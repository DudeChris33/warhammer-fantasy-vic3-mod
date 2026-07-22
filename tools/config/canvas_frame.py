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
# Terraqueous NE-II oval reference (SOURCE px of ljzbtm288r891.jpg, 4000x3256)
# ---------------------------------------------------------------------------
#
# The main oval's equatorial and pole-to-pole extents, read from the image and
# bounded by pixel analysis (its two polar insets begin at y=2148, so the oval
# bottom is above that). S2's Natural Earth II reprojection fits its projection
# constants against these + the Terraqueous control points; S1 only needs them to
# derive the approximate feature anchors below.

TERRAQUEOUS_OVAL = {"left": 150, "right": 3850, "top": 95, "bottom": 2045}

# ---------------------------------------------------------------------------
# Feature canvas anchors (approximate S1 seeds)
# ---------------------------------------------------------------------------
#
# Canvas px for recognizable Known World features, derived by treating the
# Terraqueous oval as if it were equirectangular in its central band (a good
# approximation near the equator/central meridian, degrading toward the
# edges/poles). Every registration record pins its control points to these SAME
# positions, so the mosaic is internally consistent regardless of per-feature
# error. **Approximate by design** — S2's real NE-II reprojection plus the visual
# overlay QA pass refine them; they are seeds, not survey coordinates.

ANCHORS: dict[str, tuple[int, int]] = {
    "naggaroth":          (2125, 695),
    "ulthuan_ring":       (2834, 1205),
    "lustria":            (2280, 2216),
    "norsca":             (4118, 491),
    "old_world_empire":   (4207, 714),
    "estalia":            (3764, 974),
    "araby":              (3653, 1456),
    "land_of_the_dead":   (4207, 1585),
    "southland":          (4340, 2123),
    "dark_lands":         (4871, 788),
    "dragon_isles":       (5137, 1493),
    "ogre_kingdoms":      (5602, 695),
    "grand_cathay":       (6266, 788),
    "kingdoms_of_ind":    (5912, 1493),
    "kingdoms_of_kuresh": (6199, 1827),
    "nippon":             (7284, 974),
}
