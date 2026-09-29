#!/usr/bin/env python3
"""PROTOTYPE: sea zones derived from the ocean-current gyres.

Parallel exploration (not the committed sea system). The user's premise: in
Victoria 3 navies and ocean trade travel from the *centre* of one sea zone to the
centre of the next along a fairly direct path, so a good sea-zone map is a tiling
of the ocean into **compact basins, each with a real centre, whose centre-to-
centre hops stay in water**. The wind-driven ocean gyres are exactly that — each
subtropical / subpolar gyre is a closed circulation cell with a well-defined
centre — so this derives the zones straight from the circulation solved by
``render_ocean_currents.py``:

1. Solve the Stommel transport streamfunction ``psi`` (reused verbatim from
   ``render_ocean_currents``) and smooth it into broad gyres.
2. **Gyre centres = local extrema of ``psi``** within the ocean (a max at the
   heart of an anticyclonic subtropical gyre, a min for a cyclonic subpolar one).
   These are the physically-meaningful zone centres.
3. Split the ocean into a **main ocean** (the large connected water bodies the
   gyres live in) and **inland/river water** (small disconnected bodies the
   wind/current picture says nothing about). Only the main ocean is partitioned
   into currents zones; the inland bits are kept aside and *not* counted toward
   the target — per the user's instruction.
4. To reach the requested zone count, augment the gyre-centre seeds by
   **geodesic farthest-point insertion** inside the main ocean (each new seed the
   in-water-farthest point from every existing one), so extra zones stay compact
   and well-spaced rather than slivered.
5. **Geodesic (in-water) Voronoi**: every ocean cell takes the nearest seed
   measured *through water only* (multi-source BFS, wrap-aware). Because distance
   is geodesic, no zone reaches across a peninsula, and the straight centre-to-
   centre hop between adjacent zones lies in water — the naval constraint, by
   construction. (Euclidean nearest, ``cells.fill_nearest``, would jump land; it's
   used here only for the sub-``SOLVE_DS`` coastal fringe, where a jump can't
   span a real barrier.)

Deterministic: a linear solve + smoothing + extrema + BFS with index-ordered tie
breaks — no RNG, no wall-clock. Writes a review PNG to ``mapgen/derived/`` and
prints the zone tally; it commits nothing and touches no map bitmap. The rendered
artifact is the gate (see the autonomy model): look at it, then decide.

Usage::

    python mapgen/render_sea_zones_currents.py                 # ~100 zones, half-res render
    python mapgen/render_sea_zones_currents.py --target 90
    python mapgen/render_sea_zones_currents.py --inland-max 60 # tune ocean/inland split
    python mapgen/render_sea_zones_currents.py --full          # full 8192x3616 render
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

import render_ocean_currents as oc  # noqa: E402  (reuse the physics + basemap)
from config import canvas_frame as cf  # noqa: E402
from worldgen import cells  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

DERIVED_DIR = oc.DERIVED_DIR
REPO_DIR = oc.REPO_DIR
CANVAS_W, CANVAS_H = oc.CANVAS_W, oc.CANVAS_H
DS = oc.SOLVE_DS
WRAP_X = True

TARGET = 100          # main-ocean currents zones (inland/river water excluded)
OCEAN_MIN = 300       # a connected water body >= this many coarse cells is open ocean
INLAND_MIN = 40       # [INLAND_MIN, OCEAN_MIN) coarse cells => a real inland sea (excluded);
                      # smaller specks are coastal rounding, folded into the partition
EXTREMA_FOOTPRINT = 13  # coarse cells: min separation of detected gyre centres
EXTREMA_FRAC = 0.06   # ignore |psi| extrema weaker than this fraction of the ocean max
ANISO_K = 8.0         # cross-current distance penalty: a step across the flow costs up
                      # to (1 + K)x a step along it, so zones stretch into flow-arcs
ANISO_P = 1.0         # shape of the penalty vs. across-flow fraction (1 = linear)


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


# --------------------------------------------------------------------------- #
# Anisotropic flow graph (in-water distance, cheap along the current)          #
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


class FlowGraph:
    """An anisotropic geodesic graph over the ocean cells.

    Each edge between adjacent ocean cells is weighted by its geometric length
    times an anisotropy penalty for crossing the current: a step *along* the
    local flow costs ~its length, a step *across* it costs up to ``(1 + k)`` more.
    Geodesic distance in this metric is short along streamlines and long across
    them, so a nearest-seed (Voronoi) partition yields zones that **stretch into
    arcs following the current** rather than isotropic blobs. Where the flow
    stalls (gyre eyes, stagnation) the penalty vanishes and the metric is
    isotropic. Undirected and symmetric; a pure function of (u, v) — no RNG.
    """

    def __init__(self, main_ocean: np.ndarray, u: np.ndarray, v: np.ndarray,
                 k: float, p: float, wrap_x: bool = True, penalize: str = "along"):
        from scipy import sparse
        H, W = main_ocean.shape
        nid = np.full((H, W), -1, dtype=np.int64)
        nid[main_ocean] = np.arange(int(main_ocean.sum()))
        self.nid = nid
        self.n = int(main_ocean.sum())
        self.shape = (H, W)
        self.rows, self.cols = np.nonzero(main_ocean)  # node id -> (i, j)

        fmag = np.hypot(u, v)
        eps = 1e-9
        fx = np.where(fmag > eps, u / (fmag + eps), 0.0)
        fy = np.where(fmag > eps, v / (fmag + eps), 0.0)
        has_flow = fmag > eps

        src_all, dst_all, w_all = [], [], []
        for di, dj in _OFFSETS:
            nb_ok = _shift(main_ocean.astype(np.int8), di, dj, wrap_x) > 0
            mask = main_ocean & nb_ok
            if not mask.any():
                continue
            # midpoint unit flow (average of the two endpoints)
            fxm = 0.5 * (fx + _shift(fx, di, dj, wrap_x))
            fym = 0.5 * (fy + _shift(fy, di, dj, wrap_x))
            L = float(np.hypot(di, dj))
            # step vector in (x, y) is (dj, di); |cos| with the flow line
            dot = np.abs(dj * fxm + di * fym) / L
            fm = np.hypot(fxm, fym)
            cosang = np.where(fm > eps, np.clip(dot / (fm + eps), 0.0, 1.0), 1.0)
            across = 1.0 - cosang
            # "along": penalise travel WITH the current, so zones become short
            #   perpendicular beads whose downstream neighbour is close -> centre-to-
            #   centre hops run ALONG the arrows (the user's rule).
            # "across": penalise travel across it, so zones stretch into flow-arcs
            #   (the earlier variant; kept for comparison).
            factor = cosang if penalize == "along" else across
            both_flow = has_flow & _shift(has_flow.astype(np.int8), di, dj, wrap_x).astype(bool)
            w = L * (1.0 + k * np.where(both_flow, factor ** p, 0.0))
            src_all.append(nid[mask])
            dst_all.append(_shift(nid, di, dj, wrap_x)[mask])
            w_all.append(w[mask])

        src = np.concatenate(src_all)
        dst = np.concatenate(dst_all)
        wgt = np.concatenate(w_all).astype(np.float64)
        self.G = sparse.csr_matrix((wgt, (src, dst)), shape=(self.n, self.n))

    def seed_nodes(self, seed_ij: np.ndarray) -> np.ndarray:
        return self.nid[seed_ij[:, 0], seed_ij[:, 1]]

    def distance_field(self, seed_nodes: np.ndarray):
        """(dist, source) per node: min anisotropic distance to any seed, and
        which seed node it belongs to."""
        from scipy.sparse.csgraph import dijkstra
        dist, _, sources = dijkstra(self.G, directed=False, indices=seed_nodes,
                                    min_only=True, return_predecessors=True)
        return dist, sources


# --------------------------------------------------------------------------- #
# Seeds: gyre centres + geodesic farthest-point augmentation                   #
# --------------------------------------------------------------------------- #
def smoothed_psi(psi: np.ndarray, ocean: np.ndarray) -> np.ndarray:
    """psi smoothed within the ocean the same way velocity_from_psi does."""
    if oc.SMOOTH_CELLS <= 0:
        return np.where(ocean, psi, 0.0)
    m = ocean.astype(np.float64)
    num = ndimage.gaussian_filter(psi * m, oc.SMOOTH_CELLS, mode=("nearest", "wrap"))
    den = ndimage.gaussian_filter(m, oc.SMOOTH_CELLS, mode=("nearest", "wrap"))
    return np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0) * m


def gyre_centres(psi: np.ndarray, ocean: np.ndarray,
                 footprint: int = EXTREMA_FOOTPRINT,
                 frac: float = EXTREMA_FRAC) -> list[tuple[int, int]]:
    """One seed per local extremum of psi (gyre centre) within the ocean."""
    lim = float(np.abs(psi[ocean]).max()) if ocean.any() else 1.0
    thr = frac * lim
    fp = footprint
    big = -1e18
    pmax = ndimage.maximum_filter(np.where(ocean, psi, big), size=fp, mode=("nearest", "wrap"))
    pmin = ndimage.minimum_filter(np.where(ocean, psi, -big), size=fp, mode=("nearest", "wrap"))
    is_ext = ocean & (((psi >= pmax) & (psi > thr)) | ((psi <= pmin) & (psi < -thr)))
    # cluster touching extremum pixels; one seed (the strongest) per cluster
    comp = cells.components(is_ext.astype(np.int32), WRAP_X)
    seeds: list[tuple[int, int]] = []
    for c in range(1, int(comp.max()) + 1):
        ys, xs = np.nonzero(comp == c)
        k = int(np.argmax(np.abs(psi[ys, xs])))
        seeds.append((int(ys[k]), int(xs[k])))
    return seeds


def augment_farthest(seeds: list[tuple[int, int]], fg: FlowGraph,
                     target: int, t0: float) -> np.ndarray:
    """Grow the seed set to ``target`` by farthest-point insertion in the flow
    metric: each new seed is the ocean cell whose anisotropic distance to every
    existing seed is greatest. In "along" (bead) mode the metric is cheap *across*
    the flow, so new seeds land spaced *along* the current — strung down each
    highway — and the zones they carve are perpendicular beads that hand off
    downstream. In "across" (arc) mode they space across the flow into arcs."""
    seed_ij = np.array(seeds, dtype=np.int64) if seeds else np.empty((0, 2), np.int64)
    while len(seed_ij) < target:
        dist, _ = fg.distance_field(fg.seed_nodes(seed_ij))
        dist = np.where(np.isfinite(dist), dist, -1.0)
        far = int(np.argmax(dist))
        if dist[far] <= 0:
            log(f"  farthest-point stalled at {len(seed_ij)} seeds (ocean fully covered)", t0)
            break
        seed_ij = np.vstack([seed_ij, [int(fg.rows[far]), int(fg.cols[far])]])
        if len(seed_ij) % 20 == 0:
            log(f"  seeded {len(seed_ij)}/{target}", t0)
    return seed_ij


def partition_labels(fg: FlowGraph, seed_ij: np.ndarray) -> np.ndarray:
    """Flow-metric nearest-seed label per main-ocean cell (0 elsewhere).

    ``label m`` is the 1-based index of ``seed_ij[m-1]``; every ocean cell takes
    the seed nearest in the anisotropic metric, so zones follow the current.
    """
    seed_nodes = fg.seed_nodes(seed_ij)
    _, sources = fg.distance_field(seed_nodes)
    lab_of_node = np.zeros(fg.n, dtype=np.int32)
    lab_of_node[seed_nodes] = np.arange(1, len(seed_nodes) + 1, dtype=np.int32)
    reach = sources >= 0
    src = np.where(reach, sources, seed_nodes[0])
    lab_nodes = np.where(reach, lab_of_node[src], 0).astype(np.int32)
    lab = np.zeros(fg.shape, dtype=np.int32)
    lab[fg.rows, fg.cols] = lab_nodes
    return lab


# --------------------------------------------------------------------------- #
# Build                                                                        #
# --------------------------------------------------------------------------- #
def build(target: int, full: bool, out_file: str, footprint: int, frac: float,
          aniso_k: float, mode: str, links: bool) -> Path:
    t0 = time.time()
    penalize = "along" if mode == "beads" else "across"
    land = oc.load_land()
    log(f"land mask {land.shape}, land {100 * land.mean():.1f}%", t0)

    psi_raw, ocean = oc.solve_streamfunction(land, oc.GAMMA)
    psi = smoothed_psi(psi_raw, ocean)             # for gyre-centre detection
    u, v, _typ = oc.velocity_from_psi(psi_raw, ocean)  # the flow that shapes the zones
    speed = np.hypot(u, v)
    Hs, Ws = ocean.shape
    log(f"solved streamfunction on {Ws}x{Hs} grid, {int(ocean.sum()):,} ocean cells "
        f"(mode={mode}, penalize {penalize}-flow)", t0)

    # Split the water by connected-component area (wrap-aware): open ocean gets
    # the currents partition; genuine inland seas are excluded; tiny coastal
    # specks are folded back into the partition (absorbed by the canvas coast
    # fill) so they don't show as grey noise.
    comp = cells.components(ocean.astype(np.int32), WRAP_X)
    areas = np.bincount(comp.ravel())
    a_comp = areas[comp]
    main_ocean = ocean & (a_comp >= OCEAN_MIN)
    inland = ocean & (a_comp >= INLAND_MIN) & (a_comp < OCEAN_MIN)
    n_inland_bodies = int(len({int(c) for c in np.unique(comp[inland]) if c}))
    n_speck = int((ocean & (a_comp < INLAND_MIN)).sum())
    log(f"main ocean {int(main_ocean.sum()):,} cells; "
        f"inland seas {int(inland.sum()):,} cells in {n_inland_bodies} bodies (excluded); "
        f"{n_speck} coastal-speck cells folded", t0)

    # Primary seeds: one per main ocean body so farthest-point can cover them all.
    #   beads mode  -> the strongest-current cell in each body (a highway limb, NOT
    #                  the stagnant eye); eyes then fall out as zone boundaries.
    #   arcs  mode  -> the gyre eyes (psi extrema), for the arc variant.
    if mode == "beads":
        centres = []
        for c in np.unique(comp[main_ocean]):
            m = comp == c
            ys, xs = np.nonzero(m)
            k = int(np.argmax(speed[ys, xs]))
            centres.append((int(ys[k]), int(xs[k])))
        log(f"{len(centres)} primary seeds (strongest-current cell per body; eyes avoided)", t0)
    else:
        centres = [(i, j) for (i, j) in gyre_centres(psi, ocean, footprint, frac)
                   if main_ocean[i, j]]
        seeded = {int(comp[i, j]) for (i, j) in centres}
        for c in np.unique(comp[main_ocean]):
            if int(c) not in seeded:
                ys, xs = np.nonzero(comp == c)
                k = int(np.argmax(np.abs(psi[ys, xs])))
                centres.append((int(ys[k]), int(xs[k])))
        log(f"{len(centres)} primary gyre-eye seeds (footprint {footprint}, frac {frac})", t0)

    # The anisotropic flow graph shapes both the farthest-point fill and the final
    # partition. penalize=along -> perpendicular beads (downstream neighbours);
    # penalize=across -> flow-arcs.
    log(f"building flow graph (aniso k={aniso_k}, penalize {penalize}) ...", t0)
    fg = FlowGraph(main_ocean, u, v, aniso_k, ANISO_P, WRAP_X, penalize)

    seed_ij = augment_farthest(centres, fg, target, t0)
    n = len(seed_ij)
    log(f"partitioning main ocean among {n} seeds (flow metric) ...", t0)
    lab = partition_labels(fg, seed_ij)

    # inland bodies each become their own excluded label after the n zones
    coarse = lab.copy()
    excluded: set[int] = set()
    nxt = n + 1
    for c in np.unique(comp[inland]):
        if not c:
            continue
        coarse[comp == c] = nxt
        excluded.add(nxt)
        nxt += 1
    log(f"{n} currents zones + {len(excluded)} inland/river bodies", t0)

    render(land, coarse, seed_ij, excluded, n, full, out_file, t0, links)
    return DERIVED_DIR / out_file


# --------------------------------------------------------------------------- #
# Render                                                                       #
# --------------------------------------------------------------------------- #
def _palette(n: int) -> np.ndarray:
    """n visually-distinct RGB colours via golden-angle hue rotation."""
    import colorsys
    cols = np.zeros((n + 1, 3), dtype=np.uint8)
    for i in range(1, n + 1):
        h = (i * 0.61803398875) % 1.0
        s = 0.42 + 0.22 * ((i * 7) % 3) / 2.0
        v = 0.90 - 0.16 * ((i * 5) % 2)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        cols[i] = (int(r * 255), int(g * 255), int(b * 255))
    return cols


def _upsample_labels(coarse: np.ndarray, land: np.ndarray) -> np.ndarray:
    """Coarse zone labels -> canvas labels, clipped to water, coast fringe filled."""
    up = np.repeat(np.repeat(coarse, DS, axis=0), DS, axis=1)
    full = np.zeros((CANVAS_H, CANVAS_W), dtype=np.int32)
    h = min(up.shape[0], CANVAS_H)
    w = min(up.shape[1], CANVAS_W)
    full[:h, :w] = up[:h, :w]
    full[land] = 0
    water = ~land
    full = cells.fill_nearest(full, water, WRAP_X)  # short-range coastal fringe
    return full


def zone_adjacency(coarse: np.ndarray, n: int, wrap_x: bool) -> set[tuple[int, int]]:
    """Unordered pairs of zone labels (1..n) that share a coarse-grid border."""
    pairs: set[tuple[int, int]] = set()

    def add(x, y):
        m = (x >= 1) & (x <= n) & (y >= 1) & (y <= n) & (x != y)
        if not m.any():
            return
        lo = np.minimum(x[m], y[m])
        hi = np.maximum(x[m], y[m])
        for a, b in np.unique(np.stack([lo, hi], axis=1), axis=0):
            pairs.add((int(a), int(b)))

    add(coarse[:, :-1], coarse[:, 1:])
    add(coarse[:-1, :], coarse[1:, :])
    if wrap_x:
        add(coarse[:, -1], coarse[:, 0])
    return pairs


def render(land, coarse, seed_ij, excluded, n, full, out_file, t0, links=False) -> None:
    log("rendering ...", t0)
    labels = _upsample_labels(coarse, land)
    base = np.array(oc.build_basemap(land), dtype=np.uint8)

    pal = _palette(int(coarse.max()))
    for e in excluded:
        pal[e] = (150, 156, 162)  # inland/river water: neutral grey, not a currents zone
    water = ~land
    tint = pal[labels]
    a = 0.60
    base[water] = (a * tint[water] + (1 - a) * base[water]).astype(np.uint8)

    # crisp zone boundaries in the water
    diff = np.zeros_like(land)
    diff[:, :-1] |= labels[:, :-1] != labels[:, 1:]
    diff[:-1, :] |= labels[:-1, :] != labels[1:, :]
    diff[:, -1] |= labels[:, -1] != labels[:, 0]  # wrap seam
    edge = diff & water
    edge = ndimage.binary_dilation(edge, iterations=2)
    base[edge & water] = (35, 40, 48)

    img = Image.fromarray(base, "RGB")
    draw = ImageDraw.Draw(img, "RGB")
    oc.draw_graticule(draw)

    centres = {m: ((j + 0.5) * DS, (i + 0.5) * DS)
               for m, (i, j) in enumerate(seed_ij, start=1)}

    # centre-to-centre links: the paths navies/trade actually travel. Overlaid so
    # you can verify each hop lies on open water running with the current, not
    # across a stagnant eye or clipping land.
    if links:
        for a, b in zone_adjacency(coarse, n, WRAP_X):
            (xa, ya), (xb, yb) = centres[a], centres[b]
            if abs(xa - xb) > CANVAS_W / 2:  # skip seam-wrapping links (rare)
                continue
            draw.line([(xa, ya), (xb, yb)], fill=(255, 238, 90), width=5)

    # numbered dot at every currents-zone centre (the point navies route through)
    try:
        font = ImageFont.truetype("arialbd.ttf", 46)
    except Exception:
        font = ImageFont.load_default()
    for m, (i, j) in enumerate(seed_ij, start=1):
        x = (j + 0.5) * DS
        y = (i + 0.5) * DS
        draw.ellipse([x - 13, y - 13, x + 13, y + 13], fill=(20, 24, 30), outline=(255, 255, 255), width=3)
        t = str(m)
        try:
            bb = draw.textbbox((0, 0), t, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
        except Exception:
            tw, th = 20, 20
        draw.text((x - tw / 2, y - th / 2 - 8), t, font=font, fill=(255, 255, 255))

    if not full:
        img = img.resize((CANVAS_W // 2, CANVAS_H // 2), Image.LANCZOS)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out = DERIVED_DIR / out_file
    img.save(out)
    log(f"wrote {out.relative_to(REPO_DIR)}  ({n} currents zones)", t0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", type=int, default=TARGET,
                   help=f"main-ocean currents zones, inland excluded (default {TARGET})")
    p.add_argument("--extrema-footprint", type=int, default=EXTREMA_FOOTPRINT,
                   help=f"min separation of detected gyre centres, coarse cells (default {EXTREMA_FOOTPRINT}; "
                        f"smaller = more gyres)")
    p.add_argument("--extrema-frac", type=float, default=EXTREMA_FRAC,
                   help=f"ignore |psi| extrema weaker than this fraction of the ocean max (default {EXTREMA_FRAC})")
    p.add_argument("--aniso-k", type=float, default=ANISO_K,
                   help=f"anisotropy strength; higher = stronger flow shaping (default {ANISO_K}, 0 = isotropic)")
    p.add_argument("--mode", choices=("beads", "arcs"), default="beads",
                   help="beads: centres on the current limbs, zones hand off DOWNSTREAM (the user's rule); "
                        "arcs: centres on gyre eyes, zones stretch along the flow (earlier variant)")
    p.add_argument("--links", action="store_true",
                   help="overlay centre-to-centre links (the paths navies/trade travel) to verify them")
    p.add_argument("--full", action="store_true", help="render at full 8192x3616 (default half)")
    p.add_argument("--out", default="sea_zones_currents_review.png",
                   help="output filename under mapgen/derived/")
    args = p.parse_args(argv)
    build(args.target, args.full, args.out, args.extrema_footprint, args.extrema_frac,
          args.aniso_k, args.mode, args.links)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
