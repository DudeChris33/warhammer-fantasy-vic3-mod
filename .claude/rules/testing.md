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
script. Before committing anything under `map_data/`, `common/strategic_regions/`,
the map localization, or the source-registration data (`tools/SOURCES.md`,
`tools/registration/`), run:

```
python tools/worldgen/sources.py --verify       # source manifest SHA-256 + registration cross-checks
python tools/validate_map.py --province-bitmap   # province bitmap tiles the mask + agrees with its index and the sea layer, and (if present) province_terrains.txt
python tools/validate_map.py --sea               # sea engine files: 99_seas colours ⊆ sea_starts ⊆ provinces.png sea colours; every sea state grouped + localized
python tools/run_fixture.py --check              # regression-checks the toolchain itself against synthetic fixtures
python tools/validate_map.py                     # full crosscheck (needs both sea + land state files)
```

`--sea` is the sea-only subset (`99_seas.txt`, `default.map` `sea_starts`,
`water_strategic_regions.txt`, the sea loc) — useful when only the sea side
changed. The full no-flag `validate_map.py` needs every province colour claimed
by a state, land and sea both.

All must pass before the in-game `error.log` check below — this doesn't replace
the game load, it catches the offline-detectable error class first. `sources.py
--verify` confirms the local `sources/` files still match the committed
SHA-256 manifest; a swapped/edited source that would silently change a
committed bitmap fails here. Refreshing the manifest after an *intentional*
source change is the explicit `python tools/worldgen/sources.py
--update-manifest` — never a side effect of a generator run. Registration
records (`tools/registration/*.json`) are likewise machine-fitted, not
hand-written: re-derive with `python tools/fit_registration.py --seed <stem>`
after editing the seed in `tools/registration/seeds/`.

## Regeneration pipeline

The mask moves first; every downstream layer regenerates from it, in this order:

```
generate_coastline_mask.py → generate_heightmap.py → generate_rivers.py →
generate_state_labels.py → generate_sea_zones.py → generate_provinces.py →
generate_sea_regions.py + generate_land_regions.py →
generate_province_terrains.py → generate_adjacencies.py --write →
generate_arable_heatmap.py
```

**A `generate_provinces.py` regen invalidates every downstream, colour-keyed
emitter** (sea regions, land regions, province terrains, adjacencies, arable
heatmap) even when only a few provinces actually moved — always re-run the
full chain from `generate_provinces.py` onward, then the offline gate above,
before committing. Colour/id/STATE-number/sea-zone-key stability across a
regen is handled by overlap-matching against the previously committed output
(`province_ids.assign`, `land_state_numbering.assign_state_numbers`,
`sea_state_ids.assign`) — an unchanged province/region/zone keeps its
committed identity; only genuinely new or removed geometry reassigns, off a
monotonic high-water mark that never reuses a retired id (`id_high_water` in
`provinces_index.json`, `state_number_high_water` in `land_state_ids.json`,
`sea_id_high_water`/`ordinal_high_water` in `sea_zones_index.json`). Each
generator's `--reassign` flag is the escape hatch that instead re-allocates
every id fresh in label order (pair a province `--reassign` with the land/sea
`--reassign`s, or overlap-matching has nothing to match against and falls back
with a loud warning).

Per-stage notes:

- **`generate_coastline_mask.py`** is the sole owner of `tools/derived/land_sea_mask.png`. Default mode flood-fills the traced coastline in `oldworld-first/land_sea_mask.png` (binarized first via `binarize_cyan_mask.py`); `--from-fill` reads a finished black/white land fill directly instead and additionally emits the companion `tools/derived/lake_mask.png`. Either mode drops isolated sub-4px land components to water first (`drop_land_specks`, `--speck-max` overrides the floor).
- **`generate_heightmap.py` / `generate_rivers.py` / `generate_state_labels.py`** consume the mask; write `map_data/heightmap.png`, `map_data/rivers.png` (see Rivers below), `tools/derived/state_labels.png`.
- **`generate_sea_zones.py`** flood-fills the hand-drawn purple sea-zone network into `tools/derived/sea_zones.png` + `tools/derived/sea_zones_index.json` (canon `key`/`id`/`display_name`/`sea_group`, 3000+ id band). Excludes lake pixels via `sea_zones.extract`'s `exclude=` when `lake_mask.png` exists. Runs *before* `generate_provinces.py`, so zone identity across regens is zone-layer pixel overlap.
- **`generate_provinces.py`** writes `map_data/provinces.png` (8192×3616, Git-LFS) + `tools/derived/provinces_index.json` (id/colour/area/coastal/impassable/placeholder per province) + `tools/derived/land_regions_index.json` (region→province grouping). Land geometry comes from `tools/worldgen/land_provinces.py`, which flood-fills the hand-drawn magenta state-region network into regions and subdivides each into provinces (no province crosses a magenta line); an out-of-scope continent with no interior magenta becomes one passable placeholder province. Sea provinces fold in the already-committed `sea_zones.png` labels. When `lake_mask.png` exists, lake provinces (`kind:"lake"`, impassable, informational — lakes are stateless) are threaded in as a third class via `tools/worldgen/lakes.py`. Also handles: an optional tiny-island override layer (force-merges painted circles of disconnected islets into one province each, via `land_provinces.island_override_zones`/`merge_island_overrides`); merge-fused disconnected regions (`tools/config/land_region_merges.json`, cut per connected piece, seats shared by area); impassable terrain (below); city blobs (below); lore-hub anchors (below).
- **`generate_sea_regions.py`** (sea-side emitter) joins `provinces_index.json` with `sea_zones_index.json` and writes `map_data/state_regions/99_seas.txt`, block-replaces `map_data/default.map`'s `sea_starts` and `lakes` blocks, `common/strategic_regions/water_strategic_regions.txt`, and `localization/english/map/wh_seas_l_english.yml`. Also creates a header-only `map_data/adjacencies.csv` if absent (never clobbers a populated one).
- **`generate_land_regions.py`** (land-side emitter) joins `land_regions_index.json` with `provinces_index.json` and `sea_zones_index.json` (naval-exit resolution by land↔sea adjacency), routes each region through `tools/worldgen/land_naming.py` for realm (pixel-plurality vote against a painted strategic-region overlay, `tools/config/strategic_region_colors.json`) and canon name (from the hand-edited `tools/config/land_regions_worksheet.csv`, or `tools/config/out_of_scope_continents.json` for placeholders), and writes `map_data/state_regions/NN_<stem>.txt` (all 20 files), the per-continent `common/strategic_regions/*_strategic_regions.txt`, `localization/replace/english/map/states_l_english.yml`, and `localization/english/map/wh_hub_names_l_english.yml`. Also writes `tools/derived/land_state_ids.json` (STATE-number identity authority, seeded once via `tools/seed_land_state_ids.py` off a committed git ref).
- **`generate_province_terrains.py`** writes `map_data/province_terrains.txt` (one `x<HEX>="terrain"` line per province — land `"plains"`, sea `"ocean"`, lake `"lakes"`, all three defined in `common/terrain/01_terrain.txt`). Checked by `validate_map.py --province-bitmap` when present; absence is a clean skip, not an error (deferred until the province cut settles).
- **`generate_adjacencies.py`** (core in `tools/worldgen/adjacencies.py`) reads a hand-drawn flat yellow line layer and writes `map_data/adjacencies.csv` plus, for canal crossings, `common/strait_definitions/canals.txt` and `localization/english/map/wh_canals_l_english.yml`. Lines are typed by hand in the regenerate-through `tools/config/adjacency_worksheet.json` (identity = endpoint coordinates, 4px tolerance; `type` is `sea` (land↔land) or a `canal_*` (sea↔sea)). `--review` (default) writes gitignored preview/table files and lists skipped lines; `--sync` rewrites the worksheet after a redraw (matches existing rows by endpoint, parks unmatched rows under `stale`, never deletes); `--write` emits the CSV/strait files; `--check` asserts they're current. A canal crossing is drawn as a 4-arm "+"/"X" junction (sea-to-sea CSV row + two flanking land provinces the strait-definitions block needs); the junction's sea pair is exempt from the normal touching-provinces skip. `AdjacencyRow` supports `land_a_color`/`land_b_color` escape-hatch fields and `strait_type` (`natural`|`artificial`, default `natural`) — an `artificial` canal additionally needs `common/buildings`/`common/production_methods` entries this schema does not author.
- **`generate_arable_heatmap.py`** is an offline upstream artifact, not a game-loaded file: composes `tools/worldgen/arable.py`'s `build_field` (climate·terrain·hydrology·rain-shadow moisture·lore, masked off water/lake/impassable) from the committed mask/heightmap/rivers plus `tools/config/arable_lore.json` (breadbasket/blight zones), writing the committed `tools/derived/arable_heatmap.png` + `arable_heatmap_index.json`. `--check` re-derives to a temp and asserts byte-identity. No in-game gate; the rendered preview is the human acceptance gate. Known limitation: the field is built world-wide, and the out-of-scope far-eastern heightmap carries baked-in region-label text ("GRAND CATHAY") as elevation that surfaces as suppressed text there — the in-scope Old World heightmap is clean.

### Rivers

`map_data/rivers.png` is **source-driven, not heightmap-derived**: canon rivers
are hand-traced as a pure-blue line network on the canvas.
`tools/worldgen/river_network.py` skeletonizes it, builds a topological-adjacency
graph, and orients each network into a flow DAG (BFS-distance-to-outlet →
elevation → pixel, guaranteed acyclic). This makes divergence first-class:

- **Lakes** are distinguished from the ocean (`worldgen.lakes.classify`); a
  lake-fed river sources at the lake, a lake↔sea/lake↔lake river is not a fork.
- **Endorheic** rivers dry up at an inland sink — no marker, no ocean outlet
  required.
- **Splits** (deltas, river-islands) paint the vanilla yellow split marker
  (index 2) on each distributary.
- A network the tool can't auto-orient (most often both ends reach the sea, no
  headwater) is reported `no-source` and must get a manual entry in the
  hand-authored `tools/config/river_overrides.json` (anchor + compass `flow`;
  waives the coastal-source requirement).

Naming is opt-in: `tools/config/canon_river_names.json` pins each river name to
an anchor on its drawn line, resolved to exactly one stream;
`tools/derived/rivers_index.json` (name → mouth/length/width/state-keys) is
emitted for other tools to consume. `validate_map.py`'s `_check_rivers` is
gated on `canon_river_names.json` existing (also checks (river, state)
coverage when `tools/config/canon_rivers.csv` exists) — absent, the
generator's own `worldgen.rivers._validate` still owns correctness at emit
time. `generate_rivers.py` reads the
committed mask + the trace + the heightmap, so a province regen does **not**
invalidate `rivers.png` itself — but re-run `generate_rivers.py` after one if
`rivers_index.json`'s `state_keys` need to be current.

### Lakes, impassable terrain, city blobs, lore hubs

- **Lakes**: `generate_provinces.py` threads a third province class (`kind:"lake"`, impassable, informational — lakes are stateless) through `tools/worldgen/lakes.py` when `lake_mask.png` exists; excluded from sea-zone extraction via `sea_zones.extract`'s `exclude=`, and declared only in `default.map`'s `lakes` block (never a `99_seas` state, water strategic region, or loc). `validate_map.py --province-bitmap` prints two **non-blocking** `WARNING`s (a separate `warnings` channel that never fails the gate — a legit large/small lake may exist, the render is the final verdict): a lake over `lakes.OCEAN_WARN_FRACTION` of the world ocean's area (possibly a sealed-off navigable sea) and a lake below `lakes.LAKE_REPORT_MIN` (likely fill speckle — the remedy is drop-or-redraw, never merge, since a lone lake speck has no lake neighbour to merge into). Each lake cell also carries `ocean_area_fraction` in the index.
- **Impassable land**: `generate_provinces.py` reads a flat-colour impassable
  layer and `land_provinces.subdivide_ex` cuts each painted region into passable
  pieces plus one impassable province per connected paint tract (empty/absent
  layer is dormant). No automatic pocket is cut around a canon city — the paint
  is taken as drawn, so a city that ends up sealed in needs the paint reworked
  by hand (`render_canon_cities_preview.py`'s transparent overlay is the tool
  for painting around catalogued holds). `tools/derived/canon_city_provinces_index.json` persists
  each catalogued canon-city anchor→province so the validator can prove no city
  is sealed in. Regenerate order after a paint change: `generate_provinces.py`
  → `generate_sea_regions.py` + `generate_land_regions.py` → the offline gate.
  `validate_map.py`'s `_check_impassable_land` checks state/index agreement, no
  fully-impassable state, passable-province connectivity (pixel adjacency +
  `adjacencies.csv` tunnels), and canon-city reachability.
- **City blobs**: `generate_provinces.py` reads a `cities` layer unconditionally;
  `land_provinces.city_blobs` + `unify_city_blobs` keeps each painted city blob
  under one province (hub-anchor-bearing province wins ties). A blob straddling
  a state border or paint edge by more than 4px is a hard error; up to 4px is a
  clipped graze. `validate_map._check_city_blobs` verifies every blob is one
  province colour.
- **City seeding**: every city dot on that same `cities` layer also seeds its
  own province, not just the hub-anchor ones. `land_provinces.city_dots` reduces
  each blob to its centroid anchor pixel (snapped onto the blob, land-only,
  sorted deterministically); `generate_provinces.py` forwards the list to
  `land_provinces.subdivide_ex` as `city_seeds` (with `city_seed_sep =
  MIN_ANCHOR_SEP`, the same separation floor as hub anchors). A dot is skipped
  (and logged) when it lands on a keep-whole archipelago, a non-drawn
  (placeholder) region, impassable paint, or within `city_seed_sep` px of an
  already-accepted seed in its region — hub anchors keep priority over city
  seeds when both are present. This is separate from the city-blobs behavior
  above: blobs keep a painted town from being *split* across provinces, seeding
  additionally guarantees every town gets its *own* province rather than
  sharing one with unrelated land. `tools/run_fixture.py --check`'s
  `_selfcheck_city_seeds` covers the skip conditions and the seed/hub-anchor
  interaction.
- **Lore hubs**: `tools/config/hub_worksheet.json` (hand-authored, regenerate
  through) pins each named settlement to a canvas anchor; `generate_provinces.py`
  seeds a distinct province there (hard error on an anchor in water, in a
  keep-whole archipelago, or too close to another anchor) and writes
  `tools/derived/hub_anchors_index.json` (the anchor→province authority).
  Hub picking itself reuses `tools/worldgen/statefile.pick_hubs`, falling back
  to `statefile.stack_hubs` (cycling `city`/`farm`/`mine`/`wood` across
  whatever passable provinces a small or placeholder state has, legal per
  vanilla's own `STATE_MALTA` precedent) when a state has too few passable
  provinces for `pick_hubs`. `generate_land_regions.py` preassigns each listed hub and emits
  `wh_hub_names_l_english.yml`. A `stack_on: <host hub>` row shares its host's
  exact pixel (a second hub in the same province, e.g. a port beside a capital)
  without seeding its own province. Any worksheet change forces the full
  `generate_provinces.py` → `generate_sea_regions.py` + `generate_land_regions.py`
  → re-validate cascade, since a seeded anchor reshuffles every province colour.
  `validate_map.py`'s `_check_hub_anchors` proves every anchor is land in its
  own declared state, a `port` is coastal, and its `HUB_NAME` key exists.

### Hand-authored inputs (edit deliberately, regenerate through — never inferred)

`tools/registration/seeds/`, `tools/config/inland_lakes.json` (currently
orphaned — nothing reads it since coastline classification moved to pure
parity), `tools/config/land_region_merges.json`, `tools/config/
strategic_region_colors.json`, `tools/config/land_regions_worksheet.csv`,
`tools/config/hub_worksheet.json`, `tools/config/canon_river_names.json`,
`tools/config/river_sources.json`, `tools/config/river_overrides.json`,
`tools/config/canon_cities.json`, `tools/config/adjacency_worksheet.json`,
`tools/config/arable_lore.json`.

### Dev-only review renders (outside the gate, gitignored `tools/derived/` output)

`tools/render_provinces_preview.py`, `tools/render_land_regions_preview.py`
(drapes the real parchment art under tinted regions via
`tools/project_regions_unified.py`'s triangle-warp registration; round-trips
names already committed in `land_regions_worksheet.csv` forward, never
overwrites them), `tools/render_hubs_preview.py`,
`tools/render_canon_cities_preview.py` (also emits a transparent overlay layer
for painting impassable terrain around catalogued holds),
`tools/render_rivers_preview.py`, `tools/render_arable_preview.py`,
`tools/render_cr_lookup_overlay.py`. `tools/tww3_name_lookup.py` is a read-only
canon-naming lookup CLI against the gitignored third-party
`sources/cr_oldworld_campaign/` dump — clean-skips when that source is absent,
never writes to `tools/config/` directly (only gitignored suggestion reports).

### Self-check coverage

`python tools/run_fixture.py --check` regression-checks every generator module
above (coastline mask, rivers, sea/land province cuts, stable-id assignment,
impassable terrain, city blobs, lore hubs, adjacencies/canals, arable field,
the .ora source reader) against committed synthetic fixtures, independent of
the real `sources/` tree — see the file itself for what each self-check covers
rather than this doc.

## Regression rule

When fixing a bug confirmed via `logs/error.log` or in-game behavior, first reproduce it (capture the exact error line or observed behavior) before changing script, so the fix can be verified against the same reproduction step afterward.

## Rules

- Never claim a change is "tested" without having loaded the mod in-game and checked `logs/error.log`.
- Never edit `logs/error.log` or any game-owned file to make an error disappear — fix the source in this mod.
