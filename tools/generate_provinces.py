#!/usr/bin/env python3
"""Generate the first-pass province bitmap from the hand-drawn state-region source.

Board #2773. The land mirror of ``generate_sea_zones.py``, decoupled from the
land cut / ``state_labels.png`` pipeline: reads the committed land/sea mask and
sea-zone layer plus the hand-drawn state-region source, and writes the whole-world
province image the game reads:

    tools/derived/land_sea_mask.png                          (the water authority)
    tools/derived/sea_zones.png                              (committed sea provinces)
    sources/terraqueous_globe_reprojected - state_regions.png (drawn magenta lines)
        -> worldgen.land_provinces.regions / .subdivide  (magenta -> regions -> provinces)
        -> map_data/provinces.png            8192x3616 RGB, one colour per province
        -> tools/derived/provinces_index.json per-province key / id / area / coastal

The magenta network is treated as **state_region** boundary hints (~677 cells);
each drawn region is subdivided into the **provinces beneath it** to reach a
target count, with the rule that no province crosses a magenta line. The already
finished sea zones become the sea provinces; each far continent that carries no
interior magenta stays a single placeholder province. Land provinces take labels
``1..N``, sea provinces ``N+1..N+M``; a seeded ``ColorAllocator`` gives each a
unique RGB colour.

Deterministic: a pure function of the committed mask + sea layer + the manifested
drawn source + ``map_config.SEED``, so a re-run reproduces byte-identical output —
the determinism core.md requires of a multiplayer-synchronized mod. Regenerate
through this script after an intentional source/mask change; never hand-edit
``provinces.png`` / ``provinces_index.json``.

Usage::

    python tools/generate_provinces.py
    python tools/generate_provinces.py --target 6000 --merge-floor 1500
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import cells, land_provinces, raster, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
SEA_LABELS_PATH = DERIVED_DIR / "sea_zones.png"
SEA_ZONES_INDEX_PATH = DERIVED_DIR / "sea_zones_index.json"
PROVINCES_PATH = REPO_ROOT / "map_data" / "provinces.png"
INDEX_PATH = DERIVED_DIR / "provinces_index.json"
LAND_REGIONS_INDEX_PATH = DERIVED_DIR / "land_regions_index.json"

STATE_REGIONS_SOURCE = "terraqueous_globe_reprojected - state_regions.png"
CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: Dilate the drawn magenta line this many px to bridge anti-aliased gaps.
LINE_DILATE = 2
#: Swallow region-stage offcuts below this many px (thin coastline-hugging slivers
#: the magenta-doubling-as-coast leaves) before the province cut.
MERGE_FLOOR = 1200
#: Target number of land-province seats shared across the drawn regions (user
#: directive 2026-08-23: the ~677 raw magenta cells are state-region hints, too
#: coarse for provinces — subdivide to ≥5,000 land provinces). Set above 5,000 so
#: the realised count clears the floor after the min-area sweep absorbs the finest
#: Voronoi offcuts; at the measured 3.85M-px drawn zone this lands ~6,070 land
#: provinces (~635 px each, close to vanilla's ~725 px/province globally).
PROVINCE_TARGET = 6000
#: A province piece below this many px is swallowed into a same-region neighbour
#: (never across a magenta boundary — the merge stays inside one region).
MIN_PROVINCE_AREA = 120


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=int, default=PROVINCE_TARGET,
                    help=f"target land provinces in the drawn Old World (default {PROVINCE_TARGET})")
    ap.add_argument("--merge-floor", type=int, default=MERGE_FLOOR,
                    help=f"swallow region-stage offcuts below this many px (default {MERGE_FLOOR})")
    ap.add_argument("--min-area", type=int, default=MIN_PROVINCE_AREA,
                    help=f"swallow province pieces below this many px (default {MIN_PROVINCE_AREA})")
    args = ap.parse_args(argv)
    t0 = time.time()

    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_coastline_mask.py first")
    if not SEA_LABELS_PATH.is_file():
        raise SystemExit(f"{SEA_LABELS_PATH} not found — run tools/generate_sea_zones.py first")
    errors = sources.verify()
    if errors:
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit("source manifest verification failed — refusing to generate")

    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{land.shape[1]}x{land.shape[0]}")
    log(f"land mask {land.shape} land {100 * land.mean():.2f}%", t0)

    drawn = sources.load_source_image(STATE_REGIONS_SOURCE)  # manifest-guarded RGB
    if drawn.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{STATE_REGIONS_SOURCE}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{drawn.shape[1]}x{drawn.shape[0]}")

    log("flood-filling the magenta network into state regions ...", t0)
    reg = land_provinces.regions(land, drawn, LINE_DILATE, args.merge_floor, WRAP_X, log=log)
    mag = land_provinces.magenta_lines(drawn)
    dmask = land_provinces.drawn_mask(land, mag, WRAP_X, log=log)
    log("subdividing the drawn regions into provinces ...", t0)
    land_lab, is_placeholder, reg_of = land_provinces.subdivide(reg, land, dmask, args.target,
                                                                WRAP_X, args.min_area, log=log)
    n_land = int(land_lab.max())

    sea_lab = cells.read_labels(SEA_LABELS_PATH)
    if sea_lab.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{SEA_LABELS_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{sea_lab.shape[1]}x{sea_lab.shape[0]}")
    n_sea = int(sea_lab.max())
    log(f"{n_land} land provinces + {n_sea} sea provinces", t0)

    if not SEA_ZONES_INDEX_PATH.is_file():
        raise SystemExit(f"{SEA_ZONES_INDEX_PATH} not found — run tools/generate_sea_zones.py first")
    sea_zones_index = json.loads(SEA_ZONES_INDEX_PATH.read_text(encoding="utf-8"))
    sea_impassable = {int(c["label"]): bool(c.get("impassable", False))
                      for c in sea_zones_index["cells"]}
    if set(sea_impassable) != set(range(1, n_sea + 1)):
        raise SystemExit(
            f"{SEA_ZONES_INDEX_PATH.name} cells don't match {SEA_LABELS_PATH.name}'s "
            f"{n_sea} labels 1..{n_sea} — regenerate sea zones first"
        )

    # Cross-consistency: the committed sea layer must tile exactly this mask's
    # water, and the land cut exactly its land. A stale sea/mask mismatch is a
    # hard failure — regenerate sea_zones.png — not a silently wrong bitmap.
    if not np.array_equal(sea_lab > 0, ~land):
        raise SystemExit(
            f"{SEA_LABELS_PATH.name} does not tile this mask's water: "
            f"{int((sea_lab > 0).sum()):,} sea px vs {int((~land).sum()):,} water px "
            f"— regenerate tools/generate_sea_zones.py against the committed mask")
    if not np.array_equal(land_lab > 0, land):
        raise SystemExit("internal error: land provinces do not tile the land mask")

    # Combine into one label layer: land 1..N, sea N+1..N+M.
    labels = land_lab.astype(np.int64)
    labels[~land] = sea_lab[~land].astype(np.int64) + n_land
    if int((labels == 0).sum()):
        raise SystemExit(f"{int((labels == 0).sum()):,} pixels carry no province label")

    # Deterministic unique colour per province, allocated in sorted label order.
    total = n_land + n_sea
    alloc = raster.ColorAllocator(map_config.SEED)
    palette = np.zeros((total + 1, 3), dtype=np.uint8)  # index 0 is the (0,0,0) sentinel
    for lab in range(1, total + 1):
        palette[lab] = alloc.allocate()
    rgb = palette[labels]

    PROVINCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    raster.write_rgb_png(PROVINCES_PATH, rgb)
    log(f"wrote {PROVINCES_PATH.relative_to(REPO_ROOT)}  "
        f"({total} provinces, {CANVAS_W}x{CANVAS_H} RGB)", t0)

    # Per-province index. Coastal is computed per kind: a land province is coastal
    # if it touches water, a sea province if it touches land.
    areas = np.bincount(labels.ravel(), minlength=total + 1)
    land_coastal = cells.coastal_labels(land_lab, land, WRAP_X)
    sea_coastal = cells.coastal_labels(sea_lab, ~land, WRAP_X)

    # Provinces share ONE continuous id space, exactly as vanilla's definition.csv
    # does — a province id is a unique sequential handle, and the bitmap colour is
    # the real key. The state-region id bands (map_config.LAND_ID_START /
    # SEA_ID_START, the vanilla 3000+ sea-STATE band) are NOT reused here: at
    # province scale the ~5,800 land ids would run straight through the 3000 sea
    # band and collide. So id == label: land 1..N, sea N+1..N+M, globally unique.
    land_id_start = map_config.LAND_ID_START  # 1
    sea_id_start = n_land + 1
    entries = []
    n_placeholder = 0
    for lab in range(1, n_land + 1):
        color = tuple(int(v) for v in palette[lab])
        # Out-of-scope far continents are kept whole but emitted PASSABLE: Vic3
        # stacks every hub on one province (vanilla STATE_DELAWARE/STATE_BUKOVINA),
        # so a landmass boots as a legal one-province state. The out-of-scope
        # signal is preserved separately as `placeholder` for downstream state
        # emission; `impassable` now honestly means impassable and is uniformly
        # False on land.
        placeholder = bool(is_placeholder[lab]) if lab < len(is_placeholder) else False
        n_placeholder += placeholder
        entries.append({
            "label": lab,
            "kind": "land",
            "color": color,
            "hex": raster.color_to_hex(color),
            "id": land_id_start + (lab - 1),  # == lab
            "area": int(areas[lab]),
            "coastal": bool(land_coastal[lab]) if lab < len(land_coastal) else False,
            "impassable": False,  # every land province is passable now
            "placeholder": placeholder,  # out-of-scope land kept whole, undetailed
        })
    for s in range(1, n_sea + 1):
        lab = n_land + s
        color = tuple(int(v) for v in palette[lab])
        entries.append({
            "label": lab,
            "kind": "sea",
            "color": color,
            "hex": raster.color_to_hex(color),
            "id": sea_id_start + (s - 1),  # == lab, continues after the land band
            "area": int(areas[lab]),
            "coastal": bool(sea_coastal[s]) if s < len(sea_coastal) else False,
            "impassable": sea_impassable[s],  # from sea_zones_index.json (config-driven)
            "placeholder": False,  # schema symmetry with land entries
        })

    index = {
        "canvas": [CANVAS_W, CANVAS_H],
        "source": STATE_REGIONS_SOURCE,
        "sea_source": SEA_LABELS_PATH.name,
        "land_provinces": n_land,
        "sea_provinces": n_sea,
        "impassable_land_provinces": 0,  # nothing is impassable — every landmass boots
        "impassable_sea_provinces": sum(sea_impassable.values()),  # from sea_zones.json config
        "placeholder_land_provinces": n_placeholder,  # out-of-scope land kept whole
        "land_id_start": land_id_start,
        "sea_id_start": sea_id_start,
        "cells": entries,
    }
    INDEX_PATH.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    log(f"wrote {INDEX_PATH.relative_to(REPO_ROOT)}", t0)

    # Persist the land province -> state-region grouping that subdivide already
    # computed in reg_of and used to throw away. #2930 emits land state_regions/*.txt
    # from this — the land mirror of sea_zones_index.json. Region-keyed, carrying
    # province LABELS only; provinces_index.json stays the colour authority. This
    # block writes a SEPARATE file and reads nothing above, so provinces.png and
    # provinces_index.json are byte-identical whether or not it runs.
    reg_count = int(reg.max())
    reg_areas = np.bincount(reg.ravel(), minlength=reg_count + 1)
    groups: dict[int, list[int]] = {}
    for lab in range(1, n_land + 1):
        groups.setdefault(int(reg_of[lab]), []).append(lab)
    # Totality, asserted on the REAL data at generation time (validate_map.py
    # --province-bitmap does not read this file, so a broken grouping must fail
    # loudly here): every land province lands in exactly one region, and every
    # region 1..R is populated.
    grouped = sorted(p for members in groups.values() for p in members)
    if grouped != list(range(1, n_land + 1)):
        raise SystemExit(
            f"land region grouping is not total: {len(grouped)} grouped provinces "
            f"vs {n_land} land provinces")
    if set(groups) != set(range(1, reg_count + 1)):
        raise SystemExit(
            f"land region grouping skips or invents a region id: got {sorted(groups)}, "
            f"expected 1..{reg_count}")
    region_cells = []
    n_drawn_regions = 0
    for r in range(1, reg_count + 1):
        members = sorted(groups[r])
        # A region is wholly drawn or wholly placeholder (a magenta barrier cannot
        # cross water, so a region nests in one landmass); all == any here.
        placeholder = all(bool(is_placeholder[lab]) for lab in members)
        n_drawn_regions += not placeholder
        region_cells.append({
            "region": r,
            "kind": "placeholder" if placeholder else "drawn",
            "area": int(reg_areas[r]),
            "provinces": members,
        })
    land_regions = {
        "canvas": [CANVAS_W, CANVAS_H],
        "source": STATE_REGIONS_SOURCE,
        "land_provinces": n_land,
        "regions": reg_count,
        "drawn_regions": n_drawn_regions,
        "placeholder_regions": reg_count - n_drawn_regions,
        "cells": region_cells,
    }
    LAND_REGIONS_INDEX_PATH.write_text(json.dumps(land_regions, indent=1) + "\n", encoding="utf-8")
    log(f"wrote {LAND_REGIONS_INDEX_PATH.relative_to(REPO_ROOT)} "
        f"({reg_count} regions: {n_drawn_regions} drawn, "
        f"{reg_count - n_drawn_regions} placeholder)", t0)

    land_areas = areas[1:n_land + 1]
    log(f"done: {n_land} land provinces ({n_placeholder} out-of-scope passable placeholders) "
        f"(area min {int(land_areas.min()):,} / median {int(np.median(land_areas)):,} / "
        f"max {int(land_areas.max()):,} px), {n_sea} sea provinces", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
