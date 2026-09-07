#!/usr/bin/env python3
"""S2 generator: the user-traced canon river network -> map_data/rivers.png.

Rivers are **source-driven**, not derived from the terrain (board #3703). The old
heightmap-drainage network (``hydro.py``) drew dense, terrain-following channels
that were wrong for a fictional world — the Reik did not exist and big channels
ran through the Nehekharan desert. Instead the canon rivers are traced by hand as
a pure-cyan ``(0, 255, 255)`` line network and turned into the game's river layer
by the tools::

    sources/terraqueous_globe_reprojected - rivers.png   (canvas-native cyan)
    [+ any registered-crop cyan layers, warped onto the canvas]
        -> extract cyan -> skeletonize -> graph -> orient by mask-adjacency
        -> maximal Horton/Strahler stems (one green source per headwater,
           tributaries -> red MERGE)                        (river_network.py)
        -> width from stream order on the vanilla ramp (3 -> 4 -> 6 -> 8)
        -> worldgen.rivers.rasterize (source/merge painting + strict validation)
        -> map_data/rivers.png  (indexed, vanilla palette)

Naming is opt-in: the engine has no river names, so a stream is named only if a
downstream item (#3677 economics, #3687 traits) references that specific river.
Each canon name in ``tools/config/canon_river_names.json`` pins a NAME to an
anchor pixel on its drawn line; the generator resolves each anchor to exactly one
extracted stream and writes ``tools/derived/rivers_index.json`` (name -> mouth
kind, length, width, and the state keys the river traverses) for those items to
consume instead of re-deriving.

The output is a pure function of the committed source(s), the names file, the
land/sea mask and the heightmap (elevation tie-break only) — deterministic, no
drainage-derived channel anywhere, and land with no traced river carries none.

Usage::

    python tools/generate_rivers.py             # write map_data/rivers.png
    python tools/generate_rivers.py --preview    # + a downscaled overlay
    python tools/generate_rivers.py --dry-run    # extract + validate, write nothing
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

Image.MAX_IMAGE_PIXELS = None

from config import map_config  # noqa: E402
from worldgen import raster, reproject, river_network, rivers as riverlib, schema  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MAP_DATA_DIR = REPO_ROOT / "map_data"
SOURCES_DIR = REPO_ROOT / "sources"
REGISTRATION_DIR = TOOLS_DIR / "registration"
PALETTE_JSON = TOOLS_DIR / "lut" / "rivers_palette.json"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
HEIGHTMAP_PATH = MAP_DATA_DIR / "heightmap.png"

#: The default canvas-native trace (1:1 with the canvas, no registration).
DEFAULT_SOURCE = SOURCES_DIR / "terraqueous_globe_reprojected - rivers.png"
#: Optional multi-layer declaration; absent -> read DEFAULT_SOURCE only.
RIVER_SOURCES_JSON = TOOLS_DIR / "config" / "river_sources.json"
#: The anchor-keyed canon names; absent -> every stream keeps an auto id.
CANON_NAMES_JSON = TOOLS_DIR / "config" / "canon_river_names.json"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: Rows warped at a time in registered mode, so a full-canvas float grid never
#: materialises (the memory pattern project_regions.place_painting uses).
_ROW_BLOCK = 256


def log(msg: str, t0: float | None = None) -> None:
    stamp = f"  [{time.time() - t0:5.1f}s]" if t0 is not None else ""
    print(f"{msg}{stamp}", flush=True)


def _load_canvas_layer(path: Path, dilate: int) -> np.ndarray:
    """Cyan network of a canvas-native trace (1:1 with the canvas)."""
    rgb = raster.read_rgb_png(path)
    if rgb.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(
            f"{path} is {rgb.shape[1]}x{rgb.shape[0]}, expected the canvas "
            f"{CANVAS_W}x{CANVAS_H} (a canvas-native trace must be 1:1)")
    return river_network.cyan_network(rgb, dilate=dilate)


def _load_registered_layer(path: Path, reg_name: str, regs: dict, dilate: int) -> np.ndarray:
    """Cyan network of a trace in a registered crop's own frame, warped onto the
    canvas through that crop's committed registration.

    The higher-risk mode (red-team obj 4): a 1-px line resampled through a warp can
    fray, so the cyan is dilated *before* warping and sampled nearest; any residual
    tear surfaces downstream as the loud stranded-line / non-tree error in
    ``river_network.extract_streams`` (there is no fill step to silently heal it).
    Exercised in Phase B on a real registered trace; Phase A's offline fixtures
    cover only the canvas-native path.
    """
    reg = next((r for r in regs.values() if r.source == reg_name or _stem(r.source) == reg_name),
               None)
    if reg is None:
        raise SystemExit(
            f"river source layer '{path.name}': registration '{reg_name}' not found in "
            f"{REGISTRATION_DIR} (expected a committed <name>.json)")
    rgb = raster.read_rgb_png(path)
    src = river_network.cyan_network(rgb, dilate=dilate).astype(np.float32)
    sh, sw = src.shape
    fit = reproject.fit_placement(reg, regs)
    out = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
    gx_row = (np.arange(CANVAS_W, dtype=np.float64) + 0.5)[None, :]
    for y0 in range(0, CANVAS_H, _ROW_BLOCK):
        y1 = min(y0 + _ROW_BLOCK, CANVAS_H)
        gy = (np.arange(y0, y1, dtype=np.float64) + 0.5)[:, None]
        gxb = np.broadcast_to(gx_row, (y1 - y0, CANVAS_W))
        gyb = np.broadcast_to(gy, (y1 - y0, CANVAS_W))
        sx, sy = fit.to_source_px(gxb, gyb)
        inb = (sx >= 0) & (sx <= sw - 1) & (sy >= 0) & (sy <= sh - 1)
        inb &= reproject.crop_mask(reg, sx, sy)
        sampled = reproject.resample(src, sx, sy, order=0)
        out[y0:y1][(sampled > 0.5) & inb] = True
    return out


def _stem(name: str) -> str:
    return Path(name).stem


def load_network(dilate: int, t0: float) -> np.ndarray:
    """The unioned cyan river network on the canvas, from the declared layers
    (or the single default canvas-native trace)."""
    if RIVER_SOURCES_JSON.is_file():
        layers = schema.load_river_sources(RIVER_SOURCES_JSON)
        regs = None
        network = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
        for layer in layers:
            path = SOURCES_DIR / layer.file
            if not path.is_file():
                raise SystemExit(f"river source layer file not found: {path}")
            if layer.mode == "canvas":
                network |= _load_canvas_layer(path, dilate)
            else:  # registered
                if regs is None:
                    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
                network |= _load_registered_layer(path, layer.registration, regs, dilate)
            log(f"  layer {layer.file} ({layer.mode}): union now {int(network.sum()):,} px", t0)
        return network
    if not DEFAULT_SOURCE.is_file():
        raise SystemExit(
            f"no river source: {DEFAULT_SOURCE} not found and no {RIVER_SOURCES_JSON.name}. "
            f"Trace the canon rivers in pure cyan (0,255,255) on the canvas first.")
    net = _load_canvas_layer(DEFAULT_SOURCE, dilate)
    log(f"  canvas-native {DEFAULT_SOURCE.name}: {int(net.sum()):,} cyan px", t0)
    return net


def _elevation_canvas() -> np.ndarray | None:
    """Canvas-sized elevation for the flow tie-break (heightmap is 2x the canvas;
    a stride-2 sample is precise enough for a tie-break). ``None`` if absent."""
    if not HEIGHTMAP_PATH.is_file():
        return None
    with Image.open(HEIGHTMAP_PATH) as im:
        h16 = np.asarray(im, dtype=np.uint16)
    return h16[::2, ::2][:CANVAS_H, :CANVAS_W].astype(np.float32)


def _join_state_keys(streams, t0: float) -> dict[str, list[str]]:
    """For each named stream, the sorted state keys its pixels fall in.

    The join #3677/#3687/#2968 would otherwise re-derive: river pixel ->
    provinces.png colour -> the owning state in map_data/state_regions/*.txt.
    Needs the real emitted province bitmap + states, so it is a Phase-B join;
    returns ``{}`` (with a note) when those inputs do not exist yet.
    """
    provinces_png = MAP_DATA_DIR / "provinces.png"
    state_dir = MAP_DATA_DIR / "state_regions"
    if not provinces_png.is_file() or not state_dir.is_dir():
        log("  (state_keys join skipped — provinces.png / state_regions not present yet)", t0)
        return {}
    import validate_map  # local: only needed for the Phase-B join

    color_to_state: dict[tuple[int, int, int], str] = {}
    for path in sorted(state_dir.glob("*.txt")):
        for st in validate_map.parse_state_file(path):
            for c in st.provinces:
                color_to_state[c] = st.key
    prov = raster.read_rgb_png(provinces_png)
    out: dict[str, list[str]] = {}
    for st in streams:
        keys: set[str] = set()
        for (x, y) in st.points:
            c = tuple(int(v) for v in prov[y, x])
            k = color_to_state.get(c)
            if k:
                keys.add(k)
        out[st.name] = sorted(keys)
    return out


def _write_index(result: river_network.ExtractResult, state_keys: dict[str, list[str]],
                 path: Path) -> None:
    """Write tools/derived/rivers_index.json (regenerate-never-hand-edit)."""
    rivers = []
    for name in sorted(result.index):
        entry = dict(result.index[name])
        entry["name"] = name
        entry["state_keys"] = state_keys.get(name, [])
        rivers.append(entry)
    payload = {
        "_comment": "Generated by tools/generate_rivers.py (board #3703). "
                    "Regenerate, never hand-edit. name -> mouth kind, length, width, "
                    "and the state keys the river traverses; consumed by #3677/#3687/#2968.",
        "count": len(rivers),
        "rivers": rivers,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--preview", action="store_true", help="also write a downscaled overlay")
    p.add_argument("--dry-run", action="store_true",
                   help="extract + validate + report, but write no bitmap or index")
    p.add_argument("--dilate", type=int, default=2,
                   help="cyan-line dilation to bridge anti-aliasing (default 2)")
    args = p.parse_args(argv)

    t0 = time.time()
    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_coastline_mask.py first")

    log("loading land mask + river source(s)...")
    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"mask is {land.shape}, expected {(CANVAS_H, CANVAS_W)}")
    network = load_network(args.dilate, t0)
    elevation = _elevation_canvas()

    names: list[schema.CanonRiverName] = []
    if CANON_NAMES_JSON.is_file():
        names = schema.load_canon_river_names(CANON_NAMES_JSON, canvas=(CANVAS_W, CANVAS_H))
        log(f"  {len(names)} canon river name(s) loaded", t0)

    log("extracting streams (skeleton -> graph -> orient -> Strahler stems)...")
    result = river_network.extract_streams(
        network, land, elevation=elevation, names=names, wrap_x=map_config.WRAP_X)
    n_src = sum(1 for s in result.streams if s.mouth == "sea")
    log(f"  {len(result.streams)} streams ({n_src} reach the sea); "
        f"{len(result.unnamed)} long unnamed", t0)
    for u in result.unnamed:
        log(f"    unnamed long stream {u['name']} ({u['length_px']} px) — consider naming it")

    log("rasterizing + validating...")
    palette = riverlib.load_palette(PALETTE_JSON)
    idx = riverlib.rasterize(result.streams, land, palette, wrap_x=map_config.WRAP_X)
    n_blocks, run = riverlib.measure_2x2_blocks(idx, map_config.WRAP_X)
    drawn = int((~np.isin(idx, [riverlib.LAND, riverlib.SEA])).sum())
    log(f"  {drawn} river px; 2x2 blocks {n_blocks} (longest run {run}); vanilla ships 21/5", t0)

    if args.dry_run:
        log("dry run — nothing written.", t0)
        return 0

    MAP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out = MAP_DATA_DIR / "rivers.png"
    riverlib.write_rivers_png(out, idx, palette)
    log(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)", t0)

    state_keys = _join_state_keys(result.streams, t0)
    _write_index(result, state_keys, DERIVED_DIR / "rivers_index.json")
    log(f"wrote {DERIVED_DIR / 'rivers_index.json'} ({len(result.index)} rivers)", t0)

    if args.preview:
        _write_preview(idx, palette, DERIVED_DIR / "preview_rivers.png")
    return 0


def _write_preview(idx: np.ndarray, palette: riverlib.RiverPalette, path: Path,
                   step: int = 4) -> None:
    """Downscaled overlay. Channels are dilated so 1px rivers survive the shrink."""
    from scipy import ndimage
    river = ~np.isin(idx, [riverlib.LAND, riverlib.SEA])
    land = idx != riverlib.SEA
    riv_s = ndimage.maximum_filter(river, size=step)[::step, ::step]
    land_s = land[::step, ::step]
    rgb = np.zeros(land_s.shape + (3,), dtype=np.uint8)
    rgb[land_s] = (70, 95, 60)
    rgb[~land_s] = (25, 40, 75)
    rgb[riv_s] = (80, 190, 255)
    raster.write_rgb_png(path, rgb)
    print(f"  preview -> {path}")


if __name__ == "__main__":
    raise SystemExit(main())
