#!/usr/bin/env python3
"""QA render: the finer hand-painted Old World state map, draped on the globe.

Board item #2709 (a look-and-check step, nothing that ships). The user hand-
painted ``sources/old_world_state_regions.png`` — the tww3 parchment master frame
(4096², RGBA) with a per-state fill for every individual state and a magenta
(``255,0,255``) border network — on the *flat* parchment. This carries that
painting through the **five committed Old World crop registrations** onto a copy
of the reprojected globe (``sources/originals/terraqueous_globe_reprojected.png``,
the 8192×3616 canvas frame), so the state layout can be judged by eye against the
real coastline. It emits **both** warp variants under ``tools/derived/`` for a
side-by-side accept/reject verdict; nothing is committed here.

Two variants, **one displacement field, two sampling orders**:

* ``..._nearest.png``  — the painting's RGB warped with nearest sampling
  (``order=0``): hard per-state fills stay flat and the 1 px magenta border
  network is not aliased away.
* ``..._bilinear.png`` — the same warp with bilinear sampling (``order=1``): the
  smoother anchor-dot look (the warp that produced
  ``old_world_anchor_dot_warp_combined.png`` is these same registration records,
  sampled bilinearly). Fills and borders are antialiased.

The comparison the user is making is exactly that crisp-vs-smooth tradeoff, so the
two renders must be pixel-comparable: they share one drape footprint (the alpha
gates are *always* nearest — only the painting RGB sampling changes) and one output
frame.

By default the output is the whole reprojected-globe canvas (8192×3616); ``--crop``
trims it to the placed states' bounding box (plus ``--pad``) instead.

**Placement.** The five crops are axis-aligned pixel cutouts of the master
parchment, so each crop's integer offset ``(dx, dy)`` inside the master is
recovered exactly by :func:`scope.template_offset`. For a canvas pixel, the crop's
committed ``control_point_warp`` gives the **crop** pixel (``fit.to_source_px``);
adding the crop's offset reaches the **master** pixel; the painting shares the
master frame, so that master pixel is where it is sampled. A canvas pixel is
painted only where the crop's alpha and the painting's alpha are both opaque
there — "states only where painted", the globe showing through elsewhere.

**Coast overlay.** ``sources/terraqueous_globe_reprojected - coasts.png`` is the
plain globe with a coastline drawn on it in pure magenta (``255,0,255``); it is a
reference line, **not** the backdrop. The line is lifted by exact-magenta match
and drawn in cyan (``0,255,255``) on top of each composite as an alignment
reference.

Sources are read directly from ``sources/`` (not through the SHA-256 manifest
guard), the accepted QA-render convention (see ``render_anchor_dot_example.py``):
a QA render is evidence for a human, not pipeline input, and the offline gate
(``sources.py --verify``) still owns integrity for anything that ships.

Everything is deterministic for a fixed stack: the placement is the committed
thin-plate fields with fixed sampling orders, the offsets are an exact-pixel
argmax, and no RNG or wall-clock enters.

Usage::

    python tools/project_regions.py                    # both variants, full globe frame
    python tools/project_regions.py --variant nearest
    python tools/project_regions.py --crop --pad 128   # trim to the placed states
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import reproject, schema, scope  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
SOURCES_DIR = TOOLS_DIR.parent / "sources"
DERIVED_DIR = TOOLS_DIR / "derived"
REGISTRATION_DIR = TOOLS_DIR / "registration"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: The master parchment frame the five crops are cut from and the painting shares.
MASTER_SOURCE = "tww3_old_world_mod_parchment.png"
#: The finer per-state painting to drape (same 4096² master frame).
PAINT_SOURCE = "old_world_state_regions.png"
#: The reprojected globe that IS the canvas frame — the backdrop these states drape over.
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
#: The plain globe with a magenta coastline drawn on it — a reference line, not the backdrop.
COAST_SOURCE = "terraqueous_globe_reprojected - coasts.png"

#: The five Old World parchment crops, in the fixed compositing order used by
#: ``render_anchor_dot_example.FIVE_PARCHMENT``. The crops' alpha masks are **not**
#: disjoint — ~15% of covered master pixels fall under two or more crops — so the
#: order is a real precedence: the last crop covering a master pixel owns it (see
#: :func:`master_owner`), which is what keeps overlap-zone lines from doubling.
FIVE_CROPS = (
    "tww3_old_world_mod_parchment_bretonnia.png",
    "tww3_old_world_mod_parchment_empire.png",
    "tww3_old_world_mod_parchment_kislev_norsca.png",
    "tww3_old_world_mod_parchment_dark_lands.png",
    "tww3_old_world_mod_parchment_badlands_nehekhara.png",
)

MAGENTA_RGB = (255, 0, 255)
COAST_RGB = (0, 255, 255)

#: Warped-alpha threshold for "this pixel shows content" (matches render_anchor_dot_example).
ALPHA_VALID = 127.5
#: Row block for warp evaluation — bounds the RBF's pairwise-distance temporaries.
ROW_BLOCK = 64
#: Framing pad (canvas px) around the placed states' bounding box.
CROP_PAD = 64

OUT_PREFIX_DEFAULT = "old_world_state_regions_on_globe"


def log(msg: str) -> None:
    print(msg, flush=True)


def load_rgb(name: str) -> np.ndarray:
    """HxWx3 uint8 read directly from ``sources/`` (palette/RGBA flattened to RGB)."""
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8).copy()


def load_rgba(name: str) -> np.ndarray:
    """HxWx4 uint8 read directly from ``sources/`` (palette-aware via convert)."""
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.uint8).copy()


def footprint_box(reg: schema.SourceRegistration) -> tuple[int, int, int, int]:
    """The crop's canvas footprint, clamped to the frame (canvas px)."""
    x0, y0, x1, y1 = reg.footprint
    return (max(0, int(np.floor(x0))), max(0, int(np.floor(y0))),
            min(CANVAS_W, int(np.ceil(x1))), min(CANVAS_H, int(np.ceil(y1))))


def crop_offsets(master_gray: np.ndarray,
                 crop_rgba: dict[str, np.ndarray]) -> dict[str, tuple[int, int]]:
    """``{crop_name: (dx, dy)}`` — each crop's exact integer offset in the master.

    Each crop is an axis-aligned cutout of the master, so ``master_px = crop_px +
    (dx, dy)``. Logs the offset and its exact-pixel opaque agreement so a future
    re-crop that broke the cutout assumption surfaces here rather than as a silent
    misalignment in the render.
    """
    offsets: dict[str, tuple[int, int]] = {}
    for name in FIVE_CROPS:
        rgba = crop_rgba[name]
        crop_gray = rgba[..., :3].astype(np.float32).mean(axis=2)
        opaque = rgba[..., 3] > 0
        dx, dy = scope.template_offset(master_gray, crop_gray, opaque)
        ch, cw = rgba.shape[:2]
        sub = master_gray[dy:dy + ch, dx:dx + cw]
        agree = 100.0 * (sub[opaque] == crop_gray[opaque]).mean() if opaque.any() else 0.0
        region = name.replace("tww3_old_world_mod_parchment_", "").replace(".png", "")
        log(f"  offset  {region:<20} (dx={dx}, dy={dy})  {cw}x{ch}  exact-px {agree:.1f}%")
        offsets[name] = (dx, dy)
    return offsets


def master_owner(crop_rgba: dict[str, np.ndarray],
                 offsets: dict[str, tuple[int, int]],
                 master_shape: tuple[int, int]) -> np.ndarray:
    """Partition the master frame among the crops — ``owner[my, mx]`` = crop index.

    The five crops' alpha masks are **not** disjoint: ~15% of covered master pixels
    fall under two or more crops (the Bretonnia/Empire/Badlands stack is under
    three). Without a partition each such master pixel — a border line included —
    is warped once per covering crop through that crop's *different* registration
    field, landing at slightly different canvas positions: the doubled/tripled
    lines. Assigning every master pixel to a single crop places each line once.

    Ownership follows the ``FIVE_CROPS`` compositing order — the **last** crop
    covering a pixel wins, the same "later crops win" convention the per-canvas
    overwrite already used, now decided on the master frame where it actually
    removes the double-placement. ``-1`` marks master pixels no crop covers.
    """
    owner = np.full(master_shape, -1, dtype=np.int32)
    for i, name in enumerate(FIVE_CROPS):
        a = crop_rgba[name][..., 3] > ALPHA_VALID
        dx, dy = offsets[name]
        ch, cw = a.shape
        sub = owner[dy:dy + ch, dx:dx + cw]
        sub[a] = i
    return owner


def place_painting(order: int, regs: dict[str, schema.SourceRegistration],
                   paint_rgba: np.ndarray, crop_rgba: dict[str, np.ndarray],
                   offsets: dict[str, tuple[int, int]],
                   globe_rgb: np.ndarray, owner: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Drape the painting onto a copy of the globe. Returns ``(canvas_rgb, placed)``.

    ``order`` is the painting-RGB sampling order (0 nearest, 1 bilinear). **Both
    alpha gates are always nearest** so the two variants share an identical drape
    footprint — the only difference between them is fill/border crispness. Elsewhere
    the globe shows through.

    ``owner`` (from :func:`master_owner`) partitions the master frame so each master
    pixel is drawn by exactly one crop: a crop paints a canvas pixel only where it
    owns the master pixel it maps to, so lines in the crops' overlap zones are placed
    once rather than doubled per covering crop.
    """
    canvas_rgb = globe_rgb.copy()
    placed = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)

    ph, pw = paint_rgba.shape[:2]
    paint_planes = [paint_rgba[..., c].astype(np.float32) for c in range(3)]
    paint_alpha = paint_rgba[..., 3].astype(np.float32)
    owner_f = owner.astype(np.float32)

    for idx, name in enumerate(FIVE_CROPS):
        reg = regs[name]
        dx, dy = offsets[name]
        crop_alpha = crop_rgba[name][..., 3].astype(np.float32)
        ch, cw = crop_rgba[name].shape[:2]
        fit = reproject.fit_placement(reg, regs)
        bx0, by0, bx1, by1 = footprint_box(reg)
        if bx1 <= bx0 or by1 <= by0:
            raise SystemExit(f"{name}: empty footprint box {reg.footprint}")

        gx = (np.arange(bx0, bx1, dtype=np.float64) + 0.5)[None, :]
        for yb in range(by0, by1, ROW_BLOCK):
            ye = min(yb + ROW_BLOCK, by1)
            gy = (np.arange(yb, ye, dtype=np.float64) + 0.5)[:, None]
            gxb = np.broadcast_to(gx, (ye - yb, bx1 - bx0))
            gyb = np.broadcast_to(gy, (ye - yb, bx1 - bx0))
            # canvas -> crop px, then crop -> master px by the exact cutout offset.
            sx_c, sy_c = fit.to_source_px(gxb, gyb)
            mx = sx_c + dx
            my = sy_c + dy

            in_crop = (sx_c >= 0) & (sx_c <= cw - 1) & (sy_c >= 0) & (sy_c <= ch - 1)
            in_master = (mx >= 0) & (mx <= pw - 1) & (my >= 0) & (my <= ph - 1)
            ca = reproject.resample(crop_alpha, sx_c, sy_c, order=0)
            pa = reproject.resample(paint_alpha, mx, my, order=0)
            own = reproject.resample(owner_f, mx, my, order=0)
            valid = (in_crop & in_master & (ca > ALPHA_VALID) & (pa > ALPHA_VALID)
                     & (np.rint(own) == idx))
            if not valid.any():
                continue

            block = np.empty((ye - yb, bx1 - bx0, 3), dtype=np.uint8)
            for c in range(3):
                block[..., c] = np.clip(
                    reproject.resample(paint_planes[c], mx, my, order=order), 0, 255
                ).astype(np.uint8)
            view_rgb = canvas_rgb[yb:ye, bx0:bx1]
            view_placed = placed[yb:ye, bx0:bx1]
            view_rgb[valid] = block[valid]
            view_placed |= valid
    return canvas_rgb, placed


def overlay_coast(canvas_rgb: np.ndarray, coasts_rgb: np.ndarray) -> int:
    """Draw the coasts PNG's magenta line onto ``canvas_rgb`` in cyan (in place).

    Returns the number of coastline pixels drawn. Full-frame; run before cropping.
    """
    r, g, b = MAGENTA_RGB
    line = ((coasts_rgb[..., 0] == r) & (coasts_rgb[..., 1] == g) & (coasts_rgb[..., 2] == b))
    canvas_rgb[line] = COAST_RGB
    return int(line.sum())


def placement_box(placed: np.ndarray, pad: int) -> tuple[int, int, int, int]:
    """Bounding box of the placed states + ``pad``, clipped to the canvas frame."""
    ys, xs = np.nonzero(placed)
    if not ys.size:
        raise SystemExit("nothing placed — check the painting / registrations")
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(CANVAS_W, int(xs.max()) + 1 + pad)
    y1 = min(CANVAS_H, int(ys.max()) + 1 + pad)
    return (x0, y0, x1, y1)


def build(variants: list[str], pad: int, out_prefix: str,
          paint_source: str = PAINT_SOURCE, overlay_coasts: bool = True,
          full_frame: bool = True, globe_source: str = GLOBE_SOURCE) -> list[Path]:
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    for name in FIVE_CROPS:
        if name not in regs:
            raise SystemExit(f"{name}: no committed registration record")

    master_rgb = load_rgb(MASTER_SOURCE)
    paint_rgba = load_rgba(paint_source)
    crop_rgba = {name: load_rgba(name) for name in FIVE_CROPS}
    globe_rgb = load_rgb(globe_source)
    coasts_rgb = load_rgb(COAST_SOURCE) if overlay_coasts else None

    if globe_rgb.shape[1] != CANVAS_W or globe_rgb.shape[0] != CANVAS_H:
        raise SystemExit(f"{globe_source} is {globe_rgb.shape[1]}x{globe_rgb.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} (the canvas frame)")
    if coasts_rgb is not None and coasts_rgb.shape[:2] != globe_rgb.shape[:2]:
        raise SystemExit(f"{COAST_SOURCE} is {coasts_rgb.shape[1]}x{coasts_rgb.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} to match the globe")
    if master_rgb.shape[:2] != paint_rgba.shape[:2]:
        raise SystemExit(f"painting {paint_rgba.shape[1]}x{paint_rgba.shape[0]} does not "
                         f"share the master frame {master_rgb.shape[1]}x{master_rgb.shape[0]}")

    painted_frac = 100.0 * (paint_rgba[..., 3] > 0).mean()
    log(f"painting {paint_rgba.shape[1]}x{paint_rgba.shape[0]}  "
        f"alpha-covered {painted_frac:.1f}%")

    log("locating the five crops in the master frame:")
    master_gray = master_rgb.astype(np.float32).mean(axis=2)
    offsets = crop_offsets(master_gray, crop_rgba)

    # Partition the master among the crops so overlap-zone lines are placed once.
    owner = master_owner(crop_rgba, offsets, paint_rgba.shape[:2])
    covered = (owner >= 0).sum()
    raw = sum(int((crop_rgba[n][..., 3] > ALPHA_VALID).sum()) for n in FIVE_CROPS)
    log(f"master owner  {covered:,} px owned; {raw - covered:,} overlap px "
        f"({100.0 * (raw - covered) / max(raw, 1):.1f}%) resolved to a single crop")

    # The nearest pass fixes the shared crop box (both passes drape the same
    # footprint, since the alpha gates do not depend on `order`).
    base_rgb, placed = place_painting(0, regs, paint_rgba, crop_rgba, offsets, globe_rgb, owner)
    box = (0, 0, CANVAS_W, CANVAS_H) if full_frame else placement_box(placed, pad)
    x0, y0, x1, y1 = box
    log(f"placed        {100.0 * placed.mean():.3f}% of the frame "
        f"({int(placed.sum()):,} px)")
    label = "full frame" if full_frame else "crop box"
    log(f"{label:<13} canvas [{x0}, {y0}, {x1}, {y1}]  ({x1 - x0}x{y1 - y0})")

    order_by_variant = {"nearest": 0, "bilinear": 1}
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for variant in variants:
        order = order_by_variant[variant]
        canvas_rgb = base_rgb if order == 0 else place_painting(
            order, regs, paint_rgba, crop_rgba, offsets, globe_rgb, owner)[0]
        n_coast = overlay_coast(canvas_rgb, coasts_rgb) if coasts_rgb is not None else 0
        crop = canvas_rgb[y0:y1, x0:x1].copy()
        out_path = DERIVED_DIR / f"{out_prefix}_{variant}.png"
        Image.fromarray(crop, mode="RGB").save(out_path)
        log(f"wrote {out_path.relative_to(TOOLS_DIR.parent)}  "
            f"({variant}, coast {n_coast:,} px)")
        written.append(out_path)
    return written


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--variant", choices=("both", "nearest", "bilinear"), default="both",
                   help="which warp variant(s) to emit (default both)")
    p.add_argument("--pad", type=int, default=CROP_PAD,
                   help=f"framing pad in canvas px around the placed states, with --crop "
                        f"(default {CROP_PAD}; ignored on the default full frame)")
    p.add_argument("--out-prefix", default=OUT_PREFIX_DEFAULT,
                   help=f"output filename prefix under tools/derived/ (default {OUT_PREFIX_DEFAULT})")
    p.add_argument("--paint", default=PAINT_SOURCE,
                   help=f"the master-frame painting (4096², RGBA) to drape (default {PAINT_SOURCE}); "
                        f"e.g. 'old_world_state_regions - borders_only.png' drapes only the "
                        f"magenta border network so the globe shows through everywhere else")
    p.add_argument("--no-coast", action="store_true",
                   help="skip the cyan coastline reference overlay (drape the painting alone)")
    p.add_argument("--crop", action="store_true",
                   help="crop to the placed states' bounding box (+--pad) instead of the "
                        "default full reprojected-globe canvas (8192x3616)")
    p.add_argument("--globe", default=GLOBE_SOURCE,
                   help=f"the backdrop to drape the painting over (default {GLOBE_SOURCE}); "
                        f"must share the canvas frame ({CANVAS_W}x{CANVAS_H}), e.g. "
                        f"'terraqueous_globe_reprojected - sea_zones.png'")
    args = p.parse_args(argv)

    variants = ["nearest", "bilinear"] if args.variant == "both" else [args.variant]
    build(variants, args.pad, args.out_prefix,
          paint_source=args.paint, overlay_coasts=not args.no_coast,
          full_frame=not args.crop, globe_source=args.globe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
