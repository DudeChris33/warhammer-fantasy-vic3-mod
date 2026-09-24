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
from worldgen import sources  # noqa: E402
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

# The impassable-terrain paint colour (board #3789). Measured on the real export
# (sources/gimp_exports/terraqueous_globe_reprojected - impassable_terrain.png,
# 2026-09-08, before board #5399 moved the layer into
# terraqueous_globe_reprojected - full.ora#impassable): 641,982 pixels are
# exactly (255,127,0), zero anti-aliased fringe, fully opaque — a clean
# flat-fill layer, the same idiom as the magenta state network and blue rivers.
# A future paint-colour change is a one-line edit here.
from worldgen.land_provinces import IMPASSABLE_RGB  # noqa: E402  (single home, #3704)

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

    def adjacent_pairs(self) -> set[tuple[Color, Color]]:
        """Every unordered pair of distinct province colours sharing a pixel edge
        (4-neighbourhood; x wraps when ``wrap_x``, y never). Computed once."""
        cached = getattr(self, "_adj", None)
        if cached is not None:
            return cached
        code = self._code
        parts = [(code[:, :-1], code[:, 1:]), (code[:-1, :], code[1:, :])]
        if self.wrap_x:
            parts.append((code[:, -1:], code[:, :1]))
        pairs: set[int] = set()
        for a, b in parts:
            diff = a != b
            lo = np.minimum(a[diff], b[diff]).astype(np.uint64)
            hi = np.maximum(a[diff], b[diff]).astype(np.uint64)
            pairs.update(np.unique((lo << np.uint64(24)) | hi).tolist())

        def col(c: int) -> Color:
            return ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)

        self._adj = {(col(p >> 24), col(p & 0xFFFFFF)) for p in pairs}
        return self._adj

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
    canon_cities_path: Path | None = None,
    canon_cities_mask_path: Path | None = None,
    impassable_ref: str | None = None,
    canon_city_provinces_index_path: Path | None = None,
    adjacencies_path: Path | None = None,
    extra_loc_dirs: tuple[Path, ...] = (),
    warnings: list[str] | None = None,
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
    index_cells: list[dict] | None = None
    if provinces_index_path is not None and provinces_index_path.is_file():
        import json

        prov_index = json.loads(provinces_index_path.read_text(encoding="utf-8"))
        archipelago_colors = {
            tuple(c["color"]) for c in prov_index["cells"] if c.get("archipelago")
        }
        index_cells = prov_index["cells"]
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
        if index_cells is not None:
            errors += _check_world_market_location(
                REPO_ROOT / "common" / "defines", index_cells, sea_colors)
        if index_cells is not None:
            city_index = None
            if (canon_city_provinces_index_path is not None
                    and canon_city_provinces_index_path.is_file()):
                import json

                city_index = json.loads(
                    canon_city_provinces_index_path.read_text(encoding="utf-8"))
            errors += _check_impassable_land(
                bitmap, land_states, index_cells, city_index,
                _parse_adjacency_edges(adjacencies_path))
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

    # Canon barrier cities (#3789): gated on the catalogue existing (clean skip
    # when absent, the _check_adjacencies idiom). Runs off the committed
    # land_sea_mask.png alone — independent of the province bitmap (which is still
    # churning, #3663/#3664/#3705) — so a stale/absent provinces.png never blocks
    # or corrupts the on-land check. The on-land half always runs (mask committed);
    # the impassable-collision half degrades to a skip when the gitignored .ora
    # (or its impassable layer) is absent or empty (CI / other devices, or before
    # Chris's re-export), so the committed gate never breaks.
    if (canon_cities_path is not None and canon_cities_path.is_file()
            and canon_cities_mask_path is not None and canon_cities_mask_path.is_file()):
        from worldgen import schema

        land_mask = _read_mask(canon_cities_mask_path)
        h, w = land_mask.shape[:2]
        cities = schema.load_canon_cities(canon_cities_path, canvas=(w, h))
        impassable_rgb = None
        if impassable_ref is not None:
            try:
                impassable_rgba = sources.read_source_rgba(impassable_ref, allow_empty=True)
            except sources.OraError as exc:
                impassable_rgba = None
                if warnings is not None:
                    warnings.append(
                        f"impassable layer '{impassable_ref}' missing/empty — "
                        f"collision check skipped ({exc})"
                    )
            if impassable_rgba is not None:
                if bool((impassable_rgba[..., 3] > 0).any()):
                    impassable_rgb = impassable_rgba[..., :3]
                elif warnings is not None:
                    warnings.append(
                        f"impassable layer '{impassable_ref}' missing/empty — collision check skipped"
                    )
        cc_errors, cc_warnings = _check_canon_cities(cities, land_mask, impassable_rgb)
        errors += cc_errors
        if warnings is not None:
            warnings.extend(cc_warnings)

    errors += _check_loc_coverage(states, loc_dir, extra_loc_dirs)
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


def _parse_adjacency_edges(path: Path | None) -> set[frozenset]:
    """Province-colour pairs joined by ``adjacencies.csv`` rows (tunnels/straits).
    A row's From/To are ``x<HEX>`` province colours; anything else is ignored."""
    edges: set[frozenset] = set()
    if path is None or not path.is_file():
        return edges
    for line in path.read_text(encoding="utf-8-sig").splitlines()[1:]:
        cols = line.split(";")
        if len(cols) < 2:
            continue
        a, b = (_COLOR_TOKEN.fullmatch(c.strip()) for c in cols[:2])
        if a and b:
            ca = tuple(int(a.group()[i:i + 2], 16) for i in (1, 3, 5))
            cb = tuple(int(b.group()[i:i + 2], 16) for i in (1, 3, 5))
            edges.add(frozenset((ca, cb)))
    return edges


def _check_impassable_land(bitmap: "ProvinceBitmap", land_states: list[ParsedState],
                           index_cells: list[dict], city_index: dict | None,
                           adj_edges: set[frozenset]) -> list[str]:
    """Land-side impassable checks (#3704), mirroring the sea side. Clean skip when
    no land province is impassable. For every land state:

    * its ``impassable`` colours are a subset of its own provinces;
    * they agree with ``provinces_index.json`` (both directions);
    * it is not wholly impassable;
    * its PASSABLE provinces form one connected component over pixel adjacency
      (wrap-aware) plus ``adjacencies.csv`` special-connection rows;
    * every canon city (``canon_city_provinces_index.json``) sits in a passable
      province in that state's main component - an enclosed city is a blocking
      error naming the city.

    Out-of-scope placeholder states are passable (``placeholder`` is a separate flag)
    and never trip any of this.
    """
    from worldgen.raster import color_to_hex

    idx_imp = {tuple(int(v) for v in c["color"]) for c in index_cells
               if c.get("kind") == "land" and c.get("impassable")}
    if not idx_imp and not any(st.impassable for st in land_states):
        return []
    errors: list[str] = []
    adj = bitmap.adjacent_pairs()
    nbrs: dict[Color, set[Color]] = {}
    for a, b in adj:
        nbrs.setdefault(a, set()).add(b)
        nbrs.setdefault(b, set()).add(a)
    for e in adj_edges:
        a, b = tuple(e)
        nbrs.setdefault(a, set()).add(b)
        nbrs.setdefault(b, set()).add(a)

    claimed_imp: set[Color] = set()
    main_component: set[Color] = set()  # passable colours in their state's main component
    state_of: dict[Color, ParsedState] = {}
    for st in land_states:
        own = set(st.provinces)
        imp = set(st.impassable)
        claimed_imp |= imp
        for col in own:
            state_of[col] = st
        if not imp <= own:
            errors.append(f"{st.key} ({st.filename}): impassable "
                          f"{sorted(color_to_hex(c) for c in imp - own)} not among its provinces")
        want = {c for c in own if c in idx_imp}
        if imp != want:
            errors.append(
                f"{st.key} ({st.filename}): impassable list disagrees with "
                f"provinces_index.json ({sorted(color_to_hex(c) for c in imp ^ want)})")
        passable = own - imp
        if own and not passable:
            errors.append(f"{st.key} ({st.filename}): every province is impassable")
            continue
        if not imp:
            main_component |= passable
            continue
        def _components(nodes: set[Color]) -> list[set[Color]]:
            seen: set[Color] = set()
            out: list[set[Color]] = []
            for start in sorted(nodes):
                if start in seen:
                    continue
                comp, stack = set(), [start]
                while stack:
                    c = stack.pop()
                    if c in comp:
                        continue
                    comp.add(c)
                    stack.extend(n for n in nbrs.get(c, ()) if n in nodes and n not in comp)
                seen |= comp
                out.append(comp)
            return out

        # Only paint may disconnect: land that was already apart before the paint
        # (islands, an archipelago, a merge-fused region's separate landmasses) is
        # not this check's business. So take the components of ALL the state's
        # provinces, and require the passable ones inside each to stay connected.
        for full in _components(own):
            sub = _components(full & passable)
            if not sub:
                continue
            sub.sort(key=lambda cs: (-sum(bitmap.area.get(c, 0) for c in cs), min(cs)))
            if len(sub) > 1:
                def _at(cs: set[Color]) -> str:
                    px = bitmap.pixels[min(cs)]
                    return f"({px[0][0]}, {px[0][1]})"
                errors.append(
                    f"{st.key} ({st.filename}): passable land is split into {len(sub)} "
                    f"disconnected components (cut-off pieces near "
                    f"{', '.join(_at(c) for c in sub[1:4])}"
                    f"{', ...' if len(sub) > 4 else ''}) - leave a gap in the paint or "
                    f"add an adjacencies.csv tunnel row")
            main_component |= sub[0]
            # pieces of a full component that were only ever passable-adjacent to it
            # are covered above; a passable province outside every ``sub[0]`` is
            # what the city check reads as "sealed".
    stray = idx_imp - claimed_imp
    if stray:
        errors.append(f"provinces_index.json marks {len(stray)} land province(s) impassable "
                      f"that no state declares (first {color_to_hex(sorted(stray)[0])})")

    for c in (city_index or {}).get("cities", []):
        hexc = c.get("province_hex")
        name = c["name"]
        if not hexc:
            errors.append(f"canon city '{name}': anchor resolves to no land province")
            continue
        col = tuple(int(hexc[i:i + 2], 16) for i in (1, 3, 5))
        if c.get("impassable") or col in idx_imp:
            errors.append(f"canon city '{name}' sits in an impassable province - "
                          f"paint a pocket clear or move the anchor")
        elif col in state_of and col not in main_component:
            errors.append(f"canon city '{name}' is enclosed by impassable paint with no "
                          f"path or tunnel - carve a path or add a tunnel row for {name}")
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
                  ocean: np.ndarray | None = None,
                  canon_rivers_csv: list[tuple[str, str]] | None = None,
                  rivers_index: dict | None = None) -> list[str]:
    """Validate a committed ``rivers.png`` index array against the vanilla model.

    Mirrors the invariants ``worldgen.rivers._validate`` enforces before writing,
    re-checked here on the committed bitmap (defense in depth — the offline gate in
    testing.md). ``ocean`` (board #3742) is the navigable-sea mask; a source may
    sit on a lake shore but never on the ocean. Absent, it defaults to ``~land`` (all
    water is ocean). Returns a list of error strings (empty == clean):

    * every index is in the vanilla semantic set (incl. the yellow split marker 2);
    * no river pixel sits on sea (land mask is the authority);
    * every green source (0) is clear of the ocean (inland or lake-fed);
    * every red merge (1) and yellow split (2) touches another river pixel;
    * the 2×2-block caps ``worldgen.rivers`` calibrated on vanilla; and
    * when ``canon_rivers.csv`` (#3677) exists, every ``(river, state_key)`` row
      names a river whose ``rivers_index.json`` state coverage includes that state
      (a **warning**, not a hard error).

    An endorheic river (board #3703/#3742) legitimately ends inland with no water
    and no marker, so there is no "a mouth must touch water" check here — the
    generator's own ``_validate`` owns the source→mouth topology; this pass only
    re-checks the pixel-level invariants that survive on the bare bitmap.
    """
    from worldgen.rivers import MAX_2X2_BLOCKS, MAX_2X2_RUN, measure_2x2_blocks

    errors: list[str] = []
    if idx.shape != land_mask.shape:
        return [f"rivers.png {idx.shape} and land mask {land_mask.shape} differ in size"]
    h, w = idx.shape
    if ocean is None:
        ocean = ~land_mask

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

    # Source (0) clear of the ocean (a lake shore is allowed — a lake-fed spring).
    for (yy, xx) in zip(*np.nonzero(idx == _RIVER_SOURCE)):
        if any(ocean[ny, nx] for ny, nx in _neighbors8(int(yy), int(xx), h, w, wrap_x)):
            errors.append(f"river source ({int(xx)}, {int(yy)}) is on the sea coast; "
                          f"sources must be inland or lake-fed")
            break
    # Merge (1, red) and split (2, yellow) markers each touch another river pixel.
    for marker, label in ((_RIVER_MERGE, "merge"), (2, "split")):
        for (yy, xx) in zip(*np.nonzero(idx == marker)):
            if not any(river[ny, nx] for ny, nx in _neighbors8(int(yy), int(xx), h, w, wrap_x)
                       if (ny, nx) != (int(yy), int(xx))):
                errors.append(f"river {label} marker ({int(xx)}, {int(yy)}) touches no other stream")
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


def _check_world_market_location(defines_dir: Path, cells: list[dict],
                                 sea_colors: set[Color]) -> list[str]:
    """``WORLD_MARKET_LOCATION`` (hand-authored in common/defines) must name a
    passable, non-lake sea province present in the index and in ``sea_starts``
    (board #5520). Vanilla's value is an old-map colour; a dangling one is a load
    error/crash. Clean skip when no defines file sets it."""
    import re

    from worldgen.raster import color_to_hex

    value = None
    if defines_dir.is_dir():
        for f in sorted(defines_dir.glob("*.txt")):
            m = re.search(r'^\s*WORLD_MARKET_LOCATION\s*=\s*"x([0-9A-Fa-f]{6})"',
                          f.read_text(encoding="utf-8-sig"), re.M)
            if m:
                value = m.group(1).upper()
    if value is None:
        return []
    color = tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    hexname = f"x{value}"
    cell = next((c for c in cells if tuple(int(v) for v in c["color"]) == color), None)
    if cell is None:
        return [f"WORLD_MARKET_LOCATION {hexname} is not a province in provinces_index.json"]
    errors = []
    if cell.get("kind") != "sea":
        errors.append(f"WORLD_MARKET_LOCATION {hexname} is a {cell.get('kind')} province, not sea")
    if cell.get("impassable"):
        errors.append(f"WORLD_MARKET_LOCATION {hexname} is impassable")
    if color not in sea_colors:
        errors.append(f"WORLD_MARKET_LOCATION {hexname} is not in default.map sea_starts")
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


def _warn_lakes_oversized(cells: list[dict], warn_fraction: float) -> list[str]:
    """Board #3742 Phase B — the sealed-strait guard, re-surfaced off the committed
    index as a **non-blocking WARNING** (the caller keeps these out of the error
    list; see :func:`validate_provinces`' ``warnings`` accumulator).

    ``lakes.classify`` warns at generation time when an inland lake exceeds
    ``OCEAN_WARN_FRACTION`` of the world ocean — a navigable sea a hand-drawn fill
    may have sealed off — but that warning lives only in
    ``generate_coastline_mask.py`` stdout and is trivially missed. This recomputes
    the same ratio independently from the index (so a stale/wrong persisted
    ``ocean_area_fraction`` cannot hide it): the world ocean is the navigable water,
    which the sea provinces tile exactly, so its area is the sum of the sea province
    areas — the very quantity ``classify`` measured. Stays a warning, never an
    error: a legitimately large lake may exist and the render is the final gate.
    Empty when there are no lake cells (dormant — byte-identical to a no-lake map).
    """
    lake_cells = [c for c in cells if c.get("kind") == "lake"]
    if not lake_cells or warn_fraction <= 0:
        return []
    ocean_area = sum(int(c["area"]) for c in cells if c.get("kind") == "sea")
    if ocean_area <= 0:
        return []
    warnings: list[str] = []
    for c in lake_cells:
        area = int(c["area"])
        frac = area / ocean_area
        if frac > warn_fraction:
            warnings.append(
                f"lake province {c['hex']} is {area:,} px, {frac:.1%} of the world ocean "
                f"({ocean_area:,} px) — over the {warn_fraction:.1%} guard; a navigable sea "
                f"may have been sealed off from the ocean by the fill. Verify on the "
                f"rendered map.")
    return warnings


def _warn_lakes_degenerate(cells: list[dict], report_min: int) -> list[str]:
    """Board #3742 Phase B — the junk-lake report, off the committed index, as a
    **non-blocking WARNING** (kept out of the error list by the caller).

    ``lakes.label`` gives every non-ocean water component its own province with no
    size floor — unlike sea zones or the land degeneracy sweep — so a noisy fill
    (anti-alias speckle, dust) can mint dozens of junk micro-lakes that clear the
    hard ≥ ``min_cell_area`` floor and so pass ``validate_provinces``' land-only
    check 7 silently. This surfaces every lake below ``report_min`` (mirroring
    ``generate_coastline_mask._REPORT_MIN`` — a reporting floor, not a masking one).
    The remedy is drop-or-redraw the fill, never merge: an enclosed speck has no
    lake neighbour to merge into. Warning, not error, and empty when there are no
    lake cells (dormant)."""
    if report_min <= 0:
        return []
    tiny = sorted((int(c["area"]), c["hex"]) for c in cells
                  if c.get("kind") == "lake" and int(c["area"]) < report_min)
    if not tiny:
        return []
    smallest_area, smallest_hex = tiny[0]
    return [
        f"{len(tiny)} lake province(s) are below the {report_min:,} px report floor "
        f"(smallest {smallest_hex} at {smallest_area:,} px) — check these aren't fill "
        f"speckle/dust rather than real lakes (lakes are never merged, only kept or "
        f"redrawn). Verify on the rendered map."]


def _check_loc_coverage(states: list[ParsedState], loc_dir: Path,
                        extra_loc_dirs: tuple[Path, ...] = ()) -> list[str]:
    """A state's key must be defined somewhere across ``loc_dir`` plus any
    ``extra_loc_dirs`` — a key can live in ``localization/replace/english/``
    instead of ``localization/english/`` when it deliberately overrides a
    vanilla key (board #2931 — an Old-World region name can coincide with a
    real-world vanilla state name; the mod's own loc then lives in the
    replace/ folder so it overrides vanilla's matching key rather than
    duplicate-key-erroring against it)."""
    errors = []
    loc_keys = _parse_loc_keys(loc_dir)
    for extra in extra_loc_dirs:
        loc_keys |= _parse_loc_keys(extra)
    all_dirs = ", ".join(str(d) for d in (loc_dir, *extra_loc_dirs))
    for st in sorted(states, key=lambda s: s.key):
        if st.key not in loc_keys:
            errors.append(f"{st.key}: no localization entry under {all_dirs}")
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
                       lake_mask_path: Path | None = None,
                       warnings: list[str] | None = None) -> list[str]:
    """Check the first-pass province bitmap tiles the mask exactly and agrees with
    its index and the committed sea-zone layer.

    Province **ids** are stable, gap-tolerant handles (board #3705), not
    raster-order ordinals: ``generate_provinces.py`` carries a geometry-unchanged
    province's committed colour+id across a regen. So this checks the id structure
    — positive, globally unique, a bijection with the colour key, and (when the
    header carries it) bounded by the monotonic ``id_high_water`` — rather than the
    retired per-kind ``id == *_id_start + (label-1)`` formula. The internal
    ``label`` bands stay contiguous (check 3) and are unaffected.

    ``lake_mask_path`` (#3742, optional): the inland-lake companion layer. When it
    (and/or a ``lake_provinces`` count in the index) is present, the bitmap is
    checked three-way — land / ocean (``~land & ~lake``) / lake — instead of the
    binary land/ocean tiling: lake labels occupy the band after the sea band, no
    province straddles two classes, the sea layer tiles the *navigable* water only,
    and the lake-labelled pixels equal the lake mask exactly. Absent lake mask
    **and** no lake cells → the two-class behaviour, byte-identical to before.

    ``warnings`` (#3742 Phase B, optional): a caller-owned accumulator for
    **non-blocking** lake advisories that must not gate the exit code — the
    sealed-strait guard (:func:`_warn_lakes_oversized`) and the junk-lake report
    (:func:`_warn_lakes_degenerate`). Kept separate from the returned error list on
    purpose: a legitimately large or small lake may exist and the render is the
    final gate, so these inform without failing. Pass ``None`` (every caller but the
    ``--province-bitmap`` CLI and its self-check) and they are not even computed —
    behaviour is byte-identical to before the parameter existed.

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
    # Province ids: a stable, gap-tolerant handle (board #3705), no longer a
    # raster-order ordinal — so the old per-kind `id == *_id_start + (label-1)`
    # formula is gone (it was the exact thing that made ids reshuffle on any
    # add/remove/reshape). What must still hold is structural: every id is a
    # positive integer; ids are globally unique (one id space across land+sea+lake,
    # as vanilla's definition.csv is); the (colour, id) pairing is a bijection over
    # the cells (colour is the real key, id follows it 1:1); and, when the header
    # carries the monotonic high-water, no id runs past it.
    ids = [int(c["id"]) for c in index["cells"]]
    nonpos = sorted({i for i in ids if i <= 0})
    if nonpos:
        errors.append(f"{len(nonpos)} province id(s) are not positive (first few: {nonpos[:5]})")
    if len(set(ids)) != len(ids):
        from collections import Counter
        dup = [i for i, n in Counter(ids).items() if n > 1]
        errors.append(
            f"{len(dup)} province id(s) are shared by more than one province "
            f"(first few: {sorted(dup)[:5]})")
    # colour ↔ id bijection: colour uniqueness is checked above (dup_colors); here
    # confirm the two keys are in lockstep — as many distinct ids as distinct
    # colours as cells, so neither key is many-to-one against the other.
    n_cells = len(index["cells"])
    n_colors = len({(int(c["color"][0]), int(c["color"][1]), int(c["color"][2]))
                    for c in index["cells"]})
    if not (len(set(ids)) == n_colors == n_cells):
        errors.append(
            f"colour↔id is not a bijection over the index: {n_cells} cells, "
            f"{n_colors} distinct colours, {len(set(ids))} distinct ids")
    if "id_high_water" in index:
        hw = int(index["id_high_water"])
        over = sorted({i for i in ids if i >= hw})
        if over:
            errors.append(
                f"{len(over)} province id(s) are >= id_high_water {hw} — the high-water "
                f"must be the next UNUSED id (first few: {over[:5]})")

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

    # Non-blocking lake advisories (#3742 Phase B). Collected into the caller's
    # `warnings` list, never `errors`, so they surface without gating the exit
    # code. Both no-op when there are no lake cells, so a lake-free map is
    # byte-identical to before this existed.
    if warnings is not None:
        from worldgen.lakes import LAKE_REPORT_MIN, OCEAN_WARN_FRACTION

        warnings += _warn_lakes_oversized(index["cells"], OCEAN_WARN_FRACTION)
        warnings += _warn_lakes_degenerate(index["cells"], LAKE_REPORT_MIN)
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


def _check_canon_cities(cities, land_mask: np.ndarray,
                        impassable_rgb: np.ndarray | None) -> tuple[list[str], list[str]]:
    """Barrier-city safety check (board #3789, parent #3788).

    Returns ``(errors, warnings)``. ``cities`` is a list of
    :class:`worldgen.schema.CanonCity`. For each city:

    (i) **on-land — a hard ERROR.** Its anchor must be land in the committed
        ``land_sea_mask.png`` (``land_mask[y, x]`` truthy; the mask reads
        ``True == land``). A city on water is a mis-typed anchor and fails the gate
        on every device (the mask is committed).
    (ii) **impassable collision — a non-blocking WARNING.** When ``impassable_rgb``
        is provided (the local gitignored gimp export is present), a city whose
        anchor pixel reads :data:`IMPASSABLE_RGB` is *reported* but never fails the
        gate: a catalogued hold sitting in the mountains is EXPECTED — that is the
        whole point of the catalogue — and the warning is the signal for the user
        to carve a passable pocket around it (the transparent overlay is the tool
        for that). Blocking here would redden the gate the moment a hold is placed
        correctly in the range. Same non-blocking `warnings=` convention as the
        lake content-integrity guards (#3742 Phase B); the render stays the final
        verdict. Absent the export (CI / other devices) this half is skipped by the
        caller (``impassable_rgb is None``).

    Anchor bounds are already guaranteed in-canvas by the schema's canvas check, but
    every index is guarded defensively here so a stale mask/array size can never
    raise.
    """
    errors: list[str] = []
    warnings: list[str] = []
    h, w = land_mask.shape[:2]
    for c in cities:
        x, y = int(c.anchor[0]), int(c.anchor[1])
        if not (0 <= x < w and 0 <= y < h):
            errors.append(f"canon city '{c.name}' anchor ({x},{y}) is outside the "
                          f"{w}x{h} land mask")
            continue
        if not bool(land_mask[y, x]):
            errors.append(f"canon city '{c.name}' anchor ({x},{y}) is on water "
                          f"(not land in land_sea_mask.png)")
        if impassable_rgb is not None:
            ih, iw = impassable_rgb.shape[:2]
            if 0 <= x < iw and 0 <= y < ih and tuple(
                    int(v) for v in impassable_rgb[y, x][:3]) == IMPASSABLE_RGB:
                warnings.append(f"canon city '{c.name}' ({x},{y}) terrain={c.terrain} "
                                f"is painted impassable — carve a passable pocket "
                                f"around it or it will be sealed out of the map")
    return errors, warnings


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
        warnings: list[str] = []
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
            warnings=warnings,
        )
        # Warnings are advisory (#3742 Phase B) — printed whether the gate passes or
        # fails, but they never gate the exit code (a legit large/small lake may
        # exist; the render is the final gate).
        for w in warnings:
            print(f"  ! WARNING: {w}", file=sys.stderr)
        if errors:
            print(f"validate_map --province-bitmap: {len(errors)} error(s):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        msg = ("validate_map --province-bitmap: the province bitmap tiles the mask and agrees "
               "with its index + the sea layer.")
        if warnings:
            msg += f" ({len(warnings)} non-blocking lake warning(s) above)"
        print(msg)
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
    warnings: list[str] = []
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
        canon_cities_path=None if args.fixture else TOOLS_DIR / "config" / "canon_cities.json",
        canon_cities_mask_path=None if args.fixture else TOOLS_DIR / "derived" / "land_sea_mask.png",
        impassable_ref=None if args.fixture else sources.source_ref("impassable"),
        canon_city_provinces_index_path=None if args.fixture else
        TOOLS_DIR / "derived" / "canon_city_provinces_index.json",
        adjacencies_path=None if args.fixture else REPO_ROOT / "map_data" / "adjacencies.csv",
        extra_loc_dirs=() if args.fixture else
        (REPO_ROOT / "localization" / "replace" / "english" / "map",),
        warnings=warnings,
    )
    # Warnings are advisory (canon-city impassable collisions, #3789) — printed
    # whether the gate passes or fails, but never gating the exit code: a hold in
    # the mountains is expected, and the warning is the cue to carve a passable
    # pocket around it (see _check_canon_cities). Same convention as the province
    # bitmap's lake warnings.
    for w in warnings:
        print(f"  ! WARNING: {w}", file=sys.stderr)
    if errors:
        print(f"validate_map: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    msg = "validate_map: all checks passed."
    if warnings:
        msg += f" ({len(warnings)} non-blocking canon-city warning(s) above)"
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
