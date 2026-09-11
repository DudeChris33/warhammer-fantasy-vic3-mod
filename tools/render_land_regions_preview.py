#!/usr/bin/env python3
"""Review render: the 708 land regions, numbered, over the real TWW3 parchment.

Board #2930's dev-only naming aid, mirroring ``render_provinces_preview.py``'s
committed-data + registered-source-overlay pattern. Superseded 2026-09-05: the
first cut of this tool guessed a name per region from the nearest **real-world**
vanilla Vic3 state by longitude/latitude — a coincidental-Earth-geography
heuristic the user rejected outright (this is a fictional world; Earth
proximity means nothing). OCR of the actual named parchment
(``sources/originals/tww3_old_world_mod_parchment.png``) was tried next and
failed in practice — Tesseract garbled almost everything on this stylised,
curved-baseline hand-drawn font even after rotation sweeps, contrast
stretching and despeckling (best results were fragments like "tern"/"blast"
for "Eastern Oblast"). The user chose to drop automated guessing entirely.

This version instead **drapes the real parchment art itself** under the
numbered regions, reusing ``project_regions.py``'s existing five-crop
registration (Bretonnia, Empire, Kislev+Norsca, Dark Lands,
Badlands+Nehekhara — the same thin-plate warps #2709's QA render uses to drape
the user's hand-painted state layer) instead of computing a guess: pass the
master parchment itself as the "painting" to drape, so the actual printed
place names show through under the region tinting/numbers wherever those five
crops cover the canvas. The person doing #2931's naming pass reads real names
directly off the render — no algorithmic guess, no dictionary, no OCR.

Reads the *committed* ``map_data/provinces.png`` + ``tools/derived/
land_regions_index.json`` + ``tools/derived/provinces_index.json`` (run
``generate_land_regions.py`` first), tints every region with a spread-palette
colour and draws its number at its centroid, over the parchment drape where
the five crops reach and the plain reprojected globe everywhere else (every
placeholder/out-of-scope region, plus any drawn region outside the five crops'
coverage).

**Disclosed limitation**: 708 regions (many 1-few-px placeholder slivers, plus
plenty of thin river-bounded ribbons among the 281 drawn ones — Chris draws a
lot of state borders along rivers) cannot all carry a legible on-image label
at one fixed size — the label font scales with ``sqrt(area)`` (see
``_label_font_size``, clamped to ``LABEL_FONT_MIN..LABEL_FONT_MAX``) so a
small region still gets a small but legible number instead of either an
oversized glyph or, as the first cut of this tool did at a flat 4000 px floor,
silently no number at all (that dropped 119 of the 281 drawn regions — 42% of
them, since the median drawn region is only ~4600 px). Only regions at or
above ``MIN_LABEL_AREA`` (now 150 px — just above the sub-4px degenerate-
province floor #2927 owns) get any label. The CSV sidecar
(``land_regions_worksheet.csv``, sorted by id — see ``region_id`` below) is
the exhaustive reference for the rest, mirroring
``tools/config/sea_zone_naming_worksheet.txt``'s pattern: the image serves the
large, eyeball-able regions; the sidecar is the exhaustive list. Its
``on_parchment`` column flags whether that region's centroid falls under real
parchment art (a name can be read off the render) or the plain-globe fallback
(no real Warhammer map covers it — placeholders and any drawn region outside
the five crops). ``name`` is the one column meant for a human to actually fill
in — blank on a fresh run, and carried forward (never wiped) across re-runs so
naming progress survives a later regeneration. ``region_id`` (2026-09-05: Chris
noticed neighbouring regions had wildly different numbers and asked for this)
comes from ``worldgen.land_state_numbering.assign_state_numbers`` (board
#4188) — the same function ``generate_land_regions.py`` uses for the actual
``STATE_LAND_NNN`` ids it ships (fed identical raw centroids and the same
committed ``land_state_ids.json``, read-only here), so a number here always
means the same region there, and — since #4188 — usually the *same number*
across regens too, not just the same region.

A region split or merge (the tiny-island fix already did this once; the
border corrections Chris is drawing against ``old_world_state_regions.png``
will do it again) can still retire or newly-issue a number even under stable
assignment. So a name is never carried forward by matching the old
``region_id`` — it is relocated by ``anchor_x``/``anchor_y`` (every row's own
centroid pixel, written every run), by looking up which region owns that
physical spot on the CURRENT map. A name whose anchor pixel is no longer land
drops with a loud stderr warning rather than silently reattaching to the
wrong region.

Local-only output: embeds source pixels, so it lands under ``tools/derived/``,
which ``tools/.gitignore`` excludes from the repo — never shipped content,
purely a naming aid for #2931.

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
import project_regions as pr  # noqa: E402 — reuses its five-crop registration + drape
from worldgen import land_state_numbering, raster, schema  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"

PROVINCES_PATH = REPO_ROOT / "map_data" / "provinces.png"
PROVINCES_INDEX_PATH = DERIVED_DIR / "provinces_index.json"
LAND_REGIONS_INDEX_PATH = DERIVED_DIR / "land_regions_index.json"
#: The committed STATE-number identity authority (board #4188) —
#: generate_land_regions.py writes it; this render only ever reads it, so the
#: on-image numbers/CSV ids always match what actually ships.
LAND_STATE_IDS_PATH = DERIVED_DIR / "land_state_ids.json"

OUT_PATH = DERIVED_DIR / "land_regions_preview.png"
OUT_HALF_PATH = DERIVED_DIR / "land_regions_preview_half.png"
CSV_PATH = DERIVED_DIR / "land_regions_worksheet.csv"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: Only a region at or above this pixel area gets an on-image number label at
#: all — below this there is no room for even the smallest legible glyph.
#: Every region, regardless of size, still gets a CSV row. Many drawn regions
#: are thin river-bounded ribbons rather than round blobs (Chris, 2026-09-05:
#: "I use rivers as borders for a lot of them"), so a single fixed area floor
#: either mislabels most of them as "too small" or oversizes the number for
#: the smallest ones — hence the font also scales with area (see
#: :func:`_label_font_size`). Lowered from 4000 (which silently dropped 119 of
#: the 281 drawn regions — 42% — because the median drawn region is only 4609
#: px) to 150, just above the sub-4px degenerate-province floor #2927 owns.
MIN_LABEL_AREA = 150

#: Label font size floor/ceiling (px) and the sqrt(area) scale between them —
#: a small ribbon region gets a small but still legible number instead of
#: either an oversized glyph or no number at all.
LABEL_FONT_MIN = 12
LABEL_FONT_MAX = 30
LABEL_FONT_AREA_SCALE = 0.45

EDGE_RGB = (20, 20, 20)


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


def _parchment_drape(t0: float) -> tuple[np.ndarray, np.ndarray]:
    """The real TWW3 parchment art draped over the globe via the five registered
    crops (canvas RGB, ``placed`` mask) — reuses ``project_regions.py``'s own
    registration/warp pipeline wholesale, passing the master parchment itself
    as the thing to drape (instead of the user's separate hand-painted state
    layer) so the actual printed place names show through."""
    regs = {r.source: r for r in schema.load_registrations(pr.REGISTRATION_DIR)}
    for name in pr.FIVE_CROPS:
        if name not in regs:
            raise SystemExit(f"{name}: no committed registration record")

    master_rgb = pr.load_rgb(pr.MASTER_SOURCE)
    paint_rgba = pr.load_rgba(pr.MASTER_SOURCE)  # drape the parchment itself, not a painting
    crop_rgba = {name: pr.load_or_derive_rgba(name) for name in pr.FIVE_CROPS}
    globe_rgb = pr.load_rgb(pr.GLOBE_SOURCE)
    if globe_rgb.shape[1] != CANVAS_W or globe_rgb.shape[0] != CANVAS_H:
        raise SystemExit(f"{pr.GLOBE_SOURCE} is {globe_rgb.shape[1]}x{globe_rgb.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H}")

    master_gray = master_rgb.astype(np.float32).mean(axis=2)
    offsets = pr.crop_offsets(master_gray, crop_rgba)
    log("five parchment crops located in the master frame", t0)
    owner = pr.canvas_owner(regs, crop_rgba, offsets, paint_rgba)
    canvas_rgb, placed = pr.place_painting(0, regs, paint_rgba, crop_rgba, offsets, globe_rgb, owner)
    log(f"parchment drape placed {100.0 * placed.mean():.2f}% of the frame", t0)
    return canvas_rgb, placed


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


def _snap_centroids_onto_region(lab: np.ndarray, cx: np.ndarray, cy: np.ndarray,
                                n_regions: int) -> tuple[np.ndarray, np.ndarray]:
    """Move any centroid that landed off its own region to the nearest pixel
    that actually belongs to that region.

    The circular-mean estimator is exact for a convex blob but can place a
    concave or oddly-shaped region's "centroid" outside the region entirely
    (a crescent's mean sits in the gap) — measured at roughly 1% of regions.
    A centroid on water breaks two things downstream: the on-image number
    gets drawn off the tinted area, and the CSV worksheet's anchor_x/anchor_y
    (used to relocate a carried-forward name on the next regen) resolve to no
    region at all, silently dropping the name. One global nearest-pixel pass
    (an indexed distance transform, not a per-region search) fixes both.
    """
    cx_i = np.clip(np.round(cx).astype(np.int64), 0, lab.shape[1] - 1)
    cy_i = np.clip(np.round(cy).astype(np.int64), 0, lab.shape[0] - 1)
    on_region = lab[cy_i, cx_i] == np.arange(n_regions + 1)
    bad = np.flatnonzero(~on_region)
    bad = bad[(bad >= 1) & (bad <= n_regions)]
    if not bad.size:
        return cx, cy
    out_cx, out_cy = cx.copy(), cy.copy()
    for r in bad.tolist():
        # nearest LAND pixel to the (possibly off-region) centroid is not
        # necessarily this region's own — so search the region's own mask.
        ys, xs = np.nonzero(lab == r)
        if ys.size == 0:
            continue
        d2 = (xs.astype(np.float64) - cx[r]) ** 2 + (ys.astype(np.float64) - cy[r]) ** 2
        i = int(np.argmin(d2))
        out_cx[r], out_cy[r] = float(xs[i]), float(ys[i])
    return out_cx, out_cy


def _region_on_parchment(lab: np.ndarray, placed: np.ndarray, n_regions: int) -> np.ndarray:
    """Per region: does the majority of its area fall under real parchment art?"""
    total = np.bincount(lab.ravel(), minlength=n_regions + 1)
    on = np.bincount(lab[placed].ravel(), minlength=n_regions + 1)
    out = np.zeros(n_regions + 1, dtype=bool)
    nz = total > 0
    out[nz] = on[nz] * 2 > total[nz]
    return out


#: Prefixes marking a worksheet "name" cell as an instruction to act on
#: (Chris, 2026-09-05: "the notes in parentheses are just for me, your tasks
#: are the ones in caps") rather than an actual canon name — used to pick the
#: real name over a now-satisfied merge instruction when two carried-forward
#: names land on the same post-merge region.
_DIRECTIVE_PREFIXES = ("MERGE INTO", "SHOULD BE", "NEEDS CLOSER LOOK", "MALFORMED")


def _is_directive_name(name: str) -> bool:
    return name.strip().upper().startswith(_DIRECTIVE_PREFIXES)


def _label_font_size(area: int) -> int:
    """Region area (px) -> label font size, scaled by sqrt(area) and clamped
    to [:data:`LABEL_FONT_MIN`, :data:`LABEL_FONT_MAX`] — a small ribbon
    region gets a small but still-legible number rather than an oversized
    glyph spilling over its neighbours, and a big region gets a properly
    readable one instead of the old fixed 28px for everyone."""
    size = int(round(LABEL_FONT_AREA_SCALE * (area ** 0.5)))
    return max(LABEL_FONT_MIN, min(LABEL_FONT_MAX, size))


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
    n_land = int(prov_index["land_provinces"])
    n_regions = int(land_regions["regions"])

    # Each region's stable-id identity + per-id area, for assign_state_numbers
    # (board #4188) — the same construction generate_land_regions.py uses.
    label_to_stable_id = {int(c["label"]): int(c["id"]) for c in prov_index["cells"] if c["kind"] == "land"}
    stable_id_area = {int(c["id"]): int(c["area"]) for c in prov_index["cells"] if c["kind"] == "land"}
    region_province_ids: dict[int, set[int]] = {}
    for cell in land_regions["cells"]:
        region_province_ids[int(cell["region"])] = {label_to_stable_id[p] for p in cell["provinces"]}
    committed_state_ids = (json.loads(LAND_STATE_IDS_PATH.read_text(encoding="utf-8"))
                           if LAND_STATE_IDS_PATH.is_file() else None)

    rgb = raster.read_rgb_png(PROVINCES_PATH)
    if rgb.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{PROVINCES_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{rgb.shape[1]}x{rgb.shape[0]}")
    lab = _build_region_labels(rgb, prov_index["cells"], land_regions["cells"], n_land)
    log(f"{n_regions} region labels built", t0)

    backdrop, placed = _parchment_drape(t0)
    on_parchment = _region_on_parchment(lab, placed, n_regions)

    raw_cx, raw_cy = _region_centroids(lab, n_regions, CANVAS_W)
    # Same stable STATE-number assignment generate_land_regions.py uses (board
    # #4188), fed the same RAW (unsnapped) centroids it uses — feeding a
    # different centroid layer here would silently desync the Hilbert-ordered
    # bootstrap/fresh-number paths from what the generator actually ships.
    # Read-only: this render never writes land_state_ids.json.
    state_number, _new_index = land_state_numbering.assign_state_numbers(
        raw_cx, raw_cy, n_regions, region_province_ids, stable_id_area, committed_state_ids)
    # Snapped centroids are for on-image label placement / the CSV anchor only
    # (a circular-mean centroid can land off its own region) — never fed to
    # numbering, which must match the generator's raw centroids exactly.
    cx, cy = _snap_centroids_onto_region(lab, raw_cx, raw_cy, n_regions)

    palette = _spread_palette(n_regions)
    tint = palette[lab]
    img = backdrop.astype(np.float64)
    filled = lab > 0
    # A lighter tint than render_provinces_preview.py's 0.55 — the parchment's
    # own printed place names must stay legible underneath, which is the whole
    # point of draping the real parchment here instead of the globe.
    img[filled] = 0.75 * backdrop[filled] + 0.25 * tint[filled]
    img[ndimage.binary_dilation(_edges(lab, WRAP_X), iterations=1)] = EDGE_RGB
    img = img.clip(0, 255).astype(np.uint8)
    log("tinted overlay composited over the parchment drape", t0)

    areas = {int(c["region"]): int(c["area"]) for c in land_regions["cells"]}
    kinds = {int(c["region"]): c["kind"] for c in land_regions["cells"]}

    pil_img = Image.fromarray(img, "RGB")
    draw = ImageDraw.Draw(pil_img)
    font_cache: dict[int, ImageFont.ImageFont] = {}
    n_labelled = 0
    for region_id in range(1, n_regions + 1):
        area = areas.get(region_id, 0)
        if area < MIN_LABEL_AREA:
            continue
        size = _label_font_size(area)
        font = font_cache.setdefault(size, _load_font(size))
        x, y = float(cx[region_id]), float(cy[region_id])
        text = str(int(state_number[region_id]))
        draw.text((x, y), text, fill=(255, 255, 255), font=font, anchor="mm",
                  stroke_width=max(1, size // 14), stroke_fill=(0, 0, 0))
        n_labelled += 1
    log(f"labelled {n_labelled}/{n_regions} regions on-image (>= {MIN_LABEL_AREA} px, "
        f"font {LABEL_FONT_MIN}-{LABEL_FONT_MAX}px scaled by area)", t0)

    out_rgb = np.asarray(pil_img, dtype=np.uint8)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    raster.write_rgb_png(OUT_PATH, out_rgb)
    print(f"wrote {OUT_PATH}")
    half = pil_img.resize((CANVAS_W // 2, CANVAS_H // 2), resample=Image.LANCZOS)
    half.save(OUT_HALF_PATH, format="PNG", optimize=False, compress_level=6)
    print(f"wrote {OUT_HALF_PATH}  ({CANVAS_W // 2}x{CANVAS_H // 2})")

    # --- CSV worksheet: every region, sorted by id --------------------------
    # `region_id` is the Hilbert-ordered STATE number (matches the on-image
    # label and the actual STATE_LAND_NNN shipped by generate_land_regions.py
    # — never the raw land_regions_index.json region label), sorted ascending
    # per Chris's request (2026-09-05). `name` is the one column meant for a
    # human to fill in (the actual canon name read off the render, for #2931's
    # pass to consume).
    #
    # Ids are NOT a stable identity across runs — a region split/merge (e.g.
    # the tiny-island fix, or the border corrections Chris is still drawing
    # against old_world_state_regions.png) changes the region count, which
    # reshuffles every Hilbert rank. Matching a carried-forward name by its old
    # `region_id` would silently reattach it to a different, unrelated region.
    # Instead every row also carries `anchor_x`/`anchor_y` — the region's own
    # centroid pixel at write time — and a name is carried forward by relocating
    # that anchor pixel in the CURRENT region-label raster (`lab`): whichever
    # region now owns that physical spot on the map inherits the name, no
    # matter what id it was or is assigned. A region that vanished entirely
    # (its anchor pixel is no longer land) drops its name with a loud warning
    # instead of a silent, wrong reattachment.
    # One-time migration for rows written before anchor_x/anchor_y existed:
    # fall back to matching by the old region_id directly. Only valid because
    # the region set has not changed since that row was written (no anchor to
    # relocate by yet) — every row gets a real anchor from this run on, so
    # this branch fires at most once per pre-existing name.
    label_of_state_id = {int(state_number[r]): r for r in range(1, n_regions + 1)}

    name_by_new_label: dict[int, str] = {}
    orphaned: list[tuple[str, int, int]] = []
    conflicts: list[int] = []
    if CSV_PATH.is_file():
        with CSV_PATH.open("r", newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                ax_raw, ay_raw = row.get("anchor_x"), row.get("anchor_y")
                if ax_raw and ay_raw:
                    ax, ay = int(float(ax_raw)), int(float(ay_raw))
                    new_label = int(lab[ay, ax]) if (0 <= ax < CANVAS_W and 0 <= ay < CANVAS_H) else 0
                else:
                    old_id = int(row["region_id"]) if row.get("region_id") else None
                    new_label = label_of_state_id.get(old_id, 0) if old_id is not None else 0
                    ax, ay = -1, -1
                if new_label <= 0:
                    orphaned.append((name, ax, ay))
                    continue
                if new_label in name_by_new_label and name_by_new_label[new_label] != name:
                    conflicts.append(new_label)
                    # A merge override (tools/config/land_region_merges.json)
                    # routinely lands an instruction string ("MERGE INTO 57")
                    # on the same region as the real name it pointed at
                    # ("Marienburg") — prefer the real name over the
                    # now-satisfied instruction rather than whichever
                    # happened to be read first.
                    if _is_directive_name(name) and not _is_directive_name(name_by_new_label[new_label]):
                        continue
                    if not _is_directive_name(name) and _is_directive_name(name_by_new_label[new_label]):
                        name_by_new_label[new_label] = name
                        continue
                    continue  # both/neither are directives: first writer wins
                name_by_new_label.setdefault(new_label, name)
    if orphaned:
        print(f"WARNING: {len(orphaned)} name(s) could not be relocated (their anchor point is no "
              f"longer land) and were dropped: {[n for n, _, _ in orphaned]}", file=sys.stderr)
    if conflicts:
        print(f"WARNING: {len(conflicts)} region(s) had more than one carried-forward name land on "
              f"them (a merge) — kept the first, discarded the rest", file=sys.stderr)

    n_on_parchment = 0
    n_carried = 0
    rows = []
    for region_id in range(1, n_regions + 1):
        state_id = int(state_number[region_id])
        flag = bool(on_parchment[region_id])
        n_on_parchment += flag
        name = name_by_new_label.get(region_id, "")
        n_carried += bool(name)
        rows.append({
            "region_id": state_id,
            "name": name,
            "kind": kinds.get(region_id, ""),
            "area_px": areas.get(region_id, 0),
            "on_parchment": flag,
            "anchor_x": int(round(float(cx[region_id]))),
            "anchor_y": int(round(float(cy[region_id]))),
        })
    rows.sort(key=lambda r: r["region_id"])
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {CSV_PATH}  ({len(rows)} rows, sorted by id, "
          f"{n_on_parchment} on real parchment art, {n_carried} name(s) carried forward)")

    log(f"done: {n_regions} regions rendered", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
