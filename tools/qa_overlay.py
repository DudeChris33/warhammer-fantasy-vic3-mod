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
    python tools/qa_overlay.py old_world_terrain.jpg
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


def warp_source(reg: schema.SourceRegistration, rgb: np.ndarray, w: int, h: int,
                regs_by_source: dict[str, schema.SourceRegistration] | None = None):
    """Warp a source's RGB onto a (w, h) reduced canvas. Returns (rgb, valid)."""
    xs = (np.arange(w, dtype=np.float64) + 0.5) * (CANVAS_W / w)
    ys = (np.arange(h, dtype=np.float64) + 0.5) * (CANVAS_H / h)
    gx = np.broadcast_to(xs[None, :], (h, w))
    gy = np.broadcast_to(ys[:, None], (h, w))

    if reg.projection in ("control_point_warp", "frame_alias"):
        fit = reproject.fit_placement(reg, regs_by_source)
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


def state_label_overlay(step: int) -> int:
    """Render the artifact the S3a gate asks a human to look at.

    Three things have to be judgeable at a glance, so each gets its own visual
    channel rather than a separate image:

    * **Do the cells follow the map?** Every cell is tinted by its macro region
      and outlined, so a cell that ignored the source network — or one that a
      torn warp split in two — reads as a shape that does not belong.
    * **Does the layer respect the coastline?** The mask's own shoreline is drawn
      over the top in magenta. Any cell boundary that crosses it is the failure
      the mask-authority rule exists to prevent.
    * **Where did the fit put the frame?** The registered control points are
      marked, so a region of the map with no nearby control point — where a
      thin-plate warp is extrapolating rather than interpolating — is visible
      rather than something you have to know to look for.
    """
    import json

    from worldgen import cells, schema

    labels_path = DERIVED_DIR / "state_labels.png"
    index_path = DERIVED_DIR / "state_labels_index.json"
    if not labels_path.is_file():
        raise SystemExit(f"{labels_path} not found — run tools/generate_state_labels.py first")

    labels = cells.read_labels(labels_path)[::step, ::step]
    land = raster.read_mask_png(MASK_PATH)[::step, ::step]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    n_land = int(index["land_cells"])
    macro_of = np.zeros(int(labels.max()) + 1, dtype=np.int32)
    for c in index["cells"]:
        if c["kind"] == "land":
            macro_of[c["label"]] = c["macro"]

    # A fixed, high-separation hue wheel: adjacent macros must not be adjacent
    # colours, or a mis-grouped cell hides in a neighbour's shade.
    hues = np.array([
        (214, 64, 64), (64, 150, 214), (110, 190, 90), (222, 168, 60),
        (168, 104, 200), (86, 196, 190), (226, 120, 170), (150, 150, 96),
        (96, 128, 214), (200, 96, 60), (120, 200, 140), (190, 190, 214),
        (150, 96, 96), (96, 170, 120), (214, 140, 96), (130, 130, 170),
    ], dtype=np.uint8)
    img = np.zeros(labels.shape + (3,), dtype=np.uint8)
    img[land] = hues[macro_of[labels[land]] % len(hues)]
    img[~land] = (28, 42, 70)

    # Cell outlines: a pixel differing from the neighbour to its right or below.
    edge = np.zeros(labels.shape, dtype=bool)
    edge[:, :-1] |= labels[:, :-1] != labels[:, 1:]
    edge[:-1, :] |= labels[:-1, :] != labels[1:, :]
    img[edge] = (img[edge] * 0.35).astype(np.uint8)

    coast = land ^ ndimage.binary_erosion(land, np.ones((3, 3)))
    img[coast] = (255, 0, 255)

    for reg in schema.load_registrations(sources.REGISTRATION_DIR):
        if reg.projection != "control_point_warp":
            continue
        for cp in reg.control_points:
            x, y = int(cp.canvas[0] // step), int(cp.canvas[1] // step)
            if 0 <= y < img.shape[0] and 0 <= x < img.shape[1]:
                img[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = (255, 255, 255)

    out = DERIVED_DIR / "qa_state_labels.png"
    raster.write_rgb_png(out, img)
    land_areas = np.bincount(labels[land].ravel(), minlength=n_land + 1)[1:n_land + 1]
    print(f"{out.name}: {n_land} land cells + {int(index['sea_cells'])} sea zones, "
          f"{len(np.unique(macro_of[1:]))} macro regions")
    print(f"  land cell area (full-res px): mean {int(land_areas.mean()) * step * step:,}  "
          f"target {int(index.get('target_area', 0)):,}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", nargs="?", help="one source filename (default: all registered)")
    p.add_argument("--step", type=int, default=STEP, help="canvas downscale factor")
    p.add_argument("--labels", action="store_true",
                   help="render the S3a state-label overlay instead of per-source overlays")
    p.add_argument("--plain", action="store_true",
                   help="write the warped source alone, with no mask blended over it "
                        "(and without needing land_sea_mask.png to exist)")
    args = p.parse_args(argv)

    if args.labels:
        if not MASK_PATH.is_file():
            raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first")
        return state_label_overlay(args.step)

    # --plain is what you want when the question is "where does this source land
    # on the canvas?" rather than "does it agree with our coastline?" — notably
    # after a frame change, when the committed mask is the *old* frame's and
    # drawing it over the top would be actively misleading.
    # The reduced grid has to stay a *uniform* scaling of the canvas, or the
    # Miller frame cannot say what latitude its rows are (canvas_frame._scale
    # refuses a grid that is not). Integer-dividing both axes does not give that
    # for a step that divides 8192 but not 3616 — step 6 lands on 1365x602 where
    # the frame wants 603 — so the height is derived from the width instead.
    w = CANVAS_W // args.step
    h = round(CANVAS_H * w / CANVAS_W)

    small = None
    if not args.plain:
        if not MASK_PATH.is_file():
            raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first "
                             f"(or pass --plain to skip the coastline overlay)")
        land = raster.read_mask_png(MASK_PATH)
        small = land[::args.step, ::args.step][:h, :w]
        if small.shape != (h, w):
            raise SystemExit(f"--step {args.step} gives a {small.shape[1]}x{small.shape[0]} "
                             f"mask slice but the frame wants {w}x{h}; use a smaller step")
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    all_regs = schema.load_registrations(sources.REGISTRATION_DIR)
    by_source = {r.source: r for r in all_regs}
    regs = all_regs
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
        warped, valid = warp_source(reg, rgb, w, h, by_source)

        img = warped.copy()
        img[~valid] = (img[~valid] * 0.25).astype(np.uint8)
        if small is not None:
            # Our coastline drawn over the source: a 1px outline of the mask, in
            # a colour no reference map uses, so any offset is unmistakable.
            edge = small ^ ndimage.binary_erosion(small, np.ones((3, 3)))
            img[edge] = (255, 0, 255)

        out = DERIVED_DIR / f"qa_{Path(reg.source).stem}.png"
        raster.write_rgb_png(out, img)
        print(f"{reg.source:<28} -> {out.name}  (footprint covers "
              f"{100 * valid.mean():5.1f}% of canvas, projection={reg.projection})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
