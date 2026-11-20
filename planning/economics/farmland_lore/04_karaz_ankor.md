# Farmland lore dossier: Karaz Ankor (`map_data/state_regions/04_karaz_ankor.txt`)

Board item #3682, child of epic #3675. Research run 2026-11-19, resumed 2026-11-20. Status: all 37 states have an entry and a row.

Scope note. The file holds **37 states** and it is not the whole Dwarf realm. It covers the central and southern World's Edge Mountains (Karaz-a-Karak, Zhufbar, Karak Kadrin, Karak Azul, Karak Eight Peaks and the fallen holds and passes between them), the northern stretch around Karak Ungor, the Sour Sea and Nagashizzar, and the Nehekharan east coast around Lahmia. It holds **no** Grey Mountains, Black Mountains or Vaults state, so Karak Izor, Karak Azgaraz, Karak Norn, Karak Hirn, Barak Varr and Kraka Drak are researched here only to test the standing "grain holds" ruling, not to propose rows.

Citation forms: `fandom:<Title>#<Section> [GW book, page]` (Fandom Warhammer Wiki, read live in the browser on 2026-11-19, same wiki as the local dump), `lex:<Page> [GW book, page]` (Lexicanum, read 2026-11-19), `rw:<region> [URL]`, `vanilla:STATE_X arable N, subsistence, crops`. Fandom scrambles the word "Roleplay" in its source lists; the books meant are the WFRP ones named here.

## 1. Realm picture

### 1.1 Canon: how Dwarfs eat

- **Farming land is scarce and Dwarfs farm badly; they hunt, and grain and fruit come in by trade** for metalwork and gold. `lex:Dwarf#Economy [White Dwarf 152 (UK), The Dwarf Realms, p. 51]`
- **The highlands around most holds are barren, poor for both plough and pasture.** A few herder families keep goats among the peaks for milk and meat, rangers hunt, and the few farmers grow stunted barley and wheat on steep fields inside a karak's walls. Wheat becomes stonebread, barley becomes beer. More food is bartered from the human lowlands (venison, beef). `fandom:Dwarfs#Economy [WFRP 1e Dwarfs: Stone and Steel, p. 16]`
- **The Farmers and Herders Guild never recovered from the Goblin Wars**; many holds depend on trade with humans for food. Remaining farmers mostly grow grain for the Brewers Guild; a few clans grow edible fungi. Herders keep goats (wool, milk) and mountain cattle; hard cheese is a staple and every hold has its own. `fandom:Farmers_and_Herders_Guild [Stone and Steel, p. 18; Archives of the Empire I]`
- **Farmer guilds are the smallest craft guilds** because Empire trade supplies the food; **herder guilds are still common** and give meat, wool and cheese through the winter. `fandom:Dwarfs#Guilds [Stone and Steel, pp. 17-20]`
- The Goblin Wars killed herds, stopped hunting and destroyed crops, to the point of starvation in some holds; stonebread (wild grain plus rock dust) dates from then. Dwarfs bred a hardy mountainside barley. `fandom:Stonebread [Stone and Steel, pp. 15-16]`
- A hold's surface works include goat-herding stations, breweries and farms. `lex:Dwarf-hold#Surface` (the page marks this passage "Needs Citation": weak)
- The Empire is the crucial source of food imports. `fandom:Dwarfs#Foreign_relations [WFRP 4e Dwarf Player's Guide, p. 25]`

**Reading.** Herding is the documented, still-common Dwarf food base; grain is a minor, brewing-led activity; the deficit is imported. In Vic3 terms that is `building_subsistence_pasture` (0.25 grain against a farm's 1.0, plus meat and fabric), which makes a hold a grain importer by construction. Canon supports Chris's 2026-10-05 ruling for the realm as a whole.

### 1.2 Canon: which holds grow grain (test of the "three grain holds" list)

| Hold | Evidence read | Verdict |
|---|---|---|
| Karak Azgaraz (not in this file) | Fortified farms grow mountain hops, barley and wheat plus vegetables; herders bring mountain cattle down in summer; goats high up. `fandom:Karak_Azgaraz [WFRP 3e Book of Grudges, pp. 16-20]`; small hop farms by Copper Tarn `lex:Karak_Azgaraz` | Strong. The source is the WFRP 3e Book of Grudges, **not** Stone and Steel p. 18. |
| Kraka Drak (not in this file) | The hold exports amber, grain, sapphires and silver `lex:Kraka_Drak [footnote 6b; the earlier draft resolves it to Lords of Stone and Steel, which I did not re-check]`; village Khazid Ravik produces grain, cheese, fur and wool `fandom:Kraka_Drak [WFRP 4e Lords of Stone and Steel]` | Strong. |
| Karak Izor (not in this file) | Small **human** settlements farm the sheltered valleys under Dwarf watch `lex:Karak_Izor [Stone and Steel, pp. 36-37]`; Hochstadt is a human farming town (grain, cheese, wool); the hold produces grain, metals and silver for trade `[Lords of Stone and Steel]` | Supported, but the farmers are human. |
| **Karak Kadrin (in this file: `STATE_PEAK_PASS`)** | Village Khazid Rhyn, about 2,800 people, produces grain, wool and metal `fandom:Karak_Kadrin#Settlements [Lords of Stone and Steel]`; the hold rises from a river valley `[Dragonslayer, ch. 6]` | Same grade of evidence as Kraka Drak's village. |
| Karak Hirn, Barak Varr, Karak Gantuk (not in this file) | Each has one or two villages producing grain with wool or cheese `fandom:Karak_Hirn, fandom:Barak_Varr, fandom:Karak_Gantuk [Lords of Stone and Steel]` | Same grade. |
| Zhufbar (in this file) | Most food, clothing and daily goods come by trade with other holds and the Empire `fandom:Zhufbar [Stone and Steel, p. 28]` | Against farm. |
| Karak Eight Peaks (in this file) | Crops fed the city and cattle were kept until the ash of -513 IC `lex:Karak_Eight_Peaks [Dwarfs 8e, pp. 20-21]`; `fandom:Karak_Eight_Peaks [Trollslayer]` | Historic grain; a besieged ruin in 2502. |
| Karak Angkul (in this file) | Pastures outside the hold give milk and cheese `lex:Karak_Angkul [Thanquol's Doom, ch. 6]` | Pasture. |

**Finding.** The three-hold list is right as far as it goes, but WFRP 4e's Lords of Stone and Steel gives a grain village to nearly every standing hold it lists, Karak Kadrin included. Either the list widens to "any standing hold whose gazetteer names a grain village" (in this file: Karak Kadrin only) or the gazetteer villages are treated as too small to change a state's subsistence type. I propose the first for `STATE_PEAK_PASS` and flag it (section 5, Q1).

### 1.3 Canon: greenskins, Skaven, undead and Nehekhara in this file

- **Night Goblins** grow many kinds of fungus for food, brewing and squig bait, and herd cave squigs. `fandom:Night_Goblin [Orcs & Goblins 8e, pp. 11, 52]`; `lex:Night_Goblin [Orcs & Goblins 6e, pp. 13-18]` (raid for food and slaves; netters catch squigs)
- **Misty Mountain** by the Sour Sea teems with goblins farming fungus in warpstone-laden caverns and raising outsized squigs. `fandom:Misty_Mountain [Orcs & Goblins 8e, pp. 21-23]`
- **Red Fangs** (Black Crag orcs) are described as landless nomads who follow war-boar migrations and come back yearly to the plateau below Karak Eight Peaks. `fandom:Red_Fangs [Orcs & Goblins Collector's Guide (6e), p. 4]`
- **Sour Sea, Desolation of Nagash, Cripple Peak.** A warpstone meteor poisoned the sea, killing or mutating its life and sickening the vegetation around it; Nagash's mining turned the shore into the wasteland called the Desolation; the surviving locals became ghouls. The Desolation is a desert around Nagashizzar. `lex:Sour_Sea [Undead 4e, pp. 14-16]`; `lex:Desolation_of_Nagash [Undead 4e, p. 7]`; `lex:Nagashizzar [Undead 4e, pp. 6-10]`; `fandom:Desolation_of_Nagash [White Dwarf 249, p. 37]`
- **Nehekhara** was fertile once and is now barren wasteland and searing desert, its fertility drained by Nagash's Great Ritual. `fandom:Nehekhara [Tomb Kings 8e]`; `lex:Nehekhara [Tomb Kings 8e, p. 17]`. Mahrak sits on the east side of the mountains at the end of the Charnel Valley `lex:Mahrak [Tomb Kings 6e, pp. 18-19]`; Lybaras can only be approached from the north, past ruined Lahmia `fandom:Lybaras [Tomb Kings 8e, p. 19]`.
- **Death Pass** runs through snow-capped mountains to the bleak Dark Lands. `fandom:Death_Pass [The Old World: Arcane Journal, Orc & Goblin Tribes, p. 9]`. The Dark Lands beyond are dusty, barren plains. `lex:Lair-Nests_of_the_Dark_Lands [Skaven 7e]`
- Nothing read says Skaven or greenskins plough anything in these mountains.

### 1.4 Real-world analogues, c. 1800-1850

The setting borrows the Alps and Carpathians for the central and northern range, arid ranges (Zagros, Hindu Kush, Hejaz) for the dry south, and the Red Sea desert coast for Lahmia's shore.

- **Alps: vertical transhumance.** Herds go up in spring, to the high alps in summer, down by late September; pastures are mostly below 2,400 m. Valley-floor villages grew grain and hay; in the north fields were cropped 2-5 years then left as meadow 3-10. From about 1300 cattle became the main activity along the northern edge. Alpine pasture is 35 % of Swiss farmland and 13 % of the country today, a quarter of Austria's farmland. `rw:Alps [https://en.wikipedia.org/wiki/Alpine_transhumance]`
- **Alps: grain limits.** Rye was sown to 1,800-2,000 m in the Aosta valleys, wheat and maize lower (undated; via search excerpt of sustainweb.org). The short season became a hard limit on intensifying after about 1700; Alpine population 5.8 M in 1800 on about 190,000 km2 (roughly 31 per km2, my division). `rw:Alps [https://en.wikipedia.org/wiki/History_of_the_Alps]`
- **Switzerland, land shares c. 1900.** Unproductive 25.2 %, forest 21.2 %, arable plus pasture together 8,427.7 of 15,951 sq mi (53 %), vineyards 108.7 sq mi. `rw:Switzerland [https://en.wikisource.org/wiki/1911_Encyclopædia_Britannica/Switzerland/Geography]`
- **Switzerland, arable.** 1905: 255,180 ha arable of 1,059,930 ha farmland, 134,220 ha under grain; arable shrank by about two thirds between 1855 and 1914 as railways brought cheap grain, so c. 1855 it was roughly 0.75 M ha, about 18 % of the country (my arithmetic), almost all on the Mittelland. Valais fed itself in grain in the early modern period; Graubünden and Ticino imported. `rw:Switzerland [hls-dhs-dss.ch articles 027895 "Wiesen", 013936 "Getreidebau"]` (search excerpts only; the site refused WebFetch)
- **Tyrol.** Described as mainly pastoral, partly agricultural (1911 Britannica, no figures). One excerpt gives 41.5 % of Tyrol's cultivated land as pasture (undated Austrian geography text, via search). I found no 1830s arable share for Tyrol: **not verified**.
- **Carpathians.** Sheep transhumance peaked in the 18th-19th centuries (Mărginimea Sibiului); Podhale flocks graze the hala from 23 April to 29 September. No land-share figure found. `rw:Carpathians [https://en.wikipedia.org/wiki/Transhumance; search excerpts]`
- **Caucasus.** Barley grows in the high valleys to 7,000-8,000 ft; cattle-breeding is the mountaineers' main resource; sheep move between Tusheti and the Kakheti plain over a 2,826 m pass. `rw:Caucasus [https://en.wikisource.org/wiki/1911_Encyclopædia_Britannica/Caucasia; https://en.wikipedia.org/wiki/Transhumance]`
- **Arid ranges.** Zagros tribes (Bakhtiari, Qashqai) move between winter lowlands and summer pastures at 3,700-4,600 m; in Nuristan villagers stay to irrigate terraces of millet, maize and wheat while herdsmen take goats up. `rw:Zagros / Hindu Kush [https://en.wikipedia.org/wiki/Transhumance]`
- **Desert coast.** Egypt's Eastern Desert gets under 25 mm of rain a year; the article names mining, quarrying and caravan routes and no agriculture. `rw:Eastern Desert [https://en.wikipedia.org/wiki/Eastern_Desert]`

**What the analogue says.** A real alpine state is mostly rock, forest and grass; its ploughland is a thin valley-floor strip; its people still grew their own rye and barley up to about 2,000 m and lived on dairy. Real mountaineers c. 1836 were farmer-herders, which is why vanilla gives them farms.

### 1.5 Vanilla calibration

| Analogue | Vanilla states |
|---|---|
| Alps | `vanilla:STATE_TYROL arable 30, farm, wheat_farm livestock_ranch vineyard`; `STATE_EAST_SWITZERLAND 40, farm, rye_farm livestock_ranch vineyard`; `STATE_WEST_SWITZERLAND 50, farm, rye_farm livestock_ranch vineyard`; `STATE_SAVOY 20, farm, wheat ranch cotton vineyard` (all `highland_alpine`) |
| Carpathians | `STATE_NORTHERN_TRANSYLVANIA 50, farm, wheat ranch vineyard`; `STATE_SOUTHERN_TRANSYLVANIA 50, farm`; `STATE_SLOVAKIA 105, farm`; `STATE_BUKOVINA 100, farm` (all `temperate_forest_hill`) |
| Caucasus | `STATE_GREATER_CAUCASUS 85, farm`; `STATE_DAGESTAN 30, farm`; `STATE_NORTH_CAUCASUS 25, farm, wheat ranch`; `STATE_ARMENIA 60, farm`; `STATE_KARS 10, farm` (`highland_alpine`) |
| Arid ranges | `STATE_LURISTAN 40, orchard`; `STATE_PERSIAN_KURDISTAN 50, orchard`; `STATE_KABUL 80, farm`; `STATE_YEMEN 70, pasture`; `STATE_NGARI 60, pasture, livestock_ranch`; `STATE_ALTAI 10, pasture, livestock_ranch` (`highland_alpine`) |
| Desert coast | `STATE_SINAI 10, orchard, livestock_ranch`; `STATE_HEDJAZ 20, pasture, livestock_ranch`; `STATE_NEJD 10, pasture`; `STATE_OMAN 10, pasture` (`open_desert`) |

Vanilla's temperate mountain states are farms (Alps 5 of 5, Caucasus 3 of 3; `planning/economics/arable_land_engine_research.md` section 6). Its highland pasture states are the dry, high ones (Ngari, Altai, Yemen). World-block density: `highland_alpine` 5.31 arable per 1,000 px against `temperate_forest_hill` 15.51 and `open_desert` 0.99.

### 1.6 Where canon and analogue disagree, and which I follow

- **Subsistence type.** Analogue and vanilla say farm; canon says Dwarfs herd, barely farm and import grain. I follow canon (pasture) for every mountain state except `STATE_PEAK_PASS`, per the pinned "lore first" rule. For the dry southern range the analogue (Ngari, Altai, Yemen, Zagros nomads) agrees with pasture anyway.
- **Crops.** The highland default list carries `building_vineyard` (Tyrol, Switzerland). Canon has Dwarfs brewing beer from barley and hops and importing fruit; no page read mentions vines in the World's Edge Mountains. I drop the vineyard everywhere here. Barley and hops have no building; `building_wheat_farm` stands in (canon names wheat for stonebread).
- **Fertility.** Canon calls the land round most holds barren (Stone and Steel p. 16), harsher than the real Alps. I have **not** applied a realm-wide step down, because `highland_alpine` is already a third of forest-hill density; I step down only where a page speaks about the place itself. Whether the realm sentence should make it -1 everywhere is Q2.
- **Climate class.** The climate layer reads most of the range between Karaz-a-Karak and Karak Eight Peaks as cold desert (BWk) and the Lahmia coast as tropical savanna (Aw). Canon says snow-capped mountains for the first and magical desert for the second. I follow canon in both (section 4).

## 2. Per-state entries

File order. Owners from `mapgen/derived/state_ownership.json`; hubs from `hub_worksheet.json` through `hub_anchors_index.json` ("TW" = cited there to the TWW3 Old World mod region table, a lead, not canon). "Layer" is the dominant class of `state_climate_index.json` under the brief's zone mapping, with the zone shares. Shared references: **[R1]** = the realm canon in 1.1 (Stone and Steel pp. 16-18; White Dwarf 152 p. 51); **[R2]** = Night Goblin fungus and squig canon in 1.3; **[R3]** = Nehekhara's drained desert in 1.3.

### STATE_RED_CLOUD_MOUNTAINS: Red Cloud Mountains (id 191, unowned)
- **Identity.** Karag Orrud, "Red Cloud Mountain", the southernmost of the three great volcanoes of the range; home of the Red Cloud goblin tribe. Hub Karag Orrud (mine) confirms. Confident. `fandom:Karag_Orrud [Dwarfs 6e revised, p. 23; Orcs & Goblins 7e, p. 14]`
- **Canon.** Earthquakes and tremors kept the Dwarfs from founding holds here; miners come and go; goblins tunnel. No land-use text.
- **Farm or pasture.** Neither is stated. Goblin tribe, so herding and fungus [R2]: pasture, weak.
- **Analogue.** Dry volcanic range at about 27 N: Yemen or Hejaz highlands. `vanilla:STATE_YEMEN arable 70, pasture`; `STATE_HEDJAZ 20, pasture`.
- **Layer.** `steppe` (BSk 63 %, BWk 23 %, BWh 10 %, ET 3 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. A named volcano massif is mountain land; nothing read says its soil is worse or better than typical. **Tier B.**

### STATE_SOUTHERN_WORLDS_EDGE: Southern Worlds Edge (id 193, owner MAH Mahrak)
- **Identity.** The southern range plus Mahrak, which lies on the east side of the mountains at the end of the Charnel Valley (the tag's capital comment names Mahrak). Confident on Mahrak, by owner. `lex:Mahrak [Tomb Kings 6e, pp. 18-19]`; `fandom:Charnel_Valley [Tomb Kings 8e, p. 19]`
- **Canon.** Mahrak's kings fought off orcs and goblins in the region; the valley floor is carpeted with bones and patrolled by constructs. Nehekhara's land is drained desert [R3]. No farming text.
- **Farm or pasture.** Nothing for either. Desert default is pasture.
- **Analogue.** Hejaz and the Red Sea Hills: under 25 mm of rain, herding and caravans. `vanilla:STATE_HEDJAZ arable 20, pasture, livestock_ranch`; `STATE_SINAI 10, orchard`.
- **Layer.** `open_desert` by a hair (BWh 42 %, BSk 38 %, Cfb 12 %, BWk 5 %, Cfa 3 %).
- **Proposal.** `highland_alpine`, -1, pasture, `livestock_ranch`. The name states the mountains; the -1 is the Nehekharan desert flank. `open_desert` would be as defensible (Q5). **Tier B.**

### STATE_MOUNTAINS_OF_DAWN: Mountains of Dawn (id 195, unowned)
- **Identity.** Canon name: the Nehekharans' name for the stretch of the World's Edge Mountains that cut their Great Land in two. `fandom:Worlds_Edge_Mountains [Neferata (novel), ch. 13]` (local dump). The state sits south of the Sour Sea (it shares the sea's naval exit). Hubs Bloodpeaks Hold, Burning Face Hold, Gate of Stars are TW.
- **Canon.** No land-use text. Misty Mountain, on the same shore, "teems with life" underground (goblin fungus caves) `fandom:Misty_Mountain [Orcs & Goblins 8e, pp. 21-23]`.
- **Farm or pasture.** Nothing direct; pasture by [R1]/[R2], weak.
- **Analogue.** Zagros-type dry range. `vanilla:STATE_LURISTAN arable 40, orchard`; `STATE_NGARI 60, pasture`.
- **Layer.** `steppe` (BSh 35 %, Cfa 28 %, Cfb 17 %, BSk 13 %, Dc 6 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B** (canon name, realm-level land use).

### STATE_CRIPPLE_PEAK: Cripple Peak (id 196, owner NGZ Nagashizzar)
- **Identity.** The sundered mountain holding Nagashizzar, on the Sour Sea. Certain. `lex:Cripple_Peak [Skaven 4e, pp. 13-15; Undead 4e, p. 6]`
- **Canon.** Nomad herders once wintered under the peak and built a small realm round the then Crystal Sea. The warpstone meteor poisoned the water, killing or mutating its life and sickening the plants around it; Nagash's mining made the surroundings a wasteland and the surviving people became ghouls. The fortress stands half a mile above the desert. `lex:Sour_Sea [Undead 4e, pp. 14-16]`; `lex:Nagashizzar [Undead 4e, pp. 6-10]`; `fandom:Cripple_Peak` (herders on the eastern slope)
- **Farm or pasture.** Canon's only living land use here is ancient nomad herding: pasture, moderate for the past, nothing for 2502.
- **Analogue.** None fits a poisoned mountain; nearest is a barren desert peak. `vanilla:STATE_SINAI arable 10`.
- **Layer.** `temperate_forest_hill` (Cfb 58 %, Df 37 %, BSk 5 %): the layer's most fertile reading in the file, on the most blighted ground.
- **Proposal.** `highland_alpine`, -2, pasture, `livestock_ranch`. Direct canon of poisoned water, sick vegetation and depopulation. **Tier A.**

### STATE_BLISTERING_PEAKS: Blistering Peaks (id 197, unowned)
- **Identity.** Not a canon name (no page in either wiki). Hub Karag Haraz is canon: Fire Mountain, the volcano seen from Karak Azul's southern towers `fandom:Karak_Azul [Stone and Steel, pp. 32-33]`. So: the volcanic range just south-east of Karak Azul. Fairly confident by hub.
- **Canon.** No land-use text.
- **Farm or pasture.** Nothing direct; pasture by [R1], weak.
- **Analogue.** As Red Cloud Mountains.
- **Layer.** `steppe` (BSk 60 %, Df 20 %, BWk 17 %, Cfb 3 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_IRON_PEAKS: Iron Peaks (id 198, owner AZL Karak Azul)
- **Identity.** Karak Azul, "Iron Peak", city hub. Certain.
- **Canon.** A mining and weapon-forging hold with the richest iron in the Old World; its upper works cover a plateau above a valley and road; weapons go out by the Underway and hidden trails. An ale store and a brewmaster are named. No farming or herding text for the hold itself. `lex:Karak_Azul [Dwarfs 8e, p. 24; Grudgelore, pp. 5-11]`; `fandom:Karak_Azul [Stone and Steel, pp. 32-33]`. Its rangers are named for the hairy bouldergoats of the sheer peaks `fandom:Bouldergoats [End Times: Nagash p. 223]` (fauna note only; End Times book, not used as basis).
- **Farm or pasture.** Pasture by [R1] only; no hold-level evidence either way. Karak Azul is the southernmost standing hold, far from human farmland, so imports must be thin: inference.
- **Analogue.** Dry high range, Hindu Kush: `vanilla:STATE_KABUL arable 80, farm`; `STATE_NGARI 60, pasture`.
- **Layer.** `open_desert` (BWk 67 %, BSk 27 %, ET 6 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_DESOLATION_OF_NAGASH: Desolation of Nagash (id 199, unowned)
- **Identity.** The desert round Nagashizzar on the Sour Sea shore. Certain.
- **Canon.** A desert, glittering and parched, littered with the bones of a besieging army; made by warpstone mining on a shore once ringed by villages and small towns. `lex:Desolation_of_Nagash [Undead 4e, p. 7]`; `lex:Sour_Sea [Undead 4e, pp. 14-16]`; `fandom:Desolation_of_Nagash [White Dwarf 249, p. 37]`
- **Farm or pasture.** Neither; desert default pasture.
- **Analogue.** `vanilla:STATE_NEJD arable 10, pasture`; Eastern Desert, under 25 mm.
- **Layer.** `steppe` (BSk 89 %).
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`. **Tier A.** KA-03 confirmed.

### STATE_DRAGON_CRAG: Dragon Crag (id 200, unowned)
- **Identity.** Karak Azgal, once Karak Izril, later Karag Drakk, "Dragon's Crag". Certain. `lex:Karak_Azgal [Stone and Steel, p. 38]`
- **Canon.** The Dwarfs never retook the hold; Skalf's line built a walled surface settlement and the town of Deadgate in the valley below the old gate and tax the treasure hunters who go down. Goods of every kind are sold there. No farming or herding text. `lex:Karak_Azgal [Karak Azgal (WFRP 2e), intro and ch. 1-3]`; `fandom:Karak_Azgal`, `fandom:Deadgate [Karak Azgal, pp. 3-4]`
- **Farm or pasture.** Nothing direct. A toll town living on adventurers imports; pasture by [R1], weak.
- **Analogue.** As Iron Peaks.
- **Layer.** `open_desert` (BWk 99 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. KA-01 confirmed on canon text. **Tier B.**

### STATE_KARAG_ZIFLIN: Karag Ziflin (id 201, split CRM Crooked Moon / KEP Karak Eight Peaks)
- **Identity.** One of the eight peaks, the "Windswept Mountain"; hub Karag Yar is another (Sunset Mountain). Certain. `lex:Karak_Eight_Peaks#Peaks`. (Spelling: see Q10.)
- **Canon.** As Karak Eight Peaks below; nothing about this peak's own land.
- **Farm or pasture.** As Karak Eight Peaks.
- **Layer.** `open_desert` (BWk 100 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_SOUR_CRAGS: Sour Crags (id 202, owner BKA Broken Axe goblins)
- **Identity.** Not a canon name; the crags round the Sour Sea with Misty Mountain (mine hub, the tag's seat), which canon puts south-east of the sea, facing Nagashizzar. Confident by hub.
- **Canon.** Misty Mountain teems with goblins who farm fungus in warpstone-laden caverns running under the sea and raise huge squigs. The sea itself is poisoned and the plants round it sick. `fandom:Misty_Mountain [Orcs & Goblins 8e, pp. 21-23; Arcane Journal O&G, p. 9]`; `lex:Sour_Sea [Undead 4e, pp. 14-16]`
- **Farm or pasture.** Cave fungus and squig herds: pasture as the nearer building, moderate (Q3).
- **Analogue.** Barren range by a dead lake; `vanilla:STATE_ALTAI arable 10, pasture`.
- **Layer.** `steppe` (BSk 74 %, BSh 9 %, BWh 9 %, BWk 8 %).
- **Proposal.** `highland_alpine`, -1, pasture, `livestock_ranch`. The surface is blighted; what life there is lives underground. **Tier A.** KA-03 confirmed.

### STATE_BLACK_MOUNDS: Black Mounds (id 229, unowned)
- **Identity.** Not a canon state name (Fandom has a "Battle of Black Mound"). City hub Karak Varn; farm hub Black Falls, which canon names as the Black Water's southern outflow. So: Karak Varn and the south-west shore. Confident by hub. `lex:Black_Water [Dwarfs 8e, p. 22 map]`
- **Canon.** Karak Varn was a rich mining hold on the Black Water at the meeting of the Black Mountains and the World's Edge; flooded by the earthquakes of -1500 IC and lost to Skaven and Night Goblins. No land-use text. `lex:Karak_Varn [Dwarfs 8e, p. 20; White Dwarf 152, p. 55]`
- **Farm or pasture.** Nothing direct; pasture by [R1]/[R2], weak.
- **Analogue.** Wet west-facing alpine slope: `vanilla:STATE_TYROL arable 30, farm`.
- **Layer.** `temperate_forest_hill` (Df 48 %, BSk 21 %, Dc 17 %, BWk 14 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. A mountain hold on a crater lake is not forest-hill farmland. **Tier B.**

### STATE_AGRILDRIN: Agrildrin (id 231, owner KAK Karaz-a-Karak)
- **Identity.** Agrildrin is Khazalid for the Silver Road `fandom:Ivory_Road [Stone and Steel, p. 27]` (local dump), which runs east from Karaz-a-Karak `lex:Karaz-a-Karak [Dwarfs 8e, p. 24]`. City hub Karaz-a-Karak. Certain.
- **Canon.** The capital and largest hold, in a valley among the tallest peaks, reached by a winding pass; most halls stand empty. The Yinlinsson brewing clan is here. No text on its fields or herds. `lex:Karaz-a-Karak`; `fandom:Karaz-a-Karak [Dwarfs 6e, pp. 58-59]`; `fandom:Karaz_Ankor`
- **Farm or pasture.** Realm canon only [R1]: herders common, farmers few, grain grown mainly for brewers, food imported. Pasture, moderate (realm level, and this is the hold the realm text describes best).
- **Analogue.** `vanilla:STATE_EAST_SWITZERLAND arable 40, farm, rye_farm livestock_ranch vineyard`; `STATE_TYROL 30, farm`.
- **Layer.** `highland_alpine` by a hair (ET 44 %, BWk 41 %, BSk 15 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_WEST_MAD_DOG_PASS: West Mad Dog Pass (id 232, owner RFG Red Fangs)
- **Identity.** The western half of Mad Dog Pass (Varag Kadrin), between two branches of the Howling River, opening on the Border Princes. Certain. `lex:Mad_Dog_Pass [WFB 8e, p. 196]`; `fandom:Mad_Dog_Pass [Lure of the Liche Lord, pp. 21-22; Grudgelore, p. 81]`
- **Canon.** A raiding road for orcs and goblins; Night Goblins have burrowed all along its sides; men and Dwarfs rarely use it. No land-use text.
- **Farm or pasture.** Night Goblin burrows: fungus and squigs [R2]. Pasture, weak to moderate.
- **Analogue.** High pass country: `vanilla:STATE_SAVOY arable 20, farm`.
- **Layer.** `open_desert` (BWk 76 %, BSk 24 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. KA-01 confirmed. **Tier B.**

### STATE_WEST_DEATH_PASS: West Death Pass (id 236, owner RFG Red Fangs)
- **Identity.** Black Crag (Karak Drazh), the greatest orc fortress in the old Dwarf realm, at the western entrance of Death Pass. City hub Black Crag. Certain. `lex:Black_Crag [Dwarfs 8e, p. 26; Orcs & Goblins 8e, pp. 12-14]`
- **Canon.** The old Dwarf road climbed past Karak Drazh and the Eight Peaks into Death Pass, the one clear way through snow-capped mountains; greenskin armies passing through pay a toll in captives. The Red Fangs are described as landless nomads who follow war-boar migrations into the Southlands and return each year to the plateau below Karak Eight Peaks. `fandom:Death_Pass [Arcane Journal: Orc & Goblin Tribes, p. 9]`; `fandom:Red_Fangs [Orcs & Goblins Collector's Guide (6e), p. 4]`
- **Farm or pasture.** Pasture, good: the owner tribe is canonically nomadic and boar-following. Nothing supports the orchard the file carries today.
- **Analogue.** Zagros nomads between winter lowland and summer pasture `rw:Zagros`. `vanilla:STATE_LURISTAN arable 40`; `STATE_NGARI 60, pasture`.
- **Layer.** `open_desert` (BWk 87 %, ET 9 %, BSk 4 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. Snow-capped is not desert. **Tier A.**

### STATE_THUNDER_PEAKS: Thunder Peaks (id 237, owner RFG Red Fangs)
- **Identity.** Not a canon state name. Hubs: Thunder Mountain (Karag Dron, a volcano held by Night Goblins and dragon cultists, erupted -1250 IC) and Karak Krum (a lost hold; contact ended after its miners found a glowing rock). Confident by hubs. `lex:Thunder_Mountain [Orcs & Goblins 8e, p. 28; Realms of Sorcery 1e, p. 99]`; `lex:Karak_Krum [The Great Betrayal, ch. 1]`
- **Canon.** No land-use text.
- **Farm or pasture.** Nothing direct; pasture by [R2], weak.
- **Layer.** `open_desert` (BWk 80 %, BSk 10 %, ET 10 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_EAST_DEATH_PASS: East Death Pass (id 238, owner RFG Red Fangs)
- **Identity.** The Dark Lands end of Death Pass; four of seven provinces impassable. Hubs Groz Drung, Broken Peak, Skull Chasm are TW. Confident by name.
- **Canon.** The pass climbs through snow-capped mountains to the bleak, desolate Dark Lands; beyond lies blasted wasteland. Almost nothing grows in the Dark Lands. `fandom:Death_Pass [Arcane Journal O&G, p. 9]`; `fandom:Dark_Lands [Chaos Dwarfs 5e, p. 4]`
- **Farm or pasture.** Nothing direct; pasture (greenskin ruling), weak.
- **Analogue.** Rain-shadow side of a high range: `vanilla:STATE_ALTAI arable 10, pasture`.
- **Layer.** `open_desert` (BWk 89 %, ET 11 %).
- **Proposal.** `highland_alpine`, -1, pasture, `livestock_ranch`. Mountain by name and by its impassable share; the step is the Dark Lands flank. **Tier B.**

### STATE_EAST_MAD_DOG_PASS: East Mad Dog Pass (id 239, owner RFG Red Fangs)
- **Identity.** The eastern mouth of Mad Dog Pass and the apron below it: 15 provinces, only two impassable. Hub Warpstone Meteorites (TW) and the invented Crookback Kamp point at Crookback Mountain, a canon Skaven (Clan Rictus) lair in the Dark Lands settled first by Night Goblins fleeing Nagash's desolation. Fairly confident: mostly Dark Lands plain. `fandom:Crookback_Mountain [Skaven 4e, pp. 7-8]`
- **Canon.** The lands east of the mountains are dusty, barren plains pitted with warpstone craters; almost nothing grows in the Dark Lands; wolf packs hunt round Crookback Mountain. `lex:Lair-Nests_of_the_Dark_Lands [Skaven 7e]`; `fandom:Dark_Lands [Chaos Dwarfs 5e, p. 4]`
- **Farm or pasture.** Nothing; desert default pasture.
- **Analogue.** `vanilla:STATE_SEMNAN arable 20, pasture`; `STATE_KERMAN 20, pasture`.
- **Layer.** `open_desert` (BWk 93 %, BSk 7 %). Agrees.
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`. **Tier B** (Q6).

### STATE_BLIZZARD_PEAKS: Blizzard Peaks (id 241, unowned)
- **Identity.** Not a canon name; hubs (Moonbatz Camp, Blizzard Gap, Glowpit, The High Place) are TW. A stretch of the high range east of Karaz-a-Karak, by position only.
- **Canon.** No canon land-use text found. Realm canon [R1].
- **Farm or pasture.** Nothing direct; pasture, weak.
- **Layer.** `open_desert` (BWk 47 %, ET 27 %, BSk 26 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B** (identity is "World's Edge Mountains", which is certain; nothing finer).

### STATE_MOUNT_SILVERSPEAR: Mount Silverspear (id 242, unowned)
- **Identity.** Mount Silverspear (Karag Agilwutraz), today Mount Grimfang: once one of the richest mines and the easternmost outposts of the realm, lost to greenskins in the Silver Road Wars. Certain. `fandom:Karaz_Ankor#Lost_mines`, `fandom:Mount_Grimfang [Stone and Steel, p. 40; Dwarfs 8e, pp. 20, 28]`
- **Canon.** A goblin lair that Clan Rictus raids for slaves from Crookback Mountain; its fall sent Queen Hadora's people west to found Karak Norn. No land-use text; Dark Lands canon as above. `fandom:Crookback_Mountain [Skaven 4e, pp. 7-8]`; `fandom:Karak_Norn`
- **Farm or pasture.** Nothing direct; pasture by [R2], weak.
- **Layer.** `open_desert` (BWk 50 %, ET 31 %, BSk 14 %, Dc 5 %).
- **Proposal.** `highland_alpine`, -1, pasture, `livestock_ranch`. A mountain on the Dark Lands flank. **Tier B.**

### STATE_BROKEN_TEETH: Broken Teeth (id 252, unowned)
- **Identity.** Canon name. A Tilean explorer's route runs through Death Pass, right at the volcano, then between the Plain of Bones and the Broken Teeth to the Sea of Dread coast. `fandom:Luka_Huarugoin`, `fandom:Great_East_Road [Dogs of War 5e, p. 91]` (local dump). The state lies east of Cripple Peak on the Bitter Sea, which is south of the Plain of Bones `fandom:Bitter_Sea [Tomb Kings 8e, p. 17]`, so the placement fits. Hubs are TW tooth names. Position confident; what the feature is (a jagged range, by the name) is inference.
- **Canon.** No land-use text. It sits between the Dark Lands, where almost nothing grows, and Nagash's Desolation; the Bitter Sea takes warpstone-fouled water from the Sour Sea through the Straits of Nagash. `fandom:Dark_Lands [Chaos Dwarfs 5e, p. 4]`; `fandom:Bitter_Sea [Tomb Kings 8e, p. 17]`
- **Farm or pasture.** Nothing; desert default pasture.
- **Analogue.** `vanilla:STATE_HEDJAZ arable 20, pasture`; `STATE_BALUCHISTAN 63, farm` (dry coast and range).
- **Layer.** `steppe` (BSh 53 %, Cfa 40 %, BWh 8 %).
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`. Dark Lands realm canon on one side, the Desolation on the other, fouled water offshore: the layer's steppe with 40 % humid subtropical is not what canon describes. **Tier B** (canon name, realm-level land use). Q7.

### STATE_NORTHERN_WORLD_S_EDGE: Northern World's Edge (id 288, owner BNR Bonerattlaz orcs)
- **Identity.** A small piece (five provinces, three impassable) of the northern range; hubs Kurak Peak and Bloody Spires are TW, the rest invented. Certain only as "northern World's Edge Mountains".
- **Canon.** The range is impassable but for its passes; High Pass carries the Kislev to Dark Lands trade. No land-use text. `lex:Worlds_Edge_Mountains [Realm of the Ice Queen, p. 7]`
- **Farm or pasture.** Nothing; pasture (greenskin ruling), weak.
- **Analogue.** High Caucasus: barley to 7,000-8,000 ft, cattle the mountaineers' main resource `rw:Caucasus`. `vanilla:STATE_NORTH_CAUCASUS arable 25, farm, wheat_farm livestock_ranch`.
- **Layer.** `highland_alpine` (ET 64 %, Dc 22 %, BSk 14 %). Agrees.
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_IRONCRAFT_MOUNTAINS: Ironcraft Mountains (id 289, unowned)
- **Identity.** Not a canon name. City hub Karak Angkul, a canon hold (setting of Thanquol's Doom). Confident by hub.
- **Canon.** Pastures outside the hold provide milk and cheese; inside are a vast smelthall and deeps fought over with Skaven. `lex:Karak_Angkul [Thanquol's Doom, ch. 6 (pp. 545-549); ch. 13]`. The Fandom article has no land-use text, so this rests on Lexicanum alone, and on a novel.
- **Farm or pasture.** Pasture, direct statement (novel-grade).
- **Analogue.** `vanilla:STATE_NORTH_CAUCASUS arable 25, farm`; `STATE_EAST_SWITZERLAND 40, farm`.
- **Layer.** `highland_alpine` (ET 66 %, Dc 34 %). Agrees.
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier A.** (The state is unowned at start, Q9.)

### STATE_NEW_LAHMIA: New Lahmia (id 291, owner LHX Lahmian Exiles)
- **Identity.** Not a canon name. Mine hub Silver Pinnacle is canon: the former hold Karaz Bryn, Neferata's fortress, called the tallest peak of the range. Confident by hub and owner. `lex:Silver_Pinnacle [Night's Dark Masters; Neferata (novel)]`; `fandom:Silver_Pinnacle [Night's Dark Masters, pp. 52-58]`
- **Canon.** A rich, isolated community that mortals visit to trade; black coaches come and go; attackers do not return. No land-use text.
- **Farm or pasture.** Nothing. Pasture as "no ploughland", weak (Q8).
- **Analogue.** `vanilla:STATE_NORTH_CAUCASUS arable 25`; Carpathian sheep country `rw:Carpathians`.
- **Layer.** `boreal_forest` (Dc 75 %, ET 25 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. A named peak of the main range is mountain land, not taiga. **Tier B.**

### STATE_GROM_RIDGE: Grom Ridge (id 302, unowned)
- **Identity.** Not a canon name; hubs Ironskinz Hold, Grom Peak, Rib Peaks are TW. The high ridge between Mount Gunbad and Peak Pass, by position.
- **Canon.** No canon land-use text found. Realm canon [R1], [R2].
- **Farm or pasture.** Nothing direct; pasture, weak.
- **Layer.** `highland_alpine` (ET 100 %). Agrees.
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_DELVED_HEIGHTS: Delved Heights (id 304, owner RED Red Eye)
- **Identity.** Not a canon name. City hub Karak Ungor, the first hold to fall, now Red Eye Mountain, fortress of the Red Eye Night Goblins, who fight Skaven for it. Certain by hub and owner. `lex:Karak_Ungor [Dwarfs 8e, pp. 12, 20, 26; Grudgelore, p. 77]`
- **Canon.** No land-use text for the place. Night Goblins grow fungus and herd squigs [R2].
- **Farm or pasture.** Pasture by [R2], moderate at tribe level.
- **Layer.** `highland_alpine` (ET 82 %, Dc 10 %, EF 8 %). Agrees.
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_DRAKEN_RIDGE: Draken Ridge (id 305, unowned)
- **Identity.** Not a canon name. Hub Broken Leg Gully is the site of a canon battle tied to Peak Pass (Fandom has "Battle of Broken Leg Gully"; not read). The range north-east of Peak Pass, by position.
- **Canon.** No canon land-use text found. Realm canon.
- **Farm or pasture.** Nothing direct; pasture, weak.
- **Layer.** `highland_alpine` (ET 68 %, Dc 24 %, BSk 8 %). Agrees.
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_PEAK_PASS: Peak Pass (id 306, owner KAD Karak Kadrin)
- **Identity.** Karak Kadrin, the Slayer Keep, and the pass it guards. Certain. `lex:Karak_Kadrin [Nagash Book I, pp. 100-101]`; `fandom:Peak_Pass [Stone and Steel, p. 29; Dwarfs 8e, p. 24]`
- **Canon.** A wealthy trading hold on the caravan road to the east, taking tolls from merchants its outposts protect; it feeds and lodges every Slayer who comes. The mountain rises from a river valley between higher ranges `fandom:Karak_Kadrin [Dragonslayer, ch. 6]`. Its domain holds Khazid Rhyn, a Dwarf village of about 2,800 that produces grain, wool and metal `fandom:Karak_Kadrin#Settlements [WFRP 4e Lords of Stone and Steel, p. 23]`. Lexicanum's Karak Kadrin page does not carry the village: uncorroborated there.
- **Farm or pasture.** Both are named for the one settlement canon describes (grain and wool). This is the only state in the file with a current, place-level statement of Dwarf grain growing. Farm: moderate. Pasture: equally moderate. The tie-break is consistency with the Kraka Drak ruling, which rests on the same kind of entry in the same book.
- **Analogue.** An alpine trade valley: valley-floor grain under high pasture `rw:Alps`. `vanilla:STATE_TYROL arable 30, farm, wheat_farm livestock_ranch vineyard`; `STATE_NORTH_CAUCASUS 25, farm, wheat_farm livestock_ranch`.
- **Layer.** `steppe` (BSk 75 %, ET 25 %).
- **Proposal.** `highland_alpine`, 0, **farm**, `wheat_farm livestock_ranch`. Grain first because the village's list leads with it and the state is the farm exception. No step up: one village is not a breadbasket. **Tier A.** Q1.

### STATE_MOUNT_GUNBAD: Mount Gunbad (id 310, unowned)
- **Identity.** The old gold mine, richest in the Known World, on the eastern slopes; fell to the Bloody Spear Night Goblins in -1457 IC and is now their greatest lair. Certain. `lex:Mount_Gunbad [Old World Rulebook, p. 25; Lords of Stone and Steel, p. 22; Orcs & Goblins 8e, p. 28]`; `fandom:Karaz_Ankor#Lost_mines`
- **Canon.** No land-use text for the place. Night Goblin canon [R2].
- **Farm or pasture.** Pasture by [R2], moderate at tribe level.
- **Layer.** `highland_alpine` (ET 99 %). Agrees.
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. **Tier B.**

### STATE_BLACK_WATER: Black Water (id 311, owner ZHU Zhufbar)
- **Identity.** Zhufbar and the Black Water (Varn Drazh). Certain.
- **Canon.** A meteor crater filled with glacier meltwater, ringed with ore; Zhufbar sits in a canyon where thousands of waterwheels drive the Engineers Guild's machinery; mutated monsters live in the lake. Most of the hold's food, clothing and daily goods come by trade with other holds and the Empire. It built a road to the River Aver. `lex:Black_Water [White Dwarf 152, p. 54; Dwarfs 8e, pp. 24-26]`; `lex:Zhufbar [Stone and Steel, pp. 28-29]`; `fandom:Zhufbar [Stone and Steel, p. 28]`
- **Farm or pasture.** Canon says imported. Of the two, pasture (the lower-grain building) matches; farm is contradicted. Strong against farm. Fishing is not supported: the lake is known for monsters, and no page mentions fishing.
- **Analogue.** An industrial alpine valley fed from the lowlands: Graubünden and Ticino imported grain `rw:Switzerland`. `vanilla:STATE_EAST_SWITZERLAND arable 40, farm`.
- **Layer.** `boreal_forest` (Dc 57 %, ET 23 %, Df 18 %).
- **Proposal.** `highland_alpine`, -1, pasture, `livestock_ranch wheat_farm`. The step is the direct statement that the hold does not feed itself. Net effect against the layer is still up (3.56 against 2.12 per 1,000 px). **Tier A.**

### STATE_CLIFFS_OF_DAWN: Cliffs of Dawn (id 374, unowned)
- **Identity.** Total War name (worksheet source); no page in either wiki. Three provinces, two impassable, at the eastern foot of the Mountains of Dawn above the Nehekharan coast. The name echoes the canon "Mountains of Dawn". Inferred by position.
- **Canon.** No canon land-use text found. Realm canon [R3].
- **Farm or pasture.** Nothing; desert default pasture.
- **Analogue.** Red Sea Hills `rw:Eastern Desert`. `vanilla:STATE_SINAI arable 10, orchard, livestock_ranch`.
- **Layer.** `tropical_savanna` (Aw 91 %, Cfa 9 %).
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`. **Tier C.**

### STATE_AMBER_SKULL: Amber Skull (id 513, unowned)
- **Identity.** Total War name; no page. Hub "Tomb of Phar's Legions" (TW) points at Phar, the canon king of Mahrak, so this is Mahrak's eastern approach. Inferred.
- **Canon.** No canon land-use text found. Realm canon [R3]; Mahrak's kings cleared the region of greenskins `lex:Mahrak [Tomb Kings 6e, p. 65]`.
- **Farm or pasture.** Nothing; desert default pasture.
- **Analogue.** As Cliffs of Dawn.
- **Layer.** `tropical_savanna` (Aw 75 %, Cfa 21 %, Cfb 4 %).
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`. **Tier C.**

### STATE_KARAK_EIGHT_PEAKS: Karak Eight Peaks (id 523, split CRM Crooked Moon / KEP Karak Eight Peaks)
- **Identity.** Vala-Azril-Ungol, the city in a great bowl ringed by eight peaks. Certain.
- **Canon.** Surface walls enclosed a vast area above the underground city. In -513 IC southern volcanoes blotted out the sun and the crops that fed the city died (Gotrek's telling adds that the cattle sickened); the outlying Dwarfs withdrew inside and the hold fell from below. Since 2473 Belegar's Dwarfs hold the surface citadel and upper levels under near-constant siege; goblins hold peaks and upper halls, Clan Mors the depths; parts are too poisoned to reclaim. Crooked Moon goblin slaves harvest the mushrooms that fill their lairs. `lex:Karak_Eight_Peaks [Dwarfs 8e, pp. 20-21; White Dwarf 375, p. 33]`; `fandom:Karak_Eight_Peaks [Trollslayer; Stone and Steel, pp. 26-28]`; `fandom:Skarsnik [Skarsnik (novel)]`
- **Farm or pasture.** Historic: both grain and cattle, clearly stated, enough to feed a great city. In 2502: fungus caves and a besieged garrison. Farm is supported for the land's potential, pasture for its present. Evidence for past cultivation: strong.
- **Analogue.** A high enclosed basin, like an alpine valley floor: `vanilla:STATE_WEST_SWITZERLAND arable 50, farm`.
- **Layer.** `open_desert` (BWk 88 %, BSk 8 %, ET 4 %).
- **Proposal.** `highland_alpine`, 0, pasture, `livestock_ranch wheat_farm`. Pasture for the present occupants; wheat stays on the list because canon grew grain here. If Chris wants the land's history to win, this is the second farm candidate after Peak Pass. **Tier A.**

### STATE_CURSED_WAY: Cursed Way (id 573, unowned)
- **Identity.** No page in either wiki; the naming worksheet itself marks the name "(weak)". Coast on the Bitter Sea between the Desolation of Nagash and Lahmia, by position. Hub Obelisk of Usekph is TW (Fandom has a "Usekhp" page; not read). Inferred.
- **Canon.** No canon land-use text found. Lahmia lies south of the Straits of Nagash on the Bitter Sea; the Desolation is parched desert; Nehekhara is drained [R3]. `fandom:Lahmia`; `fandom:Bitter_Sea [Tomb Kings 8e, p. 17]`
- **Farm or pasture.** Nothing; desert default pasture.
- **Analogue.** As Cliffs of Dawn.
- **Layer.** `temperate_forest_hill` by plurality (Cfa 38 %, Aw 30 %, BSh 27 %, Cfb 5 %).
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`. The largest cut in the file (15.51 to 0.99 per 1,000 px) on position alone. **Tier C.** Q4.

### STATE_SHANIDAAR: Shanidaar (id 603, unowned)
- **Identity.** Shanidaar is a canon name: the place where King Esteban of Estalia's crusaders destroyed an undead army out of Lahmia, then turned for home. `fandom:Araby#Battle_of_Shanidaar [Undead 4e, p. 12]` (local dump). Canon does not say where it is; the map's placement (the cape south-east of Lahmia) is the mod's. Hubs Cape Kharpentharia and Idol of Asaph are TW.
- **Canon.** No land-use text. Lybaras is hemmed by the Cursed Jungle to its south `fandom:Lybaras [Tomb Kings 8e, p. 19]`, so a jungle margin exists somewhere near; whether this state touches it I cannot tell from text.
- **Farm or pasture.** Nothing; desert default pasture.
- **Analogue.** Desert coast: `vanilla:STATE_OMAN arable 10, pasture`; if wetter, `STATE_SOMALILAND 80, orchard` (`tropical_savanna`).
- **Layer.** `tropical_savanna` (Aw 100 %).
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`, on realm canon [R3]. The least certain of the coast rows. **Tier C.** Q4.

### STATE_LAHMIA: Lahmia (id 604, owner LAH Lahmia)
- **Identity.** The ruined city of Lahmia, east of the mountains, north of Lybaras, on the Bitter Sea. Certain. `lex:Lahmia [Tomb Kings 6e, pp. 10, 16-17]`; `fandom:Lahmia`
- **Canon.** Once the City of the Dawn, a trading power with Cathay; a haunted ruin since its fall. Nehekhara's land is drained desert [R3]. Lexicanum adds (uncited) that life is pleasant in the few places where the desert recedes. No farmland text for Lahmia in either wiki.
- **Farm or pasture.** Nothing; desert default pasture.
- **Analogue.** `vanilla:STATE_HEDJAZ arable 20, pasture`; `STATE_SINAI 10, orchard`.
- **Layer.** `steppe` (BSh 70 %, Aw 30 %).
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`. **Tier B.**

### STATE_HOUSE_OF_EVERLASTING_LIFE: House of Everlasting Life (id 605, owner LAH Lahmia)
- **Identity.** Canon as a building, not a region: the Lahmian temple where the royal dead lay after mummification `fandom:Lahmia#Locations [Nagash the Unbroken]` (local dump). Hubs Golden Lotus Ruins and (in the Lahmia state) Hall of Rebirth are also Lahmian city features on that page. So: Lahmia's hinterland, named for a temple. Confident it is Lahmian land.
- **Canon.** As Lahmia.
- **Farm or pasture.** Nothing; desert default pasture.
- **Layer.** `tropical_savanna` (Aw 84 %, Cfa 11 %, BSh 4 %).
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`. **Tier B.**

### STATE_SIX_WATCH_FORTS: Six Watch Forts (id 606, owner LYB Lybaras)
- **Identity.** Total War name; no page, and "watch fort" appears nowhere in the Nehekhara articles of the dump. Owner Lybaras; canon says Lybaras guards its only approach, the north, toward Lahmia and Nagashizzar, which is where a line of watch forts would stand. Inferred from owner and position.
- **Canon.** No canon land-use text found. Realm canon [R3]. `fandom:Lybaras [Tomb Kings 8e, p. 19]`
- **Farm or pasture.** Nothing; desert default pasture.
- **Layer.** `tropical_savanna` (Aw 98 %).
- **Proposal.** `open_desert`, 0, pasture, `livestock_ranch`. **Tier C.**

**Tier count:** A 8, B 24, R 0, C 5.

## 3. Rows

```csv
state_key,lore_class,fertility_step,subsistence,crops,tier,note,source
STATE_RED_CLOUD_MOUNTAINS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Karag Orrud volcano, Red Cloud goblins; no land-use text; herding by realm canon",fandom:Karag_Orrud [Dwarfs 6e rev p. 23; O&G 7e p. 14] ; fandom:Dwarfs#Economy [Stone and Steel p. 16]
STATE_SOUTHERN_WORLDS_EDGE,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch,B,"Mahrak's mountains, Nehekhara side: drained desert land; Hejaz-type dry range",lex:Mahrak [Tomb Kings 6e pp. 18-19] ; fandom:Nehekhara [Tomb Kings 8e] ; vanilla:STATE_HEDJAZ arable 20 pasture
STATE_MOUNTAINS_OF_DAWN,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Nehekharan name for the range splitting the Great Land; no land-use text; realm canon",fandom:Worlds_Edge_Mountains [Neferata ch. 13] ; fandom:Dwarfs#Economy [Stone and Steel p. 16]
STATE_CRIPPLE_PEAK,highland_alpine,-2,building_subsistence_pasture,building_livestock_ranch,A,"Nagashizzar: warpstone-poisoned shore, sick vegetation, locals became ghouls",lex:Sour_Sea [Undead 4e pp. 14-16] ; lex:Nagashizzar [Undead 4e pp. 6-10] ; lex:Cripple_Peak
STATE_BLISTERING_PEAKS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Fire Mountain (Karag Haraz) country south of Karak Azul; no land-use text",fandom:Karak_Azul [Stone and Steel pp. 32-33] ; fandom:Dwarfs#Economy [Stone and Steel p. 16]
STATE_IRON_PEAKS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Karak Azul: mining and forge hold on a plateau; herding by realm canon",fandom:Karak_Azul [Stone and Steel pp. 32-33; Dwarfs 8e p. 24] ; fandom:Farmers_and_Herders_Guild [Stone and Steel p. 18]
STATE_DESOLATION_OF_NAGASH,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,"Canon desert round Nagashizzar, made by warpstone mining",lex:Desolation_of_Nagash [Undead 4e p. 7] ; fandom:Desolation_of_Nagash [White Dwarf 249 p. 37]
STATE_DRAGON_CRAG,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Karak Azgal (Karag Drakk): ruin taxed for treasure, town of Deadgate; no farming text",lex:Karak_Azgal [Stone and Steel p. 38; Karak Azgal sourcebook] ; fandom:Karak_Azgal
STATE_KARAG_ZIFLIN,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"One of the eight peaks (Windswept Mountain); as Karak Eight Peaks",lex:Karak_Eight_Peaks [Dwarfs 8e pp. 20-21]
STATE_SOUR_CRAGS,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch,A,"Sour Sea shore poisoned; Misty Mountain goblins farm cave fungus and herd squigs",lex:Sour_Sea [Undead 4e pp. 14-16] ; fandom:Misty_Mountain [O&G 8e pp. 21-23]
STATE_BLACK_MOUNDS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Karak Varn: flooded mining hold on the Black Water, lost to Skaven and goblins",lex:Karak_Varn [Dwarfs 8e p. 20; WD 152 p. 55] ; lex:Black_Water [WD 152 p. 54]
STATE_AGRILDRIN,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Karaz-a-Karak and the Silver Road; no hold-level farming text; realm canon",fandom:Dwarfs#Economy [Stone and Steel pp. 16-18] ; lex:Karaz-a-Karak [Dwarfs 8e p. 24]
STATE_WEST_MAD_DOG_PASS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Mountain pass riddled with Night Goblin burrows; fungus and squigs, no ploughland",lex:Mad_Dog_Pass [WFB 8e p. 196] ; fandom:Mad_Dog_Pass [Lure of the Liche Lord pp. 21-22]
STATE_WEST_DEATH_PASS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,"Black Crag: snow-capped pass; Red Fangs are nomads following war-boar herds",fandom:Red_Fangs [O&G Collector's Guide p. 4] ; fandom:Death_Pass [Arcane Journal O&G p. 9]
STATE_THUNDER_PEAKS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Thunder Mountain volcano and lost Karak Krum; no land-use text",lex:Thunder_Mountain [O&G 8e p. 28] ; lex:Karak_Krum [The Great Betrayal]
STATE_EAST_DEATH_PASS,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch,B,"Dark Lands end of Death Pass: bleak, desolate flank",fandom:Death_Pass [Arcane Journal O&G p. 9] ; lex:Lair-Nests_of_the_Dark_Lands [Skaven 7e]
STATE_EAST_MAD_DOG_PASS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Dark Lands apron below the pass (Crookback Mountain): dusty barren plain",lex:Lair-Nests_of_the_Dark_Lands [Skaven 7e] ; fandom:Crookback_Mountain [Skaven 4e pp. 7-8]
STATE_BLIZZARD_PEAKS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Unnamed in canon; high range east of Karaz-a-Karak; realm canon only",fandom:Dwarfs#Economy [Stone and Steel p. 16]
STATE_MOUNT_SILVERSPEAR,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch,B,"Mount Grimfang: lost mine on the Dark Lands flank, goblin lair raided by Skaven",fandom:Karaz_Ankor#Lost_mines [Stone and Steel p. 40] ; fandom:Crookback_Mountain [Skaven 4e pp. 7-8]
STATE_BROKEN_TEETH,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Canon feature beside the Plain of Bones; between the Dark Lands and Nagash's desert",fandom:Luka_Huarugoin [Dogs of War 5e p. 91] ; fandom:Dark_Lands [Chaos Dwarfs 5e p. 4] ; fandom:Bitter_Sea [Tomb Kings 8e p. 17]
STATE_NORTHERN_WORLD_S_EDGE,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Northern range held by orcs; name states the mountains; realm canon only",lex:Worlds_Edge_Mountains [Realm of the Ice Queen p. 7] ; fandom:Dwarfs#Economy [Stone and Steel p. 16]
STATE_IRONCRAFT_MOUNTAINS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,"Karak Angkul: pastures outside the hold give milk and cheese",lex:Karak_Angkul [Thanquol's Doom ch. 6]
STATE_NEW_LAHMIA,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Silver Pinnacle (Karaz Bryn), tallest peak of the range; no land-use text",lex:Silver_Pinnacle [Night's Dark Masters; Neferata] ; fandom:Silver_Pinnacle
STATE_GROM_RIDGE,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Unnamed in canon; high ridge between Gunbad and Peak Pass; realm canon only",fandom:Dwarfs#Economy [Stone and Steel p. 16]
STATE_DELVED_HEIGHTS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Karak Ungor (Red Eye Mountain): Night Goblin fortress; fungus and squigs",lex:Karak_Ungor [Dwarfs 8e p. 26] ; fandom:Night_Goblin [O&G 8e pp. 11 52]
STATE_DRAKEN_RIDGE,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Unnamed in canon; range north of Peak Pass; realm canon only",fandom:Dwarfs#Economy [Stone and Steel p. 16]
STATE_PEAK_PASS,highland_alpine,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,"Karak Kadrin: river valley; village Khazid Rhyn produces grain and wool",fandom:Karak_Kadrin#Settlements [Lords of Stone and Steel; Dragonslayer ch. 6] ; lex:Karak_Kadrin
STATE_MOUNT_GUNBAD,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Lost gold mine, greatest Night Goblin lair; fungus and squigs",lex:Mount_Gunbad [Old World Rulebook p. 25; O&G 8e p. 28] ; fandom:Night_Goblin [O&G 8e pp. 11 52]
STATE_BLACK_WATER,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,"Zhufbar: industrial canyon hold; most food comes by trade; lake holds monsters",fandom:Zhufbar [Stone and Steel p. 28] ; lex:Black_Water [WD 152 p. 54; Dwarfs 8e pp. 24-26]
STATE_CLIFFS_OF_DAWN,open_desert,0,building_subsistence_pasture,building_livestock_ranch,C,"Total War name; Nehekhara's mountain foot by position; realm desert",fandom:Nehekhara [Tomb Kings 8e] ; lex:Nehekhara [Tomb Kings 8e p. 17]
STATE_AMBER_SKULL,open_desert,0,building_subsistence_pasture,building_livestock_ranch,C,"Total War name; Nehekhara east of the mountains by hubs; realm desert",fandom:Nehekhara [Tomb Kings 8e] ; lex:Nehekhara [Tomb Kings 8e p. 17]
STATE_KARAK_EIGHT_PEAKS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,"Bowl ringed by eight peaks; crops and cattle fed the city until -513; besieged ruin now",lex:Karak_Eight_Peaks [Dwarfs 8e pp. 20-21; WD 375 p. 33] ; fandom:Karak_Eight_Peaks [Trollslayer]
STATE_CURSED_WAY,open_desert,0,building_subsistence_pasture,building_livestock_ranch,C,"No canon text; coast between Nagashizzar and Lahmia by position; realm desert",fandom:Nehekhara [Tomb Kings 8e] ; fandom:Desolation_of_Nagash [WD 249 p. 37]
STATE_SHANIDAAR,open_desert,0,building_subsistence_pasture,building_livestock_ranch,C,"Canon battle site of unstated location; realm desert, could be wetter near the jungle",fandom:Araby [Undead 4e p. 12] ; fandom:Nehekhara [Tomb Kings 8e] ; fandom:Lybaras [Tomb Kings 8e p. 19]
STATE_LAHMIA,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Ruined necropolis of Lahmia; Nehekhara's land is drained desert",lex:Lahmia [Tomb Kings 6e pp. 10 16-17] ; fandom:Nehekhara [Tomb Kings 8e]
STATE_HOUSE_OF_EVERLASTING_LIFE,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Named for a Lahmian mortuary temple; Lahmia's hinterland; realm desert",fandom:Lahmia#Locations [Nagash the Unbroken] ; fandom:Nehekhara [Tomb Kings 8e]
STATE_SIX_WATCH_FORTS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,C,"Total War name; road north of Lybaras toward Lahmia; realm desert",fandom:Lybaras [Tomb Kings 8e p. 19] ; fandom:Nehekhara [Tomb Kings 8e]
```

## 4. Disagreements

### 4.1 Against the climate layer (`mapgen/derived/state_climate_index.json`)

| States | Layer reads | Proposal | Reason |
|---|---|---|---|
| Iron Peaks, Dragon Crag, Karag Ziflin, Karak Eight Peaks, West Mad Dog Pass, West Death Pass, Thunder Peaks, East Death Pass, Blizzard Peaks, Mount Silverspear (BWk 47-100 %) | `open_desert` (0.99) | `highland_alpine` (5.31; 3.56 at -1) | Canon has snow-capped mountains, glacier meltwater and Dwarf holds with crops and cattle here, not desert. About five times the layer's arable. The BWk band looks like rain shadow plus the `dark_lands_desolation` patch's feather reaching the crest. |
| Agrildrin (ET 44 %, BWk 41 %) | `highland_alpine` by a hair | `highland_alpine` | Agrees; the desert share should not pull it down. |
| Red Cloud Mountains, Blistering Peaks, Sour Crags, Peak Pass (BSk 60-83 %) | `steppe` (4.57) | `highland_alpine` | Mountain states by canon; the numbers barely move. |
| Mountains of Dawn (BSh/BSk 49 %, C 45 %) | `steppe` | `highland_alpine` | Mountain range by name and position; small move. |
| Cripple Peak (Cfb 58 %, Df 37 %) | `temperate_forest_hill` (15.51) | `highland_alpine` -2 (2.39) | The layer makes Nagashizzar the most fertile ground in the file. Canon: poisoned, sickened, depopulated. |
| Black Mounds (Df 48 %) | `temperate_forest_hill` | `highland_alpine` | Karak Varn is a mountain hold on a crater lake. Cuts arable to a third. |
| Black Water, New Lahmia (Dc 57-75 %) | `boreal_forest` (2.12) | `highland_alpine` (Black Water at -1) | Mountain holds, not taiga. Raises both. |
| Desolation of Nagash (BSk 89 %) | `steppe` | `open_desert` | Canon desert. |
| Southern Worlds Edge (BW 47 %, BSk 38 %) | `open_desert` | `highland_alpine` -1 | Named for the mountains; dry Nehekhara flank. Either class is defensible (Q5). |
| Lahmia (BSh 70 %) | `steppe` | `open_desert` | Nehekhara's fertility was drained by Nagash's ritual. |
| House of Everlasting Life, Six Watch Forts, Shanidaar, Amber Skull, Cliffs of Dawn (Aw 75-100 %) | `tropical_savanna` (5.81) | `open_desert` (0.99) | Same realm canon. The layer cannot know the desert is magical. About a sixth of the layer's arable. |
| Cursed Way (C 43 %, Aw 30 %, BSh 27 %) | `temperate_forest_hill` | `open_desert` | Same; the largest single cut in the file, on tier C evidence (Q4). |
| East Mad Dog Pass (BWk 93 %) | `open_desert` | `open_desert` | Agrees. |
| Broken Teeth (BSh 53 %, Cfa 40 %) | `steppe` | `open_desert` | Canon feature beside the Plain of Bones; Dark Lands on one side, Nagash's desert on the other. Realm-level, not place-level, evidence. |
| Northern World's Edge, Ironcraft, Grom Ridge, Delved Heights, Draken Ridge, Mount Gunbad (ET 64-100 %) | `highland_alpine` | `highland_alpine` | Agree. |

A `climate_lore.json` patch for the Nehekharan east coast (target BWh) would fix the savanna reading at the source instead of row by row; that file is Chris's to accept.

### 4.2 Against the earlier leads

- **KA-01** (Dragon Crag, West Mad Dog Pass `highland_alpine` by name): **confirmed**, now on canon text. Dragon Crag is Karag Drakk, the old name of Karak Azgal `lex:Karak_Azgal [Stone and Steel p. 38]`; Mad Dog Pass is a canon pass. The layer's disagreement has changed from "not highland" to "cold desert". Crooked Mounts is no longer in this file.
- **KA-02** (Forest of Gloom): the state is no longer in this file. Not re-tested.
- **KA-03** (Desolation `open_desert`; Sour Crags and Cripple Peak down one): **confirmed and sharpened**. Desolation stays `open_desert` at 0. Cripple Peak goes to -2 (the layer now reads it as forest-hill, and the canon is about this exact shore). Sour Crags stays at -1, with the new note that Misty Mountain's goblins live on cave fungus and squigs.
- **`state_climate_classes.csv`**: its "tier A by name" for the mountain states is weaker than it looks; a name is identity, not land-use text. Re-tiered B here. Its `open_desert` for the Lahmia-coast states is kept; its `steppe` for Cursed Way and for Broken Teeth becomes `open_desert`. Its "Tier C, no extract" for Broken Teeth is out of date: the name is canon (Dogs of War 5e p. 91).
- **Standing ruling (2026-10-05)**: confirmed for the realm; one proposed extension (Peak Pass, farm) and one correction of sourcing (Karak Azgaraz's grain is WFRP 3e Book of Grudges; Stone and Steel p. 18 is the guild passage and names no hold).
- **Current emitted values** (retired stand-in model): `STATE_WEST_DEATH_PASS` carries `building_subsistence_orchard` with wheat and vineyard. Nothing in canon supports an orchard at Black Crag.

## 5. Open questions for Chris

1. **Peak Pass as a fourth grain hold.** Lords of Stone and Steel gives Karak Kadrin a grain-and-wool village, the same grade of evidence as Kraka Drak's. Farm for `STATE_PEAK_PASS`, or keep the list at three and treat gazetteer villages as too small to count? (The same question will come up for Karak Hirn, Barak Varr and Karak Gantuk in other files.)
2. **Realm-wide fertility.** Stone and Steel p. 16 calls the highlands round most holds barren. Apply -1 to every Dwarf mountain state, or only where a page speaks about the place (my rows)?
3. **Night Goblin subsistence.** Canon is cave fungus plus squig herds plus raiding. I used pasture (the greenskin ruling). Fungus-growing could be read as farm. Confirm pasture.
4. **Nehekhara's east coast.** Six states (Lahmia, House of Everlasting Life, Six Watch Forts, Shanidaar, Amber Skull, Cliffs of Dawn) plus Cursed Way go from steppe, savanna or forest-hill to `open_desert` on realm canon alone; none has land-use text of its own and four are placed by inference. Accept, and should it be a `climate_lore.json` patch instead? Shanidaar is the doubtful one: it lies toward the jungle south of Lybaras.
5. **Southern Worlds Edge** (Mahrak): `highland_alpine` -1, or `open_desert`? I took the name.
6. **East Mad Dog Pass**: I read it as the Dark Lands apron (`open_desert`), not the pass itself. Its hub Crookback Kamp is invented; Crookback Mountain is canon and in the Dark Lands.
7. **Broken Teeth**: canon gives only the name and that it lies beside the Plain of Bones. I made it `open_desert` from its neighbours (Dark Lands, Desolation). If Chris reads it as a jagged range, `highland_alpine` -1 gives about 3.6 times the arable.
8. **Undead states.** Cripple Peak and New Lahmia get pasture as "nothing is ploughed". Whether undead pops eat at all is the population epic's question.
9. **Karak Angkul and Karak Azgal are unowned** in `state_ownership.json`, though canon has Dwarfs living at both in 2502 (Skalf's Hold at Azgal; Angkul is a working hold in Thanquol's Doom). Outside this item; noted because the pasture evidence for Ironcraft Mountains describes a living hold.
10. **Karag Ziflin spelling.** Lexicanum has "Karag Ziflin" for the peak and a separate "Karak Ziflin" hold in the Grey Mountains; Fandom spells the peak "Karag Zilfin". The state is the peak.

## 6. Pages read

**Lexicanum** (whfb.lexicanum.com, 2026-11-19; same-origin fetch until the site began answering 403 to fetch, then single page loads; stopped after the 2026-11-20 brief update): Dwarf, Karaz Ankor, Worlds Edge Mountains, Dwarf-hold, Dwarf Clan, Karaz-a-Karak, Zhufbar, Karak Kadrin, Karak Azul, Karak Eight Peaks, Karak Varn, Black Water, Karak Azgal, Karak Ungor, Mount Gunbad, Black Crag, Karak Drazh, Karak Krum, Karak Ziflin, Karak Angkul, Mad Dog Pass, Nagashizzar, Cripple Peak, Sour Sea, Desolation of Nagash, Lahmia, Lahmia (city), Silver Pinnacle, Lair-Nests of the Dark Lands, Silver Road, Thunder Mountain, Nehekhara, Mahrak, Lybaras, Kraka Drak, Karak Azgaraz, Karak Izor, Night Goblin. (38 pages. "Death Pass" and "Peak Pass" returned 404.)

**Fandom Warhammer Wiki** (warhammerfantasy.fandom.com, 2026-11-19): Dwarfs, Farmers and Herders Guild, Dwarf Guilds, Stonebread, Dwarf Ale, Dwarf Rangers, Bouldergoats, Karaz Ankor, Karaz-a-Karak, Zhufbar, Karak Kadrin, Karak Azul, Karak Eight Peaks, Karak Varn, Karak Azgal, Deadgate, Skalf's Hold, Red Eye Mountain, Mount Gunbad, Mount Grimfang, Black Crag, Karak Krum, Karak Angkul, Karag Orrud, Red Cloud Tribe, Peak Pass, Death Pass, Mad Dog Pass, Black Water, Misty Mountain, Crookback Mountain, Nagashizzar, Sour Sea, Desolation of Nagash, Yaghur, Silver Pinnacle, Lahmia, Lybaras, Mahrak, Charnel Valley, Nehekhara, Worlds Edge Mountains, Night Goblin, Squigs, Greenskins, Skaven, Crooked Moon Tribe, Red Fangs, Barak Varr, Karak Hirn, Karak Izor, Karak Norn, Karak Azgaraz, Kraka Drak, Karak Gantuk, Karak Grom, and the gazetteer stubs Kazad Grund, Kazad Kro, Kazad Sedazund, Kazad Thar, Kazad Thrund, Kazad Mingol, Kazad Kolzhan, Kazad Frukund, Grung Agriletaz, Grung Skree, Grung Mizpal, Grung Wyruvalk, Khazid Urbaz, Khazid Wyrvarn. (70 pages.)

**Local dump** (`sources/wiki/pages/`, 2026-11-20, grep and read): Worlds Edge Mountains, Lahmia, Araby, Ivory Road, Great East Road, Dragon Isles, Luka Huarugoin, Eerie Downs, Dark Lands, Bitter Sea, Plain of Bones (header only), Skarsnik, Cripple Peak, and keyword scans of the hold pages listed above (which returned the same passages as the live read and nothing new). No page exists in the dump for: Karak Ungor, Mount Silverspear, Thunder Mountain, Fire Mountain, Straits of Nagash, City of Pillars, nor for the state names Cursed Way, Six Watch Forts, Amber Skull, Cliffs of Dawn, Blizzard Peaks, Grom Ridge, Draken Ridge, Delved Heights, Ironcraft, Blistering Peaks, Thunder Peaks, Black Mounds, Sour Crags, Iron Peaks.

**Lexicanum corroboration status.** Lexicanum answered 403 to scripted fetches late on 2026-11-19, so no further Lexicanum reads were made after the 2026-11-20 brief update. Claims resting on Fandom alone, not corroborated on Lexicanum: the Stone and Steel p. 16 "barren highlands" passage, the Farmers and Herders Guild text (p. 18), Khazid Rhyn at Karak Kadrin, Zhufbar's food-by-trade sentence, the Red Fangs' nomadism, Misty Mountain, the Mountains of Dawn and Broken Teeth names. Claim resting on Lexicanum alone: Karak Angkul's pastures.

**Web**: en.wikipedia.org/wiki/Alpine_transhumance; en.wikipedia.org/wiki/History_of_the_Alps; en.wikipedia.org/wiki/Transhumance; en.wikipedia.org/wiki/Eastern_Desert; en.wikisource.org 1911 Britannica "Tirol", "Switzerland/Geography", "Caucasia". Search excerpts only (page not opened): hls-dhs-dss.ch 027895 and 013936 (403 to WebFetch), sustainweb.org rye article, an undated Austrian land-use text, Mather and Fairbairn on Swiss forest cover. Not obtained: a Tyrol arable share for the 1830s; a Carpathian land-share figure.

**Repo**: the state file, `states_l_english.yml`, `wh_hub_names_l_english.yml`, `hub_anchors_index.json`, `state_climate_index.json`, `state_ownership.json`, `state_climate_classes.csv`, `agro_climate_overrides_draft.md`, `arable_land_engine_research.md`, `vanilla_state_climate_classes.csv`, `common/country_definitions/`, `common/buildings/` 02, 04, 12; vanilla `map_data/state_regions/*.txt`.
