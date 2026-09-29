#!/usr/bin/env python3
"""One-time migration: seed ``mapgen/derived/land_state_ids.json`` from the
already-committed ``map_data/state_regions/*.txt`` (board #4188).

:mod:`worldgen.land_state_numbering`'s new :func:`assign_state_numbers`
matches the *current* regen's regions against a committed identity record to
decide which STATE number survives. Before this item there was no such
record — the previous generator recomputed every number fresh every run
(:func:`worldgen.land_state_numbering.compute_state_numbers`). Bootstrapping
:func:`assign_state_numbers` from scratch on the next regen (i.e. treating
"no committed index" as "every region is new") would retire the already-
shipped numbers and detach every worksheet-carried canon name from its
region — exactly the failure this item exists to prevent.

Instead this script reads the numbers Victoria 3 has *already shipped*
straight out of the committed land ``state_regions/*.txt`` files (every
``STATE_… { id = N … provinces = { xHEX … } }`` block, land files only — never
``99_seas.txt``), maps each province hex to its **stable** id via the
committed ``mapgen/derived/provinces_index.json`` (the ``id`` field board
#3705 made stable), and writes the ``land_state_ids.json`` those numbers
imply. A regen run immediately afterwards then matches every unchanged region
against this seed and reproduces the committed files byte-for-byte (see
``.claude/rules/testing.md``'s land-state-ids verification step).

Reads from a git ref (``HEAD`` by default) via ``git show <ref>:<path>``
rather than the working tree, so it can seed the CLEAN committed baseline
even while a regen is in progress and the working tree's own
``state_regions/*.txt`` / ``provinces_index.json`` are already mid-edit
(exactly the situation this item was scoped in) — it never reads or touches
uncommitted work.

Usage::

    python mapgen/seed_land_state_ids.py [--ref HEAD] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
MOD_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
STATE_REGIONS_DIR = MOD_ROOT / "map_data" / "state_regions"
OUT_PATH = DERIVED_DIR / "land_state_ids.json"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: Land state files only — 99_seas.txt is the sea side and out of scope here.
LAND_STATE_FILE_RE = re.compile(r"^\d\d_\w+\.txt$")
SEA_STATE_FILENAME = "99_seas.txt"

#: One STATE block: ``STATE_NAME = {`` ... a line-start ``}`` closes it (every
#: nested block in these files, e.g. capped_resources, indents its own
#: closing brace, so an unindented "}" is unambiguously the top-level close).
_BLOCK_RE = re.compile(r"^STATE_(\w+)\s*=\s*\{\n(.*?)\n\}", re.MULTILINE | re.DOTALL)
#: `\b` before "id" excludes "naval_exit_id" (a word-boundary requires a
#: non-word character before "id", and "_" is a word character).
_ID_RE = re.compile(r"\bid\s*=\s*(\d+)")
_PROVINCES_RE = re.compile(r"provinces\s*=\s*\{([^}]*)\}")


def _git_show(ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"], cwd=MOD_ROOT,
        capture_output=True, check=True,
    )
    return result.stdout.decode("utf-8-sig")


def _git_ls_tree(ref: str, dir_path: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", ref, dir_path], cwd=MOD_ROOT,
        capture_output=True, check=True, text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _parse_state_file(text: str) -> list[tuple[int, list[str]]]:
    """``[(state_number, [province hex, ...]), ...]`` for every STATE block."""
    out = []
    for m in _BLOCK_RE.finditer(text):
        body = m.group(2)
        id_m = _ID_RE.search(body)
        prov_m = _PROVINCES_RE.search(body)
        if not id_m or not prov_m:
            raise SystemExit(f"STATE_{m.group(1)}: missing id or provinces field")
        state_number = int(id_m.group(1))
        hexes = prov_m.group(1).split()
        out.append((state_number, hexes))
    return out


def _build_index_from_texts(prov_index: dict, file_texts: dict[str, str]) -> dict:
    """Pure core of :func:`build_index` — no git, no filesystem. ``file_texts``
    is ``{filename: file content}`` for every land ``state_regions/*.txt`` to
    fold in. Split out so the parsing + hex-to-stable-id mapping is unit-
    testable on a small synthetic file without shelling out to git."""
    hex_to_id = {c["hex"]: int(c["id"]) for c in prov_index["cells"] if c["kind"] == "land"}

    states: dict[int, list[int]] = {}
    for filename in sorted(file_texts):
        for state_number, hexes in _parse_state_file(file_texts[filename]):
            if state_number in states:
                raise SystemExit(f"STATE number {state_number} defined twice "
                                 f"(last seen in {filename})")
            missing = [h for h in hexes if h not in hex_to_id]
            if missing:
                raise SystemExit(f"{filename}: STATE {state_number} province hex(es) not found "
                                 f"in provinces_index.json: {missing}")
            states[state_number] = sorted(hex_to_id[h] for h in hexes)

    high_water = (max(states) + 1) if states else int(map_config.LAND_ID_START)
    return {
        "canvas": [CANVAS_W, CANVAS_H],
        "state_number_high_water": high_water,
        "states": [
            {"state_number": n, "province_ids": states[n]}
            for n in sorted(states)
        ],
    }


def build_index(ref: str) -> dict:
    prov_index = json.loads(_git_show(ref, "mapgen/derived/provinces_index.json"))

    filenames = sorted(
        Path(p).name for p in _git_ls_tree(ref, "map_data/state_regions/")
        if LAND_STATE_FILE_RE.match(Path(p).name) and Path(p).name != SEA_STATE_FILENAME
    )
    if not filenames:
        raise SystemExit(f"no land state_regions/*.txt files found at ref {ref!r}")

    file_texts = {
        filename: _git_show(ref, f"map_data/state_regions/{filename}")
        for filename in filenames
    }
    return _build_index_from_texts(prov_index, file_texts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", default="HEAD",
                        help="git ref to seed from (default: HEAD, the clean committed baseline)")
    parser.add_argument("--dry-run", action="store_true",
                        help="parse and report, but do not write land_state_ids.json")
    args = parser.parse_args(argv)

    index = build_index(args.ref)
    print(f"seeded {len(index['states'])} land STATE number(s) from {args.ref} "
          f"(high-water {index['state_number_high_water']})")

    if args.dry_run:
        print("--dry-run: not writing", OUT_PATH)
        return 0

    if OUT_PATH.is_file():
        raise SystemExit(f"{OUT_PATH} already exists — this is a one-time migration; "
                         f"delete it first if you really mean to reseed")

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
