# World Map — P3: Provinces + States

| Field | Value |
|-------|-------|
| Type | request (child of [world-map.md](world-map.md)) |
| Status | planned |
| Date | 2026-07-20 |
| Priority | high |
| Phase | 3 of 6 |
| Gate | **Offline** — `validate_map.py` + `vic3-tiger` pass. Repo is deliberately **unbootable from P3 merge until P4 merge** — run P3 and P4 back-to-back. |
| Depends on | P1 (tools), P2 (coastline land mask) |

Child build file of the world-map master plan. Pipeline model: **all bitmaps generated in code** (see P1 header). P3 authors the state-cell partition and generates `provinces.png` plus every region/adjacency/loc text file from assignment tables.

## Description

Author the state-cell partition of the P2 land mask as committed geometry, then generate: `provinces.png` (seeded Voronoi subdivision, vanilla-order density), the `state_regions/` and `99_seas.txt` files, `default.map`, `adjacencies.csv`, the strategic-region files, and the loc skeletons. **This phase makes the repo unbootable** — new `map_data/state_regions` files merge-conflict with vanilla's (which still reference vanilla `STATE_` keys) until P4's `replace_paths` + scaffold land. P3 and P4 are one milestone split for reviewability; build them back-to-back.

---

## Plan

### Objective
Turn the P2 land mask into a complete, engine-valid province + state + strategic-region layer with placeholder economics and AUTOGEN localization — all generated deterministically from committed assignment tables.

### Steps (ordered)
1. **`tools/worldgen/geometry/states/<macro>.json`** — the state-cell partition: for each land state, a `key` (`STATE_*`), its macro-file, seed geometry (polygon or seed-point set) **inside the P2 coastline land mask**, `coastal` flag, `naval_exit` sea key, a placeholder-economics block, and an optional `impassable` sub-region (hybrid Chaos Wastes fringe + vanilla-style Greenland/Sahara interiors). Target vanilla-order counts: several hundred land states.
2. **`tools/generate_provinces.py`** → **`map_data/provinces.png`** — seeded, **wrap-aware Voronoi** subdivision of each state cell into ~40–70 provinces (vanilla-order ~30–45k total), each a globally-unique `xRRGGBB`, written as a pixel-exact **indexed PNG with no anti-aliasing**. Min-area merge for degenerate/disconnected cells. Ocean area is subdivided into single-province sea zones. Land/sea boundary comes from P2's coastline data, so coasts match the heightmap.
3. **`tools/generate_state_regions.py`** → **`map_data/state_regions/NN_<macro>.txt`** + **`99_seas.txt`** — per the verified vanilla `game\map_data\state_regions\state_regions.md` format:
   - Land: `id` (1+), `subsistence_building`, `provinces = { ... }`, auto-picked `city`/`farm`/`mine`/`wood` hubs (+ `port` for coastal), `arable_land`, `arable_resources`, `capped_resources`, `naval_exit_id`; `impassable = { ... }` where the partition marks it.
   - Sea: single-province states, `id` 3000+, in `99_seas.txt` (vanilla convention).
   - Hub auto-pick: city = centroid-most province, port = coastal province facing the naval-exit sea, farm/mine/wood spread; impassable provinces excluded from candidacy. One-line manual refinement later.
4. **`tools/generate_default_map.py`** → **`map_data/default.map`** — `provinces`/`topology`/`rivers`/`adjacencies` refs, `wrap_x = yes`, `sea_starts = { ... }` listing **every** sea province color, `lakes = { ... }` (lake colors are stateless — in no state file).
5. **`tools/generate_adjacencies.py`** → **`map_data/adjacencies.csv`** — verified 10-column format `From;To;Type;Through;start_x;start_y;stop_x;stop_y;adjacency_rule_name;Comment`, from province-adjacency analysis + a committed sea-crossing table (major straits/crossings).
6. **`common/strategic_regions/<area>_strategic_regions.txt`** + **`common/strategic_regions/water_strategic_regions.txt`** — generated from the state→SR mapping. Land SRs: `capital_province` + `map_color` + `states = { ... }`; water SRs: `states = { ... }` only (vanilla precedent). Every state (land + sea) in exactly one SR.
7. **`localization/english/map/wh_states_l_english.yml`, `wh_seas_l_english.yml`, `wh_strategic_regions_l_english.yml`** — `# AUTOGEN` skeletons (prettified from keys), UTF-8 BOM, `l_english:` header. Ships in the same phase the keys are introduced so no missing-loc errors surface later; canon naming happens in P6.
8. **`map_data/province_terrains.txt`** — minimal placeholder (land → `plains`, sea → `ocean`, keys from vanilla `common/terrain/01_terrain.txt`) purely so P4 can boot. **P5 regenerates it properly** from the terrain layer (`terrain_index` single source of truth).

### Design Decisions
- **Voronoi province generation** (user-confirmed): hand-mapping 30–45k aliasing-free cells is infeasible; subdividing the state partition with a seeded, committed tool hits vanilla density while keeping "generated from source" provenance. Impossible-by-construction to get stray/AA colors (indexed output); the validator scans both directions anyway.
- **IDs + file naming mirror vanilla**: land `id` from 1, grouped in `map_data/state_regions/NN_<macro_region>.txt`; seas `id` 3000+ in `99_seas.txt`; SR files `<area>_strategic_regions.txt` + `water_strategic_regions.txt`; loc uses the mod-wide `wh_` prefix under `localization/english/map/`.
- **Placeholder economics**: uniform parse-valid values (subsistence farm/pasture; `arable_land` ≈ 2× province count; wheat/livestock arable; small iron/logging caps; coastal fishing). Real economy is a later request (out of scope here).
- **Lakes are stateless**: listed only in `default.map` `lakes` (verified: vanilla lake colors appear in no state region).
- **`province_terrains.txt` placeholder now, real terrain in P5**: a boot needs a parse-valid terrain file; deriving real terrain from `terrain_index.png` is P5 work. The placeholder is intentionally trivial and flagged so P5's regeneration diff is clean.
- **Offline gate, paired with P4**: replacing `map_data/state_regions` instantly breaks vanilla history/countries; P3 alone cannot boot. Its gate is the validators, not a game load — the boot gate is P4's.

### Edge Cases
- **Anti-aliasing / stray colors**: impossible by construction (indexed output); `validate_map.py` cross-checks `provinces.png` ↔ state files both directions regardless.
- **Voronoi degenerates** (sub-threshold / disconnected cells): min-area merge in the generator; validator flags any 1-pixel province.
- **Seam states** at `x=0/x=8191`: generator treats x cyclically; a state only wraps the seam if genuinely contiguous in the geometry data.
- **Coastal/landlocked mismatch**: validator forbids `port`/`naval_exit_id` on a state with no coastal pixels and requires them on one with coastal pixels; `naval_exit_id` must resolve to a real sea id.
- **Hub on impassable province**: excluded at generation; validator re-checks.
- **Editor sessions rewriting generated files** (later phases): review `git diff` after each editor save; commit only intended regenerations.

### Testing
- `python tools/validate_map.py` passes every check (province uniqueness, hub membership, port/naval-exit rules, id bands, loc coverage, lakes-not-in-states).
- `vic3-tiger` (via `vic3-tiger.conf`) reports no errors on the generated text.
- Generators re-run → byte-identical outputs (determinism).
- **No game-load gate here** — repo is intentionally unbootable between P3 and P4. The boot + `error.log` check happens at P4 (see [testing.md](../../.claude/rules/testing.md)).

### Docs to Update
- `.claude/rules/scripting.md` (Naming) — record the `wh_` prefix + `map_data/state_regions/NN_<macro>.txt` / `<area>_strategic_regions.txt` conventions (first files establishing them land here).
- `.claude/rules/localization.md` — record the `localization/english/map/wh_*_l_english.yml` convention (first loc files land here).
- `tools/PROVENANCE.md` — cartography consulted for the state partition.

---

<!-- Filled in on resolution -->
## Resolution
**Status**: _pending_
**Files changed**: ...
**Tests added**: ...
**Validation**: ...
