#!/usr/bin/env python3
"""Per-state physical prior and agro-climate class tabulator (board #3677; shared with #3687).

Dev-only and read-only: reads committed inputs (the emitted ``map_data/state_regions``, the
province bitmap and index, the heightmap, the traced rivers bitmap, the arable heatmap, the
naming worksheet, the strategic regions) and writes only gitignored ``scratchpad/`` output.
Outside the offline gate; no ``sources/`` pixels are read or drawn.

It computes, once and identically for every drawn state, the numbers all of #3675's content
children and #3687 read: the 16 core columns (#3687's shared contract, verbatim and first),
then this item's descriptors (latitude band, elevation, canon rivers, heatmap within-realm
rank ``heat_realm_pct``, ...). With ``--classes`` it joins the hand-authored
``mapgen/config/state_climate_classes.csv`` (lore assigns the class) and runs the physical
expectation table: a state whose assigned class is not physically expected is
``phys_disagree`` and MUST carry an ``override_ref`` (hard error otherwise), so the lore
override list is exactly the lore-vs-physics disagreement list. ``heat_disagree`` is a
non-blocking note: #4921's lore zones are a first draft and the raster never vetoes lore.

Usage::

    python mapgen/tabulate_state_prior.py                      # physical columns only
    python mapgen/tabulate_state_prior.py --classes mapgen/config/state_climate_classes.csv \\
        --rivers mapgen/config/canon_rivers.csv --markdown --render

Outputs: ``scratchpad/state_physical_prior.csv`` (always), ``state_prior_generated.md``
(``--markdown``; also printed), ``state_prior_class_review.png`` (``--render``; needs
``--classes``). Deterministic: no clocks, no randomness, fixed number formatting.

Importable: ``tabulate(mod_root, classes=None, rivers=None) -> list[dict]``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_map  # noqa: E402
from config import canvas_frame, map_config  # noqa: E402
from worldgen import land_economics, land_naming, raster  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent

# --------------------------------------------------------------------------- constants
#: The eleven climate classes, in #3676's order (string-checked against its landed note).
CLASS_IDS = (
    "arctic_boreal_coast", "boreal_forest", "temperate_river_plain", "temperate_forest_hill",
    "mediterranean", "steppe", "desert_river", "open_desert", "highland_alpine",
    "tropical_savanna", "tropical_forest",
)
RESEARCH_NOTE = Path("planning/economics/arable_land_engine_research.md")

#: Latitude bands: (name, lower bound in degrees, inclusive), north to south.
LAT_BANDS = (
    ("polar", 66.0), ("boreal", 58.0), ("cool_temperate", 50.0), ("temperate", 42.0),
    ("warm_temperate", 34.0), ("subtropical", 24.0), ("tropical", -999.0),
)
HIGHLAND_SHARE = 0.5      # phys_highland = share of pixels >= HIGHLAND_M at or above this
HIGHLAND_M = 1000.0
TALL_SPAN_DEG = 4.0
TINY_PX = 1000

#: Expectation table (note §3.2). band -> {class: condition}; condition is "any", "coastal" or
#: "canon_river". A highland-flagged state expects only ``highland_alpine`` and an unflagged
#: state never expects it (elevation raises the flag, the lore assignment must answer it).
EXPECT = {
    "polar": {"arctic_boreal_coast": "any", "boreal_forest": "any"},
    "boreal": {"boreal_forest": "any", "arctic_boreal_coast": "coastal"},
    "cool_temperate": {"boreal_forest": "any", "temperate_forest_hill": "any", "steppe": "any",
                       "temperate_river_plain": "canon_river"},
    "temperate": {"temperate_forest_hill": "any", "steppe": "any", "mediterranean": "coastal",
                  "temperate_river_plain": "canon_river"},
    "warm_temperate": {"mediterranean": "any", "steppe": "any", "temperate_forest_hill": "any",
                       "temperate_river_plain": "canon_river", "desert_river": "canon_river",
                       "open_desert": "any"},
    "subtropical": {"steppe": "any", "open_desert": "any", "tropical_savanna": "any",
                    "mediterranean": "coastal", "desert_river": "canon_river"},
    "tropical": {"open_desert": "any", "tropical_savanna": "any", "tropical_forest": "any",
                 "desert_river": "canon_river"},
}

#: Class -> band rank for ``heat_disagree`` (0 low, 1 mid, 2 high), from the vanilla
#: comparable-geography class medians in the #3676 note (table 4.3).
CLASS_BAND_RANK = {
    "arctic_boreal_coast": 0, "open_desert": 0, "highland_alpine": 0, "mediterranean": 0,
    "boreal_forest": 1, "steppe": 1, "desert_river": 1, "tropical_savanna": 1,
    "temperate_forest_hill": 2, "temperate_river_plain": 2, "tropical_forest": 2,
}

#: Strategic region -> realm group (roster order is GROUP_ORDER).
GROUP_ORDER = ("norsca_kislev", "empire", "brettonia", "karaz_ankor", "southern_realms_badlands",
               "nehekhara", "dark_lands")
REGION_TO_GROUP = {
    "region_norsca": "norsca_kislev", "region_kislev": "norsca_kislev",
    "region_the_empire": "empire", "region_brettonia": "brettonia",
    "region_central_worlds_edge_mountains": "karaz_ankor",
    "region_northern_worlds_edge_mountains": "karaz_ankor",
    "region_southern_worlds_edge_mountains": "karaz_ankor", "region_western_ranges": "karaz_ankor",
    "region_southern_realms": "southern_realms_badlands", "region_badlands": "southern_realms_badlands",
    "region_land_of_the_dead": "nehekhara",
    "region_northern_dark_lands": "dark_lands", "region_southern_dark_lands": "dark_lands",
}
GROUP_TITLES = {
    "norsca_kislev": "Norsca and Kislev", "empire": "The Empire", "brettonia": "Bretonnia",
    "karaz_ankor": "Karaz Ankor", "southern_realms_badlands": "Southern Realms and Badlands",
    "nehekhara": "Nehekhara", "dark_lands": "The Dark Lands",
}
STRATEGIC_FILES = ("old_world_strategic_regions.txt", "southlands_strategic_regions.txt")

#: Rivers bitmap: indices <= RIVER_MAX_INDEX are river pixels; 3.. is the width ramp; 8 = trunk.
RIVER_MAX_INDEX = 11
TRUNK_INDEX = 8

CORE_COLUMNS = ("state_key", "file", "state_id", "region_id", "worksheet_name", "provinces",
                "area_px", "coastal_provinces", "port", "naval_exit", "lat", "lon",
                "elev_mean_m", "elev_max_m", "river_px", "river_share")
DESCRIPTOR_COLUMNS = (
    "area_km2", "name", "realm", "realm_group", "n_provinces", "coastal", "coastal_share",
    "lon_anchor", "lat_anchor", "lat_north", "lat_south", "lat_band", "elev_p90_m",
    "share_ge_1000m", "phys_highland", "river_per_1000px", "river_max_width", "trunk_px",
    "canon_river", "heat_mean", "heat_p90", "heat_nonzero_share", "heat_realm_pct",
    "heat_realm_rel", "heat_disagree", "lore_zone", "climate_class", "override_ref",
    "phys_disagree", "flags",
)
COLUMNS = CORE_COLUMNS + DESCRIPTOR_COLUMNS

CLASS_TINTS = {
    "arctic_boreal_coast": (150, 205, 235), "boreal_forest": (40, 110, 80),
    "temperate_river_plain": (150, 215, 90), "temperate_forest_hill": (80, 160, 70),
    "mediterranean": (235, 175, 70), "steppe": (215, 200, 110), "desert_river": (60, 150, 160),
    "open_desert": (235, 215, 160), "highland_alpine": (150, 130, 160),
    "tropical_savanna": (225, 130, 60), "tropical_forest": (30, 130, 60),
}


# --------------------------------------------------------------------------- small helpers
def _f(v: float, nd: int) -> str:
    return f"{float(v):.{nd}f}"


def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    """Rows of a hand-authored CSV: ``#`` comment lines and blank lines skipped."""
    lines = [ln for ln in path.read_text(encoding="utf-8-sig").splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise SystemExit(f"{path}: no header row")
    rdr = csv.DictReader(lines)
    rows = [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in rdr]
    return [h.strip() for h in (rdr.fieldnames or [])], rows


def lat_band(lat: float) -> str:
    for name, lo in LAT_BANDS:
        if lat >= lo:
            return name
    return LAT_BANDS[-1][0]


def expected_classes(band: str, coastal: bool, highland: bool, canon_river: bool) -> set[str]:
    """The classes physically expected for a descriptor combination (note §3.2)."""
    if highland:
        return {"highland_alpine"}
    out = set()
    for cls, cond in EXPECT[band].items():
        if cond == "any" or (cond == "coastal" and coastal) or (cond == "canon_river" and canon_river):
            out.add(cls)
    return out


def disagree_reasons(cls: str, band: str, coastal: bool, highland: bool, canon_river: bool) -> list[str]:
    if cls in expected_classes(band, coastal, highland, canon_river):
        return []
    if highland:
        return ["highland"]
    if cls == "highland_alpine":
        return ["not_highland"]
    cond = EXPECT[band].get(cls)
    if cond is None:
        return ["band"]
    if cond == "coastal":
        return ["not_coastal"]
    return ["no_canon_river"]


def check_class_ids_against_note(mod_root: Path) -> None:
    note = mod_root / RESEARCH_NOTE
    if not note.is_file():
        return
    for line in note.read_text(encoding="utf-8").splitlines():
        if "The eleven ids, verbatim" in line:
            ids = tuple(re.findall(r"`([a-z_]+)`", line.split("verbatim", 1)[1].split("(", 1)[0]))
            if ids != CLASS_IDS:
                raise SystemExit(f"CLASS_IDS differ from {RESEARCH_NOTE}: {ids} vs {CLASS_IDS}")
            return


# --------------------------------------------------------------------------- loading
def _load_states(mod_root: Path, drawn_ids: set[int]) -> tuple[list, dict[str, str]]:
    states, stem_of = [], {}
    for path in sorted((mod_root / "map_data" / "state_regions").glob("*.txt")):
        if path.name.startswith("99_"):
            continue
        for st in validate_map.parse_state_file(path):
            if st.id in drawn_ids:
                states.append(st)
                stem_of[st.key] = path.stem
    return states, stem_of


def _realms(mod_root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for fn in STRATEGIC_FILES:
        p = mod_root / "common" / "strategic_regions" / fn
        for region, members in validate_map._parse_strategic_region_states(p).items():
            for k in members:
                out[k] = region
    return out


def _state_raster(rgb: np.ndarray, states: list, passable_only: bool, impass_of: dict[str, set]) -> np.ndarray:
    code = ((rgb[..., 0].astype(np.int64) << 16) | (rgb[..., 1].astype(np.int64) << 8)
            | rgb[..., 2].astype(np.int64))
    pairs = []
    for i, st in enumerate(states, start=1):
        for c in st.provinces:
            if passable_only and c in impass_of[st.key]:
                continue
            pairs.append(((c[0] << 16) | (c[1] << 8) | c[2], i))
    pairs.sort()
    keys = np.array([p[0] for p in pairs], dtype=np.int64)
    vals = np.array([p[1] for p in pairs], dtype=np.int32)
    pos = np.searchsorted(keys, code)
    pos[pos >= len(keys)] = 0
    return np.where(keys[pos] == code, vals[pos], 0).astype(np.int32)


def _group_slices(lab_flat: np.ndarray, n: int):
    order = np.argsort(lab_flat, kind="stable")
    sorted_lab = lab_flat[order]
    bounds = np.searchsorted(sorted_lab, np.arange(1, n + 2))
    return order, bounds


def tabulate(mod_root, classes=None, rivers=None, _extras: dict | None = None) -> list[dict]:
    """One row per drawn state (sorted by ``state_key``); see the module docstring.

    ``classes`` / ``rivers`` are paths to the two hand-authored CSVs (or None). ``_extras``, when
    given, receives the label raster and states for the renderer."""
    mod_root = Path(mod_root)
    cfg = mod_root / "mapgen" / "config"
    derived = mod_root / "mapgen" / "derived"
    check_class_ids_against_note(mod_root)

    # --- roster: worksheet drawn rows, the economics worksheet's keys, the emitted states
    ws_path = cfg / "land_regions_worksheet.csv"
    with open(ws_path, newline="", encoding="utf-8") as fh:
        ws_rows = {int(r["region_id"]): r for r in csv.DictReader(fh)}
    drawn_ids = {i for i, r in ws_rows.items() if r["kind"] == "drawn"}
    states, stem_of = _load_states(mod_root, drawn_ids)
    by_id = {st.id: st for st in states}
    missing = sorted(drawn_ids - set(by_id))
    if missing:
        raise SystemExit(f"drawn worksheet rows with no emitted state (region_id): {missing}")
    econ = land_economics.load_economics_worksheet(cfg / "land_economics_worksheet.csv")
    if set(econ.rows) != {st.key for st in states}:
        a = sorted(set(econ.rows) - {st.key for st in states})
        b = sorted({st.key for st in states} - set(econ.rows))
        raise SystemExit(f"land_economics_worksheet roster differs from the emitted drawn states: "
                         f"only in worksheet {a[:5]}, only emitted {b[:5]}")
    names = land_naming.load_worksheet_names(ws_path)
    weak = set(names.weak)
    realm_of = _realms(mod_root)

    # --- optional lore inputs
    class_rows: dict[str, dict] | None = None
    if classes is not None:
        _, rows = _read_csv(Path(classes))
        class_rows = {}
        for r in rows:
            k = r["state_key"]
            if k in class_rows:
                raise SystemExit(f"{classes}: duplicate state_key {k}")
            class_rows[k] = r
    canon_rows: dict[str, set[str]] = {}
    keyset = {st.key for st in states}
    if rivers is not None:
        _, rows = _read_csv(Path(rivers))
        for r in rows:
            if r["state_key"] not in keyset:
                raise SystemExit(f"{rivers}: state_key {r['state_key']!r} is not an emitted drawn state "
                                 f"(a renamed state is re-keyed by hand; see mapgen/config/land_regions_worksheet.csv)")
            canon_rows.setdefault(r["state_key"], set()).add(r["river"])

    # --- index + pixel inputs
    prov = json.loads((derived / "provinces_index.json").read_text(encoding="utf-8"))
    cell_of = {tuple(int(v) for v in c["color"]): c for c in prov["cells"]}
    impass_of = {st.key: set(st.impassable) for st in states}
    for st in states:
        for c in st.provinces:
            if c not in cell_of:
                raise SystemExit(f"{st.key}: province colour {c} is absent from provinces_index.json")
    W, H = map_config.PROVINCES_SIZE
    rgb = raster.read_rgb_png(mod_root / "map_data" / "provinces.png")
    if rgb.shape[:2] != (H, W):
        raise SystemExit(f"provinces.png is {rgb.shape[1]}x{rgb.shape[0]}, expected {W}x{H}")
    lab_all = _state_raster(rgb, states, False, impass_of)
    lab_pass = _state_raster(rgb, states, True, impass_of)
    del rgb
    n = len(states)

    hm = raster.read_gray16_png(mod_root / "map_data" / "heightmap.png")
    if hm.shape != (2 * H, 2 * W):
        raise SystemExit(f"heightmap.png is {hm.shape[1]}x{hm.shape[0]}, not exactly 2x the {W}x{H} canvas")
    elev = (hm[::2, ::2].astype(np.float64) - map_config.HEIGHT_SEA_LEVEL) / map_config.HEIGHT_UNITS_PER_METRE
    del hm
    riv, _pal = raster.read_indexed_png(mod_root / "map_data" / "rivers.png")
    if riv.shape != (H, W):
        raise SystemExit(f"rivers.png is {riv.shape[1]}x{riv.shape[0]}, expected {W}x{H}")
    heat_path = derived / "arable_heatmap.png"
    with Image.open(heat_path) as im:
        if im.mode != "I;16" or im.size != (W, H):
            raise SystemExit(f"arable_heatmap.png must be {W}x{H} mode I;16, got {im.size} {im.mode}")
    heat = raster.read_gray16_png(heat_path).astype(np.float64) / 65535.0

    # --- per-state pixel statistics
    flat_all = lab_all.ravel()
    sel_all = np.nonzero(flat_all)[0]
    order_a, bounds_a = _group_slices(flat_all[sel_all], n)
    pix_a = sel_all[order_a]
    elev_flat = elev.ravel()
    riv_flat = riv.ravel()
    flat_pass = lab_pass.ravel()
    sel_p = np.nonzero(flat_pass)[0]
    order_p, bounds_p = _group_slices(flat_pass[sel_p], n)
    pix_p = sel_p[order_p]
    heat_flat = heat.ravel()

    row_lat = canvas_frame.canvas_to_lonlat(np.zeros(H), np.arange(H) + 0.5)[1]
    row_km2 = canvas_frame.km2_per_px(row_lat)
    rows: list[dict] = []
    for i, st in enumerate(states):
        pa = pix_a[bounds_a[i]:bounds_a[i + 1]]
        pp = pix_p[bounds_p[i]:bounds_p[i + 1]]
        if pa.size == 0:
            raise SystemExit(f"{st.key}: no pixels in provinces.png")
        ys, xs = pa // W, pa % W
        ws = ws_rows[st.id]
        ax, ay = float(ws["anchor_x"]), float(ws["anchor_y"])
        lon_a, lat_a = canvas_frame.canvas_to_lonlat(ax, ay)
        lat_n = float(canvas_frame.canvas_to_lonlat(float(xs.mean()), float(ys.min()))[1])
        lat_s = float(canvas_frame.canvas_to_lonlat(float(xs.mean()), float(ys.max()) + 1.0)[1])
        lat_a = float(lat_a)
        e = elev_flat[pa]
        rv = riv_flat[pa]
        isr = rv <= RIVER_MAX_INDEX
        river_px = int(isr.sum())
        ramp = rv[(rv >= 3) & isr]
        h = heat_flat[pp] if pp.size else np.zeros(1)
        area_px = int(pa.size)
        n_coast = sum(1 for c in st.provinces if cell_of[c].get("coastal"))
        # area_km2: sum of per-row true areas, so a tall state is not priced at one latitude.
        area_km2 = float(row_km2[ys].sum())
        cr = canon_rows.get(st.key, set())
        coastal = n_coast > 0
        band = lat_band(lat_a)
        sh1000 = float((e >= HIGHLAND_M).mean())
        phys_hl = sh1000 >= HIGHLAND_SHARE
        flags = []
        if abs(lat_n - lat_s) > TALL_SPAN_DEG:
            flags.append("tall")
        if area_px < TINY_PX:
            flags.append("tiny")
        if len(st.provinces) == 1:
            flags.append("one_province")
        if st.id in weak:
            flags.append("weak_name")
        if not ws["name"].strip():
            flags.append("naming_gap")
        group = REGION_TO_GROUP.get(realm_of.get(st.key, ""), "")
        if not group:
            raise SystemExit(f"{st.key}: not in any in-scope strategic region ({realm_of.get(st.key)!r})")
        rows.append({
            "state_key": st.key, "file": stem_of[st.key], "state_id": st.id, "region_id": st.id,
            "worksheet_name": ws["name"], "provinces": len(st.provinces), "area_px": area_px,
            "coastal_provinces": n_coast, "port": int(st.port_declared),
            "naval_exit": st.naval_exit_id if st.naval_exit_id is not None else "",
            "lat": _f(lat_a, 3), "lon": _f(lon_a, 3), "elev_mean_m": _f(e.mean(), 1),
            "elev_max_m": _f(e.max(), 1), "river_px": river_px,
            "river_share": _f(river_px / area_px, 5),
            "area_km2": _f(area_km2, 0), "name": names.names.get(st.id, ""),
            "realm": realm_of[st.key].removeprefix("region_"), "realm_group": group,
            "n_provinces": len(st.provinces), "coastal": int(coastal),
            "coastal_share": _f(n_coast / len(st.provinces), 3),
            "lon_anchor": _f(lon_a, 3), "lat_anchor": _f(lat_a, 3),
            "lat_north": _f(lat_n, 3), "lat_south": _f(lat_s, 3), "lat_band": band,
            "elev_p90_m": _f(np.percentile(e, 90), 1), "share_ge_1000m": _f(sh1000, 4),
            "phys_highland": int(phys_hl),
            "river_per_1000px": _f(1000.0 * river_px / area_px, 3),
            "river_max_width": int(ramp.max()) if ramp.size else 0,
            "trunk_px": int((rv == TRUNK_INDEX).sum()),
            "canon_river": int(bool(cr)),
            "heat_mean": _f(h.mean(), 5), "heat_p90": _f(np.percentile(h, 90), 5),
            "heat_nonzero_share": _f(float((h > 0).mean()), 4),
            "heat_realm_pct": "", "heat_realm_rel": "", "heat_disagree": "",
            "lore_zone": "", "climate_class": "", "override_ref": "", "phys_disagree": "",
            "flags": "|".join(flags),
        })
    rows.sort(key=lambda r: r["state_key"])

    # --- within-realm heat rank (equal weight per state)
    for g in GROUP_ORDER:
        grp = [r for r in rows if r["realm_group"] == g]
        if not grp:
            continue
        means = [float(r["heat_mean"]) for r in grp]
        med = float(np.median(means))
        for r in grp:
            m = float(r["heat_mean"])
            less = sum(1 for x in means if x < m)
            eq = sum(1 for x in means if x == m)
            pct = 0.5 if len(means) == 1 else (less + (eq - 1) / 2.0) / (len(means) - 1)
            r["heat_realm_pct"] = _f(pct, 4)
            r["heat_realm_rel"] = _f(m / med, 3) if med > 0 else ""

    # --- lore join + checks
    if class_rows is not None:
        id_of = {r["state_key"]: r["state_id"] for r in rows}
        for k in class_rows:
            if k not in id_of:
                raise SystemExit(f"{classes}: state_key {k!r} matches no emitted drawn state "
                                 f"(re-key by hand; see mapgen/config/land_regions_worksheet.csv)")
        errors = []
        for r in rows:
            k = r["state_key"]
            c = class_rows.get(k)
            if c is None:
                errors.append(f"{k}: no row in {classes}")
                continue
            slug = c.get("climate_class", "")
            if slug not in CLASS_IDS:
                errors.append(f"{k}: climate_class {slug!r} is not one of the eleven class ids")
                continue
            if c.get("state_id") and int(c["state_id"]) != r["state_id"]:
                errors.append(f"{k}: state_id {c['state_id']} in the class CSV, {r['state_id']} emitted (stale copy)")
            if c.get("realm_group") and c["realm_group"] != r["realm_group"]:
                errors.append(f"{k}: realm_group {c['realm_group']!r} in the class CSV, {r['realm_group']!r} from the strategic regions")
            r["lore_zone"] = c.get("lore_zone", "")
            r["climate_class"] = slug
            r["tier"] = c.get("tier", "")
            r["override_ref"] = c.get("override_ref", "")
            reasons = disagree_reasons(slug, r["lat_band"], bool(r["coastal"]),
                                       bool(r["phys_highland"]), bool(r["canon_river"]))
            r["phys_disagree"] = "|".join(reasons)
            if reasons and not r["override_ref"]:
                errors.append(f"{k}: phys_disagree ({'|'.join(reasons)}; class {slug}, band {r['lat_band']}, "
                              f"coastal {r['coastal']}, highland {r['phys_highland']}, canon_river {r['canon_river']}) "
                              f"has no override_ref")
            pct = float(r["heat_realm_pct"])
            tercile = 0 if pct < 1 / 3 else (2 if pct >= 2 / 3 else 1)
            r["heat_disagree"] = int(abs(CLASS_BAND_RANK[slug] - tercile) >= 2)
        if errors:
            raise SystemExit("hard errors:\n  " + "\n  ".join(errors))
    if _extras is not None:
        _extras.update({"lab_all": lab_all, "states": states})
    return rows


# --------------------------------------------------------------------------- outputs
def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([r[c] for c in COLUMNS])


def _heat_stamp(mod_root: Path) -> str:
    h = hashlib.sha256((mod_root / "mapgen" / "derived" / "arable_heatmap.png").read_bytes()).hexdigest()
    idx = json.loads((mod_root / "mapgen" / "derived" / "arable_heatmap_index.json").read_text(encoding="utf-8"))
    return f"heatmap sha256 {h[:12]}, norm_value {idx['norm_value']:.4f}"


def markdown(rows: list[dict], mod_root: Path, has_classes: bool) -> str:
    stamp = _heat_stamp(mod_root)
    out: list[str] = []
    for g in GROUP_ORDER:
        grp = sorted((r for r in rows if r["realm_group"] == g), key=lambda r: int(r["state_id"]))
        out.append(f"<!-- BEGIN GENERATED: s4 {g} ({stamp}) -->")
        out.append(f"#### {GROUP_TITLES[g]} ({len(grp)} states)")
        out.append("")
        out.append("| id | key | zone | class | override | tier |")
        out.append("|---|---|---|---|---|---|")
        for r in grp:
            out.append(f"| {r['state_id']} | {r['state_key']} | {r['lore_zone']} | {r['climate_class']} "
                       f"| {r['override_ref'] or '-'} | {r.get('tier', '')} |")
        out.append("<!-- END GENERATED -->")
        out.append("")
    out.append(f"<!-- BEGIN GENERATED: appendix-a ({stamp}) -->")
    out.append("| id | key | group | lat | band | elev | highland | coast | canon river | trunk | heat pct | class | disagree |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: int(r["state_id"])):
        dis = r["phys_disagree"] or ""
        if r["heat_disagree"] == 1:
            dis = (dis + "|heat") if dis else "heat"
        out.append(f"| {r['state_id']} | {r['state_key']} | {r['realm_group']} | {r['lat']} | {r['lat_band']} "
                   f"| {r['elev_mean_m']} | {r['phys_highland']} | {r['coastal']} | {r['canon_river']} "
                   f"| {r['trunk_px']} | {r['heat_realm_pct']} | {r['climate_class'] or '-'} | {dis or '-'} |")
    out.append("<!-- END GENERATED -->")
    return "\n".join(out) + "\n"


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def render(rows: list[dict], extras: dict, out_path: Path) -> None:
    """Flat per-class tints on a neutral ground, black state edges, phys_disagree outlined red."""
    lab = extras["lab_all"]
    states = extras["states"]
    n = len(states)
    row_of = {r["state_key"]: r for r in rows}
    tint = np.zeros((n + 1, 3), dtype=np.uint8)
    red = np.zeros(n + 1, dtype=bool)
    for i, st in enumerate(states, start=1):
        r = row_of[st.key]
        tint[i] = CLASS_TINTS.get(r["climate_class"], (200, 200, 200))
        red[i] = bool(r["phys_disagree"])
    ys, xs = np.nonzero(lab)
    x0, x1 = max(0, xs.min() - 40), min(lab.shape[1], xs.max() + 41)
    y0, y1 = max(0, ys.min() - 40), min(lab.shape[0], ys.max() + 41)
    lab = lab[y0:y1, x0:x1]
    img = np.empty(lab.shape + (3,), dtype=np.uint8)
    img[:] = (58, 62, 70)
    land = lab > 0
    img[land] = tint[lab[land]]
    edge = np.zeros(lab.shape, dtype=bool)
    d = lab[:, 1:] != lab[:, :-1]
    edge[:, 1:] |= d
    edge[:, :-1] |= d
    d = lab[1:, :] != lab[:-1, :]
    edge[1:, :] |= d
    edge[:-1, :] |= d
    edge &= land
    scale = 2
    big = np.repeat(np.repeat(img, scale, axis=0), scale, axis=1)
    lab_b = np.repeat(np.repeat(lab, scale, axis=0), scale, axis=1)
    edge_b = np.repeat(np.repeat(edge, scale, axis=0), scale, axis=1)
    big[edge_b] = (0, 0, 0)
    rededge = edge_b & red[lab_b]
    # thicken red outlines by 2 px via shifts
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1)):
        shifted = np.roll(np.roll(rededge, dy, axis=0), dx, axis=1) & (lab_b > 0) & red[lab_b]
        big[shifted] = (230, 20, 20)
    big[rededge] = (230, 20, 20)
    im = Image.fromarray(big)
    dr = ImageDraw.Draw(im)
    font = _font(15)
    for i, st in enumerate(states, start=1):
        m = lab == i
        if m.sum() < 700:
            continue
        yy, xx = np.nonzero(m)
        cx, cy = int(np.median(xx)), int(np.median(yy))
        # snap to a state pixel
        k = int(np.argmin((xx - cx) ** 2 + (yy - cy) ** 2))
        cx, cy = int(xx[k]), int(yy[k])
        dr.text((cx * scale, cy * scale), str(st.id), fill=(0, 0, 0), font=font, anchor="mm",
                stroke_width=1, stroke_fill=(255, 255, 255))
    # legend
    lf = _font(22)
    present = [c for c in CLASS_IDS if any(r["climate_class"] == c for r in rows)]
    lx, ly = 30, 30
    dr.rectangle((lx - 10, ly - 10, lx + 400, ly + 34 * (len(present) + 2) + 6), fill=(20, 22, 26), outline=(220, 220, 220))
    for j, c in enumerate(present):
        n_c = sum(1 for r in rows if r["climate_class"] == c)
        dr.rectangle((lx, ly + 34 * j, lx + 26, ly + 34 * j + 26), fill=CLASS_TINTS[c])
        dr.text((lx + 38, ly + 34 * j + 13), f"{c} ({n_c})", fill=(255, 255, 255), font=lf, anchor="lm")
    j = len(present)
    dr.rectangle((lx, ly + 34 * j, lx + 26, ly + 34 * j + 26), outline=(230, 20, 20), width=4)
    dr.text((lx + 38, ly + 34 * j + 13), f"red outline = phys_disagree ({sum(1 for r in rows if r['phys_disagree'])})",
            fill=(255, 255, 255), font=lf, anchor="lm")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(str(out_path), format="PNG", optimize=False, compress_level=6)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--classes", metavar="CSV", help="mapgen/config/state_climate_classes.csv")
    ap.add_argument("--rivers", metavar="CSV", help="mapgen/config/canon_rivers.csv")
    ap.add_argument("--markdown", action="store_true", help="print the generated note blocks")
    ap.add_argument("--render", action="store_true", help="write state_prior_class_review.png (needs --classes)")
    args = ap.parse_args(argv)
    if args.render and not args.classes:
        ap.error("--render needs --classes")
    extras: dict = {}
    rows = tabulate(REPO_ROOT, classes=args.classes, rivers=args.rivers, _extras=extras)
    derived = REPO_ROOT / "scratchpad"
    derived.mkdir(parents=True, exist_ok=True)
    write_csv(rows, derived / "state_physical_prior.csv")
    dis = [r for r in rows if r["phys_disagree"]]
    hd = [r for r in rows if r["heat_disagree"] == 1]
    print(f"{len(rows)} drawn states -> scratchpad/state_physical_prior.csv")
    if args.classes:
        print(f"phys_disagree: {len(dis)} (all carry override_ref); heat_disagree: {len(hd)}")
    if args.markdown:
        md = markdown(rows, REPO_ROOT, bool(args.classes))
        (derived / "state_prior_generated.md").write_text(md, encoding="utf-8", newline="\n")
        print(md)
    if args.render:
        render(rows, extras, derived / "state_prior_class_review.png")
        print("wrote scratchpad/state_prior_class_review.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
