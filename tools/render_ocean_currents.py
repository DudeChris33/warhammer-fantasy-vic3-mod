#!/usr/bin/env python3
"""QA render: wind-driven surface ocean currents of the Warhammer world.

A look-and-check visualisation, nothing that ships. Companion to
``render_wind_patterns.py``: those arrows are the atmospheric three-cell winds;
*this* is the surface-ocean circulation those winds drive. On an Earth-like world
(the user's premise) the prevailing winds push the sea into great subtropical and
subpolar **gyres**, intensified against the western side of each basin (the Gulf
Stream / Kuroshio effect) and closed by the continents — exactly the picture a
textbook ocean-currents map shows. This renders that as evenly-spaced flowing
streamlines over the oceans of a clean flat basemap (green land, pale-blue sea),
and writes ``tools/derived/ocean_currents.png`` for an accept/reject verdict.

How the flow is derived (a stylised model, not a full ocean GCM, but the standard
one that yields this picture):

1. **Wind-stress curl forcing.** The three-cell winds give a zonal surface stress
   ``tau_x(lat)`` — easterly in the trades and polar belts, westerly in the
   mid-latitudes. Its meridional derivative (the curl) is what spins the gyres:
   anticyclonic subtropical gyres between the trades and westerlies, cyclonic
   subpolar gyres between the westerlies and the polar easterlies.

2. **Stommel gyre solve.** We solve the linear barotropic vorticity balance
   ``lap(psi) + gamma * d(psi)/dx = curl(tau)`` for a transport streamfunction
   ``psi`` on a coarse ocean grid, with ``psi = 0`` on every coast (each continent
   an internal boundary). The ``gamma * d/dx`` term is the beta-effect that
   crowds the return flow onto the western boundary — western intensification.
   The surface current is then ``(u, v) = (-d psi/dy, d psi/dx)``, which runs
   along the ``psi`` contours: closed gyres, correct rotation sense, zero flow
   through any coast.

3. **Circumpolar throughflow.** A streamfunction with ``psi = 0`` on all walls
   carries no net zonal transport, so the far-south open channel (which has no
   meridional barrier) gets an added eastward component south of the continents —
   the Antarctic-Circumpolar-Current analogue drawn as long zonal streamlines.

Then evenly-spaced streamlines (a simplified Jobard-Lefer seeding) are integrated
through ``(u, v)`` over the ocean only and drawn with periodic arrowheads.

Inputs are the committed land/sea mask (``tools/derived/land_sea_mask.png``, the
canvas-frame authority) and the ``config.canvas_frame`` latitude calibration; the
parchment globe is not used here (clean basemap). Deterministic: a fixed grid, a
linear solve, and deterministic seed ordering — no RNG, no wall-clock.

Usage::

    python tools/render_ocean_currents.py
    python tools/render_ocean_currents.py --debug-psi   # dump the streamfunction heatmap
    python tools/render_ocean_currents.py --sep 52 --gamma 0.22
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import canvas_frame as cf  # noqa: E402
from config import map_config  # noqa: E402
from worldgen import raster  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_DIR = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
OUT_DEFAULT = "ocean_currents.png"

# --- basemap palette (clean, like the reference ocean-currents map) ---------
OCEAN_RGB = (206, 227, 240)
LAND_RGB = (122, 184, 103)
COAST_RGB = (86, 138, 78)
FRAME_RGB = (30, 30, 34)
GRID_RGB = (150, 168, 180)
CURRENT_RGB = (58, 138, 210)
LABEL_RGB = (40, 44, 50)

# --- solver / streamline tuning ---------------------------------------------
SOLVE_DS = 20          # solve-grid downsample from canvas (8192/20 ~ 409 wide)
GAMMA = 0.22           # beta term: western-boundary intensification (grid units)
SMOOTH_CELLS = 2.2     # smooth psi within the ocean (solve cells) to merge tiny gyres
ACC_LAT = -42.0        # eastward circumpolar throughflow ramps in south of this
ACC_STRENGTH = 0.9     # its speed relative to the gyre field's typical speed
SEP = 58               # streamline separation seeding distance (canvas px)
TEST_FRAC = 0.42       # stop a line when nearer than SEP*TEST_FRAC to another
STEP = 7.0             # integration step (canvas px)
MAX_STEPS = 560        # per direction
MIN_LEN = 200.0        # drop streamlines shorter than this (canvas px)
TURN_LIMIT = 2.15 * np.pi  # stop after ~one closed loop, so gyres don't bullseye
ARROW_EVERY = 170.0    # arrowhead spacing along a streamline (canvas px)


def log(msg: str) -> None:
    print(msg, flush=True)


def load_land() -> np.ndarray:
    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first")
    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"land mask is {land.shape[1]}x{land.shape[0]}, expected "
                         f"{CANVAS_W}x{CANVAS_H}")
    return land


def wind_stress_curl(rows: int) -> np.ndarray:
    """curl(tau) per solve-grid row, from the three-cell zonal wind stress.

    tau_x(lat): easterly (-) in the trades and polar belts, westerly (+) in the
    mid-latitudes, tapering at the equator (ITCZ) and the poles. Returned as a
    per-row forcing broadcast across longitude (the stress is zonal, so the curl
    is -d tau_x/d lat).
    """
    # latitude at each solve-grid row centre
    ys_canvas = (np.arange(rows) + 0.5) * SOLVE_DS
    _, lat = cf.canvas_to_lonlat(np.zeros(rows), ys_canvas)
    lat = np.asarray(lat, dtype=np.float64)

    def tau_x(phi):
        a = np.abs(phi)
        # piecewise sign by belt with smooth magnitude; peaks mid-belt
        t = np.zeros_like(phi)
        trades = a < 30.0
        west = (a >= 30.0) & (a < 60.0)
        polar = a >= 60.0
        t[trades] = -np.sin(np.pi * a[trades] / 30.0)          # 0 at 0/30, -1 at 15
        t[west] = +np.sin(np.pi * (a[west] - 30.0) / 30.0)     # 0 at 30/60, +1 at 45
        t[polar] = -0.6 * np.sin(np.pi * np.clip(a[polar] - 60.0, 0, 30) / 30.0)
        return t

    tx = tau_x(lat)
    # curl = -d tau_x / d(canvas y); sign folds into the solve, magnitude is free
    curl = -np.gradient(tx)
    return curl.astype(np.float64)


def solve_streamfunction(land: np.ndarray, gamma: float) -> tuple[np.ndarray, np.ndarray]:
    """Stommel transport streamfunction psi on the coarse ocean grid.

    Returns (psi, ocean) on the solve grid. psi = 0 on land and off the y-edges.
    """
    # Downsample the mask: a solve cell is land if any of its canvas pixels are land
    # (keeps narrow straits closed rather than opening them).
    Hs, Ws = CANVAS_H // SOLVE_DS, CANVAS_W // SOLVE_DS
    land_s = land[:Hs * SOLVE_DS, :Ws * SOLVE_DS].reshape(Hs, SOLVE_DS, Ws, SOLVE_DS).any(axis=(1, 3))
    ocean = ~land_s

    uid = -np.ones((Hs, Ws), dtype=np.int64)
    uid[ocean] = np.arange(int(ocean.sum()))
    N = int(ocean.sum())

    curl = wind_stress_curl(Hs)
    rhs = np.zeros(N, dtype=np.float64)
    rhs[:] = curl[:, None].repeat(Ws, axis=1)[ocean]

    rows_i, cols_j = np.nonzero(ocean)
    cid = uid[rows_i, cols_j]

    data = [np.full(N, -4.0)]
    ri = [cid]
    ci = [cid]

    def add_neighbor(ni, nj, coeff):
        # ni, nj are neighbour indices (already wrapped/validated); valid where ocean
        valid = (ni >= 0) & (ni < Hs)
        nj_w = nj % Ws  # x wraps
        vi, vj = ni[valid], nj_w[valid]
        is_ocean = ocean[vi, vj]
        src = cid[valid][is_ocean]
        dst = uid[vi[is_ocean], vj[is_ocean]]
        c = np.full(dst.shape, coeff, dtype=np.float64)
        ri.append(src); ci.append(dst); data.append(c)

    add_neighbor(rows_i - 1, cols_j, 1.0)                 # north
    add_neighbor(rows_i + 1, cols_j, 1.0)                 # south
    add_neighbor(rows_i, cols_j + 1, 1.0 + gamma / 2.0)   # east
    add_neighbor(rows_i, cols_j - 1, 1.0 - gamma / 2.0)   # west

    A = sp.coo_matrix((np.concatenate(data), (np.concatenate(ri), np.concatenate(ci))),
                      shape=(N, N)).tocsr()
    log(f"solving Stommel gyres: {N:,} ocean cells on a {Ws}x{Hs} grid (gamma={gamma})")
    psi_vec = spla.spsolve(A, rhs)

    psi = np.zeros((Hs, Ws), dtype=np.float64)
    psi[ocean] = psi_vec
    return psi, ocean


def velocity_from_psi(psi: np.ndarray, ocean: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(u, v) = (-d psi/dy, d psi/dx) on the solve grid, plus circumpolar throughflow.

    psi is first smoothed *within the ocean* (normalised convolution, so coast
    zeros are not dragged in) to merge grid-scale noise into broad gyres — the
    difference between a clean big-gyre map and a field of tiny whirlpools.
    """
    if SMOOTH_CELLS > 0:
        m = ocean.astype(np.float64)
        num = ndimage.gaussian_filter(psi * m, SMOOTH_CELLS, mode=("nearest", "wrap"))
        den = ndimage.gaussian_filter(m, SMOOTH_CELLS, mode=("nearest", "wrap"))
        psi = np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0) * m

    dpsi_dy, dpsi_dx = np.gradient(psi)
    u = -dpsi_dy
    v = dpsi_dx

    # typical gyre speed, to scale the added circumpolar current
    spd = np.hypot(u, v)
    typ = float(np.percentile(spd[ocean], 75)) if ocean.any() else 1.0

    Hs = psi.shape[0]
    ys_canvas = (np.arange(Hs) + 0.5) * SOLVE_DS
    _, lat = cf.canvas_to_lonlat(np.zeros(Hs), ys_canvas)
    lat = np.asarray(lat)
    ramp = np.clip((ACC_LAT - lat) / 12.0, 0.0, 1.0)  # 0 north of ACC_LAT, 1 well south
    u = u + (ACC_STRENGTH * typ * ramp)[:, None]

    u = np.where(ocean, u, 0.0)
    v = np.where(ocean, v, 0.0)
    return u, v, typ


class Sampler:
    """Bilinear sampler of the solve-grid velocity in canvas coordinates."""

    def __init__(self, u: np.ndarray, v: np.ndarray, land: np.ndarray):
        self.u = u
        self.v = v
        self.land = land
        self.Hs, self.Ws = u.shape

    def dir_at(self, x: float, y: float) -> tuple[float, float] | None:
        if y < 0 or y >= CANVAS_H:
            return None
        xi = (x / SOLVE_DS) - 0.5
        yi = (y / SOLVE_DS) - 0.5
        x0 = int(np.floor(xi)); y0 = int(np.floor(yi))
        fx = xi - x0; fy = yi - y0
        x0 %= self.Ws; x1 = (x0 + 1) % self.Ws
        y0c = min(max(y0, 0), self.Hs - 1); y1c = min(max(y0 + 1, 0), self.Hs - 1)
        u = (self.u[y0c, x0] * (1 - fx) * (1 - fy) + self.u[y0c, x1] * fx * (1 - fy)
             + self.u[y1c, x0] * (1 - fx) * fy + self.u[y1c, x1] * fx * fy)
        v = (self.v[y0c, x0] * (1 - fx) * (1 - fy) + self.v[y0c, x1] * fx * (1 - fy)
             + self.v[y1c, x0] * (1 - fx) * fy + self.v[y1c, x1] * fx * fy)
        m = float(np.hypot(u, v))
        if m < 1e-9:
            return None
        return u / m, v / m

    def is_land(self, x: float, y: float) -> bool:
        ix = int(x) % CANVAS_W
        iy = int(min(max(y, 0), CANVAS_H - 1))
        return bool(self.land[iy, ix])


def integrate(sampler: Sampler, sx: float, sy: float, occ: np.ndarray, ocw: int,
              line_id: int) -> list[tuple[float, float]]:
    """Integrate a streamline through the field, forward then backward from (sx, sy)."""
    def march(sign: float) -> list[tuple[float, float]]:
        pts: list[tuple[float, float]] = []
        x, y = sx, sy
        turn = 0.0
        prev: tuple[float, float] | None = None
        for _ in range(MAX_STEPS):
            d = sampler.dir_at(x, y)
            if d is None:
                break
            dx, dy = d[0] * sign, d[1] * sign
            # RK2 midpoint
            xm, ym = x + dx * STEP * 0.5, y + dy * STEP * 0.5
            dm = sampler.dir_at(xm, ym)
            if dm is None:
                break
            dx, dy = dm[0] * sign, dm[1] * sign
            if prev is not None:
                turn += abs(np.arctan2(prev[0] * dy - prev[1] * dx,
                                       prev[0] * dx + prev[1] * dy))
                if turn > TURN_LIMIT:  # completed roughly one loop — stop bullseyeing
                    break
            prev = (dx, dy)
            x, y = x + dx * STEP, y + dy * STEP
            x %= CANVAS_W
            if y < 0 or y >= CANVAS_H or sampler.is_land(x, y):
                break
            cx, cy = int(x) // ocw, int(y) // ocw
            other = occ[cy, cx]
            if other != 0 and other != line_id:
                break
            pts.append((x, y))
        return pts

    fwd = march(+1.0)
    bwd = march(-1.0)
    return list(reversed(bwd)) + [(sx, sy)] + fwd


def stamp(occ: np.ndarray, ocw: int, pts: list[tuple[float, float]], line_id: int) -> None:
    for (x, y) in pts:
        occ[int(y) // ocw, int(x) // ocw] = line_id


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_streamline(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]],
                    width: int) -> None:
    # Split on x-wrap seams so the polyline doesn't shoot across the map.
    seg: list[tuple[float, float]] = [pts[0]]
    arc = 0.0
    next_arrow = ARROW_EVERY
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        if abs(x1 - x0) > CANVAS_W / 2:  # wrapped this step
            if len(seg) > 1:
                draw.line(seg, fill=CURRENT_RGB, width=width, joint="curve")
            seg = [(x1, y1)]
            continue
        seg.append((x1, y1))
        d = float(np.hypot(x1 - x0, y1 - y0))
        arc += d
        if arc >= next_arrow and d > 1e-6:
            ux, uy = (x1 - x0) / d, (y1 - y0) / d
            _arrowhead(draw, x1, y1, ux, uy, width)
            next_arrow += ARROW_EVERY
    if len(seg) > 1:
        draw.line(seg, fill=CURRENT_RGB, width=width, joint="curve")


def _arrowhead(draw: ImageDraw.ImageDraw, x: float, y: float, ux: float, uy: float,
               width: int) -> None:
    hl = width * 3.2
    hw = width * 2.0
    px, py = -uy, ux
    bx, by = x - ux * hl, y - uy * hl
    draw.polygon([(x, y), (bx + px * hw, by + py * hw), (bx - px * hw, by - py * hw)],
                 fill=CURRENT_RGB)


def build_basemap(land: np.ndarray) -> Image.Image:
    rgb = np.empty((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)
    rgb[land] = LAND_RGB
    rgb[~land] = OCEAN_RGB
    # thin coast line: land pixels adjacent to ocean
    er = ndimage.binary_erosion(land, iterations=2, border_value=1)
    coast = land & ~er
    rgb[coast] = COAST_RGB
    return Image.fromarray(rgb, "RGB")


def draw_graticule(draw: ImageDraw.ImageDraw) -> None:
    f = _font(60)
    for lat in (60.0, 30.0, 0.0, -30.0):
        _, y = cf.lonlat_to_canvas(0.0, lat)
        y = float(y)
        if 0 <= y < CANVAS_H:
            for x in range(0, CANVAS_W, 46):
                draw.line([(x, y), (min(x + 24, CANVAS_W), y)], fill=GRID_RGB, width=3)
            tag = "Equator" if lat == 0.0 else f"{abs(lat):.0f}°{'N' if lat > 0 else 'S'}"
            draw.text((CANVAS_W - 300, y - 70), tag, font=f, fill=LABEL_RGB)
    draw.rectangle([2, 2, CANVAS_W - 3, CANVAS_H - 3], outline=FRAME_RGB, width=6)


def build(sep: int, gamma: float, out_file: str, debug_psi: bool) -> Path:
    land = load_land()
    psi, ocean = solve_streamfunction(land, gamma)

    if debug_psi:
        p = psi.copy()
        lim = np.percentile(np.abs(p[ocean]), 99) or 1.0
        norm = np.clip(p / lim, -1, 1)
        img = np.zeros((*psi.shape, 3), dtype=np.uint8)
        img[..., 0] = np.uint8(np.clip(norm, 0, 1) * 255)      # red = positive psi
        img[..., 2] = np.uint8(np.clip(-norm, 0, 1) * 255)     # blue = negative psi
        img[~ocean] = (30, 40, 30)
        out = DERIVED_DIR / "ocean_currents_psi.png"
        Image.fromarray(img, "RGB").resize((CANVAS_W // 4, CANVAS_H // 4),
                                           Image.NEAREST).save(out)
        log(f"wrote {out.relative_to(REPO_DIR)} (streamfunction debug; red +psi / blue -psi)")

    u, v, typ = velocity_from_psi(psi, ocean)
    sampler = Sampler(u, v, land)

    base = build_basemap(land)
    draw = ImageDraw.Draw(base, "RGB")

    # Evenly-spaced streamlines: deterministic seed lattice over ocean, occupancy-gated.
    ocw = max(4, int(sep * TEST_FRAC))
    occ = np.zeros((CANVAS_H // ocw + 1, CANVAS_W // ocw + 1), dtype=np.int64)
    width = 5
    line_id = 0
    drawn = 0
    seeds_x = np.arange(sep // 2, CANVAS_W, sep)
    seeds_y = np.arange(sep // 2, CANVAS_H, sep)
    for sy in seeds_y:
        for sx in seeds_x:
            if sampler.is_land(sx, sy):
                continue
            if occ[int(sy) // ocw, int(sx) // ocw] != 0:
                continue
            line_id += 1
            pts = integrate(sampler, float(sx), float(sy), occ, ocw, line_id)
            # arclength
            if len(pts) < 2:
                continue
            arc = float(np.sum(np.hypot(np.diff([p[0] for p in pts]),
                                        np.diff([p[1] for p in pts]))))
            if arc < MIN_LEN:
                continue
            stamp(occ, ocw, pts, line_id)
            draw_streamline(draw, pts, width)
            drawn += 1

    draw_graticule(draw)

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DERIVED_DIR / out_file
    base.save(out_path)
    log(f"drew {drawn} streamlines (sep {sep}px)")
    log(f"wrote {out_path.relative_to(REPO_DIR)}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sep", type=int, default=SEP, help=f"streamline spacing (default {SEP})")
    p.add_argument("--gamma", type=float, default=GAMMA,
                   help=f"western-boundary intensification (default {GAMMA})")
    p.add_argument("--debug-psi", action="store_true",
                   help="also dump the streamfunction heatmap to verify the gyres")
    p.add_argument("--out", default=OUT_DEFAULT,
                   help=f"output filename under tools/derived/ (default {OUT_DEFAULT})")
    args = p.parse_args(argv)
    build(args.sep, args.gamma, args.out, args.debug_psi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
