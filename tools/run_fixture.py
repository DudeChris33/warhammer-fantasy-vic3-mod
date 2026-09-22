#!/usr/bin/env python3
"""End-to-end fixture pipeline: prove the whole code path offline.

Runs the full generator path on the tiny synthetic world in
``tools/fixtures/world/`` — schema load -> land/sea partition -> province
subdivision stub -> state-file text -> default.map + localization -> validators —
with **zero game dependency**, and regression-checks the output against the
committed golden copies in ``tools/fixtures/expected/`` byte-for-byte.

The subdivision here is the P1 *stub*: a seeded, wrap-aware Voronoi split with
connectivity repair and a small-cell merge. P3 replaces it with the full-scale
``generate_provinces.py`` / ``generate_state_regions.py`` reusing the same
``worldgen`` primitives.

Usage::

    python tools/run_fixture.py --check     # regenerate to temp, diff golden, run twice, validate
    python tools/run_fixture.py --update     # (re)write the golden outputs in expected/

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
                            registration_dir=INGEST_REG_DIR)
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
                            registration_dir=BOUNDARY_REG_DIR)
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


def _selfcheck_island_overrides() -> None:
    """Tiny-island override merge (worldgen.land_provinces), in isolation.

    Pins the properties generate_provinces.py relies on: island_override_zones
    reads a merge-line network's connected components as distinct zone ids
    (board #4609 — a line directly connecting islands, superseding an earlier
    enclosing-ring idiom that needed a geometric splitter for touching rings
    and never reliably got it right for every shape) and a blank source as no
    zones at all; merge_island_overrides unions every region caught under the
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
    assert not lp.island_override_zones(blank, land, wrap_x=False).any(), \
        "a blank source must draw no zones"

    # A line directly connecting the two islets puts them in the same zone.
    overrides = np.full((H, W, 3), 255, dtype=np.uint8)
    overrides[1, 30:35] = (255, 0, 0)
    zones = lp.island_override_zones(overrides, land, wrap_x=False)
    assert int(zones.max()) == 1, f"one connecting line must be one zone, got {zones.max()}"
    assert zones[1, 30] == 1 and zones[1, 34] == 1, \
        "both islets must fall on the connecting line's zone"

    # A line drawn far from every islet and the mainland leaves them all at
    # zone 0 — "no forced merge here" — rather than silently roping one in.
    near_miss = np.full((H, W, 3), 255, dtype=np.uint8)
    near_miss[15, 25:30] = (255, 0, 0)  # clear of both islets (row 1) and the mainland (cols 2-18)
    nz = lp.island_override_zones(near_miss, land, wrap_x=False)
    assert nz[1, 30] == 0 and nz[1, 34] == 0, \
        "an unconnected line must not merge an islet it never touches"

    # Two separate line networks (not connected to each other) get distinct
    # zone ids; determinism holds across two runs.
    two_lines = np.full((H, W, 3), 255, dtype=np.uint8)
    two_lines[1, 30:32] = (255, 0, 0)          # touches islet A only
    two_lines[10, 2:5] = (255, 0, 0)           # touches the mainland only, far from islet A's line
    tz = lp.island_override_zones(two_lines, land, wrap_x=False)
    assert tz[1, 30] != 0 and tz[10, 2] != 0 and tz[1, 30] != tz[10, 2], \
        "two disconnected merge-line networks must keep distinct zones"
    tz2 = lp.island_override_zones(two_lines, land, wrap_x=False)
    assert np.array_equal(tz, tz2), "two runs must be byte-identical"

    reg = lp.regions(land, drawn, dilate=1, merge_floor=1, wrap_x=False)
    assert int(reg.max()) == 3, f"main landmass + 2 islets = 3, got {reg.max()}"
    islet_a, islet_b = int(reg[1, 30]), int(reg[1, 34])
    assert islet_a != islet_b, "the two islets must start as separate regions"

    merged = lp.merge_island_overrides(reg, land, zones, wrap_x=False)
    assert int((merged == 0).sum()) == int((~land).sum()), "the merge must still tile the land exactly"
    assert merged[1, 30] == merged[1, 34], "both islets must end up under one region id"
    m2 = lp.merge_island_overrides(reg, land, zones, wrap_x=False)
    assert np.array_equal(merged, m2), "two runs must be byte-identical"

    # A circle drawn over a single region is a no-op.
    single = np.zeros((H, W), dtype=np.int32)
    single[1, 30] = 1
    unchanged = lp.merge_island_overrides(reg, land, single, wrap_x=False)
    assert np.array_equal(unchanged, reg), "a circle over one region must change nothing"

    # regions() applies the override itself when given island_overrides=.
    reg_direct = lp.regions(land, drawn, dilate=1, merge_floor=1, wrap_x=False,
                            island_overrides=zones)
    assert reg_direct[1, 30] == reg_direct[1, 34], \
        "regions() must apply island_overrides internally"

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
    # source (island_overrides=None ⟹ empty set in a bare local run).
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

    Pins the #3664 fix: a drawn region that ``apply_land_region_merges`` fused
    across water (two non-touching landmasses under one label) is cut **per
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

    # Fuse the two regions across the water (a judgement-call merge). anchors (x, y).
    merges = [schema.LandRegionMerge(anchor_a=(5, 10), anchor_b=(17, 10), note="test")]
    reg_m = lp.apply_land_region_merges(reg, merges)
    assert int(reg_m.max()) == 1, f"the merge must union both blocks into one label, got {reg_m.max()}"
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
    lookup bitmap live under the gitignored, third-party
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
    a beyond-tolerance mismatch rejected as unpaired), ``name_pairs``
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


def run_check() -> int:
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
    _selfcheck_sea_zones()
    print("sea_zones: drawn-line extraction (in-water splits, land marks ignored) self-check passed.")
    _selfcheck_land_provinces()
    print("land_provinces: drawn-region cut (barrier-respecting subdivision, placeholder whole) "
          "self-check passed.")
    _selfcheck_island_overrides()
    print("land_provinces: tiny-island override merge (line -> zone -> forced single "
          "province) self-check passed.")
    _selfcheck_merge_fused()
    print("land_provinces: merge-fused disconnected region cut per piece "
          "(archipelago kept whole via keep_whole) self-check passed.")
    _selfcheck_drop_land_specks()
    print("coastline_mask: land-speck drop (sub-floor components -> water, real island "
          "kept, exclusive floor, wrap-aware, no-op guard) self-check passed.")
    _selfcheck_lakes()
    print("lakes: classify/label/assemble + sea_zones exclude + three-way validate + "
          "stateless checks + default.map lakes block + non-blocking oversized/junk-lake "
          "warnings self-check passed.")
    _selfcheck_seeded_cut()
    print("land_provinces: hub-anchor seeded cut (own-province seeds, boundary kept, "
          "unseeded byte-identical, protected pieces, hard errors) self-check passed.")
    _selfcheck_hub_validator()
    print("validate_map: hub-anchor check (own-state hub, port coastal, HUB_NAME loc, "
          "stale-index detection) self-check passed.")
    _selfcheck_stack_hubs()
    print("statefile: hub-stacking fallback (single/few-province stacking, cycling, port "
          "preference) self-check passed.")
    _selfcheck_province_terrains()
    print("province_terrains: generator (plains/ocean, id-sorted, deterministic) + validator "
          "(bijection, valid ids, negative cases) self-check passed.")
    _selfcheck_canon_cities()
    print("canon_cities: schema (order + refuse empty/bad-terrain/dup-anchor/oob) + pure "
          "transparent overlay (deterministic, canvas-sized) + validator (on-land hard error, "
          "impassable-collision non-blocking warning, export-absent skip) self-check passed.")
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
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="regenerate, diff golden, run twice, validate")
    group.add_argument("--update", action="store_true", help="(re)write the golden outputs")
    group.add_argument("--update-fixture-manifest", action="store_true",
                       help="refresh the ingestion fixture's SHA-256 manifest (after make_source.py)")
    args = parser.parse_args(argv)
    if args.update_fixture_manifest:
        _update_fixture_manifest(INGEST_MANIFEST, INGEST_DIR)
        _update_fixture_manifest(BOUNDARY_MANIFEST, BOUNDARY_DIR)
        return 0
    return run_update() if args.update else run_check()


if __name__ == "__main__":
    raise SystemExit(main())
