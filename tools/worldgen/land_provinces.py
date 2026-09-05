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
#: The 2026-08-31 state_regions.png re-export split this into two near-identical
#: shades — pure magenta (255,0,255) and a second (255,0,127) — an artifact of
#: how the coastline and interior-border GIMP layers flattened, not a meaningful
#: distinction (confirmed against the source: only these two colours occupy the
#: r>195,g<80 band, one drawing both coastline and interior borders together).
#: The blue floor is lowered to catch both.
_MAGENTA = {"r": 195, "g": 80, "b": 100}

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
            merge_floor: int = 1200, wrap_x: bool = True, log=None,
            island_overrides: np.ndarray | None = None) -> np.ndarray:
    """State-region labels (0 on water, ``1..n`` per region) from the drawn network.

    ``land`` is the boolean land mask; ``drawn`` is the RGB state-region source.
    The land mirror of :func:`worldgen.sea_zones.extract`: flood-fill the land
    minus the in-land magenta barrier into connected regions, give each barrier
    pixel the nearest region's label (crisp 1-px boundaries), **split any region
    the fill tore into disconnected pieces**, then merge sub-floor offcuts.

    ``island_overrides``, when given, is a canvas-shaped int array as returned by
    :func:`island_override_zones` — 0 where the user drew nothing, a distinct id
    per hand-drawn circle otherwise. Every region caught under the same circle is
    force-merged into one (see :func:`merge_island_overrides`) as the very last
    step, after the normal barrier/fill/merge machinery — the tiny-island fix for
    an archipelago that would otherwise ship as one micro state-region per islet.
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
    if island_overrides is not None and island_overrides.any():
        reg = merge_island_overrides(reg, land, island_overrides, wrap_x, log=log)
    if int((reg == 0).sum()) != int((~land).sum()):
        raise cells.CellError(
            "region layer does not tile the land exactly: "
            f"{int((reg == 0).sum()):,} unlabelled px vs {int((~land).sum()):,} water px"
        )
    if log:
        log(f"  {int(reg.max())} state regions")
    return reg


#: The user's island-override ring colour (pure red 255,0,0), tolerant of
#: anti-aliasing. Disjoint from the state-region magenta network (255,0,255):
#: this colour's blue channel is pinned low, magenta's is pinned high.
_ISLAND_MARK = {"r": 200, "g": 80, "b": 80}


def island_override_zones(rgb: np.ndarray, wrap_x: bool = True) -> np.ndarray:
    """Zone id per user-drawn island-override circle (0 = nothing drawn there).

    The source (``sources/terraqueous_globe_reprojected - tiny_islands_merger.png``,
    optional — see :func:`merge_island_overrides`) has the user draw a closed
    **ring** (pure red 255,0,0, tolerant of anti-aliasing) around each cluster of
    tiny islands that should be forced into a single province: a disconnected
    islet has no land neighbour to qualify for :func:`worldgen.cells.merge_small`'s
    share-a-border merge, so left alone every one of them ships as its own micro
    state-region forever. The ring never touches the islands it encloses, so its
    interior is filled (``scipy.ndimage.binary_fill_holes``) before labelling —
    the zone a ring marks is everything *inside* it, not the drawn line itself.
    Distinct rings become distinct connected components/zone ids once filled;
    two rings that touch or overlap simply become one zone, which is harmless —
    everything either one encloses still ends up merged together.
    """
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    ring = (r > _ISLAND_MARK["r"]) & (g < _ISLAND_MARK["g"]) & (b < _ISLAND_MARK["b"])
    if not ring.any():
        return np.zeros(rgb.shape[:2], dtype=np.int32)
    if wrap_x:
        pad = rgb.shape[1]
        padded = np.concatenate([ring[:, -pad:], ring, ring[:, :pad]], axis=1)
        filled = ndimage.binary_fill_holes(padded)[:, pad:-pad]
    else:
        filled = ndimage.binary_fill_holes(ring)
    comp = cells.components(filled.astype(np.int32), wrap_x)
    return cells.renumber(np.where(filled, comp, 0))


def merge_island_overrides(reg: np.ndarray, land: np.ndarray, overrides: np.ndarray,
                           wrap_x: bool = True, log=None) -> np.ndarray:
    """Force every region caught under the same override circle to merge into one.

    ``overrides`` is an :func:`island_override_zones` layer. For each zone, every
    region with at least one land pixel under it is unioned together (a circle
    touching only one region is a no-op). :func:`subdivide` never crosses a
    magenta boundary and only ever cuts a *connected* region (see its own
    connectivity guard), so a merged, non-contiguous archipelago always ships
    whole as a single province — exactly the override this exists for.
    """
    n = int(reg.max())
    parent = np.arange(n + 1)

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return int(a)

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    merged_any = False
    for z in range(1, int(overrides.max()) + 1):
        here = (overrides == z) & land
        if not here.any():
            continue
        ids = sorted(int(i) for i in np.unique(reg[here]) if i > 0)
        if len(ids) <= 1:
            continue
        for i in ids[1:]:
            union(ids[0], i)
        merged_any = True
        if log:
            log(f"  island override zone {z}: merging regions {ids} -> {find(ids[0])}")

    if not merged_any:
        return reg
    remap = np.array([find(i) for i in range(n + 1)], dtype=reg.dtype)
    return cells.renumber(remap[reg])


#: How far :func:`apply_land_region_merges` searches outward from an anchor
#: for a labelled (non-zero) region pixel, in case the exact stored pixel
#: rounds onto a barrier/off-region gap.
_MERGE_ANCHOR_SEARCH_RADIUS = 6


def _region_near(reg: np.ndarray, x: int, y: int, max_radius: int) -> int:
    """The region label at ``(x, y)``, or the nearest labelled pixel within
    ``max_radius`` (0 if none — the anchor missed land entirely)."""
    h, w = reg.shape
    for r in range(max_radius + 1):
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        sub = reg[y0:y1, x0:x1]
        nz = sub[sub > 0]
        if nz.size:
            return int(nz[0])
    return 0


def apply_land_region_merges(reg: np.ndarray, merges: list["schema.LandRegionMerge"],
                             log=None) -> np.ndarray:
    """Force-union the regions owning each merge pair's two anchors, directly.

    Resolves each anchor straight to a region label (:func:`_region_near`) and
    unions the two labels in one shared union-find pass — so a chain of pairs
    that shares an anchor (A merges into B, B merges into C) unions all three,
    which a "paint a zone per pair" scheme (this function's first cut) gets
    wrong whenever two pairs share the *exact* same anchor pixel: the second
    pair's marker silently overwrites the first's zone there, breaking the
    chain in two. Resolving to region labels up front sidesteps that
    entirely — there is no zone array for one stamp to clobber another's.
    """
    n = int(reg.max())
    parent = np.arange(n + 1)

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return int(a)

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    merged_any = False
    for m in merges:
        ax, ay = m.anchor_a
        bx, by = m.anchor_b
        ra = _region_near(reg, ax, ay, _MERGE_ANCHOR_SEARCH_RADIUS)
        rb = _region_near(reg, bx, by, _MERGE_ANCHOR_SEARCH_RADIUS)
        if ra <= 0 or rb <= 0:
            if log:
                log(f"  land region merge override skipped (anchor missed land): {m.note}")
            continue
        if find(ra) != find(rb):
            union(ra, rb)
            merged_any = True
            if log:
                log(f"  land region merge override: regions {ra},{rb} -> {find(ra)}  ({m.note})")

    if not merged_any:
        return reg
    remap = np.array([find(i) for i in range(n + 1)], dtype=reg.dtype)
    return cells.renumber(remap[reg])


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


def _is_connected(mask: np.ndarray, wrap_x: bool) -> bool:
    """Whether ``mask``'s True pixels form a single connected piece, wrap-aware.

    Cropped to the mask's own bounding box (cheap even at canvas scale) with the
    same seam-roll :func:`_subdivide_cell` uses, so a region straddling the
    antimeridian isn't mistaken for two pieces. :func:`subdivide` calls this
    before cutting a region into more than one seat: an island-override merge
    (:func:`merge_island_overrides`) can hand it a region that is legitimately
    several islands sharing one label, and farthest-point seeding across that
    disconnected mask would carve up an archipelago the user asked to stay whole.
    """
    m = mask
    if wrap_x:
        cols = np.flatnonzero(m.any(axis=0))
        if cols.size and cols[0] == 0 and cols[-1] == m.shape[1] - 1 and len(cols) < m.shape[1]:
            gap = np.flatnonzero(np.diff(cols) > 1)
            if gap.size:
                shift = m.shape[1] - int(cols[gap[0] + 1])
                m = np.roll(m, shift, axis=1)
    ys, xs = np.nonzero(m)
    if ys.size == 0:
        return True
    box = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    _, n = ndimage.label(box)
    return n <= 1


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
              ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cut the drawn regions into provinces to reach ``target`` land provinces.

    ``reg`` is the state-region layer from :func:`regions` (``1..R``, 0 on water);
    ``drawn`` is the :func:`drawn_mask` of the hand-drawn land. Every province
    stays within one region (no magenta line is crossed), so seats are shared out
    among the **drawn** regions only, proportional to area under the
    largest-remainder rule with each drawn region guaranteed at least one. A
    placeholder region (outside ``drawn``) is kept whole — one province.

    Returns ``(labels, is_placeholder, reg_of, is_archipelago)``:

    * ``labels`` — the province label layer (``1..N``, 0 on water).
    * ``is_placeholder`` — a boolean table indexed by label, ``True`` for an
      **out-of-scope placeholder** province (a far continent outside the drawn Old
      World, which the generator marks as a passable placeholder).
    * ``reg_of`` — a table indexed by province label (``reg_of[0] == 0`` for
      water), giving the ``1..R`` state-region id from ``reg`` that each province
      lies in. Each province lies wholly in one region, so this is well defined;
      :func:`generate_provinces` inverts it into the region → provinces grouping
      persisted as ``land_regions_index.json`` (the land mirror of
      ``sea_zones_index.json``). Province labels/colours are untouched by this
      return, so ``provinces.png`` stays byte-identical.
    * ``is_archipelago`` — a boolean table indexed by label, ``True`` for a
      province that is genuinely non-contiguous — several disconnected islands
      sharing one label, the deliberate outcome of an island-override merge
      (:func:`merge_island_overrides`) rather than a flood-fill bug. Vanilla
      ships exactly this shape (e.g. Micronesia's province colour spanning 23
      disconnected pixel blobs), so this is not itself invalid; it's the flag
      ``generate_provinces.py`` records so a validator can tell a deliberate
      archipelago apart from an accidentally torn province.

    After the per-region cut, :func:`worldgen.cells.split_disconnected` repairs any
    seam a fill tore, sub-floor offcuts merge into a neighbour, and the labels
    renumber to ``1..N``.
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
        if not _is_connected(m, wrap_x):
            # An island-override merge (merge_island_overrides) can hand this
            # region several disconnected islets sharing one label — an area
            # share large enough to earn >1 seat doesn't change that the user
            # asked for exactly one province here, so it stays whole.
            continue
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

    # Flag every genuinely non-contiguous province (an island-override merge
    # that was never cut, per the connectivity guard above) so a validator can
    # tell it apart from an accidentally torn one. One global connected-
    # components pass, exactly the check validate_map.py itself runs.
    comp = cells.components(out, wrap_x)
    pairs = np.unique(np.stack([out.ravel(), comp.ravel()], axis=1), axis=0)
    counts = np.bincount(pairs[:, 0].astype(np.int64), minlength=int(out.max()) + 1)
    is_archipelago = counts > 1
    is_archipelago[0] = False

    if log:
        log(f"  {int(out.max())} land provinces "
            f"({int(is_placeholder[1:].sum())} out-of-scope placeholders, "
            f"{int(is_archipelago.sum())} archipelagos)")
    return out, is_placeholder, reg_of, is_archipelago
