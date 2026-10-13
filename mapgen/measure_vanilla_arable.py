#!/usr/bin/env python3
"""Measure how Victoria 3's own map sizes arable land, by climate class (#3676).

Dev-only and never loaded by the game. The calibration table in
``planning/economics/arable_land_engine_research.md`` is **measured by this
script** against the read-only vanilla install, not recalled, so it can be
re-checked in seconds on any machine that has the game.

    state_regions/*.txt        id, arable_land, subsistence_building, provinces,
                               traits (vanilla ``STATE_*`` land states)
    provinces.png              colour -> px -> per-state px, mean row -> latitude
                               (Miller frame, ``canvas_frame.km2_per_px``) -> km^2
    common/history/pops/*.txt  1836 pop totals per state (vanilla's own start date)
    config/vanilla_state_climate_classes.csv
                               the hand-authored class of every land state

Modes (all read-only against the install):

    python mapgen/measure_vanilla_arable.py             write scratchpad/vanilla_arable_states.csv
                                                        and vanilla_arable_calibration.md (the block)
    python mapgen/measure_vanilla_arable.py --propose   write scratchpad/vanilla_state_climate_proposal.csv
                                                        from the mechanical rule set below
    python mapgen/measure_vanilla_arable.py --check     regenerate the block and diff it against the note
                                                        between the BEGIN/END markers; also fails on any
                                                        unclassified state, any class id outside
                                                        :data:`CLASS_IDS`, or an area self-test failure
    python mapgen/measure_vanilla_arable.py --selftest  install-free: area formula, parser, class-id set

``--game PATH`` overrides the install. Outputs are sorted, floats fixed-format,
no RNG and no wall clock, so a re-run is byte-identical.

The class map is the persisted judgment. ``--propose`` only bounds the effort of
writing it (rule order below); once the config CSV exists the script never
re-infers a class from the proposal. A class with fewer than :data:`THIN_N`
comparable-geography states is flagged ``thin`` and the world block is its
reference; classes are never merged to pad n.

Area caveat: vanilla draws small islands oversized (Malta about 4.7x, Azores
2.8x), so per-km^2 figures for island and fishing-village states are unreliable;
read those rows on the per-state columns. ``impassable`` provinces count toward a
state's pixels (vanilla's own convention).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import canvas_frame  # noqa: E402
from measure_vanilla_frame import (  # noqa: E402
    VANILLA_ROOT,
    _assert_writable,
    parse_state_provinces,
    state_centroids,
)

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"  # QA renders and previews; gitignored at the repo root
CLASS_CSV = TOOLS_DIR / "config" / "vanilla_state_climate_classes.csv"
NOTE_PATH = REPO_ROOT / "planning" / "economics" / "arable_land_engine_research.md"
LAND_INDEX = DERIVED_DIR / "land_regions_index.json"
MOD_STATE_DIR = REPO_ROOT / "map_data" / "state_regions"
MOD_PROVINCES = REPO_ROOT / "map_data" / "provinces.png"

BEGIN_MARK = "<!-- BEGIN measure_vanilla_arable -->"
END_MARK = "<!-- END measure_vanilla_arable -->"

#: Canvas y of vanilla's equator, **measured** by ``measure_vanilla_frame.py`` on
#: the 29-island anchor set (pinned-R Miller, median offset: 2102.8). The mod's own
#: ``canvas_frame.Y0`` (2142.0) is a drawn northern limit, not vanilla's, so the
#: vanilla latitude of a state row uses this constant. The build that introduced
#: this script confirmed the value by running ``measure_vanilla_frame.py`` once.
Y0_VANILLA = 2102.8

#: The eleven climate classes, fixed by #3676 and reused verbatim by #3677.
CLASS_IDS = (
    "arctic_boreal_coast",
    "boreal_forest",
    "temperate_river_plain",
    "temperate_forest_hill",
    "mediterranean",
    "steppe",
    "desert_river",
    "open_desert",
    "highland_alpine",
    "tropical_savanna",
    "tropical_forest",
)

BASIS_FIXED = ("subsistence", "latitude", "file_default", "manual")

#: Vanilla files whose geography the mod's Old World resembles (#3684's budget
#: set): West/South/East Europe, North Africa, Middle East, Russia.
COMPARABLE_PREFIXES = ("00", "01", "02", "03", "08", "15")

#: A class with fewer comparable-block states than this is flagged ``thin``.
THIN_N = 8

#: Back-test hit window: prediction within x0.67 .. x1.5 of the real value.
HIT_LO, HIT_HI = 0.67, 1.5

#: Reference areas for the area self-test (real km^2; the mod's note quotes them):
#: Ile-de-France, Normandy, Bohemia, Iceland. Measured area must land within 5 %.
AREA_REFERENCE = (
    ("STATE_ILE_DE_FRANCE", 12012.0),
    ("STATE_NORMANDY", 29906.0),
    ("STATE_BOHEMIA", 52065.0),
    ("STATE_ICELAND", 103000.0),
)
AREA_TOLERANCE = 0.05

#: Illustrative dominant climate class per mod realm file, for the 4.7 sanity table
#: only: the realm's total is sized as ``states x that class's median``. It is NOT
#: an assignment (the per-state class map is #3677's), and a realm file missing here
#: fails the run so a new realm gets a deliberate label. Lore anchors: Brettonia is
#: the Loire/Seine analogue, Karaz Ankor the mountain holds, the Badlands and Dark
#: Lands arid pasture, Nehekhara the Nile-pattern river strip.
REALM_ILLUSTRATIVE_CLASS = {
    "badlands": "steppe",
    "brettonia": "temperate_river_plain",
    "dark_lands": "steppe",
    "empire": "temperate_forest_hill",
    "karaz_ankor": "highland_alpine",
    "kislev": "boreal_forest",
    "nehekhara": "desert_river",
    "norsca": "boreal_forest",
    "southern_realms": "mediterranean",
}

#: Region traits whose subsistence-building split the §6 ruling cites (table 4.2b).
PATTERN_TRAITS = (
    "alps_mountains", "rocky_mountains", "andes", "himalayas_mountains", "zagros_mountains",
    "atlas_mountains", "caucasus_mountains", "sahara_desert", "arabian_desert", "sahel",
    "siberian_terrain", "gobi_desert", "australian_desert", "western_steppe", "eastern_steppe",
    "pampas", "the_great_plains", "nile_river", "mesopotamian_floodplain", "euphrates_river",
    "tigris_river", "russian_forest", "scandinavian_forests",
)

SUBSISTENCE_SHORT = {
    "building_subsistence_farm": "farm",
    "building_subsistence_pasture": "pasture",
    "building_subsistence_orchard": "orchard",
    "building_subsistence_fishing_village": "fishing_village",
    "building_subsistence_rice_farm": "rice",
}
SUBSISTENCE_ORDER = ("farm", "pasture", "orchard", "fishing_village", "rice")

EXPECTED_LAND_STATES = 675
EXPECTED_DRAWN_STATES = 343
EXPECTED_DRAWN_PROVINCES = 4442

# ---------------------------------------------------------------------------
# Proposal rules (--propose). Order matters; see the module docstring.
# ---------------------------------------------------------------------------

TRAIT_CLASS = (
    (("sahara_desert", "arabian_desert"), "open_desert"),
    (("sahel",), "tropical_savanna"),
    (("nile_river", "euphrates_river", "tigris_river", "mesopotamian_floodplain",
      "indus_river"), "desert_river"),
    (("alps_mountains", "andes", "himalayas_mountains", "zagros_mountains",
      "rocky_mountains", "atlas_mountains"), "highland_alpine"),
    (("western_steppe", "eastern_steppe", "pampas", "the_great_plains"), "steppe"),
    (("amazon_rainforest", "congo_forest", "indochinese_forest"), "tropical_forest"),
    (("russian_forest", "scandinavian_forests", "siberian_terrain",
      "northern_canadian_terrain"), "boreal_forest"),
)
SIBERIAN_RIVERS = ("ob_river", "irtysh_river", "yenisei_river", "lena_river", "amur_river")
RIVER_FILE_PREFIXES = ("00", "01", "02", "15")
FILE_DEFAULT = {
    "00": "temperate_forest_hill",
    "01": "mediterranean",
    "02": "temperate_river_plain",
    "03": "open_desert",
    "08": "open_desert",
    "04": "tropical_savanna",
    "12": "tropical_forest",
    "14": "boreal_forest",
    "15": "temperate_forest_hill",
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_HEAD_RE = re.compile(r"^(STATE_[A-Z0-9_]+)\s*=\s*\{", re.MULTILINE)
_COMMENT_RE = re.compile(r"#[^\n]*")
_HEX_RE = re.compile(r'"?x([0-9A-Fa-f]{6})"?')
_ID_RE = re.compile(r"^[ \t]*id[ \t]*=[ \t]*(\d+)", re.MULTILINE)
_ARABLE_RE = re.compile(r"^[ \t]*arable_land[ \t]*=[ \t]*(\d+)", re.MULTILINE)
_SUBS_RE = re.compile(r'^[ \t]*subsistence_building[ \t]*=[ \t]*"?([A-Za-z0-9_]+)"?', re.MULTILINE)
_PORT_RE = re.compile(r"^[ \t]*port[ \t]*=", re.MULTILINE)
_POPS_HEAD_RE = re.compile(r"s:(STATE_[A-Z0-9_]+)\s*=\s*\{")
_SIZE_RE = re.compile(r"\bsize\s*=\s*(\d+)")


def _list_block(block: str, name: str) -> str:
    m = re.search(r"\b" + name + r"\s*=\s*\{([^}]*)\}", block)
    return m.group(1) if m else ""


def parse_states(text: str) -> dict[str, dict]:
    """Every ``STATE_X = { ... }`` block of one state-region file.

    Keys per state: ``id``, ``arable`` (None for sea states), ``subsistence``
    (the long building id or None), ``colours`` (packed province colours, in file
    order), ``traits`` (names without the ``state_trait_`` prefix), ``impassable``
    (colour count), ``has_port``. ``#`` comments are stripped first (a leading BOM is stripped here; the
    callers also read ``utf-8-sig``). Not a general Clausewitz parser: vanilla lays every
    state out as a top-level ``^STATE_X = {`` header, which is all this needs.
    """
    text = _COMMENT_RE.sub("", text.lstrip("\ufeff"))
    heads = list(_HEAD_RE.finditer(text))
    out: dict[str, dict] = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[m.start():end]
        idm = _ID_RE.search(block)
        am = _ARABLE_RE.search(block)
        sm = _SUBS_RE.search(block)
        traits = [t[len("state_trait_"):] if t.startswith("state_trait_") else t
                  for t in re.findall(r'"?([A-Za-z0-9_]+)"?', _list_block(block, "traits"))]
        out[m.group(1)] = {
            "id": int(idm.group(1)) if idm else None,
            "arable": int(am.group(1)) if am else None,
            "subsistence": sm.group(1) if sm else None,
            "colours": [int(h, 16) for h in _HEX_RE.findall(_list_block(block, "provinces"))],
            "traits": traits,
            "impassable": len(_HEX_RE.findall(_list_block(block, "impassable"))),
            "has_port": bool(_PORT_RE.search(block)),
        }
    return out


def parse_pop_totals(text: str) -> dict[str, int]:
    """``STATE_X -> sum of create_pop size`` from one ``common/history/pops`` file.

    Brace-matched per ``s:STATE_X = { ... }`` block (a state can hold several
    ``region_state`` owners); a state seen twice accumulates.
    """
    text = _COMMENT_RE.sub("", text)
    out: dict[str, int] = {}
    pos = 0
    while True:
        m = _POPS_HEAD_RE.search(text, pos)
        if m is None:
            break
        depth, i = 1, m.end()
        while i < len(text) and depth:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        block = text[m.end():i]
        out[m.group(1)] = out.get(m.group(1), 0) + sum(int(s) for s in _SIZE_RE.findall(block))
        pos = i
    return out


def load_vanilla(game: Path) -> list[dict]:
    """All vanilla land states (those with an ``arable_land``), sorted by key."""
    state_dir = game / "map_data" / "state_regions"
    pops_dir = game / "common" / "history" / "pops"
    if not state_dir.is_dir() or not pops_dir.is_dir():
        raise SystemExit(f"vanilla install not found under {game} (pass --game PATH)")
    states: list[dict] = []
    for path in sorted(state_dir.glob("*.txt")):
        if not re.match(r"\d\d_", path.name):
            continue
        parsed = parse_states(path.read_text(encoding="utf-8-sig", errors="replace"))
        for key, s in parsed.items():
            if s["arable"] is None:
                continue
            s["key"] = key
            s["file"] = path.stem
            s["prefix"] = path.stem[:2]
            states.append(s)
    pops: dict[str, int] = {}
    for path in sorted(pops_dir.glob("*.txt")):
        for k, v in parse_pop_totals(path.read_text(encoding="utf-8-sig", errors="replace")).items():
            pops[k] = pops.get(k, 0) + v
    for s in states:
        s["pops"] = pops.get(s["key"], 0)
        s["subs"] = SUBSISTENCE_SHORT[s["subsistence"]]
        s["n_prov"] = len(s["colours"])
    states.sort(key=lambda s: s["key"])
    return states


# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------

def state_true_areas(provinces_png: Path, state_regions_dir: Path, y0: float,
                     colours_by_state: dict[str, list[int]] | None = None
                     ) -> dict[str, tuple[int, float, float]]:
    """``state -> (px, latitude_deg, km2)`` from the bitmap under the shared Miller frame.

    Latitude is that of the state's mean pixel row; ``y0`` is the frame's equator
    row (vanilla's :data:`Y0_VANILLA`, or the mod's ``canvas_frame.Y0``). km2 is
    ``px * canvas_frame.km2_per_px(lat)``.
    """
    if colours_by_state is None:
        colours_by_state = parse_state_provinces(state_regions_dir)
    cents = state_centroids(provinces_png, colours_by_state)
    out: dict[str, tuple[int, float, float]] = {}
    for key in sorted(cents):
        _cx, cy, px = cents[key]
        lat = float(canvas_frame._miller_lat((y0 - cy) / canvas_frame.R_CANVAS))
        out[key] = (px, lat, float(px * canvas_frame.km2_per_px(lat)))
    return out


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def pct(values, q: float) -> float:
    """Linear-interpolated percentile (``q`` in 0..100); deterministic."""
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def dist(values) -> dict[str, float]:
    v = np.asarray(values, dtype=np.float64)
    return {
        "n": int(v.size), "mean": float(v.mean()), "median": pct(v, 50),
        "min": float(v.min()), "max": float(v.max()),
        "p10": pct(v, 10), "p25": pct(v, 25), "p75": pct(v, 75), "p90": pct(v, 90),
    }


def examples(group: list[dict]) -> str:
    """Min / median / max states of ``group`` by arable, ties by key (deterministic)."""
    ordered = sorted(group, key=lambda s: (s["arable"], s["key"]))
    pick = (ordered[0], ordered[(len(ordered) - 1) // 2], ordered[-1])
    return " / ".join(f"{s['key'][len('STATE_'):]} {s['arable']}" for s in pick)


def _f0(x: float) -> str:
    return f"{x:,.0f}"


def _f1(x: float) -> str:
    return f"{x:,.1f}"


def _f2(x: float) -> str:
    return f"{x:,.2f}"


def _per(a: float, b: float, scale: float = 1000.0) -> float:
    return a / b * scale if b else 0.0


def _median_or_nan(vals: list[float]) -> float:
    return pct(vals, 50) if vals else float("nan")


# ---------------------------------------------------------------------------
# Class map
# ---------------------------------------------------------------------------

def read_class_csv(path: Path) -> dict[str, dict]:
    """``state_key -> {climate_class, basis, note}``; duplicate keys are an error."""
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            key = row["state_key"]
            if key in out:
                raise SystemExit(f"{path.name}: duplicate state_key {key}")
            out[key] = {"climate_class": row["climate_class"], "basis": row["basis"],
                        "note": row.get("note", "")}
    return out


def validate_classes(classes: dict[str, dict], states: list[dict]) -> list[str]:
    """Problems with the class map against the vanilla land states (empty = fine)."""
    problems: list[str] = []
    keys = {s["key"] for s in states}
    for k in sorted(keys - set(classes)):
        problems.append(f"unclassified vanilla state: {k}")
    for k in sorted(set(classes) - keys):
        problems.append(f"class row for a state that is not a vanilla land state: {k}")
    for k in sorted(classes):
        row = classes[k]
        if row["climate_class"] not in CLASS_IDS:
            problems.append(f"{k}: class id {row['climate_class']!r} is not one of the fixed eleven")
        b = row["basis"]
        if not (b in BASIS_FIXED or (b.startswith("trait:") and len(b) > len("trait:"))):
            problems.append(f"{k}: basis {b!r} is not trait:<name>, subsistence, latitude, file_default or manual")
        if b == "manual" and not row["note"].strip():
            problems.append(f"{k}: basis=manual needs a one-word note")
    return problems


def propose_class(s: dict) -> tuple[str, str] | None:
    """Mechanical class for one state, or None. Returns ``(class_id, basis)``."""
    lat = s["lat"]
    if (s["subs"] == "fishing_village" and lat > 55.0) or (s["subs"] == "pasture" and lat > 60.0):
        return "arctic_boreal_coast", "latitude"
    traits = set(s["traits"])
    for names, cls in TRAIT_CLASS:
        for name in names:
            if name in traits:
                return cls, f"trait:{name}"
    if s["prefix"] in RIVER_FILE_PREFIXES:
        for t in sorted(traits):
            if t.endswith("_river") and t not in SIBERIAN_RIVERS:
                return "temperate_river_plain", f"trait:{t}"
    if s["prefix"] in FILE_DEFAULT:
        return FILE_DEFAULT[s["prefix"]], "file_default"
    return None


# ---------------------------------------------------------------------------
# Back-test
# ---------------------------------------------------------------------------

METHODS = (
    ("per_area", "class median density x true km^2"),
    ("per_state_median", "class median arable per state"),
    ("sqrt_damped", "class median x sqrt(km^2 / class median km^2)"),
    ("pop_anchored", "1836 pops / class median pops-per-arable"),
)


def backtest(states: list[dict], min_others: int = 3) -> dict[str, dict]:
    """Leave-one-out prediction of a state's arable from the rest of its class.

    ``states`` carry ``cls``, ``arable``, ``km2``, ``pops``. Per method:
    ``n`` tested, ``hit`` share of predictions within x0.67-1.5, and the p10 /
    median / p90 of ``prediction / actual``. A class needs ``min_others`` other
    states for a prediction to be made.
    """
    by_cls: dict[str, list[dict]] = {}
    for s in states:
        by_cls.setdefault(s["cls"], []).append(s)
    ratios: dict[str, list[float]] = {m: [] for m, _ in METHODS}
    for cls in sorted(by_cls):
        group = by_cls[cls]
        for s in group:
            others = [o for o in group if o is not s]
            if len(others) < min_others or s["km2"] <= 0:
                continue
            med_arable = pct([o["arable"] for o in others], 50)
            med_dens = pct([o["arable"] / o["km2"] for o in others], 50)
            med_km2 = pct([o["km2"] for o in others], 50)
            ppa = [o["pops"] / o["arable"] for o in others if o["pops"] > 0]
            preds = {
                "per_area": med_dens * s["km2"],
                "per_state_median": med_arable,
                "sqrt_damped": med_arable * math.sqrt(s["km2"] / med_km2),
            }
            if ppa and s["pops"] > 0:
                preds["pop_anchored"] = s["pops"] / pct(ppa, 50)
            for m, p in preds.items():
                ratios[m].append(p / s["arable"])
    out: dict[str, dict] = {}
    for m, _ in METHODS:
        r = np.asarray(ratios[m], dtype=np.float64)
        out[m] = {
            "n": int(r.size),
            "hit": float(((r >= HIT_LO) & (r <= HIT_HI)).mean()) if r.size else 0.0,
            "p10": pct(r, 10) if r.size else float("nan"),
            "median": pct(r, 50) if r.size else float("nan"),
            "p90": pct(r, 90) if r.size else float("nan"),
        }
    return out


def log_fit(group: list[dict]) -> tuple[float, float]:
    """``(slope of log arable on log km^2, Pearson r of log arable vs log pops)``."""
    usable = [s for s in group if s["km2"] > 0 and s["arable"] > 0]
    la = np.log([s["arable"] for s in usable])
    lk = np.log([s["km2"] for s in usable])
    slope = float(np.polyfit(lk, la, 1)[0]) if len(usable) >= 3 else float("nan")
    withpop = [s for s in usable if s["pops"] > 0]
    if len(withpop) >= 3:
        r = float(np.corrcoef(np.log([s["arable"] for s in withpop]),
                              np.log([s["pops"] for s in withpop]))[0, 1])
    else:
        r = float("nan")
    return slope, r


# ---------------------------------------------------------------------------
# Mod realm table (drawn states only)
# ---------------------------------------------------------------------------

def load_mod_drawn(repo: Path = REPO_ROOT) -> list[dict]:
    """The mod's drawn states with their realm file, province colours and port flag.

    ``land_regions_index.json`` supplies the roster counts (drawn regions and the
    provinces inside them); the per-state ``scope`` (``drawn`` / ``placeholder``)
    comes from ``state_ownership.json``, because the index's per-cell province
    ids are cell-local and do not join to the state files. Asserts 343 drawn
    states and 4,442 provinces in both, else exits.
    """
    index = json.loads((repo / "mapgen" / "derived" / "land_regions_index.json").read_text(encoding="utf-8"))
    own = json.loads((repo / "mapgen" / "derived" / "state_ownership.json").read_text(encoding="utf-8"))["states"]
    n_prov = sum(len(c["provinces"]) for c in index["cells"] if c["kind"] == "drawn")
    if (index["drawn_regions"], n_prov) != (EXPECTED_DRAWN_STATES, EXPECTED_DRAWN_PROVINCES):
        raise SystemExit(f"land_regions_index.json holds {index['drawn_regions']} drawn regions / "
                         f"{n_prov} provinces; this script asserts {EXPECTED_DRAWN_STATES} / "
                         f"{EXPECTED_DRAWN_PROVINCES}")
    drawn_keys = {k for k, v in own.items() if v.get("scope") == "drawn"}
    out: list[dict] = []
    for path in sorted((repo / "map_data" / "state_regions").glob("*.txt")):
        if not re.match(r"\d\d_", path.name) or path.name.startswith("99_"):
            continue
        for key, s in parse_states(path.read_text(encoding="utf-8-sig", errors="replace")).items():
            if key in drawn_keys:
                s["key"] = key
                s["realm"] = path.stem.split("_", 1)[1]
                s["file"] = path.stem
                out.append(s)
    out.sort(key=lambda s: s["key"])
    got = (len(out), sum(len(s["colours"]) for s in out))
    if got != (EXPECTED_DRAWN_STATES, EXPECTED_DRAWN_PROVINCES):
        raise SystemExit(f"mod state files give {got[0]} drawn states / {got[1]} provinces; "
                         f"expected {EXPECTED_DRAWN_STATES} / {EXPECTED_DRAWN_PROVINCES}")
    return out


def mod_areas(drawn: list[dict], png: Path) -> None:
    """Attach ``px``, ``lat``, ``km2`` to each drawn mod state (mod frame ``Y0``)."""
    if not png.is_file() or png.stat().st_size < 1024:
        raise SystemExit(f"{png} is missing or a Git-LFS pointer; run `git lfs pull`")
    res = state_true_areas(png, MOD_STATE_DIR, canvas_frame.Y0,
                           {s["key"]: s["colours"] for s in drawn})
    for s in drawn:
        if s["key"] not in res:
            raise SystemExit(f"no pixels in {png.name} for mod state {s['key']}")
        s["px"], s["lat"], s["km2"] = res[s["key"]]


# ---------------------------------------------------------------------------
# The generated block
# ---------------------------------------------------------------------------

def build_block(states: list[dict], drawn: list[dict], area_checks: list[tuple]) -> str:
    """The calibration block (text between the markers), from joined state rows."""
    L: list[str] = []
    add = L.append
    comp = [s for s in states if s["prefix"] in COMPARABLE_PREFIXES]
    arable_all = [s["arable"] for s in states]
    d_all = dist(arable_all)
    deciles = [pct(arable_all, q) for q in range(10, 100, 10)]
    provs = sum(s["n_prov"] for s in states)

    add(BEGIN_MARK)
    add("<!-- generated by mapgen/measure_vanilla_arable.py; do not hand-edit (run it, then --check) -->")
    add("")
    add("#### 4.0 Headline (all vanilla land states)")
    add("")
    add(f"- Land states **{len(states)}**; total arable **{_f0(sum(arable_all))}**; mean {_f1(d_all['mean'])}, "
        f"median {_f0(d_all['median'])}, min {_f0(d_all['min'])}, max {_f0(d_all['max'])}.")
    add(f"- Deciles (p10..p90): {' / '.join(_f0(x) for x in deciles)}.")
    add(f"- States with arable at or below 5: {sum(1 for x in arable_all if x <= 5)} (exactly 2: "
        f"{sum(1 for x in arable_all if x == 2)}).")
    add(f"- Listed land provinces {_f0(provs)}; arable per province {_f2(sum(arable_all) / provs)}.")
    add(f"- Comparable geography (vanilla files {', '.join(COMPARABLE_PREFIXES)}): {len(comp)} states, "
        f"median {_f0(pct([s['arable'] for s in comp], 50))}, mean {_f1(float(np.mean([s['arable'] for s in comp])))}, "
        f"arable per 1,000 km^2 {_f2(_per(sum(s['arable'] for s in comp), sum(s['km2'] for s in comp)))} aggregate "
        f"/ {_f2(pct([_per(s['arable'], s['km2']) for s in comp], 50))} median.")
    pops_all = [s["pops"] / s["arable"] for s in states if s["pops"] > 0]
    add(f"- 1836 pops per arable (vanilla `common/history/pops`, vanilla's own start date): median "
        f"{_f0(pct(pops_all, 50))} over {len(pops_all)} states; {sum(1 for x in pops_all if x < 5000)} states "
        f"below 5,000 and {sum(1 for x in pops_all if x > 100000)} above 100,000.")
    add(f"- Area self-test (px x `canvas_frame.km2_per_px` at the state's mean row, vanilla Y0 {Y0_VANILLA}): "
        + "; ".join(f"{k[len('STATE_'):]} {_f0(m)} vs {_f0(r)} ({(m / r - 1) * 100:+.1f} %)"
                    for k, m, r in area_checks) + ".")
    add("")

    add("#### 4.1 By vanilla file")
    add("")
    add("| file | n | mean arable | median | pasture states | pops per arable (median) |")
    add("|---|---|---|---|---|---|")
    for prefix in sorted({s["prefix"] for s in states}):
        g = [s for s in states if s["prefix"] == prefix]
        ppa = [s["pops"] / s["arable"] for s in g if s["pops"] > 0]
        add(f"| {g[0]['file']} | {len(g)} | {_f1(float(np.mean([s['arable'] for s in g])))} | "
            f"{_f0(pct([s['arable'] for s in g], 50))} | {sum(1 for s in g if s['subs'] == 'pasture')} | "
            f"{_f0(pct(ppa, 50)) if ppa else 'n/a'} |")
    add("")

    add("#### 4.2 By subsistence building")
    add("")
    add("| type | n | mean | median | min | max | per 1,000 px | per 1,000 km^2 (agg / median) | pops per arable (median) | min / median / max state |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for t in SUBSISTENCE_ORDER:
        g = [s for s in states if s["subs"] == t]
        d = dist([s["arable"] for s in g])
        ppa = [s["pops"] / s["arable"] for s in g if s["pops"] > 0]
        add(f"| {t} | {d['n']} | {_f1(d['mean'])} | {_f0(d['median'])} | {_f0(d['min'])} | {_f0(d['max'])} | "
            f"{_f2(_per(sum(s['arable'] for s in g), sum(s['px'] for s in g)))} | "
            f"{_f2(_per(sum(s['arable'] for s in g), sum(s['km2'] for s in g)))} / "
            f"{_f2(pct([_per(s['arable'], s['km2']) for s in g], 50))} | "
            f"{_f0(pct(ppa, 50)) if ppa else 'n/a'} | {examples(g)} |")
    add("")
    add("Per-km^2 columns: vanilla draws small islands oversized (Malta about 4.7x, Azores 2.8x, Ryukyu 3.0x), "
        "so read island and `fishing_village` rows on the per-state columns.")
    add("")

    add("#### 4.2b Subsistence building by region trait")
    add("")
    add("Vanilla's own choice of type for the geography (states carrying the trait):")
    add("")
    add("| trait | states | farm | pasture | orchard | fishing_village | rice |")
    add("|---|---|---|---|---|---|---|")
    for tr in PATTERN_TRAITS:
        g = [s for s in states if tr in s["traits"]]
        add(f"| {tr} | {len(g)} | " + " | ".join(str(sum(1 for s in g if s["subs"] == t_))
                                                  for t_ in SUBSISTENCE_ORDER) + " |")
    add("")
    add("#### 4.2c Subsistence building by climate class")
    add("")
    add("World block; the example is the state at that group's median arable, for up to four classes by count:")
    add("")
    add("| type | classes used (n) | named examples across climates |")
    add("|---|---|---|")
    for t_ in SUBSISTENCE_ORDER:
        g = [s for s in states if s["subs"] == t_]
        counts = {c: sum(1 for s in g if s["cls"] == c) for c in CLASS_IDS}
        used = sorted((c for c in CLASS_IDS if counts[c]), key=lambda c: (-counts[c], c))
        ex = []
        for c in used[:4]:
            cg = sorted((s for s in g if s["cls"] == c), key=lambda s: (s["arable"], s["key"]))
            m_ = cg[(len(cg) - 1) // 2]
            ex.append(f"{c}: {m_['key'][len('STATE_'):]} {m_['arable']}")
        add(f"| {t_} | {', '.join(f'{c} ({counts[c]})' for c in used)} | {'; '.join(ex)} |")
    add("")

    def class_tables(group: list[dict], title: str, anchor: str) -> None:
        add(f"#### {anchor} {title}")
        add("")
        add("| class | n | flag | mean | median | min | max | p10 | p25 | p75 | p90 | min / median / max state |")
        add("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cls in CLASS_IDS:
            g = [s for s in group if s["cls"] == cls]
            if not g:
                add(f"| {cls} | 0 | empty | - | - | - | - | - | - | - | - | - |")
                continue
            d = dist([s["arable"] for s in g])
            flag = "thin" if len(g) < THIN_N else ""
            add(f"| {cls} | {d['n']} | {flag} | {_f1(d['mean'])} | {_f0(d['median'])} | {_f0(d['min'])} | "
                f"{_f0(d['max'])} | {_f0(d['p10'])} | {_f0(d['p25'])} | {_f0(d['p75'])} | {_f0(d['p90'])} | "
                f"{examples(g)} |")
        add("")
        add("| class | provinces (median) | arable per province | per 1,000 px | per 1,000 km^2 (agg) | per 1,000 km^2 (median) | state km^2 (median) | km^2 p10 / p90 | pops per arable (median) |")
        add("|---|---|---|---|---|---|---|---|---|")
        for cls in CLASS_IDS:
            g = [s for s in group if s["cls"] == cls]
            if not g:
                continue
            ppa = [s["pops"] / s["arable"] for s in g if s["pops"] > 0]
            kd = dist([s["km2"] for s in g])
            add(f"| {cls} | {_f0(pct([s['n_prov'] for s in g], 50))} | "
                f"{_f2(sum(s['arable'] for s in g) / sum(s['n_prov'] for s in g))} | "
                f"{_f2(_per(sum(s['arable'] for s in g), sum(s['px'] for s in g)))} | "
                f"{_f2(_per(sum(s['arable'] for s in g), sum(s['km2'] for s in g)))} | "
                f"{_f2(pct([_per(s['arable'], s['km2']) for s in g], 50))} | {_f0(kd['median'])} | "
                f"{_f0(kd['p10'])} / {_f0(kd['p90'])} | {_f0(pct(ppa, 50)) if ppa else 'n/a'} |")
        add("")

    class_tables(comp, f"By climate class: comparable geography ({len(comp)} states, vanilla files "
                       f"{', '.join(COMPARABLE_PREFIXES)})", "4.3")
    class_tables(states, f"By climate class: world ({len(states)} states)", "4.4")

    # Band table: the numbers #3677 consumes.
    add("#### 4.5 Class bands for the model (comparable block; world block for `thin` classes)")
    add("")
    add("| class | band source | n | p25 | median | p75 | km^2 p10 / p90 | peasant capacity at median (x5,000) |")
    add("|---|---|---|---|---|---|---|---|")
    bands: dict[str, dict] = {}
    for cls in CLASS_IDS:
        cg = [s for s in comp if s["cls"] == cls]
        thin = len(cg) < THIN_N
        g = [s for s in states if s["cls"] == cls] if thin else cg
        d = dist([s["arable"] for s in g])
        kd = dist([s["km2"] for s in g])
        bands[cls] = d
        add(f"| {cls} | {'world (thin)' if thin else 'comparable'} | {d['n']} | {_f0(d['p25'])} | "
            f"{_f0(d['median'])} | {_f0(d['p75'])} | {_f0(kd['p10'])} / {_f0(kd['p90'])} | "
            f"{_f0(d['median'] * 5000)} |")
    add("")

    # Back-test.
    bt = backtest([s for s in comp])
    add("#### 4.6 Leave-one-out back-test (comparable block)")
    add("")
    add(f"Each state's arable is predicted from the other states of its class (classes with at least 3 others); "
        f"a hit is a prediction within x{HIT_LO}-{HIT_HI} of the real value.")
    add("")
    add("| method | prediction | n tested | hit rate | pred / actual p10 | median | p90 |")
    add("|---|---|---|---|---|---|---|")
    for m, desc in METHODS:
        r = bt[m]
        add(f"| {m} | {desc} | {r['n']} | {r['hit'] * 100:.0f} % | {_f2(r['p10'])} | {_f2(r['median'])} | {_f2(r['p90'])} |")
    add("")
    add("| class (comparable block) | n | log arable ~ log km^2 slope | r(log arable, log pops) |")
    add("|---|---|---|---|")
    for cls in CLASS_IDS:
        g = [s for s in comp if s["cls"] == cls]
        if len(g) < 3:
            continue
        slope, r = log_fit(g)
        add(f"| {cls} | {len(g)} | {slope:.2f} | {r:.2f} |")
    add("")

    # Mod realm table.
    add("#### 4.7 The mod's drawn states by realm file (sanity check, not an assignment)")
    add("")
    n_drawn = len(drawn)
    n_prov = sum(len(s["colours"]) for s in drawn)
    cm = dist([s["arable"] for s in comp])
    add(f"Drawn states **{n_drawn}**, provinces **{_f0(n_prov)}** ({_f2(n_prov / n_drawn)} per drawn state against "
        f"vanilla's {_f1(provs / len(states))}), measured under the mod frame (`canvas_frame.Y0` {canvas_frame.Y0}). "
        f"\"Illustrative class\" is a hand-set label per realm file (`REALM_ILLUSTRATIVE_CLASS` in the script) used "
        f"only to size the realm total; it is never a state's class.")
    add("")
    add("| realm | states | provinces | px | km^2 | latitude range | coastal (port) | illustrative class | class median | n x class median |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    tot_anchor = 0.0
    for realm in sorted({s["realm"] for s in drawn}):
        g = [s for s in drawn if s["realm"] == realm]
        if realm not in REALM_ILLUSTRATIVE_CLASS:
            raise SystemExit(f"realm file {realm!r} has no REALM_ILLUSTRATIVE_CLASS entry")
        near = REALM_ILLUSTRATIVE_CLASS[realm]
        anchor = len(g) * bands[near]["median"]
        tot_anchor += anchor
        add(f"| {realm} | {len(g)} | {_f0(sum(len(s['colours']) for s in g))} | {_f0(sum(s['px'] for s in g))} | "
            f"{_f0(sum(s['km2'] for s in g))} | {min(s['lat'] for s in g):.1f} to {max(s['lat'] for s in g):.1f} | "
            f"{sum(1 for s in g if s['has_port'])} | {near} | {_f0(bands[near]['median'])} | {_f0(anchor)} |")
    add(f"| **total** | {n_drawn} | {_f0(n_prov)} | {_f0(sum(s['px'] for s in drawn))} | "
        f"{_f0(sum(s['km2'] for s in drawn))} | {min(s['lat'] for s in drawn):.1f} to {max(s['lat'] for s in drawn):.1f} | "
        f"{sum(1 for s in drawn if s['has_port'])} | | | {_f0(tot_anchor)} |")
    add("")
    naive = n_drawn * cm["median"]
    lo, hi = n_drawn * cm["p25"], n_drawn * cm["p75"]
    add(f"- Naive per-state anchor: {n_drawn} drawn states x comparable median {_f0(cm['median'])} = **{_f0(naive)} arable** "
        f"(peasant capacity {naive * 5000 / 1e6:,.1f} M at 5,000 per level); comparable p25-p75 band x {n_drawn} = "
        f"{_f0(lo)} to {_f0(hi)} arable ({lo * 5000 / 1e6:,.1f} to {hi * 5000 / 1e6:,.1f} M).")
    dens = _per(sum(s["arable"] for s in comp), sum(s["km2"] for s in comp))
    add(f"- Per-area cross-check: comparable aggregate density {_f2(dens)} per 1,000 km^2 x the mod's "
        f"{_f0(sum(s['km2'] for s in drawn))} km^2 = {_f0(dens * sum(s['km2'] for s in drawn) / 1000)} arable.")
    add(END_MARK)
    return "\n".join(L) + "\n"


def build_state_csv(states: list[dict]) -> str:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["state_key", "file", "class", "subsistence", "arable", "provinces", "px",
                "lat_deg", "km2", "pops_1836"])
    for s in states:
        w.writerow([s["key"], s["file"], s["cls"], s["subs"], s["arable"], s["n_prov"], s["px"],
                    f"{s['lat']:.3f}", f"{s['km2']:.1f}", s["pops"]])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

#: Independent expected km^2 per px at 0/30/52/68 deg: (40075.017/8192)^2 x cos(phi) x cos(0.8 phi),
#: computed with plain math.cos outside the function under test.
_EXPECTED_KM2 = ((0.0, 23.9314), (30.0, 18.9334), (52.0, 11.0178), (68.0, 5.2186))

_SNIPPET = (
    "﻿STATE_ALPHA = {\n"
    "    id = 1\n"
    '    subsistence_building = "building_subsistence_pasture"\n'
    '    provinces = { "x0974E5" "x216569" }  # two provinces\n'
    '    traits = { "state_trait_sahel" "state_trait_natural_harbors" }\n'
    "    port = x216569\n"
    "    arable_land = 30\n"
    "}\n"
    "# STATE_COMMENTED = { arable_land = 99 }\n"
    "STATE_SEA = {\n"
    "    id = 3000\n"
    '    provinces = { "x000001" }\n'
    "}\n"
)

_POPS_SNIPPET = (
    "POPS = {\n"
    "\ts:STATE_ALPHA = {\n"
    "\t\tregion_state:AAA = {\n"
    "\t\t\tcreate_pop = {\n\t\t\t\tculture = a\n\t\t\t\tsize = 100\n\t\t\t}\n"
    "\t\t\tcreate_pop = { size = 50 }  # size = 9999\n"
    "\t\t}\n"
    "\t\tregion_state:BBB = { create_pop = { size = 7 } }\n"
    "\t}\n"
    "\ts:STATE_BETA = { region_state:CCC = { create_pop = { size = 5 } } }\n"
    "}\n"
)


def selftest() -> int:
    fails: list[str] = []

    for lat, want in _EXPECTED_KM2:
        got = float(canvas_frame.km2_per_px(lat))
        if abs(got - want) > 0.005:
            fails.append(f"km2_per_px({lat}) = {got:.4f}, expected {want:.4f}")
    arr = canvas_frame.km2_per_px(np.array([0.0, 30.0]))
    if arr.shape != (2,):
        fails.append("km2_per_px does not accept arrays")

    parsed = parse_states(_SNIPPET)
    a = parsed.get("STATE_ALPHA")
    if sorted(parsed) != ["STATE_ALPHA", "STATE_SEA"]:
        fails.append(f"parse_states keys {sorted(parsed)} (BOM or comment handling)")
    elif not (a["id"] == 1 and a["arable"] == 30 and a["subsistence"] == "building_subsistence_pasture"
              and a["colours"] == [0x0974E5, 0x216569] and a["traits"] == ["sahel", "natural_harbors"]
              and a["has_port"]):
        fails.append(f"parse_states STATE_ALPHA wrong: {a}")
    elif parsed["STATE_SEA"]["arable"] is not None:
        fails.append("sea state should have no arable_land")

    pops = parse_pop_totals(_POPS_SNIPPET)
    if pops != {"STATE_ALPHA": 157, "STATE_BETA": 5}:
        fails.append(f"parse_pop_totals gave {pops}")

    if len(set(CLASS_IDS)) != 11 or any(not re.fullmatch(r"[a-z_]+", c) for c in CLASS_IDS):
        fails.append("CLASS_IDS is not eleven distinct snake_case ids")
    probe = [{"key": "STATE_ALPHA"}]
    bad = validate_classes({"STATE_ALPHA": {"climate_class": "desert", "basis": "manual", "note": ""}}, probe)
    if len(bad) != 2:
        fails.append(f"validate_classes should reject id, manual note: {bad}")
    ok = validate_classes({"STATE_ALPHA": {"climate_class": "steppe", "basis": "trait:pampas", "note": ""}}, probe)
    if ok:
        fails.append(f"validate_classes rejected a valid row: {ok}")

    if abs(pct([1, 2, 3, 4], 50) - 2.5) > 1e-12 or abs(pct([10, 20], 25) - 12.5) > 1e-12:
        fails.append("pct is not linear-interpolated")
    toy = [{"cls": "x", "arable": a_, "km2": 100.0 * (i + 1), "pops": a_ * 1000, "key": f"S{i}"}
           for i, a_ in enumerate([10, 20, 30, 40, 50])]
    r = backtest(toy)
    if r["per_state_median"]["n"] != 5 or r["pop_anchored"]["hit"] != 1.0:
        fails.append(f"backtest toy case wrong: {r}")

    if fails:
        print("SELFTEST FAILED")
        for f in fails:
            print("  - " + f)
        return 1
    print("selftest OK: area factors (0/30/52/68 deg), parser (BOM, comment, quoted colours, traits), "
          "pop parser, class-id set, class validation, percentile, back-test toy case")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _out_path(path: Path, game: Path) -> Path:
    """A writable output path: refuses anything inside the vanilla install."""
    resolved = _assert_writable(path)
    root = Path(game).resolve()
    if resolved == root or root in resolved.parents:
        raise SystemExit(f"refusing to write inside the read-only vanilla install: {resolved}")
    return resolved


def _write(path: Path, text: str, game: Path) -> Path:
    out = _out_path(path, game)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return out


def _measure(game: Path) -> tuple[list[dict], list[tuple]]:
    """Vanilla states with px / lat / km2 joined, plus the area self-test results."""
    states = load_vanilla(game)
    if len(states) != EXPECTED_LAND_STATES:
        raise SystemExit(f"parsed {len(states)} vanilla land states, expected {EXPECTED_LAND_STATES}")
    state_dir = game / "map_data" / "state_regions"
    png = game / "map_data" / "provinces.png"
    if not png.is_file():
        raise SystemExit(f"vanilla provinces.png not found under {game}")
    colours = parse_state_provinces(state_dir)
    for s in states:
        if colours.get(s["key"]) != s["colours"]:
            raise SystemExit(f"{s['key']}: province list differs from measure_vanilla_frame.parse_state_provinces")
    res = state_true_areas(png, state_dir, Y0_VANILLA, {s["key"]: s["colours"] for s in states})
    for s in states:
        if s["key"] not in res:
            raise SystemExit(f"no pixels in vanilla provinces.png for {s['key']}")
        s["px"], s["lat"], s["km2"] = res[s["key"]]
    checks = []
    for key, real in AREA_REFERENCE:
        checks.append((key, res[key][2], real))
    return states, checks


def _extract_block(note: str) -> str | None:
    a, b = note.find(BEGIN_MARK), note.find(END_MARK)
    if a < 0 or b < 0 or b < a:
        return None
    return note[a:b + len(END_MARK)]


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--game", type=Path, default=VANILLA_ROOT, help="vanilla game folder (read-only)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--propose", action="store_true", help="write the mechanical class proposal CSV")
    mode.add_argument("--check", action="store_true", help="regenerate the block and diff it against the note")
    mode.add_argument("--selftest", action="store_true", help="install-free self-test")
    p.add_argument("--classes", type=Path, default=CLASS_CSV, help="class map CSV")
    p.add_argument("--note", type=Path, default=NOTE_PATH, help="findings note holding the block")
    args = p.parse_args(argv)

    if args.selftest:
        return selftest()

    game = Path(args.game)
    states, area_checks = _measure(game)

    bad_area = [f"{k}: {m:,.0f} km^2 vs real {r:,.0f} ({(m / r - 1) * 100:+.1f} %)"
                for k, m, r in area_checks if abs(m / r - 1) > AREA_TOLERANCE]

    if args.propose:
        rows = []
        for s in states:
            pr = propose_class(s)
            rows.append((s["key"], pr[0] if pr else "", pr[1] if pr else "", s))
        buf = io.StringIO(newline="")
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["state_key", "climate_class", "basis", "note", "file", "subsistence", "arable", "lat_deg"])
        for key, cls, basis, s in rows:
            w.writerow([key, cls, basis, "", s["file"], s["subs"], s["arable"], f"{s['lat']:.1f}"])
        SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        out = _write(SCRATCH_DIR / "vanilla_state_climate_proposal.csv", buf.getvalue(), game)
        done = sum(1 for r in rows if r[1])
        print(f"proposed {done}/{len(rows)} ({done / len(rows) * 100:.0f} %) mechanically; wrote {out}")
        for cls in CLASS_IDS:
            print(f"  {cls:<22} {sum(1 for r in rows if r[1] == cls)}")
        print(f"  {'(manual review)':<22} {len(rows) - done}")
        return 0

    if not args.classes.is_file():
        raise SystemExit(f"{args.classes} not found; run --propose, review the rows, and commit the CSV")
    classes = read_class_csv(args.classes)
    problems = validate_classes(classes, states)
    if problems:
        print(f"CLASS MAP PROBLEMS ({len(problems)}):")
        for pr in problems[:40]:
            print("  - " + pr)
        return 1
    for s in states:
        s["cls"] = classes[s["key"]]["climate_class"]

    drawn = load_mod_drawn()
    mod_areas(drawn, MOD_PROVINCES)
    block = build_block(states, drawn, area_checks)

    if args.check:
        failures = [f"area self-test: {b}" for b in bad_area]
        note = args.note.read_text(encoding="utf-8-sig") if args.note.is_file() else None
        if note is None:
            failures.append(f"{args.note} not found")
        else:
            have = _extract_block(note)
            if have is None:
                failures.append(f"{args.note.name}: BEGIN/END markers not found")
            elif _norm(have) != _norm(block):
                import difflib
                diff = list(difflib.unified_diff(_norm(have).splitlines(), _norm(block).splitlines(),
                                                 "note", "regenerated", lineterm="", n=0))
                failures.append(f"block in {args.note.name} differs from the regenerated block "
                                f"({len(diff)} diff lines):\n" + "\n".join(diff[:60]))
        if failures:
            print("CHECK FAILED")
            for f in failures:
                print("  - " + f)
            return 1
        print(f"check OK: {len(states)} states classified into {len(set(s['cls'] for s in states))} of "
              f"{len(CLASS_IDS)} classes, block matches {args.note.name}, area self-test within "
              f"{AREA_TOLERANCE * 100:.0f} %")
        return 0

    if bad_area:
        print("WARNING area self-test: " + "; ".join(bad_area))
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    a = _write(SCRATCH_DIR / "vanilla_arable_states.csv", build_state_csv(states), game)
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    b = _write(SCRATCH_DIR / "vanilla_arable_calibration.md", block, game)
    print(f"wrote {a}\nwrote {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
