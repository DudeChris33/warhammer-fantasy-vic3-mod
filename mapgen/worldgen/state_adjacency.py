"""State land adjacency (``PAIR_RULE`` = ``passable-contact``), shared by the route-network writer and the
starting-buildings generator (#10453).

Two land states are adjacent when a passable province of one shares a pixel edge with a passable province of the
other (4-neighbourhood; x wraps under ``map_config.WRAP_X``). Pairs touching only through impassable provinces get
no link. This is the rule ``generate_spline_network.py`` was matched to the engine with on 2026-10-29, so a "piece"
of an owner's land here is a piece the engine's travel graph also sees as connected.

Pure functions of ``map_data/provinces.png`` and ``map_data/state_regions/*.txt``; no clock, nothing random.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from config import map_config
from .raster import read_rgb_png

PAIR_RULE = "passable-contact"


def hex_code(h: str) -> int:
    return int(h.lstrip("xX"), 16)


def parse_state_files(state_dir: Path) -> tuple[dict[int, dict], dict[int, dict]]:
    """``(land, sea)`` as ``{state id: {"key": STATE_X, "provinces": [...], "impassable": set}}`` (provinces as ints)."""
    land: dict[int, dict] = {}
    sea: dict[int, dict] = {}
    for f in sorted(state_dir.glob("*.txt")):
        text = f.read_text(encoding="utf-8-sig")
        for m in re.finditer(r"(STATE_\w+)\s*=\s*\{(.*?)\n\}", text, re.S):
            body = m.group(2)
            sid = int(re.search(r"\bid\s*=\s*(\d+)", body).group(1))
            provs = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", body).group(1).replace('"', "").split()
            imp = re.search(r"\bimpassable\s*=\s*\{([^}]*)\}", body)
            rec = {
                "key": m.group(1),
                "provinces": [hex_code(p) for p in provs],
                "impassable": {hex_code(p) for p in imp.group(1).replace('"', "").split()} if imp else set(),
            }
            target = sea if f.name.startswith("99_") else land
            if sid in land or sid in sea:
                raise SystemExit(f"duplicate state id {sid}")
            target[sid] = rec
    return land, sea


def state_rasters(provinces_png: Path, land: dict[int, dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(land_state, passable_state, impassable)`` per pixel: the state id (0 off land), the state id on passable
    provinces only (0 also on impassable ones), and the impassable-province mask."""
    rgb = read_rgb_png(provinces_png)
    code = (rgb[..., 0].astype(np.int64) << 16) | (rgb[..., 1].astype(np.int64) << 8) | rgb[..., 2]
    uniq, inv = np.unique(code.ravel(), return_inverse=True)
    lut_all = np.zeros(len(uniq), dtype=np.int32)
    lut_pass = np.zeros(len(uniq), dtype=np.int32)
    lut_imp = np.zeros(len(uniq), dtype=bool)
    pos = {int(c): i for i, c in enumerate(uniq.tolist())}
    for sid, rec in land.items():
        for p in rec["provinces"]:
            i = pos.get(p)
            if i is None:
                raise SystemExit(f"state {sid}: province x{p:06X} is not in provinces.png")
            lut_all[i] = sid
            if p in rec["impassable"]:
                lut_imp[i] = True
            else:
                lut_pass[i] = sid
    inv = inv.reshape(code.shape)
    return lut_all[inv], lut_pass[inv], lut_imp[inv]


def passable_state_raster(provinces_png: Path, land: dict[int, dict]) -> np.ndarray:
    """State id per pixel, 0 off land and on impassable provinces (the raster ``adjacent_pairs`` reads)."""
    return state_rasters(provinces_png, land)[1]


def adjacent_pairs(passable_state: np.ndarray) -> list[tuple[int, int]]:
    """State pairs sharing a pixel edge between passable provinces (x wraps under WRAP_X)."""
    s = passable_state
    parts = [(s[:, :-1], s[:, 1:]), (s[:-1, :], s[1:, :])]
    if map_config.WRAP_X:
        parts.append((s[:, -1:], s[:, :1]))
    found: set[int] = set()
    for a, b in parts:
        m = (a != b) & (a > 0) & (b > 0)
        lo = np.minimum(a[m], b[m]).astype(np.int64)
        hi = np.maximum(a[m], b[m]).astype(np.int64)
        found.update(np.unique((lo << 32) | hi).tolist())
    return sorted((p >> 32, p & 0xFFFFFFFF) for p in found)


def state_neighbours(root: Path) -> dict[str, set[str]]:
    """``{STATE_KEY: {neighbour STATE_KEYs}}`` over the land states under ``root`` (mod root), by ``PAIR_RULE``."""
    land, _ = parse_state_files(root / "map_data" / "state_regions")
    passable = passable_state_raster(root / "map_data" / "provinces.png", land)
    out: dict[str, set[str]] = {rec["key"]: set() for rec in land.values()}
    for a, b in adjacent_pairs(passable):
        ka, kb = land[a]["key"], land[b]["key"]
        out[ka].add(kb)
        out[kb].add(ka)
    return out
