"""Reprojection — place a registered source image onto the Miller canvas.

The canvas is Miller cylindrical (see ``config/canvas_frame``, which measures the
frame off vanilla's own shipped bitmap). Nothing in this module hardcodes that:
every canvas <-> lon/lat conversion below delegates to ``canvas_frame``'s two
helpers, so the frame is defined in exactly one place. Miller's inverse is closed
form, so no iterative solver enters the pipeline and byte-exact regeneration
survives the change.

Stage-A ingestion has to reconcile three different source geometries onto one
frame:

``natural_earth_2``
    The Terraqueous globe is drawn in the Natural Earth II pseudocylindrical
    projection (the map says so in its own legend, and the fit below confirms
    it). NE II has no closed-form inverse, so we never invert it: we walk the
    *target* canvas, turn each pixel into (lon, lat), and evaluate the forward
    polynomial to find where to sample the source. Forward-only means no
    iterative solver and no ``pyproj`` dependency.

``equirectangular``
    Already-rectangular sources. Degenerate case of the same code path — the
    "projection" is the identity, so only the fitted placement matters.

``control_point_warp``
    Regional maps with no analytic projection (a GW illustration, a 3D game
    render). A thin-plate spline through the hand-picked control-point pairs
    builds a smooth canvas -> source coordinate field.

Every path produces the same thing: for a block of canvas pixels, the float
source coordinates to sample. :func:`resample` then does the sampling. All of it
is deterministic given fixed inputs — no wall-clock, no RNG, no threaded kernels
(see ``mapgen/requirements.txt`` on why opencv was rejected).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.interpolate import RBFInterpolator
from scipy.spatial import Delaunay

from config import canvas_frame
from worldgen import schema

# ---------------------------------------------------------------------------
# Natural Earth II forward polynomial
# ---------------------------------------------------------------------------
#
# Savric, Patterson & Jenny (2015), "The Natural Earth II world map projection",
# International Journal of Cartography 1(2). Constants transcribed from the
# reference implementation in PROJ (``src/projections/natearth2.cpp``) rather
# than retyped from the paper's table, so they match what every other tool uses.
#
#     x = lam * (A0 + A1*phi^2 + phi^12*(A2 + A3*phi^2 + A4*phi^4 + A5*phi^6))
#     y = phi * (B0 + phi^8*(B1 + B2*phi^2 + B3*phi^4))
#
# with lam/phi in radians. Output is in earth radii; the fitted scale below
# converts to source pixels.

_A0, _A1, _A2, _A3, _A4, _A5 = 0.84719, -0.13063, -0.04515, 0.05494, -0.02326, 0.00331
_B0, _B1, _B2, _B3 = 1.01183, -0.02625, 0.01926, -0.00396


def ne2_forward(lam, phi):
    """Natural Earth II forward projection. ``lam``/``phi`` in radians."""
    lam = np.asarray(lam, dtype=np.float64)
    phi = np.asarray(phi, dtype=np.float64)
    p2 = phi * phi
    p4 = p2 * p2
    p6 = p2 * p4
    x = lam * (_A0 + _A1 * p2 + p6 * p6 * (_A2 + _A3 * p2 + _A4 * p4 + _A5 * p6))
    y = phi * (_B0 + p4 * p4 * (_B1 + _B2 * p2 + _B3 * p4))
    return x, y


#: Normalized half-extents: x at (lon 180, lat 0) and y at lat 90.
NE2_XMAX = float(ne2_forward(np.pi, 0.0)[0])
NE2_YMAX = float(ne2_forward(0.0, np.pi / 2)[1])


def ne2_inverse(x, y):
    """Inverse of :func:`ne2_forward` — normalized ``(x, y)`` back to radians.

    NE II has no closed-form inverse, but it does not need a 2-D solver either:
    ``y`` is a function of latitude alone and strictly increasing in it, so one
    monotonic 1-D solve recovers phi, after which lam falls out by a single
    division. Bisection over the fixed bracket [-pi/2, pi/2] for a fixed 60
    iterations is deterministic to the last bit — no convergence tolerance whose
    trip point could vary with the input, which a byte-exact pipeline cannot have.

    The forward direction is what the generators use; this exists so a feature
    *identified on the Terraqueous source* can be converted into an exact canvas
    position, which is how the other sources' control points are anchored.
    """
    y = np.asarray(y, dtype=np.float64)
    lo = np.full(y.shape, -np.pi / 2)
    hi = np.full(y.shape, np.pi / 2)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        too_low = ne2_forward(0.0, mid)[1] < y
        lo = np.where(too_low, mid, lo)
        hi = np.where(too_low, hi, mid)
    phi = 0.5 * (lo + hi)
    # x = lam * f(phi); recover f(phi) by projecting a unit longitude.
    f = ne2_forward(1.0, phi)[0]
    return np.asarray(x, dtype=np.float64) / f, phi


def _project_norm(kind: str, lon_deg, lat_deg):
    """Normalized projected coordinates for a projection kind (y up)."""
    if kind == "natural_earth_2":
        return ne2_forward(np.radians(lon_deg), np.radians(lat_deg))
    if kind == "equirectangular":
        return np.asarray(lon_deg, dtype=np.float64), np.asarray(lat_deg, dtype=np.float64)
    raise ValueError(f"{kind} is not a parametric projection")


def _project_norm_separable(kind: str, lon_deg, lat_deg):
    """``(x_per_lon, y)`` for a *column* of latitudes — the separable form.

    Both NE II and plain equirectangular factor as ``X = lam * f(phi)`` and
    ``Y = g(phi)``: the latitude-dependent parts do not involve longitude at all.
    Evaluating them on an ``(R, 1)`` column and only then broadcasting across
    longitude turns a dozen full ``R x W`` float64 temporaries into a dozen
    ``R x 1`` ones. At heightmap width that is the difference between ~300 MB of
    transient allocation per block and a few kilobytes, which is what makes a
    118-megapixel target practical to build in blocks at all.
    """
    if kind == "natural_earth_2":
        phi = np.radians(np.asarray(lat_deg, dtype=np.float64))
        p2 = phi * phi
        p4 = p2 * p2
        p6 = p2 * p4
        f = _A0 + _A1 * p2 + p6 * p6 * (_A2 + _A3 * p2 + _A4 * p4 + _A5 * p6)
        y = phi * (_B0 + p4 * p4 * (_B1 + _B2 * p2 + _B3 * p4))
        return np.radians(np.asarray(lon_deg, dtype=np.float64)) * f, y
    if kind == "equirectangular":
        return (np.asarray(lon_deg, dtype=np.float64) * np.ones_like(np.asarray(lat_deg, dtype=np.float64)),
                np.asarray(lat_deg, dtype=np.float64))
    raise ValueError(f"{kind} is not a parametric projection")


# ---------------------------------------------------------------------------
# Fitting a registration's placement
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParametricFit:
    """``source_px = (cx + sx * X,  cy - sy * Y)`` for normalized ``(X, Y)``."""

    kind: str
    cx: float
    cy: float
    sx: float
    sy: float
    rms_px: float
    max_px: float

    def to_source(self, lon_deg, lat_deg):
        X, Y = _project_norm(self.kind, lon_deg, lat_deg)
        return self.cx + self.sx * X, self.cy - self.sy * Y

    def to_lonlat(self, source_x, source_y):
        """Inverse: source pixel -> ``(lon, lat)`` in degrees."""
        X = (np.asarray(source_x, dtype=np.float64) - self.cx) / self.sx
        Y = (self.cy - np.asarray(source_y, dtype=np.float64)) / self.sy
        if self.kind == "natural_earth_2":
            lam, phi = ne2_inverse(X, Y)
            return np.degrees(lam), np.degrees(phi)
        if self.kind == "equirectangular":
            return X, Y
        raise ValueError(f"{self.kind} is not a parametric projection")

    def to_canvas(self, source_x, source_y, width: int, height: int):
        """Source pixel -> canvas pixel on a ``width`` x ``height`` Miller grid.

        This is the bridge that lets every other source's control points be
        anchored to the Terraqueous globe: identify a named feature on the globe,
        and this returns the canvas pixel it occupies — exactly, through the same
        fitted projection the committed mask was built with, rather than by
        eyeballing the mask.

        It is also why the whole seed-driven registration family follows a frame
        change for free: ``fit_registration.anchor_landmarks`` stores landmarks as
        *globe source px* and calls this at fit time, so re-running the fit is all
        a reframe needs.
        """
        lon, lat = self.to_lonlat(source_x, source_y)
        return canvas_frame.lonlat_to_canvas(lon, lat, width, height)


class RegistrationError(RuntimeError):
    """A registration record could not be fitted to its control points."""


def fit_parametric(reg: schema.SourceRegistration) -> ParametricFit:
    """Least-squares fit a parametric registration from its control points.

    Each control point pins a canvas pixel to a source pixel. The canvas pixel
    carries a (lon, lat) by definition of the Miller frame, so projecting it
    gives a normalized coordinate, and the source pixel is then an affine
    function of that — two independent 2-parameter linear fits, solved exactly.

    The returned residuals are the honest measure of how well the record
    describes the image; a hand-edit that drags a control point off its feature
    shows up here immediately.
    """
    if reg.projection not in ("natural_earth_2", "equirectangular"):
        raise RegistrationError(f"{reg.source}: {reg.projection} is not a parametric projection")

    lon, lat, sxp, syp = [], [], [], []
    for cp in reg.control_points:
        cxx, cyy = cp.canvas
        # A control point on the wrap seam is recorded at x = WIDTH; keep it
        # there rather than folding to 0, or the fit sees lon -180 for a +180
        # feature and the scale collapses. ``canvas_to_lonlat`` does not fold,
        # which is exactly why it is the direction used here.
        lo, la = canvas_frame.canvas_to_lonlat(cxx, cyy)
        lon.append(float(lo))
        lat.append(float(la))
        sxp.append(cp.source[0])
        syp.append(cp.source[1])

    X, Y = _project_norm(reg.projection, np.array(lon), np.array(lat))
    sxp = np.array(sxp, dtype=np.float64)
    syp = np.array(syp, dtype=np.float64)

    # source_x = cx + sx * X   /   source_y = cy - sy * Y
    ax = np.column_stack([np.ones_like(X), X])
    ay = np.column_stack([np.ones_like(Y), -Y])
    (cx, sx), *_ = np.linalg.lstsq(ax, sxp, rcond=None)
    (cy, sy), *_ = np.linalg.lstsq(ay, syp, rcond=None)

    rx = (cx + sx * X) - sxp
    ry = (cy - sy * Y) - syp
    r = np.concatenate([rx, ry])
    fit = ParametricFit(reg.projection, float(cx), float(cy), float(sx), float(sy),
                        float(np.sqrt((r ** 2).mean())), float(np.abs(r).max()))
    if fit.sx <= 0 or fit.sy <= 0:
        raise RegistrationError(
            f"{reg.source}: fitted a non-positive scale (sx={fit.sx:.3f}, sy={fit.sy:.3f}) — "
            f"control points are probably mirrored or mis-paired"
        )
    return fit


@dataclass(frozen=True)
class WarpFit:
    """Thin-plate-spline canvas -> source coordinate field."""

    rbf: RBFInterpolator
    rms_px: float
    max_px: float

    def to_source_px(self, canvas_x, canvas_y):
        pts = np.column_stack([np.ravel(canvas_x), np.ravel(canvas_y)])
        out = self.rbf(pts)
        shape = np.shape(canvas_x)
        return out[:, 0].reshape(shape), out[:, 1].reshape(shape)


@dataclass(frozen=True)
class InverseWarpFit:
    """Thin-plate-spline source -> canvas coordinate field — the reverse
    direction of :class:`WarpFit`, through the same control points.

    Lets a caller walk a source image at its own native resolution and sample
    canvas-space data (e.g. the coastline mask) onto it, instead of resampling
    the source down into its (typically much smaller) canvas footprint.
    """

    rbf: RBFInterpolator
    rms_px: float
    max_px: float

    def to_canvas_px(self, source_x, source_y):
        pts = np.column_stack([np.ravel(source_x), np.ravel(source_y)])
        out = self.rbf(pts)
        shape = np.shape(source_x)
        return out[:, 0].reshape(shape), out[:, 1].reshape(shape)


def fit_warp_inverse(reg: schema.SourceRegistration) -> InverseWarpFit:
    """Fit the source -> canvas warp through the record's control points.

    Same control points and kernel as :func:`fit_warp`, with source/canvas
    swapped, so this is exact at every control point and follows the same
    affine-trend-outside-the-hull behaviour.
    """
    if reg.projection != "control_point_warp":
        raise RegistrationError(f"{reg.source}: fit_warp_inverse needs a control_point_warp record")
    src = np.array([cp.source for cp in reg.control_points], dtype=np.float64)
    dst = np.array([cp.canvas for cp in reg.control_points], dtype=np.float64)
    if len(src) < 3:
        raise RegistrationError(f"{reg.source}: a warp needs at least 3 control points")
    rbf = RBFInterpolator(src, dst, kernel="thin_plate_spline", degree=1)
    back = rbf(src)
    r = (back - dst).ravel()
    return InverseWarpFit(rbf, float(np.sqrt((r ** 2).mean())), float(np.abs(r).max()))


# ---------------------------------------------------------------------------
# Piecewise-affine warp (Delaunay triangulation of the control points)
# ---------------------------------------------------------------------------

#: Coordinate returned for a query point outside the triangulation's convex hull.
#: A piecewise-affine field has no data past the hull (unlike a degree-1 thin-plate
#: spline, which degrades into its affine trend), so those pixels must read as
#: "outside the source frame" and be dropped. A large negative value survives both
#: the comparison masks (``sx >= 0``) and the ``clip``/``astype`` paths every
#: consumer already applies to keep a source inside its own frame.
_OUTSIDE_HULL = -1.0e9


def _affine_eval(tri: Delaunay, dst_pts: np.ndarray, simp: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Evaluate triangle ``simp[i]``'s own affine map at query point ``q[i]``.

    The barycentric formula is valid (as an *extrapolation* of that triangle's
    local affine map) for a query point outside the triangle too — nothing here
    clamps the barycentric weights to ``[0, 1]``. Callers decide whether a given
    ``simp``/``q`` pairing is a real "inside" hit or a deliberate extrapolation
    (see :func:`_bary_interp`'s ``buffer_px``).
    """
    T = tri.transform[simp]
    d = q - T[:, 2]
    b01 = np.einsum("mij,mj->mi", T[:, :2], d)
    bary = np.column_stack([b01, 1.0 - b01.sum(axis=1)])
    verts = tri.simplices[simp]
    return np.einsum("mi,mij->mj", bary, dst_pts[verts])


def _bary_interp(tri: Delaunay, dst_pts: np.ndarray, qx, qy, buffer_px: float = 0.0):
    """Piecewise-affine interpolation of ``dst_pts`` over triangulation ``tri``.

    ``tri`` is the Delaunay triangulation of the *from* points; ``dst_pts`` are the
    matching *to* points (same row order as the points ``tri`` was built on). For
    each query ``(qx, qy)`` the containing triangle's barycentric coordinates
    weight its three ``dst_pts`` vertices — exact at every vertex, continuous
    across every shared edge, and :data:`_OUTSIDE_HULL` past the convex hull.

    ``buffer_px > 0`` softens only the *outer* edge of that cutoff: a query point
    outside every triangle, but within ``buffer_px`` of the nearest **hull**
    vertex (never an interior one — interior points are already covered by real
    triangles), is placed by extrapolating that vertex's own incident triangle's
    affine map past its true bounds (see :func:`_affine_eval`). This is a QA/
    render-time convenience, not a real correspondence: accuracy past the hull is
    unverified and degrades with distance from it, so ``buffer_px`` defaults to 0
    (the strict, no-extrapolation behaviour) and every committed registration
    record relies on that default — see the piecewise_affine_warp design note in
    schema.py ("edge coverage is a dot-placement question, not a warp fallback").
    """
    shape = np.shape(qx)
    q = np.column_stack([np.ravel(qx).astype(np.float64), np.ravel(qy).astype(np.float64)])
    simp = tri.find_simplex(q)
    out = np.full((q.shape[0], 2), _OUTSIDE_HULL, dtype=np.float64)
    inside = simp >= 0
    if inside.any():
        out[inside] = _affine_eval(tri, dst_pts, simp[inside], q[inside])
    if buffer_px > 0 and (~inside).any():
        from scipy.spatial import cKDTree

        hull_verts = np.unique(tri.convex_hull.ravel())
        incident = tri.vertex_to_simplex[hull_verts]
        have_tri = incident >= 0
        hull_verts, incident = hull_verts[have_tri], incident[have_tri]
        if hull_verts.size:
            outside_idx = np.nonzero(~inside)[0]
            dist, nearest = cKDTree(tri.points[hull_verts]).query(q[outside_idx])
            within = dist <= buffer_px
            if within.any():
                sel = outside_idx[within]
                out[sel] = _affine_eval(tri, dst_pts, incident[nearest[within]], q[sel])
    return out[:, 0].reshape(shape), out[:, 1].reshape(shape)


@dataclass(frozen=True)
class PiecewiseAffineFit:
    """Piecewise-affine canvas -> source coordinate field.

    Duck-type-compatible with :class:`WarpFit` (same ``to_source_px`` and
    ``rms_px``/``max_px``), so every consumer that builds its field through
    :func:`fit_placement`/:func:`fit_warp` works unchanged. The fit is exact at
    every control point, hence ``rms_px == max_px == 0``.
    """

    tri: Delaunay
    src: np.ndarray  # source px, one row per triangulation vertex
    rms_px: float = 0.0
    max_px: float = 0.0
    buffer_px: float = 0.0  # outer-hull-only extrapolation margin; see _bary_interp

    def to_source_px(self, canvas_x, canvas_y):
        return _bary_interp(self.tri, self.src, canvas_x, canvas_y, self.buffer_px)


@dataclass(frozen=True)
class InversePiecewiseAffineFit:
    """Piecewise-affine source -> canvas field — the reverse of
    :class:`PiecewiseAffineFit`, triangulated on the *source* points.

    Its triangulation is independent of the forward one (Delaunay on the source
    points, not the canvas points), exactly as :class:`InverseWarpFit` fits its own
    reverse RBF rather than inverting the forward one; the two directions agree at
    every control point and are each internally continuous.
    """

    tri: Delaunay
    canvas: np.ndarray  # canvas px, one row per triangulation vertex
    rms_px: float = 0.0
    max_px: float = 0.0
    buffer_px: float = 0.0  # outer-hull-only extrapolation margin; see _bary_interp

    def to_canvas_px(self, source_x, source_y):
        return _bary_interp(self.tri, self.canvas, source_x, source_y, self.buffer_px)


def fit_piecewise(reg: schema.SourceRegistration, buffer_px: float = 0.0) -> PiecewiseAffineFit:
    """Fit the canvas -> source piecewise-affine field through the control points.

    ``buffer_px`` (default 0, the strict committed behaviour) softens only the
    outer hull edge — see :func:`_bary_interp`. It is a render-time convenience
    for QA consumers (``project_regions_unified.py --hull-buffer-px``), never
    stored in a registration record.
    """
    if reg.projection != "piecewise_affine_warp":
        raise RegistrationError(f"{reg.source}: fit_piecewise needs a piecewise_affine_warp record")
    src = np.array([cp.source for cp in reg.control_points], dtype=np.float64)
    dst = np.array([cp.canvas for cp in reg.control_points], dtype=np.float64)
    if len(src) < 3:
        raise RegistrationError(f"{reg.source}: a warp needs at least 3 control points")
    return PiecewiseAffineFit(Delaunay(dst), src, buffer_px=buffer_px)


def fit_piecewise_inverse(reg: schema.SourceRegistration,
                          buffer_px: float = 0.0) -> InversePiecewiseAffineFit:
    """Fit the source -> canvas piecewise-affine field (reverse direction).

    ``buffer_px`` — see :func:`fit_piecewise`.
    """
    if reg.projection != "piecewise_affine_warp":
        raise RegistrationError(
            f"{reg.source}: fit_piecewise_inverse needs a piecewise_affine_warp record")
    src = np.array([cp.source for cp in reg.control_points], dtype=np.float64)
    dst = np.array([cp.canvas for cp in reg.control_points], dtype=np.float64)
    if len(src) < 3:
        raise RegistrationError(f"{reg.source}: a warp needs at least 3 control points")
    return InversePiecewiseAffineFit(Delaunay(src), dst, buffer_px=buffer_px)


def fit_warp(reg: schema.SourceRegistration) -> WarpFit:
    """Fit a smooth canvas -> source warp through the control points.

    ``thin_plate_spline`` with ``degree=1`` keeps an affine polynomial term, so
    sampling slightly outside the control-point hull degrades into the affine
    trend instead of diverging the way a pure RBF would. Interpolation is exact
    at the control points, so the reported residual is a numerical-conditioning
    check rather than a goodness-of-fit measure.
    """
    if reg.projection != "control_point_warp":
        raise RegistrationError(f"{reg.source}: fit_warp needs a control_point_warp record")
    src = np.array([cp.source for cp in reg.control_points], dtype=np.float64)
    dst = np.array([cp.canvas for cp in reg.control_points], dtype=np.float64)
    if len(src) < 3:
        raise RegistrationError(f"{reg.source}: a warp needs at least 3 control points")
    rbf = RBFInterpolator(dst, src, kernel="thin_plate_spline", degree=1)
    back = rbf(dst)
    r = (back - src).ravel()
    return WarpFit(rbf, float(np.sqrt((r ** 2).mean())), float(np.abs(r).max()))


@dataclass(frozen=True)
class AliasFit:
    """A sibling's canvas -> source field, borrowed from its parent's warp.

    The parent maps canvas px to *parent* source px; the committed affine then
    carries those into this source's own pixel grid. Composing rather than
    re-fitting is the whole point: a correction to the parent's control points
    reaches every sibling on the next run, and no sibling can drift from the
    frame it is supposed to share.
    """

    parent: WarpFit
    parent_source: str
    scale: tuple[float, float]
    offset: tuple[float, float]

    def to_source_px(self, canvas_x, canvas_y):
        px, py = self.parent.to_source_px(canvas_x, canvas_y)
        return (px - self.offset[0]) / self.scale[0], (py - self.offset[1]) / self.scale[1]

    @property
    def rms_px(self) -> float:
        return self.parent.rms_px

    @property
    def max_px(self) -> float:
        return self.parent.max_px


def fit_alias(reg: schema.SourceRegistration,
              regs_by_source: dict[str, schema.SourceRegistration]) -> AliasFit:
    """Resolve a ``frame_alias`` record against its parent registration."""
    if not reg.is_alias:
        raise RegistrationError(f"{reg.source}: fit_alias needs a frame_alias record")
    parent = regs_by_source.get(reg.frame_alias.of)
    if parent is None:
        raise RegistrationError(
            f"{reg.source}: frame_alias parent '{reg.frame_alias.of}' is not registered"
        )
    if parent.projection != "control_point_warp":
        raise RegistrationError(
            f"{reg.source}: frame_alias parent '{parent.source}' is {parent.projection}; "
            f"only a control_point_warp parent is supported"
        )
    return AliasFit(fit_warp(parent), parent.source, reg.frame_alias.scale, reg.frame_alias.offset)


def fit_placement(reg: schema.SourceRegistration,
                  regs_by_source: dict[str, schema.SourceRegistration] | None = None,
                  buffer_px: float = 0.0):
    """The canvas -> source field for any record kind.

    Returns a :class:`WarpFit`/:class:`AliasFit` (``to_source_px``) for the warp
    kinds, or a :class:`ParametricFit` (``to_source``) for the analytic ones.
    ``buffer_px`` only affects a ``piecewise_affine_warp`` record — see
    :func:`fit_piecewise`; every other kind ignores it.
    """
    if reg.is_alias:
        return fit_alias(reg, regs_by_source or {})
    if reg.projection == "control_point_warp":
        return fit_warp(reg)
    if reg.projection == "piecewise_affine_warp":
        return fit_piecewise(reg, buffer_px=buffer_px)
    return fit_parametric(reg)


def fit_placement_inverse(reg: schema.SourceRegistration):
    """The source -> canvas field (``to_canvas_px``) for a warp record.

    The inverse mirror of :func:`fit_placement`: dispatches a ``control_point_warp``
    to :class:`InverseWarpFit` and a ``piecewise_affine_warp`` to
    :class:`InversePiecewiseAffineFit`. Only the warp kinds have a source->canvas
    inverse; a parametric or alias record raises.
    """
    if reg.projection == "control_point_warp":
        return fit_warp_inverse(reg)
    if reg.projection == "piecewise_affine_warp":
        return fit_piecewise_inverse(reg)
    raise RegistrationError(
        f"{reg.source}: no source->canvas inverse for projection '{reg.projection}'")


# ---------------------------------------------------------------------------
# Canvas -> source coordinate fields
# ---------------------------------------------------------------------------

def canvas_lonlat(y_rows: np.ndarray, width: int, height: int):
    """(lon, lat) grids for whole canvas rows ``y_rows`` of a ``width``x``height`` canvas.

    Returned as ``(lon[1, W], lat[R, 1])`` so callers broadcast instead of
    materialising two full R x W float64 grids — at heightmap resolution that
    difference is gigabytes.

    Miller keeps that separability: longitude still depends only on x and
    latitude only on y, so each axis is converted on its own vector and the
    unused argument is a scalar the helper ignores.
    """
    xs = (np.arange(width, dtype=np.float64) + 0.5)[None, :]
    ys = (y_rows.astype(np.float64) + 0.5)[:, None]
    lon, _ = canvas_frame.canvas_to_lonlat(xs, 0.0, width, height)
    _, lat = canvas_frame.canvas_to_lonlat(0.0, ys, width, height)
    return lon, lat


def source_coords_parametric(fit: ParametricFit, y_rows: np.ndarray, width: int, height: int):
    """Source (x, y) pixel coordinates for canvas rows ``y_rows``, as full grids."""
    lon, lat = canvas_lonlat(y_rows, width, height)
    xn, yn = _project_norm_separable(fit.kind, lon, lat)   # (R, W) and (R, 1)
    src_x = fit.cx + fit.sx * xn
    src_y = np.broadcast_to(fit.cy - fit.sy * yn, src_x.shape).copy()
    return src_x, src_y


def source_coords_warp(fit: WarpFit, y_rows: np.ndarray, width: int, height: int,
                       canvas_w: int, canvas_h: int):
    """Source coordinates for canvas rows of a grid that may be a multiple of the canvas.

    ``width``/``height`` are the grid being filled; ``canvas_w``/``canvas_h`` are
    the registration's own coordinate system, so a heightmap-resolution grid
    still evaluates the warp in canvas pixels.
    """
    sxc = canvas_w / width
    syc = canvas_h / height
    xs = (np.arange(width, dtype=np.float64) + 0.5) * sxc
    ys = (y_rows.astype(np.float64) + 0.5) * syc
    gx = np.broadcast_to(xs[None, :], (len(y_rows), width))
    gy = np.broadcast_to(ys[:, None], (len(y_rows), width))
    return fit.to_source_px(gx, gy)


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def resample(plane: np.ndarray, src_x: np.ndarray, src_y: np.ndarray, order: int = 1,
             cval: float = 0.0) -> np.ndarray:
    """Sample a single 2-D source plane at float coordinates.

    ``order=1`` (bilinear) for continuous fields, ``order=0`` (nearest) for
    labels/masks. ``mode="nearest"`` clamps at the source border so a coordinate
    a hair outside the image edge reuses the edge pixel rather than punching a
    hole; anything far outside is the caller's problem to mask.
    """
    coords = np.stack([src_y, src_x])
    return ndimage.map_coordinates(plane, coords, order=order, mode="nearest", cval=cval)


def crop_mask(reg: schema.SourceRegistration, src_x: np.ndarray, src_y: np.ndarray) -> np.ndarray:
    """Which sampled coordinates fall inside the record's ``crop`` (all, if none)."""
    if reg.crop is None:
        return np.ones(src_x.shape, dtype=bool)
    x0, y0, x1, y1 = reg.crop
    return (src_x >= x0) & (src_x <= x1) & (src_y >= y0) & (src_y <= y1)
