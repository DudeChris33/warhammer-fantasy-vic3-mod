"""Rasterize committed river polylines into a valid Vic3 ``rivers.png``.

A Vic3 river map is an indexed bitmap with strict, unforgiving rules — get them
wrong and the engine drops rivers silently or logs errors. This module owns those
rules so the generator (and the fixture) cannot violate them by accident:

* **Background** is the land/sea mask: land -> index 255, sea -> 254.
* **A river is a one-pixel-wide line.** Width is encoded by *colour*, not by
  painting fat pixels; a 2x2 block is malformed. Lines are drawn with Bresenham
  (``skimage.draw.line``, deterministic) and thinned if a corner doubles up.
* **Each stream has exactly one source** — its first pixel, index 0 (green).
* **The body widens downstream** through the measured ramp (3 -> 4 -> 6 -> 8),
  capped at the stream's declared width, so rivers grow toward the mouth as
  vanilla's do.
* **A stream reaches its mouth**: a ``sea`` stream's last pixel is adjacent to
  open water; a ``confluence`` stream's last pixel is index 1 (red) and touches
  another stream.

Everything is validated *before* the PNG is written, so an authoring mistake is a
loud offline error rather than a subtle in-game one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage
from skimage.draw import line as _bres_line

from worldgen import raster, schema

# Semantic indices (mirrors tools/lut/rivers_palette.json; validated on load).
LAND = 255
SEA = 254
SOURCE = 0
MERGE = 1
SPLIT = 2


class RiverError(RuntimeError):
    """A river geometry cannot be rasterized into a valid rivers.png."""


@dataclass(frozen=True)
class RiverPalette:
    indices: dict
    width_ramp: tuple[int, ...]
    table: list[tuple[int, int, int]]  # 256 entries


def load_palette(path: Path) -> RiverPalette:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    idx = d["indices"]
    if idx.get("land") != LAND or idx.get("sea") != SEA or idx.get("source") != SOURCE:
        raise RiverError(f"{path}: palette semantic indices disagree with worldgen.rivers")
    table = [(0, 0, 0)] * 256
    for k, rgb in d["palette"].items():
        table[int(k)] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    return RiverPalette(idx, tuple(d["width_ramp"]), table)


# ---------------------------------------------------------------------------
# Polyline -> ordered 1px path
# ---------------------------------------------------------------------------

def _ordered_path(points: list[tuple[float, float]], width: int, height: int,
                  wrap_x: bool) -> list[tuple[int, int]]:
    """Source-first list of (x, y) pixels along the polyline, deduped, 1px wide.

    Consecutive vertices are joined with Bresenham segments. When the world wraps
    and a segment crosses the seam, it is drawn in the continuous frame and folded
    back with ``% width`` — the same trick the polygon rasterizer uses — so a
    river mouth on the far side of the antimeridian still connects.
    """
    path: list[tuple[int, int]] = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if wrap_x and abs(x1 - x0) > width / 2:  # shorter way is across the seam
            if x1 > x0:
                x1 -= width
            else:
                x1 += width
        rr, cc = _bres_line(int(round(y0)), int(round(x0)), int(round(y1)), int(round(x1)))
        for y, x in zip(rr.tolist(), cc.tolist()):
            xx = x % width if wrap_x else x
            if 0 <= y < height and (0 <= xx < width):
                px = (xx, y)
                if not path or path[-1] != px:
                    path.append(px)
    # Drop any immediate backtracks / exact repeats introduced at vertices.
    dedup: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for px in path:
        if px not in seen:
            dedup.append(px)
            seen.add(px)
    return dedup


def _truncate_at_sea(path: list[tuple[int, int]], land: np.ndarray) -> list[tuple[int, int]]:
    """Keep the leading run of land pixels — the river up to where it meets water."""
    out: list[tuple[int, int]] = []
    for (x, y) in path:
        if not land[y, x]:
            break
        out.append((x, y))
    return out


def _ramp_index(frac: float, ramp: tuple[int, ...], width: int) -> int:
    """Width index at fractional distance ``frac`` (0=source) capped at ``width``."""
    usable = [w for w in ramp if w <= width] or [ramp[0]]
    return usable[min(len(usable) - 1, int(frac * len(usable)))]


# ---------------------------------------------------------------------------
# Rasterize + validate
# ---------------------------------------------------------------------------

def rasterize(streams: list[schema.RiverStream], land: np.ndarray, palette: RiverPalette,
              wrap_x: bool = True, ocean: np.ndarray | None = None) -> np.ndarray:
    """Return the ``rivers.png`` index array for ``streams`` over the land mask.

    ``ocean`` (board #3742) is the navigable-sea mask; where it is given, a river
    *source* may sit on a lake shore (a lake-fed outflow) but never on the ocean,
    and it is the ocean — not every water pixel — a source must stay clear of.
    Absent, it defaults to ``~land`` (all water is ocean, the pre-lake behaviour).

    Validates every rule and raises :class:`RiverError` on the first violation, so
    a malformed river never reaches disk.
    """
    h, w = land.shape
    if ocean is None:
        ocean = ~land
    idx = np.where(land, np.uint8(LAND), np.uint8(SEA))
    paths: dict[str, list[tuple[int, int]]] = {}

    for st in streams:
        path = _ordered_path(st.points, w, h, wrap_x)
        if st.mouth == "sea":
            # A river flows until it reaches the water: end at the last land pixel
            # before the coast. This absorbs the overshoot a straight final segment
            # makes into a concave shoreline — the discarded pixels were the bit of
            # the line already in the sea — and leaves a mouth guaranteed adjacent
            # to open water. (A confluence stream keeps its whole path; sea on it
            # would be a real authoring error, caught in _validate.) An endorheic
            # stream keeps its whole path — it ends inland by design, nothing to trim.
            path = _truncate_at_sea(path, land)
        if len(path) < 2:
            raise RiverError(f"{st.name}: degenerate path ({len(path)} px after coast trim)")
        paths[st.name] = path

    # Where two streams meet, their 1px lines can leave a 2x2 river block that
    # Vic3 rejects. Nudge the redundant pixel of each such block back to land
    # *before* painting, so the endpoint markers below land on the kept pixels.
    _thin_junctions(paths, land)

    # Paint bodies first (so confluence tests can see other streams), then the
    # source and mouth markers on top.
    for st in streams:
        path = paths[st.name]
        n = len(path)
        for i, (x, y) in enumerate(path):
            idx[y, x] = _ramp_index(i / max(1, n - 1), palette.width_ramp, st.width)

    for st in streams:
        path = paths[st.name]
        (sx, sy) = path[0]
        # Head marker: a headwater spring is green (0); a distributary splitting
        # off a larger river is yellow (2) — the mirror of the red merge marker.
        idx[sy, sx] = SPLIT if st.head == "split" else SOURCE
        if st.mouth == "confluence":
            mx, my = path[-1]
            idx[my, mx] = MERGE

    _validate(streams, paths, idx, land, wrap_x, ocean)
    return idx


def _thin_junctions(paths: dict[str, list[tuple[int, int]]], land: np.ndarray) -> None:
    """Drop pixels that only exist to fill a 2x2 river block, preserving each
    stream's endpoints and connectivity.

    A river must be one pixel wide. Where lines cross or graze, a 2x2 all-river
    block can appear; the redundant member is an *interior* pixel of some stream
    whose two path-neighbours are themselves 8-adjacent, so removing it leaves the
    path connected. Endpoints (source and mouth) are never candidates — they carry
    meaning — so a junction always resolves in favour of keeping the streams'
    mouths intact. Deterministic: streams and indices are walked in sorted order.
    """
    occupied: set[tuple[int, int]] = set()
    for name in sorted(paths):
        occupied.update(paths[name])

    def is_river(x, y):
        return (x, y) in occupied

    changed = True
    while changed:
        changed = False
        for name in sorted(paths):
            path = paths[name]
            for i in range(1, len(path) - 1):  # never an endpoint
                x, y = path[i]
                px, py = path[i - 1]
                nx, ny = path[i + 1]
                # Redundant only if its path-neighbours are 8-adjacent without it.
                if max(abs(px - nx), abs(py - ny)) > 1:
                    continue
                # Part of a 2x2 all-river block?
                in_block = any(
                    is_river(x + dx, y) and is_river(x, y + dy) and is_river(x + dx, y + dy)
                    for dx in (-1, 1) for dy in (-1, 1)
                )
                if in_block:
                    occupied.discard((x, y))
                    paths[name] = path[:i] + path[i + 1:]
                    changed = True
                    break
            if changed:
                break


def _neighbors8(x: int, y: int, w: int, h: int, wrap_x: bool):
    for dy in (-1, 0, 1):
        ny = y + dy
        if ny < 0 or ny >= h:
            continue
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx = (x + dx) % w if wrap_x else x + dx
            if 0 <= nx < w:
                yield nx, ny


def _validate(streams, paths, idx, land, wrap_x, ocean=None) -> None:
    h, w = land.shape
    if ocean is None:
        ocean = ~land
    river_pixels = {px for p in paths.values() for px in p}

    # One green source per headwater stream (a split distributary is yellow, not
    # green), and each sits inland.
    n_source_heads = sum(1 for st in streams if getattr(st, "head", "source") == "source")
    n_sources = int((idx == SOURCE).sum())
    if n_sources != n_source_heads:
        raise RiverError(f"expected {n_source_heads} green source pixels, painted {n_sources}")

    for st in streams:
        path = paths[st.name]
        # The path is one connected 8-adjacent run. Without this, an out-of-range
        # or mistyped vertex whose pixels get clipped leaves a river that jumps a
        # gap — and every other check here would still pass, because they only
        # look at endpoints and per-pixel properties.
        for i in range(1, len(path)):
            (ax, ay), (bx, by) = path[i - 1], path[i]
            dx = min(abs(ax - bx), w - abs(ax - bx)) if wrap_x else abs(ax - bx)
            if max(dx, abs(ay - by)) > 1:
                raise RiverError(
                    f"{st.name}: path is not contiguous — ({ax}, {ay}) to ({bx}, {by}) "
                    f"jumps {max(dx, abs(ay - by))} px (a clipped or mistyped vertex?)"
                )
        # Every river pixel is on land (a river drawn across the sea is malformed).
        for (x, y) in path:
            if not land[y, x]:
                raise RiverError(f"{st.name}: river pixel ({x}, {y}) lies on sea, not land")
        # Head check. A source (spring) is clear of the ocean — no navigable sea
        # in its 8-neighbourhood; a lake shore is allowed (a lake-fed outflow,
        # board #3742), so this checks ``ocean``, not all water. A split
        # distributary instead branches off the trunk, so its first pixel must
        # touch another stream — the mirror of the confluence check below.
        sx, sy = path[0]
        if getattr(st, "head", "source") == "split":
            others = river_pixels - set(path)
            if not any((nx, ny) in others for nx, ny in _neighbors8(sx, sy, w, h, wrap_x)):
                raise RiverError(f"{st.name}: split head ({sx}, {sy}) touches no other stream")
        elif getattr(st, "coastal_source", False):
            pass  # a manual flow override put this source on the coast on purpose
        elif any(ocean[ny, nx] for nx, ny in _neighbors8(sx, sy, w, h, wrap_x)):
            raise RiverError(f"{st.name}: source ({sx}, {sy}) is on the sea coast; sources must be inland or lake-fed")
        # Mouth reaches its target.
        mx, my = path[-1]
        if st.mouth == "sea":
            if not any(not land[ny, nx] for nx, ny in _neighbors8(mx, my, w, h, wrap_x)):
                raise RiverError(f"{st.name}: sea mouth ({mx}, {my}) does not touch open water")
        elif st.mouth == "endorheic":
            # A river that dries up inland: it just ends, no water and no marker
            # required. (Board #3742: the Marshes of Madness are a drainage sink.)
            pass
        else:  # confluence
            others = river_pixels - set(path)
            if not any((nx, ny) in others for nx, ny in _neighbors8(mx, my, w, h, wrap_x)):
                raise RiverError(f"{st.name}: confluence mouth ({mx}, {my}) touches no other stream")

    n_blocks, longest_run = measure_2x2_blocks(idx, wrap_x)
    # Vic3 tolerates incidental 2x2 blocks: its own shipped rivers.png has 21, at
    # wide-river bends and confluences. So a raw count alone is the wrong test —
    # it cannot tell 20 blocks scattered across 20 real junctions from 20 in a row,
    # which is what "two streams traced parallel instead of merging" looks like and
    # is the actual defect worth catching. Gate on both: a generous global cap, and
    # a much tighter cap on the longest *contiguous run* of blocks.
    if n_blocks > MAX_2X2_BLOCKS:
        raise RiverError(
            f"{n_blocks} 2x2 river blocks exceeds the tolerance of {MAX_2X2_BLOCKS} "
            f"(vanilla ships 21) — streams are probably running parallel"
        )
    if longest_run > MAX_2X2_RUN:
        raise RiverError(
            f"a run of {longest_run} connected 2x2 river blocks exceeds the limit of "
            f"{MAX_2X2_RUN} — two streams run adjacent for a stretch instead of merging"
        )


#: Above this, a 2x2-block count means a systematic fault, not the incidental
#: bends vanilla itself carries (21). Comfortably above vanilla's count.
MAX_2X2_BLOCKS = 30

#: Longest run of *connected* 2x2 blocks. A parallel-running pair of streams
#: produces one block per row, so a long run is the signature of that defect,
#: whereas a genuine junction or wide-river bend produces only a few.
#: Calibrated against vanilla, not guessed: the shipped 1.13.8 rivers.png has 21
#: blocks with a longest run of **5**, so anything at or below 5 demonstrably
#: occurs in cartography the engine itself ships. 8 leaves headroom above that
#: while still catching a parallel run, which reaches into the tens.
MAX_2X2_RUN = 8


def measure_2x2_blocks(idx: np.ndarray, wrap_x: bool) -> tuple[int, int]:
    """``(total 2x2 all-river blocks, largest connected run of them)``."""
    is_river = ~np.isin(idx, [LAND, SEA])
    b = np.roll(is_river, -1, axis=1) if wrap_x else np.pad(is_river[:, 1:], ((0, 0), (0, 1)))
    block = is_river[:-1, :] & is_river[1:, :] & b[:-1, :] & b[1:, :]
    total = int(block.sum())
    if total == 0:
        return 0, 0
    lab, n = ndimage.label(block, structure=np.ones((3, 3)))
    if n == 0:
        return total, 0
    return total, int(np.bincount(lab.ravel())[1:].max())


def count_2x2_blocks(idx: np.ndarray, wrap_x: bool) -> int:
    """Number of 2x2 all-river blocks (rivers should be ~1px; a few are normal)."""
    return measure_2x2_blocks(idx, wrap_x)[0]


def write_rivers_png(path, idx: np.ndarray, palette: RiverPalette) -> None:
    raster.write_indexed_png(path, idx, palette.table)
