"""Dev-only: write a cleaned copy of the Terraqueous canvas, cleaned in the globe's own pixels.

The canvas (`terraqueous_globe_reprojected.png`) is the order-1 reprojection of the native globe
(`terraqueous_globe.jpg`, Natural Earth II) onto the Miller frame. Its apparent stretching is the
globe's paper hatch, JPEG noise and lettering enlarged 1.8-4.5x (and sheared toward the top
corners) by that projection change; no geography is misplaced. So this tool cleans the native
globe first, where hatch, noise and line widths are uniform, and re-projects the clean picture
once through the committed fit (`ingest.clamped_source_coords`), at order 3. Registration to the
original canvas holds by construction.

Phase A (this file today):
  * denoise the globe band the canvas samples (non-local means; `--h` sets the strength, sea
    included);
  * find the lon/lat graticule analytically (meridians every 10 deg, parallels every 15 deg),
    centre each strip on the local dark ridge, and fill it from the nearest clean pixel of the
    same kind -- land strips from land only, sea strips from sea only; rivers, coast and long
    slim dark lines inside a strip are never filled;
  * re-project and run the verify block (non-zero exit on failure);
  * write 1:1 original-beside-cleaned review sheets.
Phase B (land lettering and river continuity) is added after the denoise strength is chosen.

Not touched: the original canvas, the source manifest, anything committed under `sources/`. Output
and sheets are git-ignored (`sources/WIP/`, `scratchpad/`). Not part of the offline gate.
Supersedes `remove_map_text.py` and `snap_land_palette.py`, which are left as they are.

Usage (from the repo root):
    mapgen/.venv/Scripts/python.exe mapgen/clean_globe_canvas.py              # write output + sheets
    mapgen/.venv/Scripts/python.exe mapgen/clean_globe_canvas.py --h 0.05 --tag h050 \\
        --out sources/WIP/terraqueous_globe_reprojected_clean_h050.png        # one strength
    mapgen/.venv/Scripts/python.exe mapgen/clean_globe_canvas.py --preview    # class overlay only
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.restoration import denoise_nl_means

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mapgen"))
from worldgen.raster import read_rgb_png  # noqa: E402
from config import canvas_frame  # noqa: E402
from worldgen import ingest, reproject, schema, sources  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TERRAQUEOUS = "terraqueous_globe.jpg"
CANVAS_ORIGINAL = ROOT / "sources" / "originals" / "terraqueous_globe_reprojected.png"
DEFAULT_OUT = ROOT / "sources" / "WIP" / "terraqueous_globe_reprojected_clean.png"
MASK_PATH = ROOT / "mapgen" / "derived" / "land_sea_mask.png"
RIVERS_PATH = ROOT / "map_data" / "rivers.png"
LUT_PATH = ROOT / "mapgen" / "lut" / "terraqueous_elevation.json"
SHEET_DIR = ROOT / "scratchpad"
WIDTH, HEIGHT = canvas_frame.WIDTH, canvas_frame.HEIGHT

NLM_H = 0.035         # non-local-means strength on 0..1 colour; --h overrides
NLM_PATCH, NLM_DIST = 5, 6
BAND_PAD = 4          # globe px kept around the registration crop so order-3 sampling sees real data
MERIDIAN_STEP, PARALLEL_STEP = 10, 15   # degrees between printed graticule lines
GRID_HALF = 2         # strip half-width, globe px (1 px core + 1 px shoulder each side, plus slack)
GRID_SEG = 32         # px per segment when centring a strip on its local ridge
GRID_SEARCH = 2       # px either side of the prediction the ridge is searched in
GRID_GAIN = 1.25      # an off-prediction ridge must beat the predicted position by this factor
GRID_MIN_RIDGE = 2.0  # mean thin-dark level (luminance units) a predicted line must show
GRID_STRAY_FRAC = 0.6 # an unpredicted 5-degree line this strong relative to real ones fails the run
TOPHAT = 12           # luminance below the 9 px median that counts as thin dark
COAST_BAND = 2        # globe px from the land edge within which thin dark line is coast
RIVER_NEAR = 3        # globe px from the river trace within which thin dark line is river
RIVER_MIN_LEN = 40    # a connected thin-dark component this long and slim is a river or a ridge line
RIVER_MAX_FAT = 6.0   # component px per px of bbox diagonal above which it is text, not a line
FILL_BLUR = 1.0       # gaussian sigma applied to filled pixels only
BLOCK_ROWS = 256
SHIFT_MAX = 3         # verify: best integer shift must be (0, 0) within +-this
BAND_BLUR = 2.0       # verify: gaussian sigma (canvas px) applied to both images before counting bands
BAND_LOSS_MAX = 0.03  # verify: no land band loses more than this share of its pixels
RIVER_DARK_NEAR = 2   # verify: canvas px within which a trace pixel must sit near a dark line
RIVER_SLACK = 0.01    # verify: river share may fall at most this far below the original's
COAST_IOU_SLACK = 0.005
COAST_RING = 4        # verify: canvas px ring around the mask edge for the coast difference

WINDOWS = {  # name: canvas (x, y) of a 512 px review window
    "ne_corner": (300, 60), "norsca": (3900, 250), "far_east": (7300, 150), "empire_n": (4000, 600),
    "equator_mid": (4200, 2000), "west": (700, 1100), "south": (4300, 3050), "east_n": (6400, 700),
    "worlds_edge": (4600, 700),
}
WIN = 512


def log(msg: str, t0: float | None = None) -> None:
    print(f"[{time.time() - t0:6.1f}s] {msg}" if t0 else msg, flush=True)


def luminance(a: np.ndarray) -> np.ndarray:
    return a.astype(np.float32) @ np.array([0.3, 0.59, 0.11], np.float32)


def thin_dark(lum: np.ndarray) -> np.ndarray:
    """How far each pixel sits below its 9 px median (thin dark features score high)."""
    return np.maximum(ndi.median_filter(lum, size=9) - lum, 0)


# ---------------------------------------------------------------------------
# Coordinates and masks
# ---------------------------------------------------------------------------

def canvas_to_source(fit, x, y):
    lon, lat = canvas_frame.canvas_to_lonlat(x, y, WIDTH, HEIGHT)
    return fit.to_source(lon, lat)


def land_mask_in_source(fit, x0, y0, x1, y1) -> np.ndarray:
    """Closed canvas land mask, nearest-sampled for every globe pixel of the band."""
    land0 = np.asarray(Image.open(MASK_PATH)).astype(bool)
    land = ndi.binary_closing(land0, np.ones((9, 9), bool))  # rivers cut hairline holes in the fill
    xs = np.arange(x0, x1, dtype=np.float64)[None, :] + 0.5
    ys = np.arange(y0, y1, dtype=np.float64)[:, None] + 0.5
    lon, lat = fit.to_lonlat(xs, ys)           # lat is (H, 1): the inverse bisects on rows only
    cx, cy = canvas_frame.lonlat_to_canvas(lon, lat, WIDTH, HEIGHT)
    cx = np.clip(np.floor(cx).astype(int), 0, WIDTH - 1)
    cy = np.clip(np.floor(np.broadcast_to(cy, cx.shape)).astype(int), 0, HEIGHT - 1)
    return land[cy, cx], land0


def river_trace_in_source(fit, x0, y0, x1, y1) -> np.ndarray:
    """Chris's river trace (`map_data/rivers.png`), pushed to globe pixels and rasterised."""
    idx = np.asarray(Image.open(RIVERS_PATH))
    ys, xs = np.nonzero(idx <= 6)               # palette 0..6 are rivers; 254/255 are background
    sx, sy = canvas_to_source(fit, xs + 0.5, ys + 0.5)
    ix, iy = np.rint(sx).astype(int) - x0, np.rint(sy).astype(int) - y0
    ok = (ix >= 0) & (iy >= 0) & (ix < x1 - x0) & (iy < y1 - y0)
    trace = np.zeros((y1 - y0, x1 - x0), bool)
    trace[iy[ok], ix[ok]] = True
    return trace


# ---------------------------------------------------------------------------
# Graticule
# ---------------------------------------------------------------------------

def graticule_lines(fit, x0, y0, x1, y1, lons, lats):
    """(kind, degrees, xs, ys): analytic polylines of the lines that cross the band, 1 px steps."""
    out = []
    lat_dense = np.linspace(-90, 90, 4000)
    for lon in lons:
        sx, sy = fit.to_source(np.full_like(lat_dense, lon), lat_dense)
        out.append(("lon", lon, sx - x0, sy - y0))
    lon_dense = np.linspace(-180, 180, 8000)
    for lat in lats:
        sx, sy = fit.to_source(lon_dense, np.full_like(lon_dense, lat))
        out.append(("lat", lat, sx - x0, sy - y0))
    return out


def trace_line(kind, xs, ys, w, h):
    """Resample a polyline to unit steps in the dominant axis, keeping only points inside the band."""
    if kind == "lat":
        t = np.arange(np.ceil(xs.min()), np.floor(xs.max()) + 1)
        px, py = t, np.interp(t, xs, ys)
    else:
        order = np.argsort(ys)
        t = np.arange(np.ceil(ys.min()), np.floor(ys.max()) + 1)
        px, py = np.interp(t, ys[order], xs[order]), t
    ok = (px >= 0) & (px <= w - 1) & (py >= 0) & (py <= h - 1)
    return px[ok], py[ok]


def build_graticule(fit, td, x0, y0, shape, t0):
    """Strip mask centred on each line's local ridge; prints the largest deviation per line."""
    h, w = shape
    lons = [l for l in range(-180 + MERIDIAN_STEP, 180, MERIDIAN_STEP)]
    lats = [l for l in range(-90 + PARALLEL_STEP, 90, PARALLEL_STEP)]
    strips = np.zeros(shape, bool)
    levels = []
    missing = []
    for kind, deg, lx, ly in graticule_lines(fit, x0, y0, x0 + w, y0 + h, lons, lats):
        px, py = trace_line(kind, lx, ly, w, h)
        if len(px) < GRID_SEG:
            continue
        worst = 0.0
        seg_levels = []
        for s in range(0, len(px), GRID_SEG):
            sx_, sy_ = px[s:s + GRID_SEG], py[s:s + GRID_SEG]
            best, best_off, level0 = -1.0, 0, 0.0
            for off in range(-GRID_SEARCH, GRID_SEARCH + 1):
                if kind == "lat":
                    ix, iy = np.rint(sx_).astype(int), np.rint(sy_ + off).astype(int)
                else:
                    ix, iy = np.rint(sx_ + off).astype(int), np.rint(sy_).astype(int)
                ok = (ix >= 0) & (iy >= 0) & (ix < w) & (iy < h)
                if not ok.any():
                    continue
                val = td[iy[ok], ix[ok]].mean()
                if off == 0:
                    level0 = val
                if val > best:
                    best, best_off = val, off
            if best < GRID_GAIN * level0:
                best, best_off = level0, 0
            seg_levels.append(best)
            worst = max(worst, abs(best_off))
            for d in range(-GRID_HALF, GRID_HALF + 1):
                if kind == "lat":
                    ix, iy = np.rint(sx_).astype(int), np.rint(sy_ + best_off + d).astype(int)
                else:
                    ix, iy = np.rint(sx_ + best_off + d).astype(int), np.rint(sy_).astype(int)
                ok = (ix >= 0) & (iy >= 0) & (ix < w) & (iy < h)
                strips[iy[ok], ix[ok]] = True
        level = float(np.median(seg_levels))
        levels.append(level)
        if level < GRID_MIN_RIDGE:
            missing.append((kind, deg, level))
        print(f"  {kind} {deg:+4d}: ridge {level:5.1f}  max offset {worst:.0f} px", flush=True)
    if missing:
        raise SystemExit(f"predicted graticule lines with no ridge: {missing}")
    # An unpredicted 5-degree line (tropics, polar circles) would mean the list is incomplete.
    real = float(np.median(levels))
    stray = []
    for kind, rng, step in (("lon", range(-175, 180, 10), None), ("lat", range(-80, 90, 15), None),
                            ("lat", [-66.5, -23.5, 23.5, 66.5], None)):
        for deg in rng:
            for _k, _d, lx, ly in graticule_lines(fit, x0, y0, x0 + w, y0 + h,
                                                   [deg] if kind == "lon" else [], [deg] if kind == "lat" else []):
                px, py = trace_line(kind, lx, ly, w, h)
                if len(px) < GRID_SEG:
                    continue
                ix, iy = np.rint(px).astype(int), np.rint(py).astype(int)
                # a stray line must be strong everywhere along its length, not just at crossings
                if np.median(td[iy, ix]) > GRID_STRAY_FRAC * real:
                    stray.append((kind, deg))
    if stray:
        raise SystemExit(f"straight line at unpredicted positions: {stray}")
    log(f"graticule: {len(levels)} lines, {strips.sum()} strip px", t0)
    return strips


# ---------------------------------------------------------------------------
# Keep mask and fill
# ---------------------------------------------------------------------------

def build_keep(td, land, trace, strips):
    """Thin-dark pixels that are coast, river or part of a long slim line; never filled."""
    thin = td > TOPHAT
    edge = (land & (ndi.distance_transform_edt(land) <= COAST_BAND)) |            (~land & (ndi.distance_transform_edt(~land) <= COAST_BAND))
    near_trace = ndi.distance_transform_edt(~trace) <= RIVER_NEAR
    cand = thin & ~strips
    lab, n = ndi.label(cand, structure=np.ones((3, 3), int))
    area = np.bincount(lab.ravel(), minlength=n + 1)
    slim = np.zeros(n + 1, bool)
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        diag = float(np.hypot(hh, ww))
        if diag >= RIVER_MIN_LEN and area[i] / diag < RIVER_MAX_FAT:
            slim[i] = True
    return thin & (edge | near_trace | slim[lab])


def fill_strips(den, strips, keep, land):
    """Nearest clean pixel of the same kind (land from land, sea from sea) over each strip."""
    fillable = strips & ~keep
    out = den.copy()
    for kind in (land, ~land):
        target = fillable & kind
        if not target.any():
            continue
        clean = kind & ~strips          # strip pixels are never a source; the other kind never is
        _, (iy, ix) = ndi.distance_transform_edt(~clean, return_indices=True)
        out[target] = den[iy[target], ix[target]]
    blurred = np.stack([ndi.gaussian_filter(out[:, :, c], FILL_BLUR) for c in range(3)], -1)
    out[fillable] = blurred[fillable]
    return out, fillable


# ---------------------------------------------------------------------------
# Verify and sheets
# ---------------------------------------------------------------------------

def classify(rgb_block, pal):
    d = ((rgb_block.astype(np.float32)[:, :, None, :] - pal[None, None]) ** 2).sum(-1)
    return d.argmin(-1)


def land_band_stats(img, land, pal, first_land):
    """Per-land-band pixel counts and the land mask implied by the nearest band, in row blocks."""
    counts = np.zeros(len(pal), np.int64)
    is_land = np.zeros(land.shape, bool)
    for y0 in range(0, HEIGHT, BLOCK_ROWS):
        k = classify(img[y0:y0 + BLOCK_ROWS], pal)
        counts += np.bincount(k[land[y0:y0 + BLOCK_ROWS]], minlength=len(pal))
        is_land[y0:y0 + BLOCK_ROWS] = k >= first_land
    return counts, is_land


def best_shift(a, b):
    """Integer (dx, dy) within +-SHIFT_MAX that minimises the mean difference of a and shifted b."""
    m = SHIFT_MAX
    core = a[m:-m, m:-m]
    best = (1e9, (0, 0))
    for dy in range(-m, m + 1):
        for dx in range(-m, m + 1):
            sh = b[m + dy:b.shape[0] - m + dy, m + dx:b.shape[1] - m + dx]
            best = min(best, (float(np.abs(core - sh).mean()), (dx, dy)))
    return best[1]


def verify(orig, clean, land0, t0) -> bool:
    ok = True

    def check(cond, msg):
        nonlocal ok
        ok &= bool(cond)
        log(f"  [{'ok' if cond else 'FAIL'}] {msg}")

    log("verify:", t0)
    check(clean.shape == (HEIGHT, WIDTH, 3), f"output is {clean.shape[1]}x{clean.shape[0]}")
    lo, lum_c = luminance(orig), luminance(clean)
    for name, (wx, wy) in WINDOWS.items():
        sl = (slice(wy, wy + WIN), slice(wx, wx + WIN))
        a, b = ndi.gaussian_filter(lo[sl], 2), ndi.gaussian_filter(lum_c[sl], 2)
        s = best_shift(a, b)
        check(s == (0, 0), f"{name}: best shift {s}")
    elut = schema.load_elevation_lut(LUT_PATH)
    pal = np.array([b.rgb for b in elut.bands], np.float32)
    first_land = elut.sea_band_count
    land = ndi.binary_closing(land0, np.ones((9, 9), bool))
    # Band counts are compared after the same blur on both: the original's hatch and noise scatter
    # pixels across neighbouring bands, so raw counts move even when no relief is lost.
    blur = lambda a: np.stack([ndi.gaussian_filter(a[:, :, c].astype(np.float32), BAND_BLUR)
                               for c in range(3)], -1)
    c0, il0 = land_band_stats(blur(orig), land, pal, first_land)
    c1, il1 = land_band_stats(blur(clean), land, pal, first_land)
    # Relief lost to the fill shows as land pixels falling out of "this band or higher"; a pixel that
    # only drifts to the adjacent band (smoothing a gradient) leaves that cumulative count alone.
    for k in range(first_land, len(pal)):
        a0, a1 = c0[k:].sum(), c1[k:].sum()
        loss = (a0 - a1) / max(a0, 1)
        check(loss <= BAND_LOSS_MAX, f"land at band {k} or higher: {a0} -> {a1} px ({-loss:+.1%})"
              f"   [band {k} alone {c0[k]} -> {c1[k]}]")
    iou = lambda m: (m & land0).sum() / (m | land0).sum()
    check(iou(il1) >= iou(il0) - COAST_IOU_SLACK, f"coast IoU {iou(il0):.4f} -> {iou(il1):.4f}")
    edge = ((land0 & (ndi.distance_transform_edt(land0) <= COAST_RING)) |
            (~land0 & (ndi.distance_transform_edt(~land0) <= COAST_RING)))
    for name, (wx, wy) in WINDOWS.items():
        sl = (slice(wy, wy + WIN), slice(wx, wx + WIN))
        e = edge[sl]
        if e.any():
            print(f"      coast-ring mean |diff| {name}: {np.abs(lo[sl] - lum_c[sl])[e].mean():.2f}")
    idx = np.asarray(Image.open(RIVERS_PATH))
    ys, xs = np.nonzero(idx <= 6)

    def river_share(lum):
        x_lo, x_hi = xs.min() - RIVER_DARK_NEAR - 1, xs.max() + RIVER_DARK_NEAR + 2
        dark = thin_dark(lum[:, x_lo:x_hi]) > TOPHAT   # only the trace's extent, to keep this cheap
        near = ndi.binary_dilation(dark, iterations=RIVER_DARK_NEAR)
        return float(near[ys, xs - x_lo].mean())

    r0, r1 = river_share(lo), river_share(lum_c)
    check(r1 >= r0 - RIVER_SLACK, f"river trace near a dark line {r0:.3f} -> {r1:.3f}")
    return ok


def write_sheets(orig, clean, tag):
    SHEET_DIR.mkdir(parents=True, exist_ok=True)
    for name, (wx, wy) in WINDOWS.items():
        a, b = orig[wy:wy + WIN, wx:wx + WIN], clean[wy:wy + WIN, wx:wx + WIN]
        sheet = np.concatenate([a, np.full((WIN, 8, 3), 255, np.uint8), b], axis=1)
        Image.fromarray(sheet).save(SHEET_DIR / f"qa_clean_canvas_{name}_{tag}.png")


def save_png(arr, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in (1, 2):                       # a Windows save once failed transiently (Errno 22)
        try:
            Image.fromarray(arr).save(path)
            return
        except OSError:
            if attempt == 2:
                raise


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--h", type=float, default=NLM_H, help=f"non-local-means strength (default {NLM_H})")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--tag", default=None, help="suffix for the review sheet names (default: h value)")
    p.add_argument("--preview", action="store_true",
                   help="write a class overlay (graticule, keep) instead of the cleaned canvas")
    args = p.parse_args(argv)
    tag = args.tag or f"h{int(round(args.h * 1000)):03d}"
    t0 = time.time()

    regs = {r.source: r for r in schema.load_registrations(sources.REGISTRATION_DIR)}
    reg = regs[TERRAQUEOUS]
    fit = reproject.fit_parametric(reg)
    src_path = sources.resolve_source_path(TERRAQUEOUS)
    if not src_path.is_file():
        raise SystemExit(f"missing source: {src_path}")
    if not CANVAS_ORIGINAL.is_file():
        raise SystemExit(f"missing original canvas: {CANVAS_ORIGINAL}")
    src = read_rgb_png(src_path)
    cx0, cy0, cx1, cy1 = (int(round(v)) for v in reg.crop)
    x0, y0 = max(cx0 - BAND_PAD, 0), max(cy0 - BAND_PAD, 0)
    x1, y1 = min(cx1 + BAND_PAD + 1, src.shape[1]), min(cy1 + BAND_PAD + 1, src.shape[0])
    band = src[y0:y1, x0:x1]
    log(f"globe {src.shape[1]}x{src.shape[0]}, band x {x0}..{x1} y {y0}..{y1}", t0)

    land, land0 = land_mask_in_source(fit, x0, y0, x1, y1)
    trace = river_trace_in_source(fit, x0, y0, x1, y1)
    log(f"masks: land {land.mean():.3f} of band, river trace {trace.sum()} px", t0)

    lum = luminance(band)
    td = thin_dark(lum)
    strips = build_graticule(fit, td, x0, y0, land.shape, t0)
    keep = build_keep(td, land, trace, strips)
    log(f"keep mask {keep.sum()} px, of which inside strips {(keep & strips).sum()}", t0)

    orig = read_rgb_png(CANVAS_ORIGINAL)
    if args.preview:
        ov = orig.copy()
        # paint the classes on the canvas by sampling the source-space masks through the fit
        for name, m, col in (("strips", strips, (255, 0, 255)), ("keep", keep, (0, 200, 255))):
            full = np.zeros(src.shape[:2], bool)
            full[y0:y1, x0:x1] = m
            for y in range(0, HEIGHT, BLOCK_ROWS):
                sx, sy = ingest.clamped_source_coords(reg, fit, np.arange(y, min(y + BLOCK_ROWS, HEIGHT)), WIDTH, HEIGHT)
                hit = full[np.rint(sy).astype(int), np.rint(sx).astype(int)]
                ov[y:y + BLOCK_ROWS][hit] = col
        path = SHEET_DIR / f"qa_clean_canvas_preview_{tag}.png"
        save_png(ov, path)
        log(f"wrote {path}", t0)
        return 0

    den = denoise_nl_means(band / 255.0, h=args.h, patch_size=NLM_PATCH, patch_distance=NLM_DIST,
                           fast_mode=True, channel_axis=-1) * 255.0
    log(f"denoised (h={args.h})", t0)
    cleaned, filled = fill_strips(den, strips, keep, land)
    log(f"filled {filled.sum()} strip px", t0)

    full = src.astype(np.float32)
    full[y0:y1, x0:x1] = cleaned
    planes = [ingest.reproject_plane(reg, fit, full[:, :, c], WIDTH, HEIGHT, block_rows=BLOCK_ROWS, order=3)
              for c in range(3)]
    clean = np.clip(np.rint(np.stack(planes, -1)), 0, 255).astype(np.uint8)
    log("re-projected (order 3)", t0)

    save_png(clean, args.out)
    log(f"wrote {args.out}", t0)
    write_sheets(orig, clean, tag)
    log(f"wrote review sheets qa_clean_canvas_*_{tag}.png", t0)
    return 0 if verify(orig, clean, land0, t0) else 1


if __name__ == "__main__":
    sys.exit(main())
