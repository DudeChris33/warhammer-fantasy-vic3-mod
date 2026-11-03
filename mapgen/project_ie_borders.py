#!/usr/bin/env python3
"""Project the traced Immortal Empires borders onto the canvas, zone by zone (#9016).

Reads the ``borders`` layer of ``iee_parchment - borders_aligned.ora`` (ChaosRobie's
expanded IE parchment frame, mapped into IE master px by ``frames.lines`` of
``mapgen/config/ie_projection.json``), the committed landmark pairs
``mapgen/config/ie_projection_pairs.csv`` and the zone outlines, and warps every line
point by its owner zone's thin-plate (rules in ``worldgen/ie_projection.py``). Writes,
to ``--out-dir`` (default ``scratchpad/ie_projection/``):

- ``terraqueous_globe_reprojected - ie_state_borders.png``: a canvas copy with the lines;
- ``ie_state_borders_layer.png``: the same lines on a transparent layer. A diagnostic
  projection, not the ``.ora`` guide layer (#9018 builds that from faces);
- ``report.json``: per zone the method picked and every candidate's numbers, held-out
  errors, folds, the triangle warp beside it, seams, overlaps and the known-answer check;
- ``review_zones_source.png``, ``review_blend_quarter.png``, ``review_known_answer.png``
  for Chris. Orange marks warnings: fold px, seam bridges longer than ``seam_flag_px``
  (not in the layer), lines where two zones' land overlaps on the canvas.

Nothing the game or a generator reads changes, and nothing writes ``sources/``,
``full.ora`` or Chris's review app. Two runs give byte-identical outputs.

Authoring flags, the only writers of a committed file (the pairs CSV); they exit
without projecting:

- ``--sync-review DB [--zones-from CSV] [--dry-run]`` lands Chris's review database
  (its ``reviewed.json``): status, coordinates and text come from it, ``zone`` and
  ``held_out`` stay the CSV's (a new id takes the database zone, else the zones CSV's).
- ``--hold-out [--dry-run]`` adds held-out pairs per the residual-blind rule.

Usage (repo root, mapgen venv)::

    python mapgen/project_ie_borders.py [--include-pending] [--pairs PATH] [--out-dir DIR]
    python mapgen/project_ie_borders.py --sync-review <reviewed.json> [--zones-from <csv>] [--dry-run]
    python mapgen/project_ie_borders.py --hold-out [--dry-run]

Exit 2 on a pairs or config validation error, 1 when a mapped zone cannot be fitted
(fewer than 4 non-collinear pairs), else 0; flags print as ``WARNING`` lines.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import tabulate_state_prior  # noqa: E402
import validate_map  # noqa: E402
from worldgen import ie_projection as iep  # noqa: E402
from worldgen import raster, sources  # noqa: E402

REPO = TOOLS_DIR.parent
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"
OUT_DEFAULT = SCRATCH_DIR / "ie_projection"
LINE = (255, 0, 255)
WARN = (255, 140, 0)
DRAWN = (0, 200, 255)
PAL = {0: (0, 0, 0), 1: (60, 200, 60), 2: (230, 60, 200), 3: (60, 120, 255), 4: (255, 150, 0),
       5: (200, 200, 200), 6: (120, 120, 120)}


def _rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).name


def _manifest_sha(name: str) -> str:
    rows = {r.file: r for r in sources.parse_manifest(sources.MANIFEST_PATH.read_text(encoding="utf-8"))}
    return rows[sources.split_ref(name)[0]].sha256


# --------------------------------------------------------------------------- authoring

def cmd_sync(args, cfg) -> int:
    db = json.loads(Path(args.sync_review).read_text(encoding="utf-8"))
    zones_from = {}
    if args.zones_from:
        with open(args.zones_from, encoding="utf-8-sig", newline="") as fh:
            zones_from = {r["id"]: r.get("zone", "") or "" for r in csv.DictReader(fh)}
    rows = iep.read_pairs(args.pairs) if Path(args.pairs).exists() else []
    expected = {"source": _manifest_sha(cfg["frames"]["master"]["source"]),
                "target": _manifest_sha(cfg["frames"]["canvas"]["source"])}
    new, log = iep.sync_rows(rows, db, expected, zones_from)
    iep.validate_rows(new)
    for line in log:
        print(line)
    _print_unzoned(new, db)
    counts = {s: sum(r.review_status == s for r in new) for s in iep.STATUSES}
    print(f"{len(new)} rows {counts}; {len(log)} changes")
    if args.dry_run:
        print("dry run: nothing written")
    else:
        iep.write_pairs(new, args.pairs)
        print(f"wrote {_rel(args.pairs)}")
    return 0


def _print_unzoned(rows, db=None):
    sugg = {a["id"]: a.get("suggested_zone") for a in (db or {}).get("anchors", [])}
    for r in rows:
        s = str(sugg.get(r.id) or "")
        if r.review_status == "accepted" and not r.zone and s in {str(z) for z in iep.MAPPED_ZONES}:
            print(f"WARNING unzoned_accepted {r.id} (suggested_zone {s})")


def cmd_hold_out(args, cfg) -> int:
    rows = iep.read_pairs(args.pairs)
    iep.validate_rows(rows)
    added = []
    for z in iep.MAPPED_ZONES:
        plan = iep.plan_held_out(rows, z, cfg["held_out"])
        print(f"zone {z}: accepted {plan['accepted']}, want {plan['want']}, have {plan['have']}, "
              f"add {plan['add'] or '-'}")
        for f in plan["flags"]:
            print(f"WARNING zone {z}: {f}")
        added += plan["add"]
    if not added:
        print("nothing to add")
        return 0
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    for r in rows:
        if r.id in added:
            r.held_out = "1"
    iep.validate_rows(rows)
    iep.write_pairs(rows, args.pairs)
    print(f"wrote {_rel(args.pairs)}")
    return 0


# --------------------------------------------------------------------------- projection

def _draw_lines(a, draw_mask, shape):
    """1-px projected lines of the drawn edges, as a bool canvas mask."""
    from PIL import Image, ImageDraw
    H, W = shape
    im = Image.new("L", (W, H))
    d = ImageDraw.Draw(im)
    e = a.line_edges[draw_mask]
    P = a.canvas_xy
    for i, j in e:
        d.line([tuple(P[i]), tuple(P[j])], fill=255, width=1)
    return np.asarray(im) > 0


def _forward_footprints(a, sc: float, shape):
    """Quarter-scale forward splat of each zone's IE land: ``{z: bool mask}`` and mean colour."""
    Hq, Wq = int(shape[0] * sc), int(shape[1] * sc)
    H, W = a.zones.shape
    gy, gx = np.mgrid[0:H:2, 0:W:2]
    G = np.c_[gx.ravel(), gy.ravel()].astype(np.float64)
    gz = a.zones[gy.ravel(), gx.ravel()]
    fp = {}
    for z, w in a.warps.items():
        Q = w.forward(G[gz == z]) * sc
        qx, qy = Q[:, 0].astype(int), Q[:, 1].astype(int)
        k = (qx >= 0) & (qx < Wq) & (qy >= 0) & (qy < Hq)
        m = np.zeros((Hq, Wq), bool)
        m[qy[k], qx[k]] = True
        fp[z] = (m, G[gz == z][k].astype(int), qx[k], qy[k])
    return fp


def _known_answer(a, lines_1px, cfg):
    rgb = raster.read_rgb_png(REPO / "map_data" / "provinces.png")
    with open(TOOLS_DIR / "config" / "land_regions_worksheet.csv", encoding="utf-8", newline="") as fh:
        drawn = {int(r["region_id"]) for r in csv.DictReader(fh) if r["kind"] == "drawn"}
    ys, xs = np.nonzero(lines_1px)
    line_px = np.c_[xs, ys]
    out, crops = {}, {}
    for stem, z in sorted(cfg["known_answer"].items()):
        path = REPO / "map_data" / "state_regions" / f"{stem}.txt"
        states = [st for st in validate_map.parse_state_file(path) if st.id in drawn]
        sid = tabulate_state_prior._state_raster(rgb, states, False, {})
        region = sid > 0
        border = iep.state_border_px(sid, region)
        st = iep.known_answer_stats(border, region, line_px, cfg["known_answer_shift_px"])
        st["zone"], st["states"] = z, len(states)
        out[stem] = st
        crops[stem] = (region, border)
    return out, crops


def cmd_project(args, cfg) -> int:
    rows = iep.read_pairs(args.pairs)
    iep.validate_rows(rows, include_pending=args.include_pending)
    a = iep.analyse(rows, cfg, args.include_pending)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    can = sources.load_source_image(cfg["frames"]["canvas"]["source"])
    CH, CW = can.shape[:2]
    flag = cfg["seam_flag_px"]
    draw, long_, seams = iep.seam_edges(a.line_edges, a.owner, np.nan_to_num(a.canvas_xy, nan=-1e9), flag)
    on = np.isfinite(a.canvas_xy).all(1)
    oncan = on & (a.canvas_xy[:, 0] >= 0) & (a.canvas_xy[:, 0] < CW) & (a.canvas_xy[:, 1] >= 0) & \
        (a.canvas_xy[:, 1] < CH)
    draw &= oncan[a.line_edges[:, 0]] & oncan[a.line_edges[:, 1]]
    from scipy import ndimage as nd
    from skimage.morphology import disk
    lines_1px = _draw_lines(a, draw, (CH, CW))
    thick = nd.binary_dilation(lines_1px, disk(2))
    canvas_out = can.copy()
    canvas_out[thick] = LINE
    raster.write_rgb_png(out / "terraqueous_globe_reprojected - ie_state_borders.png", canvas_out)
    layer = np.zeros((CH, CW, 4), np.uint8)
    layer[thick] = LINE + (255,)
    raster.write_rgba_png(out / "ie_state_borders_layer.png", layer)

    # folds on the drawn lines, per zone's chosen warp
    fold_pts = []
    for z, w in a.warps.items():
        mine = a.owner == z
        det = np.linalg.det(w.jacobian(a.line_xy[mine]))
        fold_pts.append(a.canvas_xy[mine][det <= 0])
    fold_pts = np.concatenate(fold_pts) if fold_pts else np.zeros((0, 2))

    sc = 0.25
    fp = _forward_footprints(a, sc, (CH, CW))
    overlap = {}
    zs = sorted(fp)
    for i, z1 in enumerate(zs):
        for z2 in zs[i + 1:]:
            both = fp[z1][0] & fp[z2][0]
            if not both.any():
                continue
            q = lambda z: (a.canvas_xy[a.owner == z] * sc).astype(int)  # noqa: E731
            inside = {}
            for zz, other in ((z1, z2), (z2, z1)):
                qq = q(zz)
                ok = (qq[:, 0] >= 0) & (qq[:, 0] < both.shape[1]) & (qq[:, 1] >= 0) & (qq[:, 1] < both.shape[0])
                inside[f"line_px_{zz}_in_{other}"] = int(fp[other][0][qq[ok, 1], qq[ok, 0]].sum())
            overlap[f"{z1}/{z2}"] = {"quarter_px": int(both.sum()), **inside}

    ka, crops = _known_answer(a, lines_1px, cfg)

    long_list = [[iep.r1(a.line_xy[i, 0]), iep.r1(a.line_xy[i, 1]), int(a.owner[i]), int(a.owner[j]),
                  iep.r1(np.hypot(*(a.canvas_xy[i] - a.canvas_xy[j])))] for i, j in a.line_edges[long_]]
    cand = [r for r in rows if r.review_status == "accepted" and not r.zone]
    near = iep.assign_owners(a.zones, np.array([r.src for r in cand]).reshape(-1, 2),
                             cfg["ownership"]["priority"], 12) if cand else []
    unz = [r.id for r, z in zip(cand, near) if z > 0]
    disagree = []
    for r in rows:
        if r.zones and r.review_status in ("accepted", "pending"):
            x, y = int(r.source_x), int(r.source_y)
            zr = int(a.zones[y, x])
            if zr not in r.zones:
                disagree.append({"id": r.id, "zone": r.zone, "raster_zone": zr})
    rep = {
        "inputs": {"pairs": _rel(args.pairs), "pairs_sha256_lf": iep.sha_lf(args.pairs),
                   "config_sha256_lf": iep.sha_lf(iep.CONFIG_PATH),
                   "sources": {k: {"ref": f[ "source"], "sha256": _manifest_sha(f["source"])}
                               for k, f in sorted(cfg["frames"].items())}},
        "include_pending": bool(args.include_pending),
        "pairs": {"rows": len(rows), "by_status": {s: sum(r.review_status == s for r in rows)
                                                   for s in iep.STATUSES},
                  "unzoned_accepted": unz, "zone_disagrees_with_raster": disagree},
        "lines": {"skeleton_px": int(len(a.line_xy)), "outside_master_frame_px": a.outside_master,
                  "unmapped_px": int((a.owner == 0).sum()), "off_canvas_px": int((on & ~oncan).sum()),
                  "seam_flag_px": flag},
        "zones": {str(z): r for z, r in sorted(a.zone_reports.items())},
        "seams": seams, "long_seam_bridges": long_list,
        "canvas_overlap": overlap, "known_answer": ka,
        "unsnapped_faces": a.unsnapped,
    }
    for z in iep.MAPPED_ZONES:
        zr = a.zone_reports[z]
        zr["held_out_plan"] = iep.plan_held_out(rows, z, cfg["held_out"])
    (out / "report.json").write_text(json.dumps(_round(rep), indent=1, sort_keys=True) + "\n",
                                     encoding="utf-8", newline="\n")

    _render_source(a, rows, out, cfg)
    _render_blend(a, rows, out, can, layer, fp, sc, long_, fold_pts, overlap)
    _render_known_answer(out, can, crops, lines_1px, fold_pts)

    rc = 0
    for z in iep.MAPPED_ZONES:
        zr = a.zone_reports[z]
        flags = zr.get("method", {}).get("flags", []) + zr.get("flags", [])
        if "unfittable" in flags:
            rc = 1
        ch = zr.get("chosen", {})
        print(f"zone {z} {zr['name']}: {len(zr['drawn_fit'])} pairs, lam {zr.get('method', {}).get('lam')}, "
              f"loo {ch.get('loo')}, folds lines/grid {ch.get('folds_lines')}/{ch.get('folds_land_grid')}, "
              f"outside hull {zr.get('outside_pair_hull_pct')}%")
        for f in flags:
            print(f"WARNING zone {z}: {f}")
        for f in zr["held_out_plan"]["flags"]:
            print(f"WARNING zone {z} held-out: {f}")
    for i in unz:
        print(f"WARNING unzoned_accepted {i}")
    if long_list:
        print(f"WARNING {len(long_list)} seam bridges over {flag} px left out of the layer")
    for k, v in overlap.items():
        print(f"WARNING canvas overlap {k}: {v}")
    for k, v in ka.items():
        print(f"known answer {k}: {v}")
    print(f"wrote {_rel(out)}/")
    return rc


def _round(o):
    if isinstance(o, float):
        return round(o, 1) if abs(o) >= 0.05 or o == 0 else float(f"{o:.3g}")
    if isinstance(o, dict):
        return {str(k): _round(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v) for v in o]
    if isinstance(o, np.generic):
        return _round(o.item())
    return o


# --------------------------------------------------------------------------- renders

def _render_source(a, rows, out, cfg):
    from PIL import Image, ImageDraw
    par = sources.load_source_image(cfg["frames"]["master"]["source"]).astype(np.float64)
    H, W = a.zones.shape
    cz = np.zeros_like(par)
    for z, c in PAL.items():
        cz[a.zones == z] = c
    al = np.where(np.isin(a.zones, iep.MAPPED_ZONES), 0.45, np.where(a.zones > 0, 0.25, 0))[..., None]
    v = par * (1 - al) + cz * al
    v[a.net_ie] = LINE
    im = Image.fromarray(v.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for r in rows:
        if r.zones and r.review_status in ("accepted", "pending"):
            x, y = r.src
            fill = (255, 230, 0) if r.review_status == "accepted" else (255, 255, 255)
            d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=fill, outline=(0, 0, 0), width=2)
            d.text((x + 9, y - 8), r.id, fill=(0, 0, 0), stroke_width=3, stroke_fill=(255, 255, 255))
    raster.write_rgb_png(out / "review_zones_source.png",
                         np.asarray(im.resize((W // 2, H // 2), Image.LANCZOS)))


def _render_blend(a, rows, out, can, layer, fp, sc, long_, fold_pts, overlap):
    from PIL import Image, ImageDraw
    from scipy import ndimage as nd
    from scipy.spatial import Delaunay
    CH, CW = can.shape[:2]
    Hq, Wq = int(CH * sc), int(CW * sc)
    par = sources.load_source_image(a.cfg["frames"]["master"]["source"]).astype(np.float64)
    acc = np.zeros((Hq, Wq, 3))
    cnt = np.zeros((Hq, Wq))
    for z, (m, g, qx, qy) in fp.items():
        np.add.at(acc, (qy, qx), par[g[:, 1], g[:, 0]])
        np.add.at(cnt, (qy, qx), 1)
    filled = cnt > 0
    hole = nd.binary_closing(filled, np.ones((5, 5))) & ~filled
    _, (hy, hx) = nd.distance_transform_edt(~filled, return_indices=True)
    avg = acc / np.maximum(cnt, 1)[..., None]
    avg[hole] = avg[hy[hole], hx[hole]]
    valid = filled | hole
    cq = np.asarray(Image.fromarray(can).resize((Wq, Hq), Image.LANCZOS)).astype(np.float64)
    alq = (0.5 * valid)[..., None]
    bl = cq * (1 - alq) + avg * alq
    lq = np.asarray(Image.fromarray(layer).resize((Wq, Hq), Image.BOX)).astype(np.float64)
    la = (lq[..., 3:] / 255).clip(0, 1) ** 0.6
    bl = bl * (1 - la) + lq[..., :3] * la
    zs = sorted(fp)
    for i, z1 in enumerate(zs):
        for z2 in zs[i + 1:]:
            both = fp[z1][0] & fp[z2][0]
            bl[both & (la[..., 0] > 0.2)] = WARN
    img = Image.fromarray(bl.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for i, j in a.line_edges[long_]:
        d.line([tuple(a.canvas_xy[i] * sc), tuple(a.canvas_xy[j] * sc)], fill=WARN, width=2)
    for x, y in fold_pts * sc:
        d.point((x, y), fill=WARN)
    for z, w in a.warps.items():
        hull = Delaunay(w.src).convex_hull
        for e in hull:
            t = np.linspace(0, 1, 30)[:, None]
            seg = w.forward(w.src[e[0]] * (1 - t) + w.src[e[1]] * t) * sc
            d.line([tuple(p) for p in seg], fill=PAL[z], width=2)
    for r in rows:
        if r.zones and r.review_status in ("accepted", "pending"):
            x, y = r.canvas_x * sc, r.canvas_y * sc
            fill = (255, 230, 0) if r.review_status == "accepted" else (255, 255, 255)
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=fill, outline=(0, 0, 0))
            d.text((x + 5, y - 6), r.id, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    d.rectangle([5, Hq - 62, 860, Hq - 5], fill=(255, 255, 255), outline=(0, 0, 0))
    d.text((10, Hq - 58), "zones 1-4 of the IE parchment warped 50% over the canvas, each by its chosen thin-plate; "
           "magenta = projected borders", fill=(0, 0, 0))
    d.text((10, Hq - 40), "yellow = accepted pair, white = pending; outline colour = each zone's pair hull "
           "(outside = extrapolated)", fill=(0, 0, 0))
    d.text((10, Hq - 22), "orange = warning: fold px, seam bridge over the flag (not in the layer), "
           "lines where two zones overlap", fill=(0, 0, 0))
    raster.write_rgb_png(out / "review_blend_quarter.png", np.asarray(img))


def _render_known_answer(out, can, crops, lines_1px, fold_pts):
    from PIL import Image, ImageDraw
    from scipy import ndimage as nd
    tiles = []
    for stem, (region, border) in sorted(crops.items()):
        if not region.any():
            continue
        ys, xs = np.nonzero(region)
        y0, y1 = max(ys.min() - 60, 0), min(ys.max() + 60, region.shape[0])
        x0, x1 = max(xs.min() - 60, 0), min(xs.max() + 60, region.shape[1])
        v = can[y0:y1, x0:x1].astype(np.float64) * 0.55 + 255 * 0.45
        b = nd.binary_dilation(border[y0:y1, x0:x1])
        ln = nd.binary_dilation(lines_1px[y0:y1, x0:x1])
        v[b] = DRAWN
        v[ln] = LINE
        im = Image.fromarray(v.astype(np.uint8))
        d = ImageDraw.Draw(im)
        for x, y in fold_pts:
            if x0 <= x < x1 and y0 <= y < y1:
                d.point((x - x0, y - y0), fill=WARN)
        d.rectangle([4, 4, 520, 26], fill=(255, 255, 255))
        d.text((8, 8), f"{stem}: cyan = Chris's drawn state borders, magenta = projected IE lines", fill=(0, 0, 0))
        s = min(1.0, 2000 / im.width)
        tiles.append(im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS))
    if not tiles:
        return
    W = max(t.width for t in tiles)
    H = sum(t.height for t in tiles) + 8 * (len(tiles) - 1)
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    y = 0
    for t in tiles:
        sheet.paste(t, (0, y))
        y += t.height + 8
    raster.write_rgb_png(out / "review_known_answer.png", np.asarray(sheet))


# --------------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pairs", type=Path, default=iep.PAIRS_PATH)
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--include-pending", action="store_true", help="fit pending rows too (proposal runs)")
    ap.add_argument("--sync-review", metavar="DB", help="land Chris's review database into the pairs CSV")
    ap.add_argument("--zones-from", metavar="CSV", help="zone column for ids new to the pairs CSV")
    ap.add_argument("--hold-out", action="store_true", help="add held-out pairs per the rule")
    ap.add_argument("--dry-run", action="store_true", help="with --sync-review/--hold-out: print, write nothing")
    args = ap.parse_args(argv)
    cfg = iep.load_config()
    try:
        if args.sync_review:
            return cmd_sync(args, cfg)
        if args.hold_out:
            return cmd_hold_out(args, cfg)
        return cmd_project(args, cfg)
    except iep.PairsError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
