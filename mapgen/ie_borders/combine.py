"""Merge the climate-derived and parchment-derived border skeletons, class and paint.

Climate segments are kept only where the parchment has ink under them (its region layout
differs in places, e.g. Cathay). Parchment-detected lines fill what the climate pass
lacks. Every segment is classed by the parchment's own ink darkness: thick (TW province)
magenta, thin (TW state) red.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "scratchpad" / "ie_borders"   # intermediates, git-ignored
HERE.mkdir(parents=True, exist_ok=True)
import json
OVERRIDES = ROOT / "mapgen" / "config" / "ie_border_overrides.json"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "sources" / "tww3_ie_parchment - state_borders.png"

CONFIRM_V = 165      # a climate segment must have parchment ink this dark beside it
CONFIRM_WIN = 7
CONFIRM_REACH = 3
CONFIRM_FRAC = 0.7
COVER = 6            # parchment lines this close to a kept climate line are duplicates
ADD_MIN = 60
ADD_SIDE = 45         # added parchment pieces at least this many px
THICK_V = 100.0
CLASS_WIN = 3
CAND_MIN = 20
TEXT_V = 110
TEXT_MIN = 40
WORD_GROW, WORD_CORE = 4, 7
NODE_SNAP, CORRIDOR = 10, 14
SNAP, SPUR = 12, 30
ADD_COMPACT = 2.2
PAINT_THICK, PAINT_THIN = 2, 1
MAGENTA, RED = (255, 0, 255), (255, 0, 0)
EIGHT = np.ones((3, 3), int)


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def nbr_count(sk):
    return ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - sk


def prune(sk, n):
    orig, sk = sk.copy(), sk.copy()
    for _ in range(n):
        sk &= ~(sk & (nbr_count(sk) == 1))
    for _ in range(n):
        ends = sk & (nbr_count(sk) <= 1)
        grow = ndi.binary_dilation(ends, np.ones((3, 3), bool)) & orig & ~sk
        if not grow.any():
            break
        sk |= grow
    return sk


def runs_of(sk):
    junction = sk & (nbr_count(sk) >= 3)
    runs = sk & ~ndi.binary_dilation(junction, np.ones((3, 3), bool))
    rl, n = ndi.label(runs, EIGHT)
    return runs, rl, n


def snap_ends(sk, reach):
    from skimage.draw import line as draw_line
    Hh, Ww = sk.shape
    out = sk.copy()
    for y, x in np.argwhere(sk & (nbr_count(sk) == 1)):
        y0, y1, x0, x1 = max(y - reach, 0), min(y + reach + 1, Hh), max(x - reach, 0), min(x + reach + 1, Ww)
        win = sk[y0:y1, x0:x1]
        own = np.zeros_like(win)
        own[y - y0, x - x0] = True
        for _ in range(reach + 2):
            own = ndi.binary_dilation(own, np.ones((3, 3), bool)) & win
        pts = np.argwhere(win & ~own)
        if not len(pts):
            continue
        d = np.hypot(pts[:, 0] + y0 - y, pts[:, 1] + x0 - x)
        k = d.argmin()
        if d[k] <= reach:
            rr, cc = draw_line(y, x, pts[k, 0] + y0, pts[k, 1] + x0)
            out[rr, cc] = True
    return out


master = np.array(Image.open(ROOT / "sources/originals/tww3_ie_parchment.jpg").convert("RGB"))
V = master.max(2).astype(np.float32)
vmin = ndi.minimum_filter(V, CONFIRM_WIN)


def text_mask():
    """Lettering on the parchment: dark ink where the climate sibling (same frame,
    same labels) shows a tinted stroke rather than one of its black lines."""
    c = np.array(Image.open(ROOT / "sources/originals/tww3_climate.jpg").convert("RGB")
                 .resize((V.shape[1], V.shape[0]), Image.BICUBIC)).astype(np.float32)
    cV = c.max(2)
    dev = np.zeros(cV.shape, np.float32)
    for k in range(3):
        dev = np.maximum(dev, np.abs(c[..., k] - ndi.median_filter(c[..., k], 9)))
    tint = (dev > 14) & (cV > 75) & ~ndi.binary_dilation(cV < 60, disk(2))
    return (V < TEXT_V) & ndi.binary_dilation(tint, np.ones((3, 3), bool))


text = ndi.binary_dilation(text_mask(), np.ones((3, 3), bool))
tl, _ = ndi.label(text, EIGHT)
text &= (np.bincount(tl.ravel()) >= TEXT_MIN)[tl]   # letters, not specks on line edges
# a word is a dense blob ~20 px tall; a grey/dashed climate line passes the tint test
# too but stays a few px wide, so only ink near a word-sized core counts
core = ndi.binary_erosion(ndi.binary_dilation(text, disk(WORD_GROW)), disk(WORD_CORE))
text &= ndi.binary_dilation(core, disk(WORD_GROW + WORD_CORE + 2))
np.save(HERE / "text.npy", text)
V = np.where(text, 230.0, V)          # lettering reads as paper from here on

clim = np.load(HERE / "sk_climate.npy")
parch = np.load(HERE / "sk_parch.npy")

# 1. climate runs confirmed by parchment ink
plines = ndi.binary_dilation(np.load(HERE / "lines_parch.npy"), disk(CONFIRM_REACH)).astype(np.float32)
runs, rl, n = runs_of(clim)
on = np.concatenate([[1.0], np.asarray(ndi.mean(plines, rl, index=np.arange(1, n + 1)))])
bad_runs = (on < CONFIRM_FRAC)[rl] & runs
kept = clim & ~bad_runs
np.save(HERE / "dropped_climate.npy", bad_runs)
kept = prune(kept, SPUR)

# 2. parchment lines not already covered
add = parch & ~ndi.binary_dilation(kept, disk(COVER))
al, _ = ndi.label(add, EIGHT)
sizes = np.bincount(al.ravel())
ok = np.zeros(al.max() + 1, bool)
for i, sl in enumerate(ndi.find_objects(al), 1):
    side = max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start)
    ok[i] = sizes[i] >= ADD_MIN and side >= ADD_SIDE and sizes[i] <= ADD_COMPACT * side + 40
add = ok[al] & add
add[0:1] = False

sk = skeletonize(ndi.binary_dilation(kept | add, disk(1)))
sk = snap_ends(sk, SNAP)
sk = prune(sk, 10)


def snap_to_ink(sk):
    """Re-route every junction-to-junction run along the darkest ink near it.

    The climate sibling's lines sit up to ~10 px off the parchment's own ink in
    places. Nodes (junctions, free ends) move to the darkest pixel within NODE_SNAP;
    each run is then re-drawn as the least-cost path between its two nodes, confined
    to a CORRIDOR-wide band around where it was.
    """
    from skimage.graph import route_through_array
    Hh, Ww = sk.shape
    Vs = ndi.gaussian_filter(V, 1.0)
    cost_all = (Vs / 255.0) ** 4 + 0.002
    nc = nbr_count(sk)
    nodes = sk & ((nc >= 3) | (nc == 1))
    nl, nn = ndi.label(ndi.binary_dilation(nodes, disk(2)), EIGHT)
    snapped = {}
    for i, sl in enumerate(ndi.find_objects(nl), 1):
        cy, cx = [int(round(c)) for c in ndi.center_of_mass(nl[sl] == i)]
        cy += sl[0].start
        cx += sl[1].start
        y0, y1, x0, x1 = max(cy - NODE_SNAP, 0), min(cy + NODE_SNAP + 1, Hh), max(cx - NODE_SNAP, 0), min(cx + NODE_SNAP + 1, Ww)
        win = Vs[y0:y1, x0:x1] + 0.5 * np.hypot(*np.ogrid[y0 - cy:y1 - cy, x0 - cx:x1 - cx])
        ky, kx = np.unravel_index(np.argmin(win), win.shape)
        snapped[i] = (ky + y0, kx + x0)
    runs = sk & (nl == 0)
    rl, n = ndi.label(runs, EIGHT)
    out = np.zeros_like(sk)
    for j, sl in enumerate(ndi.find_objects(rl), 1):
        if sl is None:
            continue
        pad = CORRIDOR + 2
        y0, y1 = max(sl[0].start - pad, 0), min(sl[0].stop + pad, Hh)
        x0, x1 = max(sl[1].start - pad, 0), min(sl[1].stop + pad, Ww)
        run = rl[y0:y1, x0:x1] == j
        touch = np.unique(nl[y0:y1, x0:x1][ndi.binary_dilation(run, np.ones((3, 3), bool))])
        touch = [t for t in touch if t]
        if len(touch) != 2:
            out[y0:y1, x0:x1] |= run           # loops / odd runs stay as they are
            continue
        (ay, ax), (by, bx) = snapped[touch[0]], snapped[touch[1]]
        if not (y0 <= ay < y1 and x0 <= ax < x1 and y0 <= by < y1 and x0 <= bx < x1):
            out[y0:y1, x0:x1] |= run
            continue
        band = ndi.binary_dilation(run, disk(CORRIDOR))
        band[ay - y0, ax - x0] = band[by - y0, bx - x0] = True
        for (py, px) in ((ay, ax), (by, bx)):
            yy, xx = np.ogrid[y0 - py:y1 - py, x0 - px:x1 - px]
            band |= (yy * yy + xx * xx) <= (NODE_SNAP + 2) ** 2
        c = np.where(band, cost_all[y0:y1, x0:x1], 1e3)
        path, _ = route_through_array(c, (ay - y0, ax - x0), (by - y0, bx - x0),
                                      fully_connected=True, geometric=True)
        path = np.asarray(path)
        out[path[:, 0] + y0, path[:, 1] + x0] = True
    return skeletonize(ndi.binary_dilation(out, disk(1)))


sk = snap_to_ink(sk)

# 3. class by parchment darkness
vcls = ndi.minimum_filter(V, CLASS_WIN)
runs, rl, n = runs_of(sk)
med = np.concatenate([[255.0], np.asarray(ndi.median(vcls, rl, index=np.arange(1, n + 1)))])
thick = (med < THICK_V)[rl] & runs
np.save(HERE / "paper_runs.npy", (med >= 180)[rl] & runs)
thin = runs & ~thick
joints = sk & ~runs
thick |= joints & ndi.binary_dilation(thick, disk(3))
thin |= joints & ~thick


def apply_overrides(thick, thin):
    """Hand-authored fixes, master-frame pixels. Edit deliberately and re-run.

    Applied in order reclass, add, erase, paint.
    ``erase``   [x, y, w, h] boxes: every traced pixel inside goes.
    ``reclass`` {"box": [x, y, w, h], "class": "thick"|"thin"}: traced pixels inside
                change class.
    ``add``     [x, y, w, h] boxes: every line-shaped piece of parchment ink inside
                (the review candidates) is added, classed by its darkness.
    ``paint``   {"class": ..., "points": [[x, y], ...]}: a line through the points,
                each leg routed along the darkest ink between them (so points only
                need to sit on the line, not trace it); ``"straight": true`` draws
                plain straight legs instead.
    """
    from skimage.draw import line as draw_line
    from skimage.graph import route_through_array
    if not OVERRIDES.exists():
        return thick, thin
    ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    for r in ov.get("reclass", []):
        x, y, w, h = r["box"]
        both = thick[y:y + h, x:x + w] | thin[y:y + h, x:x + w]
        thick[y:y + h, x:x + w] = both if r["class"] == "thick" else False
        thin[y:y + h, x:x + w] = both if r["class"] == "thin" else False
    for x, y, w, h in ov.get("add", []):
        thick[y:y + h, x:x + w] |= cand_thick[y:y + h, x:x + w]
        thin[y:y + h, x:x + w] |= cand_thin[y:y + h, x:x + w]
    for x, y, w, h in ov.get("erase", []):
        thick[y:y + h, x:x + w] = False
        thin[y:y + h, x:x + w] = False
    cost = (V / 255.0) ** 4 + 0.002
    for r in ov.get("paint", []):
        tgt = thick if r["class"] == "thick" else thin
        pts = r["points"]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if r.get("straight"):
                rr, cc = draw_line(y0, x0, y1, x1)
            else:
                pad = 12
                bx0, by0 = max(min(x0, x1) - pad, 0), max(min(y0, y1) - pad, 0)
                bx1, by1 = min(max(x0, x1) + pad + 1, V.shape[1]), min(max(y0, y1) + pad + 1, V.shape[0])
                path, _ = route_through_array(cost[by0:by1, bx0:bx1], (y0 - by0, x0 - bx0),
                                              (y1 - by0, x1 - bx0), fully_connected=True, geometric=True)
                path = np.asarray(path)
                rr, cc = path[:, 0] + by0, path[:, 1] + bx0
            tgt[rr, cc] = True
    return thick, thin


lines_p = np.load(HERE / "lines_parch.npy") & ~text
cand = prune(skeletonize(lines_p), 10)
cl, _ = ndi.label(cand, EIGHT)
cand &= (np.bincount(cl.ravel()) >= CAND_MIN)[cl]
cand_runs, crl, cn = runs_of(cand)
cmed = np.concatenate([[255.0], np.asarray(ndi.median(vcls, crl, index=np.arange(1, cn + 1)))])
cand_thick = (cmed < THICK_V)[crl] & cand_runs
cand_thin = cand & ~cand_thick
thick, thin = apply_overrides(thick, thin)
np.save(HERE / "cand_missing.npy", cand & ~ndi.binary_dilation(thick | thin, disk(5)))

np.savez_compressed(HERE / "skeletons.npz", thick=thick, thin=thin)
out = master.copy()
out[ndi.binary_dilation(thin, disk(PAINT_THIN))] = RED
out[ndi.binary_dilation(thick, disk(PAINT_THICK))] = MAGENTA
Image.fromarray(out).save(OUT)
Image.fromarray(out).resize((1851, 1440), Image.LANCZOS).save(HERE / "traced_half.png")
for name, (x0, y0) in {"crop_empire": (1200, 900), "crop_cathay": (2900, 1100),
                       "crop_lustria": (100, 1700), "crop_naggaroth": (0, 300),
                       "crop_southlands": (1300, 1900), "crop_ulthuan": (400, 700),
                       "crop_darklands": (2100, 700), "crop_norsca": (900, 150),
                       "crop_bretonnia": (850, 900)}.items():
    Image.fromarray(out[y0:y0 + 700, x0:x0 + 900]).save(HERE / f"{name}.png")
print("climate kept", int(kept.sum()), "dropped", int(bad_runs.sum()), "parch added", int(add.sum()))
print("thick", int(thick.sum()), "thin", int(thin.sum()))
print("class hist", list(np.histogram(med[1:], bins=24, range=(0, 240))[0]))
