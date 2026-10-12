#!/usr/bin/env python3
"""Re-draw Ulthuan's parchment state borders on the canvas, in ring terms.

A review/authoring aid, outside the offline gate. Chris drew Ulthuan's state
borders in magenta on the parchment sheet (``sources/ulthuan/ulthuan_parchment.png``).
Pushed straight through the dot warp (``render_anchor_dot_example.py
--borders-only``) they land where the parchment has them, but the parchment
draws the island thicker than the canvas does and splits it unevenly, so lines
hug or overrun the coast. This script puts the same network on the canvas so it
makes sense for the canvas's own land:

* Depth ``t = d_in / (d_in + d_out)``: 0 on the inner-sea shore, 1 on the outer
  coast, 0.5 dead centre of the land. It is measured on both the parchment (from
  the cyan coast trace) and the canvas (from ``land_sea_mask.png``).
* A border that runs along the ring takes an even depth: 1/2 where it is the
  only one across the land, 1/3 and 2/3 where two run side by side. A slanted
  link between two stretches of the same ring line counts as part of it.
* A border that runs across the ring keeps its drawn depth profile and its
  place along the ring, corrected by however far its two ends moved. Where the
  land it crosses is narrower on the canvas, its ends close up along the ring by
  the same factor, so it keeps its slant.
* An end on the parchment coast lands on the canvas coast and runs a few pixels
  into the water.

A point's place along the ring is its angle about the centre of the inner sea,
taken from the committed dot-warp record, so the dot warp still decides where
along the ring everything sits.

Writes, all gitignored under ``mapgen/derived/``:

* ``ulthuan_borders_adjusted_canvas.png``: the lines alone, pure magenta, 1 px,
  on a transparent full-canvas image, to lay into the canvas master's
  ``borders`` layer. That layer is Chris's: this script never writes a source.
* ``ulthuan_borders_adjusted_review.png``: the lines over the reprojected globe
  with the mask's coastline, 3x.
* ``ulthuan_borders_adjusted_vs_old.png``: the same with the straight warp in
  orange and edge numbers. Needs ``--borders-only`` to have been run first.

Deterministic: no RNG, no wall-clock. The constants are tuned to Ulthuan (one
ring-shaped island with one strait); another landmass needs its own boxes.

Usage::

    python mapgen/render_anchor_dot_example.py --seed cr_combi_expanded_map_ulthuan --borders-only
    python mapgen/adjust_ring_borders.py
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import reproject, schema  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
OUT = TOOLS_DIR / "derived"
SEED_SOURCE = "cr_combi_expanded_map_ulthuan.png"

#: Canvas box the island sits in (x0, y0, x1, y1).
BOX = (2470, 860, 3170, 1650)
X0, Y0, X1, Y1 = BOX
#: Parchment-sheet box the island sits in.
PB = (520, 1230, 1540, 2320)
#: Px a coast end runs past the shore.
EXTEND = 4
#: Smoothing (points) of a ring-parallel line.
SMOOTH = 9.0

def ring_of(land):
    lab, n = ndi.label(land)
    sz = ndi.sum(land, lab, range(1, n + 1))
    return lab == (1 + int(np.argmax(sz)))

N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def graph_of(lines):
    """Skeleton graph: nodes (junction clusters + endpoints) and edges (pixel paths between nodes)."""
    sk = skeletonize(ndi.binary_dilation(lines, iterations=1))
    H, W = sk.shape
    nb = ndi.convolve(sk.astype(int), np.ones((3, 3), int), mode='constant') - 1
    junc = sk & (nb >= 3); end = sk & (nb == 1)
    jl, nj = ndi.label(junc, structure=np.ones((3, 3)))
    nodes = []  # (x, y, kind)
    node_id = np.full(sk.shape, -1, int)
    for k in range(1, nj + 1):
        ys, xs = np.nonzero(jl == k)
        node_id[ys, xs] = len(nodes); nodes.append((xs.mean(), ys.mean(), 'j'))
    for y, x in zip(*np.nonzero(end)):
        node_id[y, x] = len(nodes); nodes.append((float(x), float(y), 'e'))
    edges = []; seen = set()
    for y, x in zip(*np.nonzero(node_id >= 0)):
        a = node_id[y, x]
        for dy, dx in N8:
            py, px = y + dy, x + dx
            if not (0 <= py < H and 0 <= px < W) or not sk[py, px] or node_id[py, px] == a:
                continue
            if node_id[py, px] >= 0:
                key = (min(a, node_id[py, px]), max(a, node_id[py, px]), 0)
                if key not in seen and a < node_id[py, px]:
                    seen.add(key); edges.append((a, node_id[py, px], [(x, y), (px, py)]))
                continue
            if (py, px) in seen:
                continue
            path = [(x, y), (px, py)]; visited = {(y, x), (py, px)}; cy, cx = py, px; b = -1
            while True:
                nxt = None
                for ey, ex in N8:
                    qy, qx = cy + ey, cx + ex
                    if not (0 <= qy < H and 0 <= qx < W) or not sk[qy, qx] or (qy, qx) in visited:
                        continue
                    if node_id[qy, qx] >= 0:
                        if node_id[qy, qx] == a and len(path) < 4:
                            continue
                        nxt = (qy, qx); b = node_id[qy, qx]; break
                    if nxt is None:
                        nxt = (qy, qx)
                if nxt is None:
                    break
                path.append((nxt[1], nxt[0])); visited.add(nxt); cy, cx = nxt
                if b >= 0:
                    break
            for (vy, vx) in list(visited)[0:0]:
                pass
            inner = path[1:-1] if b >= 0 else path[1:]
            if any((p[1], p[0]) in seen for p in inner):
                continue
            for p in inner:
                seen.add((p[1], p[0]))
            edges.append((a, b, path))
    return sk, nodes, edges


def font(sz=13):
    try:
        return ImageFont.truetype('arial.ttf', sz)
    except Exception:
        return ImageFont.load_default()


def split_water(ring, hole_pt):
    water = ~ring
    for k in range(1, 60):
        lab, n = ndi.label(~ndi.binary_dilation(ring, iterations=k))
        c = lab[int(hole_pt[1]), int(hole_pt[0])]
        if c == 0:
            continue
        edge_labels = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        if c not in edge_labels:
            inner_core = lab == c
            outer_core = np.isin(lab, [l for l in edge_labels if l])
            break
    else:
        raise SystemExit('inner sea never separates')
    di = ndi.distance_transform_edt(~inner_core); do = ndi.distance_transform_edt(~outer_core)
    inner = water & (di < do)
    return inner, water & ~inner, k


class Depth:
    def __init__(self, ring, hole_pt):
        self.ring = ring
        self.inner, self.outer, self.k = split_water(ring, hole_pt)
        self.din, ii = ndi.distance_transform_edt(~self.inner, return_indices=True)
        self.dout, io = ndi.distance_transform_edt(~self.outer, return_indices=True)
        self.ii, self.io = ii, io
        self.t = self.din / np.maximum(self.din + self.dout, 1e-6)
        self.t_s = ndi.gaussian_filter(self.t, 2.0)
        tw = ndi.gaussian_filter(np.where(ring, self.t, np.where(self.inner, -0.15, 1.15)), 5.0)
        self.t_w = tw; self.gy, self.gx = np.gradient(tw)
        _, self.ir = ndi.distance_transform_edt(~ring, return_indices=True)

    def sample(self, x, y, smooth=True):
        f = self.t_s if smooth else self.t
        return ndi.map_coordinates(f, [np.atleast_1d(y) - 0.5, np.atleast_1d(x) - 0.5], order=1, mode='nearest')

    def slide(self, x, y, tau):
        """Point at depth tau on the cross-section through (x, y): nearest inner shore -> p -> nearest outer coast."""
        H, W = self.ring.shape
        iy = int(np.clip(y, 0, H - 1)); ix = int(np.clip(x, 0, W - 1))
        if not self.ring[iy, ix]:
            iy, ix = self.ir[0][iy, ix], self.ir[1][iy, ix]; x, y = ix + 0.5, iy + 0.5
        a = np.array([self.ii[1][iy, ix] + 0.5, self.ii[0][iy, ix] + 0.5])
        b = np.array([self.io[1][iy, ix] + 0.5, self.io[0][iy, ix] + 0.5])
        p = np.array([x, y])
        if 0.1 < tau < 0.9:   # inside the land: along the ray from the inner sea's centre, so a point keeps its place along the ring
            if not hasattr(self, 'centre'):
                yy, xx = np.nonzero(self.inner); self.centre = np.array([xx.mean() + 0.5, yy.mean() + 0.5])
            c = self.centre; v = p - c; r0 = np.hypot(*v); u = v / max(r0, 1e-9)
            rs = np.arange(0.0, r0 + 220.0, 0.25)
            pts = c + rs[:, None] * u
            tv = ndi.map_coordinates(self.t_w, [pts[:, 1] - 0.5, pts[:, 0] - 0.5], order=1, mode='nearest')
            f = tv - tau
            cross = np.nonzero((f[:-1] <= 0) & (f[1:] > 0) | (f[:-1] >= 0) & (f[1:] < 0))[0]
            if len(cross):
                j = cross[np.argmin(np.abs(rs[cross] - r0))]
                w = f[j] / (f[j] - f[j + 1]) if f[j] != f[j + 1] else 0.0
                return c + (rs[j] + 0.25 * w) * u
            return pts[int(np.argmin(np.abs(f)))]
        s = np.linspace(0, 1, 80)[:, None]
        pts = np.vstack([a + (p - a) * s, p + (b - p) * s[1:]])
        tv = self.t_at_exact(pts)
        j = int(np.argmin(np.abs(tv - tau)))
        return pts[j]

    def t_at_exact(self, pts):
        return ndi.map_coordinates(self.t, [pts[:, 1] - 0.5, pts[:, 0] - 0.5], order=1, mode='nearest')


def smooth_path(P, sigma):
    if len(P) < 5:
        return P
    Q = np.column_stack([ndi.gaussian_filter1d(P[:, 0], sigma, mode='nearest'), ndi.gaussian_filter1d(P[:, 1], sigma, mode='nearest')])
    n = len(P); w = np.minimum(np.arange(n), np.arange(n)[::-1]) / max(1.0, 2 * sigma); w = np.clip(w, 0, 1)[:, None]
    return P * (1 - w) + Q * w


def parch_ring():
    """The island's land, the magenta borders and the cyan trace on the parchment sheet, plus the state count."""
    a = np.asarray(Image.open(ROOT / "sources" / "ulthuan" / "ulthuan_parchment.png").convert('RGB'))[PB[1]:PB[3], PB[0]:PB[2]]
    cy = (a == np.array([0, 255, 255], np.uint8)).all(-1)
    mg = (a == np.array([255, 0, 255], np.uint8)).all(-1)
    bar = ndi.binary_dilation(cy | mg, structure=np.ones((3, 3)))
    lab, n = ndi.label(~bar)
    border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
    near_mg = set(np.unique(lab[ndi.binary_dilation(mg, iterations=4)])) - {0} - border
    cells = np.isin(lab, list(near_mg))
    ring = ndi.binary_closing(cells, structure=np.ones((3, 3)), iterations=4) | cells
    return ring, mg, cy, len(near_mg)


def classify(P, pring, nodes, edges, hp):
    c = np.array(hp); E = []
    for i, (a, b, path) in enumerate(edges):
        p = np.array(path, float) + 0.5
        tp = P.sample(p[:, 0], p[:, 1], smooth=False)
        th = np.unwrap(np.arctan2(p[:, 1] - c[1], p[:, 0] - c[0]))
        r = np.hypot(p[:, 0] - c[0], p[:, 1] - c[1])
        dth = abs(th[-1] - th[0]); arc = dth * r.mean(); dr = abs(r[-1] - r[0])
        par = len(p) >= 25 and arc > 1.3 * dr and (tp.max() - tp.min()) < 0.33
        E.append(dict(i=i, a=a, b=b, p=p, tp=tp, med=float(np.median(tp)), par=par,
                      th0=float(np.degrees(min(th[0], th[-1]))), th1=float(np.degrees(max(th[0], th[-1])))))

    def covers(e, th):
        return any(e['th0'] - 1 <= th + k <= e['th1'] + 1 for k in (-360, 0, 360))
    for e in E:
        e['tier'] = None
        if not e['par']:
            continue
        votes = []
        for w in (0.25, 0.5, 0.75):
            thq = e['th0'] * (1 - w) + e['th1'] * w
            others = sorted([o for o in E if o['par'] and (o is e or covers(o, thq))], key=lambda o: o['med'])
            votes.append((others.index(e) + 1, len(others) + 1))
        j, k = collections.Counter(votes).most_common(1)[0][0]
        e['tier'] = j / k
    # a slanted link between two stretches of the same ring line is part of that line
    at = collections.defaultdict(list)
    for e in E:
        if e['par']:
            at[e['a']].append(e['tier']); at[e['b']].append(e['tier'])
    for e in E:
        if not e['par'] and at[e['a']] and at[e['b']] and (e['th1'] - e['th0']) > 8:
            ta, tb = np.mean(at[e['a']]), np.mean(at[e['b']])
            if abs(ta - tb) < 0.05:
                e['par'] = True; e['tier'] = float((ta + tb) / 2); e['link'] = True
    return E


def main():
    land = np.asarray(Image.open(OUT / "land_sea_mask.png"))[Y0:Y1, X0:X1] > 0
    cring = ring_of(land)
    ys, xs = np.nonzero(cring)
    C = Depth(cring, (xs.mean(), ys.mean() + 40))
    pring, mg, cy, ncell = parch_ring()
    ys, xs = np.nonzero(pring); hp = (xs.mean(), ys.mean() + 60)
    P = Depth(pring, hp)
    regs = {r.source: r for r in schema.load_registrations(TOOLS_DIR / "registration")}
    inv = reproject.fit_placement_inverse(regs[SEED_SOURCE])

    def to_canvas(px, py):
        cx, cy_ = inv.to_canvas_px(np.asarray(px, float) + PB[0], np.asarray(py, float) + PB[1])
        return cx - X0, cy_ - Y0

    sk, nodes, edges = graph_of(mg)
    E = classify(P, pring, nodes, edges, hp)
    deg = collections.Counter()
    for e in E:
        deg[e['a']] += 1; deg[e['b']] += 1
    par_at = collections.defaultdict(list)
    for e in E:
        if e['par']:
            par_at[e['a']].append(e['tier']); par_at[e['b']].append(e['tier'])

    ntau, npos, nwarp = {}, {}, {}
    C.slide(float(np.nonzero(cring)[1].mean()), float(np.nonzero(cring)[0].mean()), 0.5)   # sets C.centre

    def place(q, tau):
        """q moved along its ray from the centre to depth tau (0 / 1 = the shore itself)."""
        if 0.0 < tau < 1.0:
            return C.slide(float(q[0]), float(q[1]), min(max(tau, 0.101), 0.899) if not (0.1 < tau < 0.9) else tau)
        c = C.centre; v = q - c; r0 = np.hypot(*v); u = v / max(r0, 1e-9)
        rs = np.arange(0.0, r0 + 260.0, 0.25); pts = c + rs[:, None] * u
        ix = np.clip(pts[:, 0].astype(int), 0, cring.shape[1] - 1); iy = np.clip(pts[:, 1].astype(int), 0, cring.shape[0] - 1)
        on = cring[iy, ix]
        cross = np.nonzero(on[:-1] != on[1:])[0]
        want = [j for j in cross if (on[j] and not on[j + 1]) == (tau == 1.0)]   # land->water going out = outer coast
        if not want:
            return C.slide(float(q[0]), float(q[1]), tau)
        j = want[int(np.argmin(np.abs(rs[want] - r0)))]
        return c + rs[j] * u
    for k, (x, y, kind) in enumerate(nodes):
        tp = float(P.sample(x + 0.5, y + 0.5, smooth=False)[0])
        on = pring[int(round(y)), int(round(x))]
        if deg[k] <= 1 or tp <= 0.05 or tp >= 0.95 or not on:
            tau = 0.0 if tp < 0.5 else 1.0
        elif par_at[k]:
            tau = float(np.mean(par_at[k]))
        else:
            tau = tp
        cx, cy_ = to_canvas(x + 0.5, y + 0.5)
        ntau[k] = tau; nwarp[k] = np.array([float(cx), float(cy_)]); npos[k] = place(nwarp[k], tau)

    # two borders that reach the coast at the same spot share one coast point
    ends = [k for k in ntau if deg[k] <= 1]
    for i_, a in enumerate(ends):
        for b in ends[i_ + 1:]:
            if np.hypot(nodes[a][0] - nodes[b][0], nodes[a][1] - nodes[b][1]) < 9 and ntau[a] == ntau[b]:
                m_ = (nwarp[a] + nwarp[b]) / 2; nwarp[a] = nwarp[b] = m_; npos[a] = npos[b] = place(m_, ntau[a])
    # A border across the ring keeps its slant: where the land it crosses got narrower or
    # wider than on the parchment, its ends close up or spread along the ring by the same factor.
    cen = C.centre
    def polar(q):
        v = q - cen; return np.arctan2(v[1], v[0]), np.hypot(*v)
    shift = collections.defaultdict(list)
    for e in E:
        if e['par'] or len(e['p']) < 8:
            continue
        a, b = e['a'], e['b']
        tha0, ra0 = polar(nwarp[a]); thb0, rb0 = polar(nwarp[b])
        _, ra1 = polar(npos[a]); _, rb1 = polar(npos[b])
        dr0, dr1 = rb0 - ra0, rb1 - ra1
        if abs(dr0) < 6:
            continue
        k = float(np.clip(abs(dr1) / abs(dr0), 0.25, 1.6))
        dth0 = (thb0 - tha0 + np.pi) % (2 * np.pi) - np.pi
        delta = dth0 * (k - 1.0)
        free_a, free_b = deg[a] <= 1, deg[b] <= 1
        if free_a and not free_b:
            shift[a].append(-delta)
        elif free_b and not free_a:
            shift[b].append(delta)
        else:
            shift[a].append(-delta / 2); shift[b].append(delta / 2)
    for k_, lst in shift.items():
        d = float(np.mean(lst))
        th, r = polar(nwarp[k_])
        if deg[k_] > 1:   # a junction also anchors ring-parallel lines: let it give only a little
            d = float(np.clip(d, -10.0 / r, 10.0 / r))
        th += d
        npos[k_] = place(cen + r * np.array([np.cos(th), np.sin(th)]), ntau[k_])

    paths = []
    for e in E:
        p = e['p']; n = len(p); s = np.linspace(0, 1, n)
        cx, cy_ = to_canvas(p[:, 0], p[:, 1])
        ta, tb = ntau[e['a']], ntau[e['b']]
        if e['par']:
            # its own even depth along the middle, easing to the junction depths at the ends
            ra_ = max(25.0, 0.4 * n) if ta in (0.0, 1.0) else 25.0
            rb_ = max(25.0, 0.4 * n) if tb in (0.0, 1.0) else 25.0
            ramp = np.clip(np.minimum(s * n / ra_, (1 - s) * n / rb_), 0, 1)
            ramp = ramp * ramp * (3 - 2 * ramp)
            lin = ta + (tb - ta) * s
            tau = lin * (1 - ramp) + e['tier'] * ramp
            # stretched along the ring so it starts and stops where its junctions now are
            def wrap(a_):
                return (a_ + np.pi) % (2 * np.pi) - np.pi
            dtha = wrap(polar(npos[e['a']])[0] - polar(nwarp[e['a']])[0]); dthb = wrap(polar(npos[e['b']])[0] - polar(nwarp[e['b']])[0])
            Q = []
            for x, y, t, si in zip(cx, cy_, tau, s):
                v = np.array([x, y]) - cen; r = np.hypot(*v); th = np.arctan2(v[1], v[0]) + dtha * (1 - si) + dthb * si
                Q.append(place(cen + r * np.array([np.cos(th), np.sin(th)]), float(np.clip(t, 0.02, 0.98))))
            Q = smooth_path(np.array(Q), SMOOTH)
            Q = np.array([place(q, float(np.clip(t, 0.02, 0.98))) for q, t in zip(Q, tau)]); Q = smooth_path(Q, 4.0)
            m = min(18, n // 2)
            wa = np.clip(1 - np.arange(n) / max(m, 1), 0, 1)[:, None]; wb = wa[::-1]
            Q = Q + (npos[e['a']] - Q[0]) * wa + (npos[e['b']] - Q[-1]) * wb
        else:
            # carried in ring terms: each point keeps its drawn depth and place along the ring,
            # corrected by however far its two ends moved in depth and along the ring
            W0 = np.column_stack([cx, cy_])
            def wrap(a_):
                return (a_ + np.pi) % (2 * np.pi) - np.pi
            dtha = wrap(polar(npos[e['a']])[0] - polar(nwarp[e['a']])[0]); dthb = wrap(polar(npos[e['b']])[0] - polar(nwarp[e['b']])[0])
            tp = e['tp']
            tau = np.clip(tp + (ta - tp[0]) * (1 - s) + (tb - tp[-1]) * s, 0.0, 1.0)
            Q = []
            for (x, y), t, si in zip(W0, tau, s):
                v = np.array([x, y]) - cen; r = np.hypot(*v); th = np.arctan2(v[1], v[0]) + dtha * (1 - si) + dthb * si
                Q.append(place(cen + r * np.array([np.cos(th), np.sin(th)]), float(np.clip(t, 0.02, 0.98))))
            Q = smooth_path(np.array(Q), 5.0)
            m = min(12, n // 2)
            wa = np.clip(1 - np.arange(n) / max(m, 1), 0, 1)[:, None]; wb = wa[::-1]
            Q = Q + (npos[e['a']] - Q[0]) * wa + (npos[e['b']] - Q[-1]) * wb
        for end, k in ((0, e['a']), (-1, e['b'])):
            if ntau[k] in (0.0, 1.0) and len(Q) > 6:
                d = (Q[end] - cen) * (1.0 if ntau[k] == 1.0 else -1.0); nrm = np.hypot(*d)
                if nrm > 0:
                    # straight out to sea (or in to the inner sea) until the line is in the water, then a little further
                    u = d / nrm; q = Q[end].copy(); steps = 0
                    while steps < 60 and cring[int(np.clip(q[1], 0, cring.shape[0] - 1)), int(np.clip(q[0], 0, cring.shape[1] - 1))]:
                        q = q + u * 0.5; steps += 1
                    ext = q + u * EXTEND
                    if steps >= 60:
                        print('  WARNING: coast end of e%d never reached water' % e['i'])
                    Q = np.vstack([ext, Q]) if end == 0 else np.vstack([Q, ext])
        paths.append(Q)

    H, W = cring.shape
    img = Image.new('L', (W, H), 0); d = ImageDraw.Draw(img)
    for Q in paths:
        d.line([(float(x) - 0.5, float(y) - 0.5) for x, y in Q], fill=255, width=1)
    new = np.asarray(img) > 0
    full = np.zeros((3616, 8192, 4), np.uint8)
    full[Y0:Y1, X0:X1][new] = (255, 0, 255, 255)
    Image.fromarray(full, 'RGBA').save(OUT / "ulthuan_borders_adjusted_canvas.png")

    lab, n = ndi.label(cring & ~ndi.binary_dilation(new, structure=np.ones((3, 3))))
    sz = ndi.sum(cring, lab, range(1, n + 1))
    big = sorted([int(s) for s in sz if s >= 150], reverse=True)
    print('parchment cells', ncell, '| canvas cells >=150px:', len(big), big)
    for k in range(1, n + 1):
        if 8 <= sz[k - 1] < 150:
            yy, xx = np.nonzero(lab == k); print('  sliver', int(sz[k - 1]), 'px -> review px', (int(xx.mean()) - 20) * 3, (int(yy.mean()) - 60) * 3)
    # depth actually achieved by the parallel lines
    for e, Q in zip(E, paths):
        if e['par']:
            t = C.t_at_exact(Q[8:-8]) if len(Q) > 30 else C.t_at_exact(Q)
            print(f"  e{e['i']:<2} tier {e['tier']:.2f}  parchment depth {e['med']:.2f}  canvas depth now mean {t.mean():.2f} (min {t.min():.2f} max {t.max():.2f})")

    S = 3
    globe = np.asarray(Image.open(ROOT / "sources" / "originals" / "terraqueous_globe_reprojected.png").convert('RGB'))[Y0:Y1, X0:X1]
    old_path = OUT / "cr_combi_expanded_map_ulthuan_borders_canvas.png"
    renders = [('ulthuan_borders_adjusted_review.png', False)]
    if old_path.is_file():
        old = np.asarray(Image.open(old_path))[Y0:Y1, X0:X1, 3] > 0
        renders.append(('ulthuan_borders_adjusted_vs_old.png', True))
    else:
        print(f'no {old_path.name}: skipping the before/after render (run render_anchor_dot_example.py --borders-only)')
    for name, show_old in renders:
        im = Image.fromarray(globe).resize((W * S, H * S), Image.LANCZOS); dr = ImageDraw.Draw(im)
        coast = land & ~ndi.binary_erosion(land)
        for y, x in zip(*np.nonzero(coast)):
            dr.rectangle([x * S, y * S, x * S + S - 1, y * S + S - 1], fill=(0, 255, 255))
        if show_old:
            for y, x in zip(*np.nonzero(old)):
                dr.rectangle([x * S, y * S, x * S + S - 1, y * S + S - 1], fill=(255, 160, 0))
        for Q in paths:
            dr.line([(float(x) * S, float(y) * S) for x, y in Q], fill=(255, 0, 255), width=3)
        if show_old:
            for e, Q in zip(E, paths):
                x, y = Q[len(Q) // 2]
                dr.text((x * S + 3, y * S + 2), f"e{e['i']}", fill=(255, 255, 255), font=font(13), stroke_width=2, stroke_fill=(0, 0, 0))
        im.crop((20 * S, 60 * S, (W - 20) * S, (H - 40) * S)).save(OUT / name)


if __name__ == '__main__':
    main()
