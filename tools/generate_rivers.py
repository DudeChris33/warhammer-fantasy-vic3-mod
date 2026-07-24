#!/usr/bin/env python3
"""S2 generator: the v1 canon rivers -> map_data/rivers.png.

Reads the committed river polylines (``tools/rivers/rivers.json``, traced from the
Empire rivers map and the Old World map against the reprojected coastline) and the
committed land/sea mask, and rasterizes a Vic3-valid ``rivers.png``:

    tools/rivers/rivers.json  +  tools/derived/land_sea_mask.png
        -> worldgen.rivers.rasterize (1px lines, source/width/merge, validated)
        -> map_data/rivers.png  (indexed, vanilla palette)

The rivers are drawn against the **same** land/sea mask the heightmap uses, so
their mouths meet the same coastline the relief does — the two shipped bitmaps are
mutually consistent even while S2 keeps vanilla ``provinces.png``. Validity
(one-pixel width, inland sources, mouths reaching water, clean confluences) is
enforced in ``worldgen.rivers`` before anything is written; a bad vertex is an
offline error, never an in-game one.

Usage::

    python tools/generate_rivers.py            # write map_data/rivers.png
    python tools/generate_rivers.py --preview   # + a downscaled overlay for eyeballing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import raster, rivers as riverlib, schema  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MAP_DATA_DIR = REPO_ROOT / "map_data"
RIVERS_JSON = TOOLS_DIR / "rivers" / "rivers.json"
PALETTE_JSON = TOOLS_DIR / "lut" / "rivers_palette.json"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--preview", action="store_true", help="also write a downscaled overlay")
    args = p.parse_args(argv)

    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first")
    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (map_config.PROVINCES_SIZE[1], map_config.PROVINCES_SIZE[0]):
        raise SystemExit(f"mask is {land.shape}, expected {map_config.PROVINCES_SIZE[::-1]}")

    streams = schema.load_river_streams(RIVERS_JSON)
    palette = riverlib.load_palette(PALETTE_JSON)
    print(f"loaded {len(streams)} river streams; rasterizing over {land.shape[1]}x{land.shape[0]} mask")

    idx = riverlib.rasterize(streams, land, palette, wrap_x=map_config.WRAP_X)

    MAP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = MAP_DATA_DIR / "rivers.png"
    riverlib.write_rivers_png(out, idx, palette)
    drawn = int((~np.isin(idx, [riverlib.LAND, riverlib.SEA])).sum())
    print(f"wrote {out}: {drawn} river pixels across {len(streams)} streams "
          f"({out.stat().st_size / 1024:.0f} KB)")

    for st in streams:
        print(f"  - {st.name:16s} width {st.width}  mouth={st.mouth}  ({len(st.points)} vertices)")

    if args.preview:
        _write_preview(idx, palette, DERIVED_DIR / "preview_rivers.png")
    return 0


def _write_preview(idx: np.ndarray, palette: riverlib.RiverPalette, path: Path, step: int = 4) -> None:
    """Downscaled RGB overlay: coast in grey, rivers in their palette blue, sources green."""
    small = idx[::step, ::step]
    rgb = np.zeros(small.shape + (3,), dtype=np.uint8)
    rgb[small == riverlib.LAND] = (60, 80, 55)
    rgb[small == riverlib.SEA] = (25, 40, 75)
    for i, colour in enumerate(palette.table):
        if i in (riverlib.LAND, riverlib.SEA):
            continue
        m = small == i
        if m.any():
            rgb[m] = colour
    raster.write_rgb_png(path, rgb)
    print(f"  preview -> {path}")


if __name__ == "__main__":
    raise SystemExit(main())
