#!/usr/bin/env python3
"""Generate the first-pass province bitmap from the hand-drawn state-region source.

Board #2773. The land mirror of ``generate_sea_zones.py``, decoupled from the
land cut / ``state_labels.png`` pipeline: reads the committed land/sea mask and
sea-zone layer plus the hand-drawn state-region source, and writes the whole-world
province image the game reads:

    tools/derived/land_sea_mask.png                          (the water authority)
    tools/derived/sea_zones.png                              (committed sea provinces)
    terraqueous_globe_reprojected - full.ora#borders          (drawn magenta lines)
        -> worldgen.land_provinces.regions / .subdivide  (magenta -> regions -> provinces)
        -> map_data/provinces.png            8192x3616 RGB, one colour per province
        -> tools/derived/provinces_index.json per-province key / id / area / coastal

The magenta network is treated as **state_region** boundary hints (~677 cells);
each drawn region is subdivided into the **provinces beneath it** to reach a
target count, with the rule that no province crosses a magenta line. The already
finished sea zones become the sea provinces; each far continent that carries no
interior magenta stays a single placeholder province. Land provinces take labels
``1..N``, sea provinces ``N+1..N+M``; a seeded ``ColorAllocator`` gives each a
unique RGB colour.

Optionally also reads ``oldworld-first/terraqueous_globe_reprojected - tiny_islands_merger.png``
(the tiny-island fix): the user paints filled circles around clusters of tiny
islands that should ship as one province each — a disconnected islet has no land
neighbour to qualify for the region stage's share-a-border merge, so left alone
every one of them becomes its own micro state-region. Absent entirely (nothing
drawn yet) is the default and changes nothing.

Optionally also reads ``tools/config/land_region_merges.json`` (board #2930
follow-up, 2026-09-05): judgement-call region merges authored as precise pixel
anchor pairs (typically copied from the naming worksheet's own anchor_x/
anchor_y columns) rather than drawn — "unify regardless of lines," for pairs
that read as one state even though the magenta network keeps them apart.
Combined with the tiny-island zones (disjoint id ranges) into one override
layer before the region stage's usual merge machinery runs. Absent entirely
changes nothing.

Deterministic: a pure function of the committed mask + sea layer + the manifested
drawn source + ``map_config.SEED``, so a re-run reproduces byte-identical output —
the determinism core.md requires of a multiplayer-synchronized mod. Regenerate
through this script after an intentional source/mask change; never hand-edit
``provinces.png`` / ``provinces_index.json``.

Usage::

    python tools/generate_provinces.py
    python tools/generate_provinces.py --target 6000 --merge-floor 1500
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import cells, lakes, land_provinces, province_ids, raster, schema, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
#: Optional inland-lake companion layer (board #3742), written by
#: generate_coastline_mask.py --from-fill. Present -> a third province class (lake)
#: is threaded through; absent -> byte-identical two-class (land/ocean) behaviour.
LAKE_MASK_PATH = DERIVED_DIR / "lake_mask.png"
SEA_LABELS_PATH = DERIVED_DIR / "sea_zones.png"
SEA_ZONES_INDEX_PATH = DERIVED_DIR / "sea_zones_index.json"
PROVINCES_PATH = REPO_ROOT / "map_data" / "provinces.png"
INDEX_PATH = DERIVED_DIR / "provinces_index.json"
LAND_REGIONS_INDEX_PATH = DERIVED_DIR / "land_regions_index.json"

STATE_REGIONS_SOURCE = sources.source_ref("state_borders")
#: Optional — the user draws filled circles on a blank canvas of this name to
#: mark clusters of tiny islands that should ship as one province each (the
#: tiny-island problem: a disconnected islet has no land neighbour to qualify
#: for cells.merge_small's share-a-border merge, so left alone every one of
#: them becomes its own micro state-region). Not required: if the file doesn't
#: exist yet, generation proceeds with no overrides, exactly as before this
#: existed.
ISLAND_OVERRIDES_SOURCE = sources.source_ref("island_overrides")
#: Optional — judgement-call region merges authored as pixel anchor pairs
#: rather than drawn. See land_provinces.apply_land_region_merges / the module
#: docstring. Absent entirely, generation proceeds with no overrides.
LAND_REGION_MERGES_CONFIG = TOOLS_DIR / "config" / "land_region_merges.json"
#: Optional — the hand-authored lore-hub settlement list (board #3665). Each row
#: pins a settlement to a canvas anchor pixel; a distinct province is seeded there
#: and picked as that state's hub downstream. Absent entirely, generation proceeds
#: with no seeded provinces (byte-identical to a no-worksheet run).
HUB_WORKSHEET_CONFIG = TOOLS_DIR / "config" / "hub_worksheet.json"
#: The single anchor -> seeded-province authority (board #3665): written here after
#: the cut so generate_land_regions.py (hub pick) and validate_map.py never
#: re-resolve an anchor independently and disagree. Only written when the worksheet
#: exists.
HUB_ANCHORS_INDEX_PATH = DERIVED_DIR / "hub_anchors_index.json"
#: Impassable-terrain layer (board #3704): the flat (255,127,0) paint of
#: full.ora#impassable. Empty/absent -> dormant, byte-identical to a no-paint run.
IMPASSABLE_SOURCE = sources.source_ref("impassable")
#: Canon-city catalogue (board #3789) and the anchor -> province authority written
#: from it (#3704), the hub_anchors_index.json idiom: the validator reads it to prove
#: every catalogued city sits in a passable, reachable province.
CANON_CITIES_CONFIG = TOOLS_DIR / "config" / "canon_cities.json"
CANON_CITY_PROVINCES_INDEX_PATH = DERIVED_DIR / "canon_city_provinces_index.json"
#: Two hub anchors of the SAME state closer than this (Euclidean px) are a hard
#: error at generate time — defence-in-depth so a seeded piece can't collapse below
#: min_area (the anchor pieces are also `protected` in merge_small, the real
#: guarantee). Anchors in different states may be arbitrarily close.
MIN_ANCHOR_SEP = 16
CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

#: Dilate the drawn magenta line this many px to bridge anti-aliased gaps.
LINE_DILATE = 2
#: Swallow region-stage offcuts below this many px (thin coastline-hugging slivers
#: the magenta-doubling-as-coast leaves) before the province cut. Lowered from
#: 1200 to 300, then to 150 (board #2930 follow-up, 2026-09-05): 1200 was also
#: swallowing genuinely-drawn small states before they ever became separate
#: regions — confirmed by comparing against the user's hand-painted
#: old_world_state_regions.png (several regions the user flagged as
#: incorrectly merged had their border already present in the drawn magenta
#: source; the region-merge step was erasing it, not a missing line). 300
#: recovered 21 more drawn regions (260->281); 150 recovers 5 more again
#: (268->273 after the merge overrides), with no new coastal-sliver noise
#: found on inspection either time (confirmed: none of the still-flagged
#: "should be split" regions are coastal, so that's not a live risk here).
#: Below this, a real hand-drawn split still won't appear on its own — several
#: regions Chris flagged as "should be N states" are unchanged in area at
#: every floor tried, confirmed by inspecting the raw drawn source directly:
#: there is no interior magenta line there at all yet (a cyan line nearby is
#: just the coast/river reference layer, not a border), so those need an
#: actual new line drawn, not a threshold change.
MERGE_FLOOR = 150
#: Target number of land-province seats shared across the drawn regions (user
#: directive 2026-08-23: the ~677 raw magenta cells are state-region hints, too
#: coarse for provinces — subdivide to ≥5,000 land provinces). Set above 5,000 so
#: the realised count clears the floor after the min-area sweep absorbs the finest
#: Voronoi offcuts; at the measured 3.85M-px drawn zone this lands ~6,070 land
#: provinces (~635 px each, close to vanilla's ~725 px/province globally).
PROVINCE_TARGET = 6000
#: A province piece below this many px is swallowed into a same-region neighbour
#: (never across a magenta boundary — the merge stays inside one region).
MIN_PROVINCE_AREA = 120


def log(msg: str, t0: float | None = None) -> None:
    prefix = f"[{time.time() - t0:6.1f}s] " if t0 is not None else ""
    print(prefix + msg, flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=int, default=PROVINCE_TARGET,
                    help=f"target land provinces in the drawn Old World (default {PROVINCE_TARGET})")
    ap.add_argument("--merge-floor", type=int, default=MERGE_FLOOR,
                    help=f"swallow region-stage offcuts below this many px (default {MERGE_FLOOR})")
    ap.add_argument("--min-area", type=int, default=MIN_PROVINCE_AREA,
                    help=f"swallow province pieces below this many px (default {MIN_PROVINCE_AREA})")
    ap.add_argument("--reassign", action="store_true",
                    help="ignore the committed provinces.png and re-allocate every colour/id "
                         "fresh in label order (board #3705 escape hatch — WILL reshuffle "
                         "colours on purpose; use only after a wholesale source overhaul)")
    ap.add_argument("--strict-placeholder-paint", action="store_true",
                    help="(board #3704) impassable paint on an out-of-scope placeholder region "
                         "is disregarded by default (logged; the source keeps it for when that "
                         "land is in scope); with this flag it is a hard error instead")
    args = ap.parse_args(argv)
    t0 = time.time()

    if not MASK_PATH.is_file():
        raise SystemExit(f"{MASK_PATH} not found — run tools/generate_coastline_mask.py first")
    if not SEA_LABELS_PATH.is_file():
        raise SystemExit(f"{SEA_LABELS_PATH} not found — run tools/generate_sea_zones.py first")
    errors = sources.verify()
    if errors:
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit("source manifest verification failed — refusing to generate")

    land = raster.read_mask_png(MASK_PATH)
    if land.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{land.shape[1]}x{land.shape[0]}")
    log(f"land mask {land.shape} land {100 * land.mean():.2f}%", t0)

    # Optional inland-lake companion layer (board #3742). Present -> lake pixels
    # become their own province class, held out of the sea band; absent -> the
    # cut is byte-identical to the two-class (land/ocean) behaviour.
    lake_mask = None
    if LAKE_MASK_PATH.is_file():
        lake_mask = raster.read_mask_png(LAKE_MASK_PATH)
        if lake_mask.shape != (CANVAS_H, CANVAS_W):
            raise SystemExit(f"{LAKE_MASK_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                             f"{lake_mask.shape[1]}x{lake_mask.shape[0]}")
        if int((lake_mask & land).sum()):
            raise SystemExit(f"{LAKE_MASK_PATH.name}: {int((lake_mask & land).sum()):,} lake "
                             f"pixel(s) fall on land — the lake companion must be water only")
        log(f"lake mask {int(lake_mask.sum()):,} px", t0)

    drawn = sources.load_source_image(STATE_REGIONS_SOURCE)  # manifest-guarded RGB
    if drawn.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{STATE_REGIONS_SOURCE}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{drawn.shape[1]}x{drawn.shape[0]}")

    overrides_rgb = sources.load_source_image(ISLAND_OVERRIDES_SOURCE)
    if overrides_rgb.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{ISLAND_OVERRIDES_SOURCE}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{overrides_rgb.shape[1]}x{overrides_rgb.shape[0]}")
    island_overrides = land_provinces.island_override_zones(overrides_rgb, land, WRAP_X)
    log(f"island overrides: {int(island_overrides.max())} hand-drawn merge-line network(s)", t0)

    log("flood-filling the magenta network into state regions ...", t0)
    reg = land_provinces.regions(land, drawn, LINE_DILATE, args.merge_floor, WRAP_X, log=log,
                                 island_overrides=island_overrides)

    if LAND_REGION_MERGES_CONFIG.is_file():
        merges = schema.load_land_region_merges(LAND_REGION_MERGES_CONFIG, canvas=(CANVAS_W, CANVAS_H))
        reg = land_provinces.apply_land_region_merges(reg, merges, log=log)
        log(f"land region merge overrides: {len(merges)} judgement-call pair(s) applied", t0)
    mag = land_provinces.magenta_lines(drawn)
    dmask = land_provinces.drawn_mask(land, mag, WRAP_X, log=log)

    # Which region labels are island-override archipelagos (kept whole even when
    # disconnected). A disconnected drawn region NOT in this set is a merge-fused
    # region (apply_land_region_merges unioned two non-touching labels), which
    # subdivide now cuts per connected piece — the #3664 fix.
    keep_whole = land_provinces.override_fused_labels(reg, land, island_overrides)
    # Overlap guard (deterministic, non-fatal): if a merge anchor resolves into a
    # label that is also an island-override archipelago, keep_whole wins and that
    # (mainland) state stays whole — the #3664 symptom would persist. Absent from
    # the current mainland anchors; warn so the config author moves the anchor.
    if LAND_REGION_MERGES_CONFIG.is_file() and keep_whole:
        touched = set()
        for m in merges:
            touched.add(land_provinces._region_near(
                reg, m.anchor_a[0], m.anchor_a[1], land_provinces._MERGE_ANCHOR_SEARCH_RADIUS))
            touched.add(land_provinces._region_near(
                reg, m.anchor_b[0], m.anchor_b[1], land_provinces._MERGE_ANCHOR_SEARCH_RADIUS))
        overlap = keep_whole & (touched - {0})
        if overlap:
            log(f"WARNING: land-region merge anchors resolve into island-override "
                f"label(s) {sorted(overlap)} — each island line in that state becomes one "
                f"province (a single-line state stays one province)", t0)

    # Hub worksheet (#3665): resolve each settlement anchor to a state region and
    # seed a distinct province there. Guarded like land_region_merges.json — absent,
    # region_seeds stays empty and the cut is byte-identical to a no-worksheet run.
    hub_rows: list = []  # (HubRow, region_label, (rx, ry)) for the persisted index
    region_seeds: dict[int, list[tuple[int, int]]] = {}
    if HUB_WORKSHEET_CONFIG.is_file():
        rows = schema.load_hub_worksheet(HUB_WORKSHEET_CONFIG, canvas=(CANVAS_W, CANVAS_H))
        rad = land_provinces._MERGE_ANCHOR_SEARCH_RADIUS
        for r in rows:
            rid, (rx, ry) = land_provinces.resolve_anchor(reg, r.anchor[0], r.anchor[1], rad)
            if rid <= 0:
                raise SystemExit(
                    f"{HUB_WORKSHEET_CONFIG.name}: hub '{r.name}' ({r.state}/{r.hub}) anchor "
                    f"{list(r.anchor)} missed land — no region within {rad}px")
            if rid in keep_whole:
                raise SystemExit(
                    f"{HUB_WORKSHEET_CONFIG.name}: hub '{r.name}' anchor {list(r.anchor)} "
                    f"resolves into island-override archipelago region {rid} — it can never "
                    f"host a distinct hub province; move the anchor")
            region_seeds.setdefault(rid, []).append((rx, ry))
            hub_rows.append((r, rid, (rx, ry)))
        # Same-region anchors must clear MIN_ANCHOR_SEP (a drawn region is 1:1 with
        # an emitted state today, so this is "same state"; anchors in different
        # regions may be arbitrarily close).
        for rid, pts in region_seeds.items():
            for a in range(len(pts)):
                for b in range(a + 1, len(pts)):
                    (x1, y1), (x2, y2) = pts[a], pts[b]
                    d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
                    if d2 < MIN_ANCHOR_SEP ** 2:
                        raise SystemExit(
                            f"{HUB_WORKSHEET_CONFIG.name}: two hub anchors of region {rid} are "
                            f"{d2 ** 0.5:.1f}px apart (< {MIN_ANCHOR_SEP}) — they may collapse "
                            f"into one province; separate them")
        log(f"hub worksheet: {len(rows)} settlement(s) -> {len(region_seeds)} seeded region(s)", t0)

    # Impassable paint (#3704). Empty/absent layer -> None -> every path dormant.
    impassable = None
    canon_cities = []
    imp_rgba = sources.read_source_rgba(IMPASSABLE_SOURCE, allow_empty=True)
    if imp_rgba is not None:
        if imp_rgba.shape[:2] != (CANVAS_H, CANVAS_W):
            raise SystemExit(f"{IMPASSABLE_SOURCE}: expected {CANVAS_W}x{CANVAS_H}, got "
                             f"{imp_rgba.shape[1]}x{imp_rgba.shape[0]}")
        impassable = land_provinces.impassable_mask(imp_rgba, land)
        impassable = land_provinces.clean_paint(impassable, land, WRAP_X)
        if impassable.any():
            if CANON_CITIES_CONFIG.is_file():
                canon_cities = schema.load_canon_cities(CANON_CITIES_CONFIG,
                                                        canvas=(CANVAS_W, CANVAS_H))
                pockets = land_provinces.city_pockets(
                    [c.anchor for c in canon_cities], impassable.shape,
                    land_provinces.CITY_POCKET_R, WRAP_X)
                impassable &= ~pockets
            log(f"impassable paint: {int(impassable.sum()):,} px after "
                f"{len(canon_cities)} canon-city pocket(s)", t0)
        else:
            impassable = None
    del imp_rgba

    log("subdividing the drawn regions into provinces ...", t0)
    try:
        land_lab, is_placeholder, reg_of, is_archipelago, is_impassable =             land_provinces.subdivide_ex(
                reg, land, dmask, args.target, WRAP_X, args.min_area, log=log,
                keep_whole=keep_whole, region_seeds=region_seeds or None,
                island_zones=island_overrides, impassable=impassable,
                strict_placeholder_paint=args.strict_placeholder_paint,
                keep_passable=[c.anchor for c in canon_cities] or None)
    except cells.CellError as e:
        raise SystemExit(f"impassable/cut error: {e}")
    n_land = int(land_lab.max())

    sea_lab = cells.read_labels(SEA_LABELS_PATH)
    if sea_lab.shape != (CANVAS_H, CANVAS_W):
        raise SystemExit(f"{SEA_LABELS_PATH}: expected {CANVAS_W}x{CANVAS_H}, got "
                         f"{sea_lab.shape[1]}x{sea_lab.shape[0]}")
    n_sea = int(sea_lab.max())
    log(f"{n_land} land provinces + {n_sea} sea provinces", t0)

    if not SEA_ZONES_INDEX_PATH.is_file():
        raise SystemExit(f"{SEA_ZONES_INDEX_PATH} not found — run tools/generate_sea_zones.py first")
    sea_zones_index = json.loads(SEA_ZONES_INDEX_PATH.read_text(encoding="utf-8"))
    sea_impassable = {int(c["label"]): bool(c.get("impassable", False))
                      for c in sea_zones_index["cells"]}
    if set(sea_impassable) != set(range(1, n_sea + 1)):
        raise SystemExit(
            f"{SEA_ZONES_INDEX_PATH.name} cells don't match {SEA_LABELS_PATH.name}'s "
            f"{n_sea} labels 1..{n_sea} — regenerate sea zones first"
        )

    # Lake province labels (board #3742), 1..K, one per connected lake body.
    if lake_mask is not None:
        lake_lab = lakes.label(lake_mask, WRAP_X)
        n_lake = int(lake_lab.max())
        log(f"{n_lake} lake provinces", t0)
    else:
        lake_lab = np.zeros_like(land_lab)
        n_lake = 0

    # Cross-consistency: the committed sea layer must tile exactly this mask's
    # navigable water (all water, minus any lakes), and the land cut exactly its
    # land. A stale sea/mask mismatch is a hard failure — regenerate sea_zones.png
    # — not a silently wrong bitmap.
    navigable = (~land & ~lake_mask) if lake_mask is not None else ~land
    if not np.array_equal(sea_lab > 0, navigable):
        raise SystemExit(
            f"{SEA_LABELS_PATH.name} does not tile this mask's navigable water: "
            f"{int((sea_lab > 0).sum()):,} sea px vs {int(navigable.sum()):,} navigable px "
            f"— regenerate tools/generate_sea_zones.py against the committed mask "
            f"(and lake companion)")
    if not np.array_equal(land_lab > 0, land):
        raise SystemExit("internal error: land provinces do not tile the land mask")
    if lake_mask is not None and not np.array_equal(lake_lab > 0, lake_mask):
        raise SystemExit("internal error: lake provinces do not tile the lake mask")

    # Combine into one label layer: land 1..N, sea N+1..N+M, lake N+M+1..N+M+K.
    labels = lakes.assemble(land_lab, sea_lab, lake_lab, n_land, n_sea)

    # Stable colour + id per province (board #3705). A province's identity IS its
    # provinces.png hex colour, so a regen that touches only a few provinces must
    # NOT reshuffle the colour/id of every province after it in raster order. The
    # committed provinces.png + index ARE the persisted authority: each new label is
    # overlap-matched (same-kind, land+sea+lake) to the committed province it most
    # overlaps — a geometry-unchanged province overlaps its committed twin 100% and
    # keeps its colour+id; genuinely-new geometry gets a fresh colour (reserving ALL
    # committed colours) + a fresh id from a monotonic high-water; a removed province
    # is gap-tolerantly retired. --reassign (or no committed bitmap: the first
    # generation and every fixture) re-allocates fresh in label order, id == label,
    # byte-identical to the pre-#3705 generator. Read the committed bitmap FULLY
    # before writing the new one — PROVINCES_PATH is both input and output.
    total = n_land + n_sea + n_lake
    kind_of_label = [""] * (total + 1)
    for lab in range(1, n_land + 1):
        kind_of_label[lab] = "land"
    for lab in range(n_land + 1, n_land + n_sea + 1):
        kind_of_label[lab] = "sea"
    for lab in range(n_land + n_sea + 1, total + 1):
        kind_of_label[lab] = "lake"

    committed_rgb = None
    committed_cells = None
    committed_high_water = None
    if not args.reassign and PROVINCES_PATH.is_file() and INDEX_PATH.is_file():
        committed_rgb = raster.read_rgb_png(PROVINCES_PATH)
        if committed_rgb.shape[:2] != (CANVAS_H, CANVAS_W):
            raise SystemExit(
                f"{PROVINCES_PATH.name}: committed bitmap is {committed_rgb.shape[1]}x"
                f"{committed_rgb.shape[0]}, expected {CANVAS_W}x{CANVAS_H} — regenerate the "
                f"mask/sea layer first, or pass --reassign to re-allocate colours fresh")
        committed_index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        committed_cells = committed_index["cells"]
        committed_high_water = committed_index.get("id_high_water")
        log(f"honouring committed {PROVINCES_PATH.name} ({len(committed_cells)} provinces) "
            f"for stable colours/ids", t0)
    else:
        log("no committed bitmap honoured — allocating colours/ids fresh in label order "
            f"({'--reassign' if args.reassign else 'no committed provinces.png/index'})", t0)

    palette, ids, id_high_water = province_ids.assign(
        labels, kind_of_label, committed_rgb, committed_cells, map_config.SEED,
        reassign=args.reassign, committed_high_water=committed_high_water)
    rgb = palette[labels]

    # Persist the anchor -> seeded-province index (#3665): the single authority the
    # hub pick (generate_land_regions.py) and validate_map.py read, so neither
    # re-resolves an anchor from the bitmap and disagrees with the cut. Written only
    # when the worksheet exists; everything above reads none of it, so provinces.png
    # / provinces_index.json stay byte-identical to a no-worksheet run.
    if hub_rows:
        hub_index = {"canvas": [CANVAS_W, CANVAS_H], "source": HUB_WORKSHEET_CONFIG.name, "hubs": []}
        for r, rid, (rx, ry) in hub_rows:
            plab = int(land_lab[ry, rx])
            pcol = tuple(int(v) for v in palette[plab])
            hub_index["hubs"].append({
                "state": r.state,
                "hub": r.hub,
                "name": r.name,
                "source": r.source,
                "anchor": [int(r.anchor[0]), int(r.anchor[1])],
                "resolved": [int(rx), int(ry)],
                "region": int(rid),
                "province_label": plab,
                "province_color": list(pcol),
                "province_hex": raster.color_to_hex(pcol),
            })
        HUB_ANCHORS_INDEX_PATH.write_text(json.dumps(hub_index, indent=1) + "\n", encoding="utf-8")
        log(f"wrote {HUB_ANCHORS_INDEX_PATH.relative_to(REPO_ROOT)}  ({len(hub_rows)} hub(s))", t0)

    # Canon-city anchor -> province (#3704). Only written when paint exists; the
    # validator proves each city's province is passable and reachable.
    if impassable is not None and canon_cities:
        city_index = {"canvas": [CANVAS_W, CANVAS_H], "source": CANON_CITIES_CONFIG.name,
                      "pocket_radius": land_provinces.CITY_POCKET_R, "cities": []}
        for c in canon_cities:
            ax, ay = c.anchor
            plab = int(land_lab[ay, ax])
            pcol = tuple(int(v) for v in palette[plab]) if plab > 0 else None
            city_index["cities"].append({
                "name": c.name,
                "anchor": [int(ax), int(ay)],
                "province_label": plab,
                "province_hex": raster.color_to_hex(pcol) if pcol else None,
                "impassable": bool(plab > 0 and is_impassable[plab]),
            })
        CANON_CITY_PROVINCES_INDEX_PATH.write_text(
            json.dumps(city_index, indent=1) + "\n", encoding="utf-8")
        log(f"wrote {CANON_CITY_PROVINCES_INDEX_PATH.relative_to(REPO_ROOT)}  "
            f"({len(canon_cities)} city/cities)", t0)

    PROVINCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    raster.write_rgb_png(PROVINCES_PATH, rgb)
    log(f"wrote {PROVINCES_PATH.relative_to(REPO_ROOT)}  "
        f"({total} provinces, {CANVAS_W}x{CANVAS_H} RGB)", t0)

    # Per-province index. Coastal is computed per kind: a land province is coastal
    # if it touches NAVIGABLE water, a sea province if it touches land. With lakes
    # present, a lake is held out of "water" on both sides of this test — it is
    # land-locked and stateless (no naval_exit_id, no port), so a land province
    # bordering only a lake must not read as coastal (board #3742 follow-up: this
    # used to fold lake-adjacency into land_coastal, which silently produced a
    # region flagged coastal with no bordering sea state for generate_land_regions
    # to resolve a naval exit against). Byte-identical when no lake mask.
    areas = np.bincount(labels.ravel(), minlength=total + 1)
    navigable_water = (~land & ~lake_mask) if lake_mask is not None else ~land
    land_side = (land | lake_mask) if lake_mask is not None else land
    land_coastal = cells.coastal_labels(land_lab, land_side, WRAP_X)
    sea_coastal = cells.coastal_labels(sea_lab, navigable_water, WRAP_X)
    # A lake touches land by definition; computed for schema symmetry (informational).
    lake_coastal = (cells.coastal_labels(lake_lab, lake_mask, WRAP_X)
                    if lake_mask is not None else np.zeros(1, dtype=bool))

    # Provinces share ONE continuous id space, exactly as vanilla's definition.csv
    # does — a province id is a unique gap-tolerant handle, and the bitmap colour is
    # the real key. Both `color` and `id` per cell come from province_ids.assign
    # (board #3705): a geometry-unchanged province keeps its committed colour+id, so
    # neither is a raster-order ordinal any more (the old `id == label` per-kind
    # bands are retired — the `sea_id_start = n_land + 1` band was the direct cause
    # of every sea id shifting whenever the land count changed). The single monotonic
    # `id_high_water` (persisted in the header below) is the next unused id.
    entries = []
    n_placeholder = 0
    n_archipelago = 0
    n_impassable = 0
    for lab in range(1, n_land + 1):
        color = tuple(int(v) for v in palette[lab])
        # Out-of-scope far continents are kept whole but emitted PASSABLE: Vic3
        # stacks every hub on one province (vanilla STATE_DELAWARE/STATE_BUKOVINA),
        # so a landmass boots as a legal one-province state. The out-of-scope
        # signal is preserved separately as `placeholder` for downstream state
        # emission; `impassable` now honestly means impassable and is uniformly
        # False on land.
        placeholder = bool(is_placeholder[lab]) if lab < len(is_placeholder) else False
        n_placeholder += placeholder
        # Genuinely non-contiguous (several islands under one label, from a
        # deliberate island-override merge) — legal per vanilla precedent (e.g.
        # Micronesia's province colour spans 23 disconnected blobs), so
        # validate_map.py reads this flag to tell it apart from a torn province.
        archipelago = bool(is_archipelago[lab]) if lab < len(is_archipelago) else False
        n_archipelago += archipelago
        impass = bool(is_impassable[lab]) if lab < len(is_impassable) else False
        n_impassable += impass
        entries.append({
            "label": lab,
            "kind": "land",
            "color": color,
            "hex": raster.color_to_hex(color),
            "id": int(ids[lab]),  # stable committed id, or fresh from the high-water
            "area": int(areas[lab]),
            "coastal": bool(land_coastal[lab]) if lab < len(land_coastal) else False,
            "impassable": impass,  # cut from the impassable-terrain paint (#3704)
            "placeholder": placeholder,  # out-of-scope land kept whole, undetailed
            "archipelago": archipelago,  # several islands merged under one label
        })
    for s in range(1, n_sea + 1):
        lab = n_land + s
        color = tuple(int(v) for v in palette[lab])
        entries.append({
            "label": lab,
            "kind": "sea",
            "color": color,
            "hex": raster.color_to_hex(color),
            "id": int(ids[lab]),  # stable committed id, or fresh from the high-water
            "area": int(areas[lab]),
            "coastal": bool(sea_coastal[s]) if s < len(sea_coastal) else False,
            "impassable": sea_impassable[s],  # from sea_zones_index.json (config-driven)
            "placeholder": False,  # schema symmetry with land entries
            "archipelago": False,  # schema symmetry with land entries
        })
    # Lake provinces (board #3742), labels N+M+1..N+M+K, ids continuing the one
    # shared id space after the sea band. Stateless inland water: declared only in
    # default.map's `lakes` block, never in a state region (validate_map's
    # _check_lakes_stateless / _check_bitmap_state_crosscheck encode that). Marked
    # impassable (inland, non-navigable; harmless as no state ever lists them).
    # The world ocean is the navigable water — exactly the sea provinces, which
    # tile it (asserted above) — so its area is the sum of the sea province areas
    # and equals lakes.classify's own ocean_area. Persist each lake's fraction of
    # it (board #3742 Phase B) so the sealed-strait guard is legible in the index
    # itself and re-checkable offline by validate_map._warn_lakes_oversized rather
    # than living only in generate_coastline_mask.py stdout.
    ocean_area = int(areas[n_land + 1:n_land + n_sea + 1].sum())
    for k in range(1, n_lake + 1):
        lab = n_land + n_sea + k
        color = tuple(int(v) for v in palette[lab])
        entries.append({
            "label": lab,
            "kind": "lake",
            "color": color,
            "hex": raster.color_to_hex(color),
            "id": int(ids[lab]),  # stable committed id, or fresh from the high-water
            "area": int(areas[lab]),
            "ocean_area_fraction": round(int(areas[lab]) / ocean_area, 6) if ocean_area else 0.0,
            "coastal": bool(lake_coastal[k]) if k < len(lake_coastal) else False,
            "impassable": True,  # inland non-navigable water (stateless; informational)
            "placeholder": False,  # schema symmetry with land/sea entries
            "archipelago": False,  # schema symmetry with land/sea entries
        })

    index = {
        "canvas": [CANVAS_W, CANVAS_H],
        "source": STATE_REGIONS_SOURCE,
        "sea_source": SEA_LABELS_PATH.name,
        "lake_source": LAKE_MASK_PATH.name if lake_mask is not None else None,
        "land_provinces": n_land,
        "sea_provinces": n_sea,
        "lake_provinces": n_lake,
        "impassable_land_provinces": n_impassable,  # from the impassable layer (#3704)
        "impassable_sea_provinces": sum(sea_impassable.values()),  # from sea_zones.json config
        "placeholder_land_provinces": n_placeholder,  # out-of-scope land kept whole
        "archipelago_land_provinces": n_archipelago,  # islands merged by an override circle
        # Board #3705: the per-kind id bands (land_id_start/sea_id_start/lake_id_start)
        # are retired — id is a stable, gap-tolerant handle carried across regens by
        # province_ids.assign, not a raster-order ordinal. id_high_water is the next
        # unused id (seeds fresh-id allocation on the next regen so a retired id is
        # never resurrected).
        "id_high_water": int(id_high_water),
        "cells": entries,
    }
    INDEX_PATH.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    log(f"wrote {INDEX_PATH.relative_to(REPO_ROOT)}", t0)

    # Persist the land province -> state-region grouping that subdivide already
    # computed in reg_of and used to throw away. #2930 emits land state_regions/*.txt
    # from this — the land mirror of sea_zones_index.json. Region-keyed, carrying
    # province LABELS only; provinces_index.json stays the colour authority. This
    # block writes a SEPARATE file and reads nothing above, so provinces.png and
    # provinces_index.json are byte-identical whether or not it runs.
    reg_count = int(reg.max())
    reg_areas = np.bincount(reg.ravel(), minlength=reg_count + 1)
    groups: dict[int, list[int]] = {}
    for lab in range(1, n_land + 1):
        groups.setdefault(int(reg_of[lab]), []).append(lab)
    # Totality, asserted on the REAL data at generation time (validate_map.py
    # --province-bitmap does not read this file, so a broken grouping must fail
    # loudly here): every land province lands in exactly one region, and every
    # region 1..R is populated.
    grouped = sorted(p for members in groups.values() for p in members)
    if grouped != list(range(1, n_land + 1)):
        raise SystemExit(
            f"land region grouping is not total: {len(grouped)} grouped provinces "
            f"vs {n_land} land provinces")
    if set(groups) != set(range(1, reg_count + 1)):
        raise SystemExit(
            f"land region grouping skips or invents a region id: got {sorted(groups)}, "
            f"expected 1..{reg_count}")
    region_cells = []
    n_drawn_regions = 0
    for r in range(1, reg_count + 1):
        members = sorted(groups[r])
        # A region is wholly drawn or wholly placeholder (a magenta barrier cannot
        # cross water, so a region nests in one landmass); all == any here.
        placeholder = all(bool(is_placeholder[lab]) for lab in members)
        n_drawn_regions += not placeholder
        region_cells.append({
            "region": r,
            "kind": "placeholder" if placeholder else "drawn",
            "area": int(reg_areas[r]),
            "provinces": members,
        })
    land_regions = {
        "canvas": [CANVAS_W, CANVAS_H],
        "source": STATE_REGIONS_SOURCE,
        "land_provinces": n_land,
        "regions": reg_count,
        "drawn_regions": n_drawn_regions,
        "placeholder_regions": reg_count - n_drawn_regions,
        "cells": region_cells,
    }
    LAND_REGIONS_INDEX_PATH.write_text(json.dumps(land_regions, indent=1) + "\n", encoding="utf-8")
    log(f"wrote {LAND_REGIONS_INDEX_PATH.relative_to(REPO_ROOT)} "
        f"({reg_count} regions: {n_drawn_regions} drawn, "
        f"{reg_count - n_drawn_regions} placeholder)", t0)

    land_areas = areas[1:n_land + 1]
    log(f"done: {n_land} land provinces ({n_placeholder} out-of-scope passable placeholders, "
        f"{n_archipelago} island-override archipelagos) "
        f"(area min {int(land_areas.min()):,} / median {int(np.median(land_areas)):,} / "
        f"max {int(land_areas.max()):,} px), {n_sea} sea provinces, {n_lake} lake provinces", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
