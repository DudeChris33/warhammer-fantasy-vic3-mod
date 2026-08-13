# Carve ocean-connected drawn rivers / marshes out of the sea (hand-marked land/sea layer)

| Field | Value |
|-------|-------|
| Type | request |
| Priority | medium |
| Status | future (needs `/plan`) |
| Date | 2026-08-12 |
| Follows | [world-map-regenerate-land-sea-mask.md](../done/world-map-regenerate-land-sea-mask.md) (commit `28d6ed4`) |

## Description

The enclosed-water fix (commit `28d6ed4`) removed 164 false *enclosed* water
bodies (drawn rivers rendered in ocean-blue and flooded marshes that were pinched
off from the ocean). During the visual review the user found the **complementary**
failure the enclosed-only mechanism structurally cannot address:

**Drawn rivers and coastal marshes that stay *connected* to the sea are classified
as sea.** Because river-blue on the Terraqueous globe is colorimetrically identical
to ocean-blue, the classifier reads a drawn river reaching the coast as an inlet of
the ocean. These pixels are part of the single open-ocean component, so
`segment.keep_ocean_and_lakes` — which only fills *enclosed* water and can only
ever *keep* water, never carve ocean-connected water to land — cannot touch them.
No purely colorimetric classifier can separate the two either.

## Spots the user flagged (2026-08-12, on the `28d6ed4` mask)

- **Two Empire rivers near the Sea of Claws / Wasteland** — the left one stretches
  too far inland; the right is a river and should not be part of the sea.
- **Marsh in north Lustria** — falsely sea, should be land.
- **Marsh in south-eastern Naggaroth** — falsely sea, should be land.
- **Floodplains in northern Nehekhara** — falsely sea, should be land.

(These are examples, not an exhaustive list — the review was not completed.)

## Proposed mechanism (decide in `/plan`)

A **hand-marked land/sea correction layer** — request candidate approach #1, and
the same `.paint`-over-`sources/terraqueous_globe_reprojected.png` workflow already
used for rivers. Two marks:

- **force-land** — rivers, marshes, floodplains that must not be sea.
- **force-water** — pinched inlets / lakes that must stay water (would subsume the
  12-body `tools/config/inland_lakes.json` seed keep-list, or complement it).

The generator applies it deterministically after `clean_land_mask` (and the
enclosed fill), hash-pins it in `tools/SOURCES.md` via `--update-manifest`, and it
handles **both** directions everywhere. Must stay offline, RNG-free, and
byte-reproducible (`core.md` Determinism); the new source is hash-pinned and
`sources.py --verify` covers it.

## Sequencing

Lands the same coastline authority the sibling
[world-map-refit-sources-onto-reprojected-globe.md](../requests/world-map-refit-sources-onto-reprojected-globe.md)
scores registrations against, so — like the enclosed fix — it should land before a
source refit, or the refit fits to a coast the user is still correcting.

## Out of scope

- The enclosed-water fix (done — commit `28d6ed4`).
- Rivers authoring (`rivers.png` is derived from heightmap drainage; forcing a
  drawn river to land removes it from the sea mask but the drainage still routes a
  channel there by construction).
- `provinces.png` / S3b province cutting; the Miller frame; the NE-II registration.
