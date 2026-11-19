#!/usr/bin/env python3
"""The terrain-material layer: ``detail_index`` / ``detail_intensity`` and the 36 masks (#6617).

Vanilla paints terrain materials (the close-zoom ground textures) through two
8192x3616 RGBA TGAs under ``gfx/map/terrain/``: ``detail_index.tga`` holds up to
three material indices per pixel (R, G, B; ``255`` = slot unused; A = 255) and
``detail_intensity.tga`` holds their weights (R, G, B; summing to 255; A = 0). The
index is the position in ``gfx/map/terrain/materials.settings`` (``desert_01`` = 0
... ``savanna_03`` = 35; position 21 is id ``snow`` since 1.15). Beside them sit
one 8-bit ``mask_<id>.png`` per material, the form the map editor's material tools
work with. Vanilla's are Earth's; this script replaces the TGAs and the first 36
masks with our own. Vanilla's 16 dynamic and seasonal materials (positions 36-51)
and their masks are not touched.

Inputs (all committed or already-registered sources; nothing new is sourced):

* ``map_data/heightmap.png`` -> elevation (m) and slope (cliffs, snow line).
* ``mapgen/derived/land_sea_mask.png`` / ``lake_mask.png`` -> land, sea, lake.
* ``mapgen/derived/arable_heatmap.png`` -> fertility (grass lushness, forest).
* ``sources/originals/tww3_climate.jpg`` -> biome class (temperate, mountain,
  wasteland, jungle, desert, ...): the biome source here. Chosen on output (2026-11-19):
  the wind-based climate model (``generate_climate_zones.py``, kept for its own uses)
  gave non-canon ground when compared side by side (savannah Lustria, temperate Norsca
  and Naggaroth, no Chaos Wastes or magic forests). Where TWW3 is silent (its frame edges,
  Ind and Khuresh beyond its east edge, 10% of land) the model's class is used
  (:data:`CLIMATE_CODE_BIOME`): it gave tropical jungle, savannah and desert there, where the
  nearest TWW3 class gave Cathay's temperate and Ulthuan-style island grass. Where the model
  has sea (its layer predates the 2026-10-29 coast) the nearest TWW3 class fills in. Inputs
  are chosen by output, not policy (Chris, 2026-11-19). The map is classified by its measured fill colours
  (:data:`PALETTE`, :func:`classify_climate`) and placed on the canvas, best first:
  Chris's Ulthuan dot registration (``cr_combi_expanded_map_ulthuan``); the #9016 zone
  warps (``worldgen/ie_projection.py``: Naggaroth + Lustria, Nehekhara + the Southlands,
  Norsca, the Dark Lands and east), carried forward; over the drawn Old World, the
  named-place pairs in ``config/climate_oldworld_pairs.json``; elsewhere the
  ``tww3_ie_parchment.jpg`` frame registration (the climate map is its ``frame_alias``
  sibling, ``registration/seeds/ie_climate_map.json``). The Old World thin-plate gets no
  weight where it folds. Two polar rules: TWW3 gap land south of :data:`SOUTH_CHAOS_LAT`
  is chaotic waste; north of :data:`NORTH_FROZEN_LAT`, land outside every pair-based
  placement is frozen unless TWW3 says mountain or chaos.
* ``mapgen/derived/climate_zones.png`` + index (the wind model), for TWW3's gaps only.
* ``mapgen/registration/`` and the #9016 pairs (``config/ie_projection_pairs.csv``).

Output is a pure function of those inputs plus ``map_config.SEED``.

Rules, in order: a biome class per 4x4 working cell (climate map, nearest-known
fill, wind-model class in gaps, polar rules, TWW3 mountain demoted where our relief disagrees,
seeded displacement of class edges), a weight per material per cell from biome,
fertility, elevation and seeded smooth noise (rock on high ground in every class),
a Gaussian blend, the top three per cell; then at full
resolution cliff (by slope) and snow (by a latitude-dependent snow line) are added
as two more candidates, merged into a slot of the same material when one exists,
and the top three are quantised to weights summing to 255.

The two TGAs and the masks are an **exact pair of our own**: ``mask[m]`` is the sum
of the weights of the slots holding ``m``, so the masks sum to 255 and their top
three (by weight, ties to the lower index, unused slots 255) are the TGAs byte for
byte (:func:`tgas_from_masks`). Vanilla's pair is not exact (its first slot equals
the strongest mask on 99.7% of pixels, the full set on ~88%). Our TGAs are also
stricter than vanilla in one respect: a slot is 255 exactly when its weight is 0.

Only the masks are committed (Git LFS). The TGAs are gitignored and rebuilt from
them by ``--from-masks`` in seconds, with no other input, so a clean clone runs
that once before deploying (``deploy.ps1`` refuses otherwise).

TGA container: 18-byte header ``00 00 02 00 .. 00 | w | h | 20 08`` (uncompressed
true colour, 32 bpp, bottom-left origin), rows bottom-up, 26-byte TGA 2.0 footer;
118,489,132 bytes at 8192x3616. Pillow's default RGBA ``.tga`` save writes exactly
this form (asserted by ``--selftest``).

Usage::

    python mapgen/generate_terrain_masks.py                 # write gfx/map/terrain/ (2 TGAs + 36 masks)
    python mapgen/generate_terrain_masks.py --render        # also scratchpad/terrain_preview{,_oldworld}.png
    python mapgen/generate_terrain_masks.py --out DIR --no-write --render   # tuning loop: preview only
    python mapgen/generate_terrain_masks.py --from-masks    # rebuild the two TGAs from the committed masks
    python mapgen/generate_terrain_masks.py --check         # regenerate in memory, compare with disk
    python mapgen/generate_terrain_masks.py --selftest      # synthetic 1/8-scale world, needs no files

Run with ``mapgen/.venv/Scripts/python.exe`` (needs scipy). A change to any input
(a coastline or heightmap regen, the arable heatmap, the climate source) makes
``--check`` fail; the response is to re-run, render and have the preview accepted
again. ``generate_colormap.py`` (#6618) reads the TGAs and goes stale with them.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import raster, reproject, schema  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
REGISTRATION_DIR = TOOLS_DIR / "registration"
SCRATCH_DIR = REPO_ROOT / "scratchpad"
OUT_DIR = REPO_ROOT / "gfx" / "map" / "terrain"
CLIMATE_JPG = REPO_ROOT / "sources" / "originals" / "tww3_climate.jpg"
CLIMATE_PARENT = "tww3_ie_parchment.jpg"
#: ``registration/seeds/ie_climate_map.json`` ``frame_alias`` (climate px -> parent px).
CLIMATE_SCALE = (1.4985835, 1.4984391)

INDEX_TGA = "detail_index.tga"
INTENSITY_TGA = "detail_intensity.tga"
TGA_HEADER_LEN, TGA_FOOTER_LEN = 18, 26
TGA_FOOTER_SIG = b"TRUEVISION-XFILE.\x00"

W, H = map_config.PROVINCES_SIZE
Q = 4                      # working grid is canvas / Q
BLOCK = 256                # canvas rows per full-resolution block
OLDWORLD_CROP = (3450, 134, 5200, 1860)   # canvas box of the full-resolution preview crop

#: ``materials.settings`` order (index = position); ``--check`` verifies it against vanilla.
MATERIALS = [
    "desert_01", "desert_03", "desert_04", "desert_05", "desert_06",
    "beach_01", "beach_02", "beach_03",
    "marchlands_01", "marchlands_02", "marchlands_03", "marchlands_04",
    "cliff_granite_01", "cliff_granite_02", "cliff_granite_06", "cliff_granite_07",
    "cliff_limestone_02", "cliff_limestone_03",
    "cliff_sandstone_03", "cliff_sandstone_04", "cliff_sandstone_05",
    "snow",
    "grasslands_01", "grasslands_02", "grasslands_05", "grasslands_06",
    "grasslands_07", "grasslands_08",
    "permafrost_01", "permafrost_03",
    "woodlands_01", "woodlands_02", "woodlands_03",
    "rocks_01", "savanna_01", "savanna_03",
]
M = {n: i for i, n in enumerate(MATERIALS)}
NONE = 255

#: Mean diffuse colour per material, measured from the vanilla ``*_diffuse.dds`` the
#: material draws with (``snow`` -> ``terrain_snow_diffuse.dds``; ``savanna_01``/``03``
#: draw with the ``permafrost_01``/``03`` textures, ``materials.settings:281-296``).
#: Preview only; nothing shipped reads these.
MAT_RGB = {
    "desert_01": (146, 116, 91),
    "desert_03": (149, 116, 92),
    "desert_04": (148, 114, 90),
    "desert_05": (140, 109, 82),
    "desert_06": (133, 102, 79),
    "beach_01": (139, 121, 99),
    "beach_02": (116, 99, 81),
    "beach_03": (94, 84, 72),
    "marchlands_01": (98, 92, 50),
    "marchlands_02": (86, 71, 34),
    "marchlands_03": (77, 71, 34),
    "marchlands_04": (78, 73, 33),
    "cliff_granite_01": (85, 82, 78),
    "cliff_granite_02": (97, 91, 89),
    "cliff_granite_06": (81, 78, 73),
    "cliff_granite_07": (79, 71, 65),
    "cliff_limestone_02": (95, 84, 70),
    "cliff_limestone_03": (90, 80, 68),
    "cliff_sandstone_03": (108, 81, 62),
    "cliff_sandstone_04": (102, 75, 54),
    "cliff_sandstone_05": (75, 59, 48),
    "snow": (177, 189, 204),
    "grasslands_01": (96, 103, 49),
    "grasslands_02": (89, 95, 40),
    "grasslands_05": (112, 92, 59),
    "grasslands_06": (83, 83, 32),
    "grasslands_07": (94, 91, 42),
    "grasslands_08": (115, 90, 66),
    "permafrost_01": (95, 80, 47),
    "permafrost_03": (120, 93, 61),
    "woodlands_01": (85, 88, 34),
    "woodlands_02": (94, 90, 47),
    "woodlands_03": (67, 68, 24),
    "rocks_01": (82, 81, 78),
    "savanna_01": (95, 80, 47),
    "savanna_03": (120, 93, 61),
}

# Biome classes of the TWW3 climate map.
UNKNOWN, TEMPERATE, MOUNTAIN, WASTE, MAGIC, ISLAND, FROZEN, CHAOS, JUNGLE, SAVANNA, DESERT = range(11)
BIOME_NAMES = ["unknown", "temperate", "mountain", "wasteland", "magic_forest", "island",
               "frozen", "chaotic_waste", "jungle", "savannah", "desert"]
#: Fill colour per class, measured 2026-11-19 as the median of 13x13 windows inside
#: named regions of each class on the 5 px median-filtered map (jungle: Lustria and the
#: Central Jungle; savannah: the Southlands' south). The legend swatches are NOT the fills
#: (the fills are paler, blended over parchment): the prototype used the swatches, so
#: jungle (21, 76, 11) matched only outline fringes and real jungle went unclassified.
PALETTE = {
    TEMPERATE: (104, 179, 62), MOUNTAIN: (145, 137, 130), WASTE: (187, 117, 65),
    MAGIC: (79, 215, 233), ISLAND: (115, 170, 205), FROZEN: (216, 212, 209),
    CHAOS: (125, 70, 105), JUNGLE: (99, 102, 55), SAVANNA: (166, 140, 50), DESERT: (222, 187, 50),
}
#: Colours that are not land fills: the brown sea (49 L1 from the wasteland fill), the
#: parchment and its dark shading, and outline ink. A pixel nearest one of these is UNKNOWN.
NOT_LAND = [(168, 127, 85), (201, 163, 115), (179, 144, 100), (131, 96, 61), (91, 62, 39), (30, 25, 20)]
CLIMATE_MEDIAN_PX = 5      # median filter before classifying: removes the fills' paper texture
MIN_FILL_PX = 400          # a class fill smaller than this is UNKNOWN: 202 jungle-coloured specks of 60-400 px sit in the shaded sea; real regions are larger
LEGEND_BOX = (2110, 0, 2400, 350)   # climate px of the printed legend, never land
SPLAT_STEP = 2             # IE master px between points carried through the #9016 zone warps
ZONE_HULL_MARGIN = 150.0   # IE master px a #9016 zone may carry classes past its pair hull
ULTHUAN_SOURCE = "cr_combi_expanded_map_ulthuan.png"   # accepted dot registration over Ulthuan
ULTHUAN_BUFFER_PX = 40     # canvas px the Ulthuan triangulation may extrapolate past its outer dots
PALETTE_TOL = 45           # L1 distance in RGB to the nearest fill colour
FILL_MAX_CELLS = 12        # nearest-known fill radius, in working-grid cells
FRINGE_PX = 1              # opening iterations per class: removes outline-fringe lines (anti-aliasing)
OLDWORLD_PAIRS = TOOLS_DIR / "config" / "climate_oldworld_pairs.json"
OLDWORLD_SMOOTHING = (0.0, 1e2, 1e3, 1e4, 3e4, 1e5, 3e5, 1e6)   # thin-plate candidates, as #9016 plus finer steps

# --- tuning (each constant has a value that switches its rule off, used for before/after renders)
BLEND_SIGMA = 8.0          # Gaussian blend of the per-material weights, working cells (prototype 3.5)
EDGE_WARP_CELLS = 8.0      # amplitude of the seeded displacement of the biome lookup, working cells (0 = off)
EDGE_WARP_SIGMA = 10.0     # smoothness of that displacement field, working cells
MOUNTAIN_RELIEF_M = 700.0  # TWW3 `mountain` kept only at or above this mean elevation (m) or on a cliff slope;
                           # elsewhere the nearest other class (-inf = keep every mountain cell)
HIGH_ROCK_M = (1200.0, 2200.0)  # smoothstep band: rock on high ground in every class
HIGH_ROCK_STRENGTH = 0.7   # share of the cell's weight given to rock at the top of the band (0 = off)
SNOW_LINE_M = (4800.0, 1800.0)  # snow line at <=20 deg and at >=70 deg latitude, metres
SNOW_BAND_M = 250.0        # half-width of the snow fade around the line, metres
CLIFF_SLOPE = (18.0, 55.0) # smoothstep band of cliff material, metres of rise per canvas px
SOUTH_CHAOS_LAT = 50.0     # TWW3 gap land south of this latitude is chaotic waste
#: Wind-model zone code (``climate_zones_index.json``) -> biome class, used only on land the
#: TWW3 map does not reach (Ind, Khuresh, the far rims). An unmapped code is a hard error.
CLIMATE_CODE_BIOME = {
    "Af": JUNGLE, "Am": JUNGLE, "Aw": SAVANNA, "BSh": SAVANNA, "BWh": DESERT, "BWk": DESERT,
    "BSk": WASTE, "Cs": TEMPERATE, "Cfa": TEMPERATE, "Cfb": TEMPERATE, "Df": TEMPERATE,
    "Dc": TEMPERATE, "ET": FROZEN, "EF": FROZEN,
}
CLIMATE_PNG = DERIVED_DIR / "climate_zones.png"
CLIMATE_INDEX = DERIVED_DIR / "climate_zones_index.json"
NORTH_FROZEN_LAT = 62.0    # north of this, land outside every pair-based placement is frozen unless TWW3 says mountain or chaos


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- inputs

@dataclass
class Inputs:
    """Canvas-resolution inputs plus the climate-map biome on the working grid."""
    land: np.ndarray        # bool [H, W], lakes removed
    lake: np.ndarray        # bool [H, W]
    elev: np.ndarray        # float32 [H, W], metres
    arable: np.ndarray      # float32 [H, W], arable heatmap value
    biome_tww3: np.ndarray  # uint8 [H/Q, W/Q], climate-map class (UNKNOWN where none)
    covered: np.ndarray     # bool [H/Q, W/Q], inside the climate map's frame
    placed: np.ndarray      # bool [H/Q, W/Q], sampled through a pair-based placement, not the frame warp
    biome_model: np.ndarray  # uint8 [H/Q, W/Q], wind-model class (UNKNOWN on its sea)


def load_elevation() -> np.ndarray:
    """Canvas-resolution elevation in metres (float32), heightmap 2x2 block mean."""
    t = time.time()
    hm = np.asarray(Image.open(REPO_ROOT / "map_data" / "heightmap.png"))
    out = np.empty((H, W), np.float32)
    for y0 in range(0, H, 256):
        y1 = min(y0 + 256, H)
        blk = hm[y0 * 2:y1 * 2].astype(np.float32).reshape(y1 - y0, 2, W, 2).mean(axis=(1, 3))
        out[y0:y1] = (blk - map_config.HEIGHT_SEA_LEVEL) / map_config.HEIGHT_UNITS_PER_METRE
    log(f"  elevation: {time.time() - t:.1f}s  range {out.min():.0f}..{out.max():.0f} m")
    return out


def block_mean(a: np.ndarray, q: int = Q) -> np.ndarray:
    h, w = a.shape
    return a[:h // q * q, :w // q * q].reshape(h // q, q, w // q, q).mean(axis=(1, 3), dtype=np.float32)


def classify_climate(img: Image.Image) -> np.ndarray:
    """Biome class per climate-map pixel; UNKNOWN on sea, parchment, ink and outline fringes.

    The map is median-filtered (:data:`CLIMATE_MEDIAN_PX`), each pixel takes the nearest of
    :data:`PALETTE` and :data:`NOT_LAND` (a fill only within :data:`PALETTE_TOL`), and each
    class is opened by :data:`FRINGE_PX` so the thin anti-aliased edge where a black outline
    meets a fill (about (27, 56, 15) beside green) cannot pose as a region; fills under
    :data:`MIN_FILL_PX` (speckle in the shaded sea) are dropped.
    """
    from PIL import ImageFilter
    a = np.asarray(img.filter(ImageFilter.MedianFilter(CLIMATE_MEDIAN_PX)), dtype=np.int16)
    best = np.full(a.shape[:2], 10 ** 6, np.int32)
    cls_px = np.zeros(a.shape[:2], np.uint8)
    for cls, rgb in list(PALETTE.items()) + [(UNKNOWN, c) for c in NOT_LAND]:
        d = np.abs(a - np.array(rgb, np.int16)).sum(axis=2)
        hit = d < best
        best[hit] = d[hit]
        cls_px[hit] = cls
    cls_px[best > PALETTE_TOL] = UNKNOWN
    lx0, ly0, lx1, ly1 = LEGEND_BOX
    cls_px[ly0:ly1, lx0:lx1] = UNKNOWN
    out = np.zeros_like(cls_px)
    st = ndimage.generate_binary_structure(2, 2)
    for cls in PALETTE:
        m = ndimage.binary_opening(cls_px == cls, st, iterations=FRINGE_PX)
        lab, n = ndimage.label(m, st)
        if n:
            size = ndimage.sum(m, lab, np.arange(1, n + 1))
            m = np.isin(lab, np.nonzero(size >= MIN_FILL_PX)[0] + 1)
        out[m] = cls
    return out


@dataclass
class OldWorldPlacement:
    """Smoothed thin-plate canvas -> climate px through the named pairs, and its blend."""
    fit: object               # RBFInterpolator canvas (x, y) -> climate (x, y)
    smoothing: float
    loo_median: float
    hull: object              # scipy Delaunay of the canvas pairs
    blend: tuple[float, float]


def oldworld_placement() -> OldWorldPlacement:
    """Fit :data:`OLDWORLD_PAIRS`: fold-free smoothing with the lowest leave-one-out median.

    The same rule as the #9016 zone projection (``worldgen/ie_projection.choose_method``),
    applied to region-scale pairs, so the smoothing is chosen on every run, deterministically.
    """
    from scipy.interpolate import RBFInterpolator
    from scipy.spatial import Delaunay
    cfg = json.loads(OLDWORLD_PAIRS.read_text(encoding="utf-8"))
    c = np.array([p["canvas"] for p in cfg["pairs"]], float)
    s = np.array([p["source"] for p in cfg["pairs"]], float)
    xs, ys = np.meshgrid(np.arange(c[:, 0].min(), c[:, 0].max(), 20.0), np.arange(c[:, 1].min(), c[:, 1].max(), 20.0))
    grid = np.c_[xs.ravel(), ys.ravel()]
    best = None
    for lam in OLDWORLD_SMOOTHING:
        f = RBFInterpolator(c, s, kernel="thin_plate_spline", smoothing=lam)
        a, b, d = f(grid), f(grid + [1.0, 0.0]), f(grid + [0.0, 1.0])
        if ((b - a)[:, 0] * (d - a)[:, 1] - (b - a)[:, 1] * (d - a)[:, 0] <= 0).any():
            continue
        r = []
        for i in range(len(c)):
            m = np.arange(len(c)) != i
            g = RBFInterpolator(c[m], s[m], kernel="thin_plate_spline", smoothing=lam)
            r.append(float(np.hypot(*(g(c[i][None])[0] - s[i]))))
        med = float(np.median(r))
        if best is None or med < best[1] - 1e-9:
            best = (lam, med, f)
    if best is None:
        raise SystemExit(f"{OLDWORLD_PAIRS.name}: no fold-free smoothing among {OLDWORLD_SMOOTHING}")
    return OldWorldPlacement(best[2], best[0], best[1], Delaunay(c), tuple(cfg["blend_px"]))


CLIMATE_LATTICE_STEP = 4  # working cells between evaluations of the canvas -> climate map


def climate_lattice():
    """Canvas -> climate px on a lattice every :data:`CLIMATE_LATTICE_STEP` working cells.

    The frame registration (a whole-map lattice) blended into :func:`oldworld_placement`
    over the drawn Old World: full weight inside the pairs' hull grown by ``blend_px[0]``,
    fading to the frame registration by ``blend_px[1]``. Returns ``(sx, sy, frame fit,
    placement)``; lattice node (i, j) is canvas ((j * step + 0.5) * Q, (i * step + 0.5) * Q).
    """
    h4, w4 = H // Q, W // Q
    step = CLIMATE_LATTICE_STEP
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    parent = regs[CLIMATE_PARENT]
    fit = reproject.AliasFit(reproject.fit_warp(parent), parent.source, CLIMATE_SCALE, (0.0, 0.0))
    gx = np.arange(0, w4 + step, step)
    gy = np.arange(0, h4 + step, step)
    cx = (gx[None, :] * Q + Q / 2.0) * np.ones((len(gy), 1))
    cy = (gy[:, None] * Q + Q / 2.0) * np.ones((1, len(gx)))
    sx, sy = fit.to_source_px(cx, cy)
    ow = oldworld_placement()
    pts = np.c_[cx.ravel(), cy.ravel()]
    inside_hull = (ow.hull.find_simplex(pts) >= 0).reshape(cx.shape)
    dist = ndimage.distance_transform_edt(~inside_hull) * (Q * step)      # canvas px
    wgt = 1.0 - smoothstep(dist, *ow.blend)
    near = wgt > 0
    o = ow.fit(pts[near.ravel()])
    # past its northernmost pairs the thin-plate folds (canvas north mapped back onto Kislev,
    # loremaster 2026-11-19): no weight where its Jacobian is not positive
    ox = ow.fit(pts[near.ravel()] + [1.0, 0.0]) - o
    oy = ow.fit(pts[near.ravel()] + [0.0, 1.0]) - o
    det = ox[:, 0] * oy[:, 1] - ox[:, 1] * oy[:, 0]
    w_near = np.where(det > 0, wgt[near], 0.0)
    wgt[near] = w_near
    sx[near] = w_near * o[:, 0] + (1 - w_near) * sx[near]
    sy[near] = w_near * o[:, 1] + (1 - w_near) * sy[near]
    return sx, sy, fit, ow, wgt


def ulthuan_cells(px: np.ndarray, py: np.ndarray) -> np.ndarray:
    """Overwrite ``px``/``py`` over Ulthuan with Chris's accepted dot registration.

    ``cr_combi_expanded_map_ulthuan`` (fit accepted 2026-10-12) places ChaosRobie's expanded
    IE parchment, which is the IE master scaled by 4480/2880 with zero offset, so it carries
    straight into climate px. Neither the frame registration nor the #9016 zones (Ulthuan is
    their unmapped zone 5) place Ulthuan. In place; returns the cells it set.
    """
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    reg = regs[ULTHUAN_SOURCE]
    fit = reproject.fit_piecewise(reg, buffer_px=ULTHUAN_BUFFER_PX)
    x0, y0, x1, y1 = (int(v) // Q for v in reg.footprint)
    pad = ULTHUAN_BUFFER_PX // Q + 1
    y0, x0 = max(y0 - pad, 0), max(x0 - pad, 0)
    y1, x1 = min(y1 + pad, px.shape[0]), min(x1 + pad, px.shape[1])
    gy, gx = np.mgrid[y0:y1, x0:x1]
    cx, cy = fit.to_source_px((gx + 0.5) * Q, (gy + 0.5) * Q)
    ok = (cx > -1e8) & (cy > -1e8)
    to_master = 2880.0 / reg.master_shape[0]
    sub_x, sub_y = px[y0:y1, x0:x1], py[y0:y1, x0:x1]
    sub_x[ok] = cx[ok] * to_master / CLIMATE_SCALE[0]
    sub_y[ok] = cy[ok] * to_master / CLIMATE_SCALE[1]
    out = np.zeros(px.shape, bool)
    out[y0:y1, x0:x1] = ok
    return out


def zone_hull_near(warp, pts: np.ndarray) -> np.ndarray:
    """Points inside a #9016 zone's pair hull or within :data:`ZONE_HULL_MARGIN` IE px of it.

    Beyond that the zone's thin-plate extrapolates without a pair to hold it: zone 1 carried
    TWW3's mid-west Naggaroth desert onto the Arctic coast (loremaster, 2026-11-19).
    """
    inside = warp.inside_hull(pts)
    if inside.all():
        return inside
    edges = warp._hull.convex_hull
    a, b = warp.src[edges[:, 0]], warp.src[edges[:, 1]]
    out = np.nonzero(~inside)[0]
    q = pts[out]
    best = np.full(len(q), np.inf)
    for (ax, ay), (bx, by) in zip(a, b):
        dx, dy = bx - ax, by - ay
        tt = np.clip(((q[:, 0] - ax) * dx + (q[:, 1] - ay) * dy) / max(dx * dx + dy * dy, 1e-9), 0, 1)
        best = np.minimum(best, np.hypot(q[:, 0] - (ax + tt * dx), q[:, 1] - (ay + tt * dy)))
    inside[out] = best <= ZONE_HULL_MARGIN
    return inside


def zone_splat(cls_px: np.ndarray, shape4: tuple[int, int]):
    """Climate classes carried forward through the #9016 zone warps (IE px -> canvas).

    The four mapped zones (1 Naggaroth + Lustria, 2 Nehekhara + the Southlands, 3 Norsca,
    4 the Dark Lands and east; ``worldgen/ie_projection.py``) are fitted through Chris's
    reviewed landmark pairs, so where one reaches a working cell it replaces the frame
    registration. Every :data:`SPLAT_STEP`-th IE master px of a zone votes its class into
    the cell it lands in; a cell takes its majority class. Returns ``(biome, reached)``.
    """
    from worldgen import ie_projection
    proj = ie_projection.load_projection()
    h4, w4 = shape4
    votes = np.zeros((len(BIOME_NAMES), h4, w4), np.int32)
    ch, cw = cls_px.shape
    for z, warp in sorted(proj.warps.items()):
        ys, xs = np.nonzero(proj.zones[::SPLAT_STEP, ::SPLAT_STEP] == z)
        mx, my = xs * float(SPLAT_STEP), ys * float(SPLAT_STEP)
        cx = np.clip(np.rint(mx / CLIMATE_SCALE[0]), 0, cw - 1).astype(np.intp)
        cy = np.clip(np.rint(my / CLIMATE_SCALE[1]), 0, ch - 1).astype(np.intp)
        near = zone_hull_near(warp, np.c_[mx, my])      # a thin-plate is unconstrained far past its pairs
        mx, my, cx, cy = mx[near], my[near], cx[near], cy[near]
        cls = cls_px[cy, cx]
        dst = warp.forward(np.c_[mx, my])
        gx = np.floor(dst[:, 0] / Q).astype(np.intp)
        gy = np.floor(dst[:, 1] / Q).astype(np.intp)
        ok = (gx >= 0) & (gx < w4) & (gy >= 0) & (gy < h4)
        np.add.at(votes, (cls[ok], gy[ok], gx[ok]), 1)
    reached = votes.sum(axis=0) > 0
    known_votes = votes[1:].sum(axis=0)
    biome = np.where(known_votes > 0, votes[1:].argmax(axis=0) + 1, UNKNOWN).astype(np.uint8)
    # close one-cell holes between splatted points so a zone's footprint is solid
    reached = ndimage.binary_closing(reached, iterations=1)
    return biome, reached


def climate_biomes() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Biome class per working-grid cell, and where the climate map covers it.

    Returns ``(biome uint8 [H4,W4], covered bool [H4,W4], placed bool [H4,W4])``, sampled through
    :func:`climate_lattice` interpolated to the grid.
    """
    if not CLIMATE_JPG.exists():
        raise SystemExit(f"missing climate source {CLIMATE_JPG.relative_to(REPO_ROOT)} "
                         "(sources/ is local-only; see mapgen/SOURCES.md)")
    t = time.time()
    h4, w4 = H // Q, W // Q
    step = CLIMATE_LATTICE_STEP
    sx, sy, fit, ow, wgt = climate_lattice()
    fy = np.arange(h4)[:, None] / step
    fx = np.arange(w4)[None, :] / step
    coords = np.stack([np.broadcast_to(fy, (h4, w4)), np.broadcast_to(fx, (h4, w4))])
    px = ndimage.map_coordinates(sx, coords, order=1, mode="nearest")
    py = ndimage.map_coordinates(sy, coords, order=1, mode="nearest")
    ulth = ulthuan_cells(px, py)
    cls_px = classify_climate(Image.open(CLIMATE_JPG).convert("RGB"))   # JPEG: no alpha
    ch, cw = cls_px.shape
    inside = (px >= 20) & (px <= cw - 20) & (py >= 20) & (py <= ch - 20)
    ix = np.clip(np.rint(px), 0, cw - 1).astype(np.int32)
    iy = np.clip(np.rint(py), 0, ch - 1).astype(np.int32)
    biome = cls_px[iy, ix]
    biome[~inside] = UNKNOWN
    zb, reached = zone_splat(cls_px, (h4, w4))
    biome = np.where(reached, zb, biome).astype(np.uint8)
    inside = inside | reached
    ow_w = ndimage.map_coordinates(wgt, coords, order=1, mode="nearest")
    placed = reached | ulth | (ow_w >= 0.5)
    log(f"  climate warp+classify: {time.time() - t:.1f}s  frame rms {fit.rms_px:.1f}px; Old World "
        f"placement smoothing {ow.smoothing:g}, leave-one-out median {ow.loo_median:.0f} climate px; "
        f"#9016 zones reach {reached.mean() * 100:.1f}% of grid; Ulthuan registration {ulth.sum()} cells; "
        f"known {(biome > 0).mean() * 100:.1f}% of grid")
    return biome, inside, placed


def model_biomes() -> np.ndarray:
    """The wind-based climate model as biome classes on the working grid (cell-centre sample)."""
    layer, _ = raster.read_indexed_png(CLIMATE_PNG)
    index = json.loads(CLIMATE_INDEX.read_text(encoding="utf-8"))
    lut = np.full(256, UNKNOWN, np.uint8)
    for c in index["classes"]:
        if c["code"] not in CLIMATE_CODE_BIOME:
            raise SystemExit(f"{CLIMATE_INDEX.name}: zone code {c['code']!r} has no CLIMATE_CODE_BIOME entry")
        lut[c["id"]] = CLIMATE_CODE_BIOME[c["code"]]
    if layer.shape != (H, W):
        raise SystemExit(f"{CLIMATE_PNG.name}: expected {W}x{H}, got {layer.shape[1]}x{layer.shape[0]}")
    return lut[layer[Q // 2::Q, Q // 2::Q]]


def load_inputs() -> Inputs:
    log("loading inputs")
    land = np.asarray(Image.open(DERIVED_DIR / "land_sea_mask.png"), dtype=bool)
    lake = np.asarray(Image.open(DERIVED_DIR / "lake_mask.png"), dtype=bool)
    elev = load_elevation()
    arable = np.asarray(Image.open(DERIVED_DIR / "arable_heatmap.png"), dtype=np.float32)
    biome, covered, placed = climate_biomes()
    for name, a in (("land_sea_mask", land), ("lake_mask", lake), ("arable_heatmap", arable)):
        if a.shape != (H, W):
            raise SystemExit(f"{name}: expected {W}x{H}, got {a.shape[1]}x{a.shape[0]}")
    return Inputs(land=land & ~lake, lake=lake, elev=elev, arable=arable,
                  biome_tww3=biome, covered=covered, placed=placed, biome_model=model_biomes())


# --------------------------------------------------------------------------- rules

def fill_unknown(biome: np.ndarray, land: np.ndarray, covered: np.ndarray) -> np.ndarray:
    """Replace ink/labels/parchment samples on land with the nearest real biome."""
    known = biome > 0
    if not known.any():
        return biome.copy()
    dist, (iy, ix) = ndimage.distance_transform_edt(~known, return_indices=True)
    out = biome.copy()
    fill = land & ~known & covered & (dist <= FILL_MAX_CELLS)
    out[fill] = biome[iy[fill], ix[fill]]
    return out


def nearest_of(biome: np.ndarray, valid: np.ndarray, where: np.ndarray) -> np.ndarray:
    """``biome`` with the cells in ``where`` replaced by the nearest ``valid`` cell's class."""
    out = biome.copy()
    if not valid.any() or not where.any():
        return out
    _d, (iy, ix) = ndimage.distance_transform_edt(~valid, return_indices=True)
    out[where] = biome[iy[where], ix[where]]
    return out


def demote_mountains(biome: np.ndarray, land: np.ndarray, elev4: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Keep TWW3 ``mountain`` only where our relief agrees; elsewhere the nearest other land class.

    Relief agrees at a cell mean elevation of :data:`MOUNTAIN_RELIEF_M` or more, or a
    working-grid slope above the cliff onset. Returns ``(biome, demoted mask)``.
    """
    gy, gx = np.gradient(elev4)
    slope = np.hypot(gx, gy) / Q                                        # m of rise per canvas px
    relief = (elev4 >= MOUNTAIN_RELIEF_M) | (slope > CLIFF_SLOPE[0])
    demote = land & (biome == MOUNTAIN) & ~relief
    valid = land & (biome != MOUNTAIN) & (biome != UNKNOWN)
    return nearest_of(biome, valid, demote), demote


def warp_biome(biome: np.ndarray, land: np.ndarray, seed: int) -> np.ndarray:
    """Displace the biome lookup by two seeded smooth fields, so class edges stop following
    the TWW3 polygons' straight lines. Land classes are first extended over the sea so a
    coastal cell never samples a sea cell; sea cells keep their own value."""
    if EDGE_WARP_CELLS <= 0:
        return biome
    h4, w4 = biome.shape
    ext = nearest_of(biome, land & (biome != UNKNOWN), ~land | (biome == UNKNOWN))
    dx = smooth_noise(np.random.default_rng([seed, 1]), EDGE_WARP_SIGMA, (h4, w4)) * EDGE_WARP_CELLS
    dy = smooth_noise(np.random.default_rng([seed, 2]), EDGE_WARP_SIGMA, (h4, w4)) * EDGE_WARP_CELLS
    yy, xx = np.mgrid[0:h4, 0:w4]
    sy = np.clip(np.rint(yy + dy), 0, h4 - 1).astype(np.intp)
    sx = np.clip(np.rint(xx + dx), 0, w4 - 1).astype(np.intp)
    return np.where(land, ext[sy, sx], biome).astype(np.uint8)


def smooth_noise(rng, sigma: float, shape: tuple[int, int]) -> np.ndarray:
    n = ndimage.gaussian_filter(rng.standard_normal(shape).astype(np.float32), sigma)
    return n / n.std()


def smoothstep(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def build_weights(biome, land, lake, elev4, fert4, coast_dist, rng) -> np.ndarray:
    """Per-material weight stack [36, H4, W4] before blur."""
    shape = biome.shape
    s = np.zeros((len(MATERIALS),) + shape, np.float32)
    n1, n2, n3 = smooth_noise(rng, 2.5, shape), smooth_noise(rng, 7, shape), smooth_noise(rng, 1.2, shape)
    a = fert4
    lush = np.clip(a * 1.4 + 0.15 * n2, 0, 1)

    def add(name, w, where):
        s[M[name]] += np.where(where, w, 0.0).astype(np.float32)

    b = lambda c: land & (biome == c)  # noqa: E731
    # --- sea / lakes: seabed, like vanilla's (cliff_granite_02 + beach_03 at ~128/127)
    sea = ~land & ~lake
    near = np.clip(1.0 - coast_dist / 14.0, 0, 1)
    add("beach_03", 0.5 + 0.4 * near, sea)
    add("cliff_granite_02", 0.5 - 0.3 * near, sea)
    add("beach_01", 0.45 * near, sea)
    add("beach_01", 1.0, lake)
    # --- temperate: grass by fertility, woodland patches on fertile ground, scrub on poor
    t = b(TEMPERATE)
    add("grasslands_02", lush, t)
    add("grasslands_01", 1.0 - lush * 0.6, t)
    add("woodlands_01", np.clip((a - 0.3) * 2.0 + 0.5 * n1, 0, 1) * 0.9, t)
    add("marchlands_01", np.clip(0.5 - a * 1.5 + 0.2 * n3, 0, 1), t)
    add("grasslands_05", np.clip(0.3 * n2, 0, 1), t)
    # --- temperate island (Ulthuan): lush
    i = b(ISLAND)
    add("grasslands_02", 0.7, i)
    add("woodlands_01", 0.4 + 0.2 * n1, i)
    # --- magical forest
    m = b(MAGIC)
    add("woodlands_02", 0.55, m)
    add("woodlands_03", 0.45 + 0.1 * n1, m)
    # --- jungle
    j = b(JUNGLE)
    add("woodlands_03", 0.65, j)
    add("marchlands_03", 0.25 + 0.1 * n1, j)
    add("grasslands_06", 0.2, j)
    # --- savannah
    v = b(SAVANNA)
    add("savanna_01", 0.6 + 0.2 * n1, v)
    add("savanna_03", 0.3, v)
    add("grasslands_05", 0.3, v)
    # --- desert
    d = b(DESERT)
    add("desert_01", 0.55 + 0.15 * n1, d)
    add("desert_03", 0.3 + 0.15 * n2, d)
    add("desert_05", 0.2, d)
    # --- wasteland (badlands): red-brown scrub and sandstone
    w = b(WASTE)
    add("desert_04", 0.4 + 0.15 * n1, w)
    add("marchlands_02", 0.3, w)
    add("cliff_sandstone_03", 0.25 + 0.15 * n2, w)
    # --- chaotic waste: ash and black rock
    c = b(CHAOS)
    add("cliff_sandstone_05", 0.5, c)
    add("permafrost_01", 0.3 + 0.1 * n1, c)
    add("rocks_01", 0.25, c)
    # --- frozen
    f = b(FROZEN)
    add("snow", 0.6 + 0.15 * n1, f)
    add("permafrost_01", 0.4, f)
    add("permafrost_03", 0.15 * (n2 > 0), f)
    # --- mountains: rock with grass thinning out with height
    mt = b(MOUNTAIN)
    low = 1.0 - smoothstep(elev4, 600, 1800)
    add("cliff_granite_01", 0.45, mt)
    add("rocks_01", 0.25 + 0.1 * n1, mt)
    add("grasslands_05", 0.5 * low, mt)
    add("grasslands_01", 0.35 * low * (a > 0.15), mt)
    add("woodlands_01", 0.25 * low * (a > 0.25), mt)
    # --- shoreline sand on any land (not on mountains/ice), thin
    shore = land & (coast_dist < 2.0) & ~np.isin(biome, [MOUNTAIN, FROZEN, DESERT])
    add("beach_01", 0.5, shore)
    # --- rock on high ground in every class, from our own elevation: ranges the climate
    #     map does not mark still read as mountains
    if HIGH_ROCK_STRENGTH > 0:
        hr = (HIGH_ROCK_STRENGTH * smoothstep(elev4, *HIGH_ROCK_M) * land).astype(np.float32)
        tot = s.sum(axis=0)
        s *= 1.0 - hr
        s[M["rocks_01"]] += 0.55 * hr * tot
        cliff_of = cliff_lut()[biome]
        for mi in np.unique(cliff_of[hr > 0]):
            s[mi] += np.where(cliff_of == mi, 0.45 * hr * tot, 0.0).astype(np.float32)
    return s


def cliff_lut() -> np.ndarray:
    """Cliff material per biome class."""
    lut = np.full(11, M["cliff_granite_06"], np.uint8)
    lut[[WASTE, DESERT, SAVANNA]] = M["cliff_sandstone_04"]
    lut[CHAOS] = M["cliff_granite_07"]
    lut[JUNGLE] = M["cliff_granite_01"]
    return lut


def top3(stack: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Top three materials per cell: (idx [3,H,W] uint8, weight [3,H,W] float32)."""
    order = np.argsort(-stack, axis=0)[:3]
    w = np.take_along_axis(stack, order, axis=0)
    return order.astype(np.uint8), w


def merge_extras(cand_i: np.ndarray, cand_w: np.ndarray) -> None:
    """Fold the cliff (3) and snow (4) candidates into a grid slot of the same material.

    Without this a pixel can carry one material in two slots (``cliff_granite_01``
    under jungle and mountain, ``snow`` under frozen). In place.
    """
    for extra in (3, 4):
        for k in range(3):
            same = cand_i[k] == cand_i[extra]
            cand_w[k] += np.where(same, cand_w[extra], 0.0)
            cand_w[extra] = np.where(same, 0.0, cand_w[extra])


def canonical(ti: np.ndarray, wi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Order slots by weight descending, ties to the lower index, unused (255) last."""
    key = (255 - wi.astype(np.int32)) * 256 + ti.astype(np.int32)
    order = np.argsort(key, axis=0, kind="stable")
    return np.take_along_axis(ti, order, axis=0), np.take_along_axis(wi, order, axis=0)


def validate(idx: np.ndarray, wts: np.ndarray) -> None:
    """Assert the format invariants on ``idx``/``wts`` planes [3, H, W] (uint8)."""
    def fail(msg: str, bad: np.ndarray) -> None:
        ys, xs = np.nonzero(bad)
        raise SystemExit(f"terrain layer invalid: {msg} ({bad.sum()} px, first at x={xs[0]} y={ys[0]})")

    bad = (idx > len(MATERIALS) - 1) & (idx != NONE)
    if bad.any():
        fail("index outside 0-35 and not 255", bad.any(axis=0))
    tot = wts.astype(np.uint16).sum(axis=0)
    if (tot != 255).any():
        fail("weights do not sum to 255", tot != 255)
    if ((idx == NONE) != (wts == 0)).any():
        fail("a slot is 255 without weight 0, or weight 0 with an index", ((idx == NONE) != (wts == 0)).any(axis=0))
    if (idx[0] == NONE).any():
        fail("slot 0 unused", idx[0] == NONE)
    dup = (((idx[0] == idx[1]) & (idx[1] != NONE)) | ((idx[0] == idx[2]) & (idx[2] != NONE))
           | ((idx[1] == idx[2]) & (idx[2] != NONE)))
    if dup.any():
        fail("one material in two slots", dup)
    w = wts.astype(np.int16)
    order_bad = ((w[0] < w[1]) | (w[1] < w[2])
                 | ((w[0] == w[1]) & (w[1] > 0) & (idx[0] > idx[1]))
                 | ((w[1] == w[2]) & (w[2] > 0) & (idx[1] > idx[2])))
    if order_bad.any():
        fail("slots not in canonical order (weight desc, index asc)", order_bad)


def build(inp: Inputs, seed: int, *, verbose: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """The layer as planes ``(idx [3,H,W] uint8, wts [3,H,W] uint8)``; validated."""
    say = log if verbose else (lambda _m: None)
    land_c, lake_c, elev_c = inp.land, inp.lake, inp.elev
    h, w = land_c.shape
    h4, w4 = h // Q, w // Q
    rng = np.random.default_rng(seed)

    landf4 = block_mean(land_c.astype(np.float32))
    fert4 = block_mean(inp.arable)
    fert4 = np.clip(fert4 / np.percentile(fert4[landf4 > 0.5], 99.0), 0, 1)
    land4 = landf4 > 0.5
    lake4 = block_mean(lake_c.astype(np.float32)) > 0.5
    elev4 = block_mean(elev_c)
    _lon, lat = reproject.canvas_lonlat(np.arange(h4), w4, h4)
    lat4 = np.broadcast_to(lat, (h4, w4))
    coast_dist = np.where(land4, ndimage.distance_transform_edt(land4),
                          ndimage.distance_transform_edt(~land4)).astype(np.float32)

    say("biome")
    biome = fill_unknown(inp.biome_tww3, land4, inp.covered)
    # gaps (land the TWW3 map does not reach: its frame edges, Ind and Khuresh beyond its
    # east edge, specks it leaves unpainted) take the wind model's class; where the model has
    # sea (it predates the 2026-10-29 coast), the nearest TWW3 class (module docstring)
    use_proxy = land4 & (biome == UNKNOWN)
    model = inp.biome_model
    biome = np.where(use_proxy & (model != UNKNOWN), model, biome).astype(np.uint8)
    biome = nearest_of(biome, biome != UNKNOWN, land4 & (biome == UNKNOWN)).astype(np.uint8)
    # the far south: TWW3 paints the whole southern rim of its map as the Southern Chaos
    # Wastes, and the polar land beyond its frame belongs to them (loremaster 2026-11-18)
    biome = np.where(use_proxy & (lat4 < -SOUTH_CHAOS_LAT), CHAOS, biome).astype(np.uint8)
    # the far north: nothing poleward of Norsca on the TWW3 map is anything but frozen, mountain
    # or chaotic waste, but our canvas has far more Arctic land, which only the coarse frame
    # warp reaches (it put TWW3's mid-west Naggaroth desert on the Arctic coast). There, any
    # other class becomes frozen (loremaster 2026-11-19).
    arctic = land4 & ~inp.placed & (lat4 > NORTH_FROZEN_LAT) & ~np.isin(biome, [FROZEN, MOUNTAIN, CHAOS])
    biome = np.where(arctic, FROZEN, biome).astype(np.uint8)
    biome, demoted = demote_mountains(biome, land4, elev4)
    say(f"  mountain demoted to its neighbours on {demoted.sum() / max(int(land4.sum()), 1) * 100:.1f}% of land cells")
    biome = warp_biome(biome, land4, seed)
    nland = max(int(land4.sum()), 1)
    say(f"  TWW3 gaps filled from the nearest TWW3 class on {use_proxy.sum() / nland * 100:.1f}% of land cells")
    for k, nme in enumerate(BIOME_NAMES[1:], 1):
        say(f"    {nme:14s} {((biome == k) & land4).sum() / nland * 100:5.1f}% of land")

    say("weights")
    stack = build_weights(biome, land4, lake4, elev4, fert4, coast_dist, rng)
    for k in range(len(MATERIALS)):
        stack[k] = ndimage.gaussian_filter(stack[k], BLEND_SIGMA)
    idx4, w4g = top3(stack)
    del stack

    # cliff material per biome (lookup by working-grid biome class)
    clut = cliff_lut()

    say("full-resolution pass")
    idx = np.empty((3, h, w), np.uint8)
    wts = np.empty((3, h, w), np.uint8)
    gy_full = np.gradient(elev_c, axis=0)
    gx_full = np.gradient(elev_c, axis=1)
    slope = np.hypot(gx_full, gy_full)
    del gy_full, gx_full
    lat_rows = reproject.canvas_lonlat(np.arange(h), w, h)[1][:, 0]
    s_eq, s_pole = SNOW_LINE_M
    snowline = s_eq - (s_eq - s_pole) * np.clip((np.abs(lat_rows) - 20.0) / 50.0, 0, 1)    # m by latitude

    t0 = time.time()
    for y0 in range(0, h, BLOCK):
        y1 = min(y0 + BLOCK, h)
        rows = np.arange(y0, y1)
        fy = (rows + 0.5) / Q - 0.5
        fx = (np.arange(w) + 0.5) / Q - 0.5
        coords = np.stack([np.broadcast_to(fy[:, None], (len(rows), w)),
                           np.broadcast_to(fx[None, :], (len(rows), w))])
        near_y = np.clip(np.rint(fy), 0, h4 - 1).astype(int)[:, None]
        near_x = np.clip(np.rint(fx), 0, w4 - 1).astype(int)[None, :]
        cand_i = np.empty((5, len(rows), w), np.uint8)
        cand_w = np.empty((5, len(rows), w), np.float32)
        for k in range(3):
            cand_i[k] = idx4[k][near_y, near_x]
            cand_w[k] = ndimage.map_coordinates(w4g[k], coords, order=1, mode="nearest")
        landb = land_c[y0:y1]
        bio_here = biome[near_y, near_x]
        sl = slope[y0:y1]
        el = elev_c[y0:y1]
        cliff = smoothstep(sl, *CLIFF_SLOPE) * landb
        snow = smoothstep(el, snowline[y0:y1, None] - SNOW_BAND_M, snowline[y0:y1, None] + SNOW_BAND_M) * landb
        snow *= 1.0 - 0.5 * cliff
        keep = np.clip(1.0 - cliff - snow, 0.0, 1.0)
        cand_w[:3] *= keep
        cand_i[3] = clut[bio_here]
        cand_w[3] = cliff
        cand_i[4] = M["snow"]
        cand_w[4] = snow
        merge_extras(cand_i, cand_w)
        order = np.argsort(-cand_w, axis=0)[:3]
        ti = np.take_along_axis(cand_i, order, axis=0)
        tw = np.take_along_axis(cand_w, order, axis=0)
        tot = tw.sum(axis=0)
        tot[tot <= 0] = 1.0
        wi = np.rint(tw / tot * 255.0).astype(np.int16)
        wi[0] += 255 - wi.sum(axis=0)                                   # residual to the largest slot
        wi = np.clip(wi, 0, 255)
        ti = np.where(wi > 0, ti, NONE).astype(np.uint8)
        ti, wi = canonical(ti, wi)
        idx[:, y0:y1] = ti
        wts[:, y0:y1] = wi.astype(np.uint8)
    say(f"  {time.time() - t0:.0f}s")
    validate(idx, wts)
    return idx, wts


# --------------------------------------------------------------------------- masks and TGAs

def masks_from(idx: np.ndarray, wts: np.ndarray):
    """Yield ``(m, mask uint8 [H,W])`` for every material: the summed weight of its slots."""
    for m in range(len(MATERIALS)):
        acc = np.zeros(idx.shape[1:], np.uint16)
        for k in range(3):
            acc += np.where(idx[k] == m, wts[k], 0).astype(np.uint16)
        yield m, acc.astype(np.uint8)


def tgas_from_masks(masks, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """The exact inverse of :func:`masks_from`: top three by weight, ties to the lower index.

    ``masks`` yields ``(m, mask)`` in ascending ``m``; it is consumed one mask at a time
    (a running insertion into three slots), so the 36 masks are never all in memory.
    """
    idx = np.full((3,) + shape, NONE, np.uint8)
    wts = np.zeros((3,) + shape, np.uint8)
    last = -1
    for m, wm in masks:
        if m <= last:
            raise ValueError("masks must arrive in ascending material order")
        last = m
        gt0, gt1, gt2 = wm > wts[0], wm > wts[1], wm > wts[2]     # slots are sorted, so gt0 => gt1 => gt2
        np.copyto(wts[2], wts[1], where=gt1)
        np.copyto(idx[2], idx[1], where=gt1)
        new2 = gt2 & ~gt1
        np.copyto(wts[2], wm, where=new2)
        idx[2][new2] = m
        np.copyto(wts[1], wts[0], where=gt0)
        np.copyto(idx[1], idx[0], where=gt0)
        new1 = gt1 & ~gt0
        np.copyto(wts[1], wm, where=new1)
        idx[1][new1] = m
        np.copyto(wts[0], wm, where=gt0)
        idx[0][gt0] = m
    return idx, wts


def tga_bytes(planes: np.ndarray, alpha: int) -> bytes:
    """An uncompressed bottom-up 32-bit TGA of ``planes`` [3,H,W] plus a constant alpha."""
    _, h, w = planes.shape
    rgba = np.empty((h, w, 4), np.uint8)
    rgba[..., :3] = np.moveaxis(planes, 0, -1)
    rgba[..., 3] = alpha
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="TGA")
    data = buf.getvalue()
    want = tga_size(h, w)
    if len(data) != want:
        raise SystemExit(f"TGA writer produced {len(data)} bytes, expected {want}")
    return data


def tga_size(h: int, w: int) -> int:
    return TGA_HEADER_LEN + h * w * 4 + TGA_FOOTER_LEN


def read_tga_planes(path: Path, shape: tuple[int, int]) -> np.ndarray:
    size = path.stat().st_size
    if size != tga_size(*shape):
        hint = " (a Git LFS pointer or a truncated file?)" if size < 1024 else ""
        raise SystemExit(f"{path}: {size:,} bytes, expected {tga_size(*shape):,}{hint}")
    a = np.asarray(Image.open(path))
    return np.ascontiguousarray(np.moveaxis(a[..., :3], -1, 0))


def mask_path(out: Path, m: int) -> Path:
    return out / f"mask_{MATERIALS[m]}.png"


def read_mask(path: Path, shape: tuple[int, int]) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(f"{path}: missing")
    try:
        with Image.open(path) as im:
            if im.mode != "L" or im.size != (shape[1], shape[0]):
                raise SystemExit(f"{path}: expected an {shape[1]}x{shape[0]} mode L PNG, "
                                 f"got {im.size[0]}x{im.size[1]} mode {im.mode}")
            return np.asarray(im, dtype=np.uint8)
    except Image.UnidentifiedImageError:
        raise SystemExit(f"{path}: not a PNG ({path.stat().st_size} bytes); "
                         "a Git LFS pointer? run `git lfs pull`") from None


def write_layer(out: Path, idx: np.ndarray, wts: np.ndarray) -> None:
    out.mkdir(parents=True, exist_ok=True)
    t = time.time()
    (out / INDEX_TGA).write_bytes(tga_bytes(idx, 255))
    (out / INTENSITY_TGA).write_bytes(tga_bytes(wts, 0))
    log(f"wrote {INDEX_TGA}, {INTENSITY_TGA} to {out} ({time.time() - t:.0f}s)")
    for m, mask in masks_from(idx, wts):
        Image.fromarray(mask, "L").save(mask_path(out, m))
    log(f"wrote {len(MATERIALS)} mask_*.png ({time.time() - t:.0f}s)")


def from_masks(out: Path) -> int:
    t = time.time()
    shape = (H, W)
    idx, wts = tgas_from_masks(((m, read_mask(mask_path(out, m), shape)) for m in range(len(MATERIALS))), shape)
    validate(idx, wts)
    (out / INDEX_TGA).write_bytes(tga_bytes(idx, 255))
    (out / INTENSITY_TGA).write_bytes(tga_bytes(wts, 0))
    log(f"rebuilt {INDEX_TGA}, {INTENSITY_TGA} from the masks in {out} ({time.time() - t:.0f}s)")
    return 0


# --------------------------------------------------------------------------- check

def vanilla_material_ids(path: Path) -> list[str]:
    ids = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        mt = re.match(r'id\s*=\s*"([^"]+)"', s)
        if mt:
            ids.append(mt.group(1))
    return ids


def check(out: Path) -> int:
    t = time.time()
    problems: list[str] = []
    try:
        from measure_vanilla_frame import VANILLA_ROOT
        settings = VANILLA_ROOT / "gfx" / "map" / "terrain" / "materials.settings"
    except Exception:  # pragma: no cover - the module is part of this repo
        settings = None
    if settings is not None and settings.exists():
        got = vanilla_material_ids(settings)[:len(MATERIALS)]
        if got != MATERIALS:
            diff = [f"{i}: ours {a!r}, vanilla {b!r}" for i, (a, b) in enumerate(zip(MATERIALS, got)) if a != b]
            problems.append("materials.settings order differs from MATERIALS: " + "; ".join(diff[:5]))
    else:
        log("  vanilla materials.settings not found; material order not checked")

    idx, wts = build(load_inputs(), map_config.SEED)
    shape = idx.shape[1:]
    regen = dict(masks_from(idx, wts))
    del idx, wts

    def committed():
        for m in range(len(MATERIALS)):
            p = mask_path(out, m)
            try:
                disk = read_mask(p, shape)
            except FileNotFoundError:
                problems.append(f"{p.relative_to(REPO_ROOT)}: missing")
                disk = np.zeros(shape, np.uint8)
            if not np.array_equal(disk, regen[m]):
                problems.append(f"{p.relative_to(REPO_ROOT)}: stale (differs from a fresh generation)")
            yield m, disk

    m_idx, m_wts = tgas_from_masks(committed(), shape)
    for name, planes in ((INDEX_TGA, m_idx), (INTENSITY_TGA, m_wts)):
        p = out / name
        if not p.exists():
            problems.append(f"{p.relative_to(REPO_ROOT)}: missing (run --from-masks)")
            continue
        if not np.array_equal(read_tga_planes(p, shape), planes):
            problems.append(f"{p.relative_to(REPO_ROOT)}: does not match the committed masks (run --from-masks)")
    if problems:
        print("\n".join(problems))
        print("run: mapgen/.venv/Scripts/python.exe mapgen/generate_terrain_masks.py "
              "(then --render and have the preview accepted again)")
        return 1
    log(f"terrain layer current ({time.time() - t:.0f}s)")
    return 0


# --------------------------------------------------------------------------- render

def colour_rows(idx, wts, elev, land, y0, y1) -> np.ndarray:
    """Preview colour for canvas rows y0..y1: weighted material colour, shaded by relief."""
    pix_rgb = np.array([MAT_RGB[n] for n in MATERIALS] + [(0, 0, 0)] * (256 - len(MATERIALS)), np.float32)
    col = np.zeros((y1 - y0, idx.shape[2], 3), np.float32)
    for k in range(3):
        col += pix_rgb[idx[k, y0:y1]] * (wts[k, y0:y1, :, None] / 255.0)
    lo, hi = max(y0 - 1, 0), min(y1 + 1, elev.shape[0])
    e = elev[lo:hi]
    gy = np.gradient(e, axis=0)[y0 - lo:y0 - lo + (y1 - y0)]
    gx = np.gradient(e[y0 - lo:y0 - lo + (y1 - y0)], axis=1)
    shade = 1.0 + np.clip((gx * 0.7 + gy * 0.7) / 120.0, -0.45, 0.45)
    col = np.where(land[y0:y1, :, None], col * shade[..., None], col * 0.55)
    return np.clip(col, 0, 255)


def render(idx, wts, inp: Inputs, tag: str = "") -> None:
    h, w = idx.shape[1:]
    sfx = f"_{tag}" if tag else ""
    prev = np.zeros((h // 2, w // 2, 3), np.uint8)
    for y0 in range(0, h, BLOCK):
        y1 = min(y0 + BLOCK, h)
        col = colour_rows(idx, wts, inp.elev, inp.land, y0, y1)
        prev[y0 // 2:y1 // 2] = col.reshape((y1 - y0) // 2, 2, w // 2, 2, 3).mean(axis=(1, 3)).astype(np.uint8)
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    p1 = SCRATCH_DIR / f"terrain_preview{sfx}.png"
    Image.fromarray(prev).save(p1)
    x0, cy0, x1, cy1 = OLDWORLD_CROP
    crop = colour_rows(idx[:, :, x0:x1], wts[:, :, x0:x1], inp.elev[:, x0:x1], inp.land[:, x0:x1], cy0, cy1)
    p2 = SCRATCH_DIR / f"terrain_preview_oldworld{sfx}.png"
    Image.fromarray(crop.astype(np.uint8)).save(p2)
    log(f"preview: {p1}\npreview: {p2}")


# --------------------------------------------------------------------------- selftest

def synthetic_inputs(h: int = 452, w: int = 1024) -> Inputs:
    """A 1/8-scale world: the canvas frame (``canvas_lonlat``) needs the canvas aspect,
    and 1/8 is the smallest scale whose height is a multiple of ``Q``."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    land = ((xx - w / 2) / (w * 0.4)) ** 2 + ((yy - h / 2) / (h * 0.4)) ** 2 < 1.0
    lake = ((xx - w * 0.35) ** 2 + (yy - h * 0.5) ** 2) < (h * 0.06) ** 2
    land &= ~lake
    ridge = np.clip(1.0 - np.abs(xx - w * 0.6) / 60.0, 0, 1)          # 100 m/px flanks: cliff
    elev = np.where(land, 50.0 + 6000.0 * ridge, -200.0).astype(np.float32)
    arable = np.where(land, (xx / w) * 200.0, 0.0).astype(np.float32)
    h4, w4 = h // Q, w // Q
    biome = np.full((h4, w4), TEMPERATE, np.uint8)
    biome[:, w4 // 2:] = DESERT
    biome[h4 // 2 - 20:h4 // 2 - 10, w4 // 4:w4 // 4 + 20] = MOUNTAIN   # flat: demoted to its neighbours
    gap = (slice(h4 // 2 + 5, h4 // 2 + 25), slice(w4 // 4, w4 // 4 + 30))
    biome[gap] = UNKNOWN                                                 # outside the climate map:
    covered = np.ones((h4, w4), bool)                                    # takes the nearest class
    covered[gap] = False
    model = np.full((h4, w4), JUNGLE, np.uint8)
    model[gap[0].start:gap[0].start + 5, gap[1]] = UNKNOWN               # model sea on our land: nearest TWW3
    return Inputs(land=land, lake=lake, elev=elev, arable=arable, biome_tww3=biome, covered=covered,
                  placed=np.ones((h4, w4), bool), biome_model=model)


def selftest() -> int:
    t = time.time()
    inp = synthetic_inputs()
    h, w = inp.land.shape
    idx, wts = build(inp, map_config.SEED, verbose=False)          # validates the format invariants
    idx2, wts2 = build(inp, map_config.SEED, verbose=False)
    assert idx.tobytes() == idx2.tobytes() and wts.tobytes() == wts2.tobytes(), "not deterministic"
    land4 = block_mean(inp.land.astype(np.float32)) > 0.5
    _b, demoted = demote_mountains(inp.biome_tww3, land4, block_mean(inp.elev))
    assert demoted.any(), "flat TWW3 mountain was not demoted"
    h4, w4 = inp.biome_tww3.shape
    gap = idx[0, (h4 // 2 + 10) * Q:(h4 // 2 + 20) * Q, (w4 // 4 + 5) * Q:(w4 // 4 + 25) * Q]
    jungle = np.isin(gap, [M[n] for n in ("woodlands_03", "marchlands_03", "grasslands_06")])
    assert jungle.mean() > 0.9, "the TWW3 gap did not take the wind model's class"
    used = set(np.unique(idx).tolist())
    for name in ("snow", "cliff_granite_06", "cliff_sandstone_04", "beach_01", "desert_01", "grasslands_02"):
        assert M[name] in used, f"selftest world never produced {name}"
    masks = list(masks_from(idx, wts))
    total = np.zeros((h, w), np.uint16)
    for _m, mk in masks:
        total += mk
    assert (total == 255).all(), "masks do not sum to 255"
    r_idx, r_wts = tgas_from_masks(iter(masks), (h, w))
    assert np.array_equal(r_idx, idx) and np.array_equal(r_wts, wts), "masks do not round-trip to the TGAs"
    # ties go to the lower index, unused slots are 255
    a = np.full((1, 1), 100, np.uint8)
    t_idx, t_wts = tgas_from_masks(iter([(3, a), (5, np.full((1, 1), 155, np.uint8)), (9, a)]), (1, 1))
    assert t_idx[:, 0, 0].tolist() == [5, 3, 9] and t_wts[:, 0, 0].tolist() == [155, 100, 100], t_idx.ravel()
    t_idx, t_wts = tgas_from_masks(iter([(7, np.full((1, 1), 255, np.uint8))]), (1, 1))
    assert t_idx[:, 0, 0].tolist() == [7, NONE, NONE] and t_wts[:, 0, 0].tolist() == [255, 0, 0]
    # TGA container: vanilla header form, bottom-up rows, TGA 2.0 footer, round trip
    for planes, alpha in ((idx, 255), (wts, 0)):
        data = tga_bytes(planes, alpha)
        hdr = data[:TGA_HEADER_LEN]
        assert hdr[:12] == bytes([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0]), hdr.hex()
        assert int.from_bytes(hdr[12:14], "little") == w and int.from_bytes(hdr[14:16], "little") == h
        assert hdr[16:18] == bytes([0x20, 0x08]), hdr.hex()
        assert data[-TGA_FOOTER_LEN:] == bytes(8) + TGA_FOOTER_SIG, data[-TGA_FOOTER_LEN:]
        first_row = np.frombuffer(data, np.uint8, w * 4, TGA_HEADER_LEN).reshape(w, 4)   # BGRA
        assert np.array_equal(first_row[:, 2], planes[0, h - 1]) and (first_row[:, 3] == alpha).all(), "rows not bottom-up"
        back = np.asarray(Image.open(io.BytesIO(data)))
        assert np.array_equal(np.moveaxis(back[..., :3], -1, 0), planes) and (back[..., 3] == alpha).all()
    # the material-order parser skips commented ids
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "materials.settings"
        p.write_text('{\n\tid = "a"\n#\tid = "x"\n\t\tid = "b"\n}\n', encoding="utf-8")
        assert vanilla_material_ids(p) == ["a", "b"]
    log(f"selftest ok ({time.time() - t:.1f}s)")
    return 0


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="output folder (default gfx/map/terrain/)")
    ap.add_argument("--no-write", action="store_true", help="skip the TGAs and masks (preview only)")
    ap.add_argument("--render", action="store_true", help="write scratchpad/terrain_preview{,_oldworld}.png")
    ap.add_argument("--tag", default="", help="suffix for the preview file names (before/after pairs)")
    ap.add_argument("--from-masks", action="store_true", help="rebuild the two TGAs from the masks in --out")
    ap.add_argument("--check", action="store_true", help="regenerate in memory and compare with --out")
    ap.add_argument("--selftest", action="store_true", help="synthetic world, needs no files")
    args = ap.parse_args(argv)
    out = args.out if args.out.is_absolute() else (Path.cwd() / args.out)
    if args.selftest:
        return selftest()
    if args.from_masks:
        return from_masks(out)
    if args.check:
        return check(out)

    t = time.time()
    inp = load_inputs()
    idx, wts = build(inp, map_config.SEED)
    if not args.no_write:
        write_layer(out, idx, wts)
    if args.render:
        render(idx, wts, inp, args.tag)
    log(f"done in {time.time() - t:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
