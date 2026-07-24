"""Apply the committed colour -> elevation LUT to a source image.

The Terraqueous globe paints elevation as a stepped ramp with a printed legend
(14 swatches, -7000 m to +7000 m, plus open-ended ends). ``schema.ElevationLUT``
holds our sampled swatch colours; this module turns an RGB image into an
elevation field and a land mask by nearest-swatch classification.

Two things stop that from being naive nearest-neighbour:

* **Paper.** The oval leaves the polar Chaos Wastes un-inked, and blank page is
  closer in RGB to the deepest-ocean swatch than to any land swatch. The LUT
  carries an explicit paper entry classified as land, so the poles come out as
  waste rather than as the world's deepest trench.
* **Texture.** The scan carries a paper grain and JPEG ringing, both of which
  push individual pixels across swatch boundaries. Classification runs on a
  lightly median-filtered copy, which removes the speckle without moving edges
  the way a blur would.

Classification is a pure function of the pixels and the committed LUT, so the
derived elevation is reproducible for a fixed source (whose bytes ``sources.py``
has already checked against the manifest).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from worldgen import schema


def denoise(rgb: np.ndarray, size: int = 3) -> np.ndarray:
    """Median-filter each channel — kills scan speckle, keeps swatch edges."""
    if size <= 1:
        return rgb
    out = np.empty_like(rgb)
    for c in range(rgb.shape[2]):
        out[..., c] = ndimage.median_filter(rgb[..., c], size=size, mode="nearest")
    return out


def _palette(lut: schema.ElevationLUT):
    """Swatch colours + their elevations + land flags, paper appended last."""
    colors = [b.rgb for b in lut.bands] + [lut.paper_rgb]
    elevs = [b.mid_m for b in lut.bands] + [lut.paper_elevation_m]
    is_land = [i >= lut.sea_band_count for i in range(len(lut.bands))] + [True]
    return (np.array(colors, dtype=np.float32),
            np.array(elevs, dtype=np.float32),
            np.array(is_land, dtype=bool))


def classify(rgb: np.ndarray, lut: schema.ElevationLUT, block_rows: int = 512):
    """``(elevation_m, is_land, distance)`` for an ``(H, W, 3)`` uint8 image.

    ``distance`` is the RGB distance to the winning swatch — a per-pixel measure
    of how well the LUT actually explains the image. The generators report its
    distribution so a source that does not match the committed ramp (a different
    edition of the map, say) is visible rather than silently averaged in.
    """
    colors, elevs, land = _palette(lut)
    h, w, _ = rgb.shape
    elevation = np.empty((h, w), dtype=np.float32)
    is_land = np.empty((h, w), dtype=bool)
    dist = np.empty((h, w), dtype=np.float32)

    # Blocked so the (rows x W x swatches) distance stack stays bounded.
    for y0 in range(0, h, block_rows):
        y1 = min(h, y0 + block_rows)
        blk = rgb[y0:y1].astype(np.float32)
        d2 = ((blk[:, :, None, :] - colors[None, None, :, :]) ** 2).sum(axis=3)
        idx = np.argmin(d2, axis=2)
        elevation[y0:y1] = elevs[idx]
        is_land[y0:y1] = land[idx]
        dist[y0:y1] = np.sqrt(np.take_along_axis(d2, idx[:, :, None], axis=2)[:, :, 0])
    return elevation, is_land, dist


#: A pixel further than this from every swatch is not terrain colour at all.
INK_MAX_DISTANCE = 45.0
#: ...and neither is one darker than the darkest swatch (>7000 m is luminance 88).
INK_MIN_LUMINANCE = 75.0
#: Pixels to grow the ink mask by, to swallow each glyph's anti-aliased halo.
INK_DILATE = 3


def unexplained_ink(rgb: np.ndarray, dist: np.ndarray,
                    max_distance: float = INK_MAX_DISTANCE,
                    min_luminance: float = INK_MIN_LUMINANCE,
                    dilate: int = INK_DILATE) -> np.ndarray:
    """Pixels the elevation ramp cannot explain — i.e. drawn ink, not terrain.

    The reference map letters its regions ("GRAND CATHAY", "LUSTRIA", ...) and
    rules its graticule directly over the terrain wash. Nearest-swatch
    classification has to return *something* for those pixels, and because the
    ink is dark, what it returns is the darkest swatch — the >7000 m band. Left
    alone, every place name on the map is embossed into the heightmap as a
    mountain range: measured on this source, ink pixels classify to a mean of
    6003 m against 822 m for land overall.

    Two independent tests catch it. Ink is far from every swatch in RGB, and ink
    is darker than the darkest swatch (the >7000 m colour has luminance 88).
    The map's region labels are a dark red — measured at roughly (96, 8, 5), so
    luminance 36 against the >7000 swatch's 88 — which both tests catch easily.

    The mask is then **dilated**, because the tests catch glyph cores but not
    their anti-aliased edges, and those edges are the worst case: a half-and-half
    blend of label red with the terrain wash lands at about (148, 99, 78), which
    is 41 units from the >7000 m swatch and luminance 108 — inside every
    threshold, and therefore classified as the highest mountains on the map. Ink
    always has such a halo, so growing the mask by a few pixels is the fix rather
    than loosening the thresholds until they start eating real terrain.
    """
    lum = rgb.astype(np.float32).mean(axis=2)
    ink = (dist > max_distance) | (lum < min_luminance)
    if dilate > 0:
        r = int(dilate)
        yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
        ink = ndimage.binary_dilation(ink, structure=(xx * xx + yy * yy) <= r * r)
    return ink


def inpaint_nearest(field: np.ndarray, invalid: np.ndarray) -> np.ndarray:
    """Replace ``invalid`` pixels with the value of the nearest valid pixel.

    A Euclidean distance transform run with ``return_indices`` gives, for every
    pixel, the coordinates of the closest valid one — so the whole fill is a
    single vectorized gather rather than a flood or an iterative diffusion. For
    strokes a few pixels wide this reads as "close the hole with whatever the
    terrain was doing on either side", which is exactly right for text sitting on
    top of a continuous field.
    """
    if not invalid.any():
        return field
    idx = ndimage.distance_transform_edt(invalid, return_distances=False, return_indices=True)
    return field[tuple(idx)]


def smooth_elevation(elevation: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    """Soften the ramp's hard band steps into a continuous surface.

    The LUT only resolves elevation to a handful of broad bands, so classified
    output is terraced. A Gaussian at source resolution turns those terraces into
    slopes before the field is resampled up to heightmap resolution — without it
    the relief reads as a contour staircase in game.
    """
    return ndimage.gaussian_filter(elevation.astype(np.float32), sigma=sigma, mode="nearest")
