#!/usr/bin/env python3
"""QA render: a human-legible view of the 16-bit heightmap.

``map_data/heightmap.png`` is a 16-bit grayscale image scaled so the whole
useful elevation range occupies a thin, dark slice of the 0..65535 code space
(sea level sits at 4884, the highest peak at ~48766). Opened in an ordinary
viewer it is a near-black rectangle — you cannot judge "mountains where the Old
World's mountains belong, coasts on the drawn shore, no stray land in open sea"
from it. This renders the same data the way an atlas would:

* **sea** shaded by depth      — light blue at the shore, deep navy in the abyss
* **land** shaded by elevation — green lowland, tan, brown, then rock and snow
* **relief** picked out by a hillshade so ranges read as ranges
* **coastline** stroked from the committed mask so the drawn shore is crisp

It writes ``mapgen/derived/preview_heightmap_hypso.png`` (gitignored, like every
other ``render_*.py`` output) for an accept/reject verdict; nothing is committed
here.

The heightmap and the land/sea mask are read directly. Per the QA-render
convention (see ``render_wind_patterns.py``) that is deliberate: a QA render is
evidence for a human, not pipeline input, so it lives outside the
``sources.py --verify`` manifest guard that owns integrity for anything that
ships. Deterministic: the tint ramps, the hillshade and the coast stroke are all
pure functions of the committed heightmap + mask — no RNG, no wall-clock.

Usage::

    python mapgen/render_heightmap_preview.py                 # 4096-wide review PNG
    python mapgen/render_heightmap_preview.py --full          # full 8192-wide canvas
    python mapgen/render_heightmap_preview.py --width 6144    # custom width
    python mapgen/render_heightmap_preview.py --z 0.08        # stronger relief
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None  # the heightmap is 16384x7232 = 118 Mpx, over PIL's default guard

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import raster  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_DIR = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
HEIGHTMAP_PATH = REPO_DIR / "map_data" / "heightmap.png"
OUT_DEFAULT = "preview_heightmap_hypso.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
HEIGHT_W, HEIGHT_H = map_config.HEIGHTMAP_SIZE

# --- hypsometric ramps ------------------------------------------------------
# Elevation (metres above sea level) -> land colour. Classic atlas hypsometry:
# green lowlands, yellow-tan plains, brown uplands, grey rock, white snow.
LAND_STOPS_M = np.array([0, 150, 400, 900, 1800, 3000, 4500, 6000], dtype=np.float32)
LAND_COLORS = np.array([
    (58, 122, 66),    # lowland green
    (104, 156, 82),   # green
    (172, 186, 108),  # yellow-green
    (200, 176, 120),  # tan
    (176, 138, 96),   # brown
    (138, 102, 76),   # dark brown
    (196, 188, 184),  # bare rock / pre-snow grey
    (250, 250, 252),  # snow
], dtype=np.float32)

# Depth below sea level (metres, 0 = shore) -> sea colour. Deep ocean in this
# encoding bottoms out near 888 m (stored 0), so the ramp is tuned to that band.
SEA_STOPS_M = np.array([0, 60, 200, 500, 900], dtype=np.float32)
SEA_COLORS = np.array([
    (150, 202, 232),  # shallow, light blue
    (96, 168, 216),
    (52, 118, 186),
    (28, 74, 148),
    (12, 40, 96),     # deep navy
], dtype=np.float32)

COAST_RGB = np.array([25, 28, 34], dtype=np.float32)  # dark coastline stroke


def _ramp(values: np.ndarray, stops: np.ndarray, colors: np.ndarray) -> np.ndarray:
    """Per-channel linear interpolation of ``values`` through a colour ramp."""
    out = np.empty(values.shape + (3,), dtype=np.float32)
    for c in range(3):
        out[..., c] = np.interp(values, stops, colors[:, c])
    return out


def hillshade(elev_m: np.ndarray, land: np.ndarray, *, azimuth: float,
              altitude: float, z: float) -> np.ndarray:
    """Standard analytical hillshade in ``[0, 1]`` over land, ``1.0`` over sea.

    ``z`` is a vertical exaggeration: metres of elevation are multiplied by it
    before the gradient, which sets how pronounced the relief reads. Sea gets a
    flat 1.0 so the depth tint is not darkened.
    """
    zf = elev_m * z
    dy, dx = np.gradient(zf)
    slope = np.pi / 2.0 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    az = np.radians(360.0 - azimuth + 90.0)
    alt = np.radians(altitude)
    sh = np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    sh = np.clip(sh, 0.0, 1.0)
    return np.where(land, sh, 1.0).astype(np.float32)


def block_average_rgb(rgb: np.ndarray, factor: int) -> np.ndarray:
    """Downscale an ``(H, W, 3)`` float image by an integer factor via averaging."""
    if factor <= 1:
        return rgb
    h, w = rgb.shape[:2]
    h2, w2 = h // factor, w // factor
    rgb = rgb[:h2 * factor, :w2 * factor]
    return rgb.reshape(h2, factor, w2, factor, 3).mean(axis=(1, 3))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--width", type=int, default=4096,
                   help="output width in px (height follows the 8192x3616 aspect); default 4096")
    p.add_argument("--full", action="store_true",
                   help="render at the full 8192-wide canvas (overrides --width)")
    p.add_argument("--z", type=float, default=0.06, help="relief vertical exaggeration (default 0.06)")
    p.add_argument("--azimuth", type=float, default=315.0, help="hillshade light azimuth deg (default 315 = NW)")
    p.add_argument("--altitude", type=float, default=45.0, help="hillshade light altitude deg (default 45)")
    p.add_argument("--out", default=OUT_DEFAULT, help=f"output filename under mapgen/derived/ (default {OUT_DEFAULT})")
    args = p.parse_args(argv)

    if not HEIGHTMAP_PATH.is_file():
        raise SystemExit(f"{HEIGHTMAP_PATH} not found (a committed map_data/ artifact)")
    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found (run generate_coastline_mask.py first)")

    with Image.open(HEIGHTMAP_PATH) as im:
        h16 = np.asarray(im, dtype=np.float32)
    if h16.shape != (HEIGHT_H, HEIGHT_W):
        raise SystemExit(f"heightmap is {h16.shape[1]}x{h16.shape[0]}, expected {HEIGHT_W}x{HEIGHT_H}")
    # The heightmap grid is exactly 2x the canvas: block-average 2x2 down to it.
    stored = h16.reshape(CANVAS_H, 2, CANVAS_W, 2).mean(axis=(1, 3))
    elev_m = (stored - map_config.HEIGHT_SEA_LEVEL) / map_config.HEIGHT_UNITS_PER_METRE

    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"mask is {land.shape[1]}x{land.shape[0]}, expected {CANVAS_W}x{CANVAS_H}")

    # Tint: land by elevation, sea by depth. Build both, then select on the mask.
    land_rgb = _ramp(np.clip(elev_m, 0.0, None), LAND_STOPS_M, LAND_COLORS)
    depth_m = np.clip(-elev_m, 0.0, None)
    sea_rgb = _ramp(depth_m, SEA_STOPS_M, SEA_COLORS)

    sh = hillshade(elev_m, land, azimuth=args.azimuth, altitude=args.altitude, z=args.z)
    # Keep colour readable: relief modulates brightness in a 0.55..1.0 band.
    land_rgb *= (0.55 + 0.45 * sh)[..., None]

    rgb = np.where(land[..., None], land_rgb, sea_rgb)

    factor = 1 if args.full else max(1, round(CANVAS_W / args.width))
    rgb = block_average_rgb(rgb, factor)
    out_h, out_w = rgb.shape[:2]

    # Coastline stroke, computed at the OUTPUT resolution off a nearest-downsampled
    # mask so it stays a crisp single line rather than an averaged smear.
    land_small = np.asarray(
        Image.fromarray(land.astype(np.uint8) * 255).resize((out_w, out_h), Image.NEAREST),
        dtype=bool,
    )
    edge = land_small ^ ndimage.binary_erosion(land_small, iterations=1)
    edge |= (~land_small) ^ ndimage.binary_erosion(~land_small, iterations=1)
    rgb[edge] = COAST_RGB

    out = np.clip(rgb, 0, 255).astype(np.uint8)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DERIVED_DIR / args.out
    Image.fromarray(out).save(out_path)

    # Report the same land-height stats the generator prints, for a text cross-check.
    land_h = stored[land]
    print(f"wrote {out_path} ({out_w}x{out_h})")
    print(f"  land elevation (m): median {np.median(elev_m[land]):.0f} "
          f"p95 {np.percentile(elev_m[land], 95):.0f} max {elev_m[land].max():.0f}")
    print(f"  land stored uint16: median {int(np.median(land_h))} "
          f"p95 {int(np.percentile(land_h, 95))} max {int(stored.max())}  "
          f"(vanilla: 5936 / 16742 / 53469)")
    print(f"  land fraction: {100 * land.mean():.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
