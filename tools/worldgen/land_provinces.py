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
    per hand-drawn merge-line network otherwise. Every region caught under the
    same network is force-merged into one (see :func:`merge_island_overrides`) as
    the very last step, after the normal barrier/fill/merge machinery — the
    tiny-island fix for an archipelago that would otherwise ship as one micro
    state-region per islet.
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


#: The user's island-override merge-line colour (pure red 255,0,0), tolerant
#: of anti-aliasing. Disjoint from the state-region magenta network
#: (255,0,255): this colour's blue channel is pinned low, magenta's is
#: pinned high.
_ISLAND_MARK = {"r": 200, "g": 80, "b": 80}


#: Dilation (px) applied to the drawn merge-line before flood-filling it
#: together with the land, so a line ending just short of an island's
#: coastline (a hand-drawn line rarely lands pixel-perfect on it) still
#: connects to it. Small relative to the gap between genuinely separate
#: island clusters, so it never bridges two clusters that were never
#: connected by a line at all.
_ISLAND_LINE_DILATE = 3


def island_override_zones(rgb: np.ndarray, land: np.ndarray, wrap_x: bool = True,
                          dilate: int = _ISLAND_LINE_DILATE) -> np.ndarray:
    """Zone id per merge-line network (0 = land untouched by any merge line).

    The source (``sources/terraqueous_globe_reprojected - tiny_islands_merger.png``,
    optional — see :func:`merge_island_overrides`) has the user draw a plain
    **line** (pure red 255,0,0, tolerant of anti-aliasing) directly connecting
    each cluster of tiny islands that should be forced into a single
    province: a disconnected islet has no land neighbour to qualify for
    :func:`worldgen.cells.merge_small`'s share-a-border merge, so left alone
    every one of them ships as its own micro state-region forever.

    This supersedes an earlier enclosing-**ring** idiom (board #4609): a ring
    needed a geometric splitter to tell two touching or overlapping rings
    apart, and neither a fixed-pixel-distance nor a saddle-prominence
    splitter could do that correctly for every ring shape (an elongated
    ring's own ridge and a genuinely separate small ring touching it can look
    identical from pixel geometry alone). A line makes the grouping explicit
    instead of inferred, and needs no splitter at all: flood-fill the
    (slightly dilated) line together with the land it touches, wrap-aware:
    every land pixel that ends up in the same connected component as a line
    pixel shares that line's zone id, and a component with no line pixel in
    it at all — the overwhelming majority of the map — gets zone 0, meaning
    "no forced merge here."
    """
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    line = (r > _ISLAND_MARK["r"]) & (g < _ISLAND_MARK["g"]) & (b < _ISLAND_MARK["b"])
    if not line.any():
        return np.zeros(rgb.shape[:2], dtype=np.int32)
    if dilate:
        line = ndimage.binary_dilation(line, iterations=dilate)
    network = (line | land).astype(np.int32)
    comp = cells.components(network, wrap_x)
    comp = np.where(network, comp, 0)
    touches_line = set(int(z) for z in np.unique(comp[line])) - {0}
    if not touches_line:
        return np.zeros(rgb.shape[:2], dtype=np.int32)
    zones = np.where(np.isin(comp, list(touches_line)), comp, 0)
    return cells.renumber(zones.astype(np.int32))


def merge_island_overrides(reg: np.ndarray, land: np.ndarray, overrides: np.ndarray,
                           wrap_x: bool = True, log=None) -> np.ndarray:
    """Force every region caught under the same override zone to merge into one.

    ``overrides`` is an :func:`island_override_zones` layer. For each zone, every
    region with at least one land pixel under it is unioned together (a network
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


def override_fused_labels(reg: np.ndarray, land: np.ndarray,
                          overrides: np.ndarray | None) -> set[int]:
    """Final region labels that carry land under any island-override circle.

    These are the archipelago-exempt labels :func:`subdivide` must keep whole: the
    same ``(overrides == z) & land`` predicate :func:`merge_island_overrides` used
    to fuse them, run once more against the **final** ``reg`` (post
    :func:`regions` + :func:`apply_land_region_merges`), so it is robust to both
    internal renumbers — both merge steps only *union* labels then
    :func:`worldgen.cells.renumber` (never split, never move geometry), so
    ``reg[(overrides == z) & land]`` yields the final fused label for circle ``z``
    directly.

    A label under a circle is returned even if it happens to be connected
    (harmless — :func:`subdivide` only consults this set in its disconnected
    branch); a disconnected label **not** in this set is a merge-fused region
    (:func:`apply_land_region_merges`), which :func:`subdivide` cuts per connected
    piece. ``overrides is None`` (no island-override source drawn) ⟹ empty set, so
    every disconnected drawn region is cut — correct, since the only other source
    of a disconnected label is a merge.
    """
    if overrides is None:
        return set()
    out: set[int] = set()
    for z in range(1, int(overrides.max()) + 1):
        here = (overrides == z) & land
        if here.any():
            out.update(int(i) for i in np.unique(reg[here]) if i > 0)
    return out


#: How far :func:`apply_land_region_merges` searches outward from an anchor
#: for a labelled (non-zero) region pixel, in case the exact stored pixel
#: rounds onto a barrier/off-region gap.
_MERGE_ANCHOR_SEARCH_RADIUS = 6


def resolve_anchor(reg: np.ndarray, x: int, y: int, max_radius: int
                   ) -> tuple[int, tuple[int, int]]:
    """The region label at ``(x, y)`` **and the pixel it was read from**, or the
    nearest labelled pixel within ``max_radius``. Returns ``(0, (x, y))`` if none —
    the anchor missed land entirely. The pixel-returning sibling of
    :func:`_region_near` (#3665): the hub seeding needs the exact resolved pixel,
    not just the label, so the same pixel can be handed to ``_subdivide_cell`` as a
    fixed Voronoi seed and later read back for the persisted hub→province index.

    The search order (expanding square, first non-zero in raster order within each
    ring) is identical to :func:`_region_near`, so the label returned here always
    matches what ``apply_land_region_merges`` resolves.
    """
    h, w = reg.shape
    for r in range(max_radius + 1):
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        sub = reg[y0:y1, x0:x1]
        ys, xs = np.nonzero(sub > 0)
        if ys.size:
            ry, rx = int(ys[0]) + y0, int(xs[0]) + x0
            return int(reg[ry, rx]), (rx, ry)
    return 0, (x, y)


def _region_near(reg: np.ndarray, x: int, y: int, max_radius: int) -> int:
    """The region label at ``(x, y)``, or the nearest labelled pixel within
    ``max_radius`` (0 if none — the anchor missed land entirely)."""
    return resolve_anchor(reg, x, y, max_radius)[0]


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


def _subdivide_cell(mask: np.ndarray, k: int, min_area: int, wrap_x: bool,
                    anchors: list[tuple[int, int]] | None = None,
                    geodesic: bool = False) -> np.ndarray:
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

    ``anchors`` (#3665) is a list of canvas ``(x, y)`` hub anchors that fall inside
    this ``mask``. Each becomes a **fixed** first Voronoi seed, so a distinct
    province forms at every anchor; ``cells._farthest_seeds`` fills the remaining
    ``k - len(anchors)`` seats (callers guarantee ``k >= len(anchors)``). After the
    fill+split, the anchor-bearing pieces are passed to ``merge_small`` as
    ``protected`` so a deliberately-small hub province is never swallowed. The mask
    is untouched. ``anchors=None`` is byte-identical to the original cut.

    ``geodesic=True`` (#3704, painted regions only) assigns each pixel to the seat
    nearest *through the mask* (flat-image watershed, a BFS partition) instead of
    the straight-line nearest, so a winding passable tract is cut along its length
    rather than sliced across the paint. Default keeps the byte-identical path.
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
    # Translate canvas anchors into local box coords, applying the same seam roll.
    W = mask.shape[1]
    anchor_local: list[tuple[int, int]] = []
    if anchors:
        for ax, ay in anchors:
            ly = int(ay) - int(y0)
            lx = ((int(ax) + shift) % W) - int(x0)
            anchor_local.append((ly, lx))
    if anchor_local:
        fixed = np.array(anchor_local, dtype=pix.dtype)
        seeds = cells._farthest_seeds(pix, k, fixed=fixed)
    else:
        seeds = cells._farthest_seeds(pix, k)
    seed_img = np.zeros(local.shape, dtype=np.int32)
    seed_img[tuple(seeds.T)] = np.arange(1, len(seeds) + 1, dtype=np.int32)
    # Nearest labelled seed for every region pixel — one EDT over the box.
    if geodesic:
        from skimage.segmentation import watershed
        filled = watershed(np.zeros(local.shape, dtype=np.uint8), markers=seed_img,
                           mask=local, connectivity=1).astype(np.int32)
    else:
        filled = cells.fill_nearest(seed_img, local, wrap_x=False)
    # Local cleanup, all within this region: split any Voronoi piece the region's
    # concavity tore, then swallow sub-floor slivers into a same-region neighbour.
    filled = np.where(local, filled, 0)
    filled = cells.split_disconnected(filled, wrap_x=False)
    protected: set[int] | None = None
    if anchor_local:
        protected = {int(filled[ly, lx]) for ly, lx in anchor_local}
        protected.discard(0)
    filled = cells.merge_small(filled, min_area, wrap_x=False, protected=protected)
    filled = cells.renumber(filled)
    patch = np.zeros_like(m, dtype=np.int32)
    patch[y0:y1, x0:x1] = filled
    if shift:
        patch = np.roll(patch, -shift, axis=1)
    out = np.zeros(mask.shape, dtype=np.int32)
    out[patch > 0] = patch[patch > 0]
    return out


#: The flat fill colour of the hand-painted impassable layer (`full.ora#impassable`,
#: measured zero fringe). Single home; validate_map imports it.
IMPASSABLE_RGB = (255, 127, 0)

def city_dots(rgba: np.ndarray, land: np.ndarray) -> list[tuple[int, int]]:
    """Anchor pixel ``(x, y)`` of every dot on the hand-painted ``cities`` layer
    (`full.ora#cities`): one per 4-connected opaque blob, at its centroid (snapped to
    the nearest blob pixel if the centroid is not on the blob), dropped when the
    anchor is not on land. Sorted by (y, x) so the order is deterministic."""
    m = rgba[..., 3] > 0
    if not m.any():
        return []
    lab, n = ndimage.label(m)
    out: list[tuple[int, int]] = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        ys, xs = np.nonzero(lab[sl] == i)
        ys = ys + sl[0].start
        xs = xs + sl[1].start
        cy, cx = int(round(ys.mean())), int(round(xs.mean()))
        if lab[cy, cx] != i:
            k = int(np.argmin((ys - cy) ** 2 + (xs - cx) ** 2))
            cy, cx = int(ys[k]), int(xs[k])
        if land[cy, cx]:
            out.append((cx, cy))
    return sorted(out, key=lambda p: (p[1], p[0]))


def city_blobs(rgba: np.ndarray, land: np.ndarray) -> list[np.ndarray]:
    """Land pixels of every 4-connected opaque blob on the ``cities`` layer, as
    ``(N, 2)`` ``[y, x]`` arrays, sorted by each blob's top-left pixel (y, x) so
    the order is deterministic. A blob with no land pixel is dropped."""
    m = rgba[..., 3] > 0
    if not m.any():
        return []
    lab, _ = ndimage.label(m)
    out: list[np.ndarray] = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        ys, xs = np.nonzero((lab[sl] == i) & land[sl])
        if ys.size == 0:
            continue
        out.append(np.stack([ys + sl[0].start, xs + sl[1].start], axis=1))
    return sorted(out, key=lambda p: (int(p[:, 0].min()),
                                      int(p[p[:, 0] == p[:, 0].min(), 1].min())))


def unify_city_blobs(out: np.ndarray, blobs: list[np.ndarray], reg: np.ndarray,
                     imp: np.ndarray | None, keep_whole_labels: set[int],
                     anchors: list[tuple[int, int]] | None, wrap_x: bool = True,
                     log=None, line: np.ndarray | None = None
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Post-cut pass (#5679): put each city blob's land pixels under one province.

    Runs on pre-renumber labels and only rewrites blob pixels (of the receiver's
    own region and paint class), then hands any donor fragment the rewrite orphaned
    back to the receiver. A blob straddling a state-region border or the paint edge
    by more than :data:`PAINT_NOISE_PX` px is a hard :class:`cells.CellError`; a
    graze of at most that many px is clipped (its minority pixels left alone).
    Receiver = the single anchor-bearing province under the blob, else the majority
    label (tie -> lowest); two anchor-bearing provinces is an error.

    ``line`` is the *drawn* (undilated) magenta mask. The region fill dilates the
    line and hands the dilated band to the nearest region, so a blob touching a line
    (or sitting in a sliver between two) can be split across regions with no drawn
    line under it. Such a region-only split (same paint class, no ``line`` pixel
    under the blob) is not a crossing: the blob is moved whole into its majority
    region and ``reg`` patched to match. Returns ``(labels, reg)``."""
    if not blobs:
        return out, reg
    out = out.copy()
    reg = reg.copy()
    anchor_labels = {int(out[ay, ax]) for ax, ay in (anchors or ())}
    problems: list[str] = []
    for blob in blobs:
        ys, xs = blob[:, 0], blob[:, 1]
        cy, cx = int(round(ys.mean())), int(round(xs.mean()))
        labs = out[ys, xs]
        uniq = np.unique(labs)
        if uniq.size == 1 or any(int(u) in keep_whole_labels for u in uniq):
            continue
        where = f"city blob at ({cx}, {cy})"
        # Region and paint class must agree beyond a graze.
        keys = reg[ys, xs].astype(np.int64) * 2
        if imp is not None:
            keys = keys + imp[ys, xs].astype(np.int64)
        kv, kc = np.unique(keys, return_counts=True)
        pool = labs  # labels the receiver may be chosen from
        if kv.size > 1:
            major = kv[int(np.argmax(kc))]
            minor = int(kc.sum() - kc.max())
            sliver = (line is not None and not bool(line[ys, xs].any())
                      and len({int(k) % 2 for k in kv}) == 1)
            if sliver:
                if log:
                    log(f"  {where}: split across regions by the dilated line band "
                        f"only ({minor} px); moved into its majority region")
                pool = labs[keys == major]
                reg[ys, xs] = int(major) // 2
            elif minor > PAINT_NOISE_PX:
                detail = ", ".join(
                    "region %d %s: %d px" % (int(k) // 2, "impassable" if int(k) % 2 else "passable", int(n))
                    for k, n in zip(kv, kc))
                problems.append(
                    f"{where} straddles a state-region border or paint edge "
                    f"({minor} px outside its main region/paint class of {int(kc.max())} px; "
                    f"{detail}); move the blob or the border")
                continue
            else:
                if log:
                    log(f"  WARNING: {where} grazes a border/paint edge by {minor} px; clipped")
                keep = keys == major
                ys, xs, labs = ys[keep], xs[keep], labs[keep]
                pool = labs
                uniq = np.unique(labs)
                if uniq.size == 1:
                    continue
        held = [int(u) for u in uniq if int(u) in anchor_labels]
        if len(held) > 1:
            problems.append(
                f"{where} covers hub anchors of {len(held)} different provinces; "
                f"move the blob or the hubs")
            continue
        if held:
            recv = held[0]
        else:
            cnt = np.bincount(pool.astype(np.int64))
            recv = int(np.argmax(cnt))  # first max == lowest label on a tie
        out[ys, xs] = recv
        # Donor repair: keep each donor label one piece (its largest component).
        for d in (int(u) for u in uniq if int(u) != recv):
            dm = out == d
            if not dm.any():
                continue
            comp = cells.components(dm.astype(np.int32), wrap_x)
            comp[~dm] = 0
            sz = np.bincount(comp.ravel())
            sz[0] = 0
            biggest = int(np.argmax(sz))
            rm = out == recv
            grown = ndimage.binary_dilation(rm)
            if wrap_x:
                grown[:, 0] |= rm[:, -1]
                grown[:, -1] |= rm[:, 0]
            for c in np.unique(comp[dm]):
                c = int(c)
                if (c and c != biggest and (comp == c)[grown].any()
                        and reg[comp == c][0] == reg[ys[0], xs[0]]):
                    out[comp == c] = recv
    if problems:
        raise cells.CellError(f"{len(problems)} city blob(s) cannot be kept whole:\n  "
                              + "\n  ".join(problems))
    return out, reg


def impassable_mask(rgba: np.ndarray, land: np.ndarray) -> np.ndarray:
    """Boolean impassable mask from the layer's RGBA: alpha > 0 and RGB exactly
    :data:`IMPASSABLE_RGB`, intersected with ``land`` (paint over water is ignored)."""
    rgb = rgba[..., :3]
    hit = (rgba[..., 3] > 0) & np.all(rgb == np.array(IMPASSABLE_RGB, dtype=rgb.dtype), axis=-1)
    return hit & land


#: Paint hygiene threshold (Chris, 2026-09-24): impassable blobs and fully-enclosed
#: passable gaps of at most this many px are noise.
PAINT_NOISE_PX = 4


def clean_paint(imp: np.ndarray, land: np.ndarray, wrap_x: bool = True,
                max_px: int = PAINT_NOISE_PX) -> np.ndarray:
    """Erase impassable blobs of <= ``max_px`` px, then fill completely enclosed
    passable gaps of <= ``max_px`` px (a non-paint component that touches no water and
    no larger passable land, i.e. wholly surrounded by paint). Wrap-aware, pure."""
    imp = imp.copy()
    comp = cells.components(imp.astype(np.int32), wrap_x)
    sz = np.bincount(comp.ravel(), minlength=int(comp.max()) + 1)
    small = sz <= max_px
    small[0] = False
    imp &= ~small[comp]
    free = ~imp
    fcomp = cells.components(free.astype(np.int32), wrap_x)
    fsz = np.bincount(fcomp.ravel(), minlength=int(fcomp.max()) + 1)
    hole = fsz <= max_px
    hole[0] = False
    fill = hole[fcomp] & land
    # a gap containing any water pixel is not "enclosed" by paint alone
    bad = np.unique(fcomp[hole[fcomp] & ~land])
    if bad.size:
        fill &= ~np.isin(fcomp, bad)
    return imp | fill


def subdivide(*args, **kwargs) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """:func:`subdivide_ex` without the impassable table — the original 4-tuple
    ``(labels, is_placeholder, reg_of, is_archipelago)``. With no ``impassable``
    kwarg it is byte-identical to the pre-#3704 cut."""
    return subdivide_ex(*args, **kwargs)[:4]


def subdivide_ex(reg: np.ndarray, land: np.ndarray, drawn: np.ndarray, target: int,
                 wrap_x: bool = True, min_area: int = 400, log=None,
                 keep_whole: set[int] | None = None,
                 region_seeds: dict[int, list[tuple[int, int]]] | None = None,
                 island_zones: np.ndarray | None = None,
                 impassable: np.ndarray | None = None,
                 strict_placeholder_paint: bool = False,
                 keep_passable: list[tuple[int, int]] | None = None,
                 city_blobs: list[np.ndarray] | None = None,
                 city_line: np.ndarray | None = None,
                 city_seeds: list[tuple[int, int]] | None = None,
                 city_seed_sep: int = 16
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Cut the drawn regions into provinces to reach ``target`` land provinces.

    ``reg`` is the state-region layer from :func:`regions` (``1..R``, 0 on water);
    ``drawn`` is the :func:`drawn_mask` of the hand-drawn land. Every province
    stays within one region (no magenta line is crossed), so seats are shared out
    among the **drawn** regions only, proportional to area under the
    largest-remainder rule with each drawn region guaranteed at least one. A
    placeholder region (outside ``drawn``) is kept whole — one province.

    ``keep_whole`` is the set of region labels that must never be cut even when
    disconnected — the island-override archipelagos, from
    :func:`override_fused_labels`. A **disconnected** drawn region that is *not* in
    ``keep_whole`` is a merge-fused region (:func:`apply_land_region_merges` unioned
    two non-touching labels) and is cut **per connected piece** (its seats shared
    across pieces by area, each piece ≥ 1 province, ``_subdivide_cell`` per piece,
    the region label used exactly once region-wide); a disconnected region *in*
    ``keep_whole`` stays whole as one province. Connectivity alone cannot tell the
    two apart, which is why the set is threaded in. ``keep_whole is None`` ⟹ empty
    set (every disconnected drawn region is cut — the merge-fused case).

    ``island_zones`` is the :func:`island_override_zones` layer. With it, a
    ``keep_whole`` region that a state-level merge chained across several island
    lines ships as one province per line-group instead of one for the whole
    state; ``None`` (or a single group) keeps it whole, byte-identical to before.

    ``region_seeds`` (#3665) is ``{region_label: [(x, y), ...]}`` of hub anchors,
    each an already-resolved in-region pixel. A region carrying anchors is cut so a
    distinct province forms at every anchor: its seat count is bumped to at least
    its anchor count, the anchors are forwarded to ``_subdivide_cell`` as fixed
    seeds (routed to the right connected piece in the merge-fused branch), and the
    anchor pieces survive ``merge_small``. An anchor targeting a ``keep_whole``
    archipelago or a non-drawn region is a hard error. ``region_seeds=None`` keeps
    every region byte-identical to today.

    ``impassable`` (#3704) is the boolean impassable-terrain mask (already
    intersected with land). A drawn region that
    carries impassable pixels bypasses the single-seat shortcut and is split into
    wrap-aware connected **passable** pieces (which share the region's seat budget
    by area, each >= 1, cut by ``_subdivide_cell``) and connected **impassable**
    pieces (exactly one province each, on top of the budget - so ``target`` is a
    floor for painted regions). No province straddles the boundary. Impassable
    pieces smaller than ``min_area`` px are folded back to passable (paint
    dust). Paint on a ``keep_whole`` archipelago or a placeholder region, a
    region that is wholly impassable, or a hub anchor that lands on impassable
    paint is a hard :class:`cells.CellError`. ``None`` / no paint => byte-identical
    to before. Paint on an out-of-scope placeholder region is **disregarded**
    (logged, source untouched - the paint is kept in the .ora for when that land
    comes into scope; Chris, 2026-09-24); ``strict_placeholder_paint=True`` (the
    generator's ``--strict-placeholder-paint``) makes it a hard error instead. Every
    other unsupported case stays a hard error.

    Returns ``(labels, is_placeholder, reg_of, is_archipelago, is_impassable)``
    (:func:`subdivide` drops the last):

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
    * ``is_impassable`` — a boolean table indexed by label, ``True`` for a
      province cut from impassable paint. Independent of ``is_placeholder``.
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
    keep = keep_whole or set()
    seeds_by_region = region_seeds or {}
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

    # Hub anchors (#3665) can only seed a distinct province in a drawn, cuttable
    # region — never a keep_whole archipelago (stays one province) or a placeholder.
    if seeds_by_region:
        drawn_set = set(drawn_ids)
        for rid, pts in seeds_by_region.items():
            if rid in keep:
                raise cells.CellError(
                    f"hub anchor(s) {pts} target region {rid}, a keep_whole "
                    f"island-override archipelago — it cannot host a distinct hub province")
            if rid not in drawn_set:
                raise cells.CellError(
                    f"hub anchor(s) {pts} target region {rid}, which is not a drawn "
                    f"in-scope state (placeholder or empty)")

    # Impassable paint (#3704): per-region masks, validated up front.
    imp_regions: set[int] = set()
    imp = None
    if impassable is not None and impassable.any():
        imp = impassable & land
        # Sub-floor impassable dust is not a province: fold it back to passable.
        if min_area > 1:
            icomp0 = cells.components(imp.astype(np.int32), wrap_x)
            isz = np.bincount(icomp0.ravel(), minlength=int(icomp0.max()) + 1)
            dust = isz < min_area
            dust[0] = False
            imp = imp & ~dust[icomp0]
        drawn_set2 = set(drawn_ids)
        problems: list[str] = []
        for rid in np.unique(reg[imp]).tolist():
            if rid <= 0:
                continue
            ys, xs = np.nonzero(imp & (reg == rid))
            where = f"{len(xs):,} px around ({int(xs.mean())}, {int(ys.mean())})"
            if rid in keep:
                problems.append(
                    f"region {rid} ({where}) is a keep_whole island-override archipelago - "
                    f"it cannot be split into passable/impassable provinces")
            elif rid not in drawn_set2 and not strict_placeholder_paint:
                imp = imp & ~(reg == rid)  # explicit opt-in: placeholder land stays passable
                if log:
                    log(f"  WARNING: disregarded impassable paint on out-of-scope placeholder "
                        f"region {rid} ({where})")
            elif rid not in drawn_set2:
                problems.append(
                    f"region {rid} ({where}) is an out-of-scope placeholder - placeholders "
                    f"stay one passable province")
            elif not ((reg == rid) & ~imp).any():
                problems.append(f"region {rid} ({where}) is wholly impassable - a state "
                                f"needs passable land")
            else:
                imp_regions.add(int(rid))
        if problems:
            raise cells.CellError(
                f"impassable paint on {len(problems)} region(s) that cannot take it:\n  "
                + "\n  ".join(problems))

    # City seeds (#5679): every city dot is a fixed seed so each blob forms its own
    # province. Hub anchors keep priority; a dot is skipped (and logged) when it is
    # on a keep_whole archipelago / non-drawn region / impassable paint, or within
    # ``city_seed_sep`` px of an already-accepted seed in its region (two seeds that
    # close would collapse into one province anyway).
    if city_seeds:
        drawn_now = set(drawn_ids)
        merged = {k: list(v) for k, v in seeds_by_region.items()}
        skipped: dict[str, list[tuple[int, int]]] = {}
        for cx_, cy_ in city_seeds:
            rid = int(reg[cy_, cx_])
            if rid <= 0 or rid in keep or rid not in drawn_now:
                skipped.setdefault("archipelago/placeholder region", []).append((cx_, cy_))
                continue
            if imp is not None and imp[cy_, cx_]:
                skipped.setdefault("on impassable paint", []).append((cx_, cy_))
                continue
            near = merged.setdefault(rid, [])
            if any((cx_ - ax) ** 2 + (cy_ - ay) ** 2 < city_seed_sep ** 2 for ax, ay in near):
                skipped.setdefault(f"within {city_seed_sep}px of another seed", []).append((cx_, cy_))
                continue
            near.append((cx_, cy_))
        seeds_by_region = merged
        if log:
            n_used = sum(len(v) for v in merged.values()) - sum(len(v) for v in (region_seeds or {}).values())
            log(f"  city seeds: {n_used} of {len(city_seeds)} cities seeded")
            for why, pts in skipped.items():
                log(f"  WARNING: {len(pts)} city seed(s) skipped ({why}): "
                    + ", ".join(f"({x},{y})" for x, y in pts[:12]) + (" ..." if len(pts) > 12 else ""))
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
    # A seeded region needs at least as many seats as it has distinct anchors, so
    # every hub can get its own province (soft-target drift is fine, per #3664).
    if seeds_by_region:
        for idx, i in enumerate(drawn_ids):
            a = len(seeds_by_region.get(i, ()))
            if a > seats[idx]:
                seats[idx] = a
    seat_by_id = dict(zip(drawn_ids, seats.tolist()))
    a_nom = max(1.0, float(drawn_areas.sum()) / max(1, target))  # nominal province area
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
        m = reg == i
        anchors = seeds_by_region.get(i)
        if i in imp_regions:
            # Work on the region's row band only (full width, so the x seam still
            # wraps): a full-canvas pass per painted region is prohibitively slow.
            rows = np.flatnonzero(m.any(axis=1))
            y0, y1 = int(rows[0]), int(rows[-1]) + 1
            m_c = m[y0:y1]
            # Passable specks below min_area trapped by the paint are not provinces
            # (the mirror of the impassable-dust rule): fold them into the paint,
            # except a component holding a hub anchor or a ``keep_passable`` point
            # (a canon city's province). Never folds the region's last passable land.
            anchors_c = [(ax, ay - y0) for ax, ay in (anchors or ())]
            keep_c = [(ax, ay - y0) for ax, ay in (keep_passable or ())
                      if y0 <= ay < y1] + anchors_c
            # A state-region border can slice a paint tract into a sliver inside this
            # region: paint pieces below min_area *within the region* revert to
            # passable (the global dust rule only sees whole-canvas components).
            ic0 = cells.components((m_c & imp[y0:y1]).astype(np.int32), wrap_x)
            isz0 = np.bincount(ic0.ravel(), minlength=int(ic0.max()) + 1)
            idust = isz0 < min_area
            idust[0] = False
            idust_px = idust[ic0] & m_c & imp[y0:y1]
            if idust_px.any():
                imp[y0:y1][idust_px] = False
            pas0 = m_c & ~imp[y0:y1]
            pc0 = cells.components(pas0.astype(np.int32), wrap_x)
            sz0 = np.bincount(pc0.ravel(), minlength=int(pc0.max()) + 1)
            tiny = sz0 < min_area
            tiny[0] = False
            for ax, ay in keep_c:
                if pc0[ay, ax] > 0:
                    tiny[pc0[ay, ax]] = False
            if tiny.any() and not tiny[pc0[pas0]].all():
                fold = tiny[pc0] & pas0
                imp[y0:y1][fold] = True
            elif tiny.any():
                # Every passable piece is sub-floor: the region is essentially all
                # paint. A state needs real passable land, so the paint on this
                # region is disregarded (logged; the source keeps it).
                imp[y0:y1][m_c] = False
                if log:
                    log(f"  WARNING: region {i} is almost entirely impassable paint - "
                        f"paint disregarded there ({int(m_c.sum()):,} px)")
            imp_m = m_c & imp[y0:y1]
            pas_m = m_c & ~imp[y0:y1]
            for ax, ay in anchors_c:
                if imp_m[ay, ax]:
                    raise cells.CellError(
                        f"hub anchor ({ax}, {ay + y0}) in region {i} lies on impassable paint")
            pcomp = cells.renumber(np.where(
                pas_m, cells.components(pas_m.astype(np.int32), wrap_x), 0))
            icomp = cells.renumber(np.where(
                imp_m, cells.components(imp_m.astype(np.int32), wrap_x), 0))
            pc, ic = int(pcomp.max()), int(icomp.max())
            p_areas = np.bincount(pcomp.ravel(), minlength=pc + 1)[1:].astype(np.float64)
            # Seat density on passable land inside painted regions matches open land:
            # each piece gets round(area / nominal province area), where the nominal
            # area is the one every unpainted region is cut to (drawn area / target).
            # No per-region budget and no shape heuristics - a wide tunnel and a narrow
            # one of the same area get the same number of provinces, and neither is
            # over- or under-cut relative to the open land beside it.
            pk = np.maximum(1, np.rint(p_areas / a_nom).astype(int))
            piece_seeds_i: dict[int, list[tuple[int, int]]] = {}
            for ax, ay in anchors_c:
                cid = int(pcomp[ay, ax])
                if cid > 0:
                    piece_seeds_i.setdefault(cid, []).append((ax, ay))
            for cid, pts in piece_seeds_i.items():
                if len(pts) > pk[cid - 1]:
                    pk[cid - 1] = len(pts)
            out_c = out[y0:y1]  # view
            first_i = True
            for cid in range(1, pc + 1):
                pm = pcomp == cid
                sub = _subdivide_cell(pm, int(pk[cid - 1]), min_area, wrap_x,
                                      anchors=piece_seeds_i.get(cid), geodesic=True)
                q = int(sub.max())
                ids = np.zeros(q + 1, dtype=np.int32)
                start = 1
                if first_i:
                    ids[1] = i  # region label used exactly once, region-wide
                    start = 2
                    first_i = False
                for j in range(start, q + 1):
                    ids[j] = nxt
                    nxt += 1
                out_c[pm] = ids[sub[pm]]
            for cid in range(1, ic + 1):
                out_c[icomp == cid] = nxt
                nxt += 1
            continue
        if _is_connected(m, wrap_x):
            # Contiguous drawn region: the ordinary single-cell cut.
            if k <= 1:
                # One seat: the whole region is one province. If it carries a
                # single anchor, that province IS the hub — no cut needed.
                continue
            pieces = _subdivide_cell(m, k, min_area, wrap_x, anchors=anchors)  # 1..p on region
            p = int(pieces.max())
            # Piece 1 keeps the region's own label i; pieces 2..p get fresh labels.
            ids = np.zeros(p + 1, dtype=np.int32)
            ids[1] = i
            for j in range(2, p + 1):
                ids[j] = nxt
                nxt += 1
            out[m] = ids[pieces[m]]
            continue

        # --- disconnected region ---
        if i in keep:
            # An island-override merge (merge_island_overrides) fused several
            # disconnected islets into one label on purpose — one province per
            # island line. A state-level merge can chain several lines' regions
            # into one label; then each line's group is its own province, so the
            # state still has one province per line. One group ⟹ stays whole.
            if island_zones is None:
                continue
            comp = cells.components(m.astype(np.int32), wrap_x)
            comp = cells.renumber(np.where(m, comp, 0))
            c = int(comp.max())
            parent = list(range(c + 1))

            def find(a: int) -> int:
                while parent[a] != a:
                    parent[a] = parent[parent[a]]
                    a = parent[a]
                return a

            zone_owner: dict[int, int] = {}
            for cid, z in np.unique(
                    np.stack([comp[m], island_zones[m]], axis=1), axis=0).tolist():
                if z <= 0:
                    continue
                if z in zone_owner:
                    ra, rb = find(zone_owner[z]), find(cid)
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
                else:
                    zone_owner[z] = cid
            groups = sorted({find(cid) for cid in range(1, c + 1)})
            if len(groups) <= 1:
                continue
            ids = {g: (i if k == 0 else nxt + k - 1) for k, g in enumerate(groups)}
            nxt += len(groups) - 1
            root = np.array([0] + [ids[find(cid)] for cid in range(1, c + 1)],
                            dtype=np.int32)
            out[m] = root[comp[m]]
            continue
        # A merge-fused drawn region (apply_land_region_merges unioned two
        # non-touching labels): its halves are separate landmasses, so cut each
        # connected piece on its own. cells.components is the same wrap-aware
        # primitive _is_connected agrees with, so a seam-wrapped region is one
        # piece here too. Seats are shared across the pieces by area (each piece
        # ≥ 1), and the region label i is assigned exactly once across all pieces
        # so the region does not remain a single disconnected label.
        comp = cells.components(m.astype(np.int32), wrap_x)
        comp = cells.renumber(np.where(m, comp, 0))  # 0 off-region, 1..c per piece
        c = int(comp.max())
        piece_areas = np.bincount(comp.ravel(), minlength=c + 1)[1:].astype(np.float64)
        pk = np.ones(c, dtype=int)
        spare = max(0, k - c)  # k < c ⟹ spare 0, one province per piece
        if spare and piece_areas.sum() > 0:
            quota = piece_areas / piece_areas.sum() * spare
            base = np.floor(quota).astype(int)
            rem = spare - int(base.sum())
            order = np.argsort(-(quota - base), kind="stable")
            base[order[:rem]] += 1
            pk += base
        # Route each anchor to the connected piece it falls in, and make sure that
        # piece has at least as many seats as it carries anchors (#3665).
        piece_seeds: dict[int, list[tuple[int, int]]] = {}
        if anchors:
            for ax, ay in anchors:
                cid = int(comp[ay, ax])
                if cid > 0:
                    piece_seeds.setdefault(cid, []).append((ax, ay))
            for cid, pts in piece_seeds.items():
                if len(pts) > pk[cid - 1]:
                    pk[cid - 1] = len(pts)
        first = True
        for cid in range(1, c + 1):
            pm = comp == cid
            sub = _subdivide_cell(pm, int(pk[cid - 1]), min_area, wrap_x,
                                  anchors=piece_seeds.get(cid))  # 1..q on piece
            q = int(sub.max())
            ids = np.zeros(q + 1, dtype=np.int32)
            start = 1
            if first:
                ids[1] = i  # region label used exactly once, region-wide
                start = 2
                first = False
            for j in range(start, q + 1):
                ids[j] = nxt
                nxt += 1
            out[pm] = ids[sub[pm]]

    if city_blobs:
        # City blobs (#5679): one province per painted blob. Region labels used as
        # province labels for keep_whole archipelagos are protected as-is.
        # Only hub anchors are decisive: a city dot's own province is not special,
        # and neighbouring provinces that each carry a dot are the common case.
        anchor_pts = []
        for pts in seeds_by_region.values():
            anchor_pts.extend(pts)
        out, reg = unify_city_blobs(out, city_blobs, reg, imp, set(int(k) for k in keep),
                                    anchor_pts, wrap_x, log=log, line=city_line)
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

    # Flag every genuinely non-contiguous province (an island-override
    # archipelago in keep_whole, which the loop above leaves whole; a merge-fused
    # disconnected region is now cut per piece and so is contiguous) so a
    # validator can tell it apart from an accidentally torn one. One global
    # connected-components pass, exactly the check validate_map.py itself runs.
    comp = cells.components(out, wrap_x)
    pairs = np.unique(np.stack([out.ravel(), comp.ravel()], axis=1), axis=0)
    counts = np.bincount(pairs[:, 0].astype(np.int64), minlength=int(out.max()) + 1)
    is_archipelago = counts > 1
    is_archipelago[0] = False

    if log:
        log(f"  {int(out.max())} land provinces "
            f"({int(is_placeholder[1:].sum())} out-of-scope placeholders, "
            f"{int(is_archipelago.sum())} archipelagos)")
    # Every impassable province is wholly inside the (dust-filtered) paint and every
    # passable one wholly outside it, so the flag is read straight off the pixels.
    is_impassable = np.zeros(int(out.max()) + 1, dtype=bool)
    if imp is not None:
        is_impassable[out[imp]] = True
    is_impassable[0] = False
    return out, is_placeholder, reg_of, is_archipelago, is_impassable
