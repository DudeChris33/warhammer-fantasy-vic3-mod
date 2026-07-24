"""Land/sea mask cleanup — turn a noisy classification into a usable coastline.

The raw per-pixel land flag out of ``lut.classify`` is speckled: legend swatches
overlap in RGB, the scan has grain, and lettering and graticule lines sit on top
of the terrain. Feeding that straight into the province generator would produce
thousands of one-pixel islands and lakes, each of which the engine would treat as
a real landmass or water body.

This module applies the morphological cleanup, in a fixed order so the result is
reproducible:

1. **Close** then **open** with a small disk — bridges hairline gaps the
   graticule cuts through a coast, then removes isolated speckle.
2. **Drop small water bodies** enclosed by land (map lettering over an ocean
   reads as a hole) and **small islands** below a minimum area.

Every operation is wrap-aware on the x axis: the canvas is periodic in longitude
(``map_config.WRAP_X``), so a coastline crossing the seam must be treated as
continuous. ``scipy.ndimage`` has no wrap mode that also clamps y, so the array
is padded by hand on x, processed, and the pad trimmed off.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def _disk(radius: int) -> np.ndarray:
    r = int(radius)
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def _wrap_pad(mask: np.ndarray, pad: int) -> np.ndarray:
    """Pad on x by wrapping, on y by edge replication."""
    if pad <= 0:
        return mask
    wide = np.concatenate([mask[:, -pad:], mask, mask[:, :pad]], axis=1)
    top = np.repeat(wide[:1], pad, axis=0)
    bot = np.repeat(wide[-1:], pad, axis=0)
    return np.concatenate([top, wide, bot], axis=0)


def _wrap_unpad(mask: np.ndarray, pad: int) -> np.ndarray:
    return mask if pad <= 0 else mask[pad:-pad, pad:-pad]


def morphology(mask: np.ndarray, close_radius: int = 2, open_radius: int = 2,
               wrap_x: bool = True) -> np.ndarray:
    """Close-then-open the land mask with disk structuring elements."""
    pad = max(close_radius, open_radius) * 2 + 2 if wrap_x else 0
    m = _wrap_pad(mask, pad) if wrap_x else mask
    if close_radius > 0:
        m = ndimage.binary_closing(m, structure=_disk(close_radius))
    if open_radius > 0:
        m = ndimage.binary_opening(m, structure=_disk(open_radius))
    return _wrap_unpad(m, pad) if wrap_x else m


def majority_filter(mask: np.ndarray, size: int, wrap_x: bool = True) -> np.ndarray:
    """Replace each pixel by the majority of its ``size`` x ``size`` neighbourhood.

    For a binary image this *is* the median filter, but computed as a box mean
    thresholded at half — which is separable and therefore O(N) instead of
    ``ndimage.median_filter``'s O(N x size^2). On a 13-megapixel source with
    size 7 that is the difference between under a second and the better part of a
    minute.

    Its job is to erase strokes: the reference maps draw graticule lines, river
    courses and place-name lettering straight over the terrain, all of which the
    colour LUT dutifully classifies as whatever they most resemble. A stroke
    narrower than about half the window loses the vote and disappears, while
    coastlines — which have land on one whole side — do not move.
    """
    if size <= 1:
        return mask
    pad = size if wrap_x else 0
    m = _wrap_pad(mask, pad) if wrap_x else mask
    frac = ndimage.uniform_filter(m.astype(np.float32), size=size, mode="nearest")
    out = frac > 0.5
    return _wrap_unpad(out, pad) if wrap_x else out


def drop_small_components(mask: np.ndarray, min_area: int, wrap_x: bool = True) -> np.ndarray:
    """Clear connected True components smaller than ``min_area``."""
    return _drop_small(mask, min_area, wrap_x)


def _drop_small(mask: np.ndarray, min_area: int, wrap_x: bool) -> np.ndarray:
    """Clear connected True components smaller than ``min_area`` (4-connected)."""
    if min_area <= 1:
        return mask
    pad = 1 if wrap_x else 0
    m = _wrap_pad(mask, pad) if wrap_x else mask
    lab, n = ndimage.label(m)          # default structure is 4-connectivity
    if n == 0:
        return mask
    sizes = np.bincount(lab.ravel())
    # A component touching both pads is one wrapped body; counting it in the
    # padded array over-counts its area, which can only ever keep it. Safe.
    small = np.zeros(sizes.shape, dtype=bool)
    small[1:] = sizes[1:] < min_area
    m = m & ~small[lab]
    return _wrap_unpad(m, pad) if wrap_x else m


def clean_land_mask(land: np.ndarray, min_island_area: int = 24,
                    min_lake_area: int = 24, close_radius: int = 2,
                    open_radius: int = 2, wrap_x: bool = True) -> np.ndarray:
    """Full cleanup: morphology, then remove tiny islands and tiny inland seas.

    Lakes are removed by running the island filter on the *inverted* mask, which
    fills any enclosed water body under ``min_lake_area``. Open ocean is far
    larger than the threshold, so it is never touched.
    """
    m = morphology(land, close_radius, open_radius, wrap_x)
    m = _drop_small(m, min_island_area, wrap_x)
    m = ~_drop_small(~m, min_lake_area, wrap_x)
    return m


def mask_stats(land: np.ndarray, wrap_x: bool = True) -> dict:
    """Descriptive counts for the build log / validator."""
    pad = 1 if wrap_x else 0
    lm = _wrap_pad(land, pad) if wrap_x else land
    wm = _wrap_pad(~land, pad) if wrap_x else ~land
    _, n_land = ndimage.label(lm)
    _, n_water = ndimage.label(wm)
    return {
        "land_fraction": float(land.mean()),
        "land_bodies": int(n_land),
        "water_bodies": int(n_water),
    }
