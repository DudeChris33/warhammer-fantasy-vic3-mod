# Source manifest

The source-driven map pipeline reads reference imagery from a local `sources/`
folder at the repo root. **`sources/` is gitignored and never committed** — it
mixes Games Workshop cartography, a Total War screenshot mosaic, and fan maps
(third-party IP), plus ~40 MB of binaries (decision #2 in
[world-map-source-driven.md](../planning/requests/world-map-source-driven.md)).

This file is the committed **manifest** that stands in for those files: every
source's filename, dimensions, byte size, SHA-256, origin, pipeline role, and
whether it carries a [registration record](registration/). It makes the exact
inputs behind every committed bitmap auditable without redistributing any art,
and it is the hash `tools/worldgen/sources.py` checks a source against before the
ingestion stage is allowed to read it — so a swapped or edited `sources/` file
can never silently change a committed, multiplayer-synced bitmap.

Only our own derived pixels (`map_data/*.png`, …) are committed; consulting these
references for geometry is standard fan-mod practice, copying their pixels is the
line we do not cross (see [PROVENANCE.md](PROVENANCE.md)).

## The Terraqueous Globe is the most trusted source, and the shape we aim for

**`terraqueous_globe.jpg` outranks every other source in this manifest.** It is
the single geometric authority (user decision #1, 2026-07-25): its coastline is
the shape the finished map is meant to have, and every other reference is
*projected onto it* rather than averaged with it. Where a source disagrees with
the globe about where land is, the globe is right by definition and the other
source is misregistered.

Concretely, and non-negotiably:

- The committed `tools/derived/land_sea_mask.png` is derived from it and **is the
  coastline**. Nothing else may move a shoreline — not the Total War relief, not
  the Immortal Empires parchment family, not a future source.
- Other sources contribute only things the globe cannot supply: **interior
  boundaries**, **macro grouping**, **names**, and **high-frequency relief
  detail** composited as zero-mean texture on land. All of it is clipped to the
  mask.
- A new source's registration is *scored against the mask*, so "does it agree
  with the globe" is the measurement that decides whether it may be used at all
  (see `tools/fit_registration.py`). This is how the satellite render came to be
  de-registered in S2 and how the two GW regional maps came to be marked not
  usable for geometry in S3a.

It earns that standing by measurement, not by preference. Its Natural Earth II
projection was fitted to its own drawn envelope at **0.363 px RMS** across 2001
traced rows, with two independent confirmations: the fitted axes are isotropic to
within 0.07% (as a true NE-II rendering must be), and the fitted graticule lands
within ~2 px of the degree labels the map itself prints. No other source in this
folder is registered to anywhere near that accuracy — the next best are
rubber-sheeted playable-game maps whose landmasses are drawn at deliberately
wrong relative sizes.

## Verifying / refreshing

```
python tools/worldgen/sources.py --verify           # SHA-256 + registration cross-checks (offline gate)
python tools/worldgen/sources.py --update-manifest   # after an *intentional* source change only
```

`--verify` fails loudly on any missing file or SHA-256 mismatch. Refreshing a
source is the deliberate `--update-manifest` action — never a side effect of a
generator run. The table below (between the `MANIFEST` markers) is machine-read;
edit the Origin/Role cells by hand, let `--update-manifest` fill Dims/Bytes/SHA.

<!-- MANIFEST:BEGIN -->
| File | Dims | Bytes | SHA-256 | Origin | Role | Registered |
|---|---|---|---|---|---|---|
| 3274025515_preview_WH3 climate map 6.0.3.jpg | 2471x1922 | 2,022,554 | fae9e090f0b2ffba1f82008dec5c2c36cf6a03dd0eaca0808b8822ba7b413edb | Fan mod ("WH3 climate map", Steam Workshop preview) — Immortal Empires frame, flat climate fills | **Registration objective** — its flat fills give the land silhouette that makes the IE fit measurable against our own mask. Frame alias of the parchment master (exact 0.6673 scale). Terrain/biome input for S5 | no |
| Immortal-Empires-Map-Feature-Image-scaled - Copy.png | 2560x1440 | 7,319,837 | d315664e2e3d72b9d8085072d5e0568d0a07cd94ab1d3c8df6b95cf12296bfde | The IE feature image with ocean strokes drawn on by the user | Hand-marked sea. Brush strokes tracing coasts + hatching over open water, not a flat fill, so it is usable as SEA SEEDS for calibrating a land/sea test, not as a silhouette on its own. Superseded for that purpose by total_war_map_colored.png | no |
| Immortal-Empires-Map-Feature-Image-scaled.jpg | 2560x1440 | 885,605 | 64d88c294a0547c61c4faa77564c3bc253ae275d5ace3e86abe48eaa19a9ce76 | Creative Assembly / press — Immortal Empires campaign map feature image | Superseded as the primary boundary source by the master (world-map-parchment-areas-onto-globe.md, 2026-07-28): its footprint is a strict subset of the master's at lower precedence, so `stack_layers` never selects it. Registration record kept — it is Stage B's independent text-mask cross-check (differenced against the master to confirm detected labels). Frame alias of the parchment master (16:9 vertical crop, measured by NCC) | yes |
| Major_Trade_Routes_of_the_Old_World_Map.webp | 1947x1404 | 690,310 | 12026b1e21ad7b9467ff1e3d597e98492739af19e2d8cf97407ddf5d28f7b919 | Games Workshop — "Major Trade Routes of the Old World" | Manifest only, unregistered — S6 reference | no |
| TheEmpire.webp | 1596x1024 | 682,992 | e19ad56e0b21023955f3ed91301073aba03efe08b4506b4d6f3e5b4fab51adff | Games Workshop — The Empire provinces map | Empire internal subdivision. **NOT USABLE FOR GEOMETRY** (measured S3a) — misregistered off the coast, and not a chloropleth (see below) | yes |
| TheEmpireRivers - drawn on.jpg | 1920x1301 | 1,463,260 | e4d4d67afb4705d7e7c139ecd5a0cd0233adff80100939328451b6ecce384ff4 | The above, with canon river courses drawn on in red by the user | Canon-river TOPOLOGY guide for the S6 naming pass — which DEM channel is which. Contributes no geometry (see below) | no |
| TheEmpireRivers.jpg | 1920x1301 | 1,466,126 | 8c3f93454483dc261f933ad3d43530495cb11111071de2511669ac50f5ad2528 | Games Workshop / Warhammer Community — "The Empire of Man" map | Clean counterpart of the annotated map — differencing the two isolates the annotation | no |
| Warhammer_olde_world_map.webp | 1434x975 | 442,484 | d8aad1d1697980aab21f95e5724a9f95d5889656cac73cb66dd5cab578d094f5 | Fan cartography — "Landes and Seas of the Worlde" | Naming + extent confirmation (S6 naming pass) | no |
| images.steamusercontent.jpg | 637x358 | 43,099 | 8b90bae2e491a366a8c5deb3f1e8d9307dac6b8658d0fd7d62bb9c6de242d95b | Fan whole-world satellite/biome render (Steam Workshop) | DE-REGISTERED in S2 - does not register (see below) | no |
| map-the-old-world.jpg | 3016x2080 | 1,140,330 | 80ae22f4aa384049cd42e70ade67db4f57853e6e91c9fbed30458dd9a69c1f91 | Games Workshop — Warhammer: The Old World world map | Old World / Badlands / Dark Lands / Araby / Land of the Dead boundaries. **NOT USABLE FOR GEOMETRY** (measured S3a) — misregistered off the coast, and not a chloropleth (see below) | yes |
| map_of_known_world.jpg | 2048x1449 | 625,772 | 9102bb84f9a4e7ef7cac4c8262e852900dd0b594acc06871de16e347ed14e6c0 | Fan cartography - "Map of the Known World in the Year of our Lord Sigmar 2502" (AndAlso, 2023) | Illustrated relief map with settlement and faction icons. NAMING + extent reference for S6; draws no region boundaries, so it contributes no geometry | no |
| pizqenw9rd791.jpg | 3703x2880 | 3,819,973 | 0085135bcdc9bc312c92be3abbe4afa7d25a32e8a5dddc4685cf3188637572d3 | Fan annotation of the IE parchment master (Reddit) — macro-region outlines + printed province counts | **Macro grouping** — pixel-aligned twin of the master, so differencing the two isolates hue-separable macro contours. Frame alias (identity) | yes |
| terraqueous_globe.jpg | 4000x3256 | 2,292,545 | c4021e28d8d58bc3f91733df72ee9b7b398f922bb565b0478d3743446d8c15f3 | Fan cartography — "Terraqueous Globe", Kartografia Niepraktyczna 2022 | Whole-world heightmap (NE-II colour-to-height ramp) + coastline. **The single geometric authority** (S3a decision #1) — every other source projects onto it | yes |
| the-old-world-all-faction-starting-position-map-v3-0-updated-v0-ml2lq3qfofad1 - Copy.png | 4096x4096 | 32,206,014 | ff5fc28a14bd2805fa3462fe362174ca51f6fbaa2536c8a45425f982bbdeb439 | The Old World fan map with ocean strokes drawn on by the user | Hand-marked sea, as above. Calibrated a luminance land/sea cut for this map to 81% balanced accuracy - measurable at last, but well short of the exact silhouette total_war_map_colored.png provides | no |
| the-old-world-all-faction-starting-position-map-v3-0-updated-v0-ml2lq3qfofad1.png | 4096x4096 | 8,332,865 | 93f5c7b4791d7a02b60eeb4ba96bf5abc66ad4d650978d1990b022840de903a3 | Fan cartography — "The Old World, all faction starting positions v3.0" | **Denser Old World boundary network** — a line chloropleth, markedly denser than IE over the same arc. Higher precedence inside a masked footprint; the four corner vignettes + the Galleon's Graveyard spiral are excluded (they take cartographic liberties — user-flagged) | no |
| the_old_world_bot_left.png | 1195x683 | 1,542,117 | adf58b58178b2de1fb58b3f3d84038125809a8b5b2c4b727f5467f185bde856d | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (bot-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_bot_right.png | 1191x676 | 1,586,780 | 6462a83e8084bc01da73082d7e4099f897c4b6fdb6405e03c410a4213bf2743d | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (bot-right) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_bot_left.png | 1192x680 | 1,610,370 | 31e87b7948fac60aca9e475eda8a4bc3b8938958e2a8a169e1889637f002bb91 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-bot-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_bot_right.png | 1190x676 | 1,581,702 | ebc9ae26794d596d5e2182adafeaaa440d46602df25eff073f30c72e402c9125 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-bot-right) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_top_left.png | 1191x679 | 1,803,901 | bba872c288113332e0c35e003b13c5a56e724226deba61763d247ba2752f3a89 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-top-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_top_right.png | 1191x676 | 1,689,342 | 8ca134d1bea237def8eab18ea9ece930604307865addf86a1587361c2799f6e5 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-top-right) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_top_left.png | 1193x679 | 1,531,068 | 3c92d0603de70557b857df60e3c7f334f1459cc69ec50947b787e2b97601a6a0 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (top-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_top_right.png | 1197x678 | 1,362,417 | b4541e35e06dbed408e9e886da0d97023c2c8db53d1ba6d20457d9363887d86b | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (top-right) of the hi-res Old World map — S3 boundaries | no |
| total_war_map_colored.png | 4726x3010 | 1,467,069 | d3962b9e28a49765c6c6f236b89b67924d06019835bcc857a51b41e5602b3817 | Fan cartography - flat-filled Total War: Warhammer world map with region boundaries | Demoted from primary to **complement** boundary source (world-map-parchment-areas-onto-globe.md, 2026-07-28): boundary precedence 95, below the parchment master's 100, so it now wins only outside the master's coverage. Flat blue ocean still gives an EXACT land/sea silhouette (no threshold is fitted), and black region lines over flat terrain fills yield 681 clean closed cells across the whole Known World, against our 659 land-state target — the 748-vs-681 clean-cell discrepancy flagged in the S3a-2 review remains explicitly unresolved. See below | yes |
| total_war_states_per_strat_region.jpg | 2048x1593 | 1,112,706 | b8965b704a476a5e93276f217c17dc6b6135301c87564c36ebb6d181252303ca | Fan annotation of the IE parchment master - strategic regions outlined, named, and labelled with their Total War: Warhammer 3 state counts | **NAMED MACRO REGIONS** - the source that binds region names to geometry, without which none of the user's per-region requirements can be checked. 17 named regions; supersedes pizqenw9rd791.jpg for grouping. Frame alias of the twin (exact 0.553 rescale). Printed counts are a reference, not truth | yes |
| tww3_map_bot_left.png | 1898x1058 | 3,082,592 | 6d00af0b9295ff6fb04377a599e13659212ad5c71c539a7eb0cffc4424b05ed6 | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| tww3_map_bot_right.png | 1919x1066 | 3,176,709 | d049334f929ead54d03f678f084b84ccbdc530830cc28fb9308634abdbe9f2aa | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| tww3_map_stitched.paint | n/a | 18,118,672 | 94b5726b6f02f65acf5379dc15a8e97fd9d0fca7f6bdcf16d612a5c45b347597 | Total War: Warhammer 3 Immortal Empires campaign map (stitch project) | Editable master of tww3_map_stitched.png (not consumed directly) | no |
| tww3_map_stitched.png | 2531x1961 | 8,089,308 | f975c35d32578d8d6ec7cbf4a2dd079d5845a6f685f6a568ad1b21b58c7f24c4 | Total War: Warhammer 3 Immortal Empires campaign map (stitched screenshots) | High-detail coastline + relief for its arc (consumed flat artifact) | yes |
| tww3_map_top_left.png | 1890x1034 | 3,666,866 | 086cfaeab68c457a21cdea14ddeddda127ad85a062442931ac022f73f624bbb1 | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| tww3_map_top_right.png | 1919x1079 | 3,657,669 | d77d5441291a5960aaf6851870a92fbf85cab4c0ffa43b578b0086063e61eea5 | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| updated-warhammer-the-old-world-map-v0-eyiuahz1swhg1.webp | 640x938 | 135,766 | 4559b8beb215f976ef8aed1339ef94c36dcf2d40ccb9cb88cc863d8b5cac05da | Games Workshop — updated Old World relief map | Old World relief cross-check (S6) | no |
| wahafa-world-map.jpg | 547x365 | 32,445 | 69f7f4a483dd1976234e1399c88e59225093db101d8af8ba2c974f62d6257bd1 | Fan cartography — "wahafa" whole-world map | Whole-world coastline / extent cross-reference (unregistered) | no |
| wh3_dlc_ie_parchment_map_english.jpg | 3703x2880 | 3,225,567 | f6e4f53ea80673bb9b792f11b1ac1de387bb8e07757f8a384aa40fd8aea757c1 | Creative Assembly - Total War: Warhammer 3 Immortal Empires parchment campaign map (English) | **PRIMARY BOUNDARY + NAME SOURCE (world-map-parchment-areas-onto-globe.md, 2026-07-28)** - registered by `tools/fit_registration.py --seed wh3_dlc_ie_parchment_map_english` (silhouette objective via the climate map sibling, 10x8 lattice, 12 held-out landmarks). Fit: `refined_iou` 0.6193, `folded_fraction` 0%, `anisotropy_p99` 3.00, `landmark_check_px` mean 426.9 / max 872.1 - reported against the family's only other comparable record (`total_war_map_colored.json`: mean 312.2 / max 844.6, refined_iou 0.6617) as somewhat weaker but consistent (0% folding, same anisotropy), explained by the parchment's silhouette coming via a rescaled sibling rather than an exact flat-fill silhouette. The family's `ie_macro_twin.json` control points (baked standalone when the master was previously absent from `sources/`) reproduce EXACTLY (0.0 px mean/max) against this fit, confirming full reproducibility with the existing placement. Its interior line network is traced with lettering bridged (not erased) into the barrier, and its printed names are the S3a-2 review panel's missing name-to-geometry binding. Also the differencing counterpart for macro grouping (unchanged role). | yes |
<!-- MANIFEST:END -->

## Renamed in S3a: `ljzbtm288r891.jpg` → `terraqueous_globe.jpg`

The Terraqueous globe was carrying its upload-site filename. It was renamed on
disk to something legible; the **bytes are unchanged**, so its SHA-256
(`c4021e28…`) still matches the row that pinned the committed
`map_data/heightmap.png` and `land_sea_mask.png`. Provenance therefore survives
the rename intact — this is a relabelled row, not a new source. The registration
record moved with it (`registration/terraqueous_globe.json`), as did the
references in `generate_heightmap.py`, `lut/terraqueous_elevation.json` and
`config/canvas_frame.py`.

## The Immortal Empires frame family (S3a)

Four sources are the **same picture at different crops and scales**, so one
registration record carries the control points and the other three declare a
`frame_alias` to it (see [registration/](registration/) and the `frame_alias`
projection kind in `worldgen/schema.py`). The relationships were measured, not
assumed:

| Source | Relationship to the master | How measured |
|---|---|---|
| `wh3_dlc_ie_parchment_map_english.jpg` | **the master** (3703×2880) | — |
| `pizqenw9rd791.jpg` | identity — pixel-aligned twin | identical dims, grayscale corr 0.803, median abs-diff 3 |
| `3274025515_preview_WH3 climate map 6.0.3.jpg` | scale 0.6673 | exactly `2471/3703 = 1922/2880` |
| `Immortal-Empires-Map-Feature-Image-scaled.jpg` | full width `x[8..3692]`, crop `y[224..2296]`, ratio 1.4391/1.4389 | multi-scale NCC, peak 0.6701 |

That collapses four control-point authoring jobs into one, and means a
control-point correction propagates to all four automatically. Immortal Empires
is a *playable* map rather than a globe — Ulthuan is drawn roughly twice as large
relative to the world as it is on the Terraqueous globe — so the master's record
is a dense thin-plate warp, never an affine. It contributes **interior boundary
lines and names only, never coastline**: the committed `land_sea_mask.png` is the
sole coastline authority (user decision #1, 2026-07-25), which is exactly what
makes a rubber-sheeted registration acceptable here. Local scale error moves an
interior border a few pixels inside a landmass; it cannot put a coast in the sea.

## Not usable for geometry (S3a): `map-the-old-world.jpg`, `TheEmpire.webp`

Both were registered in S1 for Old World / Empire boundaries; S3a measured two
independent, either-one-disqualifying findings for each: **misregistered** (the
QA overlay shows the committed coastline cutting across the drawn landmass — S2
shifted the canvas-side control points to follow the refined
`config/canvas_frame.ANCHORS` but never re-verified them against the generated
mask), and **not a chloropleth** (both are relief illustrations with lettered
labels, so even a correct registration would yield no traceable closed region
boundaries — the decisive finding, since re-registering would not have helped).
This is why S3a took the Immortal Empires parchment family instead.

The records are **kept, not deleted** (user decision #4, 2026-07-25): their
source-side landmark picks are still good and a future re-registration should
start from them, but nothing may consume either for geometry until the canvas
side is re-picked against the committed mask. See the `notes` field in
`registration/map-the-old-world.json` / `registration/TheEmpire.json` and
[PROVENANCE.md](PROVENANCE.md).

## The annotated Empire map (`TheEmpireRivers - drawn on.jpg`)

The user drew the canon Empire river courses onto the GW map in bright red. It is
a **topology guide for S6**, not a geometry source: it records which rivers exist
and how they join, while the actual courses in `map_data/rivers.png` come from the
heightmap's own drainage (see [PROVENANCE.md](PROVENANCE.md)). That split is
deliberate — the annotation is freehand and the underlying map is a stylised
illustration that does not register tightly, so letting it place pixels would put
rivers off-valley; letting it *label* them cannot.

Extracting the strokes is a solved step: **difference it against the clean
`TheEmpireRivers.jpg`** (the same image without the annotation). The strokes are
exactly what changed. This also disposes of the coats of arms, which are bright
red in *both* images and therefore cancel — no colour threshold or shape
heuristic survives contact with heraldry, but a difference does.

## De-registered in S2: `images.steamusercontent.jpg`

S1 registered the whole-world satellite render as the "coarse global frame anchor
+ land/sea layout". S2 measured it and removed the registration record. Three
findings, in order of how much they matter:

1. **It does not register.** Sweeping the assumed latitude half-span from 60° to
   100° and the longitude offset from −20° to +20°, agreement with the finished
   land mask stayed between **63.9% and 69.0% with no peak** — against a **60.0%
   chance level** for two independent masks of this land fraction. A correct
   registration produces a sharp maximum. A flat response across every hypothesis
   means the image does not place onto our frame, so any agreement figure quoted
   from it would be noise presented as validation.
2. **Its usable content is smaller than recorded.** S1 read the letterbox as a
   ~40 px bar across the top; it is actually on the left and right. Column means
   are ~0.3 out to x=86, jump to ~24 at x=87, hold to x=548, then drop back — so
   the content is x=[87..548], y=[0..357], i.e. **462 px** of usable width, not
   637. Row means never letterbox at all.
3. **It has no job left.** Its purpose was to anchor the global frame. The
   Terraqueous NE-II envelope fit now does that to **0.363 px RMS**, measured
   against the map's own drawn projection — several thousand times tighter than a
   462-px-wide reference could manage even if it did register.

The file stays in the manifest (it was consulted, and the hash pins what we
looked at) but carries no registration record, so `sources.py --verify` treats it
like the other unregistered references. Leaving a record that asserts a placement
we have measured to be unreliable would be worse than having none — it is exactly
the class of silently-wrong committed data the SHA-256 guard exists to prevent.
