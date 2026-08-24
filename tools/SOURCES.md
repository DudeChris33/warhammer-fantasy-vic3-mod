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
| Major_Trade_Routes_of_the_Old_World_Map.png | 1947x1404 | 690,310 | 12026b1e21ad7b9467ff1e3d597e98492739af19e2d8cf97407ddf5d28f7b919 | Games Workshop — "Major Trade Routes of the Old World" | Manifest only, unregistered — S6 reference | no |
| bretonnia_black_white_colored.png | 4210x4700 | 14,643,218 | 05d03cf362e17d8c805ead02915b66334be75f01d52346936f2ac611675a3610 | Internet find; the user colored the ocean blue | Primarily Bretonnia village placement; secondarily other Bretonnia features | no |
| colored_globe.jpg | 1680x1214 | 429,642 | 91e12fbb2938d2ec61ed78abd1d42ad10615a3d427068acd5830a9598bf214c0 | Fan cartography — David "Fahran" Mills "Warhammer World Map" (war-rvr.net, 2006), a whole-world relief/satellite render with a blue ocean. Added by the user 2026-08-13 | Whole-world COASTLINE silhouette (`blue_sea` kind: ocean is blue-dominant but brightness-varying). Balanced land/sea (0.366 vs mask 0.369) so it registers globally, unlike the land-heavy regional tiles. A DIFFERENT source from the terraqueous globe (different projection — a freehand rectangular/cylindrical relief render, ~1.38:1, closest to a latitude-cropped equirectangular but NOT an analytic projection, so it stays a `control_point_warp`, not an analytic inverse; identified 2026-08-15), registered against the mask for coastline agreement; mask stays the sole authority | yes |
| land_sea_mask.png | 8192x3616 | 260,887 | 0f8849ecf8f9074aa38e4ab3721038a09d0dd7450bf73f354533fc189efbaa05 | PNG export of `land_sea_mask.xcf` | The real land/sea mask in use | no |
| land_sea_mask.xcf | n/a | 1,156,982 | c998f0a092d8ae4e32941bc9dc58cff26c5ddafcd687edf5732b9bb10ee5ec46 | User — copy of the user's hand-drawn `terraqueous_globe_reprojected - coasts.xcf`, filled to form a land-sea mask. Switched from MS Paint (`land_sea_mask.paint`) to GIMP (`.xcf`), same editable-master role | Editable master of the land-sea mask below | no |
| mega_detailed_old_world.jpg | n/a | 385,900,884 | 99b89752c24766a968cd4023a6450aa75bb34a3b01ac6ee6bcda3a698b7c7906 | Internet find | Primarily Old World town and forest placement; secondarily other Old World features | no |
| named_globe.png | 4096x2048 | 15,109,233 | 0f89110c2a4cc471f53319a05aba439a4a1e69119d06278b5374b0214ff22eff | Fan cartography — a labelled whole-world Warhammer map, blue-ocean relief with region names (Naggaroth, Ulthuan, the Old World, Southlands, Grand Cathay, …). Exact author unconfirmed. Added by the user 2026-08-12 | **Projection: equirectangular (plate carrée)** — identified 2026-08-15. Exactly 2:1 at 4096×2048 (power-of-two globe-texture dims), filled corner-to-corner with ocean/ice (an oval projection would leave the corners empty), meridians vertical. **Registered 2026-08-15** (`tools/registration/named_globe.json`) as a `control_point_warp`. A pure analytic-equirectangular placement was tried first and rejected (the artist drew landmasses at different proportions than the mask), so the geographic box was MEASURED by silhouette IoU against `land_sea_mask.png`: named_globe covers only ~320° of longitude and is latitude-cropped at ~40°S (affine cx≈2048 sx≈12.79 cy≈1348 sy≈17.50, 0.638 affine IoU), so it has NO coverage of the canvas far-eastern seam or its southern band. That affine seeds an 11×7 lattice `register.refine` pulled onto the mask to **0.788 IoU** (no folds, anisotropy≤3). Contributes NO coastline (mask stays sole authority) — a whole-world coastline reference like `colored_globe`, at a third projection. MACHINE-FITTED; re-derive, do not hand-edit. PROVISIONAL until the user accepts the render | yes |
| ocean_currents.png | 8192x3616 | 959,633 | 57076d7be6a0f1aa1deaad25831cb24c6d99e7733b84310e18de70c43e174c9f | Generated (Claude) | Partially informs sea zone placement | no |
| old_world_regions.png | 4096x4096 | 5,375,145 | 3b944a5578286ae0dd1817857979b337903b250b9d56dd9f9424bdb406240709 | PNG export of `old_world_regions.xcf` | Maps which region each state belongs to | no |
| old_world_regions.xcf | n/a | 38,442,986 | b9197f6f169701e54af737d3089ea4088e004b6750bf83346a147bc69fce01d5 | User — hand color-filled. Switched from MS Paint (`old_world_regions.paint`) to GIMP (`.xcf`) | Maps which region each state belongs to | no |
| old_world_state_regions.png | 4096x4096 | 18,725,905 | f93bc0cc30327ee0de137f3477e8474b9ace99c306045f1806b837a52d5f6e86 | PNG export of `old_world_state_regions.xcf` | Map of the borders of all state regions in the Old World | no |
| old_world_state_regions.xcf | n/a | 38,154,867 | 120250671ce3fd3ba353da95a107128d8eb676e03f87e3a603362e2e5662f08d | Generated, with the user's hand-drawn corrections. Switched from MS Paint (`old_world_state_regions.paint`) to GIMP (`.xcf`) | Map of the borders of all state regions in the Old World | no |
| old_world_terrain.jpg | 3016x2080 | 1,140,330 | 80ae22f4aa384049cd42e70ade67db4f57853e6e91c9fbed30458dd9a69c1f91 | Games Workshop — Warhammer: The Old World world map | Old World / Badlands / Dark Lands / Araby / Land of the Dead boundaries. **NOT USABLE FOR GEOMETRY** (measured S3a) — misregistered off the coast, and not a chloropleth (see below) | yes |
| old_world_z10 - grayscale.png | 6658x9824 | 70,851,835 | c2b19d3cd0ce5c0551f9c628f17160ea9dc1cf03eec23320549758be1f43a095 | Grayscale copy of `old_world_z10.png` | Same role as `old_world_z10.png`, in grayscale | no |
| old_world_z10.png | 6658x9824 | 120,598,002 | 856dfa35a633a3e7dead1972a37660791fc2b8fcbb18a59f3a535b2d3109428a | Games Workshop — official "Warhammer: The Old World" interactive map (start-warhammer.com), zoom-10 base tile layer, stitched by us (TMS tiles, transparent border cropped) | Highest-resolution whole-continent Old World reference in the folder. Base tile ART ONLY — the site's interactive city/army/region markers are separate overlays and are NOT baked in. Naming + extent + coastline/relief cross-reference (S6). Unregistered | no |
| satellite_globe.jpg | 637x358 | 43,099 | 8b90bae2e491a366a8c5deb3f1e8d9307dac6b8658d0fd7d62bb9c6de242d95b | Fan whole-world satellite/biome render (Steam Workshop) | **Projection: equirectangular** (rectangular whole-world texture, pillarboxed to 16:9 — black bars at x=[0..86] and x>548, content x=[87..548]; the map itself is corner-to-corner with vertical meridians). DE-REGISTERED in S2 — de-registered for cloud cover + the narrow 462-px usable width, not for its projection (see below) | no |
| start_warhammer_old_world_northern.png | 6134x4958 | 29,623,768 | 2eb0f55756aba70b3648675358a89e13db55ee378cbea52b049eff1c5251b999 | Northern Old World crop of `old_world_z10.png` (via its grayscale variant), cut and dot-marked by the user for the paired-anchor-dot workflow (2026-08-16) | PLACEMENT ONLY (grayscale relief, no drawn boundary network); see `tools/registration/start_warhammer_old_world_northern.json` (objective=landmarks, 40 of the crop's 42 dots; legacy full-frame fit — predates `fit_registration.py`'s hull-bounded lattice, noted for any future re-derive). Downstream consumption undecided; stays out of the combined coverage render (relief, overlaps the parchment tiles). Clean source re-derived from the surviving dot crop by `tools/inpaint_dot_markers.py` (2026-08-20; the 2 unused dots are inpainted too) — not re-rendered, placement unchanged | yes |
| terraqueous_globe.jpg | 4000x3256 | 2,292,545 | c4021e28d8d58bc3f91733df72ee9b7b398f922bb565b0478d3743446d8c15f3 | Fan cartography — "Terraqueous Globe", Kartografia Niepraktyczna 2022 | Whole-world heightmap (NE-II colour-to-height ramp) + coastline. **The single geometric authority** (S3a decision #1) — every other source projects onto it | yes |
| terraqueous_globe_reprojected - coasts.png | 8192x3616 | 33,504,121 | 0a6406692c732749ba29399bbd962c67fba5a040ada588b6d03b875cfc823569 | Derived from `terraqueous_globe_reprojected.png` (user, August 2026) | The hand-traced coastline (magenta line on the Miller-reprojected canvas, 8192x3616) that `generate_coastline_mask.py` consumes as the coastline authority (user decision, 2026-08-14: "the traced coastline wins") — supersedes the height-ramp coast extraction. Renamed from `terraqueous_globe_reprojected - rivers.{paint,png}` (was misidentified as a river-course layer, "unconfirmed, flag if wrong") once its actual role was confirmed | no |
| terraqueous_globe_reprojected - coasts.xcf | n/a | 88,664,765 | 24c405933f345f8e442a3ca8aab4b61d2954c8fadd5d8af851e0645c1955b9f0 | Derived from `terraqueous_globe_reprojected.png` (user, August 2026; still being edited locally). Switched from MS Paint (`... coasts.paint`) to GIMP (`.xcf`) | Editable master of the .png below | no |
| terraqueous_globe_reprojected - coasts_only.xcf | n/a | 1,270,409 | 7fd2915f350e266f1df608db197f7777b39e70291938450def83397f68a400bc | User. Switched from MS Paint (`... coasts_only.paint`) to GIMP (`.xcf`) | Working file for the user — cuts the land out of `terraqueous_globe_reprojected - coasts.xcf` | no |
| terraqueous_globe_reprojected - sea_zones.png | 8192x3616 | 33,751,776 | 99a3f8cbaf8b1ae51d7bbbbd56312a1d191eb3fe6fe3afc52239284819befede | Derived from `terraqueous_globe_reprojected.png` (user, August 2026) | The hand-drawn sea-zone network (canvas-space, 8192x3616): **magenta (255,0,255) = coastline, purple (127,0,255) = the sea-zone boundaries** dividing the water into naval zones. `generate_sea_zones.py` consumes the purple lines as barriers and flood-fills the water between them into zones (board #2593). Drawn using the earlier auto-partition renders as reference, then completed by hand. No registration (already in canvas space) | no |
| terraqueous_globe_reprojected - sea_zones.xcf | n/a | 89,325,186 | 3d4799e11a3374d96ff3f4c7e49da48c13d0e1461d171606f9135cc84bb4b117 | Derived from `terraqueous_globe_reprojected.png` (user, August 2026; still being edited locally). Switched from MS Paint (`... sea_zones.paint`) to GIMP (`.xcf`) | Editable master of the .png below | no |
| terraqueous_globe_reprojected - state_regions.png | 8192x3616 | 33,812,189 | c6e309322fbd15f03203b4cd0304d5676fc82bb3b2569fcace900c488ddcef3d | Derived from `terraqueous_globe_reprojected.png` (user, August 2026) | The hand-drawn state-region network (canvas-space, 8192x3616): **magenta (255,0,255) = state-region boundaries + coastline, purple (127,0,255) = the sea-zone boundaries** (the same purple layer as the sea-zones source, not consumed here). `generate_provinces.py` (board #2773) consumes the magenta lines as state-region barriers, flood-fills the land between them into regions, and subdivides each drawn region into provinces. No registration (already in canvas space, like the sea-zones source) | no |
| terraqueous_globe_reprojected.png | 8192x3616 | 30,471,432 | 604fc9f92848fc25590f0a7d69b54a46dea79bd1acbc578f250304d36b06888c | Derived from `terraqueous_globe.jpg` (user, August 2026) | `terraqueous_globe.jpg` reprojected from its native Natural Earth II to Miller cylindrical — the mod canvas's own projection (see `config/canvas_frame.py`). Canvas-sized (8192x3616 = WIDTH x HEIGHT). Not yet consumed by any script; `generate_heightmap.py` currently reprojects `terraqueous_globe.jpg` itself via its NE-II fit rather than reading a pre-reprojected copy | no |
| the_empire_1.jpg | 5426x5091 | 22,888,291 | d12726947a3afaee43bbc174dbe95cba1288e7bf4dbf542e0a6a86065642bb29 | Internet find | Very detailed map of the Empire — villages, terrain, rivers, names, etc. | no |
| the_empire_2.jpg | 1920x1301 | 1,466,126 | 8c3f93454483dc261f933ad3d43530495cb11111071de2511669ac50f5ad2528 | Games Workshop / Warhammer Community — "The Empire of Man" map | Clean counterpart of the annotated map — differencing the two isolates the annotation | no |
| the_empire_2_rivers_drawn.jpg | 1920x1301 | 1,463,260 | e4d4d67afb4705d7e7c139ecd5a0cd0233adff80100939328451b6ecce384ff4 | The above, with canon river courses drawn on in red by the user | Canon-river TOPOLOGY guide for the S6 naming pass — which DEM channel is which. Contributes no geometry (see below) | no |
| tww3_climate.jpg | 2471x1922 | 2,022,554 | fae9e090f0b2ffba1f82008dec5c2c36cf6a03dd0eaca0808b8822ba7b413edb | Total War: Warhammer 3 | Shows the (super-abstracted) climate used in the Total War game | no |
| tww3_colored.png | 4726x3010 | 1,467,069 | d3962b9e28a49765c6c6f236b89b67924d06019835bcc857a51b41e5602b3817 | Fan cartography - flat-filled Total War: Warhammer world map with region boundaries | Demoted from primary to **complement** boundary source (world-map-parchment-areas-onto-globe.md, 2026-07-28): boundary precedence 95, below the parchment master's 100, so it now wins only outside the master's coverage. Flat blue ocean still gives an EXACT land/sea silhouette (no threshold is fitted), and black region lines over flat terrain fills yield 681 clean closed cells across the whole Known World, against our 659 land-state target — the 748-vs-681 clean-cell discrepancy flagged in the S3a-2 review remains explicitly unresolved. See below | yes |
| tww3_ie_parchment.jpg | 3703x2880 | 3,225,567 | f6e4f53ea80673bb9b792f11b1ac1de387bb8e07757f8a384aa40fd8aea757c1 | Creative Assembly - Total War: Warhammer 3 Immortal Empires parchment campaign map (English) | **PRIMARY BOUNDARY + NAME SOURCE (world-map-parchment-areas-onto-globe.md, 2026-07-28)** - registered by `tools/fit_registration.py --seed wh3_dlc_ie_parchment_map_english` (silhouette objective via the climate map sibling, 10x8 lattice, 12 held-out landmarks). Fit: `refined_iou` 0.6193, `folded_fraction` 0%, `anisotropy_p99` 3.00, `landmark_check_px` mean 426.9 / max 872.1 - reported against the family's only other comparable record (`total_war_map_colored.json`: mean 312.2 / max 844.6, refined_iou 0.6617) as somewhat weaker but consistent (0% folding, same anisotropy), explained by the parchment's silhouette coming via a rescaled sibling rather than an exact flat-fill silhouette. The family's `ie_macro_twin.json` control points (baked standalone when the master was previously absent from `sources/`) reproduce EXACTLY (0.0 px mean/max) against this fit, confirming full reproducibility with the existing placement. Its interior line network is traced with lettering bridged (not erased) into the barrier, and its printed names are the S3a-2 review panel's missing name-to-geometry binding. Also the differencing counterpart for macro grouping (unchanged role). | yes |
| tww3_old_world_mod_grayscale.png | 4096x4096 | 16,207,148 | a02fed5a10833e32988fe2b83f894e529fa1894370e13929c9a1533989c762e4 | Grayscale copy of `tww3_old_world_mod_parchment.png` | Same role as `tww3_old_world_mod_parchment.png`, in grayscale | no |
| tww3_old_world_mod_parchment.png | 4096x4096 | 8,332,865 | 93f5c7b4791d7a02b60eeb4ba96bf5abc66ad4d650978d1990b022840de903a3 | Fan cartography — "The Old World, all faction starting positions v3.0" | **Denser Old World boundary network** — a line chloropleth, markedly denser than IE over the same arc. Higher precedence inside a masked footprint; the four corner vignettes + the Galleon's Graveyard spiral are excluded (they take cartographic liberties — user-flagged) | no |
| tww3_old_world_mod_parchment_badlands_nehekhara.png | 3462x2567 | 6,527,951 | 907378daee8bc1e7fcd34a8625f41721b8139a00cd081b6bea3a45793b94e5f9 | Dot-free, alpha-masked crop of `tww3_old_world_mod_parchment.png` spanning the southern Old World arc (Badlands, Border Princes, the Dead Sea coast toward Nehekhara), cut by the user for the paired-anchor-dot workflow (2026-08-15) — the worked-template tile for the workflow | **BOUNDARY SOURCE** (Old World, `ink_bridged`): registered by `tools/fit_registration.py --seed tww3_old_world_mod_parchment_badlands_nehekhara` (objective=landmarks, 16 of 17 user-drawn paired anchor dots read direct off `terraqueous_globe_reprojected.png` — interior south-central 'yellow' held out per the user's 2026-08-17 A/B compare; 6x6 lattice, hull-bounded). Consumed by `generate_state_labels.py` to cut Old World state cells inside its **alpha>0 footprint** — but NOT yet wired into `BOUNDARY_SOURCES` (that, with empire, is board item #2207). Its committed record carries the provisional boundaries precedence **5 (inert — below IE's 100)**; promotion is #2207's. Contributes NO coastline (mask stays sole authority). Clean source re-derived 2026-08-20 from `sources/dots/tww3_old_world_mod_parchment - dots_6.png` by `tools/inpaint_dot_markers.py` (the held-out yellow is inpainted with the rest; diff vs the accepted local file confined to the marker disks) | yes |
| tww3_old_world_mod_parchment_bretonnia.png | 1598x1789 | 2,702,971 | a0e9e7dad10318cf6fc9bbfbef1ca838c432c4083a5a76afcf3e8a26187c8808 | Dot-free, alpha-masked crop of `tww3_old_world_mod_parchment.png`, cut by the user for the paired-anchor-dot workflow (2026-08-14) — actually spans the whole south-west block (Bretonnia + Estalia + Tilea), named "bretonnia" per the user's request | **BOUNDARY SOURCE** (Old World, `ink_bridged`): registered by `tools/fit_registration.py --seed tww3_old_world_mod_parchment_bretonnia` (objective=landmarks, 11 user-drawn paired anchor dots read direct off `terraqueous_globe_reprojected.png`, 6x6 lattice) and consumed by `generate_state_labels.py` to cut Old World state cells inside its **alpha>0 footprint** (the crop's binary alpha mask is its contributing region; transparent = excluded). Its committed record carries the provisional boundaries precedence **5 (inert — below IE's 100)**, NOT the 111 an earlier version of this row claimed; promoting it to a live value is board item #2207's job (a re-derive, and because this is a legacy full-frame fit it would shrink the footprint to the dot hull+pad, so #2207 needs edge dots from the user first). Contributes NO coastline (mask stays sole authority). Restored 2026-08-20 — clean source re-derived from the surviving dot crop `sources/dots/tww3_old_world_mod_parchment - dots_2.png` by `tools/inpaint_dot_markers.py`; the bytes differ from the ad-hoc inpaint that generated the current committed label layer (superseded by #2207's regeneration) | yes |
| tww3_old_world_mod_parchment_dark_lands.png | 1965x2779 | 5,379,669 | 3ae17c66eb93f9eb5e587e0bb8bc1b5e1cd0221922e4369f018b49dc7bc4d959 | Dot-free, alpha-masked crop of `tww3_old_world_mod_parchment.png` (everything outside the Dark Lands alpha-erased away), cut by the user for the paired-anchor-dot workflow (2026-08-15) | **BOUNDARY SOURCE** (Old World, `ink_bridged`): registered by `tools/fit_registration.py --seed tww3_old_world_mod_parchment_dark_lands` (objective=landmarks, 14 user-drawn paired anchor dots read direct off `terraqueous_globe_reprojected.png`, 6x6 lattice) and consumed by `generate_state_labels.py` to cut Old World state cells inside its **alpha>0 footprint**, at boundaries precedence **113 (live — above IE's 100 and `tww3_colored`'s 95, so its lines win inside that footprint)**. The one crop of the five whose record carries a live boundary precedence; the other four are inert 5 pending #2207's promotion. Contributes NO coastline (mask stays sole authority). Restored 2026-08-20 — clean source re-derived from the surviving dot crop `sources/dots/tww3_old_world_mod_parchment - dots_4.png` by `tools/inpaint_dot_markers.py`; the bytes differ from the ad-hoc inpaint that generated the current committed label layer (superseded by #2207's regeneration) | yes |
| tww3_old_world_mod_parchment_empire.png | 1456x1469 | 1,994,747 | 20f7107c8bf1aee5e7123d6de0b43e896fb1e287066310d044aebbfb8d1f6dce | Dot-free, alpha-masked Empire crop of `tww3_old_world_mod_parchment.png`, cut by the user for the paired-anchor-dot workflow. **REFIT 2026-08-17**: the current local file is the accepted 7-dot refit (1456×1469, master_shape [1469,1456], revision of `sources/dots/tww3_old_world_mod_parchment - dots_1.png`), which supersedes the retired 1149×1167 9-dot crop this row's pre-sweep Dims/SHA still described — the sweep re-pins them to the refit | **BOUNDARY SOURCE** (Old World, `ink_bridged`): registered by `tools/fit_registration.py --seed tww3_old_world_mod_parchment_empire` (objective=landmarks, 7 user-drawn paired anchor dots read direct off `terraqueous_globe_reprojected.png`, 6x6 lattice, hull-bounded). Consumed by `generate_state_labels.py` to cut Old World state cells inside its **alpha>0 footprint** — but NOT yet wired into `BOUNDARY_SOURCES` (that, with badlands, is board item #2207). Its committed record carries the provisional boundaries precedence **5 (inert — below IE's 100)**, NOT the 110 an earlier version of this row claimed; promotion is #2207's. Contributes NO coastline (mask stays sole authority). Clean source re-derived 2026-08-20 from dots_1 by `tools/inpaint_dot_markers.py` (diff vs the accepted local file confined to the marker disks) | yes |
| tww3_old_world_mod_parchment_kislev_norsca.png | 2939x1436 | 3,367,534 | 44edbee0669c5f8c8361b2e3ee64d672de0561a932954f1dc5acf0238f945422 | Dot-free, alpha-masked crop of `tww3_old_world_mod_parchment.png` (everything outside Kislev + Norsca alpha-erased away), cut by the user for the paired-anchor-dot workflow (2026-08-15) | **BOUNDARY SOURCE** (Old World, `ink_bridged`): registered by `tools/fit_registration.py --seed tww3_old_world_mod_parchment_kislev_norsca` (objective=landmarks, 13 user-drawn paired anchor dots read direct off `terraqueous_globe_reprojected.png`, 6x6 lattice) and consumed by `generate_state_labels.py` to cut Old World state cells inside its **alpha>0 footprint**. Its committed record carries the provisional boundaries precedence **5 (inert — below IE's 100)**, NOT the 112 an earlier version of this row claimed; promoting it is board item #2207's job (a re-derive, and because this is a legacy full-frame fit it would shrink the footprint to the dot hull+pad, so #2207 needs edge dots from the user first). Contributes NO coastline (mask stays sole authority). Restored 2026-08-20 — clean source re-derived from the surviving dot crop `sources/dots/tww3_old_world_mod_parchment - dots_3.png` by `tools/inpaint_dot_markers.py`; the bytes differ from the ad-hoc inpaint that generated the current committed label layer (superseded by #2207's regeneration) | yes |
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

`sources/dots/` is the one subfolder in use, and it works precisely because
nothing in it is consumed: it holds the visual record of the paired-anchor-dot
registration workflow (see the Immortal Empires/Old World per-region carves
below). Its dot-picking references are the six pairs of marked images — for each
region `N` in {1..6}, `terraqueous_globe_reprojected - dots_N.png` (the canvas
frame with that region's dots marked) and its matching region crop
(`tww3_old_world_mod_parchment - dots_{1..4,6}.png` for the five parchment tiles;
`old_world_z10 - dots_5.png` for the northern relief crop) with the dots still
on — plus the marker-palette listing `127 0 191.txt`. The dots↔region pairing is:
1 = Empire (7 dots, the 2026-08-17 refit), 2 = Bretonnia+Estalia+Tilea (11),
3 = Kislev+Norsca (13), 4 = Dark Lands (14), 5 = start_warhammer northern relief
(42, of which 40 are landmarks), 6 = Badlands+Nehekhara (17, of which 16 are
landmarks). None of these is ever passed to `load_source_image` — they are
dot-picking references, not pipeline inputs — so they get no manifest row and no
SHA-256 tracking; `--verify` and `--update-manifest` correctly ignore the whole
subfolder. A future subfolder is fine on the same condition: nothing in it may be
a name any script loads.

The finished-workflow illustrations — the composite QA renders — now live at
`tools/derived/<region>_anchor_dot_warp_example.png` (plus
`tools/derived/old_world_anchor_dot_warp_combined.png`, the five-tile nine-zone
coverage proof), where they ARE git-tracked via explicit per-file allowlist
lines in `tools/.gitignore` (`tools/derived/` is not blanket-gitignored the way
`sources/` is). This resolves the 2026-08-17 flag about them having briefly moved
into the local-only `sources/dots/`: the committed home is `tools/derived/`, and
all six are regenerated — never hand-edited — by
`python tools/render_anchor_dot_example.py --all`, which warps each clean source
through its committed registration record. The clean sources those renders (and
the boundary pipeline) read are re-derived from the `sources/dots/` crops above
by `python tools/inpaint_dot_markers.py`.

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
