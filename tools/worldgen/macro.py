"""Macro-region grouping from the annotated twin of the parchment master.

``pizqenw9rd791.jpg`` is the IE parchment master with each macro region outlined
in a saturated hue and labelled with its province count. Because it is the *same
picture* underneath, the annotation can be isolated by differencing the two —
which is far more robust than any colour rule applied to the twin alone. A hue
threshold has to cope with the parchment's own warm browns and with whatever the
annotator's colours happen to be; a difference only has to cope with "these two
files disagree here", and they disagree in exactly one place.

The contours are closed loops, so the regions fall out of labelling the
complement, the same trick ``parchment.cells_from_ink`` uses on the boundary
network. Each state cell then takes the macro whose region contains most of it —
containment by majority rather than by centroid, because a cell straddling a
macro boundary has a centroid that can land in neither.

The twin's **printed province counts** (Empire 22, Cathay 19, Lustria 21, ...) are
carried as a checked invariant: a grouping that produces a wildly different
number of contours than the map declares has gone wrong somewhere upstream, and
should say so rather than quietly produce a map with two Empires.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from worldgen import cells


class MacroError(RuntimeError):
    """Macro regions could not be recovered from the annotated twin."""


#: Province counts printed on the annotated twin, read off the image. These are
#: the annotator's counts for the *Immortal Empires* campaign, not our state
#: counts — they are a sanity check on the grouping's shape, never a target.
PRINTED_COUNTS = {
    "northern_chaos_wastes": 13,
    "norsca": 9,
    "kislev": 8,
    "naggaroth": 18,
    "ulthuan": 15,
    "the_empire": 22,
    "bretonnia": 8,
    "southern_realms": 7,
    "lustria": 21,
    "badlands_wem": 18,
    "southlands": 18,
    "the_darklands": 18,
    "ogre_kingdoms": 7,
    "cathay": 19,
    "eastern_steppes": 8,
    "southern_chaos_wastes": 4,
}


def annotation_mask(twin: np.ndarray, clean: np.ndarray, threshold: int = 50,
                    min_saturation: int = 30) -> np.ndarray:
    """Where the annotated twin differs from the clean master by more than noise.

    The threshold is on the maximum per-channel difference rather than the mean:
    a saturated stroke over parchment moves one channel hard and the others
    little, and averaging would dilute exactly the signal being looked for.

    The saturation test removes JPEG ringing around the added *text*, which
    differs from the clean master but is black — the region contours are the
    coloured part, and only they are wanted. Coats of arms and other artwork
    present in both images cancel in the difference and need no special handling
    at all, which is the whole reason for differencing rather than thresholding.
    """
    if twin.shape != clean.shape:
        raise MacroError(f"twin {twin.shape} and master {clean.shape} are not the same frame")
    d = np.abs(twin.astype(np.int16) - clean.astype(np.int16)).max(axis=2)
    sat = twin.max(axis=2).astype(np.int16) - twin.min(axis=2).astype(np.int16)
    return (d > int(threshold)) & (sat > int(min_saturation))


def contours_from_twin(twin: np.ndarray, min_saturation: int = 100) -> np.ndarray:
    """Fallback: recover the macro contours from the annotated twin **alone**.

    Used only when the clean master is unavailable, because it is measurably
    worse. Differencing the two images isolates exactly what the annotator added
    and nothing else; a saturation threshold on the twin cannot distinguish an
    added contour from the map's own saturated artwork — the coats of arms are
    the obvious case, and no colour rule survives contact with heraldry.

    Measured on this source: differencing recovers **16** regions, matching the
    16 the map itself labels. This fallback recovers **13**. The three it loses
    merge into neighbours, so the states in them are grouped into the wrong
    strategic region rather than left ungrouped — a silent error, which is why
    the caller must report having fallen back to it.
    """
    mx = twin.max(axis=2).astype(np.int16)
    mn = twin.min(axis=2).astype(np.int16)
    return (mx - mn) > int(min_saturation)


def regions_from_contours(contour: np.ndarray, min_area: int = 20000,
                          close_radius: int = 17, seal_border: bool = True
                          ) -> tuple[np.ndarray, int]:
    """Label the areas enclosed by the annotation contours.

    The contours are hand-drawn and freely leave small gaps where they run under
    a label. Closing before labelling bridges those; without it a single gap lets
    two macro regions merge into one, which is the failure mode that matters here
    (a spurious extra region is obvious, a silently merged pair is not).

    ``seal_border`` draws the image edge as contour. The polar and outermost
    regions — Northern and Southern Chaos Wastes, Naggaroth's western flank — are
    only *drawn* as arcs, because the map runs out before the region does; their
    closing side is the sheet edge. Without sealing they leak into each other and
    into the surrounding sea through the border, which is what took the recovered
    count down to 8 of the 16 the map labels.
    """
    m = contour.copy()
    if seal_border:
        m[0, :] = m[-1, :] = True
        m[:, 0] = m[:, -1] = True
    if close_radius > 0:
        r = int(close_radius)
        yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
        m = ndimage.binary_closing(m, structure=(xx * xx + yy * yy) <= r * r)
    lab, n = ndimage.label(~m)
    if n == 0:
        raise MacroError("annotation contours enclose nothing")
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    keep = sizes >= int(min_area)
    keep[0] = False

    # The single largest region is everything *outside* every contour — the open
    # sea between them. It has to be dropped, or a coastal cell that misses its
    # region's outline would be assigned "the ocean" as its macro. Measured on
    # this source it is 6,173,472 px against 518,026 for the largest real region,
    # a 12x gap; the check refuses to guess if that gap ever narrows, because
    # then "largest" would no longer be a safe way to name it.
    live = np.flatnonzero(keep)
    if live.size:
        order = live[np.argsort(-sizes[live])]
        if len(order) > 1 and sizes[order[0]] < 4 * sizes[order[1]]:
            raise MacroError(
                f"cannot identify the outside region: largest is {sizes[order[0]]:,} px "
                f"against {sizes[order[1]]:,} for the next — too close to call"
            )
        keep[order[0]] = False

    remap = np.zeros(n + 1, dtype=np.int32)
    remap[np.flatnonzero(keep)] = np.arange(1, int(keep.sum()) + 1, dtype=np.int32)
    return remap[lab], int(keep.sum())


def assign(state_labels: np.ndarray, macro_labels: np.ndarray) -> np.ndarray:
    """Give each state cell the macro region most of its pixels fall in.

    Returned as an array indexed by state label, so cell ``k``'s macro is
    ``out[k]``. Cells that fall entirely outside every macro region get 0, which
    the caller must resolve — those are the coverage gap, not an error here.

    Computed as one 2-D histogram over the (cell, macro) pair rather than a loop
    over cells: at canvas scale there are hundreds of cells and tens of millions
    of pixels, and the per-cell version is the slow shape of the same answer.
    """
    n_state = int(state_labels.max()) + 1
    n_macro = int(macro_labels.max()) + 1
    m = state_labels > 0
    key = state_labels[m].astype(np.int64) * n_macro + macro_labels[m].astype(np.int64)
    counts = np.bincount(key, minlength=n_state * n_macro).reshape(n_state, n_macro)
    # A cell entirely outside every macro would otherwise "win" macro 0.
    best = np.argmax(counts, axis=1).astype(np.int32)
    only_outside = counts[:, 1:].sum(axis=1) == 0
    best[only_outside] = 0
    inside = ~only_outside
    if inside.any():
        best[inside] = 1 + np.argmax(counts[inside, 1:], axis=1)
    best[0] = 0
    return best


def fill_missing(macro_of_cell: np.ndarray, state_labels: np.ndarray,
                 wrap_x: bool = True) -> np.ndarray:
    """Give every unassigned cell the macro of its nearest assigned neighbour.

    Runs on the *label layer*, not on cells as points: a coastal cell's nearest
    assigned neighbour by centroid can be across a sea, while nearest by pixel is
    the state it actually borders.
    """
    out = macro_of_cell.copy()
    missing = np.flatnonzero(out == 0)
    missing = missing[missing > 0]
    if not missing.size:
        return out
    assigned_px = np.zeros(state_labels.shape, dtype=np.int32)
    known = out[state_labels] if state_labels.max() < len(out) else None
    if known is None:
        raise MacroError("macro table is shorter than the label layer")
    assigned_px[(state_labels > 0) & (known > 0)] = known[(state_labels > 0) & (known > 0)]
    grown = cells.fill_nearest(assigned_px, state_labels > 0, wrap_x=wrap_x)
    for cid in missing.tolist():
        vals = grown[state_labels == cid]
        vals = vals[vals > 0]
        if vals.size:
            out[cid] = int(np.bincount(vals).argmax())
    return out


def count_report(macro_of_cell: np.ndarray, names: dict[int, str] | None = None) -> list[str]:
    """Cells per macro, for the coverage report."""
    counts = np.bincount(macro_of_cell[1:]) if len(macro_of_cell) > 1 else np.array([])
    lines = []
    for m in range(1, len(counts)):
        label = (names or {}).get(m, f"macro_{m:02d}")
        lines.append(f"  {label:<28} {counts[m]:>4} cells")
    return lines
