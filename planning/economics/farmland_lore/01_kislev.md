# Farmland lore dossier — `01_kislev.txt` (Kislev + the northern Empire states in that file)

Board item #3681 (Kislev half), epic #3675. Run 2026-11-19/20. Status: **in progress — saved as I go** (see "Progress" at the end).

The file `map_data/state_regions/01_kislev.txt` holds **33 states**: 20 Kislevite / steppe / mountain states and
13 states of the northern Empire (Nordland, Laurelorn, Middenland's Schadensumpf, the northern Wasteland, Ostland,
Talabecland, Ostermark). All 33 are covered below.

Citation grammar: `fandom:<Title>#<Section> [GW publication, page]` (Fandom Warhammer Wiki; read live through the
browser pane on 2026-11-19, and re-checked against the local dump `sources/wiki/` where marked `dump`),
`lex:<Page>#<Section> [GW publication, page]` (Lexicanum, read 2026-11-19), `rw:<region> [URL]`,
`vanilla:STATE_X arable N, subsistence, crops`. Everything is paraphrase unless in quotation marks.

---

## 1. Realm picture

### 1.1 Kislev in canon

**Two countries in one, split north/south.** The realm text is consistent across both wikis and comes from
*Realm of the Ice Queen* (WFRP 2e):

- The forests of the Empire fade out in Kislev and give way to the *oblast*: broad, empty, cold grassland with
  parched ground, dry air and rare, torrential rain. Farming is hard and only viable in the more fertile south;
  most northerners are nomad herders. The north is barely distinguishable from the Troll Country and the tundra,
  always cold and infertile, more wooded toward the eastern foothills. `lex:Kislev#Geography [Realm of the Ice Queen pp. 6-8]`;
  `fandom:Kislev#The Steppes and Oblast [Realm of the Ice Queen pp. 6-8]`.
- Soil in the north is particularly poor; only in the "more temperate and fertile south" can crops be raised without
  much difficulty, which is why the northern Ungol tribes live by livestock. `fandom:Kislev#The Steppes and Oblast [RotIQ pp. 6-8]`.
- The west coast communities live by fishing and whaling. East of the oblast the land turns to large tracts of
  woodland toward the World's Edge foothills. `fandom:Kislev#Lands of Kislev [RotIQ pp. 6-8]`.
- Winters are lethal, the far north can be snow-covered all year, summers are short; in autumn livestock is
  slaughtered and crops stockpiled. `fandom:Kislev#Climate [RotIQ pp. 6-10]`.
- Cultural split: the Gospodar south ("where the lands are relatively fertile") versus the nomad north, with the
  River Lynsk as the usual dividing line. `fandom:Kislev#Two Peoples Made One [RotIQ]`; `fandom:River Lynsk [RotIQ; WFRP 1e p. 278]`.

**The four oblasts (the decisive canon for this file)** — `Realm of the Ice Queen` pp. 51-60, via Fandom:

| canon region | bounds | land use in canon | source |
|---|---|---|---|
| Southern Oblast | south of the Lesser Tobol, west of the World's Edge | mildest climate, **the main farming region**; arable farming "at least of oats" possible almost everywhere, some orchards; little steppe left, could pass for a rural part of the Empire; southern edge is fir forest continuous with the Empire's; almost wholly Gospodar | `fandom:Southern Oblast [RotIQ pp. 54-55]` |
| Western Oblast | between the Lynsk and the Lesser Tobol; includes the Blight | flat, steppe-like, almost no forest; mostly steppe, but **the south and the area by the Empire's border are farmed to a significant extent**; warmest summers; razed in the Great War (2302) and still rebuilding | `fandom:Western Oblast [RotIQ p. 57]` |
| Eastern Oblast | between the Lynsk, the Lesser Tobol and the World's Edge | mostly true steppe; **some croplands south of the Lynsk**; the foothills are forested and send timber down to the stanitsas; Gospodar and Ungol mixed | `fandom:Eastern Oblast [RotIQ p. 56]` |
| Northern Oblast | between the Tobol and the Lynsk | classic steppe and low grassy hills **grazed by herds of horses and cattle; "no agriculture to speak of"** bar sheltered valleys; Ungol nomads; harshest winters | `fandom:Northern Oblast [RotIQ pp. 58-59]` |
| Troll Country | north-west, beyond the Lynsk | steppe turning to tundra; **no farming is possible**; nomads following herds; reindeer on lichen | `fandom:Troll Country [RotIQ pp. 59-60; Sea of Claws pp. 34-37]`; `lex:Troll_Country [Sea of Claws pp. 34-37; RotIQ p. 60]` |

**What Kislev grows and eats.** Oats are the one grain canon names for the fields (Southern Oblast). Kvas is made
from malt, rye or wheat flour (`fandom:Kvas [RotIQ p. 14]`); koumiss from mare's (or oblast-elk) milk
(`fandom:Koumiss [RotIQ pp. 14, 97]`); the peasant diet is fish, tubers and oblast-elk meat, and the elk is also a
plough and sleigh animal (`fandom:Oblast Elk [RotIQ pp. 138-139]`). Steppe ponies are hardy and grass-fed, slower
than the "grain-fed horses of the Empire" (`fandom:Kislev (City)#Geroyev Square`, that page's source 4a; publication not checked). Zoishenk is a cattle town
(`lex:Oblast#Locations [RotIQ pp. 51-56]`). Praag's own grain is "sickly and in short supply" beside the south's and
the city has been starved out by southern embargo more than once (`fandom:Praag [RotIQ pp. 69-70]`; `lex:Praag [RotIQ p. 10]`).
The Dolgan nomads keep goats for milk and cheese and bison and cattle for meat, moving pasture about weekly
(`lex:Dolgan#Life on the Steppes [Something Rotten in Kislev pp. 55-56]`).

**No canon wheat belt inside Kislev proper.** The one "black soil" text is Chernozavtra, a colony in "the
Wheatlands of Kislev" on rich black soil (`lex:Chernozavtra [Something Rotten in Kislev pp. 47-48]`). Reading it with
`fandom:Karak Vlag#History [Dwarfs: Stone and Steel p. 38]` (the High Pass "separates Kislev from its Farside colonies") and the
Dolgan neighbours, the Wheatlands are the colonies **beyond** the World's Edge Mountains, not the oblast
(inference from two pages; Fandom's Southern Oblast page lists Chernozavtra under that oblast, which I read as a
wiki filing error — flagged in the open questions). An older, lower-tier source says the Urskoy "makes the fields of
Kislev fruitful" (`fandom:River Urskoy [Citadel Journal, "Kislev: The Claws of the Great Bear" pp. 8-9]`).

### 1.2 The northern Empire states in this file, in canon

- **Nordland**: two great forests blanket the coast; people live in pockets cut from the woodland and along a barren
  shore; coast folk fish (herring and cod from Drosselspule Bay, salted and sent south), timber feeds shipbuilding
  at Dietershafen; the central highlands around the Silver Hills are the most populous and a little wealthier.
  `lex:Nordland#Overview [Sigmar's Heirs p. 63ff]`; `fandom:Nordland [Sigmar's Heirs pp. 63-68; Salzenmund: City of Salt and Silver]`.
- **Laurelorn**: an independent Eonir realm; humans may settle only between the Salz and the Demst, in limited
  numbers and with limits on what they harvest; the core beyond the Demst is closed on pain of death.
  `lex:Nordland#Overview [Sigmar's Heirs]`; `fandom:Laurelorn Forest [Sigmar's Heirs pp. 63-66; Archives of the Empire I]`.
- **Middenland / Schadensumpf**: a swampy morass north of Middenheim where "little of worth" is found; a few villages
  live off bog iron. `fandom:Middenland [Sigmar's Heirs pp. 53-58]`.
- **The Wasteland (north)**: once rich woodland and grassland, since devastated; the Tumble Downs are broken hillocks
  and boggy dells with tiny vegetable plots and small herds of thin sheep and cattle; Aarnau is a fishing and
  farming town of 4,000. `lex:The_Wasteland [Marienburg: Sold Down the River pp. 6-10]`; `fandom:The Wasteland [MSDtR pp. 7-10]`.
- **Ostland**: covered almost entirely by the Forest of Shadows, farms in cleared patches; the bull emblem is read
  as heavy use of cattle; the only unforested land is the windswept grassland of the Northern March, which exports
  salted fish and sheep's-milk cheese; Ostlanders resent the "breadbasket" provinces (Reikland, Stirland, Averland,
  the Moot). `lex:Ostland [Sigmar's Heirs pp. 73-74; Uniforms & Heraldry pp. 36-39]`; `fandom:Ostland [Sigmar's Heirs pp. 73-76; Archives of the Empire I p. 13]`.
- **Talabecland**: the Great Forest end to end (oak, birch, beech in the south, dark pine in the north) with
  occasional clearings of fertile farmland where the villages are; far more villages along the rivers, living on
  Talabec fish; herdsmen in the central Färlic Hills. `fandom:Talabecland [Sigmar's Heirs pp. 77-81, 90-91]`;
  `lex:Talabecland [Sigmar's Heirs pp. 89-92]`; `fandom:River Talabec [WFRP 1e p. 283; Death on the Reik p. 23]`.
- **Ostermark**: a rural, agricultural province (`lex:Ostermark [White Dwarf 326 p. 58]`), called highly fertile if
  hostile (`fandom:Ostermark [Sigmar's Heirs pp. 68-72]`). Four parts: the Gryphon's Wood along the upper Talabec
  (lumber, riverboats, many small villages), the Dead Wood on the Stir (nothing natural lives there), the Bleak Moors
  between (fens, shallow lakes, sheep and a little dairy) and the Veldt (rolling grassland, famous horse herds,
  horse market at Heffengen). `lex:Ostermark#Known features [Sigmar's Heirs pp. 68-69]`.

### 1.3 Real-world analogue (1800-1850)

Kislev is built on Russia / Ukraine / Poland-Lithuania (the wikis' own notes say so: `lex:Kislev#Notes`,
`fandom:Ungols#Trivia`). The question the prompt set: is southern Kislev black-earth steppe or cold forest-steppe?

**Ruling: cold forest-steppe / non-black-earth rye-and-oats country, not chernozem.** Canon decides it: the best
land in the realm is described by *oats* being possible almost everywhere and by "even some orchards", inside a
realm whose farming is "hard" and whose land is "generally infertile"; and the climate layer puts it in the cold
continental belt (Df/Dc). The real black-earth belt is defined by the opposite: wheat for export on the richest
soil in Europe.

Facts read this session:

- Russia's black-earth belt runs north-east from the Romanian border through Ukraine, the Central Agricultural
  Region and the Middle Volga: the grain-surplus zone. The non-black-earth forest zone had poor soils, was
  grain-deficit, and lived by rye, oats, flax, potatoes, livestock and crafts. Rye and oats were the traditional
  grains; wheat before 1861 was mainly a landlord export crop in the surplus zone. Three-field rotation: a third
  winter rye, a third spring oats, a third fallow. `rw:Russia [https://en.wikipedia.org/wiki/Agriculture_in_the_Russian_Empire]`.
- The East European forest-steppe (Dfb, 2,100 x 600 km from central Ukraine to the Urals) is today more than half
  arable. `rw:forest-steppe [https://en.wikipedia.org/wiki/East_European_forest_steppe]`.
- Rye was the main bread grain everywhere east of the France-Germany line and north of Hungary; it survives cold
  and snow cover that kill winter wheat and tolerates poor sandy or peaty soil; kvass is fermented from rye bread
  or rye flour and malt. `rw:rye belt [https://en.wikipedia.org/wiki/Rye]`.
- Cropland share of European Russia: about 7.9 % in 1696, 16.8 % in 1796, 29.2 % in 1914 (Zhao et al. 2020, as
  reported by the search digest; provincial values in 1795 around 37-43 % for Vladimir, Ryazan, Yaroslavl).
  Forest cover (Tsvetkov 1957, same digest): 52.7 % in 1696, 44.8 % in 1796; six central provinces 41.6 % in 1796
  and 31 % in 1868. `rw:European Russia [search digest of https://www.researching.cn/articles/OJf0ce55b990144025 and cyberleninka.ru Tsvetkov citations]` — digest only, not the papers themselves.
- The Pontic steppe ("Wild Fields") stayed thinly peopled nomad and Cossack country under Tatar raiding until the
  1780s; ploughed up as Novorossiya only afterwards. `rw:Wild Fields [https://en.wikipedia.org/wiki/Wild_Fields]`.
  That is the analogue for the **northern** oblast (raided, grazed, unploughed), not for the south.
- A stanitsa is a Cossack host's village unit under an elected ataman, holding its land in common.
  `rw:stanitsa [https://en.wikipedia.org/wiki/Stanitsa]`.

Vanilla calibration (read from the install; class from `mapgen/config/vanilla_state_climate_classes.csv`):

| analogue | vanilla states |
|---|---|
| rye-belt forest zone (southern Kislev, Ostland, Talabecland) | `vanilla:STATE_SMOLENSK arable 62, farm, rye livestock` (boreal_forest); `STATE_MOSCOW 60`; `STATE_TVER 68`; `STATE_MINSK 90` (temperate_forest_hill); `STATE_BREST 75`; `STATE_LITHUANIA 56`; `STATE_VILNIUS 31`; `STATE_VOLHYNIA 40` |
| black earth (what southern Kislev is **not**) | `vanilla:STATE_KIEV arable 175, farm, wheat livestock` (temperate_river_plain); `STATE_KHARKOV 150`; `STATE_KURSK 115`; `STATE_TAMBOV 155` |
| grazed steppe (northern oblast, Dolgan and Ungol country) | `vanilla:STATE_URALSK arable 35, pasture, livestock`; `STATE_AKTOBE 24, pasture, livestock`; `STATE_KALMYKIA 8, pasture, livestock wheat`; `STATE_AKMOLINSK 45, pasture, rye livestock` |
| settled steppe margin (Western Oblast, Erengrad) | `vanilla:STATE_SAMARA arable 95, farm, rye livestock`; `STATE_SARATOV 90, farm, rye livestock`; `STATE_TOBOLSK 53, farm, rye livestock` |
| taiga and far north | `vanilla:STATE_ARKHANGELSK 15, farm, rye livestock`; `STATE_EAST_KARELIA 10`; `STATE_KOLA 2, farm, livestock`; `STATE_NENETSIA 5, pasture, livestock` |
| Baltic coast forest (Nordland, Ostland's march) | `vanilla:STATE_MECKLENBURG 25, farm, rye livestock`; `STATE_POMERANIA 55`; `STATE_EAST_PRUSSIA 40`; `STATE_COURLAND 22`; `STATE_RIGA 38`; `STATE_TALINN 22` |
| North Sea moor and marsh (Wasteland) | `vanilla:STATE_FRIESLAND 30, farm, rye livestock`; `STATE_HOLLAND 30` |
| central German forest upland (Talabecland) | `vanilla:STATE_HESSE 80, farm, rye livestock vineyard`; `STATE_WESTPHALIA 60`; `STATE_HANNOVER 60` |

**Vanilla never gives a vineyard north of the Hesse-Saxony-Bohemia line and never gives wheat to its rye belt**
(every Russian state north of Kiev-Kharkov, every Polish, Baltic and north-German state is `rye_farm, livestock_ranch`).
Today's emitted values give every state in this file `wheat_farm` and most of the Empire ones a `vineyard`:
both are wrong for this latitude and are corrected in the rows.

### 1.4 Where canon and analogue disagree, and which I follow

1. **Treeless oblast vs. the forest zone.** Real Russia at this latitude is forest (and the climate layer says
   Df/Dc = forest classes). Canon insists the forest *ends* at Kislev and the country is open grass. I follow canon
   for the land's look and use (class `steppe` for the open oblast states), and the analogue only for what grows
   (rye/oats, no wheat, no vines).
2. **Steppe does not mean black earth here.** The stereotype (Ukraine = wheat) is not supported by any Kislev text.
   Southern Kislev is classed `temperate_forest_hill` at typical fertility: settled rye country, not a
   `temperate_river_plain` granary.
3. **The Veldt.** Earlier draft: `steppe`. Canon makes it tillable humid grassland that farmers covet and horse
   breeders defend; I keep the forest-hill class (the land is good) and express the horse country through pasture
   subsistence and ranch-first crops.

---

## 2. Per-state entries

Conventions used in every entry:

- "Layer" = what `mapgen/derived/state_climate_index.json` reads (zone shares; Df -> temperate_forest_hill, Dc ->
  boreal_forest, ET -> highland_alpine below 60 N). "Indicative arable" = land px x class density x step factor,
  **before** the world rescale to 53,616; it is only there to show the size of the correction, not a target.
  "Today" = the stand-in value now in the state file (context only).
- `rye_farm` stands for the hardy northern grains as a group (canon names oats; vanilla has no oat building and
  uses `rye_farm` across its whole rye-and-oats belt).
- Hub names marked (TW) come from the TWW3 Old World mod region table: a lead to where the state sits, not canon.

### STATE_WEST_NORDLAND — West Nordland (owner NLD; 15 provinces; 3,849 px; anchor 4058,686)

- **Identity**: the inland strip between East Nordland (Salzenmund), the Schadensumpf to the south and the
  northern Wasteland to the west, directly south of the small `STATE_LAURELORN_FOREST`. Its two hub rows
  (Se Athil, Tor Lithanel, both TW) sit at the coast and at the Laurelorn state's own anchor, so they look stale
  from before the Laurelorn state was split off. I read the state as **the outer Laurelorn wards and the
  Salz-Demst settlement zone**. Confidence: medium (inferred from position; flagged).
- **Canon**: humans may settle only between the Salz and the Demst, in numbers the elves cap, with limits on what
  may be harvested from the forest; the wards outside the core are claimed by Nordland and Middenland and shared
  under logging treaties; the southern ward is mainly swamp. Around Hargendorf, at the Demst mouth, ships buy salt,
  fish, sheep and wool, and the villages south of it are a centre of Rhya (harvest-mother) worship.
  `lex:Nordland#Overview [Sigmar's Heirs p. 63ff]`; `fandom:Laurelorn Forest [Archives of the Empire I]`;
  `fandom:Hargendorf [Salzenmund: City of Salt and Silver pp. 106-107]`; `fandom:Nordland [Sigmar's Heirs pp. 63-68]`.
- **Analogue**: forested Baltic hinterland with sheep, c. 1800 (Pomerania led Prussia in sheep breeding;
  `rw:Pomerania [https://en.wikipedia.org/wiki/Province_of_Pomerania_(1815–1945)]`).
  `vanilla:STATE_MECKLENBURG arable 25, farm, rye livestock`; `vanilla:STATE_POMERANIA arable 55, farm, rye livestock`.
- **Layer**: Df 99 % -> temperate_forest_hill; indicative 59. Today 78, wheat/livestock/vineyard.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  The class is right; the step is the forest cap canon states outright (settlement and harvest capped by treaty).
  Sheep and wool are the named products, so the ranch leads. No wheat, no vineyard at this latitude. Indicative 40.
- **Tier**: B (province and forest text; the state's own identity is inferred).

### STATE_SCHADENSUMPF — Schadensumpf (owner MID; 9 provinces; 2,338 px; anchor 4056,724)

- **Identity**: the canon swamp of that name north of Middenheim. Hubs: Vorbegwerk, Drachenhöhle (TW), two invented.
  Confidence: high for the name.
- **Canon**: north of Middenheim the ground sinks into a swampy morass where little of worth is found; a few small
  villages live well off bog iron; outlaws hide there; huge flocks of black cranes. Middenland as a whole has acid
  forest soils that make cultivation hard, yet feeds itself with a small grain surplus most years; little dairying
  because herds draw raiders. `fandom:Middenland#Geography [Sigmar's Heirs pp. 53-58]`;
  `fandom:Middenland#Economy [Middenheim: City of the White Wolf pp. 119-121]`.
- **Analogue**: north-German raised bog and fen before drainage (bog-iron working is itself a moorland trade).
  `vanilla:STATE_FRIESLAND arable 30, farm, rye livestock`.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 36. Today 47.
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  There is no swamp class; canon's "little of worth" in a named morass is the strongest kind of evidence for the
  bottom step. Indicative 16.
- **Tier**: A.

### STATE_THE_WASTELAND — The Wasteland (owner MAR; 18 provinces; 4,515 px; anchor 4005,713)

- **Identity**: the **northern** Wasteland: the Tumble Downs with Aarnau (port hub) and Fort Solace, north-east of
  Marienburg (which is its own state). Hubs Stedum, Salfen, Gorssel are TW; Aarnau and Fort Solace are canon towns.
  Confidence: high.
- **Canon**: once rich woodland and grassland grazed by aurochs, ruined by the Skaven-Fimir war and misty and
  devastated since. The Tumble Downs are rough hillocks and boggy dells with stunted oak and pine, winter morass,
  summer mosquitoes; sparse hamlets scratch a living from "tiny vegetable plots" and small herds of stringy sheep
  and cattle. Settlement outside Marienburg mostly failed; Aarnau, the largest and oldest Downs town, is a fishing
  and farming place of 4,000; Fort Solace has 310. The coast is cold dune for a day's ride inland.
  `lex:The_Wasteland#Locations [Marienburg: Sold Down the River pp. 6-10]`;
  `fandom:The Wasteland#North [MSDtR pp. 8-9]`; `fandom:Aarnau [MSDtR p. 9; Sea of Claws p. 11]`.
- **Analogue**: Drenthe / Emsland heath and peat moor before reclamation — so poor that Drenthe was exempt from
  federal taxes in the Dutch Republic (`rw:Drenthe [https://en.wikipedia.org/wiki/Drenthe]`).
  `vanilla:STATE_FRIESLAND arable 30, farm, rye livestock`; `vanilla:STATE_HOLLAND arable 30`.
- **Layer**: Df 99 % -> temperate_forest_hill; indicative 70. Today 92.
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Canon is explicit that the Downs carry only garden plots and thin stock. Farm rather than pasture because the
  one real town farms and fishes; pasture is the defensible alternative (open question). Indicative 32.
  Confirms the earlier EMP-07 reading.
- **Tier**: A.

### STATE_SOUTHERN_OBLAST — Southern Oblast (owner KSV; 18 provinces; 4,697 px; anchor 4446,786)

- **Identity**: the southern strip of canon's Southern Oblast, below Kislev city down to the Empire border.
  Hub Vitevo is the canon salt-mine penal colony of the South Oblast (`lex:Oblast#Locations [RotIQ pp. 51-56]`);
  Resvynhaf and Fort Jakova are TW. Confidence: high.
- **Canon**: the mildest climate in Kislev and its main farming region; arable farming, "at least of oats", is
  possible almost everywhere and there are even some orchards; little steppe is left and a traveller could take it
  for a rural part of the Empire; the southernmost part is forest running unbroken into the Empire, turning to fir;
  settlements are larger than elsewhere; almost wholly Gospodar; it is the one region whose way of life would not
  survive the burning of half its settlements (i.e. it is settled, not mobile).
  `fandom:Southern Oblast [RotIQ pp. 54-55]`; `fandom:Vitevo [RotIQ p. 55]`.
- **Analogue**: the Russian / Lithuanian non-black-earth rye-and-oats country.
  `vanilla:STATE_SMOLENSK arable 62, farm, rye livestock`; `vanilla:STATE_MINSK arable 90, farm, rye livestock`;
  `vanilla:STATE_LITHUANIA arable 56`. Not `vanilla:STATE_KIEV arable 175, wheat`.
- **Layer**: Df 66 %, Dc 34 % -> temperate_forest_hill dominant; indicative 52. Today 51, wheat/livestock.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_farm`, crops `rye_farm livestock_ranch`.
  The class follows both the layer and canon's "like a rural part of the Empire". No step: it is the realm's best
  land but canon's yardstick is oats, so it earns typical, not rich. Grain leads the crop list because this is
  where Kislev's grain comes from (Praag is starved by southern embargo). Indicative 73.
  Replaces the earlier NK-06 (`steppe`, up 1): the steppe class is what canon says this region is *not*.
- **Tier**: A.

### STATE_BECHAFEN — Bechafen (owner OSM; 17 provinces; 5,002 px; anchor 4374,837)

- **Identity**: Ostermark's capital district on the upper Talabec, inside the Gryphon's Wood. No hub rows; the
  name is cited to the canon city in the region worksheet. Confidence: high.
- **Canon**: Ostermark is a rural province that lives mostly by agriculture and is called highly fertile if
  hostile; the Gryphon's Wood around Bechafen is its political and economic centre, exporting lumber and
  riverboats, less dangerous than other forests and full of small villages and homesteads.
  `lex:Ostermark#Overview [White Dwarf 326 p. 58]`; `lex:Ostermark#Known features [Sigmar's Heirs pp. 68-69]`;
  `fandom:Ostermark [Sigmar's Heirs pp. 68-72]`; `fandom:Bechafen [Sigmar's Heirs pp. 70-71]`.
- **Analogue**: Mazovia / eastern Brandenburg forest farmland on a navigable river.
  `vanilla:STATE_MAZOVIA arable 75, farm, rye livestock`; `vanilla:STATE_BRANDENBURG arable 50`.
- **Layer**: Df 99 % -> temperate_forest_hill; indicative 77. Today 101, wheat/livestock/vineyard.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_farm`, crops `rye_farm livestock_ranch`.
  Forest by name, but the two province-level statements (agricultural, fertile) and the well-settled wood cancel
  the usual forest cap. Indicative 78. Vineyard dropped.
- **Tier**: A.

### STATE_SOUTH_TALABECLAND — South Talabecland (owner TAL; 13 provinces; 3,679 px; anchor 4187,872)

- **Identity**: the south-west of Talabecland toward the Reik-Stir confluence. City hub Kemperbad (canon free
  town on the Reik's east bank, just north of the Stir mouth), mine hub Lieske (canon coaching-inn village on the
  Old Forest Road, in the south of the province); Zutzen and Wiedebach TW. Confidence: medium-high.
- **Canon**: Talabecland is the Great Forest end to end, with occasional clearings of fertile farmland; river
  villages are far more numerous than forest ones. Kemperbad is wealthy and "said to make the finest brandy in
  the Empire". Lieske's listed trades are pigs and timber. `fandom:Talabecland#Geography [Sigmar's Heirs pp. 77-81]`;
  `fandom:Kemperbad [Sigmar's Heirs pp. 82-84; WFRP 4e Core p. 282]`; `fandom:Lieske [Sigmar's Heirs p. 92]` (infobox: pigs, timber).
- **Analogue**: the wooded Hessian / Franconian river country.
  `vanilla:STATE_HESSE arable 80, farm, rye livestock vineyard`.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 57. Today 75.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_farm`, crops `rye_farm livestock_ranch vineyard`.
  Step 0 because this is the river-fronted, wealthy end of the province. The vineyard is an **inference**: brandy is
  distilled wine, and vanilla puts vines at this river latitude (Hesse); no page read says "vineyard" at Kemperbad.
  Listed last so it takes little of the budget; drop it if Chris wants named vines only. Indicative 57.
- **Tier**: B.

### STATE_VOLGEN — Volgen (owner TAL; 10 provinces; 2,553 px; anchor 4139,852)

- **Identity**: a western Talabecland state on the Talabec side, named from the TW table. No page for "Volgen" in
  either wiki (the dump's only near-match is Volgenhof / Volganof, a different, Ostland town). Confidence: low.
- **Canon**: none for the name. Province level only: Great Forest, dark pine in the north of the province, few
  natural clearings, river villages living on Talabec fish; the far west is the cursed Barren Hills.
  `fandom:Talabecland#Geography [Sigmar's Heirs pp. 77-81]`; `fandom:River Talabec [Death on the Reik (4e) p. 23]`.
- **Analogue / vanilla**: as South Talabecland.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 40. Today 52.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Forest cap from the province text. Indicative 27.
- **Tier**: C (identity of the state is a Total War name).

### STATE_NORTH_TALABECLAND — North Talabecland (owner TAL; 14 provinces; 3,682 px; anchor 4247,823)

- **Identity**: the Talabec-bank forest between Talabheim's district and Ostermark. Hubs: Lochrafurt (TW), rest
  invented. Confidence: medium (by name and position).
- **Canon**: the northern Great Forest is dark evergreen pine; above the Urskoy confluence the Talabec runs
  between heavy pine forests of evil repute; the river is the province's artery for timber, charcoal and pelts;
  many small villages line it and live on its fish. Bek, the upper-Talabec chief town, exports lumber and dried
  fish. `fandom:Talabecland#Geography [Sigmar's Heirs pp. 77-81]`; `fandom:River Talabec [WFRP 1e p. 283; Death on the Reik p. 23]`;
  `lex:Talabecland#Settlements [Sigmar's Heirs p. 90]`; `fandom:Bek [Sigmar's Heirs p. 91]`.
- **Analogue**: the Thuringian / Bohemian forest belt c. 1800 (charcoal, pitch, forest pasture).
  `vanilla:STATE_WESTPHALIA arable 60, farm, rye livestock`.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 57. Today 75.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Indicative 38. (Earlier EMP-05 capped at "mid"; with pine forest of evil repute as the only local text, -1 is
  the honest reading.)
- **Tier**: B.

### STATE_EAST_TALABECLAND — East Talabecland (owner TAL; 14 provinces; 3,534 px; anchor 4255,861)

- **Identity**: the eastern Great Forest toward Ostermark. Hubs Horno, Ossino (TW), rest invented. Confidence:
  medium.
- **Canon**: near Ostermark lie the Kölsa Hills, largely uninhabited, where farmers clearing trees turn up old
  earthworks; the cult of Taal and Rhya holds them as a preserve. `fandom:Talabecland#Geography [Sigmar's Heirs pp. 77-81]`.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 55. Today 72.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Largely uninhabited hills inside the forest. Indicative 37.
- **Tier**: B.

### STATE_WEST_OSTERMARK — West Ostermark (owners OSM, with two provinces VSY; 21 provinces; 4,759 px; anchor 4334,866)

- **Identity**: southern and western Ostermark: the Bleak Moors and Eerie Downs down to the Dead Wood and the
  Stir. City hub Essen is the canon town on the north Stir between the Dead Wood and the Eerie Downs.
  Confidence: high.
- **Canon**: the Bleak Moors are low hills, fens and shallow lakes, thinly peopled, towns clinging to the rivers;
  sheep-herding is the common living with small dairy herds, in isolated farms and crofts. The Dead Wood is
  shunned and nothing natural lives in it. `lex:Ostermark#Known features [Sigmar's Heirs pp. 68-69]`;
  `fandom:Ostermark [Sigmar's Heirs pp. 68-72]`; `fandom:Essen [Sigmar's Heirs p. 71]` (infobox: agriculture).
- **Analogue**: upland sheep moor. `vanilla:STATE_HIGHLANDS, building_subsistence_farm` is vanilla's own choice for
  moor (farm), but the canon text here names herding as the living.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 74. Today 109.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_pasture`, crops `livestock_ranch rye_farm`.
  Moor, fen and a dead forest: one step down. Pasture because sheep-herding is named as the common occupation.
  Indicative 49.
- **Tier**: A.

### STATE_GRYPHON_WOOD — Gryphon Wood (owner GRW; 6 provinces; 1,294 px; anchor 4326,804)

- **Identity**: a small slice of the canon Gryphon's Wood on the upper Talabec, west of Bechafen. Hubs
  Kappelburg (TW) and invented names. Confidence: high for the name.
- **Canon**: the Gryphon's Wood is the northern arm of the Great Forest along the upper Talabec; lumber is felled
  and floated to Bechafen; many small villages and isolated homesteads, with ruins of older ones deeper in.
  `lex:Ostermark#Known features [Sigmar's Heirs pp. 68-69]`; `fandom:Ostermark [Sigmar's Heirs pp. 68-72]`.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 20. Today 26.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  A wood by name whose export is timber. Indicative 13. The owner tag is a wood-elf one; if Chris means this as an
  elf enclave, it should follow the Laurelorn / Athel Loren convention instead (open question).
- **Tier**: A (name).

### STATE_WESTERN_OBLAST — Western Oblast (owner KSV; 19 provinces; 5,600 px; anchor 4330,716)

- **Identity**: the **southern, Empire-facing half** of canon's Western Oblast: it lies south of the Erengrad state
  and borders Ostland (Bohsenfels). City hub Milkavala is the canon West Oblast town (`lex:Oblast#Locations [RotIQ pp. 51-56]`);
  Ptorsk, Irjisara, Kamysh are TW. Confidence: high.
- **Canon**: flat, steppe-like and almost treeless; mostly steppe, but the southern parts and the land near the
  Empire's border are "farmed to a significant extent"; the warmest summers in Kislev, with freak summer
  blizzards off the Sea of Claws; sacked almost entirely in 2302 and still marked by it, with many villages now
  too small to be viable. Milkavala came through the last war without losing "a single cow". The Blight, a large
  tainted moor whose edge villages dig peat, lies in this oblast (which state holds it is not established).
  `fandom:Western Oblast [RotIQ p. 57]`; `fandom:Milkavala [RotIQ pp. 57-58]`; `fandom:The Blight [RotIQ p. 58]`.
- **Analogue**: the settled northern margin of the steppe, rye and stock.
  `vanilla:STATE_SAMARA arable 95, farm, rye livestock` (steppe); `vanilla:STATE_SARATOV arable 90, farm, rye livestock`.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 87. Today 60, wheat/livestock.
- **Proposal**: `steppe`, step **+1**, `building_subsistence_farm`, crops `rye_farm livestock_ranch`.
  Class swap against the layer: canon is flat that this oblast has almost no forest and is steppe. The +1 is for
  the one canon sentence that sets this half apart from ordinary steppe (farmed to a significant extent, warmest
  summers). Crops override the steppe default: no wheat, no vineyard. Indicative 38.
  Replaces NK-06's blanket "up 1" with the same step on firmer text.
- **Tier**: A.

### STATE_ERENGRAD — Erengrad (owner ERE; 22 provinces; 5,482 px; anchor 4332,646)

- **Identity**: Kislev's port city at the mouth of the Lynsk and the northern half of the Western Oblast along
  the river's south bank, east almost to Mazhorod. Hubs: Erengrad (canon), Vitzy, Zhedevka, Zhirovsk (TW).
  Confidence: high.
- **Canon**: the city sits in a lagoon at the Lynsk mouth; it trades whale oil, ivory, timber, tar and smoked fish
  brought across the Sea of Claws, and was Norvard, the Ungol capital, before the Gospodars. The land around it
  escaped the corruption that ruined Praag's. The coast's stanitsas live by fishing and whaling and must fend off
  Norse raids themselves. The oblast text above applies: mostly open steppe. No text on Erengrad's own farmland.
  `lex:Erengrad [RotIQ pp. 10, 61-62]`; `fandom:Erengrad [RotIQ pp. 61-66]`;
  `fandom:Kislev#Lands of Kislev [RotIQ pp. 6-8]`; `fandom:Old World Trade and Economy [Old World Armoury p. 12]`.
- **Analogue**: a Baltic entrepôt with a thin hinterland — Riga or Reval.
  `vanilla:STATE_RIGA arable 38, farm, rye livestock`; `vanilla:STATE_TALINN arable 22`; `vanilla:STATE_INGRIA arable 50`.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 85. Today 59.
- **Proposal**: `steppe`, step **0**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Same class swap as Western Oblast, without the plus: this is the "mostly steppelands" part. Farm, not fishing
  village: the state is 22 provinces of inland oblast behind one port (the fishery belongs in the capped
  resources, not the subsistence type). Indicative 25.
- **Tier**: B (oblast-level text; nothing on the city's own fields).

### STATE_BOHSENFELS — Bohsenfels (owner OST; 13 provinces; 3,212 px; anchor 4259,689)

- **Identity**: Ostland's coastal Northern March, between North Ostland and the Kislev border, named for the
  canon fortress-town of the outer march. No hub rows. Confidence: medium-high (Bohsenfels is named among the towns
  of the North March on `fandom:Salkalten`, in that page's Storm of Chaos section; used for location only).
- **Canon**: the only part of Ostland not under forest is the windswept grassland of the Northern March, from
  Salkalten to the Kislev border; its sleepy ports failed to draw the Kislev trade, and its main exports are
  salted fish and a pungent sheep's-milk cheese (hence "Cheeseheads").
  `fandom:Ostland#Geography [Sigmar's Heirs pp. 73-76]`; `fandom:Ostland#Northern March [Archives of the Empire I p. 13]`;
  `fandom:Bohsenfels [Sigmar's Heirs p. 75]`.
- **Analogue**: Courland / East Prussian coast: sheep, rye, herring.
  `vanilla:STATE_COURLAND arable 22, farm, rye livestock`; `vanilla:STATE_EAST_PRUSSIA arable 40`.
- **Layer**: Df 99 % -> temperate_forest_hill; indicative 49. Today 65, wheat/livestock/vineyard.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_pasture`, crops `livestock_ranch rye_farm`.
  Windswept coastal grass on a war frontier, exporting cheese and fish rather than grain: one step down and a
  herding subsistence. A fishing village is the alternative (the state has a coast). Indicative 33.
- **Tier**: B.

### STATE_EAST_NORDLAND — East Nordland (owner NLD; 21 provinces; 5,632 px; anchor 4138,677)

- **Identity**: Nordland proper: Salzenmund (capital, city hub), the Silver Hills, the coast with Dietershafen
  and Norden. All four are canon towns. Confidence: high.
- **Canon**: two great forests blanket the coast and people live in pockets cut out of them and along a barren
  shore of sand, marsh and bog; fishermen on Drosselspule Bay take vast catches of herring and cod, salted and sent
  south; timber feeds Dietershafen's shipyards, where fish, livestock and vegetable markets are held; Norden trades
  fish and amber; the central highlands round the Silver Hills are the most populous and a little wealthier; the
  province is a centre of Rhya worship. The Rol Valley's grain is told in the past tense (c. 1070 IC).
  `lex:Nordland#Overview [Sigmar's Heirs p. 63ff]`; `fandom:Nordland [Sigmar's Heirs pp. 63-68; Salzenmund: City of Salt and Silver]`;
  `fandom:Dietershafen [Salzenmund p. 106]`; `fandom:Norden [Sigmar's Heirs p. 66; Sea of Claws pp. 27-28]`.
  Infobox lead (uncited): exports agriculture, sheep, wool, cheese, woollens, timber.
- **Analogue**: Pomerania / Mecklenburg c. 1800: rye, coarse-wool sheep, herring.
  `vanilla:STATE_POMERANIA arable 55, farm, rye livestock`; `vanilla:STATE_MECKLENBURG arable 25`; `vanilla:STATE_SCHLESWIG_HOLSTEIN arable 40`.
- **Layer**: Df 98 % -> temperate_forest_hill; indicative 86. Today 114, wheat/livestock/vineyard.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Forest cap as stated by canon. Farm, because the populous part is the inland highland, not the fishing shore.
  Indicative 59. Confirms EMP-06.
- **Tier**: A.

### STATE_UNGOL_STEPPES — Ungol Steppes (owner UNG; 13 provinces; 3,708 px; anchor 4305,569)

- **Identity**: the southern **Troll Country**, north of the Lynsk above Erengrad. Its hubs are canon Troll
  Country places: Zamak Spayenya (the great white rock where nomads gather in summer), Pradeshynya (Ungol port
  town that swells with wintering nomads). Confidence: high.
- **Canon**: steppe turning to tundra; "no farming is possible"; long steppe grass in the south, reindeer on
  lichen in the north; the people are overwhelmingly Ungol nomads who follow their domesticated herds from pasture
  to pasture and settle only when snow stops them; fixed settlements get raided out.
  `fandom:Troll Country [RotIQ pp. 59-60; Sea of Claws p. 34]`; `lex:Troll_Country [Sea of Claws pp. 34-37; RotIQ p. 60]`;
  `fandom:Steppes Nomad [RotIQ]`; `fandom:Zamak Spayenya [RotIQ p. 60]`.
- **Analogue**: nomad steppe under raiding (the pre-1780s Wild Fields; the Kazakh / Kalmyk range).
  `vanilla:STATE_KALMYKIA arable 8, pasture, livestock wheat`; `vanilla:STATE_AKTOBE arable 24, pasture, livestock`.
- **Layer**: Df 60 %, Dc 40 % -> temperate_forest_hill dominant; indicative 38. Today 40, farm, wheat/livestock.
- **Proposal**: `steppe`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  Class swap (grass, not forest), bottom step (canon rules farming out), herding subsistence, ranch only.
  Indicative 8. `arctic_boreal_coast` would be the alternative but would zero it; the south of the Troll Country is
  grazed grass, and that is the part this state covers.
- **Tier**: A.

### STATE_THE_GOLINYI — The Golinyi (owner DOL; 22 provinces; 5,784 px; anchor 4458,550)

- **Identity**: the far north beyond Praag and the Lynsk, toward the Goromadny range; owned by the Dolgan tag.
  The name is not in either wiki; hubs are TW. Confidence: low (identity inferred from position and owner).
- **Canon**: nothing for the name. For the area: north of the Lynsk the land is cold, infertile nomad country
  and the far north can lie under snow all year; Chaos warbands prowl the north bank. For the owner: Dolgan
  tribes travel by wagon to new pasture about weekly, keep goats for milk and cheese and bison and cattle for meat,
  and gather wild roots. `fandom:River Lynsk [RotIQ; WFRP 1e p. 278]`; `fandom:Kislev#Climate [RotIQ pp. 6-10]`;
  `lex:Dolgan#Life on the Steppes [Something Rotten in Kislev pp. 55-56]`.
- **Analogue / vanilla**: `vanilla:STATE_URALSK arable 35, pasture, livestock`; `vanilla:STATE_NENETSIA arable 5, pasture, livestock`.
- **Layer**: Dc 65 %, ET 35 % -> boreal_forest; indicative 19. Today 59, farm, wheat/livestock.
- **Proposal**: `steppe`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  Numerically the same as the layer's boreal reading (indicative 12), but the class and subsistence say what the
  owner does with it: herd. No rye.
- **Tier**: C.

### STATE_NORTHERN_OBLAST — Northern Oblast (owner BOL; 21 provinces; 5,769 px; anchor 4363,594)

- **Identity**: canon's Northern Oblast, north of the Lynsk between Erengrad and Praag. City hub Zoishenk is the
  canon cattle town on the Tobol, largest settlement of the North Oblast. Confidence: high.
- **Canon**: classic steppe and low grass hills grazed by herds of horses and cattle; harsher, longer winters than
  the south; even the nomads camp for winter; "no agriculture to speak of" outside sheltered valleys; Ungol
  nomads with a few Gospodar stanitsas, every one sacked many times; southerners count it as Troll Country.
  Zoishenk is a stockaded cattle town and mustering point. `fandom:Northern Oblast [RotIQ pp. 58-59]`;
  `fandom:Zoishenk [RotIQ p. 59]`; `lex:Oblast#Locations [RotIQ pp. 51-56]`.
- **Analogue**: grazed, unploughed steppe. `vanilla:STATE_URALSK arable 35, pasture, livestock`;
  `vanilla:STATE_AKMOLINSK arable 45, pasture, rye livestock`.
- **Layer**: Df 69 %, Dc 31 % -> temperate_forest_hill dominant; indicative 65. Today 62, farm, wheat/livestock.
- **Proposal**: `steppe`, step **-1**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The biggest single correction in the file: the layer would make this farmland as dense as Ostland's; canon says
  cattle and horses and no crops. One step down for the cold (it still carries large herds and a cattle town).
  Indicative 18. Confirms NK-01 and adds the subsistence and crop calls.
- **Tier**: A.

### STATE_MAZHOROD — Mazhorod (owner KSV; 12 provinces; 2,739 px; anchor 4397,687)

- **Identity**: central Kislev between the Erengrad state and the Taiga, south of the Lynsk. Mazhorod is a canon
  place name: a battle site east of Krakjunov, itself east of Erengrad (`fandom:Kislev#Notable Settlements [Storm of Chaos p. 11]`,
  used for location only). Hubs Zhanyka, Choika TW. Confidence: medium.
- **Canon**: a novel describes the ford of Mazhorod with "an immense open plain" on either side, bare but for
  twisted shrubs, gorse and steppe thistle (`fandom:Mazhorod [Ursun's Teeth, novel]` — novel-tier, and it puts the
  ford on the Urskoy, which does not fit this state's position). Otherwise the Western / Eastern Oblast text:
  open steppe.
- **Layer**: Df 74 %, Dc 26 % -> temperate_forest_hill dominant; indicative 33. Today 29.
- **Proposal**: `steppe`, step **0**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Open oblast between the farmed south and the grazed north; nothing to move it off typical. Indicative 13.
- **Tier**: C (name located only by a campaign map note and a novel).

### STATE_THE_DOBRYRION — The Dobryrion (owner KSV; 21 provinces; 5,911 px; anchor 4442,734)

- **Identity**: the capital's own district on the Urskoy. City hub Kislev (canon); farm hub Gerslev, the canon
  provincial town of the southern Oblast; port hub Voltsara is listed under the Southern Oblast on Fandom.
  ("Dobryion Fields" is a canon battle site, `fandom:Kislev Timeline`.) Confidence: high.
- **Canon**: Kislev city stands on a loop of the Urskoy, practically on the Empire's border; it is listed as the
  largest settlement of the Southern Oblast, so that oblast's text applies in full (main farming region, oats
  almost everywhere, orchards, large settlements). Gerslev is the cultured provincial town of the same oblast.
  The Urskoy carries Kislev's exports to the Talabec; an older source says it makes Kislev's fields fruitful.
  `fandom:Southern Oblast [RotIQ pp. 54-55]`; `lex:Kislev_(city) [RotIQ pp. 9-11, 78-87]`; `lex:Gerslev [RotIQ p. 55]`;
  `lex:Urskoy [WFRP 1e pp. 278-279]`; `fandom:River Urskoy [Citadel Journal, Kislev: The Claws of the Great Bear pp. 8-9]`.
- **Analogue**: Moscow / Smolensk: the capital of a rye country.
  `vanilla:STATE_MOSCOW arable 60, farm, rye livestock`; `vanilla:STATE_SMOLENSK arable 62`; `vanilla:STATE_MINSK arable 90`.
- **Layer**: Dc 69 %, Df 31 % -> **boreal_forest** dominant; indicative 37. Today 64, wheat/livestock.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_farm`, crops `rye_farm livestock_ranch`.
  Class swap up from the layer's boreal reading: canon places the capital in the realm's mildest, most farmed
  region. Not `temperate_river_plain`: the only "fruitful Urskoy" line is a Citadel Journal article, against a
  rulebook that measures the region's fertility in oats. Indicative 92: the largest value in Kislev, as it should be.
- **Tier**: A.

### STATE_THE_TAIGA — The Taiga (owner PRA; 14 provinces; 4,337 px; anchor 4472,682)

- **Identity**: forest country between Praag's steppe and the capital, south of the Lynsk. Lexicanum places
  Bolgasgrad "within the Taiga" from the Old World website map, and Bolgasgrad is the port hub of the neighbouring
  Eastern Oblast state at the two states' border. Hubs Uvetsyn, Belava TW. Confidence: medium.
- **Canon**: the Taiga is a lawless, inhospitable land north of civilised Kislev, worked for the finest furs in
  the known world by the Sibyrian trappers (`fandom:Sibyrians [Kislev: The Claws of the Great Bear p. 11]` —
  Citadel Journal tier). Bolgasgrad is a fairly large Gospodar stanitsa with its own lancer rota. The Eastern
  Oblast has some croplands south of the Lynsk. `lex:Bolgasgrad [RotIQ p. 56; Old World website map]`;
  `fandom:Eastern Oblast [RotIQ p. 56]`.
- **Analogue**: the Russian north. `vanilla:STATE_VOLOGDA arable 70, farm, rye livestock`; `vanilla:STATE_ARKHANGELSK arable 15`;
  `vanilla:STATE_EAST_KARELIA arable 10`.
- **Layer**: Dc 100 % -> boreal_forest; indicative 9. Today 47.
- **Proposal**: `boreal_forest`, step **+1**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  The class agrees with the layer and the name. +1 because this taiga lies south of the Lynsk, where canon puts
  the Eastern Oblast's croplands and a large settled stanitsa: it is settled forest, not empty forest.
  Indicative 14.
- **Tier**: B.

### STATE_KISLEV_FOOTHILLS — Kislev Foothills (owner ROP; 14 provinces, 2 impassable; 3,097 px; anchor 4530,716)

- **Identity**: the wooded World's Edge foothills east of the capital. Hubs Deghov, Kalinora TW. Confidence:
  medium (descriptive name).
- **Canon**: east of the oblast the land gives way to large tracts of woodland climbing to the foothills, where
  orc and goblin tribes have settled and where Kislevites and dwarfs trade; the Eastern Oblast counts the foothills
  and lower peaks as its own and brings "much timber" down from them for the settled stanitsas.
  `fandom:Kislev#Lands of Kislev [RotIQ pp. 6-8]`; `fandom:Eastern Oblast [RotIQ p. 56]`; `lex:Kislev#Geography [RotIQ pp. 6-8]`.
- **Analogue**: the forested Ural foreland. `vanilla:STATE_PERM arable 70, farm, rye livestock`; `vanilla:STATE_URAL arable 60`.
- **Layer**: Dc 99 % -> boreal_forest; indicative 7. Today 51.
- **Proposal**: `boreal_forest`, step **0**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Canon and layer agree: timber country with greenskins in it. No row needed beyond the crops. Indicative 7.
- **Tier**: B.

### STATE_THE_ROPSALS — The Ropsals (owner ROP; 13 provinces, 2 impassable; 3,171 px; anchor 4579,622)

- **Identity**: the hill and mountain country north-east of Praag, under the High Pass. Hubs Novchozy, Zhidyrna,
  Plesk TW. The only text naming the Ropsals is a Total War tie-in short story, which calls them the "densely
  wooded highlands" of Kislev's Eastern Oblast (`fandom:Mother Ostankya [Things in the Wood, short story, p. 11]`
  — a lead, not rulebook canon). Confidence: low-medium.
- **Canon**: no rulebook land-use text for the name. Region level: the Eastern Oblast counts the World's Edge
  foothills and lower peaks as its own, forested, sending timber down; greenskins raid out of the mountains.
  `fandom:Eastern Oblast [RotIQ p. 56]`.
- **Layer**: Dc 67 %, ET 27 %, EF 5 % -> boreal_forest; indicative 9. Today 55.
- **Proposal**: `boreal_forest`, step **0**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Follows the layer; the story lead and the oblast text both say wooded upland. (The earlier lead had
  `highland_alpine` from a heightmap flag; the zone shares say forest first.) Indicative 7.
- **Tier**: C.

### STATE_SEPUKZY — Sepukzy (owner VOL; 22 provinces; 5,942 px; anchor 4538,598)

- **Identity**: the eastern end of the Eastern Oblast, from Praag toward the High Pass, named for the canon
  town. No hub rows. Confidence: medium-high (canon name, cited in the region worksheet).
- **Canon**: Sepukzy is one of the largest *settled* groups of Ungols in Kislev, with no permanent Gospodar
  residents, raising horse archers and dominated by the wise women. Volksgrad, the last major settlement before
  the High Pass and the caravans' supply stop, is walled against constant greenskin raids. The oblast around is
  "true steppeland", with croplands only south of the Lynsk and krugs of nomads on the northern and western steppe.
  `fandom:Sepukzy [RotIQ p. 56]`; `fandom:Volksgrad [RotIQ pp. 56-57]`; `fandom:Eastern Oblast [RotIQ p. 56]`;
  `lex:Oblast#Locations [RotIQ pp. 51-56]`.
- **Analogue**: `vanilla:STATE_AKMOLINSK arable 45, pasture, rye livestock`.
- **Layer**: Dc 84 %, ET 16 % -> boreal_forest; indicative 16. Today 61, farm, wheat/livestock.
- **Proposal**: `steppe`, step **-1**, `building_subsistence_pasture`, crops `livestock_ranch rye_farm`.
  Class swap to the steppe canon names; one step down for the cold and the raiding from two sides. Pasture for an
  all-Ungol horse country; rye kept second because the town is settled and caravans provision here. Indicative 18.
- **Tier**: B.

### STATE_GOROMADNY_HOLD — Goromadny Hold (owner VOL; 5 provinces, 2 impassable; 517 px in the climate index; anchor 4556,526)

- **Identity**: a small mountain state in the Goromadny range, north of Sepukzy. TW name. The wikis know the
  Goromadny mountains only as the range that links the Norse dwarf mountains to the World's Edge on the Old World
  website map (`fandom:Warhammer: The Old World`), and as a street name in Kislev city. No "hold" is described.
  Confidence: low.
- **Canon**: no canon land-use text found. Realm level: the north is always cold and infertile.
  `lex:Kislev#Geography [RotIQ pp. 6-8]`.
- **Layer**: ET 97 % -> highland_alpine (arctic_boreal_coast if the state sits at or above 60 N; the layer's
  latitude cut decides). Indicative 3. Today 31, rye/livestock.
- **Proposal**: `highland_alpine`, step **0**, `building_subsistence_pasture`, crops `livestock_ranch`.
  No evidence to step it; the size makes the step moot. Pasture and ranch-only because nothing in the realm text
  allows grain this far north in the mountains.
- **Tier**: C.

### STATE_HIGH_PASS — High Pass (unowned; 11 provinces, 5 impassable; 1,417 px; anchor 4637,574)

- **Identity**: the Belyevorota (High) Pass through the World's Edge and the site of **Karak Vlag** (city hub)
  on its southern side. Confidence: high.
- **Canon**: the northernmost and most treacherous pass: jagged peaks, glaciers, howling wind; the snow rarely
  melts even in summer and nothing weak survives there. Karak Vlag, famed for iron and masonry, was engulfed by
  the Chaos incursion of 2301 and vanished without trace; dwarfs do not speak of it. So at 2502 there is no hold
  to feed. `fandom:High Pass [RotIQ p. 11]`; `lex:High_Pass [RotIQ p. 7]`;
  `fandom:Karak Vlag [Dwarfs: Stone and Steel p. 38; White Dwarf 274 pp. 58-59]`.
- **Analogue**: `vanilla:STATE_ALTAI arable 10, pasture, livestock` (highland_alpine).
- **Layer**: ET 97 %, EF 2 % -> highland_alpine; indicative 7. Today 48, rye/livestock.
- **Proposal**: `highland_alpine`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  Canon's year-round snow is the evidence for the bottom step. The standing "dwarf holds herd" ruling is moot here
  (no dwarfs since 2301) but pasture is right for the land anyway. Indicative 3.
- **Tier**: A.

### STATE_THE_VELDT — The Veldt (owner OSM; 11 provinces; 3,163 px; anchor 4426,821)

- **Identity**: Ostermark's north-eastern grassland between the Gryphon's Wood and the World's Edge. Farm hub
  Heffengen is the canon horse-market village; Nagenhof, Weiler, Rheden TW. Confidence: high.
- **Canon**: great rolling plains, well suited to raising horses and long fought over with the Kislevites;
  Ostermark horses are famous for size and strength and buyers come from as far as Estalia to Heffengen's summer
  market; an Ungol-derived horse culture. Kislevite refugees are squatting on its edges and the breeders fear the
  newcomers "will begin fencing off and tilling" the grassland — i.e. it is ploughable land kept as range by
  choice. Heffengen's listed trades: agriculture, goats, cheese.
  `lex:Ostermark#Known features [Sigmar's Heirs pp. 68-69]`; `fandom:Ostermark [Sigmar's Heirs pp. 68-72]`;
  `fandom:Heffengen [Sigmar's Heirs p. 72]`; `fandom:Fortenhaf [Sigmar's Heirs pp. 71-72]`.
- **Analogue**: East Prussian and Hungarian horse country: the Trakehnen stud (founded 1731-32 on cleared land in
  East Prussia) held about 3,800 ha of fields beside 2,400 ha of meadow, and peasant mares bred to its stallions
  supplied the army's remounts (`rw:Trakehnen [https://en.wikipedia.org/wiki/Trakehner]`). Good mixed land used
  for horses, not semi-arid range. `vanilla:STATE_EAST_PRUSSIA arable 40, farm, rye livestock`.
- **Layer**: Df 82 %, Dc 18 % -> temperate_forest_hill; indicative 42. Today 64, wheat/livestock/vineyard.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_pasture`, crops `livestock_ranch rye_farm`.
  Keeps the layer's class against the earlier `steppe` lead: the steppe class would cut the arable to under a
  third, and in the engine ranches spend arable like farms do, so a horse country needs the land budget. The horse
  identity is carried by pasture subsistence and the ranch leading the list. Indicative 49.
- **Tier**: A.

### STATE_IRINASGRAD — Irinasgrad (owner KSV; 7 provinces; 1,861 px; anchor 4381,769)

- **Identity**: a small south-western border state between the Western Oblast, the Southern Oblast and
  Ostermark. TW name, no page in either wiki, no hub rows. Confidence: low.
- **Canon**: no canon land-use text found for the name. By position it is the Empire-border belt both oblast
  texts single out: the Western Oblast's border area is farmed to a significant extent, the Southern Oblast is the
  main farming region, and Zavstra, the border town sometimes counted in the south, is half Imperial.
  `fandom:Western Oblast [RotIQ p. 57]`; `fandom:Southern Oblast [RotIQ pp. 54-55]`; `fandom:Zavstra [RotIQ p. 58]`.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 29. Today 20.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_farm`, crops `rye_farm livestock_ranch`.
  Follows the layer and the southern rye-country reading. Indicative 29.
- **Tier**: C.

### STATE_NORTH_OSTLAND — North Ostland (owner OST; 10 provinces; 2,636 px; anchor 4216,690)

- **Identity**: the Forest of Shadows north of the Middle Mountains. City hub Ferlangen (canon). Confidence: high.
- **Canon**: Ostland is covered almost entirely by the Forest of Shadows, its people clearing patches for farms;
  the bull emblem is read as heavy use of cattle for meat, dairy, leather and draught; Ferlangen grew from a
  fur-trading and timber-felling camp; large areas round the Middle Mountains were never resettled after Gothor's
  rampage; Ostlanders envy the breadbasket provinces. `lex:Ostland [Sigmar's Heirs pp. 73-74; Uniforms & Heraldry pp. 36-39]`;
  `fandom:Ostland [Sigmar's Heirs pp. 73-76]`; `fandom:Ferlangen [Sigmar's Heirs p. 75]`; `fandom:Forest of Shadows [Sigmar's Heirs pp. 7, 73-76]`.
- **Analogue**: Livonia / Masuria: forest clearings, cattle, rye. `vanilla:STATE_RIGA arable 38, farm, rye livestock`;
  `vanilla:STATE_TARTU arable 18`.
- **Layer**: Df 100 % -> temperate_forest_hill; indicative 41. Today 54, wheat/livestock/vineyard.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Forest cap; cattle first on the heraldry reading. Indicative 27.
- **Tier**: A.

### STATE_CASTLE_ALEXANDRONOV — Castle Alexandronov (owner UNG; 12 provinces; 2,766 px; anchor 4266,599)

- **Identity**: the coast north of Erengrad on the edge of the Troll Country, named for the canon fortress. No
  hub rows. Confidence: medium-high.
- **Canon**: the castle stands north of Erengrad on the Troll Country border, on a 500-foot cliff, along a
  northern frontier that is mostly "windswept plain"; it exists to draw Chaos armies, not to hold farmland
  (`fandom:Castle Alexandronov [Citadel Journal 14, Kislev: The Claws of the Great Bear p. 10]` — Citadel Journal
  tier). The Troll Country seaboard is rock and salt marsh. `lex:Troll_Country [Sea of Claws pp. 34-37]`.
- **Layer**: Df 96 % -> temperate_forest_hill; indicative 42. Today 30, farm, wheat/livestock.
- **Proposal**: `steppe`, step **-1**, `building_subsistence_pasture`, crops `livestock_ranch`.
  Treated as Northern Oblast (border of the Troll Country, not inside it): grazed plain, no crops. Indicative 8.
- **Tier**: B.

### STATE_DUSHYKA — Dushyka (owner BOL; 12 provinces; 2,970 px; anchor 4416,591)

- **Identity**: between the Northern Oblast state and Praag, north of the Lynsk. TW name, no page, no hubs.
  Confidence: low.
- **Canon**: no canon land-use text found for the name. By position it is the east of the Northern Oblast
  (canon puts the near-abandoned stanitsa Krasicyno there): steppe grazed by horses and cattle, no agriculture.
  `fandom:Northern Oblast [RotIQ pp. 58-59]`; `fandom:Krasicyno [RotIQ p. 59]`.
- **Layer**: Dc 77 %, Df 23 % -> boreal_forest; indicative 16. Today 32.
- **Proposal**: `steppe`, step **-1**, `building_subsistence_pasture`, crops `livestock_ranch`. Same as the
  Northern Oblast. Indicative 9.
- **Tier**: C.

### STATE_EASTERN_OBLAST — Eastern Oblast (owner PRA; 20 provinces; 5,285 px; anchor 4473,623)

- **Identity**: Praag and the steppe around it on the Lynsk. City hub Praag; port hub Bolgasgrad and farm hub
  Volksgrad are canon East Oblast settlements. Confidence: high.
- **Canon**: Praag's grain is "sickly and in short supply" beside the south's; the city has been starved into
  submission by southern trade embargo and lives by luxury crafts instead; in 2301 it starved once the surrounding
  farms were destroyed; its ground is Chaos-tainted (Erengrad's land "escaped" that); nomads and steppe folk sell
  beasts, meat and hides in its squares. The oblast is mostly true steppe with some croplands south of the Lynsk.
  `fandom:Praag [RotIQ pp. 69-72]`; `lex:Praag [RotIQ p. 10]`; `fandom:Eastern Oblast [RotIQ p. 56]`;
  `fandom:Erengrad [RotIQ pp. 61-62]`.
- **Analogue**: `vanilla:STATE_TOBOLSK arable 53, farm, rye livestock` (steppe); `vanilla:STATE_AKMOLINSK arable 45, pasture`.
- **Layer**: Dc 88 %, Df 12 % -> boreal_forest; indicative 20. Today 57, wheat/livestock.
- **Proposal**: `steppe`, step **-1**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Steppe by canon; one step down on the direct statement about Praag's grain and soil. Farm, since there are
  peasant farms round the city (they are what the sieges destroy). Indicative 16. Confirms NK-01.
- **Tier**: A.

### STATE_LAURELORN_FOREST — Laurelorn Forest (owner LAU; 6 provinces; 1,487 px; anchor 4063,661)

- **Identity**: the core of the Eonir realm (the Ward of the Sun with Tor Lithanel; the Tor Lithanel hub row sits
  on this state's anchor though it is filed under West Nordland). Not in the economics worksheet yet (new state).
  Confidence: medium-high.
- **Canon**: a mixed and coniferous northern forest, older as an elf realm than Athel Loren; the core beyond the
  Demst is closed to humans on pain of death; the Eonir claim no farmland and tolerate humans only in the outer
  wards under logging treaties; inside Tor Lithanel's walls exotic fruit and nut trees are grown with magic.
  `fandom:Laurelorn Forest [Sigmar's Heirs pp. 63-66; Archives of the Empire I pp. 71-79]`;
  `fandom:Tor Lithanel [Archives of the Empire I p. 80]`; `lex:Nordland#Overview [Sigmar's Heirs]`.
- **Layer**: Df 97 % -> temperate_forest_hill; indicative 23. Today 30, wheat/livestock/vineyard.
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_orchard`, crops `livestock_ranch rye_farm`.
  An unfarmed elf forest: bottom step, as the earlier work did for Athel Loren. Orchard subsistence on the one
  canon food text (fruit and nut trees). The crop list is the class default only because a list is required: it
  should take whatever convention the Athel Loren dossier sets for elf forests. Indicative 10.
- **Tier**: A for the class and step; the subsistence and crops are a judgement call (open question).

---

## 3. Rows

(provisional rows are kept current here; final when "Progress" says complete)

```csv
state_key,lore_class,fertility_step,subsistence,crops,tier,note,source
STATE_WEST_NORDLAND,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,"Laurelorn outer wards and Salz-Demst zone: settlement and harvest capped by treaty; sheep and wool",lex:Nordland#Overview [Sigmar's Heirs p. 63ff] ; fandom:Laurelorn Forest [Archives of the Empire I] ; fandom:Hargendorf [Salzenmund: City of Salt and Silver pp. 106-107]
STATE_SCHADENSUMPF,temperate_forest_hill,-2,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,"Swampy morass north of Middenheim, little of worth; bog-iron villages",fandom:Middenland#Geography [Sigmar's Heirs pp. 53-58]
STATE_THE_WASTELAND,temperate_forest_hill,-2,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,"Tumble Downs: boggy hillocks, garden plots, thin sheep and cattle; Aarnau farms and fishes",lex:The_Wasteland#Locations [Marienburg: Sold Down the River pp. 6-10] ; fandom:The Wasteland#North [MSDtR pp. 8-9]
STATE_SOUTHERN_OBLAST,temperate_forest_hill,0,building_subsistence_farm,building_rye_farm building_livestock_ranch,A,"Kislev's main farming region: oats almost everywhere, some orchards, little steppe left",fandom:Southern Oblast [Realm of the Ice Queen pp. 54-55] ; lex:Kislev#Geography [RotIQ pp. 6-8]
STATE_BECHAFEN,temperate_forest_hill,0,building_subsistence_farm,building_rye_farm building_livestock_ranch,A,"Ostermark's agricultural core in the well-settled Gryphon's Wood; lumber and riverboats",lex:Ostermark [White Dwarf 326 p. 58; Sigmar's Heirs pp. 68-69] ; fandom:Ostermark [Sigmar's Heirs pp. 68-72]
STATE_SOUTH_TALABECLAND,temperate_forest_hill,0,building_subsistence_farm,building_rye_farm building_livestock_ranch building_vineyard,B,"Reik-Stir end of the Great Forest; Kemperbad brandy (vineyard is an inference)",fandom:Talabecland#Geography [Sigmar's Heirs pp. 77-81] ; fandom:Kemperbad [Sigmar's Heirs pp. 82-84]
STATE_VOLGEN,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,C,"TW name, no canon page; Great Forest cap from the province text",fandom:Talabecland#Geography [Sigmar's Heirs pp. 77-81]
STATE_NORTH_TALABECLAND,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,"Dark pine forest along the Talabec; timber, charcoal, pelts, river fish",fandom:Talabecland#Geography [Sigmar's Heirs pp. 77-81] ; fandom:River Talabec [WFRP 1e p. 283; Death on the Reik p. 23]
STATE_EAST_TALABECLAND,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,"Eastern Great Forest and the largely uninhabited Kolsa Hills",fandom:Talabecland#Geography [Sigmar's Heirs pp. 77-81]
STATE_WEST_OSTERMARK,temperate_forest_hill,-1,building_subsistence_pasture,building_livestock_ranch building_rye_farm,A,"Bleak Moors and Dead Wood: fens, sheep-herding, small dairy herds, crofts",lex:Ostermark#Known features [Sigmar's Heirs pp. 68-69] ; fandom:Ostermark [Sigmar's Heirs pp. 68-72]
STATE_GRYPHON_WOOD,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,"Forest arm on the upper Talabec; timber country with small villages",lex:Ostermark#Known features [Sigmar's Heirs pp. 68-69]
STATE_WESTERN_OBLAST,steppe,1,building_subsistence_farm,building_rye_farm building_livestock_ranch,A,"Treeless steppe; this southern Empire-facing half is farmed to a significant extent",fandom:Western Oblast [Realm of the Ice Queen p. 57] ; fandom:Milkavala [RotIQ pp. 57-58]
STATE_ERENGRAD,steppe,0,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,"Port on the Lynsk with a mostly-steppe hinterland; coast fishes and whales","fandom:Western Oblast [Realm of the Ice Queen p. 57] ; lex:Erengrad [RotIQ pp. 10, 61-62]"
STATE_BOHSENFELS,temperate_forest_hill,-1,building_subsistence_pasture,building_livestock_ranch building_rye_farm,B,"Ostland's Northern March: windswept grass; exports salted fish and sheep's-milk cheese",fandom:Ostland [Sigmar's Heirs pp. 73-76; Archives of the Empire I p. 13]
STATE_EAST_NORDLAND,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,"Forest-blanketed coast, people in cleared pockets; herring and cod, timber, sheep",lex:Nordland#Overview [Sigmar's Heirs p. 63ff] ; fandom:Nordland [Sigmar's Heirs pp. 63-68]
STATE_UNGOL_STEPPES,steppe,-2,building_subsistence_pasture,building_livestock_ranch,A,"Southern Troll Country: no farming possible; Ungol nomads following herds",fandom:Troll Country [Realm of the Ice Queen pp. 59-60; Sea of Claws p. 34] ; lex:Troll_Country [Sea of Claws pp. 34-37]
STATE_THE_GOLINYI,steppe,-2,building_subsistence_pasture,building_livestock_ranch,C,"Name not canon; far north beyond the Lynsk, Dolgan herders (goats, bison, cattle)",lex:Dolgan [Something Rotten in Kislev pp. 55-56] ; fandom:River Lynsk [RotIQ]
STATE_NORTHERN_OBLAST,steppe,-1,building_subsistence_pasture,building_livestock_ranch,A,"Steppe grazed by horses and cattle; no agriculture to speak of; Zoishenk cattle town",fandom:Northern Oblast [Realm of the Ice Queen pp. 58-59] ; lex:Oblast#Locations [RotIQ pp. 51-56]
STATE_MAZHOROD,steppe,0,building_subsistence_farm,building_livestock_ranch building_rye_farm,C,"Open central oblast; name placed by a campaign map and a novel only",fandom:Western Oblast [Realm of the Ice Queen p. 57] ; fandom:Mazhorod [Ursun's Teeth (novel)]
STATE_THE_DOBRYRION,temperate_forest_hill,0,building_subsistence_farm,building_rye_farm building_livestock_ranch,A,"Kislev city on the Urskoy, largest settlement of the Southern Oblast farming region","fandom:Southern Oblast [Realm of the Ice Queen pp. 54-55] ; lex:Kislev_(city) [RotIQ pp. 9-11, 78-87]"
STATE_THE_TAIGA,boreal_forest,1,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,"Fur taiga, but south of the Lynsk with croplands and the large stanitsa Bolgasgrad",fandom:Eastern Oblast [Realm of the Ice Queen p. 56] ; lex:Bolgasgrad [RotIQ p. 56] ; fandom:Sibyrians [Citadel Journal: Claws of the Great Bear p. 11]
STATE_KISLEV_FOOTHILLS,boreal_forest,0,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,"Wooded World's Edge foothills; timber for the stanitsas; greenskin country",fandom:Eastern Oblast [Realm of the Ice Queen p. 56] ; lex:Kislev#Geography [RotIQ pp. 6-8]
STATE_THE_ROPSALS,boreal_forest,0,building_subsistence_farm,building_livestock_ranch building_rye_farm,C,"Wooded highlands NE of Praag; name only in a Total War tie-in story",fandom:Eastern Oblast [Realm of the Ice Queen p. 56] ; fandom:Mother Ostankya [Things in the Wood (short story) p. 11]
STATE_SEPUKZY,steppe,-1,building_subsistence_pasture,building_livestock_ranch building_rye_farm,B,"True steppe east of Praag; Sepukzy is an all-Ungol settled horse town",fandom:Sepukzy [Realm of the Ice Queen p. 56] ; fandom:Eastern Oblast [RotIQ p. 56]
STATE_GOROMADNY_HOLD,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch,C,"TW name; far-northern mountain range, no canon land-use text",lex:Kislev#Geography [Realm of the Ice Queen pp. 6-8]
STATE_HIGH_PASS,highland_alpine,-2,building_subsistence_pasture,building_livestock_ranch,A,"Glaciated pass where snow rarely melts; Karak Vlag lost since 2301",fandom:High Pass [Realm of the Ice Queen p. 11] ; fandom:Karak Vlag [Dwarfs: Stone and Steel p. 38]
STATE_THE_VELDT,temperate_forest_hill,0,building_subsistence_pasture,building_livestock_ranch building_rye_farm,A,"Rolling ploughable grassland kept as horse range; Heffengen horse market",lex:Ostermark#Known features [Sigmar's Heirs pp. 68-69] ; fandom:Fortenhaf [Sigmar's Heirs pp. 71-72]
STATE_IRINASGRAD,temperate_forest_hill,0,building_subsistence_farm,building_rye_farm building_livestock_ranch,C,"TW name; Empire-border belt of the farmed south-west",fandom:Western Oblast [Realm of the Ice Queen p. 57] ; fandom:Southern Oblast [RotIQ pp. 54-55]
STATE_NORTH_OSTLAND,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,"Forest of Shadows with farms in cleared patches; cattle; Ferlangen furs and timber",lex:Ostland [Sigmar's Heirs pp. 73-74; Uniforms & Heraldry pp. 36-39] ; fandom:Ferlangen [Sigmar's Heirs p. 75]
STATE_CASTLE_ALEXANDRONOV,steppe,-1,building_subsistence_pasture,building_livestock_ranch,B,"Windswept plain on the Troll Country border north of Erengrad",fandom:Castle Alexandronov [Citadel Journal 14 p. 10] ; fandom:Northern Oblast [Realm of the Ice Queen pp. 58-59]
STATE_DUSHYKA,steppe,-1,building_subsistence_pasture,building_livestock_ranch,C,"TW name; east of the Northern Oblast: grazed steppe, no agriculture",fandom:Northern Oblast [Realm of the Ice Queen pp. 58-59]
STATE_EASTERN_OBLAST,steppe,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,"Praag: sickly scarce grain, tainted ground; true steppe with a few croplands",fandom:Praag [Realm of the Ice Queen pp. 69-72] ; fandom:Eastern Oblast [RotIQ p. 56]
STATE_LAURELORN_FOREST,temperate_forest_hill,-2,building_subsistence_orchard,building_livestock_ranch building_rye_farm,A,"Closed Eonir forest core, unfarmed; fruit and nut trees grown in Tor Lithanel",fandom:Laurelorn Forest [Sigmar's Heirs pp. 63-66; Archives of the Empire I pp. 71-79] ; fandom:Tor Lithanel [Archives of the Empire I p. 80]
```

## 4. Disagreements

### 4.1 With the climate layer's reading

| state | layer reads | row says | why |
|---|---|---|---|
| Northern Oblast, Castle Alexandronov, Ungol Steppes | temperate_forest_hill (Df 60-96 %) | steppe -1 / -1 / -2, pasture, ranch only | Canon: grazed steppe, "no agriculture to speak of"; Troll Country "no farming is possible". The layer would make these as dense as Ostland (indicative 65 / 42 / 38 against 18 / 8 / 8). The largest correction in the file. |
| Western Oblast, Erengrad, Mazhorod | temperate_forest_hill (Df 74-100 %) | steppe +1 / 0 / 0 | Canon: the Western Oblast is flat, steppe-like and almost devoid of forest. Indicative 87 / 85 / 33 falls to 38 / 25 / 13. |
| The Dobryrion | boreal_forest (Dc 69 %) | temperate_forest_hill 0 | Kislev city is the largest settlement of the Southern Oblast, the realm's mildest and main farming region. Indicative 37 rises to 92. |
| Eastern Oblast, Sepukzy, Dushyka, The Golinyi | boreal_forest (Dc 65-88 %) | steppe -1 / -1 / -1 / -2 | Canon: "true steppeland"; the numbers barely move (boreal 2.12 against steppe x0.67 = 3.06 per 1,000 px) but the class carries pasture and no forest identity. |
| The Taiga | boreal_forest | boreal_forest **+1** | Same class; stepped up for the croplands canon puts south of the Lynsk and the large stanitsa Bolgasgrad. |
| Schadensumpf, The Wasteland, Laurelorn Forest | temperate_forest_hill | same class, **-2** | Named swamp of no worth; devastated moor; closed elf forest. |
| West / East Nordland, North Ostland, Bohsenfels, Volgen, North / East Talabecland, West Ostermark, Gryphon Wood | temperate_forest_hill | same class, **-1** | Forest caps stated by canon (pockets cut out of solid woodland; covered almost entirely by forest; moor and fen). |
| High Pass | highland_alpine | same class, **-2** | Snow rarely melts even in summer. |

No disagreement (row only fixes crops or subsistence): Southern Oblast, Irinasgrad, Bechafen, South Talabecland,
The Veldt, Kislev Foothills, The Ropsals, Goromadny Hold.

**Crops, every state**: the layer's class defaults would hand the steppe states `livestock_ranch, wheat_farm,
vineyard`. No row keeps wheat, and only South Talabecland keeps a vineyard (as an inference). Vanilla gives rye and
livestock to every state of its own rye belt.

**A model note for #3677, not a lore finding**: `boreal_forest` at 2.12 per 1,000 px gives single-digit arable to
mod-sized states (The Taiga 9-14, Kislev Foothills 7, The Ropsals 7), because vanilla's boreal states are ten times
the area. `validate_map.py` warns below 10. The rows are what canon supports; whether the class density suits
small states is the model's call.

### 4.2 With the earlier part-A leads (`agro_climate_overrides_draft.md`, `state_climate_classes.csv`)

| lead | what it said | this dossier | reason |
|---|---|---|---|
| NK-01 | steppe, down 1 for Ungol Steppes, Northern Oblast, Eastern Oblast, Castle Alexandronov, Dushyka; 0 for Erengrad | **kept**, with Ungol Steppes lowered to -2, and pasture / ranch-only added for the northern four | Ungol Steppes' hubs are Troll Country places, where canon rules farming out. The oblast pages (not read for part A) give the grazing and no-agriculture text. |
| NK-06 | Southern Oblast, Western Oblast, Mazhorod, The Dobryrion, Irinasgrad: steppe, up 1 | **changed**: Southern Oblast, The Dobryrion, Irinasgrad to temperate_forest_hill 0; Western Oblast steppe +1; Mazhorod steppe 0 | RotIQ p. 54 says the Southern Oblast has little steppe left and looks like the rural Empire. Part A had only the realm sentence. |
| NK-02 (Troll Country), NK-03, NK-04, NK-05 | Norsca-file states | not in this file | sibling dossier. |
| Sepukzy, Kislev Foothills as boreal_forest; The Golinyi, The Ropsals as highland_alpine | class by heightmap flag | Sepukzy steppe -1; Foothills boreal; Golinyi steppe -2; Ropsals boreal | Sepukzy is a canon steppe town of the Eastern Oblast; the zone shares put forest before alpine in the Ropsals; the Golinyi is Dolgan herding country by owner. |
| High Pass, Goromadny Hold as highland_alpine | same class | High Pass -2 added | canon snow text. |
| The Veldt as steppe | class:steppe | temperate_forest_hill 0 + pasture | canon makes it ploughable grassland coveted by farmers; see the entry. |
| EMP-05 Great Forest "cap at mid, never high" | 0 | -1 for Volgen, North and East Talabecland; 0 for South Talabecland | the only local texts are dark pine forest and uninhabited hills. |
| EMP-06 Nordland, Gryphon Wood down 1 | -1 | **kept** | confirmed. |
| EMP-07 The Wasteland down 2 | -2 | **kept** | confirmed; no polder text exists for the northern Wasteland either. |
| Schadensumpf: no entry | 0 | **-2** | the Middenland page has the swamp text part A lacked. |
| Bechafen, West Ostermark, Bohsenfels, North Ostland: no entry | 0 | Bechafen 0; West Ostermark -1 pasture; Bohsenfels -1 pasture; North Ostland -1 | province pages read in full this time. |
| `canon_rivers.csv`: Lynsk at Southern Oblast, Tobol at Erengrad (tier C, "look misplaced") | — | **both wrong** | The Lynsk runs Praag to Erengrad: it belongs to the Erengrad and Eastern Oblast states (and bounds the Northern Oblast). The Tobol bounds the Northern Oblast (Zoishenk stands on it); the Lesser Tobol bounds the Southern Oblast. The Urskoy at The Dobryrion is right. |

---

## 5. Open questions for Chris

1. **Southern Kislev's level.** I put the Southern Oblast, The Dobryrion and Irinasgrad at typical forest-hill
   fertility (rye country, like Smolensk or Minsk), not at black-earth richness and not on the river-plain class.
   The one line that could lift The Dobryrion is the Citadel Journal's "fruitful" Urskoy. Lift it a step, or leave it?
2. **West Nordland / Laurelorn Forest split.** The Se Athil and Tor Lithanel hub rows are filed under West Nordland
   but sit on the coast and on the Laurelorn state's anchor. I treated West Nordland as the outer wards plus the
   Salz-Demst settlement zone (-1) and Laurelorn Forest as the closed core (-2). If West Nordland is meant to be
   mostly elf forest too, it should drop to -2.
3. **Elf-forest convention.** Laurelorn Forest carries orchard subsistence (fruit and nut trees at Tor Lithanel)
   and the default crop list. It should match whatever the Athel Loren dossier settles. Gryphon Wood has a wood-elf
   owner tag but canon makes it an ordinary human-settled Ostermark forest; I treated it as the latter.
4. **The Veldt's class.** Forest-hill with pasture (my row) or steppe (the earlier lead)? The row keeps the arable
   budget that horse ranches need in the engine.
5. **Kemperbad's vineyard.** Canon says finest brandy, not vineyards. Keep the inferred vineyard on South
   Talabecland or drop it? Also: Kemperbad is a Reikland free town in canon, sitting in a Talabecland state here.
6. **Pasture or farm on the moors.** West Ostermark and Bohsenfels are pasture on named herding and cheese texts;
   The Wasteland is farm (Aarnau farms and fishes) though the Tumble Downs text reads as crofting with thin stock.
   Vanilla uses farm for its moor states.
7. **Fishing villages.** No state takes `building_subsistence_fishing_village`. Bohsenfels (salted fish exports),
   East Nordland (herring coast) and Erengrad are the candidates if Chris wants one on this coast.
8. **TW-named states with no canon**: Volgen, Irinasgrad, Dushyka, The Golinyi, Goromadny Hold (and The Ropsals,
   named only in a Total War tie-in story). Their rows rest on position and the regional text. "Goromadny Hold":
   is a hold meant to stand there? Nothing read describes one.
9. **The Wheatlands.** Chernozavtra's black-soil Wheatlands read as Kislev's colonies beyond the High Pass, not as
   part of the oblast; Fandom files Chernozavtra under the Southern Oblast. If Chris places the Wheatlands inside
   drawn Kislev, one southern state would deserve wheat and a step up.
10. **Where the Blight lies.** The tainted peat moor is in the canon Western Oblast; I could not tell whether it
    falls in the Western Oblast state or the Erengrad state. Whichever holds it could lose a step.
11. **`canon_rivers.csv`** needs the Lynsk and Tobol rows moved (section 4.2). The layer has no river signal, and
    I propose no river-plain state in this file, so nothing in the rows depends on it.

---

## 6. Pages read

**Lexicanum** (whfb.lexicanum.com, 2026-11-19; 22 pages, before and after the Cloudflare challenge, which I did
not try to pass): Kislev, Oblast, Kislev_(city), Erengrad, Praag, Urskoy, Lynsk, Ungol, Gospodar, Ropsmenn, Dolgan,
Troll_Country, High_Pass, Bolgasgrad, Gerslev, Chernozavtra, Zamoski, Ostermark, Ostland, Nordland, Talabecland,
The_Wasteland. Not found (404 / no title): Tobol. Not reached before the challenge: Great_Rasputia, Kharakorsi,
Tahmak_(city) (all Old World-era eastern steppe cities, outside this file).
**Not corroborated on Lexicanum** (Fandom or dump only): the four oblast pages (Lexicanum has one short Oblast
page), Kvas, Koumiss, Oblast Elk, Sepukzy, Volksgrad, Zoishenk, The Blight, Laurelorn's wards, Tor Lithanel,
Middenland / Schadensumpf, Kemperbad, the Northern March, Heffengen, Fortenhaf, Castle Alexandronov, Sibyrians.
The two wikis did not contradict each other on any claim used here.

**Fandom Warhammer Wiki** (read live 2026-11-19 through the browser pane; spot-checked against the local dump
`sources/wiki/pages/` on 2026-11-20 for footnotes and infoboxes): Kislev, Southern Oblast, Western Oblast,
Northern Oblast, Eastern Oblast, Oblast, The Blight, Troll Country, River Lynsk, River Urskoy, River Tobol,
Zoishenk, Sepukzy, Volksgrad, Vitevo, Resov, Milkavala, Zavstra, Krasicyno, Zvenilev, Castle Alexandronov, Mazhorod,
Kvas, Koumiss, Zhidovsk, Leblya, Erengrad, Praag, Kislev (City), Ungols, Gospodars, Dolgan, Roppsmenn, Oblast Elk,
Kislevite Riding Horse, Karak Vlag, High Pass, Gerslev, Zamak Spayenya, Bolgasgrad, Kraka Ravnsvake, Steppes Nomad,
Horsemaster, Sibyrians, Eastern Steppes, Kislev Timeline, Urszebya, Horse Coper, Mother Ostankya (dump), Kislevarin
(dump), Old World Trade and Economy (dump), Nordland, Ostland, Ostermark, Talabecland, Talabec (Grand Duchy),
The Wasteland, Laurelorn Forest, Tor Lithanel, Middenland, Great Forest, Forest of Shadows, River Talabec,
Salzenmund, Dietershafen, Norden, Hargendorf, Ferlangen, Bohsenfels, Salkalten, Bechafen, Essen, Heffengen,
Fortenhaf, Kemperbad, Lieske, Bek, Aarnau, Bleak Moor (Albion's, not relevant), Ivory Road (not relevant).
No article exists for: Volgen, Irinasgrad, Dushyka, Golinyi, Goromadny (range or hold), Resvynhaf, Fort Jakova,
Uvetsyn, Deghov, Kalinora, Novchozy, Zhanyka, Kzarla, Lochrafurt, Horno, Ossino, Nagenhof, Stedum, Salfen,
Vorbegwerk, Schadensumpf, Gryphon Wood, Veldt, Northern March, Silver Hills (the last five are covered inside their
province articles).

**Web (real-world half)**:
- https://en.wikipedia.org/wiki/Agriculture_in_the_Russian_Empire — black-earth vs non-black-earth zones, rye and oats, three-field rotation.
- https://en.wikipedia.org/wiki/Chernozem — belt extent, humus, fertility.
- https://en.wikipedia.org/wiki/East_European_forest_steppe — extent, Dfb climate, over half arable today.
- https://en.wikipedia.org/wiki/Rye — rye as the bread grain east of the France-Germany line; cold and poor-soil tolerance; kvass.
- https://en.wikipedia.org/wiki/Economy_of_the_Russian_Empire — little pre-1861 data; Pontic steppe opened late.
- https://en.wikipedia.org/wiki/Stanitsa — the Cossack village unit.
- https://en.wikipedia.org/wiki/Pontic%E2%80%93Caspian_steppe — extent and nomad peoples.
- https://en.wikipedia.org/wiki/Wild_Fields — raided, thinly settled steppe until the 1780s.
- https://en.wikipedia.org/wiki/Trakehner — East Prussian stud, fields and meadow.
- https://en.wikipedia.org/wiki/History_of_the_forest_in_Central_Europe — clearance phases; no usable 1800 percentage.
- https://en.wikipedia.org/wiki/Drenthe — poverty of the heath province.
- https://en.wikipedia.org/wiki/Province_of_Pomerania_(1815%E2%80%931945) — sheep breeding, rural character.
- Search digest only (papers not opened): Zhao et al. 2020, cropland of European Russia 1696-1914 (https://www.researching.cn/articles/OJf0ce55b990144025); Tsvetkov 1957 forest cover as cited on cyberleninka.ru.
- 404: https://en.wikipedia.org/wiki/Economy_of_the_Polish–Lithuanian_Commonwealth.

**Limits of the real-world half**: I found no province-level table of arable share for 1800-1850 Russia, Poland
or the Baltic; the figures above are regional and partly second-hand. The calibration therefore leans on vanilla's
own state values, which is what the brief names as the calibration table.

**Repo and vanilla files read**: `map_data/state_regions/01_kislev.txt`, `states_l_english.yml`, `hub_worksheet.json`,
`land_economics_worksheet.csv`, `land_regions_worksheet.csv`, `state_climate_index.json`, `state_ownership.json`,
`state_climate_classes.csv`, `canon_rivers.csv`, `climate_lore.json`, `agro_climate_overrides_draft.md`,
`arable_land_engine_research.md` (sections 4-6), `vanilla_state_climate_classes.csv`, `common/buildings/` ids,
vanilla `map_data/state_regions/*.txt`.

## Progress

- 2026-11-20: file created with the realm picture.
- 2026-11-20: entries and rows 1-11 of 33 written (West Nordland .. Gryphon Wood).
- 2026-11-20: entries and rows 12-22 written (Western Oblast .. Kislev Foothills).
- 2026-11-20: entries and rows 23-33 written (The Ropsals .. Laurelorn Forest). All 33 states have an entry and a row.
- 2026-11-20: csv quoting fixed (Erengrad, The Dobryrion); sections 4-6 written. **Complete.**
