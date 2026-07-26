"""Fit a source's control points by scoring its silhouette against our own mask.

Registration is the step S3a most depends on and the step two earlier sessions
dead-ended on, so it is done by measurement rather than by eye. The committed
``tools/derived/land_sea_mask.png`` is the geometric authority (user decision #1);
a candidate placement is scored by how well the source's own land silhouette,
warped onto the canvas, agrees with it.

Two documented dead ends are deliberately not repeated (investigation §5 of the
plan of record):

* **A one-sided objective is degenerate.** "Fraction of the source's land that
  lands on our land" is maximised by squashing the whole map onto the largest
  continent; the previous attempt peaked flat at 0.674 against a 0.278 chance
  level with the vertical scale running off the bottom of its grid. Every score
  here is a **two-sided IoU** over a fixed canvas domain, where shrinking loses
  intersection while the union term stays put.
* **A brute-force 4-parameter grid over full-resolution masks does not finish.**
  The coarse stage here runs on masks reduced by a large integer factor, where a
  hundred thousand candidates is seconds rather than hours, and the fine stage is
  a *local* coordinate descent per control point rather than a global search.

The output is a set of canvas<->source pairs written into a registration record.
Because the search is a fixed grid followed by a fixed number of descent passes
over deterministic inputs, re-running reproduces the same record — the committed
JSON is machine-derived, not hand-tuned, and can be re-derived from the local
source at any time.

Immortal Empires is a *playable* map, not a globe (Ulthuan is drawn roughly twice
as large relative to the world as it is on the Terraqueous globe), so no affine
can fit it. The affine stage only places the frame; the thin-plate lattice is
what actually registers it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.interpolate import RBFInterpolator


def two_sided_iou(a: np.ndarray, b: np.ndarray) -> float:
    """Intersection over union of two boolean masks (0.0 when both are empty)."""
    inter = int(np.count_nonzero(a & b))
    union = int(np.count_nonzero(a | b))
    return (inter / union) if union else 0.0


# ---------------------------------------------------------------------------
# Stage 1 — coarse affine placement
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AffinePlacement:
    """``canvas = source * scale + offset``, axis-aligned."""

    scale: tuple[float, float]
    offset: tuple[float, float]
    iou: float

    def to_canvas(self, sx, sy):
        return sx * self.scale[0] + self.offset[0], sy * self.scale[1] + self.offset[1]

    def to_source(self, cx, cy):
        return (cx - self.offset[0]) / self.scale[0], (cy - self.offset[1]) / self.scale[1]


def _render_affine(src_mask: np.ndarray, scale, offset, shape) -> np.ndarray:
    """Paint ``src_mask`` onto a ``shape`` canvas under an axis-aligned affine.

    Sampled canvas-side (for each canvas pixel, which source pixel is it?) rather
    than painted source-side, so a magnifying placement leaves no gaps.
    """
    h, w = shape
    ys = (np.arange(h, dtype=np.float32) - offset[1]) / scale[1]
    xs = (np.arange(w, dtype=np.float32) - offset[0]) / scale[0]
    sy = np.rint(ys).astype(np.int64)
    sx = np.rint(xs).astype(np.int64)
    oky = (sy >= 0) & (sy < src_mask.shape[0])
    okx = (sx >= 0) & (sx < src_mask.shape[1])
    out = np.zeros(shape, dtype=bool)
    out[np.ix_(oky, okx)] = src_mask[np.ix_(sy[oky], sx[okx])]
    return out


def coarse_affine(src_mask: np.ndarray, canvas_mask: np.ndarray,
                  scale_x: np.ndarray, scale_y: np.ndarray,
                  offset_x: np.ndarray, offset_y: np.ndarray) -> AffinePlacement:
    """Best axis-aligned placement of ``src_mask`` onto ``canvas_mask`` by IoU.

    All four sweeps are explicit arrays rather than ranges so the caller commits
    to exactly which candidates were considered — a search whose grid is implied
    by three floats is a search nobody can reproduce later.

    Ties are broken by the first candidate in the declared order, so the answer
    does not depend on floating-point noise between two equally good placements.
    """
    best = AffinePlacement((1.0, 1.0), (0.0, 0.0), -1.0)
    for sxv in scale_x:
        for syv in scale_y:
            for oxv in offset_x:
                for oyv in offset_y:
                    painted = _render_affine(src_mask, (sxv, syv), (oxv, oyv), canvas_mask.shape)
                    score = two_sided_iou(painted, canvas_mask)
                    if score > best.iou:
                        best = AffinePlacement((float(sxv), float(syv)),
                                               (float(oxv), float(oyv)), score)
    return best


# ---------------------------------------------------------------------------
# Stage 2 — thin-plate lattice, refined per control point
# ---------------------------------------------------------------------------

def lattice(src_shape: tuple[int, int], nx: int, ny: int,
            inset: float = 0.02) -> np.ndarray:
    """An ``nx`` x ``ny`` grid of source-pixel points, inset from the border.

    The inset keeps every control point strictly inside the image: a thin-plate
    spline is exact at its points and degrades to its affine trend outside their
    hull, so points sitting exactly on the edge would leave the border pixels
    extrapolated.
    """
    h, w = src_shape
    xs = np.linspace(w * inset, w * (1 - inset), nx)
    ys = np.linspace(h * inset, h * (1 - inset), ny)
    gx, gy = np.meshgrid(xs, ys)
    return np.column_stack([gx.ravel(), gy.ravel()])


def query_grid(shape: tuple[int, int], step: int) -> tuple[np.ndarray, tuple[int, int]]:
    """Canvas sample points for a reduced grid, as an ``(N, 2)`` array.

    Hoisted out of :func:`warp_mask` because the refinement loop evaluates the
    same points thousands of times while only the control points move; rebuilding
    a 115k-row coordinate array per trial was most of the cost.
    """
    h, w = shape
    ys = np.arange(0, h, step, dtype=np.float64) + 0.5
    xs = np.arange(0, w, step, dtype=np.float64) + 0.5
    gx, gy = np.meshgrid(xs, ys)
    return np.column_stack([gx.ravel(), gy.ravel()]), gx.shape


def lattice_box(box: tuple[float, float, float, float], nx: int, ny: int) -> np.ndarray:
    """An ``nx`` x ``ny`` grid of points filling a box, endpoints included.

    The lattice is laid out on the **canvas** side rather than the source side.
    Laying it out in source pixels looked natural and was wrong: a source whose
    frame extends past the top of the canvas puts whole rows of control points
    off the sheet, and clamping them back on collapses a row onto y=0 — which
    both wrecks the warp and, once two points coincide, makes the thin-plate
    system singular. Starting from canvas points that are inside the canvas by
    construction removes the failure mode instead of patching it.
    """
    x0, y0, x1, y1 = box
    gx, gy = np.meshgrid(np.linspace(x0, x1, nx), np.linspace(y0, y1, ny))
    return np.column_stack([gx.ravel(), gy.ravel()])


def warp_mask(src_pts: np.ndarray, canvas_pts: np.ndarray, src_mask: np.ndarray,
              shape: tuple[int, int], src_scale: tuple[float, float] = (1.0, 1.0),
              step: int = 1, query: tuple[np.ndarray, tuple[int, int]] | None = None
              ) -> tuple[np.ndarray, np.ndarray]:
    """Warp ``src_mask`` onto a ``shape`` canvas through a thin-plate spline.

    ``src_scale`` divides the fitted source coordinates before sampling, so the
    control points can be expressed in one frame (the parchment master) while the
    mask being sampled lives in a sibling's smaller frame (the climate map) —
    which is the whole point of the alias mechanism.

    Returns ``(land, inside)``: the warped mask, and where the warp landed inside
    the source image at all. Everything outside is False in both, so a caller
    scoring against it is scoring "the source says sea here" the same way for
    genuine sea and for no-coverage — the coverage figure is reported separately.
    """
    pts, grid_shape = query if query is not None else query_grid(shape, step)
    rbf = RBFInterpolator(canvas_pts, src_pts, kernel="thin_plate_spline", degree=1)
    out = rbf(pts)
    sx = out[:, 0].reshape(grid_shape) / src_scale[0]
    sy = out[:, 1].reshape(grid_shape) / src_scale[1]
    ih, iw = src_mask.shape
    inside = (sx >= 0) & (sx < iw) & (sy >= 0) & (sy < ih)
    land = np.zeros(grid_shape, dtype=bool)
    if inside.any():
        land[inside] = src_mask[np.rint(sy[inside]).astype(np.int64).clip(0, ih - 1),
                                np.rint(sx[inside]).astype(np.int64).clip(0, iw - 1)]
    return WarpResult(land, inside, fold_fraction(sx, sy, inside))


@dataclass(frozen=True)
class WarpResult:
    land: np.ndarray
    inside: np.ndarray
    folded: float

    def __iter__(self):
        # Kept unpackable as (land, inside) so existing two-value call sites read
        # naturally; `folded` is asked for by name where it matters.
        return iter((self.land, self.inside))


def fold_fraction(sx: np.ndarray, sy: np.ndarray, inside: np.ndarray | None = None) -> float:
    """Fraction of the sampled area where the warp turns itself inside out.

    A thin-plate spline through independently-placed control points is under no
    obligation to stay injective, and when it folds, two separate parts of the
    canvas sample the *same* part of the source. That is not a small error: the
    cells traced out of the folded band come back as long thin ribbons running
    across whole continents, which is what a first, unconstrained fit produced —
    21% of the covered canvas was inside a fold, and Lustria, the southern Old
    World and southern Cathay were visibly striped because of it.

    The test is the sign of the Jacobian determinant of the canvas -> source map.
    Positive everywhere means orientation-preserving, i.e. locally one-to-one.
    """
    dxdy, dxdx = np.gradient(sx)
    dydy, dydx = np.gradient(sy)
    det = dxdx * dydy - dxdy * dydx
    sel = det if inside is None else det[inside]
    return 0.0 if sel.size == 0 else float((sel <= 0).mean())


def refine(src_pts: np.ndarray, canvas_pts: np.ndarray, src_mask: np.ndarray,
           canvas_mask: np.ndarray, src_scale: tuple[float, float] = (1.0, 1.0),
           step: int = 16, radii: tuple[float, ...] = (128.0, 48.0, 16.0),
           passes: int = 2, log=None,
           bounds: tuple[float, float] | None = None,
           max_fold: float = 0.0) -> tuple[np.ndarray, float]:
    """Coordinate descent: move each control point's canvas position to raise IoU.

    Each point is tried at its current position and at eight neighbours a given
    radius away, keeping whichever scores best, then the radius shrinks. Moving
    one point at a time (rather than optimising all of them jointly) is what keeps
    this tractable: the thin-plate solve is over the control points only, so a
    single trial is one small linear solve plus one warp of the reduced canvas.

    ``step`` reduces the canvas the score is computed on. Registration error worth
    correcting is tens of canvas pixels; scoring at full resolution would cost
    ~256x more for a decision that does not change.

    The candidate offsets are a fixed sequence and the acceptance test is strictly
    ">", so the descent is deterministic: same inputs, same record.
    """
    canvas_pts = np.array(canvas_pts, dtype=np.float64, copy=True)
    small = canvas_mask[::step, ::step]
    shape = canvas_mask.shape
    query = query_grid(shape, step)

    def score(pts: np.ndarray) -> float:
        """IoU, or -1 for a candidate that folds the warp.

        Rejecting outright rather than penalising is deliberate: a fold is not a
        slightly worse registration, it is a warp that maps two places to one and
        cannot be traced from. Since the affine seed is fold-free by construction
        and every accepted move is checked, the fit stays injective throughout.
        """
        r = warp_mask(src_pts, pts, src_mask, shape, src_scale, step=step, query=query)
        if r.folded > max_fold:
            return -1.0
        return two_sided_iou(r.land[:small.shape[0], :small.shape[1]], small)

    best = score(canvas_pts)
    if log:
        log(f"    seed IoU {best:.4f}")
    offsets = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    for radius in radii:
        for p in range(passes):
            moved = 0
            for i in range(len(canvas_pts)):
                keep = canvas_pts[i].copy()
                for dx, dy in offsets:
                    trial = keep + np.array([dx * radius, dy * radius])
                    if bounds is not None:
                        trial = np.array([min(max(trial[0], 0.0), bounds[0]),
                                          min(max(trial[1], 0.0), bounds[1])])
                        # A trial that clamps onto another control point would
                        # make the thin-plate system singular; skip it.
                        if np.any(np.all(np.isclose(np.delete(canvas_pts, i, axis=0), trial), axis=1)):
                            continue
                    canvas_pts[i] = trial
                    s = score(canvas_pts)
                    if s > best:
                        best, keep, moved = s, canvas_pts[i].copy(), moved + 1
                canvas_pts[i] = keep
            if log:
                log(f"    radius {radius:>6.1f} pass {p + 1}: IoU {best:.4f} ({moved} moves)")
            if moved == 0:
                break
    return canvas_pts, best


def residual_report(src_pts: np.ndarray, canvas_pts: np.ndarray,
                    seed_canvas_pts: np.ndarray) -> dict:
    """How far refinement moved each control point off its affine seed.

    A large, *spatially coherent* set of moves means the affine seed was simply
    the wrong scale there and the lattice absorbed it; a large isolated move means
    that one point found a local match that its neighbours disagree with, and is
    worth looking at in the overlay before trusting it.
    """
    d = np.hypot(*(canvas_pts - seed_canvas_pts).T)
    return {
        "n": int(len(d)),
        "mean_px": float(d.mean()),
        "max_px": float(d.max()),
        "p90_px": float(np.percentile(d, 90)),
    }


def to_records(src_pts: np.ndarray, canvas_pts: np.ndarray, notes) -> list[dict]:
    """Control points as registration-record JSON dicts, rounded to 0.1 px.

    Rounding is deliberate: the record is committed text that a human has to be
    able to read and diff, and a tenth of a canvas pixel is four orders of
    magnitude finer than the registration error being described.
    """
    out = []
    for i, ((sx, sy), (cx, cy)) in enumerate(zip(src_pts, canvas_pts)):
        out.append({
            "source": [round(float(sx), 1), round(float(sy), 1)],
            "canvas": [round(float(cx), 1), round(float(cy), 1)],
            "note": notes(i) if callable(notes) else str(notes),
        })
    return out


def clamp_canvas(pts: np.ndarray, width: int, height: int) -> np.ndarray:
    """Keep canvas-side points inside the canvas.

    ``sources.py`` rejects a control point outside the canvas, and rightly: a
    record that places a feature off the sheet is describing a placement the
    generator cannot honour. Descent is bounded here rather than after the fact so
    the search never spends passes exploring positions the schema forbids.
    """
    out = np.array(pts, dtype=np.float64, copy=True)
    np.clip(out[:, 0], 0.0, float(width), out=out[:, 0])
    np.clip(out[:, 1], 0.0, float(height), out=out[:, 1])
    return out
