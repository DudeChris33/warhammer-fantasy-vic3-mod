#!/usr/bin/env python3
"""Generator: the committed physical priors + lore -> tools/derived/arable_heatmap.png.

Board #4921 (epic #3675). A single canvas-aligned (8192x3616) 16-bit grayscale
raster of *relative* arable potential over the drawn Old World — barren ->
breadbasket, proportions only, **no Victoria 3 ``arable_land`` numbers**. It is the
shared physical+lore prior the epic's realm children (#3679-#3686) sample instead
of each re-deriving one; turning intensity into per-state values is downstream and
out of scope here.

The field is the pure ``worldgen.arable.build_field`` (climate . terrain .
hydrology . wind/rain-shadow moisture . lore, masked off water/lake/impassable,
tone-curved, percentile-normalized). This driver only does the I/O the core forbids itself: read the
committed inputs, block-average the heightmap to the canvas, build the river-width
weight from ``rivers.png``, encode the 16-bit PNG, and write the provenance
sidecar. It mirrors ``generate_rivers.py``.

The committed raster reads **only committed inputs** — ``land_sea_mask.png``,
``lake_mask.png``, ``heightmap.png``, ``rivers.png``, ``arable_lore.json`` — no
``sources/`` file — so it reproduces byte-identically on any device (the repo's
regenerate-never-hand-edit discipline; "MP determinism" here is reproducibility,
not engine MP-sync — the raster is never loaded by Victoria 3). ``--check`` proves
exactly that against the committed file.

Known limitation (board #5056, deferred): the field is built over *all* passable
land, and ``map_data/heightmap.png`` has region-label text ("GRAND CATHAY")
baked into the **out-of-scope** far-eastern landmass as elevation, so it surfaces
as suppressed (dark) text there. That land is out of scope (Old World only) and
sampled by no realm child; per Chris (2026-09-20) the heightmap label is fixed
when Cathay is brought in-scope, not here. The in-scope Old World heightmap is
clean.

Usage::

    python tools/generate_arable_heatmap.py             # write the raster + sidecar
    python tools/generate_arable_heatmap.py --dry-run   # compose + report, write nothing
    python tools/generate_arable_heatmap.py --check      # regen to temp, diff the committed raster
    python tools/generate_arable_heatmap.py --gamma 0.55 --norm-pctl 99.0
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # the heightmap is 16384x7232 = 118 Mpx, over PIL's default guard

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import canvas_frame as cf  # noqa: E402
from config import map_config  # noqa: E402
from worldgen import arable, raster, rivers as riverlib, schema  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MAP_DATA_DIR = REPO_ROOT / "map_data"

MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
LAKE_MASK_PATH = DERIVED_DIR / "lake_mask.png"
HEIGHTMAP_PATH = MAP_DATA_DIR / "heightmap.png"
RIVERS_PATH = MAP_DATA_DIR / "rivers.png"
LORE_JSON = TOOLS_DIR / "config" / "arable_lore.json"
#: Optional committed impassable/barrier mask (#3704, unbuilt) — clean-skip when
#: absent (the _check_adjacencies / canon_cities idiom): mountains are already
#: suppressed proportionally by the terrain factor, which is right for a potential.
IMPASSABLE_PATH = DERIVED_DIR / "impassable_mask.png"

OUT_PNG = DERIVED_DIR / "arable_heatmap.png"
OUT_INDEX = DERIVED_DIR / "arable_heatmap_index.json"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE


def log(msg: str, t0: float | None = None) -> None:
    stamp = f"  [{time.time() - t0:5.1f}s]" if t0 is not None else ""
    print(f"{msg}{stamp}", flush=True)


def _lat_per_row() -> np.ndarray:
    """Latitude (deg) of each canvas row. Latitude is x-independent under the
    Miller frame, so one column of the inverse transform is the whole field."""
    _, lat = cf.canvas_to_lonlat(np.zeros(CANVAS_H), np.arange(CANVAS_H, dtype=np.float64))
    return np.asarray(lat, dtype=np.float64)


def _elev_m_canvas() -> np.ndarray:
    """Metres above sea level on the canvas grid (0 in the sea).

    The heightmap grid is exactly 2x the canvas: block-average 2x2 down to it (the
    ``render_wind_patterns`` idiom), subtract the committed sea-level value, clip
    the sea floor to 0, and convert stored units to metres. The result has no
    shoreline cliff (coastal land sits a few metres above 0), so the slope term is
    safe."""
    with Image.open(HEIGHTMAP_PATH) as im:
        h = np.asarray(im, dtype=np.float32)
    hw, hh = map_config.HEIGHTMAP_SIZE
    if h.shape != (hh, hw):
        raise SystemExit(f"heightmap is {h.shape[1]}x{h.shape[0]}, expected {hw}x{hh}")
    h = h.reshape(CANVAS_H, 2, CANVAS_W, 2).mean(axis=(1, 3))
    elev = np.clip(h - map_config.HEIGHT_SEA_LEVEL, 0.0, None)
    return (elev / map_config.HEIGHT_UNITS_PER_METRE).astype(np.float32)


def _river_masks() -> tuple[np.ndarray, np.ndarray]:
    """``(river bool, river_width float)`` from the committed indexed ``rivers.png``.

    A river pixel is any index that is not LAND/SEA. Its drawn stream width is the
    index value itself (the vanilla ramp 3/4/6/8); the source/merge/split markers
    (0/1/2) are floored to the smallest ramp width so a confluence is not
    under-weighted. Width feeds the width-modulated river boost (panel note: the
    Reik/Talabec/Stir/Aver should read as the fertile floor)."""
    idx, _ = raster.read_indexed_png(RIVERS_PATH)
    if idx.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"rivers.png is {idx.shape[1]}x{idx.shape[0]}, expected "
                         f"{CANVAS_W}x{CANVAS_H}")
    river = ~np.isin(idx, [riverlib.LAND, riverlib.SEA])
    ramp_min = float(min(p for p in (3, 4, 6, 8)))  # smallest vanilla ramp width
    width = np.zeros((CANVAS_H, CANVAS_W), dtype=np.float32)
    vals = idx[river].astype(np.float32)
    # markers 0/1/2 -> the smallest ramp width; ramp values kept as-is.
    vals = np.where(vals <= riverlib.SPLIT, ramp_min, vals)
    width[river] = vals
    return river, width


def compose(params: arable.ArableParams, t0: float
            ) -> tuple[np.ndarray, dict, np.ndarray]:
    """Read the committed inputs and run the pure core. Returns ``(field, stats,
    passable)``."""
    for pth, hint in ((MASK_PATH, "generate_coastline_mask.py"),
                      (HEIGHTMAP_PATH, "generate_heightmap.py"),
                      (RIVERS_PATH, "generate_rivers.py")):
        if not pth.is_file():
            raise SystemExit(f"{pth} not found — run tools/{hint} first")

    log("loading committed inputs (mask, lake, heightmap, rivers, lore)...")
    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"land mask is {land.shape}, expected {(CANVAS_H, CANVAS_W)}")
    lake = (raster.read_mask_png(LAKE_MASK_PATH) if LAKE_MASK_PATH.is_file()
            else np.zeros_like(land))
    sea = (~land) & (~lake)
    passable = land & (~lake)
    if IMPASSABLE_PATH.is_file():
        impassable = raster.read_mask_png(IMPASSABLE_PATH)
        passable &= ~impassable
        log(f"  impassable mask: {int(impassable.sum()):,} px held out", t0)
    else:
        log("  (no committed impassable mask — terrain factor suppresses relief; clean-skip)", t0)

    lat = _lat_per_row()
    elev_m = _elev_m_canvas()
    river, river_width = _river_masks()
    log(f"  land {int(land.sum()):,} px, sea {int(sea.sum()):,}, lake {int(lake.sum()):,}, "
        f"river {int(river.sum()):,}", t0)

    zones = []
    if LORE_JSON.is_file():
        zones = schema.load_arable_lore(LORE_JSON, canvas=(CANVAS_W, CANVAS_H))
        log(f"  {len(zones)} lore zone(s): "
            f"{sum(1 for z in zones if z.kind == 'breadbasket')} breadbasket, "
            f"{sum(1 for z in zones if z.kind == 'blight')} blight", t0)
    else:
        log("  (no arable_lore.json — physical priors only, L = 1)", t0)

    log("composing field (climate . terrain . hydrology . moisture . lore -> normalize -> tone)...")
    field, stats = arable.build_field(
        lat_per_row=lat, elev_m=elev_m, sea=sea, passable=passable,
        river=river, river_width=river_width, lore_zones=zones,
        params=params, wrap_x=map_config.WRAP_X)
    s = stats["summary"]
    log(f"  passable {stats['passable_px']:,} px; field mean {s['mean']:.3f} "
        f"max {s['max']:.3f}; norm@P{stats['norm_pctl']} = {stats['norm_value']:.4g}; "
        f"gamma {stats['gamma']}", t0)
    return field, stats, passable


def encode16(field: np.ndarray) -> np.ndarray:
    """Field in [0,1] -> uint16 grayscale (0 stays 0 on non-passable land)."""
    return np.rint(np.clip(field, 0.0, 1.0) * 65535.0).astype(np.uint16)


def _write_index(stats: dict, path: Path) -> None:
    payload = {
        "_comment": "Generated by tools/generate_arable_heatmap.py (board #4921). "
                    "Regenerate, never hand-edit. Provenance for arable_heatmap.png: "
                    "factor weights, the normalization value + percentile, the tone "
                    "gamma, and the passable-field histogram/quantiles so any shift "
                    "between regenerations is visible in a diff.",
        **stats,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true",
                   help="compose + report, write no PNG or sidecar")
    p.add_argument("--check", action="store_true",
                   help="regenerate to a temp file and diff the committed raster "
                        "(proves byte-identical reproduction); write nothing")
    p.add_argument("--gamma", type=float, default=None,
                   help="tone-curve exponent (default from ArableParams; <1 lifts the mid)")
    p.add_argument("--norm-pctl", type=float, default=None,
                   help="normalization percentile (default from ArableParams)")
    p.add_argument("--moist-lambda", type=float, default=None,
                   help="rain-shadow overland-fetch decay length, canvas px (default from ArableParams)")
    p.add_argument("--moist-oro-m", type=float, default=None,
                   help="rain-shadow orographic loss: metres of upwind ascent per 1/e drop")
    p.add_argument("--moist-floor", type=float, default=None,
                   help="floor on the moisture factor (driest interior; default from ArableParams)")
    p.add_argument("--no-moisture", action="store_true",
                   help="disable the wind/rain-shadow factor (physical-only fallback)")
    args = p.parse_args(argv)

    overrides = {}
    if args.gamma is not None:
        overrides["gamma"] = args.gamma
    if args.norm_pctl is not None:
        overrides["norm_pctl"] = args.norm_pctl
    if args.moist_lambda is not None:
        overrides["moist_lambda"] = args.moist_lambda
    if args.moist_oro_m is not None:
        overrides["moist_oro_m"] = args.moist_oro_m
    if args.moist_floor is not None:
        overrides["moist_floor"] = args.moist_floor
    if args.no_moisture:
        overrides["moist_enable"] = False
    params = arable.ArableParams(**overrides) if overrides else arable.ArableParams()

    t0 = time.time()
    field, stats, _ = compose(params, t0)
    gray = encode16(field)

    if args.check:
        if not OUT_PNG.is_file():
            log(f"--check: {OUT_PNG} is not committed yet — nothing to diff against.", t0)
            return 0
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "arable_heatmap.png"
            raster.write_gray16_png(tmp, gray)
            committed = OUT_PNG.read_bytes()
            regen = tmp.read_bytes()
        if committed == regen:
            log("--check: regenerated raster is byte-identical to the committed one.", t0)
            return 0
        log("--check: MISMATCH — regenerated raster differs from the committed "
            f"{OUT_PNG.name} (stale commit or non-deterministic input).", t0)
        return 1

    if args.dry_run:
        log("dry run — nothing written.", t0)
        return 0

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    raster.write_gray16_png(OUT_PNG, gray)
    log(f"wrote {OUT_PNG} ({OUT_PNG.stat().st_size / 1024:.0f} KB)", t0)
    _write_index(stats, OUT_INDEX)
    log(f"wrote {OUT_INDEX}", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
