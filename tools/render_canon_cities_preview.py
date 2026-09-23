#!/usr/bin/env python3
"""Dev-only overlay render for the barrier-city catalogue (board #3789, parent #3788).

Reads the committed ``tools/config/canon_cities.json`` (via
``schema.load_canon_cities``) and emits **two** artifacts into ``tools/derived/``
(gitignored — a dev-only authoring aid, never shipped content):

  (a) ``canon_cities_preview.png`` — a human review PNG: a labelled dot per city
      over the reprojected globe, draping the real TWW3 parchment art wherever
      ``project_regions_unified``'s single triangle-warp registration covers the
      canvas (reusing
      ``render_land_regions_preview._parchment_drape_triangle`` wholesale, exactly
      as ``render_hubs_preview`` does), plain globe elsewhere — plus a half-size and
      a tight crop around the catalogued cities, so a proving-slice of a few holds
      isn't lost on the 8192-wide frame.

  (b) ``canon_cities_overlay.png`` — a **transparent 8192x3616 RGBA layer** (dots +
      names on full alpha) Chris drops straight into the GIMP impassable project. It
      registers pixel-exact over the canvas, so he can paint the impassable terrain
      *around* the catalogued holds instead of sealing them out.

The transparent overlay (b) is built by :func:`build_overlay_layer`, a **pure,
source-free function of (cities, canvas_size)** — it touches none of the 118 MB
sources, so the ``run_fixture`` self-check exercises it directly and cheaply. Only
the review PNG (a) needs the parchment drape.

Usage::

    python tools/render_canon_cities_preview.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import render_land_regions_preview as rlr  # noqa: E402 — reuse its drape + font
from config import map_config  # noqa: E402
from worldgen import schema  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
CANON_CITIES_PATH = TOOLS_DIR / "config" / "canon_cities.json"

OUT_PREVIEW_PATH = DERIVED_DIR / "canon_cities_preview.png"
OUT_HALF_PATH = DERIVED_DIR / "canon_cities_preview_half.png"
OUT_CROP_PATH = DERIVED_DIR / "canon_cities_preview_crop.png"
OUT_OVERLAY_PATH = DERIVED_DIR / "canon_cities_overlay.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: A distinct dot colour per barrier terrain (schema._CITY_TERRAINS).
_TERRAIN_DOT = {
    "mountain": (150, 150, 165),
    "marsh": (90, 150, 70),
    "forest": (40, 130, 60),
    "cliff_coast": (60, 110, 200),
}
#: Chris, 2026-09-15: was (255, 0, 255) — collided with the magenta state-border
#: network drawn on the same canvas (mark_state_borders.py / project_regions.py's
#: MAGENTA_RGB), since overlay (b) below is painted alongside it in GIMP.
_DEFAULT_DOT = (127, 127, 255)

DOT_RADIUS = 9


def log(msg: str, t0: float | None = None) -> None:
    print((f"[{time.time() - t0:6.1f}s] " if t0 is not None else "") + msg, flush=True)


def _draw_markers(draw: ImageDraw.ImageDraw, cities, dot_radius: int, font) -> None:
    """Draw one dot + name label per city at its exact anchor — the shared routine
    behind both the transparent overlay and the review PNG. Deterministic: authored
    order, no state read outside ``cities``."""
    for c in cities:
        x, y = int(c.anchor[0]), int(c.anchor[1])
        col = _TERRAIN_DOT.get(c.terrain, _DEFAULT_DOT)
        draw.ellipse([x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius],
                     fill=col + (255,), outline=(0, 0, 0, 255), width=2)
        draw.text((x + dot_radius + 4, y - 16), f"{c.name} ({c.terrain})",
                  fill=(0, 0, 0, 255), font=font,
                  stroke_width=3, stroke_fill=(255, 255, 255, 255))


def build_overlay_layer(cities, canvas_size: tuple[int, int]) -> Image.Image:
    """The transparent GIMP layer (artifact b): an RGBA image the size of the
    canvas, fully transparent ``(0,0,0,0)`` everywhere except an opaque dot + name
    per city at its anchor. A **pure function of ``(cities, canvas_size)``** — no
    sources, no committed bitmaps — so it is fast and deterministic to self-check.
    """
    w, h = canvas_size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = rlr._load_font(30)
    _draw_markers(draw, cities, DOT_RADIUS, font)
    return img


def main(argv: list[str] | None = None) -> int:
    t0 = time.time()
    if not CANON_CITIES_PATH.is_file():
        raise SystemExit(f"{CANON_CITIES_PATH} not found — author the catalogue first")

    cities = schema.load_canon_cities(CANON_CITIES_PATH, canvas=(CANVAS_W, CANVAS_H))
    log(f"{len(cities)} canon cit(y/ies) to draw", t0)

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    # --- artifact (b): the transparent GIMP overlay (pure, source-free) ----
    overlay = build_overlay_layer(cities, (CANVAS_W, CANVAS_H))
    overlay.save(OUT_OVERLAY_PATH)
    log(f"wrote {OUT_OVERLAY_PATH}  ({CANVAS_W}x{CANVAS_H}, transparent GIMP layer)", t0)

    # --- artifact (a): the parchment-draped review PNG ---------------------
    # _parchment_drape_triangle returns a full backdrop already: the globe with
    # the parchment draped on top where the triangle warp reaches, plain globe
    # elsewhere (place_painting starts from a copy of the globe). So the
    # backdrop IS the base — no second globe composite needed.
    backdrop, _placed = rlr._parchment_drape_triangle(t0)
    review = Image.fromarray(backdrop).convert("RGBA")
    review.alpha_composite(overlay)
    review = review.convert("RGB")

    review.save(OUT_PREVIEW_PATH)
    log(f"wrote {OUT_PREVIEW_PATH}", t0)
    review.resize((CANVAS_W // 2, CANVAS_H // 2)).save(OUT_HALF_PATH)
    log(f"wrote {OUT_HALF_PATH}  ({CANVAS_W // 2}x{CANVAS_H // 2})", t0)

    xs = [int(c.anchor[0]) for c in cities]
    ys = [int(c.anchor[1]) for c in cities]
    if xs:
        pad = 240
        x0, x1 = max(0, min(xs) - pad), min(CANVAS_W, max(xs) + pad)
        y0, y1 = max(0, min(ys) - pad), min(CANVAS_H, max(ys) + pad)
        review.crop((x0, y0, x1, y1)).save(OUT_CROP_PATH)
        log(f"wrote {OUT_CROP_PATH}  ({x1 - x0}x{y1 - y0})", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
