#!/usr/bin/env python3
"""Diagnostic: where does the actual generation source miss a border the
user already drew in ``old_world_state_regions.png``?

Board #2930 follow-up (2026-09-05). Chris flagged several regions that read
as merged on the land-regions preview render but are "clearly outlined" in
``sources/gimp_exports/old_world_state_regions.png`` — the hand-painted
master-frame layer used for #2709's QA drape (a per-state fill + a magenta
``255,0,255`` border network), a *different* file from the one
``generate_provinces.py`` actually reads for province generation
(``sources/terraqueous_globe_reprojected - state_regions.png``). Both are the
user's own hand-drawn political borders for the same map, just traced onto
two different frames — so a line present in one and absent from the other is
a transcription gap, not a new creative decision, and can be found
mechanically:

1. Warp ``old_world_state_regions.png``'s magenta network onto the canvas via
   the existing five-crop registration (``project_regions.py``, reused
   wholesale — same warp #2709's QA drape uses).
2. Read the magenta network already in the actual generation source
   (``worldgen.land_provinces.magenta_lines``).
3. A canvas pixel is a **gap** when the warped painting says "border here"
   and the generation source, dilated by a few px to absorb warp/registration
   jitter, says "no border here" — restricted to land (a gap over water or
   outside the five crops' coverage is meaningless).

Writes a full-canvas overlay (gaps in bright red over the tinted region
render) + a half-size copy + a CSV of gap components (connected blobs, sorted
by size) with a canvas-pixel centroid each, so a human can navigate to every
one systematically instead of finding them by eye one at a time.

This never edits any source or generated file — pure read-only diagnostic,
local-only output under ``tools/derived/`` (gitignored).

Usage::

    python tools/diff_state_borders.py
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
import project_regions as pr  # noqa: E402 — reuses its five-crop registration + drape
from worldgen import land_provinces, raster, schema  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
STATE_REGIONS_SOURCE = "terraqueous_globe_reprojected - state_regions.png"
PAINTING_SOURCE = "old_world_state_regions.png"

OUT_PATH = DERIVED_DIR / "state_border_gaps.png"
OUT_HALF_PATH = DERIVED_DIR / "state_border_gaps_half.png"
CSV_PATH = DERIVED_DIR / "state_border_gaps.csv"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: Dilate the generation source's own magenta this many px before checking
#: absence — absorbs sub-pixel warp/registration jitter between the two
#: frames so a genuinely-matching line never false-positives as a gap.
TOLERANCE_PX = 3
#: Drop gap components smaller than this many px (paint flecks, anti-aliasing
#: specks) — a real missing border segment is much bigger.
MIN_GAP_AREA = 40
GAP_RGB = (255, 0, 0)


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


def _painting_magenta_on_canvas(t0: float) -> np.ndarray:
    """The painting's magenta network warped onto canvas space (boolean), via
    the same five-crop registration ``project_regions.py`` already uses."""
    regs = {r.source: r for r in schema.load_registrations(pr.REGISTRATION_DIR)}
    for name in pr.FIVE_CROPS:
        if name not in regs:
            raise SystemExit(f"{name}: no committed registration record")

    master_rgb = pr.load_rgb(pr.MASTER_SOURCE)
    paint_rgba = pr.load_rgba(PAINTING_SOURCE)
    if master_rgb.shape[:2] != paint_rgba.shape[:2]:
        raise SystemExit(f"{PAINTING_SOURCE} does not share the master frame")
    crop_rgba = {name: pr.load_or_derive_rgba(name) for name in pr.FIVE_CROPS}
    globe_rgb = pr.load_rgb(pr.GLOBE_SOURCE)

    master_gray = master_rgb.astype(np.float32).mean(axis=2)
    offsets = pr.crop_offsets(master_gray, crop_rgba)
    log("five parchment crops located", t0)
    owner = pr.canvas_owner(regs, crop_rgba, offsets, paint_rgba)
    # order=0 (nearest): the painting's magenta must stay pure, unblurred.
    canvas_rgb, placed = pr.place_painting(0, regs, paint_rgba, crop_rgba, offsets, globe_rgb, owner)
    log(f"painting warped onto canvas ({100.0 * placed.mean():.2f}% of frame)", t0)

    magenta = land_provinces.magenta_lines(canvas_rgb) & placed
    return magenta


def main(argv: list[str] | None = None) -> int:
    t0 = time.time()
    for path in (MASK_PATH,):
        if not path.is_file():
            raise SystemExit(f"{path} not found — run the map generator pipeline first")

    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}, got {land.shape[1]}x{land.shape[0]}")

    painted_magenta = _painting_magenta_on_canvas(t0)

    current_rgb = pr.load_rgb(STATE_REGIONS_SOURCE)
    if current_rgb.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{STATE_REGIONS_SOURCE}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{current_rgb.shape[1]}x{current_rgb.shape[0]}")
    current_magenta = land_provinces.magenta_lines(current_rgb)
    current_magenta_tol = ndimage.binary_dilation(current_magenta, iterations=TOLERANCE_PX)
    log(f"generation source magenta: {int(current_magenta.sum()):,} px "
        f"(painting magenta: {int(painted_magenta.sum()):,} px)", t0)

    gap = painted_magenta & ~current_magenta_tol & land
    log(f"raw gap: {int(gap.sum()):,} px before small-component filtering", t0)

    comp, n = ndimage.label(gap, structure=ndimage.generate_binary_structure(2, 2))
    sizes = ndimage.sum(gap, comp, range(1, n + 1))
    keep = np.zeros(n + 1, dtype=bool)
    keep[1:] = sizes >= MIN_GAP_AREA
    gap_clean = keep[comp]
    n_kept = int(keep[1:].sum())
    log(f"gap components: {n} raw, {n_kept} kept (>= {MIN_GAP_AREA} px)", t0)

    # --- CSV of components: id, area, canvas centroid, bbox ----------------
    comp_clean, n_clean = ndimage.label(gap_clean, structure=ndimage.generate_binary_structure(2, 2))
    rows = []
    objs = ndimage.find_objects(comp_clean)
    for i, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        mask_i = comp_clean[sl] == i
        area = int(mask_i.sum())
        ys, xs = np.nonzero(comp_clean == i)
        cx, cy = int(round(xs.mean())), int(round(ys.mean()))
        rows.append({
            "gap_id": i,
            "area_px": area,
            "centroid_x": cx,
            "centroid_y": cy,
            "bbox_x0": sl[1].start, "bbox_y0": sl[0].start,
            "bbox_x1": sl[1].stop, "bbox_y1": sl[0].stop,
        })
    rows.sort(key=lambda r: -r["area_px"])
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    if rows:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {CSV_PATH}  ({len(rows)} gap component(s), sorted by area descending)")
    else:
        print("no gap components found — nothing to write to CSV")

    # --- render: gaps in bright red over the actual generation source ------
    base = current_rgb.copy()
    base[land_provinces.magenta_lines(current_rgb)] = (255, 0, 255)
    dilated_gap = ndimage.binary_dilation(gap_clean, iterations=1)  # a touch thicker, easier to see
    out = base.copy()
    out[dilated_gap] = GAP_RGB
    raster.write_rgb_png(OUT_PATH, out)
    print(f"wrote {OUT_PATH}")
    Image.fromarray(out, "RGB").resize((CANVAS_W // 2, CANVAS_H // 2), resample=Image.LANCZOS).save(
        OUT_HALF_PATH, format="PNG", optimize=False, compress_level=6)
    print(f"wrote {OUT_HALF_PATH}  ({CANVAS_W // 2}x{CANVAS_H // 2})")

    log(f"done: {n_kept} gap component(s), {int(gap_clean.sum()):,} px total", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
