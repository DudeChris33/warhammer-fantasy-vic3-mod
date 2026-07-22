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

The full, hash-pinned list is in [SOURCES.md](SOURCES.md). Registered onto the
canvas so far (S1):

- **"Terraqueous Globe"** (fan cartography, Natural Earth II) — whole-world
  colour→height ramp + coastline.
- **Whole-world satellite/biome render** (fan, Steam Workshop) — coarse global
  frame anchor + land/sea layout.
- **Games Workshop — *Warhammer: The Old World* world map** — Old World /
  Badlands / Dark Lands / Araby / Land of the Dead boundaries.
- **Games Workshop — *The Empire* provinces map** — Empire internal subdivision.
- **Total War: Warhammer 3 Immortal Empires campaign map** (stitched
  screenshots) — high-detail coastline + relief for its arc, shape reference only.

Consulted but not yet registered (naming / cross-check, S6): the
"Landes and Seas of the Worlde" fan map and an updated GW Old World relief map.

## Per-region tracing log

Filled in as real geometry is traced (S2 heightmap/coastline/rivers, S3 state
cells). Each entry: region, which registered source(s) informed its
coastline/relief/boundaries, and the date traced.

| Region | Sources consulted | Phase | Date |
|---|---|---|---|
| _(none yet — S1 registers the sources onto the canvas; no geometry is traced until S2/S3. P1 fixtures use the synthetic `tools/fixtures/` world, which is invented, not derived from any source.)_ | — | S1 | 2026-07-21 |
