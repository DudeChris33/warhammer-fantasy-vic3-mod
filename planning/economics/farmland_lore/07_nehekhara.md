# Farmland lore dossier: Nehekhara (`07_nehekhara.txt`) and Araby (`08_araby.txt`)

Board item #3685, child of epic #3675. Run 2026-11-19 / 2026-11-20. Status: **complete: all 11 states have an entry and
a row.** Built in two passes: Lexicanum online on 2026-11-19 (29 pages, until its fetch endpoint returned HTTP 429 then
403; not used again after that, per the brief), then the local Fandom dump (`sources/wiki/`, 34 articles) on
2026-11-20, which is the primary canon source wherever both speak. Where a claim rests on only one of the two it is
cited to that one.

Coverage: 11 states in `map_data/state_regions/07_nehekhara.txt`, all with an entry and a row.
`map_data/state_regions/08_araby.txt` is **empty** (0 bytes of content, confirmed by reading it): no Araby state exists
to cover. A short Araby note for the day one is drawn is in 1.6.

Citation forms: `lex:<Page>#<Section> [book, page]` = Lexicanum page read this session, with the footnote it carries;
`fandom:<Title>#<Section> [book, page]` = local dump article; `rw:<region> [URL]` = real-world source; `vanilla:STATE_X`
= the vanilla install's `map_data/state_regions/`; `repo:<path>` = a measured fact from this repo.

---

## 1. Realm picture

### 1.1 What the mod's Nehekhara is (measured, `repo:`)

The eleven states are **western Nehekhara only**: the Great Mortis from its source to the sea, plus the Ash. Canon's
eastern cities (Lahmia, Lybaras, Mahrak, Rasetra) and Quatar, Bhagar and Ka-Sabar have no state of their own here; their
tags are seated in stand-in states (`common/country_definitions/07_nehekhara.txt` flags each: "no hub carries ...").
The owner of a state is therefore not evidence about its land.

The lower Mortis, the upper Mortis and the Ash are drawn as **navigable water zones**
(`STATE_GREAT_MORTIS_RIVER_02` id 3110, `STATE_UPPER_MORTIS_RIVER_02` id 3218, `STATE_ASH_RIVER_03` id 3219 in
`99_seas.txt`), which is why nine of the eleven states have a port. Measured on `map_data/provinces.png` (read-only):

| state | px (land) | owner | pops at start | river frontage (shared border px) | drawn rivers through it (`rivers_index.json`) |
|---|---|---|---|---|---|
| Great Mortis Delta | 2,389 | ZND | 125,000 nehekharan | lower Mortis 132; open sea (Charnel Deeps) 41 | four short distributaries |
| Swamp of Terror | 1,448 | unowned | 1,000 goblin (placeholder) | lower Mortis 125 | 0197, 0199, 0200 |
| Road of Kings | 1,579 | RAS | 125,000 nehekharan | none (landlocked, no port) | 0200 (a short tributary) |
| City of Kings | 3,470 | KHM | 350,000 nehekharan | lower Mortis 126 + upper Mortis 69 (it sits at the confluence) | 0197, 0200 |
| Khemrian Desert | 5,246 | BHA | 250,000 nehekharan | none (landlocked, no port) | none |
| Pyramid of Tutankhanut | 2,551 | unowned | 1,000 goblin | upper Mortis 37 | none |
| The Scarab City | 5,449 | NUM | 190,206 nehekharan | upper Mortis 73 | 0191, 0192 (the Mortis above the navigable zone) |
| Sphinx of Phaa | 749 | KAS | 40,000 nehekharan | upper Mortis 84 + Ash 61 (the tongue between the two) | none |
| Fallow Fields | 12,314 | unowned | 1,000 goblin | Ash 96 + upper Mortis 57 | 0192, 0196 (north edge), 0201 (south edge) |
| Upper Ash River | 3,880 | QUA | 150,000 nehekharan | Ash 41 | 0201, 0208 |
| Mortis Tarn | 5,553 passable (7,264 with impassable) | 1 province NUM (9,794 dawi_ancestral), rest unowned | 1,000 goblin | upper Mortis 30 (western tip only) | 0191, 0192, 0196 (the headstreams) |

Total 44,628 land px; 1,230,206 Nehekharan pops in seven owned states.

### 1.2 Canon farmland picture (Lexicanum pass)

- **In life the river made the farmland.** Before the fall the river was the Great Vitae; its water fertilised the land
  beside it and made "viable arable land within a desert", worked by many cities and towns with bountiful crops; trade
  ships ran it and Zandri at the coast grew richest. `lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17;
  Liber Necris p. 6]`
- **The interfluve was the best land.** The Ash River (once the Golden River) also rises in the World's Edge Mountains
  and joins the Mortis east of Khemri; the land between the two was extremely fertile and is "now a dead wasteland"
  since Nagash's attack. `lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17]`
- **Three river cities**: Numas near the Mortis Tarn, Khemri mid-river below the Ash confluence, Zandri beside a delta
  at least a hundred miles square. `lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 4, 10, 16-17; Liber Necris p. 13]`
- **The poison.** Nagash poisoned the river at its source, the Mortis Tarn, high in the World's Edge Mountains; the land
  withered, crops wilted and what was gathered was poisonous; millions died within a year.
  `lex:Great_Mortis_River#History [Tomb Kings 6e p. 8; Liber Necris pp. 48-49]`. The corruption spread to the lands the
  river had made fertile and the dead soon outnumbered the living. `lex:History_of_Nehekhara [Tomb Kings 8e pp. 13-15]`
- **Today (the army-book present).** The river is poisonous; sandstorms and flesh-eating swarms; the few remaining
  oases are tainted with pools of blood; man-eating trees in the oases. `lex:Nehekhara#Dangers / #Flora, Fauna and
  Inhabitants [Tomb Kings 8e p. 17]`. Very few traders sail the river; visitors come overland with local camels and
  desert tribes as guides. `lex:Great_Mortis_River#Trade [Tomb Kings 6e pp. 72-75]`
- **The one working exception: Numas.** Under Prince Tutankhanut the pyramids were restored, a tribe of Arabyan nomads
  (the Scythans) settled in his service, and crops are grown again in the fields around the city for his living
  subjects. `lex:Numas [Tomb Kings 6e p. 14 "Tales from the Oasis"; Arcane Journal: Tomb Kings of Khemri p. 8]`;
  `lex:Scythan [Tomb Kings 6e p. 14]`; `lex:Tutankhanut [Tomb Kings 6e pp. 14, 65]`. Note: Lexicanum footnotes the
  quoted "crops grow around the city" line to its source 7 (Total War: Warhammer III) while attributing it in the text
  to "Tales from the Oasis by the Trader Suli", which is the 6th edition army book section; the statement in the
  article body carries the 6e p. 14 and Arcane Journal footnotes. Treated as army-book canon, flagged.
- **The living in 2502.** Lexicanum's uncited paragraph says the undead outnumber the living many times over and that
  life can be pleasant "where the desert recedes". `lex:Nehekhara#Flora, Fauna and Inhabitants [no footnote]`. Named
  living groups: the Scythans at Numas; desert tribes and camel guides (Suli, Aral) who take explorers to Khemri
  (`lex:Suli [Tomb Kings 6e pp. 12-15]`, `lex:Heinrich_Johann [Tomb Kings 6e pp. 72-75]`); tomb robbers, bandits and
  raiding orcs (`lex:Nehekhara [Tomb Kings 8e p. 17]`).
- **Nomads of the Great Desert** pre-date the Nehekharans, raided the settled land for food and pack animals, and were
  bound by Settra's oath; in life Numas was famous for horses raised on the surrounding plains and Bhagar for its desert
  horses. `lex:Araby [Nagash Immortal pp. 758, 810, 833-835]`; `lex:History_of_Nehekhara [Tomb Kings 8e pp. 8-9]`;
  `lex:Numas#Trade [Nagash the Sorcerer pp. 108-112]`; `lex:Bhagar#Horses [Nagash the Sorcerer pp. 93-95]`. The Mike Lee
  novels are Black Library canon about the living age; they are evidence for what the land can do, not for 2502.

### 1.3 Real-world analogue: Egypt and the Nile, c. 1800-1850

Nehekhara is Pharaonic Egypt on a Nile; the analogue for a Victoria 3 calibration is Egypt under Muhammad Ali.

- **Almost all farmland is the valley and delta, a few percent of the country.** Egypt is 1,010,408 km2; about
  35,000 km2 (3.5 percent) is cultivated and settled today; valley plus delta are about 5 percent of the area and hold
  about 99 percent of the people; the delta is about 22,000 km2; the Western Desert alone is about 700,000 km2.
  `rw:Egypt [https://en.wikipedia.org/wiki/Geography_of_Egypt]`. Farming is confined to under 3 percent of the land.
  `rw:Egypt [https://countrystudies.us/egypt/83.htm]`
- **c. 1813-1840 the cultivated area was about half of today's.** A chronology of Egyptian agriculture (M. N. Nofal,
  CIHEAM) gives 3,540,710 feddans arable in Muhammad Ali's first survey, about 3.5 million feddans in 1835 and
  3,856,226 in 1840. At 0.42 ha per feddan that is 14,700 to 16,200 km2, about 1.5 percent of the country.
  `rw:Egypt [https://ressources.ciheam.org/ressources/om/pdf/b09/CI950942.pdf]` **read only as a search-result
  snippet: the host did not resolve when fetched; treat the three figures as unverified leads.** Feddan size from
  `rw:Egypt [https://countrystudies.us/egypt/83.htm]`.
- **Basin irrigation.** Earth banks trapped the flood (river up in August and September, off in October, sown on the
  wet silt, harvested March to May): one crop a year. `rw:Egypt
  [https://en.wikipedia.org/wiki/Ancient_Egyptian_agriculture]`. Cotton forced the change to year-round (perennial)
  irrigation, which then allowed two and three crops a year. `rw:Egypt [https://countrystudies.us/egypt/88.htm]`.
  Search snippets date the first perennial canals in the delta to about 1820-1830 and say a sixth of the cultivated
  area, mostly Upper Egypt, was still basin-irrigated in the 1960s (snippets, not fetched pages).
- **Muhammad Ali's cotton.** Jumel's long-staple cotton went into commercial production in 1820
  (`rw:Egypt [https://en.wikipedia.org/wiki/Egyptian_cotton]`); cotton growing in the delta began in 1822, the
  Mahmudiyya canal to Alexandria was begun in 1819, state monopolies on the main crops date from 1816-1819, and the
  population had stood near 4 million for centuries before 1805 (`rw:Egypt
  [https://en.wikipedia.org/wiki/History_of_Egypt_under_the_Muhammad_Ali_dynasty]`).
- **Crops.** Ancient staples barley and emmer, flax, papyrus, pulses, dates (`rw:Egypt
  [https://en.wikipedia.org/wiki/Ancient_Egyptian_agriculture]`); by the 19th century wheat, beans, berseem clover,
  rice (grown 1,400 years), maize (a 19th-century arrival), cotton, with sugar cane, onions and lentils in the hotter
  south; livestock water buffalo, cattle, sheep, camels (`rw:Egypt [https://countrystudies.us/egypt/88.htm]`).
- **The delta's wet north.** Lakes Manzala, Burullus, Idku and Mariout fringe the coast; the delta is hot desert
  (BWh) with 100-200 mm of winter rain (`rw:Nile Delta [https://en.wikipedia.org/wiki/Nile_Delta]`). Its northern
  lowlands (the *barari*) were lake, marsh and salt flat, drained only after perennial irrigation arrived in the 19th
  century (`rw:Nile Delta [https://batavialand.nl/uploads/documents/country-document-polders-in-egypt-web-site.pdf]`,
  search snippet). This is the analogue for the Swamp of Terror.
- **Nubia (the upper river).** Cultivation by ox-driven water wheel (saqia) on the banks; wheat, barley, millet,
  dates, vines; date palms the main cash crop; date trees and water wheels were the tax base in the 1840s
  (`rw:Nubia`, search snippets from worldhistory.org "Old Dongola" and the PCMA Old Dongola volume; not fetched pages).
- **The desert.** Bedouin live on camels, sheep and goats, eat mostly dairy, move with the pasture, tax and guide
  caravans, raid, and barter animals for the farmers' grain. `rw:Bedouin [https://en.wikipedia.org/wiki/Bedouin]`.
  That is the Scythan / desert-tribe / camel-guide economy canon describes.

### 1.4 Vanilla's own numbers (the calibration table)

Read from `C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game\map_data\state_regions\03_north_africa.txt`
and `08_middle_east.txt`; classes from `mapgen/config/vanilla_state_climate_classes.csv`.

| vanilla state | provinces | arable | subsistence | arable_resources | trait / class |
|---|---|---|---|---|---|
| STATE_LOWER_EGYPT | 12 | 80 | farm | wheat, livestock, cotton, opium, tobacco, sugar, banana, vineyard | nile_river / desert_river |
| STATE_MIDDLE_EGYPT | 15 | 50 | farm | wheat, livestock, cotton, opium, tobacco, sugar, banana | nile_river / desert_river |
| STATE_UPPER_EGYPT | 33 | 40 | farm | wheat, livestock, cotton, dye, opium, tobacco, sugar | nile_river / desert_river |
| STATE_DONGOLA (Nubia) | 135 (36 impassable) | 40 | farm | millet, livestock, cotton, tobacco, sugar | nile_river / desert_river |
| STATE_BLUE_NILE | 72 | 60 | farm | millet, livestock, coffee, cotton, tobacco, sugar | nile_river / tropical_savanna |
| STATE_EGYPTIAN_DESERT | 96 | 5 | pasture | livestock | sahara_desert / open_desert |
| STATE_MATRUH | 47 | 3 | pasture | livestock | sahara_desert / open_desert |
| STATE_SINAI | 13 | 10 | orchard | livestock | open_desert |
| STATE_LIBYA | 170 | 28 | pasture | wheat, livestock, vineyard | sahara_desert |
| STATE_LIBYAN_DESERT | 128 | 10 | pasture | livestock | sahara_desert / open_desert |
| STATE_TRIPOLI | 68 | 30 | pasture | wheat, livestock | steppe |
| STATE_KORDOFAN | 81 | 40 | pasture | livestock | sahel / tropical_savanna |
| STATE_DARFUR | 96 | 20 | pasture | livestock | sahel |
| STATE_HEDJAZ | 105 | 20 | pasture | livestock | open_desert |
| STATE_NEJD | 178 | 10 | pasture | livestock | arabian_desert / open_desert |
| STATE_HAIL | 180 | 5 | pasture | livestock | arabian_desert / open_desert |
| STATE_OMAN | 68 | 10 | pasture | livestock, coffee, tobacco | open_desert |
| STATE_BAGHDAD | 34 | 40 | orchard | rice, livestock, silk, tobacco | desert_river (marsh and floodplain) |
| STATE_BASRA | 17 | 30 | orchard | rice, livestock, silk, tobacco | desert_river (marsh and floodplain) |
| STATE_DEIR_EZ_ZOR | 24 | 20 | pasture | millet, livestock, tobacco | desert_river (the class minimum) |

Reading: Egypt is 188 arable, of which **170 (90 percent) sits in the three Nile states on 60 of 216 provinces**; the
three desert states share 18. With Nubia the river carries 210. Every Nile state is `building_subsistence_farm` (5 of
5) and every Saharan or Arabian desert state is pasture (Sinai: orchard). Vanilla's `state_trait_nile_river`
(`common/state_traits/07_africa_traits.txt:9`) adds +20 percent agriculture and plantation throughput and +20
infrastructure; `state_trait_sahara_desert` takes 20 percent off agriculture and plantations and 10 off ranching.
World-block class densities (per 1,000 px): `desert_river` 11.58, `open_desert` 0.99: a factor of 11.7, which is the
whole size of the decision below.

### 1.5 Fandom dump pass (`sources/wiki/`)

The dump is now the primary canon source; Lexicanum (1.2) corroborates. Findings so far (more appended below):

- **Realm statement, present day.** Once fertile, populous and prosperous; now a desolate kingdom of barren wasteland
  and searing desert; beyond the centuries of war and neglect, the land was "forever tainted" by the enchantments of
  Nagash's Great Ritual. `fandom:Nehekhara#lead [Tomb Kings 8e p. 17]`. **This is the strongest canon line against a
  high-potential reading: the taint is in the land, not only in the lack of farmers.**
- **The river today.** Poisonous and blood-coloured, no relief to the thirsty; the few oases are tainted with pools of
  blood; few trees grow; skeletons go through the motions of old jobs, "harvesting crops long since withered",
  fetching stagnant water, rowing barges on the Mortis. `fandom:Nehekhara#Geography [Tomb Kings 8e p. 17]`. The river
  "oozes" through the land the colour of rotten blood. `fandom:Great Mortis River [TheOldWorld.com interactive map]`
- **The river in life.** It flowed through lush valleys and gave some of the most fertile land in the world; food from
  its soil raised desert nomads into a civilisation. `fandom:Great Mortis River [Tomb Kings 8e pp. 8-16; Liber Necris
  p. 6]`. The Nehekharans cultivated the land and herded **oxen and goats**. `fandom:Nehekhara#History [Liber Necris
  pp. 6-8]`
- **The poisoning.** Nagash fouled the Vitae Tarn, a group of lakes high in the World's Edge Mountains, with warpstone
  and dark magic; the taint spread down the major rivers of Nehekhara (plural); crops withered and died and the cattle
  sickened. `fandom:Mortis Tarn [Liber Necris p. 48]`; `fandom:Great Mortis River [Liber Necris pp. 48-49]`
- **Numas.** Called the "Scarab City" (so the state's name is the wiki's epithet for Numas); one of the few cities of
  the Land of the Dead that still holds the living; the Scythans tend the crops that feed their people and live in the
  city under the protection of the dead. The trader's line about crops growing around the city again is footnoted to
  **Tomb Kings 6e p. 14**, which settles the footnote doubt recorded in 1.2. `fandom:Numas [Tomb Kings 6e p. 14]`;
  `fandom:Scythans [Tomb Kings 6e p. 14]`. The founding-for-fertile-land sentence is footnoted to Tomb Kings 8e p. 18
  here (Lexicanum: Arcane Journal p. 8). The infobox lists industry as none at present, agriculture formerly, and the
  article says Numas was once the "Breadbasket of the Kingdom", but that footnote (4a) has no entry in the article's
  source list: **unsourced on Fandom**; Lexicanum carries the same idea from *Nagash the Unbroken* pp. 590-593.
- **Swamp of Terror.** Since the poisoning the river's banks are sickly and corrupted, peopled only by the husks of
  deathless waterfowl, its floodplains stalked by great undead beasts; the swamp lies in the domain of the Kings of
  Zandri. `fandom:Swamp of Terror [TheOldWorld.com interactive map]`
- **Zandri Trail.** Once a busy highway from the port of Zandri to every corner of Nehekhara, now a dust-choked
  wasteland haunted by dead merchants. `fandom:Zandri Trail [TheOldWorld.com interactive map]`. The Pools of Despair
  (mirage oases) also lie in Zandri's domain. `fandom:Pools of Despair [Tomb Kings 6e p. 14; TheOldWorld.com map]`
- **Living nomads.** Much of the desert is inhabited by Arabyan nomads, who keep to its less inhospitable margins,
  avoid the necropoli and sometimes raid them. `fandom:Nehekhara#lead [Town Cryer 16 p. 6]`. Nomad bandits and orc
  tribes cross it: barren, "far from empty". `fandom:Nehekhara#Geography [Tomb Kings 8e p. 17]`. The nomads live on the
  fringes of the Sahra west of the Land of the Dead, move from oasis to oasis, guide explorers, raid, and rarely stay
  long inside the dead land; their ancestors traded with the Nehekharans. `fandom:Arabyan Nomads [Town Cryer 16 p. 6;
  Town Cryer 20 pp. 14-17]`
- **Settra's restoration of Khemri (the Liche Priests' annals).** Year 1251 of the reign (124 IC): the war galleons are
  raised from the tomb pits and sail to seize captives. Year 1252 (125 IC): the fleet returns with captives "to be set
  to work"; Settra orders wells of pure water sunk and irrigation canals dug so that Khemri might be restored as in
  former days, and it is done. Year 2326 (1199 IC): the fleet sails for the eleventh time to seize captives.
  `fandom:Tomb Kings Timeline [Tomb Kings 6e pp. 5-8]`. **This is canon for living labour and working irrigation at
  Khemri under the Tomb Kings**, drawing on wells rather than the river. Disputed use of the captives: the Bretonnian
  book has Settra's raiders take the living to Khemri to be killed in rituals and added to the host.
  `fandom:Tomb Kings#History [Bretonnia 6e p. 39]`. Both can be true; neither says the works are still kept up in 2502.
- **How wide the green belt was.** Lands within a hundred leagues of the Vitae's banks were once green and fertile;
  today they are cracked and barren, ruined by Nagash and emptied by the passing of a whole nation.
  `fandom:Cracked Land [TheOldWorld.com interactive map]`. (The Cracked Land itself is on the Araby border, outside
  these eleven states; the sentence is about the river.) "Emptied by the passing of a nation" is the one canon line
  that blames depopulation as well as the curse.
- **Names.** Khemri is called the "City of Kings" (`fandom:Khemri [Tomb Kings 8e p. 19]`; also `fandom:Tomb Kings
  Timeline [Tomb Kings 8e p. 20]`) and Numas the "Scarab City" (`fandom:Numas`): both state names are canon epithets of
  their cities. The Ash River appears only in the Numas article and in one of Settra's titles ("Deacon of the Ash
  River", `fandom:Settra`). The dump has **no** article or mention for Road of Kings, Fallow Fields, Khemrian Desert,
  Sphinx of Phaa, Pyramid of Tutankhanut or Golden River.
- **Other cities, for the stand-in owners.** Bhagar lies in the *southern* Land of the Dead on the road to the Gulf of
  Medes, a horse-breeding trade city (`fandom:Bhagar [Tomb Kings 6e p. 16; Nagash the Sorcerer]`), so it is not the
  Khemrian Desert. Quatar's kings once ruled a wealthy land; today their gardens lie barren (`fandom:Quatar
  [TheOldWorld.com interactive map]`). Numas under Rahmohtep had very fertile land fed by the Vitae, "the sandy
  wasteland it is today" (`fandom:Rahmohtep [White Dwarf 288 p. 35]`). In-life works: King Pharakh's Canal of
  Abundance, ten years and ten thousand labourers, made Nehekhara prosper (`fandom:Tomb Kings [Tomb Kings 6e
  pp. 4-11]`).
- **Editions disagree in tone.** The 6th edition book (2002) has living people inside Nehekhara: the Scythans at Numas,
  captives at Khemri, guides and traders. The 8th edition book (2011) describes a land "forever tainted" where the dead
  mime the harvest. The Old World material (2024, set about 2276 IC) keeps Numas as a living city and calls the river
  banks sickly and corrupted. I treat all three as canon and let the 6e specifics stand where 8e is general.
- **Fandom infobox lines** "Industry: None (Currently), Agriculture (Formerly)" on Khemri and Numas are editors'
  summaries with no footnote; the Numas one contradicts the article's own cited text. Not used as evidence.

### 1.6 Where canon and analogue disagree, and which I follow

The analogue says: a Nile is the richest farmland for a thousand miles. Canon says: this Nile was that, has been
poison for 3,650 years (-1152 IC to 2502 IC), the land is "forever tainted" (8e), and yet one city farms again and the
High King had wells and canals dug at another (6e). Victoria 3's `arable_land` is the land's
capacity for rural buildings, not what is farmed on the start date. I follow **the analogue for the class** (the
geography is a desert river and nothing has moved the river) and **canon for the fertility step** (the poison is a
current, permanent, canon fact about the water that step-downs exist to record). See section 5 for the three readings
laid out with numbers and the recommendation.

**Araby (`08_araby.txt`, empty).** For the day it is drawn: the coastal zones are prosperous and fertile and hold the
cities; south of the River of Serpents the land is drier and poorer, home to nomads; east of the Atalan Mountains the
great desert runs for hundreds of miles to the Land of the Dead, with the odd sheltered oasis in the mountain valleys.
`fandom:Araby#Geography [WFB 3e pg. 194; Warmaster Armies p. 48]`. Water is never plentiful, few areas are really
fertile, and crops need careful irrigation. `fandom:Araby#Geography [WFB 2e Battle Bestiary p. 7]`. Nomad realms follow
the oases. `fandom:Arabyan Nomads [Town Cryer 20 p. 14]`. Lexicanum agrees (fertile coast, arid interior of camel
raiders; spices, gold and slaves traded). `lex:Araby [WFRP 1e pp. 222, 261]`. Vanilla's Maghreb pattern (Tunisia 70 farm, Tripoli 30 pasture, Libya 28 pasture)
and section 6 of `planning/economics/arable_land_engine_research.md` (`orchard` or `farm`) are the calibration. No row
is proposed because there is no state.

---

## 2. Per-state entries (file order)

Indicative arable below = land px x world-block class density x step factor, **unscaled** (the model's world
normalisation to 53,616 will move every number by one common factor). They are for comparing readings, not targets.
"Pops-implied" = start pops / 11,500 to 14,700 (vanilla's North Africa and Middle East medians of pops per arable,
`arable_land_engine_research.md` section 5).

### STATE_KHEMRIAN_DESERT (id 121) — "Khemrian Desert"

- **Identity.** The desert north of Khemri, between the City of Kings and the Badlands (borders North and East Barrier
  Idols). Landlocked, no port, no drawn river. The name is not a Lexicanum article (opensearch "Khemrian" returns
  nothing); `hub_worksheet.json` says the name is the TWW3 Old World mod region `khemrian_desert`. Owner BHA (Bhagar) is
  a stand-in seat. Confidence in "this is open desert beside Khemri": high. All four hubs are invented.
- **Canon.** Khemri stood on flat land ringed by fertile flood plain "and then expansive deserts" reaching toward what
  is now Araby. `lex:Khemri [paragraph carries no footnote on Lexicanum]`. Realm level: sandstorms, tainted oases,
  dune seas with sand sharks. `lex:Nehekhara#Dangers [Tomb Kings 8e p. 17]`. Explorers reach Khemri across this kind of
  desert by camel with tribal guides. `lex:Heinrich_Johann [Tomb Kings 6e pp. 72-75]`. Arabyan nomads live on the
  desert's less hostile margins and avoid the necropoli. `fandom:Nehekhara#lead [Town Cryer 16 p. 6]`. The shifting
  sands of Khemri swallow the unwary. `fandom:Khemrian Quicksand [Warhammer Rulebook 8e p. 121]`. Canon Bhagar is in
  the southern Land of the Dead (`fandom:Bhagar [Tomb Kings 6e p. 16]`), so nothing about Bhagar describes this state.
- **Analogue.** Egypt's Eastern/Western Desert. `vanilla:STATE_EGYPTIAN_DESERT arable 5, pasture, livestock_ranch`;
  `vanilla:STATE_MATRUH arable 3, pasture, livestock_ranch`. Bedouin camel and goat herding (`rw:Bedouin`).
- **Climate layer.** BWh 100 percent: `open_desert`, pasture, livestock_ranch.
- **Proposal.** `open_desert`, step 0, `building_subsistence_pasture`, `building_livestock_ranch`. Canon and layer
  agree; the row only confirms. The realm-level "oases are tainted" line would support a step down, but canon also has
  living guides and nomads crossing it, and at this density the step is worth under two arable. Indicative: 5.2.
  **Flag:** 250,000 pops are seated here; at about 5 arable that is 25,000 peasant places (see open question 3).
- **Tier B** (zone-level canon: the deserts around Khemri).

### STATE_MORTIS_TARN (id 190) — "Mortis Tarn"

- **Identity.** A strip 320 px long and 70 px deep running east from the head of the navigable upper Mortis to the
  World's Edge Mountains (borders Red Cloud Mountains, Southern Worlds Edge, Mountains of Dawn), with the Scarab City to
  its north-west and Fallow Fields along its whole south side. The Mortis headstreams (rivers 0191, 0192, 0196) run
  through it. Two impassable provinces. So it is the upper Mortis valley plus the mountain foot, of which the tarn is
  the eastern end, not a mountain state as a whole. Hubs: Tombs of the Four Pillars, Guardian of the Tarn (TWW3 names),
  Palms of the Tarn (invented). Homeland `dawi_ancestral` and one NUM-owned province with dwarf pops: odd, flagged.
- **Canon.** The river rises as the Mortis Tarn "high in the Worlds Edge Mountains"; Nagash poisoned the river there,
  and from that the land withered and died. `lex:Great_Mortis_River#lead / #History [Tomb Kings 6e pp. 8, 10, 16-17;
  Liber Necris pp. 48-49]`. The dump agrees and adds detail: the tarn (formerly the Vitae Tarn) is a group of lakes
  high in the mountains, fouled with warpstone and dark magic until the water ran the colour of blood, and still the
  source of the pollution. `fandom:Mortis Tarn [Liber Necris p. 48]`. Numas lies close to the tarn. No land-use text
  for the valley strip itself.
- **Analogue.** The Nile above the cataracts in the Nubian desert, and the Red Sea Hills: `vanilla:STATE_DONGOLA arable
  40 on 135 provinces` (0.30 per province, near the open-desert density of 0.23, although vanilla classes it
  desert_river); `vanilla:STATE_SINAI arable 10, orchard, livestock_ranch`.
- **Climate layer.** BWh 82 percent, BWk 10, BSk 8: `open_desert`.
- **Re-test of NEH-03** (`class:highland_alpine`, 0). The draft's own measurement was 1,382 m mean with 41 percent at
  or above 1,000 m, *below* the highland flag threshold; the override rested on the canon phrase about the tarn. That
  phrase describes a lake at one end of the state. `highland_alpine` density (5.31) is calibrated on watered ranges
  (Alps, Atlas, Andes) and would give this hot-desert, poison-source strip about 29 arable, more than Khemri. I do not
  carry NEH-03.
- **Proposal.** `open_desert`, step -1, `building_subsistence_pasture`, `building_livestock_ranch`. The step is the one
  place canon names as the origin of the poison. Indicative: 3.7 (the engine floor of 2 is close). Alternative if Chris
  wants the upper valley farmable: `desert_river` step -2, about 29.
- **Tier B** (canon text is about the tarn and the poison, not this strip's land use).

### STATE_ROAD_OF_KINGS (id 569) — "Road of Kings"

- **Identity.** A small landlocked state north-west of Khemri, behind the Swamp of Terror (which holds the river
  frontage) and west of the Khemrian Desert. No Lexicanum article or search hit for "Road of Kings"; the worksheet
  source is blank. Lexicanum's Great Mortis page cites a "Zandri Trail" on the TheOldWorld.com map, which may be the
  same road; **inference**. Hubs: Charge of the Kings (TWW3 "Amsu's Charge"), Carrion Nest (TWW3), two invented. A short
  drawn tributary (river 0200) crosses it. Owner RAS (Rasetra) is a stand-in: canonical Rasetra is about 1,300 miles
  from Khemri in the south-eastern jungle (`lex:Rasetra`; `fandom:Rasetra`). The dump has no "Road of Kings" either.
- **Canon.** No canon land-use text found for the state. The nearest canon is the Zandri Trail: once a busy highway
  from the port to every corner of Nehekhara, now a dust-choked wasteland haunted by dead merchants. `fandom:Zandri
  Trail [TheOldWorld.com interactive map]`. If the Road of Kings is that road (**inference**), canon calls its country
  a dusty waste. Realm level: desert; river poisonous. `fandom:Nehekhara#Geography [Tomb Kings 8e p. 17]`
- **Analogue.** Desert margin of the Nile valley. `vanilla:STATE_MATRUH arable 3, pasture`;
  `vanilla:STATE_EGYPTIAN_DESERT arable 5, pasture`.
- **Climate layer.** BWh 100 percent: `open_desert`.
- **Proposal.** `open_desert`, step 0, `building_subsistence_pasture`, `building_livestock_ranch`. Nothing puts this
  state on the river: the swamp lies between. Indicative: 1.6 (floor 2). **Flag:** 125,000 pops seated here.
- **Tier C** (identity inferred; no canon place of this name found).

### STATE_CITY_OF_KINGS (id 570) — "City of Kings"

- **Identity.** Khemri. The state holds the Khemri hub (tag capital of KHM) and fronts both the lower and upper Mortis
  water zones at the confluence, matching canon's "at the centre of the river, after the joining with the Ash".
  Confidence high. The name is canon: Khemri is "called the City of Kings". `fandom:Khemri [Tomb Kings 8e p. 19]`
- **Canon.** In life: Khemri sat on the Great Vitae amid fertile flood plains that fed its people amply.
  `lex:Khemri [paragraph carries no footnote]`. Settra's reign opened with the river flooding for the first time in
  decades and the first plentiful harvest in living memory. `fandom:Tomb Kings#History [Tomb Kings 8e pp. 8-25]`;
  `lex:Khemri#Settra [Tomb Kings 6e pp. 8-9]`. Alcadizzar's reign brought new methods of irrigation.
  `lex:Khemri#Alcadizaar [Nagash Immortal pp. 944-949]`. **Under the Tomb Kings:** in 125 IC Settra had captives set
  to work, wells of pure water sunk and irrigation canals dug to restore Khemri as in former days; the fleet was still
  sailing for captives in 1199 IC. `fandom:Tomb Kings Timeline [Tomb Kings 6e pp. 5-8]`. **Now:** a decaying
  necropolis at the heart of the desert, its streets scattered with dust; the river beside it is poison; skeletons
  mime the harvest of crops long withered. `fandom:Khemri#History [Tomb Kings 8e p. 19]`; `fandom:Nehekhara#Geography
  [Tomb Kings 8e p. 17]`. No text says crops stand at Khemri in 2502; the annals say the works to grow them were
  built.
- **Analogue.** Middle Egypt (Cairo and the valley below it). `vanilla:STATE_MIDDLE_EGYPT arable 50, farm, wheat,
  livestock, cotton, opium, tobacco, sugar, banana`; `vanilla:STATE_UPPER_EGYPT arable 40, farm`.
- **Climate layer.** BWh 100 percent: `open_desert`, about 3.4 arable, pasture.
- **Proposal.** `desert_river`, step -1, `building_subsistence_farm`, crops `wheat_farm, livestock_ranch,
  cotton_plantation, tobacco_plantation, opium_plantation`. Class from the geography and the in-life text; one step
  down for the poisoned river. The annals (wells, canals, captive labour) are why it is -1 and not -2, and would
  support 0 if Chris reads them as still in force; the 8e present-day text and the lack of any "crops grow here"
  line are why I stop at -1. Wheat first because canon's Khemri is a grain city (flood plain, harvest). Indicative:
  26.9 (18.1 at -2, 40.2 at 0); pops-implied 24 to 30, which fits -1.
- **Tier A** (canon text about this place's land: the annals and the harvest text are footnoted; the flood-plain
  sentence is uncited on Lexicanum).

### STATE_THE_SCARAB_CITY (id 571) — "The Scarab City"

- **Identity.** Numas. Holds the Numas hub (tag capital of NUM); the Mortis above the navigable zone runs through it
  (rivers 0191, 0192). The name is canon: Numas is "called the Scarab City" (`fandom:Numas`), after its Scarab King
  Rahmohtep, his Scarab Legion and Scarab Pyramid (`lex:Rahmohtep`, `lex:Scarab_Legion [White Dwarf 288 pp. 34-36]`).
  Confidence high. The city
  sits at the state's south-west corner; the north of the state runs up to the Badlands, where canon puts the Salt
  Plains north of Numas, a dry basin of great heat (`lex:Numas [Tomb Kings 8e pp. 23-25]`, `lex:Salt_Plains [Nagash
  Book I p. 226]`; the second is an End Times book, used only for the place's nature).
- **Canon.** Founded for its nearness to very fertile land south of the Mortis and north of the Ash; its people ate in
  plenty. `lex:Numas [Arcane Journal: Tomb Kings of Khemri p. 8]`. By -1350 IC the chief food producer of Nehekhara,
  with Lahmia paying heavily for its grain. `lex:Numas#History [Nagash the Unbroken pp. 590-593]`. Famous for horses
  raised on the surrounding plains. `lex:Numas#Trade [Nagash the Sorcerer pp. 108-112]`. Under Rahmohtep its lands were
  very fertile, fed by the Vitae. `fandom:Rahmohtep [White Dwarf 288 p. 35]`. **Now:** one of the few cities of the
  Land of the Dead that still holds the living; life has returned to the desert and "once again crops grow around the
  city"; the Scythans, a once-nomadic Arabyan tribe, live in the city, tend the crops that feed their people, patrol
  the desert and ride white Arabyan horses to war beside the Prince's chariots. `fandom:Numas [Tomb Kings 6e p. 14]`;
  `fandom:Scythans [Tomb Kings 6e p. 14]`; `fandom:Tutankhanut [Tomb Kings 6e pp. 14, 65]`; corroborated by
  `lex:Numas [Tomb Kings 6e p. 14; Arcane Journal p. 8]`, `lex:Scythan`. Both wikis agree; the claim that carries this
  row is doubly sourced to the 6th edition army book.
- **Analogue.** Upper Egypt. `vanilla:STATE_UPPER_EGYPT arable 40, farm, wheat, livestock, cotton, dye, opium, tobacco,
  sugar`.
- **Climate layer.** BWh 100 percent: `open_desert`, about 5.4 arable, pasture.
- **Proposal.** `desert_river`, step 0, `building_subsistence_farm`, crops `wheat_farm, livestock_ranch,
  cotton_plantation, tobacco_plantation, opium_plantation`. In life this was above-typical river land (+1); the river is
  still poison (-1); canon shows the land actually bearing crops in the present, so net 0. Wheat first (chief food
  producer), ranch second (horses). Indicative: 63.1; pops-implied 13 to 17 (see open question 10: at 63 the state
  starts under Victoria 3's low-population threshold).
- **Tier A.**

### STATE_UPPER_ASH_RIVER (id 607) — "Upper Ash River"

- **Identity.** The south bank of the Ash: borders the Ash water zone, Fallow Fields across it, Horn of Araby and
  Southern Worlds Edge. Rivers 0201 and 0208 run through it. The worksheet marks the name "(weak)". Owner QUA (Quatar)
  is a stand-in; canon Quatar stands at the western mouth of the Charnel Valley about 500 miles from Khemri
  (`lex:Quatar [Tomb Kings 6e pp. 10, 16-17]`), which may or may not be this state: no hub carries it.
- **Canon.** The Ash, once the Golden River, flows from the World's Edge Mountains to join the Mortis east of Khemri.
  `lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17]`. The dump has no Ash River article; it names the
  river only in the Numas article and in Settra's title "Deacon of the Ash River" (`fandom:Settra`). The poison went
  down "the rest of the major rivers" of Nehekhara, not the Mortis alone. `fandom:Great Mortis River [Liber Necris
  pp. 48-49]`; `lex:Alcadizaar [Tomb Kings 6e p. 7]` (rivers, plural). The fertile land canon names is the land
  *between* the rivers, i.e. the other bank; no land-use text for the south bank. For the stand-in owner: Quatar's
  kings once ruled a wealthy land and today their gardens lie barren (`fandom:Quatar [TheOldWorld.com interactive
  map]`); in life it had parks, fountains and the sacred Springs of Eternal Life nearby (`lex:Quatar [Nagash the
  Sorcerer pp. 140-141]`, `fandom:Springs of Eternal Life`). Colour, not farmland evidence for this bank.
- **Analogue.** A secondary desert river. `vanilla:STATE_DEIR_EZ_ZOR arable 20, pasture, millet, livestock, tobacco`
  (Euphrates in the Syrian desert, the class minimum); `vanilla:STATE_DONGOLA arable 40, farm`.
- **Climate layer.** BWh 100 percent: `open_desert`, about 3.8.
- **Proposal.** `desert_river`, step -1, `building_subsistence_farm`, crops `wheat_farm, livestock_ranch,
  cotton_plantation, tobacco_plantation, opium_plantation`. The state is named for and drained by a canon river; the
  step is the poison. Indicative: 30.1; pops-implied 10 to 13. If Chris reads the south bank as desert with a river
  edge, `open_desert` +1 (about 5.8) is the alternative.
- **Tier B** (the river is canon; the bank's land use is not described).

### STATE_SPHINX_OF_PHAA (id 608) — "Sphinx of Phaa"

- **Identity.** Three provinces: the tongue of land at the confluence, with the upper Mortis on one side (84 px) and the
  Ash on the other (61 px), Fallow Fields behind it; directly across the water from Numas and east of Khemri. Name: TWW3
  Old World mod region (worksheet source). Pha'a is a Nehekharan god (`lex:Pha'a [Tomb Kings 6e p. 27; 8e p. 50]`).
  Owner KAS (Ka-Sabar) is a stand-in: canon Ka-Sabar is a copper and bronze city across the Great Desert that later
  became Arabyan (`lex:Ka-Sabar [Nagash the Sorcerer pp. 129-136]`).
- **Canon.** It is the western tip of "the land between the two rivers": extremely fertile in life, dead wasteland now
  (`lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17]`), and the nearest piece of the land "south of the
  Great Mortis and north of the Ash" for which Numas was founded (`lex:Numas [Arcane Journal p. 8]`). Numas's revived
  fields "surround" the city (`lex:Numas [Tomb Kings 6e p. 14]`); whether they reach across the river is not stated.
- **Analogue.** `vanilla:STATE_MIDDLE_EGYPT arable 50, farm` for land of this kind at full health.
- **Climate layer.** BWh 100 percent: `open_desert`, under 1 arable.
- **Proposal.** `desert_river`, step -1, `building_subsistence_farm`, crops as City of Kings. Between Fallow Fields'
  -2 and Numas's 0 because it is the part of the dead interfluve nearest the one city that farms. Indicative: 5.8;
  pops-implied 3.
- **Tier B** (zone-level canon covers it; identity by geometry, name from TWW3).

### STATE_FALLOW_FIELDS (id 609) — "Fallow Fields"

- **Identity.** The largest state of the realm (12,314 px, 48 provinces), unowned. It borders the upper Mortis water
  zone and the Mortis headstreams on the north (rivers 0192 and 0196 list it) and the Ash on the south (river 0201,
  the Ash water zone): it **is** the land between the two rivers, by measurement, not by its name. The earlier draft
  held this at Tier C as "an inference from the name"; the geometry removes that doubt. The name itself is not on
  Lexicanum and its worksheet source is blank. Hubs: Valley of Locust (TWW3), the rest invented.
- **Canon.** In life extremely fertile, the reason Numas was built and the base of its standing as chief food
  producer (`fandom:Numas [Tomb Kings 8e p. 18]`; `lex:Numas [Arcane Journal p. 8; Nagash the Unbroken
  pp. 590-593]`). Since the poisoning "now a dead wasteland". `lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10,
  16-17]` (Lexicanum only: the dump's river article does not carry the interfluve sentence, and Lexicanum could not be
  re-read to double-check it; **uncorroborated, and it carries this row**). Consistent with it: Numas's once fertile
  lands are "the sandy wasteland it is today" (`fandom:Rahmohtep [White Dwarf 288 p. 35]`) and the land once green
  within a hundred leagues of the river is cracked and barren (`fandom:Cracked Land [TheOldWorld.com map]`).
- **Analogue.** An interfluve between two desert rivers: Mesopotamia and the Sudanese Gezira. `vanilla:STATE_BAGHDAD
  arable 40, orchard, rice, livestock, silk, tobacco`; `vanilla:STATE_BLUE_NILE arable 60, farm, millet, livestock,
  coffee, cotton, tobacco, sugar`; for the Nile itself `vanilla:STATE_LOWER_EGYPT arable 80`.
- **Climate layer.** BWh 95 percent, BWk 5: `open_desert`, about 12 arable, pasture.
- **Proposal.** `desert_river`, step -2, `building_subsistence_farm`, crops `wheat_farm, livestock_ranch,
  cotton_plantation, tobacco_plantation, opium_plantation`. The class is what the land is (canon's best river land);
  the largest step down the vocabulary allows is what canon says it is now. Indicative: 64.2. **This is the single
  biggest lever in the realm**: `open_desert` gives 12, in-life (+1) gives 214. At 64 it is an empty, unowned state
  with more room than Khemri, which is exactly the "dead valley that would bloom if resettled" reading. See open
  question 2.
- **Tier A** (canon text about this very land; identity by measured position).

### STATE_PYRAMID_OF_TUTANKHANUT (id 620) — "Pyramid of Tutankhanut"

- **Identity.** North bank of the upper Mortis between the Khemrian Desert and the Scarab City, immediately west of the
  Numas hub (the city is about 20 px from the border). The worksheet's retired name for this anchor was "Necropolis of
  Numas". The current name is a TWW3 Old World mod region. Tutankhanut is the canon Prince of Numas
  (`lex:Tutankhanut [Tomb Kings 6e pp. 14, 65]`); the farm hub is named for Numas's Scarab King Rahmohtep; the wood hub
  note says its dot sits in the TWW3 region `scythans_oasis` (a Total War lead, not canon, for where the Scythans
  camp). Unowned. Confidence that this is Numas's western approach and necropolis ground: medium.
- **Canon.** Nothing names this ground. What covers it: crops are grown in the fields surrounding Numas, and the
  Scythans patrol the desert around the city (`lex:Numas`, `lex:Scythan [Tomb Kings 6e p. 14]`).
- **Analogue.** The valley edge of Upper Egypt, cultivated strip plus necropolis desert.
  `vanilla:STATE_UPPER_EGYPT arable 40, farm`.
- **Climate layer.** BWh 100 percent: `open_desert`, about 2.5.
- **Proposal.** `desert_river`, step -1, `building_subsistence_farm`, crops `wheat_farm, livestock_ranch,
  cotton_plantation, tobacco_plantation, opium_plantation`. It fronts the river and adjoins the one farmed city, so it
  takes the river class with the poison step. Indicative: 19.8. Alternative: `open_desert` with pasture (about 2.5) if
  Chris reads it as Scythan patrol desert; see open question 8.
- **Tier C** (identity inferred from a TWW3 name and position).

### STATE_GREAT_MORTIS_DELTA (id 623) — "Great Mortis Delta"

- **Identity.** The delta and Zandri: at the river's mouth, fronting both the lower Mortis and the open sea, with four
  short distributary rivers drawn inside it; ZND's capital (no hub carries Zandri; the retired worksheet row
  "Necropolis of Zandri" sat just south of it). Confidence high. Worksheet source cites the Lexicanum river page.
- **Canon.** Zandri lies in the delta where the river meets the Great Ocean, about 600 miles north-west of Khemri; the
  delta is at least a hundred miles square and littered with wrecks. `lex:Zandri [Tomb Kings 8e p. 19]`;
  `lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17]`. In life the richest city on the river through trade.
  When the land was poisoned its crops died, despite its access to the coast and to sea food, and with the Swamp of
  Terror within a hundred miles it suffered pestilence. `lex:Zandri [paragraph carries no footnote]` (not in the dump;
  uncorroborated). The dump: Zandri, once "The City of the Waves", commands the waters off the delta; in its glory
  its streets were lined with palms and its wharves thronged; now it is tumbled stone, sand and bones, its palace
  veined with black necrotic vines. `fandom:Zandri [Nagash the Sorcerer; Lords of the Lance ch. 3]`. In 1167 IC
  invading war hydras were drowned "beneath the poisonous waters" of the river at Zandri. `fandom:Tomb Kings Timeline
  [Tomb Kings 8e p. 21]`: army-book canon that the river is poison at its mouth. The Swamp of Terror and the Pools of
  Despair lie in the domain of Zandri's kings. `fandom:Swamp of Terror`, `fandom:Pools of Despair [TheOldWorld.com
  map]`. Its fleets still sail. `lex:Zandri [Tomb Kings 8e pp. 17, 19]`
- **Analogue.** The Nile delta: the densest farmland of the analogue, with a wet, saline, fished northern rim.
  `vanilla:STATE_LOWER_EGYPT arable 80 on 12 provinces, farm, wheat, livestock, cotton, opium, tobacco, sugar, banana,
  vineyard`.
- **Climate layer.** BWh 100 percent: `open_desert`, about 2.4.
- **Proposal.** `desert_river`, step -1, `building_subsistence_farm`, crops `wheat_farm, livestock_ranch,
  cotton_plantation, tobacco_plantation, opium_plantation`. A delta would be +1 on the analogue; the poison collects
  here at the bottom of the river and canon records the crops dying, so -1 overall. Indicative: 18.5; pops-implied 9 to
  11. `building_subsistence_fishing_village` is a defensible alternative (coastal; canon mentions sea food): open
  question 7.
- **Tier A.**

### STATE_SWAMP_OF_TERROR (id 624) — "Swamp of Terror"

- **Identity.** Six provinces on the lower Mortis between the delta and Khemri, unowned. The name is on the
  TheOldWorld.com map that Lexicanum cites and in the TWW3 region table. Confidence high.
- **Canon.** Formed from the death waters of the Mortis where the river turns into its delta: a large, pestilential
  tract of stagnant water thick with flying insects. `lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17;
  TheOldWorld.com interactive map]`. Within a hundred miles of Zandri, to which it brought pestilence. `lex:Zandri`.
  The dump's version of the same map text: since the poisoning the river's banks are sickly and corrupted, peopled
  only by the husks of deathless waterfowl, the floodplains stalked by great undead beasts; the swamp lies in the
  domain of the Kings of Zandri. `fandom:Swamp of Terror [TheOldWorld.com interactive map]`. Both wikis draw on the
  same map; the "pestilential stagnant water, insects" wording is Lexicanum's, the "undead waterfowl and beasts"
  wording is Fandom's. Not disputed, two extracts of one source.
- **Analogue.** The undrained northern delta (*barari*) and the Mesopotamian marshes: `vanilla:STATE_BASRA arable 30,
  orchard, rice, livestock, silk, tobacco`. Those are living wetlands; this one is canon-poisoned.
- **Climate layer.** BWh 100 percent: `open_desert`, about 1.4.
- **Proposal.** `desert_river`, step -2, `building_subsistence_farm`, crops `livestock_ranch, wheat_farm` (no
  plantations: stagnant, pestilential water; that restriction is my inference). Carries NEH-02 unchanged in substance.
  Indicative: 7.5. `open_desert` (1.4) is the alternative; the difference is six arable.
- **Tier A.**

---

## 3. Rows

```csv
state_key,lore_class,fertility_step,subsistence,crops,tier,note,source
STATE_KHEMRIAN_DESERT,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Open desert north of Khemri; no river, no port. Confirms the climate layer.","fandom:Nehekhara#Geography [Tomb Kings 8e p. 17] ; fandom:Nehekhara#lead [Town Cryer 16 p. 6] ; lex:Khemri [no footnote] ; vanilla:STATE_EGYPTIAN_DESERT"
STATE_MORTIS_TARN,open_desert,-1,building_subsistence_pasture,building_livestock_ranch,B,"Upper valley strip and mountain foot; the tarn is where Nagash poisoned the river. Drops NEH-03 highland.","fandom:Mortis Tarn [Liber Necris p. 48] ; lex:Great_Mortis_River#History [Tomb Kings 6e p. 8; Liber Necris pp. 48-49] ; vanilla:STATE_SINAI"
STATE_ROAD_OF_KINGS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,C,"Landlocked desert margin behind the swamp; no canon place of this name. Zandri Trail (dust waste) may be it.","fandom:Zandri Trail [TheOldWorld.com interactive map] ; fandom:Nehekhara#Geography [Tomb Kings 8e p. 17] ; vanilla:STATE_MATRUH"
STATE_CITY_OF_KINGS,desert_river,-1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_cotton_plantation building_tobacco_plantation building_opium_plantation,A,"Khemri, the City of Kings: flood-plain grain land in life; Settra had wells and canals dug in 125 IC; river still poison.","fandom:Tomb Kings Timeline [Tomb Kings 6e pp. 5-8] ; fandom:Khemri [Tomb Kings 8e p. 19] ; fandom:Nehekhara#Geography [Tomb Kings 8e p. 17] ; lex:Khemri [Tomb Kings 6e pp. 8-9] ; vanilla:STATE_MIDDLE_EGYPT"
STATE_THE_SCARAB_CITY,desert_river,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_cotton_plantation building_tobacco_plantation building_opium_plantation,A,"Numas, the Scarab City: crops grow again around it, tended by the living Scythans; food and horse country in life.","fandom:Numas [Tomb Kings 6e p. 14; Tomb Kings 8e p. 18] ; fandom:Scythans [Tomb Kings 6e p. 14] ; fandom:Tutankhanut [Tomb Kings 6e pp. 14, 65] ; lex:Numas [Arcane Journal: Tomb Kings of Khemri p. 8] ; vanilla:STATE_UPPER_EGYPT"
STATE_UPPER_ASH_RIVER,desert_river,-1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_cotton_plantation building_tobacco_plantation building_opium_plantation,B,"South bank of the Ash (once the Golden River); river canon, bank land use not described.","lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17] ; fandom:Great Mortis River [Liber Necris pp. 48-49] ; fandom:Numas [Tomb Kings 8e p. 18] ; vanilla:STATE_DEIR_EZ_ZOR"
STATE_SPHINX_OF_PHAA,desert_river,-1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_cotton_plantation building_tobacco_plantation building_opium_plantation,B,"Tip of the land between the rivers, across from Numas; dead interfluve nearest the farmed city.","fandom:Numas [Tomb Kings 8e p. 18; Tomb Kings 6e p. 14] ; lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17] ; vanilla:STATE_MIDDLE_EGYPT"
STATE_FALLOW_FIELDS,desert_river,-2,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_cotton_plantation building_tobacco_plantation building_opium_plantation,A,"The land between Mortis and Ash: extremely fertile in life, a dead wasteland now. Biggest lever in the realm.","lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17] ; fandom:Numas [Tomb Kings 8e p. 18] ; fandom:Rahmohtep [White Dwarf 288 p. 35] ; vanilla:STATE_BLUE_NILE"
STATE_PYRAMID_OF_TUTANKHANUT,desert_river,-1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_cotton_plantation building_tobacco_plantation building_opium_plantation,C,"North bank beside Numas (formerly Necropolis of Numas); covered by the fields-around-Numas text.","fandom:Numas [Tomb Kings 6e p. 14] ; fandom:Tutankhanut [Tomb Kings 6e pp. 14, 65] ; vanilla:STATE_UPPER_EGYPT"
STATE_GREAT_MORTIS_DELTA,desert_river,-1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_cotton_plantation building_tobacco_plantation building_opium_plantation,A,"Zandri and the delta: crops died when the river was poisoned; the poison collects at the mouth.","fandom:Tomb Kings Timeline [Tomb Kings 8e p. 21] ; fandom:Zandri [Tomb Kings 8e p. 19] ; lex:Zandri [one paragraph unfootnoted] ; lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17] ; vanilla:STATE_LOWER_EGYPT"
STATE_SWAMP_OF_TERROR,desert_river,-2,building_subsistence_farm,building_livestock_ranch building_wheat_farm,A,"Stagnant, pestilential water from the river's death waters; banks corrupted, only undead fowl and beasts.","fandom:Swamp of Terror [TheOldWorld.com interactive map] ; lex:Great_Mortis_River#Overview [Tomb Kings 6e pp. 10, 16-17; TheOldWorld.com map] ; vanilla:STATE_BASRA"
```

---

## 4. Disagreements

**With the climate layer** (which reads all eleven as BWh `open_desert`, pasture, `livestock_ranch`; it has no river
signal by design):

| state | layer | proposal | reason |
|---|---|---|---|
| City of Kings, Great Mortis Delta, Upper Ash River, Sphinx of Phaa, Pyramid of Tutankhanut | open_desert 0 | desert_river -1, farm | on a canon river; poison step |
| The Scarab City | open_desert 0 | desert_river 0, farm | Numas farms again in canon |
| Fallow Fields, Swamp of Terror | open_desert 0 | desert_river -2, farm | canon's best land and its wetland, both canon-dead |
| Mortis Tarn | open_desert 0 | open_desert -1 | the poison's source |
| Khemrian Desert, Road of Kings | open_desert 0 | same | agreement |

**With the earlier part-A leads** (`planning/economics/agro_climate_overrides_draft.md`,
`mapgen/config/state_climate_classes.csv`):

- **NEH-01** (strip = City of Kings, Scarab City, Upper Ash River, Delta as `desert_river`, `low` except Numas):
  **kept**, and **widened** to Fallow Fields, Sphinx of Phaa and Pyramid of Tutankhanut, which the draft left
  `open_desert`. Fallow Fields was Tier C there on the name alone; it is now placed by measured position between the
  two river zones.
- **NEH-02** (Swamp of Terror, two steps down): **kept**.
- **NEH-03** (Mortis Tarn `highland_alpine`): **dropped** for `open_desert` -1 (reasons in the entry).
- `canon_rivers.csv` row "Great Mortis, STATE_ROAD_OF_KINGS, C": **not supported**. The state does not touch the river
  zone; only a short drawn tributary crosses it. The row for Fallow Fields can rise from C to A on geometry.

**Between the two wikis** (none is a flat contradiction):

- *What Settra's captives were for.* Set to work on wells and canals (`fandom:Tomb Kings Timeline [Tomb Kings 6e
  pp. 5-8]`) against killed in rituals to join the host (`fandom:Tomb Kings [Bretonnia 6e p. 39]`). I follow the Tomb
  Kings book for Khemri's land; the two are not exclusive.
- *Is the river trafficked?* Lexicanum's uncited paragraph says a good deal of trade passes down it; its footnoted one
  says very few traders sail it now (`[Tomb Kings 6e pp. 72-75]`). I follow the footnoted line.
- *Numas's farming today.* Fandom's infobox says industry "None (Currently)"; the same article's footnoted text and
  Lexicanum both say crops grow around the city. I follow the footnoted text.
- *Lexicanum only (not in the dump):* the Ash River as the former Golden River; the interfluve as "dead wasteland";
  Zandri's crops dying despite sea food; the delta a hundred miles square. *Fandom only:* Settra's irrigation works;
  "forever tainted"; nomads on the desert margins; the hundred-league green belt; the two city epithets.

---

## 5. Open questions for Chris

1. **The Nehekhara reading (the decision the earlier run flagged).** Three readings, unscaled indicative totals for the
   eleven states (today's emitted total is 108; vanilla Egypt is 188, Egypt plus Nubia 228):

   | reading | what it does | realm arable | pops per arable |
   |---|---|---|---|
   | (a) dead land, as farmed in 2502 | `open_desert` everywhere, Numas alone `desert_river` | about 102 | about 12,000 (a normal settled periphery) |
   | **(b) potential, priced for the poison (recommended, built in section 3)** | river states `desert_river` at -1, Numas 0, the swamp and the interfluve -2, deserts as they are | about 246 | about 5,000 (an emptied land with room) |
   | (b-) as (b), one step harsher | river states -2, Numas -1 | about 192 | about 6,400 |
   | (c) in life | river states `desert_river` at 0 or +1 | about 390 to 490 | about 2,500 to 3,200 |

   Recommendation (b). Victoria 3 reads `arable_land` as capacity, and the engine already has the tool for "nobody
   farms it": few pops. Canon gives two proofs that tended land bears with the poison still in the river: Numas's
   crops (Tomb Kings 6e p. 14) and Settra's wells and irrigation canals at Khemri (Tomb Kings 6e pp. 5-8). It also
   gives a present-day fact that the water is poison and the land tainted (Tomb Kings 8e p. 17), which is what a step
   down records. (b) lands western Nehekhara beside vanilla's Egypt plus Nubia rather than at a tenth or at double.
   What argues for (a) or (b-): the 8th edition says "forever tainted" and shows skeletons miming a withered harvest;
   if Chris weights the newer book over the older, (b-) is the honest version of that and (a) the literal one.
   (c) ignores the poison and I would not build it.
2. **Fallow Fields.** 64 arable (b) against 12 (a). It is unowned with a placeholder pop, so (b) makes it the richest
   colonisation target in the realm. Is "resettle the dead interfluve" wanted gameplay, or should the dead wasteland
   stay worthless (`open_desert`)?
3. **Pops seated in desert stand-in states.** Khemrian Desert carries 250,000 pops (BHA) on about 5 arable (25,000
   peasant places) and Road of Kings 125,000 (RAS) on about 2. That is a population-epic problem created by seating
   Bhagar and Rasetra in western desert states; farmland should not be bent to fix it. Options are Chris's: move the
   pops, repaint the owners onto river states, or accept it.
4. **Poison as a state trait.** The faithful vehicle for a poisoned river is a throughput malus like vanilla's
   `state_trait_sahara_desert` (-20 percent agriculture and plantations) set against a `nile_river`-style bonus, not
   only less arable. The mod's `common/state_traits/` holds generic traits only. Worth an item?
5. **Mortis Tarn.** `open_desert` -1 here against the draft's `highland_alpine`. Also: why does NUM own one province of
   it with 9,794 `dawi_ancestral` pops, and why is the state's homeland dwarf?
6. **Plantation crops are analogue-only.** A search of the whole dump for Nehekharan crops found: cultivated land,
   oxen and goats (`fandom:Nehekhara [Liber Necris pp. 6-8]`), cattle (`fandom:Great Mortis River [Liber Necris
   p. 49]`), horses, costly because of the water they need (`fandom:Skeleton Horsemen [Tomb Kings 8e p. 36]`), palms
   (Zandri), papyrus scrolls, linen mummy wrappings (`fandom:Mummy [WFRP 2e Old World Bestiary pp. 67-68]`), and
   incense, ivory and gold as exports to Cathay (`fandom:Grand Cathay`, timeline line, footnote not traced). Nothing
   names cotton, tobacco, opium, sugar or a grain by species. The plantation ids follow vanilla's Egypt (and Muhammad
   Ali's cotton); `cotton_plantation` is the nearest stand-in for a linen country. The canon-minimal list would be
   `wheat_farm, livestock_ranch`. Vanilla's Egypt also carries sugar (all three Nile states) and dye (Upper Egypt),
   which the mod has ids for; I left them out to stay inside the class default.
7. **Zandri's subsistence.** Farm (Nile delta pattern) or fishing village (canon mentions sea food; the sea is not said
   to be poisoned)?
8. **Pyramid of Tutankhanut.** River land beside Numas (`desert_river` -1, about 20) or Scythan patrol desert
   (`open_desert`, pasture, about 2.5)? The only tie to the Scythans is a Total War region name.
9. **Do Tomb King subjects eat?** The seven owned states hold 1.23 million `nehekharan` pops. Whether undead pops
   should need subsistence at all is the population epic's question (`arable_land_engine_research.md` section 6 parks
   it there); this dossier assumes they are ordinary pops.
10. **Low-population threshold.** Under (b) The Scarab City starts near 3,000 pops per arable, below
    `LOW_POP_THRESHOLD = 5000`, which gives the vanilla low-pop birth bonus. Acceptable for the one living city, or a
    reason to hold Numas at -1?
11. **State names.** City of Kings and The Scarab City are canon epithets of Khemri and Numas (found in the dump; the
    worksheet `source` cells are blank and could now cite them). Road of Kings, Fallow Fields, Khemrian Desert, Sphinx
    of Phaa and Pyramid of Tutankhanut appear in neither wiki: Chris's names or Total War's? It does not change a row
    but it sets the tier ceiling.
12. **Khemri at -1 or 0.** The 6e annals (wells of pure water, irrigation canals, captive labour, 125 IC) would carry a
    0 like Numas. I held -1 because no text says crops stand there now. Chris's call.
13. **Uncorroborated load-bearing sentence.** "The land between the two rivers ... now a dead wasteland" is on Lexicanum
    (footnoted Tomb Kings 6e pp. 10, 16-17) and not in the Fandom dump, and Lexicanum could not be re-read after the
    403. The Fallow Fields and Sphinx of Phaa rows lean on it. Anyone with the 6th edition book open at pages 16-17
    can settle it in a minute.

---

## 6. Pages read

**Fandom dump (`sources/wiki/pages/`, 2026-11-20, 34 articles: 19 in full, 15 by scan):** read in full: Nehekhara; Great Mortis River; Mortis
Tarn; Swamp of Terror; Charnel Deeps; Pools of Despair; Zandri Trail; Zandri Road; Scythans; Numas; Khemri;
Tutankhanut; Arabyan Nomads; Khemrian Quicksand; Deserts; Cracked Land; Sahra Desert; Phar of Numas; Pha'a. Read by
keyword scan plus the relevant sections and source lists: Zandri; Quatar; Bhagar; Ka-Sabar; Rahmohtep; Springs of
Eternal Life; Charnel Valley; Tomb Kings Timeline (the annals, in full); Tomb Kings; Alcadizaar the Conqueror; Rasetra;
Araby; Mummy; Skeleton Horsemen; Grand Cathay (one line each for the last three). Whole-dump greps: the eleven state
names, Ash River, Golden River, Salt Plain, Mortis Delta, and Nehekharan place names against crop and livestock words
(504 articles mention Nehekhara; hits listed in open question 6). No article exists for: Ash River, Road of Kings,
Fallow Fields, Khemrian Desert, Sphinx of Phaa, Pyramid of Tutankhanut, Great Desert of Araby (redirects to Sahra
Desert).

**Lexicanum (whfb.lexicanum.com, 2026-11-19, 29 pages):** Nehekhara (also reached as Nehekharan); Great Mortis River
(also reached as Mortis Tarn, Mortis Delta, Vitae River); Khemri; Numas; Zandri; Quatar; Bhagar; Ka-Sabar; Rasetra;
Charnel Valley; Scythan; Salt Plains; Springs of Eternal Life; Tutankhanut; Rahmohtep; Scarab Legion; Geheb; Pha'a;
Asaph; Tomb King; History of Nehekhara; Mortuary Cult; Liche Priest; Dust Goblin; Alcadizaar; Necropolis of Khemri;
Suli; Heinrich Johann; Araby. No page exists for: Ash River, Swamp of Terror, Deserts (404); opensearch returned
nothing for Khemrian, Fallow, Road of Kings, City of Kings, Phaa, Great Desert, Golden River, Oasis, Pools of Despair,
Quay of Seftu, Zedri, Golden Plain, Nomad. Blocked by HTTP 429/403 and not retried: Blight Water, Khsar, Desert Rider,
Marshes of Madness (none is in this realm file). Fandom's live site returned a Cloudflare challenge and was not read
online.

**Web (real-world):**
- https://countrystudies.us/egypt/83.htm (agriculture overview)
- https://countrystudies.us/egypt/88.htm (cropping patterns, livestock)
- https://en.wikipedia.org/wiki/Geography_of_Egypt
- https://en.wikipedia.org/wiki/Nile_Delta
- https://en.wikipedia.org/wiki/Ancient_Egyptian_agriculture
- https://en.wikipedia.org/wiki/Egyptian_cotton
- https://en.wikipedia.org/wiki/History_of_Egypt_under_the_Muhammad_Ali_dynasty
- https://en.wikipedia.org/wiki/Muhammad_Ali_of_Egypt (first 100,000 characters)
- https://en.wikipedia.org/wiki/Agriculture_in_Egypt (served the "Economy of Egypt" article; modern figures only)
- https://en.wikipedia.org/wiki/Bedouin
- https://en.wikipedia.org/wiki/Basin_irrigation (nothing on the Nile; not used)
- https://researchonline.lse.ac.uk/id/eprint/20185 (O'Brien 1968: bibliographic record only, no text)
- Search-result snippets only, pages not fetched (marked as such where used): CIHEAM CI950942.pdf (Nofal chronology;
  host did not resolve), horizon.documentation.ird.fr 41799.pdf (host did not resolve), batavialand.nl polders
  document, worldhistory.org Old Dongola, PCMA Old Dongola volume, Wikipedia Lake Burullus.
- Could not read: thebritishacademy.ac.uk 96p347.pdf (Owen on cotton: binary PDF, no reader here), britannica.com
  (403), Wikipedia "Delta Barrages" and "Economy of Egypt under Muhammad Ali" (404).

**Vanilla install (read-only):** `map_data/state_regions/03_north_africa.txt`, `08_middle_east.txt`, `09_central_asia.txt`
(analogue rows), `common/state_traits/07_africa_traits.txt`, `08_near_east_traits.txt`.

**Repo inputs:** `map_data/state_regions/07_nehekhara.txt`, `08_araby.txt`, `99_seas.txt`, `map_data/provinces.png`
(measured, read-only), `mapgen/derived/state_climate_index.json`, `state_ownership.json`, `rivers_index.json`,
`mapgen/config/hub_worksheet.json`, `land_regions_worksheet.csv`, `canon_rivers.csv`, `state_climate_classes.csv`,
`vanilla_state_climate_classes.csv`, `state_homelands.json`, `planning/economics/agro_climate_overrides_draft.md`,
`planning/economics/arable_land_engine_research.md`, `common/country_definitions/07_nehekhara.txt`,
`common/history/pops/07_nehekhara.txt`, `common/buildings/02_agro.txt`, `04_plantations.txt`, `12_subsistence.txt`.
