# Cartography provenance

The world geometry under `tools/worldgen/geometry/` (and the fixtures) is
**hand-encoded as coordinates** from published Warhammer Fantasy cartography used
as **geometric reference only**. We derive our own bitmaps; no pixels are lifted
from Total War, GW products, or other mods, and **no reference image is committed
to this repo**. This file logs which sources were consulted for each region so
provenance is auditable without redistributing any copyrighted image.

## Reference sources (consulted for geometry/relief only)

- Warhammer Fantasy Wiki / Lexicanum — Known World maps and per-realm articles.
- Games Workshop published *Warhammer: The Old World* setting map.
- *Total War: Warhammer* campaign-map coastlines (shape reference only).

Fan-mod naming of GW settings is standard practice; copying art or map files is
the line we do not cross.

## Per-region encoding log

Filled in as real geometry is authored (P2 coastlines/relief/rivers, P3 state
cells). Each entry: region, which source(s) informed its coastline/relief, and
the date encoded.

| Region | Sources consulted | Phase | Date |
|---|---|---|---|
| _(none yet — P1 uses only the synthetic `tools/fixtures/` world, which is invented, not derived from any source)_ | — | P1 | 2026-07-20 |
