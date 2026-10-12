"""Author the real-world-equivalent economics inputs (Chris, 2026-10-12).

Reads (all local-only): ``sources/history/real-world-comparisons-f.png`` (the WHFB
map with Chris's red outlines), ``real-world-comparisons-r.png`` (vanilla's world
painted in zone colours) and the read-only vanilla install. Writes the two
committed inputs ``worldgen/real_world_economics.py`` consumes:

* ``mapgen/config/real_world_zones.png`` - canvas-aligned zone index raster (R channel)
* ``mapgen/config/real_world_equivalents.json`` - per-zone vanilla totals

Zone geometry: each closed region of the red outlines is one cell, mapped to a
zone by ``CELL_ZONE``; the Old World lump (cell 5) is split between Norsca,
Kislev, Empire, Bretonnia, Estalia, Tilea and the Border Princes by the nearest
land state of that realm. Colour -> zone is Chris's legend (``ZONES``); the mustard
north-east strip is folded into Cathay. Vanilla states take the colour that
covers most of their pixels on the r image (nearest colour for specks).

Run when sources, the legend or the drawn Old World change; never part of the
gate. ``--check`` re-derives and diffs the committed JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))

import measure_vanilla_arable as mva  # noqa: E402
from measure_vanilla_frame import VANILLA_ROOT  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
HIST = REPO / "sources" / "history"
OUT_JSON = REPO / "mapgen" / "config" / "real_world_equivalents.json"
OUT_PNG = REPO / "mapgen" / "config" / "real_world_zones.png"
STATE_DIR = REPO / "map_data" / "state_regions"
WORKSHEET = REPO / "mapgen" / "config" / "land_economics_worksheet.csv"

#: zone name -> (legend colour name, r-image RGB values folded into it)
ZONES: list[tuple[str, str, list[tuple[int, int, int]]]] = [
    ("naggaroth_chaos_wastes", "purple", [(126, 0, 126)]),
    ("ulthuan", "light blue", [(120, 190, 255)]),
    ("lustria", "green", [(30, 216, 54)]),
    ("far_south_spur", "steel blue", [(60, 120, 180)]),
    ("norsca", "brown", [(138, 61, 44)]),
    ("kislev", "cyan", [(125, 255, 255)]),
    ("empire", "red", [(255, 0, 0)]),
    ("bretonnia", "blue", [(0, 0, 255)]),
    ("estalia", "amber", [(252, 168, 0)]),
    ("tilea", "lime", [(125, 255, 0)]),
    ("border_princes", "orange", [(255, 125, 0)]),
    ("worlds_edge_ranges", "navy", [(0, 0, 126)]),
    ("badlands", "olive", [(125, 125, 0)]),
    ("dark_lands", "grey", [(143, 141, 122)]),
    ("northern_steppes", "tan", [(191, 156, 133)]),
    ("ogre_kingdoms", "violet", [(90, 60, 150)]),
    ("cathay", "yellow + mustard", [(255, 255, 0), (200, 200, 0)]),
    ("ind", "lilac", [(182, 142, 225)]),
    ("khuresh", "dark grey-green", [(74, 83, 68)]),
    ("nippon", "pink", [(255, 100, 255)]),
    ("araby", "sand", [(222, 184, 95)]),
    ("nehekhara", "dark brown", [(150, 90, 20)]),
    ("southlands", "dark green", [(0, 110, 60)]),
    ("kingdom_of_beasts", "magenta", [(200, 0, 120)]),
    ("sun_island_dragon_isles", "teal", [(0, 170, 170)]),
    ("lost_isles_of_elithis", "pale green", [(150, 220, 150)]),
    ("albion", "light pink", [(255, 180, 180)]),
    ("lumbria", "salmon", [(255, 150, 150)]),
]
ZONE_INDEX = {name: i for i, (name, _c, _v) in enumerate(ZONES, start=1)}
COLOUR_ZONE = {rgb: name for name, _c, vals in ZONES for rgb in vals}

#: red-outline cell number (``label_cells`` below, the f image's closed regions) -> zone
CELL_ZONE = {
    1: "naggaroth_chaos_wastes", 2: "naggaroth_chaos_wastes", 3: "northern_steppes",
    4: "northern_steppes", 6: "ogre_kingdoms", 7: "albion", 8: "worlds_edge_ranges",
    10: "dark_lands", 11: "ulthuan", 13: "cathay", 15: "nippon", 16: "badlands",
    17: "cathay", 18: "ind", 19: "sun_island_dragon_isles", 20: "araby", 21: "nehekhara",
    22: "sun_island_dragon_isles", 25: "kingdom_of_beasts", 26: "lustria", 27: "khuresh",
    28: "southlands", 29: "lumbria", 30: "southlands", 31: "lost_isles_of_elithis",
    32: "far_south_spur",
}
OLD_WORLD_CELL = 5
#: realm file stem -> zone inside the Old World lump
FILE_ZONE = {"00_norsca": "norsca", "01_kislev": "kislev", "02_empire": "empire",
             "03_brettonia": "bretonnia"}
#: Southern Realms split by the state's naming anchor x (Estalia | Tilea | Border Princes)
SOUTHERN_X = (3830, 4125)


def label_cells(f_rgb: np.ndarray) -> np.ndarray:
    red = (f_rgb[..., 0] > 180) & (f_rgb[..., 1] < 90) & (f_rgb[..., 2] < 90)
    red = ndi.binary_dilation(red, iterations=1)
    lab, _n = ndi.label(~red)
    # pixels on the lines (label 0) take the nearest cell
    idx = ndi.distance_transform_edt(lab == 0, return_distances=False, return_indices=True)
    return lab[tuple(idx)]


def mod_state_pixels() -> tuple[np.ndarray, dict[int, str], dict[int, float]]:
    """``(state index per pixel, file stem per state, anchor x per state)`` for the mod map."""
    import csv
    anchors = {r["state_key"]: int(r["anchor_x"])
               for r in csv.DictReader(open(WORKSHEET, encoding="utf-8-sig"))}
    keys: list[str] = []
    stems: dict[int, str] = {}
    axs: dict[int, float] = {}
    cols: list[int] = []
    idxs: list[int] = []
    for path in sorted(STATE_DIR.glob("[0-1]*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        for m in re.finditer(r"^(STATE_\w+)\s*=\s*\{(.*?)^\}", text, re.S | re.M):
            pm = re.search(r"provinces\s*=\s*\{([^}]*)\}", m.group(2))
            i = len(keys)
            keys.append(m.group(1))
            stems[i] = path.stem
            axs[i] = anchors.get(m.group(1), -1)
            for h in re.findall(r"x([0-9A-Fa-f]{6})", pm.group(1)):
                cols.append(int(h, 16))
                idxs.append(i)
    p = np.array(Image.open(REPO / "map_data" / "provinces.png").convert("RGB")).astype(np.int64)
    pk = (p[..., 0] << 16) | (p[..., 1] << 8) | p[..., 2]
    cols_a = np.array(cols)
    o = np.argsort(cols_a)
    cols_a = cols_a[o]
    idx_a = np.array(idxs)[o]
    pos = np.searchsorted(cols_a, pk).clip(0, len(cols_a) - 1)
    return np.where(cols_a[pos] == pk, idx_a[pos], -1), stems, axs


def build_zone_raster() -> np.ndarray:
    f = np.array(Image.open(HIST / "real-world-comparisons-f.png").convert("RGB")).astype(int)
    cells = label_cells(f)
    zone = np.zeros(cells.shape, dtype=np.uint8)
    for cell, name in CELL_ZONE.items():
        zone[cells == cell] = ZONE_INDEX[name]
    sidx, stems, axs = mod_state_pixels()
    # per-state zone for the Old World lump
    state_zone = np.zeros(max(stems) + 2, dtype=np.uint8)
    for i, stem in stems.items():
        if stem in FILE_ZONE:
            state_zone[i] = ZONE_INDEX[FILE_ZONE[stem]]
        elif stem == "05_southern_realms":
            x = axs[i]
            z = "estalia" if x < SOUTHERN_X[0] else ("tilea" if x < SOUTHERN_X[1] else "border_princes")
            state_zone[i] = ZONE_INDEX[z]
    seed_zone = np.where(sidx >= 0, state_zone[sidx.clip(0)], 0).astype(np.uint8)
    seed_zone[(sidx < 0) | (cells != OLD_WORLD_CELL)] = 0
    nearest = ndi.distance_transform_edt(seed_zone == 0, return_distances=False, return_indices=True)
    filled = seed_zone[tuple(nearest)]
    lump = cells == OLD_WORLD_CELL
    zone[lump] = filled[lump]
    return zone


# --- vanilla side -----------------------------------------------------------

def _block_ints(block: str, name: str) -> dict[str, int]:
    m = re.search(r"\b" + name + r"\s*=\s*\{([^}]*)\}", block)
    return {k: int(v) for k, v in re.findall(r"(\w+)\s*=\s*(\d+)", m.group(1))} if m else {}


def parse_vanilla_extras(path: Path) -> dict[str, dict]:
    text = re.sub(r"#.*", "", path.read_text(encoding="utf-8-sig", errors="replace"))
    out = {}
    heads = list(re.finditer(r"^(STATE_\w+)\s*=\s*\{", text, re.M))
    for i, m in enumerate(heads):
        block = text[m.start(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        ar = re.search(r"arable_resources\s*=\s*\{([^}]*)\}", block)
        res = []
        for rm in re.finditer(r"\bresource\s*=\s*\{([^}]*)\}", block):
            body = rm.group(1)
            t = re.search(r'type\s*=\s*"?(\w+)"?', body)
            d = re.search(r'depleted_type\s*=\s*"?(\w+)"?', body)
            di = re.search(r"\bdiscovered_amount\s*=\s*(\d+)", body)
            un = re.search(r"undiscovered_amount\s*=\s*(\d+)", body)
            if t:
                res.append((t.group(1), d.group(1) if d else "", int(di.group(1)) if di else 0,
                            int(un.group(1)) if un else 0))
        out[m.group(1)] = {
            "arable_resources": tuple(re.findall(r'"?(building_\w+)"?', ar.group(1))) if ar else (),
            "capped": _block_ints(block, "capped_resources"),
            "resources": res,
        }
    return out


def vanilla_state_colours(states: list[dict], game: Path) -> dict[str, tuple[int, int, int] | None]:
    # r is vanilla's frame at 1.0225x, offset (-82.5, -12.75) px (fitted 2026-10-12, IoU 0.63)
    a, b, c, d = 1.0225, -82.5, 1.0225, -12.75
    p = np.array(Image.open(game / "map_data" / "provinces.png").convert("RGB")).astype(np.int64)
    pk = (p[..., 0] << 16) | (p[..., 1] << 8) | p[..., 2]
    cols, idx = [], []
    for i, s in enumerate(states):
        for col in s["colours"]:
            cols.append(col)
            idx.append(i)
    cols_a = np.array(cols)
    o = np.argsort(cols_a)
    cols_a = cols_a[o]
    idx_a = np.array(idx)[o]
    pos = np.searchsorted(cols_a, pk).clip(0, len(cols_a) - 1)
    sidx = np.where(cols_a[pos] == pk, idx_a[pos], -1)
    r = np.array(Image.open(HIST / "real-world-comparisons-r.png").convert("RGB")).astype(int)
    H, W = r.shape[:2]
    ry, rx = np.mgrid[0:H, 0:W]
    vx = (((rx - b) / a) * (8192 / W)).round().astype(int).clip(0, 8191)
    vy = (((ry - d) / c) * (3616 / H)).round().astype(int).clip(0, 3615)
    st = sidx[vy, vx]
    border = (r.sum(-1) < 60) | (r >= 250).all(-1)
    tally: list[Counter] = [Counter() for _ in states]
    ys, xs = np.nonzero(~border & (st >= 0))
    for y, x in zip(ys, xs):
        tally[st[y, x]][(int(r[y, x, 0]), int(r[y, x, 1]), int(r[y, x, 2]))] += 1
    # fallback: nearest coloured pixel to the state's pixel centroid
    paint = ~border
    near = ndi.distance_transform_edt(~paint, return_distances=False, return_indices=True)
    out: dict[str, tuple[int, int, int] | None] = {}
    for i, s in enumerate(states):
        if tally[i]:
            out[s["key"]] = tally[i].most_common(1)[0][0]
            continue
        m = np.nonzero(sidx == i)
        if not len(m[0]):
            out[s["key"]] = None
            continue
        y = int(c * (m[0].mean() / (3616 / H)) + d)
        x = int(a * (m[1].mean() / (8192 / W)) + b)
        y, x = int(np.clip(y, 0, H - 1)), int(np.clip(x, 0, W - 1))
        yy, xx = near[0][y, x], near[1][y, x]
        out[s["key"]] = (int(r[yy, xx, 0]), int(r[yy, xx, 1]), int(r[yy, xx, 2]))
    return out


def build_totals(game: Path) -> dict:
    states = mva.load_vanilla(game)
    extras: dict[str, dict] = {}
    for path in sorted((game / "map_data" / "state_regions").glob("[0-9][0-9]_*.txt")):
        extras.update(parse_vanilla_extras(path))
    colour_of = vanilla_state_colours(states, game)
    per_zone: dict[str, list[dict]] = defaultdict(list)
    dropped = Counter()
    for s in states:
        col = colour_of[s["key"]]
        zone = COLOUR_ZONE.get(col) if col else None
        if zone is None:
            dropped[str(col)] += 1
            continue
        per_zone[zone].append(s)
    zones = []
    for name, legend, _vals in ZONES:
        group = per_zone.get(name, [])
        sub = Counter()
        arset = Counter()
        capped: Counter = Counter()
        res: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
        for s in group:
            ex = extras[s["key"]]
            if s["subsistence"] != "building_subsistence_fishing_village":
                sub[s["subsistence"]] += s["arable"]
            arset[ex["arable_resources"]] += s["arable"]
            for k, v in ex["capped"].items():
                capped[k] += v
            for t, dep, di, un in ex["resources"]:
                res[(t, dep)][0] += di
                res[(t, dep)][1] += un
        zones.append({
            "name": name, "legend_colour": legend,
            "vanilla_states": len(group),
            "arable": sum(s["arable"] for s in group),
            "subsistence": (sub.most_common(1)[0][0] if sub else "building_subsistence_farm"),
            "arable_resources": list(arset.most_common(1)[0][0]) if arset
            else ["building_wheat_farm", "building_livestock_ranch"],
            "capped": dict(sorted(capped.items())),
            "resources": [{"type": t, "depleted_type": dep, "discovered": di, "undiscovered": un}
                          for (t, dep), (di, un) in sorted(res.items())],
        })
    return {"note": "generated by mapgen/build_real_world_equivalents.py; do not hand-edit",
            "vanilla_states": len(states), "unassigned_vanilla_states": dict(dropped), "zones": zones}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", type=Path, default=Path(VANILLA_ROOT))
    ap.add_argument("--check", action="store_true", help="re-derive and diff the committed files")
    args = ap.parse_args(argv)
    totals = build_totals(args.game)
    text = json.dumps(totals, indent=1, sort_keys=False) + "\n"
    zone = build_zone_raster()
    rgb = np.zeros(zone.shape + (3,), dtype=np.uint8)
    rgb[..., 0] = zone
    if args.check:
        ok = OUT_JSON.read_text(encoding="utf-8") == text
        print("real_world_equivalents.json:", "current" if ok else "STALE")
        return 0 if ok else 1
    OUT_JSON.write_text(text, encoding="utf-8")
    Image.fromarray(rgb).save(OUT_PNG, optimize=True)
    for z in totals["zones"]:
        px = int((zone == ZONE_INDEX[z["name"]]).sum())
        print(f"{z['name']:26s} vanilla_states={z['vanilla_states']:3d} arable={z['arable']:5d} zone_px={px:9d}")
    print("unassigned vanilla states:", totals["unassigned_vanilla_states"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
