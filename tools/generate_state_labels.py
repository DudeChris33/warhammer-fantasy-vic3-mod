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

#: How far a cell may sit from the target before it is merged away or split up.
#: Deliberately loose: real states vary hugely in size, and forcing them towards
#: uniformity would erase the source's information, which is the whole point of
#: tracing rather than tessellating.
MIN_AREA_FRACTION = 0.35
MAX_AREA_FRACTION = 2.2

#: Clipping the source cells to our own coastline shaves a sliver off every
#: coastal one. A traced piece below this fraction of the target is treated as
#: that clipping artefact rather than as a state, and handed back to the fill —
#: see ``cells.drop_small`` for why dropping beats merging here.
FRAGMENT_FRACTION = 0.25

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
#: record with a boundary precedence": two S1 records (map-the-old-world.jpg,
#: TheEmpire.webp) still declare one, and both are measured to be misregistered
#: and are annotated as unusable for geometry. Naming the consumers here means
#: adding a source is a deliberate edit, not a side effect of a precedence.
BOUNDARY_SOURCES = (
    "Immortal-Empires-Map-Feature-Image-scaled.jpg",
    "wh3_dlc_ie_parchment_map_english.jpg",
)

#: Ink-threshold parameters for the parchment line networks.
INK_WINDOW = 41
INK_OFFSET = 12
#: Minimum enclosed area, in source px, for a traced cell to be kept.
MIN_SOURCE_CELL = 150


def log(msg: str) -> None:
    print(msg, flush=True)


def extract_source_cells(reg: schema.SourceRegistration) -> np.ndarray:
    """Trace one source's boundary network into a cell-label image."""
    rgb = sources.load_source_image(reg.source)
    ink = parchment.ink_mask(rgb, window=INK_WINDOW, offset=INK_OFFSET)
    lab, n = parchment.cells_from_ink(ink, MIN_SOURCE_CELL)
    log(f"  {reg.source:<48} ink {ink.mean():.3f}  cells {n}")
    return lab.astype(np.int32)


def build_layers(regs: dict[str, schema.SourceRegistration]
                 ) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Warp every boundary source onto the canvas and stack it by precedence."""
    layers: list[tuple[str, int, np.ndarray, np.ndarray]] = []
    covered = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
    report: list[str] = []
    for name in BOUNDARY_SOURCES:
        reg = regs.get(name)
        if reg is None:
            raise SystemExit(f"{name} has no registration record — run tools/fit_registration.py")
        src = extract_source_cells(reg)
        t0 = time.time()
        lab, inside = cells.warp_cells(reg, regs, src, (CANVAS_H, CANVAS_W))
        covered |= inside
        prec = reg.precedence_for(BOUNDARY_LAYER)
        layers.append((name, prec, lab, inside))
        report.append(f"  precedence {prec:>3}  {name:<48} covers {100 * inside.mean():5.1f}% of canvas")
        log(f"  warped {name} in {time.time() - t0:.0f}s "
            f"(covers {100 * inside.mean():.1f}% of canvas)")
    return cells.stack_layers(layers, (CANVAS_H, CANVAS_W)), covered, report


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
                     ) -> tuple[np.ndarray, dict]:
    stats: dict = {}
    log("tracing boundary sources:")
    stacked, covered, prec_report = build_layers(regs)
    stats["precedence"] = prec_report
    stats["source_cells"] = int(stacked.max())

    # The mask is the coastline authority: a source cell that spills into the sea
    # is clipped here and can never move a coast (user decision #1/#2).
    stacked[~land] = 0
    log(f"  {int((stacked > 0).sum()) / land.sum() * 100:.1f}% of land carries a source cell")

    # A rubber-sheeted warp can tear one source cell into pieces on opposite
    # sides of a strait; each piece has to become its own state.
    stacked = cells.split_disconnected(stacked, WRAP_X)

    target = int(land.sum() // TARGET_LAND_STATES)
    stats["target_area"] = target
    before = int(stacked.max())
    stacked = cells.drop_small(stacked, int(target * FRAGMENT_FRACTION))
    log(f"  dropped {before - len(np.unique(stacked)) + 1} coastal fragments below "
        f"{int(target * FRAGMENT_FRACTION):,} px back to the fill")

    stacked, uncovered_frac = seed_uncovered(stacked, land, target)
    stats["uncovered_land_fraction"] = round(uncovered_frac, 4)

    log("  filling to tile the mask...")
    stacked = cells.fill_nearest(stacked, land, WRAP_X, pad=256)
    stacked[~land] = 0
    stacked = cells.split_disconnected(stacked, WRAP_X)
    log(f"  {int(stacked.max())} cells after fill")

    log("  reconciling density...")
    # Merge first, split second. The other order splits a large cell into pieces
    # that the merge pass then puts straight back together.
    stacked = cells.merge_to_target(stacked, TARGET_LAND_STATES, WRAP_X, log=log)
    stacked = cells.split_large(stacked, int(target * MAX_AREA_FRACTION), target, WRAP_X)
    stacked = cells.merge_small(stacked, int(target * MIN_AREA_FRACTION), WRAP_X)
    # Splitting torn cells can strand a handful of pixels: a merge that chained
    # A -> B -> C leaves A's pixels next to C without touching it. Sweep those up
    # against an absolute floor, then re-split, so no state comes out smaller
    # than the smallest island the mask itself is allowed to keep.
    stacked = cells.split_disconnected(stacked, WRAP_X)
    stacked = cells.merge_small(stacked, MIN_CELL_AREA, WRAP_X)
    stacked = cells.split_disconnected(stacked, WRAP_X)
    log(f"  {int(stacked.max())} land cells (target {TARGET_LAND_STATES})")

    if int((stacked == 0)[land].sum()):
        raise SystemExit("land pixels left unlabelled — the layer does not tile the mask")
    return stacked, stats


def assign_macros(land_labels: np.ndarray, regs: dict[str, schema.SourceRegistration]
                  ) -> tuple[np.ndarray, dict]:
    """Group land cells into macro regions from the annotated twin."""
    twin_reg = next((r for r in regs.values() if r.role == "ie_macro_grouping"), None)
    master = next((r for r in regs.values() if r.role == "ie_boundary_frame_master"), None)
    if twin_reg is None or master is None:
        raise SystemExit("macro grouping needs the annotated twin and the frame master")
    twin = sources.load_source_image(twin_reg.source)
    clean = sources.load_source_image(master.source)
    ann = macro.annotation_mask(twin, clean)
    regions, n = macro.regions_from_contours(ann)
    declared = len(macro.PRINTED_COUNTS)
    log(f"  {n} macro contours recovered (twin declares {declared})")
    # A checked invariant, not a warning: silently producing two Empires (or
    # none) is the failure this grouping is most prone to, and it would not be
    # visible until strategic regions were generated from it in S3b.
    if n != declared:
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
                   "macro_filled_from_neighbour": unassigned}


def coastal_flags(labels: np.ndarray, land: np.ndarray) -> np.ndarray:
    """Which labels touch water (wrap-aware on x, not on y)."""
    sea = ~land
    nb = np.zeros_like(sea)
    nb |= np.roll(sea, 1, axis=1)
    nb |= np.roll(sea, -1, axis=1)
    nb[:-1] |= sea[1:]
    nb[1:] |= sea[:-1]
    touching = np.unique(labels[nb & land])
    out = np.zeros(int(labels.max()) + 1, dtype=bool)
    out[touching[touching > 0]] = True
    return out


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

    land_labels, stats = build_land_cells(land, regs)
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

    coastal = coastal_flags(land_labels, land)
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
        render_coverage(stats, macro_of, areas, n_land, n_sea), encoding="utf-8")
    log(f"wrote {COVERAGE_PATH.relative_to(TOOLS_DIR.parent)}")

    if args.preview:
        write_preview(labels, land, n_land)
    log(f"done in {time.time() - t_start:.0f}s")
    return 0


def render_coverage(stats: dict, macro_of: np.ndarray, areas: np.ndarray,
                    n_land: int, n_sea: int) -> str:
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
        "1. **`the-old-world-...-v3-0-...ml2lq3qfofad1.png`** (already in the manifest,",
        "   deliberately unregistered in S3a — see `tools/SOURCES.md`). A denser line",
        "   chloropleth over the Old World arc. It would raise density where we already",
        "   have coverage rather than close the gap, but it is the cheapest next step:",
        "   a viable measurable objective exists for it (its own cell network covers",
        "   only land, so the union of its small cells *is* a land silhouette that can",
        "   be scored the same way the IE family was).",
        "2. **A boundary source for Ind / Khuresh / Nippon.** Nothing in `sources/`",
        "   draws provinces there. This is the real gap and no reprocessing of the",
        "   current set will close it.",
        "3. **A polar source.** The Chaos Wastes fringe is inherently vague, and the",
        "   hybrid-fringe rule means much of it becomes `impassable` anyway — lowest",
        "   value of the three.",
        "",
        "## Macro grouping",
        "",
        f"- {stats['macro_regions']} contours recovered from the annotated twin "
        f"(it prints {stats['macro_declared']} region labels).",
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
