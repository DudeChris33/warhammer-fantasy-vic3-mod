#!/usr/bin/env python3
"""End-to-end fixture pipeline: prove the whole code path offline.

Runs the full generator path on the tiny synthetic world in
``mapgen/fixtures/world/`` — schema load -> land/sea partition -> province
subdivision stub -> state-file text -> default.map + localization -> validators —
with **zero game dependency**, and regression-checks the output against the
committed golden copies in ``mapgen/fixtures/expected/`` byte-for-byte.

The subdivision here is the P1 *stub*: a seeded, wrap-aware Voronoi split with
connectivity repair and a small-cell merge. P3 replaces it with the full-scale
``generate_provinces.py`` / ``generate_state_regions.py`` reusing the same
``worldgen`` primitives.

Usage::

    python mapgen/run_fixture.py --check     # regenerate to temp, diff golden, run twice, validate
    python mapgen/run_fixture.py --update     # (re)write the golden outputs in expected/
    python mapgen/run_fixture.py --update-country-history   # rewrite only the country-history golden

``--check`` is the offline gate for P1. It fails (exit 1) on any determinism
drift, golden mismatch, or validator error.
"""

from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import math
import random
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import (  # noqa: E402
    cells, composite, ingest, macro, parchment, raster, reproject, schema, segment,
    sources, statefile,
)
from worldgen.raster import (  # noqa: E402
    ColorAllocator,
    color_to_hex,
    connected_components,
    neighbors4,
    point_distance,
    rasterize_polygon,
    segment_point_distance,
    voronoi_labels,
    write_rgb_png,
)
from worldgen.statefile import ProvinceInfo, compute_centroid, pick_hubs, stack_hubs  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
WORLD_DIR = TOOLS_DIR / "fixtures" / "world"
EXPECTED_DIR = TOOLS_DIR / "fixtures" / "expected"

# The S2 ingestion fixture: a synthetic whole-world source (our own pixels, so it
# is committed and runs on a clean clone) driven through the *same* ingestion core
# the real generator uses (worldgen.ingest), at a tiny canvas.
INGEST_DIR = TOOLS_DIR / "fixtures" / "ingest"
INGEST_MANIFEST = INGEST_DIR / "SOURCES.md"
INGEST_REG_DIR = INGEST_DIR / "registration"
INGEST_LUT = INGEST_DIR / "lut.json"
INGEST_EXPECTED = INGEST_DIR / "expected"

#: Fixture canvas — keeps the real canvas' ~2.266 aspect so lat/lon scaling is
#: representative; the heightmap is exactly 2x, exercising the upscale-to-mask.
INGEST_CANVAS = (512, 226)
INGEST_HEIGHTMAP = (1024, 452)
INGEST_BLOCK_ROWS = 64

# The S3a boundary fixture: a synthetic parchment plus a half-scale frame_alias
# sibling, carried through the *same* extract -> warp -> intersect -> tile path
# the real state-label generator uses, at a tiny canvas.
BOUNDARY_DIR = TOOLS_DIR / "fixtures" / "boundary"
BOUNDARY_MANIFEST = BOUNDARY_DIR / "SOURCES.md"
BOUNDARY_REG_DIR = BOUNDARY_DIR / "registration"
BOUNDARY_MASK = BOUNDARY_DIR / "mask.png"
BOUNDARY_EXPECTED = BOUNDARY_DIR / "expected"
BOUNDARY_CANVAS = (256, 112)  # (width, height)
#: Cell counts for the fixture, scaled down from the real targets.
BOUNDARY_LAND_CELLS = 12
BOUNDARY_SEA_ZONES = 5

# The fixture uses a tiny canvas (the real map is map_config.PROVINCES_SIZE).
FIXTURE_CANVAS = (128, 64)  # (width, height)

# Province seeds per land state in the subdivision stub.
PROVINCES_PER_COASTAL = 6
PROVINCES_PER_LANDLOCKED = 5
# Land passable provinces smaller than this get merged into a neighbour.
MERGE_MIN_AREA = 8
BOM = b"\xef\xbb\xbf"


# ---------------------------------------------------------------------------
# Partition: land ownership + sea zones + province subdivision
# ---------------------------------------------------------------------------

def _stable_seed(key: str) -> int:
    """Platform-stable hash of a state key (Python's hash() is salted)."""
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")


def _province_count(state: schema.State) -> int:
    return PROVINCES_PER_COASTAL if state.coastal else PROVINCES_PER_LANDLOCKED


class Partition:
    """Every pixel assigned to a province id (``pid``); metadata per pid."""

    def __init__(self, width: int, height: int, wrap_x: bool) -> None:
        self.width = width
        self.height = height
        self.wrap_x = wrap_x
        self.pid_pixels: dict[str, set[tuple[int, int]]] = {}
        self.pixel_pid: dict[tuple[int, int], str] = {}
        self.pid_info: dict[str, dict] = {}  # pid -> {state, kind, impassable}

    def add(self, pid: str, pixels, state: str, kind: str, impassable: bool) -> None:
        px = set(pixels)
        self.pid_pixels[pid] = px
        self.pid_info[pid] = {"state": state, "kind": kind, "impassable": impassable}
        for p in px:
            self.pixel_pid[p] = pid


def build_partition(world: schema.World, width: int, height: int, wrap_x: bool, seed: int) -> Partition:
    part = Partition(width, height, wrap_x)

    # --- land mask from coastlines ---------------------------------------
    land_mask: set[tuple[int, int]] = set()
    for _stem, landmasses in sorted(world.coastlines.items()):
        for lm in landmasses:
            land_mask |= rasterize_polygon(lm.outer, lm.holes, width, height, wrap_x)

    # --- land ownership from state polygons (must tile the land mask) -----
    owner: dict[tuple[int, int], str] = {}
    land_pixels_by_state: dict[str, set[tuple[int, int]]] = {}
    for st in world.land_states:
        g = st.geometry
        if g.kind != "polygon":
            raise ValueError(f"{st.key}: fixture land states must use polygon geometry")
        px = rasterize_polygon(g.polygon, g.holes, width, height, wrap_x)
        for p in px:
            if p in owner:
                raise RuntimeError(f"{st.key} overlaps {owner[p]} at pixel {p}")
        for p in px:
            owner[p] = st.key
        land_pixels_by_state[st.key] = px
    if set(owner) != land_mask:
        gap = len(land_mask - set(owner))
        stray = len(set(owner) - land_mask)
        raise RuntimeError(
            f"land states do not tile the coastline mask: {gap} uncovered, {stray} outside"
        )

    # --- sea zones: nearest-seed Voronoi over the ocean ------------------
    all_pixels = {(x, y) for x in range(width) for y in range(height)}
    ocean = sorted(all_pixels - land_mask)
    seeds: list[tuple[float, float]] = []
    seed_owner: list[str] = []
    for st in world.sea_states:
        for s in st.geometry.seeds or []:
            seeds.append(s)
            seed_owner.append(st.key)
    if not seeds:
        raise RuntimeError("fixture defines no sea zones")
    sea_pixels_by_state: dict[str, set[tuple[int, int]]] = {st.key: set() for st in world.sea_states}
    for pix, lab in zip(ocean, voronoi_labels(ocean, seeds, width, wrap_x)):
        sea_pixels_by_state[seed_owner[lab]].add(pix)
    for st in world.sea_states:
        part.add(f"{st.key}#sea", sea_pixels_by_state[st.key], st.key, "sea", impassable=False)

    # --- land subdivision: carve impassable, then seeded Voronoi ----------
    for st in world.land_states:
        px = land_pixels_by_state[st.key]
        imp_pixels: set[tuple[int, int]] = set()
        if st.impassable is not None:
            imp_pixels = px & rasterize_polygon(st.impassable, [], width, height, wrap_x)
        passable = px - imp_pixels

        imp_comps = connected_components(imp_pixels, width, height, wrap_x) if imp_pixels else []
        for i, comp in enumerate(sorted(imp_comps, key=lambda c: min(c))):
            part.add(f"{st.key}#imp{i}", comp, st.key, "land", impassable=True)

        passable_sorted = sorted(passable)
        k = min(_province_count(st), len(passable_sorted))
        rng = random.Random(seed ^ _stable_seed(st.key))
        seed_pixels = rng.sample(passable_sorted, k) if k > 0 else []
        groups: dict[int, set[tuple[int, int]]] = {}
        for pix, lab in zip(passable_sorted, voronoi_labels(passable_sorted, seed_pixels, width, wrap_x)):
            groups.setdefault(lab, set()).add(pix)
        for j, lab in enumerate(sorted(groups, key=lambda l: seed_pixels[l])):
            part.add(f"{st.key}#p{j}", groups[lab], st.key, "land", impassable=False)

    repair_connectivity(part)
    merge_small_land(part, MERGE_MIN_AREA)
    return part


def repair_connectivity(part: Partition) -> None:
    """Reassign disconnected fragments so every province is one component.

    A land fragment merges into the same-state land province it borders most; a
    sea fragment merges into whichever sea zone it borders most (sea-zone borders
    are arbitrary). Deterministic tie-breaks throughout.
    """
    changed = True
    while changed:
        changed = False
        for pid in sorted(part.pid_pixels):
            pixels = part.pid_pixels[pid]
            if len(pixels) <= 1:
                continue
            comps = connected_components(pixels, part.width, part.height, part.wrap_x)
            if len(comps) <= 1:
                continue
            comps.sort(key=lambda c: (-len(c), min(c)))
            for stray in comps[1:]:
                target = _best_merge_target(part, pid, stray)
                if target is None:
                    continue
                for p in stray:
                    part.pixel_pid[p] = target
                    part.pid_pixels[target].add(p)
                    part.pid_pixels[pid].discard(p)
                changed = True
    _drop_empty(part)


def merge_small_land(part: Partition, min_area: int) -> None:
    """Merge under-sized passable land provinces into a same-state neighbour."""
    changed = True
    while changed:
        changed = False
        for pid in sorted(part.pid_pixels):
            info = part.pid_info[pid]
            if info["kind"] != "land" or info["impassable"]:
                continue
            if len(part.pid_pixels[pid]) >= min_area:
                continue
            target = _best_merge_target(part, pid, part.pid_pixels[pid])
            if target is None:
                continue
            for p in list(part.pid_pixels[pid]):
                part.pixel_pid[p] = target
                part.pid_pixels[target].add(p)
            part.pid_pixels[pid].clear()
            changed = True
    _drop_empty(part)


def _best_merge_target(part: Partition, own_pid: str, fragment) -> str | None:
    own = part.pid_info[own_pid]
    counts: dict[str, int] = {}
    for (x, y) in fragment:
        for nb in neighbors4(x, y, part.width, part.height, part.wrap_x):
            npid = part.pixel_pid.get(nb)
            if npid is None or npid == own_pid:
                continue
            ninfo = part.pid_info[npid]
            if own["kind"] == "land":
                if ninfo["kind"] != "land" or ninfo["state"] != own["state"] or ninfo["impassable"]:
                    continue
            else:  # sea fragment
                if ninfo["kind"] != "sea":
                    continue
            counts[npid] = counts.get(npid, 0) + 1
    if not counts:
        return None
    return min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]


def _drop_empty(part: Partition) -> None:
    for pid in list(part.pid_pixels):
        if not part.pid_pixels[pid]:
            del part.pid_pixels[pid]
            del part.pid_info[pid]


# ---------------------------------------------------------------------------
# Colour allocation (sea first, so land never collides with a sea colour)
# ---------------------------------------------------------------------------

def allocate_colors(world: schema.World, part: Partition, seed: int) -> dict[str, raster.Color]:
    allocator = ColorAllocator(seed)
    pid_color: dict[str, raster.Color] = {}
    for st in world.sea_states:
        pid_color[f"{st.key}#sea"] = allocator.allocate()
    for st in world.land_states:
        state_pids = [p for p in part.pid_pixels if part.pid_info[p]["state"] == st.key]
        impassable = sorted(p for p in state_pids if part.pid_info[p]["impassable"])
        passable = sorted(p for p in state_pids if not part.pid_info[p]["impassable"])
        for pid in impassable + passable:
            pid_color[pid] = allocator.allocate()
    return pid_color


# ---------------------------------------------------------------------------
# Full map build (writes every output into out_dir)
# ---------------------------------------------------------------------------

def build_map(world: schema.World, out_dir: Path, width: int, height: int, wrap_x: bool, seed: int) -> None:
    part = build_partition(world, width, height, wrap_x, seed)
    pid_color = allocate_colors(world, part, seed)

    sea_pixels: set[tuple[int, int]] = set()
    for pid, info in part.pid_info.items():
        if info["kind"] == "sea":
            sea_pixels |= part.pid_pixels[pid]

    def is_coastal(pixels) -> bool:
        for (x, y) in pixels:
            for nb in neighbors4(x, y, width, height, wrap_x):
                if nb in sea_pixels:
                    return True
        return False

    # State ids.
    land_id = {st.key: map_config.LAND_ID_START + i for i, st in enumerate(world.land_states)}
    sea_id = {st.key: map_config.SEA_ID_START + i for i, st in enumerate(world.sea_states)}

    # --- provinces.png ---------------------------------------------------
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    for pid, pixels in part.pid_pixels.items():
        r, g, b = pid_color[pid]
        for (x, y) in pixels:
            rgb[y, x, 0] = r
            rgb[y, x, 1] = g
            rgb[y, x, 2] = b
    if bool((rgb == 0).all(axis=2).any()):
        raise RuntimeError("provinces.png has unassigned (black) pixels — partition is not total")

    map_dir = out_dir / "state_regions"
    loc_dir = out_dir / "loc"
    out_dir.mkdir(parents=True, exist_ok=True)
    map_dir.mkdir(parents=True, exist_ok=True)
    loc_dir.mkdir(parents=True, exist_ok=True)
    write_rgb_png(out_dir / "provinces.png", rgb)

    # --- state_regions/*.txt (land grouped by macro) ---------------------
    def state_province_infos(state_key: str) -> list[ProvinceInfo]:
        infos = []
        for pid in sorted(p for p in part.pid_pixels if part.pid_info[p]["state"] == state_key):
            pixels = part.pid_pixels[pid]
            infos.append(
                ProvinceInfo(
                    color=pid_color[pid],
                    centroid=compute_centroid(pixels, width, wrap_x),
                    area=len(pixels),
                    coastal=is_coastal(pixels),
                    impassable=part.pid_info[pid]["impassable"],
                )
            )
        return infos

    macros = sorted({st.macro for st in world.land_states})
    for i, macro in enumerate(macros):
        blocks = []
        for st in [s for s in world.land_states if s.macro == macro]:
            infos = state_province_infos(st.key)
            hubs = pick_hubs(st, infos, width, wrap_x)
            province_colors = [info.color for info in infos]
            impassable_colors = [info.color for info in infos if info.impassable]
            naval_exit_id = sea_id[st.naval_exit] if st.coastal else None
            blocks.append(
                statefile.render_land_state(
                    st, land_id[st.key], province_colors, hubs, impassable_colors, naval_exit_id
                )
            )
        _write_text(map_dir / f"{i + 1:02d}_{macro}.txt", statefile.render_state_file(blocks))

    sea_blocks = []
    for st in world.sea_states:
        pid = f"{st.key}#sea"
        sea_blocks.append(statefile.render_sea_state(st, sea_id[st.key], pid_color[pid]))
    _write_text(map_dir / "99_seas.txt", statefile.render_state_file(sea_blocks))

    # --- default.map -----------------------------------------------------
    sea_colors = sorted(pid_color[f"{st.key}#sea"] for st in world.sea_states)
    _write_text(out_dir / "default.map", _render_default_map(sea_colors))

    # --- localization ----------------------------------------------------
    _write_text(loc_dir / "wh_states_l_english.yml", _render_loc(world.land_states), bom=True)
    _write_text(loc_dir / "wh_seas_l_english.yml", _render_loc(world.sea_states), bom=True)


def _render_default_map(sea_colors: list[raster.Color]) -> str:
    sea_line = "\t" + " ".join(color_to_hex(c) for c in sea_colors)
    return (
        'provinces = "provinces.png"\n'
        'topology = "heightmap.heightmap"\n'
        'rivers = "rivers.png"\n'
        'adjacencies = "adjacencies.csv"\n'
        "wrap_x = yes\n"
        "\n"
        "sea_starts = {\n"
        f"{sea_line}\n"
        "}\n"
        "lakes = {\n"
        "}\n"
    )


def _pretty_name(key: str) -> str:
    return " ".join(part.capitalize() for part in key[len("STATE_"):].split("_"))


def _render_loc(states: list[schema.State]) -> str:
    lines = ["l_english:"]
    for st in sorted(states, key=lambda s: s.key):
        lines.append(f' {st.key}:0 "{_pretty_name(st.key)}" {map_config.AUTOGEN_MARKER}')
    return "\n".join(lines) + "\n"


def _write_text(path: Path, text: str, bom: bool = False) -> None:
    data = text.encode("utf-8")
    if bom:
        data = BOM + data
    path.write_bytes(data)  # binary write keeps LF newlines regardless of platform


# ---------------------------------------------------------------------------
# S2 ingestion fixture: the source-driven front-end, offline and byte-pinned
# ---------------------------------------------------------------------------

def build_ingest(out_dir: Path) -> None:
    """Drive the synthetic source through the real ingestion core into ``out_dir``.

    Deliberately calls the same ``worldgen.ingest`` functions the whole-world
    generator does — classify/de-ink/despeckle, reproject, clean, encode — so a
    regression in any of them trips this fixture. The source is loaded through the
    fixture manifest's SHA-256 guard, exactly as the real run loads its sources,
    so the verify path is covered too.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    elut = schema.load_elevation_lut(INGEST_LUT)
    regs = schema.load_registrations(INGEST_REG_DIR)
    if len(regs) != 1:
        raise RuntimeError(f"ingest fixture expects exactly one registration, found {len(regs)}")
    reg = regs[0]

    rgb = sources.load_source_image(reg.source, sources_dir=INGEST_DIR, manifest_path=INGEST_MANIFEST)

    # The synthetic world is rectangular and fills the frame, so its "drawn
    # envelope" is the whole image. The southern cap is set to half the source
    # height on purpose: the enclosed basin sits well inside that range, so what
    # excludes it is genuinely its lack of a path to the rim and not the cap
    # quietly doing the work.
    rim = ingest.PolarRim(
        envelope=np.ones(rgb.shape[:2], dtype=bool),
        north_seed=(0, 8),
        north_limit=rgb.shape[0] // 2,
    )
    # The synthetic world tiles the globe, so the majority filter is wrap-aware.
    fields = ingest.classify_source(rgb, elut, majority=3, wrap_x=True, polar_rim=rim)
    fit = reproject.fit_parametric(reg)

    cw, ch = INGEST_CANVAS
    land_raw = ingest.reproject_plane(reg, fit, fields.land, cw, ch,
                                      block_rows=INGEST_BLOCK_ROWS, order=1) > 0.5
    land = segment.clean_land_mask(land_raw, min_island_area=8, min_lake_area=8,
                                   close_radius=1, open_radius=1, wrap_x=True)
    raster.write_mask_png(out_dir / "land_sea_mask.png", land)

    hw, hh = INGEST_HEIGHTMAP
    height = np.empty((hh, hw), dtype=np.uint16)
    for y0 in range(0, hh, INGEST_BLOCK_ROWS):
        y1 = min(hh, y0 + INGEST_BLOCK_ROWS)
        rows = np.arange(y0, y1)
        sx, sy = ingest.clamped_source_coords(reg, fit, rows, hw, hh)
        elev = reproject.resample(fields.elev, sx, sy, order=1).astype(np.float32)
        blk_land = ingest.upscale2_rows(land, y0, y1)
        height[y0:y1] = ingest.encode_heightmap(
            elev, blk_land, sea_level=map_config.HEIGHT_SEA_LEVEL,
            units_per_metre=map_config.HEIGHT_UNITS_PER_METRE,
            shore_margin=map_config.HEIGHT_SHORE_MARGIN)
    raster.write_gray16_png(out_dir / "heightmap.png", height)

    _write_ingest_digest(out_dir / "ingest_stats.txt", reg, fields, land, height)


def _write_ingest_digest(path: Path, reg, fields, land: np.ndarray, height: np.ndarray) -> None:
    """A tiny human-readable digest, so the golden diff is legible as well as byte-exact.

    Everything here is an integer or an exactly-representable value — no floats
    that could differ in their last digit between platforms and break the
    byte-exact golden compare.
    """
    stats = segment.mask_stats(land, wrap_x=True)
    lo = map_config.HEIGHT_SEA_LEVEL + map_config.HEIGHT_SHORE_MARGIN
    hi = map_config.HEIGHT_SEA_LEVEL - map_config.HEIGHT_SHORE_MARGIN
    pr = fields.polar_report
    lines = [
        f"source                {reg.source}",
        f"projection            {reg.projection}",
        f"ink_source_px         {int(fields.ink.sum())}",
        f"land_bodies           {stats['land_bodies']}",
        f"water_bodies          {stats['water_bodies']}",
        f"land_px               {int(land.sum())}",
        f"heightmap_min         {int(height.min())}",
        f"heightmap_max         {int(height.max())}",
        f"land_at_or_above_lo   {bool((height[height >= map_config.HEIGHT_SEA_LEVEL] >= lo).all())}",
        f"sea_at_or_below_hi    {bool((height[height < map_config.HEIGHT_SEA_LEVEL] <= hi).all())}",
        f"polar_flipped_px      {pr.flipped if pr else 0}",
        f"polar_enclosed_px     {pr.enclosed if pr else 0}",
        f"polar_band_is_land    {_probe_polar_band(fields)}",
        f"enclosed_basin_is_sea {_probe_enclosed_basin(fields)}",
        "",
    ]
    path.write_bytes("\n".join(lines).encode("utf-8"))


def _fixture_source_geometry():
    """The two probe regions, imported from the script that paints them.

    Imported rather than re-typed: a probe box that drifted away from the feature
    it is supposed to be measuring would land on plain ocean and make
    ``enclosed_basin_is_sea`` pass for the wrong reason — a test that cannot fail
    is worse than no test.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_ingest_make_source", INGEST_DIR / "make_source.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.POLAR_BAND, mod.ENCLOSED_BASIN


#: Rows to leave off the polar band's southern edge when probing it. ``land`` is a
#: *smoothed* fraction (``land_sigma``), so the coast at the band's edge is a soft
#: ramp by design — including it would test the blur rather than the rule, which
#: is the same reason the basin probe uses a core.
_PROBE_MARGIN = 3


def _probe_polar_band(fields) -> bool:
    """Did the blank band along the north rim come out as land?"""
    (x0, y0, x1, y1), _ = _fixture_source_geometry()
    return bool((fields.land[y0:y1 - _PROBE_MARGIN, x0:x1] > 0.5).all())


def _probe_enclosed_basin(fields) -> bool:
    """Did the identically-coloured enclosed basin stay sea?"""
    _, (cx, cy, rx, ry) = _fixture_source_geometry()
    h, w = fields.land.shape
    yy, xx = np.mgrid[0:h, 0:w]
    # Probe the basin's core only: its rim is a colour boundary the smoothing
    # deliberately softens, so including it would test the blur, not the rule.
    core = ((xx - cx) / (rx * 0.6)) ** 2 + ((yy - cy) / (ry * 0.6)) ** 2 <= 1.0
    return bool((fields.land[core] <= 0.5).all())


def _update_fixture_manifest(manifest: Path, root: Path) -> None:
    """Refresh a fixture manifest's dims/bytes/SHA for its committed sources.

    Deliberately does *not* reuse ``sources.update_manifest``: that sweeps every
    file in its directory, and a fixture dir also holds ``make_source.py``,
    ``lut.json``, a mask and the manifest itself, none of which must become
    manifest rows. This only refreshes rows already declared.
    """
    md = manifest.read_text(encoding="utf-8")
    rows = []
    for r in sources.parse_manifest(md):
        p = root / r.file
        rows.append(sources.ManifestRow(
            r.file, sources.image_dims(p), f"{p.stat().st_size:,}",
            sources.sha256_of(p), r.origin, r.role, r.registered))
    manifest.write_text(
        sources._splice_manifest(md, sources.render_table(rows)), encoding="utf-8")
    print(f"fixture manifest refreshed: {manifest}")


def check_ingest() -> int:
    """Determinism + golden + manifest-verify for the ingestion fixture."""
    errors = sources.verify(sources_dir=INGEST_DIR, manifest_path=INGEST_MANIFEST,
                            registration_dir=INGEST_REG_DIR,
                            source_layers_path=INGEST_DIR / "_no_source_layers.json")
    if errors:
        print("INGEST manifest verification failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("ingest: fixture manifest SHA-256 + registration checks passed.")

    with tempfile.TemporaryDirectory(prefix="wh_ingest_") as tmp:
        run1, run2 = Path(tmp) / "run1", Path(tmp) / "run2"
        build_ingest(run1)
        build_ingest(run2)
        det = _diff(_snapshot(run1), _snapshot(run2))
        if det:
            print("INGEST DETERMINISM FAILURE:", file=sys.stderr)
            for p in det:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print("ingest: two runs are byte-identical.")

        if not INGEST_EXPECTED.is_dir():
            print(f"no ingest golden at {INGEST_EXPECTED}; run --update first.", file=sys.stderr)
            return 1
        reg = _diff(_snapshot(run1), _snapshot(INGEST_EXPECTED))
        if reg:
            print("INGEST REGRESSION — output differs from committed golden:", file=sys.stderr)
            for p in reg:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print("ingest: output matches committed golden.")
    return 0


def build_boundary(out_dir: Path) -> None:
    """Drive the synthetic parchment through the real S3a boundary path.

    Deliberately calls the same ``worldgen.parchment`` / ``worldgen.cells``
    functions ``generate_state_labels.py`` does — ink threshold, complement
    labelling, warp, precedence stack, mask intersection, tear repair,
    nearest-label fill, density reconciliation, sea zones — so a regression in
    any of them trips this golden. The sources are loaded through the fixture
    manifest's SHA-256 guard, exactly as the real run loads its sources.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    regs = {r.source: r for r in schema.load_registrations(BOUNDARY_REG_DIR)}
    land = raster.read_mask_png(BOUNDARY_MASK)
    w, h = BOUNDARY_CANVAS
    canvas_shape = (map_config.PROVINCES_SIZE[1], map_config.PROVINCES_SIZE[0])

    layers = []
    warped_by_source = {}
    inside_by_source = {}
    bridge_stats = []
    crop_probe: dict = {}
    for name in sorted(regs):
        reg = regs[name]
        # Load through the RGBA guard exactly as the generator does: opaque sources
        # come back with alpha None (byte-identical to load_source_image), and the
        # alpha-masked crop comes back with its footprint mask.
        rgb, alpha = sources.load_source_image_rgba(name, sources_dir=BOUNDARY_DIR,
                                                    manifest_path=BOUNDARY_MANIFEST)
        valid = alpha > 0 if alpha is not None else None
        # Scale the ink window with the source, so the half-scale sibling sees the
        # same neighbourhood in map terms rather than twice as much of the map.
        win = max(5, int(round(21 * rgb.shape[1] / 320)) | 1)
        min_area = max(10, 40 * rgb.shape[1] // 320)
        ink = parchment.ink_mask(rgb, window=win, offset=10)
        if valid is not None:
            ink = ink | ~valid   # transparent = barrier, no cell there (generator parity)
        # Mirror generate_state_labels.py's ink_bridged path so a regression in
        # glyph_mask/label_blobs trips this golden too: detect glyph-shaped ink,
        # close/dilate it into the barrier, and re-trace.
        _, before = parchment.cells_from_ink(ink, min_area)
        glyphs = parchment.glyph_mask(ink)
        blobs = parchment.label_blobs(glyphs)
        barrier = ink | (blobs > 0)
        src_cells, after = parchment.cells_from_ink(barrier, min_area)
        bridge_stats.append((name, before, after))
        lab, inside = cells.warp_cells(reg, regs, src_cells.astype(np.int32), (h, w),
                                       block_rows=32, canvas_shape=canvas_shape,
                                       src_valid=valid)
        if valid is not None:
            # The buggy path for the same crop: coverage with the alpha ignored.
            # Used only to assert the src_valid path actually shrinks coverage to
            # the opaque footprint and keeps the lower layer showing through.
            _, inside_novalid = cells.warp_cells(reg, regs, src_cells.astype(np.int32),
                                                 (h, w), block_rows=32,
                                                 canvas_shape=canvas_shape)
            crop_probe = {"name": name, "cov": inside, "cov_novalid": inside_novalid}
        warped_by_source[name] = lab
        inside_by_source[name] = inside
        layers.append((name, reg.precedence_for("boundaries"), lab, inside))

    # The src_valid / alpha-footprint path: the crop must contribute only where its
    # alpha is opaque, and a lower-precedence layer's cell must survive showing
    # through its transparent hole rather than being blanked and Voronoi-refilled
    # (the exact failure a .convert("RGB") that dropped the alpha would cause).
    if not crop_probe:
        raise RuntimeError("boundary fixture has no alpha-masked crop — the src_valid path is untested")
    cov, cov_novalid = crop_probe["cov"], crop_probe["cov_novalid"]
    if not (cov <= cov_novalid).all() or cov.sum() >= cov_novalid.sum():
        raise RuntimeError(
            "alpha-masked crop coverage was not clipped to its opaque footprint: "
            f"valid {int(cov.sum())} px vs alpha-ignored {int(cov_novalid.sum())} px"
        )
    hole = cov_novalid & ~cov & land
    stack_valid = cells.stack_layers(layers, (h, w))
    stack_novalid = cells.stack_layers(
        [(n, p, lab, cov_novalid if n == crop_probe["name"] else ins)
         for (n, p, lab, ins) in layers], (h, w))
    survived = int((stack_valid[hole] > 0).sum())
    blanked = int((stack_novalid[hole] > 0).sum())
    if not (survived > 0 and blanked == 0):
        raise RuntimeError(
            "the lower layer did not survive the crop's transparent hole: "
            f"src_valid kept {survived} labelled px there, alpha-ignored kept {blanked} "
            "(expected >0 and 0 respectively)"
        )

    # The measurement the acceptance criterion demands: bridging the fixture's
    # deliberate letter-interrupted border must recover more cells than the raw
    # ink saw. Checked on the full-scale source only — the glyph thresholds are
    # absolute pixel sizes (matching the real master's fixed resolution, not
    # scaled per source), so the half-scale alias sibling's letters fall below
    # GLYPH_MIN_HEIGHT and legitimately do not bridge; that asymmetry is itself
    # expected, not a fixture bug.
    master_before, master_after = next(
        (b, a) for n, b, a in bridge_stats if n == "synthetic_parchment.png")
    if master_after <= master_before:
        raise RuntimeError(
            f"glyph bridging did not recover more cells than plain ink tracing: {bridge_stats}"
        )
    bridge_stats = [f"{n}: {b} -> {a}" for n, b, a in bridge_stats]

    # The property the whole alias mechanism rests on: a sibling must land in the
    # same canvas *place* as its parent. Deliberately not tested as pixel-exact
    # equality — the sibling is half resolution, so its traced boundaries really
    # do fall a pixel either side of the parent's, and demanding they coincide
    # would be testing the resampler rather than the alias. What must hold is
    # that every boundary is within a couple of pixels of the corresponding one:
    # an inverted or offset alias composition misses by hundreds.
    agree = _edge_proximity(warped_by_source["synthetic_parchment.png"],
                            warped_by_source["synthetic_parchment_half.png"])
    if agree < 0.95:
        raise RuntimeError(
            f"frame_alias sibling does not land where its parent does — only "
            f"{100 * agree:.1f}% of its cell boundaries fall within 2 px of the parent's"
        )

    labels = cells.stack_layers(layers, (h, w))
    labels[~land] = 0
    labels = cells.split_disconnected(labels, wrap_x=True)
    labels = cells.fill_nearest(labels, land, wrap_x=True, pad=32)
    labels[~land] = 0
    labels = cells.split_disconnected(labels, wrap_x=True)
    labels = cells.merge_to_target(labels, BOUNDARY_LAND_CELLS, wrap_x=True)
    target = int(land.sum() // BOUNDARY_LAND_CELLS)
    labels = cells.split_large(labels, int(target * 2.2), target, wrap_x=True)
    labels = cells.merge_small(labels, int(target * 0.35), wrap_x=True)
    labels = cells.split_disconnected(labels, wrap_x=True)
    labels = cells.merge_small(labels, 20, wrap_x=True)
    labels = cells.split_disconnected(labels, wrap_x=True)
    n_land = int(labels.max())

    sea = cells.sea_zones(~land, BOUNDARY_SEA_ZONES, wrap_x=True)
    labels[~land] = sea[~land] + n_land
    if int((labels == 0).sum()):
        raise RuntimeError("boundary fixture left pixels unlabelled")
    cells.write_labels(out_dir / "state_labels.png", labels)

    areas = np.bincount(labels.ravel(), minlength=n_land + int(sea.max()) + 1)
    coastal = cells.coastal_labels(labels, land, wrap_x=True)
    index = {
        "canvas": list(BOUNDARY_CANVAS),
        "land_cells": n_land,
        "sea_cells": int(sea.max()),
        "cells": [
            {"label": i, "kind": "land" if i <= n_land else "sea",
             "key": (f"STATE_FIXTURE_{i:03d}" if i <= n_land else f"STATE_SEA_{i - n_land:03d}"),
             # The fixture has no macro source, so every land cell takes macro 1 —
             # enough for the --labels lint's "every land cell has a macro" check
             # to be exercised without inventing a second annotated image.
             "macro": 1 if i <= n_land else 0,
             "area": int(areas[i]),
             "coastal": bool(coastal[i]) if i <= n_land else True}
            for i in range(1, n_land + int(sea.max()) + 1)
        ],
    }
    (out_dir / "state_labels_index.json").write_bytes(
        (json.dumps(index, indent=1) + "\n").encode("utf-8"))

    stats = [
        f"land_px               {int(land.sum())}",
        f"land_cells            {n_land}",
        f"sea_zones             {int(sea.max())}",
        f"alias_edge_agreement  {round(agree, 4)}",
        f"min_land_area         {int(np.bincount(labels.ravel())[1:n_land + 1].min())}",
        f"max_land_area         {int(np.bincount(labels.ravel())[1:n_land + 1].max())}",
        "bridging (before -> after, per source):",
    ] + [f"  {s}" for s in bridge_stats] + [""]
    (out_dir / "boundary_stats.txt").write_bytes("\n".join(stats).encode("utf-8"))


def _edge_proximity(a: np.ndarray, b: np.ndarray, tol: int = 2) -> float:
    """Fraction of ``b``'s cell boundaries lying within ``tol`` px of one of ``a``'s."""
    from scipy import ndimage

    def edges(x: np.ndarray) -> np.ndarray:
        e = np.zeros(x.shape, dtype=bool)
        e[:, :-1] |= x[:, :-1] != x[:, 1:]
        e[:-1, :] |= x[:-1, :] != x[1:, :]
        return e

    ea, eb = edges(a), edges(b)
    if not eb.any():
        return 0.0
    near = ndimage.binary_dilation(ea, np.ones((2 * tol + 1, 2 * tol + 1), bool))
    return float(near[eb].mean())


def check_boundary() -> int:
    """Determinism + golden + manifest-verify for the boundary fixture."""
    errors = sources.verify(sources_dir=BOUNDARY_DIR, manifest_path=BOUNDARY_MANIFEST,
                            registration_dir=BOUNDARY_REG_DIR,
                            source_layers_path=BOUNDARY_DIR / "_no_source_layers.json")
    if errors:
        print("BOUNDARY manifest verification failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("boundary: fixture manifest SHA-256 + registration checks passed.")

    with tempfile.TemporaryDirectory(prefix="wh_boundary_") as tmp:
        run1, run2 = Path(tmp) / "run1", Path(tmp) / "run2"
        build_boundary(run1)
        build_boundary(run2)
        det = _diff(_snapshot(run1), _snapshot(run2))
        if det:
            print("BOUNDARY DETERMINISM FAILURE:", file=sys.stderr)
            for p in det:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print("boundary: two runs are byte-identical.")

        if not BOUNDARY_EXPECTED.is_dir():
            print(f"no boundary golden at {BOUNDARY_EXPECTED}; run --update first.", file=sys.stderr)
            return 1
        reg = _diff(_snapshot(run1), _snapshot(BOUNDARY_EXPECTED))
        if reg:
            print("BOUNDARY REGRESSION — output differs from committed golden:", file=sys.stderr)
            for p in reg:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print("boundary: output matches committed golden.")

        import validate_map
        errs = validate_map.validate_labels(
            labels_path=BOUNDARY_EXPECTED / "state_labels.png",
            mask_path=BOUNDARY_MASK,
            index_path=BOUNDARY_EXPECTED / "state_labels_index.json",
            wrap_x=True,
            # Scaled to the fixture canvas: 256x112 against the real 8192x3616 is
            # a 1024x area ratio, so the real 256 px floor is well under a pixel
            # here. 20 px still catches a degenerate cell at this size.
            min_cell_area=20,
        )
        if errs:
            print("BOUNDARY --labels lint failed:", file=sys.stderr)
            for e in errs:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print("boundary: --labels lint passed on the golden layer.")
    return 0


def _selfcheck_cells() -> None:
    """Wrap-aware component labelling and the nearest-label fill, in isolation.

    The seam is where a label layer goes wrong invisibly: a landmass split at
    x=0/x=W-1 becomes two states that look correct on every map mode and are
    wrong in every adjacency. Pinning it here means the fixture fails rather than
    the game.
    """
    a = np.zeros((8, 16), dtype=np.int32)
    a[2:6, 14:] = 7
    a[2:6, :2] = 7
    comp = cells.components(a, wrap_x=True)
    assert len(np.unique(comp[a == 7])) == 1, "a label crossing the seam is one component"
    comp_nowrap = cells.components(a, wrap_x=False)
    assert len(np.unique(comp_nowrap[a == 7])) == 2, "...and two when x does not wrap"

    b = np.zeros((6, 12), dtype=np.int32)
    b[3, 0] = 1
    b[3, 11] = 2
    within = np.ones(b.shape, dtype=bool)
    filled = cells.fill_nearest(b, within, wrap_x=True, pad=6)
    assert int(filled[3, 10]) == 2 and int(filled[3, 1]) == 1
    assert (filled != 0).all(), "the fill must leave nothing unlabelled"


def _selfcheck_mask_component_sizes() -> None:
    """`raster.mask_component_sizes` agrees with the pixel-set BFS it replaces.

    `validate_map.py`'s degenerate-province check used to run
    `connected_components` (a pure-Python BFS over `(x, y)` tuples) on every
    province colour; a several-million-pixel out-of-scope placeholder built
    enough tuples/sets to raise a `MemoryError`. `mask_component_sizes` is the
    vectorized replacement for provinces above that size — this pins that it
    reports the same component count and sizes as the BFS on a contiguous
    blob, a genuinely torn province, and a component that only connects
    through the x=0/x=width-1 wrap seam (where a bug would most likely hide).
    """
    def bfs_sizes(mask: np.ndarray, wrap_x: bool) -> list[int]:
        h, w = mask.shape
        pixels = [(x, y) for y in range(h) for x in range(w) if mask[y, x]]
        comps = connected_components(pixels, w, h, wrap_x)
        return sorted((len(c) for c in comps), reverse=True)

    def vec_sizes(mask: np.ndarray, wrap_x: bool) -> list[int]:
        return sorted(raster.mask_component_sizes(mask, wrap_x), reverse=True)

    # One contiguous blob.
    a = np.zeros((8, 16), dtype=bool)
    a[2:6, 4:10] = True
    assert vec_sizes(a, True) == bfs_sizes(a, True) == [24]

    # Genuinely torn into two same-coloured pieces, away from the seam.
    b = np.zeros((8, 16), dtype=bool)
    b[1:3, 2:4] = True   # 4 px
    b[5:7, 9:13] = True  # 8 px
    assert vec_sizes(b, True) == bfs_sizes(b, True) == [8, 4]

    # Only connects across the x=0/x=width-1 seam.
    c = np.zeros((8, 16), dtype=bool)
    c[2:6, 14:] = True
    c[2:6, :2] = True
    assert vec_sizes(c, True) == bfs_sizes(c, True) == [16]
    # ...and is two components when x does not wrap.
    assert vec_sizes(c, False) == bfs_sizes(c, False) == [8, 8]


def _selfcheck_segment_lakes() -> None:
    """The enclosed-water keep rule, in isolation (no golden needed).

    Pins the property generate_heightmap.py relies on: keep the open ocean and
    every seeded body, fill every other enclosed body to land — and that the seam
    merge is wrap-aware, so seeding one side of a body split across x=0/x=W-1
    keeps both halves.
    """
    # Ocean strip on the left (largest water component), plus two enclosed lakes:
    # one seeded (kept), one not (filled).
    land = np.ones((12, 20), dtype=bool)
    land[:, :6] = False          # open ocean
    land[3:5, 10:12] = False     # lake A — seeded, must survive
    land[8:10, 15:17] = False    # lake B — unseeded, must fill
    out = segment.keep_ocean_and_lakes(land, [(10, 3)], wrap_x=False)
    assert not out[0, 0], "the open ocean must stay water"
    assert not out[3, 10], "a keep-seeded enclosed body must stay water"
    assert out[8, 15], "an unseeded enclosed body must fill to land"
    assert (out | ~land).all(), "the keep step is additive — it must never remove land"

    # A body split across the wrap seam is one component: seeding either side keeps
    # both halves.
    w = np.ones((6, 10), dtype=bool)
    w[0, :] = False              # ocean row (largest water component)
    w[2:4, 0] = False            # left half of a seam-wrapped body
    w[2:4, 9] = False            # right half
    out2 = segment.keep_ocean_and_lakes(w, [(9, 2)], wrap_x=True)
    assert not out2[2, 0] and not out2[2, 9], \
        "seeding one side of a seam-wrapped body must keep both halves"
    # Without wrap the two halves are separate; seeding the right leaves the left
    # unseeded, so it fills.
    out3 = segment.keep_ocean_and_lakes(w, [(9, 2)], wrap_x=False)
    assert out3[2, 0] and not out3[2, 9], \
        "without wrap the seam halves are distinct — only the seeded one survives"


def _selfcheck_rivers() -> None:
    """Rasterize + validate a tiny synthetic river network (no golden needed).

    Covers worldgen.rivers end to end: a trunk reaching the sea, a tributary
    merging into it, and — the part most worth pinning — that an invalid geometry
    (a mouth stranded inland) is *rejected*, so the generator's safety net cannot
    rot into a no-op.
    """
    from worldgen import rivers as rl

    land = np.ones((40, 60), dtype=bool)
    land[:, 55:] = False  # a sea strip on the right edge
    palette = rl.RiverPalette({"land": rl.LAND, "sea": rl.SEA, "source": rl.SOURCE},
                              (3, 4, 6, 8), [(0, 0, 0)] * 256)

    trunk = schema.RiverStream("trunk", [(10, 20), (30, 20), (54, 20)], "sea", 6)
    trib = schema.RiverStream("trib", [(25, 5), (28, 14), (30, 20)], "confluence", 4)
    idx = rl.rasterize([trunk, trib], land, palette, wrap_x=False)
    assert int((idx == rl.SOURCE).sum()) == 2, "one source per stream"
    assert (idx[:, 55:] == rl.SEA).all(), "sea strip preserved"
    assert rl.count_2x2_blocks(idx, wrap_x=False) <= rl.MAX_2X2_BLOCKS

    stranded = schema.RiverStream("bad", [(10, 30), (20, 30), (30, 30)], "sea", 3)
    try:
        rl.rasterize([stranded], land, palette, wrap_x=False)
    except rl.RiverError:
        pass
    else:  # pragma: no cover
        raise AssertionError("rivers must reject a sea mouth that never reaches water")


def _selfcheck_river_extraction() -> None:
    """Drawn river extraction (worldgen.river_network), in isolation (no golden).

    Pins what generate_rivers.py relies on (board #3703 + the #3742 lake model): a
    blue Y-junction yields one green source per headwater with a red MERGE at the
    confluence (not a per-segment source explosion); streams run source-first and
    name by anchor; an inland-terminating river is a valid ENDORHEIC sink; a
    lake→sea river is one sea stream with a lake-fed source (not a fork); a DELTA
    (one trunk, two sea mouths) and a RIVER-ISLAND (split then rejoin) are valid
    and paint yellow split markers; only a sourceless closed ring is an error; a
    short spur is pruned; a seam-crossing stem extracts under wrap_x; and two runs
    are byte-identical.
    """
    from skimage.draw import line as _line
    from worldgen import river_network as rn
    from worldgen import rivers as rl

    def blue(H, W, segs):
        img = np.full((H, W, 3), 180, dtype=np.uint8)
        for (y0, x0, y1, x1) in segs:
            rr, cc = _line(y0, x0, y1, x1)
            img[rr, cc] = (0, 0, 255)
        return img

    H, W = 48, 64
    land = np.ones((H, W), bool)
    land[:, 58:] = False  # sea strip on the right

    # Y junction: two headwaters merge into one trunk that reaches the sea.
    net = rn.blue_network(blue(H, W, [(12, 8, 24, 28), (36, 8, 24, 28), (24, 28, 24, 57)]),
                          dilate=1)
    res = rn.extract_streams(net, land, wrap_x=False)
    assert len(res.streams) == 2, f"Y network -> 2 streams (trunk + tributary), got {len(res.streams)}"
    assert sorted(s.mouth for s in res.streams) == ["confluence", "sea"], \
        [s.mouth for s in res.streams]
    for s in res.streams:  # source-first: points[0] is the inland spring
        assert land[s.points[0][1], s.points[0][0]], "source must be on land"
    # One green source per HEADWATER (== 2), and one red MERGE — vanilla's model,
    # not a source per segment.
    pal = rl.RiverPalette({"land": rl.LAND, "sea": rl.SEA, "source": rl.SOURCE},
                          (3, 4, 6, 8), [(0, 0, 0)] * 256)
    idx = rl.rasterize(res.streams, land, pal, wrap_x=False)
    assert int((idx == rl.SOURCE).sum()) == 2, "one green source per headwater"
    assert int((idx == rl.MERGE).sum()) == 1, "one red merge at the confluence"
    # The trunk (Strahler order 2) renders wider than a headwater.
    sea_stream = next(s for s in res.streams if s.mouth == "sea")
    assert sea_stream.width >= 4, f"trunk should widen downstream, got {sea_stream.width}"

    # Naming by anchor: an anchor on the trunk names that stream.
    named = rn.extract_streams(net, land, wrap_x=False,
                               names=[schema.CanonRiverName("Reik", (45, 24), None, None, "")])
    assert "Reik" in {s.name for s in named.streams}, "anchor must name a stream"

    # Determinism: two runs byte-identical.
    res2 = rn.extract_streams(net, land, wrap_x=False)
    sig = lambda r: [(s.name, tuple(s.points), s.mouth, s.width) for s in r.streams]
    assert sig(res) == sig(res2), "two runs must be byte-identical"

    # An inland line reaching NO water is a valid ENDORHEIC river now (board
    # #3742: the Marshes of Madness are a drainage sink), not an error: it dries
    # up inland, one source and one endorheic mouth, no MERGE marker.
    endo = rn.extract_streams(rn.blue_network(blue(H, W, [(24, 8, 24, 30)]), dilate=1),
                              np.ones((H, W), bool), wrap_x=False)
    assert len(endo.streams) == 1 and endo.streams[0].mouth == "endorheic", \
        f"a fully-inland river must be one endorheic stream, got {[s.mouth for s in endo.streams]}"
    idx_e = rl.rasterize(endo.streams, np.ones((H, W), bool), pal, wrap_x=False)
    assert int((idx_e == rl.MERGE).sum()) == 0, "an endorheic river carries no merge marker"

    # A lake→sea river is NOT a fork: the lake end is a source (lake-fed), the
    # ocean end is the mouth. Two independent water bodies distinguished by ocean
    # vs lake (board #3742).
    landL = np.ones((H, W), bool)
    landL[:, 58:] = False               # ocean strip on the right
    lakeL = np.zeros((H, W), bool)
    lakeL[20:25, 8:13] = True           # an enclosed lake block on the left
    landL[lakeL] = False                # a lake is water in the land/sea mask
    netL = rn.blue_network(blue(H, W, [(22, 13, 22, 57)]), dilate=1)
    resL = rn.extract_streams(netL, landL, lake=lakeL, wrap_x=False)
    assert len(resL.streams) == 1 and resL.streams[0].mouth == "sea", \
        f"lake→sea must be one sea stream (not a fork), got {[s.mouth for s in resL.streams]}"
    (ssx, ssy) = resL.streams[0].points[0]
    assert any(lakeL[ny, nx] for ny, nx in rn._neighbors8(ssy, ssx, H, W, False)), \
        "the source of a lake-fed river sits on the lake shore"
    oceanL = (~landL) & (~lakeL)
    rl.rasterize(resL.streams, landL, pal, wrap_x=False, ocean=oceanL)  # lake-fed source is legal

    # A closed ring with no source/mouth (a "moat") is still a hard error.
    loop = blue(H, W, [(10, 10, 10, 30), (10, 30, 30, 30), (30, 30, 30, 10), (30, 10, 10, 10)])
    _assert_river_error(lambda: rn.extract_streams(
        rn.blue_network(loop, dilate=1), land, wrap_x=False), "loop")

    # A DELTA — one trunk splitting into two distributaries that each reach the
    # sea — is valid (board #3703 split support): two sea mouths, a yellow split
    # marker, one green source (the trunk's headwater).
    delta = blue(H, W, [(24, 8, 24, 28), (24, 28, 10, 57), (24, 28, 38, 57)])
    res_d = rn.extract_streams(rn.blue_network(delta, dilate=1), land, wrap_x=False)
    assert sorted(s.mouth for s in res_d.streams).count("sea") == 2, \
        f"a delta reaches the sea twice, got {[s.mouth for s in res_d.streams]}"
    assert any(s.head == "split" for s in res_d.streams), "a delta has a split-head distributary"
    idx_d = rl.rasterize(res_d.streams, land, pal, wrap_x=False)
    assert int((idx_d == rl.SPLIT).sum()) >= 1, "a delta paints a yellow split marker (index 2)"
    assert int((idx_d == rl.SOURCE).sum()) == 1, "a delta has one green source"

    # A RIVER-ISLAND — the channel splits and rejoins around an island, then
    # reaches the sea — is valid too: a split (yellow) and a rejoin (red merge).
    island = blue(H, W, [(24, 8, 24, 20),
                         (24, 20, 16, 30), (16, 30, 24, 40),      # north arm
                         (24, 20, 32, 30), (32, 30, 24, 40),      # south arm
                         (24, 40, 24, 57)])
    res_i = rn.extract_streams(rn.blue_network(island, dilate=1), land, wrap_x=False)
    idx_i = rl.rasterize(res_i.streams, land, pal, wrap_x=False)
    assert int((idx_i == rl.SPLIT).sum()) >= 1, "the island's split paints a yellow marker"
    assert int((idx_i == rl.MERGE).sum()) >= 1, "the island's rejoin paints a red merge"
    assert int((idx_i == rl.SOURCE).sum()) == 1, "one green source (the headwater)"

    # A sea-to-sea channel has no auto-derivable source -> error; a manual flow
    # override orients it (mouth = furthest in the flow direction; the opposite,
    # coastal, end is the source, and its inland-source rule is waived).
    land2 = np.ones((H, W), bool)
    land2[:, :3] = False    # ocean on the left
    land2[:, 58:] = False   # ocean on the right
    net_ss = rn.blue_network(blue(H, W, [(24, 3, 24, 57)]), dilate=1)
    _assert_river_error(lambda: rn.extract_streams(net_ss, land2, wrap_x=False), "no inland source")
    res_ov = rn.extract_streams(net_ss, land2, overrides=[schema.RiverOverride((30, 24), "W", "")],
                                wrap_x=False)
    assert len(res_ov.streams) == 1 and res_ov.streams[0].mouth == "sea", "override -> one sea stream"
    assert res_ov.streams[0].points[0][0] > 40, \
        f"flow W means the source is the eastern end, got {res_ov.streams[0].points[0]}"
    assert res_ov.streams[0].coastal_source, "the override source is flagged coastal"
    rl.rasterize(res_ov.streams, land2, pal, wrap_x=False, ocean=~land2)  # coastal source waived, no raise

    # A short spur off a line is pruned, not turned into a fake headwater.
    spur = blue(H, W, [(24, 8, 24, 57), (24, 30, 20, 30)])
    res_spur = rn.extract_streams(rn.blue_network(spur, dilate=1), land, wrap_x=False)
    assert len(res_spur.streams) == 1 and res_spur.streams[0].mouth == "sea", \
        f"spur must be pruned -> 1 sea stream, got {len(res_spur.streams)}"

    # A seam-crossing stem extracts under wrap_x (wrap-aware skeleton + graph).
    Hw, Ww = 24, 40
    landw = np.ones((Hw, Ww), bool)
    landw[8:13, 10:15] = False  # a sea block for the mouth
    netw = rn.blue_network(blue(Hw, Ww, [(10, 25, 10, 39), (10, 0, 10, 9)]), dilate=1)
    resw = rn.extract_streams(netw, landw, wrap_x=True)
    assert len(resw.streams) == 1 and resw.streams[0].mouth == "sea", "wrap stem -> 1 sea stream"
    xs = {x for s in resw.streams for (x, _y) in s.points}
    assert min(xs) == 0 and max(xs) == Ww - 1, "the stem must span the x=0/x=w-1 seam"


def _assert_river_error(fn, needle: str) -> None:
    from worldgen import river_network as rn
    try:
        fn()
    except rn.RiverNetworkError as e:
        assert needle in str(e), f"expected '{needle}' in error, got: {e}"
        return
    raise AssertionError(f"expected a RiverNetworkError mentioning '{needle}'")  # pragma: no cover


def _selfcheck_river_validator() -> None:
    """The validate_map._check_rivers check, on synthetic index arrays — a passing
    rivers.png plus failing cases, so the check can actually fail (board #3703 +
    the #3742 lake / endorheic / split extensions)."""
    import validate_map as vm

    H, W = 10, 14
    land = np.ones((H, W), bool)
    land[:, 9:] = False        # ocean strip on the right (x >= 9)
    lake = np.zeros((H, W), bool)
    lake[7:9, 2:4] = True      # a small inland lake
    land[lake] = False         # a lake is water in the land/sea mask
    ocean = (~land) & (~lake)
    LAND, SEA = 255, 254

    def base():
        a = np.full((H, W), LAND, dtype=np.uint8)
        a[~land] = SEA
        return a

    # A clean river: inland green source, blue body, mouth adjacent to the sea.
    ok = base()
    ok[2, 2] = 0            # source (inland)
    ok[2, 3:9] = 4          # body to x=8, adjacent to ocean at x=9
    assert vm._check_rivers(ok, land, wrap_x=False, ocean=ocean) == [], \
        f"a clean rivers.png must pass, got {vm._check_rivers(ok, land, wrap_x=False, ocean=ocean)}"

    # A lake-fed source (green pixel on the lake shore, not the ocean) passes.
    lakefed = base()
    lakefed[7, 4] = 0          # x=4 is beside the lake (x=3), far from the ocean
    lakefed[7, 5:9] = 4        # flows out to the ocean
    assert vm._check_rivers(lakefed, land, wrap_x=False, ocean=ocean) == [], \
        f"a lake-fed source must pass, got {vm._check_rivers(lakefed, land, wrap_x=False, ocean=ocean)}"

    # An ENDORHEIC river ending inland (no water at the mouth) is now legal.
    endo = base()
    endo[5, 3] = 0
    endo[5, 4:7] = 4        # ends at x=6, nowhere near water — a dry sink
    assert vm._check_rivers(endo, land, wrap_x=False, ocean=ocean) == [], \
        f"an endorheic river ending inland must pass, got {vm._check_rivers(endo, land, wrap_x=False, ocean=ocean)}"

    # A river pixel on the sea fails.
    bad_sea = ok.copy()
    bad_sea[2, 10] = 4
    assert vm._check_rivers(bad_sea, land, wrap_x=False, ocean=ocean), "a river pixel on sea must fail"

    # A green source ON the ocean coast fails; a lake-fed one passes.
    on_coast = base()
    on_coast[4, 8] = 0      # x=8 is adjacent to ocean x=9
    on_coast[4, 3:8] = 4
    assert any("sea coast" in e for e in vm._check_rivers(on_coast, land, wrap_x=False, ocean=ocean)), \
        "a source on the ocean coast must fail"

    # A yellow split marker (2) touching no other river fails.
    lone_split = base()
    lone_split[8, 6] = 2
    assert any("split" in e for e in vm._check_rivers(lone_split, land, wrap_x=False, ocean=ocean)), \
        "a split marker touching no stream must fail"

    # An index outside the vanilla semantic set fails.
    bad_idx = ok.copy()
    bad_idx[2, 5] = 99
    assert any("outside the vanilla semantic set" in e
               for e in vm._check_rivers(bad_idx, land, wrap_x=False, ocean=ocean)), \
        "an out-of-set index must fail"


def _selfcheck_sea_zones() -> None:
    """Drawn sea-zone extraction (worldgen.sea_zones), in isolation (no golden).

    Pins the property generate_sea_zones.py relies on: a purple line drawn *in
    the water* splits it into separate zones, a purple mark drawn *on land* does
    not, every water pixel ends up labelled and no land pixel does, and two runs
    are byte-identical.
    """
    from worldgen import sea_zones as sz

    H, W = 16, 32
    land = np.zeros((H, W), dtype=bool)
    land[:, 8:12] = True                     # a vertical land strip: west + east water
    drawn = np.full((H, W, 3), 180, dtype=np.uint8)
    drawn[:, 22] = (127, 0, 255)             # purple divider across the east water
    drawn[8, 9] = (127, 0, 255)              # a purple mark on land — must not split water

    zones = sz.extract(land, drawn, dilate=1, merge_floor=1, wrap_x=False)
    assert int(zones.max()) == 3, f"west + (east split in two) = 3 zones, got {zones.max()}"
    assert (zones[~land] > 0).all(), "every water pixel must be labelled"
    assert (zones[land] == 0).all(), "no land pixel may be labelled"
    z2 = sz.extract(land, drawn, dilate=1, merge_floor=1, wrap_x=False)
    assert np.array_equal(zones, z2), "two runs must be byte-identical"


def _selfcheck_land_provinces() -> None:
    """Drawn land-province cut (worldgen.land_provinces), in isolation (no golden).

    Pins the properties generate_provinces.py relies on: a magenta line drawn on
    land splits it into regions while a magenta mark in water is ignored; a
    landmass dense with interior magenta is classed drawn and one bare of it is a
    placeholder; ``subdivide`` cuts a drawn region into several provinces that
    never cross the magenta boundary (each province lies in one region) while a
    placeholder region stays a single province; every land pixel is labelled and
    no water pixel is; and two runs are byte-identical.
    """
    from worldgen import land_provinces as lp

    H, W = 20, 40
    land = np.zeros((H, W), dtype=bool)
    land[2:18, 2:18] = True          # drawn landmass (interior magenta line)
    land[2:18, 25:35] = True         # placeholder landmass (no magenta)
    drawn = np.full((H, W, 3), 180, dtype=np.uint8)
    drawn[2:18, 9] = (255, 0, 255)   # magenta divider through the drawn landmass
    drawn[10, 21] = (255, 0, 255)    # a magenta mark in the water — must be ignored

    reg = lp.regions(land, drawn, dilate=1, merge_floor=1, wrap_x=False)
    assert int(reg.max()) == 3, f"2 drawn regions + 1 placeholder = 3, got {reg.max()}"
    assert (reg[land] > 0).all(), "every land pixel must carry a region"
    assert (reg[~land] == 0).all(), "no water pixel may carry a region (water mark ignored)"

    dmask = lp.drawn_mask(land, lp.magenta_lines(drawn), wrap_x=False,
                          interior_dist=2, reach=10)
    # The interior-magenta blob covers the drawn landmass and reaches nowhere near
    # the bare one, so subdivide subdivides the first and keeps the second whole.
    assert dmask[2:18, 25:35].mean() < 0.5, "the bare landmass must be classed placeholder"
    assert dmask[2:18, 2:18].mean() > 0.5, "the interior-magenta landmass must be classed drawn"

    prov, is_placeholder, reg_of, is_archipelago = lp.subdivide(
        reg, land, dmask, target=6, wrap_x=False, min_area=1)
    assert int(prov.max()) >= 6, f"drawn regions must subdivide, got {prov.max()} provinces"
    assert not is_archipelago.any(), "no province here is an island-override merge"
    assert (prov[land] > 0).all() and (prov[~land] == 0).all(), "provinces must tile land only"
    # No province crosses a magenta boundary: each province lies in one region.
    for lab in range(1, int(prov.max()) + 1):
        regs_here = np.unique(reg[prov == lab])
        assert len(regs_here) == 1, f"province {lab} spans regions {regs_here.tolist()}"
    # The placeholder landmass stays exactly one province, flagged out-of-scope.
    placeholder_provs = np.unique(prov[2:18, 25:35])
    assert len(placeholder_provs) == 1, \
        f"placeholder landmass must be one province, got {placeholder_provs.tolist()}"
    assert is_placeholder[placeholder_provs[0]], "the placeholder province must be flagged"
    # A subdivided (drawn) province must NOT be flagged out-of-scope.
    drawn_prov = int(prov[9, 5])  # inside the drawn landmass
    assert not is_placeholder[drawn_prov], "a drawn Old-World province must not be flagged"

    # The region grouping generate_provinces.py serializes into land_regions_index.json:
    # reg_of maps every province label to exactly one region, and the inversion is total.
    assert int(reg_of[0]) == 0, "water must map to region 0"
    groups: dict[int, list[int]] = {}
    for lab in range(1, int(prov.max()) + 1):
        r = int(reg_of[lab])
        assert r >= 1, f"province {lab} maps to no region (reg_of={r})"
        groups.setdefault(r, []).append(lab)
    grouped = sorted(p for members in groups.values() for p in members)
    assert grouped == list(range(1, int(prov.max()) + 1)), \
        "the region grouping must cover every land province exactly once (totality)"
    # The placeholder landmass's province is the sole member of its own region.
    ph = int(placeholder_provs[0])
    assert groups[int(reg_of[ph])] == [ph], \
        "the placeholder province must be the only member of its region"

    p2, ip2, ro2, ia2 = lp.subdivide(reg, land, dmask, target=6, wrap_x=False, min_area=1)
    assert np.array_equal(prov, p2), "two runs must be byte-identical"
    assert np.array_equal(is_placeholder, ip2), "placeholder flags must be byte-identical too"
    assert np.array_equal(reg_of, ro2), "the region grouping must be byte-identical too"
    assert np.array_equal(is_archipelago, ia2), "archipelago flags must be byte-identical too"


def _selfcheck_province_merges() -> None:
    """Tiny-island override merge (worldgen.land_provinces), in isolation.

    Pins the properties generate_provinces.py relies on: province_merge_zones
    reads a merge-line network's connected components as distinct zone ids
    (board #4609 — a line directly connecting islands, superseding an earlier
    enclosing-ring idiom that needed a geometric splitter for touching rings
    and never reliably got it right for every shape) and a blank source as no
    zones at all; merge_province_zones unions every region caught under the
    same zone into one (a line touching only one region is a no-op); the merge
    result still tiles the land exactly and is byte-identical across two runs;
    and subdivide's connectivity guard keeps a merged, non-contiguous archipelago
    as exactly one province even when its area earns it more than one seat.
    """
    from worldgen import land_provinces as lp

    H, W = 20, 40
    land = np.zeros((H, W), dtype=bool)
    land[2:18, 2:18] = True          # main landmass, undivided
    land[1, 30] = True               # islet A, far from the landmass
    land[1, 34] = True               # islet B, far from the landmass and from A
    drawn = np.full((H, W, 3), 180, dtype=np.uint8)  # no magenta anywhere

    # A blank overrides source yields no zones at all.
    blank = np.full((H, W, 3), 255, dtype=np.uint8)
    assert not lp.province_merge_zones(blank, land, wrap_x=False).any(), \
        "a blank source must draw no zones"

    # A line directly connecting the two islets puts them in the same zone.
    overrides = np.full((H, W, 3), 255, dtype=np.uint8)
    overrides[1, 30:35] = (255, 0, 0)
    zones = lp.province_merge_zones(overrides, land, wrap_x=False)
    assert int(zones.max()) == 1, f"one connecting line must be one zone, got {zones.max()}"
    assert zones[1, 30] == 1 and zones[1, 34] == 1, \
        "both islets must fall on the connecting line's zone"

    # A line drawn far from every islet and the mainland leaves them all at
    # zone 0 — "no forced merge here" — rather than silently roping one in.
    near_miss = np.full((H, W, 3), 255, dtype=np.uint8)
    near_miss[15, 25:30] = (255, 0, 0)  # clear of both islets (row 1) and the mainland (cols 2-18)
    nz = lp.province_merge_zones(near_miss, land, wrap_x=False)
    assert nz[1, 30] == 0 and nz[1, 34] == 0, \
        "an unconnected line must not merge an islet it never touches"

    # Two separate line networks (not connected to each other) get distinct
    # zone ids; determinism holds across two runs.
    two_lines = np.full((H, W, 3), 255, dtype=np.uint8)
    two_lines[1, 30:32] = (255, 0, 0)          # touches islet A only
    two_lines[10, 2:5] = (255, 0, 0)           # touches the mainland only, far from islet A's line
    tz = lp.province_merge_zones(two_lines, land, wrap_x=False)
    assert tz[1, 30] != 0 and tz[10, 2] != 0 and tz[1, 30] != tz[10, 2], \
        "two disconnected merge-line networks must keep distinct zones"
    tz2 = lp.province_merge_zones(two_lines, land, wrap_x=False)
    assert np.array_equal(tz, tz2), "two runs must be byte-identical"

    reg = lp.regions(land, drawn, dilate=1, merge_floor=1, wrap_x=False)
    assert int(reg.max()) == 3, f"main landmass + 2 islets = 3, got {reg.max()}"
    islet_a, islet_b = int(reg[1, 30]), int(reg[1, 34])
    assert islet_a != islet_b, "the two islets must start as separate regions"

    merged = lp.merge_province_zones(reg, land, zones, wrap_x=False)
    assert int((merged == 0).sum()) == int((~land).sum()), "the merge must still tile the land exactly"
    assert merged[1, 30] == merged[1, 34], "both islets must end up under one region id"
    m2 = lp.merge_province_zones(reg, land, zones, wrap_x=False)
    assert np.array_equal(merged, m2), "two runs must be byte-identical"

    # A circle drawn over a single region is a no-op.
    single = np.zeros((H, W), dtype=np.int32)
    single[1, 30] = 1
    unchanged = lp.merge_province_zones(reg, land, single, wrap_x=False)
    assert np.array_equal(unchanged, reg), "a circle over one region must change nothing"

    # regions() applies the override itself when given province_merges=.
    reg_direct = lp.regions(land, drawn, dilate=1, merge_floor=1, wrap_x=False,
                            province_merges=zones)
    assert reg_direct[1, 30] == reg_direct[1, 34], \
        "regions() must apply province_merges internally"

    # subdivide's connectivity guard: a merged, disconnected region (two islets
    # sharing one label) must never be cut, no matter how many seats its area
    # would otherwise earn — tested directly against the private helper so the
    # assertion doesn't hinge on the largest-remainder seat allocation's output.
    merged_id = int(merged[1, 30])
    assert not lp._is_connected(merged == merged_id, wrap_x=False), \
        "two islets merged under one label must read as disconnected"
    # A normal, single-piece region reads as connected.
    other_id = next(i for i in range(1, int(merged.max()) + 1) if i != merged_id)
    assert lp._is_connected(merged == other_id, wrap_x=False), \
        "an ordinary contiguous region must read as connected"

    # override_fused_labels is the discriminator subdivide uses to tell an
    # island-override archipelago (keep whole) from a merge-fused disconnected
    # region (cut per piece). Assert its CONTENT, not just that it runs: the
    # merged islets' label is the only archipelago-exempt label here. This is the
    # sole exerciser of the archipelago branch on a machine without the island
    # source (province_merges=None ⟹ empty set in a bare local run).
    keep_whole = lp.override_fused_labels(merged, land, zones)
    assert keep_whole == {merged_id}, \
        f"override_fused_labels must return exactly the archipelago label, got {keep_whole}"

    # End to end through subdivide(): the merged archipelago ships as exactly
    # one non-contiguous province, correctly flagged is_archipelago — vanilla
    # ships this shape for real (Micronesia's province colour spans 23
    # disconnected blobs), so this is the deliberate case validate_map.py's
    # own connectivity check must let through instead of rejecting. keep_whole
    # is required now: without it the default-empty set would cut the archipelago
    # per piece (the #3664 behaviour for a merge-fused region).
    dmask = lp.drawn_mask(land, lp.magenta_lines(drawn), wrap_x=False,
                          interior_dist=0, reach=1)
    prov, is_placeholder, reg_of, is_archipelago = lp.subdivide(
        merged, land, dmask, target=merged.max(), wrap_x=False, min_area=1,
        keep_whole=keep_whole)
    island_prov = int(prov[1, 30])
    assert island_prov == int(prov[1, 34]), \
        "the merged islets must ship as exactly one province"
    assert is_archipelago[island_prov], "the merged province must be flagged archipelago"
    main_prov = int(prov[9, 5])
    assert not is_archipelago[main_prov], "an ordinary contiguous province must not be flagged"


def _selfcheck_merge_fused() -> None:
    """Merge-fused disconnected region cut per piece (#3664), in isolation.

    Pins the #3664 fix: a drawn region that was fused across water (two
    non-touching landmasses under one label) is cut **per
    connected piece** — each piece gets its own provinces, no province spans the
    two pieces, none is flagged an archipelago — while the SAME region, told to
    stay whole via ``keep_whole``, ships as exactly one non-contiguous province.
    ``keep_whole`` (from ``override_fused_labels``) is what tells the two apart;
    connectivity alone cannot. Two runs of the cut path are byte-identical.
    """
    from worldgen import land_provinces as lp

    H, W = 20, 40
    land = np.zeros((H, W), dtype=bool)
    land[2:18, 2:10] = True          # west block
    land[2:18, 14:22] = True         # east block, separated by water (cols 10-13)
    drawn = np.full((H, W, 3), 180, dtype=np.uint8)
    # A short interior magenta stroke in each block that does NOT span it, so each
    # block stays one region yet is classed drawn (interior magenta present).
    drawn[8:12, 5] = (255, 0, 255)
    drawn[8:12, 17] = (255, 0, 255)

    reg = lp.regions(land, drawn, dilate=1, merge_floor=1, wrap_x=False)
    assert int(reg.max()) == 2, f"two separate blocks = 2 regions, got {reg.max()}"

    # Fuse the two regions across the water under one label.
    reg_m = np.where(land, 1, 0).astype(reg.dtype)
    assert not lp._is_connected(reg_m == 1, wrap_x=False), \
        "the merged region must be disconnected (its halves never touch)"

    dmask = lp.drawn_mask(land, lp.magenta_lines(drawn), wrap_x=False,
                          interior_dist=1, reach=12)
    assert dmask[reg_m == 1].mean() > 0.5, "the merged region must be classed drawn"

    # keep_whole empty ⟹ merge-fused region cut per connected piece.
    prov, is_placeholder, reg_of, ia = lp.subdivide(
        reg_m, land, dmask, target=4, wrap_x=False, min_area=1, keep_whole=set())
    assert int(prov.max()) >= 2, f"a merge-fused region must be cut, got {prov.max()} provinces"
    west = set(int(p) for p in np.unique(prov[2:18, 2:10]))
    east = set(int(p) for p in np.unique(prov[2:18, 14:22]))
    assert west and east, "each block must carry at least one province"
    assert west.isdisjoint(east), \
        f"no province may span the two disconnected pieces: west {west} east {east}"
    assert not ia.any(), "a per-piece-cut merge-fused province is contiguous, never an archipelago"

    # keep_whole={1} ⟹ the SAME region stays whole as one non-contiguous province.
    provk, _, _, iak = lp.subdivide(
        reg_m, land, dmask, target=4, wrap_x=False, min_area=1, keep_whole={1})
    kept = set(int(p) for p in np.unique(provk[land]))
    assert kept == {int(provk[3, 5])}, f"a kept-whole region must be one province, got {kept}"
    assert iak[int(provk[3, 5])], "the kept-whole non-contiguous province must be flagged archipelago"

    # The cut path is byte-identical across two runs.
    prov2, _, _, _ = lp.subdivide(
        reg_m, land, dmask, target=4, wrap_x=False, min_area=1, keep_whole=set())
    assert np.array_equal(prov, prov2), "two runs of the per-piece cut must be byte-identical"

    # --- wrap_x=True is the production path (map_config.WRAP_X). The merge-fused
    # branch leans on cells.components (piece split, land_provinces.py) and
    # _is_connected (branch test) agreeing about the antimeridian seam -- two
    # independently-implemented wrap mechanisms. Exercise a seam-wrapping piece so
    # a spurious cross-seam split can't hide behind the wrap_x=False cases above. ---
    Hw, Ww = 16, 40
    landw = np.zeros((Hw, Ww), dtype=bool)
    landw[4:12, 0:5] = True           # west half of a seam-wrapping piece
    landw[4:12, 36:40] = True         # east half -- adjacent across x=0 / x=W-1
    landw[4:12, 18:24] = True         # a second, separate piece (water between)
    regw = np.where(landw, 1, 0).astype(np.int32)   # one region, two pieces
    # _is_connected and cells.components must AGREE: the region is disconnected
    # (the second block never touches the wrapping one), and the wrapping half is
    # ONE piece across the seam -- so exactly 2 pieces, not 3.
    assert not lp._is_connected(regw == 1, wrap_x=True),         "the region is two water-separated pieces -> disconnected under wrap"
    compw = cells.renumber(np.where(regw == 1,
                                    cells.components((regw == 1).astype(np.int32), True), 0))
    assert int(compw.max()) == 2,         f"cells.components must stitch the seam-wrapping half into ONE piece (2 total), got {compw.max()}"
    provw, _, _, iaw = lp.subdivide(
        regw, landw, landw.copy(), target=4, wrap_x=True, min_area=1, keep_whole=set())
    wrap_piece = set(int(p) for p in np.unique(provw[4:12, 0:5])) |         set(int(p) for p in np.unique(provw[4:12, 36:40]))
    other_piece = set(int(p) for p in np.unique(provw[4:12, 18:24]))
    assert wrap_piece and other_piece, "each piece must carry provinces"
    assert wrap_piece.isdisjoint(other_piece),         f"no province may span the two pieces across the seam: {wrap_piece} vs {other_piece}"
    assert not iaw.any(),         "a seam-wrapping province is contiguous under wrap, never flagged archipelago"


def _selfcheck_island_zone_groups() -> None:
    """A state chained across several island lines ships one province per line.

    A ``keep_whole`` region normally stays one province, but a state-level merge
    can chain several island-override lines' regions into one label. With the
    ``island_zones`` layer, ``subdivide`` gives each line-group its own province;
    a single group (or no layer) stays whole, byte-identical to before.
    """
    from worldgen import land_provinces as lp

    H, W = 12, 40
    land = np.zeros((H, W), dtype=bool)
    land[3:8, 2:6] = True      # islet A   (line 1)
    land[3:8, 10:14] = True    # islet B   (line 1, same line as A)
    land[3:8, 20:24] = True    # islet C   (line 2)
    land[3:8, 30:34] = True    # islet D   (no line: came in via a state merge)
    reg = np.where(land, 1, 0).astype(np.int32)   # one chained state region
    zones = np.zeros((H, W), dtype=np.int32)
    zones[5, 2:14] = 1
    zones[5, 20:24] = 2
    drawn = land.copy()

    def run(z, kw={1}):
        return lp.subdivide(reg, land, drawn, target=8, wrap_x=False, min_area=1,
                            keep_whole=set(kw), island_zones=z)

    prov, _, reg_of, ia = run(zones)
    a, b, c, d = (int(prov[5, x]) for x in (3, 11, 21, 31))
    assert a == b, "islets on the same island line must share one province"
    assert len({a, c, d}) == 3, f"each line-group and the unlined islet is its own province: {a, c, d}"
    assert int(prov.max()) == 3, f"exactly one province per group, got {prov.max()}"
    assert set(int(reg_of[p]) for p in (a, c, d)) == {1}, "all groups stay in the one state region"
    assert ia[a] and not ia[c], "only the two-islet group is non-contiguous"

    whole, _, _, _ = run(None)
    assert int(whole.max()) == 1, "no island_zones layer keeps the region whole (old behaviour)"

    one = np.zeros_like(zones)
    one[5, 2:34] = 1               # a single line touching every islet
    single, _, _, _ = run(one)
    assert int(single.max()) == 1, "a single group stays whole"

    prov2, _, _, _ = run(zones)
    assert np.array_equal(prov, prov2), "two runs must be byte-identical"


def _selfcheck_world_market_location() -> None:
    """validate_map._check_world_market_location (board #5520)."""
    import validate_map as vm

    def cell(rgb, kind="sea", imp=False):
        return {"color": list(rgb), "kind": kind, "impassable": imp}

    sea, land, lake, imp = (1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12)
    cells = [cell(sea), cell(land, "land"), cell(lake, "lake", True), cell(imp, "sea", True)]
    starts = {sea, imp}
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)

        def run(rgb):
            (d / "a.txt").write_text(
                'NEconomy = {\n\tWORLD_MARKET_LOCATION = "x%02X%02X%02X"\n}\n' % rgb,
                encoding="utf-8")
            return vm._check_world_market_location(d, cells, starts)

        assert run(sea) == [], "a passable sea province in sea_starts must pass"
        assert run(land), "a land colour must fail"
        assert run(lake), "a lake colour must fail"
        assert run(imp), "an impassable sea must fail"
        assert run((99, 99, 99)), "an unknown colour must fail"
        (d / "a.txt").unlink()
        assert vm._check_world_market_location(d, cells, starts) == [],             "no define present is a clean skip"


def _selfcheck_lakes() -> None:
    """Inland-lake water class (board #3742), in isolation (no golden needed).

    Pins the whole lake path: ``lakes.classify`` finds the world ocean (largest
    water body) and marks every other water component a lake, wrap-aware, keeping
    land untouched and staying deterministic; ``lakes.label`` gives one label per
    lake component; ``sea_zones.extract`` before/after grounds the defect in the
    real current behaviour (with ``exclude=None`` an enclosed body IS its own
    labelled sea zone; with ``exclude=lake`` those pixels stay unlabelled and the
    tiling assertion counts land+lake); ``lakes.assemble`` bands the three classes
    and rejects overlap; ``validate_map.validate_provinces`` three-way passes on a
    clean lake-bearing map and fails on the negatives; the stateless-lake checks
    fail on a claimed lake; and ``generate_sea_regions._replace_lakes`` fills and
    is idempotent.
    """
    from worldgen import lakes as lk
    from worldgen import sea_zones as sz
    import validate_map as vm
    import generate_sea_regions as gsr

    # --- lakes.classify: an ocean strip + two enclosed bodies ---
    land = np.ones((12, 24), dtype=bool)
    land[:, :6] = False              # open ocean (largest water component)
    land[3:5, 10:12] = False         # enclosed body A (a lake)
    land[8:10, 18:20] = False        # enclosed body B (a lake)
    lake = lk.classify(land, wrap_x=False)
    assert not lake[0, 0], "the world ocean must not be a lake"
    assert lake[3, 10] and lake[8, 18], "both enclosed bodies must be lakes"
    assert not lake[land].any(), "no land pixel may be a lake"
    assert int(lake.sum()) == 8, f"two 2x2 lakes = 8 px, got {int(lake.sum())}"
    assert np.array_equal(lake, lk.classify(land, wrap_x=False)), "classify must be deterministic"

    # A body split across the x=0/x=W-1 seam is ONE lake under wrap_x.
    wland = np.ones((8, 12), dtype=bool)
    wland[0, :] = False              # ocean row (largest water body)
    wland[3:5, 0] = False            # left half of a seam-wrapped enclosed body
    wland[3:5, 11] = False           # right half
    wlake = lk.classify(wland, wrap_x=True)
    wlabel = lk.label(wlake, wrap_x=True)
    assert int(wlabel.max()) == 1, f"a seam-wrapped body must be one lake, got {int(wlabel.max())}"

    # --- lakes.label: distinct components -> distinct labels ---
    lab = lk.label(lake, wrap_x=False)
    assert int(lab.max()) == 2, f"two lake bodies = 2 labels, got {int(lab.max())}"
    assert lab[3, 10] != lab[8, 18], "the two lakes must carry different labels"
    assert (lab[~lake] == 0).all(), "no non-lake pixel may carry a lake label"
    assert np.array_equal(lab, lk.label(lake, wrap_x=False)), "label must be deterministic"

    # --- Phase B (board #3742): classify reporting via the log hook ---
    # A lake over OCEAN_WARN_FRACTION of the world ocean logs a sealed-strait
    # WARNING; any sub-report_min lake logs a junk-speck note.
    rland = np.ones((40, 40), dtype=bool)
    rland[:, :20] = False            # world ocean, 800 px
    rland[5:11, 30:36] = False       # a 6x6 = 36 px lake: 4.5% > 3% guard, < 2000 floor
    lines: list[str] = []
    lk.classify(rland, wrap_x=False, log=lines.append)
    assert any("WARNING" in ln and "sealed off" in ln for ln in lines), \
        f"classify must warn on an over-{lk.OCEAN_WARN_FRACTION:.0%} lake, got {lines}"
    assert any("report floor" in ln for ln in lines), \
        f"classify must note a sub-floor lake, got {lines}"
    # A tiny lake in a big ocean is under the fraction guard (no WARNING) but still
    # under the report floor (still noted).
    rland2 = np.ones((40, 40), dtype=bool)
    rland2[:, :20] = False           # world ocean, 800 px
    rland2[5:7, 30:32] = False       # 2x2 = 4 px: 0.5% < guard, < 2000 floor
    lines2: list[str] = []
    lk.classify(rland2, wrap_x=False, log=lines2.append)
    assert not any("WARNING" in ln for ln in lines2), \
        f"a 0.5% lake must not trigger the sealed-strait WARNING, got {lines2}"
    assert any("report floor" in ln for ln in lines2), \
        f"a sub-floor lake must still be noted, got {lines2}"

    # --- Phase B: the two non-blocking index-side warning functions, in isolation ---
    sea_cell = {"kind": "sea", "area": 10000, "hex": "x0000FF"}
    big_lake = {"kind": "lake", "area": 400, "hex": "xAAAAAA"}   # 4% of ocean > 3% guard
    small_lake = {"kind": "lake", "area": 50, "hex": "xBBBBBB"}  # 0.5% < guard; < 2000 floor
    assert vm._warn_lakes_oversized([sea_cell, big_lake], lk.OCEAN_WARN_FRACTION), \
        "a lake over the ocean-fraction guard must warn"
    assert vm._warn_lakes_oversized([sea_cell, small_lake], lk.OCEAN_WARN_FRACTION) == [], \
        "a lake under the guard must not warn"
    assert vm._warn_lakes_oversized([sea_cell], lk.OCEAN_WARN_FRACTION) == [], \
        "no lake cells -> no oversized warning (dormant)"
    big_ok = {"kind": "lake", "area": 5000, "hex": "xCCCCCC"}    # >= 2000 report floor
    assert vm._warn_lakes_degenerate([sea_cell, small_lake], lk.LAKE_REPORT_MIN), \
        "a lake below the report floor must warn"
    assert vm._warn_lakes_degenerate([sea_cell, big_ok], lk.LAKE_REPORT_MIN) == [], \
        "a lake at/above the report floor must not warn"
    assert vm._warn_lakes_degenerate([sea_cell], lk.LAKE_REPORT_MIN) == [], \
        "no lake cells -> no degenerate warning (dormant)"

    # --- sea_zones.extract before/after (the defect, then the fix) ---
    drawn = np.full((12, 24, 3), 180, dtype=np.uint8)  # no purple dividers
    zones_before = sz.extract(land, drawn, dilate=1, merge_floor=1, wrap_x=False)
    assert int(zones_before[3, 10]) > 0, \
        "without exclude, an enclosed body is its OWN labelled sea zone (the defect)"
    zones_after = sz.extract(land, drawn, dilate=1, merge_floor=1, wrap_x=False, exclude=lake)
    assert int(zones_after[3, 10]) == 0 and int(zones_after[8, 18]) == 0, \
        "with exclude, lake pixels stay unlabelled (never a sea zone)"
    assert (zones_after[~land & ~lake] > 0).all(), "the navigable ocean must be fully labelled"
    assert int((zones_after == 0).sum()) == int(land.sum()) + int(lake.sum()), \
        "unlabelled == land + lake (the three-way tiling)"
    assert np.array_equal(
        zones_after, sz.extract(land, drawn, dilate=1, merge_floor=1, wrap_x=False, exclude=lake)), \
        "extract must be deterministic"

    # --- lakes.assemble: bands, totality, disjointness ---
    land_lab = np.where(land, 1, 0).astype(np.int32)   # one land province
    n_land = 1
    sea_lab = zones_after
    n_sea = int(sea_lab.max())
    lake_lab = lab
    combined = lk.assemble(land_lab, sea_lab, lake_lab, n_land, n_sea)
    assert (combined[land] == 1).all(), "land keeps 1..N"
    assert (combined[~land & ~lake] > n_land).all() and (combined[~land & ~lake] <= n_land + n_sea).all(), \
        "ocean lands in the sea band"
    assert (combined[lake] > n_land + n_sea).all(), "lakes land in the band above the sea band"
    assert int((combined == 0).sum()) == 0, "assemble must leave no unlabelled pixel"
    # Overlapping layers are rejected.
    try:
        lk.assemble(land_lab, np.where(land, 1, 0).astype(np.int32), lake_lab, n_land, n_sea)
    except cells.CellError:
        pass
    else:  # pragma: no cover
        raise AssertionError("assemble must reject overlapping land/sea labels")

    # --- validate_map.validate_provinces three-way, clean + negatives ---
    with tempfile.TemporaryDirectory(prefix="wh_lakes_") as td:
        tdp = Path(td)
        A, Bc, C = (200, 40, 40), (40, 40, 200), (40, 200, 200)  # land / ocean / lake
        rgb = np.zeros((12, 24, 3), dtype=np.uint8)
        rgb[land] = A
        rgb[~land & ~lake] = Bc
        rgb[lake] = C
        write_rgb_png(tdp / "provinces.png", rgb)
        raster.write_mask_png(tdp / "mask.png", land)
        raster.write_mask_png(tdp / "lake_mask.png", lake)
        cells.write_labels(tdp / "sea_zones.png", sea_lab)

        areas = np.bincount(combined.ravel())
        index = {
            "canvas": [24, 12], "land_provinces": 1, "sea_provinces": n_sea, "lake_provinces": 2,
            "id_high_water": 4 + n_sea,  # #3705: max id (n_sea+3) + 1
            "cells": (
                [{"label": 1, "kind": "land", "color": list(A), "hex": raster.color_to_hex(A),
                  "id": 1, "area": int(areas[1]), "coastal": True, "impassable": False,
                  "placeholder": False, "archipelago": False}]
                + [{"label": 1 + s, "kind": "sea", "color": list(Bc), "hex": raster.color_to_hex(Bc),
                    "id": 1 + s, "area": int(areas[1 + s]), "coastal": True, "impassable": False,
                    "placeholder": False, "archipelago": False} for s in range(1, n_sea + 1)]
                + [{"label": 1 + n_sea + k, "kind": "lake", "color": list(C),
                    "hex": raster.color_to_hex(C), "id": 1 + n_sea + k,
                    "area": int(areas[1 + n_sea + k]), "coastal": True, "impassable": True,
                    "placeholder": False, "archipelago": False} for k in range(1, 3)]
            ),
        }
        # Two lake bodies share one colour C, which would trip the "duplicate colour"
        # check — give each its own colour so the clean case is genuinely clean.
        C2 = (60, 210, 210)
        rgb[lake_lab == 2] = C2
        write_rgb_png(tdp / "provinces.png", rgb)
        index["cells"][-1]["color"] = list(C2)
        index["cells"][-1]["hex"] = raster.color_to_hex(C2)

        def _write_index(obj):
            (tdp / "index.json").write_text(json.dumps(obj) + "\n", encoding="utf-8")

        _write_index(index)
        clean = vm.validate_provinces(
            tdp / "provinces.png", tdp / "mask.png", tdp / "index.json",
            tdp / "sea_zones.png", wrap_x=False, lake_mask_path=tdp / "lake_mask.png")
        assert clean == [], f"a clean lake-bearing map must pass, got {clean}"

        # Phase B (board #3742): the advisory warnings surface via the accumulator
        # but never gate — errors stay empty. Here the two synthetic lakes are each
        # ~5.6% of the tiny 72 px ocean (over the guard) and 4 px (under the report
        # floor), so both advisories fire while the gate still passes.
        warns: list[str] = []
        clean_w = vm.validate_provinces(
            tdp / "provinces.png", tdp / "mask.png", tdp / "index.json",
            tdp / "sea_zones.png", wrap_x=False, lake_mask_path=tdp / "lake_mask.png",
            warnings=warns)
        assert clean_w == [], f"warnings must not become errors, got {clean_w}"
        assert any("sealed off" in w for w in warns), \
            f"an over-guard lake must raise a non-blocking sealed-strait warning, got {warns}"
        assert any("report floor" in w for w in warns), \
            f"a sub-floor lake must raise a non-blocking junk-lake warning, got {warns}"

        # Negative: a lake pixel painted the ocean colour (a lake labelled sea).
        bad = rgb.copy()
        bad[3, 10] = Bc
        write_rgb_png(tdp / "bad.png", bad)
        errs = vm.validate_provinces(
            tdp / "bad.png", tdp / "mask.png", tdp / "index.json",
            tdp / "sea_zones.png", wrap_x=False, lake_mask_path=tdp / "lake_mask.png")
        assert errs, "a lake pixel labelled sea must fail"

        # Negative: a lake pixel painted the land colour (out of the lake band).
        bad2 = rgb.copy()
        bad2[3, 10] = A
        write_rgb_png(tdp / "bad2.png", bad2)
        errs2 = vm.validate_provinces(
            tdp / "bad2.png", tdp / "mask.png", tdp / "index.json",
            tdp / "sea_zones.png", wrap_x=False, lake_mask_path=tdp / "lake_mask.png")
        assert any("band" in e or "span" in e for e in errs2), \
            f"a lake pixel carrying a land-band label must fail, got {errs2}"

        # Negative: the sea layer tiles ALL water (lakes included) instead of only
        # the navigable ocean.
        sea_all = np.where(~land, 1, 0).astype(np.int32)
        cells.write_labels(tdp / "sea_all.png", sea_all)
        errs3 = vm.validate_provinces(
            tdp / "provinces.png", tdp / "mask.png", tdp / "index.json",
            tdp / "sea_all.png", wrap_x=False, lake_mask_path=tdp / "lake_mask.png")
        assert any("navigable water" in e for e in errs3), \
            f"a sea layer tiling all water (not just ocean) must fail, got {errs3}"

    # --- stateless-lake checks (repo-form validate()) ---
    lake_col = {C, C2}
    claimant = vm.ParsedState("STATE_X", "01_x.txt")
    claimant.provinces = [A, C]      # wrongly claims a lake colour
    assert vm._check_lakes_stateless([claimant], lake_col), \
        "a state claiming a lake colour must fail _check_lakes_stateless"
    assert vm._check_lakes_declared({C, C2}, {C}), \
        "a lake in the index but not the default.map lakes block must fail"
    assert vm._check_lakes_declared({C}, {C, C2}), \
        "a lakes-block colour absent from the index must fail"
    assert vm._check_lakes_declared({C, C2}, {C, C2}) == [], \
        "matching lake colours must pass"

    # --- generate_sea_regions._replace_lakes: fill + idempotent ---
    dm = 'sea_starts = {\n\tx010101\n}\nlakes = {\n\n}\n'
    lake_colors = {3: (10, 20, 30), 4: (40, 50, 60)}
    filled = gsr._replace_lakes(dm, lake_colors)
    assert "x0A141E" in filled and "x28323C" in filled, f"lakes block must carry the colours: {filled}"
    assert gsr._replace_lakes(filled, lake_colors) == filled, "_replace_lakes must be idempotent"
    empty = gsr._replace_lakes(dm, {})
    assert "lakes = {\n}" in empty, f"an empty lakes block must normalize to the empty shape: {empty}"


def _selfcheck_drop_land_specks() -> None:
    """Anti-aliasing land-speck drop (generate_coastline_mask.drop_land_specks).

    Board #3705 follow-up — the durable fix for the xD3DC0A "Western Ocean Mass"
    1-px state: a finished fill exported to PNG can strand tiny near-white "islands"
    in the sea, and left in the mask each ships as a permanent micro state (a
    disconnected islet has no land neighbour to be merged away downstream). The drop
    lives at the mask, the sole owner of land_sea_mask.png, upstream of the
    sea/province cuts. Pins: sub-floor land components are reclassified as water
    while a real island and every water pixel are untouched; the floor is exclusive
    (a component exactly at min_px survives); min_px<=1 is a no-op; a seam-straddling
    speck counts as one component under wrap_x; and two runs are byte-identical.
    """
    import generate_coastline_mask as gcm

    quiet = lambda *_a, **_k: None
    H, W = 12, 20
    land = np.zeros((H, W), dtype=bool)
    land[3:8, 3:8] = True        # 25-px real island — must survive
    land[1, 15] = True           # 1-px speck
    land[10, 2:4] = True         # 2-px speck
    water0 = int((~land).sum())

    cleaned, n_comp, n_px = gcm.drop_land_specks(land, gcm.SPECK_MAX_PX, wrap_x=False, log=quiet)
    assert (n_comp, n_px) == (2, 3), f"expected 2 specks / 3 px dropped, got {n_comp}/{n_px}"
    assert cleaned[3:8, 3:8].all(), "the real island must survive"
    assert not cleaned[1, 15] and not cleaned[10, 2] and not cleaned[10, 3], "specks must be water"
    assert int((~cleaned).sum()) == water0 + 3, "only the 3 speck px may flip to water"
    again, n2, p2 = gcm.drop_land_specks(land, gcm.SPECK_MAX_PX, wrap_x=False, log=quiet)
    assert np.array_equal(cleaned, again) and (n2, p2) == (2, 3), "two runs must be byte-identical"

    # The floor is exclusive: a component of exactly min_px px is kept.
    at_floor = np.zeros((H, W), dtype=bool)
    at_floor[5, 5:9] = True       # exactly 4 px
    kept, nf, pf = gcm.drop_land_specks(at_floor, 4, wrap_x=False, log=quiet)
    assert (nf, pf) == (0, 0) and np.array_equal(kept, at_floor), "a component == min_px must survive"

    # min_px <= 1 is a no-op (nothing is smaller than one pixel).
    noop, n0, p0 = gcm.drop_land_specks(land, 1, wrap_x=False, log=quiet)
    assert (n0, p0) == (0, 0) and np.array_equal(noop, land), "min_px<=1 must be a no-op"

    # Wrap-aware: a 2-px speck straddling the x-seam is ONE component, dropped whole.
    seam = np.zeros((H, W), dtype=bool)
    seam[6, 0] = True
    seam[6, W - 1] = True
    wrapped, nw, pw = gcm.drop_land_specks(seam, gcm.SPECK_MAX_PX, wrap_x=True, log=quiet)
    assert (nw, pw) == (1, 2), f"seam speck must be one 2-px component under wrap, got {nw}/{pw}"
    assert not wrapped.any(), "the seam speck must be fully reclassified as water"
    _flat, nf2, pf2 = gcm.drop_land_specks(seam, gcm.SPECK_MAX_PX, wrap_x=False, log=quiet)
    assert (nf2, pf2) == (2, 2), "without wrap the seam speck is two 1-px components"


def _selfcheck_seeded_cut() -> None:
    """Hub-anchor seeded province cut (#3665), in isolation (no golden).

    Pins the properties generate_provinces.py relies on: cells.merge_small never
    folds a protected piece away; cells._farthest_seeds pins fixed seeds first and
    is byte-identical without them; subdivide with region_seeds gives every anchor
    its own province, never crosses a magenta region boundary, keeps an unseeded
    region byte-identical to the region_seeds=None cut, hard-errors on an anchor in
    a keep_whole archipelago or a non-drawn region, and is deterministic.
    """
    from worldgen import land_provinces as lp
    from worldgen import cells as C

    # --- cells.merge_small(protected=) primitive ---
    lab = np.full((10, 10), 2, dtype=np.int32)
    lab[0, 0] = 1                       # a 1-px cell below the floor
    unprot = C.merge_small(lab, 5, wrap_x=False)
    assert int(len(np.unique(unprot))) == 1, "unprotected sub-floor cell must be folded away"
    prot = C.merge_small(lab, 5, wrap_x=False, protected={1})
    assert int(len(np.unique(prot))) == 2 and prot[0, 0] != prot[5, 5],         "a protected sub-floor cell must survive"

    # Three mutually-adjacent sub-floor cells that each pick the next (a -> b -> c -> a)
    # used to rotate labels forever and never merge, stranding a thin coastal spur as
    # several tiny states; a cycle must fold into one cell.
    cyc = np.array([[3, 2, 3, 3, 3, 2], [3, 3, 1, 2, 2, 3], [2, 3, 2, 3, 1, 2],
                    [1, 3, 2, 2, 3, 1], [2, 3, 3, 3, 3, 2]], dtype=np.int32)
    assert int(len(np.unique(C.merge_small(cyc, 100, wrap_x=False)))) == 1,         "a merge_small choice cycle must fold into a single cell"

    # --- cells._farthest_seeds(fixed=) primitive ---
    pix = np.column_stack(np.nonzero(np.ones((6, 6), dtype=bool)))
    base = C._farthest_seeds(pix, 3)
    assert np.array_equal(base, C._farthest_seeds(pix, 3, fixed=None)),         "fixed=None must be byte-identical to the original farthest-point path"
    seeded = C._farthest_seeds(pix, 3, fixed=np.array([[0, 0]]))
    assert len(seeded) == 3 and tuple(seeded[0]) == (0, 0), "fixed seed must come first"

    # --- subdivide(region_seeds=) end to end ---
    H, W = 24, 48
    land = np.zeros((H, W), dtype=bool)
    land[3:21, 3:21] = True             # drawn block, split by a divider into 2 regions
    land[3:12, 30:40] = True            # a separate placeholder block (no magenta)
    drawn = np.full((H, W, 3), 180, dtype=np.uint8)
    drawn[3:21, 11] = (255, 0, 255)     # interior magenta divider

    reg = lp.regions(land, drawn, dilate=1, merge_floor=1, wrap_x=False)
    west = int(reg[7, 5]); east = int(reg[7, 15]); placeholder = int(reg[6, 32])
    assert west > 0 and east > 0 and placeholder > 0 and len({west, east, placeholder}) == 3,         f"expected 3 distinct regions, got west={west} east={east} placeholder={placeholder}"
    dmask = lp.drawn_mask(land, lp.magenta_lines(drawn), wrap_x=False, interior_dist=1, reach=12)
    assert dmask[reg == west].mean() > 0.5 and dmask[reg == east].mean() > 0.5,         "both halves of the drawn block must be classed drawn"
    assert dmask[reg == placeholder].mean() < 0.5, "the bare block must be classed placeholder"

    a1, a2 = (5, 7), (7, 17)            # two anchors in the WEST region, far apart
    prov, _, _, _ = lp.subdivide(reg, land, dmask, target=6, wrap_x=False, min_area=1,
                                 region_seeds={west: [a1, a2]})
    p1, p2 = int(prov[a1[1], a1[0]]), int(prov[a2[1], a2[0]])
    assert p1 != p2, "each anchor must land in its own province"
    for lab_id in (p1, p2):
        assert list(np.unique(reg[prov == lab_id])) == [west],             "an anchor province must lie wholly inside its own region"
    # No province anywhere crosses a magenta region boundary.
    for lab_id in range(1, int(prov.max()) + 1):
        regs_here = np.unique(reg[prov == lab_id])
        assert len(regs_here) == 1, f"province {lab_id} spans regions {regs_here.tolist()}"

    # An UNSEEDED region is byte-identical (as a partition) to the region_seeds=None cut.
    prov0, _, _, _ = lp.subdivide(reg, land, dmask, target=6, wrap_x=False, min_area=1)
    def _canon(arr, mask):
        out = np.zeros(arr.shape, dtype=np.int64)
        lut: dict[int, int] = {}
        for idx in np.flatnonzero(mask.ravel()):
            v = int(arr.ravel()[idx])
            if v not in lut:
                lut[v] = len(lut) + 1
            out.ravel()[idx] = lut[v]
        return out
    east_mask = reg == east
    assert np.array_equal(_canon(prov, east_mask), _canon(prov0, east_mask)),         "an unseeded region's cut must be byte-identical to the no-seed run"

    # Determinism: two seeded runs are byte-identical.
    prov_b, _, _, _ = lp.subdivide(reg, land, dmask, target=6, wrap_x=False, min_area=1,
                                   region_seeds={west: [a1, a2]})
    assert np.array_equal(prov, prov_b), "two seeded runs must be byte-identical"

    # Hard errors: anchor in a keep_whole archipelago, or in a non-drawn region.
    try:
        lp.subdivide(reg, land, dmask, target=6, wrap_x=False, min_area=1,
                     keep_whole={west}, region_seeds={west: [a1]})
        raise AssertionError("anchor in a keep_whole region must be a hard error")
    except C.CellError:
        pass
    try:
        lp.subdivide(reg, land, dmask, target=6, wrap_x=False, min_area=1,
                     region_seeds={placeholder: [(32, 6)]})
        raise AssertionError("anchor in a non-drawn (placeholder) region must be a hard error")
    except C.CellError:
        pass


    # --- wrap_x=True: the seam-shift anchor translation, the one piece of genuinely
    # new coordinate math (production runs map_config.WRAP_X). A region straddling
    # the antimeridian with anchors near both seam edges must still give each anchor
    # its own contiguous province (the ((ax+shift)%W)-x0 mapping in _subdivide_cell).
    Hw, Ww = 16, 40
    landw = np.zeros((Hw, Ww), dtype=bool)
    landw[3:13, 0:5] = True             # west of the seam
    landw[3:13, 35:40] = True           # east of the seam, adjacent across x=0/x=W-1
    drawnw = np.full((Hw, Ww, 3), 180, dtype=np.uint8)
    drawnw[6:10, 2] = (255, 0, 255)     # short interior magenta (marks drawn, no split)
    drawnw[6:10, 37] = (255, 0, 255)
    regw = lp.regions(landw, drawnw, dilate=1, merge_floor=1, wrap_x=True)
    rlabel = int(regw[7, 0])
    assert rlabel > 0 and int(regw[7, 39]) == rlabel,         "the seam-straddling land must be ONE region under wrap"
    assert lp._is_connected(regw == rlabel, wrap_x=True), "one connected seam-wrapping region"
    dmaskw = lp.drawn_mask(landw, lp.magenta_lines(drawnw), wrap_x=True, interior_dist=1, reach=10)
    aw1, aw2 = (0, 5), (39, 10)         # anchors near opposite seam edges
    provw, _, _, iaw = lp.subdivide(regw, landw, dmaskw, target=4, wrap_x=True, min_area=1,
                                    region_seeds={rlabel: [aw1, aw2]})
    assert int(provw[aw1[1], aw1[0]]) != int(provw[aw2[1], aw2[0]]),         "each seam-side anchor must get its own province under wrap"
    for a in (aw1, aw2):
        assert list(np.unique(regw[provw == int(provw[a[1], a[0]])])) == [rlabel],             "a seam-wrapped anchor province must stay inside its own region"
    assert not iaw.any(), "seam-wrapping provinces are contiguous under wrap, never archipelago"


def _selfcheck_city_blobs() -> None:
    """City blobs kept whole in one province (board #5679), synthetic canvas."""
    import validate_map as vm
    from worldgen import cells as C
    from worldgen import land_provinces as lp

    H, W = 40, 90
    land = np.zeros((H, W), dtype=bool)
    land[3:37, 3:37] = True
    land[3:37, 40:70] = True
    reg = np.zeros((H, W), dtype=np.int32)
    reg[3:37, 3:37] = 1
    reg[3:37, 40:70] = 2
    drawn = land.copy()
    kw = dict(wrap_x=False, min_area=20)

    def rgba(*boxes):
        a = np.zeros((H, W, 4), dtype=np.uint8)
        for y0, y1, x0, x1 in boxes:
            a[y0:y1, x0:x1] = (0, 255, 255, 255)
        return a

    base = lp.subdivide_ex(reg, land, drawn, 8, **kw)[0]
    # empty / None blobs: byte-identical
    assert np.array_equal(base, lp.subdivide_ex(reg, land, drawn, 8, city_blobs=[], **kw)[0])
    assert lp.city_blobs(rgba(), land) == []

    # Find a seam inside region A and put a blob across it.
    seam = None
    for y in range(6, 34):
        for x in range(6, 34):
            if base[y, x] != base[y, x + 1] and reg[y, x] == 1:
                seam = (y, x)
                break
        if seam:
            break
    assert seam, "fixture cut has no interior seam in region A"
    sy, sx = seam
    cities = rgba((sy - 1, sy + 2, sx - 1, sx + 3))
    blobs = lp.city_blobs(cities, land)
    assert len(blobs) == 1
    assert np.unique(base[cities[..., 3] > 0]).size > 1, "blob must straddle a seam before the fix"
    lab = lp.subdivide_ex(reg, land, drawn, 8, city_blobs=blobs, **kw)[0]
    assert np.unique(lab[cities[..., 3] > 0]).size == 1, "blob must land in one province"
    assert np.array_equal(lab, lp.subdivide_ex(reg, land, drawn, 8, city_blobs=blobs, **kw)[0]), \
        "determinism"
    # Region B is untouched.
    assert np.array_equal(lab[:, 40:70] > 0, base[:, 40:70] > 0)
    b = reg == 2
    assert np.array_equal(lab[b] == lab[b][0], base[b] == base[b][0]), "unaffected region changed"
    # Every province stays one connected piece.
    for L in range(1, int(lab.max()) + 1):
        comp = C.components((lab == L).astype(np.int32), False)
        assert len(np.unique(comp[lab == L])) == 1, f"province {L} torn"
    # Validator round-trip: the split one fails, the fixed one passes, empty skips.
    def code_of(l):
        return (l.astype(np.uint32) + 1000)
    assert vm._check_city_blobs(code_of(base), cities), "validator must flag a split blob"
    assert not vm._check_city_blobs(code_of(lab), cities), "validator must pass a whole blob"
    assert not vm._check_city_blobs(code_of(base), rgba()), "empty layer must skip"
    # Graze tolerance: a blob with <= 4 px in a second province passes; 5 px fails.
    gc = np.full((H, W), 1000, dtype=np.uint32)
    gb = rgba((10, 12, 10, 15))                      # 10 px blob
    gc[10, 10:14] = 2000                             # 4 px elsewhere
    assert not vm._check_city_blobs(gc, gb), "4 px graze must be tolerated"
    gc[10, 14] = 2000                                # 5 px
    assert vm._check_city_blobs(gc, gb), "5 px must fail"

    # Blob across the region border (A|B gap is water; bridge them with land).
    land2 = land.copy()
    land2[18:22, 37:40] = True
    reg2 = reg.copy()
    reg2[18:22, 37:38] = 1
    reg2[18:22, 38:40] = 2
    bridge = lp.city_blobs(rgba((17, 23, 34, 43)), land2)
    try:
        lp.subdivide_ex(reg2, land2, land2, 8, city_blobs=bridge, **kw)
    except C.CellError as e:
        assert "city blob at" in str(e), e
    else:
        raise AssertionError("blob across a state border must be a CellError")

    # Sliver case: same split, but no drawn line under the blob (the region fill's
    # dilated band did the splitting) -> accepted, blob moved whole into its
    # majority region, reg patched, every province still one region.
    bl = rgba((17, 23, 34, 43))
    noline = np.zeros((H, W), dtype=bool)
    lab2, _, reg_of2, _, _ = lp.subdivide_ex(reg2, land2, land2, 8, city_blobs=bridge,
                                             city_line=noline, **kw)
    assert np.unique(lab2[bl[..., 3] > 0][land2[bl[..., 3] > 0]]).size == 1, "sliver blob split"
    for L in range(1, int(lab2.max()) + 1):
        assert len(np.unique(reg_of2[L:L + 1])) == 1
    # A drawn line under the blob keeps it a hard error.
    line = noline.copy()
    line[20, 36:41] = True
    try:
        lp.subdivide_ex(reg2, land2, land2, 8, city_blobs=bridge, city_line=line, **kw)
    except C.CellError:
        pass
    else:
        raise AssertionError("blob over a drawn line must stay a CellError")


def _selfcheck_city_seeds() -> None:
    """Every city dot seeds its own province (board #5679), incl. a tunnel of
    passable land inside impassable paint."""
    from worldgen import land_provinces as lp

    H, W = 40, 90
    land = np.zeros((H, W), dtype=bool)
    land[3:37, 3:37] = True
    land[3:37, 40:70] = True
    reg = np.zeros((H, W), dtype=np.int32)
    reg[3:37, 3:37] = 1
    reg[3:37, 40:70] = 2
    kw = dict(wrap_x=False, min_area=20)
    paint = np.zeros((H, W), dtype=bool)
    paint[3:37, 3:30] = True
    paint[18:22, 8:28] = False                 # the tunnel (80 px)
    tunnel = np.zeros((H, W), dtype=bool)
    tunnel[18:22, 8:28] = True
    cities = [(10, 20), (18, 20), (26, 20)]

    base = lp.subdivide_ex(reg, land, land, 8, impassable=paint, **kw)[0]
    assert np.unique(base[tunnel]).size == 1, "fixture: tunnel is one province unseeded"
    lab = lp.subdivide_ex(reg, land, land, 8, impassable=paint, city_seeds=cities,
                          city_seed_sep=5, **kw)[0]
    assert len({int(lab[y, x]) for x, y in cities}) == 3, "each city gets its own province"
    assert np.array_equal(lab, lp.subdivide_ex(reg, land, land, 8, impassable=paint,
                                               city_seeds=cities, city_seed_sep=5, **kw)[0])
    # Open land: two cities in one unpainted region split it into distinct provinces.
    op = [(45, 10), (60, 30)]
    lab2 = lp.subdivide_ex(reg, land, land, 2, city_seeds=op, city_seed_sep=5, **kw)[0]
    assert lab2[10, 45] != lab2[30, 60]
    # Seeds closer than the separation collapse (skipped, no error).
    lab3 = lp.subdivide_ex(reg, land, land, 2, city_seeds=[(45, 10), (47, 10)],
                           city_seed_sep=16, **kw)[0]
    assert lab3[10, 45] == lab3[10, 47]
    # None / empty is byte-identical.
    assert np.array_equal(lp.subdivide_ex(reg, land, land, 8, **kw)[0],
                          lp.subdivide_ex(reg, land, land, 8, city_seeds=[], **kw)[0])


def _selfcheck_impassable_land() -> None:
    """Impassable land provinces (board #3704), source-independent, on a synthetic
    canvas: the ``subdivide_ex`` passable/impassable cut, canon-city pockets, and
    the ``validate_map._check_impassable_land`` connectivity / city-reachability
    validator. Also the stable-id diff (paint in one region moves nothing in an
    unaffected one)."""
    from pathlib import Path

    import validate_map as vm
    from worldgen import cells as C
    from worldgen import land_provinces as lp
    from worldgen import province_ids

    H, W = 40, 90
    land = np.zeros((H, W), dtype=bool)
    land[3:37, 3:37] = True             # region A (drawn)
    land[3:37, 40:70] = True            # region B (drawn, never painted)
    land[3:20, 75:88] = True            # region C (placeholder: not drawn)
    reg = np.zeros((H, W), dtype=np.int32)
    reg[3:37, 3:37] = 1
    reg[3:37, 40:70] = 2
    reg[3:20, 75:88] = 3
    drawn = land & (reg != 3)
    kw = dict(wrap_x=False, min_area=20)

    def cut(imp, target=8, **extra):
        return lp.subdivide_ex(reg, land, drawn, target, impassable=imp, **kw, **extra)

    def canon(arr, mask):
        out = np.zeros(arr.shape, dtype=np.int64)
        lut: dict[int, int] = {}
        for idx in np.flatnonzero(mask.ravel()):
            v = int(arr.ravel()[idx])
            lut.setdefault(v, len(lut) + 1)
            out.ravel()[idx] = lut[v]
        return out

    def _disc(anchors, shape, radius, wrap_x=False):
        yy, xx = np.mgrid[:shape[0], :shape[1]]
        m_ = np.zeros(shape, dtype=bool)
        for ax_, ay_ in anchors:
            m_ |= (yy - ay_) ** 2 + (xx - ax_) ** 2 <= radius * radius
        return m_

    base = cut(None)
    # --- dormancy: None and an all-False mask are byte-identical to the 4-tuple cut
    assert np.array_equal(base[0], cut(np.zeros((H, W), dtype=bool))[0]), "empty paint must be a no-op"
    old4 = lp.subdivide(reg, land, drawn, 8, impassable=None, **kw)
    assert np.array_equal(old4[0], base[0]) and len(old4) == 4, "subdivide() wrapper must stay 4-tuple"
    assert not base[4].any(), "no paint => no impassable province"

    # --- a tract: band across A's full height (cols 14:20), no gap
    wall = np.zeros((H, W), dtype=bool)
    wall[3:37, 14:20] = True
    lab, is_ph, reg_of, is_arch, is_imp = cut(wall)
    assert int(is_imp.sum()) == 1, f"one contiguous tract => one impassable province, got {int(is_imp.sum())}"
    tract = int(lab[10, 16])
    assert is_imp[tract] and (lab[wall] == tract).all(), "the tract is exactly the painted pixels"
    assert not is_imp[lab[10, 5]] and not is_imp[lab[10, 30]], "open land stays passable"
    for L in range(1, int(lab.max()) + 1):
        m = lab == L
        assert not (wall[m].any() and (~wall[m]).any()), f"province {L} straddles the paint boundary"
    assert not is_ph[tract], "painted-impassable is not a placeholder"
    assert is_ph[lab[5, 78]] and not is_imp[lab[5, 78]], "placeholder != impassable"
    # Unaffected region B is a byte-identical partition to the unpainted cut.
    b = reg == 2
    assert np.array_equal(canon(lab, b), canon(base[0], b)), "unaffected region must be unchanged"
    # Determinism.
    assert np.array_equal(lab, cut(wall)[0]), "two painted runs must be byte-identical"

    # --- stable ids: colour+id of every province in the unpainted region survive
    KIND = ["", *["land"] * int(lab.max())]
    KIND0 = ["", *["land"] * int(base[0].max())]
    pal0, ids0, hw0 = province_ids.assign(base[0], KIND0, None, None, map_config.SEED, reassign=True)
    rgb0 = pal0[base[0]]
    cells0 = [{"label": L, "kind": "land", "color": [int(v) for v in pal0[L]], "id": int(ids0[L])}
              for L in range(1, int(base[0].max()) + 1)]
    pal1, ids1, _ = province_ids.assign(lab, KIND, rgb0, cells0, map_config.SEED,
                                        committed_high_water=hw0)
    for L in np.unique(lab[b]).tolist():
        old = int(base[0][b & (lab == L)][0])
        assert tuple(pal1[L]) == tuple(pal0[old]) and int(ids1[L]) == int(ids0[old]), \
            "an unaffected province must keep its colour+id"

    # --- validator: bitmap + states from a cut
    def bitmap_and_state(lab_arr, is_imp_arr, tag):
        pal = np.zeros((int(lab_arr.max()) + 1, 3), dtype=np.uint8)
        for L in range(1, len(pal)):
            pal[L] = (20 + 7 * L, 90 + 3 * L, 40 + 5 * L)
        rgb = pal[lab_arr]
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "p.png"
            write_rgb_png(png, rgb)
            bmp = vm.ProvinceBitmap(png, wrap_x=False)
        labs = [L for L in np.unique(lab_arr[reg == 1]).tolist() if L > 0]
        st = vm.ParsedState("STATE_A", "t.txt")
        st.provinces = [tuple(int(v) for v in pal[L]) for L in labs]
        st.impassable = [tuple(int(v) for v in pal[L]) for L in labs if is_imp_arr[L]]
        cells_ = [{"kind": "land", "color": [int(v) for v in pal[L]], "impassable": bool(is_imp_arr[L])}
                  for L in range(1, len(pal))]
        return bmp, st, cells_, pal

    bmp, st, cells_, pal = bitmap_and_state(lab, is_imp, "wall")
    errs = vm._check_impassable_land(bmp, [st], cells_, None, set())
    assert any("disconnected components" in e for e in errs), f"a fully-across tract must fail, got {errs}"
    # ...unless a tunnel row reconnects the two sides.
    west = tuple(int(v) for v in pal[lab[10, 5]])
    east = tuple(int(v) for v in pal[lab[10, 30]])
    assert not vm._check_impassable_land(bmp, [st], cells_, None, {frozenset((west, east))}), \
        "an adjacencies.csv tunnel row must satisfy connectivity"

    # --- a gap keeps passable land connected
    gap = wall.copy()
    gap[30:37, 14:20] = False
    labg, _, _, _, impg = cut(gap)
    bmpg, stg, cellsg, _ = bitmap_and_state(labg, impg, "gap")
    assert vm._check_impassable_land(bmpg, [stg], cellsg, None, set()) == [], \
        "a gap in the paint must keep the state connected"

    # --- city pockets
    cx, cy = 16, 10
    pk = _disc([(cx, cy)], (H, W), radius=6, wrap_x=False)
    assert pk[cy, cx] and not pk[cy, cx + 8], "pocket is a bounded disc"
    assert np.array_equal(pk, _disc([(cx, cy)], (H, W), radius=6, wrap_x=False)), "deterministic"
    # (i) pocket touching open land: city province passable + reachable
    wall_p = wall & ~pk
    labp, _, _, _, impp = cut(wall_p)
    bmpp, stp, cellsp, palp = bitmap_and_state(labp, impp, "pocket-path")
    cprov = int(labp[cy, cx])
    assert not impp[cprov], "the city's province is passable"
    ci = {"cities": [{"name": "Testhold", "province_hex": "x%02X%02X%02X" % tuple(palp[cprov]),
                      "impassable": False}]}
    assert vm._check_impassable_land(bmpp, [stp], cellsp, ci, {frozenset((west, east))}) == [], \
        "a city pocket connected to open land passes"
    # (ii) pocket floating inside solid paint: enclosed -> blocking error naming the city
    cy2 = 20
    pk2 = _disc([(16, cy2)], (H, W), radius=1, wrap_x=False)
    wall_e = wall & ~pk2
    labe, _, _, _, impe = cut(wall_e, keep_passable=[(16, cy2)])
    bmpe, ste, cellse, pale = bitmap_and_state(labe, impe, "pocket-enclosed")
    eprov = int(labe[cy2, 16])
    assert not impe[eprov], "an enclosed pocket is still its own passable province"
    ce = {"cities": [{"name": "Sealedhold", "province_hex": "x%02X%02X%02X" % tuple(pale[eprov]),
                      "impassable": False}]}
    errs = vm._check_impassable_land(bmpe, [ste], cellse, ce, {frozenset((west, east))})
    assert any("Sealedhold" in e and "enclosed" in e for e in errs), f"enclosed city must fail, got {errs}"

    # --- validator: placeholder states never fire; agreement/stray checks fire
    labs_ph = [L for L in np.unique(lab[reg == 3]).tolist() if L > 0]
    stph = vm.ParsedState("STATE_PH", "t.txt")
    stph.provinces = [tuple(int(v) for v in pal[L]) for L in labs_ph]
    assert vm._check_impassable_land(bmp, [stph], [c for c in cells_ if False], None, set()) == [], \
        "no impassable anywhere => clean skip"
    bad = vm.ParsedState("STATE_A", "t.txt")
    bad.provinces = list(st.provinces)
    bad.impassable = []
    assert any("disagrees" in e for e in vm._check_impassable_land(bmp, [bad], cells_, None, set())), \
        "state/index disagreement must fail"

    # --- trapped passable specks below min_area fold into the paint; a kept point survives
    holed = wall.copy()
    speck = np.zeros((H, W), dtype=bool)
    speck[19:22, 15:18] = True                       # 9 px < min_area 20, inside the tract
    holed_p = holed & ~speck
    labh, _, _, _, imph = cut(holed_p)
    assert imph[labh[20, 16]], "a trapped sub-floor passable speck folds into the paint"
    labk, _, _, _, impk = cut(holed_p, keep_passable=[(16, 20)])
    assert not impk[labk[20, 16]], "a keep_passable point (city pocket) is never folded"

    # --- a painted region's big open tract is still Voronoi-cut when kept pockets exist
    many = np.zeros((H, W), dtype=bool)
    many[3:8, 3:37] = True               # a thin painted band across the top of A
    pockets = [(6 + 6 * j, 5) for j in range(5)]
    for px_, py_ in pockets:
        many[py_, px_] = False           # 1px pockets, kept via keep_passable
    labm, _, _, _, impm = cut(many, target=10, keep_passable=pockets)
    open_provs = np.unique(labm[12:37, 3:37])
    assert len(open_provs) >= 3,         f"trapped pockets must not eat the big tract's seats, got {len(open_provs)} provinces"

    # --- a long thin enclosed passable corridor is not left as one province
    tun = np.zeros((H, W), dtype=bool)
    tun[3:37, 10:24] = True
    tun[4:36, 16:19] = False             # 3px x 32px corridor, walled in
    labt, _, _, _, impt = cut(tun, target=60, keep_passable=[(17, 20)])
    corr = np.unique(labt[4:36, 16:19])
    assert len(corr) >= 2 and not impt[corr].any(),         f"a long thin passable corridor must be cut into several provinces, got {len(corr)}"
    tcomp = C.components(labt, wrap_x=False)
    pairs_t = np.unique(np.stack([labt[labt > 0], tcomp[labt > 0]], axis=1), axis=0)
    assert len(pairs_t) == len(np.unique(labt[labt > 0])), "geodesic cut: no province is torn"

    # --- generation-time errors
    on_placeholder = np.zeros((H, W), dtype=bool)
    on_placeholder[5:15, 78:85] = True
    assert np.array_equal(cut(on_placeholder)[0], base[0]) and not cut(on_placeholder)[4].any(),         "paint on a placeholder region is disregarded by default"
    try:
        cut(on_placeholder, strict_placeholder_paint=True)
        raise AssertionError("strict mode: paint on a placeholder region must raise")
    except C.CellError:
        pass
    try:
        cut(wall, keep_whole={1})
        raise AssertionError("paint on a keep_whole region must raise")
    except C.CellError:
        pass
    try:
        cut(land & (reg == 1))
        raise AssertionError("a wholly impassable region must raise")
    except C.CellError:
        pass
    try:
        cut(wall, region_seeds={1: [(16, 10)]})
        raise AssertionError("a hub anchor on impassable paint must raise")
    except C.CellError:
        pass
    # Paint over water is ignored.
    water_paint = np.zeros((H, W), dtype=bool)
    water_paint[38:40, 3:30] = True
    assert np.array_equal(cut(water_paint)[0], base[0]), "paint over water changes nothing"

    # --- paint hygiene: <=4px blobs erased, <=4px enclosed gaps filled
    dirty = np.zeros((H, W), dtype=bool)
    dirty[5:15, 5:15] = True
    dirty[9, 9] = False                  # 1px enclosed gap
    dirty[22:24, 22:24] = True           # 4px blob
    dirty[30:32, 30:33] = True           # 6px blob survives
    cl = lp.clean_paint(dirty, land, wrap_x=False)
    assert cl[9, 9], "a 1px enclosed gap is filled"
    assert not cl[22:24, 22:24].any(), "a 4px blob is erased"
    assert cl[30:32, 30:33].all(), "a 6px blob survives"
    open_gap = dirty.copy()
    open_gap[5, 5:7] = False             # a notch touching the outside, not enclosed
    assert not lp.clean_paint(open_gap, land, wrap_x=False)[5, 5], "an open notch is not filled"
    assert np.array_equal(cl, lp.clean_paint(dirty, land, wrap_x=False)), "deterministic"

    # --- city_dots: one anchor per blob, on land only, deterministic order
    crgba = np.zeros((H, W, 4), dtype=np.uint8)
    crgba[10:12, 10:12] = (127, 127, 255, 255)     # 2x2 dot on land
    crgba[30, 20] = (127, 127, 255, 255)           # 1px dot on land
    crgba[38, 60] = (127, 127, 255, 255)           # dot on water (row 38 is off the land block)
    dots = lp.city_dots(crgba, land)
    assert dots == [(10, 10), (20, 30)] or dots == [(11, 11), (20, 30)] or len(dots) == 2, dots
    assert all(land[y_, x_] for x_, y_ in dots), "a dot on water is dropped"
    assert dots == lp.city_dots(crgba, land), "deterministic"
    assert lp.city_dots(np.zeros((H, W, 4), dtype=np.uint8), land) == [], "empty layer -> no dots"

    # --- impassable_mask: exact colour + alpha
    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[5:10, 5:10] = (255, 127, 0, 255)
    rgba[12:14, 5:10] = (255, 126, 0, 255)      # wrong colour
    rgba[16:18, 5:10] = (255, 127, 0, 0)        # transparent
    m = lp.impassable_mask(rgba, land)
    assert int(m.sum()) == 25, f"only the exact opaque colour counts, got {int(m.sum())}"
    # --- a state whose only coastal province is impassable is not coastal
    A, B, SEA = (10, 20, 30), (40, 50, 60), (0, 0, 200)

    class _CoastBitmap:                  # only B touches the sea
        def coastal_colors(self, sea_colors):
            return {B}

    cbmp = _CoastBitmap()
    cst = vm.ParsedState("STATE_COAST", "t.txt")
    cst.provinces = [A, B]
    sea_st = vm.ParsedState("STATE_SEA", "s.txt")
    assert vm._check_coastal_naval_exit([cst], [sea_st], cbmp, {SEA}),         "a passably-coastal state without a port must fail"
    cst.impassable = [B]
    _e = vm._check_coastal_naval_exit([cst], [sea_st], cbmp, {SEA})
    assert _e == [], f"a state whose only coast is impassable is not coastal, got {_e}"
    print("impassable land: cut/pockets/validator/stable-ids checks passed.")


def _selfcheck_hub_validator() -> None:
    """The #3665 validate_map hub-anchor check, on a synthetic bitmap + states —
    a passing case and three failing cases, so the check can actually fail."""
    import validate_map as vm
    from pathlib import Path

    A, B, SEA = (10, 20, 30), (40, 50, 60), (0, 0, 200)
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    rgb[:, 0:4] = A          # province A, non-coastal
    rgb[:, 4:7] = B          # province B, coastal (adjacent to the sea block)
    rgb[:, 7:10] = SEA       # sea
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "p.png"
        write_rgb_png(png, rgb)
        bitmap = vm.ProvinceBitmap(png, wrap_x=False)
    sea_colors = {SEA}
    st = vm.ParsedState("STATE_TEST", "02_empire.txt")
    st.provinces = [A, B]
    st.hubs = {"city": A, "port": B, "farm": A, "mine": A, "wood": A}
    states = [st]
    loc_keys = {"HUB_NAME_STATE_TEST_port"}

    def _idx(color, resolved=(5, 5), name="Marienburg"):
        return {"hubs": [{"name": name, "hub": "port", "resolved": list(resolved),
                          "province_color": list(color), "province_label": 2}]}

    assert vm._check_hub_anchors(bitmap, states, sea_colors, loc_keys, _idx(B)) == [],         "a clean port hub anchor must pass"
    assert vm._check_hub_anchors(bitmap, states, sea_colors, loc_keys, _idx(A, resolved=(2, 5))),         "a port anchor on a non-coastal, non-declared province must fail"
    miss = vm._check_hub_anchors(bitmap, states, sea_colors, set(), _idx(B))
    assert any("missing loc key" in e for e in miss), f"missing HUB_NAME must fail, got {miss}"
    stale = vm._check_hub_anchors(bitmap, states, sea_colors, loc_keys, _idx((99, 99, 99)))
    assert any("stale index" in e for e in stale), f"a stale index colour must fail, got {stale}"

    # #3666: the one-non-stack-hub-per-province rule counts PASSABLE provinces only.
    keys2 = loc_keys | {"HUB_NAME_STATE_TEST_city", "HUB_NAME_STATE_TEST_farm"}

    def _two(stack=False):
        farm = {"name": "Farmstead", "hub": "farm", "resolved": [2, 5], "anchor": [2, 5],
                "province_color": list(A), "province_label": 1}
        if stack:
            farm["stack_on"] = "city"
        return {"hubs": [{"name": "Town", "hub": "city", "resolved": [2, 5], "anchor": [2, 5],
                          "province_color": list(A), "province_label": 1}, farm]}

    shared = vm._check_hub_anchors(bitmap, states, sea_colors, keys2, _two())
    assert any("share province" in e for e in shared), \
        f"two non-stack hubs on one province of a 2-passable-province state must fail, got {shared}"
    st.impassable = [B]
    ok_small = vm._check_hub_anchors(bitmap, states, sea_colors, keys2, _two())
    assert not any("share province" in e for e in ok_small), \
        f"with only 1 passable province, sharing is legitimate, got {ok_small}"
    st.impassable = []
    stacked = vm._check_hub_anchors(bitmap, states, sea_colors, keys2, _two(stack=True))
    assert stacked == [], f"a stack_on row sharing its host's province must pass, got {stacked}"


def _selfcheck_hub_stack() -> None:
    """Board #3666 unified stacking contract: ``stack_on`` rows bind to their host
    by exact anchor equality, seed nothing, are indexed with the host's colour and
    the POST-cut region, and the validator enforces host colour + coastal port."""
    import generate_provinces as gp
    import validate_map as vm
    from pathlib import Path
    from worldgen import schema

    def row(hub, name, anchor, stack_on="", state="S"):
        return schema.HubRow(state=state, hub=hub, name=name, anchor=anchor,
                             source="invented", note="", stack_on=stack_on)

    def raises(rows, frag):
        try:
            schema.check_hub_stacking(rows)
        except schema.SchemaError as e:
            assert frag in str(e), f"expected '{frag}' in: {e}"
            return str(e)
        raise AssertionError(f"expected a SchemaError containing '{frag}'")

    # --- worksheet binding rules
    pair = [row("city", "Host", (5, 5)), row("port", "Quay", (5, 5), stack_on="city")]
    schema.check_hub_stacking(pair)                                   # shared-anchor pair ok
    raises([row("city", "A", (5, 5)), row("farm", "B", (5, 5))], "non-stack rows")
    raises([row("city", "A", (5, 5)), row("port", "Stray", (6, 6), stack_on="city")], "stray stack row")
    raises([row("city", "A", (5, 5)), row("farm", "F", (5, 5), stack_on="city"),
            row("mine", "M", (5, 5), stack_on="farm")], "itself a stack row")
    raises([row("city", "A", (5, 5)), row("farm", "F", (5, 5), stack_on="farm")], "stack_on == hub")
    raises([row("city", "A", (5, 5)), row("farm", "F", (5, 5), stack_on="mine")], "the seeded row")
    # all problems listed at once
    many = raises([row("city", "A", (5, 5)), row("farm", "B", (5, 5)),
                   row("port", "Stray", (9, 9), stack_on="city")], "non-stack rows")
    assert "stray stack row" in many, f"every problem must be listed together: {many}"
    try:
        schema.HubRow.from_dict({"state": "S", "hub": "farm", "name": "x", "anchor": [1, 1],
                                 "source": "invented", "stack_on": "harbour"}, "t")
        raise AssertionError("an unknown stack_on hub type must be refused")
    except schema.SchemaError:
        pass

    # --- plan_hub_seeds: stack rows seed nothing and skip MIN_ANCHOR_SEP
    reg = np.zeros((40, 40), dtype=np.int32)
    reg[:, :20] = 1
    reg[:, 20:] = 2
    seeds_pair, rows_pair = gp.plan_hub_seeds(pair, reg, set())
    assert seeds_pair == {1: [(5, 5)]}, f"only the host seeds, got {seeds_pair}"
    assert len(rows_pair) == 2, "the stack row is still resolved + indexed"
    base = [row("city", "Host", (5, 5)), row("farm", "Far", (5, 30)), row("city", "East", (30, 5))]
    seeds_base, _ = gp.plan_hub_seeds(base, reg, set())
    seeds_more, _ = gp.plan_hub_seeds(base + [row("mine", "Pit", (5, 30), stack_on="farm")], reg, set())
    assert seeds_base == seeds_more, "adding a stack row must not change the seeds (the cut)"
    try:
        gp.plan_hub_seeds([row("city", "A", (5, 5)), row("farm", "B", (5, 10))], reg, set())
        raise AssertionError("two seeded same-region anchors < MIN_ANCHOR_SEP must raise")
    except ValueError:
        pass

    # --- plan_hub_seeds: water-crossing min-sep waiver (board #5399 follow-up,
    # Zorn Uzkul / Great Slave Port opposite-fjord-shores case)
    close_pair = [row("city", "A", (5, 5)), row("farm", "B", (5, 10))]
    land_strip = np.ones((40, 40), dtype=bool)
    land_strip[7:9, :] = False   # a water channel between y=5 and y=10 at x=5
    assert gp._segment_crosses_water(land_strip, 5, 5, 5, 10), "sanity: the strip must be crossed"
    seeds_waived, _ = gp.plan_hub_seeds(close_pair, reg, set(), land=land_strip)
    assert seeds_waived == {1: [(5, 5), (5, 10)]}, \
        "opposite shores of water must waive the min-sep check, both anchors still seed"
    land_no_strip = np.ones((40, 40), dtype=bool)   # same pair, no water between them
    try:
        gp.plan_hub_seeds(close_pair, reg, set(), land=land_no_strip)
        raise AssertionError("close anchors with no water between them must still raise, even with land given")
    except ValueError:
        pass

    # --- hub_index_entries: host colour, post-cut region, stack_on only on stack rows
    land_lab = np.zeros((40, 40), dtype=np.int32)
    land_lab[:, :10] = 1
    land_lab[:, 10:] = 2
    reg_of = np.array([0, 7, 2], dtype=np.int32)       # province 1 moved to region 7 post-cut
    palette = np.array([[0, 0, 0], [10, 20, 30], [40, 50, 60]], dtype=np.uint8)
    ents = gp.hub_index_entries(rows_pair, land_lab, reg_of, palette)
    assert ents[0]["province_color"] == ents[1]["province_color"] == [10, 20, 30]
    assert ents[0]["region"] == ents[1]["region"] == 7, "region is reg_of[plab], post-cut"
    assert "stack_on" not in ents[0] and ents[1]["stack_on"] == "city"
    _, rows_nostack = gp.plan_hub_seeds(base, reg, set())
    nostack = gp.hub_index_entries(rows_nostack, land_lab, reg_of, palette)
    assert all("stack_on" not in e for e in nostack), "no-stack rows keep the pre-#3666 shape"
    assert json.dumps(nostack) == json.dumps(gp.hub_index_entries(rows_nostack, land_lab, reg_of, palette)), \
        "byte-identical across runs"

    # --- validator: host colour + coastal port host
    A, B, SEA = (10, 20, 30), (40, 50, 60), (0, 0, 200)
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    rgb[0:4, :] = A          # non-coastal (coastal_colors wraps x, never y)
    rgb[4:7, :] = B          # coastal
    rgb[7:10, :] = SEA
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "p.png"
        write_rgb_png(png, rgb)
        bitmap = vm.ProvinceBitmap(png, wrap_x=False)
    st = vm.ParsedState("STATE_T", "02_empire.txt")
    st.provinces = [A, B]
    loc = {f"HUB_NAME_STATE_T_{h}" for h in ("city", "port", "farm", "mine", "wood")}

    def idx(host_col, host_px, stack_col=None, stack_hub="port"):
        stack_col = host_col if stack_col is None else stack_col
        return {"hubs": [
            {"name": "Host", "hub": "city", "anchor": list(host_px), "resolved": list(host_px),
             "province_color": list(host_col), "province_label": 1},
            {"name": "Stacked", "hub": stack_hub, "anchor": list(host_px), "resolved": list(host_px),
             "province_color": list(stack_col), "province_label": 1, "stack_on": "city"}]}

    st.hubs = {"city": B, "port": B, "farm": A, "mine": A, "wood": A}
    good = vm._check_hub_anchors(bitmap, [st], {SEA}, loc, idx(B, (5, 5)))
    assert good == [], f"a port stacked on a coastal host must pass, got {good}"
    st.hubs = {"city": A, "port": A, "farm": B, "mine": B, "wood": B}
    inland = vm._check_hub_anchors(bitmap, [st], {SEA}, loc, idx(A, (5, 2)))
    assert any("coastal host" in e for e in inland), f"a port stacked on an inland host must fail, got {inland}"
    st.hubs = {"city": B, "port": B, "farm": A, "mine": A, "wood": A}
    wrong = vm._check_hub_anchors(bitmap, [st], {SEA}, loc, idx(B, (5, 5), stack_col=A))
    assert any("!= host province" in e for e in wrong), f"stack colour != host colour must fail, got {wrong}"
    orphan = {"hubs": [idx(B, (5, 5))["hubs"][1]]}
    assert any("no seeded host" in e for e in vm._check_hub_anchors(bitmap, [st], {SEA}, loc, orphan)), \
        "a stack entry with no host in the index must fail"
    print("hub stacking (#3666): worksheet binding, seeds, index, validator checks passed.")


def _selfcheck_adjacencies() -> None:
    """Board #5563: yellow line -> crossing extraction, worksheet matching, CSV
    emission (bottom-origin y, sorted, byte-identical) and the semantic validator."""
    import json
    import validate_map as vm
    from pathlib import Path
    from worldgen import adjacencies as adj
    from worldgen import schema

    H, W = 40, 60
    cols = [(10, 0, 0), (20, 0, 0), (30, 0, 0), (40, 0, 0), (50, 0, 0), (60, 0, 0)]
    A, B, C, D, E, F = cols
    rgb = np.zeros((H, W, 3), dtype=np.uint8)
    for i, c in enumerate(cols):
        rgb[:, i * 10:(i + 1) * 10] = c
    rgb[0:2, 30:32] = E  # a 3-province corner at (30, 1): an ambiguous tip
    code = ((rgb[..., 0].astype(np.uint32) << 16) | (rgb[..., 1].astype(np.uint32) << 8)
            | rgb[..., 2].astype(np.uint32))
    kinds = {c: "land" for c in cols}
    mask = np.zeros((H, W), dtype=bool)
    mask[5, 5:26] = True                      # straight A -> C
    mask[20:31, 5] = True                     # bent A -> C
    mask[30, 5:26] = True
    mask[35, 32:49] = True                    # T junction (bad-shape)
    mask[30:36, 40] = True
    mask[20, 46:55] = True                    # loop (bad-shape)
    mask[28, 46:55] = True
    mask[20:29, 46] = True
    mask[20:29, 54] = True
    mask[3, 15:26] = True                     # B -> C: touching provinces
    mask[1, 5:31] = True                      # A -> border tip (ambiguous)
    mask[5, 52:58] = True                     # F -> F (same province)
    mask[37, 55] = True                       # dot
    touching = {frozenset((cols[i], cols[i + 1])) for i in range(5)}
    lines = adj.extract_lines(mask, wrap_x=False)
    assert len(lines) == 8, f"expected 8 components, got {len(lines)}"
    assert lines == adj.extract_lines(mask, wrap_x=False), "extraction must be deterministic"
    crossings, skipped = adj.classify_lines(lines, code, kinds, touching, wrap_x=False)
    reasons = " | ".join(s.reason for s in skipped)
    assert len(crossings) == 2, f"straight + bent lines resolve, got {len(crossings)}: {reasons}"
    assert reasons.count("bad-shape") == 3, reasons     # T, loop, dot
    assert "touching" in reasons and "ambiguous" in reasons and "same-province" in reasons, reasons
    for c in crossings:
        assert c.from_color == A and c.to_color == C, "From must be the lower colour code"

    class _Pin:
        a, b, a_color, b_color = (5, 1), (30, 1), None, D

    pinned, _ = adj.classify_lines(lines, code, kinds, touching, pins=[_Pin], wrap_x=False)
    assert len(pinned) == 3, "a pinned ambiguous endpoint must resolve"

    def _row(a, b, t, comment=""):
        return schema.AdjacencyRow(a=a, b=b, type=t, comment=comment)

    straight = min(crossings, key=lambda c: c.start[1] if c.start[0] == 5 else 99)
    bent = max(crossings, key=lambda c: c.start[1])
    rows = [_row((straight.start[0] + 2, straight.start[1]), straight.stop, "sea", "Straight"),
            _row(bent.stop, (bent.start[0], bent.start[1] - 1), "sea")]
    pairs, untyped, errs = adj.match_worksheet(crossings, rows, W)
    assert not errs and len(pairs) == 2 and not untyped, (errs, pairs)
    _, untyped1, errs1 = adj.match_worksheet(crossings, rows[:1], W)
    assert not errs1 and len(untyped1) == 1, "a line with no row is reported untyped"
    _, _, stale = adj.match_worksheet(crossings, rows + [_row((1, 1), (2, 2), "sea")], W)
    assert any("matches no drawn line" in e for e in stale), "a stale row is a hard error"
    _, _, dbl = adj.match_worksheet(
        crossings, rows + [_row(straight.start, straight.stop, "sea")], W)
    assert any("claimed by 2" in e for e in dbl), "two rows on one line is a hard error"

    tk = {A: "land", C: "land"}
    assert adj.type_kind_errors(pairs, tk) == [], "sea rows join land to land"
    assert len(adj.type_kind_errors([(pairs[0][0], _row((1, 1), (2, 2), "canal_x"))], tk)) == 1
    # sync: typed rows survive a redraw; new lines get blank rows; unmatched rows are parked
    C0 = adj.Crossing(A, C, (5, 5), (25, 5), 21, (15, 5))
    C1 = adj.Crossing(A, C, (5, 20), (25, 30), 30, (15, 25))
    C2 = adj.Crossing(A, C, (40, 3), (52, 9), 14, (46, 6))
    raw = [{"a": [27, 5], "b": [6, 6], "type": "sea", "comment": "Shifted", "a_color": "xAA0000"},
           {"a": [5, 21], "b": [25, 30], "type": "canal_x", "comment": "Kept"},
           {"a": [1, 1], "b": [2, 2], "type": "sea", "comment": "Gone"}]
    srows, sstale, serrs, sstats = adj.sync_worksheet([C0, C1, C2], raw, W)
    assert not serrs and sstats == {"kept": 2, "moved": 2, "new": 1, "stale": 1}, (serrs, sstats)
    assert [r["type"] for r in srows] == ["sea", "canal_x", ""], "types follow their lines"
    assert srows[0]["comment"] == "Shifted" and srows[0]["a_color"] == "xAA0000", "extra fields kept"
    assert srows[0]["a"] == [25, 5] and srows[0]["b"] == [5, 5], "row orientation kept, endpoints refreshed"
    assert srows[2]["a"] == [40, 3] and srows[2]["comment"] == ""
    assert sstale == [raw[2]], "an unmatched row is parked, not deleted"
    again, stale2, _, st2 = adj.sync_worksheet([C0, C1, C2], srows, W)
    assert again == srows and not stale2 and st2["moved"] == 0, "sync is idempotent"
    _, _, amb, _ = adj.sync_worksheet([C0, C1, C2], raw + [dict(raw[1])], W)
    assert any("claimed by 2" in e for e in amb), "ambiguity leaves everything untouched"
    blank_pairs = [(C0, schema.AdjacencyRow(a=C0.start, b=C0.stop, type="", comment=""))]
    assert adj.emit_csv(blank_pairs, H) == adj.ADJACENCIES_HEADER, "an untyped stub is not emitted"
    text = adj.emit_csv(pairs, H)
    assert text == adj.emit_csv(list(reversed(pairs)), H) == adj.emit_csv(pairs, H)
    out = text.split("\n")
    assert out[0] == adj.ADJACENCIES_HEADER and len(out) == 3 and not text.endswith("\n")
    f = out[1].split(";")
    assert f[:4] == ["x0A0000", "x1E0000", "sea", "-1"] and f[8] == "" and f[9] == "Straight"
    assert (int(f[5]), int(f[7])) == (H - 1 - straight.start[1], H - 1 - straight.stop[1])
    assert out[2].split(";")[9] == "None", "blank comment mirrors vanilla's None"

    # wrap-seam line: one component, endpoints in-bounds, resolves across the seam
    W2 = 30
    rgb2 = np.zeros((H, W2, 3), dtype=np.uint8)
    seg = [(0, 4), (4, 11), (11, 20), (20, 26), (26, 30)]
    pc = [(1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0), (5, 0, 0)]
    for (x0, x1), c in zip(seg, pc):
        rgb2[:, x0:x1] = c
    code2 = ((rgb2[..., 0].astype(np.uint32) << 16) | (rgb2[..., 1].astype(np.uint32) << 8)
             | rgb2[..., 2].astype(np.uint32))
    m2 = np.zeros((H, W2), dtype=bool)
    m2[5, 22:30] = True
    m2[5, 0:3] = True
    ln2 = adj.extract_lines(m2, wrap_x=True)
    assert len(ln2) == 1 and ln2[0].a is not None, "a seam-crossing line is one component"
    cr2, sk2 = adj.classify_lines(ln2, code2, {c: "land" for c in pc}, None, wrap_x=True)
    assert len(cr2) == 1 and {cr2[0].from_color, cr2[0].to_color} == {pc[0], pc[3]}, (cr2, sk2)
    assert all(0 <= p[0] < W2 for p in (cr2[0].start, cr2[0].stop))

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "w.json"
        assert schema.load_adjacency_worksheet(ws, (W, H)) == [], "absent worksheet is dormant"

        def _load(rows_):
            ws.write_text(json.dumps({"adjacencies": rows_}), encoding="utf-8")
            return schema.load_adjacency_worksheet(ws, (W, H))

        assert _load([]) == []
        ok = {"a": [1, 2], "b": [30, 4], "type": "sea"}
        assert len(_load([ok, {**ok, "a": [3, 3], "type": "canal_x", "a_color": "xAA0000"}])) == 2
        assert _load([{**ok, "type": ""}])[0].type == "", "a blank type is an untyped stub, not an error"
        for bad in ({**ok, "type": "canal_"}, {**ok, "type": "tunnel"}, {**ok, "b": [999, 4]},
                    {**ok, "comment": "a;b"}, {**ok, "a_color": "red"}):
            try:
                _load([bad])
            except schema.SchemaError:
                pass
            else:
                raise AssertionError(f"worksheet must refuse {bad}")
        try:
            _load([ok, {**ok, "a": [30, 4], "b": [1, 2]}])
        except schema.SchemaError:
            pass
        else:
            raise AssertionError("a duplicate endpoint pair must be refused")

        # validator: horizontal bands make y matter (pixel row = H-1-y)
        P, Q, R, S = (1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0)
        brgb = np.zeros((H, W, 3), dtype=np.uint8)
        for i, c in enumerate((P, Q, R, S)):
            brgb[i * 10:(i + 1) * 10, :] = c
        png = Path(td) / "b.png"
        write_rgb_png(png, brgb)
        bitmap = vm.ProvinceBitmap(png, wrap_x=False)
        cells = [{"color": list(c), "kind": k}
                 for c, k in ((P, "land"), (Q, "sea"), (R, "land"), (S, "sea"))]
        cells.append({"color": [9, 9, 9], "kind": "lake"})
        sd = Path(td) / "straits"
        sd.mkdir()
        # P touches only Q; R touches both Q and S — a valid "opposite shores" canal
        # (board #5744) needs only that each land endpoint touch a *different* one
        # of the two sea endpoints, not that it touch *only* one.
        (sd / "s.txt").write_text(
            "canal_ok = {\n\ttype = artificial\n\ttotal_block_requires_full_control = no\n"
            "\tmilitary_block_requires_full_control = no\n"
            "\tfirst_land_endpoint = x010000\n\tsecond_land_endpoint = x030000\n"
            "\tfirst_sea_endpoint = x020000\n\tsecond_sea_endpoint = x040000\n}\n",
            encoding="utf-8")
        csv = Path(td) / "adjacencies.csv"

        def _errs(row):
            csv.write_text(adj.ADJACENCIES_HEADER + "\n" + row, encoding="utf-8")
            return vm._check_adjacency_rows(csv, bitmap, cells, sd)

        good = "x010000;x030000;sea;-1;5;34;20;14;;None"   # pixel rows 5 (P) and 25 (R)
        assert _errs(good) == [], _errs(good)
        csv.write_text(adj.ADJACENCIES_HEADER, encoding="utf-8")
        assert vm._check_adjacency_rows(csv, bitmap, cells, sd) == [], "header-only skips"
        assert any("within 3 px" in e for e in _errs("x010000;x030000;sea;-1;5;5;20;25;;None")), \
            "top-origin y (not flipped) must fail"
        assert _errs("x020000;x040000;canal_ok;-1;5;24;20;4;;None") == [], "canal joins sea to sea"
        assert any("joins land to land" in e for e in _errs("x020000;x040000;sea;-1;5;24;20;4;;None")), \
            "a sea row joining sea to sea must fail"
        assert any("joins sea to sea" in e for e in _errs("x010000;x030000;canal_ok;-1;5;34;20;14;;None")), \
            "a canal row joining land to land must fail"
        assert any("Type" in e for e in _errs("x010000;x030000;canal_bad;-1;5;34;20;14;;None"))
        assert any("already touch" in e for e in _errs("x010000;x020000;sea;-1;5;34;5;24;;None"))

        # A canal row is exempt from the touching-provinces skip (board #5744):
        # two sea provinces that touch (Sea1/Sea2 here) would otherwise be flagged
        # "already touch", but a canal's whole point is a controllable chokepoint
        # even when the two seas also connect some other way.
        L, Sea1, Sea2 = (11, 0, 0), (12, 0, 0), (13, 0, 0)
        trgb = np.zeros((30, W, 3), dtype=np.uint8)
        for i, c in enumerate((L, Sea1, Sea2)):
            trgb[i * 10:(i + 1) * 10, :] = c
        tpng = Path(td) / "t.png"
        write_rgb_png(tpng, trgb)
        tbitmap = vm.ProvinceBitmap(tpng, wrap_x=False)
        tcells = [{"color": list(c), "kind": k}
                 for c, k in ((L, "land"), (Sea1, "sea"), (Sea2, "sea"))]
        tsd = Path(td) / "straits2"
        tsd.mkdir()
        (tsd / "s.txt").write_text(
            "canal_touch = {\n\ttype = artificial\n\ttotal_block_requires_full_control = no\n"
            "\tmilitary_block_requires_full_control = no\n"
            "\tfirst_land_endpoint = xFF00AA\n\tsecond_land_endpoint = xFF00AB\n"
            "\tfirst_sea_endpoint = x0C0000\n\tsecond_sea_endpoint = x0D0000\n}\n",
            encoding="utf-8")
        tcsv = Path(td) / "t_adj.csv"
        tcsv.write_text(adj.ADJACENCIES_HEADER + "\nx0C0000;x0D0000;canal_touch;-1;5;24;5;14;;None",
                        encoding="utf-8")
        touch_errs = vm._check_adjacency_rows(tcsv, tbitmap, tcells, tsd)
        assert not any("already touch" in e for e in touch_errs), touch_errs
        tcsv.write_text(adj.ADJACENCIES_HEADER + "\nx0C0000;x0D0000;sea;-1;5;24;5;14;;None",
                        encoding="utf-8")
        assert any("already touch" in e for e in
                   vm._check_adjacency_rows(tcsv, tbitmap, tcells, tsd)), \
            "an ordinary 'sea' row is still caught by the touching-provinces skip"

        # _check_strait_block content checks, in isolation (board #5744)
        Pc, Qc, Rc, Sc, Lakec = (1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0), (9, 9, 9)
        idx_colors = {Pc, Qc, Rc, Sc, Lakec}
        knd = {Pc: "land", Qc: "sea", Rc: "land", Sc: "sea", Lakec: "lake"}
        touch = {frozenset((Pc, Qc)), frozenset((Rc, Qc)), frozenset((Rc, Sc))}
        good_fields = {"first_sea_endpoint": "x020000", "second_sea_endpoint": "x040000",
                      "first_land_endpoint": "x010000", "second_land_endpoint": "x030000"}
        assert vm._check_strait_block("t", "c", good_fields, Qc, Sc, idx_colors, knd, touch) == []
        missing = dict(good_fields)
        del missing["first_land_endpoint"]
        assert any("has no first_land_endpoint" in e for e in
                   vm._check_strait_block("t", "c", missing, Qc, Sc, idx_colors, knd, touch))
        mismatched = {**good_fields, "first_sea_endpoint": "x090909"}
        assert any("sea endpoints don't match" in e for e in
                   vm._check_strait_block("t", "c", mismatched, Qc, Sc, idx_colors, knd, touch))
        not_land = {**good_fields, "first_land_endpoint": "x020000"}  # Q is sea, not land
        assert any("not land" in e for e in
                   vm._check_strait_block("t", "c", not_land, Qc, Sc, idx_colors, knd, touch))
        unknown_color = {**good_fields, "first_land_endpoint": "xABCDEF"}
        assert any("not a province" in e for e in
                   vm._check_strait_block("t", "c", unknown_color, Qc, Sc, idx_colors, knd, touch))
        same_land = {**good_fields, "second_land_endpoint": "x010000"}
        assert any("must be distinct" in e for e in
                   vm._check_strait_block("t", "c", same_land, Qc, Sc, idx_colors, knd, touch))
        # both land endpoints only touch Q (Sc), never Rc's actual far shore -> same side
        one_side_touch = {frozenset((Pc, Qc)), frozenset((Rc, Qc))}  # Rc no longer touches Sc
        assert any("opposite shores" in e for e in
                   vm._check_strait_block("t", "c", good_fields, Qc, Sc, idx_colors, knd,
                                          one_side_touch))
        blocks = vm._parse_strait_blocks(sd)
        assert set(blocks) == {"canal_ok"} and blocks["canal_ok"]["type"] == "artificial"
        assert any("not a province" in e
                   for e in _errs("x010000;xABCDEF;sea;-1;5;34;20;14;;None"))
        assert any("same province" in e for e in _errs("x010000;x010000;sea;-1;5;34;20;34;;None"))
        assert any("lake" in e for e in _errs("x010000;x090909;sea;-1;5;34;20;14;;None"))
        assert any("Through" in e for e in _errs("x010000;x030000;sea;0;5;34;20;14;;None"))
        assert any("rule_name" in e for e in _errs("x010000;x030000;sea;-1;5;34;20;14;r;None"))
        csv.write_text(adj.ADJACENCIES_HEADER + "\nx010000;x030000;sea", encoding="utf-8")
        assert vm._check_adjacencies(csv), "a bad column count must fail the parse check"


def _selfcheck_canal_junctions() -> None:
    """Board #5744: a canal drawn as a 4-arm "+"/"X" junction decomposes into a
    sea pair (an ordinary :class:`adj.Crossing`, unchanged downstream) + a land
    pair, by resolved province kind, on a synthetic mask — no dependency on the
    real source."""
    from worldgen import adjacencies as adj

    H = W = 30
    Land1, Sea1, Sea2, Land2 = (10, 0, 0), (10, 1, 0), (10, 2, 0), (10, 3, 0)
    rgb = np.zeros((H, W, 3), dtype=np.uint8)
    rgb[:15, :15] = Land1
    rgb[:15, 15:] = Sea1
    rgb[15:, :15] = Sea2
    rgb[15:, 15:] = Land2
    code = ((rgb[..., 0].astype(np.uint32) << 16) | (rgb[..., 1].astype(np.uint32) << 8)
            | rgb[..., 2].astype(np.uint32))
    kinds = {Land1: "land", Sea1: "sea", Sea2: "sea", Land2: "land"}

    def _x_mask(arm: int = 9) -> np.ndarray:
        """A clean 4-arm "X" from (15,15), one arm per quadrant."""
        m = np.zeros((H, W), dtype=bool)
        m[15, 15] = True
        for d in range(1, arm + 1):
            m[15 - d, 15 - d] = m[15 - d, 15 + d] = True
            m[15 + d, 15 - d] = m[15 + d, 15 + d] = True
        return m

    def _plateau_mask(arm: int = 9) -> np.ndarray:
        """A 4-arm "+" whose intersection is *two* branch pixels 2px apart
        bridged by one degree-2 pixel — the measured plateau (board #5744) that
        :func:`adj._junction_clusters` must collapse to one logical junction via
        its short (<=SPUR_PX) connecting chain, not report as 2 separate ones."""
        m = np.zeros((H, W), dtype=bool)
        m[15, 14] = m[15, 15] = m[15, 16] = True  # the 2px-apart bridge
        for d in range(1, arm + 1):
            m[15 - d, 14] = True   # N arm off the left branch pixel
            m[15, 14 - d] = True   # W arm off the left branch pixel
            m[15 + d, 16] = True   # S arm off the right branch pixel
            m[15, 16 + d] = True   # E arm off the right branch pixel
        return m

    mask = _x_mask()
    lines = adj.extract_lines(mask, wrap_x=False)
    assert len(lines) == 1 and lines[0].leaves is not None, lines
    crossings, skipped = adj.classify_lines(lines, code, kinds, touching=set(), wrap_x=False)
    assert not skipped, skipped
    assert len(crossings) == 1
    c = crossings[0]
    assert {c.from_color, c.to_color} == {Sea1, Sea2}, c
    assert c.land_pair is not None and set(c.land_pair) == {Land1, Land2}, c
    assert c.land_points is not None and len(c.land_points) == 2

    # the plateau case: two branch pixels bridged by a short chain still resolve
    # to one logical junction. Tips (N, W, S, E) land far from the "X" mask's
    # quadrant split, so colour by small patches at the known tip coordinates
    # instead of reusing the quadrant grid.
    prgb = np.full((H, W, 3), Land1, dtype=np.uint8)
    for (ty, tx), col in (((6, 14), Land1), ((15, 5), Sea2), ((24, 16), Land2), ((15, 25), Sea1)):
        prgb[max(0, ty - 2):ty + 3, max(0, tx - 2):tx + 3] = col
    pcode = ((prgb[..., 0].astype(np.uint32) << 16) | (prgb[..., 1].astype(np.uint32) << 8)
            | prgb[..., 2].astype(np.uint32))
    gapped = adj.extract_lines(_plateau_mask(), wrap_x=False)
    assert len(gapped) == 1 and gapped[0].leaves is not None, \
        "two branch pixels bridged by a short (<=SPUR_PX) chain is one logical junction"
    gc, gs = adj.classify_lines(gapped, pcode, kinds, touching=set(), wrap_x=False)
    assert len(gc) == 1 and not gs, (gc, gs)
    assert {gc[0].from_color, gc[0].to_color} == {Sea1, Sea2} and set(gc[0].land_pair) == {Land1, Land2}

    # a canal's sea pair is exempt from the touching-provinces skip
    touching = {frozenset((Sea1, Sea2))}
    ct, st = adj.classify_lines(lines, code, kinds, touching=touching, wrap_x=False)
    assert len(ct) == 1 and not st, "junction sea pair ignores the touching skip"

    # 3 leaves (two marks too close together to tell apart) -> named skip
    m3 = _x_mask()
    m3[15 - 9:15, 15 - 9:15] = False  # erase the NW arm entirely
    l3 = adj.extract_lines(m3, wrap_x=False)
    assert len(l3) == 1 and l3[0].leaves is None and "3 leaves" in l3[0].reason, l3

    # all 4 leaves the same kind -> no valid sea/land split
    all_land_kinds = {Land1: "land", Sea1: "land", Sea2: "land", Land2: "land"}
    _, sk_all = adj.classify_lines(lines, code, all_land_kinds, touching=set(), wrap_x=False)
    assert len(sk_all) == 1 and "no leaf pairing" in sk_all[0].reason, sk_all

    # two leaves resolving to the SAME land colour are not a valid land pair
    same_land_rgb = rgb.copy()
    same_land_rgb[15:, 15:] = Land1  # SE quadrant now also Land1
    same_code = ((same_land_rgb[..., 0].astype(np.uint32) << 16)
                | (same_land_rgb[..., 1].astype(np.uint32) << 8) | same_land_rgb[..., 2])
    _, sk_same = adj.classify_lines(lines, same_code, kinds, touching=set(), wrap_x=False)
    assert len(sk_same) == 1 and "no leaf pairing" in sk_same[0].reason, sk_same

    # a lake leaf can never join a valid pair (kind must be exactly "land"/"sea")
    lake_kinds = dict(kinds)
    lake_kinds[Land2] = "lake"
    _, sk_lake = adj.classify_lines(lines, code, lake_kinds, touching=set(), wrap_x=False)
    assert len(sk_lake) == 1 and "no leaf pairing" in sk_lake[0].reason, sk_lake

    # worksheet identity survives a canal's redraw from a plain line to a "+":
    # a stale row's a/b (the line's pre-redraw endpoints) match the new
    # crossing's land_points, not its start/stop, and it keeps its type/comment.
    old_a, old_b = c.land_points  # the line's pre-redraw (land-side) endpoints
    raw = [{"a": [old_a[0], old_a[1]], "b": [old_b[0], old_b[1]],
           "type": "canal_x", "comment": "Kept across redraw"}]
    srows, sstale, serrs, sstats = adj.sync_worksheet(crossings, raw, W)
    assert not serrs and not sstale and sstats["kept"] == 1, (serrs, sstale, sstats)
    assert srows[0]["type"] == "canal_x" and srows[0]["comment"] == "Kept across redraw"
    assert tuple(srows[0]["a"]) in (c.start, c.stop), "endpoints refreshed to the sea pair"


def _selfcheck_stack_hubs() -> None:
    """Hub-stacking fallback (worldgen.statefile.stack_hubs), in isolation.

    Pins the property board #2930's placeholder/small-region states rely on: a
    single passable province stacks every hub onto itself (k=1, vanilla
    STATE_MALTA precedent — city+port on one province, farm+mine+wood on
    another), a state with fewer passable provinces than pick_hubs needs
    cycles city/farm/mine/wood deterministically across what it has
    (``ordered[i % k]``), the port prefers a coastal candidate over a larger
    non-coastal one, and a landlocked state never gets a port hub at all.
    """
    solo = [ProvinceInfo(color=(10, 20, 30), centroid=(5.0, 5.0), area=100,
                        coastal=True, impassable=False)]
    hubs = stack_hubs(solo, coastal=True)
    assert hubs["port"] == hubs["city"] == hubs["farm"] == hubs["mine"] == hubs["wood"] == (10, 20, 30), hubs

    two = [
        ProvinceInfo(color=(1, 1, 1), centroid=(1.0, 1.0), area=50, coastal=True, impassable=False),
        ProvinceInfo(color=(2, 2, 2), centroid=(2.0, 2.0), area=200, coastal=False, impassable=False),
    ]
    hubs2 = stack_hubs(two, coastal=True)
    assert hubs2["port"] == (1, 1, 1), "port must prefer the coastal candidate even if smaller"
    assert hubs2["city"] == (1, 1, 1) and hubs2["farm"] == (2, 2, 2), hubs2
    assert hubs2["mine"] == (1, 1, 1) and hubs2["wood"] == (2, 2, 2), "cycling must wrap i % k"

    landlocked = stack_hubs(
        [ProvinceInfo(color=(9, 9, 9), centroid=(0.0, 0.0), area=1, coastal=False, impassable=False)],
        coastal=False,
    )
    assert "port" not in landlocked, "a landlocked state must not get a port hub"


def _selfcheck_economics() -> None:
    """Per-state land economics (worldgen.land_economics, board #3678), in isolation.

    Pins the worksheet loader (full / partial / all-empty rows, permuted header, every
    rejection), the per-column fallback, check_economics against a synthetic building
    catalog, the byte-identical emission guarantee (an empty or default-reproducing row
    emits exactly today's text; a full row differs only in the three farmland lines),
    the identity check (stale key, dead anchor, placeholder, sea key) and the key rewrite,
    plus determinism. The validator-side rules are `_selfcheck_economics_validator`.
    """
    import csv

    from worldgen import land_economics as le
    from worldgen.statefile import render_land_state

    header = ["arable_note", "arable_resources", "subsistence_building", "arable_land",
              "anchor_y", "anchor_x", "state_key", "arable_source"]  # permuted

    def write(path: Path, rows: list[dict], cols: list[str] = header) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, restval="", extrasaction="ignore",
                               lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    full = {"state_key": "STATE_FULL", "anchor_x": "10", "anchor_y": "20", "arable_land": "40",
            "subsistence_building": "building_subsistence_orchard",
            "arable_resources": "building_rye_farm building_vineyard", "arable_note": "n", "arable_source": "s"}
    partial = {"state_key": "STATE_PARTIAL", "anchor_x": "11", "anchor_y": "21", "arable_land": "25"}
    empty = {"state_key": "STATE_EMPTY", "anchor_x": "12", "anchor_y": "22"}

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # (a) loader round-trip
        p = tmp / "ok.csv"
        write(p, [full, partial, empty])
        sheet = le.load_economics_worksheet(p)
        assert list(sheet.rows) == ["STATE_FULL", "STATE_PARTIAL", "STATE_EMPTY"], list(sheet.rows)
        f, pa, em = (sheet.rows[k] for k in ("STATE_FULL", "STATE_PARTIAL", "STATE_EMPTY"))
        assert f.anchor == (10, 20) and f.arable_land == 40, f
        assert f.subsistence_building == "building_subsistence_orchard", f
        assert f.arable_resources == ["building_rye_farm", "building_vineyard"], f
        assert f.arable_note == "n" and f.arable_source == "s" and f.has_values()
        assert pa.arable_land == 25 and pa.subsistence_building is None and pa.arable_resources is None
        assert not em.has_values() and em.arable_land is None
        # optional columns absent, BOM, CRLF, blank lines and cell whitespace tolerated
        bom = tmp / "bom.csv"
        bom.write_bytes("﻿state_key,anchor_x,anchor_y,arable_land\r\n\r\n STATE_B , 1 , 2 , 7 \r\n".encode("utf-8"))
        assert le.load_economics_worksheet(bom).rows["STATE_B"].arable_land == 7

        # (b) per-column fallback
        d = le.default_economics()
        assert le.resolve_economics(None, d) == d and le.resolve_economics(em, d) == d
        rp = le.resolve_economics(pa, d)
        assert rp.arable_land == 25 and rp.subsistence_building == d.subsistence_building
        assert rp.arable_resources == d.arable_resources and rp.capped_resources == d.capped_resources
        assert rp.arable_resources is not d.arable_resources, "resolve must copy the default's list"
        assert le.default_economics() == le.DEFAULT_ECONOMICS and le.default_economics() is not le.DEFAULT_ECONOMICS

        # (c) rejections
        base = {"state_key": "STATE_X", "anchor_x": "1", "anchor_y": "2"}

        def rejects(rows: list[dict], cols: list[str], what: str) -> None:
            bad = tmp / "bad.csv"
            write(bad, rows, cols)
            try:
                le.load_economics_worksheet(bad)
            except schema.SchemaError as exc:
                assert "bad.csv" in str(exc), exc
                return
            raise AssertionError(f"loader accepted {what}")

        cols = ["state_key", "anchor_x", "anchor_y", "arable_land", "arable_resources"]
        rejects([base], cols + ["arable_lnad"], "an unknown column")
        rejects([base, base], cols, "a duplicate key")
        rejects([{**base, "arable_land": "-1"}], cols, "arable_land -1")
        rejects([{**base, "arable_land": "ten"}], cols, "arable_land ten")
        rejects([{**base, "arable_land": "40.0"}], cols, "arable_land 40.0")
        rejects([{**base, "state_key": "state_x"}], cols, "a lowercase key")
        rejects([{**base, "state_key": "MOOTLAND"}], cols, "an unprefixed key")
        rejects([base], ["anchor_x", "anchor_y", "arable_land"], "a missing state_key column")
        rejects([base], ["state_key", "anchor_x", "arable_land"], "a missing anchor column")
        rejects([{**base, "anchor_x": "x"}], cols, "a non-integer anchor")
        rejects([{**base, "arable_resources": "building_rye_farm,building_vineyard"}], cols,
                "comma-joined ids")

        # (d) check_economics against a synthetic catalog
        cat = le.BuildingCatalog(
            groups={"building_wheat_farm": "bg_staple_crops", "building_rye_farm": "bg_staple_crops",
                    "building_livestock_ranch": "bg_ranching", "building_logging_camp": "bg_logging",
                    "building_subsistence_farm": "bg_subsistence_agriculture",
                    "building_subsistence_orchard": "bg_subsistence_agriculture",
                    "building_subsistence_fishing_village": "bg_subsistence_ranching"},
            rural=frozenset({"building_wheat_farm", "building_rye_farm", "building_livestock_ranch",
                             "building_subsistence_farm", "building_subsistence_orchard",
                             "building_subsistence_fishing_village"}),
            subsistence=frozenset({"building_subsistence_farm", "building_subsistence_orchard",
                                   "building_subsistence_fishing_village"}))

        def econ(**kw) -> schema.Economics:
            e = le.default_economics()
            return schema.Economics(kw.get("sub", e.subsistence_building), kw.get("land", e.arable_land),
                                    kw.get("res", e.arable_resources), kw.get("cap", e.capped_resources))

        errs, warns = le.check_economics("K", le.default_economics(), True, cat)
        assert errs == [] and warns == [], (errs, warns)
        for what, e in (
            ("unknown subsistence", econ(sub="building_subsistence_nope")),
            ("non-subsistence building as subsistence", econ(sub="building_wheat_farm")),
            ("unknown arable id", econ(res=["building_wheat_farm", "building_nope"])),
            ("unknown capped key", econ(cap={"building_nope": 1})),
            ("logging camp as arable (not rural)", econ(res=["building_logging_camp"])),
            ("duplicate arable id", econ(res=["building_wheat_farm", "building_wheat_farm"])),
            ("subsistence id in arable", econ(res=["building_wheat_farm", "building_subsistence_farm"])),
            ("empty arable_resources", econ(res=[])),
            ("negative arable_land", econ(land=-1)),
        ):
            errs, _ = le.check_economics("K", e, True, cat)
            assert errs and all(m.startswith("K:") for m in errs), (what, errs)
        fv = econ(sub=le.FISHING_VILLAGE)
        assert le.check_economics("K", fv, False, cat)[0], "fishing village on a landlocked state must error"
        assert le.check_economics("K", fv, True, cat) == ([], []), "fishing village on a coastal state is clean"
        errs, warns = le.check_economics("K", econ(land=5), True, cat)
        assert errs == [] and len(warns) == 1 and "MASS_MIGRATION_TARGET_MIN_ARABLE_LAND" in warns[0], warns
        assert le.check_economics("K", econ(land=0), True, cat)[1], "arable_land 0 warns, not errors"
        assert le.check_economics("K", econ(land=10), True, cat)[1] == []
        # catalog-free: id existence skipped, structural rules kept
        assert le.check_economics("K", econ(res=["building_nope"]), True, None) == ([], [])
        assert le.check_economics("K", econ(sub="building_nope"), True, None)[0]

        # (e) byte-identical emission: default == all-empty row; the full row differs in three lines only
        def emit(e: schema.Economics) -> str:
            st = schema.State(
                key="STATE_SYNTH", kind="land", macro="x",
                geometry=schema.StateGeometry(kind="seeds", polygon=None, holes=[], seeds=[(0.0, 0.0)]),
                coastal=True, naval_exit=None, economics=e, impassable=None)
            hubs = {h: (1, 2, 3) for h in ("city", "farm", "mine", "wood", "port")}
            return render_land_state(st, 400, [(1, 2, 3), (4, 5, 6)], hubs, [], 7)

        text_default = emit(d)
        assert emit(le.resolve_economics(em, d)) == text_default == emit(le.resolve_economics(None, d))
        text_full = emit(le.resolve_economics(f, d))
        diff = [(a, b) for a, b in zip(text_default.splitlines(), text_full.splitlines()) if a != b]
        assert len(diff) == 3 and len(text_default.splitlines()) == len(text_full.splitlines()), diff
        assert {a.split("=")[0].strip() for a, _ in diff} == {
            "subsistence_building", "arable_land", "arable_resources"}, diff

        # identity check + key rewrite (the generator and validator share this)
        ident = {"STATE_NEW": le.StateIdentity((10, 20), False), "STATE_OTHER": le.StateIdentity((30, 40), False),
                 "STATE_LAND_001": le.StateIdentity((50, 60), True)}

        def row(key: str, x: int, y: int, line: int = 2) -> le.EconomicsRow:
            return le.EconomicsRow(key, (x, y), None, None, None, "", "", line)

        errs, rk = le.check_worksheet_identity({"STATE_NEW": row("STATE_NEW", 10, 20)}, ident)
        assert errs == [] and rk == []
        errs, rk = le.check_worksheet_identity({"STATE_OLD": row("STATE_OLD", 10, 20, 5)}, ident)
        assert len(errs) == 1 and "STATE_NEW" in errs[0] and "--rekey-economics" in errs[0], errs
        assert [(r.state_key, n) for r, n in rk] == [("STATE_OLD", "STATE_NEW")]
        errs, rk = le.check_worksheet_identity({"STATE_NEW": row("STATE_NEW", 30, 40)}, ident)
        assert len(errs) == 1 and "different states" in errs[0] and rk == [], errs
        errs, rk = le.check_worksheet_identity({"STATE_NEW": row("STATE_NEW", 1, 1)}, ident)
        assert len(errs) == 1 and "re-anchor" in errs[0] and rk == [], errs
        errs, rk = le.check_worksheet_identity({"STATE_GONE": row("STATE_GONE", 1, 1)}, ident)
        assert len(errs) == 1 and "row dead" in errs[0] and rk == [], errs
        errs, rk = le.check_worksheet_identity({"STATE_LAND_001": row("STATE_LAND_001", 50, 60)}, ident)
        assert len(errs) == 1 and "placeholder" in errs[0], errs
        errs, rk = le.check_worksheet_identity({"STATE_SEA": row("STATE_SEA", 1, 1)}, ident, {"STATE_SEA"})
        assert len(errs) == 1 and "sea state" in errs[0], errs
        errs, rk = le.check_worksheet_identity(
            {"STATE_OLD": row("STATE_OLD", 10, 20), "STATE_OLDER": row("STATE_OLDER", 10, 20)}, ident)
        assert len(errs) == 2 and len(rk) == 1, "two stale rows must not claim the same state"
        csv_text = "state_key,anchor_x,anchor_y\r\nSTATE_OLD,10,20\r\nSTATE_OLD_2,10,20\r\n"
        out = le.rekey_worksheet_text(csv_text, [(row("STATE_OLD", 10, 20), "STATE_NEW")])
        assert out == "state_key,anchor_x,anchor_y\r\nSTATE_NEW,10,20\r\nSTATE_OLD_2,10,20\r\n", repr(out)

        # (g) determinism
        assert le.load_economics_worksheet(p) == sheet
        assert le.check_economics("K", econ(land=5, res=["building_nope", "building_nope"]), False, cat) == \
            le.check_economics("K", econ(land=5, res=["building_nope", "building_nope"]), False, cat)

    # the catalog loader on a synthetic mod: group chain, rural/subsistence flags, comments ignored
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "b").mkdir()
        (tmp / "g").mkdir()
        (tmp / "g" / "g.txt").write_text(
            "bg_agriculture = {\n\tland_usage = rural\n}\n"
            "bg_staple = {\n\tparent_group = bg_agriculture\n}\n"
            "bg_sub = {\n\tparent_group = bg_agriculture\n\tis_subsistence = yes\n}\n"
            "bg_mining = {\n\t# land_usage = rural\n}\n", encoding="utf-8")
        (tmp / "b" / "b.txt").write_text(
            "﻿# header { not a block\nbuilding_a = {\n\tbuilding_group = bg_staple\n"
            "\tpmgs = { x y }\n}\nbuilding_b = {\n\tbuilding_group = bg_sub\n}\n"
            "building_c = {\n\tbuilding_group = bg_mining\n}\n", encoding="utf-8")
        c = le.load_building_catalog(tmp / "b", tmp / "g")
        assert set(c.groups) == {"building_a", "building_b", "building_c"}, c.groups
        assert c.rural == {"building_a", "building_b"} and c.subsistence == {"building_b"}, c


def _selfcheck_economics_validator() -> None:
    """``validate_map._check_state_economics`` (board #3678) on synthetic ParsedStates: the
    emitted-file rules (fishing village needs the emitted ``port``, placeholders stay on the
    default, a missing field) and the worksheet cross-checks (state file disagrees with a filled
    cell, anchor not equal to ``naming_anchor``, unknown/placeholder row), warnings kept out of
    the errors, and the block parser."""
    import validate_map as vm
    from worldgen import land_economics as le

    def st(key: str, port: bool = False, land: int = 10, sub: str = "building_subsistence_farm",
           res: tuple[str, ...] = ("building_wheat_farm", "building_livestock_ranch"),
           provs: tuple = ((1, 1, 1),)) -> "vm.ParsedState":
        s = vm.ParsedState(key, "t.txt")
        s.provinces = list(provs)
        s.port_declared = port
        s.subsistence_building, s.arable_land, s.arable_resources = sub, land, list(res)
        return s

    own = {"STATE_A": {"naming_anchor": [10, 20], "scope": "drawn"},
           "STATE_B": {"naming_anchor": [30, 40], "scope": "drawn"},
           "STATE_LAND_001": {"naming_anchor": [50, 60], "scope": "placeholder"}}

    def sheet(*rows: "le.EconomicsRow") -> "le.EconomicsWorksheet":
        return le.EconomicsWorksheet({r.state_key: r for r in rows}, le.KNOWN_COLUMNS)

    def row(key, x, y, land=None, sub=None, res=None) -> "le.EconomicsRow":
        return le.EconomicsRow(key, (x, y), land, sub, res, "", "", 2)

    def run(states, sh=None, ownership=own, ph=frozenset()):
        warns: list[str] = []
        errs = vm._check_state_economics(states, [], None, set(ph), sh, ownership, warns)
        return errs, warns

    errs, warns = run([st("STATE_A"), st("STATE_B")])
    assert errs == [] and warns == [], (errs, warns)
    errs, _ = run([st("STATE_A", sub=le.FISHING_VILLAGE, port=False)])
    assert len(errs) == 1 and "port hub" in errs[0], errs
    assert run([st("STATE_A", sub=le.FISHING_VILLAGE, port=True)])[0] == []
    # Without the real-world-equivalents input a placeholder must carry the default economics;
    # with it (Chris, 2026-10-12) a placeholder carries its zone's share and any valid value passes.
    real_cfg = vm._REAL_WORLD_CONFIG
    try:
        vm._REAL_WORLD_CONFIG = Path("/nonexistent/real_world_equivalents.json")
        errs, _ = run([st("STATE_LAND_001", land=40)])
        assert any("default economics" in e for e in errs), "a placeholder off-default must error"
        errs, _ = run([st("STATE_X", land=40, provs=((9, 9, 9),))], ph={(9, 9, 9)}, ownership=None)
        assert any("default economics" in e for e in errs), "placeholder by province colour"
    finally:
        vm._REAL_WORLD_CONFIG = real_cfg
    vm._REAL_WORLD_CONFIG = Path(__file__)  # any existing file stands in for the present input
    try:
        errs, _ = run([st("STATE_LAND_001", land=40)])
        assert errs == [], errs
    finally:
        vm._REAL_WORLD_CONFIG = real_cfg
    errs, _ = run([st("STATE_A", res=())])
    assert any("missing" in e for e in errs), errs
    errs, warns = run([st("STATE_A", land=5)])
    assert errs == [] and len(warns) == 1 and "MASS_MIGRATION_TARGET_MIN_ARABLE_LAND" in warns[0], (errs, warns)
    # worksheet agreement
    states = [st("STATE_A", land=40), st("STATE_B")]
    errs, warns = run(states, sheet(row("STATE_A", 10, 20, land=40), row("STATE_B", 30, 40)))
    assert errs == [], errs
    assert warns == ["1 drawn state(s) still on default economics (no worksheet values)"], warns
    errs, _ = run(states, sheet(row("STATE_A", 10, 20, land=41)))
    assert len(errs) == 1 and "disagrees with the worksheet" in errs[0], errs
    errs, _ = run(states, sheet(row("STATE_A", 10, 20, sub="building_subsistence_orchard")))
    assert len(errs) == 1 and "subsistence_building" in errs[0], errs
    errs, _ = run(states, sheet(row("STATE_A", 11, 20, land=40)))
    assert len(errs) == 1 and "anchor" in errs[0], errs
    errs, _ = run(states, sheet(row("STATE_GONE", 1, 1)))
    assert len(errs) == 1 and "row dead" in errs[0], errs
    errs, _ = run(states + [st("STATE_LAND_001")], sheet(row("STATE_LAND_001", 50, 60)))
    assert len(errs) == 1 and "placeholder" in errs[0], errs
    assert run(states, sheet(row("STATE_A", 10, 20, land=40)))[0] == run(states, sheet(row("STATE_A", 10, 20, land=40)))[0]

    # the block parser reads what render_land_state emits
    parsed = vm._parse_block("STATE_P", 'id = 400\n\tsubsistence_building = "building_subsistence_orchard"\n'
                             '\tprovinces = { x010203 }\n\tarable_land = 25\n'
                             '\tarable_resources = { "building_rye_farm" "building_vineyard" }\n', "t.txt")
    assert (parsed.subsistence_building, parsed.arable_land, parsed.arable_resources) == (
        "building_subsistence_orchard", 25, ["building_rye_farm", "building_vineyard"]), vars(parsed)


def _selfcheck_province_terrains() -> None:
    """province_terrains.txt generator + validator (board #2968), in isolation.

    Pins what generate_province_terrains.py and validate_map.validate_province_terrains
    rely on: land cells emit ``"plains"`` and sea cells ``"ocean"``; lines are
    sorted by integer id (not index order); two runs are byte-identical; an empty
    cell list is refused rather than writing a truncated file; and the emitted file
    round-trips cleanly through the validator, whose bijection + valid-id checks can
    actually fail (a missing line, an extra line, and an undefined terrain id all
    error).
    """
    import generate_province_terrains as gpt
    import validate_map as vm

    # Deliberately id-out-of-order in the list, to prove the sort by id; a lake
    # cell (board #3742) maps to "lakes".
    cells = [
        {"hex": "xDDEEFF", "kind": "sea", "id": 3},
        {"hex": "xAABBCC", "kind": "land", "id": 1},
        {"hex": "x112233", "kind": "land", "id": 2},
        {"hex": "x445566", "kind": "lake", "id": 4},
    ]
    text = gpt.render_terrains(cells)
    body = [ln for ln in text.splitlines() if not ln.startswith("#")]
    assert body == ['xAABBCC="plains"', 'x112233="plains"', 'xDDEEFF="ocean"',
                    'x445566="lakes"'], body
    assert text.endswith("\n") and "\r" not in text, "LF newlines, trailing newline"
    assert text == gpt.render_terrains(cells), "two runs must be byte-identical"

    try:
        gpt.render_terrains([])
    except SystemExit:
        pass
    else:  # pragma: no cover
        raise AssertionError("an empty cell list must be refused, not written")

    # A terrain-defs file defining exactly the three ids the generator emits.
    with tempfile.TemporaryDirectory() as td:
        defs = Path(td) / "01_terrain.txt"
        defs.write_text("plains = {\n\tweight = 1\n}\nocean = {\n\tweight = 1\n}\n"
                        "lakes = {\n\tweight = 1\n}\n")
        assert vm._terrain_ids(defs) == {"plains", "ocean", "lakes"}, \
            "only column-0 keys are terrain ids"

        terrains = Path(td) / "province_terrains.txt"
        terrains.write_text(text)
        assert vm.validate_province_terrains(cells, terrains, defs) == [], \
            "the generator's own output must validate clean"

        # Missing line, extra line, and an undefined id each error.
        (Path(td) / "miss.txt").write_text('xAABBCC="plains"\n')
        assert vm.validate_province_terrains(cells, Path(td) / "miss.txt", defs)
        (Path(td) / "extra.txt").write_text(text + 'x445566="plains"\n')
        assert vm.validate_province_terrains(cells, Path(td) / "extra.txt", defs)
        (Path(td) / "badid.txt").write_text(
            'xAABBCC="steppe"\nx112233="plains"\nxDDEEFF="ocean"\nx445566="lakes"\n')
        assert any("not defined" in e
                   for e in vm.validate_province_terrains(cells, Path(td) / "badid.txt", defs))


def _selfcheck_canon_cities() -> None:
    """Barrier-city tooling (board #3789), in isolation — schema, the pure overlay
    builder, and the validator's on-land + impassable-collision check.

    Pins what render_canon_cities_preview.build_overlay_layer and
    validate_map._check_canon_cities rely on: the schema loads authored order and
    refuses empty/bad-terrain/dup-anchor/out-of-canvas files; the transparent
    overlay is a deterministic, source-free, exactly-canvas-sized layer; and the
    validator passes a clean on-land city, flags an on-water anchor, flags a city
    painted impassable, and runs the on-land half alone when the export is absent.
    """
    import validate_map as vm
    import render_canon_cities_preview as rcc

    # --- schema: clean load + the four refusals -------------------------------
    def _cities_json(rows):
        return json.dumps({"cities": rows})

    def _refuses(fn, msg):
        try:
            fn()
        except schema.SchemaError:
            return
        raise AssertionError(msg)

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        rows = [
            {"name": "Karak A", "anchor": [5, 5], "realm": "Karaz Ankor",
             "terrain": "mountain", "source": "canon"},
            {"name": "Karak B", "anchor": [8, 3], "realm": "Karaz Ankor",
             "terrain": "marsh", "source": "canon", "note": "n"},
        ]
        good = tdp / "canon_cities.json"
        good.write_text(_cities_json(rows))
        cities = schema.load_canon_cities(good, canvas=(10, 10))
        assert [c.name for c in cities] == ["Karak A", "Karak B"], "authored order preserved"
        assert cities[0].terrain == "mountain" and cities[1].terrain == "marsh"

        empty = tdp / "empty.json"
        empty.write_text(json.dumps({"cities": []}))
        _refuses(lambda: schema.load_canon_cities(empty, canvas=(10, 10)),
                 "an empty cities list must be refused")

        badterr = tdp / "badterr.json"
        badterr.write_text(_cities_json([{**rows[0], "terrain": "swamp"}]))
        _refuses(lambda: schema.load_canon_cities(badterr, canvas=(10, 10)),
                 "a bad terrain must be refused")

        dup = tdp / "dup.json"
        dup.write_text(_cities_json([rows[0], {**rows[1], "anchor": [5, 5]}]))
        _refuses(lambda: schema.load_canon_cities(dup, canvas=(10, 10)),
                 "a duplicate exact anchor must be refused")

        oob = tdp / "oob.json"
        oob.write_text(_cities_json([{**rows[0], "anchor": [50, 5]}]))
        _refuses(lambda: schema.load_canon_cities(oob, canvas=(10, 10)),
                 "an out-of-canvas anchor must be refused")

    # --- overlay: deterministic, source-free, transparent ground, canvas size --
    ov_cities = [
        schema.CanonCity(name="A", anchor=(5, 5), realm="r", terrain="mountain",
                         source="s", note=""),
        schema.CanonCity(name="B", anchor=(30, 20), realm="r", terrain="marsh",
                         source="s", note=""),
    ]
    o1 = np.asarray(rcc.build_overlay_layer(ov_cities, (40, 30)))
    o2 = np.asarray(rcc.build_overlay_layer(ov_cities, (40, 30)))
    assert o1.shape == (30, 40, 4), f"overlay must be canvas-sized RGBA, got {o1.shape}"
    assert np.array_equal(o1, o2), "two overlay builds must be byte-identical"
    # (29, 0) is the bottom-left corner, clear of both dots (radius 9 at (5,5) and
    # (30,20)) and their right-extending labels — proof the ground is transparent.
    assert tuple(o1[29, 0]) == (0, 0, 0, 0), "the overlay ground must be transparent where no marker"
    assert o1[..., 3].max() == 255, "each marker must be opaque somewhere"
    # The honest, cheap proof of "exactly 8192x3616" without a 474 MB allocation.
    assert (rcc.CANVAS_W, rcc.CANVAS_H) == (8192, 3616), \
        f"canvas must be 8192x3616, got {(rcc.CANVAS_W, rcc.CANVAS_H)}"

    # --- validator: on-land + impassable-collision, pass + two failures --------
    land = np.ones((10, 10), dtype=bool)
    land[:, 9] = False                       # a water column at x=9
    impass = np.zeros((10, 10, 3), dtype=np.uint8)
    impass[7, 3] = vm.IMPASSABLE_RGB         # one painted-impassable pixel

    def _city(name, xy, terrain="mountain"):
        return schema.CanonCity(name=name, anchor=xy, realm="r", terrain=terrain,
                                source="s", note="")

    err, warn = vm._check_canon_cities([_city("Clear", (2, 2))], land, impass)
    assert err == [] and warn == [], \
        f"a clean on-land, non-impassable city must produce no error/warning, got {err}/{warn}"

    err, warn = vm._check_canon_cities([_city("Wet", (9, 4))], land, impass)
    assert any("on water" in e for e in err), f"an on-water anchor must be a hard error, got {err}"

    # A hold painted impassable is a NON-BLOCKING WARNING, never an error (a hold in
    # the mountains is expected — the warning cues carving a passable pocket).
    err, warn = vm._check_canon_cities([_city("Sealed", (3, 7))], land, impass)
    assert err == [], f"a painted-impassable hold on land must not be an error, got {err}"
    assert any("painted impassable" in w for w in warn), \
        f"a city on an impassable pixel must warn, got {warn}"

    # impassable=None -> collision half skipped: the same sealed pixel now warns
    # nothing, while the on-water anchor still hard-errors.
    err, warn = vm._check_canon_cities([_city("Sealed", (3, 7))], land, None)
    assert err == [] and warn == [], f"with no export, the collision half must be skipped, got {err}/{warn}"
    err, warn = vm._check_canon_cities([_city("Wet", (9, 4))], land, None)
    assert err, "the on-land half must still run (hard error) when the export is absent"


def _selfcheck_climate() -> None:
    """Climate-zone stage (board #8202), in isolation: the pure core ``worldgen.climate`` on a small
    synthetic canvas (no committed bitmaps, no ``sources/``), the stroke reader, the per-state share
    helper and the mapping loader of ``tabulate_state_prior``.

    Physical-direction assertions (warm current warms, rain shadow dries) are deliberately absent: they
    are not monotone on a tiny canvas; equality with the accepted grid is proved by comparing
    ``generate_climate_zones.py`` output against the accepted class grid, not here.
    """
    import tempfile as _tf
    from PIL import Image as _Image
    from config import canvas_frame as _cf
    from worldgen import climate
    import generate_climate_zones as gcz
    import tabulate_state_prior as tsp

    # --- stroke reader: red warm, cyan cold, land green and sea blue are neither --------------
    with _tf.TemporaryDirectory() as td:
        a = np.zeros((8, 8, 4), np.uint8)
        a[..., :3] = (40, 160, 60)
        a[..., 3] = 255                              # flat green land
        a[0, 0] = (255, 0, 0, 255)                   # warm stroke
        a[0, 1] = (0, 255, 255, 255)                 # cold stroke
        a[1, 0] = (0, 0, 255, 255)                   # sea blue
        pth = Path(td) / "c.png"
        _Image.fromarray(a).save(pth)
        red, cya = climate.read_currents(pth)
        assert red[0, 0] == 1.0 and cya[0, 1] == 1.0, "pure red/cyan strokes must read as 1.0"
        assert red.sum() == 1.0 and cya.sum() == 1.0, "land green and sea blue must not read as strokes"

    # --- core on a synthetic canvas: range, polar land, determinism ---------------------------
    S = 32
    W, H = _cf.WIDTH // S, _cf.HEIGHT // S
    land = np.zeros((H, W), bool)
    land[40:80, 60:200] = True                       # a mid-latitude continent
    land[0:12, 100:180] = True                       # land touching the polar edge
    yy, xx = np.mgrid[0:H, 0:W]
    elev = (np.exp(-(((yy - 60) / 8.0) ** 2 + ((xx - 120) / 20.0) ** 2)) * 1800.0 * land).astype(np.float32)
    red = np.zeros((H, W), np.float32)
    cya = np.zeros((H, W), np.float32)
    red[60:70, 40:58] = 1.0
    cya[75:85, 205:215] = 1.0
    inp = dict(W=W, H=H, R=_cf.WIDTH / (2 * np.pi) / S, Y0=_cf.Y0 / S, S=S, land=land, elev=elev,
               red=red, cya=cya)
    k1 = climate.run(inp, {"pole_ice": 7.0})["k"]
    k2 = climate.run(inp, {"pole_ice": 7.0})["k"]
    assert k1.shape == (H, W) and k1.dtype == np.uint8, "class grid must be uint8 (H, W)"
    assert np.array_equal(k1, k2), "two runs on the same inputs must be array-equal"
    assert int(k1.max()) < len(climate.CLASSES), "class ids must index CLASSES"
    polar = k1[0:6, 110:170]
    assert np.isin(polar, [climate.IDX["ET"], climate.IDX["EF"]]).all(), \
        "land at the polar edge must come out tundra or ice cap"
    assert "cur_sig" in climate.DEFAULT and "pole_ice" in climate.DEFAULT

    # --- per-state share helper: shares sum to 1, ties to the lowest id, empty -> no dominant --
    codes = [c[0] for c in climate.CLASSES]
    row = np.zeros(len(codes), np.int64)
    row[3], row[8], row[12] = 5, 5, 2
    tot, dom, shares = gcz.zone_shares(row, codes)
    assert tot == 12 and dom == codes[3], "tie must go to the lowest class id"
    assert abs(sum(shares.values()) - 1.0) < 1e-3 and set(shares) == {codes[3], codes[8], codes[12]}
    assert gcz.zone_shares(np.zeros(len(codes), np.int64), codes) == (0, None, {})

    # --- mapping loader + the tabulator columns -----------------------------------------------
    def _row(key, cls, hl):
        return {"state_key": key, "climate_class": cls, "phys_highland": hl, "clim_dominant": "",
                "clim_share": "", "clim_expected": "", "clim_disagree": ""}

    with _tf.TemporaryDirectory() as td:
        root = Path(td)
        (root / "mapgen" / "derived").mkdir(parents=True)
        (root / "mapgen" / "config").mkdir(parents=True)
        assert tsp.load_climate(root) is None, "absent inputs must skip cleanly"
        idx = {"states": [
            {"state_key": "STATE_A", "dominant": "Cs", "shares": {"Cs": 0.75, "BSk": 0.25}},
            {"state_key": "STATE_B", "dominant": None, "shares": {}},
        ]}
        (root / "mapgen" / "derived" / "state_climate_index.json").write_text(json.dumps(idx), encoding="utf-8")
        mp = root / "mapgen" / "config" / "climate_zone_class_map.json"
        mp.write_text(json.dumps({"zones": {"Cs": {"classes": ["mediterranean"], "why": "x"}}}), encoding="utf-8")
        by_key, expect = tsp.load_climate(root)
        rows = [_row("STATE_A", "steppe", 0), _row("STATE_B", "steppe", 0),
                _row("STATE_A", "mediterranean", 0), _row("STATE_A", "steppe", 1)]
        tsp.apply_climate(rows, by_key, expect)
        assert rows[0]["clim_dominant"] == "Cs" and rows[0]["clim_share"] == "0.7500"
        assert rows[0]["clim_disagree"] == 1 and rows[2]["clim_disagree"] == 0
        assert rows[3]["clim_disagree"] == 0, "a highland state is never flagged"
        assert rows[1]["clim_dominant"] == "" and rows[1]["clim_disagree"] == "", "no dominant -> blank"
        mp.write_text(json.dumps({"zones": {"Cs": {"classes": ["no_such_class"], "why": "x"}}}), encoding="utf-8")
        try:
            tsp.load_climate(root)
        except SystemExit:
            pass
        else:
            raise AssertionError("an unknown class id in the mapping must be refused")


def _selfcheck_cr_partition() -> None:
    """CR partition proposal (board #8210), in isolation: ``worldgen.cr_partition`` on synthetic
    rasters, independent of ``sources/``. Decode (asymmetric, so a row flip fails), dot-free
    placement (known scale and offset recovered; landmarks exact, far field the affine), the
    fill over a differing coast, snap (crossing is snapped, a feature ending mid-band is not),
    a scope cut sealed by closing lines and proved through the generator's own region stage, a
    box across the seam, and determinism. Board #8211 adds the mainland path: cut rasterising,
    the cut-closed scope with an island list and frame rows, landmark placement, leave-one-out,
    coast agreement and high-ground edges.
    """
    import struct as _st
    from scipy import ndimage as _ndi
    from worldgen import cells as _cells, cr_partition as crp, land_provinces as _lp

    # --- decode: 4x3, palette of 5 with black at 2, descriptor 0x10, header colour-map start 18 --
    h, w = 3, 4
    want = np.array([[0, 1, 2, 3], [4, 0, 0, 1], [2, 2, 3, 4]], dtype="<u2")
    pal = [(10, 20, 30), (200, 0, 0), (0, 0, 0), (0, 200, 0), (0, 0, 200)]
    blob = _st.pack("<BBBHHBHHHHBB", 0, 1, 1, 18, len(pal), 32, 0, 0, w, h, 16, 0x10)
    blob += b"".join(bytes([b, g, r, 255]) for r, g, b in pal) + want.tobytes()
    idx, palette = crp.decode_lookup(blob)
    assert np.array_equal(idx, want), "rows must stay as stored (top-down), not flipped"
    assert palette.tolist() == [list(c) for c in pal] and crp.void_index(palette) == 2
    for bad in (blob[:-1], blob + b"\0"):
        try:
            crp.decode_lookup(bad)
        except crp.PartitionError:
            pass
        else:
            raise AssertionError("a lookup of the wrong length must be refused")
    big = np.zeros((1941, 3200), np.uint16)
    big[0, 0], big[0, 1100], big[-1, -1] = 5, 1, 7           # void is 1 here
    lab = crp.to_parchment_frame(big, 1, (0, 0, 6400, 4480))
    assert lab.shape == (4480, 6400) and lab[0, 0] == 6 and lab[0, 2200] == 0 and lab[-1, -1] == 8
    assert lab[1, 1] == 6 and lab[2, 2] == 1 and lab[0, 3] == 1, "per-axis nearest upsample (2.0, 2.308)"

    # --- placement: a known blob, recovered without landmarks, then with four ---------------------
    yy, xx = np.mgrid[0:240, 0:240]
    src = ((((xx - 120) / 70.0) ** 2 + ((yy - 110) / 45.0) ** 2) < 1) | \
          ((((xx - 170) / 18.0) ** 2 + ((yy - 70) / 26.0) ** 2) < 1)
    H, W = 360, 380
    cy, cx = np.mgrid[0:H, 0:W]
    ux, uy = (cx - 40) / 1.3, (cy - 25) / 1.1
    canvas = np.zeros((H, W), bool)
    ok = (ux >= 0) & (ux < 240) & (uy >= 0) & (uy < 240)
    canvas[ok] = src[uy[ok].astype(int), ux[ok].astype(int)]
    sp, cp_, info = crp.fit_placement(src, canvas, [])
    probe = np.array([[120.0, 110.0], [90.0, 130.0], [170.0, 70.0]])
    got = crp.forward_map(sp, cp_, probe)
    truth = np.column_stack([probe[:, 0] * 1.3 + 40, probe[:, 1] * 1.1 + 25])
    assert np.abs(got - truth).max() < 2.5, f"placement missed the known affine: {got} vs {truth}"
    assert info["folded_fraction"] == 0.0 and info["coarse_iou"] > 0.9
    lms = [crp.Landmark(f"l{i}", (a, b), (a * 1.3 + 40 + 6.0, b * 1.1 + 25 - 4.0))
           for i, (a, b) in enumerate([(100.0, 110.0), (140.0, 110.0), (120.0, 90.0), (120.0, 130.0)])]
    sp2, cp2, info2 = crp.fit_placement(src, canvas, lms, {"influence_px": 60.0})
    at = crp.forward_map(sp2, cp2, np.array([lm.source for lm in lms]))
    assert np.abs(at - np.array([lm.canvas for lm in lms])).max() < 0.01, "exact at every landmark"
    far = crp.forward_map(sp2, cp2, np.array([[10.0, 230.0]]))
    far0 = crp.forward_map(sp, cp_, np.array([[10.0, 230.0]]))
    assert np.abs(far - far0).max() < 1.0, "far from a landmark the placement is the affine"
    sp3, cp3, _ = crp.fit_placement(src, canvas, lms, {"influence_px": 60.0})
    assert np.array_equal(cp2, cp3) and np.array_equal(sp2, sp3), "placement must be deterministic"

    # --- fill over a differing coast: every scope pixel carries a label ---------------------------
    scope = np.zeros((40, 60), bool)
    scope[5:35, 5:55] = True
    guide = np.zeros((40, 60), np.int32)
    guide[5:35, 5:28] = 3
    guide[5:35, 31:50] = 7                      # a gap, and CR stops short of our coast on the right
    filled = _cells.fill_nearest(np.where(scope, guide, 0), scope, wrap_x=False, pad=0)
    assert (filled[scope] > 0).all() and set(np.unique(filled[scope])) == {3, 7}

    # --- snap: a river that crosses the band is followed; one that ends mid-band is not -----------
    lab2 = np.zeros((40, 70), np.int32)
    lab2[:, :30] = 1
    lab2[:, 30:] = 2
    sc2 = np.ones(lab2.shape, bool)
    river = np.zeros(lab2.shape, bool)
    river[:, 34] = True
    out, rep = crp.snap_to_features(lab2, sc2, river, snap_px=8, follow_frac=0.6)
    assert rep["snapped"] and np.array_equal(np.unique(out), [1, 2])
    col = [int(np.flatnonzero(out[r] == 2)[0]) for r in range(0, 40, 5)]
    assert all(33 <= c <= 35 for c in col), f"border should sit on the river, got {col}"
    half = np.zeros(lab2.shape, bool)
    half[:20, 34] = True
    out2, rep2 = crp.snap_to_features(lab2, sc2, half, snap_px=8, follow_frac=0.3)
    assert rep2["not_splitting"] and np.array_equal(out2, lab2), \
        "a feature that ends mid-band must not move a border"

    # --- a scope cut sealed by closing lines, proved through the generator's region stage -----------
    land = np.ones((120, 120), bool)
    scope3 = np.zeros(land.shape, bool)
    scope3[30:90, 30:90] = True
    lab3 = np.zeros(land.shape, np.int32)
    lab3[30:90, 30:60] = 1
    lab3[30:90, 60:90] = 2
    lines = crp.lines_from_labels(lab3, scope3)
    closing = crp.closing_line(scope3, land & ~scope3)
    drawn = np.zeros(land.shape + (3,), np.uint8)
    drawn[lines | closing] = (255, 0, 255)
    reg = _lp.regions(land, drawn, 2, 150, False)
    from scipy import ndimage as _ndi
    off = _ndi.distance_transform_edt(~scope3)
    inner = [int(v) for v in np.unique(reg[scope3]) if ((reg == v) & scope3).sum() * 2 > (reg == v).sum()]
    assert len(inner) == 2, "the two proposed states must come out as two regions"
    for r in inner:
        assert not ((reg == r) & (off > 3)).any(), "a proposed state must not be open to outside land"
    drawn_open = np.zeros(land.shape + (3,), np.uint8)
    drawn_open[lines] = (255, 0, 255)
    unsealed = _lp.regions(land, drawn_open, 2, 150, False)
    leaked = [int(v) for v in np.unique(unsealed[scope3])
              if ((unsealed == v) & (off > 3)).any()]
    assert leaked, "without the closing line a state is open to the outside land"

    # --- a box across the seam comes back contiguous -------------------------------------------------
    a = np.arange(10 * 20).reshape(10, 20)
    got = crp.crop_box(a, (15, 2, 25, 8), wrap=True)
    assert np.array_equal(got, np.concatenate([a[2:8, 15:], a[2:8, :5]], axis=1))

    # --- provenance: shares add up --------------------------------------------------------------------
    fin = np.zeros((20, 20), np.int32)
    fin[2:18, 2:18] = 1
    smp = np.zeros_like(fin)
    smp[2:18, 2:10] = 5
    smp[2:18, 10:18] = 9
    pr = crp.provenance(fin, smp)
    assert pr[1]["area_px"] == 256 and abs(sum(pr[1]["cr_shares"].values()) - 1.0) < 1e-3

    # --- mainland support (board #8211) -------------------------------------------------------------
    # rasterize_cuts: an 8-connected diagonal cut blocks a 4-connected flood across it.
    cutp = crp.rasterize_cuts((30, 30), [[(0, 0), (29, 29)]])
    assert cutp.sum() == 30 and all(cutp[i, i] for i in range(30))
    flood, nf = _ndi.label(~cutp)                       # 4-connected by default
    assert nf == 2 and flood[0, 29] != flood[29, 0], "a diagonal cut must separate the two sides"
    seam = crp.rasterize_cuts((10, 20), [[(5, 2), (15, 2)]], origin=(10, 0), wrap_w=20)
    assert seam.sum() == 11 and seam[2, 5:16].all(), "x left of the origin unwraps across the seam"

    # cut_scope: a land strip the cut closes; the seed side and a listed island come in, an
    # unlisted island and the far side do not.
    free = np.zeros((40, 60), bool)
    free[5:35, 5:35] = True                              # the seed's land
    free[5:35, 35:55] = True                             # land beyond the cut
    cut = np.zeros_like(free)
    cut[5:35, 35] = True                                 # the cut column
    free[2:4, 20:24] = True                              # an island, listed
    free[36:38, 10:12] = True                            # an island, not listed
    bmask = np.ones_like(free)
    bmask[:, 58:] = False                                # box ends at col 58
    sc, inf = crp.cut_scope(free, cut, (10, 10), [(21, 2)], bmask)
    assert sc[10, 10] and sc[3, 21] and not sc[36, 10] and not sc[10, 45]
    assert sc[10, 35], "a cut pixel next to scope joins scope so closing_line marks it"
    assert inf["island_px"] == [8]
    # land on a non-frame box edge: the cut is missing and the call raises, naming the edge
    for kw, what in (({}, "missing cut"),):
        try:
            crp.cut_scope(free, np.zeros_like(cut), (10, 10), [], np.pad(np.ones((40, 54), bool),
                                                                        ((0, 0), (0, 6)))[:, :60])
        except crp.PartitionError as exc:
            assert "cut is missing" in str(exc), exc
        else:
            raise AssertionError("a scope that runs onto the box edge must raise")
    # ... but the same land on a frame row is the end of the map, not a cut
    land_f = np.zeros((20, 30), bool)
    land_f[0:12, 5:25] = True                            # touches row 0 only
    bm_f = np.zeros_like(land_f)
    bm_f[0:15, 3:27] = True
    crp.cut_scope(land_f, np.zeros_like(land_f), (10, 5), [], bm_f, frame_rows=[0])
    try:
        crp.cut_scope(land_f, np.zeros_like(land_f), (10, 5), [], bm_f)
    except crp.PartitionError:
        pass
    else:
        raise AssertionError("without frame_rows the top row is a box edge")
    # an island point in the seed's own land is refused
    try:
        crp.cut_scope(free, cut, (10, 10), [(12, 12)], bmask)
    except crp.PartitionError as exc:
        assert "seed" in str(exc)
    else:
        raise AssertionError("an island inside the seed's land must raise")

    # fit_from_landmarks: exact on 5 points of a known per-axis affine; refuses 3
    pts = [(10.0, 20.0), (200.0, 40.0), (120.0, 180.0), (30.0, 150.0), (170.0, 90.0)]
    lm5 = [crp.Landmark(f"p{i}", (a, b), (a * 1.7 + 33.0, b * 0.9 - 12.0)) for i, (a, b) in enumerate(pts)]
    sc_, of_ = crp.fit_from_landmarks(lm5)
    assert abs(sc_[0] - 1.7) < 1e-9 and abs(sc_[1] - 0.9) < 1e-9
    assert abs(of_[0] - 33.0) < 1e-9 and abs(of_[1] + 12.0) < 1e-9
    try:
        crp.fit_from_landmarks(lm5[:3])
    except crp.PartitionError:
        pass
    else:
        raise AssertionError("landmark placement must refuse fewer than 4 landmarks")
    # landmark mode places the blob without the silhouette sweeps
    sp4, cp4, info4 = crp.fit_placement(src, canvas, lms, {"influence_px": 60.0}, mode="landmarks")
    assert info4["mode"] == "landmarks" and info4["coarse_iou"] > 0.8

    # landmark_loo: 0 for points on one affine; the inconsistent one is flagged
    loo0 = crp.landmark_loo(lm5, {"influence_px": 0.0})
    assert loo0["affine"]["max"] < 1e-6
    off_lm = list(lm5)
    off_lm[2] = crp.Landmark("bad", lm5[2].source, (lm5[2].canvas[0] + 40.0, lm5[2].canvas[1] - 30.0))
    loo1 = crp.landmark_loo(off_lm, {"influence_px": 0.0})
    worst = max(loo1["per_landmark"], key=lambda r: r["affine_px"])
    assert worst["name"] == "bad" and worst["affine_px"] > 10.0

    # coast_agreement: 0 on identical masks, about k on a k-px shift, frame rows ignored
    base = np.zeros((60, 80), bool)
    base[0:40, 20:60] = True                             # touches the top row: a frame row
    region = np.ones_like(base)
    ca0 = crp.coast_agreement(base, base, region)
    assert ca0["median"] == 0.0 and ca0["n"] > 0
    shifted = np.roll(base, 5, axis=1)
    ca5 = crp.coast_agreement(shifted, base, region)
    assert 4.0 <= ca5["median"] <= 6.0, ca5
    only_top = np.zeros_like(base)
    only_top[0:3, 10:70] = True                          # coast only along the frame row + its ends
    assert crp.coast_agreement(only_top, only_top, region)["median"] == 0.0

    # high_ground_edges: outlines a plateau, ignores a sub-500 px bump
    elev = np.zeros((120, 160), np.float32)
    elev[20:80, 20:100] = 3000.0                         # 4,800 px plateau
    elev[100:110, 120:130] = 3000.0                      # 100 px bump
    edge = crp.high_ground_edges(elev, np.ones_like(elev, bool), 2000.0)
    assert edge[20, 50] and edge[79, 50] and not edge[50, 50] and not edge[100:110, 120:130].any()

    # split_large_terrain: one 60x120 cell split in two settles on a river column 20 px off the
    # straight-line midpoint, where cells.split_large would cut through the middle
    cell = np.ones((60, 120), np.int32)
    river_c = np.zeros(cell.shape, bool)
    river_c[:, 40] = True
    cost_t = crp.terrain_cost(np.zeros(cell.shape, np.float32), river_c, cell > 0)
    out_t = crp.split_large_terrain(cell, cost_t, 5000, 3600)
    assert len(np.unique(out_t)) == 2
    edge_col = [int(np.flatnonzero(out_t[r, 1:] != out_t[r, :-1])[0]) for r in (5, 30, 55)]
    assert all(38 <= c <= 42 for c in edge_col), f"split must settle on the river, got {edge_col}"
    out_t2 = crp.split_large_terrain(cell, cost_t, 5000, 3600)
    assert np.array_equal(out_t, out_t2), "terrain split must be deterministic"

    # a cut-closed mainland round-trips through the generator's region stage with nothing open
    land4 = np.ones((100, 140), bool)
    scope4 = np.zeros(land4.shape, bool)
    scope4[20:80, 20:70] = True
    cut4 = crp.rasterize_cuts(land4.shape, [[(19, 19), (19, 80)], [(70, 19), (70, 80)],
                                            [(19, 19), (70, 19)], [(19, 80), (70, 80)]])
    sc4, _ = crp.cut_scope(land4, cut4, (40, 40), [], np.ones_like(land4), frame_rows=[])
    assert sc4[40, 40] and not sc4[5, 5], "cuts enclosing a seed close its scope"
    lab4 = np.zeros(land4.shape, np.int32)
    lab4[20:80, 20:45] = 1
    lab4[20:80, 45:70] = 2
    lines4 = crp.lines_from_labels(lab4, sc4) | cut4
    drawn4 = np.zeros(land4.shape + (3,), np.uint8)
    drawn4[lines4] = (255, 0, 255)
    reg4 = _lp.regions(land4, drawn4, 2, 150, False)
    inner4 = [int(v) for v in np.unique(reg4[40:60, 25:65]) if v > 0]
    assert len(inner4) == 2
    off4 = _ndi.distance_transform_edt(~sc4)
    for r in inner4:
        assert not ((reg4 == r) & (off4 > 3)).any(), "a cut-closed state must not be open"


def _selfcheck_arable() -> None:
    """Arable-potential field (board #4921), in isolation — the pure core
    ``worldgen.arable`` and ``schema.load_arable_lore``, on a small synthetic
    canvas with NO dependency on the real committed bitmaps (mirrors
    ``_selfcheck_lakes`` / ``_selfcheck_river_extraction``).

    Covers: water/lake/impassable = 0; climate monotonicity (temperate peak, arid
    trough, pole taper); terrain suppression; hydrology boost (river + coast);
    lore lift/suppress with a smooth monotone falloff and multiplicative
    composition; percentile normalization (max<=1, real spread, an outlier does not
    flatten the rest); the schema loader (order + every refusal); and determinism
    (build_field array-equal + the encoded PNG byte-identical across runs).
    """
    from worldgen import arable, schema, raster as _raster
    import generate_arable_heatmap as gah

    p = arable.ArableParams()

    # --- climate curve shape (pure function of latitude) ---------------------
    lat = np.array([70.0, 50.0, 35.0, 23.0, 10.0, 0.0])
    c = arable.climate_curve(lat, p)
    assert c[1] == c.max(), "climate must peak in the temperate band (~50 deg)"
    assert c[3] < c[2], "subtropical-arid trough: 23 deg below 35 deg"
    assert c[0] < c[1] and c[0] < 0.2, "hard polar taper toward the pole edge"
    assert c[5] < c[1], "falls toward the equator relative to the temperate peak"

    def _flat_canvas(h, w, top_lat, bot_lat):
        lp = np.linspace(top_lat, bot_lat, h)
        elev = np.zeros((h, w), np.float32)
        sea = np.zeros((h, w), bool)
        passable = np.ones((h, w), bool)
        river = np.zeros((h, w), bool)
        return lp, elev, sea, passable, river

    # --- water / lake / impassable -> 0 --------------------------------------
    lp, elev, sea, passable, river = _flat_canvas(40, 30, 60.0, 40.0)
    sea[:, 0:3] = True          # ocean column
    lake = np.zeros((40, 30), bool); lake[20, 15] = True
    impass = np.zeros((40, 30), bool); impass[10, 20] = True
    passable = (~sea) & (~lake) & (~impass)
    field, stats = arable.build_field(
        lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
        river=river, river_width=None, lore_zones=[], params=p, wrap_x=False)
    assert (field[sea] == 0).all(), "sea reads exactly 0"
    assert field[20, 15] == 0, "lake reads exactly 0"
    assert field[10, 20] == 0, "impassable reads exactly 0"
    assert (field[passable] > 0).any(), "passable land is non-zero where factors are positive"
    assert field.max() <= 1.0 + 1e-6, "normalized field never exceeds 1"

    # --- climate monotonicity on flat, river-free, fixed-coast land ----------
    # Sea is a full left column, so d_coast is constant across rows for a fixed
    # column: comparing rows at one column isolates C(lat).
    lp, elev, sea, passable, river = _flat_canvas(60, 20, 74.0, 5.0)
    sea[:, 0] = True
    passable = ~sea
    # Moisture off here so the column truly isolates C(lat) (moisture varies by the
    # per-row wind belt, which would otherwise confound a single-column compare).
    field, _ = arable.build_field(
        lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
        river=river, river_width=None, lore_zones=[],
        params=arable.ArableParams(moist_enable=False), wrap_x=False)
    col = 12
    def _row_at(target):
        return int(np.abs(lp - target).argmin())
    r_temp, r_arid, r_pole = _row_at(50.0), _row_at(23.0), _row_at(73.0)
    assert field[r_temp, col] > field[r_arid, col], "temperate > subtropical-arid"
    assert field[r_temp, col] > field[r_pole, col], "temperate > polar edge"

    # --- terrain suppression: a mountain block reads below adjacent lowland ---
    # No sea (coast term off) so the only difference is elevation/slope. Use a
    # small smoothing sigma here so the synthetic block's plateau stays high (on
    # the real 8192px canvas a mountain is hundreds of px wide, so the default
    # sigma is tiny relative to it — the render confirms real spines read barren).
    p_terr = arable.ArableParams(elev_smooth_sigma=1.0)
    lp = np.full(20, 50.0); elev = np.zeros((20, 20), np.float32)
    elev[:, 10:14] = 3000.0     # a highland block (metres)
    sea = np.zeros((20, 20), bool); passable = np.ones((20, 20), bool)
    river = np.zeros((20, 20), bool)
    field, _ = arable.build_field(
        lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
        river=river, river_width=None, lore_zones=[], params=p_terr, wrap_x=False)
    assert field[10, 11] < field[10, 2], "highland block reads below same-latitude lowland"

    # --- hydrology: river-adjacent + coast-adjacent read above interior ------
    lp = np.full(12, 50.0); elev = np.zeros((12, 40), np.float32)
    sea = np.zeros((12, 40), bool); river = np.zeros((12, 40), bool)
    river[6, 20] = True
    passable = np.ones((12, 40), bool)
    rw = np.zeros((12, 40), np.float32); rw[6, 20] = 8.0
    field, _ = arable.build_field(
        lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
        river=river, river_width=rw, lore_zones=[], params=p, wrap_x=False)
    assert field[6, 21] > field[6, 34], "river-adjacent land reads above the dry interior"

    lp = np.full(12, 50.0); elev = np.zeros((12, 40), np.float32)
    sea = np.zeros((12, 40), bool); sea[:, 0] = True
    river = np.zeros((12, 40), bool); passable = ~sea
    field, _ = arable.build_field(
        lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
        river=river, river_width=None, lore_zones=[], params=p, wrap_x=False)
    assert field[6, 1] > field[6, 34], "coast-adjacent land reads above the dry interior"

    # --- moisture / rain shadow (prevailing-wind advection) ------------------
    # Belt direction: |lat| in [30,60) sources moisture from the WEST, else east.
    assert list(arable._zonal_upwind_from_west(np.array([70.0, 45.0, 20.0]))) \
        == [False, True, False], "westerlies source from the west; trades/polar from the east"

    # Continentality: on flat land in the westerlies with a western ocean and the
    # coast boost OFF, a near-coast column reads above the deep interior purely from
    # the moisture fetch decay.
    # Smoothing off in these sub-tests: it is a cosmetic de-streak pass over the
    # scan output; the physics under test lives in the per-row scan itself.
    p_moist = arable.ArableParams(coast_amp=0.0, moist_lambda=30.0, moist_smooth_sigma=0.0)
    lp = np.full(8, 45.0); elev = np.zeros((8, 120), np.float32)
    sea = np.zeros((8, 120), bool); sea[:, 0] = True
    river = np.zeros((8, 120), bool); passable = ~sea
    field, _ = arable.build_field(
        lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
        river=river, river_width=None, lore_zones=[], params=p_moist, wrap_x=False)
    assert field[4, 5] > field[4, 110], "continentality: near-coast reads above the deep interior"

    # Rain shadow: a tall N-S ridge between the western ocean and the lee drives the
    # lee far below the windward flank at the same latitude and (flat) elevation.
    # A gentle fetch decay keeps the near-coast windward point wet, so the collapse
    # in the lee is the orographic loss of crossing the ridge, not extra distance
    # (~15px of gentle decay alone would leave the lee ~0.9x the windward).
    # gamma=1 so the compared ratio is the physical moisture drop, not the tone curve.
    p_rs = arable.ArableParams(coast_amp=0.0, moist_lambda=200.0, elev_smooth_sigma=1.0,
                               gamma=1.0, moist_smooth_sigma=0.0)
    elev = np.zeros((8, 120), np.float32); elev[:, 20:24] = 4000.0
    field, _ = arable.build_field(
        lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
        river=river, river_width=None, lore_zones=[], params=p_rs, wrap_x=False)
    assert field[4, 30] < 0.3 * field[4, 15], "rain shadow: the lee of a ridge reads far below its windward flank"

    # Direction isolates cleanly on the factor itself: land with ocean only to the
    # EAST is watered under trades (source east) but dry under westerlies (source
    # west, no western ocean).
    seaE = np.zeros((8, 60), bool); seaE[:, -1] = True
    flat = np.zeros((8, 60), np.float32)
    mf_trades = arable._moisture_factor(seaE, flat, np.full(8, 20.0), p_moist, wrap_x=False)
    mf_west = arable._moisture_factor(seaE, flat, np.full(8, 45.0), p_moist, wrap_x=False)
    assert mf_trades[4, 58] > mf_west[4, 58], "trades water an eastern coast the westerlies leave dry"

    # Disable identity: moist_enable=False is an all-ones factor and changes the field.
    mf_off = arable._moisture_factor(seaE, flat, np.full(8, 45.0),
                                     arable.ArableParams(moist_enable=False), wrap_x=False)
    assert np.array_equal(mf_off, np.ones_like(mf_off)), "moist_enable=False is the identity factor"
    lp2 = np.full(8, 45.0); elev2 = np.zeros((8, 120), np.float32)
    sea2 = np.zeros((8, 120), bool); sea2[:, 0] = True; pass2 = ~sea2
    riv2 = np.zeros((8, 120), bool)
    f_on, _ = arable.build_field(lat_per_row=lp2, elev_m=elev2, sea=sea2, passable=pass2,
                                 river=riv2, river_width=None, lore_zones=[],
                                 params=arable.ArableParams(coast_amp=0.0), wrap_x=False)
    f_off, _ = arable.build_field(lat_per_row=lp2, elev_m=elev2, sea=sea2, passable=pass2,
                                  river=riv2, river_width=None, lore_zones=[],
                                  params=arable.ArableParams(coast_amp=0.0, moist_enable=False),
                                  wrap_x=False)
    assert not np.array_equal(f_on, f_off), "the moisture factor changes the composed field"

    # De-streak: the per-row scan trails downwind streaks where elevation differs
    # row to row; the smoothing pass reduces that row-to-row variance downwind.
    seaW = np.zeros((20, 60), bool); seaW[:, 0] = True
    elev_streak = np.zeros((20, 60), np.float32)
    elev_streak[::2, 10:14] = 800.0     # a broken ridge present on even rows only
    latw = np.full(20, 45.0)
    mf_raw = arable._moisture_factor(seaW, elev_streak, latw,
                                     arable.ArableParams(moist_smooth_sigma=0.0), wrap_x=False)
    mf_sm = arable._moisture_factor(seaW, elev_streak, latw,
                                    arable.ArableParams(moist_smooth_sigma=6.0), wrap_x=False)
    assert float(mf_sm[:, 30].std()) < float(mf_raw[:, 30].std()), \
        "smoothing reduces the downwind per-row streak variance"

    # --- lore: lift/suppress, smooth monotone falloff, multiplicative -------
    Z = schema.ArableLoreZone
    bread = Z(anchor=(20, 6), radius=10.0, factor=1.8, kind="breadbasket",
              name="B", note="")
    blight = Z(anchor=(20, 6), radius=10.0, factor=0.4, kind="blight", name="Y", note="")
    L1 = arable._lore_factor([bread], (12, 40), wrap_x=False)
    assert abs(L1[6, 20] - 1.8) < 1e-4, "breadbasket multiplier at the anchor == factor"
    assert abs(L1[6, 31] - 1.0) < 1e-4, "lore returns to 1.0 at/after the radius"
    # monotone falloff between anchor and radius
    d = [L1[6, 20 + k] for k in range(0, 11)]
    assert all(d[i] >= d[i + 1] - 1e-6 for i in range(len(d) - 1)), "smooth monotone falloff"
    Lb = arable._lore_factor([blight], (12, 40), wrap_x=False)
    assert Lb[6, 20] < 1.0, "blight suppresses at the anchor"
    Lboth = arable._lore_factor([bread, blight], (12, 40), wrap_x=False)
    assert abs(Lboth[6, 20] - 1.8 * 0.4) < 1e-4, "overlapping zones compose multiplicatively"

    # --- normalization: real spread + an outlier does not flatten the rest ---
    lp = np.linspace(60.0, 40.0, 40); elev = np.zeros((40, 40), np.float32)
    sea = np.zeros((40, 40), bool); river = np.zeros((40, 40), bool)
    passable = np.ones((40, 40), bool)
    base, _ = arable.build_field(
        lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
        river=river, river_width=None, lore_zones=[], params=p, wrap_x=False)
    assert base.max() > base[base > 0].min(), "field spans a real range, not all-equal"
    # A single-pixel extreme zone (well under the P99.5 tail) must be clipped
    # without dragging the normalization denominator up and flattening the rest.
    outlier = Z(anchor=(20, 20), radius=1.0, factor=50.0, kind="breadbasket", name="O", note="")
    withz, _ = arable.build_field(
        lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
        river=river, river_width=None, lore_zones=[outlier], params=p, wrap_x=False)
    assert withz.max() <= 1.0 + 1e-6, "an extreme outlier is clipped, not overflowing"
    assert abs(float(np.median(withz)) - float(np.median(base))) < 0.15, \
        "percentile normalization keeps the bulk spread despite one extreme zone"

    # --- schema loader: order kept + every refusal ---------------------------
    with tempfile.TemporaryDirectory() as td:
        def _write(obj):
            pth = Path(td) / "lore.json"
            pth.write_text(json.dumps(obj), encoding="utf-8")
            return pth
        good = {"zones": [
            {"anchor": [5, 5], "radius": 4, "factor": 1.5, "kind": "breadbasket", "name": "A"},
            {"anchor": [8, 8], "radius": 4, "factor": 0.5, "kind": "blight", "name": "B"},
        ]}
        zs = schema.load_arable_lore(_write(good), canvas=(20, 20))
        assert [z.name for z in zs] == ["A", "B"], "authored order preserved"
        for bad, why in [
            ({"zones": []}, "empty list"),
            ({"zones": [{"anchor": [99, 1], "radius": 4, "factor": 1.5,
                         "kind": "breadbasket", "name": "X"}]}, "out-of-canvas anchor"),
            ({"zones": [{"anchor": [1, 1], "radius": 0, "factor": 1.5,
                         "kind": "breadbasket", "name": "X"}]}, "non-positive radius"),
            ({"zones": [{"anchor": [1, 1], "radius": 4, "factor": 0.8,
                         "kind": "breadbasket", "name": "X"}]}, "breadbasket factor<=1"),
            ({"zones": [{"anchor": [1, 1], "radius": 4, "factor": 1.2,
                         "kind": "blight", "name": "X"}]}, "blight factor>=1"),
            ({"zones": [{"anchor": [2, 2], "radius": 4, "factor": 1.5, "kind": "breadbasket", "name": "X"},
                        {"anchor": [2, 2], "radius": 4, "factor": 1.5, "kind": "breadbasket", "name": "Y"}]},
             "duplicate anchor"),
        ]:
            try:
                schema.load_arable_lore(_write(bad), canvas=(20, 20))
            except schema.SchemaError:
                pass
            else:  # pragma: no cover
                raise AssertionError(f"load_arable_lore must reject: {why}")

    # --- determinism: array-equal core + byte-identical encoded PNG ----------
    lp = np.linspace(60.0, 40.0, 24); elev = np.zeros((24, 24), np.float32)
    sea = np.zeros((24, 24), bool); sea[:, 0] = True
    river = np.zeros((24, 24), bool); river[12, 12] = True
    passable = ~sea
    rw = np.zeros((24, 24), np.float32); rw[12, 12] = 6.0
    kw = dict(lat_per_row=lp, elev_m=elev, sea=sea, passable=passable,
              river=river, river_width=rw, lore_zones=[bread], params=p, wrap_x=True)
    f1, _ = arable.build_field(**kw)
    f2, _ = arable.build_field(**kw)
    assert np.array_equal(f1, f2), "two build_field runs must be array-identical"
    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "a.png"; b = Path(td) / "b.png"
        _raster.write_gray16_png(a, gah.encode16(f1))
        _raster.write_gray16_png(b, gah.encode16(f2))
        assert a.read_bytes() == b.read_bytes(), "the encoded 16-bit PNG must be byte-identical"


def _selfcheck_tww3_names() -> None:
    """TWW3 canon-name lookup (board #4363), in isolation — the TSV parser and
    the exact-hex point sample, on a synthetic table + array.

    Deliberately **independent of the real source**: the region table and the
    lookup bitmap live under the gitignored
    ``sources/cr_oldworld_campaign/``, which is absent on every device but
    Chris's, so a self-check that needed them would simply never run. The
    synthetic table reproduces the real file's exact shape — the header, the
    ``#regions_tables`` metadata row, black water rows, a blank row — and the
    sampling is checked against a tiny hand-built array.
    """
    import tww3_name_lookup as tnl
    from worldgen import tww3_names as tn

    header = "\t".join(tn.EXPECTED_HEADER)

    def _tsv(rows: list[tuple[str, str]], *, header_line: str = header,
             extra: list[str] | None = None) -> str:
        lines = [header_line, "#regions_tables;0;db/regions_tables/cr_oldworld_campaign\t\t\t\t\t"]
        for key, colour in rows:
            lines.append(f"{key}\t\temp\tfalse\t\t{colour}")
        lines.extend(extra or [])
        return "\n".join(lines) + "\n"

    def _refuses(fn, msg):
        try:
            fn()
        except tn.TWW3NamesError:
            return
        raise AssertionError(msg)

    # A table just over the truncation floor: the first three are the ones the
    # assertions below name, the filler keeps the row count legal.
    base = [("cr_oldworld_region_altdorf", "112233"),
            ("cr_oldworld_region_karak_kadrin", "445566"),
            ("cr_oldworld_region_sea_of_claws", tn.WATER_HEX)]
    filler = [(f"cr_oldworld_region_filler_{i:04d}", f"{0x200000 + i:06X}")
              for i in range(tn.MIN_DATA_ROWS)]
    rows = base + filler

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)

        good = tdp / "good.tsv"
        # A blank row between the data rows must be skipped, not counted or refused.
        good.write_text(_tsv(rows, extra=[""]), encoding="utf-8")
        regions = tn.load_tww3_regions(good)
        assert len(regions) == len(rows), \
            f"metadata + blank rows must be skipped and every data row kept, got {len(regions)}"
        assert regions[0].key == "cr_oldworld_region_altdorf", "file order must be preserved"
        assert regions[0].slug == "altdorf", f"the key prefix must be stripped, got {regions[0].slug!r}"
        assert regions[0].hex == "112233"
        assert regions[2].is_water and not regions[0].is_water, \
            "only the 000000 row is water"

        index = tn.colour_index(regions)
        assert len(index) == len(rows) - 1, "the colour index must exclude every black row"
        assert tn.WATER_HEX not in index, "black must never be an index key"
        assert index["445566"].slug == "karak_kadrin"
        bank = tn.water_name_bank(regions)
        assert [r.slug for r in bank] == ["sea_of_claws"], \
            f"the water bank must be exactly the black rows, got {[r.slug for r in bank]}"

        # A lowercase colour must normalise to the same uppercase index key, or a
        # sample would miss a region purely on the export's letter case.
        lower = tdp / "lower.tsv"
        lower.write_text(_tsv([("cr_oldworld_region_a", "aabbcc")] + filler), encoding="utf-8")
        assert "AABBCC" in tn.colour_index(tn.load_tww3_regions(lower)), \
            "colours must be normalised to uppercase"

        dup = tdp / "dup.tsv"
        dup.write_text(_tsv(rows + [("cr_oldworld_region_other", "112233")]), encoding="utf-8")
        _refuses(lambda: tn.load_tww3_regions(dup),
                 "two keys claiming one non-black colour must be refused")

        # Two black rows are NOT a duplicate — black is void, and the real file
        # carries 138 of them.
        dupblack = tdp / "dupblack.tsv"
        dupblack.write_text(_tsv(rows + [("cr_oldworld_region_bitter_sea", tn.WATER_HEX)]),
                            encoding="utf-8")
        assert len(tn.load_tww3_regions(dupblack)) == len(rows) + 1, \
            "repeated black colours must be allowed (138 of them in the real file)"

        bad = tdp / "bad.tsv"
        bad.write_text(_tsv([("cr_oldworld_region_a", "ZZTOP1")] + filler), encoding="utf-8")
        _refuses(lambda: tn.load_tww3_regions(bad), "a malformed colour must be refused")

        blank = tdp / "blank.tsv"
        blank.write_text(_tsv([("cr_oldworld_region_a", "")] + filler), encoding="utf-8")
        _refuses(lambda: tn.load_tww3_regions(blank), "a blank colour must be refused")

        short = tdp / "short.tsv"
        short.write_text(_tsv(base), encoding="utf-8")
        _refuses(lambda: tn.load_tww3_regions(short),
                 "a truncated export (< MIN_DATA_ROWS) must be refused")

        badhead = tdp / "badhead.tsv"
        badhead.write_text(_tsv(rows, header_line="key\tcolour"), encoding="utf-8")
        _refuses(lambda: tn.load_tww3_regions(badhead),
                 "a header shape mismatch must be refused — the colour column is "
                 "identified by name")

        # Byte-identical across two loads.
        a = tn.load_tww3_regions(good)
        b = tn.load_tww3_regions(good)
        assert a == b, "two loads of one file must be identical"

    # --- exact-hex sampling, on a hand-built array ----------------------------
    # 4x4: left half colour 112233, top-right 445566, bottom-right black.
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[:, :2] = (0x11, 0x22, 0x33)
    arr[:2, 2:] = (0x44, 0x55, 0x66)

    class _Stub:
        hex_at_lookup = tnl.Lookup.hex_at_lookup

    stub = _Stub()
    stub.arr = arr
    assert _Stub.hex_at_lookup(stub, 0, 0) == "112233"
    assert _Stub.hex_at_lookup(stub, 3, 0) == "445566"
    assert _Stub.hex_at_lookup(stub, 3, 3) == tn.WATER_HEX, \
        "the black quadrant must read as the water hex"
    assert index["112233"].slug == "altdorf" and tn.WATER_HEX not in index, \
        "a sampled hex resolves through the non-water colour index"

    # The citation format every accepted suggestion carries.
    cite = tnl.source_citation(tn.TWW3Region(key="cr_oldworld_region_altdorf",
                                             slug="altdorf", hex="112233", is_water=False))
    assert cite == ("canon: cr_oldworld_campaign/altdorf "
                    "(TWW3 Old World mod region table)"), f"citation format changed: {cite}"

    # The two scripts sampling the same bitmap MUST agree on which duplicate row
    # to drop, or they would disagree about the same pixel.
    import render_cr_lookup_overlay as rcl
    assert tnl.DROP_ROW == rcl.DROP_ROW and tnl.LOOKUP_SCALE == rcl.MASTER_TO_LOOKUP_SCALE, \
        "tww3_name_lookup and render_cr_lookup_overlay must share the row-drop and scale"

    # --- the printed-label crop render (board #4414) ---------------------------
    # It centres its crops through the SAME registration and master->campaign-map
    # scale, so a divergence would silently show a reviewer different ground than
    # the suggestion being checked. Unlike the lookup bitmap the text layer has no
    # duplicate padding row, so it must carry no row-drop constant at all.
    import render_tww3_text_crops as rtc
    assert rtc.TEXT_SCALE == tnl.LOOKUP_SCALE, \
        "text-crop tool must share the master->campaign-map scale"
    assert rtc.TEXT_SIZE == tnl.LOOKUP_SIZE, \
        "text layer and lookup share the 8192 campaign-map frame"
    assert not hasattr(rtc, "DROP_ROW"), \
        "cr_oldworld_map_text.png is 8192x8192 — no padding row to drop"

    # The drift test itself, on synthetic hexes: a matching pair is clean, a
    # mismatch flags, case never invents a phantom drift, and a row with no
    # recorded colour cannot drift (there is nothing to disagree with).
    assert rtc.is_anchor_drift("112233", "445566"), \
        "a sampled colour differing from the row's own must flag ANCHOR DRIFT"
    assert not rtc.is_anchor_drift("112233", "112233"), \
        "an unchanged colour must not flag drift"
    assert not rtc.is_anchor_drift("112233", "112233".lower()), \
        "the hex comparison must be case-insensitive"
    assert not rtc.is_anchor_drift("112233", ""), \
        "a row carrying no colour cannot drift"

    # The report-shape detector: each real shape recognised, and the anchorless
    # --regions vote report refused by name rather than silently cropping nothing.
    assert rtc.detect_report_kind(
        ["region_id", "worksheet_name", "kind", "anchor_x", "anchor_y", "status",
         "tww3_key", "tww3_slug", "hex", "margin_lookup_px", "agrees", "source"]
    ) == rtc.KIND_ANCHORS
    assert rtc.detect_report_kind(
        ["tww3_key", "tww3_slug", "hex", "area_lookup_px", "anchor_x", "anchor_y",
         "land_region_id", "status", "source"]
    ) == rtc.KIND_HUBS
    try:
        rtc.detect_report_kind(["region_id", "worksheet_name", "area_px",
                                "candidate_1", "fraction_1", "margin", "source"])
    except SystemExit as exc:
        assert "--regions" in str(exc), f"the vote report must be named: {exc}"
    else:
        raise AssertionError("a --regions vote report carries no anchors and must "
                             "be refused explicitly")


def _selfcheck_stable_ids() -> None:
    """Stable province colour+id assignment across regens (board #3705), isolated.

    The committed cross-regen regression the offline gate cannot otherwise see
    (it only ever runs ONE regen). Pins ``province_ids.assign`` — the mechanism
    that binds a province's colour+id to a stable identity carried by the committed
    map instead of to flood-fill / cut order — on a small synthetic committed map
    exercising land, sea AND lake:

    (a) a no-op regen keeps every colour+id and is byte-identical;
    (b) removing one province keeps every survivor's colour+id and retires the
        removed colour (never reused this run);
    (c) splitting a region lets the dominant-overlap piece keep the committed
        colour+id while a genuinely-new piece gets a fresh id >= the high-water and
        a colour reserved off ALL committed colours;
    (d) a land-count change leaves the sea and lake colours identical (the ripple
        the old single land->sea->lake allocator caused, now fixed);
    (e) reassign / no-committed reproduces the pre-#3705 fresh label-order
        allocation (colour by label ordinal, id == label);
    (f) the assignment is byte-identical when the committed cells are fed in a
        shuffled order and across two runs (no dict/set iteration leaks into a
        colour choice);

    plus a round-trip through ``validate_map.validate_provinces`` proving the new
    structural id invariants pass on a clean map and fire on a duplicate id, a
    non-positive id, and an id past the high-water.
    """
    from worldgen import province_ids
    import validate_map as vm

    SEED = map_config.SEED

    # --- The committed map: 3 land + 1 sea + 1 lake, deliberately non-contiguous
    #     ids (10/20/30/40/50) so a kept id is proven honoured verbatim, not
    #     recomputed as an ordinal. Layout (4 rows x 8 cols):
    #       1 1 1 2 2 2 4 4     1,2,3 land   4 sea   5 lake
    #       1 1 1 2 2 2 4 4
    #       3 3 3 3 5 5 4 4
    #       3 3 3 3 5 5 4 4
    L_c = np.array([
        [1, 1, 1, 2, 2, 2, 4, 4],
        [1, 1, 1, 2, 2, 2, 4, 4],
        [3, 3, 3, 3, 5, 5, 4, 4],
        [3, 3, 3, 3, 5, 5, 4, 4],
    ], dtype=np.int32)
    KIND = {1: "land", 2: "land", 3: "land", 4: "sea", 5: "lake"}
    COLOR = {1: (200, 0, 0), 2: (0, 200, 0), 3: (0, 0, 200), 4: (10, 10, 60), 5: (0, 120, 120)}
    CID = {1: 10, 2: 20, 3: 30, 4: 40, 5: 50}
    HIGH = 51

    def _committed(lab_arr, kind, color, cid):
        rgb = np.zeros((*lab_arr.shape, 3), dtype=np.uint8)
        cells_ = []
        for L in sorted(set(lab_arr.ravel().tolist()) - {0}):
            rgb[lab_arr == L] = color[L]
            cells_.append({"label": int(L), "kind": kind[L], "color": list(color[L]),
                           "id": cid[L]})
        return rgb, cells_

    def _kind_list(kind_by_label, total):
        out = [""] * (total + 1)
        for lab, k in kind_by_label.items():
            out[lab] = k
        return out

    committed_rgb, committed_cells = _committed(L_c, KIND, COLOR, CID)
    kind_c = _kind_list(KIND, 5)

    # (a) No-op regen: identical geometry -> every colour+id kept, byte-identical.
    pal, ids, hw = province_ids.assign(L_c, kind_c, committed_rgb, committed_cells, SEED,
                                       committed_high_water=HIGH)
    for L in range(1, 6):
        assert tuple(int(v) for v in pal[L]) == COLOR[L], f"(a) label {L} colour moved"
        assert int(ids[L]) == CID[L], f"(a) label {L} id moved"
    assert hw == HIGH, f"(a) no-op high-water must stay {HIGH}, got {hw}"
    pal2, ids2, hw2 = province_ids.assign(L_c, kind_c, committed_rgb, committed_cells, SEED,
                                          committed_high_water=HIGH)
    assert np.array_equal(pal, pal2) and np.array_equal(ids, ids2) and hw == hw2, \
        "(a) two runs must be byte-identical"

    # (b) Remove one province: old label 2 dropped (its pixels absorbed into a grown
    #     new land province), old 3/4/5 byte-identical. New contiguous labels 1..4.
    #       1 1 1 1 1 1 3 3     new1 = old1 U old2 (grown)   new3 = old4 sea
    #       1 1 1 1 1 1 3 3     new2 = old3 (unchanged)      new4 = old5 lake
    #       2 2 2 2 4 4 3 3
    #       2 2 2 2 4 4 3 3
    L_b = np.array([
        [1, 1, 1, 1, 1, 1, 3, 3],
        [1, 1, 1, 1, 1, 1, 3, 3],
        [2, 2, 2, 2, 4, 4, 3, 3],
        [2, 2, 2, 2, 4, 4, 3, 3],
    ], dtype=np.int32)
    kind_b = _kind_list({1: "land", 2: "land", 3: "sea", 4: "lake"}, 4)
    palb, idsb, hwb = province_ids.assign(L_b, kind_b, committed_rgb, committed_cells, SEED,
                                          committed_high_water=HIGH)
    assigned = {(tuple(int(v) for v in palb[L]), int(idsb[L])) for L in range(1, 5)}
    # The three geometry-unchanged provinces keep colour+id exactly.
    assert (COLOR[3], CID[3]) in assigned, "(b) unchanged land old3 must keep colour+id"
    assert (COLOR[4], CID[4]) in assigned, "(b) unchanged sea old4 must keep colour+id"
    assert (COLOR[5], CID[5]) in assigned, "(b) unchanged lake old5 must keep colour+id"
    # The removed province's colour+id are retired and reused by nobody this run.
    assert not any(c == COLOR[2] for c, _ in assigned), "(b) removed colour must be retired"
    assert not any(i == CID[2] for _, i in assigned), "(b) removed id must be retired"
    assert hwb == HIGH, f"(b) all-matched high-water must stay {HIGH}, got {hwb}"
    # (d) The land count dropped 3 -> 2, but the sea and lake colours are identical
    #     to committed (the ripple the old land->sea->lake allocator caused).
    sea_lab_b = next(L for L in range(1, 5) if kind_b[L] == "sea")
    lake_lab_b = next(L for L in range(1, 5) if kind_b[L] == "lake")
    assert tuple(int(v) for v in palb[sea_lab_b]) == COLOR[4], "(d) sea colour must not ripple"
    assert tuple(int(v) for v in palb[lake_lab_b]) == COLOR[5], "(d) lake colour must not ripple"

    # (c) Split old land province 1 into a dominant piece (4 px) + a small new piece
    #     (2 px); everything else unchanged. New contiguous labels 1..6.
    #       1 1 4 2 2 2 5 5     new1 = old1 dominant (4px)   new4 = old1 remainder (2px, NEW)
    #       1 1 4 2 2 2 5 5     new2 = old2   new3 = old3    new5 = old4 sea   new6 = old5 lake
    #       3 3 3 3 6 6 5 5
    #       3 3 3 3 6 6 5 5
    L_s = np.array([
        [1, 1, 4, 2, 2, 2, 5, 5],
        [1, 1, 4, 2, 2, 2, 5, 5],
        [3, 3, 3, 3, 6, 6, 5, 5],
        [3, 3, 3, 3, 6, 6, 5, 5],
    ], dtype=np.int32)
    kind_s = _kind_list({1: "land", 2: "land", 3: "land", 4: "land", 5: "sea", 6: "lake"}, 6)
    pals, idss, hws = province_ids.assign(L_s, kind_s, committed_rgb, committed_cells, SEED,
                                          committed_high_water=HIGH)
    # new1 is the dominant (4px > 2px) piece of old1 -> keeps committed1 colour+id.
    assert tuple(int(v) for v in pals[1]) == COLOR[1] and int(idss[1]) == CID[1], \
        "(c) dominant split piece must keep the committed colour+id"
    # new4 is the small new piece -> fresh id >= high-water, colour off ALL committed.
    assert int(idss[4]) >= HIGH, f"(c) new piece id {int(idss[4])} must be >= high-water {HIGH}"
    assert int(idss[4]) == HIGH, f"(c) first fresh id must be the high-water {HIGH}, got {int(idss[4])}"
    fresh_col = tuple(int(v) for v in pals[4])
    assert fresh_col not in set(COLOR.values()), \
        "(c) a fresh colour must be reserved off every committed colour (retained or retired)"
    assert hws == HIGH + 1, f"(c) high-water must advance past the one fresh id, got {hws}"

    # (e) reassign / no committed -> pre-#3705 fresh label-order allocation.
    pe, ie, he = province_ids.assign(L_c, kind_c, None, None, SEED)
    pr, ir, hr = province_ids.assign(L_c, kind_c, committed_rgb, committed_cells, SEED,
                                     reassign=True)
    assert np.array_equal(pe, pr) and np.array_equal(ie, ir) and he == hr, \
        "(e) reassign must equal the no-committed fresh allocation"
    alloc = ColorAllocator(SEED)
    for L in range(1, 6):
        assert tuple(int(v) for v in pe[L]) == alloc.allocate(), f"(e) label {L} not fresh label-order"
        assert int(ie[L]) == L, f"(e) fresh id must equal the label ({L})"
    assert he == 6, f"(e) fresh high-water must be total+1 (6), got {he}"

    # (f) Byte-identical under a shuffled committed-cell order and across two runs.
    shuffled = list(reversed(committed_cells))
    pf1, if1, hf1 = province_ids.assign(L_b, kind_b, committed_rgb, shuffled, SEED,
                                        committed_high_water=HIGH)
    pf2, if2, hf2 = province_ids.assign(L_b, kind_b, committed_rgb, committed_cells, SEED,
                                        committed_high_water=HIGH)
    assert np.array_equal(pf1, pf2) and np.array_equal(if1, if2) and hf1 == hf2, \
        "(f) committed-cell order must not affect the assignment"
    pf3, if3, hf3 = province_ids.assign(L_b, kind_b, committed_rgb, shuffled, SEED,
                                        committed_high_water=HIGH)
    assert np.array_equal(pf1, pf3) and np.array_equal(if1, if3) and hf1 == hf3, \
        "(f) two runs must be byte-identical"

    # --- validate_map.validate_provinces: the new id invariants pass clean + fire ---
    with tempfile.TemporaryDirectory(prefix="wh_stableids_") as td:
        tdp = Path(td)
        land = np.zeros((4, 4), dtype=bool)
        land[:, :2] = True                        # land = cols 0-1, sea = cols 2-3
        LC, SC = (200, 0, 0), (0, 0, 200)
        rgb = np.zeros((4, 4, 3), dtype=np.uint8)
        rgb[land] = LC
        rgb[~land] = SC
        write_rgb_png(tdp / "provinces.png", rgb)
        raster.write_mask_png(tdp / "mask.png", land)
        sea_lab = np.where(~land, 1, 0).astype(np.int32)
        cells.write_labels(tdp / "sea_zones.png", sea_lab)

        clean = {
            "canvas": [4, 4], "land_provinces": 1, "sea_provinces": 1, "lake_provinces": 0,
            "id_high_water": 21,
            "cells": [
                {"label": 1, "kind": "land", "color": list(LC), "hex": raster.color_to_hex(LC),
                 "id": 10, "area": 8, "coastal": True, "impassable": False,
                 "placeholder": False, "archipelago": False},
                {"label": 2, "kind": "sea", "color": list(SC), "hex": raster.color_to_hex(SC),
                 "id": 20, "area": 8, "coastal": True, "impassable": False,
                 "placeholder": False, "archipelago": False},
            ],
        }

        def _run(obj):
            (tdp / "index.json").write_text(json.dumps(obj) + "\n", encoding="utf-8")
            return vm.validate_provinces(tdp / "provinces.png", tdp / "mask.png",
                                         tdp / "index.json", tdp / "sea_zones.png", wrap_x=False)

        assert _run(clean) == [], "clean stable-id map must pass the validator"

        import copy
        dup = copy.deepcopy(clean); dup["cells"][1]["id"] = 10
        assert any("shared by more than one" in e for e in _run(dup)), "a duplicate id must fail"
        nonpos = copy.deepcopy(clean); nonpos["cells"][0]["id"] = 0
        assert any("not positive" in e for e in _run(nonpos)), "a non-positive id must fail"
        over = copy.deepcopy(clean); over["id_high_water"] = 15
        assert any("id_high_water" in e for e in _run(over)), "an id past the high-water must fail"


def _selfcheck_sea_naming() -> None:
    """Canon sea naming (worldgen.sea_naming), in isolation (no golden).

    Pins the properties generate_sea_zones.py relies on: per-pixel seed-Voronoi
    plurality assigns each zone to a canon sea, the ordinal NN follows the zones'
    wrap-robust first pixel, an override reassigns a single zone, a canon sea that
    wins nothing raises a loud warning (not a silent pass), an override on land is
    a hard error, and two runs are byte-identical.
    """
    from worldgen import sea_naming as sn
    from worldgen import cells as _cells
    from worldgen import schema as _schema

    # All-water canvas, four side-by-side zones (x: 0-9, 10-19, 20-29, 30-39).
    H, W = 8, 40
    land = np.zeros((H, W), dtype=bool)
    sea = np.zeros((H, W), dtype=np.int32)
    sea[:, 0:10] = 1
    sea[:, 10:20] = 2
    sea[:, 20:30] = 3
    sea[:, 30:40] = 4

    west = _schema.CanonSea("WEST", "West Sea", ((2, 4), (12, 4)), "")
    east = _schema.CanonSea("EAST", "East Sea", ((25, 4), (35, 4)), "")
    ghost = _schema.CanonSea("GHOST", "Ghost Sea", ((19, 4),), "")  # dominated in zone 2
    cfg = _schema.SeaZoneConfig(canon_seas=(west, east, ghost), overrides=())

    msgs: list[str] = []
    res = sn.assign(sea, land, cfg, wrap_x=False, log=msgs.append)
    assert res[1].sea_group == "WEST" and res[2].sea_group == "WEST", res
    assert res[3].sea_group == "EAST" and res[4].sea_group == "EAST", res
    # Ordinal follows first raster pixel: zone 1 (x=0) before zone 2 (x=10).
    assert res[1].key == "STATE_WEST_01" and res[2].key == "STATE_WEST_02", res
    assert res[3].key == "STATE_EAST_01" and res[4].key == "STATE_EAST_02", res
    assert res[1].display_name == "West Sea", res
    assert any("GHOST won 0 zones" in m for m in msgs), msgs

    # Two runs byte-identical.
    res2 = sn.assign(sea, land, cfg, wrap_x=False, log=None)
    assert res == res2, "sea naming must be deterministic"

    # An override reassigns a single zone, keyed on an interior pixel of it.
    cfg_ov = _schema.SeaZoneConfig(
        canon_seas=(west, east, ghost),
        overrides=(_schema.SeaZoneOverride((35, 4), "WEST", ""),),
    )
    res_ov = sn.assign(sea, land, cfg_ov, wrap_x=False, log=None)
    assert res_ov[4].sea_group == "WEST", res_ov
    assert res_ov[4].key == "STATE_WEST_03", res_ov  # renumbered within WEST

    # An override pixel on land is a hard error.
    land_hole = land.copy()
    sea_hole = sea.copy()
    land_hole[4, 5] = True
    sea_hole[4, 5] = 0
    cfg_bad = _schema.SeaZoneConfig(
        canon_seas=(west, east),
        overrides=(_schema.SeaZoneOverride((5, 4), "WEST", ""),),
    )
    try:
        sn.assign(sea_hole, land_hole, cfg_bad, wrap_x=False, log=None)
    except _cells.CellError:
        pass
    else:  # pragma: no cover
        raise AssertionError("an override on a land pixel must raise CellError")

    # rekey_by_display_name: an individually named zone's key follows its own
    # name, not its parent sea group's generic STATE_<group>_NN.
    zone_names = (
        _schema.SeaZoneDisplayName((2, 4), "Shard Coast", ""),  # zone 1, was STATE_WEST_01
    )
    cfg_named = _schema.SeaZoneConfig(canon_seas=(west, east, ghost), overrides=(),
                                      zone_names=zone_names)
    named = sn.assign(sea, land, cfg_named, wrap_x=False, log=None)
    named = sn.apply_zone_names(named, sea, cfg_named)
    assert named[1].display_name == "Shard Coast" and named[1].key == "STATE_WEST_01", named
    named, impassable, merged = sn.apply_naming_overrides(named, sea, cfg_named)
    assert not impassable and not merged, (impassable, merged)
    rekeyed = sn.rekey_by_display_name(named, sea, merged)
    # A name no other zone shares gets a bare key, no ordinal — there is only
    # one Shard Coast.
    assert rekeyed[1].key == "STATE_SHARD_COAST", rekeyed
    # A zone that kept its group's generic name is rekeyed from that name too, so
    # the key still matches what the player sees for it (zone 2's key becomes its
    # own display name "West Sea", not left as "WEST") — and it too is unique
    # within this fixture (zone 1 no longer shares "West Sea"), so no ordinal.
    assert rekeyed[2].display_name == "West Sea" and rekeyed[2].key == "STATE_WEST_SEA", \
        rekeyed
    # Zones 3 and 4 both carry the East canon sea's shared generic name, so they
    # DO collide and keep the disambiguating ordinal.
    assert rekeyed[3].key == "STATE_EAST_SEA_01" and rekeyed[4].key == "STATE_EAST_SEA_02", \
        rekeyed

    # Two zones sharing a display name are disambiguated by ordinal, ordered by
    # first pixel (zone 3 before zone 4), not left colliding on one key.
    dup_names = (
        _schema.SeaZoneDisplayName((25, 4), "Twin Strait", ""),
        _schema.SeaZoneDisplayName((35, 4), "Twin Strait", ""),
    )
    cfg_dup = _schema.SeaZoneConfig(canon_seas=(west, east, ghost), overrides=(),
                                    zone_names=dup_names)
    dup = sn.assign(sea, land, cfg_dup, wrap_x=False, log=None)
    dup = sn.apply_zone_names(dup, sea, cfg_dup)
    dup, _, dup_merged = sn.apply_naming_overrides(dup, sea, cfg_dup)
    dup = sn.rekey_by_display_name(dup, sea, dup_merged)
    assert dup[3].key == "STATE_TWIN_STRAIT_01" and dup[4].key == "STATE_TWIN_STRAIT_02", dup

    # A merge's zones keep their shared key (the STATE grouping mechanism) rather
    # than being rekeyed individually from their own display name.
    merge_cfg = _schema.SeaZoneConfig(
        canon_seas=(west, east, ghost), overrides=(),
        merges=(_schema.SeaZoneMerge("WHIRLPOOL", "Whirlpool", ((2, 4), (12, 4)),
                                     impassable=True, note=""),),
    )
    mrg = sn.assign(sea, land, merge_cfg, wrap_x=False, log=None)
    mrg = sn.apply_zone_names(mrg, sea, merge_cfg)
    mrg, mrg_impassable, mrg_merged = sn.apply_naming_overrides(mrg, sea, merge_cfg)
    assert mrg_merged == {1, 2} and mrg_impassable == {1, 2}, (mrg_merged, mrg_impassable)
    mrg = sn.rekey_by_display_name(mrg, sea, mrg_merged)
    assert mrg[1].key == "STATE_WHIRLPOOL_01" and mrg[2].key == "STATE_WHIRLPOOL_01", mrg


def _selfcheck_sea_state_ids() -> None:
    """Stable sea-zone STATE id + key assignment across regens (board #4191), isolated.

    The sea mirror of ``_selfcheck_stable_ids`` / ``_selfcheck_land_state_numbers``:
    ``worldgen.sea_state_ids.assign`` keys each zone's identity on **pixel overlap
    of the current ``sea_zones.png`` against the committed one** (not a province id
    — generate_sea_zones runs before generate_provinces), keeps a matched zone's
    committed id + key verbatim (when its display name is unchanged), issues a
    fresh id above a monotonic ``sea_id_high_water`` + a fresh per-slug ordinal for
    a genuinely new zone, and retires a removed zone's id/key/ordinal for good.

    All-water 8x40 canvas, side-by-side zones (the ``_selfcheck_sea_naming``
    fixture shape). Scenarios (a)-(k) mirror the workspec's testing plan:
    (a) no-op keeps every id+key, byte-identical across two runs, high-waters
    unchanged; (b) remove retires a zone's id+key, high-water does not regress;
    (c) a retired id is never reused; (d) a new zone gets a fresh id at the
    high-water + a fresh non-colliding ordinal, unrelated zones stable; (e) a
    renamed matched zone re-derives its key while keeping its id, others stable;
    (f) merged zones keep a stable id and their shared config key across an
    unrelated removal; (g) reassign / no committed baseline is the pre-#4191
    label-order bootstrap; (h) shuffled committed order + two runs are
    byte-identical; (i) zero-overlap falls back to bootstrap + a loud warning;
    (j) 2+ new zones sharing a brand-new slug are all numbered (not bare + _01),
    byte-identical to a reassign of the same geometry; (k) a digit-suffixed
    display name recovers its slug via _slugify, not a trailing-digit strip.
    """
    from worldgen import sea_state_ids as ssi
    from worldgen.sea_naming import SeaZoneName as SZ

    H, W = 8, 40

    def _layout(spec: dict[int, tuple[int, int]]) -> np.ndarray:
        z = np.zeros((H, W), dtype=np.int32)
        for lab, (a, b) in spec.items():
            z[:, a:b] = lab
        return z

    def _index(id_of, key_of, naming, hw, ohw, labels):
        return {
            "cells": [{"label": l, "id": id_of[l], "key": key_of[l],
                       "display_name": naming[l].display_name} for l in labels],
            "sea_id_high_water": hw,
            "ordinal_high_water": ohw,
        }

    # Committed baseline: four full-width zones, distinct display names.
    zc = _layout({1: (0, 10), 2: (10, 20), 3: (20, 30), 4: (30, 40)})
    nc = {1: SZ("STATE_ALPHA", "G", "Alpha"), 2: SZ("STATE_BETA", "G", "Beta"),
          3: SZ("STATE_GAMMA", "G", "Gamma"), 4: SZ("STATE_DELTA", "G", "Delta")}
    idc, keyc, hwc, ohwc = ssi.assign(zc, nc, set(), None, None, 3000)
    assert idc == {1: 3000, 2: 3001, 3: 3002, 4: 3003}, f"bootstrap ids {idc}"
    ci = _index(idc, keyc, nc, hwc, ohwc, range(1, 5))

    # (a) no-op: identical geometry keeps every id + key; high-waters unchanged;
    #     two runs byte-identical.
    ida, keya, hwa, ohwa = ssi.assign(zc, nc, set(), zc, ci, 3000)
    assert ida == idc and keya == keyc, f"(a) no-op must keep ids+keys, got {ida} {keya}"
    assert hwa == hwc and ohwa == ohwc, f"(a) no-op high-waters must be unchanged, got {hwa} {ohwa}"
    ida2, keya2, hwa2, ohwa2 = ssi.assign(zc, nc, set(), zc, ci, 3000)
    assert (ida, keya, hwa, ohwa) == (ida2, keya2, hwa2, ohwa2), "(a) two runs must be byte-identical"

    # (b) remove zone 4 (Delta): current has 3 zones overlapping committed 1,2,3.
    zb = _layout({1: (0, 10), 2: (10, 20), 3: (20, 40)})
    nb = {1: nc[1], 2: nc[2], 3: nc[3]}
    idb, keyb, hwb, ohwb = ssi.assign(zb, nb, set(), zc, ci, 3000)
    assert idb == {1: 3000, 2: 3001, 3: 3002}, f"(b) survivors keep ids, got {idb}"
    assert 3003 not in idb.values(), "(b) removed id must retire"
    assert "STATE_DELTA" not in keyb.values(), "(b) removed key must retire"
    assert hwb == hwc, f"(b) high-water must not regress, got {hwb} (was {hwc})"

    # (c) retired id not reused: committed WITHOUT delta (it retired), then a
    #     genuinely new zone appears -> its id is the high-water (3004), never the
    #     freed 3003.
    ci_retired = _index(idb, keyb, nb, hwc, ohwb, range(1, 4))
    zc2 = _layout({1: (0, 10), 2: (10, 20), 3: (20, 30), 4: (30, 40)})
    nc2 = {1: nc[1], 2: nc[2], 3: nc[3], 4: SZ("STATE_EPSILON", "G", "Epsilon")}
    idcc, keycc, hwcc, _ = ssi.assign(zc2, nc2, set(), zb, ci_retired, 3000)
    assert idcc[4] == 3004, f"(c) new zone id must be the high-water 3004, not the freed 3003, got {idcc[4]}"
    assert 3003 not in idcc.values(), "(c) the retired 3003 must never be reused"
    assert hwcc == 3005, f"(c) high-water advances by one, got {hwcc}"

    # (d) new zone: fresh id at the high-water (+1) + a fresh ordinal in its slug;
    #     the three unchanged zones keep their ids/keys/ordinals.
    zd = _layout({1: (0, 10), 2: (10, 20), 3: (20, 30), 4: (30, 35), 5: (35, 40)})
    nd = {1: nc[1], 2: nc[2], 3: nc[3], 4: nc[4], 5: SZ("x", "G", "Newsea")}
    idd, keyd, hwd, _ = ssi.assign(zd, nd, set(), zc, ci, 3000)
    assert {idd[i] for i in (1, 2, 3, 4)} == {3000, 3001, 3002, 3003}, f"(d) old zones keep ids, got {idd}"
    assert idd[5] == 3004 and hwd == 3005, f"(d) new zone at high-water, got id {idd[5]} hw {hwd}"
    assert keyd[5] == "STATE_NEWSEA", f"(d) a lone new-slug zone gets a bare key, got {keyd[5]}"
    assert keyd[1] == "STATE_ALPHA" and keyd[4] == "STATE_DELTA", "(d) unrelated keys stable"

    # (e) rename matched zone 2: keeps its committed id, re-derives its key; every
    #     other zone byte-stable.
    ne = {1: nc[1], 2: SZ("ignored", "G", "Renamed"), 3: nc[3], 4: nc[4]}
    ide, keye, _, _ = ssi.assign(zc, ne, set(), zc, ci, 3000)
    assert ide == idc, f"(e) rename must keep all ids (geometry unchanged), got {ide}"
    assert keye[2] == "STATE_RENAMED", f"(e) renamed zone re-derives its key, got {keye[2]}"
    assert keye[1] == "STATE_ALPHA" and keye[3] == "STATE_GAMMA" and keye[4] == "STATE_DELTA", \
        "(e) every other key byte-stable"

    # (f) merge: committed zones 3,4 are a merge sharing STATE_MAELSTROM_01. A regen
    #     removes the unrelated zone 1; the two merged zones keep their committed
    #     ids (so the group's min(id) — the land naval_exit — stays put) and their
    #     shared config key.
    ncm = {1: nc[1], 2: nc[2],
           3: SZ("STATE_MAELSTROM_01", "MAELSTROM", "The Maelstrom"),
           4: SZ("STATE_MAELSTROM_01", "MAELSTROM", "The Maelstrom")}
    idcm, keycm, hwcm, ohwcm = ssi.assign(zc, ncm, {3, 4}, None, None, 3000)
    assert keycm[3] == "STATE_MAELSTROM_01" and keycm[4] == "STATE_MAELSTROM_01", keycm
    cim = _index(idcm, keycm, ncm, hwcm, ohwcm, range(1, 5))
    # current: zone 1 removed; the two merged bodies + Beta survive (same pixels).
    zf = _layout({1: (10, 20), 2: (20, 30), 3: (30, 40)})
    nf = {1: nc[2],
          2: SZ("STATE_MAELSTROM_01", "MAELSTROM", "The Maelstrom"),
          3: SZ("STATE_MAELSTROM_01", "MAELSTROM", "The Maelstrom")}
    idf, keyf, _, _ = ssi.assign(zf, nf, {2, 3}, zc, cim, 3000)
    assert idf[2] == 3002 and idf[3] == 3003, f"(f) merged zones keep their committed ids, got {idf}"
    assert keyf[2] == "STATE_MAELSTROM_01" and keyf[3] == "STATE_MAELSTROM_01", \
        f"(f) merged zones keep their shared config key, got {keyf}"
    assert idf[1] == 3001, f"(f) surviving Beta keeps its id, got {idf[1]}"

    # (g) reassign / no committed baseline -> pre-#4191 label-order bootstrap:
    #     id = 3000 + label - 1, key = the naming key verbatim.
    idg, keyg, hwg, _ = ssi.assign(zc, nc, set(), zc, ci, 3000, reassign=True)
    assert idg == {l: 3000 + l - 1 for l in range(1, 5)}, f"(g) reassign ids must be label-order, got {idg}"
    assert keyg == {l: nc[l].key for l in range(1, 5)}, f"(g) reassign keys must be verbatim, got {keyg}"
    assert hwg == 3004, f"(g) reassign high-water == SEA_ID_START + n, got {hwg}"
    idg2, keyg2, _, _ = ssi.assign(zc, nc, set(), None, None, 3000)
    assert idg == idg2 and keyg == keyg2, "(g) reassign == no-committed-baseline bootstrap"

    # (h) order-invariance + determinism: a shuffled committed cell list and two
    #     runs produce byte-identical output.
    ci_shuf = _index(idc, keyc, nc, hwc, ohwc, [4, 2, 1, 3])
    idh, keyh, hwh, ohwh = ssi.assign(zc, nc, set(), zc, ci_shuf, 3000)
    assert (idh, keyh, hwh, ohwh) == (ida, keya, hwa, ohwa), "(h) committed order must not affect the result"
    idh2, keyh2, hwh2, ohwh2 = ssi.assign(zc, nc, set(), zc, ci_shuf, 3000)
    assert (idh, keyh, hwh, ohwh) == (idh2, keyh2, hwh2, ohwh2), "(h) two runs must be byte-identical"

    # (i) zero-overlap safety net: committed zones sit in disjoint rows from the
    #     current ones (no pixel overlap) -> bootstrap fallback + a loud warning.
    z_bottom = np.zeros((H, W), dtype=np.int32)
    z_bottom[4:8, 0:20] = 1
    z_bottom[4:8, 20:40] = 2
    c_top = np.zeros((H, W), dtype=np.int32)
    c_top[0:4, 0:20] = 1
    c_top[0:4, 20:40] = 2
    n_bottom = {1: SZ("STATE_A", "G", "A"), 2: SZ("STATE_B", "G", "B")}
    ci_top = _index({1: 3000, 2: 3001}, {1: "STATE_A", 2: "STATE_B"}, n_bottom, 3002, {"A": 2, "B": 2}, [1, 2])
    msgs: list[str] = []
    idi, keyi, hwi, _ = ssi.assign(z_bottom, n_bottom, set(), c_top, ci_top, 3000, log=msgs.append)
    assert idi == {1: 3000, 2: 3001}, f"(i) zero-overlap must bootstrap to label order, got {idi}"
    assert msgs and "ZERO zones" in msgs[0], "(i) a zero-overlap collapse must warn loudly"

    # (j) fresh multi-zone slug: two brand-new zones sharing a new display name in
    #     one regen -> both numbered (_01/_02), NOT bare + _01; byte-identical to a
    #     reassign of the same geometry for those labels.
    zc3 = _layout({1: (0, 20), 2: (20, 40)})
    nc3 = {1: SZ("STATE_A", "G", "A"), 2: SZ("STATE_B", "G", "B")}
    idc3, keyc3, hwc3, ohwc3 = ssi.assign(zc3, nc3, set(), None, None, 3000)
    ci3 = _index(idc3, keyc3, nc3, hwc3, ohwc3, range(1, 3))
    zj = _layout({1: (0, 20), 2: (20, 30), 3: (30, 35), 4: (35, 40)})
    nj = {1: SZ("STATE_A", "G", "A"), 2: SZ("STATE_B", "G", "B"),
          3: SZ("STATE_TWIN_01", "G", "Twin"), 4: SZ("STATE_TWIN_02", "G", "Twin")}
    idj, keyj, _, _ = ssi.assign(zj, nj, set(), zc3, ci3, 3000)
    assert keyj[3] == "STATE_TWIN_01" and keyj[4] == "STATE_TWIN_02", \
        f"(j) two new same-slug zones must both be numbered, got {keyj}"
    idj_re, keyj_re, _, _ = ssi.assign(zj, nj, set(), zc3, ci3, 3000, reassign=True)
    assert keyj_re[3] == keyj[3] and keyj_re[4] == keyj[4], "(j) matched fresh keys must equal a reassign of the same geometry"

    # (k) digit-suffixed display name: "Far Passage 3" -> slug FAR_PASSAGE_3 (key
    #     STATE_FAR_PASSAGE_3 is BARE, ordinal 1) recovered via _slugify, not a
    #     trailing-digit strip that would corrupt slug FAR_PASSAGE's high-water.
    ohw_k = ssi._seed_ordinal_high_water(
        [{"key": "STATE_FAR_PASSAGE_3", "display_name": "Far Passage 3"}])
    assert ohw_k == {"FAR_PASSAGE_3": 2}, f"(k) digit-suffixed slug must be FAR_PASSAGE_3 ordinal 1, got {ohw_k}"
    ohw_k2 = ssi._seed_ordinal_high_water(
        [{"key": "STATE_FAR_PASSAGE_02", "display_name": "Far Passage"}])
    assert ohw_k2 == {"FAR_PASSAGE": 3}, f"(k) a genuine FAR_PASSAGE _02 stays its own slug, got {ohw_k2}"


def _selfcheck_land_state_numbers() -> None:
    """Stable land STATE-number assignment across regens (board #4188), isolated.

    Mirrors ``_selfcheck_stable_ids``'s coverage but at the land-REGION level:
    ``worldgen.land_state_numbering.assign_state_numbers`` keys a region's
    identity on its set of stable province ids (already stable per #3705,
    ``_selfcheck_stable_ids`` above) rather than a pixel colour, area-weighted
    overlap-matches it against a committed ``land_state_ids.json``-shaped
    record, and issues/retires numbers exactly like ``province_ids.assign``
    issues/retires colours+ids.

    Committed baseline (mirrors the workspec's real Marches-of-Couronne/
    Couronne example): three committed states —
    A (number 10, provinces {1,2,3,4}), B (20, {5,6}), C (30, {7,8}) — with
    areas 1-4 = 10 each, 5-6 = 15 each (a bigger polity), 7-8 = 5 each (a
    smaller one), high-water 31.

    (a) a no-op regen (identical province-id sets) keeps every number and is
        byte-identical across two runs;
    (b) removing a region (its committed provinces vanish from every current
        region) retires its number — it never resurfaces this run;
    (c) splitting A into a dominant piece (3 of its 4 provinces, by area) plus
        a small new piece (A's 4th province + a genuinely new stable id, e.g.
        from a province regen) keeps the dominant piece on number 10 and
        gives the small piece a fresh number == the high-water, which then
        advances by exactly one;
    (d) merging B and C into one current region keeps the larger-overlap
        (B, by area) number and retires the smaller (C);
    (e) ``reassign=True`` (or no committed index at all) reproduces the pure
        ``compute_state_numbers`` Hilbert-rank bootstrap, high-water ==
        n_regions + 1;
    (f) the assignment is byte-identical whether the committed states list is
        fed in its original or reversed order, and across two runs — no
        dict/set iteration leaks into a number choice;
    (g) a non-empty committed index that matches **zero** current regions
        (the un-paired-province-``--reassign`` signature) falls back to the
        bootstrap branch instead of retiring every state, and calls the
        ``log`` callback with a loud warning.
    """
    from worldgen import land_state_numbering as lsn

    AREA = {1: 10, 2: 10, 3: 10, 4: 10, 5: 15, 6: 15, 7: 5, 8: 5, 99: 5}
    COMMITTED = {
        "state_number_high_water": 31,
        "states": [
            {"state_number": 10, "province_ids": [1, 2, 3, 4]},
            {"state_number": 20, "province_ids": [5, 6]},
            {"state_number": 30, "province_ids": [7, 8]},
        ],
    }

    def _centroids(n: int) -> tuple[np.ndarray, np.ndarray]:
        # Spread out, distinct, arbitrary — only their RELATIVE Hilbert order
        # matters, and every scenario below has at most one unmatched region
        # per committed state so the exact fresh-number order is never
        # ambiguous.
        cx = np.array([0.0] + [200.0 * i for i in range(1, n + 1)])
        cy = np.array([0.0] + [100.0 * i for i in range(1, n + 1)])
        return cx, cy

    # (a) No-op: every current region equals a committed state's province set.
    cx, cy = _centroids(3)
    regions_a = {1: {1, 2, 3, 4}, 2: {5, 6}, 3: {7, 8}}
    nums_a, idx_a = lsn.assign_state_numbers(cx, cy, 3, regions_a, AREA, COMMITTED)
    assert int(nums_a[1]) == 10 and int(nums_a[2]) == 20 and int(nums_a[3]) == 30, \
        f"(a) no-op must keep every committed number, got {nums_a[1:]}"
    assert idx_a["state_number_high_water"] == 31, "(a) no-op high-water must stay 31"
    nums_a2, idx_a2 = lsn.assign_state_numbers(cx, cy, 3, regions_a, AREA, COMMITTED)
    assert np.array_equal(nums_a, nums_a2) and idx_a == idx_a2, "(a) two runs must be byte-identical"

    # (b) Remove region B (provinces 5,6 vanish from every current region) —
    #     its number (20) must not appear anywhere in the output.
    cx2, cy2 = _centroids(2)
    regions_b = {1: {1, 2, 3, 4}, 2: {7, 8}}
    nums_b, idx_b = lsn.assign_state_numbers(cx2, cy2, 2, regions_b, AREA, COMMITTED)
    assert int(nums_b[1]) == 10 and int(nums_b[2]) == 30, f"(b) survivors must keep their numbers, got {nums_b[1:]}"
    assert 20 not in {s["state_number"] for s in idx_b["states"]}, "(b) removed number must be retired"
    assert idx_b["state_number_high_water"] == 31, "(b) all-matched high-water must stay 31"

    # (c) Split A: region1 = dominant 3/4 provinces (area 30), region2 = A's
    #     4th province + a genuinely new stable id 99 (area 15) — region1
    #     wins A's number by overlap, region2 is unmatched -> fresh number.
    cx4, cy4 = _centroids(4)
    regions_c = {1: {1, 2, 3}, 2: {4, 99}, 3: {5, 6}, 4: {7, 8}}
    nums_c, idx_c = lsn.assign_state_numbers(cx4, cy4, 4, regions_c, AREA, COMMITTED)
    assert int(nums_c[1]) == 10, f"(c) dominant split piece must keep the committed number, got {nums_c[1]}"
    assert int(nums_c[2]) == 31, f"(c) new split piece must get the high-water number, got {nums_c[2]}"
    assert int(nums_c[3]) == 20 and int(nums_c[4]) == 30, "(c) untouched regions must keep their numbers"
    assert idx_c["state_number_high_water"] == 32, f"(c) high-water must advance by one, got {idx_c['state_number_high_water']}"

    # (d) Merge B+C into one region: B contributes more area (30 vs 10) so the
    #     merged region keeps B's number (20); C's (30) retires.
    cx1, cy1 = _centroids(1)
    regions_d = {1: {5, 6, 7, 8}}
    nums_d, idx_d = lsn.assign_state_numbers(cx1, cy1, 1, regions_d, AREA, COMMITTED)
    assert int(nums_d[1]) == 20, f"(d) merged region must keep the larger-overlap number, got {nums_d[1]}"
    assert 30 not in {s["state_number"] for s in idx_d["states"]}, "(d) smaller-overlap number must retire"

    # (e) reassign / no committed index -> pure compute_state_numbers bootstrap.
    bootstrap_expected = lsn.compute_state_numbers(cx, cy, 3)
    nums_none, idx_none = lsn.assign_state_numbers(cx, cy, 3, regions_a, AREA, None)
    nums_reassign, idx_reassign = lsn.assign_state_numbers(cx, cy, 3, regions_a, AREA, COMMITTED, reassign=True)
    assert np.array_equal(nums_none, bootstrap_expected), "(e) no-index must equal pure Hilbert bootstrap"
    assert np.array_equal(nums_reassign, bootstrap_expected), "(e) reassign must equal pure Hilbert bootstrap"
    assert idx_none == idx_reassign, "(e) no-index and reassign must produce the identical fresh index"
    assert idx_none["state_number_high_water"] == 4, "(e) bootstrap high-water must be n_regions + 1"

    # (f) Byte-identical under a shuffled committed-states order and across
    #     two runs — no dict/set iteration leaks into a number choice.
    shuffled = {"state_number_high_water": COMMITTED["state_number_high_water"],
               "states": list(reversed(COMMITTED["states"]))}
    nums_f1, idx_f1 = lsn.assign_state_numbers(cx, cy, 3, regions_a, AREA, shuffled)
    nums_f2, idx_f2 = lsn.assign_state_numbers(cx, cy, 3, regions_a, AREA, COMMITTED)
    assert np.array_equal(nums_f1, nums_f2) and idx_f1 == idx_f2, "(f) committed-state order must not affect the result"
    nums_f3, idx_f3 = lsn.assign_state_numbers(cx, cy, 3, regions_a, AREA, shuffled)
    assert np.array_equal(nums_f1, nums_f3) and idx_f1 == idx_f3, "(f) two runs must be byte-identical"

    # (g) Zero-match safety net: current regions use province ids disjoint from
    #     every committed state (the un-paired province `--reassign` signature)
    #     -> falls back to the pure bootstrap instead of retiring every state,
    #     and warns via the log callback.
    regions_g = {1: {101, 102, 103, 104}, 2: {105, 106}, 3: {107, 108}}
    area_g = {101: 10, 102: 10, 103: 10, 104: 10, 105: 15, 106: 15, 107: 5, 108: 5}
    warnings: list[str] = []
    nums_g, idx_g = lsn.assign_state_numbers(cx, cy, 3, regions_g, area_g, COMMITTED, log=warnings.append)
    assert np.array_equal(nums_g, bootstrap_expected), "(g) zero-match must fall back to the pure Hilbert bootstrap"
    assert idx_g["state_number_high_water"] == 4, "(g) zero-match fallback high-water must be n_regions + 1, not the committed one"
    assert warnings and "ZERO regions" in warnings[0], "(g) a zero-match collapse must warn loudly"

    # --- seed_land_state_ids: pure block parser on a tiny synthetic file ----
    import seed_land_state_ids as seed

    sample = (
        'STATE_TEST_A = {\n'
        '    id = 5\n'
        '    subsistence_building = "building_subsistence_farm"\n'
        '    provinces = { xAAAAAA xBBBBBB }\n'
        '    city = xAAAAAA\n'
        '    arable_land = 10\n'
        '    capped_resources = {\n'
        '        building_logging_camp = 10\n'
        '    }\n'
        '    naval_exit_id = 3005\n'
        '}\n'
        'STATE_TEST_B = {\n'
        '    id = 6\n'
        '    provinces = { xCCCCCC }\n'
        '}\n'
    )
    parsed = seed._parse_state_file(sample)
    assert parsed == [(5, ["xAAAAAA", "xBBBBBB"]), (6, ["xCCCCCC"])], (
        f"seed parser must extract each STATE's id + province hexes, ignoring "
        f"arable_land/naval_exit_id and the nested capped_resources block, got {parsed}"
    )

    fake_prov_index = {"cells": [
        {"kind": "land", "hex": "xAAAAAA", "id": 101},
        {"kind": "land", "hex": "xBBBBBB", "id": 102},
        {"kind": "land", "hex": "xCCCCCC", "id": 103},
        {"kind": "sea", "hex": "xDDDDDD", "id": 900},  # a sea cell must be ignored
    ]}
    built = seed._build_index_from_texts(fake_prov_index, {"05_test.txt": sample})
    assert built["state_number_high_water"] == 7, f"seed high-water must be max(state number) + 1, got {built}"
    assert built["states"] == [
        {"state_number": 5, "province_ids": [101, 102]},
        {"state_number": 6, "province_ids": [103]},
    ], f"seed index must map each state's province hexes to their stable ids, sorted, got {built}"


def _write_test_ora(path: Path, w: int, h: int, layers: list[dict]) -> None:
    """Write a synthetic .ora to ``path`` for :func:`_selfcheck_ora_reader`.

    ``layers`` is a list of ``{name, rgba (HxWx4 uint8), x=0, y=0,
    visibility="visible"}`` dicts, written in order. ``mimetype`` is written
    first and uncompressed (stored), matching real GIMP exports."""
    import io as _io

    from PIL import Image as _Image

    with zipfile.ZipFile(path, "w") as zf:
        mi = zipfile.ZipInfo("mimetype")
        zf.writestr(mi, b"image/openraster", compress_type=zipfile.ZIP_STORED)
        layer_xml: list[str] = []
        for i, layer in enumerate(layers):
            src = f"data/{i:03d}.png"
            buf = _io.BytesIO()
            _Image.fromarray(layer["rgba"], "RGBA").save(buf, format="PNG")
            zf.writestr(src, buf.getvalue())
            vis = layer.get("visibility", "visible")
            layer_xml.append(
                f'<layer src="{src}" name="{layer["name"]}" x="{layer.get("x", 0)}" '
                f'y="{layer.get("y", 0)}" opacity="1.0" visibility="{vis}" '
                f'composite-op="svg:src-over" />'
            )
        stack_xml = f'<image w="{w}" h="{h}"><stack>' + "".join(layer_xml) + "</stack></image>"
        zf.writestr("stack.xml", stack_xml)


def _selfcheck_alpha_zero() -> None:
    """Nothing at alpha 0 is ever read as paint (Chris, 2026-10-15).

    An erased brush stroke keeps its RGB under alpha 0 (a transparent pixel can
    still be red underneath), and ``convert("RGB")`` exposes it. Two guards:

    1. the shared image readers return RGB 0 under every alpha-0 pixel (flat RGBA
       PNG through :func:`raster.read_rgb_png` / :func:`raster.rgb_zero_transparent`
       / :func:`sources.read_source_rgba`);
    2. a source lint: no script outside the allowlist of opaque derived/engine
       images calls ``.convert("RGB")`` — a new reader must go through
       ``worldgen.raster.read_rgb_png`` / ``rgb_zero_transparent``.
    """
    import re
    import tempfile
    from pathlib import Path

    import numpy as np
    from PIL import Image
    from worldgen import raster
    from worldgen import sources as src_mod

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ghost.png"
        a = np.zeros((4, 4, 4), dtype=np.uint8)
        a[..., :3] = (255, 0, 0)       # red everywhere ...
        a[0, 0, 3] = 0                 # ... but alpha 0: an erased stroke
        a[0, 1, 3] = 255               # one real red pixel
        a[1:, :, 3] = 0
        Image.fromarray(a, "RGBA").save(p)
        for name, got in (
            ("raster.read_rgb_png", raster.read_rgb_png(p)),
            ("raster.rgb_zero_transparent", raster.rgb_zero_transparent(Image.open(p))),
            ("sources.read_source_rgba", src_mod.read_source_rgba(p.name, Path(td))[..., :3]),
        ):
            assert got.shape == (4, 4, 3), (name, got.shape)
            assert tuple(got[0, 1]) == (255, 0, 0), f"{name}: visible paint was lost"
            ghost = got.copy()
            ghost[0, 1] = 0
            assert not ghost.any(), f"{name}: RGB under alpha 0 leaked"

    root = Path(__file__).resolve().parent
    allow = {
        # opaque derived / engine images, art composites and size-only reads
        "build_real_world_equivalents.py", "generate_flatmap_textures.py", "generate_map_locators.py",
        "generate_terrain_masks.py", "render_canon_cities_preview.py", "render_tww3_text_crops.py",
        "render_wind_patterns.py", "render_arable_preview.py", "run_fixture.py",
        "worldgen/pop_history.py", "worldgen/raster.py", "worldgen/sources.py",
    }
    pat = re.compile(r"""\.convert\(["']RGB["']\)""")
    offenders = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith((".venv/", "derived/", "fixtures/")) or rel in allow:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if pat.search(line):
                offenders.append(f"{rel}:{n}")
    assert not offenders, (
        "convert('RGB') exposes the colour under alpha 0; read hand-drawn/art inputs through "
        "worldgen.raster.read_rgb_png / rgb_zero_transparent (or add the file to the allowlist "
        "in _selfcheck_alpha_zero if it only reads opaque output): " + ", ".join(offenders))


def _selfcheck_ora_reader() -> None:
    """The .ora (OpenRaster) layer reader (board #5399), on synthetic archives
    built in a temp dir — no dependency on the real gitignored ``sources/``."""
    from worldgen import sources as src_mod

    with tempfile.TemporaryDirectory(prefix="wh_ora_") as tmp_s:
        tmp = Path(tmp_s)
        w, h = 10, 8

        base = np.zeros((h, w, 4), dtype=np.uint8)
        base[:, :] = (10, 20, 30, 255)
        base[0, 0] = (99, 88, 77, 0)  # transparent px, nonzero stored RGB -> must read back as 0

        hidden = np.full((4, 4, 4), (200, 0, 0, 255), dtype=np.uint8)
        overhang = np.full((5, 5, 4), (0, 200, 0, 255), dtype=np.uint8)
        dup_a = np.zeros((1, 1, 4), dtype=np.uint8)
        dup_b = np.full((1, 1, 4), 1, dtype=np.uint8)
        empty_layer = np.zeros((3, 3, 4), dtype=np.uint8)

        ora_path = tmp / "test.ora"
        _write_test_ora(ora_path, w, h, [
            {"name": "base", "x": 0, "y": 0, "rgba": base},
            {"name": "hidden", "x": 3, "y": -2, "rgba": hidden, "visibility": "hidden"},
            {"name": "overhang", "x": w - 2, "y": 0, "rgba": overhang},
            {"name": "dup", "x": 0, "y": 0, "rgba": dup_a},
            {"name": "dup", "x": 0, "y": 0, "rgba": dup_b},
            {"name": "empty_layer", "x": 0, "y": 0, "rgba": empty_layer},
        ])

        # --- read by name: composite equals a hand-built expected array -----
        got_base = src_mod.read_ora_layer(ora_path, "base")
        expected_base = base.copy()
        expected_base[0, 0, :3] = 0  # RGB zeroed under alpha 0
        assert np.array_equal(got_base, expected_base), "base layer composite mismatch"

        got_hidden = src_mod.read_ora_layer(ora_path, "hidden")
        expected_hidden = np.zeros((h, w, 4), dtype=np.uint8)
        # x=3,y=-2, 4x4 source: canvas rows 0..1 <- src rows 2..3; canvas cols 3..6 <- src cols 0..3
        expected_hidden[0:2, 3:7] = hidden[2:4, 0:4]
        assert np.array_equal(got_hidden, expected_hidden), "hidden layer composite mismatch (offset/clip)"
        assert got_hidden[..., 3].any(), "hidden layer must be readable despite visibility=hidden"

        got_overhang = src_mod.read_ora_layer(ora_path, "overhang")
        expected_overhang = np.zeros((h, w, 4), dtype=np.uint8)
        # x=w-2=8,y=0, 5x5 source clipped to canvas cols 8..9 (src cols 0..1), all 5 rows fit
        expected_overhang[0:5, 8:10] = overhang[0:5, 0:2]
        assert np.array_equal(got_overhang, expected_overhang), "overhang layer composite mismatch (right-edge clip)"

        # --- stray partial-opacity paint (e.g. an accidental 98% brush stroke)
        #     must be snapped to exactly 0/255, not shipped as-is -----------------
        stray = np.zeros((h, w, 4), dtype=np.uint8)
        stray[:, :] = (10, 20, 30, 255)
        stray[0, 0] = (1, 2, 3, 250)   # ~98% opacity -> must snap to 255, RGB kept
        stray[0, 1] = (1, 2, 3, 5)     # ~2% opacity -> must snap to 0, RGB zeroed
        stray[0, 2] = (1, 2, 3, 128)   # exact midpoint -> rounds up to 255
        stray[0, 3] = (1, 2, 3, 127)   # just under midpoint -> rounds down to 0
        stray_path = tmp / "stray.ora"
        _write_test_ora(stray_path, w, h, [{"name": "stray", "x": 0, "y": 0, "rgba": stray}])
        got_stray = src_mod.read_ora_layer(stray_path, "stray")
        assert got_stray[0, 0, 3] == 255 and tuple(got_stray[0, 0, :3]) == (1, 2, 3), got_stray[0, 0]
        assert got_stray[0, 1, 3] == 0 and tuple(got_stray[0, 1, :3]) == (0, 0, 0), got_stray[0, 1]
        assert got_stray[0, 2, 3] == 255, "alpha 128 (the midpoint) must round up to 255"
        assert got_stray[0, 3, 3] == 0, "alpha 127 (just under the midpoint) must round down to 0"
        assert set(np.unique(got_stray[..., 3]).tolist()) <= {0, 255}, "alpha must only ever be 0 or 255"

        # --- missing name lists the available names -------------------------
        try:
            src_mod.read_ora_layer(ora_path, "nope")
            raise AssertionError("a missing layer name must raise OraError")
        except src_mod.OraError as exc:
            msg = str(exc)
            for name in ("base", "hidden", "overhang", "dup", "empty_layer"):
                assert name in msg, f"missing-name error must list available names, got: {msg}"

        # --- duplicated requested name raises; an unrelated duplicate does not --
        try:
            src_mod.read_ora_layer(ora_path, "dup")
            raise AssertionError("a name matching 2 layers must raise OraError")
        except src_mod.OraError:
            pass
        src_mod.read_ora_layer(ora_path, "base")  # unrelated duplicate ("dup") must not block this

        # --- empty layer: raises unless allow_empty=True ---------------------
        try:
            src_mod.read_ora_layer(ora_path, "empty_layer")
            raise AssertionError("an all-transparent layer must raise OraError by default")
        except src_mod.OraError:
            pass
        got_empty = src_mod.read_ora_layer(ora_path, "empty_layer", allow_empty=True)
        assert got_empty.shape == (h, w, 4) and int(got_empty[..., 3].max()) == 0

        # --- ora_layer_names ---------------------------------------------------
        names = src_mod.ora_layer_names(ora_path)
        assert names == ["base", "hidden", "overhang", "dup", "dup", "empty_layer"], names

        # --- malformed archives: wrong mimetype, malformed XML, nested <stack>,
        #     missing src --------------------------------------------------------
        bad_mime = tmp / "bad_mime.ora"
        with zipfile.ZipFile(bad_mime, "w") as zf:
            zf.writestr("mimetype", b"image/png")
            zf.writestr("stack.xml", f'<image w="{w}" h="{h}"><stack></stack></image>')
        try:
            src_mod.read_ora_layer(bad_mime, "base")
            raise AssertionError("a wrong mimetype must raise OraError")
        except src_mod.OraError:
            pass

        bad_xml = tmp / "bad_xml.ora"
        with zipfile.ZipFile(bad_xml, "w") as zf:
            zf.writestr("mimetype", b"image/openraster")
            zf.writestr("stack.xml", f'<image w="{w}" h="{h}"><stack>')  # unterminated
        try:
            src_mod.ora_layer_names(bad_xml)
            raise AssertionError("malformed stack.xml must raise OraError")
        except src_mod.OraError:
            pass

        nested = tmp / "nested.ora"
        with zipfile.ZipFile(nested, "w") as zf:
            zf.writestr("mimetype", b"image/openraster")
            zf.writestr(
                "stack.xml",
                f'<image w="{w}" h="{h}"><stack><stack>'
                f'<layer src="data/000.png" name="x" /></stack></stack></image>',
            )
        try:
            src_mod.ora_layer_names(nested)
            raise AssertionError("a nested <stack> (layer group) must raise OraError")
        except src_mod.OraError:
            pass

        no_src = tmp / "no_src.ora"
        with zipfile.ZipFile(no_src, "w") as zf:
            zf.writestr("mimetype", b"image/openraster")
            zf.writestr(
                "stack.xml",
                f'<image w="{w}" h="{h}"><stack>'
                f'<layer src="data/999.png" name="ghost" /></stack></image>',
            )
        try:
            src_mod.read_ora_layer(no_src, "ghost")
            raise AssertionError("a layer src absent from the archive must raise OraError")
        except src_mod.OraError:
            pass

        # --- split_ref ---------------------------------------------------------
        assert src_mod.split_ref("plain.png") == ("plain.png", None)
        assert src_mod.split_ref("x.ora#layer") == ("x.ora", "layer")
        assert src_mod.split_ref("x#y.png") == ("x#y.png", None)
        assert src_mod.split_ref("x.ora") == ("x.ora", None)
        assert src_mod.split_ref("X.ORA#Layer") == ("X.ORA", "Layer")

        # --- image_dims on an .ora ----------------------------------------------
        assert src_mod.image_dims(ora_path) == f"{w}x{h}"

        # --- load_source_image with the manifest SHA-256 guard -----------------
        sources_dir = tmp / "sources"
        sources_dir.mkdir()
        guarded_ora = sources_dir / "s.ora"
        _write_test_ora(guarded_ora, w, h, [{"name": "a", "x": 0, "y": 0, "rgba": base}])
        sha = src_mod.sha256_of(guarded_ora)
        manifest_path = tmp / "SOURCES.md"
        manifest_path.write_text(
            "# test manifest\n\n"
            f"{src_mod.MANIFEST_BEGIN}\n"
            + src_mod.render_table([
                src_mod.ManifestRow("s.ora", f"{w}x{h}", str(guarded_ora.stat().st_size),
                                     sha, "test", "test", "no"),
            ])
            + f"\n{src_mod.MANIFEST_END}\n",
            encoding="utf-8",
        )
        loaded_rgb = src_mod.load_source_image("s.ora#a", sources_dir=sources_dir, manifest_path=manifest_path)
        assert np.array_equal(loaded_rgb, expected_base[..., :3])
        with open(guarded_ora, "ab") as fh:
            fh.write(b"\x00")  # tamper
        try:
            src_mod.load_source_image("s.ora#a", sources_dir=sources_dir, manifest_path=manifest_path)
            raise AssertionError("a tampered .ora must fail the SHA-256 guard")
        except src_mod.ManifestError:
            pass

        # --- load_source_layers refusals ----------------------------------------
        def _refused(text: str) -> bool:
            p = tmp / "sl.json"
            p.write_text(text, encoding="utf-8")
            try:
                src_mod.load_source_layers(p)
                return False
            except src_mod.ManifestError:
                return True

        assert _refused("[]"), "a non-object source_layers.json must be refused"
        assert _refused('{"k": ""}'), "an empty ref value must be refused"
        assert _refused('{"k": "x.ora"}'), "an .ora ref with no #layer must be refused"
        assert _refused('{"k": "plain.png#layer"}'), "a '#' in a non-.ora ref must be refused"
        ok_path = tmp / "sl_ok.json"
        ok_path.write_text('{"k": "s.ora#a"}', encoding="utf-8")
        assert src_mod.load_source_layers(ok_path) == {"k": "s.ora#a"}

        # --- verify()'s source_layers.json step ---------------------------------
        v4_sources = tmp / "v4_sources"
        v4_sources.mkdir()
        v4_ora = v4_sources / "a.ora"
        _write_test_ora(v4_ora, w, h, [
            {"name": "x", "x": 0, "y": 0, "rgba": base},
            {"name": "dup2", "x": 0, "y": 0, "rgba": dup_a},
            {"name": "dup2", "x": 0, "y": 0, "rgba": dup_b},
        ])
        from PIL import Image as _Image2

        _Image2.fromarray(base, "RGBA").save(v4_sources / "flat.png")
        (v4_sources / "missing.png").write_bytes((v4_sources / "flat.png").read_bytes())

        v4_manifest = tmp / "v4_SOURCES.md"
        v4_manifest.write_text(
            f"{src_mod.MANIFEST_BEGIN}\n"
            + src_mod.render_table([
                src_mod.ManifestRow("a.ora", f"{w}x{h}", str(v4_ora.stat().st_size),
                                     src_mod.sha256_of(v4_ora), "test", "test", "no"),
                src_mod.ManifestRow("flat.png", src_mod.image_dims(v4_sources / "flat.png"),
                                     str((v4_sources / "flat.png").stat().st_size),
                                     src_mod.sha256_of(v4_sources / "flat.png"), "test", "test", "no"),
            ])
            + f"\n{src_mod.MANIFEST_END}\n",
            encoding="utf-8",
        )
        v4_reg_dir = tmp / "v4_registration"
        v4_reg_dir.mkdir()

        def _v4(table: dict) -> list[str]:
            sl_path = tmp / "v4_source_layers.json"
            sl_path.write_text(json.dumps(table), encoding="utf-8")
            return src_mod.verify(
                sources_dir=v4_sources, manifest_path=v4_manifest,
                registration_dir=v4_reg_dir, source_layers_path=sl_path,
            )

        assert _v4({"ok": "a.ora#x"}) == [], "a clean, resolvable ref must yield no error"
        errs = _v4({"missing_file": "notfound.ora#y"})
        assert len(errs) == 1 and "missing_file" in errs[0], errs
        errs = _v4({"no_manifest_row": "missing.png"})
        assert len(errs) == 1 and "no_manifest_row" in errs[0], errs
        errs = _v4({"missing_layer": "a.ora#nope"})
        assert len(errs) == 1 and "missing_layer" in errs[0], errs
        errs = _v4({"dup_layer": "a.ora#dup2"})
        assert len(errs) == 1 and "dup_layer" in errs[0], errs
        # A missing source_layers.json path (the ingest/boundary fixture harness
        # idiom) is a clean skip, not an error.
        no_table_errs = src_mod.verify(
            sources_dir=v4_sources, manifest_path=v4_manifest, registration_dir=v4_reg_dir,
            source_layers_path=tmp / "does-not-exist-source-layers.json",
        )
        assert no_table_errs == [], no_table_errs

        # --- read_source_rgba: flat file, alpha-0 RGB zeroing, determinism ------
        flat_rgba = src_mod.read_source_rgba("flat.png", sources_dir=v4_sources)
        assert flat_rgba is not None
        assert np.array_equal(flat_rgba, expected_base), "flat-file read must zero RGB under alpha 0 too"
        assert src_mod.read_source_rgba("does-not-exist.png", sources_dir=v4_sources) is None

        again = src_mod.read_ora_layer(ora_path, "base")
        assert np.array_equal(got_base, again) and got_base.tobytes() == again.tobytes(), \
            "two reads of the same layer must be byte-identical"


def _selfcheck_piecewise_affine() -> None:
    """The piecewise-affine warp projection (board: scale-collage registration).

    A unit square with a displaced centre dot triangulates into four fan
    triangles. The checks are the properties that make this projection the right
    answer for a source whose regions are drawn at different scales:

    * **Exact at every control point**, both directions (the fit IS the dots).
    * **Locally affine, not globally smooth** — the centre maps where its dot
      says, which a single affine/TPS through the corners cannot reproduce. This
      is the "no inter-region skew" property.
    * **Continuous across every triangle edge (no tearing)** — a dense grid over
      the interior has no jump larger than the local Jacobian allows; a tear
      would show a large adjacent-pixel discontinuity.
    * **No data past the convex hull** — outside points read as the far-outside
      sentinel so consumers drop them.
    * **Deterministic** across two builds, and the **schema** accepts the new
      projection while still rejecting fewer than three points.
    """
    canvas = np.array([[0, 0], [100, 0], [100, 100], [0, 100], [50, 50]], dtype=np.float64)
    source = np.array([[0, 0], [100, 0], [100, 100], [0, 100], [70, 30]], dtype=np.float64)
    rec = {
        "source": "piecewise_selfcheck.png", "role": "test",
        "projection": "piecewise_affine_warp", "footprint": [0, 0, 100, 100],
        "precedence": 1,
        "control_points": [
            {"source": source[i].tolist(), "canvas": canvas[i].tolist(), "note": str(i)}
            for i in range(len(canvas))
        ],
    }
    reg = schema.SourceRegistration.from_dict(rec, "piecewise_selfcheck")
    fit = reproject.fit_placement(reg)
    inv = reproject.fit_placement_inverse(reg)

    # Exact at every control point, both directions.
    sx, sy = fit.to_source_px(canvas[:, 0], canvas[:, 1])
    assert np.allclose(np.column_stack([sx, sy]), source, atol=1e-6), \
        "piecewise forward not exact at the control points"
    cx, cy = inv.to_canvas_px(source[:, 0], source[:, 1])
    assert np.allclose(np.column_stack([cx, cy]), canvas, atol=1e-6), \
        "piecewise inverse not exact at the control points"

    # Locally affine: the centre lands on its dot (70,30). A least-squares affine
    # through the four corners is the identity, which would put it at (50,50) —
    # so piecewise is demonstrably NOT a single global affine.
    csx, csy = fit.to_source_px(np.array([50.0]), np.array([50.0]))
    assert abs(csx[0] - 70) < 1e-6 and abs(csy[0] - 30) < 1e-6, "centre not honoured"
    assert np.hypot(csx[0] - 50, csy[0] - 50) > 20, "piecewise collapsed to the global affine"

    # Continuous across the interior edges: a fine interior grid is finite
    # everywhere (inside the hull) and has no tear — adjacent samples differ by
    # less than the local scale allows. The max source scale here is ~1.4, the
    # grid step ~0.49 px, so a genuine mapping stays well under 2 px; a torn edge
    # would jump tens of px.
    g = np.linspace(1.0, 99.0, 201)
    gx, gy = np.meshgrid(g, g)
    fx, fy = fit.to_source_px(gx, gy)
    assert np.isfinite(fx).all() and (fx > -1e8).all(), "interior sampled the outside-hull sentinel"
    jump = np.maximum(
        np.abs(np.diff(fx, axis=1)).max() + np.abs(np.diff(fy, axis=1)).max(),
        np.abs(np.diff(fx, axis=0)).max() + np.abs(np.diff(fy, axis=0)).max())
    assert jump < 2.0, f"piecewise field tears across an edge (max adjacent jump {jump:.2f} px)"

    # No data past the convex hull -> the far-outside sentinel, which every
    # consumer's in-frame check drops.
    ox, oy = fit.to_source_px(np.array([-25.0, 150.0]), np.array([-25.0, 150.0]))
    assert (ox < -1e8).all(), "outside-hull query did not return the sentinel"

    # Deterministic across two independent builds.
    fit2 = reproject.fit_placement(reg)
    fx2, fy2 = fit2.to_source_px(gx, gy)
    assert np.array_equal(fx, fx2) and np.array_equal(fy, fy2), "piecewise fit is not deterministic"

    # Schema: accepts the projection, still rejects fewer than three points.
    raised = False
    try:
        schema.SourceRegistration.from_dict({**rec, "control_points": rec["control_points"][:2]},
                                            "piecewise_selfcheck_short")
    except schema.SchemaError:
        raised = True
    assert raised, "schema accepted a piecewise_affine_warp with fewer than 3 control points"


def _selfcheck_composite() -> None:
    """Precedence resolution + tie rejection for worldgen.composite."""
    shape = (4, 4)
    base = composite.Mosaic(shape)
    lo = np.zeros(shape, dtype=np.uint8)
    hi = np.ones(shape, dtype=np.uint8) * 9
    valid_all = np.ones(shape, dtype=bool)
    half = np.zeros(shape, dtype=bool)
    half[:, :2] = True
    base.add(composite.Layer("lo", 1, lo, valid_all))
    base.add(composite.Layer("hi", 5, hi, half))
    out, covered = base.resolve()
    assert covered.all(), "one full-coverage layer must cover everything"
    assert (out[:, :2] == 9).all(), "higher precedence must win where it is valid"
    assert (out[:, 2:] == 0).all(), "lower precedence fills the rest"
    # A precedence tie is rejected — the winner would depend on insertion order.
    try:
        composite.Mosaic(shape).add(composite.Layer("a", 1, lo, valid_all)) \
            .add(composite.Layer("b", 1, hi, valid_all))
    except composite.CompositeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("composite must reject two layers at the same precedence")


# ---------------------------------------------------------------------------
# Self-check: wrap-aware distance across the seam
# ---------------------------------------------------------------------------

def _selfcheck_wrap() -> None:
    w = FIXTURE_CANVAS[0]
    assert point_distance((1, 10), (127, 10), w, wrap_x=True) == 2.0
    assert point_distance((1, 10), (127, 10), w, wrap_x=False) == 126.0
    # A point near the right edge is close to a segment near the left edge when the
    # x axis wraps, and far when it does not.
    near = segment_point_distance((126, 15), (1, 10), (1, 20), w, wrap_x=True)
    far = segment_point_distance((126, 15), (1, 10), (1, 20), w, wrap_x=False)
    assert near < 5.0 < far


def _selfcheck_frame() -> None:
    """The Miller canvas frame: exact round trip, and a guard against a bad grid.

    The frame is the one piece of this toolchain whose correctness is a *maths*
    property rather than a golden bitmap, so it is checked as maths. The invariant
    is deliberately asymmetric — ``lonlat_to_canvas`` folds x into ``[0, width)``
    while ``canvas_to_lonlat`` does not, because ``fit_parametric`` needs a seam
    control point recorded at ``x = WIDTH`` to read back as +180 — so the round
    trip is *latitude exact everywhere, longitude exact modulo width*. It is
    checked at both the provinces grid and the 2x heightmap grid, since every real
    consumer runs at one of those two scales.
    """
    from config import canvas_frame as cf

    for w, h in (map_config.PROVINCES_SIZE, map_config.HEIGHTMAP_SIZE):
        xs = np.linspace(0.0, w, 419)
        ys = np.linspace(0.0, h, 419)
        gx, gy = np.meshgrid(xs, ys)
        lon, lat = cf.canvas_to_lonlat(gx, gy, w, h)
        rx, ry = cf.lonlat_to_canvas(lon, lat, w, h)
        dlat = float(np.abs(ry - gy).max())
        dlon = float(np.abs(((rx - gx + w / 2) % w) - w / 2).max())
        assert dlat < 1e-6, f"frame latitude round trip off by {dlat:.2e}px at {w}x{h}"
        assert dlon < 1e-6, f"frame longitude round trip off by {dlon:.2e}px (mod width) at {w}x{h}"

    # The uniform-grid guard must fire on a grid whose height is not width*H/W —
    # under Miller a non-multiple grid would distort latitude silently, so the
    # frame refuses it rather than guessing.
    raised = False
    try:
        cf.lonlat_to_canvas(0.0, 0.0, cf.WIDTH, cf.HEIGHT - 1)
    except ValueError:
        raised = True
    assert raised, "canvas frame accepted a non-uniformly-scaled grid — the guard is broken"

    # The band the frame actually claims, pinned so a fat-fingered constant is caught.
    assert abs(cf.LAT_TOP - 74.9052) < 1e-3, f"LAT_TOP drifted to {cf.LAT_TOP}"
    assert abs(cf.LAT_BOTTOM - (-57.4084)) < 1e-3, f"LAT_BOTTOM drifted to {cf.LAT_BOTTOM}"


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _snapshot(root: Path) -> dict[str, bytes]:
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root)).replace("\\", "/")] = path.read_bytes()
    return out


def _diff(a: dict[str, bytes], b: dict[str, bytes]) -> list[str]:
    problems = []
    for name in sorted(set(a) | set(b)):
        if name not in a:
            problems.append(f"only in second: {name}")
        elif name not in b:
            problems.append(f"only in first: {name}")
        elif a[name] != b[name]:
            problems.append(f"differs: {name}")
    return problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _selfcheck_marker() -> None:
    """The border-markup extraction, in isolation (no golden needed).

    Pins ``parchment.marker_barrier``: the user's hand-drawn marker lines plus the
    map's rivers become the barrier, while roads and terrain — dark but *thin* —
    are ignored. A synthetic tile carries all three: two magenta borders, a thick
    dark river band, and a thin dark road. With rivers on, the magenta borders and
    the river carve a 3x2 grid (6 cells); with rivers off, only the magenta borders
    act, giving 3 columns — which also proves the thin road never becomes a border
    (or the rivers-off count would be 6, not 3).
    """
    from worldgen import parchment as P

    h, w = 100, 150
    rgb = np.full((h, w, 3), (185, 150, 110), dtype=np.uint8)  # parchment
    rgb[24:26, :] = (60, 45, 30)      # thin ROAD (dark) — must be ignored
    rgb[60:70, :] = (25, 18, 12)      # thick RIVER band — a real border
    rgb[:, 48:51] = (255, 0, 255)     # magenta border 1
    rgb[:, 98:101] = (255, 0, 255)    # magenta border 2
    valid = np.ones((h, w), dtype=bool)
    valid[:, 145:] = False            # a transparent footprint strip

    barrier, mf, rf = P.marker_barrier(rgb, (255, 0, 255), tol=70, dilate=0,
                                       rivers={"darkness": 60, "open": 2, "dilate": 1},
                                       valid=valid)
    _, n = P.cells_from_ink(barrier, 50)
    assert n == 6, f"marker + river should carve 6 cells, got {n}"
    barrier0, _, _ = P.marker_barrier(rgb, (255, 0, 255), tol=70, dilate=0,
                                      rivers=None, valid=valid)
    _, n0 = P.cells_from_ink(barrier0, 50)
    assert n0 == 3, f"marker alone should carve 3 columns (road ignored), got {n0}"
    assert mf > 0 and rf > 0, "marker and river fractions must be positive"


def _selfcheck_reseed_dots() -> None:
    """The paired-anchor-dot reseed core, in isolation (no golden needed).

    Pins ``worldgen.reseed_dots``: detection (chromatic component absent from the
    original, sub-4px speck and near-gray diff ignored; the noisy-rect chroma
    rule — a pale dot survives OUTSIDE a rect at ``relaxed_chroma`` while a
    same-chroma mark INSIDE is dropped), ``select_new`` (a dot on an existing
    landmark is skipped, a far one is new), ``pair_by_colour`` (colour pairing,
    a beyond-tolerance mismatch rejected as unpaired), ``ignore_colours`` (a dot
    on a trace), ``resolve_repeated_colours`` (same-colour dots paired by
    position, too few points refused), ``name_pairs``
    (``c_<hex>`` + ``_N`` disambiguation) and determinism.
    """
    from worldgen import reseed_dots as R

    H, W = 40, 60
    base = np.full((H, W, 3), (185, 150, 110), dtype=np.uint8)  # parchment
    orig = base.copy()
    dots = base.copy()

    def stamp(img, cx, cy, colour, r=1):
        img[cy - r:cy + r + 1, cx - r:cx + r + 1] = colour

    # A saturated red dot (chroma 255), a sub-4px speck (single px), a near-gray
    # difference (chroma 5 — ink, not a dot), and a pale blue dot (chroma 60).
    stamp(dots, 10, 10, (255, 0, 0))            # 3x3 = 9 px, kept
    dots[30, 50] = (0, 200, 0)                  # 1 px speck, dropped (< MIN_DOT_PX)
    stamp(dots, 45, 8, (150, 150, 155))         # near-gray, chroma 5, dropped
    stamp(dots, 20, 30, (120, 140, 180))        # pale, chroma 60

    got = R.detect_dots(orig, dots, chroma_floor=120)
    cols = sorted(d.color for d in got)
    assert cols == [(255, 0, 0)], f"chroma_floor=120 should keep only the red dot, got {cols}"

    # Noisy-rect rule: the pale dot survives OUTSIDE the rect at relaxed=40, but a
    # same-pale mark INSIDE the rect (which demands >=120) is dropped.
    stamp(dots, 52, 32, (120, 140, 180))        # pale, inside the rect below
    rects = ((48, 28, 60, 40),)                 # x0,y0,x1,y1 around (52,32)
    got2 = R.detect_dots(orig, dots, chroma_floor=120, relaxed_chroma=40,
                         noisy_rects=rects)
    centres = sorted((round(d.cx), round(d.cy)) for d in got2)
    assert (20, 30) in centres, "pale dot outside the noisy rect must survive"
    assert (52, 32) not in centres, "pale mark inside the noisy rect must be dropped"
    assert (10, 10) in centres, "the red dot must still be kept under the noisy rule"

    # select_new: one dot sits on an existing landmark, the other is new.
    dots3 = base.copy()
    stamp(dots3, 10, 10, (255, 0, 0))           # matches the landmark below
    stamp(dots3, 40, 20, (0, 0, 255))           # new
    found = R.detect_dots(orig, dots3, chroma_floor=120)
    landmarks = [{"name": "c_ff0000", "source": [10.5, 10.5], "canvas": [0, 0]}]
    new, matched = R.select_new(found, landmarks, "source", tol_px=3.0)
    assert matched == 1 and len(new) == 1 and new[0].color == (0, 0, 255), \
        f"select_new should skip the on-landmark dot, got matched={matched} new={new}"

    # pair_by_colour: a colour match pairs; a mismatch beyond tolerance is unpaired.
    red_m = R.Dot(10.0, 10.0, (255, 0, 0), 9)
    red_c = R.Dot(99.0, 99.0, (250, 4, 3), 9)
    blue_m = R.Dot(40.0, 20.0, (0, 0, 255), 9)
    green_c = R.Dot(80.0, 80.0, (0, 200, 0), 9)   # no master match
    pairs, up_m, up_c = R.pair_by_colour([red_m, blue_m], [red_c, green_c],
                                         max_colour_dist=40.0)
    assert len(pairs) == 1 and pairs[0].master is red_m and pairs[0].canvas is red_c
    assert up_m == [blue_m] and up_c == [green_c], \
        f"blue master + green canvas must be unpaired, got {up_m} {up_c}"

    # ignore_colours: a dot touching a same-sheet trace stays its own component.
    traced = base.copy()
    traced[18, 5:55] = (0, 255, 255)            # a cyan trace across the sheet
    stamp(traced, 30, 17, (0, 255, 0))          # a green dot sitting on it
    assert R.detect_dots(orig, traced, chroma_floor=120) == [], \
        "a dot merged into a long trace is one oversized component, dropped"
    on_trace = R.detect_dots(orig, traced, chroma_floor=120,
                             ignore_colours=((0, 255, 255),))
    assert [d.color for d in on_trace] == [(0, 255, 0)], \
        f"ignore_colours should leave only the green dot, got {on_trace}"

    # resolve_repeated_colours: three reds and two blues, canvas = a rotated,
    # scaled, shifted copy of the master, handed over mis-paired within each colour.
    def to_canvas(x, y):
        return (300.0 + 1.5 * x - 0.4 * y, 80.0 + 0.4 * x + 1.5 * y)
    spots = [((10.0, 10.0), (255, 0, 0)), ((90.0, 20.0), (255, 0, 0)),
             ((40.0, 70.0), (255, 0, 0)), ((70.0, 80.0), (0, 0, 255)),
             ((20.0, 45.0), (0, 0, 255))]
    m_d = [R.Dot(x, y, c, 9) for (x, y), c in spots]
    c_d = [R.Dot(*to_canvas(x, y), c, 9) for (x, y), c in spots]
    wrong = [R.Pair(m_d[0], c_d[2], 0.0), R.Pair(m_d[1], c_d[0], 0.0),
             R.Pair(m_d[2], c_d[1], 0.0), R.Pair(m_d[3], c_d[4], 0.0),
             R.Pair(m_d[4], c_d[3], 0.0)]
    fixed, rep = R.resolve_repeated_colours(wrong)
    assert all(p.canvas is c_d[i] for i, p in enumerate(fixed)), \
        "repeated colours must be re-paired by position"
    assert rep["combos"] == 12 and rep["rms_px"] < 1e-3 < rep["runner_up_rms_px"], rep
    same, rep1 = R.resolve_repeated_colours([wrong[0], wrong[3]])
    assert same == [wrong[0], wrong[3]] and rep1["rms_px"] is None, \
        "distinct colours pass through untouched"
    try:
        R.resolve_repeated_colours(wrong[:2])
    except ValueError:
        pass
    else:
        raise AssertionError("two same-colour pairs alone cannot be told apart by position")

    # name_pairs: c_<hex> + _N disambiguation against existing + within-batch.
    p1 = R.Pair(R.Dot(1, 1, (191, 0, 255), 9), R.Dot(2, 2, (190, 0, 254), 9), 1.0)
    p2 = R.Pair(R.Dot(3, 3, (191, 0, 255), 9), R.Dot(4, 4, (192, 0, 255), 9), 1.0)
    named = R.name_pairs([p1, p2], {"c_bf00ff"})
    assert [lm["name"] for lm in named] == ["c_bf00ff_2", "c_bf00ff_3"], \
        f"name_pairs disambiguation wrong: {[lm['name'] for lm in named]}"

    # Determinism: identical inputs -> identical detection.
    again = R.detect_dots(orig, dots, chroma_floor=120, relaxed_chroma=40,
                          noisy_rects=rects)
    assert [(d.cx, d.cy, d.color, d.size) for d in got2] == \
           [(d.cx, d.cy, d.color, d.size) for d in again], "detect_dots not deterministic"


def _selfcheck_parse_layers() -> None:
    """The unified projection's ``--colors`` -> ora-layer resolution, in isolation
    (no golden needed, no dependency on the real gitignored .ora).

    Pins ``project_regions_unified.parse_layers``: a name resolves to its
    ``NAMED_LAYERS`` entry (incl. ``light-blue`` -> ``cities``), a matching
    ``#rrggbb`` literal resolves to the same layer, a repeated layer (by name
    or by its equivalent hex) is deduped, the RETURNED order always follows
    ``LAYER_Z_ORDER`` (impassable bottom, state_regions middle, cities on top)
    regardless of the order tokens were given in, and an unknown name / a hex
    matching no layer's flat-fill colour / an empty spec all raise
    ``SystemExit``.
    """
    import project_regions_unified as P

    MAGENTA = ("magenta", "state_regions", (255, 0, 255))
    ORANGE = ("orange", "impassable", (255, 127, 0))
    LIGHT_BLUE = ("light-blue", "cities", (127, 127, 255))

    # z-order (impassable, state_regions, cities) wins over input order.
    assert P.parse_layers("magenta,orange") == [ORANGE, MAGENTA]
    assert P.parse_layers("orange,magenta") == [ORANGE, MAGENTA]
    assert P.parse_layers("light-blue,magenta,orange") == [ORANGE, MAGENTA, LIGHT_BLUE]
    assert P.parse_layers("orange,magenta,light-blue") == [ORANGE, MAGENTA, LIGHT_BLUE], \
        "compositing order must not depend on the order --colors tokens were given in"

    assert P.parse_layers("#ff00ff") == [MAGENTA]
    assert P.parse_layers("#7f7fff") == [LIGHT_BLUE]
    assert P.parse_layers(" MAGENTA , orange ") == [ORANGE, MAGENTA], "case/space tolerant"
    assert P.parse_layers("magenta,#ff00ff,magenta") == [MAGENTA], \
        "a repeated layer (by name or equivalent hex) is deduped"

    for bad in ("bogus", "", ",", "#ff00", "#00ffff"):
        try:
            P.parse_layers(bad)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"parse_layers({bad!r}) should have raised SystemExit")


def _selfcheck_composite_layers_over() -> None:
    """``project_regions_unified.composite_layers_over``, in isolation.

    A single layer passes through unchanged; a fully-opaque top layer replaces
    the bottom everywhere; a partially-transparent top layer's opaque pixels
    win and its transparent pixels leave the bottom showing, alpha itself
    accumulating (over, not replace); an empty list raises; and two runs are
    byte-identical.
    """
    import project_regions_unified as P

    H, W = 4, 4
    bottom = np.zeros((H, W, 4), dtype=np.uint8)
    bottom[..., :3] = (10, 20, 30)
    bottom[..., 3] = 255

    solo = P.composite_layers_over([bottom])
    assert np.array_equal(solo, bottom), "a single layer must pass through unchanged"

    opaque_top = np.zeros((H, W, 4), dtype=np.uint8)
    opaque_top[..., :3] = (200, 0, 0)
    opaque_top[..., 3] = 255
    over_opaque = P.composite_layers_over([bottom, opaque_top])
    assert np.array_equal(over_opaque, opaque_top), \
        "a fully-opaque top layer must replace the bottom everywhere"

    partial_top = np.zeros((H, W, 4), dtype=np.uint8)
    partial_top[1:3, 1:3] = (0, 200, 0, 255)  # opaque patch, rest transparent
    over_partial = P.composite_layers_over([bottom, partial_top])
    assert tuple(over_partial[1, 1]) == (0, 200, 0, 255), "opaque top pixel must win"
    assert tuple(over_partial[0, 0]) == tuple(bottom[0, 0]), \
        "transparent top pixel must leave the bottom showing"

    again = P.composite_layers_over([bottom, partial_top])
    assert np.array_equal(over_partial, again), "composite_layers_over not deterministic"

    try:
        P.composite_layers_over([])
    except ValueError:
        pass
    else:
        raise AssertionError("composite_layers_over([]) should have raised ValueError")


def _selfcheck_state_ownership() -> dict:
    """Starting-ownership map: render -> read round-trips on the synthetic world.

    Drives ``worldgen.state_ownership`` (the core of ``render_state_ownership.py`` /
    ``read_state_ownership.py``) over the committed golden provinces + state files:
    whole-state fills, a split state (GAMMA straddles the x=0 seam), a placeholder
    state (DELTA), border overlay ignored on read, unknown colour / scope mismatch /
    unassigned-state refusals, byte-stable JSON, and the committed legend loading.
    """
    from worldgen import state_ownership as so

    legend = so.parse_legend({
        "reserved": {"water": [16, 40, 112], "unowned": [255, 255, 255],
                     "placeholder": [176, 176, 176], "border": [0, 0, 0]},
        "tags": {"REI": {"color": [178, 58, 58]}, "MID": {"color": [62, 74, 96]}},
    })
    states = so.load_land_states(EXPECTED_DIR / "state_regions")
    prov = raster.read_rgb_png(EXPECTED_DIR / "provinces.png")
    layout = so.Layout(prov, states)
    by_key = {s.key: s for s in states}
    placeholder = {"STATE_DELTA"}
    gamma = by_key["STATE_GAMMA"].provinces
    assignment = {
        "STATE_ALPHA": "REI",
        "STATE_BETA": "unowned",
        "STATE_GAMMA": {tok: ("REI" if i < 2 else "MID") for i, tok in enumerate(gamma)},
    }
    ids = {s.key: (s.id, None) for s in states}

    owners = so.province_owners(layout, assignment, placeholder, legend)
    img = so.render(layout, owners, legend, border_width=2)
    assert (img == np.array(legend.reserved["border"], dtype=np.uint8)).all(axis=2).any(), \
        "the border overlay must be drawn"
    doc = so.read(layout, img, legend, placeholder, ids)
    assert so.assignment_of(doc) == so.normalize_assignment(assignment, layout), \
        "render -> read must return the assignment"
    assert doc["STATE_DELTA"]["scope"] == "placeholder" and doc["STATE_DELTA"]["owner"] == "placeholder"
    assert [o["owner"] for o in doc["STATE_GAMMA"]["owners"]] == ["MID", "REI"], "a split lists its owners"
    assert so.to_json(doc) == so.to_json(so.read(layout, img, legend, placeholder, ids)), "byte-stable"
    # seam: border pixels do not vote, so 1 px or 2 px lines read back the same
    img1 = so.render(layout, owners, legend, border_width=1)
    assert so.assignment_of(so.read(layout, img1, legend, placeholder, ids)) == so.assignment_of(doc)

    def refuses(fn, frag):
        try:
            fn()
        except so.OwnershipError as exc:
            assert frag in str(exc), f"expected {frag!r} in {exc}"
        else:
            raise AssertionError(f"expected an OwnershipError containing {frag!r}")

    bad = img.copy()
    ys, xs = np.nonzero(layout.prov > 0)
    bad[ys[0], xs[0]] = (1, 2, 3)
    refuses(lambda: so.read(layout, bad, legend, placeholder, ids), "not in the legend")
    refuses(lambda: so.province_owners(layout, {"STATE_ALPHA": "REI"}, placeholder, legend), "no owner")
    refuses(lambda: so.province_owners(layout, {**assignment, "STATE_DELTA": "REI"}, placeholder, legend),
            "must not be assigned")
    refuses(lambda: so.province_owners(layout, {**assignment, "STATE_ALPHA": "ZZZ"}, placeholder, legend),
            "not a tag")
    # a drawn state painted with the placeholder colour is refused on read
    ph = img.copy()
    ph[layout.state_index == 1 + [s.key for s in states].index("STATE_ALPHA")] = legend.reserved["placeholder"]
    refuses(lambda: so.read(layout, ph, legend, placeholder, ids), "placeholder colour")
    # the committed legend is valid
    so.load_legend(TOOLS_DIR / "config" / "state_ownership_legend.json")
    return {"states": doc}


def _selfcheck_state_history(ownership_doc: dict) -> None:
    """Starting ownership as history script (#6372), on the golden assignment of
    :func:`_selfcheck_state_ownership` (ALPHA=REI, BETA unowned, GAMMA split
    REI/MID, DELTA placeholder): what is emitted (unowned and placeholder land
    go to c:UNO, #6391), byte stability, held-back undefined tags (UNO
    included), the CRLF-insensitive freshness compare, a 3-way split whose
    unowned slice goes to UNO, and the validator refusing hand-broken history text.
    """
    import copy

    from worldgen import state_history as sh
    from worldgen import state_ownership as so

    by_file = sh.load_states_by_file(EXPECTED_DIR / "state_regions")
    assert "99_seas.txt" not in by_file and sorted(by_file) == ["01_driftland.txt", "02_isle.txt", "03_mainland.txt"]
    land = {s.key: s for ss in by_file.values() for s in ss}
    tags = {"REI", "MID", "UNO"}

    p = sh.plan(ownership_doc, by_file, tags)
    creates = {k: c for e in p.files.values() for k, c in e}
    assert [t for t, _ in creates["STATE_ALPHA"]] == ["REI"], "a whole-state owner gets one create_state"
    assert creates["STATE_ALPHA"][0][1] == sorted(land["STATE_ALPHA"].provinces), \
        "a whole-state owner owns every province (impassable included)"
    assert [t for t, _ in creates["STATE_GAMMA"]] == ["MID", "REI"], "a split gets one create_state per owner"
    assert sorted(t for _, ps in creates["STATE_GAMMA"] for t in ps) == sorted(land["STATE_GAMMA"].provinces)
    assert creates["STATE_BETA"] == [("UNO", sorted(land["STATE_BETA"].provinces))], \
        "an unowned state goes wholly to c:UNO"
    assert creates["STATE_DELTA"] == [("UNO", sorted(land["STATE_DELTA"].provinces))], \
        "an out-of-scope placeholder state goes wholly to c:UNO"
    assert p.unowned == ["STATE_BETA"] and p.placeholder == ["STATE_DELTA"] and not p.held_back
    assert all(p.files.values()) and sh.render_file([]) == sh.HEADER, \
        "every golden file now carries a state; an empty file is header-only"
    texts = {f: sh.render_file(e) for f, e in p.files.items()}
    assert texts == {f: sh.render_file(e) for f, e in sh.plan(ownership_doc, by_file, tags).files.items()}, \
        "byte-stable"
    assert "\ts:STATE_ALPHA = {\n\t\tcreate_state = {\n\t\t\tcountry = c:REI\n" in texts["03_mainland.txt"], \
        "vanilla shape: tabs, s:/c: scopes"
    # freshness compare ignores a BOM and CRLF (core.autocrlf checkouts)
    crlf = "\ufeff" + texts["03_mainland.txt"].replace("\n", "\r\n")
    assert sh.normalize_text(crlf) == texts["03_mainland.txt"]
    # the emitted files validate clean; the parser round-trips them
    errs, held = sh.check(texts, ownership_doc, by_file, tags)
    assert errs == [] and held == [], errs
    assert sh.parse_history_text(crlf) == [(k, [(t, ps) for t, ps in c]) for k, c in p.files["03_mainland.txt"]]

    # an undefined tag is held back by the generator and reported by the validator
    hp = sh.plan(ownership_doc, by_file, {"REI", "UNO"})
    hcreates = {k: c for e in hp.files.values() for k, c in e}
    assert [t for t, _ in hcreates["STATE_GAMMA"]] == ["REI"] and hp.held_back == [("STATE_GAMMA", "MID")]
    htexts = {f: sh.render_file(e) for f, e in hp.files.items()}
    errs, held = sh.check(htexts, ownership_doc, by_file, {"REI", "UNO"})
    assert errs == [] and held == [("STATE_GAMMA", "MID")], (errs, held)
    # without a UNO definition the unowned / placeholder states are held back like any undefined owner
    np_ = sh.plan(ownership_doc, by_file, {"REI", "MID"})
    ncreates = {k: c for e in np_.files.values() for k, c in e}
    assert "STATE_BETA" not in ncreates and "STATE_DELTA" not in ncreates and np_.files["02_isle.txt"] == []
    assert sorted(np_.held_back) == [("STATE_BETA", "UNO"), ("STATE_DELTA", "UNO")], np_.held_back
    errs, held = sh.check({f: sh.render_file(e) for f, e in np_.files.items()}, ownership_doc, by_file, {"REI", "MID"})
    assert errs == [] and sorted(held) == [("STATE_BETA", "UNO"), ("STATE_DELTA", "UNO")], (errs, held)
    # D-tags are runtime slots, not start-date countries; a BOM'd first entry still counts
    assert sh.parse_country_tags(
        "\ufeffREI = {\n\tcolor = { 1 2 3 }\n}\n# QQQ = { }\nD00 = {\n\tdynamic_country_definition = yes\n}\n") == {"REI"}

    # 3-way split (defined + undefined + unowned): the defined slice is emitted, the
    # unowned slice becomes a c:UNO slice, the undefined one is held back
    alpha = sorted(land["STATE_ALPHA"].provinces)
    split_doc = copy.deepcopy(ownership_doc)
    split_doc["states"]["STATE_ALPHA"] = {
        "id": land["STATE_ALPHA"].id, "naming_anchor": None, "scope": "drawn",
        "owners": [{"owner": "REI", "provinces": alpha[:3]}, {"owner": "ZZZ", "provinces": alpha[3:5]},
                   {"owner": "unowned", "provinces": alpha[5:]}]}
    sp = sh.plan(split_doc, by_file, tags)
    screates = {k: c for e in sp.files.values() for k, c in e}
    assert screates["STATE_ALPHA"] == [("REI", alpha[:3]), ("UNO", alpha[5:])], screates["STATE_ALPHA"]
    assert sp.held_back == [("STATE_ALPHA", "ZZZ")] and sp.unowned == ["STATE_BETA"], "a slice is not an unowned state"
    stexts = {f: sh.render_file(e) for f, e in sp.files.items()}
    errs, held = sh.check(stexts, split_doc, by_file, tags)
    assert errs == [] and held == [("STATE_ALPHA", "ZZZ")], errs

    def refused(texts_: dict, frag: str, doc: dict = ownership_doc) -> None:
        e, _ = sh.check(texts_, doc, by_file, tags)
        assert any(frag in x for x in e), f"expected {frag!r} in {e}"

    main = texts["03_mainland.txt"]
    a0 = alpha[0]
    g0 = sorted(land["STATE_GAMMA"].provinces)[0]
    # province assigned twice (ALPHA's first province also listed under GAMMA)
    refused({**texts, "01_driftland.txt": texts["01_driftland.txt"].replace(
        f"owned_provinces = {{ {g0}", f"owned_provinces = {{ {a0} {g0}", 1)}, "not a province of the state")
    dup = main.replace(f"owned_provinces = {{ {a0}", f"owned_provinces = {{ {a0} {a0}", 1)
    refused({**texts, "03_mainland.txt": dup}, "assigned twice")
    # foreign province (a sea province) in owned_provinces
    refused({**texts, "03_mainland.txt": main.replace(a0, "xD35EE9", 1)}, "not a province of the state")
    # unknown c:TAG
    refused({**texts, "03_mainland.txt": main.replace("c:REI", "c:QQQ")}, "no (non-dynamic) common/country_definitions")
    # a state in the wrong NN_ file
    moved = sh.render_file(p.files["03_mainland.txt"])
    refused({"01_driftland.txt": texts["01_driftland.txt"], "02_isle.txt": moved,
             "03_mainland.txt": sh.render_file([])}, "belongs in 03_mainland.txt")
    # another owner on the placeholder state, or its c:UNO block dropped
    refused({**texts, "02_isle.txt": texts["02_isle.txt"].replace("c:UNO", "c:REI")}, "differ from state_ownership.json")
    refused({**texts, "02_isle.txt": sh.render_file([])}, "differ from state_ownership.json")
    # another owner on the unowned state, or its c:UNO block dropped
    un = sh.render_file([(k, c) if k != "STATE_BETA" else (k, [("REI", c[0][1])]) for k, c in p.files["03_mainland.txt"]])
    refused({**texts, "03_mainland.txt": un}, "differ from state_ownership.json")
    no_uno = sh.render_file([(k, c) for k, c in p.files["03_mainland.txt"] if k != "STATE_BETA"])
    refused({**texts, "03_mainland.txt": no_uno}, "differ from state_ownership.json")
    # a drawn state painted with the placeholder token is refused by plan() and check()
    ph_doc = copy.deepcopy(ownership_doc)
    ph_doc["states"]["STATE_ALPHA"]["owner"] = "placeholder"
    refused(texts, "drawn state owned by 'placeholder'", ph_doc)
    try:
        sh.plan(ph_doc, by_file, tags)
    except so.OwnershipError:
        pass
    else:
        raise AssertionError("plan() must refuse a drawn state owned by 'placeholder'")
    # emitted owner differs from the JSON (a repaint read but not regenerated)
    refused({**texts, "03_mainland.txt": main.replace("c:REI", "c:MID")}, "differ from state_ownership.json")
    # missing provinces (coverage) and a missing state entirely
    refused({**texts, "03_mainland.txt": main.replace(f"{a0} ", "", 1)}, "owned_provinces differ")
    refused({**texts, "03_mainland.txt": sh.render_file([])}, "differ from state_ownership.json")
    # a missing history file; a stale JSON (id mismatch)
    refused({k: v for k, v in texts.items() if k != "02_isle.txt"}, "02_isle.txt is missing")
    stale = copy.deepcopy(ownership_doc)
    stale["states"]["STATE_ALPHA"]["id"] = 999
    refused(texts, "map_data id", stale)
    try:
        sh.plan(stale, by_file, tags)
    except so.OwnershipError:
        pass
    else:
        raise AssertionError("plan() must refuse a JSON id that differs from map_data")

    # homelands (#6374): derived from the owners' cultures, UNO contributes none
    cc = {"REI": ["reiklander", "middenlander"], "MID": ["middenlander", "stirlander"], "UNO": ["wilderness"]}
    ids = {"reiklander", "middenlander", "stirlander", "wilderness"}
    assert sh.parse_country_cultures(
        "﻿REI = {\n\tcultures = { reiklander middenlander }\n}\n# QQQ = { cultures = { zz } }\n"
        "NOC = {\n\tcolor = { 1 2 3 }\n}\nD00 = {\n\tdynamic_country_definition = yes\n\tcultures = { zz }\n}\n"
    ) == {"REI": ["reiklander", "middenlander"], "NOC": []}, "tag cultures: ordered, comments/dynamic skipped"
    assert sh.parse_culture_ids(
        "﻿# c\nreiklander = {\n\tcolor = rgb{ 1 2 3 }\n\ttraditions = { }\n}\nstirlander = {\n\tobsessions = { }\n}\n"
    ) == {"reiklander", "stirlander"}, "culture ids: top-level keys only"
    hp2 = sh.plan(ownership_doc, by_file, tags, cc)
    assert hp2.homelands == {"STATE_ALPHA": ["reiklander", "middenlander"],
                             "STATE_GAMMA": ["middenlander", "stirlander", "reiklander"]}, hp2.homelands
    assert sh.plan(ownership_doc, by_file, tags).homelands == {}, "no cultures supplied, no homelands"
    assert {f: sh.render_file(e) for f, e in hp2.files.items()} == texts, "render without homelands is unchanged"
    htx = {f: sh.render_file(e, hp2.homelands) for f, e in hp2.files.items()}
    assert ("\t\t}\n\n\t\tadd_homeland = cu:reiklander\n\t\tadd_homeland = cu:middenlander\n\t}\n"
            in htx["03_mainland.txt"]), "vanilla shape: blank line, then one add_homeland per culture"
    assert sh.parse_homelands("\ufeff" + htx["03_mainland.txt"].replace("\n", "\r\n")) == {
        k: hp2.homelands[k] for k, _ in hp2.files["03_mainland.txt"] if k in hp2.homelands}
    assert sh.check(htx, ownership_doc, by_file, tags, cc, ids) == ([], []), "homelands validate clean"
    assert sh.check(texts, ownership_doc, by_file, tags) == ([], []), "no culture args: homelands not checked"
    # UNO's states (BETA unowned, DELTA placeholder) get a create_state but no homeland
    hcreates2 = {k for e in hp2.files.values() for k, _ in e}
    assert {"STATE_BETA", "STATE_DELTA"} <= hcreates2 and not {"STATE_BETA", "STATE_DELTA"} & set(hp2.homelands)

    def refused_h(texts_: dict, frag: str, cult: dict = cc, cids: set = ids) -> None:
        e, _ = sh.check(texts_, ownership_doc, by_file, tags, cult, cids)
        assert any(frag in x for x in e), f"expected {frag!r} in {e}"

    m2 = htx["03_mainland.txt"]
    refused_h({**htx, "03_mainland.txt": m2.replace("cu:reiklander", "cu:nonesuch")}, "has no common/cultures definition")
    refused_h({**htx, "03_mainland.txt": m2.replace("\t\tadd_homeland = cu:reiklander\n", "")}, "differs from the")
    refused_h({**htx, "03_mainland.txt": m2.replace("\t\tadd_homeland = cu:middenlander\n", "", 1)}, "differs from the")
    refused_h(texts, "differs from the")                       # homelands never emitted
    refused_h(htx, "owned state gets no homeland", {**cc, "REI": []})
    # a homeland on UNO's state is refused (UNO gives none, though it has a culture)
    uno_home = sh.render_file(hp2.files["03_mainland.txt"], {**hp2.homelands, "STATE_BETA": ["wilderness"]})
    refused_h({**htx, "03_mainland.txt": uno_home}, "whose owner(s) give no homelands")
    stray = sh.render_file([e for e in hp2.files["03_mainland.txt"] if e[0] != "STATE_BETA"] + [("STATE_BETA", [])],
                           {**hp2.homelands, "STATE_BETA": ["reiklander"]})
    refused_h({**htx, "03_mainland.txt": stray}, "without a create_state")


def _selfcheck_country_history(ownership_doc: dict) -> None:
    """Starting country setup (#6375), on the golden assignment of
    :func:`_selfcheck_state_ownership` (owners REI and MID, plus UNO for the
    unowned / placeholder states, #6391): tier -> technology effect, byte
    stability, the CRLF-insensitive compare, held-back undefined tags, an
    unmapped tier, and the validator refusing hand-broken text.
    """
    from worldgen import country_history as ch
    from worldgen import state_ownership as so

    tiers = {"REI": "grand_principality", "MID": "city_state", "UNO": "principality"}
    effects = {"effect_starting_technology_tier_5_tech", "effect_starting_technology_tier_6_tech",
               "effect_starting_politics_traditional"}
    p = ch.plan(ownership_doc, tiers)
    assert p.blocks == [("MID", ["effect_starting_technology_tier_6_tech", ch.POLITICS_EFFECT]),
                        ("REI", ["effect_starting_technology_tier_5_tech", ch.POLITICS_EFFECT]),
                        ("UNO", ["effect_starting_technology_tier_6_tech", ch.POLITICS_EFFECT])] \
        and not p.held_back, "one block per owner (UNO included), sorted, tier -> technology effect"
    # UNO is an owner only while some state or slice is unowned / placeholder
    states = ownership_doc["states"]
    assert ch.owner_tags(ownership_doc) == {"REI", "MID", "UNO"}
    assert ch.owner_tags({"states": {k: v for k, v in states.items() if k not in ("STATE_BETA", "STATE_DELTA")}}) \
        == {"REI", "MID"}, "no unowned / placeholder token, no UNO"
    assert ch.owner_tags({"states": {"STATE_DELTA": states["STATE_DELTA"]}}) == {"UNO"}
    assert ch.owner_tags({"states": {"STATE_BETA": states["STATE_BETA"]}}) == {"UNO"}
    names = {"REI": "Reikland", "MID": "Middenland: the Wolf"}
    texts = ch.render(p.blocks, names)
    assert texts == ch.render(ch.plan(ownership_doc, tiers).blocks, names), "byte-stable"
    assert sorted(texts) == ["mid - middenland the wolf.txt", "rei - reikland.txt", "uno.txt"], "one file per tag, vanilla's layout"
    text = texts["rei - reikland.txt"]
    assert "\tc:REI ?= {\n\t\teffect_starting_technology_tier_5_tech = yes\n" in text, \
        "vanilla shape: tabs, c: scope, ?="
    assert "c:MID" not in text, "one block per file"
    crlf = {n: "\ufeff" + t.replace("\n", "\r\n") for n, t in texts.items()}
    errs, held = ch.check(crlf, ownership_doc, tiers, effects, names)
    assert errs == [] and held == [], errs
    assert ch.parse_history_text(crlf["rei - reikland.txt"]) == [p.blocks[1]]
    assert ch.parse_country_tiers("\ufeffREI = {\n\ttier = kingdom\n}\nXXX = {\n}\n"
                                  "D00 = {\n\tdynamic_country_definition = yes\n}\n") == {"REI": "kingdom", "XXX": None}

    # an undefined owner is held back (no block) and reported
    hp = ch.plan(ownership_doc, {"REI": "kingdom"})
    assert [t for t, _ in hp.blocks] == ["REI"] and hp.held_back == ["MID", "UNO"], hp.held_back
    # a defined owner whose tier has no technology mapping is an error, never a default
    for bad in ({"REI": "kingdom", "MID": None}, {"REI": "kingdom", "MID": "duchy"}):
        try:
            ch.plan(ownership_doc, bad)
        except so.OwnershipError:
            pass
        else:
            raise AssertionError("plan() must refuse a tier with no starting-technology mapping")

    def refused(texts_: dict | None, frag: str, tiers_: dict = tiers, effects_: set = effects) -> None:
        e, _ = ch.check(texts_, ownership_doc, tiers_, effects_, names)
        assert any(frag in x for x in e), f"expected {frag!r} in {e}"

    def swap(name: str, fn) -> dict:
        return {**texts, name: fn(texts[name])}

    refused({}, "has no files")
    refused({n: t for n, t in texts.items() if n != "rei - reikland.txt"}, "owns a state but has no country history block")
    refused({**texts, "mid.txt": texts["rei - reikland.txt"]}, "lives in mid.txt, expected one block per file in rei - reikland.txt")
    refused({**texts, "00_start_setup.txt": texts["mid - middenland the wolf.txt"]}, "appears 2 times")
    refused(swap("mid - middenland the wolf.txt", lambda t: t.replace("c:MID", "c:QQQ")), "no (non-dynamic) common/country_definitions")
    refused(swap("mid - middenland the wolf.txt", lambda t: t.replace("tier_6_tech", "tier_9_tech")), "not a scripted effect")
    refused(texts, "not a scripted effect", effects_=effects - {ch.POLITICS_EFFECT})
    refused(swap("mid - middenland the wolf.txt", lambda t: t.replace("tier_6_tech", "tier_5_tech")), "differs from what the generator emits")
    refused({**texts, "zzz.txt": ch.render_file("ZZZ", [ch.POLITICS_EFFECT])},
            "has a country history block but owns no state", {**tiers, "ZZZ": "kingdom"})


COUNTRY_HISTORY_DIR = TOOLS_DIR / "fixtures" / "country_history"
COUNTRY_HISTORY_EXPECTED = COUNTRY_HISTORY_DIR / "expected" / "report.txt"

#: Every error class the country-history linter must still report on the broken fixture
#: files; ``--update`` cannot silently drop one by regenerating the golden report.
COUNTRY_HISTORY_NEEDLES = (
    "duplicate key", "baseline missing", "unknown tech_tier", "ruling_igs must be", "missing law group",
    "not in the tag registry", "is a formable", "registry places it in", "start tag has no entry",
    "more than one law for", "unknown law group", "unknown law ", "unknown tech ", "unknown interest group",
    "unknown tax_level", "unknown good", "unknown institution", "is locked: needs tech",
    "is locked: needs law", "extra tech currency_standards needs", "is disallowed alongside",
    "possible trigger", "next_election", "laws hold elections", "needs justify.", "has no matching override",
    "repeats the baseline", "unknown field", "unknown profile", "confidence must be",
)


def _country_history_run(files=None):
    import validate_country_history as vch

    return vch.run(COUNTRY_HISTORY_DIR / "game", COUNTRY_HISTORY_DIR / "data",
                   COUNTRY_HISTORY_DIR / "registry.md", files)


def _write_country_history_golden() -> None:
    COUNTRY_HISTORY_EXPECTED.parent.mkdir(parents=True, exist_ok=True)
    COUNTRY_HISTORY_EXPECTED.write_text(_country_history_run()[1], encoding="utf-8", newline="\n")
    print(f"wrote country-history golden report to {COUNTRY_HISTORY_EXPECTED}")


def check_country_history() -> int:
    """The starting-country data linter: golden report, determinism, every error class fires."""
    code, report = _country_history_run()
    code2, report2 = _country_history_run()
    if (code, report) != (code2, report2):
        print("country_history: validator output differs between two runs (non-deterministic).", file=sys.stderr)
        return 1
    if code != 1:
        print("country_history: the broken fixture region files were accepted.", file=sys.stderr)
        return 1
    missing = [n for n in COUNTRY_HISTORY_NEEDLES if n not in report]
    if missing:
        print(f"country_history: error class(es) no longer reported: {missing}", file=sys.stderr)
        return 1
    if "not fully evaluable" not in report:
        print("country_history: the unresolved-government warning disappeared.", file=sys.stderr)
        return 1
    good_code, good_report = _country_history_run(["00_test.json"])
    if good_code != 0 or "OK 00_test.json: 3 tag(s)" not in good_report:
        print("country_history: the valid fixture region file was rejected:\n" + good_report, file=sys.stderr)
        return 1
    expected = COUNTRY_HISTORY_EXPECTED.read_text(encoding="utf-8")
    if report != expected:
        import difflib

        print("country_history: report differs from the golden copy:", file=sys.stderr)
        sys.stderr.writelines(difflib.unified_diff(expected.splitlines(True), report.splitlines(True),
                                                   "expected/report.txt", "regenerated"))
        return 1
    print("country_history: laws/techs/government-trigger linter (unknown ids, group cardinality, locked and "
          "disallowed laws, formable/registry rules, justification bookkeeping, profiles, determinism) "
          "matches the golden report.")
    return 0


def _selfcheck_pop_history() -> None:
    """Starting pops (#6375): golden output, determinism, exact sums, a split state, a skipped owner and
    culture, a religion override, a dropped sub-minimum pop, and the hard-error refusals, on
    ``mapgen/fixtures/pop_history/``."""
    import generate_pop_history

    generate_pop_history.run_fixture_check(TOOLS_DIR / "fixtures" / "pop_history")


def _selfcheck_building_history() -> None:
    """Starting buildings: golden output, determinism, the tech gate (a railway for a tag without
    ``railways`` is a hard error, a tech-locked method is never chosen, an unresolvable tech set gets
    tech-free buildings only), the other hard errors and the independent verifier catching hand-broken
    output, on ``mapgen/fixtures/building_history/``."""
    import generate_building_history

    generate_building_history.run_fixture_check(TOOLS_DIR / "fixtures" / "building_history")


def _selfcheck_smooth_cr_borders() -> None:
    """smooth_cr_borders: a stair-stepped two-state boundary on a synthetic island is smoothed
    deterministically, keeps its states, ends on the coast and still seals every state."""
    import numpy as np
    from scipy import ndimage

    import smooth_cr_borders as sm

    h, w = 60, 120
    land = np.zeros((h, w), dtype=bool)
    land[10:50, 10:110] = True
    box = np.zeros_like(land)
    box[5:55, 5:115] = True
    yy, xx = np.mgrid[0:h, 0:w]
    lab = np.where(land, np.where(xx < 60 + ((yy // 3) % 2) * 3, 1, 2), 0).astype(np.int32)
    lines = sm.cr_partition.lines_from_labels(lab, land)
    new, _, labels, scope, _ = sm.smooth_lines(lines, land, box, 4.0)
    again = sm.smooth_lines(lines, land, box, 4.0)[0]
    assert np.array_equal(new, again), "smooth_cr_borders: not deterministic"
    assert len([v for v in np.unique(labels) if v > 0]) == 2, "smooth_cr_borders: state count changed"
    assert not (new & ~land).any(), "smooth_cr_borders: a line left the land"
    ys = np.nonzero(new)[0]
    assert ys.min() <= 11 and ys.max() >= 48, "smooth_cr_borders: a border no longer reaches the coast"
    comp, n = ndimage.label(land & ~new)
    assert n == 2, f"smooth_cr_borders: lines no longer separate the two states ({n} pieces)"
    assert np.nonzero(new)[1].std() < np.nonzero(lines)[1].std() or         len(np.unique(np.nonzero(new)[1])) < len(np.unique(np.nonzero(lines)[1])),         "smooth_cr_borders: the border was not smoothed"


def run_check() -> int:
    # Stdlib-only and independent of the map goldens, so it runs (and can fail) first.
    rc = check_country_history()
    if rc != 0:
        return rc
    ownership_doc = _selfcheck_state_ownership()
    print("state_ownership: render -> read round-trip (whole + split + placeholder states, seam, refusals, "
          "byte-stable JSON, committed legend) self-check passed.")
    _selfcheck_state_history(ownership_doc)
    print("state_history: create_state emission (whole + split, unowned + placeholder -> c:UNO, held-back "
          "tag incl. UNO, 3-way split with a UNO slice, CRLF compare, hand-broken history refusals incl. a "
          "dropped or replaced c:UNO) and add_homeland derivation (owner cultures, UNO skip, unknown-culture "
          "refusal) self-check passed.")
    _selfcheck_country_history(ownership_doc)
    print("country_history: tier -> starting-technology blocks (UNO from the unowned/placeholder tokens, "
          "held-back tags, unmapped tier, CRLF compare, hand-broken history refusals) self-check passed.")
    _selfcheck_pop_history()
    print("pop_history: pops/population emission (split state, skipped owner + culture, religion override, "
          "exact-sum rounding, dropped small pop, UNO's fixed unclaimed pop, created pair without pops, "
          "hard errors) self-check passed.")
    _selfcheck_building_history()
    print("building_history: tech-gated building emission (railway without the tech refused, locked method "
          "never chosen, unresolved tech set -> tech-free only, resource/anchor/id/job-cap errors, "
          "independent verifier on hand-broken output and changed country history) self-check passed.")
    _selfcheck_smooth_cr_borders()
    print("smooth_cr_borders: deterministic label-field smoothing keeps states, coast ends and the seal "
          "self-check passed.")
    _selfcheck_wrap()
    _selfcheck_frame()
    print("frame: Miller round-trip + uniform-grid guard self-check passed.")
    _selfcheck_piecewise_affine()
    print("reproject: piecewise-affine warp (exact dots, local scale, no-tear continuity, "
          "outside-hull sentinel, determinism, schema) self-check passed.")
    _selfcheck_composite()
    print("composite: precedence + tie-rejection self-check passed.")
    _selfcheck_cells()
    print("cells: wrap-aware components + nearest-label fill self-check passed.")
    _selfcheck_mask_component_sizes()
    print("raster: vectorized mask_component_sizes matches the pixel-set BFS self-check passed.")
    _selfcheck_segment_lakes()
    print("segment: enclosed-water keep (ocean + seeded lakes) self-check passed.")
    _selfcheck_rivers()
    print("rivers: rasterize + topology-validation self-check passed.")
    _selfcheck_river_extraction()
    print("river_network: drawn-blue extraction (Strahler stems, endorheic sink, "
          "lake-fed source, delta + river-island splits, sourceless-ring rejected, "
          "spur pruned, wrap stem) self-check passed.")
    _selfcheck_river_validator()
    print("validate_map: rivers check (on-land, sea-mouth-touches-water, in-set indices, "
          "negative cases) self-check passed.")
    _selfcheck_marker()
    print("marker: border-markup extraction (rivers in, roads ignored) self-check passed.")
    _selfcheck_reseed_dots()
    print("reseed_dots: paired-anchor-dot fold (chroma detect + noisy-rect rule, select_new "
          "skips known, colour pairing + mismatch rejected, c_<hex> naming, determinism) "
          "self-check passed.")
    _selfcheck_parse_layers()
    print("project_regions_unified: --colors -> ora-layer resolution (names/#hex, dedup, "
          "refusals) self-check passed.")
    _selfcheck_composite_layers_over()
    print("project_regions_unified: layer compositing (single pass-through, opaque replace, "
          "partial over, determinism, empty refused) self-check passed.")
    _selfcheck_sea_zones()
    print("sea_zones: drawn-line extraction (in-water splits, land marks ignored) self-check passed.")
    _selfcheck_land_provinces()
    print("land_provinces: drawn-region cut (barrier-respecting subdivision, placeholder whole) "
          "self-check passed.")
    _selfcheck_province_merges()
    print("land_provinces: tiny-island override merge (line -> zone -> forced single "
          "province) self-check passed.")
    _selfcheck_merge_fused()
    _selfcheck_island_zone_groups()
    print("land_provinces: state chained across island lines (one province per line-group, single group/no layer stays whole, deterministic) self-check passed.")
    print("land_provinces: merge-fused disconnected region cut per piece "
          "(archipelago kept whole via keep_whole) self-check passed.")
    _selfcheck_drop_land_specks()
    print("coastline_mask: land-speck drop (sub-floor components -> water, real island "
          "kept, exclusive floor, wrap-aware, no-op guard) self-check passed.")
    _selfcheck_lakes()
    _selfcheck_world_market_location()
    print("lakes: classify/label/assemble + sea_zones exclude + three-way validate + "
          "stateless checks + default.map lakes block + non-blocking oversized/junk-lake "
          "warnings self-check passed.")
    _selfcheck_seeded_cut()
    _selfcheck_impassable_land()
    _selfcheck_city_blobs()
    _selfcheck_city_seeds()
    print("land_provinces: hub-anchor seeded cut (own-province seeds, boundary kept, "
          "unseeded byte-identical, protected pieces, hard errors) self-check passed.")
    _selfcheck_hub_validator()
    print("validate_map: hub-anchor check (own-state hub, port coastal, HUB_NAME loc, "
          "stale-index detection, passable-only sharing rule) self-check passed.")
    _selfcheck_hub_stack()
    _selfcheck_adjacencies()
    print("adjacencies: line extraction (straight/bent/seam ok; T/loop/dot/touching/ambiguous/"
          "same-province skipped, pins), worksheet matching (tolerance, one-to-one, stale), "
          "bottom-origin sorted byte-identical CSV, schema + validator negative cases "
          "self-check passed.")
    _selfcheck_canal_junctions()
    print("canal junctions (#5744): '+'/'X' sea+land split, plateau collapse, touching-skip "
          "exemption, 3-leaf/no-valid-pairing/same-colour/lake skips, worksheet identity "
          "across a redraw via land_points self-check passed.")
    _selfcheck_stack_hubs()
    print("statefile: hub-stacking fallback (single/few-province stacking, cycling, port "
          "preference) self-check passed.")
    _selfcheck_economics()
    print("land_economics: worksheet loader (full/partial/empty rows, permuted header, BOM/CRLF, "
          "refuse unknown column/dup/negative/non-integer/lowercase key/missing identity/comma ids) "
          "+ per-column fallback + check_economics (catalog ids, rural, fishing-village-needs-port, "
          "<10 warning) + byte-identical emission + identity/rekey + catalog loader + determinism "
          "self-check passed.")
    _selfcheck_economics_validator()
    print("validate_map economics: fishing-village-needs-port, placeholder-stays-default, missing "
          "field, <10 warning (non-blocking), worksheet disagreement/anchor/dead-row/placeholder-row "
          "errors + block parser self-check passed.")
    _selfcheck_province_terrains()
    print("province_terrains: generator (plains/ocean, id-sorted, deterministic) + validator "
          "(bijection, valid ids, negative cases) self-check passed.")
    _selfcheck_canon_cities()
    print("canon_cities: schema (order + refuse empty/bad-terrain/dup-anchor/oob) + pure "
          "transparent overlay (deterministic, canvas-sized) + validator (on-land hard error, "
          "impassable-collision non-blocking warning, export-absent skip) self-check passed.")
    _selfcheck_climate()
    print("climate: stroke reader (red/cyan, land and sea fill ignored) + core on a synthetic canvas "
          "(uint8 grid in range, polar land is tundra/ice, array-equal across runs) + per-state shares "
          "(sum to 1, ties to lowest id, empty -> none) + class-map loader and clim_* columns "
          "(clean skip, unknown class refused, highland never flagged) self-check passed.")
    _selfcheck_cr_partition()
    print("cr partition: lookup decode (top-down rows kept, wrong length refused) + dot-free placement "
          "(known affine recovered, exact at landmarks, affine far from them, deterministic) + fill, snap "
          "(crossing followed, mid-band end left alone), closing lines sealed through the generator's "
          "region stage, seam crop and provenance + mainland path (8-connected cuts block a flood, "
          "cut-closed scope with island list and frame rows and its refusals, landmark affine "
          "exact and refused below 4, leave-one-out flags the inconsistent point, coast agreement, "
          "high-ground edges, terrain split on a river, cut-closed round trip) self-check passed.")
    _selfcheck_arable()
    print("arable: field core (water/lake/impassable=0, climate peak/arid-trough/pole-taper, "
          "terrain suppression, river+coast boost, lore lift/suppress + smooth falloff + "
          "multiplicative compose, percentile-norm spread + outlier-clip) + schema (order + "
          "refuse empty/oob/bad-radius/kind-factor-mismatch/dup) + determinism (array-equal "
          "core, byte-identical PNG) self-check passed.")
    _selfcheck_tww3_names()
    print("tww3_names: region-table parser (metadata/blank rows skipped, order + row count, "
          "case-normalised colours, refuse dup-colour/malformed/blank/truncated/bad-header, "
          "black excluded from the index and returned by the water bank) + exact-hex "
          "sampling + citation format + row-drop agreement with #4364 + the #4414 "
          "text-crop scale/frame agreement, drift test and report-shape detector "
          "self-check passed.")
    _selfcheck_stable_ids()
    print("province_ids: stable colour+id across regens (no-op kept, remove retires, split "
          "keeps dominant + fresh piece, no sea/lake ripple, reassign fresh, order-invariant) "
          "self-check passed.")
    _selfcheck_sea_naming()
    print("sea_naming: canon plurality assignment + ordinal + override + zero-zone warning "
          "self-check passed.")
    _selfcheck_sea_state_ids()
    print("sea_state_ids: stable sea-zone STATE id+key across regens (no-op kept, remove "
          "retires, retired id never reused, new zone at high-water, rename re-derives key, "
          "merge keeps id+shared key, reassign/no-baseline bootstrap, order-invariant, "
          "zero-overlap safety net, fresh multi-zone slug numbered, digit-suffix slug) "
          "self-check passed.")
    _selfcheck_land_state_numbers()
    print("land_state_numbering: stable STATE-number assignment across regens (no-op kept, "
          "remove retires, split keeps dominant + fresh piece, merge keeps larger overlap, "
          "reassign/no-index bootstrap, order-invariant, zero-match safety net) + "
          "seed_land_state_ids parser self-check passed.")
    _selfcheck_alpha_zero()
    print("alpha 0: shared image readers zero the colour under every alpha-0 pixel, and no script "
          "outside the opaque-output allowlist calls convert('RGB') self-check passed.")
    _selfcheck_ora_reader()
    print("sources: .ora layer reader (name lookup, offset/clip composite, hidden layers, "
          "missing/duplicate-name and empty-layer refusals, malformed-archive errors, "
          "split_ref, image_dims, manifest SHA-256 guard, source_layers.json refusals + "
          "verify() step 4, flat-file alpha-0 zeroing, determinism) self-check passed.")
    world = schema.load_world(WORLD_DIR)
    width, height = FIXTURE_CANVAS

    with tempfile.TemporaryDirectory(prefix="wh_fixture_") as tmp:
        run1 = Path(tmp) / "run1"
        run2 = Path(tmp) / "run2"
        build_map(world, run1, width, height, map_config.WRAP_X, map_config.SEED)
        build_map(world, run2, width, height, map_config.WRAP_X, map_config.SEED)

        det = _diff(_snapshot(run1), _snapshot(run2))
        if det:
            print("DETERMINISM FAILURE — two runs differ:", file=sys.stderr)
            for p in det:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print("determinism: two runs are byte-identical.")

        if not EXPECTED_DIR.is_dir():
            print(f"no golden outputs at {EXPECTED_DIR}; run --update first.", file=sys.stderr)
            return 1
        reg = _diff(_snapshot(run1), _snapshot(EXPECTED_DIR))
        if reg:
            print("REGRESSION — output differs from committed golden:", file=sys.stderr)
            for p in reg:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print("regression: output matches committed golden outputs.")

    # Validate the committed golden outputs with the linter.
    import validate_map

    errors = validate_map.validate(
        provinces_path=EXPECTED_DIR / "provinces.png",
        state_regions_dir=EXPECTED_DIR / "state_regions",
        default_map_path=EXPECTED_DIR / "default.map",
        loc_dir=EXPECTED_DIR / "loc",
        min_province_area=4,
        wrap_x=map_config.WRAP_X,
    )
    if errors:
        print(f"validate_map: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("validate_map: all checks passed.")

    print()
    rc = check_ingest()
    if rc != 0:
        return rc

    print()
    rc = check_boundary()
    if rc != 0:
        return rc

    print("\nFIXTURE OK.")
    return 0


def run_update() -> int:
    _selfcheck_wrap()
    _selfcheck_composite()
    _selfcheck_cells()
    _selfcheck_rivers()
    world = schema.load_world(WORLD_DIR)
    width, height = FIXTURE_CANVAS
    if EXPECTED_DIR.exists():
        shutil.rmtree(EXPECTED_DIR)
    build_map(world, EXPECTED_DIR, width, height, map_config.WRAP_X, map_config.SEED)
    print(f"wrote golden outputs to {EXPECTED_DIR}")

    if INGEST_EXPECTED.exists():
        shutil.rmtree(INGEST_EXPECTED)
    build_ingest(INGEST_EXPECTED)
    print(f"wrote ingest golden outputs to {INGEST_EXPECTED}")

    if BOUNDARY_EXPECTED.exists():
        shutil.rmtree(BOUNDARY_EXPECTED)
    build_boundary(BOUNDARY_EXPECTED)
    print(f"wrote boundary golden outputs to {BOUNDARY_EXPECTED}")

    _write_country_history_golden()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="regenerate, diff golden, run twice, validate")
    group.add_argument("--update", action="store_true", help="(re)write the golden outputs")
    group.add_argument("--update-fixture-manifest", action="store_true",
                       help="refresh the ingestion fixture's SHA-256 manifest (after make_source.py)")
    group.add_argument("--update-country-history", action="store_true",
                       help="rewrite only the country-history linter's golden report")
    args = parser.parse_args(argv)
    if args.update_country_history:
        _write_country_history_golden()
        return 0
    if args.update_fixture_manifest:
        _update_fixture_manifest(INGEST_MANIFEST, INGEST_DIR)
        _update_fixture_manifest(BOUNDARY_MANIFEST, BOUNDARY_DIR)
        return 0
    return run_update() if args.update else run_check()


if __name__ == "__main__":
    raise SystemExit(main())
