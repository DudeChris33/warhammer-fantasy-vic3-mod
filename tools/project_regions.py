#!/usr/bin/env python3
"""QA render: the painted Old World states, draped on the reprojected globe.

Board item #2270 (a look-and-check step, nothing that ships). The user hand-
painted ``sources/old_world_regions.png`` — the tww3 parchment master frame with
ten flat per-macro fills and a magenta (``255,0,255``) state-border network — on
the *flat* parchment. This carries that painting through the **five committed
Old World crop registrations** onto a copy of ``sources/terraqueous_globe_
reprojected.png`` (the canvas frame), so the state layout can be judged by eye
against the real coastline. It writes ``tools/derived/old_world_regions_on_
globe.png`` for an accept/reject verdict; nothing is committed here.

It does **not** re-implement the placement. The projection this preview must be
faithful to already exists: ``generate_state_labels.place_old_world`` carries the
drawing onto the canvas piecewise through the five crops — whole-crop opaque-
masked template offset (``scope.template_offset``) → classify the flat fills into
the ten macros + trace the magenta network into cells → warp both **nearest**
through each committed registration (``cells.warp_cells``), with a runtime frame
guard asserting the drawing is the master's own frame. So this script is a thin
visualiser over the reused ``place_old_world``: it colourises the returned
``macro_raster`` (the ten fill colours) and the ``cell_labels`` borders, and
alpha-blends them over the globe only where a state was placed. Categorical
nearest warp — not the bilinear anchor-dot warp — so hard MS-Paint fills stay
flat and the 1 px border network is not aliased away.

Sources are read directly from ``sources/`` (not through the SHA-256 manifest
guard), the accepted QA-render convention (see ``render_anchor_dot_example.py``):
``old_world_regions.png`` is not manifest-pinned and the state-label pipeline is
mid-edit on this branch (#2207), which is exactly when the guard would refuse. The
offline gate (``sources.py --verify``) still owns integrity for anything that
ships; a QA render is evidence for a human, not pipeline input.

Everything is deterministic for a fixed stack: the placement is the committed
thin-plate fields with nearest resampling, the offsets are an exact-pixel argmax,
and no RNG or wall-clock enters.

Usage::

    python tools/project_regions.py
    python tools/project_regions.py --fills-only --opacity 0.7
    python tools/project_regions.py --coast
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
from worldgen import raster, schema, scope  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402
import generate_state_labels as gsl  # noqa: E402  (import-safe: work is under __main__)

TOOLS_DIR = Path(__file__).resolve().parent
SOURCES_DIR = TOOLS_DIR.parent / "sources"
DERIVED_DIR = TOOLS_DIR / "derived"
REGISTRATION_DIR = TOOLS_DIR / "registration"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: The reprojected globe that IS the canvas frame — the backdrop these states drape over.
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"

#: Province-subdivision borders (edges of the warped cell network) drawn this dark,
#: so the magenta subdivision reads without carrying the raw-magenta halo.
BORDER_RGB = (24, 24, 28)
COAST_RGB = (0, 255, 255)

#: Framing pad (canvas px) around the placed states' bounding box.
CROP_PAD = 64

OUT_DEFAULT = "old_world_regions_on_globe.png"


def log(msg: str) -> None:
    print(msg, flush=True)


def load_rgba(name: str) -> np.ndarray:
    """HxWx4 uint8 read directly from ``sources/`` (see module docstring).

    Mirrors ``worldgen.sources.load_source_image_rgba`` (palette-aware via
    ``convert``), minus the manifest guard: RGB from ``convert("RGB")`` and alpha
    from ``convert("RGBA")`` — so ``P``/``RGBA``/``LA`` all read the same way the
    shipped loader would. A fully-opaque source yields an all-255 alpha.
    """
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing")
    with Image.open(path) as im:
        rgba = np.asarray(im.convert("RGBA"), dtype=np.uint8)
    return rgba.copy()


def load_rgb(name: str) -> np.ndarray:
    """HxWx3 uint8 read directly from ``sources/`` (palette/RGBA flattened to RGB)."""
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8).copy()


def macro_colour_lut() -> np.ndarray:
    """(N_FILL_MACROS+1, 3) uint8 LUT; index 0 (not placed) is unused/black."""
    lut = np.zeros((gsl.N_FILL_MACROS + 1, 3), dtype=np.uint8)
    for mid, _name, rgb in gsl.OLD_WORLD_MACROS:
        lut[mid] = rgb
    return lut


def cell_borders(cell_labels: np.ndarray, placed: np.ndarray) -> np.ndarray:
    """Boolean mask of placed pixels whose stacked cell id differs from a 4-neighbour."""
    lab = cell_labels
    edge = np.zeros(lab.shape, dtype=bool)
    d = lab[1:, :] != lab[:-1, :]
    edge[1:, :] |= d
    edge[:-1, :] |= d
    d = lab[:, 1:] != lab[:, :-1]
    edge[:, 1:] |= d
    edge[:, :-1] |= d
    return edge & placed & (lab > 0)


def out_of_five_report(drawing_rgba: np.ndarray, master_rgb: np.ndarray,
                       crop_rgba: dict[str, np.ndarray]) -> None:
    """Log how much painted drawing area lies outside the five aligned tiles.

    Measured in the drawing's own (source) space: painted pixels (any of the ten
    fills or the magenta network, gated by the drawing's alpha) that fall outside
    the union of the five crop windows are never sampled by any registration, so
    they are left unprojected by construction. Offsets come from the same
    deterministic ``scope.template_offset`` the placement uses.
    """
    fill_to_macro = gsl._fill_to_macro()
    d_rgb = drawing_rgba[..., :3]
    d_alpha = drawing_rgba[..., 3] > 0
    in_scope_all, _ = scope.classify_fills(d_rgb, fill_to_macro, gsl.MARKER_RGB)
    painted = in_scope_all & d_alpha

    master_gray = master_rgb.astype(np.float32).mean(axis=2)
    covered = np.zeros(painted.shape, dtype=bool)
    for name in gsl.OLD_WORLD_CROPS:
        rgba = crop_rgba[name]
        ch, cw = rgba.shape[:2]
        crop_gray = rgba[..., :3].astype(np.float32).mean(axis=2)
        opaque = rgba[..., 3] > 0
        dx, dy = scope.template_offset(master_gray, crop_gray, opaque)
        covered[dy:dy + ch, dx:dx + cw] |= opaque

    total = int(painted.sum())
    unproj = int((painted & ~covered).sum())
    frac = 100.0 * unproj / total if total else 0.0
    log(f"out-of-five: {unproj:,} of {total:,} painted drawing px ({frac:.1f}%) lie outside the "
        f"five aligned tiles - left unprojected (no registration covers them).")


def build(opacity: float, fills_only: bool, coast: bool, out_file: str) -> Path:
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    drawing_rgba = load_rgba(gsl.DRAWING_SOURCE)
    master_rgb = load_rgb(gsl.MASTER_SOURCE)
    crop_rgba = {name: load_rgba(name) for name in gsl.OLD_WORLD_CROPS}

    log("placing the Old World drawing through the five committed registrations:")
    cell_labels, macro_raster, _raw_in_scope, reports = gsl.place_old_world(
        regs, drawing_rgba, master_rgb, crop_rgba)
    log("placement (per crop, highest precedence first):")
    for line in reports:
        log(line)
    region_names = [n.replace("tww3_old_world_mod_parchment_", "").replace(".png", "")
                    for n in gsl.OLD_WORLD_CROPS]
    log(f"projected the five registered regions: {', '.join(region_names)} "
        f"(anything outside these five is warped by no registration)")

    placed = macro_raster > 0
    if not placed.any():
        raise SystemExit("nothing placed — check the drawing / registrations")

    out_of_five_report(drawing_rgba, master_rgb, crop_rgba)

    # Colourise the categorical placement: fills -> the ten macro colours; the cell
    # network -> a thin dark border overlay (unless --fills-only).
    colour = macro_colour_lut()[macro_raster]
    border = None if fills_only else cell_borders(cell_labels, placed)

    globe = load_rgb(GLOBE_SOURCE)
    if globe.shape[0] != CANVAS_H or globe.shape[1] != CANVAS_W:
        raise SystemExit(f"{GLOBE_SOURCE} is {globe.shape[1]}x{globe.shape[0]}, expected "
                         f"{CANVAS_W}x{CANVAS_H} (the canvas frame)")

    # Alpha-blend the states over the globe ONLY where placed, so the globe's own
    # coastline shows through and unpainted canvas stays pure globe.
    out = globe.astype(np.float32)
    op = float(np.clip(opacity, 0.0, 1.0))
    out[placed] = (1.0 - op) * globe[placed] + op * colour[placed]
    if border is not None and border.any():
        b_op = min(1.0, op + 0.35)
        out[border] = (1.0 - b_op) * globe[border] + b_op * np.array(BORDER_RGB, dtype=np.float32)
    out = np.clip(out, 0, 255).astype(np.uint8)

    # Crop to the placement bounding box + a pad for legible framing.
    ys, xs = np.nonzero(placed)
    y0 = max(0, int(ys.min()) - CROP_PAD)
    y1 = min(CANVAS_H, int(ys.max()) + 1 + CROP_PAD)
    x0 = max(0, int(xs.min()) - CROP_PAD)
    x1 = min(CANVAS_W, int(xs.max()) + 1 + CROP_PAD)
    crop = out[y0:y1, x0:x1].copy()
    log(f"crop box      canvas [{x0}, {y0}, {x1}, {y1}]  ({x1 - x0}x{y1 - y0})")

    if coast:
        if not MASK_PATH.is_file():
            raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first")
        land = raster.read_mask_png(MASK_PATH)
        sub = land[y0:y1, x0:x1]
        er = ndimage.binary_erosion(sub, structure=np.ones((3, 3), dtype=bool), border_value=True)
        edge = ndimage.binary_dilation(sub & ~er, structure=np.ones((3, 3), dtype=bool))
        crop[edge] = COAST_RGB

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DERIVED_DIR / out_file
    Image.fromarray(crop, mode="RGB").save(out_path)
    log(f"wrote {out_path.relative_to(TOOLS_DIR.parent)}  "
        f"(opacity {op}, {'fills only' if fills_only else 'with borders'}"
        f"{', coast' if coast else ''})")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--opacity", type=float, default=0.55,
                   help="state-fill blend strength over the globe (0..1, default 0.55)")
    p.add_argument("--fills-only", action="store_true",
                   help="drop the province-border overlay (fills only)")
    p.add_argument("--coast", action="store_true",
                   help="overlay the committed land/sea mask coastline in cyan")
    p.add_argument("--out", default=OUT_DEFAULT,
                   help=f"output filename under tools/derived/ (default {OUT_DEFAULT})")
    args = p.parse_args(argv)

    build(args.opacity, args.fills_only, args.coast, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
