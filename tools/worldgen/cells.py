"""Turn traced boundary networks into a label layer that tiles the committed mask.

The engine invariant this whole module exists to satisfy is simple and absolute:
**every land pixel belongs to exactly one state**. The reference maps cannot
supply that on their own — they are rubber-sheeted illustrations whose cells
overlap, leave gaps, and stop entirely around Cathay — so the source networks are
treated as *hints about where borders go*, and this module is what turns hints
into a partition.

The order is deliberate:

1. **Warp** each source's cell labels onto the canvas at nearest-neighbour, never
   interpolated — an interpolated label is a label that appears nowhere in the
   source.
2. **Intersect with the committed mask.** The mask is the coastline authority
   (user decision #1); a source cell that spills into the sea is clipped, and a
   source that puts sea where the mask has land contributes nothing there.
3. **Fill the remainder by nearest label**, then seed fresh cells wherever no
   source reaches at all — roughly 40% of the world's land (Ind, Khuresh,
   Nippon, the far Eastern Steppes, the polar Wastes) has no boundary source and
   always will need this.
4. **Repair connectivity**, because a rubber-sheet can tear one source cell into
   two pieces on opposite sides of a strait, and a state made of two islands is
   not a state.
5. **Reconcile density** — merge below target, split above — so the join between
   a dense source, a sparse source and the fallback is not visible as a change in
   granularity.

Every step is wrap-aware on x: the canvas is periodic in longitude, so a cell
crossing the seam is one cell.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage import measure

from worldgen import raster, reproject, schema


class CellError(RuntimeError):
    """The label layer cannot be built as declared."""


# ---------------------------------------------------------------------------
# Wrap-aware connected components of a label image
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = np.arange(n, dtype=np.int64)

    def find(self, a: int) -> int:
        p = self.parent
        while p[a] != a:
            p[a] = p[p[a]]
            a = p[a]
        return int(a)

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def components(labels: np.ndarray, wrap_x: bool = True) -> np.ndarray:
    """Connected components of equal-valued regions, 4-connected, wrap-aware.

    ``skimage.measure.label`` already splits an image of labels into
    same-value connected regions, which is exactly what is needed to catch a
    single source cell that the warp tore into two pieces. It has no periodic
    mode, so the seam is stitched afterwards: under 4-connectivity the only
    cross-seam adjacencies are ``(y, 0)`` next to ``(y, W-1)``, so one pass down
    that column pair and a union-find is both sufficient and exact — far cheaper
    than doubling a 30-megapixel array.

    Label 0 is treated as a value like any other, so callers that use 0 for
    "unassigned" should mask it out afterwards.
    """
    comp = measure.label(labels, connectivity=1, background=None).astype(np.int64)
    if not wrap_x:
        return comp
    left, right = labels[:, 0], labels[:, -1]
    same = np.flatnonzero(left == right)
    if same.size:
        uf = _UnionFind(int(comp.max()) + 1)
        cl, cr = comp[same, 0], comp[same, -1]
        for a, b in zip(cl.tolist(), cr.tolist()):
            uf.union(a, b)
        remap = np.array([uf.find(i) for i in range(int(comp.max()) + 1)], dtype=np.int64)
        comp = remap[comp]
    return renumber(comp)


def renumber(labels: np.ndarray) -> np.ndarray:
    """Compact label values to ``0..k`` preserving 0, deterministically by value."""
    uniq, inv = np.unique(labels, return_inverse=True)
    out = inv.reshape(labels.shape).astype(np.int32)
    if uniq[0] == 0:
        return out
    return out + 1


# ---------------------------------------------------------------------------
# Wrap-aware nearest-label fill
# ---------------------------------------------------------------------------

def _pad_x(a: np.ndarray, pad: int) -> np.ndarray:
    return np.concatenate([a[:, -pad:], a, a[:, :pad]], axis=1) if pad else a


def _unpad_x(a: np.ndarray, pad: int) -> np.ndarray:
    return a[:, pad:-pad] if pad else a


def fill_nearest(labels: np.ndarray, within: np.ndarray, wrap_x: bool = True,
                 pad: int = 512) -> np.ndarray:
    """Give every ``within`` pixel the label of the nearest already-labelled pixel.

    One Euclidean distance transform with ``return_indices`` answers "where is the
    closest labelled pixel" for the whole image at once, so the fill is a single
    gather. This is the mask-constrained watershed the plan calls for, in its
    cheapest correct form: because the seeds are the source cells themselves and
    the metric is Euclidean, the result is exactly the Voronoi partition of the
    unlabelled area among the labelled cells.

    ``pad`` wraps enough columns for the seam to behave: a pixel near x=0 must be
    able to take a label from near x=W-1. It has to exceed the widest unlabelled
    gap that straddles the seam, not merely a pixel or two.
    """
    # A pad wider than the array itself would make _unpad_x slice past the end;
    # a full-width wrap is the most that can ever be needed anyway.
    pad = min(int(pad), labels.shape[1])
    lab = _pad_x(labels, pad) if wrap_x else labels
    need = (_pad_x(within, pad) if wrap_x else within) & (lab == 0)
    if not need.any():
        return labels
    src = lab != 0
    if not src.any():
        raise CellError("fill_nearest: nothing is labelled, so there is nothing to grow from")
    idx = ndimage.distance_transform_edt(~src, return_distances=False, return_indices=True)
    out = lab.copy()
    out[need] = lab[tuple(idx)][need]
    return _unpad_x(out, pad) if wrap_x else out


# ---------------------------------------------------------------------------
# Source cell layers
# ---------------------------------------------------------------------------

def warp_cells(reg: schema.SourceRegistration,
               regs_by_source: dict[str, schema.SourceRegistration],
               src_labels: np.ndarray, shape: tuple[int, int],
               block_rows: int = 256,
               canvas_shape: tuple[int, int] | None = None
               ) -> tuple[np.ndarray, np.ndarray]:
    """Warp a source's cell labels onto the canvas. Returns ``(labels, inside)``.

    Blocked by canvas rows so the coordinate grids stay bounded: at 8192 columns
    a full-canvas float64 coordinate pair is half a gigabyte, and the thin-plate
    evaluation needs both at once.

    ``canvas_shape`` is the coordinate system the *registration* is expressed in,
    which need not be the grid being filled — the same split
    ``reproject.source_coords_warp`` makes. It lets the boundary fixture run this
    exact function on a 256 px canvas while its committed record still states
    control points in real canvas pixels, so ``sources.verify`` can bounds-check
    them the same way it checks every other record.
    """
    h, w = shape
    ch, cw = canvas_shape if canvas_shape is not None else shape
    sxc, syc = cw / w, ch / h
    fit = reproject.fit_placement(reg, regs_by_source)
    if not hasattr(fit, "to_source_px"):
        raise CellError(f"{reg.source}: cell warping needs a warp/alias placement")
    out = np.zeros(shape, dtype=src_labels.dtype)
    inside = np.zeros(shape, dtype=bool)
    ih, iw = src_labels.shape
    x0, y0, x1, y1 = reg.crop if reg.crop is not None else (0, 0, iw, ih)
    xs = (np.arange(w, dtype=np.float64) + 0.5) * sxc
    for r0 in range(0, h, block_rows):
        r1 = min(h, r0 + block_rows)
        gy = np.broadcast_to(((np.arange(r0, r1, dtype=np.float64) + 0.5) * syc)[:, None],
                             (r1 - r0, w))
        gx = np.broadcast_to(xs[None, :], (r1 - r0, w))
        sx, sy = fit.to_source_px(gx, gy)
        # `inside` is *coverage* — where this source has anything to say at all,
        # including its own ink lines. It is deliberately not "where this source
        # has a cell": stack_layers needs to suppress lower layers across the ink
        # too, or the layer underneath shows through every boundary line.
        covers = (sx >= x0) & (sx <= x1) & (sy >= y0) & (sy <= y1)
        inside[r0:r1] = covers
        if not covers.any():
            continue
        ix = np.rint(sx).astype(np.int64).clip(0, iw - 1)
        iy = np.rint(sy).astype(np.int64).clip(0, ih - 1)
        blk = src_labels[iy, ix]
        take = covers & (blk != 0)
        out[r0:r1][take] = blk[take]
    return out, inside


def stack_layers(layers: list[tuple[str, int, np.ndarray, np.ndarray]],
                 shape: tuple[int, int]) -> np.ndarray:
    """Merge per-source cell layers by precedence, never blending.

    Layers are painted low precedence first, so a higher-precedence source
    overwrites inside its own **coverage** and leaves the rest alone — the same
    rule ``composite.Mosaic`` applies to the heightmap. Label values are offset
    per layer so two sources' cell #7 can never collide.

    *Coverage*, not "wherever this layer has a label", is the load-bearing
    distinction and it was learned the hard way. Painting only where the top
    layer has a cell lets the layer underneath show through the top layer's **ink
    lines** — and since both sources draw the same continents with slightly
    different borders, the result is not a map with better borders but a fine
    mesh of ribbons where the two networks cross. Measured: 1112 + 1143 source
    cells came out as 40,129 slivers. Suppressing the lower layer across the
    higher one's whole footprint leaves the ink as unlabelled gaps, which
    :func:`fill_nearest` then closes into the cells either side, as intended.

    A precedence tie is rejected: the winner would depend on the order the
    records happened to be loaded in.
    """
    seen: dict[int, str] = {}
    for name, prec, _, _ in layers:
        if prec in seen:
            raise CellError(
                f"{name} and {seen[prec]} both claim boundary precedence {prec} — "
                f"the winner would depend on load order"
            )
        seen[prec] = name
    out = np.zeros(shape, dtype=np.int32)
    offset = 0
    for name, _prec, lab, covers in sorted(layers, key=lambda t: t[1]):
        out[covers] = 0
        take = covers & (lab != 0)
        out[take] = lab[take].astype(np.int32) + offset
        offset += int(lab.max()) + 1
    return out


# ---------------------------------------------------------------------------
# Density reconciliation
# ---------------------------------------------------------------------------

def _neighbour_pairs(labels: np.ndarray, wrap_x: bool = True) -> dict[int, dict[int, int]]:
    """Shared-border length between every pair of adjacent labels (4-connected)."""
    pairs: dict[int, dict[int, int]] = {}

    def add(a: np.ndarray, b: np.ndarray) -> None:
        m = (a != b) & (a != 0) & (b != 0)
        if not m.any():
            return
        key = a[m].astype(np.int64) * (int(labels.max()) + 1) + b[m].astype(np.int64)
        vals, counts = np.unique(key, return_counts=True)
        k = int(labels.max()) + 1
        for v, c in zip(vals.tolist(), counts.tolist()):
            u, w_ = divmod(v, k)
            pairs.setdefault(u, {})[w_] = pairs.setdefault(u, {}).get(w_, 0) + c
            pairs.setdefault(w_, {})[u] = pairs.setdefault(w_, {}).get(u, 0) + c

    add(labels[:, :-1], labels[:, 1:])
    add(labels[:-1, :], labels[1:, :])
    if wrap_x:
        add(labels[:, -1:], labels[:, :1])
    return pairs


def merge_small(labels: np.ndarray, min_area: int, wrap_x: bool = True,
                rounds: int = 12) -> np.ndarray:
    """Merge cells below ``min_area`` into the neighbour they share most border with.

    Ties break on the lower label id, so the result does not depend on dictionary
    ordering. Repeats until stable, because merging two small cells can still
    leave one under the threshold.
    """
    lab = labels.copy()
    for _ in range(rounds):
        areas = np.bincount(lab.ravel())
        small = [i for i in range(1, len(areas)) if 0 < areas[i] < min_area]
        if not small:
            break
        pairs = _neighbour_pairs(lab, wrap_x)
        remap = np.arange(len(areas), dtype=np.int32)
        for i in sorted(small, key=lambda j: (areas[j], j)):
            nb = pairs.get(i)
            if not nb:
                continue
            cand = [(j, n) for j, n in nb.items() if j != 0 and remap[j] != i]
            if not cand:
                continue
            remap[i] = min(cand, key=lambda t: (-t[1], t[0]))[0]
        # Collapse chains so a -> b -> c lands on c in one pass.
        for _ in range(8):
            nxt = remap[remap]
            if np.array_equal(nxt, remap):
                break
            remap = nxt
        if np.array_equal(remap, np.arange(len(areas))):
            break
        lab = remap[lab]
    return renumber(lab)


def drop_small(labels: np.ndarray, min_area: int) -> np.ndarray:
    """Unlabel cells below ``min_area`` instead of merging them.

    Dropping and re-filling is not the same as merging, and the difference is
    visible in the finished map. Our coastline is not the source's, so clipping
    the source cells to the committed mask shaves a sliver off every coastal one.
    Merged, those slivers join to whichever neighbour they share most border with
    — which for a sliver is usually *another sliver*, and the chain comes out as a
    long ribbon state hugging the coast. Dropped, the same pixels go back to
    :func:`fill_nearest`, which hands each one to its genuinely nearest cell and
    produces compact shapes.

    Runs on the labels as given: callers should have split disconnected pieces
    first, or a cell's total area will hide a sliver limb.
    """
    areas = np.bincount(labels.ravel())
    small = np.zeros(len(areas), dtype=bool)
    small[1:] = areas[1:] < int(min_area)
    small[0] = False
    out = labels.copy()
    out[small[labels]] = 0
    return out


def merge_to_target(labels: np.ndarray, target: int, wrap_x: bool = True,
                    tolerance: float = 0.03, rounds: int = 8, log=None) -> np.ndarray:
    """Merge upward until the cell count is near ``target``.

    A fixed minimum area cannot hit a cell *count*: how many cells a threshold
    removes depends on the area distribution, which changes as soon as the first
    merge lands. So the threshold is re-derived each round from the distribution
    itself — "merge everything below the (n - target)-th smallest area" is an
    exact answer if every merge removed exactly one cell, and a good enough
    estimate given they do not, which is why it iterates.

    Overshooting is avoided by construction: the threshold never rises above the
    area of the cell that *would* be the target-th largest, so a round can only
    take the count down towards the target, never past it in one step.
    """
    lab = labels
    for r in range(rounds):
        areas = np.bincount(lab.ravel())
        live = np.flatnonzero(areas[1:]) + 1
        n = len(live)
        if n <= target * (1 + tolerance):
            break
        order = np.sort(areas[live])
        cut = int(order[min(n - 1, n - target)])
        lab = split_disconnected(merge_small(lab, cut, wrap_x, rounds=3), wrap_x)
        if log:
            log(f"    round {r + 1}: {n} -> {int(lab.max())} cells (merged below {cut:,} px)")
    return lab


def _farthest_seeds(pixels: np.ndarray, k: int) -> np.ndarray:
    """``k`` well-spread pixels from an ``(N, 2)`` array, deterministically.

    Farthest-point sampling from the first pixel in raster order: no RNG, no
    dependence on the committed SEED, and the same cell always yields the same
    seeds. k-means would be better spread but iterates to a floating-point
    tolerance, which is exactly the kind of near-tie a byte-exact pipeline should
    not build on.
    """
    chosen = [0]
    if k <= 1:
        return pixels[chosen]
    d = ((pixels - pixels[0]) ** 2).sum(axis=1).astype(np.float64)
    for _ in range(k - 1):
        i = int(np.argmax(d))
        chosen.append(i)
        d = np.minimum(d, ((pixels - pixels[i]) ** 2).sum(axis=1))
    return pixels[chosen]


def split_large(labels: np.ndarray, max_area: int, target_area: int,
                wrap_x: bool = True) -> np.ndarray:
    """Subdivide cells above ``max_area`` into pieces of about ``target_area``.

    Splitting is done inside the cell's own bounding box with a direct
    nearest-seed assignment. Cells needing a split are by definition large but
    still small next to the canvas, so this stays local; doing it globally would
    mean a distance transform over 30 megapixels per cell.

    A cell that wraps the seam is handled by rolling its bounding box into the
    middle of the canvas first, so "nearest" means nearest the short way round.
    """
    lab = labels.copy()
    nxt = int(lab.max()) + 1
    areas = np.bincount(lab.ravel())
    for cid in range(1, len(areas)):
        if areas[cid] <= max_area:
            continue
        k = max(2, int(round(areas[cid] / target_area)))
        m = lab == cid
        shift = 0
        if wrap_x:
            cols = np.flatnonzero(m.any(axis=0))
            # Wrapping shows up as occupancy at both edges with a gap between.
            if cols[0] == 0 and cols[-1] == lab.shape[1] - 1 and len(cols) < lab.shape[1]:
                gap = np.flatnonzero(np.diff(cols) > 1)
                if gap.size:
                    shift = lab.shape[1] - int(cols[gap[0] + 1])
                    m = np.roll(m, shift, axis=1)
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        local = m[y0:y1, x0:x1]
        pix = np.column_stack(np.nonzero(local))
        seeds = _farthest_seeds(pix, k)
        d = ((pix[:, None, :] - seeds[None, :, :]) ** 2).sum(axis=2)
        owner = np.argmin(d, axis=1)
        new = np.zeros(local.shape, dtype=np.int32)
        ids = [cid] + [nxt + i for i in range(k - 1)]
        nxt += k - 1
        new[tuple(pix.T)] = np.array(ids, dtype=np.int32)[owner]
        patch = np.zeros_like(m, dtype=np.int32)
        patch[y0:y1, x0:x1] = new
        if shift:
            patch = np.roll(patch, -shift, axis=1)
            m = np.roll(m, -shift, axis=1)
        lab[m] = patch[m]
    return renumber(lab)


def split_disconnected(labels: np.ndarray, wrap_x: bool = True) -> np.ndarray:
    """Give every connected piece of a torn cell its own label."""
    comp = components(labels, wrap_x)
    comp[labels == 0] = 0
    return renumber(comp)


# ---------------------------------------------------------------------------
# Sea zones
# ---------------------------------------------------------------------------

def sea_zones(water: np.ndarray, count: int, wrap_x: bool = True) -> np.ndarray:
    """Partition water into about ``count`` zones, proportional to body area.

    Every water body gets at least one zone (the engine wants one province per
    sea state, and a lake that shares a zone with an ocean on the far side of a
    continent is not a sea zone anyone can sail). Seats beyond that are shared out
    by area under the largest-remainder rule, so the totals add up exactly instead
    of drifting by a few after rounding.
    """
    bodies = components(water.astype(np.int32), wrap_x)
    bodies[~water] = 0
    ids = [i for i in np.unique(bodies) if i != 0]
    if not ids:
        raise CellError("sea_zones: the mask has no water")
    areas = np.array([int((bodies == i).sum()) for i in ids], dtype=np.float64)
    seats = np.ones(len(ids), dtype=int)
    spare = max(0, count - len(ids))
    if spare:
        quota = areas / areas.sum() * spare
        base = np.floor(quota).astype(int)
        rem = spare - int(base.sum())
        order = np.argsort(-(quota - base), kind="stable")
        base[order[:rem]] += 1
        seats += base

    out = np.zeros(water.shape, dtype=np.int32)
    nxt = 1
    for i, k in zip(ids, seats.tolist()):
        m = bodies == i
        if k <= 1:
            out[m] = nxt
            nxt += 1
            continue
        pix = np.column_stack(np.nonzero(m))
        seeds = _farthest_seeds(pix, k)
        seed_img = np.zeros(water.shape, dtype=np.int32)
        seed_img[tuple(seeds.T)] = np.arange(nxt, nxt + k, dtype=np.int32)
        filled = fill_nearest(seed_img, m, wrap_x)
        out[m] = filled[m]
        nxt += k

    # The nearest-seed fill measures Euclidean distance, which does not know
    # about land: a zone in a bay can end up owning a patch of the same ocean on
    # the far side of a continent, and the engine wants one province per sea
    # state. Splitting the pieces apart is the fix; the pieces are then merged
    # back towards the seat count, which cannot re-create the problem because
    # merging only ever joins neighbours.
    out = split_disconnected(out, wrap_x)
    out = merge_to_target(out, count, wrap_x)
    return renumber(out)


# ---------------------------------------------------------------------------
# Committed IO
# ---------------------------------------------------------------------------

def coastal_labels(labels: np.ndarray, land: np.ndarray, wrap_x: bool = True) -> np.ndarray:
    """Boolean table, indexed by label, of which land cells touch water.

    4-connected, and wrap-aware on x only — the canvas is periodic in longitude
    but its top and bottom edges are the polar cut, not ocean, so a cell on the
    north edge is not coastal by virtue of the edge.

    Lives here rather than in the generator because three callers need the same
    answer: the generator writes it into the index, the boundary fixture writes
    it into its own, and S3b turns it into `port` + `naval_exit_id`, which the
    state schema requires to agree. ``validate_map`` deliberately does *not* use
    this function — it recomputes the same fact a different way, so the two can
    disagree and the check has something to catch.
    """
    sea = ~land
    nb = np.zeros_like(sea)
    if wrap_x:
        nb |= np.roll(sea, 1, axis=1)
        nb |= np.roll(sea, -1, axis=1)
    else:
        nb[:, 1:] |= sea[:, :-1]
        nb[:, :-1] |= sea[:, 1:]
    nb[:-1] |= sea[1:]
    nb[1:] |= sea[:-1]
    touching = np.unique(labels[nb & land])
    out = np.zeros(int(labels.max()) + 1, dtype=bool)
    out[touching[touching > 0]] = True
    return out


def write_labels(path, labels: np.ndarray) -> None:
    """Write the label layer as a lossless 16-bit grayscale PNG.

    Not a palette PNG: a palette holds 256 entries and this layer carries
    vanilla-order state counts (hundreds of land cells plus a hundred sea zones),
    so an indexed file could not represent it without silently colliding labels.
    16-bit grayscale is exactly lossless in the same way and round-trips through
    ``raster.read_gray16_png`` unchanged, which is the property that matters — a
    lossy re-save of a label raster invents states.
    """
    if labels.max() > 65535:
        raise CellError(f"label layer has {labels.max()} labels, over the 16-bit limit")
    raster.write_gray16_png(path, labels.astype(np.uint16))


def read_labels(path) -> np.ndarray:
    return raster.read_gray16_png(path).astype(np.int32)
