#!/usr/bin/env python3
"""Dev-only (board #8210 follow-up): smooth the pixel-stepped borders of a CR border proposal.

Reads ``scratchpad/<landmass>_borders_proposal_canvas.png`` (pure magenta 1 px lines, written by
``propose_cr_borders.py``) and the land/sea mask, recovers the states as the land components the
lines cut out, smooths the state-label field and re-rasterizes 1 px lines. Writes only
``scratchpad/``; never a source, the ``borders`` layer or a generated map file.

Method (deterministic, no RNG): each state's indicator is Gaussian-blurred *within scope only*
(normalized convolution) and every scope pixel takes the strongest label. The field never leaves
scope, so a border still ends on the coast it ended on; a triple junction drifts by a fraction of
sigma. Closing lines (scope edge against unlined land) are kept pixel-for-pixel. A state that the
blur would split keeps only its main piece, the rest is handed to the neighbour it touches most.

Usage::

    python mapgen/smooth_cr_borders.py --landmass ulthuan [--sigma 4]

Outputs: ``<landmass>_borders_smooth_canvas.png``, ``_smooth_review.png`` (before in orange, after
in magenta), ``_borders_smooth.json``. Exit 0 on a passing round trip, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import cells, cr_partition  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"
MAGENTA = (255, 0, 255)
DEFAULT_SIGMA = 4.0
FRAGMENT_PX = 300           # a state piece below this is a sliver behind a line neck


# ---------------------------------------------------------------------------
# Pure core (shared with the run_fixture self-check)
# ---------------------------------------------------------------------------

def recover_labels(lines: np.ndarray, land: np.ndarray, box_mask: np.ndarray):
    """``(labels, scope, closing)`` from a line raster.

    States are the 4-connected components of ``land & ~lines`` that lie wholly inside
    ``box_mask``; line pixels join the nearest state; line pixels 4-adjacent to land outside
    scope are the closing line and are returned separately (and left out of scope).
    """
    free = land & ~lines
    comp, n = ndimage.label(free)               # 4-connectivity, as the generator's fill
    outside = np.unique(comp[free & ~box_mask])
    comp[np.isin(comp, outside)] = 0
    # A state is a component the lines touch; a lone islet with no line is left to the generator.
    touched = np.unique(comp[ndimage.binary_dilation(lines) & (comp > 0)])
    comp[~np.isin(comp, touched)] = 0
    # A thin neck made wholly of its own line pixels leaves a sliver of the same state behind it.
    sizes = np.bincount(comp.ravel(), minlength=comp.max() + 1)
    frag = (comp > 0) & (sizes[comp] < FRAGMENT_PX)
    comp[frag] = 0
    states = np.zeros(comp.shape, dtype=np.int32)
    for new, old in enumerate((v for v in np.unique(comp) if v > 0), 1):
        states[comp == old] = new
    open_land = free & (states == 0)
    near = np.zeros(land.shape, dtype=bool)
    near[:, 1:] |= open_land[:, :-1]
    near[:, :-1] |= open_land[:, 1:]
    near[1:] |= open_land[:-1]
    near[:-1] |= open_land[1:]
    closing = lines & land & near & box_mask
    line_land = (lines | frag) & land & ~closing & box_mask
    # nearest state for line pixels
    if states.any():
        _, (iy, ix) = ndimage.distance_transform_edt(states == 0, return_indices=True)
        filled = states[iy, ix]
    else:
        filled = states
    labels = np.where(line_land, filled, states).astype(np.int32)
    scope = labels > 0
    return labels, scope, closing


def smooth_labels(labels: np.ndarray, scope: np.ndarray, sigma: float) -> np.ndarray:
    """Argmax of per-label Gaussian blurs normalized over scope; ties go to the lower label."""
    ids = [int(v) for v in np.unique(labels) if v > 0]
    if sigma <= 0 or len(ids) < 2:
        return labels.copy()
    w = ndimage.gaussian_filter(scope.astype(np.float32), sigma, mode="constant")
    w = np.maximum(w, 1e-6)
    best = np.full(labels.shape, -1.0, dtype=np.float32)
    out = np.zeros(labels.shape, dtype=np.int32)
    for i in ids:
        g = ndimage.gaussian_filter((labels == i).astype(np.float32), sigma, mode="constant") / w
        take = g > best
        out[take] = i
        best[take] = g[take]
    out[~scope] = 0
    return out


def tidy(labels: np.ndarray, scope: np.ndarray) -> np.ndarray:
    """Keep each label's largest 4-connected piece; hand stray pieces to the touching label."""
    out = labels.copy()
    for _ in range(4):
        stray = np.zeros(out.shape, dtype=bool)
        for i in (int(v) for v in np.unique(out) if v > 0):
            comp, n = ndimage.label(out == i)
            if n > 1:
                sizes = ndimage.sum(np.ones_like(comp), comp, range(1, n + 1))
                keep = 1 + int(np.argmax(sizes))
                stray |= (comp > 0) & (comp != keep)
        if not stray.any():
            break
        base = np.where(stray, 0, out)
        _, (iy, ix) = ndimage.distance_transform_edt(base == 0, return_indices=True)
        out = np.where(stray, base[iy, ix], out)
        out[~scope] = 0
    return out


def smooth_lines(lines: np.ndarray, land: np.ndarray, box_mask: np.ndarray, sigma: float):
    """Whole pipeline on one crop: ``(new_lines, labels, new_labels, scope, closing)``."""
    labels, scope, closing = recover_labels(lines, land, box_mask)
    new = tidy(smooth_labels(labels, scope, sigma), scope)
    new_lines = cr_partition.lines_from_labels(new, scope) | closing
    return new_lines, labels, new, scope, closing


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import propose_cr_borders as pcb
    from scipy import ndimage as ndi
    import generate_provinces as gp

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--landmass", required=True)
    ap.add_argument("--sigma", type=float, default=DEFAULT_SIGMA)
    ap.add_argument("--in-dir", type=Path, default=SCRATCH_DIR)
    ap.add_argument("--out-dir", type=Path, default=SCRATCH_DIR)
    args = ap.parse_args(argv)
    name = args.landmass
    src_json = args.in_dir / f"{name}_borders_proposal.json"
    src_png = args.in_dir / f"{name}_borders_proposal_canvas.png"
    if not src_png.is_file() or not src_json.is_file():
        raise SystemExit(f"missing {src_png.name} / {src_json.name}: run propose_cr_borders.py "
                         f"--landmass {name} first")
    rep = json.loads(src_json.read_text(encoding="utf-8"))
    box = [int(v) for v in rep["params"]["box"]]
    replace = bool(rep.get("replace_existing"))

    layers = pcb.Layers()
    land = layers.land
    with Image.open(src_png) as im:
        prop = np.array(im.convert("RGBA"))[..., 3] > 0
    bx0, by0, bx1, by1 = box
    P = pcb.PAD
    crop_box = (bx0 - P, max(0, by0 - P), bx1 + P, min(pcb.CANVAS_H, by1 + P))
    cx0, cy0, cx1, cy1 = crop_box
    land_c = cr_partition.crop_box(land, crop_box, wrap=True)
    lines_c = cr_partition.crop_box(prop, crop_box, wrap=True)
    box_mask = np.zeros(land_c.shape, dtype=bool)
    box_mask[by0 - cy0:by1 - cy0, bx0 - cx0:bx1 - cx0] = True

    new_lines, labels, new, scope, closing = smooth_lines(lines_c, land_c, box_mask, args.sigma)
    n_states = int(len([v for v in np.unique(labels) if v > 0]))
    n_new = int(len([v for v in np.unique(new) if v > 0]))
    n_island = int(rep.get("states", {}).get("island_only", 0))
    print(f"{name}: {n_states} lined states recovered, {n_new} after smoothing"
          f" (+ {n_island} island-only state(s) in the proposal, which carry no line and are "
          f"not counted here; proposal total {rep.get('states', {}).get('count', '?')})", flush=True)

    # Round trip: the generator's own region stage on existing + smoothed proposal.
    smooth_full = np.zeros(land.shape, dtype=bool)
    pcb.paste_crop(smooth_full, new_lines & box_mask, cx0, cy0)
    composite = layers.magenta.copy()
    if replace:
        erase_c = ndi.binary_erosion(scope | closing, iterations=gp.LINE_DILATE + 1)
        erase = np.zeros(land.shape, dtype=bool)
        pcb.paste_crop(erase, erase_c, cx0, cy0)
        composite &= ~erase
    composite |= smooth_full
    reg1, _ = pcb.existing_regions(layers, composite, None)
    reg_c = cr_partition.crop_box(reg1, crop_box, wrap=True)
    gen_ids = [int(r) for r in np.unique(reg_c[scope]) if r > 0]
    gen = np.zeros(land_c.shape, dtype=np.int32)
    off = ndi.distance_transform_edt(~(scope | closing))
    leaks = []
    for r in gen_ids:
        m = reg_c == r
        far = float((m & (off > gp.LINE_DILATE + 1)).sum()) / float(m.sum())
        gen[m & scope] = r
        if far > 0.02:
            leaks.append({"region": r, "beyond_frac": round(far, 3)})
    pairs, only_new, only_gen = pcb.match_regions(new, gen, 0.9)
    passed = bool(not leaks and len(pairs) == n_new == n_states == len(gen_ids))
    print(f"round trip: {n_new} states, {len(gen_ids)} generated, {len(pairs)} matched at "
          f"IoU>=0.9, {len(leaks)} leaking -> {'PASS' if passed else 'FAIL'}", flush=True)

    # Outputs
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    rgba = np.zeros((pcb.CANVAS_H, pcb.CANVAS_W, 4), dtype=np.uint8)
    rgba[smooth_full] = (*MAGENTA, 255)
    Image.fromarray(rgba).save(out / f"{name}_borders_smooth_canvas.png")
    ys, xs = np.nonzero(scope | closing)
    y0, y1 = max(0, ys.min() - 20), min(land_c.shape[0], ys.max() + 21)
    x0, x1 = max(0, xs.min() - 20), min(land_c.shape[1], xs.max() + 21)
    bg = pcb._globe_crop(crop_box).astype(np.uint8)
    bg[pcb._coast(land_c)] = (0, 255, 255)
    S = 3
    panels = []
    for ln in (lines_c, new_lines):
        im = bg.copy()
        im[ln] = MAGENTA
        panels.append(Image.fromarray(im[y0:y1, x0:x1]).resize(((x1 - x0) * S, (y1 - y0) * S), Image.NEAREST))
    both = bg.copy()
    both[lines_c] = (255, 140, 0)
    both[new_lines] = MAGENTA
    over = Image.fromarray(both[y0:y1, x0:x1]).resize(((x1 - x0) * S, (y1 - y0) * S), Image.NEAREST)
    sheet = Image.new("RGB", (panels[0].width * 2 + 10, panels[0].height * 2 + 10), (0, 0, 0))
    sheet.paste(panels[0], (0, 0))
    sheet.paste(panels[1], (panels[0].width + 10, 0))
    sheet.paste(over, (0, panels[0].height + 10))
    sheet.save(out / f"{name}_borders_smooth_review.png")
    (out / f"{name}_borders_smooth.json").write_text(json.dumps({
        "landmass": name, "sigma": args.sigma, "states": n_states, "island_only": n_island,
        "line_px": {"before": int(lines_c.sum()), "after": int(new_lines.sum())},
        "round_trip": {"generated": len(gen_ids), "matched_iou_0.9": len(pairs), "leaks": leaks,
                       "unmatched_smoothed": only_new, "unmatched_generated": only_gen,
                       "passed": passed}}, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
