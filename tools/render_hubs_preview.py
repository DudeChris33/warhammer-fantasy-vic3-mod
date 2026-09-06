#!/usr/bin/env python3
"""Dev-only review render for the lore-hub tooling (board #3665).

Draws each listed settlement's anchor dot + name and the province edges over the
parchment-draped globe, so a realm naming pass ends in a visual verdict. Reads the
committed ``map_data/provinces.png`` + ``tools/derived/provinces_index.json`` and
the derived ``tools/derived/hub_anchors_index.json`` (written by
``generate_provinces.py`` when a hub worksheet exists).

Source-dependent (the parchment drape reuses ``project_regions.py``'s five-crop
registration, like ``render_land_regions_preview.py``) and writes into
``tools/derived/`` (gitignored) — a dev-only artifact, run on the user's authoring
machine. Outputs the whole world plus a tight crop around the listed hubs, since a
proving-slice of a few states is otherwise lost on the 8192-wide canvas.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import render_land_regions_preview as rlr  # noqa: E402 — reuse its drape/edges/font
from config import map_config  # noqa: E402
from worldgen import raster  # noqa: E402

REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
PROVINCES_PNG = REPO_ROOT / "map_data" / "provinces.png"
PROVINCES_INDEX = DERIVED_DIR / "provinces_index.json"
HUB_ANCHORS_INDEX = DERIVED_DIR / "hub_anchors_index.json"
OUT_PATH = DERIVED_DIR / "hubs_preview.png"
OUT_HALF_PATH = DERIVED_DIR / "hubs_preview_half.png"
OUT_CROP_PATH = DERIVED_DIR / "hubs_preview_crop.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: A distinct dot colour per hub kind.
_HUB_DOT = {
    "city": (220, 40, 40),
    "port": (40, 90, 240),
    "farm": (235, 195, 40),
    "mine": (150, 150, 165),
    "wood": (40, 180, 70),
}


def log(msg: str, t0: float | None = None) -> None:
    print((f"[{time.time() - t0:6.1f}s] " if t0 is not None else "") + msg, flush=True)


def _province_labels(rgb: np.ndarray, prov_cells: list[dict]) -> np.ndarray:
    """Per-pixel province-label layer from the committed colour->label mapping."""
    code = ((rgb[..., 0].astype(np.int64) << 16)
            | (rgb[..., 1].astype(np.int64) << 8) | rgb[..., 2].astype(np.int64))
    c2l: dict[int, int] = {}
    for c in prov_cells:
        r, g, b = c["color"]
        c2l[(int(r) << 16) | (int(g) << 8) | int(b)] = int(c["label"])
    uniq, inv = np.unique(code, return_inverse=True)
    lut = np.array([c2l.get(int(k), 0) for k in uniq.tolist()], dtype=np.int64)
    return lut[inv].reshape(code.shape)


def main(argv: list[str] | None = None) -> int:
    t0 = time.time()
    for p in (PROVINCES_PNG, PROVINCES_INDEX, HUB_ANCHORS_INDEX):
        if not p.is_file():
            raise SystemExit(f"missing {p} — run generate_provinces.py with a hub worksheet first")

    rgb = raster.read_rgb_png(PROVINCES_PNG)
    prov_index = json.loads(PROVINCES_INDEX.read_text(encoding="utf-8"))
    hub_index = json.loads(HUB_ANCHORS_INDEX.read_text(encoding="utf-8"))
    log(f"{len(hub_index['hubs'])} hub(s) to draw", t0)

    prov_lab = _province_labels(rgb, prov_index["cells"])
    edges = rlr._edges(prov_lab, WRAP_X)

    backdrop, placed = rlr._parchment_drape(t0)
    out = np.where(placed[..., None], backdrop, rgb).astype(np.uint8)
    out[edges] = (40, 20, 10)  # dark province edges

    img = Image.fromarray(out)
    draw = ImageDraw.Draw(img)
    font = rlr._load_font(30)
    r = 9
    for h in hub_index["hubs"]:
        rx, ry = int(h["resolved"][0]), int(h["resolved"][1])
        col = _HUB_DOT.get(h["hub"], (255, 0, 255))
        draw.ellipse([rx - r, ry - r, rx + r, ry + r], fill=col, outline=(0, 0, 0), width=2)
        draw.text((rx + r + 4, ry - 16), f"{h['name']} ({h['hub']})", fill=(0, 0, 0),
                  font=font, stroke_width=3, stroke_fill=(255, 255, 255))

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_PATH)
    log(f"wrote {OUT_PATH}", t0)
    img.resize((CANVAS_W // 2, CANVAS_H // 2)).save(OUT_HALF_PATH)
    log(f"wrote {OUT_HALF_PATH}  ({CANVAS_W // 2}x{CANVAS_H // 2})", t0)

    xs = [int(h["resolved"][0]) for h in hub_index["hubs"]]
    ys = [int(h["resolved"][1]) for h in hub_index["hubs"]]
    if xs:
        pad = 240
        x0, x1 = max(0, min(xs) - pad), min(CANVAS_W, max(xs) + pad)
        y0, y1 = max(0, min(ys) - pad), min(CANVAS_H, max(ys) + pad)
        img.crop((x0, y0, x1, y1)).save(OUT_CROP_PATH)
        log(f"wrote {OUT_CROP_PATH}  ({x1 - x0}x{y1 - y0})", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
