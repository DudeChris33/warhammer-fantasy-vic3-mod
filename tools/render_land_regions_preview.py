#!/usr/bin/env python3
"""Review render: the 708 land regions, numbered, over the reprojected globe.

Board #2930's dev-only naming aid, mirroring ``render_provinces_preview.py``'s
committed-data + reprojected-globe-overlay pattern
(``feedback-review-render-on-reprojected-globe``): reads the *committed*
``map_data/provinces.png`` + ``tools/derived/land_regions_index.json`` +
``tools/derived/provinces_index.json`` + the name guesses from
``tools/derived/land_region_name_guesses.json`` (run ``generate_land_regions.py``
first), tints every region with a spread-palette colour and draws its number at
its centroid.

**Disclosed limitation**: 708 regions (many 1-few-px placeholder slivers)
cannot all carry a legible on-image label — only regions at or above
``MIN_LABEL_AREA`` get one. The CSV sidecar (``land_regions_worksheet.csv``,
sorted by area descending) is the exhaustive reference for the rest, mirroring
``tools/config/sea_zone_naming_worksheet.txt``'s pattern: the image serves the
large, eyeball-able regions; the sidecar is the exhaustive list.

Local-only output: embeds the source globe pixels, so it lands under
``tools/derived/``, which ``tools/.gitignore`` excludes from the repo — never
shipped content, purely a naming aid for #2931.

Usage::

    python tools/render_land_regions_preview.py
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import raster, sources  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"

PROVINCES_PATH = REPO_ROOT / "map_data" / "provinces.png"
PROVINCES_INDEX_PATH = DERIVED_DIR / "provinces_index.json"
LAND_REGIONS_INDEX_PATH = DERIVED_DIR / "land_regions_index.json"
NAME_GUESS_PATH = DERIVED_DIR / "land_region_name_guesses.json"

OUT_PATH = DERIVED_DIR / "land_regions_preview.png"
OUT_HALF_PATH = DERIVED_DIR / "land_regions_preview_half.png"
CSV_PATH = DERIVED_DIR / "land_regions_worksheet.csv"

GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: Only a region at or above this pixel area gets an on-image number label —
#: below this the text would not be legible at canvas scale. Every region,
#: regardless of size, still gets a CSV row.
MIN_LABEL_AREA = 4000

EDGE_RGB = (20, 20, 20)


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


def _build_region_labels(rgb: np.ndarray, prov_cells: list[dict],
                         region_cells: list[dict], n_land: int) -> np.ndarray:
    """Per-pixel region-id layer (0 on sea/out-of-canvas), built the same way
    ``generate_land_regions._build_label_array`` + its region_of mapping does."""
    code = ((rgb[..., 0].astype(np.int64) << 16)
            | (rgb[..., 1].astype(np.int64) << 8) | rgb[..., 2].astype(np.int64))
    color_to_label: dict[int, int] = {}
    for c in prov_cells:
        r, g, b = c["color"]
        color_to_label[(int(r) << 16) | (int(g) << 8) | int(b)] = int(c["label"])
    uniq, inv = np.unique(code, return_inverse=True)
    lut = np.array([color_to_label.get(int(k), 0) for k in uniq.tolist()], dtype=np.int64)
    prov_labels = lut[inv].reshape(code.shape)

    region_of = np.zeros(n_land + 1, dtype=np.int64)
    for cell in region_cells:
        for p in cell["provinces"]:
            region_of[p] = int(cell["region"])

    land_mask = (prov_labels >= 1) & (prov_labels <= n_land)
    region_labels = np.zeros(prov_labels.shape, dtype=np.int64)
    region_labels[land_mask] = region_of[prov_labels[land_mask]]
    return region_labels


def _spread_palette(n: int) -> np.ndarray:
    import colorsys

    out = np.zeros((n + 1, 3), dtype=np.float64)
    for i in range(1, n + 1):
        h = ((i - 1) * 0.61803398875) % 1.0
        s = 0.45 + 0.30 * (i % 2)
        r, g, b = colorsys.hsv_to_rgb(h, s, 0.98)
        out[i] = (r * 255, g * 255, b * 255)
    return out


def _edges(lab: np.ndarray, wrap_x: bool) -> np.ndarray:
    edge = np.zeros(lab.shape, dtype=bool)
    edge[:, :-1] |= (lab[:, :-1] != lab[:, 1:]) & (lab[:, :-1] > 0) & (lab[:, 1:] > 0)
    edge[:-1, :] |= (lab[:-1, :] != lab[1:, :]) & (lab[:-1, :] > 0) & (lab[1:, :] > 0)
    if wrap_x:
        col = (lab[:, -1] != lab[:, 0]) & (lab[:, -1] > 0) & (lab[:, 0] > 0)
        edge[:, -1] |= col
        edge[:, 0] |= col
    return edge


def _region_centroids(lab: np.ndarray, n_regions: int, width: int):
    """Circular-mean centroid per region (same estimator as the generator)."""
    ys, xs = np.nonzero(lab > 0)
    grp = lab[ys, xs]
    theta = (xs.astype(np.float64) + 0.5) * (2.0 * np.pi / width)
    sum_cos = np.bincount(grp, weights=np.cos(theta), minlength=n_regions + 1)
    sum_sin = np.bincount(grp, weights=np.sin(theta), minlength=n_regions + 1)
    sum_y = np.bincount(grp, weights=ys.astype(np.float64) + 0.5, minlength=n_regions + 1)
    counts = np.bincount(grp, minlength=n_regions + 1)
    ang = np.arctan2(sum_sin, sum_cos)
    cx = (ang % (2.0 * np.pi)) * width / (2.0 * np.pi)
    cy = np.zeros_like(sum_y)
    nz = counts > 0
    cy[nz] = sum_y[nz] / counts[nz]
    return cx, cy


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover — Pillow < 10.1 has no `size` kwarg
        return ImageFont.load_default()


def main(argv: list[str] | None = None) -> int:
    t0 = time.time()
    for path in (PROVINCES_PATH, PROVINCES_INDEX_PATH, LAND_REGIONS_INDEX_PATH):
        if not path.is_file():
            raise SystemExit(f"{path} not found — run generate_provinces.py / "
                             f"generate_land_regions.py first")

    prov_index = json.loads(PROVINCES_INDEX_PATH.read_text(encoding="utf-8"))
    land_regions = json.loads(LAND_REGIONS_INDEX_PATH.read_text(encoding="utf-8"))
    name_guesses = (json.loads(NAME_GUESS_PATH.read_text(encoding="utf-8"))
                    if NAME_GUESS_PATH.is_file() else {})
    n_land = int(prov_index["land_provinces"])
    n_regions = int(land_regions["regions"])

    rgb = raster.read_rgb_png(PROVINCES_PATH)
    if rgb.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{PROVINCES_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{rgb.shape[1]}x{rgb.shape[0]}")
    lab = _build_region_labels(rgb, prov_index["cells"], land_regions["cells"], n_land)
    log(f"{n_regions} region labels built", t0)

    cx, cy = _region_centroids(lab, n_regions, CANVAS_W)

    palette = _spread_palette(n_regions)
    tint = palette[lab]
    globe = sources.load_source_image(GLOBE_SOURCE).astype(np.float64)
    img = globe.copy()
    filled = lab > 0
    img[filled] = 0.45 * globe[filled] + 0.55 * tint[filled]
    img[ndimage.binary_dilation(_edges(lab, WRAP_X), iterations=1)] = EDGE_RGB
    img = img.clip(0, 255).astype(np.uint8)
    log("tinted overlay composited", t0)

    areas = {int(c["region"]): int(c["area"]) for c in land_regions["cells"]}
    kinds = {int(c["region"]): c["kind"] for c in land_regions["cells"]}

    pil_img = Image.fromarray(img, "RGB")
    draw = ImageDraw.Draw(pil_img)
    font = _load_font(28)
    n_labelled = 0
    for region_id in range(1, n_regions + 1):
        if areas.get(region_id, 0) < MIN_LABEL_AREA:
            continue
        x, y = float(cx[region_id]), float(cy[region_id])
        text = str(region_id)
        draw.text((x, y), text, fill=(255, 255, 255), font=font, anchor="mm",
                  stroke_width=2, stroke_fill=(0, 0, 0))
        n_labelled += 1
    log(f"labelled {n_labelled}/{n_regions} regions on-image (>= {MIN_LABEL_AREA} px)", t0)

    out_rgb = np.asarray(pil_img, dtype=np.uint8)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    raster.write_rgb_png(OUT_PATH, out_rgb)
    print(f"wrote {OUT_PATH}")
    half = pil_img.resize((CANVAS_W // 2, CANVAS_H // 2), resample=Image.LANCZOS)
    half.save(OUT_HALF_PATH, format="PNG", optimize=False, compress_level=6)
    print(f"wrote {OUT_HALF_PATH}  ({CANVAS_W // 2}x{CANVAS_H // 2})")

    # --- CSV worksheet: every region, sorted by area descending ------------
    rows = []
    for region_id in range(1, n_regions + 1):
        guess = name_guesses.get(str(region_id), {})
        rows.append({
            "region_id": region_id,
            "kind": kinds.get(region_id, ""),
            "area_px": areas.get(region_id, 0),
            "guess_key": guess.get("guess_key", ""),
            "guess_lon": guess.get("guess_lon", ""),
            "guess_lat": guess.get("guess_lat", ""),
            "distance_deg": guess.get("distance_deg", ""),
        })
    rows.sort(key=lambda r: -r["area_px"])
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {CSV_PATH}  ({len(rows)} rows, sorted by area descending)")

    log(f"done: {n_regions} regions rendered", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
