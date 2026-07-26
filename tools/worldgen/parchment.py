"""Primitives shared by the Immortal Empires parchment sources.

Four of the S3a references are the same parchment picture at different crops and
scales (see ``tools/SOURCES.md``), and the Old World mod map is drawn in the same
idiom: a warm paper wash, region boundaries as thin dark ruled lines, place names
lettered directly over the terrain. Three operations recur across all of them, so
they live here rather than being re-derived per source.

**Silhouette.** Painted regions vs bare parchment separate on *chromaticity*, not
on brightness. The parchment is a single hue at wildly varying luminance — it is
a paper texture with drop shadows, stains and vignetting — so any brightness
threshold cuts through the middle of the paper. Normalising each pixel by its own
total intensity throws the luminance away and keeps only the hue, and against
that the painted climate fills sit far from the paper's point.

**Ink.** The boundary lines are darker than their surroundings but not dark in
absolute terms: a line drawn over a bright highlight is brighter than open
parchment in a shadowed corner. So ink is found by *local* contrast — darker than
the neighbourhood mean by a margin — which is invariant to the vignetting that
defeats a global threshold.

**Erasure.** Lettering is ink by the same test and would otherwise chop cells in
half. Where a source must be de-lettered rather than have its lines traced, the
strokes are filled from their nearest non-ink neighbours, the technique
``worldgen/lut.py`` already uses on the Terraqueous globe's own lettering.

Everything here is a pure function of the pixels plus committed constants — no
RNG, no wall-clock, no adaptive thresholds fitted at run time to a percentile of
the data (which would make a crop change the answer for the pixels it kept).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

#: Chromaticity of the bare IE parchment, measured as the median of a known
#: open-sea block on ``3274025515_preview_WH3 climate map 6.0.3.jpg``.
PARCHMENT_RG = (0.4436, 0.3344)

#: Chromaticity distance beyond which a pixel is "painted" rather than paper.
PAINT_DISTANCE = 0.04

#: Window (px) for the local mean the ink test is measured against, and how far
#: below that mean a pixel must sit (0-255) to count as ink.
INK_WINDOW = 41
INK_OFFSET = 14


def chromaticity(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(r, g)`` normalised chromaticity — each channel over the pixel's total.

    Pure black would divide by zero; it is clamped to a total of 1 instead, which
    puts it at (1/3, 1/3) — the neutral point, far from any saturated fill and
    close enough to the paper's own hue to be treated as unpainted. That is the
    right answer for the black legend border and drop shadows.
    """
    f = rgb.astype(np.float32)
    total = f.sum(axis=2)
    np.maximum(total, 1.0, out=total)
    return f[..., 0] / total, f[..., 1] / total


def painted_mask(rgb: np.ndarray,
                 reference: tuple[float, float] = PARCHMENT_RG,
                 threshold: float = PAINT_DISTANCE,
                 open_size: int = 3, close_size: int = 5,
                 exclude: list[tuple[int, int, int, int]] | None = None) -> np.ndarray:
    """Pixels whose hue is far enough from bare parchment to be a painted fill.

    ``exclude`` is a list of ``(x0, y0, x1, y1)`` source-pixel boxes cleared after
    thresholding — the legend panel, a title cartouche, a compass rose. They are
    excluded rather than thresholded around because they are *correctly* detected
    as painted; they simply are not terrain.
    """
    r, g = chromaticity(rgb)
    d = np.hypot(r - reference[0], g - reference[1])
    m = d > threshold
    if open_size > 1:
        m = ndimage.binary_opening(m, structure=np.ones((open_size, open_size), bool))
    if close_size > 1:
        m = ndimage.binary_closing(m, structure=np.ones((close_size, close_size), bool))
    for x0, y0, x1, y1 in (exclude or []):
        m[int(y0):int(y1), int(x0):int(x1)] = False
    return m


def ink_mask(rgb: np.ndarray, window: int = INK_WINDOW, offset: float = INK_OFFSET,
             exclude: list[tuple[int, int, int, int]] | None = None) -> np.ndarray:
    """Ruled/lettered ink: darker than its local neighbourhood by ``offset``.

    ``uniform_filter`` gives the local mean in O(N) regardless of window size,
    which matters at 3703x2880. ``mode="nearest"`` keeps the window from pulling
    the border towards zero and inventing a frame of ink around the image.
    """
    v = rgb.astype(np.float32).max(axis=2)
    local = ndimage.uniform_filter(v, size=int(window), mode="nearest")
    m = v < (local - float(offset))
    for x0, y0, x1, y1 in (exclude or []):
        m[int(y0):int(y1), int(x0):int(x1)] = False
    return m


def erase_ink(rgb: np.ndarray, ink: np.ndarray) -> np.ndarray:
    """Fill ink pixels from the nearest non-ink pixel, per channel.

    One distance transform serves all three channels — the nearest valid
    neighbour is a property of the mask, not of the colour — so this costs one
    EDT rather than three.
    """
    if not ink.any():
        return rgb
    idx = ndimage.distance_transform_edt(ink, return_distances=False, return_indices=True)
    out = np.empty_like(rgb)
    for c in range(rgb.shape[2]):
        out[..., c] = rgb[..., c][tuple(idx)]
    return out


def cells_from_ink(ink: np.ndarray, min_area: int = 150) -> tuple[np.ndarray, int]:
    """Label the *complement* of the ink network — every enclosed cell falls out.

    Labelling the gaps rather than following the lines is what makes a hand-drawn
    network usable. A break in a boundary merges two cells, which is a recoverable
    error (the merged cell is still a closed region of the right shape, just too
    big); following the strokes instead would turn the same break into an open
    polyline with no interior at all, which is not recoverable. 4-connectivity is
    deliberate: an 8-connected fill leaks diagonally through a 1 px line.

    Returns ``(labels, count)`` with 0 = ink/too-small and labels renumbered
    ``1..count`` in raster order of first appearance, so the numbering is a pure
    function of the image.
    """
    lab, n = ndimage.label(~ink)  # default structure is 4-connectivity
    if n == 0:
        return np.zeros_like(lab), 0
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    keep = sizes >= int(min_area)
    keep[0] = False
    # Renumber in order of first raster appearance so the ids do not depend on
    # ndimage's internal ordering.
    remap = np.zeros(n + 1, dtype=np.int32)
    flat = lab.ravel()
    seen: list[int] = []
    _, first_idx = np.unique(flat, return_index=True)
    for old in flat[np.sort(first_idx)]:
        if old != 0 and keep[old] and remap[old] == 0:
            seen.append(int(old))
            remap[old] = len(seen)
    return remap[lab], len(seen)
