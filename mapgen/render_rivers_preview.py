#!/usr/bin/env python3
"""Dev-only review render for the traced river network (board #3703).

Draws the extracted rivers — coloured by width, green source dots, mouths marked,
names labelled — over the reprojected globe (the review-render convention:
`sources/terraqueous_globe_reprojected.png`, 1:1 with the canvas), so Chris can
judge the traced network by eye before any `map_data/rivers.png` is committed. The
rendered artifact is the gate; his verdict is recorded on the item's trail.

Output is gitignored under `mapgen/derived/` — this is QA, not shipped content, and
it loads source imagery directly (no manifest guard), like the other review
renders (`render_land_regions_preview.py`, `render_hubs_preview.py`).

Usage::

    python mapgen/render_rivers_preview.py             # -> mapgen/derived/rivers_preview.png
    python mapgen/render_rivers_preview.py --scale 3   # bigger (default downscale 4)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

Image.MAX_IMAGE_PIXELS = None

import generate_rivers as gr  # noqa: E402  (reuse the exact source/extract path)
from config import map_config  # noqa: E402
from worldgen import raster, river_network, schema, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
GLOBE = sources.resolve_source_path("terraqueous_globe_reprojected.png")

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: Width index -> render colour (source-green / merge handled separately).
_WIDTH_RGB = {3: (120, 200, 255), 4: (60, 170, 255), 6: (20, 120, 255), 8: (0, 70, 235)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scale", type=int, default=4, help="downscale factor (default 4)")
    p.add_argument("--dilate", type=int, default=2, help="blue-line dilation (default 2)")
    args = p.parse_args(argv)
    t0 = time.time()

    if not gr.MASK_PATH.is_file():
        raise SystemExit(f"{gr.MASK_PATH} not found — run generate_coastline_mask.py first")
    land = raster.read_mask_png(gr.MASK_PATH)
    network = gr.load_network(args.dilate, t0)
    elevation = gr._elevation_canvas()
    names: list[schema.CanonRiverName] = []
    if gr.CANON_NAMES_JSON.is_file():
        names = schema.load_canon_river_names(gr.CANON_NAMES_JSON, canvas=(CANVAS_W, CANVAS_H))
    # Non-strict so a trace with problems still renders: the clean rivers plus a
    # marker at each problem, instead of one hard error. Naming is skipped here
    # (a broken river's anchor would not resolve) — geometry + problems are the point.
    lake = gr._lake_mask(land, t0)
    overrides: list[schema.RiverOverride] = []
    if gr.RIVER_OVERRIDES_JSON.is_file():
        overrides = schema.load_river_overrides(gr.RIVER_OVERRIDES_JSON, canvas=(CANVAS_W, CANVAS_H))
    result = river_network.extract_streams(
        network, land, elevation=elevation, names=(), lake=lake, overrides=overrides,
        wrap_x=map_config.WRAP_X, strict=False)
    n_endo = sum(1 for s in result.streams if s.mouth == "endorheic")
    print(f"  {len(result.streams)} streams extracted ({n_endo} endorheic), "
          f"{len(result.issues)} problem(s)", flush=True)

    step = args.scale
    ow, oh = CANVAS_W // step, CANVAS_H // step
    if GLOBE.is_file():
        globe = np.asarray(Image.open(GLOBE).convert("RGB"))[:CANVAS_H, :CANVAS_W]
        base = globe[::step, ::step].copy()
    else:
        base = np.where(land[::step, ::step, None], np.uint8((60, 80, 55)),
                        np.uint8((25, 40, 70))).astype(np.uint8)
    # Tint lakes so the ocean/lake distinction the flow model uses is visible.
    lake_s = lake[::step, ::step][:oh, :ow]
    base = base[:oh, :ow]
    base[lake_s] = (90, 140, 210)
    img = Image.fromarray(base, mode="RGB")
    draw = ImageDraw.Draw(img)

    def sc(x, y):
        return (x / step, y / step)

    for s in result.streams:
        col = _WIDTH_RGB.get(s.width, (0, 120, 255))
        pts = [sc(x, y) for (x, y) in s.points]
        if len(pts) >= 2:
            draw.line(pts, fill=col, width=1)
        # head marker: green dot = spring source, yellow dot = split distributary.
        # mouth marker: red = confluence, orange square = endorheic (dries up
        # inland), cyan = reaches water (sea or lake).
        sx, sy = pts[0]
        draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2],
                     fill=(255, 240, 0) if s.head == "split" else (0, 230, 0))
        mx, my = pts[-1]
        if s.mouth == "confluence":
            draw.ellipse([mx - 1, my - 1, mx + 1, my + 1], fill=(255, 40, 40))
        elif s.mouth == "endorheic":
            draw.rectangle([mx - 2, my - 2, mx + 2, my + 2], fill=(255, 150, 0))
        else:
            draw.ellipse([mx - 1, my - 1, mx + 1, my + 1], fill=(0, 255, 255))
        if not s.name.startswith("river_"):  # only real (named) rivers get a label
            draw.text((sx + 3, sy - 4), s.name, fill=(255, 255, 0))

    # Mark each blocking trace problem with a magenta ring + label, so the fixes
    # are locatable on the map.
    _ISSUE_ABBR = {"fork": "FORK", "cycle": "LOOP", "loop": "LOOP",
                   "stranded": "DRY", "no-source": "SRC", "too-short": "SHORT"}
    for i in result.issues:
        ix, iy = i["x"] / step, i["y"] / step
        draw.ellipse([ix - 5, iy - 5, ix + 5, iy + 5], outline=(255, 0, 255), width=2)
        draw.text((ix + 6, iy - 5), _ISSUE_ABBR.get(i["kind"], i["kind"].upper()),
                  fill=(255, 0, 255))

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out = DERIVED_DIR / "rivers_preview.png"
    img.save(str(out), format="PNG")
    print(f"wrote {out} ({ow}x{oh})  [{time.time() - t0:.1f}s]")
    if result.issues:
        print(f"  {len(result.issues)} blocking problem(s) marked:")
        for i in result.issues:
            print(f"    - {i['kind']} at (x={i['x']}, y={i['y']}): {i['detail']}")
    if result.unnamed:
        print(f"  {len(result.unnamed)} long unnamed stream(s) — consider naming them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
