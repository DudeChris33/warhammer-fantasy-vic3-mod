#!/usr/bin/env python3
"""Rebuild the two governance law icons that show fasces (#6642).

Vanilla's Corporate State and Social Monarchy law icons carry fasces, which the
mod renames Guild State and Estates Monarchy. This generator rebuilds both from
vanilla art:

* ``corporate_state`` (Guild State): vanilla's three figures keep their hands;
  the axe and the rod bundle become an open charter (a sheet between two rolled
  ends, paper tone, a hanging seal on two ribbon tails). The sheet's texture is
  vanilla ``law_icon_parts/big_banner``; the six fists are restored from vanilla
  on top, so the figures grip the charter's lower edge.
* ``social_monarchy`` (Estates Monarchy): vanilla ``law_icons/monarchy`` with its
  cross removed (the same crown outline as the money glyph, #6575) between two
  ``law_icon_parts/flag`` banners on thickened poles, flying outward.

Inputs: the vanilla install (``--game`` or ``VANILLA_ROOT``, read-only).
Output: ``gfx/interface/icons/law_icons/{corporate_state,social_monarchy}.dds``
at the vanilla path with vanilla's header, size, format and mip chain
(``dds.py``). RGB is 0 under alpha 0.

Modes::

    --preview DIR   <id>.png and contact_sheet.png (vanilla | new at 256 px, 64 px and 48 px)
    --write         write both overrides into gfx/
    --check         header/size/mip parity with vanilla, plus a fresh regeneration
                    byte-compared against each committed file

Deterministic for the pinned stack in ``mapgen/requirements.txt``; no
randomness, clock or OS state. Run it with ``mapgen/.venv``'s Python.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dds  # noqa: E402
from currency_icons import (  # noqa: E402
    REPO, SHEET_BG, display, on_bg, over, resize_premul, to_float, to_u8, vanilla_root,
)

LAW = "gfx/interface/icons/law_icons/"
PARTS = LAW + "law_icon_parts/"
SS = 4  # supersampling for drawn shapes


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load(game: Path, rel: str) -> np.ndarray:
    return to_float(dds.read_top(game / rel))


def grid(h: int, w: int):
    """Supersampled pixel-centre coordinates in output pixel units."""
    yy, xx = np.mgrid[0:h * SS, 0:w * SS]
    return (yy + 0.5) / SS, (xx + 0.5) / SS


def down(m: np.ndarray) -> np.ndarray:
    """Box-average a supersampled array back to output pixels."""
    h, w = m.shape[0] // SS, m.shape[1] // SS
    return m.reshape(h, SS, w, SS, *m.shape[2:]).mean(axis=(1, 3))


def layer(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    out = np.zeros(alpha.shape + (4,))
    out[..., :3] = rgb
    out[..., 3] = alpha
    return out


def halo(alpha: np.ndarray, sigma: float, strength: float) -> np.ndarray:
    """The dark glow vanilla law art sits on, fitted by eye to the vanilla icons."""
    a = np.clip(ndimage.gaussian_filter(alpha, sigma) * strength, 0, 1)
    return layer(np.zeros(alpha.shape + (3,)), a)


def lum(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def ramp(t: np.ndarray, dark, light) -> np.ndarray:
    d, l = np.array(dark) / 255.0, np.array(light) / 255.0
    return d + (l - d) * np.clip(t, 0, 1)[..., None]


def crop_alpha(a: np.ndarray, thresh: float = 0.02) -> np.ndarray:
    ys, xs = np.nonzero(a[..., 3] > thresh)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def paste(canvas: np.ndarray, part: np.ndarray, x0: int, y0: int) -> np.ndarray:
    """``part`` over ``canvas`` with its top-left at (x0, y0)."""
    h, w = canvas.shape[:2]
    full = np.zeros_like(canvas)
    ph, pw = part.shape[:2]
    ys, xs = slice(max(0, y0), min(h, y0 + ph)), slice(max(0, x0), min(w, x0 + pw))
    full[ys, xs] = part[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    return over(full, canvas)


# ---------------------------------------------------------------------------
# Guild State: three figures holding a charter
# ---------------------------------------------------------------------------

# Geometry in px of the 256x256 vanilla icon, measured on 9x crops.
PAPER_DARK, PAPER_LIGHT = (124, 100, 72), (232, 214, 180)
SHEET = (52, 90, 220, 120)            # x0, y0, x1, y1 of the open sheet
ROLL_W, ROLL_OVER = 15, 8             # rolled ends: width, overhang above/below the sheet
FISTS = [                             # (cx, cy, rx, ry): vanilla fists restored on top
    (55.5, 119.0, 7.5, 6.0), (98.5, 119.0, 5.0, 4.5), (116.0, 118.0, 6.5, 5.5),
    (157.0, 118.0, 7.5, 5.5), (175.0, 118.0, 7.0, 5.5), (212.5, 115.5, 8.0, 5.0),
]
SEAL = dict(cx=137.0, r=9.0, drop=11.0, colour=(128, 58, 40))
TEXT = [                              # (row as a fraction of the sheet height, words as fractions of its width)
    (0.32, [(0.07, 0.21), (0.24, 0.33), (0.36, 0.55), (0.58, 0.66), (0.69, 0.84), (0.87, 0.93)]),
    (0.52, [(0.07, 0.15), (0.18, 0.37), (0.40, 0.47), (0.50, 0.71), (0.74, 0.80), (0.83, 0.93)]),
    (0.72, [(0.07, 0.26), (0.29, 0.36), (0.39, 0.50), (0.53, 0.62)]),
]


def sheet_layer(game: Path, h: int, w: int) -> np.ndarray:
    x0, y0, x1, y1 = SHEET
    sw, sh = x1 - x0, y1 - y0
    banner = load(game, PARTS + "big_banner.dds")[8:205, 91:166]      # the body, without the point
    tex = resize_premul(np.rot90(banner), (sw, sh))
    L = lum(tex[..., :3])
    lo, hi = np.percentile(L, 5), np.percentile(L, 95)
    t = (L - lo) / max(hi - lo, 1e-6)
    v = (np.arange(sh)[:, None] + 0.5) / sh
    t = 0.22 + 0.62 * t + 0.16 * (1 - v)                                # lit from above
    rgb = ramp(t, PAPER_DARK, PAPER_LIGHT)
    # hand-lettered lines: short dark strokes ("words") on three rows
    yy, xx = grid(sh, sw)
    ink = np.zeros(yy.shape)
    for row, words in TEXT:
        on_row = np.abs(yy - row * sh) < 0.6
        for a, b in words:
            ink = np.maximum(ink, on_row & (xx > a * sw) & (xx < b * sw))
    ink = down(ink) * 0.38
    rgb = rgb * (1 - ink[..., None])
    # rims: darker top and bottom edge
    edge = np.zeros(sh)
    edge[0], edge[-1], edge[1], edge[-2] = 0.45, 0.45, 0.2, 0.2
    rgb = rgb * (1 - edge[:, None, None])
    out = np.zeros((h, w, 4))
    out[y0:y1, x0:x1] = layer(rgb, np.ones((sh, sw)))
    return out


def roll_layer(h: int, w: int, cx: float) -> np.ndarray:
    """A rolled end: a vertical cylinder of paper with a spiral on its top face."""
    _, y0, _, y1 = SHEET
    top, bot = y0 - ROLL_OVER, y1 + ROLL_OVER
    r, ry = ROLL_W / 2, 2.6
    yy, xx = grid(h, w)
    u = (xx - (cx - r)) / ROLL_W                                     # 0..1 across the roll
    inside_x = (u >= 0) & (u <= 1)
    body = inside_x & (yy >= top) & (yy <= bot + ry * np.sqrt(np.clip(1 - (2 * u - 1) ** 2, 0, 1)))
    face_d = ((xx - cx) / r) ** 2 + ((yy - top) / ry) ** 2
    face = face_d <= 1
    shade = 0.35 + 0.65 * np.sin(np.pi * np.clip(u * 0.85 + 0.12, 0, 1)) ** 0.8
    shade = np.where(u < 0.3, shade + 0.25 * (0.3 - u) / 0.3 * (u > 0.08), shade)  # rim light
    t = np.where(face, 0.25 + 0.45 * ((np.sqrt(face_d) * 3.2) % 1.0 > 0.45), shade)
    alpha = down((body | face).astype(float))
    rgb = down(ramp(t, PAPER_DARK, PAPER_LIGHT) * (body | face)[..., None]) / np.maximum(alpha, 1e-6)[..., None]
    return layer(np.clip(rgb, 0, 1), alpha)


def seal_layer(h: int, w: int) -> np.ndarray:
    _, _, _, y1 = SHEET
    cx, r = SEAL["cx"], SEAL["r"]
    cy = y1 + SEAL["drop"]
    yy, xx = grid(h, w)
    base = np.array(SEAL["colour"]) / 255.0
    # two ribbon tails from under the sheet to below the seal, notched ends
    ribbons = np.zeros(yy.shape, bool)
    for side in (-1, 1):
        x_top, x_bot = cx + side * 3.0, cx + side * 9.0
        y_top, y_bot = y1 - 2, cy + r + 8
        f = np.clip((yy - y_top) / (y_bot - y_top), 0, 1)
        centre = x_top + (x_bot - x_top) * f
        notch = (y_bot - yy) < 3.5 - 3.5 * np.abs(xx - centre) / 3.2
        ribbons |= (np.abs(xx - centre) <= 3.2) & (yy >= y_top) & (yy <= y_bot) & ~notch
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    disc = d <= 1
    # wax: lit from the top left, a raised rim and a pressed centre
    lx, ly = (xx - cx) / r, (yy - cy) / r
    light = np.clip(0.75 - 0.35 * (lx + ly), 0.35, 1.2)
    rim = (d > 0.62) & (d < 0.78)
    shade_disc = np.where(rim, light * 0.7, np.where(d < 0.62, 0.85 + 0.25 * (-lx - ly) * 0.5, light))
    shade = np.where(disc, shade_disc, 0.62 + 0.15 * (xx < cx))
    m = (disc | ribbons)
    alpha = down(m.astype(float))
    rgb = down(np.clip(base[None, None] * shade[..., None] * 1.25, 0, 1) * m[..., None])
    return layer(rgb / np.maximum(alpha, 1e-6)[..., None], alpha)


def ellipse_mask(h: int, w: int, ellipses, feather: float = 1.0) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    m = np.zeros((h, w))
    for cx, cy, rx, ry in ellipses:
        d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
        m = np.maximum(m, np.clip((1 - d) * min(rx, ry) / feather + 0.5, 0, 1))
    return m


def guild_state(game: Path) -> np.ndarray:
    src = load(game, LAW + "corporate_state.dds")
    h, w = src.shape[:2]
    base = src.copy()
    x0, y0, x1, y1 = SHEET
    # 1. erase the axe (left of the bundle) and the shaft's right end
    base[70:150, :47] = 0
    base[85:126, x1 + ROLL_W // 2 + 1:] = 0
    # 2. below the sheet the rods' lower edge showed between the fists: continue the
    #    figures upward from the first clean row under the bundle
    clean = 127
    base[y1 - 2:clean, 47:x1 + ROLL_W] = src[clean, 47:x1 + ROLL_W]
    # 3. the charter, its halo, the seal
    sheet = sheet_layer(game, h, w)
    rolls = over(roll_layer(h, w, x1 + 1), roll_layer(h, w, x0 - 1))
    charter = over(rolls, sheet)
    seal = seal_layer(h, w)
    new_alpha = np.maximum(charter[..., 3], seal[..., 3])
    out = over(halo(new_alpha, 2.2, 1.6), base)
    out = over(charter, out)
    out = over(halo(seal[..., 3], 1.5, 1.2), out)
    out = over(seal, out)
    # 4. the fists, from vanilla, in front of the sheet
    fists = ellipse_mask(h, w, FISTS)
    fist_layer = src.copy()
    fist_layer[..., 3] *= fists
    out = over(fist_layer, out)
    return to_u8(out)


# ---------------------------------------------------------------------------
# Estates Monarchy: the crossless crown between two banners
# ---------------------------------------------------------------------------

CROSS_BOX = (118, 186, 0, 66)          # x0, x1, y0, y1 of the cross in monarchy.dds (302 px)
ORB = (151.5, 85.5, 23.5)              # cx, cy, r of the orb in monarchy.dds
CROWN_W, CROWN_BOTTOM = 160, 234       # crown width and bottom edge on the 256 canvas
POLE_W, POLE_TOP, POLE_BOTTOM = 14, 28, 226
POLE_X = (62, 194)                     # pole centres
CLOTH = (82, 15, 192, 106)             # x0, y0, x1, y1 of the cloth in flag.dds
CLOTH_W, CLOTH_H = 64, 78              # cloth size on the canvas


def crossless_crown(game: Path) -> np.ndarray:
    m = load(game, LAW + "monarchy.dds")
    x0, x1, y0, y1 = CROSS_BOX
    cx, cy, r = ORB
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]] + 0.5
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    zone = np.zeros(m.shape[:2], bool)
    zone[y0:y1, x0:x1] = True
    out = m.copy()
    out[zone] = 0
    # close the orb's top where the cross stood: continue the column below upward
    cap = zone & (d <= r)
    col = m[y1, :, :]
    out[cap] = col[np.nonzero(cap)[1]]
    out[..., 3] = np.where(zone, np.clip(r + 0.5 - d, 0, 1) * (d <= r + 1), out[..., 3])
    # its own dark glow, like the rest of the crown's outline
    glow = halo((zone & (d <= r)).astype(float), 2.0, 1.4)
    glow[..., 3] *= zone
    return crop_alpha(over(out, glow))


def pole(h: int) -> np.ndarray:
    """A banner pole POLE_W wide with a ball finial, shaded like the flag part's pole."""
    yy, xx = grid(h, POLE_W + 6)
    cx, r = (POLE_W + 6) / 2, POLE_W / 2
    u = (xx - (cx - r)) / POLE_W
    shaft = (u >= 0) & (u <= 1) & (yy >= 9)
    fr = POLE_W * 0.75
    ball = (xx - cx) ** 2 + (yy - fr) ** 2 <= fr ** 2
    shade = np.where(ball, np.clip(0.95 - 0.45 * ((xx - cx) + (yy - fr)) / fr, 0.3, 1.1),
                     0.45 + 0.55 * np.sin(np.pi * np.clip(u * 0.85 + 0.1, 0, 1)) ** 0.7)
    m = shaft | ball
    alpha = down(m.astype(float))
    rgb = down(ramp(shade, (58, 46, 33), (214, 194, 160)) * m[..., None]) / np.maximum(alpha, 1e-6)[..., None]
    return layer(np.clip(rgb, 0, 1), alpha)


def estates_monarchy(game: Path) -> np.ndarray:
    h = w = 256
    canvas = np.zeros((h, w, 4))
    flag = load(game, PARTS + "flag.dds")
    x0, y0, x1, y1 = CLOTH
    cloth = resize_premul(flag[y0 - 4:y1 + 6, x0:x1 + 6], (CLOTH_W, CLOTH_H + 10))
    p = pole(POLE_BOTTOM - POLE_TOP + 9)
    for i, px in enumerate(POLE_X):
        c = cloth[:, ::-1] if i == 0 else cloth                  # both fly outward
        cx0 = px - POLE_W // 2 - CLOTH_W + 2 if i == 0 else px + POLE_W // 2 - 2
        canvas = paste(canvas, c, cx0, POLE_TOP + 6)
        canvas = paste(canvas, p, px - p.shape[1] // 2, POLE_TOP - 9)
    canvas = over(canvas, halo(canvas[..., 3], 2.0, 1.0))
    crown = crossless_crown(game)
    ch = round(crown.shape[0] * CROWN_W / crown.shape[1])
    crown = resize_premul(crown, (CROWN_W, ch))
    canvas = paste(canvas, crown, (w - CROWN_W) // 2, CROWN_BOTTOM - ch)
    return to_u8(canvas)


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

ICONS = {
    "corporate_state": guild_state,
    "social_monarchy": estates_monarchy,
}


def generate(game: Path):
    for name, build in ICONS.items():
        yield name, LAW + name + ".dds", build(game)


def contact_sheet(rows, out: Path):
    font = ImageFont.load_default(size=14)
    pad, label_w = 14, 170
    sizes = (64, 48)
    cell_h = 256 + 2 * pad
    sheet_w = label_w + 2 * 256 + 4 * max(sizes) + 7 * pad
    sheet = Image.new("RGB", (sheet_w, 44 + cell_h * len(rows)), SHEET_BG[:3])
    d = ImageDraw.Draw(sheet)
    d.text((pad, 14), "vanilla | new at 256 px  -  vanilla | new at 64 px  -  vanilla | new at 48 px",
           fill=(220, 210, 190), font=font)
    for i, (name, src, img) in enumerate(rows):
        y = 44 + i * cell_h + pad
        d.text((pad, y + 120), name, fill=(235, 225, 200), font=font)
        x = label_w
        for im in (src, img):
            sheet.paste(on_bg(im, SHEET_BG), (x, y))
            x += 256 + pad
        for px in sizes:
            x += pad
            for im in (src, img):
                sheet.paste(display(im, px, SHEET_BG), (x, y + 128 - px // 2))
                x += px + pad
    sheet.save(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", type=Path, metavar="DIR", help="write PNGs and contact_sheet.png into DIR")
    mode.add_argument("--write", action="store_true", help="write the overrides into gfx/")
    mode.add_argument("--check", action="store_true", help="parity with vanilla + byte-identical regeneration")
    ap.add_argument("--game", help="Victoria 3 install's game folder (default: $VANILLA_ROOT)")
    args = ap.parse_args(argv)

    game = vanilla_root(args.game)
    if game.resolve() == REPO.resolve():
        raise SystemExit("--game must be the vanilla install, not this repo")

    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        rows = []
        for name, rel, img in generate(game):
            Image.fromarray(img, "RGBA").save(args.preview / f"{name}.png")
            rows.append((name, dds.read_top(game / rel), img))
        contact_sheet(rows, args.preview / "contact_sheet.png")
        print("wrote", args.preview / "contact_sheet.png")
        return 0

    if args.write:
        for _name, rel, img in generate(game):
            dds.write_like(game / rel, img, REPO / rel)
            print("wrote", rel)
        return 0

    problems = []
    for _name, rel, img in generate(game):
        vanilla, ours = game / rel, REPO / rel
        found = dds.check_like(vanilla, ours)
        if not found and dds.encode_like(vanilla, img) != ours.read_bytes():
            found = [f"{rel}: committed file differs from a fresh regeneration"]
        problems += found
        print(("FAIL " if found else "ok   ") + rel)
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
