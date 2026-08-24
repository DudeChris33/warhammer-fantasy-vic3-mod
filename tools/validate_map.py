#!/usr/bin/env python3
"""Pre-commit map linter for the Warhammer Fantasy world map.

Run before committing anything that touches the province bitmap or the state /
sea / strategic-region text. Ports the two checks from Exether's
``map_data/state_validator.py`` (a province is claimed by exactly one state;
every declared hub is one of the state's own provinces) and adds the engine
invariants that would otherwise only surface as a crash-to-desktop or a silent
map error in-game.

Paths come from argparse and default to repo-relative locations resolved from
this file — there is deliberately **no hardcoded absolute path** (the anti-pattern
at ``state_validator.py:139``, which would also violate the repo's "no personal
absolute paths" rule).

Usage::

    python tools/validate_map.py                 # lint the real map (repo paths)
    python tools/validate_map.py --fixture       # lint the synthetic fixture
    python tools/validate_map.py --provinces ... --state-regions ...   # custom

Exit code is 0 when clean, 1 when any check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

# Allow running as a script (`python tools/validate_map.py`) — put tools/ on the
# path so the `config` and `worldgen` packages import.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen.raster import (  # noqa: E402
    Color,
    connected_components,
    hex_to_color,
)

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
FIXTURE_EXPECTED = TOOLS_DIR / "fixtures" / "expected"

# Land states must declare all four; coastal states additionally a port.
REQUIRED_LAND_HUBS = ("city", "farm", "mine", "wood")

_STATE_HEADER = re.compile(r"(STATE_\w+)\s*=\s*\{")
_COLOR_TOKEN = re.compile(r"x[0-9A-Fa-f]{6}")
_LOC_KEY = re.compile(r"^\s*([A-Za-z0-9_.]+):\d*\s+\"")


# ---------------------------------------------------------------------------
# Parsed representations
# ---------------------------------------------------------------------------

class ParsedState:
    def __init__(self, key: str, filename: str) -> None:
        self.key = key
        self.filename = filename
        self.id: int | None = None
        self.provinces: list[Color] = []
        self.impassable: list[Color] = []
        self.hubs: dict[str, Color] = {}
        self.naval_exit_id: int | None = None
        self.port_declared = False

    # Classified against the sea colours from default.map.
    def is_sea(self, sea_colors: set[Color]) -> bool:
        return bool(self.provinces) and all(c in sea_colors for c in self.provinces)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _match_braces(text: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced braces")


def _extract_block(body: str, field: str) -> str | None:
    """Return the ``{ ... }`` contents of ``field = { ... }`` within a block body."""
    m = re.search(rf"\b{field}\s*=\s*\{{", body)
    if not m:
        return None
    open_idx = body.index("{", m.end() - 1)
    close_idx = _match_braces(body, open_idx)
    return body[open_idx + 1 : close_idx]


def parse_state_file(path: Path) -> list[ParsedState]:
    text = path.read_text(encoding="utf-8-sig")
    states: list[ParsedState] = []
    idx = 0
    while True:
        m = _STATE_HEADER.search(text, idx)
        if not m:
            break
        open_idx = text.index("{", m.end() - 1)
        close_idx = _match_braces(text, open_idx)
        body = text[open_idx + 1 : close_idx]
        states.append(_parse_block(m.group(1), body, path.name))
        idx = close_idx + 1
    return states


def _parse_block(key: str, body: str, filename: str) -> ParsedState:
    st = ParsedState(key, filename)

    m = re.search(r"\bid\s*=\s*(\d+)", body)
    if m:
        st.id = int(m.group(1))

    prov_block = _extract_block(body, "provinces")
    if prov_block is not None:
        st.provinces = [hex_to_color(t) for t in _COLOR_TOKEN.findall(prov_block)]

    imp_block = _extract_block(body, "impassable")
    if imp_block is not None:
        st.impassable = [hex_to_color(t) for t in _COLOR_TOKEN.findall(imp_block)]

    for hub in ("city", "farm", "mine", "wood", "port"):
        hm = re.search(rf"(?m)^\s*{hub}\s*=\s*(x[0-9A-Fa-f]{{6}})", body)
        if hm:
            st.hubs[hub] = hex_to_color(hm.group(1))
            if hub == "port":
                st.port_declared = True

    nm = re.search(r"\bnaval_exit_id\s*=\s*(\d+)", body)
    if nm:
        st.naval_exit_id = int(nm.group(1))

    return st


def _parse_color_field(default_map_text: str, field: str) -> set[Color]:
    block = _extract_block(default_map_text, field)
    if block is None:
        return set()
    return {hex_to_color(t) for t in _COLOR_TOKEN.findall(block)}


def _parse_loc_keys(loc_dir: Path) -> set[str]:
    keys: set[str] = set()
    if not loc_dir.is_dir():
        return keys
    for path in sorted(loc_dir.glob("*.yml")):
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            km = _LOC_KEY.match(line)
            if km:
                keys.add(km.group(1))
    return keys


# ---------------------------------------------------------------------------
# Province bitmap analysis
# ---------------------------------------------------------------------------

class ProvinceBitmap:
    """Per-colour pixel index of provinces.png, computed once."""

    def __init__(self, path: Path, wrap_x: bool) -> None:
        from worldgen.raster import read_rgb_png

        rgb = read_rgb_png(path)
        self.height, self.width = rgb.shape[0], rgb.shape[1]
        self.wrap_x = wrap_x
        code = (
            rgb[:, :, 0].astype(np.uint32) << 16
        ) | (rgb[:, :, 1].astype(np.uint32) << 8) | rgb[:, :, 2].astype(np.uint32)
        self._code = code

        flat = code.ravel()
        order = np.argsort(flat, kind="stable")
        sorted_codes = flat[order]
        boundaries = np.flatnonzero(np.diff(sorted_codes)) + 1
        starts = np.concatenate(([0], boundaries))
        ends = np.concatenate((boundaries, [len(flat)]))
        self.pixels: dict[Color, list[tuple[int, int]]] = {}
        self.area: dict[Color, int] = {}
        w = self.width
        for s, e in zip(starts.tolist(), ends.tolist()):
            c = int(sorted_codes[s])
            color = ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)
            idxs = order[s:e]
            xs = (idxs % w).tolist()
            ys = (idxs // w).tolist()
            self.pixels[color] = list(zip(xs, ys))
            self.area[color] = e - s

    @property
    def colors(self) -> set[Color]:
        return set(self.pixels)

    def coastal_colors(self, sea_colors: set[Color]) -> set[Color]:
        """Colours with at least one pixel adjacent to a sea pixel (wrap-aware x)."""
        sea_codes = np.array(
            [(r << 16) | (g << 8) | b for (r, g, b) in sea_colors], dtype=np.uint32
        )
        sea = np.isin(self._code, sea_codes)
        neighbor_sea = np.zeros_like(sea)
        # x axis wraps
        neighbor_sea |= np.roll(sea, 1, axis=1)
        neighbor_sea |= np.roll(sea, -1, axis=1)
        # y axis does not wrap (top/bottom map edges are not ocean by adjacency)
        up = np.zeros_like(sea)
        up[:-1, :] = sea[1:, :]
        down = np.zeros_like(sea)
        down[1:, :] = sea[:-1, :]
        neighbor_sea |= up
        neighbor_sea |= down
        coastal_pixel = neighbor_sea & ~sea
        coastal_codes = np.unique(self._code[coastal_pixel])
        return {((int(c) >> 16) & 0xFF, (int(c) >> 8) & 0xFF, int(c) & 0xFF) for c in coastal_codes}


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def validate(
    provinces_path: Path,
    state_regions_dir: Path,
    default_map_path: Path,
    loc_dir: Path,
    min_province_area: int = 4,
    wrap_x: bool = True,
) -> list[str]:
    """Run every check and return a flat list of error strings (empty == clean)."""
    errors: list[str] = []

    # --- load state text -------------------------------------------------
    state_files = sorted(state_regions_dir.glob("*.txt")) if state_regions_dir.is_dir() else []
    if not state_files:
        return [f"no state-region files found in {state_regions_dir}"]
    states: list[ParsedState] = []
    for path in state_files:
        states.extend(parse_state_file(path))

    # --- default.map sea/lake colours -----------------------------------
    sea_colors: set[Color] = set()
    lake_colors: set[Color] = set()
    if default_map_path.is_file():
        dm_text = default_map_path.read_text(encoding="utf-8-sig")
        sea_colors = _parse_color_field(dm_text, "sea_starts")
        lake_colors = _parse_color_field(dm_text, "lakes")
    else:
        errors.append(f"default.map not found at {default_map_path}")

    # --- province bitmap -------------------------------------------------
    bitmap: ProvinceBitmap | None = None
    if provinces_path.is_file():
        bitmap = ProvinceBitmap(provinces_path, wrap_x)
    else:
        errors.append(f"provinces.png not found at {provinces_path}")

    # classify land vs sea states against the sea palette
    land_states = [s for s in states if not s.is_sea(sea_colors)]
    sea_states = [s for s in states if s.is_sea(sea_colors)]

    errors += _check_province_uniqueness(states)
    errors += _check_hub_membership(states)
    errors += _check_required_hubs(land_states)
    errors += _check_id_bands(land_states, sea_states)
    if bitmap is not None:
        errors += _check_coastal_naval_exit(land_states, sea_states, bitmap, sea_colors)
        errors += _check_degenerate_provinces(bitmap, min_province_area)
        errors += _check_bitmap_state_crosscheck(bitmap, states, sea_colors, lake_colors)
        errors += _check_lakes_stateless(states, lake_colors)
    errors += _check_loc_coverage(states, loc_dir)
    return errors


def _check_province_uniqueness(states: list[ParsedState]) -> list[str]:
    claims: dict[Color, list[ParsedState]] = {}
    for st in states:
        for color in st.provinces:
            claims.setdefault(color, []).append(st)
    errors = []
    from worldgen.raster import color_to_hex

    for color, owners in sorted(claims.items()):
        if len(owners) > 1:
            who = ", ".join(f"{o.key} ({o.filename})" for o in owners)
            errors.append(f"province {color_to_hex(color)} is claimed by multiple states: {who}")
    return errors


def _check_hub_membership(states: list[ParsedState]) -> list[str]:
    from worldgen.raster import color_to_hex

    errors = []
    for st in states:
        own = set(st.provinces)
        impassable = set(st.impassable)
        for hub_name, color in sorted(st.hubs.items()):
            if color not in own:
                errors.append(
                    f"{st.key} ({st.filename}): {hub_name} {color_to_hex(color)} "
                    f"is not one of the state's provinces"
                )
            elif color in impassable:
                errors.append(
                    f"{st.key} ({st.filename}): {hub_name} {color_to_hex(color)} "
                    f"is on an impassable province"
                )
    return errors


def _check_required_hubs(land_states: list[ParsedState]) -> list[str]:
    errors = []
    for st in land_states:
        for hub in REQUIRED_LAND_HUBS:
            if hub not in st.hubs:
                errors.append(f"{st.key} ({st.filename}): land state missing required '{hub}' hub")
    return errors


def _check_id_bands(land_states: list[ParsedState], sea_states: list[ParsedState]) -> list[str]:
    errors = []
    seen: dict[int, ParsedState] = {}
    for st in land_states + sea_states:
        if st.id is None:
            errors.append(f"{st.key} ({st.filename}): missing id")
            continue
        if st.id in seen:
            other = seen[st.id]
            errors.append(
                f"id {st.id} used by both {st.key} ({st.filename}) and "
                f"{other.key} ({other.filename})"
            )
        else:
            seen[st.id] = st
    for st in land_states:
        if st.id is not None and not (map_config.LAND_ID_START <= st.id < map_config.SEA_ID_START):
            errors.append(
                f"{st.key} ({st.filename}): land id {st.id} outside band "
                f"[{map_config.LAND_ID_START}, {map_config.SEA_ID_START})"
            )
    for st in sea_states:
        if st.id is not None and st.id < map_config.SEA_ID_START:
            errors.append(
                f"{st.key} ({st.filename}): sea id {st.id} below band start "
                f"{map_config.SEA_ID_START}"
            )
    return errors


def _check_coastal_naval_exit(
    land_states: list[ParsedState],
    sea_states: list[ParsedState],
    bitmap: ProvinceBitmap,
    sea_colors: set[Color],
) -> list[str]:
    errors = []
    coastal_colors = bitmap.coastal_colors(sea_colors)
    sea_ids = {s.id for s in sea_states if s.id is not None}
    for st in land_states:
        has_coastal_pixels = any(c in coastal_colors for c in st.provinces)
        if has_coastal_pixels:
            if not st.port_declared:
                errors.append(f"{st.key} ({st.filename}): coastal state (has coastal provinces) has no port")
            if st.naval_exit_id is None:
                errors.append(f"{st.key} ({st.filename}): coastal state has no naval_exit_id")
            elif st.naval_exit_id not in sea_ids:
                errors.append(
                    f"{st.key} ({st.filename}): naval_exit_id {st.naval_exit_id} "
                    f"is not a real sea-zone id"
                )
        else:
            if st.port_declared:
                errors.append(f"{st.key} ({st.filename}): landlocked state (no coastal provinces) declares a port")
            if st.naval_exit_id is not None:
                errors.append(f"{st.key} ({st.filename}): landlocked state declares naval_exit_id")
    return errors


def _check_degenerate_provinces(bitmap: ProvinceBitmap, min_area: int) -> list[str]:
    from worldgen.raster import color_to_hex

    errors = []
    for color in sorted(bitmap.colors):
        area = bitmap.area[color]
        if area < min_area:
            errors.append(
                f"province {color_to_hex(color)} is degenerate: {area} px "
                f"(< {min_area})"
            )
        comps = connected_components(
            bitmap.pixels[color], bitmap.width, bitmap.height, bitmap.wrap_x
        )
        if len(comps) > 1:
            sizes = ", ".join(str(len(c)) for c in sorted(comps, key=len, reverse=True))
            errors.append(
                f"province {color_to_hex(color)} is disconnected: "
                f"{len(comps)} components (sizes {sizes})"
            )
    return errors


def _check_bitmap_state_crosscheck(
    bitmap: ProvinceBitmap,
    states: list[ParsedState],
    sea_colors: set[Color],
    lake_colors: set[Color],
) -> list[str]:
    from worldgen.raster import color_to_hex

    errors = []
    state_colors: set[Color] = set()
    for st in states:
        state_colors.update(st.provinces)

    png_colors = bitmap.colors
    # Every bitmap colour except lakes must be claimed by some state.
    for color in sorted(png_colors - lake_colors - state_colors):
        errors.append(
            f"province colour {color_to_hex(color)} in provinces.png "
            f"is in no state file"
        )
    # Every state colour must exist in the bitmap.
    for color in sorted(state_colors - png_colors):
        errors.append(
            f"province colour {color_to_hex(color)} in a state file "
            f"is absent from provinces.png"
        )
    return errors


def _check_lakes_stateless(states: list[ParsedState], lake_colors: set[Color]) -> list[str]:
    from worldgen.raster import color_to_hex

    errors = []
    for st in states:
        for color in sorted(set(st.provinces) & lake_colors):
            errors.append(
                f"{st.key} ({st.filename}): lake colour {color_to_hex(color)} "
                f"must not belong to any state"
            )
    return errors


def _check_loc_coverage(states: list[ParsedState], loc_dir: Path) -> list[str]:
    errors = []
    loc_keys = _parse_loc_keys(loc_dir)
    for st in sorted(states, key=lambda s: s.key):
        if st.key not in loc_keys:
            errors.append(f"{st.key}: no localization entry under {loc_dir}")
    return errors


# ---------------------------------------------------------------------------
# The S3a state-label layer (--labels)
# ---------------------------------------------------------------------------
#
# S3a produces a label layer, not provinces — so it needs its own lint. The
# checks are the engine invariants restated one level up: what "every province is
# in exactly one state" becomes when the states themselves are the thing being
# built. Catching a gap or a straddling cell here is what makes an S3a
# control-point correction cheap; discovering it after 40k provinces have been
# cut from the layer is not.

def validate_labels(labels_path: Path, mask_path: Path, index_path: Path,
                    wrap_x: bool = True, min_cell_area: int = 256) -> list[str]:
    """Check that the state-label layer tiles the committed land/sea mask exactly."""
    import json

    from worldgen import cells

    errors: list[str] = []
    for path in (labels_path, mask_path, index_path):
        if not path.is_file():
            errors.append(f"missing {path}")
    if errors:
        return errors

    labels = cells.read_labels(labels_path)
    land = _read_mask(mask_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))

    if labels.shape != land.shape:
        return [f"label layer {labels.shape} does not match the mask {land.shape}"]

    n_land = int(index["land_cells"])
    n_sea = int(index["sea_cells"])

    # 1. Total partition: no unlabelled pixel anywhere.
    blank = int((labels == 0).sum())
    if blank:
        errors.append(f"{blank:,} pixels carry no label — the layer does not tile the canvas")

    # 2. No cell straddles the coastline. This is the invariant that keeps the
    #    mask authoritative: a label with pixels on both sides would mean a state
    #    that is partly a sea zone, which the engine has no representation for.
    land_ids = set(np.unique(labels[land]).tolist())
    sea_ids = set(np.unique(labels[~land]).tolist())
    both = sorted(land_ids & sea_ids)
    if both:
        errors.append(
            f"{len(both)} label(s) span land and sea (first few: {both[:5]}) — "
            f"a cell must be wholly one or the other"
        )

    # 3. The index and the raster agree about which labels exist and what they are.
    for i in sorted(land_ids):
        if not (1 <= i <= n_land):
            errors.append(f"land pixel carries label {i}, outside the land band 1..{n_land}")
            break
    for i in sorted(sea_ids):
        if not (n_land < i <= n_land + n_sea):
            errors.append(
                f"water pixel carries label {i}, outside the sea band "
                f"{n_land + 1}..{n_land + n_sea}"
            )
            break
    listed_ids = [c["label"] for c in index["cells"]]
    listed = set(listed_ids)
    if len(listed_ids) != len(listed):
        # A duplicate entry is invisible to a set comparison, and the two copies
        # can disagree about area, macro and coastal — so whichever one a later
        # phase happens to read decides the answer.
        seen: set[int] = set()
        dupes = sorted({i for i in listed_ids if i in seen or seen.add(i)})
        errors.append(
            f"{len(dupes)} label(s) appear more than once in the index "
            f"(first few: {dupes[:5]})"
        )
    present = land_ids | sea_ids
    for missing in sorted(present - listed)[:5]:
        errors.append(f"label {missing} is in the raster but not in the index")
    for extra in sorted(listed - present)[:5]:
        errors.append(f"label {extra} is in the index but not in the raster")

    # The summary counts derive the id bands checked above, so they have to agree
    # with the entries they summarise or the band check is validating itself.
    for kind, declared in (("land", n_land), ("sea", n_sea)):
        actual = sum(1 for c in index["cells"] if c["kind"] == kind)
        if actual != declared:
            errors.append(
                f"index declares {declared} {kind} cells but lists {actual} of them"
            )

    # 4. Every cell is one connected region. A state in two pieces is not a state.
    comp = cells.components(labels, wrap_x)
    pairs = np.unique(np.stack([labels.ravel(), comp.ravel()], axis=1), axis=0)
    counts = np.bincount(pairs[:, 0].astype(np.int64), minlength=int(labels.max()) + 1)
    torn = np.flatnonzero(counts > 1)
    if torn.size:
        errors.append(
            f"{torn.size} cell(s) are disconnected (first few: {torn[:5].tolist()})"
        )

    # 5. Areas in the index match the raster, so downstream code can trust it
    #    without recomputing over 30 megapixels.
    areas = np.bincount(labels.ravel(), minlength=n_land + n_sea + 1)
    for c in index["cells"]:
        if int(areas[c["label"]]) != int(c["area"]):
            errors.append(
                f"label {c['label']}: index says {c['area']} px, raster has {areas[c['label']]}"
            )
            break

    # 6. Every land cell has a macro region — S3b groups strategic regions by it.
    for c in index["cells"]:
        if c["kind"] == "land" and not c["macro"]:
            errors.append(f"land cell {c['label']} has no macro region")
            break

    # 6b. The index's `coastal` flag must match the raster. This one earns its
    #     keep downstream: S3b turns `coastal` into `port` + `naval_exit_id`, and
    #     the state schema then *requires* the two to agree — so a wrong flag here
    #     surfaces as a confusing schema failure a phase later, pointing at the
    #     wrong file. Recomputed deliberately by a different route than
    #     `cells.coastal_labels` (a dilation of the sea mask rather than four
    #     shifts of it), so the two implementations can disagree and this check
    #     has something to catch beyond a corrupted index.
    from scipy import ndimage

    sea = ~land
    pad = 1 if wrap_x else 0
    padded = np.concatenate([sea[:, -pad:], sea, sea[:, :pad]], axis=1) if pad else sea
    grown = ndimage.binary_dilation(padded, structure=ndimage.generate_binary_structure(2, 1))
    grown = grown[:, pad:-pad] if pad else grown
    touching = set(np.unique(labels[grown & land]).tolist()) - {0}
    bad = [c["label"] for c in index["cells"]
           if c["kind"] == "land" and bool(c["coastal"]) != (c["label"] in touching)]
    if bad:
        errors.append(
            f"{len(bad)} land cell(s) have a `coastal` flag that disagrees with the "
            f"mask (first few: {bad[:5]})"
        )

    # 7. No avoidably-degenerate cell. S3b cuts provinces out of each state, and a
    #    state a few pixels across cannot carry one. But a small *island* is a
    #    legitimately small state — vanilla ships several — and there is nothing to
    #    merge it into, so the rule is "below the floor **and** adjacent to another
    #    cell of the same kind", i.e. it could have been merged and was not.
    tiny = [i for i in sorted(land_ids | sea_ids)
            if i > 0 and int(areas[i]) < int(min_cell_area)]
    if tiny:
        same_kind_nb: dict[int, bool] = {i: False for i in tiny}
        pairs = np.concatenate([
            np.stack([labels[:, :-1].ravel(), labels[:, 1:].ravel()], axis=1),
            np.stack([labels[:-1, :].ravel(), labels[1:, :].ravel()], axis=1),
            np.stack([labels[:, -1].ravel(), labels[:, 0].ravel()], axis=1)
            if wrap_x else np.empty((0, 2), dtype=labels.dtype),
        ])
        pairs = np.unique(pairs[pairs[:, 0] != pairs[:, 1]], axis=0)
        tiny_set = set(tiny)
        for a, b in pairs.tolist():
            for u, v in ((a, b), (b, a)):
                if u in tiny_set and ((u in land_ids) == (v in land_ids)):
                    same_kind_nb[u] = True
        mergeable = [i for i in tiny if same_kind_nb[i]]
        if mergeable:
            smallest = min(mergeable, key=lambda i: areas[i])
            errors.append(
                f"{len(mergeable)} cell(s) are below the {min_cell_area} px floor and "
                f"have a same-kind neighbour to merge into "
                f"(smallest: label {smallest} at {int(areas[smallest])} px)"
            )
    return errors


# ---------------------------------------------------------------------------
# The first-pass province bitmap (--province-bitmap)
# ---------------------------------------------------------------------------
#
# Board #2773 produces the RGB province image + its index directly from the
# drawn source, ahead of the state_regions/*.txt text the repo-form validator
# needs. This is the RGB mirror of validate_labels: the same engine invariants
# ("every pixel one province, no province straddles the coast, every province one
# connected region") restated on the colour bitmap, cross-checked against the
# committed index and the committed sea-zone layer.

def validate_provinces(provinces_path: Path, mask_path: Path, index_path: Path,
                       sea_labels_path: Path, wrap_x: bool = True,
                       min_cell_area: int = 4) -> list[str]:
    """Check the first-pass province bitmap tiles the mask exactly and agrees with
    its index and the committed sea-zone layer."""
    import json

    from worldgen import cells
    from worldgen.raster import read_rgb_png

    errors: list[str] = []
    for path in (provinces_path, mask_path, index_path, sea_labels_path):
        if not path.is_file():
            errors.append(f"missing {path}")
    if errors:
        return errors

    rgb = read_rgb_png(provinces_path)
    land = _read_mask(mask_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))

    if rgb.shape[:2] != land.shape:
        return [f"province bitmap {rgb.shape[:2]} does not match the mask {land.shape}"]

    n_land = int(index["land_provinces"])
    n_sea = int(index["sea_provinces"])

    # Pack each pixel's colour into one 24-bit key; map keys to index labels.
    key = ((rgb[..., 0].astype(np.int64) << 16)
           | (rgb[..., 1].astype(np.int64) << 8)
           | rgb[..., 2].astype(np.int64))

    # 1. The (0,0,0) sentinel must never appear as a province colour.
    if bool((key == 0).any()):
        errors.append(f"{int((key == 0).sum()):,} pixel(s) are (0,0,0) — the reserved sentinel")

    color_to_label: dict[int, int] = {}
    dup_colors: list[int] = []
    for c in index["cells"]:
        r, g, b = c["color"]
        k = (int(r) << 16) | (int(g) << 8) | int(b)
        if k in color_to_label:
            dup_colors.append(k)
        color_to_label[k] = int(c["label"])
    if dup_colors:
        errors.append(f"{len(dup_colors)} colour(s) are shared by more than one province in the index")

    uniq, inv = np.unique(key, return_inverse=True)
    lut = np.array([color_to_label.get(int(k), -1) for k in uniq], dtype=np.int64)
    unknown = [int(k) for k, lab in zip(uniq.tolist(), lut.tolist()) if lab < 0 and k != 0]
    if unknown:
        errors.append(
            f"{len(unknown)} colour(s) appear in the bitmap but not the index "
            f"(first few hex: {[f'{k:06X}' for k in unknown[:5]]})")
    labels = np.where(lut[inv].reshape(key.shape) < 0, 0, lut[inv].reshape(key.shape)).astype(np.int32)

    # 2. No province straddles the coast (the mask stays authoritative).
    land_ids = set(np.unique(labels[land]).tolist()) - {0}
    sea_ids = set(np.unique(labels[~land]).tolist()) - {0}
    both = sorted(land_ids & sea_ids)
    if both:
        errors.append(
            f"{len(both)} province(s) span land and sea (first few: {both[:5]}) — "
            f"a province must be wholly one or the other")

    # 3. Land labels 1..n_land, sea labels n_land+1..n_land+n_sea.
    for i in sorted(land_ids):
        if not (1 <= i <= n_land):
            errors.append(f"land pixel carries label {i}, outside the land band 1..{n_land}")
            break
    for i in sorted(sea_ids):
        if not (n_land < i <= n_land + n_sea):
            errors.append(
                f"water pixel carries label {i}, outside the sea band "
                f"{n_land + 1}..{n_land + n_sea}")
            break

    # 4. Index kinds/ids/areas agree with the raster.
    listed = {c["label"] for c in index["cells"]}
    present = land_ids | sea_ids
    for missing in sorted(present - listed)[:5]:
        errors.append(f"label {missing} is in the bitmap but not the index")
    for extra in sorted(listed - present)[:5]:
        errors.append(f"label {extra} is in the index but not the bitmap")
    for kind, declared in (("land", n_land), ("sea", n_sea)):
        actual = sum(1 for c in index["cells"] if c["kind"] == kind)
        if actual != declared:
            errors.append(f"index declares {declared} {kind} provinces but lists {actual}")
    areas = np.bincount(labels.ravel(), minlength=n_land + n_sea + 1)
    for c in index["cells"]:
        lab = int(c["label"])
        if lab <= n_land + n_sea and int(areas[lab]) != int(c["area"]):
            errors.append(f"label {lab}: index says {c['area']} px, raster has {int(areas[lab])}")
            break
    # Id bands: land id = land_id_start + (label-1); sea id = sea_id_start + (sea_index-1).
    lid, sid = int(index["land_id_start"]), int(index["sea_id_start"])
    for c in index["cells"]:
        lab = int(c["label"])
        want = lid + (lab - 1) if c["kind"] == "land" else sid + (lab - n_land - 1)
        if int(c["id"]) != want:
            errors.append(f"label {lab}: index id {c['id']} != expected {want} for a {c['kind']} province")
            break

    # 5. Every province is one connected region (a province in two pieces is none).
    comp = cells.components(labels, wrap_x)
    pairs = np.unique(np.stack([labels.ravel(), comp.ravel()], axis=1), axis=0)
    counts = np.bincount(pairs[:, 0].astype(np.int64), minlength=int(labels.max()) + 1)
    torn = np.flatnonzero(counts > 1)
    torn = torn[torn > 0]
    if torn.size:
        errors.append(f"{torn.size} province(s) are disconnected (first few: {torn[:5].tolist()})")

    # 6. The sea province count matches the committed sea-zone layer.
    sea_lab = cells.read_labels(sea_labels_path)
    committed_sea = int(sea_lab.max())
    if committed_sea != n_sea:
        errors.append(
            f"index has {n_sea} sea provinces but {sea_labels_path.name} has {committed_sea}")
    if sea_lab.shape == land.shape and not bool((( sea_lab > 0) == ~land).all()):
        errors.append(f"{sea_labels_path.name} does not tile this mask's water exactly")

    # 7. No avoidably-degenerate LAND province: below the floor AND with a
    #    same-kind neighbour it could have merged into (a lone small island is
    #    legitimate). Restricted to land, which this generator subdivides and so
    #    controls; the sea provinces are a faithful 1:1 copy of the committed,
    #    separately-gated sea-zone layer (whose own policy deliberately keeps thin
    #    coastal inlets, merge_floor=1), and check 6 already ties their count to
    #    that layer — re-flagging them here would be a false positive this
    #    generator cannot fix without diverging from the sea layer.
    tiny = [i for i in sorted(land_ids) if i > 0 and int(areas[i]) < int(min_cell_area)]
    if tiny:
        adj = np.concatenate([
            np.stack([labels[:, :-1].ravel(), labels[:, 1:].ravel()], axis=1),
            np.stack([labels[:-1, :].ravel(), labels[1:, :].ravel()], axis=1),
            np.stack([labels[:, -1].ravel(), labels[:, 0].ravel()], axis=1)
            if wrap_x else np.empty((0, 2), dtype=labels.dtype),
        ])
        adj = np.unique(adj[adj[:, 0] != adj[:, 1]], axis=0)
        tiny_set = set(tiny)
        same_kind_nb = {i: False for i in tiny}
        for a, b in adj.tolist():
            for u, v in ((a, b), (b, a)):
                if u in tiny_set and v > 0 and ((u in land_ids) == (v in land_ids)):
                    same_kind_nb[u] = True
        mergeable = [i for i in tiny if same_kind_nb[i]]
        if mergeable:
            smallest = min(mergeable, key=lambda i: areas[i])
            errors.append(
                f"{len(mergeable)} province(s) are below the {min_cell_area} px floor and have a "
                f"same-kind neighbour to merge into (smallest: label {smallest} at "
                f"{int(areas[smallest])} px)")
    return errors


def _read_mask(path: Path) -> np.ndarray:
    from worldgen.raster import read_mask_png

    return read_mask_png(path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fixture", action="store_true", help="lint tools/fixtures/expected/ instead of the repo map")
    p.add_argument("--labels", action="store_true", help="lint the S3a state-label layer instead of the province map")
    p.add_argument("--province-bitmap", action="store_true",
                   help="lint the first-pass province bitmap (RGB + index) instead of the repo map text")
    p.add_argument("--labels-path", type=Path, help="path to state_labels.png")
    p.add_argument("--sea-labels-path", type=Path, help="path to sea_zones.png")
    p.add_argument("--mask-path", type=Path, help="path to land_sea_mask.png")
    p.add_argument("--index-path", type=Path, help="path to state_labels_index.json")
    p.add_argument("--provinces", type=Path, help="path to provinces.png")
    p.add_argument("--state-regions", type=Path, help="path to state_regions/ directory")
    p.add_argument("--default-map", type=Path, help="path to default.map")
    p.add_argument("--loc-dir", type=Path, help="path to the map localization directory")
    p.add_argument("--min-province-area", type=int, default=4, help="minimum province pixel area (default 4)")
    return p


def _resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    if args.fixture:
        base = FIXTURE_EXPECTED
        defaults = {
            "provinces": base / "provinces.png",
            "state_regions": base / "state_regions",
            "default_map": base / "default.map",
            "loc_dir": base / "loc",
        }
    else:
        defaults = {
            "provinces": REPO_ROOT / "map_data" / "provinces.png",
            "state_regions": REPO_ROOT / "map_data" / "state_regions",
            "default_map": REPO_ROOT / "map_data" / "default.map",
            "loc_dir": REPO_ROOT / "localization" / "english" / "map",
        }
    return {
        "provinces": args.provinces or defaults["provinces"],
        "state_regions": args.state_regions or defaults["state_regions"],
        "default_map": args.default_map or defaults["default_map"],
        "loc_dir": args.loc_dir or defaults["loc_dir"],
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.labels:
        derived = TOOLS_DIR / "derived"
        errors = validate_labels(
            labels_path=args.labels_path or derived / "state_labels.png",
            mask_path=args.mask_path or derived / "land_sea_mask.png",
            index_path=args.index_path or derived / "state_labels_index.json",
            wrap_x=map_config.WRAP_X,
        )
        if errors:
            print(f"validate_map --labels: {len(errors)} error(s):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print("validate_map --labels: the state-label layer tiles the mask exactly.")
        return 0

    if args.province_bitmap:
        derived = TOOLS_DIR / "derived"
        errors = validate_provinces(
            provinces_path=args.provinces or REPO_ROOT / "map_data" / "provinces.png",
            mask_path=args.mask_path or derived / "land_sea_mask.png",
            index_path=args.index_path or derived / "provinces_index.json",
            sea_labels_path=args.sea_labels_path or derived / "sea_zones.png",
            wrap_x=map_config.WRAP_X,
            min_cell_area=args.min_province_area,
        )
        if errors:
            print(f"validate_map --province-bitmap: {len(errors)} error(s):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print("validate_map --province-bitmap: the province bitmap tiles the mask and agrees "
              "with its index + the sea layer.")
        return 0

    paths = _resolve_paths(args)
    errors = validate(
        provinces_path=paths["provinces"],
        state_regions_dir=paths["state_regions"],
        default_map_path=paths["default_map"],
        loc_dir=paths["loc_dir"],
        min_province_area=args.min_province_area,
        wrap_x=map_config.WRAP_X,
    )
    if errors:
        print(f"validate_map: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("validate_map: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
