#!/usr/bin/env python3
"""Review render: the sea-zone partition on the reprojected globe.

Board #2593. Draws the sea-zone division lines (from
``worldgen.sea_zones.extract`` — the same layer ``generate_sea_zones.py``
commits) over the canvas-aligned reprojected globe
(``sources/terraqueous_globe_reprojected.png``, 8192x3616, overlays 1:1), so the
hand-drawn partition can be eyeballed. Magenta = zone boundaries, cyan = coast.

Local-only output: it embeds the source globe pixels (like
``globe_named_review.png``), so it lands under ``tools/derived/``, which
``tools/.gitignore`` excludes from the repo. The committed artifact is the label
layer from ``generate_sea_zones.py``; this is only the human-review picture.

Usage::

    python tools/render_sea_zones_preview.py            # full canvas + half-size preview
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import raster, sea_zones, sources  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
OUT_PATH = DERIVED_DIR / "seas_partition_review.png"
OUT_HALF_PATH = DERIVED_DIR / "seas_partition_review_half.png"

SEA_ZONES_SOURCE = "terraqueous_globe_reprojected - sea_zones.png"
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

LINE_RGB = (255, 0, 255)    # magenta — the sea-zone division lines
COAST_RGB = (0, 220, 255)   # cyan — the coastline (mask boundary)


def _zone_edges(sea: np.ndarray, wrap_x: bool) -> np.ndarray:
    edge = np.zeros(sea.shape, dtype=bool)
    edge[:, :-1] |= (sea[:, :-1] != sea[:, 1:]) & (sea[:, :-1] > 0) & (sea[:, 1:] > 0)
    edge[:-1, :] |= (sea[:-1, :] != sea[1:, :]) & (sea[:-1, :] > 0) & (sea[1:, :] > 0)
    if wrap_x:
        col = (sea[:, -1] != sea[:, 0]) & (sea[:, -1] > 0) & (sea[:, 0] > 0)
        edge[:, -1] |= col
        edge[:, 0] |= col
    return edge


def main() -> int:
    t0 = time.time()
    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — the land/sea mask must exist first")
    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{land.shape[1]}x{land.shape[0]}")
    print(f"land mask {land.shape} land {100 * land.mean():.2f}%")

    drawn = sources.load_source_image(SEA_ZONES_SOURCE)
    print("extracting hand-drawn sea zones ...")
    sea = sea_zones.extract(land, drawn, wrap_x=WRAP_X, log=print)
    n = int(sea.max())
    print(f"  {n} sea zones  {time.time() - t0:.0f}s")

    edge = ndimage.binary_dilation(_zone_edges(sea, WRAP_X), iterations=2)
    coast = land ^ ndimage.binary_erosion(land, np.ones((3, 3), dtype=bool))
    coast = ndimage.binary_dilation(coast, iterations=1)

    globe = sources.load_source_image(GLOBE_SOURCE)
    img = globe.copy()
    img[coast] = COAST_RGB
    img[edge] = LINE_RGB

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    raster.write_rgb_png(OUT_PATH, img)
    print(f"wrote {OUT_PATH}  ({n} zones, {int(edge.sum()):,} line px)")
    half = Image.fromarray(img, "RGB").resize((CANVAS_W // 2, CANVAS_H // 2),
                                              resample=Image.LANCZOS)
    half.save(OUT_HALF_PATH, format="PNG", optimize=False, compress_level=6)
    print(f"wrote {OUT_HALF_PATH}  ({CANVAS_W // 2}x{CANVAS_H // 2})")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
