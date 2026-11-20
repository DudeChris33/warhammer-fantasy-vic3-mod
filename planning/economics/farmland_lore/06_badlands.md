# Farmland lore dossier: 06_badlands (Badlands + Border Princes)

Board #3683 (child of #3675), Badlands half. Run 2026-11-19, resumed and finished 2026-11-20. Status: **complete**.

File covered: `map_data/state_regions/06_badlands.txt`, **39 states** (the prompt guessed "about 39"; a `^STATE_`
grep says 38 only because the first key sits behind the file's BOM). Despite the file name only 21 are the
Badlands proper. The other 18 are the Border Princes, the north shore of the Black Gulf, two Black Mountains
passes held by the Empire and three dwarf holds (Barak Varr, Karak Izor, Karak Hirn). Cripple Peak, the
Desolation of Nagash and the Sour Crags (draft entry KA-03) are **not** in this file; section 4 re-tests KA-03
only as far as the pages I read reach.

Citation prefixes: `fandom:` local dump `sources/wiki/pages/<Title>.wiki` (primary, read 2026-11-20);
`lex:` Lexicanum page read in the browser pane on 2026-11-19 (corroboration); `rw:` real-world source;
`vanilla:` the vanilla install's `state_regions`. Bracketed publications are the footnotes those pages carry.
Everything is paraphrased; four phrases are quoted and each is under 15 words.

How to read a row: where `lore_class` equals the climate layer's dominant class and `fertility_step` is 0 the
row **confirms** the layer (keep the layer's per-pixel mix; the note says "confirm layer"). A class swap or a
non-zero step is a correction and names its evidence. "Indicative" figures are `px/1000 x class density x step
multiplier` before the world scaling to 53,616, only to compare states with each other.

## 1. Realm picture

### 1.1 Canon: two different countries share this file

**The Badlands proper (south of the Blood River).** The Blood River is the border between the Border Princes
and the Badlands (fandom:Blood_River [Night of the Daemon ch. 1]). South of it canon is consistent across
editions:

- A desolate region of barren rock, arid plains and searing desert between the World's Edge and the Black Gulf;
  "barren and blasted"; the dwarfs never claimed the interior because of the harsh climate and lack of minerals
  (fandom:Badlands [Blood in the Badlands pp. 6-11; Master of Dragons ch. 21]). Arid, rocky, boulder-strewn
  steppe and marsh with thorn scrub and ash-grey trees; the water is foul; barrows and ruins recall a more
  fertile past; to the south it turns to shifting sand at the Land of the Dead (lex:Badlands [Arcane Journal:
  Orc & Goblin Tribes pp. 7-9; Orcs & Goblins 8e p. 12; Blood in the Badlands pp. 8-11]).
- Even at its height it was poor land: the Badlands "were not fertile" and Mourkain's population was never
  great; zombie labour built its citadels (fandom:Morgheim [Warhammer Armies: Undead 4e pp. 19-21]). A Strigany
  folk song remembers three crops a year (fandom:Strygos, quote box); that is nostalgia in a song and loses to
  the army book.
- Both great rivers are ruined. The Blight Water ran among fertile fields before Nagash's Great Ritual and is
  now putrid; drinking it kills and raises the drinker as a zombie. The Blind River is cursed below Mourkain.
  River trolls line both (fandom:Blight_Water, fandom:Blind_River [Blood in the Badlands p. 11; AJ Orc and
  Goblin Tribes p. 8]; lex:Blight_Water adds [Warhammer: Nagash I p. 226] for the fertile-fields past).
- The Marshes of Madness are "a virulent swamp", trackless, the water maddening; goblin tribes in stilt huts,
  boglars, swamp trolls, undead (fandom:Marshes_of_Madness [Blood in the Badlands pp. 10-11; Tomb Kings 6e
  p. 10]; lex:Marshes_of_Madness [O&G 8e pp. 12-13; BitB p. 51]; lex:Boglar [WD 310 p. 90]). Dwarfs who tried to
  tame the swamp failed (Tree of Beards).
- **What greenskins eat.** No page read, on either wiki, says a greenskin tribe grows a field crop. The Old
  World Bestiary's peasant says flatly that they do not farm, craft or trade, only rob and burn
  (fandom:Greenskins, quote [Old World Bestiary p. 22]). What canon does give is herding, hunting and raiding:
  goblins do the tribe's hunting, building, herding and crafting, and the most successful goblin tribes are
  wolf riders roaming the Badlands deserts (fandom:Goblin [O&G 8e]); Night Goblins grow fungus for food and
  herd cave squigs (fandom:Night_Goblin; lex:Night_Goblin [O&G 4e p. 71; O&G 6e pp. 13-18]); squigs are a food
  animal (fandom:Squigs [O&G 6e p. 18; 8e pp. 54-62]); orcs keep war boars fed on raw meat (lex:Boar [O&G 8e
  pp. 37-38]); Mount Bloodhorn breeds cave squigs in their thousands as its greatest export
  (fandom:Mount_Bloodhorn [Blood in the Badlands p. 9]); the Bloody Handz of the western foothills live off
  yearly sea raids on Tilea and Araby (fandom:Bloody_Handz_Tribe; lex:Bloody_Hand_Tribe [O&G Collectors' Guide
  p. 3]); giants and trolls follow tribes for the food (lex:Giant [O&G 8e p. 60]). **The standing ruling
  (greenskin Badlands herd, `building_subsistence_pasture`) is supported**: herding plus raiding is exactly the
  canon economy, and the pasture basket (meat, hides, a quarter of a farm's grain) is the right shape.

**The Border Princes (north of the Blood River).** Petty realms of fortified villages under constant raiding:

- Geography: wild and rugged; large plains of small thorny trees; hills that belong to nomads and herdsmen;
  many rivers and good rainfall, yet "not especially fertile"; poor soil even in the river valleys; a constant
  hunger for more farmland. **Good farm country exists in a few places only: around Malko and in the valleys
  near the Vaults** (fandom:Border_Princes#Geography [General's Compendium pp. 48-49; WFRP 1e pp. 271-274; Plague
  Daemon ch. 1]). Infobox: temperate, good rainfall, limited fertile land. The Vaults' hanging valleys give
  excellent cattle pasture and modest harvests [WFRP 1e pp. 271-274].
- Named economies (Renegade Crowns via fandom:Border_Princes#Settlements and lex:Border_Princes): Brovska,
  about 500 people, agriculture and cattle; Styrtia, about 450, agriculture, cattle and vineyards; Munzig, about
  520, timber, sheep and a market; Akendorf, about 800, timber, woodcarving, hogs and fur-trapping. Mentreda is
  a large town among fields grazed by herds [Plague Daemon ch. 6]. A cattle-rustling cult of Gunndred works the
  region (lex:Border_Princes#Religion [Tome of Salvation pp. 117-118]). The Zani hill tribes of the Black
  Mountains' southern slopes herd aurochs on thorn scrub and raid the lowland farms when grazing runs short
  (fandom:Zani [General's Compendium p. 49; Plague Daemon ch. 1]).
- The two fertile cores: Malko, in an especially fertile area ringed by agricultural towns, storehouses and
  barns, "the breadbasket of the Border Princes" (fandom:Malko [General's Compendium p. 54; AJ Orc and Goblin
  Tribes pp. 12-15]; lex:Malko agrees); and Khypris, an unusually fertile patch along the Tana Dante, bounded
  south by a very dry stony desert and east by ridges, whose outlying "northern and western lands" are barren
  waste with valleys that grow mostly turnips, beets and cabbages (fandom:Khypris, fandom:Tana_Dante [Plague
  Daemon chs. 1, 6]; lex:Khypris [WD 125 pp. 12-16]).
- A thousand-mile belt of forest, the Black Deeps, lies just south of the Black Mountains and includes the
  Forest of Gloom, the Hvargir and the Kharnos (fandom:Black_Deeps [Beastmen 7e p. 20; Renegade Crowns p. 6
  map]); forest goblins, beastmen and giant spiders hold it.

**The dwarf holds.** Realm level: highlands round most holds are barren, a few herder families keep goats, a
few farmers grow stunted barley and wheat inside the hold's walls, the farmer guilds are the smallest guilds
and grow grain for the brewers, the herder guilds are still common (meat, wool, cheese), and food otherwise
comes by trade (fandom:Dwarfs#Economy [Stone and Steel pp. 17-20]; lex:Dwarf#Economy [WD 152 p. 51]). That
supports the standing pasture ruling in general. Hold level, in this file:

- **Karak Izor** (state Shattered Teeth): human villages are allowed to farm its sheltered valleys; Hochstadt
  lives by cereal and pastoral farming; the hold produces grain, metals and silver for trade (fandom:Karak_Izor,
  fandom:Hochstadt [Stone and Steel pp. 36-37, 112]; lex:Karak_Izor [Lords of Stone and Steel p. 23]). The
  grain-hold exception stands, corroborated on both wikis.
- **Karak Hirn, Karak Angazhar, Karak Gantuk** (state Black Mountains): every subsidiary village the WFRP 4e
  gazetteer lists makes grain, most also wool: Khazid Grentaz (2,500), Migdhal Vongalbarak (5,200), Kazad
  Nardak (1,200), Khazid Hafak (2,000), Kazad Zhum (250); Karak Gantuk's own industry line includes grain
  (fandom:Karak_Hirn, fandom:Karak_Angazhar, fandom:Karak_Gantuk [Lords of Stone and Steel p. 23]). Not
  corroborated on Lexicanum (its pages give no food text). This is new against the ruling's list of three grain
  holds; see open question 2.
- **Barak Varr** (state Varenka Hills): industry lines grain and wool; Khazid Varrwyndak, an unusually large
  village of 8,000, makes grain, cheese and wool (fandom:Barak_Varr [Lords of Stone and Steel p. 23]). Not
  corroborated on Lexicanum (lex:Barak_Varr has no food text). No page gives the sea hold a fishery.

### 1.2 Real-world analogues, c. 1800-1850

The setting's own names say what it borrows: the Border Princes are a Balkan and Danubian march (Brovska,
Brasov, Vidovdan, Moslac, Somjek, the rivers Stacnek and Treblecz), and the Badlands are the Near Eastern
steppe-desert fringe south of it (Naqqara, the Barrier Idols, Nehekharan ruins, a poisoned Mesopotamia-like
marsh between two rivers).

- **Badlands = Syrian steppe / Karakum fringe / Kazakh dry steppe.** The Syrian Desert is about 500,000 km2 of
  stony plateau, used mainly as rangeland by Bedouin herders of sheep, goats and camels, with towns only at
  oases (rw:Syrian Desert [en.wikipedia.org/wiki/Syrian_Desert]). In Syria crops need the 300-600 mm arc; south
  and east of it the land is arid, grazing is possible on part and the rest is desert of little agricultural
  value (rw:Syria [en.wikipedia.org/wiki/Agriculture_in_Syria]). At the start of the nineteenth century most
  people of the Syrian and Jordanian interior were nomads and only a small share of the land was cultivated;
  settlement advanced only after about 1850 (rw:Syria, N. Lewis, Nomads and Settlers in Syria and Jordan
  1800-1980, as summarised in the publisher's description returned by web search; I could not open the book).
  The Karakum has 70-150 mm of rain and one person per 6.5 km2; farming exists only where the Murghab and Tejen
  rivers reach it (rw:Karakum [en.wikipedia.org/wiki/Karakum_Desert]). The Kazakh steppe has 200-400 mm; before
  Russian colonisation nomadic herding was the basis of the economy, herds about 60 % sheep, 13 % horses, 12 %
  cattle, 4 % camels; the northern steppe was pasture until it was first ploughed in 1954-60, with heavy erosion
  (rw:Kazakh steppe [en.wikipedia.org/wiki/Kazakh_Steppe; en.wikipedia.org/wiki/Virgin_Lands_campaign;
  e-history.kz via web search]). In the Ottoman lands output grew in the nineteenth century mainly by putting
  new land under the plough as tribes were settled; the central Anatolian basin and the Syrian steppe zone were
  still "empty" enough to settle refugees on (rw:Ottoman agriculture
  [en.wikipedia.org/wiki/Economic_history_of_the_Ottoman_Empire]). **I found no source that states the cropped
  share of these lands for 1800-1850 as a number**; the qualitative picture (herding everywhere, crops at oases
  and river strips only) is all the sources I could open support.
- **Marshes of Madness = the Mesopotamian marshes, minus the people.** About 20,000 km2; the Marsh Arabs split
  into buffalo breeders and cultivators of rice, barley, wheat and millet, with fishing and reeds
  (rw:Mesopotamian marshes [en.wikipedia.org/wiki/Mesopotamian_Marshes; en.wikipedia.org/wiki/Marsh_Arabs]).
  Canon removes exactly what made the real marsh productive: the water is poison. Canon wins; see section 4.
- **Border Princes = a raided frontier march: the Wild Fields, the Military Frontier, Dobruja.** The Pontic
  "Wild Fields" were good land kept thinly peopled for centuries by slave raids (86 recorded 1450-1586);
  herding and fortified Cossack settlement came first, the plough only with eighteenth-century colonisation
  (rw:Wild Fields [en.wikipedia.org/wiki/Wild_Fields]). The Habsburg Military Frontier settled soldier-farmers
  on land grants, one inhabitant in twelve a soldier (rw:Military Frontier
  [en.wikipedia.org/wiki/Military_Frontier]). Dobruja was dry steppe repeatedly emptied by war (the 1829
  invasion depopulated towns and villages) and resettled piecemeal (rw:Dobruja
  [en.wikipedia.org/wiki/Dobruja]). All three match canon's fortified villages, herds and unploughed plains.

### 1.3 Vanilla calibration

| analogue | vanilla state | class | arable | subsistence | arable_resources |
|---|---|---|---|---|---|
| open desert, herders | SAHARA, LIBYAN_DESERT, NEJD | open_desert | 10 | pasture | livestock_ranch |
| open desert | TRANSJORDAN | open_desert | 5 | orchard | millet, livestock, banana |
| Iranian desert | SEMNAN / KERMAN | open_desert | 20 / 20 | pasture | wheat, livestock, plantations |
| Karakum | TURKMENIA | open_desert | 25 | farm | wheat, livestock, silk, opium |
| Syrian steppe | SYRIA / ALEPPO | steppe | 30 / 40 | farm | millet or wheat, livestock, plantations, vineyard |
| Euphrates strip | DEIR_EZ_ZOR | desert_river | 20 | pasture | millet, livestock, tobacco |
| Mesopotamian marsh | BASRA / BAGHDAD | desert_river | 30 / 40 | orchard | rice, livestock, silk, tobacco |
| Anatolian plateau | KONYA / ANKARA | steppe | 40 / 65 | farm | wheat, livestock, plantations, vineyard |
| dry steppe, nomads | KALMYKIA / URALSK / KIRGHIZIA | steppe | 8 / 35 / 50 | pasture | livestock (+ wheat) |
| Balkan march | DOBRUDJA / BULGARIA / BOSNIA / MONTENEGRO | river plain / river plain / forest-hill / forest-hill | 10 / 35 / 40 / 38 | farm | wheat, livestock, vineyard (+ cotton, tobacco) |
| Danubian grain land | WALLACHIA / MOLDAVIA | temperate_river_plain | 85 / 100 | farm | wheat, livestock, vineyard, silk, cotton |
| rocky Adriatic coast | DALMATIA / ATTICA / PELOPONNESE | mediterranean | 20 / 25 / 10 | farm | wheat, livestock, vineyard |
| Alpine valleys | TYROL / EAST_SWITZERLAND | highland_alpine | 30 / 40 | farm | wheat or rye, livestock, vineyard |

Readings that matter: vanilla's pure nomad deserts carry `livestock_ranch` alone and `pasture`; its steppe
herding states drop the vineyard; vanilla uses `orchard` only for oases and Mesopotamia; its Balkan states grow
wheat, never rye; its Alpine states are `farm`.

### 1.4 Where canon and analogue disagree, and what I follow

1. Marshes of Madness: the analogue says rice, buffalo and fish; canon says poison. Canon.
2. Border Princes: Chris's real-world zone colouring (today's stand-in values: Aquilena 228, Black Peninsula
   132, Old Dwarf Road 101) treats them as settled Balkan farmland; canon says thorn-tree plains, herdsmen and
   two small fertile cores. Canon, which here agrees with the climate layer's steppe reading.
3. Today's emitted `building_subsistence_orchard` on every Badlands state (inherited from a Persian or
   Mesopotamian zone) has no canon support: no oasis gardening is described anywhere. Pasture.
4. Dwarf holds: vanilla says farm for mountains; the realm canon says herders and imported grain; the WFRP 4e
   gazetteer says the Black Mountains and Barak Varr villages grow grain. I keep the ruling for Karak Hirn
   (highland, no export), follow the gazetteer for Barak Varr (lowland, large farm village), and flag both.

## 2. Per-state entries (file order)

Each entry: display name; owner tag; layer = the climate index's zone shares and resulting class. Hubs marked
(TW) come from the TWW3 Old World mod region table and are leads only.

### STATE_AQUILENA — Aquilena (AQL, Border Prince)
- Identity: the realm of Karolina Aquilena, a 2276 IC prince from The Old World map (fandom:Border_Prince_(Title)
  [TOW website]). On the canvas it is the south-western mainland facing the Lagoon of Tears and Tilea; hubs
  Zvörak, Argalis, Verdanos (TOW map names; no land-use text). Confidence in the name: high; in what land it
  covers: medium.
- Canon: nothing place-specific. Realm text applies: thorn-tree plains, herdsmen, limited fertile land. The TOW
  map puts the dense oak Kharnos Forest "in the south-western Borderlands", which may be this state rather than
  the one named for the forest (open question 6).
- Analogue: Dobruja / Bulgaria; vanilla:STATE_DOBRUDJA arable 10, farm; vanilla:STATE_BULGARIA 35, farm, wheat
  livestock cotton vineyard.
- Layer: BSk 99 % -> steppe. Indicative 29.
- Proposal: `steppe`, 0, farm, livestock_ranch wheat_farm vineyard. Confirm layer. The realm canon and the layer
  agree; the stand-in's 228 has no support.
- Tier: R.

### STATE_NORTH_BADLAND_HILLS — North Badland Hills (unowned)
- Identity: hills between the Dragonbacks and the central plain; hubs Oliday Retreat (TW), Snotwood (TW). The
  "Oliday" name echoes the Bloody Handz tribe's raiding season. Name is the mod's.
- Canon: realm only (barren rock, arid plains); giants and greenskins on the Dragonback side.
- Analogue: Syrian badia; vanilla:STATE_NEJD 10, pasture, livestock_ranch.
- Layer: BWh 70 %, BWk 30 % -> open_desert. Indicative 5.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_EAST_BARRIER_IDOLS — East Barrier Idols (unowned)
- Identity: the idol line on the Land of the Dead's northern border; hubs Mork Idol, Khakkekk Idol (TW).
- Canon: great stone idols of the Nehekharan gods line the border; Savage Orcs hold rituals beneath them
  (fandom:Badlands#Notable_Regions, fandom:Barrier_Idols [TOW website; TWW3]); the land turns to shifting sand
  here (lex:Badlands [O&G 8e p. 12]). The idol text itself is TOW-website and Total War; the sand is army book.
- Analogue: Libyan Desert edge; vanilla:STATE_LIBYAN_DESERT 10, pasture, livestock_ranch.
- Layer: BWh 100 % -> open_desert. Indicative 6.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_WORLDS_EDGE_FOOTHILLS — Worlds Edge Foothills (BSB, Bloody Sunz orcs)
- Identity: the eastern rim under the World's Edge south of Death Pass; hubs Rusty Daggaz Hold, Bloody Tusks
  Hold, Skullbreaker Ridge (TW). The Bloody Tusks are a canon tribe based at Deff Gorge, between the marshes and
  Red Cloud Mountain, raiding into the Badlands and the mountains (fandom:Bloody_Tusks [O&G 8e pp. 8, 13]).
- Canon: raiding tribes; no land-use text. The dwarfs' first Badlands settlers are said to have farmed barley on
  the eastern plains before -1500 IC (fandom:Dragonback_Mountains, weakly cited to Blood in the Badlands
  pp. 8-12); far too old and too thinly sourced to move a 2502 value.
- Analogue: Syrian badia under a mountain front; vanilla:STATE_KERMAN 20, pasture.
- Layer: BWh 76 %, BWk 20 %, BSk 4 % -> open_desert. Indicative 8-9.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_EASTERN_BADLANDS — Eastern Badlands (BSB)
- Identity: eastern plain; hubs Kazad Drung, Bloodspike Mesa (TW).
- Canon: realm only; same ancient barley note as above.
- Analogue and layer: as above; BWh 81 %, BWk 19 % -> open_desert. Indicative 5.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_BLIGHTWATER — Blightwater (BSB)
- Identity: the Blight Water's course from the Sour Sea toward the marshes (name; `canon_rivers.csv` row).
- Canon: once a sluggish river among fertile fields, now black and putrid; a drinker dies and rises as a zombie;
  river trolls on the banks (fandom:Blight_Water [Blood in the Badlands p. 11]; lex:Blight_Water [AJ O&G Tribes
  p. 8; Warhammer: Nagash I p. 226 for the past]).
- Analogue: a desert river strip would be vanilla:STATE_DEIR_EZ_ZOR 20, pasture; canon forbids that reading.
- Layer: BWh 94 % -> open_desert. Indicative 11 at step 0, 7 at -1.
- Proposal: `open_desert`, **-1**, pasture, livestock_ranch. The one river that could have made a `desert_river`
  state is the poison itself; the largest Badlands state should not also be its richest.
- Tier: A.

### STATE_MARSHES_OF_MADNESS — Marshes of Madness (RDV, Redvenom goblins)
- Identity: canon marsh by name; hubs Floating Village and Tree of Beards are canon features (fandom, [Blood in
  the Badlands p. 10]).
- Canon: see 1.1. Goblin tribes on raised islands and stilts, boglars that hunt amphibians, reptiles and fish,
  trolls, undead. No cultivation; failed dwarf drainage.
- Analogue: Mesopotamian marshes; vanilla:STATE_BASRA 30, orchard, rice. Rejected on the poison text.
- Layer: BWh 100 % -> open_desert (the layer has no wetland signal). Indicative 7.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. There is no swamp class; for farmland the honest
  reading is "almost none", which is what `open_desert` yields. Part A's `tropical_savanna` with two steps down
  gives about three times as much for no canon reason. A fishing village would fit the boglars but the state
  has no coast, so it is not legal.
- Tier: A.

### STATE_BADLANDS_COAST — Badlands Coast (unowned)
- Identity: south-west coast toward Nehekhara; hubs Galbaraz, Top Knotz Hold, White Skullz Hold (TW); the farm
  hub "Swamp of Terror" is a TW placement of a Zandri feature and proves nothing here.
- Canon: realm only. Lead, not basis: in about -1149 IC the gulf coast near the marshes held pirate enclaves
  and fishing villages on pontoons (fandom:Black_Gulf [Master of Death ch. 11, novel]). Today: Pirates of the
  Black Gulf and orc hulks (fandom:Black_Gulf [Blood in the Badlands p. 8]). Ogre tribes in the southern
  reaches (fandom:Badlands, uncited sentence).
- Analogue: desert coast; vanilla:STATE_TRANSJORDAN 5; STATE_NEJD 10.
- Layer: BWh 100 % -> open_desert. Indicative 4.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer. No present-day fishing text, so no
  fishing village (open question 5).
- Tier: B.

### STATE_OLD_STRYGOS — Old Strygos (STR, Strigoi remnants)
- Identity: the ruins of Mourkain / Morgheim on the Blind River (city hub Mourkain; `canon_rivers.csv` row).
  Sources conflict on whether the city lies inside the marshes or just north of them (fandom:Morgheim notes; lex
  the same); the mod puts it north, as GW's maps do.
- Canon: a necromantic kingdom from the Black Gulf to Mad Dog Pass, built on land that was "not fertile" with a
  small population and zombie labour; sacked -200 IC; the ruins are abandoned and haunted; a Ghoul King holds a
  mock court (fandom:Morgheim [Undead 4e pp. 19-21; Blood in the Badlands p. 10]; lex:Mourkain [Vampire Counts
  8e pp. 22, 36]; lex:Strigoi [Night's Dark Masters pp. 66-73]). fandom:Strygos's infobox says the climate was
  temperate and is now arid or swamp. The Blind River is cursed below the city.
- Analogue: a dead tell on a spoiled river; vanilla:STATE_DEIR_EZ_ZOR 20 pasture is the ceiling.
- Layer: BWh 100 % -> open_desert. Indicative 11.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer. A ghoul kingdom needs no fields, and the
  best text for the land's past already calls it poor.
- Tier: A.

### STATE_MOUNT_BLOODHORN — Mount Bloodhorn (unowned)
- Identity: the fallen dwarf mine Ekrund, tallest Dragonback peak (city hub Ekrund).
- Canon: an orc fortress whose caverns breed cave squigs in their thousands, its greatest export, with Night
  Goblin herders (fandom:Mount_Bloodhorn [Blood in the Badlands p. 9]; lex:Ekrund the same). The dwarf mine had
  a famous brewery (fandom:Ekrund [Stone and Steel p. 39]). Its influence runs over the whole Dragonback chain.
- Analogue: none real; in game terms a ranching centre in a desert, like vanilla:STATE_KERMAN 20 pasture.
- Layer: BWh 74 %, BWk 26 % -> open_desert. Indicative 6 at step 0, 9 at +1.
- Proposal: `open_desert`, **+1**, pasture, livestock_ranch. The only named herding export in the Badlands sits
  here; a step up gives the ranch room without pretending the mountain is farmland.
- Tier: A.

### STATE_DRAGONBACK_MOUNTAINS — Dragonback Mountains (unowned)
- Identity: canon range on the Black Gulf's eastern shore (hubs Komar, Stonemine Tower (TW)).
- Canon: teeming with orcs, goblins, trolls and giants since the dwarfs were driven out (fandom:Badlands
  [Blood in the Badlands pp. 9-10]; lex:Dragonback_Mountains). No land-use text.
- Analogue: arid coastal range; vanilla:STATE_NEJD 10; highland alternative vanilla:STATE_LURISTAN 40 orchard.
- Layer: BWk 78 %, BSk 14 %, BWh 7 % -> open_desert. Indicative 7 (layer mix).
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer. Part A classed it `highland_alpine` on
  the name; that would lift it fivefold with no canon valley, pasture or settlement to justify it (open
  question 4).
- Tier: B.

### STATE_STINKLANDS — Stinklands (unowned)
- Identity: mod name; farm hub Stinking Geysers is a canon place, the Putrid Tar Pits hub is TW.
- Canon: the Stinking Geysers are unstable and so unpleasant that goblin tribes camp there because nobody else
  wants the place (lex:Badlands#Locations [O&G 8e p. 12]). Not found in the Fandom dump under that title.
- Analogue: a solfatara field; no vanilla twin.
- Layer: BWk 95 % -> open_desert. Indicative 5 at step 0, 3 at -1.
- Proposal: `open_desert`, **-1**, pasture, livestock_ranch. One canon sentence, tied to the state through a
  hub, so the step is weakly held; dropping it to 0 costs nothing.
- Tier: B.

### STATE_THE_BLIGHT — The Blight (BTO, Broken Tooth orcs)
- Identity: mod name ("the Blight" is also the elves' name for the whole Badlands, fandom:Badlands [Master of
  Dragons ch. 21]); hubs Broken Tooth Fort, Crow's Edge, Oeragor (TW). The Broken Tooth are a canon tribe of the
  Death Pass country under Black Orc bosses (fandom:Broken_Tooth_Tribe [O&G Collectors' Guide p. 3; O&G 8e
  pp. 13, 17-19]).
- Canon: realm only.
- Layer: BWk 100 % -> open_desert. Indicative 4.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_CENTRAL_BADLANDS — Central Badlands (unowned)
- Identity: the central plain; hubs Naqqara (canon Nehekharan tomb-city between the Dragonbacks and the Blind
  River, fandom:Naqqara [Blood in the Badlands p. 34]) and Stormhenge (canon, [BitB p. 10]).
- Canon: realm only: arid plains, ruins, things even orcs avoid.
- Layer: BWh 91 % -> open_desert. Indicative 6.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_CROOKED_MOUNTS — Crooked Mounts (unowned)
- Identity: mod name; city hub Crooked Fang Fort is canon.
- Canon: Crooked Fang Fort is a skull-shaped fortress "in the centre of the plains" (lex:Badlands#Locations
  [O&G 8e p. 12; Blood in the Badlands]). So the one canon feature here says plain, not mountain.
- Layer: BWk 90 %, BWh 10 % -> open_desert. Indicative 5.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer. Draft entry KA-01 made this state
  `highland_alpine` on its name alone; the heightmap draws it flat and the canon hub sits on a plain, so KA-01
  should be dropped for this state.
- Tier: B.

### STATE_THE_CAULDRON — The Cauldron (BTO)
- Identity: mod name; hub Pillar of Bones is the canon Pillar of Bone (fandom:Badlands [BitB p. 11]).
- Canon: realm only.
- Layer: BWk 100 % -> open_desert. Indicative 6.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_VARENKA_HILLS — Varenka Hills (BVR, Barak Varr)
- Identity: canon hills where the Skull River meets the Black Gulf, seat of Barak Varr (fandom:Varenka_Hills
  [TOW website; Dwarf Player's Guide p. 111]). Farm hub Dunkelmund is a TOW prince's realm.
- Canon: the hills are dotted with burial mounds and shunned; frontier towns cluster on the nearby river banks.
  Barak Varr is a trade hold; its gazetteer industries include grain and wool, and its village Khazid
  Varrwyndak (8,000) makes grain, cheese and wool (fandom:Barak_Varr [Lords of Stone and Steel p. 23]).
  Lexicanum's Barak Varr page has no food text, so this is single-source. No fishery is described.
- Analogue: a fortified port with a farmed hinterland on a dry coast; vanilla:STATE_DALMATIA 20 farm;
  vanilla:STATE_CRIMEA 40 farm.
- Layer: BSk 82 %, Cs 18 % -> steppe. Indicative 31 (layer mix); 32 as steppe +1.
- Proposal: `steppe`, **+1**, **farm**, wheat_farm livestock_ranch. A grain-and-cheese village of 8,000 is the
  largest farming settlement named anywhere in this file. This departs from the dwarf pasture ruling: the hold
  is a lowland port, not a peak, and the gazetteer names grain first (open question 2).
- Tier: A.

### STATE_NORTHERN_BADLANDS — Northern Badlands (DUN, Dunkelmund)
- Identity: the Badlands' north-west corner south of Barak Varr; city hub Kalkmir (TOW map), Hanging Rock
  (canon: a cursed execution site, fandom:Badlands [BitB p. 9]), Scabby Eye Camp (canon goblin tribe).
- Canon: the Old Silk Road crosses "the northernmost corner of the Orc-infested Badlands" here on its way to
  Black Crag (fandom:Old_Silk_Road [Dawn of the Storm Dragon p. 9; General's Compendium p. 49]). Realm text
  otherwise.
- Analogue: nomad steppe; vanilla:STATE_KALMYKIA 8 pasture; vanilla:STATE_URALSK 35 pasture, livestock only.
- Layer: BSk 55 %, BWk 45 % -> steppe. Indicative 18 (layer mix).
- Proposal: `steppe`, 0, **pasture**, livestock_ranch wheat_farm. Confirm layer mix; subsistence pasture
  because it lies south of the Blood River, half of it is desert and its named sites are goblin camps. Vineyard
  dropped on the vanilla nomad-steppe pattern.
- Tier: B.

### STATE_MYRMIDIA_S_COAST — Myrmidia's Coast (GDO, Gordorno)
- Identity: the Dragonbacks' northern foot on the gulf; hubs Citadel of Myrmidia (a 2276 IC settlement on the
  TOW map, fandom:Citadel_of_Myrmidia), Tor Anrok (TOW places the hidden elf tower in the Dragonbacks; older
  sources put it in the woods near Munzig: fandom:Tor_Anrok, lex:Tor_Anrok), Circle of the Sun.
- Canon: no land-use text. Giants wander these foothills (fandom:Giant_Stomping_Grounds [BitB p. 10]).
- Analogue: vanilla:STATE_KALMYKIA 8 pasture; vanilla:STATE_SYRIA 30 farm.
- Layer: BSk 72 %, BWk 19 %, Cs 9 % -> steppe. Indicative 23.
- Proposal: `steppe`, 0, **pasture**, livestock_ranch wheat_farm. Confirm layer; pasture on the same
  south-of-the-gulf rule. The mod gives it a human owner, so farm is arguable (open question 3).
- Tier: B.

### STATE_BLACK_PENINSULA — Black Peninsula (MON, Monteaux)
- Identity: canon peninsula between the Lagoon of Tears and the Black Gulf; hubs Myrmidens, Kasos, Thessos
  (canon towns), Achaes (port city, Stone and Steel map), Talshunar (lighthouse, TOW).
- Canon: Myrmidens is a sprawling cliff port founded from Luccini, the largest Border Princes realm at about
  7,000 people, living on trade and mercenaries (fandom:Myrmidens, fandom:Border_Princes [Renegade Crowns;
  Lords of the Lance ch. 2]; lex:Myrmidens). Kasos Rock is a cliff-top fastness with cave wharfs (fandom:Kasos
  [Lords of the Lance]). Razorbills nest in thousands along its cliffs (fandom:Black_Peninsula [Imperial Zoo
  p. 77]). The "mild climate" line cites Total War only. No farming text.
- Analogue: a rocky Adriatic or Aegean coast colonised from Italy; vanilla:STATE_DALMATIA 20,
  vanilla:STATE_ATTICA 25, both mediterranean, farm, wheat livestock vineyard.
- Layer: BSk 51 %, Cs 46 % -> steppe by a hair. Indicative 36 (layer mix); 38 as mediterranean -1.
- Proposal: `mediterranean`, **-1**, farm, wheat_farm livestock_ranch vineyard. Half the state already reads
  Cs; a Tilean colony on a cliff coast is the Mediterranean class, and the step down is for the cliffs. This
  lands on the layer's own mix, so it is a tidy-up of the class label and the crop list (no cotton), not a
  change of size.
- Tier: R.

### STATE_LOST_KHYPNIA — Lost Khypnia (UVE, Uvetovsk)
- Identity: the Khyprian heartland east of the Kharnos; mine hub **Malko**; hubs Brasov, Moslac, Somjek (Stone
  and Steel map names); city Uvetovsk (TOW prince).
- Canon: see 1.1. Malko stands in an especially fertile area with rich farms, agricultural towns, a network of
  storehouses and barns; one of the region's largest crop producers; "the breadbasket of the Border Princes";
  and for that reason every warlord's target (fandom:Malko [General's Compendium p. 54; AJ Orc and Goblin Tribes
  pp. 12-15]; lex:Malko the same). The Tana Dante's lands are especially fertile by the region's standards
  (fandom:Tana_Dante [Plague Daemon]).
- Analogue: a small Wallachia; vanilla:STATE_WALLACHIA 85, vanilla:STATE_BULGARIA 35, both river plain, farm.
- Layer: BSk 75 %, Cs 25 % -> steppe. Indicative 27 (layer mix); 63 as river plain -1.
- Proposal: `temperate_river_plain`, **-1**, farm, **wheat_farm** livestock_ranch vineyard. The strongest
  farming text in the whole file, on both wikis, tied to a river. The step down keeps it a frontier granary
  behind a makeshift palisade rather than a Lombardy. It becomes the file's richest state, which is what canon
  says it is. The alternative, `steppe` +2 (indicative 37), leaves it below the forest states.
- Tier: A.

### STATE_WINTERTEETH_PASS — Winterteeth Pass (WIS, Wissenland)
- Identity: the Winter's Teeth Pass through the Black Mountains; one province; hub Fort Soll (TW).
- Canon: castles and forts watch the pass against orc raids (fandom:Black_Mountains [Empire 8e p. 24; Sigmar's
  Heirs p. 5]); the route down the Yetzin valley is plagued by bandits and goblins (fandom:Kreutzhofen).
- Analogue: vanilla:STATE_TYROL 30, farm (scaled to one province).
- Layer: Dc 100 % -> boreal_forest. Indicative under 1 either way (floor 2).
- Proposal: `highland_alpine`, 0, farm, livestock_ranch rye_farm. A mountain pass, not taiga; the swap changes
  nothing measurable.
- Tier: B.

### STATE_ORTEGETA — Ortegeta (ORT, Border Prince)
- Identity: realm of Fulma Ortegeta, an Estalian exile of 2276 IC (fandom:Fulma_Ortegeta [TOW website; AJ War of
  Settra's Fury]). On the canvas it is the Black Mountains' southern foot north of Khypnia. That position is
  read from the mod's map, not from canon.
- Canon for that country: the lands north and west of the Tana Dante are barren, desolate waste with isolated
  valleys that sometimes grow grain but mostly turnips, beets and cabbages, with meagre surpluses
  (fandom:Khypris [Plague Daemon ch. 1]); the southern slopes of the Black Mountains belong to the Zani,
  aurochs-herding hill tribes who graze thorn scrub and raid the farms (fandom:Zani [General's Compendium
  p. 49]).
- Analogue: Montenegrin karst; vanilla:STATE_MONTENEGRO 38 farm; herding uplands vanilla:STATE_KARS 10.
- Layer: Dc 55 %, BSk 43 % -> boreal_forest. Indicative 8 either way.
- Proposal: `highland_alpine`, **-1**, **pasture**, livestock_ranch rye_farm. Herders' hills with root-crop
  valleys. Rye stands in for the poor-valley staple (inference; canon names only roots and "sometimes grain").
- Tier: B.

### STATE_SHATTERED_TEETH — Shattered Teeth (KIZ, Karak Izor)
- Identity: Karak Izor under the Vaults (city hub). Only 1,219 px are passable; three provinces are impassable.
- Canon: see 1.1: human villages farm the sheltered valleys, Hochstadt by cereals and stock; the hold produces
  grain for trade; the valleys near the Vaults are one of the Border Princes' few areas of good farm country,
  with excellent cattle pasture and modest harvests.
- Analogue: Alpine valley farming; vanilla:STATE_TYROL 30, vanilla:STATE_EAST_SWITZERLAND 40, both farm.
- Layer: BSk 68 %, Dc 32 % -> steppe. Indicative 5 (layer); 10 as highland +1.
- Proposal: `highland_alpine`, **+1**, **farm**, wheat_farm livestock_ranch. The grain-hold ruling stands. The
  number will still be small because the model is area-driven and this state's passable area is tiny (open
  question 7).
- Tier: A.

### STATE_BLACK_MOUNTAINS — Black Mountains (KHI, Karak Hirn)
- Identity: Karak Hirn with Karak Angazhar, Karak Gantuk and Migdhal Vongalbarak (all hubs). 788 px passable.
- Canon: trading holds on iron, gold and silver; villages tucked in valleys; every gazetteer village makes
  grain, most also wool (see 1.1); the mountains are famous for furs and hunting (fandom:Karak_Angazhar
  [Sigmar's Heirs p. 180]; lex:Black_Mountains).
- Analogue: vanilla:STATE_EAST_SWITZERLAND 40, farm, rye livestock vineyard.
- Layer: Dc 93 % -> boreal_forest. Indicative 2 (layer); 4 as highland.
- Proposal: `highland_alpine`, 0, **pasture**, livestock_ranch wheat_farm. I keep the standing dwarf ruling
  because the hold-level text is about wool as much as grain and nothing is exported, but the gazetteer is a
  real argument for farm (open question 2).
- Tier: A.

### STATE_EASTERN_BORDER_PRINCES — Eastern Border Princes (ESS, Esselhafen)
- Identity: the Northern Border Confederacy's country; farm hub **Brovska**, wood hub **Styratia** (= Styrtia),
  mine hub Wissenheim (a town on the River Weiss north of Barak Varr, fandom:Border_Princes [Shadow of the
  Horned Rat, game]).
- Canon: Brovska lives by agriculture and cattle; Styrtia by agriculture, cattle and vineyards; each has about
  450-500 people (fandom:Border_Princes [Renegade Crowns]; lex:Border_Princes the same).
- Analogue: Balkan march; vanilla:STATE_BOSNIA 40 farm, wheat livestock vineyard.
- Layer: BSk 91 %, Dc 9 % -> steppe. Indicative 19.
- Proposal: `steppe`, 0, farm, livestock_ranch wheat_farm vineyard. Confirm layer. The class default crop list
  is exactly what canon names.
- Tier: A.

### STATE_BLACK_FIRE_PASS — Black Fire Pass (AVE, Averland)
- Identity: canon pass; three provinces.
- Canon: a chasm of contorted lava between cliffs of black volcanic glass with vapour vents; the Old Dwarf Road
  runs along its floor; Averland garrisons it with hunters and trappers (fandom:Black_Fire_Pass [WFRP 3e Black
  Fire Pass]; lex:Black_Fire_Pass [Black Fire Pass pp. 3-14]).
- Analogue: none needed; a pass.
- Layer: Dc 65 %, BSk 35 % -> boreal_forest. Indicative 2-3.
- Proposal: `highland_alpine`, **-1**, farm, livestock_ranch rye_farm. Lava and glass do not plough; no vines.
- Tier: A.

### STATE_FOREST_OF_GLOOM — Forest of Gloom (unowned)
- Identity: canon forest near Black Fire Pass and Karaz-a-Karak.
- Canon: part of the Black Deeps forest belt; once a verdant wood-elf colony sacred to Loec; Chaos Dwarfs burn
  it every hundred years, last in 2497 IC; by the 2500s it is infested with spider-riding forest goblins and
  beastmen (fandom:Forest_of_Gloom [Renegade Crowns p. 6 map; Lords of Stone and Steel p. 6]; fandom:Black_Deeps
  [Beastmen 7e p. 20]; lex:Forest_of_Gloom [WD 170 pp. 50-69]). Forest goblins raid farms and eat spiders; they
  do not farm (lex:Forest_Goblin [O&G 4e pp. 36, 77]).
- Analogue: unsettled Balkan forest; vanilla:STATE_BOSNIA 40 is the settled ceiling.
- Layer: BSk 96 % -> steppe (the layer does not see the forest). Indicative 8 (layer); 13 as forest-hill -2.
- Proposal: `temperate_forest_hill`, **-2**, farm, livestock_ranch wheat_farm. A real forest by canon, so the
  class is corrected; two steps down because nobody has cleared or tilled it. Subsistence left at the class
  default: canon gives its holders neither fields nor herds (open question 3).
- Tier: A.

### STATE_OLD_DWARF_ROAD — Old Dwarf Road (unowned)
- Identity: the road corridor south of Black Fire Pass; city hub **Munzig**, farm hub **Akendorf**.
- Canon: Munzig is a wooden trading town on the Durich River below the forests that climb to the pass, living
  on timber, sheep and its market; Akendorf, about 800 people in a confined valley west of the Thunder River,
  lives on timber, woodcarving, hogs and furs; the haunted Geistenmund Hills lie south (fandom:Munzig [Gilead's
  Blood; Renegade Crowns p. 42]; fandom:Border_Princes, fandom:Akendorf, fandom:Geistenmund_Hills [Renegade
  Crowns; General's Compendium pp. 50-51]; lex:Akendorf, lex:Border_Princes).
- Analogue: Serbian or Bosnian forest march, stock before grain; vanilla:STATE_BOSNIA 40 farm.
- Layer: BSk 70 %, BWk 30 % -> steppe. Indicative 17 (layer mix).
- Proposal: `steppe`, 0, farm, livestock_ranch wheat_farm vineyard. Confirm layer. Canon's economy here is
  wood, hogs, sheep and furs: a logging state (for #3687), not a ploughed one, so the forest is no reason to
  raise arable. The stand-in's 101 has no support.
- Tier: A.

### STATE_HOWLING_RIVER_VALLEY — Howling River Valley (RAA, Raachwald)
- Identity: canon river; wood hub Vitrolle is the city canon puts on it; mine hub Zenres is a canon town
  between the Skull River and the World's Edge (fandom:Border_Princes [Lure of the Liche Lord pp. 22-23]).
- Canon: three ice-cold, mineral-tasting, dangerously fast branches off the World's Edge either side of Mad Dog
  Pass; few creatures live in it (fandom:Howling_River [Lure of the Liche Lord p. 22]). A cold torrent, not an
  irrigation river. Mad Dog Pass makes the valley a thoroughfare fought over by three princes
  (fandom:Mad_Dog_Pass).
- Analogue: vanilla:STATE_BULGARIA 35 farm; vanilla:STATE_DOBRUDJA 10.
- Layer: BSk 80 %, BWk 20 % -> steppe. Indicative 15.
- Proposal: `steppe`, 0, farm, livestock_ranch wheat_farm vineyard. Confirm layer. No `temperate_river_plain`:
  the river's own description rules out a fertile floodplain.
- Tier: B.

### STATE_BLOOD_RIVER_VALLEY — Blood River Valley (ICL, Iron Rock orcs)
- Identity: canon border river; city hub **Iron Rock**.
- Canon: the Blood River is the large southern river, the line between the Border Princes and the Badlands, and
  the crusaders of 1452 IC cleared greenskin strongholds along it (fandom:Blood_River [Night of the Daemon];
  lex:Border_Princes [Bretonnia 5e pp. 14-16]). Iron Rock is an iron mountain held by orcs for 800 years
  (fandom:Badlands [BitB p. 9]). No fertility text for the valley.
- Analogue: a steppe river held by raiders; vanilla:STATE_ASTRAKHAN 45 pasture; vanilla:STATE_KALMYKIA 8.
- Layer: BSk 94 % -> steppe. Indicative 19-20.
- Proposal: `steppe`, 0, **pasture**, livestock_ranch wheat_farm. Confirm layer. Not `desert_river`: the valley
  is steppe, not desert, and canon never calls it fertile. Wheat stays in the crop list as the land's
  potential under a settled owner.
- Tier: B.

### STATE_GIANT_STOMPING_GROUNDS — Giant Stomping Grounds (unowned)
- Identity: canon name for the Dragonback foothills above the gulf.
- Canon: an unusually dense giant population wanders these foothills, perhaps escaped from the Bloody Handz
  tribe's holding pens (fandom:Giant_Stomping_Grounds [BitB p. 10]). A giant eats a whole herd at a sitting
  (lex:Giant [O&G 8e p. 60]).
- Layer: BWh 88 %, BWk 11 % -> open_desert. Indicative 5.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_SOUTH_BADLAND_HILLS — South Badland Hills (unowned)
- Identity: mod name; hills between the Dragonbacks and the marsh basin; hubs are TW names.
- Canon: realm only. (A crescent of hills from the Dragonbacks to the Nehekharan sands rings the marsh basin:
  fandom:Marshes_of_Madness, cited to Warhammer Online, so a lead.)
- Layer: BWh 83 %, BWk 17 % -> open_desert. Indicative 6.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_WESTERN_BADLANDS — Western Badlands (unowned)
- Identity: the western foothills on the shore; mine hub Bloody Hand Hold.
- Canon: the Bloody Handz claim the western foothills of the Badlands near the shore and are among the richest
  orc tribes through yearly raids on Tilea and Araby; giants and trolls join them for the food
  (fandom:Bloody_Handz_Tribe; lex:Bloody_Hand_Tribe [O&G Collectors' Guide p. 3]).
- Layer: BWh 54 %, BWk 46 % -> open_desert. Indicative 5.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer. Part A's `highland_alpine` rested only on
  a heightmap flag. A raiding tribe's wealth is plunder, not land.
- Tier: B.

### STATE_MARG_BEH_MARD — Marg-Beh-Mard (unowned)
- Identity: the name appears on neither wiki; hubs Teshert and Salt Plain are TW names. Unverified name.
- Canon: realm only (shifting sand toward Nehekhara).
- Layer: BWh 100 % -> open_desert. Indicative 3.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_NORTH_BARRIER_IDOLS — North Barrier Idols (unowned)
- Identity and canon: as East Barrier Idols; hubs Gork Idol, Shrunken Headz Idol (the Shrunken Headz are named
  in the idol text, fandom:Badlands [TOW website; TWW3]).
- Layer: BWh 100 % -> open_desert. Indicative 3.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Confirm layer.
- Tier: B.

### STATE_SUNKEN_KHEMARCH — Sunken Khemarch (RDV)
- Identity: the marsh's northern half. Both wikis give the Nehekharan name as the "Sinking Marshes of
  Khernarch" [Tomb Kings 6e p. 10]; the state's "Khemarch" is that name with rn read as m. Worth correcting in
  the naming worksheet.
- Canon: as Marshes of Madness. Naqqara lies between the Dragonbacks and the Blind River, about here.
- Layer: BWh 100 % -> open_desert. Indicative 6.
- Proposal: `open_desert`, 0, pasture, livestock_ranch. Same reasoning as the Marshes of Madness.
- Tier: A.

### STATE_KHARNOS_FOREST — Kharnos Forest (BPR)
- Identity: named for the canon forest; farm hub **Khypris**, mine hub Mentreda, city Matorea.
- Canon: the Kharnos is a dense oak forest from the rugged Lagoon of Tears coast up into the Apuccini, full of
  brigands (fandom:Kharnos_Forest [TOW website; Lords of the Lance ch. 12]; lex:Kharnos_Forest). Khypris sits
  in an unusually fertile, prosperous patch with a grain industry; Mentreda is ringed by grazed fields; Matorea
  is a large coastal town (fandom:Khypris, fandom:Border_Princes, fandom:Matorea [Plague Daemon chs. 1, 6]).
- Analogue: Balkan forest-and-valley country; vanilla:STATE_BOSNIA 40, vanilla:STATE_MONTENEGRO 38, farm.
- Layer: Df 49 %, Cs 40 %, BSk 11 % -> temperate_forest_hill. Indicative 46-49.
- Proposal: `temperate_forest_hill`, 0, farm, **wheat_farm** livestock_ranch vineyard. Confirm layer class;
  forest and fertile patch cancel out. Crops overridden from the class default's rye: canon says grain and
  herds, and every vanilla Balkan state grows wheat.
- Tier: A.

### STATE_GASTONNE — Gastonne (GAS)
- Identity: realm of Sir Cecil Gastonne, whose stronghold was Louen Keep, an old Bretonnian exiles' fort
  guarding the south-eastern approaches to Bretonnia, toward the Vaults (fandom:Louen_Keep,
  fandom:Border_Princes [TOW website; AJ War of Settra's Fury]). No hub rows. Where it lies is read from the
  mod's map.
- Canon: none for the place. If it is Vaults foothill country, the valleys near the Vaults are good farm
  country and cattle pasture, while the Apuccini foothills are heavily forested and nearly uninhabited
  (fandom:Border_Princes [General's Compendium p. 49; WFRP 1e pp. 271-274]; lex:Apuccini_Mountains [WFRP 1e
  pp. 270-271, 279]).
- Analogue: vanilla:STATE_BOSNIA 40, vanilla:STATE_MONTENEGRO 38.
- Layer: Df 84 % -> temperate_forest_hill. Indicative 48 at step 0, 35 at -1.
- Proposal: `temperate_forest_hill`, **-1**, farm, livestock_ranch wheat_farm vineyard. Without the step this
  unnamed forest foothill would out-farm everything but Malko; the realm text (limited fertile land, poor soil)
  is the evidence for the cap.
- Tier: C.

## 3. Rows

```csv
state_key,lore_class,fertility_step,subsistence,crops,tier,note,source
STATE_AQUILENA,steppe,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,R,"Confirm layer. TOW prince realm, no land-use text; realm canon: thorn plains, herdsmen, limited fertile land",fandom:Border_Princes#Geography [General's Compendium pp. 48-49; WFRP 1e pp. 271-274] ; vanilla:STATE_DOBRUDJA arable 10 farm
STATE_NORTH_BADLAND_HILLS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Confirm layer. Barren rock and arid plain; greenskins herd and raid, none farm",fandom:Badlands [Blood in the Badlands pp. 6-11] ; fandom:Greenskins [Old World Bestiary p. 22]
STATE_EAST_BARRIER_IDOLS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Idol line on the Nehekharan border; shifting sand; Savage Orc rituals,fandom:Barrier_Idols [TOW website] ; lex:Badlands [Orcs & Goblins 8e p. 12]
STATE_WORLDS_EDGE_FOOTHILLS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Raiding tribes under the mountain front; no land-use text,"fandom:Badlands [Blood in the Badlands pp. 6-11] ; fandom:Bloody_Tusks [Orcs & Goblins 8e pp. 8, 13]"
STATE_EASTERN_BADLANDS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Arid eastern plain; ancient dwarf barley farms are pre -1500 IC and thinly sourced,fandom:Badlands [Blood in the Badlands pp. 6-11] ; fandom:Morgheim [Undead 4e pp. 19-21]
STATE_BLIGHTWATER,open_desert,-1,building_subsistence_pasture,building_livestock_ranch,A,"Poisoned river: once fertile fields, now water that kills and raises zombies. No desert_river",fandom:Blight_Water [Blood in the Badlands p. 11] ; lex:Blight_Water [AJ Orc & Goblin Tribes p. 8; Warhammer: Nagash I p. 226]
STATE_MARSHES_OF_MADNESS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,"Virulent swamp, maddening water, no cultivation; no swamp class and no coast for a fishing village",fandom:Marshes_of_Madness [Blood in the Badlands pp. 10-11; Tomb Kings 6e p. 10] ; lex:Boglar [WD 310 p. 90]
STATE_BADLANDS_COAST,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Desert coast of pirates and orc hulks; fishing villages only in a -1149 IC novel scene,fandom:Badlands [Blood in the Badlands pp. 6-11] ; fandom:Black_Gulf [Blood in the Badlands p. 8; Master of Death ch. 11]
STATE_OLD_STRYGOS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,Confirm layer. Mourkain ruins; the land was not fertile even at its height; cursed river; ghoul court,fandom:Morgheim [Undead 4e pp. 19-21; Blood in the Badlands p. 10] ; lex:Strigoi [Night's Dark Masters pp. 66-73]
STATE_MOUNT_BLOODHORN,open_desert,1,building_subsistence_pasture,building_livestock_ranch,A,Orc fortress breeding cave squigs in thousands for export: the one named herding industry,fandom:Mount_Bloodhorn [Blood in the Badlands p. 9] ; lex:Ekrund [Blood in the Badlands p. 9]
STATE_DRAGONBACK_MOUNTAINS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Confirm layer. Arid range of giants, trolls and greenskins; no valley or pasture text",fandom:Badlands [Blood in the Badlands pp. 9-10] ; lex:Dragonback_Mountains [Blood in the Badlands pp. 9-10]
STATE_STINKLANDS,open_desert,-1,building_subsistence_pasture,building_livestock_ranch,B,Stinking Geysers: a place so foul only goblins hiding from others camp there. Weakly held step,lex:Badlands#Locations [Orcs & Goblins 8e p. 12]
STATE_THE_BLIGHT,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Broken Tooth country; realm text only,"fandom:Badlands [Blood in the Badlands pp. 6-11] ; fandom:Broken_Tooth_Tribe [Orcs & Goblins 8e pp. 13, 17-19]"
STATE_CENTRAL_BADLANDS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Central arid plain with Naqqara and Stormhenge; realm text only,fandom:Badlands [Blood in the Badlands pp. 6-11] ; fandom:Naqqara [Blood in the Badlands p. 34]
STATE_CROOKED_MOUNTS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Confirm layer. Crooked Fang Fort stands in the centre of the plains: not a mountain state, drop KA-01",lex:Badlands#Locations [Orcs & Goblins 8e p. 12; Blood in the Badlands]
STATE_THE_CAULDRON,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Realm text only; Pillar of Bone,fandom:Badlands [Blood in the Badlands pp. 6-11]
STATE_VARENKA_HILLS,steppe,1,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,"Barak Varr: grain and wool industries; village of 8,000 on grain, cheese, wool. Farm, against dwarf ruling",fandom:Barak_Varr [Lords of Stone and Steel p. 23] ; fandom:Varenka_Hills [TOW website; Dwarf Player's Guide p. 111]
STATE_NORTHERN_BADLANDS,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,Confirm layer mix. Orc-infested corner crossed by the Old Silk Road; half desert; no vineyard,fandom:Old_Silk_Road [Dawn of the Storm Dragon p. 9] ; fandom:Badlands [Blood in the Badlands p. 9] ; vanilla:STATE_KALMYKIA arable 8 pasture
STATE_MYRMIDIA_S_COAST,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,Confirm layer. Dragonback foot south of the gulf; giants roam; no land-use text,fandom:Giant_Stomping_Grounds [Blood in the Badlands p. 10] ; fandom:Citadel_of_Myrmidia [TOW website]
STATE_BLACK_PENINSULA,mediterranean,-1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,R,"Tilean-founded cliff port Myrmidens; razorbill cliffs; no farming text. Class by analogue, equals layer mix",fandom:Myrmidens [Lords of the Lance ch. 2; Renegade Crowns] ; fandom:Black_Peninsula [Imperial Zoo p. 77] ; vanilla:STATE_DALMATIA arable 20 farm
STATE_LOST_KHYPNIA,temperate_river_plain,-1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,"Malko: especially fertile, rich farms, storehouses, the breadbasket of the Border Princes",fandom:Malko [General's Compendium p. 54; AJ Orc and Goblin Tribes pp. 12-15] ; lex:Malko [AJ Orc & Goblin Tribes pp. 13-15] ; fandom:Tana_Dante [Plague Daemon]
STATE_WINTERTEETH_PASS,highland_alpine,0,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,"One-province mountain pass watched by forts; class by name, no measurable effect",fandom:Black_Mountains [Empire 8e p. 24; Sigmar's Heirs p. 5]
STATE_ORTEGETA,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch building_rye_farm,B,"Black Mountain foot: barren waste, valleys of turnips, beets, cabbages; Zani aurochs herders. Position inferred",fandom:Khypris [Plague Daemon ch. 1] ; fandom:Zani [General's Compendium p. 49] ; lex:Khypris [WD 125 pp. 12-16]
STATE_SHATTERED_TEETH,highland_alpine,1,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,Karak Izor: human villages farm sheltered valleys; grain produced for trade. Grain-hold ruling stands,fandom:Karak_Izor [Stone and Steel pp. 36-37] ; fandom:Hochstadt [Stone and Steel p. 112] ; lex:Karak_Izor [Lords of Stone and Steel p. 23]
STATE_BLACK_MOUNTAINS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,"Karak Hirn group: gazetteer villages make grain and wool; furs. Ruling kept, farm is arguable","fandom:Karak_Hirn [Lords of Stone and Steel p. 23] ; fandom:Karak_Angazhar [Lords of Stone and Steel pp. 15, 23] ; fandom:Dwarfs#Economy [Stone and Steel pp. 17-20]"
STATE_EASTERN_BORDER_PRINCES,steppe,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,A,"Confirm layer. Brovska: agriculture and cattle; Styrtia: agriculture, cattle, vineyards; ~500 people each",fandom:Border_Princes#Settlements [Renegade Crowns] ; lex:Border_Princes#Locations [Renegade Crowns]
STATE_BLACK_FIRE_PASS,highland_alpine,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,Lava chasm between volcanic glass cliffs; garrison of hunters and trappers; no vines,fandom:Black_Fire_Pass [WFRP 3e Black Fire Pass] ; lex:Black_Fire_Pass [Black Fire Pass pp. 3-14]
STATE_FOREST_OF_GLOOM,temperate_forest_hill,-2,building_subsistence_farm,building_livestock_ranch building_wheat_farm,A,"Real forest (Black Deeps belt), burnt 2497 IC, held by forest goblins and beastmen; untilled",fandom:Forest_of_Gloom [Renegade Crowns p. 6; Lords of Stone and Steel p. 6] ; fandom:Black_Deeps [Beastmen 7e p. 20] ; lex:Forest_of_Gloom [WD 170 pp. 50-69]
STATE_OLD_DWARF_ROAD,steppe,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,A,"Confirm layer. Munzig: timber, sheep, market; Akendorf: timber, hogs, furs. Logging, not ploughland",fandom:Border_Princes#Settlements [Renegade Crowns] ; fandom:Munzig [Gilead's Blood; Renegade Crowns p. 42] ; lex:Akendorf [WD 125 p. 31]
STATE_HOWLING_RIVER_VALLEY,steppe,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,B,"Confirm layer. Ice-cold, fast, near-lifeless river: no floodplain farming; no river-plain class",fandom:Howling_River [Lure of the Liche Lord p. 22] ; fandom:Border_Princes#Geography [General's Compendium pp. 48-49]
STATE_BLOOD_RIVER_VALLEY,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,Confirm layer. Border river held by Iron Rock orcs; no fertility text; not desert_river,fandom:Blood_River [Night of the Daemon chs. 1-5] ; fandom:Badlands [Blood in the Badlands p. 9]
STATE_GIANT_STOMPING_GROUNDS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Dragonback foothills full of wandering giants,fandom:Giant_Stomping_Grounds [Blood in the Badlands p. 10]
STATE_SOUTH_BADLAND_HILLS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Realm text only,fandom:Badlands [Blood in the Badlands pp. 6-11]
STATE_WESTERN_BADLANDS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Confirm layer. Bloody Handz foothills: a tribe rich from sea raids, not from land",fandom:Bloody_Handz_Tribe [Orcs & Goblins Collectors' Guide p. 3] ; lex:Bloody_Hand_Tribe [Orcs & Goblins Collectors' Guide p. 3]
STATE_MARG_BEH_MARD,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Name on neither wiki; sand toward Nehekhara; realm text only,lex:Badlands [Orcs & Goblins 8e p. 12] ; fandom:Badlands [Blood in the Badlands pp. 6-11]
STATE_NORTH_BARRIER_IDOLS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,Confirm layer. Idol line on the Nehekharan border; shifting sand,fandom:Barrier_Idols [TOW website] ; lex:Badlands [Orcs & Goblins 8e p. 12]
STATE_SUNKEN_KHEMARCH,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,"Northern Marshes of Madness (canon spelling Khernarch): poison swamp, no cultivation",fandom:Marshes_of_Madness [Blood in the Badlands pp. 10-11; Tomb Kings 6e p. 10] ; lex:Marshes_of_Madness [Orcs & Goblins 8e pp. 12-13]
STATE_KHARNOS_FOREST,temperate_forest_hill,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,Confirm layer class. Dense oak brigand forest plus the fertile Khypris patch (grain) and grazed fields,"fandom:Kharnos_Forest [TOW website; Lords of the Lance ch. 12] ; fandom:Khypris [Plague Daemon chs. 1, 6] ; lex:Khypris [WD 125 pp. 12-16]"
STATE_GASTONNE,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,C,"TOW prince realm (Louen Keep); place by inference; cap on the realm text: limited fertile land, poor soil",fandom:Louen_Keep [TOW website] ; fandom:Border_Princes#Geography [General's Compendium pp. 48-49; WFRP 1e pp. 271-274]
```

39 rows. Tiers: A 14, B 22, R 2, C 1. Subsistence: pasture 26, farm 13.

Indicative arable before world scaling (sum of the rows): about 510 for the file, against 480 from the raw
layer and 1,365 emitted today by the stand-in model. Within it the Badlands proper hold about 120, the three
northern-Badlands steppe states about 60, the Border Princes and holds about 330.

## 4. Disagreements

### With the climate layer

| state | layer | proposal | why |
|---|---|---|---|
| Lost Khypnia | steppe | temperate_river_plain -1 | Malko's fertile fields; strongest farm text in the file |
| Black Peninsula | steppe (51 % BSk, 46 % Cs) | mediterranean -1 | Tilean cliff-coast colony; equals the layer's own mix in size |
| Forest of Gloom | steppe | temperate_forest_hill -2 | canon forest the layer cannot see; untilled |
| Shattered Teeth | steppe | highland_alpine +1 | Karak Izor's valley farms, grain for trade |
| Black Mountains, Winterteeth Pass, Black Fire Pass, Ortegeta | boreal_forest (Dc) | highland_alpine (0, 0, -1, -1) | mountain cold at 40 N is alpine, not taiga; sizes barely move |
| Varenka Hills | steppe | steppe +1 | Barak Varr's grain and wool village |
| Blightwater, Stinklands | open_desert | open_desert -1 | poison river; the geyser field |
| Mount Bloodhorn | open_desert | open_desert +1 | squig-breeding export |
| Gastonne | temperate_forest_hill | same, -1 | realm text on poor soil; keeps an unnamed foothill below Malko |
| Marshes of Madness, Sunken Khemarch | open_desert | same | agreement by accident: the layer sees desert, canon a swamp; both mean no farmland |

Everything else confirms the layer. The layer's reading of the Border Princes as steppe, which looked wrong
beside the Balkan stand-in, is what canon says.

### With the earlier part-A leads

- **Badlands realm reading (`steppe`, position low).** Canon's own word is "steppes" in one army book and
  "searing desert" in the campaign book; the land "was not fertile" even under Strygos. I follow the layer:
  `open_desert` for the 21 states the layer reads as desert, `steppe` only for the three northern ones it reads
  as steppe. In size the two readings are close (steppe two steps down is about 2.1 per 1,000 px, open desert
  1.0); the difference is that the model no longer needs a realm-wide step.
- **SRB-06 (Marshes of Madness and Sunken Khemarch as `tropical_savanna`, two steps down).** Re-tested: the
  canon text holds on both wikis, but savanna is the wrong vehicle. It yields about 2.6 per 1,000 px, more than
  the surrounding desert, for a swamp whose water is poison. `open_desert` at step 0. Also the Nehekharan name
  is Khernarch, not Khemarch.
- **KA-01 (Crooked Mounts as `highland_alpine`).** Rejected for this state: its canon feature stands on a
  plain and the heightmap is flat. (Dragon Crag and West Mad Dog Pass are not in this file.)
- **KA-02 (Forest of Gloom as `temperate_forest_hill`).** Confirmed, and it now has text, not only a name; add
  two steps down.
- **KA-03 (Cripple Peak, Desolation of Nagash, Sour Crags).** These states are not in `06_badlands.txt`, so no
  rows here. The pages agree with the draft: a parched desert surrounds Nagashizzar (fandom:Desolation_of_Nagash;
  lex:Desolation_of_Nagash [Undead 4e p. 7]); warpstone dust from Cripple Peak poisoned the sea for ever
  (fandom:Sour_Sea, fandom:Cripple_Peak; lex:Sour_Sea [Undead 4e pp. 14-16]). One addition for whoever owns
  them: the Sour Sea is the Blight Water's source, so the poison argument runs downstream into Blightwater.
- **SRB-01 to SRB-05** are Southern Realms entries and belong to the sibling dossier; not re-tested.
- **Border Princes as `temperate_forest_hill` on a realm statement (part A open question 17).** Rejected for
  the open country: the fuller text says thorn-tree plains, herdsmen and limited fertile land. Kept only where
  the layer itself reads forest (Kharnos Forest, Gastonne) and for the Forest of Gloom.
- **Karak Izor as a grain hold.** Confirmed with two more sources than the ruling cites.
- **Part A's Tier C states Ortegeta, Gastonne, Old Dwarf Road.** Ortegeta and Old Dwarf Road now have canon
  text (B and A); Gastonne stays C.

## 5. Open questions for Chris

1. **Is `open_desert` right for the whole Badlands interior?** It follows your accepted climate layer and the
   campaign book. It gives each Badlands state an indicative 3 to 11 arable before scaling, so several will sit
   under the validator's 10-arable warning and under the mass-migration threshold. If you want the greenskin
   heartland to carry more pasture slots, the lever is one realm-wide step up, not a class change.
2. **Dwarf holds: does the WFRP 4e gazetteer extend the grain-hold list?** Lords of Stone and Steel p. 23 (as
   the Fandom dump reports it; I could not corroborate it on Lexicanum) lists grain for every named village of
   Karak Hirn, Karak Angazhar and Karak Gantuk and gives Barak Varr grain and wool industries with a farming
   village of 8,000. I proposed farm for Barak Varr (lowland port) and kept pasture for the Black Mountains.
   Either both farm or both pasture is defensible; the Karaz Ankor dossier will meet the same page.
3. **Subsistence by land or by owner?** I used one rule: pasture south of the Blood River and the Black Gulf,
   farm north of it, whoever owns the state. That makes the human-owned Northern Badlands and Myrmidia's Coast
   herd, and leaves the goblin-held Forest of Gloom on the forest default (farm), since canon gives its goblins
   neither fields nor herds. Say if you would rather key it on the starting owner.
4. **Dragonback Mountains: desert or highland?** Kept `open_desert` (arid, no canon valley). `highland_alpine`
   one step down would be about three times as much. Mount Bloodhorn would follow the same call.
5. **Fishing villages.** No present-day text supports one anywhere in this file. Leads only: pontoon fishing
   villages on the gulf coast in a novel scene set in -1149 IC; Barak Varr as a sea hold; Myrmidens as a port.
   If you want one coastal exception, the Black Peninsula is the least forced.
6. **Where is the Kharnos Forest?** The TOW map text puts it in the south-western Borderlands rising from the
   Lagoon of Tears into the Apuccini. On the canvas that sounds like Aquilena or Gastonne as much as the state
   that carries the name. If Aquilena is the forest, it wants `temperate_forest_hill` with a step down instead
   of `steppe`.
7. **Holds and area.** Shattered Teeth has 1,219 passable px and the Black Mountains 788, so an area-driven
   model gives a grain hold an indicative 10 and Karak Hirn 4, whatever the lore row says. If holds should carry
   more, the model needs a floor for hold states; a fertility step cannot do it.
8. **Two fertile cores, three states.** Malko's hub is in Lost Khypnia and Khypris's in Kharnos Forest, and
   both belong to the same Khyprian country. I put the river-plain class on Lost Khypnia only. If you see
   Kharnos Forest as the Khypris plain rather than the forest, swap its class too.
9. **Names to check.** "Sunken Khemarch" (canon Khernarch); "Marg-Beh-Mard" (on neither wiki); the TOW prince
   realms are dated 2276 IC, 226 years before the start date, which is your design call, not a lore finding.
10. **Stinklands' step down** rests on one sentence about one hub. Drop it to 0 if you prefer steps only on
    state-wide evidence.

## 6. Pages read

**Fandom dump (`sources/wiki/pages/`, 2026-11-20).** Read in full: Badlands; Border Princes (Geography, Notable
Locations and Sources sections; the rest by keyword lines). Read as extracted keyword lines plus the Sources
block (not every line of the article): Malko, Khypris, Akendorf, Munzig, Aldium, Matorea, Myrmidens, Kasos,
Thessos, Blood River, Howling River, Tana Dante, River Orco, Skull River, Blind River, Blight Water, Varenka
Hills, Black Peninsula, Lagoon of Tears, Black Gulf, Kharnos Forest, Forest of Gloom, Black Deeps, Geistenmund
Hills, Old Dwarf Road, Old Silk Road, Mad Dog Pass, Death Pass, Louen Keep, Zvörak, Sonnental, Zani, Border
Prince (Title), Fulma Ortegeta, Marshes of Madness, Morgheim, Strygos, Dragonback Mountains, Ekrund, Mount
Bloodhorn, Giant Stomping Grounds, Iron Rock, Hanging Rock, Stormhenge, Naqqara, Floating Village, Tree of
Beards, Barrier Idols, Swamp of Terror, Citadel of Myrmidia, Tor Anrok, Black Crag, Bloody Handz Tribe, Bloody
Hand (an unrelated Norse tribe), Broken Tooth Tribe, Scabby Eye Tribe, Ironclaw Tribe, Bloody Tusks, Greenskin
Tribes, Greenskins, Orcs, Goblin, Night Goblin, Savage Orcs, Squigs, River Trolls, Barak Varr, Karak Izor,
Hochstadt, Karak Hirn, Karak Angazhar, Karak Gantuk, Black Mountains, The Vaults, Black Fire Pass, Apuccini
Mountains, Dwarfs, Sour Sea, Desolation of Nagash, Cripple Peak; grep lines only from Kreutzhofen and Pfeildorf.
No article exists for Gordorno, Kalkmir or Marg-Beh-Mard.

**Lexicanum (browser pane, 2026-11-19, before the corroboration-only rule; none read after it).** Badlands,
Border Princes, Marshes of Madness, Blight Water, Blind River, Dragonback Mountains, Ekrund, Black Gulf,
Mourkain, Barak Varr, Iron Rock, Skull River, Naqqara, Forest of Gloom, Road, Kharnos Forest, Khypris,
Greenskin, Orc, Goblin, Squig, Boar, Fungus, Snotling, Night Goblin, Forest Goblin, Gnoblar, Boglar, Giant,
Great Wolf, Black Crag, Karak Izor, Karak Hirn, Karak Angazbar, Black Mountains, Black Fire Pass, The Vaults,
Apuccinis, Lagoon of Tears, Sour Sea, Desolation of Nagash, Cripple Peak, Nagashizzar, Strigoi, Dwarf, Renegade
Crowns, River, Matorea, Myrmidens, Malko, Akendorf, Sonnental, Kasos, Thessos, Zvork, High Spear, Tor Anrok,
Thunder Mountain, Bloody Hand Tribe, Broken Tooth Tribe, Bloody Sunz Tribe, Rusty Nail Tribe, Blue Face,
Pirates of the Black Gulf, Karolina Aquilena, Cecil Gastonne, Fulma Ortegeta, Gunter Dunkelmund, Jurgan
Esselhafen, Karl Raachwald, Valdos Uvetovsk, Adalene Monteaux. No page (404): Blood River, Howling River,
Thunder River, Varenka Hills, Black Peninsula, Alfori, Styrtia. In-page fetches began returning HTTP 429 and 403
part-way through that session; I switched to plain page navigation and did not use Lexicanum at all on
2026-11-20.

**Claims not corroborated on Lexicanum** (Fandom dump only): the Lords of Stone and Steel p. 23 village lists
for Barak Varr, Karak Hirn, Karak Angazhar and Karak Gantuk; the Zani; the Border Princes geography paragraph
from the General's Compendium; Akendorf's and Mentreda's economies; the Black Deeps; the Howling River's
description; the Undead 4e "not fertile" line on fandom:Morgheim; the Barrier Idols. **Lexicanum only**: the
Stinking Geysers, Crooked Fang Fort "in the centre of the plains", the Blight Water's fertile past.

**Fandom live site**: showed a bot-verification page on 2026-11-19; I did not attempt to pass it.

**Web (real world).** en.wikipedia.org/wiki/Mesopotamian_Marshes; /Marsh_Arabs; /Syrian_Desert; /Kazakh_Steppe;
/Virgin_Lands_campaign; /Karakum_Desert; /Economic_history_of_the_Ottoman_Empire; /Military_Frontier;
/Wild_Fields; /Dobruja; /Agriculture_in_Syria; /Agriculture_in_Kazakhstan; /Agriculture_in_Turkey; /Konya_Plain;
/Danubian_Principalities and /Principality_of_Serbia (nothing usable on farming). Web searches returned
summaries only for N. Lewis, Nomads and Settlers in Syria and Jordan 1800-1980 (Cambridge) and for e-history.kz
(Kazakh herd mix). Could not open: Pamuk's chapter on Turkish agriculture (404), the Powell's page for Lewis
(403), the Cambridge review of Lewis (no abstract).

**Vanilla install**: `game/map_data/state_regions/*.txt` for the analogue states in table 1.3.
