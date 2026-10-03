"""The geographic frame the source-driven ingestion stage registers onto.

``map_config`` fixes the canvas *dimensions*; this module fixes what those pixels
*mean* geographically, so every source (Terraqueous NE-II oval, the Immortal
Empires parchment family, the Total War renders) can be placed on one shared
coordinate system.

The canvas is a **Miller cylindrical sheet**. That is not a taste decision: it is
what Victoria 3's own shipped map is drawn in, measured rather than assumed by
``mapgen/measure_vanilla_frame.py`` (rerun it — it reads the read-only install and
prints the table below). Vanilla declares no projection anywhere, so the frame was
recovered from 29 island states, whose footprints *are* the islands they are named
after::

    R pinned to W/2pi by wrap_x       median |dy|
        Miller                             2.5 px      <-- adopted
        Mercator                          12.3 px
        plate carree                      28.0 px
        Gall stereographic                50.5 px

Two independent facts confirm it. Miller wins outright once ``R`` is pinned, and
its *free-scale* fit returns R = 1.0112 x the canvas's own ``W / 2*pi`` — i.e.
vanilla is a **true, unscaled** Miller in which 8192 px is exactly 360 degrees of
longitude. ``wrap_x`` (see ``map_config``) makes longitude periodic, so x = 0 and
x = WIDTH are the same meridian, and that periodicity is what pins ``R``.

Provenance of the three constants, which is deliberately not uniform:

``R_CANVAS``
    Forced. ``wrap_x`` means 8192 px = 360 deg, so R = WIDTH / 2*pi. Nothing to
    choose.
``X0``
    Measured against vanilla (``measure_vanilla_frame.py`` reports 4099.0 on the
    29-anchor set; 4098.0 is kept as the committed value the migration was
    computed against — one pixel apart, against a 4.1 px median |dx| scatter, so
    re-deriving it would churn every record to move nothing).
``Y0``
    **Not** vanilla's. Vanilla's equator sits at 2102.8, but its band is
    asymmetric because Earth's landmasses are, and the Warhammer world has Chaos
    Wastes at *both* poles. The user resolved it by drawing a northern limit on a
    local-only annotated copy of the globe
    (``sources/terraqueous_globe_with_NS_lines.jpg``, 2026-07-29; renamed since,
    bytes unchanged); recovered by
    differencing against the clean source, that line is source row 238.183 =
    **74.9050 N**. ``Y0 = 2142.0`` puts the canvas top edge exactly on it.

    That file is **markup, not a source**: it is not registered, not listed in
    ``mapgen/SOURCES.md``, and never consumed. Adding it to the manifest would make
    ``sources.py --verify`` go red the day the user deletes their scratch file.
    This docstring is its only record.

The band does not fit and could not: R is pinned, so the canvas covers exactly
132.31 deg of latitude, while the user's marked keep-band spans 149.8 deg. The
667 px overflow is spent entirely in the south, which is the minimum on both
total land loss (0.686%) and loss of land the user did not mark free (0.466%).

    top     y = 0     ->  +74.9052 N
    bottom  y = 3616  ->  -57.4084 S
    x = 0             ->  lon -180.0879        span 132.3136 deg

Nothing here is read by Victoria 3 — it is offline ingestion config, committed so
the placement of every source (and thus every derived bitmap) is reproducible
from the committed data plus the local ``sources/`` file.
"""

from __future__ import annotations

import numpy as np

from config.map_config import PROVINCES_SIZE

WIDTH, HEIGHT = PROVINCES_SIZE  # (8192, 3616)

# ---------------------------------------------------------------------------
# Miller cylindrical frame
# ---------------------------------------------------------------------------

#: Miller's compression constants. ``y = K * ln(tan(pi/4 + C*phi))`` with
#: K = 1/0.8 and C = 0.4 — i.e. Mercator applied to four fifths of the latitude
#: and stretched back by five fourths. Written out rather than as ``1/0.8`` so the
#: closed-form inverse below reads against the same two numbers.
MILLER_K = 1.25
MILLER_C = 0.4

#: px per radian. Forced by ``wrap_x``: 8192 px is exactly 360 deg of longitude.
R_CANVAS = WIDTH / (2.0 * np.pi)

#: Canvas x of the prime meridian (measured against vanilla).
X0 = 4098.0

#: Canvas y of the equator (the user's drawn northern limit — see the docstring).
Y0 = 2142.0


def _miller_y(lat_deg):
    """Miller's normalized y (north-positive, in units of R) for degrees."""
    phi = np.radians(np.asarray(lat_deg, dtype=np.float64))
    return MILLER_K * np.log(np.tan(np.pi / 4.0 + MILLER_C * phi))


def _miller_lat(y_norm):
    """Inverse of :func:`_miller_y` — normalized y back to degrees.

    Closed form, so no iterative solver enters the pipeline and byte-exact
    regeneration is preserved (``.claude/rules/core.md`` determinism).
    """
    y = np.asarray(y_norm, dtype=np.float64)
    return np.degrees((np.arctan(np.exp(y / MILLER_K)) - np.pi / 4.0) / MILLER_C)


#: Latitude of the canvas's top and bottom rows, and longitude of its left edge.
#: Derived, never typed — a hand-edited band would silently disagree with the
#: constants everything else converts through.
LAT_TOP = float(_miller_lat((Y0 - 0.0) / R_CANVAS))
LAT_BOTTOM = float(_miller_lat((Y0 - HEIGHT) / R_CANVAS))
LON_AT_X0 = float(np.degrees(-X0 / R_CANVAS))


#: Earth's equatorial circumference in km (WGS-84 equatorial radius x 2*pi).
EARTH_CIRCUMFERENCE_KM = 40075.017


def km2_per_px(lat_deg):
    """True ground area, in km^2, of one canvas pixel at latitude ``lat_deg``.

    Miller is neither equal-area nor conformal. At latitude phi its meridian
    scale is ``h = sec(0.8 phi)`` (dy/dphi) and its parallel scale ``k = sec phi``,
    so one canvas px covers ``(circumference / WIDTH)^2 * cos(phi) * cos(0.8 phi)``
    km^2 of ground; at the equator that is (40,075.017 / 8192)^2 = 23.93 km^2.
    Pure and closed-form (determinism). Works on scalars or arrays; the frame is
    the same for every canvas scale because the grids are uniform multiples
    (:func:`_scale`), so ``WIDTH`` is the 1:1 canvas.
    """
    phi = np.radians(np.asarray(lat_deg, dtype=np.float64))
    km_per_px = EARTH_CIRCUMFERENCE_KM / WIDTH
    return km_per_px * km_per_px * np.cos(phi) * np.cos(MILLER_C * 2.0 * phi)


def _scale(width: int, height: int) -> float:
    """Uniform canvas scale factor, asserted to be uniform.

    The heightmap grid is exactly 2x the canvas and the ingest preview exactly
    1/16, so every grid the toolchain builds is a uniform multiple. Asserting it
    means a future non-uniform grid raises here instead of quietly distorting
    latitude — under plate carree that mistake was survivable, under Miller it
    would bend the whole world.
    """
    k = width / WIDTH
    expected = round(HEIGHT * k)
    if height != expected:
        raise ValueError(
            f"canvas frame needs a uniformly scaled grid: {width}x{height} implies "
            f"k={k:.6g}, which wants height {expected}, not {height}"
        )
    return k


def lonlat_to_canvas(lon, lat, width: int = WIDTH, height: int = HEIGHT):
    """(lon, lat) in degrees -> (x, y) px on a ``width`` x ``height`` canvas.

    x is folded into ``[0, width)``. y is **not** clamped: under plate carree the
    old clamp was harmless, but under Miller a feature at 78 N would pin silently
    to row 0 and register wrong. Callers that genuinely want a clamp call
    ``worldgen.register.clamp_canvas``.
    """
    k = _scale(width, height)
    x = (X0 * k + R_CANVAS * k * np.radians(np.asarray(lon, dtype=np.float64))) % width
    y = Y0 * k - R_CANVAS * k * _miller_y(lat)
    return (x, y)


def canvas_to_lonlat(x, y, width: int = WIDTH, height: int = HEIGHT):
    """Inverse of :func:`lonlat_to_canvas`.

    x is **not** folded, deliberately: ``reproject.fit_parametric`` relies on a
    control point recorded on the wrap seam at ``x = WIDTH`` reading back as
    +180 rather than folding to -180, or the fit sees a -180 feature at +180 and
    the longitude scale collapses. So the round-trip invariant is *latitude exact
    everywhere, longitude exact modulo width*.
    """
    k = _scale(width, height)
    lon = np.degrees((np.asarray(x, dtype=np.float64) - X0 * k) / (R_CANVAS * k))
    lat = _miller_lat((Y0 * k - np.asarray(y, dtype=np.float64)) / (R_CANVAS * k))
    return (lon, lat)


# ---------------------------------------------------------------------------
# Terraqueous NE-II oval reference (SOURCE px of terraqueous_globe.jpg, 4000x3256)
# ---------------------------------------------------------------------------
#
# Source-space and therefore **frame-independent**: the oval's extent in the
# scan does not change when the canvas reprojection does.
#
# The main oval's extent. **Measured in S2** (2026-07-23), superseding S1's
# eyeballed seed: the oval's drawn boundary curve was traced across 2001 rows and
# the Natural Earth II envelope least-squares fitted to it, giving
#
#     centre (1999.55, 1129.29)   scale sx=702.212  sy=702.683
#     inlier RMS 0.363 px, 100% of traced rows within 10 px
#
# Two independent confirmations fall out of that fit: sx/sy = 0.99933 (the oval is
# drawn to true, isotropic NE-II proportions), and the fitted graticule reproduces
# the map's own printed degree labels to ~2 px. Deriving the numbers from the
# projection rather than from feature guesses is what makes the reprojection
# reproducible; ``worldgen/reproject.py`` re-fits them from the committed control
# points in ``mapgen/registration/terraqueous_globe.json`` on every run.

TERRAQUEOUS_OVAL = {"left": 131, "right": 3869, "top": 129, "bottom": 2130}

# ---------------------------------------------------------------------------
# Feature canvas anchors
# ---------------------------------------------------------------------------
#
# Canvas px for recognizable Known World features. Every registration record pins
# its control points to these SAME positions, so the mosaic stays internally
# consistent regardless of per-feature error.
#
# **Refined in S2 (2026-07-23)**, then **migrated to Miller (2026-08-04)**. S1
# seeded these by treating the Terraqueous oval as if it were equirectangular in
# its central band; S2 replaced that by pushing each feature's source pick back
# through the true NE-II fit (source px -> lon/lat -> canvas px). The Miller
# migration is the same idea applied to the canvas side and is exact rather than
# a re-authoring: canvas px -> lon/lat under the old plate carree -> canvas px
# under Miller, emitted by ``mapgen/migrate_frame_coords.py``. Re-picking any of
# them by hand would only have added error.
#
# The reframe moves every anchor down (Miller compresses the tropics relative to
# a square graticule) by 100 px at the equator rising to ~340 px at high
# latitude, and by a uniform +2 px in x from the X0 change.
#
# Still approximate: the underlying source picks are hand-placed to maybe +-30
# source px (~55 canvas px). These anchor *regional map placement*, not the
# coastline — the coastline comes from the sub-pixel-registered projection.

ANCHORS: dict[str, tuple[int, int]] = {
    "naggaroth":          (1828, 792),
    "ulthuan_ring":       (2791, 1414),
    "lustria":            (2237, 2450),
    "norsca":             (4127, 470),
    "old_world_empire":   (4226, 819),
    "estalia":            (3783, 1147),
    "araby":              (3656, 1678),
    "land_of_the_dead":   (4210, 1811),
    "southland":          (4343, 2352),
    "dark_lands":         (4968, 919),
    "dragon_isles":       (5234, 1720),
    "ogre_kingdoms":      (5868, 796),
    "grand_cathay":       (6532, 919),
    "kingdoms_of_ind":    (6178, 1720),
    "kingdoms_of_kuresh": (6465, 2059),
    "nippon":             (7529, 1151),
}
