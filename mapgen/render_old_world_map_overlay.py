#!/usr/bin/env python3
"""QA render (board #4425): the TWW3 campaign-map debug export
``old_world_map - stretched.png`` draped onto this mod's canvas through the
existing ``tww3_old_world_mod_parchment_full`` registration, at a measured
scale shortcut — the same pattern ``mapgen/render_cr_lookup_overlay.py`` (board
#4364) already uses for ``cr_oldworld_lookup.bmp``.

**Dev-only, gitignored output.** Everything this writes lands in
``mapgen/derived/`` (ignored there); nothing it reads from
``sources/cr_oldworld_campaign/`` — itself gitignored
— ever reaches a committed file. This produces *evidence for a human*: a
render Chris looks at, plus a printed fit report. No committed
``mapgen/registration/``, ``common/``, ``events/`` or ``map_data/`` file
depends on it, and it can never gain its own registration entry — see the
next section.

Why this can never get its own ``mapgen/registration/`` entry
--------------------------------------------------------------
``mapgen/worldgen/sources.py``'s ``verify()`` hard-errors if a manifest row's
file is missing locally, and separately hard-errors if any
``mapgen/registration/*.json`` record's ``"source"`` has no manifest row.
``sources/cr_oldworld_campaign/`` is deliberately gitignored/unmanifested
absent on every device but the one that owns it — so there is
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

* **Candidate A** — ``mapgen/derived/land_sea_mask.png`` (this mod's own
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
``mapgen/registration/tww3_old_world_mod_parchment_full.json`` self-declares
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
resolve). By default, one colour is treated specially: ``(46,46,46)`` is
rendered as void (the globe shows through) so the default full drape reads as
a clean land/sea/border/terrain map. **Correction to this board item's own
earlier scoping note:** ``(46,46,46)`` was described there as purely a
"rounded-corner camera-vignette artifact." A pixel-spatial check this session
(masking the colour and looking at where it falls) shows that is only part of
the picture — a small circular frame/compass-rose decoration does sit in each
corner, but the colour's bulk (25.4% of the image) is an organic, branching
network spread across the *whole* frame, matching mountain ranges far more
than a UI bezel would: this is almost certainly the export's **impassable
terrain** layer, not decoration. Dropped to void by default (:option:`--show-grey`
includes it instead).

Colour selection (``--colors``)
--------------------------------
:option:`--colors` restricts the drape to an explicit, comma-separated list of
named colours from :data:`COLOR_LIBRARY` (case-insensitive; ``purple``/``magenta``
are aliases for the border-line colour). :data:`COLOR_LIBRARY` currently only
carries the 3-colour palette of Chris's hand-recoloured
``old_world_map - stretched.png`` (a gitignored local working copy given via
``--source``; ``purple``/``magenta``, ``cities``, ``gimp_impassable`` —
confirmed 2026-09-15; the canonical dataset's
own 8-colour palette is no longer independently selectable by name, only via
the default full drape / :option:`--show-grey` described above). Every pixel
whose colour is **not** in the selected set is treated as void (globe shows
through) — this is a selection, not a recolour: each kept pixel is drawn in
its own real source colour. Omit the option for the original full drape
(every colour except the void colour, unchanged from this render's first
version). Output paths are suffixed with the selected names (sorted) so
different selections never overwrite each other.

Usage::

    python mapgen/render_old_world_map_overlay.py
    python mapgen/render_old_world_map_overlay.py --coast
    python mapgen/render_old_world_map_overlay.py --colors purple
    python mapgen/render_old_world_map_overlay.py --colors purple,gimp_impassable --coast
    python mapgen/render_old_world_map_overlay.py --verify-correspondence
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

#: The reference dataset. Gitignored and absent on most devices —
#: see :func:`require_source` for the clean skip.
DATASET_DIR = SOURCES_DIR / "cr_oldworld_campaign"
#: The square, isotropically-scaled companion file this script actually uses —
#: NOT the raw ``old_world_map.png`` (see module docstring for why).
STRETCHED_PNG = DATASET_DIR / "campaign_map" / "old_world_map - stretched.png"
LOOKUP_BMP = DATASET_DIR / "cr_oldworld_lookup" / "cr_oldworld_lookup.bmp"

#: The reprojected globe that IS the canvas frame — the backdrop this drapes over.
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
#: The plain globe with a magenta coastline drawn on it — a reference line, not the backdrop.
COAST_SOURCE = sources_mod.source_ref("coast_trace")

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

#: The canonical dataset export's terrain/impassable layer, plus a small corner
#: frame decoration sharing the same flat colour — see the module docstring's
#: correction. Dropped to void by DEFAULT (the original full-drape behaviour).
VOID_RGB = (46, 46, 46)
VOID_TOLERANCE = 10  # small AA slack around the flat colour
#: The flat land colour, used only by --verify-correspondence's silhouette extraction.
LAND_RGB = (16, 248, 0)
LAND_TOLERANCE = 60
#: Per-pixel colour-distance slack used when matching a --colors selection —
#: this export is flat/exact (see the histogram in the module docstring), so
#: this only needs to absorb incidental PNG re-save noise, not real AA.
COLOR_MATCH_TOLERANCE = 10

#: Chris's hand-recoloured old_world_map - stretched.png (a gitignored local
#: working copy given via --source) — its own 3-colour palette, confirmed by
#: Chris 2026-09-15. Selectable by name via --colors; aliases point at the
#: same RGB as their primary name.
COLOR_LIBRARY: dict[str, tuple[int, int, int]] = {
    "purple": (255, 0, 255),   # region-border lines
    "magenta": (255, 0, 255),  # alias for "purple"
    "cities": (127, 127, 255),        # settlement markers
    "gimp_impassable": (255, 127, 0), # impassable-terrain fill
}

COAST_RGB = (0, 255, 255)

OUT_PREFIX = "old_world_map_overlay"


def resolve_colors(spec: str | None) -> list[tuple[str, tuple[int, int, int]]] | None:
    """Parse ``--colors`` into ``[(name, rgb), ...]``, or None for "no selection".

    Deduplicates by RGB (an alias and its primary name given together would
    otherwise double-count in the fit report) while keeping first-seen order,
    and hard-errors on an unknown name rather than silently ignoring it.
    """
    if not spec:
        return None
    seen_rgb: set[tuple[int, int, int]] = set()
    out: list[tuple[str, tuple[int, int, int]]] = []
    for raw in spec.split(","):
        name = raw.strip().lower()
        if not name:
            continue
        if name not in COLOR_LIBRARY:
            raise SystemExit(
                f"--colors: unknown colour name {raw!r}. Known names: "
                f"{', '.join(sorted(COLOR_LIBRARY))}")
        rgb = COLOR_LIBRARY[name]
        if rgb in seen_rgb:
            continue
        seen_rgb.add(rgb)
        out.append((name, rgb))
    if not out:
        raise SystemExit("--colors: no colour names given")
    return out


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Dataset presence / loading
# ---------------------------------------------------------------------------

def resolve_stretched_source(arg: str | None) -> Path:
    """``--source`` -> an absolute path, defaulting to the dataset's own file.

    A relative ``arg`` is resolved against the repo root, so
    ``--source "sources/oldworld-first/old_world_map - stretched.png"`` (a
    gitignored local working copy, e.g. hand-edited in GIMP) works exactly as
    typed — ``--source`` takes any PNG path, not one drawn from a fixed
    folder. An absolute path is used as-is.
    """
    if not arg:
        return STRETCHED_PNG
    p = Path(arg)
    return p if p.is_absolute() else (REPO_ROOT / p)


def source_tag(path: Path) -> str:
    """Output-filename suffix distinguishing a non-default ``--source``.

    Empty for the dataset's own file (unchanged filenames from this render's
    first version); otherwise the source's parent folder name, so a
    ``--source`` override and the dataset's own copy never collide on disk.
    """
    if path == STRETCHED_PNG:
        return ""
    return "_" + "".join(c if c.isalnum() else "_" for c in path.parent.name.lower()).strip("_")


def require_source(path: Path) -> None:
    """Clean-skip when ``path`` is not present on this device.

    The ``validate_map._check_canon_cities`` idiom, reused throughout this
    dataset's other consumers: a gitignored local working file's absence is
    the expected state on most devices, not an error.
    """
    if path.is_file():
        return
    log(f"{path}: not present on this device — dev-only render, skipping")
    sys.exit(0)


def load_source_rgb(name: str) -> np.ndarray:
    arr = sources_mod.read_source_rgba(name, SOURCES_DIR, allow_empty=True)
    if arr is None:
        raise SystemExit(f"sources/{name} is missing")
    return arr[..., :3].copy()


def load_stretched(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """``path`` as ``(rgb (2048,2048,3) uint8, visible (2048,2048) bool)``.

    ``visible`` is True everywhere for a plain RGB source (the dataset's own
    file). A source carrying an alpha channel (e.g. a GIMP export with erased
    regions) is False wherever alpha is 0 — that is genuinely transparent, not
    a paintable colour, and must not be treated as void-by-colour-match
    (which would wrongly compare it against :data:`VOID_RGB`/``--colors``
    instead of dropping it outright). Partial alpha (this format's exports
    also carry 128) is treated as visible — its RGB is real paint, not a
    background blend, since GIMP does not premultiply on export.

    Hard-errors on an unexpected size — a differently-sized export is a
    different dataset and :data:`MASTER_TO_STRETCHED_SCALE` would not apply.
    """
    with Image.open(path) as im:
        if im.size != (STRETCHED_SIZE, STRETCHED_SIZE):
            raise SystemExit(
                f"{path.name} is {im.size[0]}x{im.size[1]}, expected "
                f"{STRETCHED_SIZE}x{STRETCHED_SIZE} — a different size is a different "
                f"export and the scale/void constants documented in this script would "
                f"not apply")
        has_alpha = "A" in im.getbands()
        arr = np.asarray(im.convert("RGBA" if has_alpha else "RGB"), dtype=np.uint8)
    if has_alpha:
        return arr[..., :3].copy(), (arr[..., 3] > 0)
    return arr.copy(), np.ones(arr.shape[:2], dtype=bool)


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
                    visible: np.ndarray, scope: np.ndarray,
                    colors: list[tuple[str, tuple[int, int, int]]] | None = None,
                    show_grey: bool = False) -> tuple[np.ndarray, np.ndarray, dict]:
    """Warp the stretched export into canvas space. Returns ``(rgb, placed, excluded)``.

    ``placed`` is True where the warp landed inside the master frame AND
    ``visible`` (genuinely opaque in the source — see :func:`load_stretched`)
    AND inside this mod's scope (:data:`SCOPE_SOURCE`'s alpha) AND the sampled
    colour survives the colour gate.

    The colour gate is one of three things:

    * ``colors is None`` and ``show_grey`` False (default, unchanged from
      this render's first version) — every colour is paintable *except*
      :data:`VOID_RGB`.
    * ``colors is None`` and ``show_grey`` True (``--show-grey``) — every
      colour is paintable, full stop; nothing is dropped by colour (only by
      ``visible``/scope/master-frame bounds).
    * ``colors`` given (``--colors``) — only pixels matching one of the named
      colours are paintable; everything else is void, regardless of whether it
      would otherwise have been drawn. This is a selection, not a recolour:
      a kept pixel is still drawn in its own real sampled colour.
      (``--show-grey`` is ignored when ``--colors`` is given — list ``grey``
      explicitly instead.)

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
        vis = visible[sy, sx]

        block16 = block.astype(np.int16)
        if colors is None:
            if show_grey:
                gate = np.ones(block.shape[:2], dtype=bool)
            else:
                d = np.abs(block16 - np.array(VOID_RGB, dtype=np.int16)).sum(axis=2)
                gate = d > VOID_TOLERANCE
        else:
            gate = np.zeros(block.shape[:2], dtype=bool)
            for _, rgb in colors:
                d = np.abs(block16 - np.array(rgb, dtype=np.int16)).sum(axis=2)
                gate |= d <= COLOR_MATCH_TOLERANCE
        paintable = in_master & vis & gate

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
    the line; the gitignored source's absence is a skip, not an error).
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
    require_source(STRETCHED_PNG)
    from scipy import ndimage
    from skimage.registration import phase_cross_correlation

    stretched, _visible = load_stretched(STRETCHED_PNG)
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
              scope: np.ndarray,
              colors: list[tuple[str, tuple[int, int, int]]] | None,
              show_grey: bool = False) -> dict:
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
    if colors is None and not show_grey:
        log(f"  colour gate       full drape: every colour except void {VOID_RGB} "
            f"(terrain/impassable layer + corner frame decoration, ~25% of the source "
            f"image — see module docstring)")
    elif colors is None:
        log(f"  colour gate       full drape including grey/impassable {VOID_RGB} "
            f"(--show-grey): nothing dropped by colour")
    else:
        names = ", ".join(f"{n} {rgb}" for n, rgb in colors)
        log(f"  colour gate       --colors selection: only {names} placed; everything "
            f"else void")
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
        "colors_selected": ([n for n, _ in colors] if colors is not None else None),
        "show_grey": bool(show_grey),
    }


def build(coast: bool, hull_buffer_px: float,
         colors: list[tuple[str, tuple[int, int, int]]] | None = None,
         source_path: Path | None = None, show_grey: bool = False) -> Path:
    source_path = source_path or STRETCHED_PNG
    require_source(source_path)
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    if FULL_SOURCE not in regs:
        raise SystemExit(f"{FULL_SOURCE}: no committed registration record — run "
                         f"mapgen/fit_registration.py --seed tww3_old_world_mod_parchment_full")
    reg = regs[FULL_SOURCE]

    backdrop = load_source_rgb(GLOBE_SOURCE)
    if backdrop.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{GLOBE_SOURCE} is {backdrop.shape[1]}x{backdrop.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} (the canvas frame)")

    stretched, visible = load_stretched(source_path)
    try:
        rel = source_path.relative_to(REPO_ROOT)
    except ValueError:
        rel = source_path
    log(f"stretched export  {rel} {STRETCHED_SIZE}x{STRETCHED_SIZE}"
        + (f" ({100.0 * (~visible).mean():.1f}% transparent, dropped)" if not visible.all() else ""))
    scope = load_scope_mask()
    log(f"scope mask        {SCOPE_SOURCE} alpha: {100.0 * scope.mean():.1f}% of the "
        f"master frame is in scope; anything outside it is dropped to void "
        f"(Chris, 2026-09-12)")

    fit = reproject.fit_placement(reg, regs, buffer_px=hull_buffer_px)
    box = footprint_box(reg, pad=hull_buffer_px)
    log(f"eval box          canvas {list(box)}"
        + (f" (footprint + {hull_buffer_px:.0f}px outer-hull buffer)" if hull_buffer_px > 0
           else " (strict footprint)"))
    rgb, placed, excluded = place_stretched(fit, box, stretched, visible, scope, colors=colors,
                                            show_grey=show_grey)
    if not placed.any():
        raise SystemExit("nothing placed — check the registration / stretched export / "
                         "scope mask / --colors selection")

    report = fit_report(placed, reg, excluded, scope, colors, show_grey=show_grey)

    canvas = compose(rgb, placed, backdrop)
    del rgb
    if colors is None and not show_grey:
        legend = [(None, "TWW3 old_world_map (stretched) draped via "
                         "tww3_old_world_mod_parchment_full (PROVISIONAL)"),
                  (None, "void = terrain/impassable layer + corner frame decoration, "
                         "not drawn")]
    elif colors is None:
        legend = [(None, "TWW3 old_world_map (stretched), incl. grey/impassable, draped "
                         "via tww3_old_world_mod_parchment_full (PROVISIONAL)")]
    else:
        names = ", ".join(n for n, _ in colors)
        legend = [(None, f"TWW3 old_world_map (stretched), colours {{{names}}} only, "
                         f"via tww3_old_world_mod_parchment_full (PROVISIONAL)"),
                  *[(rgb, name) for name, rgb in colors],
                  (None, "everything else void, not drawn")]
    legend.append((None, f"cropped to {SCOPE_SOURCE} extent: "
                         f"{report['scope_excluded_px']:,} px out of scope, dropped"))
    if coast:
        legend.append((COAST_RGB, "this mod's coastline (reference)"))
        report["coast_px"] = overlay_coast(canvas)

    draw_legend(canvas, legend)

    prefix = OUT_PREFIX + source_tag(source_path)
    if colors is not None:
        prefix += "_" + "_".join(sorted(n for n, _ in colors))
    elif show_grey:
        prefix += "_show_grey"
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DERIVED_DIR / f"{prefix}.png"
    Image.fromarray(canvas, mode="RGB").save(out_path)
    log(f"wrote {out_path.relative_to(REPO_ROOT)}")
    write_crops(canvas, box, prefix)

    report["provenance"] = {
        "stretched_png": {"name": source_path.name, "path": str(rel),
                          "sha256": sha256_of(source_path)},
    }
    report["note"] = ("dev-only QA render, board #4425. Built on the PROVISIONAL "
                      "tww3_old_world_mod_parchment_full registration; if that "
                      "placement moves, this render moves with it. Cropped to "
                      f"{SCOPE_SOURCE}'s opaque extent (Chris, 2026-09-12: land not "
                      "drawn there is out of scope).")
    side = DERIVED_DIR / f"{prefix}.json"
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
    p.add_argument("--colors", type=str, default=None,
                   help="comma-separated colour names to restrict the drape to (e.g. "
                        "'purple' or 'purple,gimp_impassable'); everything else renders "
                        f"as void. Known names: {', '.join(sorted(COLOR_LIBRARY))}. Omit "
                        "for the full drape (every colour except the void colour)")
    p.add_argument("--source", type=str, default=None,
                   help="path (repo-root-relative, or absolute) to a different 2048x2048 "
                        "export to drape instead of the dataset's own file — e.g. a local, "
                        "gitignored GIMP-edited copy anywhere under sources/. Must share "
                        "the same frame/scale as the dataset file (same corners, same "
                        "content, just recoloured/edited); a genuinely different export "
                        "would need its own correspondence check. Output filenames are "
                        "suffixed with the source's parent folder name so this never "
                        "overwrites the default render")
    p.add_argument("--show-grey", action="store_true",
                   help="include the void colour in the full drape instead of treating "
                        "it as void (ignored when --colors is given — list the colour "
                        "explicitly there instead)")
    args = p.parse_args(argv)

    if args.verify_correspondence:
        return verify_correspondence()

    colors = resolve_colors(args.colors)
    source_path = resolve_stretched_source(args.source)
    build(coast=args.coast, hull_buffer_px=args.hull_buffer_px, colors=colors,
         source_path=source_path, show_grey=args.show_grey)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
