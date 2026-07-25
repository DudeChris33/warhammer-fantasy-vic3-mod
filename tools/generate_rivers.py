#!/usr/bin/env python3
"""S2 generator: the drainage network -> map_data/rivers.png.

Rivers are derived from the terrain, exactly as the relief is::

    map_data/heightmap.png  +  tools/derived/land_sea_mask.png
        -> fill depressions -> D8 flow direction -> flow accumulation   (hydro.py)
        -> channels (accum >= threshold), thinned to ~1 px
        -> flow-width ramp + green sources + red confluences
        -> map_data/rivers.png  (indexed, vanilla palette)

**Why derived rather than drawn.** Hand-placed polylines gave sparse, straight
lines that had no relationship to the valleys underneath them. A drainage network
computed from the committed heightmap meanders through the real terrain, joins
into dendritic basins, and reaches the coastline *by construction* — the mouths
cannot disagree with the shoreline, because the same land mask produced both. It
is also far denser, which is what a world map should look like.

**Canon naming** stays a later concern: the S6 pass identifies which of these
channels are the Reik, the Talabec, and so on, using the user's annotated Empire
map (`sources/TheEmpireRivers - drawn on.jpg`) as the guide for *which* channel
is which. Naming does not move any water — the geometry here is already correct
by construction, so identification is a labelling step, not a re-trace.

Usage::

    python tools/generate_rivers.py             # write map_data/rivers.png
    python tools/generate_rivers.py --preview    # + a downscaled overlay
    python tools/generate_rivers.py --threshold N  # tune network density
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

Image.MAX_IMAGE_PIXELS = None

from config import map_config  # noqa: E402
from worldgen import hydro, raster, rivers as riverlib  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MAP_DATA_DIR = REPO_ROOT / "map_data"
PALETTE_JSON = TOOLS_DIR / "lut" / "rivers_palette.json"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
HEIGHTMAP_PATH = MAP_DATA_DIR / "heightmap.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: The heightmap is 2x the canvas; hydrology runs on a block-mean downsample of
#: it at this factor *relative to the canvas*, then the network is scaled up.
#: Working coarse is deliberate, not just cheaper: flow routing on a
#: 16k x 7k grid produces hair-fine capillaries that vanish at map zoom, whereas
#: routing on a smoothed grid yields the trunk rivers a player actually sees.
HYDRO_DOWNSCALE = 4

#: Minimum upstream cell count for a cell to count as a channel, at working
#: resolution. Tuned on the real world: ~120 gives major rivers plus their main
#: tributaries without the network turning into a solid mat of capillaries.
DEFAULT_THRESHOLD = 120

#: Accumulation breakpoints (as a fraction of the max) for the vanilla width ramp.
#: Wider indices are for higher flow, so a trunk river renders broader than a
#: headwater stream, mirroring how vanilla draws its own rivers.
WIDTH_BREAKS = (0.0006, 0.004, 0.02)


def log(msg: str, t0: float | None = None) -> None:
    stamp = f"  [{time.time() - t0:5.1f}s]" if t0 is not None else ""
    print(f"{msg}{stamp}", flush=True)


def load_working_grids(step: int, t0: float):
    """Elevation (metres) + land mask at 1/``step`` of the canvas."""
    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"mask is {land.shape}, expected {(CANVAS_H, CANVAS_W)}")
    with Image.open(HEIGHTMAP_PATH) as im:
        h16 = np.asarray(im, dtype=np.uint16)
    log(f"  heightmap {h16.shape[1]}x{h16.shape[0]}, mask {CANVAS_W}x{CANVAS_H}", t0)

    metres = (h16.astype(np.float32) - map_config.HEIGHT_SEA_LEVEL) / map_config.HEIGHT_UNITS_PER_METRE
    # Heightmap is 2x canvas, so the block factor from heightmap to working grid.
    f = step * 2
    hh, ww = h16.shape[0] // f, h16.shape[1] // f
    elev = metres[:hh * f, :ww * f].reshape(hh, f, ww, f).mean(axis=(1, 3))

    # Land at working resolution comes from the *mask* (the authority on the
    # coastline), not from thresholding elevation — so channels can never drain
    # into a cell the province map will call land.
    lf = step
    land_w = land[:hh * lf, :ww * lf].reshape(hh, lf, ww, lf).mean(axis=(1, 3)) > 0.5
    return elev, land_w, land


def upscale_nearest(mask: np.ndarray, step: int, out_shape: tuple[int, int]) -> np.ndarray:
    big = np.repeat(np.repeat(mask, step, axis=0), step, axis=1)
    out = np.zeros(out_shape, dtype=mask.dtype)
    h = min(out_shape[0], big.shape[0])
    w = min(out_shape[1], big.shape[1])
    out[:h, :w] = big[:h, :w]
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--preview", action="store_true", help="also write a downscaled overlay")
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                   help=f"channel accumulation threshold (default {DEFAULT_THRESHOLD})")
    p.add_argument("--step", type=int, default=HYDRO_DOWNSCALE,
                   help=f"hydrology downscale vs the canvas (default {HYDRO_DOWNSCALE})")
    args = p.parse_args(argv)

    t0 = time.time()
    for path in (MASK_PATH, HEIGHTMAP_PATH):
        if not path.is_file():
            raise SystemExit(f"{path} not found — run tools/generate_heightmap.py first")

    log("loading terrain...")
    elev, land_w, land = load_working_grids(args.step, t0)
    log(f"  working grid {elev.shape[1]}x{elev.shape[0]}  land {100 * land_w.mean():.1f}%", t0)

    log("routing drainage (fill -> D8 -> accumulation)...")
    net = hydro.build_network(elev, land_w, args.threshold, wrap_x=map_config.WRAP_X)
    accum, channel = net["accum"], net["channel"]
    log(f"  max accumulation {int(accum.max())}; channel cells {int(channel.sum())} "
        f"({100 * channel.sum() / max(1, land_w.sum()):.2f}% of land)", t0)

    channel = hydro.thin_to_single_pixel(channel, accum, wrap_x=map_config.WRAP_X)
    log(f"  thinned to {int(channel.sum())} cells", t0)

    # --- to canvas resolution -------------------------------------------
    ch_canvas = upscale_nearest(channel, args.step, (CANVAS_H, CANVAS_W))
    ac_canvas = upscale_nearest(accum, args.step, (CANVAS_H, CANVAS_W))
    # A river must sit on land: the mask is the authority, and upscaling a coarse
    # cell can otherwise spill a channel one pixel past the true shoreline.
    ch_canvas &= land
    # Re-thin at canvas scale: the nearest upscale turns each cell into a step x
    # step block, which is emphatically not one pixel wide.
    ch_canvas = _skeletonize_channels(ch_canvas)
    ch_canvas &= land
    log(f"  canvas channels {int(ch_canvas.sum())} px", t0)

    # --- paint the indexed bitmap ---------------------------------------
    palette = riverlib.load_palette(PALETTE_JSON)
    idx = np.where(land, np.uint8(riverlib.LAND), np.uint8(riverlib.SEA))
    ramp = palette.width_ramp
    amax = float(ac_canvas.max()) or 1.0
    frac = ac_canvas.astype(np.float32) / amax
    for i, lo in enumerate(WIDTH_BREAKS):
        idx[ch_canvas & (frac >= lo)] = ramp[min(i + 1, len(ramp) - 1)]
    idx[ch_canvas & (frac < WIDTH_BREAKS[0])] = ramp[0]

    # Sources: the green pixel marking where each watercourse begins. Headwaters
    # are identified on the *working* grid from the flow directions (exact), then
    # each is placed on the nearest surviving canvas channel pixel — the thinning
    # above may have moved a cell by a pixel or two, and a source that misses the
    # network would be a watercourse the engine cannot follow.
    heads = hydro.headwaters(channel, net["direction"], wrap_x=map_config.WRAP_X)
    sources = _place_sources(heads, ch_canvas, args.step)
    idx[sources] = riverlib.SOURCE
    log(f"  {int(heads.sum())} headwaters -> {int(sources.sum())} source pixels placed", t0)

    n_blocks, run = riverlib.measure_2x2_blocks(idx, map_config.WRAP_X)
    log(f"  2x2 blocks {n_blocks} (longest run {run}); vanilla ships 21/5")

    MAP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = MAP_DATA_DIR / "rivers.png"
    riverlib.write_rivers_png(out, idx, palette)
    drawn = int((~np.isin(idx, [riverlib.LAND, riverlib.SEA])).sum())
    log(f"wrote {out}: {drawn} river px ({out.stat().st_size / 1024:.0f} KB)", t0)

    if args.preview:
        _write_preview(idx, palette, DERIVED_DIR / "preview_rivers.png")
    return 0


def _skeletonize_channels(mask: np.ndarray) -> np.ndarray:
    """Thin an upscaled channel mask back to ~1 px, preserving connectivity."""
    from skimage.morphology import skeletonize
    return skeletonize(mask)


def _place_sources(heads: np.ndarray, ch_canvas: np.ndarray, step: int) -> np.ndarray:
    """Put one source pixel on the canvas network for each working-grid headwater.

    A headwater cell maps to a ``step`` x ``step`` canvas block, but thinning may
    have left no channel pixel inside that exact block, so the search widens by a
    ring before giving up. Deterministic: blocks are visited in sorted order and
    the first channel pixel in raster order wins.
    """
    out = np.zeros_like(ch_canvas)
    h, w = ch_canvas.shape
    ys, xs = np.nonzero(heads)
    for cy, cx in sorted(zip(ys.tolist(), xs.tolist())):
        placed = False
        for pad in (0, step, 2 * step):
            y0 = max(0, cy * step - pad)
            y1 = min(h, (cy + 1) * step + pad)
            x0 = max(0, cx * step - pad)
            x1 = min(w, (cx + 1) * step + pad)
            sub = ch_canvas[y0:y1, x0:x1]
            if sub.any():
                sy, sx = np.argwhere(sub)[0]
                out[y0 + sy, x0 + sx] = True
                placed = True
                break
        if not placed:
            continue
    return out


def _write_preview(idx: np.ndarray, palette: riverlib.RiverPalette, path: Path,
                   step: int = 4) -> None:
    """Downscaled overlay. Channels are dilated so 1px rivers survive the shrink."""
    from scipy import ndimage
    river = ~np.isin(idx, [riverlib.LAND, riverlib.SEA])
    land = idx != riverlib.SEA
    riv_s = ndimage.maximum_filter(river, size=step)[::step, ::step]
    land_s = land[::step, ::step]
    rgb = np.zeros(land_s.shape + (3,), dtype=np.uint8)
    rgb[land_s] = (70, 95, 60)
    rgb[~land_s] = (25, 40, 75)
    rgb[riv_s] = (80, 190, 255)
    raster.write_rgb_png(path, rgb)
    print(f"  preview -> {path}")


if __name__ == "__main__":
    raise SystemExit(main())
