# Source manifest

The source-driven map pipeline reads reference imagery from a local `sources/`
folder at the repo root. It mixes Games Workshop cartography, a Total War
screenshot mosaic, and fan maps, plus tens of MB of binaries
(decision #2 in
[world-map-source-driven.md](../planning/requests/world-map-source-driven.md)).
**As of board #4608 (2026-09-17), `sources/` is gitignored and local-only** —
this manifest is its sole provenance record. (A 2026-09-03 decision briefly
committed it in full via Git LFS to sync between two devices; that reason
stopped applying once work went single-device on 2026-09-15, and #4608 purged
`sources/` back out of git history entirely.) A fresh clone gets zero files
under `sources/` — they are copied onto a new machine by hand.

This file remains the committed **manifest** that documents those files: every
source's filename, dimensions, byte size, SHA-256, origin, pipeline role, and
whether it carries a [registration record](registration/). It makes the exact
inputs behind every committed bitmap auditable without committing any art, and it is the hash `mapgen/worldgen/sources.py` checks a
source against before the ingestion stage is allowed to read it — so a swapped
or edited `sources/` file can never silently change a committed,
multiplayer-synced bitmap.

## The Terraqueous Globe is the most trusted source, and the shape we aim for

**`terraqueous_globe.jpg` outranks every other source in this manifest.** It is
the single geometric authority (user decision #1, 2026-07-25): its coastline is
the shape the finished map is meant to have, and every other reference is
*projected onto it* rather than averaged with it. Where a source disagrees with
the globe about where land is, the globe is right by definition and the other
source is misregistered.

Concretely, and non-negotiably:

- The committed `mapgen/derived/land_sea_mask.png` is derived from it and **is the
  coastline**. Nothing else may move a shoreline — not the Total War relief, not
  the Immortal Empires parchment family, not a future source.
- Other sources contribute only things the globe cannot supply: **interior
  boundaries**, **macro grouping**, **names**, and **high-frequency relief
  detail** composited as zero-mean texture on land. All of it is clipped to the
  mask.
- A new source's registration is *scored against the mask*, so "does it agree
  with the globe" is the measurement that decides whether it may be used at all
  (see `mapgen/fit_registration.py`). This is how the satellite render came to be
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

Files live directly under `sources/`, or in one of six searched subfolders:
`originals/` (raw reference imagery), `oldworld-first/` (the current
canvas-scale GIMP masters and their exports — see the .ora convention below),
`dots-triangles/` and `dots-mega/` (the paired-anchor-dot registration
workflow's active crops), `ulthuan/` (Ulthuan's paired-anchor-dot sheets —
see below) and `geology/` (physical-geography drawings; today the ocean-current
drawing the climate stage reads, board #8202). `archive/` (retired sources — including the five
per-region dot-marking sheets retired by board #5403), `WIP/` (local scratch),
`dots-claude/` (an earlier whole-parchment dot experiment; it holds the clean
PNG of the expanded parchment, `cr_combi_expanded_map.png`),
`history/` (finished reference artefacts kept for the record — see below) and
`cr_oldworld_campaign/` (its own dataset loader) and `cr_immortal_empires_expanded/` (see below) are deliberately **not**
searched. `mapgen/worldgen/sources.py`'s `resolve_source_path()` searches the
root plus those six by bare filename, so the **File** column below stays a
bare filename regardless of which subfolder a source actually sits in — the
manifest audits identity (dims/bytes/SHA/origin/role), not physical location.
`--update-manifest` discovers files the same way and refuses if a name
collides across more than one searched location.

**Board #5399 (2026-09-23): each multi-layer GIMP `.xcf` master gets a sibling
OpenRaster `.ora` export saved next to it**, and individual concerns (the
coastline trace, rivers, sea zones, state borders, impassable terrain) are
pulled out of it by **layer name** (`stack.xml`, not a colour registry —
Chris renames layers, so this manifest and `mapgen/config/source_layers.json`
are the sources of truth, not a hardcoded palette). A tool reads a layer via a
`<file>.ora#<layer>` reference; `mapgen/config/source_layers.json` is the one
committed table mapping each hand-painted input to its reference, so a rename
is a one-line edit there rather than a code change. Two kinds of source stay
flat PNGs instead: the paired-anchor-dot sheets (their layers only make sense
together) and single-layer masks — the land/sea fill `land_sea_mask.png`
(binarized first via `binarize_cyan_mask.py`; the `.ora` `coasts` layer is only
the cyan trace, with no land fill of its own) and the tiny-islands merger
circles.

## `cr_oldworld_campaign/`: ChaosRobie's Old World dataset (pruned 2026-10-06)

`sources/cr_oldworld_campaign/` is the extracted pack of ChaosRobie's Old World
Total War: Warhammer 3 campaign-map mod. It is not searched and has no manifest
rows; the name and overlay scripts read it directly (`tww3_name_lookup.py`,
`render_cr_lookup_overlay.py`, `render_tww3_text_crops.py`). Provenance and
ranking: [PROVENANCE.md](PROVENANCE.md#chaosrobies-mods).

Pruned on 2026-10-06 (2.8 GB to about 570 MB). Deleted: `terrain/` (3D models and
battle terrain), `rigidmodels/`, `prefabs/`, `weather/`, `materials/`,
`composite_scene/`, `movies/`, `warscape_asset_variation_db/`, `ui/skins/`,
`campaign_maps/.../display/`, the `.dds`/`.tga` duplicates of the lookup and
overlay bitmaps, `spd_data.esf`, `hlp_data.esf`, `pathfinding.ppd`, the RPFM
reserved files, and the engine-only `db/` tables (audio, battle, CAI, units,
videos, character art, trees, settlement display and similar). What remains:

- `cr_oldworld_lookup/`: `cr_oldworld_lookup.bmp` (the region partition) and
  `cr_oldworld_campaign.tsv` (colour to region key).
- `text/db/`: region, province, settlement, faction and culture names, plus
  dilemma and mission text.
- `db/`: the region, province, region-group, settlement, faction, culture,
  building and caravan tables (design reference).
- `campaign_maps/cr_oldworld_map_1/`: the map and text PNGs, camera heightmap,
  minimaps, `map_data.esf`, `trade_routes.ptd`. `startpos.esf` is under
  `campaigns/`. The ESF files are unparsed.
- `ui/flags/`: his faction flags (mostly Partypus's art; see
  `oldworld_campaign_credits.txt`).
- `script/` and `script_data/`: Lua and mission JSON, design reference only.
- `sea/`: sea and flow masks, kept pending review.

## `cr_immortal_empires_expanded/`: ChaosRobie's whole-world dataset (2026-10-05)

`sources/cr_immortal_empires_expanded/` is the extracted pack of ChaosRobie's
whole-world Total War: Warhammer 3 campaign-map mod, the sibling of
`cr_oldworld_campaign/`. Like it, the folder is not searched and has no manifest
rows: no tool reads the folder itself, and a file gets a row only when a loader
is pointed at it. Its parchment is in use through a dot-marked copy: see
`ulthuan/` below. See [PROVENANCE.md](PROVENANCE.md#chaosrobies-mods).

**Trust ranking (Chris, 2026-10-05): this dataset ranks equal to the Old World
mod.** Both are ChaosRobie's work and carry the same standing: higher precedence
than the stock Immortal Empires parchment for interior boundaries and names
inside their footprint, and the same name-citation convention. Neither ever
outranks the Terraqueous Globe, which alone sets the coastline (see the top of
this file).

Pruned to the useful part on 2026-10-05 (3.0 GB to about 305 MB; the 3D assets,
Lua, battle terrain, pathing and UI skins were deleted). What remains and why:

- `campaign_maps/cr_combi_expanded_map_1/cr_combi_expanded_map.dds` (6400x4480,
  unlabelled) and `..._map_text.dds` (same frame, labels only): the Immortal
  Empires parchment extended past the vanilla frame. Candidate boundary source.
  Registered for Ulthuan only (2026-10-11, `ulthuan/` below); the rest of the
  frame is unregistered. **The text DDS is read, alpha only, by
  `propose_cr_borders.py --placement-review` (#8211, 2026-10-14)** to overlay CR's
  province labels on the landmark sheet; no manifest row, nothing is written from it.
- `cr_combi_expanded_lookup.tga` (3200x1941): the world region partition, 768
  flat colours with 16-bit palette indices (PIL cannot open it). Only
  ChaosRobie's own `cr_combi_region_*` colours decode from this folder; vanilla
  region colours live in the installed WH3 `data.pack`. **Read directly by
  `mapgen/propose_cr_borders.py` (#8210, 2026-10-14), with its SHA-256 in each
  report and no manifest row** (the `cr_oldworld_campaign/` precedent). Decode
  facts: an 18-byte header (colour-mapped, 16-bit indices, a 32-bit BGRA palette
  of 768 entries whose "first entry" header field reads 18, which is the byte
  offset and not an index shift: pixel values index the palette directly), then
  the indices, no trailing bytes. The descriptor byte is `0x10` yet the rows are
  stored **top-down** and are kept as stored (read bottom-up, Ulthuan lands south
  of Naggaroth). Void is the one `000000` entry (index 27); index 12 (`eb06df`)
  is a real region. The lookup spans the whole 6400x4480 parchment frame at a
  per-axis scale of (2.0, 4480/1941) with zero offset: its interior region edges
  over Ulthuan sit a median 1 parchment px from Chris's accepted magenta lines.
  194 of the 768 colours are keyed in `db/regions_tables/!cr_map_expansion.tsv`
  (`unnamed colour group_1`, upper-case hex) with display names
  `regions_onscreen_<key>` in `text/db/cr_new_combi_regions.loc.tsv`; the other
  574 stay `cr_idx_<n>` until the WH3 `data.pack` is read.
  **Placement is automatic, with no dots from Chris** (2026-10-14): a silhouette
  fit per landmass, scored against his accepted Ulthuan dots, with any Claude
  landmarks kept in `mapgen/config/cr_border_landmasses.json` (`placed_by`,
  `feature`) and never in `mapgen/registration/`. Everything it writes is a
  proposal under `scratchpad/`, never a source.
- `terrain/campaigns/cr_combi_expanded_map_1/`: `full_height_map.dds` (12800x7764,
  HDR, needs a real BC6H decoder), `tile_mask`, `snow_mask`, `colour_overlay`.
- `text/db/cr_new_combi_*.loc.tsv` and `db/`: names and the region/province
  structure for the lands outside the Old World. Cite names as ChaosRobie's, not
  `canon:`.
- `campaigns/cr_combi_expanded/startpos.esf`, `map_data.esf`: unparsed (no ESF
  reader in the repo); settlement positions and starting ownership.
- `ui/flags/`: his faction flags, a starting point for heraldry.

## `ulthuan/`: Ulthuan's paired-anchor-dot sheets (2026-10-11)

Ulthuan joined the mod's scope on 2026-10-11 (Chris). `sources/ulthuan/` is a
searched subfolder holding the two sheets that place ChaosRobie's expanded
parchment onto the canvas over Ulthuan, each with its GIMP `.xcf` master:

- `ulthuan_parchment.png` (6400x4480): the whole `cr_combi_expanded_map` frame.
- `ulthuan_terraqueous.png` (4096x1808): the top-left of
  `terraqueous_globe_reprojected.png` at zero offset, so its pixels are canvas
  pixels.

Both carry the same 34 dots (12 px, flat colours that repeat) and a cyan
`(0,255,255)` coastline trace. The trace is markup, not a dot and not a
coastline source: the mask stays the only coastline. The parchment sheet also
carries Chris's magenta `(255,0,255)` state-border network for Ulthuan (added
2026-10-11). When magenta became the border colour he recoloured the four
magenta dots on the parchment sheet to lavender `(174,102,213)`; on the canvas
sheet they are still magenta, and their positions did not move.

The seed is `mapgen/registration/seeds/cr_combi_expanded_map_ulthuan.json`
(`objective: piecewise_affine`) and the record
`mapgen/registration/cr_combi_expanded_map_ulthuan.json`. After Chris adds
dots and re-exports the two PNGs:

```
python mapgen/worldgen/sources.py --update-manifest
python mapgen/reseed_registration_dots.py --seed cr_combi_expanded_map_ulthuan --fit
python mapgen/render_anchor_dot_example.py --seed cr_combi_expanded_map_ulthuan
python mapgen/render_anchor_dot_example.py --seed cr_combi_expanded_map_ulthuan --borders-only
```

The last one draws only the magenta borders, carried onto the canvas, over the
reprojected globe (`scratchpad/cr_combi_expanded_map_ulthuan_borders_only.png`)
and also writes them alone on a transparent full-canvas PNG
(`..._borders_canvas.png`, 8192x3616), which can be laid over the canvas master
as a tracing guide. Both are gitignored review output: the state borders
themselves stay Chris's to draw on the `borders` layer.

Carried straight through the warp, the borders sit where the parchment has
them, and the parchment draws the island thicker than the canvas does and
splits it unevenly, so some lines hug or overrun the coast.
`python mapgen/adjust_ring_borders.py` redraws the same network for the
canvas's own land (its docstring has the rules):

- A border along the ring splits the land evenly between the inner-sea shore
  and the outer coast: at 1/2 where it is the only one, at 1/3 and 2/3 where two
  run side by side (the north and the west).
- A border across the ring keeps its drawn shape and slant between its ends.
- Every coast end lands on the canvas coast and runs a few pixels into the water.

It writes `scratchpad/ulthuan_borders_adjusted_canvas.png` (the lines alone,
pure magenta, 1 px, transparent full canvas) and two review renders, all
gitignored. Chris accepted that output on 2026-10-12 as the proposal for
Ulthuan's state borders: 28 states, the same count as his parchment drawing,
the smallest about 1,600 canvas px. It becomes real only when he lays it into
the canvas master's `borders` layer; the script never writes a source.

The reseed only adds dots. A dot that was moved or deleted leaves its old
landmark in the seed: delete that landmark by hand first (or empty `landmarks`
to rebuild all of them from the sheets).

Three things differ from the Old World `dots_7` sheets, all declared in the
seed's `dots_reseed` block:

- The file names do not follow `<master> - dots_N.png`, so all four are named.
  `master_original` is `dots-claude/cr_combi_expanded_map.png`, the clean
  parchment the dots are found against.
- The canvas sheet is a crop of the canvas (`canvas_offset`, here `[0, 0]`).
- The dots share colours, so colour alone cannot pair them. They are paired by
  position: of every way to match same-coloured dots, the one closest to a
  single affine map wins (`reseed_dots.resolve_repeated_colours`). On
  2026-10-11 the best of 138,240 assignments for the first 18 dots had 9.2 px
  RMS against 38.8 px for the runner-up; the 8 added later, 21.5 px against
  59.0 px. The cyan trace and the magenta borders are skipped through
  `ignore_colours`, and `chroma_floor` is 100 so the lavender dots are seen.

The seed's top-level `keep_colours` lists the magenta borders: the clean
parchment derived from the sheet (`worldgen.derive_crop`) inpaints the dots and
the cyan trace but keeps that colour, so the borders ride through the warp
onto the canvas in the render.

State of the fit (fourth pass, **accepted by Chris on 2026-10-12**): 61
triangles over 34 dots, exact at every dot. Four orange
`(255,127,0)` dots at the corners of a box around the island make the coverage
a rectangle, canvas x 2511..3128, y 899..1612, holding the whole parchment
trace (18 dots held 3,544 of its pixels; 26 held 6,981). The fourth pass added
dots on the inner sea's west and east shores and on the north-west coast. The
warped parchment coast lands a mean 6.1 px (p90 12.5, max 53.9) from the
canvas trace. What is left is the parchment drawing the land wider than the
canvas does along the east coast and the inner sea's south-west shore.
Nothing downstream reads the record yet.

## `history/`: finished reference artefacts (2026-10-05)

`sources/history/` holds finished one-off artefacts kept for the record. It is
not a searched subfolder, so nothing in it has a manifest row and no tool reads
it; this section is its only record.

**`real-world-comparisons-r.png`** (1427x628, 45,076 bytes, SHA-256
`ddac6a07c44f0c8727b513d6b85455c22982b0c31d82965c86b4bc9f182aab71`). A blank
political map of Earth (Robinson-style outline, country borders, no Antarctica)
flood-filled so that each colour is the real-world stand-in for one Warhammer
region: the countries in a colour together take up about the same share of
Earth's land as that region takes of the mod's land, and sit in roughly the
matching part of the world. It answers "how big is Kislev, really?" by picture.

- Region areas on the Warhammer side are true spherical areas measured on the
  mod canvas (Miller, `config/canvas_frame.py`). Old World regions come from
  the strategic-region files; everything outside the drawn Old World comes from
  hand-drawn red zone outlines on a copy of the reprojected globe
  (`real-world-comparisons-f.png`, below).
- The match is by **share of total land**, not absolute km²: the mod's world
  has about 19% more land than Earth as vanilla draws it (158.8M vs 133.7M
  km²), so real areas are effectively scaled up by 1.188.
- Where no set of whole countries fitted, a country is split by a 1px line
  (the United States, Russia, Alaska, Argentina/Chile, Sudan, Finland). Line
  positions were placed from a fitted projection of the outline map and are
  good to a degree or two.
- Built iteratively by Claude and Chris on 2026-10-04/05. Claude's last pass
  had every zone within 3% of its target share; Chris then edited by hand, and
  the image is the record. Diffed against that pass, his edits are: Tibet
  folded back into Cathay (so Cathay now also stands for the Mountains of
  Heaven: +0.9% against the two combined); Algeria made whole again as the
  Badlands (+8.1%, Araby +0.8%); the Egypt/Sudan cut redrawn so Egypt is all
  Nehekhara and only eastern Sudan goes to Ind (Nehekhara +0.2%, Ind -1.1%);
  and a few stray pixels filled. Every other zone is unchanged and within 3%.
- Known mismatch: the tally used the zone outlines as they stood when the
  fill was built. The kept `-f` file was redrawn afterwards and now groups
  three zones differently (the steppe pocket north of the Ogre Kingdoms joins
  the Ogre zone, 8.95M km² in all; the north-east Cathay strip joins the
  eastern steppes). The combined area of those zones is the same, so the fill
  is right in aggregate but its Ogre / steppes / north-east strip split
  follows the earlier outlines.

Colour key (RGB hex): Naggaroth and the Chaos Wastes above it `7e007e`,
Ulthuan `78beff`, Lustria `1ed836`, far-south spur `3c78b4`, Norsca `8a3d2c`,
Kislev `7dffff`, the Empire `ff0000`, Bretonnia `0000ff`, Estalia `fca800`,
Tilea `7dff00`, Border Princes `ff7d00`, World's Edge Mountains with the
western ranges `00007e`, Badlands `7d7d00`, Dark Lands `8f8d7a`, northern
steppes `bf9c85`, Ogre Kingdoms with Gnoblar Country `5a3c96`, Cathay `ffff00`,
north-east Cathay strip `c8c800`, Ind `b68ee1`, Khuresh `4a5344`, Nippon
`ff64ff`, Araby `deb85f`, Nehekhara `965a14`, Southlands `006e3c`, Kingdom of
Beasts `c80078`, Sun Island with the Dragon Isles `00aaaa`, Lost Isles of
Elithis `96dc96`, Albion `ffb4b4`, northern edge fragment `505050`, Lumbria
`ff9696`. White is sea and inland water.

**`real-world-comparisons-f.png`** (8192x3616, 33,185,585 bytes, SHA-256
`bf00a94b10b860abcfffb16adaf5516c4c8bc55e1f9a1d82c5d83b5223666dd3`). The other
half of the pair: a canvas-sized copy of the reprojected Terraqueous Globe with
Chris's hand-drawn red outlines marking which land belongs to which Warhammer
region for this comparison (Naggaroth, Lustria, Ulthuan, Araby, the Southlands,
Cathay, Ind, Khuresh, Nippon, the steppes and so on). The outlines are rough by
intent and enclose sea as well as land; the land inside each is what was
measured. Markup, not a source: the lines are not state or region borders and
nothing reads them.

Both are comparison aids only: they contribute no geometry, names or
registration. Their GIMP masters (`real-world-comparisons-{f,r}.xcf`) are
still in `WIP/`.

## Verifying / refreshing

```
python mapgen/worldgen/sources.py --verify           # SHA-256 + registration cross-checks (offline gate)
python mapgen/worldgen/sources.py --update-manifest   # after an *intentional* source change only
```

`--verify` fails loudly on any missing file or SHA-256 mismatch. Refreshing a
source is the deliberate `--update-manifest` action — never a side effect of a
generator run. The table below (between the `MANIFEST` markers) is machine-read;
edit the Origin/Role cells by hand, let `--update-manifest` fill Dims/Bytes/SHA.

<!-- MANIFEST:BEGIN -->
| File | Dims | Bytes | SHA-256 | Origin | Role | Registered |
|---|---|---|---|---|---|---|
| High_Elf_Outposts.JPG | 3942x2586 | 1,321,940 | 680dd8d730f60efcf77a119ec132cdfa979d9caee5a9fbe6689e6ae639314d38 | Chris's source | Manifest only, unregistered — names the six High Elf colony tags (CDU FDW TEL TOS GCL TEH) and is the source of the CDU and FDW roundel arms (#8444) | no |
| Major_Trade_Routes_of_the_Old_World_Map.png | 1947x1404 | 690,310 | 12026b1e21ad7b9467ff1e3d597e98492739af19e2d8cf97407ddf5d28f7b919 | Games Workshop — "Major Trade Routes of the Old World" | Manifest only, unregistered — S6 reference | no |
| bretonnia_black_white_colored.png | 4210x4700 | 14,643,218 | 05d03cf362e17d8c805ead02915b66334be75f01d52346936f2ac611675a3610 | Internet find; the user colored the ocean blue | Primarily Bretonnia village placement; secondarily other Bretonnia features | no |
| climate_zones_flat.png | 4096x1808 | 227,993 | 0e45a6cffc9755e4f5f6142fe3ebec8d63513e36dd5130ef095a3f51b49a520b | TBD | TBD | no |
| climate_zones_flat.xcf | n/a | 26,222,158 | b6b61cd664e8d734bdcc490626058a9515d57b4c0751405826adcd16996505f5 | TBD | TBD | no |
| climates.xcf | n/a | 90,175,963 | e4cdce579ed4c28719366ccb04d108ae8a144fbea78bc4ff3b806da8a75abc4b | TBD | TBD | no |
| colored_globe.jpg | 1680x1214 | 429,642 | 91e12fbb2938d2ec61ed78abd1d42ad10615a3d427068acd5830a9598bf214c0 | Fan cartography — David "Fahran" Mills "Warhammer World Map" (war-rvr.net, 2006), a whole-world relief/satellite render with a blue ocean. Added by the user 2026-08-13 | Whole-world COASTLINE silhouette (`blue_sea` kind: ocean is blue-dominant but brightness-varying). Balanced land/sea (0.366 vs mask 0.369) so it registers globally, unlike the land-heavy regional tiles. A DIFFERENT source from the terraqueous globe (different projection — a freehand rectangular/cylindrical relief render, ~1.38:1, closest to a latitude-cropped equirectangular but NOT an analytic projection, so it stays a `control_point_warp`, not an analytic inverse; identified 2026-08-15), registered against the mask for coastline agreement; mask stays the sole authority | yes |
| cr_combi_expanded_map.xcf | n/a | 16,120,227 | 0aa2149f1c462bbb2016b8c28cb0210919d35ecbee106955136a06ac7860d570 | GIMP editable master, added by the user 2026-10-11 | A GIMP document of the expanded parchment kept beside the Ulthuan sheets; not read by any tool. Role inferred from the filename, Chris to confirm | no |
| fanmade_colored.png | 4726x3010 | 1,467,069 | d3962b9e28a49765c6c6f236b89b67924d06019835bcc857a51b41e5602b3817 | TBD | TBD | no |
| land_sea_mask.png | 8192x3616 | 260,735 | 506275815a55d16fe53d5166164fe33aa9ae0fb3a57c8d81316cf5cdb9b38827 | PNG export of `land_sea_mask.xcf`, now under `oldworld-first/` | The real land/sea mask in use — binarized first via `binarize_cyan_mask.py`; the `coastline_fill` `source_layers.json` ref (board #5399) | no |
| land_sea_mask.xcf | n/a | 1,258,208 | 9240cd00ec723e26082811f55256671a8507be5b82ff83ca60d1ba102c6132f2 | GIMP editable master | Editable master of `land_sea_mask.png`; not read directly by any tool | no |
| lustria_1.jpg | 2362x3271 | 1,059,627 | 2eac6ae87ada14619b4fcc285a00dd7247c47fa6c832d6fe2551bf122133097a | TBD | TBD | no |
| mega_detailed_old_world.jpg | n/a | 385,900,884 | 99b89752c24766a968cd4023a6450aa75bb34a3b01ac6ee6bcda3a698b7c7906 | Internet find | Primarily Old World town and forest placement; secondarily other Old World features | no |
| naggaroth_1.png | 2378x3166 | 11,505,584 | 0e44e34913a54852318400a1ed60591d1a422df29d8390fadefdfcb8bbb497ff | TBD | TBD | no |
| naggaroth_2.png | 1589x2267 | 2,339,450 | d27ab99b6d467e3adabf0ead64db4618510d6b56189d026411c926c1fb4ee885 | TBD | TBD | no |
| named_globe.png | 4096x2048 | 15,109,233 | 0f89110c2a4cc471f53319a05aba439a4a1e69119d06278b5374b0214ff22eff | Fan cartography — a labelled whole-world Warhammer map, blue-ocean relief with region names (Naggaroth, Ulthuan, the Old World, Southlands, Grand Cathay, …). Exact author unconfirmed. Added by the user 2026-08-12 | **Projection: equirectangular (plate carrée)** — identified 2026-08-15. Exactly 2:1 at 4096×2048 (power-of-two globe-texture dims), filled corner-to-corner with ocean/ice (an oval projection would leave the corners empty), meridians vertical. **Registered 2026-08-15** (`mapgen/registration/named_globe.json`) as a `control_point_warp`. A pure analytic-equirectangular placement was tried first and rejected (the artist drew landmasses at different proportions than the mask), so the geographic box was MEASURED by silhouette IoU against `land_sea_mask.png`: named_globe covers only ~320° of longitude and is latitude-cropped at ~40°S (affine cx≈2048 sx≈12.79 cy≈1348 sy≈17.50, 0.638 affine IoU), so it has NO coverage of the canvas far-eastern seam or its southern band. That affine seeds an 11×7 lattice `register.refine` pulled onto the mask to **0.788 IoU** (no folds, anisotropy≤3). Contributes NO coastline (mask stays sole authority) — a whole-world coastline reference like `colored_globe`, at a third projection. MACHINE-FITTED; re-derive, do not hand-edit. PROVISIONAL until the user accepts the render | yes |
| ocean_currents - Copy.png | 10233x3616 | 3,679,568 | 0a3ee852264a8cd8fbb9c537400012aa0c0018f3b1ee25e097c9e7dc7a2a6912 | Copy of `ocean_currents.png` | Assists with x-axis (seam) wrapping when working with the ocean-currents layer | no |
| ocean_currents.png | 8192x3616 | 959,633 | 57076d7be6a0f1aa1deaad25831cb24c6d99e7733b84310e18de70c43e174c9f | Generated (Claude) | Partially informs sea zone placement | no |
| old_world_map - full.ora | 2048x2048 | 14,010,651 | 360491a567a1efffae6ac89efb39d3468829091d7693cfd099a1cb4ca31055da | GIMP OpenRaster export of `old_world_map - full.xcf` | Layers `cities`/`state_regions`/`impassable`/`parchment_cropped` (measured during #5399 scoping); not read by any tool — out of scope for board #5399 | no |
| old_world_map - full.xcf | n/a | 16,393,362 | c4adac9c16213237c60fa1134474631c595639bdd479eb4f5a0c8b922c8d74c4 | GIMP editable master | Editable master of `old_world_map - full.ora` | no |
| old_world_map - stretched.xcf | n/a | 16,453,660 | 8fe1a631ce7d59306514f7733a092a1e2f8c1f56fe57ee91362d34da2fc2d662 | GIMP editable master | Editable master of the `old_world_map - stretched.png` working copy `render_old_world_map_overlay.py --source` can drape | no |
| old_world_map.xcf | n/a | 33,101,805 | 60f1e3e88d6660fa7989e2c0f726584b6093ba599d79735ec76efd029530f421 | GIMP editable master | Editable master, predecessor of `old_world_map - full.xcf`/`- stretched.xcf` — inferred from filename, Chris to confirm/correct | no |
| old_world_terrain.jpg | 3016x2080 | 1,140,330 | 80ae22f4aa384049cd42e70ade67db4f57853e6e91c9fbed30458dd9a69c1f91 | Games Workshop — Warhammer: The Old World world map | Old World / Badlands / Dark Lands / Araby / Land of the Dead boundaries. **NOT USABLE FOR GEOMETRY** (measured S3a) — misregistered off the coast, and not a chloropleth (see below) | yes |
| old_world_z10 - grayscale.png | 6658x9824 | 70,851,835 | c2b19d3cd0ce5c0551f9c628f17160ea9dc1cf03eec23320549758be1f43a095 | Grayscale copy of `old_world_z10.png` | Same role as `old_world_z10.png`, in grayscale | no |
| old_world_z10 - grayscale_dots.png | 6658x9824 | 70,851,835 | c2b19d3cd0ce5c0551f9c628f17160ea9dc1cf03eec23320549758be1f43a095 | Dot-marked derivative of `old_world_z10 - grayscale.png` (see that row) | Dot-picking reference — inferred from filename/sibling pattern, Chris to confirm/correct | no |
| old_world_z10 - grayscale_dots.xcf | n/a | 185,840,861 | ba1ccd86e97db14d324be589b20548e3c09648316de5f2bf1219e63348cade88 | TBD | TBD | no |
| old_world_z10.png | 6658x9824 | 120,598,002 | 856dfa35a633a3e7dead1972a37660791fc2b8fcbb18a59f3a535b2d3109428a | Games Workshop — official "Warhammer: The Old World" interactive map (start-warhammer.com), zoom-10 base tile layer, stitched by us (TMS tiles, transparent border cropped) | Highest-resolution whole-continent Old World reference in the folder. Base tile ART ONLY — the site's interactive city/army/region markers are separate overlays and are NOT baked in. Naming + extent + coastline/relief cross-reference (S6). Unregistered | no |
| satellite_globe.jpg | 637x358 | 43,099 | 8b90bae2e491a366a8c5deb3f1e8d9307dac6b8658d0fd7d62bb9c6de242d95b | Fan whole-world satellite/biome render (Steam Workshop) | **Projection: equirectangular** (rectangular whole-world texture, pillarboxed to 16:9 — black bars at x=[0..86] and x>548, content x=[87..548]; the map itself is corner-to-corner with vertical meridians). DE-REGISTERED in S2 — de-registered for cloud cover + the narrow 462-px usable width, not for its projection (see below) | no |
| state_regions_on_parchment - dots_7.png | 4096x4096 | 20,655,646 | 37123186f85b4e0bd963af068d050e668e37b110bba911754808a4c0b1a5e2db | Archive of the state border line drawing generator, dot-marked by the user | Region 7 dot-picking reference for the state-border drawing pass, same role as the other `- dots_7` variants | no |
| state_regions_on_parchment - dots_7.xcf | n/a | 43,446,175 | c7ae77cd95d04671abc69af3e31a68653608824f4fb4d8433ba7de9cc13a70f6 | Archive of the state border line drawing generator, dot-marked by the user | Editable master of the dots_7.png export above | no |
| state_regions_on_parchment.png | 4096x4096 | 20,655,646 | 37123186f85b4e0bd963af068d050e668e37b110bba911754808a4c0b1a5e2db | Archive of the state border line drawing generator | Flattened export of the state-border-drawing pass over the parchment | no |
| state_regions_on_parchment.xcf | n/a | 43,446,175 | c7ae77cd95d04671abc69af3e31a68653608824f4fb4d8433ba7de9cc13a70f6 | Archive of the state border line drawing generator | Editable master of the state_regions_on_parchment.png export above | no |
| stylized_world_map.jpg | 2048x1939 | 838,790 | 52e4c4b4be443b517b56ef5725eda8a08ae1bfd7485d66bd20694464068ec687 | TBD | TBD | no |
| terraqueous_globe.jpg | 4000x3256 | 2,292,545 | c4021e28d8d58bc3f91733df72ee9b7b398f922bb565b0478d3743446d8c15f3 | Fan cartography — "Terraqueous Globe", Kartografia Niepraktyczna 2022 | Whole-world heightmap (NE-II colour-to-height ramp) + coastline. **The single geometric authority** (S3a decision #1) — every other source projects onto it | yes |
| terraqueous_globe_reprojected - dots_7.png | 8192x3616 | 33,040,662 | be218e8678b0ce6134742b68ba9fa7f8afa794ac42d8b47794e29d5a4afc8c87 | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Region 7 dot-picking reference for the paired-anchor-dot workflow, same role as dots_1-6 | no |
| terraqueous_globe_reprojected - dots_7.xcf | n/a | 164,259,326 | 3d4af433759570c24695c6c020379cd3c138bb8f629821ead461e11f0cf2e55d | Derived from `terraqueous_globe_reprojected.png`, dot-marked by the user | Editable master of the dots_7.png export above | no |
| terraqueous_globe_reprojected - full.ora | 8192x3616 | 95,085,568 | ef3861931194ed590d8f1259435a72449765b5cfc1e48aea3e5c730cf96be724 | GIMP OpenRaster export of `terraqueous_globe_reprojected - full.xcf` | The canvas master (board #5399): layers `coasts`/`rivers`/`cities`/`borders`/`impassable`/`sea_zones`/`canvas`, read by name via `mapgen/config/source_layers.json` | no |
| terraqueous_globe_reprojected - full.png | 8192x3616 | 33,453,057 | 070ad9583e7be75efb8bd88181636e7d482b89692c8974679009fb1efe04066b | TBD | TBD | no |
| terraqueous_globe_reprojected - full.xcf | n/a | 109,876,148 | 9cfe7d2a28f41770f2c82685c0495135268e8dc359c98285ba9ea54fe97edcbe | GIMP editable master | Editable master of `terraqueous_globe_reprojected - full.ora` | no |
| terraqueous_globe_reprojected - grayscale.png | 8192x3616 | 24,587,697 | e5a40962048ea5fa68d752899cc89ee61ddab565b0e49c851bfe4905f56e4b7c | Grayscale copy of `terraqueous_globe_reprojected.png` | Same role as `terraqueous_globe_reprojected.png`, in grayscale | no |
| terraqueous_globe_reprojected - grayscale_dots.png | 8192x3616 | 24,587,697 | e5a40962048ea5fa68d752899cc89ee61ddab565b0e49c851bfe4905f56e4b7c | Dot-marked derivative of `terraqueous_globe_reprojected - grayscale.png` (see that row) | Dot-picking reference — inferred from filename/sibling pattern, Chris to confirm/correct | no |
| terraqueous_globe_reprojected - grayscale_dots.xcf | n/a | 87,438,501 | cf32f13c5a5cd9c9ebd727d5ae6b358e5140a22f35253c2219d3c794b0391316 | TBD | TBD | no |
| terraqueous_globe_reprojected - strategic_regions.png | 5310x2044 | 216,621 | dd8ac943d7bc22d5d882e376c8014b9f83a15f5e46d57037e0f442222dc33295 | TBD | TBD | no |
| terraqueous_globe_reprojected.png | 8192x3616 | 30,471,432 | 604fc9f92848fc25590f0a7d69b54a46dea79bd1acbc578f250304d36b06888c | Derived from `terraqueous_globe.jpg` (user, August 2026) | `terraqueous_globe.jpg` reprojected from its native Natural Earth II to Miller cylindrical — the mod canvas's own projection (see `config/canvas_frame.py`). Canvas-sized (8192x3616 = WIDTH x HEIGHT). Not yet consumed by any script; `generate_heightmap.py` currently reprojects `terraqueous_globe.jpg` itself via its NE-II fit rather than reading a pre-reprojected copy | no |
| terraqueous_globe_reprojected_full-southland-mountain-rework.xcf | n/a | 109,866,869 | 44a6a3a62c9c53e5635e81e41b2e39ef5f3b595ebb82386161e72a034d8262d3 | TBD | TBD | no |
| terraqueous_globe_with_NS_lines.jpg | 4000x3256 | 4,397,707 | 179ea7271e2adc0d509bce5358d40c3a60a36c251309dac4377a5acef0ca1c9c | Derived from `terraqueous_globe.jpg` (user) | `terraqueous_globe.jpg` with a north-south graticule drawn on, used as a registration/projection-check reference; contributes no geometry (globe stays the coastline authority) | no |
| the_empire_1.jpg | 5426x5091 | 22,888,291 | d12726947a3afaee43bbc174dbe95cba1288e7bf4dbf542e0a6a86065642bb29 | Internet find | Very detailed map of the Empire — villages, terrain, rivers, names, etc. | no |
| the_empire_2.jpg | 1920x1301 | 1,466,126 | 8c3f93454483dc261f933ad3d43530495cb11111071de2511669ac50f5ad2528 | Games Workshop / Warhammer Community — "The Empire of Man" map | Clean counterpart of the annotated map — differencing the two isolates the annotation | no |
| tww3_climate.jpg | 2471x1922 | 2,022,554 | fae9e090f0b2ffba1f82008dec5c2c36cf6a03dd0eaca0808b8822ba7b413edb | Total War: Warhammer 3 | Shows the (super-abstracted) climate used in the Total War game | no |
| tww3_ie_parchment.jpg | 3703x2880 | 3,225,567 | f6e4f53ea80673bb9b792f11b1ac1de387bb8e07757f8a384aa40fd8aea757c1 | Creative Assembly - Total War: Warhammer 3 Immortal Empires parchment campaign map (English) | **PRIMARY BOUNDARY + NAME SOURCE (world-map-parchment-areas-onto-globe.md, 2026-07-28)** - registered by `mapgen/fit_registration.py --seed wh3_dlc_ie_parchment_map_english` (silhouette objective via the climate map sibling, 10x8 lattice, 12 held-out landmarks). Fit: `refined_iou` 0.6193, `folded_fraction` 0%, `anisotropy_p99` 3.00, `landmark_check_px` mean 426.9 / max 872.1 - reported against the family's only other comparable record (`total_war_map_colored.json`: mean 312.2 / max 844.6, refined_iou 0.6617) as somewhat weaker but consistent (0% folding, same anisotropy), explained by the parchment's silhouette coming via a rescaled sibling rather than an exact flat-fill silhouette. The family's `ie_macro_twin.json` control points (baked standalone when the master was previously absent from `sources/`) reproduce EXACTLY (0.0 px mean/max) against this fit, confirming full reproducibility with the existing placement. Its interior line network is traced with lettering bridged (not erased) into the barrier, and its printed names are the S3a-2 review panel's missing name-to-geometry binding. Also the differencing counterpart for macro grouping (unchanged role). | yes |
| tww3_old_world_mod_grayscale.png | 4096x4096 | 16,207,148 | a02fed5a10833e32988fe2b83f894e529fa1894370e13929c9a1533989c762e4 | Grayscale copy of `tww3_old_world_mod_parchment.png` | Same role as `tww3_old_world_mod_parchment.png`, in grayscale | no |
| tww3_old_world_mod_grayscale_dots.png | 4096x4096 | 16,207,148 | a02fed5a10833e32988fe2b83f894e529fa1894370e13929c9a1533989c762e4 | Dot-marked derivative of `tww3_old_world_mod_grayscale.png` (see that row) | Dot-picking reference — inferred from filename/sibling pattern, Chris to confirm/correct | no |
| tww3_old_world_mod_grayscale_dots.xcf | n/a | 48,707,184 | d03c6037049d08c078b66a907dbc8af57885b959db17da6d1f71d44506082b31 | TBD | TBD | no |
| tww3_old_world_mod_parchment - dots_7.png | 4096x4096 | 22,918,076 | ae929894eb869f60c776360b9072525cc1dd2f4d2846595937afc7d4a74e45e2 | Derived from `tww3_old_world_mod_parchment.png`, dot-marked by the user | Region 7 parchment-tile dot-picking reference, same role as dots_1-6 | no |
| tww3_old_world_mod_parchment - dots_7.xcf | n/a | 90,373,003 | 4aafe190d1d1d6411f190525f8d83fbbf464b6b00d56c57022a87b6a8e2376de | Derived from `tww3_old_world_mod_parchment.png`, dot-marked by the user | Editable master of the dots_7.png export above | no |
| tww3_old_world_mod_parchment.png | 4096x4096 | 8,332,865 | 93f5c7b4791d7a02b60eeb4ba96bf5abc66ad4d650978d1990b022840de903a3 | Fan cartography — "The Old World, all faction starting positions v3.0" | **Denser Old World boundary network** — a line chloropleth, markedly denser than IE over the same arc. Higher precedence inside a masked footprint; the four corner vignettes + the Galleon's Graveyard spiral are excluded (they take cartographic liberties — user-flagged) | no |
| tww3_old_world_mod_parchment_cropped.png | 4096x4096 | 28,200,702 | 0f0e371c81d4428d719c4f995729a5077178031205b503784fff57e45b8d6af4 | Cropped by the user from `tww3_old_world_mod_parchment.png`, out-of-scope regions removed | Replaces `tww3_old_world_mod_parchment.png` as the baseline parchment reference wherever it's used, once the out-of-scope extent needs excluding | no |
| tww3_states_per_strat_region.jpg | 2048x1593 | 1,112,706 | b8965b704a476a5e93276f217c17dc6b6135301c87564c36ebb6d181252303ca | Fan annotation of the IE parchment master - strategic regions outlined, named, and labelled with their Total War: Warhammer 3 state counts | **NAMED MACRO REGIONS** - the source that binds region names to geometry, without which none of the user's per-region requirements can be checked. 17 named regions; supersedes pizqenw9rd791.jpg for grouping. Frame alias of the twin (exact 0.553 rescale, now pointing at `tww3_ie_parchment.jpg`). Printed counts are a reference, not truth. **Re-added** after the August 2026 retirement — same bytes (SHA-256 confirmed), so registration is restored rather than re-derived | yes |
| ulthuan_1.jpg | 764x771 | 188,484 | 7517492e515be7712c933e98f43095e078ddd1b0911538ba47ddec90c11e2edb | TBD | TBD | no |
| ulthuan_2.png | 1080x1080 | 126,002 | eb168dc9852441b1f885128bdac216d12d32d6c4c88127fc5e7c8cce2195658a | TBD | TBD | no |
| ulthuan_3.png | 781x830 | 286,800 | 978142cc35e9919c88d4b46240e02bbdc0a09cd891bb86eb2034554b73964da1 | TBD | TBD | no |
| ulthuan_parchment.png | 6400x4480 | 56,463,651 | 7ab020f36ba96d4e4a2a858ba7dd3a2233008f5fc88debf1414d20114ab73f85 | ChaosRobie's expanded Immortal Empires parchment (`cr_combi_expanded_map`, see the `cr_immortal_empires_expanded/` section), dot-marked by the user 2026-10-11 | Ulthuan paired-anchor-dot sheet, parchment side: the dots, a cyan trace of Ulthuan's coast and the magenta state-border network. `dots_source` of the `cr_combi_expanded_map_ulthuan` seed; the clean parchment is derived from it on demand | no |
| ulthuan_parchment.xcf | n/a | 80,912,404 | fc0b1ffa17f366ac7fbe8b1b4106f5f20e0c7166deaaf73b3fe878aa5fdc05e1 | GIMP editable master | Editable master of `ulthuan_parchment.png`; not read by any tool | no |
| ulthuan_terraqueous.png | 4096x1808 | 9,085,020 | 3c3860b49013dde1ccaa987ef9cd9f7c0394f3b7c3d91f35130e533a91c92aea | Top-left 4096x1808 of `terraqueous_globe_reprojected.png` (canvas pixels, zero offset), dot-marked by the user 2026-10-11 | Ulthuan paired-anchor-dot sheet, canvas side: the same dots plus the cyan coast trace. `dots_reseed.canvas_dots` of the `cr_combi_expanded_map_ulthuan` seed | no |
| ulthuan_terraqueous.xcf | n/a | 22,453,440 | 2bac967a3efbcde8bd842f0a0ab1006151f033c51bce2372df3b5b2f7237d958 | GIMP editable master | Editable master of `ulthuan_terraqueous.png`; not read by any tool | no |
| warhammer-world-map-8k-cropped.png | 2867x2029 | 10,012,338 | de82489649b1780fd34d0e855f48574efcf6d6a731f9aec03daee028f23eb53a | TBD | TBD | no |
| warhammer-world-map-8k.png | 4389x2029 | 1,787,168 | 81d3c4150a7df1dc345dfa9186b8d14d110278b4679038a5a7a8fc3f4fc68055 | TBD | TBD | no |
| white_dwarf_world_map.png | 4524x3093 | 1,960,224 | c5a4c6708600fedbfe404c59a7c8d6ab5745eea6e4d35a28180ef13932b37be7 | Games Workshop — official Warhammer world map (boxed / White Dwarf fold-out poster; the sheet prints "© Games Workshop Ltd 2000–2004" and "Product code 60440199034"). Fold seams visible | **Projection: oval pseudocylindrical, flattened-pole (Winkel Tripel / Robinson / Natural Earth family — NOT pointed-pole Mollweide/Aitoff)** — identified 2026-08-15. The world's printed neat-line is a smooth arc bowing down to clipped corners, ~360° of longitude wrapping (HUNG at both far edges); the broad clipped top is a pole line, not a point. Same oval family the terraqueous NE-II globe reproduces. Manifest/naming/extent reference only; unregistered — a fit would try the `natural_earth_2` kind, falling back to a `control_point_warp` if its oval isn't exactly NE-II | no |
| winds_and_currents.png | 8192x3616 | 377,553 | a19d25fd52da4ccde9a6126d4d81f1d2d70e22fa02d7a20b16b2c7589f2ea9bf | Drawn by Chris on the canvas frame (single layer, flat colours: land green, sea blue, strokes pure red `255,0,0` warm and pure cyan `0,255,255` cold); editable master `winds_and_currents.xcf` | Warm and cold ocean-current drawing read by `generate_climate_zones.py` through `source_layers.json` key `climate_currents`. A stroke only reaches about 240 km from a coast (`cur_sig`); strokes in open ocean do nothing. The stage never edits it | no |
| winds_and_currents.xcf | n/a | 90,129,409 | d21608dd8e2f95b3b6ced5c510355debc8dd77438bd2dceae519c85989cdb297 | GIMP editable master | Editable master of `winds_and_currents.png`; not read by any tool | no |
<!-- MANIFEST:END -->

## Local organisation: descriptive filenames

Every source `load_source_image`/`load_source_image_rgba` actually reads —
anything with a manifest row above — is found by `resolve_source_path()`
across `sources/` and the five searched subfolders (see Layout above); a
`<file>.ora#<layer>` reference resolves its container file the same way, then
reads the named layer directly from the zip. A file dropped in an unsearched
folder (`archive/`, `WIP/`, `dots-claude/`, `history/`, `cr_oldworld_campaign/`, `cr_immortal_empires_expanded/`) is invisible to
`--verify`, `--update-manifest`, and every loader.

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

`sources/dots/` held the visual record of the paired-anchor-dot registration
workflow's per-region carves: for each region `N` in {1..6},
`terraqueous_globe_reprojected - dots_N.png` (the canvas frame with that
region's dots marked) and its matching region crop
(`tww3_old_world_mod_parchment - dots_{1..4,6}.png` for the five parchment tiles;
`old_world_z10 - dots_5.png` for the northern relief crop) with the dots still
on — plus the marker-palette listing `127 0 191.txt`. The dots↔region pairing
was: 1 = Empire, 2 = Bretonnia+Estalia+Tilea, 3 = Kislev+Norsca, 4 = Dark Lands,
5 = start_warhammer northern relief, 6 = Badlands+Nehekhara.

**Retired by board #5403 (2026-09-23).** The unified Delaunay triangle warp
(`tww3_old_world_mod_parchment_full`, derived from `dots_7` under
`sources/dots-triangles/` — a *different*, still-searched sheet) had already
superseded the five per-region crops as the live parchment-drape backend
(user decision 2026-09-18). Chris moved the six dots_1..6 sheets into
`sources/archive/`, which the tools no longer search (`SOURCE_SUBDIRS` in
`worldgen/sources.py` excludes `archive`), so the six per-region registrations
+ their seeds (`mapgen/registration/tww3_old_world_mod_parchment_{empire,
bretonnia,kislev_norsca,dark_lands,badlands_nehekhara}.json` and
`start_warhammer_old_world_northern.json`, plus their seeds) were removed
outright rather than left dangling — the same "confirmed gone, remove rather
than leave dangling" precedent as the August 2026 reorg's three retired
sources (`pizqenw9rd791.jpg` et al.) above. Their only consumers —
`mapgen/project_regions.py`, `mapgen/diff_state_borders.py`,
`mapgen/project_lines_onto_parchment.py` — could not function without them and
were deleted outright; `render_land_regions_preview.py`'s `--warp five-crop`
fallback and `render_anchor_dot_example.py`'s `--combined`/`--all` options were
removed for the same reason. `generate_state_labels.py`'s `BOUNDARY_SOURCES` /
`OLD_WORLD_CROP_MIN_STATES` also wired in three of these six crops as LIVE
boundary-line sources for bretonnia/kislev_norsca/dark_lands — user-confirmed
decision: retire those entries too, a disclosed capability loss (that script's
boundary-line coverage for those three macros now comes from IE/`tww3_colored.png`
only), safe because `generate_state_labels.py` is decoupled from the live
province pipeline (`generate_provinces.py` reads the hand-drawn magenta
`state_regions.png` directly) and isn't part of the offline gate.

The composite QA renders that used to live at
`mapgen/derived/<region>_anchor_dot_warp_example.png` and
`mapgen/derived/old_world_anchor_dot_warp_combined.png` (their old location; renders now land in `scratchpad/`) are gone too — they were
regenerated only by the now-removed `--all`/`--combined` options and are
permanently unregenerable without them, so they were `git rm`'d along with the
`.gitignore` allowlist line for the combined one.
`mapgen/render_anchor_dot_example.py --seed <stem>` remains live for any
still-registered seed (today, `tww3_old_world_mod_parchment_full`), deriving
its clean source on demand from its own `dots_source` sheet via
`worldgen.derive_crop.derive_clean_source`.

## The .ora-per-.xcf convention (board #5399, 2026-09-23)

Chris switched from exporting one flattened PNG per concern into a
now-retired `sources/gimp_exports/` folder to exporting the whole GIMP
document once, as OpenRaster (`.xcf` → matching `.ora`, same folder, same
stem), and letting tools pull each concern out by layer name. The canvas
master is `oldworld-first/terraqueous_globe_reprojected - full.ora`, whose
layers are `coasts` (cyan trace only, no land fill), `rivers` (blue), `cities`,
`borders`, `impassable`, `sea_zones` and `canvas` (the globe backdrop).
`mapgen/config/source_layers.json` is the committed table mapping each
concern to its `<file>.ora#<layer>` reference; `sources.verify()` checks every
entry resolves to a real file, a manifest row, and a layer name that exists
exactly once. `mapgen/worldgen/sources.py`'s `read_ora_layer()` reads the zip
directly (never extracts it) and composites the named layer onto the full
canvas at its own offset, with RGB zeroed under alpha 0 so a tool's exact-paint-
colour detection never sees whatever the encoder stored under a transparent
pixel — `read_source_rgba()` (the new unverified dev-render loader) applies the
same zeroing to a flat PNG for the same reason.

As of this board item, `full.ora`'s `borders` and `impassable` layers are
**empty** (a bad export Chris is redoing): `generate_provinces.py` hard-errors
on the empty required `state_borders` ref, and `validate_map.py`'s impassable
collision check degrades to a non-blocking skip until the re-export lands.

Two kinds of source were deliberately kept as flat PNGs rather than folded
into an `.ora` layer: the paired-anchor-dot sheets (their several layers only
make sense read together) and the two single-layer masks —
`land_sea_mask.png` (the land/sea fill; binarize it first with
`binarize_cyan_mask.py`, since the `.ora` `coasts` layer is only the cyan
trace and — measured during scoping — differs from the fill by ~145k px) and
`terraqueous_globe_reprojected - tiny_islands_merger.png`.

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
through `mapgen/generate_rivers.py`, not from the heightmap's drainage (the old
`worldgen/hydro.py` path is retired from the river generator). This annotated
Empire map never places pixels — it is freehand over a stylised illustration that
does not register tightly — so it stays a reference the user reads by eye to
decide *which* traced streams are the Reik, the Talabec, and so on (the
anchor-keyed names in `mapgen/config/canon_river_names.json`), covering the Empire
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
