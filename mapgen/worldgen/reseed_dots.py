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

import itertools
import math
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
#: Upper bound on the assignments :func:`resolve_repeated_colours` will try (the
#: product of the factorials of the repeated-colour group sizes). Past it the
#: sheet needs more distinct colours, not a longer search.
MAX_REPEAT_COMBOS = 2_000_000


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
    ignore_colours: tuple = (),
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
    crossings). With no rectangles the floor is uniform. ``ignore_colours``
    lists exact RGB triples that are markup but never a dot (a coastline trace
    drawn on the same sheet): they are dropped before labelling, so a dot that
    touches the trace stays its own component. Both arrays are
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
    for colour in ignore_colours:
        keep &= ~np.all(dots == np.array(colour, dtype=np.int16), axis=-1)

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


def _affine_residual_projector(src: np.ndarray) -> np.ndarray:
    """``M`` with ``y' M y`` = the squared residual of the least-squares affine
    fit of ``y`` on the points ``src`` (``(n, 2)``)."""
    X = np.column_stack([src, np.ones(len(src))])
    return np.eye(len(src)) - X @ np.linalg.pinv(X)


def resolve_repeated_colours(
    pairs: list[Pair],
    anchors: tuple = (),
    *,
    max_colour_dist: float = DEFAULT_MAX_COLOUR_DIST,
    max_combos: int = MAX_REPEAT_COMBOS,
) -> tuple[list[Pair], dict]:
    """Re-pair dots that share a colour, by position.

    :func:`pair_by_colour` cannot tell two dots of one colour apart, so where a
    sheet reuses a colour its pairing inside that colour is arbitrary. Here the
    pairs are grouped by master colour (within ``max_colour_dist`` of the
    group's first member, in the given order) and, for every group of two or
    more, each assignment of the group's canvas dots to its master dots is
    tried. The assignment kept is the one whose points, together with
    ``anchors`` (``(source_xy, canvas_xy)`` of the landmarks already in the
    seed), lie closest to a single affine map: lowest RMS residual, first in
    enumeration order on a tie. That is a ranking only; the warp is never
    affine.

    Returns ``(pairs, info)``; ``info`` has ``combos``, ``rms_px`` and
    ``runner_up_rms_px`` (``None`` when nothing repeated). Raises ``ValueError``
    when there are fewer than four points to rank on or more than
    ``max_combos`` assignments.
    """
    max_d2 = max_colour_dist * max_colour_dist
    groups: list[list[int]] = []
    for i, p in enumerate(pairs):
        for g in groups:
            if _colour_dist2(pairs[g[0]].master.color, p.master.color) <= max_d2:
                g.append(i)
                break
        else:
            groups.append([i])
    repeated = [g for g in groups if len(g) > 1]
    info = {"combos": 1, "rms_px": None, "runner_up_rms_px": None}
    if not repeated:
        return list(pairs), info

    combos = math.prod(math.factorial(len(g)) for g in repeated)
    n = len(pairs) + len(anchors)
    if n < 4:
        raise ValueError(
            f"{len(pairs)} dot pair(s) share colours and only {n} point(s) exist "
            "to tell them apart by position (need 4) — use distinct colours")
    if combos > max_combos:
        raise ValueError(
            f"{combos} ways to pair the repeated colours (limit {max_combos}) — "
            "use more distinct colours")

    src = np.array([p.master.xy for p in pairs] + [a[0] for a in anchors], dtype=np.float64)
    dst = np.array([p.canvas.xy for p in pairs] + [a[1] for a in anchors], dtype=np.float64)
    M = _affine_residual_projector(src)

    best_ss, runner_ss, best_order = None, None, None
    order = np.arange(len(pairs))
    for perms in itertools.product(*(itertools.permutations(g) for g in repeated)):
        for g, perm in zip(repeated, perms):
            order[g] = perm
        y = dst.copy()
        y[:len(pairs)] = dst[order]
        ss = float(np.einsum("ik,ij,jk->", y, M, y))
        if best_ss is None or ss < best_ss:
            best_ss, runner_ss, best_order = ss, best_ss, order.copy()
        elif runner_ss is None or ss < runner_ss:
            runner_ss = ss

    out = [
        Pair(master=p.master, canvas=pairs[j].canvas,
             colour_dist=float(_colour_dist2(p.master.color, pairs[j].canvas.color) ** 0.5))
        for p, j in zip(pairs, best_order)
    ]
    info.update(combos=combos, rms_px=float((best_ss / n) ** 0.5),
                runner_up_rms_px=float((runner_ss / n) ** 0.5))
    return out, info


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
