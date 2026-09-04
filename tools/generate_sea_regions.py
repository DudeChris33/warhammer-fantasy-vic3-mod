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
* ``map_data/state_regions/99_seas.txt`` — one ``STATE_* { id provinces }``
  block per zone, passable by default (2026-08-22 decision: 1800s steamships
  cross open ocean). Cells sharing a ``key`` (a ``schema.SeaZoneMerge``, e.g.
  the Maelstrom) become one multi-province state instead — merging their
  *pixels* into one province would be disconnected and Vic3 rejects that, so
  each keeps its own province colour and the block lists them all, with
  ``impassable = { ... }`` added when the group is flagged impassable
  (2026-08-31 exception). Colours from ``provinces.png``, ids/keys from the
  canon index.
* ``map_data/default.map`` — in-place block-replace of only the ``sea_starts``
  body with the 201 sea colours; every other key is left byte-for-byte untouched.
* ``common/strategic_regions/water_strategic_regions.txt`` — one ``states``-only
  region per sea *state* by default (2026-09-03: 1 state = 1 region unless a
  future explicit exception groups several; filename overrides vanilla's
  dangling file).
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

def _group_by_key(cells: list[dict]) -> list[list[dict]]:
    """Cells sharing a ``key`` are one Vic3 *state* with several provinces — a
    :class:`schema.SeaZoneMerge` (2026-08-31: e.g. the three separate Maelstrom
    water bodies) gives its members an identical key for exactly this reason,
    since fusing their pixels into one province would be disconnected and Vic3
    rejects that. Grouped in ascending-label order within the group, groups
    themselves ordered by their lowest member label (both for reproducibility)."""
    groups: dict[str, list[dict]] = {}
    for c in cells:
        groups.setdefault(c["key"], []).append(c)
    ordered = sorted(groups.values(), key=lambda g: min(m["label"] for m in g))
    return [sorted(g, key=lambda c: c["label"]) for g in ordered]


def _render_loc(cells: list[dict]) -> str:
    """The committed sea loc: one ``KEY:0 "Display"`` per *state* (cells sharing
    a key are one merged state — see :func:`_group_by_key` — and get one line,
    or the loc carries a duplicate key)."""
    lines = ["l_english:"]
    seen: dict[str, str] = {}
    for c in sorted(cells, key=lambda c: c["key"]):
        seen.setdefault(c["key"], c["display_name"])
    for key in sorted(seen):
        lines.append(f' {key}:0 "{seen[key]}"')
    return "\n".join(lines) + "\n"


def _render_sea_state(key: str, state_id: int, colors: list[raster.Color],
                      impassable: bool) -> str:
    """One sea-zone block: passable by default, or every listed province
    impassable if any member of the group is (2026-08-31 exception to the
    2026-08-22 "no impassable sea province" decision — a merged group is
    impassable as a whole, not province-by-province)."""
    hexes = [raster.color_to_hex(c) for c in colors]
    lines = [
        f"{key} = {{",
        f"{INDENT}id = {state_id}",
        f"{INDENT}provinces = {{ {' '.join(hexes)} }}",
    ]
    if impassable:
        lines.append(f"{INDENT}impassable = {{ {' '.join(hexes)} }}")
    lines.append("}")
    return "\n".join(lines)


def _render_99_seas(cells: list[dict], colors: dict[int, raster.Color]) -> str:
    blocks = [
        _render_sea_state(
            group[0]["key"],
            min(c["id"] for c in group),
            [colors[c["label"]] for c in group],
            any(c.get("impassable", False) for c in group),
        )
        for group in _group_by_key(cells)
    ]
    return "\n\n".join(blocks) + "\n"


def _render_water_strategic_regions(cells: list[dict]) -> str:
    """One ``states``-only water region per sea *state*, by default.

    Vanilla ``water_strategic_regions.txt`` blocks are minimal (``states`` only,
    no ``capital_province`` / ``map_color``) and load, so this override matches
    that shape. Earlier this grouped every state under its canon ``sea_group``
    (23 seas -> ~24 sprawling regions); the default is now 1 state = 1 region, so
    naval AI/strategic scoring for one small strait isn't bundled with every
    other state across its whole canon sea. A merged state (several cells
    sharing a key, e.g. the Maelstrom) still contributes its key only once.
    Region name comes from the state's own key (lower-cased, ``STATE_`` prefix
    dropped) so it stays legible and collision-free the same way the key itself
    now does (``sea_naming.rekey_by_display_name``). Grouping several states
    into one region is a deliberate future exception, not the default — none are
    declared yet.
    """
    keys = sorted({c["key"] for c in cells})
    blocks = []
    for key in keys:
        region = "region_" + key[len("STATE_"):].lower()
        blocks.append(
            f"{region} = {{\n"
            f"{INDENT}states = {{ {key} }}\n"
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
    n_states = len(_group_by_key(cells))
    print(f"wrote {SEAS_TXT_PATH.relative_to(MOD_ROOT)}  "
          f"({n_states} states, {len(cells)} provinces)")

    # --- 3. default.map sea_starts (in-place block replace) --------------
    dm_text = DEFAULT_MAP_PATH.read_text(encoding="utf-8")
    dm_new = _replace_sea_starts(dm_text, colors)
    _write_bytes(DEFAULT_MAP_PATH, dm_new, bom=False)
    print(f"wrote {DEFAULT_MAP_PATH.relative_to(MOD_ROOT)}  (sea_starts: {len(colors)} colours)")

    # --- 4. water strategic regions --------------------------------------
    _write_bytes(STRATEGIC_REGIONS_PATH, _render_water_strategic_regions(cells), bom=True)
    n_regions = len({c["key"] for c in cells})
    print(f"wrote {STRATEGIC_REGIONS_PATH.relative_to(MOD_ROOT)}  ({n_regions} regions)")

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
          f"99_seas == sea_starts; {n_regions} water regions; loc complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
