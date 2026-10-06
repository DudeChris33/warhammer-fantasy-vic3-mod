# Cartography provenance

The world geometry is **traced/registered from published Warhammer Fantasy
reference imagery** (the source-driven redo,
[world-map-source-driven.md](../planning/requests/world-map-source-driven.md)),
used as **geometric reference only**. We derive our own bitmaps, and **no
reference image is committed to this repo** — the `sources/` folder is
local-only and gitignored (decision #2). This file is the narrative provenance
record; the file-level manifest (filename, dims, SHA-256, origin, role) lives in
[SOURCES.md](SOURCES.md), and how each registered source maps onto the canvas is
in [registration/](registration/).

## ChaosRobie's mods

Two of ChaosRobie's Total War: Warhammer 3 campaign-map mods are held locally in
`sources/`: the Old World mod (`sources/cr_oldworld_campaign/`) and Immortal
Empires Expanded (`cr_immortal_empires_expanded`, the whole-world sibling).

- **Usable content:** the region/province/settlement tables and their names, the
  lookup (region-partition) bitmaps, his map and terrain edits, the factions, and
  his UI art.
- **Vanilla layers:** the vanilla parchment art, region names and colours,
  terrain and textures inside his packs are treated as geometric reference only.
- **Bookkeeping:** `sources/` stays local and gitignored, new files get a
  `SOURCES.md` manifest row, and anything borrowed is cited
  (`canon: cr_oldworld_campaign/<slug>` for the Old World table; use the same
  shape for the expanded mod). Invented-by-ChaosRobie content is not Warhammer
  canon, so cite it as his rather than as `canon:`.
- **Ranking:** the expanded whole-world dataset is trusted equally with the Old
  World mod (Chris, 2026-10-05): above the stock Immortal Empires parchment for
  interior boundaries and names within its footprint, never above the Terraqueous
  Globe for coastline.

## Reference sources (consulted for geometry/relief only)

The full, hash-pinned list is in [SOURCES.md](SOURCES.md). State as of S3a:

- **"Terraqueous Globe"** (fan cartography, Natural Earth II) — **the whole-world
  colour→height ramp**, and the backdrop the user traced the coastline on. Its
  NE-II projection was fitted to sub-pixel accuracy (0.363 px RMS), so it drives
  `map_data/heightmap.png`. The committed `land_sea_mask.png` is **no longer**
  ramp-derived from it (that derivation was deleted 2026-08-22): the mask is now
  flood-filled by `generate_coastline_mask.py` from the user's hand-traced
  coastline in `sources/land_sea_mask.png` (itself drawn on this globe).
  Registered.
- **Total War: Warhammer 3 Immortal Empires campaign map** (stitched screenshots)
  — high-frequency **relief detail** composited onto the heightmap inside its
  footprint (zero-mean, so it sharpens ridges but never moves a coast). Registered.
- **Creative Assembly — Total War: Warhammer 3 Immortal Empires campaign map**
  (parchment master, and its macro-annotated twin, climate-map and feature-image
  siblings) — **interior state boundaries, macro grouping, and printed names
  only, never coastline** (S3a / world-map-parchment-areas-onto-globe.md,
  2026-07-28). The master carries the family's one dense thin-plate
  registration (fitted against the climate-map sibling's silhouette, 12
  held-out landmarks); the other three declare a `frame_alias` directly to it.
  Its lettering is *bridged* into the traced barrier rather than erased —
  detected glyph-shaped ink closes the physical gaps a printed label leaves in
  the ruled line, recovering cells a break would otherwise merge. Registered.
  It is the primary boundary source; the flat-filled Total War map
  (`total_war_map_colored.png`) is now the complement, winning only outside
  the master's coverage.
- **Games Workshop — *Warhammer: The Old World* world map** — registered in S1 for
  Old World boundaries; **measured in S3a to be misregistered *and* not a
  chloropleth**, so it contributes no geometry. Record kept and annotated rather
  than deleted (its source-side picks remain good), not consumed.
- **Games Workshop — *The Empire* provinces map** — same finding, same disposition
  (S3a). Not consumed for geometry.
- **Games Workshop / Warhammer Community — *The Empire of Man* map**
  (`TheEmpireRivers.jpg`) — **consulted for the v1 river courses** (Reik/Talabec/
  Stir/Aver) authored in `mapgen/rivers/rivers.json`; not warped, so unregistered.
- **De-registered in S2:** the whole-world satellite/biome render
  (`images.steamusercontent.jpg`) — measured not to register (flat agreement, no
  peak); see [SOURCES.md](SOURCES.md). No longer consulted.
- **Consulted for cross-reference, unregistered:** the hi-res tiled Old World map
  (`the_old_world_*`), the "Landes and Seas of the Worlde" and "wahafa"
  whole-world maps, the GW "Major Trade Routes" map, and the updated GW Old World
  relief map (extent + naming, S6). Also **the "all faction starting positions"
  Old World fan map** — a denser boundary network than IE over the same arc,
  deliberately left unregistered in S3a because no measurable objective for it had
  been authored; named in `mapgen/derived/COVERAGE.md` as the next source to bring
  in, with the viable approach recorded there.

## Per-region tracing log

Each entry: region, which registered source(s) informed its coastline/relief/
boundaries, and the date traced.

| Region | Sources consulted | Phase | Date |
|---|---|---|---|
| Whole-world heightmap | Terraqueous Globe (NE-II reproject → LUT elevation); TW3 stitched relief composited as high-frequency detail inside its footprint. The land/sea split is the committed `land_sea_mask.png` (see below), consumed not re-derived. | S2 | 2026-07-23 |
| Whole-world coastline (`land_sea_mask.png`) | User-traced magenta coastline on the reprojected Terraqueous globe (`sources/land_sea_mask.png`), flood-filled by `generate_coastline_mask.py` (coastline parity — no colour, no height ramp, no lake list). Supersedes the deleted height-ramp mask derivation. | S2 | 2026-08-22 |
| Whole-world river network | **Derived, not traced** — drainage computed from the committed `heightmap.png` + `land_sea_mask.png` (depression fill -> D8 flow direction -> flow accumulation). No source imagery contributes geometry, so no source cartography is embedded in the result; the rivers follow our own generated terrain. Supersedes the hand-authored v1 polylines. | S2 | 2026-07-24 |
| Canon river *identification* (deferred to S6) | User-annotated *The Empire of Man* map (`TheEmpireRivers - drawn on.jpg`, canon courses drawn in red) — consulted as a **topology guide** for which DEM channel is the Reik/Talabec/Stir/Aver etc. Not warped, contributes no geometry. | S6 | pending |
| Whole-world state boundaries (the committed state-label layer) | **Immortal Empires parchment map + its unlabelled feature-image sibling**, traced as line networks and warped onto the Terraqueous geometry. They contribute interior borders only: every cell is intersected with the committed `land_sea_mask.png` and watershedded to tile it, so no coastline in the result comes from them. Macro grouping from the annotated twin, recovered by differencing it against the clean master. 2.4% of land has no source and carries seeded fallback cells. | S3a | 2026-07-25 |
| Whole-world state boundaries, geometry stage (registration + tracing only; names deferred to Stage B) | **Immortal Empires parchment master**, registered directly (silhouette via the climate-map sibling, `refined_iou` 0.6193) and promoted to the primary boundary source; its lettering is bridged into the barrier rather than erased. The unlabelled feature image is no longer traced for geometry (superseded by the master's superset coverage) but its registration stays as Stage B's text-mask cross-check. `total_war_map_colored.png` demoted to complement (wins only outside the master's footprint). | S3a (world-map-parchment-areas-onto-globe.md) | 2026-07-28 |
| _S1/S2/S3a fixtures use synthetic worlds under `mapgen/fixtures/` (invented by their own `make_source.py`, not derived from any source)._ | — | S1–S3a | 2026-07-21 |
