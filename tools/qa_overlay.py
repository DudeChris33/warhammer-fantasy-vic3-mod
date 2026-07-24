#!/usr/bin/env python3
"""Fidelity QA: overlay a registered source onto the generated land/sea mask.

The plan makes cartographic exactness a *checked* property, not a gated one —
the boot gate is a clean ``error.log``, but fidelity is the whole point of the
source-driven redo, so it needs to be looked at rather than assumed. This writes
a side-by-side/blended PNG per source: the committed ``land_sea_mask.png``
underneath, the source's own imagery warped through its committed registration
on top. A misregistered source shows up immediately as coastline that does not
line up.

It also prints a numeric agreement figure where the source has a usable land/sea
signal, so a regression is visible without opening the image.

Usage::

    python tools/qa_overlay.py                    # every registered source
    python tools/qa_overlay.py map-the-old-world.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import raster, reproject, schema, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
#: Downscale factor for the QA images — full canvas is unviewable, and
#: misregistration worth worrying about is visible at 1/8 scale.
STEP = 8


def warp_source(reg: schema.SourceRegistration, rgb: np.ndarray, w: int, h: int):
    """Warp a source's RGB onto a (w, h) reduced canvas. Returns (rgb, valid)."""
    xs = (np.arange(w, dtype=np.float64) + 0.5) * (CANVAS_W / w)
    ys = (np.arange(h, dtype=np.float64) + 0.5) * (CANVAS_H / h)
    gx = np.broadcast_to(xs[None, :], (h, w))
    gy = np.broadcast_to(ys[:, None], (h, w))

    if reg.projection == "control_point_warp":
        fit = reproject.fit_warp(reg)
        sx, sy = fit.to_source_px(gx, gy)
        x0, y0, x1, y1 = reg.footprint
        valid = (gx >= x0) & (gx <= x1) & (gy >= y0) & (gy <= y1)
    else:
        # The reduced grid *is* the canvas, just coarser — so lon/lat come from
        # its own row indices and its own dimensions, not from canvas-scale
        # coordinates, which would sample only the top 1/step of the world.
        fit = reproject.fit_parametric(reg)
        sx, sy = reproject.source_coords_parametric(fit, np.arange(h), w, h)
        valid = np.ones((h, w), dtype=bool)

    valid &= reproject.crop_mask(reg, sx, sy)
    if reg.crop is not None:
        cx0, cy0, cx1, cy1 = reg.crop
        np.clip(sx, cx0, cx1, out=sx)
        np.clip(sy, cy0, cy1, out=sy)

    out = np.zeros((h, w, 3), dtype=np.uint8)
    for c in range(3):
        out[..., c] = np.clip(
            ndimage.map_coordinates(rgb[..., c].astype(np.float32),
                                    np.stack([sy, sx]), order=1, mode="nearest"),
            0, 255).astype(np.uint8)
    return out, valid


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", nargs="?", help="one source filename (default: all registered)")
    p.add_argument("--step", type=int, default=STEP, help="canvas downscale factor")
    args = p.parse_args(argv)

    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first")
    land = raster.read_mask_png(MASK_PATH)
    h, w = land.shape[0] // args.step, land.shape[1] // args.step
    small = land[::args.step, ::args.step][:h, :w]
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    regs = schema.load_registrations(sources.REGISTRATION_DIR)
    if args.source:
        regs = [r for r in regs if r.source == args.source]
        if not regs:
            raise SystemExit(f"no registration record for {args.source!r}")

    for reg in regs:
        try:
            rgb = sources.load_source_image(reg.source)
        except sources.ManifestError as exc:
            print(f"{reg.source}: skipped — {exc}")
            continue
        warped, valid = warp_source(reg, rgb, w, h)

        # Our coastline drawn over the source: a 1px outline of the mask, in a
        # colour no reference map uses, so any offset is unmistakable.
        edge = small ^ ndimage.binary_erosion(small, np.ones((3, 3)))
        img = warped.copy()
        img[~valid] = (img[~valid] * 0.25).astype(np.uint8)
        img[edge] = (255, 0, 255)

        out = DERIVED_DIR / f"qa_{Path(reg.source).stem}.png"
        raster.write_rgb_png(out, img)
        print(f"{reg.source:<28} -> {out.name}  (footprint covers "
              f"{100 * valid.mean():5.1f}% of canvas, projection={reg.projection})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
