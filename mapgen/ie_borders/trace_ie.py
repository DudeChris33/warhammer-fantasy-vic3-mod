"""Trace the IE parchment's printed borders: thick (TW province) magenta, thin (TW state) red.

One line mask (dark ink | local-contrast ridges) on land (climate-sibling silhouette,
eroded off the coast ink), minus lakes / painted rivers (wide fills), road and river
ribbons (paired rails around a long light gap) and lettering (compact word blobs, short
spurs). Skeletonized, cut at junctions, and each segment classed thick/thin by the median
darkness of the ink under it.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from skimage.filters import apply_hysteresis_threshold

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "scratchpad" / "ie_borders"   # intermediates, git-ignored
HERE.mkdir(parents=True, exist_ok=True)
SRC = ROOT / "sources/originals/tww3_ie_parchment.jpg"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "traced_parch.png"

HI, LO = 112, 142
COAST_ERODE = 7
WIDE_EDT = 2.9
WIDE_REACH = 20
TEXT_BOX, TEXT_JUNCTIONS, TEXT_RUN = 31, 4, 40
COMP_MIN_SIDE = 70
LOOP_AREA = 350      # skeleton loops enclosing less than this are letter counters
SPUR_LATE = 30
SNAP = 10
RIDGE_BG, RIDGE_T = 11, 24
GAP_CLOSE, GAP_MIN_LEN, RAIL_REACH = 3, 30, 2
MIN_COMP = 40
SPUR = 14
GLYPH_AREA, GLYPH_SIDE, GLYPH_ELONG = 3500, 160, 16.0
THICK_V = float(sys.argv[2]) if len(sys.argv) > 2 else 95.0
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


def drop_words(mask):
    closed = ndi.binary_closing(mask, disk(2))
    lbl, _ = ndi.label(closed, EIGHT)
    out = mask.copy()
    for i, sl in enumerate(ndi.find_objects(lbl), 1):
        comp = (lbl[sl] == i) & mask[sl]
        area = comp.sum()
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if area and area <= GLYPH_AREA and max(h, w) <= GLYPH_SIDE and (h * h + w * w) / area <= GLYPH_ELONG:
            out[sl][comp] = False
    return out


rgb = np.array(Image.open(SRC).convert("RGB"))
V = rgb.max(2).astype(np.float32)
land = ndi.binary_erosion(np.array(Image.open(HERE / "land_mask.png")) > 127, disk(COAST_ERODE))

ink = apply_hysteresis_threshold(-V, -LO, -HI) & land
edt = ndi.distance_transform_edt(ink)
wide = ndi.binary_propagation(edt >= WIDE_EDT, mask=ink & ndi.binary_dilation(edt >= WIDE_EDT, disk(WIDE_REACH)))

R = ndi.median_filter(V, RIDGE_BG) - V
ridge = (R > RIDGE_T) & land
# rivers: the climate sibling paints them as a brown fill registered exactly to this frame
crgb = np.array(Image.open(ROOT / "sources/originals/tww3_climate.jpg").convert("RGB")).astype(np.int16)
cV, cch = crgb.max(2), crgb[..., 0] - crgb[..., 2]
criver = ndi.binary_opening((cV < 140) & (cch >= 35) & (crgb[..., 0] - crgb[..., 1] >= 18), disk(1))
clbl, _ = ndi.label(criver, EIGHT)
criver = (np.bincount(clbl.ravel()) >= 60)[clbl] & criver
river = np.array(Image.fromarray(criver.astype(np.uint8) * 255).resize(V.shape[::-1], Image.NEAREST)) > 0
river = ndi.binary_dilation(river, disk(5))
lines = (ridge | ink) & ~wide & ~river

# ribbons: the light gap a closing fills between two rails, kept only where it runs long
gap = ndi.binary_closing(lines, disk(GAP_CLOSE)) & ~lines & land
glbl, _ = ndi.label(gap, EIGHT)
keep = np.zeros(glbl.max() + 1, bool)
for i, sl in enumerate(ndi.find_objects(glbl), 1):
    h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    if max(h, w) >= GAP_MIN_LEN:
        keep[i] = True
gap_long = keep[glbl]
rails = ndi.binary_dilation(gap_long, disk(RAIL_REACH)) & lines
# a dark thick border never has a light gap inside it; only drop pale rails
lines &= ~(rails & (V > HI))

np.save(HERE / "lines_parch.npy", lines)
lines = drop_words(lines)
sk = prune(skeletonize(ndi.binary_closing(lines, disk(1))), SPUR)


def drop_small(sk):
    lbl, _ = ndi.label(sk, EIGHT)
    keep = np.zeros(lbl.max() + 1, bool)
    sizes = np.bincount(lbl.ravel())
    for i, sl in enumerate(ndi.find_objects(lbl), 1):
        side = max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start)
        keep[i] = sizes[i] >= MIN_COMP and side >= COMP_MIN_SIDE
    return keep[lbl]


def drop_text_runs(sk):
    # lettering welded to a border skeletonizes into a knot: many junctions close
    # together, joined by short runs. Borders branch every ~50+ px at most.
    for _ in range(3):
        junction = sk & (nbr_count(sk) >= 3)
        jl, nj = ndi.label(ndi.binary_dilation(junction, disk(2)), EIGHT)
        centres = np.zeros_like(sk)
        if nj:
            cy, cx = np.array(ndi.center_of_mass(np.ones_like(sk), jl, range(1, nj + 1))).astype(int).T
            centres[cy, cx] = True
        dens = ndi.uniform_filter(centres.astype(np.float32), TEXT_BOX) * TEXT_BOX ** 2
        runs = sk & ~ndi.binary_dilation(junction, np.ones((3, 3), bool))
        rl, n = ndi.label(runs, EIGHT)
        if not n:
            break
        length = np.bincount(rl.ravel())
        rd = np.asarray(ndi.maximum(dens, rl, index=np.arange(1, n + 1)))
        bad = np.concatenate([[False], (length[1:] < TEXT_RUN) & (rd >= TEXT_JUNCTIONS - 0.5)])
        if not bad.any():
            break
        sk = sk & ~bad[rl]
        sk = prune(sk, SPUR)
    return sk


sk = drop_small(sk)
sk = drop_small(drop_text_runs(sk))


def drop_small_loops(sk):
    holes = ndi.binary_fill_holes(sk) & ~sk
    hl, _ = ndi.label(holes)
    small = (np.bincount(hl.ravel()) < LOOP_AREA)[hl] & holes
    # the skeleton ring around a small hole goes; shared walls with big cells stay
    ring = ndi.binary_dilation(small, np.ones((3, 3), bool)) & sk
    big = ndi.binary_dilation(holes & ~small, np.ones((3, 3), bool)) | ~ndi.binary_dilation(holes, np.ones((3, 3), bool))
    return sk & ~(ring & ~(ndi.binary_dilation(holes & ~small, np.ones((3, 3), bool))))


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


sk = drop_small_loops(sk)
sk = snap_ends(sk, SNAP)
sk = drop_small(prune(sk, SPUR_LATE))
np.save(HERE / "sk_parch.npy", sk)

# cut at junctions, class each run by median darkness of the ink beside it
junction = sk & (nbr_count(sk) >= 3)
runs = sk & ~ndi.binary_dilation(junction, np.ones((3, 3), bool))
rl, n = ndi.label(runs, EIGHT)
vmin = ndi.minimum_filter(V, 5)
med = ndi.median(vmin, rl, index=np.arange(1, n + 1))
med = np.concatenate([[255.0], np.asarray(med)])
np.save(HERE / "seg_med.npy", med[1:])
thick_runs = (med < THICK_V)[rl] & runs
thin_runs = runs & ~thick_runs
joints = sk & ~runs
sk_thick = thick_runs | (joints & ndi.binary_dilation(thick_runs, disk(3)))
sk_thin = thin_runs | (joints & ~sk_thick)

np.savez_compressed(HERE / "skeletons.npz", thick=sk_thick, thin=sk_thin)
out = rgb.copy()
out[ndi.binary_dilation(sk_thin, disk(PAINT_THIN))] = RED
out[ndi.binary_dilation(sk_thick, disk(PAINT_THICK))] = MAGENTA
Image.fromarray(out).save(OUT)
Image.fromarray(out).resize((1851, 1440), Image.LANCZOS).save(HERE / "traced_half.png")
for name, (x0, y0) in {"crop_empire": (1200, 900), "crop_cathay": (2900, 1100),
                       "crop_lustria": (100, 1700), "crop_naggaroth": (0, 300),
                       "crop_southlands": (1300, 1900), "crop_ulthuan": (400, 700),
                       "crop_darklands": (2100, 700)}.items():
    Image.fromarray(out[y0:y0 + 700, x0:x0 + 900]).save(HERE / f"{name}.png")
h = np.histogram(med[1:], bins=24, range=(0, 240))
print("segments", n, "thick px", int(sk_thick.sum()), "thin px", int(sk_thin.sum()))
print([(int(a), int(b)) for a, b in zip(h[1][:-1], h[0])])

if "--debug" in sys.argv:
    dbg = (rgb * 0.5 + 127).astype(np.uint8)
    dbg[ridge] = (120, 120, 120)
    dbg[rails & (V > HI)] = (0, 90, 255)
    dbg[(ridge | ink) & wide] = (0, 200, 200)
    dbg[gap_long] = (255, 220, 0)
    dbg[sk_thin] = (255, 0, 0)
    dbg[sk_thick] = (255, 0, 255)
    for name, (x0, y0) in {"dbg_empire": (1300, 950), "dbg_cathay": (2950, 1150)}.items():
        Image.fromarray(dbg[y0:y0 + 400, x0:x0 + 450]).resize((900, 800), Image.NEAREST).save(HERE / f"{name}.png")
