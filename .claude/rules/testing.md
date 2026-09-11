# Testing Rules

There is no compiler and no automated test suite for Clausewitz script — validation happens by loading the mod in Victoria 3 itself.

## Validation procedure

1. Launch Victoria 3 with this mod enabled.
2. Load into a game (main menu script parsing alone won't catch every error — get to a session if the change touches `events/` or `history/`).
3. Check `logs/error.log`, located one level above the game's `mod/` folder — i.e. `Documents/Paradox Interactive/Victoria 3/logs/error.log` (this mod folder is `Documents/Paradox Interactive/Victoria 3/mod/warhammer-fantasy/`).
4. Any new line referencing a file in this mod is a failure. Fix the **script**, not the log.

## Map data (offline pre-commit lint)

Map text and bitmaps additionally have an **offline** validator — there is no
reason to load the game to catch a duplicate province claim or a missing hub.
One-time setup: create a local virtualenv and install the pinned deps — see
`tools/requirements.txt` for the exact commands. The project convention is a
`tools/.venv` (already gitignored) — activate it before running any `tools/`
script. Before committing anything
under `map_data/` (province bitmap, `heightmap.png`, `rivers.png`,
`state_regions/`, `default.map`, `adjacencies.csv`), the water strategic regions
(`common/strategic_regions/water_strategic_regions.txt`), the map localization, or
the source-registration data (`tools/SOURCES.md`, `tools/registration/`), run:

```
python tools/worldgen/sources.py --verify       # source manifest SHA-256 + registration cross-checks
python tools/validate_map.py --province-bitmap   # the province bitmap tiles the mask + agrees with its index and the sea layer, and (if present) province_terrains.txt
python tools/validate_map.py --sea               # sea engine files: 99_seas colours ⊆ sea_starts ⊆ provinces.png sea colours; every sea state grouped + localized
python tools/run_fixture.py --check              # regression-checks the toolchain itself
python tools/validate_map.py                     # full crosscheck (needs both sea + land states — see below)
```

The `--sea` subset check is the sea-side gate for board #2929's emitted files
(`99_seas.txt`, `default.map` `sea_starts`, `water_strategic_regions.txt`, the sea
loc), useful on its own when only the sea side has changed. The full no-flag
`validate_map.py` needs *every* province colour claimed by a state, land and sea
both — it started passing once board #2930 emitted the land states
(`00_norsca.txt`) alongside the already-shipped sea files, and stays the gate to
run whenever either side changes. **A province-bitmap regen invalidates both
emitted state files, not just the one whose input changed**: `99_seas.txt`'s
colours are `provinces_index.json`-label-keyed (`land_provinces + zone_label`), so
a `generate_provinces.py` run that changes the land province count shifts every
sea colour even though nothing about the sea zones themselves changed — this bit
board #2930 (the committed `99_seas.txt` had gone stale after a source update
regenerated `provinces.png`, 714→708 regions). Board #3705 fixed this ripple going
forward — `generate_provinces.py` now honours the committed `provinces.png` +
index and keeps a geometry-unchanged province's colour+id stable even when the
land count changes elsewhere (see below) — but re-running **both**
`generate_sea_regions.py` and `generate_land_regions.py` after any
`generate_provinces.py` regen stays the rule: a genuinely new/removed province
still moves colours locally, and `--reassign` (or the very first generation) still
re-allocates every colour fresh in label order, not just the one whose upstream
index moved.
`tools/generate_province_terrains.py` (board #2968) is the same colour-keyed
fragility class and belongs in that same re-run set once its output ships — see
below; today its generated `map_data/province_terrains.txt` is not committed
(the province cut is still churning, #3663/#3664/#3705), so there is nothing
yet to go stale.

All must pass before the in-game `error.log` check below. This does not replace
the game load — it catches the offline-detectable class of error first. The
`sources.py --verify` step confirms the local `sources/` files still match the
committed SHA-256 manifest — a swapped or edited source that would silently
change a committed bitmap fails here. Refreshing a source after an *intentional*
change is the explicit `python tools/worldgen/sources.py --update-manifest`
action, never a side effect of a generator run.

`tools/derived/land_sea_mask.png`, `map_data/heightmap.png`, `map_data/rivers.png`,
`tools/derived/state_labels.png`, `tools/derived/sea_zones.png` (+
`tools/derived/sea_zones_index.json`) and `map_data/provinces.png` (+
`tools/derived/provinces_index.json` + `tools/derived/land_regions_index.json`, the
region→province grouping) are generated, not hand-authored: after an
intentional source/LUT/registration change, regenerate them with `python
tools/generate_coastline_mask.py` (the sole owner of `land_sea_mask.png` — either
flood-filled from the user's traced coastline in `sources/land_sea_mask.png`, or,
with `--from-fill`, read directly when that source is already a finished
black/white land fill rather than a coastline trace; `--from-fill` also emits the
companion `tools/derived/lake_mask.png`, board #3742 — see below. Either mode
drops isolated sub-4px land components to water first
(`drop_land_specks`, board #3705 follow-up) — anti-aliased export specks that
would otherwise ship as a permanent 1px micro state; `--speck-max` overrides the
floor, 0/1 disables), `python
tools/generate_heightmap.py` (which now *consumes* that mask — the old
height-ramp mask derivation was deleted 2026-08-22), `python
tools/generate_rivers.py`, `python tools/generate_state_labels.py`, `python
tools/generate_sea_zones.py` and `python tools/generate_provinces.py`, and re-run
the checks above before committing. The mask moves first; every downstream layer
is regenerated from it.
**Sea-zone STATE id + key stability (board #4191).** `generate_sea_zones.py`
overlap-matches the current `sea_zones.png` against the committed one via
`worldgen/sea_state_ids.py` (the sea mirror of #3705's `province_ids.assign` and
#4188's `land_state_numbering.assign_state_numbers`; identity is zone-layer pixel
overlap, since it runs *before* `generate_provinces.py` and has no stable
province id yet), so a geometry-unchanged zone keeps its committed `id` (3000+
band) and — when its `display_name` is unchanged — its `STATE_<NAME>_NN` `key`
verbatim; a new zone gets a fresh id above a monotonic `sea_id_high_water` + a
fresh per-slug ordinal off `ordinal_high_water`; a removed zone's id/key retire
permanently. The two high-waters are new regenerate-only top-level keys in
`sea_zones_index.json` — **no new committed file, no seed script** (unlike #4188's
`land_state_ids.json`; the sea index already carries per-zone `id`+`key`, and the
high-water self-bootstraps from the dense committed ids on the first fixed run).
`generate_sea_zones.py --reassign` (pair it with a province/land `--reassign`) is
the byte-identical pre-#4191 label-order escape hatch; a zero-overlap collapse
falls back to it with a loud warning. `generate_sea_regions.py` /
`generate_land_regions.py` are unchanged (they read only `cells[].id`/`key`). Like
#3705/#4188 this ships **tools-only** — no committed sea regen (that stays the
user-gated visual step below).
The sea engine files `map_data/state_regions/99_seas.txt`,
`common/strategic_regions/water_strategic_regions.txt`, and `map_data/default.map`'s
`sea_starts` block are emitted by `python tools/generate_sea_regions.py` (board
#2929) — it joins `provinces_index.json` (colours) with `sea_zones_index.json`
(canon keys/ids), so regenerate rather than hand-edit them (`default.map`'s other
keys and `adjacencies.csv`'s strait rows stay hand-authored). The old staged
`tools/derived/seas_99_seas.txt` / `seas_sea_starts.txt` are removed.
`map_data/state_regions/NN_<stem>.txt` (all 20),
`common/strategic_regions/{old_world,southlands,out_of_scope}_strategic_regions.txt`
and `localization/replace/english/map/states_l_english.yml` (in `replace/`, named
after vanilla's own file — an Old-World name can coincide with a real-world
vanilla state name, found via `STATE_AQUITAINE`, and the mod's own name
overrides vanilla's outright rather than dodging the collision) are emitted the same
way by `python tools/generate_land_regions.py` (boards #2930/#2931) — it joins
`land_regions_index.json` (369 regions: 267 drawn + 102 out-of-scope placeholders)
with `provinces_index.json` and `sea_zones_index.json` (naval-exit resolution by
real land↔sea pixel adjacency), then routes each region through
`tools/worldgen/land_naming.py` for its canon realm (a per-region pixel-plurality
vote against `sources/terraqueous_globe_reprojected - strategic_regions.png`,
classified by `tools/config/strategic_region_colors.json`) and canon name (from
the persisted, hand-edited `tools/config/land_regions_worksheet.csv`, or its
out-of-scope continent's name from `tools/config/out_of_scope_continents.json`);
regenerate rather than hand-edit any of the emitted files. It also (board #4188)
writes `tools/derived/land_state_ids.json` — the STATE-number identity
authority (state_number → stable province-id set + a monotonic
`state_number_high_water`), read read-only by `render_land_regions_preview.py`
— a committed, regenerate-only index like `provinces_index.json`, never
hand-edited. `tools/worldgen/land_state_numbering.assign_state_numbers`
overlap-matches the current region cut against it so an unchanged region keeps
its STATE number across regens instead of every region being renumbered fresh
by Hilbert rank each run (the land-region mirror of #3705's stable province
ids); it was seeded once from the already-shipped numbers with the one-time
`python tools/seed_land_state_ids.py` (parses the committed
`state_regions/*.txt` off a git ref — `HEAD` by default — never the working
tree, so it can seed the clean baseline even mid-regen). `generate_land_regions.py`'s own `--reassign` flag forces a fresh Hilbert
renumber and always pairs with a `generate_provinces.py --reassign` — running
one without the other trips `assign_state_numbers`' zero-match safety net
(loud warning, falls back to the bootstrap renumber rather than silently
retiring every state).
`map_data/province_terrains.txt` (board #2968) is the map-config counterpart,
emitted by `python tools/generate_province_terrains.py` from
`provinces_index.json`'s `cells` — one `x<HEX>="terrain"` line per province,
sorted by id, land → `"plains"`, sea → `"ocean"` and (board #3742) lake →
`"lakes"` (all three defined in `common/terrain/01_terrain.txt`; the lake mapping
is only exercised when the index carries `kind:"lake"` cells), a uniform
placeholder baseline standing in for a future sourcing-driven terrain pass.
`validate_map.py --province-bitmap`'s check 8 (`validate_province_terrains`)
verifies it, when present, is a bijection with the index colours and that every
terrain id is defined in `common/terrain`; its **absence is a clean skip, not an
error** — same convention as `_check_adjacencies`. The generated file is
**deferred**: it is the same colour-keyed fragility class as `99_seas.txt`/the
land `state_regions/*.txt` and is not committed until the province cut settles
(#3663/#3664/#3705), at which point it joins the "re-run after a
`generate_provinces.py` regen" set alongside `generate_sea_regions.py` and
`generate_land_regions.py`.
**Inland lakes (board #3742)**: a third province class — `lake`, water not
connected to the world ocean — is threaded through the same pipeline as an
*optional* companion layer, `tools/derived/lake_mask.png`, emitted by
`generate_coastline_mask.py --from-fill` (see above). Its pure core is
`tools/worldgen/lakes.py` (`classify`/`label`/`assemble` — the lake mirror of
`worldgen/sea_zones.py`: of the water, the largest wrap-aware connected component
is the world ocean and every other component is an inland lake, one province per
lake, no subdivision). When present, `generate_sea_zones.py` passes it to
`sea_zones.extract`'s new `exclude=` param so a lake is never labelled a sea
zone; `generate_provinces.py` tiles land/ocean/lake three-way and appends
`kind:"lake"` cells (`impassable:true`, informational) with a new index header key
`lake_provinces`, ids continuing the one shared id space after the sea band —
originally via a retired `lake_id_start` band, now (board #3705) via the single
monotonic `id_high_water`; and `generate_sea_regions.py` block-replaces
`map_data/default.map`'s
`lakes = { }` block with the lake province colours (empty when there are none) —
**lakes are stateless**, declared only there, never in a `99_seas` state, a water
strategic region, or loc. `validate_map.py --province-bitmap` becomes three-way
when a lake mask and/or lake cells are present (lake band check, no province
straddles land/ocean/lake, the sea layer tiles the *navigable* water only,
lake-labelled pixels == the lake mask exactly); the full `validate_map.py` run
gains `_check_lakes_declared` closing the loop between the index's lake colours
and `default.map`'s `lakes` block. **Phase B hardening (board #3742 follow-up):**
`generate_provinces.py` persists each lake cell's `ocean_area_fraction` (its area
over the world ocean's — the sum of the sea province areas, which tile the
navigable water), and `validate_map.py --province-bitmap` re-surfaces the two
content-integrity guards that previously lived only in
`generate_coastline_mask.py` stdout, as **non-blocking `WARNING`s** printed to
stderr that never gate the exit code (a legit large/small lake may exist; the
render is the final gate): `_warn_lakes_oversized` (a lake over
`lakes.OCEAN_WARN_FRACTION` of the ocean — a navigable sea the fill may have
sealed off) and `_warn_lakes_degenerate` (a lake below `lakes.LAKE_REPORT_MIN`, a
*reporting* floor mirroring `generate_coastline_mask._REPORT_MIN` — likely fill
speckle; `lakes.label` gives every water component a province with no floor, and
the remedy is drop-or-redraw, never merge, since a lone speck has no lake
neighbour to merge into). These flow through a caller-owned `warnings=` list
distinct from the returned error list; `lakes.classify` logs the same two guards
at generation time. `python tools/run_fixture.py --check` gained
`_selfcheck_lakes` (classify/label/assemble; `sea_zones.extract`'s exclude=
before/after; the three-way validator; the stateless checks; `_replace_lakes`
idempotence; **and, Phase B, `classify`'s oversized/junk-lake log reporting, the
two `_warn_lakes_*` functions in isolation, and the end-to-end proof that
`validate_provinces` populates `warnings` without adding to `errors`**) and
`_selfcheck_province_terrains` now also covers the `lake -> "lakes"` mapping. **Every lake code path is dormant and byte-identical to the
prior two-class (land/ocean) behaviour when no `lake_mask.png` exists** — this is
Phase A tooling only, like rivers #3703: the real `lake_mask.png` and the
bitmaps it feeds are regenerated only on the user's fill and gated on their
visual verdict, not here. A `generate_provinces.py` regen invalidates the lake
dependents too, so `lake_mask.png`'s presence joins the "re-run
`generate_sea_zones.py`, `generate_sea_regions.py`, `generate_land_regions.py`
and `generate_province_terrains.py` after a `generate_provinces.py` regen" set
above.
**Canon rivers (board #3703)**: `map_data/rivers.png` is **source-driven**, not
heightmap-derived (committed real 2026-09-07). The canon rivers are hand-traced
as a pure-cyan (`0,255,255`) line network on the canvas
(`sources/terraqueous_globe_reprojected - rivers.png`, 1:1, no registration — or
several layers in the optional `tools/config/river_sources.json`).
`worldgen/river_network.py` skeletonizes the cyan (wrap-aware), builds a
topological-adjacency graph, and orients each connected network into a **flow
DAG** by a strict rank (BFS-distance-to-outlet → elevation → pixel; a total order,
so it is guaranteed acyclic). That makes **divergence first-class** — vanilla's
model, not the earlier tree-only one:
- **Lakes** (board #3742): ocean and lake are distinguished
  (`worldgen.lakes.classify` on the committed `land_sea_mask.png`, or the
  committed `lake_mask.png` when present). A lake-fed river sources at the lake; a
  lake→sea or lake→lake river is not a fork.
- **Endorheic** rivers dry up inland at a sink (the Marshes of Madness) — an
  `endorheic` mouth, no marker, no water-adjacency required.
- **Splits** (deltas + river-islands): a distributary branches off the trunk and
  is painted with vanilla's yellow **split marker (index 2)**, the mirror of the
  red merge. `schema.RiverStream` carries a `head` (`source`|`split`).
- **Manual flow overrides** `tools/config/river_overrides.json` (hand-authored,
  regenerate-through, the anchor idiom): a network the tool can't auto-orient —
  most often a channel whose *both* ends reach the sea, so it has no headwater —
  is pinned by anchor to a compass `flow` direction (mouth = the furthest endpoint
  that way); its coastal source is waived (`RiverStream.coastal_source`). Each
  un-orientable river needs its own entry — a per-case manual decision, reported
  by the generator (`no-source`), never guessed.

A source change follows the usual cascade: edit/redraw the trace → `python
tools/worldgen/sources.py --update-manifest` → `python tools/generate_rivers.py`
(→ `map_data/rivers.png` + committed `tools/derived/rivers_index.json`) → offline
gate → `python tools/render_rivers_preview.py` → **send the render, get the user's
visual verdict, then the in-game `error.log` check** → commit. `generate_rivers.py`
reads the committed `land_sea_mask.png` + the cyan trace + the heightmap (flow
tie-break / endorheic-sink pick), so a `generate_provinces.py` regen does **not**
invalidate `rivers.png` — but a *province* regen moves the state colours the
`rivers_index.json` `state_keys` join reads, so re-run `generate_rivers.py` after
one if you need the index current. The full `validate_map.py` run's `_check_rivers`
(indices ⊆ the vanilla set incl. the split 2; river pixels on land; sources clear
of the ocean but lake-fed allowed via an `ocean` param; merge + split markers
touch a stream; the 2×2 caps; endorheic mouths legal — no dead-end rule; the
`canon_rivers.csv` (river, state) cross-check) stays **gated on
`tools/config/canon_river_names.json` existing** (naming is opt-in; absent, the
generator's own `worldgen.rivers._validate` owns correctness at emit time).
`python tools/run_fixture.py --check` exercises `worldgen/river_network.py` and
the validator on synthetic networks (Strahler stems; endorheic sink; lake-fed
source; a **delta** and a **river-island** that paint splits; a manual override on
a sea-to-sea channel; a sourceless closed ring rejected; spur pruned; wrap-seam
stem; byte-identical reruns).
**Lore hubs (board #3665)**: `tools/config/hub_worksheet.json` is a hand-authored,
regenerate-through input (like the naming worksheet) — one settlement per row,
pinned to a canvas anchor. A change to it forces the **full**
`generate_provinces.py → generate_sea_regions.py **and** generate_land_regions.py`
cascade + re-validate, because a seeded anchor reshuffles every province colour
(the global sorted-label `ColorAllocator`), exactly like any other
`generate_provinces.py` regen. It writes `tools/derived/hub_anchors_index.json`
(the anchor→province authority — regenerate, never hand-edit) and the generated
loc `localization/english/map/wh_hub_names_l_english.yml`, which joins the map-loc
gate. `python tools/validate_map.py` (full) runs `_check_hub_anchors` on the real
map when that index exists; `python tools/render_hubs_preview.py` is the dev-only
review render (source-dependent, gitignored `tools/derived/` output). Absent (no
worksheet), every one of these paths is dormant and the map is byte-identical to a
no-hub run.
`tools/render_land_regions_preview.py` is the matching **dev-only** review
render, outside the gate above: a numbered review PNG + a `tools/derived/`
worksheet sidecar that round-trips names already committed in
`tools/config/land_regions_worksheet.csv` forward (never overwrites them),
draping the real TWW3 parchment art under the tinted regions via
`tools/project_regions.py`'s existing five-crop registration wherever it covers
the canvas (an `on_parchment` CSV column flags which regions that is), so the
person doing the canon-naming pass reads real printed names off the render
directly. Two earlier automated-guess attempts were tried and dropped
(2026-09-05): nearest real-world vanilla Vic3 state by lon/lat (a coincidental-
Earth-geography heuristic the user rejected outright) and OCR of the parchment
itself (Tesseract garbled almost everything on the stylised, curved-baseline
font even after rotation sweeps, contrast stretching and despeckling). Neither
tool nor its derived output exists any more. `python tools/run_fixture.py --check` also exercises
`worldgen.statefile.stack_hubs`, the hub-stacking fallback `pick_hubs` cannot
cover (a state with fewer passable provinces than it needs — every placeholder
and any small drawn region).
`generate_sea_zones.py` and `generate_provinces.py` are both decoupled from the
land cut — each reads the committed `land_sea_mask.png` and its own hand-drawn
source directly (the purple sea-zone network, the magenta state-region network),
and neither is wired into `state_labels.png`. `generate_provinces.py` (board
#2773) folds the already-committed `sea_zones.png` in as the sea provinces
(labels `N+1..N+M` after land `1..N`); the land side comes from
`tools/worldgen/land_provinces.py`, the land mirror of `worldgen/sea_zones.py` —
it flood-fills the hand-drawn magenta network into barrier-respecting state
regions, then subdivides each drawn region into provinces (no province crosses a
magenta line); an out-of-scope far continent with no interior magenta is
classified a placeholder and kept whole as one passable placeholder province (Vic3
stacks every hub on one province, so a landmass needs only one passable province
to boot as a legal state; `impassable` is uniformly `false` on land, and the
out-of-scope signal is carried separately as the `placeholder` flag).
`worldgen/sea_zones.py`'s `extract` also gained a `split_disconnected`
connectivity repair (the nearest-label fill can tear a zone into two
disconnected pieces sharing one label; `land_provinces.regions` mirrors the
same repair).
`--labels` is only meaningful once the state-label layer exists; the plain
`validate_map.py` (no flag) additionally needs `state_regions/*.txt`, which
hasn't been authored yet (S3b) — until then, `--province-bitmap` is the check
for `map_data/provinces.png` itself.

Registration records (`tools/registration/*.json`) are machine-fitted, not
hand-written: re-derive with `python tools/fit_registration.py --seed <stem>`
after editing the corresponding seed in `tools/registration/seeds/`. Like
`--update-manifest`, that is an explicit authoring action and never part of the
gate.

`tools/config/inland_lakes.json` is hand-authored geographic data, like a
registration seed: it lists the genuine enclosed lakes/seas to keep as water
(by interior seed pixel) when the mask pipeline distinguishes them from false
enclosed water (drawn rivers, flooded marshes). **As of 2026-08-22 no code reads
it**: `generate_coastline_mask.py`, now the sole owner of `land_sea_mask.png`,
classifies enclosed seas as water by coastline parity alone, needing no lake
list. The file (and `schema.load_inland_lakes`) is orphaned pending a decision to
keep or retire it.

`run_fixture.py --check` also regression-checks the source-driven pipeline itself
against committed synthetic fixtures, independent of the real `sources/`:
`tools/fixtures/ingest/` covers LUT classification, reprojection, segmentation,
compositing and river rasterization; `tools/fixtures/boundary/` covers the
boundary path (local-contrast ink, complement labelling, the `frame_alias` warp,
precedence stacking, mask intersection, nearest-label fill, density
reconciliation and sea zones). It also self-checks `worldgen/sea_zones.py`
in isolation (no golden fixture): a purple line drawn in the water splits it
into zones, a purple mark drawn on land is ignored, every water pixel ends up
labelled and no land pixel does, and two runs are byte-identical. It likewise
self-checks `worldgen/land_provinces.py` in isolation: a magenta line drawn on
land splits it into regions while a magenta mark in water is ignored, a
landmass dense with interior magenta is classed drawn and one bare of it a
placeholder, subdividing a drawn region never crosses the magenta boundary
while a placeholder region stays one province, every land pixel ends up
labelled and no water pixel does, and two runs are byte-identical.
`_selfcheck_drop_land_specks` (board #3705 follow-up) exercises
`generate_coastline_mask.drop_land_specks` — the durable fix for the anti-aliased
`xD3DC0A` "Western Ocean Mass" 1px state: sub-floor land components are
reclassified as water while a real island and every water pixel are untouched, the
floor is exclusive (a component of exactly `min_px` px survives), `min_px<=1` is a
no-op, a seam-straddling speck counts as one component under `wrap_x`, and two runs
are byte-identical.
It also self-checks the optional tiny-island override merge
(`land_provinces.island_override_zones` / `merge_island_overrides`, the fix for
a disconnected islet that can never qualify for `cells.merge_small`'s
share-a-border merge and so ships as its own micro state-region forever): a
blank override source draws no zones, distinct painted circles are distinct
zone ids, every region caught under the same zone is force-merged into one (a
circle over a single region is a no-op), the merge still tiles the land
exactly and is byte-identical across runs, and `subdivide` keeps such an
island-override archipelago whole (via the `keep_whole` set from
`land_provinces.override_fused_labels`) no matter how many seats its area earns.
A separate self-check (`_selfcheck_merge_fused`, board #3664) covers the
counterpart case: a **merge-fused** disconnected region (two non-touching drawn
regions unioned by `apply_land_region_merges`, not under an island circle, so
absent from `keep_whole`) is cut **per connected piece** — each piece gets its
own province(s), no province spans the two pieces, none is flagged an
archipelago — while the same region told to stay whole via `keep_whole` ships as
one non-contiguous province; two runs of the cut path are byte-identical.
Two more self-checks cover the lore-hubs machinery (board #3665):
`_selfcheck_seeded_cut` pins `cells.merge_small(protected=)` (a protected
sub-floor cell survives the merge floor that would otherwise fold it away),
`cells._farthest_seeds(fixed=)` (a fixed seed always comes first, and
`fixed=None` stays byte-identical to the original farthest-point path), and
`subdivide(region_seeds=)` end to end — every anchor gets its own province,
no anchor province crosses a magenta region boundary, an unseeded region
stays byte-identical to the `region_seeds=None` cut, an anchor in a
`keep_whole` archipelago or a non-drawn region hard-errors, the cut is
deterministic, and a `wrap_x=True` case exercises the seam-shift anchor
translation the production `WRAP_X` uses. `_selfcheck_hub_validator` exercises `validate_map._check_hub_anchors`
on a synthetic bitmap and state list: a clean port anchor passes; a port
anchor resolved onto a non-coastal, non-declared province fails; a missing
`HUB_NAME` loc key fails; and a stale index entry (resolved colour no longer
matching the anchor's province) fails.
`_selfcheck_province_terrains` (board #2968) exercises
`generate_province_terrains.py` and `validate_map.validate_province_terrains` in
isolation: land cells emit `"plains"` and sea cells `"ocean"`, lines are
sorted by integer id (not index order), two runs are byte-identical, an empty
cell list is refused rather than writing a truncated file, and the emitted file
round-trips cleanly through the validator, whose bijection and valid-id checks
each fail on a missing line, an extra line, and an undefined terrain id.
`_selfcheck_canon_cities` (board #3789) exercises the barrier-city tooling in
isolation: `schema.load_canon_cities` preserves authored order and refuses an
empty/bad-terrain/duplicate-anchor/out-of-canvas file; the pure, source-free
`render_canon_cities_preview.build_overlay_layer` builds a deterministic
(byte-identical across runs) canvas-sized RGBA layer with a transparent ground and
opaque markers (and `CANVAS_W/CANVAS_H == (8192, 3616)` is asserted directly rather
than allocating the 474 MB layer); and `validate_map._check_canon_cities` (returning
`(errors, warnings)`) passes a clean on-land city with no error/warning, raises a
hard **error** for an on-water anchor, raises a non-blocking **warning** (never an
error) for a city painted the impassable colour `(255,127,0)`, and runs the on-land
half alone when the export array is `None`. The check itself is **gated on
`tools/config/canon_cities.json` existing** (a clean skip when absent, the
`_check_adjacencies` idiom): given the catalogue, the **on-land** half always runs
off the committed `land_sea_mask.png` (an anchor on water is a hard error), while
the **impassable-collision** half is a **non-blocking warning** — a hold in the
range is expected, and the warning cues carving a passable pocket around it (flowing
through the full `validate_map.py` run's `warnings=` channel, printed but never
gating the exit code, the same convention as the lake guards) — and degrades to a
skip when the gitignored local export
(`sources/gimp_exports/terraqueous_globe_reprojected - impassable_terrain.png`) is
absent, so a device without that working file never reddens the committed gate.
`tools/render_canon_cities_preview.py` (the dev render) and its two
`tools/derived/` artifacts are outside the gate — gitignored, source-dependent,
regenerated only on the user's machine for a visual verdict.
`_selfcheck_river_extraction` (board #3703) exercises `worldgen/river_network.py`'s
flow-DAG model on synthetic cyan networks: a Y-junction stitches Strahler stems
with one green source per headwater and a red MERGE at the confluence (source
count == headwater count), streams run source-first, an anchor names exactly one
stream, the trunk widens downstream; an inland-terminating river is a valid
**endorheic** sink; a **lake→sea** river is one sea stream with a lake-fed source
(not a fork); a **delta** (one trunk, two sea mouths) and a **river-island** (split
then rejoin) are valid and paint yellow split markers; a sea-to-sea channel is a
`no-source` error unless a **manual flow override** orients it (mouth = furthest in
the compass direction, coastal source waived); only a sourceless closed ring is a
hard error; a short spur is pruned; a wrap-seam stem extracts under `wrap_x`; and
two runs are byte-identical. `_selfcheck_river_validator` exercises
`validate_map._check_rivers` on synthetic index arrays (with an `ocean` mask): a
clean rivers.png and an endorheic-inland and a lake-fed one all pass, while a
river pixel on sea, a source on the ocean coast, a lone split marker, and an
out-of-set index each fail.
`_selfcheck_stable_ids` (board #3705) exercises `worldgen/province_ids.assign` on
a small synthetic committed map spanning land, sea and lake: a **no-op** regen
(identical geometry) keeps every province's committed colour+id and is
**byte-identical** across two runs (this is the invariant that matters most in
practice — regenerating from unchanged sources must never reshuffle
`provinces.png`); removing a province retires its colour+id without disturbing
any survivor; splitting a region lets the dominant-overlap piece keep the
committed colour+id while the genuinely-new piece gets a fresh id at or past the
committed `id_high_water` and a colour reserved off every committed colour; a
land-count change leaves sea and lake colours untouched (the ripple this board
item fixes); `--reassign` (or no committed bitmap) reproduces the pre-#3705
fresh label-order allocation (`id == label`); and the assignment is order-invariant
(feeding the committed cells in a shuffled order changes nothing). A companion
round-trip through `validate_map.validate_provinces` proves the new structural id
invariants — positive, globally unique, a colour↔id bijection, and bounded by
`id_high_water` — pass on a clean map and fire on a duplicate id, a non-positive
id, and an id past the high-water.

`_selfcheck_land_state_numbers` (board #4188) is the land-region mirror of the
above, exercising `worldgen/land_state_numbering.assign_state_numbers` on a
small synthetic committed `land_state_ids.json`-shaped record: a **no-op**
regen (identical province-id sets) keeps every STATE number and is
byte-identical across two runs; removing a region retires its number without
disturbing any survivor; splitting a region lets the dominant-overlap piece
(by province area) keep the committed number while the new piece gets a fresh
one at the committed `state_number_high_water`; merging two committed regions
into one keeps the larger-overlap number and retires the smaller; `reassign`
(or no committed index) reproduces the pure `compute_state_numbers` Hilbert
bootstrap; the assignment is order-invariant (a shuffled committed-states list
changes nothing); and a non-empty committed index matching **zero** current
regions (the un-paired province-`--reassign` signature) falls back to the
bootstrap instead of retiring every state, warning loudly via its `log`
callback. A companion check exercises `seed_land_state_ids`'s pure block
parser + hex→stable-id mapping on a tiny synthetic state file (correctly
skipping `arable_land`/`naval_exit_id` and a nested `capped_resources` block).

`_selfcheck_sea_state_ids` (board #4191) is the sea-zone mirror, exercising
`worldgen/sea_state_ids.assign` on a small all-water synthetic zone layer (the
`_selfcheck_sea_naming` fixture shape) with **pixel-overlap** identity: a
**no-op** regen keeps every id+key and is byte-identical across two runs
(high-waters unchanged); removing a zone retires its id+key without disturbing a
survivor, and the high-water does not regress; a retired id is **never reused**
(a later new zone lands strictly above the high-water, not in the freed slot); a
new zone gets a fresh id at the high-water + a fresh non-colliding ordinal while
unrelated zones stay put; a **renamed** matched zone re-derives its key but keeps
its id, others byte-stable; **merged** zones keep a stable id and their shared
config key across an unrelated removal; `reassign` / no committed baseline is the
pre-#4191 label-order bootstrap (`id = SEA_ID_START + label - 1`, keys verbatim);
the assignment is order-invariant (a shuffled committed cell list changes
nothing) and deterministic across two runs; a **zero-overlap** collapse falls
back to the bootstrap with a loud `log` warning; **2+ new zones sharing a
brand-new slug** in one regen are all numbered (`_01`/`_02`, not bare + `_01`),
byte-identical to a reassign of the same geometry; and a **digit-suffixed**
display name ("Far Passage 3") recovers its slug via `_slugify`, not a
trailing-digit strip that would corrupt another slug's high-water.

## Regression rule

When fixing a bug confirmed via `logs/error.log` or in-game behavior, first reproduce it (capture the exact error line or observed behavior) before changing script, so the fix can be verified against the same reproduction step afterward.

## Rules

- Never claim a change is "tested" without having loaded the mod in-game and checked `logs/error.log`.
- Never edit `logs/error.log` or any game-owned file to make an error disappear — fix the source in this mod.
