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
| TheEmpire.webp | 1596x1024 | 682,992 | e19ad56e0b21023955f3ed91301073aba03efe08b4506b4d6f3e5b4fab51adff | Games Workshop — The Empire provinces map | Empire internal subdivision | yes |
| TheEmpireRivers.jpg | 1920x1301 | 1,466,126 | 8c3f93454483dc261f933ad3d43530495cb11111071de2511669ac50f5ad2528 | Games Workshop / Warhammer Community — "The Empire of Man" map | Empire river system reference (Reik/Talabec/Stir/Aver) — consulted for the v1 river courses in tools/rivers/rivers.json, not warped | no |
| Warhammer_olde_world_map.webp | 1434x975 | 442,484 | d8aad1d1697980aab21f95e5724a9f95d5889656cac73cb66dd5cab578d094f5 | Fan cartography — "Landes and Seas of the Worlde" | Naming + extent confirmation (S6 naming pass) | no |
| images.steamusercontent.jpg | 637x358 | 43,099 | 8b90bae2e491a366a8c5deb3f1e8d9307dac6b8658d0fd7d62bb9c6de242d95b | Fan whole-world satellite/biome render (Steam Workshop) | DE-REGISTERED in S2 - does not register (see below) | no |
| ljzbtm288r891.jpg | 4000x3256 | 2,292,545 | c4021e28d8d58bc3f91733df72ee9b7b398f922bb565b0478d3743446d8c15f3 | Fan cartography — "Terraqueous Globe", Kartografia Niepraktyczna 2022 | Whole-world heightmap (NE-II colour-to-height ramp) + coastline | yes |
| map-the-old-world.jpg | 3016x2080 | 1,140,330 | 80ae22f4aa384049cd42e70ade67db4f57853e6e91c9fbed30458dd9a69c1f91 | Games Workshop — Warhammer: The Old World world map | Old World / Badlands / Dark Lands / Araby / Land of the Dead boundaries | yes |
| the_old_world_bot_left.png | 1195x683 | 1,542,117 | adf58b58178b2de1fb58b3f3d84038125809a8b5b2c4b727f5467f185bde856d | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (bot-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_bot_right.png | 1191x676 | 1,586,780 | 6462a83e8084bc01da73082d7e4099f897c4b6fdb6405e03c410a4213bf2743d | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (bot-right) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_bot_left.png | 1192x680 | 1,610,370 | 31e87b7948fac60aca9e475eda8a4bc3b8938958e2a8a169e1889637f002bb91 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-bot-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_bot_right.png | 1190x676 | 1,581,702 | ebc9ae26794d596d5e2182adafeaaa440d46602df25eff073f30c72e402c9125 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-bot-right) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_top_left.png | 1191x679 | 1,803,901 | bba872c288113332e0c35e003b13c5a56e724226deba61763d247ba2752f3a89 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-top-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_mid_top_right.png | 1191x676 | 1,689,342 | 8ca134d1bea237def8eab18ea9ece930604307865addf86a1587361c2799f6e5 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (mid-top-right) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_top_left.png | 1193x679 | 1,531,068 | 3c92d0603de70557b857df60e3c7f334f1459cc69ec50947b787e2b97601a6a0 | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (top-left) of the hi-res Old World map — S3 boundaries | no |
| the_old_world_top_right.png | 1197x678 | 1,362,417 | b4541e35e06dbed408e9e886da0d97023c2c8db53d1ba6d20457d9363887d86b | Games Workshop — hi-res Old World map (interactive tiles) | Pre-stitch tile (top-right) of the hi-res Old World map — S3 boundaries | no |
| tww3_map_bot_left.png | 1898x1058 | 3,082,592 | 6d00af0b9295ff6fb04377a599e13659212ad5c71c539a7eb0cffc4424b05ed6 | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| tww3_map_bot_right.png | 1919x1066 | 3,176,709 | d049334f929ead54d03f678f084b84ccbdc530830cc28fb9308634abdbe9f2aa | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| tww3_map_stitched.paint | n/a | 18,118,672 | 94b5726b6f02f65acf5379dc15a8e97fd9d0fca7f6bdcf16d612a5c45b347597 | Total War: Warhammer 3 Immortal Empires campaign map (stitch project) | Editable master of tww3_map_stitched.png (not consumed directly) | no |
| tww3_map_stitched.png | 2531x1961 | 8,089,308 | f975c35d32578d8d6ec7cbf4a2dd079d5845a6f685f6a568ad1b21b58c7f24c4 | Total War: Warhammer 3 Immortal Empires campaign map (stitched screenshots) | High-detail coastline + relief for its arc (consumed flat artifact) | yes |
| tww3_map_top_left.png | 1890x1034 | 3,666,866 | 086cfaeab68c457a21cdea14ddeddda127ad85a062442931ac022f73f624bbb1 | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| tww3_map_top_right.png | 1919x1079 | 3,657,669 | d77d5441291a5960aaf6851870a92fbf85cab4c0ffa43b578b0086063e61eea5 | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| updated-warhammer-the-old-world-map-v0-eyiuahz1swhg1.webp | 640x938 | 135,766 | 4559b8beb215f976ef8aed1339ef94c36dcf2d40ccb9cb88cc863d8b5cac05da | Games Workshop — updated Old World relief map | Old World relief cross-check (S6) | no |
| wahafa-world-map.jpg | 547x365 | 32,445 | 69f7f4a483dd1976234e1399c88e59225093db101d8af8ba2c974f62d6257bd1 | Fan cartography — "wahafa" whole-world map | Whole-world coastline / extent cross-reference (unregistered) | no |
<!-- MANIFEST:END -->

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
