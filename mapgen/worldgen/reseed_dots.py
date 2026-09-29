"""Fold newly hand-marked anchor dots into a ``landmarks`` registration seed.

The reusable, deterministic core of the paired-anchor-dot **reseed** step (see
``mapgen/reseed_registration_dots.py``, a thin CLI over this module). A pure
function of two dots sheets' pixels plus the seed's existing landmarks — zero
file I/O and no RNG, so a re-run reproduces the same landmarks.

Background. A ``landmarks``-objective seed (e.g.
``tww3_old_world_mod_parchment_full``) carries paired anchor dots: for each one,
``source`` is the dot's centroid in the master image's own frame and ``canvas``
is the SAME coloured dot's centroid read straight off
``terraqueous_globe_reprojected.png`` (canvas space). The user marks new matched
dot pairs on the two "dots" sheets over time; this module detects the dots that
are not yet represented by an existing landmark, colour-pairs the new master and
canvas dots, names them, and appends them. ``mapgen/fit_registration.py`` then
re-derives the committed registration record from the enlarged seed.

Detection reproduces the method documented in the seed's ``_comment``: a compact,
chromatic component present on a dots sheet but absent from the matching original,
undotted document. A component's colour is the rounded mean of its pixels; a name
is ``c_<rrggbb>`` of that colour, disambiguated with ``_N`` against the names
already in the seed (the same convention the earlier dots_7 additions used, which
is why the literal detected mean is kept rather than snapped to the draw
palette — cf. the existing ``c_7f06fe`` / ``c_ff64ff`` landmarks).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

#: A palette-coloured speck smaller than this is art/noise, not a marker dot
#: (the known dots are ~12 px). Matches ``derive_crop.MIN_MARKER_PX`` and drops
#: the single-pixel re-save specks the chroma floor would otherwise admit.
MIN_DOT_PX = 4
#: A component larger than this (px) or wider/taller than :data:`MAX_DOT_BOX`
#: is not a dot — a smear or a fill bleed; reported by the caller, never folded.
MAX_DOT_PX = 60
MAX_DOT_BOX = 20
#: Default chromaticity (max-min channel) floor for a kept component. A dot is
#: drawn in a saturated colour; parchment/relief ink is near-gray.
DEFAULT_CHROMA_FLOOR = 120
#: A detected centroid within this many px of an existing landmark's own centroid
#: (in the matching frame) IS that landmark — left untouched, never re-added.
DEFAULT_MATCH_TOL_PX = 3.0
#: Two paired dots' mean colours must agree within this Euclidean distance, or
#: the pair is rejected as a mis-pairing rather than folded blind.
DEFAULT_MAX_COLOUR_DIST = 40.0


@dataclass(frozen=True)
class Dot:
    """One detected marker component on a dots sheet."""

    cx: float
    cy: float
    color: tuple[int, int, int]
    size: int

    @property
    def xy(self) -> tuple[float, float]:
        return (self.cx, self.cy)


def _chroma(rgb: np.ndarray) -> np.ndarray:
    return rgb.max(axis=-1) - rgb.min(axis=-1)


def detect_dots(
    orig_rgb: np.ndarray,
    dots_rgb: np.ndarray,
    *,
    chroma_floor: int = DEFAULT_CHROMA_FLOOR,
    relaxed_chroma: int | None = None,
    noisy_rects: tuple = (),
    min_px: int = MIN_DOT_PX,
    max_px: int = MAX_DOT_PX,
    max_box: int = MAX_DOT_BOX,
) -> list[Dot]:
    """Marker dots present on ``dots_rgb`` but absent from ``orig_rgb``.

    A pixel is a candidate when it differs from the original AND is chromatic
    enough. ``relaxed_chroma`` (when given, with ``noisy_rects``) lets pale dots
    survive a lower floor *outside* the listed rectangles while a higher
    ``chroma_floor`` is demanded *inside* them — the rectangles being regions of
    the master where re-save/anti-alias noise concentrates (e.g. dense linework
    crossings). With no rectangles the floor is uniform. Both arrays are
    ``(H, W, 3)`` in the SAME frame; the returned centroids are pixel-centre
    (mean + 0.5) and the list is in ``ndimage.label`` order (deterministic).
    """
    if orig_rgb.shape != dots_rgb.shape:
        raise ValueError(
            f"orig {orig_rgb.shape} and dots {dots_rgb.shape} must share a frame")
    orig = orig_rgb.astype(np.int16)
    dots = dots_rgb.astype(np.int16)
    diff = np.any(orig != dots, axis=-1)
    ch = _chroma(dots)
    if noisy_rects and relaxed_chroma is not None:
        H, W = ch.shape
        inside = np.zeros((H, W), dtype=bool)
        for x0, y0, x1, y1 in (tuple(int(v) for v in r) for r in noisy_rects):
            inside[y0:y1, x0:x1] = True
        keep = diff & np.where(inside, ch >= chroma_floor, ch >= relaxed_chroma)
    else:
        keep = diff & (ch >= chroma_floor)

    labeled, n = ndimage.label(keep, structure=np.ones((3, 3)))
    out: list[Dot] = []
    for i in range(1, n + 1):
        ys, xs = np.where(labeled == i)
        size = len(xs)
        if size < min_px or size > max_px:
            continue
        h = int(ys.max() - ys.min() + 1)
        w = int(xs.max() - xs.min() + 1)
        if h > max_box or w > max_box:
            continue
        color = tuple(int(round(v)) for v in dots[ys, xs].mean(axis=0))
        out.append(Dot(cx=float(xs.mean() + 0.5), cy=float(ys.mean() + 0.5),
                       color=color, size=int(size)))
    return out


def select_new(
    dots: list[Dot],
    landmarks: list[dict],
    key: str,
    *,
    tol_px: float = DEFAULT_MATCH_TOL_PX,
) -> tuple[list[Dot], int]:
    """Split ``dots`` into (not-yet-a-landmark, count-matching-a-landmark).

    A dot matches when its centroid is within ``tol_px`` of some landmark's
    ``key`` (``"source"`` or ``"canvas"``) centroid; each landmark consumes at
    most one dot. Existing landmarks are never re-detected reliably on every
    re-export (a pale dot can fall under the chroma floor), so this only
    identifies the NEW dots — the committed landmarks are left untouched.
    """
    tol2 = tol_px * tol_px
    remaining = list(range(len(dots)))
    matched = 0
    for lm in landmarks:
        if key not in lm:
            continue
        px, py = lm[key]
        best_i, best_d = None, tol2 + 1e-9
        for i in remaining:
            d = (dots[i].cx - px) ** 2 + (dots[i].cy - py) ** 2
            if d < best_d:
                best_d, best_i = d, i
        if best_i is not None and best_d <= tol2:
            remaining.remove(best_i)
            matched += 1
    return [dots[i] for i in remaining], matched


def _colour_dist2(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return sum((int(x) - int(y)) ** 2 for x, y in zip(a, b))


@dataclass(frozen=True)
class Pair:
    master: Dot
    canvas: Dot
    colour_dist: float


def pair_by_colour(
    master_new: list[Dot],
    canvas_new: list[Dot],
    *,
    max_colour_dist: float = DEFAULT_MAX_COLOUR_DIST,
) -> tuple[list[Pair], list[Dot], list[Dot]]:
    """Greedily pair new master dots to new canvas dots by nearest mean colour.

    A user draws each new anchor as the SAME colour on both sheets, so colour is
    the pairing key. Processing master dots in a stable order (sorted by source
    ``(y, x)``), each takes its closest-colour unused canvas dot; a pair whose
    colours disagree by more than ``max_colour_dist`` is rejected (returned among
    the unpaired), never folded on a guess. Returns
    ``(pairs, unpaired_master, unpaired_canvas)``.
    """
    order = sorted(range(len(master_new)),
                   key=lambda i: (master_new[i].cy, master_new[i].cx))
    used: set[int] = set()
    pairs: list[Pair] = []
    unpaired_master: list[Dot] = []
    max_d2 = max_colour_dist * max_colour_dist
    for mi in order:
        m = master_new[mi]
        best_j, best_d2 = None, None
        for j, c in enumerate(canvas_new):
            if j in used:
                continue
            d2 = _colour_dist2(m.color, c.color)
            if best_d2 is None or d2 < best_d2:
                best_d2, best_j = d2, j
        if best_j is None or best_d2 > max_d2:
            unpaired_master.append(m)
            continue
        used.add(best_j)
        pairs.append(Pair(master=m, canvas=canvas_new[best_j],
                          colour_dist=float(best_d2 ** 0.5)))
    unpaired_canvas = [c for j, c in enumerate(canvas_new) if j not in used]
    return pairs, unpaired_master, unpaired_canvas


def _hexname(color: tuple[int, int, int]) -> str:
    return "c_%02x%02x%02x" % tuple(int(v) for v in color)


def name_pairs(pairs: list[Pair], existing_names) -> list[dict]:
    """Turn colour pairs into named landmark dicts, unique against ``existing_names``.

    Name is ``c_<rrggbb>`` of the master dot's mean colour, disambiguated with a
    ``_N`` suffix (N counting from 2) when the base — or a lower suffix — is
    already taken, both by the seed and by earlier pairs in this same batch.
    Centroids are rounded to 0.1 px, matching the committed seed's precision.
    """
    taken = set(existing_names)
    landmarks: list[dict] = []
    for p in pairs:
        base = _hexname(p.master.color)
        name = base
        k = 2
        while name in taken:
            name = f"{base}_{k}"
            k += 1
        taken.add(name)
        landmarks.append({
            "name": name,
            "source": [round(p.master.cx, 1), round(p.master.cy, 1)],
            "canvas": [round(p.canvas.cx, 1), round(p.canvas.cy, 1)],
        })
    return landmarks
