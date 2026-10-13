#!/usr/bin/env python3
"""Zoomed-out map textures: the parchment flatmap and the land masks (board #6613).

Vanilla paints the real Earth into three map-keyed textures that load unchanged
because our canvas matches vanilla's 8192x3616: ``flatmap.dds`` (the parchment
picture shown fully zoomed out), ``land_mask.dds`` (an Earth silhouette read as
``.r`` by the flatmap overlay and every map-mode colour overlay) and
``dynamic_masks/exclusion_mask.dds`` (multiplies devastation/pollution). This
generator replaces all three from ``mapgen/derived/land_sea_mask.png``, the
coastline authority (``generate_coastline_mask.py``), so the zoomed-out view and
map-mode colouring follow our coastline. ``flatmap_overlay.dds`` stays vanilla's:
its alpha "details" channel is all zero, so it carries no Earth shapes.

Outputs (all DXT1, full 14-level mip chain, 8192x3616, header fields identical to
vanilla's ``land_mask.dds``):

``gfx/map/textures/land_mask.dds``
    Land white, sea black.
``gfx/map/dynamic_masks/exclusion_mask.dds``
    The same silhouette **flipped vertically**: vanilla stores this one with row 0
    in the south (correlation with ``land_mask`` is 0.80 flipped, -0.11 not), so
    ours does too.
``gfx/map/textures/flatmap.dds``
    A procedural parchment: pale blue-grey sea, olive-grey land, a soft darker
    coastal halo in place of the Earth continental shelf, a thin coast line, a
    seeded paper grain (which doubles as the dither that keeps BC1 from banding on
    the soft gradients) and a mild edge vignette. No vanilla pixels are copied; the
    palette constants were sampled once from vanilla's flatmap. Land provinces are
    repainted by ``ApplyDynamicFlatmap`` (``coloroverlay.fxh``), so the land tone
    only shows where no province paints; sea tone and halo are what matter.
    Ornaments, real-world sea names and the cartouche are deliberately absent.

Mips are built by this script (Pillow writes one level): each level is a 2x2 box
average in **linear light** re-encoded to sRGB, because the land-mask sampler is
``srgb = yes`` and ``ApplyDynamicFlatmap`` reads a blurred low mip for the shore
stripes. An odd dimension drops its last row/column before halving.

Deterministic: the only randomness is ``numpy.random.Generator(PCG64(SEED))``.
The distance transform does not wrap in x (``should_wrap_x = no``).

Usage::

    python mapgen/generate_flatmap_textures.py            # write the three files
    python mapgen/generate_flatmap_textures.py --render   # also write scratchpad/flatmap_preview.png (gitignored)
    python mapgen/generate_flatmap_textures.py --check    # regenerate in memory, byte-compare with disk (stale if the mask moved)
    python mapgen/generate_flatmap_textures.py --selftest # 64x32 mask: container + mip invariants, needs no mask file

A coastline regen (``generate_coastline_mask.py``) makes these stale; ``--check``
fails until this script is re-run. It is the last step of the regeneration
pipeline in ``.claude/rules/testing.md``.
"""
from __future__ import annotations

import argparse
import io
import struct
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import raster  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_DIR = TOOLS_DIR.parent
MASK_PATH = TOOLS_DIR / "derived" / "land_sea_mask.png"
PREVIEW_PATH = TOOLS_DIR.parent / "scratchpad" / "flatmap_preview.png"
OUT_LAND_MASK = REPO_DIR / "gfx" / "map" / "textures" / "land_mask.dds"
OUT_FLATMAP = REPO_DIR / "gfx" / "map" / "textures" / "flatmap.dds"
OUT_EXCLUSION = REPO_DIR / "gfx" / "map" / "dynamic_masks" / "exclusion_mask.dds"

CANVAS_W, CANVAS_H = 8192, 3616
MIP_COUNT = 14
# Total file size of an 8192x3616 DXT1 texture with 14 mips (vanilla land_mask.dds).
EXPECTED_BYTES_FULL = 19_749_224

SEED = 6613

# Palette (sRGB), sampled once from vanilla's flatmap (patches of open sea, shelf and
# land); recorded here so the script needs no vanilla file.
SEA_COLOR = (176, 188, 190)
SHELF_COLOR = (150, 170, 180)
COAST_COLOR = (128, 150, 162)
LAND_COLOR = (170, 176, 152)
HALO_REACH_PX = 70.0      # e-fold distance of the coastal halo, canvas pixels
HALO_STRENGTH = 0.85
COAST_LINE_PX = 2.0
VIGNETTE = 0.07           # edge darkening fraction
GRAIN_COARSE = 3.0        # +/- levels, ~64 px features
GRAIN_FINE = 2.0          # +/- levels, per pixel (also the BC1 dither)

# DDS container constants (DDS_HEADER, 124 bytes after the 4-byte magic).
DDSD_CAPS, DDSD_HEIGHT, DDSD_WIDTH = 0x1, 0x2, 0x4
DDSD_PIXELFORMAT, DDSD_MIPMAPCOUNT, DDSD_LINEARSIZE = 0x1000, 0x20000, 0x80000
DDS_FLAGS = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT | DDSD_LINEARSIZE
DDPF_FOURCC = 0x4
DDSCAPS_COMPLEX, DDSCAPS_TEXTURE, DDSCAPS_MIPMAP = 0x8, 0x1000, 0x400000
DDS_CAPS = DDSCAPS_COMPLEX | DDSCAPS_TEXTURE | DDSCAPS_MIPMAP


def log(msg: str, t0: float | None = None) -> None:
    stamp = f" [{time.time() - t0:5.1f}s]" if t0 is not None else ""
    print(msg + stamp, flush=True)


# ---------------------------------------------------------------------------
# sRGB <-> linear helpers (LUT based, uint8 in / uint8 out)
# ---------------------------------------------------------------------------

_SRGB_TO_LIN = np.array(
    [(v / 255.0 / 12.92) if v / 255.0 <= 0.04045 else ((v / 255.0 + 0.055) / 1.055) ** 2.4
     for v in range(256)], dtype=np.float32)
_LIN_GRID = np.linspace(0.0, 1.0, 4097, dtype=np.float32)
_LIN_TO_SRGB = np.where(_LIN_GRID <= 0.0031308, _LIN_GRID * 12.92,
                        1.055 * np.power(_LIN_GRID, 1 / 2.4) - 0.055).astype(np.float32)


def to_linear(img: np.ndarray) -> np.ndarray:
    return _SRGB_TO_LIN[img]


def to_srgb8(lin: np.ndarray) -> np.ndarray:
    s = np.interp(np.clip(lin, 0.0, 1.0), _LIN_GRID, _LIN_TO_SRGB)
    return np.clip(np.rint(s * 255.0), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# DXT1 + mip chain container
# ---------------------------------------------------------------------------

def mip_dims(w: int, h: int, count: int = MIP_COUNT) -> list[tuple[int, int]]:
    dims = []
    for _ in range(count):
        dims.append((w, h))
        w, h = max(1, w // 2), max(1, h // 2)
    return dims


def level_bytes(w: int, h: int) -> int:
    return ((w + 3) // 4) * ((h + 3) // 4) * 8


def halve_linear(lin: np.ndarray) -> np.ndarray:
    """2x2 box average of a (h, w, 3) linear-light float array; odd tail dropped."""
    h, w = lin.shape[:2]
    if h > 1:
        h2 = (h // 2) * 2
        lin = (lin[0:h2:2] + lin[1:h2:2]) * 0.5
    if w > 1:
        w2 = (w // 2) * 2
        lin = (lin[:, 0:w2:2] + lin[:, 1:w2:2]) * 0.5
    return lin


def encode_dxt1(rgb: np.ndarray) -> bytes:
    """One DXT1 level through Pillow; returns the payload without Pillow's header."""
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, "DDS", pixel_format="DXT1")
    data = buf.getvalue()
    if data[:4] != b"DDS " or struct.unpack_from("<I", data, 4)[0] != 124 or data[84:88] != b"DXT1":
        raise SystemExit("Pillow DXT1 output has an unexpected header (DX10 extension?)")
    payload = data[128:]
    h, w = rgb.shape[:2]
    if len(payload) != level_bytes(w, h):
        raise SystemExit(f"Pillow DXT1 level {w}x{h}: {len(payload)} bytes, expected {level_bytes(w, h)}")
    return payload


def dds_header(w: int, h: int, mips: int) -> bytes:
    fields = [
        124, DDS_FLAGS, h, w, level_bytes(w, h), 0, mips,
        *([0] * 9), 0x5454564E, 0x20008,   # reserved1[9:11]: vanilla's NVTT tool signature + version
        32, DDPF_FOURCC, struct.unpack("<I", b"DXT1")[0], 0, 0, 0, 0, 0,
        DDS_CAPS, 0, 0, 0,
        0,
    ]
    return b"DDS " + struct.pack("<31I", *fields)


def build_dds(rgb: np.ndarray, *, mips: int = MIP_COUNT) -> bytes:
    """DXT1 file with a full mip chain, levels downsampled in linear light."""
    h, w = rgb.shape[:2]
    dims = mip_dims(w, h, mips)
    parts = [dds_header(w, h, mips)]
    lin = to_linear(rgb)
    level = rgb
    for i, (lw, lh) in enumerate(dims):
        if i:
            lin = halve_linear(lin)
            level = to_srgb8(lin)
        if level.shape[:2] != (lh, lw):
            raise SystemExit(f"mip {i}: built {level.shape[1]}x{level.shape[0]}, expected {lw}x{lh}")
        parts.append(encode_dxt1(np.ascontiguousarray(level)))
    out = b"".join(parts)
    want = 128 + sum(level_bytes(lw, lh) for lw, lh in dims)
    if len(out) != want:
        raise SystemExit(f"DDS size {len(out)} != expected {want}")
    return out


# ---------------------------------------------------------------------------
# Texture content
# ---------------------------------------------------------------------------

def mask_rgb(land: np.ndarray, *, flip_v: bool = False) -> np.ndarray:
    v = np.where(land, 255, 0).astype(np.uint8)
    if flip_v:
        v = v[::-1]
    return np.ascontiguousarray(np.repeat(v[:, :, None], 3, axis=2))


def _grain(shape: tuple[int, int], rng: np.random.Generator) -> np.ndarray:
    """Coarse paper mottling plus fine grain, in sRGB levels (float32, mean ~0)."""
    h, w = shape
    ch, cw = max(2, h // 64 + 2), max(2, w // 64 + 2)
    coarse = rng.standard_normal((ch, cw)).astype(np.float32)
    coarse = ndimage.gaussian_filter(coarse, 1.0, mode="nearest")
    coarse = np.asarray(Image.fromarray(coarse).resize((cw * 64, ch * 64), Image.BICUBIC))[:h, :w]
    coarse = coarse / max(float(coarse.std()), 1e-6)
    fine = rng.standard_normal((h, w)).astype(np.float32)
    return coarse * GRAIN_COARSE * 0.5 + fine * GRAIN_FINE * 0.5


def flatmap_rgb(land: np.ndarray) -> np.ndarray:
    h, w = land.shape
    rng = np.random.Generator(np.random.PCG64(SEED))
    d_sea = ndimage.distance_transform_edt(~land).astype(np.float32)   # sea px -> nearest land
    d_land = ndimage.distance_transform_edt(land).astype(np.float32)   # land px -> nearest sea
    halo = HALO_STRENGTH * np.exp(-d_sea / HALO_REACH_PX)
    halo[land] = 0.0
    coast = np.clip(1.0 - np.minimum(d_sea, d_land) / COAST_LINE_PX, 0.0, 1.0)
    del d_sea, d_land

    yy = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
    xx = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    vig = 1.0 - VIGNETTE * np.clip(np.maximum(np.abs(yy), np.abs(xx)) ** 4, 0.0, 1.0)
    grain = _grain((h, w), rng)

    out = np.empty((h, w, 3), dtype=np.uint8)
    for c in range(3):
        ch = np.where(land, np.float32(LAND_COLOR[c]), np.float32(SEA_COLOR[c]))
        ch = ch + halo * np.float32(SHELF_COLOR[c] - SEA_COLOR[c])
        ch = ch + coast * np.float32(COAST_COLOR[c]) * 0.5 - coast * ch * 0.5
        ch = ch * vig + grain
        out[:, :, c] = np.clip(np.rint(ch), 0, 255).astype(np.uint8)
    return out


def load_land() -> np.ndarray:
    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}, got {land.shape[1]}x{land.shape[0]}")
    return land


def build_all(land: np.ndarray, t0: float) -> tuple[dict[Path, bytes], np.ndarray]:
    out: dict[Path, bytes] = {}
    log("land_mask.dds ...", t0)
    out[OUT_LAND_MASK] = build_dds(mask_rgb(land))
    log("exclusion_mask.dds (vertically flipped, as vanilla stores it) ...", t0)
    out[OUT_EXCLUSION] = build_dds(mask_rgb(land, flip_v=True))
    log("flatmap.dds (procedural parchment) ...", t0)
    flat = flatmap_rgb(land)
    out[OUT_FLATMAP] = build_dds(flat)
    for path, data in out.items():
        if len(data) != EXPECTED_BYTES_FULL:
            raise SystemExit(f"{path.name}: {len(data)} bytes, expected {EXPECTED_BYTES_FULL}")
    return out, flat


def write_preview(flat: np.ndarray, land: np.ndarray) -> None:
    """Downscaled flatmap with our coastline traced in red, for the visual gate."""
    im = Image.fromarray(flat, "RGB").resize((2048, 904), Image.LANCZOS)
    coast = ndimage.binary_dilation(land) ^ ndimage.binary_erosion(land)
    cs = np.asarray(Image.fromarray(coast.astype(np.uint8) * 255).resize((2048, 904), Image.BOX)) > 40
    a = np.asarray(im).copy()
    a[cs] = (200, 40, 40)
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a).save(PREVIEW_PATH)
    log(f"preview: {PREVIEW_PATH}")


# ---------------------------------------------------------------------------
# Self-test and main
# ---------------------------------------------------------------------------

def selftest() -> int:
    t0 = time.time()
    h, w = 32, 64
    land = np.zeros((h, w), dtype=bool)
    land[8:24, 10:40] = True
    land[2:6, 50:60] = True
    for mips in (7,):
        data = build_dds(mask_rgb(land), mips=mips)
        hdr = struct.unpack_from("<31I", data, 4)
        assert hdr[0] == 124 and hdr[1] == DDS_FLAGS and hdr[2] == h and hdr[3] == w, hdr[:4]
        assert hdr[4] == level_bytes(w, h) and hdr[6] == mips, hdr[4:7]
        assert hdr[18] == 32 and hdr[19] == DDPF_FOURCC and data[84:88] == b"DXT1"
        assert hdr[26] == DDS_CAPS, hex(hdr[26])
        assert len(data) == 128 + sum(level_bytes(*d) for d in mip_dims(w, h, mips))
        top = Image.open(io.BytesIO(data)).convert("RGB")
        a = np.asarray(top)[:, :, 0]
        assert ((a > 127) == land).all(), "level 0 does not round-trip the mask"
    flip = np.asarray(Image.open(io.BytesIO(build_dds(mask_rgb(land, flip_v=True), mips=7))).convert("L"))
    assert ((flip > 127) == land[::-1]).all(), "flip_v did not flip"
    # linear-light average of a black/white pair is sRGB ~188, not 128
    pair = np.zeros((2, 2, 3), np.uint8)
    pair[:, 1] = 255
    assert abs(int(to_srgb8(halve_linear(to_linear(pair)))[0, 0, 0]) - 188) <= 1
    # determinism
    assert flatmap_rgb(land).tobytes() == flatmap_rgb(land).tobytes()
    log("selftest ok", t0)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--render", action="store_true", help="also write the gitignored preview PNG")
    p.add_argument("--check", action="store_true", help="regenerate in memory and byte-compare with disk")
    p.add_argument("--selftest", action="store_true", help="64x32 container/mip invariants")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()

    t0 = time.time()
    land = load_land()
    log(f"mask {MASK_PATH.name}: land {100 * land.mean():.2f}%", t0)
    files, flat = build_all(land, t0)

    if args.check:
        bad = []
        for path, data in files.items():
            if not path.exists():
                bad.append(f"{path.relative_to(REPO_DIR)}: missing")
            elif path.read_bytes() != data:
                bad.append(f"{path.relative_to(REPO_DIR)}: stale (differs from a fresh generation)")
        if bad:
            print("\n".join(bad))
            print("run: python mapgen/generate_flatmap_textures.py")
            return 1
        log("flatmap textures current", t0)
        return 0

    for path, data in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        log(f"wrote {path.relative_to(REPO_DIR)} ({len(data):,} bytes)", t0)
    if args.render:
        write_preview(flat, land)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
