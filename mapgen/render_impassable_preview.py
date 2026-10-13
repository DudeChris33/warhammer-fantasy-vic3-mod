#!/usr/bin/env python3
"""Dev-only review render for the impassable land provinces (board #3704).

Tints every impassable province orange over passable land, draws the province
edges, and dots each canon city (green = passable province in its state's
main component, red = sealed/impassable). Reads the committed
``map_data/provinces.png`` + ``mapgen/derived/provinces_index.json`` and, when it
exists, ``mapgen/derived/canon_city_provinces_index.json``. Writes into
``scratchpad/`` (gitignored) — a dev-only artifact for the user's visual
verdict, outside the offline gate. Source-free: no parchment drape.
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

from config import map_config  # noqa: E402
from worldgen import land_provinces, raster  # noqa: E402

REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"  # QA renders and previews; gitignored at the repo root
PROVINCES_PNG = REPO_ROOT / "map_data" / "provinces.png"
PROVINCES_INDEX = DERIVED_DIR / "provinces_index.json"
CITY_INDEX = DERIVED_DIR / "canon_city_provinces_index.json"
OUT_PATH = SCRATCH_DIR / "impassable_preview.png"
OUT_HALF_PATH = SCRATCH_DIR / "impassable_preview_half.png"
OUT_CROP_PATH = SCRATCH_DIR / "impassable_preview_crop.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

WATER = (28, 48, 84)
PASSABLE = (214, 205, 180)
PLACEHOLDER = (170, 170, 170)
IMPASSABLE = (232, 110, 20)
EDGE = (60, 40, 25)


def log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def _edges(code: np.ndarray) -> np.ndarray:
    e = np.zeros(code.shape, dtype=bool)
    e[:, :-1] |= code[:, :-1] != code[:, 1:]
    e[:-1, :] |= code[:-1, :] != code[1:, :]
    return e


def main() -> int:
    t0 = time.time()
    for p in (PROVINCES_PNG, PROVINCES_INDEX):
        if not p.is_file():
            raise SystemExit(f"missing {p} — run generate_provinces.py first")
    rgb = raster.read_rgb_png(PROVINCES_PNG)
    index = json.loads(PROVINCES_INDEX.read_text(encoding="utf-8"))
    code = ((rgb[..., 0].astype(np.uint32) << 16) | (rgb[..., 1].astype(np.uint32) << 8)
            | rgb[..., 2].astype(np.uint32))

    kinds = {"land": PASSABLE}
    palette: dict[int, tuple[int, int, int]] = {}
    n_imp = 0
    for c in index["cells"]:
        r, g, b = (int(v) for v in c["color"])
        key = (r << 16) | (g << 8) | b
        if c["kind"] != "land":
            palette[key] = WATER
        elif c.get("impassable"):
            palette[key] = IMPASSABLE
            n_imp += 1
        elif c.get("placeholder"):
            palette[key] = PLACEHOLDER
        else:
            palette[key] = kinds["land"]
    uniq, inv = np.unique(code, return_inverse=True)
    lut = np.array([palette.get(int(k), WATER) for k in uniq.tolist()], dtype=np.uint8)
    out = lut[inv].reshape(*code.shape, 3)
    out[_edges(code)] = EDGE
    log(f"{n_imp} impassable land province(s)", t0)

    img = Image.fromarray(out)
    draw = ImageDraw.Draw(img)
    pts: list[tuple[int, int]] = []
    if CITY_INDEX.is_file():
        for c in json.loads(CITY_INDEX.read_text(encoding="utf-8"))["cities"]:
            x, y = c["anchor"]
            ok = (not c.get("impassable")) and c.get("province_hex")
            col = (30, 170, 60) if ok else (220, 30, 30)
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=col)
            if not ok:
                draw.text((x + 8, y - 10), c["name"], fill=(0, 0, 0))
            pts.append((x, y))

    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_PATH)
    img.resize((CANVAS_W // 2, CANVAS_H // 2)).save(OUT_HALF_PATH)
    log(f"wrote {OUT_PATH.name} + half", t0)

    imp_px = np.isin(code, [((int(c['color'][0]) << 16) | (int(c['color'][1]) << 8) | int(c['color'][2]))
                            for c in index["cells"] if c["kind"] == "land" and c.get("impassable")])
    if imp_px.any():
        ys, xs = np.nonzero(imp_px)
        x0, x1 = max(0, int(xs.min()) - 100), min(CANVAS_W, int(xs.max()) + 100)
        y0, y1 = max(0, int(ys.min()) - 100), min(CANVAS_H, int(ys.max()) + 100)
        img.crop((x0, y0, x1, y1)).save(OUT_CROP_PATH)
        log(f"wrote {OUT_CROP_PATH.name} ({x1 - x0}x{y1 - y0})", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
