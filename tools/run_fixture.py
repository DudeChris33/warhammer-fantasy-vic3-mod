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
    reads distinct painted circles as distinct zone ids and a blank source as no
    zones at all; merge_island_overrides unions every region caught under the
    same zone into one (a circle over a single region is a no-op); the merge
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
    assert not lp.island_override_zones(blank, wrap_x=False).any(), "a blank source must draw no zones"

    # A drawn ring — the user's real idiom — never touches what it encloses;
    # both islets sit in the hollow interior, not on the ring itself.
    overrides = np.full((H, W, 3), 255, dtype=np.uint8)
    overrides[0, 28:37] = (255, 0, 0)
    overrides[3, 28:37] = (255, 0, 0)
    overrides[0:4, 28] = (255, 0, 0)
    overrides[0:4, 36] = (255, 0, 0)
    zones = lp.island_override_zones(overrides, wrap_x=False)
    assert int(zones.max()) == 1, f"one drawn ring must be one zone, got {zones.max()}"
    assert zones[1, 30] == 1 and zones[1, 34] == 1, \
        "both islets must fall inside the ring's filled interior"

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


def run_check() -> int:
    _selfcheck_wrap()
    _selfcheck_frame()
    print("frame: Miller round-trip + uniform-grid guard self-check passed.")
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
    _selfcheck_marker()
    print("marker: border-markup extraction (rivers in, roads ignored) self-check passed.")
    _selfcheck_sea_zones()
    print("sea_zones: drawn-line extraction (in-water splits, land marks ignored) self-check passed.")
    _selfcheck_land_provinces()
    print("land_provinces: drawn-region cut (barrier-respecting subdivision, placeholder whole) "
          "self-check passed.")
    _selfcheck_island_overrides()
    print("land_provinces: tiny-island override merge (circle -> zone -> forced single "
          "province) self-check passed.")
    _selfcheck_merge_fused()
    print("land_provinces: merge-fused disconnected region cut per piece "
          "(archipelago kept whole via keep_whole) self-check passed.")
    _selfcheck_stack_hubs()
    print("statefile: hub-stacking fallback (single/few-province stacking, cycling, port "
          "preference) self-check passed.")
    _selfcheck_sea_naming()
    print("sea_naming: canon plurality assignment + ordinal + override + zero-zone warning "
          "self-check passed.")
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
