#!/usr/bin/env python3
"""PROTOTYPE (approach B): sea zones strung ALONG the ocean currents.

Parallel exploration — not the committed sea system, commits nothing, touches no
map bitmap. Companion to ``render_sea_zones_currents.py`` (approach A).

The design rule (the user's): in Victoria 3, navies and ocean trade travel from
the *centre* of one sea zone to the centre of the next along a fairly direct path,
and that path must lie on **the easily traversible part of the sea — the strong,
straight current arrows**. So a zone centre belongs ON a current highway, not on a
gyre eye: the eye is stagnant, tightly-circling water (the hardest to cross), and
belongs on a zone *boundary*. Consecutive zone centres should be strung along a
current so the straight centre-to-centre hop runs downstream along the arrows.

This builds exactly that, from the circulation solved by ``render_ocean_currents``:

1. Solve the Stommel streamfunction ``psi`` and its surface velocity ``(u, v)``
   (both reused verbatim from ``render_ocean_currents``).
2. Integrate the **current streamlines** (the same evenly-spaced set the currents
   render draws) — the arrows themselves.
3. **Seed zone centres along those streamlines** at a fixed arc-length spacing,
   skipping stagnant water, and thinned to a minimum separation. Centres therefore
   sit on the fast straight currents, and two centres a step apart on the same
   streamline are joined by a straight downstream arrow. Gyre eyes and stagnation
   lines — where no streamline threads through — fall between zones, on the
   boundaries, exactly as the rule wants.
4. Split the water into **main ocean** (partitioned) and small **inland seas**
   (excluded, not counted); tiny coastal specks are folded in.
5. **Geodesic (in-water) Voronoi** from the streamline seeds (8-connected BFS,
   wrap-aware): every ocean cell takes the nearest seed *through water only*, so no
   zone reaches across land and adjacency follows the coast.

The review render overlays the current streamlines and draws a link between every
pair of adjacent zone centres, so you can check directly that the centre-to-centre
links ride the arrows rather than cutting across them.

Deterministic: linear solve + deterministic streamline seeding + BFS with
index-ordered tie breaks — no RNG, no wall-clock. Writes a PNG to ``scratchpad/``.

Usage::

    python mapgen/render_sea_zones_gyres.py                       # streamline-seeded zones
    python mapgen/render_sea_zones_gyres.py --spacing 260 --min-dist 190   # more, tighter zones
    python mapgen/render_sea_zones_gyres.py --no-currents         # hide the streamline overlay
    python mapgen/render_sea_zones_gyres.py --full                # full 8192x3616 render
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_ocean_currents as oc  # noqa: E402  (reuse the physics + streamlines + basemap)
from worldgen import cells  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

DERIVED_DIR = oc.DERIVED_DIR
SCRATCH_DIR = oc.SCRATCH_DIR
REPO_DIR = oc.REPO_DIR
CANVAS_W, CANVAS_H = oc.CANVAS_W, oc.CANVAS_H
DS = oc.SOLVE_DS
WRAP_X = True

OCEAN_MIN = 300       # a connected water body >= this many coarse cells is open ocean
INLAND_MIN = 40       # [INLAND_MIN, OCEAN_MIN) coarse cells => a real inland sea (excluded)
STREAM_SEP = 88       # streamline seeding lattice spacing (canvas px) — the arrow density
SPACING = 460         # seed every this many px of arc length along a streamline
MIN_DIST = 520        # thin seeds to at least this separation (canvas px)
ANISO_K = 4.0         # anisotropy: an along-flow step costs up to (1+K)x an across one
ANISO_P = 2.0         # sharpness of the along/across penalty on |cos(step, flow)|
SPEED_FRAC = 0.30     # seed only where speed >= this * ocean 75th-pct (skip stagnant eyes)


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


# --------------------------------------------------------------------------- #
# Geodesic (in-water) multi-source BFS                                         #
# --------------------------------------------------------------------------- #
def _shift(lab: np.ndarray, di: int, dj: int, wrap_x: bool) -> np.ndarray:
    """``out[i, j] = lab[i + di, j + dj]`` — the neighbour at offset (di, dj) as
    seen from each cell. x wraps (``wrap_x``); y is bounded (off-edge reads 0)."""
    if wrap_x:
        x = np.roll(lab, -dj, axis=1)
    elif dj == 0:
        x = lab
    else:
        x = np.zeros_like(lab)
        if dj > 0:
            x[:, :-dj] = lab[:, dj:]
        else:
            x[:, -dj:] = lab[:, :dj]
    if di == 0:
        return x
    out = np.zeros_like(x)
    if di > 0:
        out[:-di, :] = x[di:, :]
    else:
        out[-di:, :] = x[:di, :]
    return out


_OFFSETS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def _neighbour_labels(lab: np.ndarray, wrap_x: bool):
    return [_shift(lab, di, dj, wrap_x) for di, dj in _OFFSETS]


def geodesic_labels(seed_ij: np.ndarray, ocean: np.ndarray, wrap_x: bool = True):
    """Nearest-seed label + hop distance through ``ocean`` only (8-connected).

    ``seed_ij`` is a (k, 2) int array of (row, col) seed cells; label ``m`` is the
    1-based index of seed ``m-1``. Ties resolve to the smallest seed index, so the
    partition is a deterministic function of the seed order.
    """
    lab = np.zeros(ocean.shape, dtype=np.int32)
    dist = np.full(ocean.shape, -1, dtype=np.int32)
    ids = np.arange(1, len(seed_ij) + 1, dtype=np.int32)
    lab[seed_ij[:, 0], seed_ij[:, 1]] = ids
    dist[seed_ij[:, 0], seed_ij[:, 1]] = 0
    frontier = lab > 0
    cur = 0
    while frontier.any():
        cur += 1
        labf = np.where(frontier, lab, 0)
        cand = ocean & (lab == 0)
        incoming = np.zeros(lab.shape, dtype=bool)
        choice = np.full(lab.shape, np.iinfo(np.int32).max, dtype=np.int32)
        for n in _neighbour_labels(labf, wrap_x):
            has = n > 0
            incoming |= has
            take = cand & has & (n < choice)
            choice = np.where(take, n, choice)
        cand = cand & incoming
        if not cand.any():
            break
        lab[cand] = choice[cand]
        dist[cand] = cur
        frontier = cand
    return lab, dist


# --------------------------------------------------------------------------- #
# Anisotropic flow metric: cheap ACROSS the current, expensive ALONG it        #
# --------------------------------------------------------------------------- #
class FlowMetric:
    """A geodesic graph over the coarse ocean whose edges cost more when the step
    runs ALONG the local current and less when it cuts ACROSS.

    Distance is therefore short across streamlines and long along them, so a
    nearest-seed (Voronoi) partition makes zones **short beads along each current,
    wide across it**: consecutive beads down a current are adjacent, and the
    straight centre-to-centre hop rides the arrow, while the slow gyre eyes and
    stagnation lines — where the metric is isotropic and every seed is far — fall
    on the boundaries between beads. (The inverse of penalising across-flow, which
    would stretch zones into arcs and route hops across the current.) A pure
    function of (u, v); undirected, symmetric, no RNG.
    """

    def __init__(self, main_ocean: np.ndarray, u: np.ndarray, v: np.ndarray,
                 k: float, p: float, wrap_x: bool = True):
        import scipy.sparse as sp
        H, W = main_ocean.shape
        nid = np.full((H, W), -1, dtype=np.int64)
        nid[main_ocean] = np.arange(int(main_ocean.sum()))
        self.nid = nid
        self.n = int(main_ocean.sum())

        mag = np.hypot(u, v)
        eps = 1e-9
        fx = np.where(mag > eps, u / (mag + eps), 0.0)
        fy = np.where(mag > eps, v / (mag + eps), 0.0)
        has = mag > eps

        src, dst, wgt = [], [], []
        for di, dj in _OFFSETS:
            nb = _shift(main_ocean.astype(np.int8), di, dj, wrap_x) > 0
            mask = main_ocean & nb
            if not mask.any():
                continue
            fxm = 0.5 * (fx + _shift(fx, di, dj, wrap_x))
            fym = 0.5 * (fy + _shift(fy, di, dj, wrap_x))
            L = float(np.hypot(di, dj))
            # |cos| between the step (dj, di) and the mean flow: 1 = along, 0 = across
            along = np.abs(dj * fxm + di * fym) / L
            fm = np.hypot(fxm, fym)
            along = np.where(fm > eps, np.clip(along / (fm + eps), 0.0, 1.0), 0.0)
            both = has & _shift(has.astype(np.int8), di, dj, wrap_x).astype(bool)
            w = L * (1.0 + k * np.where(both, along ** p, 0.0))
            src.append(nid[mask])
            dst.append(_shift(nid, di, dj, wrap_x)[mask])
            wgt.append(w[mask])
        self.G = sp.csr_matrix((np.concatenate(wgt).astype(np.float64),
                                (np.concatenate(src), np.concatenate(dst))),
                               shape=(self.n, self.n))

    def labels(self, seed_ij: np.ndarray) -> np.ndarray:
        """Coarse label grid (0 off the main ocean, 1..k per seed) by nearest seed
        in the anisotropic metric."""
        from scipy.sparse.csgraph import dijkstra
        seed_nodes = self.nid[seed_ij[:, 0], seed_ij[:, 1]]
        _dist, _pred, sources = dijkstra(self.G, directed=False, indices=seed_nodes,
                                         min_only=True, return_predecessors=True)
        node_to_seed = {int(sn): m + 1 for m, sn in enumerate(seed_nodes)}
        lab = np.zeros(self.nid.shape, dtype=np.int32)
        oc_cells = self.nid >= 0
        flat_nid = self.nid[oc_cells]
        src_of = sources[flat_nid]
        out = np.array([node_to_seed.get(int(s), 0) for s in src_of], dtype=np.int32)
        lab[oc_cells] = out
        return lab


# --------------------------------------------------------------------------- #
# Streamlines and along-flow seeding                                          #
# --------------------------------------------------------------------------- #
def integrate_streamlines(sampler: "oc.Sampler", sep: int) -> list[list[tuple[float, float]]]:
    """The evenly-spaced current streamlines (same seeding idiom as the currents
    render): the arrows the zone centres will be strung along."""
    ocw = max(4, int(sep * oc.TEST_FRAC))
    occ = np.zeros((CANVAS_H // ocw + 1, CANVAS_W // ocw + 1), dtype=np.int64)
    lines: list[list[tuple[float, float]]] = []
    line_id = 0
    for sy in range(sep // 2, CANVAS_H, sep):
        for sx in range(sep // 2, CANVAS_W, sep):
            if sampler.is_land(sx, sy) or occ[int(sy) // ocw, int(sx) // ocw] != 0:
                continue
            line_id += 1
            pts = oc.integrate(sampler, float(sx), float(sy), occ, ocw, line_id)
            if len(pts) < 2:
                continue
            arc = float(np.sum(np.hypot(np.diff([p[0] for p in pts]),
                                        np.diff([p[1] for p in pts]))))
            if arc < oc.MIN_LEN:
                continue
            oc.stamp(occ, ocw, pts, line_id)
            lines.append(pts)
    return lines


def _wrapped_d2(x0, y0, x1, y1):
    dx = abs(x0 - x1)
    dx = min(dx, CANVAS_W - dx)
    dy = y0 - y1
    return dx * dx + dy * dy


def seeds_along_flow(lines, spacing: float, min_dist: float, main_ocean: np.ndarray,
                     spd: np.ndarray | None = None, spd_thr: float = 0.0):
    """Drop a seed every ``spacing`` px of arc length along each streamline, kept
    to the main ocean (and to cells whose current speed clears ``spd_thr`` — so
    seeds land on fast flow, not stagnant eyes) and thinned to ``min_dist``
    separation (a greedy Poisson filter over a wrap-aware spatial hash). Returns
    canvas (x, y) seed points."""
    cell = max(1.0, min_dist)
    ncx = int(CANVAS_W // cell) + 1
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    md2 = min_dist * min_dist
    accepted: list[tuple[float, float]] = []

    def in_main(x, y):
        i = min(int(y) // DS, main_ocean.shape[0] - 1)
        j = min(int(x) // DS, main_ocean.shape[1] - 1)
        if not main_ocean[i, j]:
            return False
        return spd is None or spd[i, j] >= spd_thr

    def ok(x, y):
        cx, cy = int(x // cell), int(y // cell)
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for (px, py) in grid.get((gx % ncx, gy), ()):  # x bucket wraps
                    if _wrapped_d2(x, y, px, py) < md2:
                        return False
        return True

    def add(x, y):
        cx, cy = int(x // cell), int(y // cell)
        grid.setdefault((cx % ncx, cy), []).append((x, y))
        accepted.append((x, y))

    for pts in lines:
        acc = spacing  # emit at the first eligible vertex, then every `spacing`
        prev = None
        for (x, y) in pts:
            if prev is not None:
                acc += float(np.hypot(x - prev[0], y - prev[1]))
            prev = (x, y)
            if acc >= spacing and in_main(x, y) and ok(x, y):
                add(x, y)
                acc = 0.0
    return accepted


def _to_cells(seeds_xy, main_ocean: np.ndarray) -> np.ndarray:
    """Canvas seed points -> unique coarse (row, col) cells inside the main ocean."""
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    H, W = main_ocean.shape
    for (x, y) in seeds_xy:
        i = min(int(y) // DS, H - 1)
        j = min(int(x) // DS, W - 1)
        if not main_ocean[i, j] or (i, j) in seen:
            continue
        seen.add((i, j))
        out.append((i, j))
    return np.array(out, dtype=np.int64)


# --------------------------------------------------------------------------- #
# Build                                                                        #
# --------------------------------------------------------------------------- #
def build(spacing: float, min_dist: float, stream_sep: int, k: float, p: float,
          speed_frac: float, show_currents: bool, full: bool, out_file: str) -> Path:
    t0 = time.time()
    land = oc.load_land()
    log(f"land mask {land.shape}, land {100 * land.mean():.1f}%", t0)

    psi, ocean = oc.solve_streamfunction(land, oc.GAMMA)
    u, v, _typ = oc.velocity_from_psi(psi, ocean)
    spd = np.hypot(u, v)
    log(f"solved streamfunction + velocity, {int(ocean.sum()):,} ocean cells", t0)

    comp = cells.components(ocean.astype(np.int32), WRAP_X)
    areas = np.bincount(comp.ravel())
    a_comp = areas[comp]
    main_ocean = ocean & (a_comp >= OCEAN_MIN)
    inland = ocean & (a_comp >= INLAND_MIN) & (a_comp < OCEAN_MIN)
    n_inland = int(len({int(c) for c in np.unique(comp[inland]) if c}))
    log(f"main ocean {int(main_ocean.sum()):,} cells; {n_inland} inland seas excluded; "
        f"{int((ocean & (a_comp < INLAND_MIN)).sum())} speck cells folded", t0)

    sampler = oc.Sampler(u, v, land)
    lines = integrate_streamlines(sampler, stream_sep)
    log(f"integrated {len(lines)} current streamlines (sep {stream_sep}px)", t0)

    spd_thr = speed_frac * float(np.percentile(spd[main_ocean], 75)) if main_ocean.any() else 0.0
    seeds_xy = seeds_along_flow(lines, spacing, min_dist, main_ocean, spd, spd_thr)
    seed_ij = _to_cells(seeds_xy, main_ocean)
    # guarantee every main body has at least one seed
    seeded = {int(comp[i, j]) for (i, j) in seed_ij}
    extra = []
    for c in np.unique(comp[main_ocean]):
        if int(c) not in seeded:
            ys, xs = np.nonzero(comp == c)
            k = len(ys) // 2
            extra.append((int(ys[k]), int(xs[k])))
    if extra:
        seed_ij = np.vstack([seed_ij, extra]) if len(seed_ij) else np.array(extra, np.int64)
    n = len(seed_ij)
    log(f"{n} zone centres on the currents "
        f"(spacing {spacing:.0f}px, min-dist {min_dist:.0f}px, speed-gate {speed_frac:.2f})", t0)

    log(f"partitioning in the anisotropic flow metric (k={k}, p={p}) ...", t0)
    lab = FlowMetric(main_ocean, u, v, k, p, WRAP_X).labels(seed_ij)

    coarse = lab.copy()
    excluded: set[int] = set()
    nxt = n + 1
    for c in np.unique(comp[inland]):
        if not c:
            continue
        coarse[comp == c] = nxt
        excluded.add(nxt)
        nxt += 1
    log(f"{n} currents zones + {len(excluded)} inland seas", t0)

    render(land, coarse, seed_ij, excluded, n, lines if show_currents else None,
           full, out_file, t0)
    return SCRATCH_DIR / out_file


# --------------------------------------------------------------------------- #
# Render                                                                       #
# --------------------------------------------------------------------------- #
def _palette(n: int) -> np.ndarray:
    import colorsys
    cols = np.zeros((n + 1, 3), dtype=np.uint8)
    for i in range(1, n + 1):
        h = (i * 0.61803398875) % 1.0
        s = 0.40 + 0.20 * ((i * 7) % 3) / 2.0
        val = 0.92 - 0.14 * ((i * 5) % 2)
        r, g, b = colorsys.hsv_to_rgb(h, s, val)
        cols[i] = (int(r * 255), int(g * 255), int(b * 255))
    return cols


def _upsample_labels(coarse: np.ndarray, land: np.ndarray) -> np.ndarray:
    up = np.repeat(np.repeat(coarse, DS, axis=0), DS, axis=1)
    full = np.zeros((CANVAS_H, CANVAS_W), dtype=np.int32)
    h = min(up.shape[0], CANVAS_H)
    w = min(up.shape[1], CANVAS_W)
    full[:h, :w] = up[:h, :w]
    full[land] = 0
    return cells.fill_nearest(full, ~land, WRAP_X)


def _adjacency_links(coarse: np.ndarray, seed_ij: np.ndarray, n: int):
    """(x0,y0,x1,y1) canvas segments joining every pair of adjacent zone centres,
    excluding pairs that straddle the wrap seam (for a clean straight draw)."""
    pairs: set[tuple[int, int]] = set()
    a = coarse
    # horizontal (wrap), vertical
    rb = np.roll(a, -1, axis=1)
    m = (a >= 1) & (a <= n) & (rb >= 1) & (rb <= n) & (a != rb)
    for x, y in zip(a[m].ravel(), rb[m].ravel()):
        pairs.add((int(min(x, y)), int(max(x, y))))
    m = (a[:-1, :] >= 1) & (a[:-1, :] <= n) & (a[1:, :] >= 1) & (a[1:, :] <= n) & (a[:-1, :] != a[1:, :])
    for x, y in zip(a[:-1, :][m].ravel(), a[1:, :][m].ravel()):
        pairs.add((int(min(x, y)), int(max(x, y))))
    segs = []
    for (p, q) in pairs:
        i0, j0 = seed_ij[p - 1]
        i1, j1 = seed_ij[q - 1]
        x0, y0 = (j0 + 0.5) * DS, (i0 + 0.5) * DS
        x1, y1 = (j1 + 0.5) * DS, (i1 + 0.5) * DS
        if abs(x0 - x1) > CANVAS_W / 2:  # seam-straddling; skip for a clean draw
            continue
        segs.append((x0, y0, x1, y1))
    return segs


def render(land, coarse, seed_ij, excluded, n, lines, full, out_file, t0) -> None:
    log("rendering ...", t0)
    labels = _upsample_labels(coarse, land)
    base = np.array(oc.build_basemap(land), dtype=np.uint8)

    pal = _palette(int(coarse.max()))
    for e in excluded:
        pal[e] = (150, 156, 162)
    water = ~land
    tint = pal[labels]
    a = 0.55
    base[water] = (a * tint[water] + (1 - a) * base[water]).astype(np.uint8)

    diff = np.zeros_like(land)
    diff[:, :-1] |= labels[:, :-1] != labels[:, 1:]
    diff[:-1, :] |= labels[:-1, :] != labels[1:, :]
    diff[:, -1] |= labels[:, -1] != labels[:, 0]
    edge = ndimage.binary_dilation(diff & water, iterations=2)
    base[edge & water] = (30, 34, 42)

    img = Image.fromarray(base, "RGB")
    draw = ImageDraw.Draw(img, "RGB")

    # the current arrows, faint, under the links
    if lines is not None:
        for pts in lines:
            oc.draw_streamline(draw, pts, width=3)

    # centre-to-centre links: the routes navies actually sail — should ride the arrows
    for (x0, y0, x1, y1) in _adjacency_links(coarse, seed_ij, n):
        draw.line([(x0, y0), (x1, y1)], fill=(20, 22, 28), width=6)
        draw.line([(x0, y0), (x1, y1)], fill=(250, 250, 250), width=2)

    oc.draw_graticule(draw)

    try:
        font = ImageFont.truetype("arialbd.ttf", 42)
    except Exception:
        font = ImageFont.load_default()
    for m, (i, j) in enumerate(seed_ij, start=1):
        x = (j + 0.5) * DS
        y = (i + 0.5) * DS
        draw.ellipse([x - 15, y - 15, x + 15, y + 15], fill=(200, 30, 40), outline=(255, 255, 255), width=3)
        t = str(m)
        try:
            bb = draw.textbbox((0, 0), t, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
        except Exception:
            tw, th = 18, 18
        draw.text((x - tw / 2, y - th / 2 - 7), t, font=font, fill=(255, 255, 255))

    if not full:
        img = img.resize((CANVAS_W // 2, CANVAS_H // 2), Image.LANCZOS)
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    out = SCRATCH_DIR / out_file
    img.save(out)
    log(f"wrote {out.relative_to(REPO_DIR)}  ({n} currents zones)", t0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spacing", type=float, default=SPACING,
                   help=f"seed every this many px of arc length along a streamline (default {SPACING})")
    p.add_argument("--min-dist", type=float, default=MIN_DIST,
                   help=f"thin seeds to at least this separation, px (default {MIN_DIST})")
    p.add_argument("--stream-sep", type=int, default=STREAM_SEP,
                   help=f"streamline seeding lattice spacing, px (default {STREAM_SEP})")
    p.add_argument("--k", type=float, default=ANISO_K,
                   help=f"anisotropy strength: how much dearer an along-flow step is (default {ANISO_K})")
    p.add_argument("--p", type=float, default=ANISO_P,
                   help=f"anisotropy sharpness exponent on |cos| (default {ANISO_P})")
    p.add_argument("--speed-frac", type=float, default=SPEED_FRAC,
                   help=f"seed only where current speed >= this * ocean 75th pct (default {SPEED_FRAC})")
    p.add_argument("--no-currents", action="store_true", help="hide the streamline overlay")
    p.add_argument("--full", action="store_true", help="render at full 8192x3616 (default half)")
    p.add_argument("--out", default="sea_zones_gyres_review.png",
                   help="output filename under scratchpad/")
    args = p.parse_args(argv)
    build(args.spacing, args.min_dist, args.stream_sep, args.k, args.p,
          args.speed_frac, not args.no_currents, args.full, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
