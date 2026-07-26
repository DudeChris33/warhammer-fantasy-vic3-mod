#!/usr/bin/env python3
"""Author a registration record by fitting a source's silhouette to our own mask.

This is an **authoring tool**, not part of the offline gate — like
``sources.py --update-manifest``, it is run deliberately when a source's
placement needs (re)deriving, and it rewrites a committed
``tools/registration/<source>.json``. The gate reads the committed record; it
never runs this.

What it does, per the S3a plan:

1. Extract the source's land silhouette (or a registered sibling's — the climate
   map is the only Immortal Empires sibling with a measurable land signal, so it
   is the objective for the whole family).
2. **Coarse**: sweep an axis-aligned affine and keep the best two-sided IoU
   against ``tools/derived/land_sea_mask.png``. This only places the frame.
3. **Fine**: lay a lattice of control points over the source, seed their canvas
   positions through the affine, and refine each one by local coordinate descent
   on the same IoU. Immortal Empires is a playable map, not a globe, so this
   thin-plate stage is where the actual registration happens.
4. Write the record, with the fit's own numbers (IoU at each stage, how far the
   lattice moved) recorded in its ``notes`` so the committed placement carries
   the evidence for itself.

Everything it reads is committed except the source images, and every search is a
declared, finite sweep, so a re-run reproduces the same record.

Some sources have no measurable silhouette (the Old World mod map's open ocean is
the same parchment as its land, so a threshold finds the coastal shadow band
rather than the coast). Those declare ``"objective": "landmarks"`` in their seed
file and are fitted by thin-plate interpolation through hand-identified landmarks
alone — a weaker guarantee, recorded as such in the record's notes.

Usage::

    python tools/fit_registration.py --seed wh3_dlc_ie_parchment_map_english
    python tools/fit_registration.py --seed <stem> --dry-run    # fit, report, write nothing
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.interpolate import RBFInterpolator

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import parchment, raster, register, reproject, schema, segment, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
SEED_DIR = TOOLS_DIR / "registration" / "seeds"
REGISTRATION_DIR = TOOLS_DIR / "registration"
MASK_PATH = TOOLS_DIR / "derived" / "land_sea_mask.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: The globe every other source is anchored to. Landmark seeds are given as
#: pixels on *this* image and converted through its committed NE-II fit, so no
#: source's control points are ever eyeballed against the canvas directly — they
#: inherit the 0.363 px envelope fit (user decision #1: one geometric authority).
ANCHOR_SOURCE = "terraqueous_globe.jpg"


def _sweep(spec) -> np.ndarray:
    """``[start, stop, step]`` -> the inclusive candidate array it declares."""
    start, stop, step = (float(v) for v in spec)
    n = int(round((stop - start) / step)) + 1
    return start + step * np.arange(n)


def load_seed(stem: str) -> dict:
    path = SEED_DIR / f"{stem}.json"
    if not path.is_file():
        raise SystemExit(f"no seed file at {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def silhouette(spec: dict) -> tuple[np.ndarray, tuple[float, float]]:
    """The land mask used as the fitting objective, plus its scale to the master frame."""
    rgb = sources.load_source_image(spec["from"])
    m = parchment.painted_mask(rgb, exclude=[tuple(b) for b in spec.get("exclude", [])])
    keep = int(spec.get("min_component", 400))
    m = segment.drop_small_components(m, keep, wrap_x=False)
    m = ~segment.drop_small_components(~m, keep, wrap_x=False)
    return m, tuple(float(v) for v in spec.get("to_master_scale", (1.0, 1.0)))


def anchor_landmarks(seed: dict) -> tuple[np.ndarray, np.ndarray]:
    """``(source_px, canvas_px)`` for the seed's hand-identified landmarks.

    The canvas side is *computed*, never typed: each landmark records where the
    feature sits on the Terraqueous globe, and that pixel is pushed through the
    committed NE-II fit to get its canvas position.
    """
    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    fit = reproject.fit_parametric(regs[ANCHOR_SOURCE])
    src, canvas = [], []
    for lm in seed["landmarks"]:
        src.append(lm["source"])
        cx, cy = fit.to_canvas(lm["anchor"][0], lm["anchor"][1], CANVAS_W, CANVAS_H)
        canvas.append([float(cx), float(cy)])
    return np.array(src, dtype=np.float64), np.array(canvas, dtype=np.float64)


def build_alias(seed: dict, log=print) -> dict:
    """Write a ``frame_alias`` record, measuring its footprint through the parent.

    An alias carries no control points, so the only thing left to establish is
    *where on the canvas it lands* — and that is measured by actually running the
    composed warp over the canvas and taking the bounding box of the pixels that
    hit inside its crop. Declaring the footprint by hand would go stale the next
    time the parent is re-fitted, which is exactly the silent breakage the alias
    mechanism exists to avoid.
    """
    rec = dict(seed["record"])
    rec["source"] = seed["source"]
    rec["projection"] = "frame_alias"
    rec["frame_alias"] = seed["frame_alias"]
    rec["control_points"] = []
    rec["footprint"] = [0, 0, CANVAS_W, CANVAS_H]

    regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
    probe = schema.SourceRegistration.from_dict(rec, f"{seed['source']} (probe)")
    regs[probe.source] = probe
    fit = reproject.fit_alias(probe, regs)

    step = int(seed.get("footprint_step", 8))
    h, w = CANVAS_H // step, CANVAS_W // step
    gx, gy = np.meshgrid((np.arange(w) + 0.5) * step, (np.arange(h) + 0.5) * step)
    sx, sy = fit.to_source_px(gx, gy)
    x0, y0, x1, y1 = probe.crop if probe.crop is not None else (0, 0, 1e9, 1e9)
    inside = (sx >= x0) & (sx <= x1) & (sy >= y0) & (sy <= y1)
    if not inside.any():
        raise SystemExit(f"{seed['source']}: alias lands entirely outside its crop")
    ys, xs = np.nonzero(inside)
    pad = float(seed.get("footprint_pad", 0))
    rec["footprint"] = [
        max(0.0, float(xs.min()) * step - pad), max(0.0, float(ys.min()) * step - pad),
        min(float(CANVAS_W), float(xs.max() + 1) * step + pad),
        min(float(CANVAS_H), float(ys.max() + 1) * step + pad),
    ]
    log(f"alias of      {seed['frame_alias']['of']}")
    log(f"footprint     {[round(v) for v in rec['footprint']]} "
        f"({100 * inside.mean():.1f}% of canvas)")
    return rec


def fit_source(stem: str, log=print) -> dict:
    seed = load_seed(stem)
    objective = seed.get("objective", "silhouette")
    log(f"source        {seed['source']}")
    log(f"objective     {objective}")
    if objective == "frame_alias":
        return build_alias(seed, log)

    land = raster.read_mask_png(MASK_PATH)
    master_shape = tuple(seed["master_shape"])  # (h, w) of the frame control points live in

    lm_src, lm_canvas = anchor_landmarks(seed)
    log(f"landmarks     {len(lm_src)} (canvas positions derived through {ANCHOR_SOURCE})")

    info: dict = {"landmarks": int(len(lm_src))}

    if objective == "landmarks":
        # No measurable silhouette: interpolate the landmarks and stop. Exact at
        # every landmark, affine trend between them.
        src_pts = register.lattice(master_shape, seed["lattice"]["nx"], seed["lattice"]["ny"],
                                   float(seed["lattice"].get("inset", 0.02)))
        rbf = RBFInterpolator(lm_src, lm_canvas, kernel="thin_plate_spline", degree=1)
        canvas_pts = register.clamp_canvas(rbf(src_pts), CANVAS_W, CANVAS_H)
        info["method"] = "thin-plate interpolation of landmarks (no silhouette objective)"
        return _emit(seed, src_pts, canvas_pts, info, log)

    sil, to_master = silhouette(seed["silhouette"])
    log(f"silhouette    {seed['silhouette']['from']} {sil.shape} land {sil.mean():.3f}")

    # --- coarse: place the frame -----------------------------------------
    c = seed["coarse"]
    ss, cs = int(c["src_step"]), int(c["canvas_step"])
    t0 = time.time()
    best = register.coarse_affine(
        sil[::ss, ::ss], land[::cs, ::cs],
        _sweep(c["scale_x"]), _sweep(c["scale_y"]), _sweep(c["offset_x"]), _sweep(c["offset_y"]),
    )
    log(f"coarse affine IoU {best.iou:.4f}  scale {best.scale} offset {best.offset}  "
        f"({time.time() - t0:.0f}s)")
    info["coarse_iou"] = round(best.iou, 4)

    # Reduced-grid affine -> full-resolution silhouette-px -> canvas-px.
    scale = (best.scale[0] * cs / ss, best.scale[1] * cs / ss)
    offset = (best.offset[0] * cs, best.offset[1] * cs)

    # --- fine: lattice, seeded through the affine, refined by IoU --------
    #
    # The lattice is laid out on the canvas side, over the intersection of the
    # canvas with where the affine says the source lands. The source-side
    # coordinates then follow by inverting the affine, so every control point is
    # inside the canvas from the start and no clamping is needed to keep it there.
    lat = seed["lattice"]
    sh, sw = sil.shape
    box = (max(0.0, offset[0]), max(0.0, offset[1]),
           min(float(CANVAS_W), sw * scale[0] + offset[0]),
           min(float(CANVAS_H), sh * scale[1] + offset[1]))
    inset = float(lat.get("inset", 0.02))
    dx, dy = (box[2] - box[0]) * inset, (box[3] - box[1]) * inset
    box = (box[0] + dx, box[1] + dy, box[2] - dx, box[3] - dy)
    log(f"lattice box   {tuple(round(v) for v in box)}")
    seed_canvas = register.lattice_box(box, int(lat["nx"]), int(lat["ny"]))
    sil_pts = np.column_stack([(seed_canvas[:, 0] - offset[0]) / scale[0],
                               (seed_canvas[:, 1] - offset[1]) / scale[1]])
    src_pts = sil_pts * np.array(to_master)

    # Stages coarse-to-fine: a big correction does not need a fine scoring grid,
    # and a fine correction cannot be seen on a coarse one. Scoring cost goes as
    # 1/step^2, so doing the long-range passes cheaply is most of the saving.
    canvas_pts, iou = seed_canvas, 0.0
    t0 = time.time()
    for i, stage in enumerate(seed["refine"]["stages"]):
        log(f"  stage {i + 1}: step {stage['step']} radii {stage['radii']}")
        canvas_pts, iou = register.refine(
            src_pts, canvas_pts, sil, land, src_scale=to_master,
            step=int(stage["step"]), radii=tuple(float(v) for v in stage["radii"]),
            passes=int(stage.get("passes", 1)), log=log,
            bounds=(float(CANVAS_W), float(CANVAS_H)))
    log(f"refined IoU   {iou:.4f}  ({time.time() - t0:.0f}s)")

    info["method"] = "coarse affine + thin-plate lattice refined on two-sided silhouette IoU"
    info["refined_iou"] = round(float(iou), 4)
    # Recheck the finished warp at full canvas resolution: refinement rejects
    # folds on a reduced grid, so a fold narrower than that grid could survive.
    final = register.warp_mask(src_pts, canvas_pts, sil, land.shape, to_master, step=8)
    info["folded_fraction"] = round(final.folded, 5)
    log(f"fold check    {100 * final.folded:.3f}% of the covered canvas folds "
        f"(checked at 8 px, refined at {seed['refine']['stages'][-1]['step']} px)")
    info["lattice"] = f"{lat['nx']}x{lat['ny']}"
    seed_canvas = np.asarray(seed_canvas)
    info["move"] = register.residual_report(src_pts, canvas_pts, seed_canvas)

    # How well do the hand-identified landmarks survive the fit? They took no
    # part in the refinement, so this is an independent check rather than a
    # restatement of the objective.
    rbf = RBFInterpolator(src_pts, canvas_pts, kernel="thin_plate_spline", degree=1)
    lm_pred = rbf(lm_src)
    d = np.hypot(*(lm_pred - lm_canvas).T)
    info["landmark_check_px"] = {"mean": round(float(d.mean()), 1),
                                 "max": round(float(d.max()), 1)}
    log(f"landmark check mean {d.mean():.0f} px, max {d.max():.0f} px (not used in the fit)")
    return _emit(seed, src_pts, canvas_pts, info, log)


def _emit(seed: dict, src_pts: np.ndarray, canvas_pts: np.ndarray, info: dict, log) -> dict:
    rec = dict(seed["record"])
    rec["source"] = seed["source"]
    rec["projection"] = "control_point_warp"
    # The footprint is *measured* from where the fit actually put the source,
    # not declared up front — a hand-written box would go stale the moment the
    # control points moved, and a stale footprint silently truncates the layer.
    pad = float(seed.get("footprint_pad", 64))
    rec["footprint"] = [
        max(0.0, float(canvas_pts[:, 0].min()) - pad),
        max(0.0, float(canvas_pts[:, 1].min()) - pad),
        min(float(CANVAS_W), float(canvas_pts[:, 0].max()) + pad),
        min(float(CANVAS_H), float(canvas_pts[:, 1].max()) + pad),
    ]
    rec["notes"] = rec.get("notes", "").rstrip() + " FIT: " + json.dumps(info, sort_keys=True)
    rec["control_points"] = register.to_records(
        src_pts, canvas_pts, lambda i: f"lattice {i}")
    log(f"control points {len(rec['control_points'])}")
    return rec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", required=True, help="seed stem under tools/registration/seeds/")
    p.add_argument("--dry-run", action="store_true", help="fit and report, write nothing")
    args = p.parse_args(argv)

    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_heightmap.py first")

    rec = fit_source(args.seed)
    out = REGISTRATION_DIR / f"{load_seed(args.seed).get('record_stem', args.seed)}.json"
    if args.dry_run:
        print(f"(dry run — would write {out})")
        return 0
    out.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    # Fail loudly here rather than at the next gate run.
    schema.load_registration_file(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
