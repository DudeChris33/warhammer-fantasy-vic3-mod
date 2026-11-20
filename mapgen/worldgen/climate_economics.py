"""Farmland from the hybrid climate (board #3677; ruling Chris, 2026-11-20).

Every land state's ``arable_land``, ``subsistence_building`` and ``arable_resources`` default
comes from here; ``generate_land_regions.py`` does the I/O and ``validate_map.py`` re-checks the
stamp. Pure: numpy, ``fractions`` and ``hashlib`` only, no file access, no clock, no randomness.

The model
---------
* **Class per pixel** (:func:`hybrid_class`, vectorized by :func:`classify`). The #6617 terrain
  biome grid decides the family (:data:`BIOME_CLASS`); the #8202 wind layer
  (:data:`KOPPEN_CLASS`) refines only inside temperate land, by rules R1-R5 (:data:`RULES`).
  A tropical wind class never overrides the biome. Pixel ``(x, y)`` of ``provinces.png`` takes
  biome cell ``[y // q, x // q]``, wind value ``[y, x]`` and its row's latitude.
* **Weight** (:func:`class_pixels`, :func:`allocate`). A state's weight is the sum over its
  pixels, impassable included, of the vanilla world-block density of the pixel's class
  (:data:`CLASS_DENSITY_X100`, #3676 table 4.4, arable per 1,000 px x 100).
  :data:`WORLD_ARABLE` (vanilla's world total, table 4.0) is apportioned over all land states,
  placeholders included, by exact integer largest remainder (:func:`apportion_exact`).
* **Lore rows** are local. A row's class (``swap``) replaces the state's mix: its weight becomes
  ``pixels x density of that class``. A row's factor multiplies the weight. Either is valued on
  the climate-only scale (``WORLD_ARABLE x w / sum of climate-only weights``, rounded half up),
  so a row touches only its own state and the world total moves by the lore delta.
* **Floor**: no state is emitted below :data:`ARABLE_FLOOR`.
* **Class of a state** for subsistence and crops: the row's class, else the class carrying the
  largest ``passable pixels x density`` (where the farmland is, not where most of the area is).
  :func:`subsistence` and :data:`CLASS_CROPS` map it to the defaults.

:data:`MODEL_VERSION` is bumped by hand whenever a rule or :func:`subsistence` changes;
:func:`model_sha256` covers it and every constant, and the stamp
(``mapgen/derived/land_economics_stamp.json``) records it.
"""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction

import numpy as np

#: The eleven climate classes of #3676, in its order (``measure_vanilla_arable.CLASS_IDS``;
#: ``run_fixture.py`` asserts the two are equal).
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
_CI = {c: i for i, c in enumerate(CLASS_IDS)}

#: Vanilla arable per 1,000 map px x 100, all vanilla states of the class (world block):
#: ``planning/economics/arable_land_engine_research.md`` table 4.4, column "per 1,000 px".
CLASS_DENSITY_X100 = {
    "arctic_boreal_coast": 6,
    "boreal_forest": 212,
    "temperate_river_plain": 2615,
    "temperate_forest_hill": 1551,
    "mediterranean": 1629,
    "steppe": 457,
    "desert_river": 1158,
    "open_desert": 99,
    "highland_alpine": 531,
    "tropical_savanna": 581,
    "tropical_forest": 578,
}
#: Vanilla's world arable total (table 4.0 of the same note): the whole map sums to it before lore.
WORLD_ARABLE = 53_616
#: No state is emitted below this (vanilla's own minimum, table 4.0).
ARABLE_FLOOR = 2
#: Bump by hand whenever a rule (R1-R5, the class pick, the rounding) or :func:`subsistence` changes.
MODEL_VERSION = 1

#: ``frozen`` biome: boreal forest below this absolute latitude, arctic coast at or above it.
FROZEN_SPLIT_LAT = 60.0
#: Wind zone ``ET``: alpine tundra below this absolute latitude, arctic coast at or above it.
ALPINE_TUNDRA_LAT = 60.0
#: R2: a temperate biome under a steppe wind class is mediterranean below this absolute latitude.
DRY_TEMPERATE_LAT = 45.0

_SPLIT_FROZEN = "frozen"   # marker: resolved by latitude, see FROZEN_SPLIT_LAT
_SPLIT_ET = "ET"           # marker: resolved by latitude, see ALPINE_TUNDRA_LAT

#: Terrain biome class name (``generate_terrain_masks.BIOME_NAMES``) -> climate class.
#: ``frozen`` is split by latitude (:data:`FROZEN_SPLIT_LAT`).
BIOME_CLASS = {
    "temperate": "temperate_forest_hill",
    "magic_forest": "temperate_forest_hill",
    "hills": "temperate_forest_hill",
    "mountain": "highland_alpine",
    "wasteland": "steppe",
    "island": "mediterranean",
    "chaotic_waste": "arctic_boreal_coast",
    "jungle": "tropical_forest",
    "savannah": "tropical_savanna",
    "desert": "open_desert",
    "swamp": "boreal_forest",
    "frozen": _SPLIT_FROZEN,
}
#: Wind-layer zone code (``climate_zones_index.json``) -> climate class. The one authority for
#: the mapping. ``ET`` is split by latitude (:data:`ALPINE_TUNDRA_LAT`).
KOPPEN_CLASS = {
    "Af": "tropical_forest",
    "Am": "tropical_forest",
    "Aw": "tropical_savanna",
    "BWh": "open_desert",
    "BWk": "open_desert",
    "BSh": "steppe",
    "BSk": "steppe",
    "Cs": "mediterranean",
    "Cfa": "temperate_forest_hill",
    "Cfb": "temperate_forest_hill",
    "Df": "temperate_forest_hill",
    "Dc": "boreal_forest",
    "EF": "arctic_boreal_coast",
    "ET": _SPLIT_ET,
}
#: Biomes inside which the wind layer may refine the class (R1, R2).
TEMPERATE_FAMILY = ("temperate", "hills", "magic_forest", "island")
#: Wind classes R1 accepts inside the temperate family.
WIND_REFINES = ("temperate_forest_hill", "mediterranean", "boreal_forest")
#: The rules, in the order they are applied on top of ``BIOME_CLASS`` (their conditions are
#: disjoint, so at most one fires on a pixel). Index + 1 is the rule id :func:`classify` returns.
RULES = (
    "wind_refines_temperate",          # R1: temperate family, wind class in WIND_REFINES -> the wind class
    "dry_temperate_is_mediterranean",  # R2: temperate family, wind steppe, |lat| < 45 -> mediterranean
    "frozen_under_ice",                # R3: frozen, wind arctic -> arctic
    "polar_mountain",                  # R4: mountain, wind arctic -> arctic
    "desert_waste",                    # R5: wasteland, wind open desert -> open desert
)

_RANCH = "building_livestock_ranch"
#: Default ``arable_resources`` per class, in planner order (the first crop takes the remainder,
#: the last is dropped first when the workforce share runs out).
CLASS_CROPS = {
    # Comparable block (vanilla state files 00, 01, 02, 03, 08, 15): crops listed by more than
    # half of the class's states there. The dossier rows carry these classes.
    "arctic_boreal_coast": (_RANCH,),
    "open_desert": (_RANCH,),
    "boreal_forest": (_RANCH, "building_rye_farm"),
    "temperate_forest_hill": (_RANCH, "building_rye_farm"),
    "temperate_river_plain": (_RANCH, "building_wheat_farm", "building_vineyard"),
    "steppe": (_RANCH, "building_wheat_farm", "building_vineyard"),
    "highland_alpine": (_RANCH, "building_wheat_farm", "building_vineyard"),
    "mediterranean": ("building_vineyard", _RANCH, "building_wheat_farm", "building_cotton_plantation"),
    "desert_river": (_RANCH, "building_tobacco_plantation", "building_wheat_farm",
                     "building_cotton_plantation", "building_opium_plantation"),
    # World block (all vanilla states of the class, more than half): the two tropical classes have
    # no Old World rows to speak of (savanna 0, forest 2), so their land is the rowless far lands.
    "tropical_savanna": (_RANCH, "building_sugar_plantation", "building_cotton_plantation",
                         "building_banana_plantation", "building_tobacco_plantation",
                         "building_coffee_plantation"),
    "tropical_forest": ("building_banana_plantation", _RANCH, "building_coffee_plantation",
                        "building_sugar_plantation", "building_rice_farm", "building_tobacco_plantation",
                        "building_dye_plantation", "building_cotton_plantation", "building_tea_plantation"),
}

SUBSISTENCE_FARM = "building_subsistence_farm"
SUBSISTENCE_PASTURE = "building_subsistence_pasture"
SUBSISTENCE_FISHING_VILLAGE = "building_subsistence_fishing_village"


def subsistence(cls: str, coastal: bool) -> str:
    """The class's default subsistence building. ``coastal`` = the state emits a port hub."""
    if cls not in _CI:
        raise ValueError(f"unknown climate class {cls!r}")
    if cls == "open_desert":
        return SUBSISTENCE_PASTURE
    if cls == "arctic_boreal_coast":
        return SUBSISTENCE_FISHING_VILLAGE if coastal else SUBSISTENCE_PASTURE
    return SUBSISTENCE_FARM


# ---------------------------------------------------------------------------
# Class per pixel
# ---------------------------------------------------------------------------

def _biome_base(biome: str, abs_lat: float) -> str:
    b = BIOME_CLASS[biome]
    if b == _SPLIT_FROZEN:
        return "boreal_forest" if abs_lat < FROZEN_SPLIT_LAT else "arctic_boreal_coast"
    return b


def _wind_class(code: str, abs_lat: float) -> str:
    a = KOPPEN_CLASS[code]
    if a == _SPLIT_ET:
        return "highland_alpine" if abs_lat < ALPINE_TUNDRA_LAT else "arctic_boreal_coast"
    return a


def hybrid_class(biome: str, code: str, abs_lat: float) -> tuple[str, str | None]:
    """``(class, rule that fired or None)`` for one pixel: the scalar statement of the model.

    ``biome`` is a terrain biome name, ``code`` a wind zone code, ``abs_lat`` the absolute
    latitude in degrees. ``KeyError`` on a name or code the tables do not carry."""
    B = _biome_base(biome, abs_lat)
    A = _wind_class(code, abs_lat)
    if biome in TEMPERATE_FAMILY and A in WIND_REFINES:
        return A, RULES[0]
    if biome in TEMPERATE_FAMILY and A == "steppe" and abs_lat < DRY_TEMPERATE_LAT:
        return "mediterranean", RULES[1]
    if biome == "frozen" and A == "arctic_boreal_coast":
        return "arctic_boreal_coast", RULES[2]
    if biome == "mountain" and A == "arctic_boreal_coast":
        return "arctic_boreal_coast", RULES[3]
    if biome == "wasteland" and A == "open_desert":
        return "open_desert", RULES[4]
    return B, None


def classify(biome_ids: np.ndarray, wind_ids: np.ndarray, abs_lat: np.ndarray,
             biome_names: list[str], wind_codes: dict[int, str]) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized :func:`hybrid_class`: ``(class index int8, rule id int8)`` per element.

    ``biome_ids`` and ``wind_ids`` are uint8 arrays of one shape, ``abs_lat`` broadcasts against
    them. Class index is the position in :data:`CLASS_IDS`; rule id is 0 (none) or the 1-based
    position in :data:`RULES`. An element whose biome name is not in :data:`BIOME_CLASS` or whose
    wind id is not in ``wind_codes`` gets class -1; ``KeyError`` on a wind code that
    :data:`KOPPEN_CLASS` lacks."""
    def lut(pairs, table, low_marker, low, high):
        lo = np.full(256, -1, np.int8)
        hi = np.full(256, -1, np.int8)
        for i, name in pairs:
            if name not in table:
                continue
            v = table[name]
            lo[i] = _CI[low] if v == low_marker else _CI[v]
            hi[i] = _CI[high] if v == low_marker else _CI[v]
        return lo, hi

    for code in wind_codes.values():
        KOPPEN_CLASS[code]  # an unmapped zone code is a KeyError, never a silent -1
    b_lo, b_hi = lut(enumerate(biome_names), BIOME_CLASS, _SPLIT_FROZEN, "boreal_forest", "arctic_boreal_coast")
    a_lo, a_hi = lut(wind_codes.items(), KOPPEN_CLASS, _SPLIT_ET, "highland_alpine", "arctic_boreal_coast")
    abs_lat = np.asarray(abs_lat, dtype=np.float64)
    B = np.where(abs_lat < FROZEN_SPLIT_LAT, b_lo[biome_ids], b_hi[biome_ids])
    A = np.where(abs_lat < ALPINE_TUNDRA_LAT, a_lo[wind_ids], a_hi[wind_ids])

    def is_biome(*names: str) -> np.ndarray:
        flag = np.zeros(256, bool)
        for i, name in enumerate(biome_names):
            flag[i] = name in names
        return flag[biome_ids]

    fam = is_biome(*TEMPERATE_FAMILY)
    arctic = A == _CI["arctic_boreal_coast"]
    masks = (
        (fam & np.isin(A, [_CI[c] for c in WIND_REFINES]), A),
        (fam & (A == _CI["steppe"]) & (abs_lat < DRY_TEMPERATE_LAT), _CI["mediterranean"]),
        (is_biome("frozen") & arctic, _CI["arctic_boreal_coast"]),
        (is_biome("mountain") & arctic, _CI["arctic_boreal_coast"]),
        (is_biome("wasteland") & (A == _CI["open_desert"]), _CI["open_desert"]),
    )
    cls = B.astype(np.int8)
    rule = np.zeros(cls.shape, np.int8)
    for k, (m, value) in enumerate(masks, start=1):
        m = m & (rule == 0)
        cls = np.where(m, value, cls).astype(np.int8)
        rule = np.where(m, k, rule).astype(np.int8)
    bad = (B < 0) | (A < 0)
    cls[bad] = -1
    rule[bad] = 0
    return cls, rule


def class_pixels(region_px: np.ndarray, passable: np.ndarray, biome_grid: np.ndarray,
                 biome_names: list[str], wind: np.ndarray, wind_codes: dict[int, str],
                 lat_of_row: np.ndarray, n_regions: int, *, wind_sea: int = 255,
                 q: int = 4, block: int = 256) -> tuple[np.ndarray, np.ndarray]:
    """Pixel counts per region and class: ``(all_px, passable_px)``, two ``(n_regions + 1, 11)``
    int64 arrays (row 0 unused).

    ``region_px`` [H, W] is the land region of each pixel (0 = not land), ``passable`` [H, W]
    is false on impassable provinces, ``biome_grid`` [H // q, W // q] and ``wind`` [H, W] are the
    decoded rasters, ``lat_of_row`` [H] the latitude of each canvas row in degrees.

    ``SystemExit`` on a wrong grid or layer shape, an unknown biome name or wind code, or a
    land pixel the wind layer calls sea (the layer predates the coast)."""
    h, w = region_px.shape
    if passable.shape != (h, w):
        raise SystemExit(f"passable mask is {passable.shape}, province bitmap {(h, w)}")
    if h % q or w % q or biome_grid.shape != (h // q, w // q):
        raise SystemExit(f"biome grid is {biome_grid.shape[1]}x{biome_grid.shape[0]}, expected "
                         f"{w // q}x{h // q} (canvas {w}x{h} / {q}): run generate_terrain_masks.py --biome-grid")
    if wind.shape != (h, w):
        raise SystemExit(f"climate layer is {wind.shape[1]}x{wind.shape[0]}, expected {w}x{h}: "
                         f"regenerate generate_climate_zones.py")
    if len(lat_of_row) != h:
        raise SystemExit(f"lat_of_row has {len(lat_of_row)} rows, expected {h}")
    unknown_codes = sorted({c for c in wind_codes.values() if c not in KOPPEN_CLASS})
    if unknown_codes:
        raise SystemExit(f"climate layer: zone code(s) {unknown_codes} have no KOPPEN_CLASS entry")
    unknown_names = sorted({n for n in biome_names if n != "unknown" and n not in BIOME_CLASS})
    if unknown_names:
        raise SystemExit(f"biome grid: class name(s) {unknown_names} have no BIOME_CLASS entry")
    abs_lat = np.abs(np.asarray(lat_of_row, dtype=np.float64))
    n_cls = len(CLASS_IDS)
    all_px = np.zeros((n_regions + 1) * n_cls, np.int64)
    pass_px = np.zeros((n_regions + 1) * n_cls, np.int64)
    known_wind = np.zeros(256, bool)
    known_wind[list(wind_codes)] = True
    xcell = np.arange(w) // q
    for y0 in range(0, h, block):
        y1 = min(y0 + block, h)
        reg = region_px[y0:y1]
        land = reg > 0
        if not land.any():
            continue
        wnd = wind[y0:y1]
        n_sea = int((land & (wnd == wind_sea)).sum())
        if n_sea:
            ys, xs = np.nonzero(land & (wnd == wind_sea))
            raise SystemExit(f"climate layer: {n_sea}+ land pixel(s) are sea in the layer (first at "
                             f"x={int(xs[0])} y={int(ys[0]) + y0}); it predates the coast: "
                             f"regenerate generate_climate_zones.py")
        bad_wind = land & ~known_wind[wnd]
        if bad_wind.any():
            raise SystemExit(f"climate layer: land pixels carry class id(s) "
                             f"{sorted(set(wnd[bad_wind].tolist()))} that its index does not list")
        bio = biome_grid[(np.arange(y0, y1) // q)[:, None], xcell[None, :]]
        cls, _rule = classify(bio, wnd, abs_lat[y0:y1, None], biome_names, wind_codes)
        if (land & (cls < 0)).any():
            ids = sorted(set(bio[land & (cls < 0)].tolist()))
            raise SystemExit(f"biome grid: land pixels carry class id(s) {ids} "
                             f"({[biome_names[i] if i < len(biome_names) else '?' for i in ids]}) with no "
                             f"BIOME_CLASS entry: run generate_terrain_masks.py --biome-grid")
        key = reg[land].astype(np.int64) * n_cls + cls[land]
        all_px += np.bincount(key, minlength=all_px.size)
        ok = passable[y0:y1][land]
        pass_px += np.bincount(key[ok], minlength=pass_px.size)
    return all_px.reshape(n_regions + 1, n_cls), pass_px.reshape(n_regions + 1, n_cls)


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def apportion_exact(total: int, weights: list[int], order: list[int]) -> list[int]:
    """Integer shares of ``total`` proportional to the integer ``weights``: largest remainder,
    ties to the lower ``order`` key (the state number). Exact arithmetic; the sum is asserted."""
    if len(weights) != len(order):
        raise ValueError("weights and order differ in length")
    if any(w < 0 for w in weights):
        raise ValueError("negative weight")
    s = sum(weights)
    if total < 0 or (total and s <= 0):
        raise ValueError(f"cannot apportion {total} over a total weight of {s}")
    if not total:
        return [0] * len(weights)
    out = [total * w // s for w in weights]
    rem = [total * w % s for w in weights]
    left = total - sum(out)
    for i in sorted(range(len(weights)), key=lambda i: (-rem[i], order[i]))[:left]:
        out[i] += 1
    assert sum(out) == total, (sum(out), total)
    return out


def _density() -> list[int]:
    return [int(CLASS_DENSITY_X100[c]) for c in CLASS_IDS]


def state_class(all_row, passable_row) -> str:
    """The class carrying the largest ``passable pixels x density`` (ties to the earlier
    :data:`CLASS_IDS` entry); a state with no passable pixel is judged on all its pixels."""
    d = _density()
    px = [int(v) for v in passable_row]
    if not sum(px):
        px = [int(v) for v in all_row]
    weight = [p * dd for p, dd in zip(px, d)]
    return CLASS_IDS[max(range(len(CLASS_IDS)), key=lambda c: (weight[c], -c))]


def allocate(all_px: np.ndarray, passable_px: np.ndarray, state_number, swap: dict[int, str],
             factor: dict[int, Fraction], keep_confirmed_mix: bool = False,
             ) -> tuple[list[int], list[str | None], dict]:
    """``(arable, cls, stats)`` per region (index 0 unused: 0 and ``None``).

    ``all_px`` / ``passable_px`` are :func:`class_pixels`' arrays, ``state_number[r]`` breaks
    apportionment ties, ``swap[r]`` is a lore row's class for region ``r`` and ``factor[r]`` its
    multiplier (a ``Fraction``). A region with a swap or a factor is valued
    ``floor(WORLD_ARABLE x w / sum(w0) + 1/2)``; every other region keeps its apportioned
    climate-only value. Then :data:`ARABLE_FLOOR`.

    ``keep_confirmed_mix=True`` is the prototype's rule, kept for a comparison panel only: the
    swap applies only when the row's class differs from the class with the most pixels."""
    n = all_px.shape[0] - 1
    d = _density()
    for r, c in swap.items():
        if c not in _CI:
            raise ValueError(f"region {r}: unknown climate class {c!r}")
    px = [[int(v) for v in all_px[r]] for r in range(n + 1)]
    w0 = [sum(p * dd for p, dd in zip(px[r], d)) for r in range(n + 1)]
    w0[0] = 0
    s = sum(w0)
    order = [int(state_number[r]) for r in range(1, n + 1)]
    base = [0] + apportion_exact(WORLD_ARABLE, w0[1:], order)
    lore = list(base)
    n_swap = n_factor = 0
    for r in range(1, n + 1):
        c = swap.get(r)
        f = factor.get(r)
        swapped = c is not None
        if swapped and keep_confirmed_mix:
            swapped = max(range(len(CLASS_IDS)), key=lambda k: (px[r][k], -k)) != _CI[c]
        if not swapped and f is None:
            continue
        w = Fraction(sum(px[r]) * d[_CI[c]] if swapped else w0[r])
        if f is not None:
            w *= f
            n_factor += 1
        n_swap += int(swapped)
        lore[r] = int((Fraction(WORLD_ARABLE) * w / s + Fraction(1, 2)).__floor__())
    arable = [0] + [max(ARABLE_FLOOR, v) for v in lore[1:]]
    cls: list[str | None] = [None] + [
        swap[r] if r in swap else state_class(all_px[r], passable_px[r]) for r in range(1, n + 1)]
    stats = {
        "climate_only_total": sum(base),
        "lore_delta": sum(lore) - sum(base),
        "floor_lifted_states": sum(1 for r in range(1, n + 1) if arable[r] != lore[r]),
        "floor_added": sum(arable) - sum(lore),
        "final_total": sum(arable),
        "swaps": n_swap,
        "factors": n_factor,
        "climate_only": base,
    }
    return arable, cls, stats


# ---------------------------------------------------------------------------
# Identity: what the stamp records
# ---------------------------------------------------------------------------

def text_sha256(data: bytes) -> str:
    """SHA-256 of a text input with a BOM stripped and ``\\r\\n`` -> ``\\n``: ``core.autocrlf``
    checks committed LF files out as CRLF, and the hash must not move with it."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def array_sha256(a: np.ndarray) -> str:
    """SHA-256 of a decoded uint8 raster's bytes in row order (what was read, not the file)."""
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.uint8).tobytes()).hexdigest()


def model_sha256() -> str:
    """SHA-256 of a canonical JSON of every constant and :data:`MODEL_VERSION`."""
    payload = {
        "model_version": MODEL_VERSION,
        "class_ids": list(CLASS_IDS),
        "class_density_x100": {c: CLASS_DENSITY_X100[c] for c in CLASS_IDS},
        "world_arable": WORLD_ARABLE,
        "arable_floor": ARABLE_FLOOR,
        "frozen_split_lat": FROZEN_SPLIT_LAT,
        "alpine_tundra_lat": ALPINE_TUNDRA_LAT,
        "dry_temperate_lat": DRY_TEMPERATE_LAT,
        "biome_class": dict(sorted(BIOME_CLASS.items())),
        "koppen_class": dict(sorted(KOPPEN_CLASS.items())),
        "temperate_family": list(TEMPERATE_FAMILY),
        "wind_refines": list(WIND_REFINES),
        "rules": list(RULES),
        "class_crops": {c: list(CLASS_CROPS[c]) for c in CLASS_IDS},
        "subsistence": [SUBSISTENCE_FARM, SUBSISTENCE_PASTURE, SUBSISTENCE_FISHING_VILLAGE],
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
