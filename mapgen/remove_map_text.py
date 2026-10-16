"""Strip cartographic lettering (and the graticule) from the reprojected Terraqueous
globe so only the terrain colour survives to drive the heightmap, filling every removed
mark with its surrounding terrain colour.

This is a SOURCE-preprocessing step, not part of the game or the committed map pipeline:
it reads the pristine reprojected globe and writes the ``_no_text`` copy that later feeds
``generate_heightmap.py``. Both live under the local-only, gitignored ``sources/`` folder.

Why this is hard: on this artwork the mountain relief is itself reddish-brown, and the
red region-name lettering shares that exact colour family; the labels are semi-transparent
ink drawn over textured relief. So no single colour threshold separates text from terrain.
The detector is therefore a union of narrowly-targeted layers, each keyed on the ONE
property that separates a given class of lettering from the terrain it sits on:

  RED region/place names  -- white top-hat on "redness" (thin red strokes are redder than
      their local background); whole words recovered by morphological reconstruction from
      confident tan-background seeds, plus a compact-shape catch for isolated red capitals
      that sit entirely on reddish terrain (no tan seed).
  DARK region/place names -- dark ink on a lighter surround (black-tophat "ink" gate),
      removed anywhere including on reddish plateaus.
  BOLD near-black capitals -- very-dark (V<70) letter-shaped blobs whose thick strokes
      defeat the ink gate; caught directly by shape.
  GREY / standalone labels on FLAT ground -- strong "darkness" top-hat, gated off relief
      (background-redness small) so faint parchment hatch and mountain hachures are spared;
      catches light grey italic polar/steppe labels and spaced sea names.
  ROTATED mountain-range italics -- dark brown ink (R>=B excludes blue rivers/lakes/sea)
      whose letters close into a word, separated from linework by ELONGATION: rivers,
      ridges, coastlines and the graticule are long simple curves and drop out; compact
      letter-clusters stay. (These semi-transparent labels are the residual-quality limit;
      they fade to faint traces rather than vanishing completely.)
  BLUE sea names -- blue over the grey sea, grown to cover the anti-aliased halo.
  GRATICULE -- the lon/lat rules, found as full-length perfectly-straight horizontals and
      verticals via a long 1-D opening (curved coast/rivers never stay straight that far).
  PAGE annotations -- label fragments / grid on the blank polar page and near-white
      abyssal ocean, confined spatially to the border-connected bright region so interior
      light lowlands are never touched.

Preserved on purpose: mountain relief, coastlines, rivers, political borders.
Fill: OpenCV Navier-Stokes inpaint (surrounding-colour diffusion).

Usage (from the repo root, with mapgen/.venv active):
    python mapgen/remove_map_text.py            # write the de-texted PNG + a QA thumbnail
    python mapgen/remove_map_text.py --preview  # write only a colour-coded detection overlay
    python mapgen/remove_map_text.py --src A.png --out B.png
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mapgen"))
from worldgen.raster import read_rgb_png  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402

SOURCES_DIR = ROOT / "sources"
DEFAULT_SRC = sources_mod.resolve_source_path("terraqueous_globe_reprojected.png", SOURCES_DIR)
#: Local scratch, not manifest-tracked — see ``sources/WIP/``.
DEFAULT_OUT = SOURCES_DIR / "WIP" / "terraqueous_globe_reprojected_no_text.png"
QA_DIR = ROOT / "scratchpad"


# --------------------------------------------------------------------------- helpers
def ink_gate(a):
    """Black-tophat: bright where a dark feature sits on a LIGHTER surround — i.e.
    lettering, as opposed to broad relief or dark-on-dark hachures."""
    V = a.max(2).astype(np.uint8)
    bth = cv2.morphologyEx(V, cv2.MORPH_BLACKHAT,
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    return ndi.binary_dilation(bth > 24, iterations=7)


def _shape_ok(comp, sl, min_area, max_area, max_long, min_extent, er_ratio_min, er):
    area = int(comp.sum())
    if not (min_area <= area <= max_area):
        return False
    h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    if max(h, w) > max_long:
        return False
    if area / max(h * w, 1) < min_extent:
        return False
    if (er[sl] & comp).sum() / area < er_ratio_min:      # too thin -> a line, not a glyph
        return False
    return True


def keep_glyphs(mask, min_area=25, max_area=60000, max_long=600,
                min_extent=0.10, er_ratio_min=0.14, erode=1):
    """Keep connected components that look like glyphs (area / compactness / stroke
    thickness), dropping specks and hairline lines."""
    er = ndi.binary_erosion(mask, iterations=erode)
    lbl, _ = ndi.label(mask)
    keep = np.zeros_like(mask)
    for i, sl in enumerate(ndi.find_objects(lbl), 1):
        if sl is None:
            continue
        comp = (lbl[sl] == i)
        if _shape_ok(comp, sl, min_area, max_area, max_long, min_extent, er_ratio_min, er):
            keep[sl][comp] = True
    return keep


def filter_dark_glyphs(dark):
    """Compact dark blobs = letters; drop long thin river/border/coast lines."""
    lbl, _ = ndi.label(dark)
    keep = np.zeros_like(dark)
    for i, sl in enumerate(ndi.find_objects(lbl), 1):
        if sl is None:
            continue
        comp = (lbl[sl] == i)
        area = int(comp.sum())
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        extent = area / max(h * w, 1)
        longest = max(h, w)
        if (12 <= area <= 4000 and extent >= 0.20 and longest <= 220
                and not (longest > 80 and extent < 0.14)):
            keep[sl][comp] = True
    return keep


def dark_label_runs(mask, close=5, min_area=70, max_area=6500, max_elong=14.0):
    """Separate dark-ink LABEL runs from linework by elongation. Letters are first closed
    into words; a component's bbox-diagonal^2 / area is small for compact letter-clusters
    and large for long simple curves (rivers, ridges, coastlines, graticule), which drop.
    Huge blobs (dark water/shadow) are dropped by area."""
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close, close))).astype(bool)
    lbl, _ = ndi.label(m)
    keep = np.zeros_like(m)
    for i, sl in enumerate(ndi.find_objects(lbl), 1):
        if sl is None:
            continue
        comp = (lbl[sl] == i)
        area = int(comp.sum())
        if not (min_area <= area <= max_area):
            continue
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if (h * h + w * w) / area > max_elong:           # long simple curve -> linework
            continue
        keep[sl][comp] = True
    return keep & mask   # fill only the true ink, not the closing's bridge pixels


def grid_mask(a):
    """The lon/lat graticule: faint, perfectly straight full-length horizontal and
    vertical rules. A long 1-D opening keeps only pixels belonging to a long straight run,
    so curved coastlines/rivers/contours (never straight that far) are spared."""
    V = a.max(2).astype(np.uint8)
    dk = cv2.morphologyEx(255 - V, cv2.MORPH_TOPHAT,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    b = (dk > 7).astype(np.uint8)
    gh = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (130, 1)))
    gv = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 130)))
    return ndi.binary_dilation((gh | gv).astype(bool), iterations=2)


def paper_annotation(a):
    """Clear annotations (label fragments, grid) on the blank page — confined SPATIALLY to
    the true page, not interior light-land patches that merely happen to be bright. The
    page is the large blurred-bright region reaching a pole (top/bottom edge) or the
    near-white abyssal ocean; light lowlands are ringed by darker terrain, so they never
    join it. Any mark darker than the local page level, inside that region, is annotation."""
    V = a.max(2).astype(np.uint8)
    smooth = cv2.blur(V, (25, 25))          # blur first so parchment hatch can't fragment it
    lbl, n = ndi.label(smooth > 205)
    big = np.zeros(lbl.shape, bool)
    if n:
        sizes = np.bincount(lbl.ravel())
        for cid in np.nonzero(sizes > 120000)[0]:
            if cid == 0:
                continue
            ys = np.where(lbl == cid)[0]
            if ys.min() < 60 or ys.max() > lbl.shape[0] - 60:
                big |= (lbl == cid)
    page = ndi.binary_dilation(big, iterations=15)
    paper = cv2.morphologyEx(V, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
    mark = page & ((paper.astype(np.int16) - V) > 22)
    return ndi.binary_dilation(mark, iterations=2)


# --------------------------------------------------------------------------- detection
def build_masks(a):
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    V = a.max(2)
    ink = ink_gate(a)
    redness = np.clip(R - np.maximum(G, B), 0, 255).astype(np.uint8)
    darkness = (255 - V).astype(np.uint8)
    k29 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (29, 29))
    th_red = cv2.morphologyEx(redness, cv2.MORPH_TOPHAT, k29)
    th_dark = cv2.morphologyEx(darkness, cv2.MORPH_TOPHAT, k29)
    bg_red = cv2.morphologyEx(redness, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (45, 45)))

    # RED words: reconstruct whole glyphs/words from confident tan-background seeds,
    # plus isolated red capitals on relief (compact strong-red blobs, no tan seed).
    red = ndi.binary_propagation((th_red > 18) & (bg_red < 9),
                                 mask=(th_red > 11) & (bg_red < 24))
    red = red | keep_glyphs((th_red > 26), min_area=180, max_area=6000, max_long=170,
                            min_extent=0.22, er_ratio_min=0.22)

    dark_a = filter_dark_glyphs((V < 100) & ink)                     # dark names, anywhere
    dark_black = keep_glyphs((V < 70), min_area=140, max_area=9000,  # bold near-black caps
                             min_extent=0.16, er_ratio_min=0.16)
    grey = keep_glyphs((th_dark > 30) & (V < 150) & (redness < 22) & (bg_red < 8),
                       min_area=90, max_area=8000, min_extent=0.18, er_ratio_min=0.18)
    dark_ink = dark_label_runs((V < 128) & (R >= B - 3) & ink)       # rotated range italics
    dark = dark_a | dark_black | grey | dark_ink

    blue = (B - R > 28) & (B - G > 18) & (B > 90) & (V < 205)

    red_body = (R - G > 18) & (R > 110) & (G < 155)
    dark_body = (V < 150) & (bg_red < 12)
    blue_body = (B - R > 10) & (B - G > 4) & (B > 82) & (V < 215)
    return red, dark, blue, red_body, dark_body, blue_body


def compute(a):
    red, dark, blue, red_body, dark_body, blue_body = build_masks(a)
    # Grow each class into its own anti-aliased halo (clipped to its colour) so no ghost
    # rim survives, then union with the geometry-based grid/page layers.
    red = ndi.binary_dilation((ndi.binary_dilation(red, iterations=5) & red_body) | red, iterations=1)
    dark = (ndi.binary_dilation(dark, iterations=3) & dark_body) | dark
    blue = (ndi.binary_dilation(blue, iterations=4) & blue_body) | blue
    grid = grid_mask(a)
    paper = paper_annotation(a)
    mask = ndi.binary_dilation(red | dark | blue | grid | paper, iterations=2)
    return mask, red, dark, blue, grid


# --------------------------------------------------------------------------- driver
def main():
    ap = argparse.ArgumentParser(description="Remove lettering + graticule from the reprojected globe.")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC, help="pristine source PNG to read")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="de-texted PNG to write")
    ap.add_argument("--preview", action="store_true",
                    help="write only a colour-coded detection overlay, do not inpaint")
    args = ap.parse_args()

    a = read_rgb_png(args.src).astype(np.int16)
    mask, red, dark, blue, grid = compute(a)
    print(f"red {int(red.sum())}  dark {int(dark.sum())}  blue {int(blue.sum())}  "
          f"grid {int(grid.sum())}  total_mask {int(mask.sum())}")

    QA_DIR.mkdir(parents=True, exist_ok=True)
    if args.preview:
        ov = a.copy().astype(np.uint8)
        ov[grid] = [0, 200, 255]
        ov[red] = [0, 255, 0]
        ov[dark] = [255, 160, 0]
        ov[blue] = [255, 0, 255]
        prev = Image.fromarray(ov)
        prev.thumbnail((2000, 2000))
        out = QA_DIR / "qa_remove_map_text_preview.png"
        prev.save(out)
        print("wrote", out)
        return

    result = cv2.inpaint(a.astype(np.uint8), mask.astype(np.uint8) * 255,
                         inpaintRadius=6, flags=cv2.INPAINT_NS)
    Image.fromarray(result).save(args.out)
    print("wrote", args.out)
    qa = Image.fromarray(result)
    qa.thumbnail((2000, 2000))
    qa.save(QA_DIR / "qa_remove_map_text.png")
    print("wrote", QA_DIR / "qa_remove_map_text.png")


if __name__ == "__main__":
    main()
