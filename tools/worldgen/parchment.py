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


#: Ink-threshold offset tuned for the IE parchment master
#: (``world-map-parchment-areas-onto-globe.md`` measurement 4): a sweep with
#: bridging active found usable cells rising from 885 (offset 12) to 915
#: (offset 9) to 920 (offset 7, but at 26.5% ink — the cost is starting to
#: outrun the recovery). 9 is the adopted value.
INK_OFFSET_MASTER = 9

#: Glyph-shaped ink component thresholds (measurement 2): letters on the master
#: separate cleanly from the boundary-line network by shape alone — 3,854
#: compact blobs holding 292k ink px at a 9-16 px glyph height, against 4 giant
#: connected components holding 1.19M of the 1.68M ink px (the line network
#: itself). These bounds sit generously around that measured range so a bold
#: numeral or a punctuation mark still qualifies, while the line network's
#: components — long, thin, and mostly-empty inside their own bounding box —
#: do not.
GLYPH_MIN_AREA = 20
GLYPH_MAX_SIDE = 60
GLYPH_MIN_HEIGHT = 6
GLYPH_MIN_FILL = 0.15

#: Anisotropic closing structure for bridging detected glyphs into a barrier
#: (measurement 3): wide on x because letter spacing within a printed word is
#: horizontal, short on y so the bridge does not reach into an unrelated ruled
#: line a few pixels above or below the label.
LABEL_CLOSE = (7, 21)


def glyph_mask(ink: np.ndarray) -> np.ndarray:
    """Ink pixels belonging to a small, compact (glyph-shaped) component.

    The parchment's ink separates cleanly into two populations by shape: the
    ruled boundary/river network is a handful of huge, thin, sparsely-filled
    connected components, while lettering is thousands of small, squarish,
    densely-filled ones (measurement 2). Filtering on area, bounding-box side
    length, minimum height and fill ratio keeps the second population and
    drops the first, with no OCR engine involved. 4-connectivity matches
    :func:`cells_from_ink`'s own test, so a glyph and the line network never
    disagree about where one component ends and the next begins.
    """
    lab, n = ndimage.label(ink)
    if n == 0:
        return np.zeros_like(ink)
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    keep = np.zeros(n + 1, dtype=bool)
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        area = int(sizes[i])
        if area < GLYPH_MIN_AREA:
            continue
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if h > GLYPH_MAX_SIDE or w > GLYPH_MAX_SIDE or h < GLYPH_MIN_HEIGHT:
            continue
        if area / (h * w) < GLYPH_MIN_FILL:
            continue
        keep[i] = True
    return keep[lab]


def label_blobs(glyphs: np.ndarray) -> np.ndarray:
    """Group glyph pixels into per-label regions, closing the letter spacing.

    A printed label is a run of separate glyph components with gaps between
    letters and words; closing with :data:`LABEL_CLOSE` bridges those gaps into
    one blob per label, and the trailing 3x3 dilation thickens the result just
    enough to fuse with the interrupted ruled line either side of it. Returns
    an ``int32`` label image (0 = not part of any blob) rather than a boolean
    mask, so a caller needing a specific label's bounding box, centroid or
    pixel footprint (Stage B's binding) gets it for free instead of re-deriving
    connected components later.

    Measured and rejected (measurement 5): closing the *whole ink barrier*
    rather than only the detected glyphs makes the largest traced cell worse
    (852k -> 2.19M px at a 3x3 close) — it bridges real gaps between unrelated
    cells, not just letter spacing. Do not retry that.
    """
    if not glyphs.any():
        return np.zeros(glyphs.shape, dtype=np.int32)
    ch, cw = LABEL_CLOSE
    closed = ndimage.binary_closing(glyphs, structure=np.ones((ch, cw), bool))
    dilated = ndimage.binary_dilation(closed, structure=np.ones((3, 3), bool))
    lab, _ = ndimage.label(dilated)
    return lab.astype(np.int32)


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


#: Flat ocean fill on the coloured Total War map, sampled from it directly.
FLAT_SEA_RGB = (16, 6, 175)
#: Off-map background / land base tone on the same map.
FLAT_PAPER_RGB = (211, 189, 140)


def flat_sea_mask(rgb: np.ndarray, tolerance: int = 60) -> np.ndarray:
    """Sea on a flat-filled map, by distance to the committed ocean colour.

    A map whose ocean is a single flat colour needs no threshold *fitting* at
    all: the answer is exact up to the anti-aliased pixel at each coastline. This
    is worth far more than it sounds. Every other source here forced a judgement
    call about where the water started — a chromaticity distance on the parchment
    family, a calibrated luminance cut on the Old World map that reached only 81%
    balanced accuracy — and a registration can be no better than the silhouette it
    is scored against.
    """
    d = np.abs(rgb.astype(np.int16) - np.array(FLAT_SEA_RGB, dtype=np.int16)).max(axis=2)
    return d <= int(tolerance)


def flat_map_cells(rgb: np.ndarray, min_area: int = 300,
                   max_area_fraction: float = 0.012,
                   line_luminance: int = 90,
                   exclude: list[tuple[int, int, int, int]] | None = None
                   ) -> tuple[np.ndarray, np.ndarray]:
    """``(cell_labels, land)`` for a flat-filled map with drawn region lines.

    The barrier is the union of the ocean and the drawn black lines, so labelling
    the complement yields the land regions directly — no local-contrast ink test,
    no text to inpaint, no coastal shadow band to mistake for a border.

    ``max_area_fraction`` drops the handful of enormous "cells" that are not
    regions at all: the off-map background outside the map's own frame, and the
    legend panel. They are separated from real regions by two orders of magnitude
    in area (the largest is 5.8% of the image against a 0.05% median), so the cut
    is not delicate. Land is then defined as the union of the surviving cells,
    which is a cleaner statement of "inside the map, and not sea" than any
    colour test could give.
    """
    dark = rgb.astype(np.int16).max(axis=2) < int(line_luminance)
    sea = flat_sea_mask(rgb)
    barrier = dark | sea
    for x0, y0, x1, y1 in (exclude or []):
        barrier[int(y0):int(y1), int(x0):int(x1)] = True
    lab, _ = cells_from_ink(barrier, min_area)
    sizes = np.bincount(lab.ravel())
    too_big = np.zeros(len(sizes), dtype=bool)
    too_big[1:] = sizes[1:] > max_area_fraction * rgb.shape[0] * rgb.shape[1]
    lab = np.where(too_big[lab], 0, lab)
    return renumber_cells(lab), lab > 0


def renumber_cells(labels: np.ndarray) -> np.ndarray:
    """Compact cell ids to ``1..k``, preserving 0."""
    uniq, inv = np.unique(labels, return_inverse=True)
    out = inv.reshape(labels.shape).astype(np.int32)
    return out if uniq[0] == 0 else out + 1


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
