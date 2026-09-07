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
    provinces_index_path: Path | None = None,
    hub_anchors_index_path: Path | None = None,
    rivers_path: Path | None = None,
    rivers_mask_path: Path | None = None,
    canon_river_names_path: Path | None = None,
    canon_rivers_csv_path: Path | None = None,
    rivers_index_path: Path | None = None,
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
    # Deliberately non-contiguous provinces (island-override merges — see
    # land_provinces.merge_island_overrides) carry an `archipelago` flag in
    # provinces_index.json; a torn province is only a real bug when it isn't
    # one of these. Optional: the fixture's golden bitmap has no index file
    # and never needed the concept, so an absent path just means no exceptions.
    archipelago_colors: set[Color] = set()
    index_lake_colors: set[Color] | None = None
    if provinces_index_path is not None and provinces_index_path.is_file():
        import json

        prov_index = json.loads(provinces_index_path.read_text(encoding="utf-8"))
        archipelago_colors = {
            tuple(c["color"]) for c in prov_index["cells"] if c.get("archipelago")
        }
        index_lake_colors = {
            tuple(int(v) for v in c["color"])
            for c in prov_index["cells"] if c.get("kind") == "lake"
        }
    # Hub-anchor exemptions + checks (#3665). Anchor-flagged province colours are
    # deliberately kept small (a hub seeded near a region edge), so they are
    # exempted from the disconnected/degenerate sweep the same way archipelagos are;
    # the hard < min_area flag still stands. Present only when a worksheet exists.
    anchor_colors: set[Color] = set()
    hub_index: dict | None = None
    if hub_anchors_index_path is not None and hub_anchors_index_path.is_file() and bitmap is not None:
        import json

        hub_index = json.loads(hub_anchors_index_path.read_text(encoding="utf-8"))
        anchor_colors = {tuple(int(v) for v in h["province_color"]) for h in hub_index["hubs"]}
    if bitmap is not None:
        errors += _check_coastal_naval_exit(land_states, sea_states, bitmap, sea_colors)
        errors += _check_degenerate_provinces(
            bitmap, min_province_area, archipelago_colors | anchor_colors)
        errors += _check_bitmap_state_crosscheck(bitmap, states, sea_colors, lake_colors)
        errors += _check_lakes_stateless(states, lake_colors)
        if index_lake_colors is not None:
            errors += _check_lakes_declared(index_lake_colors, lake_colors)
        if hub_index is not None:
            errors += _check_hub_anchors(
                bitmap, states, sea_colors, _parse_loc_keys(loc_dir), hub_index)
        # Rivers (#3703): gated on the source-driven pipeline being live — the
        # names file's presence is that signal (the same file-exists idiom the
        # canon_rivers.csv cross-check uses). Absent -> the committed gate stays
        # green on today's heightmap-derived bitmap, which was never held to the
        # strict caps. The check's own correctness is proven by a synthetic
        # self-check in run_fixture.py, not against that bitmap.
        if (canon_river_names_path is not None and canon_river_names_path.is_file()
                and rivers_path is not None and rivers_path.is_file()
                and rivers_mask_path is not None and rivers_mask_path.is_file()):
            from worldgen.raster import read_indexed_png

            ridx, _ = read_indexed_png(rivers_path)
            rmask = _read_mask(rivers_mask_path)
            csv_rows = (_parse_canon_rivers_csv(canon_rivers_csv_path)
                        if canon_rivers_csv_path is not None and canon_rivers_csv_path.is_file()
                        else None)
            rindex = None
            if rivers_index_path is not None and rivers_index_path.is_file():
                import json

                rindex = json.loads(rivers_index_path.read_text(encoding="utf-8"))
            errors += _check_rivers(ridx, rmask, wrap_x, csv_rows, rindex)
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


def _check_hub_anchors(bitmap: "ProvinceBitmap", states: list[ParsedState],
                       sea_colors: set[Color], loc_keys: set[str],
                       hub_index: dict) -> list[str]:
    """#3665 hub-anchor checks, straight off the bitmap so they can catch a
    disagreement between the seeded cut and the emitted state (they never re-read
    the derived index for the answer, only for which pixel to look at):

    * each anchor's resolved pixel is in-canvas and its provinces.png colour is a
      LAND colour that matches the index (a stale index vs a re-cut bitmap fails);
    * that colour is claimed by exactly one state, and that state declares it as
      its ``<hub_type>`` hub — proving both "picked as the hub" and "hub in its own
      state" in one check;
    * a ``port`` anchor's province is coastal;
    * the ``HUB_NAME_<state_key>_<hub>`` loc key exists;
    * two anchors of one state share a province only when the state has fewer
      provinces than its distinct anchor hubs (the legitimate stacking case).
    """
    from worldgen.raster import color_to_hex

    errors: list[str] = []
    W, H = bitmap.width, bitmap.height
    owner: dict[Color, ParsedState] = {}
    dup: set[Color] = set()
    for st in states:
        for col in st.provinces:
            if col in owner:
                dup.add(col)
            owner[col] = st
    coastal = bitmap.coastal_colors(sea_colors)
    per_state: dict[str, list[tuple[str, Color, ParsedState]]] = {}

    for h in hub_index["hubs"]:
        name = h["name"]
        rx, ry = int(h["resolved"][0]), int(h["resolved"][1])
        hub = h["hub"]
        idx_col = tuple(int(v) for v in h["province_color"])
        if not (0 <= rx < W and 0 <= ry < H):
            errors.append(f"hub '{name}' resolved pixel ({rx},{ry}) is outside the {W}x{H} canvas")
            continue
        code = int(bitmap._code[ry, rx])
        actual = ((code >> 16) & 0xFF, (code >> 8) & 0xFF, code & 0xFF)
        if actual != idx_col:
            errors.append(
                f"hub '{name}': hub_anchors_index colour {color_to_hex(idx_col)} != "
                f"provinces.png colour {color_to_hex(actual)} at ({rx},{ry}) — stale index")
            continue
        if actual in sea_colors:
            errors.append(f"hub '{name}': anchor province {color_to_hex(actual)} is sea, not land")
            continue
        st = owner.get(actual)
        if st is None:
            errors.append(f"hub '{name}': anchor province {color_to_hex(actual)} is claimed by no state")
            continue
        if actual in dup:
            errors.append(f"hub '{name}': anchor province {color_to_hex(actual)} is claimed by multiple states")
        declared = st.hubs.get(hub)
        if declared != actual:
            errors.append(
                f"hub '{name}' ({st.key}): province {color_to_hex(actual)} is not the state's "
                f"'{hub}' hub (declared {color_to_hex(declared) if declared else 'none'})")
        if hub == "port" and actual not in coastal:
            errors.append(
                f"hub '{name}' ({st.key}): a port anchor must be coastal, {color_to_hex(actual)} is not")
        lk = f"HUB_NAME_{st.key}_{hub}"
        if lk not in loc_keys:
            errors.append(f"hub '{name}' ({st.key}): missing loc key {lk}")
        per_state.setdefault(st.key, []).append((hub, actual, st))

    for skey, items in per_state.items():
        by_prov: dict[Color, list[str]] = {}
        for hub, col, _st in items:
            by_prov.setdefault(col, []).append(hub)
        for col, hubs_here in by_prov.items():
            if len(hubs_here) > 1:
                st = items[0][2]
                n_prov = len(set(st.provinces))
                n_hubs = len({hub for hub, _c, _s in items})
                if n_prov >= n_hubs:
                    errors.append(
                        f"{skey}: hubs {sorted(hubs_here)} share province {color_to_hex(col)}, "
                        f"but the state has {n_prov} provinces for {n_hubs} distinct anchor hub(s) "
                        f"— give them separate provinces")
    return errors


#: The vanilla rivers.png semantic index set (tools/lut/rivers_palette.json):
#: source 0, merge 1, split 2, the blue width ramp 3-11, sea 254, land 255. The
#: source-driven generator emits only a subset (0/1/3/4/6/8/254/255); an index
#: outside this whole set means a re-save remapped a semantic value.
_RIVER_INDICES = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 254, 255})
_RIVER_LAND = 255
_RIVER_SEA = 254
_RIVER_SOURCE = 0
_RIVER_MERGE = 1

_R_D8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


def _neighbors8(y: int, x: int, h: int, w: int, wrap_x: bool):
    for dy, dx in _R_D8:
        ny = y + dy
        if ny < 0 or ny >= h:
            continue
        nx = x + dx
        if nx < 0 or nx >= w:
            if not wrap_x:
                continue
            nx %= w
        yield (ny, nx)


def _check_rivers(idx: np.ndarray, land_mask: np.ndarray, wrap_x: bool,
                  canon_rivers_csv: list[tuple[str, str]] | None = None,
                  rivers_index: dict | None = None) -> list[str]:
    """Validate a committed ``rivers.png`` index array against the vanilla model.

    Mirrors the invariants ``worldgen.rivers._validate`` enforces before writing,
    re-checked here on the committed bitmap (defense in depth — the offline gate in
    testing.md). Returns a list of error strings (empty == clean):

    * every index is in the vanilla semantic set;
    * no river pixel sits on sea (land mask is the authority);
    * every green source (0) is inland (no water in its 8-neighbourhood);
    * every red merge (1) touches another river pixel;
    * every ramp-body river endpoint (a body pixel with a single river neighbour)
      is a sea mouth — 8-adjacent to open water — so no river dead-ends on land;
    * the 2×2-block caps ``worldgen.rivers`` calibrated on vanilla; and
    * when ``canon_rivers.csv`` (#3677) exists, every ``(river, state_key)`` row
      names a river whose ``rivers_index.json`` state coverage includes that state
      (a **warning**, not a hard error).
    """
    from worldgen.rivers import MAX_2X2_BLOCKS, MAX_2X2_RUN, measure_2x2_blocks

    errors: list[str] = []
    if idx.shape != land_mask.shape:
        return [f"rivers.png {idx.shape} and land mask {land_mask.shape} differ in size"]
    h, w = idx.shape

    bad = sorted(int(v) for v in np.unique(idx) if int(v) not in _RIVER_INDICES)
    if bad:
        errors.append(f"rivers.png uses indices outside the vanilla semantic set: {bad}")

    river = ~np.isin(idx, [_RIVER_LAND, _RIVER_SEA])
    water = ~land_mask
    off_land = river & water
    if off_land.any():
        n = int(off_land.sum())
        ys, xs = np.nonzero(off_land)
        errors.append(f"{n} river pixel(s) lie on sea, first at "
                      f"({int(xs[0])}, {int(ys[0])})")

    # Source (0) inland, merge (1) touches another river.
    for (yy, xx) in zip(*np.nonzero(idx == _RIVER_SOURCE)):
        if any(water[ny, nx] for ny, nx in _neighbors8(int(yy), int(xx), h, w, wrap_x)):
            errors.append(f"river source ({int(xx)}, {int(yy)}) is on the coast; "
                          f"sources must be inland")
            break
    for (yy, xx) in zip(*np.nonzero(idx == _RIVER_MERGE)):
        if not any(river[ny, nx] for ny, nx in _neighbors8(int(yy), int(xx), h, w, wrap_x)
                   if (ny, nx) != (int(yy), int(xx))):
            errors.append(f"river merge marker ({int(xx)}, {int(yy)}) touches no other stream")
            break

    # A ramp-body endpoint (one river neighbour) that is not a sea mouth is a
    # river dead-ending on land.
    body = np.isin(idx, [3, 4, 5, 6, 7, 8, 9, 10, 11])
    for (yy, xx) in zip(*np.nonzero(body)):
        y, x = int(yy), int(xx)
        nb = [(ny, nx) for ny, nx in _neighbors8(y, x, h, w, wrap_x)]
        rn = sum(1 for ny, nx in nb if river[ny, nx])
        if rn == 1 and not any(water[ny, nx] for ny, nx in nb):
            errors.append(f"river body pixel ({x}, {y}) dead-ends on land "
                          f"(a sea mouth must touch open water)")
            break

    n_blocks, run = measure_2x2_blocks(idx, wrap_x)
    if n_blocks > MAX_2X2_BLOCKS:
        errors.append(f"{n_blocks} 2x2 river blocks exceed the tolerance of "
                      f"{MAX_2X2_BLOCKS} (vanilla ships 21)")
    if run > MAX_2X2_RUN:
        errors.append(f"a run of {run} connected 2x2 river blocks exceeds the limit "
                      f"of {MAX_2X2_RUN} — streams may run parallel instead of merging")

    if canon_rivers_csv is not None and rivers_index is not None:
        cover: dict[str, set[str]] = {}
        for r in rivers_index.get("rivers", []):
            cover[r["name"]] = set(r.get("state_keys", []))
        for river_name, state_key in canon_rivers_csv:
            if river_name not in cover:
                errors.append(f"WARNING canon_rivers.csv: river '{river_name}' is not in "
                              f"rivers_index.json")
            elif state_key not in cover[river_name]:
                errors.append(f"WARNING canon_rivers.csv: '{river_name}' does not reach "
                              f"state '{state_key}' in rivers_index.json")
    return errors


def _parse_canon_rivers_csv(path: Path) -> list[tuple[str, str]]:
    """``(river, state_key)`` rows from #3677's canon_rivers.csv (header skipped)."""
    import csv

    rows: list[tuple[str, str]] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        want = {"river": 0, "state_key": 1}
        if header:
            lower = [c.strip().lower() for c in header]
            for key in ("river", "state_key"):
                if key in lower:
                    want[key] = lower.index(key)
        for row in reader:
            if len(row) <= max(want.values()):
                continue
            rows.append((row[want["river"]].strip(), row[want["state_key"]].strip()))
    return rows


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


#: Above this many pixels, a per-pixel Python BFS (`connected_components`)
#: builds enough `(x, y)` tuples/sets to exhaust memory — only a couple dozen
#: out-of-scope placeholder provinces are this large, so they take the
#: vectorized `mask_component_sizes` path instead; everything smaller keeps
#: the original BFS.
_LARGE_PROVINCE_PX = 100_000


def _check_degenerate_provinces(bitmap: ProvinceBitmap, min_area: int,
                                archipelago_colors: set[Color] = frozenset()) -> list[str]:
    from worldgen.raster import color_to_hex, mask_component_sizes

    errors = []
    for color in sorted(bitmap.colors):
        area = bitmap.area[color]
        if area < min_area:
            errors.append(
                f"province {color_to_hex(color)} is degenerate: {area} px "
                f"(< {min_area})"
            )
        if color in archipelago_colors:
            # Deliberately non-contiguous (an island-override merge) — vanilla
            # ships exactly this shape (e.g. Micronesia's province colour spans
            # 23 disconnected pixel blobs), so being torn is not itself a bug.
            continue
        if area > _LARGE_PROVINCE_PX:
            r, g, b = color
            code = (r << 16) | (g << 8) | b
            mask = bitmap._code == code
            sizes = sorted(mask_component_sizes(mask, bitmap.wrap_x), reverse=True)
            num_components = len(sizes)
        else:
            comps = connected_components(
                bitmap.pixels[color], bitmap.width, bitmap.height, bitmap.wrap_x
            )
            sizes = sorted((len(c) for c in comps), reverse=True)
            num_components = len(comps)
        if num_components > 1:
            sizes_str = ", ".join(str(s) for s in sizes)
            errors.append(
                f"province {color_to_hex(color)} is disconnected: "
                f"{num_components} components (sizes {sizes_str})"
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


def _check_lakes_declared(index_lake_colors: set[Color], lake_colors: set[Color]) -> list[str]:
    """Every ``kind=="lake"`` province colour in the index appears in default.map's
    ``lakes`` block, and vice-versa (board #3742).

    Closes the loop the ``--sea`` subset does for sea colours: a lake the generator
    cut but forgot to declare would silently ship as an undeclared water province,
    and a stray ``lakes`` colour claims a province that no longer exists."""
    from worldgen.raster import color_to_hex

    errors = []
    for color in sorted(index_lake_colors - lake_colors):
        errors.append(f"lake colour {color_to_hex(color)} in provinces_index.json is not "
                      f"declared in default.map's lakes block")
    for color in sorted(lake_colors - index_lake_colors):
        errors.append(f"lake colour {color_to_hex(color)} in default.map's lakes block is "
                      f"not a lake province in provinces_index.json")
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
                       min_cell_area: int = 4,
                       hub_anchors_index_path: Path | None = None,
                       province_terrains_path: Path | None = None,
                       terrain_defs_path: Path | None = None,
                       lake_mask_path: Path | None = None) -> list[str]:
    """Check the first-pass province bitmap tiles the mask exactly and agrees with
    its index and the committed sea-zone layer.

    ``lake_mask_path`` (#3742, optional): the inland-lake companion layer. When it
    (and/or a ``lake_provinces`` count in the index) is present, the bitmap is
    checked three-way — land / ocean (``~land & ~lake``) / lake — instead of the
    binary land/ocean tiling: lake labels occupy the band after the sea band, no
    province straddles two classes, the sea layer tiles the *navigable* water only,
    and the lake-labelled pixels equal the lake mask exactly. Absent lake mask
    **and** no lake cells → the two-class behaviour, byte-identical to before.

    ``hub_anchors_index_path`` (#3665, optional): the seeded hub provinces are
    deliberately kept small and are exempted from the avoidably-degenerate check 7
    (they were placed on purpose, like an archipelago); the hard <4px floor still
    applies to them.

    ``province_terrains_path`` / ``terrain_defs_path`` (#2968, optional): when the
    generated ``map_data/province_terrains.txt`` is present, check 8 verifies it is
    a bijection with the index colours and that every terrain id is defined in the
    mod's ``common/terrain``. The file is deliberately **deferred** (built by
    ``generate_province_terrains.py`` but not committed until the province cut
    settles), so its *absence* is the expected state and is not an error — the
    same convention as ``adjacencies.csv`` in ``_check_adjacencies``."""
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

    # Lake companion layer (#3742). Three-way tiling is active when the index
    # declares lake provinces and/or the companion mask exists; absent both, the
    # check is byte-identical to the two-class (land/ocean) path.
    n_lake = int(index.get("lake_provinces", 0))
    lake_mask = None
    if lake_mask_path is not None and lake_mask_path.is_file():
        lake_mask = _read_mask(lake_mask_path)
        if lake_mask.shape != land.shape:
            return [f"lake mask {lake_mask.shape} does not match the mask {land.shape}"]
    lakes_active = n_lake > 0 or lake_mask is not None
    if lakes_active and lake_mask is None:
        errors.append(f"index declares {n_lake} lake province(s) but no lake mask is present "
                      f"at {lake_mask_path}")
        lakes_active = False  # cannot verify three-way; the mismatch is already reported
    if lakes_active and int((lake_mask & land).sum()):
        errors.append(f"{int((lake_mask & land).sum()):,} lake-mask pixel(s) fall on land")
    # The three pixel classes. Ocean is the *navigable* water (all water minus
    # lakes); with no lakes it is just the water.
    lake_region = lake_mask if lakes_active else np.zeros(land.shape, dtype=bool)
    ocean_region = (~land & ~lake_region)

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

    # 2. No province straddles a class boundary (the mask stays authoritative). A
    #    province must be wholly land, wholly ocean, or wholly lake.
    land_ids = set(np.unique(labels[land]).tolist()) - {0}
    ocean_ids = set(np.unique(labels[ocean_region]).tolist()) - {0}
    lake_ids = set(np.unique(labels[lake_region]).tolist()) - {0} if lakes_active else set()
    for a, b, na, nb in ((land_ids, ocean_ids, "land", "ocean"),
                         (land_ids, lake_ids, "land", "lake"),
                         (ocean_ids, lake_ids, "ocean", "lake")):
        both = sorted(a & b)
        if both:
            errors.append(
                f"{len(both)} province(s) span {na} and {nb} (first few: {both[:5]}) — "
                f"a province must be wholly one class")
    # `sea_ids` (all water: ocean + lake) is what the connectivity/degeneracy
    # checks below key on for "not land".
    sea_ids = ocean_ids | lake_ids

    # 3. Land labels 1..n_land, sea labels n_land+1..n_land+n_sea, lake labels
    #    n_land+n_sea+1..n_land+n_sea+n_lake.
    for i in sorted(land_ids):
        if not (1 <= i <= n_land):
            errors.append(f"land pixel carries label {i}, outside the land band 1..{n_land}")
            break
    for i in sorted(ocean_ids):
        if not (n_land < i <= n_land + n_sea):
            errors.append(
                f"ocean pixel carries label {i}, outside the sea band "
                f"{n_land + 1}..{n_land + n_sea}")
            break
    for i in sorted(lake_ids):
        if not (n_land + n_sea < i <= n_land + n_sea + n_lake):
            errors.append(
                f"lake pixel carries label {i}, outside the lake band "
                f"{n_land + n_sea + 1}..{n_land + n_sea + n_lake}")
            break

    # 4. Index kinds/ids/areas agree with the raster.
    listed = {c["label"] for c in index["cells"]}
    present = land_ids | sea_ids
    for missing in sorted(present - listed)[:5]:
        errors.append(f"label {missing} is in the bitmap but not the index")
    for extra in sorted(listed - present)[:5]:
        errors.append(f"label {extra} is in the index but not the bitmap")
    for kind, declared in (("land", n_land), ("sea", n_sea), ("lake", n_lake)):
        actual = sum(1 for c in index["cells"] if c["kind"] == kind)
        if actual != declared:
            errors.append(f"index declares {declared} {kind} provinces but lists {actual}")
    total = n_land + n_sea + n_lake
    areas = np.bincount(labels.ravel(), minlength=total + 1)
    for c in index["cells"]:
        lab = int(c["label"])
        if lab <= total and int(areas[lab]) != int(c["area"]):
            errors.append(f"label {lab}: index says {c['area']} px, raster has {int(areas[lab])}")
            break
    # Id bands: land id = land_id_start + (label-1); sea id = sea_id_start +
    # (sea_index-1); lake id = lake_id_start + (lake_index-1).
    lid, sid = int(index["land_id_start"]), int(index["sea_id_start"])
    lkid = int(index.get("lake_id_start", n_land + n_sea + 1))
    for c in index["cells"]:
        lab = int(c["label"])
        if c["kind"] == "land":
            want = lid + (lab - 1)
        elif c["kind"] == "sea":
            want = sid + (lab - n_land - 1)
        else:  # lake
            want = lkid + (lab - n_land - n_sea - 1)
        if int(c["id"]) != want:
            errors.append(f"label {lab}: index id {c['id']} != expected {want} for a {c['kind']} province")
            break
    # Per-kind formula compliance is not enough — the land and sea bands must not
    # overlap. A province id is a globally-unique handle (vanilla definition.csv
    # shares one id space across land and sea), so a collision between a land and a
    # sea province is invalid content that would propagate downstream.
    ids = [int(c["id"]) for c in index["cells"]]
    if len(set(ids)) != len(ids):
        from collections import Counter
        dup = [i for i, n in Counter(ids).items() if n > 1]
        errors.append(
            f"{len(dup)} province id(s) are shared by more than one province — the "
            f"land and sea id bands overlap (first few: {sorted(dup)[:5]})")

    # 5. Every province is one connected region, UNLESS it's a deliberate
    # island-override archipelago (several islands merged under one label by
    # land_provinces.merge_island_overrides) — vanilla ships exactly this shape
    # (e.g. Micronesia's province colour spans 23 disconnected pixel blobs), so
    # a torn province is only an error when it isn't flagged as one.
    archipelago_labels = {int(c["label"]) for c in index["cells"] if c.get("archipelago")}
    comp = cells.components(labels, wrap_x)
    pairs = np.unique(np.stack([labels.ravel(), comp.ravel()], axis=1), axis=0)
    counts = np.bincount(pairs[:, 0].astype(np.int64), minlength=int(labels.max()) + 1)
    torn = set(np.flatnonzero(counts > 1).tolist()) - {0}
    unexpected = sorted(torn - archipelago_labels)
    if unexpected:
        errors.append(
            f"{len(unexpected)} province(s) are disconnected without being flagged "
            f"archipelago (first few: {unexpected[:5]})")
    stale_flags = sorted(archipelago_labels - torn)
    if stale_flags:
        errors.append(
            f"{len(stale_flags)} province(s) are flagged archipelago but are actually "
            f"contiguous (first few: {stale_flags[:5]})")

    # 6. The sea province count matches the committed sea-zone layer, and the sea
    #    layer tiles the *navigable* water (all water minus lakes) exactly.
    sea_lab = cells.read_labels(sea_labels_path)
    committed_sea = int(sea_lab.max())
    if committed_sea != n_sea:
        errors.append(
            f"index has {n_sea} sea provinces but {sea_labels_path.name} has {committed_sea}")
    if sea_lab.shape == land.shape and not bool(((sea_lab > 0) == ocean_region).all()):
        errors.append(f"{sea_labels_path.name} does not tile this mask's navigable water exactly")

    # 6b. Lake-labelled bitmap pixels equal the lake mask exactly (#3742). The
    #     lake labels are the band above the sea band; every one of their pixels
    #     must be a lake-mask pixel and vice-versa.
    if lakes_active:
        lake_pixels = (labels > n_land + n_sea) & (labels <= n_land + n_sea + n_lake)
        if not bool((lake_pixels == lake_region).all()):
            mism = int((lake_pixels != lake_region).sum())
            errors.append(
                f"{mism:,} pixel(s) disagree between the lake-labelled bitmap region and "
                f"the lake mask — lake provinces do not tile the lake mask exactly")

    # 7. No avoidably-degenerate LAND province: below the floor AND with a
    #    same-kind neighbour it could have merged into (a lone small island is
    #    legitimate). Restricted to land, which this generator subdivides and so
    #    controls; the sea provinces are a faithful 1:1 copy of the committed,
    #    separately-gated sea-zone layer (whose own policy deliberately keeps thin
    #    coastal inlets, merge_floor=1), and check 6 already ties their count to
    #    that layer — re-flagging them here would be a false positive this
    #    generator cannot fix without diverging from the sea layer.
    anchor_labels: set[int] = set()
    if hub_anchors_index_path is not None and hub_anchors_index_path.is_file():
        hub_index = json.loads(hub_anchors_index_path.read_text(encoding="utf-8"))
        anchor_labels = {int(h["province_label"]) for h in hub_index["hubs"]}
    tiny = [i for i in sorted(land_ids)
            if i > 0 and int(areas[i]) < int(min_cell_area) and i not in anchor_labels]
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

    # 8. province_terrains.txt bijection + valid terrain ids (#2968), when present.
    #    The file is deferred until the province cut settles, so absence is fine;
    #    when it IS there it must be a 1:1 map of the index colours to defined
    #    terrain ids. index<->PNG bijection is proven above, so terrain<->index
    #    plus index<->PNG gives terrain<->PNG in this one gate run.
    if province_terrains_path is not None and province_terrains_path.is_file():
        errors.extend(validate_province_terrains(
            index["cells"], province_terrains_path,
            terrain_defs_path or (REPO_ROOT / "common" / "terrain" / "01_terrain.txt")))
    return errors


_TERRAIN_LINE = re.compile(r'^\s*(x[0-9A-Fa-f]{6})\s*=\s*"([^"]+)"\s*$')
_TERRAIN_DEF = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{', re.MULTILINE)


def _terrain_ids(defs_path: Path) -> set[str]:
    """Top-level ``<id> = {`` keys from the mod's ``common/terrain`` file.

    ``common/terrain`` is in ``replace_paths``, so vanilla's terrain types do NOT
    load and only these ids are valid province-terrain values."""
    text = defs_path.read_text(encoding="utf-8-sig")
    # Only column-0 definitions are terrain types; nested ``weight = {`` etc. are
    # indented, so anchoring on a line start (no leading whitespace) excludes them.
    return {m.group(1) for m in _TERRAIN_DEF.finditer(text)
            if m.start() == 0 or text[m.start() - 1] == "\n"}


def validate_province_terrains(cells: list[dict], terrains_path: Path,
                               terrain_defs_path: Path) -> list[str]:
    """``province_terrains.txt`` is a bijection with the index colours, and every
    terrain value is a defined mod terrain id (board #2968).

    Pure over its inputs (cells + two files) so ``run_fixture.py`` can self-check
    it. Checks, in order: every line is well-formed; no hex appears twice; the set
    of file hexes equals the set of index hexes (nothing missing, nothing extra);
    every terrain id is defined in ``common/terrain``."""
    errors: list[str] = []
    valid_ids = _terrain_ids(terrain_defs_path)
    if not valid_ids:
        errors.append(f"{terrain_defs_path.name}: no terrain ids parsed — cannot validate terrains")
        return errors

    file_hexes: set[str] = set()
    dup_hexes: list[str] = []
    bad_ids: list[str] = []
    for i, raw in enumerate(terrains_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _TERRAIN_LINE.match(line)
        if not m:
            errors.append(f"province_terrains.txt line {i} is malformed: {line!r}")
            continue
        hexkey, terrain = m.group(1).upper(), m.group(2)
        if hexkey in file_hexes:
            dup_hexes.append(hexkey)
        file_hexes.add(hexkey)
        if terrain not in valid_ids:
            bad_ids.append(terrain)
    if dup_hexes:
        errors.append(f"{len(dup_hexes)} province colour(s) appear on more than one "
                      f"province_terrains.txt line (first few: {sorted(set(dup_hexes))[:5]})")
    if bad_ids:
        errors.append(f"{len(set(bad_ids))} terrain id(s) are not defined in "
                      f"{terrain_defs_path.name} (first few: {sorted(set(bad_ids))[:5]})")

    index_hexes = {c["hex"].upper() for c in cells}
    missing = index_hexes - file_hexes
    extra = file_hexes - index_hexes
    if missing:
        errors.append(f"{len(missing)} province colour(s) in the index have no "
                      f"province_terrains.txt line (first few: {sorted(missing)[:5]})")
    if extra:
        errors.append(f"{len(extra)} province_terrains.txt line(s) reference a colour "
                      f"absent from the index (first few: {sorted(extra)[:5]})")
    return errors


# ---------------------------------------------------------------------------
# The sea engine files (--sea)
# ---------------------------------------------------------------------------
#
# Board #2929 emits the sea side of the map (99_seas.txt + default.map sea_starts
# + water strategic regions) ahead of the land states, so the full no-flag
# validator cannot pass yet (it requires every province colour claimed). This is
# the sea-only subset: the colour chain that MUST hold for the seas to load —
# every 99_seas colour is a real provinces.png sea colour and is listed in
# sea_starts — plus the two cross-file invariants the game would otherwise only
# reveal as a load error (every sea state grouped into exactly one water strategic
# region; every sea state localized).

_REGION_HEADER = re.compile(r"(region_\w+)\s*=\s*\{")


def _parse_strategic_region_states(path: Path) -> dict[str, list[str]]:
    """Map each ``region_*`` key to the ``STATE_*`` keys in its ``states`` block."""
    text = path.read_text(encoding="utf-8-sig")
    out: dict[str, list[str]] = {}
    idx = 0
    while True:
        m = _REGION_HEADER.search(text, idx)
        if not m:
            break
        open_idx = text.index("{", m.end() - 1)
        close_idx = _match_braces(text, open_idx)
        body = text[open_idx + 1 : close_idx]
        states_block = _extract_block(body, "states")
        members = re.findall(r"STATE_\w+", states_block) if states_block else []
        out[m.group(1)] = members
        idx = close_idx + 1
    return out


ADJACENCIES_HEADER = (
    "From;To;Type;Through;start_x;start_y;stop_x;stop_y;adjacency_rule_name;Comment"
)


def _check_adjacencies(path: Path) -> list[str]:
    """adjacencies.csv must parse cleanly (board #3542).

    The engine reads every ``\\n``-separated line after the header as a data row,
    so a trailing newline after a header-only file makes an empty "line 2" that
    fails with ``map.cpp:264 Failed to read province string``. Vanilla ends the
    file at its last row with no trailing newline; a header-only file is the
    header line alone. Reject any empty line and any data row whose column count
    or first field is malformed."""
    errors: list[str] = []
    if not path.is_file():
        return errors  # header-only file is created by generate_sea_regions.py when absent
    text = path.read_text(encoding="utf-8-sig")
    lines = text.split("\n")
    ncols = ADJACENCIES_HEADER.count(";") + 1
    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip("\r")
        if i == 1:
            if line != ADJACENCIES_HEADER:
                errors.append(f"adjacencies.csv line 1 is not the expected header row")
            continue
        if line == "":
            errors.append(f"adjacencies.csv line {i} is blank - the engine reads it as a "
                          f"malformed data row (Failed to read province string)")
            continue
        if line.startswith("#"):
            continue
        fields = line.split(";")
        if len(fields) != ncols:
            errors.append(f"adjacencies.csv line {i} has {len(fields)} fields, expected {ncols}")
        elif fields[0].strip() == "":
            errors.append(f"adjacencies.csv line {i} has an empty From province id")
    return errors


def validate_sea(
    seas_txt_path: Path,
    default_map_path: Path,
    provinces_index_path: Path,
    strategic_regions_dir: Path,
    loc_dir: Path,
    adjacencies_path: Path | None = None,
) -> list[str]:
    """Sea-only subset check (board #2929) — the sea colour chain + cross-file invariants."""
    import json

    errors: list[str] = []
    for path in (seas_txt_path, default_map_path, provinces_index_path):
        if not path.is_file():
            errors.append(f"missing {path}")
    if errors:
        return errors

    sea_states = parse_state_file(seas_txt_path)
    if not sea_states:
        return [f"no sea states found in {seas_txt_path}"]

    from worldgen.raster import color_to_hex

    seas_colors: set[Color] = set()
    declared_impassable: set[Color] = set()
    for st in sea_states:
        seas_colors.update(st.provinces)
        declared_impassable.update(st.impassable)
        for color in st.impassable:
            if color not in st.provinces:
                errors.append(f"{st.key} ({st.filename}): impassable colour "
                              f"{color_to_hex(color)} is not one of its own provinces")

    dm_text = default_map_path.read_text(encoding="utf-8-sig")
    sea_starts = _parse_color_field(dm_text, "sea_starts")

    prov_index = json.loads(provinces_index_path.read_text(encoding="utf-8"))
    prov_sea_colors = {
        tuple(int(v) for v in c["color"])
        for c in prov_index["cells"] if c.get("kind") == "sea"
    }
    prov_impassable_colors = {
        tuple(int(v) for v in c["color"])
        for c in prov_index["cells"] if c.get("kind") == "sea" and c.get("impassable")
    }

    # 1. Every 99_seas colour is listed in default.map sea_starts.
    for color in sorted(seas_colors - sea_starts):
        errors.append(f"sea colour {color_to_hex(color)} in 99_seas.txt is absent from "
                      f"default.map sea_starts")
    # 2. No stray sea_starts colour that no sea state claims.
    for color in sorted(sea_starts - seas_colors):
        errors.append(f"sea colour {color_to_hex(color)} in default.map sea_starts is "
                      f"claimed by no state in 99_seas.txt")
    # 3. Every 99_seas colour is a real provinces.png sea colour.
    for color in sorted(seas_colors - prov_sea_colors):
        errors.append(f"sea colour {color_to_hex(color)} in 99_seas.txt is not a sea colour "
                      f"in provinces_index.json (absent from provinces.png)")
    # 3b. Impassable declarations agree between 99_seas.txt and provinces_index.json
    # (the 2026-08-22 "every zone passable" default stands, with the 2026-08-31
    # exceptions named in tools/config/sea_zones.json's merges/impassable_seeds).
    for color in sorted(declared_impassable - prov_impassable_colors):
        errors.append(f"sea colour {color_to_hex(color)} declared impassable in 99_seas.txt "
                      f"but not flagged impassable in provinces_index.json")
    for color in sorted(prov_impassable_colors - declared_impassable):
        errors.append(f"sea colour {color_to_hex(color)} flagged impassable in "
                      f"provinces_index.json but not declared impassable in 99_seas.txt")

    # 4. Every sea state is in exactly one water strategic region.
    region_map: dict[str, list[str]] = {}
    wsr_path = strategic_regions_dir / "water_strategic_regions.txt"
    if not wsr_path.is_file():
        errors.append(f"missing {wsr_path}")
    else:
        region_map = _parse_strategic_region_states(wsr_path)
    membership: dict[str, list[str]] = {}
    for region, members in region_map.items():
        for state in members:
            membership.setdefault(state, []).append(region)
    for st in sorted(sea_states, key=lambda s: s.key):
        regions = membership.get(st.key, [])
        if not regions:
            errors.append(f"{st.key}: not assigned to any water strategic region")
        elif len(regions) > 1:
            errors.append(f"{st.key}: assigned to multiple water strategic regions: "
                          f"{', '.join(regions)}")

    # 5. Every sea state is localized.
    loc_keys = _parse_loc_keys(loc_dir)
    for st in sorted(sea_states, key=lambda s: s.key):
        if st.key not in loc_keys:
            errors.append(f"{st.key}: no localization entry under {loc_dir}")

    # 6. adjacencies.csv parses cleanly (board #3542).
    if adjacencies_path is not None:
        errors.extend(_check_adjacencies(adjacencies_path))

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
    p.add_argument("--sea", action="store_true",
                   help="lint the sea engine files only (99_seas + sea_starts + water regions + loc)")
    p.add_argument("--labels-path", type=Path, help="path to state_labels.png")
    p.add_argument("--sea-labels-path", type=Path, help="path to sea_zones.png")
    p.add_argument("--mask-path", type=Path, help="path to land_sea_mask.png")
    p.add_argument("--lake-mask-path", type=Path,
                   help="path to the inland-lake companion mask (default derived/lake_mask.png)")
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
            hub_anchors_index_path=derived / "hub_anchors_index.json",
            province_terrains_path=REPO_ROOT / "map_data" / "province_terrains.txt",
            terrain_defs_path=REPO_ROOT / "common" / "terrain" / "01_terrain.txt",
            lake_mask_path=args.lake_mask_path or derived / "lake_mask.png",
        )
        if errors:
            print(f"validate_map --province-bitmap: {len(errors)} error(s):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print("validate_map --province-bitmap: the province bitmap tiles the mask and agrees "
              "with its index + the sea layer.")
        return 0

    if args.sea:
        derived = TOOLS_DIR / "derived"
        errors = validate_sea(
            seas_txt_path=(args.state_regions or REPO_ROOT / "map_data" / "state_regions")
            / "99_seas.txt",
            default_map_path=args.default_map or REPO_ROOT / "map_data" / "default.map",
            provinces_index_path=args.index_path or derived / "provinces_index.json",
            strategic_regions_dir=REPO_ROOT / "common" / "strategic_regions",
            loc_dir=args.loc_dir or REPO_ROOT / "localization" / "english" / "map",
            adjacencies_path=REPO_ROOT / "map_data" / "adjacencies.csv",
        )
        if errors:
            print(f"validate_map --sea: {len(errors)} error(s):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print("validate_map --sea: 99_seas colours are all in sea_starts and are real "
              "provinces.png sea colours; every sea state grouped and localized.")
        return 0

    paths = _resolve_paths(args)
    errors = validate(
        provinces_path=paths["provinces"],
        state_regions_dir=paths["state_regions"],
        default_map_path=paths["default_map"],
        loc_dir=paths["loc_dir"],
        min_province_area=args.min_province_area,
        wrap_x=map_config.WRAP_X,
        provinces_index_path=None if args.fixture else
        (args.index_path or TOOLS_DIR / "derived" / "provinces_index.json"),
        hub_anchors_index_path=None if args.fixture else
        (TOOLS_DIR / "derived" / "hub_anchors_index.json"),
        rivers_path=None if args.fixture else REPO_ROOT / "map_data" / "rivers.png",
        rivers_mask_path=None if args.fixture else TOOLS_DIR / "derived" / "land_sea_mask.png",
        canon_river_names_path=None if args.fixture else
        TOOLS_DIR / "config" / "canon_river_names.json",
        canon_rivers_csv_path=None if args.fixture else TOOLS_DIR / "config" / "canon_rivers.csv",
        rivers_index_path=None if args.fixture else TOOLS_DIR / "derived" / "rivers_index.json",
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
