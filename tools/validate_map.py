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
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fixture", action="store_true", help="lint tools/fixtures/expected/ instead of the repo map")
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
