"""Drainage hydrology — derive a river network from the committed heightmap.

The rivers are generated the same way the relief is: from the terrain itself. On
a real elevation surface, water fills pits, runs downhill, and gathers into
channels that reach the sea through the actual valleys — so a drainage network
computed from the heightmap gives dense, naturally-meandering rivers that match
the coastline and the relief *by construction*, instead of hand-drawn lines laid
over a coast they were never measured against. The Empire basin drains to the Sea
of Claws exactly as the Reik does; the canon names are applied to the matching
channels in the S6 naming pass.

The standard three steps, all deterministic (no RNG, fixed tie-breaks):

1. **Priority-flood depression fill** (Barnes 2014) — raise every pit just enough
   that all land has a monotone downhill path to the sea. The heap is keyed by
   ``(elevation, insertion_counter)`` so equal elevations resolve in a fixed
   order, and an epsilon is added as each cell is filled so flat regions acquire
   a gentle gradient toward their outlet rather than an arbitrary one.
2. **D8 flow direction** — each land cell drains to its lowest of 8 neighbours,
   ties broken to the lowest neighbour index.
3. **Flow accumulation** — cells processed highest-first, each passing its count
   downstream. Channels are the cells whose accumulation exceeds a threshold.

Everything is wrap-aware on x (the canvas is periodic in longitude).
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np

# 8 neighbour offsets, in a fixed order so tie-breaks are deterministic.
# Index i is the direction "flow leaves toward"; -1 means no flow (sink/sea).
_D8 = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))


def _wrap_x(x: int, w: int) -> int:
    return x % w


def fill_depressions(elev: np.ndarray, land: np.ndarray, wrap_x: bool = True,
                     epsilon: float = 1e-3) -> np.ndarray:
    """Priority-flood fill so every land cell drains monotonically to the sea.

    Returns a filled copy of ``elev``. Sea cells are the outlets; the flood grows
    inward from the coast, and each newly filled cell is raised to at least its
    neighbour's filled level plus ``epsilon`` — the epsilon is what turns a flat
    plateau into a faint ramp toward its exit, so flat areas do not braid into
    parallel false channels.
    """
    h, w = elev.shape
    filled = elev.astype(np.float64).copy()
    visited = ~land  # sea is the outlet set, already "done"
    heap: list[tuple[float, int, int, int]] = []
    counter = 0

    # Seed the heap with coastal land cells (land 4-adjacent to sea).
    ys, xs = np.nonzero(land)
    for y, x in zip(ys.tolist(), xs.tolist()):
        coastal = False
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if nx < 0 or nx >= w:
                if wrap_x:
                    nx = _wrap_x(nx, w)
                else:
                    continue
            if 0 <= ny < h and not land[ny, nx]:
                coastal = True
                break
        if coastal:
            heapq.heappush(heap, (float(filled[y, x]), counter, y, x))
            counter += 1
            visited[y, x] = True

    while heap:
        level, _, y, x = heapq.heappop(heap)
        for dy, dx in _D8:
            ny, nx = y + dy, x + dx
            if ny < 0 or ny >= h:
                continue
            if nx < 0 or nx >= w:
                if not wrap_x:
                    continue
                nx = _wrap_x(nx, w)
            if visited[ny, nx]:
                continue
            visited[ny, nx] = True
            # Raise into the pit: at least the current level + epsilon.
            filled[ny, nx] = max(float(elev[ny, nx]), level + epsilon)
            heapq.heappush(heap, (filled[ny, nx], counter, ny, nx))
            counter += 1
    return filled


def flow_directions(filled: np.ndarray, land: np.ndarray, wrap_x: bool = True) -> np.ndarray:
    """D8 direction index (0..7 into ``_D8``) per land cell, -1 for sea/outlet.

    A land cell drains to its lowest neighbour; a coastal cell whose lowest
    neighbour is sea drains to sea and is marked an outlet (-1) — the river ends
    there. Deterministic: the first neighbour achieving the minimum wins, and the
    offsets are in a fixed order.
    """
    h, w = filled.shape
    direction = np.full((h, w), -1, dtype=np.int8)
    ys, xs = np.nonzero(land)
    for y, x in zip(ys.tolist(), xs.tolist()):
        best_i = -1
        best = filled[y, x]
        drains_to_sea = False
        for i, (dy, dx) in enumerate(_D8):
            ny, nx = y + dy, x + dx
            if ny < 0 or ny >= h:
                continue
            if nx < 0 or nx >= w:
                if not wrap_x:
                    continue
                nx = _wrap_x(nx, w)
            if not land[ny, nx]:
                drains_to_sea = True
                continue
            if filled[ny, nx] < best:
                best = filled[ny, nx]
                best_i = i
        # If a downhill land neighbour exists, follow it; else, if adjacent to
        # sea, this is a coastal outlet (river mouth) — leave direction -1.
        if best_i >= 0 and not (drains_to_sea and filled[y, x] <= best):
            direction[y, x] = best_i
    return direction


def _downstream(y: int, x: int, direction: np.ndarray, w: int, wrap_x: bool):
    d = direction[y, x]
    if d < 0:
        return None
    dy, dx = _D8[d]
    ny, nx = y + dy, x + dx
    if nx < 0 or nx >= w:
        nx = _wrap_x(nx, w) if wrap_x else nx
    return (ny, nx)


def flow_accumulation(direction: np.ndarray, land: np.ndarray, filled: np.ndarray,
                      wrap_x: bool = True) -> np.ndarray:
    """Number of cells draining through each cell (its own cell included).

    Processing land cells highest-filled-first guarantees every upstream cell is
    handled before the cell it drains into, so a single pass accumulates exactly.
    """
    h, w = direction.shape
    accum = land.astype(np.int64)  # each land cell contributes 1
    ys, xs = np.nonzero(land)
    order = np.argsort(-filled[ys, xs], kind="stable")
    ys, xs = ys[order], xs[order]
    for y, x in zip(ys.tolist(), xs.tolist()):
        ds = _downstream(y, x, direction, w, wrap_x)
        if ds is None:
            continue
        ny, nx = ds
        if 0 <= ny < h:
            accum[ny, nx] += accum[y, x]
    return accum


def build_network(elev: np.ndarray, land: np.ndarray, threshold: int,
                  wrap_x: bool = True) -> dict:
    """Run the whole drainage pipeline. Returns filled/direction/accum/channel.

    Convenience wrapper so callers (the generator, the fixture, QA) all drive the
    same sequence in the same order rather than re-deriving it.
    """
    filled = fill_depressions(elev, land, wrap_x=wrap_x)
    direction = flow_directions(filled, land, wrap_x=wrap_x)
    accum = flow_accumulation(direction, land, filled, wrap_x=wrap_x)
    channel = (accum >= threshold) & land
    return {"filled": filled, "direction": direction, "accum": accum, "channel": channel}


def thin_to_single_pixel(channel: np.ndarray, accum: np.ndarray,
                         wrap_x: bool = True) -> np.ndarray:
    """Reduce the channel mask so no 2x2 block is fully channel.

    Vic3 wants rivers about one pixel wide. A D8 network is already thin, but
    diagonal steps can leave 2x2 squares filled. Dropping the *lowest-accumulation*
    member of each such square removes the redundant corner rather than a real
    channel cell — flow always continues through the higher-accumulation
    neighbour, so the network stays connected end to end. Deterministic:
    candidates are processed in ascending (accum, y, x) order.
    """
    ch = channel.copy()
    h, w = ch.shape

    def blocks(mask):
        b = np.roll(mask, -1, axis=1) if wrap_x else np.pad(mask[:, 1:], ((0, 0), (0, 1)))
        return mask[:-1, :] & mask[1:, :] & b[:-1, :] & b[1:, :]

    for _ in range(8):  # a handful of passes converges; bounded for safety
        blk = blocks(ch)
        if not blk.any():
            break
        ys, xs = np.nonzero(blk)
        # For each 2x2, drop its lowest-accumulation member.
        cand: list[tuple[int, int, int]] = []
        for y, x in zip(ys.tolist(), xs.tolist()):
            x1 = (x + 1) % w if wrap_x else min(x + 1, w - 1)
            members = ((y, x), (y + 1, x), (y, x1), (y + 1, x1))
            my, mx = min(members, key=lambda p: (int(accum[p]), p[0], p[1]))
            cand.append((int(accum[my, mx]), my, mx))
        for _a, my, mx in sorted(cand):
            if ch[my, mx]:
                ch[my, mx] = False
    return ch


def headwaters(channel: np.ndarray, direction: np.ndarray, wrap_x: bool = True) -> np.ndarray:
    """Channel cells with no channel cell draining into them — the branch tips.

    Computed from the flow directions rather than from the mask's shape, which is
    what makes it exact: a cell is a headwater precisely when nothing upstream of
    it is also a channel. Shape-based tests (counting neighbours) get confused by
    the diagonal staircases a thinned raster contains.
    """
    h, w = channel.shape
    has_inflow = np.zeros((h, w), dtype=bool)
    ys, xs = np.nonzero(channel)
    for y, x in zip(ys.tolist(), xs.tolist()):
        ds = _downstream(y, x, direction, w, wrap_x)
        if ds is None:
            continue
        ny, nx = ds
        if 0 <= ny < h and channel[ny, nx]:
            has_inflow[ny, nx] = True
    return channel & ~has_inflow


@dataclass(frozen=True)
class Segment:
    """A river channel between two network nodes, source-first.

    ``mouth`` is ``"sea"`` (drains off the coast) or ``"confluence"`` (ends where
    it joins a larger channel). ``accum`` is the flow at its downstream end, used
    to pick a render width.
    """

    points: list[tuple[int, int]]  # (x, y), source-first
    mouth: str
    accum: int


def extract_segments(direction: np.ndarray, accum: np.ndarray, land: np.ndarray,
                     threshold: int, wrap_x: bool = True) -> list[Segment]:
    """Decompose the channel network (accum >= threshold) into source-first segments.

    Nodes are sources (no channel drains in), junctions (>= 2 channels drain in),
    and coastal outlets. A segment runs from a source or a junction downstream to
    the next junction (``confluence``) or the sea (``sea``). Deterministic: cells
    are visited in sorted order and the offsets are fixed.
    """
    h, w = direction.shape
    channel = (accum >= threshold) & land

    # Count how many channel cells drain into each channel cell.
    indeg = np.zeros((h, w), dtype=np.int32)
    ys, xs = np.nonzero(channel)
    for y, x in zip(ys.tolist(), xs.tolist()):
        ds = _downstream(y, x, direction, w, wrap_x)
        if ds is not None and 0 <= ds[0] < h and channel[ds[0], ds[1]]:
            indeg[ds[0], ds[1]] += 1

    is_junction = channel & (indeg >= 2)
    is_source = channel & (indeg == 0)

    # Segment heads: sources, and the cell just downstream of each junction.
    heads: list[tuple[int, int]] = []
    for y, x in zip(*[a.tolist() for a in np.nonzero(is_source)]):
        heads.append((y, x))
    for y, x in zip(*[a.tolist() for a in np.nonzero(is_junction)]):
        ds = _downstream(y, x, direction, w, wrap_x)
        if ds is not None and 0 <= ds[0] < h and channel[ds[0], ds[1]]:
            heads.append(ds)
    heads = sorted(set(heads))

    segments: list[Segment] = []
    for (hy, hx) in heads:
        pts = [(hx, hy)]
        y, x = hy, hx
        guard = 0
        mouth = "sea"
        while True:
            guard += 1
            if guard > h * w:
                break  # cycle guard (should not happen after depression fill)
            ds = _downstream(y, x, direction, w, wrap_x)
            if ds is None or not (0 <= ds[0] < h) or not channel[ds[0], ds[1]]:
                mouth = "sea"
                break
            ny, nx = ds
            pts.append((nx, ny))
            if is_junction[ny, nx]:
                mouth = "confluence"
                break
            y, x = ny, nx
        if len(pts) >= 2:
            segments.append(Segment(points=pts, mouth=mouth, accum=int(accum[pts[-1][1], pts[-1][0]])))
    return segments
