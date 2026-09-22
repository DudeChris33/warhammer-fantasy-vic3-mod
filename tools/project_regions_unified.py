#!/usr/bin/env python3
"""QA render: the hand-painted Old World state map, draped on the globe through
the single UNIFIED whole-master registration instead of the five per-region crops.

The single-warp counterpart of ``tools/project_regions.py``. That script drapes
``sources/old_world_state_regions.png`` (the tww3 parchment master frame, 4096²,
RGBA, a per-state fill plus a magenta boundary network) onto the canvas through
the **five committed per-region crop registrations**, which means partitioning
canvas ownership across their ~15%-overlapping footprints (``canvas_owner``) so a
line in an overlap band is not drawn twice, once per crop, a pixel or two apart.

``tools/registration/seeds/tww3_old_world_mod_parchment_full.json`` (fit via
``tools/fit_registration.py --seed tww3_old_world_mod_parchment_full``) places
the SAME master frame as ONE piece through a single thin-plate warp, so none of
that ownership machinery is needed here: every canvas pixel this warp reaches has
exactly one source position, full stop. This script is the direct, much simpler
analogue of ``project_regions.py``'s ``place_painting`` with the five-crop loop
and ``canvas_owner`` partition removed.

**Nearest sampling only** — unlike ``project_regions.py``'s nearest/bilinear pair.
Compared side by side (2026-09-09) bilinear's antialiasing just blurred the hard
per-state fills and the 1px magenta border network for no benefit anyone wanted,
so it was dropped rather than kept as a second, always-worse option.

Sources are read directly from ``sources/`` (not through the SHA-256 manifest
guard) — the accepted QA-render convention (see ``render_anchor_dot_example.py``):
a QA render is evidence for a human, not pipeline input.

**Colour filter.** ``--colors`` keeps only the named painted layers from the
finished drape — every pixel further than ``--color-tol`` (Euclidean, default 12)
from every listed colour reverts to the globe. Names come from ``NAMED_COLORS``
(``magenta`` = the state-border network, ``orange`` = the impassable-terrain
fill, ``cyan``) or a ``#rrggbb`` literal, comma-separated: e.g.
``--colors magenta,orange`` shows the borders and the impassable fill with the
globe's terrain everywhere else (see :func:`extract_colors`).

**Hull buffer.** ``--hull-buffer-px`` softens only the *outer* edge of the
piecewise-affine warp's strict hull cutoff (see ``reproject._bary_interp``): a
query point past every triangle, but within the given distance of the nearest
hull vertex, is placed by extrapolating that vertex's own triangle rather than
dropped. It is a QA-render convenience for judging content just past today's
dot coverage — not a real correspondence, and never stored in the registration
record itself; the principled fix for a systematic gap is still more dots
(``tools/fit_registration.py --seed tww3_old_world_mod_parchment_full``).
Defaults to 50px (``HULL_BUFFER_PX_DEFAULT`` — user-accepted by eye 2026-09-12,
100px read as too much); pass 0 for the strict, no-extrapolation behaviour.

The painting draped (``PAINT_SOURCE``) is ``old_world_state_regions.png`` — the
magenta boundary network, authored in the parchment master's frame but exported
at 2048² (half the 4096² master). The warp coords are scaled onto that grid via
the record's ``master_shape`` (written by ``fit_registration``), so no ``--paint``
override and no re-export to 4096² is needed: after
``tools/reseed_registration_dots.py --seed tww3_old_world_mod_parchment_full --fit``
folds new dots and re-derives the warp, ``project_regions_unified.py --crop`` IS
the projection.

Usage::

    python tools/project_regions_unified.py --crop          # the projection (defaults are current)
    python tools/project_regions_unified.py                 # full uncropped canvas
    python tools/project_regions_unified.py --colors magenta,orange --crop
    python tools/project_regions_unified.py --hull-buffer-px 100 --crop
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import reproject, schema  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
SOURCES_DIR = TOOLS_DIR.parent / "sources"
DERIVED_DIR = TOOLS_DIR / "derived"
REGISTRATION_DIR = TOOLS_DIR / "registration"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: The full-master registration this script projects through.
FULL_SOURCE = "tww3_old_world_mod_parchment_full.png"
#: The state-region painting to drape: the magenta boundary network, exported at
#: 2048² — HALF the registration's 4096² master frame. It is a borders-only
#: source (transparent except the lines, so its alpha coverage reads low — that
#: is complete, not sparse), authored in the SAME parchment frame the warp fits.
#: ``place_painting`` scales the master-frame warp coords onto this grid via the
#: record's ``master_shape``, so the half-res export drapes at full extent rather
#: than cropped to a quadrant. Update this filename here (not with ``--paint``)
#: whenever the current export changes, so a plain run is always the projection.
PAINT_SOURCE = "old_world_state_regions.png"
#: The reprojected globe that IS the canvas frame — the backdrop the painting drapes over.
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
#: The destination coastline: a transparent overlay in the canvas frame whose
#: only opaque pixels are the hand-drawn cyan coast line. Overlaid on the drape
#: by default (opacity-detected — see overlay_coast; --no-coast skips it).
COAST_SOURCE = "terraqueous_globe_reprojected - coasts.png"

MAGENTA_RGB = (255, 0, 255)
COAST_RGB = (0, 255, 255)

#: Painted layers a ``--colors`` filter can keep, by name (case-insensitive).
#: magenta = the state-border network, orange = the impassable-terrain fill —
#: the two overlays these paintings carry. A ``#rrggbb`` literal is also accepted.
NAMED_COLORS = {
    "magenta": (255, 0, 255),
    "orange": (255, 127, 0),
    "cyan": (0, 255, 255),
}

#: Warped-alpha threshold for "this pixel shows content" (matches project_regions.py).
ALPHA_VALID = 127.5
#: Row block for warp evaluation — bounds the RBF's pairwise-distance temporaries.
ROW_BLOCK = 64
#: Framing pad (canvas px) around the placed states' bounding box.
CROP_PAD = 64
#: Default Euclidean RGB tolerance for the --colors match.
COLOR_TOL_DEFAULT = 12.0
#: Default --hull-buffer-px — accepted by eye (2026-09-12) against the then-current
#: dot coverage; 100px read as too much, 50px looked right. Revisit if the dot
#: coverage changes enough to change that judgment.
HULL_BUFFER_PX_DEFAULT = 50.0

OUT_PREFIX_DEFAULT = "old_world_state_regions_on_globe_unified"


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_colors(spec: str) -> list[tuple[int, int, int]]:
    """Parse a ``--colors`` spec (``"magenta,orange"`` / ``"#ff00ff,orange"``) to RGB.

    Each comma-separated token is a name in :data:`NAMED_COLORS` or a ``#rrggbb``
    (``rrggbb``) literal. Unknown tokens and an empty list are hard errors — a
    silent drop would render the wrong thing without saying so.
    """
    out: list[tuple[int, int, int]] = []
    for tok in spec.split(","):
        t = tok.strip().lower()
        if not t:
            continue
        if t in NAMED_COLORS:
            out.append(NAMED_COLORS[t])
        elif re.fullmatch(r"#?[0-9a-f]{6}", t):
            h = t.lstrip("#")
            out.append((int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))
        else:
            raise SystemExit(
                f"--colors: unknown colour {tok!r}; use one of "
                f"{', '.join(NAMED_COLORS)} or a #rrggbb literal")
    if not out:
        raise SystemExit("--colors: no colours given")
    return out


def load_rgb(name: str) -> np.ndarray:
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8).copy()


def load_rgba(name: str) -> np.ndarray:
    path = sources_mod.resolve_source_path(name, SOURCES_DIR)
    if not path.is_file():
        raise SystemExit(f"sources/{name} is missing")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.uint8).copy()


def footprint_box(reg: schema.SourceRegistration, pad: float = 0.0) -> tuple[int, int, int, int]:
    """The registration's canvas footprint, clamped to the frame (canvas px).

    ``pad`` grows the box by that many px on every side before clamping — needed
    when ``--hull-buffer-px`` extrapolates past the registration's own footprint,
    or the eval box itself would clip the extrapolated margin before the warp
    ever gets a chance to place it.
    """
    x0, y0, x1, y1 = reg.footprint
    return (max(0, int(np.floor(x0 - pad))), max(0, int(np.floor(y0 - pad))),
            min(CANVAS_W, int(np.ceil(x1 + pad))), min(CANVAS_H, int(np.ceil(y1 + pad))))


def place_painting(fit, box: tuple[int, int, int, int], paint_rgba: np.ndarray,
                   globe_rgb: np.ndarray,
                   master_shape: tuple[int, int] | None = None
                   ) -> tuple[np.ndarray, np.ndarray]:
    """Drape the painting onto a copy of the globe through the single full-master
    warp, sampled nearest (hard per-state fills stay flat, the 1px magenta
    border network is not aliased away). Returns ``(canvas_rgb, placed)``.

    The warp is only evaluated inside ``box`` (the registration's own
    footprint) — the whole point of a single-warp registration is a compact
    placement, not a canvas-spanning one, so walking the full 8192x3616 frame
    would burn >90% of the work on RBF evaluations that can never land inside
    the painting anyway.

    ``fit.to_source_px`` returns px in the registration's MASTER frame. When the
    painting is authored at a different resolution of that same frame (e.g. a
    2048² export of a 4096² master), ``master_shape`` (``(h, w)``, from the
    record) scales the master-frame coords onto the painting's own grid before
    sampling — so a half-res or double-res painting drapes identically, not
    cropped to a quadrant at the wrong scale. ``None`` keeps the old
    painting==master assumption.
    """
    canvas_rgb = globe_rgb.copy()
    placed = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)

    ph, pw = paint_rgba.shape[:2]
    if master_shape is not None:
        mh, mw = master_shape
        sx, sy = pw / float(mw), ph / float(mh)
    else:
        sx = sy = 1.0
    paint_planes = [paint_rgba[..., c].astype(np.float32) for c in range(3)]
    paint_alpha = paint_rgba[..., 3].astype(np.float32)

    bx0, by0, bx1, by1 = box
    gx = (np.arange(bx0, bx1, dtype=np.float64) + 0.5)[None, :]
    for yb in range(by0, by1, ROW_BLOCK):
        ye = min(yb + ROW_BLOCK, by1)
        gy = (np.arange(yb, ye, dtype=np.float64) + 0.5)[:, None]
        gxb = np.broadcast_to(gx, (ye - yb, bx1 - bx0))
        gyb = np.broadcast_to(gy, (ye - yb, bx1 - bx0))
        mx, my = fit.to_source_px(gxb, gyb)
        px, py = mx * sx, my * sy  # master-frame -> painting-frame px

        in_master = (px >= 0) & (px <= pw - 1) & (py >= 0) & (py <= ph - 1)
        pa = reproject.resample(paint_alpha, px, py, order=0)
        valid = in_master & (pa > ALPHA_VALID)
        if not valid.any():
            continue

        block = np.empty((ye - yb, bx1 - bx0, 3), dtype=np.uint8)
        for c in range(3):
            block[..., c] = np.clip(
                reproject.resample(paint_planes[c], px, py, order=0), 0, 255
            ).astype(np.uint8)
        view_rgb = canvas_rgb[yb:ye, bx0:bx1]
        view_placed = placed[yb:ye, bx0:bx1]
        view_rgb[valid] = block[valid]
        view_placed |= valid

    return canvas_rgb, placed


def extract_colors(canvas_rgb: np.ndarray, globe_rgb: np.ndarray, placed: np.ndarray,
                   colors: list[tuple[int, int, int]], tol: float) -> np.ndarray:
    """Keep only the painted pixels near one of ``colors``; revert the rest to the globe.

    Generalises the former magenta-only "borders" extraction to any set of
    painted layers — e.g. ``magenta`` (the state-border network) plus ``orange``
    (the impassable-terrain fill). Runs *after* :func:`place_painting` has draped
    the whole opaque painting (fills and lines both): for each listed colour a
    smooth ``1 - distance/tol`` falloff is computed over the already-resampled
    composite, and every pixel is blended from the globe toward the NEAREST
    listed colour by that falloff. A pixel outside every colour's ``tol`` keeps
    the globe, so only the chosen layers show and the globe's own terrain shows
    through everywhere else.

    ``placed`` restricts the test to pixels :func:`place_painting` actually drew;
    the extraction only decides how much of that already-placed colour to keep,
    not where to resample from again.
    """
    gb = globe_rgb.astype(np.float32)
    canvas = canvas_rgb.astype(np.float32)
    out = gb.copy()
    best = np.zeros(placed.shape, dtype=np.float32)
    for col in colors:
        c = np.array(col, dtype=np.float32)
        dist = np.sqrt(((canvas - c) ** 2).sum(axis=2))
        alpha = np.clip(1.0 - dist / tol, 0.0, 1.0) * placed
        take = alpha > best
        a = alpha[take][:, None]
        out[take] = gb[take] * (1.0 - a) + c * a
        best[take] = alpha[take]
    return np.clip(out, 0, 255).astype(np.uint8)


def overlay_coast(canvas_rgb: np.ndarray, coasts_rgba: np.ndarray) -> int:
    """Draw the coasts PNG's line onto ``canvas_rgb`` in cyan (in place).

    The coast source is a transparent overlay whose only opaque pixels ARE the
    hand-drawn coastline (already cyan). Detect the line by opacity, not by an
    RGB match — the earlier magenta match found nothing, since the line is cyan.
    """
    line = coasts_rgba[..., 3] > 127
    canvas_rgb[line] = COAST_RGB
    return int(line.sum())


def placement_box(placed: np.ndarray, pad: int) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(placed)
    if not ys.size:
        raise SystemExit("nothing placed — check the painting / registration")
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(CANVAS_W, int(xs.max()) + 1 + pad)
    y1 = min(CANVAS_H, int(ys.max()) + 1 + pad)
    return (x0, y0, x1, y1)


def build(pad: int, out_prefix: str,
          paint_source: str = PAINT_SOURCE, overlay_coasts: bool = True,
          full_frame: bool = True, globe_source: str = GLOBE_SOURCE,
          colors: list[tuple[int, int, int]] | None = None,
          color_tol: float = COLOR_TOL_DEFAULT,
          hull_buffer_px: float = HULL_BUFFER_PX_DEFAULT) -> Path:
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    if FULL_SOURCE not in regs:
        raise SystemExit(f"{FULL_SOURCE}: no committed registration record — "
                         f"run tools/fit_registration.py --seed tww3_old_world_mod_parchment_full")
    reg = regs[FULL_SOURCE]

    paint_rgba = load_rgba(paint_source)
    globe_rgb = load_rgb(globe_source)
    coasts_rgba = load_rgba(COAST_SOURCE) if overlay_coasts else None

    if globe_rgb.shape[1] != CANVAS_W or globe_rgb.shape[0] != CANVAS_H:
        raise SystemExit(f"{globe_source} is {globe_rgb.shape[1]}x{globe_rgb.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} (the canvas frame)")
    if coasts_rgba is not None and coasts_rgba.shape[:2] != globe_rgb.shape[:2]:
        raise SystemExit(f"{COAST_SOURCE} is {coasts_rgba.shape[1]}x{coasts_rgba.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} to match the globe")

    painted_frac = 100.0 * (paint_rgba[..., 3] > 0).mean()
    log(f"painting {paint_rgba.shape[1]}x{paint_rgba.shape[0]}  "
        f"alpha-covered {painted_frac:.1f}%")

    fit = reproject.fit_placement(reg, regs, buffer_px=hull_buffer_px)
    eval_box = footprint_box(reg, pad=hull_buffer_px)
    log(f"registration  {FULL_SOURCE} ({reg.projection})")
    if hull_buffer_px > 0:
        log(f"hull buffer   {hull_buffer_px:.0f}px past the outer hull edge only "
            f"(extrapolated, not a real correspondence — see reproject._bary_interp)")
    log(f"eval box      canvas {list(eval_box)} (the registration's own footprint"
        f"{f' + {hull_buffer_px:.0f}px buffer' if hull_buffer_px > 0 else ''} — "
        f"the warp is never evaluated outside it)")

    canvas_rgb, placed = place_painting(fit, eval_box, paint_rgba, globe_rgb,
                                        master_shape=reg.master_shape)
    box = (0, 0, CANVAS_W, CANVAS_H) if full_frame else placement_box(placed, pad)
    x0, y0, x1, y1 = box
    log(f"placed        {100.0 * placed.mean():.3f}% of the frame "
        f"({int(placed.sum()):,} px)")
    label = "full frame" if full_frame else "crop box"
    log(f"{label:<13} canvas [{x0}, {y0}, {x1}, {y1}]  ({x1 - x0}x{y1 - y0})")

    if colors:
        canvas_rgb = extract_colors(canvas_rgb, globe_rgb, placed, colors, color_tol)
        kept = int((canvas_rgb != globe_rgb).any(axis=2).sum())
        swatches = ", ".join(str(tuple(c)) for c in colors)
        log(f"colors        kept {kept:,} px within {color_tol} of [{swatches}] "
            f"(of {int(placed.sum()):,} placed)")
    n_coast = overlay_coast(canvas_rgb, coasts_rgba) if coasts_rgba is not None else 0

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    crop = canvas_rgb[y0:y1, x0:x1].copy()
    out_path = DERIVED_DIR / f"{out_prefix}.png"
    Image.fromarray(crop, mode="RGB").save(out_path)
    log(f"wrote {out_path.relative_to(TOOLS_DIR.parent)}  (coast {n_coast:,} px)")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pad", type=int, default=CROP_PAD,
                   help=f"framing pad in canvas px around the placed states, with --crop "
                        f"(default {CROP_PAD}; ignored on the default full frame)")
    p.add_argument("--out-prefix", default=OUT_PREFIX_DEFAULT,
                   help=f"output filename prefix under tools/derived/ (default {OUT_PREFIX_DEFAULT})")
    p.add_argument("--paint", default=PAINT_SOURCE,
                   help=f"the painting (RGBA, any resolution of the master frame — "
                        f"scaled via the record's master_shape) to drape (default {PAINT_SOURCE})")
    p.add_argument("--no-coast", action="store_true",
                   help="skip the cyan coastline reference overlay (drape the painting alone)")
    p.add_argument("--crop", action="store_true",
                   help="crop to the placed states' bounding box (+--pad) instead of the "
                        "default full reprojected-globe canvas (8192x3616)")
    p.add_argument("--globe", default=GLOBE_SOURCE,
                   help=f"the backdrop to drape the painting over (default {GLOBE_SOURCE}); "
                        f"must share the canvas frame ({CANVAS_W}x{CANVAS_H})")
    p.add_argument("--colors", default=None,
                   help="keep only these painted layers from the finished drape (comma-"
                        "separated), reverting everything else to the globe's own terrain — "
                        f"the painting is still draped in full first. Names: "
                        f"{', '.join(NAMED_COLORS)}, or a #rrggbb literal. "
                        "e.g. --colors magenta,orange keeps the state borders + the "
                        "impassable fill; see extract_colors")
    p.add_argument("--color-tol", type=float, default=COLOR_TOL_DEFAULT,
                   help=f"--colors' Euclidean RGB match tolerance to each named colour "
                        f"(default {COLOR_TOL_DEFAULT})")
    p.add_argument("--hull-buffer-px", type=float, default=HULL_BUFFER_PX_DEFAULT,
                   help="extrapolate this many canvas px past the OUTER hull edge only "
                        "(nearest hull vertex's own triangle, unclamped) instead of the "
                        "strict hull cutoff; a QA render convenience, not a real "
                        f"correspondence — accuracy is unverified past the hull and "
                        f"degrades with distance from it (default {HULL_BUFFER_PX_DEFAULT:.0f}, "
                        f"pass 0 for the strict, no-extrapolation behaviour)")
    args = p.parse_args(argv)

    colors = parse_colors(args.colors) if args.colors else None
    out_prefix = args.out_prefix
    if colors and out_prefix == OUT_PREFIX_DEFAULT:
        tag = re.sub(r"[^0-9a-z]+", "_", args.colors.strip().lower()).strip("_")
        out_prefix = f"{out_prefix}_{tag}"
    build(args.pad, out_prefix,
          paint_source=args.paint, overlay_coasts=not args.no_coast,
          full_frame=not args.crop, globe_source=args.globe,
          colors=colors, color_tol=args.color_tol,
          hull_buffer_px=args.hull_buffer_px)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
