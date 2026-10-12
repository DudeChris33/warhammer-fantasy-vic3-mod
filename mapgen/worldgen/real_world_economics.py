"""Per-state land economics from real-world equivalents (Chris, 2026-10-12).

Each WHFB zone (legend in ``mapgen/config/real_world_equivalents.json``) stands in
for a coloured real-world area on ``sources/history/real-world-comparisons-r.png``.
The zone's *vanilla* totals (arable land, capped resources, discovered/undiscovered
resource blocks) are summed once, offline, by ``mapgen/build_real_world_equivalents.py``
and committed; the zone's *geometry* is the canvas-aligned index raster
``mapgen/config/real_world_zones.png`` (0 = no zone). This module is the pure,
install-free half: it spreads each zone's totals over the land regions that overlap
the zone, weighted by overlapping pixels, with largest-remainder rounding so the
integer totals are conserved exactly. Deterministic: pure function of the two
committed inputs and the province bitmap labels (ties break on region id).

A region's arable land / capped resources / resource blocks are the sum of its
shares; its subsistence building and arable-resource list come from the zone it
overlaps most. A region overlapping no zone is absent from the result and falls
back to ``land_economics.DEFAULT_ECONOMICS``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

import numpy as np

from . import raster


class Zone(NamedTuple):
    index: int
    name: str
    arable: int
    subsistence: str
    arable_resources: tuple[str, ...]
    capped: dict[str, int]
    resources: tuple[tuple[str, str, int, int], ...]  # (type, depleted_type or "", discovered, undiscovered)


class Model(NamedTuple):
    zones: tuple[Zone, ...]
    raster: np.ndarray  # uint8, canvas-aligned, 0 = no zone


def load(config_path: Path, zones_png: Path) -> Model | None:
    """The committed model, or ``None`` when either input is absent (fixture runs)."""
    if not (config_path.is_file() and zones_png.is_file()):
        return None
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    zones = []
    for i, z in enumerate(cfg["zones"], start=1):
        zones.append(Zone(
            index=i, name=z["name"], arable=int(z["arable"]), subsistence=z["subsistence"],
            arable_resources=tuple(z["arable_resources"]),
            capped={k: int(v) for k, v in z["capped"].items()},
            resources=tuple((r["type"], r.get("depleted_type", ""), int(r.get("discovered", 0)),
                             int(r.get("undiscovered", 0))) for r in z["resources"])))
    idx = raster.read_rgb_png(zones_png)[..., 0]
    return Model(tuple(zones), idx)


def apportion(total: int, weights: dict[int, float]) -> dict[int, int]:
    """Integer shares of ``total`` proportional to ``weights``, largest remainder first
    (ties by key), summing to exactly ``total``."""
    s = sum(weights.values())
    if total <= 0 or s <= 0:
        return {}
    raw = {k: total * w / s for k, w in weights.items()}
    out = {k: int(v) for k, v in raw.items()}
    left = total - sum(out.values())
    order = sorted(raw, key=lambda k: (-(raw[k] - out[k]), k))
    for k in order[:left]:
        out[k] += 1
    return {k: v for k, v in out.items() if v}


def region_economics(model: Model, labels: np.ndarray, n_land: int, region_of: np.ndarray,
                     n_regions: int) -> tuple[dict[int, dict], dict]:
    """``(region id -> economics fields, stats)`` for every region overlapping a zone."""
    if labels.shape != model.raster.shape:
        raise SystemExit(f"real-world zone raster is {model.raster.shape}, province labels {labels.shape}")
    nz = len(model.zones) + 1
    land = (labels >= 1) & (labels <= n_land)
    reg = region_of[labels[land]].astype(np.int64)
    zon = model.raster[land].astype(np.int64)
    counts = np.bincount(reg * nz + zon, minlength=(n_regions + 1) * nz).reshape(n_regions + 1, nz)
    px: dict[int, dict[int, int]] = {}
    for r, z in zip(*np.nonzero(counts[:, 1:])):
        px.setdefault(int(r), {})[int(z) + 1] = int(counts[r, z + 1])

    fields: dict[int, dict] = {r: {"arable_land": 0, "capped_resources": {}, "res": {}} for r in px}
    unused: list[str] = []
    for z in model.zones:
        w = {r: float(d[z.index]) for r, d in px.items() if z.index in d}
        if not w:
            unused.append(z.name)
            continue
        for r, n in apportion(z.arable, w).items():
            fields[r]["arable_land"] += n
        for b, total in z.capped.items():
            for r, n in apportion(total, w).items():
                fields[r]["capped_resources"][b] = fields[r]["capped_resources"].get(b, 0) + n
        for typ, dep, disc, und in z.resources:
            d_alloc = apportion(disc, w)
            u_alloc = apportion(und, w)
            for r in set(d_alloc) | set(u_alloc):
                cur = fields[r]["res"].get((typ, dep), (0, 0))
                fields[r]["res"][(typ, dep)] = (cur[0] + d_alloc.get(r, 0), cur[1] + u_alloc.get(r, 0))

    zone_by_index = {z.index: z for z in model.zones}
    out: dict[int, dict] = {}
    for r, f in fields.items():
        dom = zone_by_index[max(px[r], key=lambda z: (px[r][z], -z))]
        out[r] = {
            "arable_land": max(1, f["arable_land"]),
            "subsistence_building": dom.subsistence,
            "arable_resources": list(dom.arable_resources),
            "capped_resources": dict(sorted(f["capped_resources"].items())),
            "resources": tuple((t, d, a, b) for (t, d), (a, b) in sorted(f["res"].items())),
            "zone": dom.name,
        }
    return out, {"zones_without_land": unused, "regions": len(out)}
