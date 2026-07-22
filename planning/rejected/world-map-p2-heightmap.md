# World Map — P2: Heightmap + Rivers

> **Superseded by [world-map-source-driven.md](../requests/world-map-source-driven.md)** (2026-07-21) — re-phased into S0–S6; this phase's work is inherited by S2. Kept for history.

| Field | Value |
|-------|-------|
| Type | request (child of [world-map.md](world-map.md)) |
| Status | planned |
| Date | 2026-07-20 |
| Priority | high |
| Phase | 2 of 6 |
| Gate | Game boots to **main menu** with mod enabled; editor heightmap-repack round-trip succeeds; `logs/error.log` clean of mod-file lines |
| Depends on | P1 (`tools/` schema + raster libs) |

Child build file of the world-map master plan. Pipeline model: **all bitmaps generated in code** (see P1 header). P2 authors the whole-world geometry data and generates the heightmap + rivers bitmaps; the only human step is the map-editor heightmap repack, driven by the runbook.

## Description

Author the whole Known World's coastline, relief, and river **geometry as committed data**, generate `heightmap.png` (16-bit, 16384×7232) and `rivers.png` in code, and prove the desktop map-editor repack → boot loop works — decoupled from the province overhaul (which lands in P3). P2 ships **only** the heightmap + rivers layers; `provinces.png`, `default.map`, and `state_regions` stay vanilla so the repo still parses and boots to the main menu.

---

## Plan

### Objective
Produce the physical shape of the world — coastlines, elevation, major rivers — as code-generated bitmaps, and validate the heightmap-pack + boot pipeline in isolation before the province layer depends on it.

### Steps (ordered)
1. **`tools/worldgen/geometry/coastlines/<macro>.json`** — landmass polygons for the entire Known World, one file per macro-landmass: Old World (Empire, Bretonnia, Kislev, Norsca, Tilea/Estalia, Border Princes, Badlands, Worlds Edge), Ulthuan, Naggaroth, Lustria, Southlands, Darklands + Mountains of Mourn/Ogre lands, Grand Cathay, Ind/Khuresh/Nippon, Eastern Steppes. Coordinates in `provinces.png` canvas space; encoded from published cartography (logged in `tools/PROVENANCE.md`, no image committed). **This is the canonical land/sea boundary reused verbatim by P3**, so heightmap coastlines and province coastlines line up exactly. Chaos Wastes: the canvas top/bottom edges cut inside the polar Wastes exactly as vanilla cuts the Arctic (hybrid-fringe decision — outer playable tundra, innermost band becomes `impassable` in P3, no all-impassable states).
2. **`tools/worldgen/geometry/relief.json`** — `sea_level`; mountain ridge polylines with crest heights (Worlds Edge, Grey/Black/Vaults, Annulii of Ulthuan, Mountains of Mourn, Ind highlands, etc.); coastal falloff distance; seeded fractal-noise params for mid-slope detail.
3. **`tools/worldgen/geometry/rivers.json`** — v1 canon river polylines: Reik + Talabec/Stir/Aver (Empire), Grismerie (Bretonnia), Lynsk/Urskoy (Kislev), Blood River (Badlands), River Ruin (Darklands), Amaxon (Lustria), Vitae/Mortis (Southlands). Eastern rivers deferred to the P6 naming/art pass (geometry only sketched here if convenient) — **no invented canon** beyond published cartography.
4. **`tools/generate_heightmap.py`** → **`map_data/heightmap.png`** — rasterize `coastlines` + `relief` into a 16-bit grayscale 16384×7232 PNG: land above `sea_level`, ocean below, coastal falloff at boundaries, ridge polylines raised to crest height with interpolated flanks, seeded noise added. numpy array math; deterministic from `SEED`.
5. **`tools/generate_rivers.py`** → **`map_data/rivers.png`** — rasterize `rivers` following vanilla's river-palette convention (**sample the vanilla `rivers.png` palette at generation time** rather than hardcoding indices — source/flow-direction/tributary colors as the engine expects).
6. **`tools/MAP_RUNBOOK.md`** (append P2 section) — click-by-click **map-editor heightmap repack**: open the mod in the editor with the new `heightmap.png`, run the heightmap pack, save. User commits the editor outputs: **`packed_heightmap.png`, `indirection_heightmap.png`, `heightmap.heightmap`** (`original_heightmap_size = { 16384 7232 }`, `tile_size = 65`, `should_wrap_x`/`level_offsets` = whatever the 1.13.8 editor writes — never hand-tuned).

### Design Decisions
- **P2 ships heightmap + rivers only; `provinces.png`/`default.map`/`state_regions` stay vanilla.** This is what lets the P2 gate be *clean* — vanilla province/state data still references vanilla province colors, which are unchanged, so the game parses and boots. It de-risks the editor + boot pipeline before the province overhaul, exactly per the master plan's P2 intent.
- **Coastline data is the single shared boundary** between the heightmap (P2) and provinces (P3) — authored once here, imported there. Prevents the classic "heightmap coast ≠ province coast" mismatch.
- **`nodes.dat` and object locators are NOT regenerated in P2.** They are province-adjacency/model-placement artifacts; with vanilla provinces still in place, vanilla's are correct. `nodes.dat` regeneration waits for the new provinces (P4); locators wait for P5.
- **Canvas identical to vanilla** (8192×3616 / 16384×7232, `tile_size` 65) and **`wrap_x = yes`** — Exether-proven on 1.13; lore-consistent circumnavigation (west from Lustria reaches Nippon/Cathay).
- **Heightmap internals are editor-authoritative** — we generate the *source* `heightmap.png`; the `.heightmap` pack is whatever the game's editor produces from it. We never hand-edit the packed files.

### Edge Cases
- **Fidelity risk (called out under the "generate all in code" model):** encoding a recognizable whole-world coastline as coordinates — without tracing reference images — is bounded in accuracy. P2's coastline is a good-faith geometric approximation from published maps; refinement of specific coastlines is a candidate future polish request, not a P2 gate condition.
- Swapping `heightmap.png` under vanilla `provinces.png` means some vanilla land provinces may sit below the new sea level (and vice versa). This looks wrong but **parses** — the P2 gate is heightmap-pack validity + clean parse, not geographic correctness. If it produces `error.log` lines referencing mod files, treat that as a real failure and investigate.
- Seam continuity: coastline/relief/river polylines that cross `x=0/x=8191` must wrap continuously (`wrap_x = yes`) — the generators use P1's wrap-aware geometry.
- Editor session rewriting more than the heightmap pack (e.g. touching `province_terrains.txt`) → review `git diff` after the save; commit only the intended heightmap-pack files.
- 16-bit depth: verify `heightmap.png` is written as true 16-bit grayscale, not 8-bit — the editor pack expects 16-bit source.

### Testing
- Generators run deterministically (re-run → byte-identical `heightmap.png` / `rivers.png`).
- After the editor repack: launch Victoria 3 with the mod, reach the **main menu** (globe/flatmap renders on the new relief), and confirm `Documents/Paradox Interactive/Victoria 3/logs/error.log` has **zero lines referencing this mod's files** (see [testing.md](../../.claude/rules/testing.md)).
- Editor round-trip: opening + repacking + saving the heightmap produces no editor errors; committed pack files load.

### Docs to Update
- `tools/MAP_RUNBOOK.md` — P2 heightmap-repack section (the deliverable itself).
- `tools/PROVENANCE.md` — cartography consulted for coastlines/relief/rivers.
- No `.claude/rules/` change (map bitmaps establish no new script convention).

---

<!-- Filled in on resolution -->
## Resolution
**Status**: _pending_
**Files changed**: ...
**Tests added**: ...
**Validation**: ...
