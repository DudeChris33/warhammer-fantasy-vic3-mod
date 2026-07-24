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

The full, hash-pinned list is in [SOURCES.md](SOURCES.md). State as of S2:

- **"Terraqueous Globe"** (fan cartography, Natural Earth II) — **the whole-world
  coastline + colour→height ramp.** Its NE-II projection was fitted to sub-pixel
  accuracy (0.363 px RMS), so it drives both `map_data/heightmap.png` and the
  committed `land_sea_mask.png`. Registered.
- **Total War: Warhammer 3 Immortal Empires campaign map** (stitched screenshots)
  — high-frequency **relief detail** composited onto the heightmap inside its
  footprint (zero-mean, so it sharpens ridges but never moves a coast). Registered.
- **Games Workshop — *Warhammer: The Old World* world map** — Old World /
  Badlands / Dark Lands / Araby / Land of the Dead boundaries (S3). Registered.
- **Games Workshop — *The Empire* provinces map** — Empire internal subdivision
  (S3). Registered.
- **Games Workshop / Warhammer Community — *The Empire of Man* map**
  (`TheEmpireRivers.jpg`) — **consulted for the v1 river courses** (Reik/Talabec/
  Stir/Aver) authored in `tools/rivers/rivers.json`; not warped, so unregistered.
- **De-registered in S2:** the whole-world satellite/biome render
  (`images.steamusercontent.jpg`) — measured not to register (flat agreement, no
  peak); see [SOURCES.md](SOURCES.md). No longer consulted.
- **Consulted for cross-reference, unregistered:** the hi-res tiled Old World map
  (`the_old_world_*`, S3), the "Landes and Seas of the Worlde" and "wahafa"
  whole-world maps, and the updated GW Old World relief map (extent + naming, S6).

## Per-region tracing log

Each entry: region, which registered source(s) informed its coastline/relief/
boundaries, and the date traced.

| Region | Sources consulted | Phase | Date |
|---|---|---|---|
| Whole-world coastline + heightmap | Terraqueous Globe (NE-II reproject → LUT elevation + land/sea mask); TW3 stitched relief composited as high-frequency detail inside its footprint | S2 | 2026-07-23 |
| v1 canon rivers (Reik/Talabec/Stir/Aver, Grismerie, Lynsk/Urskoy, Blood River, River Ruin, Amaxon, Vitae/Mortis) | *The Empire of Man* rivers map (Empire system topology) + the reprojected coastline (`land_sea_mask.png`) for mouths; courses hand-authored in `tools/rivers/rivers.json` and rasterized to a valid `rivers.png` | S2 | 2026-07-23 |
| _S1 fixtures use the synthetic `tools/fixtures/` world (invented, not derived from any source)._ | — | S1 | 2026-07-21 |
