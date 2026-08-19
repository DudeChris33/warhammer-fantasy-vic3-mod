#!/usr/bin/env python3
"""S3a generator: the committed state-label layer.

Produces one label per state cell over the whole canvas, tiling the committed
``tools/derived/land_sea_mask.png`` exactly — every land pixel in exactly one land
cell, every water pixel in exactly one sea zone — at vanilla-order granularity.
This is the layer S3b cuts ~40k provinces from, and the artifact the S3a gate asks
a human to look at.

Pipeline::

    registered boundary sources (SHA-256 verified)
        -> local-contrast ink -> label the complement   (cells, in source px)
        -> warp onto the canvas, nearest                (never interpolated)
        -> stack by boundary precedence                 (never blended)
        -> intersect with the committed land mask       (mask is the authority)
        -> seed fresh cells where no source reaches     (~40% of land)
        -> nearest-label fill                           (mask-constrained watershed)
        -> split torn cells, merge small, split large   (density reconciliation)
        -> sea zones from the mask's water bodies
        -> macro grouping from the annotated twin
        -> tools/derived/state_labels.png + _index.json + COVERAGE.md

Outputs
-------
``state_labels.png``       16-bit grayscale, lossless. Land cells 1..N, sea zones
                           N+1..N+M, 0 nowhere.
``state_labels_index.json``per-label macro, area, coastal flag, provisional key.
``COVERAGE.md``            achieved density per macro against the target, naming
                           every region that still wants a boundary source.

Usage::

    python tools/generate_state_labels.py
    python tools/generate_state_labels.py --preview   # + a downscaled PNG to eyeball
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import cells, macro, parchment, raster, schema, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
LABELS_PATH = DERIVED_DIR / "state_labels.png"
INDEX_PATH = DERIVED_DIR / "state_labels_index.json"
COVERAGE_PATH = DERIVED_DIR / "COVERAGE.md"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: Vanilla's own granularity, measured from the shipped map: 659 land + 103 sea
#: state blocks. Matching it is user decision #6 — the map should feel like a
#: Victoria 3 map, not a coarser one, and 659 over our 8,249,246 land px puts the
#: mean land state at ~12,500 canvas px (about 112x112).
TARGET_LAND_STATES = 659
TARGET_SEA_ZONES = 103

#: The density *count* snap targets the TOP of the user's 600–700 band, not the
#: vanilla 659, so density reconciliation never merges a legitimate cell away just
#: to hit the point count — the 2026-08-15 decision to prefer satisfying the Old
#: World ``min_states`` over snapping the total. ``TARGET_LAND_STATES`` still sets
#: the *mean cell size* (``target_area``) that drives split-large / merge-small, so
#: individual cells stay vanilla-sized; only the global count is allowed to drift
#: up into the band as the denser Old World sources supply real cells.
MERGE_TARGET_LAND_STATES = 700

#: How far a cell may sit from the target before it is merged away or split up.
#: Deliberately loose: real states vary hugely in size, and forcing them towards
#: uniformity would erase the source's information, which is the whole point of
#: tracing rather than tessellating.
MIN_AREA_FRACTION = 0.35
MAX_AREA_FRACTION = 2.2

#: The merge floor inside the Old World crop footprints, as a fraction of the mean
#: cell area — deliberately far below ``MIN_AREA_FRACTION``. The Old World mod
#: parchment draws a province network an order of magnitude finer than a vanilla
#: state (Empire source cells average a few hundred px), and the user's per-macro
#: minimums (Empire ≥30 in a small footprint) require cells much smaller than
#: vanilla. Reconciling the Old World to the global floor merges that density clean
#: away (Empire fell to 11 of 30); this smaller floor lets it survive while the
#: rest of the map still reconciles to vanilla granularity. Tuned against the
#: `*_anchor_dot_warp_example.png` references + the user's per-macro minimums
#: (Empire ≥30, Bretonnia+Estalia+Tilea ≥24, Kislev+Norsca ≥30, Darklands ≥30):
#: state-, not province-, granularity. Bracketed: 0.35 (vanilla floor) gave Empire
#: 11, 0.15 gave 113; this targets ~35–45 per crop.
OLD_WORLD_MIN_AREA_FRACTION = 0.13

#: The merge floor for a macro whose borders were **hand-drawn** by the user
#: (``marker_lines``) rather than ink-traced. Those cells ARE the states the user
#: wants — there is no province noise to reconcile away — so they get a floor just
#: above rubble, preserving essentially every drawn cell (only coastal-clip
#: fragments below it merge). Much lighter than the ink floor above.
OLD_WORLD_MARKER_MIN_AREA_FRACTION = 0.05

#: A connected piece smaller than this fraction of its own source cell's largest
#: piece is coastal rubble from clipping to our mask, not a state. Expressed
#: relative to the cell, never to the target size: the traced cells are ~3.4x
#: FINER than a vanilla state (median 3,648 px against a 12,517 px target), so an
#: absolute threshold near the target deletes the boundary network itself. See
#: ``cells.prune_slivers``.
SLIVER_FRACTION = 0.35

#: Absolute floor on a cell's area, matching the minimum island the land mask
#: itself keeps (``generate_heightmap.MIN_FEATURE_AREA``). Any real island
#: therefore clears it, so a cell below it is an artefact of the partition rather
#: than a place — and S3b would have to cut provinces out of it.
MIN_CELL_AREA = 256

#: A land pixel further than this from any source cell is treated as uncovered
#: and gets its own seeded cell, rather than being swept into the nearest source
#: cell. Set well below the target cell's ~112 px width so a genuine gap inside a
#: covered region still fills from its neighbours, while a landmass the sources
#: never reach (Nippon, Khuresh) starts fresh.
UNCOVERED_DISTANCE = 72.0

#: The layer name whose precedence orders the boundary sources.
BOUNDARY_LAYER = "boundaries"

#: Sources consumed for boundaries. Membership is explicit rather than "every
#: record with a boundary precedence": the S1 record old_world_terrain.jpg still
#: declares one, yet is measured to be misregistered and annotated as unusable for
#: geometry. Naming the consumers here means adding a source is a deliberate edit,
#: not a side effect of a precedence.
#: name -> how its cells are extracted. A bare string is the extraction kind;
#: a dict is ``{"kind": ..., "ink": {...glyph/window overrides...}}`` for a source
#: whose lines/lettering sit at a different pixel scale than the IE master, whose
#: ink constants the bare-string sources inherit. ``flat_colour`` for a map whose
#: ocean is a flat fill and whose region lines are drawn over flat terrain fills;
#: ``ink``/``ink_bridged`` for a textured parchment needing a local-contrast
#: threshold (``ink_bridged`` also bridges lettering into the barrier).
#:
#: The three remaining ``tww3_old_world_mod_parchment_*`` crops are the denser
#: Old World boundary network, one per-region tile placed by the paired-anchor-dot
#: workflow. Each carries an intentional binary alpha mask (transparent = regions
#: cut away), honoured as its contributing footprint (see ``extract_source_cells``
#: and ``warp_cells``'s ``src_valid``), and a boundary precedence (110–113) above
#: IE (100) and ``tww3_colored`` (95) so its lines win *inside its own footprint*
#: only. NOTE 2026-08-17: their backing source files (and the Empire crop,
#: imperial_provinces.png, since removed below) are currently missing from
#: sources/ — the registrations are kept (not deleted) pending either their
#: restoration or a replacement registration for claude_old_world_state_regions.png
#: (the new unified marker-line source), which needs its own paired-anchor-dot fit
#: before it can stand in — a whole-map frame_alias isn't possible because the
#: master (tww3_old_world_mod_parchment.png) was never itself registered, only
#: these per-region crops were (a whole-map fit is defeated by inconsistent
#: regional scale, the same reason the crop workflow exists at all).
BOUNDARY_SOURCES = {
    "tww3_colored.png": "flat_colour",
    "tww3_ie_parchment.jpg": "ink_bridged",
    # The three macros are still ink-traced pending their own border markup;
    # they carry roads until then, but reach usable density.
    "tww3_old_world_mod_parchment_bretonnia.png": {"kind": "ink_bridged"},
    "tww3_old_world_mod_parchment_kislev_norsca.png": {"kind": "ink_bridged"},
    "tww3_old_world_mod_parchment_dark_lands.png": {"kind": "ink_bridged"},
}

#: The Old World macro footprints, measured directly from each crop's warped
#: ``alpha>0`` mask, and the user's per-macro state-count minimums (2026-08-15;
#: from ``tools/regions/named_regions.json`` — the_empire 30, bretonnia 15,
#: kislev 10, darklands 30). Because the annotated-twin macro grouping is blocked
#: (see :func:`assign_macros`), the crop footprints ARE the Old World macros for
#: counting: this measures density where the request is judged, without the twin.
#: imperial_provinces.png (the_empire) removed 2026-08-17 — its source file is
#: gone; no replacement wired in yet (see BOUNDARY_SOURCES note above).
OLD_WORLD_CROP_MIN_STATES = {
    "tww3_old_world_mod_parchment_bretonnia.png": ("bretonnia+estalia+tilea", 24),
    "tww3_old_world_mod_parchment_kislev_norsca.png": ("kislev+norsca", 30),
    "tww3_old_world_mod_parchment_dark_lands.png": ("darklands", 30),
}

#: Off-map background and legend panels, in each source's own pixels.
BOUNDARY_EXCLUDE = {
    "tww3_colored.png": [(0, 2450, 330, 3010)],
}

#: The clean counterpart the macro-annotated twin is differenced against. Named
#: by filename rather than looked up by registration role: it contributes no
#: geometry at all, only its unannotated pixels, so requiring it to carry a
#: registration record would be asserting a placement nothing uses.
MACRO_CLEAN_MASTER = "tww3_ie_parchment.jpg"

#: Ink-threshold parameters for the parchment line networks.
INK_WINDOW = 41
INK_OFFSET = 12
#: Minimum enclosed area, in source px, for a traced cell to be kept.
MIN_SOURCE_CELL = 150


def log(msg: str) -> None:
    print(msg, flush=True)


#: Default marker colour + tolerance for the ``marker_lines`` kind — pure magenta,
#: absent from the warm-brown parchment so it isolates exactly. A source overrides
#: per-record via ``marker_rgb`` / ``marker_tol`` in its ``BOUNDARY_SOURCES`` spec.
MARKER_RGB = (255, 0, 255)
MARKER_TOL = 80


def _normalize_source_spec(spec) -> tuple[str, dict]:
    """``BOUNDARY_SOURCES`` value -> ``(kind, params)``.

    A bare string is a kind with no overrides; a dict carries a ``kind`` plus the
    rest of its keys as params (``ink`` overrides for the parchment kinds,
    ``marker_rgb`` / ``marker_tol`` / ``min_source_cell`` for ``marker_lines``), so
    a source tunes its own extraction without disturbing the others.
    """
    if isinstance(spec, str):
        return spec, {}
    params = dict(spec)
    return params.pop("kind"), params


def _borrow_parent_footprint(reg: schema.SourceRegistration,
                             shape: tuple[int, int]) -> np.ndarray | None:
    """Resample a frame_alias parent's ``alpha>0`` mask into this source's frame.

    The border-markup crop the user draws on is a wider, fully-opaque re-crop of
    the same parchment, placed as a ``frame_alias`` of a narrower alpha-masked
    tile. It has no alpha of its own, so it would otherwise cover — and suppress
    the lower boundary layers across — everything it depicts, including the
    surroundings it happens to include. Borrowing the parent tile's accepted alpha
    footprint (``parent_px = child_px*scale + offset``, so the inverse index is a
    per-axis affine — separable, no interpolation) clips it to exactly the region
    the parent was placed for. Returns ``None`` if the parent is itself opaque.
    """
    fa = reg.frame_alias
    _, palpha = sources.load_source_image_rgba(fa.of)
    if palpha is None:
        return None
    pmask = palpha > 0
    ph, pw = pmask.shape
    h, w = shape
    px = np.rint(np.arange(w) * fa.scale[0] + fa.offset[0]).astype(np.int64)
    py = np.rint(np.arange(h) * fa.scale[1] + fa.offset[1]).astype(np.int64)
    vx, vy = (px >= 0) & (px < pw), (py >= 0) & (py < ph)
    sampled = pmask[np.ix_(py.clip(0, ph - 1), px.clip(0, pw - 1))]
    return sampled & np.outer(vy, vx)


def extract_source_cells(reg: schema.SourceRegistration, spec
                         ) -> tuple[np.ndarray, dict, np.ndarray | None]:
    """Trace one source's boundary network into a cell-label image.

    Returns ``(labels, extra, valid)`` — ``extra`` carries source-specific
    headline metrics (the ``ink_bridged`` path's before/after bridging counts)
    that the caller folds into the coverage report, and ``valid`` is the source's
    ``alpha>0`` footprint mask (``None`` for an opaque source). An alpha-masked
    region crop's transparent pixels are forced into the ink barrier so no cell
    forms there and no cell leaks across a transparent hole, and ``valid`` is
    passed to :func:`worldgen.cells.warp_cells` so the crop only *covers* — and
    therefore only suppresses the lower boundary layers — inside that footprint.
    """
    kind, params = _normalize_source_spec(spec)
    ink_params = params.get("ink", {})
    rgb, alpha = sources.load_source_image_rgba(reg.source)
    valid = alpha > 0 if alpha is not None else None
    if valid is None and reg.is_alias:
        # An opaque frame_alias (the user's wider border-markup re-crop) borrows
        # its parent tile's accepted alpha footprint so it contributes only there.
        valid = _borrow_parent_footprint(reg, rgb.shape[:2])
    exclude = BOUNDARY_EXCLUDE.get(reg.source, [])
    win = int(ink_params.get("window", INK_WINDOW))
    min_cell = int(params.get("min_source_cell", ink_params.get("min_source_cell", MIN_SOURCE_CELL)))
    glyph_kw = {k: ink_params[k] for k in ("min_area", "max_side", "min_height", "min_fill")
                if k in ink_params}
    extra: dict = {}
    if kind == "marker_lines":
        # The user has hand-drawn the state-region boundaries in a pure marker
        # colour (the border-markup workflow — the sister of the paired-anchor-dot
        # placement). Only those lines, the map's own rivers, and the coast are the
        # barrier; roads, province lines, terrain and lettering are ignored. The
        # user draws red only for the *land* borders and leaves the rivers to close
        # the rest (they deliberately stop each red line at a river), so the rivers
        # — the thick, very-dark bands, isolated from thin ink by an opening — are
        # detected and unioned in. The marker is dilated a little to bridge the
        # small gaps where two hand-drawn segments don't quite meet at a junction.
        # The enclosed cells are the states the user drew — nothing to reconcile.
        barrier, marker_frac, rivers_frac = parchment.marker_barrier(
            rgb, marker_rgb=params.get("marker_rgb", MARKER_RGB),
            tol=int(params.get("marker_tol", MARKER_TOL)),
            dilate=int(params.get("marker_dilate", 2)),
            rivers=params.get("rivers"), valid=valid)
        lab, n = parchment.cells_from_ink(barrier, min_cell)
        extra = {"marker_line_fraction": round(marker_frac, 4),
                 "marker_rivers_fraction": round(rivers_frac, 4)}
        log(f"  {reg.source:<44} marker {marker_frac:.4f} rivers {rivers_frac:.3f}  cells {n}")
    elif kind == "flat_colour":
        lab, land = parchment.flat_map_cells(rgb, min_area=min_cell, exclude=exclude)
        n = int(lab.max())
        log(f"  {reg.source:<44} flat  land {land.mean():.3f}  cells {n}")
    elif kind == "ink_bridged":
        # Lettering interrupts the ruled border to make room for the label,
        # which cells_from_ink's complement-labelling turns into a MERGE of the
        # cells either side — the unrecoverable failure mode (11 of 17 contours
        # on the first parchment pass). Filling the detected label footprint
        # into the barrier bridges the gap; cells.fill_nearest then hands the
        # bridge back to its neighbours downstream, converting the merge into a
        # recoverable "border a few px off" (world-map-parchment-areas-onto-globe.md,
        # measurement 3: +46% usable cells at this offset).
        off = float(ink_params.get("offset", parchment.INK_OFFSET_MASTER))
        ink = parchment.ink_mask(rgb, window=win, offset=off, exclude=exclude)
        if valid is not None:
            # Transparent = barrier: no cell forms in a cut-away region, and the
            # complement labelling cannot leak one cell across a transparent hole
            # into another.
            ink = ink | ~valid
        _, before = parchment.cells_from_ink(ink, min_cell)
        glyphs = parchment.glyph_mask(ink, **glyph_kw)
        blobs = parchment.label_blobs(glyphs)
        barrier = ink | (blobs > 0)
        lab, n = parchment.cells_from_ink(barrier, min_cell)
        sizes = np.bincount(lab.ravel())
        largest = int(sizes[1:].max()) if n else 0
        extra = {"traced_cells_before_bridge": before, "traced_cells_after_bridge": n,
                 "largest_traced_cell_px": largest}
        log(f"  {reg.source:<44} ink+bridge  {barrier.mean():.3f}  "
            f"cells {before} -> {n}  (largest {largest:,} px)")
    else:
        off = float(ink_params.get("offset", INK_OFFSET))
        ink = parchment.ink_mask(rgb, window=win, offset=off, exclude=exclude)
        if valid is not None:
            ink = ink | ~valid
        lab, n = parchment.cells_from_ink(ink, min_cell)
        log(f"  {reg.source:<44} ink   {ink.mean():.3f}  cells {n}")
    return lab.astype(np.int32), extra, valid


def build_layers(regs: dict[str, schema.SourceRegistration]
                 ) -> tuple[np.ndarray, np.ndarray, list[str], dict, dict[str, np.ndarray]]:
    """Warp every boundary source onto the canvas and stack it by precedence."""
    layers: list[tuple[str, int, np.ndarray, np.ndarray]] = []
    covered = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
    report: list[str] = []
    extra_stats: dict = {}
    inside_by_source: dict[str, np.ndarray] = {}
    for name, spec in BOUNDARY_SOURCES.items():
        reg = regs.get(name)
        if reg is None:
            raise SystemExit(f"{name} has no registration record — run tools/fit_registration.py")
        src, extra, valid = extract_source_cells(reg, spec)
        extra_stats.update(extra)
        t0 = time.time()
        lab, inside = cells.warp_cells(reg, regs, src, (CANVAS_H, CANVAS_W), src_valid=valid)
        covered |= inside
        inside_by_source[name] = inside
        prec = reg.precedence_for(BOUNDARY_LAYER)
        layers.append((name, prec, lab, inside))
        report.append(f"  precedence {prec:>3}  {name:<48} covers {100 * inside.mean():5.1f}% of canvas")
        log(f"  warped {name} in {time.time() - t0:.0f}s "
            f"(covers {100 * inside.mean():.1f}% of canvas)")
    return cells.stack_layers(layers, (CANVAS_H, CANVAS_W)), covered, report, extra_stats, inside_by_source


def seed_uncovered(labels: np.ndarray, land: np.ndarray, target: int) -> tuple[np.ndarray, float]:
    """Give land the sources never reached its own cells, at the target density.

    Without this the nearest-label fill would stretch a Cathay cell across the
    Sea of Dread to Nippon: Euclidean distance does not know about water, and a
    single cell spanning two continents is not a state. Seeding first means the
    fill has something local to grow from everywhere.

    Returns the seeded labels and the fraction of land that had no source.
    """
    from scipy import ndimage

    have = labels > 0
    if not have.any():
        raise SystemExit("no source cell survived the mask — check the registrations")
    dist = ndimage.distance_transform_edt(~have)
    uncovered = land & (dist > UNCOVERED_DISTANCE)
    frac = float(uncovered.sum()) / float(land.sum())
    if not uncovered.any():
        return labels, 0.0

    out = labels.copy()
    nxt = int(out.max()) + 1
    comp = cells.components(uncovered.astype(np.int32), WRAP_X)
    comp[~uncovered] = 0
    for cid in np.unique(comp):
        if cid == 0:
            continue
        pix = np.column_stack(np.nonzero(comp == cid))
        k = max(1, int(round(len(pix) / target)))
        seeds = cells._farthest_seeds(pix, k)
        out[tuple(seeds.T)] = np.arange(nxt, nxt + len(seeds), dtype=out.dtype)
        nxt += len(seeds)
    log(f"  seeded {nxt - int(labels.max()) - 1} cells over {100 * frac:.1f}% of land "
        f"that no source reaches")
    return out, frac


def build_land_cells(land: np.ndarray, regs: dict[str, schema.SourceRegistration]
                     ) -> tuple[np.ndarray, dict, dict[str, np.ndarray]]:
    stats: dict = {}
    log("tracing boundary sources:")
    stacked, covered, prec_report, extra_stats, inside_by_source = build_layers(regs)
    stats["precedence"] = prec_report
    stats["source_cells"] = int(stacked.max())
    stats.update(extra_stats)

    # Each Old World crop's warped alpha>0 footprint (now that inside is clipped by
    # src_valid) IS its macro footprint — the twin macro grouping is blocked, so
    # these masks are what render_coverage counts cells against per named macro.
    crop_footprints = {name: inside_by_source[name].copy() & land
                       for name in OLD_WORLD_CROP_MIN_STATES if name in inside_by_source}

    # IE-footprint land coverage: of the land the parchment master's own warp
    # reaches at all (its footprint, not the whole canvas — the frame stops
    # around Cathay), how much carries a traced cell rather than falling
    # through to the mask-wide seeded fallback below.
    ie_inside = inside_by_source.get(MACRO_CLEAN_MASTER)
    if ie_inside is not None:
        ie_land = ie_inside & land
        if ie_land.any():
            stats["ie_footprint_land_coverage"] = round(
                float((stacked > 0)[ie_land].sum()) / float(ie_land.sum()), 4)

    # The mask is the coastline authority: a source cell that spills into the sea
    # is clipped here and can never move a coast (user decision #1/#2).
    stacked[~land] = 0
    log(f"  {int((stacked > 0).sum()) / land.sum() * 100:.1f}% of land carries a source cell")

    # Clipping to the mask tears each cell into one real piece plus coastal
    # rubble. Keep the substantial pieces (each becomes its own state — a cell cut
    # in two by a strait is two states) and hand the rubble back to the fill.
    before = int(stacked.max())
    stacked = cells.prune_slivers(stacked, WRAP_X, SLIVER_FRACTION)
    log(f"  {before} masked cells -> {int(stacked.max())} substantial pieces "
        f"(slivers below {SLIVER_FRACTION:.0%} of their own cell go back to the fill)")

    # The "drawn versus tessellated" measure: land carrying a traced, substantial
    # source cell at this point in the pipeline, before any fallback seeding or
    # nearest-label fill invents boundary the sources never drew. Approximate in
    # one direction: split_large can still cut a *synthetic* border through a
    # traced cell's interior later if it comes out oversized, so this is an
    # upper bound on truly-drawn area, not an exact one — reported as such in
    # COVERAGE.md rather than overclaimed.
    traced_land_px = int((stacked > 0)[land].sum())
    stats["traced_land_fraction"] = round(traced_land_px / float(land.sum()), 4)

    target = int(land.sum() // TARGET_LAND_STATES)
    stats["target_area"] = target
    stacked, uncovered_frac = seed_uncovered(stacked, land, target)
    stats["uncovered_land_fraction"] = round(uncovered_frac, 4)

    log("  filling to tile the mask...")
    stacked = cells.fill_nearest(stacked, land, WRAP_X, pad=256)
    stacked[~land] = 0
    stacked = cells.split_disconnected(stacked, WRAP_X)
    log(f"  {int(stacked.max())} cells after fill")

    # Per-region merge floors: cells inside an Old World crop footprint reconcile
    # to a much finer floor than the vanilla-sized rest of the map, and an
    # ink-traced macro (province noise to coalesce) uses a coarser floor than a
    # macro whose borders the user hand-drew as clean states (nothing to reconcile
    # — preserve them). A cell outside every footprint keeps the vanilla floor.
    floor_map = np.zeros(land.shape, dtype=np.int32)
    ow_floor = int(target * OLD_WORLD_MIN_AREA_FRACTION)
    ow_marker_floor = int(target * OLD_WORLD_MARKER_MIN_AREA_FRACTION)
    for name, mask in crop_footprints.items():
        kind = _normalize_source_spec(BOUNDARY_SOURCES[name])[0]
        floor_map[mask] = ow_marker_floor if kind == "marker_lines" else ow_floor
    stats["old_world_floor"] = ow_floor
    stats["old_world_marker_floor"] = ow_marker_floor
    log(f"  Old World footprint {100 * (floor_map > 0).mean():.1f}% of canvas; "
        f"floors ink {ow_floor:,} / marker {ow_marker_floor:,} px "
        f"(vs {int(target * MIN_AREA_FRACTION):,} elsewhere)")

    log("  reconciling density...")
    # Merge first, split second. The other order splits a large cell into pieces
    # that the merge pass then puts straight back together. The Old World keeps its
    # per-region floor throughout via floor_map.
    stacked = cells.merge_to_target(stacked, MERGE_TARGET_LAND_STATES, WRAP_X,
                                    log=log, floor_map=floor_map)
    stacked = cells.split_large(stacked, int(target * MAX_AREA_FRACTION), target, WRAP_X)
    stacked = cells.merge_small(stacked, int(target * MIN_AREA_FRACTION), WRAP_X,
                                floor_map=floor_map)
    # Absolute-floor cleanup, iterated to a joint fixpoint: absorb any sub-floor
    # rubble into a neighbour (merge_small), then split torn cells into connected
    # pieces (split_disconnected). The loop ends only in a round where *neither*
    # step changes anything — at which point no sub-floor cell still has a same-kind
    # neighbour to merge into AND every cell is connected, which is exactly the pair
    # of conditions validate_map --labels checks. Ending on either step alone trades
    # one violation for the other, so both must be no-ops in the same round.
    for _ in range(20):
        a = int(stacked.max())
        stacked = cells.merge_small(stacked, MIN_CELL_AREA, WRAP_X)
        b = int(stacked.max())
        stacked = cells.split_disconnected(stacked, WRAP_X)
        if a == b == int(stacked.max()):
            break
    log(f"  {int(stacked.max())} land cells (target {TARGET_LAND_STATES})")

    if int((stacked == 0)[land].sum()):
        raise SystemExit("land pixels left unlabelled — the layer does not tile the mask")
    return stacked, stats, crop_footprints


def assign_macros(land_labels: np.ndarray, regs: dict[str, schema.SourceRegistration]
                  ) -> tuple[np.ndarray, dict]:
    """Group land cells into macro regions from the annotated twin.

    Degrades to "no macro grouping" (every cell reports macro 0, the existing
    "outside every macro region" sentinel — see ``macro.assign``) rather than
    aborting the whole run when no *frame-aligned* twin is available.

    The pixel-difference path (:func:`macro.annotation_mask`) differences the twin
    against the clean master pixel-for-pixel, so it needs a twin in the master's
    own frame (matching dims). The only macro source currently registered is
    ``named_macro_regions`` (``tww3_states_per_strat_region.jpg``), a rescaled
    ``frame_alias`` of the master — it cannot feed that path, and re-tooling
    ``macro.py`` to warp the alias into the master frame is a separate request.
    That is the accurate diagnosis this reports; the Old World per-crop counts
    above stand in for the macros this round.
    """
    twin_reg = next((r for r in regs.values()
                     if r.role == "ie_macro_grouping" and not r.is_alias), None)
    if twin_reg is None:
        macro_src = next((r for r in regs.values() if r.role == "named_macro_regions"), None)
        if macro_src is not None and macro_src.is_alias:
            reason = (
                f"the only macro source ({macro_src.source}, role 'named_macro_regions') "
                f"is a frame_alias of {macro_src.frame_alias.of} "
                f"(scale {macro_src.frame_alias.scale[0]:.3f}), not a frame-aligned twin. "
                "macro.annotation_mask differences the twin against the clean master "
                "pixel-for-pixel and needs matching dims, so a rescaled alias cannot feed "
                "it. Warping the alias into the master frame is a separate request."
            )
        elif macro_src is not None:
            reason = (
                f"the macro source {macro_src.source} (role 'named_macro_regions') is "
                "registered but not in the master frame the pixel-difference path needs."
            )
        else:
            reason = (
                "no source carries a macro-grouping role (neither a frame-aligned "
                "'ie_macro_grouping' twin nor 'named_macro_regions')."
            )
        log(f"  WARNING: macro grouping SKIPPED — {reason} Every cell reports macro 0.")
        table = np.zeros(int(land_labels.max()) + 1, dtype=np.int32)
        return table, {"macro_regions": 0, "macro_declared": len(macro.PRINTED_COUNTS),
                       "macro_filled_from_neighbour": 0, "macro_degraded": False,
                       "macro_skipped": True, "macro_skip_reason": reason}
    twin = sources.load_source_image(twin_reg.source)

    # Preferred path: difference the twin against the clean master, which cancels
    # everything present in both (notably the coats of arms) and leaves exactly
    # what the annotator drew. Falls back to a saturation threshold on the twin
    # alone when the master is not available, which is measurably worse — see
    # macro.contours_from_twin.
    degraded = False
    try:
        ann = macro.annotation_mask(twin, sources.load_source_image(MACRO_CLEAN_MASTER))
    except (sources.ManifestError, FileNotFoundError) as exc:
        log(f"  WARNING: clean master unavailable ({exc})")
        ann, degraded = macro.contours_from_twin(twin), True

    regions, n = macro.regions_from_contours(ann)
    declared = len(macro.PRINTED_COUNTS)
    log(f"  {n} macro contours recovered (twin declares {declared})")
    if degraded:
        log("  WARNING: macro grouping ran WITHOUT the clean master — regions that "
            "failed to close have merged into neighbours, so some states are "
            "grouped into the wrong macro. Restore the master and regenerate.")
    elif n != declared:
        # With the master available this is a hard failure: silently producing two
        # Empires (or none) would not surface until S3b built strategic regions.
        raise SystemExit(
            f"macro grouping recovered {n} regions but the annotated twin labels "
            f"{declared} — re-tune worldgen/macro.py rather than proceeding"
        )

    warped, _ = cells.warp_cells(twin_reg, regs, regions.astype(np.int32), land_labels.shape)
    table = macro.assign(land_labels, warped)
    unassigned = int((table[1:] == 0).sum())
    table = macro.fill_missing(table, land_labels, WRAP_X)
    log(f"  {unassigned} cells took their macro from a neighbour")
    return table, {"macro_regions": n, "macro_declared": len(macro.PRINTED_COUNTS),
                   "macro_filled_from_neighbour": unassigned,
                   "macro_degraded": degraded}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--preview", action="store_true", help="also write a downscaled preview PNG")
    args = p.parse_args(argv)

    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first")

    errors = sources.verify()
    if errors:
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit("source manifest verification failed — refusing to generate")

    t_start = time.time()
    land = raster.read_mask_png(MASK_PATH)
    log(f"land mask     {land.shape} land {100 * land.mean():.2f}% ({int(land.sum()):,} px)")
    regs = {r.source: r for r in schema.load_registrations(sources.REGISTRATION_DIR)}

    land_labels, stats, crop_footprints = build_land_cells(land, regs)
    n_land = int(land_labels.max())

    log("macro grouping:")
    macro_of, macro_stats = assign_macros(land_labels, regs)
    stats.update(macro_stats)

    log("sea zones:")
    sea = cells.sea_zones(~land, TARGET_SEA_ZONES, WRAP_X)
    n_sea = int(sea.max())
    log(f"  {n_sea} sea zones (target {TARGET_SEA_ZONES})")

    labels = land_labels.copy()
    labels[~land] = sea[~land] + n_land
    if int((labels == 0).sum()):
        raise SystemExit("the label layer has unlabelled pixels")

    coastal = cells.coastal_labels(land_labels, land, WRAP_X)
    areas = np.bincount(labels.ravel(), minlength=n_land + n_sea + 1)

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    cells.write_labels(LABELS_PATH, labels)
    log(f"wrote {LABELS_PATH.relative_to(TOOLS_DIR.parent)}  "
        f"({n_land} land + {n_sea} sea = {n_land + n_sea} cells)")

    index = {
        "canvas": [CANVAS_W, CANVAS_H],
        "land_cells": n_land,
        "sea_cells": n_sea,
        "target_land_states": TARGET_LAND_STATES,
        "target_sea_zones": TARGET_SEA_ZONES,
        "target_area": stats["target_area"],
        "cells": [
            {
                "label": i,
                "kind": "land" if i <= n_land else "sea",
                "key": (f"STATE_MACRO{macro_of[i]:02d}_{i:04d}" if i <= n_land
                        else f"STATE_SEA_{i - n_land:04d}"),
                "macro": int(macro_of[i]) if i <= n_land else 0,
                "area": int(areas[i]),
                "coastal": bool(coastal[i]) if i <= n_land else True,
            }
            for i in range(1, n_land + n_sea + 1)
        ],
    }
    INDEX_PATH.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    log(f"wrote {INDEX_PATH.relative_to(TOOLS_DIR.parent)}")

    COVERAGE_PATH.write_text(
        render_coverage(stats, macro_of, areas, n_land, n_sea, land_labels, crop_footprints),
        encoding="utf-8")
    log(f"wrote {COVERAGE_PATH.relative_to(TOOLS_DIR.parent)}")

    if args.preview:
        write_preview(labels, land, n_land)
    log(f"done in {time.time() - t_start:.0f}s")
    return 0


def old_world_crop_counts(land_labels: np.ndarray, n_land: int,
                          crop_footprints: dict[str, np.ndarray]) -> dict[str, int]:
    """Land cells whose majority area falls inside each crop's warped footprint.

    Majority-by-area (not centroid) so a cell straddling a footprint edge is
    attributed to whichever crop holds most of it, and — the footprints being
    alpha-disjoint — to at most one. This is the density measurement the request
    is judged on, taken directly from the crop footprints because the annotated
    twin's macro grouping is blocked (see :func:`assign_macros`).
    """
    total = np.bincount(land_labels.ravel(), minlength=n_land + 1)
    counts: dict[str, int] = {}
    for name, mask in crop_footprints.items():
        inside = np.bincount(land_labels[mask].ravel(), minlength=n_land + 1)
        majority = inside[1:n_land + 1] * 2 > total[1:n_land + 1]
        counts[name] = int(majority.sum())
    return counts


def render_coverage(stats: dict, macro_of: np.ndarray, areas: np.ndarray,
                    n_land: int, n_sea: int, land_labels: np.ndarray,
                    crop_footprints: dict[str, np.ndarray]) -> str:
    """The honest report: where the sources reach, and where they do not."""
    land_areas = areas[1:n_land + 1]
    target = stats["target_area"]
    lines = [
        "# State-label coverage (S3a)",
        "",
        "Generated by `tools/generate_state_labels.py`. **Do not hand-edit** —",
        "regenerate. This is the report user decision #6 asks for: where the",
        "boundary sources reached vanilla-order density, and where a new source",
        "would help rather than the build silently coarsening.",
        "",
        "## Density",
        "",
        f"- Target: **{TARGET_LAND_STATES} land states** (vanilla's own count) at a mean",
        f"  of **{target:,} canvas px** each, plus **{TARGET_SEA_ZONES} sea zones**.",
        f"- Achieved: **{n_land} land cells** (mean {int(land_areas.mean()):,} px, "
        f"median {int(np.median(land_areas)):,} px, "
        f"min {int(land_areas.min()):,}, max {int(land_areas.max()):,}) "
        f"and **{n_sea} sea zones**.",
        f"- Cells traced from a source before filling: **{stats['source_cells']:,}**.",
        "",
    ]
    if "traced_cells_before_bridge" in stats:
        lines += [
            "## Lettering bridge (the parchment master)",
            "",
            f"- Traced cells before bridging detected labels into the barrier: "
            f"**{stats['traced_cells_before_bridge']:,}**.",
            f"- After: **{stats['traced_cells_after_bridge']:,}** "
            f"({100 * (stats['traced_cells_after_bridge'] / max(1, stats['traced_cells_before_bridge']) - 1):+.1f}%) "
            "— this is the measurement that says whether the glyph detector earned its "
            "dependency.",
            f"- Largest traced cell after bridging: **{stats['largest_traced_cell_px']:,} px** "
            "(source pixels, before warping onto the canvas or clipping to the mask). A "
            "faint or broken ruled line, not a text problem — recoverable by `split_large`, "
            "reported here rather than hidden.",
            "",
        ]
    if "ie_footprint_land_coverage" in stats:
        lines += [
            f"- Within the parchment master's own footprint, "
            f"**{100 * stats['ie_footprint_land_coverage']:.1f}%** of land carries a traced "
            "cell (the rest falls through to the mask-wide seeded fallback below, same as "
            "everywhere else).",
            "",
        ]
    lines += [
        f"- **Drawn versus tessellated**: **{100 * stats['traced_land_fraction']:.1f}%** of "
        "final land area belongs to a cell that carries a traced source boundary "
        "(an upper bound — `split_large` can still cut a synthetic border through a "
        "traced cell's interior if it comes out oversized, so the true drawn share is "
        "this number or lower, never higher). The rest is seeded fallback or "
        "nearest-label fill: tessellated, not drawn.",
        "",
    ]

    # The Old World macros this request is judged on. Counted straight from each
    # crop's warped alpha>0 footprint, because the annotated-twin macro grouping is
    # blocked (see the Macro grouping section below) — the crops ARE these macros.
    counts = old_world_crop_counts(land_labels, n_land, crop_footprints)
    lines += [
        "## Old World density (this request's gate)",
        "",
        "Land cells whose majority area lands inside each Old World crop's warped",
        "`alpha>0` footprint, against the user's per-macro `min_states` "
        "(`tools/regions/named_regions.json`). The crop footprints are the macros",
        "here because the twin grouping is blocked (below).",
        "",
    ]
    if counts:
        for name, (label, minimum) in OLD_WORLD_CROP_MIN_STATES.items():
            got = counts.get(name)
            if got is None:
                lines.append(f"- **{label}**: crop not warped (no footprint) — investigate.")
                continue
            ok = "✅" if got >= minimum else "⚠ SHORT"
            lines.append(f"- **{label}**: {got} cells (min {minimum}) {ok}")
        short = [OLD_WORLD_CROP_MIN_STATES[n][0] for n, c in counts.items()
                 if c < OLD_WORLD_CROP_MIN_STATES[n][1]]
        if short:
            lines += [
                "",
                f"⚠ Below minimum: {', '.join(short)}. Either the crop's boundary lines "
                "are under-tracing (tune its ink params) or the source genuinely draws "
                "fewer regions there than required — named honestly here rather than "
                "merged up to hit a number.",
            ]
    else:
        lines.append("- No Old World crop footprints reached the canvas — check the registrations.")
    lines += [
        "",
        "## Source coverage",
        "",
        "Boundary sources, highest precedence first — the area a layer *offers*, not",
        "the area it wins:",
        "",
    ]
    lines += ["```"] + stats["precedence"] + ["```", ""]
    frac = stats["uncovered_land_fraction"]
    lines += [
        "## The gap",
        "",
        f"**{100 * frac:.1f}% of land has no boundary source at all** and is partitioned by",
        "seeded fallback cells at the target density. This is expected, not a defect:",
        "the Immortal Empires frame stops around Cathay, so the Kingdoms of Ind,",
        "Khuresh, Nippon, the far Eastern Steppes and the polar Chaos Wastes have no",
        "registered source. Their cells are the right *size* and tile the mask",
        "correctly; they are simply not tracing anything.",
        "",
        "Named candidates for closing it, in order of expected value:",
        "",
        "1. **The Old World mod parchment crops** (`tww3_old_world_mod_parchment_*`)",
        "   are now wired in — see the Old World density section above. They raise",
        "   density inside their own footprints rather than closing this gap, which is",
        "   the whole east/polar coverage hole, not the Old World.",
        "2. **A boundary source for Ind / Khuresh / Nippon.** Nothing in `sources/`",
        "   draws provinces there. This is the real gap and no reprocessing of the",
        "   current set will close it.",
        "3. **A polar source.** The Chaos Wastes fringe is inherently vague, and the",
        "   hybrid-fringe rule means much of it becomes `impassable` anyway — lowest",
        "   value of the three.",
        "",
        "## Macro grouping",
        "",
    ] + (
        [
            "- **⚠ SKIPPED — macro grouping did not run.**",
            f"  {stats.get('macro_skip_reason', '')}",
            "  Every land cell reports macro 0 (unassigned) below; the Old World per-crop",
            "  counts above stand in for the macros this round.",
            "",
        ] if stats.get("macro_skipped") else
        [
            f"- {stats['macro_regions']} contours recovered from the annotated twin "
            f"(it prints {stats['macro_declared']} region labels).",
        ] + ([
            "- **⚠ DEGRADED: the clean master was unavailable**, so the contours came from a",
            "  saturation threshold on the twin alone rather than from differencing the two.",
            "  Regions that failed to close have merged into neighbours, which means some",
            "  states are grouped into the wrong macro — silently. Restore",
            "  `tww3_ie_parchment.jpg` to `sources/` and regenerate.",
        ] if stats.get("macro_degraded") else [])
    ) + [
        f"- {stats['macro_filled_from_neighbour']} cells fell outside every contour and took "
        "their macro from the nearest neighbour — these are mostly the uncovered regions above.",
        "",
    ]
    lines += macro.count_report(macro_of) + [""]
    return "\n".join(lines)


def write_preview(labels: np.ndarray, land: np.ndarray, n_land: int, step: int = 8) -> None:
    """A downscaled false-colour PNG — cheap to open, enough to spot a tear."""
    small = labels[::step, ::step]
    sland = land[::step, ::step]
    rng = np.random.default_rng(map_config.SEED)  # seeded: the preview is reproducible
    palette = rng.integers(60, 250, size=(int(labels.max()) + 1, 3), dtype=np.uint8)
    img = palette[small]
    img[~sland] = (img[~sland] // 3 + np.array([0, 0, 60], dtype=np.uint8))
    out = DERIVED_DIR / "preview_state_labels.png"
    raster.write_rgb_png(out, img)
    log(f"wrote {out.relative_to(TOOLS_DIR.parent)}")


if __name__ == "__main__":
    raise SystemExit(main())
