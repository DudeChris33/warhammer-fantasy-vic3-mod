#!/usr/bin/env python3
"""Check that every good a tag taxes is produced in its own market at the start (#6638 phase A).

Reads the resolved starting packages (``mapgen/config/country_history``), the emitted
``common/history/buildings`` (so run it after ``generate_building_history.py``), the state
subsistence buildings in ``map_data/state_regions`` and the production methods. Rules and the
market definition are in ``worldgen/taxed_goods.py``. Exit 1 on any taxed good with no producer.

Usage::

    python mapgen/validate_taxed_goods.py
    python mapgen/validate_taxed_goods.py --summary     # failures grouped by good
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import building_history as bh  # noqa: E402
from worldgen import country_config as cc  # noqa: E402
from worldgen import taxed_goods as tg  # noqa: E402

MOD_ROOT = Path(__file__).resolve().parent.parent


def run(root: Path, summary: bool = False) -> tuple[int, str]:
    resolved = cc.load_resolved(root / "mapgen" / "config" / "country_history")
    if resolved is None:
        return 1, "validate_taxed_goods: no mapgen/config/country_history data\n"
    world = bh.load_world(root)
    outputs = tg.load_pm_outputs(root / "common" / "production_methods")
    sub = tg.load_subsistence(root / "map_data" / "state_regions")
    texts = {p.name: p.read_text(encoding="utf-8-sig") for p in sorted((root / "common" / "history" / "buildings").glob("*.txt"))}
    produced = tg.produced_goods(world, outputs, sub, texts)
    taxed = {t: r.package.get("taxed_goods", []) for t, r in resolved.items() if t in {x for tags in world.owners.values() for x in tags}}
    errors = tg.check(taxed, produced)
    lines: list[str] = []
    if summary and errors:
        by: dict[str, int] = {}
        for e in errors:
            good = e.split(" taxes ")[1].split(" ")[0]
            by[good] = by.get(good, 0) + 1
        lines += [f"{n} tag(s) tax {g} with no producer" for g, n in sorted(by.items())]
    lines += [f"ERROR: {e}" for e in errors]
    lines.append(f"validate_taxed_goods: {sum(len(v) for v in taxed.values())} taxed good(s) over {len(taxed)} owner(s), "
                 f"{len(errors)} without a producer")
    return (1 if errors else 0), "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=MOD_ROOT)
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args(argv)
    code, report = run(args.root, args.summary)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
