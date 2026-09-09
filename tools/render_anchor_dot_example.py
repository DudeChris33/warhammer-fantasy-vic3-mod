#!/usr/bin/env python3
"""Diagnostic render of a paired-anchor-dot placement, through the committed record.

Step 5 of the paired-anchor-dot registration workflow
(``planning/requests/register-old-world-region-anchor-dot-handoff.md``) as a
deterministic, reusable script instead of ad-hoc session code, in the accepted
Dark-Lands/Badlands render style: the clean source tile thin-plate-warped onto
the canvas through its **committed** registration record (no re-fit — the point
is to prove the committed placement still reproduces what the user accepted),
composited over a neutral backdrop, with the committed
``tools/derived/land_sea_mask.png`` coastline overlaid in cyan and the seed's
landmark dots as red rings, cropped to the record's footprint.

Writes ``tools/derived/<region>_anchor_dot_warp_example.png``, where
``<region>`` is the seed stem with the shared ``tww3_old_world_mod_parchment_``
prefix dropped (``badlands_nehekhara_anchor_dot_warp_example.png``, …).

``--combined`` composites the five Old World parchment tiles on one canvas — the
nine-zone coverage proof — as
``tools/derived/old_world_anchor_dot_warp_combined.png``. The z10 relief crop
(``start_warhammer_old_world_northern``) stays out of it: it overlaps the
parchment tiles and its downstream consumption is undecided.

Sources are read directly from ``sources/`` (not through the SHA-256 manifest
guard): this render runs mid-workflow, after an inpaint/restore and *before* the
user's ``--update-manifest`` sweep re-pins the hashes, which is exactly when the
guard would refuse. The gate (``sources.py --verify``) still owns integrity; a
QA render is evidence for a human, not pipeline input.

Everything is deterministic for a fixed stack: the warp is the committed
record's thin-plate field, sampling is bilinear, and no RNG or wall-clock enters.

Usage::

    python tools/render_anchor_dot_example.py --seed tww3_old_world_mod_parchment_empire
    python tools/render_anchor_dot_example.py --combined
    python tools/render_anchor_dot_example.py --all   # the five tiles + combined
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import derive_crop, raster, reproject, schema  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
SEED_DIR = TOOLS_DIR / "registration" / "seeds"
REGISTRATION_DIR = TOOLS_DIR / "registration"
SOURCES_DIR = TOOLS_DIR.parent / "sources"
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: The accepted render style (measured off the committed Badlands example).
BACKDROP_RGB = (60, 64, 72)
COAST_RGB = (0, 255, 255)
RING_RGB = (255, 0, 0)
RING_R_OUT = 8.5
RING_R_IN = 5.5

#: Warped-alpha threshold for "this canvas pixel shows tile content".
ALPHA_VALID = 127.5
#: Row block for warp evaluation — bounds the RBF's pairwise-distance temporaries.
ROW_BLOCK = 64

PARCHMENT_PREFIX = "tww3_old_world_mod_parchment_"

#: The five Old World parchment tiles, in the fixed compositing order used by
#: ``--combined`` (later tiles win where warped alpha overlaps along shared
#: borders; the crops' alpha masks are cut to be disjoint, so overlap is a
#: border-pixel affair, not a design decision).
FIVE_PARCHMENT = (
    "tww3_old_world_mod_parchment_bretonnia",
    "tww3_old_world_mod_parchment_empire",
    "tww3_old_world_mod_parchment_kislev_norsca",
    "tww3_old_world_mod_parchment_dark_lands",
    "tww3_old_world_mod_parchment_badlands_nehekhara",
)
COMBINED_PAD = 64
COMBINED_OUT = "old_world_anchor_dot_warp_combined.png"


def log(msg: str) -> None:
    print(msg, flush=True)


def load_seed(stem: str) -> dict:
    path = SEED_DIR / f"{stem}.json"
    if not path.is_file():
        raise SystemExit(f"no seed file at {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def out_name(stem: str) -> str:
    region = stem[len(PARCHMENT_PREFIX):] if stem.startswith(PARCHMENT_PREFIX) else stem
    return f"{region}_anchor_dot_warp_example.png"


def load_source_rgba(name: str) -> tuple[np.ndarray, np.ndarray | None]:
    """(rgb, alpha) — derives the five parchment crops on demand from their
    dots sheet (board #3570); everything else is still read directly from
    sources/ per this module's own no-manifest-guard convention."""
    stem = name[:-4] if name.endswith(".png") else name
    seed_path = derive_crop.SEED_DIR / f"{stem}.json"
    if seed_path.is_file():
        seed = derive_crop.load_seed(stem)
        dots_source = seed.get("dots_source")
        if dots_source:
            dots_rgb, dots_alpha = _read_source_rgba(dots_source)
            return derive_crop.derive_clean_source(dots_rgb, dots_alpha, seed)
    return _read_source_rgba(name)


def _read_source_rgba(name: str) -> tuple[np.ndarray, np.ndarray | None]:
    """``(rgb, alpha)`` read directly from ``sources/`` (see module docstring)."""
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing — restore it first (tools/inpaint_dot_markers.py)")
    with Image.open(path) as im:
        if im.mode == "RGBA":
            arr = np.asarray(im, dtype=np.uint8)
            return arr[..., :3].copy(), arr[..., 3].copy()
        if im.mode == "RGB":
            return np.asarray(im, dtype=np.uint8).copy(), None
        raise SystemExit(f"sources/{name}: unsupported image mode '{im.mode}'")


def footprint_box(reg: schema.SourceRegistration) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = reg.footprint
    return (max(0, int(np.floor(x0))), max(0, int(np.floor(y0))),
            min(CANVAS_W, int(np.ceil(x1))), min(CANVAS_H, int(np.ceil(y1))))


def warp_tile_into(canvas_rgb: np.ndarray, canvas_valid: np.ndarray,
                   box: tuple[int, int, int, int], reg: schema.SourceRegistration,
                   regs: dict[str, schema.SourceRegistration]) -> None:
    """Warp one tile through its committed record into ``canvas_rgb`` (in place).

    ``canvas_rgb``/``canvas_valid`` cover ``box`` (canvas px). Only canvas pixels
    whose warped source alpha exceeds ``ALPHA_VALID`` — and whose source
    coordinates land inside the image — are painted, so the crop's alpha mask is
    the contributing region exactly as it is for every pipeline consumer.
    """
    rgb, alpha = load_source_rgba(reg.source)
    sh, sw = rgb.shape[:2]
    fit = reproject.fit_placement(reg, regs)
    bx0, by0, bx1, by1 = footprint_box(reg)
    # Intersect the tile's own footprint with the render box.
    x0, y0 = max(bx0, box[0]), max(by0, box[1])
    x1, y1 = min(bx1, box[2]), min(by1, box[3])
    if x1 <= x0 or y1 <= y0:
        raise SystemExit(f"{reg.source}: footprint {reg.footprint} does not meet the render box {box}")

    alpha_f = (alpha if alpha is not None else np.full((sh, sw), 255, dtype=np.uint8)).astype(np.float64)
    gx = (np.arange(x0, x1, dtype=np.float64) + 0.5)[None, :]
    for yb in range(y0, y1, ROW_BLOCK):
        ye = min(yb + ROW_BLOCK, y1)
        gy = (np.arange(yb, ye, dtype=np.float64) + 0.5)[:, None]
        sx, sy = fit.to_source_px(np.broadcast_to(gx, (ye - yb, x1 - x0)),
                                  np.broadcast_to(gy, (ye - yb, x1 - x0)))
        inside = (sx >= 0) & (sx <= sw - 1) & (sy >= 0) & (sy <= sh - 1)
        a = reproject.resample(alpha_f, sx, sy, order=1)
        valid = inside & (a > ALPHA_VALID)
        if not valid.any():
            continue
        block = np.empty((ye - yb, x1 - x0, 3), dtype=np.uint8)
        for c in range(3):
            block[..., c] = np.clip(
                reproject.resample(rgb[..., c].astype(np.float64), sx, sy, order=1), 0, 255
            ).astype(np.uint8)
        oy, ox = yb - box[1], x0 - box[0]
        view_rgb = canvas_rgb[oy:oy + (ye - yb), ox:ox + (x1 - x0)]
        view_valid = canvas_valid[oy:oy + (ye - yb), ox:ox + (x1 - x0)]
        view_rgb[valid] = block[valid]
        view_valid |= valid


def overlay_coast(canvas_rgb: np.ndarray, box: tuple[int, int, int, int], land: np.ndarray) -> None:
    """Cyan coastline from the committed mask, ~3 px, drawn over everything."""
    x0, y0, x1, y1 = box
    sub = land[y0:y1, x0:x1]
    er = ndimage.binary_erosion(sub, structure=np.ones((3, 3), dtype=bool), border_value=True)
    edge = sub & ~er
    edge = ndimage.binary_dilation(edge, structure=np.ones((3, 3), dtype=bool))
    canvas_rgb[edge] = COAST_RGB


def _draw_ring(canvas_rgb: np.ndarray, cx: float, cy: float) -> None:
    """One red ring centered at ``(cx, cy)`` in ``canvas_rgb``'s own pixel frame."""
    h, w = canvas_rgb.shape[:2]
    r_out_i = int(np.ceil(RING_R_OUT))
    xa, xb = int(np.floor(cx - r_out_i)), int(np.ceil(cx + r_out_i)) + 1
    ya, yb = int(np.floor(cy - r_out_i)), int(np.ceil(cy + r_out_i)) + 1
    xa, ya = max(0, xa), max(0, ya)
    xb, yb = min(w, xb), min(h, yb)
    if xb <= xa or yb <= ya:
        return
    yy, xx = np.mgrid[ya:yb, xa:xb]
    d2 = (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2
    ring = (d2 <= RING_R_OUT ** 2) & (d2 >= RING_R_IN ** 2)
    canvas_rgb[ya:yb, xa:xb][ring] = RING_RGB


def draw_rings(canvas_rgb: np.ndarray, box: tuple[int, int, int, int], seed: dict) -> None:
    """The seed's landmark dots as red rings at their canvas positions."""
    for lm in seed["landmarks"]:
        _draw_ring(canvas_rgb, float(lm["canvas"][0]) - box[0], float(lm["canvas"][1]) - box[1])


def render_native(stem: str, out_file: str) -> Path:
    """Render one tile at its own native source resolution instead of its
    (typically much smaller) canvas footprint.

    The only thing actually projected onto the tile is the coastline overlay,
    so it is cheaper and sharper to sample the *mask* into source-pixel space
    through the inverse warp than to resample the *source* down into canvas
    space the way :func:`render` does. Landmark rings use the seed's own
    ``source`` positions directly — exact, no warp needed. Only meaningful for
    a single tile: a multi-tile ``--combined`` composite has no one shared
    "native" resolution across siblings.
    """
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    land = raster.read_mask_png(MASK_PATH)
    canvas_h, canvas_w = land.shape

    seed = load_seed(stem)
    reg = regs.get(seed["source"])
    if reg is None:
        raise SystemExit(f"{seed['source']}: no committed registration record")

    rgb, _alpha = load_source_rgba(reg.source)
    sh, sw = rgb.shape[:2]
    log(f"native size   {sw}x{sh} (source) vs {out_name(stem)!r}'s canvas footprint")

    inv = reproject.fit_warp_inverse(reg)
    log(f"inverse warp  rms {inv.rms_px:.2f}px  max {inv.max_px:.2f}px (source px)")

    land_f = land.astype(np.float64)
    land_at_source = np.zeros((sh, sw), dtype=bool)
    gx = (np.arange(sw, dtype=np.float64) + 0.5)[None, :]
    for yb in range(0, sh, ROW_BLOCK):
        ye = min(yb + ROW_BLOCK, sh)
        gy = (np.arange(yb, ye, dtype=np.float64) + 0.5)[:, None]
        cx, cy = inv.to_canvas_px(np.broadcast_to(gx, (ye - yb, sw)),
                                  np.broadcast_to(gy, (ye - yb, sw)))
        inside = (cx >= 0) & (cx <= canvas_w - 1) & (cy >= 0) & (cy <= canvas_h - 1)
        v = reproject.resample(land_f, cx, cy, order=0)
        land_at_source[yb:ye, :] = inside & (v > 0.5)

    canvas_rgb = rgb.copy()
    overlay_coast(canvas_rgb, (0, 0, sw, sh), land_at_source)
    for lm in seed["landmarks"]:
        _draw_ring(canvas_rgb, float(lm["source"][0]), float(lm["source"][1]))

    out = DERIVED_DIR / out_file
    Image.fromarray(canvas_rgb, mode="RGB").save(out)
    log(f"wrote {out}")
    return out


def render(stems: list[str], out_file: str, box_pad: int = 0) -> Path:
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    land = raster.read_mask_png(MASK_PATH)

    seeds = [load_seed(s) for s in stems]
    tile_regs = []
    for seed in seeds:
        reg = regs.get(seed["source"])
        if reg is None:
            raise SystemExit(f"{seed['source']}: no committed registration record")
        tile_regs.append(reg)

    boxes = [footprint_box(r) for r in tile_regs]
    box = (max(0, min(b[0] for b in boxes) - box_pad),
           max(0, min(b[1] for b in boxes) - box_pad),
           min(CANVAS_W, max(b[2] for b in boxes) + box_pad),
           min(CANVAS_H, max(b[3] for b in boxes) + box_pad))
    h, w = box[3] - box[1], box[2] - box[0]
    log(f"render box    canvas [{box[0]}, {box[1]}, {box[2]}, {box[3]}]  ({w}x{h})")

    canvas_rgb = np.empty((h, w, 3), dtype=np.uint8)
    canvas_rgb[...] = BACKDROP_RGB
    canvas_valid = np.zeros((h, w), dtype=bool)
    for seed, reg in zip(seeds, tile_regs):
        warp_tile_into(canvas_rgb, canvas_valid, box, reg, regs)
        log(f"tile          {reg.source} (footprint {[round(v) for v in reg.footprint]})")
    log(f"tile coverage {100.0 * canvas_valid.mean():.1f}% of the render box")

    overlay_coast(canvas_rgb, box, land)
    for seed in seeds:
        draw_rings(canvas_rgb, box, seed)

    out = DERIVED_DIR / out_file
    Image.fromarray(canvas_rgb, mode="RGB").save(out)
    log(f"wrote {out}")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", action="append", default=[],
                   help="seed stem under tools/registration/seeds/ (repeatable)")
    p.add_argument("--combined", action="store_true",
                   help=f"composite the five parchment tiles -> {COMBINED_OUT}")
    p.add_argument("--all", action="store_true",
                   help="the five per-region renders plus the combined one")
    p.add_argument("--native", action="store_true",
                   help="render a single --seed at its own native source resolution "
                        "(mask sampled onto it via the inverse warp) instead of its "
                        "canvas footprint; not valid with --combined/--all")
    args = p.parse_args(argv)

    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first")

    stems = list(args.seed)
    if args.all:
        stems = list(FIVE_PARCHMENT)
    if not stems and not args.combined:
        raise SystemExit("nothing to render — pass --seed <stem>, --combined, or --all")
    if args.native and (args.combined or args.all or len(stems) != 1):
        raise SystemExit("--native needs exactly one --seed and no --combined/--all")

    if args.native:
        render_native(stems[0], out_name(stems[0]))
        return 0

    for stem in stems:
        render([stem], out_name(stem))
    if args.combined or args.all:
        render(list(FIVE_PARCHMENT), COMBINED_OUT, box_pad=COMBINED_PAD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
