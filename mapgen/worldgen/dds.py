"""Shared DDS writer and reader for the map-keyed textures (board #11533, consumed by #11534).

numpy and Pillow only. Pillow writes one block-compressed level at a time and no
mip chain, no uncompressed BGRA header and no DX10 header, so this module builds
the 128/148-byte headers itself and Pillow only encodes the BC payload of each
level. Every header below was compared byte for byte with the vanilla 1.15.1 files
(``watercolor_rgb_waterspec_a``, ``foam_map``, ``land_mask``, ``windmap_tree``, the
single-level ``colormap_tree``, ``flowmap``, ``coast_distance``).

Header facts (``DDS_HEADER`` is 124 bytes after the 4-byte magic; field order is
size, flags, height, width, pitch-or-linear-size, depth, mip count, reserved1[11],
pixel format (size, flags, fourCC, bit count, four masks), caps, caps2-4, reserved2):

* Block-compressed (``DXT1``/``DXT5``): flags ``0xA1007`` (``0x81007`` with one
  level and a mip field of 0), linear size ``ceil(w/4)*ceil(h/4)*(8|16)``, depth 0,
  ``reserved1[9..10] = 0x5454564E, 0x20008`` (Paradox's NVTT tool signature),
  pixel-format size 32, flags ``0x4``, caps ``0x401008`` (``0x1000`` with one level).
* Uncompressed BGRA8 (``flowmap``): flags ``0x2100F``, pitch ``w*4``, the NVTT
  signature, pixel-format flags ``0x41``, 32 bpp, masks R ``0xFF0000``, G ``0xFF00``,
  B ``0xFF``, A ``0xFF000000`` (bytes stored B, G, R, A), caps ``0x401008``.
* DX10 extension (``coast_distance``, ``DXGI_FORMAT_R16_FLOAT`` = 54): flags
  ``0x2100F``, pitch ``w*bytes``, every reserved field 0, pixel-format flags ``0x4``,
  fourCC ``DX10``, caps ``0x401008``, then the 20-byte extension
  ``(format, 3 = texture2D, 0, 1, 0)``: 148 header bytes in all.
* Every chain runs to width 1: ``max(1, n // 2)`` per step. A 2x2 box filter drops
  the odd last row or column; an axis of size 1 is left alone.
"""
from __future__ import annotations

import io
import struct

import numpy as np
from PIL import Image

NVTT_SIGNATURE = (0x5454564E, 0x20008)
DDSD_FLAGS_BC = 0xA1007
DDSD_FLAGS_BC_ONE = 0x81007
DDSD_FLAGS_UNCOMPRESSED = 0x2100F
DDS_CAPS_CHAIN = 0x401008
DDS_CAPS_ONE = 0x1000
DDPF_FOURCC = 0x4
DDPF_RGBA = 0x41
DXGI_R16_FLOAT = 54


def mip_dims(w: int, h: int, count: int) -> list[tuple[int, int]]:
    """Level sizes, ``max(1, n // 2)`` per step."""
    dims = []
    for _ in range(count):
        dims.append((w, h))
        w, h = max(1, w // 2), max(1, h // 2)
    return dims


def halve_box(a: np.ndarray) -> np.ndarray:
    """2x2 mean of a 2-D or 3-D array (axes 0 and 1); odd tail dropped, size-1 axis untouched."""
    a = np.asarray(a, dtype=np.float32)
    h, w = a.shape[:2]
    if h > 1:
        h2 = h // 2 * 2
        a = (a[0:h2:2] + a[1:h2:2]) * np.float32(0.5)
    if w > 1:
        w2 = w // 2 * 2
        a = (a[:, 0:w2:2] + a[:, 1:w2:2]) * np.float32(0.5)
    return a


def mip_chain(level0: np.ndarray, count: int) -> list[np.ndarray]:
    """``count`` float32 levels; each is halved from the previous float level, never re-quantised."""
    levels = [np.asarray(level0, dtype=np.float32)]
    for _ in range(count - 1):
        levels.append(halve_box(levels[-1]))
    return levels


def q8(a: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(a), 0, 255).astype(np.uint8)


def bc_level_bytes(w: int, h: int, fourcc: str) -> int:
    return ((w + 3) // 4) * ((h + 3) // 4) * (8 if fourcc == "DXT1" else 16)


def _fourcc(code: str) -> int:
    return struct.unpack("<I", code.encode("ascii"))[0]


def header_bc(w: int, h: int, mips: int, fourcc: str) -> bytes:
    one = mips == 1
    fields = [
        124, DDSD_FLAGS_BC_ONE if one else DDSD_FLAGS_BC, h, w, bc_level_bytes(w, h, fourcc), 0,
        0 if one else mips,
        *([0] * 9), *NVTT_SIGNATURE,
        32, DDPF_FOURCC, _fourcc(fourcc), 0, 0, 0, 0, 0,
        DDS_CAPS_ONE if one else DDS_CAPS_CHAIN, 0, 0, 0,
        0,
    ]
    return b"DDS " + struct.pack("<31I", *fields)


def header_bgra8(w: int, h: int, mips: int) -> bytes:
    fields = [
        124, DDSD_FLAGS_UNCOMPRESSED, h, w, w * 4, 0, mips,
        *([0] * 9), *NVTT_SIGNATURE,
        32, DDPF_RGBA, 0, 32, 0xFF0000, 0xFF00, 0xFF, 0xFF000000,
        DDS_CAPS_CHAIN, 0, 0, 0,
        0,
    ]
    return b"DDS " + struct.pack("<31I", *fields)


def header_dx10(w: int, h: int, mips: int, dxgi_format: int, bytes_per_pixel: int) -> bytes:
    fields = [
        124, DDSD_FLAGS_UNCOMPRESSED, h, w, w * bytes_per_pixel, 0, mips,
        *([0] * 11),
        32, DDPF_FOURCC, _fourcc("DX10"), 0, 0, 0, 0, 0,
        DDS_CAPS_CHAIN, 0, 0, 0,
        0,
    ]
    return b"DDS " + struct.pack("<31I", *fields) + struct.pack("<5I", dxgi_format, 3, 0, 1, 0)


def encode_bc_level(u8: np.ndarray, fourcc: str) -> bytes:
    """One BC level through Pillow; returns the payload without Pillow's header."""
    # The array shape picks the mode: (h, w, 4) is RGBA for DXT5, (h, w, 3) is RGB for DXT1.
    want = 4 if fourcc == "DXT5" else 3
    if u8.ndim != 3 or u8.shape[2] != want or u8.dtype != np.uint8:
        raise ValueError(f"{fourcc} level needs uint8 (h, w, {want}), got {u8.dtype} {u8.shape}")
    buf = io.BytesIO()
    Image.fromarray(u8).save(buf, "DDS", pixel_format=fourcc)
    data = buf.getvalue()
    assert data[84:88] == fourcc.encode("ascii"), f"Pillow wrote {data[84:88]!r}, expected {fourcc}"
    payload = data[128:]
    h, w = u8.shape[:2]
    assert len(payload) == bc_level_bytes(w, h, fourcc), (
        f"{fourcc} level {w}x{h}: {len(payload)} bytes, expected {bc_level_bytes(w, h, fourcc)}")
    return payload


def build_bc(level0_float: np.ndarray, *, fourcc: str, mips: int) -> bytes:
    """DXT1 (RGB) or DXT5 (RGBA) file from a float level 0, full mip chain."""
    level0 = np.asarray(level0_float, dtype=np.float32)
    h, w = level0.shape[:2]
    dims = mip_dims(w, h, mips)
    parts = [header_bc(w, h, mips, fourcc)]
    for (lw, lh), level in zip(dims, mip_chain(level0, mips)):
        assert level.shape[:2] == (lh, lw), f"mip built {level.shape[1]}x{level.shape[0]}, expected {lw}x{lh}"
        parts.append(encode_bc_level(np.ascontiguousarray(q8(level)), fourcc))
    out = b"".join(parts)
    assert len(out) == 128 + sum(bc_level_bytes(lw, lh, fourcc) for lw, lh in dims), "DDS size mismatch"
    return out


def build_bgra8(level0_float: np.ndarray, *, mips: int) -> bytes:
    """Uncompressed BGRA8 file from a float (h, w, 4) level 0 holding R, G, B, A."""
    level0 = np.asarray(level0_float, dtype=np.float32)
    h, w = level0.shape[:2]
    parts = [header_bgra8(w, h, mips)]
    for level in mip_chain(level0, mips):
        parts.append(np.ascontiguousarray(q8(level)[..., [2, 1, 0, 3]]).tobytes())
    return b"".join(parts)


def build_r16f(level0_float: np.ndarray, *, mips: int) -> bytes:
    """Single-channel half-float file (DXGI_FORMAT_R16_FLOAT) from a float (h, w) level 0."""
    level0 = np.asarray(level0_float, dtype=np.float32)
    h, w = level0.shape
    parts = [header_dx10(w, h, mips, DXGI_R16_FLOAT, 2)]
    for level in mip_chain(level0, mips):
        parts.append(np.ascontiguousarray(level.astype("<f2")).tobytes())
    return b"".join(parts)


def read_levels(data: bytes) -> list[np.ndarray]:
    """Decode every level of a file this module (or vanilla) writes.

    R16F: float32 (h, w). BGRA8: uint8 (h, w, 4) in R, G, B, A order. DXT1/DXT5:
    uint8 (h, w, 4) RGBA as Pillow decodes it (so block loss is visible).
    """
    if data[:4] != b"DDS " or struct.unpack_from("<I", data, 4)[0] != 124:
        raise ValueError("not a DDS file")
    hdr = struct.unpack_from("<31I", data, 4)
    h, w, mips = hdr[2], hdr[3], max(1, hdr[6])
    pf_flags, fourcc = hdr[19], data[84:88]
    dims = mip_dims(w, h, mips)
    levels: list[np.ndarray] = []
    pos = 128
    if fourcc == b"DX10":
        fmt = struct.unpack_from("<I", data, 128)[0]
        if fmt != DXGI_R16_FLOAT:
            raise ValueError(f"unsupported DXGI format {fmt}")
        pos = 148
        for lw, lh in dims:
            n = lw * lh * 2
            levels.append(np.frombuffer(data, dtype="<f2", count=lw * lh, offset=pos)
                          .reshape(lh, lw).astype(np.float32))
            pos += n
    elif pf_flags & 0x40 and fourcc != b"DXT1" and fourcc != b"DXT5":
        for lw, lh in dims:
            n = lw * lh * 4
            raw = np.frombuffer(data, dtype=np.uint8, count=n, offset=pos).reshape(lh, lw, 4)
            levels.append(np.ascontiguousarray(raw[..., [2, 1, 0, 3]]))
            pos += n
    elif fourcc in (b"DXT1", b"DXT5"):
        code = fourcc.decode("ascii")
        for lw, lh in dims:
            n = bc_level_bytes(lw, lh, code)
            head = bytearray(data[:128])
            struct.pack_into("<I", head, 12, lh)
            struct.pack_into("<I", head, 16, lw)
            struct.pack_into("<I", head, 20, n)
            struct.pack_into("<I", head, 28, 1)
            im = Image.open(io.BytesIO(bytes(head) + data[pos:pos + n])).convert("RGBA")
            levels.append(np.asarray(im, dtype=np.uint8).copy())
            pos += n
    else:
        raise ValueError(f"unsupported DDS pixel format (flags {pf_flags:#x}, fourCC {fourcc!r})")
    assert pos == len(data), f"{len(data) - pos} trailing bytes after {mips} levels"
    return levels
