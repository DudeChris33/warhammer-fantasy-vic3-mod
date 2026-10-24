#!/usr/bin/env python3
"""Emit the land engine files from the committed land-region grouping.

Board #2930/#2931 (bootable-map milestone #2700). The land mirror of
``generate_sea_regions.py``: reads ``mapgen/derived/land_regions_index.json``
(board #2928 — 369 regions: 267 drawn + 102 out-of-scope placeholders) plus the
colour authority ``mapgen/derived/provinces_index.json`` and the sea canon
``mapgen/derived/sea_zones_index.json``, and writes:

* ``map_data/state_regions/NN_<stem>.txt`` — one ``STATE_LAND_NNN`` block per
  region, routed into whichever of the 20 existing stub files its assigned
  realm's ``file_stem`` names (``worldgen.land_naming``, board #2931 — real
  per-realm split superseding #2930's single-``00_norsca.txt`` placeholder).
  Realm assignment is a per-region pixel-plurality vote against
  ``sources/terraqueous_globe_reprojected - strategic_regions.png``, classified
  by exact RGB via ``mapgen/config/strategic_region_colors.json``; a region with
  zero votes (outside the painting's coverage) is an out-of-scope placeholder,
  named from its nearest continent in ``mapgen/config/out_of_scope_continents.json``.
  ``NNN`` is **not** the raw ``land_regions_index.json`` region label (flood-fill
  discovery order, geographically scattered) — see
  ``worldgen.land_state_numbering.assign_state_numbers`` (board #4188), which
  keys each region's identity on its stable province-id set and matches it
  against the committed ``mapgen/derived/land_state_ids.json`` so an unchanged
  region keeps its number across regens (falling back to a fresh Hilbert-order
  numbering, Chris 2026-09-05, only for a genuinely new region or the very
  first generation). ``render_land_regions_preview.py`` imports the same
  function fed identical raw centroids, so its on-image numbers and CSV ids
  always match what actually ships here.
* ``common/strategic_regions/<continent>_strategic_regions.txt`` — one
  ``region_<realm>`` block per in-scope realm, grouped by continent (mirroring
  vanilla's own ``europe_strategic_regions.txt``-style split; user decision
  2026-09-05) — currently ``old_world_strategic_regions.txt`` and
  ``southlands_strategic_regions.txt``. Every out-of-scope placeholder state
  lands in one catch-all ``region_out_of_scope_placeholders`` block in
  ``out_of_scope_strategic_regions.txt`` (states-only, no capital/map_color —
  the minimal shape vanilla's own water regions already prove loads fine).
* ``localization/replace/english/map/states_l_english.yml`` — the canon name
  from ``mapgen/config/land_regions_worksheet.csv`` (or the out-of-scope
  placeholder's continent name) per state; ``AUTOGEN_MARKER`` only survives for
  a state with neither — a real content gap to fix in the worksheet, not to
  invent here. Deliberately in ``localization/replace/`` and named after
  vanilla's own file (not ``wh_land_states_l_english.yml`` under
  ``localization/english/``) — an Old-World name can coincide with a
  real-world vanilla state name (found via ``STATE_AQUITAINE``), and the
  mod's own name should override vanilla's outright rather than dodge the
  collision with a numeric fallback key (user decision 2026-09-06).

Each drawn state's ``subsistence_building`` / ``arable_land`` / ``arable_resources`` come from
``mapgen/config/land_economics_worksheet.csv`` (hand-authored; rows keyed on the canon state key
with a verified naming anchor; an empty cell, a missing row and every placeholder take
``worldgen.land_economics.DEFAULT_ECONOMICS``; rules in ``land_economics.check_economics``,
errors collected and reported once, board #3678). ``--rekey-economics`` repairs stale key cells.
A worksheet edit also forces ``generate_building_history.py`` (it reads the emitted fields).

Run ``mapgen/render_land_regions_preview.py`` afterwards for the numbered
review render + CSV worksheet — the persisted naming input this script reads
(``mapgen/config/land_regions_worksheet.csv``, hand-edited like
``mapgen/config/inland_lakes.json``, never re-derived from scratch). It drapes
the real TWW3 parchment art under the numbered regions (reusing
``project_regions_unified.py``'s triangle-warp registration) rather than guessing a name
algorithmically: an earlier cut of this pipeline guessed the nearest
real-world vanilla Vic3 state by longitude/latitude (rejected — coincidental
Earth-geography proximity means nothing on a fictional world), and OCR of the
parchment itself was tried and failed in practice (Tesseract garbled almost
everything on this stylised, curved-baseline font). The user chose to drop
automated guessing and read real names off the render instead (2026-09-05).

Deterministic: a pure function of the committed indices +
``map_data/provinces.png`` + the two board-#2931 inputs above +
``map_config.SEED`` (only used for each strategic region's cosmetic
``map_color``). Regenerate through this script after an intentional upstream
change; never hand-edit its outputs.

Usage::

    python mapgen/generate_land_regions.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import (land_economics, land_naming, land_state_numbering, raster,  # noqa: E402
                      real_world_economics, schema, scope_additions, sources)
from worldgen.statefile import (  # noqa: E402
    ProvinceInfo,
    pick_hubs,
    render_land_state,
    render_state_file,
    stack_hubs,
)

TOOLS_DIR = Path(__file__).resolve().parent
MOD_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"

LAND_REGIONS_INDEX_PATH = DERIVED_DIR / "land_regions_index.json"
PROVINCES_INDEX_PATH = DERIVED_DIR / "provinces_index.json"
SEA_ZONES_INDEX_PATH = DERIVED_DIR / "sea_zones_index.json"
#: Optional — the anchor -> seeded-province index written by generate_provinces.py
#: (#3665). Present only when a hub worksheet exists; read here to pick each listed
#: settlement's province as its state's hub and emit the HUB_NAME loc.
HUB_ANCHORS_INDEX_PATH = DERIVED_DIR / "hub_anchors_index.json"
#: Committed STATE-number identity authority (board #4188, mirrors #3705's
#: provinces_index.json): state_number -> stable province-id set + a monotonic
#: state_number_high_water. Written here, read read-only by
#: render_land_regions_preview.py. Absent on the very first generation —
#: land_state_numbering.assign_state_numbers falls back to a fresh bootstrap.
LAND_STATE_IDS_PATH = DERIVED_DIR / "land_state_ids.json"
PROVINCES_PNG_PATH = MOD_ROOT / "map_data" / "provinces.png"
SEAS_TXT_PATH = MOD_ROOT / "map_data" / "state_regions" / "99_seas.txt"

WORKSHEET_PATH = TOOLS_DIR / "config" / "land_regions_worksheet.csv"
VANILLA_STATE_LOC_KEYS_PATH = TOOLS_DIR / "config" / "vanilla_state_loc_keys.txt"
STRATEGIC_COLORS_PATH = TOOLS_DIR / "config" / "strategic_region_colors.json"
STRATEGIC_PNG_PATH = sources.resolve_source_path("terraqueous_globe_reprojected - strategic_regions.png")
OUT_OF_SCOPE_CONTINENTS_PATH = TOOLS_DIR / "config" / "out_of_scope_continents.json"
#: In-scope land outside the painted realms, with the realm each piece takes
#: (worldgen.scope_additions); the same file generate_provinces.py reads.
IN_SCOPE_ADDITIONS_PATH = TOOLS_DIR / "config" / "in_scope_additions.json"

STATE_REGIONS_DIR = MOD_ROOT / "map_data" / "state_regions"
STRATEGIC_REGIONS_DIR = MOD_ROOT / "common" / "strategic_regions"
#: Lives under localization/replace/english/ (not localization/english/) and
#: is named after vanilla's own file, matching that file's filename exactly —
#: user decision 2026-09-06: an Old-World region name can coincide with a
#: real-world vanilla state name (found via STATE_AQUITAINE), and the mod's
#: own name should simply override vanilla's in that case, not dodge it with
#: a numeric fallback. A replace-folder file overrides matching keys and adds
#: new ones without the duplicate-key error two same-named vanilla-namespace
#: files would raise.
LOC_PATH = MOD_ROOT / "localization" / "replace" / "english" / "map" / "states_l_english.yml"
# replace/ so STATE_AQUITAINE (also a vanilla state) overrides vanilla's HUB_NAME_STATE_AQUITAINE_* instead of erroring as a duplicate key
HUB_LOC_PATH = MOD_ROOT / "localization" / "replace" / "english" / "map" / "wh_hub_names_l_english.yml"
BUILDINGS_DIR = MOD_ROOT / "common" / "buildings"
BUILDING_GROUPS_DIR = MOD_ROOT / "common" / "building_groups"
#: Hand-authored per-state economics (#3678), keyed on the canon state key + naming anchor;
#: read here, rules in worldgen.land_economics. Empty cell = per-column default.
ECONOMICS_WORKSHEET_PATH = TOOLS_DIR / "config" / "land_economics_worksheet.csv"
#: Real-world-equivalent defaults (Chris, 2026-10-12): per-zone vanilla totals + the canvas zone
#: raster, built offline by ``build_real_world_equivalents.py``; worldgen.real_world_economics.
REAL_WORLD_CONFIG_PATH = TOOLS_DIR / "config" / "real_world_equivalents.json"
REAL_WORLD_ZONES_PATH = TOOLS_DIR / "config" / "real_world_zones.png"

BOM = b"\xef\xbb\xbf"
INDENT = "\t"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: realm's ``file_stem`` (from strategic_region_colors.json) -> the existing
#: NN_<stem>.txt stub file it lands in (board #2931 — the real per-realm split
#: #2930 deferred). Every stub file already exists; this only routes into it.
STATE_FILE_STEMS = {
    "norsca": "00_norsca.txt", "kislev": "01_kislev.txt", "empire": "02_empire.txt",
    "brettonia": "03_brettonia.txt", "karaz_ankor": "04_karaz_ankor.txt",
    "southern_realms": "05_southern_realms.txt", "badlands": "06_badlands.txt",
    "nehekhara": "07_nehekhara.txt", "araby": "08_araby.txt", "southlands": "09_southlands.txt",
    "dark_lands": "10_dark_lands.txt", "ogre_kingdoms": "11_ogre_kingdoms.txt",
    "eastern_steppes": "12_eastern_steppes.txt", "cathay": "13_cathay.txt", "ind": "14_ind.txt",
    "khuresh": "15_khuresh.txt", "nippon": "16_nippon.txt", "ulthuan": "17_ulthuan.txt",
    "naggaroth": "18_naggaroth.txt", "lustria": "19_lustria.txt",
}

#: out-of-scope continent (mapgen/config/out_of_scope_continents.json's own
#: ``name``) -> the ``STATE_FILE_STEMS`` key its placeholder states land in.
#: Bookkeeping only (which already-empty stub file houses the state), not a
#: canon geographic claim — several continents share a file where no distinct
#: stub exists for them yet (this item does not author new stub files).
OUT_OF_SCOPE_FILE_STEM = {
    "naggaroth": "naggaroth", "lustria": "lustria", "ulthuan": "ulthuan",
    "southlands": "southlands", "nippon": "nippon",
    "eastern_lands": "cathay",           # "one placeholder for the whole eastern remainder"
    "western_ocean_mass": "naggaroth",   # nearest known landmass; canon identity TBD (config's own note)
    "far_south_east": "khuresh",         # nearest known landmass; canon identity TBD (config's own note)
}


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


def _write_bytes(path: Path, text: str, bom: bool = False) -> None:
    data = text.encode("utf-8")
    if bom:
        data = BOM + data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _pretty_name(key: str) -> str:
    return " ".join(part.capitalize() for part in key[len("STATE_"):].split("_"))


# ---------------------------------------------------------------------------
# Province bitmap -> label array (the colour authority, read once)
# ---------------------------------------------------------------------------

def _build_label_array(rgb: np.ndarray, cells: list[dict]) -> np.ndarray:
    """Reconstruct the per-pixel province-label layer from the bitmap + index,
    exactly as ``validate_map.validate_provinces`` cross-checks it."""
    code = ((rgb[..., 0].astype(np.int64) << 16)
            | (rgb[..., 1].astype(np.int64) << 8) | rgb[..., 2].astype(np.int64))
    color_to_label: dict[int, int] = {}
    for c in cells:
        r, g, b = c["color"]
        k = (int(r) << 16) | (int(g) << 8) | int(b)
        color_to_label[k] = int(c["label"])
    uniq, inv = np.unique(code, return_inverse=True)
    lut = np.array([color_to_label.get(int(k), 0) for k in uniq.tolist()], dtype=np.int64)
    labels = lut[inv].reshape(code.shape)
    if int((labels == 0).sum()):
        raise SystemExit(
            f"{int((labels == 0).sum()):,} pixel(s) in {PROVINCES_PNG_PATH.name} match no "
            f"province colour in the index"
        )
    return labels


# ---------------------------------------------------------------------------
# Wrap-aware circular centroids (province-level and region-level, one pass)
# ---------------------------------------------------------------------------

def _land_pixel_theta(labels: np.ndarray, land_mask: np.ndarray, width: int):
    ys, xs = np.nonzero(land_mask)
    lab = labels[ys, xs]
    theta = (xs.astype(np.float64) + 0.5) * (2.0 * np.pi / width)
    return lab, np.cos(theta), np.sin(theta), ys.astype(np.float64) + 0.5


def _circular_centroids(lab: np.ndarray, cos_t: np.ndarray, sin_t: np.ndarray, y: np.ndarray,
                        group_of: np.ndarray, n_groups: int, width: int):
    """Wrap-aware (circular-mean x, linear-mean y) centroid per group id
    ``1..n_groups`` (mirrors ``measure_vanilla_frame.state_centroids``'
    circular-mean estimator, generalised from province colours to any
    per-pixel group array)."""
    grp = group_of[lab]
    sum_cos = np.bincount(grp, weights=cos_t, minlength=n_groups + 1)
    sum_sin = np.bincount(grp, weights=sin_t, minlength=n_groups + 1)
    sum_y = np.bincount(grp, weights=y, minlength=n_groups + 1)
    counts = np.bincount(grp, minlength=n_groups + 1)
    ang = np.arctan2(sum_sin, sum_cos)
    cx = (ang % (2.0 * np.pi)) * width / (2.0 * np.pi)
    cy = np.zeros_like(sum_y)
    nz = counts > 0
    cy[nz] = sum_y[nz] / counts[nz]
    return cx, cy, counts


# ---------------------------------------------------------------------------
# naval_exit resolution: region <-> bordering sea-state adjacency
# ---------------------------------------------------------------------------

def _sea_state_of_zone(sea_cells: list[dict], n_sea: int) -> np.ndarray:
    """zone label ``1..n_sea`` -> the sea **state** id it will be emitted
    under in ``99_seas.txt`` (cells sharing a ``key`` are one merged state and
    use the group's ``min(id)`` — mirrors ``generate_sea_regions._render_99_seas``)."""
    groups: dict[str, list[dict]] = {}
    for c in sea_cells:
        groups.setdefault(c["key"], []).append(c)
    out = np.zeros(n_sea + 1, dtype=np.int64)
    for members in groups.values():
        min_id = min(int(m["id"]) for m in members)
        for m in members:
            out[int(m["label"])] = min_id
    return out


def _naval_exit_choices(labels: np.ndarray, n_land: int, region_of: np.ndarray,
                        sea_state_of_zone: np.ndarray) -> dict[int, int]:
    """region id -> the sea-state id bordering the most of its coastline
    (ties -> lowest sea id), by 4-neighbour adjacency between every land pixel
    and every sea pixel (x wraps, y does not — matching
    ``validate_map.ProvinceBitmap.coastal_colors``)."""
    land_mask = (labels >= 1) & (labels <= n_land)
    n_sea = len(sea_state_of_zone) - 1  # sea_state_of_zone is sized n_sea + 1 (index 0 unused)
    sea_mask = (labels > n_land) & (labels <= n_land + n_sea)  # excludes lake labels above it

    region_full = np.zeros(labels.shape, dtype=np.int64)
    region_full[land_mask] = region_of[labels[land_mask]]

    sea_full = np.zeros(labels.shape, dtype=np.int64)
    sea_full[sea_mask] = sea_state_of_zone[labels[sea_mask] - n_land]

    pair_counts: dict[int, int] = {}

    def _accumulate(shifted_sea: np.ndarray) -> None:
        mask = (region_full > 0) & (shifted_sea > 0)
        if not mask.any():
            return
        keys = region_full[mask] * 1_000_000 + shifted_sea[mask]
        uniq, counts = np.unique(keys, return_counts=True)
        for k, c in zip(uniq.tolist(), counts.tolist()):
            pair_counts[k] = pair_counts.get(k, 0) + c

    _accumulate(np.roll(sea_full, 1, axis=1))
    _accumulate(np.roll(sea_full, -1, axis=1))
    up = np.zeros_like(sea_full)
    up[:-1, :] = sea_full[1:, :]
    down = np.zeros_like(sea_full)
    down[1:, :] = sea_full[:-1, :]
    _accumulate(up)
    _accumulate(down)

    best: dict[int, tuple[int, int]] = {}  # region -> (count, sea_id)
    for key, count in pair_counts.items():
        region, sea_id = divmod(key, 1_000_000)
        cur = best.get(region)
        if cur is None or count > cur[0] or (count == cur[0] and sea_id < cur[1]):
            best[region] = (count, sea_id)
    return {region: sea_id for region, (count, sea_id) in best.items()}


# ---------------------------------------------------------------------------
# Strategic region + loc rendering
# ---------------------------------------------------------------------------

def _render_strategic_region_block(name: str, state_keys: list[str],
                                   capital_color: raster.Color | None = None,
                                   map_color: raster.Color | None = None) -> str:
    """One ``region_<name>`` block. ``states``-only when no capital/colour is
    given — vanilla's own ``water_strategic_regions.txt`` blocks are minimal
    like this and load fine (see ``generate_sea_regions._render_water_strategic_regions``),
    so the out-of-scope catch-all region uses that shape too."""
    lines = [f"region_{name} = {{"]
    if capital_color is not None:
        lines.append(f"{INDENT}capital_province = {raster.color_to_hex(capital_color)}")
    if map_color is not None:
        r, g, b = map_color
        lines.append(f"{INDENT}map_color = {{ {r} {g} {b} }}")
    lines.append(f"{INDENT}states = {{ {' '.join(state_keys)} }}")
    lines.append("}")
    return "\n".join(lines)


_LOC_LINE = re.compile(r'^ ([A-Za-z0-9_]+):0 ".*$')


def _read_existing_loc(path: Path) -> dict[str, str]:
    """``key -> raw line`` for every entry already in the shipped loc file, so a
    regen never drops a name whose state no longer exists."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = _LOC_LINE.match(line)
        if m:
            out[m.group(1)] = line
    return out


def _render_loc(keys: list[str], canon_names: dict[str, str],
                existing: dict[str, str] | None = None) -> str:
    lines = ["l_english:"]
    for key in keys:
        name = canon_names.get(key)
        if name:
            escaped = name.replace('"', '\\"')
            lines.append(f' {key}:0 "{escaped}"')
        else:
            lines.append(f' {key}:0 "{_pretty_name(key)}" {map_config.AUTOGEN_MARKER}')
    emitted = set(keys)
    retained = sorted(k for k in (existing or {}) if k not in emitted)
    if retained:
        lines.append("# Retained: no longer emitted by the current region cut; kept so no name is lost.")
        lines.extend(existing[k] for k in retained)
    return "\n".join(lines) + "\n"


def _render_hub_loc(entries: list[tuple[str, str]]) -> str:
    """The ``HUB_NAME_<STATE_KEY>_<hub>`` loc file (board #3665), vanilla's shape in
    ``game/localization/english/hub_names_l_english.yml``. Only listed hubs get a
    key — an unlisted hub falls through to the engine default (no entry)."""
    lines = ["l_english:"]
    for loc_key, name in entries:
        escaped = name.replace('"', '\\"')
        lines.append(f' {loc_key}:0 "{escaped}"')
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reassign", action="store_true",
                        help="Ignore the committed land_state_ids.json and renumber every STATE "
                             "fresh in Hilbert order (board #4188's escape hatch — pair with a "
                             "province-bitmap --reassign so every identity resets together).")
    parser.add_argument("--rekey-economics", action="store_true",
                        help="Authoring action (#3678): rewrite the state_key cell of every "
                             "land_economics_worksheet.csv row whose key is stale but whose anchor "
                             "equals exactly one drawn state's naming anchor, print old -> new, and "
                             "exit without emitting. Never touches anchors or any other cell.")
    args = parser.parse_args(argv)
    t0 = time.time()

    for path in (LAND_REGIONS_INDEX_PATH, PROVINCES_INDEX_PATH, SEA_ZONES_INDEX_PATH, PROVINCES_PNG_PATH):
        if not path.is_file():
            raise SystemExit(f"{path} not found — run the map generator pipeline first")

    land_regions = json.loads(LAND_REGIONS_INDEX_PATH.read_text(encoding="utf-8"))
    prov_index = json.loads(PROVINCES_INDEX_PATH.read_text(encoding="utf-8"))
    sea_index = json.loads(SEA_ZONES_INDEX_PATH.read_text(encoding="utf-8"))

    n_land = int(prov_index["land_provinces"])
    n_sea = int(prov_index["sea_provinces"])
    n_regions = int(land_regions["regions"])
    if len(land_regions["cells"]) != n_regions:
        raise SystemExit(
            f"{LAND_REGIONS_INDEX_PATH.name}: declares {n_regions} regions but lists "
            f"{len(land_regions['cells'])}"
        )
    log(f"{n_regions} land regions ({land_regions['drawn_regions']} drawn, "
        f"{land_regions['placeholder_regions']} placeholder), {n_land} land provinces, "
        f"{n_sea} sea zones", t0)

    catalog = land_economics.load_building_catalog(BUILDINGS_DIR, BUILDING_GROUPS_DIR)
    default_econ = land_economics.default_economics()
    default_errs, _ = land_economics.check_economics("<defaults>", default_econ, True, catalog)
    if default_errs:
        raise SystemExit("default economics are invalid:\n  " + "\n  ".join(default_errs))
    log(f"verified the default economics' building ids exist under {BUILDINGS_DIR.name}/ "
        f"({len(catalog.groups)} buildings in the catalog)", t0)

    # --- province info + region membership --------------------------------
    province_info: dict[int, dict] = {}
    label_to_stable_id: dict[int, int] = {}
    stable_id_area: dict[int, int] = {}
    for c in prov_index["cells"]:
        if c["kind"] != "land":
            continue
        label = int(c["label"])
        stable_id = int(c["id"])
        area = int(c["area"])
        province_info[label] = {
            "color": tuple(int(v) for v in c["color"]),
            "area": area,
            "coastal": bool(c["coastal"]),
            "impassable": bool(c.get("impassable", False)),  # #3704, never OR'd with placeholder
        }
        label_to_stable_id[label] = stable_id
        stable_id_area[stable_id] = area

    region_of = np.zeros(n_land + 1, dtype=np.int64)
    for cell in land_regions["cells"]:
        for p in cell["provinces"]:
            region_of[p] = int(cell["region"])
    if not (region_of[1:] > 0).all():
        raise SystemExit("land_regions_index.json does not cover every land province")

    # Each region's identity for stable STATE-number matching (board #4188):
    # the set of its provinces' STABLE ids (worldgen.province_ids.assign's
    # `id`), not the transient cut-order `label` — labels are only guaranteed
    # stable within a single run.
    region_province_ids: dict[int, set[int]] = {}
    for cell in land_regions["cells"]:
        region_province_ids[int(cell["region"])] = {
            label_to_stable_id[p] for p in cell["provinces"]
        }

    # --- province bitmap -> label array, then province + region centroids -
    rgb = raster.read_rgb_png(PROVINCES_PNG_PATH)
    if rgb.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{PROVINCES_PNG_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{rgb.shape[1]}x{rgb.shape[0]}")
    labels = _build_label_array(rgb, prov_index["cells"])
    land_mask = (labels >= 1) & (labels <= n_land)
    log("province bitmap indexed", t0)

    lab, cos_t, sin_t, y = _land_pixel_theta(labels, land_mask, CANVAS_W)
    identity = np.arange(n_land + 1, dtype=np.int64)
    prov_cx, prov_cy, prov_counts = _circular_centroids(lab, cos_t, sin_t, y, identity, n_land, CANVAS_W)
    region_cx, region_cy, region_counts = _circular_centroids(
        lab, cos_t, sin_t, y, region_of, n_regions, CANVAS_W)
    if not (prov_counts[1:] > 0).all():
        raise SystemExit("a land province has no pixels in provinces.png")
    if not (region_counts[1:] > 0).all():
        raise SystemExit("a land region has no pixels in provinces.png")
    log("province + region centroids computed", t0)

    # --- stable STATE numbering across regens (board #4188) ----------------
    # land_regions_index.json's "region" field is flood-fill discovery order,
    # not geographic order, so a raw Hilbert-order-every-run renumbering
    # (Chris, 2026-09-05) made neighbouring regions numerically close — but
    # renumbered EVERY region on EVERY run, rewriting almost every
    # state_regions/*.txt file (and silently reattaching worksheet-carried
    # canon names to the wrong region) even when only one region actually
    # changed. assign_state_numbers keys each region's identity on its stable
    # province-id set and matches it against the committed
    # land_state_ids.json: an unchanged region keeps its number, a genuinely
    # new region gets a fresh one, a removed region's number is retired for
    # good. Shared with render_land_regions_preview.py (fed identical raw,
    # unsnapped centroids) so the two never drift apart.
    committed_state_ids = None
    if LAND_STATE_IDS_PATH.is_file() and not args.reassign:
        committed_state_ids = json.loads(LAND_STATE_IDS_PATH.read_text(encoding="utf-8"))
    state_number, new_state_ids_index = land_state_numbering.assign_state_numbers(
        region_cx, region_cy, n_regions, region_province_ids, stable_id_area,
        committed_state_ids, reassign=args.reassign, log=lambda m: log(f"WARNING: {m}", t0))
    log("region ids stably matched into STATE numbers", t0)

    # --- realm assignment from the strategic-regions painting (board #2931) -
    for path in (WORKSHEET_PATH, STRATEGIC_COLORS_PATH, STRATEGIC_PNG_PATH, OUT_OF_SCOPE_CONTINENTS_PATH):
        if not path.is_file():
            raise SystemExit(f"{path} not found")

    legend = land_naming.load_strategic_region_colors(STRATEGIC_COLORS_PATH)
    strategic_rgb = raster.read_rgb_png(STRATEGIC_PNG_PATH)
    crop_h, crop_w = strategic_rgb.shape[:2]
    if crop_h > CANVAS_H or crop_w > CANVAS_W:
        raise SystemExit(f"{STRATEGIC_PNG_PATH.name}: {crop_w}x{crop_h} does not fit inside the "
                         f"{CANVAS_W}x{CANVAS_H} canvas — it must be a top-left crop of it")
    labels_crop = labels[:crop_h, :crop_w]
    land_crop_mask = (labels_crop >= 1) & (labels_crop <= n_land)
    region_of_pixel_crop = np.zeros((crop_h, crop_w), dtype=np.int64)
    region_of_pixel_crop[land_crop_mask] = region_of[labels_crop[land_crop_mask]]
    assignments = land_naming.assign_realms(region_of_pixel_crop, n_regions, strategic_rgb, legend)
    log(f"realm votes computed for {n_regions} regions against {STRATEGIC_PNG_PATH.name}", t0)

    weak_margin = land_naming.weak_confidence_regions(assignments)
    if weak_margin:
        log(f"WARNING: {len(weak_margin)} region(s) have a thin realm-vote margin "
            f"(<{land_naming.CONFIDENCE_MARGIN_FLOOR:.0%}) — flag for loremaster review: "
            f"STATE number(s) {sorted(int(state_number[r]) for r in weak_margin)}", t0)

    # A drawn region with zero votes (e.g. a sliver small enough that its
    # province pixels land entirely on the magenta border ink) falls back to
    # its nearest already-classified drawn neighbour's realm, wrap-aware — the
    # plan's own edge case: "must not raise on this ... falls back to
    # nearest-neighbour among already-classified regions." A drawn region is
    # never left unclassified; only genuinely out-of-scope regions are.
    drawn_region_ids = {int(c["region"]) for c in land_regions["cells"] if c["kind"] == "drawn"}

    # In-scope additions name their realm outright: the painting does not cover
    # them, and where it does (Ulthuan sits inside its crop, unpainted) a stray
    # vote or the nearest-neighbour fallback below would file them under an
    # Old World realm.
    addition_realms: dict[str, scope_additions.Realm] = {}
    if IN_SCOPE_ADDITIONS_PATH.is_file():
        try:
            additions = scope_additions.load(IN_SCOPE_ADDITIONS_PATH, (CANVAS_W, CANVAS_H))
            region_of_pixel = np.zeros(labels.shape, dtype=np.int64)
            land_px = (labels >= 1) & (labels <= n_land)
            region_of_pixel[land_px] = region_of[labels[land_px]]
            added = scope_additions.region_realms(region_of_pixel, additions)
        except scope_additions.ScopeAdditionError as e:
            raise SystemExit(f"{IN_SCOPE_ADDITIONS_PATH.name}: {e}")
        painted = {f.realm for f in legend.fills}
        clash = sorted(set(additions.realms) & painted)
        if clash:
            raise SystemExit(f"{IN_SCOPE_ADDITIONS_PATH.name}: realm(s) {clash} are already painted "
                             f"realms in {STRATEGIC_COLORS_PATH.name}")
        not_drawn = sorted(int(state_number[r]) for r in added if r not in drawn_region_ids)
        if not_drawn:
            raise SystemExit(f"{IN_SCOPE_ADDITIONS_PATH.name}: STATE number(s) {not_drawn} are taken by an "
                             f"addition but were cut as placeholders - re-run generate_provinces.py")
        for r, realm_name in added.items():
            realm_def = additions.realms[realm_name]
            if realm_def.file_stem not in STATE_FILE_STEMS:
                raise SystemExit(f"{IN_SCOPE_ADDITIONS_PATH.name}: realm {realm_name!r} names file stem "
                                 f"{realm_def.file_stem!r}, which has no map_data/state_regions file")
            addition_realms[realm_name] = realm_def
            assignments[r] = land_naming.RealmAssignment(
                realm=realm_def.realm, file_stem=realm_def.file_stem, continent=realm_def.continent,
                votes=0, top_fraction=0.0, margin=0.0)
        log(f"in-scope additions: {len(added)} region(s) take a declared realm "
            f"({sorted(addition_realms)})", t0)

    zero_vote_drawn = sorted(r for r in drawn_region_ids if assignments[r].realm is None)
    if zero_vote_drawn:
        classified_drawn = [r for r in drawn_region_ids if assignments[r].realm is not None]
        if not classified_drawn:
            raise SystemExit("every drawn region got zero realm-colour votes — "
                             "the strategic-regions painting covers nothing")
        half = CANVAS_W / 2.0
        for r in zero_vote_drawn:
            cx, cy = float(region_cx[r]), float(region_cy[r])

            def _d2(other: int) -> float:
                dx = abs(cx - float(region_cx[other]))
                if dx > half:
                    dx = CANVAS_W - dx
                dy = cy - float(region_cy[other])
                return dx * dx + dy * dy

            nearest = min(classified_drawn, key=_d2)
            fallback = assignments[nearest]
            assignments[r] = land_naming.RealmAssignment(
                realm=fallback.realm, file_stem=fallback.file_stem, continent=fallback.continent,
                votes=0, top_fraction=0.0, margin=0.0)
        log(f"WARNING: {len(zero_vote_drawn)} drawn region(s) got zero realm-colour votes "
            f"(sliver landed on border ink) — fell back to nearest classified neighbour's realm: "
            f"STATE number(s) {sorted(int(state_number[r]) for r in zero_vote_drawn)}", t0)

    worksheet = land_naming.load_worksheet_names(WORKSHEET_PATH)
    if worksheet.weak:
        log(f"{len(worksheet.weak)} worksheet name(s) flagged (weak) for loremaster review: "
            f"STATE number(s) {sorted(worksheet.weak)}", t0)
    dupe_names = {n for n in worksheet.names.values()
                  if list(worksheet.names.values()).count(n) > 1}
    if dupe_names:
        log(f"WARNING: {len(dupe_names)} worksheet name(s) used more than once: {sorted(dupe_names)}", t0)

    # --- key-collision guard against the sea file ---------------------------
    sea_keys: set[str] = set()
    if SEAS_TXT_PATH.is_file():
        sea_keys = set(re.findall(r"(STATE_\w+)\s*=\s*\{", SEAS_TXT_PATH.read_text(encoding="utf-8-sig")))

    # Named-region STATE keys derive from the worksheet name itself (user
    # decision 2026-09-05), not the numeric STATE_LAND_NNN placeholder — an
    # unnamed region (out-of-scope placeholder, or a real naming gap) keeps
    # the numeric key, since there is no name to derive one from.
    derived_keys = land_naming.derive_state_keys(worksheet)

    # A land name can legitimately coincide with an already-emitted sea zone's
    # name (e.g. a coastal region named after the bay it borders) — the plan's
    # own edge case says to surface this, not silently invent a workaround.
    # Falling back to the numeric key for just the colliding region (rather
    # than hard-erroring the whole build over one shared name) is the
    # least-surprising resolution: the sea side keeps its name, this land
    # region keeps a stable numeric id, and the clash is still logged loudly.
    # (A collision with a *vanilla* state key is NOT handled this way — see
    # below: this mod's loc now lives in localization/replace/english/ and is
    # meant to override vanilla's matching key outright, user decision
    # 2026-09-06, found via STATE_AQUITAINE.)
    colliding = {sn: key for sn, key in derived_keys.items() if key in sea_keys}
    if colliding:
        for sn in colliding:
            del derived_keys[sn]
        log(f"WARNING: {len(colliding)} land name(s) collide with an existing sea-zone key — "
            f"kept numeric STATE_LAND_NNN for these instead: "
            f"{sorted((sn, colliding[sn]) for sn in colliding)}", t0)

    # Informational only: a derived key that happens to match a vanilla state
    # key is a deliberate override now (the loc file lives in
    # localization/replace/english/), not something to dodge — just log which
    # ones so it's visible, never blocking.
    vanilla_keys = {
        line.strip() for line in VANILLA_STATE_LOC_KEYS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    vanilla_overrides = sorted(key for key in derived_keys.values() if key in vanilla_keys)
    if vanilla_overrides:
        log(f"{len(vanilla_overrides)} land name(s) override a vanilla state loc key by design "
            f"(localization/replace/english/): {vanilla_overrides}", t0)

    continents = schema.load_out_of_scope_continents(OUT_OF_SCOPE_CONTINENTS_PATH,
                                                       canvas=(CANVAS_W, CANVAS_H))
    # Classified by land_regions_index.json's own authoritative `kind`, not by
    # vote count: a huge placeholder can graze the painting's crop rectangle
    # and pick up a few stray in-scope votes without being any less
    # out-of-scope (found 2026-09-05 — STATE_LAND_172, a 1.25M px placeholder,
    # got a nonzero realm vote this way and would otherwise have shipped as a
    # bogus "in-scope realm" region with no name).
    placeholder_region_ids = [int(c["region"]) for c in land_regions["cells"] if c["kind"] == "placeholder"]
    oos_continent_of = land_naming.assign_out_of_scope_continent(
        region_cx, region_cy, placeholder_region_ids, continents, CANVAS_W)
    log(f"{len(placeholder_region_ids)} out-of-scope placeholder region(s) classified to a continent", t0)

    # --- naval_exit: region -> bordering sea-state id ----------------------
    sea_state_of_zone = _sea_state_of_zone(sea_index["cells"], n_sea)
    naval_exit_choice = _naval_exit_choices(labels, n_land, region_of, sea_state_of_zone)
    log(f"naval_exit adjacency resolved for {len(naval_exit_choice)} coastal region(s)", t0)

    # --- per-state economics worksheet (#3678) -------------------------------
    # Rows are keyed on the canon state key and verified against the state's
    # naming-worksheet anchor (worldgen.land_economics); a drawn state without a
    # row, or with empty cells, takes the default per column; placeholders always do.
    if not ECONOMICS_WORKSHEET_PATH.is_file():
        raise SystemExit(f"{ECONOMICS_WORKSHEET_PATH} not found")
    try:
        econ_sheet = land_economics.load_economics_worksheet(ECONOMICS_WORKSHEET_PATH)
    except schema.SchemaError as exc:
        raise SystemExit(str(exc))
    naming_anchors = land_economics.load_naming_anchors(WORKSHEET_PATH)
    econ_identity: dict[str, land_economics.StateIdentity] = {}
    for cell in land_regions["cells"]:
        rid = int(cell["region"])
        sn = int(state_number[rid])
        econ_identity[derived_keys.get(sn, f"STATE_LAND_{sn:03d}")] = land_economics.StateIdentity(
            anchor=naming_anchors[sn][0] if sn in naming_anchors else None,
            placeholder=rid not in drawn_region_ids)
    sheet_errors, rekeys = land_economics.check_worksheet_identity(
        econ_sheet.rows, econ_identity, sea_keys)
    if args.rekey_economics:
        if rekeys:
            text = ECONOMICS_WORKSHEET_PATH.read_bytes().decode("utf-8")
            ECONOMICS_WORKSHEET_PATH.write_bytes(
                land_economics.rekey_worksheet_text(text, rekeys).encode("utf-8"))
        for row, new_key in rekeys:
            log(f"rekeyed row {row.line}: {row.state_key} -> {new_key}", t0)
        fixed = {f"row {r.line} {r.state_key}:" for r, _ in rekeys}
        for e in sheet_errors:
            if not any(e.startswith(f) for f in fixed):
                log(f"NOT auto-fixable, edit by hand: {e}", t0)
        log(f"{len(rekeys)} row(s) rekeyed in {ECONOMICS_WORKSHEET_PATH.name}; nothing emitted", t0)
        return 0
    rw_model = real_world_economics.load(REAL_WORLD_CONFIG_PATH, REAL_WORLD_ZONES_PATH)
    rw_by_region: dict[int, dict] = {}
    if rw_model is not None:
        rw_by_region, rw_stats = real_world_economics.region_economics(
            rw_model, labels, n_land, region_of, n_regions)
        log(f"real-world equivalents: {rw_stats['regions']} region(s) take their zone's share; "
            f"zones with no mod land: {rw_stats['zones_without_land'] or 'none'}", t0)
    econ_errors: list[str] = list(sheet_errors)
    econ_warnings: list[str] = []
    n_econ_sheet = n_econ_default = n_econ_placeholder = 0

    # --- per-region emission -------------------------------------------------
    blocks_by_file: dict[str, list[str]] = {stem: [] for stem in STATE_FILE_STEMS}
    keys_by_realm: dict[str, list[str]] = {}
    continent_of_realm: dict[str, str] = {f.realm: f.continent for f in legend.fills}
    continent_of_realm.update({r.realm: r.continent for r in addition_realms.values()})
    oos_keys: list[str] = []
    first_hub_by_realm: dict[str, raster.Color] = {}
    canon_names: dict[str, str] = {}
    loc_keys: list[str] = []
    n_stacked = 0
    sealed_coast_keys: list[str] = []
    n_sealed_coast = 0  # coastal states left port-less because their coast is impassable (#3704)
    n_sealed_stacked = 0  # pick_hubs -> stack_hubs downgrades caused by impassable provinces (#3704)

    # Anchor-driven hubs (#3665): the persisted anchor -> seeded-province index is
    # the single authority — no re-resolving an anchor from the bitmap. Map each
    # state region to {hub: (color, name)}; a duplicate (region, hub) is an error.
    hub_by_region: dict[int, dict[str, tuple[raster.Color, str]]] = {}
    if HUB_ANCHORS_INDEX_PATH.is_file():
        hub_index = json.loads(HUB_ANCHORS_INDEX_PATH.read_text(encoding="utf-8"))
        for h in hub_index["hubs"]:
            rid = int(h["region"])
            slot = hub_by_region.setdefault(rid, {})
            if h["hub"] in slot:
                raise SystemExit(
                    f"{HUB_ANCHORS_INDEX_PATH.name}: region {rid} has two '{h['hub']}' hubs "
                    f"('{slot[h['hub']][1]}' and '{h['name']}') — one worksheet row per (state, hub)")
            slot[h["hub"]] = (tuple(int(v) for v in h["province_color"]), h["name"])
    hub_loc_entries: list[tuple[str, str]] = []
    hub_unlisted_states = 0          # in-scope drawn states with an auto-picked slot
    hub_unnamed_regions: list[str] = []  # listed hubs whose region has no canon name

    for cell in sorted(land_regions["cells"], key=lambda c: int(state_number[int(c["region"])])):
        region_id = int(cell["region"])
        state_num = int(state_number[region_id])
        members = cell["provinces"]
        key = derived_keys.get(state_num, f"STATE_LAND_{state_num:03d}")
        if key in sea_keys:
            raise SystemExit(f"key collision: {key} is also defined in {SEAS_TXT_PATH.name}")
        if not (map_config.LAND_ID_START <= state_num < map_config.SEA_ID_START):
            raise SystemExit(f"{key}: id {state_num} outside land band "
                             f"[{map_config.LAND_ID_START}, {map_config.SEA_ID_START})")

        # `kind` (drawn vs placeholder), not vote count, decides in-scope vs
        # out-of-scope — a placeholder can graze the painting's crop and pick
        # up stray votes without being any less out-of-scope (see the note by
        # `placeholder_region_ids` above).
        is_drawn = region_id in drawn_region_ids
        assignment = assignments[region_id]
        if is_drawn:
            assert assignment.realm is not None, f"{key}: drawn region left unclassified"
            file_stem = assignment.file_stem
            realm = assignment.realm
        else:
            oos_slug = oos_continent_of[region_id]
            file_stem = OUT_OF_SCOPE_FILE_STEM[oos_slug]
            realm = None

        name = worksheet.names.get(state_num)
        if not name and not is_drawn:
            name = " ".join(part.capitalize() for part in oos_continent_of[region_id].split("_"))
        if name:
            canon_names[key] = name

        infos = [
            ProvinceInfo(
                color=province_info[p]["color"],
                centroid=(float(prov_cx[p]), float(prov_cy[p])),
                area=province_info[p]["area"],
                coastal=province_info[p]["coastal"],
                impassable=province_info[p]["impassable"],
            )
            for p in members
        ]
        # A port needs a PASSABLE coastal province: a state whose only coast is
        # impassable paint has no usable port, so it is emitted non-coastal (no
        # port / naval_exit) rather than failing the hub pick (#3704).
        coastal = any(info.coastal and not info.impassable for info in infos)
        if not coastal and any(info.coastal for info in infos):
            n_sealed_coast += 1
            sealed_coast_keys.append(key)
        needed = 5 if coastal else 4
        passable_infos = [info for info in infos if not info.impassable]
        if infos and not passable_infos:
            raise SystemExit(f"{key}: every province is impassable — a state needs passable land")

        row = econ_sheet.rows.get(key) if is_drawn else None
        rw = rw_by_region.get(region_id)
        state_default = default_econ if rw is None else schema.Economics(
            subsistence_building=rw["subsistence_building"], arable_land=rw["arable_land"],
            arable_resources=list(rw["arable_resources"]),
            capped_resources=dict(rw["capped_resources"]), resources=rw["resources"])
        econ = land_economics.resolve_economics(row, state_default)
        errs, warns = land_economics.check_economics(key, econ, coastal, catalog)
        econ_errors.extend(errs)
        econ_warnings.extend(warns)
        if not is_drawn:
            n_econ_placeholder += 1
        elif row is not None and row.has_values():
            n_econ_sheet += 1
        else:
            n_econ_default += 1

        state = schema.State(
            key=key,
            kind="land",
            macro=file_stem,
            geometry=schema.StateGeometry(kind="seeds", polygon=None, holes=[], seeds=[(0.0, 0.0)]),
            coastal=coastal,
            naval_exit=None,
            economics=econ,
            impassable=None,
        )

        # Listed settlements (#3665) preassign their seeded province to a hub slot;
        # unlisted slots fall through to the geometric auto-pick.
        anchor_hubs = hub_by_region.get(region_id, {})
        preassigned = {hub: col for hub, (col, _nm) in anchor_hubs.items()} or None
        if len(passable_infos) >= needed:
            hubs = pick_hubs(state, infos, CANVAS_W, WRAP_X, preassigned=preassigned)
        else:
            hubs = stack_hubs(passable_infos, coastal, preassigned=preassigned)
            n_stacked += 1
            if len(infos) >= needed:
                n_sealed_stacked += 1  # impassable paint, not size, forced the stacking
        # HUB_NAME loc for every listed hub, keyed on the state's EMITTED key (never
        # a stored key — the emitted key is what actually ships).
        for hub, (_col, hubname) in anchor_hubs.items():
            hub_loc_entries.append((f"HUB_NAME_{key}_{hub}", hubname))
        if anchor_hubs and is_drawn and not name:
            hub_unnamed_regions.append(key)  # a churny STATE_LAND_NNN key
        if is_drawn:
            slots = {"city", "port", "farm", "mine", "wood"} if coastal else {"city", "farm", "mine", "wood"}
            if slots - set(anchor_hubs):
                hub_unlisted_states += 1

        naval_exit_id = None
        if coastal:
            naval_exit_id = naval_exit_choice.get(region_id)
            if naval_exit_id is None:
                raise SystemExit(
                    f"{key}: coastal region has coastal provinces but no bordering sea "
                    f"state was found by the adjacency pass"
                )

        province_colors = [info.color for info in infos]
        blocks_by_file[file_stem].append(
            render_land_state(state, state_num, province_colors, hubs,
                              [info.color for info in infos if info.impassable], naval_exit_id))
        loc_keys.append(key)

        if realm is not None:
            keys_by_realm.setdefault(realm, []).append(key)
            if realm not in first_hub_by_realm:
                first_hub_by_realm[realm] = hubs["city"]
        else:
            oos_keys.append(key)

    n_blocks = sum(len(v) for v in blocks_by_file.values())
    log(f"{n_blocks} land states emitted ({n_stacked} hub-stacked placeholder/small regions"
        f"{f', {n_sealed_stacked} of them downgraded by impassable provinces' if n_sealed_stacked else ''})", t0)
    if n_sealed_coast:
        log(f"{n_sealed_coast} coastal state(s) emitted without a port: every coastal province "
            f"is impassable ({', '.join(sealed_coast_keys)}) - paint a passable coastal "
            f"pocket for a port", t0)

    for w in econ_warnings:
        log(f"WARNING: {w}", t0)
    log(f"economics: {n_econ_sheet} state(s) carry worksheet economics, {n_econ_default} on defaults, "
        f"{n_econ_placeholder} placeholder(s) untouched", t0)
    if econ_errors:
        raise SystemExit(f"{len(econ_errors)} land economics error(s) in "
                         f"{ECONOMICS_WORKSHEET_PATH.name}:\n  " + "\n  ".join(econ_errors))

    # --- write the state files (one per existing NN_<stem>.txt stub) --------
    for stem, filename in STATE_FILE_STEMS.items():
        blocks = blocks_by_file[stem]
        if not blocks:
            continue
        path = STATE_REGIONS_DIR / filename
        _write_bytes(path, render_state_file(blocks), bom=True)
        log(f"wrote {path.relative_to(MOD_ROOT)}  ({len(blocks)} states)", t0)

    # --- write the loc -------------------------------------------------------
    _write_bytes(LOC_PATH, _render_loc(loc_keys, canon_names, _read_existing_loc(LOC_PATH)), bom=True)
    log(f"wrote {LOC_PATH.relative_to(MOD_ROOT)}  ({len(loc_keys)} entries)", t0)

    # --- write the hub-name loc (#3665) -------------------------------------
    if hub_loc_entries:
        _write_bytes(HUB_LOC_PATH, _render_hub_loc(hub_loc_entries), bom=True)
        log(f"wrote {HUB_LOC_PATH.relative_to(MOD_ROOT)}  ({len(hub_loc_entries)} hub name(s))", t0)
        if hub_unlisted_states:
            log(f"  note: {hub_unlisted_states} in-scope drawn state(s) have auto-picked "
                f"(unlisted) hub slots — name them in hub_worksheet.json to override", t0)
        if hub_unnamed_regions:
            log(f"  WARNING: {len(hub_unnamed_regions)} listed hub(s) sit in an unnamed region "
                f"(churny STATE_LAND_NNN loc key): {sorted(set(hub_unnamed_regions))[:8]}", t0)

    # --- write the strategic regions, grouped by continent (board #2931) ----
    color_alloc = raster.ColorAllocator(map_config.SEED)
    continent_blocks: dict[str, list[str]] = {}
    for realm in sorted(keys_by_realm):
        continent = continent_of_realm[realm]
        block = _render_strategic_region_block(
            realm, keys_by_realm[realm],
            capital_color=first_hub_by_realm[realm], map_color=color_alloc.allocate())
        continent_blocks.setdefault(continent, []).append(block)

    for continent, blocks in sorted(continent_blocks.items()):
        path = STRATEGIC_REGIONS_DIR / f"{continent}_strategic_regions.txt"
        _write_bytes(path, "\n\n".join(blocks) + "\n", bom=True)
        log(f"wrote {path.relative_to(MOD_ROOT)}  ({len(blocks)} region(s))", t0)

    if oos_keys:
        oos_block = _render_strategic_region_block("out_of_scope_placeholders", oos_keys)
        path = STRATEGIC_REGIONS_DIR / "out_of_scope_strategic_regions.txt"
        _write_bytes(path, oos_block + "\n", bom=True)
        log(f"wrote {path.relative_to(MOD_ROOT)}  (1 region, {len(oos_keys)} states)", t0)

    # --- assertions -----------------------------------------------------------
    ids = [int(re.search(r"\bid\s*=\s*(\d+)", b).group(1))
           for blocks in blocks_by_file.values() for b in blocks]
    if len(set(ids)) != len(ids):
        raise SystemExit("invariant: land state ids are not unique")
    keys_emitted = set(loc_keys)
    if len(keys_emitted) != len(loc_keys):
        raise SystemExit("invariant: land state keys are not unique")
    if keys_emitted & sea_keys:
        raise SystemExit(f"invariant: key collision with 99_seas.txt: {keys_emitted & sea_keys}")
    all_region_keys = {k for keys in keys_by_realm.values() for k in keys} | set(oos_keys)
    if all_region_keys != keys_emitted:
        raise SystemExit("invariant: every emitted land state must belong to exactly one strategic region")

    # --- write the STATE-number identity index (board #4188) ---------------
    new_state_ids_index = {"canvas": [CANVAS_W, CANVAS_H], **new_state_ids_index}
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    LAND_STATE_IDS_PATH.write_text(json.dumps(new_state_ids_index, indent=1) + "\n", encoding="utf-8")
    log(f"wrote {LAND_STATE_IDS_PATH.relative_to(MOD_ROOT)}  "
        f"(high-water {new_state_ids_index['state_number_high_water']})", t0)

    log(f"done: {n_blocks} land states, {len(naval_exit_choice)} coastal naval exits, "
        f"{len(keys_by_realm)} realm region(s) + out-of-scope catch-all, {len(loc_keys)} loc entries", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
