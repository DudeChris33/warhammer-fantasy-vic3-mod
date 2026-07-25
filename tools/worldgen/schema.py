"""Geometry-data schema — the reproducibility contract between phases.

The whole world is hand-encoded (from published cartography, logged in
``tools/PROVENANCE.md``) as committed JSON under ``geometry/``; the generators
rasterize it. This module defines and **validates on load** every geometry file
the later phases consume, so a malformed hand-edit fails loudly at load time
rather than producing a subtly-wrong bitmap.

Geometry layout (real world and the ``tools/fixtures/`` synthetic world share it)::

    <geometry_dir>/
        coastlines/<macro>.json     # landmass polygons  (the land/sea boundary)
        relief.json                 # sea level, ridges, falloff, noise params
        rivers.json                 # named river polylines
        states/<macro>.json         # state-cell partition (land + sea zones)

Coordinates are in ``provinces.png`` canvas space (P2/P3 share the same canvas).
A polygon whose x extends past the canvas width encodes a shape that wraps the
``x=0`` seam (see ``raster.rasterize_polygon``).

This module also defines the **upstream source-registration schema**
(:class:`SourceRegistration`) the source-driven ingestion stage consumes: how
each committed ``tools/registration/<source>.json`` places a reference image onto
the canvas — projection kind, hand-picked control points (source px <-> canvas
px), crop, target footprint, and compositing precedence. It is validated on load
exactly like the geometry schema above; the *dimensioned* cross-checks (control
points inside the source image, footprint inside the canvas, source present in
the SHA-256 manifest) live in ``worldgen/sources.py``, mirroring how
``validate_map`` — not this module — owns the engine-invariant checks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

Point = tuple[float, float]


class SchemaError(ValueError):
    """Raised when a geometry file violates the schema."""


# ---------------------------------------------------------------------------
# Low-level validators
# ---------------------------------------------------------------------------

def _require(mapping: dict, key: str, ctx: str):
    if not isinstance(mapping, dict):
        raise SchemaError(f"{ctx}: expected an object, got {type(mapping).__name__}")
    if key not in mapping:
        raise SchemaError(f"{ctx}: missing required field '{key}'")
    return mapping[key]


def _as_str(value, ctx: str) -> str:
    if not isinstance(value, str):
        raise SchemaError(f"{ctx}: expected a string, got {type(value).__name__}")
    return value


def _as_bool(value, ctx: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaError(f"{ctx}: expected a boolean, got {type(value).__name__}")
    return value


def _as_number(value, ctx: str) -> float:
    # bool is a subclass of int — reject it explicitly so `true` isn't read as 1.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{ctx}: expected a number, got {type(value).__name__}")
    return float(value)


def _as_int(value, ctx: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{ctx}: expected an integer, got {type(value).__name__}")
    return value


def _as_point(value, ctx: str) -> Point:
    if (not isinstance(value, (list, tuple))) or len(value) != 2:
        raise SchemaError(f"{ctx}: expected a [x, y] pair, got {value!r}")
    return (_as_number(value[0], f"{ctx}[0]"), _as_number(value[1], f"{ctx}[1]"))


def _as_polygon(value, ctx: str, min_points: int = 3) -> list[Point]:
    if not isinstance(value, (list, tuple)):
        raise SchemaError(f"{ctx}: expected a list of points, got {type(value).__name__}")
    pts = [_as_point(p, f"{ctx}[{i}]") for i, p in enumerate(value)]
    if len(pts) < min_points:
        raise SchemaError(f"{ctx}: expected at least {min_points} points, got {len(pts)}")
    return pts


def _as_bbox(value, ctx: str) -> tuple[float, float, float, float]:
    """An axis-aligned pixel box ``[x0, y0, x1, y1]`` with a non-negative origin
    and ``x0 < x1``, ``y0 < y1``. Used by the source-registration schema for
    crops (source px) and footprints (canvas px)."""
    if (not isinstance(value, (list, tuple))) or len(value) != 4:
        raise SchemaError(f"{ctx}: expected [x0, y0, x1, y1], got {value!r}")
    x0, y0, x1, y1 = (_as_number(value[i], f"{ctx}[{i}]") for i in range(4))
    if x0 < 0 or y0 < 0:
        raise SchemaError(f"{ctx}: box origin must be non-negative, got ({x0}, {y0})")
    if x1 <= x0 or y1 <= y0:
        raise SchemaError(f"{ctx}: expected x0<x1 and y0<y1, got ({x0}, {y0}, {x1}, {y1})")
    return (x0, y0, x1, y1)


# ---------------------------------------------------------------------------
# Coastlines
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Landmass:
    """One landmass polygon. ``holes`` are inland seas cut out of it."""

    name: str
    outer: list[Point]
    holes: list[list[Point]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "Landmass":
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        outer = _as_polygon(_require(d, "outer", ctx), f"{ctx}.outer")
        holes_raw = d.get("holes", [])
        if not isinstance(holes_raw, list):
            raise SchemaError(f"{ctx}.holes: expected a list, got {type(holes_raw).__name__}")
        holes = [_as_polygon(h, f"{ctx}.holes[{i}]") for i, h in enumerate(holes_raw)]
        return cls(name=name, outer=outer, holes=holes)


def load_coastline_file(path: Path) -> list[Landmass]:
    ctx = path.name
    data = _load_json(path)
    landmasses_raw = _require(data, "landmasses", ctx)
    if not isinstance(landmasses_raw, list) or not landmasses_raw:
        raise SchemaError(f"{ctx}.landmasses: expected a non-empty list")
    return [Landmass.from_dict(m, f"{ctx}.landmasses[{i}]") for i, m in enumerate(landmasses_raw)]


# ---------------------------------------------------------------------------
# Relief
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ridge:
    name: str
    polyline: list[Point]
    height: float

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "Ridge":
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        polyline = _as_polygon(_require(d, "polyline", ctx), f"{ctx}.polyline", min_points=2)
        height = _as_number(_require(d, "height", ctx), f"{ctx}.height")
        return cls(name=name, polyline=polyline, height=height)


@dataclass(frozen=True)
class Relief:
    sea_level: float
    coastal_falloff: float
    noise: dict
    ridges: list[Ridge]

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "Relief":
        sea_level = _as_number(_require(d, "sea_level", ctx), f"{ctx}.sea_level")
        coastal_falloff = _as_number(_require(d, "coastal_falloff", ctx), f"{ctx}.coastal_falloff")
        noise = _require(d, "noise", ctx)
        if not isinstance(noise, dict):
            raise SchemaError(f"{ctx}.noise: expected an object, got {type(noise).__name__}")
        ridges_raw = d.get("ridges", [])
        if not isinstance(ridges_raw, list):
            raise SchemaError(f"{ctx}.ridges: expected a list, got {type(ridges_raw).__name__}")
        ridges = [Ridge.from_dict(r, f"{ctx}.ridges[{i}]") for i, r in enumerate(ridges_raw)]
        return cls(sea_level=sea_level, coastal_falloff=coastal_falloff, noise=noise, ridges=ridges)


def load_relief(path: Path) -> Relief:
    return Relief.from_dict(_load_json(path), path.name)


# ---------------------------------------------------------------------------
# Rivers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class River:
    name: str
    polyline: list[Point]

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "River":
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        polyline = _as_polygon(_require(d, "polyline", ctx), f"{ctx}.polyline", min_points=2)
        return cls(name=name, polyline=polyline)


def load_rivers(path: Path) -> list[River]:
    ctx = path.name
    data = _load_json(path)
    rivers_raw = _require(data, "rivers", ctx)
    if not isinstance(rivers_raw, list):
        raise SchemaError(f"{ctx}.rivers: expected a list, got {type(rivers_raw).__name__}")
    return [River.from_dict(r, f"{ctx}.rivers[{i}]") for i, r in enumerate(rivers_raw)]


# ---------------------------------------------------------------------------
# River streams (the committed geometry generate_rivers.py rasterizes)
# ---------------------------------------------------------------------------
#
# ``River`` above is the P1 name+polyline stub. A Vic3 ``rivers.png`` needs more
# than a polyline: every stream has a *source* end and a *mouth* end, the mouth is
# either the open sea or a confluence into another stream, and the rendered width
# is an index into vanilla's blue ramp. ``RiverStream`` carries exactly that, and
# nothing the engine does not consume — the flow topology the generator must get
# right to produce a valid bitmap.

#: Vanilla's rivers.png blue width ramp (measured from game/map_data/rivers.png).
#: A stream's ``width`` names its *widest* (downstream) index; the generator ramps
#: up to it from the narrowest so a river visibly grows toward its mouth, exactly
#: as vanilla's rivers do (source 3 -> 4 -> 6 -> 8).
RIVER_WIDTH_RAMP = (3, 4, 6, 8)
RIVER_MOUTHS = ("sea", "confluence")


@dataclass(frozen=True)
class RiverStream:
    """One river or tributary: an ordered polyline from source to mouth.

    ``points`` run **source-first**: ``points[0]`` becomes the green spring pixel,
    ``points[-1]`` the mouth. ``mouth`` is ``"sea"`` (the last pixel must reach
    open water) or ``"confluence"`` (it must land on another stream, and is marked
    red so the engine reads the flows as joined). ``width`` is the downstream
    width index, one of :data:`RIVER_WIDTH_RAMP`.
    """

    name: str
    points: list[Point]
    mouth: str
    width: int

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None) -> "RiverStream":
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        ctx = f"{ctx}({name})"
        points = _as_polygon(_require(d, "points", ctx), f"{ctx}.points", min_points=2)
        mouth = _as_str(_require(d, "mouth", ctx), f"{ctx}.mouth")
        if mouth not in RIVER_MOUTHS:
            raise SchemaError(f"{ctx}.mouth: expected one of {RIVER_MOUTHS}, got '{mouth}'")
        width = _as_int(_require(d, "width", ctx), f"{ctx}.width")
        if width not in RIVER_WIDTH_RAMP:
            raise SchemaError(f"{ctx}.width: expected one of {RIVER_WIDTH_RAMP}, got {width}")

        # Bounds-check against the canvas when it is known. Without this a
        # mistyped vertex is silently dropped by the rasterizer's clip, leaving a
        # river that teleports across the gap — which passes every downstream
        # check because none of them assert contiguity. Fail loudly at load
        # instead, matching how ControlPoint rejects impossible coordinates.
        if canvas is not None:
            cw, ch = canvas
            for i, (px, py) in enumerate(points):
                if not (0 <= px <= cw and 0 <= py <= ch):
                    raise SchemaError(
                        f"{ctx}.points[{i}]: ({px}, {py}) is outside the canvas {cw}x{ch}"
                    )
        return cls(name=name, points=points, mouth=mouth, width=width)


def load_river_streams(path: Path, canvas: tuple[int, int] | None = None) -> list[RiverStream]:
    ctx = path.name
    data = _load_json(path)
    streams_raw = _require(data, "streams", ctx)
    if not isinstance(streams_raw, list) or not streams_raw:
        raise SchemaError(f"{ctx}.streams: expected a non-empty list")
    streams = [RiverStream.from_dict(s, f"{ctx}.streams[{i}]", canvas)
               for i, s in enumerate(streams_raw)]
    names = [s.name for s in streams]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise SchemaError(f"{ctx}: duplicate stream names {sorted(dupes)}")
    return streams


# ---------------------------------------------------------------------------
# States (the state-cell partition — land states and single-province sea zones)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Economics:
    """Placeholder economics. Values only need to parse; the real economy pass
    is a later request. Validated as present-and-parse-valid, not balanced."""

    subsistence_building: str
    arable_land: int
    arable_resources: list[str]
    capped_resources: dict[str, int]

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "Economics":
        subsistence = _as_str(_require(d, "subsistence_building", ctx), f"{ctx}.subsistence_building")
        arable_land = _as_int(_require(d, "arable_land", ctx), f"{ctx}.arable_land")
        if arable_land < 0:
            raise SchemaError(f"{ctx}.arable_land: must be >= 0")
        ar_raw = _require(d, "arable_resources", ctx)
        if not isinstance(ar_raw, list):
            raise SchemaError(f"{ctx}.arable_resources: expected a list")
        arable_resources = [_as_str(x, f"{ctx}.arable_resources[{i}]") for i, x in enumerate(ar_raw)]
        cap_raw = _require(d, "capped_resources", ctx)
        if not isinstance(cap_raw, dict):
            raise SchemaError(f"{ctx}.capped_resources: expected an object")
        capped: dict[str, int] = {}
        for k, v in cap_raw.items():
            n = _as_int(v, f"{ctx}.capped_resources.{k}")
            if n < 0:
                raise SchemaError(f"{ctx}.capped_resources.{k}: must be >= 0")
            capped[k] = n
        return cls(subsistence, arable_land, arable_resources, capped)


@dataclass(frozen=True)
class StateGeometry:
    """A state cell is defined either by an explicit ``polygon`` (with optional
    inland-sea ``holes``) or by a ``seeds`` set — ocean pixels are assigned to
    the nearest sea-zone seed, land pixels to the polygon that contains them."""

    kind: str  # "polygon" | "seeds"
    polygon: list[Point] | None
    holes: list[list[Point]]
    seeds: list[Point] | None

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "StateGeometry":
        gtype = _as_str(_require(d, "type", ctx), f"{ctx}.type")
        if gtype == "polygon":
            polygon = _as_polygon(_require(d, "polygon", ctx), f"{ctx}.polygon")
            holes_raw = d.get("holes", [])
            if not isinstance(holes_raw, list):
                raise SchemaError(f"{ctx}.holes: expected a list")
            holes = [_as_polygon(h, f"{ctx}.holes[{i}]") for i, h in enumerate(holes_raw)]
            return cls(kind="polygon", polygon=polygon, holes=holes, seeds=None)
        if gtype == "seeds":
            seeds_raw = _require(d, "seeds", ctx)
            if not isinstance(seeds_raw, list) or not seeds_raw:
                raise SchemaError(f"{ctx}.seeds: expected a non-empty list of points")
            seeds = [_as_point(p, f"{ctx}.seeds[{i}]") for i, p in enumerate(seeds_raw)]
            return cls(kind="seeds", polygon=None, holes=[], seeds=seeds)
        raise SchemaError(f"{ctx}.type: expected 'polygon' or 'seeds', got '{gtype}'")


@dataclass(frozen=True)
class State:
    key: str
    kind: str  # "land" | "sea"
    macro: str
    geometry: StateGeometry
    coastal: bool
    naval_exit: str | None
    economics: Economics | None
    impassable: list[Point] | None  # polygon marking an impassable sub-region

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "State":
        key = _as_str(_require(d, "key", ctx), f"{ctx}.key")
        if not key.startswith("STATE_"):
            raise SchemaError(f"{ctx}.key: must start with 'STATE_', got '{key}'")
        ctx = f"{ctx}({key})"
        kind = _as_str(_require(d, "kind", ctx), f"{ctx}.kind")
        if kind not in ("land", "sea"):
            raise SchemaError(f"{ctx}.kind: expected 'land' or 'sea', got '{kind}'")
        macro = _as_str(_require(d, "macro", ctx), f"{ctx}.macro")
        geometry = StateGeometry.from_dict(_require(d, "geometry", ctx), f"{ctx}.geometry")
        coastal = _as_bool(_require(d, "coastal", ctx), f"{ctx}.coastal")

        naval_exit = d.get("naval_exit")
        if naval_exit is not None:
            naval_exit = _as_str(naval_exit, f"{ctx}.naval_exit")
            if not naval_exit.startswith("STATE_"):
                raise SchemaError(f"{ctx}.naval_exit: must be a STATE_ key, got '{naval_exit}'")

        econ_raw = d.get("economics")
        economics = Economics.from_dict(econ_raw, f"{ctx}.economics") if econ_raw is not None else None

        impassable_raw = d.get("impassable")
        impassable = (
            _as_polygon(impassable_raw, f"{ctx}.impassable") if impassable_raw is not None else None
        )

        # Cross-field rules mirrored by validate_map.py's engine-invariant checks.
        if kind == "land":
            if economics is None:
                raise SchemaError(f"{ctx}: land state requires an 'economics' block")
            if coastal and naval_exit is None:
                raise SchemaError(f"{ctx}: coastal land state requires 'naval_exit'")
            if not coastal and naval_exit is not None:
                raise SchemaError(f"{ctx}: landlocked land state must not set 'naval_exit'")
        else:  # sea
            if naval_exit is not None:
                raise SchemaError(f"{ctx}: sea zone must not set 'naval_exit'")
            if coastal:
                raise SchemaError(f"{ctx}: sea zone must not be marked 'coastal'")

        return cls(key, kind, macro, geometry, coastal, naval_exit, economics, impassable)


def load_state_file(path: Path) -> list[State]:
    ctx = path.name
    data = _load_json(path)
    states_raw = _require(data, "states", ctx)
    if not isinstance(states_raw, list) or not states_raw:
        raise SchemaError(f"{ctx}.states: expected a non-empty list")
    return [State.from_dict(s, f"{ctx}.states[{i}]") for i, s in enumerate(states_raw)]


# ---------------------------------------------------------------------------
# Whole-world bundle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class World:
    """Everything loaded from a geometry directory, validated and cross-checked."""

    coastlines: dict[str, list[Landmass]]  # keyed by coastline file stem, sorted
    relief: Relief | None
    rivers: list[River]
    states: list[State]  # sorted by key

    @property
    def land_states(self) -> list[State]:
        return [s for s in self.states if s.kind == "land"]

    @property
    def sea_states(self) -> list[State]:
        return [s for s in self.states if s.kind == "sea"]


def load_world(geometry_dir: str | Path) -> World:
    """Load + validate a whole geometry directory. Raises :class:`SchemaError`.

    Iterates directories in sorted order so the resulting :class:`World` is
    deterministic regardless of filesystem enumeration order.
    """
    root = Path(geometry_dir)
    if not root.is_dir():
        raise SchemaError(f"geometry directory not found: {root}")

    coastlines: dict[str, list[Landmass]] = {}
    coast_dir = root / "coastlines"
    if coast_dir.is_dir():
        for path in sorted(coast_dir.glob("*.json")):
            coastlines[path.stem] = load_coastline_file(path)

    relief_path = root / "relief.json"
    relief = load_relief(relief_path) if relief_path.is_file() else None

    rivers_path = root / "rivers.json"
    rivers = load_rivers(rivers_path) if rivers_path.is_file() else []

    states: list[State] = []
    states_dir = root / "states"
    if states_dir.is_dir():
        for path in sorted(states_dir.glob("*.json")):
            states.extend(load_state_file(path))

    _cross_check(states)
    states.sort(key=lambda s: s.key)
    return World(coastlines=coastlines, relief=relief, rivers=rivers, states=states)


def _cross_check(states: list[State]) -> None:
    """World-level invariants that a single file cannot see."""
    seen: dict[str, str] = {}
    sea_keys = {s.key for s in states if s.kind == "sea"}
    for s in states:
        if s.key in seen:
            raise SchemaError(f"duplicate state key '{s.key}'")
        seen[s.key] = s.macro
    for s in states:
        if s.naval_exit is not None and s.naval_exit not in sea_keys:
            raise SchemaError(
                f"{s.key}: naval_exit '{s.naval_exit}' is not a declared sea zone"
            )


# ---------------------------------------------------------------------------
# Source registration (the upstream ingestion schema)
# ---------------------------------------------------------------------------
#
# Stage-A ingestion (reproject -> segment -> composite) needs to know, per source
# image, how it lands on the provinces.png canvas. That mapping is committed as
# ``tools/registration/<source>.json`` and validated here on load, exactly like
# the downstream geometry schema above — a malformed hand-edit fails loudly at
# load time instead of silently mis-registering a source. ``sources.py`` adds the
# dimensioned cross-checks this structural pass deliberately omits (control points
# inside the source image, footprint inside the canvas, source in the manifest).

#: The projections the ingestion stage knows how to apply.
#:  * ``natural_earth_2``    — the Terraqueous oval; NE II forward polynomial.
#:  * ``equirectangular``    — already-rectangular sources (the satellite frame).
#:  * ``control_point_warp`` — regional maps warped by a control-point field.
PROJECTION_KINDS = ("natural_earth_2", "equirectangular", "control_point_warp")

#: Minimum control points per projection. A control-point warp needs at least an
#: affine's worth (3); the parametric projections need 2 to fit scale/placement.
_MIN_CONTROL_POINTS = {
    "natural_earth_2": 2,
    "equirectangular": 2,
    "control_point_warp": 3,
}


@dataclass(frozen=True)
class ControlPoint:
    """One source-pixel <-> canvas-pixel correspondence, hand-picked from a
    recognizable feature. ``note`` records which feature (a cape, a graticule
    crossing, an image corner) so the choice is auditable later."""

    source: Point
    canvas: Point
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "ControlPoint":
        source = _as_point(_require(d, "source", ctx), f"{ctx}.source")
        canvas = _as_point(_require(d, "canvas", ctx), f"{ctx}.canvas")
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        for label, (x, y) in (("source", source), ("canvas", canvas)):
            if x < 0 or y < 0:
                raise SchemaError(f"{ctx}.{label}: pixel coords must be non-negative, got ({x}, {y})")
        return cls(source=source, canvas=canvas, note=note)


@dataclass(frozen=True)
class SourceRegistration:
    """How one reference image registers onto the canvas.

    ``source`` is the image's filename (cross-checked against the SHA-256 manifest
    by ``sources.py``). ``crop`` (optional, source px) is the region kept — e.g.
    the Terraqueous oval minus its polar insets. ``footprint`` (canvas px) is the
    box this source contributes to; on an overlap the higher ``precedence`` wins.
    """

    source: str
    role: str
    projection: str
    control_points: list[ControlPoint]
    crop: tuple[float, float, float, float] | None
    footprint: tuple[float, float, float, float]
    precedence: int
    layer_precedence: dict[str, int] = field(default_factory=dict)

    def precedence_for(self, layer: str) -> int:
        """Precedence for one *kind* of contribution, falling back to the record's
        overall ``precedence``.

        A source can be authoritative for one thing and useless for another. The
        Total War relief is the sharpest elevation detail we have, but it is a
        near-top-down 3-D render registered through five hand-picked points, so
        it must never be allowed to move a shoreline that the Terraqueous globe
        pins to sub-pixel accuracy. One number per source cannot express that;
        ``layer_precedence`` can.
        """
        return self.layer_precedence.get(layer, self.precedence)

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "SourceRegistration":
        source = _as_str(_require(d, "source", ctx), f"{ctx}.source")
        ctx = f"{ctx}({source})"
        role = _as_str(_require(d, "role", ctx), f"{ctx}.role")
        projection = _as_str(_require(d, "projection", ctx), f"{ctx}.projection")
        if projection not in PROJECTION_KINDS:
            raise SchemaError(
                f"{ctx}.projection: expected one of {PROJECTION_KINDS}, got '{projection}'"
            )

        cps_raw = _require(d, "control_points", ctx)
        if not isinstance(cps_raw, list):
            raise SchemaError(f"{ctx}.control_points: expected a list, got {type(cps_raw).__name__}")
        control_points = [
            ControlPoint.from_dict(c, f"{ctx}.control_points[{i}]") for i, c in enumerate(cps_raw)
        ]
        need = _MIN_CONTROL_POINTS[projection]
        if len(control_points) < need:
            raise SchemaError(
                f"{ctx}.control_points: {projection} needs at least {need}, got {len(control_points)}"
            )

        crop_raw = d.get("crop")
        crop = _as_bbox(crop_raw, f"{ctx}.crop") if crop_raw is not None else None
        footprint = _as_bbox(_require(d, "footprint", ctx), f"{ctx}.footprint")

        precedence = _as_int(_require(d, "precedence", ctx), f"{ctx}.precedence")
        if precedence < 0:
            raise SchemaError(f"{ctx}.precedence: must be >= 0, got {precedence}")

        lp_raw = d.get("layer_precedence", {})
        if not isinstance(lp_raw, dict):
            raise SchemaError(f"{ctx}.layer_precedence: expected an object, got {type(lp_raw).__name__}")
        layer_precedence: dict[str, int] = {}
        for k, v in lp_raw.items():
            if not isinstance(k, str) or not k:
                raise SchemaError(f"{ctx}.layer_precedence: layer names must be non-empty strings")
            n = _as_int(v, f"{ctx}.layer_precedence.{k}")
            if n < 0:
                raise SchemaError(f"{ctx}.layer_precedence.{k}: must be >= 0, got {n}")
            layer_precedence[k] = n

        # A control point's source pixel must fall inside the crop it is measured
        # against (when one is given) — a point outside the kept region is a
        # mis-pick that would warp garbage into the canvas.
        if crop is not None:
            for i, cp in enumerate(control_points):
                sx, sy = cp.source
                if not (crop[0] <= sx <= crop[2] and crop[1] <= sy <= crop[3]):
                    raise SchemaError(
                        f"{ctx}.control_points[{i}].source ({sx}, {sy}) lies outside crop {crop}"
                    )

        return cls(source, role, projection, control_points, crop, footprint,
                   precedence, layer_precedence)


def load_registration_file(path: Path) -> SourceRegistration:
    return SourceRegistration.from_dict(_load_json(path), path.name)


# ---------------------------------------------------------------------------
# Colour -> elevation LUT (the Terraqueous legend ramp, committed)
# ---------------------------------------------------------------------------
#
# The Terraqueous globe encodes elevation as a stepped colour ramp with a printed
# legend. Sampling that legend once and committing the result is what makes the
# heightmap reproducible from (local source + committed data): the LUT is our own
# measurement of the ramp, not a copy of the artwork.

@dataclass(frozen=True)
class ElevationBand:
    """One legend swatch: its sampled colour and the elevation range it means."""

    rgb: tuple[int, int, int]
    low_m: float
    high_m: float
    label: str

    @property
    def mid_m(self) -> float:
        return (self.low_m + self.high_m) / 2.0

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "ElevationBand":
        rgb_raw = _require(d, "rgb", ctx)
        if (not isinstance(rgb_raw, (list, tuple))) or len(rgb_raw) != 3:
            raise SchemaError(f"{ctx}.rgb: expected [r, g, b], got {rgb_raw!r}")
        rgb = tuple(_as_int(v, f"{ctx}.rgb[{i}]") for i, v in enumerate(rgb_raw))
        for i, v in enumerate(rgb):
            if not (0 <= v <= 255):
                raise SchemaError(f"{ctx}.rgb[{i}]: must be 0..255, got {v}")
        low = _as_number(_require(d, "low_m", ctx), f"{ctx}.low_m")
        high = _as_number(_require(d, "high_m", ctx), f"{ctx}.high_m")
        if high <= low:
            raise SchemaError(f"{ctx}: expected low_m < high_m, got {low} / {high}")
        return cls(rgb, low, high, _as_str(d.get("label", ""), f"{ctx}.label"))


@dataclass(frozen=True)
class ElevationLUT:
    """The sampled ramp. Bands run deepest-first; the first ``sea_band_count``
    are ocean and the rest are land, which is where the 0 m break sits.

    ``paper_rgb`` is the un-inked page colour. It matters because the Terraqueous
    oval deliberately leaves the polar Chaos Wastes blank, and blank paper is
    nearer the deepest-ocean swatch than to any land swatch — without an explicit
    paper entry the poles would classify as ocean.
    """

    source: str
    bands: list[ElevationBand]
    sea_band_count: int
    paper_rgb: tuple[int, int, int]
    paper_elevation_m: float

    @property
    def land_bands(self) -> list[ElevationBand]:
        return self.bands[self.sea_band_count:]


def load_elevation_lut(path: Path) -> ElevationLUT:
    ctx = path.name
    d = _load_json(path)
    source = _as_str(_require(d, "source", ctx), f"{ctx}.source")
    bands_raw = _require(d, "bands", ctx)
    if not isinstance(bands_raw, list) or len(bands_raw) < 2:
        raise SchemaError(f"{ctx}.bands: expected a list of at least 2 bands")
    bands = [ElevationBand.from_dict(b, f"{ctx}.bands[{i}]") for i, b in enumerate(bands_raw)]
    for i in range(1, len(bands)):
        if bands[i].low_m < bands[i - 1].low_m:
            raise SchemaError(f"{ctx}.bands[{i}]: bands must be ordered deepest-first")

    sea_n = _as_int(_require(d, "sea_band_count", ctx), f"{ctx}.sea_band_count")
    if not (0 < sea_n < len(bands)):
        raise SchemaError(f"{ctx}.sea_band_count: must be between 1 and {len(bands) - 1}, got {sea_n}")
    # The land/sea split has to land exactly on the ramp's own 0 m break.
    if bands[sea_n - 1].high_m != 0 or bands[sea_n].low_m != 0:
        raise SchemaError(
            f"{ctx}: sea_band_count={sea_n} does not fall on the 0 m break "
            f"(band {sea_n - 1} ends at {bands[sea_n - 1].high_m}, band {sea_n} starts at {bands[sea_n].low_m})"
        )

    paper_raw = _require(d, "paper_rgb", ctx)
    if (not isinstance(paper_raw, (list, tuple))) or len(paper_raw) != 3:
        raise SchemaError(f"{ctx}.paper_rgb: expected [r, g, b], got {paper_raw!r}")
    paper = tuple(_as_int(v, f"{ctx}.paper_rgb[{i}]") for i, v in enumerate(paper_raw))
    paper_m = _as_number(_require(d, "paper_elevation_m", ctx), f"{ctx}.paper_elevation_m")
    if paper_m <= 0:
        raise SchemaError(f"{ctx}.paper_elevation_m: blank page is polar land, so it must be > 0")

    return ElevationLUT(source, bands, sea_n, paper, paper_m)


def load_registrations(registration_dir: str | Path) -> list[SourceRegistration]:
    """Load + validate every ``tools/registration/*.json`` (sorted, deterministic).

    Raises :class:`SchemaError` on any malformed record or a duplicate source.
    """
    root = Path(registration_dir)
    if not root.is_dir():
        raise SchemaError(f"registration directory not found: {root}")
    regs: list[SourceRegistration] = []
    seen: set[str] = set()
    for path in sorted(root.glob("*.json")):
        reg = load_registration_file(path)
        if reg.source in seen:
            raise SchemaError(f"duplicate registration for source '{reg.source}'")
        seen.add(reg.source)
        regs.append(reg)
    return regs


def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise SchemaError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{path.name}: invalid JSON — {exc}") from exc
