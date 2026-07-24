#!/usr/bin/env python3
"""S2 generator: the whole-world land/sea mask and 16-bit heightmap.

Pipeline::

    sources/ljzbtm288r891.jpg  (SHA-256 verified)
        -> denoise -> LUT classify        (elevation + land, at SOURCE res)
        -> NE-II reproject                (to canvas res, blocked)
        -> morphological cleanup          -> tools/derived/land_sea_mask.png
        -> reproject at heightmap res
        -> + TW3 high-frequency relief    (inside its footprint, land only)
        -> encode + clamp to the mask     -> map_data/heightmap.png

Two ordering decisions carry most of the quality:

**Classify before reprojecting.** The LUT runs on the 4000x3256 source (13 M px),
not on the 16384x7232 target (118 M px). That is ~9x less work, and more
importantly it means the *elevation field* is what gets interpolated rather than
the *colours* — bilinear between two swatch colours can land on a third swatch's
colour and produce elevations that appear nowhere in the legend.

**The mask, not the elevation, defines the coastline.** The mask is built once at
canvas resolution and then forced onto the heightmap (nearest 2x, exact by
construction since the heightmap is exactly twice the canvas). Any land pixel is
pushed above sea level and any sea pixel below it, so the heightmap shoreline can
never contradict the mask that provinces.png will be cut from. Without that,
resampling alone would leave the two disagreeing by a pixel here and there — and
every such disagreement is a coastal province the engine renders underwater.

Usage::

    python tools/generate_heightmap.py            # write mask + heightmap
    python tools/generate_heightmap.py --mask-only # skip the 16-bit heightmap
    python tools/generate_heightmap.py --preview   # + downscaled PNGs for eyeballing
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import composite, ingest, raster, reproject, segment, sources, schema  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MAP_DATA_DIR = REPO_ROOT / "map_data"
LUT_PATH = TOOLS_DIR / "lut" / "terraqueous_elevation.json"

TERRAQUEOUS = "ljzbtm288r891.jpg"
TWW3 = "tww3_map_stitched.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
HEIGHT_W, HEIGHT_H = map_config.HEIGHTMAP_SIZE

#: Rows of the target processed per block. Bounds peak memory: a block holds two
#: float64 coordinate grids of (BLOCK x width), which at heightmap width is
#: ~2 MB per row — so this is the knob that keeps the run inside a few hundred MB.
BLOCK_ROWS = 256

#: Amplitude, in metres, of the high-frequency detail borrowed from the TW3
#: relief. Deliberately small: it sharpens ridge and valley texture that the
#: 14-band LUT cannot resolve, without letting a five-point warp restate absolute
#: elevation. The TW3 render is a shaded 3-D view, not an elevation ramp, so its
#: *absolute* brightness means nothing — only its local variation is information.
TWW3_DETAIL_M = 260.0

#: Sigma (in canvas px) of the low-pass used to extract that detail.
TWW3_DETAIL_SIGMA = 24.0

#: Minimum area, in canvas pixels, for an island or inland water body to survive
#: the final cleanup. 256 px is a ~16x16 blob, roughly 0.7 degrees square — below
#: that a feature cannot carry even one province, so keeping it would only add
#: engine objects nobody can see or play. Real archipelagos worth naming are
#: placed deliberately in a later phase, not rescued from resampling noise.
CANVAS_MIN_BLOB = 256


def log(msg: str, t0: float | None = None) -> None:
    stamp = f"  [{time.time() - t0:5.1f}s]" if t0 is not None else ""
    print(f"{msg}{stamp}", flush=True)


# ---------------------------------------------------------------------------
# Source preparation
# ---------------------------------------------------------------------------

def load_registrations() -> dict[str, schema.SourceRegistration]:
    regs = {r.source: r for r in schema.load_registrations(sources.REGISTRATION_DIR)}
    errors = sources.verify()
    if errors:
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit("sources failed verification — refusing to generate from unverified input")
    return regs


#: Majority-filter window applied to the source-space land flag. Sized to lose
#: the map's drawn strokes (graticule, rivers, borders) without moving coasts.
SOURCE_MAJORITY = 7

#: Minimum area, in *source* pixels, for a land or water blob to survive.
#: Place-name lettering set over the ocean is the target: each glyph is a
#: few hundred pixels, so it is removed here, at native size, where it is still
#: recognisably small — after reprojection to a 4x wider canvas the same glyph
#: would be several thousand pixels and indistinguishable from a real island.
SOURCE_MIN_BLOB = 900


def _crop_inside(reg: schema.SourceRegistration, shape) -> np.ndarray:
    """Boolean mask of the source pixels inside the record's crop (all, if none).

    Stats are reported over this only: two thirds of the Terraqueous image is page
    margin, title block and polar insets, all of which classify as paper -> land,
    so a whole-image land fraction would be meaningless.
    """
    inside = np.zeros(shape, dtype=bool)
    if reg.crop is not None:
        x0, y0, x1, y1 = (int(v) for v in reg.crop)
        inside[y0:y1, x0:x1] = True
    else:
        inside[:] = True
    return inside


def terraqueous_fields(reg: schema.SourceRegistration, elut: schema.ElevationLUT, t0: float):
    """Classified elevation + land mask in Terraqueous source pixel space.

    Thin wrapper over :func:`ingest.classify_source` (the shared core the fixture
    also runs) that adds the whole-world reporting.
    """
    rgb = sources.load_source_image(TERRAQUEOUS)
    log(f"  loaded {TERRAQUEOUS} {rgb.shape[1]}x{rgb.shape[0]}", t0)
    inside = _crop_inside(reg, rgb.shape[:2])

    fields = ingest.classify_source(
        rgb, elut, denoise_size=3, majority=SOURCE_MAJORITY,
        min_blob=SOURCE_MIN_BLOB, wrap_x=False,
    )
    log(f"  LUT colour distance: median {np.median(fields.dist[inside]):.1f} "
        f"p95 {np.percentile(fields.dist[inside], 95):.1f}", t0)
    log(f"  ink (lettering/graticule) erased: {100 * fields.ink[inside].mean():.2f}% "
        f"of the crop, inpainted from nearest non-ink neighbours", t0)
    log(f"  source land fraction after despeckle: {100 * (fields.land[inside] > 0.5).mean():.1f}%", t0)
    return fields.elev, fields.land, fields.dist


# ---------------------------------------------------------------------------
# TW3 relief detail
# ---------------------------------------------------------------------------

def tww3_detail(regs, land_mask: np.ndarray, t0: float):
    """Zero-mean high-frequency relief from the TW3 render, at canvas res.

    Returns ``(detail_m, valid)`` or ``(None, None)`` when the source is absent.
    The detail is a high-pass of the render's luminance: subtract a heavy
    Gaussian, normalise by a robust spread, scale to ``TWW3_DETAIL_M``. Being
    zero-mean is the whole point — it can add a ridge crest and a valley floor
    but cannot raise or lower a region's base elevation, so a registration error
    shows up as misplaced texture rather than as a displaced landmass.
    """
    reg = regs.get(TWW3)
    if reg is None:
        return None, None
    rgb = sources.load_source_image(TWW3)
    log(f"  loaded {TWW3} {rgb.shape[1]}x{rgb.shape[0]}", t0)
    fit = reproject.fit_warp(reg)
    log(f"  warp fit: interpolation residual rms {fit.rms_px:.3g} px", t0)

    luminance = rgb.astype(np.float32).mean(axis=2)
    x0, y0, x1, y1 = (int(v) for v in reg.footprint)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(CANVAS_W, x1), min(CANVAS_H, y1)

    detail = np.zeros((CANVAS_H, CANVAS_W), dtype=np.float32)
    valid = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
    sub_h, sub_w = y1 - y0, x1 - x0
    patch = np.empty((sub_h, sub_w), dtype=np.float32)
    inside = np.empty((sub_h, sub_w), dtype=bool)
    for by in range(0, sub_h, BLOCK_ROWS):
        be = min(sub_h, by + BLOCK_ROWS)
        rows = np.arange(y0 + by, y0 + be, dtype=np.float64)
        gx = np.broadcast_to(np.arange(x0, x1, dtype=np.float64)[None, :], (be - by, sub_w))
        gy = np.broadcast_to(rows[:, None], (be - by, sub_w))
        sx, sy = fit.to_source_px(gx, gy)
        inside[by:be] = reproject.crop_mask(reg, sx, sy)
        if reg.crop is not None:
            cx0, cy0, cx1, cy1 = reg.crop
            np.clip(sx, cx0, cx1, out=sx)
            np.clip(sy, cy0, cy1, out=sy)
        patch[by:be] = reproject.resample(luminance, sx, sy, order=1)

    from scipy import ndimage
    high = patch - ndimage.gaussian_filter(patch, sigma=TWW3_DETAIL_SIGMA, mode="nearest")
    spread = float(np.percentile(np.abs(high), 90)) or 1.0
    high = np.clip(high / spread, -2.0, 2.0) * TWW3_DETAIL_M

    detail[y0:y1, x0:x1] = high
    valid[y0:y1, x0:x1] = inside
    valid &= land_mask          # relief detail on land only; the sea floor is flat
    log(f"  TW3 detail: covers {100 * valid.mean():.2f}% of canvas "
        f"(+-{TWW3_DETAIL_M:.0f} m, spread {spread:.1f} lum)", t0)
    return detail, valid


# ---------------------------------------------------------------------------
# Cross-check against the independent satellite render
# ---------------------------------------------------------------------------

# NOTE — the whole-world satellite render (images.steamusercontent.jpg) was
# de-registered in S2 and is deliberately NOT consumed here.
#
# S1 gave it the role of "coarse global frame anchor + land/sea layout". Measured
# against the finished mask it cannot do that job. Its content band is 462x358
# (S1 had also mis-read the letterbox as a top bar when it is on the left and
# right), it is a cloudy Blue-Marble style view whose ocean is near-black, and
# sweeping the assumed latitude half-span from 60 to 100 degrees and the
# longitude offset from -20 to +20 produced agreement of 63.9%-69.0% with **no
# peak** — against a 60.0% chance level for two independent masks of this land
# fraction. A correct registration produces a sharp maximum; a flat response
# across every hypothesis means the image does not register, so any number quoted
# from it would be noise dressed as validation.
#
# Its registration record was removed rather than left committed-but-wrong, and
# the manifest marks it unregistered. The frame it was meant to anchor is now set
# by the Terraqueous NE-II fit, which is measured to 0.363 px.


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mask-only", action="store_true", help="stop after land_sea_mask.png")
    p.add_argument("--preview", action="store_true", help="also write downscaled preview PNGs")
    args = p.parse_args(argv)

    t0 = time.time()
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    MAP_DATA_DIR.mkdir(parents=True, exist_ok=True)

    log("verifying sources against the committed manifest...")
    regs = load_registrations()
    elut = schema.load_elevation_lut(LUT_PATH)
    log(f"  LUT: {len(elut.bands)} bands, {elut.sea_band_count} of them ocean", t0)

    reg = regs[TERRAQUEOUS]
    fit = reproject.fit_parametric(reg)
    log(f"NE-II fit from committed control points: centre=({fit.cx:.2f}, {fit.cy:.2f}) "
        f"scale=({fit.sx:.3f}, {fit.sy:.3f}) rms={fit.rms_px:.3f}px max={fit.max_px:.3f}px", t0)
    if fit.rms_px > 2.0:
        raise SystemExit(f"NE-II control points fit to {fit.rms_px:.2f} px rms — "
                         f"expected sub-pixel; the registration record looks edited")
    aniso = abs(fit.sx / fit.sy - 1.0)
    log(f"  anisotropy |sx/sy - 1| = {aniso:.5f} "
        f"({'isotropic, as a true NE-II rendering must be' if aniso < 0.01 else 'WARNING: not isotropic'})")

    log("classifying the Terraqueous ramp...")
    elev_src, land_src_f, _dist = terraqueous_fields(reg, elut, t0)

    log(f"reprojecting to canvas {CANVAS_W}x{CANVAS_H}...")
    terra_land = ingest.reproject_plane(
        reg, fit, land_src_f, CANVAS_W, CANVAS_H, block_rows=BLOCK_ROWS, order=1) > 0.5
    log(f"  raw land fraction {100 * terra_land.mean():.2f}%", t0)

    # --- coastline mosaic ------------------------------------------------
    # Resolved by *layer* precedence, not the records' overall precedence: the
    # Terraqueous globe is registered to sub-pixel accuracy and so owns the
    # shoreline (coastline 90) even though the regional sources outrank it for
    # boundaries and relief. Today it is the only layer that wins any pixel; the
    # mosaic is here so adding a better-registered regional coastline later is a
    # data change rather than a code change, and so the report says out loud
    # which source actually decided each part of the world.
    log("compositing the coastline layer...")
    mosaic = composite.Mosaic((CANVAS_H, CANVAS_W))
    mosaic.add(composite.Layer(
        name=f"{TERRAQUEOUS} (NE-II)",
        precedence=reg.precedence_for("coastline"),
        data=terra_land,
        valid=np.ones((CANVAS_H, CANVAS_W), dtype=bool),
    ))
    land_raw, covered = mosaic.resolve()
    for line in mosaic.coverage_report():
        print(line)
    if not covered.all():
        raise SystemExit("coastline mosaic left pixels uncovered — no source claims them")

    log("cleaning the land/sea mask...")
    land = segment.clean_land_mask(land_raw, min_island_area=CANVAS_MIN_BLOB,
                                   min_lake_area=CANVAS_MIN_BLOB,
                                   close_radius=2, open_radius=2, wrap_x=map_config.WRAP_X)
    stats = segment.mask_stats(land, wrap_x=map_config.WRAP_X)
    log(f"  land {100 * stats['land_fraction']:.2f}%  "
        f"land bodies {stats['land_bodies']}  water bodies {stats['water_bodies']}", t0)
    raster.write_mask_png(DERIVED_DIR / "land_sea_mask.png", land)
    log(f"  wrote {DERIVED_DIR / 'land_sea_mask.png'}", t0)

    if args.preview:
        _write_preview(land, DERIVED_DIR / "preview_land_sea.png")

    if args.mask_only:
        log("--mask-only: stopping before the heightmap.")
        return 0

    log("building relief detail...")
    detail, detail_valid = tww3_detail(regs, land, t0)

    log(f"writing heightmap {HEIGHT_W}x{HEIGHT_H} (16-bit)...")
    height = np.empty((HEIGHT_H, HEIGHT_W), dtype=np.uint16)
    for y0 in range(0, HEIGHT_H, BLOCK_ROWS):
        y1 = min(HEIGHT_H, y0 + BLOCK_ROWS)
        rows = np.arange(y0, y1)
        sx, sy = ingest.clamped_source_coords(reg, fit, rows, HEIGHT_W, HEIGHT_H)
        elev = reproject.resample(elev_src, sx, sy, order=1).astype(np.float32)
        blk_land = ingest.upscale2_rows(land, y0, y1)
        if detail is not None:
            d = ingest.upscale2_rows(detail_valid, y0, y1)
            elev += np.where(d, ingest.upscale2_rows(detail, y0, y1), 0.0).astype(np.float32)
        height[y0:y1] = ingest.encode_heightmap(
            elev, blk_land, sea_level=map_config.HEIGHT_SEA_LEVEL,
            units_per_metre=map_config.HEIGHT_UNITS_PER_METRE,
            shore_margin=map_config.HEIGHT_SHORE_MARGIN)
        if (y0 // BLOCK_ROWS) % 8 == 0:
            log(f"    rows {y0}/{HEIGHT_H}", t0)

    out = MAP_DATA_DIR / "heightmap.png"
    raster.write_gray16_png(out, height)
    size_mb = out.stat().st_size / (1 << 20)
    land_h = height[height >= map_config.HEIGHT_SEA_LEVEL]
    log(f"  wrote {out} ({size_mb:.1f} MB)", t0)
    log(f"  land heights: median {int(np.median(land_h))} p95 {int(np.percentile(land_h, 95))} "
        f"max {int(height.max())}  (vanilla: 5936 / 16742 / 53469)")

    if args.preview:
        _write_preview_gray(height, DERIVED_DIR / "preview_heightmap.png")
    log("done.", t0)
    return 0


def _write_preview(mask: np.ndarray, path: Path, step: int = 8) -> None:
    small = mask[::step, ::step]
    raster.write_rgb_png(path, np.where(small[..., None],
                                        np.array([90, 120, 70], dtype=np.uint8),
                                        np.array([30, 60, 110], dtype=np.uint8)))
    print(f"  preview -> {path}")


def _write_preview_gray(height: np.ndarray, path: Path, step: int = 16) -> None:
    small = height[::step, ::step].astype(np.float32)
    v = np.clip((small - 3000) / 20000.0, 0, 1)
    g = (v * 255).astype(np.uint8)
    raster.write_rgb_png(path, np.repeat(g[..., None], 3, axis=2))
    print(f"  preview -> {path}")


if __name__ == "__main__":
    raise SystemExit(main())
