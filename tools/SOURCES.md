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
| Warhammer_olde_world_map.webp | 1434x975 | 442,484 | d8aad1d1697980aab21f95e5724a9f95d5889656cac73cb66dd5cab578d094f5 | Fan cartography — "Landes and Seas of the Worlde" | Naming + extent confirmation (S6 naming pass) | no |
| images.steamusercontent.jpg | 637x358 | 43,099 | 8b90bae2e491a366a8c5deb3f1e8d9307dac6b8658d0fd7d62bb9c6de242d95b | Fan whole-world satellite/biome render (Steam Workshop) | Coarse global frame anchor + land/sea layout | yes |
| ljzbtm288r891.jpg | 4000x3256 | 2,292,545 | c4021e28d8d58bc3f91733df72ee9b7b398f922bb565b0478d3743446d8c15f3 | Fan cartography — "Terraqueous Globe", Kartografia Niepraktyczna 2022 | Whole-world heightmap (NE-II colour-to-height ramp) + coastline | yes |
| map-the-old-world.jpg | 3016x2080 | 1,140,330 | 80ae22f4aa384049cd42e70ade67db4f57853e6e91c9fbed30458dd9a69c1f91 | Games Workshop — Warhammer: The Old World world map | Old World / Badlands / Dark Lands / Araby / Land of the Dead boundaries | yes |
| tww3_map_bot_left.png | 1898x1058 | 3,082,592 | 6d00af0b9295ff6fb04377a599e13659212ad5c71c539a7eb0cffc4424b05ed6 | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| tww3_map_bot_right.png | 1919x1066 | 3,176,709 | d049334f929ead54d03f678f084b84ccbdc530830cc28fb9308634abdbe9f2aa | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| tww3_map_stitched.paint | n/a | 18,118,672 | 94b5726b6f02f65acf5379dc15a8e97fd9d0fca7f6bdcf16d612a5c45b347597 | Total War: Warhammer 3 Immortal Empires campaign map (stitch project) | Editable master of tww3_map_stitched.png (not consumed directly) | no |
| tww3_map_stitched.png | 2531x1961 | 8,089,308 | f975c35d32578d8d6ec7cbf4a2dd079d5845a6f685f6a568ad1b21b58c7f24c4 | Total War: Warhammer 3 Immortal Empires campaign map (stitched screenshots) | High-detail coastline + relief for its arc (consumed flat artifact) | yes |
| tww3_map_top_left.png | 1890x1034 | 3,666,866 | 086cfaeab68c457a21cdea14ddeddda127ad85a062442931ac022f73f624bbb1 | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| tww3_map_top_right.png | 1919x1079 | 3,657,669 | d77d5441291a5960aaf6851870a92fbf85cab4c0ffa43b578b0086063e61eea5 | Total War: Warhammer 3 campaign map screenshot | Pre-stitch tile of tww3_map_stitched.png | no |
| updated-warhammer-the-old-world-map-v0-eyiuahz1swhg1.webp | 640x938 | 135,766 | 4559b8beb215f976ef8aed1339ef94c36dcf2d40ccb9cb88cc863d8b5cac05da | Games Workshop — updated Old World relief map | Old World relief cross-check (S6) | no |
<!-- MANIFEST:END -->
