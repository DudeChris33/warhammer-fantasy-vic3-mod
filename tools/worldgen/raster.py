"""Shared rasterization + geometry primitives for the map generators.

Everything here is deterministic and, where the world wraps, **wrap-aware** at
the ``x=0`` / ``x=width-1`` seam. Province bitmaps are written as pixel-exact
RGB PNGs (no anti-aliasing, no palette quantization) so every pixel is an exact
``xRRGGBB`` province id — matching vanilla / Exether ``provinces.png`` (mode RGB).
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

Color = tuple[int, int, int]
Point = tuple[float, float]

# 24-bit RGB colour space.
_RGB_SPACE = 1 << 24
# An odd step is coprime to 2**24, so repeatedly adding it mod 2**24 visits every
# colour exactly once before repeating — a full-period, reproducible permutation.
# (~golden-ratio scaled into the 24-bit range, and odd.)
_ALLOC_STEP = 0x9E3779


# ---------------------------------------------------------------------------
# Colour <-> hex-token conversion
# ---------------------------------------------------------------------------

def color_to_hex(color: Color) -> str:
    """``(r, g, b) -> "xRRGGBB"`` (uppercase), the province-id token form."""
    r, g, b = color
    return "x{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))


def hex_to_color(token: str) -> Color:
    """Parse an ``xRRGGBB`` token (either case, optional quotes) to ``(r, g, b)``."""
    t = token.strip().strip('"')
    if len(t) != 7 or t[0] not in "xX":
        raise ValueError(f"not a valid province colour token: {token!r}")
    try:
        val = int(t[1:], 16)
    except ValueError as exc:
        raise ValueError(f"not a valid province colour token: {token!r}") from exc
    return ((val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF)


# ---------------------------------------------------------------------------
# Deterministic globally-unique colour allocator
# ---------------------------------------------------------------------------

class ColorAllocator:
    """Hands out globally-unique province colours in a deterministic sequence.

    The sequence is a fixed full-period permutation of the 24-bit space seeded
    from ``seed``, so regeneration reproduces identical colours. Colours already
    issued are never repeated, and any colour in ``reserved`` is skipped — so if
    the sea-zone colours are allocated first (or supplied as ``reserved``), land
    allocation can never collide with a reserved sea colour. ``(0, 0, 0)`` is
    always reserved as a border/edge sentinel and never issued.

    Asserts (fails loudly) on collision-free exhaustion of the colour space.
    """

    def __init__(self, seed: int, reserved: set[Color] | None = None) -> None:
        self._cur = seed % _RGB_SPACE
        self._issued: set[Color] = set()
        self._reserved: set[Color] = {(0, 0, 0)}
        if reserved:
            self._reserved.update(tuple(c) for c in reserved)

    def reserve(self, color: Color) -> None:
        self._reserved.add(tuple(color))

    def allocate(self) -> Color:
        for _ in range(_RGB_SPACE):
            self._cur = (self._cur + _ALLOC_STEP) % _RGB_SPACE
            color = ((self._cur >> 16) & 0xFF, (self._cur >> 8) & 0xFF, self._cur & 0xFF)
            if color in self._reserved or color in self._issued:
                continue
            self._issued.add(color)
            return color
        raise AssertionError("ColorAllocator exhausted the 24-bit colour space")


# ---------------------------------------------------------------------------
# Wrap-aware distance
# ---------------------------------------------------------------------------

def wrap_signed_delta(a: float, b: float, span: float) -> float:
    """Minimal signed ``a - b`` on a cyclic axis of width ``span``, in (-span/2, span/2]."""
    d = (a - b) % span
    if d > span / 2:
        d -= span
    return d


def axis_delta(a: float, b: float, span: float, wrap: bool) -> float:
    """Absolute distance between two coordinates on one axis, wrap-aware if ``wrap``."""
    if wrap:
        return abs(wrap_signed_delta(a, b, span))
    return abs(a - b)


def point_distance(p: Point, q: Point, width: float, wrap_x: bool = True) -> float:
    """Euclidean distance, wrapping on the x axis when ``wrap_x``."""
    dx = axis_delta(p[0], q[0], width, wrap_x)
    dy = abs(p[1] - q[1])
    return math.hypot(dx, dy)


def segment_point_distance(
    p: Point, a: Point, b: Point, width: float, wrap_x: bool = True
) -> float:
    """Distance from point ``p`` to segment ``a``-``b``, wrapping on x.

    Segments and the query point are re-expressed in the continuous frame nearest
    ``a`` before the standard point-to-segment projection, so a ridge/river/coast
    polyline that crosses the seam is measured correctly (used by P2's relief
    falloff). Assumes the segment is shorter than half the canvas width, which
    holds for every authored polyline.
    """
    if wrap_x:
        bx = a[0] + wrap_signed_delta(b[0], a[0], width)
        px = a[0] + wrap_signed_delta(p[0], a[0], width)
    else:
        bx, px = b[0], p[0]
    ax, ay, by, py = a[0], a[1], b[1], p[1]
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    seg_len2 = vx * vx + vy * vy
    t = 0.0 if seg_len2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / seg_len2))
    cx, cy = ax + t * vx, ay + t * vy
    return math.hypot(px - cx, py - cy)


# ---------------------------------------------------------------------------
# Voronoi labelling (wrap-aware nearest-seed assignment)
# ---------------------------------------------------------------------------

def voronoi_labels(
    pixels: list[tuple[int, int]],
    seeds: list[Point],
    width: int,
    wrap_x: bool = True,
) -> list[int]:
    """For each pixel, the index of the nearest seed (wrap-aware).

    Ties break to the lowest seed index (deterministic). Brute-force O(pixels x
    seeds) — correct and adequate for a state cell's pixel count; P3 keeps these
    exact semantics for the full-scale subdivision.
    """
    labels: list[int] = []
    for (x, y) in pixels:
        best_i = 0
        best_d = math.inf
        for i, (sx, sy) in enumerate(seeds):
            dx = axis_delta(x, sx, width, wrap_x)
            dy = y - sy
            d = dx * dx + dy * dy
            if d < best_d:
                best_d = d
                best_i = i
        labels.append(best_i)
    return labels


# ---------------------------------------------------------------------------
# Polygon rasterization (wrap-aware fill with hole support)
# ---------------------------------------------------------------------------

def rasterize_polygon(
    outer: list[Point],
    holes: list[list[Point]],
    width: int,
    height: int,
    wrap_x: bool = True,
) -> set[tuple[int, int]]:
    """Pixel set inside ``outer`` minus ``holes`` (no anti-aliasing).

    A polygon whose x extends past ``[0, width)`` encodes a seam-straddling shape:
    it is rasterized on a strip covering its full x-extent, then each filled pixel's
    x is folded back with ``% width`` when ``wrap_x`` (out-of-range pixels are
    dropped when not). Integer x-translation makes PIL's fill translation-invariant,
    so a hole cut from one polygon removes exactly the pixels an identical polygon
    fills — adjacent cells sharing a border tile without gaps or overlap.
    """
    all_x = [pt[0] for pt in outer]
    for hole in holes:
        all_x.extend(pt[0] for pt in hole)
    min_x = math.floor(min(all_x))
    max_x = math.ceil(max(all_x))
    strip_w = max_x - min_x + 1
    if strip_w <= 0 or height <= 0:
        return set()

    img = Image.new("1", (strip_w, height), 0)
    draw = ImageDraw.Draw(img)

    def _shift(poly: list[Point]) -> list[tuple[float, float]]:
        return [(px - min_x, py) for px, py in poly]

    draw.polygon(_shift(outer), fill=1)
    for hole in holes:
        draw.polygon(_shift(hole), fill=0)

    filled = np.asarray(img, dtype=bool)  # shape (height, strip_w)
    ys, ixs = np.nonzero(filled)
    xs = ixs + min_x
    pixels: set[tuple[int, int]] = set()
    if wrap_x:
        xs = np.mod(xs, width)
        for x, y in zip(xs.tolist(), ys.tolist()):
            pixels.add((x, y))
    else:
        for x, y in zip(xs.tolist(), ys.tolist()):
            if 0 <= x < width:
                pixels.add((x, y))
    return pixels


# ---------------------------------------------------------------------------
# Pixel-grid adjacency + connectivity (wrap-aware)
# ---------------------------------------------------------------------------

def neighbors4(x: int, y: int, width: int, height: int, wrap_x: bool = True):
    """4-connected neighbours of ``(x, y)``, wrapping on x when ``wrap_x``."""
    if x > 0:
        yield (x - 1, y)
    elif wrap_x:
        yield (width - 1, y)
    if x < width - 1:
        yield (x + 1, y)
    elif wrap_x:
        yield (0, y)
    if y > 0:
        yield (x, y - 1)
    if y < height - 1:
        yield (x, y + 1)


def connected_components(
    pixels, width: int, height: int, wrap_x: bool = True
) -> list[set[tuple[int, int]]]:
    """Partition ``pixels`` into 4-connected components (wrap-aware).

    The partition itself is deterministic (independent of iteration order); only
    the order of the returned list is not, which callers here never depend on.
    """
    remaining = set(pixels)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = next(iter(remaining))
        remaining.discard(start)
        comp = {start}
        stack = [start]
        while stack:
            cx, cy = stack.pop()
            for nb in neighbors4(cx, cy, width, height, wrap_x):
                if nb in remaining:
                    remaining.discard(nb)
                    comp.add(nb)
                    stack.append(nb)
        components.append(comp)
    return components


# ---------------------------------------------------------------------------
# PNG IO (lossless, deterministic)
# ---------------------------------------------------------------------------

def write_rgb_png(path, rgb: np.ndarray) -> None:
    """Write an ``(H, W, 3)`` uint8 array as a lossless RGB PNG.

    No palette, no anti-aliasing, no timestamp chunk (Pillow omits ``tIME`` by
    default) and a fixed compression level, so re-running the generator produces
    byte-identical output.
    """
    arr = np.ascontiguousarray(rgb, dtype=np.uint8)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"expected an (H, W, 3) uint8 array, got shape {arr.shape}")
    Image.fromarray(arr, mode="RGB").save(
        str(path), format="PNG", optimize=False, compress_level=6
    )


def read_rgb_png(path) -> np.ndarray:
    """Read a PNG as an ``(H, W, 3)`` uint8 array (forces RGB)."""
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def write_gray16_png(path, gray: np.ndarray) -> None:
    """Write an ``(H, W)`` uint16 array as a **true 16-bit** grayscale PNG.

    ``map_data/heightmap.png`` must be 16-bit or the in-game map editor refuses
    to pack it — an 8-bit file silently loses the entire vertical range. Pillow
    writes 16-bit grayscale only from mode ``I;16``, and only when the array is
    little-endian uint16, so both are forced here rather than trusted. Vanilla's
    own ``heightmap.png`` reads back as mode ``I;16``; so does this.
    """
    arr = np.ascontiguousarray(gray, dtype="<u2")
    if arr.ndim != 2:
        raise ValueError(f"expected an (H, W) uint16 array, got shape {arr.shape}")
    im = Image.frombytes("I;16", (arr.shape[1], arr.shape[0]), arr.tobytes())
    im.save(str(path), format="PNG", optimize=False, compress_level=6)


def read_gray16_png(path) -> np.ndarray:
    """Read a 16-bit grayscale PNG as an ``(H, W)`` uint16 array."""
    with Image.open(path) as im:
        if im.mode not in ("I;16", "I;16L", "I;16B", "I"):
            raise ValueError(f"{path}: expected a 16-bit grayscale PNG, got mode {im.mode}")
        return np.asarray(im, dtype=np.uint16)


def write_mask_png(path, mask: np.ndarray) -> None:
    """Write a boolean mask as a 1-bit PNG (mode ``1``).

    Used for the committed ``land_sea_mask.png``: at canvas size a 1-bit file is
    a couple of hundred KB where an RGB one would be tens of MB, and the
    round-trip is exact, which matters because this mask — not the heightmap — is
    what defines the coastline every later phase builds on.
    """
    arr = np.ascontiguousarray(mask, dtype=bool)
    if arr.ndim != 2:
        raise ValueError(f"expected an (H, W) boolean array, got shape {arr.shape}")
    Image.fromarray(arr).save(str(path), format="PNG", optimize=False, compress_level=6)


def read_mask_png(path) -> np.ndarray:
    """Read a 1-bit mask PNG back as a boolean ``(H, W)`` array."""
    with Image.open(path) as im:
        return np.asarray(im.convert("1"), dtype=bool)


def write_indexed_png(path, index: np.ndarray, palette: list[Color]) -> None:
    """Write an ``(H, W)`` uint8 index array as a palette PNG (mode ``P``).

    ``map_data/rivers.png`` is a palette image whose *index* values are semantic
    (source / merge / split / flow width / land / sea), so the file must keep its
    indices exactly — any conversion through RGB would let a re-save remap them.
    The palette is padded to the full 256 entries because Pillow writes only as
    many entries as it is given, and vanilla's file carries all 256.
    """
    arr = np.ascontiguousarray(index, dtype=np.uint8)
    if arr.ndim != 2:
        raise ValueError(f"expected an (H, W) uint8 array, got shape {arr.shape}")
    if len(palette) > 256:
        raise ValueError(f"palette has {len(palette)} entries, max 256")
    flat: list[int] = []
    for c in palette:
        flat.extend(int(v) for v in c)
    flat.extend([0] * (768 - len(flat)))
    im = Image.fromarray(arr, mode="P")
    im.putpalette(flat)
    im.save(str(path), format="PNG", optimize=False, compress_level=6)


def read_indexed_png(path) -> tuple[np.ndarray, list[Color]]:
    """Read a palette PNG as ``(index_array, palette)`` without touching indices."""
    with Image.open(path) as im:
        if im.mode != "P":
            raise ValueError(f"{path}: expected a palette PNG, got mode {im.mode}")
        flat = im.getpalette() or []
        flat = list(flat) + [0] * (768 - len(flat))
        palette = [(flat[i * 3], flat[i * 3 + 1], flat[i * 3 + 2]) for i in range(256)]
        return np.asarray(im, dtype=np.uint8), palette
