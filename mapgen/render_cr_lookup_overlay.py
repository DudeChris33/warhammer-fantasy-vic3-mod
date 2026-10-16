#!/usr/bin/env python3
"""QA render (board #4364): the TWW3 ``cr_oldworld_lookup`` region partition
draped onto this mod's canvas through the single whole-master
``tww3_old_world_mod_parchment_full`` registration.

**Dev-only, gitignored output.** Every artifact this writes lands in
``scratchpad/`` and is ignored there (root ``.gitignore``); nothing it reads from
``sources/cr_oldworld_campaign/`` — itself gitignored —
ever reaches a committed file. This script produces *evidence for a human*: a
render Chris looks at, plus a printed fit report. It is not pipeline input, it
emits no map data, and no committed bitmap or state file depends on it.

Why this is possible at all
---------------------------
``sources/cr_oldworld_campaign/campaign_maps/cr_oldworld_map_1/cr_oldworld_map.png`` (8192²) is a
confirmed **exact 2x rescale** of ``sources/originals/tww3_old_world_mod_parchment.png``
(4096²) — zero crop, zero offset (established by FFT phase correlation with a
decisive scale sweep at 2.00; ``--verify-correspondence`` re-confirms it cheaply).
``cr_oldworld_lookup.bmp`` shares that 8192² campaign-map frame. So the lookup
lives in the SAME master frame the ``_full`` registration already places — at
exactly twice its resolution. Placing the lookup is therefore the existing
``mapgen/project_regions_unified.py`` drape with one extra factor:

    canvas px --(fit.to_source_px)--> master px --(x MASTER_TO_LOOKUP_SCALE)--> lookup px

This script is the direct analogue of that one; read it first.

PROVISIONAL FOUNDATION — READ BEFORE TRUSTING THIS RENDER
---------------------------------------------------------
``mapgen/registration/tww3_old_world_mod_parchment_full.json`` self-declares
"PROVISIONAL until the user accepts the diagnostic render" in its own ``notes``.
That is a real, disclosed dependency, not solid ground: **this overlay is built
on a registration that is itself still awaiting acceptance. If that placement
moves, this render moves with it.** The live landmark count is read off the
record and printed in the fit report rather than hardcoded here, because the
record is re-fit from its seed as dots are added.

The 8193-row tie
----------------
``cr_oldworld_lookup.bmp`` is 8192x**8193** (32bpp BI_RGB), and it is a genuine
tie which extra row is the padding: row 0 duplicates row 1, and row 8192
duplicates row 8191. Both readings are equally defensible. This script drops
row 0 and uses rows 1..8192 (:data:`DROP_ROW`) — the prior tentative choice,
kept for continuity — and the fit report **discloses** the resulting +-1
lookup-px (0.5 master-px) ambiguity, converted to actual canvas px through this
registration's own measured master->canvas scale. It is sub-pixel at canvas
resolution; see :func:`row_tie_canvas_px`.

Scope filter (Chris, 2026-09-12)
--------------------------------
**Land not drawn in ``sources/originals/tww3_old_world_mod_parchment_cropped.png``
is out of scope.** That file is the same 4096² master frame carrying the same
art, with everything this mod does not cover erased to alpha 0 — an irregular
*interior* shape, so its bounding box proves nothing and the **alpha channel** is
the only real extent. Every canvas pixel this render would place is additionally
tested against that alpha, through the same ``canvas -> master`` transform, and a
pixel landing on an erased master pixel is dropped to void. This is a second,
distinct exclusion from the hull footprint: the footprint bound says "the
registration could not place this point at all", the scope mask says "it placed
fine, on ground this mod does not cover". Both counts are reported separately in
the fit report. Shares :data:`SCOPE_SOURCE` and the ``alpha > 0`` threshold with
``mapgen/tww3_name_lookup.py`` (#4363) — the two tools warp through the identical
registration and master->lookup scale and must agree about the same pixel.

Colour handling (both disclosed in the fit report and the legend)
-----------------------------------------------------------------
* **Black (``000000``) is void**, not a region: the campaign map's sea and
  off-map. 138 TSV rows also carry colour ``000000``, so those keys are not
  paintable either. Black renders as nothing at all — the globe shows through.
* **Colour ``600954`` has NO TSV row** despite being the single largest
  non-black area in the bitmap. It is rendered in a distinct neutral grey
  (:data:`UNKEYED_RGB`) and labelled "unkeyed" in the legend, never silently
  painted as if it were a named region.

Usage::

    python mapgen/render_cr_lookup_overlay.py --fills
    python mapgen/render_cr_lookup_overlay.py --borders-only --coast
    python mapgen/render_cr_lookup_overlay.py --verify-correspondence
    python mapgen/render_cr_lookup_overlay.py --verify-lookup-coregistration
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen.raster import rgb_zero_transparent  # noqa: E402
from config import map_config  # noqa: E402
from worldgen import reproject, schema  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402

# The lookup is 8192x8193 and the campaign map 8192x8192 — both far past
# Pillow's decompression-bomb guard, which is aimed at hostile uploads, not at
# local reference art whose dimensions we assert explicitly below.
Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
SOURCES_DIR = REPO_ROOT / "sources"
DERIVED_DIR = TOOLS_DIR / "derived"
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"  # QA renders and previews; gitignored at the repo root
REGISTRATION_DIR = TOOLS_DIR / "registration"

#: The reference dataset. Gitignored (repo .gitignore line "sources/cr_oldworld_campaign")
#: and absent on most devices — see :func:`require_dataset` for the clean skip.
DATASET_DIR = SOURCES_DIR / "cr_oldworld_campaign"
LOOKUP_BMP = DATASET_DIR / "cr_oldworld_lookup" / "cr_oldworld_lookup.bmp"
LOOKUP_TSV = DATASET_DIR / "cr_oldworld_lookup" / "cr_oldworld_campaign.tsv"
CAMPAIGN_MAP_PNG = DATASET_DIR / "campaign_maps" / "cr_oldworld_map_1" / "cr_oldworld_map.png"

#: The master frame the ``_full`` registration places (4096², committed source).
PARCHMENT_SOURCE = "tww3_old_world_mod_parchment.png"
#: The reprojected globe that IS the canvas frame — the backdrop this drapes over.
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
#: The plain globe with a magenta coastline drawn on it — a reference line, not the backdrop.
COAST_SOURCE = sources_mod.source_ref("coast_trace")

#: The registration record this projects through (see the PROVISIONAL note above).
FULL_SOURCE = "tww3_old_world_mod_parchment_full.png"
#: The scope authority (Chris, 2026-09-12): the same master frame and the same art
#: as ``FULL_SOURCE``'s own source, with every area this mod does not cover erased
#: to alpha 0. Its **alpha channel** is the extent — the opaque region is an
#: irregular interior shape whose bounding box is the whole image. Identical
#: constant and threshold to ``mapgen/tww3_name_lookup.py`` (#4363).
SCOPE_SOURCE = "tww3_old_world_mod_parchment_cropped.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
#: The master frame's own size, in master px. The registration's control points
#: are expressed in it, and the lookup is exactly this x MASTER_TO_LOOKUP_SCALE.
MASTER_SIZE = 4096
#: Confirmed by FFT phase correlation (scale sweep decisive at 2.00, zero offset);
#: re-confirmed cheaply by --verify-correspondence.
MASTER_TO_LOOKUP_SCALE = 2.0
#: The lookup's true region raster size, after the duplicate row is dropped.
LOOKUP_SIZE = int(MASTER_SIZE * MASTER_TO_LOOKUP_SCALE)
#: Which of the two duplicate rows to drop — a genuine tie, disclosed in the report.
DROP_ROW = 0
#: Horizontal lookup-px offset applied when sampling. Deliberately **0** even though
#: --verify-correspondence measures a repeatable +1: that is half a master px of
#: resample-convention bias (~0.2 canvas px through this registration), the same
#: order as the 8193-row tie and far below what a rendered overlay can resolve.
#: Correcting it would imply a precision this placement does not have. Disclosed in
#: the fit report rather than silently applied.
LOOKUP_OFFSET_X = 0
#: --verify-correspondence sweeps lookup-px offsets over +-this, and accepts a best
#: offset within OFFSET_TOLERANCE_LOOKUP_PX of zero (see that function's docstring).
OFFSET_SWEEP_LOOKUP_PX = 3
OFFSET_TOLERANCE_LOOKUP_PX = 1

#: --verify-lookup-coregistration's master-px shift sweep (see that function).
COREG_SWEEP_PX = (-512, -256, -128, -64, -32, -16, 0, 16, 32, 64, 128, 256, 512)
#: Shifts at or below this are inside the interior erosion's own slack — not
#: trusted to break a tie for where the peak sits.
COREG_FINE_PX = 16
#: Shifts at or beyond this must have lost most of the contrast, or the sweep is
#: flat and proves nothing either way.
COREG_FAR_PX = 256
COREG_DECAY_MAX = 0.70

#: Void: the campaign map's sea / off-map, and the colour of 138 unpaintable TSV rows.
VOID_RGB = (0, 0, 0)
#: The single largest non-black lookup colour, which has no TSV row at all.
UNKEYED_HEX = "600954"
#: How an unkeyed region renders — a flat neutral grey, never a region-like colour.
UNKEYED_RGB = (128, 128, 128)
#: --borders-only line colour, and the cyan the --coast reference line is drawn in.
BORDER_RGB = (255, 0, 255)
COAST_RGB = (0, 255, 255)

#: Row block for warp evaluation — bounds the piecewise fit's temporaries.
ROW_BLOCK = 64
#: Extrapolation past the OUTER hull edge only, matching project_regions_unified.py's
#: user-accepted default (2026-09-12). Not a real correspondence — a QA convenience
#: for judging content just past today's dot coverage.
HULL_BUFFER_PX_DEFAULT = 50.0

#: Zoom crops, centred on real committed hub anchors (mapgen/config/hub_worksheet.json)
#: so each crop lands on ground this mod has already named — high-signal for a verdict.
HUB_WORKSHEET = TOOLS_DIR / "config" / "hub_worksheet.json"
ZOOM_HUBS = ("Altdorf", "Middenheim")
ZOOM_HALF = 420

OUT_PREFIX = "cr_lookup_overlay"


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Dataset presence / loading
# ---------------------------------------------------------------------------

def require_dataset() -> None:
    """Clean-skip when the reference dataset is not on this device.

    The ``validate_map._check_canon_cities`` idiom: a gitignored local working
    file's absence is the expected state on most devices, not an error, so this
    exits 0 with a plain explanation rather than raising.
    """
    if DATASET_DIR.is_dir() and LOOKUP_BMP.is_file() and LOOKUP_TSV.is_file():
        return
    log(f"{DATASET_DIR.relative_to(REPO_ROOT)}: reference dataset not present on "
        f"this device — dev-only render, skipping")
    sys.exit(0)


def load_source_rgb(name: str) -> np.ndarray:
    arr = sources_mod.read_source_rgba(name, SOURCES_DIR, allow_empty=True)
    if arr is None:
        raise SystemExit(f"sources/{name} is missing")
    return arr[..., :3].copy()


def load_lookup() -> np.ndarray:
    """The region raster as ``(8192, 8192, 3)`` uint8, duplicate row dropped.

    Hard-errors (never silently adapts) if the on-disk dimensions are not the
    expected 8192x8193 — a differently-sized export is a different dataset and
    every scale/offset constant here would be wrong for it.
    """
    with Image.open(LOOKUP_BMP) as im:
        w, h = im.size
        if (w, h) != (LOOKUP_SIZE, LOOKUP_SIZE + 1):
            raise SystemExit(
                f"{LOOKUP_BMP.name} is {w}x{h}, expected {LOOKUP_SIZE}x{LOOKUP_SIZE + 1} "
                f"(8192 region rows + 1 duplicate padding row). A different size is a "
                f"different export — the master->lookup scale and the row-tie choice "
                f"documented in this script would not apply.")
        arr = rgb_zero_transparent(im)
    keep = np.arange(arr.shape[0]) != DROP_ROW
    arr = arr[keep].copy()
    if arr.shape != (LOOKUP_SIZE, LOOKUP_SIZE, 3):
        raise SystemExit(f"lookup is {arr.shape} after dropping row {DROP_ROW}, "
                         f"expected ({LOOKUP_SIZE}, {LOOKUP_SIZE}, 3)")
    return arr


def load_scope_mask() -> np.ndarray:
    """``(4096, 4096)`` bool: True where this mod's scope covers the master frame.

    Read from :data:`SCOPE_SOURCE`'s **alpha channel** (``alpha > 0``, matching
    ``mapgen/tww3_name_lookup.py``). Required, not optional: without it the render
    would keep painting the out-of-scope land Chris ruled out. A palette+
    transparency PNG is converted via ``RGBA`` rather than read raw, so the
    transparency reaches the alpha band however Pillow stored it.
    """
    path = sources_mod.resolve_source_path(SCOPE_SOURCE, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(
            f"sources/{SCOPE_SOURCE} is missing — it is the scope authority "
            f"(Chris, 2026-09-12: land not drawn there is out of scope) and this "
            f"render must not paint regions without it")
    with Image.open(path) as im:
        if im.size != (MASTER_SIZE, MASTER_SIZE):
            raise SystemExit(
                f"{SCOPE_SOURCE} is {im.size[0]}x{im.size[1]}, expected "
                f"{MASTER_SIZE}x{MASTER_SIZE} — the scope mask must share the master "
                f"frame this registration places")
        alpha = np.asarray(im.convert("RGBA"), dtype=np.uint8)[..., 3]
    return alpha > 0


def load_region_keys() -> dict[str, str]:
    """``hex -> region key`` from the TSV, excluding every black-colour row.

    The file is a TWW3 table export: a real header row, then a ``#``-prefixed
    metadata row (``#regions_tables;0;db/regions_tables/cr_oldworld_campaign``),
    then the data. The colour lives in the last column
    (``unnamed colour group_1``). Rows whose colour is ``000000`` are dropped:
    black is void in the bitmap, so those keys are not paintable and mapping
    them would paint sea.
    """
    keys: dict[str, str] = {}
    black_rows = 0
    with open(LOOKUP_TSV, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader, None)
        if not header or header[0].strip() != "key":
            raise SystemExit(f"{LOOKUP_TSV.name}: unexpected header {header!r}")
        for row in reader:
            if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
                continue  # the metadata row, and any blank row
            key = row[0].strip()
            colour = row[-1].strip().upper()
            if not colour:
                continue
            if colour == "000000":
                black_rows += 1
                continue
            keys[colour] = key
    load_region_keys.black_rows = black_rows  # type: ignore[attr-defined]
    return keys


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def footprint_box(reg: schema.SourceRegistration, pad: float = 0.0) -> tuple[int, int, int, int]:
    """The registration's canvas footprint, grown by ``pad`` and clamped."""
    x0, y0, x1, y1 = reg.footprint
    return (max(0, int(np.floor(x0 - pad))), max(0, int(np.floor(y0 - pad))),
            min(CANVAS_W, int(np.ceil(x1 + pad))), min(CANVAS_H, int(np.ceil(y1 + pad))))


def master_to_canvas_scale(reg: schema.SourceRegistration) -> float:
    """Canvas px per master px, measured from the record's own footprint width.

    Not a constant: it is whatever the live registration places the 4096-px-wide
    master at. Used only to state the row-tie ambiguity in canvas px.
    """
    x0, _, x1, _ = reg.footprint
    return (x1 - x0) / MASTER_SIZE


def row_tie_canvas_px(reg: schema.SourceRegistration) -> float:
    """The 8193-row tie expressed in canvas px through THIS registration.

    Dropping row 0 versus row 8192 shifts the whole region raster by 1 lookup px,
    i.e. ``1 / MASTER_TO_LOOKUP_SCALE`` = 0.5 master px, i.e. that times the
    measured master->canvas scale.
    """
    return (1.0 / MASTER_TO_LOOKUP_SCALE) * master_to_canvas_scale(reg)


def place_lookup(fit, box: tuple[int, int, int, int], lookup: np.ndarray,
                 scope: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """Warp the lookup into canvas space. Returns ``(label_rgb, placed, excluded)``.

    ``placed`` is True where the warp landed inside the master frame AND inside
    this mod's scope (:data:`SCOPE_SOURCE`'s alpha, Chris 2026-09-12) AND the
    sampled lookup colour is not void-black — so neither sea/off-map nor
    out-of-scope land ever counts as placed content.

    ``excluded`` reports the **scope** exclusion specifically (distinct from the
    hull-footprint bound, which simply never enters this loop): ``px`` is how many
    canvas pixels would have been painted but were dropped, and ``colours`` is the
    set of packed region colours that appeared in them — some of which may also
    survive elsewhere, so it is an upper bound on regions removed outright.

    **Nearest sampling, by direct integer indexing.** Unlike
    ``project_regions_unified.place_painting`` (which calls
    ``reproject.resample(..., order=0)`` per channel), this indexes the lookup
    array directly at the rounded coordinate. For a *label* image the two are
    numerically identical — ``map_coordinates(order=0)`` is a rounded lookup —
    but resample would first need three float32 copies of a 67-megapixel plane
    (~800 MB) to sample colours that must stay exact anyway. The registration
    API (``fit.to_source_px``) is used exactly as everywhere else; only the
    final sample is done by hand.
    """
    label = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)
    placed = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
    oos_px = 0
    oos_colours: set[int] = set()

    bx0, by0, bx1, by1 = box
    gx = (np.arange(bx0, bx1, dtype=np.float64) + 0.5)[None, :]
    for yb in range(by0, by1, ROW_BLOCK):
        ye = min(yb + ROW_BLOCK, by1)
        gy = (np.arange(yb, ye, dtype=np.float64) + 0.5)[:, None]
        gxb = np.broadcast_to(gx, (ye - yb, bx1 - bx0))
        gyb = np.broadcast_to(gy, (ye - yb, bx1 - bx0))
        mx, my = fit.to_source_px(gxb, gyb)

        in_master = (mx >= 0) & (mx <= MASTER_SIZE - 1) & (my >= 0) & (my <= MASTER_SIZE - 1)
        if not in_master.any():
            continue
        lx = np.clip(np.rint(mx * MASTER_TO_LOOKUP_SCALE) + LOOKUP_OFFSET_X,
                     0, LOOKUP_SIZE - 1).astype(np.int32)
        ly = np.clip(np.rint(my * MASTER_TO_LOOKUP_SCALE), 0, LOOKUP_SIZE - 1).astype(np.int32)
        block = lookup[ly, lx]

        non_void = (block[..., 0] != VOID_RGB[0]) | (block[..., 1] != VOID_RGB[1]) \
            | (block[..., 2] != VOID_RGB[2])
        paintable = in_master & non_void

        # Scope gate (Chris, 2026-09-12): the master pixel this canvas point maps
        # to must be drawn in SCOPE_SOURCE. Indices are clipped only so the gather
        # is legal off-frame; in_master already excludes those points.
        mxi = np.clip(np.rint(np.where(in_master, mx, 0.0)), 0, MASTER_SIZE - 1).astype(np.int32)
        myi = np.clip(np.rint(np.where(in_master, my, 0.0)), 0, MASTER_SIZE - 1).astype(np.int32)
        in_scope = scope[myi, mxi]

        dropped = paintable & ~in_scope
        if dropped.any():
            oos_px += int(dropped.sum())
            oos_colours.update(np.unique(pack(block[dropped])).tolist())

        valid = paintable & in_scope
        if not valid.any():
            continue
        label[yb:ye, bx0:bx1][valid] = block[valid]
        placed[yb:ye, bx0:bx1] |= valid

    return label, placed, {"px": oos_px, "colours": oos_colours}


def pack(label: np.ndarray) -> np.ndarray:
    """RGB -> one uint32 per pixel, so regions can be counted with np.unique."""
    return ((label[..., 0].astype(np.uint32) << 16)
            | (label[..., 1].astype(np.uint32) << 8)
            | label[..., 2].astype(np.uint32))


def unpack_hex(packed: int) -> str:
    return f"{int(packed):06X}"


def compose_fills(label: np.ndarray, placed: np.ndarray, globe_rgb: np.ndarray,
                  unkeyed_mask: np.ndarray) -> np.ndarray:
    """Region colours draped over the globe; unkeyed regions flattened to grey."""
    out = globe_rgb.copy()
    out[placed] = label[placed]
    out[unkeyed_mask] = UNKEYED_RGB
    return out


def extract_borders(label: np.ndarray, placed: np.ndarray,
                    globe_rgb: np.ndarray) -> tuple[np.ndarray, int]:
    """Post-warp boundary extraction: a placed pixel whose right/down neighbour
    carries a different region colour is a border pixel.

    Post-warp for the same reason ``project_regions_unified.extract_colors``
    is: the boundary we want is the boundary of what actually landed on the
    canvas, and a single neighbour comparison over the finished label image is
    cheaper and simpler than warping a pre-extracted edge layer. A placed pixel
    adjacent to un-placed void also counts — that is the campaign map's own
    coastline, which is exactly the line worth judging.
    """
    p = pack(label)
    edge = np.zeros(placed.shape, dtype=bool)
    diff_x = (p[:, :-1] != p[:, 1:]) & (placed[:, :-1] | placed[:, 1:])
    edge[:, :-1] |= diff_x
    edge[:, 1:] |= diff_x
    diff_y = (p[:-1, :] != p[1:, :]) & (placed[:-1, :] | placed[1:, :])
    edge[:-1, :] |= diff_y
    edge[1:, :] |= diff_y
    edge &= placed
    out = globe_rgb.copy()
    out[edge] = BORDER_RGB
    return out, int(edge.sum())


def overlay_coast(canvas_rgb: np.ndarray) -> int:
    """Draw the coasts reference PNG's drawn line onto ``canvas_rgb`` in cyan.

    The line is matched as **any non-black pixel**, not as one hardcoded colour:
    the file is a black ground with a single drawn line on it, and the line's
    colour has already changed once (``project_regions_unified.py`` still looks
    for magenta, which silently matches zero pixels in the current export — a
    hardcoded colour here fails open, drawing no reference line at all while
    reporting success).

    The source is a gitignored local file, so its absence is the expected state
    on most devices: that is a skip with a note, not an error.
    """
    rgba = sources_mod.read_source_rgba(COAST_SOURCE, SOURCES_DIR, allow_empty=True)
    if rgba is None:
        log(f"  coast: sources/{COAST_SOURCE} not present on this device — "
            f"reference line skipped")
        return 0
    coasts = rgba[..., :3]
    if coasts.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{COAST_SOURCE} is {coasts.shape[1]}x{coasts.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H}")
    line = coasts.any(axis=2)
    canvas_rgb[line] = COAST_RGB
    return int(line.sum())


# ---------------------------------------------------------------------------
# Legend + crops
# ---------------------------------------------------------------------------

def draw_legend(canvas_rgb: np.ndarray, lines: list[tuple[tuple[int, int, int] | None, str]],
                scale: int = 4) -> None:
    """Stamp a small legend into the top-left of the canvas (in place).

    Rendered at 1x with the default bitmap font and upscaled NEAREST, so it is
    legible on an 8192-px-wide frame without a font dependency.
    """
    pad, row_h, sw = 6, 12, 10
    w = 8 + sw + 6 + max(int(6.2 * len(text)) for _, text in lines) + 8
    h = pad * 2 + row_h * len(lines)
    tile = Image.new("RGB", (w, h), (16, 16, 16))
    d = ImageDraw.Draw(tile)
    for i, (swatch, text) in enumerate(lines):
        y = pad + i * row_h
        if swatch is not None:
            d.rectangle([8, y + 1, 8 + sw, y + 1 + sw], fill=swatch, outline=(220, 220, 220))
        d.text((8 + sw + 6, y), text, fill=(235, 235, 235))
    big = np.asarray(tile.resize((w * scale, h * scale), Image.NEAREST), dtype=np.uint8)
    bh, bw = big.shape[:2]
    canvas_rgb[24:24 + bh, 24:24 + bw] = big


def hub_anchors() -> dict[str, tuple[int, int]]:
    """Named canvas anchors from the committed hub worksheet (crop centres)."""
    if not HUB_WORKSHEET.is_file():
        return {}
    with open(HUB_WORKSHEET, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {h["name"]: (int(h["anchor"][0]), int(h["anchor"][1]))
            for h in data.get("hubs", []) if "anchor" in h and "name" in h}


def write_crops(canvas_rgb: np.ndarray, prefix: str) -> list[Path]:
    """Zoomed crops centred on real committed hub anchors."""
    anchors = hub_anchors()
    out: list[Path] = []
    for name in ZOOM_HUBS:
        if name not in anchors:
            log(f"  zoom: no anchor named {name!r} in the hub worksheet — skipped")
            continue
        cx, cy = anchors[name]
        x0 = max(0, cx - ZOOM_HALF); x1 = min(CANVAS_W, cx + ZOOM_HALF)
        y0 = max(0, cy - ZOOM_HALF); y1 = min(CANVAS_H, cy + ZOOM_HALF)
        path = SCRATCH_DIR / f"{prefix}_zoom_{name.lower()}.png"
        Image.fromarray(canvas_rgb[y0:y1, x0:x1].copy(), mode="RGB").save(path)
        log(f"  zoom {name:<12} canvas [{x0}, {y0}, {x1}, {y1}] -> "
            f"{path.relative_to(REPO_ROOT)}")
        out.append(path)
    return out


# ---------------------------------------------------------------------------
# Verification modes
# ---------------------------------------------------------------------------

def verify_correspondence(windows: int = 6, size: int = 384) -> int:
    """Re-confirm cr_oldworld_map.png == parchment x2 (cheap spot check).

    Not a re-run of the original full-frame FFT phase correlation — that work is
    already done and its conclusion (scale 2.00) is baked into
    :data:`MASTER_TO_LOOKUP_SCALE`. This checks the constant still holds for the
    files on this device, by nearest-upsampling a few parchment windows to lookup
    resolution and sweeping the mean-abs-difference over lookup-px offsets.

    **Measured finding (2026-09-12), disclosed rather than asserted away.** The
    MAE minimum sits consistently at **dx = +1 lookup px, dy = 0**, not at
    (0, 0) — every window, by a small but repeatable margin. That is half a
    master px of horizontal bias, the signature of a resample convention
    (pixel-centre vs pixel-corner) in whatever produced the 8192² campaign map,
    not a real translation of the artwork. At this registration's measured
    master->canvas scale it is ~0.2 canvas px: the same order as the 8193-row tie
    and far below anything a rendered overlay can show. The render therefore does
    **not** apply it (see :data:`LOOKUP_OFFSET_X`), and this check passes any
    best offset within :data:`OFFSET_TOLERANCE_LOOKUP_PX` of zero while printing
    the offset it actually measured.

    The absolute MAE is large (12-37 of 255) because the two files are different
    renders of the same map, not a byte-exact rescale — so this is a *structural
    alignment* check, which is what the render depends on, not a pixel-identity
    one.
    """
    require_dataset()
    if not CAMPAIGN_MAP_PNG.is_file():
        log(f"{CAMPAIGN_MAP_PNG.relative_to(REPO_ROOT)} is missing — cannot spot-check "
            f"the 2x correspondence (the lookup render itself does not need it)")
        return 1
    parch = load_source_rgb(PARCHMENT_SOURCE).astype(np.float32)
    if parch.shape[:2] != (MASTER_SIZE, MASTER_SIZE):
        raise SystemExit(f"{PARCHMENT_SOURCE} is {parch.shape[1]}x{parch.shape[0]}, "
                         f"expected {MASTER_SIZE}x{MASTER_SIZE}")
    with Image.open(CAMPAIGN_MAP_PNG) as im:
        if im.size != (LOOKUP_SIZE, LOOKUP_SIZE):
            raise SystemExit(f"{CAMPAIGN_MAP_PNG.name} is {im.size[0]}x{im.size[1]}, "
                             f"expected {LOOKUP_SIZE}x{LOOKUP_SIZE}")
        camp = rgb_zero_transparent(im).astype(np.float32)

    rng = np.random.default_rng(4364)
    span = range(-OFFSET_SWEEP_LOOKUP_PX, OFFSET_SWEEP_LOOKUP_PX + 1)
    shifts = [(dx, dy) for dy in span for dx in span]
    wins_ok = 0
    bests: list[tuple[int, int]] = []
    for i in range(windows):
        x0 = int(rng.integers(size, MASTER_SIZE - 2 * size))
        y0 = int(rng.integers(size, MASTER_SIZE - 2 * size))
        ref = np.repeat(np.repeat(parch[y0:y0 + size, x0:x0 + size], 2, axis=0), 2, axis=1)
        scores = {}
        for dx, dy in shifts:
            sx, sy = 2 * x0 + dx, 2 * y0 + dy
            blk = camp[sy:sy + 2 * size, sx:sx + 2 * size]
            scores[(dx, dy)] = float(np.abs(blk - ref).mean())
        best = min(scores, key=scores.get)
        bests.append(best)
        ok = max(abs(best[0]), abs(best[1])) <= OFFSET_TOLERANCE_LOOKUP_PX
        wins_ok += ok
        log(f"  window {i + 1} at master ({x0}, {y0}) {size}²: best lookup-px offset "
            f"{best} MAE {scores[best]:.2f} (offset (0,0) MAE {scores[(0, 0)]:.2f}) "
            f"{'OK' if ok else 'MISMATCH'}")
    log(f"correspondence: {wins_ok}/{windows} windows aligned within "
        f"±{OFFSET_TOLERANCE_LOOKUP_PX} lookup px at "
        f"MASTER_TO_LOOKUP_SCALE = {MASTER_TO_LOOKUP_SCALE}")
    if bests:
        mdx = int(np.median([b[0] for b in bests]))
        mdy = int(np.median([b[1] for b in bests]))
        log(f"  measured offset   median (dx, dy) = ({mdx:+d}, {mdy:+d}) lookup px "
            f"= ({mdx / MASTER_TO_LOOKUP_SCALE:+.1f}, {mdy / MASTER_TO_LOOKUP_SCALE:+.1f}) "
            f"master px — a resample-convention bias, sub-pixel at canvas scale and "
            f"NOT applied by the render (LOOKUP_OFFSET_X = {LOOKUP_OFFSET_X})")
    if wins_ok != windows:
        log("  NOT CONFIRMED — the 2x correspondence this script rests on does not "
            "hold for these files")
        return 1
    return 0


def verify_lookup_coregistration(samples: int = 20000) -> int:
    """Does the lookup's own land/void partition agree with the parchment artwork?

    The render path assumes the lookup and the parchment share a frame. This
    checks that directly, *through the real render path*: canvas points inside
    the registration footprint are mapped ``canvas -> master`` by
    ``fit.to_source_px`` and then ``master -> lookup`` by
    :data:`MASTER_TO_LOOKUP_SCALE`, and the two are compared where the lookup is
    unambiguous.

    The comparison is a deliberately **cheap heuristic**, not a rigorous
    measurement: the parchment is stylised sepia art with no flat sea colour, so
    "sea" is only weakly separable by local luminance (a blurred-luminance
    threshold scores ~82% per-sample on this art even at perfect alignment).
    A per-sample pass rate alone would therefore prove little, so the decisive
    half is the **offset sweep**: the land-minus-void luminance contrast is
    recomputed at master-space shifts out to +-512 px and must (i) peak at zero
    shift and (ii) decay materially by +-256 px. An aligned pair holds its
    contrast at zero and loses it as the lookup slides off the artwork; a
    misregistered pair is flat, because a flat sweep means the test had no
    discriminating power in the first place — so (ii) is what makes (i) mean
    something. Shifts smaller than :data:`COREG_FINE_PX` are deliberately not
    trusted to break a tie: the interior erosion is +-16 lookup px, so a shift
    that small barely changes which samples are which.

    Only interior samples are used (every point within a 33-lookup-px window of
    one class), so boundary pixels never decide the result.
    """
    require_dataset()
    from scipy import ndimage

    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    if FULL_SOURCE not in regs:
        raise SystemExit(f"{FULL_SOURCE}: no committed registration record")
    reg = regs[FULL_SOURCE]
    fit = reproject.fit_placement(reg, regs, buffer_px=0.0)

    lookup = load_lookup()
    void = (lookup.sum(axis=2) == 0)
    del lookup
    interior = ndimage.uniform_filter(void.astype(np.float32), size=33)
    interior_void = interior > 0.999
    interior_land = interior < 0.001
    del interior

    parch = load_source_rgb(PARCHMENT_SOURCE).astype(np.float32)
    lum = 0.299 * parch[..., 0] + 0.587 * parch[..., 1] + 0.114 * parch[..., 2]
    lum = ndimage.uniform_filter(lum, size=33)

    x0, y0, x1, y1 = reg.footprint
    rng = np.random.default_rng(4364)
    cx = rng.uniform(x0, x1, samples * 3)
    cy = rng.uniform(y0, y1, samples * 3)
    mx, my = fit.to_source_px(cx, cy)
    good = np.isfinite(mx) & np.isfinite(my) \
        & (mx >= 40) & (mx <= MASTER_SIZE - 41) & (my >= 40) & (my <= MASTER_SIZE - 41)
    mx, my = mx[good][:samples], my[good][:samples]
    if mx.size < 20:
        log("coregistration: too few canvas samples landed in the master frame")
        return 1

    def contrast(shift_x: float, shift_y: float) -> tuple[float, int, int]:
        # Shifted samples that fall outside the lookup are DROPPED, not clamped:
        # clamping would pile the whole far-shift tail onto one edge column and
        # make the decay measurement meaningless.
        fx = np.rint((mx + shift_x) * MASTER_TO_LOOKUP_SCALE)
        fy = np.rint((my + shift_y) * MASTER_TO_LOOKUP_SCALE)
        inside = (fx >= 0) & (fx <= LOOKUP_SIZE - 1) & (fy >= 0) & (fy <= LOOKUP_SIZE - 1)
        lx = fx[inside].astype(np.int32)
        ly = fy[inside].astype(np.int32)
        px = np.rint(mx[inside]).astype(np.int32)
        py = np.rint(my[inside]).astype(np.int32)
        is_void = interior_void[ly, lx]
        is_land = interior_land[ly, lx]
        v = lum[py[is_void], px[is_void]]
        l = lum[py[is_land], px[is_land]]
        if v.size < 5 or l.size < 5:
            return 0.0, int(v.size), int(l.size)
        return float(l.mean() - v.mean()), int(v.size), int(l.size)

    base, n_void, n_land = contrast(0.0, 0.0)
    log(f"coregistration: {mx.size} canvas samples through {FULL_SOURCE} "
        f"({reg.projection}); {n_void} interior-void, {n_land} interior-land")

    # Per-sample pass rate under the weak luminance rule (reported, not decisive).
    lx = np.clip(np.rint(mx * MASTER_TO_LOOKUP_SCALE), 0, LOOKUP_SIZE - 1).astype(np.int32)
    ly = np.clip(np.rint(my * MASTER_TO_LOOKUP_SCALE), 0, LOOKUP_SIZE - 1).astype(np.int32)
    px = np.rint(mx).astype(np.int32); py = np.rint(my).astype(np.int32)
    iv, il = interior_void[ly, lx], interior_land[ly, lx]
    thr = float(np.median(np.concatenate([lum[py[iv], px[iv]], lum[py[il], px[il]]]))) \
        if (iv.sum() and il.sum()) else 0.0
    agree = int((lum[py[iv], px[iv]] < thr).sum() + (lum[py[il], px[il]] >= thr).sum())
    total = int(iv.sum() + il.sum())
    rate = 100.0 * agree / total if total else 0.0
    log(f"  per-sample land/sea-ink agreement: {agree}/{total} ({rate:.1f}%) "
        f"[weak heuristic — stylised sepia art has no flat sea colour]")

    sweep: list[tuple[int, float, float]] = []
    for d in COREG_SWEEP_PX:
        cxy = contrast(float(d), 0.0)[0] if d else base
        cyx = contrast(0.0, float(d))[0] if d else base
        sweep.append((d, cxy, cyx))
        log(f"  shift {d:+5d} master px:  dx-contrast {cxy:7.2f}   dy-contrast {cyx:7.2f}")

    # (i) the peak must sit at zero, up to the erosion-limited fine scale.
    peak_x = max(sweep, key=lambda t: t[1])[0]
    peak_y = max(sweep, key=lambda t: t[2])[0]
    peaks_at_zero = abs(peak_x) <= COREG_FINE_PX and abs(peak_y) <= COREG_FINE_PX
    # (ii) the sweep must actually discriminate, or (i) proves nothing.
    far = [c for d, cx, cy in sweep for c in (cx, cy) if abs(d) >= COREG_FAR_PX]
    decayed = bool(far) and max(far) < base * COREG_DECAY_MAX
    ok = peaks_at_zero and decayed and base > 0

    log(f"  contrast peaks at dx={peak_x:+d}, dy={peak_y:+d} master px "
        f"(zero-shift contrast {base:.2f}; |shift| >= {COREG_FAR_PX} px tops out at "
        f"{max(far) if far else float('nan'):.2f}, needs < "
        f"{base * COREG_DECAY_MAX:.2f} for the sweep to be discriminating)")
    log(f"  coregistration: {'PASS' if ok else 'FAIL'}")
    if not ok:
        if not decayed:
            log("  the sweep is flat — this test had no discriminating power here, so "
                "it neither confirms nor denies the frame match")
        else:
            log("  the lookup and the parchment master do NOT appear to share a frame "
                "at this scale — the render would be meaningless")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def fit_report(label: np.ndarray, placed: np.ndarray, keys: dict[str, str],
               reg: schema.SourceRegistration, excluded: dict, scope: np.ndarray) -> dict:
    """Print, and return for the sidecar, what actually landed on the canvas."""
    packed = pack(label)[placed]
    colours, counts = np.unique(packed, return_counts=True)
    hexes = [unpack_hex(c) for c in colours]
    keyed = sum(1 for hx in hexes if hx in keys)
    unkeyed = [hx for hx in hexes if hx not in keys]
    unkeyed_px = int(counts[[hx not in keys for hx in hexes]].sum()) if unkeyed else 0

    surviving = set(colours.tolist())
    oos_colours = excluded["colours"]
    oos_only = sorted(oos_colours - surviving)
    oos_keyed = sum(1 for c in oos_only if unpack_hex(c) in keys)

    pct = np.percentile(counts, [1, 5, 50, 95]) if counts.size else np.zeros(4)
    n_landmarks = len(reg.control_points)
    tie = row_tie_canvas_px(reg)
    scale = master_to_canvas_scale(reg)

    log("")
    log("fit report")
    log(f"  registration      {FULL_SOURCE}  ({reg.projection}, "
        f"{n_landmarks} landmark control points)")
    log(f"  PROVISIONAL       this overlay rests on that registration, which its own "
        f"record still marks PROVISIONAL pending the user's separate acceptance — "
        f"if that placement moves, this render moves with it")
    log(f"  placed            {int(placed.sum()):,} canvas px "
        f"({100.0 * placed.mean():.3f}% of the {CANVAS_W}x{CANVAS_H} frame)")
    log(f"  regions >=1px     {colours.size:,} of the bitmap's own non-black regions "
        f"({keyed:,} carry a TSV key)")
    log(f"  scope excluded    {excluded['px']:,} canvas px dropped for landing outside "
        f"{SCOPE_SOURCE}'s opaque extent ({100.0 * scope.mean():.1f}% of the master "
        f"frame is in scope) — Chris, 2026-09-12. {len(oos_colours):,} region colour(s) "
        f"appeared in the dropped pixels; {len(oos_only):,} of those are now gone from "
        f"the render entirely ({oos_keyed:,} of them carry a TSV key), the rest survive "
        f"where they also cover in-scope ground. Distinct from the hull-footprint bound, "
        f"which excludes points the registration cannot place at all")
    log(f"  region area px    p1 {pct[0]:.0f}  p5 {pct[1]:.0f}  p50 {pct[2]:.0f}  "
        f"p95 {pct[3]:.0f}")
    log(f"  small regions     <25px {int((counts < 25).sum()):,}   "
        f"<100px {int((counts < 100).sum()):,}   <400px {int((counts < 400).sum()):,}")
    log(f"  master->canvas    {scale:.4f} canvas px per master px "
        f"(footprint width {reg.footprint[2] - reg.footprint[0]:.1f} / {MASTER_SIZE})")
    log(f"  8193-row tie      dropped row {DROP_ROW} (rows 1..{LOOKUP_SIZE} used). "
        f"The other reading shifts everything by 1 lookup px = "
        f"{1.0 / MASTER_TO_LOOKUP_SCALE} master px = {tie:.3f} canvas px — "
        f"sub-pixel here, but a real unresolved ±1 ambiguity, not a measured zero")
    log(f"  x-offset          not applied (LOOKUP_OFFSET_X = {LOOKUP_OFFSET_X}); "
        f"--verify-correspondence measures a repeatable +1 lookup px = "
        f"{0.5 * scale:.3f} canvas px of resample-convention bias, the same order as "
        f"the row tie and below rendering resolution")
    log(f"  black 000000      rendered as VOID (globe shows through): sea/off-map in "
        f"the bitmap, and {getattr(load_region_keys, 'black_rows', 0)} TSV rows carry "
        f"it as their colour, so those keys are unpaintable too")
    log(f"  unkeyed colours   {len(unkeyed):,} placed colour(s) have no TSV row "
        f"({unkeyed_px:,} px), rendered flat {UNKEYED_RGB} grey and labelled in the "
        f"legend — never painted as if named"
        + (f"; largest: {sorted(unkeyed)[:4]}" if unkeyed else ""))
    log(f"  TSV keys          {len(keys):,} paintable region keys loaded")

    return {
        "registration": FULL_SOURCE,
        "registration_projection": reg.projection,
        "registration_landmarks": n_landmarks,
        "registration_provisional": True,
        "placed_px": int(placed.sum()),
        "regions_placed": int(colours.size),
        "regions_placed_keyed": int(keyed),
        "scope_source": SCOPE_SOURCE,
        "scope_master_fraction": float(scope.mean()),
        "scope_excluded_px": int(excluded["px"]),
        "scope_excluded_colours_touched": len(oos_colours),
        "scope_excluded_colours_removed": len(oos_only),
        "scope_excluded_colours_removed_keyed": int(oos_keyed),
        "scope_excluded_colours_removed_hex": [unpack_hex(c) for c in oos_only],
        "region_area_percentiles": {"p1": float(pct[0]), "p5": float(pct[1]),
                                    "p50": float(pct[2]), "p95": float(pct[3])},
        "regions_under_25px": int((counts < 25).sum()),
        "regions_under_100px": int((counts < 100).sum()),
        "regions_under_400px": int((counts < 400).sum()),
        "master_to_canvas_scale": scale,
        "row_tie_dropped_row": DROP_ROW,
        "row_tie_canvas_px": tie,
        "lookup_offset_x_applied": LOOKUP_OFFSET_X,
        "lookup_offset_x_measured": 1,
        "lookup_offset_x_measured_canvas_px": 0.5 * scale,
        "tsv_keys": len(keys),
        "tsv_black_rows": int(getattr(load_region_keys, "black_rows", 0)),
        "unkeyed_placed_colours": sorted(unkeyed),
        "unkeyed_placed_px": unkeyed_px,
    }


def build(mode: str, coast: bool, hull_buffer_px: float) -> Path:
    require_dataset()
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    if FULL_SOURCE not in regs:
        raise SystemExit(f"{FULL_SOURCE}: no committed registration record — run "
                         f"mapgen/fit_registration.py --seed tww3_old_world_mod_parchment_full")
    reg = regs[FULL_SOURCE]

    globe = load_source_rgb(GLOBE_SOURCE)
    if globe.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{GLOBE_SOURCE} is {globe.shape[1]}x{globe.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} (the canvas frame)")

    keys = load_region_keys()
    scope = load_scope_mask()
    log(f"scope mask        {SCOPE_SOURCE} alpha: {100.0 * scope.mean():.1f}% of the "
        f"master frame is in scope; anything outside it is dropped to void "
        f"(Chris, 2026-09-12)")
    lookup = load_lookup()
    log(f"lookup            {LOOKUP_BMP.name} {LOOKUP_SIZE}x{LOOKUP_SIZE} "
        f"(row {DROP_ROW} dropped from {LOOKUP_SIZE + 1})")

    fit = reproject.fit_placement(reg, regs, buffer_px=hull_buffer_px)
    box = footprint_box(reg, pad=hull_buffer_px)
    log(f"eval box          canvas {list(box)}"
        + (f" (footprint + {hull_buffer_px:.0f}px outer-hull buffer)" if hull_buffer_px > 0
           else " (strict footprint)"))
    label, placed, excluded = place_lookup(fit, box, lookup, scope)
    del lookup
    if not placed.any():
        raise SystemExit("nothing placed — check the registration / lookup / scope mask")

    unkeyed_target = int(UNKEYED_HEX, 16)
    unkeyed_mask = placed & (pack(label) == unkeyed_target)

    report = fit_report(label, placed, keys, reg, excluded, scope)

    if mode == "borders":
        canvas, n_edge = extract_borders(label, placed, globe)
        log(f"  border pixels     {n_edge:,}")
        report["border_px"] = n_edge
        legend = [(BORDER_RGB, "cr_oldworld_lookup region boundaries"),
                  (None, f"{report['regions_placed']} regions placed / "
                         f"{report['tsv_keys']} TSV keys"),
                  (None, "void (black) = campaign-map sea / off-map, not drawn"),
                  (None, f"cropped to {SCOPE_SOURCE} extent: "
                         f"{report['scope_excluded_px']:,} px out of scope, dropped")]
        if coast:
            legend.insert(1, (COAST_RGB, "this mod's coastline (reference)"))
    else:
        canvas = compose_fills(label, placed, globe, unkeyed_mask)
        legend = [(None, "cr_oldworld_lookup regions draped via "
                         "tww3_old_world_mod_parchment_full (PROVISIONAL)"),
                  (UNKEYED_RGB, f"unkeyed: colour {UNKEYED_HEX} has no TSV row"),
                  (None, "void (black) = campaign-map sea / off-map, not drawn"),
                  (None, f"{report['regions_placed']} regions placed / "
                         f"{report['tsv_keys']} TSV keys"),
                  (None, f"cropped to {SCOPE_SOURCE} extent: "
                         f"{report['scope_excluded_px']:,} px out of scope, dropped")]
        if coast:
            legend.append((COAST_RGB, "this mod's coastline (reference)"))
    del label

    if coast:
        report["coast_px"] = overlay_coast(canvas)

    draw_legend(canvas, legend)

    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"{OUT_PREFIX}_{mode}"
    out_path = SCRATCH_DIR / f"{prefix}.png"
    Image.fromarray(canvas, mode="RGB").save(out_path)
    log(f"wrote {out_path.relative_to(REPO_ROOT)}")
    write_crops(canvas, prefix)

    report["provenance"] = {
        "lookup_bmp": {"name": LOOKUP_BMP.name, "sha256": sha256_of(LOOKUP_BMP),
                       "dimensions": f"{LOOKUP_SIZE}x{LOOKUP_SIZE + 1}"},
        "region_tsv": {"name": LOOKUP_TSV.name, "sha256": sha256_of(LOOKUP_TSV)},
    }
    report["mode"] = mode
    report["note"] = ("dev-only QA render, board #4364. Built on the PROVISIONAL "
                      "tww3_old_world_mod_parchment_full registration; if that "
                      "placement moves, this render moves with it. Cropped to "
                      f"{SCOPE_SOURCE}'s opaque extent (Chris, 2026-09-12: land not "
                      "drawn there is out of scope).")
    side = SCRATCH_DIR / f"{prefix}.json"
    with open(side, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    log(f"wrote {side.relative_to(REPO_ROOT)} (provenance + fit report)")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fills", action="store_true",
                   help="render the lookup's region colours draped over the globe (default)")
    p.add_argument("--borders-only", action="store_true",
                   help="render only the region boundaries extracted from the finished "
                        "drape, so the globe's own terrain shows through everywhere else")
    p.add_argument("--coast", action="store_true",
                   help="also draw this mod's own coastline in cyan as a reference line")
    p.add_argument("--hull-buffer-px", type=float, default=HULL_BUFFER_PX_DEFAULT,
                   help=f"extrapolate this many canvas px past the OUTER hull edge only "
                        f"(a QA convenience, not a real correspondence; default "
                        f"{HULL_BUFFER_PX_DEFAULT:.0f}, 0 for the strict cutoff)")
    p.add_argument("--verify-correspondence", action="store_true",
                   help="spot-check that cr_oldworld_map.png is the parchment master at "
                        "exactly 2x with zero offset, then exit")
    p.add_argument("--verify-lookup-coregistration", action="store_true",
                   help="check the lookup's own land/void partition against the parchment "
                        "artwork through the real render path, then exit")
    args = p.parse_args(argv)

    if args.verify_correspondence:
        return verify_correspondence()
    if args.verify_lookup_coregistration:
        return verify_lookup_coregistration()

    mode = "borders" if args.borders_only else "fills"
    build(mode, coast=args.coast, hull_buffer_px=args.hull_buffer_px)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
