#!/usr/bin/env python3
"""QA render: the prevailing-wind belts of the Warhammer world, over the globe.

A look-and-check visualisation, nothing that ships. The premise (the user's) is
that the Warhammer Fantasy world is Earth-like in climate and has an Earth-like
moon, so its lower-atmosphere circulation is Earth's idealised **three-cell
model**: a fixed pattern of surface wind belts set by latitude alone. This drapes
that flow field over a copy of ``sources/terraqueous_globe_reprojected.png`` (the
canvas frame, 1:1) so the wind pattern can be judged by eye against the real
coastline, like a textbook "global wind patterns" arrow map does for Earth. It
writes ``scratchpad/wind_patterns_on_globe.png`` for an accept/reject verdict;
nothing is committed here.

Two stages compose the field:

1. **The zonal belt skeleton** (``wind_vector``). Every arrow's latitude comes
   from ``config.canvas_frame`` (the committed Miller calibration — canvas y maps
   to latitude in closed form), and its base direction from which of Earth's three
   surface belts that latitude falls in:

       |lat| band            surface wind blows...        arrow (screen)
       -----------------------------------------------------------------
        0-30  Trade winds     toward the equator, westward  down-/up-left
       30-60  Westerlies      toward the pole,   eastward    up-/down-right
       60-90  Polar easterlies toward the equator, westward  down-/up-left

   The meridional sign flips across the equator (the Coriolis deflection
   reverses), so the two trade belts converge on the equator (the doldrums / ITCZ)
   and the two westerly belts diverge from the horse latitudes at +-30. The canvas
   spans +74.9N to -57.4S, so the northern polar easterlies appear only in part
   and the southern polar band is off the bottom edge.

2. **A stylised terrain-deflection pass** (``terrain_gradient`` +  ``deflect``).
   The pure belt is continent-blind; real surface wind bends along coasts and
   skirts high ground. We approximate that (NOT a physical simulation) with an
   *obstacle-potential* field ``P`` = a smoothed land mask (which puts a gradient
   band across every shoreline) + smoothed, normalised elevation from the
   heightmap (a stronger barrier over mountains). Its gradient ``grad P`` points
   into rising terrain/land; at each arrow we remove the belt wind's component
   that blows *into* that barrier and renormalise, so the arrow rotates to run
   parallel to the coast / around the massif while keeping its length. Arrows over
   open ocean far from any coast keep the pure zonal direction (grad P ~ 0). Belt
   *colour* stays keyed to latitude — deflection is local, the belt identity is
   not. Disable with ``--no-deflect`` to see the bare zonal skeleton.

The backdrop, the land/sea mask and the heightmap are read directly (the globe and
mask outside the SHA-256 manifest guard — the accepted QA-render convention, see
``render_anchor_dot_example.py``; the heightmap is a committed ``map_data/`` artifact). A QA
render is evidence for a human, not pipeline input, and the offline gate
(``sources.py --verify``) still owns integrity for anything that ships.
Deterministic: the arrow grid is a fixed lattice, the belt directions are a pure
function of latitude, and the deflection is a pure function of the committed mask +
heightmap (Gaussian smoothing + finite-difference gradient, no RNG, no wall-clock).

Usage::

    python mapgen/render_wind_patterns.py
    python mapgen/render_wind_patterns.py --no-deflect          # bare zonal belts
    python mapgen/render_wind_patterns.py --gain 90 --spacing 280
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None  # the heightmap is 16384x7232 = 118 Mpx, over PIL's default guard

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
HEIGHTMAP_PATH = REPO_DIR / "map_data" / "heightmap.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: The reprojected globe that IS the canvas frame — the backdrop the winds drape over.
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"

OUT_DEFAULT = "wind_patterns_on_globe.png"

# --- belt palette (RGB) -----------------------------------------------------
# One colour per belt *type*, so the three-cell banding reads at a glance.
TRADES_RGB = (255, 176, 40)     # warm gold — the trade winds
WESTERLIES_RGB = (64, 205, 224)  # cyan — the westerlies
POLAR_RGB = (206, 130, 240)      # violet — the polar easterlies

OUTLINE_RGB = (20, 20, 26)       # dark rim, so arrows read over both ocean and land
BOUNDARY_RGB = (245, 245, 245)   # dashed belt-boundary latitude lines

BELTS = {
    "trades": ("Trade winds", TRADES_RGB),
    "westerlies": ("Westerlies", WESTERLIES_RGB),
    "polar": ("Polar easterlies", POLAR_RGB),
}

# --- terrain-deflection tuning ----------------------------------------------
#: Gaussian sigma (canvas px) that smears the binary land mask into a coastal
#: transition band — this is the width over which a coast bends the wind.
SIGMA_COAST = 30.0
#: Gaussian sigma (canvas px) applied to the normalised elevation barrier.
SIGMA_ELEV = 18.0
#: Relative weight of the coast barrier and the mountain barrier in ``P``.
W_LAND = 1.0
W_ELEV = 1.7
#: Elevation percentile (over land) mapped to barrier = 1.0; higher ground clips.
ELEV_PCTL = 98.0
#: |grad P| -> deflection fraction. Tuned so a typical coast gradient rotates the
#: wind most of the way parallel; scaled by ``--gain`` at the CLI.
DEFLECT_GAIN = 75.0
#: Cap on the removed-into-barrier fraction (1.0 = fully parallel).
BETA_MAX = 0.95


def log(msg: str) -> None:
    print(msg, flush=True)


def load_globe() -> np.ndarray:
    path = sources_mod.resolve_source_path(GLOBE_SOURCE, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{GLOBE_SOURCE} is missing")
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8).copy()
    if rgb.shape[0] != CANVAS_H or rgb.shape[1] != CANVAS_W:
        raise SystemExit(f"{GLOBE_SOURCE} is {rgb.shape[1]}x{rgb.shape[0]}, expected "
                         f"{CANVAS_W}x{CANVAS_H} (the canvas frame)")
    return rgb


def wind_vector(lat: float) -> tuple[str, float, float]:
    """Belt name and unit surface-wind direction (dx east+, dy south+) at ``lat``.

    Earth's idealised three-cell model. The zonal sign is set by the belt; the
    meridional sign by belt *and* hemisphere (Coriolis deflection reverses across
    the equator), so the two trade belts converge on the equator and the two
    westerly belts diverge from +-30.
    """
    a = abs(lat)
    if a < 30.0:
        belt, zonal, toward_equator = "trades", -1.0, True
    elif a < 60.0:
        belt, zonal, toward_equator = "westerlies", +1.0, False
    else:
        belt, zonal, toward_equator = "polar", -1.0, True

    # Northern hemisphere: the equator lies south (screen +y), the pole north (-y).
    if lat >= 0.0:
        merid = +1.0 if toward_equator else -1.0
    else:
        merid = -1.0 if toward_equator else +1.0

    norm = float(np.hypot(zonal, merid))
    return belt, zonal / norm, merid / norm


def terrain_gradient() -> tuple[np.ndarray, np.ndarray]:
    """Screen-space gradient (gx east+, gy south+) of the obstacle potential ``P``.

    ``P`` is high over land and higher over mountains, smoothed so the shoreline
    and the flanks of a massif carry a gradient the wind can be turned by. The
    return is the field the deflection samples; it is a pure function of the
    committed land mask + heightmap.
    """
    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run mapgen/generate_heightmap.py first")
    if not HEIGHTMAP_PATH.is_file():
        raise SystemExit(f"{HEIGHTMAP_PATH} not found (a committed map_data/ artifact)")

    land = raster.read_mask_png(MASK_PATH)  # bool (H, W) on the canvas frame
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"land mask is {land.shape[1]}x{land.shape[0]}, expected "
                         f"{CANVAS_W}x{CANVAS_H}")

    with Image.open(HEIGHTMAP_PATH) as im:
        h = np.asarray(im, dtype=np.float32)
    hh, hw = map_config.HEIGHTMAP_SIZE[1], map_config.HEIGHTMAP_SIZE[0]
    if h.shape != (hh, hw):
        raise SystemExit(f"heightmap is {h.shape[1]}x{h.shape[0]}, expected {hw}x{hh}")
    # The heightmap grid is exactly 2x the canvas: block-average 2x2 down to it.
    h = h.reshape(CANVAS_H, 2, CANVAS_W, 2).mean(axis=(1, 3))

    elev = np.clip(h - map_config.HEIGHT_SEA_LEVEL, 0.0, None)
    scale = float(np.percentile(elev[land], ELEV_PCTL)) if land.any() else 0.0
    elev = (elev / scale if scale > 0 else elev)
    elev = np.clip(elev, 0.0, 1.0) * land  # barrier only rises over land

    land_s = ndimage.gaussian_filter(land.astype(np.float32), SIGMA_COAST)
    elev_s = ndimage.gaussian_filter(elev.astype(np.float32), SIGMA_ELEV)
    potential = W_LAND * land_s + W_ELEV * elev_s

    gy, gx = np.gradient(potential)  # d/axis0 = south+ (y), d/axis1 = east+ (x)
    return gx.astype(np.float32), gy.astype(np.float32)


def deflect(dx: float, dy: float, gx: float, gy: float, gain: float) -> tuple[float, float]:
    """Rotate the belt wind (dx, dy) away from the barrier gradient (gx, gy).

    Removes the fraction of the wind blowing *into* rising terrain/land and
    renormalises, so it runs parallel to the obstacle. Winds blowing *away* from
    the barrier (offshore, downslope) are left alone.
    """
    gmag = float(np.hypot(gx, gy))
    if gmag < 1e-9:
        return dx, dy
    nx, ny = gx / gmag, gy / gmag
    proj = dx * nx + dy * ny
    if proj <= 0.0:
        return dx, dy  # already flowing off the barrier
    beta = min(BETA_MAX, gmag * gain)
    ux, uy = dx - beta * proj * nx, dy - beta * proj * ny
    m = float(np.hypot(ux, uy))
    if m < 1e-6:
        return dx, dy
    return ux / m, uy / m


def _font(size: int) -> ImageFont.ImageFont:
    """A TrueType face at ``size`` if the OS has one, else PIL's bitmap default."""
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_arrow(draw: ImageDraw.ImageDraw, cx: float, cy: float, dx: float, dy: float,
               length: float, color: tuple[int, int, int], alpha: int, width: int) -> None:
    """One centred arrow: dark rim first, bright core over it (legible on any pixel)."""
    half = length / 2.0
    tail = (cx - dx * half, cy - dy * half)
    head = (cx + dx * half, cy + dy * half)

    # Arrowhead triangle geometry (perpendicular to the shaft).
    hl, hw = length * 0.34, length * 0.20
    px, py = -dy, dx

    def head_tri(scale: float) -> list[tuple[float, float]]:
        b = (head[0] - dx * hl * scale, head[1] - dy * hl * scale)
        w = hw * scale
        return [head, (b[0] + px * w, b[1] + py * w), (b[0] - px * w, b[1] - py * w)]

    rim = OUTLINE_RGB + (alpha,)
    core = color + (alpha,)

    # Rim pass — wider shaft + enlarged head.
    draw.line([tail, head], fill=rim, width=width + 5)
    draw.polygon(head_tri(1.35), fill=rim)
    # Core pass.
    draw.line([tail, head], fill=core, width=width)
    draw.polygon(head_tri(1.0), fill=core)


def dashed_hline(draw: ImageDraw.ImageDraw, y: float, dash: int, gap: int,
                 color: tuple[int, int, int], alpha: int, width: int) -> None:
    x = 0
    fill = color + (alpha,)
    while x < CANVAS_W:
        draw.line([(x, y), (min(x + dash, CANVAS_W), y)], fill=fill, width=width)
        x += dash + gap


def draw_legend(draw: ImageDraw.ImageDraw, deflected: bool) -> None:
    """Belt key + title, bottom-left, on a translucent card."""
    pad = 40
    sw = 96          # swatch (arrow) length
    row_h = 130
    title_f = _font(96)
    label_f = _font(72)
    sub_f = _font(52)

    x0, y0 = 70, CANVAS_H - 70 - (row_h * 3 + 250)
    box_w, box_h = 1780, row_h * 3 + 250
    draw.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=32,
                           fill=(12, 14, 20, 205), outline=(230, 230, 235, 235), width=4)

    tx, ty = x0 + pad, y0 + pad
    draw.text((tx, ty), "Prevailing winds — Warhammer world", font=title_f,
              fill=(245, 245, 245, 255))
    sub = "Earth-like three-cell circulation" + (", deflected by terrain" if deflected
                                                 else ", by latitude")
    draw.text((tx, ty + 108), sub, font=sub_f, fill=(198, 200, 210, 255))

    # Direction shown by each swatch = the belt's northern-hemisphere arrow, taken
    # from a latitude inside that belt (15N trades, 45N westerlies, 70N polar).
    belt_lat = {"trades": 15.0, "westerlies": 45.0, "polar": 70.0}
    ry = ty + 210
    for belt, (label, rgb) in BELTS.items():
        _, dxn, dyn = wind_vector(belt_lat[belt])
        cx = tx + sw
        cy = ry + row_h // 2 - 20
        draw_arrow(draw, cx, cy, dxn, dyn, sw * 1.7, rgb, 255, 16)
        draw.text((tx + sw * 2 + 40, ry + 6), label, font=label_f, fill=rgb + (255,))
        ry += row_h


def build(spacing: int, length: float, opacity: float, use_deflect: bool,
          gain: float, out_file: str) -> Path:
    globe = load_globe()
    overlay = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    alpha = int(round(np.clip(opacity, 0.0, 1.0) * 255))

    gx = gy = None
    if use_deflect:
        log("building the terrain obstacle field (land mask + heightmap)…")
        gx, gy = terrain_gradient()

    # Belt-boundary latitude lines (dashed) + a margin label per boundary.
    lab_f = _font(58)
    for lat in (60.0, 30.0, 0.0, -30.0):
        _, y = cf.lonlat_to_canvas(0.0, lat)
        y = float(y)
        if 0.0 <= y < CANVAS_H:
            dashed_hline(draw, y, 90, 70, BOUNDARY_RGB, 150, 5)
            tag = "Equator" if lat == 0.0 else f"{abs(lat):.0f}°{'N' if lat > 0 else 'S'}"
            draw.text((CANVAS_W - 300, y - 74), tag, font=lab_f, fill=(245, 245, 245, 220))

    # The arrow lattice. Belt + colour from each cell's latitude; direction then
    # deflected by the local terrain gradient (when enabled).
    counts = {"trades": 0, "westerlies": 0, "polar": 0}
    deflected_n = 0
    ys = np.arange(spacing // 2, CANVAS_H, spacing)
    xs = np.arange(spacing // 2, CANVAS_W, spacing)
    # Brick offset every other row so the field doesn't read as a rigid grid.
    for i, y in enumerate(ys):
        _, lat = cf.canvas_to_lonlat(0.0, float(y))
        lat = float(lat)
        belt, base_dx, base_dy = wind_vector(lat)
        rgb = BELTS[belt][1]
        iy = int(min(CANVAS_H - 1, max(0, round(float(y)))))
        row_shift = (spacing // 2) if (i % 2) else 0
        for x in xs:
            xc = float(x) + row_shift
            if xc >= CANVAS_W:
                continue
            dx, dy = base_dx, base_dy
            if use_deflect:
                ix = int(min(CANVAS_W - 1, max(0, round(xc))))
                ndx, ndy = deflect(dx, dy, float(gx[iy, ix]), float(gy[iy, ix]), gain)
                if (ndx, ndy) != (dx, dy):
                    deflected_n += 1
                dx, dy = ndx, ndy
            draw_arrow(draw, xc, float(y), dx, dy, length, rgb, alpha, 12)
            counts[belt] += 1

    draw_legend(draw, use_deflect)

    out = Image.alpha_composite(Image.fromarray(globe, "RGB").convert("RGBA"), overlay)
    out = out.convert("RGB")

    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCRATCH_DIR / out_file
    out.save(out_path)
    total = sum(counts.values())
    log(f"arrows placed: {total}  "
        f"(trades {counts['trades']}, westerlies {counts['westerlies']}, "
        f"polar {counts['polar']})")
    if use_deflect:
        log(f"terrain-deflected {deflected_n} of {total} arrows "
            f"(gain {gain:.0f}); the rest sit over open ocean / flat land")
    log(f"wrote {out_path.relative_to(REPO_DIR)}  "
        f"(spacing {spacing}px, length {length:.0f}px, opacity {opacity}, "
        f"{'deflected' if use_deflect else 'zonal only'})")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spacing", type=int, default=320,
                   help="arrow grid spacing in canvas px (default 320)")
    p.add_argument("--length", type=float, default=190.0,
                   help="arrow length in canvas px (default 190)")
    p.add_argument("--opacity", type=float, default=0.9,
                   help="arrow blend strength over the globe (0..1, default 0.9)")
    p.add_argument("--no-deflect", action="store_true",
                   help="skip the terrain-deflection pass (bare zonal belts)")
    p.add_argument("--gain", type=float, default=DEFLECT_GAIN,
                   help=f"terrain-deflection strength (default {DEFLECT_GAIN:.0f})")
    p.add_argument("--out", default=OUT_DEFAULT,
                   help=f"output filename under scratchpad/ (default {OUT_DEFAULT})")
    args = p.parse_args(argv)

    build(args.spacing, args.length, args.opacity, not args.no_deflect,
          args.gain, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
