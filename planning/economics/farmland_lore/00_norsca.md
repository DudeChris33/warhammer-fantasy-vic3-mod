# Farmland lore dossier: Norsca (`map_data/state_regions/00_norsca.txt`)

Epic #3675, child #3681 (Norsca half). Research run 2026-11-19 / 2026-11-20. Status: **complete** (45 entries,
45 rows; rows machine-checked for 8 fields, key order and coverage against the state file). **45 state keys** in the file (a `grep -c "^STATE_"` says 44 because the
first key sits behind the file's byte-order mark); every one gets an entry and a row.

What the file actually holds (counted, not assumed): 30 Norscan-tribe states, 4 Norse Dwarf states (KRD, KRV, KOR),
3 Clan Moulder states (Hell Pit), 4 Troll Country / far-north Kislev states (TRO, UNG, DOL), 4 Zorn Uzkul / High
Pass states (UZK and one unowned). **No Albion state is in this file** (Albion sits under the `03_brettonia` stub
per `CLAUDE.md`), so Albion is not covered here.

Citation prefixes: `lex:` = Lexicanum page read through the browser pane on 2026-11-19; `fandom:` = Fandom Warhammer
Wiki, read live on 2026-11-19 and/or in the local dump `sources/wiki/pages/` on 2026-11-20; `rw:` = real-world
source; `vanilla:` = the vanilla install's `map_data/state_regions`. Everything about lore is paraphrase.

## 1. Realm picture

### 1.1 Canon

**Norsca proper.** A mountainous peninsula of long hard winters and dense forest, ringed by the Sea of Claws (south),
the Sea of Chaos (west) and the Frozen and Kraken Seas (north and east).
`lex:Norsca#lead [Warhammer: The Old World Rulebook pp. 82-83, 224]`

- **Farming is marginal and seasonal.** There are few viable arable fields, and they are worked only in the warmer
  six months; most Norse live as raiders. `lex:Norsca#Society [Tome of Corruption (WFRP 2e) ch. XI, pp. 136-144]`.
  Fandom's paraphrase of the same chapter: few crops grow, the ground is iron-hard, and in summer the air warms just
  enough to work the sparse stretches of farmable land, which supplement a diet of fish, bear and other game.
  `fandom:Norsca#Geography [Tome of Corruption pp. 136-141; Warriors of Chaos 8e p. 8]`
- **Who works the land.** Peasants tend the fields and control the thralls; a loyal warrior or peasant can be granted
  land as a freeholder, with thralls to work it. `lex:Norsca#Social Structure [Tome of Corruption pp. 136-144]`.
  Thralls are set to shipbuilding or to work the frozen fields of farmsteads.
  `fandom:Norsca#Thralls [Tome of Corruption pp. 142-145; Liber Chaotica: Khorne]`
- **Where settlements go.** A site needs one useful resource: good fishing, forest for timber and hunting, or a rich
  patch of soil. Most settlements are small (a dozen clans) but number in the thousands.
  `fandom:Norsca#Norscan Settlements [Tome of Corruption pp. 146-150]`
- **The land.** Mostly mountains, which make the interior hard to reach, so fortified villages cluster on the
  southern and western coasts; vast pine and spruce forests stand mainly on the interior slopes of the ranges, in the
  lee of the northern storms; glaciers spread from the Chaos Wastes across the Frozen Sea.
  `lex:Norsca#Locations [Tome of Corruption pp. 136-144]`. Fandom adds that pack ice and glaciers cover most of the
  northern half of the country and that inland the fjords give way to frozen steppe where tribesmen hunt.
  `fandom:Norsca#Geography [Tome of Corruption pp. 136-141; Warriors of Chaos 8e p. 8]`
- **The sea feeds them.** Whaling is a respected trade; one whale feeds a village for months, small whales are driven
  ashore with boats, large ones are hunted from longships.
  `fandom:Norsca#Whaling [Tome of Corruption pp. 136-150; WFRP 2e Career Compendium]`. The Bjornlings live by fishing,
  raiding and trade. `lex:Bjornling#lead [Sea of Claws (WFRP 4e) pp. 58-62]`. The Skaeling Coast's sea is full of fish,
  sharks and whales; fir forest grows in the sheltered valleys. `lex:Skaeling_Coast [Sea of Claws p. 48]`
- **Exports.** Whale oil, ivory and lumber, sold by Norse merchants in Old World ports; rare timber, gold, silver
  and warpstone in the interior. `lex:Norsca#Society, #Trade [Tome of Corruption pp. 136-144]`. Furs, meat, gems,
  iron ore and slaves go to the Chaos Dwarfs of Zorn Uzkul. `fandom:Norsca#Crafts and Trade [Warriors of Chaos 7e
  pp. 38-41; 8e p. 55]`
- **No crop is named anywhere** in the pages read. Livestock named: shaggy cattle at Vinnskor (Baersonlings), cattle
  stolen by the Aeslings, chickens at Skraevold, goats on the Skaeling Coast and in a southerner's warning about the
  Bearmen; cheese and wool only in the Norse Dwarf gazetteer.

**Norse Dwarfs.** The Giantshome (Grontklung) Mountains are described as a land of plenty: mountainous coasts under
conifer forest rich in game, rivers and coastal waters full of fish, amber in the valleys.
`fandom:Norse Dwarfs [Dwarfs: Stone and Steel (WFRP 1e) p. 42]`. The WFRP 4e gazetteer lists grain among the products
of Kraka Drak (exports amber, grain, sapphires, silver) and of settlements under every Norse hold but Ravnsvake's own
seat: Khazid Ravik (cheese, fur, grain, wool), Sjoktraken (grain, amber, trade), Khazid Fneldruk (fur, grain, metal),
Grung Dobekzhulf (grain, metalwork), Kazad Dumund (grain and cheese for Kraka Ornsmotek).
`lex:Kraka_Drak#Trade, lex:Khazid_Ravik, lex:Khazid_Fneldruk [Lords of Stone and Steel (WFRP 4e) p. 24]`;
`fandom:Kraka Drak, fandom:Kraka Dorden, fandom:Kraka Ornsmotek, fandom:Kraka Ravnsvake [Lords of Stone and Steel p. 24]`

**Troll Country.** Steppe in the south shading to tundra in the north, a few hills and forests, salt-marsh deltas
(Tobol, Kalti) and the rocky Bile Lands coast; the people (mostly Ungol, with Sarl Norscans on the north-west coast)
are nomads who follow game herds and camp only in deep snow. `lex:Troll_Country [Sea of Claws pp. 34-37; Realm of the
Ice Queen p. 60]`. Fandom, from Realm of the Ice Queen p. 59: among the least forgiving land in the Old World, **no
farming is possible**; reindeer graze lichen in winter and grass in the short summer. `fandom:Troll Country [Realm of
the Ice Queen pp. 59-60; Sea of Claws pp. 34-37]`

**Hell Pit.** A chasm in a snowy mountainside on the northern spur of the Worlds Edge Mountains, in the blasted
Troll Country waste; the land around is barren, and Moulder's packmasters scour it for beasts.
`lex:Hell_Pit#Overview [Skaven 7e p. 15; White Dwarf 311]`. No text on what the clan eats was found.

**Zorn Uzkul and the High Pass.** A vast plateau of barren rock under thin, cold air, so bleak that most of the
migrating Dwarfs turned back. `lex:Dark_Lands#Zorn Uzkul [Warhammer Armies: Orcs & Goblins]`. Fandom: frigid, thin
air, dusty ground strewn with bones, rich in minerals. `fandom:Zorn Uzkul [Tamurkhan pp. 164-165]`. The High Pass
(Belyevorota) is the northernmost and worst pass over the Worlds Edge Mountains: glaciers, cliffs, snow that rarely
melts even in summer. `fandom:High Pass [Realm of the Ice Queen p. 11]`

### 1.2 Real-world analogue, c. 1800-1850

Norsca is the Viking-age North Sea world; Lexicanum's own trivia note says so (`lex:Norsca#Notes`). On the canvas the
realm runs from about 59.5 N to 70 N (anchors at canvas rows 200-600 under `mapgen/config/canvas_frame.py`), the same
band as Norway (58-71 N), and table 4.7 of `planning/economics/arable_land_engine_research.md` measures it at about
1.10 M km2, the size of Norway, Sweden and Finland together.

- **Norway: a few percent farmed.** Grain fields and meadow together were "hardly 3 %" of the country and grain
  fields alone about 0.7 % (1/140) around 1900; about 70 % of the country is barren and 21 % forest.
  `rw:Norway [Norway: Official Publication for the Paris Exhibition 1900, agriculture chapter,
  https://runeberg.org/norparis/0320.html]`; `rw:Norway [1911 Encyclopaedia Britannica, "Norway",
  https://en.wikisource.org/wiki/1911_Encyclop%C3%A6dia_Britannica/Norway]`. Area statistics before 1907 are
  estimates (`rw:Norway [Statistics Norway, https://www.ssb.no/a/en/histstat/kap14.html]`), so the 1900 figure is
  the nearest sound number to 1836.
- **Crops.** Oats (about 242,000 acres) and barley (128,000) dominate; rye 34,000, wheat 11,000 ("rarely found north
  of the Trondhjem Fjord"), potatoes 97,000 and grown almost everywhere. Barley is "pretty certain to mature every
  year" up to 70 N; rye reaches 69-70 N around Tromso. `rw:Norway [same publication,
  https://runeberg.org/norparis/0325.html, /0326.html, /0327.html]`. Pre-industrial crops were the hardy grains (oats,
  rye, barley); livestock were sheep, goats, cattle, pigs. `rw:Norway [https://en.wikipedia.org/wiki/Economic_history_of_Norway]`
- **Herding.** Seter (summer mountain farm) transhumance was common through most of Norway because the lowland is so
  scarce: stock went up in late June, women milked and made cheese, the valley meadow was kept for hay.
  `rw:Scandinavia [https://en.wikipedia.org/wiki/Transhumance]`. In the far north the Sami kept large reindeer herds
  (`rw:Norway [1911 EB]`); reindeer pasture today covers about 40 % of mainland Norway
  (`rw:Fennoscandia [https://en.wikipedia.org/wiki/Reindeer_herding]`).
- **Fishing.** The coast lived as fisher-farmers: holdings too small to live on, eked out with fishing
  (`rw:Norway [Jones 1985, Northern Studies 22, via search; Norway 1935 handbook,
  https://runeberg.org/norway35/0147.html]`). The Lofoten cod fishery has been the centre of great cod fisheries for
  over a thousand years (`rw:Lofoten [https://en.wikipedia.org/wiki/Lofoten]`). Northern Norway could not feed
  itself in grain: the Pomor trade (1740-1917) brought Russian rye flour north in exchange for dried cod
  (`rw:Northern Norway [https://en.wikipedia.org/wiki/Pomor_trade]`).
- **Iceland: the no-grain end of the scale.** Grain culture "is not practised"; all bread-stuffs are imported; hay is
  the only crop; in 1850 82 % of Icelanders lived by stock-raising and 7 % by fishing. About 1 % of the island is
  under cultivation today. `rw:Iceland [1911 EB "Iceland",
  https://en.wikisource.org/wiki/1911_Encyclop%C3%A6dia_Britannica/Iceland; https://en.wikipedia.org/wiki/Agriculture_in_Iceland]`
- **Whale drives.** The Faroese pilot-whale drive (boats herd a pod onto a beach; records from 1584) is the real
  practice the Tome of Corruption's "herd small whales ashore" describes.
  `rw:Faroe [https://en.wikipedia.org/wiki/Whaling_in_the_Faroe_Islands]`
- **Troll Country analogue: the Russian Arctic coast.** Pomors of the White Sea lived by sea-mammal hunting, whaling,
  fishing and trade, with reindeer in the tundra (`rw:Pomorye [https://en.wikipedia.org/wiki/Pomors]`); the Nenets
  live by reindeer herding and hunting, migrating with the herds (`rw:Nenets [https://en.wikipedia.org/wiki/Nenets_people]`).
- **Zorn Uzkul analogue: a cold high plateau.** The Changtang: over 4,500 m, about 100 mm of precipitation, mostly
  "too inhospitable for farming", inhabited by nomadic herders who trade wool, salt and stock for grain.
  `rw:Changtang [https://en.wikipedia.org/wiki/Changtang]`

### 1.3 Vanilla's own numbers for the analogue

| vanilla state | class (`vanilla_state_climate_classes.csv`) | arable | subsistence | crops | fishing / whaling caps |
|---|---|---|---|---|---|
| STATE_WESTERN_NORWAY | highland_alpine (manual: fjord) | 20 | farm | rye_farm, livestock_ranch | 15 / 0 |
| STATE_EASTERN_NORWAY | boreal_forest | 20 | farm | rye_farm, livestock_ranch | 5 / 0 |
| STATE_NORTHERN_NORWAY | arctic_boreal_coast | 20 | pasture | livestock_ranch | 10 / 10 |
| STATE_NORRLAND | boreal_forest | 22 | farm | livestock_ranch | 12 / 0 |
| STATE_SVEALAND | boreal_forest | 30 | pasture | rye_farm, livestock_ranch | 11 / 0 |
| STATE_OULU | boreal_forest | 8 | farm | livestock_ranch | 10 / 0 |
| STATE_KOLA | boreal_forest | 2 | farm | livestock_ranch | 10 / 0 |
| STATE_ARKHANGELSK | boreal_forest | 15 | farm | rye_farm, livestock_ranch | 10 / 0 |
| STATE_NENETSIA | arctic_boreal_coast | 5 | pasture | livestock_ranch | 12 / 0 |
| STATE_ICELAND | arctic_boreal_coast | 5 | fishing_village | rye_farm, livestock_ranch | 3 / 5 |
| STATE_GREENLAND | arctic_boreal_coast | 3 | fishing_village | livestock_ranch | 3 / 5 |
| STATE_KAMCHATKA | arctic_boreal_coast | 6 | fishing_village | livestock_ranch | 21 / 11 |
| STATE_OKHOTSK | arctic_boreal_coast | 2 | fishing_village | livestock_ranch | 10 / 5 |
| STATE_ALAND | (fishing village) | 2 | fishing_village | rye_farm, livestock_ranch | - |
| STATE_OB | arctic_boreal_coast | 2 | pasture | livestock_ranch | 0 / 0 |

Which of them use fishing villages: in Scandinavia only **Iceland, Greenland and Aland**. Vanilla's three Norwegian
states do **not**: Western and Eastern Norway are `farm`, Northern Norway is `pasture`. Sweden and Finland are `farm`
(Svealand `pasture`). The other arctic fishing villages are Kamchatka and Okhotsk.

Calibration that matters for the rows: all Norway is 60 arable on about 385,000 km2, 0.16 per 1,000 km2. The world
boreal class runs 0.24 per 1,000 km2 (table 4.4) and the arctic class 0.01. So **per km2, vanilla Norway sits at
about two thirds of typical boreal land**, which is one fertility step down (x0.67); and typical arctic-class land
is effectively zero arable (0.06 per 1,000 px: a 3,000 px Norscan state reads 0.2 before scaling).

**A projection effect the model owner should know about (my arithmetic, not measured by a script).** The model
multiplies pixels by a per-pixel density. On the Miller canvas a pixel is `23.9 x cos(lat) x cos(0.8 lat)` km2: 9.5
km2 at 56 N (where vanilla's boreal class mostly lives; the class tables give 2.12 per 1,000 px against 0.24 per
1,000 km2, so 8.8 km2 per px on average), but 7.3 at 62 N, 6.4 at 64.5 N and 5.2 at 68 N. A Norscan pixel is
therefore about 30 to 40 % smaller than the pixel the density was measured on, and the same class gives Norsca
that much more arable per km2 than it gives vanilla's boreal belt. Per pixel, vanilla Norway (60 arable on roughly
60,000 px) is 1.0 per 1,000 px, 0.47 of the boreal density, which is **two** steps down (x0.45), not one. My rows
use step -1 as the Norscan coastal default (the per-km2 reading, and what a latitude-corrected model would want);
if the model stays per-pixel with no latitude term, -2 reproduces vanilla Norway. Open question 2.

### 1.4 Where canon and analogue disagree, and what I follow

1. **Fishing village against vanilla's farm.** Vanilla gives the Norwegian coast `farm`. Canon says the Norse eat
   fish and game and treat the few fields as a summer supplement, name fishing first for the Bjornlings, and make
   whaling the one honoured non-warrior trade. I follow canon: every coastal Norscan-tribe state takes
   `fishing_village`, including the boreal ones where the model's default would be `farm`. The real 19th-century
   coast agrees with canon here (fisher-farmers, grain imported), so vanilla is the outlier, not the lore.
2. **Harsher than Norway.** Canon is harsher than the analogue (ice over the northern half, Chaos storms, fields
   worked six months). The analogue already costs one step; I do not stack a second one on the southern coast
   without place-specific text, and the northern half falls to the arctic class on its own.
3. **Norse Dwarfs grow grain.** The standing ruling (holds herd, except Karak Izor, Karak Azgaraz, Kraka Drak) holds
   for Kraka Drak and is contradicted for Kraka Dorden and Kraka Ornsmotek, whose dependent settlements produce grain
   in the same gazetteer. See those entries and open question 1.
4. **Troll Country reads as forest.** The layer reads boreal forest (Dc 100 %); canon says steppe-to-tundra with no
   farming. Canon wins: arctic class, pasture.
5. **Zorn Uzkul reads as forest.** The layer reads boreal forest; canon says barren rock plateau. Canon wins.

## 2. Per-state entries (file order)

Reading the entries: "layer" is `mapgen/derived/state_climate_index.json` (Koppen shares) mapped by the brief's rule
(Dc boreal_forest; Df temperate_forest_hill; ET at or above 60 N and EF arctic_boreal_coast; BSk steppe). Every state
in this file lies north of 59 N; only the Zorn Uzkul group dips below 60 N. "px" is land pixels from the same index.
Owner tags are from `mapgen/derived/state_ownership.json`. Hub names marked TWW come from the TWW3 Old World mod
region table (`cr_oldworld_campaign/...` in `hub_worksheet.json`): a lead to where the map-maker put a canon place,
not canon evidence.

Shared shorthand used below:

- **Coast default (Norscan)** = `boreal_forest`, step -1, `building_subsistence_fishing_village`, crops
  `building_livestock_ranch building_rye_farm`. Basis: realm canon (few fields worked six months; fish, whale and
  game are the diet; section 1.1) plus the Norway analogue (3 % farmed, fisher-farmers, oats and barley; section
  1.2). `rye_farm` is vanilla's cold-grain building and stands for barley and oats, as it does in vanilla Norway.
  Livestock first because the analogue's farming was stock-and-hay first and canon names cattle, never a grain.
- **Mountain default (Norscan)** = `arctic_boreal_coast`, step 0, `building_subsistence_pasture`, crops
  `building_livestock_ranch`. Basis: the layer reads tundra and ice; canon has the interior hunted for meat and
  fur, with forest only on sheltered slopes; the analogue is the Norwegian fjell (seter dairying, Sami reindeer).
  Pasture's basket (meat, hides-as-fabric, a quarter of a farm's grain) is the nearest of the five to a hunting and
  herding upland. This matches the model's own default for inland arctic land.
- **Far-north coast default** = `arctic_boreal_coast`, step 0, `building_subsistence_fishing_village`, crops
  `building_livestock_ranch`. This is the model's own default for coastal arctic land; canon and vanilla (Iceland,
  Greenland, Northern Norway's crop list) both support it.

### STATE_NORTH_NORSE_COAST — North Norse Coast (SOR; 1,133 px; 65.9 N; coastal)
- **Identity.** North-west coast, facing the Sea of Chaos. Name has no worksheet source (Chris's); all five hubs
  are invented. Owner Sortsvinaer, a canon tribe "living off the northern coast" and devoted to Slaanesh
  (`lex:Sortsvinaer [Liber Chaotica: Slaanesh]`). Confidence in the place: medium; no canon place maps to it.
- **Canon.** No canon land-use text found for this coast. Realm canon applies.
- **Analogue.** Nordland coast of Norway at the same latitude: fisher-farmers, barley and oats ripen, grain
  imported. `vanilla:STATE_NORTHERN_NORWAY arable 20, pasture, livestock_ranch`; `vanilla:STATE_WESTERN_NORWAY
  arable 20, farm, rye_farm livestock_ranch`.
- **Layer.** Dc 85 %, Df 11 %, ET 4 %: boreal_forest.
- **Proposal.** Coast default (boreal_forest, -1, fishing village, livestock + rye). Agrees with the layer's class;
  changes the subsistence from the boreal default `farm` to fishing village. **Tier B.**

### STATE_FJORD_COAST — Fjord Coast (GRA 16 provinces / SKA 7; 4,045 px; 67.7 N; coastal)
- **Identity.** The north coast between the Graeling and Skaeling holdings of the mod; hubs all invented. A
  descriptive name (fjords), no canon place. The Graelings are canon as the tribe north of the Bjornlings and their
  rivals at sea (`lex:Bjornling#Relations [Sea of Claws p. 59]`).
- **Canon.** None for this coast. Realm canon: the northern tribes live nearest the Wastes; ice covers most of the
  northern half of the country (`fandom:Norsca#Geography [Tome of Corruption pp. 136-141]`).
- **Analogue.** Troms at 68-69 N: barley and rye reach their polar limit at 69-70 N (`rw:Norway [Paris 1900
  publication]`), and the coast lived on cod and imported Russian flour (`rw:Northern Norway [Pomor trade]`).
- **Layer.** Dc 80 %, ET 20 %: boreal_forest (a warm-current reading at a very high latitude).
- **Proposal.** `boreal_forest`, **step -2**, fishing village, livestock + rye. The extra step over the coast
  default is for latitude: this is at the analogue's grain limit and inside canon's ice-bound northern half.
  **Tier B.**

### STATE_WEST_HELSPIRE_MOUNTAINS — West Helspire Mountains (owner split or none in the index; 1,391 px; 64.9 N; inland; 5 of 11 provinces impassable)
- **Identity.** Western block of the range behind the Bjornling and Graeling coasts. Hubs Helspire Camp and
  Crooktail Peak are TWW names. Fandom's Bjornling article, from Sea of Claws, speaks of "the valleys of the
  Helspire Mountains" as raided Bjornling country, so the range name is canon (WFRP 4e).
- **Canon.** Graeling raids strike Bjornling coastal villages and the valleys of the Helspire Mountains
  (`fandom:Bjornlings#Relations [Sea of Claws pp. 59-64]`): the valleys are settled. No crop or herd named.
- **Analogue.** Norwegian fjell: seter dairying in summer, reindeer further north. `vanilla:STATE_NORTHERN_NORWAY
  pasture`.
- **Layer.** ET 82 %, EF 17 %: arctic_boreal_coast; inland, so pasture.
- **Proposal.** Mountain default. Agrees with the layer. **Tier B.**

### STATE_ULFWRENAR_COAST — Ulfwrenar Coast (SAR; 2,325 px; 62.5 N; coastal)
- **Identity.** South coast on the Sea of Claws. Hubs Aarvik, Ulfennik and Skapa Fjord are canon names placed by
  the TWW table: Ulfennik and Aarvik are coastal towns razed from Ostland in 2513 IC, so standing in 2502
  (`fandom:Ulfennik [Warhammer Rulebook 8e pp. 452-454]`; `lex:Norsca#Age of Karl Franz [same]`); Skapa Fjord is
  where the Ravnsvake fleet beat a Norse fleet in 2302 (`lex:Kraka_Ravnsvake#History [Sea of Claws pp. 6-7]`).
  "Ulfwrenar" echoes the ulfwerenar (were-warriors). Confidence: good that this is the raided south coast opposite
  Ostland.
- **Canon.** Towns and villages on the coast, no land-use text for them. Realm canon; the Skaeling Coast text
  (fish, whales, fir in sheltered valleys) describes this same shore (`lex:Skaeling_Coast [Sea of Claws p. 48]`).
- **Analogue.** South-west Norway. `vanilla:STATE_WESTERN_NORWAY arable 20, farm, rye_farm livestock_ranch, fishing
  cap 15`.
- **Layer.** Dc 85 %, ET 11 %, Df 5 %: boreal_forest.
- **Proposal.** Coast default. **Tier B.**

### STATE_CLAW_COAST — Claw Coast (SNA; 1,251 px; 63.1 N; **inland**, 4 of 8 provinces impassable)
- **Identity.** Uncertain. The name says coast but the drawn state has no port and no sea exit; it sits in the
  mountains behind the Mermedus Coast. Hubs Jorundr, Black Iron Fort and Baga Yar's Fortress are TWW placements;
  Baga Yar's daemon fortress is canon to the Skaeling lands, destroyed by Wulfrik
  (`fandom:Norsca#Landmarks [Wulfrik, novel]`).
- **Canon.** No canon land-use text found.
- **Analogue.** Norwegian fjell.
- **Layer.** ET 74 %, Dc 13 %, EF 12 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** Mountain default. Agrees with the layer. **Tier C** (identity uncertain; analogue only).

### STATE_VANNHEIM_MOUNTAINS — Vannheim Mountains (BAE; 1,858 px; 63.1 N; inland)
- **Identity.** The Vanaheim Mountains of the Old World map; hub Kronfjall is the Dragon Ogre peak of the Bjornling
  Coast (`lex:Bjornling_Coast [Sea of Claws pp. 58-59]`). Confidence: good.
- **Canon.** Snow-capped all year; their beasts are hunted by the tribes for meat and fur
  (`fandom:Vanaheim Mountains [Warhammer: The Old World website, interactive map]`).
- **Analogue.** Norwegian fjell; hunting and summer grazing.
- **Layer.** ET 59 %, Dc 24 %, EF 16 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** Mountain default. Agrees with the layer. **Tier A** (range named, use stated: hunted, not farmed).

### STATE_GLOOMWRACK_COAST — Gloomwrack Coast (BJO; 4,454 px; 62.7 N; coastal)
- **Identity.** The Bjornling Coast, west end of Norsca where the Sea of Chaos meets the Sea of Claws. Hubs
  Eyristaad, Oseberg and Troll Fjord: Eyristaad (Eyri Goldfinger's villages) and Oseberg (Erik the Lost's home
  port) are canon Bjornling places (`lex:Bjornling_Coast`; `lex:Bjornling#Notable [Sea of Claws pp. 58-59]`).
  Fandom names the "Gloomwrack Strait" between this coast and Albion (`fandom:Bjornlings [Sea of Claws pp. 59-64]`).
  Confidence: high.
- **Canon.** The Bjornlings live by fishing, raiding and trade (`lex:Bjornling#lead [Sea of Claws pp. 58-62]`).
  Settlements cling to cliffs and fjords; the country is as mountainous and harsh as the rest. On Bragnir, a hilly
  island close inshore, the valleys are unusually fertile for Norsca, perhaps because thralls manure the crops with
  kelp; Fjirgard trades furs (`fandom:Bjornlings#Geography [Sea of Claws pp. 59-64]`).
- **Analogue.** Outer coast of western Norway and the Hebrides (seaweed manuring of small plots is the same
  practice). `vanilla:STATE_WESTERN_NORWAY arable 20, farm`; `vanilla:STATE_HIGHLANDS arable 30, farm, rye_farm
  livestock_ranch, fishing 14, whaling 6`.
- **Layer.** Dc 50 %, Cfb 24 %, ET 17 %, Df 9 %: boreal_forest dominant, a third temperate.
- **Proposal.** `boreal_forest`, **step 0**, fishing village, livestock + rye. Step 0 rather than the coast
  default's -1: the one canon statement of good cropland in Norsca is here, and the layer reads a third of it as
  temperate. **Tier A.**

### STATE_ELDAGRIMM_GULF — Eldagrimm Gulf (BAE; 2,705 px; 61.3 N; coastal)
- **Identity.** Skjold, the Bjornling capital, stands on a clifftop "on the Eldagrimm Gulf"
  (`lex:Skjold [Sea of Claws pp. 60-62]`); hub Traktatsey is where the treaty of 765 IC was signed. Confidence:
  high. (The mod gives the state to the Baersonlings; that is an ownership matter, not a land-use one.)
- **Canon.** Skjold lives on plunder and trade; wharves, a master shipwright, a meadhall; no fields are described
  (`fandom:Skjold [Sea of Claws pp. 60-63]`). Bjornling canon as above.
- **Analogue.** The Norwegian south-west (Jaeren, Ryfylke): the mildest corner, still fisher-farmers.
- **Layer.** Df 44 %, Dc 27 %, Cfb 23 %, ET 6 %: **temperate_forest_hill** dominant (15.5 per 1,000 px).
- **Proposal.** `boreal_forest`, **step 0**, fishing village, livestock + rye. A class change down from the layer:
  nothing in canon supports mixed-forest farm country anywhere in Norsca, and the Bjornling Coast is called as
  harsh as the rest. Step 0 (not -1) because it is the mildest shore the realm has. **Tier A.**

### STATE_ZORN_UZKUL — Zorn Uzkul (UZK; 2,050 px; 61.0 N; coastal)
- **Identity.** The Great Skull Land with the Chaos Dwarf port of Uzkulak (hub), which lies "within Zorn Uzkul",
  at the mouth of the underground canal from the River Ruin (`lex:Uzkulak [Tamurkhan pp. 164-165; White Dwarf
  Presents: Chaos Dwarfs p. 8]`). Confidence: high. Canon files it under the Dark Lands; the mod draws it in this
  file.
- **Canon.** A vast plateau of barren rock to the horizon under thin, cold air (`lex:Dark_Lands#Zorn Uzkul
  [Warhammer Armies: Orcs & Goblins]`); frigid, dusty, bone-strewn, mineral-rich (`fandom:Zorn Uzkul [Tamurkhan
  pp. 164-165]`). No farming, herding or food text. Uzkulak is a slave port and garrison.
- **Analogue.** The Changtang: too high and cold to farm, nomad herders only. `vanilla:STATE_NGARI arable 60,
  pasture, livestock_ranch` (a far larger state); `vanilla:STATE_ALTAI arable 10, pasture, livestock_ranch`.
- **Layer.** Dc 70 %, ET 30 %: boreal_forest. `climate_lore.json`'s Dark Lands patch explicitly leaves "the tundra
  around Zorn Uzkul" physical.
- **Proposal.** `open_desert`, step 0, pasture, livestock only. Canon rules out forest; "barren rock" and "dusty"
  describe a cold desert, which in the vocabulary is `open_desert` (0.99 per 1,000 px, pasture by default). I do
  not take the earlier `highland_alpine` (DL-03): that class is calibrated on farmed mountain valleys (Tyrol,
  Switzerland) at five times the density. **Tier A.**

### STATE_SKULL_ROAD — Skull Road (UZK; 4,267 px; 58.5 N; inland)
- **Identity.** Named for the Road of Skulls, which runs from Kislev through the High Pass into Zorn Uzkul and on
  south of Uzkulak (`fandom:Zorn Uzkul [White Dwarf Presents: Chaos Dwarfs p. 6]`; `lex:High_Pass [Realm of the Ice
  Queen p. 7]`). Hubs Uzkulany and Ozergrany are TWW names. So: the southern Zorn Uzkul plateau the road crosses.
  Confidence: medium.
- **Canon.** Zorn Uzkul's text (above) covers it; nothing place-specific.
- **Analogue.** Cold plateau, as above.
- **Layer.** ET 42 %, Dc 37 %, BSk 19 %; below 60 N the ET share maps to highland_alpine.
- **Proposal.** `open_desert`, step 0, pasture, livestock only, for the same reason as Zorn Uzkul. **Tier B.**

### STATE_BELYEROVOTA — Belyerovota (unowned; 1,490 px; 59.7 N; inland; 3 of 9 provinces impassable)
- **Identity.** The High Pass, "Belyevorota" in Kislevarin (Lexicanum spells it Belyevobota from the Old World
  map): the northernmost pass over the Worlds Edge Mountains, on the Road of Skulls (`lex:High_Pass [Realm of the
  Ice Queen p. 7]`). Hubs are TWW. Confidence: high.
- **Canon.** Jagged snowbound peaks, great glaciers, cliffs; snow that rarely melts even in summer; blizzards and
  avalanches; sabretusks, wolves and yhetees (`fandom:High Pass [Realm of the Ice Queen p. 11]`).
- **Analogue.** A glaciated high pass; no settled agriculture.
- **Layer.** ET 88 %; just south of 60 N, so the rule maps it to **highland_alpine** (5.3 per 1,000 px).
- **Proposal.** `arctic_boreal_coast`, step 0, pasture, livestock only. Canon's permanent snow makes this the
  lowest class the vocabulary has; the 60 N cut-off is what makes the layer read it as an alpine valley state.
  **Tier A.**

### STATE_GOROMADNY_COAST — Goromadny Coast (URS; 3,976 px; 61.9 N; coastal)
- **Identity.** East-coast Norsca under the Goromadny range. Hubs Vinnskor, Drergan Mort, Keep of Asavar Kul and
  Temple of Heimkel are TWW placements of canon names: Vinnskor is the Baersonling capital village
  (`fandom:Vinnskor`), the Ice Field of Drergan Mort is where the Baersonlings fought the Kurgan
  (`fandom:Norsca#Geography [Tome of Corruption pp. 136-141]`). Confidence that Vinnskor's description belongs
  here: medium (hub placement is the map-maker's).
- **Canon.** At Vinnskor farmers and herdsmen go out at dawn to tend the fields and shaggy cattle; a mountain
  stream supplies water; thralls fell timber (`fandom:Vinnskor [Palace of the Plague Lord, novel, ch. 3]`). The
  Baersonlings have freeholders, thralls and cattle that the Aeslings steal, and fishing villages
  (`fandom:Aeslings`, `fandom:Baersonlings [same novel, ch. 1, 11]`). Source grade: a Black Library novel reported
  by Fandom; no Lexicanum page exists for the tribe.
- **Analogue.** Inner fjord and valley farms of Trondelag: mixed stock and barley.
  `vanilla:STATE_EASTERN_NORWAY arable 20, farm, rye_farm livestock_ranch`.
- **Layer.** Dc 97 %: boreal_forest.
- **Proposal.** `boreal_forest`, **step 0**, `building_subsistence_farm`, livestock + rye. The one Norscan place
  whose canon picture is fields and cattle first; so it keeps the boreal default (`farm`) and loses the realm's
  -1. **Tier A** (novel-grade).

### STATE_TROLL_COUNTRY — Troll Country (TRO; 3,472 px; 62.3 N; coastal; river Tobol)
- **Identity.** Troll Country by name; hub Leblya is its largest Kislevite settlement, a stanitsa built round an
  old mound (`fandom:Leblya [Realm of the Ice Queen p. 60]`). Confidence: high.
- **Canon.** No farming is possible; steppe turning to tundra; frost through spring and autumn; very little
  vegetation; a few scrawny trees in the south (`fandom:Troll Country [Realm of the Ice Queen pp. 59-60]`). The
  people are nomads following game herds; reindeer graze lichen and summer grass; the Tobol Delta is a huge salt
  marsh (`lex:Troll_Country [Sea of Claws pp. 34-37]`). Ungol krugs follow their domesticated herds from pasture
  to pasture (`fandom:Steppes Nomad [Realm of the Ice Queen p. 105]`).
- **Analogue.** The Russian Arctic coast: Nenets reindeer nomads, Pomor sea-hunters. `vanilla:STATE_NENETSIA arable
  5, pasture, livestock_ranch`; `vanilla:STATE_KOLA arable 2, farm, livestock_ranch`.
- **Layer.** Dc 100 %: boreal_forest (farm, livestock + rye).
- **Proposal.** `arctic_boreal_coast`, step 0, **pasture** (not the coastal-arctic default of fishing village),
  livestock only. Canon says in terms that it cannot be farmed and that its people are herders; the vanilla tundra
  states give the size (2 to 5 arable). **Tier A.** Confirms NK-02's direction and goes further (a class change,
  not a step down).

### STATE_FLESHWARREN — Fleshwarren (MDR; 550 px; 62.0 N; inland)
- **Identity.** Invented name (worksheet); one of three small states carrying Clan Moulder's Hell Pit. No hubs.
- **Canon.** Hell Pit's text only: barren land around the pit, scoured by packmasters for beasts
  (`lex:Hell_Pit#Overview [Skaven 7e p. 15; White Dwarf 311]`). No canon text on what the clan grows or eats was
  found in the Hell Pit or Clan Moulder pages of either wiki.
- **Analogue.** None useful; tundra mountain.
- **Layer.** ET 100 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** Mountain-default values (arctic, 0, pasture, livestock only). Agrees with the layer. Pasture suits
  a clan whose whole economy is breeding beasts. **Tier B** (reached through Hell Pit).

### STATE_FROZEN_COAST — Frozen Coast (URS; 2,622 px; 63.2 N; coastal)
- **Identity.** Hubs Hall of Urslo, Ursfjord and Frozen Landing. Ursfjord, on the Frozen Sea, holds the great hall
  of Urslo, seat of Beorg Bearstruck's Bearmen (`fandom:Bearmen of Urslo [Dogs of War 5e pp. 50-51]`;
  `lex:Frozen_Sea [Old World website map]` lists Ursfjord). Confidence: good.
- **Canon.** Ursfjord lies in "the frozen north of eastern Norsca"; the hall is built of great timbers from mighty
  trees. No fields or herds. The two wikis differ on the sea: Lexicanum calls the Frozen Sea a cold body of water
  with fjords and a new Norse Dwarf harbour built to trade across it; Fandom (from a novel) describes it frozen
  solid, with seal and ice-crab the only food. I follow Lexicanum for 2502 (open water at least seasonally).
- **Analogue.** Inner Finnmark and the White Sea shore. `vanilla:STATE_ARKHANGELSK arable 15, farm, rye_farm
  livestock_ranch, fishing 10`.
- **Layer.** Dc 88 %, ET 12 %: boreal_forest.
- **Proposal.** Coast default. **Tier B.**

### STATE_TALDURSFJORD — Taldursfjord (KVE; 3,848 px; 65.6 N; coastal)
- **Identity.** Taldursfjord is the fjord of the Frozen Sea that Kraka Dorden overlooks (`lex:Kraka_Dorden [Lords of
  Stone and Steel p. 20]`; `lex:Frozen_Sea [Old World website map]`). Hubs Drakefjord and Skraevold are TWW
  placements of canon names; Skraevold is the southernmost Aesling village (`fandom:Skraevold`). Confidence: good
  for the fjord, medium for Skraevold sitting here.
- **Canon.** At Skraevold the Aeslings keep no thralls and take pride in working their own fields, quarrying their
  own stone and felling their own timber; hens are fed in the lanes; a forest lies half a day to the south-east
  (`fandom:Skraevold [Palace of the Plague Lord, novel, ch. 1]`). Aesling land borders the Frozen Sea.
- **Analogue.** Inner Troms and Finnmark fjords at 66 to 70 N: barley and potatoes at the fjord heads, fish outside.
  `vanilla:STATE_NORTHERN_NORWAY arable 20, pasture, livestock_ranch, fishing 10, whaling 10`.
- **Layer.** ET 65 %, Dc 33 %, EF 2 %: arctic_boreal_coast; coastal, fishing village.
- **Proposal.** `arctic_boreal_coast`, **step +1**, fishing village, livestock + rye. The class and subsistence are
  the layer's; the step and the added `rye_farm` record canon's worked fields. Note that in the arctic class a step
  changes almost nothing in the number; what keeps arable here is the layer's own one-third boreal share, which a
  flat class row would erase (open question 3). **Tier B** (novel-grade, hub placement by the map-maker).

### STATE_KRAKEN_COAST — Kraken Coast (AES; 4,606 px; 67.8 N; coastal)
- **Identity.** North coast on the Kraken Sea; all hubs invented. Owner Aeslings, whom the registry itself marks
  "non-canon" for this seat. The Kraken Sea is "north of Norsca" (`lex:Kraken_Sea`, sourced there only to Total War:
  Warhammer II, so not canon evidence). Confidence in a canon identity: low.
- **Canon.** None for this coast. Realm canon: the northern tribes (Aesling, Graeling, Varg) live nearest the
  Wastes; ice covers most of the north.
- **Analogue.** Finnmark's outer coast: fish, seal, a cow and some sheep, no grain.
  `vanilla:STATE_NORTHERN_NORWAY`; `vanilla:STATE_ICELAND arable 5, fishing_village, rye_farm livestock_ranch`.
- **Layer.** ET 95 %, EF 5 %: arctic_boreal_coast; coastal, fishing village.
- **Proposal.** Far-north coast default. Agrees with the layer. **Tier B** (realm canon), identity inferred.

### STATE_MOUNTAINS_OF_HEL — Mountains of Hel (AES; 2,057 px; 66.4 N; inland; 5 of 11 provinces impassable)
- **Identity.** High interior range. Hub Forbidden Citadel is a canon fortress "overlooking the Frozen Sea", long
  fought over by tribal chieftains (`fandom:Forbidden Citadel (Norsca) [Old World website map]`). Fandom's Vargs
  page mentions Chaos-tainted Norse Dwarfs "from the Hel Peaks" (Archaon: Everchosen, novel). Confidence: medium.
- **Canon.** No land-use text.
- **Analogue.** Glaciated fjell.
- **Layer.** EF 55 %, ET 45 %: arctic_boreal_coast (more than half ice cap); inland, pasture.
- **Proposal.** Mountain default. Agrees with the layer. **Tier R.**

### STATE_GIANTHOME_MOUNTAINS — Gianthome Mountains (KRD; 554 px; 65.7 N; inland; 3 of 6 provinces impassable)
- **Identity.** The Giantshome (Grontklung) Mountains. Hubs Kraka Dorden and Grung Dobekzhulf: this state is the
  seat of **Kraka Dorden**, the second Norse Dwarf hold, north-west of Kraka Drak in the mountain above Taldursfjord
  (`lex:Kraka_Dorden [Dwarfs: Stone and Steel p. 42; Lords of Stone and Steel p. 20]`). It is owned by KRD (the
  registry has no Kraka Dorden tag). Confidence: high.
- **Canon.** The Giantshome range: rich iron, silver and gems, amber in the valleys, mountainous coasts under
  conifer forest rich in game, rivers and coastal waters full of fish; called a land of plenty
  (`fandom:Norse Dwarfs [Dwarfs: Stone and Steel p. 42]`). Kraka Dorden is known for furs, metalwork, iron, tin and
  quartz; its town Khazid Fneldruk (4,000 people) produces fur, grain and metal, and its mine Grung Dobekzhulf
  grain and metalwork (`lex:Khazid_Fneldruk`, `fandom:Kraka Dorden [Lords of Stone and Steel p. 24]`).
- **Analogue.** A forested mountain coast at 65 N (Helgeland, Vasterbotten): small barley fields, stock, furs.
  `vanilla:STATE_NORRLAND arable 22, farm, livestock_ranch`.
- **Layer.** ET 86 %, EF 14 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** `boreal_forest`, step 0, **`building_subsistence_farm`**, livestock + rye. Class change up from
  the layer on canon's conifer forest; `farm` because two of the hold's three listed dependencies produce grain.
  This **contradicts the standing ruling** (dwarf holds herd, bar three named grain holds): see open question 1.
  With 554 px the number is small whatever the class. **Tier A.**

### STATE_BLACK_BLOOD_PASS — Black Blood Pass (KRV; 1,707 px; 63.6 N; coastal; 5 of 12 provinces impassable)
- **Identity.** Seat of **Kraka Ravnsvake** (hub "Kraka Ravnvake"), with its dependencies Grung Stekbrud and Khazid
  Bordkarag as hubs (`lex:Kraka_Ravnsvake#Subsidiary Settlements [Dwarfs: Stone and Steel, Gazetteer]`). The hold
  lies south-west of Kraka Drak above the Draksfjord and the River Dypvann. Black Blood Pass itself is a canon pass
  with Kislevite forts at its southern end (`fandom:Kislev#History [Realm of the Ice Queen pp. 16-21]`).
  Confidence: high for the hold.
- **Canon.** Exports metal and okrinaduraz stone; copper, iron, silver; home of the Norse Dwarf fleet (190
  warships); a brewing clan; trade with L'Anguille, Marienburg, Norden and Ulthuan; a riverport "in the forest to
  the west" (`lex:Kraka_Ravnsvake [Sea of Claws pp. 40-47; Lords of Stone and Steel p. 24]`). Khazid Bordkarag
  produces metal (`lex:Khazid_Bordkarag [Lords of Stone and Steel p. 24]`). **No grain, cheese or herd is listed
  for this hold's own lands** (Sjoktraken, which it took over, has grain but stands on the Draksfjord by Kraka
  Drak).
- **Analogue.** A mining and shipping fjord town fed by trade.
- **Layer.** ET 86 %, Dc 9 %, EF 5 %: arctic_boreal_coast; coastal, fishing village.
- **Proposal.** `arctic_boreal_coast`, step 0, **pasture**, livestock only. The standing dwarf ruling (holds herd)
  stands here because canon gives no grain; it replaces the layer's fishing village. A fishing village would also
  be defensible (the fleet, the fish-rich coast). **Tier B.**

### STATE_STUREN_RIDGE — Sturen Ridge (TRO; 3,586 px; 62.5 N; coastal)
- **Identity.** The Sturen Ridges, a high rocky relief in the centre of Troll Country; hub Dhazhyn is a Kislevite
  settlement of mostly Ungol people (`fandom:Troll Country#Notable Locations [Realm of the Ice Queen p. 45 map]`).
  Hubs Macadone and Fort Sturchod are TWW names. Confidence: high.
- **Canon.** Troll Country's text in full (no farming, herders, reindeer); nothing ridge-specific beyond "rocky".
- **Analogue.** As Troll Country. `vanilla:STATE_NENETSIA arable 5, pasture`.
- **Layer.** Dc 100 %: boreal_forest.
- **Proposal.** As STATE_TROLL_COUNTRY: `arctic_boreal_coast`, 0, pasture, livestock only. **Tier A** (named place
  inside Troll Country; the land-use text is the region's).

### STATE_TROLLHEIM_MOUNTAINS — Trollheim Mountains (HAS; 3,008 px; 65.7 N; inland; 4 of 13 provinces impassable)
- **Identity.** Central high range. Hub Black Gulch is a canon glacial valley whose tunnels shelter Skaven and
  worse (`fandom:Black Gulch [Old World website map]`); Crow Brethren Roost is a TWW name. "Trollheim" does not
  occur in either wiki. Confidence: low to medium.
- **Canon.** No land-use text.
- **Analogue.** Glaciated fjell.
- **Layer.** EF 67 %, ET 33 %: arctic_boreal_coast; two thirds ice cap.
- **Proposal.** Mountain default. Agrees with the layer. **Tier R.**

### STATE_ULFWRENAR_MOUNTAINS — Ulfwrenar Mountains (SNA; 1,969 px; 63.7 N; inland)
- **Identity.** Hubs Hall of Snaegr, Doom Keep, Vagr Lodge. The Hall of the Snaegr "lies in the land of the
  Skaelings" (`fandom:Norsca#Landmarks`); the Doomkeep is a Skaeling watchtower over the mountain pass in the
  centre of Norsca (`fandom:Doomkeep [Old World website map]`); the Snaegr are a Khornate Skaeling tribe
  (`lex:Snaegr [Hordes of Chaos 6e p. 9; Sea of Claws p. 52]`). Confidence: good.
- **Canon.** From the Doomkeep its Skaeling garrison goes out to hunt and raid. No fields or herds.
- **Analogue.** Fjell.
- **Layer.** EF 57 %, ET 43 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** Mountain default. Agrees with the layer. **Tier B.**

### STATE_BAY_OF_BLADES — Bay of Blades (SAR; 4,911 px; 64.3 N; coastal; 5 of 22 provinces impassable)
- **Identity.** The Bay of Blades, sacred duelling water of the Sarl and Skaeling (`lex:Troll_Country#Locations
  [Sea of Claws p. 36]`), with the Sarl town of Ormskaro and the fortress of Ormfell as hubs. Sea of Claws lists
  the bay under Troll Country; the mod draws it as the Sarl heartland of south-east Norsca. Confidence: high for
  the places.
- **Canon.** Ormskaro sits deep in a narrow fjord round a natural harbour: reavers' dragonships beside the boats
  of hunters and fishermen, whales hauled onto timber platforms and flensed for oil, animals loose in the lanes,
  thralls hauling nets (`fandom:Ormskaro [Wulfrik, novel, ch. 2]`). Few Sarl villages do not float timber down
  icy rivers to the shipyards (`fandom:Sarls [Palace of the Plague Lord, novel, ch. 10]`). The bay has a shingle
  beach, cliffs and a waterfall; green amber washes down from mountain forests (`fandom:Bay of Blades [Sea of
  Claws p. 36]`). Inland, fjords give way to frozen steppe where tribesmen hunt (`fandom:Norsca#Geography
  [Warriors of Chaos 8e p. 8]`).
- **Analogue.** Trondelag and Nordland: timber, cod, whale oil.
- **Layer.** BSk 36 %, Dc 27 %, ET 27 %, EF 11 %: **steppe** dominant, whose defaults are `farm` with wheat and
  vineyards.
- **Proposal.** `boreal_forest`, -1, fishing village, livestock + rye (the coast default). A class change from the
  layer: the dry patch is canon's cold hunting steppe, not wheat country, and the settled life is timber, whale and
  fish. The crop list matters most here: no `wheat_farm`, no `vineyard`. **Tier A.**

### STATE_NAGLFARI_MOUNTAINS — Naglfari Mountains (SKA; 2,894 px; 66.2 N; coastal; 5 of 15 provinces impassable)
- **Identity.** North-coast range. Hubs Naglheim and Naglfarling Keep are TWW names; "Naglfar" occurs in neither
  wiki. No canon place identified. Confidence: low.
- **Canon.** No canon land-use text found.
- **Analogue.** Lyngen and the Lofoten wall: ice-capped mountains straight out of the sea, people on the shore
  strip living by fish.
- **Layer.** ET 43 %, EF 35 %, Dc 23 %: arctic_boreal_coast; coastal, fishing village.
- **Proposal.** Far-north coast default. Agrees with the layer. **Tier R** (C on identity).

### STATE_NAGLFARI_COAST — Naglfari Coast (SKA; 6,018 px; 68.8 N; coastal)
- **Identity.** The largest state in the file, on the far north-west coast. Hubs Kin-Slayer Haven, Dragonbone,
  North Scourge Hold: TWW names (Fandom's "Kin-slayers" minor tribe has no GW citation). Owner Skaelings, marked
  non-canon for this seat in the registry; canon puts the Skaelings on the **south** coast
  (`fandom:Skaelings [Sea of Claws pp. 48-51]`). Confidence in a canon identity: low.
- **Canon.** None for this coast; realm canon for the ice-bound north.
- **Analogue.** Finnmark at 69 to 70 N: the very limit of barley; cod, seal and imported flour.
- **Layer.** Dc 76 %, ET 20 %, EF 4 %: boreal_forest at 68.8 N.
- **Proposal.** `boreal_forest`, **step -2**, fishing village, livestock + rye, as STATE_FJORD_COAST and for the
  same reason. I would not argue with `arctic_boreal_coast` here either; the layer's boreal reading this far north
  is the thing to look at on the climate render. **Tier B.**

### STATE_HELL_PIT_DEPTHS — Hell Pit Depths (MDR; 851 px; 61.9 N; inland)
- **Identity.** Invented name; the registry makes it Clan Moulder's capital state. No hubs.
- **Canon / analogue / layer.** As STATE_FLESHWARREN. ET 100 %.
- **Proposal.** `arctic_boreal_coast`, 0, pasture, livestock only. Agrees with the layer. **Tier B.**

### STATE_HELL_PIT — Hell Pit (MDR; 448 px; 62.5 N; inland)
- **Identity.** Hell Pit itself, "at the very northern edge of Troll Country" (`lex:Troll_Country#Locations`).
  Hubs are invented (Moulder's Warren, Breeding Pens). Confidence: high.
- **Canon.** A chasm in a snowy mountainside with volcanic pools; nine circles of cages, breeding pits and flesh
  laboratories; the land around is barren (`lex:Hell_Pit [Skaven 7e p. 15; White Dwarf 311]`). The clan hunts
  Troll Country for stock and mines warpstone (`fandom:Troll Country#Hell Pit Hunting Grounds`). Nothing on food.
- **Analogue.** None.
- **Layer.** ET 100 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** `arctic_boreal_coast`, 0, pasture, livestock only. Agrees with the layer and with NK-04's
  direction (the class there was `highland_alpine`; north of 60 N the layer's arctic reading is the better fit for
  a barren snowfield). If the Skaven dossier settles a different under-city subsistence for the race, it should
  carry here. **Tier A** for the place, with no food text.

### STATE_FORT_STRAGHOV — Fort Straghov (DOL; 4,326 px; 61.6 N; coastal)
- **Identity.** Uncertain. The name is a TWW region; "Straghov" in canon is the family of Ivan Straghov, a
  Kislevite march boyar guarding the northern border (`fandom:Kislev#Notable Kislevites`, from the Gotrek and Felix
  novels). The state lies east of Troll Country and Sturen Ridge on the same shore, below Hell Pit. I read it as
  the eastern Troll Country march. Confidence: low.
- **Canon.** No text for the place. Troll Country's regional text, by position.
- **Analogue.** As Troll Country.
- **Layer.** Dc 88 %, ET 12 %: boreal_forest.
- **Proposal.** As STATE_TROLL_COUNTRY: `arctic_boreal_coast`, 0, pasture, livestock only. **Tier C.** If Chris
  holds this to be Kislev's own northern march rather than Troll Country, the Kislev dossier's far-north class
  should apply instead.

### STATE_HELSPIRE_COAST — Helspire Coast (SOR; 2,815 px; 66.6 N; coastal)
- **Identity.** North-west coast under the Helspire range. Hub "Sortsvinaer" (the tribe's seat) and Foul Fortress
  are TWW placements. Sortsvinaer: a canon northern-coast tribe (`lex:Sortsvinaer [Liber Chaotica: Slaanesh]`).
  Confidence: medium.
- **Canon.** None beyond the tribe living off the northern coast.
- **Analogue.** Nordland and Troms coast.
- **Layer.** Dc 88 %, ET 12 %: boreal_forest.
- **Proposal.** Coast default. **Tier B.**

### STATE_NORSVEG_PLAIN — Norsveg Plain (GRA; 3,159 px; 66.2 N; coastal)
- **Identity.** North-west coast lowland. Hubs Graeling Moot and Stormraven's Roost are TWW names (Fandom's infobox
  cites "Graeling Moot" to Total War; "Norsveg" occurs in neither wiki). The Graelings are canon: the tribe north
  of the Bjornlings, fiercer raiders and their rivals at sea (`lex:Bjornling#Relations [Sea of Claws p. 59]`),
  slavers who sell to and raid the Dark Elves (`fandom:Norsca#Crafts and Trade [Warriors of Chaos 7e pp. 38-41]`).
  Confidence: medium (right tribe, right side of the peninsula; the plain itself is the map-maker's).
- **Canon.** No land-use text. A sea-raiding tribe.
- **Analogue.** Nordland's strandflat: the narrow coastal shelf that held almost all of north Norway's farms.
- **Layer.** Dc 74 %, ET 26 %: boreal_forest.
- **Proposal.** Coast default. I did not raise the step on the word "plain": no source says it is farmed.
  **Tier B.**

### STATE_HELSPIRE_MOUNTAINS — Helspire Mountains (GRA; 1,796 px; 64.7 N; inland)
- **Identity.** The Helspire Mountains named in Sea of Claws (see West Helspire). Hubs Beast-Flayer Lodge and
  Stoneclaw Mountain are TWW names. Fandom also has a volcano "Mount Hellspire" in Norsca, visited for obsidian
  (`fandom:Mount Hellspire [Old World website map]`); whether it is the same feature is not stated.
- **Canon.** Settled valleys raided by the Graelings (`fandom:Bjornlings#Relations [Sea of Claws pp. 59-64]`).
- **Analogue.** Fjell with seter valleys.
- **Layer.** ET 66 %, EF 34 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** Mountain default. Agrees with the layer. **Tier B.**

### STATE_BJORNLING_S_GATHERING — Bjornling's Gathering (BJO; 1,685 px; 64.7 N; coastal)
- **Identity.** TWW region name; no hubs. The registry makes it the Bjornling capital state, though canon's
  Bjornling capital, Skjold, is in STATE_ELDAGRIMM_GULF. It is the northern end of the Bjornling Coast, where the
  tribe meets the Graelings. Confidence: medium.
- **Canon.** Bjornling canon (fishing, raiding, trade; coastal villages raided from the north). An island town,
  Horvenghaast, lies ten miles off the northern point of Bjornling country (`fandom:Bjornlings#Geography [Sea of
  Claws pp. 59-64]`). No fields named.
- **Analogue.** More og Romsdal coast. `vanilla:STATE_WESTERN_NORWAY`.
- **Layer.** Dc 71 %, Df 26 %, ET 3 %: boreal_forest.
- **Proposal.** Coast default. **Tier B.**

### STATE_STROVENGAARD — Strovengaard (BAE; 3,639 px; 61.2 N; coastal)
- **Identity.** TWW region name carrying a canon one: the great Hall of Strovengaard is the seat of Egil Styrbjorn's
  Skaelings (`fandom:Norsca#Landmarks`; `fandom:Egil Styrbjorn [Knight of the Realm, novel]`). South coast,
  between the Eldagrimm Gulf and the Mermedus Coast. The mod's owner is the Baersonlings (registry: non-canon
  seat). Confidence: medium.
- **Canon.** A raiding jarldom; no land-use text for it. The Skaeling Coast picture applies: cold but "not
  sterile", fir and pine on sheltered valleys and south slopes, fishing boats crewed by warriors, few industries
  beyond weapons, leather and textiles (`fandom:Skaelings#Skaeling Coast [Sea of Claws pp. 48-49]`).
- **Analogue.** Sorlandet and Rogaland.
- **Layer.** Df 47 %, Dc 32 %, ET 14 %, Cfb 7 %: **temperate_forest_hill** dominant.
- **Proposal.** `boreal_forest`, step 0, fishing village, livestock + rye: the same class change and reasoning as
  STATE_ELDAGRIMM_GULF. **Tier B.**

### STATE_MERMEDUS_COAST — Mermedus Coast (SNA; 3,599 px; 61.6 N; coastal)
- **Identity.** The Skaeling Coast. Hub Temple of Mermedus: the temple is a rotting hulk in the Skaeling trading
  port of Kirkjugardur Langskipa (`lex:Kirkjugardur_Langskipa [Sea of Claws pp. 53-54]`); Mermedus is the Skaeling
  sea daemon under the Sea of Claws (`lex:Norsca#Religion`). Confidence: high.
- **Canon.** A coast of rocky islands, twisting fjords and cliffs; the sea full of fish, sharks and whales; fir
  forest in the sheltered valleys (`lex:Skaeling_Coast [Sea of Claws p. 48]`). The port has smokehouses,
  shipyards, warehouses and slave pens (`lex:Kirkjugardur_Langskipa`). Wild goats among the fauna; southern
  merchants come for rare timber, gold and weapons (`fandom:Skaelings [Sea of Claws pp. 48-49]`).
- **Analogue.** Western Norway. `vanilla:STATE_WESTERN_NORWAY arable 20, farm, rye_farm livestock_ranch, fishing
  15`.
- **Layer.** Dc 73 %, Df 20 %, ET 7 %: boreal_forest.
- **Proposal.** Coast default. **Tier A** (the coast's own text: sea first, forest second, no fields).

### STATE_CHAMON_DHAREK — Chamon Dharek (UNG; 3,349 px; 61.7 N; coastal)
- **Identity.** Chamon Dharek, the Kurgan grave mound in a hilly district north of the Tobol Delta, inside Troll
  Country (`lex:Troll_Country#Locations [Realm of the Ice Queen p. 60; Sea of Claws p. 36]`; `fandom:Chamon
  Dharek`). Confidence: high.
- **Canon.** Troll Country's text (no farming; herders). The mound's treasure is cursed and left alone; ringed by
  mummified horses.
- **Analogue.** As Troll Country.
- **Layer.** Dc 82 %, Df 13 %, ET 6 %: boreal_forest.
- **Proposal.** As STATE_TROLL_COUNTRY: `arctic_boreal_coast`, 0, pasture, livestock only. This is the southern,
  grassier end (canon: steppe in the south), so if any Troll Country state were to be read as `steppe` with
  pasture it is this one; I keep it with the others because the same source says of the whole region that it
  cannot be farmed. **Tier A.**

### STATE_VIDARHEIM — Vidarheim (KVE; 3,033 px; 66.8 N; coastal)
- **Identity.** TWW region name, no hubs, found in neither wiki. North-east coast on the Frozen Sea. Owner
  Kvellig, a canon tribe that hunts the Chaos Wastes in large parties for ivory, fur and bone and keeps a harbour
  fortress there (`fandom:Kvellig [Old World website map; Arcane Journal: Warriors of Chaos p. 8]`). Confidence in
  the place: low.
- **Canon.** None for the place. The owner is a hunting people, not farmers.
- **Analogue.** Varanger coast.
- **Layer.** ET 96 %, EF 4 %: arctic_boreal_coast; coastal, fishing village.
- **Proposal.** Far-north coast default. Agrees with the layer. **Tier C.**

### STATE_KRAKA_DRAK — Kraka Drak (KRD; 1,570 px; 65.1 N; coastal)
- **Identity.** Kraka Drak, largest and richest Norse Dwarf hold, near the coast with its harbour Sjoktraken on
  the Draksfjord (`lex:Kraka_Drak [Dwarfs: Stone and Steel p. 42; Lords of Stone and Steel p. 20]`). Worksheet
  source is Lexicanum. Confidence: high. Timeline note: the hold fell to the Aeslings in 2390 IC and is being
  resettled under King Thorgard by 2502-2512; the gazetteer figures are for 2512.
- **Canon.** The hold exports amber, **grain**, sapphires and silver; its village Khazid Ravik (3,600 people)
  produces cheese, fur, grain and wool; Sjoktraken (2,000) grain, amber and trade (`lex:Kraka_Drak#Trade`,
  `lex:Khazid_Ravik [Lords of Stone and Steel p. 24]`; `fandom:Kraka Ravnsvake [same]`). The surrounding
  Giantshome coast is conifer forest with fish-rich rivers (`fandom:Norse Dwarfs [Stone and Steel p. 42]`).
- **Analogue.** The best fjord-head farmland of the north (Trondelag, or Malselv in Troms).
  `vanilla:STATE_EASTERN_NORWAY arable 20, farm, rye_farm livestock_ranch`.
- **Layer.** Dc 53 %, ET 47 %: boreal_forest.
- **Proposal.** `boreal_forest`, **step +1**, `building_subsistence_farm`, crops `building_rye_farm
  building_livestock_ranch` (grain first: it is the export). Confirms the standing ruling and NK-05. The only
  state in the realm with a stated surplus. **Tier A.**

### STATE_BRENNUN_S_ENCAMPMENT — Brennun's Encampment (HAS; 2,282 px; 64.7 N; inland; 3 of 12 provinces impassable)
- **Identity.** TWW region name; "Brennuns" appear in Fandom's list of minor tribes with no citation. No hubs.
  Central high interior. Confidence: low.
- **Canon.** No canon land-use text found.
- **Analogue.** Fjell and ice cap.
- **Layer.** EF 51 %, ET 46 %, BSk 4 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** Mountain default. Agrees with the layer. **Tier C.**

### STATE_THORSHAFN — Thorshafn (HAS; 1,832 px; 64.0 N; coastal)
- **Identity.** TWW region name, found in neither wiki; no hubs. A short stretch of south-east coast between the
  Bay of Blades and Troll Country. Owner Hastlings, whose canon range is elsewhere: the blasted plains leading up
  to the northern Worlds Edge Mountains, where they are noted horsemen (`fandom:Hastlings [Arcane Journal:
  Warriors of Chaos p. 8]`). Confidence: low.
- **Canon.** None for the place.
- **Analogue.** Inner Trondelag coast.
- **Layer.** Dc 81 %, ET 13 %, BSk 7 %: boreal_forest.
- **Proposal.** Coast default. If Chris means this as the Hastlings' horse country, pasture would suit the owner
  better than a fishing village; the land itself gives no reason to choose. **Tier C.**

### STATE_MONOLITH_OF_INGVAR — Monolith of Ingvar (SKA; 2,917 px; 67.1 N; inland; 5 of 15 provinces impassable)
- **Identity.** TWW region name. Chaos monoliths are canon tribal markers (`fandom:Norsca#Landmarks [Liber
  Chaotica: Khorne]`), and Ingvar the Ravager is a Varg king in a novel (`fandom:Vargs [Archaon: Everchosen]`),
  but no "Monolith of Ingvar" is in either wiki. Northern interior. Confidence: low.
- **Canon.** No canon land-use text found.
- **Analogue.** Fjell.
- **Layer.** ET 68 %, EF 25 %, Dc 7 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** Mountain default. Agrees with the layer. **Tier C.**

### STATE_EAGLE_S_PEAK — Eagle's Peak (KOR; 1,176 px; 68.1 N; inland on the map)
- **Identity.** **Kraka Ornsmotek**, "Eagle's Peak Hold", the northernmost Norse Dwarf hold; all four hubs (Kazad
  Dumund, Kazad Grontunt, Khazid Skovekarag, Kraka Ornsmotek) are its canon settlements
  (`lex:Kraka_Ornsmotek [Dwarfs: Stone and Steel p. 42 and Gazetteer; Lords of Stone and Steel p. 20]`).
  Confidence: high. Canon sets it on a fjord shore with a new Frozen Harbour; the drawn state has no port.
- **Canon.** In the Jagged Tooth Mountains beside the Giantshome range, the most Giant- and Troll-ridden country
  known; the only substantial gold mine of the Norse Dwarfs, with diamonds and obsidian. The fort Kazad Dumund
  (about 360 people) specialises in producing **grain and cheese for the hold**; Khazid Skovekarag is a mining and
  hunting settlement (`fandom:Kraka Ornsmotek [Lords of Stone and Steel pp. 20, 24]`).
- **Analogue.** A mining town at 68 N fed by a home farm and a dairy: Finnmark's fjord-head barley and goats.
- **Layer.** ET 73 %, EF 15 %, Dc 12 %: arctic_boreal_coast; inland, pasture.
- **Proposal.** `arctic_boreal_coast`, **step +1**, pasture, livestock + rye. The class is the layer's (the land
  as a whole is tundra and ice); the step and the `rye_farm` record the one fort that grows grain. Pasture rather
  than farm because cheese stands beside the grain and the land is a class poorer than Kraka Dorden's; this is the
  weaker half of open question 1. **Tier A.**

### STATE_VARG_CAMP — Varg Camp (VAR; 3,131 px; 70.2 N; coastal)
- **Identity.** TWW region name; the northernmost state in the file. The Vargs are a canon northern tribe
  (`lex:Norsca#Tribes [Tome of Corruption pp. 136-144]`) on the north-central coast, said to have come west out of
  the Chaos Wastes (`fandom:Vargs [Games Day 2002: Hrothgar Daemonaxe pp. 1-3]`). Confidence: medium.
- **Canon.** None on land use. Among the tribes most given to slaughter.
- **Analogue.** North Cape and Svalbard waters: beyond the grain limit (barley's is 70 N), sealing, whaling and
  fishing. `vanilla:STATE_GREENLAND arable 3, fishing_village, livestock_ranch, whaling 5`.
- **Layer.** ET 85 %, EF 15 %: arctic_boreal_coast; coastal, fishing village.
- **Proposal.** Far-north coast default. Agrees with the layer. **Tier B.**

### STATE_DEATH_S_SIDE — Death's Side (UZK; 3,813 px; 59.3 N; inland; 3 of 17 provinces impassable)
- **Identity.** Uncertain. The name is in neither wiki. Hubs: Danyastrona is the Kislevite end of the Road of
  Skulls (`fandom:Road of Skulls [Archaon: Everchosen, novel, ch. 10; Old World website map]`); Black Skull
  Mountain and Fort Dorznye Vort are TWW names. The state is the easternmost in the file, half ice cap, east of the
  High Pass. I read it as the high mountains walling Zorn Uzkul. Confidence: low.
- **Canon.** No text for the place; the High Pass and Zorn Uzkul texts bracket it (permanent snow; barren rock).
- **Analogue.** Glaciated high range.
- **Layer.** EF 47 %, Dc 28 %, ET 25 %; south of 60 N the ET quarter maps to highland_alpine.
- **Proposal.** `arctic_boreal_coast`, 0, pasture, livestock only. **Tier C.**

### STATE_NORTH_CAPE — North Cape (VAR; 3,666 px; 68.8 N; coastal)
- **Identity.** The northern cape of the peninsula; Chris's name (no worksheet source). Hubs Gorehunt Hall and
  Aesling's Conclave are TWW names: the Gorehunt were a Khornate Norscan tribe wiped out in Araby in 2103 IC
  (`fandom:Gorehunt Tribe [Warriors of Chaos 7e p. 17]`). Owner Vargs. Confidence: medium (geography plain, no
  canon place).
- **Canon.** None on land use.
- **Analogue.** Finnmark's outer coast. `vanilla:STATE_NORTHERN_NORWAY arable 20, pasture, livestock_ranch`.
- **Layer.** ET 99 %: arctic_boreal_coast; coastal, fishing village.
- **Proposal.** Far-north coast default. Agrees with the layer. **Tier B.**

Progress: 45 of 45 entries written.

## 3. Rows

```csv
state_key,lore_class,fertility_step,subsistence,crops,tier,note,source
STATE_NORTH_NORSE_COAST,boreal_forest,-1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"Norscan coast default: few fields, fish and raiding; Norway analogue",lex:Norsca#Society [Tome of Corruption pp. 136-144] ; lex:Sortsvinaer [Liber Chaotica: Slaanesh] ; rw:Norway [runeberg.org/norparis/0320.html]
STATE_FJORD_COAST,boreal_forest,-2,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"Far-north coast at the analogue's grain limit (68 N); ice-bound northern half",fandom:Norsca#Geography [Tome of Corruption pp. 136-141] ; rw:Norway [runeberg.org/norparis/0325.html] ; rw:Northern Norway [en.wikipedia.org/wiki/Pomor_trade]
STATE_WEST_HELSPIRE_MOUNTAINS,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,B,"Mountain default; settled valleys raided by Graelings, no crop named",fandom:Bjornlings#Relations [Sea of Claws pp. 59-64] ; lex:Norsca#Locations [Tome of Corruption pp. 136-144] ; rw:Scandinavia [en.wikipedia.org/wiki/Transhumance]
STATE_ULFWRENAR_COAST,boreal_forest,-1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"South coast towns (Aarvik, Ulfennik); Skaeling Coast picture: fish, whales, fir valleys",fandom:Ulfennik [Warhammer Rulebook 8e pp. 452-454] ; lex:Skaeling_Coast [Sea of Claws p. 48] ; lex:Norsca#Society [Tome of Corruption pp. 136-144]
STATE_CLAW_COAST,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,C,"Inland mountain state despite its name; no canon land-use text; analogue only",lex:Norsca#Locations [Tome of Corruption pp. 136-144] ; rw:Scandinavia [en.wikipedia.org/wiki/Transhumance]
STATE_VANNHEIM_MOUNTAINS,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,A,"Vanaheim Mountains: snow all year, beasts hunted for meat and fur",fandom:Vanaheim Mountains [Warhammer: The Old World website map] ; lex:Bjornling_Coast [Sea of Claws pp. 58-59]
STATE_GLOOMWRACK_COAST,boreal_forest,0,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,A,"Bjornling Coast: fishing, raiding, trade; Bragnir's valleys unusually fertile (kelp manure)",lex:Bjornling#lead [Sea of Claws pp. 58-62] ; fandom:Bjornlings#Geography [Sea of Claws pp. 59-64]
STATE_ELDAGRIMM_GULF,boreal_forest,0,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,A,"Skjold on the Eldagrimm Gulf: plunder, trade, shipyards; layer's temperate class not supported",lex:Skjold [Sea of Claws pp. 60-62] ; fandom:Skjold [Sea of Claws pp. 60-63] ; lex:Bjornling#lead [Sea of Claws pp. 58-62]
STATE_ZORN_UZKUL,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,"Great Skull Land: barren rock plateau, thin cold air, dusty; Uzkulak slave port",lex:Dark_Lands#Zorn Uzkul [Warhammer Armies: Orcs & Goblins] ; fandom:Zorn Uzkul [Tamurkhan pp. 164-165] ; lex:Uzkulak [Tamurkhan pp. 164-165] ; rw:Changtang [en.wikipedia.org/wiki/Changtang]
STATE_SKULL_ROAD,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Road of Skulls across the Zorn Uzkul plateau; covered by the plateau text",fandom:Zorn Uzkul [White Dwarf Presents: Chaos Dwarfs p. 6; Tamurkhan pp. 164-165] ; lex:High_Pass [Realm of the Ice Queen p. 7]
STATE_BELYEROVOTA,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,A,"High Pass (Belyevorota): glaciers, snow rarely melts even in summer",fandom:High Pass [Realm of the Ice Queen p. 11] ; lex:High_Pass [Realm of the Ice Queen p. 7]
STATE_GOROMADNY_COAST,boreal_forest,0,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,"Vinnskor (Baersonlings): farmers and herdsmen, fields and shaggy cattle; novel-grade source","fandom:Vinnskor [Palace of the Plague Lord, novel, ch. 3] ; fandom:Baersonlings [same, ch. 1, 11] ; fandom:Aeslings [same, ch. 1]"
STATE_TROLL_COUNTRY,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,A,"No farming possible; steppe to tundra; nomads follow their herds; reindeer",fandom:Troll Country [Realm of the Ice Queen pp. 59-60] ; lex:Troll_Country [Sea of Claws pp. 34-37] ; fandom:Steppes Nomad [Realm of the Ice Queen p. 105]
STATE_FLESHWARREN,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,B,"Invented name; Hell Pit's barren snowy mountain; beast-breeding clan",lex:Hell_Pit#Overview [Skaven 7e p. 15; White Dwarf 311]
STATE_FROZEN_COAST,boreal_forest,-1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"Ursfjord and the hall of Urslo on the Frozen Sea; timber; no fields named",fandom:Bearmen of Urslo [Dogs of War 5e pp. 50-51] ; lex:Frozen_Sea [Old World website map] ; lex:Norsca#Society [Tome of Corruption pp. 136-144]
STATE_TALDURSFJORD,arctic_boreal_coast,1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"Fjord under Kraka Dorden; Skraevold's Aeslings work their own fields; novel-grade","fandom:Skraevold [Palace of the Plague Lord, novel, ch. 1] ; lex:Kraka_Dorden [Lords of Stone and Steel p. 20] ; lex:Frozen_Sea [Old World website map]"
STATE_KRAKEN_COAST,arctic_boreal_coast,0,building_subsistence_fishing_village,building_livestock_ranch,B,"Far-north coast; no place canon; realm canon and Finnmark analogue",fandom:Norsca#Geography [Tome of Corruption pp. 136-141] ; vanilla:STATE_NORTHERN_NORWAY ; vanilla:STATE_ICELAND
STATE_MOUNTAINS_OF_HEL,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,R,"Ice-capped interior range (Forbidden Citadel); no land-use canon",fandom:Forbidden Citadel (Norsca) [Old World website map] ; rw:Scandinavia [en.wikipedia.org/wiki/Transhumance]
STATE_GIANTHOME_MOUNTAINS,boreal_forest,0,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,"Kraka Dorden: conifer-forest range; Khazid Fneldruk and Grung Dobekzhulf produce grain; against the herding ruling",fandom:Norse Dwarfs [Dwarfs: Stone and Steel p. 42] ; lex:Khazid_Fneldruk [Lords of Stone and Steel p. 24] ; fandom:Kraka Dorden [Lords of Stone and Steel p. 24]
STATE_BLACK_BLOOD_PASS,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,B,"Kraka Ravnsvake: metal, stone, fleet; no grain listed; dwarf herding ruling stands",lex:Kraka_Ravnsvake [Sea of Claws pp. 40-47; Lords of Stone and Steel p. 24] ; lex:Khazid_Bordkarag [Lords of Stone and Steel p. 24]
STATE_STUREN_RIDGE,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,A,"Sturen Ridges in central Troll Country: no farming possible, nomad herders","fandom:Troll Country [Realm of the Ice Queen pp. 45, 59-60] ; lex:Troll_Country [Sea of Claws pp. 34-37] ; fandom:Steppes Nomad [Realm of the Ice Queen p. 105]"
STATE_TROLLHEIM_MOUNTAINS,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,R,"Two-thirds ice cap; Black Gulch only canon place; no land-use text",fandom:Black Gulch [Old World website map] ; rw:Scandinavia [en.wikipedia.org/wiki/Transhumance]
STATE_ULFWRENAR_MOUNTAINS,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,B,"Doomkeep and Hall of the Snaegr: Skaelings hunt and raid from the pass",fandom:Doomkeep [Old World website map] ; lex:Snaegr [Hordes of Chaos 6e p. 9; Sea of Claws p. 52]
STATE_BAY_OF_BLADES,boreal_forest,-1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,A,"Ormskaro: whaling, fishing, timber rafting; layer's steppe (wheat, vineyard) not supported","fandom:Ormskaro [Wulfrik, novel, ch. 2] ; fandom:Sarls [Palace of the Plague Lord, novel, ch. 10] ; fandom:Bay of Blades [Sea of Claws p. 36]"
STATE_NAGLFARI_MOUNTAINS,arctic_boreal_coast,0,building_subsistence_fishing_village,building_livestock_ranch,R,"Ice-capped coastal range; no canon place; Lofoten-wall analogue",rw:Lofoten [en.wikipedia.org/wiki/Lofoten] ; vanilla:STATE_NORTHERN_NORWAY
STATE_NAGLFARI_COAST,boreal_forest,-2,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"Far north-west coast at 69 N, the analogue's barley limit; no place canon",fandom:Norsca#Geography [Tome of Corruption pp. 136-141] ; rw:Norway [runeberg.org/norparis/0325.html]
STATE_HELL_PIT_DEPTHS,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,B,"Invented name; Hell Pit's barren snowy mountain; beast-breeding clan",lex:Hell_Pit#Overview [Skaven 7e p. 15; White Dwarf 311]
STATE_HELL_PIT,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,A,"Hell Pit: chasm in a snowy mountainside, barren surroundings; no food text",lex:Hell_Pit#Overview [Skaven 7e p. 15; White Dwarf 311] ; fandom:Troll Country#Hell Pit Hunting Grounds
STATE_FORT_STRAGHOV,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,C,"TWW name; read as eastern Troll Country by position; no farming, herders",fandom:Troll Country [Realm of the Ice Queen pp. 59-60] ; fandom:Steppes Nomad [Realm of the Ice Queen p. 105]
STATE_HELSPIRE_COAST,boreal_forest,-1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"Sortsvinaer's northern coast; Norscan coast default",lex:Sortsvinaer [Liber Chaotica: Slaanesh] ; lex:Norsca#Society [Tome of Corruption pp. 136-144] ; rw:Norway [runeberg.org/norparis/0320.html]
STATE_NORSVEG_PLAIN,boreal_forest,-1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"Graeling coast: sea raiders and slavers; no source says the plain is farmed",lex:Bjornling#Relations [Sea of Claws p. 59] ; fandom:Norsca#Crafts and Trade [Warriors of Chaos 7e pp. 38-41] ; lex:Norsca#Society [Tome of Corruption pp. 136-144]
STATE_HELSPIRE_MOUNTAINS,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,B,"Helspire Mountains: settled valleys raided by Graelings; tundra and ice by the layer",fandom:Bjornlings#Relations [Sea of Claws pp. 59-64] ; rw:Scandinavia [en.wikipedia.org/wiki/Transhumance]
STATE_BJORNLING_S_GATHERING,boreal_forest,-1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"Northern Bjornling Coast: fishing, raiding, trade; no fields named",lex:Bjornling#lead [Sea of Claws pp. 58-62] ; fandom:Bjornlings#Geography [Sea of Claws pp. 59-64]
STATE_STROVENGAARD,boreal_forest,0,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,B,"Hall of Strovengaard (Skaelings) on the mild south coast; layer's temperate class not supported","fandom:Egil Styrbjorn [Knight of the Realm, novel] ; fandom:Skaelings#Skaeling Coast [Sea of Claws pp. 48-49] ; lex:Skaeling_Coast [Sea of Claws p. 48]"
STATE_MERMEDUS_COAST,boreal_forest,-1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,A,"Skaeling Coast: sea full of fish and whales, fir in sheltered valleys, smokehouses",lex:Skaeling_Coast [Sea of Claws p. 48] ; lex:Kirkjugardur_Langskipa [Sea of Claws pp. 53-54] ; fandom:Skaelings [Sea of Claws pp. 48-49]
STATE_CHAMON_DHAREK,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,A,"Chamon Dharek mound in southern Troll Country: no farming possible, nomad herders",lex:Troll_Country#Locations [Realm of the Ice Queen p. 60; Sea of Claws p. 36] ; fandom:Troll Country [Realm of the Ice Queen pp. 59-60] ; fandom:Steppes Nomad [Realm of the Ice Queen p. 105]
STATE_VIDARHEIM,arctic_boreal_coast,0,building_subsistence_fishing_village,building_livestock_ranch,C,"TWW name on the Frozen Sea coast; no canon; owner Kvellig are hunters",fandom:Kvellig [Arcane Journal: Warriors of Chaos p. 8] ; vanilla:STATE_NORTHERN_NORWAY
STATE_KRAKA_DRAK,boreal_forest,1,building_subsistence_farm,building_rye_farm building_livestock_ranch,A,"Exports grain; Khazid Ravik cheese fur grain wool; Sjoktraken grain; confirms ruling",lex:Kraka_Drak#Trade [Lords of Stone and Steel p. 24] ; lex:Khazid_Ravik [Lords of Stone and Steel p. 24] ; fandom:Norse Dwarfs [Dwarfs: Stone and Steel p. 42]
STATE_BRENNUN_S_ENCAMPMENT,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,C,"TWW name; half ice cap; no canon land-use text; analogue only",rw:Scandinavia [en.wikipedia.org/wiki/Transhumance] ; lex:Norsca#Locations [Tome of Corruption pp. 136-144]
STATE_THORSHAFN,boreal_forest,-1,building_subsistence_fishing_village,building_livestock_ranch building_rye_farm,C,"TWW name; south-east coast; Norscan coast default; owner Hastlings are horsemen elsewhere",fandom:Hastlings [Arcane Journal: Warriors of Chaos p. 8] ; lex:Norsca#Society [Tome of Corruption pp. 136-144]
STATE_MONOLITH_OF_INGVAR,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,C,"TWW name; northern interior tundra and ice; no canon land-use text",rw:Scandinavia [en.wikipedia.org/wiki/Transhumance] ; lex:Norsca#Locations [Tome of Corruption pp. 136-144]
STATE_EAGLE_S_PEAK,arctic_boreal_coast,1,building_subsistence_pasture,building_livestock_ranch building_rye_farm,A,"Kraka Ornsmotek: gold hold at 68 N; Kazad Dumund grows grain and makes cheese for it","fandom:Kraka Ornsmotek [Lords of Stone and Steel pp. 20, 24] ; lex:Kraka_Ornsmotek [Dwarfs: Stone and Steel p. 42]"
STATE_VARG_CAMP,arctic_boreal_coast,0,building_subsistence_fishing_village,building_livestock_ranch,B,"Varg coast at 70 N: beyond the grain limit; sea economy",lex:Norsca#Tribes [Tome of Corruption pp. 136-144] ; fandom:Vargs [Games Day 2002: Hrothgar Daemonaxe pp. 1-3] ; vanilla:STATE_GREENLAND
STATE_DEATH_S_SIDE,arctic_boreal_coast,0,building_subsistence_pasture,building_livestock_ranch,C,"Identity uncertain; half ice cap east of the High Pass; no canon land-use text",fandom:High Pass [Realm of the Ice Queen p. 11] ; fandom:Road of Skulls [Old World website map]
STATE_NORTH_CAPE,arctic_boreal_coast,0,building_subsistence_fishing_village,building_livestock_ranch,B,"Northern cape, all tundra; Varg coast; Finnmark analogue",lex:Norsca#Tribes [Tome of Corruption pp. 136-144] ; vanilla:STATE_NORTHERN_NORWAY
```

Reading the rows: `lore_class` is the class the evidence supports for the state's land as a whole. Where it equals
the layer's dominant class the row is a confirmation, not a correction (34 of 45), and the model should keep its
per-pixel mix there rather than flatten the state to one class (open question 3).

## 4. Disagreements

### 4.1 With the climate layer's reading

**Class changes (11 states by dominant class; Death's Side is a twelfth where only the minority share moves).**

| state | layer (dominant) | proposed | reason |
|---|---|---|---|
| STATE_ELDAGRIMM_GULF, STATE_STROVENGAARD | temperate_forest_hill (Df) | boreal_forest, step 0 | Nothing in canon supports mixed-forest farm country in Norsca; the Bjornling and Skaeling coasts are described as harsh, mountainous, fir-clad. The layer's temperate reading would give these two states several times the arable of vanilla's whole Western Norway. |
| STATE_BAY_OF_BLADES | steppe (BSk 36 %) | boreal_forest, -1 | The dry share is canon's cold hunting steppe; steppe's defaults (farm, wheat, vineyard) are wrong for a whaling and timber fjord. |
| STATE_TROLL_COUNTRY, STATE_STUREN_RIDGE, STATE_CHAMON_DHAREK, STATE_FORT_STRAGHOV | boreal_forest (Dc 82-100 %) | arctic_boreal_coast, pasture | Canon: no farming is possible; steppe to tundra; nomad herders. The layer has no way to see this (it is a Chaos-blighted waste at a boreal latitude); a `climate_lore.json` patch would be the physical-side fix if Chris wants the picture itself to change. |
| STATE_ZORN_UZKUL | boreal_forest (Dc 70 %) | open_desert | Canon: barren rock plateau, thin cold air, dust. |
| STATE_SKULL_ROAD | highland_alpine / boreal mix | open_desert | Same plateau, by the road's canon route. |
| STATE_BELYEROVOTA | highland_alpine (ET just south of 60 N) | arctic_boreal_coast | Canon: snow rarely melts even in summer. The 60 N cut in the ET rule is what turns a glaciated pass into an alpine valley state. |
| STATE_DEATH_S_SIDE | arctic dominant (EF 47 %), with an ET quarter that maps to highland_alpine south of 60 N | arctic_boreal_coast throughout | Same cut-off problem; half the state is ice cap. Tier C. |
| STATE_GIANTHOME_MOUNTAINS | arctic_boreal_coast (ET 86 %) | boreal_forest | Canon: conifer-forested range, grain grown by Kraka Dorden's dependencies. |

**Subsistence changes where the class is kept.** Every coastal Norscan state the layer reads as boreal (11 states)
moves from the boreal default `farm` to `fishing_village`, on realm canon. STATE_GOROMADNY_COAST deliberately keeps
`farm` (Vinnskor). STATE_BLACK_BLOOD_PASS moves from the coastal-arctic default (fishing village) to `pasture` under
the dwarf ruling. The Troll Country four take `pasture`, not the coastal-arctic fishing village.

**Steps.** -1 on nine boreal coasts, -2 on the two northernmost (Fjord Coast, Naglfari Coast), 0 on the five with
place-specific support (Gloomwrack, Eldagrimm, Strovengaard, Goromadny, Gianthome Mountains), +1 on Kraka Drak, Taldursfjord and Eagle's
Peak.

**Agreements worth stating.** The model's defaults are right for the 14 inland tundra and ice states (pasture)
and the 6 far-north tundra coasts (fishing village): canon and the analogue support both, as the task asked me to
check per state.

### 4.2 With the earlier part-A leads

- **NK-02 (Troll Country, Sturen Ridge: `down` 1 within arctic).** Confirmed and extended: the class itself must
  be set (the current layer reads boreal, not arctic as the draft expected), the subsistence is pasture, and
  Chamon Dharek and Fort Straghov belong with them.
- **NK-03 (Forest of Sighs).** The state key no longer exists in `00_norsca.txt`; nothing to rule on.
- **NK-04 (Hell Pit: `highland_alpine`, down 1).** Class changed to `arctic_boreal_coast` (the layer's reading
  north of 60 N); same intent. `STATE_CLAWMARKET` is no longer in the file.
- **NK-05 (Kraka Drak: `up` 1).** Confirmed, with the gazetteer page and two grain-producing dependencies added.
- **NK-01, NK-06** are Kislev's: not researched here.
- **DL-03 (Zorn Uzkul: `highland_alpine`).** Replaced by `open_desert`: same canon text, read as barren cold desert
  rather than as mountain valleys.
- **Part-A classes generally** (`state_climate_classes.csv`): "coast-named states take arctic_boreal_coast,
  mountain-named take highland_alpine". I reverse both for the south: the southern and western coasts are boreal
  (they are where the fields, forests and people are), and the mountains are arctic, not alpine (north of 60 N the
  alpine class would give ice caps more arable than the coast). STATE_CLAW_COAST and STATE_EAGLE_S_PEAK keep the
  inland readings part A gave them.
- **Open question 8 of the draft** (arctic or boreal for the southern coasts at 61 to 63 N): answered boreal.

### 4.3 Between the two wikis

- **Frozen Sea.** Lexicanum (Old World website map; Lords of Stone and Steel for the Frozen Harbour): a cold sea
  with fjords and Dwarf shipping. Fandom (no GW book cited; novel material): frozen solid. I follow Lexicanum.
- **Kraka Drak in 2502.** Fandom's lead says the hold was "completely destroyed"; both wikis then describe its
  resettlement and the 4e gazetteer lists it as a working, grain-exporting hold in 2512. I follow the gazetteer.
- **Skaeling range.** Fandom scatters the Skaelings across the southern coast and the mountains behind it; the mod
  seats the SKA tag in the far north-west. Ownership, not land use; noted because the Skaeling Coast land-use text
  therefore lands on states owned by other tags (SNA, SAR, BAE).

### 4.4 Not corroborated on Lexicanum

Lexicanum was at its page cap after the first day and was not used on 2026-11-20. These claims rest on Fandom
alone: everything from *Palace of the Plague Lord* (Vinnskor, Skraevold, Baersonling cattle, Sarl timber rafting)
and *Wulfrik* (Ormskaro); the Realm of the Ice Queen wording "no farming is possible" and the Steppes Nomad career
text (Lexicanum's Troll Country page supports the nomad and tundra picture but not that sentence); Bragnir's
fertile valleys; the Giantshome "land of plenty" passage; Kazad Dumund and Grung Dobekzhulf's grain (Lexicanum
confirms the same gazetteer for Kraka Drak, Khazid Ravik and Khazid Fneldruk); the High Pass climate text; the
Old World website map entries (Vanaheim Mountains, Doomkeep, Forbidden Citadel, Black Gulch).

## 5. Open questions for Chris

1. **Norse Dwarf holds: herd or farm?** The standing ruling makes Kraka Drak the only Norse grain hold. The WFRP 4e
   gazetteer (Lords of Stone and Steel p. 24) lists grain under Kraka Dorden's and Kraka Ornsmotek's dependencies
   as well. I propose `farm` for STATE_GIANTHOME_MOUNTAINS (Dorden), `pasture` with a rye farm for
   STATE_EAGLE_S_PEAK (Ornsmotek: "grain and cheese"), `pasture` for STATE_BLACK_BLOOD_PASS (Ravnsvake: no grain).
   Yes or no on extending the grain-hold list to Kraka Dorden?
2. **Per-pixel density at high latitude.** A Norscan pixel is 30 to 40 % smaller in km2 than the pixels vanilla's
   boreal density was measured on (section 1.3). Should the model carry a latitude term? If not, my Norscan coast
   default should be -2, not -1, to land on vanilla Norway.
3. **Does a lore row flatten a mixed state?** Several states are mixed (Taldursfjord a third boreal, Kraka Drak
   half tundra). If a row replaces every pixel's class with `lore_class`, a row that merely confirms the dominant
   class changes the number. I assumed confirmations leave the pixel mix alone.
4. **Floor.** Twenty-eight of the 45 states end in the arctic class or open desert, at well under 1 arable before
   any floor. Vanilla's minimum is 2 (Kola, Ob, Okhotsk). The inhabited ones (the tribes' mountain seats, Troll
   Country, the three Hell Pit states, Uzkulak) need whatever floor the model sets to hold their pops.
5. **Inferred identities (tier C, 7 states):** Claw Coast (inland despite its name), Fort Straghov (read as
   eastern Troll Country), Vidarheim, Brennun's Encampment, Thorshafn, Monolith of Ingvar, Death's Side. All take
   the default for their climate and coast; say if any is meant as something particular.
6. **Zorn Uzkul's class** should match whatever the Dark Lands dossier does with the Chaos Dwarf north; I chose
   `open_desert` independently.
7. **Hell Pit's subsistence** (pasture here, as a beast-breeding clan on barren ground) should follow the Skaven
   dossier's ruling for under-city clans if that differs.
8. **Novel-grade evidence.** Goromadny Coast's `farm` and Taldursfjord's +1 rest on a Black Library novel reported
   by Fandom, attached to those states through TWW hub placements. Acceptable as tier A/B, or demote to the coast
   default?
9. **The far north-west reads boreal.** The layer gives Dc to Naglfari Coast and Fjord Coast at 68 to 69 N. I
   answered with -2 rather than a class change; worth a look on the climate render.
10. **Albion** is not in this file, so the task's Albion pointer went unused. Whoever holds the `03_brettonia`
    stub should cover it.

## 6. Pages read

**Lexicanum (read through the browser pane, 2026-11-19; 34 pages, cap reached, none read on 2026-11-20):** Norsca
(also reached as Norse, Norscans), Aesling, Bjornling, Bjornling Coast, Sarl, Skaelings (also as Skaeling), Skaeling
Coast, Varg, Snaegr, Sortsvinaer, Troll Country, Kraka Drak, Kraka Dorden, Kraka Ornsmotek, Kraka Ravnsvake, Norse
Dwarf, Khazid Bordkarag, Khazid Ravik, Khazid Fneldruk, Hell Pit, Skjold, Altar of the Crimson Harvest, Frozen Sea,
Kraken Sea, Uzkulak, Dark Lands, High Pass, Clan Moulder, Sea of Claws, Kurgan, Skaven, Throgg, Ulfwerenar,
Kirkjugardur Langskipa. No Lexicanum page exists for: Graeling, Baersonling, Chamon Dharek, Zorn Uzkul, Sjoktraken,
Goromadny, Giantshome. Same-origin `fetch` drew HTTP 429 then 403 on 2026-11-19; plain navigation still worked; per
the 2026-11-20 update Lexicanum was not used again.

**Fandom, read live 2026-11-19:** Norsca, Baersonlings, Aeslings, Graelings, Vargs, Sarls, Bjornlings, Skaelings,
Troll Country, Kraka Drak, Norse Dwarfs, Kraka Ravnsvake, Kraka Dorden, Kraka Ornsmotek, Hell Pit, Zorn Uzkul,
Uzkulak, Frozen Sea, Bay of Blades, Altar of the Crimson Harvest, Forest of Knives, Hastlings, High Pass, Kvelligs,
Road of Skulls, Skraevold, Ursfjordings (Bearmen of Urslo), Vanaheim Mountains, Vinnskor, Chamon Dharek, Sea of
Claws, Skjold, Helspire, Egil Styrbjorn, Mermedus, Clan Moulder, Kislev.

**Fandom local dump (`sources/wiki/pages/`), 2026-11-20:** read in full or to the relevant sections: Ormskaro,
Ulfennik, Norscan Freeholder, Norscan Whalers, Iskvard, Suderholm, Fjaergardhold, Black Gulch, Forbidden Citadel
(Norsca), Doomkeep, Tower of Khrakk, Mount Hellspire, Icehorn Peak, Kraka Drang, Leblya, Zamak Spayenya, Steppes
Nomad, Troll Country, Svunum, Hastlings, Kvellig. Keyword passes (farm, crop, grain, cattle, herd, fish, whale,
pasture, reindeer, food, hunt): Norscan Thrall, Norscan Bondsman, Tribe of the Crow, Iron Wolves, Gorehunt Tribe,
Sea of Chaos, Mammoths, Schwarzvolf, Kraka Ornsmotek, Kraka Dorden, Kraka Ravnsvake, Hell Pit. Context checks for
single names: Kislev (Black Blood Pass, Straghov), Norsca (minor tribes, infobox, mountain names), Vargs, Kislev
(City). Name searches across the whole dump that found nothing: Macadone, Thorshafn, Vidarheim, Naglfar, Norsveg,
Trollheim, Pradeshynya, Varg Camp, Gorehunt Hall. The index was walked for the Norsca, Norse Dwarf and Troll
Country categories.

Useful dump finds not tied to one state: freeholders work land "frozen for six months" and most of Norsca's meagre
wealth is timber and mines, amber among them (`fandom:Norscan Freeholder [Tome of Corruption p. 146; Career
Compendium p. 83]`); Imperial demand for lamp oil makes whaling very profitable (`fandom:Norscan Whalers [Tome of
Corruption p. 150; Career Compendium p. 226]`); thralls build longships or work the frozen fields (`fandom:Norscan
Thrall [Tome of Corruption p. 140]`); mammoths are hunted in Norsca (`fandom:Mammoths [Warhammer Rulebook 3e p.
249]`).

**Web:** https://en.wikipedia.org/wiki/Economic_history_of_Norway ; https://en.wikipedia.org/wiki/Economy_of_Iceland ;
https://en.wikipedia.org/wiki/Agriculture_in_Iceland ; https://en.wikipedia.org/wiki/Transhumance ;
https://en.wikipedia.org/wiki/Reindeer_herding ; https://en.wikipedia.org/wiki/Pomor_trade ;
https://en.wikipedia.org/wiki/Lofoten ; https://en.wikipedia.org/wiki/Pomors ; https://en.wikipedia.org/wiki/Nenets_people ;
https://en.wikipedia.org/wiki/Changtang ; https://en.wikipedia.org/wiki/Whaling_in_the_Faroe_Islands ;
https://en.wikipedia.org/wiki/Economy_of_the_Faroe_Islands (nothing usable) ;
https://en.wikisource.org/wiki/1911_Encyclop%C3%A6dia_Britannica/Norway ;
https://en.wikisource.org/wiki/1911_Encyclop%C3%A6dia_Britannica/Iceland ;
https://runeberg.org/norparis/0320.html , /0321.html , /0322.html , /0325.html , /0326.html , /0327.html ;
https://www.ssb.no/a/en/histstat/kap14.html ; two web searches (Norway arable share and fisher-farmers; northern
limit of barley, which also surfaced Baedeker 1889 and an 1886 newspaper report, read only as search summaries).

**Repo and vanilla:** `map_data/state_regions/00_norsca.txt`; `localization/replace/english/map/states_l_english.yml`;
`mapgen/config/hub_worksheet.json`, `land_regions_worksheet.csv`, `state_climate_classes.csv`, `canon_rivers.csv`,
`climate_lore.json`, `vanilla_state_climate_classes.csv`, `canvas_frame.py`; `mapgen/derived/state_climate_index.json`,
`state_ownership.json`; `planning/economics/arable_land_engine_research.md`, `agro_climate_overrides_draft.md`;
`planning/tag_registry.md`; `common/buildings/12_subsistence.txt`, `02_agro.txt`, `04_plantations.txt`; vanilla
`map_data/state_regions/*.txt`.
