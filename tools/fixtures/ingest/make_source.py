#!/usr/bin/env python3
"""Build the synthetic ingestion source. Deterministic — no RNG, no wall clock.

The S2 ingestion path (verify -> classify -> de-ink -> despeckle -> reproject ->
segment) has to be regression-tested offline, and it cannot be tested against the
real ``sources/``: those are third-party imagery, gitignored by decision, so a
fixture built on them would not run on a clean clone.

So this paints a tiny world of our own pixels, deliberately containing every
feature the real pipeline has to survive:

* a stepped elevation ramp using the fixture LUT's own swatch colours;
* two landmasses, one of which **crosses the x=0 seam**, so wrap handling is
  exercised;
* an inland sea and a small island, for the lake/island area filters;
* **ink strokes** — a "label" block and thin ruled lines drawn across land in a
  dark colour close to the highest-elevation swatch, reproducing the exact defect
  that embossed place names into the real heightmap as mountain ranges;
* single-pixel speckle, for the majority filter.

Re-run after an intentional change, then ``run_fixture.py --update``::

    python tools/fixtures/ingest/make_source.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from worldgen import raster  # noqa: E402

W, H = 256, 128


def build() -> np.ndarray:
    lut = json.loads((HERE / "lut.json").read_text(encoding="utf-8"))
    bands = lut["bands"]
    sea_n = lut["sea_band_count"]
    deep = np.array(bands[0]["rgb"], dtype=np.uint8)
    shelf = np.array(bands[sea_n - 1]["rgb"], dtype=np.uint8)
    land_swatches = [np.array(b["rgb"], dtype=np.uint8) for b in bands[sea_n:]]

    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:, :] = deep

    yy, xx = np.mgrid[0:H, 0:W]

    # Continent A: an ellipse well inside the canvas, with an inland sea.
    ax, ay, arx, ary = 90.0, 64.0, 46.0, 34.0
    ra = ((xx - ax) / arx) ** 2 + ((yy - ay) / ary) ** 2
    land_a = ra <= 1.0
    lake = ((xx - 96.0) / 9.0) ** 2 + ((yy - 60.0) / 6.0) ** 2 <= 1.0

    # Continent B: straddles the x=0 seam (drawn at both edges).
    dx = np.minimum(np.abs(xx - 0.0), np.abs(xx - W))
    rb = (dx / 26.0) ** 2 + ((yy - 44.0) / 22.0) ** 2
    land_b = rb <= 1.0

    # A small island, big enough to survive the island-area filter.
    isle = ((xx - 190.0) / 7.0) ** 2 + ((yy - 96.0) / 6.0) ** 2 <= 1.0

    land = (land_a & ~lake) | land_b | isle

    # Elevation rises toward each landmass' centre, so the ramp is walked.
    depth = np.minimum(np.sqrt(np.clip(ra, 0, None)), np.sqrt(np.clip(rb, 0, None)))
    level = np.clip(((1.0 - depth) * len(land_swatches)).astype(int), 0, len(land_swatches) - 1)
    for i, sw in enumerate(land_swatches):
        img[land & (level == i)] = sw

    # A continental shelf ring, so the sea side of the ramp is walked too.
    shelf_ring = (~land) & (np.minimum(ra, rb) <= 1.45)
    img[shelf_ring] = shelf
    img[lake] = shelf

    # --- ink: the defect this fixture exists to catch --------------------
    ink = np.array(lut["ink_rgb"], dtype=np.uint8)
    # "Label" glyph blocks across the middle of continent A.
    for gx in range(70, 116, 8):
        img[58:66, gx:gx + 4] = ink
    # Thin ruled lines (a graticule) crossing both land and sea.
    img[::32, :] = ink
    img[:, ::64] = ink
    # Speckle: isolated pixels of the wrong class on each side of the coast.
    for (sy, sx) in ((30, 150), (31, 152), (100, 40), (12, 200), (70, 5)):
        img[sy, sx] = land_swatches[-1]
    return img


def main() -> int:
    img = build()
    out = HERE / "synthetic_world.png"
    raster.write_rgb_png(out, img)
    print(f"wrote {out} ({img.shape[1]}x{img.shape[0]})")
    print("now run: python tools/worldgen/sources.py  (fixture manifest) and run_fixture.py --update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
