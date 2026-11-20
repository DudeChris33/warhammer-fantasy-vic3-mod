# Farmland lore dossier: The Dark Lands (`10_dark_lands.txt`)

Board item #3686 (child of epic #3675). Research run 2026-11-19 / resumed 2026-11-20. Status line is kept current
at the bottom of this file ("Progress").

- State file: `map_data/state_regions/10_dark_lands.txt`, **54 states** (counted from the file).
- `map_data/state_regions/11_ogre_kingdoms.txt` is **empty** (3 bytes, a BOM only): confirmed 2026-11-19.
- Citation forms: `lex:` = Lexicanum page read in the browser pane on 2026-11-19; `fandom:` = Fandom Warhammer Wiki
  (read live on 2026-11-19, or from the local dump `sources/wiki/` on 2026-11-20; the per-state text says which);
  `rw:` = real-world source; `vanilla:` = vanilla Victoria 3 state file on disk.
- Lexicanum returned HTTP 429 and then 403 during the first run. Per the brief's update it was not used again.
  Lexicanum pages read before the block are listed in section 6; nothing after the block is corroborated there.

## 1. Realm picture

### 1.1 What canon says about the land

**The realm statement (barren).** The Dark Lands lie between the Worlds Edge Mountains and the Mountains of
Mourn. The ground is riven and volcanic; tar pits and oil pools foul the plains; lava covers ash wastes. Dim light
and polluted air mean almost nothing grows except a few thin black thorns. The land is rich in minerals instead.
- lex:Dark_Lands#Overview [White Dwarf presents: Chaos Dwarfs p. 20; Orcs & Goblins 8e p. 14; the Lexicanum page
  carries a "needs better citations" banner and its Overview paragraph has no footnote of its own]
- fandom:Dark_Lands (lead) [Warhammer Armies: Chaos Dwarfs (the Fandom page labels it "5th Edition") p. 4]
- lex:Chaos_Dwarf#Domain [Tamurkhan: The Throne of Chaos pp. 38-48]: always barren, made more so by thousands of
  years of Chaos Dwarf industry, ash on the land and smoke in the sky.

**The stated exceptions (not barren).** The same Lexicanum Overview paragraph says the **south coast is covered in
thick forest**, as are **the foothills of the Worlds Edge Mountains and of the Mountains of Mourn**. This sentence
has no footnote on Lexicanum and I did not find it on the Fandom Dark Lands page: treat it as a weak, uncorroborated
lead (see open question Q3). **Gnoblar Country** is separately and firmly attested as green hills (below).

**Named regions with land-use text** (all read; detail in the per-state entries):

| canon place | what the text says | source |
|---|---|---|
| Plain of Zharr / Zharrduk | meteor crater, the Chaos Dwarf heartland; tar pits, burning oil, coal heaps, mines, slag; nothing is able to grow; one watercourse, the polluted Ruin | lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins, loose footnote]; fandom:Plain_of_Zharrduk [Chaos Dwarfs 4e; Battle Book 5e]; fandom:Chaos_Dwarfs [Tamurkhan p. 165] |
| Zorn Uzkul | vast high plateau, thin cold air, barren rock to the horizon, bone-strewn dust; the Dwarfs turned back at the sight of it | lex:Dark_Lands#Features Zorn Uzkul; fandom:Zorn_Uzkul [Tamurkhan pp. 164-165; Chaos Dwarfs 4e p. 6] |
| Howling Wastes | flat, desolate plain; near-constant gale; "blasted heath"; Chaos Dwarf rocket range; the Sentinels stand in it | lex:Dark_Lands#Features Howling Wastes; fandom:Howling_Wastes [White Dwarf 302 (UK) p. 17] |
| Wolf Lands | barren land and wind-carved rock around Crookback Mountain and Mount Grey Hag; wolf packs; only the fiercest animals survive | lex:Dark_Lands#Features Wolf Lands [Orcs & Goblins, loose footnote] |
| Blasted Wastes | parched great desert, sandstorms and burning sun, fights over water holes; scattered nomadic goblins in valleys and hills who live by ambushing caravans; Grimgor's Da Immortulz | lex:Dark_Lands#Features Blasted Wastes; fandom:Dark_Lands |
| Desolation of Azgorh | the exploded volcano Azgorh left a labyrinth of razor rock and toxic steam vents between the Ash Ridge Mountains and Gorgoth where no creature or plant will live; sulphur pits | lex:Dark_Lands#Features Desolation of Azgorh; fandom:Dark_Lands |
| Tower of Gorgoth | mines and furnaces in the remains of Azgorh; the largest slave camp; the text calls the surrounding earth infertile | lex:Dark_Lands#Features Tower of Gorgoth; lex:Tower_of_Gorgoth [Tamurkhan p. 167] |
| Plain of Bones | polluted desert of coloured sand and dragon skeletons; windblown factory poison; wandering greenskins ravage any life; poisoned beaches on its south | lex:Plain_of_Bones [Undead 4e, Undead Gazetteer p. 10]; fandom:Plain_of_Bones [Undead 4e p. 10; Vampire Counts 8e p. 49] |
| River Ruin | rises on Zorn Uzkul, falls into the Plain of Zharr, cools the forges of Zharr-Naggrund and leaves thick, steaming and poisonous; nothing lives in it and very little on its banks; five Mourn tributaries join it | lex:Dark_Lands#Features River Ruin; fandom:River_Ruin [Chaos Dwarfs 4e pp. 5-8; Ogre Kingdoms 8e pp. 13-15] |
| Scalded Delta | the Ruin's delta: a sulphur-stinking swamp whose water is near boiling; fog-bound poison bogs; the Swamp Eater ogre tribe lives in it | fandom:Scalded_Delta [White Dwarf 302 (UK) p. 14; Monstrous Arcanum p. 10]; lex:Dark_Lands#Features Scalded Delta; fandom:River_Ruin [Ogre Kingdoms 6e p. 54, 8e pp. 14-15] |
| Gnoblar Country | a large expanse of relatively lush green hills north of Pigbarter; a traveller calls it green and fecund next to Pigbarter's sludge; once teeming with gnoblar and hill-goblin warrens, now largely deserted after slave raids | fandom:Gnoblar_Country [White Dwarf 302 (UK) pp. 16-17]; lex:Dark_Lands#Features Gnoblar Country |
| The Sentinels | two rock pillars and a trading post in the Howling Wastes on the Ivory Road; paddocks of horses, mules and rhinoxen; provisions, furs, red meat and dried fish for sale; ruled by the Eyebiter ogres | lex:Sentinels [Ogre Kingdoms 6e pp. 54-56]; fandom:The_Sentinels [Ogre Kingdoms 6e p. 54; White Dwarf 302 pp. 16-17] |
| Pigbarter | stilt town at the Ruin's mouth; a mile-wide livestock and goods market, boars everywhere, pig-jousting; the best place to buy supplies in the region | fandom:Pigbarter [White Dwarf 302 pp. 15-16]; lex:Pigbarter [Ogre Kingdoms 6e p. 14] |
| Black Fortress | hollowed mountain ringed by cinder pits of lava; base of the Legion of Azgorh, which escorts slave caravans through the Howling Wastes | lex:Black_Fortress [Tamurkhan pp. 39-48, 167] |
| Wheatlands (of Kislev) | Kislevite colony land: the walled town of Chernozavtra on an island in the Zapadryeka river, founded for its rich black crop soil; "the richest colony in the Wheatlands" by 2300 IC; emptied by plague in 2478 IC | lex:Chernozavtra [Something Rotten in Kislev, "Death Takes a Holiday" pp. 47-48] |
| Dolgan steppe | Dolgan nomads of the Kislev steppes move by horse wagon to new pasture about weekly; goats for milk and cheese, bison and cattle for meat, gathered roots | lex:Dolgan#Life on the Steppes [Something Rotten in Kislev pp. 55-56] |
| Mountains of Mourn (west flank) | cold; rhinox herds in the valleys; ogre life revolves around the hunt; sparse pine on the lower slopes; ogre tribes are semi-nomadic and move camp often | lex:Mountains_of_Mourn; lex:Ogre_Kingdoms; lex:Ogre [Ogre Kingdoms 8e pp. 12-18]; fandom:Mountains_of_Mourn [Ogre Kingdoms 6e p. 14, 8e pp. 12-13] |

### 1.2 How the Chaos Dwarfs feed themselves and their slaves: nothing found

I looked again, harder, as asked. Result after reading both wikis' Chaos Dwarf, Zharr-Naggrund, Plain of Zharrduk,
Uzkulak, Black Fortress, Tower of Gorgoth, Daemon's Stump, Vale of Woe / Gash Kadrak, Legion of Azgorh, Hobgoblin
and River Ruin pages, and keyword-scanning the 73,000-character Fandom Chaos Dwarfs article for farm, crop, grain,
food, feed, meat, herd, livestock, fish, fungus, provision, ration, tribute:

- **No page read says the Chaos Dwarfs farm, herd, fish or import food.** The only "livestock" in the text is a
  metaphor for slaves (fandom:Chaos_Dwarfs [Tamurkhan p. 166]).
- What the text does say: they need nothing from outside but slaves ("all the resources they require" are in their
  own domain, lex:Chaos_Dwarf, unfooted paragraph); they pay for slaves in weapons and armour, to northern
  marauders, ogres and orcs (lex:Chaos_Dwarf [Tamurkhan pp. 38-48]; fandom:Chaos_Dwarfs [Tamurkhan p. 166]).
- The local wiki dump was searched again on 2026-11-20: see section 1.5.

So a food economy for Zharr-Naggrund has to be a design decision, not a canon reading (open question Q1).

### 1.3 Real-world analogues, c. 1800-1850

| analogue | what it was | source |
|---|---|---|
| Mongolia (the hobgoblin, wolf-rider and ogre herding economy; the Howling Wastes as Gobi) | About three quarters of the land is pasture; cropping was traditionally disdained by Mongols and left to Chinese farmers; growing season only 95-110 days; less than 1 percent arable by the climate section (the page's infobox figure conflicts); 100-200 mm of rain in the south, 200-350 mm in the north; the Gobi supports camels and little else | rw:Mongolia [https://en.wikipedia.org/wiki/Agriculture_in_Mongolia]; rw:Mongolia [https://en.wikipedia.org/wiki/Geography_of_Mongolia] |
| Kazakh steppe (Dolgan and hobgoblin steppe) | A nomadic state whose income was trade in horses and cattle; Russia's 1822 reforms tried to make the Kazakhs farm and failed, they stayed nomadic. Pastoralists everywhere trade meat for grain with settled farmers, or raid and take tribute | rw:Kazakh steppe [https://en.wikipedia.org/wiki/Kazakh_Khanate]; rw:pastoral nomadism [https://en.wikipedia.org/wiki/Nomadic_pastoralism] |
| Tarim Basin / Taklamakan (caravan roads across a desert: the Ivory Road, the Sentinels, Pigbarter) | Most of the basin is too dry for permanent habitation; life is in rim oases irrigated by meltwater rivers; the Silk Road ran oasis to oasis | rw:Tarim Basin [https://en.wikipedia.org/wiki/Tarim_Basin] |
| Iceland's interior highlands (ash and lava wastes: Desolation of Azgorh, Plain of Zharr) | Mostly uninhabitable volcanic-ash desert above 300-400 m; plants only at glacier edges and along streams | rw:Iceland highlands [https://en.wikipedia.org/wiki/Highlands_of_Iceland] |
| Laki 1783-84 (what an eruption and its poison do to herding) | About 80 percent of sheep and half of cattle and horses died of fluorine-poisoned grass; most crops were destroyed; about a fifth of Iceland's people died in the famine | rw:Laki [https://en.wikipedia.org/wiki/Laki] |
| Mesopotamia and Assyria (the setting's own Chaos Dwarf model) | Cities were fed from irrigated barley and date land run by temple estates, with sheep on the dry margin; the dry north farmed on rain with lower returns; Assyria moved about 4.4 million people over 250 years, mostly into its heartland, as farm and building labour, and extended canals around Nineveh. **The model needs an irrigated grain hinterland; canon gives the Chaos Dwarfs none**: their only river is poison | rw:Mesopotamia [https://en.wikipedia.org/wiki/Agriculture_in_Mesopotamia]; rw:Assyrian deportations [https://en.wikipedia.org/wiki/Resettlement_policy_of_the_Neo-Assyrian_Empire] |
| South Caspian (Hyrcanian) coast (a forested coast under a desert plateau: the canon "forested south coast") | 900-1,600 mm of rain against desert and steppe inland; much lusher than the land it borders | rw:Hyrcanian forests [https://en.wikipedia.org/wiki/Caspian_Hyrcanian_mixed_forests] |

Added 2026-11-20 for the Wheatlands and the Dolgan steppe: the Kazakh Steppe is about 804,450 km2 of dry grassland
on 200-400 mm of rain, wetter in the north, grading to semi-desert in the south, with 2-7 people per km2
(rw:Kazakh Steppe [https://en.wikipedia.org/wiki/Kazakh_Steppe]); chernozem, the black earth of that steppe belt,
carries 4-16 percent humus and is very fertile (rw:chernozem [https://en.wikipedia.org/wiki/Chernozem]). Neither
page dates the ploughing-up; vanilla's own Siberian steppe states stand in for that.

### 1.4 Vanilla's calibration states for these analogues

Read from the vanilla install on 2026-11-19 (`arable`, subsistence, class from
`mapgen/config/vanilla_state_climate_classes.csv`, crops in file order):

| vanilla state | arable | subsistence | class | crops |
|---|---|---|---|---|
| STATE_ALXA (Gobi) | 11 | pasture | open_desert | livestock, wheat |
| STATE_NEJD | 10 | pasture | open_desert | livestock |
| STATE_SAHARA | 10 | pasture | open_desert | livestock |
| STATE_SEMNAN (Dasht-e Kavir) | 20 | pasture | open_desert | wheat, livestock, tobacco, opium |
| STATE_KERMAN | 20 | pasture | open_desert | wheat, livestock, + plantations |
| STATE_TURKMENIA (Karakum) | 25 | farm | open_desert | wheat, livestock, silk, opium |
| STATE_TIANSHAN (Tarim) | 40 | pasture | open_desert | wheat, livestock, cotton |
| STATE_ULIASTAI (W Mongolia) | 30 | pasture | steppe | livestock |
| STATE_URGA (Mongolia) | 40 | pasture | steppe | livestock, wheat |
| STATE_HINGGAN | 102 | pasture | steppe | wheat, livestock |
| STATE_DZUNGARIA | 30 | pasture | steppe | wheat, livestock |
| STATE_URALSK | 35 | pasture | steppe | livestock |
| STATE_SEMIRECHE | 32 | pasture | steppe | livestock |
| STATE_AKMOLINSK | 45 | pasture | steppe | rye, livestock |
| STATE_KALMYKIA | 8 | pasture | steppe | livestock, wheat |
| STATE_KIRGHIZIA | 50 | pasture | steppe | wheat, livestock, tea |
| STATE_TOBOLSK (W Siberian forest-steppe) | 53 | farm | steppe | rye, livestock |
| STATE_TOMSK | 90 | farm | steppe | rye, livestock |
| STATE_TUVA | 15 | farm | steppe | rye, livestock |
| STATE_ALTAI | 10 | pasture | highland_alpine | livestock |
| STATE_NGARI (W Tibet plateau) | 60 | pasture | highland_alpine | livestock |
| STATE_QINGHAI | 60 | farm | highland_alpine | livestock |
| STATE_ICELAND | 5 | fishing_village | arctic_boreal_coast | rye, livestock |
| STATE_KAMCHATKA | 6 | fishing_village | arctic_boreal_coast | livestock |
| STATE_BAGHDAD | 40 | orchard | desert_river | rice, livestock, silk, tobacco |
| STATE_MOSUL (Assyria) | 30 | orchard | steppe | wheat, livestock, cotton, tobacco |
| STATE_DEIR_EZ_ZOR | 20 | pasture | desert_river | millet, livestock, tobacco |
| STATE_MAZANDARAN (Hyrcanian coast) | 70 | farm | temperate_forest_hill | rice, livestock, + plantations |
| STATE_BALUCHISTAN (Makran) | 63 | farm | open_desert | wheat, livestock, dye, opium, tea |

Reading: vanilla gives its true deserts 10-25 arable per (very large) state and pasture; its nomad steppe 30-50 and
pasture with livestock first or only; its black-earth Siberian forest-steppe 53-90 and farm with a grain first; its
cold plateau 10-60 and pasture with livestock only. World densities per 1,000 px (research doc table 4.4):
open desert 0.99, steppe 4.57, highland 5.31, boreal 2.12, temperate forest-hill 15.51.

### 1.5 Where canon and analogue disagree, and which I follow

1. **Latitude versus lore.** The climate layer puts the Plain of Zharr, the north Howling Wastes and the "Causeway
   of Zharr" at 46-54 N under a humid continental (Df) reading, which maps to `temperate_forest_hill`, the second
   richest class. Canon says the opposite in plain words (nothing grows on the plain; the wastes are a desolate
   gale-scoured flat). **Lore wins: `open_desert`.** The real-world analogue for a cold continental interior desert
   at that latitude is the Gobi/Alxa (vanilla 11, pasture), not the Russian forest belt.
2. **Mesopotamian model versus a poisoned river.** The setting borrows Assyria/Babylon for the Chaos Dwarfs, and
   Mesopotamian cities lived on an irrigated river plain. Canon removes exactly that: the Ruin is dead and its banks
   nearly so. **Lore wins: no `desert_river` anywhere on the Ruin.**
3. **Ogres on good land.** The Mourn foothills and the Ruin's east bank read as humid and green (climate layer Cfa;
   Gnoblar Country canon). Ogres do not farm; they hunt and keep rhinox. I keep the land's class (it is the land's
   capacity and several of these states are unowned) and express the ogre economy through the subsistence building
   (`pasture`) and crop order (livestock first).

### 1.5a Local-dump re-search (2026-11-20): Chaos Dwarf food, and other finds

Searched `sources/wiki/pages/` (240 articles mention the Chaos Dwarfs) for any sentence joining Chaos Dwarf / Dawi
Zharr / Zharr-Naggrund / Hashut with farm, crop, grain, food, feed, meat, cattle, herd, livestock, fungus, fish,
ration, provision, tribute, starve, eat. Three results, and only three:

1. **Slave meat.** Slave meat is described as common fare for the Chaos Dwarfs; Bull Centaurs prefer theirs alive.
   fandom:Bull_Centaur_Renders [Tamurkhan: The Throne of Chaos p. 174; Monstrous Arcanum p. 38]. This is the only
   statement found anywhere about what Chaos Dwarfs eat.
2. **Tribute.** Dark Lands hobgoblins serve the Chaos Dwarfs as slave masters, overseers and tribute collectors.
   fandom:Hobgoblin_Cutthroats [Tamurkhan p. 182]. What the tribute consists of is not said.
3. **"Livestock" = slaves** (already noted). fandom:Chaos_Dwarfs [Tamurkhan p. 166].

Still no farm, field, herd, fishery or food import. The earlier pass's negative finding stands, now with one
positive datum (cannibalised slaves) that fits a land with no agriculture rather than contradicting it.

Other dump finds used below:
- **Ogre tribes of the south-east.** The Swamp Eater, Skraggleguts, Boulderbellies, Treehammer and Death Toll ogre
  tribes are settled along the Spice Route to Ind, between the River Ruin, the Mountains of Mourn and the Haunted
  Forest, **which covers the coast opposite the Dragon Isles**. fandom:Kingdoms_of_Ind [Ogre Kingdoms 8e map p. 15];
  fandom:Treehammer_Tribe [Ogre Kingdoms 8e pp. 13, 15]; fandom:River_Ruin (Boulderbellies and Skraggleguts on the
  left bank; Swamp Eaters in the delta) [Ogre Kingdoms 6e p. 54; 8e pp. 14-15]. The Haunted Forest holds Beastmen
  (fandom:Mountains_of_Mourn [Ogre Kingdoms 8e]). This is the one corroboration of the "forested south coast"
  sentence, and it covers only the coast **east** of the Ruin.
- **Wolf Lands.** Barren open plains just east of Mad Dog Pass where whole Wolf Rider tribes encircle and harass
  intruders who do not pay. fandom:Goblin_Wolf_Riders [Orcs & Goblins 8e p. 45].
- **Road to Pigbarter.** South of the Sentinels a traveller passes the stinking sulphur pits of the Desolation of
  Azgorh, then the wild and largely deserted homelands of the Hill Goblins, before Pigbarter. fandom:Ivory_Road
  [Ogre Kingdoms 6e pp. 54-55].
- **Plain of Bones as "Plains of Plenty".** Tomb Kings 6e p. 10 gives that Nehekharan name, but the Fandom article
  notes the region was already called parched long before (Undead 4e p. 10). Ancient history; no bearing on 2502.
- **Dark Lands greenskin tribes** named on the page: Stone Snakes (Savage Orcs fighting the Chaos Dwarfs),
  Necksnappers (Black Orcs), Ironskinz. fandom:Greenskin_Tribes. Several of the mod's hub names match.
- **Chernozavtra's location is disputed.** fandom:Southern_Oblast lists it among that oblast's places [Realm of
  the Ice Queen pp. 54-55, list only]; fandom:Mother_Ostankya puts it beyond the High Pass on the Zapadreyka river
  [Son of Kislev short story; Total War: Warhammer III]; Lexicanum calls it a colony in "the Wheatlands of Kislev"
  among Dolgan tribes [Something Rotten in Kislev pp. 47-48]. The dump has no Wheatlands or Chernozavtra article.
- No dump article for: Direbogs (one mention, in River Ruin), Wolf Lands, Blasted Wastes (redirect to Dark
  Lands), Ash Ridge Mountains, Flayed Rock, Rockguts, Dark Citadel, Zapadryeka, Wheatlands.

## 2. Per-state entries

Entries are in the order of `10_dark_lands.txt`. The rows block in section 3 is the one-line-per-state list.

**How to read an entry.** `Layer` is the climate layer's zone shares from `mapgen/derived/state_climate_index.json`
and the class they map to. `Lat` is the naming anchor's latitude on the canvas. Evidence is cited by the place rows
of table 1.1 unless a new source is given. "Mod/TW name" means the name is not a Games Workshop place name on any
page read; where the worksheet cites `cr_oldworld_campaign` the name comes from the TWW3 Old World mod's region
table (ChaosRobie), which is not canon evidence. Subsistence `pasture` for greenskin and ogre land follows the
standing rulings, which the reading supports: Dark Lands goblins are wolf-riding nomads and caravan raiders, ogres
hunt and keep rhinox, and no page read shows either farming. Chaos Dwarf states take `pasture` only as the model's
desert default: canon gives no Chaos Dwarf herding either (Q1).

### STATE_WEST_DARK_LANDS — West Dark Lands
- Identity: mod name. Western interior under the Worlds Edge Mountains, lat 42.7; hubs Gribbletown, Dog Boyz Hold,
  Stone Snakes Hold, Drippin' Fangs Hold (all TWW3 Old World mod names; "Stone Snakes" matches a Savage Orc tribe of
  the Dark Lands, fandom:Greenskin_Tribes). Owner DLO. Confidence in position: fair; in a canon name: none.
- Canon: no land-use text for this place. Realm statement (barren) covers it. The uncorroborated foothill-forest
  sentence (Q3) would also touch it.
- Analogue: the Gobi margin; vanilla:STATE_ALXA arable 11, pasture, livestock + wheat.
- Layer: BWk 82 %, BSk 18 % -> open_desert.
- Proposal: `open_desert`, step 0, `pasture`, livestock. Canon and the layer agree; nothing to correct. Tier **B**.

### STATE_WOLF_LANDS — Wolf Lands
- Identity: canon place, firm. Barren ground and wind-carved rock around Crookback Mountain and Mount Grey Hag;
  "just east of Mad Dog Pass". Lat 42.3, 19,592 px, one of the realm's largest states. City hub Den of the Great
  Wolves (TW mod name); three hubs invented.
- Canon: barren land; wolf packs hunt whatever lives; only the strongest breeds survive (lex:Dark_Lands#Features Wolf
  Lands). Barren open plains held by Wolf Rider tribes who extort passage (fandom:Goblin_Wolf_Riders [Orcs & Goblins
  8e p. 45]).
- Analogue: Gobi / Alxa wolf-and-camel desert steppe; vanilla:STATE_ALXA 11 pasture; vanilla:STATE_KALMYKIA 8
  pasture, livestock + wheat.
- Layer: BWk 100 % -> open_desert.
- Proposal: `open_desert`, 0, `pasture`, livestock. Wolf-rider nomads on barren plains: the purest pasture case in
  the realm, and the lowest density class. Tier **A**.

### STATE_AGRIL_MIGDHAL — Agril Migdhal
- Identity: TWW3 Old World mod region name (worksheet source `cr_oldworld_campaign/agril_migdhal`); no page on
  either wiki. No hubs. Interior between the Wolf Lands and the Plain of Zharr, lat 45.0. Owner DLO.
- Canon: none for the place; realm statement.
- Analogue and layer: as West Dark Lands. Layer BWk 87 %, BSk 13 % -> open_desert.
- Proposal: `open_desert`, 0, `pasture`, livestock. Tier **B** (realm statement); the name itself is not canon.

### STATE_GORGOTHDRINAZ — Gorgothdrinaz
- Identity: TWW3 Old World mod name (`cr_oldworld_campaign/gorgothdrinaz`); reads as "Gorgoth road". No hubs.
  Interior north of Mount Azgorh, lat 43.1. Owner DLO.
- Canon: none for the place; realm statement. It lies on the approach to Gorgoth, which canon calls infertile.
- Layer: BWk 100 % -> open_desert.
- Proposal: `open_desert`, 0, `pasture`, livestock. Tier **B**.

### STATE_GREY_HAG_MOUNTAIN — Grey Hag Mountain
- Identity: canon place, firm: Mount Grey Hag, a goblin stronghold south-east of Crookback Mountain
  (lex:Dark_Lands#Features Mount Grey Hag [Orcs & Goblins 8e p. 14]); Night Goblins from it joined Urk Ironskull
  (fandom:Ogre_Kingdoms [Ogre Kingdoms 8e pp. 24-29]). 1,099 px, 3 of 7 provinces impassable. **Owner is GOR
  (Gorgoth, a Chaos Dwarf tag), which does not match the canon goblin hold**: flagged, not mine to change.
- Canon: the Wolf Lands text names the land around Mount Grey Hag as barren wolf country.
- Analogue: a desert massif; vanilla:STATE_ALTAI 10 pasture, livestock.
- Layer: BWk 100 % -> open_desert.
- Proposal: `open_desert`, 0, `pasture`, livestock. Tier **A** (Wolf Lands text covers it by name).

### STATE_MOUNT_AZGORH — Mount Azgorh
- Identity: canon, firm: the remains of the volcano Azgorh with the Tower of Gorgoth and its mines (city hub Tower of
  Gorgoth, mine hub Mines of Azgorh). 6 of 10 provinces impassable. Owner GOR.
- Canon: mines and furnaces worked by slaves, the largest slave camp; the tower is sunk in "the infertile earth of
  the south" (lex:Dark_Lands#Features Tower of Gorgoth); many miles of caverns and mines (lex:Tower_of_Gorgoth
  [Tamurkhan p. 167]). The Desolation's "no creatures or plants will live" applies around it.
- Analogue: an active-volcano ash field; rw:Iceland highlands (plants only by streams); vanilla has no state this
  barren except by size (STATE_MATRUH 3, the world minimum for open desert).
- Layer: BWk 100 % -> open_desert.
- Proposal: `open_desert`, step **-2**, `pasture`, livestock. Canon says infertile in so many words. Tier **A**.

### STATE_DESOLATION_OF_AZGORH — Desolation of Azgorh
- Identity: canon place, firm. 27,626 px, the realm's third largest state, lat 36.4. All four hubs invented. Owner DLO.
- Canon: razor rock and toxic steam vents where no creatures or plants will live; sulphur pits (table 1.1). The Legion
  of Azgorh "ranges across the desolation of the southern Dark Lands" (fandom:River_Ruin [Tamurkhan p. 167]).
- Analogue: rw:Laki (fluorine-poisoned pasture killed four fifths of the sheep) and rw:Iceland highlands;
  vanilla:STATE_SAHARA 10, pasture, livestock only.
- Layer: BWk 90 %, BSk 10 % -> open_desert.
- Proposal: `open_desert`, step **-2**, `pasture`, livestock. The strongest "nothing lives" statement in the realm
  after the Plain of Zharr. Tier **A**.

### STATE_WOLF_EDGE — Wolf Edge
- Identity: mod name. Strip south-west of the Wolf Lands under the Worlds Edge Mountains, lat 38.7; hubs Tusked Sunz
  Hold, Oozy Eye Hold (TW mod names), two invented. Owner DLO.
- Canon: none for the place; realm statement; edge of the Wolf Lands. Foothill-forest lead (Q3) would touch it.
- Layer: BWk 100 % -> open_desert.
- Proposal: `open_desert`, 0, `pasture`, livestock. Tier **B**.

### STATE_OLD_SILK_ROAD — Old Silk Road
- Identity: named for a canon route, not a canon region. The Old Silk Road leaves the Badlands under Black Crag,
  runs through Death Pass and on east past the ruined Fortress of Vorag (lex:Spice_Route [Arcane Journal: Dawn of
  the Storm Dragon pp. 9-10]; fandom:Old_Silk_Road). The state is the Dark Lands end of Death Pass, lat 35.5; hubs
  Pilfer Town, Moon Howlerz Hold, Broken Tooth Hold, Idol of Zak Aloog (TW mod names). Owner DLO.
- Canon: no land-use text; caravans cross it only heavily guarded. Realm statement.
- Analogue: a caravan road across desert, rw:Tarim Basin (too dry for settlement off the oases; no oasis is attested
  here); vanilla:STATE_TIANSHAN 40 pasture is the oasis-rich case and too generous.
- Layer: BWk 100 % -> open_desert.
- Proposal: `open_desert`, 0, `pasture`, livestock. Tier **B**.

### STATE_DRAGON_BARROWS — Dragon Barrows
- Identity: **open, not confirmed by Chris.** Mod/TW name. It adjoins STATE_PLAIN_OF_BONES on the west (anchors 4642
  vs 4771, same latitude band, lat 32.2); hubs Vaults of Plenty, Barrow of Malice, The Bone Gulch, Gordinar's Lair
  (TW mod names; "Plenty" echoes the Nehekharan "Plains of Plenty"). Canon puts the Plain of Bones "in the southwest"
  of the Dark Lands, east of the Worlds Edge Mountains and south of the Ash Ridge Mountains (lex:Plain_of_Bones).
  Evidence that it is the western Plain of Bones: position and dragon-grave names only. Confidence: moderate.
- Canon (if the identification holds): polluted desert, see STATE_PLAIN_OF_BONES.
- Layer: BSk 52 %, BWk 34 %, Cfa 10 %, Cfb 3 % -> mostly steppe.
- Proposal: `open_desert`, step -1, `pasture`, livestock, i.e. the same row as the Plain of Bones. If Chris rejects
  the identification, fall back to the layer (steppe). Tier **C**.

### STATE_SOUTH_DARKLANDS — South Darklands
- Identity: mod name. Small (1,664 px) at the south-west corner, lat 29.1, no port; hubs Skullsplittaz Hold, Mangy
  Marauders Hold (TW mod names), two invented. Unowned.
- Canon: nothing for the place. Two realm-level statements pull opposite ways: the south coast is thick forest
  (lex:Dark_Lands#Overview, no footnote) and the Plain of Bones' southern edge is poisoned beach (fandom:Plain_of_Bones
  [Undead 4e p. 10]). Savage Orc hunting packs roam the Dark Lands (lex:Dark_Lands [Orcs & Goblins 8e p. 14]).
- Analogue: the Makran / Baluchistan dry coast; vanilla:STATE_BALUCHISTAN 63 farm (far larger state);
  vanilla:STATE_KALMYKIA 8 pasture.
- Layer: BSh 62 %, BWh 24 %, BSk 14 % -> steppe.
- Proposal: `steppe`, 0, `pasture`, livestock then wheat (no vineyard). I keep the layer's reading because canon is
  split and neither statement names this ground. Tier **R**.

### STATE_PLAIN_OF_BONES — Plain of Bones
- Identity: canon place, firm (mine hub Graves of the Dragons; three hubs invented). 18,795 px, lat 31.3. Unowned.
- Canon: a polluted desert: toxic smoke from the Chaos Dwarf furnaces drifts over it; many-coloured sand; scorpions
  and Zombie Dragons; wandering orcs and goblins ravage any sign of life (lex:Plain_of_Bones [Undead 4e p. 10]);
  "parched"; poisoned beaches on the south (fandom:Plain_of_Bones [Undead 4e p. 10; Vampire Counts 8e p. 49]).
- Analogue: a sand desert under industrial fallout; vanilla:STATE_NEJD 10 pasture, livestock.
- Layer: BWk 69 %, BSh 14 %, BWh 9 %, BSk 8 % -> open_desert with a steppe fringe.
- Proposal: `open_desert`, step **-1** (poisoned as well as dry), `pasture`, livestock. Tier **A**.

### STATE_DRAGONS_LANDING — Dragons' Landing
- Identity: mod name. The southern tip of the Dark Lands, lat 27.8, with a port. Farm hub Anurell's Tomb is canon:
  a monolith tomb at the southern tip near the shore (lex:Dark_Lands#Features Anurell's Tomb [White Dwarf presents:
  Chaos Dwarfs p. 20]). Other hubs (Drakk Gazan, Dramalliel's Landing, Shackolot's Lair) are TW mod names. Unowned.
- Canon: the coast is wild and dangerous with no established ports; ships rarely stop (lex:Dark_Lands#Overview).
  Same split as South Darklands on forest versus poisoned shore.
- Layer: BSh 74 %, Cfa 22 %, Aw 3 % -> steppe with a humid fringe.
- Proposal: `steppe`, 0, `pasture`, livestock then wheat. Layer kept. If Chris accepts the forested-coast sentence
  (Q3) this becomes `tropical_savanna`, which changes the density by about a quarter and drops wheat. Tier **R**.

### STATE_ASH_RIDGE_MOUNTAINS — Ash Ridge Mountains
- Identity: canon name, firm: the range bounding the Desolation of Azgorh on one side and standing north of the Plain
  of Bones (lex:Dark_Lands#Features Desolation of Azgorh; lex:Plain_of_Bones); Tamurkhan's horde crossed the Dark
  Lands in its shadow (fandom:Tamurkhan). 4 of 12 provinces impassable. Hubs are TW mod names (Darkhold, ...). Unowned.
- Canon: no land-use text. It is the rim of the blast zone.
- Layer: BWk 100 % -> open_desert.
- Proposal: `open_desert`, 0, `pasture`, livestock. Not `highland_alpine`: nothing read gives it snow, meadow or
  water, and the layer does not read it as high (no ET share). Tier **B**.

### STATE_GNOBLAR_HILLS — Gnoblar Hills
- Identity: canon place, firm: Gnoblar Country, the hills north of Pigbarter (city hub Gnoblar Warrens, mine hub
  Arrowhawk Roost: canon names arrowhawks as the gnoblars' predators). Small: 941 px, lat 33.0. The port hub is
  Pigbarter, which canon puts at the Ruin's mouth; the mod has it here. Unowned.
- Canon: "a large expanse of relatively lush-green hills"; the traveller Reuben Kyte finds it pleasant, green and
  fecund after Pigbarter; once teeming with gnoblar and hill-goblin warrens, now largely deserted after Chaos Dwarf
  slave raids from the Black Fortress, arrowhawks and Pigbarter's runtspike sport (fandom:Gnoblar_Country [White
  Dwarf 302 (UK) pp. 16-17]; lex:Dark_Lands#Features Gnoblar Country; fandom:Ivory_Road [Ogre Kingdoms 6e pp.
  54-55]). Pigbarter itself: a mile-wide market of boars, pig-jousting, the best place for supplies in the region
  (fandom:Pigbarter [White Dwarf 302 pp. 15-16]).
- Analogue: green foothills beside a desert, rw:Hyrcanian forests; vanilla:STATE_MAZANDARAN 70 farm (a large,
  densely peopled rice coast: the upper bound, not the target).
- Layer: BSk 100 % -> steppe.
- Proposal: `temperate_forest_hill`, step **-1**, `farm`, livestock (the pig market) then rye. This is the one place
  in the Dark Lands canon calls green and fertile, so it leaves the steppe class; the step down is for "relatively":
  the comparison in the text is with poisoned sludge, and the hills are depopulated. Earlier draft DL-06 kept
  steppe; I differ (section 4). Tier **A**.

### STATE_DRAGONS_BREATH — Dragons' Breath
- Identity: mod/TW name; hubs Black Sands, Omdra's Lair, Maw Wyrm's Lair (TW mod names; "Omdra the Dread" has a
  Fandom page sourced to Total War). 1,798 px, lat 31.7, on the west bank of the lower Ruin between the Plain of
  Bones and Gnoblar Country. Unowned. No canon place identified: uncertain.
- Canon: nothing for the name. The west bank of the lower Ruin is the sulphur-pit edge of the Desolation of Azgorh
  (fandom:River_Ruin [Ogre Kingdoms 8e pp. 14-15]; fandom:Ivory_Road).
- Layer: BSk 88 %, BWk 12 % -> steppe.
- Proposal: `open_desert`, 0, `pasture`, livestock, on the realm statement plus the sulphur-pit bank. Tier **C**.

### STATE_TOWER_OF_THE_BLOODYTOOTH — Tower of the Bloodytooth
- Identity: canon place under a mod name (`cr_oldworld_campaign/tower_of_the_bloodytooth`): the Fortress of Vorag,
  built with slave labour by the Ghoul King Vorag Bloodytooth and abandoned at his death, east of the Plain of Bones
  (lex:Fortress_of_Vorag [White Dwarf 276 (UK) p. 68]); the Old Silk Road passes under its ruin
  (lex:Spice_Route [Dawn of the Storm Dragon p. 9]). 3,720 px, lat 30.1, with a port. No hubs; owner field empty.
- Canon: no land-use text. Ghouls, orcs and hobgoblins live in the western Dark Lands (fandom:Tamurkhan).
- Layer: Cfa 50 %, BSh 25 %, BSk 24 % -> half forest-hill, half steppe.
- Proposal: `steppe`, 0, `pasture`, livestock then wheat. It sits between the poisoned desert and the boiling delta
  with nothing said of its own soil; I take the drier half of the layer's reading and do not credit humid forest
  without a text. Tier **R**.

### STATE_ALD_GRUNGAZ — Ald Grungaz
- Identity: unknown. 278 px (the smallest state in the file), 3 of 4 provinces impassable; all hubs invented; the
  name is not on either wiki. Lat 30.8, beside the lower Ruin. Unowned.
- Canon: none.
- Layer: BSk 61 %, Cfa 24 %, BSh 15 % -> steppe.
- Proposal: `steppe`, 0, `pasture`, livestock then wheat (layer kept). At this size the row yields the floor value
  whatever the class. Tier **C**.

### STATE_BURY_BONE_HILLS — Bury Bone Hills
- Identity: TW mod name (the mine hub of the same name cites the mod's table); hubs Slavelords Hold, Blasted Heath.
  East of the Ruin against the Mountains of Mourn, lat 38.4, with a port. Unowned. No canon place identified.
- Canon: none for the place. Mourn foothills: rolling, less harsh than the peaks; gnoblars' ancestral hills
  (fandom:Mountains_of_Mourn [Ogre Kingdoms 6e p. 14]). Ogres hunt and keep rhinox.
- Analogue: Mongolian mountain-foot steppe; vanilla:STATE_ULIASTAI 30 pasture, livestock only.
- Layer: BSk 100 % -> steppe.
- Proposal: `steppe`, 0, `pasture`, livestock then wheat (layer kept). Tier **R**.

### STATE_ASHEN_PLAINS — Ashen Plains
- Identity: mod name. East bank of the Ruin, lat 40.3. The port hub Giant's Rocks is canon: the boulder ford east of
  the Sentinels where the Ivory Road crosses the Ruin and enters the Mountains of Mourn by the Valley of Horns
  (fandom:River_Ruin [Ogre Kingdoms 8e pp. 13-15]). "Ashen plains" is canon only as a phrase for the Dark Lands under
  the Mourn (fandom:Mountains_of_Mourn [Ogre Kingdoms 8e p. 12]). Other hubs TW mod or invented. Unowned.
- Canon: no land-use text; the Valley of Horns is a steep vale of petrified giant bones.
- Layer: BSk 88 %, Df 12 % -> steppe.
- Proposal: `steppe`, 0, `pasture`, livestock then wheat (layer kept). Tier **R**.

### STATE_THE_SENTINELS — The Sentinels
- Identity: canon place, firm (hubs Eyebiter Hold, North Sentinel, The Sentinels). Lat 40.8. Owner EYB (Eyebiter
  ogres, who canonically rule it: lex:Sentinels [Ogre Kingdoms 6e p. 56]).
- Canon: two rock pillars rising from ashen plains deep in the Howling Wastes; the only relative safety in the
  region; a trading post for rhinoxen, furs and provisions; paddocks of horses, mules and rhinoxen; red meat and
  dried fish hung between the stones (fandom:The_Sentinels [Ogre Kingdoms 6e p. 54; White Dwarf 302 pp. 16-17]). The
  Eyebiters tithe the traders and hunt the "dreary plains" for monsters (fandom:Spice_Route [Ogre Kingdoms 8e p. 21]).
- Analogue: a caravanserai in the Gobi; vanilla:STATE_ALXA 11 pasture.
- Layer: BSk 98 % -> steppe.
- Proposal: `open_desert`, 0, `pasture`, livestock. The land is the Howling Wastes; the stock in the paddocks is
  traded in, not raised on the spot. Tier **A**.

### STATE_DIRETOWN — Diretown
- Identity: **the earlier identification "Diretown = Direbogs" is not supported.** The state's city hub is the Black
  Fortress and its port hub the Black Causeway; lat 36.3. Canon puts the Black Fortress west of the Ruin opposite
  Flayed Rock, south of the Sentinels, at the ford (lex:Dark_Lands#Features Black Fortress; fandom:River_Ruin). The
  Direbogs are named once, as ground the Ruin crosses **further south**, after the Desolation's sulphur pits and
  the Gnoblar Country hills and just before the Scalded Delta (fandom:River_Ruin [Ogre Kingdoms 8e pp. 14-15]). On
  this map that is the latitude of STATE_GNOBLAR_HILLS / STATE_RUIN_S_END, about four degrees south of this state.
  "Diretown" is on neither wiki. Unowned.
- Canon: a hollowed mountain ringed with cinder pits of flowing lava; base of the Legion of Azgorh
  (lex:Black_Fortress [Tamurkhan pp. 39-48, 167]), which ranges over "the desolation of the southern Dark Lands".
- Layer: BSk 100 % -> steppe.
- Proposal: `open_desert`, 0, `pasture`, livestock, on the fortress text and the realm statement. Tier **B**.

### STATE_PIGBARTER_ROAD — Pigbarter Road
- Identity: mod name for the road south from the Sentinels to Pigbarter; hubs Poisoned Well and Sulphur Pits (TW
  mod names that match the canon description), two invented. Lat 37.3. Unowned.
- Canon: this leg of the journey passes "the stinking sulphur pits of the Desolation of Azgorh" before reaching the
  deserted Hill Goblin hills (fandom:Ivory_Road [Ogre Kingdoms 6e pp. 54-55]).
- Layer: BSk 58 %, BWk 42 % -> steppe / desert mix.
- Proposal: `open_desert`, step -1, `pasture`, livestock. The text describes exactly this road as sulphur-pit
  country. Tier **B**.

### STATE_PLAINS_OF_GRIEF — Plains of Grief
- Identity: mod/TW name; hubs Dronangkul, Tower of Grief, Toxic Steam Vents, Labyrinth of Razors (TW mod names). The
  last two repeat the canon description of the Desolation of Azgorh almost word for word, and the state adjoins it
  (lat 37.5). Inference: part of the Desolation. Owner DLO.
- Canon (if so): razor rock, toxic steam, nothing lives.
- Layer: BWk 94 %, BSk 6 % -> open_desert.
- Proposal: `open_desert`, step -2, `pasture`, livestock, as the Desolation. Tier **C**.

### STATE_SOUTH_HOWLING_WASTES — South Howling Wastes
- Identity: canon place, firm; the north/south split is the mod's. 14,735 px, lat 41.1. All hubs invented. Owner DLO.
- Canon: flat, desolate plain under a thin, constant, voice-carrying gale; "blasted heath"; far enough from any Chaos
  Dwarf settlement to be their rocket range; slave caravans cross it under escort (table 1.1; lex:Black_Fortress).
- Analogue: the Gobi: sparse cover that carries camels and little else, 100-200 mm of rain (rw:Mongolia);
  vanilla:STATE_ALXA 11 pasture, livestock + wheat.
- Layer: BWk 98 % -> open_desert.
- Proposal: `open_desert`, 0, `pasture`, livestock. Tier **A**.

### STATE_IVORY_ROAD — Ivory Road
- Identity: named for the canon caravan route; city hub Zahn Migdhal (TW mod name), three invented. Lat 43.0, between
  the Plain of Zharr and the Howling Wastes. Owner DLO.
- Canon: the road's leg to the Sentinels runs through the industrial wasteland of the Plain of Zharrduk and is safe
  only for a heavily guarded caravan (fandom:Ivory_Road [Ogre Kingdoms 6e pp. 54-55]). No land-use text.
- Layer: BWk 100 % -> open_desert.
- Proposal: `open_desert`, 0, `pasture`, livestock. Tier **B**.

### STATE_DAEMON_S_RUIN — Daemon's Ruin
- Identity: mod name around a canon place: the Daemon's Stump (city hub), a rock pillar and Chaos Dwarf citadel
  south-east of the Plain of Zharr on the bank of the Ruin, on the eastern fringe of the Howling Wastes
  (fandom:Daemon's_Stump [Chaos Dwarfs 4e p. 6; Daemons of Chaos 8e p. 17; Ogre Kingdoms 8e p. 23]). Lat 42.8. Unowned.
- Canon: a slaving base against the Sentinels caravans. No land-use text. The Ruin's banks carry very little life.
- Layer: BSk 83 %, Df 17 % -> steppe with a forest-hill fringe.
- Proposal: `open_desert`, 0, `pasture`, livestock (Howling Wastes fringe on a poisoned river). Tier **B**.

### STATE_FIVE_RIVERS — Five Rivers
- Identity: inferred. Canon: the Ruin takes no fewer than five tributaries from the Mountains of Mourn between the
  Plain of Zharr and the Black Fortress ford (fandom:River_Ruin [Chaos Dwarfs 4e p. 6; Ogre Kingdoms 8e pp. 14-15]),
  and those tributaries mark ogre tribal borders (lex:Ogre_Kingdoms [Ogre Kingdoms 6e p. 52]). The state is on the
  east bank at lat 47.1; city hub Red Maw Hold ("Red Maw" is in the Fandom list of ogre tribes, no article). Owner MAW.
- Canon: Mourn valleys: cold; rhinox in great herds on the valley floors; sparse pine on the lower slopes; ogre camps
  in sheltered valleys, moved often; life revolves around the hunt (table 1.1).
- Analogue: Altai and Tuva valley herding; vanilla:STATE_ALTAI 10 pasture livestock; vanilla:STATE_TUVA 15 farm,
  rye + livestock; vanilla:STATE_KIRGHIZIA 50 pasture.
- Layer: Df 100 % -> temperate_forest_hill (raw density would make this small state one of the realm's richest).
- Proposal: `highland_alpine`, 0, `pasture`, livestock then rye (no wheat, no vineyard: cold valleys). Mountain-valley
  herding country, not mixed farmland. Tier **C** (identity), on class B evidence.

### STATE_NORTH_HOWLING_WASTES — North Howling Wastes
- Identity: canon place, firm; the mod's northern half. 26,752 px, lat 45.6. All hubs invented. Owner DLO.
- Canon: as South Howling Wastes.
- Analogue: as South Howling Wastes; at this latitude the Dzungarian Gobi.
- Layer: **Df 56 %**, BSk 36 %, BWk 8 % -> more than half `temperate_forest_hill`. Unscaled that is about 280 arable
  against 26 for open desert: the layer makes a gale-scoured waste the second-richest state in the realm.
- Proposal: `open_desert`, 0, `pasture`, livestock. The largest single correction in this dossier, with Causeway of
  Zharr. Tier **A**.

### STATE_HOWLING_DISTRICT — Howling District
- Identity: mod district of the Plain of Zharr (all hubs invented; the name is on neither wiki). South-east corner of
  the plain toward the Howling Wastes, lat 50.0, with a port on the Ruin. Owner MZN.
- Canon: Plain of Zharr: nothing is able to grow (table 1.1).
- Layer: Df 100 % -> temperate_forest_hill.
- Proposal: `open_desert`, step -2, `pasture`, livestock. See STATE_HEART_OF_ZHARRDUK. Tier **B**.

### STATE_RIVER_DISTRICT — River District
- Identity: mod district of the Plain of Zharr on the Ruin below the city (all hubs invented), lat 51.4. Owner MZN.
- Canon: the Ruin leaves Zharr-Naggrund stained, steaming, thick and poisonous under a yellow cloud, its banks
  choked with drifts of pollutant (fandom:River_Ruin [Chaos Dwarfs 4e p. 5]). **A river state in name only: no
  `desert_river` or river-plain class.**
- Layer: Df 100 % -> temperate_forest_hill.
- Proposal: `open_desert`, step -2, `pasture`, livestock. Tier **B**.

### STATE_MANUFACTORY_DISTRICT — Manufactory District
- Identity: mod district of the Plain of Zharr (all hubs invented), lat 51.0. Owner MZN.
- Canon: Plain of Zharr: thousands of workshops and factories, coal heaps, tar lakes; nothing grows.
- Layer: Df 100 % -> temperate_forest_hill.
- Proposal: `open_desert`, step -2, `pasture`, livestock. Tier **B**.

### STATE_HEART_OF_ZHARRDUK — Heart of Zharrduk
- Identity: canon, firm: Zharr-Naggrund (city hub) at the centre of the Plain of Zharr / Zharrduk. Lat 52.5. Owner MZN.
- Canon: a meteor crater hundreds of square miles across, the Chaos Dwarf heartland; tar pits, burning oil, coal
  heaps, open mines, slag, ash dunes, foaming yellow and red pools; **nothing is able to grow there**; the only water
  is the Ruin, which enters cold and leaves as poison (lex:Dark_Lands#Features Plain of Zharr; fandom:Plain_of_Zharrduk
  [Chaos Dwarfs 4e; Battle Book 5e]; fandom:Chaos_Dwarfs [Tamurkhan p. 165]). Untold thousands of slaves work it.
  What they are fed is not stated; the one datum is slave meat (section 1.5a).
- Analogue: none on Earth for a city this size with no fields. Mesopotamia shows what the model would need (an
  irrigated barley plain: vanilla:STATE_BAGHDAD 40 orchard, STATE_MOSUL 30 orchard) and canon withholds it.
- Layer: Df 75 %, Dc 25 % -> temperate_forest_hill.
- Proposal: `open_desert`, step **-2**, `pasture`, livestock. The plainest canon statement in the realm. This applies
  to all ten MZN districts, which together then hold only a handful of arable levels (Q1). Tier **A**.

### STATE_FALLS_DISTRICT — Falls District
- Identity: mod district at the north edge of the plain, under the escarpment where the Ruin drops from Zorn Uzkul
  (the Falls of Doom hub itself is in STATE_ZORN_DUM). All hubs invented. Lat 53.9, port on the Ruin. Owner MZN.
- Canon: Plain of Zharr; the canal to Uzkulak starts at the foot of the falls (fandom:River_Ruin [Chaos Dwarfs 4e
  pp. 6, 8]). Here the river is still cold and clean, but nothing says the land is used.
- Layer: Dc 100 % -> boreal_forest.
- Proposal: `open_desert`, step -2, `pasture`, livestock. Tier **B**.

### STATE_ZORN_DUM — Zorn Dum
- Identity: mod name; the south-east edge of Zorn Uzkul. Hubs Falls of Doom (canon: where the Ruin leaves the
  plateau), Ivory Mounds (canon: the plateau's bone heaps form mounds of ivory, lex:Dark_Lands#Features Zorn Uzkul),
  Dum Kadrak (TW mod name). Lat 56.5, port. Owner UZK (Uzkulak, which canon places in Zorn Uzkul: lex:Uzkulak
  [Tamurkhan pp. 164-165]). STATE_ZORN_UZKUL itself is now in `00_norsca.txt`, outside this dossier.
- Canon: a vast high plateau; thin, frigid air; barren rock as far as the eye can see; dusty ground strewn with
  wind-scoured bones; mineral-rich; the sight of it turned most of the migrating Dwarfs back (table 1.1).
- Analogue: the Changtang of western Tibet; vanilla:STATE_NGARI 60 pasture, livestock only (a state ten times this
  size); vanilla:STATE_ALTAI 10 pasture.
- Layer: Dc 99 % -> boreal_forest.
- Proposal: `highland_alpine`, step **-2**, `pasture`, livestock only. The class matches the earlier draft's DL-03 for
  the plateau; the double step down is for "barren rock" in the text. The result lands close to the layer's boreal
  density, so this row changes the class label and crops more than the number. Tier **B**.

### STATE_SKULL_CLIFFS — Skull Cliffs
- Identity: inferred. Mod name; city hub Crater of the Hammer of Hashut (TW mod name; canon has the Hammer of Hashut
  rocket falling on a goblin camp near Zharr-Naggrund, lex:Chaos_Dwarf [White Dwarf presents: Chaos Dwarfs p. 13]),
  three hubs invented. Lat 54.9, between the plain's north-west rim and Zorn Uzkul: the escarpment that canon says
  separates the two (fandom:Zorn_Uzkul [Chaos Dwarfs 4e pp. 6, 8]). Owner UZK.
  Note: `mapgen/config/canon_rivers.csv` lists a "Skull River" here. The canon Skull River is in the Badlands /
  Border Princes (lex:Skull_River [Blood in the Badlands p. 11]; fandom:Battle_of_Skull_River [White Dwarf 170
  pp. 50-67]). That csv row is wrong; it is not mine to edit.
- Canon (if the identification holds): Zorn Uzkul text.
- Layer: Dc 100 % -> boreal_forest.
- Proposal: `highland_alpine`, step -2, `pasture`, livestock only, as Zorn Dum. Tier **C**.

### STATE_WHEATLANDS — Wheatlands
- Identity: **canon, and not a Total War name as the earlier draft (DL-05) recorded.** "The Wheatlands of Kislev" is
  the setting of the WFRP adventure Something Rotten in Kislev. Two of this state's hubs are that adventure's places:
  city Zapadryeka (the river) and farm Chernozavtra (the town on its island). Lat 56.9. Owner UZK, which canon does
  not support: the Wheatlands are Kislevite colony land among Dolgan nomads (Q2).
- Canon: Chernozavtra was founded in 2252 IC on a river island chosen for trade and for its rich black soil, good
  for crops (the name is glossed "Black Tomorrow"); walled by 2270 against orc, goblin and Dolgan raids; by 2300 "the
  richest colony in the Wheatlands"; destroyed in the Great War of 2302, refounded a century later, flourishing
  again; emptied by plague in the winter of 2478, since when a necromancer holds it (lex:Chernozavtra [Something
  Rotten in Kislev, "Death Takes a Holiday" pp. 47-48]). Placement is disputed between sources (section 1.5a): the
  mod follows the "beyond the High Pass" reading.
- Analogue: the black-earth forest-steppe of western Siberia and northern Kazakhstan, colonised by Russian peasants
  for grain. vanilla:STATE_TOBOLSK 53 farm, rye + livestock, class steppe; vanilla:STATE_TOMSK 90 farm, rye +
  livestock, class steppe; vanilla:STATE_AKMOLINSK 45 pasture, rye + livestock (the still-nomad steppe).
  rw:chernozem (4-16 percent humus, very fertile, found along the Kazakh steppe belt); rw:Kazakh Steppe (200-400 mm
  of rain, more in the north).
- Layer: Dc 100 % -> boreal_forest (density 2.12).
- Proposal: `steppe`, step **+1**, `farm`, **wheat first**, then livestock. Canon names the land for its wheat and
  the soil as rich and black; that is steppe black earth, not taiga. About three times the layer's value. In 2502 the
  richest town is a plague ruin, but arable is the land's capacity, not its present harvest. Tier **A**.

### STATE_SKULL_STEPPES — Skull Steppes
- Identity: inferred. Mod name; hubs Dark Citadel, Temple of Zemlya (TW mod names, Kislevite in form), Stepnaya
  Zastava (invented). Lat 56.6, immediately west of the Wheatlands. Owner UZK. By position this is the open steppe
  the Wheatlands colonies were planted in, i.e. Dolgan country; no page names it.
- Canon (if so): the Dolgan are nomads of the Kislev steppes, moving by horse wagon to new pasture about every week,
  keeping goats for milk and cheese and bison and cattle for meat, and gathering wild roots (lex:Dolgan#Life on the
  Steppes [Something Rotten in Kislev pp. 55-56]). The wider Eastern Steppes are cool grassland with sparse, dry
  forest (fandom:Eastern_Steppes).
- Analogue: the Kazakh steppe before the plough (rw:Kazakh steppe: herders who would not be made farmers);
  vanilla:STATE_AKMOLINSK 45 pasture, rye + livestock; vanilla:STATE_URALSK 35 pasture, livestock.
- Layer: Dc 100 % -> boreal_forest.
- Proposal: `steppe`, 0, `pasture`, livestock then rye. Tier **C**.

### STATE_NORTH_DARK_LANDS — North Dark Lands
- Identity: mod name. North-west interior, lat 51.8; hubs Necksnapper Hold, Ironclad Skulls Hold, Iron Fist Camp (TW
  mod names; the Necksnappers are a Dark Lands Black Orc tribe, fandom:Greenskin_Tribes). Owner DLO.
- Canon: none for the place; realm statement.
- Layer: Dc 91 %, Df 9 % -> boreal_forest.
- Proposal: `open_desert`, 0, `pasture`, livestock. The realm statement is canon and the layer's taiga is not; the
  numerical gap is small (0.99 against 2.12 per 1,000 px). Tier **B**.

### STATE_STEEL_PLAINS — Steel Plains
- Identity: mod name. Between the North Dark Lands and the Plain of Zharr, lat 53.2; hubs Ead Krumpa Hold, Ironback
  Hold, Steel Fangz Hold (TW mod names). Owner DLO.
- Canon: none for the place; realm statement; the plain's western approach.
- Layer: Dc 96 %, Df 4 % -> boreal_forest.
- Proposal: `open_desert`, 0, `pasture`, livestock. Tier **B**.

### STATE_PITS_DISTRICT — Pits District
- Identity: mod district of the Plain of Zharr (all hubs invented), lat 52.8, 2 of 8 provinces impassable. Owner MZN.
- Canon: Plain of Zharr: countless pits and mines; nothing grows.
- Layer: Dc 85 %, Df 15 %.
- Proposal: `open_desert`, step -2, `pasture`, livestock. Tier **B**.

### STATE_MARKET_DISTRICT — Market District
- Identity: mod district of the Plain of Zharr (all hubs invented), lat 53.1. Owner MZN.
- Canon: Plain of Zharr. No canon text gives Zharr a food market; its trade is weapons for slaves.
- Layer: Dc 98 %.
- Proposal: `open_desert`, step -2, `pasture`, livestock. Tier **B**.

### STATE_FOUNDRY_DISTRICT — Foundry District
- Identity: mod district of the Plain of Zharr (all hubs invented), lat 51.6. Owner MZN.
- Canon: Plain of Zharr: foundries, forges, slag.
- Layer: Df 89 %, Dc 12 % -> temperate_forest_hill.
- Proposal: `open_desert`, step -2, `pasture`, livestock. Tier **B**.

### STATE_BLASTED_DISTRICT — Blasted District
- Identity: mod district of the Plain of Zharr (all hubs invented), lat 50.9. Owner MZN.
- Canon: Plain of Zharr.
- Layer: Df 99 % -> temperate_forest_hill.
- Proposal: `open_desert`, step -2, `pasture`, livestock. Tier **B**.

### STATE_GATE_DISTRICT — Gate District
- Identity: mod district at the south of the Plain of Zharr (all hubs invented), lat 49.8. Owner MZN.
- Canon: Plain of Zharr; roads of crushed stone carry ore and plunder into the city (fandom:Chaos_Dwarfs [Tamurkhan
  p. 165]).
- Layer: Df 100 % -> temperate_forest_hill.
- Proposal: `open_desert`, step -2, `pasture`, livestock. Tier **B**.

### STATE_NAGGRUNDRINAZ — Naggrundrinaz
- Identity: TWW3 Old World mod name (`cr_oldworld_campaign/naggrundrinaz`), reads as "Naggrund road". No hubs. South
  of the plain on the way to the Howling Wastes, lat 46.7. Owner MZN.
- Canon: none for the place; realm statement. Outside the crater, so the plain's "nothing grows" is not claimed.
- Layer: Df 58 %, BSk 33 %, BWk 9 % -> mostly temperate_forest_hill.
- Proposal: `open_desert`, 0, `pasture`, livestock. Tier **B**.

### STATE_CAUSEWAY_OF_ZHARR — Causeway of Zharr
- Identity: mod name, recorded as non-canon in `planning/tag_registry.md`. All four hubs invented. The largest state
  in the file (28,573 px), lat 47.9: the whole interior between the Plain of Zharr and the Wolf Lands. Owner DLO.
- Canon: none for the place. The realm statement was written for exactly this kind of ground: ash plains, tar, lava,
  black thorns. Tamurkhan's phrasing for the country beyond the plain is monster-infested, shifting ash desert
  (fandom:Chaos_Dwarfs [Tamurkhan p. 165]).
- Analogue: the Gobi; vanilla:STATE_ALXA 11 pasture.
- Layer: **Df 55 %**, BSk 31 %, BWk 8 %, Dc 6 %. Unscaled about 288 arable against 28 as open desert: the layer makes
  this the richest state in the realm.
- Proposal: `open_desert`, 0, `pasture`, livestock. With North Howling Wastes, the correction that most changes the
  realm total. Tier **B**.

### STATE_BLACK_WASTES — Black Wastes
- Identity: inferred, fairly strong: the canon **Blasted Wastes**. City hub Da Immortulz Hold: canon makes Grimgor's
  Da Immortulz the notorious inhabitants of the Blasted Wastes (lex:Dark_Lands#Features Blasted Wastes), and Grimgor
  came out of the Blasted Wastes from the east into the northern Worlds Edge Mountains (fandom:Grimgor_Ironhide
  [Orcs & Goblins 6e pp. 66-67 / 7e p. 36]). The state is the strip under those mountains at lat 46.9. "Black Wastes"
  is on neither wiki. Other hubs TW mod names. Owner DLO.
- Canon (if so): a parched great desert that supports very little life; wind long ago destroyed what grew; sandstorm
  and burning sun; fights for caves and water holes; scattered nomadic goblins in its valleys and hills who live by
  ambush.
- Analogue: rw:Tarim Basin without its oases; vanilla:STATE_ALXA 11 pasture.
- Layer: BSk 61 %, ET 28 %, BWk 6 %, Dc 3 %, Df 2 % -> steppe with a highland share.
- Proposal: `open_desert`, 0, `pasture`, livestock. About a fifth of the layer's value. Tier **C**.

### STATE_DRAKENMOOR — Drakenmoor
- Identity: TWW3 Old World mod name (`cr_oldworld_campaign/drakenmoor`). No hubs. The canon "Drakenmoor" on Fandom is
  an Empire story location (fandom:Nightmare_of_Drakenmoor), unrelated. A mountain-foot state under the Worlds Edge
  Mountains at lat 50.3. Owner DLO. No canon place identified.
- Canon: none. The uncorroborated foothill-forest sentence (Q3) would apply here if anywhere in the west.
- Analogue: vanilla:STATE_ALTAI 10 pasture, livestock.
- Layer: ET 63 %, Dc 25 %, BSk 12 % -> highland_alpine.
- Proposal: `highland_alpine`, 0, `pasture`, livestock then rye (layer kept; no vineyard or wheat at this height and
  latitude). Tier **C**.

### STATE_RUIN_S_END — Ruin's End
- Identity: mod name for a canon place: the mouth of the River Ruin, i.e. the head of the Scalded Delta. Hubs Ruin's
  End, Tidal Flats, Bitter Grove (TW mod names), two invented. 1,401 px, lat 29.8, port. Unowned. Canon puts
  Pigbarter here (fandom:Pigbarter: "at the mouth of the River Ruin"); the mod's Pigbarter hub is in
  STATE_GNOBLAR_HILLS. The Direbogs, if they are to be placed, belong on this reach (see STATE_DIRETOWN).
- Canon: the delta swamp stinks of sulphur and its water is near boiling, from volcanism or Chaos Dwarf waste; fog
  and poison bogs (fandom:Scalded_Delta [White Dwarf 302 (UK) p. 14; Monstrous Arcanum p. 10]). The river is dead.
  **The earlier pass had this only second-hand; the page and its White Dwarf citation are now read.**
- Analogue: none close. A geothermal, acid wetland (the Danakil hot springs) rather than a farmed delta.
- Layer: Cfa 68 %, BSh 20 %, BSk 9 %, Aw 4 % -> mostly temperate_forest_hill.
- Proposal: `tropical_forest` (swamp), step **-2**, `pasture`, livestock only. Not a fishing village: canon kills the
  fish. Not `desert_river`: this delta feeds nobody. Tier **A**.

### STATE_SWAMP_EATER_HOLD — Swamp Eater Hold
- Identity: TWW3 Old World mod name for a canon tribe's land: the Swamp Eater ogres live in the Scalded Delta
  (fandom:River_Ruin [Ogre Kingdoms 6e p. 54; 8e pp. 14-15]) and are one of the tribes along the Spice Route
  (fandom:Kingdoms_of_Ind [Ogre Kingdoms 8e p. 15]). 6,000 px, lat 29.7, port, east of the Ruin's mouth. Unowned.
- Canon: Scalded Delta as above; beyond it the Haunted Forest covers the coast opposite the Dragon Isles.
- Layer: Cfa 94 % -> temperate_forest_hill; unscaled about 89 arable, the realm's third richest.
- Proposal: `tropical_forest`, step **-1**, `pasture`, livestock only. One step, not two: the state is larger than
  the delta and takes in forested coast. Still roughly a quarter of the layer's value. Tier **A** for the delta part.

### STATE_DEATHTOLL_HOLD — Deathtoll Hold
- Identity: TWW3 Old World mod name for a canon tribe: the Death Toll (Fandom also lists "Deathtoll Tribe", no
  article) are named among the ogre tribes settled along the Spice Route to Ind, between the Ruin, the Mountains of
  Mourn and the Haunted Forest (fandom:Kingdoms_of_Ind [Ogre Kingdoms 8e map p. 15]). Lat 30.9, port. Unowned.
- Canon: the Haunted Forest covers this coast and holds Beastmen (fandom:Mountains_of_Mourn). No land-use text.
- Analogue: rw:Hyrcanian forests (a wet wooded coast against dry upland); vanilla:STATE_MAZANDARAN 70 farm is that
  coast fully cleared and planted, which this is not.
- Layer: Cfa 100 % -> temperate_forest_hill.
- Proposal: `temperate_forest_hill`, step -1, `pasture`, livestock then rye. Canon and the layer agree that the land
  is wooded and wet; the step down and the pasture type carry the ogre economy and an uncleared, monster-held forest.
  Tier **B**.

### STATE_SKRAGGLEGUTS_HOLD — Skraggleguts Hold
- Identity: TWW3 Old World mod name for a canon tribe: the Skraggleguts live on the left (east) bank of the lower
  Ruin (fandom:River_Ruin [Ogre Kingdoms 8e pp. 14-15]). Lat 32.8, port, facing Gnoblar Country across the river.
- Canon: no land-use text for the tribe. The facing bank is the green Gnoblar Country.
- Layer: Cfa 74 %, BSk 26 % -> mostly temperate_forest_hill.
- Proposal: `temperate_forest_hill`, step -1, `pasture`, livestock then rye, matching STATE_GNOBLAR_HILLS across the
  river. Tier **B**.

### STATE_BOULDERBELLIES_HOLD — Boulderbellies Hold
- Identity: TWW3 Old World mod name for a canon tribe: the Boulderbellies, on the left bank of the Ruin north of the
  Skraggleguts (same sources). Lat 34.6, port. Unowned.
- Canon: as Skraggleguts; Mourn foothills.
- Layer: Cfa 100 % -> temperate_forest_hill.
- Proposal: `temperate_forest_hill`, step -1, `pasture`, livestock then rye. Tier **B**.

<!-- APPEND-4 -->

## 3. Rows

One row per state, in the order of `10_dark_lands.txt` (54 rows). Every field that contains a comma is quoted.

```csv
state_key,lore_class,fertility_step,subsistence,crops,tier,note,source
STATE_WEST_DARK_LANDS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Barren interior; layer agrees. Name is the mod's.","lex:Dark_Lands#Overview [White Dwarf presents: Chaos Dwarfs p. 20; Orcs & Goblins 8e p. 14]"
STATE_WOLF_LANDS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,"Barren wind-carved plains held by wolf-rider tribes.","lex:Dark_Lands#Features Wolf Lands [Orcs & Goblins] ; fandom:Goblin_Wolf_Riders [Orcs & Goblins 8e p. 45]"
STATE_AGRIL_MIGDHAL,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Barren interior; TW mod name; layer agrees.","lex:Dark_Lands#Overview [White Dwarf presents: Chaos Dwarfs p. 20; Orcs & Goblins 8e p. 14]"
STATE_GORGOTHDRINAZ,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Barren interior on the Gorgoth approach; TW mod name.","lex:Dark_Lands#Overview [White Dwarf presents: Chaos Dwarfs p. 20; Orcs & Goblins 8e p. 14]"
STATE_GREY_HAG_MOUNTAIN,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,"Mount Grey Hag in the Wolf Lands; owner GOR conflicts with the canon goblin hold.","lex:Dark_Lands#Features Wolf Lands and Mount Grey Hag [Orcs & Goblins 8e p. 14]"
STATE_MOUNT_AZGORH,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,A,"Tower of Gorgoth in the dead volcano; canon calls the earth infertile.","lex:Dark_Lands#Features Tower of Gorgoth [Orcs & Goblins] ; lex:Tower_of_Gorgoth [Tamurkhan p. 167]"
STATE_DESOLATION_OF_AZGORH,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,A,"Razor rock and toxic vents where no creature or plant will live.","lex:Dark_Lands#Features Desolation of Azgorh [Orcs & Goblins]"
STATE_WOLF_EDGE,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Barren edge of the Wolf Lands; mod name; layer agrees.","lex:Dark_Lands#Overview [White Dwarf presents: Chaos Dwarfs p. 20; Orcs & Goblins 8e p. 14]"
STATE_OLD_SILK_ROAD,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Dark Lands end of Death Pass; caravan road with no oasis attested.","lex:Dark_Lands#Overview [Orcs & Goblins 8e p. 14] ; lex:Spice_Route [Arcane Journal: Dawn of the Storm Dragon pp. 9-10]"
STATE_DRAGON_BARROWS,open_desert,-1,building_subsistence_pasture,building_livestock_ranch,C,"Read as the western Plain of Bones by position and names; identification not confirmed.","lex:Plain_of_Bones [Undead 4e Undead Gazetteer p. 10]"
STATE_SOUTH_DARKLANDS,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,R,"Layer kept: canon splits between forested coast and poisoned shore; no vineyard.","rw:Makran dry coast ; vanilla:STATE_KALMYKIA arable 8 pasture ; lex:Dark_Lands#Overview [Orcs & Goblins 8e p. 14]"
STATE_PLAIN_OF_BONES,open_desert,-1,building_subsistence_pasture,building_livestock_ranch,A,"Polluted sand desert; factory fallout; greenskins ravage any life.","lex:Plain_of_Bones [Undead 4e Undead Gazetteer p. 10] ; fandom:Plain_of_Bones [Undead 4e p. 10; Vampire Counts 8e p. 49]"
STATE_DRAGONS_LANDING,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,R,"Layer kept: wild coast with no ports; forest-versus-poison conflict unresolved.","lex:Dark_Lands#Overview [Orcs & Goblins 8e p. 14] ; lex:Dark_Lands#Features Anurell's Tomb [White Dwarf presents: Chaos Dwarfs p. 20] ; vanilla:STATE_KALMYKIA arable 8 pasture"
STATE_ASH_RIDGE_MOUNTAINS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Rim of the Azgorh blast zone; canon name but no land-use text.","lex:Dark_Lands#Features Desolation of Azgorh [Orcs & Goblins] ; lex:Plain_of_Bones [Undead 4e p. 10]"
STATE_GNOBLAR_HILLS,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,"Gnoblar Country: relatively lush green hills, now depopulated; Pigbarter pig market.","fandom:Gnoblar_Country [White Dwarf 302 (UK) pp. 16-17] ; lex:Dark_Lands#Features Gnoblar Country [Orcs & Goblins] ; fandom:Pigbarter [White Dwarf 302 pp. 15-16]"
STATE_DRAGONS_BREATH,open_desert,0,building_subsistence_pasture,building_livestock_ranch,C,"West bank of the lower Ruin: sulphur-pit edge of the Desolation; TW names.","fandom:River_Ruin [Ogre Kingdoms 8e pp. 14-15] ; fandom:Ivory_Road [Ogre Kingdoms 6e pp. 54-55]"
STATE_TOWER_OF_THE_BLOODYTOOTH,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,R,"Fortress of Vorag; no land-use text; drier half of the layer kept.","lex:Fortress_of_Vorag [White Dwarf 276 (UK) p. 68] ; vanilla:STATE_KALMYKIA arable 8 pasture"
STATE_ALD_GRUNGAZ,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,C,"Unidentified 278 px state; layer kept; floor value either way.","no canon land-use text found ; vanilla:STATE_KALMYKIA arable 8 pasture"
STATE_BURY_BONE_HILLS,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,R,"Mourn foothills east of the Ruin; ogre hunting and rhinox country; layer kept.","fandom:Mountains_of_Mourn [Ogre Kingdoms 6e p. 14; 8e pp. 12-13] ; vanilla:STATE_ULIASTAI arable 30 pasture"
STATE_ASHEN_PLAINS,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,R,"East bank at the Giant's Rocks ford; no land-use text; layer kept.","fandom:River_Ruin [Ogre Kingdoms 8e pp. 13-15] ; vanilla:STATE_ULIASTAI arable 30 pasture"
STATE_THE_SENTINELS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,"Trading post in the Howling Wastes; paddock stock is traded in, not raised.","lex:Sentinels [Ogre Kingdoms 6e pp. 54-56] ; fandom:The_Sentinels [Ogre Kingdoms 6e p. 54; White Dwarf 302 pp. 16-17]"
STATE_DIRETOWN,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Black Fortress among lava cinder pits; not the Direbogs, which lie further south.","lex:Black_Fortress [Tamurkhan pp. 39-48 and 167] ; fandom:River_Ruin [Ogre Kingdoms 8e pp. 14-15]"
STATE_PIGBARTER_ROAD,open_desert,-1,building_subsistence_pasture,building_livestock_ranch,B,"Road past the stinking sulphur pits of the Desolation.","fandom:Ivory_Road [Ogre Kingdoms 6e pp. 54-55]"
STATE_PLAINS_OF_GRIEF,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,C,"Hub names repeat the Desolation text; read as part of it.","lex:Dark_Lands#Features Desolation of Azgorh [Orcs & Goblins]"
STATE_SOUTH_HOWLING_WASTES,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,"Flat desolate gale-scoured plain; layer agrees.","lex:Dark_Lands#Features Howling Wastes [Orcs & Goblins] ; fandom:Howling_Wastes [White Dwarf 302 (UK) p. 17]"
STATE_IVORY_ROAD,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Caravan road through wasteland between Zharr and the Howling Wastes.","fandom:Ivory_Road [Ogre Kingdoms 6e pp. 54-55] ; lex:Dark_Lands#Overview [Orcs & Goblins 8e p. 14]"
STATE_DAEMON_S_RUIN,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Daemon's Stump on the poisoned Ruin at the edge of the Howling Wastes.","fandom:Daemon's_Stump [Chaos Dwarfs 4e p. 6; Daemons of Chaos 8e p. 17] ; lex:Dark_Lands#Features Howling Wastes [Orcs & Goblins]"
STATE_FIVE_RIVERS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_rye_farm,C,"Mourn tributary valleys: cold, rhinox herds, ogre camps; not mixed farmland.","fandom:River_Ruin [Ogre Kingdoms 8e pp. 14-15] ; lex:Mountains_of_Mourn ; lex:Ogre_Kingdoms [Ogre Kingdoms 6e p. 52] ; vanilla:STATE_ALTAI arable 10 pasture"
STATE_NORTH_HOWLING_WASTES,open_desert,0,building_subsistence_pasture,building_livestock_ranch,A,"Howling Wastes; layer reads 56 % humid continental, lore says desolate plain.","lex:Dark_Lands#Features Howling Wastes [Orcs & Goblins] ; fandom:Howling_Wastes [White Dwarf 302 (UK) p. 17]"
STATE_HOWLING_DISTRICT,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,B,"Plain of Zharr district: nothing is able to grow.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:Plain_of_Zharrduk [Chaos Dwarfs 4e; Battle Book 5e] ; fandom:Chaos_Dwarfs [Tamurkhan p. 165]"
STATE_RIVER_DISTRICT,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,B,"Plain of Zharr on the poisoned Ruin; no river-plain class.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:River_Ruin [Chaos Dwarfs 4e p. 5]"
STATE_MANUFACTORY_DISTRICT,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,B,"Plain of Zharr district: nothing is able to grow.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:Plain_of_Zharrduk [Chaos Dwarfs 4e; Battle Book 5e] ; fandom:Chaos_Dwarfs [Tamurkhan p. 165]"
STATE_HEART_OF_ZHARRDUK,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,A,"Zharr-Naggrund on the Plain of Zharr: nothing is able to grow.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:Plain_of_Zharrduk [Chaos Dwarfs 4e; Battle Book 5e] ; fandom:Chaos_Dwarfs [Tamurkhan p. 165]"
STATE_FALLS_DISTRICT,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,B,"Plain of Zharr under the Zorn Uzkul escarpment.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:River_Ruin [Chaos Dwarfs 4e pp. 6 and 8]"
STATE_ZORN_DUM,highland_alpine,-2,building_subsistence_pasture,building_livestock_ranch,B,"South-east Zorn Uzkul: barren rock plateau, thin cold air.","lex:Dark_Lands#Features Zorn Uzkul [Orcs & Goblins] ; fandom:Zorn_Uzkul [Tamurkhan pp. 164-165] ; lex:Uzkulak [Tamurkhan pp. 164-165]"
STATE_SKULL_CLIFFS,highland_alpine,-2,building_subsistence_pasture,building_livestock_ranch,C,"Read as the Zorn Uzkul escarpment; identity inferred.","lex:Dark_Lands#Features Zorn Uzkul [Orcs & Goblins] ; fandom:Zorn_Uzkul [Tamurkhan pp. 164-165; Chaos Dwarfs 4e pp. 6 and 8]"
STATE_WHEATLANDS,steppe,1,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,"Canon Wheatlands of Kislev: rich black crop soil at Chernozavtra; wheat first.","lex:Chernozavtra [Something Rotten in Kislev: Death Takes a Holiday pp. 47-48] ; vanilla:STATE_TOBOLSK arable 53 farm ; vanilla:STATE_TOMSK arable 90 farm"
STATE_SKULL_STEPPES,steppe,0,building_subsistence_pasture,building_livestock_ranch building_rye_farm,C,"Read as Dolgan nomad steppe beside the Wheatlands; identity inferred.","lex:Dolgan#Life on the Steppes [Something Rotten in Kislev pp. 55-56] ; vanilla:STATE_AKMOLINSK arable 45 pasture"
STATE_NORTH_DARK_LANDS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Barren interior; Necksnapper Black Orc country; layer reads taiga.","lex:Dark_Lands#Overview [White Dwarf presents: Chaos Dwarfs p. 20; Orcs & Goblins 8e p. 14]"
STATE_STEEL_PLAINS,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Barren western approach to the Plain of Zharr; layer reads taiga.","lex:Dark_Lands#Overview [White Dwarf presents: Chaos Dwarfs p. 20; Orcs & Goblins 8e p. 14]"
STATE_PITS_DISTRICT,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,B,"Plain of Zharr district: pits and mines; nothing grows.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:Plain_of_Zharrduk [Chaos Dwarfs 4e; Battle Book 5e] ; fandom:Chaos_Dwarfs [Tamurkhan p. 165]"
STATE_MARKET_DISTRICT,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,B,"Plain of Zharr district: nothing is able to grow.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:Plain_of_Zharrduk [Chaos Dwarfs 4e; Battle Book 5e] ; fandom:Chaos_Dwarfs [Tamurkhan p. 165]"
STATE_FOUNDRY_DISTRICT,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,B,"Plain of Zharr district: nothing is able to grow.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:Plain_of_Zharrduk [Chaos Dwarfs 4e; Battle Book 5e] ; fandom:Chaos_Dwarfs [Tamurkhan p. 165]"
STATE_BLASTED_DISTRICT,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,B,"Plain of Zharr district: nothing is able to grow.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:Plain_of_Zharrduk [Chaos Dwarfs 4e; Battle Book 5e] ; fandom:Chaos_Dwarfs [Tamurkhan p. 165]"
STATE_GATE_DISTRICT,open_desert,-2,building_subsistence_pasture,building_livestock_ranch,B,"Plain of Zharr district: nothing is able to grow.","lex:Dark_Lands#Features Plain of Zharr [Orcs & Goblins] ; fandom:Plain_of_Zharrduk [Chaos Dwarfs 4e; Battle Book 5e] ; fandom:Chaos_Dwarfs [Tamurkhan p. 165]"
STATE_NAGGRUNDRINAZ,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Barren ground south of the plain; TW mod name; layer reads forest-hill.","lex:Dark_Lands#Overview [White Dwarf presents: Chaos Dwarfs p. 20; Orcs & Goblins 8e p. 14]"
STATE_CAUSEWAY_OF_ZHARR,open_desert,0,building_subsistence_pasture,building_livestock_ranch,B,"Ash-desert interior; layer reads 55 % humid continental; non-canon name.","lex:Dark_Lands#Overview [White Dwarf presents: Chaos Dwarfs p. 20; Orcs & Goblins 8e p. 14] ; fandom:Chaos_Dwarfs [Tamurkhan p. 165]"
STATE_BLACK_WASTES,open_desert,0,building_subsistence_pasture,building_livestock_ranch,C,"Read as the canon Blasted Wastes (Da Immortulz hub): parched desert, nomad goblins.","lex:Dark_Lands#Features Blasted Wastes [Orcs & Goblins] ; fandom:Grimgor_Ironhide [Orcs & Goblins 6e pp. 66-67]"
STATE_DRAKENMOOR,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_rye_farm,C,"Unidentified mountain-foot state; layer kept; no wheat or vineyard.","no canon land-use text found ; vanilla:STATE_ALTAI arable 10 pasture"
STATE_RUIN_S_END,tropical_forest,-2,building_subsistence_pasture,building_livestock_ranch,A,"Mouth of the Ruin: sulphur swamp with near-boiling water; dead river, no fishing.","fandom:Scalded_Delta [White Dwarf 302 (UK) p. 14; Monstrous Arcanum p. 10] ; lex:Dark_Lands#Features Scalded Delta [Orcs & Goblins]"
STATE_SWAMP_EATER_HOLD,tropical_forest,-1,building_subsistence_pasture,building_livestock_ranch,A,"Swamp Eater ogres of the Scalded Delta, plus Haunted Forest coast.","fandom:Scalded_Delta [White Dwarf 302 (UK) p. 14] ; fandom:River_Ruin [Ogre Kingdoms 6e p. 54; 8e pp. 14-15] ; fandom:Kingdoms_of_Ind [Ogre Kingdoms 8e p. 15]"
STATE_DEATHTOLL_HOLD,temperate_forest_hill,-1,building_subsistence_pasture,building_livestock_ranch building_rye_farm,B,"Death Toll ogres on the Haunted Forest coast: wooded, uncleared, ogre herding.","fandom:Kingdoms_of_Ind [Ogre Kingdoms 8e p. 15] ; fandom:Mountains_of_Mourn [Ogre Kingdoms 8e]"
STATE_SKRAGGLEGUTS_HOLD,temperate_forest_hill,-1,building_subsistence_pasture,building_livestock_ranch building_rye_farm,B,"Skraggleguts on the Ruin's east bank facing Gnoblar Country.","fandom:River_Ruin [Ogre Kingdoms 8e pp. 14-15] ; fandom:Kingdoms_of_Ind [Ogre Kingdoms 8e p. 15]"
STATE_BOULDERBELLIES_HOLD,temperate_forest_hill,-1,building_subsistence_pasture,building_livestock_ranch building_rye_farm,B,"Boulderbellies on the Ruin's east bank under the Mourn foothills.","fandom:River_Ruin [Ogre Kingdoms 8e pp. 14-15] ; fandom:Kingdoms_of_Ind [Ogre Kingdoms 8e p. 15]"
```

Row check (2026-11-20, script-verified): 54 rows, each with exactly 8 fields; keys and order equal the state file;
every class, step, subsistence and crop id is legal (ids checked against `common/buildings/12_subsistence.txt`,
`02_agro.txt`, `04_plantations.txt`). Tiers: A 13, B 27, R 5, C 9. Classes: open_desert 36, steppe 8,
temperate_forest_hill 4, highland_alpine 4, tropical_forest 2.

Crop lists: class defaults are written out except where noted. Overrides: `steppe` rows drop the default vineyard
(dim light and foul air realm-wide; nothing read grows vines here) and the two northern steppe rows use rye, not
wheat, except the Wheatlands, which puts wheat first; `highland_alpine` rows drop wheat and vineyard (cold);
`tropical_forest` has no default in the brief, so livestock is given explicitly.

## 4. Disagreements

### 4.1 With the climate layer

Unscaled sums (state px x class density, before the model's world scaling; a relative measure only): the layer gives
the realm about **1,838**; these rows give about **591**, roughly a third. Largest moves:

| state | layer reads | layer (unscaled) | proposal (unscaled) | why |
|---|---|---|---|---|
| STATE_CAUSEWAY_OF_ZHARR | Df 55 % (forest-hill) | 288 | 28 | realm statement: ash, tar and thorn; an ash desert in Tamurkhan |
| STATE_NORTH_HOWLING_WASTES | Df 56 % | 280 | 27 | Howling Wastes: flat, desolate, gale-scoured (White Dwarf 302) |
| STATE_SWAMP_EATER_HOLD | Cfa 94 % | 89 | 23 | Scalded Delta: boiling sulphur swamp |
| Ten Plain of Zharr districts | Df / Dc | 308 in total | 12 in total | nothing is able to grow on the plain |
| STATE_FIVE_RIVERS | Df 100 % | 68 | 23 | cold Mourn valleys, herding not mixed farming |
| STATE_BLACK_WASTES | BSk 61 %, ET 28 % | 50 | 11 | Blasted Wastes: parched desert (identity inferred) |
| STATE_DAEMON_S_RUIN, STATE_DIRETOWN, STATE_THE_SENTINELS, STATE_PIGBARTER_ROAD | BSk (steppe) | 116 in total | 23 in total | Howling Wastes fringe, lava cinder pits, sulphur pits |
| STATE_NAGGRUNDRINAZ | Df 58 % | 34 | 3 | realm statement |
| STATE_RUIN_S_END | Cfa 68 % | 17 | 4 | the delta head |
| STATE_WHEATLANDS | Dc 100 % (boreal) | 10 | **34** | canon wheat colony on black soil: the one large move upward |
| STATE_SKULL_STEPPES | Dc 100 % | 8 | 18 | nomad steppe, not taiga |
| STATE_GNOBLAR_HILLS | BSk 100 % | 4 | 10 | the realm's one "green and fecund" place |

**What class does the evidence support for the Plain of Zharr and the Howling Wastes?** `open_desert`, without
qualification. The layer's humid-continental reading there is a physical-model result for 46-54 N; every canon text
that names those places describes ground where plants do not grow. The existing lore patch `dark_lands_desolation`
in `mapgen/config/climate_lore.json` (polygon x 4610-5000, y 1000-1480, rain x 0.55) stops at y 1000 and so does not
reach the Plain of Zharr (y 780-905), the Causeway of Zharr (anchor y 961) or most of the North Howling Wastes
(anchor y 1025): that is why those three read Df. Extending the patch north would fix the layer at source; the rows
above fix it per state either way. Changing the patch changes the accepted climate picture and is Chris's call.

Where I kept the layer: the western and southern interior it already reads as desert (West Dark Lands, Wolf Lands,
Agril Migdhal, Gorgothdrinaz, Wolf Edge, Old Silk Road, Ash Ridge, South Howling Wastes, Ivory Road), and the states
where canon is silent or split (South Darklands, Dragons' Landing, Ald Grungaz, Bury Bone Hills, Ashen Plains,
Drakenmoor, and the three east-bank ogre holds, whose humid reading canon supports).

### 4.2 With the earlier leads (`agro_climate_overrides_draft.md`, `state_climate_classes.csv`)

| lead | re-test | result |
|---|---|---|
| DL-01 interior north of 42 N -> open_desert | realm statement re-read on both wikis | **Upheld** for West Dark Lands, Agril Migdhal, Gorgothdrinaz, Ivory Road, Daemon's Ruin, North Dark Lands, Steel Plains, Naggrundrinaz, Causeway of Zharr. **Changed** for Zorn Dum and Skull Cliffs: they are Zorn Uzkul plateau edge, so `highland_alpine` step -2 (consistent with DL-03), not open desert. |
| DL-02 Plain of Zharr -> open_desert, down 1 | "nothing is able to grow" confirmed on Lexicanum and Fandom, with Tamurkhan p. 165 | **Upheld, strengthened to step -2.** The nine district names are the mod's (hubs marked invented), not found on either wiki. |
| DL-03 Zorn Uzkul -> highland_alpine | text confirmed (Tamurkhan pp. 164-165) | **Upheld**, but STATE_ZORN_UZKUL now sits in `00_norsca.txt`, outside this dossier. Applied here to its two edge states with step -2 for "barren rock". |
| DL-04 Howling Wastes and Wolf Lands -> open_desert | both confirmed; White Dwarf 302 p. 17 and Orcs & Goblins 8e p. 45 added | **Upheld.** |
| DL-05 Wheatlands "TW name, no Lexicanum page, provisional up" | Lexicanum's Chernozavtra page read | **Overturned on the facts.** The Wheatlands are GW canon (WFRP, Something Rotten in Kislev): Kislevite wheat colonies on black soil. The up-step is now sourced; class `steppe` +1, farm, wheat first. It has nothing to do with Chaos Dwarf farming. |
| DL-06 Gnoblar Country stays steppe, step 0 | primary citation found (White Dwarf 302 pp. 16-17) | **Changed** to `temperate_forest_hill` step -1: the text says lush green hills. |
| csv: Diretown = "interior (Black Fortress)" | | Upheld; and the separate guess Diretown = Direbogs is rejected (entry). |
| csv: Ruin's End open_desert | Scalded Delta page read at source | Changed to swamp (`tropical_forest`) step -2: similar number, truer class, and no fishing. |
| csv: ogre holds "no lore", steppe | Ogre Kingdoms 8e map citations found | Changed to forest-hill -1 (east bank) and swamp (delta): the tribes are canon, the Haunted Forest covers the coast. |
| csv: Five Rivers steppe, "name weak" | five Mourn tributaries are canon | Changed to `highland_alpine`. |
| csv: Black Wastes highland, Drakenmoor highland | Blasted Wastes text | Black Wastes changed to open_desert (identity inferred); Drakenmoor kept. |
| csv: Ashen Plains open_desert "name (ashen plains)", Bury Bone Hills open_desert | names are TW/mod, not evidence | Changed to the layer's steppe: they are east of the Ruin under the Mourn, where the realm statement is weakest. |
| csv: Dragon coast states "no lore", steppe | Anurell's Tomb only | Kept (steppe), with the coast conflict recorded. |
| csv: Skull Steppes "name (steppes)" | Dolgan text | Kept as steppe, now on Dolgan evidence, tier C. |
| `canon_rivers.csv`: Skull River in STATE_SKULL_CLIFFS | canon Skull River is in the Badlands / Border Princes | Wrong row; flagged, not edited. |

### 4.3 Standing rulings re-tested

- **Ogre holds herd (pasture): supported.** Rhinox are pack, herd and riding beasts; life revolves around the hunt;
  tribes move camp constantly; no page shows ogres farming (lex:Rhinox [Archives of the Empire II p. 34];
  lex:Ogre_Kingdoms; lex:Ogre [Ogre Kingdoms 8e p. 18]).
- **Greenskins herd (pasture): supported for the Dark Lands.** Wolf-rider tribes, nomadic goblins living by ambush.
- **Chaos Dwarfs: no ruling possible from canon.** `pasture` is only the desert default (Q1).
- **Gnoblar Hills is the one `farm` exception** besides the Wheatlands: warren-dwelling hill goblins and gnoblars
  and a human stilt-town with a livestock market are settled, not nomadic. Weak; Chris may prefer pasture.

## 5. Open questions for Chris

- **Q1. How does Zharr-Naggrund eat?** Canon: nothing grows on the plain; slave meat is common fare; hobgoblins
  collect unspecified tribute; arms are traded for slaves; nothing else. With these rows the ten MZN districts hold
  only a handful of arable levels between them. Options, all design calls: (a) accept it and feed the city through
  trade and the slave system; (b) give the Chaos Dwarfs a food-producing subject (Gnoblar Country, the Wheatlands,
  the east-bank valleys) rather than fields on the plain; (c) add a non-farm food building. I would not raise the
  plain's arable: it is the best-attested barren ground in the setting.
- **Q2. The Wheatlands' owner and placement.** Canon makes them Kislevite colonies among Dolgan nomads; sources
  disagree on where (Southern Oblast list; "beyond the High Pass"; Lexicanum's "Wheatlands of Kislev"). The mod draws
  them beyond the pass and gives them to UZK (Uzkulak). Should the state be Kislevite, Dolgan/unowned, or stay UZK?
  The farmland row holds either way. The richest town has been a plague ruin since 2478.
- **Q3. The forested south coast and foothills.** One unfooted Lexicanum sentence. Corroborated only east of the
  Ruin (Haunted Forest, Ogre Kingdoms 8e p. 15) and contradicted west of it by the Plain of Bones' poisoned beaches
  (Undead 4e p. 10). I applied it east of the Ruin only. Accepting it in the west would move Dragons' Landing, South
  Darklands and Tower of the Bloodytooth to `tropical_savanna`, and the Worlds Edge foothill strip (West Dark Lands,
  Wolf Edge, Black Wastes, Drakenmoor) up a class.
- **Q4. Identifications still open** (evidence in the entries):
  - Dragon Barrows = western Plain of Bones: plausible (position, names); not proven.
  - Diretown = Direbogs: **not supported**; the state is the Black Fortress country, the Direbogs lie on the lower
    Ruin near Ruin's End / Gnoblar Hills. Does Chris want the Direbogs represented at all?
  - Black Wastes = Blasted Wastes: likely (Da Immortulz hub; Grimgor came out of them into the northern Worlds Edge).
  - Plains of Grief = part of the Desolation of Azgorh: likely (hub names quote the canon text).
  - Skull Cliffs = Zorn Uzkul escarpment; Skull Steppes = Dolgan steppe; Five Rivers = the Ruin's five Mourn
    tributaries: by position.
  - Dread Rock = Dragon Isles and Haunted Grove = Haunted Forest: **not in this file any more** (STATE_DREAD_ROCK is
    in `09_southlands.txt`; no STATE_HAUNTED_GROVE block is in `10_dark_lands.txt`). Evidence gathered in passing:
    the Dragon Isles are dense jungle and swamp full of giant reptiles (lex:Dragon_Isles [Warhammer Chronicles 2004
    pp. 28-33]); the Haunted Forest covers the mainland coast opposite them and holds Beastmen (fandom:Kingdoms_of_Ind
    [Ogre Kingdoms 8e p. 15]; fandom:Mountains_of_Mourn). Their owners should rule on them.
- **Q5. Names that are not GW canon.** From the TWW3 Old World mod table (worksheet-cited): Agril Migdhal,
  Gorgothdrinaz, Naggrundrinaz, Drakenmoor, Tower of the Bloodytooth, and the four "... Hold" states (the tribes are
  canon, the hold names are not). On neither wiki and with no worksheet source: West / North / South Dark(-)lands,
  Wolf Edge, Dragon Barrows, Dragons' Landing, Dragons' Breath, Ald Grungaz, Bury Bone Hills, Ashen Plains, Diretown,
  Pigbarter Road, Plains of Grief, Daemon's Ruin, Five Rivers, Zorn Dum, Skull Cliffs, Skull Steppes, Steel Plains,
  Black Wastes, Causeway of Zharr, Ruin's End, and all ten Zharr districts.
- **Q6. Owner oddities seen in passing.** Grey Hag Mountain is owned by GOR (a Chaos Dwarf tag) though canon makes
  Mount Grey Hag a goblin hold. Tower of the Bloodytooth has an empty owner field in `state_ownership.json`.
- **Q7. Rye at 30-35 N.** The forest-hill default (livestock, rye) is kept for the three east-bank ogre holds and
  Gnoblar Hills. Rye is a poor fit for a humid subtropical coast; canon names no crop there. A model-level question
  (should Cfa map to a warm-forest crop list?), not a per-state one.
- **Q8. Step -2 on nearly a third of the realm's states.** Sixteen states carry -2. If the model clamps to a floor of 2 per state,
  most of these land on the floor regardless; Chris may prefer -1 plus the floor for simplicity.

## 6. Pages read

**Lexicanum** (browser pane, 2026-11-19, before the Cloudflare block): Dark_Lands; Chaos_Dwarf (also reached as
Chaos_Dwarfs); Zharr-Naggrund; Hobgoblin; Hobgoblin_Khanate; Eastern_Steppes; Uzkulak; Black_Fortress; Daemon's_Stump;
Tower_of_Gorgoth; Gash_Kadrak; Skull_River; Dragon_Isles; Plain_of_Bones; Pigbarter; Sentinels; Ivory_Road (also as
Silk_Road); Spice_Route; Fortress_of_Vorag; Legion_of_Azgorh; Sea_of_Dread; Mountains_of_Mourn; Ogre_Kingdoms; Ogre;
Rhinox; Gnoblar; Crookback_Mountain (lead only); High_Pass; Chernozavtra; Mount_Silverspear (via Mount_Grimfang);
Dolgan; Bolgasgrad. Not found (404 or no search hit): Plain_of_Zharr, River_Ruin, Wheatlands, Zorn Uzkul, Howling
Wastes, Wolf Lands, Scalded Delta, Gnoblar Country, Desolation of Azgorh, Blasted Wastes, Direbogs, Haunted Forest,
Flayed Rock, Falls of Doom. About 32 pages. **Not corroborated on Lexicanum because of the block:** the Fandom-only
claims of section 1.5a (slave meat, tribute collectors, the Ogre Kingdoms 8e tribe map, the Haunted Forest coast,
the Wolf Rider plains) and the Fandom citations for the Scalded Delta, Gnoblar Country and Howling Wastes (White
Dwarf 302), whose text does also appear, with a looser footnote, on the Lexicanum Dark Lands page that was read.

**Fandom, read live** (2026-11-19, before its own challenge page appeared): Dark_Lands; Scalded_Delta;
Gnoblar_Country; Howling_Wastes; Plain_of_Zharrduk; Zorn_Uzkul; River_Ruin; Chaos_Dwarfs; Plain_of_Bones;
The_Sentinels; Pigbarter; Spice_Route; Old_Silk_Road; Daemon's_Stump; Vale_of_Woe; Ogre_Kingdoms; Mountains_of_Mourn;
Rhinoxen; Gnoblar; Hobgoblins; Hobgoblin_Empire; Black_Fortress; Tower_of_Gorgoth; Uzkulak; Zharr-Naggrund;
Goblin_Wolf_Riders; Battle_of_Skull_River; Dragon_Isles; Eyebiter_Tribe.

**Fandom, local dump** `sources/wiki/pages/` (2026-11-20): a whole-dump search (240 articles naming the Chaos
Dwarfs) for food and farming terms; keyword scans of Chaos Dwarfs, Zharr-Naggrund, Chaos Dwarf Fleet, Zharralid,
Hobgoblins, Hobgoblin Cutthroats, Hobgoblin Wolf Raiders, Uzkulak, Tower of Gorgoth, Black Fortress, Legion of
Azgorh, Chaos Dwarf Warriors, Vale of Woe, Daemon's Stump; passages read in Bull Centaur Renders, Kingdoms of Ind,
Treehammer Tribe, Ogre Kingdoms, Mountains of Mourn, Greenskin Tribes, Goblin Wolf Riders, Plain of Bones, Ivory
Road, Southern Oblast, Mother Ostankya, Golgfag's Maneaters, Tamurkhan, Dolgan, Pigbarter, Old Silk Road, Eastern
Steppes, Road of Skulls, Kurgan, Grimgor Ironhide, Kislev. (Anurell Peninsula was opened and is about Lustria: not
used.)

**Web** (13 URLs): en.wikipedia.org/wiki/ Agriculture_in_Mongolia; Geography_of_Mongolia; Kazakh_Khanate; Kazakhs
(nothing usable); Nomadic_pastoralism; Kazakh_Steppe (804,450 km2 of dry steppe, 200-400 mm of rain, grass and
wormwood grading to semi-desert, 2-7 people per km2); Chernozem (black earth with 4-16 percent humus, very fertile,
found along the Eurasian steppe belt including the Kazakh steppe); Tarim_Basin; Highlands_of_Iceland; Laki;
Agriculture_in_Mesopotamia; Resettlement_policy_of_the_Neo-Assyrian_Empire; Caspian_Hyrcanian_mixed_forests.

**Repo and vanilla inputs read:** `10_dark_lands.txt`, `11_ogre_kingdoms.txt`, `states_l_english.yml`,
`hub_worksheet.json`, `land_regions_worksheet.csv`, `state_climate_index.json`, `state_ownership.json`,
`state_climate_classes.csv`, `canon_rivers.csv`, `climate_lore.json`, `agro_climate_overrides_draft.md`,
`arable_land_engine_research.md` (sections 3-6), `vanilla_state_climate_classes.csv`, vanilla `state_regions/*.txt`.

## Could not do

- Lexicanum corroboration after the 429/403 block (list above). Not retried, per the brief.
- No primary GW book was read: every book and page reference is carried from a wiki footnote. The Lexicanum Dark
  Lands page, which carries most of the per-region text, flags its own citations as needing work and cites most
  regions only to "Warhammer Armies: Orcs & Goblins" without a page.
- No quantitative 1800-1850 figure for the share of Kazakh or Mongol land under the plough was found on the pages
  read; the analogue rests on qualitative statements plus vanilla's own state values.
- Nothing was run or changed outside this file.

## Progress

- 2026-11-20: sections 1 and 1.5a written; entries 1-14 of 54 written (through STATE_ASH_RIDGE_MOUNTAINS).
- 2026-11-20: entries 15-54 written; csv block written and script-checked (54 rows x 8 fields, keys and order match
  the state file); sections 4-6 and "Could not do" written. **Dossier complete.**

