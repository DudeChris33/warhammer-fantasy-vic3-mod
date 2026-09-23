#!/usr/bin/env python3
"""Generate the sea-zone label layer from the user's hand-drawn boundary network.

Board #2593 (decoupled from the land cut). Reads the committed land/sea mask and
the hand-drawn sea-zone source, and writes the committed sea-zone layer that the
bootable-map milestone will turn into ``provinces.png`` sea provinces +
``state_regions/99_seas.txt`` + ``default.map`` ``sea_starts``:

    tools/derived/land_sea_mask.png                  (the water authority)
    terraqueous_globe_reprojected - full.ora#sea_zones   (the drawn purple lines)
        -> worldgen.sea_zones.extract  (flood-fill water between the lines)
        -> tools/derived/sea_zones.png        16-bit labels, 0 = land, 1..n = zones
        -> tools/derived/sea_zones_index.json per-zone key / id / area / coastal

The layer is **not** wired into ``state_labels.png`` (that generator is blocked
on an unrelated land-boundary precedence collision); it is a standalone,
decoupled sea layer keyed on the vanilla 3000+ sea-state id band. Canon-sea
naming, zone merges (``config.merges``) and impassable flags
(``config.impassable_seeds`` and per-merge ``impassable``) all come from the
hand-authored ``tools/config/sea_zones.json``; adjacencies are still a
follow-up.

Deterministic: a pure function of the committed mask + the manifested drawn
source. Regenerate through it after an intentional source/mask change; never
hand-edit ``sea_zones.png`` / ``sea_zones_index.json``.

Usage::

    python tools/generate_sea_zones.py
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
from worldgen import cells, raster, schema, sea_naming, sea_state_ids, sea_zones, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
DERIVED_DIR = TOOLS_DIR / "derived"
CONFIG_DIR = TOOLS_DIR / "config"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
LAKE_MASK_PATH = DERIVED_DIR / "lake_mask.png"
LABELS_PATH = DERIVED_DIR / "sea_zones.png"
INDEX_PATH = DERIVED_DIR / "sea_zones_index.json"
SEA_ZONES_CONFIG = CONFIG_DIR / "sea_zones.json"

SEA_ZONES_SOURCE = sources.source_ref("sea_zones")
CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: Dilate the drawn line this many px to bridge anti-aliased gaps; drop zone
#: fragments below the floor. Both are stable knobs, committed here so the layer
#: is reproducible from source alone. The floor exists only to swallow the thin
#: offcuts the extraction leaves where the drawn line runs just off the mask
#: coast (and sub-pixel dilation dust) — every offcut is coastline-hugging, not a
#: hand-drawn open-water zone. 50 sits well below the smallest real hand-drawn
#: zone seen so far (354px, a river-mouth pocket) and comfortably above the
#: largest pure line-intersection artifact (16px) — confirmed 2026-08-31 against
#: the user's naming pass, which flagged every sub-floor fragment as "not real".
#: Set ``--merge-floor 1`` to keep every region between the drawn lines verbatim.
LINE_DILATE = 2
MERGE_FLOOR = 50


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--merge-floor", type=int, default=MERGE_FLOOR,
                    help=f"drop zone fragments below this many px (default {MERGE_FLOOR} = keep all "
                         f"regions the drawn lines make; raise it to swallow coastline offcuts)")
    ap.add_argument("--reassign", action="store_true",
                    help="re-allocate every sea-zone STATE id + key fresh in label order "
                         "(pre-#4191 behaviour) instead of honouring the committed sea_zones.png/"
                         "index — the deliberate escape hatch, pair it with a province --reassign")
    args = ap.parse_args(argv)
    merge_floor = args.merge_floor
    t0 = time.time()

    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first")
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

    config = schema.load_sea_zones(SEA_ZONES_CONFIG, canvas=(CANVAS_W, CANVAS_H))

    # Inland-lake companion layer (board #3742): if present, hold enclosed lakes
    # out of the navigable water so a lake never becomes a sea zone. Absent (the
    # Phase-A default) -> exclude=None -> byte-identical to the two-class run.
    lake_mask = None
    if LAKE_MASK_PATH.is_file():
        lake_mask = raster.read_mask_png(LAKE_MASK_PATH)
        if lake_mask.shape != (CANVAS_H, CANVAS_W):
            raise SystemExit(f"{LAKE_MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                             f"{lake_mask.shape[1]}x{lake_mask.shape[0]}")
        log(f"lake mask {int(lake_mask.sum()):,} px held out of the navigable water", t0)

    drawn = sources.load_source_image(SEA_ZONES_SOURCE)  # manifest-guarded RGB
    log("extracting hand-drawn sea zones ...", t0)
    zones = sea_zones.extract(land, drawn, LINE_DILATE, merge_floor, WRAP_X, log=log,
                              exclude=lake_mask)
    n = int(zones.max())

    coastal = cells.coastal_labels(zones, ~land, WRAP_X)  # inverted mask -> sea zones touching land
    areas = np.bincount(zones.ravel(), minlength=n + 1)

    # Canon naming (board #2698): give every zone a Warhammer sea group + key from
    # the hand-authored seed config, via a per-pixel seed-Voronoi plurality. The
    # index becomes fully self-describing (key / sea_group / display_name), so the
    # loc generator reads it alone and config-to-loc drift is impossible.
    log(f"naming {n} zones from {len(config.canon_seas)} canon seas "
        f"({len(config.overrides)} overrides, {len(config.merges)} merges, "
        f"{len(config.impassable_seeds)} standalone impassable, "
        f"{len(config.zone_names)} individually named) ...", t0)
    naming = sea_naming.assign(zones, land, config, WRAP_X, log=log)
    naming = sea_naming.apply_zone_names(naming, zones, config)
    naming, impassable, merged = sea_naming.apply_naming_overrides(naming, zones, config)
    naming = sea_naming.rekey_by_display_name(naming, zones, merged)

    # Stable STATE id + key across regens (board #4191): honour the committed
    # sea_zones.png/index so a zone whose geometry is unchanged keeps its id, key
    # and per-canon-sea ordinal even when other zones were added/removed. Read the
    # committed baseline BEFORE overwriting the label PNG below (guard each input
    # independently — a missing one selects the bootstrap == pre-#4191 behaviour).
    committed_labels = cells.read_labels(LABELS_PATH) if LABELS_PATH.is_file() else None
    committed_index = json.loads(INDEX_PATH.read_text(encoding="utf-8")) if INDEX_PATH.is_file() else None
    id_of, key_of, sea_id_high_water, ordinal_high_water = sea_state_ids.assign(
        zones, naming, merged, committed_labels, committed_index,
        map_config.SEA_ID_START, reassign=args.reassign, log=log)
    bootstrapped = args.reassign or committed_labels is None or committed_index is None
    log(f"stable sea ids: high-water {sea_id_high_water}, {len(ordinal_high_water)} named slugs, "
        f"{'fresh label order (reassign/bootstrap)' if bootstrapped else 'matched vs committed sea_zones.png'}", t0)

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    cells.write_labels(LABELS_PATH, zones)
    log(f"wrote {LABELS_PATH.relative_to(TOOLS_DIR.parent)}  ({n} sea zones)", t0)

    index = {
        "canvas": [CANVAS_W, CANVAS_H],
        "sea_zones": n,
        "id_start": map_config.SEA_ID_START,
        "sea_id_high_water": sea_id_high_water,
        "ordinal_high_water": {slug: ordinal_high_water[slug] for slug in sorted(ordinal_high_water)},
        "source": SEA_ZONES_SOURCE,
        "config": SEA_ZONES_CONFIG.name,
        "cells": [
            {
                "label": i,
                "key": key_of[i],
                "sea_group": naming[i].sea_group,
                "display_name": naming[i].display_name,
                "id": id_of[i],
                "area": int(areas[i]),
                "coastal": bool(coastal[i]),
                "impassable": i in impassable,
            }
            for i in range(1, n + 1)
        ],
    }
    INDEX_PATH.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    log(f"wrote {INDEX_PATH.relative_to(TOOLS_DIR.parent)}", t0)

    n_coastal = int(coastal[1:].sum())
    log(f"done: {n} sea zones ({n_coastal} coastal, {n - n_coastal} open-ocean), "
        f"area min {int(areas[1:].min()):,} / median {int(np.median(areas[1:])):,} / "
        f"max {int(areas[1:].max()):,} px", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
