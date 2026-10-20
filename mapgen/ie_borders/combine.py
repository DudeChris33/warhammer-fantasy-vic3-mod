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
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "sources" / "tww3_ie_parchment - state_borders.png"

CONFIRM_V = 165      # a climate segment must have parchment ink this dark beside it
CONFIRM_WIN = 7
CONFIRM_REACH = 3
CONFIRM_FRAC = 0.7
COVER = 6            # parchment lines this close to a kept climate line are duplicates
ADD_MIN = 60
ADD_SIDE = 45         # added parchment pieces at least this many px
THICK_V = 90.0
CLASS_WIN = 7
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

clim = np.load(HERE / "sk_climate.npy")
parch = np.load(HERE / "sk_parch.npy")

# 1. climate runs confirmed by parchment ink
plines = ndi.binary_dilation(np.load(HERE / "lines_parch.npy"), disk(CONFIRM_REACH)).astype(np.float32)
runs, rl, n = runs_of(clim)
on = np.concatenate([[1.0], np.asarray(ndi.mean(plines, rl, index=np.arange(1, n + 1)))])
bad_runs = (on < CONFIRM_FRAC)[rl] & runs
kept = clim & ~bad_runs
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

# 3. class by parchment darkness
vcls = ndi.minimum_filter(V, CLASS_WIN)
runs, rl, n = runs_of(sk)
med = np.concatenate([[255.0], np.asarray(ndi.median(vcls, rl, index=np.arange(1, n + 1)))])
thick = (med < THICK_V)[rl] & runs
thin = runs & ~thick
joints = sk & ~runs
thick |= joints & ndi.binary_dilation(thick, disk(3))
thin |= joints & ~thick

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
