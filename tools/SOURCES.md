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
| Major_Trade_Routes_of_the_Old_World_Map.png | 1947x1404 | 690,310 | 12026b1e21ad7b9467ff1e3d597e98492739af19e2d8cf97407ddf5d28f7b919 | Games Workshop — "Major Trade Routes of the Old World" | Manifest only, unregistered — S6 reference | no |
| Map-Albion-2.jpg | 900x676 | 521,210 | 2d60a240255cde0bad4122b13f923f33a97601d4825d6c4a557276f5d21d0449 | TBD | TBD | no |
| Map-Araby-2-Political.jpg | 2977x2381 | 777,678 | 614a54d96b1ad181b6db5cbd48688ea340b4106d438e990d2cb4d2fefd718f26 | TBD | TBD | no |
| Map-Norsca-6.jpg | 13500x6000 | 19,310,145 | 48c58079cb9262b66df4823fc2d5e98cf7aad9f72faab69e1752932d85c6d0be | TBD | TBD | no |
| the_empire_1.jpg | 5426x5091 | 22,888,291 | d12726947a3afaee43bbc174dbe95cba1288e7bf4dbf542e0a6a86065642bb29 | TBD | TBD | no |
| TheEmpire.webp | 1596x1024 | 682,992 | e19ad56e0b21023955f3ed91301073aba03efe08b4506b4d6f3e5b4fab51adff | Games Workshop — The Empire provinces map | Empire internal subdivision. **NOT USABLE FOR GEOMETRY** (measured S3a) — misregistered off the coast, and not a chloropleth (see below). **File currently absent from sources/** (August 2026 reorg) — record kept per provenance policy, but `sources.py --verify` will flag it missing until restored or the row is explicitly retired | yes |
| the_empire_2_rivers_drawn.jpg | 1920x1301 | 1,463,260 | e4d4d67afb4705d7e7c139ecd5a0cd0233adff80100939328451b6ecce384ff4 | The above, with canon river courses drawn on in red by the user | Canon-river TOPOLOGY guide for the S6 naming pass — which DEM channel is which. Contributes no geometry (see below) | no |
| the_empire_2.jpg | 1920x1301 | 1,466,126 | 8c3f93454483dc261f933ad3d43530495cb11111071de2511669ac50f5ad2528 | Games Workshop / Warhammer Community — "The Empire of Man" map | Clean counterpart of the annotated map — differencing the two isolates the annotation | no |
| Warhammer_olde_world_map.webp | 1434x975 | 442,484 | d8aad1d1697980aab21f95e5724a9f95d5889656cac73cb66dd5cab578d094f5 | Fan cartography — "Landes and Seas of the Worlde" | Naming + extent confirmation (S6 naming pass) | no |
| canvas.png | 1880x1880 | 1,596,392 | 118e3f15fac97a62502cc81f3e415a383be429e321560fecfcbde5b560f8b0b0 | TBD | TBD | no |
| satellite_globe.jpg | 637x358 | 43,099 | 8b90bae2e491a366a8c5deb3f1e8d9307dac6b8658d0fd7d62bb9c6de242d95b | Fan whole-world satellite/biome render (Steam Workshop) | DE-REGISTERED in S2 - does not register (see below) | no |
| old_world_terrain.jpg | 3016x2080 | 1,140,330 | 80ae22f4aa384049cd42e70ade67db4f57853e6e91c9fbed30458dd9a69c1f91 | Games Workshop — Warhammer: The Old World world map | Old World / Badlands / Dark Lands / Araby / Land of the Dead boundaries. **NOT USABLE FOR GEOMETRY** (measured S3a) — misregistered off the coast, and not a chloropleth (see below) | yes |
| map_of_known_world.jpg | 2048x1449 | 625,772 | 9102bb84f9a4e7ef7cac4c8262e852900dd0b594acc06871de16e347ed14e6c0 | Fan cartography - "Map of the Known World in the Year of our Lord Sigmar 2502" (AndAlso, 2023) | Illustrated relief map with settlement and faction icons. NAMING + extent reference for S6; draws no region boundaries, so it contributes no geometry | no |
| mega_detailed_old_world.jpg | n/a | 385,900,884 | 99b89752c24766a968cd4023a6450aa75bb34a3b01ac6ee6bcda3a698b7c7906 | TBD | TBD | no |
| total_war_states_per_strat_region.jpg | 2048x1593 | 1,112,706 | b8965b704a476a5e93276f217c17dc6b6135301c87564c36ebb6d181252303ca | Fan annotation of the IE parchment master - strategic regions outlined, named, and labelled with their Total War: Warhammer 3 state counts | **NAMED MACRO REGIONS** - the source that binds region names to geometry, without which none of the user's per-region requirements can be checked. 17 named regions; supersedes pizqenw9rd791.jpg for grouping. Frame alias of the twin (exact 0.553 rescale, now pointing at `tww3_ie_parchment.jpg`). Printed counts are a reference, not truth. **Re-added** after the August 2026 retirement — same bytes (SHA-256 confirmed), so registration is restored rather than re-derived | yes |
| start_warhammer_old_world_z10.png | 9795x14734 | 109,573,120 | b9bd24fe451fadcb8763b1ebec54e8065a3aa0b6433502c4b019282c82286fe8 | Games Workshop — official "Warhammer: The Old World" interactive map (start-warhammer.com), zoom-10 base tile layer, stitched by us (TMS tiles, transparent border cropped) | Highest-resolution whole-continent Old World reference in the folder. Base tile ART ONLY — the site's interactive city/army/region markers are separate overlays and are NOT baked in. Naming + extent + coastline/relief cross-reference (S6). Unregistered | no |
| terraqueous_globe.jpg | 4000x3256 | 2,292,545 | c4021e28d8d58bc3f91733df72ee9b7b398f922bb565b0478d3743446d8c15f3 | Fan cartography — "Terraqueous Globe", Kartografia Niepraktyczna 2022 | Whole-world heightmap (NE-II colour-to-height ramp) + coastline. **The single geometric authority** (S3a decision #1) — every other source projects onto it | yes |
| terraqueous_globe_reprojected.png | 8192x3616 | 30,471,432 | 604fc9f92848fc25590f0a7d69b54a46dea79bd1acbc578f250304d36b06888c | Derived from `terraqueous_globe.jpg` (user, August 2026) | `terraqueous_globe.jpg` reprojected from its native Natural Earth II to Miller cylindrical — the mod canvas's own projection (see `config/canvas_frame.py`). Canvas-sized (8192x3616 = WIDTH x HEIGHT). Not yet consumed by any script; `generate_heightmap.py` currently reprojects `terraqueous_globe.jpg` itself via its NE-II fit rather than reading a pre-reprojected copy | no |
| terraqueous_globe_reprojected - rivers.paint | n/a | 61,948,466 | 10359c7f96619c04f58dcd2dff91ba40cd959a14ab0ba7ec7bca4bb806887d7d | Derived from `terraqueous_globe_reprojected.png` (user, August 2026; still being edited locally) | Editable master of the .png below — presumed river-course working layer on the Miller-reprojected canvas, by naming analogy with `the_empire_2_rivers_drawn.jpg`; unconfirmed, flag if wrong | no |
| terraqueous_globe_reprojected - rivers.png | 8192x3616 | 62,831,194 | 1621be72f16c0bfaabfa730c6dbf3e15bc086400400ea0cb83936f098eb5388b | Derived from `terraqueous_globe_reprojected.png` (user, August 2026) | Presumed river-course working layer on the Miller-reprojected canvas (8192x3616); unconfirmed, flag if wrong | no |
| tww3_old_world_mod_parchment.png | 4096x4096 | 8,332,865 | 93f5c7b4791d7a02b60eeb4ba96bf5abc66ad4d650978d1990b022840de903a3 | Fan cartography — "The Old World, all faction starting positions v3.0" | **Denser Old World boundary network** — a line chloropleth, markedly denser than IE over the same arc. Higher precedence inside a masked footprint; the four corner vignettes + the Galleon's Graveyard spiral are excluded (they take cartographic liberties — user-flagged) | no |
| the-old-world-all-faction-starting-position-map-v3_oceans_hatched.png | 4096x4096 | 32,206,014 | ff5fc28a14bd2805fa3462fe362174ca51f6fbaa2536c8a45425f982bbdeb439 | The Old World fan map with ocean strokes drawn on by the user | Hand-marked sea, as above. Calibrated a luminance land/sea cut for this map to 81% balanced accuracy - measurable at last, but well short of the exact silhouette total_war_map_colored.png provides | no |
| the_old_world_bot_left.png | 1195x683 | 1,542,117 | adf58b58178b2de1fb58b3f3d84038125809a8b5b2c4b727f5467f185bde856d | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (bot-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_bot_right.png | 1191x676 | 1,586,780 | 6462a83e8084bc01da73082d7e4099f897c4b6fdb6405e03c410a4213bf2743d | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (bot-right) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_bot_left.png | 1192x680 | 1,610,370 | 31e87b7948fac60aca9e475eda8a4bc3b8938958e2a8a169e1889637f002bb91 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-bot-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_bot_right.png | 1190x676 | 1,581,702 | ebc9ae26794d596d5e2182adafeaaa440d46602df25eff073f30c72e402c9125 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-bot-right) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_top_left.png | 1191x679 | 1,803,901 | bba872c288113332e0c35e003b13c5a56e724226deba61763d247ba2752f3a89 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-top-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_top_right.png | 1191x676 | 1,689,342 | 8ca134d1bea237def8eab18ea9ece930604307865addf86a1587361c2799f6e5 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-top-right) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_top_left.png | 1193x679 | 1,531,068 | 3c92d0603de70557b857df60e3c7f334f1459cc69ec50947b787e2b97601a6a0 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (top-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_top_right.png | 1197x678 | 1,362,417 | b4541e35e06dbed408e9e886da0d97023c2c8db53d1ba6d20457d9363887d86b | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (top-right) of the hi-res Old World map — S3 boundaries | no |
| tww3_colored.png | 4726x3010 | 1,467,069 | d3962b9e28a49765c6c6f236b89b67924d06019835bcc857a51b41e5602b3817 | Fan cartography - flat-filled Total War: Warhammer world map with region boundaries | Demoted from primary to **complement** boundary source (world-map-parchment-areas-onto-globe.md, 2026-07-28): boundary precedence 95, below the parchment master's 100, so it now wins only outside the master's coverage. Flat blue ocean still gives an EXACT land/sea silhouette (no threshold is fitted), and black region lines over flat terrain fills yield 681 clean closed cells across the whole Known World, against our 659 land-state target — the 748-vs-681 clean-cell discrepancy flagged in the S3a-2 review remains explicitly unresolved. See below | yes |
| updated-warhammer-the-old-world-map-v0-eyiuahz1swhg1.webp | 640x938 | 135,766 | 4559b8beb215f976ef8aed1339ef94c36dcf2d40ccb9cb88cc863d8b5cac05da | Games Workshop — updated Old World relief map | Old World relief cross-check (S6) | no |
| wahafa-world-map.jpg | 547x365 | 32,445 | 69f7f4a483dd1976234e1399c88e59225093db101d8af8ba2c974f62d6257bd1 | Fan cartography — "wahafa" whole-world map | Whole-world coastline / extent cross-reference (unregistered) | no |
| tww3_ie_parchment.jpg | 3703x2880 | 3,225,567 | f6e4f53ea80673bb9b792f11b1ac1de387bb8e07757f8a384aa40fd8aea757c1 | Creative Assembly - Total War: Warhammer 3 Immortal Empires parchment campaign map (English) | **PRIMARY BOUNDARY + NAME SOURCE (world-map-parchment-areas-onto-globe.md, 2026-07-28)** - registered by `tools/fit_registration.py --seed wh3_dlc_ie_parchment_map_english` (silhouette objective via the climate map sibling, 10x8 lattice, 12 held-out landmarks). Fit: `refined_iou` 0.6193, `folded_fraction` 0%, `anisotropy_p99` 3.00, `landmark_check_px` mean 426.9 / max 872.1 - reported against the family's only other comparable record (`total_war_map_colored.json`: mean 312.2 / max 844.6, refined_iou 0.6617) as somewhat weaker but consistent (0% folding, same anisotropy), explained by the parchment's silhouette coming via a rescaled sibling rather than an exact flat-fill silhouette. The family's `ie_macro_twin.json` control points (baked standalone when the master was previously absent from `sources/`) reproduce EXACTLY (0.0 px mean/max) against this fit, confirming full reproducibility with the existing placement. Its interior line network is traced with lettering bridged (not erased) into the barrier, and its printed names are the S3a-2 review panel's missing name-to-geometry binding. Also the differencing counterpart for macro grouping (unchanged role). | yes |
<!-- MANIFEST:END -->

## Local organisation: descriptive flat filenames, no subfolders

`sources/` is kept **flat** (no subfolders): `tools/worldgen/sources.py` only
ever looks up `sources/<basename>` directly — it does **not** search
subfolders recursively, despite an earlier draft of this file claiming
otherwise. A file dropped in a subfolder is invisible to `--verify`,
`--update-manifest`, and `load_source_image`. Until that lookup is made
recursive (not currently planned — the churn of keeping every script and
registration record in sync with a moving basename was judged not worth it),
subfolders are not a safe way to organise this folder.

What subfolders would have bought — grouping related sources — is instead done
with a filename prefix that names the family the source belongs to (e.g.
`tww3_*` for the Total War: Warhammer 3 / Immortal Empires parchment family,
`old_world_*` for Games Workshop's Old World tabletop maps, `the_empire_*` for
Empire-specific references, `terraqueous_globe*` for the globe and its
derivatives). Sorted alphabetically, same-prefix files land next to each other
in a flat listing without needing a folder. The manifest's `File` column stays
a bare filename either way; renaming a source here means updating this
manifest row plus every registration record / generator-script constant that
names it — see the August 2026 reorg note below for what that touched.

## Renamed: `the-old-world-all-faction-starting-position-map-v3-0-updated-v0-ml2lq3qfofad1{, - Copy}.png`

Shortened to `the-old-world-all-faction-starting-position-map-v3.png` (clean) and
`the-old-world-all-faction-starting-position-map-v3_oceans_hatched.png` (the
hand-marked-sea copy) — same upload-site-filename problem as the globe below.
Bytes unchanged, confirmed by SHA-256, so both rows above are relabelled, not
new sources.

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
| `tww3_ie_parchment.jpg` (was `wh3_dlc_ie_parchment_map_english.jpg`) | **the master** (3703×2880) | — |
| `pizqenw9rd791.jpg` (retired — no longer in the manifest, see below) | identity — pixel-aligned twin | identical dims, grayscale corr 0.803, median abs-diff 3 |
| `tww3_climate.jpg` (was `3274025515_preview_WH3 climate map 6.0.3.jpg`) | scale 0.6673 | exactly `2471/3703 = 1922/2880` |
| `Immortal-Empires-Map-Feature-Image-scaled.jpg` (absent from `sources/`, pre-existing) | full width `x[8..3692]`, crop `y[224..2296]`, ratio 1.4391/1.4389 | multi-scale NCC, peak 0.6701 |

That collapses four control-point authoring jobs into one, and means a
control-point correction propagates to all four automatically. Immortal Empires
is a *playable* map rather than a globe — Ulthuan is drawn roughly twice as large
relative to the world as it is on the Terraqueous globe — so the master's record
is a dense thin-plate warp, never an affine. It contributes **interior boundary
lines and names only, never coastline**: the committed `land_sea_mask.png` is the
sole coastline authority (user decision #1, 2026-07-25), which is exactly what
makes a rubber-sheeted registration acceptable here. Local scale error moves an
interior border a few pixels inside a landmass; it cannot put a coast in the sea.

## Not usable for geometry (S3a): `old_world_terrain.jpg` (was `map-the-old-world.jpg`), `TheEmpire.webp`

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
`registration/map-the-old-world.json` / `registration/TheEmpire.json` (record
filenames unchanged by the reorg — only the `source` field inside
`map-the-old-world.json` was updated, to `old_world_terrain.jpg`) and
[PROVENANCE.md](PROVENANCE.md).

## The annotated Empire map (`the_empire_2_rivers_drawn.jpg`, was `TheEmpireRivers - drawn on.jpg`)

The user drew the canon Empire river courses onto the GW map in bright red. It is
a **topology guide for S6**, not a geometry source: it records which rivers exist
and how they join, while the actual courses in `map_data/rivers.png` come from the
heightmap's own drainage (see [PROVENANCE.md](PROVENANCE.md)). That split is
deliberate — the annotation is freehand and the underlying map is a stylised
illustration that does not register tightly, so letting it place pixels would put
rivers off-valley; letting it *label* them cannot.

Extracting the strokes is a solved step: **difference it against the clean
`the_empire_2.jpg`** (was `TheEmpireRivers.jpg`, the same image without the
annotation). The strokes are
exactly what changed. This also disposes of the coats of arms, which are bright
red in *both* images and therefore cancel — no colour threshold or shape
heuristic survives contact with heraldry, but a difference does.

## De-registered in S2: `satellite_globe.jpg` (was `images.steamusercontent.jpg`)

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

## Renamed / reorganised, August 2026: descriptive flat filenames

The user reorganised `sources/` locally for legibility as the source count grew
past what a bare upload-site filename (`pizqenw9rd791.jpg`, `3274025515_preview_WH3
climate map 6.0.3.jpg`) or a same-named-but-different set of tiles could keep
straight. Nine tracked rows were renamed; bytes unchanged (confirmed by
SHA-256) in every case, so these are relabelled rows, not new sources:

| Old filename | New filename |
|---|---|
| `Major_Trade_Routes_of_the_Old_World_Map.webp` | `Major_Trade_Routes_of_the_Old_World_Map.png` (extension corrected — the bytes were already PNG) |
| `map-the-old-world.jpg` | `old_world_terrain.jpg` |
| `images.steamusercontent.jpg` | `satellite_globe.jpg` |
| `Map-The-Empire-2-Detailed-Color.jpg` | `the_empire_1.jpg` |
| `TheEmpireRivers.jpg` | `the_empire_2.jpg` |
| `TheEmpireRivers - drawn on.jpg` | `the_empire_2_rivers_drawn.jpg` |
| `total_war_map_colored.png` | `tww3_colored.png` |
| `wh3_dlc_ie_parchment_map_english.jpg` | `tww3_ie_parchment.jpg` |
| `the-old-world-all-faction-starting-position-map-v3.png` | `tww3_old_world_mod_parchment.png` |

Every registration record's `source` field and every `frame_alias.of` pointer
into the renamed IE-parchment master, plus the matching constants in
`generate_state_labels.py` (`BOUNDARY_SOURCES`, `BOUNDARY_EXCLUDE`,
`MACRO_CLEAN_MASTER`), were updated to match. `terraqueous_globe.jpg`,
`mega_detailed_old_world.jpg`, `3274025515_preview_WH3 climate map
6.0.3.jpg`→already-named `tww3_climate.jpg`, and `start_warhammer_old_world_z10.png`
kept the names they already had.

A duplicate — `wh3_dlc_ie_parchment_map_english - Copy.jpg`, byte-identical to
the tracked master — was deleted rather than kept as a second row; it carried
no information the master row doesn't already pin.

**Three tracked, previously-registered sources were retired, confirmed final by
the user** rather than renamed (no matching SHA-256 anywhere on disk after the
reorg): `pizqenw9rd791.jpg` (the `ie_macro_grouping` twin), `tww3_map_stitched.png`
plus its `.paint` master and all four pre-stitch tiles (the `TWW3` relief-detail
source in `generate_heightmap.py`), and `total_war_states_per_strat_region.jpg`
(the named-macro-region source). Unlike the kept-not-deleted policy used for
*misregistered-but-present* sources (`map-the-old-world.json` / `TheEmpire.json`,
above), these files were simply gone with no plan to restore them, so — per an
explicit user decision — their manifest rows and registration records
(`registration/ie_macro_twin.json` + seed, `registration/ie_named_regions.json`
+ seed, `registration/tww3_map_stitched.json`) were removed outright rather than
left dangling. Both scripts consuming the load-bearing two now degrade
gracefully instead of crashing: `generate_heightmap.py`'s `tww3_detail()`
already returned `(None, None)` when its registration is absent (no code
change needed — it just does that now), and
`generate_state_labels.py:assign_macros()` was changed to log a warning and
report every cell as macro 0 (unassigned) instead of raising `SystemExit` when
no source carries the `ie_macro_grouping` role. That code change is permanent
regardless of what happens to any individual source, since a future source
going missing shouldn't be able to take the whole run down either.

**`total_war_states_per_strat_region.jpg` was re-added shortly after** (same
bytes, SHA-256 confirmed, so its registration record and manifest row were
restored rather than re-derived) — its `frame_alias.of` now points at the
current name of the master, `tww3_ie_parchment.jpg`. It was never read by role
in any active script, so no code depended on its absence or needs to change now
that it's back. `pizqenw9rd791.jpg` and `tww3_map_stitched.png` remain retired.

**Four files new to `sources/`** were folded in: `start_warhammer_old_world_z10.png`
already carried a fully-authored row (added in an earlier pass); three
`terraqueous_globe*reprojected*` files (a canvas-sized reprojection of the globe
and a canvas-sized rivers working layer, plus its `.paint` master) were added as
`TBD` rows — their exact origin/role needs a human pass, per the usual new-source
convention. A fifth new file, `qa_terraqueous_globe_river_errors_circled.png`,
was **not** added to the manifest: its name matches the existing
`terraqueous_globe_with_NS_lines.jpg` pattern of local-only QA/markup scratch
that is deliberately excluded (see `config/canvas_frame.py`'s `Y0` derivation
comment) rather than a reference source — if that's wrong, it should be added
by hand with `--update-manifest` or a manual row.
