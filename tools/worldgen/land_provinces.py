"""Land provinces from the user's hand-drawn state-region boundary network.

Board #2773 (the land mirror of :mod:`worldgen.sea_zones`, decoupled from the
land cut / ``state_labels.png`` pipeline). Reads the committed land/sea mask and
the hand-drawn state-region source, and turns them into a land province label
layer that :mod:`generate_provinces` folds together with the committed sea zones.

The user drew the state-region boundaries by hand as a **magenta (255,0,255)**
line network on the canvas-space reprojected globe
(``sources/terraqueous_globe_reprojected - state_regions.png``), the same idiom
as the coastline trace and the sea-zone network. In the Vic3 hierarchy those
magenta lines are **state_region** boundaries (the ~677 cells they flood-fill to
≈ the 600–700 state-region target); this module cuts the **provinces beneath
them** — thousands of them — with the rule that no province may cross a magenta
line.

Two stages, both pure functions of the committed mask + the drawn source + the
knobs (no RNG), so a re-run reproduces byte-identical labels — the determinism
core.md requires of a multiplayer-synchronized mod:

1. :func:`regions` — flood-fill the land between the magenta lines into
   barrier-respecting **regions** (state_region cells), exactly as
   :func:`worldgen.sea_zones.extract` flood-fills water between the purple lines,
   plus a :func:`worldgen.cells.split_disconnected` repair (the nearest-label
   fill tears cells; without the split a torn region ships as two disconnected
   pieces sharing one label).
2. :func:`subdivide` — cut each **drawn** region into provinces to hit a target
   count, by deterministic farthest-point seeding + a nearest-seed fill *within
   that region* (so no province crosses a magenta line), mirroring
   :func:`worldgen.cells.sea_zones`. A region that belongs to an out-of-scope
   placeholder continent (no interior magenta, so one region already) is kept
   whole — one province.

:func:`drawn_mask` is what separates the two: it classifies each **landmass**
(a connected component of land) as *drawn* (the Old World, dense with interior
magenta) or *placeholder* (a far continent with none), by interior-magenta
density. The separation is stark — the drawn Old World carries ~115k px of
interior magenta against ≤1,554 for every other landmass — so any floor in
[2k, 100k] works; the default sits at 5,000.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from worldgen import cells

#: The user's STATE-REGION boundary colour (magenta 255,0,255), tolerant of
#: anti-aliasing. Disjoint from the sea-zone purple band
#: (:data:`worldgen.sea_zones._PURPLE_RED` = (60, 195)): magenta's red channel is
#: pinned high, purple's is mid — 0 overlapping px in the real source.
_MAGENTA = {"r": 195, "g": 80, "b": 190}

#: A magenta pixel counts toward the drawn zone only if it sits at least this many
#: px from any coast — the drawn source paints the *coastline* magenta too, and
#: only genuine interior state borders should mark where the user drew regions.
#: Without this the whole coast reads as "drawn" and every continent qualifies.
_INTERIOR_COAST_DIST = 8

#: How far the interior-magenta network reaches to define the hand-drawn zone: the
#: interior magenta is dilated by this many px into a blob covering the Old World
#: (where the user drew state borders), and a region is subdivided only if the
#: majority of it falls inside that blob. Large enough to bridge across a single
#: state region's magenta-sparse interior so the Old World reads as one contiguous
#: drawn zone, small enough not to engulf the magenta-free far continents even
#: where they are land-connected to it. The far continents (Cathay, the eastern
#: steppes, the Southlands, …) share the Old World's landmass but carry no drawn
#: borders, so a per-landmass test cannot separate them — this density blob can:
#: measured, the 4.9M/2.7M/1.25M px far-continent blobs score ≤0.34 drawn-overlap
#: while Old World regions score ≥0.79.
_DRAWN_REACH = 150


def magenta_lines(rgb: np.ndarray) -> np.ndarray:
    """The hand-drawn state-region boundary line (magenta 255,0,255), tolerant of
    anti-aliasing."""
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    return (r > _MAGENTA["r"]) & (g < _MAGENTA["g"]) & (b > _MAGENTA["b"])


def regions(land: np.ndarray, drawn: np.ndarray, dilate: int = 2,
            merge_floor: int = 1200, wrap_x: bool = True, log=None) -> np.ndarray:
    """State-region labels (0 on water, ``1..n`` per region) from the drawn network.

    ``land`` is the boolean land mask; ``drawn`` is the RGB state-region source.
    The land mirror of :func:`worldgen.sea_zones.extract`: flood-fill the land
    minus the in-land magenta barrier into connected regions, give each barrier
    pixel the nearest region's label (crisp 1-px boundaries), **split any region
    the fill tore into disconnected pieces**, then merge sub-floor offcuts.
    """
    mag = magenta_lines(drawn)
    if dilate:
        mag = ndimage.binary_dilation(mag, iterations=dilate)
    barrier = mag & land
    if log:
        log(f"  magenta line {int(magenta_lines(drawn).sum()):,} px, "
            f"in-land barrier {int(barrier.sum()):,} px")

    # Connected components of the land minus the in-land barrier (wrap-aware).
    free = land & ~barrier
    comp = cells.components(free.astype(np.int32), wrap_x)
    reg = cells.renumber(np.where(free, comp, 0))
    if log:
        log(f"  {int(reg.max())} raw regions between the lines")

    # Crisp 1-px boundaries: each barrier pixel takes the nearest region's label.
    reg = cells.fill_nearest(reg, land, wrap_x)
    # The nearest-label fill measures Euclidean distance, which does not know
    # about the barrier: it can hand a barrier pixel to a region on the far side
    # of a thin isthmus, tearing that region into two disconnected pieces sharing
    # one label. Splitting the pieces apart is the fix (a region in two parts is
    # not a state region); the merge then swallows any sub-floor offcut.
    reg = cells.split_disconnected(reg, wrap_x)
    reg = cells.merge_small(reg, merge_floor, wrap_x)
    reg = cells.renumber(reg)
    if int((reg == 0).sum()) != int((~land).sum()):
        raise cells.CellError(
            "region layer does not tile the land exactly: "
            f"{int((reg == 0).sum()):,} unlabelled px vs {int((~land).sum()):,} water px"
        )
    if log:
        log(f"  {int(reg.max())} state regions")
    return reg


def drawn_mask(land: np.ndarray, mag: np.ndarray, wrap_x: bool = True,
               interior_dist: int = _INTERIOR_COAST_DIST,
               reach: int = _DRAWN_REACH, log=None) -> np.ndarray:
    """Boolean canvas mask of the hand-drawn zone (near the interior magenta network).

    The drawn source paints the coastline magenta as well as the state borders, so
    "is there magenta near this land" is true everywhere — every continent's
    outline is magenta. What actually marks where the user drew *regions* is
    **interior** magenta (at least ``interior_dist`` px from any coast); dilating
    that by ``reach`` gives a blob over the Old World and nowhere else.
    :func:`subdivide` then subdivides a region only where the majority of it falls
    in this blob, so a far continent that shares the Old World's landmass but
    carries no interior magenta stays a single placeholder province. ``mag`` is the
    raw (undilated) magenta mask.
    """
    # Distance (in px) from every land pixel to the nearest non-land pixel.
    # Wrap-aware via an x-pad wide enough to reach across the seam: a full-width
    # pad is the most that can ever be needed and stays cheap at canvas size.
    if wrap_x:
        pad = land.shape[1]
        padded = np.concatenate([land[:, -pad:], land, land[:, :pad]], axis=1)
        dist = ndimage.distance_transform_edt(padded)[:, pad:-pad]
    else:
        dist = ndimage.distance_transform_edt(land)
    interior_mag = mag & land & (dist >= interior_dist)

    if wrap_x:
        pad = min(reach + 1, land.shape[1])
        padded = np.concatenate([interior_mag[:, -pad:], interior_mag, interior_mag[:, :pad]], axis=1)
        blob = ndimage.binary_dilation(padded, iterations=reach)[:, pad:-pad]
    else:
        blob = ndimage.binary_dilation(interior_mag, iterations=reach)
    out = blob & land
    if log:
        log(f"  interior magenta {int(interior_mag.sum()):,} px; drawn zone "
            f"{int(out.sum()):,} px ({100 * out.sum() / max(1, land.sum()):.0f}% of land, "
            f"reach {reach})")
    return out


def _subdivide_cell(mask: np.ndarray, k: int, min_area: int, wrap_x: bool) -> np.ndarray:
    """Cut one region ``mask`` into pieces, returning a canvas-shaped int array
    with contiguous labels ``1..m`` (``m <= k``) on the region and 0 elsewhere.

    Farthest-point seeds (deterministic, no RNG) + a nearest-seed assignment done
    in the region's own bounding box — memory-linear (one distance transform over
    the box), unlike :func:`worldgen.cells.split_large`'s pixels×seeds array,
    which OOMs on a canvas-scale region. A region that wraps the seam is rolled
    into the middle of the canvas first, so "nearest" means nearest the short way
    round, exactly as ``split_large`` handles it.

    **All connectivity repair and sub-floor merging happens here, inside the box,
    where every labelled pixel belongs to this one region** — so a province can
    never merge into a neighbour across the magenta boundary. The box holds only
    this region's pixels (``local`` is the region's boolean mask), so
    ``merge_small`` only ever joins two pieces of the same region; the surrounding
    0s are background it cannot merge into.
    """
    m = mask
    shift = 0
    if wrap_x:
        cols = np.flatnonzero(m.any(axis=0))
        if cols.size and cols[0] == 0 and cols[-1] == m.shape[1] - 1 and len(cols) < m.shape[1]:
            gap = np.flatnonzero(np.diff(cols) > 1)
            if gap.size:
                shift = m.shape[1] - int(cols[gap[0] + 1])
                m = np.roll(m, shift, axis=1)
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    local = m[y0:y1, x0:x1]
    pix = np.column_stack(np.nonzero(local))
    seeds = cells._farthest_seeds(pix, k)
    seed_img = np.zeros(local.shape, dtype=np.int32)
    seed_img[tuple(seeds.T)] = np.arange(1, len(seeds) + 1, dtype=np.int32)
    # Nearest labelled seed for every region pixel — one EDT over the box.
    filled = cells.fill_nearest(seed_img, local, wrap_x=False)
    # Local cleanup, all within this region: split any Voronoi piece the region's
    # concavity tore, then swallow sub-floor slivers into a same-region neighbour.
    filled = np.where(local, filled, 0)
    filled = cells.split_disconnected(filled, wrap_x=False)
    filled = cells.merge_small(filled, min_area, wrap_x=False)
    filled = cells.renumber(filled)
    patch = np.zeros_like(m, dtype=np.int32)
    patch[y0:y1, x0:x1] = filled
    if shift:
        patch = np.roll(patch, -shift, axis=1)
    out = np.zeros(mask.shape, dtype=np.int32)
    out[patch > 0] = patch[patch > 0]
    return out


def subdivide(reg: np.ndarray, land: np.ndarray, drawn: np.ndarray, target: int,
              wrap_x: bool = True, min_area: int = 400, log=None
              ) -> tuple[np.ndarray, np.ndarray]:
    """Cut the drawn regions into provinces to reach ``target`` land provinces.

    ``reg`` is the state-region layer from :func:`regions` (``1..R``, 0 on water);
    ``drawn`` is the :func:`drawn_mask` of the hand-drawn land. Every province
    stays within one region (no magenta line is crossed), so seats are shared out
    among the **drawn** regions only, proportional to area under the
    largest-remainder rule with each drawn region guaranteed at least one. A
    placeholder region (outside ``drawn``) is kept whole — one province.

    Returns ``(labels, is_placeholder)``: the province label layer (``1..N``, 0 on
    water) and a boolean table indexed by label, ``True`` for an **out-of-scope
    placeholder** province (a far continent outside the drawn Old World, which the
    generator marks impassable). After the per-region cut,
    :func:`worldgen.cells.split_disconnected` repairs any seam a fill tore,
    sub-floor offcuts merge into a neighbour, and the labels renumber to ``1..N``.
    """
    n = int(reg.max())
    areas = np.bincount(reg.ravel(), minlength=n + 1)
    drawn_area = np.bincount(reg[drawn & land].ravel(), minlength=n + 1)
    # A region is "drawn" (to be subdivided) when the majority of its pixels fall
    # on the drawn landmass mask. Regions nest inside a landmass (a magenta
    # barrier cannot cross water), so this is unambiguous.
    is_drawn = np.zeros(n + 1, dtype=bool)
    is_drawn[1:] = drawn_area[1:] * 2 > areas[1:]
    drawn_ids = [i for i in range(1, n + 1) if is_drawn[i] and areas[i] > 0]
    drawn_areas = np.array([areas[i] for i in drawn_ids], dtype=np.float64)

    # Largest-remainder seat allocation across the drawn regions: one each, then
    # the remaining seats by area share, so the totals add up exactly.
    seats = np.ones(len(drawn_ids), dtype=int)
    spare = max(0, target - len(drawn_ids))
    if spare and drawn_areas.sum() > 0:
        quota = drawn_areas / drawn_areas.sum() * spare
        base = np.floor(quota).astype(int)
        rem = spare - int(base.sum())
        order = np.argsort(-(quota - base), kind="stable")
        base[order[:rem]] += 1
        seats += base
    seat_by_id = dict(zip(drawn_ids, seats.tolist()))
    if log:
        log(f"  {len(drawn_ids)} drawn regions, {n - len(drawn_ids)} placeholder; "
            f"target {target} -> {int(seats.sum())} seats "
            f"(min {int(seats.min())} / max {int(seats.max())} per region)")

    # Every region starts as one province (placeholder regions and any drawn
    # region that draws a single seat keep their region label); drawn regions with
    # >1 seat are re-cut in place. All connectivity/sliver cleanup happens inside
    # _subdivide_cell, per region, so nothing here can cross a magenta boundary.
    out = np.where(land, reg, 0).astype(np.int32)
    nxt = n + 1
    for i in drawn_ids:
        k = seat_by_id[i]
        if k <= 1:
            continue
        m = reg == i
        pieces = _subdivide_cell(m, k, min_area, wrap_x)  # labels 1..p on the region
        p = int(pieces.max())
        # Piece 1 keeps the region's own label i; pieces 2..p get fresh labels.
        ids = np.zeros(p + 1, dtype=np.int32)
        ids[1] = i
        for j in range(2, p + 1):
            ids[j] = nxt
            nxt += 1
        out[m] = ids[pieces[m]]

    out = cells.renumber(out)
    if int((out == 0).sum()) != int((~land).sum()):
        raise cells.CellError(
            "province layer does not tile the land exactly: "
            f"{int((out == 0).sum()):,} unlabelled px vs {int((~land).sum()):,} water px"
        )

    # Flag every province whose region was not drawn (a far-continent placeholder)
    # as out-of-scope. Each province lies in one region, so its region is constant
    # over its pixels; the generator marks these impassable.
    reg_of = np.zeros(int(out.max()) + 1, dtype=reg.dtype)
    reg_of[out.ravel()] = reg.ravel()
    is_placeholder = ~is_drawn[reg_of]
    is_placeholder[0] = False
    if log:
        log(f"  {int(out.max())} land provinces "
            f"({int(is_placeholder[1:].sum())} out-of-scope placeholders)")
    return out, is_placeholder
