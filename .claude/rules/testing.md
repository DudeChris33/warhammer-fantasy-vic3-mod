---
paths:
  - "map_data/**/*"
  - "mapgen/**/*"
  - "sources/**/*"
  - "common/strategic_regions/**/*"
  - "common/strait_definitions/**/*"
  - "common/defines/**/*"
  - "gfx/map/**/*"
  - "localization/**/map/**/*"
---

# Map pipeline, sources and offline gate

**Read when:** you are touching `map_data/`, `mapgen/`, `sources/`, strategic regions, straits, `gfx/map/`, or the generated map loc. The in-game `error.log` gate that this file used to open with now lives in [core.md](core.md). **Covers:** canvas and scope, sources, the tooling loop, the offline gate, the regeneration pipeline and its invariants, generated-file ownership, hand-authored inputs, name citations and map-keyed vanilla overrides. Loads automatically when you open a matching file with the Read tool — a starting point, not a boundary: read any other guide that would help, and read a neighbour whenever your work touches its area.

**Related guides:**
- [localization.md](localization.md) — generated state, hub, sea and canal name files; the `STATE_AQUITAINE` collision rule
- [scripting.md](scripting.md) — defines, strategic regions and the general script rules
- [interface.md](interface.md) — generated map-object locators under `gfx/map/`
- [peoples.md](peoples.md) — tag capitals point at generated `STATE_*` ids
- [../../mapgen/MAP_RUNBOOK.md](../../mapgen/MAP_RUNBOOK.md) — desktop-client (map editor) steps

Per-script mechanics live in each `mapgen/generate_*.py` module docstring — read the docstring, not this file, for what a stage reads and writes. This guide keeps what a docstring can't: ordering, ownership, invariants, gotchas and stop points.

## Canvas, scope and sources

- The canvas is **8192×3616**, a Miller projection pinned to a line the user drew; the frame constants live in `mapgen/config/canvas_frame.py` and `map_config.py`. Vanilla's own frame is the reference for formats and sizes.
- **Scope**: the drawn Old World land regions, all oceans (global), and placeholder regions for the out-of-scope land, seeded by `mapgen/config/out_of_scope_continents.json` (`land_regions_index.json` records `drawn_regions` vs `placeholder_regions`).
- `sources/` is **git-ignored and local-only** (third-party IP). Provenance is the SHA-256 manifest `mapgen/SOURCES.md` plus `mapgen/registration/*.json`; `python mapgen/worldgen/sources.py --verify` checks it. A hand-painted GIMP master's OpenRaster `.ora` export is read **by layer name** through the committed `mapgen/config/source_layers.json`. Choosing, adding or marking up imagery is Chris's; `--update-manifest` follows an intentional source change and is never a side effect of a generator run.
- Registration records (`mapgen/registration/*.json`) are machine-fitted, not hand-written: edit a seed in `mapgen/registration/seeds/` and re-derive with `python mapgen/fit_registration.py --seed <stem>`.
- Better source beats more tuning: if an extraction is capped by its source, say so and ask for imagery rather than tuning thresholds.

## The tooling loop

Run this autonomously to convergence: edit a generator, LUT, seed or hand-authored input → re-derive (`fit_registration.py`, then the regeneration pipeline below) → run the offline gate → **render the map and send the PNG** → read it, diagnose, go again. A green gate is a precondition, never a stopping point; the rendered map is the real gate and Chris's verdict is final (see [core.md](core.md)). Review renders overlay cells on the reprojected globe (`terraqueous_globe_reprojected.png`, 1:1 with the canvas), never the native `terraqueous_globe.jpg`.

## Offline gate (pre-commit lint)

One-time setup: a local `mapgen/.venv` (git-ignored), deps pinned in `mapgen/requirements.txt`. Before committing anything under `map_data/`, `common/strategic_regions/`, the map localization, or the source-registration data, run:

```
python mapgen/read_state_ownership.py --check     # state_ownership.json is current with the painted PNG + map_data
python mapgen/generate_state_history.py --check   # common/history/states is current with state_ownership.json
python mapgen/generate_pop_history.py --check     # common/history/pops + population are current with mapgen/config/pop_history and resolve
python mapgen/generate_country_history.py --check # common/history/countries is current with the owners + tiers
python mapgen/worldgen/sources.py --verify        # source manifest SHA-256 + registration cross-checks
python mapgen/validate_map.py --province-bitmap    # bitmap tiles the mask, agrees with its index and the sea layer
python mapgen/validate_map.py --sea                # sea engine files (colours, sea_starts, grouping, loc)
python mapgen/run_fixture.py --check               # regression-checks the toolchain against synthetic fixtures
python mapgen/validate_map.py                      # full crosscheck (needs both sea + land state files)
```

All must pass before the in-game `error.log` check; they catch the offline-detectable error class first and do not replace the game load. `validate_map.py --labels` lints the state-label layer instead of the province map. `validate_map.py --province-bitmap` prints non-blocking `WARNING`s (a separate channel that never fails the gate): a lake over `lakes.OCEAN_WARN_FRACTION` of the world ocean (possibly a sealed-off sea) and one below `lakes.LAKE_REPORT_MIN` (likely fill speckle — drop or redraw, never merge). `run_fixture.py --check` covers every generator module against committed fixtures, independent of `sources/`. Full `validate_map.py` also checks `common/history/states` against `map_data`, `state_ownership.json`, the defined (non-dynamic) country tags and the homelands (every `add_homeland` id must be a `common/cultures` id and equal the owners' `cultures`); an unowned or out-of-scope state without its `c:UNO` block fails as an owner mismatch, and an owner tag with no definition (`UNO` included) is held back by the generator and fails the gate (`HELD_BACK_IS_ERROR`). A `--check` that byte-compares a generated text file normalizes a BOM and `\r\n` first: `core.autocrlf` checks the committed LF files out as CRLF.

## Regeneration pipeline

The mask moves first; every downstream layer regenerates from it, in this order:

```
generate_coastline_mask.py --from-fill → generate_heightmap.py → generate_rivers.py →
generate_state_labels.py → generate_sea_zones.py → generate_provinces.py →
generate_sea_regions.py + generate_land_regions.py →
read_state_ownership.py → generate_state_history.py → generate_country_history.py →
generate_province_terrains.py → generate_adjacencies.py --write →
generate_arable_heatmap.py
```

- **A `generate_provinces.py` or `generate_land_regions.py` regen stales the starting ownership.** `state_ownership.json` and `common/history/states` are colour- and state-keyed, so re-run `read_state_ownership.py` then `generate_state_history.py`; the read may hard-error (a province with no votable pixel, a new state) and need a repaint, which is Chris's.

- The coastline source is a black/white land **fill**, so always pass `--from-fill` (the parity-trace default is legacy, `generate_coastline_mask.py`). `--from-fill` also emits `mapgen/derived/lake_mask.png`; either mode first drops isolated sub-4px land components (`drop_land_specks`, `--speck-max`).
- **A `generate_provinces.py` regen invalidates every downstream, colour-keyed emitter** (sea regions, land regions, province terrains, adjacencies, arable heatmap) even when few provinces moved — always re-run the full chain from `generate_provinces.py` onward, then the offline gate, before committing.
- **Identity is stable across regens.** Province colour = province id in Vic3, so ids must not churn. `province_ids.assign`, `land_state_numbering.assign_state_numbers` and `sea_state_ids.assign` overlap-match against the previously committed output; only genuinely new or removed geometry is reassigned, off a monotonic high-water mark that never reuses a retired id (`id_high_water` in `provinces_index.json`, `state_number_high_water` in `land_state_ids.json`, `sea_id_high_water`/`ordinal_high_water` in `sea_zones_index.json`).
- `--reassign` (on `generate_provinces.py`, `generate_land_regions.py` and `generate_sea_zones.py`) is the escape hatch that re-allocates ids fresh in label order. Pair a province `--reassign` with the land and sea ones, or overlap-matching has nothing to match against and falls back with a loud warning.
- **State borders are frozen; province cuts may move.** State borders are the user-drawn `full.ora#borders` layer on the canvas (consumed directly by `land_provinces.py`). Redraw provinces through the generator (e.g. to place hubs), never state borders. Merged regions (`mapgen/config/land_region_merges.json`) ship as one province per connected piece.
- `generate_sea_zones.py` runs *before* `generate_provinces.py`, so zone identity across regens is zone-layer pixel overlap. The purple-network zones are authoritative; ocean-current auto-generation is reference-only (its "centre on the current limb" rule is worth keeping).
- `generate_land_regions.py` writes all 20 land files `map_data/state_regions/NN_<stem>.txt`, the per-continent `common/strategic_regions/*_strategic_regions.txt`, `localization/replace/english/map/states_l_english.yml` and `localization/replace/english/map/wh_hub_names_l_english.yml`, plus `mapgen/derived/land_state_ids.json` (STATE-number authority, seeded once by `mapgen/seed_land_state_ids.py` off a committed git ref). `generate_sea_regions.py` writes `99_seas.txt`, block-replaces `default.map`'s `sea_starts` and `lakes`, the water strategic regions and `wh_seas_l_english.yml`, and creates a header-only `adjacencies.csv` if absent (never clobbers a populated one).
- `generate_province_terrains.py` writes `map_data/province_terrains.txt` (land `plains`, sea `ocean`, lake `lakes`); `validate_map.py --province-bitmap` checks it when present.
- `generate_arable_heatmap.py` is an offline upstream artifact (`mapgen/derived/arable_heatmap*.{png,json}`), not game-loaded; its rendered preview is the acceptance gate. Known limitation: the field is built world-wide and the out-of-scope far-eastern heightmap carries baked-in label text as elevation; the Old World heightmap is clean.

### Generated files and their owners

| Owner | Files |
|---|---|
| `generate_coastline_mask.py` | `mapgen/derived/land_sea_mask.png`, `lake_mask.png` |
| `generate_heightmap.py` | `map_data/heightmap.png` (the packed `heightmap.heightmap`, `packed_heightmap.png`, `indirection_heightmap.png`, `nodes.dat` come from the in-game map editor — `mapgen/MAP_RUNBOOK.md`) |
| `generate_rivers.py` | `map_data/rivers.png`, `mapgen/derived/rivers_index.json` |
| `generate_state_labels.py` | `mapgen/derived/state_labels.png`, `state_labels_index.json`, `COVERAGE.md` |
| `generate_sea_zones.py` | `mapgen/derived/sea_zones.png`, `sea_zones_index.json` |
| `generate_provinces.py` | `map_data/provinces.png`, `mapgen/derived/provinces_index.json`, `land_regions_index.json`, `hub_anchors_index.json`, `canon_city_provinces_index.json` |
| `generate_sea_regions.py` | `map_data/state_regions/99_seas.txt`, `default.map` `sea_starts`/`lakes`, `common/strategic_regions/water_strategic_regions.txt`, `localization/english/map/wh_seas_l_english.yml` |
| `generate_land_regions.py` | `map_data/state_regions/00–19_*.txt`, the other `*_strategic_regions.txt`, `states_l_english.yml`, `wh_hub_names_l_english.yml`, `mapgen/derived/land_state_ids.json` |
| `generate_province_terrains.py` | `map_data/province_terrains.txt` |
| `generate_adjacencies.py --write` | `map_data/adjacencies.csv`, `common/strait_definitions/canals.txt`, `localization/english/map/wh_canals_l_english.yml` |
| `generate_arable_heatmap.py` | `mapgen/derived/arable_heatmap.png`, `arable_heatmap_index.json` |
| `read_state_ownership.py` | `mapgen/derived/state_ownership.json` (per-`STATE_*` owner, or split owners with province ids, read from `state_ownership.png`) |
| `generate_state_history.py` | `common/history/states/00–19_*.txt` (one per land state-region file; `create_state` per owner — the `unowned` and `placeholder` tokens map to `c:UNO`, so every land state, out-of-scope ones included, has an owner (#6391) — then one `add_homeland = cu:<culture>` per culture of the owner tags' `cultures`: derived, no override table, `UNO` gets none (#6374); header-only only where a file has no state, today 08, 11, 12, 14) |
| `generate_pop_history.py` | `common/history/pops/00–19_*.txt` and `common/history/population/00–19_*.txt` (same names as the state-region files; `create_pop` per (state, owner) from `mapgen/config/pop_history/`, `POPULATION` wealth/literacy per tag; header-only where nothing is owned) |
| `generate_country_history.py` | `common/history/countries/00_start_setup.txt` (one `c:TAG ?= { }` per tag that owns a state, `UNO` included whenever any state is unowned or out-of-scope: starting-technology effect from its definition `tier` plus `effect_starting_politics_traditional`; placeholder-grade, #6375) |
| `fit_registration.py` | `mapgen/registration/*.json` |
| engine (copy from `Documents/.../Victoria 3/generated/` after a load reports an incomplete locator) | `gfx/map/map_object_data/generated_map_object_locators_*` |

### Rivers, lakes, impassable land, cities, hubs

- **Rivers** are source-driven: canon rivers are hand-traced as a pure-blue network (`full.ora#rivers`); `worldgen/river_network.py` orients each network into a flow DAG. A network the tool can't auto-orient is reported `no-source` and needs a manual entry in `mapgen/config/river_overrides.json`. Naming is opt-in via the optional `mapgen/config/canon_river_names.json` (and `river_sources.json`; `canon_rivers.csv` adds (river, state) coverage) — read only if present. A province regen does not invalidate `rivers.png`, but re-run `generate_rivers.py` after one if `rivers_index.json`'s `state_keys` must be current.
- **Lakes** are a third province class (`kind:"lake"`, impassable, stateless): declared only in `default.map`'s `lakes` block, never a `99_seas` state, water strategic region or loc.
- **Impassable land**: a flat-colour layer cut into one impassable province per connected paint tract. No pocket is cut around a canon city — the paint is taken as drawn, so a sealed-in city needs the paint reworked by hand (`render_canon_cities_preview.py` emits a transparent overlay for that). `validate_map._check_impassable_land` proves connectivity and canon-city reachability.
- **City blobs and seeding**: a painted city blob stays in one province (a blob straddling a state border or paint edge by more than 4px is a hard error; up to 4px is a graze); every city dot also seeds its own province (`city_dots`, skipped and logged when it lands on a keep-whole archipelago, placeholder region, impassable paint, or within `MIN_ANCHOR_SEP` of another seed; hub anchors win).
- **Lore hubs**: `mapgen/config/hub_worksheet.json` pins each named settlement to a canvas anchor; `generate_provinces.py` seeds a distinct province there (hard error on an anchor in water, in a keep-whole archipelago, or too close to another). A `stack_on: <host hub>` row shares its host's pixel. Any worksheet change forces the full `generate_provinces.py` → `generate_sea_regions.py` + `generate_land_regions.py` → re-validate cascade, since a seeded anchor reshuffles every province colour.
- **Adjacencies**: Chris draws non-touching crossings as flat yellow lines (`terraqueous_globe_reprojected - adjacencies.png`); each is typed by hand in `mapgen/config/adjacency_worksheet.json` (identity = endpoint coordinates, 4px tolerance; `type` `sea` or `canal_*`). `--review` (default) writes gitignored previews; `--sync` re-anchors the worksheet after a redraw and never deletes (unmatched rows park under `stale`); `--write` emits; `--check` asserts current. An `artificial` canal additionally needs `common/buildings`/`common/production_methods` entries this schema does not author.

### Hand-authored inputs (edit deliberately, regenerate through — never inferred from generator output)

`mapgen/registration/seeds/`, `mapgen/config/land_region_merges.json`, `mapgen/config/pop_history/` (`state_weights.json` there is derived: `generate_pop_history.py --refresh-weights`), `strategic_region_colors.json`, `land_regions_worksheet.csv`, `hub_worksheet.json`, `river_overrides.json`, `canon_cities.json`, `adjacency_worksheet.json`, `arable_lore.json`, `out_of_scope_continents.json`, `state_border_overrides.json`, `sea_zones.json`, `state_ownership.png` (the painted starting owner of every drawn state, flat exact-RGB fills; `render_state_ownership.py` only bootstraps it from `state_ownership_proposal.json`, never overwrites a repaint without `--force`) with its colour key `state_ownership_legend.json`, and the optional `canon_river_names.json` / `river_sources.json` / `canon_rivers.csv`. `mapgen/config/inland_lakes.json` is orphaned: no generator reads it (only comments and an unused `schema.load_inland_lakes` mention it).

`mapgen/config/country_history/NN_<stem>.json` is the same kind of input for a different consumer: the per-tag starting laws, tech tier, ruling IGs, taxes and institutions that a later task turns into `common/history/countries/`. Nothing reads it yet; `python mapgen/validate_country_history.py` is its gate (unknown ids, law-group cardinality, unlock/disallow rules, government-type trigger, source/why bookkeeping) and `run_fixture.py --check` regression-tests that linter. Schema, the tech-tier calibration and the mechanics gaps are in `mapgen/config/country_history/README.md`.

### Dev-only review renders (gitignored `mapgen/derived/` output, outside the gate)

`mapgen/render_*_preview.py`, `render_cr_lookup_overlay.py` and `qa_overlay.py` (produces the `qa_*.png` overlays on demand; absent until rendered). `render_land_regions_preview.py` round-trips names already committed in the worksheet forward and never overwrites them. `mapgen/tww3_name_lookup.py` is read-only, clean-skips when `sources/cr_oldworld_campaign/` is absent, and never writes `mapgen/config/`.

## Name citations: the `source` convention

Every hand-authored place name carries a **citation**, so canon can be told from invention without re-litigating it:

- `mapgen/config/hub_worksheet.json` — each `HubRow` has a required `source` (a canon citation or the literal `invented`); blank is a schema error. Canon names come first; coin one only where canon is silent, and flag it `invented`.
- `mapgen/config/land_regions_worksheet.csv` — a trailing `source` column, additive (blank is legal for names that predate the convention). `name` and `source` are carried across a regen together by the same anchor relocation (`render_land_regions_preview.py`), never separately.

A name from the TWW3 Old World mod region table is cited `canon: cr_oldworld_campaign/<slug> (TWW3 Old World mod region table)` (`SOURCE_TEMPLATE` in `mapgen/tww3_name_lookup.py`). That table is ChaosRobie's third-party Old World mod, used with his explicit permission — not Creative Assembly/Sega content. The lookup **never writes either file**: it emits suggestions into gitignored `mapgen/derived/` for a human to accept, because the registration it samples through is provisional and the table is settlement-scale while our regions are province-scale (a hit is often a town *inside* the region). Land not drawn in `sources/originals/tww3_old_world_mod_parchment_cropped.png` is out of scope for naming; its **alpha channel** is the extent (the bounding box is the whole image and proves nothing), and a name resolved outside it is discarded.

Canon-city anchors (`mapgen/config/canon_cities.json`) are read off Chris's cyan dots on `sources/terraqueous_globe_reprojected - canon_cities.png` (canvas frame; detect `g>170 & b>170 & r<130`, cluster centroids). On the Games Workshop map "Cragmere" is Karak Varn.

## Standing decisions and lessons

- **The picture is the gate.** Every offline check was green while the map was visually unusable; render, send, and wait for Chris's verdict ([core.md](core.md)).
- **Canvas.** Miller cylindrical, `Y0 = 2142.0` pinned to a line Chris drew (band +74.9°N/−57.4°S), 8192×3616; no installed mod deviates from vanilla's dimensions. Chris communicates geometry by drawing on a copy of a source image: recover markup by differencing against the clean source, and never register or list a markup file in `mapgen/SOURCES.md`.
- **Usable sources** are flat uniform fills (not hatching or brush strokes), PNG not JPEG, and the same pixel dimensions as an already-registered frame; warn before Chris spends effort on a map. Registration: whole-map fits inflate (silhouette IoU rewards land overlap, and by-eye landmarks are the bottleneck) — use Chris's paired anchor dots on the reprojected globe (thin-plate through exact-RGB dot centroids; the crop's binary alpha mask must be kept, and dimensions re-read every pass because he re-exports).
- **Acceptance is by named region**: Bretonnia ≥15, Empire ≥30, Cathay ≥40 and so on, 600–700 land states in all (`mapgen/regions/named_regions.json`). Bind a name to geometry by anchor point snapped to land, never by contour id. Hierarchy: province < state < state_region < strategic/geographic region; aim for ~7 provinces per state_region in the drawn Old World.
- **Per-state hand-authored tables** key on the canon state key `STATE_<NAME>` plus the naming anchor (`anchor_x`/`anchor_y`), never the Hilbert STATE number or a province colour — both reshuffle on regen.
- **LFS.** Seven `map_data/` paths are Git-LFS (see `.gitattributes`); a clone needs git-lfs (else 133-byte pointer files) and `core.longpaths` on Windows. Before rewriting history, back up with `git bundle create … --all`, not just a branch.
- **Symptom.** A coastline regen reporting "0 land regions" or 100% ocean means `--from-fill` was not passed.

## Vanilla map-keyed data overridden

Vanilla data keyed to the old real-world map crashes/errors the loader once the map is redrawn. Overrides in place:

- `common/defines/00_wh_defines.txt` — `WORLD_MARKET_LOCATION` (vanilla `x9137A4`, old North Atlantic, a province colour the mod lacks; caused `world_market.cpp:246` and a load crash). Set to a passable non-lake sea province (`xCC2EA6`). `common/defines` is not in `replace_paths`, so it merges per key. **Hand-authored, guarded by `validate_map._check_world_market_location`; re-check after any `generate_provinces.py --reassign`.**
- `gfx/map/spline_network/game_road_data.txt` — blanked; rows are keyed to vanilla state-region ids (`route_graphics.cpp` errors).
- `gfx/map/spline_network/spline_network.splnet` — zero-byte override: `travel_connection_definition.cpp` "no connection node" errors (681 lines) and no strip errors; without it, strip/anchor errors instead. **Neither variant is the load crash** (see below); the travel errors are non-fatal noise until real route data exists.
- `gfx/map/map_object_data/generated_map_object_locators_{city,farm,mine,port,wood}.txt` — engine-generated for the redrawn map (copy from `Documents/.../Victoria 3/generated/` after a load reports "map object locator ... is incomplete"); overrides vanilla's same-named files. Regenerate the same way after any hub/province change.
- `gfx/map/map_object_data/fortification_locators.txt` — blanked; instances sit at old-map pixels (`fortification_graphics.cpp` errors).

If a new stale-reference error appears, override one more file per iteration (candidates: `generated_map_object_locators_*`, `papermap_*`, `spline_network.splnet`) and list it here.

### Load crash root cause (confirmed 2026-09-28, #5525 / #5520)

The recurring `EXCEPTION_ACCESS_VIOLATION` at RVA `0x107D720` of `victoria3.exe` 1.13.11 (null read in `UpdateCountryScorePositions`, `logic/country_rank_manager.cpp`, reached from `InitializeGamestateFromBookmark`) is **not a map or gfx problem. It fires when the starting gamestate contains zero countries.** `map_data` is `replace_paths`-blanked and every `common/history/*` file is a stub, so no country exists and no state has an owner. The map editor builds the same gamestate, so it crashed identically.

- Evidence: the mod-off editor launch loads; the mod on with vanilla `map_data` (provinces, states, pack, nodes) and with vanilla `splnet` still crashed at the same RVA; adding **one** `common/history/countries` entry (`c:SAR ?= { }`) and **one** `common/history/states` `create_state` for `STATE_BAY_OF_BLADES` made the editor load with the same map, `splnet` and pack. Nothing else changed.
- Fix direction: ship real `common/history/countries` + `common/history/states` (start owners, then pops/buildings; the state start owners are now generated by `generate_state_history.py`, #6372); the SAR/BAY_OF_BLADES pair was only a discriminator. The starting country setup is now `generate_country_history.py` (#6375); not yet loaded in-game. Expect follow-on errors until pops exist ("There are no pops" assertion; `common/history/pops` is still header-only).
- The map pack (`packed_heightmap.png`, `indirection_heightmap.png`, `nodes.dat`, descriptor) and the base install were **not** the cause; #5525's pack hypothesis is falsified, and the base install's July timestamps were not editor damage (Verify integrity left every hash unchanged). `!Out.Contains( 616u )` still logs after script load but is non-fatal.
- The pack is committed (`209d199`): `packed_heightmap.png`, `indirection_heightmap.png`, `nodes.dat` and the editor's own `heightmap.heightmap` (`should_wrap_x=no`, never hand-edited). A Pack + Save also rewrites `heightmap.png`, `provinces.png`, `99_seas.txt`, the locators, `splnet` and ~320 `.bin` files: restore or delete those, commit only the four pack files (`MAP_RUNBOOK.md`, S4 result).
- Still vanilla Earth data: the mod overrides none of `gfx/map/terrain/detail_index.tga`, `detail_intensity.tga`, `textures/colormap.dds`, `flatmap*.dds`, `land_mask.dds`, `dynamic_masks/exclusion_mask.dds` or `map_object_data/generated/*`. They load because the canvas matches vanilla's size, and they are why the map editor shows Earth's materials and coastlines under our land. Generating our own is a separate `mapgen` job.
- Minidump triage without symbols: the exe's own debug strings name the enclosing function; a fault RVA plus the strings referenced near it and near the stack return addresses is enough to identify the subsystem.
