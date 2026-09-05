"""State-region text emission + hub auto-pick.

Turns the generated province partition into ``map_data/state_regions/*.txt``
Clausewitz text, in the vanilla / Exether format (verified against
``realms-of-exether/map_data/state_regions/``). P3 reuses these helpers for the
full-scale generator; P1 exercises them on the fixture.

Hub auto-pick is deliberately simple and deterministic; hubs are one-line manual
refinements later. Impassable provinces are never picked as hubs.
"""

from __future__ import annotations

from dataclasses import dataclass

from .raster import Color, Point, color_to_hex, wrap_signed_delta
from .schema import State

INDENT = "    "  # 4 spaces, matching the reference state files


@dataclass(frozen=True)
class ProvinceInfo:
    """A generated province, as far as state-file emission cares."""

    color: Color
    centroid: Point
    area: int
    coastal: bool
    impassable: bool


class HubError(ValueError):
    """Raised when a state has too few passable provinces to place its hubs."""


def compute_centroid(pixels, width: int, wrap_x: bool = True) -> Point:
    """Wrap-aware centroid of a pixel set.

    Unwraps every x relative to a deterministic reference (the minimum x) before
    averaging, so a province straddling the seam gets a sensible centroid.
    Assumes a province spans less than half the canvas width (always true here).
    """
    pts = list(pixels)
    n = len(pts)
    if n == 0:
        raise ValueError("cannot take the centroid of an empty pixel set")
    ref_x = min(px for px, _ in pts)
    sx = 0.0
    sy = 0.0
    for (x, y) in pts:
        sx += (ref_x + wrap_signed_delta(x, ref_x, width)) if wrap_x else x
        sy += y
    cx = (sx / n) % width if wrap_x else sx / n
    return (cx, sy / n)


def _hex_list(colors) -> str:
    """`{ xAAAAAA xBBBBBB }` with colours in a deterministic (sorted) order."""
    return "{ " + " ".join(color_to_hex(c) for c in sorted(colors)) + " }"


def pick_hubs(
    state: State,
    provinces: list[ProvinceInfo],
    width: int,
    wrap_x: bool = True,
) -> dict[str, Color]:
    """Auto-pick ``city``/``farm``/``mine``/``wood`` (+ ``port`` if coastal).

    * Port (coastal states only) = the coastal province with the largest area
      (ties → lowest colour), a stand-in for "faces the naval-exit sea" that P3
      refines.
    * City = the remaining province whose centroid is nearest the state centroid.
    * Farm / mine / wood = three spread picks from what remains.

    Impassable provinces are excluded from every hub. Raises :class:`HubError`
    if there are too few passable provinces.
    """
    candidates = sorted(
        (p for p in provinces if not p.impassable), key=lambda p: p.color
    )
    needed = 5 if (state.kind == "land" and state.coastal) else 4
    if len(candidates) < needed:
        raise HubError(
            f"{state.key}: needs {needed} passable provinces for hubs, "
            f"has {len(candidates)}"
        )

    hubs: dict[str, Color] = {}
    pool = list(candidates)

    if state.coastal:
        coastal_candidates = [p for p in pool if p.coastal]
        if not coastal_candidates:
            raise HubError(f"{state.key}: coastal state has no coastal province for a port")
        port = max(coastal_candidates, key=lambda p: (p.area, tuple(-c for c in p.color)))
        hubs["port"] = port.color
        pool.remove(port)

    state_centroid = _state_centroid(pool, width, wrap_x)
    city = min(
        pool,
        key=lambda p: (_wrap_dist2(p.centroid, state_centroid, width, wrap_x), p.color),
    )
    hubs["city"] = city.color
    pool.remove(city)

    # Spread farm/mine/wood across the sorted remainder.
    pool.sort(key=lambda p: p.color)
    idx = [0, len(pool) // 2, len(pool) - 1]
    for name, i in zip(("farm", "mine", "wood"), idx):
        hubs[name] = pool[i].color
    return hubs


def stack_hubs(provinces: list[ProvinceInfo], coastal: bool) -> dict[str, Color]:
    """Fallback hub placement for a state with fewer passable provinces than
    :func:`pick_hubs` needs (board #2930: every single-province placeholder
    state, and any small drawn region).

    ``city``/``farm``/``mine``/``wood`` cycle across whatever passable
    provinces exist (sorted by colour, ``ordered[i % k]``), so a 1-province
    state stacks every hub on that one province. ``port`` (coastal states
    only) is the largest-area coastal candidate (falling back to the largest
    candidate overall if none happen to be individually coastal), independent
    of the cycle. Legal per vanilla precedent (``STATE_MALTA`` stacks
    city+port on one province, farm+mine+wood on another) and the validator's
    own rule (hub membership only requires a hub be one of the state's own
    provinces, never distinct from the others).
    """
    if not provinces:
        raise HubError("cannot stack hubs onto an empty province list")
    hubs: dict[str, Color] = {}
    if coastal:
        coastal_candidates = [p for p in provinces if p.coastal] or list(provinces)
        port = max(coastal_candidates, key=lambda p: (p.area, tuple(-c for c in p.color)))
        hubs["port"] = port.color
    ordered = sorted(provinces, key=lambda p: p.color)
    k = len(ordered)
    for i, name in enumerate(("city", "farm", "mine", "wood")):
        hubs[name] = ordered[i % k].color
    return hubs


def _state_centroid(provinces: list[ProvinceInfo], width: int, wrap_x: bool) -> Point:
    """Area-weighted centroid of a state's provinces (wrap-aware)."""
    total = sum(p.area for p in provinces)
    ref_x = min(p.centroid[0] for p in provinces)
    sx = 0.0
    sy = 0.0
    for p in provinces:
        cx = (ref_x + wrap_signed_delta(p.centroid[0], ref_x, width)) if wrap_x else p.centroid[0]
        sx += cx * p.area
        sy += p.centroid[1] * p.area
    x = (sx / total) % width if wrap_x else sx / total
    return (x, sy / total)


def _wrap_dist2(p: Point, q: Point, width: int, wrap_x: bool) -> float:
    dx = abs(wrap_signed_delta(p[0], q[0], width)) if wrap_x else abs(p[0] - q[0])
    dy = p[1] - q[1]
    return dx * dx + dy * dy


# ---------------------------------------------------------------------------
# Text emission
# ---------------------------------------------------------------------------

def render_land_state(
    state: State,
    state_id: int,
    province_colors: list[Color],
    hubs: dict[str, Color],
    impassable_colors: list[Color],
    naval_exit_id: int | None,
) -> str:
    """One land-state block, in the verified vanilla format."""
    econ = state.economics
    assert econ is not None  # guaranteed for land states by the schema
    lines = [f"{state.key} = {{"]
    lines.append(f"{INDENT}id = {state_id}")
    lines.append(f'{INDENT}subsistence_building = "{econ.subsistence_building}"')
    lines.append(f"{INDENT}provinces = {_hex_list(province_colors)}")
    if impassable_colors:
        lines.append(f"{INDENT}impassable = {_hex_list(impassable_colors)}")
    for hub in ("city", "farm", "mine", "wood"):
        lines.append(f"{INDENT}{hub} = {color_to_hex(hubs[hub])}")
    if state.coastal:
        lines.append(f"{INDENT}port = {color_to_hex(hubs['port'])}")
    lines.append(f"{INDENT}arable_land = {econ.arable_land}")
    resources = " ".join(f'"{r}"' for r in econ.arable_resources)
    lines.append(f"{INDENT}arable_resources = {{ {resources} }}")
    lines.append(f"{INDENT}capped_resources = {{")
    for building in sorted(econ.capped_resources):
        lines.append(f"{INDENT}{INDENT}{building} = {econ.capped_resources[building]}")
    lines.append(f"{INDENT}}}")
    if state.coastal:
        if naval_exit_id is None:
            raise ValueError(f"{state.key}: coastal state needs a resolved naval_exit_id")
        lines.append(f"{INDENT}naval_exit_id = {naval_exit_id}")
    lines.append("}")
    return "\n".join(lines)


def render_sea_state(
    state: State,
    state_id: int,
    province_color: Color,
    impassable: bool = False,
) -> str:
    """One single-province sea-zone block."""
    lines = [f"{state.key} = {{"]
    lines.append(f"{INDENT}id = {state_id}")
    lines.append(f"{INDENT}provinces = {_hex_list([province_color])}")
    if impassable:
        lines.append(f"{INDENT}impassable = {_hex_list([province_color])}")
    lines.append("}")
    return "\n".join(lines)


def render_state_file(blocks: list[str]) -> str:
    """Join state blocks into a file body (LF newlines, trailing newline)."""
    return "\n".join(blocks) + "\n"
