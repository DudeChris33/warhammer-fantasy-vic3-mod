#!/usr/bin/env python3
"""Write starting state ownership into ``common/history/states/NN_*.txt``.

Reads ``mapgen/derived/state_ownership.json`` (``read_state_ownership.py``),
the land ``map_data/state_regions/NN_*.txt`` and the tags defined in
``common/country_definitions/*.txt``, and writes one history file per land
state-region file, same name, in the vanilla
``STATES = { s:STATE_X = { create_state = { country = c:TAG owned_provinces = { ... } } } }``
shape, plus ``add_homeland = cu:<culture>`` lines taken only from the hand-authored
``mapgen/config/state_homelands.json`` and checked against ``common/cultures`` (#8604). Unowned and
out-of-scope placeholder land goes to ``c:UNO`` (Unclaimed Lands, #6391). Rules
(the UNO token mapping, splits, held-back undefined tags, homelands, stable
ordering) are in ``worldgen/state_history.py``.

Runs after ``generate_land_regions.py`` and ``read_state_ownership.py``: a
province or land-region regen stales the ownership JSON, which must be re-read
first (it may hard-error and need a repaint). Output is UTF-8 with a BOM and LF
endings, like the sibling generated map files. A generated file set: never
hand-edit it.

Usage::

    python mapgen/generate_state_history.py           # write common/history/states/NN_*.txt
    python mapgen/generate_state_history.py --check   # exit 1 if any file is stale (BOM/CRLF-insensitive)
    python mapgen/generate_state_history.py --seed-homelands [--force]   # first-time write of state_homelands.json from owner cultures
    python mapgen/generate_state_history.py --sync-homelands             # after a regen: add new states, move unambiguous renames

``--seed-homelands`` refuses to overwrite an existing config without ``--force``. ``--sync-homelands``
never deletes a row or touches an existing row's cultures, and exits 1 while stale rows remain. Neither
writes history files; run the generator afterwards.
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
CULTURES_DIR = MOD_ROOT / "common" / "cultures"
HOMELANDS_PATH = MOD_ROOT / "mapgen" / "config" / "state_homelands.json"
OUT_DIR = MOD_ROOT / "common" / "history" / "states"
BOM = b"\xef\xbb\xbf"


def build(ownership: Path, state_regions: Path, country_defs: Path, cultures: Path = CULTURES_DIR,
          homelands: Path = HOMELANDS_PATH) -> sh.Plan:
    doc = json.loads(ownership.read_text(encoding="utf-8"))
    by_file = sh.load_states_by_file(state_regions)
    if not homelands.is_file():
        raise OwnershipError(f"{homelands} not found -- run generate_state_history.py --seed-homelands")
    config = sh.load_homelands(homelands)
    # the same gate validate_map runs: full coverage, matching anchors, defined culture ids
    errors, _ = sh.check_homelands(config, doc, by_file, sh.load_culture_ids(cultures))
    if errors:
        raise OwnershipError("state_homelands.json is out of line:\n  " + "\n  ".join(errors))
    return sh.plan(doc, by_file, sh.load_country_tags(country_defs), config)


def sync(args) -> int:
    """``--seed-homelands`` / ``--sync-homelands``: write the config, never history files."""
    doc = json.loads(args.ownership.read_text(encoding="utf-8"))
    by_file = sh.load_states_by_file(args.state_regions)
    existing = None
    if args.seed_homelands:
        if args.homelands.is_file() and not args.force:
            print(f"generate_state_history: ERROR: {args.homelands} exists; --force overwrites it "
                  "(and discards every hand edit)", file=sys.stderr)
            return 1
    else:
        if not args.homelands.is_file():
            print(f"generate_state_history: ERROR: {args.homelands} not found -- run --seed-homelands",
                  file=sys.stderr)
            return 1
        existing = sh.load_homelands(args.homelands)
    rows, report = sh.sync_homelands(existing, doc, by_file, sh.load_country_tags(args.country_definitions),
                                     sh.load_country_cultures(args.country_definitions))
    args.homelands.write_bytes(sh.dump_homelands(rows).encode("utf-8"))
    print(f"generate_state_history: wrote {args.homelands}: {len(rows)} rows; "
          f"{len(report['added'])} added, {len(report['rekeyed'])} rekeyed, {len(report['adopted'])} anchors adopted")
    for label in ("added", "rekeyed", "adopted"):
        if report[label] and not args.seed_homelands:
            print(f"  {label}: {', '.join(report[label])}")
    if report["stale"]:
        print(f"generate_state_history: ERROR: {len(report['stale'])} stale row(s) match no land state and were "
              f"left in place -- move or delete by hand: {', '.join(report['stale'])}", file=sys.stderr)
        return 1
    return 0


def summary(p: sh.Plan) -> str:
    emitted = sum(len(e) for e in p.files.values())
    header_only = sum(1 for e in p.files.values() if not e)
    lines = [f"{len(p.files)} files ({header_only} header-only), {emitted} states owned, "
             f"{p.create_states} create_state blocks; {len(p.unowned)} unowned + "
             f"{len(p.placeholder)} placeholder -> c:{sh.UNO_TAG}, {len(p.held_back)} held back; "
             f"{len(p.homelands)} states with homelands ({sum(len(h) for h in p.homelands.values())} add_homeland)"]
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
    ap.add_argument("--cultures-dir", type=Path, default=CULTURES_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--homelands", type=Path, default=HOMELANDS_PATH)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--seed-homelands", action="store_true",
                      help="write state_homelands.json from the owners' cultures (first time only)")
    mode.add_argument("--sync-homelands", action="store_true",
                      help="add new states and carry unambiguous renames over; never deletes or edits a row")
    ap.add_argument("--force", action="store_true", help="with --seed-homelands: overwrite an existing config")
    ap.add_argument("--check", action="store_true", help="assert the files on disk are current; write nothing")
    args = ap.parse_args(argv)
    if args.seed_homelands or args.sync_homelands:
        try:
            return sync(args)
        except OwnershipError as exc:
            print(f"generate_state_history: ERROR: {exc}", file=sys.stderr)
            return 1
    try:
        p = build(args.ownership, args.state_regions, args.country_definitions, args.cultures_dir, args.homelands)
    except OwnershipError as exc:
        print(f"generate_state_history: ERROR: {exc}", file=sys.stderr)
        return 1
    texts = {fname: sh.render_file(entries, p.homelands) for fname, entries in p.files.items()}
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
