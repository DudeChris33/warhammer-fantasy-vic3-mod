"""The geographic frame the source-driven ingestion stage registers onto.

``map_config`` fixes the canvas *dimensions*; this module fixes what those pixels
*mean* geographically, so every source (Terraqueous NE-II oval, the satellite
frame, the regional maps) can be placed on one shared coordinate system.

The canvas is a **plate-carrée (equirectangular) sheet**: longitude is linear in
x, latitude is linear in y, and the latitude span is chosen so degrees-per-pixel
is identical on both axes (square graticule cells) — the natural target for
reprojecting the Natural Earth II oval. ``wrap_x`` (see ``map_config``) makes
longitude periodic, so x = 0 and x = WIDTH are the same meridian.

    px/deg = WIDTH / 360 = 8192 / 360 = 22.7556
    lat span = HEIGHT / (px/deg) = 3616 / 22.7556 = 158.90625 deg  ->  +-79.453125

Nothing here is read by Victoria 3 — it is offline ingestion config, committed so
the placement of every source (and thus every derived bitmap) is reproducible
from the committed data plus the local ``sources/`` file.
"""

from __future__ import annotations

from config.map_config import PROVINCES_SIZE

WIDTH, HEIGHT = PROVINCES_SIZE  # (8192, 3616)

# ---------------------------------------------------------------------------
# Plate-carrée frame
# ---------------------------------------------------------------------------

LON_MIN, LON_MAX = -180.0, 180.0
#: Chosen so px/deg matches the longitude axis (a true plate carrée). The poles
#: themselves are off-canvas; the top/bottom bands are the Chaos Wastes fringe.
LAT_MAX = 79.453125
LAT_MIN = -79.453125

_PX_PER_DEG_LON = WIDTH / (LON_MAX - LON_MIN)
_PX_PER_DEG_LAT = HEIGHT / (LAT_MAX - LAT_MIN)


def lonlat_to_canvas(lon: float, lat: float) -> tuple[float, float]:
    """(lon, lat) in degrees -> (x, y) canvas px. x is folded into [0, WIDTH)."""
    x = (lon - LON_MIN) * _PX_PER_DEG_LON % WIDTH
    y = (LAT_MAX - lat) * _PX_PER_DEG_LAT
    return (x, max(0.0, min(float(HEIGHT), y)))


def canvas_to_lonlat(x: float, y: float) -> tuple[float, float]:
    """Inverse of :func:`lonlat_to_canvas` (x taken modulo the canvas width)."""
    lon = LON_MIN + (x % WIDTH) / _PX_PER_DEG_LON
    lat = LAT_MAX - y / _PX_PER_DEG_LAT
    return (lon, lat)


# ---------------------------------------------------------------------------
# Terraqueous NE-II oval reference (SOURCE px of terraqueous_globe.jpg, 4000x3256)
# ---------------------------------------------------------------------------
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
# points in ``tools/registration/terraqueous_globe.json`` on every run.

TERRAQUEOUS_OVAL = {"left": 131, "right": 3869, "top": 129, "bottom": 2130}

# ---------------------------------------------------------------------------
# Feature canvas anchors (approximate S1 seeds)
# ---------------------------------------------------------------------------
#
# Canvas px for recognizable Known World features. Every registration record pins
# its control points to these SAME positions, so the mosaic stays internally
# consistent regardless of per-feature error.
#
# **Refined in S2 (2026-07-23).** S1 seeded these by treating the Terraqueous oval
# as if it were equirectangular in its central band — an approximation that
# degrades badly toward the edges. With the real NE-II fit available, each feature
# the Terraqueous registration had a source pick for was pushed back through the
# true projection (source px -> lon/lat -> canvas px). The corrections were large:
# 106 px for the Old World, 283 px for Cathay, 317 px for Naggaroth — i.e. the
# equirectangular approximation was worth up to ~4 degrees of longitude out
# toward the limbs, exactly as expected. Features without their own Terraqueous
# pick were shifted by their nearest refined neighbour's correction, so the set
# moves as a whole rather than tearing.
#
# Still approximate: the underlying source picks are hand-placed to maybe +-30
# source px (~55 canvas px). These anchor *regional map placement*, not the
# coastline — the coastline comes from the sub-pixel-registered projection.

ANCHORS: dict[str, tuple[int, int]] = {
    "naggaroth":          (1826, 590),
    "ulthuan_ring":       (2789, 1103),
    "lustria":            (2235, 2114),
    "norsca":             (4125, 370),
    "old_world_empire":   (4224, 610),
    "estalia":            (3781, 870),
    "araby":              (3654, 1350),
    "land_of_the_dead":   (4208, 1479),
    "southland":          (4341, 2017),
    "dark_lands":         (4966, 686),
    "dragon_isles":       (5232, 1391),
    "ogre_kingdoms":      (5866, 593),
    "grand_cathay":       (6530, 686),
    "kingdoms_of_ind":    (6176, 1391),
    "kingdoms_of_kuresh": (6463, 1725),
    "nippon":             (7527, 873),
}
