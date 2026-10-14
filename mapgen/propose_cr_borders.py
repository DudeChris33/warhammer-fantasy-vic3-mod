#!/usr/bin/env python3
"""Dev-only (board #8210): propose state borders for a landmass from ChaosRobie's region partition.

Places the CR whole-world lookup (``cr_combi_expanded_lookup.tga``) on our canvas **by itself**
(Chris does not mark anchor dots, 2026-10-14) and uses its regions as a *guide* to cut the
landmass's land into states that follow our coast, rivers and impassable paint. CR's lines are
not reproduced. Where the automatic placement is off, Claude adds landmarks of its own to
``mapgen/config/cr_border_landmasses.json`` (``placed_by``, ``feature``) and runs again.

Everything is a proposal: it writes only ``scratchpad/`` and never a source, a registration
record or a generated map file. The ``borders`` layer stays Chris's.

Usage::

    python mapgen/propose_cr_borders.py --landmass ulthuan --replace-existing --placement-review
    python mapgen/propose_cr_borders.py --landmass ulthuan --replace-existing --target 22

Outputs, under ``scratchpad/``: ``<landmass>_borders_proposal_canvas.png`` (pure magenta 1 px on a
transparent 8192x3616 canvas), ``_review.png``, ``_states.csv`` and ``.json`` (inputs' SHA-256,
placement, dot check, hull, snap, round-trip, compare); ``--placement-review`` adds
``_placement_review.png`` and ``_landmark_sheet.png``.

Exit 0 on a passing round trip (or a clean skip when the dataset is absent), 1 on a failed one.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import cells, cr_partition, land_provinces, raster, schema, scope_additions  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402
import generate_provinces as gp  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"  # QA renders and previews; gitignored at the repo root
CONFIG_PATH = TOOLS_DIR / "config" / "cr_border_landmasses.json"
MASK_PATH = TOOLS_DIR / "derived" / "land_sea_mask.png"
REGISTRATION_DIR = TOOLS_DIR / "registration"

DATASET_DIR = REPO_ROOT / "sources" / "cr_immortal_empires_expanded"
LOOKUP_TGA = DATASET_DIR / "campaign_maps" / "cr_combi_expanded_map_1" / "cr_combi_expanded_lookup.tga"
REGIONS_TSV = DATASET_DIR / "db" / "regions_tables" / "!cr_map_expansion.tsv"
LOC_TSV = DATASET_DIR / "text" / "db" / "cr_new_combi_regions.loc.tsv"
GLOBE_SOURCE = "terraqueous_globe_reprojected.png"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X
PAD = 64                      # the crop around the box; warp_cells clips to it
MAGENTA = (255, 0, 255)
EDGE_CUT_MAX = 0.15
#: Landmasses that have an accepted dot registration, used only to SCORE the placement.
DOT_RECORDS = {"ulthuan": "cr_combi_expanded_map_ulthuan"}


def log(msg: str, t0: float | None = None) -> None:
    stamp = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(f"{stamp}{msg}", flush=True)


class ConfigError(SystemExit):
    pass


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: Path, name: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if name not in data:
        raise ConfigError(f"{path.name}: no landmass {name!r} (have {', '.join(sorted(data))})")
    c = dict(data[name])
    for key in ("box", "cr_box"):
        if key not in c or len(c[key]) != 4:
            raise ConfigError(f"{path.name}.{name}: {key} must be [x0, y0, x1, y1]")
    x0, y0, x1, y1 = c["box"]
    if not (0 <= x0 < x1 and 0 <= y0 < y1 <= CANVAS_H and x1 - x0 <= CANVAS_W):
        raise ConfigError(f"{path.name}.{name}: box {c['box']} is not on the canvas")
    c.setdefault("target", None)
    c.setdefault("min_state_px", 1500)
    c.setdefault("max_state_px", None)
    c.setdefault("snap_px", 8)
    c.setdefault("snap_follow_frac", 0.6)
    c.setdefault("fit", {})
    c.setdefault("landmarks", [])
    for i, lm in enumerate(c["landmarks"]):
        for k in ("name", "source", "canvas", "feature"):
            if not lm.get(k):
                raise ConfigError(f"{path.name}.{name}.landmarks[{i}]: needs {k!r}")
    return c


# ---------------------------------------------------------------------------
# Generator stage, mirrored (never restated): generate_provinces.py:405-421
# ---------------------------------------------------------------------------

class Layers:
    """Everything the generator's region stage reads, loaded once."""

    def __init__(self) -> None:
        self.land = raster.read_mask_png(MASK_PATH)
        if self.land.shape != (CANVAS_H, CANVAS_W):
            raise SystemExit(f"{MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}")
        self.borders = self._read(gp.STATE_REGIONS_SOURCE, required=True)
        self.rivers = self._read(sources_mod.source_ref("rivers"), required=True)
        self.impassable = self._read(gp.IMPASSABLE_SOURCE, required=False)
        ov = self._read(gp.ISLAND_OVERRIDES_SOURCE, required=False)
        self.island_overrides = (land_provinces.island_override_zones(ov[..., :3], self.land, WRAP_X)
                                 if ov is not None else np.zeros(self.land.shape, dtype=np.int32))
        # The borders layer is read by name: any paint on it is a border, whatever its colour.
        painted = self.borders[..., 3] > 0
        self.magenta = painted | land_provinces.magenta_lines(self.borders[..., :3])

    @staticmethod
    def _read(ref: str, required: bool):
        arr = sources_mod.read_source_rgba(ref, allow_empty=not required)
        if arr is None:
            if required:
                raise SystemExit(f"missing source {ref} - this tool needs sources/ locally")
            return None
        if arr.shape[:2] != (CANVAS_H, CANVAS_W):
            raise SystemExit(f"{ref}: expected {CANVAS_W}x{CANVAS_H}, got {arr.shape[1]}x{arr.shape[0]}")
        return arr

    def features(self) -> np.ndarray:
        """Rivers (pure blue) plus the edge of impassable tracts, both on land."""
        from worldgen import river_network
        feat = river_network.blue_lines(self.rivers[..., :3]) & self.land
        if self.impassable is not None:
            imp = land_provinces.impassable_mask(self.impassable, self.land)
            edge = imp & ~ndimage.binary_erosion(imp)
            feat |= edge
        return feat

    def impassable_mask(self) -> np.ndarray:
        if self.impassable is None:
            return np.zeros(self.land.shape, dtype=bool)
        return land_provinces.impassable_mask(self.impassable, self.land)


def existing_regions(layers: Layers, magenta: np.ndarray, t0: float):
    """The generator's own region stage on a magenta line raster: ``(reg, drawn_zone)``.

    ``generate_provinces.py:405-421`` is the authority; the constants are imported from it.
    """
    drawn = np.zeros(layers.land.shape + (3,), dtype=np.uint8)
    drawn[magenta] = MAGENTA
    reg = land_provinces.regions(layers.land, drawn, gp.LINE_DILATE, gp.MERGE_FLOOR, WRAP_X,
                                 island_overrides=layers.island_overrides)
    if gp.LAND_REGION_MERGES_CONFIG.is_file():
        merges = schema.load_land_region_merges(gp.LAND_REGION_MERGES_CONFIG,
                                                canvas=(CANVAS_W, CANVAS_H))
        reg = land_provinces.apply_land_region_merges(reg, merges)
    mag = land_provinces.magenta_lines(drawn)
    dmask = land_provinces.drawn_mask(layers.land, mag, WRAP_X)
    if gp.IN_SCOPE_ADDITIONS_CONFIG.is_file():
        additions = scope_additions.load(gp.IN_SCOPE_ADDITIONS_CONFIG, (CANVAS_W, CANVAS_H))
        added = scope_additions.region_realms(np.where(layers.land, reg, 0), additions)
        dmask = dmask | (np.isin(reg, sorted(added)) & layers.land)
    log(f"  generator region stage: {int(reg.max())} regions", t0)
    return reg, dmask


# ---------------------------------------------------------------------------
# CR names
# ---------------------------------------------------------------------------

def read_cr_names(palette: np.ndarray) -> dict[int, tuple[str, str]]:
    """``{label (palette index + 1): (key, display name)}`` for the keyed palette colours.

    Keys come from the regions table (``unnamed colour group_1`` is upper-case hex), names from
    ``regions_onscreen_<key>`` in the loc table. The rest are vanilla IE regions whose names live
    in the game's own data files; they stay ``cr_idx_<n>``.
    """
    by_hex: dict[str, str] = {}
    for i, line in enumerate(REGIONS_TSV.read_text(encoding="utf-8").splitlines()):
        cols = line.split("\t")
        if i < 2 or len(cols) < 6 or not cols[0] or cols[0].startswith("#"):
            continue
        by_hex[cols[5].strip().upper()] = cols[0]
    names: dict[str, str] = {}
    for line in LOC_TSV.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if len(cols) >= 2 and cols[0].startswith("regions_onscreen_"):
            names[cols[0][len("regions_onscreen_"):]] = cols[1]
    out: dict[int, tuple[str, str]] = {}
    for i, rgb in enumerate(palette):
        key = by_hex.get("%02X%02X%02X" % tuple(int(v) for v in rgb))
        if key:
            out[i + 1] = (key, names.get(key, key))
    return out


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def to_canvas_x(x: float, box_x0: int) -> float:
    """A canvas x written in 0..W, unwrapped to sit at or past ``box_x0``."""
    return x + CANVAS_W if x < box_x0 else x


def paste_crop(canvas: np.ndarray, crop: np.ndarray, x0: int, y0: int) -> None:
    """OR (bool) or assign a crop into the canvas at ``(x0, y0)``, columns modulo the width."""
    h, w = crop.shape[:2]
    cols = np.arange(x0, x0 + w) % CANVAS_W
    if canvas.dtype == bool:
        canvas[y0:y0 + h][:, cols] |= crop
    else:
        canvas[y0:y0 + h][:, cols] = crop


def match_regions(a: np.ndarray, b: np.ndarray, floor: float):
    """One-to-one best-IoU matching of label rasters ``a`` and ``b``; returns
    ``(pairs [(la, lb, iou)], unmatched_a, unmatched_b)``. Greedy by IoU, deterministic."""
    la = [int(v) for v in np.unique(a) if v > 0]
    lb = [int(v) for v in np.unique(b) if v > 0]
    cand = []
    for x in la:
        mx = a == x
        hit = np.unique(b[mx])
        for y in (int(v) for v in hit if v > 0):
            my = b == y
            inter = int((mx & my).sum())
            union = int((mx | my).sum())
            if inter:
                cand.append((inter / union, x, y))
    cand.sort(key=lambda t: (-t[0], t[1], t[2]))
    ua, ub, pairs = set(la), set(lb), []
    for iou, x, y in cand:
        if iou < floor:
            break
        if x in ua and y in ub:
            pairs.append((x, y, round(iou, 3)))
            ua.discard(x)
            ub.discard(y)
    return pairs, sorted(ua), sorted(ub)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--landmass", required=True)
    ap.add_argument("--replace-existing", action="store_true",
                    help="take all land in the box and erase the existing magenta strictly inside "
                         "it from the composite (the Ulthuan proof)")
    ap.add_argument("--target", type=int, default=None, help="merge down to about this many states")
    ap.add_argument("--placement-review", action="store_true",
                    help="also write the placement review and the landmark sheet")
    ap.add_argument("--config", type=Path, default=CONFIG_PATH)
    ap.add_argument("--out-dir", type=Path, default=SCRATCH_DIR)
    args = ap.parse_args(argv)
    t0 = time.time()

    if not LOOKUP_TGA.is_file():
        print(f"clean skip: {DATASET_DIR} is absent on this device")
        return 0
    cfg = load_config(args.config, args.landmass)
    name = args.landmass
    target = args.target if args.target is not None else cfg["target"]
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    # --- inputs --------------------------------------------------------------------
    raw = LOOKUP_TGA.read_bytes()
    idx, palette = cr_partition.decode_lookup(raw)
    void = cr_partition.void_index(palette)
    names = read_cr_names(palette)
    log(f"lookup {idx.shape[1]}x{idx.shape[0]}, {len(palette)} regions, {len(names)} keyed, void {void}", t0)
    layers = Layers()
    land = layers.land
    log(f"layers read; land {100 * land.mean():.1f}%", t0)

    bx0, by0, bx1, by1 = (int(v) for v in cfg["box"])
    cx0, cy0, cx1, cy1 = bx0 - PAD, max(0, by0 - PAD), bx1 + PAD, min(CANVAS_H, by1 + PAD)
    crop_box = (cx0, cy0, cx1, cy1)
    ox, oy = bx0 - cx0, by0 - cy0           # box origin inside the crop
    crop_shape = (cy1 - cy0, cx1 - cx0)
    land_crop = cr_partition.crop_box(land, crop_box, wrap=True)
    box_mask = np.zeros(crop_shape, dtype=bool)
    box_mask[oy:oy + (by1 - by0), ox:ox + (bx1 - bx0)] = True

    # --- same-rule silhouettes and the edge-cut check ---------------------------------
    fit_p = cfg["fit"]
    minc = int(fit_p.get("min_component", cr_partition.DEFAULT_FIT["min_component"]))
    ours = cr_partition.box_land(cr_partition.crop_box(land, cfg["box"], wrap=True), minc)
    rx0, ry0, rx1, ry1 = (int(v) for v in cfg["cr_box"])
    src_labels = cr_partition.to_parchment_frame(idx, void, cfg["cr_box"])
    theirs = cr_partition.box_land(src_labels > 0, minc)
    for what, m in (("box (canvas)", ours), ("cr_box (parchment)", theirs)):
        cut = cr_partition.edge_cut(m)
        bad = {k: v for k, v in cut.items() if v > EDGE_CUT_MAX}
        if bad:
            raise ConfigError(
                f"{name}: {what} is cut across land on its "
                f"{', '.join(f'{k} edge ({v:.0%})' for k, v in bad.items())}; "
                f"move the box so its edges run over sea or narrow necks (limit {EDGE_CUT_MAX:.0%})")

    # --- placement -----------------------------------------------------------------
    lms = [cr_partition.Landmark(
        lm["name"],
        (float(lm["source"][0]) - rx0, float(lm["source"][1]) - ry0),
        (to_canvas_x(float(lm["canvas"][0]), bx0) - bx0, float(lm["canvas"][1]) - by0),
        lm["feature"]) for lm in cfg["landmarks"]]
    log(f"placing CR land on ours ({len(lms)} Claude landmark(s)) ...", t0)
    src_pts, cvs_pts, info = cr_partition.fit_placement(theirs, ours, lms, fit_p, lambda m: log(m, t0))
    log(f"  placement IoU {info['iou']:.4f} (affine {info['coarse_iou']:.4f}), "
        f"folds {100 * info['folded_fraction']:.3f}%, anisotropy p99 {info['anisotropy_p99']}", t0)
    if info.get("warning"):
        log(f"WARNING: {info['warning']}", t0)
    if info["coarse_iou"] < 0.5:
        log("WARNING: affine IoU is below 0.5; this landmass needs landmarks before it is usable", t0)

    # Dot check: Chris's accepted dots only SCORE the placement, they never enter it.
    dot_check = None
    rec_name = DOT_RECORDS.get(name)
    if rec_name and (REGISTRATION_DIR / f"{rec_name}.json").is_file():
        rec = schema.load_registration_file(REGISTRATION_DIR / f"{rec_name}.json")
        pts = [(cp.source, cp.canvas) for cp in rec.control_points
               if rx0 <= cp.source[0] <= rx1 and ry0 <= cp.source[1] <= ry1]
        if pts:
            s = np.array([[p[0][0] - rx0, p[0][1] - ry0] for p in pts])
            want = np.array([p[1] for p in pts])
            scale, off = info["scale"], info["offset"]
            aff = np.column_stack([s[:, 0] * scale[0] + off[0] + bx0, s[:, 1] * scale[1] + off[1] + by0])
            full = cr_partition.forward_map(src_pts, cvs_pts, s) + np.array([bx0, by0])

            def stats(got):
                d = np.hypot(*(got - want).T)
                return {"median": round(float(np.median(d)), 1), "mean": round(float(d.mean()), 1),
                        "max": round(float(d.max()), 1)}
            dot_check = {"dots": len(pts), "affine": stats(aff), "with_landmarks": stats(full)}
            log(f"  dot check over {len(pts)} dots: affine median {dot_check['affine']['median']} px, "
                f"with landmarks {dot_check['with_landmarks']['median']} px (max "
                f"{dot_check['with_landmarks']['max']})", t0)

    # --- the generator's view of what exists ----------------------------------------
    log("generator region stage on the existing borders ...", t0)
    reg0, dmask0 = existing_regions(layers, layers.magenta, t0)
    reg_crop = cr_partition.crop_box(reg0, crop_box, wrap=True)
    dmask_crop = cr_partition.crop_box(dmask0, crop_box, wrap=True)

    # --- project the partition, then fit it to our land ----------------------------------
    rec = cr_partition.placement_record(f"cr_partition:{name}", src_pts, cvs_pts + np.array([ox, oy]),
                                        crop_shape, src_labels.shape)
    lab, hull = cells.warp_cells(rec, {}, src_labels, crop_shape)
    log(f"  warped CR labels: hull covers {int(hull.sum()):,} px", t0)

    region_drawn = np.zeros(int(reg0.max()) + 1, dtype=bool)
    for r in np.unique(reg_crop[land_crop]):
        if r > 0:
            m = reg_crop == r
            region_drawn[r] = bool(dmask_crop[m & land_crop].mean() > 0.5)
    drawn_zone = region_drawn[reg_crop] & land_crop
    scope = land_crop & box_mask & hull
    if not args.replace_existing:
        scope &= ~drawn_zone
    if not scope.any():
        raise SystemExit(f"{name}: no undrawn land inside the box and the fitted hull "
                         f"(use --replace-existing to redraw drawn land)")
    log(f"  scope {int(scope.sum()):,} px", t0)

    # Hull report: undrawn land of regions touching scope that sits outside the hull or box.
    touching = [int(r) for r in np.unique(reg_crop[scope]) if r > 0]
    in_touch = np.isin(reg_crop, touching) & land_crop
    leftover = in_touch & ~scope & ~drawn_zone
    blobs = []
    comp, n = ndimage.label(leftover)
    for c in range(1, n + 1):
        ys, xs = np.nonzero(comp == c)
        if xs.size >= 200:
            blobs.append({"bbox": [int(xs.min()) + cx0, int(ys.min()) + cy0,
                                   int(xs.max()) + cx0 + 1, int(ys.max()) + cy0 + 1], "px": int(xs.size)})
    blobs.sort(key=lambda b: -b["px"])

    cr_raw = np.where(scope, lab, 0).astype(np.int32)
    labels = cells.prune_slivers(cr_raw, False, 0.35)
    # Land the warp did not cover still needs states: grow from the nearest, as the label stage does.
    labels = cells.fill_nearest(labels, scope, wrap_x=False, pad=0) if labels.any() else labels
    labels[~scope] = 0
    labels = cells.split_disconnected(labels, False)
    n_cr = int(len(np.unique(cr_raw[cr_raw > 0])))
    log(f"  {n_cr} CR regions reach scope -> {int(labels.max())} pieces after prune/fill", t0)

    features = layers.features()
    feat_crop = cr_partition.crop_box(features, crop_box, wrap=True) & land_crop
    labels, snap_report = cr_partition.snap_to_features(
        labels, scope, feat_crop, int(cfg["snap_px"]), float(cfg["snap_follow_frac"]))
    labels = cells.split_disconnected(labels, False)
    before_merge = int(labels.max())
    labels = cells.merge_small(labels, int(cfg["min_state_px"]), False)
    labels = cells.split_disconnected(labels, False)
    # An islet below the floor with no land neighbour cannot merge and would be a state of its
    # own; it gets no line, so it is left to the generator (which treats it as it always has)
    # and taken out of scope, and listed.
    nb = cells._neighbour_pairs(labels, False)
    ar = np.bincount(labels.ravel())
    islets = [i for i in range(1, len(ar)) if 0 < ar[i] < int(cfg["min_state_px"]) and not nb.get(i)]
    for i in islets:
        scope &= labels != i
        labels[labels == i] = 0
    labels = cells.renumber(labels)
    log(f"  {len(islets)} sub-floor islet(s) with no land neighbour left to the generator", t0)
    if target:
        labels = cells.merge_to_target(labels, int(target), False, log=lambda m: log(m, t0))
    split = 0
    if cfg["max_state_px"]:
        pre = int(labels.max())
        labels = cells.split_large(labels, int(cfg["max_state_px"]), int(cfg["max_state_px"]) // 2, False)
        split = int(labels.max()) - pre
    labels = cells.renumber(labels)
    areas = np.bincount(labels.ravel())[1:]
    med = float(np.median(areas)) if areas.size else 0.0
    flagged = [int(i + 1) for i, a in enumerate(areas) if med and a > 2.5 * med]
    n_states = int(labels.max())
    log(f"  {n_states} states (merged {max(0, before_merge - n_states)}, split {split}, "
        f"flagged {len(flagged)} over 2.5x the median {med:,.0f} px)", t0)

    # --- lines, round trip -----------------------------------------------------------------
    open_land = in_touch & ~scope
    lines = cr_partition.lines_from_labels(labels, scope)
    closing = cr_partition.closing_line(scope, open_land)
    proposal_crop = (lines | closing) & box_mask
    proposal = np.zeros(land.shape, dtype=bool)
    paste_crop(proposal, proposal_crop, cx0, cy0)

    composite = layers.magenta.copy()
    if args.replace_existing:
        erase_crop = ndimage.binary_erosion(scope, iterations=gp.LINE_DILATE + 1)
        erase = np.zeros(land.shape, dtype=bool)
        paste_crop(erase, erase_crop, cx0, cy0)
        composite &= ~erase
    composite |= proposal
    log("round trip: the generator's region stage on existing + proposal ...", t0)
    reg1, _ = existing_regions(layers, composite, t0)
    reg1_crop = cr_partition.crop_box(reg1, crop_box, wrap=True)
    gen_ids = [int(r) for r in np.unique(reg1_crop[scope]) if r > 0]
    gen = np.zeros(crop_shape, dtype=np.int32)
    leaks = []
    # The generator dilates every line by LINE_DILATE and hands those pixels to the nearest
    # region, so a state may spill a couple of px past a closing line. A leak is land beyond that.
    off_scope = ndimage.distance_transform_edt(~scope)
    spill = gp.LINE_DILATE + 1
    for r in gen_ids:
        m = reg1_crop == r
        far = float((m & (off_scope > spill)).sum()) / float(m.sum())
        gen[m & scope] = r
        if far > 0.02:
            leaks.append({"region": r, "beyond_frac": round(far, 3), "px": int(m.sum())})
    pairs, only_prop, only_gen = match_regions(labels, gen, 0.9)
    round_trip = {
        "proposed": n_states, "generated": len(gen_ids), "matched_iou_0.9": len(pairs),
        "leaks": leaks, "unmatched_proposed": only_prop, "unmatched_generated": only_gen,
        "passed": bool(not leaks and len(pairs) == n_states == len(gen_ids)),
    }
    log(f"  round trip: {n_states} proposed, {len(gen_ids)} generated, {len(pairs)} matched, "
        f"{len(leaks)} leaking -> {'PASS' if round_trip['passed'] else 'FAIL'}", t0)

    compare = None
    if args.replace_existing:
        ex_ids = [int(r) for r in np.unique(reg_crop[scope]) if r > 0
                  if float((scope & (reg_crop == r)).sum()) / float((reg_crop == r).sum()) >= 0.5]
        ex = np.where(np.isin(reg_crop, ex_ids) & scope, reg_crop, 0)
        cpairs, c_prop, c_ex = match_regions(labels, ex, 0.6)
        compare = {"existing": len(ex_ids), "proposed": n_states, "matched_iou_0.6": len(cpairs),
                   "unmatched_proposed": len(c_prop), "unmatched_existing": len(c_ex)}
        log(f"  vs the existing layer: {len(ex_ids)} states there, {n_states} proposed, "
            f"{len(cpairs)} match at IoU >= 0.6", t0)

    # --- provenance, names ---------------------------------------------------------------------
    prov = cr_partition.provenance(labels, cr_raw)

    def cr_name(label: int) -> tuple[str, str]:
        if label in names:
            return names[label]
        return (f"cr_idx_{label - 1}", f"cr_idx_{label - 1}")

    rows = []
    for st in sorted(prov):
        p = prov[st]
        shares = sorted(p["cr_shares"].items(), key=lambda kv: (-kv[1], kv[0]))
        rows.append({
            "state": st, "area_px": p["area_px"],
            "anchor_x": p["anchor"][0] + cx0, "anchor_y": p["anchor"][1] + cy0,
            "cr_keys": "+".join(cr_name(k)[0] for k, _ in shares),
            "cr_names": " + ".join(cr_name(k)[1] for k, _ in shares[:2]) or "(no CR source)",
            "cr_shares": "+".join(f"{v:.2f}" for _, v in shares),
            "split_flag": "oversize" if st in flagged else "",
        })

    # --- outputs ------------------------------------------------------------------------------
    canvas_png = out / f"{name}_borders_proposal_canvas.png"
    rgba = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
    rgba[proposal] = (*MAGENTA, 255)
    Image.fromarray(rgba).save(canvas_png)

    csv_path = out / f"{name}_borders_proposal_states.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["state"])
        w.writeheader()
        w.writerows(rows)

    header = (f"{name}: {n_states} states (CR regions {n_cr}, merged "
              f"{max(0, before_merge - n_states)}, split {split}, flagged {len(flagged)}); "
              f"placement IoU {info['iou']:.2f}"
              + (f", dot check {dot_check['with_landmarks']['median']} px" if dot_check else ""))
    review = render_review(name, header, scope, labels, rows, lines, closing, feat_crop,
                           layers, crop_box, (ox, oy), lms, (cx0, cy0), round_trip, gen, out)

    report = {
        "landmass": name, "target": target, "replace_existing": bool(args.replace_existing),
        "inputs_sha256": {
            "lookup": sources_mod.sha256_of(LOOKUP_TGA),
            "regions_tsv": sources_mod.sha256_of(REGIONS_TSV),
            "loc_tsv": sources_mod.sha256_of(LOC_TSV),
            "land_sea_mask": sources_mod.sha256_of(MASK_PATH),
            "state_borders": sources_mod.sha256_of(
                sources_mod.resolve_source_path(sources_mod.split_ref(gp.STATE_REGIONS_SOURCE)[0])),
            "config": sources_mod.sha256_of(args.config),
        },
        "params": {"box": cfg["box"], "cr_box": cfg["cr_box"], "min_state_px": cfg["min_state_px"],
                   "max_state_px": cfg["max_state_px"], "snap_px": cfg["snap_px"],
                   "snap_follow_frac": cfg["snap_follow_frac"], "fit": {**cr_partition.DEFAULT_FIT, **fit_p}},
        "placement": info, "dot_check": dot_check,
        "hull": {"outside_blobs": blobs[:12], "scope_px": int(scope.sum())},
        "snap": {k: len(v) if isinstance(v, list) else v for k, v in snap_report.items()},
        "snap_detail": snap_report,
        "states": {"count": n_states, "cr_regions": n_cr, "flagged_oversize": flagged,
                   "median_px": med, "islets_left_to_generator": len(islets)},
        "round_trip": round_trip, "compare": compare,
        "unproven_until_a_mainland_child": ["mainland scope", "box-edge closing lines at scale",
                                           "borders snapping to rivers (Ulthuan has few)",
                                           "Claude-placed landmarks (unless listed)"],
    }
    (out / f"{name}_borders_proposal.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.placement_review:
        render_placement(name, lab, hull, land_crop, layers, crop_box, (cx0, cy0), cfg, lms,
                         idx, void, out)
    log(f"wrote {canvas_png.name}, {review.name} and the table under {out}", t0)
    return 0 if round_trip["passed"] else 1


# ---------------------------------------------------------------------------
# Renders
# ---------------------------------------------------------------------------

def _globe_crop(crop_box) -> np.ndarray:
    path = sources_mod.resolve_source_path(GLOBE_SOURCE)
    with Image.open(path) as im:
        arr = np.array(im.convert("RGB"))
    return cr_partition.crop_box(arr, crop_box, wrap=True)


def _coast(land: np.ndarray) -> np.ndarray:
    return land & ~ndimage.binary_erosion(land)


def render_review(name, header, scope, labels, rows, lines, closing, features, layers, crop_box,
                  box_origin, lms, crop_origin, round_trip, gen, out: Path) -> Path:
    cx0, cy0 = crop_origin
    bg = _globe_crop(crop_box).astype(np.uint8)
    land = cr_partition.crop_box(layers.land, crop_box, wrap=True)
    imp = cr_partition.crop_box(layers.impassable_mask(), crop_box, wrap=True)
    img = bg.copy()
    img[imp] = (0.5 * img[imp] + 0.5 * np.array([120, 120, 120])).astype(np.uint8)
    img[_coast(land)] = (0, 255, 255)
    img[features & ~_coast(land)] = (40, 90, 255)
    img[lines] = MAGENTA
    img[closing] = (255, 140, 0)
    # failing generated states, outlined in red
    if not round_trip["passed"]:
        bad = np.zeros(scope.shape, dtype=bool)
        for r in round_trip["unmatched_generated"]:
            bad |= gen == r
        img[bad & ~ndimage.binary_erosion(bad)] = (255, 0, 0)
    ys, xs = np.nonzero(scope)
    y0, y1 = max(0, ys.min() - 40), min(img.shape[0], ys.max() + 41)
    x0, x1 = max(0, xs.min() - 40), min(img.shape[1], xs.max() + 41)
    pic = Image.fromarray(img[y0:y1, x0:x1]).resize(((x1 - x0) * 2, (y1 - y0) * 2), Image.NEAREST)
    d = ImageDraw.Draw(pic)
    d.rectangle([0, 0, pic.width, 14], fill=(0, 0, 0))
    d.text((4, 2), header, fill=(255, 255, 255))
    for r in rows:
        ax, ay = (r["anchor_x"] - cx0 - x0) * 2, (r["anchor_y"] - cy0 - y0) * 2
        d.text((ax - 20, ay - 5), r["cr_names"][:26], fill=(255, 255, 255))
    for i, lm in enumerate(lms, 1):
        lx, ly = (lm.canvas[0] + box_origin[0] - x0) * 2, (lm.canvas[1] + box_origin[1] - y0) * 2
        d.ellipse([lx - 8, ly - 8, lx + 8, ly + 8], outline=(255, 255, 0), width=2)
        d.text((lx + 10, ly - 6), str(i), fill=(255, 255, 0))
    path = out / f"{name}_borders_proposal_review.png"
    pic.save(path)
    return path


def render_placement(name, lab, hull, land_crop, layers, crop_box, crop_origin, cfg, lms,
                     idx, void, out: Path) -> None:
    cx0, cy0 = crop_origin
    bg = _globe_crop(crop_box).astype(np.uint8)
    img = bg.copy()
    edges = cr_partition.lines_from_labels(lab, hull)
    cr_land = lab > 0
    img[_coast(cr_land) & hull] = (255, 140, 0)        # CR coast
    img[edges] = (255, 40, 40)                         # CR region edges
    img[_coast(land_crop)] = (0, 255, 255)             # our coast
    Image.fromarray(img).resize((img.shape[1] * 2, img.shape[0] * 2), Image.NEAREST).save(
        out / f"{name}_placement_review.png")

    # Landmark sheet: CR land (parchment frame) beside our globe crop, 50 px tick grids.
    rx0, ry0, rx1, ry1 = (int(v) for v in cfg["cr_box"])
    src = cr_partition.to_parchment_frame(idx, void, cfg["cr_box"])
    left = np.full(src.shape + (3,), 24, dtype=np.uint8)
    left[src > 0] = (70, 90, 70)
    left[cr_partition.lines_from_labels(src, src > 0)] = (255, 255, 255)
    left[_coast(src > 0)] = (255, 140, 0)
    bx0, by0, bx1, by1 = (int(v) for v in cfg["box"])
    right = cr_partition.crop_box(bg, (bx0 - cx0, by0 - cy0, bx1 - cx0, by1 - cy0)).copy()
    rland = cr_partition.crop_box(land_crop, (bx0 - cx0, by0 - cy0, bx1 - cx0, by1 - cy0))
    right[_coast(rland)] = (0, 255, 255)

    def grid(arr, ox, oy, scale=1):
        im = Image.fromarray(arr).resize((arr.shape[1] * scale, arr.shape[0] * scale), Image.NEAREST)
        d = ImageDraw.Draw(im)
        for gx in range(((ox + 49) // 50) * 50, ox + arr.shape[1], 50):
            px = (gx - ox) * scale
            d.line([px, 0, px, 8], fill=(255, 255, 0))
            d.text((px + 2, 8), str(gx), fill=(255, 255, 0))
        for gy in range(((oy + 49) // 50) * 50, oy + arr.shape[0], 50):
            py = (gy - oy) * scale
            d.line([0, py, 8, py], fill=(255, 255, 0))
            d.text((10, py - 5), str(gy), fill=(255, 255, 0))
        return im, d

    li, ld = grid(left, rx0, ry0)
    ri, rd = grid(right, bx0, by0)
    for i, lm in enumerate(lms, 1):
        ld.ellipse([lm.source[0] - 8, lm.source[1] - 8, lm.source[0] + 8, lm.source[1] + 8],
                   outline=(255, 255, 0), width=2)
        ld.text((lm.source[0] + 10, lm.source[1] - 6), str(i), fill=(255, 255, 0))
        rd.ellipse([lm.canvas[0] - 8, lm.canvas[1] - 8, lm.canvas[0] + 8, lm.canvas[1] + 8],
                   outline=(255, 255, 0), width=2)
        rd.text((lm.canvas[0] + 10, lm.canvas[1] - 6), str(i), fill=(255, 255, 0))
    sheet = Image.new("RGB", (li.width + ri.width + 10, max(li.height, ri.height)), (0, 0, 0))
    sheet.paste(li, (0, 0))
    sheet.paste(ri, (li.width + 10, 0))
    sheet.save(out / f"{name}_landmark_sheet.png")


if __name__ == "__main__":
    sys.exit(main())
