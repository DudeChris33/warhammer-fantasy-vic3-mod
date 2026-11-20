#!/usr/bin/env python3
"""Sea-surface textures that follow our coastline: water colour, flow, foam, coast distance (board #11533).

Vanilla paints the real Earth into four map-keyed textures that load unchanged
because our canvas matches vanilla's 8192x3616. Every reader samples them with
``(x / MapSizeX, 1 - z / MapSizeZ)``: column 0 west, row 0 north, a whole-canvas
stretch. This generator replaces all four from ``mapgen/derived/land_sea_mask.png``
(lakes are water there) and ``lake_mask.png``, so water colour, wave direction,
open-ocean swell and the sea-ice coast band follow our coastline, and so do trees
(the flowmap also sets their sway direction).

Outputs (formats, mip counts, headers and total sizes match vanilla's files):

``gfx/map/water/watercolor_rgb_waterspec_a.dds`` (4096x1808, DXT5, 13 mips, 9,876,048 bytes)
    RGB is the water body colour (``GameCalcWater``, ``GameCalcRiver``, the
    refraction tint); A is glossiness (255). Rivers sample the same texture at the
    same UV, so **land texels are river water colour**. Sea colour is a ramp over the
    log of the distance to the nearest land through vanilla's own distance-bin means
    (shallow turquoise at the shore to deep blue), plus a seeded multiplicative
    mottling that fades out within ``NOISE_FADE_PX`` of the coast. We have no
    bathymetry (vanilla's is hand-painted from real ocean depths, and its heightmap
    is 0 below the shelf), so the open sea is plainer than vanilla's.
``gfx/map/water/flowmap.dds`` (1024x452, uncompressed BGRA8, 11 mips, 2,468,284 bytes)
    ``FlowDir = normalize(RG * 2 - 1)`` (R east, G north); B is flow strength; A is
    unread. Within ``COAST_BAND_PX`` of a coast the flow points toward the nearest
    land (the gradient of a blurred land fraction); far from it a latitude-zonal field
    (trades blow west toward the equator, westerlies blow east). On land, R and B set
    the tree-sway direction (``normalize(R*2-1, B*2-1)`` in world x/z), so land B is
    kept at ``B_LAND`` = 151 as vanilla has it; ``windmap_tree.dds`` (#11534) sets only
    the magnitude.
``gfx/map/water/foam_map.dds`` (2048x904, DXT5, 12 mips, 2,470,480 bytes)
    Only R is read, as ``OceanMap``: ``smoothstep(-0.7, 1.1, R)`` blends in the ocean
    flow normal, swell foam and gloss. A heavily blurred open-ocean mask: low near
    coasts, high far out (vanilla's best simple fit: ``blur20(clip((d_sea - 32) / 128,
    0, 1))``). ``d_sea`` is the distance to land **or lake**, so enclosed lakes stay 0.
    Masked to sea after the blur, so land and lake texels are exactly 0 as in vanilla.
``gfx/map/masks/coast_distance.dds`` (2048x904, DX10 ``R16_FLOAT``, 12 mips, 4,937,010 bytes)
    Read only by the sea-ice coast band (``seasons_ice.fxh``): 0 on land and
    ``clip(d / 200, 0, 1)`` on water, lakes included.

DDS container, mip chains and Pillow's DXT5 encoder come from ``worldgen/dds.py``.
Distances are in canvas pixels and do not wrap in x (``should_wrap_x = no``, as in
``generate_flatmap_textures.py``). Deterministic: the only randomness is
``numpy.random.Generator(PCG64(SEED))``.

Usage::

    python mapgen/generate_sea_surface_textures.py             # write the four files
    python mapgen/generate_sea_surface_textures.py --no-write  # build in memory only (gfx untouched)
    python mapgen/generate_sea_surface_textures.py --render    # also write scratchpad/sea_surface_*.png (gitignored)
    python mapgen/generate_sea_surface_textures.py --check     # regenerate in memory, byte-compare with disk
    python mapgen/generate_sea_surface_textures.py --selftest  # synthetic data: headers, sizes, round trips, content

A coastline regen (``generate_coastline_mask.py``) makes these stale; ``--check``
fails until this script is re-run. ``--render`` is the visual gate: send the PNGs and
wait for Chris's verdict before committing the textures.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import canvas_frame  # noqa: E402
from measure_vanilla_frame import VANILLA_ROOT  # noqa: E402
from worldgen import dds, raster  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_DIR = TOOLS_DIR.parent
MASK_PATH = TOOLS_DIR / "derived" / "land_sea_mask.png"
LAKE_PATH = TOOLS_DIR / "derived" / "lake_mask.png"
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"
OUT_WATERCOLOR = REPO_DIR / "gfx" / "map" / "water" / "watercolor_rgb_waterspec_a.dds"
OUT_FLOWMAP = REPO_DIR / "gfx" / "map" / "water" / "flowmap.dds"
OUT_FOAM = REPO_DIR / "gfx" / "map" / "water" / "foam_map.dds"
OUT_COAST = REPO_DIR / "gfx" / "map" / "masks" / "coast_distance.dds"
VANILLA_WATERCOLOR_REL = Path("gfx") / "map" / "water" / "watercolor_rgb_waterspec_a.dds"

CANVAS_W, CANVAS_H = 8192, 3616
SEED = 11533

# Level-0 reduction factor, mip count and expected total bytes of each file (vanilla's).
WATERCOLOR_FACTOR, WATERCOLOR_MIPS, WATERCOLOR_BYTES = 2, 13, 9_876_048
FOAM_FACTOR, FOAM_MIPS, FOAM_BYTES = 4, 12, 2_470_480
FLOW_FACTOR, FLOW_MIPS, FLOW_BYTES = 8, 11, 2_468_284
COAST_FACTOR, COAST_MIPS, COAST_BYTES = 4, 12, 4_937_010

# Sea colour (sRGB, no sRGB flag in the sampler) by distance to land in canvas px:
# vanilla's own distance-bin means, recorded here so the script needs no vanilla file.
SEA_KNOTS = [
    (0, (53, 102, 105)), (1.5, (52, 101, 104)), (3, (42, 92, 97)), (6, (27, 74, 83)),
    (12, (24, 68, 78)), (24, (20.5, 61, 70)), (48, (17, 52, 60)), (96, (12, 40, 47)),
    (192, (10, 34, 40)), (384, (10, 32, 38)),
]
SHORE_RGB = (50, 99, 103)    # land halo at the coast and lake edge
RIVER_RGB = (57, 97, 82)     # land interior = river water colour
LAKE_RGB = (35, 85, 82)      # lake interior
LAND_RAMP_PX = 16.0
LAKE_RAMP_PX = 16.0
NOISE_AMP = 0.10             # multiplicative mottling strength
NOISE_CELL = 64              # texels per noise cell
NOISE_FADE_PX = 16.0         # mottling fades to 0 at the coast
SPEC_ALPHA = 255
FOAM_LO_PX = 32.0
FOAM_HI_PX = 160.0
FOAM_SIGMA = 20.0            # texels
COAST_REACH_PX = 200.0
FLOW_BLUR = 2.0              # texels
GRAD_EPS = 1e-4
COAST_BAND_PX = 24.0
FLOW_LEN = 0.5
TRADE_LAT = 30.0
TRADE_WIDTH = 8.0
B_COAST_DROP = 25.0
B_DROP_PX = 32.0
B_LAND = 151

RED = (200, 40, 40)

# Vanilla header bytes (1.15.1) the writer must reproduce, for --selftest.
VANILLA_HEADERS = {
    "watercolor": "444453207c00000007100a00100700000010000000007100000000000d0000000000000000000000000000000000000000000000000000000000000000000000000000004e5654540800020020000000040000004458543500000000000000000000000000000000000000000810400000000000000000000000000000000000",
    "foam": "444453207c00000007100a00880300000008000000401c00000000000c0000000000000000000000000000000000000000000000000000000000000000000000000000004e5654540800020020000000040000004458543500000000000000000000000000000000000000000810400000000000000000000000000000000000",
    "flowmap": "444453207c0000000f100200c40100000004000000100000000000000b0000000000000000000000000000000000000000000000000000000000000000000000000000004e56545408000200200000004100000000000000200000000000ff0000ff0000ff000000000000ff0810400000000000000000000000000000000000",
    "coast": "444453207c0000000f100200880300000008000000100000000000000c0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000200000000400000044583130000000000000000000000000000000000000000008104000000000000000000000000000000000003600000003000000000000000100000000000000",
}


def log(msg: str, t0: float | None = None) -> None:
    stamp = f" [{time.time() - t0:5.1f}s]" if t0 is not None else ""
    print(msg + stamp, flush=True)


# ---------------------------------------------------------------------------
# Distances and helpers
# ---------------------------------------------------------------------------

def distances(land: np.ndarray, lake: np.ndarray) -> dict[str, np.ndarray]:
    """Euclidean distance fields at canvas resolution (float32 px, no wrap in x).

    ``d_water``: a water pixel's distance to land (0 on land). ``d_land``: a land
    pixel's distance to the nearest water (0 on water). ``d_sea``: distance to the
    nearest land or lake (0 on both), i.e. open-sea distance.
    """
    water = ~land
    sea = water & ~lake
    return {
        "d_water": ndimage.distance_transform_edt(water).astype(np.float32),
        "d_land": ndimage.distance_transform_edt(land).astype(np.float32),
        "d_sea": ndimage.distance_transform_edt(sea).astype(np.float32),
    }


def block_mean(a: np.ndarray, k: int) -> np.ndarray:
    """k x k block mean over axes 0 and 1 (sides must be multiples of k)."""
    h, w = a.shape[:2]
    if h % k or w % k:
        raise ValueError(f"block_mean: {w}x{h} is not a multiple of {k}")
    return a.reshape(h // k, k, w // k, k, *a.shape[2:]).mean(axis=(1, 3), dtype=np.float32)


# ---------------------------------------------------------------------------
# Texture content (level 0, float32)
# ---------------------------------------------------------------------------

def _noise(h: int, w: int, rng: np.random.Generator) -> np.ndarray:
    """Unit-std smooth mottling on an (h, w) texel grid, ~NOISE_CELL texel features."""
    ch, cw = h // NOISE_CELL + 2, w // NOISE_CELL + 2
    coarse = rng.standard_normal((ch, cw)).astype(np.float32)
    big = np.asarray(Image.fromarray(coarse).resize((cw * NOISE_CELL, ch * NOISE_CELL), Image.BICUBIC))[:h, :w]
    return (big / max(float(big.std()), 1e-6)).astype(np.float32)


def watercolor_level0(land: np.ndarray, lake: np.ndarray, d: dict[str, np.ndarray]) -> np.ndarray:
    """(H/2, W/2, 4) RGBA: sea ramp + mottling, lake ramp, river-coloured land, A = 255."""
    h, w = land.shape
    h2, w2 = h // WATERCOLOR_FACTOR, w // WATERCOLOR_FACTOR
    d_water, d_land = d["d_water"], d["d_land"]
    x = np.log2(1.0 + d_water)
    knot_x = np.log2(1.0 + np.array([k[0] for k in SEA_KNOTS], dtype=np.float64))
    lake_t = np.clip(d_water / LAKE_RAMP_PX, 0.0, 1.0)
    land_t = np.clip(d_land / LAND_RAMP_PX, 0.0, 1.0)

    rng = np.random.Generator(np.random.PCG64(SEED))
    noise = _noise(h2, w2, rng)
    fade = block_mean(np.clip(d_water / NOISE_FADE_PX, 0.0, 1.0), WATERCOLOR_FACTOR)

    out = np.empty((h2, w2, 4), dtype=np.float32)
    for c in range(3):
        knot_c = np.array([k[1][c] for k in SEA_KNOTS], dtype=np.float64)
        sea_c = np.interp(x, knot_x, knot_c).astype(np.float32)
        lake_c = np.float32(SHORE_RGB[c]) + np.float32(LAKE_RGB[c] - SHORE_RGB[c]) * lake_t
        land_c = np.float32(SHORE_RGB[c]) + np.float32(RIVER_RGB[c] - SHORE_RGB[c]) * land_t
        v = np.where(land, land_c, np.where(lake, lake_c, sea_c)).astype(np.float32)
        v2 = block_mean(v, WATERCOLOR_FACTOR)
        out[:, :, c] = v2 * (1.0 + np.float32(NOISE_AMP) * noise * fade)
    out[:, :, 3] = SPEC_ALPHA
    return out


def foam_level0(d_sea: np.ndarray) -> np.ndarray:
    """(H/4, W/4, 4): heavily blurred open-ocean mask in R = G = B, A = 255.

    Masked to sea after the blur (times the sea fraction of each 4x4 block; ``d_sea``
    is 0 on land and lakes), so land and lake texels are exactly 0 as in vanilla.
    """
    f = np.clip((block_mean(d_sea, FOAM_FACTOR) - FOAM_LO_PX) / (FOAM_HI_PX - FOAM_LO_PX), 0.0, 1.0)
    f = ndimage.gaussian_filter(f, FOAM_SIGMA, mode=("constant", "nearest"), cval=0.0).astype(np.float32)
    sea_frac = block_mean((d_sea > 0).astype(np.float32), FOAM_FACTOR)
    f = f * sea_frac
    out = np.empty(f.shape + (4,), dtype=np.float32)
    out[:, :, 0] = out[:, :, 1] = out[:, :, 2] = f * 255.0
    out[:, :, 3] = 255.0
    return out


def coast_level0(d_water: np.ndarray) -> np.ndarray:
    """(H/4, W/4) float in [0, 1]: 0 on land, clip(d / 200) on water (lakes included)."""
    return np.clip(block_mean(np.clip(d_water / COAST_REACH_PX, 0.0, 1.0), COAST_FACTOR), 0.0, 1.0)


def flow_level0(land: np.ndarray, d: dict[str, np.ndarray]) -> np.ndarray:
    """(H/8, W/8, 4): R east, G north, B strength, A 255 (see the module docstring)."""
    h, w = land.shape
    k = FLOW_FACTOR
    d_water, d_land = d["d_water"], d["d_land"]
    lf = block_mean(land.astype(np.float32), k)
    b = ndimage.gaussian_filter(lf, FLOW_BLUR, mode="nearest")
    gy, gx = np.gradient(b)
    east, north = gx, -gy
    gn = np.hypot(east, north)
    ok = gn > GRAD_EPS
    safe = np.where(ok, gn, 1.0)
    ux = np.where(ok, east / safe, 0.0)
    uy = np.where(ok, north / safe, 0.0)
    wgt = np.clip(1.0 - block_mean(d_water + d_land, k) / COAST_BAND_PX, 0.0, 1.0) * ok

    rows = np.arange(h // k, dtype=np.float64)
    lat = np.asarray(canvas_frame.canvas_to_lonlat(0.0, (rows + 0.5) * k)[1], dtype=np.float64)
    far_e = np.tanh((np.abs(lat) - TRADE_LAT) / TRADE_WIDTH)
    far_n = -np.sign(lat) * np.sqrt(np.maximum(0.0, 1.0 - far_e ** 2))
    far_e = far_e[:, None].astype(np.float32)
    far_n = far_n[:, None].astype(np.float32)

    vx = wgt * ux + (1.0 - wgt) * far_e
    vy = wgt * uy + (1.0 - wgt) * far_n
    mag = np.hypot(vx, vy)
    weak = mag < 1e-3
    vx = np.where(weak, far_e, vx)
    vy = np.where(weak, far_n, vy)
    mag = np.maximum(np.hypot(vx, vy), 1e-6)

    out = np.empty((h // k, w // k, 4), dtype=np.float32)
    out[:, :, 0] = 127.5 + 127.5 * FLOW_LEN * vx / mag
    out[:, :, 1] = 127.5 + 127.5 * FLOW_LEN * vy / mag
    sea_b = 255.0 - B_COAST_DROP * np.exp(-block_mean(d_water, k) / B_DROP_PX)
    out[:, :, 2] = np.where(lf >= 0.5, float(B_LAND), sea_b)
    out[:, :, 3] = 255.0
    return out


def make_levels(land: np.ndarray, lake: np.ndarray, t0: float | None = None) -> dict[str, np.ndarray]:
    """Level-0 float arrays of the four textures; works on any mask with sides multiple of 8."""
    if land.shape[0] % 8 or land.shape[1] % 8:
        raise ValueError(f"mask {land.shape[1]}x{land.shape[0]}: sides must be multiples of 8")
    log("distance transforms ...", t0)
    d = distances(land, lake)
    log("watercolor level 0 ...", t0)
    watercolor = watercolor_level0(land, lake, d)
    log("foam level 0 ...", t0)
    foam = foam_level0(d["d_sea"])
    log("coast distance level 0 ...", t0)
    coast = coast_level0(d["d_water"])
    log("flowmap level 0 ...", t0)
    flow = flow_level0(land, d)
    return {"watercolor": watercolor, "foam": foam, "flowmap": flow, "coast": coast}


def encode_all(levels: dict[str, np.ndarray], t0: float | None = None) -> dict[Path, bytes]:
    out: dict[Path, bytes] = {}
    log("encoding watercolor (DXT5) ...", t0)
    out[OUT_WATERCOLOR] = dds.build_bc(levels["watercolor"], fourcc="DXT5", mips=WATERCOLOR_MIPS)
    log("encoding foam_map (DXT5) ...", t0)
    out[OUT_FOAM] = dds.build_bc(levels["foam"], fourcc="DXT5", mips=FOAM_MIPS)
    log("encoding flowmap (BGRA8) ...", t0)
    out[OUT_FLOWMAP] = dds.build_bgra8(levels["flowmap"], mips=FLOW_MIPS)
    log("encoding coast_distance (R16F) ...", t0)
    out[OUT_COAST] = dds.build_r16f(levels["coast"], mips=COAST_MIPS)
    return out


EXPECTED_BYTES = {
    OUT_WATERCOLOR: WATERCOLOR_BYTES, OUT_FOAM: FOAM_BYTES,
    OUT_FLOWMAP: FLOW_BYTES, OUT_COAST: COAST_BYTES,
}


def build_all(land: np.ndarray, lake: np.ndarray, t0: float | None = None
              ) -> tuple[dict[Path, bytes], dict[str, np.ndarray]]:
    levels = make_levels(land, lake, t0)
    files = encode_all(levels, t0)
    for path, data in files.items():
        want = EXPECTED_BYTES[path]
        if len(data) != want:
            raise SystemExit(f"{path.name}: {len(data)} bytes, expected {want}")
        log(f"{path.name}: {len(data):,} bytes sha256 {hashlib.sha256(data).hexdigest()[:12]}", t0)
    return files, levels


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def load_masks() -> tuple[np.ndarray, np.ndarray]:
    land = raster.read_mask_png(MASK_PATH)
    lake = raster.read_mask_png(LAKE_PATH)
    for name, m, p in (("land", land, MASK_PATH), ("lake", lake, LAKE_PATH)):
        if m.shape != (CANVAS_H, CANVAS_W):
            raise SystemExit(f"{p}: expected {CANVAS_W}x{CANVAS_H}, got {m.shape[1]}x{m.shape[0]}")
    overlap = int((land & lake).sum())
    if overlap:
        raise SystemExit(f"{LAKE_PATH.name} overlaps {MASK_PATH.name} on {overlap} px: lakes must be water")
    return land, lake


# ---------------------------------------------------------------------------
# Previews (gitignored, in scratchpad/)
# ---------------------------------------------------------------------------

def _coast_edge(land: np.ndarray) -> np.ndarray:
    return ndimage.binary_dilation(land) ^ ndimage.binary_erosion(land)


def _coast_at(edge: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Boolean coastline at ``size`` = (w, h): BOX-resized, threshold > 40."""
    im = Image.fromarray(edge.astype(np.uint8) * 255).resize(size, Image.BOX)
    return np.asarray(im) > 40


def _to_u8(a: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(a), 0, 255).astype(np.uint8)


def _resized(a: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return np.asarray(Image.fromarray(a).resize(size, Image.LANCZOS))


def write_preview(files: dict[Path, bytes], land: np.ndarray, game_dir: Path) -> None:
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    pw, ph = 1024, 452
    edge = _coast_edge(land)
    cs = _coast_at(edge, (pw, ph))

    wc = dds.read_levels(files[OUT_WATERCOLOR])[0]
    foam = dds.read_levels(files[OUT_FOAM])[0]
    flow = dds.read_levels(files[OUT_FLOWMAP])[0]
    coast = dds.read_levels(files[OUT_COAST])[0]

    panels = [
        _resized(_to_u8(wc[:, :, :3].astype(np.float32) * 2.2), (pw, ph)),
        _resized(np.repeat(foam[:, :, :1], 3, axis=2), (pw, ph)),
        _resized(np.repeat(_to_u8(coast[:, :, None] * 255.0), 3, axis=2), (pw, ph)),
        np.stack([flow[:, :, 0], flow[:, :, 1], np.full(flow.shape[:2], 128, np.uint8)], axis=2),
    ]
    grid = np.zeros((ph * 2, pw * 2, 3), dtype=np.uint8)
    for i, p in enumerate(panels):
        p = p.copy()
        p[cs] = RED
        r, c = divmod(i, 2)
        grid[r * ph:(r + 1) * ph, c * pw:(c + 1) * pw] = p
    path = SCRATCH_DIR / "sea_surface_preview.png"
    Image.fromarray(grid).save(path)
    log(f"preview: {path}")

    vanilla_path = game_dir / VANILLA_WATERCOLOR_REL
    vanilla0 = None
    if vanilla_path.exists():
        vanilla0 = dds.read_levels(vanilla_path.read_bytes())[0]
    else:
        log("vanilla panel skipped (vanilla watercolor not found)")
    for name, (x0, y0, x1, y1) in (("bretonnia", (3300, 500, 4300, 1100)), ("lustria", (1700, 1900, 2700, 2500))):
        f = WATERCOLOR_FACTOR
        tx0, ty0, tx1, ty1 = x0 // f, y0 // f, x1 // f, y1 // f
        cs_crop = _coast_at(edge[y0:y1, x0:x1], (tx1 - tx0, ty1 - ty0))
        cs_crop = np.repeat(np.repeat(cs_crop, 2, axis=0), 2, axis=1)
        tiles = []
        for src in (vanilla0, wc):
            if src is None:
                continue
            tile = _to_u8(src[ty0:ty1, tx0:tx1, :3].astype(np.float32) * 2.2)
            tile = np.repeat(np.repeat(tile, 2, axis=0), 2, axis=1)
            tile[cs_crop] = RED
            tiles.append(tile)
        sheet = np.concatenate(tiles, axis=1)
        path = SCRATCH_DIR / f"sea_surface_{name}.png"
        Image.fromarray(sheet).save(path)
        log(f"preview: {path}" + (" (left: vanilla, right: ours)" if len(tiles) == 2 else " (ours only)"))


# ---------------------------------------------------------------------------
# Self-test and main
# ---------------------------------------------------------------------------

def selftest() -> int:
    t0 = time.time()

    # 1. Header parity with vanilla's bytes.
    got = {
        "watercolor": dds.header_bc(4096, 1808, 13, "DXT5"),
        "foam": dds.header_bc(2048, 904, 12, "DXT5"),
        "flowmap": dds.header_bgra8(1024, 452, 11),
        "coast": dds.header_dx10(2048, 904, 12, dds.DXGI_R16_FLOAT, 2),
    }
    for name, hdr in got.items():
        assert hdr.hex() == VANILLA_HEADERS[name], f"{name} header differs from vanilla:\n{hdr.hex()}\n{VANILLA_HEADERS[name]}"
    assert [len(got[k]) for k in ("watercolor", "foam", "flowmap", "coast")] == [128, 128, 128, 148]

    # 2. Size formula at full size, without building the files.
    def bc_total(w, h, mips):
        return 128 + sum(dds.bc_level_bytes(lw, lh, "DXT5") for lw, lh in dds.mip_dims(w, h, mips))

    def raw_total(w, h, mips, bpp, head):
        return head + sum(lw * lh * bpp for lw, lh in dds.mip_dims(w, h, mips))

    cw, ch = CANVAS_W, CANVAS_H
    assert bc_total(cw // WATERCOLOR_FACTOR, ch // WATERCOLOR_FACTOR, WATERCOLOR_MIPS) == WATERCOLOR_BYTES
    assert bc_total(cw // FOAM_FACTOR, ch // FOAM_FACTOR, FOAM_MIPS) == FOAM_BYTES
    assert raw_total(cw // FLOW_FACTOR, ch // FLOW_FACTOR, FLOW_MIPS, 4, 128) == FLOW_BYTES
    assert raw_total(cw // COAST_FACTOR, ch // COAST_FACTOR, COAST_MIPS, 2, 148) == COAST_BYTES
    assert [h for _, h in dds.mip_dims(4096, 1808, 13)] == [1808, 904, 452, 226, 113, 56, 28, 14, 7, 3, 1, 1, 1]

    # 3. Round trips on a 64x36 gradient (odd height drops a tail row).
    gw, gh, mips = 64, 36, 7
    # a sea-like ramp (about 90 levels across the tile), not a full 0-255 sweep: BC endpoint
    # quantisation on a steeper ramp is a property of the encoder, not of this module
    xx = np.linspace(20.0, 110.0, gw, dtype=np.float32)[None, :]
    yy = np.linspace(110.0, 20.0, gh, dtype=np.float32)[:, None]
    x = np.empty((gh, gw, 4), dtype=np.float32)
    x[:, :, 0] = xx + 0 * yy
    x[:, :, 1] = yy + 0 * xx
    x[:, :, 2] = 0.5 * (xx + yy)
    x[:, :, 3] = 255.0
    dims = dds.mip_dims(gw, gh, mips)
    chain = dds.mip_chain(x, mips)
    lv = dds.read_levels(dds.build_bgra8(x, mips=mips))
    assert [l.shape[:2] for l in lv] == [(h, w) for w, h in dims]
    for k in range(mips):
        assert (lv[k] == dds.q8(chain[k])).all(), f"bgra8 level {k} differs"
    x1 = (x[:, :, 0] / 255.0).astype(np.float32)
    chain1 = dds.mip_chain(x1, mips)
    lv = dds.read_levels(dds.build_r16f(x1, mips=mips))
    assert [l.shape for l in lv] == [(h, w) for w, h in dims]
    for k in range(mips):
        assert (lv[k] == chain1[k].astype("<f2").astype(np.float32)).all(), f"r16f level {k} differs"
    lv = dds.read_levels(dds.build_bc(x, fourcc="DXT5", mips=mips))
    assert [l.shape[:2] for l in lv] == [(h, w) for w, h in dims]
    mae = float(np.abs(lv[0][:, :, :3].astype(np.float32) - dds.q8(x[:, :, :3]).astype(np.float32)).mean())
    assert mae <= 3.0, f"DXT5 level-0 MAE {mae:.2f}"
    assert (lv[0][:, :, 3] == 255).all(), "DXT5 alpha is not exactly 255"
    lv1 = dds.read_levels(dds.build_bc(x[:, :, :3], fourcc="DXT1", mips=1))
    assert len(lv1) == 1 and lv1[0].shape[:2] == (gh, gw)

    # 4. Content on a 256x128 synthetic mask: land = west half plus a lake inside it.
    h, w = 128, 256
    land = np.zeros((h, w), dtype=bool)
    land[:, :128] = True
    lake = np.zeros((h, w), dtype=bool)
    lake[56:72, 40:56] = True
    land[lake] = False
    a = make_levels(land, lake)
    b = make_levels(land, lake)
    for name in a:
        assert a[name].tobytes() == b[name].tobytes(), f"{name} is not deterministic"
    fa, fb = encode_all(a), encode_all(b)
    assert all(fa[p] == fb[p] for p in fa), "encoded bytes differ between runs"

    landf = land.astype(np.float32)
    coast = a["coast"]
    ch4 = h // COAST_FACTOR
    cw4 = w // COAST_FACTOR
    blk = block_mean(landf, COAST_FACTOR)
    blk_lake = block_mean(lake.astype(np.float32), COAST_FACTOR)
    assert coast.shape == (ch4, cw4)
    assert (coast[blk == 1.0] == 0).all(), "coast distance not 0 on all-land texels"
    assert (coast[blk == 0.0] > 0).all(), "coast distance not > 0 on water texels"
    assert (coast[(blk_lake == 1.0)] > 0).all(), "coast distance not > 0 inside the lake"

    flow = a["flowmap"]
    mid = flow.shape[0] // 2
    coast_col = 128 // FLOW_FACTOR
    texel = flow[mid, coast_col]          # first texel east of the coast
    assert texel[0] < 128, f"flow R {texel[0]:.1f} does not point west toward land"
    assert abs(texel[1] - 128) < 16, f"flow G {texel[1]:.1f} drifts off the east-west axis"
    assert (flow[land[::FLOW_FACTOR, ::FLOW_FACTOR] & ~lake[::FLOW_FACTOR, ::FLOW_FACTOR]][:, 2] == B_LAND).all()

    wc = a["watercolor"]
    row = wc.shape[0] // 2
    shore_g = wc[row, 128 // WATERCOLOR_FACTOR + 1, 1]        # sea texel just east of the coast
    far_g = wc[row, (128 + 40) // WATERCOLOR_FACTOR, 1]       # 40 px out
    assert shore_g > far_g, f"watercolor shore G {shore_g:.1f} not above 40 px out {far_g:.1f}"

    foam = a["foam"]
    assert foam.shape == (h // FOAM_FACTOR, w // FOAM_FACTOR, 4)
    fblk = block_mean(landf, FOAM_FACTOR)
    fblk_lake = block_mean(lake.astype(np.float32), FOAM_FACTOR)
    assert (foam[:, :, 0][fblk == 1.0] == 0).all(), "foam R is not exactly 0 on all-land texels"
    assert (foam[:, :, 0][fblk_lake == 1.0] == 0).all(), "foam R is not exactly 0 on lake texels"
    assert (foam[:, :, 0][fblk + fblk_lake == 1.0] == 0).all(), "foam R is not 0 on texels with no sea"
    assert foam[:, -1, 0].max() > 50, "foam is not high in open sea"
    assert (foam[:, :, 3] == 255).all()
    log("selftest ok", t0)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--no-write", action="store_true", help="build in memory only; leave gfx/ untouched")
    p.add_argument("--render", action="store_true", help="also write the gitignored preview PNGs")
    p.add_argument("--check", action="store_true", help="regenerate in memory and byte-compare with disk")
    p.add_argument("--selftest", action="store_true", help="synthetic headers, sizes, round trips and content")
    p.add_argument("--game", type=Path, default=VANILLA_ROOT,
                   help="vanilla game folder for the comparison panel (default: the Steam install)")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()

    t0 = time.time()
    land, lake = load_masks()
    log(f"masks: land {100 * land.mean():.2f}%, lake {int(lake.sum()):,} px", t0)
    files, _ = build_all(land, lake, t0)

    if args.check:
        bad = []
        for path, data in files.items():
            rel = path.relative_to(REPO_DIR)
            if not path.exists():
                bad.append(f"{rel}: missing")
            elif path.read_bytes() != data:
                bad.append(f"{rel}: stale (differs from a fresh generation)")
        if bad:
            print("\n".join(bad))
            print("run: python mapgen/generate_sea_surface_textures.py")
            return 1
        log("sea-surface textures current", t0)
        return 0

    if not args.no_write:
        for path, data in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            log(f"wrote {path.relative_to(REPO_DIR)} ({len(data):,} bytes)", t0)
    if args.render:
        write_preview(files, land, args.game)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
