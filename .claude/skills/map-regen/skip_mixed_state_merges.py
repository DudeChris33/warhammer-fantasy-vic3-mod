#!/usr/bin/env python3
"""Run generate_provinces.py, dropping every state_merges line that joins in-scope land to
out-of-scope (placeholder) land, and print each line it drops.

This is a per-run exemption: use it only when Chris says to skip those lines for this run
("skip them again" is a new instruction each run). It changes nothing in the repo. The real
fix is the generator's in/out-of-scope rule, which still rejects lines Chris considers fine.
"""
import inspect
import sys
from pathlib import Path

import numpy as np

MAPGEN = Path(__file__).resolve().parents[3] / "mapgen"
sys.path.insert(0, str(MAPGEN))

from worldgen import land_provinces as lp  # noqa: E402

rec = []  # (x, y, region) per resolve_anchor call, in call order (line ends, interleaved with hub lookups)
_orig_resolve = lp.resolve_anchor


def _resolve(reg, x, y, r, *a, **k):
    out = _orig_resolve(reg, x, y, r, *a, **k)
    rec.append((int(x), int(y), int(out[0])))
    return out


_orig_groups = lp.state_merge_groups


def _groups(n_reg, pairs):
    loc = inspect.currentframe().f_back.f_locals  # generate_provinces.main's locals
    reg_ph = np.zeros(n_reg + 1, dtype=bool)
    reg_ph[loc["reg_of"][1:]] = loc["is_placeholder"][1:loc["n_land"] + 1]
    lines = [(rec[i], rec[i + 1]) for i in range(len(rec) - 1)]
    keep = []
    for p in pairs:
        if reg_ph[p[0]] != reg_ph[p[1]]:
            ends = [(a[:2], b[:2]) for a, b in lines if {a[2], b[2]} == {p[0], p[1]}]
            print("SKIPPED mixed state_merges line, regions", p, "ends", ends[:2])
            continue
        keep.append(p)
    return _orig_groups(n_reg, keep)


lp.resolve_anchor = _resolve
lp.state_merge_groups = _groups

import generate_provinces as gp  # noqa: E402

sys.exit(gp.main())
