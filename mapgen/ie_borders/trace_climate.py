"""Trace IE borders from the climate-map sibling, paint them on the parchment master.

The climate map (exact 2471/3703 rescale of tww3_ie_parchment.jpg) draws TW province
borders as solid black and TW state borders as black dashes, with lettering as a pale
tint and roads faint, so neither interferes. Thick (solid) -> magenta, thin (dashed) -> red.
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
sys.path.insert(0, str(ROOT / "mapgen"))
from worldgen import parchment, segment, sources  # noqa: E402

MASTER = ROOT / "sources/originals/tww3_ie_parchment.jpg"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "traced_climate.png"
LEGEND = (2040, 0, 2471, 400)

INK_DROP, INK_MAX = 45, 130   # ink: this much darker than the local fill, and dark
SOLID_COMP = 30      # 8-connected ink pieces this big are solid strokes; less = dashes
DASH_BRIDGE = 3
SNAP = 7             # thin endpoints reach to a line within this many px
LINE_V = 90
LINE_CHROMA = 35     # ... and near-neutral (R-B below this); river fill is brown
SOLID_V = 62         # solid stroke core
ON_INK_V = int(sys.argv[3]) if len(sys.argv) > 3 else 110
RIVER_V, RIVER_GROW = 140, 3
COAST_ERODE = 3
BRIDGE = 2           # closing radius that joins dashes into one line
SPUR, MIN_COMP, MIN_SIDE = 6, 12, 18
THICK_V = float(sys.argv[2]) if len(sys.argv) > 2 else 92.0
CLASS_WIN = 7
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


def drop_small(sk, min_px, min_side):
    lbl, _ = ndi.label(sk, EIGHT)
    sizes = np.bincount(lbl.ravel())
    keep = np.zeros(lbl.max() + 1, bool)
    for i, sl in enumerate(ndi.find_objects(lbl), 1):
        keep[i] = sizes[i] >= min_px and max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) >= min_side
    return keep[lbl]


rgb = sources.load_source_image("tww3_climate.jpg").astype(np.int16)
H, W = rgb.shape[:2]
V = rgb.max(2)
chroma = rgb[..., 0] - rgb[..., 2]

land = parchment.painted_mask(rgb.astype(np.uint8), exclude=[LEGEND])
land = segment.drop_small_components(land, 400, wrap_x=False)
land = ~segment.drop_small_components(~land, 400, wrap_x=False)
land = ndi.binary_erosion(land, disk(COAST_ERODE))

river = (V < RIVER_V) & (chroma >= LINE_CHROMA) & (rgb[..., 0] - rgb[..., 1] >= 18)   # brown, not olive jungle
river = ndi.binary_opening(river, disk(1))                   # fills, not stray pixels
river = segment.drop_small_components(river, 60, wrap_x=False)
river = ndi.binary_dilation(river, disk(RIVER_GROW))

bg = ndi.median_filter(V, 11)
ink = (V < np.minimum(bg - INK_DROP, INK_MAX)) & land & ~river
line = ink


def snap_ends(sk, reach):
    """Join each free endpoint to the nearest pixel of a different branch within reach."""
    from skimage.draw import line as draw_line
    out = sk.copy()
    for y, x in np.argwhere(sk & (nbr_count(sk) == 1)):
        y0, y1, x0, x1 = max(y - reach, 0), min(y + reach + 1, H), max(x - reach, 0), min(x + reach + 1, W)
        win = sk[y0:y1, x0:x1].copy()
        # mask out the endpoint's own branch: pixels reachable within `reach` steps
        own = np.zeros_like(sk[y0:y1, x0:x1])
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


sk = skeletonize(ndi.binary_dilation(ink, disk(DASH_BRIDGE)))
sk = drop_small(prune(sk, SPUR), MIN_COMP, MIN_SIDE)
sk = snap_ends(sk, SNAP)

# up to the master frame (exact rescale): nearest-resample, re-skeletonize, prune
master = np.array(Image.open(MASTER).convert("RGB"))
MH, MW = master.shape[:2]
big = np.array(Image.fromarray(ndi.binary_dilation(sk, disk(1)).astype(np.uint8) * 255).resize((MW, MH), Image.NEAREST)) > 0
msk = prune(skeletonize(big), 8)
np.save(HERE / "sk_climate.npy", msk)

# class each junction-to-junction run by the parchment's own ink darkness beside it
mV = master.max(2).astype(np.float32)
vmin = ndi.minimum_filter(mV, CLASS_WIN)
junction = msk & (nbr_count(msk) >= 3)
runs = msk & ~ndi.binary_dilation(junction, np.ones((3, 3), bool))
rl, n = ndi.label(runs, EIGHT)
med = np.concatenate([[255.0], np.asarray(ndi.median(vmin, rl, index=np.arange(1, n + 1)))])
np.save(HERE / "seg_med.npy", med[1:])
m_thick = (med < THICK_V)[rl] & runs
m_thin = runs & ~m_thick
joints = msk & ~runs
m_thick |= joints & ndi.binary_dilation(m_thick, disk(3))
m_thin |= joints & ~m_thick

np.savez_compressed(HERE / "skeletons.npz", thick=m_thick, thin=m_thin)
out = master.copy()
out[ndi.binary_dilation(m_thin, disk(PAINT_THIN))] = RED
out[ndi.binary_dilation(m_thick, disk(PAINT_THICK))] = MAGENTA
Image.fromarray(out).save(OUT)
Image.fromarray(out).resize((1851, 1440), Image.LANCZOS).save(HERE / "traced_half.png")
for name, (x0, y0) in {"crop_empire": (1200, 900), "crop_cathay": (2900, 1100),
                       "crop_lustria": (100, 1700), "crop_naggaroth": (0, 300),
                       "crop_southlands": (1300, 1900), "crop_ulthuan": (400, 700),
                       "crop_darklands": (2100, 700), "crop_norsca": (900, 150)}.items():
    Image.fromarray(out[y0:y0 + 700, x0:x0 + 900]).save(HERE / f"{name}.png")
h = np.histogram(med[1:], bins=24, range=(0, 240))
print("segments", n, "thick px", int(m_thick.sum()), "thin px", int(m_thin.sum()))
print([(int(a), int(b)) for a, b in zip(h[1][:-1], h[0])])
thick, thin = sk, np.zeros_like(sk)

if "--debug" in sys.argv:
    dbg = (rgb * 0.45 + 140).clip(0, 255).astype(np.uint8)
    dbg[line] = (0, 0, 0)
    dbg[river] = (dbg[river] * 0.5 + np.array([0, 100, 200]) * 0.5).astype(np.uint8)
    dbg[thin] = (255, 0, 0)
    dbg[thick] = (255, 0, 255)
    s = 1 / 1.4985
    for name, (x0, y0) in {"cdbg_empire": (1300, 950), "cdbg_cathay": (2950, 1150)}.items():
        x0, y0 = int(x0 * s), int(y0 * s)
        Image.fromarray(dbg[y0:y0 + 267, x0:x0 + 300]).resize((900, 801), Image.NEAREST).save(HERE / f"{name}.png")
