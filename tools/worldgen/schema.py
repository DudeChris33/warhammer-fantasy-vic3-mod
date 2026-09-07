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
# Canon river names (the anchor-keyed naming input generate_rivers.py reads, #3703)
# ---------------------------------------------------------------------------
#
# The river geometry is *traced* (a pure-cyan line network on the canvas), not
# authored as polylines, so names cannot ride on the stream objects the way
# ``RiverStream`` above carries them. Instead a small hand-authored file pins each
# canon river NAME to an ``anchor`` pixel on its drawn line — the same
# canvas-anchor idiom as ``land_region_merges.json`` / the hub worksheet — and the
# generator resolves each anchor to exactly one extracted stream. Naming is
# **opt-in**: the engine has no river names, so a stream needs a name only if a
# downstream item (#3677 economics, #3687 traits) references that specific river
# through ``rivers_index.json``. ``width`` / ``mouth`` are optional per-river
# overrides (``mouth`` must agree with the traced topology or it is rejected).

@dataclass(frozen=True)
class CanonRiverName:
    """One canon river: a display name pinned to an ``anchor`` pixel on its line.

    ``anchor`` is a single canvas ``[x, y]`` pixel (bounds-checked exactly like
    :class:`LandRegionMerge.anchor_a`). ``width`` optionally overrides the
    Strahler-derived render width (one of :data:`RIVER_WIDTH_RAMP`); ``mouth``
    optionally pins the mouth kind (one of :data:`RIVER_MOUTHS`) and must match
    the traced topology.
    """

    name: str
    anchor: tuple[int, int]
    width: int | None
    mouth: str | None
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None
                  ) -> "CanonRiverName":
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        if not name:
            raise SchemaError(f"{ctx}.name: must be a non-empty string")
        ctx = f"{ctx}({name})"
        (anchor,) = _as_seed_list([_require(d, "anchor", ctx)], f"{ctx}.anchor", canvas)
        width = d.get("width")
        if width is not None:
            width = _as_int(width, f"{ctx}.width")
            if width not in RIVER_WIDTH_RAMP:
                raise SchemaError(f"{ctx}.width: expected one of {RIVER_WIDTH_RAMP}, got {width}")
        mouth = d.get("mouth")
        if mouth is not None:
            mouth = _as_str(mouth, f"{ctx}.mouth")
            if mouth not in RIVER_MOUTHS:
                raise SchemaError(f"{ctx}.mouth: expected one of {RIVER_MOUTHS}, got '{mouth}'")
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        return cls(name=name, anchor=anchor, width=width, mouth=mouth, note=note)


def load_canon_river_names(path: Path, canvas: tuple[int, int] | None = None
                           ) -> list[CanonRiverName]:
    """Load + validate the committed canon-river names file (authored order kept).

    Bounds-checks every anchor against ``canvas`` when known, rejects a duplicate
    river name and a duplicate anchor pixel (two names on one pixel is a silent
    authoring bug, the rule the sea-zone / hub loaders use). Region-aware checks
    (an anchor resolving to exactly one stream) need the extracted network and are
    enforced by ``river_network.extract_streams``, not here.
    """
    ctx = path.name
    data = _load_json(path)
    rivers_raw = _require(data, "rivers", ctx)
    if not isinstance(rivers_raw, list) or not rivers_raw:
        raise SchemaError(f"{ctx}.rivers: expected a non-empty list")
    rivers = [CanonRiverName.from_dict(r, f"{ctx}.rivers[{i}]", canvas)
              for i, r in enumerate(rivers_raw)]
    names = [r.name for r in rivers]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise SchemaError(f"{ctx}: duplicate river names {sorted(dupes)}")
    seen: dict[tuple[int, int], str] = {}
    for r in rivers:
        if r.anchor in seen:
            raise SchemaError(
                f"{ctx}: anchor pixel {list(r.anchor)} is claimed by both "
                f"'{seen[r.anchor]}' and '{r.name}' — anchors must be unique"
            )
        seen[r.anchor] = r.name
    return rivers


# ---------------------------------------------------------------------------
# River source layers (the optional multi-layer trace declaration, #3703)
# ---------------------------------------------------------------------------
#
# By default the river generator reads a single canvas-native cyan trace
# (``sources/terraqueous_globe_reprojected - rivers.png``, 1:1 with the canvas,
# no registration). ``river_sources.json`` optionally declares several layers to
# union — each either ``canvas`` (already canvas-space, read as-is) or
# ``registered`` (cyan traced on an unwarped registered crop's own frame, warped
# onto the canvas through that crop's committed registration). The file is only
# needed when there is more than one trace, or a trace in a source frame.

@dataclass(frozen=True)
class RiverSourceLayer:
    """One river trace layer: a source ``file`` and how it lands on the canvas.

    ``mode`` is ``canvas`` (1:1, no warp) or ``registered`` (warped through
    ``registration``, the stem of a committed ``tools/registration/<name>.json``).
    """

    file: str
    mode: str
    registration: str | None

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "RiverSourceLayer":
        file = _as_str(_require(d, "file", ctx), f"{ctx}.file")
        if not file:
            raise SchemaError(f"{ctx}.file: must be a non-empty string")
        ctx = f"{ctx}({file})"
        mode = _as_str(_require(d, "mode", ctx), f"{ctx}.mode")
        if mode not in ("canvas", "registered"):
            raise SchemaError(f"{ctx}.mode: expected 'canvas' or 'registered', got '{mode}'")
        registration = d.get("registration")
        if mode == "registered":
            registration = _as_str(_require(d, "registration", ctx), f"{ctx}.registration")
            if not registration:
                raise SchemaError(f"{ctx}.registration: a registered layer needs a registration name")
        elif registration is not None:
            registration = _as_str(registration, f"{ctx}.registration")
        return cls(file=file, mode=mode, registration=registration)


def load_river_sources(path: Path) -> list[RiverSourceLayer]:
    """Load + validate the committed river-source-layer declaration (order kept —
    it is the union order; layers are OR-ed so order is cosmetic but preserved)."""
    ctx = path.name
    data = _load_json(path)
    layers_raw = _require(data, "layers", ctx)
    if not isinstance(layers_raw, list) or not layers_raw:
        raise SchemaError(f"{ctx}.layers: expected a non-empty list")
    return [RiverSourceLayer.from_dict(la, f"{ctx}.layers[{i}]") for i, la in enumerate(layers_raw)]


# ---------------------------------------------------------------------------
# Inland lakes (the enclosed-water keep-list the land/sea mask generator reads)
# ---------------------------------------------------------------------------
#
# The Terraqueous globe draws rivers in ocean-blue and floods some marshes to a
# shallow-ocean tone, so the classifier leaves hundreds of enclosed (non-ocean-
# connected) "lakes" the map does not mean. ``generate_heightmap.py`` fills every
# enclosed water body to land EXCEPT the genuine ones listed here — identified by
# a stable interior *seed pixel* rather than an area threshold (a size cut cannot
# separate the 14k-px false Marshes-of-Madness blob from a ~4k-px real lake) or a
# component index (labels are not stable across regenerations).

@dataclass(frozen=True)
class InlandLake:
    """One enclosed water body to keep as water.

    ``seed`` is a guaranteed-interior water pixel (canvas px, integer) naming the
    body's connected component. ``kind`` is ``lake`` (an impassable lake
    downstream in S3b) or ``sea`` (an ocean-connected navigable sea zone modelled
    like Ulthuan's Inner Sea). The binary land/sea mask keeps every listed body
    identically as water; ``kind`` only records the distinction the later
    default.map / states pass consumes.
    """

    name: str
    seed: tuple[int, int]
    kind: str
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None) -> "InlandLake":
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        if not name:
            raise SchemaError(f"{ctx}.name: must be a non-empty string")
        ctx = f"{ctx}({name})"
        seed_raw = _require(d, "seed", ctx)
        if (not isinstance(seed_raw, (list, tuple))) or len(seed_raw) != 2:
            raise SchemaError(f"{ctx}.seed: expected an [x, y] pixel pair, got {seed_raw!r}")
        sx = _as_int(seed_raw[0], f"{ctx}.seed[0]")
        sy = _as_int(seed_raw[1], f"{ctx}.seed[1]")
        if sx < 0 or sy < 0:
            raise SchemaError(f"{ctx}.seed: pixel coords must be non-negative, got ({sx}, {sy})")
        if canvas is not None:
            cw, ch = canvas
            if not (0 <= sx < cw and 0 <= sy < ch):
                raise SchemaError(f"{ctx}.seed: ({sx}, {sy}) is outside the canvas {cw}x{ch}")
        kind = _as_str(_require(d, "kind", ctx), f"{ctx}.kind")
        if kind not in ("lake", "sea"):
            raise SchemaError(f"{ctx}.kind: expected 'lake' or 'sea', got '{kind}'")
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        return cls(name=name, seed=(sx, sy), kind=kind, note=note)


def load_inland_lakes(path: Path, canvas: tuple[int, int] | None = None) -> list[InlandLake]:
    """Load + validate the committed inland-lake keep-list (sorted by name).

    Bounds-checks each seed against ``canvas`` when it is known, exactly like
    :class:`RiverStream`. Raises :class:`SchemaError` on any malformed body or a
    duplicate name.
    """
    ctx = path.name
    data = _load_json(path)
    bodies_raw = _require(data, "bodies", ctx)
    if not isinstance(bodies_raw, list) or not bodies_raw:
        raise SchemaError(f"{ctx}.bodies: expected a non-empty list")
    bodies = [InlandLake.from_dict(b, f"{ctx}.bodies[{i}]", canvas)
              for i, b in enumerate(bodies_raw)]
    names = [b.name for b in bodies]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise SchemaError(f"{ctx}: duplicate body names {sorted(dupes)}")
    bodies.sort(key=lambda b: b.name)
    return bodies


# ---------------------------------------------------------------------------
# Out-of-scope continents (the placeholder-cell seed list the label generator reads)
# ---------------------------------------------------------------------------
#
# The map is rescoped to the Old World (board item #2207). Land the user did not
# draw into ``sources/old_world_regions.png`` collapses to one impassable
# placeholder cell per major continent; this hand-authored list names those
# continents and seeds them. Like ``inland_lakes.json`` it is deliberate
# geographic input — a seed is a guaranteed-interior pixel of the out-of-scope
# component it claims — and, unlike a bitmap, is edited by hand and the generator
# regenerated through it, never inferred from a regenerated layer.
#
# ``generate_state_labels.py`` labels the connected components of
# ``land ∧ ¬in_scope``; each seed here CLAIMS the component it lands in, a
# component claimed by two or more seeds is split geodesically between them
# (Naggaroth/Lustria are one physical landmass), and small unclaimed components
# fold into the nearest placeholder. A seed on water or on in-scope land, or an
# unclaimed component above the audit floor, is a hard error — a forgotten
# continent must be a deliberate config edit, never silently an island.

@dataclass(frozen=True)
class OutOfScopeContinent:
    """One out-of-scope major landmass to collapse to a single placeholder cell.

    ``seed`` is a guaranteed-interior land pixel (canvas px, integer) of the
    out-of-scope component this entry claims — the same seed-pixel idiom as
    :class:`InlandLake`, and for the same reason (a component index is not stable
    across regenerations; an interior pixel is). ``name`` becomes the placeholder
    cell's ``STATE_OOS_<NAME_UPPER>`` key and its localized display name.
    """

    name: str
    seed: tuple[int, int]
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None
                  ) -> "OutOfScopeContinent":
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        if not name:
            raise SchemaError(f"{ctx}.name: must be a non-empty string")
        ctx = f"{ctx}({name})"
        seed_raw = _require(d, "seed", ctx)
        if (not isinstance(seed_raw, (list, tuple))) or len(seed_raw) != 2:
            raise SchemaError(f"{ctx}.seed: expected an [x, y] pixel pair, got {seed_raw!r}")
        sx = _as_int(seed_raw[0], f"{ctx}.seed[0]")
        sy = _as_int(seed_raw[1], f"{ctx}.seed[1]")
        if sx < 0 or sy < 0:
            raise SchemaError(f"{ctx}.seed: pixel coords must be non-negative, got ({sx}, {sy})")
        if canvas is not None:
            cw, ch = canvas
            if not (0 <= sx < cw and 0 <= sy < ch):
                raise SchemaError(f"{ctx}.seed: ({sx}, {sy}) is outside the canvas {cw}x{ch}")
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        return cls(name=name, seed=(sx, sy), note=note)


def load_out_of_scope_continents(path: Path, canvas: tuple[int, int] | None = None
                                 ) -> list[OutOfScopeContinent]:
    """Load + validate the committed out-of-scope continent seed list.

    Bounds-checks each seed against ``canvas`` when known and rejects a duplicate
    name, exactly like :func:`load_inland_lakes`. **Unlike** that loader this one
    preserves the file's authored order rather than sorting by name: the order is
    the placeholder cells' numbering and presentation order (config order → label
    ``n_in+1 .. n_in+M`` → the EDT tie-break's "lower placeholder index"), so it is
    a meaningful, author-controlled sequence, not an incidental one.
    """
    ctx = path.name
    data = _load_json(path)
    conts_raw = _require(data, "continents", ctx)
    if not isinstance(conts_raw, list) or not conts_raw:
        raise SchemaError(f"{ctx}.continents: expected a non-empty list")
    conts = [OutOfScopeContinent.from_dict(c, f"{ctx}.continents[{i}]", canvas)
             for i, c in enumerate(conts_raw)]
    names = [c.name for c in conts]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise SchemaError(f"{ctx}: duplicate continent names {sorted(dupes)}")
    return conts


# ---------------------------------------------------------------------------
# Land-region merge overrides (board #2930 follow-up: judgement-call merges)
# ---------------------------------------------------------------------------
#
# Some land regions the drawn magenta network keeps separate should still ship
# as one state regardless — a deliberate editorial call (2026-09-05: "unify
# regardless of lines"), not a flood-fill/merge-floor artifact like the
# tiny-island problem or the too-aggressive MERGE_FLOOR that #2930 already
# fixed. Unlike :class:`OutOfScopeContinent` or the tiny-island override (both
# painted), a merge pair is authored as two precise pixel **anchors** — in
# practice copied straight from the naming worksheet's own anchor_x/anchor_y
# columns, since those already pin an exact interior point of each region.

@dataclass(frozen=True)
class LandRegionMerge:
    """One judgement-call merge: the regions owning ``anchor_a`` and
    ``anchor_b`` are force-unioned regardless of any magenta line between
    them. Transitive chains (A merges into B, B into C) are fine — the
    consuming union-find does not care which pair record supplies which leg."""

    anchor_a: tuple[int, int]
    anchor_b: tuple[int, int]
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None
                  ) -> "LandRegionMerge":
        (a,) = _as_seed_list([_require(d, "anchor_a", ctx)], f"{ctx}.anchor_a", canvas)
        (b,) = _as_seed_list([_require(d, "anchor_b", ctx)], f"{ctx}.anchor_b", canvas)
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        return cls(anchor_a=a, anchor_b=b, note=note)


def load_land_region_merges(path: Path, canvas: tuple[int, int] | None = None
                            ) -> list[LandRegionMerge]:
    """Load + validate the committed land-region merge overrides (authored
    order preserved — it has no semantic meaning here, but matches the other
    loaders' convention of not reordering hand-authored input)."""
    ctx = path.name
    data = _load_json(path)
    merges_raw = _require(data, "merges", ctx)
    if not isinstance(merges_raw, list) or not merges_raw:
        raise SchemaError(f"{ctx}.merges: expected a non-empty list")
    return [LandRegionMerge.from_dict(m, f"{ctx}.merges[{i}]", canvas)
            for i, m in enumerate(merges_raw)]


# ---------------------------------------------------------------------------
# Hub worksheet (the settlement list the lore-hub tooling reads, board #3665)
# ---------------------------------------------------------------------------
#
# A hand-authored, regenerate-through JSON input (sibling of
# ``land_region_merges.json``) — one row per named hub. Each row pins a
# settlement to a canvas ``anchor`` pixel; ``generate_provinces.py`` resolves that
# anchor to a state region and seeds a distinct province there, and
# ``generate_land_regions.py`` picks that province as the state's ``hub`` and emits
# its ``HUB_NAME_*`` loc. The anchor pixel IS the row's identity (objection 3): no
# ``STATE_`` key is stored, because the Hilbert STATE number churns on any region
# change and a name collision falls back to a bare number — both unstable. ``state``
# is a human label surfaced in logs only, never parsed into a key.

#: The five hub slots every state has, matching vanilla's hub kinds.
_HUB_TYPES = ("city", "port", "farm", "mine", "wood")


@dataclass(frozen=True)
class HubRow:
    """One named hub: a settlement pinned to a canvas ``anchor`` pixel.

    ``state`` is a free-text human label (logs only). ``hub`` is one of
    :data:`_HUB_TYPES`. ``name`` is the display text. ``source`` is a canon
    citation or the literal ``invented``. ``anchor`` is a single canvas ``[x, y]``
    pixel, bounds-checked exactly like :class:`LandRegionMerge.anchor_a`.
    """

    state: str
    hub: str
    name: str
    anchor: tuple[int, int]
    source: str
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None) -> "HubRow":
        state = _as_str(_require(d, "state", ctx), f"{ctx}.state")
        if not state:
            raise SchemaError(f"{ctx}.state: must be a non-empty string")
        ctx = f"{ctx}({state})"
        hub = _as_str(_require(d, "hub", ctx), f"{ctx}.hub")
        if hub not in _HUB_TYPES:
            raise SchemaError(f"{ctx}.hub: must be one of {list(_HUB_TYPES)}, got '{hub}'")
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        if not name:
            raise SchemaError(f"{ctx}.name: must be a non-empty string")
        (anchor,) = _as_seed_list([_require(d, "anchor", ctx)], f"{ctx}.anchor", canvas)
        source = _as_str(_require(d, "source", ctx), f"{ctx}.source")
        if not source:
            raise SchemaError(f"{ctx}.source: must be a non-empty string (canon citation or 'invented')")
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        return cls(state=state, hub=hub, name=name, anchor=anchor, source=source, note=note)


def load_hub_worksheet(path: Path, canvas: tuple[int, int] | None = None) -> list[HubRow]:
    """Load + validate the committed hub worksheet (authored order preserved).

    Bounds-checks every anchor against ``canvas`` when known, and rejects a
    **duplicate exact anchor pixel** across rows — two hubs on one pixel is
    last-writer-wins in the seed raster, a silent authoring bug (the same rule
    :func:`load_sea_zones` uses for its seed pixels). Region-aware checks (an anchor
    resolving to no region, two anchors of the same state too close together) need
    the canvas region layer and are enforced by ``generate_provinces.py``, not here.
    """
    ctx = path.name
    data = _load_json(path)
    hubs_raw = _require(data, "hubs", ctx)
    if not isinstance(hubs_raw, list) or not hubs_raw:
        raise SchemaError(f"{ctx}.hubs: expected a non-empty list")
    rows = [HubRow.from_dict(h, f"{ctx}.hubs[{i}]", canvas) for i, h in enumerate(hubs_raw)]

    seen: dict[tuple[int, int], str] = {}
    for r in rows:
        if r.anchor in seen:
            raise SchemaError(
                f"{ctx}: anchor pixel {list(r.anchor)} is claimed by both "
                f"'{seen[r.anchor]}' and '{r.name}' — anchors must be unique"
            )
        seen[r.anchor] = r.name
    return rows


# ---------------------------------------------------------------------------
# Canon sea groups (the sea-zone naming config generate_sea_zones.py reads)
# ---------------------------------------------------------------------------
#
# The 154 hand-drawn sea zones (board #2593) are numbered placeholders. Board
# #2698 gives each a Warhammer-canon sea group — the Sea of Claws, the Great
# Ocean, the Black Gulf, ... — printed on the Terraqueous globe itself. Like
# ``inland_lakes.json`` / ``out_of_scope_continents.json`` this is hand-authored
# geographic input: each canon sea is named and located by a set of
# guaranteed-interior water **seed pixels** (a label id is opaque and only stable
# while the partition is), and ``sea_naming.assign`` gives every zone the canon
# sea owning the plurality of its pixels in a wrap-aware seed-Voronoi. An
# ``override`` reassigns a single mis-assigned zone to a different canon sea,
# keyed on an interior pixel of the zone — never a label id, for the same reason.
#
# The order of ``canon_seas`` is the deterministic canon-index tie-break (a
# plurality tie goes to the lower canon index), so — like
# ``load_out_of_scope_continents`` — this loader PRESERVES the authored order and
# does NOT sort. Seeds must be unique across all seas (two seas seeding one pixel
# is last-writer-wins in the seed raster — a silent authoring bug), so that is a
# hard error here. Seed-on-water is checked by the generator, not here: the
# canvas water mask is not available at schema-load time.

@dataclass(frozen=True)
class CanonSea:
    """One canon sea group: a name, a display name, and its seed pixels.

    ``name`` is the ``STATE_``-suffix token (uppercase/underscore only, so
    ``STATE_<name>`` is a legal key); the per-zone key becomes
    ``STATE_<name>_NN``. ``display_name`` is the shared localized text every zone
    in the group carries. ``seeds`` are guaranteed-interior water pixels (canvas
    px, integer) that source the Voronoi assignment — at least one.
    """

    name: str
    display_name: str
    seeds: tuple[tuple[int, int], ...]
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None) -> "CanonSea":
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        if not name:
            raise SchemaError(f"{ctx}.name: must be a non-empty string")
        if not all(c.isupper() or c == "_" or c.isdigit() for c in name) or not name[0].isalpha():
            raise SchemaError(
                f"{ctx}.name: must be uppercase letters/digits/underscore and start with a "
                f"letter (so STATE_{name} is a legal key), got '{name}'"
            )
        ctx = f"{ctx}({name})"
        display_name = _as_str(_require(d, "display_name", ctx), f"{ctx}.display_name")
        if not display_name:
            raise SchemaError(f"{ctx}.display_name: must be a non-empty string")
        seeds = _as_seed_list(_require(d, "seeds", ctx), f"{ctx}.seeds", canvas)
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        return cls(name=name, display_name=display_name, seeds=seeds, note=note)


@dataclass(frozen=True)
class SeaZoneOverride:
    """Reassign one mis-assigned zone to a different canon sea.

    ``zone_seed`` is a guaranteed-interior pixel of the zone to reassign (never a
    label id); ``canon_sea`` is the ``name`` of a declared :class:`CanonSea`.
    """

    zone_seed: tuple[int, int]
    canon_sea: str
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None
                  ) -> "SeaZoneOverride":
        (seed,) = _as_seed_list([_require(d, "zone_seed", ctx)], f"{ctx}.zone_seed", canvas)
        canon_sea = _as_str(_require(d, "canon_sea", ctx), f"{ctx}.canon_sea")
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        return cls(zone_seed=seed, canon_sea=canon_sea, note=note)


@dataclass(frozen=True)
class SeaZoneMerge:
    """Fuse several drawn zones into one named province, bypassing canon-sea
    Voronoi naming entirely (its own ``name``/``display_name``, not a group NN).

    ``seeds`` are guaranteed-interior pixels of the zones to fuse — at least two,
    since a "merge" of one zone is just an override. ``impassable`` marks the
    resulting single province unsailable (2026-08-31 exception to the
    2026-08-22 "no impassable sea province" decision: a supernatural whirlpool,
    not open ocean real-world ships would cross).
    """

    name: str
    display_name: str
    seeds: tuple[tuple[int, int], ...]
    impassable: bool
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None
                  ) -> "SeaZoneMerge":
        name = _as_str(_require(d, "name", ctx), f"{ctx}.name")
        if not name:
            raise SchemaError(f"{ctx}.name: must be a non-empty string")
        if not all(c.isupper() or c == "_" or c.isdigit() for c in name) or not name[0].isalpha():
            raise SchemaError(
                f"{ctx}.name: must be uppercase letters/digits/underscore and start with a "
                f"letter (so STATE_{name} is a legal key), got '{name}'"
            )
        ctx = f"{ctx}({name})"
        display_name = _as_str(_require(d, "display_name", ctx), f"{ctx}.display_name")
        if not display_name:
            raise SchemaError(f"{ctx}.display_name: must be a non-empty string")
        seeds = _as_seed_list(_require(d, "seeds", ctx), f"{ctx}.seeds", canvas)
        if len(seeds) < 2:
            raise SchemaError(f"{ctx}.seeds: a merge needs at least 2 zones, got {len(seeds)}")
        impassable = bool(d.get("impassable", False))
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        return cls(name=name, display_name=display_name, seeds=seeds,
                    impassable=impassable, note=note)


@dataclass(frozen=True)
class SeaZoneDisplayName:
    """Give one individual zone its own display name, leaving its sea_group
    untouched (only the loc text and, downstream via
    ``sea_naming.rekey_by_display_name``, the zone's own key change — the group
    it was Voronoi-assigned to is still recorded for reference).

    From the per-zone naming worksheet (``tools/config/sea_zone_naming_worksheet.txt``,
    board #2698 follow-up): each hand-drawn zone gets a real place name (e.g. "Shard
    Coast") rather than sharing its whole canon sea's generic display name. ``seed``
    is a guaranteed-interior pixel of the zone (never a label id, for the same
    reason as :class:`SeaZoneOverride`) — it may equal an ``impassable_seeds`` entry
    for the same zone; naming and passability are independent.
    """

    seed: tuple[int, int]
    display_name: str
    note: str

    @classmethod
    def from_dict(cls, d: dict, ctx: str, canvas: tuple[int, int] | None = None
                  ) -> "SeaZoneDisplayName":
        (seed,) = _as_seed_list([_require(d, "seed", ctx)], f"{ctx}.seed", canvas)
        display_name = _as_str(_require(d, "display_name", ctx), f"{ctx}.display_name")
        if not display_name:
            raise SchemaError(f"{ctx}.display_name: must be a non-empty string")
        note = _as_str(d.get("note", ""), f"{ctx}.note")
        return cls(seed=seed, display_name=display_name, note=note)


@dataclass(frozen=True)
class SeaZoneConfig:
    """The whole ``tools/config/sea_zones.json`` — canon seas + overrides."""

    canon_seas: tuple[CanonSea, ...]
    overrides: tuple[SeaZoneOverride, ...]
    merges: tuple[SeaZoneMerge, ...] = ()
    impassable_seeds: tuple[tuple[int, int], ...] = ()
    zone_names: tuple[SeaZoneDisplayName, ...] = ()


def _as_seed_list(value, ctx: str, canvas: tuple[int, int] | None = None
                  ) -> tuple[tuple[int, int], ...]:
    """A non-empty list of integer ``[x, y]`` pixel pairs, bounds-checked against
    ``canvas`` when it is known — the same seed-pixel idiom as :class:`InlandLake`."""
    if not isinstance(value, list) or not value:
        raise SchemaError(f"{ctx}: expected a non-empty list of [x, y] pixel pairs")
    out: list[tuple[int, int]] = []
    for i, seed_raw in enumerate(value):
        if (not isinstance(seed_raw, (list, tuple))) or len(seed_raw) != 2:
            raise SchemaError(f"{ctx}[{i}]: expected an [x, y] pixel pair, got {seed_raw!r}")
        sx = _as_int(seed_raw[0], f"{ctx}[{i}][0]")
        sy = _as_int(seed_raw[1], f"{ctx}[{i}][1]")
        if sx < 0 or sy < 0:
            raise SchemaError(f"{ctx}[{i}]: pixel coords must be non-negative, got ({sx}, {sy})")
        if canvas is not None:
            cw, ch = canvas
            if not (0 <= sx < cw and 0 <= sy < ch):
                raise SchemaError(f"{ctx}[{i}]: ({sx}, {sy}) is outside the canvas {cw}x{ch}")
        out.append((sx, sy))
    return tuple(out)


def _as_seed_list_or_empty(value, ctx: str, canvas: tuple[int, int] | None = None
                           ) -> tuple[tuple[int, int], ...]:
    """Like :func:`_as_seed_list`, but ``[]``/absent is valid (no impassable seeds
    declared) rather than an error."""
    if isinstance(value, list) and not value:
        return ()
    return _as_seed_list(value, ctx, canvas)


def load_sea_zones(path: Path, canvas: tuple[int, int] | None = None) -> SeaZoneConfig:
    """Load + validate the committed canon-sea seed config (authored order kept).

    Bounds-checks every seed against ``canvas`` when known and rejects a duplicate
    canon-sea name, exactly like :func:`load_out_of_scope_continents`. Additionally
    hard-errors on a **duplicate seed pixel across all canon seas** (two seas
    seeding one pixel is last-writer-wins in the seed raster — a silent authoring
    bug), and on an override whose ``canon_sea`` does not resolve to a declared
    name. Preserves authored order — it is the deterministic canon-index tie-break.
    """
    ctx = path.name
    data = _load_json(path)
    seas_raw = _require(data, "canon_seas", ctx)
    if not isinstance(seas_raw, list) or not seas_raw:
        raise SchemaError(f"{ctx}.canon_seas: expected a non-empty list")
    seas = [CanonSea.from_dict(s, f"{ctx}.canon_seas[{i}]", canvas)
            for i, s in enumerate(seas_raw)]

    names = [s.name for s in seas]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise SchemaError(f"{ctx}: duplicate canon-sea names {sorted(dupes)}")

    seen_seeds: dict[tuple[int, int], str] = {}
    for s in seas:
        for seed in s.seeds:
            if seed in seen_seeds:
                raise SchemaError(
                    f"{ctx}: seed pixel {list(seed)} is claimed by both "
                    f"'{seen_seeds[seed]}' and '{s.name}' — seeds must be unique"
                )
            seen_seeds[seed] = s.name

    overrides_raw = data.get("overrides", [])
    if not isinstance(overrides_raw, list):
        raise SchemaError(f"{ctx}.overrides: expected a list, got {type(overrides_raw).__name__}")
    overrides = [SeaZoneOverride.from_dict(o, f"{ctx}.overrides[{i}]", canvas)
                 for i, o in enumerate(overrides_raw)]
    declared = set(names)
    for i, o in enumerate(overrides):
        if o.canon_sea not in declared:
            raise SchemaError(
                f"{ctx}.overrides[{i}].canon_sea: '{o.canon_sea}' is not a declared canon sea"
            )

    merges_raw = data.get("merges", [])
    if not isinstance(merges_raw, list):
        raise SchemaError(f"{ctx}.merges: expected a list, got {type(merges_raw).__name__}")
    merges = [SeaZoneMerge.from_dict(m, f"{ctx}.merges[{i}]", canvas)
              for i, m in enumerate(merges_raw)]
    merge_names = [m.name for m in merges]
    dupe_merge_names = {n for n in merge_names if merge_names.count(n) > 1}
    if dupe_merge_names:
        raise SchemaError(f"{ctx}: duplicate merge names {sorted(dupe_merge_names)}")
    name_collisions = declared & set(merge_names)
    if name_collisions:
        raise SchemaError(
            f"{ctx}: merge name(s) {sorted(name_collisions)} collide with a declared canon sea"
        )
    for m in merges:
        for seed in m.seeds:
            if seed in seen_seeds:
                raise SchemaError(
                    f"{ctx}: merge '{m.name}' seed {list(seed)} is already claimed by "
                    f"canon sea '{seen_seeds[seed]}' — seeds must be unique across the file"
                )
            seen_seeds[seed] = f"merge:{m.name}"

    impassable_raw = data.get("impassable_seeds", [])
    impassable_seeds = _as_seed_list_or_empty(impassable_raw, f"{ctx}.impassable_seeds", canvas)
    for seed in impassable_seeds:
        if seed in seen_seeds and not seen_seeds[seed].startswith("merge:"):
            raise SchemaError(
                f"{ctx}.impassable_seeds: {list(seed)} is also a canon-sea seed "
                f"('{seen_seeds[seed]}') — pick a different interior pixel"
            )

    names_raw = data.get("zone_names", [])
    if not isinstance(names_raw, list):
        raise SchemaError(f"{ctx}.zone_names: expected a list, got {type(names_raw).__name__}")
    zone_names = [SeaZoneDisplayName.from_dict(zn, f"{ctx}.zone_names[{i}]", canvas)
                  for i, zn in enumerate(names_raw)]
    seen_name_seeds: set[tuple[int, int]] = set()
    for zn in zone_names:
        if zn.seed in seen_name_seeds:
            raise SchemaError(
                f"{ctx}.zone_names: seed pixel {list(zn.seed)} is claimed by more than one "
                f"zone_names entry — seeds must be unique within zone_names"
            )
        seen_name_seeds.add(zn.seed)

    return SeaZoneConfig(canon_seas=tuple(seas), overrides=tuple(overrides),
                          merges=tuple(merges), impassable_seeds=impassable_seeds,
                          zone_names=tuple(zone_names))


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
#:  * ``frame_alias``        — a crop/rescale of another registered source; it
#:                             borrows that source's control points rather than
#:                             duplicating them (see :class:`FrameAlias`).
PROJECTION_KINDS = ("natural_earth_2", "equirectangular", "control_point_warp", "frame_alias")

#: Minimum control points per projection. A control-point warp needs at least an
#: affine's worth (3); the parametric projections need 2 to fit scale/placement;
#: an alias needs none, because its placement comes entirely from its parent.
_MIN_CONTROL_POINTS = {
    "natural_earth_2": 2,
    "equirectangular": 2,
    "control_point_warp": 3,
    "frame_alias": 0,
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
class FrameAlias:
    """This source is a crop/rescale of another registered source's frame.

    Four of the Immortal Empires references are the *same picture* at different
    crops and scales (measured — see ``tools/SOURCES.md``). Authoring dense
    control points four times would be four chances to author them inconsistently,
    and a later correction would have to be applied four times. Instead one record
    carries the warp and the siblings declare the fixed affine that takes their
    own pixels into its:

        parent_px = source_px * scale + offset

    ``scale`` is deliberately expressed in the direction that needs no division —
    a sibling at 0.6673x the master records ``scale = 1/0.6673``, computed once
    here rather than inverted at every call site.
    """

    of: str
    scale: Point
    offset: Point

    def to_parent_px(self, x, y):
        """Map this source's pixel coordinates into the parent's."""
        return (x * self.scale[0] + self.offset[0],
                y * self.scale[1] + self.offset[1])

    @classmethod
    def from_dict(cls, d: dict, ctx: str) -> "FrameAlias":
        of = _as_str(_require(d, "of", ctx), f"{ctx}.of")
        scale = _as_point(_require(d, "scale", ctx), f"{ctx}.scale")
        offset = _as_point(_require(d, "offset", ctx), f"{ctx}.offset")
        if scale[0] <= 0 or scale[1] <= 0:
            raise SchemaError(f"{ctx}.scale: must be positive, got {scale}")
        return cls(of=of, scale=scale, offset=offset)


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
    frame_alias: FrameAlias | None = None

    @property
    def is_alias(self) -> bool:
        return self.projection == "frame_alias"

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

        alias_raw = d.get("frame_alias")
        if projection == "frame_alias":
            if alias_raw is None:
                raise SchemaError(f"{ctx}: projection 'frame_alias' requires a 'frame_alias' block")
            if not isinstance(alias_raw, dict):
                raise SchemaError(f"{ctx}.frame_alias: expected an object, got {type(alias_raw).__name__}")
            frame_alias = FrameAlias.from_dict(alias_raw, f"{ctx}.frame_alias")
            if frame_alias.of == source:
                raise SchemaError(f"{ctx}.frame_alias.of: a source cannot alias itself")
            # Control points on an alias would be silently ignored, which is worse
            # than refusing them: the author would think they had an effect.
            if control_points:
                raise SchemaError(
                    f"{ctx}: a frame_alias takes its placement from '{frame_alias.of}' — "
                    f"remove its {len(control_points)} control point(s) and correct the parent instead"
                )
        else:
            if alias_raw is not None:
                raise SchemaError(
                    f"{ctx}: 'frame_alias' is only meaningful with projection 'frame_alias', "
                    f"not '{projection}'"
                )
            frame_alias = None

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
                   precedence, layer_precedence, frame_alias)


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
