#!/usr/bin/env python3
"""Generate the sea-zone label layer from the user's hand-drawn boundary network.

Board #2593 (decoupled from the land cut). Reads the committed land/sea mask and
the hand-drawn sea-zone source, and writes the committed sea-zone layer that the
bootable-map milestone will turn into ``provinces.png`` sea provinces +
``state_regions/99_seas.txt`` + ``default.map`` ``sea_starts``:

    tools/derived/land_sea_mask.png                  (the water authority)
    sources/terraqueous_globe_reprojected - sea_zones.png   (the drawn purple lines)
        -> worldgen.sea_zones.extract  (flood-fill water between the lines)
        -> tools/derived/sea_zones.png        16-bit labels, 0 = land, 1..n = zones
        -> tools/derived/sea_zones_index.json per-zone key / id / area / coastal

The layer is **not** wired into ``state_labels.png`` (that generator is blocked
on an unrelated land-boundary precedence collision); it is a standalone,
decoupled sea layer keyed on the vanilla 3000+ sea-state id band. Naming
(canon sea groups), impassable flags and adjacencies are a follow-up.

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
from worldgen import cells, raster, schema, sea_naming, sea_zones, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
DERIVED_DIR = TOOLS_DIR / "derived"
CONFIG_DIR = TOOLS_DIR / "config"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
LABELS_PATH = DERIVED_DIR / "sea_zones.png"
INDEX_PATH = DERIVED_DIR / "sea_zones_index.json"
SEA_ZONES_CONFIG = CONFIG_DIR / "sea_zones.json"

SEA_ZONES_SOURCE = "terraqueous_globe_reprojected - sea_zones.png"
CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: Dilate the drawn line this many px to bridge anti-aliased gaps; drop zone
#: fragments below the floor. Both are stable knobs, committed here so the layer
#: is reproducible from source alone. The floor exists only to swallow the thin
#: offcuts the extraction leaves where the drawn line runs just off the mask
#: coast (and sub-pixel dilation dust) — every offcut is coastline-hugging, not a
#: hand-drawn open-water zone. Set ``--merge-floor 1`` to keep every region
#: between the drawn lines (the user's partition verbatim, nothing merged).
LINE_DILATE = 2
MERGE_FLOOR = 1


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--merge-floor", type=int, default=MERGE_FLOOR,
                    help=f"drop zone fragments below this many px (default {MERGE_FLOOR} = keep all "
                         f"regions the drawn lines make; raise it to swallow coastline offcuts)")
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

    drawn = sources.load_source_image(SEA_ZONES_SOURCE)  # manifest-guarded RGB
    log("extracting hand-drawn sea zones ...", t0)
    zones = sea_zones.extract(land, drawn, LINE_DILATE, merge_floor, WRAP_X, log=log)
    n = int(zones.max())

    coastal = cells.coastal_labels(zones, ~land, WRAP_X)  # inverted mask -> sea zones touching land
    areas = np.bincount(zones.ravel(), minlength=n + 1)

    # Canon naming (board #2698): give every zone a Warhammer sea group + key from
    # the hand-authored seed config, via a per-pixel seed-Voronoi plurality. The
    # index becomes fully self-describing (key / sea_group / display_name), so the
    # loc generator reads it alone and config-to-loc drift is impossible.
    config = schema.load_sea_zones(SEA_ZONES_CONFIG, canvas=(CANVAS_W, CANVAS_H))
    log(f"naming {n} zones from {len(config.canon_seas)} canon seas "
        f"({len(config.overrides)} overrides) ...", t0)
    naming = sea_naming.assign(zones, land, config, WRAP_X, log=log)

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    cells.write_labels(LABELS_PATH, zones)
    log(f"wrote {LABELS_PATH.relative_to(TOOLS_DIR.parent)}  ({n} sea zones)", t0)

    index = {
        "canvas": [CANVAS_W, CANVAS_H],
        "sea_zones": n,
        "id_start": map_config.SEA_ID_START,
        "source": SEA_ZONES_SOURCE,
        "config": SEA_ZONES_CONFIG.name,
        "cells": [
            {
                "label": i,
                "key": naming[i].key,
                "sea_group": naming[i].sea_group,
                "display_name": naming[i].display_name,
                "id": map_config.SEA_ID_START + (i - 1),
                "area": int(areas[i]),
                "coastal": bool(coastal[i]),
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
