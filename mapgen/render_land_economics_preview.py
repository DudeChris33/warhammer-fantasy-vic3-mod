#!/usr/bin/env python3
"""Review render: per-state land economics choropleth on the reprojected globe.

Board #3678's dev-only review aid, the sibling of ``render_land_regions_preview.py`` (which
drapes parchment and rewrites the naming sidecar, so a flag there would do both for nothing).
It reads what the game gets: the emitted ``map_data/state_regions/NN_<stem>.txt`` (parsed with
``validate_map.parse_state_file``), ``map_data/provinces.png`` and ``mapgen/derived/
provinces_index.json`` (placeholder flag), plus the economics worksheet (only to outline the
states still on defaults). The backdrop is the plain ``terraqueous_globe_reprojected.png``
(SHA-checked through ``worldgen.sources``), no parchment.

Each in-scope state is tinted **hue = subsistence building** (farm green, pasture ochre, orchard
orange, fishing village blue, rice teal) x **lightness = a fixed arable-land bin** (0-9 hatched:
below ``MASS_MIGRATION_TARGET_MIN_ARABLE_LAND``; 10-19, 20-34, 35-49, 50-79, 80-119, 120-179,
180+). The bins are fixed, not min-max, so realm renders stay comparable to each other and to
#3675's vanilla deciles. Placeholders stay untinted with a thin grey edge; states still on
defaults have a thin grey outline, states carrying worksheet values a heavy black one. Labels
sit at the snapped circular-mean centroid: line 0 the state identity (the ``id`` on the full
render, the key sans ``STATE_`` under ``--realm``), line 1 the arable number, line 2 the crop
set as short codes (table in the legend).

Local-only output (embeds source pixels): ``scratchpad/``, which the root ``.gitignore``
excludes; never shipped content.

Usage::

    python mapgen/render_land_economics_preview.py
    python mapgen/render_land_economics_preview.py --realm 02_empire    # or --realm empire
"""
from __future__ import annotations

import argparse
import colorsys
import json
import sys
import time
from pathlib import Path
from typing import Callable, NamedTuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_map  # noqa: E402
from config import map_config  # noqa: E402
from render_land_regions_preview import (  # noqa: E402
    MIN_LABEL_AREA,
    _edges,
    _label_font_size,
    _load_font,
    _region_centroids,
    _snap_centroids_onto_region,
)
from worldgen import land_economics, raster, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"  # QA renders and previews; gitignored at the repo root
STATE_REGIONS_DIR = REPO_ROOT / "map_data" / "state_regions"
PROVINCES_PATH = REPO_ROOT / "map_data" / "provinces.png"
PROVINCES_INDEX_PATH = DERIVED_DIR / "provinces_index.json"
WORKSHEET_PATH = TOOLS_DIR / "config" / "land_economics_worksheet.csv"
OUT_PATH = SCRATCH_DIR / "land_economics_preview.png"
OUT_HALF_PATH = SCRATCH_DIR / "land_economics_preview_half.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"

TINT_ALPHA = 0.65
#: Realm crops add this margin around the realm's bounding box, then upscale 2x (nearest).
REALM_MARGIN_PX = 64
REALM_SCALE = 2

#: subsistence building -> (legend name, hue in degrees)
SUBSISTENCE_HUES = {
    "building_subsistence_farm": ("farm", 125),
    "building_subsistence_pasture": ("pasture", 48),
    "building_subsistence_orchard": ("orchard", 22),
    "building_subsistence_fishing_village": ("fishing village", 212),
    "building_subsistence_rice_farm": ("rice", 175),
}
UNKNOWN_HUE = ("other", 300)

#: Short crop codes shown on labels; the legend carries this table. An id not listed falls back
#: to the first two letters after ``building_``.
CROP_CODES = {
    "building_wheat_farm": "Wh", "building_rye_farm": "Ry", "building_rice_farm": "Rc",
    "building_maize_farm": "Mz", "building_millet_farm": "Ml", "building_livestock_ranch": "Lv",
    "building_vineyard": "Vn", "building_banana_plantation": "Ba", "building_coffee_plantation": "Cf",
    "building_cotton_plantation": "Ct", "building_dye_plantation": "Dy",
    "building_opium_plantation": "Op", "building_silk_plantation": "Sk",
    "building_sugar_plantation": "Su", "building_tea_plantation": "Te",
    "building_tobacco_plantation": "Tb",
}


def crop_code(building: str) -> str:
    return CROP_CODES.get(building) or building.removeprefix("building_")[:2].capitalize()


class Field(NamedTuple):
    """One drawable per-state quantity (#3688 adds per-resource modes here)."""

    title: str
    edges: tuple[int, ...]            # lower bound of every bin after the first
    labels: tuple[str, ...]           # one per bin
    value: Callable[["validate_map.ParsedState"], int | None]


#: Bin 0 is drawn hatched; the 0-9 split is the mass-migration floor.
FIELDS = {
    "arable_land": Field(
        title="arable_land",
        edges=(10, 20, 35, 50, 80, 120, 180),
        labels=("0-9", "10-19", "20-34", "35-49", "50-79", "80-119", "120-179", "180+"),
        value=lambda st: st.arable_land,
    ),
}


def log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def tint_rgb(hue_deg: float, bin_index: int, n_bins: int) -> tuple[float, float, float]:
    """Light (low bin) to dark (high bin) at one hue; bin 0 uses the lightest step."""
    t = max(0, bin_index - 1) / max(1, n_bins - 2)
    lightness = 0.80 - 0.50 * t
    r, g, b = colorsys.hls_to_rgb(hue_deg / 360.0, lightness, 0.70)
    return (r * 255.0, g * 255.0, b * 255.0)


def bin_of(field: Field, value: int | None) -> int:
    if value is None:
        return 0
    return sum(1 for e in field.edges if value >= e)


def load_states() -> tuple[list["validate_map.ParsedState"], dict[str, str]]:
    """Every land state in file order, and ``key -> state-file stem`` (``02_empire``)."""
    states: list[validate_map.ParsedState] = []
    stem_of: dict[str, str] = {}
    for path in sorted(STATE_REGIONS_DIR.glob("*.txt")):
        if path.name.startswith("99_"):
            continue
        for st in validate_map.parse_state_file(path):
            states.append(st)
            stem_of[st.key] = path.stem
    return states, stem_of


def build_state_labels(rgb: np.ndarray, states: list["validate_map.ParsedState"]) -> np.ndarray:
    """Per-pixel 1-based index into ``states`` (0 = sea/lake/unclaimed), from province colours."""
    code = ((rgb[..., 0].astype(np.int64) << 16) | (rgb[..., 1].astype(np.int64) << 8)
            | rgb[..., 2].astype(np.int64))
    pairs = sorted(((c[0] << 16) | (c[1] << 8) | c[2], i + 1)
                   for i, st in enumerate(states) for c in st.provinces)
    keys = np.array([p[0] for p in pairs], dtype=np.int64)
    vals = np.array([p[1] for p in pairs], dtype=np.int64)
    pos = np.searchsorted(keys, code)
    pos[pos >= len(keys)] = 0
    return np.where(keys[pos] == code, vals[pos], 0)


def resolve_realm(arg: str, stem_of: dict[str, str]) -> str:
    stems = sorted(set(stem_of.values()))
    for s in stems:
        if s == arg or s.split("_", 1)[-1] == arg:
            return s
    raise SystemExit(f"no state file matches --realm {arg!r}; realms with states: {stems}")


def legend_height(field: Field, used_codes: dict[str, str], unit: int) -> int:
    """Height of the box ``draw_legend`` draws (so the caller can keep it inside the image)."""
    swatch = unit * 3
    return (unit * 3 + len(SUBSISTENCE_HUES) * (swatch + unit // 3) + unit * 4
            + (len(used_codes) // 4 + 1) * unit * 2)


def draw_legend(draw: ImageDraw.ImageDraw, field: Field, used_codes: dict[str, str],
                origin: tuple[int, int], unit: int) -> None:
    font = _load_font(max(10, unit))
    small = _load_font(max(9, unit * 4 // 5))
    swatch = unit * 3
    x0, y0 = origin
    hues = list(SUBSISTENCE_HUES.values())
    codes = sorted(used_codes.items(), key=lambda kv: kv[1])
    width = unit * 4 + swatch * (len(field.labels) + 1) + unit * 14
    height = legend_height(field, used_codes, unit)
    draw.rectangle((x0, y0, x0 + width, y0 + height), fill=(18, 22, 28), outline=(220, 220, 220))
    draw.text((x0 + unit, y0 + unit // 2),
              f"{field.title}: hue = subsistence building, lightness = bin", fill=(255, 255, 255), font=font)
    y = y0 + unit * 2
    for j, lab in enumerate(field.labels):
        # centre each bin label over its swatch so adjacent labels ("120-179", "180+") never touch
        lw = draw.textlength(lab, font=small)
        draw.text((x0 + unit * 9 + j * swatch + (swatch - lw) / 2, y), lab, fill=(220, 220, 220), font=small)
    y += unit * 2
    n = len(field.labels)
    for name, hue in hues:
        draw.text((x0 + unit, y + swatch // 6), name, fill=(255, 255, 255), font=small)
        for j in range(n):
            r, g, b = (int(v) for v in tint_rgb(hue, j, n))
            x = x0 + unit * 9 + j * swatch
            draw.rectangle((x, y, x + swatch - 2, y + swatch - 2), fill=(r, g, b))
            if j == 0:
                for k in range(0, swatch, 4):
                    draw.line((x + k, y, x, y + k), fill=(60, 60, 60))
        y += swatch + unit // 3
    y += unit // 2
    draw.text((x0 + unit, y), "hatched = below the mass-migration floor (arable 0-9); "
              "grey outline = still on defaults; black = worksheet values", fill=(220, 220, 220), font=small)
    y += unit * 2
    draw.text((x0 + unit, y), "crops: " + "  ".join(f"{c}={n.removeprefix('building_')}" for n, c in codes),
              fill=(220, 220, 220), font=small)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--field", choices=sorted(FIELDS), default="arable_land",
                    help="quantity to draw (default arable_land)")
    ap.add_argument("--realm", metavar="STEM",
                    help="crop to that state file's bounding box + 64 px at 2x (e.g. 02_empire or empire)")
    args = ap.parse_args(argv)
    field = FIELDS[args.field]
    t0 = time.time()

    for path in (PROVINCES_PATH, PROVINCES_INDEX_PATH):
        if not path.is_file():
            raise SystemExit(f"{path} not found - run generate_provinces.py / generate_land_regions.py first")
    states, stem_of = load_states()
    if not states:
        raise SystemExit(f"no state files under {STATE_REGIONS_DIR}")
    prov_index = json.loads(PROVINCES_INDEX_PATH.read_text(encoding="utf-8"))
    placeholder_colors = {tuple(int(v) for v in c["color"]) for c in prov_index["cells"] if c.get("placeholder")}
    is_placeholder = [bool(st.provinces) and all(c in placeholder_colors for c in st.provinces) for st in states]
    sheet = (land_economics.load_economics_worksheet(WORKSHEET_PATH) if WORKSHEET_PATH.is_file() else None)
    has_values = [(not ph) and sheet is not None and st.key in sheet.rows and sheet.rows[st.key].has_values()
                  for st, ph in zip(states, is_placeholder)]

    realm_stem = resolve_realm(args.realm, stem_of) if args.realm else None
    rgb = raster.read_rgb_png(PROVINCES_PATH)
    if rgb.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{PROVINCES_PATH}: expected {CANVAS_W}x{CANVAS_H}, got {rgb.shape[1]}x{rgb.shape[0]}")
    lab = build_state_labels(rgb, states)
    del rgb
    n = len(states)
    log(f"{n} land states indexed ({sum(is_placeholder)} placeholder)", t0)

    backdrop = sources.load_source_image(GLOBE_SOURCE)
    if backdrop.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{GLOBE_SOURCE} is {backdrop.shape[1]}x{backdrop.shape[0]}, expected the canvas frame")
    img = backdrop.copy()

    # Per-state colour (hue x bin) and hatching flag.
    lut = np.zeros((n + 1, 3), dtype=np.float32)
    hatched = np.zeros(n + 1, dtype=bool)
    tinted = np.zeros(n + 1, dtype=bool)
    for i, st in enumerate(states, start=1):
        if is_placeholder[i - 1]:
            continue
        _, hue = SUBSISTENCE_HUES.get(st.subsistence_building or "", UNKNOWN_HUE)
        b = bin_of(field, field.value(st))
        lut[i] = tint_rgb(hue, b, len(field.labels))
        tinted[i] = True
        hatched[i] = b == 0
    filled = tinted[lab]
    ys, xs = np.nonzero(filled)
    colour = lut[lab[ys, xs]]
    stripe = ((xs + ys) // 5) % 2 == 0
    hat = hatched[lab[ys, xs]] & stripe
    colour[hat] = colour[hat] * 0.45
    img[ys, xs] = (backdrop[ys, xs] * (1.0 - TINT_ALPHA) + colour * TINT_ALPHA).clip(0, 255).astype(np.uint8)
    log("choropleth composited over the reprojected globe", t0)

    # Edges: placeholders thin grey, default states thin dark grey, worksheet states heavy black.
    edge = _edges(lab, WRAP_X)
    state_class = np.zeros(n + 1, dtype=np.int8)  # 1 placeholder, 2 default, 3 worksheet
    for i in range(1, n + 1):
        state_class[i] = 1 if is_placeholder[i - 1] else (3 if has_values[i - 1] else 2)
    cls = state_class[lab]
    img[edge & (cls == 1)] = (150, 150, 150)
    img[edge & (cls == 2)] = (70, 70, 70)
    heavy = ndimage.binary_dilation(edge & (cls == 3), iterations=2)
    img[heavy] = (0, 0, 0)

    # Crop + upscale for --realm; labels are drawn after, so text stays crisp.
    scale, ox, oy = 1, 0, 0
    if realm_stem is not None:
        member = np.array([stem_of[st.key] == realm_stem for st in states])
        mask = np.concatenate([[False], member])[lab]
        yy, xx = np.nonzero(mask)
        if yy.size == 0:
            raise SystemExit(f"{realm_stem} has no states; realms with states: {sorted(set(stem_of.values()))}")
        x0 = max(0, int(xx.min()) - REALM_MARGIN_PX)
        x1 = min(CANVAS_W, int(xx.max()) + 1 + REALM_MARGIN_PX)
        y0 = max(0, int(yy.min()) - REALM_MARGIN_PX)
        y1 = min(CANVAS_H, int(yy.max()) + 1 + REALM_MARGIN_PX)
        scale, ox, oy = REALM_SCALE, x0, y0
        pil = Image.fromarray(img[y0:y1, x0:x1], "RGB").resize(
            ((x1 - x0) * scale, (y1 - y0) * scale), resample=Image.NEAREST)
    else:
        pil = Image.fromarray(img, "RGB")
    del img, backdrop

    raw_cx, raw_cy = _region_centroids(lab, n, CANVAS_W)
    cx, cy = _snap_centroids_onto_region(lab, raw_cx, raw_cy, n)
    areas = np.bincount(lab.ravel(), minlength=n + 1)
    draw = ImageDraw.Draw(pil)
    font_cache: dict[int, object] = {}
    used_codes: dict[str, str] = {}
    n_labelled = 0
    for i, st in enumerate(states, start=1):
        if is_placeholder[i - 1] or int(areas[i]) < MIN_LABEL_AREA:
            continue
        if realm_stem is not None and stem_of[st.key] != realm_stem:
            continue
        x, y = (float(cx[i]) - ox) * scale, (float(cy[i]) - oy) * scale
        if not (0 <= x < pil.width and 0 <= y < pil.height):
            continue
        size = max(9, int(_label_font_size(int(areas[i])) * 0.7))
        font = font_cache.setdefault(size, _load_font(size))
        codes = " ".join(crop_code(r) for r in st.arable_resources)
        for r in st.arable_resources:
            used_codes[r] = crop_code(r)
        ident = st.key.removeprefix("STATE_").replace("_", " ") if realm_stem is not None else str(st.id)
        value = field.value(st)
        lines = [str(value) if value is not None else "?"]
        scaled_area = int(areas[i]) * scale * scale
        if scaled_area >= 1500:
            lines.insert(0, ident)
        if scaled_area >= 4500:
            lines.append(codes)
        lh = int(size * 1.1)
        y_top = y - lh * (len(lines) - 1) / 2.0
        for k, text in enumerate(lines):
            draw.text((x, y_top + k * lh), text, fill=(255, 255, 255), font=font, anchor="mm",
                      stroke_width=max(1, size // 12), stroke_fill=(0, 0, 0))
        n_labelled += 1
    log(f"labelled {n_labelled} states", t0)

    unit = max(14, pil.height // 90)
    draw_legend(draw, field, used_codes,
                (unit, pil.height - legend_height(field, used_codes, unit) - unit), unit)

    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    if realm_stem is None:
        out, half = OUT_PATH, OUT_HALF_PATH
        raster.write_rgb_png(out, np.asarray(pil, dtype=np.uint8))
        pil.resize((CANVAS_W // 2, CANVAS_H // 2), resample=Image.LANCZOS).save(
            half, format="PNG", optimize=False, compress_level=6)
        print(f"wrote {out}")
        print(f"wrote {half}  ({CANVAS_W // 2}x{CANVAS_H // 2})")
    else:
        out = SCRATCH_DIR / f"land_economics_preview_{realm_stem}.png"
        raster.write_rgb_png(out, np.asarray(pil, dtype=np.uint8))
        print(f"wrote {out}  ({pil.width}x{pil.height})")
    n_default = sum(1 for ph, hv in zip(is_placeholder, has_values) if not ph and not hv)
    log(f"done: {n - sum(is_placeholder)} in-scope states ({n_default} on defaults, "
        f"{sum(has_values)} with worksheet values)", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
