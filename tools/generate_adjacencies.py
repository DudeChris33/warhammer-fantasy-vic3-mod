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


def review() -> int:
    from PIL import Image, ImageDraw, ImageFont

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

    # Numbered render over dim province edges.
    code = _code_map(rgb)
    edge = np.zeros(code.shape, dtype=bool)
    edge[:, :-1] |= code[:, :-1] != code[:, 1:]
    edge[:-1, :] |= code[:-1, :] != code[1:, :]
    img_arr = np.full(rgb.shape, 235, dtype=np.uint8)
    img_arr[edge] = (150, 150, 150)
    img = Image.fromarray(img_arr)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=28)
    except TypeError:
        font = ImageFont.load_default()
    # Draw every line first, then place the numbers so no two labels (nor a label and
    # any line endpoint) overlap: try 8 directions at growing distances around the
    # line's midpoint and take the first free box; a leader line joins a far label.
    for c in crossings:
        col = (0, 140, 0) if id(c) in typed else (220, 0, 0)
        d.line([c.start, c.stop], fill=col, width=5)
        for pt in (c.start, c.stop):
            d.ellipse([pt[0] - 6, pt[1] - 6, pt[0] + 6, pt[1] + 6], fill=col)
    pad = 4
    taken: list[tuple[int, int, int, int]] = [
        (pt[0] - 10, pt[1] - 10, pt[0] + 10, pt[1] + 10)
        for c in crossings for pt in (c.start, c.stop)]

    def _hits(box, others):
        return any(box[0] < o[2] and o[0] < box[2] and box[1] < o[3] and o[1] < box[3]
                   for o in others)

    dirs = [(1, -1), (1, 1), (-1, -1), (-1, 1), (0, -1), (0, 1), (1, 0), (-1, 0)]
    for i, c in enumerate(crossings, 1):
        col = (0, 140, 0) if id(c) in typed else (220, 0, 0)
        text = str(i)
        l, t, r, b = d.textbbox((0, 0), text, font=font, stroke_width=3)
        tw, th = r - l, b - t
        mx, my = (c.start[0] + c.stop[0]) // 2, (c.start[1] + c.stop[1]) // 2
        placed = None
        for dist in range(14, 400, 10):
            for dx, dy in dirs:
                cx, cy = mx + dx * dist, my + dy * dist
                box = (cx - tw // 2 - pad, cy - th // 2 - pad, cx + tw // 2 + pad, cy + th // 2 + pad)
                if not _hits(box, taken):
                    placed = (cx, cy, box)
                    break
            if placed:
                break
        if placed is None:  # pathological crowding: fall back to a fixed offset
            cx, cy = mx + 14, my - 14
            placed = (cx, cy, (cx - tw // 2, cy - th // 2, cx + tw // 2, cy + th // 2))
        cx, cy, box = placed
        taken.append(box)
        if max(abs(cx - mx), abs(cy - my)) > 30:
            d.line([(mx, my), (cx, cy)], fill=col, width=2)
        d.text((cx - tw // 2 - l, cy - th // 2 - t), text, fill=(0, 0, 0), font=font,
               stroke_width=3, stroke_fill=(255, 255, 255))
    for s in skipped:
        d.ellipse([s.centroid[0] - 14, s.centroid[1] - 14, s.centroid[0] + 14, s.centroid[1] + 14],
                  outline=(255, 120, 0), width=4)
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


def write(check: bool) -> int:
    if not schema.load_adjacency_worksheet(WORKSHEET):
        raise SystemExit(f"{WORKSHEET.name} has no rows - fill it from the --review stubs first")
    text, errors, untyped = build_csv()
    if errors:
        print("refusing to write - worksheet problems:")
        for e in errors:
            print("  " + e)
        return 1
    data = text.encode("utf-8")  # LF, no BOM, no trailing newline
    if check:
        cur = CSV_PATH.read_bytes() if CSV_PATH.is_file() else b""
        if cur != data:
            print("adjacencies.csv is stale - re-run generate_adjacencies.py --write")
            return 1
        print("adjacencies.csv matches the worksheet + drawn lines")
        return 0
    if untyped:
        print(f"note: {len(untyped)} drawn line(s) have no worksheet row and are omitted")
    if not CSV_PATH.is_file() or CSV_PATH.read_bytes() != data:
        CSV_PATH.write_bytes(data)
        n_rows = data.count(b"\n")
        print(f"wrote {CSV_PATH.relative_to(MOD_ROOT)} ({n_rows} row(s))")
    else:
        print("adjacencies.csv unchanged")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--review", action="store_true", help="table + stubs + numbered render (default)")
    g.add_argument("--sync", action="store_true",
                   help="carry the worksheet over to the current lines (keeps typed rows, adds blanks)")
    g.add_argument("--write", action="store_true", help="write map_data/adjacencies.csv")
    g.add_argument("--check", action="store_true", help="assert the committed CSV is current")
    a = ap.parse_args(argv)
    if a.sync:
        return sync()
    if a.write or a.check:
        return write(check=a.check)
    return review()


if __name__ == "__main__":
    raise SystemExit(main())
