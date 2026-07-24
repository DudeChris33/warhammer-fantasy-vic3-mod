"""The ingestion core — one code path shared by the real run and the fixture.

``generate_heightmap.py`` orchestrates the real whole-world build (logging,
mosaic, the TW3 relief layer, the map-editor hand-off); the offline fixture
(``run_fixture.py``) drives a tiny synthetic world through the same steps. If the
two used *different* code, the fixture would regression-test a parallel
reimplementation and prove nothing about the generator. So every step that is not
pure orchestration lives here, parameterised by canvas size and filter widths,
and both callers import it.

The steps, in order (source space, then canvas space):

    denoise -> classify -> de-ink -> despeckle -> smooth      (source res)
    reproject -> clean land mask                              (canvas res)
    encode with the shoreline forced to the mask             (heightmap res)

Everything is deterministic: no RNG, no wall-clock, no threaded kernels — the
same inputs give byte-identical output, which is what the fixture pins.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from worldgen import lut, reproject, schema, segment

# ---------------------------------------------------------------------------
# Source-space classification (the novel de-ink / despeckle stage)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceFields:
    """Everything the classify stage produces, at *source* resolution.

    ``elev`` is smoothed metres, ``land`` a smoothed 0..1 land fraction (float so
    the reprojected shoreline lands on a sub-pixel boundary rather than a
    stair-stepped one). ``dist`` (colour distance to the winning swatch) and
    ``ink`` (the erased lettering/graticule mask) are carried out for the caller
    to report on — they are diagnostics, not further inputs.
    """

    elev: np.ndarray
    land: np.ndarray
    dist: np.ndarray
    ink: np.ndarray


def classify_source(
    rgb: np.ndarray,
    elut: schema.ElevationLUT,
    *,
    denoise_size: int = 3,
    ink_dilate: int = lut.INK_DILATE,
    majority: int = 7,
    min_blob: int = 900,
    wrap_x: bool = False,
    elev_sigma: float = 2.0,
    land_sigma: float = 1.0,
) -> SourceFields:
    """Colour image -> smoothed elevation + land fraction, with ink removed.

    The de-ink step is the one that matters most and is easiest to get wrong: the
    reference map's lettering and graticule classify as the darkest (highest)
    swatch, so without removing them every place name embosses into the heightmap
    as a mountain range. It is done here, at source resolution, before anything is
    reprojected — a stroke is still a few pixels wide here and its neighbours can
    fill it; after a 2-4x upscale it would be an unfixable ridge.

    ``wrap_x`` is False for a cropped whole-world source (its left/right edges are
    the antimeridian, not neighbours) and True for a synthetic source that tiles
    the globe. The despeckle filters honour it so a coastline on the seam is not
    tulipped by edge effects.
    """
    den = lut.denoise(rgb, denoise_size)
    elev, is_land, dist = lut.classify(den, elut)

    ink = lut.unexplained_ink(den, dist, dilate=ink_dilate)
    elev = lut.inpaint_nearest(elev, ink)
    is_land = lut.inpaint_nearest(is_land, ink)

    is_land = segment.majority_filter(is_land, majority, wrap_x=wrap_x)
    is_land = segment.drop_small_components(is_land, min_blob, wrap_x=wrap_x)
    is_land = ~segment.drop_small_components(~is_land, min_blob, wrap_x=wrap_x)

    elev = lut.smooth_elevation(elev, sigma=elev_sigma)
    land_f = lut.smooth_elevation(is_land.astype(np.float32), sigma=land_sigma)
    return SourceFields(elev=elev, land=land_f, dist=dist, ink=ink)


# ---------------------------------------------------------------------------
# Reprojection onto the canvas (blocked, crop-clamped)
# ---------------------------------------------------------------------------


def clamped_source_coords(reg: schema.SourceRegistration, fit, y_rows, width, height):
    """Source coordinates for canvas rows ``y_rows``, clamped into the crop.

    Clamping rather than masking is deliberate for a whole-world source: the
    canvas seam at lon +-180 projects exactly onto the oval's drawn boundary
    rule, and sampling that black line would classify as the darkest swatch — a
    thin strip of false >7000 m "land" down both edges of the world. Clamping
    reuses the ocean pixel just inside the rule instead.
    """
    sx, sy = reproject.source_coords_parametric(fit, y_rows, width, height)
    if reg.crop is not None:
        x0, y0, x1, y1 = reg.crop
        np.clip(sx, x0, x1, out=sx)
        np.clip(sy, y0, y1, out=sy)
    return sx, sy


def reproject_plane(reg, fit, plane, out_w, out_h, *, block_rows, order=1, dtype=np.float32):
    """Reproject one source plane onto an ``out_w`` x ``out_h`` grid, in row blocks.

    Blocking bounds peak memory: only ``block_rows`` of the target's float
    coordinate grids exist at once, so a 118-megapixel heightmap builds in a few
    hundred MB rather than gigabytes.
    """
    out = np.empty((out_h, out_w), dtype=dtype)
    for y0 in range(0, out_h, block_rows):
        y1 = min(out_h, y0 + block_rows)
        rows = np.arange(y0, y1)
        sx, sy = clamped_source_coords(reg, fit, rows, out_w, out_h)
        out[y0:y1] = reproject.resample(plane, sx, sy, order=order)
    return out


# ---------------------------------------------------------------------------
# Heightmap encoding (metres -> vanilla uint16, shoreline forced to the mask)
# ---------------------------------------------------------------------------


def encode_heightmap(elev_m, land, *, sea_level, units_per_metre, shore_margin) -> np.ndarray:
    """Metres -> the uint16 encoding vanilla uses, with the shoreline forced.

    Any land pixel is pushed at least ``shore_margin`` above sea level and any
    sea pixel at least that far below, so the heightmap's coastline can never
    contradict the committed land/sea mask that provinces.png is cut from — a
    disagreement there is a coastal province the engine would render underwater.
    """
    v = np.round(sea_level + units_per_metre * np.asarray(elev_m, dtype=np.float32))
    np.clip(v, 0, 65535, out=v)
    out = v.astype(np.uint16)
    lo = np.uint16(sea_level + shore_margin)
    hi = np.uint16(sea_level - shore_margin)
    np.maximum(out, lo, out=out, where=land)
    np.minimum(out, hi, out=out, where=~land)
    return out


def upscale2_rows(mask: np.ndarray, y0: int, y1: int) -> np.ndarray:
    """Rows ``[y0, y1)`` of ``mask`` upscaled 2x on both axes.

    Computed for the row slice only, so the full 2x array never has to exist. The
    heightmap is exactly twice the canvas, so nearest-neighbour 2x is exact —
    which is what makes "force the heightmap shoreline to the canvas mask" a
    lossless operation rather than an approximate one.
    """
    src = mask[y0 // 2:(y1 + 1) // 2]
    big = np.repeat(np.repeat(src, 2, axis=0), 2, axis=1)
    return big[(y0 % 2):(y0 % 2) + (y1 - y0)]
