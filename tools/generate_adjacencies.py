#!/usr/bin/env python3
"""Author ``map_data/adjacencies.csv`` from the hand-drawn yellow line layer (board #5563).

Chris draws every crossing between provinces that do not touch (a strait, an island
link, a tunnel) as a flat ``(255,255,0)`` line on
``terraqueous_globe_reprojected - adjacencies.png`` (``source_layers.json``'s
``adjacencies`` key). This tool turns each line into a numbered entry naming the
two provinces its endpoints sit in; Chris then types each entry in the hand-authored
``tools/config/adjacency_worksheet.json`` (type + comment, identity = endpoint
coordinates), and ``--write`` emits the engine CSV from that.

Modes::

    python tools/generate_adjacencies.py            # --review (default): numbered table + render
    python tools/generate_adjacencies.py --sync     # carry the worksheet over to the current lines
    python tools/generate_adjacencies.py --write    # write map_data/adjacencies.csv from the worksheet
    python tools/generate_adjacencies.py --check    # re-derive in memory, assert == committed CSV

``--review`` writes only gitignored ``tools/derived/`` files. Ambiguous lines are
reported and skipped, never guessed. The emitted CSV is province-colour keyed, so
re-run after any ``generate_provinces.py`` regen.

Engine ``y`` is bottom-origin (``H - 1 - y``); see ``worldgen/adjacencies.py``.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import adjacencies as adj  # noqa: E402
from worldgen import raster, schema, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
MOD_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
PROVINCES_PNG = MOD_ROOT / "map_data" / "provinces.png"
PROVINCES_INDEX = DERIVED_DIR / "provinces_index.json"
STATE_DIR = MOD_ROOT / "map_data" / "state_regions"
WORKSHEET = TOOLS_DIR / "config" / "adjacency_worksheet.json"
CSV_PATH = MOD_ROOT / "map_data" / "adjacencies.csv"
TABLE_PATH = DERIVED_DIR / "adjacencies_table.csv"
PREVIEW_PATH = DERIVED_DIR / "adjacencies_preview.png"
STRAITS_PATH = MOD_ROOT / "common" / "strait_definitions" / "canals.txt"
CANAL_LOC_PATH = MOD_ROOT / "localization" / "english" / "map" / "wh_canals_l_english.yml"
BOM = b"\xef\xbb\xbf"
INDENT = "\t"


def _write_bytes(path: Path, text: str, bom: bool = False) -> None:
    data = text.encode("utf-8")
    if bom:
        data = BOM + data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _code_map(rgb: np.ndarray) -> np.ndarray:
    return ((rgb[..., 0].astype(np.uint32) << 16) | (rgb[..., 1].astype(np.uint32) << 8)
            | rgb[..., 2].astype(np.uint32))


def _touching(code: np.ndarray, wrap_x: bool) -> set[frozenset]:
    parts = [(code[:, :-1], code[:, 1:]), (code[:-1, :], code[1:, :])]
    if wrap_x:
        parts.append((code[:, -1:], code[:, :1]))
    pairs: set[int] = set()
    for a, b in parts:
        d = a != b
        lo = np.minimum(a[d], b[d]).astype(np.uint64)
        hi = np.maximum(a[d], b[d]).astype(np.uint64)
        pairs.update(np.unique((lo << np.uint64(24)) | hi).tolist())
    return {frozenset((adj.code_color(p >> 24), adj.code_color(p & 0xFFFFFF))) for p in pairs}


def _state_names() -> dict[adj.Color, str]:
    import validate_map as vm

    out: dict[adj.Color, str] = {}
    if STATE_DIR.is_dir():
        for f in sorted(STATE_DIR.glob("*.txt")):
            for st in vm.parse_state_file(f):
                for c in st.provinces:
                    out[c] = st.key
    return out


def derive(*, need_worksheet: bool, load_rows: bool = True):
    """Shared pipeline: (crossings, skipped, lines, rows, code_map) or a SystemExit."""
    for p in (PROVINCES_PNG, PROVINCES_INDEX):
        if not p.is_file():
            raise SystemExit(f"missing {p} - run generate_provinces.py first")
    rgba = sources.read_source_rgba(sources.source_ref("adjacencies"))
    if rgba is None:
        raise SystemExit("adjacencies source not present locally - nothing to do")
    mask = (rgba[..., 3] > 0) & (rgba[..., 0] == 255) & (rgba[..., 1] == 255) & (rgba[..., 2] == 0)
    rgb = raster.read_rgb_png(PROVINCES_PNG)
    if mask.shape != rgb.shape[:2]:
        raise SystemExit(f"adjacencies layer {mask.shape} != provinces.png {rgb.shape[:2]}")
    h, w = mask.shape
    index = json.loads(PROVINCES_INDEX.read_text(encoding="utf-8"))
    kinds = {tuple(int(v) for v in c["color"]): c.get("kind", "land") for c in index["cells"]}
    code = _code_map(rgb)
    rows = schema.load_adjacency_worksheet(WORKSHEET, (w, h)) if load_rows else []
    lines = adj.extract_lines(mask, map_config.WRAP_X)
    crossings, skipped = adj.classify_lines(
        lines, code, kinds, _touching(code, map_config.WRAP_X), pins=rows,
        wrap_x=map_config.WRAP_X)
    return crossings, skipped, lines, rows, rgb, kinds


def _seg_cross(p1, p2, p3, p4) -> bool:
    """True when segments p1-p2 and p3-p4 properly cross."""
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return (v > 0) - (v < 0)
    return (orient(p1, p2, p3) != orient(p1, p2, p4)
            and orient(p3, p4, p1) != orient(p3, p4, p2))


def _seg_hits_box(p, q, box) -> bool:
    """True when segment p-q passes through ``box`` (sampled every 3 px)."""
    n = max(2, int(max(abs(q[0] - p[0]), abs(q[1] - p[1])) // 3))
    for k in range(n + 1):
        x = p[0] + (q[0] - p[0]) * k / n
        y = p[1] + (q[1] - p[1]) * k / n
        if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
            return True
    return False


def _render_numbered(rgb, items, skipped=(), base=None, scale=1):
    """Numbered render over dim province edges. ``items`` is a list of
    ``(start, stop, text, typed)``; every line is drawn first, then each label is
    placed clear of every other label and endpoint, of every other line, and so
    that its leader line (drawn when the label is far) crosses no other leader and
    no other line. ``base`` is an optional ready-made backdrop image with ``items``
    already in its coordinates (the zoom render); ``scale`` thickens the drawing."""
    from PIL import Image, ImageDraw, ImageFont

    if base is None:
        code = _code_map(rgb)
        edge = np.zeros(code.shape, dtype=bool)
        edge[:, :-1] |= code[:, :-1] != code[:, 1:]
        edge[:-1, :] |= code[:-1, :] != code[1:, :]
        img_arr = np.full(rgb.shape, 235, dtype=np.uint8)
        img_arr[edge] = (150, 150, 150)
        img = Image.fromarray(img_arr)
    else:
        img = base
    d = ImageDraw.Draw(img)
    fsize = 28 if scale == 1 else 30
    try:
        font = ImageFont.load_default(size=fsize)
    except TypeError:
        font = ImageFont.load_default()
    lw, dr = (5, 6) if scale == 1 else (max(5, scale), max(6, scale + 1))
    for start, stop, _text, typed in items:
        col = (0, 140, 0) if typed else (220, 0, 0)
        d.line([start, stop], fill=col, width=lw)
        for pt in (start, stop):
            d.ellipse([pt[0] - dr, pt[1] - dr, pt[0] + dr, pt[1] + dr], fill=col)
    pad = 4
    taken = [(pt[0] - 10, pt[1] - 10, pt[0] + 10, pt[1] + 10)
             for start, stop, _t, _ty in items for pt in (start, stop)]
    leaders: list[tuple] = []

    def _hits(box, others):
        return any(box[0] < o[2] and o[0] < box[2] and box[1] < o[3] and o[1] < box[3]
                   for o in others)

    dirs = [(1, -1), (1, 1), (-1, -1), (-1, 1), (0, -1), (0, 1), (1, 0), (-1, 0),
            (2, -1), (2, 1), (-2, -1), (-2, 1), (1, -2), (1, 2), (-1, -2), (-1, 2)]
    maxd = 400 if scale == 1 else 1400
    for n, (start, stop, text, typed) in enumerate(items):
        col = (0, 140, 0) if typed else (220, 0, 0)
        l, t, r, b = d.textbbox((0, 0), text, font=font, stroke_width=3)
        tw, th = r - l, b - t
        mx, my = (start[0] + stop[0]) // 2, (start[1] + stop[1]) // 2
        others = [(o[0], o[1]) for k, o in enumerate(items) if k != n]
        placed = None
        for dist in range(14, maxd, 10):
            for dx, dy in dirs:
                norm = max(abs(dx), abs(dy))
                cx, cy = mx + dx * dist // norm, my + dy * dist // norm
                box = (cx - tw // 2 - pad, cy - th // 2 - pad, cx + tw // 2 + pad, cy + th // 2 + pad)
                if _hits(box, taken):
                    continue
                if any(_seg_hits_box(it[0], it[1], box) for it in items):
                    continue  # a label never sits on any line, its own included
                far = max(abs(cx - mx), abs(cy - my)) > 30
                if far:
                    ld = ((mx, my), (cx, cy))
                    if any(_seg_cross(ld[0], ld[1], o[0], o[1])
                           for o in ((it[0], it[1]) for k, it in enumerate(items) if k != n)):
                        continue
                    if any(_seg_cross(ld[0], ld[1], q[0], q[1]) for q in leaders):
                        continue
                placed = (cx, cy, box, far)
                break
            if placed:
                break
        if placed is None:  # pathological crowding: fall back to a fixed offset
            cx, cy = mx + 14, my - 14
            placed = (cx, cy, (cx - tw // 2, cy - th // 2, cx + tw // 2, cy + th // 2),
                      False)
        cx, cy, box, far = placed
        taken.append(box)
        if far:
            leaders.append(((mx, my), (cx, cy)))
            d.line([(mx, my), (cx, cy)], fill=col, width=2)
        d.text((cx - tw // 2 - l, cy - th // 2 - t), text, fill=(0, 0, 0), font=font,
               stroke_width=3, stroke_fill=(255, 255, 255))
    for s in skipped:
        d.ellipse([s.centroid[0] - 14, s.centroid[1] - 14, s.centroid[0] + 14, s.centroid[1] + 14],
                  outline=(255, 120, 0), width=4)
    return img


def zoom(rows_wanted: list[int], out: Path, half: int = 45, scale: int = 10) -> int:
    """Render one cluster of numbered lines zoomed in: the province edges around the
    given table row numbers, magnified, with labels/leaders placed so none overlap."""
    from types import SimpleNamespace
    from PIL import Image

    crossings, skipped, lines, _, rgb, _ = derive(need_worksheet=False, load_rows=False)
    h, w = rgb.shape[:2]
    raw = (json.loads(WORKSHEET.read_text(encoding="utf-8")).get("adjacencies", [])
           if WORKSHEET.is_file() else [])
    synced, _s, errs, _st = adj.sync_worksheet(crossings, raw, w)
    if errs:
        synced = [{"type": "", "comment": ""}] * len(crossings)
    sel = [(n, crossings[n - 1], synced[n - 1]) for n in rows_wanted]
    xs = [p[0] for _, c, _ in sel for p in (c.start, c.stop)]
    ys = [p[1] for _, c, _ in sel for p in (c.start, c.stop)]
    x0, x1 = max(0, min(xs) - half), min(w, max(xs) + half)
    y0, y1 = max(0, min(ys) - half), min(h, max(ys) + half)
    code = _code_map(rgb)[y0:y1, x0:x1]
    edge = np.zeros(code.shape, dtype=bool)
    edge[:, :-1] |= code[:, :-1] != code[:, 1:]
    edge[:-1, :] |= code[:-1, :] != code[1:, :]
    tile = np.full(code.shape + (3,), 235, dtype=np.uint8)
    tile[edge] = (110, 110, 110)
    base = Image.fromarray(tile).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)

    def tf(pt):
        return ((pt[0] - x0) * scale + scale // 2, (pt[1] - y0) * scale + scale // 2)

    items = []
    for n, c, r in sel:
        note = r.get("comment", "")
        items.append((tf(c.start), tf(c.stop), f"{n} {note}" if note else str(n),
                      bool(r.get("type"))))
    img = _render_numbered(rgb, items, base=base, scale=scale)
    if out.exists():
        out.unlink()
    img.save(out)
    print(f"wrote {out.relative_to(MOD_ROOT)} (rows {rows_wanted}, {img.size[0]}x{img.size[1]})")
    return 0


def as_filled(path: Path, out: Path) -> int:
    """Render a worksheet file exactly as written: rows in FILE order at their stored
    coordinates, numbered by row, with each row's note. No matching to today's lines,
    so it shows the numbering the worksheet was filled against."""
    rgb = raster.read_rgb_png(PROVINCES_PNG)
    raw = json.loads(path.read_text(encoding="utf-8")).get("adjacencies", [])
    items = []
    for i, r in enumerate(raw, 1):
        note = r.get("comment", "")
        items.append((tuple(r["a"]), tuple(r["b"]), f"{i} {note}" if note else str(i),
                      bool(r.get("type"))))
    img = _render_numbered(rgb, items)
    if out.exists():
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"wrote {out.relative_to(MOD_ROOT)} ({len(items)} rows, file order)")
    return 0


def review() -> int:
    from types import SimpleNamespace

    # Read the worksheet leniently (raw JSON, like --sync) so an invalid or blank row
    # never blocks the review; invalid types are reported below.
    crossings, skipped, lines, _, rgb, _ = derive(need_worksheet=False, load_rows=False)
    h, w = rgb.shape[:2]
    names = _state_names()
    raw = (json.loads(WORKSHEET.read_text(encoding="utf-8")).get("adjacencies", [])
           if WORKSHEET.is_file() else [])
    synced, _stale, errors, _stats = adj.sync_worksheet(crossings, raw, w)
    if errors:
        synced = [{"type": "", "comment": ""}] * len(crossings)
    pairs = [(c, SimpleNamespace(type=r.get("type", ""), comment=r.get("comment", "")))
             for c, r in zip(crossings, synced)]
    untyped = [c for c, r in pairs if not r.type]
    typed = {id(c) for c, r in pairs if r.type}
    for c, r in pairs:
        if r.type and not schema._ADJ_TYPE_RE.fullmatch(r.type):
            print(f"  INVALID type {r.type!r} ({r.comment!r}) near {list(c.start)}")
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    with open(TABLE_PATH, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["number", "From", "To", "from_state", "to_state", "start_x", "start_y",
                     "stop_x", "stop_y", "Type", "Comment"])
        for i, c in enumerate(crossings, 1):
            row = next((r for cc, r in pairs if cc is c), None)
            wr.writerow([i, adj.color_token(c.from_color), adj.color_token(c.to_color),
                         names.get(c.from_color, ""), names.get(c.to_color, ""),
                         *c.start, *c.stop, row.type if row else "", row.comment if row else ""])

    img = _render_numbered(rgb, [(c.start, c.stop,
                                  f"{i} {pairs[i - 1][1].comment}" if pairs[i - 1][1].comment else str(i),
                                  id(c) in typed) for i, c in enumerate(crossings, 1)], skipped)
    if PREVIEW_PATH.exists():
        PREVIEW_PATH.unlink()  # a viewer holding the old file otherwise breaks the save
    img.save(PREVIEW_PATH)

    print(f"{len(lines)} drawn line(s): {len(crossings)} resolved, {len(skipped)} skipped, "
          f"{len(untyped)} untyped (no worksheet row)")
    for s in skipped:
        print(f"  SKIP near {list(s.centroid)}: {s.reason}")
    for e in errors:
        print(f"  WORKSHEET: {e}")
    print(f"wrote {TABLE_PATH.relative_to(MOD_ROOT)}, {PREVIEW_PATH.relative_to(MOD_ROOT)}")
    print("run --sync to carry the worksheet over to these lines (adds blank rows for new ones)")
    return 0


def sync() -> int:
    """Rewrite the worksheet in place so it matches the lines as drawn now, keeping
    every typed row (endpoints refreshed), appending blank stubs for new lines and
    parking unmatched rows under ``stale`` instead of deleting them."""
    crossings, skipped, _, _, rgb, _ = derive(need_worksheet=False, load_rows=False)
    h, w = rgb.shape[:2]
    data = json.loads(WORKSHEET.read_text(encoding="utf-8")) if WORKSHEET.is_file() else {}
    raw = data.get("adjacencies", [])
    rows, stale, errors, stats = adj.sync_worksheet(crossings, raw, w)
    if errors:
        print("refusing to sync - ambiguous matches (worksheet left untouched):")
        for e in errors:
            print("  " + e)
        return 1
    bad = [i for i, r in enumerate(rows)
           if r.get("type") and not schema._ADJ_TYPE_RE.fullmatch(r["type"])]
    out = {"adjacencies": rows}
    parked = list(data.get("stale", [])) + stale
    if parked:
        out["stale"] = parked
    text = json.dumps(out, indent=2) + "\n"
    if not WORKSHEET.is_file() or WORKSHEET.read_text(encoding="utf-8") != text:
        WORKSHEET.write_text(text, encoding="utf-8")
    print(f"synced {WORKSHEET.relative_to(MOD_ROOT)}: {stats['kept']} kept "
          f"({stats['moved']} endpoints refreshed), {stats['new']} new blank row(s), "
          f"{stats['stale']} unmatched row(s) parked under 'stale'")
    for r in stale:
        print(f"  parked: {r.get('a')}->{r.get('b')} type={r.get('type')!r} "
              f"comment={r.get('comment')!r}")
    untyped = [i + 1 for i, r in enumerate(rows) if not r.get("type")]
    if untyped:
        print(f"  untyped rows (numbers as in the review table): {untyped}")
    for i in bad:
        print(f"  INVALID type on row {i + 1}: {rows[i]['type']!r} "
              f"(comment {rows[i].get('comment')!r})")
    for s in skipped:
        print(f"  SKIP near {list(s.centroid)}: {s.reason}")
    return 0


def build_csv() -> tuple[str, list[str], list]:
    crossings, skipped, _, rows, rgb, kinds = derive(need_worksheet=True)
    h, w = rgb.shape[:2]
    pairs, untyped, errors = adj.match_worksheet(crossings, rows, w)
    errors += adj.type_kind_errors(pairs, kinds)
    return adj.emit_csv(pairs, h), errors, untyped


def build_straits() -> tuple[str, str, list[str]]:
    """Derive ``common/strait_definitions/canals.txt`` + the canal loc file text
    from the same worksheet-matched crossings :func:`build_csv` uses (board
    #5744). Returns ``(straits_text, loc_text, notes)`` — ``notes`` lists a
    ``canal_*`` row with no resolvable land pair (reported, never an error here;
    the existing ``_check_adjacency_rows`` validator is what turns that into a
    real, blocking failure once the full offline gate runs)."""
    crossings, _, _, rows, rgb, _ = derive(need_worksheet=True)
    w = rgb.shape[1]
    pairs, _, errors = adj.match_worksheet(crossings, rows, w)
    if errors:
        return "", "", []
    blocks: dict[str, tuple] = {}
    notes: list[str] = []
    for c, row in pairs:
        if not row.type.startswith("canal_"):
            continue
        land = c.land_pair
        if land is None and row.land_a_color is not None and row.land_b_color is not None:
            land = tuple(sorted((row.land_a_color, row.land_b_color), key=adj.color_code))
        if land is None:
            notes.append(f"{row.type}: no land endpoints yet (draw it as a '+'/'X' junction, "
                         "or pin land_a_color/land_b_color in the worksheet)")
            continue
        blocks[row.type] = (c.from_color, c.to_color, land, row.strait_type, row.comment)

    def render_block(canal_id: str) -> str:
        sea_a, sea_b, (land_a, land_b), strait_type, _comment = blocks[canal_id]
        return "\n".join([
            f"{canal_id} = {{",
            f"{INDENT}type = {strait_type}",
            "",
            f"{INDENT}total_block_requires_full_control = no",
            f"{INDENT}military_block_requires_full_control = no",
            "",
            f"{INDENT}first_land_endpoint = {adj.color_token(land_a)}",
            f"{INDENT}second_land_endpoint = {adj.color_token(land_b)}",
            "",
            f"{INDENT}first_sea_endpoint = {adj.color_token(sea_a)}",
            f"{INDENT}second_sea_endpoint = {adj.color_token(sea_b)}",
            "}",
        ])

    straits_text = ("\n\n".join(render_block(cid) for cid in sorted(blocks)) + "\n"
                    if blocks else "")
    loc_lines = ["l_english:"]
    for canal_id in sorted(blocks):
        name = blocks[canal_id][4].replace('"', "'")
        loc_lines.append(f' {canal_id}:0 "{name}"')
    loc_text = "\n".join(loc_lines) + "\n" if blocks else ""
    return straits_text, loc_text, notes


def write(check: bool) -> int:
    if not schema.load_adjacency_worksheet(WORKSHEET):
        raise SystemExit(f"{WORKSHEET.name} has no rows - fill it from the --review stubs first")
    text, errors, untyped = build_csv()
    if errors:
        print("refusing to write - worksheet problems:")
        for e in errors:
            print("  " + e)
        return 1
    straits_text, loc_text, notes = build_straits()
    data = text.encode("utf-8")  # LF, no BOM, no trailing newline
    straits_data = BOM + straits_text.encode("utf-8")
    loc_data = BOM + loc_text.encode("utf-8")
    if check:
        cur = CSV_PATH.read_bytes() if CSV_PATH.is_file() else b""
        cur_straits = STRAITS_PATH.read_bytes() if STRAITS_PATH.is_file() else b""
        cur_loc = CANAL_LOC_PATH.read_bytes() if CANAL_LOC_PATH.is_file() else b""
        stale = []
        if cur != data:
            stale.append(str(CSV_PATH.relative_to(MOD_ROOT)))
        if cur_straits != straits_data:
            stale.append(str(STRAITS_PATH.relative_to(MOD_ROOT)))
        if cur_loc != loc_data:
            stale.append(str(CANAL_LOC_PATH.relative_to(MOD_ROOT)))
        if stale:
            print("stale - re-run generate_adjacencies.py --write: " + ", ".join(stale))
            return 1
        print("adjacencies.csv, strait_definitions and canal loc match the worksheet + drawn lines")
        return 0
    if untyped:
        print(f"note: {len(untyped)} drawn line(s) have no worksheet row and are omitted")
    for note in notes:
        print(f"note: {note}")
    if not CSV_PATH.is_file() or CSV_PATH.read_bytes() != data:
        CSV_PATH.write_bytes(data)
        n_rows = data.count(b"\n")
        print(f"wrote {CSV_PATH.relative_to(MOD_ROOT)} ({n_rows} row(s))")
    else:
        print("adjacencies.csv unchanged")
    if not STRAITS_PATH.is_file() or STRAITS_PATH.read_bytes() != straits_data:
        _write_bytes(STRAITS_PATH, straits_text, bom=True)
        print(f"wrote {STRAITS_PATH.relative_to(MOD_ROOT)}")
    else:
        print(f"{STRAITS_PATH.relative_to(MOD_ROOT)} unchanged")
    if not CANAL_LOC_PATH.is_file() or CANAL_LOC_PATH.read_bytes() != loc_data:
        _write_bytes(CANAL_LOC_PATH, loc_text, bom=True)
        print(f"wrote {CANAL_LOC_PATH.relative_to(MOD_ROOT)}")
    else:
        print(f"{CANAL_LOC_PATH.relative_to(MOD_ROOT)} unchanged")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--review", action="store_true", help="table + stubs + numbered render (default)")
    g.add_argument("--zoom", metavar="ROWS", help="comma-separated table numbers to render zoomed in")
    g.add_argument("--as-filled", metavar="WORKSHEET",
                   help="render a worksheet file in FILE order at its stored coordinates")
    g.add_argument("--sync", action="store_true",
                   help="carry the worksheet over to the current lines (keeps typed rows, adds blanks)")
    g.add_argument("--write", action="store_true", help="write map_data/adjacencies.csv")
    g.add_argument("--check", action="store_true", help="assert the committed CSV is current")
    a = ap.parse_args(argv)
    if a.zoom:
        rows_ = [int(v) for v in a.zoom.split(",")]
        return zoom(rows_, DERIVED_DIR / f"adjacencies_zoom_{'_'.join(map(str, rows_))}.png")
    if a.as_filled:
        return as_filled(Path(a.as_filled), DERIVED_DIR / "adjacencies_as_filled.png")
    if a.sync:
        return sync()
    if a.write or a.check:
        return write(check=a.check)
    return review()


if __name__ == "__main__":
    raise SystemExit(main())
