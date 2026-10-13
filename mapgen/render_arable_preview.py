#!/usr/bin/env python3
"""QA render: the arable-potential heatmap, cropland-style, over the globe.

Board #4921. A look-and-check visualisation of the committed
``mapgen/derived/arable_heatmap.png`` — the rendered artifact is the real
acceptance gate (per the "review renders go on the reprojected globe" rule and the
autonomy model's visual verdict). It drapes a smooth barren->dense-green cropland
choropleth over a copy of ``sources/terraqueous_globe_reprojected.png`` (the canvas
frame, 1:1), tinting **only passable land** and leaving water fully transparent
(post-scope panel must-fix) so the inherited coastline reads. Writes
``scratchpad/arable_on_globe.png`` for an accept/reject verdict; nothing here is
committed (dev-only, like ``render_wind_patterns.py`` / ``render_hubs_preview.py``,
so its output is gitignored and it is not on the offline gate).

Deterministic and source-dependent: it reads the committed raster + land mask and
the local globe (outside the SHA-256 manifest guard — the accepted QA-render
convention). The ramp endpoints and opacity are CLI-tunable (green-on-green is
low-contrast, so the low end is a warm tan, not green).

Land is tinted **opaque** by default (``--opacity 1.0``): a translucent tint let
the parchment's printed *land* labels bleed through the green as false low-arable
"gaps" (Chris's visual verdict). Water stays fully transparent either way, so the
globe's coastlines and ocean labels still orient the map. Lower ``--opacity`` to
see the land relief through the tint, at the cost of that label bleed.

Usage::

    python mapgen/render_arable_preview.py
    python mapgen/render_arable_preview.py --opacity 0.85      # translucent (labels bleed through)
    python mapgen/render_arable_preview.py --no-globe          # flat dark backdrop
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import canvas_frame as cf  # noqa: E402
from config import map_config  # noqa: E402
from worldgen import raster  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_DIR = TOOLS_DIR.parent
SOURCES_DIR = REPO_DIR / "sources"
DERIVED_DIR = TOOLS_DIR / "derived"
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"  # QA renders and previews; gitignored at the repo root
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
LAKE_MASK_PATH = DERIVED_DIR / "lake_mask.png"
ARABLE_PATH = DERIVED_DIR / "arable_heatmap.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
OUT_DEFAULT = "arable_on_globe.png"

#: Cropland ramp control stops (value in [0,1] -> RGB). Barren is a warm tan, not
#: green, so the low end stays legible against a green-tinted mid/high.
RAMP = [
    (0.00, (238, 232, 205)),   # barren — pale tan
    (0.20, (214, 214, 150)),   # sparse — khaki
    (0.45, (160, 196, 104)),   # moderate — yellow-green
    (0.70, (82, 158, 66)),     # rich — green
    (1.00, (18, 92, 40)),      # breadbasket — dark green
]


def log(msg: str) -> None:
    print(msg, flush=True)


def load_globe(use_globe: bool) -> np.ndarray:
    """The reprojected-globe backdrop (canvas frame), or a flat dark sheet."""
    if not use_globe:
        bg = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)
        bg[:] = (24, 28, 34)
        return bg
    path = sources_mod.resolve_source_path(GLOBE_SOURCE, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"{GLOBE_SOURCE} not found under sources/ — pass --no-globe "
                         "to render on a flat backdrop instead")
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8).copy()
    if rgb.shape[0] != CANVAS_H or rgb.shape[1] != CANVAS_W:
        raise SystemExit(f"{GLOBE_SOURCE} is {rgb.shape[1]}x{rgb.shape[0]}, expected "
                         f"{CANVAS_W}x{CANVAS_H} (the canvas frame)")
    return rgb


def ramp_rgb(value: np.ndarray) -> np.ndarray:
    """Vectorized piecewise-linear cropland ramp: ``(H, W)`` [0,1] -> ``(H, W, 3)``."""
    v = np.clip(value, 0.0, 1.0)
    out = np.zeros(v.shape + (3,), dtype=np.float32)
    for (lo, c_lo), (hi, c_hi) in zip(RAMP, RAMP[1:]):
        m = (v >= lo) & (v <= hi)
        if not m.any():
            continue
        t = ((v[m] - lo) / (hi - lo))[:, None]
        out[m] = np.asarray(c_lo, np.float32) * (1 - t) + np.asarray(c_hi, np.float32) * t
    return out


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_legend(draw: ImageDraw.ImageDraw) -> None:
    """Title + a cropland colourbar, bottom-left on a translucent card."""
    x0, y0 = 70, CANVAS_H - 70 - 430
    box_w, box_h = 1700, 430
    draw.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=32,
                           fill=(12, 14, 20, 205), outline=(230, 230, 235, 235), width=4)
    tx, ty = x0 + 40, y0 + 36
    draw.text((tx, ty), "Arable potential — Old World", font=_font(88),
              fill=(245, 245, 245, 255))
    draw.text((tx, ty + 104), "relative farming potential (proportions only, no game values)",
              font=_font(46), fill=(198, 200, 210, 255))
    # Colourbar.
    bar_x0, bar_x1 = tx, tx + box_w - 80
    bar_y0, bar_y1 = ty + 210, ty + 290
    for i in range(bar_x1 - bar_x0):
        v = i / max(bar_x1 - bar_x0 - 1, 1)
        c = tuple(int(round(x)) for x in ramp_rgb(np.array([[v]]))[0, 0])
        draw.line([(bar_x0 + i, bar_y0), (bar_x0 + i, bar_y1)], fill=c + (255,))
    draw.rectangle([bar_x0, bar_y0, bar_x1, bar_y1], outline=(230, 230, 235, 235), width=3)
    lf = _font(46)
    draw.text((bar_x0, bar_y1 + 14), "barren", font=lf, fill=(235, 235, 235, 255))
    draw.text((bar_x1 - 220, bar_y1 + 14), "breadbasket", font=lf, fill=(235, 235, 235, 255))


def build(use_globe: bool, opacity: float, out_file: str) -> Path:
    if not ARABLE_PATH.is_file():
        raise SystemExit(f"{ARABLE_PATH} not found — run mapgen/generate_arable_heatmap.py first")
    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run mapgen/generate_coastline_mask.py first")

    gray = raster.read_gray16_png(ARABLE_PATH)
    if gray.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"arable raster is {gray.shape}, expected {(CANVAS_H, CANVAS_W)}")
    field = gray.astype(np.float32) / 65535.0

    land = raster.read_mask_png(MASK_PATH)
    lake = (raster.read_mask_png(LAKE_MASK_PATH) if LAKE_MASK_PATH.is_file()
            else np.zeros_like(land))
    passable = land & (~lake)  # water/lake -> fully transparent

    globe = load_globe(use_globe)
    rgb = ramp_rgb(field).astype(np.uint8)
    a = int(round(np.clip(opacity, 0.0, 1.0) * 255))
    alpha = np.where(passable, a, 0).astype(np.uint8)
    tint = np.dstack([rgb, alpha])

    overlay = Image.fromarray(tint, "RGBA")
    draw = ImageDraw.Draw(overlay, "RGBA")
    # Belt-boundary latitude guides (context for the climate driver).
    for lat in (60.0, 30.0, 0.0, -30.0):
        _, y = cf.lonlat_to_canvas(0.0, lat)
        y = float(y)
        if 0.0 <= y < CANVAS_H:
            for x in range(0, CANVAS_W, 160):
                draw.line([(x, y), (min(x + 90, CANVAS_W), y)], fill=(245, 245, 245, 90), width=3)
            tag = "Equator" if lat == 0.0 else f"{abs(lat):.0f}°{'N' if lat > 0 else 'S'}"
            draw.text((CANVAS_W - 300, y - 70), tag, font=_font(54), fill=(245, 245, 245, 150))
    draw_legend(draw)

    out = Image.alpha_composite(Image.fromarray(globe, "RGB").convert("RGBA"), overlay).convert("RGB")
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCRATCH_DIR / out_file
    out.save(out_path)
    log(f"wrote {out_path.relative_to(REPO_DIR)}  (opacity {opacity}, "
        f"{'globe' if use_globe else 'flat'} backdrop, {int(passable.sum()):,} passable px tinted)")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--opacity", type=float, default=1.0,
                   help="land tint strength over the globe (0..1, default 1.0 = opaque, so "
                        "parchment land labels do not bleed through as false gaps)")
    p.add_argument("--no-globe", action="store_true",
                   help="render on a flat dark backdrop instead of the reprojected globe")
    p.add_argument("--out", default=OUT_DEFAULT,
                   help=f"output filename under scratchpad/ (default {OUT_DEFAULT})")
    args = p.parse_args(argv)
    build(not args.no_globe, args.opacity, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
