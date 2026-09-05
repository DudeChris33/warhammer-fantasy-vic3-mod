#!/usr/bin/env python3
"""Emit the land engine files from the committed land-region grouping.

Board #2930 (bootable-map milestone #2700). The land mirror of
``generate_sea_regions.py``: reads ``tools/derived/land_regions_index.json``
(board #2928 — 708 regions: 281 drawn + 427 out-of-scope placeholders) plus the
colour authority ``tools/derived/provinces_index.json`` and the sea canon
``tools/derived/sea_zones_index.json``, and writes:

* ``map_data/state_regions/00_norsca.txt`` — one ``STATE_LAND_NNN`` block per
  region (all 708), with hubs, placeholder economics and, for coastal regions,
  ``port`` + ``naval_exit_id``. **No realm/macro split** — every region lands
  in this single file (user decision 2026-09-04; #2931 does the real 20-file
  division). The other 19 macro stub files are left untouched.
* ``common/strategic_regions/land_strategic_regions.txt`` — one
  ``region_old_world`` block covering every land state (a real per-realm split
  is #2931's job too; nothing here is designed to survive that rewrite).
* ``localization/english/map/wh_land_states_l_english.yml`` — placeholder loc,
  one ``STATE_*:0 "<pretty name>" # AUTOGEN`` per state.

Run ``tools/render_land_regions_preview.py`` afterwards for the numbered
review render + CSV worksheet — a naming aid for the user's canon pass in
#2931. It drapes the real TWW3 parchment art under the numbered regions
(reusing ``project_regions.py``'s five-crop registration) rather than
guessing a name algorithmically: an earlier cut of this pipeline guessed the
nearest real-world vanilla Vic3 state by longitude/latitude (rejected —
coincidental Earth-geography proximity means nothing on a fictional world),
and OCR of the parchment itself was tried and failed in practice (Tesseract
garbled almost everything on this stylised, curved-baseline font). The user
chose to drop automated guessing and read real names off the render instead
(2026-09-05).

Deterministic: a pure function of the three committed indices +
``map_data/provinces.png`` + ``map_config.SEED`` (only used for the strategic
region's cosmetic ``map_color``). Regenerate through this script after an
intentional upstream change; never hand-edit its outputs.

Usage::

    python tools/generate_land_regions.py
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
from worldgen import raster, schema  # noqa: E402
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
PROVINCES_PNG_PATH = MOD_ROOT / "map_data" / "provinces.png"
SEAS_TXT_PATH = MOD_ROOT / "map_data" / "state_regions" / "99_seas.txt"

STATE_FILE_PATH = MOD_ROOT / "map_data" / "state_regions" / "00_norsca.txt"
STRATEGIC_REGIONS_PATH = MOD_ROOT / "common" / "strategic_regions" / "land_strategic_regions.txt"
LOC_PATH = MOD_ROOT / "localization" / "english" / "map" / "wh_land_states_l_english.yml"
BUILDINGS_DIR = MOD_ROOT / "common" / "buildings"

BOM = b"\xef\xbb\xbf"
INDENT = "\t"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: The single macro file every region lands in (user decision 2026-09-04 — see
#: module docstring). Purely a bookkeeping stem; #2931 overwrites it wholesale.
MACRO_STEM = "norsca"

#: Placeholder economics (schema.Economics — "values only need to parse"),
#: verified at generation time to reference only building ids that actually
#: exist under common/buildings/ (challenge #2 in the plan).
SUBSISTENCE_BUILDING = "building_subsistence_farm"
ARABLE_LAND = 10
ARABLE_RESOURCES = ["building_wheat_farm", "building_livestock_ranch"]
CAPPED_RESOURCES = {"building_logging_camp": 10}


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
# Building-id verification (challenge #2 — never trust an unverified reference)
# ---------------------------------------------------------------------------

def _verify_building_ids(buildings_dir: Path, ids: set[str]) -> None:
    pattern = re.compile(r"^(building_\w+)\s*=\s*\{", re.MULTILINE)
    found: set[str] = set()
    for path in sorted(buildings_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        found.update(pattern.findall(text))
    missing = sorted(ids - found)
    if missing:
        raise SystemExit(
            f"placeholder economics references undefined building id(s) "
            f"(not found under {buildings_dir}): {missing}"
        )


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
    sea_mask = labels > n_land

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

def _render_land_strategic_region(capital_color: raster.Color, map_color: raster.Color,
                                  state_keys: list[str]) -> str:
    r, g, b = map_color
    lines = [
        "region_old_world = {",
        f"{INDENT}capital_province = {raster.color_to_hex(capital_color)}",
        f"{INDENT}map_color = {{ {r} {g} {b} }}",
        f"{INDENT}states = {{ {' '.join(state_keys)} }}",
        "}",
    ]
    return "\n".join(lines) + "\n"


def _render_loc(keys: list[str]) -> str:
    lines = ["l_english:"]
    for key in keys:
        lines.append(f' {key}:0 "{_pretty_name(key)}" {map_config.AUTOGEN_MARKER}')
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
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

    all_ids = {SUBSISTENCE_BUILDING, *ARABLE_RESOURCES, *CAPPED_RESOURCES}
    _verify_building_ids(BUILDINGS_DIR, all_ids)
    log(f"verified {len(all_ids)} placeholder building id(s) exist under {BUILDINGS_DIR.name}/", t0)

    # --- province info + region membership --------------------------------
    province_info: dict[int, dict] = {}
    for c in prov_index["cells"]:
        if c["kind"] != "land":
            continue
        province_info[int(c["label"])] = {
            "color": tuple(int(v) for v in c["color"]),
            "area": int(c["area"]),
            "coastal": bool(c["coastal"]),
        }

    region_of = np.zeros(n_land + 1, dtype=np.int64)
    for cell in land_regions["cells"]:
        for p in cell["provinces"]:
            region_of[p] = int(cell["region"])
    if not (region_of[1:] > 0).all():
        raise SystemExit("land_regions_index.json does not cover every land province")

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
    if not (prov_counts[1:] > 0).all():
        raise SystemExit("a land province has no pixels in provinces.png")
    log("province centroids computed", t0)

    # --- naval_exit: region -> bordering sea-state id ----------------------
    sea_state_of_zone = _sea_state_of_zone(sea_index["cells"], n_sea)
    naval_exit_choice = _naval_exit_choices(labels, n_land, region_of, sea_state_of_zone)
    log(f"naval_exit adjacency resolved for {len(naval_exit_choice)} coastal region(s)", t0)

    # --- placeholder economics (verified building ids, shared by every state)
    econ = schema.Economics(
        subsistence_building=SUBSISTENCE_BUILDING,
        arable_land=ARABLE_LAND,
        arable_resources=list(ARABLE_RESOURCES),
        capped_resources=dict(CAPPED_RESOURCES),
    )

    # --- key-collision guard against the sea file --------------------------
    sea_keys: set[str] = set()
    if SEAS_TXT_PATH.is_file():
        sea_keys = set(re.findall(r"(STATE_\w+)\s*=\s*\{", SEAS_TXT_PATH.read_text(encoding="utf-8-sig")))

    # --- per-region emission -------------------------------------------------
    blocks: list[str] = []
    loc_keys: list[str] = []
    first_city_color: raster.Color | None = None
    n_stacked = 0

    for cell in sorted(land_regions["cells"], key=lambda c: c["region"]):
        region_id = int(cell["region"])
        members = cell["provinces"]
        key = f"STATE_LAND_{region_id:03d}"
        if key in sea_keys:
            raise SystemExit(f"key collision: {key} is also defined in {SEAS_TXT_PATH.name}")
        if not (map_config.LAND_ID_START <= region_id < map_config.SEA_ID_START):
            raise SystemExit(f"{key}: id {region_id} outside land band "
                             f"[{map_config.LAND_ID_START}, {map_config.SEA_ID_START})")

        infos = [
            ProvinceInfo(
                color=province_info[p]["color"],
                centroid=(float(prov_cx[p]), float(prov_cy[p])),
                area=province_info[p]["area"],
                coastal=province_info[p]["coastal"],
                impassable=False,
            )
            for p in members
        ]
        coastal = any(info.coastal for info in infos)
        needed = 5 if coastal else 4

        state = schema.State(
            key=key,
            kind="land",
            macro=MACRO_STEM,
            geometry=schema.StateGeometry(kind="seeds", polygon=None, holes=[], seeds=[(0.0, 0.0)]),
            coastal=coastal,
            naval_exit=None,
            economics=econ,
            impassable=None,
        )

        if len(infos) >= needed:
            hubs = pick_hubs(state, infos, CANVAS_W, WRAP_X)
        else:
            hubs = stack_hubs(infos, coastal)
            n_stacked += 1

        naval_exit_id = None
        if coastal:
            naval_exit_id = naval_exit_choice.get(region_id)
            if naval_exit_id is None:
                raise SystemExit(
                    f"{key}: coastal region has coastal provinces but no bordering sea "
                    f"state was found by the adjacency pass"
                )

        province_colors = [info.color for info in infos]
        blocks.append(render_land_state(state, region_id, province_colors, hubs, [], naval_exit_id))
        loc_keys.append(key)
        if region_id == 1:
            first_city_color = hubs["city"]

    log(f"{len(blocks)} land states emitted ({n_stacked} hub-stacked placeholder/small regions)", t0)

    # --- write the state file ----------------------------------------------
    _write_bytes(STATE_FILE_PATH, render_state_file(blocks), bom=True)
    log(f"wrote {STATE_FILE_PATH.relative_to(MOD_ROOT)}  ({len(blocks)} states)", t0)

    # --- write the loc -------------------------------------------------------
    _write_bytes(LOC_PATH, _render_loc(loc_keys), bom=True)
    log(f"wrote {LOC_PATH.relative_to(MOD_ROOT)}  ({len(loc_keys)} entries)", t0)

    # --- write the land strategic region -------------------------------------
    assert first_city_color is not None, "region 1 must exist and have been emitted"
    map_color = raster.ColorAllocator(map_config.SEED).allocate()
    _write_bytes(
        STRATEGIC_REGIONS_PATH,
        _render_land_strategic_region(first_city_color, map_color, loc_keys),
        bom=True,
    )
    log(f"wrote {STRATEGIC_REGIONS_PATH.relative_to(MOD_ROOT)}  (1 region, {len(loc_keys)} states)", t0)

    # --- assertions -----------------------------------------------------------
    ids = [int(re.search(r"\bid\s*=\s*(\d+)", b).group(1)) for b in blocks]
    if len(set(ids)) != len(ids):
        raise SystemExit("invariant: land state ids are not unique")
    keys_emitted = set(loc_keys)
    if len(keys_emitted) != len(loc_keys):
        raise SystemExit("invariant: land state keys are not unique")
    if keys_emitted & sea_keys:
        raise SystemExit(f"invariant: key collision with 99_seas.txt: {keys_emitted & sea_keys}")

    log(f"done: {len(blocks)} land states, {len(naval_exit_choice)} coastal naval exits, "
        f"1 strategic region, {len(loc_keys)} loc entries", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
