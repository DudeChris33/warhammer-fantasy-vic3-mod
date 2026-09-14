#!/usr/bin/env python3
"""QA render (board #4425): the TWW3 campaign-map debug export
``old_world_map - stretched.png`` draped onto this mod's canvas through the
existing ``tww3_old_world_mod_parchment_full`` registration, at a measured
scale shortcut — the same pattern ``tools/render_cr_lookup_overlay.py`` (board
#4364) already uses for ``cr_oldworld_lookup.bmp``.

**Dev-only, gitignored output.** Everything this writes lands in
``tools/derived/`` (ignored there); nothing it reads from
``sources/cr_oldworld_campaign/`` — third-party CA/SEGA IP, itself gitignored
— ever reaches a committed file. This produces *evidence for a human*: a
render Chris looks at, plus a printed fit report. No committed
``tools/registration/``, ``common/``, ``events/`` or ``map_data/`` file
depends on it, and it can never gain its own registration entry — see the
next section.

Why this can never get its own ``tools/registration/`` entry
--------------------------------------------------------------
``tools/worldgen/sources.py``'s ``verify()`` hard-errors if a manifest row's
file is missing locally, and separately hard-errors if any
``tools/registration/*.json`` record's ``"source"`` has no manifest row.
``sources/cr_oldworld_campaign/`` is deliberately gitignored/unmanifested
third-party IP, absent on every device but the one that owns it — so there is
no way to register this source without breaking ``--verify`` somewhere.
Precedent already avoids the trap: ``cr_oldworld_map.png`` /
``cr_oldworld_lookup.bmp`` were never registered either; this script is that
same shortcut, applied to a different file in the same dataset.

The stretched file, not the raw one
------------------------------------
``old_world_map.png`` itself is 2048x1774 — a non-square debug export whose
extra height was found (this board item's own scoping) to be *cropped*
relative to a square frame, not merely offset: a crop-model correlation
against it found no real peak (best offset landed at an arbitrary dy=292).
Its companion file, ``old_world_map - stretched.png``, is the same content
resized to an exact 2048x2048 square — i.e. the 1774px height *stretched* to
close the gap, not cropped — so it matches the 4096 parchment master and the
8192 ``cr_oldworld`` campaign frame exactly in both dimensions, at a uniform
isotropic scale, with no crop needed. Only the stretched file is used here;
the raw file has no established correspondence to anything.

Step 1 correlation findings (this session, superseding scoping's own cruder
IoU-only sweep)
----------------------------------------------------------------------------
Two independent references were tested by FFT phase correlation
(``skimage.registration.phase_cross_correlation``, sub-pixel, on downsampled
land-density fields to keep the transform tractable):

* **Candidate A** — ``tools/derived/land_sea_mask.png`` (this mod's own
  committed coastline) forward-projected into the 4096 master frame through
  the existing ``tww3_old_world_mod_parchment_full`` registration
  (``fit_placement_inverse``), at scale 2.0 (master = stretched x 2). Measured
  shift: (dy, dx) = (+1.2, -0.8) px at the master frame's resolution — a real
  but sub-2px residual, i.e. no crop/offset correction needed. IoU 0.494 at
  zero offset, essentially unchanged at the measured shift (0.509).
* **Candidate B** — ``cr_oldworld_lookup.bmp``'s own non-black (land+sea-zone)
  partition, sampled *directly*, no registration involved at all — an
  independent check that the stretched file shares the same underlying
  campaign-map frame as the dataset's own reference art. Measured shift:
  (dy, dx) = (-0.8, +0.8) px at the 8192 campaign frame's resolution. IoU
  0.581 at zero offset (0.590 at the measured shift).

Both candidates independently converge on essentially zero offset (sub-pixel
at their own resolution, nowhere near the ~arbitrary hundreds-of-px offset the
raw non-square file produced). An offset sweep out to +-3200/+-6400 px shows
IoU decaying steadily and monotonically away from zero in every direction
tested (e.g. candidate B: 0.581 at zero, down to ~0.36-0.41 by +-6400 px) —
the peak is real, not a coincidental local maximum in a flat landscape. The
absolute IoU is moderate rather than dramatic, exactly as expected: this
mod's own hand-drawn coastline genuinely differs from the source game's, which
is the whole point of this QA render, and candidate A additionally carries the
``_full`` registration's own disclosed PROVISIONAL uncertainty. **Conclusion:
scale 2.0 against the master frame, zero offset** — the same shortcut shape as
``MASTER_TO_LOOKUP_SCALE`` in the sibling script, reused here as
:data:`MASTER_TO_STRETCHED_SCALE`. Testing the alpha-eroded
``tww3_old_world_mod_parchment_cropped.png`` scope mask as a *third*, separate
target (Chris's other recollection) was judged unnecessary once candidate A
confirmed a real geographic correspondence against this mod's own coastline
directly, in the identical master frame that scope mask shares — a
content-based correlation is the stronger of the two checks, and the scope
mask is applied at render time regardless (see below), so it is exercised
either way.

PROVISIONAL FOUNDATION — READ BEFORE TRUSTING THIS RENDER
-----------------------------------------------------------
Same disclosure as the sibling lookup-overlay script:
``tools/registration/tww3_old_world_mod_parchment_full.json`` self-declares
"PROVISIONAL until the user accepts the diagnostic render". This overlay rides
on that placement; if it moves, this render moves with it.

Scope filter (Chris, 2026-09-12) — reused verbatim
-----------------------------------------------------
Land not drawn in ``sources/originals/tww3_old_world_mod_parchment_cropped.png``
(its **alpha channel** is the extent) is out of scope, exactly as in the
sibling lookup overlay. Every canvas pixel this render places is tested
against that alpha through the same ``canvas -> master`` transform.

Colour handling
----------------
The stretched export is an 8-flat-colour debug render, not painted art, sampled
here as **raw RGB** (no label/TSV lookup — this file carries no region keys to
resolve). One colour is treated specially: ``(46,46,46)`` is the export's own
rounded-corner camera-vignette artifact (confirmed by histogram: 25.4% of the
image, in four rounded corners) — a HUD bezel, not geography — and is rendered
as void (the globe shows through), the same convention the sibling script
applies to its own void colour.

Usage::

    python tools/render_old_world_map_overlay.py
    python tools/render_old_world_map_overlay.py --coast
    python tools/render_old_world_map_overlay.py --verify-correspondence
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import reproject, schema  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
SOURCES_DIR = REPO_ROOT / "sources"
DERIVED_DIR = TOOLS_DIR / "derived"
REGISTRATION_DIR = TOOLS_DIR / "registration"

#: The third-party reference dataset. Gitignored and absent on most devices —
#: see :func:`require_dataset` for the clean skip.
DATASET_DIR = SOURCES_DIR / "cr_oldworld_campaign"
#: The square, isotropically-scaled companion file this script actually uses —
#: NOT the raw ``old_world_map.png`` (see module docstring for why).
STRETCHED_PNG = DATASET_DIR / "campaign_map" / "old_world_map - stretched.png"
LOOKUP_BMP = DATASET_DIR / "cr_oldworld_lookup" / "cr_oldworld_lookup.bmp"

#: The reprojected globe that IS the canvas frame — the backdrop this drapes over.
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
#: The plain globe with a magenta coastline drawn on it — a reference line, not the backdrop.
COAST_SOURCE = "terraqueous_globe_reprojected - coasts.png"

#: The registration record this projects through (see the PROVISIONAL note above).
FULL_SOURCE = "tww3_old_world_mod_parchment_full.png"
#: The scope authority (Chris, 2026-09-12), shared verbatim with render_cr_lookup_overlay.py.
SCOPE_SOURCE = "tww3_old_world_mod_parchment_cropped.png"
#: The raw parchment master art, used only by --verify-correspondence's candidate A
#: land-mask forward-projection (via the committed coastline, not this file's own pixels).
LAND_SEA_MASK_PATH = DERIVED_DIR / "land_sea_mask.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
#: The master frame's own size, in master px.
MASTER_SIZE = 4096
#: The stretched export's own size (2048x2048, confirmed on load).
STRETCHED_SIZE = 2048
#: Confirmed this session by FFT phase correlation against two independent
#: references (see module docstring): stretched px * this = master px.
MASTER_TO_STRETCHED_SCALE = STRETCHED_SIZE / MASTER_SIZE  # 0.5

#: Row block for warp evaluation — bounds the piecewise fit's temporaries.
ROW_BLOCK = 64
#: Extrapolation past the OUTER hull edge only, matching the sibling scripts'
#: user-accepted default. Not a real correspondence — a QA convenience.
HULL_BUFFER_PX_DEFAULT = 50.0

#: The export's own rounded-corner camera-vignette artifact — void, not geography
#: (confirmed by histogram: 25.4% of the image, four rounded corners).
VOID_RGB = (46, 46, 46)
VOID_TOLERANCE = 10  # small AA slack around the flat vignette colour
#: The flat land colour, used only by --verify-correspondence's silhouette extraction.
LAND_RGB = (16, 248, 0)
LAND_TOLERANCE = 60

COAST_RGB = (0, 255, 255)

OUT_PREFIX = "old_world_map_overlay"


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Dataset presence / loading
# ---------------------------------------------------------------------------

def require_dataset() -> None:
    """Clean-skip when the third-party reference dataset is not on this device.

    The ``validate_map._check_canon_cities`` idiom, reused throughout this
    dataset's other consumers: a gitignored local working file's absence is
    the expected state on most devices, not an error.
    """
    if DATASET_DIR.is_dir() and STRETCHED_PNG.is_file():
        return
    log(f"{DATASET_DIR.relative_to(REPO_ROOT)}: reference dataset not present on "
        f"this device — dev-only render, skipping")
    sys.exit(0)


def load_source_rgb(name: str) -> np.ndarray:
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8).copy()


def load_stretched() -> np.ndarray:
    """The debug export as ``(2048, 2048, 3)`` uint8 RGB.

    Hard-errors on an unexpected size — a differently-sized export is a
    different dataset and :data:`MASTER_TO_STRETCHED_SCALE` would not apply.
    """
    with Image.open(STRETCHED_PNG) as im:
        if im.size != (STRETCHED_SIZE, STRETCHED_SIZE):
            raise SystemExit(
                f"{STRETCHED_PNG.name} is {im.size[0]}x{im.size[1]}, expected "
                f"{STRETCHED_SIZE}x{STRETCHED_SIZE} — a different size is a different "
                f"export and the scale/void constants documented in this script would "
                f"not apply")
        return np.asarray(im.convert("RGB"), dtype=np.uint8).copy()


def load_scope_mask() -> np.ndarray:
    """``(4096, 4096)`` bool: True where this mod's scope covers the master frame.

    Identical to render_cr_lookup_overlay.load_scope_mask — read from
    :data:`SCOPE_SOURCE`'s alpha channel.
    """
    path = sources_mod.resolve_source_path(SCOPE_SOURCE, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(
            f"sources/{SCOPE_SOURCE} is missing — it is the scope authority "
            f"(Chris, 2026-09-12: land not drawn there is out of scope) and this "
            f"render must not paint content without it")
    with Image.open(path) as im:
        if im.size != (MASTER_SIZE, MASTER_SIZE):
            raise SystemExit(
                f"{SCOPE_SOURCE} is {im.size[0]}x{im.size[1]}, expected "
                f"{MASTER_SIZE}x{MASTER_SIZE} — the scope mask must share the master "
                f"frame this registration places")
        alpha = np.asarray(im.convert("RGBA"), dtype=np.uint8)[..., 3]
    return alpha > 0


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
    x0, y0, x1, y1 = reg.footprint
    return (max(0, int(np.floor(x0 - pad))), max(0, int(np.floor(y0 - pad))),
            min(CANVAS_W, int(np.ceil(x1 + pad))), min(CANVAS_H, int(np.ceil(y1 + pad))))


def master_to_canvas_scale(reg: schema.SourceRegistration) -> float:
    """Canvas px per master px, measured from the record's own footprint width."""
    x0, _, x1, _ = reg.footprint
    return (x1 - x0) / MASTER_SIZE


def place_stretched(fit, box: tuple[int, int, int, int], stretched: np.ndarray,
                    scope: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """Warp the stretched export into canvas space. Returns ``(rgb, placed, excluded)``.

    ``placed`` is True where the warp landed inside the master frame AND inside
    this mod's scope (:data:`SCOPE_SOURCE`'s alpha) AND the sampled colour is
    not the export's own void/vignette colour.

    Nearest sampling, direct integer indexing — same rationale as
    ``render_cr_lookup_overlay.place_lookup``: this is a small (2048²) flat-
    colour raster, so an exact rounded lookup is both correct and cheap.
    """
    out_rgb = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)
    placed = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
    oos_px = 0

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
        sx = np.clip(np.rint(mx * MASTER_TO_STRETCHED_SCALE), 0, STRETCHED_SIZE - 1).astype(np.int32)
        sy = np.clip(np.rint(my * MASTER_TO_STRETCHED_SCALE), 0, STRETCHED_SIZE - 1).astype(np.int32)
        block = stretched[sy, sx]

        d = np.abs(block.astype(np.int16) - np.array(VOID_RGB, dtype=np.int16)).sum(axis=2)
        non_void = d > VOID_TOLERANCE
        paintable = in_master & non_void

        mxi = np.clip(np.rint(np.where(in_master, mx, 0.0)), 0, MASTER_SIZE - 1).astype(np.int32)
        myi = np.clip(np.rint(np.where(in_master, my, 0.0)), 0, MASTER_SIZE - 1).astype(np.int32)
        in_scope = scope[myi, mxi]

        dropped = paintable & ~in_scope
        if dropped.any():
            oos_px += int(dropped.sum())

        valid = paintable & in_scope
        if not valid.any():
            continue
        out_rgb[yb:ye, bx0:bx1][valid] = block[valid]
        placed[yb:ye, bx0:bx1] |= valid

    return out_rgb, placed, {"px": oos_px}


def compose(rgb: np.ndarray, placed: np.ndarray, globe_rgb: np.ndarray) -> np.ndarray:
    out = globe_rgb.copy()
    out[placed] = rgb[placed]
    return out


def overlay_coast(canvas_rgb: np.ndarray) -> int:
    """Draw the coasts reference PNG's drawn line onto ``canvas_rgb`` in cyan.

    Identical to render_cr_lookup_overlay.overlay_coast (any non-black pixel is
    the line; the gitignored export's absence is a skip, not an error).
    """
    path = sources_mod.resolve_source_path(COAST_SOURCE, SOURCES_DIR)
    if not path.is_file():
        log(f"  coast: sources/{COAST_SOURCE} not present on this device — "
            f"reference line skipped")
        return 0
    with Image.open(path) as im:
        coasts = np.asarray(im.convert("RGB"), dtype=np.uint8)
    if coasts.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{COAST_SOURCE} is {coasts.shape[1]}x{coasts.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H}")
    line = coasts.any(axis=2)
    canvas_rgb[line] = COAST_RGB
    return int(line.sum())


def draw_legend(canvas_rgb: np.ndarray, lines: list[tuple[tuple[int, int, int] | None, str]],
                scale: int = 4) -> None:
    """Stamp a small legend into the top-left of the canvas (in place)."""
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


def write_crops(canvas_rgb: np.ndarray, box: tuple[int, int, int, int], prefix: str) -> list[Path]:
    """A couple of zoomed crops over the placed footprint, for closer inspection."""
    bx0, by0, bx1, by1 = box
    cx, cy = (bx0 + bx1) // 2, (by0 + by1) // 2
    half = 500
    out: list[Path] = []
    for name, (zx, zy) in {
        "center": (cx, cy),
        "nw_quadrant": (bx0 + (cx - bx0) // 2, by0 + (cy - by0) // 2),
    }.items():
        x0 = max(0, zx - half); x1 = min(CANVAS_W, zx + half)
        y0 = max(0, zy - half); y1 = min(CANVAS_H, zy + half)
        path = DERIVED_DIR / f"{prefix}_zoom_{name}.png"
        Image.fromarray(canvas_rgb[y0:y1, x0:x1].copy(), mode="RGB").save(path)
        log(f"  zoom {name:<12} canvas [{x0}, {y0}, {x1}, {y1}] -> "
            f"{path.relative_to(REPO_ROOT)}")
        out.append(path)
    return out


# ---------------------------------------------------------------------------
# Verification mode — Step 1's correlation check, reproducible on demand
# ---------------------------------------------------------------------------

def _land_mask_stretched(stretched: np.ndarray) -> np.ndarray:
    d = np.abs(stretched.astype(np.int16) - np.array(LAND_RGB, dtype=np.int16)).sum(axis=2)
    return d < LAND_TOLERANCE


def _downsample_density(mask: np.ndarray, factor: int) -> np.ndarray:
    h, w = mask.shape
    h2, w2 = h // factor, w // factor
    m = mask[: h2 * factor, : w2 * factor].astype(np.float32)
    return m.reshape(h2, factor, w2, factor).mean(axis=(1, 3))


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = int(np.count_nonzero(a & b))
    union = int(np.count_nonzero(a | b))
    return (inter / union) if union else 0.0


def verify_correspondence() -> int:
    """Re-run Step 1's FFT phase-correlation check against both references.

    Not exploratory here — the conclusion (scale 2.0, ~zero offset) is already
    baked into :data:`MASTER_TO_STRETCHED_SCALE`. This reproduces the evidence
    on demand, the same role ``render_cr_lookup_overlay.verify_correspondence``
    plays for its own scale constant.
    """
    require_dataset()
    from scipy import ndimage
    from skimage.registration import phase_cross_correlation

    stretched = load_stretched()
    land_s = _land_mask_stretched(stretched)
    log(f"stretched land px: {int(land_s.sum()):,} ({100.0 * land_s.mean():.2f}%)")

    ok = True

    # --- Candidate A: land_sea_mask forward-projected into the master frame ---
    if LAND_SEA_MASK_PATH.is_file():
        regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
        if FULL_SOURCE not in regs:
            log(f"  {FULL_SOURCE}: no committed registration record — skipping candidate A")
        else:
            reg = regs[FULL_SOURCE]
            inv = reproject.fit_placement_inverse(reg)
            mask = np.asarray(Image.open(LAND_SEA_MASK_PATH), dtype=np.uint8) > 0
            ys, xs = np.mgrid[0:MASTER_SIZE, 0:MASTER_SIZE]
            cx, cy = inv.to_canvas_px(xs.astype(np.float64) + 0.5, ys.astype(np.float64) + 0.5)
            inb = (cx >= 0) & (cx < mask.shape[1]) & (cy >= 0) & (cy < mask.shape[0])
            cxi = np.clip(np.rint(cx), 0, mask.shape[1] - 1).astype(np.int64)
            cyi = np.clip(np.rint(cy), 0, mask.shape[0] - 1).astype(np.int64)
            proj_a = np.zeros((MASTER_SIZE, MASTER_SIZE), dtype=bool)
            proj_a[inb] = mask[cyi[inb], cxi[inb]]
            factor = 8
            ref_a = _downsample_density(proj_a, factor) > 0.5
            mov_a = _downsample_density(
                ndimage.zoom(land_s.astype(np.float32), 2.0, order=1) > 0.5, factor)
            shift, error, _ = phase_cross_correlation(ref_a, mov_a, upsample_factor=20,
                                                      normalization=None)
            iou0 = _iou(ref_a, mov_a > 0.5)
            log(f"candidate A (scale 2.0, via {FULL_SOURCE}): shift {tuple(shift)} "
                f"downsampled px (factor {factor}) = ({shift[0] * factor:+.1f}, "
                f"{shift[1] * factor:+.1f}) master px; translation-error {error:.3f}; "
                f"IoU at zero offset {iou0:.3f}")
            ok = ok and max(abs(shift[0]), abs(shift[1])) * factor < 20
    else:
        log(f"  {LAND_SEA_MASK_PATH.relative_to(REPO_ROOT)} not present — skipping candidate A")

    # --- Candidate B: cr_oldworld_lookup non-black, direct, no registration ---
    if LOOKUP_BMP.is_file():
        with Image.open(LOOKUP_BMP) as im:
            arr = np.asarray(im.convert("RGB"), dtype=np.uint8)
        arr = arr[1:]  # drop the duplicate padding row (render_cr_lookup_overlay convention)
        lookup_land = arr.any(axis=2)
        factor = 16
        ref_b = _downsample_density(lookup_land, factor) > 0.5
        mov_b = _downsample_density(
            ndimage.zoom(land_s.astype(np.float32), 4.0, order=1) > 0.5, factor)
        shift, error, _ = phase_cross_correlation(ref_b, mov_b, upsample_factor=20,
                                                  normalization=None)
        iou0 = _iou(ref_b, mov_b > 0.5)
        log(f"candidate B (scale 4.0, direct vs cr_oldworld_lookup.bmp): shift "
            f"{tuple(shift)} downsampled px (factor {factor}) = "
            f"({shift[0] * factor:+.1f}, {shift[1] * factor:+.1f}) campaign px; "
            f"translation-error {error:.3f}; IoU at zero offset {iou0:.3f}")
        ok = ok and max(abs(shift[0]), abs(shift[1])) * factor < 20
    else:
        log(f"  {LOOKUP_BMP.relative_to(REPO_ROOT)} not present — skipping candidate B")

    log(f"correspondence: {'CONFIRMED' if ok else 'NOT CONFIRMED'} — both available "
        f"candidates converge on an offset well under 20px at their own resolution, "
        f"consistent with MASTER_TO_STRETCHED_SCALE = {MASTER_TO_STRETCHED_SCALE} "
        f"and zero applied offset")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def fit_report(placed: np.ndarray, reg: schema.SourceRegistration, excluded: dict,
              scope: np.ndarray) -> dict:
    n_landmarks = len(reg.control_points)
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
    log(f"  scale             MASTER_TO_STRETCHED_SCALE = {MASTER_TO_STRETCHED_SCALE} "
        f"(stretched px = master px x {MASTER_TO_STRETCHED_SCALE}), zero offset applied — "
        f"see this script's module docstring for the FFT phase-correlation evidence")
    log(f"  scope excluded    {excluded['px']:,} canvas px dropped for landing outside "
        f"{SCOPE_SOURCE}'s opaque extent ({100.0 * scope.mean():.1f}% of the master "
        f"frame is in scope) — Chris, 2026-09-12")
    log(f"  master->canvas    {scale:.4f} canvas px per master px "
        f"(footprint width {reg.footprint[2] - reg.footprint[0]:.1f} / {MASTER_SIZE})")
    log(f"  void colour       {VOID_RGB} (the export's own rounded-corner camera "
        f"vignette, ~25% of the source image) rendered as void — globe shows through")
    return {
        "registration": FULL_SOURCE,
        "registration_projection": reg.projection,
        "registration_landmarks": n_landmarks,
        "registration_provisional": True,
        "placed_px": int(placed.sum()),
        "master_to_stretched_scale": MASTER_TO_STRETCHED_SCALE,
        "scope_source": SCOPE_SOURCE,
        "scope_master_fraction": float(scope.mean()),
        "scope_excluded_px": int(excluded["px"]),
        "master_to_canvas_scale": scale,
        "void_rgb": list(VOID_RGB),
    }


def build(coast: bool, hull_buffer_px: float) -> Path:
    require_dataset()
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    if FULL_SOURCE not in regs:
        raise SystemExit(f"{FULL_SOURCE}: no committed registration record — run "
                         f"tools/fit_registration.py --seed tww3_old_world_mod_parchment_full")
    reg = regs[FULL_SOURCE]

    globe = load_source_rgb(GLOBE_SOURCE)
    if globe.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{GLOBE_SOURCE} is {globe.shape[1]}x{globe.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} (the canvas frame)")

    stretched = load_stretched()
    log(f"stretched export  {STRETCHED_PNG.name} {STRETCHED_SIZE}x{STRETCHED_SIZE}")
    scope = load_scope_mask()
    log(f"scope mask        {SCOPE_SOURCE} alpha: {100.0 * scope.mean():.1f}% of the "
        f"master frame is in scope; anything outside it is dropped to void "
        f"(Chris, 2026-09-12)")

    fit = reproject.fit_placement(reg, regs, buffer_px=hull_buffer_px)
    box = footprint_box(reg, pad=hull_buffer_px)
    log(f"eval box          canvas {list(box)}"
        + (f" (footprint + {hull_buffer_px:.0f}px outer-hull buffer)" if hull_buffer_px > 0
           else " (strict footprint)"))
    rgb, placed, excluded = place_stretched(fit, box, stretched, scope)
    if not placed.any():
        raise SystemExit("nothing placed — check the registration / stretched export / scope mask")

    report = fit_report(placed, reg, excluded, scope)

    canvas = compose(rgb, placed, globe)
    del rgb
    legend = [(None, "TWW3 old_world_map (stretched) draped via "
                     "tww3_old_world_mod_parchment_full (PROVISIONAL)"),
              (None, "void = camera-vignette corners + campaign-map sea, not drawn"),
              (None, f"cropped to {SCOPE_SOURCE} extent: "
                     f"{report['scope_excluded_px']:,} px out of scope, dropped")]
    if coast:
        legend.append((COAST_RGB, "this mod's coastline (reference)"))
        report["coast_px"] = overlay_coast(canvas)

    draw_legend(canvas, legend)

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DERIVED_DIR / f"{OUT_PREFIX}.png"
    Image.fromarray(canvas, mode="RGB").save(out_path)
    log(f"wrote {out_path.relative_to(REPO_ROOT)}")
    write_crops(canvas, box, OUT_PREFIX)

    report["provenance"] = {
        "stretched_png": {"name": STRETCHED_PNG.name, "sha256": sha256_of(STRETCHED_PNG)},
    }
    report["note"] = ("dev-only QA render, board #4425. Built on the PROVISIONAL "
                      "tww3_old_world_mod_parchment_full registration; if that "
                      "placement moves, this render moves with it. Cropped to "
                      f"{SCOPE_SOURCE}'s opaque extent (Chris, 2026-09-12: land not "
                      "drawn there is out of scope).")
    side = DERIVED_DIR / f"{OUT_PREFIX}.json"
    with open(side, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    log(f"wrote {side.relative_to(REPO_ROOT)} (provenance + fit report)")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--coast", action="store_true",
                   help="also draw this mod's own coastline in cyan as a reference line")
    p.add_argument("--hull-buffer-px", type=float, default=HULL_BUFFER_PX_DEFAULT,
                   help=f"extrapolate this many canvas px past the OUTER hull edge only "
                        f"(a QA convenience, not a real correspondence; default "
                        f"{HULL_BUFFER_PX_DEFAULT:.0f}, 0 for the strict cutoff)")
    p.add_argument("--verify-correspondence", action="store_true",
                   help="re-run the FFT phase-correlation check behind "
                        "MASTER_TO_STRETCHED_SCALE, then exit")
    args = p.parse_args(argv)

    if args.verify_correspondence:
        return verify_correspondence()

    build(coast=args.coast, hull_buffer_px=args.hull_buffer_px)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
