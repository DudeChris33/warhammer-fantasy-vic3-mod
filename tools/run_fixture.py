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
import random
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import composite, ingest, raster, reproject, schema, segment, sources, statefile  # noqa: E402
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
from worldgen.statefile import ProvinceInfo, compute_centroid, pick_hubs  # noqa: E402

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

    # The synthetic world tiles the globe, so despeckle is wrap-aware; its
    # features are large relative to a 256 px source, so a small blob threshold
    # keeps them while still removing the painted speckle.
    fields = ingest.classify_source(rgb, elut, majority=3, min_blob=8, wrap_x=True)
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
        "",
    ]
    path.write_bytes("\n".join(lines).encode("utf-8"))


def _update_ingest_manifest() -> None:
    """Refresh the fixture manifest's dims/bytes/SHA for the committed source.

    Deliberately does *not* reuse ``sources.update_manifest``: that sweeps every
    file in its directory, and the fixture dir also holds ``make_source.py``,
    ``lut.json`` and this manifest, which must not become manifest rows. This only
    refreshes rows already declared in the fixture manifest.
    """
    md = INGEST_MANIFEST.read_text(encoding="utf-8")
    rows = []
    for r in sources.parse_manifest(md):
        p = INGEST_DIR / r.file
        rows.append(sources.ManifestRow(
            r.file, sources.image_dims(p), f"{p.stat().st_size:,}",
            sources.sha256_of(p), r.origin, r.role, r.registered))
    INGEST_MANIFEST.write_text(
        sources._splice_manifest(md, sources.render_table(rows)), encoding="utf-8")
    print(f"fixture manifest refreshed: {INGEST_MANIFEST}")


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

def run_check() -> int:
    _selfcheck_wrap()
    _selfcheck_composite()
    print("composite: precedence + tie-rejection self-check passed.")
    _selfcheck_rivers()
    print("rivers: rasterize + topology-validation self-check passed.")
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

    print("\nFIXTURE OK.")
    return 0


def run_update() -> int:
    _selfcheck_wrap()
    _selfcheck_composite()
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
        _update_ingest_manifest()
        return 0
    return run_update() if args.update else run_check()


if __name__ == "__main__":
    raise SystemExit(main())
