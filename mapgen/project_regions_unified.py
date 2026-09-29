#!/usr/bin/env python3
"""QA render: the hand-painted Old World state map, draped on the globe through
the single UNIFIED whole-master registration instead of the five per-region crops.

The single-warp counterpart of ``mapgen/project_regions.py``. That script drapes
``sources/old_world_state_regions.png`` (the tww3 parchment master frame, 4096²,
RGBA, a per-state fill plus a magenta boundary network) onto the canvas through
the **five committed per-region crop registrations**, which means partitioning
canvas ownership across their ~15%-overlapping footprints (``canvas_owner``) so a
line in an overlap band is not drawn twice, once per crop, a pixel or two apart.

``mapgen/registration/seeds/tww3_old_world_mod_parchment_full.json`` (fit via
``mapgen/fit_registration.py --seed tww3_old_world_mod_parchment_full``) places
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

**Colour-selected layers.** ``--colors`` (required) picks which layers to pull
out of ``PAINT_ORA`` and composite before draping — it is the ONLY way this
script decides what to draw, there is no "everything" default. Each
comma-separated token is a name in ``NAMED_LAYERS`` (``magenta`` -> the
``state_regions`` layer, the state-border network; ``orange`` -> the
``impassable`` layer, the impassable-terrain fill; ``light-blue`` -> the
``cities`` layer, city point markers) or a ``#rrggbb`` literal matching one of
those layers' own flat-fill colour exactly, e.g. ``--colors magenta,orange``
composites the state borders + the impassable fill (see :func:`parse_layers`,
:func:`load_paint_layers`). When more than one is selected they always stack
in :data:`LAYER_Z_ORDER` (orange at the bottom, magenta over it, light-blue on
top) regardless of the order given on the command line — a city marker must
never be hidden under a border or fill. Every layer in ``PAINT_ORA`` is a
hard-edged, binary-alpha flat fill in exactly one colour (confirmed by
inspection), so selecting layers upstream is exact — no post-drape
colour-distance filtering is needed the way a single flat painting would have
required.

**Hull buffer.** ``--hull-buffer-px`` softens only the *outer* edge of the
piecewise-affine warp's strict hull cutoff (see ``reproject._bary_interp``): a
query point past every triangle, but within the given distance of the nearest
hull vertex, is placed by extrapolating that vertex's own triangle rather than
dropped. It is a QA-render convenience for judging content just past today's
dot coverage — not a real correspondence, and never stored in the registration
record itself; the principled fix for a systematic gap is still more dots
(``mapgen/fit_registration.py --seed tww3_old_world_mod_parchment_full``).
Defaults to 50px (``HULL_BUFFER_PX_DEFAULT`` — user-accepted by eye 2026-09-12,
100px read as too much); pass 0 for the strict, no-extrapolation behaviour.

The painting draped comes from ``PAINT_ORA`` (``sources/oldworld-first/
old_world_map - full.ora``) — the Old World parchment-frame painting (state
borders, impassable terrain, cities, the base parchment), 2048² (half the
4096² master). The warp coords are scaled onto that grid via the record's
``master_shape`` (written by ``fit_registration``), so no re-export to 4096²
is needed: after
``mapgen/reseed_registration_dots.py --seed tww3_old_world_mod_parchment_full --fit``
folds new dots and re-derives the warp, ``project_regions_unified.py --colors
... --crop`` IS the projection. (Supersedes the flat ``old_world_state_regions.png``
export retired by board #5403 — that single-file painting drifted out of sync
once its content was split into named layers here.)

Usage::

    python mapgen/project_regions_unified.py --colors magenta,orange --crop
    python mapgen/project_regions_unified.py --colors magenta                 # full uncropped canvas
    python mapgen/project_regions_unified.py --colors orange,magenta,light-blue --crop  # stacks light-blue on top regardless of arg order
    python mapgen/project_regions_unified.py --colors magenta,orange --hull-buffer-px 100 --crop
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
#: The Old World parchment-frame painting this script pulls layers from — an
#: .ora authored at 2048² (HALF the registration's 4096² master frame).
#: ``place_painting`` scales the master-frame warp coords onto this grid via the
#: record's ``master_shape``, so the half-res export drapes at full extent
#: rather than cropped to a quadrant. Resolved under ``sources/`` (checked
#: against ``worldgen.sources.SOURCE_SUBDIRS`` — currently
#: ``sources/oldworld-first/``), never through the SHA-256 manifest guard (see
#: the module docstring's "Sources are read directly" note).
PAINT_ORA = "old_world_map - full.ora"
#: The reprojected globe that IS the canvas frame — the backdrop the painting drapes over.
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"
#: The destination coastline: a transparent overlay in the canvas frame whose
#: only opaque pixels are the hand-drawn cyan coast line. Overlaid on the drape
#: by default (opacity-detected — see overlay_coast; --no-coast skips it).
COAST_SOURCE = sources_mod.source_ref("coast_trace")

COAST_RGB = (0, 255, 255)

#: ``--colors`` token -> (the layer's name inside PAINT_ORA, its own flat-fill
#: colour). Confirmed by inspection of ``old_world_map - full.ora``'s
#: ``stack.xml``: each of these layers is a flat, hard-edged (binary alpha,
#: 0 or 255 — no antialiasing) fill in exactly this RGB, so the colour is also
#: a reliable key for a ``#rrggbb`` literal (see :func:`parse_layers`). "cyan"
#: is deliberately absent — no layer in this .ora is cyan; that RGB is
#: ``COAST_RGB``, a wholly different overlay applied separately by
#: :func:`overlay_coast`.
NAMED_LAYERS: dict[str, tuple[str, tuple[int, int, int]]] = {
    "magenta": ("state_regions", (255, 0, 255)),
    "orange": ("impassable", (255, 127, 0)),
    "light-blue": ("cities", (127, 127, 255)),
}
#: Reverse of NAMED_LAYERS, for resolving a ``#rrggbb`` literal to a layer.
_RGB_TO_LAYER: dict[tuple[int, int, int], tuple[str, str]] = {
    rgb: (name, layer) for name, (layer, rgb) in NAMED_LAYERS.items()
}
#: Fixed compositing order (bottom -> top) for whichever layers a --colors
#: spec selects, regardless of the order the tokens were given in: orange
#: (impassable) sits at the bottom, magenta (state_regions) over it, and
#: light-blue (cities) on top of both — cities are point markers that should
#: never be hidden by an underlying fill or border line. See :func:`parse_layers`.
LAYER_Z_ORDER: tuple[str, ...] = ("impassable", "state_regions", "cities")

#: Warped-alpha threshold for "this pixel shows content" (matches project_regions.py).
ALPHA_VALID = 127.5
#: Row block for warp evaluation — bounds the RBF's pairwise-distance temporaries.
ROW_BLOCK = 64
#: Framing pad (canvas px) around the placed states' bounding box.
CROP_PAD = 64
#: Default --hull-buffer-px — accepted by eye (2026-09-12) against the then-current
#: dot coverage; 100px read as too much, 50px looked right. Revisit if the dot
#: coverage changes enough to change that judgment.
HULL_BUFFER_PX_DEFAULT = 50.0

OUT_PREFIX_DEFAULT = "old_world_state_regions_on_globe_unified"


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_layers(spec: str) -> list[tuple[str, str, tuple[int, int, int]]]:
    """Parse a ``--colors`` spec (``"magenta,orange"`` / ``"#ff00ff,orange"``)
    into the ``(name, ora layer, rgb)`` triples to pull from :data:`PAINT_ORA`.

    Each comma-separated token is a name in :data:`NAMED_LAYERS` or a
    ``#rrggbb`` literal matching one of those layers' own flat-fill colour
    exactly. Unknown tokens, a hex literal matching no layer, and an empty
    list are hard errors — a silent drop would render the wrong (or no) layer
    without saying so. A repeated layer (by name or by an equivalent hex) is
    deduped. The RETURNED order is always :data:`LAYER_Z_ORDER` (bottom to
    top), regardless of the order the tokens were given in — the compositing
    order must be fixed, not input-dependent, or the same spec in a different
    token order would silently draw a different picture.
    """
    picked: dict[str, tuple[str, tuple[int, int, int]]] = {}
    for tok in spec.split(","):
        t = tok.strip().lower()
        if not t:
            continue
        if t in NAMED_LAYERS:
            name = t
            layer, rgb = NAMED_LAYERS[t]
        elif re.fullmatch(r"#?[0-9a-f]{6}", t):
            h = t.lstrip("#")
            rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            if rgb not in _RGB_TO_LAYER:
                raise SystemExit(
                    f"--colors: {tok!r} matches no layer's flat-fill colour in "
                    f"{PAINT_ORA!r} — known: "
                    f"{', '.join(f'{n}={rgb2}' for n, (_, rgb2) in NAMED_LAYERS.items())}")
            name, layer = _RGB_TO_LAYER[rgb]
        else:
            raise SystemExit(
                f"--colors: unknown colour {tok!r}; use one of "
                f"{', '.join(NAMED_LAYERS)} or a #rrggbb literal")
        picked.setdefault(layer, (name, rgb))
    if not picked:
        raise SystemExit("--colors: no colours given")
    return [(picked[layer][0], layer, picked[layer][1])
            for layer in LAYER_Z_ORDER if layer in picked]


def composite_layers_over(layers: list[np.ndarray]) -> np.ndarray:
    """Alpha-composite ``layers`` (each an ``(H, W, 4)`` uint8 RGBA array,
    same shape) "over" in list order — first is bottommost — into one RGBA
    array. Pure and I/O-free so it self-checks on synthetic arrays; the real
    per-layer reads live in :func:`load_paint_layers`.
    """
    if not layers:
        raise ValueError("composite_layers_over: no layers given")
    out = layers[0].astype(np.float32).copy()
    for top in layers[1:]:
        t = top.astype(np.float32)
        a = t[..., 3:4] / 255.0
        out[..., :3] = t[..., :3] * a + out[..., :3] * (1.0 - a)
        out[..., 3:4] = t[..., 3:4] + out[..., 3:4] * (1.0 - a[..., 0:1])
    return np.clip(out, 0, 255).astype(np.uint8)


def load_paint_layers(ora_ref: str, layer_names: list[str]) -> np.ndarray:
    """Read + composite ``layer_names`` out of the .ora at ``ora_ref`` (resolved
    under ``sources/``) into one ``(H, W, 4)`` RGBA array, in the given order.
    """
    layers = []
    for name in layer_names:
        rgba = sources_mod.read_source_rgba(f"{ora_ref}#{name}", SOURCES_DIR, allow_empty=True)
        if rgba is None:
            raise SystemExit(f"sources/{ora_ref} is missing")
        layers.append(rgba)
    return composite_layers_over(layers)


def load_rgb(name: str) -> np.ndarray:
    arr = sources_mod.read_source_rgba(name, SOURCES_DIR, allow_empty=True)
    if arr is None:
        raise SystemExit(f"sources/{name} is missing")
    return arr[..., :3].copy()


def load_rgba(name: str) -> np.ndarray:
    arr = sources_mod.read_source_rgba(name, SOURCES_DIR, allow_empty=True)
    if arr is None:
        raise SystemExit(f"sources/{name} is missing")
    return arr


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


def build(pad: int, out_prefix: str, layers: list[tuple[str, str, tuple[int, int, int]]],
          ora_source: str = PAINT_ORA, overlay_coasts: bool = True,
          full_frame: bool = True, globe_source: str = GLOBE_SOURCE,
          hull_buffer_px: float = HULL_BUFFER_PX_DEFAULT) -> Path:
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    if FULL_SOURCE not in regs:
        raise SystemExit(f"{FULL_SOURCE}: no committed registration record — "
                         f"run mapgen/fit_registration.py --seed tww3_old_world_mod_parchment_full")
    reg = regs[FULL_SOURCE]

    paint_rgba = load_paint_layers(ora_source, [layer for _, layer, _ in layers])
    globe_rgb = load_rgb(globe_source)
    coasts_rgba = load_rgba(COAST_SOURCE) if overlay_coasts else None

    if globe_rgb.shape[1] != CANVAS_W or globe_rgb.shape[0] != CANVAS_H:
        raise SystemExit(f"{globe_source} is {globe_rgb.shape[1]}x{globe_rgb.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} (the canvas frame)")
    if coasts_rgba is not None and coasts_rgba.shape[:2] != globe_rgb.shape[:2]:
        raise SystemExit(f"{COAST_SOURCE} is {coasts_rgba.shape[1]}x{coasts_rgba.shape[0]}, "
                         f"expected {CANVAS_W}x{CANVAS_H} to match the globe")

    painted_frac = 100.0 * (paint_rgba[..., 3] > 0).mean()
    layer_names = ", ".join(f"{name}={layer}" for name, layer, _ in layers)
    log(f"layers        {layer_names} (from {ora_source})")
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
                   help=f"output filename prefix under mapgen/derived/ (default {OUT_PREFIX_DEFAULT})")
    p.add_argument("--source", default=PAINT_ORA,
                   help=f"the .ora (RGBA layers, any resolution of the master frame — "
                        f"scaled via the record's master_shape) to pull --colors' layers "
                        f"from (default {PAINT_ORA!r})")
    p.add_argument("--no-coast", action="store_true",
                   help="skip the cyan coastline reference overlay (drape the painting alone)")
    p.add_argument("--crop", action="store_true",
                   help="crop to the placed states' bounding box (+--pad) instead of the "
                        "default full reprojected-globe canvas (8192x3616)")
    p.add_argument("--globe", default=GLOBE_SOURCE,
                   help=f"the backdrop to drape the painting over (default {GLOBE_SOURCE}); "
                        f"must share the canvas frame ({CANVAS_W}x{CANVAS_H})")
    p.add_argument("--colors", required=True,
                   help="which layers to pull from --source and composite before draping "
                        "(comma-separated) — the only thing that decides what gets drawn. "
                        f"Names: {', '.join(NAMED_LAYERS)}, or a #rrggbb literal matching one "
                        "of those layers' own flat-fill colour. e.g. --colors magenta,orange "
                        "pulls the state-border network + the impassable fill. Multiple "
                        f"layers always stack in LAYER_Z_ORDER {LAYER_Z_ORDER} (bottom to "
                        "top) regardless of the order given here; see parse_layers")
    p.add_argument("--hull-buffer-px", type=float, default=HULL_BUFFER_PX_DEFAULT,
                   help="extrapolate this many canvas px past the OUTER hull edge only "
                        "(nearest hull vertex's own triangle, unclamped) instead of the "
                        "strict hull cutoff; a QA render convenience, not a real "
                        f"correspondence — accuracy is unverified past the hull and "
                        f"degrades with distance from it (default {HULL_BUFFER_PX_DEFAULT:.0f}, "
                        f"pass 0 for the strict, no-extrapolation behaviour)")
    args = p.parse_args(argv)

    layers = parse_layers(args.colors)
    out_prefix = args.out_prefix
    if out_prefix == OUT_PREFIX_DEFAULT:
        tag = re.sub(r"[^0-9a-z]+", "_", args.colors.strip().lower()).strip("_")
        out_prefix = f"{out_prefix}_{tag}"
    build(args.pad, out_prefix, layers,
          ora_source=args.source, overlay_coasts=not args.no_coast,
          full_frame=not args.crop, globe_source=args.globe,
          hull_buffer_px=args.hull_buffer_px)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
