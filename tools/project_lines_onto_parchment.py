#!/usr/bin/env python3
"""QA render: canvas-space line art, projected back onto the master parchment.

The reverse of ``tools/project_regions.py``'s parchment -> canvas drape. Where
that script warps a *parchment-space* painting onto the canvas through the
five committed Old World crop registrations, this one takes a *canvas-space*
line-art export (colour-coded coastline/river/border traces, canvas frame
8192x3616) and projects it back onto a master-parchment-frame target (4096x4096,
the same frame ``tww3_old_world_mod_parchment.png`` and
``old_world_state_regions.png`` share) — so hand-drawn canvas work can be
eyeballed against the original mod parchment's own printed lines.

**Mechanism.** For each of the five committed crop registrations: its
``control_point_warp`` is refit in reverse (:func:`worldgen.reproject.fit_warp_inverse`
— same idiom as ``render_anchor_dot_example.py --native``) to get a crop-local
pixel -> canvas pixel field. The crop's exact integer offset in the master is
recovered by template match (:func:`worldgen.scope.template_offset`, same as
``project_regions.py``'s :func:`crop_offsets`), so crop-local pixel + offset =
master pixel. Walking every master pixel the crop's own alpha covers, sampling
the canvas line-art through the inverse warp, and painting a hit onto the
target at that master pixel reconstructs the crop's footprint of the canvas
source directly on the parchment frame.

**Colour classes, not just one.** ``--colors`` (default ``red,magenta,cyan``)
names which flat colours in the canvas source count as "line" pixels; each
sampled hit keeps its own colour on the target, so multiple traced networks
(coastline, rivers, state borders, ...) come through as distinct, still
colour-coded lines rather than being flattened to one mark.

**Overlap.** The five crops overlap by ~15% of their master footprint (see
``project_regions.py``'s ``FIVE_CROPS`` comment). Unlike the forward direction
— where a canvas pixel's *source* coordinate has to be warped before its
coverage can be tested, hence :func:`project_regions.canvas_owner`'s
canvas-space partition — a **master** pixel's crop coverage needs no warp at
all: each crop's own alpha mask sits at a plain integer offset in the master
frame, so ownership is decided directly there. :func:`master_owner` gives each
overlapping master pixel to whichever crop's coverage mask runs deepest at
that point (the same Euclidean-distance-transform Voronoi idiom as
``canvas_owner``, just simpler since it needs no warp), and the paint loop
only writes a pixel when its owning crop says so. This matters: painting
"later crop overwrites earlier" pixel-by-pixel is *not* equivalent to true
ownership — a later crop only overwrites where *it itself* finds a line hit,
so anywhere its own (slightly different) warp of the same canvas line misses
the earlier crop's placement, the earlier crop's stroke survives untouched,
and the overlap band shows both crops' independent reconstructions of the
same line side by side (a real double-line bug, not a rendering choice).
:func:`master_owner` fixes this by deciding, in advance, exactly one crop per
pixel — a pixel outside that crop's verdict is left as the target's own
content, never an orphaned stroke from a different crop.

Nothing here writes into ``sources/`` — the output is a copy of ``--target``
with the projected lines painted on, written under ``tools/derived/``. A
QA/reference projection only; feeds nothing downstream.

Usage::

    python tools/project_lines_onto_parchment.py
    python tools/project_lines_onto_parchment.py \\
        --canvas-source "terraqueous_globe_reprojected - coast_river_state.png" \\
        --target old_world_state_regions.png --colors red,magenta,cyan
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import derive_crop, reproject, schema, scope  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
SOURCES_DIR = TOOLS_DIR.parent / "sources"
DERIVED_DIR = TOOLS_DIR / "derived"
REGISTRATION_DIR = TOOLS_DIR / "registration"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: The master parchment frame the five crops are cut from, and that any valid
#: ``--target`` must share (used only for the crops' template-match offsets).
MASTER_SOURCE = "tww3_old_world_mod_parchment.png"

#: The five Old World parchment crops (mirrors project_regions.FIVE_CROPS /
#: render_anchor_dot_example.FIVE_PARCHMENT — duplicated here rather than
#: cross-imported, this project's existing convention between sibling QA
#: scripts). Paint order for overlap resolution: later wins.
FIVE_CROPS = (
    "tww3_old_world_mod_parchment_bretonnia.png",
    "tww3_old_world_mod_parchment_empire.png",
    "tww3_old_world_mod_parchment_kislev_norsca.png",
    "tww3_old_world_mod_parchment_dark_lands.png",
    "tww3_old_world_mod_parchment_badlands_nehekhara.png",
)

DEFAULT_CANVAS_SOURCE = "terraqueous_globe_reprojected - coast_river_state.png"
DEFAULT_TARGET = "old_world_state_regions.png"
DEFAULT_OUT = "old_world_state_regions_with_coast_river_state_overlay.png"
DEFAULT_COLORS = "red,magenta,cyan"

_NAMED_COLORS = {
    "red": (255, 0, 0),
    "magenta": (255, 0, 255),
    "cyan": (0, 255, 255),
    "green": (0, 255, 0),
    "yellow": (255, 255, 0),
}

#: Warped-alpha threshold for "this master pixel is inside the crop's cutout".
ALPHA_VALID = 127.5
#: Row block for warp evaluation — bounds the RBF's pairwise-distance temporaries.
ROW_BLOCK = 64
#: Default Euclidean RGB match tolerance to a named colour.
COLOR_TOL_DEFAULT = 24.0


def log(msg: str) -> None:
    print(msg, flush=True)


def load_rgba(name: str) -> np.ndarray:
    """HxWx4 uint8 read directly from ``sources/`` (palette-aware via convert).

    Not manifest-guarded — the accepted QA-render convention (see
    ``project_regions.py`` / ``render_anchor_dot_example.py``): a QA render is
    evidence for a human, not pipeline input.
    """
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.uint8).copy()


def load_rgb(name: str) -> np.ndarray:
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8).copy()


def load_or_derive_rgba(name: str) -> np.ndarray:
    """Like load_rgba, but derives the five parchment crops on demand from
    their dots sheet (board #3570) instead of a pre-baked file — same as
    ``project_regions.load_or_derive_rgba``."""
    seed_path = derive_crop.SEED_DIR / f"{Path(name).stem}.json"
    seed = derive_crop.load_seed(Path(name).stem) if seed_path.is_file() else None
    dots_source = seed.get("dots_source") if seed else None
    if dots_source:
        dots_rgba = load_rgba(dots_source)
        out_rgb, out_alpha = derive_crop.derive_clean_source(
            dots_rgba[..., :3], dots_rgba[..., 3], seed)
        return np.dstack([out_rgb, out_alpha])
    return load_rgba(name)


def crop_offsets(master_gray: np.ndarray,
                 crop_rgba: dict[str, np.ndarray]) -> dict[str, tuple[int, int]]:
    """``{crop_name: (dx, dy)}`` — each crop's exact integer offset in the
    master. Identical to ``project_regions.crop_offsets``."""
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


def parse_colors(spec: str) -> list[tuple[str, tuple[int, int, int]]]:
    out = []
    for tok in spec.split(","):
        tok = tok.strip().lower()
        if not tok:
            continue
        if tok not in _NAMED_COLORS:
            raise SystemExit(f"--colors: unknown colour '{tok}' "
                             f"(known: {', '.join(sorted(_NAMED_COLORS))})")
        out.append((tok, _NAMED_COLORS[tok]))
    if not out:
        raise SystemExit("--colors: named at least one colour")
    return out


def classify_lines(canvas_rgba: np.ndarray, colors: list[tuple[str, tuple[int, int, int]]],
                   tol: float) -> np.ndarray:
    """``int32`` canvas-shaped array: index into ``colors`` for a line pixel, -1 otherwise.

    Gated on the source's own alpha (transparent elsewhere), then nearest-colour
    match within ``tol`` (Euclidean RGB) — ties broken toward the earlier colour
    in ``colors``.
    """
    opaque = canvas_rgba[..., 3] > 0
    rgb = canvas_rgba[..., :3].astype(np.float32)
    idx = np.full(canvas_rgba.shape[:2], -1, dtype=np.int32)
    best = np.full(canvas_rgba.shape[:2], np.inf, dtype=np.float32)
    for i, (_name, rgbc) in enumerate(colors):
        d = np.sqrt(((rgb - np.array(rgbc, dtype=np.float32)) ** 2).sum(axis=2))
        better = opaque & (d <= tol) & (d < best)
        idx[better] = i
        best[better] = d[better]
    for i, (name, _rgbc) in enumerate(colors):
        log(f"  {name:<8} {int((idx == i).sum()):,} canvas px")
    return idx


def master_owner(crop_rgba: dict[str, np.ndarray], offsets: dict[str, tuple[int, int]],
                 mh: int, mw: int) -> np.ndarray:
    """Partition the *master* frame among the crops — ``owner[my, mx]`` = crop index.

    No warp needed (contrast :func:`project_regions.canvas_owner`, which
    partitions the canvas and so must warp each crop's coverage to test it):
    a crop's own alpha mask already sits at a plain integer offset in the
    master frame, so its coverage there is just that mask placed by
    :data:`offsets`. Ownership goes to whichever crop's coverage mask runs
    deepest (Euclidean distance transform) at an overlapping pixel — an
    equidistant, single-valued partition, so every master pixel the crops
    reach at all has exactly one owner.
    """
    owner = np.full((mh, mw), -1, dtype=np.int32)
    best = np.full((mh, mw), -1.0, dtype=np.float32)
    for idx, name in enumerate(FIVE_CROPS):
        dx, dy = offsets[name]
        alpha = crop_rgba[name][..., 3]
        ch, cw = alpha.shape
        y0, y1 = max(0, dy), min(mh, dy + ch)
        x0, x1 = max(0, dx), min(mw, dx + cw)
        if y1 <= y0 or x1 <= x0:
            continue
        mask = np.zeros((mh, mw), dtype=bool)
        mask[y0:y1, x0:x1] = alpha[y0 - dy:y1 - dy, x0 - dx:x1 - dx] > ALPHA_VALID
        if not mask.any():
            continue
        dist = ndimage.distance_transform_edt(mask).astype(np.float32)
        better = mask & (dist > best)
        owner[better] = idx
        best[better] = dist[better]
    return owner


def project(canvas_source: str, target_source: str, out_name: str,
           colors: list[tuple[str, tuple[int, int, int]]], tol: float) -> Path:
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    for name in FIVE_CROPS:
        if name not in regs:
            raise SystemExit(f"{name}: no committed registration record")

    master_rgb = load_rgb(MASTER_SOURCE)
    mh, mw = master_rgb.shape[:2]

    canvas_rgba = load_rgba(canvas_source)
    if canvas_rgba.shape[1] != CANVAS_W or canvas_rgba.shape[0] != CANVAS_H:
        raise SystemExit(f"{canvas_source} is {canvas_rgba.shape[1]}x{canvas_rgba.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} (the canvas frame)")

    target_rgba = load_rgba(target_source)
    if target_rgba.shape[1] != mw or target_rgba.shape[0] != mh:
        raise SystemExit(f"{target_source} is {target_rgba.shape[1]}x{target_rgba.shape[0]}, "
                         f"expected {mw}x{mh} (the master parchment frame, same as {MASTER_SOURCE})")

    log("classifying canvas line art:")
    color_idx = classify_lines(canvas_rgba, colors, tol)
    color_idx_f = color_idx.astype(np.float32)

    crop_rgba = {name: load_or_derive_rgba(name) for name in FIVE_CROPS}
    log("locating the five crops in the master frame:")
    master_gray = master_rgb.astype(np.float32).mean(axis=2)
    offsets = crop_offsets(master_gray, crop_rgba)

    owner = master_owner(crop_rgba, offsets, mh, mw)
    log(f"master owner  {int((owner >= 0).sum()):,} master px assigned a single owning crop")

    out_rgb = target_rgba[..., :3].copy()
    out_alpha = target_rgba[..., 3].copy()
    color_rgb = np.array([c for _n, c in colors], dtype=np.uint8)

    total_painted = 0
    for crop_idx, name in enumerate(FIVE_CROPS):
        reg = regs[name]
        dx, dy = offsets[name]
        crop_alpha = crop_rgba[name][..., 3].astype(np.float32)
        ch, cw = crop_rgba[name].shape[:2]
        inv = reproject.fit_placement_inverse(reg)
        region = name.replace("tww3_old_world_mod_parchment_", "").replace(".png", "")
        log(f"  {region:<20} inverse warp rms {inv.rms_px:.2f}px max {inv.max_px:.2f}px (source px)")

        # Exact axis-aligned cutout: local (0,0)..(cw,ch) tiles master (dx,dy)..(dx+cw,dy+ch).
        # Clip to the master/target frame in case a crop pokes past its edge.
        lx0, ly0 = max(0, -dx), max(0, -dy)
        lx1, ly1 = min(cw, mw - dx), min(ch, mh - dy)
        if lx1 <= lx0 or ly1 <= ly0:
            continue

        painted_here = 0
        gx = (np.arange(lx0, lx1, dtype=np.float64) + 0.5)[None, :]
        for yb in range(ly0, ly1, ROW_BLOCK):
            ye = min(yb + ROW_BLOCK, ly1)
            gy = (np.arange(yb, ye, dtype=np.float64) + 0.5)[:, None]
            gxb = np.broadcast_to(gx, (ye - yb, lx1 - lx0))
            gyb = np.broadcast_to(gy, (ye - yb, lx1 - lx0))
            cx, cy = inv.to_canvas_px(gxb, gyb)
            inside = (cx >= 0) & (cx <= CANVAS_W - 1) & (cy >= 0) & (cy <= CANVAS_H - 1)
            idxf = reproject.resample(color_idx_f, cx, cy, order=0)
            idx = np.rint(idxf).astype(np.int64)
            ca = crop_alpha[yb:ye, lx0:lx1]
            my0, my1 = yb + dy, ye + dy
            mx0, mx1 = lx0 + dx, lx1 + dx
            owns = owner[my0:my1, mx0:mx1] == crop_idx
            valid = inside & (idx >= 0) & (ca > ALPHA_VALID) & owns
            if not valid.any():
                continue
            block = color_rgb[idx.clip(0, len(colors) - 1)]
            view = out_rgb[my0:my1, mx0:mx1]
            view[valid] = block[valid]
            painted_here += int(valid.sum())
        log(f"  {region:<20} painted {painted_here:,} master px")
        total_painted += painted_here

    log(f"total painted {total_painted:,} master px across {len(FIVE_CROPS)} crops "
        f"(exactly one owning crop decides each overlapping pixel)")

    out_rgba = np.dstack([out_rgb, out_alpha])
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DERIVED_DIR / out_name
    Image.fromarray(out_rgba, mode="RGBA").save(out_path)
    log(f"wrote {out_path.relative_to(TOOLS_DIR.parent)}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--canvas-source", default=DEFAULT_CANVAS_SOURCE,
                   help=f"canvas-frame ({CANVAS_W}x{CANVAS_H}) line-art source to project "
                        f"(default {DEFAULT_CANVAS_SOURCE!r})")
    p.add_argument("--target", default=DEFAULT_TARGET,
                   help=f"master-frame RGBA image to project onto (default {DEFAULT_TARGET!r}); "
                        f"must share the master parchment frame ({MASTER_SOURCE})")
    p.add_argument("--out", default=DEFAULT_OUT,
                   help=f"output filename under tools/derived/ (default {DEFAULT_OUT!r})")
    p.add_argument("--colors", default=DEFAULT_COLORS,
                   help=f"comma-separated flat colours in --canvas-source to project, each kept "
                        f"on the output in its own colour (default {DEFAULT_COLORS!r}; known: "
                        f"{', '.join(sorted(_NAMED_COLORS))})")
    p.add_argument("--tol", type=float, default=COLOR_TOL_DEFAULT,
                   help=f"Euclidean RGB match tolerance to a named colour (default {COLOR_TOL_DEFAULT})")
    args = p.parse_args(argv)

    colors = parse_colors(args.colors)
    project(args.canvas_source, args.target, args.out, colors, args.tol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
