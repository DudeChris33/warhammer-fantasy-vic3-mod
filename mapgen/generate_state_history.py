#!/usr/bin/env python3
"""Write starting state ownership into ``common/history/states/NN_*.txt``.

Reads ``mapgen/derived/state_ownership.json`` (``read_state_ownership.py``),
the land ``map_data/state_regions/NN_*.txt`` and the tags defined in
``common/country_definitions/*.txt``, and writes one history file per land
state-region file, same name, in the vanilla
``STATES = { s:STATE_X = { create_state = { country = c:TAG owned_provinces = { ... } } } }``
shape. Rules (placeholder / unowned states, splits, held-back undefined tags,
stable ordering) are in ``worldgen/state_history.py``.

Runs after ``generate_land_regions.py`` and ``read_state_ownership.py``: a
province or land-region regen stales the ownership JSON, which must be re-read
first (it may hard-error and need a repaint). Output is UTF-8 with a BOM and LF
endings, like the sibling generated map files. A generated file set: never
hand-edit it.

Usage::

    python mapgen/generate_state_history.py           # write common/history/states/NN_*.txt
    python mapgen/generate_state_history.py --check   # exit 1 if any file is stale (BOM/CRLF-insensitive)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import state_history as sh  # noqa: E402
from worldgen.state_ownership import OwnershipError  # noqa: E402

MOD_ROOT = Path(__file__).resolve().parent.parent
OWNERSHIP_PATH = MOD_ROOT / "mapgen" / "derived" / "state_ownership.json"
STATE_REGIONS_DIR = MOD_ROOT / "map_data" / "state_regions"
COUNTRY_DEFS_DIR = MOD_ROOT / "common" / "country_definitions"
OUT_DIR = MOD_ROOT / "common" / "history" / "states"
BOM = b"\xef\xbb\xbf"


def build(ownership: Path, state_regions: Path, country_defs: Path) -> sh.Plan:
    doc = json.loads(ownership.read_text(encoding="utf-8"))
    return sh.plan(doc, sh.load_states_by_file(state_regions), sh.load_country_tags(country_defs))


def summary(p: sh.Plan) -> str:
    emitted = sum(len(e) for e in p.files.values())
    header_only = sum(1 for e in p.files.values() if not e)
    lines = [f"{len(p.files)} files ({header_only} header-only), {emitted} states owned, "
             f"{p.create_states} create_state blocks; {len(p.unowned)} unowned, "
             f"{len(p.placeholder)} placeholder, {len(p.held_back)} held back"]
    by_tag: dict[str, list[str]] = {}
    for key, tag in p.held_back:
        by_tag.setdefault(tag, []).append(key)
    for tag in sorted(by_tag):
        lines.append(f"  held back (c:{tag} undefined): {', '.join(by_tag[tag])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ownership", type=Path, default=OWNERSHIP_PATH)
    ap.add_argument("--state-regions", type=Path, default=STATE_REGIONS_DIR)
    ap.add_argument("--country-definitions", type=Path, default=COUNTRY_DEFS_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--check", action="store_true", help="assert the files on disk are current; write nothing")
    args = ap.parse_args(argv)
    try:
        p = build(args.ownership, args.state_regions, args.country_definitions)
    except OwnershipError as exc:
        print(f"generate_state_history: ERROR: {exc}", file=sys.stderr)
        return 1
    texts = {fname: sh.render_file(entries) for fname, entries in p.files.items()}
    if args.check:
        stale = []
        for fname, text in texts.items():
            path = args.out_dir / fname
            current = sh.normalize_text(path.read_bytes().decode("utf-8")) if path.is_file() else None
            if current != text:
                stale.append(fname)
        if stale:
            print(f"generate_state_history: stale: {', '.join(stale)} -- re-run without --check", file=sys.stderr)
            return 1
        print(f"generate_state_history: output is current. {summary(p)}")
        return 0
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for fname, text in texts.items():
        (args.out_dir / fname).write_bytes(BOM + text.encode("utf-8"))
    print(f"generate_state_history: wrote {args.out_dir}: {summary(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
