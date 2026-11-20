#!/usr/bin/env python3
"""Trees, bushes, icebergs and their colour and wind maps from our own ground (board #11534).

Vanilla places its trees where they grow on the real Earth: 41 generator files under
``gfx/map/map_object_data/generated/`` (about 1.74 million trees, bushes and icebergs, 26% of
them in our sea) and two map-keyed textures, ``gfx/map/textures/colormap_tree.dds`` (the tree
tint, ``tree.shader`` overlays it on the mesh diffuse) and ``windmap_tree.dds`` (the sway
amplitude, ``.r`` only). This generator replaces all of them with a pure function of our own
close-zoom ground (#6617's committed material masks), our coastline, heightmap and latitude.
It needs no vanilla file and no editor at run time.

Inputs
    ``gfx/map/terrain/mask_<material>.png``   the 36 #6617 material masks (read by name; a missing
                                             one is a hard error naming ``generate_terrain_masks.py``)
    ``mapgen/derived/land_sea_mask.png``, ``lake_mask.png``   coast and lakes
    ``map_data/provinces.png``, ``map_data/state_regions/NN_<realm>.txt``, ``mapgen/config/in_scope_additions.json``
                                             the latitude-exempt ground (``LATITUDE_EXEMPT_REALMS``, Ulthuan): the realm's
                                             states painted through the province bitmap inside its box. ``--check`` goes
                                             stale when that state list or the province cut moves
    ``map_data/heightmap.png``                elevation, and slope from the elevation blurred by ``SLOPE_SMOOTH_PX``
                                             (``generate_terrain_masks.load_elevation``)
    ``mapgen/config/vegetation_objects.json`` the vanilla object schema (files, objects, meshes,
                                             vanilla counts, scale ranges), the only vanilla-derived
                                             input; written by ``--dump-vanilla-schema`` from the
                                             install (read-only), never hand-edited
Outputs (under ``--out``, default the repo root)
    ``gfx/map/map_object_data/generated/<file>.txt``   the 41 non-dynamic vanilla files, same names
    ``gfx/map/map_object_data/<object>.bin``           one transform table per non-empty object
    ``gfx/map/textures/colormap_tree.dds``             1024x512, DXT1, one level, 262,272 bytes
    ``gfx/map/textures/windmap_tree.dds``              1024x452, DXT1, 11 mips, 309,608 bytes
The 20 ``*_dynamic_*`` generator files belong to ``generate_dynamic_masks.py`` (#11536) and are never
touched. DDS bytes come only from ``worldgen/dds.py``; the object codec is ``worldgen/map_objects.py``.

Record and frame (decoded from vanilla): 40 bytes per instance, little-endian float32,
``x y z  qx qy qz qw  sx sy sz``. ``x`` is the canvas x, ``z`` is 3616 minus the canvas y (the locator
frame of ``generate_map_locators.py``), ``y`` is 0 (the engine puts objects on the terrain at load),
rotation is yaw only, scale is uniform. All objects are written as ``.bin``; an object that gets no
instance is written with neither ``transform_bin_file`` nor ``transform``, a valid empty object
(vanilla ships three), so a file whose objects are all empty still shadows vanilla's.

Rules
    1. Working grid: canvas / ``G`` (4096x1808). Per-cell class probabilities ``P`` come from the
       material masks by name (``CLASS_MATERIALS``); woodland, grass and savanna weights are
       ``Fw``, ``Gr``, ``Sv``. ``family_values`` turns them, with latitude and elevation, into one
       0..1 value per family (the rule table in that function), times land fraction, a treeline
       and a cliff factor (slope of the smoothed elevation, ``CLIFF_SLOPE``). Two pine rules add
       up: the boreal rule (temperate class x boreal weight, by latitude or elevation) and the
       taiga rule, which the terrain masks' class model cannot express (they have no taiga class,
       only frozen ground that is snow plus the permafrost pair): ``pine_dense += TAIGA_DENSE *
       tg * t_lat * t_low`` and ``pine_sparse += TAIGA_SPARSE * ...``, with ``tg`` the summed
       ``permafrost_01`` + ``permafrost_03`` weight, ``t_lat = 1 - smoothstep(|lat|, TAIGA_LAT)``
       (full to 62 N, gone by 68 N) and ``t_low = smoothstep(|lat|, TAIGA_MIN_LAT)`` (none on
       alpine permafrost south of 46-52 N). Snow, bare rock, cliffs and the treeline still stop it.
       Ulthuan (Chris 2026-11-20, a temperate magical island) is exempt from the latitude rules:
       no Mediterranean split and no latitude term of the boreal weight (its elevation term stays),
       in the rules and in the tint (``LATITUDE_EXEMPT_REALMS``).
    2. A tree gain and a bush gain (``calibrate``, bisection) bring the expected counts to
       ``TARGET_TREES_PER_LAND_PX`` and ``TARGET_BUSHES_PER_LAND_PX`` of our land.
    3. Each schema file gets a Poisson count per cell from its layer's tier (``TIER``: the layers
       are graphics-quality tiers and add up), positions uniform in the cell, kept only on land
       (icebergs: only on open sea), mesh by vanilla's per-object share, scale inside vanilla's
       observed range, uniform yaw.
    4. The tree tint blends one colour per class (broadleaf, boreal, Mediterranean, magic, jungle,
       savanna, dry, barren) and the wind map is greyscale by latitude over land (calm in the
       tropics, strong in the north); both carry seeded smooth noise.
    Every tuning knob below has a value that switches it off (noted beside it).

Deterministic: every RNG is ``numpy.random.default_rng([SEED, 11534, k])`` with ``SEED =
map_config.SEED``: ``k`` is the schema file's index for placement, 900 for the tint noise, 901 for
the wind noise. Output is a pure function of the inputs; byte-identical across runs.

Usage::

    python mapgen/generate_vegetation.py                        # write all outputs under the repo root
    python mapgen/generate_vegetation.py --out DIR --render     # write under DIR, previews to scratchpad/
    python mapgen/generate_vegetation.py --check                # regenerate in memory, compare with disk
    python mapgen/generate_vegetation.py --selftest             # synthetic 1/8-scale world, needs no files
    python mapgen/generate_vegetation.py --dump-vanilla-schema  # (dev) write config/vegetation_objects.json from the install
    python mapgen/generate_vegetation.py --check-schema         # (dev) re-derive it and diff; skips without the install

Run with ``mapgen/.venv/Scripts/python.exe`` (needs scipy). It runs after ``generate_terrain_masks.py``;
``--check`` goes stale whenever the masks, the coastline or the heightmap move. Every regeneration
rewrites about 80 MB of ``.bin`` (Git-LFS).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import dds, map_objects, raster  # noqa: E402
from worldgen.map_objects import ObjectEntry  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_DIR = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
LAND_PATH = DERIVED_DIR / "land_sea_mask.png"
LAKE_PATH = DERIVED_DIR / "lake_mask.png"
SCHEMA_PATH = TOOLS_DIR / "config" / "vegetation_objects.json"
SCOPE_ADDITIONS_PATH = TOOLS_DIR / "config" / "in_scope_additions.json"
STATE_REGIONS_DIR = REPO_DIR / "map_data" / "state_regions"
PROVINCES_PATH = REPO_DIR / "map_data" / "provinces.png"
DEFAULT_TERRAIN = REPO_DIR / "gfx" / "map" / "terrain"
SCRATCH_DIR = REPO_DIR / "scratchpad"          # gitignored previews; never mapgen/derived
GEN_REL = "gfx/map/map_object_data/generated"
TEX_REL = "gfx/map/textures"
VANILLA_GEN_REL = "gfx/map/map_object_data/generated"

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE   # 8192 x 3616

SEED = map_config.SEED
SEED_TAG = 11534                                  # the board item; second word of every RNG key
TINT_NOISE_KEY, WIND_NOISE_KEY = 900, 901

G = 2                                             # working grid = canvas / G (4096x1808)

#: layer -> (K trees per canvas px^2 at saturation, X mask value at which a tier saturates)
TIER = {"semidynamic": (0.077, 0.4), "semidynamic_medium": (0.250, 0.6), "semidynamic_high": (0.380, 0.8)}

TARGET_TREES_PER_LAND_PX = 0.1514
TARGET_BUSHES_PER_LAND_PX = 0.0286
BUSH_FAMILIES = frozenset({"bush_01", "bush_02", "bush_dry_02"})
ICEBERG_TARGET = 413
ICEBERG_FAMILY = "iceberg"

# --- tuning knobs (each has a value that switches its rule off, given beside it)
BOREAL_LAT = (54.0, 62.0)          # smoothstep of |lat| to boreal pine (off: (999, 1000))
BOREAL_ELEV_M = (900.0, 1500.0)    # smoothstep of elevation to boreal pine (off: (1e9, 1e9 + 1))
MED_LAT = (42.0, 47.0)             # |lat| below this is Mediterranean cypress (off: (-1, 0))
TREELINE_BASE_M = 3300.0           # treeline T(lat) = clip(BASE - SLOPE * max(|lat| - LAT0, 0), MIN, BASE) (off: BASE 1e9)
TREELINE_SLOPE_M = 45.0
TREELINE_LAT0 = 15.0
TREELINE_MIN_M = 900.0
TREELINE_FADE_M = 300.0
CLIFF_SLOPE = (18.0, 40.0)         # m of rise per canvas px; no trees on cliffs (off: (1e9, 1e9 + 1))
SLOPE_SMOOTH_PX = 8.0              # Gaussian blur (canvas px) of the elevation before the slope: the heightmap
                                   # carries ripple texture that a raw gradient reads as cliffs everywhere (0: raw)
PALM_COAST_PX = 24.0               # palms hug the coast, e-fold in canvas px (off: inf)
ICE_LAT = (58.0, 68.0)             # |lat| band where icebergs start (off: (999, 1000))
ICE_COAST_E = 50.0                 # iceberg e-fold distance from the coast, canvas px
ICE_MIN_COAST_PX = 3.0             # no iceberg closer to land than this
SCORE_FLOOR = 0.0                  # P = score / max(sum score, floor); 0 = plain share (the rule as specified)
# latitude exemption (Chris 2026-11-20): Ulthuan is a magical island made by the gods to be temperate across its
# whole extent, with no winter except in its mountains and the wasteland of Nagarythe, and it is excluded from
# geography-based climate projections. Inside the exempt ground the latitude rules do not apply: no Mediterranean
# split (``m`` = 0) and no latitude term of the boreal weight (``b`` keeps only its elevation term, so high
# ground may still carry pine); the tint takes BROADLEAF, not MED. What grows is whatever the ground masks say.
# Each entry is a realm key of ``config/in_scope_additions.json``: the land is that realm's state-region file
# (``NN_<file_stem>.txt``) restricted to the box of the addition of the same name, which is the ring island and
# the isles round it (the Shifting Isles); the realm's far-flung western islets lie outside the box and stay
# ordinary. The High Elf colonies belong to other realms and are not exempt. (off: ())
LATITUDE_EXEMPT_REALMS = ("ulthuan",)

# taiga (Chris 2026-11-20): pine on the cold northern ground that is not snow or bare rock. The terrain
# masks have no taiga class: their cold, non-ice ground is the permafrost pair (``TAIGA_MATERIALS``), painted
# by the frozen and chaotic-waste biomes. The rule is NOT multiplied by a class probability; it rides the
# material weight itself, times the same land, treeline and cliff factors as every family.
TAIGA_MATERIALS = ("permafrost_01", "permafrost_03")   # the taiga key: summed weight is ``tg``
TAIGA_LAT = (62.0, 68.0)           # taiga latitude factor = 1 - smoothstep(|lat|): full strength to 62, gone by 68 (off: (-2, -1))
TAIGA_MIN_LAT = (46.0, 52.0)       # taiga latitude floor = smoothstep(|lat|): no sea-level taiga on alpine permafrost far south;
                                   # mountain pine there is the boreal elevation rule's (off: (-2, -1))
TAIGA_DENSE = 0.6                  # pine_dense gain of the taiga rule (off: 0)
TAIGA_SPARSE = 0.3                 # pine_sparse gain of the taiga rule (off: 0; both 0 switches the rule off)

# --- class model: materials of #6617 by name
CLASSES = ("temperate", "magic", "jungle", "savanna", "dry", "frozen", "barren")
CLASS_MATERIALS = {
    "temperate": ["grasslands_01", "grasslands_02", "woodlands_01", "marchlands_01"],
    "magic": ["woodlands_02"],
    "jungle": ["marchlands_03", "grasslands_06"],      # plus max(woodlands_03 - woodlands_02, 0)
    "savanna": ["savanna_01", "savanna_03"],
    "dry": ["desert_01", "desert_03", "desert_04", "desert_05", "desert_06", "marchlands_02",
            "cliff_sandstone_03"],
    "frozen": ["snow", "permafrost_03"],
    "barren": ["cliff_sandstone_04", "cliff_sandstone_05", "rocks_01", "permafrost_01",
               "cliff_granite_01", "cliff_granite_02", "cliff_granite_06", "cliff_granite_07",
               "cliff_limestone_02", "cliff_limestone_03"],
}
WOOD = ("woodlands_01", "woodlands_02", "woodlands_03")
GRASS = ("grasslands_01", "grasslands_02", "grasslands_05")
SAVANNA_MATS = ("savanna_01", "savanna_03")
EXTRA_MASKS = ("grasslands_05", "woodlands_03")
REQUIRED_MASKS = sorted({m for ms in CLASS_MATERIALS.values() for m in ms} | set(EXTRA_MASKS)
                        | set(TAIGA_MATERIALS))
_KEEP_MASKS = frozenset(WOOD + GRASS + SAVANNA_MATS + ("marchlands_01", "marchlands_03", "grasslands_06"))

# --- tree tint colours (sRGB) and the wind map
BROADLEAF = (107, 111, 50)
BOREAL = (93, 95, 52)
MED = (119, 118, 46)
MAGIC = (88, 93, 50)               # no vanilla analogue: tuning
JUNGLE = (104, 108, 46)
SAVANNA = (121, 120, 49)
DRY = (124, 120, 46)
BARREN = (97, 97, 52)              # also frozen
SEA = (128, 131, 74)
LAND_FALLBACK = (107, 107, 51)     # vanilla land mean, where no class applies
TINT_W, TINT_H = 1024, 512
WIND_W, WIND_H = 1024, 452
TINT_NOISE_LEVELS, TINT_NOISE_SIGMA, TINT_BLUR_SIGMA = 5.0, 3.0, 1.5
WIND_BASE, WIND_LAT_GAIN, WIND_NOISE_LEVELS, WIND_NOISE_SIGMA = 85.0, 105.0, 12.0, 6.0
WIND_LAT_BAND = (20.0, 50.0)
TINT_BYTES, WIND_BYTES = 262_272, 309_608
#: vanilla's 128-byte headers, verbatim (flags, linear size, mip count, caps)
HEADER_TINT = bytes.fromhex(
    "444453207c0000000710080000020000000400000000040000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000004e5654540800020020000000"
    "04000000445854310000000000000000000000000000000000000000001000000000000000000000"
    "0000000000000000")
HEADER_WIND = bytes.fromhex(
    "444453207c00000007100a00c40100000004000000880300000000000b0000000000000000000000"
    "000000000000000000000000000000000000000000000000000000004e5654540800020020000000"
    "04000000445854310000000000000000000000000000000000000000081040000000000000000000"
    "0000000000000000")

PREVIEW_W, PREVIEW_H = 2048, 904
OLDWORLD_CROP = (3450, 134, 5200, 1860)            # canvas box of the 1:1 close-up
FAMILY_RGB = {
    "oak": (96, 170, 70), "oak_dense": (60, 140, 60), "pine_dense": (40, 100, 120),
    "pine_sparse": (90, 150, 170), "cypress_mediterranean_dense": (170, 150, 60),
    "cypress_mediterranean_sparse": (210, 190, 110), "cypress_dense": (150, 70, 190),
    "rainforest": (20, 120, 40), "rainforest_sparse": (110, 200, 90), "palm_dense": (230, 120, 40),
    "savanna_tree": (200, 170, 50), "baobab": (160, 100, 40), "bush_01": (140, 200, 120),
    "bush_02": (120, 220, 170), "bush_dry_02": (220, 200, 150), "iceberg": (240, 250, 255),
}
SEA_PREVIEW_RGB = (25, 35, 60)
COAST_PREVIEW_RGB = (210, 210, 210)

VANILLA_SCHEMA_COMMENT = (
    "Derived from the Victoria 3 1.15.1 install by generate_vegetation.py --dump-vanilla-schema "
    "(gfx/map/map_object_data/generated/*.txt without _dynamic_, plus the .bin they name); never "
    "hand-edited. --check-schema re-derives it and diffs; it skips cleanly without the install. "
    "scale_min and scale_max are the 0.5th and 99.5th percentile of an object's scale.")


def log(msg: str, t0: float | None = None) -> None:
    stamp = f" [{time.time() - t0:5.1f}s]" if t0 is not None else ""
    print(msg + stamp, flush=True)


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------

def smoothstep(x, lo: float, hi: float) -> np.ndarray:
    """0 below ``lo``, 1 above ``hi``, cubic between (float32)."""
    x = np.asarray(x, dtype=np.float32)
    t = np.clip((x - np.float32(lo)) / np.float32(hi - lo), 0.0, 1.0)
    return (t * t * (np.float32(3.0) - np.float32(2.0) * t)).astype(np.float32)


def area_resize(a: np.ndarray, w: int, h: int) -> np.ndarray:
    """Area (box) resample of a 2-D float array to ``w`` x ``h`` (float32)."""
    a = np.ascontiguousarray(a, dtype=np.float32)
    return np.asarray(Image.fromarray(a).resize((w, h), Image.BOX), dtype=np.float32)


def block_mean(a: np.ndarray, q: int) -> np.ndarray:
    h, w = a.shape
    return a.reshape(h // q, q, w // q, q).mean(axis=(1, 3), dtype=np.float32)


def block_max(a: np.ndarray, q: int) -> np.ndarray:
    h, w = a.shape
    return a.reshape(h // q, q, w // q, q).max(axis=(1, 3))


def unit_noise(key: int, shape: tuple[int, int], sigma: float) -> np.ndarray:
    """Smooth seeded noise with unit standard deviation."""
    rng = np.random.default_rng([SEED, SEED_TAG, key])
    n = ndimage.gaussian_filter(rng.standard_normal(shape).astype(np.float32), sigma, mode="nearest")
    return (n / max(float(n.std()), 1e-6)).astype(np.float32)


# ---------------------------------------------------------------------------
# Schema (the vanilla object table) and the dev-only dump of it
# ---------------------------------------------------------------------------

def vanilla_root() -> Path:
    from measure_vanilla_frame import VANILLA_ROOT   # lazy: pulls in skimage
    return VANILLA_ROOT


def family_of(stem: str) -> str:
    return re.sub(r"_generator_\d+$", "", stem)


def derive_schema(root: Path) -> list[dict]:
    """Rows for every non-dynamic vanilla generator file, sorted by name (read-only on ``root``)."""
    gen = root / VANILLA_GEN_REL
    files = sorted(p for p in gen.glob("*.txt") if "_dynamic_" not in p.name)
    rows = []
    for p in files:
        entries = map_objects.parse_object_file(p.read_text(encoding="utf-8"))
        layers = {e.layer for e in entries}
        if len(layers) != 1:
            raise SystemExit(f"{p.name}: objects on several layers {sorted(layers)}")
        objs = []
        for e in entries:
            a = map_objects.instances(e, root)
            if len(a):
                s = a[:, 7].astype(np.float64)
                lo, hi = (round(float(v), 3) for v in np.percentile(s, [0.5, 99.5]))
            else:
                lo = hi = 0
            objs.append({"name": e.name, "pdxmesh": e.pdxmesh, "clamp_to_water_level": e.clamp_to_water_level,
                         "render_under_water": e.render_under_water, "vanilla_count": int(len(a)),
                         "scale_min": lo, "scale_max": hi})
        rows.append({"file": p.name, "family": family_of(p.stem), "layer": layers.pop(), "objects": objs})
    return rows


def schema_text(rows: list[dict]) -> str:
    out = ["{", f'  "_comment": {json.dumps(VANILLA_SCHEMA_COMMENT)},', '  "rows": [']
    for i, r in enumerate(rows):
        out.append("    {" + f'"file": {json.dumps(r["file"])}, "family": {json.dumps(r["family"])}, '
                   f'"layer": {json.dumps(r["layer"])}, "objects": [')
        for j, o in enumerate(r["objects"]):
            out.append("      " + json.dumps(o) + ("," if j + 1 < len(r["objects"]) else ""))
        out.append("    ]}" + ("," if i + 1 < len(rows) else ""))
    out += ["  ]", "}", ""]
    return "\n".join(out)


def load_schema(path: Path = SCHEMA_PATH) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"{path}: missing; run: python mapgen/generate_vegetation.py --dump-vanilla-schema")
    rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
    for r in rows:
        if r["layer"] not in TIER:
            raise SystemExit(f"{r['file']}: layer {r['layer']!r} has no tier in TIER")
    return rows


def dump_vanilla_schema() -> int:
    root = vanilla_root()
    if not (root / VANILLA_GEN_REL).is_dir():
        raise SystemExit(f"vanilla install not found at {root}")
    rows = derive_schema(root)
    SCHEMA_PATH.write_text(schema_text(rows), encoding="utf-8", newline="\n")
    n_obj = sum(len(r["objects"]) for r in rows)
    total = sum(o["vanilla_count"] for r in rows for o in r["objects"])
    log(f"wrote {SCHEMA_PATH.relative_to(REPO_DIR).as_posix()}: {len(rows)} files, {n_obj} objects, "
        f"{total:,} vanilla instances")
    return 0


def check_schema() -> int:
    root = vanilla_root()
    if not (root / VANILLA_GEN_REL).is_dir():
        log("check-schema: skipped, the vanilla install is not on this machine")
        return 0
    want = schema_text(derive_schema(root))
    have = SCHEMA_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") if SCHEMA_PATH.exists() else ""
    if want != have:
        log(f"check-schema: {SCHEMA_PATH.relative_to(REPO_DIR).as_posix()} differs from the install; "
            "re-run --dump-vanilla-schema")
        return 1
    log(f"check-schema: current ({len(json.loads(have)['rows'])} files)")
    return 0


# ---------------------------------------------------------------------------
# Fields: everything the rules read, on the working grid
# ---------------------------------------------------------------------------

@dataclass
class Fields:
    canvas_w: int
    canvas_h: int
    grid: int
    L: np.ndarray                  # land & ~lake fraction per working cell
    Fw: np.ndarray                 # woodland weight
    Gr: np.ndarray                 # grass weight
    Sv: np.ndarray                 # savanna weight
    Tg: np.ndarray                 # taiga key weight (permafrost pair, ``TAIGA_MATERIALS``)
    Ul: np.ndarray                 # latitude-exempt fraction per working cell (``LATITUDE_EXEMPT_REALMS``)
    P: dict[str, np.ndarray]       # soft class probabilities
    lat: np.ndarray                # (h, 1) degrees at working row centres
    lat_rows: np.ndarray           # (canvas_h,) degrees at canvas row centres
    elev: np.ndarray               # mean metres per cell
    slope: np.ndarray              # mean metres of rise per canvas px over the cell (smoothed elevation)
    coast_px: np.ndarray           # canvas px from a cell to the nearest land (0 on land)
    land_px: np.ndarray            # canvas px from a land cell to the nearest non-land (0 elsewhere)
    sea_cell: np.ndarray           # bool: open sea (not lake) at cell level
    land_full: np.ndarray          # bool canvas: land & ~lake, the exact land test
    sea_full: np.ndarray           # bool canvas: sea & ~lake, the exact iceberg test
    exempt_full: np.ndarray | None = None   # bool canvas: latitude-exempt land (None: none)
    shape: tuple[int, int] = field(init=False)

    def __post_init__(self) -> None:
        self.shape = self.L.shape


class _Masks:
    """Mask provider with a small cache for the masks the rules read more than once."""

    def __init__(self, read) -> None:
        self._read = read
        self._cache: dict[str, np.ndarray] = {}

    def __call__(self, name: str) -> np.ndarray:
        if name in self._cache:
            return self._cache[name]
        a = self._read(name)
        if name in _KEEP_MASKS:
            self._cache[name] = a
        return a


def fields_from_arrays(land_raw: np.ndarray, lake: np.ndarray, elev_full: np.ndarray, masks,
                       lat_rows: np.ndarray, grid: int = G, exempt: np.ndarray | None = None) -> Fields:
    """Pure function of canvas-resolution land, lake, elevation and latitude-exempt masks and working-grid masks."""
    ch, cw = land_raw.shape
    h, w = ch // grid, cw // grid
    get = masks if isinstance(masks, _Masks) else _Masks(masks if callable(masks) else masks.__getitem__)
    land_full = land_raw & ~lake
    sea_full = ~land_raw & ~lake
    L = block_mean(land_full.astype(np.float32), grid)
    sea_cell = block_mean(sea_full.astype(np.float32), grid) >= 0.5

    Fw = np.clip(sum(get(n) for n in WOOD), 0.0, 1.0).astype(np.float32)
    Gr = np.clip(sum(get(n) for n in GRASS), 0.0, 1.0).astype(np.float32)
    Sv = np.clip(sum(get(n) for n in SAVANNA_MATS), 0.0, 1.0).astype(np.float32)
    Tg = np.clip(sum(get(n) for n in TAIGA_MATERIALS), 0.0, 1.0).astype(np.float32)
    Ul = (block_mean(exempt.astype(np.float32), grid) if exempt is not None and exempt.any()
          else np.zeros((h, w), np.float32))

    scores: dict[str, np.ndarray] = {}
    for c in CLASSES:
        s = np.zeros((h, w), np.float32)
        for n in CLASS_MATERIALS[c]:
            s += get(n)
        if c == "jungle":
            s += np.maximum(get("woodlands_03") - get("woodlands_02"), 0.0)
        scores[c] = s
    total = sum(scores.values())
    denom = np.maximum(total, np.float32(SCORE_FLOOR))
    P = {c: np.divide(scores[c], denom, out=np.zeros_like(scores[c]), where=denom > 0).astype(np.float32)
         for c in CLASSES}
    del scores, total, denom

    elev = block_mean(elev_full, grid)
    gy, gx = np.gradient(ndimage.gaussian_filter(elev_full, SLOPE_SMOOTH_PX, mode="nearest"))
    slope = block_mean(np.hypot(gx, gy).astype(np.float32), grid)
    del gx, gy

    from worldgen import reproject
    lat = reproject.canvas_lonlat(np.arange(h) * grid + (grid - 1) / 2.0, cw, ch)[1].astype(np.float32)
    lat = lat.reshape(h, 1)

    lbin = L >= 0.5
    land_px = (ndimage.distance_transform_edt(lbin) * grid).astype(np.float32)
    coast_px = (ndimage.distance_transform_edt(~lbin) * grid).astype(np.float32)
    return Fields(cw, ch, grid, L, Fw, Gr, Sv, Tg, Ul, P, lat, np.asarray(lat_rows, np.float32), elev, slope,
                  coast_px, land_px, sea_cell, land_full, sea_full,
                  exempt_full=(exempt & land_full) if exempt is not None else None)


def read_mask_channel(terrain_dir: Path, name: str, grid: int = G) -> np.ndarray:
    """One 8-bit material mask reduced to the working grid, 0..1 float32."""
    p = Path(terrain_dir) / f"mask_{name}.png"
    if not p.exists():
        raise SystemExit(f"{p}: missing; run: python mapgen/generate_terrain_masks.py "
                         f"(or --from-masks on a clean clone)")
    with Image.open(p) as im:
        a = np.asarray(im)
    if a.ndim != 2 or a.dtype != np.uint8 or a.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{p}: expected an 8-bit {CANVAS_W}x{CANVAS_H} greyscale PNG, got {a.dtype} {a.shape}")
    return (block_mean(a.astype(np.float32), grid) / 255.0).astype(np.float32)


def latitude_exempt_mask(realms: tuple[str, ...] | None = None) -> np.ndarray:
    """Canvas bool mask of the latitude-exempt ground (``LATITUDE_EXEMPT_REALMS``), committed data only.

    For each realm key: the provinces of the land states in its ``NN_<file_stem>.txt`` state-region file,
    painted through ``map_data/provinces.png`` (alpha-aware reader), kept inside the box of the
    ``in_scope_additions.json`` addition of the same name. A realm with no state file or no box row is an error.
    """
    from worldgen import scope_additions, state_ownership
    realms = LATITUDE_EXEMPT_REALMS if realms is None else realms
    mask = np.zeros((CANVAS_H, CANVAS_W), bool)
    if not realms:
        return mask
    cfg = scope_additions.load(SCOPE_ADDITIONS_PATH, (CANVAS_W, CANVAS_H))
    prov = None
    for key in realms:
        if key not in cfg.realms:
            raise SystemExit(f"latitude-exempt realm {key!r} is not declared in {SCOPE_ADDITIONS_PATH.name}")
        stem = cfg.realms[key].file_stem
        files = sorted(STATE_REGIONS_DIR.glob(f"[0-9][0-9]_{stem}.txt"))
        boxes = [a.box for a in cfg.additions if a.name == key and a.box is not None]
        if len(files) != 1 or len(boxes) != 1:
            raise SystemExit(f"latitude-exempt realm {key!r}: need exactly one state file *_{stem}.txt "
                             f"({len(files)} found) and one box addition named {key!r} ({len(boxes)} found)")
        tokens = sorted({int(t[1:], 16) for st in state_ownership.parse_state_text(files[0].read_text(encoding="utf-8-sig"))
                         for t in st.provinces})
        if prov is None:
            prov = raster.read_rgb_png(PROVINCES_PATH)
            if prov.shape[:2] != (CANVAS_H, CANVAS_W):
                raise SystemExit(f"{PROVINCES_PATH.name}: expected {CANVAS_W}x{CANVAS_H}, got {prov.shape[1]}x{prov.shape[0]}")
        x0, y0, x1, y1 = boxes[0]
        blk = prov[y0:y1, x0:x1].astype(np.uint32)
        packed = (blk[..., 0] << 16) | (blk[..., 1] << 8) | blk[..., 2]
        mask[y0:y1, x0:x1] |= np.isin(packed, np.array(tokens, np.uint32))
    return mask


def load_fields(terrain_dir: Path = DEFAULT_TERRAIN) -> Fields:
    """Read the real inputs. ``generate_terrain_masks`` is imported here, not at module level."""
    import generate_terrain_masks as gtm
    from worldgen import reproject
    t0 = time.time()
    land_raw = raster.read_mask_png(LAND_PATH)
    lake = raster.read_mask_png(LAKE_PATH)
    for nm, a in (("land_sea_mask.png", land_raw), ("lake_mask.png", lake)):
        if a.shape != (CANVAS_H, CANVAS_W):
            raise SystemExit(f"{nm}: expected {CANVAS_W}x{CANVAS_H}, got {a.shape[1]}x{a.shape[0]}")
    for name in REQUIRED_MASKS:       # fail on a missing mask before the slow steps
        if not (Path(terrain_dir) / f"mask_{name}.png").exists():
            raise SystemExit(f"{Path(terrain_dir) / f'mask_{name}.png'}: missing; run: "
                             "python mapgen/generate_terrain_masks.py")
    elev = gtm.load_elevation()
    lat_rows = reproject.canvas_lonlat(np.arange(CANVAS_H), CANVAS_W, CANVAS_H)[1][:, 0]
    exempt = latitude_exempt_mask() & land_raw & ~lake
    log(f"inputs read: land {100 * (land_raw & ~lake).mean():.2f}%; latitude-exempt land "
        f"{int(exempt.sum()):,} px ({', '.join(LATITUDE_EXEMPT_REALMS) or 'none'})", t0)
    return fields_from_arrays(land_raw, lake, elev, _Masks(lambda n: read_mask_channel(terrain_dir, n)),
                              lat_rows, exempt=exempt)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def climate_blend(f: Fields) -> tuple[np.ndarray, np.ndarray]:
    """``b``: boreal weight (latitude or elevation); ``m``: Mediterranean weight (southern Old World).

    On latitude-exempt ground (``f.Ul`` = 1, ``LATITUDE_EXEMPT_REALMS``) the latitude term of ``b`` and ``m`` are 0.
    """
    alat = np.abs(f.lat)
    keep = np.float32(1.0) - f.Ul
    b = np.maximum(smoothstep(alat, *BOREAL_LAT) * keep, smoothstep(f.elev, *BOREAL_ELEV_M))
    m = (np.float32(1.0) - smoothstep(alat, *MED_LAT)) * keep
    return b.astype(np.float32), m.astype(np.float32)


def treeline_factor(f: Fields) -> np.ndarray:
    alat = np.abs(f.lat)
    t = np.clip(TREELINE_BASE_M - TREELINE_SLOPE_M * np.maximum(alat - TREELINE_LAT0, 0.0),
                TREELINE_MIN_M, TREELINE_BASE_M).astype(np.float32)
    return np.float32(1.0) - _ss_elev(f.elev, t - TREELINE_FADE_M, t)


def _ss_elev(x: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Smoothstep with array edges (the treeline varies by row)."""
    t = np.clip((x - lo) / np.maximum(hi - lo, np.float32(1e-6)), 0.0, 1.0).astype(np.float32)
    return t * t * (np.float32(3.0) - np.float32(2.0) * t)


RULE_FAMILIES = ("oak_dense", "oak", "pine_dense", "pine_sparse", "cypress_mediterranean_dense",
                 "cypress_mediterranean_sparse", "cypress_dense", "rainforest", "rainforest_sparse",
                 "palm_dense", "savanna_tree", "baobab", "bush_dry_02", "bush_02", "bush_01")


def taiga_factor(f: Fields) -> np.ndarray:
    """``tg * t_lat * t_low``: taiga-key weight times the latitude window (no class probability)."""
    alat = np.abs(f.lat)
    t_lat = np.float32(1.0) - smoothstep(alat, *TAIGA_LAT)
    t_low = smoothstep(alat, *TAIGA_MIN_LAT)
    return (f.Tg * t_lat * t_low).astype(np.float32)


def base_factor(f: Fields) -> np.ndarray:
    """``L * A * C``: land fraction, treeline, cliff; the factor every family is multiplied by."""
    A = treeline_factor(f)
    C = np.float32(1.0) - smoothstep(f.slope, *CLIFF_SLOPE)
    return (f.L * A * C).astype(np.float32)


def pine_parts(f: Fields) -> dict[str, np.ndarray]:
    """The pine families split by rule, each already times ``L * A * C`` (their sum is ``family_values``)."""
    b, _m = climate_blend(f)
    base = base_factor(f)
    Pt = f.P["temperate"]
    tgf = taiga_factor(f)
    return {
        "boreal_dense": np.clip(Pt * b * f.Fw * base, 0.0, None).astype(np.float32),
        "boreal_sparse": np.clip(Pt * b * 0.25 * f.Gr * base, 0.0, None).astype(np.float32),
        "taiga_dense": np.clip(TAIGA_DENSE * tgf * base, 0.0, None).astype(np.float32),
        "taiga_sparse": np.clip(TAIGA_SPARSE * tgf * base, 0.0, None).astype(np.float32),
    }


def family_values(f: Fields) -> dict[str, np.ndarray]:
    """One 0..1 value per family on the working grid: the rule table times ``L * A * C``.

    Frozen and barren ground carries no trees, except the taiga rule below. ``b`` is the
    boreal weight, ``m`` the Mediterranean one, ``A`` the treeline factor, ``C`` the cliff
    factor. Taiga: ``pine_dense += TAIGA_DENSE * tg * t_lat * t_low`` and ``pine_sparse +=
    TAIGA_SPARSE * ...`` (``tg`` the permafrost weight, ``t_lat`` and ``t_low`` the latitude
    window, :func:`taiga_factor`), times the same ``L * A * C``.
    """
    b, m = climate_blend(f)
    base = base_factor(f)
    Pt, Pm, Pj, Ps, Pd = (f.P[k] for k in ("temperate", "magic", "jungle", "savanna", "dry"))
    Fw, Gr, Sv = f.Fw, f.Gr, f.Sv
    tb = Pt * (1 - b) * (1 - m)
    tgf = taiga_factor(f)
    palm_coast = np.exp(-f.land_px / np.float32(PALM_COAST_PX)).astype(np.float32)
    raw = {
        "oak_dense": tb * 0.6 * Fw + Pm * 0.7 * Fw,
        "oak": tb * (0.4 * Fw + 0.15 * Gr),
        "pine_dense": Pt * b * Fw + TAIGA_DENSE * tgf,
        "pine_sparse": Pt * b * 0.25 * Gr + TAIGA_SPARSE * tgf,
        "cypress_mediterranean_dense": Pt * (1 - b) * m * 0.7 * Fw,
        "cypress_mediterranean_sparse": Pt * (1 - b) * m * 0.15 * Gr,
        "cypress_dense": Pm * 0.5 * Fw,
        "rainforest": Pj * Fw,
        "rainforest_sparse": Pj * 0.35 * (1 - Fw),
        "palm_dense": Pj * 0.6 * Fw * palm_coast,
        "savanna_tree": Ps * 0.35 * Sv,
        "baobab": Ps * 0.2 * Sv,
        "bush_dry_02": Ps * 0.3 * Sv + Pd * 0.06,
        "bush_02": Pj * 0.1 + Ps * 0.15,
        "bush_01": Pt * (0.3 * Gr + 0.15 * Fw),
    }
    return {k: np.clip(v * base, 0.0, None).astype(np.float32) for k, v in raw.items()}


def unruled_families(schema: list[dict]) -> list[str]:
    return sorted({r["family"] for r in schema} - set(RULE_FAMILIES) - {ICEBERG_FAMILY})


def _is_bush(family: str) -> bool:
    return family in BUSH_FAMILIES


def expected_total(values: dict[str, np.ndarray], schema: list[dict], g_tree: float, g_bush: float,
                   cell_area: int, bush: bool | None = None) -> float:
    """Expected instance count of the schema files (``bush``: only bushes / only trees / None = both)."""
    total = 0.0
    for r in schema:
        fam = r["family"]
        if fam == ICEBERG_FAMILY or (bush is not None and _is_bush(fam) != bush):
            continue
        v = values.get(fam)
        if v is None:
            continue
        gain = g_bush if _is_bush(fam) else g_tree
        k, x = TIER[r["layer"]]
        total += cell_area * k * float(np.minimum(np.clip(gain * v, 0.0, 1.0) / x, 1.0).sum(dtype=np.float64))
    return total


def calibrate(values: dict[str, np.ndarray], schema: list[dict], f: Fields) -> tuple[float, float]:
    """Tree and bush gains by bisection (30 steps over [0, 50]) to the per-land-pixel targets.

    ``min(clip(g v, 0, 1) / X, 1) = min(g v / X, 1)`` for ``X <= 1``, so each family's expected count is
    evaluated exactly from its sorted nonzero values and their prefix sums.
    """
    land_px = int(f.land_full.sum())
    cell_area = f.grid * f.grid
    stats: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for fam, v in values.items():
        nz = np.sort(v[v > 0]).astype(np.float64)
        stats[fam] = (nz, np.concatenate([[0.0], np.cumsum(nz)]))

    def expect(gain: float, bush: bool) -> float:
        tot = 0.0
        for r in schema:
            fam = r["family"]
            if fam == ICEBERG_FAMILY or _is_bush(fam) != bush or fam not in stats:
                continue
            k, x = TIER[r["layer"]]
            nz, cs = stats[fam]
            idx = int(np.searchsorted(nz, x / gain, side="left")) if gain > 0 else len(nz)
            tot += cell_area * k * ((len(nz) - idx) + (gain / x) * cs[idx])
        return tot

    gains = []
    for bush, target in ((False, TARGET_TREES_PER_LAND_PX), (True, TARGET_BUSHES_PER_LAND_PX)):
        want = target * land_px
        lo, hi = 0.0, 50.0
        if expect(hi, bush) < want:
            log(f"warning: {'bush' if bush else 'tree'} target {want:,.0f} unreachable "
                f"(max {expect(hi, bush):,.0f}); gain left at {hi}")
        else:
            for _ in range(30):
                mid = 0.5 * (lo + hi)
                if expect(mid, bush) < want:
                    lo = mid
                else:
                    hi = mid
        gains.append(hi)
    return gains[0], gains[1]


def record_pixels(x32: np.ndarray, z32: np.ndarray, canvas_h: int, canvas_w: int) -> tuple[np.ndarray, np.ndarray]:
    """Canvas pixel ``(ix, iy)`` of float32 record positions, exactly as ``--check`` reads them."""
    ix = np.floor(x32.astype(np.float64)).astype(np.int64)
    iy = np.floor(canvas_h - z32.astype(np.float64)).astype(np.int64)
    return np.clip(ix, 0, canvas_w - 1), np.clip(iy, 0, canvas_h - 1)


def file_lambda(row: dict, values: dict[str, np.ndarray], gains: tuple[float, float], f: Fields):
    """Expected instances per cell of one schema file and the clipped value ``v`` (None = no instances)."""
    fam = row["family"]
    cell_area = f.grid * f.grid
    if fam == ICEBERG_FAMILY:
        w = smoothstep(np.abs(f.lat), *ICE_LAT) * np.exp(-f.coast_px / np.float32(ICE_COAST_E))
        w = np.where(f.sea_cell & (f.coast_px >= ICE_MIN_COAST_PX), w, 0.0).astype(np.float64)
        s = float(w.sum())
        return (w / s * ICEBERG_TARGET, None) if s > 0 else (None, None)
    val = values.get(fam)
    if val is None:
        return None, None
    gain = gains[1] if _is_bush(fam) else gains[0]
    v = np.clip(gain * val, 0.0, 1.0)
    k, x = TIER[row["layer"]]
    return cell_area * k * np.minimum(v / x, 1.0), v


def place(values: dict[str, np.ndarray], gains: tuple[float, float], schema: list[dict],
          f: Fields) -> dict[str, np.ndarray]:
    """Instances per object name, ``(N, 10)`` float32 (empty tables for objects that get none)."""
    h, w = f.shape
    n_ice = max(1, sum(1 for r in schema if r["family"] == ICEBERG_FAMILY))
    arrays: dict[str, np.ndarray] = {}
    empty = np.zeros((0, map_objects.RECORD_FLOATS), np.float32)
    for i, row in enumerate(schema):
        objs = row["objects"]
        for o in objs:
            arrays[o["name"]] = empty
        rng = np.random.default_rng([SEED, SEED_TAG, i])
        lam, v = file_lambda(row, values, gains, f)
        if lam is None or not np.any(lam > 0):
            continue
        ice = row["family"] == ICEBERG_FAMILY
        if ice:
            lam = lam / n_ice
        n = rng.poisson(lam.astype(np.float64))
        cells = np.repeat(np.arange(n.size), n.ravel())
        m = cells.size
        if m == 0:
            continue
        ux, uy, umesh, uscale, uyaw = (rng.random(m) for _ in range(5))
        j, ii = np.divmod(cells, w)
        x = np.clip(f.grid * ii + f.grid * ux, 0.0, f.canvas_w - 1e-3)
        yc = np.clip(f.grid * j + f.grid * uy, 0.0, f.canvas_h - 1e-3)
        x32 = x.astype(np.float32)
        z32 = (f.canvas_h - yc).astype(np.float32)
        ix, iy = record_pixels(x32, z32, f.canvas_h, f.canvas_w)
        keep = (f.sea_full if ice else f.land_full)[iy, ix]
        counts = np.array([o["vanilla_count"] for o in objs], dtype=np.float64)
        if counts.sum() <= 0:
            log(f"warning: {row['file']}: every vanilla object is empty; equal mesh shares used")
            counts = np.ones(len(objs))
        cum = np.cumsum(counts / counts.sum())
        cum[-1] = 1.0
        mi = np.minimum(np.searchsorted(cum, umesh, side="right"), len(objs) - 1)
        smin = np.array([o["scale_min"] for o in objs], dtype=np.float64)[mi]
        smax = np.array([o["scale_max"] for o in objs], dtype=np.float64)[mi]
        if ice:
            s = np.ones(m)
        else:
            vc = v.ravel()[cells]
            s = smin + (smax - smin) * (0.5 * vc + 0.5 * uscale)
        theta = 2.0 * np.pi * uyaw
        rec = np.zeros((m, map_objects.RECORD_FLOATS), np.float32)
        rec[:, 0] = x32
        rec[:, 2] = z32
        rec[:, 4] = np.sin(theta / 2.0)
        rec[:, 6] = np.cos(theta / 2.0)
        rec[:, 7:10] = s.astype(np.float32)[:, None]
        for k, o in enumerate(objs):
            arrays[o["name"]] = rec[keep & (mi == k)]
    return arrays


# ---------------------------------------------------------------------------
# Textures
# ---------------------------------------------------------------------------

def tint_texture(f: Fields) -> np.ndarray:
    """Tree tint, float32 ``(512, 1024, 3)``, row 0 north."""
    w, h = TINT_W, TINT_H
    Pr = {c: area_resize(f.P[c], w, h) for c in CLASSES}
    b, m = climate_blend(f)
    br, mr = area_resize(b, w, h), area_resize(m, w, h)
    Lt = np.clip(area_resize(f.L, w, h), 0.0, 1.0)
    temperate = (((1 - br) * (1 - mr))[..., None] * np.array(BROADLEAF, np.float32)
                 + br[..., None] * np.array(BOREAL, np.float32)
                 + ((1 - br) * mr)[..., None] * np.array(MED, np.float32))
    colours = {"magic": MAGIC, "jungle": JUNGLE, "savanna": SAVANNA, "dry": DRY, "frozen": BARREN,
               "barren": BARREN}
    num = Pr["temperate"][..., None] * temperate
    for c, rgb in colours.items():
        num = num + Pr[c][..., None] * np.array(rgb, np.float32)
    psum = sum(Pr.values())[..., None]
    land = np.where(psum > 1e-6, num / np.maximum(psum, 1e-6), np.array(LAND_FALLBACK, np.float32))
    col = Lt[..., None] * land + (1 - Lt[..., None]) * np.array(SEA, np.float32)
    col = np.stack([ndimage.gaussian_filter(col[..., c], TINT_BLUR_SIGMA, mode="nearest") for c in range(3)], axis=-1)
    noise = unit_noise(TINT_NOISE_KEY, (h, w), TINT_NOISE_SIGMA)
    col[..., 0] += TINT_NOISE_LEVELS * noise * Lt
    col[..., 1] += TINT_NOISE_LEVELS * noise * Lt
    return np.clip(col, 0, 255).astype(np.float32)


def wind_texture(f: Fields) -> np.ndarray:
    """Tree sway amplitude, float32 ``(452, 1024, 3)`` grey, row 0 north."""
    from worldgen import reproject
    w, h = WIND_W, WIND_H
    Lw = np.clip(area_resize(f.L, w, h), 0.0, 1.0)
    lat = reproject.canvas_lonlat(np.arange(h), w, h)[1].astype(np.float32)        # (h, 1)
    base = WIND_BASE + WIND_LAT_GAIN * smoothstep(np.abs(lat), *WIND_LAT_BAND)
    noise = unit_noise(WIND_NOISE_KEY, (h, w), WIND_NOISE_SIGMA)
    out = np.clip(Lw * base + Lw * WIND_NOISE_LEVELS * noise, 0, 255)
    return np.repeat(out[..., None], 3, axis=2).astype(np.float32)


def build_textures(f: Fields) -> tuple[bytes, bytes, np.ndarray, np.ndarray]:
    tint, wind = tint_texture(f), wind_texture(f)
    tint_dds = dds.build_bc(tint, fourcc="DXT1", mips=1)
    wind_dds = dds.build_bc(wind, fourcc="DXT1", mips=11)
    if len(tint_dds) != TINT_BYTES or tint_dds[:128] != HEADER_TINT:
        raise SystemExit(f"colormap_tree.dds: {len(tint_dds)} bytes or header differs from vanilla's")
    if len(wind_dds) != WIND_BYTES or wind_dds[:128] != HEADER_WIND:
        raise SystemExit(f"windmap_tree.dds: {len(wind_dds)} bytes or header differs from vanilla's")
    return tint_dds, wind_dds, tint, wind


# ---------------------------------------------------------------------------
# Generate, write, check
# ---------------------------------------------------------------------------

@dataclass
class Result:
    fields: Fields
    schema: list[dict]
    values: dict[str, np.ndarray]
    gains: tuple[float, float]
    arrays: dict[str, np.ndarray]
    entries: dict[str, list[ObjectEntry]]
    tint_dds: bytes
    wind_dds: bytes
    tint: np.ndarray
    wind: np.ndarray


def build_entries(schema: list[dict], arrays: dict[str, np.ndarray]) -> dict[str, list[ObjectEntry]]:
    out: dict[str, list[ObjectEntry]] = {}
    for r in schema:
        out[r["file"]] = [
            ObjectEntry(name=o["name"], clamp_to_water_level=o["clamp_to_water_level"],
                        render_under_water=o["render_under_water"], generated_content="yes", layer=r["layer"],
                        pdxmesh=o["pdxmesh"],
                        transform_bin_file=map_objects.bin_path(o["name"]) if len(arrays[o["name"]]) else None)
            for o in r["objects"]]
    return out


def generate(f: Fields, schema: list[dict], t0: float | None = None) -> Result:
    values = family_values(f)
    gains = calibrate(values, schema, f)
    log(f"gains: trees {gains[0]:.4f}, bushes {gains[1]:.4f}", t0)
    arrays = place(values, gains, schema, f)
    log(f"placed {sum(len(a) for a in arrays.values()):,} instances", t0)
    entries = build_entries(schema, arrays)
    tint_dds, wind_dds, tint, wind = build_textures(f)
    return Result(f, schema, values, gains, arrays, entries, tint_dds, wind_dds, tint, wind)


def _assert_not_vanilla(path: Path) -> None:
    try:
        vr = vanilla_root().resolve()
    except Exception:       # no install on this machine: nothing to protect
        return
    p = Path(path).resolve()
    if p == vr or vr in p.parents:
        raise SystemExit(f"refusing to write into the vanilla install: {p}")


def output_files(res: Result, out_root: Path) -> dict[Path, bytes]:
    """Every file the run writes, path -> bytes (text files UTF-8 with BOM, LF)."""
    files: dict[Path, bytes] = {}
    for fname, entries in res.entries.items():
        files[out_root / GEN_REL / fname] = map_objects.render_object_file(entries).encode("utf-8")
    for name, a in res.arrays.items():
        if len(a):
            files[out_root / map_objects.BIN_DIR / f"{name}.bin"] = map_objects.bin_bytes(a)
    files[out_root / TEX_REL / "colormap_tree.dds"] = res.tint_dds
    files[out_root / TEX_REL / "windmap_tree.dds"] = res.wind_dds
    return files


def empty_bins(res: Result, out_root: Path) -> list[Path]:
    return [out_root / map_objects.BIN_DIR / f"{n}.bin" for n, a in res.arrays.items() if not len(a)]


def write(res: Result, out_root: Path, t0: float | None = None) -> None:
    out_root = Path(out_root)
    _assert_not_vanilla(out_root)
    for path, data in output_files(res, out_root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for stale in empty_bins(res, out_root):
        stale.unlink(missing_ok=True)
    log(f"wrote {len(res.entries)} object files, {sum(1 for a in res.arrays.values() if len(a))} .bin, 2 DDS "
        f"under {out_root}", t0)


def _norm_text(b: bytes) -> str:
    t = b.decode("utf-8")
    return t.lstrip(map_objects.BOM).replace("\r\n", "\n")


def check(res: Result, out_root: Path) -> list[str]:
    """Problems found comparing a fresh in-memory generation with ``out_root`` (empty list = current)."""
    out_root = Path(out_root)
    f = res.fields
    bad: list[str] = []
    for path, data in output_files(res, out_root).items():
        rel = path.relative_to(out_root).as_posix()
        if not path.exists():
            bad.append(f"{rel}: missing")
        elif path.suffix == ".txt":
            if _norm_text(path.read_bytes()) != _norm_text(data):
                bad.append(f"{rel}: stale")
        elif path.read_bytes() != data:
            bad.append(f"{rel}: stale (differs from a fresh generation)")
    for path in empty_bins(res, out_root):
        if path.exists():
            bad.append(f"{path.relative_to(out_root).as_posix()}: stray .bin for an object that is empty")
    fam_of = {o["name"]: r["family"] for r in res.schema for o in r["objects"]}
    for name, fam in sorted(fam_of.items()):
        p = out_root / map_objects.BIN_DIR / f"{name}.bin"
        if not p.exists() or not p.stat().st_size:
            continue
        a = map_objects.read_bin(p)
        ix, iy = record_pixels(a[:, 0], a[:, 2], f.canvas_h, f.canvas_w)
        ok = (f.sea_full if fam == ICEBERG_FAMILY else f.land_full)[iy, ix]
        if not ok.all():
            bad.append(f"{p.name}: {int((~ok).sum())} instances on {'land or lake' if fam == ICEBERG_FAMILY else 'sea or lake'}")
    return bad


def count_misplaced(res: Result) -> int:
    f = res.fields
    n = 0
    for r in res.schema:
        for o in r["objects"]:
            a = res.arrays[o["name"]]
            if not len(a):
                continue
            ix, iy = record_pixels(a[:, 0], a[:, 2], f.canvas_h, f.canvas_w)
            ok = (f.sea_full if r["family"] == ICEBERG_FAMILY else f.land_full)[iy, ix]
            n += int((~ok).sum())
    return n


# ---------------------------------------------------------------------------
# Renders for the visual gate (scratchpad/, gitignored)
# ---------------------------------------------------------------------------

def _coast_ds(f: Fields, w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    land = area_resize(f.L, w, h) >= 0.5
    coast = ndimage.binary_dilation(land) ^ ndimage.binary_erosion(land)
    return land, coast


def render_families(res: Result, out: Path) -> None:
    f = res.fields
    land, coast = _coast_ds(f, PREVIEW_W, PREVIEW_H)
    fams = sorted({r["family"] for r in res.schema})
    best = np.zeros((PREVIEW_H, PREVIEW_W), np.float32)
    dom = np.full((PREVIEW_H, PREVIEW_W), -1, np.int16)
    total = np.zeros((PREVIEW_H, PREVIEW_W), np.float32)
    for fi, fam in enumerate(fams):
        acc = np.zeros(f.shape, np.float32)
        for r in res.schema:
            if r["family"] == fam:
                lam, _ = file_lambda(r, res.values, res.gains, f)
                if lam is not None:
                    acc += lam.astype(np.float32)
        ds = area_resize(acc, PREVIEW_W, PREVIEW_H)
        total += ds
        hit = ds > best
        best[hit] = ds[hit]
        dom[hit] = fi
    ref = float(np.percentile(total[total > 0], 99)) if np.any(total > 0) else 1.0
    bright = np.clip(total / max(ref, 1e-9), 0.0, 1.0) ** 0.5
    pal = np.array([FAMILY_RGB.get(fam, (200, 200, 200)) for fam in fams] + [(0, 0, 0)], np.float32)
    dom[total < 0.02 * ref] = -1        # a faint haze of expected instances is not a family
    img = pal[dom] * (0.25 + 0.75 * bright[..., None])
    img[(dom < 0) & land] = (45, 50, 45)
    img[(dom < 0) & ~land] = SEA_PREVIEW_RGB
    img[coast] = COAST_PREVIEW_RGB
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(im)
    draw.rectangle((4, PREVIEW_H - 14 * (len(fams) + 2) - 6, 232, PREVIEW_H - 4), fill=SEA_PREVIEW_RGB)
    for k, fam in enumerate(fams):
        y = PREVIEW_H - 14 * (len(fams) + 1) + 14 * k - 2
        draw.rectangle((10, y, 22, y + 10), fill=FAMILY_RGB.get(fam, (200, 200, 200)))
        draw.text((28, y - 1), fam, fill=(235, 235, 235))
    draw.rectangle((10, PREVIEW_H - 16, 22, PREVIEW_H - 8), fill=(45, 50, 45))
    draw.text((28, PREVIEW_H - 17), "no trees on land", fill=(235, 235, 235))
    out.mkdir(parents=True, exist_ok=True)
    im.save(out / "vegetation_families.png")


def render_oldworld(res: Result, out: Path) -> None:
    f = res.fields
    s = f.canvas_w / CANVAS_W
    x0, y0, x1, y1 = (int(round(v * s)) for v in OLDWORLD_CROP)
    x1, y1 = min(x1, f.canvas_w), min(y1, f.canvas_h)
    elev = np.repeat(np.repeat(f.elev, f.grid, axis=0), f.grid, axis=1)[y0:y1, x0:x1]
    land = f.land_full[y0:y1, x0:x1]
    gy, gx = np.gradient(elev)
    shade = 0.55 + 0.35 * np.clip(elev / 2000.0, 0, 1) + 0.04 * np.clip(-(gx + gy), -4, 4)
    img = np.empty(elev.shape + (3,), np.float32)
    img[:] = SEA_PREVIEW_RGB
    img[land] = (np.array((70, 72, 62), np.float32) * shade[land][:, None])
    for r in res.schema:
        if r["layer"] != "semidynamic":
            continue
        rgb = FAMILY_RGB.get(r["family"], (255, 255, 255))
        for o in r["objects"]:
            a = res.arrays[o["name"]]
            if not len(a):
                continue
            ix, iy = record_pixels(a[:, 0], a[:, 2], f.canvas_h, f.canvas_w)
            sel = (ix >= x0) & (ix < x1) & (iy >= y0) & (iy < y1)
            img[iy[sel] - y0, ix[sel] - x0] = rgb
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(out / "vegetation_oldworld.png")


def render_texture_previews(res: Result, out: Path) -> None:
    f = res.fields
    _, coast = _coast_ds(f, PREVIEW_W, PREVIEW_H)
    for name, data in (("tree_tint_preview.png", res.tint_dds), ("tree_wind_preview.png", res.wind_dds)):
        lvl = dds.read_levels(data)[0][..., :3]
        im = np.asarray(Image.fromarray(np.ascontiguousarray(lvl)).resize((PREVIEW_W, PREVIEW_H), Image.LANCZOS)).copy()
        im[coast] = (200, 40, 40)
        out.mkdir(parents=True, exist_ok=True)
        Image.fromarray(im).save(out / name)


def pine_rule_split(res: Result) -> dict:
    """Expected pine instances per rule (boreal vs taiga), splitting each cell's expected count by the
    rule's share of that cell's value; ``ours`` is the placed count of the family."""
    f = res.fields
    parts = pine_parts(f)
    out: dict[str, dict[str, float]] = {}
    for fam in ("pine_dense", "pine_sparse"):
        kind = fam.split("_")[1]
        bo, ta = parts[f"boreal_{kind}"], parts[f"taiga_{kind}"]
        tot = np.maximum(bo + ta, np.float32(1e-12))
        e_bo = e_ta = 0.0
        for r in res.schema:
            if r["family"] != fam:
                continue
            lam, _v = file_lambda(r, res.values, res.gains, f)
            if lam is None:
                continue
            e_bo += float((lam * (bo / tot)).sum(dtype=np.float64))
            e_ta += float((lam * (ta / tot)).sum(dtype=np.float64))
        ours = sum(int(len(res.arrays[o["name"]])) for r in res.schema if r["family"] == fam for o in r["objects"])
        out[fam] = {"ours": ours, "boreal_rule_expected": round(e_bo), "taiga_rule_expected": round(e_ta)}
    return out


def exempt_family_counts(res: Result) -> dict:
    """Placed instances inside the latitude-exempt ground, per family."""
    f = res.fields
    if f.exempt_full is None or not f.exempt_full.any():
        return {"canvas_px": 0, "instances_by_family": {}}
    counts: dict[str, int] = {}
    for r in res.schema:
        for o in r["objects"]:
            a = res.arrays[o["name"]]
            if len(a):
                ix, iy = record_pixels(a[:, 0], a[:, 2], f.canvas_h, f.canvas_w)
                counts[r["family"]] = counts.get(r["family"], 0) + int(f.exempt_full[iy, ix].sum())
    return {"canvas_px": int(f.exempt_full.sum()), "instances_by_family": dict(sorted(counts.items()))}


def report_dict(res: Result) -> dict:
    f = res.fields
    fams = sorted({r["family"] for r in res.schema})
    ours = {fam: 0 for fam in fams}
    vanilla = {fam: 0 for fam in fams}
    for r in res.schema:
        for o in r["objects"]:
            ours[r["family"]] += int(len(res.arrays[o["name"]]))
            vanilla[r["family"]] += o["vanilla_count"]
    land_px = int(f.land_full.sum())
    landc = f.L >= 0.5
    dominant = np.argmax(np.stack([f.P[c] for c in CLASSES]), axis=0)
    shares = {c: round(float((dominant[landc] == i).mean()), 4) if landc.any() else 0.0
              for i, c in enumerate(CLASSES)}
    mean_p = {c: round(float(f.P[c][landc].mean()), 4) if landc.any() else 0.0 for c in CLASSES}
    cell = f.grid * f.grid
    exp_tree = expected_total(res.values, res.schema, res.gains[0], res.gains[1], cell, bush=False)
    exp_bush = expected_total(res.values, res.schema, res.gains[0], res.gains[1], cell, bush=True)
    return {
        "families": {fam: {"ours": ours[fam], "vanilla_count": vanilla[fam]} for fam in fams},
        "totals": {"ours": sum(ours.values()), "vanilla": sum(vanilla.values()),
                   "trees_ours": sum(v for k, v in ours.items() if k not in BUSH_FAMILIES and k != ICEBERG_FAMILY),
                   "bushes_ours": sum(v for k, v in ours.items() if k in BUSH_FAMILIES),
                   "icebergs_ours": ours.get(ICEBERG_FAMILY, 0)},
        "gains": {"trees": round(res.gains[0], 5), "bushes": round(res.gains[1], 5)},
        "targets": {"trees": round(TARGET_TREES_PER_LAND_PX * land_px), "bushes": round(TARGET_BUSHES_PER_LAND_PX * land_px),
                    "trees_expected": round(exp_tree), "bushes_expected": round(exp_bush),
                    "land_px": land_px},
        "class_share_dominant": shares,
        "class_mean_probability": mean_p,
        "unruled_families": unruled_families(res.schema),
        "slope_share_of_land_cells": {"above_18": round(float((f.slope[landc] > 18).mean()), 4),
                                      "above_40": round(float((f.slope[landc] > 40).mean()), 4),
                                      "smooth_px": SLOPE_SMOOTH_PX},
        "land_cells_carrying_trees": round(float((sum(res.values.values())[landc] > 0.01).mean()), 4),
        "pine_by_rule": pine_rule_split(res),
        "latitude_exempt": {"realms": list(LATITUDE_EXEMPT_REALMS), **exempt_family_counts(res)},
        "taiga": {"materials": list(TAIGA_MATERIALS), "lat": list(TAIGA_LAT), "min_lat": list(TAIGA_MIN_LAT),
                  "dense": TAIGA_DENSE, "sparse": TAIGA_SPARSE},
        "land_north_of_52N": {
            "cells": int((landc & (f.lat > 52.0)).sum()),
            "carrying_trees_share": round(float((sum(res.values.values())[landc & (f.lat > 52.0)] > 0.01).mean()), 4)
            if (landc & (f.lat > 52.0)).any() else 0.0},
        "instances_on_sea_or_lake": count_misplaced(res),
    }


def render_all(res: Result, out: Path = SCRATCH_DIR) -> None:
    render_families(res, out)
    render_oldworld(res, out)
    render_texture_previews(res, out)
    rep = report_dict(res)
    (out / "vegetation_report.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    log(f"previews and report in {out}")


# ---------------------------------------------------------------------------
# Self-test: a synthetic 1/8-scale world
# ---------------------------------------------------------------------------

def synthetic_schema() -> list[dict]:
    fams = list(RULE_FAMILIES) + [ICEBERG_FAMILY]
    layers = {"oak": "semidynamic_high", "oak_dense": "semidynamic_medium", "pine_dense": "semidynamic_medium"}
    rows = []
    for fam in sorted(fams):
        stem = f"{fam}_generator_1"
        objs = []
        for k, cnt in enumerate((60, 0, 40) if fam == "oak_dense" else (60, 40)):
            objs.append({"name": f"{stem}_{k}", "pdxmesh": f"{fam}_{k}_mesh",
                         "clamp_to_water_level": "yes" if fam == ICEBERG_FAMILY else "no",
                         "render_under_water": "yes" if fam == ICEBERG_FAMILY else "no",
                         "vanilla_count": cnt, "scale_min": 0.5 if cnt else 0, "scale_max": 1.25 if cnt else 0})
        rows.append({"file": f"{stem}.txt", "family": fam, "layer": layers.get(fam, "semidynamic"), "objects": objs})
    return rows


def TAIGA_PATCH(alat: np.ndarray, w: int, min_lat: float = 56.0) -> np.ndarray:
    """Working-grid cells of the synthetic world's permafrost patch (|lat| >= ``min_lat``, columns 140-260)."""
    cols = np.arange(w)[None, :]
    return (alat >= min_lat) & (cols >= 140) & (cols < 260)


def exempt_canvas_patch(shape: tuple[int, int], land: np.ndarray) -> np.ndarray:
    """Canvas mask of the synthetic latitude-exempt patch: Mediterranean latitudes (about 34-43 N) on the
    northern island, where the unexempt model grows cypress."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return land & (xx >= 350) & (xx < 440) & (yy >= 115) & (yy < 145)


def synthetic_fields(canvas_w: int = 1024, canvas_h: int = 452, exempt: bool = True) -> Fields:
    from worldgen import reproject
    h, w = canvas_h // G, canvas_w // G
    yy, xx = np.mgrid[0:canvas_h, 0:canvas_w]
    land = (((xx - 300) / 250.0) ** 2 + ((yy - 170) / 70.0) ** 2 < 1) \
        | (((xx - 750) / 200.0) ** 2 + ((yy - 300) / 100.0) ** 2 < 1) \
        | (((xx - 400) / 150.0) ** 2 + ((yy - 75) / 25.0) ** 2 < 1)
    lake = ((xx - 300) ** 2 + (yy - 170) ** 2) < 12 ** 2
    rng = np.random.default_rng(7)
    hill = np.exp(-(((xx - 260) / 40.0) ** 2 + ((yy - 150) / 30.0) ** 2))
    elev = (150 + 2600 * hill + 80 * ndimage.gaussian_filter(rng.standard_normal(land.shape), 6)).astype(np.float32)
    lat_rows = reproject.canvas_lonlat(np.arange(canvas_h), canvas_w, canvas_h)[1][:, 0]
    alat = np.abs(lat_rows)[G // 2::G][:h, None] * np.ones((1, w))
    wob = ndimage.gaussian_filter(rng.standard_normal((h, w)), 4)
    wob = (wob / wob.std() * 0.25).astype(np.float32)
    zero = np.zeros((h, w), np.float32)
    m = {n: zero.copy() for n in REQUIRED_MASKS}
    jungle, sav, temp = alat < 18, (alat >= 18) & (alat < 30), alat >= 30
    m["marchlands_03"][jungle] = 0.4
    m["woodlands_03"][jungle] = 0.5
    m["grasslands_06"][jungle] = 0.1
    m["savanna_01"][sav] = 0.5
    m["savanna_03"][sav] = 0.3
    m["grasslands_05"][sav] = 0.2
    m["woodlands_01"][temp] = 0.5 + wob[temp]
    m["grasslands_01"][temp] = 0.3
    m["marchlands_01"][temp] = 0.2 - wob[temp]
    m["woodlands_02"][temp & (np.arange(w)[None, :] > w * 0.6)] = 0.4
    m["desert_01"][(alat > 18) & (alat < 30) & (np.arange(w)[None, :] > w * 0.7)] = 0.7
    m["cliff_granite_01"][block_mean(elev, G) > 1200] = 0.5
    # a permafrost patch at high latitude with no temperate ground under it: only the taiga rule can grow pine there
    pm = TAIGA_PATCH(alat, w)
    for n in ("woodlands_01", "grasslands_01", "marchlands_01", "woodlands_02"):
        m[n][pm] = 0.0
    m["permafrost_01"][pm] = 0.5
    m["permafrost_03"][pm] = 0.1
    m["snow"][pm] = 0.2
    for n in m:
        m[n] = np.clip(m[n], 0, 1)
    ex = exempt_canvas_patch(land.shape, land & ~lake) if exempt else None
    return fields_from_arrays(land, lake, elev, lambda n: m[n], lat_rows, exempt=ex)


def selftest() -> int:
    t0 = time.time()
    # codec: bin entry, inline entry closed by '"}', render -> parse identity
    rows = np.array([[10.5, 0, 20.25, 0, 0.6, 0, 0.8, 0.9, 0.9, 0.9],
                     [11.5, 0, 21.25, 0, 0.0, 0, 1.0, 1.1, 1.1, 1.1]], np.float32)
    vanilla_like = ('﻿object={\n\tname="a_0"\n\tclamp_to_water_level=no\n\trender_under_water=no\n'
                    '\tgenerated_content=yes\n\tlayer="semidynamic"\n\tpdxmesh="m"\n\tcount=2\n\ttransform="'
                    + "\n".join(" ".join(f"{v:.6f}" for v in r) for r in rows) + '\n"}\n'
                    'object={\n\tname="a_1"\n\tclamp_to_water_level=no\n\trender_under_water=no\n'
                    '\tgenerated_content=yes\n\tlayer="semidynamic"\n\tpdxmesh="m"\n'
                    '\ttransform_bin_file="gfx/map/map_object_data/a_1.bin"\n}\n'
                    'object={\n\tname="a_2"\n\tclamp_to_water_level=no\n\trender_under_water=no\n'
                    '\tgenerated_content=yes\n\tlayer="semidynamic"\n\tpdxmesh="m"\n}\n')
    ents = map_objects.parse_object_file(vanilla_like)
    assert [e.name for e in ents] == ["a_0", "a_1", "a_2"], ents
    assert ents[0].inline is not None and np.array_equal(ents[0].inline, rows)
    assert ents[1].transform_bin_file == "gfx/map/map_object_data/a_1.bin" and ents[1].inline is None
    assert ents[2].transform_bin_file is None and ents[2].inline is None
    assert map_objects.render_object_file(ents) == vanilla_like, "render does not reproduce vanilla's text form"
    again = map_objects.parse_object_file(map_objects.render_object_file(ents))
    assert [(e.name, e.layer, e.pdxmesh, e.transform_bin_file) for e in again] == \
        [(e.name, e.layer, e.pdxmesh, e.transform_bin_file) for e in ents]
    assert np.array_equal(again[0].inline, rows)
    assert map_objects.parse_object_file(vanilla_like.replace("\n", "\r\n"))[0].inline is not None
    try:
        map_objects.parse_object_file(vanilla_like.replace("count=2", "count=3"))
        raise AssertionError("a wrong count was accepted")
    except ValueError:
        pass
    raw = map_objects.bin_bytes(rows)
    assert len(raw) == 2 * map_objects.RECORD_BYTES
    with tempfile.TemporaryDirectory() as td:
        bp = Path(td) / "t.bin"
        bp.write_bytes(raw)
        assert np.array_equal(map_objects.read_bin(bp), rows)
        bp.write_bytes(raw + b"\0")
        try:
            map_objects.read_bin(bp)
            raise AssertionError("a ragged .bin was accepted")
        except ValueError:
            pass
        q = map_objects.yaw_quat(1.0)
        assert q[0] == 0 and q[2] == 0 and abs(q[1] ** 2 + q[3] ** 2 - 1) < 1e-12
        assert dds.header_bc(TINT_W, TINT_H, 1, "DXT1") == HEADER_TINT
        assert dds.header_bc(WIND_W, WIND_H, 11, "DXT1") == HEADER_WIND

        # the synthetic world
        f = synthetic_fields()
        schema = synthetic_schema()
        assert unruled_families(schema) == []
        r1 = generate(f, schema)
        r2 = generate(synthetic_fields(), schema)
        a1, a2 = output_files(r1, Path("x")), output_files(r2, Path("x"))
        assert a1.keys() == a2.keys() and all(a1[k] == a2[k] for k in a1), "two runs are not byte-equal"
        n_total = sum(len(a) for a in r1.arrays.values())
        assert n_total > 1000, n_total
        assert count_misplaced(r1) == 0, "instances on sea or lake"
        ice = sum(len(r1.arrays[o["name"]]) for o in schema[[r["family"] for r in schema].index("iceberg")]["objects"])
        assert ice > 0, "no icebergs"
        assert len(r1.arrays["oak_dense_generator_1_1"]) == 0, "an empty vanilla object was chosen"
        for a in r1.arrays.values():
            if len(a):
                assert a.dtype == np.float32 and np.all(a[:, 1] == 0) and np.all(a[:, 3] == 0) and np.all(a[:, 5] == 0)
                assert np.abs(a[:, 4] ** 2 + a[:, 6] ** 2 - 1).max() < 1e-5, "quaternion not unit"
                assert a[:, 0].min() >= 0 and a[:, 0].max() < f.canvas_w and a[:, 2].min() > 0 and a[:, 2].max() <= f.canvas_h
                assert np.all(a[:, 7] == a[:, 8]) and np.all(a[:, 8] == a[:, 9])
        # latitude exemption: the exempt patch grows oak and no Mediterranean cypress; without the exemption it does
        epatch = block_mean(exempt_canvas_patch(f.land_full.shape, f.land_full).astype(np.float32), G) > 0.99
        assert int(epatch.sum()) >= 30, int(epatch.sum())
        mm = climate_blend(f)[1]
        assert float(mm[epatch].max()) == 0.0, "exempt patch still has a Mediterranean weight"
        for fam in ("cypress_mediterranean_dense", "cypress_mediterranean_sparse"):
            assert r1.values[fam][epatch].sum() == 0, f"exempt patch has {fam}"
        assert r1.values["oak_dense"][epatch].sum() > 0 and r1.values["oak"][epatch].sum() > 0, "exempt patch has no oak"
        r_ne = generate(synthetic_fields(exempt=False), schema)
        assert (r_ne.values["cypress_mediterranean_dense"][epatch].sum() > 0
                and r_ne.values["cypress_mediterranean_sparse"][epatch].sum() > 0), "unexempt patch has no cypress"
        assert r_ne.values["oak_dense"][epatch].sum() < r1.values["oak_dense"][epatch].sum(),             "the exemption did not raise the patch's oak"
        assert float(climate_blend(f)[0][epatch].max()) < 0.25, "exempt patch (low ground) still has a boreal weight"
        # taiga: the permafrost patch receives pine, and none with the rule switched off
        patch = TAIGA_PATCH(np.abs(f.lat) * np.ones((1, f.shape[1])), f.shape[1], 57.0) & (f.L > 0.99)  # inside the painted patch, clear of its edge row
        assert int(patch.sum()) >= 50, int(patch.sum())
        pine_on = r1.values["pine_dense"][patch].sum() + r1.values["pine_sparse"][patch].sum()
        assert pine_on > 0, "taiga: no pine value on the permafrost patch"

        def pine_in_patch(res: Result) -> int:
            n = 0
            for rr in res.schema:
                if rr["family"] in ("pine_dense", "pine_sparse"):
                    for o in rr["objects"]:
                        a = res.arrays[o["name"]]
                        if len(a):
                            ix, iy = record_pixels(a[:, 0], a[:, 2], f.canvas_h, f.canvas_w)
                            n += int(patch[iy // f.grid, ix // f.grid].sum())
            return n

        n_on = pine_in_patch(r1)
        assert n_on > 0, "taiga: no pine instance on the permafrost patch"
        sv = TAIGA_DENSE, TAIGA_SPARSE
        try:
            globals()["TAIGA_DENSE"] = globals()["TAIGA_SPARSE"] = 0.0
            r0 = generate(synthetic_fields(), schema)
            assert r0.values["pine_dense"][patch].sum() == 0 and r0.values["pine_sparse"][patch].sum() == 0,                 "taiga off: the patch still has pine value"
            assert pine_in_patch(r0) == 0, "taiga off: the patch still receives pine"
        finally:
            globals()["TAIGA_DENSE"], globals()["TAIGA_SPARSE"] = sv
        split = pine_rule_split(r1)
        assert split["pine_dense"]["taiga_rule_expected"] > 0 and split["pine_sparse"]["taiga_rule_expected"] > 0
        # counts hit the calibrated target
        cell = f.grid * f.grid
        land_px = int(f.land_full.sum())
        for bush, tgt in ((False, TARGET_TREES_PER_LAND_PX), (True, TARGET_BUSHES_PER_LAND_PX)):
            e = expected_total(r1.values, schema, *r1.gains, cell, bush=bush)
            assert abs(e / (tgt * land_px) - 1) < 0.005, (bush, e, tgt * land_px)
        # DDS container
        assert len(r1.tint_dds) == TINT_BYTES and r1.tint_dds[:128] == HEADER_TINT
        assert len(r1.wind_dds) == WIND_BYTES and r1.wind_dds[:128] == HEADER_WIND
        assert r1.tint.shape == (TINT_H, TINT_W, 3) and r1.wind.shape == (WIND_H, WIND_W, 3)
        # write -> check round trip, then corruption is caught
        out = Path(td) / "out"
        write(r1, out)
        assert check(r1, out) == [], check(r1, out)
        victim = next(out / map_objects.BIN_DIR / f"{n}.bin" for n, a in r1.arrays.items() if len(a))
        victim.write_bytes(victim.read_bytes()[:-map_objects.RECORD_BYTES])
        assert any("stale" in p for p in check(r1, out))
        stray = out / map_objects.BIN_DIR / "oak_dense_generator_1_1.bin"
        stray.write_bytes(raw)
        assert any("stray" in p for p in check(r1, out))
        # previews and report build
        render_all(r1, Path(td) / "prev")
        for nm in ("vegetation_families.png", "vegetation_oldworld.png", "tree_tint_preview.png",
                   "tree_wind_preview.png", "vegetation_report.json"):
            assert (Path(td) / "prev" / nm).exists(), nm
        with Image.open(Path(td) / "prev" / "vegetation_families.png") as im:
            assert im.size == (PREVIEW_W, PREVIEW_H)
        assert json.loads((Path(td) / "prev" / "vegetation_report.json").read_text())["instances_on_sea_or_lake"] == 0
    log(f"selftest ok ({n_total:,} synthetic instances, {ice} icebergs, {n_on} pine on the taiga patch)", t0)
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=REPO_DIR, help="output root (default: the repo root)")
    p.add_argument("--terrain", type=Path, default=DEFAULT_TERRAIN, help="folder of the mask_<material>.png files")
    p.add_argument("--render", action="store_true", help="also write the preview PNGs and report to scratchpad/")
    p.add_argument("--check", action="store_true", help="regenerate in memory and compare with --out")
    p.add_argument("--selftest", action="store_true", help="synthetic 1/8-scale world, needs no files")
    p.add_argument("--dump-vanilla-schema", action="store_true", help="(dev) write config/vegetation_objects.json")
    p.add_argument("--check-schema", action="store_true", help="(dev) re-derive the schema and diff it")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.dump_vanilla_schema:
        return dump_vanilla_schema()
    if args.check_schema:
        return check_schema()

    t0 = time.time()
    schema = load_schema()
    missing = unruled_families(schema)
    if missing:
        log(f"families with no placement rule (written empty): {', '.join(missing)}", t0)
    f = load_fields(args.terrain)
    res = generate(f, schema, t0)
    if args.check:
        bad = check(res, args.out)
        if bad:
            print("\n".join(bad))
            print("run: python mapgen/generate_vegetation.py")
            return 1
        log("vegetation outputs current", t0)
        return 0
    write(res, args.out, t0)
    if args.render:
        render_all(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
