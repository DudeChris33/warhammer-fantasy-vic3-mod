#!/usr/bin/env python3
"""One-off: real-world lon/lat centroid for every vanilla Vic3 state.

Board #2930's dev-only naming aid. Feeds ``generate_land_regions.py``'s
nearest-vanilla-state name guess: for every region in this mod's Old World, the
generator finds the closest entry in this table by longitude/latitude and
records it as a guess to react to in #2931's canon naming pass. This is a
**coincidental-proximity heuristic** on a fictional world, not a claim that the
Warhammer world's geography truly corresponds to real Earth — it exists only
because both canvases share the same measured, unscaled Miller cylindrical
projection (``tools/config/canvas_frame.py`` / ``tools/measure_vanilla_frame.py``),
so a canvas pixel genuinely does correspond to a real (lon, lat) in both worlds.

Reuses ``measure_vanilla_frame.parse_state_provinces`` / ``.state_centroids``
against vanilla's **full** state roster (not just the 29 anchor islands) —
no new parsing code. Converts each state's canvas centroid to (lon, lat) with
vanilla's own measured frame (``X0 = 4099.0``, ``Y0 = 2102.8`` — *not* this
mod's own ``Y0 = 2142.0``, see ``canvas_frame.py``'s docstring for why they
differ), via the same closed-form Miller math ``canvas_frame.py`` implements.

Read-only against the vanilla install, like ``measure_vanilla_frame.py`` itself.
Rerunnable/explicit, like ``fit_registration.py`` or ``--update-manifest`` — the
committed output is stable as long as the vanilla install stays at the pinned
1.13.9 (``CLAUDE.md``); never part of the offline gate.

Usage::

    python tools/build_vanilla_state_lonlat.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import measure_vanilla_frame as mvf  # noqa: E402 — reuses its vanilla parsing
from config import canvas_frame as cf  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
DERIVED_DIR = TOOLS_DIR / "derived"
OUT_PATH = DERIVED_DIR / "vanilla_state_lonlat.json"

#: Vanilla's own measured frame (measure_vanilla_frame.py's printed table) —
#: deliberately NOT this mod's canvas_frame.X0/Y0, which re-pins Y0 to the
#: user's drawn northern limit. R is shared: wrap_x forces R = W/2pi on both.
VANILLA_X0 = 4099.0
VANILLA_Y0 = 2102.8


def _canvas_to_lonlat_vanilla(x: float, y: float) -> tuple[float, float]:
    lon = float(np.degrees((x - VANILLA_X0) / cf.R_CANVAS))
    lat = float(cf._miller_lat((VANILLA_Y0 - y) / cf.R_CANVAS))
    return lon, lat


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", type=Path, default=mvf.VANILLA_ROOT,
                    help="vanilla game folder (read-only)")
    args = ap.parse_args(argv)

    game = Path(args.game)
    state_dir = game / "map_data" / "state_regions"
    provinces = game / "map_data" / "provinces.png"
    if not state_dir.is_dir() or not provinces.is_file():
        raise SystemExit(f"vanilla map_data not found under {game}")

    print(f"reading {state_dir} (read-only)")
    all_states = mvf.parse_state_provinces(state_dir)
    print(f"  parsed {len(all_states)} states")

    print(f"reading {provinces} (read-only)")
    cents = mvf.state_centroids(provinces, all_states)
    missing = sorted(set(all_states) - set(cents))
    if missing:
        print(f"  WARNING: no pixels found for {len(missing)} state(s): {missing[:5]}")

    out: dict[str, list[float]] = {}
    for state in sorted(cents):
        cx, cy, _count = cents[state]
        lon, lat = _canvas_to_lonlat_vanilla(cx, cy)
        out[state] = [round(lon, 4), round(lat, 4)]

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}  ({len(out)} vanilla states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
