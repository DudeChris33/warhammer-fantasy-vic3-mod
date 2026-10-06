#!/usr/bin/env python3
"""PROTOTYPE: the terrain-material layer (``detail_index`` / ``detail_intensity``).

Vanilla paints terrain materials through two 8192x3616 RGBA TGAs under
``gfx/map/terrain/``: ``detail_index.tga`` holds up to three material indices per
pixel (R, G, B; ``255`` = slot unused; A = 255) and ``detail_intensity.tga`` holds
their weights (R, G, B; summing to 255; A = 0). The index order is the order of
``gfx/map/terrain/materials.settings`` (``desert_01`` = 0 ... ``savanna_03`` = 35).
This mod still ships vanilla's Earth copies of both, which is why the map editor
shows Earth's materials under our land (``.claude/rules/testing.md``).

The *format* was checked against the shipped 1.13 files (3 slots, weights sum to
255, alpha 255/0, ``materials_limit = 3`` in ``detail_data.settings``) and cross-
checked against RandomParadox's ``Vic3ImageExporter::detailMaps`` (same index
table). The *rules* below are ours.

Inputs (all committed or already-registered sources; nothing new is sourced):

* ``map_data/heightmap.png`` -> elevation (m) and slope (cliffs, snow line).
* ``mapgen/derived/land_sea_mask.png`` / ``lake_mask.png`` -> land, sea, lake.
* ``mapgen/derived/arable_heatmap.png`` -> fertility (grass lushness, forest).
* ``sources/originals/tww3_climate.jpg`` -> biome class (temperate, mountain,
  wasteland, jungle, desert, ...), warped onto the canvas through the committed
  ``tww3_ie_parchment.jpg`` registration (the climate map is its ``frame_alias``
  sibling, ``registration/seeds/ie_climate_map.json``). Where it has no coverage
  or the sample is ink/parchment, a latitude/elevation/fertility proxy is used.

Output is a pure function of those inputs plus ``map_config.SEED``.

**Not wired into ``gfx/``.** The default output directory is gitignored scratch;
this writes a preview PNG and the two TGAs for review, and never touches the
shipping folders. The 36 per-material ``mask_*.png`` files (editor re-import
helpers) and ``colormap.dds`` / ``flatmap`` / ``land_mask`` are not produced yet.

Usage::

    python mapgen/generate_terrain_masks.py --out <dir>
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import reproject, schema  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
REGISTRATION_DIR = TOOLS_DIR / "registration"
CLIMATE_JPG = REPO_ROOT / "sources" / "originals" / "tww3_climate.jpg"
CLIMATE_PARENT = "tww3_ie_parchment.jpg"
#: ``registration/seeds/ie_climate_map.json`` ``frame_alias`` (climate px -> parent px).
CLIMATE_SCALE = (1.4985835, 1.4984391)

W, H = map_config.PROVINCES_SIZE
Q = 4                      # working grid is canvas / Q
W4, H4 = W // Q, H // Q
BLOCK = 256                # canvas rows per full-resolution block

#: ``materials.settings`` order (index = position).
MATERIALS = [
    "desert_01", "desert_03", "desert_04", "desert_05", "desert_06",
    "beach_01", "beach_02", "beach_03",
    "marchlands_01", "marchlands_02", "marchlands_03", "marchlands_04",
    "cliff_granite_01", "cliff_granite_02", "cliff_granite_06", "cliff_granite_07",
    "cliff_limestone_02", "cliff_limestone_03",
    "cliff_sandstone_03", "cliff_sandstone_04", "cliff_sandstone_05",
    "snow_02",
    "grasslands_01", "grasslands_02", "grasslands_05", "grasslands_06",
    "grasslands_07", "grasslands_08",
    "permafrost_01", "permafrost_03",
    "woodlands_01", "woodlands_02", "woodlands_03",
    "rocks_01", "savanna_01", "savanna_03",
]
M = {n: i for i, n in enumerate(MATERIALS)}
NONE = 255

#: Mean diffuse colour per material, measured from the vanilla ``*_diffuse.dds``
#: (savanna has no diffuse in the install; those two are estimates). Preview only.
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
    "snow_02": (163, 171, 174),
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
    "savanna_01": (150, 132, 72),
    "savanna_03": (160, 140, 80),
}

# Biome classes of the TWW3 climate map (legend colours measured from the image).
UNKNOWN, TEMPERATE, MOUNTAIN, WASTE, MAGIC, ISLAND, FROZEN, CHAOS, JUNGLE, SAVANNA, DESERT = range(11)
BIOME_NAMES = ["unknown", "temperate", "mountain", "wasteland", "magic_forest", "island",
               "frozen", "chaotic_waste", "jungle", "savannah", "desert"]
PALETTE = {
    TEMPERATE: (74, 171, 42), MOUNTAIN: (139, 138, 136), WASTE: (172, 102, 43),
    MAGIC: (37, 216, 239), ISLAND: (81, 179, 218), FROZEN: (228, 227, 223),
    CHAOS: (99, 33, 97), JUNGLE: (21, 76, 11), SAVANNA: (165, 136, 6), DESERT: (220, 180, 22),
}
PALETTE_TOL = 60           # L1 distance in RGB
FILL_MAX_CELLS = 12        # nearest-known fill radius, in working-grid cells


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- inputs

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


def climate_biomes() -> tuple[np.ndarray, np.ndarray]:
    """Biome class per working-grid cell, and where the climate map covers it.

    Returns ``(biome uint8 [H4,W4], covered bool [H4,W4])``. The warp is evaluated on
    a coarse lattice (it is a thin-plate spline) and interpolated to the grid.
    """
    t = time.time()
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    parent = regs[CLIMATE_PARENT]
    fit = reproject.AliasFit(reproject.fit_warp(parent), parent.source, CLIMATE_SCALE, (0.0, 0.0))
    step = 4                                    # lattice spacing in working cells
    gx = np.arange(0, W4 + step, step)
    gy = np.arange(0, H4 + step, step)
    cx = (gx[None, :] * Q + Q / 2.0) * np.ones((len(gy), 1))
    cy = (gy[:, None] * Q + Q / 2.0) * np.ones((1, len(gx)))
    sx, sy = fit.to_source_px(cx, cy)
    fy = np.arange(H4)[:, None] / step
    fx = np.arange(W4)[None, :] / step
    coords = np.stack([np.broadcast_to(fy, (H4, W4)), np.broadcast_to(fx, (H4, W4))])
    px = ndimage.map_coordinates(sx, coords, order=1, mode="nearest")
    py = ndimage.map_coordinates(sy, coords, order=1, mode="nearest")
    clim = np.asarray(Image.open(CLIMATE_JPG).convert("RGB"), dtype=np.int16)
    ch, cw = clim.shape[:2]
    inside = (px >= 20) & (px <= cw - 20) & (py >= 20) & (py <= ch - 20)
    ix = np.clip(np.rint(px), 0, cw - 1).astype(np.int32)
    iy = np.clip(np.rint(py), 0, ch - 1).astype(np.int32)
    samp = clim[iy, ix]
    best = np.full((H4, W4), 10 ** 6, np.int32)
    biome = np.zeros((H4, W4), np.uint8)
    for cls, rgb in PALETTE.items():
        d = np.abs(samp - np.array(rgb, np.int16)).sum(axis=2)
        hit = d < best
        best[hit] = d[hit]
        biome[hit] = cls
    biome[(best > PALETTE_TOL) | ~inside] = UNKNOWN
    log(f"  climate warp+classify: {time.time() - t:.1f}s  rms {fit.rms_px:.1f}px  "
        f"known {(biome > 0).mean() * 100:.1f}% of grid")
    return biome, inside


def fill_unknown(biome: np.ndarray, land: np.ndarray, covered: np.ndarray) -> np.ndarray:
    """Replace ink/labels/parchment samples on land with the nearest real biome."""
    known = biome > 0
    dist, (iy, ix) = ndimage.distance_transform_edt(~known, return_indices=True)
    out = biome.copy()
    fill = land & ~known & covered & (dist <= FILL_MAX_CELLS)
    out[fill] = biome[iy[fill], ix[fill]]
    return out


def proxy_biome(lat: np.ndarray, elev4: np.ndarray, fert4: np.ndarray) -> np.ndarray:
    """Latitude / elevation / fertility stand-in where the climate map has no say."""
    alat = np.abs(lat)
    out = np.full(elev4.shape, TEMPERATE, np.uint8)
    out[(alat < 16) & (fert4 > 0.35)] = JUNGLE
    out[(alat < 16) & (fert4 <= 0.35)] = SAVANNA
    out[(alat >= 16) & (alat < 38) & (fert4 < 0.18)] = DESERT
    out[(alat >= 16) & (alat < 38) & (fert4 >= 0.18) & (fert4 < 0.3)] = SAVANNA
    out[elev4 > 1800] = MOUNTAIN
    out[alat > 64] = FROZEN
    return out


# --------------------------------------------------------------------------- rules

def smooth_noise(rng, sigma: float) -> np.ndarray:
    n = ndimage.gaussian_filter(rng.standard_normal((H4, W4)).astype(np.float32), sigma)
    return n / n.std()


def smoothstep(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def build_weights(biome, land, lake, elev4, fert4, coast_dist, rng) -> np.ndarray:
    """Per-material weight stack [36, H4, W4] before blur."""
    s = np.zeros((len(MATERIALS), H4, W4), np.float32)
    n1, n2, n3 = smooth_noise(rng, 2.5), smooth_noise(rng, 7), smooth_noise(rng, 1.2)
    a = fert4
    lush = np.clip(a * 1.4 + 0.15 * n2, 0, 1)

    def add(name, w, where):
        s[M[name]] += np.where(where, w, 0.0).astype(np.float32)

    b = lambda c: land & (biome == c)
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
    add("snow_02", 0.6 + 0.15 * n1, f)
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
    return s


def top3(stack: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Top three materials per cell: (idx [3,H,W] uint8, weight [3,H,W] float32)."""
    order = np.argsort(-stack, axis=0)[:3]
    w = np.take_along_axis(stack, order, axis=0)
    return order.astype(np.uint8), w


# --------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="output directory (not gfx/)")
    ap.add_argument("--no-tga", action="store_true", help="preview only")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(map_config.SEED)
    T0 = time.time()

    log("loading inputs")
    land_c = np.asarray(Image.open(DERIVED_DIR / "land_sea_mask.png"), dtype=bool)
    lake_c = np.asarray(Image.open(DERIVED_DIR / "lake_mask.png"), dtype=bool)
    land_c = land_c & ~lake_c
    elev_c = load_elevation()
    ar = np.asarray(Image.open(DERIVED_DIR / "arable_heatmap.png"), dtype=np.float32)
    fert4 = block_mean(ar)
    fert4 = np.clip(fert4 / np.percentile(fert4[block_mean(land_c.astype(np.float32)) > 0.5], 99.0), 0, 1)

    land4 = block_mean(land_c.astype(np.float32)) > 0.5
    lake4 = block_mean(lake_c.astype(np.float32)) > 0.5
    elev4 = block_mean(elev_c)
    lon, lat = reproject.canvas_lonlat(np.arange(H4), W4, H4)
    lat4 = np.broadcast_to(lat, (H4, W4))
    coast_dist = np.where(land4, ndimage.distance_transform_edt(land4),
                          ndimage.distance_transform_edt(~land4)).astype(np.float32)

    log("biome")
    biome_c, covered = climate_biomes()
    biome = fill_unknown(biome_c, land4, covered)
    prox = proxy_biome(lat4, elev4, fert4)
    use_proxy = land4 & (biome == UNKNOWN)
    biome = np.where(use_proxy, prox, biome).astype(np.uint8)
    log(f"  proxy fallback on {use_proxy.sum() / max(land4.sum(), 1) * 100:.1f}% of land cells")
    for k, nme in enumerate(BIOME_NAMES[1:], 1):
        log(f"    {nme:14s} {((biome == k) & land4).sum() / max(land4.sum(), 1) * 100:5.1f}% of land")

    log("weights")
    stack = build_weights(biome, land4, lake4, elev4, fert4, coast_dist, rng)
    for k in range(len(MATERIALS)):
        stack[k] = ndimage.gaussian_filter(stack[k], 3.5)
    idx4, w4 = top3(stack)
    del stack

    # cliff material per biome (lookup by working-grid biome class)
    cliff_lut = np.full(11, M["cliff_granite_06"], np.uint8)
    cliff_lut[[WASTE, DESERT, SAVANNA]] = M["cliff_sandstone_04"]
    cliff_lut[CHAOS] = M["cliff_granite_07"]
    cliff_lut[JUNGLE] = M["cliff_granite_01"]

    log("full-resolution pass")
    pix_rgb = np.array([MAT_RGB[n] for n in MATERIALS], np.float32)

    idx_img = np.zeros((H, W, 4), np.uint8)
    int_img = np.zeros((H, W, 4), np.uint8)
    idx_img[..., 3] = 255
    prev = np.zeros((H // 2, W // 2, 3), np.uint8)
    gy_full = np.gradient(elev_c, axis=0)
    gx_full = np.gradient(elev_c, axis=1)
    slope = np.hypot(gx_full, gy_full)
    lat_rows = reproject.canvas_lonlat(np.arange(H), W, H)[1][:, 0]
    snowline = 4800.0 - 3000.0 * np.clip((np.abs(lat_rows) - 20.0) / 50.0, 0, 1)    # m by latitude

    for y0 in range(0, H, BLOCK):
        y1 = min(y0 + BLOCK, H)
        rows = np.arange(y0, y1)
        fy = (rows + 0.5) / Q - 0.5
        fx = (np.arange(W) + 0.5) / Q - 0.5
        coords = np.stack([np.broadcast_to(fy[:, None], (len(rows), W)),
                           np.broadcast_to(fx[None, :], (len(rows), W))])
        near_y = np.clip(np.rint(fy), 0, H4 - 1).astype(int)[:, None]
        near_x = np.clip(np.rint(fx), 0, W4 - 1).astype(int)[None, :]
        cand_i = np.empty((5, len(rows), W), np.uint8)
        cand_w = np.empty((5, len(rows), W), np.float32)
        for k in range(3):
            cand_i[k] = idx4[k][near_y, near_x]
            cand_w[k] = ndimage.map_coordinates(w4[k], coords, order=1, mode="nearest")
        landb = land_c[y0:y1]
        bio_here = biome[near_y, near_x]
        sl = slope[y0:y1]
        el = elev_c[y0:y1]
        cliff = smoothstep(sl, 18.0, 55.0) * landb                      # m of rise per canvas px
        snow = smoothstep(el, snowline[y0:y1, None] - 250, snowline[y0:y1, None] + 250) * landb
        snow *= 1.0 - 0.5 * cliff
        keep = np.clip(1.0 - cliff - snow, 0.0, 1.0)
        cand_w[:3] *= keep
        cand_i[3] = cliff_lut[bio_here]
        cand_w[3] = cliff
        cand_i[4] = M["snow_02"]
        cand_w[4] = snow
        order = np.argsort(-cand_w, axis=0)[:3]
        ti = np.take_along_axis(cand_i, order, axis=0)
        tw = np.take_along_axis(cand_w, order, axis=0)
        tot = tw.sum(axis=0)
        tot[tot <= 0] = 1.0
        wi = np.rint(tw / tot * 255.0).astype(np.int16)
        wi[0] += 255 - wi.sum(axis=0)                                   # residual to the largest slot
        wi = np.clip(wi, 0, 255)
        ti = np.where(wi > 0, ti, NONE).astype(np.uint8)
        for k in range(3):
            idx_img[y0:y1, :, k] = ti[k]
            int_img[y0:y1, :, k] = wi[k].astype(np.uint8)
        # preview: weighted material colour, shaded by relief
        col = np.zeros((len(rows), W, 3), np.float32)
        for k in range(3):
            c = pix_rgb[np.where(ti[k] == NONE, 0, ti[k])]
            col += c * (wi[k][..., None] / 255.0)
        shade = 1.0 + np.clip((gx_full[y0:y1] * 0.7 + gy_full[y0:y1] * 0.7) / 120.0, -0.45, 0.45)
        col = np.where(landb[..., None], col * shade[..., None], col * 0.55)
        prev[y0 // 2:y1 // 2] = np.clip(
            col.reshape(len(rows) // 2, 2, W // 2, 2, 3).mean(axis=(1, 3)), 0, 255).astype(np.uint8)
        log(f"  rows {y0}-{y1}  {time.time() - T0:.0f}s")

    Image.fromarray(prev).save(out / "terrain_preview.png")
    # Old World close-up at full canvas resolution (re-render a crop)
    crop = (3450, 134, 5200, 1860)
    log(f"preview: {out / 'terrain_preview.png'}")
    np.save(out / "_crop_box.npy", np.array(crop))
    if not args.no_tga:
        Image.fromarray(idx_img, "RGBA").save(out / "detail_index.tga")
        Image.fromarray(int_img, "RGBA").save(out / "detail_intensity.tga")
        log("wrote detail_index.tga, detail_intensity.tga")
    np.savez_compressed(out / "_state.npz", idx=idx_img[..., :3][::2, ::2], wts=int_img[..., :3][::2, ::2])
    log(f"done in {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
