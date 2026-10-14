#!/usr/bin/env python3
"""Generator: land/sea mask + heightmap + Chris's currents drawing -> climate zone layer (board #8202).

Turns the accepted climate-map prototype into a pipeline stage. ``worldgen.climate`` is the pure model
(fourteen Koppen-style zones, tuned on Earth, then accepted on this map on 2026-10-13); this driver does the
I/O the core forbids itself and writes:

* ``mapgen/derived/climate_zones.png`` -- 8192x3616 indexed PNG, value = class id (index into
  ``worldgen.climate.CLASSES``), 255 = sea or lake;
* ``mapgen/derived/climate_zones_index.json`` -- class ids, names, colours, land share per class and the
  SHA-256 of every input and of the 904x2048 class grid;
* with ``--states``: ``mapgen/derived/state_climate_index.json`` -- per drawn state the dominant zone and the
  share of each zone, keyed on ``state_key`` with the worksheet name as anchor (never the state number).

Inputs: ``derived/land_sea_mask.png``, ``map_data/heightmap.png``, the drawing registered as source layer
``climate_currents`` (``sources/geology/winds_and_currents.png``), and
``mapgen/config/climate_settings.json`` merged over ``climate.DEFAULT``. The drawing is Chris's; this stage
never edits it. The model runs at 1/4 canvas scale (about 30 s) and the class of each model cell is
nearest-filled to the canvas over the full-resolution mask. No clock, randomness or network.

Usage::

    python mapgen/generate_climate_zones.py             # write layer + index
    python mapgen/generate_climate_zones.py --dry-run   # compute + report, write nothing
    python mapgen/generate_climate_zones.py --check     # regenerate, diff the committed files
    python mapgen/generate_climate_zones.py --render    # flat picture + preview to scratchpad/
    python mapgen/generate_climate_zones.py --states    # per-state table (after generate_land_regions.py)
    python mapgen/generate_climate_zones.py --states --check

``--check`` compares decoded layer pixels and the index JSON, not PNG file bytes (those depend on the
Pillow build). A regenerated heightmap or mask moves the picture: re-render and have Chris accept it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

Image.MAX_IMAGE_PIXELS = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import climate, raster, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
SCRATCH_DIR = REPO_ROOT / "scratchpad"  # QA renders and previews; gitignored at the repo root

MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
HEIGHTMAP_PATH = REPO_ROOT / "map_data" / "heightmap.png"
SETTINGS_PATH = TOOLS_DIR / "config" / "climate_settings.json"
LAYERS_PATH = TOOLS_DIR / "config" / "source_layers.json"
SOURCE_LAYER_KEY = "climate_currents"

OUT_PNG = DERIVED_DIR / "climate_zones.png"
OUT_INDEX = DERIVED_DIR / "climate_zones_index.json"
OUT_STATES = DERIVED_DIR / "state_climate_index.json"

SEA = 255
CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE


def log(msg: str, t0: float | None = None) -> None:
    stamp = f"  [{time.time() - t0:5.1f}s]" if t0 is not None else ""
    print(f"{msg}{stamp}", flush=True)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def drawing_path() -> Path:
    layers = json.loads(LAYERS_PATH.read_text(encoding="utf-8"))
    return sources.resolve_source_path(layers[SOURCE_LAYER_KEY])


def compute(t0: float) -> tuple[np.ndarray, np.ndarray, dict]:
    """Return ``(grid, layer, index)``: the 904x2048 class grid, the canvas class raster and the index."""
    drawing = drawing_path()
    for pth, hint in ((MASK_PATH, "generate_coastline_mask.py"), (HEIGHTMAP_PATH, "generate_heightmap.py"),
                      (SETTINGS_PATH, "(hand-authored)")):
        if not pth.is_file():
            raise SystemExit(f"{pth} not found -- run mapgen/{hint} first")
    if not drawing.is_file():
        raise SystemExit(f"currents drawing not found at {drawing} (source layer {SOURCE_LAYER_KEY!r}; "
                         f"sources/ is local -- see mapgen/SOURCES.md)")
    log("loading inputs (mask, heightmap, currents drawing, settings)...", t0)
    land_full = raster.read_mask_png(MASK_PATH)
    if land_full.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"land mask is {land_full.shape}, expected {(CANVAS_H, CANVAS_W)}")
    hm = raster.read_gray16_png(HEIGHTMAP_PATH)
    hw, hh = map_config.HEIGHTMAP_SIZE
    if hm.shape != (hh, hw):
        raise SystemExit(f"heightmap is {hm.shape[1]}x{hm.shape[0]}, expected {hw}x{hh}")
    red, cya = climate.read_currents(drawing)
    if red.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"currents drawing is {red.shape[1]}x{red.shape[0]}, expected {CANVAS_W}x{CANVAS_H}")
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    unknown = sorted(set(settings) - set(climate.DEFAULT))
    if unknown:
        raise SystemExit(f"{SETTINGS_PATH}: unknown parameters {unknown}")
    log("running the model at 1/4 scale...", t0)
    inp = climate.prepare_inputs(land_full, hm, red, cya, climate.SCALE)
    del hm
    grid = climate.run(inp, settings)["k"].astype(np.uint8)
    log("filling to the canvas...", t0)
    S = climate.SCALE
    # the fill reference is the block mean > 0.5 (the accepted render's), not the model's BOX-resized mask
    h, w = grid.shape
    fill_land = land_full.reshape(h, S, w, S).mean(axis=(1, 3)) > 0.5
    near = ndi.distance_transform_edt(~fill_land, return_distances=False, return_indices=True)
    layer = np.repeat(np.repeat(grid[near[0], near[1]], S, 0), S, 1)
    layer = np.where(land_full, layer, SEA).astype(np.uint8)
    total = int(land_full.sum())
    classes = []
    for i, (code, name, col) in enumerate(climate.CLASSES):
        n = int((layer == i).sum())
        classes.append({"id": i, "code": code, "name": name, "color": list(col),
                        "land_px": n, "land_share": round(n / total, 5) if total else 0.0})
    index = {
        "schema": 1,
        "board": 8202,
        "canvas": [CANVAS_W, CANVAS_H],
        "model_grid": [int(grid.shape[1]), int(grid.shape[0])],
        "sea_value": SEA,
        "classes": classes,
        "inputs": {
            "land_sea_mask.png": _sha(MASK_PATH),
            "heightmap.png": _sha(HEIGHTMAP_PATH),
            "winds_and_currents.png": _sha(drawing),
            "climate_settings.json": _sha(SETTINGS_PATH),
        },
        "grid_sha256": hashlib.sha256(np.ascontiguousarray(grid).tobytes()).hexdigest(),
    }
    return grid, layer, index


def write_outputs(layer: np.ndarray, index: dict, png: Path, idx_path: Path) -> None:
    palette = [tuple(c["color"]) for c in index["classes"]]
    png.parent.mkdir(parents=True, exist_ok=True)
    raster.write_indexed_png(png, layer, palette)
    idx_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")


def render(layer: np.ndarray, index: dict, out_dir: Path) -> None:
    """Flat picture and a preview with the drawn strokes on top (thickened so they survive the downscale)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cl = index["classes"]
    pal = np.array([c["color"] for c in cl] + [(30, 40, 90)], np.uint8)
    flat = pal[np.where(layer == SEA, len(cl), layer)]

    def legend(im: Image.Image) -> Image.Image:
        d = ImageDraw.Draw(im)
        try:
            f = ImageFont.truetype("arial.ttf", 26)
        except OSError:
            f = ImageFont.load_default()
        x, y = 30, im.height - 40 * len(cl) - 30
        d.rectangle([x - 12, y - 12, x + 400, im.height - 18], fill=(255, 255, 255), outline=(0, 0, 0))
        for c in cl:
            d.rectangle([x, y, x + 44, y + 28], fill=tuple(c["color"]), outline=(0, 0, 0))
            d.text((x + 58, y - 2), f"{c['name']} ({c['code']})", fill=(0, 0, 0), font=f)
            y += 40
        return im

    small = lambda a: Image.fromarray(a).resize((4096, 1808), Image.LANCZOS)
    legend(small(flat)).save(out_dir / "climate_zones_flat.png")
    red, cya = climate.read_currents(drawing_path())
    comp = flat.astype(np.float32)
    for msk, col in ((red, (255, 0, 0)), (cya, (0, 255, 255))):
        t = np.clip(ndi.maximum_filter(msk, size=7), 0, 1)[..., None]
        comp = comp * (1 - t) + np.array(col, np.float32) * t
    legend(small(comp.astype(np.uint8))).save(out_dir / "climate_zones_preview.png")
    log(f"wrote {out_dir / 'climate_zones_flat.png'} and climate_zones_preview.png")


def zone_shares(row: np.ndarray, codes: list[str]) -> tuple[int, str | None, dict]:
    """``(land px, dominant code or None, {code: share})`` from one state's per-class pixel counts.
    Ties go to the lowest class id; a state with no land pixel in the layer has no dominant zone."""
    tot = int(row.sum())
    if not tot:
        return 0, None, {}
    dom = codes[int(np.argmax(row))]
    return tot, dom, {codes[c]: round(int(row[c]) / tot, 4) for c in range(len(codes)) if row[c]}


def state_table(layer: np.ndarray, index: dict) -> dict:
    """Per drawn state: dominant zone and the share of each zone over its passable land pixels."""
    import tabulate_state_prior as tsp
    from worldgen import land_naming

    ws_path = TOOLS_DIR / "config" / "land_regions_worksheet.csv"
    with open(ws_path, newline="", encoding="utf-8") as fh:
        ws_rows = {int(r["region_id"]): r for r in csv.DictReader(fh)}
    drawn_ids = {i for i, r in ws_rows.items() if r["kind"] == "drawn"}
    states, _stem = tsp._load_states(REPO_ROOT, drawn_ids)
    missing = sorted(drawn_ids - {st.id for st in states})
    if missing:
        # small-state prune folds some named rows into a neighbour; they have no state of their own
        log(f"note: {len(missing)} drawn worksheet rows have no emitted state (region_id): {missing}")
    impass_of = {st.key: set(st.impassable) for st in states}
    rgb = raster.read_rgb_png(REPO_ROOT / "map_data" / "provinces.png")
    if rgb.shape[:2] != layer.shape:
        raise SystemExit(f"provinces.png is {rgb.shape[1]}x{rgb.shape[0]}, "
                         f"expected {layer.shape[1]}x{layer.shape[0]}")
    lab = tsp._state_raster(rgb, states, True, impass_of)
    del rgb
    ncls = len(index["classes"])
    codes = [c["code"] for c in index["classes"]]
    ok = (lab > 0) & (layer != SEA)
    counts = np.zeros((len(states) + 1, ncls), np.int64)
    np.add.at(counts, (lab[ok], layer[ok].astype(np.int64)), 1)
    names = land_naming.load_worksheet_names(ws_path)
    out = []
    for i, st in sorted(enumerate(states, start=1), key=lambda t: t[1].key):
        tot, dom, shares = zone_shares(counts[i], codes)
        out.append({
            "state_key": st.key,
            "worksheet_name": ws_rows[st.id]["name"],
            "name": names.names.get(st.id, ""),
            "land_px": tot,
            "dominant": dom,
            "shares": shares,
        })
    return {"schema": 1, "board": 8202, "layer_grid_sha256": index["grid_sha256"], "states": out}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="compute and report, write nothing")
    p.add_argument("--check", action="store_true", help="regenerate and diff the committed files")
    p.add_argument("--render", action="store_true", help="write the flat picture and preview to scratchpad/")
    p.add_argument("--states", action="store_true", help="the per-state table (reads the committed layer)")
    args = p.parse_args(argv)
    t0 = time.time()

    if args.states:
        if not (OUT_PNG.is_file() and OUT_INDEX.is_file()):
            raise SystemExit("--states needs the committed layer: run generate_climate_zones.py first")
        layer, _ = raster.read_indexed_png(OUT_PNG)
        index = json.loads(OUT_INDEX.read_text(encoding="utf-8"))
        table = state_table(layer, index)
        text = json.dumps(table, indent=2) + "\n"
        if args.check:
            if not OUT_STATES.is_file():
                log(f"--check: {OUT_STATES} is not committed yet -- nothing to diff against.", t0)
                return 0
            if OUT_STATES.read_text(encoding="utf-8") == text:
                log("--check: the per-state table matches the committed one.", t0)
                return 0
            log("--check: MISMATCH -- the per-state table is stale; re-run with --states.", t0)
            return 1
        log(f"{len(table['states'])} drawn states", t0)
        if not args.dry_run:
            OUT_STATES.write_text(text, encoding="utf-8", newline="\n")
            log(f"wrote {OUT_STATES}", t0)
        return 0

    grid, layer, index = compute(t0)
    for c in index["classes"]:
        log(f"  {c['code']:4s} {c['name']:20s} {100 * c['land_share']:5.1f}%")
    if args.render:
        render(layer, index, SCRATCH_DIR)
    if args.check:
        if not (OUT_PNG.is_file() and OUT_INDEX.is_file()):
            log("--check: the layer is not committed yet -- nothing to diff against.", t0)
            return 0
        same_px = np.array_equal(raster.read_indexed_png(OUT_PNG)[0], layer)
        same_idx = json.loads(OUT_INDEX.read_text(encoding="utf-8")) == index
        if same_px and same_idx:
            log("--check: regenerated layer and index match the committed ones.", t0)
            return 0
        log(f"--check: STALE -- layer pixels {'match' if same_px else 'DIFFER'}, index "
            f"{'matches' if same_idx else 'DIFFERS'}. Re-run, render and have Chris accept the picture.", t0)
        return 1
    if not args.dry_run:
        write_outputs(layer, index, OUT_PNG, OUT_INDEX)
        log(f"wrote {OUT_PNG} and {OUT_INDEX}", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
