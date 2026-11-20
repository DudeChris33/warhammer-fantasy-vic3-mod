#!/usr/bin/env python3
"""Season masks: the snow line, the snow carve and the foliage placement from our climate (#11535).

Vanilla's seasons are drawn from Earth. Three data sets decide where they show, all Earth's:

* the **snow line**: 24 north and 24 south control points (``snow_curve_{north,south}_00..23`` in
  ``gfx/map/environment/season_settings.txt``) set the deep-winter line over longitude, in MapCoords.y
  units (1 = north edge of the map). The shader (``gfx/FX/seasons_coverage.fxh``, 333-417) retracts it as
  winter fades, offsets it by the carve mask and pulls it toward the equator on high ground;
* ``gfx/map/masks/snow_carve_mask.png`` (2048x904, 8-bit L, row 0 north): read as ``.r`` at ``(x, 1 - y)``;
  ``(v / 255 - 0.5) * 2 * snow_carve_strength`` is subtracted from the north line and added to the south
  line, so **brighter = more snow** in both hemispheres and 128 is neutral;
* ``gfx/map/masks/season_placement_mask.dds`` (BC7, 4096x1808, 13 mips, row 0 north): ``.r`` is where the
  foliage that turns grows (autumn ground colour), ``.g`` where the ground is clear of trees (spring ground
  colour). It does not affect snow.

This script writes our own of all three from the committed climate model, the heightmap, the coastline and
#6617's terrain masks, and writes ``season_settings.txt`` with our 48 snow-curve values and carve strength
(every other knob stays vanilla's, copied byte for byte from the install). ``ice_curve_*`` pass through
unchanged: sea ice (and ``coast_distance.dds``) is #11533's, and any work on it has to go through this file.

Inputs (nothing new is sourced), sampled onto a 2048x904 grid (G2, the carve's own) and a 4096x1808 grid (G4,
the placement's):

* ``mapgen/derived/climate_zones.png`` + index -> **cold** land is a Koppen zone starting with ``D`` or ``E``
  (the committed #8202 model); a land pixel with no zone takes the nearest land zone.
* ``mapgen/derived/land_sea_mask.png`` and ``lake_mask.png`` -> land; lakes count as water in both files.
* ``map_data/heightmap.png`` -> world height ``hm / 65535 * WORLD_EXTENTS_Y`` (the mod's defines first, then
  vanilla's; 24), the quantity ``smoothstep(3, 11, height) * snow_height_lead`` in the shader.
* ``gfx/map/terrain/mask_{desert_01,03,04,05,06,savanna_01,03,woodlands_01,02,03}.png`` (``--terrain-dir``,
  #6617). A missing mask or a Git LFS pointer is a hard error naming #6617.
* vanilla's ``season_settings.txt`` (``--game``) as the template. A missing curve key, ``snow_carve_strength``,
  ``snow_height_lead`` or ``carve_mask_*`` key (or one we do not model) is a hard error: a game patch that
  moves a knob must fail ``--check`` and be looked at.

Method:

1. **Snow target.** On G2, cold land should be snowed in deep winter and warm land should not; warm land
   whose height lead exceeds :data:`MOUNTAIN_LEAD` is exempt (high ranges may carry snow anywhere).
2. **Curves.** Control point ``i`` sits at ``u = (i + 0.5) / 24`` and the engine interpolates linearly between
   neighbours, wrapping in x (:data:`CURVE_PHASE`; see below). Each point is fitted over the columns within
   half a segment: for a candidate line value the pixel's ``d`` (the line minus latitude minus the height
   lead, signs mirrored in the south) says how much carve the pixel needs. A cold pixel needs ``carve >= d +
   MARGIN`` and a warm one ``carve <= d - MARGIN``; the cost is first the number of pixels the carve cannot
   put right (outside ``+-S``), then the summed carve needed, ties poleward. The 24 choices are made together
   by a circular dynamic programme under the neighbour cap :data:`CURVE_MAX_STEP`; windows with no land
   interpolate, and a hemisphere with no cold land puts its line at the pole edge (no snow; the template's
   mean would need the carve to switch a whole hemisphere's snow off).
3. **Carve.** The carve a pixel still needs where the curve and the lead leave it unmet, plus a desert term
   ``-S * K_DESERT * gauss(sum carve_mask_w * mask / 255)`` over the desert and savanna material masks with
   vanilla's own weights (how vanilla's carve was made), clipped to ``+-S`` and blurred over land only; sea and
   lakes are neutral.
4. **Placement.** ``R = smoothstep(gauss(w01 + w02))`` (windows :data:`PLACEMENT_TURN`, :data:`PLACEMENT_TREES`) (``woodlands_01`` temperate woodland and
   ``woodlands_02`` magical forest turn), ``G = 1 - smoothstep(gauss(w01 + w02 + w03))`` (``woodlands_03`` is
   jungle and swamp: trees, never autumn); sea and lakes are R 0, G 255.

Control-point layout (measured 2026-11-19, vanilla install 1.15.1, from the engine-built curve strip we
cannot read): vanilla's snow line simulated on vanilla's own states (boreal and arctic states must snow;
tropical, savanna, desert and Mediterranean states must not; carve and height lead included) misclassifies
0.26% of the land at ``(i + 0.5) / 24``, 0.36% at ``i / 24`` and 0.60% at ``(i - 0.5) / 24``; the correlation
of the 24 north values with the southernmost boreal latitude per sector is 0.63 against 0.58. Weak, but both
favour the half-segment offset, so :data:`CURVE_PHASE` is 0.5. The preview shows the result; a wrong phase
shifts our line by at most half a segment (7.5 degrees of longitude).

BC7: mode 6 only (one line per 4x4 block, both p-bits 1, so A is 255 and B is 1, as vanilla's file: B <= 8,
A 255), 13 mips down to 1x1, vanilla's 148-byte header field for field (compared with the install's file by
``--check``), 9,876,068 bytes. The encoder is vectorised numpy: endpoints span the RG box (G swapped on
negative covariance), refined by least squares and kept where they win; an exhaustive 16-index search with
the anchor fix. Pillow decodes BC7 but cannot encode it, so every encode is verified by decoding level 0:
R and G must match within a mean error of 1.5 with at most 0.5% of pixels off by more than 8 and none by more than 96
(a line per block cannot hold the few blocks where forest, jungle and clear ground meet). ``ENCODING = "bgra8"`` writes the
uncompressed fallback instead (as vanilla's ``tree_autumn_ramp.dds``).

The three files are generated: never save the in-game season panel over them. Output is a pure function of
the inputs and the pinned toolchain. They are committed (the DDS through Git LFS) only after Chris accepts
the preview.

Usage::

    python mapgen/generate_season_masks.py                  # write the three files
    python mapgen/generate_season_masks.py --render         # also scratchpad/season_preview{,_oldworld}.png
    python mapgen/generate_season_masks.py --no-write --render   # tuning loop: preview only
    python mapgen/generate_season_masks.py --check          # regenerate in memory, compare with disk
    python mapgen/generate_season_masks.py --selftest       # synthetic world, needs no files

Run with ``mapgen/.venv/Scripts/python.exe`` (needs scipy). A change to any input (coastline, heightmap,
climate zones, #6617's masks) or a patch that moves the template makes ``--check`` fail; the response is to
re-run, render and have the preview accepted again, never to loosen the check.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import canvas_frame, map_config  # noqa: E402
from measure_vanilla_frame import VANILLA_ROOT  # noqa: E402
from worldgen import raster  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
SCRATCH_DIR = REPO_ROOT / "scratchpad"
TERRAIN_DIR = REPO_ROOT / "gfx" / "map" / "terrain"
OUT_PLACEMENT = REPO_ROOT / "gfx" / "map" / "masks" / "season_placement_mask.dds"
OUT_CARVE = REPO_ROOT / "gfx" / "map" / "masks" / "snow_carve_mask.png"
OUT_SETTINGS = REPO_ROOT / "gfx" / "map" / "environment" / "season_settings.txt"
SETTINGS_REL = Path("gfx") / "map" / "environment" / "season_settings.txt"
VANILLA_PLACEMENT_REL = Path("gfx") / "map" / "masks" / "season_placement_mask.dds"
VANILLA_CARVE_REL = Path("gfx") / "map" / "masks" / "snow_carve_mask.png"

CW, CH = map_config.PROVINCES_SIZE            # canvas 8192 x 3616
G2 = (2048, 904)                              # (w, h) of the carve mask
G4 = (4096, 1808)                             # (w, h) of the placement mask
OLDWORLD_CROP_G4 = (1725, 67, 2600, 930)      # (x0, y0, x1, y1) of the Old World preview crop on G4

# --- the engine's constants (gfx/FX/seasons_coverage.fxh, common/defines/00_graphics.txt)
POINTS = 24                                   # control points per curve
HEIGHT_RAMP = (3.0, 11.0)                     # SEASONS_SNOW_HEIGHT_MIN / MAX, world height units
PLACEMENT_MIPS = 13
EXPECTED_PLACEMENT_BYTES = 9_876_068          # vanilla's season_placement_mask.dds

# --- tuning (each constant has a value that switches its rule off)
#: Where control point i sits along longitude, in segments: u = (i + CURVE_PHASE) / 24 (docstring).
CURVE_PHASE = 0.5
#: Carve strength written to ``snow_carve_strength`` (vanilla 0.1). The carve spans +-S.
S = 0.15
#: A cold pixel's line must clear its latitude by this much, a warm pixel's fall short by this much.
MARGIN = 0.02
#: Strength of the desert/savanna material term in the carve (0 switches it off).
K_DESERT = 0.6
#: Longest step between neighbouring control points (MapCoords.y units).
CURVE_MAX_STEP = 0.03
#: Fit candidates every this much.
CURVE_GRID = 0.0025
#: Warm land whose height lead exceeds this is exempt from the "must stay snow-free" rule (mountains may snow).
MOUNTAIN_LEAD = 0.02
#: Land-only blur of the carve, G2 cells; sigma of the desert term, G2 cells.
CARVE_BLUR = 2.0
DESERT_SIGMA = 4.0
#: Placement: gaussian sigma in G4 pixels and the smoothstep window of both channels.
PLACEMENT_SIGMA = 2.0
#: Our woodland masks are sparse (temperate woodland peaks near 0.33, jungle near 0.6), so the windows sit low.
PLACEMENT_TURN = (0.03, 0.25)      # blurred woodlands_01 + 02 -> R
PLACEMENT_TREES = (0.05, 0.30)     # blurred woodlands_01 + 02 + 03 -> 1 - G
#: North candidates run from just above the equator to this; south candidates mirror it.
CURVE_CEIL = 0.99
#: BC7 verification limits on R and G (level 0): mean |d| over both channels; at most BC7_BAD_SHARE of pixels may be off
#: by more than BC7_BAD_ERR; no pixel off by more than BC7_MAX_ERR. A mode-6 block is one line, so the few blocks where
#: forest, jungle and clear ground meet (a triangle in RG) cannot be exact; measured 2026-11-19 on the real data: max 77,
#: 0.14% of pixels above 8, 0.003% above 32.
BC7_BAD_ERR = 8
BC7_BAD_SHARE = 0.005
BC7_MAX_ERR = 96
BC7_MEAN_ERR = 1.5
BC7_REFINE_ITERS = 2
#: "bc7" writes vanilla's format; "bgra8" the uncompressed fallback (4x the size).
ENCODING = "bc7"

CARVE_MASK_KEYS = ("desert_01", "desert_03", "desert_04", "desert_05", "desert_06", "savanna_01", "savanna_03")
WOOD_KEYS = ("woodlands_01", "woodlands_02", "woodlands_03")
CURVE_KEYS = tuple(f"snow_curve_{h}_{i:02d}" for h in ("north", "south") for i in range(POINTS))


def log(msg: str) -> None:
    print(msg, flush=True)


def smoothstep(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def equator_lat() -> float:
    """MapCoords.y of our equator (canvas row ``Y0``); the hemisphere split."""
    return 1.0 - canvas_frame.Y0 / CH


# --------------------------------------------------------------------------- template and defines

@dataclass
class Template:
    text: str                       # vanilla's season_settings.txt, decoded
    curve_north: np.ndarray         # (24,) vanilla values
    curve_south: np.ndarray
    carve_strength: float
    height_lead: float
    carve_weights: dict[str, float]


def _read_value(text: str, key: str) -> float:
    m = re.search(rf'^"{re.escape(key)}"\s*=\s*([-+0-9.eE]+)\s*$', text, re.M)
    if not m:
        raise SystemExit(f"season_settings.txt template: key {key!r} is missing (a game patch moved a knob? "
                         "read the new file before changing this script)")
    return float(m.group(1))


def load_template(game: Path) -> Template:
    path = game / SETTINGS_REL
    if not path.exists():
        raise SystemExit(f"{path}: not found; pass --game <Victoria 3 install>/game")
    text = path.read_bytes().decode("utf-8-sig")
    cn = np.array([_read_value(text, f"snow_curve_north_{i:02d}") for i in range(POINTS)])
    cs = np.array([_read_value(text, f"snow_curve_south_{i:02d}") for i in range(POINTS)])
    weights = {k: _read_value(text, f"carve_mask_{k}") for k in CARVE_MASK_KEYS}
    found = set(re.findall(r'^"carve_mask_(\w+)"', text, re.M))
    if found != set(CARVE_MASK_KEYS):
        raise SystemExit(f"season_settings.txt template: carve_mask keys {sorted(found)} differ from the "
                         f"{sorted(CARVE_MASK_KEYS)} this script models")
    return Template(text, cn, cs, _read_value(text, "snow_carve_strength"), _read_value(text, "snow_height_lead"),
                    weights)


def world_extents_y(game: Path) -> float:
    """``WORLD_EXTENTS_Y``: the mod's ``common/defines`` first (last file wins), then vanilla's."""
    for root in (REPO_ROOT / "common" / "defines", game / "common" / "defines"):
        found = None
        for p in sorted(root.glob("*.txt")) if root.is_dir() else []:
            m = re.search(r"^\s*WORLD_EXTENTS_Y\s*=\s*([0-9.]+)", p.read_text(encoding="utf-8-sig"), re.M)
            if m:
                found = float(m.group(1))
        if found is not None:
            return found
    raise SystemExit("WORLD_EXTENTS_Y not found in the mod's or vanilla's common/defines")


def settings_text(template: Template, cn: np.ndarray, cs: np.ndarray, strength: float) -> str:
    """The template with only the 48 ``snow_curve_*`` lines and ``snow_carve_strength`` replaced."""
    text = template.text

    def put(key: str, value: float) -> None:
        nonlocal text
        text, n = re.subn(rf'^("{re.escape(key)}"\s*=\s*)[-+0-9.eE]+(\s*)$', lambda m: f"{m.group(1)}{value:.6f}{m.group(2)}",
                          text, count=1, flags=re.M)
        if n != 1:
            raise SystemExit(f"season_settings.txt template: could not replace {key!r}")

    for i in range(POINTS):
        put(f"snow_curve_north_{i:02d}", float(cn[i]))
        put(f"snow_curve_south_{i:02d}", float(cs[i]))
    put("snow_carve_strength", strength)
    return text


def normalize_text(text: str) -> str:
    """BOM and CRLF removed: ``core.autocrlf`` checks committed LF files out as CRLF."""
    return text.lstrip("\ufeff").replace("\r\n", "\n")


# --------------------------------------------------------------------------- inputs

@dataclass
class Inputs:
    land2: np.ndarray        # bool (904, 2048)
    cold2: np.ndarray        # bool, land only
    height2: np.ndarray      # float32 world height
    desert2: np.ndarray      # float32, sum of carve_mask_w * mask / 255 (not clipped)
    land4: np.ndarray        # bool (1808, 4096)
    height4: np.ndarray | None
    wood4: np.ndarray        # float32 (3, 1808, 4096), 0..255, woodlands_01..03
    cold4: np.ndarray | None = None


def _down(a: np.ndarray, f: int, dtype=np.float32) -> np.ndarray:
    """Box mean of f x f blocks of a canvas-sized array, a band of rows at a time."""
    h, w = a.shape
    out = np.empty((h // f, w // f), dtype=np.float32)
    step = 128 * f
    for y0 in range(0, h, step):
        blk = a[y0:y0 + step].astype(np.float32)
        out[y0 // f:(y0 + step) // f] = blk.reshape(-1, f, w // f, f).mean(axis=(1, 3))
    return out


def read_terrain_mask(directory: Path, name: str) -> np.ndarray:
    path = directory / f"mask_{name}.png"
    if not path.exists():
        raise SystemExit(f"{path}: missing. These are #6617's terrain masks (generate_terrain_masks.py); "
                         "pass --terrain-dir if they live elsewhere")
    try:
        with Image.open(path) as im:
            if im.mode != "L" or im.size != (CW, CH):
                raise SystemExit(f"{path}: expected an {CW}x{CH} mode L PNG (#6617), got {im.size[0]}x{im.size[1]} "
                                 f"mode {im.mode}; check --terrain-dir")
            return np.asarray(im, dtype=np.uint8)
    except Image.UnidentifiedImageError:
        raise SystemExit(f"{path}: not a PNG ({path.stat().st_size} bytes); a Git LFS pointer? run `git lfs pull` "
                         "(#6617's masks; check --terrain-dir)") from None


def load_inputs(game: Path, terrain_dir: Path, template: Template, weights: dict[str, float]) -> Inputs:
    t0 = time.time()
    land = raster.read_mask_png(DERIVED_DIR / "land_sea_mask.png")
    lake = raster.read_mask_png(DERIVED_DIR / "lake_mask.png")
    for name, a in (("land_sea_mask", land), ("lake_mask", lake)):
        if a.shape != (CH, CW):
            raise SystemExit(f"{name}.png: expected {CW}x{CH}, got {a.shape[1]}x{a.shape[0]}")
    land = land & ~lake
    land4 = _down(land, 2) >= 0.5
    land4_sum = (_down(land, 2) * 4).round().astype(np.int32)       # land pixels per G4 cell (0..4)
    del lake
    log(f"  coast: land {100 * land.mean():.2f}% of the canvas [{time.time() - t0:.0f}s]")
    del land

    # climate zones -> cold flag per G4 cell, nearest land zone where a land cell has none
    zones, _pal = raster.read_indexed_png(DERIVED_DIR / "climate_zones.png")
    index = json.loads((DERIVED_DIR / "climate_zones_index.json").read_text(encoding="utf-8"))
    sea_value = int(index["sea_value"])
    cold_ids = [c["id"] for c in index["classes"] if c["code"][0] in "DE"]
    if not cold_ids:
        raise SystemExit("climate_zones_index.json lists no D or E zone")
    z4 = zones[0::2, 0::2].copy()
    del zones
    have = land4 & (z4 != sea_value)
    missing = land4 & ~have
    if missing.any():
        _d, (iy, ix) = ndimage.distance_transform_edt(~have, return_indices=True)
        z4 = z4[iy, ix]
        log(f"  climate: {int(missing.sum()):,} land cells without a zone took the nearest land zone")
    cold4 = land4 & np.isin(z4, cold_ids)
    del z4

    # G2 aggregates
    def agg(a):
        return a.reshape(G2[1], 2, G2[0], 2).sum(axis=(1, 3))

    land_n = agg(land4_sum)                                          # land pixels per G2 cell of 16
    land2 = land_n >= 8
    cold_n = agg(cold4.astype(np.int32) * land4_sum)
    cold2 = land2 & (cold_n * 2 >= land_n)

    # height
    wey = world_extents_y(game)
    hm = raster.read_gray16_png(REPO_ROOT / "map_data" / "heightmap.png")
    if hm.shape != (CH * 2, CW * 2):
        raise SystemExit(f"heightmap.png: expected {CW * 2}x{CH * 2}, got {hm.shape[1]}x{hm.shape[0]}")
    height4 = (_down(hm, 4) / 65535.0 * wey).astype(np.float32)
    del hm
    height2 = height4.reshape(G2[1], 2, G2[0], 2).mean(axis=(1, 3), dtype=np.float32)
    log(f"  height: WORLD_EXTENTS_Y {wey:g}, land max {height4[land4].max():.1f} [{time.time() - t0:.0f}s]")

    # material masks
    desert = np.zeros((G2[1], G2[0]), np.float32)
    for k in CARVE_MASK_KEYS:
        m = read_terrain_mask(terrain_dir, k)
        desert += np.float32(weights[k]) * _down(m, 4) / 255.0
    wood = np.stack([_down(read_terrain_mask(terrain_dir, k), 2) for k in WOOD_KEYS])
    log(f"  masks read [{time.time() - t0:.0f}s]")
    return Inputs(land2, cold2, height2, desert, land4, height4, wood, cold4)


# --------------------------------------------------------------------------- snow line model

def curve_at(c: np.ndarray, x: np.ndarray, phase: float = CURVE_PHASE) -> np.ndarray:
    """Linear interpolation of the 24 control points at longitude fractions ``x``, wrapping."""
    pos = x * POINTS - phase
    i0 = np.floor(pos).astype(np.int64)
    f = pos - i0
    return c[i0 % POINTS] * (1.0 - f) + c[(i0 + 1) % POINTS] * f


def height_lead(height: np.ndarray, lead_max: float) -> np.ndarray:
    return smoothstep(height, HEIGHT_RAMP[0], HEIGHT_RAMP[1]) * lead_max


def lat_of_rows(h: int) -> np.ndarray:
    return 1.0 - (np.arange(h, dtype=np.float64) + 0.5) / h


def cols_x(w: int) -> np.ndarray:
    return (np.arange(w, dtype=np.float64) + 0.5) / w


def hemisphere_rows(h: int) -> int:
    """Number of north rows (latitude above our equator)."""
    return int((lat_of_rows(h) > equator_lat()).sum())


def _point_costs(inp: Inputs, lead: np.ndarray, north: bool, cand: np.ndarray, strength: float, margin: float) -> tuple:
    """Per control point and candidate: ``(unfixable pixel count + summed need, constrained pixel counts)``."""
    h, w = inp.land2.shape
    lat = lat_of_rows(h)
    r_eq = hemisphere_rows(h)
    rows = slice(0, r_eq) if north else slice(r_eq, h)
    x = cols_x(w)
    cost = np.zeros((POINTS, len(cand)))
    n_cold = np.zeros(POINTS, np.int64)
    n_con = np.zeros(POINTS, np.int64)
    land = inp.land2[rows]
    cold = inp.cold2[rows]
    warm = land & ~cold & (lead[rows] <= MOUNTAIN_LEAD)
    lat_r = lat[rows][:, None]
    for i in range(POINTS):
        centre = (i + CURVE_PHASE) / POINTS
        dx = (x - centre + 0.5) % 1.0 - 0.5
        cols = np.nonzero(np.abs(dx) <= 0.5 / POINTS + 1e-9)[0]
        cm = cold[:, cols]
        wm = warm[:, cols]
        lat_b = np.broadcast_to(lat_r, cm.shape)
        ld = lead[rows][:, cols]
        n_cold[i] = int(cm.sum())
        n_con[i] = int(cm.sum() + wm.sum())
        for sel, is_cold in ((cm, True), (wm, False)):
            if not sel.any():
                continue
            la = lat_b[sel]
            le = ld[sel]
            d = (cand[:, None] - la[None, :] - le[None, :]) if north else (la[None, :] - cand[:, None] - le[None, :])
            if is_cold:
                bad = (d + margin) > strength
                need = np.maximum(d + margin, 0.0)
            else:
                bad = (d - margin) < -strength
                need = np.maximum(margin - d, 0.0)
            cost[i] += bad.sum(axis=1) * 1e6 + need.sum(axis=1)
    return cost, n_cold, n_con


def _circular_dp(cost: np.ndarray, step: int, pen_scale: float) -> np.ndarray:
    """Cheapest circular path through ``cost`` (points x candidates) with neighbours <= ``step`` candidates apart."""
    n, k = cost.shape
    shifts = range(-step, step + 1)
    pen = {d: pen_scale * d * d for d in shifts}
    inf = np.inf
    dp = np.full((k, k), inf)                      # [start candidate, current candidate]
    dp[np.arange(k), np.arange(k)] = cost[0]
    back = np.zeros((n, k, k), np.int16)
    for i in range(1, n):
        best = np.full((k, k), inf)
        arg = np.zeros((k, k), np.int16)
        for d in shifts:                           # previous candidate = current - d
            lo, hi = max(0, d), min(k, k + d)
            cand = np.full((k, k), inf)
            cand[:, lo:hi] = dp[:, lo - d:hi - d] + pen[d]
            better = cand < best
            best = np.where(better, cand, best)
            arg = np.where(better, np.int16(d), arg)
        dp = best + cost[i][None, :]
        back[i] = arg
    # close the ring: the last candidate is within `step` of the start
    total = np.full(k, inf)
    last = np.zeros(k, np.int64)
    for s in range(k):
        lo, hi = max(0, s - step), min(k, s + step + 1)
        seg = dp[s, lo:hi] + np.array([pen[c - s] for c in range(lo, hi)])
        j = int(np.argmin(seg))
        total[s] = seg[j]
        last[s] = lo + j
    s0 = int(np.argmin(total))
    path = np.zeros(n, np.int64)
    path[-1] = last[s0]
    for i in range(n - 1, 0, -1):
        path[i - 1] = path[i] - back[i, s0, path[i]]
    return path


def fit_curve(inp: Inputs, lead: np.ndarray, north: bool, strength: float, margin: float) -> tuple:
    """The 24 control points of one hemisphere: ``(values, info)``."""
    eq = equator_lat()
    if north:
        cand = np.arange(eq + 0.05, CURVE_CEIL + 1e-9, CURVE_GRID)
    else:
        cand = np.arange(0.0, eq - 0.05 + 1e-9, CURVE_GRID)
    h = inp.land2.shape[0]
    r_eq = hemisphere_rows(h)
    rows = slice(0, r_eq) if north else slice(r_eq, h)
    cold_total = int(inp.cold2[rows].sum())
    info = {"cold_px": cold_total, "candidates": len(cand), "fitted": cold_total > 0}
    if cold_total == 0:
        return np.full(POINTS, CURVE_CEIL if north else 1.0 - CURVE_CEIL), info
    cost, n_cold, n_con = _point_costs(inp, lead, north, cand, strength, margin)
    # poleward ties; windows with no constrained pixels cost nothing and so interpolate
    tie = 1e-8 * np.arange(len(cand))
    if north:
        tie = tie[::-1]
    for i in range(POINTS):
        if n_con[i] > 0:
            cost[i] += tie
    step = int(round(CURVE_MAX_STEP / CURVE_GRID))
    path = _circular_dp(cost, step, 1e-5)
    info["empty_windows"] = [int(i) for i in range(POINTS) if n_con[i] == 0]
    return cand[path], info


def fit_curves(inp: Inputs, template: Template, strength: float = S, margin: float = MARGIN) -> tuple:
    lead = height_lead(inp.height2, template.height_lead)
    cn, info_n = fit_curve(inp, lead, True, strength, margin)
    cs, info_s = fit_curve(inp, lead, False, strength, margin)
    return cn, cs, {"north": info_n, "south": info_s}


# --------------------------------------------------------------------------- carve

def _normalized_blur(a: np.ndarray, land: np.ndarray, sigma: float) -> np.ndarray:
    lf = land.astype(np.float32)
    num = ndimage.gaussian_filter(a * lf, sigma, mode=("nearest", "wrap"))
    den = ndimage.gaussian_filter(lf, sigma, mode=("nearest", "wrap"))
    return np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0)


def build_carve(inp: Inputs, cn: np.ndarray, cs: np.ndarray, template: Template, strength: float = S,
                margin: float = MARGIN, k_desert: float = K_DESERT) -> np.ndarray:
    """The carve as a uint8 (904, 2048) mask: 128 neutral, brighter = more snow."""
    h, w = inp.land2.shape
    lat = lat_of_rows(h)[:, None]
    x = cols_x(w)
    lead = height_lead(inp.height2, template.height_lead)
    r_eq = hemisphere_rows(h)
    ln = curve_at(cn, x)[None, :]
    ls = curve_at(cs, x)[None, :]
    d = np.empty((h, w))
    d[:r_eq] = (ln - lat[:r_eq] - lead[:r_eq])
    d[r_eq:] = (lat[r_eq:] - ls - lead[r_eq:])
    cold = inp.cold2
    warm = inp.land2 & ~cold & (lead <= MOUNTAIN_LEAD)
    o = np.zeros((h, w))
    o = np.where(cold, np.maximum(d + margin, 0.0), o)
    o = np.where(warm, np.minimum(d - margin, 0.0), o)
    if k_desert > 0.0:
        desert = ndimage.gaussian_filter(np.clip(inp.desert2, 0.0, 1.0), DESERT_SIGMA, mode=("nearest", "wrap"))
        o = o - strength * k_desert * desert * (~cold)      # cold land keeps the snow it needs
    o = np.clip(o, -strength, strength)
    o = _normalized_blur(o.astype(np.float32), inp.land2, CARVE_BLUR)
    o = np.where(inp.land2, o, 0.0)
    v = np.rint(255.0 * (0.5 + o / (2.0 * strength)))
    return np.clip(v, 0, 255).astype(np.uint8)


def carve_offset(v: np.ndarray, strength: float) -> np.ndarray:
    """What the shader reads: ``(v / 255 - 0.5) * 2 * strength``."""
    return (v.astype(np.float64) / 255.0 - 0.5) * 2.0 * strength


def snowed(cn, cs, offset, lead, lat, x, edge: float | None = None, margin: float = 0.0):
    """Coverage (half-coverage on the line) of the deep-winter snow, ``max`` of both hemispheres' fields.

    ``edge`` None gives a boolean (coverage >= 0.5); otherwise the smoothstep coverage with that edge width
    and the line pushed ``margin`` toward the equator (frost)."""
    ln = curve_at(cn, x)[None, :] - offset - (lead + margin)
    ls = curve_at(cs, x)[None, :] + offset + (lead + margin)
    la = lat[:, None]
    if edge is None:
        return (la >= ln) | (la <= ls)
    half = edge * 0.5
    north = smoothstep(la, ln - half, ln + half)
    south = smoothstep(la, ls + half, ls - half)
    return np.maximum(north, south)


def unmet(inp: Inputs, cn, cs, v, template: Template, strength: float) -> dict:
    """Share of land (per hemisphere) the line leaves wrong: cold unsnowed, or warm (non-mountain) snowed."""
    h, w = inp.land2.shape
    lat = lat_of_rows(h)
    lead = height_lead(inp.height2, template.height_lead)
    snow = snowed(cn, cs, carve_offset(v, strength), lead, lat, cols_x(w))
    warm = inp.land2 & ~inp.cold2 & (lead <= MOUNTAIN_LEAD)
    bad = (inp.cold2 & ~snow) | (warm & snow)
    r_eq = hemisphere_rows(h)
    out = {}
    for name, rows in (("north", slice(0, r_eq)), ("south", slice(r_eq, h))):
        n = int(inp.land2[rows].sum())
        out[name] = {"land": n, "cold": int(inp.cold2[rows].sum()), "cold_unsnowed": int((inp.cold2 & ~snow)[rows].sum()),
                     "warm_snowed": int((warm & snow)[rows].sum()), "share": float(bad[rows].sum()) / max(n, 1)}
    return out


# --------------------------------------------------------------------------- placement

def build_placement(inp: Inputs) -> np.ndarray:
    """RG uint8 (1808, 4096, 2): R where foliage turns, G where the ground is clear of trees."""
    land = inp.land4
    w1, w2, w3 = inp.wood4
    lf = land.astype(np.float32)
    den = np.maximum(ndimage.gaussian_filter(lf, PLACEMENT_SIGMA, mode=("nearest", "wrap")), 1e-6)

    def field(a: np.ndarray) -> np.ndarray:
        num = ndimage.gaussian_filter(np.clip(a, 0.0, 255.0) * lf / 255.0, PLACEMENT_SIGMA, mode=("nearest", "wrap"))
        return num / den

    r = smoothstep(field(w1 + w2), *PLACEMENT_TURN)
    g = 1.0 - smoothstep(field(w1 + w2 + w3), *PLACEMENT_TREES)
    rg = np.empty(land.shape + (2,), np.uint8)
    rg[..., 0] = np.where(land, np.rint(r * 255.0), 0).astype(np.uint8)
    rg[..., 1] = np.where(land, np.rint(g * 255.0), 255).astype(np.uint8)
    return rg


# --------------------------------------------------------------------------- BC7 (mode 6, RG)

_W6 = np.array([0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64], np.int32)
_BC7_CHUNK = 16384


def _search(b: np.ndarray, q0: np.ndarray, q1: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Best 16-level index per pixel for endpoints ``q0``, ``q1`` (n, 2) in 7-bit units; returns (idx, err)."""
    v0 = 2 * q0 + 1
    v1 = 2 * q1 + 1
    pal = ((64 - _W6)[None, :, None] * v0[:, None, :] + _W6[None, :, None] * v1[:, None, :] + 32) >> 6   # (n,16,2)
    diff = b[:, :, None, :] - pal[:, None, :, :]
    e = (diff * diff).sum(-1)                                                                           # (n,16px,16idx)
    idx = e.argmin(-1)
    err = np.take_along_axis(e, idx[..., None], -1)[..., 0].sum(1)
    return idx.astype(np.int32), err


def _refine(b: np.ndarray, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Least-squares endpoints (7-bit units) for fixed indices; flat blocks come back as their mean."""
    w = (_W6[idx] / 64.0)                                       # (n,16)
    a = ((1 - w) ** 2).sum(1)
    bb = ((1 - w) * w).sum(1)
    c = (w ** 2).sum(1)
    det = a * c - bb * bb
    ok = det > 1e-6
    safe = np.where(ok, det, 1.0)
    e0 = np.empty((len(b), 2))
    e1 = np.empty((len(b), 2))
    for ch in range(2):
        p = b[:, :, ch].astype(np.float64)
        r0 = ((1 - w) * p).sum(1)
        r1 = (w * p).sum(1)
        mean = p.mean(1)
        e0[:, ch] = np.where(ok, (c * r0 - bb * r1) / safe, mean)
        e1[:, ch] = np.where(ok, (a * r1 - bb * r0) / safe, mean)
    to_q = lambda e: np.clip(np.rint((e - 1.0) / 2.0), 0, 127).astype(np.int32)  # noqa: E731
    return to_q(e0), to_q(e1)


def encode_bc7_blocks(b: np.ndarray) -> np.ndarray:
    """``(n, 16, 2)`` uint8 RG pixels -> ``(n, 2)`` uint64 (low, high) mode-6 blocks."""
    n = len(b)
    out = np.empty((n, 2), np.uint64)
    for s in range(0, n, _BC7_CHUNK):
        blk = b[s:s + _BC7_CHUNK].astype(np.int32)
        m = len(blk)
        lo = blk.min(1)
        hi = blk.max(1)
        cr = blk[:, :, 0] - blk[:, :, 0].mean(1, keepdims=True)
        cg = blk[:, :, 1] - blk[:, :, 1].mean(1, keepdims=True)
        neg = (cr * cg).sum(1) < 0
        e0 = lo.copy()
        e1 = hi.copy()
        e0[neg, 1], e1[neg, 1] = hi[neg, 1], lo[neg, 1]
        q0 = np.clip(e0 >> 1, 0, 127)
        q1 = np.clip(e1 >> 1, 0, 127)
        idx, err = _search(blk, q0, q1)
        for _ in range(BC7_REFINE_ITERS):
            r0, r1 = _refine(blk, idx)
            idx2, err2 = _search(blk, r0, r1)
            win = err2 < err
            q0 = np.where(win[:, None], r0, q0)
            q1 = np.where(win[:, None], r1, q1)
            idx = np.where(win[:, None], idx2, idx)
            err = np.where(win, err2, err)
        flip = idx[:, 0] >= 8                                    # anchor index keeps its top bit clear
        idx = np.where(flip[:, None], 15 - idx, idx)
        q0, q1 = np.where(flip[:, None], q1, q0), np.where(flip[:, None], q0, q1)
        u = lambda a: a.astype(np.uint64)  # noqa: E731
        low = np.full(m, 1 << 6, np.uint64)                      # mode 6
        low |= u(q0[:, 0]) << np.uint64(7)
        low |= u(q1[:, 0]) << np.uint64(14)
        low |= u(q0[:, 1]) << np.uint64(21)
        low |= u(q1[:, 1]) << np.uint64(28)
        # B endpoints 0 (value 1 with the p-bit), A endpoints 127 (value 255)
        low |= np.uint64(127) << np.uint64(49)
        low |= np.uint64(127) << np.uint64(56)
        low |= np.uint64(1) << np.uint64(63)                     # p-bit of endpoint 0
        high = np.full(m, 1, np.uint64)                          # p-bit of endpoint 1
        high |= u(idx[:, 0]) << np.uint64(1)
        for k in range(1, 16):
            high |= u(idx[:, k]) << np.uint64(4 * k)
        out[s:s + m, 0] = low
        out[s:s + m, 1] = high
    return out


def level_blocks(rg: np.ndarray) -> np.ndarray:
    """``(h, w, 2)`` -> ``(blocks, 16, 2)`` in block row-major order, edge-replicated to a multiple of 4."""
    h, w = rg.shape[:2]
    ph, pw = (-h) % 4, (-w) % 4
    if ph or pw:
        rg = np.pad(rg, ((0, ph), (0, pw), (0, 0)), mode="edge")
    hh, ww = rg.shape[:2]
    return rg.reshape(hh // 4, 4, ww // 4, 4, 2).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 2)


def encode_bc7_level(rg: np.ndarray) -> bytes:
    return np.ascontiguousarray(encode_bc7_blocks(level_blocks(rg)).astype("<u8")).tobytes()


def mip_dims(w: int, h: int, count: int) -> list[tuple[int, int]]:
    dims = []
    for _ in range(count):
        dims.append((w, h))
        w, h = max(1, w // 2), max(1, h // 2)
    return dims


def halve(a: np.ndarray) -> np.ndarray:
    """2x2 box average (round half up) of an ``(h, w, c)`` uint8 array; an odd tail row/column is dropped."""
    a = a.astype(np.int32)
    h, w = a.shape[:2]
    if h > 1:
        hh = h // 2 * 2
        a = a[0:hh:2] + a[1:hh:2]
    else:
        a = a * 2
    if w > 1:
        ww = w // 2 * 2
        a = a[:, 0:ww:2] + a[:, 1:ww:2]
    else:
        a = a * 2
    return ((a + 2) >> 2).astype(np.uint8)


def level_bytes(w: int, h: int, encoding: str | None = None) -> int:
    if (encoding or ENCODING) == "bc7":
        return ((w + 3) // 4) * ((h + 3) // 4) * 16
    return w * h * 4


def dds_header(w: int, h: int, mips: int, encoding: str | None = None) -> bytes:
    """Vanilla's ``season_placement_mask.dds`` header (148 bytes), or the legacy BGRA header."""
    if (encoding or ENCODING) == "bc7":
        fields = [
            124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000, h, w, level_bytes(w, h, "bc7"), 1, mips,   # depth 1, as vanilla's
            *([0] * 9), 0x3354564E, 1,                        # reserved1[9:11]: NVTT signature "NVT3", version 1
            32, 0x4, struct.unpack("<I", b"DX10")[0], 0, 0, 0, 0, 0,
            0x8 | 0x1000 | 0x400000, 0, 0, 0,
            0,
        ]
        return b"DDS " + struct.pack("<31I", *fields) + struct.pack("<5I", 98, 3, 0, 1, 1)
    fields = [
        124, 0x1 | 0x2 | 0x4 | 0x8 | 0x1000 | 0x20000, h, w, w * 4, 0, mips,
        *([0] * 11),
        32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000,
        0x8 | 0x1000 | 0x400000, 0, 0, 0,
        0,
    ]
    return b"DDS " + struct.pack("<31I", *fields)


def build_dds(rg: np.ndarray, mips: int = PLACEMENT_MIPS, verify: bool = True, encoding: str | None = None) -> bytes:
    """The placement DDS: header, then every level (box-averaged mips) encoded."""
    enc = encoding or ENCODING
    h, w = rg.shape[:2]
    dims = mip_dims(w, h, mips)
    parts = [dds_header(w, h, mips, enc)]
    level = rg
    for i, (lw, lh) in enumerate(dims):
        if i:
            level = halve(level)
        if level.shape[:2] != (lh, lw):
            raise SystemExit(f"mip {i}: built {level.shape[1]}x{level.shape[0]}, expected {lw}x{lh}")
        if enc == "bc7":
            parts.append(encode_bc7_level(level))
        else:
            bgra = np.zeros((lh, lw, 4), np.uint8)
            bgra[..., 2] = level[..., 0]
            bgra[..., 1] = level[..., 1]
            bgra[..., 3] = 255
            parts.append(bgra.tobytes())
    data = b"".join(parts)
    head = 148 if enc == "bc7" else 128
    want = head + sum(level_bytes(lw, lh, enc) for lw, lh in dims)
    if len(data) != want:
        raise SystemExit(f"DDS size {len(data)} != expected {want}")
    if verify:
        verify_dds(data, rg)
    return data


def decode_level0(data: bytes) -> np.ndarray:
    im = Image.open(io.BytesIO(data))
    return np.asarray(im.convert("RGBA"), dtype=np.int32)


def dds_errors(data: bytes, rg: np.ndarray) -> dict:
    got = decode_level0(data)
    if got.shape[:2] != rg.shape[:2]:
        raise SystemExit(f"decoded {got.shape[1]}x{got.shape[0]}, expected {rg.shape[1]}x{rg.shape[0]}")
    d = np.abs(got[..., :2] - rg.astype(np.int32))
    return {"max": int(d.max()), "mean": float(d.mean()), "bad_share": float((d.max(-1) > BC7_BAD_ERR).mean()), "max_r": int(d[..., 0].max()), "max_g": int(d[..., 1].max()),
            "b_max": int(got[..., 2].max()), "a_min": int(got[..., 3].min())}


def verify_dds(data: bytes, rg: np.ndarray) -> dict:
    e = dds_errors(data, rg)
    if e["max"] > BC7_MAX_ERR or e["mean"] > BC7_MEAN_ERR or e["bad_share"] > BC7_BAD_SHARE:
        raise SystemExit(f"BC7 round trip too lossy: max |d| {e['max']} (limit {BC7_MAX_ERR}), mean {e['mean']:.3f} "
                         f"(limit {BC7_MEAN_ERR}), {100 * e['bad_share']:.3f}% of pixels above {BC7_BAD_ERR} "
                         f"(limit {100 * BC7_BAD_SHARE:g}%)")
    return e


# --------------------------------------------------------------------------- build

@dataclass
class Result:
    cn: np.ndarray
    cs: np.ndarray
    carve: np.ndarray
    placement: np.ndarray
    settings: str
    info: dict


def build(inp: Inputs, template: Template, strength: float = S, margin: float = MARGIN,
          k_desert: float = K_DESERT, t0: float | None = None) -> Result:
    t0 = t0 if t0 is not None else time.time()
    cn, cs, info = fit_curves(inp, template, strength, margin)
    log(f"  curves fitted [{time.time() - t0:.0f}s]")
    carve = build_carve(inp, cn, cs, template, strength, margin, k_desert)
    um = unmet(inp, cn, cs, carve, template, strength)
    info["unmet"] = um
    info["unmet_vanilla"] = unmet(inp, template.curve_north, template.curve_south,
                                  _vanilla_neutral(carve.shape), template, template.carve_strength)
    log(f"  carve built [{time.time() - t0:.0f}s]")
    placement = build_placement(inp)
    land = inp.land4
    info["placement"] = {"land_r_mean": float(placement[..., 0][land].mean() / 255.0),
                         "land_g_mean": float(placement[..., 1][land].mean() / 255.0)}
    log(f"  placement built [{time.time() - t0:.0f}s]")
    return Result(cn, cs, carve, placement, settings_text(template, cn, cs, strength), info)


def _vanilla_neutral(shape) -> np.ndarray:
    return np.full(shape, 128, np.uint8)


def report(res: Result, template: Template) -> None:
    def curve_line(name, c, v):
        log(f"  {name:6s} " + " ".join(f"{x:.3f}" for x in c) + f"   (vanilla mean {np.mean(v):.3f})")

    curve_line("north", res.cn, template.curve_north)
    curve_line("south", res.cs, template.curve_south)
    for hemi in ("north", "south"):
        u = res.info["unmet"][hemi]
        uv = res.info["unmet_vanilla"][hemi]
        log(f"  unmet land, {hemi}: {100 * u['share']:.2f}% (cold unsnowed {u['cold_unsnowed']}, warm snowed "
            f"{u['warm_snowed']}, of {u['land']} land / {u['cold']} cold cells); vanilla's curves flat carve: "
            f"{100 * uv['share']:.2f}%")
    p = res.info["placement"]
    log(f"  placement on land: R mean {p['land_r_mean']:.2f}, G mean {p['land_g_mean']:.2f} (vanilla R 0.11, G 0.61)")
    cv = res.carve
    log(f"  carve: min {int(cv.min())}, max {int(cv.max())}, non-neutral {100 * float((cv != 128).mean()):.1f}% of cells")


# --------------------------------------------------------------------------- outputs and check

def carve_png_bytes(carve: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(carve, "L").save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def vanilla_header_problems(game: Path, data: bytes) -> list[str]:
    """Our DDS header against vanilla's file, field by field (BC7 only)."""
    path = game / VANILLA_PLACEMENT_REL
    if ENCODING != "bc7" or not path.exists():
        return []
    with path.open("rb") as f:
        van = f.read(148)
    ours = data[:148]
    if van == ours:
        return []
    names = ["magic"] + ["size", "flags", "height", "width", "pitch/linearsize", "depth", "mips"] + \
            [f"reserved1[{i}]" for i in range(11)] + ["pf.size", "pf.flags", "pf.fourcc", "pf.bits", "pf.rmask", "pf.gmask",
                                                       "pf.bmask", "pf.amask", "caps", "caps2", "caps3", "caps4", "reserved2",
                                                       "dx10.format", "dx10.dimension", "dx10.misc", "dx10.array", "dx10.misc2"]
    out = []
    for i, name in enumerate(names):
        a, b = van[4 * i:4 * i + 4], ours[4 * i:4 * i + 4]
        if a != b:
            out.append(f"header {name}: vanilla {int.from_bytes(a, 'little'):#x}, ours {int.from_bytes(b, 'little'):#x}")
    return out


def check(res: Result, game: Path) -> int:
    problems: list[str] = []
    data = build_dds(res.placement, verify=True)
    if ENCODING == "bc7" and len(data) != EXPECTED_PLACEMENT_BYTES:
        problems.append(f"placement DDS is {len(data):,} bytes, vanilla's is {EXPECTED_PLACEMENT_BYTES:,}")
    problems += vanilla_header_problems(game, data)
    for path, label in ((OUT_PLACEMENT, "placement DDS"),):
        if not path.exists():
            problems.append(f"{path.relative_to(REPO_ROOT)}: missing")
        elif path.read_bytes() != data:
            problems.append(f"{path.relative_to(REPO_ROOT)}: stale (differs from a fresh generation)")
    if not OUT_CARVE.exists():
        problems.append(f"{OUT_CARVE.relative_to(REPO_ROOT)}: missing")
    else:
        with Image.open(OUT_CARVE) as im:
            if im.mode != "L" or im.size != G2:
                problems.append(f"{OUT_CARVE.relative_to(REPO_ROOT)}: expected {G2[0]}x{G2[1]} mode L, got "
                                f"{im.size[0]}x{im.size[1]} mode {im.mode}")
            elif not np.array_equal(np.asarray(im), res.carve):
                problems.append(f"{OUT_CARVE.relative_to(REPO_ROOT)}: stale (pixels differ from a fresh generation)")
    if not OUT_SETTINGS.exists():
        problems.append(f"{OUT_SETTINGS.relative_to(REPO_ROOT)}: missing")
    elif normalize_text(OUT_SETTINGS.read_bytes().decode("utf-8")) != normalize_text(res.settings):
        problems.append(f"{OUT_SETTINGS.relative_to(REPO_ROOT)}: stale (differs from the template with our curves)")
    if problems:
        print("\n".join(problems))
        print("run: mapgen/.venv/Scripts/python.exe mapgen/generate_season_masks.py "
              "(then --render and have the preview accepted again)")
        return 1
    log("season masks current")
    return 0


def write_outputs(res: Result, template: Template, game: Path, t0: float) -> None:
    data = build_dds(res.placement, verify=True)
    if ENCODING == "bc7" and len(data) != EXPECTED_PLACEMENT_BYTES:
        raise SystemExit(f"placement DDS is {len(data):,} bytes, vanilla's is {EXPECTED_PLACEMENT_BYTES:,}")
    probs = vanilla_header_problems(game, data)
    if probs:
        raise SystemExit("DDS header differs from vanilla's:\n" + "\n".join(probs))
    log(f"  placement DDS encoded: {len(data):,} bytes; {dds_errors(data, res.placement)} [{time.time() - t0:.0f}s]")
    for path in (OUT_PLACEMENT, OUT_CARVE, OUT_SETTINGS):
        path.parent.mkdir(parents=True, exist_ok=True)
    OUT_PLACEMENT.write_bytes(data)
    OUT_CARVE.write_bytes(carve_png_bytes(res.carve))
    OUT_SETTINGS.write_bytes(res.settings.encode("utf-8"))      # template's own line ends (LF, no BOM in 1.15.1)
    for path in (OUT_PLACEMENT, OUT_CARVE, OUT_SETTINGS):
        log(f"wrote {path.relative_to(REPO_ROOT)} ({path.stat().st_size:,} bytes)")


# --------------------------------------------------------------------------- render

def _panel(img: np.ndarray, title: str) -> np.ndarray:
    pil = Image.fromarray(img)
    d = ImageDraw.Draw(pil)
    d.rectangle((0, 0, 330, 13), fill=(0, 0, 0))
    d.text((3, 1), title, fill=(255, 255, 255))
    return np.asarray(pil)


def snow_picture(inp: Inputs, cn, cs, v, template: Template, strength: float, grid: int, box=None,
                 curves=False) -> np.ndarray:
    """Deep-winter picture on G2 (grid 2) or G4 (grid 4): land tinted by cold/warm, frost and snow over it."""
    if grid == 2:
        land, cold, height = inp.land2, inp.cold2, inp.height2
    else:
        land, cold, height = inp.land4, inp.cold4, inp.height4
    h, w = land.shape
    if box is None:
        box = (0, 0, w, h)
    x0, y0, x1, y1 = box
    lat = lat_of_rows(h)[y0:y1]
    x = cols_x(w)[x0:x1]
    off_img = Image.fromarray(v, "L").resize((w, h), Image.BILINEAR) if grid == 4 else None
    off = carve_offset(np.asarray(off_img) if off_img is not None else v, strength)[y0:y1, x0:x1]
    lead = height_lead(height[y0:y1, x0:x1], template.height_lead)
    snow = snowed(cn, cs, off, lead, lat, x, edge=0.0816)
    frost = snowed(cn, cs, off, lead, lat, x, edge=0.0884, margin=0.0333)
    lnd = land[y0:y1, x0:x1]
    cl = cold[y0:y1, x0:x1]
    hy = np.gradient(height[y0:y1, x0:x1].astype(np.float32), axis=0)
    shade = 1.0 + np.clip(hy * (2.0 if grid == 2 else 4.0), -0.35, 0.35)
    base = np.where(cl[..., None], np.array([92, 104, 122], np.float32), np.array([128, 124, 84], np.float32))
    base = base * shade[..., None]
    base = np.where(lnd[..., None], base, np.array([22, 38, 58], np.float32))
    fr = (frost * 0.55)[..., None]
    img = base * (1 - fr) + np.array([196, 214, 236], np.float32) * fr
    sn = snow[..., None]
    img = img * (1 - sn) + np.array([248, 250, 252], np.float32) * sn
    img = np.where(lnd[..., None], img, base)
    img = np.clip(img, 0, 255).astype(np.uint8)
    if curves:
        pil = Image.fromarray(img)
        d = ImageDraw.Draw(pil)
        for c, col in ((cn, (230, 40, 40)), (cs, (230, 40, 40))):
            pts = [(i, int((1.0 - float(curve_at(c, np.array([x[i]]))[0])) * h) - y0) for i in range(0, len(x), 4)]
            d.line(pts, fill=col, width=1)
        ey = int((1.0 - equator_lat()) * h) - y0
        d.line([(0, ey), (len(x), ey)], fill=(140, 140, 140), width=1)
        img = np.asarray(pil)
    return img


def carve_picture(v: np.ndarray, land: np.ndarray, box=None) -> np.ndarray:
    d = (v.astype(np.float32) - 128.0) / 127.0
    out = np.empty(v.shape + (3,), np.float32)
    pos = np.clip(d, 0, 1)[..., None]
    neg = np.clip(-d, 0, 1)[..., None]
    out[:] = np.array([60, 60, 60], np.float32)
    out = out * (1 - pos) + np.array([220, 60, 40], np.float32) * pos
    out = out * (1 - neg) + np.array([50, 110, 230], np.float32) * neg
    out = np.where(land[..., None], out, np.array([18, 28, 40], np.float32))
    return np.clip(out, 0, 255).astype(np.uint8)


def placement_picture(rg: np.ndarray, land: np.ndarray) -> np.ndarray:
    img = np.zeros(rg.shape[:2] + (3,), np.uint8)
    img[..., 0] = rg[..., 0]
    img[..., 1] = rg[..., 1]
    img[~land] = (18, 28, 40)
    return img


def render(inp: Inputs, res: Result, template: Template, game: Path, strength: float = S) -> None:
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    van_carve_path = game / VANILLA_CARVE_REL
    if van_carve_path.exists():
        with Image.open(van_carve_path) as im:
            van_carve = np.asarray(im, dtype=np.uint8)
    else:
        van_carve = None
        log(f"  {van_carve_path} not found: the vanilla panel shows neutral carve")
    if van_carve is None or van_carve.shape != (G2[1], G2[0]):
        van_carve = np.full((G2[1], G2[0]), 128, np.uint8)
    vs = template.carve_strength

    def panels(grid: int, box):
        a = snow_picture(inp, res.cn, res.cs, res.carve, template, strength, grid, box, curves=True)
        b = snow_picture(inp, template.curve_north, template.curve_south, van_carve, template, vs, grid, box)
        if grid == 2:
            land = inp.land2
            c = carve_picture(res.carve, land)
            pl = res.placement.reshape(G2[1], 2, G2[0], 2, 2).mean(axis=(1, 3)).astype(np.uint8)
            dd = placement_picture(pl, land)
        else:
            x0, y0, x1, y1 = box
            c = carve_picture(np.asarray(Image.fromarray(res.carve, "L").resize(G4, Image.BILINEAR))[y0:y1, x0:x1],
                              inp.land4[y0:y1, x0:x1])
            dd = placement_picture(res.placement[y0:y1, x0:x1], inp.land4[y0:y1, x0:x1])
        return [_panel(a, "our deep winter, fitted curves in red"), _panel(b, "vanilla curves + carve on our map"),
                _panel(c, "carve offset: red more snow, blue less"), _panel(dd, "placement R (autumn) G (spring)")]

    def sheet(ps):
        top = np.concatenate(ps[:2], axis=1)
        bot = np.concatenate(ps[2:], axis=1)
        return np.concatenate([top, bot], axis=0)

    p1 = SCRATCH_DIR / "season_preview.png"
    Image.fromarray(sheet(panels(2, None))).save(p1)
    p2 = SCRATCH_DIR / "season_preview_oldworld.png"
    Image.fromarray(sheet(panels(4, OLDWORLD_CROP_G4))).save(p2)
    log(f"preview: {p1}\npreview: {p2}")


# --------------------------------------------------------------------------- selftest

def synthetic_inputs() -> Inputs:
    """A 1/8-scale world with a flat cold north, a desert south of it and forest patches; land everywhere."""
    h2, w2 = G2[1] // 4, G2[0] // 4
    h4, w4 = h2 * 2, w2 * 2
    lat = lat_of_rows(h2)[:, None] * np.ones((1, w2))
    land2 = np.ones((h2, w2), bool)
    land2[:, : w2 // 8] = False                       # an ocean band
    cold2 = land2 & (lat > 0.70)
    height2 = np.zeros((h2, w2), np.float32)
    desert2 = np.zeros((h2, w2), np.float32)
    desert2[(lat < 0.5) & (lat > 0.3)] = 1.0
    land4 = np.kron(land2, np.ones((2, 2), bool))
    wood4 = np.zeros((3, h4, w4), np.float32)
    wood4[0, : h4 // 4, w4 // 2:] = 255.0             # temperate woodland, north-east
    wood4[2, h4 // 2:, : w4 // 2] = 255.0             # jungle, south-west
    return Inputs(land2, cold2, height2, desert2, land4, None, wood4, None)


def synthetic_template() -> Template:
    cn = np.full(POINTS, 0.714)
    cs = np.full(POINTS, 0.13)
    text = ('"a" = 1\n' + "".join(f'"snow_curve_{h}_{i:02d}" = 0.500000\n' for h in ("north", "south") for i in range(POINTS))
            + '"snow_carve_strength" = 0.100000\n"snow_height_lead" = 0.181900\n"ice_curve_north_00" = 0.5\n')
    return Template(text, cn, cs, 0.1, 0.1819, {k: 1.0 for k in CARVE_MASK_KEYS})


def selftest() -> int:
    t0 = time.time()
    # BC7 blocks: gradient, flat, anti-correlated ramp, noise
    yy, xx = np.mgrid[0:16, 0:16]
    cases = {
        "gradient": np.stack([(xx + yy) * 8, 255 - (xx + yy) * 5], -1),
        "2D (two lines)": np.stack([xx * 12, yy * 12], -1),
        "flat": np.stack([np.zeros((16, 16)), np.full((16, 16), 255)], -1),
        "flat mid": np.full((16, 16, 2), 100),
        "anticorrelated": np.stack([xx * 16, 255 - xx * 16], -1),
        "noisy": np.random.default_rng(7).integers(0, 256, (16, 16, 2)),
    }
    limits = {"gradient": (6, 3.0), "2D (two lines)": (None, None), "flat": (1, 1.0), "flat mid": (1, 1.0), "anticorrelated": (8, 3.0), "noisy": (None, None)}
    for name, a in cases.items():
        rg = a.astype(np.uint8)
        data = build_dds(rg, mips=1, verify=False, encoding="bc7")
        assert len(data) == 148 + 16 * 16, (name, len(data))
        e = dds_errors(data, rg)
        mx, mean = limits[name]
        if mx is not None:
            assert e["max"] <= mx and e["mean"] <= mean, (name, e)
        assert e["b_max"] <= 8 and e["a_min"] == 255, (name, e)
        log(f"  bc7 {name:15s} max |d| {e['max']:3d}  mean {e['mean']:.3f}")
    # a 4x1 level (the mip tail) pads by edge replication and keeps its size
    tail = build_dds(np.full((1, 1, 2), 77, np.uint8), mips=1, verify=False)
    assert len(tail) == 148 + 16
    # byte total of the real size (analytic) and of a built small chain
    dims = mip_dims(*G4, PLACEMENT_MIPS)
    assert dims[-1] == (1, 1) and len(dims) == 13
    total = 148 + sum(level_bytes(w, h, "bc7") for w, h in dims)
    assert total == EXPECTED_PLACEMENT_BYTES, total
    small = build_dds(np.zeros((32, 64, 2), np.uint8), mips=7, verify=False)
    assert len(small) == 148 + sum(level_bytes(w, h, "bc7") for w, h in mip_dims(64, 32, 7))
    hdr = struct.unpack_from("<31I", small, 4)
    assert hdr[0] == 124 and hdr[1] == 0xA1007 and hdr[2] == 32 and hdr[3] == 64 and hdr[5] == 1 and hdr[6] == 7, hdr[:7]   # depth 1, as vanilla's
    assert small[84:88] == b"DX10" and struct.unpack_from("<5I", small, 128) == (98, 3, 0, 1, 1)
    bg = build_dds(np.zeros((8, 8, 2), np.uint8), mips=4, verify=False, encoding="bgra8")
    assert len(bg) == 128 + sum(w * h * 4 for w, h in mip_dims(8, 8, 4))
    # the world: deterministic, neutral carve where the curve already fits, north at row 0
    inp = synthetic_inputs()
    tpl = synthetic_template()
    r1 = build(inp, tpl, t0=t0)
    r2 = build(inp, tpl, t0=t0)
    d1 = build_dds(r1.placement, mips=5, verify=False)
    assert d1 == build_dds(r2.placement, mips=5, verify=False), "DDS not deterministic"
    e = dds_errors(d1, r1.placement)
    assert e["max"] <= 40 and e["mean"] <= BC7_MEAN_ERR, e
    log(f"  bc7 synthetic placement: max |d| {e['max']}, mean {e['mean']:.3f}")
    assert r1.carve.tobytes() == r2.carve.tobytes() and r1.settings == r2.settings, "not deterministic"
    h2, w2 = inp.land2.shape
    lat = lat_of_rows(h2)
    assert r1.cn.min() > equator_lat() and r1.cn.max() <= CURVE_CEIL, r1.cn
    assert abs(float(r1.cn.mean()) - (0.70 - 0.0)) < 0.05, f"north curve {r1.cn.mean():.3f} does not sit on the cold edge"
    snow = snowed(r1.cn, r1.cs, carve_offset(r1.carve, S), 0.0, lat, cols_x(w2))
    assert snow[0, w2 // 2] and not snow[h2 // 2, w2 // 2], "north is not at row 0"
    far = np.abs(lat - 0.70)[:, None] > 0.15                  # a hard edge needs carve within MARGIN of it
    away = (lat[:, None] > 0.08) & ~((lat[:, None] < 0.62) & (lat[:, None] > 0.15))   # south edge, desert and its blur
    land_rows = inp.land2 & far & away
    assert (np.abs(r1.carve[land_rows].astype(int) - 128) <= 0).all(), "carve is not neutral where the curve already fits"
    assert (r1.carve[~inp.land2] == 128).all(), "sea is not neutral"
    assert (r1.carve[(lat < 0.5)[:, None] & (lat > 0.3)[:, None] & inp.land2] <= 128).all(), "desert term raises the carve"
    pl = r1.placement
    assert pl[2, pl.shape[1] - 3, 0] > 200 and pl[2, pl.shape[1] - 3, 1] < 50, "woodland did not turn/shade at the top"
    assert (pl[:, :4, 0] == 0).all() and (pl[:, :4, 1] == 255).all(), "sea is not R 0, G 255"
    # settings text: only the 49 lines change
    real = tpl.text
    out = settings_text(tpl, r1.cn, r1.cs, S)
    a, b = real.splitlines(), out.splitlines()
    changed = [i for i in range(len(a)) if a[i] != b[i]]
    assert len(a) == len(b) and len(changed) == 49 and out.endswith("\n") and b[-1] == a[-1] and b[0] == a[0], changed
    assert curve_at(np.arange(POINTS, dtype=float), np.array([(3 + CURVE_PHASE) / POINTS]))[0] == 3.0
    log(f"selftest ok ({time.time() - t0:.1f}s)")
    return 0


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", type=Path, default=VANILLA_ROOT, help="Victoria 3 install's game folder (the settings template)")
    ap.add_argument("--terrain-dir", type=Path, default=TERRAIN_DIR, help="folder of #6617's mask_*.png (default gfx/map/terrain/)")
    ap.add_argument("--no-write", action="store_true", help="skip the three files (preview only)")
    ap.add_argument("--render", action="store_true", help="write scratchpad/season_preview{,_oldworld}.png")
    ap.add_argument("--check", action="store_true", help="regenerate in memory and compare with disk")
    ap.add_argument("--selftest", action="store_true", help="synthetic world, needs no files")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    t0 = time.time()
    game = args.game
    template = load_template(game)
    log(f"template: {game / SETTINGS_REL}")
    inp = load_inputs(game, args.terrain_dir, template, template.carve_weights)
    res = build(inp, template, t0=t0)
    report(res, template)
    if args.check:
        return check(res, game)
    if not args.no_write:
        write_outputs(res, template, game, t0)
    if args.render:
        render(inp, res, template, game)
    log(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
