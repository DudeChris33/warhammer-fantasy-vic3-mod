# Source manifest

The source-driven map pipeline reads reference imagery from a local `sources/`
folder at the repo root. It mixes Games Workshop cartography, a Total War
screenshot mosaic, and fan maps (third-party IP), plus tens of MB of binaries
(decision #2 in
[world-map-source-driven.md](../planning/requests/world-map-source-driven.md)).
**As of 2026-09-03, `sources/` is committed to the repo in full via Git LFS**
(user decision — private repo, not worth manually shifting ~2.3GB between
devices; previously it was gitignored and tracked only by this manifest).

This file remains the committed **manifest** that documents those files: every
source's filename, dimensions, byte size, SHA-256, origin, pipeline role, and
whether it carries a [registration record](registration/). It makes the exact
inputs behind every committed bitmap auditable without redistributing any art
outside this repo, and it is the hash `tools/worldgen/sources.py` checks a
source against before the ingestion stage is allowed to read it — so a swapped
or edited `sources/` file can never silently change a committed,
multiplayer-synced bitmap.

Consulting these references for geometry is standard fan-mod practice; copying
their pixels is the line we do not cross (see [PROVENANCE.md](PROVENANCE.md)).

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

## Layout: `sources/` is organized into subfolders by role

Files live directly under `sources/`, or in one of three subfolders:
`originals/` (the raw reference imagery), `gimp/` (editable masters — GIMP
`.xcf`, since the user switched off MS Paint), and `dots/` (crops and example
renders from the paired-anchor-dot registration workflow). A fourth folder,
`WIP/`, holds local scratch that is deliberately **not** manifest-tracked.
`tools/worldgen/sources.py`'s `resolve_source_path()` searches all of these by
bare filename, so the **File** column below stays a bare filename regardless of
which subfolder a source actually sits in — the manifest audits identity
(dims/bytes/SHA/origin/role), not physical location. `--update-manifest`
discovers files the same way (root + the three tracked subfolders) and refuses
if a name collides across more than one of them.

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
| 0 255 191.txt | n/a | 4,131 | 708823ecf767854c37888048f6854ef9d91508341a05ce601eec09aee37e16cb | User | RGB color codes reference for dot markers used in the paired-anchor-dot workflow | no |
| Major_Trade_Routes_of_the_Old_World_Map.png | 1947x1404 | 690,310 | 12026b1e21ad7b9467ff1e3d597e98492739af19e2d8cf97407ddf5d28f7b919 | Games Workshop — "Major Trade Routes of the Old World" | Manifest only, unregistered — S6 reference | no |
| bretonnia_black_white_colored.png | 4210x4700 | 14,643,218 | 05d03cf362e17d8c805ead02915b66334be75f01d52346936f2ac611675a3610 | Internet find; the user colored the ocean blue | Primarily Bretonnia village placement; secondarily other Bretonnia features | no |
| colored_globe.jpg | 1680x1214 | 429,642 | 91e12fbb2938d2ec61ed78abd1d42ad10615a3d427068acd5830a9598bf214c0 | Fan cartography — David "Fahran" Mills "Warhammer World Map" (war-rvr.net, 2006), a whole-world relief/satellite render with a blue ocean. Added by the user 2026-08-13 | Whole-world COASTLINE silhouette (`blue_sea` kind: ocean is blue-dominant but brightness-varying). Balanced land/sea (0.366 vs mask 0.369) so it registers globally, unlike the land-heavy regional tiles. A DIFFERENT source from the terraqueous globe (different projection — a freehand rectangular/cylindrical relief render, ~1.38:1, closest to a latitude-cropped equirectangular but NOT an analytic projection, so it stays a `control_point_warp`, not an analytic inverse; identified 2026-08-15), registered against the mask for coastline agreement; mask stays the sole authority | yes |
| land_sea_mask.png | 8192x3616 | 358,875 | ddfd2622ce0bd52cece251135d999d3904c802d5538e40af60f47e2e892bb28e | PNG export of `land_sea_mask.xcf` | The real land/sea mask in use | no |
| land_sea_mask.xcf | n/a | 903,760 | 1b18d44f55e4b7d654f06f34b743397fe77c9f01db77536af8adcff2e2539f0b | User — copy of the user's hand-drawn `terraqueous_globe_reprojected - coasts.xcf`, filled to form a land-sea mask. Switched from MS Paint (`land_sea_mask.paint`) to GIMP (`.xcf`), same editable-master role | Editable master of the land-sea mask below | no |
| mega_detailed_old_world.jpg | n/a | 385,900,884 | 99b89752c24766a968cd4023a6450aa75bb34a3b01ac6ee6bcda3a698b7c7906 | Internet find | Primarily Old World town and forest placement; secondarily other Old World features | no |
| named_globe.png | 4096x2048 | 15,109,233 | 0f89110c2a4cc471f53319a05aba439a4a1e69119d06278b5374b0214ff22eff | Fan cartography — a labelled whole-world Warhammer map, blue-ocean relief with region names (Naggaroth, Ulthuan, the Old World, Southlands, Grand Cathay, …). Exact author unconfirmed. Added by the user 2026-08-12 | **Projection: equirectangular (plate carrée)** — identified 2026-08-15. Exactly 2:1 at 4096×2048 (power-of-two globe-texture dims), filled corner-to-corner with ocean/ice (an oval projection would leave the corners empty), meridians vertical. **Registered 2026-08-15** (`tools/registration/named_globe.json`) as a `control_point_warp`. A pure analytic-equirectangular placement was tried first and rejected (the artist drew landmasses at different proportions than the mask), so the geographic box was MEASURED by silhouette IoU against `land_sea_mask.png`: named_globe covers only ~320° of longitude and is latitude-cropped at ~40°S (affine cx≈2048 sx≈12.79 cy≈1348 sy≈17.50, 0.638 affine IoU), so it has NO coverage of the canvas far-eastern seam or its southern band. That affine seeds an 11×7 lattice `register.refine` pulled onto the mask to **0.788 IoU** (no folds, anisotropy≤3). Contributes NO coastline (mask stays sole authority) — a whole-world coastline reference like `colored_globe`, at a third projection. MACHINE-FITTED; re-derive, do not hand-edit. PROVISIONAL until the user accepts the render | yes |
| ocean_currents - Copy.png | 10233x3616 | 3,679,568 | 0a3ee852264a8cd8fbb9c537400012aa0c0018f3b1ee25e097c9e7dc7a2a6912 | Copy of `ocean_currents.png` | Assists with x-axis (seam) wrapping when working with the ocean-currents layer | no |
| ocean_currents.png | 8192x3616 | 959,633 | 57076d7be6a0f1aa1deaad25831cb24c6d99e7733b84310e18de70c43e174c9f | Generated (Claude) | Partially informs sea zone placement | no |
| old_world_regions.png | 4096x4096 | 5,375,145 | 3b944a5578286ae0dd1817857979b337903b250b9d56dd9f9424bdb406240709 | PNG export of `old_world_regions.xcf` | Maps which region each state belongs to | no |
| old_world_state_regions - borders_only.xcf | n/a | 1,094,090 | 8517d9881ed620e835179db30592ae4a94ab521665bc010bf1323eaa53d4d9ef | User — GIMP `.xcf` | Working file — the magenta border lines isolated from `old_world_state_regions.xcf`, no region fill (parallel to `terraqueous_globe_reprojected - coasts_only.xcf`) | no |
| old_world_state_regions.png | 4096x4096 | 18,715,761 | c8faec178b4673a556f37a784155ad0418c3a88dc2c427bc7413d87c836dc98e | PNG export of `old_world_state_regions.xcf` | Map of the borders of all state regions in the Old World | no |
| old_world_state_regions.xcf | n/a | 38,262,830 | 76805da4cd940e672674e195a0bffd6c831dc11427c2537f4182c1b3b256bdd6 | Generated, with the user's hand-drawn corrections. Switched from MS Paint (`old_world_state_regions.paint`) to GIMP (`.xcf`) | Map of the borders of all state regions in the Old World | no |
| old_world_terrain.jpg | 3016x2080 | 1,140,330 | 80ae22f4aa384049cd42e70ade67db4f57853e6e91c9fbed30458dd9a69c1f91 | Games Workshop — Warhammer: The Old World world map | Old World / Badlands / Dark Lands / Araby / Land of the Dead boundaries. **NOT USABLE FOR GEOMETRY** (measured S3a) — misregistered off the coast, and not a chloropleth (see below) | yes |
| old_world_z10 - dots_5.png | 6134x4958 | 42,730,538 | 0d9bf2273d6051086fb62bea4377bb68cbbc88cf2334d2dd450b97be81941190 | Northern Old World crop of `old_world_z10.png`, dot-marked by the user | Region 5 (northern relief) dot-picking reference for the paired-anchor-dot workflow — the marked counterpart of `start_warhammer_old_world_northern.png`. Not consumed by any script (dot-picking reference only) | no |
| old_world_z10 - grayscale.png | 6658x9824 | 70,851,835 | c2b19d3cd0ce5c0551f9c628f17160ea9dc1cf03eec23320549758be1f43a095 | Grayscale copy of `old_world_z10.png` | Same role as `old_world_z10.png`, in grayscale | no |
| old_world_z10.png | 6658x9824 | 120,598,002 | 856dfa35a633a3e7dead1972a37660791fc2b8fcbb18a59f3a535b2d3109428a | Games Workshop — official "Warhammer: The Old World" interactive map (start-warhammer.com), zoom-10 base tile layer, stitched by us (TMS tiles, transparent border cropped) | Highest-resolution whole-continent Old World reference in the folder. Base tile ART ONLY — the site's interactive city/army/region markers are separate overlays and are NOT baked in. Naming + extent + coastline/relief cross-reference (S6). Unregistered | no |
| satellite_globe.jpg | 637x358 | 43,099 | 8b90bae2e491a366a8c5deb3f1e8d9307dac6b8658d0fd7d62bb9c6de242d95b | Fan whole-world satellite/biome render (Steam Workshop) | **Projection: equirectangular** (rectangular whole-world texture, pillarboxed to 16:9 — black bars at x=[0..86] and x>548, content x=[87..548]; the map itself is corner-to-corner with vertical meridians). DE-REGISTERED in S2 — de-registered for cloud cover + the narrow 462-px usable width, not for its projection (see below) | no |
| start_warhammer_old_world_northern_anchor_dot_warp_example.png | 6134x4958 | 33,051,768 | 9bb2fc6b2570b88d7c8bb0ac703afb01a39fcbbceb4b6ae222dfb54d3dbc1303 | TBD | TBD | no |
| start_warhammer_old_world_northern_anchor_dot_warp_example.xcf | n/a | 87,883,816 | a3b77a7fb7733f2feca32700f05b82e757eb1ba82695f0d880d290ea0d5fc9a5 | TBD | TBD | no |
| terraqueous_globe.jpg | 4000x3256 | 2,292,545 | c4021e28d8d58bc3f91733df72ee9b7b398f922bb565b0478d3743446d8c15f3 | Fan cartography — "Terraqueous Globe", Kartografia Niepraktyczna 2022 | Whole-world heightmap (NE-II colour-to-height ramp) + coastline. **The single geometric authority** (S3a decision #1) — every other source projects onto it | yes |
| terraqueous_globe_reprojected - adjacencies.xcf | n/a | 90,724,139 | 634501465bb5b97a25235557d936e8601d13e6abcbc6ce5d30fb86def66c62a4 | User — GIMP `.xcf` marked on the reprojected globe canvas | Marks which provinces should be declared adjacent (straits/canals) for `map_data/adjacencies.csv` | no |
| terraqueous_globe_reprojected - coast_river_state.png | 8192x3616 | 510,813 | 10661b2f2f4024f301fc9f8e4593aadcf3e43711426eb4e6b012665fd5a2b1e9 | Derived from `terraqueous_globe_reprojected - full.xcf` | Coasts, rivers, and state-border layers composited onto one canvas for cross-referencing. **Temporary working file, per the user — not meant to be committed** (lives in the gitignored `sources/gimp_exports/` folder) | no |
| terraqueous_globe_reprojected - coast_river_state.xcf | n/a | 2,189,182 | f1e19d950573cb3c94848f11d06120d06b459570dc7841da9612bf5c060fe896 | User — GIMP `.xcf` | Editable master of the coast_river_state.png export above. **Temporary working file, per the user — not meant to be committed** despite living in the tracked `sources/gimp/` folder; left untracked deliberately | no |
| terraqueous_globe_reprojected - coasts.png | 8192x3616 | 364,444 | 5490a6285b5598fff63d9b84d2a585d01aacc9c0b0636f674d9024172af03163 | Derived from `terraqueous_globe_reprojected.png` (user, August 2026) | The hand-traced coastline (magenta line on the Miller-reprojected canvas, 8192x3616) that `generate_coastline_mask.py` consumes as the coastline authority (user decision, 2026-08-14: "the traced coastline wins") — supersedes the height-ramp coast extraction. Renamed from `terraqueous_globe_reprojected - rivers.{paint,png}` (was misidentified as a river-course layer, "unconfirmed, flag if wrong") once its actual role was confirmed | no |
| terraqueous_globe_reprojected - coasts.xcf | n/a | 1,360,962 | 29fe0a983b2a0b8ad5e16fd2af2590462011aba07c4891bb9d0d937d9aa2e7b5 | Derived from `terraqueous_globe_reprojected.png` (user, August 2026; still being edited locally). Switched from MS Paint (`... coasts.paint`) to GIMP (`.xcf`) | Editable master of the .png below | no |
| terraqueous_globe_reprojected - dots_1.png | 4645x1358 | 7,811,811 | 676815ee0b0c61ce2ee9c768f1c0b6b55b5f6eecb1d829deb2f9675f3e60e409 | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Region 1 (Empire) dot-picking reference for the paired-anchor-dot workflow — canvas frame with that region's anchor dots marked. Not consumed by any script (dot-picking reference only) | no |
| terraqueous_globe_reprojected - dots_2.png | 4639x1394 | 8,024,366 | af8b800366e5cb29bdf6c97a8b0324b00fbdaf926cf1ece3ae1daf31da24b4d9 | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Region 2 (Bretonnia+Estalia+Tilea) dot-picking reference, same role | no |
| terraqueous_globe_reprojected - dots_3.png | 4997x971 | 5,798,227 | 6f7860f50ad231a5b3ad9ded2837c3e4b6a9b72798c7697a319a7225a5b03f46 | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Region 3 (Kislev+Norsca) dot-picking reference, same role | no |
| terraqueous_globe_reprojected - dots_4.png | 5690x1788 | 13,203,707 | 838f75bfdd31ef821e05501d27dcec28d6dd5ad990e4a7873a24f8b6982dc530 | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Region 4 (Dark Lands) dot-picking reference, same role | no |
| terraqueous_globe_reprojected - dots_5.png | 5309x2051 | 13,897,550 | 0461ce39b114190aafb5916ba7219a7c6601b3104aa511052dc6f02e4b62cda9 | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Region 5 (start_warhammer northern relief) dot-picking reference, same role | no |
| terraqueous_globe_reprojected - dots_6.png | 5286x2051 | 13,830,559 | 6ea0d064b0dfc0ebf4da43b2f6477cd51d3ac0950b8369b298fb939910fb33bf | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Region 6 (Badlands+Nehekhara) dot-picking reference, same role | no |
| terraqueous_globe_reprojected - dots_7.png | 8192x3616 | 33,038,270 | 5f6f59a9b0fb7b53731ccb782518048f80df312ad3bd934f77a13b41a4feebe9 | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Region 7 dot-picking reference for the paired-anchor-dot workflow, same role as dots_1-6 | no |
| terraqueous_globe_reprojected - dots_7.xcf | n/a | 201,550,812 | accd74959ba650f0004704c73923f74b528a7a70f374866653f8e50c01312b00 | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Editable master of the dots_7.png export above | no |
| terraqueous_globe_reprojected - full.png | 8192x3616 | 33,842,422 | 3614a4c7d62224b051d359149af82c837349ba88a91b7abfbdc3dedcefdce774 | User — flattened export of `terraqueous_globe_reprojected - full.xcf` | All hand-drawn layers (coastline, sea zones, state regions, rivers, political labels) composited onto one PNG — the flattened export of the full.xcf master, same role | no |
| terraqueous_globe_reprojected - full.xcf | n/a | 99,969,815 | 9dc63c742f9ac154fd2d375eee1f9b6fee9faf4e3d6d95dbc17120ed8bedaa39 | User — GIMP `.xcf`, multi-layer master over `terraqueous_globe_reprojected.png` (September 2026) | The consolidated master holding every hand-drawn layer (coastline, sea zones, state regions, rivers, political labels) — the other per-topic `.xcf`/`.png` exports in this folder are each `full.xcf` with one of those layers toggled off (confirmed by the user: `political` = full minus rivers, `water` = full minus state borders). Not itself read by any script | no |
| terraqueous_globe_reprojected - grayscale.png | 8192x3616 | 24,587,697 | e5a40962048ea5fa68d752899cc89ee61ddab565b0e49c851bfe4905f56e4b7c | Grayscale copy of `terraqueous_globe_reprojected.png` | Same role as `terraqueous_globe_reprojected.png`, in grayscale | no |
| terraqueous_globe_reprojected - impassable_terrain.png | 8192x3616 | 118,684,557 | cef2a44045d0fe276055dd3427dba51afa05bc606188446e521b5fcc404debc4 | Flattened PNG export of `terraqueous_globe_reprojected - impassable_terrain.xcf` (gitignored — lives in `sources/gimp_exports/`) | Impassable terrain painted directly on the canvas — the local-machine-only working export consumed by `validate_map._check_canon_cities`'s impassable-collision warning and `render_canon_cities_preview.py` (board #3789/#3788) | no |
| terraqueous_globe_reprojected - impassable_terrain.xcf | n/a | 91,542,936 | b23d07b3a738212587b3be6e122652c27101b16d859ba0323462c9cbc972d4f0 | User — GIMP `.xcf` painted directly on the reprojected globe canvas | Editable master of the impassable_terrain.png export above — impassable terrain (mountains, etc.) marked for the barrier-city safety-overlay tooling (board #3789/#3788) | no |
| terraqueous_globe_reprojected - rivers.png | 8192x3616 | 160,972 | 84bc257f32852ae6bec9644948aff56eb76e5537380a0c54c122b3625a9ed87a | Derived from `terraqueous_globe_reprojected - full.xcf` (user, September 2026) | The rivers layer of `full.xcf` in isolation (**pure cyan `0,255,255`** line, transparent elsewhere): the hand-traced canon river network over the Old World. **Consumed by `tools/generate_rivers.py` (board #3703)** as the canvas-native river source — extracted by colour, 1:1 with the canvas, no registration (the `- coasts.png` / `- sea_zones.png` idiom). This is now the geometry authority for `map_data/rivers.png`, replacing the old heightmap drainage. Regenerating the committed bitmap from it is a user-gated visual step (render + accept) | no |
| terraqueous_globe_reprojected - rivers.xcf | n/a | 307,019 | 14de439c85b859d935ca6688dc6ca1b525fb33facf78ee16bea2af0afcbb1288 | Derived from `terraqueous_globe_reprojected - full.xcf` (user, September 2026) | Editable master of the .png above | no |
| terraqueous_globe_reprojected - sea_zones.png | 8192x3616 | 225,017 | 8679603e36441086f2171bd66e257e5f945782458a2128f4d62138db90f36732 | Derived from `terraqueous_globe_reprojected.png` (user, August 2026) | The hand-drawn sea-zone network (canvas-space, 8192x3616): **magenta (255,0,255) = coastline, purple (127,0,255) = the sea-zone boundaries** dividing the water into naval zones. `generate_sea_zones.py` consumes the purple lines as barriers and flood-fills the water between them into zones (board #2593). Drawn using the earlier auto-partition renders as reference, then completed by hand. No registration (already in canvas space) | no |
| terraqueous_globe_reprojected - sea_zones.xcf | n/a | 634,771 | 13048dc92fb8f39547e7c66a43f5afbfc4aa11010df0f323fa44ead077f0d1f7 | Derived from `terraqueous_globe_reprojected.png` (user, August 2026; still being edited locally). Switched from MS Paint (`... sea_zones.paint`) to GIMP (`.xcf`) | Editable master of the .png below | no |
| terraqueous_globe_reprojected - state_regions.png | 8192x3616 | 194,002 | 42cf27b4d109a95ebb873dc75bc8ec95ce690542eab8bbf4a46957af2c26dc3e | Composited (2026-09-04) from `terraqueous_globe_reprojected.png` + the user's hand-edited crop `old_world_state_regions_on_globe_borders_only_nearest_drawn_on.png`, pasted back at its exact canvas position (3323, 37), located by template match against the parent (96% pixel match; the differing 3.8% is the hand-drawn magenta network) | The hand-drawn magenta state-region boundary network (Old World only) that `generate_provinces.py` consumes as `STATE_REGIONS_SOURCE` — replaces the previously-missing file of this name | no |
| terraqueous_globe_reprojected - state_regions.xcf | n/a | 470,317 | db516b39e0f93a24bfeebf78136d280ec3ca3e3221c144ab7d9f7b02f567d0a0 | Derived from `terraqueous_globe_reprojected.png` (user, August 2026; still being edited locally). Switched from MS Paint to GIMP (`.xcf`) | Editable master of `terraqueous_globe_reprojected - state_regions.png` below | no |
| terraqueous_globe_reprojected - strategic_regions.png | 5310x2044 | 216,621 | dd8ac943d7bc22d5d882e376c8014b9f83a15f5e46d57037e0f442222dc33295 | User-painted (MS Paint) realm/strategic-region fill over the same crop as `terraqueous_globe_reprojected - state_regions.png`; a top-left crop of the main 8192x3616 canvas at zero offset/zero scale (confirmed 2026-09-05: its magenta border network is pixel-identical to that image's, IoU 0.9999 against the already-registered full canvas — no separate registration record needed) | Realm-assignment input for board #2931's land canon naming — classified by exact RGB against `tools/config/strategic_region_colors.json` (colours are arbitrary MS Paint swatch picks, confirmed by the user, unrelated to `old_world_region_colors.json`) | no |
| terraqueous_globe_reprojected - tiny_islands_merger.png | 8192x3616 | 33,555,541 | 84de6f1b8bbac49542f540c5640b171cee99b8f315207de2bb820cf856d1d8bb | PNG export of `terraqueous_globe_reprojected - tiny_islands_merger.xcf` | User-painted filled circles around clusters of tiny islands that `generate_provinces.py` should merge into a single province each — the tiny-island override `land_provinces.island_override_zones` reads (board #2930) | no |
| terraqueous_globe_reprojected - tiny_islands_merger.xcf | n/a | 88,965,136 | f0357a18892aa70b02442af7df3b9886ade4736315950467beba18386460dcdd | User — GIMP `.xcf`, drawn on a blank canvas the size of the reprojected globe | Editable master of `terraqueous_globe_reprojected - tiny_islands_merger.png` above | no |
| terraqueous_globe_reprojected.png | 8192x3616 | 30,471,432 | 604fc9f92848fc25590f0a7d69b54a46dea79bd1acbc578f250304d36b06888c | Derived from `terraqueous_globe.jpg` (user, August 2026) | `terraqueous_globe.jpg` reprojected from its native Natural Earth II to Miller cylindrical — the mod canvas's own projection (see `config/canvas_frame.py`). Canvas-sized (8192x3616 = WIDTH x HEIGHT). Not yet consumed by any script; `generate_heightmap.py` currently reprojects `terraqueous_globe.jpg` itself via its NE-II fit rather than reading a pre-reprojected copy | no |
| terraqueous_globe_reprojected.xcf | n/a | 87,570,774 | 557e3e02f43e61f4c02d84428b5feb744d8223f987f9a11eea6961d1b6697943 | TBD | TBD | no |
| terraqueous_globe_with_NS_lines.jpg | 4000x3256 | 4,397,707 | 179ea7271e2adc0d509bce5358d40c3a60a36c251309dac4377a5acef0ca1c9c | Derived from `terraqueous_globe.jpg` (user) | `terraqueous_globe.jpg` with a north-south graticule drawn on, used as a registration/projection-check reference; contributes no geometry (globe stays the coastline authority) | no |
| the_empire_1.jpg | 5426x5091 | 22,888,291 | d12726947a3afaee43bbc174dbe95cba1288e7bf4dbf542e0a6a86065642bb29 | Internet find | Very detailed map of the Empire — villages, terrain, rivers, names, etc. | no |
| the_empire_2.jpg | 1920x1301 | 1,466,126 | 8c3f93454483dc261f933ad3d43530495cb11111071de2511669ac50f5ad2528 | Games Workshop / Warhammer Community — "The Empire of Man" map | Clean counterpart of the annotated map — differencing the two isolates the annotation | no |
| the_empire_2_rivers_drawn.jpg | 1920x1301 | 1,463,260 | e4d4d67afb4705d7e7c139ecd5a0cd0233adff80100939328451b6ecce384ff4 | The above, with canon river courses drawn on in red by the user | A **which-rivers-exist-and-how-they-join reference** for the Empire only — never geometry. Superseded as the geometry source by the user's canvas-native cyan trace (`terraqueous_globe_reprojected - rivers.png`, board #3703); `map_data/rivers.png` is now that trace, not heightmap drainage, so this map is a naming/topology reference the user reads by eye, not an input to any script (see below) | no |
| tww3_climate.jpg | 2471x1922 | 2,022,554 | fae9e090f0b2ffba1f82008dec5c2c36cf6a03dd0eaca0808b8822ba7b413edb | Total War: Warhammer 3 | Shows the (super-abstracted) climate used in the Total War game | no |
| tww3_colored.png | 4726x3010 | 1,467,069 | d3962b9e28a49765c6c6f236b89b67924d06019835bcc857a51b41e5602b3817 | Fan cartography - flat-filled Total War: Warhammer world map with incorrect region boundaries | Demoted from primary to **complement** boundary source (world-map-parchment-areas-onto-globe.md, 2026-07-28): boundary precedence 95, below the parchment master's 100, so it now wins only outside the master's coverage. Flat blue ocean still gives an EXACT land/sea silhouette (no threshold is fitted), and black region lines over flat terrain fills yield 681 clean closed cells across the whole Known World, against our 659 land-state target — the 748-vs-681 clean-cell discrepancy flagged in the S3a-2 review remains explicitly unresolved. See below | yes |
| tww3_colored.xcf | n/a | 3,498,382 | a2e854fb8567386b5f718dd6f76a41fc9ae954adc024d5976d6751628b45e496 | TBD | TBD | no |
| tww3_ie_parchment.jpg | 3703x2880 | 3,225,567 | f6e4f53ea80673bb9b792f11b1ac1de387bb8e07757f8a384aa40fd8aea757c1 | Creative Assembly - Total War: Warhammer 3 Immortal Empires parchment campaign map (English) | **PRIMARY BOUNDARY + NAME SOURCE (world-map-parchment-areas-onto-globe.md, 2026-07-28)** - registered by `tools/fit_registration.py --seed wh3_dlc_ie_parchment_map_english` (silhouette objective via the climate map sibling, 10x8 lattice, 12 held-out landmarks). Fit: `refined_iou` 0.6193, `folded_fraction` 0%, `anisotropy_p99` 3.00, `landmark_check_px` mean 426.9 / max 872.1 - reported against the family's only other comparable record (`total_war_map_colored.json`: mean 312.2 / max 844.6, refined_iou 0.6617) as somewhat weaker but consistent (0% folding, same anisotropy), explained by the parchment's silhouette coming via a rescaled sibling rather than an exact flat-fill silhouette. The family's `ie_macro_twin.json` control points (baked standalone when the master was previously absent from `sources/`) reproduce EXACTLY (0.0 px mean/max) against this fit, confirming full reproducibility with the existing placement. Its interior line network is traced with lettering bridged (not erased) into the barrier, and its printed names are the S3a-2 review panel's missing name-to-geometry binding. Also the differencing counterpart for macro grouping (unchanged role). | yes |
| tww3_old_world_mod_grayscale.png | 4096x4096 | 16,207,148 | a02fed5a10833e32988fe2b83f894e529fa1894370e13929c9a1533989c762e4 | Grayscale copy of `tww3_old_world_mod_parchment.png` | Same role as `tww3_old_world_mod_parchment.png`, in grayscale | no |
| tww3_old_world_mod_parchment - dots_1.png | 1456x1469 | 1,917,139 | 5639bb30e01a893a94d322d88099ea2391c1c8476109fd0284dcb861526cb6d8 | Empire crop of `tww3_old_world_mod_parchment.png`, dot-marked by the user | Region 1 (Empire) parchment-tile dot-picking reference — matching counterpart to `terraqueous_globe_reprojected - dots_1.png`. Board #3570: the verified input `sources.load_or_derive_image_rgba`/`worldgen.derive_crop.derive_clean_source` re-derive the dot-free Empire crop from on every pipeline call, per `tools/registration/seeds/tww3_old_world_mod_parchment_empire.json`'s `dots_source` field — no cached crop file exists any more | no |
| tww3_old_world_mod_parchment - dots_2.png | 1598x1789 | 3,909,655 | c5ee9b4537a9dd81d4486f65d16a5b7d4d958c624ee2bddf3489c24d84270549 | Bretonnia+Estalia+Tilea crop of `tww3_old_world_mod_parchment.png`, dot-marked by the user | Region 2 parchment-tile dot-picking reference, same role as dots_1 — the verified input the bretonnia crop is re-derived from on every load (board #3570) | no |
| tww3_old_world_mod_parchment - dots_3.png | 2939x1436 | 4,091,250 | 30c4dffaf89e9dab9e820c3b92ca88e1c93fec26c7c1f2360db35f9eb1b0b26b | Kislev+Norsca crop of `tww3_old_world_mod_parchment.png`, dot-marked by the user | Region 3 parchment-tile dot-picking reference, same role as dots_1 — the verified input the kislev_norsca crop is re-derived from on every load (board #3570) | no |
| tww3_old_world_mod_parchment - dots_4.png | 1965x2779 | 7,724,885 | 36c7cf08681cc696fd2132d7467939bed136db75aa66c886b1e079cb06aae965 | Dark Lands crop of `tww3_old_world_mod_parchment.png`, dot-marked by the user | Region 4 parchment-tile dot-picking reference, same role as dots_1 — the verified input the dark_lands crop is re-derived from on every load (board #3570) | no |
| tww3_old_world_mod_parchment - dots_6.png | 3462x2567 | 9,593,438 | aaaa2e471dd1b0b1be7f72901cb76cc4bcb858e8a9f6eb3b24ff3f205126dc4a | Badlands+Nehekhara crop of `tww3_old_world_mod_parchment.png`, dot-marked by the user | Region 6 parchment-tile dot-picking reference, same role as dots_1 — the verified input the badlands_nehekhara crop is re-derived from on every load (board #3570) | no |
| tww3_old_world_mod_parchment - dots_7.png | 4096x4096 | 22,919,640 | 6f8146f1da40123b8afe70a0add39e812a9c99d4aa53436a92c7293be46455f5 | Derived from `tww3_old_world_mod_parchment.png`, dot-marked by the user | Region 7 parchment-tile dot-picking reference, same role as dots_1-6 | no |
| tww3_old_world_mod_parchment - dots_7.xcf | n/a | 90,381,037 | f097d61737e90779941a90eb6a30a2bcf78713b32d4fdbaca41d80a41c91d228 | Derived from `tww3_old_world_mod_parchment.png`, dot-marked by the user | Editable master of the dots_7.png export above | no |
| tww3_old_world_mod_parchment.png | 4096x4096 | 8,332,865 | 93f5c7b4791d7a02b60eeb4ba96bf5abc66ad4d650978d1990b022840de903a3 | Fan cartography — "The Old World, all faction starting positions v3.0" | **Denser Old World boundary network** — a line chloropleth, markedly denser than IE over the same arc. Higher precedence inside a masked footprint; the four corner vignettes + the Galleon's Graveyard spiral are excluded (they take cartographic liberties — user-flagged) | no |
| tww3_states_per_strat_region.jpg | 2048x1593 | 1,112,706 | b8965b704a476a5e93276f217c17dc6b6135301c87564c36ebb6d181252303ca | Fan annotation of the IE parchment master - strategic regions outlined, named, and labelled with their Total War: Warhammer 3 state counts | **NAMED MACRO REGIONS** - the source that binds region names to geometry, without which none of the user's per-region requirements can be checked. 17 named regions; supersedes pizqenw9rd791.jpg for grouping. Frame alias of the twin (exact 0.553 rescale, now pointing at `tww3_ie_parchment.jpg`). Printed counts are a reference, not truth. **Re-added** after the August 2026 retirement — same bytes (SHA-256 confirmed), so registration is restored rather than re-derived | yes |
| white_dwarf_world_map.png | 4524x3093 | 1,960,224 | c5a4c6708600fedbfe404c59a7c8d6ab5745eea6e4d35a28180ef13932b37be7 | Games Workshop — official Warhammer world map (boxed / White Dwarf fold-out poster; the sheet prints "© Games Workshop Ltd 2000–2004" and "Product code 60440199034"). Fold seams visible | **Projection: oval pseudocylindrical, flattened-pole (Winkel Tripel / Robinson / Natural Earth family — NOT pointed-pole Mollweide/Aitoff)** — identified 2026-08-15. The world's printed neat-line is a smooth arc bowing down to clipped corners, ~360° of longitude wrapping (HUNG at both far edges); the broad clipped top is a pole line, not a point. Same oval family the terraqueous NE-II globe reproduces. Manifest/naming/extent reference only; unregistered — a fit would try the `natural_earth_2` kind, falling back to a `control_point_warp` if its oval isn't exactly NE-II | no |
<!-- MANIFEST:END -->

## Local organisation: descriptive filenames; consumed sources stay flat

Every source `load_source_image` actually reads — anything with a manifest row
above — must sit directly in `sources/`: `tools/worldgen/sources.py` looks up
`sources/<basename>` and does **not** search subfolders recursively, so a
consumed file dropped in a subfolder is invisible to `--verify`,
`--update-manifest`, and `load_source_image`.

Grouping related sources is done with a filename prefix that names the family
the source belongs to (e.g. `tww3_*` for the Total War: Warhammer 3 / Immortal
Empires parchment family, `old_world_*` for Games Workshop's Old World tabletop
maps, `the_empire_*` for Empire-specific references, `terraqueous_globe*` for
the globe and its derivatives). Sorted alphabetically, same-prefix files land
next to each other in a flat listing without needing a folder. The manifest's
`File` column stays a bare filename either way; renaming a source here means
updating this manifest row plus every registration record / generator-script
constant that names it — see the August 2026 reorg note below for what that
touched.

`sources/dots/` is the one subfolder in use. It holds the visual record of the
paired-anchor-dot registration workflow (see the Immortal Empires/Old World
per-region carves below): the six pairs of marked images — for each region `N`
in {1..6}, `terraqueous_globe_reprojected - dots_N.png` (the canvas frame with
that region's dots marked) and its matching region crop
(`tww3_old_world_mod_parchment - dots_{1..4,6}.png` for the five parchment tiles;
`old_world_z10 - dots_5.png` for the northern relief crop) with the dots still
on — plus the marker-palette listing `127 0 191.txt`. The dots↔region pairing is:
1 = Empire (7 dots, the 2026-08-17 refit), 2 = Bretonnia+Estalia+Tilea (11),
3 = Kislev+Norsca (13), 4 = Dark Lands (14), 5 = start_warhammer northern relief
(42, of which 40 are landmarks), 6 = Badlands+Nehekhara (17, of which 16 are
landmarks). The `terraqueous_globe_reprojected - dots_N.png` canvas-frame half
and `old_world_z10 - dots_5.png` are still pure dot-picking references, never
loaded by any script, and correctly carry no manifest row.

**The five `tww3_old_world_mod_parchment - dots_{1..4,6}.png` sheets are
different: as of board #3570 they ARE pipeline inputs**, manifest-tracked and
SHA-256 verified like any other source. Each of the five per-region parchment
crops (`tww3_old_world_mod_parchment_{empire,bretonnia,kislev_norsca,dark_lands,
badlands_nehekhara}.png`) used to be cached as its own separately-checksummed
dot-free file, re-derived by hand into `sources/dots/` whenever its dots sheet
changed — which is exactly the double-bookkeeping that let a cached crop go
silently stale (see #2207's closing comment). Those five cached files are gone;
the crop is now recomputed in memory on every load, straight from its dots
sheet, via `sources.load_or_derive_image_rgba` (manifest-verified: used by
`generate_state_labels.py`) or the equivalent unverified dispatch in
`project_regions.py`/`render_anchor_dot_example.py` (matching their existing
preview-before-manifest-update convention). Each per-region registration seed
(`tools/registration/seeds/tww3_old_world_mod_parchment_<region>.json`) records
which `dots_N.png` sheet it derives from in a `dots_source` field. A future
subfolder is fine on the same no-cached-copy condition as any other consumed
source: whatever it holds must itself be manifest-tracked, not a derivable copy
of something else that already is.

The finished-workflow illustrations — the composite QA renders — still live at
`tools/derived/<region>_anchor_dot_warp_example.png` (plus
`tools/derived/old_world_anchor_dot_warp_combined.png`, the five-tile nine-zone
coverage proof), where they ARE git-tracked via explicit per-file allowlist
lines in `tools/.gitignore` (`tools/derived/` is not blanket-gitignored the way
`sources/` is). This resolves the 2026-08-17 flag about them having briefly moved
into the local-only `sources/dots/`: the committed home is `tools/derived/` only.
All six are regenerated — never hand-edited — by
`python tools/render_anchor_dot_example.py --all`, which warps each clean source
through its committed registration record. The clean sources those renders (and
the boundary pipeline) read are derived on demand from the `sources/dots/`
sheets above by `worldgen.derive_crop.derive_clean_source` — the same function
`tools/inpaint_dot_markers.py` now wraps as a thin CLI for one-off inspection.

## Renamed: `the-old-world-all-faction-starting-position-map-v3-0-updated-v0-ml2lq3qfofad1{, - Copy}.png`

Shortened to `the-old-world-all-faction-starting-position-map-v3.png` (clean) and
`the-old-world-all-faction-starting-position-map-v3_oceans_hatched.png` (the
hand-marked-sea copy) — same upload-site-filename problem as the globe below.
Bytes unchanged, confirmed by SHA-256, so both rows above are relabelled, not
new sources.

## Renamed: `terraqueous_globe_reprojected - rivers.{paint,png}` → `terraqueous_globe_reprojected - coasts.{paint,png}`

The pair was added under a guessed name ("presumed river-course working layer …
unconfirmed, flag if wrong") before its role was known. The user has since drawn
the world's coastline on it as a magenta trace and renamed it to say so; the
content also changed in the same pass (bytes differ from the old `rivers` rows —
it is still being edited locally), so this is a relabel-plus-edit, not a
byte-identical rename. `generate_coastline_mask.py`'s `DEFAULT_SOURCE` and
docstring were updated to the new name; it is now the coastline authority,
superseding the height-ramp coast extraction (user decision, 2026-08-14).

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
a **which-rivers-exist-and-how-they-join reference**, not a geometry source.

As of board #3703 the geometry of `map_data/rivers.png` comes from the user's
**canvas-native cyan trace** (`terraqueous_globe_reprojected - rivers.png`) driven
through `tools/generate_rivers.py`, not from the heightmap's drainage (the old
`worldgen/hydro.py` path is retired from the river generator). This annotated
Empire map never places pixels — it is freehand over a stylised illustration that
does not register tightly — so it stays a reference the user reads by eye to
decide *which* traced streams are the Reik, the Talabec, and so on (the
anchor-keyed names in `tools/config/canon_river_names.json`), covering the Empire
only.

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
change needed — it just did that then). *(Later, #3510 revived and renamed
that path to `relief_detail()`, repointed at the already-registered
`colored_globe.jpg`, so the relief layer is live again — it no longer returns
`(None, None)`.)* And
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
