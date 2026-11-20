#!/usr/bin/env python3
"""Field, forestry and mine dressing: three masks and the building placements (#11536).

As farms, logging camps and mines grow, the map dresses the land. Two data sets decide
where, both vanilla's and both Earth's:

* ``gfx/map/masks/mask_dynamic_{farmland,forestry,mining}.png`` (8192x3616, mode ``L``)
  bound where the terrain manipulators (``common/terrain_manipulators``, not overridden
  by the mod) may paint the converted-province ground and its ``farms_dynamic`` /
  ``forestry_dynamic`` / ``mines_dynamic`` layers. ``mask_dynamic_farmland`` is also the
  ``terrain_mask`` of ``urban_city`` and ``urban_port``, so it bounds city sprawl too.
* The farm, camp and mine buildings that sit on that ground are placed by inline
  ``transform`` rows in ``gfx/map/map_object_data/generated/<family>_dynamic_<kind>_
  objects_generator_<n>.txt`` (one file per family and kind, one object per mesh; 24
  files counting the French DLC family). They too are Earth's positions: measured
  2026-11-19, Earth's meshes come within 4 px of only 23% (farm), 13% (forestry) and
  2.4% (mining) of our land, so masks alone leave the buildings mostly absent.

This script writes our own of both from committed data only. Vanilla's three PNGs and
24 files are overridden at their vanilla paths.

Inputs (nothing new is sourced):

* ``map_data/state_regions/*.txt`` + ``map_data/provinces.png`` -> **land**: every pixel
  whose province is listed in a land state, minus that state's ``impassable`` provinces.
  Sea, lakes and impassable land are zero in every mask. The pixel count where this
  disagrees with ``land_sea_mask.png`` / ``lake_mask.png`` is logged, not an error.
* ``generate_map_locators.compute()`` -> the ``city``, ``farm``, ``port``, ``wood`` and
  ``mine`` hubs (y = 3616 - z). The locator ``.txt`` files are gitignored; not read.
* ``mapgen/derived/arable_heatmap.png`` -> where the ground is farmland.
* ``gfx/map/terrain/mask_woodlands_0{1,2,3}.png`` (``--terrain-dir``, #6617) -> where it
  is forest, so ground and dressing agree.
* ``mapgen/config/state_homelands.json`` + ``common/cultures/*.txt`` -> the **building
  family** of each state: its first homeland culture's ``graphics`` value (european,
  arabic, east_asian and south_asian -> asian, african, decentralised_americas ->
  latin; anything else, or an empty row, -> european). All families share one layer, so a
  pixel belongs to exactly one family and buildings never stack. The ``french`` family
  is a DLC004 asset set (its meshes do not exist without the DLC), so it is never
  mapped: its four files are blanked, as are the families no state uses.

Masks (vanilla: 45% / 25% / 3.3% of land non-zero; medians 198 / 97 / 121):

* farmland: ``255 * smoothstep(arable, p55, p87)`` over land percentiles, blurred
  (sigma 1.5 px), maxed with a feathered disc (255 inside 8 px, 0 at 14 px) at every
  ``city``, ``farm`` and ``port`` hub.
* forestry: ``180 * smoothstep(sum of the three woodland masks, 16, 128)`` blurred
  (sigma 2 px), maxed with a disc (140 inside 5 px, 0 at 9 px) at every ``wood`` hub.
  Never 255, as vanilla.
* mining: a hollow ring per ``mine`` hub, ``180 * smoothstep(r, 3, 6) * (1 - smoothstep
  (r, 11, 16))`` with r wobbled by seeded smooth radial noise.

Placements, per (kind, family, generator file): over the pixels of that family's states
a seeded uniform draw below ``max_density * sum(mesh weights) * DENSITY_SCALE * density(mask)`` places an
instance (sub-pixel jitter, mesh by weight, seeded yaw), as vanilla's content-source
generators (``content_source/map_objects/generators``) do. Vanilla's rows carry scale
0 or 1 only (measured 2026-11-19: ``--check`` re-measures it): scale 1 where the
generator's mask is at its top, scale 0 elsewhere. We write scale 1 where our mask is at
least :data:`KEEP_FRACTION` of the kind's peak and, with :data:`EMIT_ZERO_SCALE`, scale
0 for the other drawn instances, as vanilla does. File layout is vanilla's bytes: UTF-8
BOM, LF, one ``object={...}`` per mesh, every transform row ``x 0 z 0 qy 0 qw sx sy sz``
(z = 3616 - y) newline-terminated, closing ``"}``.

Output is a pure function of those inputs plus ``map_config.SEED``. The masks are
committed (Git LFS) only after Chris accepts the preview; the mesh files (~tens of MB
of text) are gitignored and rebuilt from the committed masks by ``--from-masks``.

Usage::

    python mapgen/generate_dynamic_masks.py                 # write 3 masks + 24 mesh files
    python mapgen/generate_dynamic_masks.py --render        # also scratchpad/dynamic_masks_preview{,_oldworld}.png
    python mapgen/generate_dynamic_masks.py --no-write --render   # tuning loop: preview only
    python mapgen/generate_dynamic_masks.py --from-masks    # rebuild the mesh files from the committed masks
    python mapgen/generate_dynamic_masks.py --check         # regenerate in memory, compare with disk
    python mapgen/generate_dynamic_masks.py --selftest      # synthetic 1/8-scale world, needs no files

Run with ``mapgen/.venv/Scripts/python.exe`` (needs scipy). A change to any input (map
regen, arable heatmap, woodland masks, hubs, homelands) makes ``--check`` fail; the
response is to re-run, render and have the preview accepted again.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import state_ownership  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
SCRATCH_DIR = REPO_ROOT / "scratchpad"
MASK_DIR = REPO_ROOT / "gfx" / "map" / "masks"
MESH_DIR = REPO_ROOT / "gfx" / "map" / "map_object_data" / "generated"
TERRAIN_DIR = REPO_ROOT / "gfx" / "map" / "terrain"
STATE_REGIONS_DIR = REPO_ROOT / "map_data" / "state_regions"
PROVINCES_PNG = REPO_ROOT / "map_data" / "provinces.png"
HOMELANDS = TOOLS_DIR / "config" / "state_homelands.json"
CULTURES_DIR = REPO_ROOT / "common" / "cultures"

W, H = map_config.PROVINCES_SIZE
BLOCK = 256                                # canvas rows per full-resolution block
OLDWORLD_CROP = (3450, 134, 5200, 1860)    # canvas box of the full-resolution preview crop (as generate_terrain_masks)

KINDS = ("farmland", "forestry", "mining")
KIND_INDEX = {k: i for i, k in enumerate(KINDS)}
KIND_LAYER = {"farmland": "farms_dynamic", "forestry": "forestry_dynamic", "mining": "mines_dynamic"}
#: Vanilla's name for each kind in ``content_source/map_objects/generators/<family>_<x>_generator.txt``.
KIND_GENERATOR = {"farmland": "farms", "forestry": "forestry", "mining": "mining"}
MASK_NAME = {k: f"mask_dynamic_{k}.png" for k in KINDS}
#: Highest value each mask reaches (forestry and mining never 255, as vanilla's).
KIND_PEAK = {"farmland": 255, "forestry": 180, "mining": 180}
VANILLA_STATS = {"farmland": (45.0, 198), "forestry": (25.0, 97), "mining": (3.3, 121)}   # % of land non-zero, median

#: Building families, in seed order (the index feeds the placement RNG; never reorder).
FAMILY_ORDER = ("european", "asian", "arabic", "african", "latin")
FAMILY_NONE = 255
#: ``graphics`` value of a state's first homeland culture -> building family; anything else is european.
GRAPHICS_FAMILY = {"european": "european", "arabic": "arabic", "east_asian": "asian", "south_asian": "asian",
                   "african": "african", "decentralised_americas": "latin"}
DEFAULT_FAMILY = "european"
#: DLC004 (Voice of the People) families: meshes exist only with the DLC, so they are blanked, never mapped.
DLC_BLANK_FAMILIES = ("french",)

# --- tuning (each constant has a value that switches its rule off)
FARM_PERCENTILES = (55.0, 87.0)    # land arable percentiles bounding the smoothstep
FARM_BLUR = 1.5                    # px
FARM_DISC = (8.0, 14.0)            # px: 255 inside, 0 at the outer radius
FARM_HUBS = ("city", "farm", "port")
FOREST_VALUE = 180
FOREST_RAMP = (16.0, 128.0)        # summed woodland weight (of 255)
FOREST_BLUR = 2.0                  # px
FOREST_DISC_VALUE = 140
FOREST_DISC = (5.0, 9.0)
MINE_VALUE = 180
MINE_RING = (3.0, 6.0, 11.0, 16.0)  # px: inner ramp, outer ramp
MINE_WOBBLE = 0.25                 # +-25% radius wobble
MINE_HARMONICS = 4
MINE_SEED_STREAM = 3               # np.random.default_rng([SEED, 3]) draws the ring wobbles
#: An instance is scale 1 where its mask is at least this share of the kind's peak. Measured on vanilla's live
#: rows (2026-11-19): the mask under scale-1 rows has its 10th percentile at 192/255 (farmland, peak 255) and 147-148
#: of 192 (forestry, mining), i.e. 0.75-0.77 of the peak; the rows below that are the scale-0 fringe.
KEEP_FRACTION = 0.75
#: Drawn rows per unit of mask mass (sum of mask/255), scaling the generators' ``max_density``. Vanilla's live files
#: (DLC004 european_* and french_*, the base game's other families, european farmland from its ``.bin``) hold, per unit of
#: its global mask's mass: 0.0325 farm rows (generators' nominal 0.0825 for european), 0.0618 lumberpile rows (nominal
#: 0.2), 0.1008 mining rows (nominal 0.11 on vanilla's mask shape). Without this scale our dressing is 2-3x vanilla's.
DENSITY_SCALE = {"farmland": 0.39, "forestry": 0.31, "mining": 0.92}
#: Vanilla's current rows are scale 0 or 1 only, zero rows 33-67% of them (measured 2026-11-19),
#: so writing the dropped instances at scale 0 matches vanilla's files. Set False to drop them.
EMIT_ZERO_SCALE = True
#: ``density_curve`` of vanilla's generators: farms and forestry are linear in the mask, mining
#: runs from 0.5 at the lowest mask value to 1 at the highest.
DENSITY_FLOOR = {"farmland": 0.0, "forestry": 0.0, "mining": 0.5}


def log(msg: str) -> None:
    print(msg, flush=True)


def smoothstep(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------- building families

def _mesh(*pairs):
    return tuple(pairs)


#: Per family and kind: the generator files, each ``(file index, max_density, ((mesh, weight), ...))``.
#: Object ``i`` of file ``n`` is named ``<family>_dynamic_<kind>_objects_generator_<n>_<i>``. Names and
#: meshes are vanilla's current generated headers (DLC004's where it ships one: the base game's
#: ``european_province_farm_01_nobillboards_mesh`` is a mesh no asset defines); ``--check`` verifies
#: them. Weights are the content-source generators' (``asian`` farms: the three meshes its generated
#: file carries, at the weights its row counts show); ``--check`` compares the row-count shares.
FAMILIES: dict[str, dict[str, tuple]] = {
    "european": {
        "farmland": ((1, 0.075, (("european_province_farm_01_mesh", 0.25), ("european_province_farm_02_mesh", 0.25),
                                 ("european_farm_farmhouse_01_mesh", 0.25), ("european_farm_farmhouse_02_mesh", 0.25),
                                 ("windmill_01_mesh", 0.10))),),
        "forestry": ((1, 0.02, (("generic_rural_forestry_camp_01_mesh", 0.2), ("generic_rural_forestry_camp_02_mesh", 0.2))),
                     (2, 0.2, (("generic_forestry_lumberpile_02_mesh", 1.0),))),
        "mining": ((1, 0.1, (("generic_rural_mining_coaldepo_01_mesh", 0.25), ("generic_rural_mining_coaldepo_02_mesh", 0.2),
                             ("generic_rural_mining_pile_01_mesh", 0.05), ("generic_rural_mining_pile_02_mesh", 0.05),
                             ("generic_rural_mining_entrance_01_mesh", 0.05), ("generic_rural_mining_entrance_02_mesh", 0.05))),),
    },
    "asian": {
        "farmland": ((1, 0.075, (("asian_province_subfarm_01_mesh", 0.5), ("asian_province_subfarm_02_mesh", 0.5),
                                 ("windmill_01_mesh", 0.10))),),
        "forestry": ((1, 0.02, (("asian_forestry_camp_01_mesh", 0.1), ("asian_forestry_camp_02_mesh", 0.1))),
                     (2, 0.2, (("generic_forestry_lumberpile_02_mesh", 1.0),))),
        "mining": ((1, 0.1, (("asian_mining_coaldepo_01_mesh", 0.25), ("generic_rural_mining_coaldepo_02_mesh", 0.2),
                             ("generic_rural_mining_pile_01_mesh", 0.05), ("generic_rural_mining_pile_02_mesh", 0.05),
                             ("generic_rural_mining_entrance_01_mesh", 0.05), ("generic_rural_mining_entrance_02_mesh", 0.05))),),
    },
    "arabic": {
        "farmland": ((1, 0.075, (("arabic_farm_farmstead_01_mesh", 0.25), ("arabic_farm_scatter_01_mesh", 0.25),
                                 ("arabic_farm_scatter_02_mesh", 0.25), ("windmill_01_mesh", 0.10))),),
        "forestry": ((1, 0.02, (("arabic_forestry_scatter_01_mesh", 0.1), ("arabic_forestry_scatter_02_mesh", 0.1))),
                     (2, 0.2, (("generic_forestry_lumberpile_02_mesh", 1.0),))),
        "mining": ((1, 0.1, (("generic_rural_mining_coaldepo_sandstone_01_mesh", 0.25), ("generic_rural_mining_coaldepo_02_mesh", 0.2),
                             ("generic_rural_mining_pile_01_mesh", 0.05), ("generic_rural_mining_pile_02_mesh", 0.05),
                             ("generic_rural_mining_entrance_01_mesh", 0.05), ("generic_rural_mining_entrance_02_mesh", 0.05))),),
    },
    "african": {
        "farmland": ((1, 0.075, (("african_farm_farmstead_01_mesh", 0.25), ("african_farm_farmstead_01_mesh", 0.25),
                                 ("african_farm_scatter_01_mesh", 0.25), ("african_farm_scatter_02_mesh", 0.25),
                                 ("windmill_01_mesh", 0.10))),),
        "forestry": ((1, 0.02, (("african_forestry_scatter_01_mesh", 0.1), ("african_forestry_scatter_02_mesh", 0.1))),
                     (2, 0.2, (("generic_forestry_lumberpile_02_mesh", 1.0),))),
        "mining": ((1, 0.1, (("african_mining_coaldepo_01_mesh", 0.2), ("generic_rural_mining_coaldepo_02_mesh", 0.25),
                             ("generic_rural_mining_pile_01_mesh", 0.05), ("generic_rural_mining_pile_02_mesh", 0.05),
                             ("generic_rural_mining_entrance_01_mesh", 0.05), ("generic_rural_mining_entrance_02_mesh", 0.05))),),
    },
    "latin": {
        "farmland": ((1, 0.075, (("latin_farm_farmstead_01_mesh", 0.25), ("latin_farm_scatter_01_mesh", 0.25),
                                 ("latin_farm_scatter_02_mesh", 0.25), ("windmill_01_mesh", 0.10))),),
        "forestry": ((1, 0.02, (("latin_forestry_scatter_01_mesh", 0.1), ("latin_forestry_scatter_02_mesh", 0.1))),
                     (2, 0.2, (("generic_forestry_lumberpile_02_mesh", 1.0),))),
        "mining": ((1, 0.1, (("latin_mining_coaldepo_01_mesh", 0.25), ("generic_rural_mining_coaldepo_02_mesh", 0.2),
                             ("generic_rural_mining_pile_01_mesh", 0.05), ("generic_rural_mining_pile_02_mesh", 0.05),
                             ("generic_rural_mining_entrance_01_mesh", 0.05), ("generic_rural_mining_entrance_02_mesh", 0.05))),),
    },
}
#: Per kind, the generator file indices every family has (the French DLC family has the same four files).
KIND_FILES = {"farmland": (1,), "forestry": (1, 2), "mining": (1,)}


def file_stem(family: str, kind: str, n: int) -> str:
    return f"{family}_dynamic_{kind}_objects_generator_{n}"


def all_files() -> list[tuple[str, str, int]]:
    """Every ``(family, kind, n)`` this script writes: the five families plus the blanked DLC family."""
    out = []
    for fam in FAMILY_ORDER + DLC_BLANK_FAMILIES:
        for kind in KINDS:
            for n in KIND_FILES[kind]:
                out.append((fam, kind, n))
    return out


def file_spec(family: str, kind: str, n: int):
    for idx, max_density, meshes in FAMILIES.get(family, {}).get(kind, ()):
        if idx == n:
            return max_density, meshes
    return None


# --------------------------------------------------------------------------- inputs

@dataclass
class Inputs:
    """Canvas-resolution inputs. ``fam`` is the per-pixel family index (:data:`FAMILY_NONE` off land)."""
    land: np.ndarray        # bool [H, W]
    fam: np.ndarray         # uint8 [H, W]
    arable: np.ndarray      # float32 [H, W], 0..1
    wood: np.ndarray        # uint16 [H, W], summed woodland weight (0..255)
    locators: dict          # {type: [(state id, x, z)]}, canvas px with z = height - y
    wood_source: str = ""   # which woodland masks were read, for the preview caption
    family_states: dict | None = None   # {family: state count}, for the log


def parse_states_with_impassable(directory: Path):
    """``[(key, provinces, impassable)]`` for every land state file (``99_seas.txt`` skipped)."""
    out = []
    for path in sorted(Path(directory).glob("*.txt")):
        if path.name.startswith("99_"):
            continue
        text = path.read_text(encoding="utf-8-sig")
        for st in state_ownership.parse_state_text(text):
            m = re.search(rf"\b{re.escape(st.key)}\s*=\s*\{{", text)
            close = state_ownership._match_brace(text, text.index("{", m.start()))
            body = text[m.end():close]
            im = re.search(r"\bimpassable\s*=\s*\{([^}]*)\}", body)
            imp = {t.upper().replace("X", "x", 1) for t in re.findall(r"x[0-9A-Fa-f]{6}", im.group(1))} if im else set()
            out.append((st.key, st.provinces, imp))
    return out


def culture_graphics(directory: Path) -> dict[str, str]:
    """``{culture id: graphics value}`` from ``common/cultures/*.txt`` (top-level blocks, ``#`` comments stripped)."""
    out: dict[str, str] = {}
    for path in sorted(Path(directory).glob("*.txt")):
        text = "\n".join(line.split("#", 1)[0] for line in path.read_text(encoding="utf-8-sig").splitlines())
        depth = 0
        for m in re.finditer(r"[{}]|\b(\w+)\s*=\s*\{|\bgraphics\s*=\s*(\w+)", text):
            tok = m.group(0)
            if tok == "}":
                depth -= 1
            elif tok == "{":
                depth += 1
            elif m.group(1):
                if depth == 0:
                    cur = m.group(1)
                depth += 1
            elif m.group(2) and depth == 1:
                out[cur] = m.group(2)
    return out


def state_family(key: str, homelands: dict, graphics: dict) -> str:
    """Building family of a state: its first homeland culture's graphics value (module docstring)."""
    row = homelands.get(key, {}).get("cultures") or []
    if not row:
        return DEFAULT_FAMILY
    return GRAPHICS_FAMILY.get(graphics.get(row[0], ""), DEFAULT_FAMILY)


def load_land_and_family():
    """``(land bool [H,W], fam uint8 [H,W], {family: state count}, disagreement dict)``."""
    states = parse_states_with_impassable(STATE_REGIONS_DIR)
    homelands = json.loads(HOMELANDS.read_text(encoding="utf-8"))["states"]
    graphics = culture_graphics(CULTURES_DIR)
    fam_index = {f: i for i, f in enumerate(FAMILY_ORDER)}
    tok, fam_of_tok = [], []
    counts = {f: 0 for f in FAMILY_ORDER}
    for key, provs, imp in states:
        fam = state_family(key, homelands, graphics)
        counts[fam] += 1
        for p in provs:
            if p not in imp:
                tok.append(int(p[1:], 16))
                fam_of_tok.append(fam_index[fam])
    tok = np.array(tok, np.uint32)
    order = np.argsort(tok, kind="stable")
    tok_sorted, fam_sorted = tok[order], np.array(fam_of_tok, np.uint8)[order]
    if len(np.unique(tok_sorted)) != len(tok_sorted):
        raise SystemExit("a province is listed in two land states")
    prov = np.asarray(Image.open(PROVINCES_PNG).convert("RGB"))
    if prov.shape[:2] != (H, W):
        raise SystemExit(f"{PROVINCES_PNG.name}: expected {W}x{H}, got {prov.shape[1]}x{prov.shape[0]}")
    fam = np.full((H, W), FAMILY_NONE, np.uint8)
    for y0 in range(0, H, BLOCK):
        blk = prov[y0:y0 + BLOCK].astype(np.uint32)
        packed = (blk[..., 0] << 16) | (blk[..., 1] << 8) | blk[..., 2]
        pos = np.searchsorted(tok_sorted, packed)
        pos[pos >= len(tok_sorted)] = 0
        hit = tok_sorted[pos] == packed
        fam[y0:y0 + BLOCK] = np.where(hit, fam_sorted[pos], FAMILY_NONE)
    del prov
    land = fam != FAMILY_NONE
    sea = np.asarray(Image.open(DERIVED_DIR / "land_sea_mask.png"), dtype=bool)
    lake = np.asarray(Image.open(DERIVED_DIR / "lake_mask.png"), dtype=bool)
    ref = sea & ~lake
    dis = {"state_land_not_in_mask": int((land & ~ref).sum()), "mask_land_not_in_state": int((ref & ~land).sum()),
           "state_land_total": int(land.sum())}
    return land, fam, counts, dis


def read_mask(path: Path, shape: tuple[int, int], *, hint: str = "") -> np.ndarray:
    """A mode-``L`` PNG of exactly ``shape``; a missing file, other mode or LFS pointer is a ``SystemExit``."""
    if not path.exists():
        raise SystemExit(f"{path}: missing{hint}")
    try:
        with Image.open(path) as im:
            if im.mode != "L" or im.size != (shape[1], shape[0]):
                raise SystemExit(f"{path}: expected an {shape[1]}x{shape[0]} mode L PNG, got {im.size[0]}x{im.size[1]} "
                                 f"mode {im.mode}{hint}")
            return np.asarray(im, dtype=np.uint8)
    except Image.UnidentifiedImageError:
        raise SystemExit(f"{path}: not a PNG ({path.stat().st_size} bytes); a Git LFS pointer? run `git lfs pull`{hint}") from None


def load_woodland(terrain_dir: Path) -> np.ndarray:
    hint = " (the woodland masks come from #6617's generate_terrain_masks.py; pass --terrain-dir DIR)"
    acc = np.zeros((H, W), np.uint16)
    for n in (1, 2, 3):
        acc += read_mask(terrain_dir / f"mask_woodlands_0{n}.png", (H, W), hint=hint)
    return acc


def load_locators() -> dict:
    from generate_map_locators import compute
    return compute()


def load_inputs(terrain_dir: Path) -> Inputs:
    log("loading inputs")
    t = time.time()
    land, fam, counts, dis = load_land_and_family()
    log(f"  land (state provinces minus impassable): {dis['state_land_total']:,} px; "
        f"{dis['state_land_not_in_mask']:,} px of it are sea or lake on land_sea_mask/lake_mask, "
        f"{dis['mask_land_not_in_state']:,} px of mask land are in no land state; {time.time() - t:.0f}s")
    log("  states per building family: " + ", ".join(f"{f} {counts[f]}" for f in FAMILY_ORDER))
    arable = np.asarray(Image.open(DERIVED_DIR / "arable_heatmap.png"), dtype=np.float32) / 65535.0
    if arable.shape != (H, W):
        raise SystemExit(f"arable_heatmap.png: expected {W}x{H}, got {arable.shape[1]}x{arable.shape[0]}")
    wood = load_woodland(terrain_dir)
    try:
        src = str(terrain_dir.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        src = terrain_dir.name
    return Inputs(land=land, fam=fam, arable=arable, wood=wood, locators=load_locators(),
                  wood_source=f"{src}/mask_woodlands_0[123].png", family_states=counts)


# --------------------------------------------------------------------------- masks

def window(cx: float, cy: float, radius: float, shape: tuple[int, int]):
    """Row/column slices of the canvas around ``(cx, cy)`` (pixel-centre coordinates) and their centre grids."""
    h, w = shape
    x0, x1 = max(int(np.floor(cx - radius)), 0), min(int(np.ceil(cx + radius)) + 1, w)
    y0, y1 = max(int(np.floor(cy - radius)), 0), min(int(np.ceil(cy + radius)) + 1, h)
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    return slice(y0, y1), slice(x0, x1), xx + 0.5 - cx, yy + 0.5 - cy


def hubs_xy(inp: Inputs, kinds, height: int) -> list[tuple[float, float]]:
    """Hub positions as canvas ``(x, y)`` in pixel-centre coordinates, in locator order."""
    out = []
    for k in kinds:
        for _sid, x, z in inp.locators.get(k, []):
            out.append((float(x), float(height - z)))
    return out


def stamp_discs(field: np.ndarray, centres, value: float, radii: tuple[float, float]) -> None:
    """Max ``value * (1 - smoothstep(r, *radii))`` into ``field`` around every centre (in place)."""
    for cx, cy in centres:
        sy, sx, dx, dy = window(cx, cy, radii[1], field.shape)
        r = np.hypot(dx, dy)
        np.maximum(field[sy, sx], (value * (1.0 - smoothstep(r, *radii))).astype(np.float32), out=field[sy, sx])


def farmland_mask(inp: Inputs) -> np.ndarray:
    a = inp.arable
    on_land = a[inp.land]
    t1, t2 = (float(np.percentile(on_land, p)) for p in FARM_PERCENTILES)
    del on_land
    if t2 <= t1:
        t2 = t1 + 1e-6
    f = (255.0 * smoothstep(a, t1, t2)).astype(np.float32)
    f = ndimage.gaussian_filter(f, FARM_BLUR)
    stamp_discs(f, hubs_xy(inp, FARM_HUBS, inp.land.shape[0]), 255.0, FARM_DISC)
    return np.rint(np.where(inp.land, f, 0.0)).astype(np.uint8)


def forestry_mask(inp: Inputs) -> np.ndarray:
    w = ndimage.gaussian_filter(inp.wood.astype(np.float32), FOREST_BLUR)
    f = (FOREST_VALUE * smoothstep(w, *FOREST_RAMP)).astype(np.float32)
    del w
    stamp_discs(f, hubs_xy(inp, ("wood",), inp.land.shape[0]), float(FOREST_DISC_VALUE), FOREST_DISC)
    return np.rint(np.where(inp.land, f, 0.0)).astype(np.uint8)


def mining_mask(inp: Inputs, seed: int) -> np.ndarray:
    """A hollow ring per mine hub; each ring's radius wobbles by a seeded sum of angular harmonics."""
    rng = np.random.default_rng([seed, MINE_SEED_STREAM])
    f = np.zeros(inp.land.shape, np.float32)
    in0, in1, out0, out1 = MINE_RING
    reach = out1 * (1.0 + MINE_WOBBLE) + 1.0
    for cx, cy in hubs_xy(inp, ("mine",), inp.land.shape[0]):
        amp = rng.random(MINE_HARMONICS).astype(np.float32) / np.arange(1, MINE_HARMONICS + 1, dtype=np.float32)
        phase = rng.random(MINE_HARMONICS).astype(np.float32) * 2.0 * np.pi
        amp = amp / max(float(amp.sum()), 1e-6)          # |wobble| <= 1
        sy, sx, dx, dy = window(cx, cy, reach, f.shape)
        theta = np.arctan2(dy, dx)
        wob = np.zeros_like(theta)
        for k in range(MINE_HARMONICS):
            wob += amp[k] * np.cos((k + 1) * theta + phase[k])
        r = np.hypot(dx, dy) / (1.0 + MINE_WOBBLE * wob)
        ring = MINE_VALUE * smoothstep(r, in0, in1) * (1.0 - smoothstep(r, out0, out1))
        np.maximum(f[sy, sx], ring.astype(np.float32), out=f[sy, sx])
    return np.rint(np.where(inp.land, f, 0.0)).astype(np.uint8)


def build_masks(inp: Inputs, seed: int = map_config.SEED) -> dict[str, np.ndarray]:
    t = time.time()
    masks = {"farmland": farmland_mask(inp), "forestry": forestry_mask(inp), "mining": mining_mask(inp, seed)}
    log(f"  masks built ({time.time() - t:.0f}s)")
    return masks


def mask_stats(masks: dict[str, np.ndarray], land: np.ndarray) -> list[str]:
    n_land = max(int(land.sum()), 1)
    out = []
    for k in KINDS:
        nz = masks[k] > 0
        med = float(np.median(masks[k][nz])) if nz.any() else 0.0
        cov = 100.0 * float(nz.sum()) / n_land
        vcov, vmed = VANILLA_STATS[k]
        out.append(f"  {k:9s} non-zero on {cov:5.1f}% of land (vanilla {vcov}%)  median {med:5.0f} (vanilla {vmed})  "
                   f"max {int(masks[k].max())}  255 on {100.0 * float((masks[k] == 255).sum()) / max(int(nz.sum()), 1):.1f}% of non-zero")
    return out


# --------------------------------------------------------------------------- placements and mesh files

@dataclass
class PlacedObject:
    """One mesh's rows: ``x, z, qy, qw, keep`` (float64 / bool arrays), in placement order."""
    name: str
    mesh: str
    layer: str
    x: np.ndarray
    z: np.ndarray
    qy: np.ndarray
    qw: np.ndarray
    keep: np.ndarray


def place_file(mask: np.ndarray, fam: np.ndarray, family: str, kind: str, n: int, seed: int) -> list[PlacedObject]:
    """Draw the instances of one generator file; object ``i`` takes mesh ``i`` of the spec."""
    max_density, meshes = file_spec(family, kind, n)
    h = mask.shape[0]
    fi = FAMILY_ORDER.index(family)
    rng = np.random.default_rng([seed, KIND_INDEX[kind], fi, n])
    weights = np.array([w for _m, w in meshes], np.float64)
    cum = np.cumsum(weights) / weights.sum()
    cum[-1] = 1.0
    thresh = int(np.ceil(KEEP_FRACTION * KIND_PEAK[kind]))
    floor = DENSITY_FLOOR[kind]
    xs_all, zs_all, qy_all, qw_all, keep_all, obj_all = [], [], [], [], [], []
    for y0 in range(0, h, BLOCK):
        mb, fb = mask[y0:y0 + BLOCK], fam[y0:y0 + BLOCK]
        ys, xs = np.nonzero((fb == fi) & (mb > 0))
        if not len(ys):
            continue
        m = mb[ys, xs]
        dens = (max_density * weights.sum() * DENSITY_SCALE[kind]
                * (floor + (1.0 - floor) * (m.astype(np.float64) / 255.0)))
        acc = rng.random(len(ys)) < dens
        k = int(acc.sum())
        jitter = rng.random((k, 2))
        pick = rng.random(k)
        yaw = rng.random(k) * (2.0 * np.pi)
        ys, xs, m = ys[acc], xs[acc], m[acc]
        xs_all.append(xs + jitter[:, 0])
        zs_all.append(h - (y0 + ys + jitter[:, 1]))
        qy_all.append(np.sin(yaw / 2.0))
        qw_all.append(np.cos(yaw / 2.0))
        keep_all.append(m >= thresh)
        obj_all.append(np.minimum(np.searchsorted(cum, pick, side="right"), len(meshes) - 1))
    cat = lambda parts, dt: np.concatenate(parts) if parts else np.zeros(0, dt)  # noqa: E731
    x, z, qy, qw = cat(xs_all, np.float64), cat(zs_all, np.float64), cat(qy_all, np.float64), cat(qw_all, np.float64)
    keep, obj = cat(keep_all, bool), cat(obj_all, np.int64)
    out = []
    for i, (mesh, _w) in enumerate(meshes):
        sel = obj == i
        out.append(PlacedObject(f"{file_stem(family, kind, n)}_{i}", mesh, KIND_LAYER[kind],
                                x[sel], z[sel], qy[sel], qw[sel], keep[sel]))
    return out


BLANK_COMMENT = ("# Blank: no state uses this building family, so vanilla's Earth positions for it are overridden\n"
                 "# by this object-less file (board #11536). Generated by mapgen/generate_dynamic_masks.py - do not hand-edit.\n")
USED_COMMENT = ("# Generated by mapgen/generate_dynamic_masks.py (board #11536) - do not hand-edit.\n"
                "# Placements drawn from gfx/map/masks/mask_dynamic_*.png over the states of one building family;\n"
                "# scale 1 = at or above half the mask's peak, scale 0 = the fringe (vanilla's layout).\n")


def object_text(o: PlacedObject) -> str:
    keep = o.keep
    if EMIT_ZERO_SCALE:
        sel = np.ones(len(keep), bool)
    else:
        sel = keep
    n = int(sel.sum())
    if n == 0:
        return ""
    rows = []
    for x, z, qy, qw, k in zip(o.x[sel], o.z[sel], o.qy[sel], o.qw[sel], keep[sel]):
        s = "1.000000" if k else "0.000000"
        rows.append(f"{x:.6f} 0.000000 {z:.6f} 0.000000 {qy:.6f} 0.000000 {qw:.6f} {s} {s} {s}\n")
    return (f"object={{\n\tname=\"{o.name}\"\n\tclamp_to_water_level=no\n\trender_under_water=no\n"
            f"\tgenerated_content=yes\n\tlayer=\"{o.layer}\"\n\tpdxmesh=\"{o.mesh}\"\n\tcount={n}\n"
            f"\ttransform=\"{''.join(rows)}\"}}\n")


def file_bytes(objects: list[PlacedObject] | None) -> bytes:
    """A mesh file: the BOM, a provenance comment, then every non-empty object (``None`` = blank file)."""
    if objects is None:
        text = BLANK_COMMENT
    else:
        body = "".join(object_text(o) for o in objects)
        text = USED_COMMENT + body if body else BLANK_COMMENT
    return b"\xef\xbb\xbf" + text.encode("utf-8")


def build_meshes(masks: dict[str, np.ndarray], fam: np.ndarray, seed: int = map_config.SEED):
    """``({file name: bytes}, {(family, kind, n): [PlacedObject]}, {file name: instance rows})``.

    Pure in the three masks, the family raster and ``seed``: the full write and ``--from-masks`` both
    come through here. A family no pixel of ``fam`` belongs to, and every DLC family, gets a blank file.
    """
    present = set(np.unique(fam).tolist())
    files, placed, counts = {}, {}, {}
    t = time.time()
    for family, kind, n in all_files():
        name = file_stem(family, kind, n) + ".txt"
        if family in FAMILY_ORDER and FAMILY_ORDER.index(family) in present:
            objs = place_file(masks[kind], fam, family, kind, n, seed)
            placed[(family, kind, n)] = objs
            files[name] = file_bytes(objs)
            counts[name] = (sum(len(o.x) for o in objs), sum(int(o.keep.sum()) for o in objs))
        else:
            files[name] = file_bytes(None)
            counts[name] = (0, 0)
    log(f"  placements drawn ({time.time() - t:.0f}s)")
    return files, placed, counts


def mesh_report(counts: dict[str, tuple[int, int]], files: dict[str, bytes]) -> list[str]:
    out = []
    for name in sorted(counts):
        n, kept = counts[name]
        out.append(f"  {name:62s} {n:>8,} rows ({kept:,} at scale 1)  {len(files[name]) / 1e6:7.2f} MB")
    out.append(f"  total {sum(len(b) for b in files.values()) / 1e6:.1f} MB in {len(files)} files")
    return out


def write_masks(out: Path, masks: dict[str, np.ndarray]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for k in KINDS:
        Image.fromarray(masks[k], "L").save(out / MASK_NAME[k])
    log(f"wrote {len(KINDS)} masks to {out}")


def write_meshes(out: Path, files: dict[str, bytes]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)
    log(f"wrote {len(files)} mesh files to {out}")


def read_masks(directory: Path) -> dict[str, np.ndarray]:
    return {k: read_mask(directory / MASK_NAME[k], (H, W), hint=" (run without --from-masks to generate it)") for k in KINDS}


# --------------------------------------------------------------------------- vanilla verification

def vanilla_headers(path: Path) -> list[dict]:
    """``[{name, pdxmesh, layer, flags..., count}]`` of every object in a generated vanilla file."""
    text = path.read_text(encoding="utf-8-sig")
    out = []
    for block in re.split(r"\bobject=\{", text)[1:]:
        head = block.split("transform", 1)[0]
        d = {k: v.strip('"') for k, v in re.findall(r'(\w+)=("[^"]*"|[^\s"]+)', head)}
        d["rows"] = None
        tm = re.search(r'transform="(.*?)"', block, re.S)
        if tm:
            d["rows"] = np.array(tm.group(1).split(), np.float64).reshape(-1, 10)
        out.append(d)
    return out


def vanilla_check(vanilla_root: Path) -> list[str]:
    """Verify :data:`FAMILIES` and the file set against the vanilla install and its DLC (problems as text)."""
    problems: list[str] = []
    base = vanilla_root / "gfx" / "map" / "map_object_data" / "generated"
    dlc_dirs = sorted(vanilla_root.glob("dlc/*/gfx/map/map_object_data/generated"))
    pat = "*_dynamic_*_objects_generator_*.txt"
    vanilla_files: dict[str, list[Path]] = {}
    for d in [base] + dlc_dirs:
        for p in sorted(d.glob(pat)):
            vanilla_files.setdefault(p.name, []).append(p)
    ours = {file_stem(*f) + ".txt" for f in all_files()}
    if set(vanilla_files) != ours:
        problems.append("vanilla dynamic generator files differ from ours: only in vanilla "
                        f"{sorted(set(vanilla_files) - ours)}, only ours {sorted(ours - set(vanilla_files))}")
    # content-source generators: max_density
    gens: dict[str, float] = {}
    for src in [vanilla_root / "content_source" / "map_objects" / "generators"] + sorted(
            vanilla_root.glob("dlc/*/content_source/map_objects/generators")):
        for p in sorted(src.glob("*_generator.txt")):
            t = p.read_text(encoding="utf-8-sig")
            for m in re.finditer(r"(\w+_objects_generator_\d+)=\{(.*?)\n\}", t, re.S):
                md = re.search(r"max_density\s*=\s*([\d.]+)", m.group(2))
                if md:
                    gens.setdefault(m.group(1), float(md.group(1)))
    # mesh names that exist without any DLC
    meshes: set[str] = set()
    for p in (vanilla_root / "gfx").rglob("*.asset"):
        meshes.update(re.findall(r'pdxmesh\s*=\s*\{\s*name\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8-sig", errors="replace")))
    scales: dict[float, int] = {}
    intermediate_in: set[str] = set()
    for name, refs in sorted(vanilla_files.items()):
        for p in refs:
            for h in vanilla_headers(p):
                if h["rows"] is not None:
                    for v, c in zip(*np.unique(np.round(h["rows"][:, 7], 3), return_counts=True)):
                        scales[float(v)] = scales.get(float(v), 0) + int(c)
                        if float(v) not in (0.0, 1.0):
                            intermediate_in.add(f"{'dlc' if 'dlc' in p.parts[len(vanilla_root.parts):][:1] else 'base'}:{name}")
    for family, kind, n in all_files():
        name = file_stem(family, kind, n) + ".txt"
        refs = vanilla_files.get(name, [])
        spec = file_spec(family, kind, n)
        if not refs or spec is None:
            continue
        # the DLC's file is the live one when present (DLC004 replaces european_*), else the base game's
        hdr = vanilla_headers(refs[-1])
        max_density, mesh_list = spec
        if [h["name"] for h in hdr] != [f"{file_stem(family, kind, n)}_{i}" for i in range(len(mesh_list))]:
            problems.append(f"{name}: object names differ from vanilla's {[h['name'] for h in hdr]}")
            continue
        for h, (mesh, _w) in zip(hdr, mesh_list):
            if h["pdxmesh"] != mesh:
                problems.append(f"{name}: {h['name']} mesh {mesh!r}, vanilla {h['pdxmesh']!r}")
            if (h["layer"], h["clamp_to_water_level"], h["render_under_water"], h["generated_content"]) != (
                    KIND_LAYER[kind], "no", "no", "yes"):
                problems.append(f"{name}: {h['name']} layer/flags differ from vanilla's")
            if mesh not in meshes:
                problems.append(f"{name}: mesh {mesh!r} is defined by no base-game asset (needs a DLC?)")
        gname = f"{file_stem(family, kind, n)}"
        if gname in gens and abs(gens[gname] - max_density) > 1e-9:
            problems.append(f"{name}: max_density {max_density}, vanilla generator {gens[gname]}")
        counted = vanilla_headers(refs[0])      # the base game's file carries the row counts
        if all(h["rows"] is not None for h in counted) and len(counted) == len(mesh_list):
            tot = sum(len(h["rows"]) for h in counted)
            wsum = sum(w for _m, w in mesh_list)
            for h, (mesh, w) in zip(counted, mesh_list):
                share, want = len(h["rows"]) / max(tot, 1), w / wsum
                if abs(share - want) > 0.03 and tot > 1000:
                    problems.append(f"{name}: {h['name']} weight share {want:.3f}, vanilla row share {share:.3f}")
    inter = {v: c for v, c in scales.items() if v not in (0.0, 1.0)}
    log(f"  vanilla scale column over {sum(scales.values()):,} rows: 0 -> {scales.get(0.0, 0):,}, 1 -> {scales.get(1.0, 0):,}, "
        f"intermediate -> {sum(inter.values()):,}" + (f" (values {min(inter):.3f}..{max(inter):.3f}, only in {sorted(intermediate_in)})"
                                                    if inter else ""))
    mf = vanilla_root / "gfx" / "map" / "masks" / "manifest.json"
    want = {"mask_dynamic_mining": "mask_dynamic_mining.png", "mask_dynamic_forestry": "mask_dynamic_forestry.png",
            "mask_dynamic_farmland": "mask_dynamic_farmland.png"}
    if mf.exists():
        got = {m["key"]: m["filename"] for m in json.loads(mf.read_text(encoding="utf-8-sig"))["masks"]}
        if got != want:
            problems.append(f"vanilla masks/manifest.json lists {got}, not exactly our three keys")
    else:
        problems.append("vanilla gfx/map/masks/manifest.json not found")
    return problems


# --------------------------------------------------------------------------- check

def check(terrain_dir: Path, mask_dir: Path, mesh_dir: Path) -> int:
    t = time.time()
    problems: list[str] = []
    try:
        from measure_vanilla_frame import VANILLA_ROOT
    except Exception:  # pragma: no cover - the module is part of this repo
        VANILLA_ROOT = None
    if VANILLA_ROOT is not None and (VANILLA_ROOT / "gfx").is_dir():
        problems += vanilla_check(VANILLA_ROOT)
    else:
        log("  vanilla install not found; FAMILIES, the file set and the manifest were not checked")
    inp = load_inputs(terrain_dir)
    masks = build_masks(inp)
    for line in mask_stats(masks, inp.land):
        log(line)
    for k in KINDS:
        p = mask_dir / MASK_NAME[k]
        try:
            disk = read_mask(p, masks[k].shape)
        except SystemExit as e:
            problems.append(str(e))
            continue
        if not np.array_equal(disk, masks[k]):
            problems.append(f"{p.relative_to(REPO_ROOT)}: stale (differs from a fresh generation)")
    files, _placed, counts = build_meshes(masks, inp.fam)
    for name, data in files.items():
        p = mesh_dir / name
        if not p.exists():
            problems.append(f"{p.relative_to(REPO_ROOT)}: missing (run --from-masks)")
        elif p.read_bytes() != data:
            problems.append(f"{p.relative_to(REPO_ROOT)}: stale (differs from a fresh generation; run --from-masks)")
    if problems:
        print("\n".join(problems))
        print("run: mapgen/.venv/Scripts/python.exe mapgen/generate_dynamic_masks.py "
              "(then --render and have the preview accepted again)")
        return 1
    log(f"dynamic masks and mesh files current ({time.time() - t:.0f}s)")
    return 0


# --------------------------------------------------------------------------- render

FAMILY_RGB = {"european": (255, 235, 60), "asian": (255, 80, 255), "arabic": (255, 150, 30),
              "african": (60, 255, 255), "latin": (255, 255, 255)}
KIND_RGB = {"farmland": (230, 40, 40), "forestry": (40, 190, 60), "mining": (60, 110, 255)}


def load_elevation() -> np.ndarray:
    """Canvas-resolution elevation in metres (float32), heightmap 2x2 block mean."""
    hm = np.asarray(Image.open(REPO_ROOT / "map_data" / "heightmap.png"))
    out = np.empty((H, W), np.float32)
    for y0 in range(0, H, BLOCK):
        y1 = min(y0 + BLOCK, H)
        blk = hm[y0 * 2:y1 * 2].astype(np.float32).reshape(y1 - y0, 2, W, 2).mean(axis=(1, 3))
        out[y0:y1] = (blk - map_config.HEIGHT_SEA_LEVEL) / map_config.HEIGHT_UNITS_PER_METRE
    return out


def base_rows(elev, land, y0, y1) -> np.ndarray:
    """Relief-shaded grey on land, dark blue-grey sea, for canvas rows y0..y1."""
    lo, hi = max(y0 - 1, 0), min(y1 + 1, elev.shape[0])
    e = elev[lo:hi]
    gy = np.gradient(e, axis=0)[y0 - lo:y0 - lo + (y1 - y0)]
    gx = np.gradient(e[y0 - lo:y0 - lo + (y1 - y0)], axis=1)
    shade = 150.0 * (1.0 + np.clip((gx * 0.7 + gy * 0.7) / 120.0, -0.45, 0.45)) * 0.75
    grey = np.repeat(shade[..., None], 3, axis=2)
    return np.where(land[y0:y1, :, None], np.clip(grey, 40, 230), np.array([18, 26, 40], np.float32))


def overlay_rows(base: np.ndarray, masks: dict[str, np.ndarray], y0: int, y1: int, x0: int = 0, x1: int | None = None) -> np.ndarray:
    col = base.astype(np.float32)
    for k in KINDS:
        a = (masks[k][y0:y1, x0:x1].astype(np.float32) / KIND_PEAK[k])[..., None] * 0.75
        col = col * (1.0 - a) + np.array(KIND_RGB[k], np.float32) * a
    return np.clip(col, 0, 255)


def caption(im: Image.Image, lines: list[str]) -> Image.Image:
    d = ImageDraw.Draw(im)
    h = 14 * len(lines) + 8
    d.rectangle([0, 0, max(520, max(len(s) for s in lines) * 7 + 12), h], fill=(0, 0, 0))
    for i, s in enumerate(lines):
        d.text((6, 4 + 14 * i), s, fill=(255, 255, 255))
    return im


def render(inp: Inputs, masks: dict[str, np.ndarray], placed: dict, tag: str = "") -> None:
    h, w = inp.land.shape
    sfx = f"_{tag}" if tag else ""
    elev = load_elevation()
    land = inp.land
    prev = np.zeros((h // 2, w // 2, 3), np.uint8)
    for y0 in range(0, h, BLOCK):
        y1 = min(y0 + BLOCK, h)
        col = overlay_rows(base_rows(elev, land, y0, y1), masks, y0, y1)
        prev[y0 // 2:y1 // 2] = col.reshape((y1 - y0) // 2, 2, w // 2, 2, 3).mean(axis=(1, 3)).astype(np.uint8)
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["red = farmland mask, green = forestry mask, blue = mining mask; land in relief grey, sea dark",
             f"woodland input: {inp.wood_source}"]
    p1 = SCRATCH_DIR / f"dynamic_masks_preview{sfx}.png"
    caption(Image.fromarray(prev), lines).save(p1)
    x0, cy0, x1, cy1 = OLDWORLD_CROP
    crop = overlay_rows(base_rows(elev, land, cy0, cy1)[:, x0:x1], masks, cy0, cy1, x0, x1).astype(np.uint8)
    n_dots = 0
    for (family, _kind, _n), objs in placed.items():
        rgb = np.array(FAMILY_RGB[family], np.uint8)
        for o in objs:
            xs = np.floor(o.x[o.keep]).astype(int) - x0
            ys = np.floor(h - o.z[o.keep]).astype(int) - cy0
            ok = (xs >= 0) & (xs < x1 - x0) & (ys >= 0) & (ys < cy1 - cy0)
            crop[ys[ok], xs[ok]] = rgb
            n_dots += int(ok.sum())
    for kind in ("city", "farm", "mine", "port", "wood"):
        for _sid, x, z in inp.locators.get(kind, []):
            cx, cy = int(x) - x0, int(h - z) - cy0
            for d in range(-3, 4):
                for px, py in ((cx + d, cy), (cx, cy + d)):
                    if 0 <= px < crop.shape[1] and 0 <= py < crop.shape[0]:
                        crop[py, px] = (255, 255, 255)
    lines2 = lines + [f"dots = scale-1 instances ({n_dots:,} here) coloured by family: european yellow, asian magenta, "
                      "arabic orange, african cyan, latin white; white crosses = hubs"]
    p2 = SCRATCH_DIR / f"dynamic_masks_preview_oldworld{sfx}.png"
    caption(Image.fromarray(crop), lines2).save(p2)
    log(f"preview: {p1}\npreview: {p2}")


# --------------------------------------------------------------------------- selftest

def synthetic_inputs(h: int = 452, w: int = 1024) -> Inputs:
    """A 1/8-scale world: an ellipse of land in two states (european west, asian east), a lake, a sea strip
    through the middle that no state owns, hubs of every type and woodland on the east."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ell = ((xx - w / 2) / (w * 0.42)) ** 2 + ((yy - h / 2) / (h * 0.42)) ** 2 < 1.0
    lake = ((xx - w * 0.30) ** 2 + (yy - h * 0.5) ** 2) < (h * 0.06) ** 2
    impassable = (xx > w * 0.62) & (xx < w * 0.66) & (yy < h * 0.5)
    land = ell & ~lake & ~impassable
    fam = np.full((h, w), FAMILY_NONE, np.uint8)
    fam[land & (xx < w / 2)] = FAMILY_ORDER.index("european")
    fam[land & (xx >= w / 2)] = FAMILY_ORDER.index("asian")
    arable = np.where(land, np.clip(xx / w, 0, 1) * 0.9 + 0.1 * np.sin(yy / 17.0) ** 2, 0.0).astype(np.float32)
    wood = np.where(land & (xx > w * 0.5), 200, 0).astype(np.uint16)
    loc = {"city": [(1, w * 0.30 + 0.5, h - (h * 0.30 + 0.5))], "farm": [(1, w * 0.35 + 0.5, h - (h * 0.60 + 0.5))],
           "port": [(2, w * 0.70 + 0.5, h - (h * 0.80 + 0.5))], "mine": [(1, w * 0.42 + 0.5, h - (h * 0.40 + 0.5)),
                                                                          (2, w * 0.58 + 0.5, h - (h * 0.30 + 0.5))],
           "wood": [(2, w * 0.75 + 0.5, h - (h * 0.50 + 0.5))]}
    return Inputs(land=land, fam=fam, arable=arable, wood=wood, locators=loc, wood_source="synthetic")


def parse_mesh_file(data: bytes) -> list[dict]:
    """Strict parse of our own output: BOM, LF, objects with count = rows, rows of ten floats."""
    assert data[:3] == b"\xef\xbb\xbf" and b"\r" not in data, "BOM / LF"
    text = data[3:].decode("utf-8")
    out = []
    for block in re.split(r"(?m)^object=\{\n", text)[1:]:
        m = re.match(r'\tname="([^"]+)"\n\tclamp_to_water_level=no\n\trender_under_water=no\n\tgenerated_content=yes\n'
                     r'\tlayer="(\w+)"\n\tpdxmesh="(\w+)"\n\tcount=(\d+)\n\ttransform="(.*)"\}\n\Z', block, re.S)
        assert m, f"object block does not match vanilla's layout: {block[:200]!r}"
        body = m.group(5)
        assert body.endswith("\n"), "last row is not newline-terminated"
        rows = [r.split(" ") for r in body[:-1].split("\n")]
        assert len(rows) == int(m.group(4)) and all(len(r) == 10 for r in rows), "count != rows of ten floats"
        out.append({"name": m.group(1), "layer": m.group(2), "mesh": m.group(3),
                    "rows": np.array(rows, np.float64)})
    return out


def selftest() -> int:
    global EMIT_ZERO_SCALE
    t = time.time()
    inp = synthetic_inputs()
    h, w = inp.land.shape
    masks = build_masks(inp, map_config.SEED)
    masks2 = build_masks(inp, map_config.SEED)
    for k in KINDS:
        assert np.array_equal(masks[k], masks2[k]), f"{k} mask not deterministic"
        assert not masks[k][~inp.land].any(), f"{k} mask is non-zero outside land"
        assert masks[k].max() > 0, f"{k} mask is empty"
    assert masks["farmland"].max() == 255 and masks["forestry"].max() <= FOREST_VALUE and masks["mining"].max() <= MINE_VALUE
    # farm disc at a farm hub: 255 within 8 px, fading to the arable field beyond 14 px
    cx, cy = int(w * 0.35), int(h * 0.60)
    assert masks["farmland"][cy, cx] == 255 and masks["farmland"][cy, cx + 7] == 255
    # a hollow ring at a mine hub: zero at the centre, strong on the ring, zero past the outer radius (wobble <= 25%)
    mx, my = int(w * 0.42), int(h * 0.40)
    assert masks["mining"][my, mx] == 0, "mine ring is not hollow"
    assert masks["mining"][my - 12:my + 13, mx - 12:mx + 13].max() >= 0.9 * MINE_VALUE, "mine ring is weak"
    ring = masks["mining"][my - 30:my + 31, mx - 30:mx + 31]
    yy, xx = np.mgrid[-30:31, -30:31]
    assert not ring[np.hypot(xx, yy) > MINE_RING[3] * (1 + MINE_WOBBLE) + 2].any(), "mine ring reaches past its outer radius"
    # the wobble is a pure function of the seed: different seed, different ring
    assert not np.array_equal(mining_mask(inp, map_config.SEED + 1), masks["mining"]), "ring wobble ignores the seed"
    # forestry: woodland on the east, never in the (state-less) west beyond the wood disc's reach
    assert masks["forestry"][int(h * 0.5), int(w * 0.75)] > 0 and not masks["forestry"][:, : w // 4].any()
    # placements, both scale modes
    for emit in (True, False):
        EMIT_ZERO_SCALE = emit
        files, placed, counts = build_meshes(masks, inp.fam)
        files2, _p2, _c2 = build_meshes(masks2, inp.fam)
        assert files == files2, "mesh files not deterministic"
        assert set(files) == {file_stem(*f) + ".txt" for f in all_files()} and len(files) == 24
        per_kind_pixels: dict[str, dict[tuple, str]] = {k: {} for k in KINDS}
        for name, data in files.items():
            fam_name = name.split("_dynamic_")[0]
            used = fam_name in ("european", "asian")
            if not used:
                assert data == b"\xef\xbb\xbf" + BLANK_COMMENT.encode() and b"object=" not in data, name
                continue
            objs = parse_mesh_file(data)
            kind = re.search(r"dynamic_(\w+?)_objects", name).group(1)
            fi = FAMILY_ORDER.index(fam_name)
            for o in objs:
                r = o["rows"]
                assert set(np.unique(r[:, 7])) <= {0.0, 1.0} and (r[:, 7:] == r[:, 7:8]).all()
                assert (r[:, [1, 3, 5]] == 0).all()
                if not emit:
                    assert (r[:, 7] == 1).all(), "scale-0 rows written with EMIT_ZERO_SCALE off"
                ix, iy = np.floor(r[:, 0]).astype(int), np.floor(h - r[:, 2]).astype(int)
                assert ((ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)).all()
                assert (inp.fam[iy, ix] == fi).all(), f"{name}: an instance sits outside its family's states"
                assert inp.land[iy, ix].all(), f"{name}: an instance sits off land"
                assert (masks[kind][iy, ix] > 0).all(), f"{name}: an instance sits on a zero mask"
                kept = r[:, 7] == 1
                assert (masks[kind][iy[kept], ix[kept]] >= np.ceil(KEEP_FRACTION * KIND_PEAK[kind])).all()
                for px in zip(ix.tolist(), iy.tolist()):
                    prev = per_kind_pixels[kind].setdefault(px, fam_name)
                    assert prev == fam_name, f"pixel {px} hosts {prev} and {fam_name} instances"
        assert sum(c[0] for c in counts.values()) > 100, "selftest world drew almost nothing"
    EMIT_ZERO_SCALE = True
    # --from-masks equivalence: PNG round trip, then the same files
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        write_masks(d, masks)
        back = {k: read_mask(d / MASK_NAME[k], (h, w)) for k in KINDS}
        assert all(np.array_equal(back[k], masks[k]) for k in KINDS), "mask PNG round trip differs"
        files3, _p3, _c3 = build_meshes(back, inp.fam)
        assert files3 == build_meshes(masks, inp.fam)[0], "--from-masks differs from the full run"
        (d / "not_a_png.png").write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
        try:
            read_mask(d / "not_a_png.png", (h, w))
        except SystemExit as e:
            assert "LFS" in str(e)
        else:
            raise AssertionError("an LFS pointer was accepted as a mask")
    # a family nobody uses is blanked even when the raster has other families
    only_euro = np.where(inp.fam == FAMILY_ORDER.index("asian"), FAMILY_NONE, inp.fam).astype(np.uint8)
    f_euro, _p, _c = build_meshes(masks, only_euro)
    assert b"object=" not in f_euro[file_stem("asian", "farmland", 1) + ".txt"]
    # parsers: culture graphics skips comments and nested blocks, state family falls back to european
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "c.txt").write_text(
            "# graphics = african\nalpha = {\n\tcolor = rgb{ 1 2 3 }\n\tgraphics = east_asian\n\tnames = { graphics = nope }\n}\n"
            "beta = {\n\tgraphics = decentralised_americas\n}\ngamma = { }\n", encoding="utf-8")
        g = culture_graphics(Path(td))
        assert g == {"alpha": "east_asian", "beta": "decentralised_americas"}, g
    hl = {"S1": {"cultures": ["alpha"]}, "S2": {"cultures": []}, "S3": {"cultures": ["gamma"]}}
    gm = {"alpha": "east_asian", "beta": "decentralised_americas"}
    assert [state_family(k, hl, gm) for k in ("S1", "S2", "S3", "S4")] == ["asian", "european", "european", "european"]
    assert state_family("S5", {"S5": {"cultures": ["beta"]}}, gm) == "latin"
    log(f"selftest ok ({time.time() - t:.1f}s)")
    return 0


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--terrain-dir", type=Path, default=TERRAIN_DIR,
                    help="folder holding mask_woodlands_0{1,2,3}.png (default gfx/map/terrain/)")
    ap.add_argument("--no-write", action="store_true", help="skip the masks and mesh files (preview only)")
    ap.add_argument("--render", action="store_true", help="write scratchpad/dynamic_masks_preview{,_oldworld}.png")
    ap.add_argument("--tag", default="", help="suffix for the preview file names (before/after pairs)")
    ap.add_argument("--from-masks", action="store_true", help="rebuild the mesh files from the masks in gfx/map/masks/")
    ap.add_argument("--check", action="store_true", help="regenerate in memory and compare with disk")
    ap.add_argument("--selftest", action="store_true", help="synthetic world, needs no files")
    args = ap.parse_args(argv)
    terrain_dir = args.terrain_dir if args.terrain_dir.is_absolute() else (Path.cwd() / args.terrain_dir)
    if args.selftest:
        return selftest()
    if args.check:
        return check(terrain_dir, MASK_DIR, MESH_DIR)
    t = time.time()
    if args.from_masks:
        land, fam, counts, _dis = load_land_and_family()
        log("  states per building family: " + ", ".join(f"{f} {counts[f]}" for f in FAMILY_ORDER))
        masks = read_masks(MASK_DIR)
        files, _placed, rows = build_meshes(masks, fam)
        write_meshes(MESH_DIR, files)
        for line in mesh_report(rows, files):
            log(line)
        log(f"rebuilt the mesh files from {MASK_DIR.relative_to(REPO_ROOT)} ({time.time() - t:.0f}s)")
        return 0
    inp = load_inputs(terrain_dir)
    masks = build_masks(inp)
    for line in mask_stats(masks, inp.land):
        log(line)
    files, placed, rows = build_meshes(masks, inp.fam)
    for line in mesh_report(rows, files):
        log(line)
    if not args.no_write:
        write_masks(MASK_DIR, masks)
        write_meshes(MESH_DIR, files)
    if args.render:
        render(inp, masks, placed, args.tag)
    log(f"done in {time.time() - t:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
