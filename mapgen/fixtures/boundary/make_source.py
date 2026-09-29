#!/usr/bin/env python3
"""Build the synthetic boundary fixture — a tiny invented parchment and a mask.

Every pixel here is **our own**, drawn by this script, so the fixture is
committed and the boundary path regression-runs on a clean clone with no
``sources/`` present. The real S3a sources are third-party art and can never be.

The point is not to look like a map; it is to carry every feature the real
ingestion has to survive, so a regression in any of them trips the golden:

* **a luminance gradient across the paper** — the whole reason ink is found by
  *local* contrast. A global threshold gets this fixture wrong, which is exactly
  what should happen.
* **closed cells of very different sizes** — so the merge-small and split-large
  reconciliation both actually fire.
* **a broken boundary line** — the recoverable failure. It must merge two cells,
  not produce an open polyline.
* **lettering over the lines** — the unrecoverable one, and the reason the
  unlabelled feature image outranks the lettered master in the real pipeline.
* **a ruled border interrupted by a run of glyph-shaped blobs** — the
  recoverable-via-bridging case (``worldgen.parchment.glyph_mask`` /
  ``label_blobs``): the cartographer breaks the line to make room for a label,
  leaving a physical gap that plain ``cells_from_ink`` cannot see across, but
  which the detected glyphs — closed and dilated into the barrier — do.
* **a seam-crossing landmass and an enclosed lake in the mask** — so the
  wrap-aware component labelling and the sea-zone split are exercised rather
  than assumed.
* **a half-scale sibling** — the ``frame_alias`` path, which must land in exactly
  the same canvas place as its parent.

Usage::

    python mapgen/fixtures/boundary/make_source.py
    python mapgen/run_fixture.py --update-fixture-manifest
    python mapgen/run_fixture.py --update
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from worldgen import raster  # noqa: E402

HERE = Path(__file__).resolve().parent
SRC_W, SRC_H = 320, 240
CANVAS_W, CANVAS_H = 256, 112

PAPER = (208, 182, 140)
INK = (72, 54, 38)


def _line(img: np.ndarray, x0: int, y0: int, x1: int, y1: int, skip: tuple[int, int] | None = None):
    """Draw a 2 px ink line, optionally leaving a gap (the broken-boundary case)."""
    n = max(abs(x1 - x0), abs(y1 - y0)) + 1
    for i in range(n):
        t = i / max(1, n - 1)
        if skip and skip[0] <= i < skip[1]:
            continue
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        img[max(0, y - 1):y + 1, max(0, x - 1):x + 1] = INK


def _line_with_label_gap(img: np.ndarray, y: int, x0: int, x1: int,
                         gap: tuple[int, int], n_glyphs: int = 3,
                         glyph_w: int = 7, glyph_h: int = 8, spacing: int = 4,
                         margin: int = 1) -> None:
    """A ruled line broken to make room for a run of glyph-shaped ink blobs.

    The line is drawn solid except for ``gap`` (x-offsets from ``x0``, same
    convention as ``_line``'s ``skip``), filled by ``n_glyphs`` compact blocks:
    ``margin`` px of real paper between the line stubs and the outermost
    blocks, ``spacing`` px between blocks. Both are small enough for a 3x3
    dilation plus ``worldgen.parchment.LABEL_CLOSE`` to bridge — but they are
    real gaps in the raw ink, so plain ``cells_from_ink`` still sees an open
    border, and only bridging the *detected glyphs* closes it.

    ``_line``'s own 2-px-wide dab means the line resuming right after the gap
    paints one column *before* its nominal start too (the dab is centred on
    ``x``, covering ``x-1:x+1``) — so the right edge of the usable gap is one
    column narrower than ``gap`` alone would suggest. Accounted for here
    rather than left as an off-by-one for the next person to rediscover.
    """
    _line(img, x0, y, x1, y, skip=gap)
    ga = x0 + gap[0]
    gb_effective = x0 + gap[1] - 1  # the resuming dab's one-column backward bleed
    start = ga + margin
    end = gb_effective - margin  # exclusive-ish: last glyph must end at or before this
    total = n_glyphs * glyph_w + (n_glyphs - 1) * spacing
    if start + total - 1 > end:
        raise ValueError(f"label run ({total} px) does not fit the gap ({end - start + 1} px)")
    x = start
    for _ in range(n_glyphs):
        img[y - glyph_h // 2:y + glyph_h // 2, x:x + glyph_w] = INK
        x += glyph_w + spacing


def build_source() -> np.ndarray:
    img = np.zeros((SRC_H, SRC_W, 3), dtype=np.uint8)
    img[:] = PAPER
    # Vignette: bright top-left to dark bottom-right, ~35% of full range. Ink in
    # the bright corner is lighter than bare paper in the dark one, so only a
    # local test can find both.
    gy, gx = np.mgrid[0:SRC_H, 0:SRC_W]
    shade = 1.0 - 0.35 * ((gx / SRC_W) * 0.5 + (gy / SRC_H) * 0.5)
    img = (img * shade[..., None]).astype(np.uint8)

    # Frame, so the outermost cells are closed.
    _line(img, 8, 8, SRC_W - 8, 8)
    _line(img, 8, SRC_H - 8, SRC_W - 8, SRC_H - 8)
    _line(img, 8, 8, 8, SRC_H - 8)
    _line(img, SRC_W - 8, 8, SRC_W - 8, SRC_H - 8)

    # Interior network: uneven columns and rows give cells of very different size.
    for x in (70, 130, 215, 262):
        _line(img, x, 8, x, SRC_H - 8)
    _line(img, 8, 84, SRC_W - 8, 84)
    _line(img, 8, 160, SRC_W - 8, 160)
    # Extra subdivision only on the left, so density varies across the frame.
    _line(img, 8, 44, 130, 44)
    _line(img, 8, 120, 70, 120)

    # A boundary with a gap in the middle: the two cells it separates must come
    # back as one, not as an open line.
    _line(img, 130, 200, 215, 200, skip=(30, 55))

    # A boundary interrupted by letter-shaped blobs rather than a plain gap —
    # the case only glyph detection + bridging (not plain ink) can close.
    _line_with_label_gap(img, 52, 8, SRC_W - 8, gap=(140, 172))

    # "Lettering": a blob of ink sitting across a line, as a place name does.
    img[92:100, 150:186] = INK
    return img


#: The crop's alpha footprint on the 320x240 source: opaque only right of this x
#: (its "region"), with a transparent rectangular hole punched inside the opaque
#: part. Both are exercised — no cell may form left of the split or inside the
#: hole, and the base layer's cell must survive showing through the hole.
CROP_SPLIT_X = 150
CROP_HOLE = (206, 96, 262, 152)  # x0, y0, x1, y1 in source px


def build_crop() -> np.ndarray:
    """An alpha-masked region crop of the master, for the ``src_valid`` path.

    Frame-aligned to the master (its registration reuses the master's control
    points), so it overlays the same canvas place. It carries:

    * **a binary alpha mask** — opaque only right of :data:`CROP_SPLIT_X`, with a
      transparent hole (:data:`CROP_HOLE`) inside the opaque part. This is the
      intentional footprint the real region crops carry, and the exact thing
      ``.convert("RGB")`` drops. The fixture asserts the crop contributes cells
      only where ``alpha>0`` and that a lower-precedence layer's cell survives
      showing through the hole rather than being blanked and Voronoi-refilled.
    * **an extra interior line the master lacks** (a horizontal rule across its
      footprint), so where it is opaque and outranks the master it visibly
      *densifies* — the whole reason a denser boundary crop is wired in.

    Written RGBA; every opaque pixel copies the master so the ink test sees the
    same paper, and the transparent pixels are left black (alpha 0 excludes them).
    """
    rgb = build_source()
    # A boundary the master does not draw here, so the crop subdivides its own
    # footprint more finely than the layer beneath it.
    _line(rgb, CROP_SPLIT_X, 120, SRC_W - 8, 120)
    rgba = np.zeros((SRC_H, SRC_W, 4), dtype=np.uint8)
    rgba[..., :3] = rgb
    alpha = np.zeros((SRC_H, SRC_W), dtype=np.uint8)
    alpha[:, CROP_SPLIT_X:] = 255
    x0, y0, x1, y1 = CROP_HOLE
    alpha[y0:y1, x0:x1] = 0
    rgba[..., 3] = alpha
    # Zero the RGB of transparent pixels too, so the file cannot smuggle geometry
    # in through a channel the alpha says is absent.
    rgba[alpha == 0, :3] = 0
    return rgba


def build_mask() -> np.ndarray:
    """A canvas-resolution land mask with the awkward cases in it."""
    land = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
    yy, xx = np.mgrid[0:CANVAS_H, 0:CANVAS_W]
    # Main continent.
    land[18:92, 40:200] = True
    # A landmass crossing the wrap seam — one body, not two.
    land[30:70, 236:] = True
    land[30:70, :16] = True
    # An enclosed lake, so the sea-zone split sees more than one water body.
    land[(xx - 96) ** 2 + (yy - 50) ** 2 < 90] = False
    # A detached island.
    land[(xx - 214) ** 2 + ((yy - 84) * 2) ** 2 < 60] = True
    return land


def main() -> int:
    src = build_source()
    raster.write_rgb_png(HERE / "synthetic_parchment.png", src)
    # The alias sibling: exactly half scale, so parent_px = sibling_px * 2.
    raster.write_rgb_png(HERE / "synthetic_parchment_half.png", src[::2, ::2])
    # The alpha-masked region crop: exercises the src_valid / alpha-footprint path.
    raster.write_rgba_png(HERE / "synthetic_parchment_crop.png", build_crop())
    raster.write_mask_png(HERE / "mask.png", build_mask())
    print(f"wrote synthetic_parchment.png {src.shape[1]}x{src.shape[0]}, "
          f"synthetic_parchment_half.png, synthetic_parchment_crop.png, "
          f"mask.png {CANVAS_W}x{CANVAS_H}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
