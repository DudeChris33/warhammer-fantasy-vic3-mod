#!/usr/bin/env python3
"""Emit the real sea engine files the game loads, from the canon index + province colours.

Board #2929 (bootable-map milestone #2700). This is the pass that turns the
finished, canon-named ocean zones into loadable ``map_data`` / ``common`` content.
It reads two committed indices and joins them:

* ``tools/derived/sea_zones_index.json`` — the canon per-zone ``key`` / ``id`` /
  ``display_name`` / ``sea_group`` (board #2698).
* ``tools/derived/provinces_index.json`` — the **colour authority**: the actual
  ``xRRGGBB`` each sea province carries in ``map_data/provinces.png`` (board #2773).

**Colour join (critical).** Earlier this generator allocated its *own* province
colours with a fresh ``ColorAllocator`` — those never matched ``provinces.png``
(measured 2026-08-24: 0/201 overlap), so promoting them would have referenced
absent colours and failed to load. The colour now comes straight from
``provinces_index.json``: sea-zone label ``s`` maps to the province cell with
``label == land_provinces + s`` (the sea provinces are appended after the
``land_provinces`` land provinces, in ascending sea-zone-label order). The join is
label arithmetic, asserted complete and ``kind == "sea"`` with matching area.

Writes (all deterministic — pure functions of the two committed indices):

* ``localization/english/map/wh_seas_l_english.yml`` — the canon sea loc (BOM,
  ``l_english:`` header, one ``KEY:0 "Display"`` per zone). Unchanged behaviour.
* ``map_data/state_regions/99_seas.txt`` — one passable single-province
  ``STATE_* { id provinces }`` block per zone (no ``impassable`` — 2026-08-22
  decision). Colours from ``provinces.png``, ids/keys from the canon index.
* ``map_data/default.map`` — in-place block-replace of only the ``sea_starts``
  body with the 201 sea colours; every other key is left byte-for-byte untouched.
* ``common/strategic_regions/water_strategic_regions.txt`` — one ``states``-only
  region per canon ``sea_group`` (filename overrides vanilla's dangling file).
* ``map_data/adjacencies.csv`` — created header-only when absent (fixes the
  ``default.map`` reference); strait/canal pairs are a user-driven follow-up
  against the rendered map, so an existing authored file is left untouched.

Run ``generate_sea_zones.py`` and ``generate_provinces.py`` first (they write the
two indices this reads).

Usage::

    python tools/generate_sea_regions.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import raster  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
MOD_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
INDEX_PATH = DERIVED_DIR / "sea_zones_index.json"
PROVINCES_INDEX_PATH = DERIVED_DIR / "provinces_index.json"

LOC_DIR = MOD_ROOT / "localization" / "english" / "map"
LOC_PATH = LOC_DIR / "wh_seas_l_english.yml"
SEAS_TXT_PATH = MOD_ROOT / "map_data" / "state_regions" / "99_seas.txt"
DEFAULT_MAP_PATH = MOD_ROOT / "map_data" / "default.map"
STRATEGIC_REGIONS_PATH = MOD_ROOT / "common" / "strategic_regions" / "water_strategic_regions.txt"
ADJACENCIES_PATH = MOD_ROOT / "map_data" / "adjacencies.csv"

BOM = b"\xef\xbb\xbf"
INDENT = "\t"

# Vanilla ``adjacencies.csv`` header — the exact column order the engine expects.
ADJACENCIES_HEADER = (
    "From;To;Type;Through;start_x;start_y;stop_x;stop_y;adjacency_rule_name;Comment"
)


def _write_bytes(path: Path, text: str, bom: bool = False) -> None:
    data = text.encode("utf-8")
    if bom:
        data = BOM + data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)  # binary write keeps LF newlines regardless of platform


# ---------------------------------------------------------------------------
# The colour join: canon zone -> its real provinces.png colour
# ---------------------------------------------------------------------------

def _join_colors(zone_cells: list[dict], prov_index: dict) -> dict[int, raster.Color]:
    """Map each sea-zone label to the ``provinces.png`` colour of its province.

    Sea provinces occupy provinces-index labels ``land_provinces + 1 ..
    land_provinces + sea_provinces`` in ascending sea-zone order, so zone label
    ``s`` -> province label ``land_provinces + s``. Asserts the target exists, is a
    sea province, and has the same area the canon index recorded (a second,
    independent check that the two indices describe the same zone).
    """
    land_provinces = int(prov_index["land_provinces"])
    by_label = {int(c["label"]): c for c in prov_index["cells"]}

    colors: dict[int, raster.Color] = {}
    for z in zone_cells:
        s = int(z["label"])
        prov_label = land_provinces + s
        pc = by_label.get(prov_label)
        if pc is None:
            raise SystemExit(
                f"colour join failed: sea zone label {s} ({z['key']}) expects "
                f"province label {prov_label}, absent from provinces_index.json"
            )
        if pc.get("kind") != "sea":
            raise SystemExit(
                f"colour join failed: province label {prov_label} for {z['key']} "
                f"is kind={pc.get('kind')!r}, not 'sea'"
            )
        if int(pc["area"]) != int(z["area"]):
            raise SystemExit(
                f"colour join failed: {z['key']} area {z['area']} != province "
                f"label {prov_label} area {pc['area']} — indices disagree on the zone"
            )
        colors[s] = tuple(int(v) for v in pc["color"])
    return colors


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _render_loc(cells: list[dict]) -> str:
    """The committed sea loc: one ``KEY:0 "Display"`` per zone, canon (no marker)."""
    lines = ["l_english:"]
    for c in sorted(cells, key=lambda c: c["key"]):
        lines.append(f' {c["key"]}:0 "{c["display_name"]}"')
    return "\n".join(lines) + "\n"


def _render_sea_state(key: str, state_id: int, color: raster.Color) -> str:
    """One passable single-province sea-zone block (no ``impassable``, unquoted colour)."""
    return (
        f"{key} = {{\n"
        f"{INDENT}id = {state_id}\n"
        f"{INDENT}provinces = {{ {raster.color_to_hex(color)} }}\n"
        "}"
    )


def _render_99_seas(cells: list[dict], colors: dict[int, raster.Color]) -> str:
    blocks = [_render_sea_state(c["key"], c["id"], colors[c["label"]])
              for c in sorted(cells, key=lambda c: c["label"])]
    return "\n\n".join(blocks) + "\n"


def _render_water_strategic_regions(cells: list[dict]) -> str:
    """One ``states``-only water region per canon ``sea_group``.

    Vanilla ``water_strategic_regions.txt`` blocks are minimal (``states`` only,
    no ``capital_province`` / ``map_color``) and load, so this override matches
    that shape. Every sea state lands in exactly one region — its group.
    """
    groups: dict[str, list[dict]] = {}
    for c in cells:
        groups.setdefault(c["sea_group"], []).append(c)
    blocks = []
    for group in sorted(groups):
        members = sorted(groups[group], key=lambda c: c["label"])
        keys = " ".join(m["key"] for m in members)
        blocks.append(
            f"region_{group.lower()} = {{\n"
            f"{INDENT}states = {{ {keys} }}\n"
            "}"
        )
    return "\n\n".join(blocks) + "\n"


def _replace_sea_starts(default_map_text: str, colors: dict[int, raster.Color]) -> str:
    """Replace only the ``sea_starts = { ... }`` body; leave every other key intact.

    Idempotent: the token set and order (sorted by hex) are a pure function of the
    colours, so a re-run reproduces byte-identical output.
    """
    toks = " ".join(sorted(raster.color_to_hex(c) for c in colors.values()))
    open_kw = "sea_starts = {"
    start = default_map_text.index(open_kw)
    brace_open = default_map_text.index("{", start)
    depth = 0
    brace_close = -1
    for i in range(brace_open, len(default_map_text)):
        ch = default_map_text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                brace_close = i
                break
    if brace_close < 0:
        raise SystemExit("default.map: unbalanced braces in sea_starts block")
    new_block = f"sea_starts = {{\n{INDENT}{toks}\n}}"
    return default_map_text[:start] + new_block + default_map_text[brace_close + 1:]


def _parse_sea_starts(default_map_text: str) -> set[str]:
    open_kw = "sea_starts = {"
    start = default_map_text.index(open_kw)
    brace_open = default_map_text.index("{", start)
    depth = 0
    for i in range(brace_open, len(default_map_text)):
        ch = default_map_text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = default_map_text[brace_open + 1:i]
                return set(body.split())
    raise SystemExit("default.map: unbalanced braces in sea_starts block")


def _loc_keys(path: Path) -> set[str]:
    import re
    keys: set[str] = set()
    if not path.is_file():
        return keys
    key_re = re.compile(r"^\s*([A-Za-z0-9_.]+):\d")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = key_re.match(line)
        if m:
            keys.add(m.group(1))
    return keys


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    if not INDEX_PATH.is_file():
        raise SystemExit(f"{INDEX_PATH} not found — run tools/generate_sea_zones.py first")
    if not PROVINCES_INDEX_PATH.is_file():
        raise SystemExit(f"{PROVINCES_INDEX_PATH} not found — run tools/generate_provinces.py first")

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    cells = index["cells"]
    if not cells:
        raise SystemExit(f"{INDEX_PATH} has no cells")
    prov_index = json.loads(PROVINCES_INDEX_PATH.read_text(encoding="utf-8"))

    # Real province colours, joined by label arithmetic (asserted complete).
    colors = _join_colors(cells, prov_index)

    # --- 1. sea loc (canon, unchanged) -----------------------------------
    _write_bytes(LOC_PATH, _render_loc(cells), bom=True)
    print(f"wrote {LOC_PATH.relative_to(MOD_ROOT)}  ({len(cells)} zones)")

    # --- 2. 99_seas.txt --------------------------------------------------
    _write_bytes(SEAS_TXT_PATH, _render_99_seas(cells, colors), bom=True)
    print(f"wrote {SEAS_TXT_PATH.relative_to(MOD_ROOT)}  ({len(cells)} states)")

    # --- 3. default.map sea_starts (in-place block replace) --------------
    dm_text = DEFAULT_MAP_PATH.read_text(encoding="utf-8")
    dm_new = _replace_sea_starts(dm_text, colors)
    _write_bytes(DEFAULT_MAP_PATH, dm_new, bom=False)
    print(f"wrote {DEFAULT_MAP_PATH.relative_to(MOD_ROOT)}  (sea_starts: {len(colors)} colours)")

    # --- 4. water strategic regions --------------------------------------
    _write_bytes(STRATEGIC_REGIONS_PATH, _render_water_strategic_regions(cells), bom=True)
    n_groups = len({c["sea_group"] for c in cells})
    print(f"wrote {STRATEGIC_REGIONS_PATH.relative_to(MOD_ROOT)}  ({n_groups} regions)")

    # --- 5. adjacencies.csv (header-only when absent) --------------------
    if not ADJACENCIES_PATH.is_file():
        _write_bytes(ADJACENCIES_PATH, ADJACENCIES_HEADER + "\n", bom=False)
        print(f"wrote {ADJACENCIES_PATH.relative_to(MOD_ROOT)}  (header only)")
    else:
        print(f"kept  {ADJACENCIES_PATH.relative_to(MOD_ROOT)}  (already authored)")

    # --- assertions ------------------------------------------------------
    seas_colors = {raster.color_to_hex(colors[c["label"]]) for c in cells}
    starts_colors = _parse_sea_starts(dm_new)
    missing = seas_colors - starts_colors
    if missing:
        raise SystemExit(f"invariant: {len(missing)} sea colours missing from sea_starts: "
                         f"{sorted(missing)[:5]}")
    if starts_colors != seas_colors:
        extra = starts_colors - seas_colors
        raise SystemExit(f"invariant: sea_starts carries {len(extra)} colours not in 99_seas: "
                         f"{sorted(extra)[:5]}")

    loc_keys = _loc_keys(LOC_PATH)
    missing_loc = {c["key"] for c in cells} - loc_keys
    if missing_loc:
        raise SystemExit(f"invariant: {len(missing_loc)} sea states have no loc key: "
                         f"{sorted(missing_loc)[:5]}")

    # Idempotence: re-running the block-replace on our own output is a no-op.
    if _replace_sea_starts(dm_new, colors) != dm_new:
        raise SystemExit("invariant: default.map sea_starts replace is not idempotent")

    print(f"ok: {len(cells)} zones joined; {len(seas_colors)} colours in "
          f"99_seas == sea_starts; {n_groups} water regions; loc complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
