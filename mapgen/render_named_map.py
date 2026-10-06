#!/usr/bin/env python3
"""S3a review renders: project the committed state-label layer for a human look.

Two artifacts, two different jobs (world-map-parchment-areas-onto-globe.md):

``--globe``
    **Local-only.** A copy of ``terraqueous_globe.jpg`` at its native
    4000x3256, with the committed ``state_labels.png`` cell network projected
    onto it and outlined. The mapping is the same *forward* fit every other
    source's control points are anchored through
    (``reproject.fit_parametric(terraqueous_globe.jpg)``): walk the globe's own
    pixels, push each one to its canvas position, and sample the label layer
    there — no inverse projection has to be derived. Written under
    ``mapgen/derived/``, which ``mapgen/.gitignore`` excludes by default; it
    embeds the source image itself, so it is not committed.

``--tiles``
    **Committed.** Flat macro-tinted cells plus a 1-canvas-px coastline, drawn
    from our own pixels only — no source art. One PNG per macro region at its
    own canvas bounding box (long side capped, nearest-scaled so a small region
    stays legible), plus ``index.png``, one whole-world sheet. Text labelling
    is Stage B's job (the names file does not exist yet); Stage A's cells are
    reviewed unnamed, by shape and macro grouping alone.

Usage::

    python mapgen/render_named_map.py --globe
    python mapgen/render_named_map.py --tiles
    python mapgen/render_named_map.py --globe --tiles
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import canvas_frame, map_config  # noqa: E402
from worldgen import cells, raster, reproject, schema, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
DERIVED_DIR = TOOLS_DIR / "derived"
NAMED_DIR = DERIVED_DIR / "named"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
LABELS_PATH = DERIVED_DIR / "state_labels.png"
INDEX_PATH = DERIVED_DIR / "state_labels_index.json"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
GLOBE_SOURCE = "terraqueous_globe.jpg"

#: A high-separation hue wheel, one entry per macro (cycled if there are more
#: macros than entries — matches the palette qa_overlay.py already uses, so the
#: two renders read consistently).
MACRO_HUES = np.array([
    (214, 64, 64), (64, 150, 214), (110, 190, 90), (222, 168, 60),
    (168, 104, 200), (86, 196, 190), (226, 120, 170), (150, 150, 96),
    (96, 128, 214), (200, 96, 60), (120, 200, 140), (190, 190, 214),
    (150, 96, 96), (96, 170, 120), (214, 140, 96), (130, 130, 170),
], dtype=np.uint8)

#: Long side cap for a per-macro tile — legible without being unwieldy to open.
TILE_MAX_SIDE = 2400
#: Whole-world index sheet downscale.
INDEX_STEP = 2

COAST_RGB = (0, 0, 0)


def _load_index() -> dict:
    if not INDEX_PATH.is_file():
        raise SystemExit(f"{INDEX_PATH} not found — run mapgen/generate_state_labels.py first")
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _cell_shade(cell_id: np.ndarray) -> np.ndarray:
    """Deterministic per-cell brightness factor in [0.7, 1.15], from a fixed hash.

    Not randomness (see ``.claude/rules/core.md``) — a pure function of the cell
    id, so two cells sharing a macro's hue are still visually distinguishable
    and re-running the render reproduces the same pixels.
    """
    h = (cell_id.astype(np.uint64) * np.uint64(2654435761)) & np.uint64(0xFFFF)
    return 0.7 + 0.45 * (h.astype(np.float64) / 0xFFFF)


def _tint(labels: np.ndarray, land: np.ndarray, macro_of: np.ndarray) -> np.ndarray:
    """Flat macro-tinted RGB, one shade per cell, black sea."""
    img = np.zeros(labels.shape + (3,), dtype=np.uint8)
    hue = MACRO_HUES[macro_of[labels] % len(MACRO_HUES)].astype(np.float64)
    shade = _cell_shade(labels)[..., None]
    tinted = np.clip(hue * shade, 0, 255).astype(np.uint8)
    img[land] = tinted[land]
    img[~land] = (18, 26, 44)
    return img


def _outline(img: np.ndarray, labels: np.ndarray, land: np.ndarray) -> None:
    """Draw 1-px cell borders and a 1-px coastline, in place."""
    edge = np.zeros(labels.shape, dtype=bool)
    edge[:, :-1] |= labels[:, :-1] != labels[:, 1:]
    edge[:-1, :] |= labels[:-1, :] != labels[1:, :]
    img[edge] = (img[edge] * 0.3).astype(np.uint8)
    coast = land ^ ndimage.binary_erosion(land, np.ones((3, 3), dtype=bool))
    img[coast] = COAST_RGB


def _fit_long_side(img: np.ndarray, max_side: int) -> np.ndarray:
    """Nearest-scale so the long side is exactly ``max_side`` — up or down."""
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    if abs(scale - 1.0) < 1e-9:
        return img
    nh, nw = max(1, round(h * scale)), max(1, round(w * scale))
    return np.asarray(
        Image.fromarray(img, mode="RGB").resize((nw, nh), resample=Image.NEAREST),
        dtype=np.uint8,
    )


def render_globe_composite() -> Path:
    """The local-only globe-space review render."""
    regs = {r.source: r for r in schema.load_registrations(sources.REGISTRATION_DIR)}
    globe_reg = regs.get(GLOBE_SOURCE)
    if globe_reg is None:
        raise SystemExit(f"{GLOBE_SOURCE} has no registration record")
    fit = reproject.fit_parametric(globe_reg)

    globe_rgb = sources.load_source_image(GLOBE_SOURCE)
    gh, gw = globe_rgb.shape[:2]
    labels = cells.read_labels(LABELS_PATH)

    # Blank paper margin outside the globe's own drawn oval maps through the
    # projection just like everywhere else, landing on whatever seeded
    # fallback cell sits nearest the frame edge on the canvas — and those are
    # small and densely packed, so the margin fills with meaningless outline
    # noise unless it is masked out first.
    o = canvas_frame.TERRAQUEOUS_OVAL
    ocx, ocy = (o["left"] + o["right"]) / 2, (o["top"] + o["bottom"]) / 2
    orx, ory = (o["right"] - o["left"]) / 2, (o["bottom"] - o["top"]) / 2

    out_labels = np.zeros((gh, gw), dtype=np.int32)
    in_oval = np.zeros((gh, gw), dtype=bool)
    block = 256
    for r0 in range(0, gh, block):
        r1 = min(gh, r0 + block)
        gy, gx = np.mgrid[r0:r1, 0:gw].astype(np.float64)
        in_oval[r0:r1] = (((gx - ocx) / orx) ** 2 + ((gy - ocy) / ory) ** 2) <= 1.0
        cx, cy = fit.to_canvas(gx, gy, CANVAS_W, CANVAS_H)
        ix = np.clip(np.rint(cx), 0, CANVAS_W - 1).astype(np.int64)
        iy = np.clip(np.rint(cy), 0, CANVAS_H - 1).astype(np.int64)
        out_labels[r0:r1] = labels[iy, ix]

    edge = np.zeros((gh, gw), dtype=bool)
    edge[:, :-1] |= (out_labels[:, :-1] != out_labels[:, 1:]) & in_oval[:, :-1] & in_oval[:, 1:]
    edge[:-1, :] |= (out_labels[:-1, :] != out_labels[1:, :]) & in_oval[:-1, :] & in_oval[1:, :]

    img = globe_rgb.copy()
    img[edge] = (255, 0, 255)

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out = DERIVED_DIR / "globe_named_review.png"
    raster.write_rgb_png(out, img)
    print(f"wrote {out} (local-only — {gw}x{gh}, {int(edge.sum()):,} outline px)")
    return out


def render_tiles() -> list[Path]:
    """The committed, own-pixels-only macro tiles + whole-world index sheet."""
    index = _load_index()
    n_land = int(index["land_cells"])
    labels = cells.read_labels(LABELS_PATH)
    land = raster.read_mask_png(MASK_PATH)

    macro_of = np.zeros(int(labels.max()) + 1, dtype=np.int32)
    for c in index["cells"]:
        if c["kind"] == "land":
            macro_of[c["label"]] = c["macro"]

    NAMED_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    macros = sorted({int(c["macro"]) for c in index["cells"]
                     if c["kind"] == "land" and c["macro"] > 0})
    for m in macros:
        cell_ids = {c["label"] for c in index["cells"] if c["kind"] == "land" and c["macro"] == m}
        member = np.isin(labels, list(cell_ids)) & land
        if not member.any():
            continue

        # A macro can straddle the x=0/x=W-1 seam (the canvas is periodic in
        # longitude — see map_config.WRAP_X). A plain min/max bbox on such a
        # macro spans the whole canvas width, mostly empty, which is exactly
        # the "not legible" failure this render exists to avoid. Detect it the
        # same way cells.split_large does — occupancy at both edges with a gap
        # between — and roll the macro contiguous before cropping.
        cols = np.flatnonzero(member.any(axis=0))
        shift = 0
        if cols[0] == 0 and cols[-1] == member.shape[1] - 1 and len(cols) < member.shape[1]:
            gap = np.flatnonzero(np.diff(cols) > 1)
            if gap.size:
                shift = member.shape[1] - int(cols[gap[0] + 1])
        if shift:
            member = np.roll(member, shift, axis=1)
            roll_labels = np.roll(labels, shift, axis=1)
            roll_land = np.roll(land, shift, axis=1)
        else:
            roll_labels, roll_land = labels, land

        ys, xs = np.nonzero(member)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        sub_labels = roll_labels[y0:y1, x0:x1]
        sub_land = roll_land[y0:y1, x0:x1]
        img = _tint(sub_labels, sub_land, macro_of)
        _outline(img, sub_labels, sub_land)
        img = _fit_long_side(img, TILE_MAX_SIDE)
        out = NAMED_DIR / f"macro_{m:02d}.png"
        raster.write_rgb_png(out, img)
        written.append(out)
        print(f"wrote {out} ({len(cell_ids)} cells, native {x1 - x0}x{y1 - y0})")

    small_labels = labels[::INDEX_STEP, ::INDEX_STEP]
    small_land = land[::INDEX_STEP, ::INDEX_STEP]
    img = _tint(small_labels, small_land, macro_of)
    _outline(img, small_labels, small_land)
    out = NAMED_DIR / "index.png"
    raster.write_rgb_png(out, img)
    written.append(out)
    print(f"wrote {out} (whole world at 1/{INDEX_STEP}, {n_land} land cells, "
         f"{len(macros)} macro regions)")
    return written


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--globe", action="store_true", help="local-only globe-space composite")
    p.add_argument("--tiles", action="store_true", help="committed per-macro tiles + index")
    args = p.parse_args(argv)

    if not args.globe and not args.tiles:
        p.error("pass --globe, --tiles, or both")

    if not LABELS_PATH.is_file():
        raise SystemExit(f"{LABELS_PATH} not found — run mapgen/generate_state_labels.py first")

    if args.globe:
        render_globe_composite()
    if args.tiles:
        render_tiles()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
