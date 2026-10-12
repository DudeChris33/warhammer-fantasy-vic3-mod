"""Land that is in scope although the border-density rule would not find it.

``mapgen/config/in_scope_additions.json`` lists it: islands with no interior
state border, and small caps cut off a mainland by one border stroke. Each
addition marks land regions by a box (a region is taken when more than half of
its pixels lie inside) or by points (the region holding the point is taken), and
names the realm those regions take.

Two generators share this module so they cannot disagree about which regions
are meant: ``generate_provinces.py`` (which regions are cut as drawn states) and
``generate_land_regions.py`` (which realm each one belongs to). Pure functions
of the label array and the config, no RNG.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


class ScopeAdditionError(ValueError):
    """The additions file is malformed or does not fit the map."""


@dataclass(frozen=True)
class Realm:
    realm: str
    file_stem: str
    continent: str


@dataclass(frozen=True)
class Addition:
    name: str
    realm: str
    box: tuple[int, int, int, int] | None
    points: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ScopeAdditions:
    realms: dict[str, Realm]
    additions: tuple[Addition, ...]


def load(path: Path, canvas: tuple[int, int]) -> ScopeAdditions:
    """Load and validate the additions file against a ``(width, height)`` canvas."""
    ctx = path.name
    data = json.loads(path.read_text(encoding="utf-8"))
    w, h = canvas
    realms: dict[str, Realm] = {}
    for i, raw in enumerate(data.get("realms", [])):
        try:
            r = Realm(str(raw["realm"]), str(raw["file_stem"]), str(raw["continent"]))
        except KeyError as exc:
            raise ScopeAdditionError(f"{ctx}.realms[{i}]: missing {exc}")
        if r.realm in realms:
            raise ScopeAdditionError(f"{ctx}: duplicate realm {r.realm!r}")
        realms[r.realm] = r
    additions: list[Addition] = []
    seen: set[str] = set()
    for i, raw in enumerate(data.get("additions", [])):
        where = f"{ctx}.additions[{i}]"
        name, realm = str(raw.get("name", "")), str(raw.get("realm", ""))
        if not name or name in seen:
            raise ScopeAdditionError(f"{where}: name missing or repeated ({name!r})")
        seen.add(name)
        if realm not in realms:
            raise ScopeAdditionError(f"{where} ({name}): realm {realm!r} is not declared in realms")
        box = raw.get("box")
        points = raw.get("points", [])
        if (box is None) == (not points):
            raise ScopeAdditionError(f"{where} ({name}): give exactly one of box or points")
        if box is not None:
            if len(box) != 4:
                raise ScopeAdditionError(f"{where} ({name}): box must be [x0, y0, x1, y1]")
            x0, y0, x1, y1 = (int(v) for v in box)
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
                raise ScopeAdditionError(f"{where} ({name}): box {box} is empty or off the {w}x{h} canvas")
            box = (x0, y0, x1, y1)
        pts = []
        for p in points:
            x, y = int(p[0]), int(p[1])
            if not (0 <= x < w and 0 <= y < h):
                raise ScopeAdditionError(f"{where} ({name}): point {p} is off the {w}x{h} canvas")
            pts.append((x, y))
        additions.append(Addition(name, realm, box, tuple(pts)))
    return ScopeAdditions(realms, tuple(additions))


def region_realms(region_of_pixel: np.ndarray, cfg: ScopeAdditions) -> dict[int, str]:
    """``region id -> realm`` for every land region an addition takes.

    ``region_of_pixel`` is the canvas-shaped region label array, 0 off land. A
    point on a pixel with no region, a box that takes nothing, and a region
    claimed by two additions of different realms are errors: each means the
    config no longer matches the map.
    """
    n = int(region_of_pixel.max())
    areas = np.bincount(region_of_pixel.ravel(), minlength=n + 1)
    out: dict[int, str] = {}
    owner: dict[int, str] = {}

    def claim(rid: int, add: Addition) -> None:
        if rid in out and out[rid] != add.realm:
            raise ScopeAdditionError(
                f"region {rid} is taken by both '{owner[rid]}' ({out[rid]}) and "
                f"'{add.name}' ({add.realm})")
        out[rid] = add.realm
        owner.setdefault(rid, add.name)

    for add in cfg.additions:
        if add.box is not None:
            x0, y0, x1, y1 = add.box
            inside = np.bincount(region_of_pixel[y0:y1, x0:x1].ravel(), minlength=n + 1)
            taken = [rid for rid in range(1, n + 1) if areas[rid] and inside[rid] * 2 > areas[rid]]
            if not taken:
                raise ScopeAdditionError(f"addition '{add.name}': its box {list(add.box)} takes no land region")
            for rid in taken:
                claim(rid, add)
        for x, y in add.points:
            rid = int(region_of_pixel[y, x])
            if rid <= 0:
                raise ScopeAdditionError(f"addition '{add.name}': point ({x}, {y}) is not on a land region")
            claim(rid, add)
    return out
