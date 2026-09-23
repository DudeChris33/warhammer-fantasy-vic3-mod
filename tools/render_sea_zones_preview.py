#!/usr/bin/env python3
"""Review render: the sea-zone partition on the reprojected globe.

Board #2593 / #2698. Two modes over the canvas-aligned reprojected globe
(``sources/terraqueous_globe_reprojected.png``, 8192x3616, overlays 1:1):

* **default** — the raw sea-zone division lines (re-extracted from
  ``worldgen.sea_zones.extract``). Magenta = zone boundaries, cyan = coast.
* **``--named``** (board #2698) — reads the *committed* ``sea_zones.png`` +
  ``sea_zones_index.json`` (not a re-extract, so it shows exactly what is
  committed), tints every zone by its Warhammer-canon **sea group**, and prints
  each group's display name once. This PNG is the loremaster + user visual gate.

Local-only output: it embeds the source globe pixels (like
``globe_named_review.png``), so it lands under ``tools/derived/``, which
``tools/.gitignore`` excludes from the repo. The committed artifacts are the label
layer + index from ``generate_sea_zones.py``; this is only the human-review picture.

Usage::

    python tools/render_sea_zones_preview.py            # partition lines
    python tools/render_sea_zones_preview.py --named     # canon sea groups
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import cells, raster, sea_zones, sources  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
LABELS_PATH = DERIVED_DIR / "sea_zones.png"
INDEX_PATH = DERIVED_DIR / "sea_zones_index.json"
OUT_PATH = DERIVED_DIR / "seas_partition_review.png"
OUT_HALF_PATH = DERIVED_DIR / "seas_partition_review_half.png"
NAMED_OUT_PATH = DERIVED_DIR / "seas_named_review.png"
NAMED_OUT_HALF_PATH = DERIVED_DIR / "seas_named_review_half.png"
NUMBERED_OUT_PATH = DERIVED_DIR / "seas_numbered_review.png"
NUMBERED_OUT_HALF_PATH = DERIVED_DIR / "seas_numbered_review_half.png"
NUMBERED_TABLE_PATH = DERIVED_DIR / "seas_numbered_index.txt"

SEA_ZONES_SOURCE = sources.source_ref("sea_zones")
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

LINE_RGB = (255, 0, 255)    # magenta — the sea-zone division lines
COAST_RGB = (0, 220, 255)   # cyan — the coastline (mask boundary)


def _zone_edges(sea: np.ndarray, wrap_x: bool) -> np.ndarray:
    edge = np.zeros(sea.shape, dtype=bool)
    edge[:, :-1] |= (sea[:, :-1] != sea[:, 1:]) & (sea[:, :-1] > 0) & (sea[:, 1:] > 0)
    edge[:-1, :] |= (sea[:-1, :] != sea[1:, :]) & (sea[:-1, :] > 0) & (sea[1:, :] > 0)
    if wrap_x:
        col = (sea[:, -1] != sea[:, 0]) & (sea[:, -1] > 0) & (sea[:, 0] > 0)
        edge[:, -1] |= col
        edge[:, 0] |= col
    return edge


def _group_colors(groups: list[str]) -> dict[str, tuple[int, int, int]]:
    """A distinct, deterministic tint per canon sea group.

    Hues spread around the wheel by authored order (the index the group first
    appears at), so neighbouring groups on the map get well-separated colours.
    """
    import colorsys

    order: list[str] = []
    for g in groups:
        if g not in order:
            order.append(g)
    out: dict[str, tuple[int, int, int]] = {}
    for i, g in enumerate(order):
        h = (i * 0.61803398875) % 1.0          # golden-ratio hop, even coverage
        s = 0.45 + 0.30 * (i % 2)               # alternate saturation for contrast
        v = 0.98                                 # keep every tint light so it reads over land
        r, gg, b = colorsys.hsv_to_rgb(h, s, v)
        out[g] = (int(r * 255), int(gg * 255), int(b * 255))
    return out


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_partition(t0: float) -> int:
    land = _read_land()
    drawn = sources.load_source_image(SEA_ZONES_SOURCE)
    print("extracting hand-drawn sea zones ...")
    sea = sea_zones.extract(land, drawn, wrap_x=WRAP_X, log=print)
    n = int(sea.max())
    print(f"  {n} sea zones  {time.time() - t0:.0f}s")

    edge = ndimage.binary_dilation(_zone_edges(sea, WRAP_X), iterations=2)
    coast = land ^ ndimage.binary_erosion(land, np.ones((3, 3), dtype=bool))
    coast = ndimage.binary_dilation(coast, iterations=1)

    globe = sources.load_source_image(GLOBE_SOURCE)
    img = globe.copy()
    img[coast] = COAST_RGB
    img[edge] = LINE_RGB

    _write(img, OUT_PATH, OUT_HALF_PATH, f"{n} zones, {int(edge.sum()):,} line px")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


def render_named(t0: float) -> int:
    """Tint the committed zones by canon sea group and label each group."""
    if not LABELS_PATH.is_file() or not INDEX_PATH.is_file():
        raise SystemExit(f"{LABELS_PATH} / {INDEX_PATH} not found — run generate_sea_zones.py first")
    land = _read_land()
    sea = cells.read_labels(LABELS_PATH)
    if sea.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{LABELS_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{sea.shape[1]}x{sea.shape[0]}")
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    cells_by_label = {c["label"]: c for c in index["cells"]}
    n = int(sea.max())

    groups = [cells_by_label[i]["sea_group"] for i in range(1, n + 1)]
    displays = {cells_by_label[i]["sea_group"]: cells_by_label[i]["display_name"]
                for i in range(1, n + 1)}
    gcolor = _group_colors(groups)
    print(f"  {n} zones in {len(gcolor)} canon sea groups  {time.time() - t0:.0f}s")

    # Per-zone group tint, blended over the globe so the terrain still reads.
    tint = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.float64)
    water = sea > 0
    for lab in range(1, n + 1):
        m = sea == lab
        tint[m] = gcolor[groups[lab - 1]]

    globe = sources.load_source_image(GLOBE_SOURCE).astype(np.float64)
    img = globe.copy()
    img[water] = 0.5 * globe[water] + 0.5 * tint[water]

    edge = ndimage.binary_dilation(_zone_edges(sea, WRAP_X), iterations=1)
    coast = land ^ ndimage.binary_erosion(land, np.ones((3, 3), dtype=bool))
    img[edge] = (30, 30, 30)
    img[ndimage.binary_dilation(coast, iterations=1)] = COAST_RGB
    img = img.clip(0, 255).astype(np.uint8)

    # One display name per group, at the group's water centroid snapped to a
    # group pixel (cosmetic, deterministic). Drawn last, over the tint.
    pil = Image.fromarray(img, "RGB")
    draw = ImageDraw.Draw(pil)
    font = _load_font(46)
    for g in sorted(gcolor):
        gm = np.isin(sea, [i for i in range(1, n + 1) if groups[i - 1] == g])
        ys, xs = np.nonzero(gm)
        if not len(xs):
            continue
        cx, cy = float(xs.mean()), float(ys.mean())
        # snap the anchor onto an actual group pixel so text sits in its water
        j = int(np.argmin((xs - cx) ** 2 + (ys - cy) ** 2))
        ax, ay = int(xs[j]), int(ys[j])
        text = displays[g]
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = (ax - tw // 2, ay - th // 2)
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                draw.text((pos[0] + dx, pos[1] + dy), text, font=font, fill=(0, 0, 0))
        draw.text(pos, text, font=font, fill=(255, 255, 255))
    img = np.asarray(pil, dtype=np.uint8)

    _write(img, NAMED_OUT_PATH, NAMED_OUT_HALF_PATH, f"{n} zones, {len(gcolor)} groups")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


def _zone_anchors(sea: np.ndarray, n: int) -> dict[int, tuple[int, int]]:
    """Each zone's centroid snapped to one of its own pixels — a guaranteed-interior
    ``(x, y)`` anchor for an override seed (one representative pixel is enough for
    that; see :func:`_zone_anchors_multi` for the printed numbers)."""
    ys, xs = np.nonzero(sea > 0)
    labs = sea[ys, xs]
    order = np.argsort(labs, kind="stable")
    ys, xs, labs = ys[order], xs[order], labs[order]
    uniq, starts = np.unique(labs, return_index=True)
    bounds = list(starts) + [len(labs)]
    out: dict[int, tuple[int, int]] = {}
    for k, lab in enumerate(uniq.tolist()):
        s, e = bounds[k], bounds[k + 1]
        zx, zy = xs[s:e], ys[s:e]
        cx, cy = zx.mean(), zy.mean()
        j = int(np.argmin((zx - cx) ** 2 + (zy - cy) ** 2))
        out[int(lab)] = (int(zx[j]), int(zy[j]))
    return out


def _zone_anchors_multi(sea: np.ndarray, n: int) -> dict[int, list[tuple[int, int]]]:
    """Every zone's numbered anchor(s) for the review render: one per significant
    disconnected *visual* fragment (plain, non-wrap 8-connectivity — this is about
    what a viewer sees on the flat canvas, not the wrap-aware zone topology).

    A zone that spans the wrap seam (``worldgen.cells`` correctly keeps it one
    zone) shows up as 2+ separate patches on the cut-open map; a single
    centroid-snapped anchor lands in only one of them — or, if the centroid pulls
    toward the seam, arguably neither. Found 2026-09-01: three FAR_OCEAN zones
    each wrapping pole-to-pole with no visible number on either edge. Every
    fragment at least 2,000px or 5% of the zone's total area (whichever is
    smaller) gets its own number, so a viewer never has to go hunting.
    """
    out: dict[int, list[tuple[int, int]]] = {}
    for lab in range(1, n + 1):
        mask = sea == lab
        total = int(mask.sum())
        if total == 0:
            out[lab] = []
            continue
        comp, ncomp = ndimage.label(mask, structure=np.ones((3, 3)))
        floor = min(2000, max(1, int(total * 0.05)))
        anchors = []
        sizes = ndimage.sum(mask, comp, range(1, ncomp + 1))
        for ci in range(1, ncomp + 1):
            if sizes[ci - 1] < floor:
                continue
            cys, cxs = np.nonzero(comp == ci)
            cx, cy = cxs.mean(), cys.mean()
            j = int(np.argmin((cxs - cx) ** 2 + (cys - cy) ** 2))
            anchors.append((int(cxs[j]), int(cys[j])))
        if not anchors:
            # every fragment was below the floor (a very scattered sliver) —
            # fall back to the single largest so the zone still gets a number.
            biggest = int(np.argmax(sizes)) + 1
            cys, cxs = np.nonzero(comp == biggest)
            cx, cy = cxs.mean(), cys.mean()
            j = int(np.argmin((cxs - cx) ** 2 + (cys - cy) ** 2))
            anchors = [(int(cxs[j]), int(cys[j]))]
        out[lab] = anchors
    return out


def render_numbered(t0: float) -> int:
    """Print each committed zone's label id on the group-tinted globe, and emit a
    number -> group + interior-pixel table for fine-tuning names via overrides."""
    if not LABELS_PATH.is_file() or not INDEX_PATH.is_file():
        raise SystemExit(f"{LABELS_PATH} / {INDEX_PATH} not found — run generate_sea_zones.py first")
    _read_land()  # shape guard + log
    sea = cells.read_labels(LABELS_PATH)
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    by_label = {c["label"]: c for c in index["cells"]}
    n = int(sea.max())
    groups = [by_label[i]["sea_group"] for i in range(1, n + 1)]
    gcolor = _group_colors(groups)

    tint = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.float64)
    water = sea > 0
    for lab in range(1, n + 1):
        tint[sea == lab] = gcolor[groups[lab - 1]]
    globe = sources.load_source_image(GLOBE_SOURCE).astype(np.float64)
    img = globe.copy()
    img[water] = 0.55 * globe[water] + 0.45 * tint[water]
    img[ndimage.binary_dilation(_zone_edges(sea, WRAP_X), iterations=1)] = (20, 20, 20)
    img = img.clip(0, 255).astype(np.uint8)

    anchors = _zone_anchors(sea, n)  # one seed pixel per zone, for the table
    anchors_multi = _zone_anchors_multi(sea, n)  # every visible fragment, for the numbers
    pil = Image.fromarray(img, "RGB")
    draw = ImageDraw.Draw(pil)
    font = _load_font(34)
    n_labels_drawn = 0
    for lab in range(1, n + 1):
        text = str(lab)
        bbox = draw.textbbox((0, 0), text, font=font)
        for (ax, ay) in anchors_multi[lab]:
            pos = (ax - (bbox[2] - bbox[0]) // 2, ay - (bbox[3] - bbox[1]) // 2)
            for dx in (-2, 0, 2):
                for dy in (-2, 0, 2):
                    draw.text((pos[0] + dx, pos[1] + dy), text, font=font, fill=(0, 0, 0))
            draw.text(pos, text, font=font, fill=(255, 255, 0))
            n_labels_drawn += 1
    img = np.asarray(pil, dtype=np.uint8)

    _write(img, NUMBERED_OUT_PATH, NUMBERED_OUT_HALF_PATH,
          f"{n} numbered zones, {n_labels_drawn} labels drawn")

    lines = ["# Zone number -> current canon sea + an interior pixel (for a sea_zones.json",
             "# override: {\"zone_seed\": [x, y], \"canon_sea\": \"<NAME>\"}). Board #2698.",
             f"# {n} zones. Regenerate with: python tools/render_sea_zones_preview.py --numbered",
             ""]
    for lab in range(1, n + 1):
        ax, ay = anchors[lab]
        c = by_label[lab]
        lines.append(f"{lab:3d}  {c['sea_group']:<20s} pixel=[{ax}, {ay}]  "
                     f"area={c['area']}  {'coastal' if c['coastal'] else 'open'}")
    NUMBERED_TABLE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {NUMBERED_TABLE_PATH}")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


def _read_land() -> np.ndarray:
    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — the land/sea mask must exist first")
    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{land.shape[1]}x{land.shape[0]}")
    print(f"land mask {land.shape} land {100 * land.mean():.2f}%")
    return land


def _write(img: np.ndarray, out_path: Path, half_path: Path, note: str) -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    raster.write_rgb_png(out_path, img)
    print(f"wrote {out_path}  ({note})")
    half = Image.fromarray(img, "RGB").resize((CANVAS_W // 2, CANVAS_H // 2),
                                              resample=Image.LANCZOS)
    half.save(half_path, format="PNG", optimize=False, compress_level=6)
    print(f"wrote {half_path}  ({CANVAS_W // 2}x{CANVAS_H // 2})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--named", action="store_true",
                    help="tint the committed zones by canon sea group (board #2698)")
    ap.add_argument("--numbered", action="store_true",
                    help="print each committed zone's label id + emit a number->group table (board #2698)")
    args = ap.parse_args(argv)
    t0 = time.time()
    if args.numbered:
        return render_numbered(t0)
    return render_named(t0) if args.named else render_partition(t0)


if __name__ == "__main__":
    raise SystemExit(main())
