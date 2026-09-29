#!/usr/bin/env python3
"""Review render: the first-pass province partition on the reprojected globe.

Board #2773. Reads the *committed* ``map_data/provinces.png`` +
``mapgen/derived/provinces_index.json`` (not a re-extract, so it shows exactly
what is committed) and draws it over the canvas-aligned reprojected globe
(``sources/terraqueous_globe_reprojected.png``, 8192x3616, overlays 1:1 —
feedback-review-render-on-reprojected-globe):

* **default** — province edges (magenta) + coast (cyan) over the globe, so the
  province density and border placement read against the terrain.
* **``--tinted``** — every province filled with a spread (golden-ratio hue)
  tint blended over the globe, so neighbouring provinces are easy to tell apart.

Local-only output: it embeds the source globe pixels, so it lands under
``mapgen/derived/``, which ``mapgen/.gitignore`` excludes from the repo. The
committed artifacts are ``provinces.png`` + its index from
``generate_provinces.py``; this is only the human-review picture (the visual
gate — the user's, per the autonomy model).

Usage::

    python mapgen/render_provinces_preview.py            # edges + coast
    python mapgen/render_provinces_preview.py --tinted    # spread-palette fills
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import raster, sources  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
PROVINCES_PATH = REPO_ROOT / "map_data" / "provinces.png"
INDEX_PATH = DERIVED_DIR / "provinces_index.json"
OUT_PATH = DERIVED_DIR / "provinces_partition_review.png"
OUT_HALF_PATH = DERIVED_DIR / "provinces_partition_review_half.png"
TINTED_OUT_PATH = DERIVED_DIR / "provinces_tinted_review.png"
TINTED_OUT_HALF_PATH = DERIVED_DIR / "provinces_tinted_review_half.png"

GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

LINE_RGB = (255, 0, 255)    # magenta — province boundaries
COAST_RGB = (0, 220, 255)   # cyan — the coastline (mask boundary)


def _read_labels() -> tuple[np.ndarray, dict]:
    """Reconstruct the province label image from the committed bitmap + index."""
    if not PROVINCES_PATH.is_file() or not INDEX_PATH.is_file():
        raise SystemExit(f"{PROVINCES_PATH} / {INDEX_PATH} not found — run generate_provinces.py first")
    rgb = raster.read_rgb_png(PROVINCES_PATH)
    if rgb.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{PROVINCES_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{rgb.shape[1]}x{rgb.shape[0]}")
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    key = ((rgb[..., 0].astype(np.int64) << 16)
           | (rgb[..., 1].astype(np.int64) << 8)
           | rgb[..., 2].astype(np.int64))
    color_to_label = {(int(r) << 16) | (int(g) << 8) | int(b): int(c["label"])
                      for c in index["cells"] for r, g, b in [c["color"]]}
    uniq, inv = np.unique(key, return_inverse=True)
    lut = np.array([color_to_label.get(int(k), 0) for k in uniq], dtype=np.int64)
    labels = lut[inv].reshape(key.shape).astype(np.int32)
    return labels, index


def _read_land() -> np.ndarray:
    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — the land/sea mask must exist first")
    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{land.shape[1]}x{land.shape[0]}")
    print(f"land mask {land.shape} land {100 * land.mean():.2f}%")
    return land


def _edges(lab: np.ndarray, wrap_x: bool) -> np.ndarray:
    edge = np.zeros(lab.shape, dtype=bool)
    edge[:, :-1] |= (lab[:, :-1] != lab[:, 1:]) & (lab[:, :-1] > 0) & (lab[:, 1:] > 0)
    edge[:-1, :] |= (lab[:-1, :] != lab[1:, :]) & (lab[:-1, :] > 0) & (lab[1:, :] > 0)
    if wrap_x:
        col = (lab[:, -1] != lab[:, 0]) & (lab[:, -1] > 0) & (lab[:, 0] > 0)
        edge[:, -1] |= col
        edge[:, 0] |= col
    return edge


def _spread_palette(n: int) -> np.ndarray:
    """A distinct, deterministic tint per label 1..n (golden-ratio hue hop)."""
    import colorsys

    out = np.zeros((n + 1, 3), dtype=np.float64)
    for i in range(1, n + 1):
        h = ((i - 1) * 0.61803398875) % 1.0
        s = 0.45 + 0.30 * (i % 2)
        r, g, b = colorsys.hsv_to_rgb(h, s, 0.98)
        out[i] = (r * 255, g * 255, b * 255)
    return out


def _write(img: np.ndarray, out_path: Path, half_path: Path, note: str) -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    raster.write_rgb_png(out_path, img)
    print(f"wrote {out_path}  ({note})")
    half = Image.fromarray(img, "RGB").resize((CANVAS_W // 2, CANVAS_H // 2),
                                              resample=Image.LANCZOS)
    half.save(half_path, format="PNG", optimize=False, compress_level=6)
    print(f"wrote {half_path}  ({CANVAS_W // 2}x{CANVAS_H // 2})")


def render_partition(t0: float) -> int:
    land = _read_land()
    lab, index = _read_labels()
    n = int(index["land_provinces"]) + int(index["sea_provinces"])
    print(f"  {index['land_provinces']} land + {index['sea_provinces']} sea provinces  "
          f"{time.time() - t0:.0f}s")

    edge = ndimage.binary_dilation(_edges(lab, WRAP_X), iterations=1)
    coast = land ^ ndimage.binary_erosion(land, np.ones((3, 3), dtype=bool))
    coast = ndimage.binary_dilation(coast, iterations=1)

    img = sources.load_source_image(GLOBE_SOURCE).copy()
    img[coast] = COAST_RGB
    img[edge] = LINE_RGB
    _write(img, OUT_PATH, OUT_HALF_PATH, f"{n} provinces, {int(edge.sum()):,} edge px")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


def render_tinted(t0: float) -> int:
    land = _read_land()
    lab, index = _read_labels()
    n = int(lab.max())
    print(f"  {index['land_provinces']} land + {index['sea_provinces']} sea provinces  "
          f"{time.time() - t0:.0f}s")

    palette = _spread_palette(n)
    tint = palette[lab]
    globe = sources.load_source_image(GLOBE_SOURCE).astype(np.float64)
    img = globe.copy()
    filled = lab > 0
    img[filled] = 0.45 * globe[filled] + 0.55 * tint[filled]
    img[ndimage.binary_dilation(_edges(lab, WRAP_X), iterations=1)] = (20, 20, 20)
    img = img.clip(0, 255).astype(np.uint8)
    _write(img, TINTED_OUT_PATH, TINTED_OUT_HALF_PATH, f"{n} provinces tinted")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tinted", action="store_true",
                    help="fill each province with a spread-palette tint (default: edges + coast)")
    args = ap.parse_args(argv)
    t0 = time.time()
    return render_tinted(t0) if args.tinted else render_partition(t0)


if __name__ == "__main__":
    raise SystemExit(main())
