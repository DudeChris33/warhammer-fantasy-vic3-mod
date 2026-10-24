"""Snap the loose hand-drawn ``borders`` layer of ``sources/iee/iee_parchment.ora`` onto
the printed border lines of its own ``main surface`` parchment.

The drawn network is topologically right but sits a few to ~15 px off the printed ink.
Every junction-to-junction run is re-drawn as the least-cost path between its (snapped)
end nodes, where cost is low on dark line-shaped ink (a Sato ridge filter) and rises
with distance from the original stroke, so the route follows the nearest printed line
and never wanders to a different one. Topology is kept: same junctions, same runs.

Writes to scratchpad/iee/ (git-ignored): ``borders_aligned.png`` (the new layer, same
size, colour and stroke width as the drawn one), ``aligned_overview.png`` and
``aligned_tiles/`` review renders (grey = the original line, magenta = aligned).
The source ``.ora`` is never modified.

Usage (repo root, mapgen/.venv): python mapgen/ie_borders/align_iee_borders.py
"""
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.filters import sato
from skimage.graph import route_through_array
from skimage.morphology import skeletonize

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[2]
ORA = ROOT / "sources" / "iee" / "iee_parchment.ora"
OUT = ROOT / "scratchpad" / "iee"
OUT.mkdir(parents=True, exist_ok=True)

MAGENTA = (255, 0, 255)
PAINT_R = 2          # drawn strokes are ~5 px wide (half-width 2-3 at the skeleton)
NODE_SNAP = 8        # a junction may move this far to land on printed ink
CORRIDOR = 16        # a run may move this far from where it was drawn
DIST_W = 0.6         # cost per (px from the drawn line / CORRIDOR)^2
EPS = 0.02           # floor cost on perfect ink
EDGE_PIN = 6         # nodes / runs this close to the canvas edge stay put
RECONNECT = 24       # a new free end rejoins a branch this close
FILL_V, FILL_BOX, FILL_DEPTH = 125, 7, 5
FILL_KEEP = 6        # ... except within this of where the line was drawn
LOOP_RATIO = 0.4     # ends closer than this x run length: the run is a loop
SLIVER = 60          # enclosed cells under this many px are re-route loops: filled
EIGHT = np.ones((3, 3), int)


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def nbr_count(sk):
    return ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - sk


def layer(z, name):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(z.read("stack.xml"))
    src = next(l.get("src") for l in root.iter("layer") if l.get("name") == name)
    return np.array(Image.open(z.open(src)).convert("RGBA"))


z = zipfile.ZipFile(ORA)
borders = layer(z, "borders")
surface = layer(z, "main surface")
drawn = borders[..., 3] > 0
H, W = drawn.shape

# line-ness of the printed ink; transparent parchment (alpha 0) carries no ink
V = surface[..., :3].max(2).astype(np.float32)
V[surface[..., 3] == 0] = 255.0
cache = OUT / "ridge.npy"
if cache.exists():
    ridge = np.load(cache)
else:
    ridge = sato(V, sigmas=[1.0, 1.5, 2.0], black_ridges=True).astype(np.float32)
    np.save(cache, ridge)
r = np.clip(ridge / np.percentile(ridge[ridge > 0], 99), 0, 1)
ink_cost = (1.0 - r) ** 3 + EPS
# interior of wide dark fills (river channels, lakes, dark sea): a border runs along a
# bank, never through the middle, so routes may not cut across
deep = ndi.distance_transform_edt(ndi.uniform_filter(V, FILL_BOX) < FILL_V) >= FILL_DEPTH

sk = skeletonize(drawn)
nc = nbr_count(sk)
nodes = sk & ((nc >= 3) | (nc == 1))
nl, nn = ndi.label(ndi.binary_dilation(nodes, disk(2)), EIGHT)

snapped = {}
for i, sl in enumerate(ndi.find_objects(nl), 1):
    cy, cx = [int(round(c)) for c in ndi.center_of_mass(nl[sl] == i)]
    cy += sl[0].start
    cx += sl[1].start
    if nc[max(cy - 2, 0):cy + 3, max(cx - 2, 0):cx + 3].max() <= 1 and not (
            nc[sl] >= 3).any():                       # free end (coast, map edge): keep put
        snapped[i] = (cy, cx)
        continue
    if min(cy, cx, H - 1 - cy, W - 1 - cx) < EDGE_PIN:  # the canvas edge is a border too
        snapped[i] = (cy, cx)
        continue
    y0, y1, x0, x1 = max(cy - NODE_SNAP, 0), min(cy + NODE_SNAP + 1, H), max(cx - NODE_SNAP, 0), min(cx + NODE_SNAP + 1, W)
    yy, xx = np.ogrid[y0 - cy:y1 - cy, x0 - cx:x1 - cx]
    score = ink_cost[y0:y1, x0:x1] + 0.03 * np.hypot(yy, xx)
    ky, kx = np.unravel_index(np.argmin(score), score.shape)
    snapped[i] = (ky + y0, kx + x0)

runs = sk & (nl == 0)
rl, n = ndi.label(runs, EIGHT)
out = np.zeros_like(drawn)
moved = []
for j, sl in enumerate(ndi.find_objects(rl), 1):
    if sl is None:
        continue
    pad = CORRIDOR + NODE_SNAP + 2
    y0, y1 = max(sl[0].start - pad, 0), min(sl[0].stop + pad, H)
    x0, x1 = max(sl[1].start - pad, 0), min(sl[1].stop + pad, W)
    run = rl[y0:y1, x0:x1] == j
    touch = [t for t in np.unique(nl[y0:y1, x0:x1][ndi.binary_dilation(run, np.ones((3, 3), bool))]) if t]
    ry, rx = np.nonzero(run)
    edge_d = np.minimum.reduce([ry + y0, rx + x0, H - 1 - (ry + y0), W - 1 - (rx + x0)])
    if np.median(edge_d) < EDGE_PIN:
        out[y0:y1, x0:x1] |= run
        continue
    if len(touch) != 2:
        out[y0:y1, x0:x1] |= run                       # closed loops etc.: keep as drawn
        continue
    (ay, ax), (by, bx) = snapped[touch[0]], snapped[touch[1]]
    if not (y0 <= ay < y1 and x0 <= ax < x1 and y0 <= by < y1 and x0 <= bx < x1):
        out[y0:y1, x0:x1] |= run
        continue
    dist = ndi.distance_transform_edt(~run)
    c = ink_cost[y0:y1, x0:x1] + DIST_W * (dist / CORRIDOR) ** 2
    c = np.where(dist <= CORRIDOR, c, 1e3)
    c = np.where(deep[y0:y1, x0:x1] & (dist > FILL_KEEP), 1e3, c)
    for (py, px) in ((ay, ax), (by, bx)):                 # let the ends reach their nodes
        yy, xx = np.ogrid[y0 - py:y1 - py, x0 - px:x1 - px]
        near = (yy * yy + xx * xx) <= (NODE_SNAP + 3) ** 2
        c = np.where(near, np.minimum(c, ink_cost[y0:y1, x0:x1] + DIST_W), c)
    # a run that loops (island outline between two neighbouring junctions) would
    # collapse to the short hop between its ends: route it through its far point
    stops = [(ay - y0, ax - x0)]
    if np.hypot(ay - by, ax - bx) < LOOP_RATIO * run.sum():
        dfar = np.hypot(ry - (ay - y0), rx - (ax - x0)) + np.hypot(ry - (by - y0), rx - (bx - x0))
        k = int(np.argmax(dfar))
        stops.append((int(ry[k]), int(rx[k])))
    stops.append((by - y0, bx - x0))
    path = np.concatenate([np.asarray(route_through_array(c, u, v, fully_connected=True, geometric=True)[0])
                           for u, v in zip(stops, stops[1:])])
    out[path[:, 0] + y0, path[:, 1] + x0] = True
    moved.append(float(np.median(dist[path[:, 0], path[:, 1]])))
# nodes join their runs
for i, (py, px) in snapped.items():
    out[py, px] = True
out = skeletonize(ndi.binary_dilation(out, disk(1)))


def free_ends(sk):
    return sk & (nbr_count(sk) == 1)


def reconnect(out, reach):
    """Join each free end the drawing did not have to the nearest other branch."""
    from skimage.draw import line as draw_line
    orig_ends = ndi.binary_dilation(free_ends(sk), disk(12))
    res = out.copy()
    for y, x in np.argwhere(free_ends(out) & ~orig_ends):
        y0, y1, x0, x1 = max(y - reach, 0), min(y + reach + 1, H), max(x - reach, 0), min(x + reach + 1, W)
        win = out[y0:y1, x0:x1]
        own = np.zeros_like(win)
        own[y - y0, x - x0] = True
        for _ in range(reach + 4):
            own = ndi.binary_dilation(own, np.ones((3, 3), bool)) & win
        pts = np.argwhere(win & ~own)
        if not len(pts):
            continue
        d = np.hypot(pts[:, 0] + y0 - y, pts[:, 1] + x0 - x)
        k = d.argmin()
        rr, cc = draw_line(y, x, pts[k, 0] + y0, pts[k, 1] + x0)
        res[rr, cc] = True
    return res


out = reconnect(out, RECONNECT)

paint = ndi.binary_dilation(out, disk(PAINT_R))
four = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])
cells, _ = ndi.label(~paint, four)
paint |= (np.bincount(cells.ravel()) < SLIVER)[cells] & (cells > 0)   # re-route loops
lay = np.zeros((H, W, 4), np.uint8)
lay[paint] = (*MAGENTA, 255)
Image.fromarray(lay).save(OUT / "borders_aligned.png")
np.save(OUT / "aligned_skeleton.npy", out)

# review renders
base = surface[..., :3].copy()
rev = base.copy()
rev[ndi.binary_dilation(sk, disk(1))] = (150, 150, 150)
rev[ndi.binary_dilation(out, disk(1))] = MAGENTA
Image.fromarray(rev).resize((W // 4, H // 4), Image.LANCZOS).save(OUT / "aligned_overview.png")
tiles = OUT / "aligned_tiles"
tiles.mkdir(exist_ok=True)
for f in tiles.glob("*.png"):
    f.unlink()
land = surface[..., 3] > 0
T = 400
for ty in range(0, H, T):
    for tx in range(0, W, T):
        if drawn[ty:ty + T, tx:tx + T].sum() < 500:
            continue
        a = base[ty:ty + T, tx:tx + T]
        b = rev[ty:ty + T, tx:tx + T]
        Image.fromarray(np.hstack([a, b])).save(tiles / f"a_{tx}_{ty}.png")
print("runs", n, "nodes", nn, "median offset moved px: p50 %.1f p90 %.1f p99 %.1f"
      % tuple(np.percentile(moved, [50, 90, 99])))
print("drawn px", int(drawn.sum()), "aligned px", int(paint.sum()))


def write_ora_copy(dst, new_borders):
    """Copy ORA with its ``borders`` layer replaced; mergedimage recomposited from
    the visible layers (bottom-up, src-over), every other entry byte-identical."""
    import io
    import xml.etree.ElementTree as ET
    root = ET.fromstring(z.read("stack.xml"))
    layers = list(root.iter("layer"))
    bsrc = next(l.get("src") for l in layers if l.get("name") == "borders")
    buf = io.BytesIO()
    Image.fromarray(new_borders).save(buf, "PNG")
    comp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for l in reversed(layers):
        if l.get("visibility") == "hidden":
            continue
        im = Image.fromarray(new_borders) if l.get("src") == bsrc else Image.open(z.open(l.get("src"))).convert("RGBA")
        comp = Image.alpha_composite(comp, im)
    mbuf = io.BytesIO()
    comp.save(mbuf, "PNG")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in z.infolist():
            if info.filename == bsrc:
                data = buf.getvalue()
            elif info.filename == "mergedimage.png":
                data = mbuf.getvalue()
            else:
                data = z.read(info.filename)
            zo.writestr(info, data, compress_type=info.compress_type)


write_ora_copy(OUT / "iee_parchment - borders_aligned.ora", lay)
print("wrote", OUT / "iee_parchment - borders_aligned.ora")
