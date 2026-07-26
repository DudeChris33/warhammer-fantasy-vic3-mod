# Cartography provenance

The world geometry is **traced/registered from published Warhammer Fantasy
reference imagery** (the source-driven redo,
[world-map-source-driven.md](../planning/requests/world-map-source-driven.md)),
used as **geometric reference only**. We derive our own bitmaps; no pixels are
lifted from Total War, GW products, or other mods, and **no reference image is
committed to this repo** — the `sources/` folder is local-only and gitignored
(decision #2). This file is the narrative IP/provenance record; the file-level
manifest (filename, dims, SHA-256, origin, role) lives in
[SOURCES.md](SOURCES.md), and how each registered source maps onto the canvas is
in [registration/](registration/).

Fan-mod naming of GW settings is standard practice; copying art or map files is
the line we do not cross. Only our own derived pixels are committed.

## Reference sources (consulted for geometry/relief only)

The full, hash-pinned list is in [SOURCES.md](SOURCES.md). State as of S3a:

- **"Terraqueous Globe"** (fan cartography, Natural Earth II) — **the whole-world
  coastline + colour→height ramp.** Its NE-II projection was fitted to sub-pixel
  accuracy (0.363 px RMS), so it drives both `map_data/heightmap.png` and the
  committed `land_sea_mask.png`. Registered.
- **Total War: Warhammer 3 Immortal Empires campaign map** (stitched screenshots)
  — high-frequency **relief detail** composited onto the heightmap inside its
  footprint (zero-mean, so it sharpens ridges but never moves a coast). Registered.
- **Creative Assembly — Total War: Warhammer 3 Immortal Empires campaign map**
  (parchment master, and its macro-annotated twin, climate-map and feature-image
  siblings) — **interior state boundaries and macro grouping only, never
  coastline** (S3a). One dense thin-plate registration serves all four; the other
  three declare a `frame_alias` to it. Registered.
- **Games Workshop — *Warhammer: The Old World* world map** — registered in S1 for
  Old World boundaries; **measured in S3a to be misregistered *and* not a
  chloropleth**, so it contributes no geometry. Record kept and annotated rather
  than deleted (its source-side picks remain good), not consumed.
- **Games Workshop — *The Empire* provinces map** — same finding, same disposition
  (S3a). Not consumed for geometry.
- **Games Workshop / Warhammer Community — *The Empire of Man* map**
  (`TheEmpireRivers.jpg`) — **consulted for the v1 river courses** (Reik/Talabec/
  Stir/Aver) authored in `tools/rivers/rivers.json`; not warped, so unregistered.
- **De-registered in S2:** the whole-world satellite/biome render
  (`images.steamusercontent.jpg`) — measured not to register (flat agreement, no
  peak); see [SOURCES.md](SOURCES.md). No longer consulted.
- **Consulted for cross-reference, unregistered:** the hi-res tiled Old World map
  (`the_old_world_*`), the "Landes and Seas of the Worlde" and "wahafa"
  whole-world maps, the GW "Major Trade Routes" map, and the updated GW Old World
  relief map (extent + naming, S6). Also **the "all faction starting positions"
  Old World fan map** — a denser boundary network than IE over the same arc,
  deliberately left unregistered in S3a because no measurable objective for it had
  been authored; named in `tools/derived/COVERAGE.md` as the next source to bring
  in, with the viable approach recorded there.

## Per-region tracing log

Each entry: region, which registered source(s) informed its coastline/relief/
boundaries, and the date traced.

| Region | Sources consulted | Phase | Date |
|---|---|---|---|
| Whole-world coastline + heightmap | Terraqueous Globe (NE-II reproject → LUT elevation + land/sea mask); TW3 stitched relief composited as high-frequency detail inside its footprint | S2 | 2026-07-23 |
| Whole-world river network | **Derived, not traced** — drainage computed from the committed `heightmap.png` + `land_sea_mask.png` (depression fill -> D8 flow direction -> flow accumulation). No source imagery contributes geometry, so no third-party cartography is embedded in the result; the rivers follow our own generated terrain. Supersedes the hand-authored v1 polylines. | S2 | 2026-07-24 |
| Canon river *identification* (deferred to S6) | User-annotated *The Empire of Man* map (`TheEmpireRivers - drawn on.jpg`, canon courses drawn in red) — consulted as a **topology guide** for which DEM channel is the Reik/Talabec/Stir/Aver etc. Not warped, contributes no geometry. | S6 | pending |
| Whole-world state boundaries (the committed state-label layer) | **Immortal Empires parchment map + its unlabelled feature-image sibling**, traced as line networks and warped onto the Terraqueous geometry. They contribute interior borders only: every cell is intersected with the committed `land_sea_mask.png` and watershedded to tile it, so no coastline in the result comes from them. Macro grouping from the annotated twin, recovered by differencing it against the clean master. 2.4% of land has no source and carries seeded fallback cells. | S3a | 2026-07-25 |
| _S1/S2/S3a fixtures use synthetic worlds under `tools/fixtures/` (invented by their own `make_source.py`, not derived from any source)._ | — | S1–S3a | 2026-07-21 |
