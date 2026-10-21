#!/usr/bin/env python3
"""Replace the pound sign painted into vanilla interface icons with the mod's crown.

#6575 swapped the texture behind ``@money!`` for a gold crown, but many vanilla
icons carry a £ inside their own art (the GDP gear, map modes, subsidy markers,
tax laws, ...). This generator rebuilds each listed icon from the vanilla file
and one crown master, driven by the recipes in ``currency_icons.json``.

Inputs
    * the vanilla file at ``<game>/<recipe path>`` (read-only; ``--game`` or the
      ``VANILLA_ROOT`` environment variable, pointing at the install's ``game``
      folder);
    * the crown master: the top mip of the committed
      ``gfx/interface/icons/generic_icons/money.dds`` (#6575).

Output
    ``<repo>/<recipe path>``: the override at the vanilla path, with the vanilla
    header, size, pixel format and mip count (``dds.py``).

Per icon (keys are the recipe fields, documented in ``README.md``):
    1. Read the vanilla top mip (RGB under alpha 0 ignored).
    2. Glyph mask inside ``region``: ``bright`` / ``dark`` (luminance against
       ``thresh``, a number or ``"otsu"``), ``solid`` (a bare glyph: the opaque
       components centred in the region), or ``cutout`` (alpha holes enclosed by
       the silhouette). Minus ``protect``; specks under ``min_blob`` dropped;
       closed, then grown by ``dilate`` px (``erase: region`` refills the whole
       region instead, for an embossed glyph whose edges fade into the field).
    3. Remove the glyph: ``inpaint`` continues the field under it (biharmonic,
       all four channels; for a cut-out only inside the silhouette), ``clear``
       erases a bare glyph and its drop shadow, keeping everything else.
    4. Place the crown, scaled to fit the glyph's box times ``scale``:
       ``painted`` is the master itself; ``stencil`` is a flat crown cut from the
       master's own alpha outline with two cap windows punched where the
       master's cap panels are, so orb, arches and band survive (one shape).
    5. Colour it. Painted: ``transfer`` gives each crown pixel the colour of the
       glyph pixel at the same luminance rank, so the crown inherits the glyph's
       own metal ramp (``palette: region`` ranks the whole region instead);
       ``tint`` keeps the master's shading in the glyph's median colour (for
       one-tone glyphs, where rank transfer goes flat). Stencil: ``flat`` takes
       the glyph's median colour and alpha; ``punch`` cuts the crown out of the
       field (cut-out glyphs).
    6. A ``clear`` icon gets a drop shadow fitted to the vanilla glyph's own
       (Gaussian width and strength by least squares, colour from the halo).
    7. ``protect`` pixels (a polygon in front, or the red no-sign stroke) are
       restored from vanilla on top.

Twin icons (``*_not``) are separate recipes, usually ``like`` their base: each
takes its colours from its own vanilla glyph, so vanilla's own recolouring
(teal, dimmed) carries over.

Modes::

    --preview DIR   per-icon PNGs (as written, DXT1 loss included), <id>_mask.png
                    and contact_sheet.png (vanilla | new, enlarged and at display size)
    --write         write the overrides into gfx/
    --check         header/size/mip parity with vanilla, plus a fresh regeneration
                    byte-compared against each committed file

Deterministic for the pinned stack in ``mapgen/requirements.txt`` (numpy, Pillow,
scipy, scikit-image); no randomness, no clock, no OS state. Run it with
``mapgen/.venv``'s Python.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from skimage.filters import threshold_otsu
from skimage.restoration import inpaint_biharmonic

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dds  # noqa: E402

ARTGEN = Path(__file__).resolve().parent
REPO = ARTGEN.parent
RECIPES = ARTGEN / "currency_icons.json"
CROWN_MASTER = "gfx/interface/icons/generic_icons/money.dds"
STENCIL_UPSAMPLE = 8


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def lum(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def to_float(rgba_u8: np.ndarray) -> np.ndarray:
    return rgba_u8.astype(np.float64) / 255.0


def to_u8(rgba: np.ndarray) -> np.ndarray:
    out = np.clip(np.rint(np.clip(rgba, 0.0, 1.0) * 255.0), 0, 255).astype(np.uint8)
    out[out[..., 3] == 0, :3] = 0
    return out


def premul(rgba: np.ndarray) -> np.ndarray:
    out = rgba.copy()
    out[..., :3] *= rgba[..., 3:4]
    return out


def unpremul(p: np.ndarray) -> np.ndarray:
    a = p[..., 3:4]
    rgb = np.where(a > 1e-6, p[..., :3] / np.maximum(a, 1e-6), 0.0)
    return np.concatenate([np.clip(rgb, 0, 1), np.clip(a, 0, 1)], axis=-1)


def over(top: np.ndarray, bottom: np.ndarray) -> np.ndarray:
    """Straight-alpha RGBA ``top`` over ``bottom``."""
    pt, pb = premul(top), premul(bottom)
    return unpremul(pt + pb * (1.0 - top[..., 3:4]))


def resize_premul(rgba: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Lanczos resize of straight RGBA through premultiplied channels."""
    p = premul(rgba)
    chans = [np.asarray(Image.fromarray(p[..., c].astype(np.float32), "F").resize(size, Image.LANCZOS),
                        dtype=np.float64) for c in range(4)]
    return unpremul(np.clip(np.stack(chans, -1), 0, 1))


def resize_mask(m: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    img = Image.fromarray(m.astype(np.float32), "F").resize(size, Image.LANCZOS)
    return np.clip(np.asarray(img, dtype=np.float64), 0, 1)


def region_mask(h: int, w: int, reg) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w]
    xx = (xx + 0.5) / w
    yy = (yy + 0.5) / h
    if isinstance(reg, dict) and "circle" in reg:
        cx, cy, r = reg["circle"]
        return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    x0, y0, x1, y1 = reg
    return (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)


def polygon_mask(h: int, w: int, pts, ss: int = 4) -> np.ndarray:
    """Antialiased polygon (fractions of the icon) as a float mask."""
    img = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(img).polygon([(x * w * ss, y * h * ss) for x, y in pts], fill=255)
    return np.asarray(img.resize((w, h), Image.BOX), dtype=np.float64) / 255.0


def drop_specks(m: np.ndarray, min_blob: int) -> np.ndarray:
    lab, n = ndimage.label(m)
    if not n:
        return m
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    keep = np.flatnonzero(sizes >= min_blob) + 1
    return np.isin(lab, keep)


# ---------------------------------------------------------------------------
# the crown master and its stencil
# ---------------------------------------------------------------------------

def load_master(repo: Path) -> np.ndarray:
    m = to_float(dds.read_top(repo / CROWN_MASTER))
    ys, xs = np.nonzero(m[..., 3] > 0.04)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def crown_geometry(master: np.ndarray) -> dict:
    """Measure the painted master's cap panels, at STENCIL_UPSAMPLE x.

    The master's alpha is one solid silhouette: arches, cap and band all opaque.
    The cap panels between the arches are the darker painted areas: the two
    largest dark regions inside the silhouette (clear of its dark rim) above the
    points. From them come the cuts the stencil is made by: their top and bottom
    rows (the points line), the gap between them (the centre arch) and their inset
    from the silhouette's sides (the outer arches). Painted detail is too noisy to
    punch out directly, so the windows are rebuilt from these measurements.
    """
    u = STENCIL_UPSAMPLE
    h, w = master.shape[:2]
    big = resize_premul(master, (w * u, h * u))
    a = big[..., 3]
    inside = a > 0.5
    edge = ndimage.distance_transform_edt(inside)
    yy = (np.arange(h * u)[:, None] + 0.5) / (h * u)
    dark = (edge > 2.5 * u) & (lum(big[..., :3]) < 0.68) & (yy < 0.64)
    dark = ndimage.binary_opening(dark, iterations=u // 2)
    lab, n = ndimage.label(dark)
    sizes = ndimage.sum(dark, lab, range(1, n + 1))
    two = np.argsort(sizes, kind="stable")[-2:] + 1
    (ly, lx), (ry, rx) = sorted((np.nonzero(lab == k) for k in two), key=lambda yx: yx[1].mean())
    cols = np.arange(w * u)
    left = np.array([cols[row].min() if row.any() else 0 for row in inside])
    right = np.array([cols[row].max() if row.any() else 0 for row in inside])
    inner_l, inner_r = np.percentile(lx, 90), np.percentile(rx, 10)
    inset = float(np.median(np.concatenate([
        [lx[ly == y].min() - left[y] for y in np.unique(ly)],
        [right[y] - rx[ry == y].max() for y in np.unique(ry)],
    ])))
    ys = np.concatenate([ly, ry])
    return {
        "alpha": a, "left": left, "right": right,
        "cx": float(inner_l + inner_r) / 2, "centre_half": float(inner_r - inner_l) / 2,
        "inset": inset, "top": float(np.percentile(ys, 3)), "bottom": float(np.percentile(ys, 97)),
    }


def crown_stencil(geo: dict, stroke: float) -> np.ndarray:
    """Flat crown (float alpha, STENCIL_UPSAMPLE x) cut from the master's own outline.

    The silhouette is the master's alpha. Two windows are punched in the cap at
    the measured panels (inset from each row's silhouette edge, either side of
    the centre arch, between the panels' top and the points line), so the outer
    arches, centre arch, orb, points and band stay solid. ``stroke`` (master px)
    is the least arch width: arches widen to it so they survive small sizes.
    """
    u = STENCIL_UPSAMPLE
    a = geo["alpha"]
    hh, ww = a.shape
    yy, xx = np.mgrid[0:hh, 0:ww] + 0.5
    inset = max(geo["inset"], stroke * u)
    half = max(geo["centre_half"], stroke * u / 2)
    win = ((xx > geo["left"][:, None] + inset) & (xx < geo["right"][:, None] - inset)
           & (np.abs(xx - geo["cx"]) > half) & (yy > geo["top"]) & (yy < geo["bottom"]))
    win = ndimage.gaussian_filter(win.astype(np.float64), 1.5 * u) > 0.5
    soft = ndimage.gaussian_filter(win.astype(np.float64), 0.4 * u)
    return np.clip(ndimage.gaussian_filter(a, 0.3 * u) * (1.0 - soft), 0, 1)


# ---------------------------------------------------------------------------
# glyph detection and removal
# ---------------------------------------------------------------------------

def protect_mask(src: np.ndarray, spec) -> np.ndarray:
    h, w = src.shape[:2]
    if not spec:
        return np.zeros((h, w))
    m = np.zeros((h, w))
    if "poly" in spec:
        poly = polygon_mask(h, w, spec["poly"])
        if spec.get("grow"):
            poly = np.clip(ndimage.grey_dilation(poly, size=2 * spec["grow"] + 1), 0, 1)
        m = np.maximum(m, poly)
    if spec.get("red"):
        r, g, b = src[..., 0], src[..., 1], src[..., 2]
        # red, not orange: well above green, with green and blue level
        red = (r - g > 0.15) & (np.abs(g - b) < 0.12) & (src[..., 3] > 0.5)
        red = drop_specks(red, 6)
        red = ndimage.binary_dilation(red, iterations=1)  # take the stroke's dark edge too
        m = np.maximum(m, np.clip(ndimage.gaussian_filter(red.astype(np.float64), 0.6) * 1.5, 0, 1))
    return m


def glyph_masks(src: np.ndarray, r: dict, prot: np.ndarray):
    h, w = src.shape[:2]
    reg = region_mask(h, w, r["region"])
    A = src[..., 3]
    L = lum(src[..., :3])
    kind = r["glyph"]
    t = r.get("thresh", 0.5)
    if t == "otsu" and kind in ("bright", "dark"):
        # split the region's own pixels into glyph and field (Otsu), plus an offset
        t = float(threshold_otsu(L[reg & (A > 0.05)])) + r.get("thresh_offset", 0.0)
    if kind == "bright":
        m = reg & (L > t) & (A > 0.5)
    elif kind == "dark":
        m = reg & (L < t) & (A > 0.05)
    elif kind == "solid":
        # a bare glyph: the opaque components whose centre lies in the region
        m = (A > t) & (prot < 0.5)
        lab, n = ndimage.label(m)
        cents = ndimage.center_of_mass(m, lab, range(1, n + 1)) if n else []
        keep = [i + 1 for i, (cy, cx) in enumerate(cents) if reg[int(cy), int(cx)]]
        m = np.isin(lab, keep)
        reg = np.ones_like(reg)
    elif kind == "cutout":
        solid = A > 0.5
        m = reg & ndimage.binary_fill_holes(solid) & ~solid
    else:
        raise ValueError(f"unknown glyph kind {kind!r}")
    m &= prot < 0.5
    m = drop_specks(m, r.get("min_blob", 12))
    core = ndimage.binary_closing(m, iterations=1) & reg
    grown = ndimage.binary_dilation(core, iterations=r.get("dilate", 2))
    if kind != "solid":
        grown &= reg
    if r.get("erase") == "region":
        # an embossed glyph whose edges fade into the field: refill the whole region
        grown = reg & (prot < 0.5)
    return core, grown, t


def fit_shadow(src: np.ndarray, core: np.ndarray):
    """Gaussian drop shadow ``gain * blur(core alpha, sigma)`` fitted to vanilla's halo."""
    A = src[..., 3]
    body = ndimage.binary_dilation(core, iterations=1)
    ca = A * body
    near = ndimage.binary_dilation(core, iterations=12) & ~ndimage.binary_dilation(core, iterations=2)
    near &= A < 0.98
    if near.sum() < 10:
        return None
    best = None
    for sigma in np.arange(0.5, 8.01, 0.25):
        b = ndimage.gaussian_filter(ca, sigma)[near]
        t = A[near]
        gain = float(np.dot(b, t) / max(np.dot(b, b), 1e-9))
        e = float(np.mean((np.clip(gain * b, 0, 1) - t) ** 2))
        if best is None or e < best[0]:
            best = (e, float(sigma), gain)
    halo = near & (A > 0.03) & (A < 0.9)
    wts = A[halo]
    colour = (src[..., :3][halo] * wts[:, None]).sum(0) / max(wts.sum(), 1e-9) if halo.any() else np.zeros(3)
    return {"sigma": best[1], "gain": best[2], "rgb": colour, "rms": best[0] ** 0.5}


def shadow_layer(alpha: np.ndarray, sh: dict) -> np.ndarray:
    a = np.clip(sh["gain"] * ndimage.gaussian_filter(alpha, sh["sigma"]), 0, 1)
    return np.concatenate([np.broadcast_to(sh["rgb"], alpha.shape + (3,)), a[..., None]], -1)


def remove_glyph(src: np.ndarray, r: dict, core: np.ndarray, grown: np.ndarray, sh):
    fill = r.get("fill", "inpaint")
    out = src.copy()
    if fill == "inpaint":
        if r["glyph"] == "cutout":
            inside = ndimage.binary_fill_holes(src[..., 3] > 0.5)
            hole = ndimage.binary_dilation(grown, iterations=r.get("rim", 2)) & inside
            for c in range(3):
                out[..., c] = inpaint_biharmonic(src[..., c], hole)
            out[..., 3] = np.where(hole, 1.0, src[..., 3])
        else:
            for c in range(4):
                out[..., c] = inpaint_biharmonic(src[..., c], grown)
        return np.clip(out, 0, 1)
    if fill == "clear":
        # zone the glyph and its shadow occupy; keep every other opaque thing
        reach = int(np.ceil(3 * (sh["sigma"] if sh else 1.0))) + 2
        zone = ndimage.binary_dilation(core, iterations=reach)
        others = (src[..., 3] > 0.5) & ~ndimage.binary_dilation(core, iterations=r.get("dilate", 2))
        others = drop_specks(others, 6)
        keep_px = ndimage.binary_dilation(others, iterations=1)
        cleared = np.zeros_like(src)
        if sh and others.any():
            cleared = shadow_layer(src[..., 3] * others, sh)
        cleared = np.where(keep_px[..., None], src, cleared)
        out = np.where(zone[..., None], cleared, src)
        return out
    raise ValueError(f"unknown fill {fill!r}")


# ---------------------------------------------------------------------------
# crown placement and colour
# ---------------------------------------------------------------------------

def rank_transfer(crown_rgba: np.ndarray, glyph_px: np.ndarray) -> np.ndarray:
    """Colour each crown pixel from the glyph pixel at the same luminance rank.

    The master's dark anti-aliased rim (alpha below 0.9) keeps its own colour:
    recoloured from a light glyph it turns into a pale halo.
    """
    out = crown_rgba.copy()
    vis = crown_rgba[..., 3] > 0.9
    if not vis.any() or not len(glyph_px):
        return out
    order = np.argsort(lum(glyph_px[:, :3]), kind="stable")
    g = glyph_px[order]
    v = lum(crown_rgba[..., :3])[vis]
    pr = np.argsort(np.argsort(v, kind="stable"), kind="stable") / max(1, len(v) - 1)
    idx = np.clip(np.rint(pr * (len(g) - 1)).astype(int), 0, len(g) - 1)
    out[..., :3][vis] = g[idx, :3]
    return out


def tint(crown_rgba: np.ndarray, glyph_px: np.ndarray) -> np.ndarray:
    """The master's own shading in the glyph's median colour.

    For a flat glyph (one tone, e.g. vanilla's teal "not" twins) rank transfer
    has no ramp to hand out and the crown goes flat; tinting keeps the arches.
    """
    out = crown_rgba.copy()
    vis = crown_rgba[..., 3] > 0.05
    if not vis.any():
        return out
    med = np.median(glyph_px[:, :3], axis=0)
    med_l = max(float(lum(med)), 1e-6)
    L = lum(crown_rgba[..., :3])
    body = crown_rgba[..., 3] > 0.9
    # the glyph's mean tone, with the master's light and shade at reduced contrast
    new_l = med_l + (L - float(np.mean(L[body]))) * 0.6
    rgb = np.clip(med[None, None, :] * (new_l / med_l)[..., None], 0, 1)
    out[..., :3] = np.where(body[..., None], rgb, crown_rgba[..., :3])
    return out


def place(canvas_hw, layer: np.ndarray, cx: float, cy: float) -> np.ndarray:
    """Paste ``layer`` (straight RGBA or a 2-D mask) centred at (cx, cy) on an empty canvas."""
    h, w = canvas_hw
    lh, lw = layer.shape[:2]
    x0, y0 = int(round(cx - lw / 2)), int(round(cy - lh / 2))
    out = np.zeros((h, w) + layer.shape[2:])
    ys, xs = slice(max(0, y0), min(h, y0 + lh)), slice(max(0, x0), min(w, x0 + lw))
    out[ys, xs] = layer[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    return out


def build_icon(src_u8: np.ndarray, r: dict, master: np.ndarray, geo: dict):
    src = to_float(src_u8)
    h, w = src.shape[:2]
    prot = protect_mask(src, r.get("protect"))
    core, grown, thresh = glyph_masks(src, r, prot)
    if not core.any():
        raise RuntimeError(f"{r['id']}: no glyph pixels found")
    sh = fit_shadow(src, core) if r.get("fill") == "clear" else None
    field = remove_glyph(src, r, core, grown, sh)

    ys, xs = np.nonzero(core)
    gx0, gy0, gx1, gy1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    mh, mw = master.shape[:2]
    s = min((gx1 - gx0) / mw, (gy1 - gy0) / mh) * r.get("scale", 1.0)
    cw, ch = max(1, round(mw * s)), max(1, round(mh * s))
    cx = (gx0 + gx1) / 2 + r.get("dx", 0.0) * w
    cy = (gy0 + gy1) / 2 + r.get("dy", 0.0) * h

    style = r.get("crown", "painted")
    colour = r.get("colour", "transfer")
    pal = grown if r.get("palette") == "region" else core
    glyph_px = src[pal & (src[..., 3] > (0.05 if r["glyph"] == "dark" else 0.9))]
    if not len(glyph_px):
        glyph_px = src[core]

    painted = resize_premul(master, (cw, ch))
    if style == "painted":
        if colour == "transfer":
            crown = rank_transfer(painted, glyph_px)
        elif colour == "tint":
            crown = tint(painted, glyph_px)
        else:
            raise ValueError(f"{r['id']}: painted crown takes colour transfer or tint, not {colour!r}")
        layer = place((h, w), crown, cx, cy)
        if sh:
            field = over(field, shadow_layer(layer[..., 3], sh))
        out = over(layer, field)
    elif style == "stencil":
        stroke = r.get("stencil_stroke", 1.0) / s          # least arch width, target px -> master px
        st = resize_mask(crown_stencil(geo, stroke), (cw, ch))
        S = place((h, w), st, cx, cy)
        if colour == "punch":
            out = field.copy()
            out[..., 3] = field[..., 3] * (1.0 - S)
        elif colour == "flat":
            ink = np.broadcast_to(np.median(glyph_px, axis=0), (h, w, 4)).copy()
            if sh:
                field = over(field, shadow_layer(S * ink[..., 3], sh))
            # replace, not over: the crown takes the glyph's own alpha
            out = unpremul(premul(field) * (1.0 - S[..., None]) + premul(ink) * S[..., None])
        else:
            raise ValueError(f"{r['id']}: stencil crown takes colour flat or punch, not {colour!r}")
    else:
        raise ValueError(f"unknown crown style {style!r}")

    if prot.any():
        p = prot[..., None]
        out = unpremul(premul(src) * p + premul(out) * (1.0 - p))
    info = {"glyph_box": [int(gx0), int(gy0), int(gx1), int(gy1)], "crown_px": [cw, ch],
            "thresh": round(float(thresh), 3), "masks": (core, grown, prot)}
    if sh:
        info["shadow"] = {"sigma": sh["sigma"], "gain": round(sh["gain"], 3), "rms": round(sh["rms"], 4)}
    return to_u8(out), info


# ---------------------------------------------------------------------------
# recipes, preview, write, check
# ---------------------------------------------------------------------------

def load_recipes(path: Path = RECIPES) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    by_id = {}
    out = []
    for raw in data["icons"]:
        r = dict(by_id[raw["like"]]) if "like" in raw else {}
        r.update({k: v for k, v in raw.items() if k != "like"})
        by_id[r["id"]] = r
        out.append(r)
    return out


def vanilla_root(arg: str | None) -> Path:
    root = arg or os.environ.get("VANILLA_ROOT")
    if not root:
        raise SystemExit("set --game or VANILLA_ROOT to the Victoria 3 install's game folder")
    root = Path(root)
    if not (root / "gfx" / "interface").is_dir():
        raise SystemExit(f"{root} has no gfx/interface; point --game at the install's game folder")
    return root


def generate(recipes, game: Path, repo: Path):
    master = load_master(repo)
    geo = crown_geometry(master)
    for r in recipes:
        src = dds.read_top(game / r["path"])
        img, info = build_icon(src, r, master, geo)
        yield r, src, img, info


def on_bg(rgba_u8: np.ndarray, bg) -> Image.Image:
    im = Image.fromarray(rgba_u8, "RGBA")
    base = Image.new("RGBA", im.size, bg)
    base.alpha_composite(im)
    return base.convert("RGB")


def display(rgba_u8: np.ndarray, px: int, bg) -> Image.Image:
    h, w = rgba_u8.shape[:2]
    s = px / max(w, h)
    small = resize_premul(to_float(rgba_u8), (max(1, round(w * s)), max(1, round(h * s))))
    return on_bg(to_u8(small), bg)


SHEET_BG = (43, 37, 31, 255)


def mask_overlay(src_u8: np.ndarray, core, grown, prot) -> Image.Image:
    """Vanilla beside the same with the glyph core (red), its grown zone (yellow) and protect (blue)."""
    base = np.asarray(on_bg(src_u8, SHEET_BG), dtype=np.float64)
    marked = base.copy()
    marked[grown] = marked[grown] * 0.5 + np.array([255, 220, 0]) * 0.5
    marked[core] = marked[core] * 0.4 + np.array([255, 0, 0]) * 0.6
    p = prot > 0.5
    marked[p] = marked[p] * 0.5 + np.array([0, 120, 255]) * 0.5
    im = Image.fromarray(np.concatenate([base, marked], axis=1).astype(np.uint8))
    f = 4 if im.width < 400 else 1
    return im.resize((im.width * f, im.height * f), Image.NEAREST)


def contact_sheet(rows, out: Path, columns: int = 2):
    """Vanilla next to new, enlarged (2x; 1x for icons over 160 px) and at display size."""
    font = ImageFont.load_default(size=14)
    small_font = ImageFont.load_default(size=12)
    pad, label_w = 14, 210
    cells = []
    for r, src, img, _ in rows:
        h, w = src.shape[:2]
        f = 2 if max(w, h) <= 160 else 1
        big = [on_bg(x, SHEET_BG).resize((w * f, h * f), Image.NEAREST) for x in (src, img)]
        px = r.get("display", 40)
        small = [display(x, px, SHEET_BG) for x in (src, img)]
        cw = label_w + big[0].width * 2 + small[0].width * 2 + pad * 5
        ch = max(big[0].height, 60) + pad * 2
        cells.append((r, f, big, small, px, w, h, cw, ch))
    col_w = max(c[7] for c in cells)
    n_rows = (len(cells) + columns - 1) // columns
    row_h = [max(c[8] for c in cells[i * columns:(i + 1) * columns]) for i in range(n_rows)]
    sheet = Image.new("RGB", (col_w * columns, sum(row_h) + 44), SHEET_BG[:3])
    d = ImageDraw.Draw(sheet)
    d.text((pad, 14), "each cell: vanilla | new, enlarged  -  vanilla | new at display size (true pixels)",
           fill=(220, 210, 190), font=font)
    for i, (r, f, big, small, px, w, h, _cw, _ch) in enumerate(cells):
        col, row = i % columns, i // columns
        x0 = col * col_w
        y0 = 44 + sum(row_h[:row])
        rh = row_h[row]
        mid = y0 + rh // 2
        d.text((x0 + pad, mid - 18), r["id"], fill=(235, 225, 200), font=font)
        d.text((x0 + pad, mid + 2), f"{w}x{h}, shown {f}x  |  display {px} px", fill=(160, 150, 130), font=small_font)
        x = x0 + label_w
        for im in big:
            sheet.paste(im, (x, mid - im.height // 2))
            x += im.width + pad
        x += pad
        for im in small:
            sheet.paste(im, (x, mid - im.height // 2))
            x += im.width + pad
        d.rectangle([x0 + 4, y0 + 2, x0 + col_w - 4, y0 + rh - 2], outline=(70, 62, 54))
    sheet.save(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", type=Path, metavar="DIR", help="write PNGs and contact_sheet.png into DIR")
    mode.add_argument("--write", action="store_true", help="write the overrides into gfx/")
    mode.add_argument("--check", action="store_true", help="parity with vanilla + byte-identical regeneration")
    ap.add_argument("--game", help="Victoria 3 install's game folder (default: $VANILLA_ROOT)")
    ap.add_argument("--only", nargs="+", metavar="ID", help="restrict to these recipe ids")
    args = ap.parse_args(argv)

    game = vanilla_root(args.game)
    if game.resolve() == REPO.resolve():
        raise SystemExit("--game must be the vanilla install, not this repo")
    recipes = load_recipes()
    if args.only:
        unknown = set(args.only) - {r["id"] for r in recipes}
        if unknown:
            raise SystemExit(f"unknown recipe ids: {sorted(unknown)}")
        recipes = [r for r in recipes if r["id"] in args.only]

    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        rows = []
        for r, src, img, info in generate(recipes, game, REPO):
            img = dds.decode_like(game / r["path"], img)  # what the game will show
            Image.fromarray(img, "RGBA").save(args.preview / f"{r['id']}.png")
            mask_overlay(src, *info.pop("masks")).save(args.preview / f"{r['id']}_mask.png")
            print(r["id"], json.dumps(info))
            rows.append((r, src, img, info))
        contact_sheet(rows, args.preview / "contact_sheet.png")
        print("wrote", args.preview / "contact_sheet.png")
        return 0

    if args.write:
        for r, _src, img, _info in generate(recipes, game, REPO):
            dds.write_like(game / r["path"], img, REPO / r["path"])
            print("wrote", r["path"])
        return 0

    problems = []
    for r, _src, img, _info in generate(recipes, game, REPO):
        vanilla, ours = game / r["path"], REPO / r["path"]
        found = dds.check_like(vanilla, ours)
        if not found and dds.encode_like(vanilla, img) != ours.read_bytes():
            found = [f"{r['path']}: committed file differs from a fresh regeneration"]
        problems += found
        print(("FAIL " if found else "ok   ") + r["path"])
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
