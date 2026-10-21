"""DDS read/write for interface textures that override a vanilla file.

An override must keep the vanilla file's dimensions, pixel format and mip count:
the engine lays texticons and buttons out from the texture, and a header that
differs from vanilla's (size, padding, mip count) shifts every place it is drawn.
So the writer never builds a header of its own. It copies the vanilla file's
128-byte header verbatim and appends pixel data in the same layout.

Supported layouts (anything else raises):

* uncompressed 32-bit BGRA (pixel-format flags ``0x41``, masks ff0000/ff00/ff/
  ff000000), any mip count, including a header that records 0 mips (one level);
* DXT1 with a single level (payload encoded by Pillow, punch-through alpha).

Mips are a 2x2 box filter in the stored (sRGB) space, like vanilla's. An odd
dimension is resampled by area (each output pixel averages the 2.5-ish source
pixels it covers) instead of dropping the last row or column. RGB is averaged
weighted by alpha, so the RGB 0 that this module writes under alpha 0 never
bleeds into a dark fringe at small mips.

Public API::

    read_top(path)                       -> uint8 (h, w, 4) RGBA, RGB 0 under alpha 0
    encode_like(vanilla_path, rgba)      -> bytes of a DDS laid out like the vanilla file
    decode_like(vanilla_path, rgba)      -> the top mip as written (shows DXT1 loss in previews)
    write_like(vanilla_path, rgba, out)  -> writes encode_like's bytes
    check_like(vanilla_path, out)        -> list of problems ([] when the file matches)

Deterministic: numpy and Pillow only, no randomness. Byte-identical output needs
the pinned stack in ``mapgen/requirements.txt``.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

HEADER_BYTES = 128
_BGRA_MASKS = (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)


@dataclass(frozen=True)
class Layout:
    width: int
    height: int
    levels: int        # number of stored levels (a header mip count of 0 means 1)
    fmt: str           # "BGRA" or "DXT1"
    header: bytes      # the 128 header bytes, verbatim

    def level_sizes(self) -> list[tuple[int, int]]:
        w, h, out = self.width, self.height, []
        for _ in range(self.levels):
            out.append((w, h))
            w, h = max(1, w // 2), max(1, h // 2)
        return out

    def file_size(self) -> int:
        if self.fmt == "BGRA":
            body = sum(w * h * 4 for w, h in self.level_sizes())
        else:
            body = sum(((w + 3) // 4) * ((h + 3) // 4) * 8 for w, h in self.level_sizes())
        return HEADER_BYTES + body


def layout(path: Path | str) -> Layout:
    """Parse the header of a DDS this module can reproduce; raise on anything else."""
    with open(path, "rb") as f:
        head = f.read(HEADER_BYTES)
    if len(head) < HEADER_BYTES or head[:4] != b"DDS " or struct.unpack_from("<I", head, 4)[0] != 124:
        raise ValueError(f"{path}: not a DDS with a 124-byte header")
    height, width = struct.unpack_from("<II", head, 12)
    mips = struct.unpack_from("<I", head, 28)[0]
    pf_flags = struct.unpack_from("<I", head, 80)[0]
    fourcc = head[84:88]
    bits = struct.unpack_from("<I", head, 88)[0]
    masks = struct.unpack_from("<IIII", head, 92)
    levels = max(1, mips)
    if pf_flags & 0x4:
        if fourcc != b"DXT1":
            raise ValueError(f"{path}: compressed format {fourcc!r} not supported")
        if levels != 1:
            raise ValueError(f"{path}: DXT1 with {levels} mips not supported")
        fmt = "DXT1"
    elif pf_flags == 0x41 and bits == 32 and masks == _BGRA_MASKS:
        fmt = "BGRA"
    else:
        raise ValueError(f"{path}: pixel format flags {pf_flags:#x}/{bits} bpp not supported")
    return Layout(width, height, levels, fmt, head)


def read_top(path: Path | str) -> np.ndarray:
    """The top mip as uint8 RGBA. RGB under alpha 0 is zeroed: hidden colour is never data."""
    with Image.open(path) as im:
        rgba = np.array(im.convert("RGBA"), dtype=np.uint8)
    rgba[rgba[..., 3] == 0, :3] = 0
    return rgba


def _resample_matrix(n: int, new: int) -> np.ndarray:
    """(new, n) area weights: output pixel j averages source span [j*n/new, (j+1)*n/new)."""
    m = np.zeros((new, n), dtype=np.float64)
    for j in range(new):
        s0, s1 = j * n / new, (j + 1) * n / new
        for i in range(int(s0), min(n, int(np.ceil(s1)))):
            m[j, i] = max(0.0, min(s1, i + 1) - max(s0, i))
    return m / m.sum(axis=1, keepdims=True)


def _halve(level: np.ndarray) -> np.ndarray:
    """One mip step on float RGBA (0..255): area box filter, RGB weighted by alpha."""
    h, w = level.shape[:2]
    my = _resample_matrix(h, max(1, h // 2))
    mx = _resample_matrix(w, max(1, w // 2))
    a = level[..., 3]
    pre = level[..., :3] * a[..., None]

    def apply(x: np.ndarray) -> np.ndarray:
        return np.einsum("yh,hw...->yw...", my, np.einsum("xw,hw...->hx...", mx, x))

    a2 = apply(a)
    pre2 = apply(pre)
    rgb2 = np.where(a2[..., None] > 0, pre2 / np.maximum(a2[..., None], 1e-12), 0.0)
    return np.concatenate([rgb2, a2[..., None]], axis=-1)


def _quantize(level: np.ndarray) -> np.ndarray:
    q = np.clip(np.rint(level), 0, 255).astype(np.uint8)
    q[q[..., 3] == 0, :3] = 0
    return q


def mip_chain(rgba: np.ndarray, levels: int) -> list[np.ndarray]:
    """``levels`` uint8 RGBA levels, the first being ``rgba`` itself (RGB 0 under alpha 0)."""
    out = [_quantize(rgba.astype(np.float64))]
    cur = rgba.astype(np.float64)
    for _ in range(levels - 1):
        cur = _halve(cur)
        out.append(_quantize(cur))
        cur = out[-1].astype(np.float64)
    return out


def _dxt1_payload(rgba: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "DDS", pixel_format="DXT1")
    data = buf.getvalue()
    if data[:4] != b"DDS " or data[84:88] != b"DXT1":
        raise RuntimeError("Pillow DXT1 output has an unexpected header (DX10 extension?)")
    return data[HEADER_BYTES:]


def encode_like(vanilla_path: Path | str, rgba: np.ndarray) -> bytes:
    """A DDS with ``vanilla_path``'s header and layout holding ``rgba`` (uint8, vanilla's size)."""
    lay = layout(vanilla_path)
    if rgba.shape != (lay.height, lay.width, 4) or rgba.dtype != np.uint8:
        raise ValueError(f"image {rgba.shape} {rgba.dtype} does not match {lay.width}x{lay.height} RGBA uint8")
    if lay.fmt == "BGRA":
        body = b"".join(lv[..., [2, 1, 0, 3]].tobytes() for lv in mip_chain(rgba, lay.levels))
    else:
        punch = rgba.copy()
        punch[..., 3] = np.where(rgba[..., 3] >= 128, 255, 0)
        punch[punch[..., 3] == 0, :3] = 0
        body = _dxt1_payload(punch)
    data = lay.header + body
    if len(data) != lay.file_size():
        raise RuntimeError(f"encoded {len(data)} bytes, layout expects {lay.file_size()}")
    return data


def decode_like(vanilla_path: Path | str, rgba: np.ndarray) -> np.ndarray:
    """The top mip as the game will see it once written (block compression included)."""
    with Image.open(io.BytesIO(encode_like(vanilla_path, rgba))) as im:
        out = np.array(im.convert("RGBA"), dtype=np.uint8)
    out[out[..., 3] == 0, :3] = 0
    return out


def write_like(vanilla_path: Path | str, rgba: np.ndarray, out_path: Path | str) -> None:
    data = encode_like(vanilla_path, rgba)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)


def check_like(vanilla_path: Path | str, out_path: Path | str) -> list[str]:
    """Header bytes, file size and level count of ``out_path`` against the vanilla file."""
    out_path = Path(out_path)
    if not out_path.is_file():
        return [f"{out_path}: missing"]
    lay = layout(vanilla_path)
    data = out_path.read_bytes()
    problems = []
    if data[:HEADER_BYTES] != lay.header:
        problems.append(f"{out_path}: header differs from vanilla")
    if len(data) != lay.file_size():
        problems.append(f"{out_path}: {len(data)} bytes, vanilla layout is {lay.file_size()}")
    try:
        with Image.open(out_path) as im:
            if im.size != (lay.width, lay.height):
                problems.append(f"{out_path}: decodes as {im.size}, vanilla is {(lay.width, lay.height)}")
    except Exception as exc:  # noqa: BLE001 - any decode failure is a finding
        problems.append(f"{out_path}: does not decode ({exc})")
    return problems
