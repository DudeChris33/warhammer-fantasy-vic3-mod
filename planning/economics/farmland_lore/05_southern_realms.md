# Farmland lore dossier: 05_southern_realms (epic #3675, item #3683, Southern Realms half)

Status: COMPLETE (2026-11-20): 36 entries, 36 rows. Run dates 2026-11-19 and 2026-11-20.
State file: `map_data/state_regions/05_southern_realms.txt`, **36 states** (counted from the file; a BOM hides the
first key from a naive `grep -c`). The file holds no Border Princes state (they sit in `06_badlands.txt`, the
sibling's file); it does hold southern Bretonnia (Quenelles, Aquitaine, Brionne, Carcassonne), all of Estalia,
all of Tilea, Sartosa, and the mountain strip where the Irranas, the Vaults and the Apuccini meet.

Source notes that apply to the whole file:

- `lex:` = Lexicanum page read in this run (33 pages, 2026-11-19, before the Cloudflare block). `fandom:` = the
  Fandom Warhammer Wiki (read 2026-11-19 through its API, and 2026-11-20 from the local dump `sources/wiki/`).
  Bracketed text is the GW publication and page the wiki footnotes.
- **Lexicanum is closed for this task.** Same-origin fetches started returning HTTP 429, then 403, on
  2026-11-19; per the brief I stopped. Claims that rest on Fandom alone are marked "(Fandom only)".
- Lore claims are paraphrases. Inference is labelled as inference.
- Density arithmetic uses the brief's vanilla world-block figures (arable per 1,000 px): river plain 26.15,
  forest-hill 15.51, mediterranean 16.29, steppe 4.57, highland 5.31. "Raw arable" below = state px x density x
  step factor, before the world scaling the model applies. It is there to sanity-check against vanilla
  analogues, not as a target.

## 1. Realm picture

### 1.1 Canon

**Tilea.** A fertile peninsula round a warm, calm sea, walled by the Irranas (north), the Apuccini (east) and
the Abasko (west). The coastal plains are green, fertile and easily cultivated; the far south turns arid in high
summer; the mountain foothills carry open woodland; the Apuccini and Abasko are rugged, bare and sparsely
vegetated (fandom:Tilea#Geography [Dogs of War 5e pp. 75-76; Up in Arms pp. 50-54]). The inland states live
mostly by agriculture and are sometimes subservient to the coastal ones (lex:Tilea#Geography [WFRP 1e Rulebook
p. 279]). Tilea is renowned for its wines (lex:Tilea#Trade [Warhammer Rulebook 6e, Of Tilea and Estalia]) and
for gourmet food, wine, leather and citrus; a bad Tilean harvest can triple the price of Reikland wheat
(fandom:Tilea#Trade and Commerce [WFRP 1e Death's Dark Shadow p. 32]). Bretonnia fought for decades to annex
the northern Tilean vineyards and gave up after a joust at Ravola (lex:Tilea#History [Up in Arms pp. 57-60]).
Per city, from the Up in Arms gazetteer through Lexicanum: Miragliano has a grain-exporting village and a
vineyard town; Verezzo dominates a fertile plain with two large grain villages and a citrus village; Trantio is
a hill state with one farming, one olive and two sheep villages; Pavona has a wine village and a wool-and-wine
town; Luccini has "copious granaries", horses bred on the great southern plains, and exports grain and wool;
Remas grows its own corn and imported grain only when vermin ate the crop; Tobaro trades silver and gems for
food; Sartosa farms grapes, olives and wheat on fertile but stony volcanic soil and still imports most food.
The Blighted Marshes are a stagnant fog-bound swamp whose only crop is the black corn Skaven slaves cut from
the reed beds to feed Skavenblight (lex:Blighted_Marshes [Plague Fleet pp. 51-52; Empire 4e p. 5];
lex:Skavenblight [Skaven 4e pp. 6-7; White Dwarf 302 p. 38]).

**Estalia.** Warm and dry; harvests are adequate rather than bountiful, and the export goods are wine, olive
oil and fruit, mostly south to Araby (lex:Estalia#Trade [WFRP 1e Rulebook p. 277]; fandom:Estalia#Geography
[same page]). The northern kingdoms in the Irranas are barren hill country; the south-coast kingdoms are
prosperous traders (lex:Estalia#Geography [WFB 3e p. 201; Warhammer: The Old World Rulebook p. 55]). From its
"dry and arid northern mountain ranges, to its fertile southern coasts" (fandom:Estalia lead [The Old World RPG
Player's Guide p. 187; The Old World Rulebook pp. 54-55]). Seen from Tilea the interior is an arid plateau /
arid uplands (fandom:Tilea#Geography [Dogs of War 5e p. 75]; fandom:Tobaro [WFRP Companion p. 79]); a
"scorching" Estalian Plain is named (fandom:Estalia#Plains [Tamurkhan p. 158]). Estalian horses are famous
(lex:Estalia#Trade [The Old World Rulebook p. 54]); Bilbali makes a famous dark red wine aged in sea caves
(lex:Bilbali [Sea of Claws p. 139]; fandom:Bilbali [Realms of Sorcery p. 234]); the hills at Aguilas are clad
in olive groves (lex:Aguilas [Fell Cargo ch. 17]). Fandom adds that most Old World sheep are found in Estalia
and Bretonnia (fandom:Estalia; see section 2.0 for the footnote) and that the Abasko silver and "a rich
agricultural industry" carry the economy (fandom:Abasko Mountains [Old World Armoury p. 13]).

**Southern Bretonnia.** Peasants work strips of arable with wheat dominant, barley and vegetables beside it;
vineyards and orchards take the steep land, often with sheep grazed beneath (lex:Bretonnia [Knights of the
Grail ch. I p. 6]). Aquitaine is almost entirely arable with no hill steep enough to force pasture, and has no
major river (lex:Aquitaine [Knights of the Grail ch. VI pp. 47-49]). Brionne is mostly arable, with some
pasture in the east and south and a natural port at the Brienne mouth (fandom:Brionne [Knights of the Grail
pp. 61-62]; Fandom only, the Lexicanum page lacks the line). Quenelles is pastoral in the north and arable in
the south, and its south-west holds the unfarmed Grave of Cuileux (lex:Quenelles [Knights of the Grail];
fandom:Quenelles [Knights of the Grail pp. 88-90]). Carcassonne has narrow arable bands along its rivers and is
otherwise overwhelmingly pastoral or mountain, with armed shepherds guarding foothill flocks (lex:Carcassonne
[Knights of the Grail ch. VI pp. 64-65]).

**The mountains.** The Irranas are largely barren peaks with fortresses on the passes and poor mountain
kingdoms (lex:Irrana_Mountains [WFRP 1e Rulebook pp. 270, 277, 279]); grain is carried up to their strongholds
(fandom:Irrana Mountains [Old World Armoury p. 11]). The Vaults are very high; their hanging valleys give
excellent cattle pasture and modest harvests (fandom:The Vaults [WFRP 1e Rulebook p. 274]; Fandom only), and
mountain clans toll the passes (lex:Vaults [Warhammer Rulebook 7e p. 152]). The Apuccini are described two
ways: thickly wooded (WFRP 1e pp. 270-271) and bare with sparse vegetation (Dogs of War 5e pp. 75-76); both are
on lex:Apuccini_Mountains. They are largely uninhabited except by bandits and goblins.

### 1.2 Real-world analogues, c. 1800-1850

- **Italy for Tilea.** rw:Italy [1911 Encyclopaedia Britannica "Italy", en.wikisource.org/wiki/1911_Encyclopædia_Britannica/Italy]:
  about 71 % of the land productive, 16 % unproductive (4 % lagoon or marsh), 13 % uncultivated; wheat on about
  18 % of the land at only about 12 bushels an acre; maize 7 %; rice 0.5 %, in the Po valley, Emilia and
  Romagna; vines about 14 %; olives 3.5 %, unsheltered only in the south; pasture about 30 %; silk in Lombardy,
  Venetia and Piedmont; citrus in Sicily and the far south, almost none in the north and centre. Period caveat:
  these are 1900-1905 figures; the first national land register is 1909 (ISTAT historical series note, found
  through search, not opened), so nothing better exists for 1836.
  - Po plain = Miragliano's north. rw:Lombardy [1911 EB "Lombardy"]: three zones, mountain pasture, hill vines /
    fruit / silk, irrigated plain with maize, rice, wheat, flax; irrigation "unsurpassed in Europe"; cotton
    growing "insignificant in Italy".
  - Tuscany = Trantio / Pavona. rw:Tuscany [1911 EB "Tuscany"]: wheat, maize, wine (Chianti), olive oil,
    chestnuts; sheep, mules, cattle; the Arno valley is the fertile part; the Maremma (about 850 sq mi) is
    malarial pasture for horses and half-wild cattle, drained from Leopold II onward.
  - Pontine Marshes / Maremma = Blighted Marshes. rw:Pontine Marshes [en.wikipedia.org/wiki/Pontine_Marshes]:
    about 80,000 ha; forested swamp and mud flats; herding only; fewer than 1,000 people on 700 km2 about 1900;
    every drainage scheme from 1298 to 1914 failed.
  - Apulia / Naples / Sicily = Luccini's plain. rw:Tavoliere [en.wikipedia.org/wiki/Tavoliere_delle_Puglie]:
    3,000 km2, Italy's second plain, kept as winter sheep pasture for transhumant flocks, with winter floods and
    summer drought; wheat, olives and vines now. rw:Sicily [1911 EB "Sicily"]: once the granary of Italy;
    latifondi of 500 ha and more rotating wheat, barley and beans; rainfall 19.5 to 29 in; forest hardly 3 %;
    citrus and vines the high-value crops; about 700,000 sheep and goats; cotton tried only during the American
    Civil War and dropped; tunny and coral fisheries.
- **Spain for Estalia.** rw:Spain [1911 EB "Spain", en.wikisource.org/wiki/1911_Encyclopædia_Britannica/Spain]:
  about 80 % of the land classed productive, of which a third is tilled; forest under 6 %; wheat and barley on
  the flat parts of the Castiles, Leon and the Guadalquivir basin, nearly all dry-farmed; Madrid gets 15 in of
  rain, Bilbao 46, Santiago 66, Murcia 14; olives over the southern half of the tableland with olive "forests"
  from Andujar to Cordoba; oranges, lemons and figs on the Andalusian plains and Mediterranean coast; irrigated
  huertas (Valencia, Murcia) yield about twelve times dry land; esparto steppe in Murcia and La Mancha; the wet
  north (Galicia, Asturias, Basque provinces) grows maize without irrigation, cider apples and dairy cattle.
  rw:Mesta [en.wikipedia.org/wiki/Mesta]: transhumant merino flocks peaked near 5 million in 1790-1795, 2.75
  million in 1818, 1.1 million in 1832; summer pasture in Leon, Old Castile and the sierras, winter pasture in
  Extremadura and Andalusia; pastures were barred from the plough until the late 18th century; dissolved 1836.
- **South-west France for southern Bretonnia.** rw:France [search summary of the 1840 Statistique de la France;
  not opened]: about 27 % of French arable still lay fallow in the 1830s. Vanilla's own states are the
  calibration here (below). For Carcassonne's foothill flocks the analogue is Pyrenean and Alpine transhumance
  (rw:Alps [en.wikipedia.org/wiki/Transhumance_in_the_Alps]: valley floor grain and hay, summer herds on the
  alps; alpine pasture is 35 % of Swiss farmland).

### 1.3 Vanilla calibration (read from the install on 2026-11-19)

| analogue for | vanilla state | arable | subsistence | class (#3676 csv) | crops |
|---|---|---|---|---|---|
| Miragliano plain | STATE_LOMBARDY | 110 | farm | temperate_river_plain | wheat, livestock, cotton, silk, vineyard |
| | STATE_PIEDMONT | 90 | rice_farm | temperate_river_plain | rice, livestock, cotton, vineyard |
| | STATE_VENETIA | 70 | farm | temperate_river_plain | wheat, livestock, silk, vineyard |
| | STATE_EMILIA | 60 | farm | temperate_river_plain | wheat, livestock, cotton, silk, vineyard |
| Trantio, Pavona | STATE_TUSCANY | 60 | farm | mediterranean | wheat, livestock, cotton, silk, vineyard |
| | STATE_UMBRIA | 20 | farm | mediterranean | wheat, livestock, cotton, vineyard |
| Remas, Verezzo | STATE_LAZIO | 60 | farm | mediterranean | wheat, livestock, cotton, silk, vineyard |
| | STATE_CAMPANIA | 90 | farm | mediterranean | wheat, livestock, cotton, silk, sugar, vineyard |
| Luccini | STATE_APULIA | 60 | farm | mediterranean | wheat, livestock, cotton, sugar, vineyard |
| | STATE_SICILY | 60 | farm | mediterranean | wheat, livestock, cotton, silk, sugar, vineyard |
| Monte Castello | STATE_CALABRIA | 30 | farm | mediterranean | wheat, livestock, cotton, sugar, vineyard |
| Sartosa, isles | STATE_SARDINIA | 15 | farm | mediterranean | wheat, livestock, cotton, vineyard |
| | STATE_CORSICA | 10 | pasture | mediterranean | livestock, vineyard |
| | STATE_MALTA | 5 | orchard | mediterranean | wheat, livestock, cotton, sugar |
| | STATE_IONIAN_ISLANDS | 10 | orchard | mediterranean | wheat, livestock, cotton, tobacco, vineyard |
| Tobaro | STATE_DALMATIA | 20 | farm | mediterranean | wheat, livestock, vineyard |
| Estalian plateau | STATE_OLD_CASTILE | 69 (22 prov) | farm | mediterranean | wheat, livestock, cotton, tobacco, vineyard |
| | STATE_NEW_CASTILE | 51 (18 prov) | farm | mediterranean | wheat, livestock, cotton, sugar, vineyard |
| | STATE_LEON | 41 | farm | mediterranean | wheat, livestock, vineyard |
| | STATE_ARAGON | 34 | farm | mediterranean | wheat, livestock, vineyard |
| | STATE_EXTREMADURA | 34 | farm | mediterranean | wheat, livestock, vineyard, tobacco |
| Magritta coast | STATE_LOWER_ANDALUSIA | 67 | farm | mediterranean | wheat, silk, livestock, cotton, tobacco, sugar, vineyard |
| | STATE_UPPER_ANDALUSIA | 53 | farm | mediterranean | wheat, livestock, cotton, silk, tobacco, sugar, vineyard |
| | STATE_VALENCIA | 56 | farm | mediterranean | rice, livestock, cotton, silk, tobacco, vineyard |
| | STATE_MURCIA | 24 | farm | mediterranean | wheat, silk, livestock, vineyard |
| West coast | STATE_BEIRA | 65 | farm | mediterranean | wheat, livestock, cotton, tobacco, banana, vineyard |
| | STATE_ALENTEJO | 25 | farm | mediterranean | wheat, livestock, banana, vineyard |
| Bilbali coast | STATE_BASQUE_COUNTRY | 42 | farm | temperate_forest_hill | maize, livestock, vineyard |
| | STATE_ASTURIAS | 21 | farm | temperate_forest_hill | maize, livestock |
| | STATE_GALICIA | 51 | farm | temperate_forest_hill | maize, livestock, vineyard |
| South Bretonnia | STATE_AQUITAINE | 90 | farm | temperate_forest_hill | wheat, livestock, vineyard |
| | STATE_GUYENNE | 90 | farm | temperate_forest_hill | wheat, livestock, vineyard |
| | STATE_LANGUEDOC | 120 | farm | mediterranean | wheat, livestock, cotton, vineyard |
| | STATE_AUVERGNE_LIMOUSIN | 110 | farm | temperate_forest_hill | wheat, livestock, vineyard |
| | STATE_RHONE | 110 | farm | temperate_river_plain | wheat, livestock, cotton, silk, vineyard |
| Vaults, Irranas | STATE_EAST_SWITZERLAND | 40 | farm | highland_alpine | rye, livestock, vineyard |
| | STATE_SAVOY | 20 | farm | highland_alpine | wheat, livestock, cotton, vineyard |
| | STATE_TYROL | 30 | farm | highland_alpine | wheat, livestock, vineyard |

Readings: every vanilla Italian, Iberian and south-French state carries `building_vineyard` (only Asturias and
Malta lack it). Vanilla gives peninsular Italy 6 to 15 arable per province against the mediterranean class
average of 3.6, so Italy sits well above "typical mediterranean"; the Castilian meseta sits at about 3, i.e.
at or below typical.

### 1.4 Where canon and analogue disagree, and which I follow

- **Carcassonne.** The real Carcassonne (Aude, Languedoc) is vine country. Canon makes the dukedom pastoral
  mountain marches. Canon wins: pasture, no vineyard lead.
- **Silk and cotton in Tilea.** Vanilla gives Lombardy, Tuscany, Lazio and Sicily silk and cotton. Canon has
  Tilean merchants cross the world to find the *source* of silk and open the Silk Road to Cathay (lex:Tilea#History
  [Dogs of War 5e pp. 94-95]), so silk is an import (inference from that text); no canon cotton, tobacco, sugar
  or dye was found for Tilea or Estalia in any page read, and the 1911 EB calls Italian cotton insignificant.
  I drop the plantation crops everywhere except a cotton tail on the three Magritta coast states (Andalusia
  analogue, canon silent, tier R for that one crop; see open questions).
- **Rice.** Piedmont is a rice-subsistence state in vanilla. No canon rice in Tilea. Not used.
- **The climate layer's steppe reading of lowland Tilea.** Rejected for every lowland state: canon says green,
  fertile, easily cultivated coastal plains with summer drought only in the far south, which is the
  mediterranean class, not steppe (details in section 4).

## 2. Per-state entries

Entries are in file order.

### 2.0 Notes that apply to several entries

- **Identity method.** State keys and display names come from the state file and `states_l_english.yml`; the
  places inside each state come from `hub_worksheet.json` (anchors inside the state). Most hub names are
  Total War names (the ChaosRobie Old World mod table), which are leads, not canon. I matched them to canon
  through the Fandom settlement lists, which cite the Man O' War: Corsair campaign map and the Warhammer: The
  Old World website map (fandom:Estalia#Cities and Settlements), and through the wiki page of each place.
  Lexicanum notes that the minor Estalian kingdom names (Avila, Cantonia, Novareno, Obregon) began as fan
  material by a freelance writer and were put on, then removed from, the official web map in February 2025
  (lex:Estalia#Notes/Trivia). Treat those four names as soft canon.
- **Owner tags** are from `state_ownership.json` and `planning/tag_registry.md`.
- **"Pastoral" is not "low arable".** In the engine arable land is the shared level budget of farms and
  ranches alike (`arable_land_engine_research.md` 2.1). A canon statement that land is pastoral therefore sets
  the subsistence building (pasture) and puts `building_livestock_ranch` first; the fertility step moves only
  where canon also says the land is poor, mountainous, unfarmed or imports its food.
- **Sheep.** Most Old World sheep are in Estalia and Bretonnia (fandom:Livestock [Old World Armoury p. 83];
  Fandom only). This is the canon basis for a ranch entry in every Estalian and Bretonnian row.
- **Crop order.** First id = the product canon names first for that place; where canon is silent, wheat first.
- **Very small mountain states** come out below the engine floor on raw density (Dark Maiden Pass 0.8,
  Chateau Lovarre 1.2, Eastern Irranas 2.6). The model's floor of 2 will apply; the rows are not adjusted
  for it.

### STATE_QUENELLES — Quenelles

- **Identity.** The eastern heart of the Dukedom of Quenelles: the city of Quenelles on the Brienne at the
  edge of Athel Loren (hub, canon) with the Total War hubs Perrache, Montlac and Viefin north of it. Owner QUE.
  High confidence. The Massif Orcal is a separate state in the sibling's file.
- **Canon.** Northern Quenelles is pastoral, the south arable; the city stands on the Brienne near Loren
  (lex:Quenelles [Knights of the Grail; Bretonnia 5e p. 7]; fandom:Quenelles [Knights of the Grail pp. 88-90]).
  The Brienne is over 100 yards wide at the city (fandom:River Brienne; no footnote on that page). The ducal
  court of 2276 IC drew knights with tournaments and fine wine (lex:Quenelles, timeline). Realm: wheat strips,
  vineyards and orchards on steep ground (lex:Bretonnia [Knights of the Grail ch. I p. 6]).
- **Analogue.** Burgundy / Lyonnais: vanilla:STATE_BURGUNDY arable 80, farm, wheat livestock vineyard;
  vanilla:STATE_RHONE 110; vanilla:STATE_AUVERGNE_LIMOUSIN 110 (forest-hill).
- **Climate layer.** Df 50 %, Cfb 47 %, Dc 3 %: temperate_forest_hill. Agrees.
- **Proposal.** temperate_forest_hill, step 0, farm; wheat, livestock, vineyard. The state takes in both the
  arable south round the city and part of the pastoral north, so the two halves cancel and the step stays 0.
  The crop list replaces the forest-hill default (ranch, rye): canon names wheat as the Bretonnian staple.
  Raw arable 77. **Tier A.**

### STATE_GRAVE_OF_CUILEUX — Grave of Cuileux

- **Identity.** South-western Quenelles, the old land of Cuileux (hubs Chinon, Laguiller, Gien, Brusse: Total
  War names). Owner QUE. 21 provinces, the largest state in the file. High confidence on the region; the
  state is larger than the unfarmed tract it is named for (inference from its size).
- **Canon.** The south-west of Quenelles was Cuileux; a large area there, the Grave of Cuileux, is not farmed,
  because the ghosts of the Cuilen knights kill anyone who ploughs it (lex:Quenelles [Knights of the Grail];
  fandom:Cuileux [Knights of the Grail pp. 89-91]). Southern Quenelles as a whole is arable (same pages).
- **Analogue.** Same as Quenelles; a parallel for a taboo waste inside good farmland is the Landes moor inside
  vanilla:STATE_AQUITAINE (90).
- **Climate layer.** Cfb 100 %: temperate_forest_hill. Agrees on class.
- **Proposal.** temperate_forest_hill, step -1, farm; wheat, livestock, vineyard. The earlier draft (BRE-05)
  took two steps down. I take one: the canon text makes the Grave "a large area" of the south-west, not all of
  it, and the same source calls the south of the dukedom arable. Raw arable 56. **Tier A.** Open question 1.

### STATE_AQUITAINE — Aquitaine

- **Identity.** The Dukedom of Aquitaine (hub city Aquitaine, canon; Derrevin Libre, a canon village in
  eastern Aquitaine [Knights of the Grail p. 50]; Chateau d'Epee, canon). Owner AQU. High confidence.
- **Canon.** Consists almost entirely of arable land; a few hills, none steep enough to force pasture; the
  gentlest coast in Bretonnia with fishing and smuggling villages; no major river inland and no large town
  (lex:Aquitaine [Knights of the Grail ch. VI pp. 47-49]). Before the crusades it was larger but could not keep
  enough people to farm all its land (lex:Aquitaine [Circle of Blood p. 3]).
- **Analogue.** The Garonne and Charente lowlands: vanilla:STATE_AQUITAINE 90, vanilla:STATE_GUYENNE 90,
  vanilla:STATE_POITOU 90 (all forest-hill class, farm, wheat livestock vineyard).
- **Climate layer.** Cfb 100 %: temperate_forest_hill. Disagrees on density, not on climate.
- **Proposal.** temperate_river_plain, step 0, farm; wheat, livestock, vineyard. Canon gives the top arable
  share of any Bretonnian dukedom, which is the river-plain density (26 per 1,000 px against 15.5). The class is
  used for that density; canon explicitly names no major river, so this is "open arable lowland", not
  alluvium. The alternative with the same effect is temperate_forest_hill +1 (23 per 1,000 px). Raw arable 71.
  **Tier A.** Open question 2.

### STATE_BRIONNE — Brionne

- **Identity.** The Dukedom of Brionne: the port city at the Brienne mouth (canon) with Muret and Castle
  Gransette (Total War names). Owner BRI. High confidence.
- **Canon.** Most of Brionne is arable, with some pastoral land in the east and south; a major natural port at
  the mouth of the River Brienne (fandom:Brionne [Knights of the Grail pp. 61-62]; Fandom only: the Lexicanum
  page read on 2026-11-19 has the port but not the land-use sentence). `canon_rivers.csv` already carries the
  Brienne for this state.
- **Analogue.** Lower Garonne / Gironde: vanilla:STATE_GUYENNE 90, vanilla:STATE_AQUITAINE 90.
- **Climate layer.** Cfb 91 %, Cfa 9 %: temperate_forest_hill.
- **Proposal.** temperate_river_plain, step 0, farm; wheat, livestock, vineyard. Mostly arable land on the
  lower course of a 600-mile river is the river-plain class as #3676 defines it. Raw arable 75. **Tier A**
  (not corroborated on Lexicanum).

### STATE_CANTABRIO_ROAD — Cantabrio Road

- **Identity.** The north coast of Estalia round the city of Bilbali, with the ports Barboza and Alquezaro,
  both placed in the realm of Bilbali by the Man O' War: Corsair map and the Old World web map
  (fandom:Estalia#Cities and Settlements). Owner BIL. High confidence. The state name itself has no wiki page.
- **Canon.** Bilbali is the second city of Estalia and controls the north (lex:Bilbali [WFRP 1e Rulebook
  p. 278]); it produces a famous wine (lex:Bilbali [Sea of Claws p. 139]), a dark red aged ten years in vats in
  caves along the Great Ocean (fandom:Bilbali [Realms of Sorcery p. 234]), listed as "Bilbali Vino Tinto" among
  the best wines (fandom:Wine [WFRP 4e Taverns of the Empire p. 16]). Bilbali is the "rugged" kingdom
  (fandom:Bilbali [The Old World RPG Player's Guide p. 187]). No text on grain or stock for this coast.
- **Analogue.** The Cantabrian coast and the Rioja behind Bilbao. rw:Spain [1911 EB Spain]: Bilbao 46 in of
  rain; maize without irrigation, cider apples and dairy cattle in the Atlantic provinces.
  vanilla:STATE_BASQUE_COUNTRY 42, farm, maize livestock vineyard; vanilla:STATE_ASTURIAS 21.
- **Climate layer.** Cfa 75 %, Cfb 25 %: temperate_forest_hill. I follow it.
- **Proposal.** temperate_forest_hill, step 0, farm; vineyard, livestock, wheat. The realm statement "warm
  and dry" would give mediterranean (the earlier lead); the layer and the Cantabrian analogue both say humid,
  and the two classes are within 5 % in density, so the choice only affects the default crop list, which I
  override anyway. Vineyard leads on the Bilbali wine text. Raw arable 52. **Tier A** for the wine; class on
  the layer.

### STATE_CEFIRO_HILLS — Cefiro Hills

- **Identity.** The north-west corner of Estalia: the Cefiro Hills, the port Diamanterra and the inland town
  Sahagun, all placed in the realm of Obregon by the two maps (lex:Obregon; fandom:Estalia#Cities and
  Settlements). Owner CNT, the mod's "Cantonia" (its tag registry row says the placement is non-canon; canon
  Cantonia is in the south-east). Medium-high confidence.
- **Canon.** No canon land-use text found for the hills or for Obregon. Realm level only: warm dry Estalia
  exporting wine, oil and fruit (lex:Estalia#Trade [WFRP 1e Rulebook p. 277]); sheep (2.0).
- **Analogue.** Galicia and northern Portugal: vanilla:STATE_GALICIA 51, farm, maize livestock vineyard;
  vanilla:STATE_ENTRE_DOURO_E_MINHO 60, forest-hill.
- **Climate layer.** Cfa 66 %, Cfb 34 %: temperate_forest_hill. I follow it.
- **Proposal.** temperate_forest_hill, step 0, farm; livestock, wheat, vineyard. Hill country on a humid
  ocean coast, by analogue. Raw arable 70. **Tier B** (realm-level canon; class from layer and analogue).

### STATE_NUJA — Nuja

- **Identity.** The south-west corner of Estalia. Hub city Nuja: Fandom has it as Nerja, "known also as
  Nuja", a port in the realm of Avila (fandom:Estalia#Cities and Settlements [Man O' War: Corsair map; Old
  World web map]; the fandom:Nerja page has no land-use text). Hub Tor Karyndis is a Total War name. Split
  ownership: CNT (13 provinces), MGL the wood-elf "Miramar Glade" (3), MAG (1). Medium confidence.
- **Canon.** No canon land-use text found for this coast. Realm level: fertile southern coasts
  (fandom:Estalia lead [The Old World RPG Player's Guide p. 187]); wine, olive oil and fruit shipped to Araby
  (lex:Estalia#Trade [WFRP 1e Rulebook p. 277]). The Miramar Hills are in Avila (fandom:Miramar Hills [Old
  World web map]), with no description.
- **Analogue.** Algarve, Alentejo and Huelva: vanilla:STATE_ALENTEJO 25, farm, wheat livestock vineyard;
  vanilla:STATE_LOWER_ANDALUSIA 67.
- **Climate layer.** Cfa 92 %, Cfb 6 %, Cs 1 %: temperate_forest_hill. I depart from it.
- **Proposal.** mediterranean, step 0, farm; vineyard, wheat, livestock. An olive-oil, wine and fruit export
  coast is the mediterranean class by definition; the layer's humid-subtropical reading has almost the same
  density, so the swap changes the crop defaults, not the size. Raw arable 71. **Tier B.**

### STATE_ESTALIAN_HIGHLANDS — Estalian Highlands

- **Identity.** A small landlocked block (7 provinces, 2 impassable) on the south flank of the western
  Irranas: Reas ("a settlement on the Irrana Mountains", Obregon), Siernos (inland town, Magritta) and
  Llaqueno (near the Irranas, Avila), all from the two maps (fandom:Estalia#Cities and Settlements). Owner MAG.
  Medium confidence.
- **Canon.** The northern kingdoms of the Irranas are barren lands of hill-fighters with fortresses on the
  passes (lex:Estalia#Geography [WFB 3e p. 201]); the poorer mountain kingdoms envy the ports
  (lex:Irrana_Mountains); grain reaching the Irrana strongholds is imported and poor (fandom:Irrana Mountains
  [Old World Armoury p. 11]; Fandom only).
- **Analogue.** The Cantabrian range and the Sistema Central: summer pasture of the Mesta flocks (rw:Mesta).
  vanilla:STATE_SAVOY 20, vanilla:STATE_TYROL 30 (highland, farm).
- **Climate layer.** Cfb 100 %: temperate_forest_hill. I depart from it.
- **Proposal.** highland_alpine, step 0, pasture; livestock, wheat. Barren hill kingdoms that buy their grain
  are a pasture economy by canon; pasture makes the state a grain importer by construction, which matches the
  text. This goes against vanilla's habit of giving mountain states farms, on canon. Raw arable 7.
  **Tier B** (realm and range text; no text on these places).

### STATE_CENTRAL_MAGRITTA — Central Magritta

- **Identity.** The city and kingdom of Magritta on the Bay of Quietude at the mouth of the Tagos
  (lex:Magritta), with Javea, Molena and Almyria (maps; fandom:Estalia#Cities and Settlements). Owner MAG.
  High confidence.
- **Canon.** Magritta is the largest city of Estalia and the leading port of the Southern Sea (lex:Magritta
  [WFRP 1e Rulebook p. 278; Marienburg: Sold Down the River p. 25]). Land-use text is realm level only: the
  south-coast kingdoms are prosperous (lex:Estalia#Geography [WFB 3e p. 201]); "fertile southern coasts"
  (fandom:Estalia lead [The Old World RPG Player's Guide p. 187]); harvests adequate rather than bountiful,
  with wine, oil and fruit sold to Araby (fandom:Estalia#Geography [WFRP 1e Rulebook p. 277]).
- **Analogue.** Lower Andalusia / Valencia. rw:Spain [1911 EB Spain]: wheat on the Guadalquivir basin, olive
  forests, oranges, lemons and figs on the Andalusian plain. vanilla:STATE_LOWER_ANDALUSIA 67, farm, wheat silk
  livestock cotton tobacco sugar vineyard; vanilla:STATE_VALENCIA 56.
- **Climate layer.** Cfa 49 %, Cfb 31 %, Cs 20 %: temperate_forest_hill. I depart from it (same reason as Nuja).
- **Proposal.** mediterranean, step 0, farm; vineyard, wheat, livestock, cotton. The two canon statements pull
  opposite ways (fertile coast; harvests merely adequate), so no step. Cotton is kept as the class default's
  tail on the Andalusian analogue only (open question 6). Raw arable 62. **Tier B.**

### STATE_WEST_MAGRITTA — West Magritta

- **Identity.** The south coast and hinterland west of Magritta: Cebreros (inland, Magritta), the ports Ubrique
  and Torrosa (Magritta) and Belmoz (a port in the south of Avila), per the two maps
  (fandom:Estalia#Cities and Settlements). Owner MAG. Medium-high confidence.
- **Canon.** No canon land-use text found for these places. The River Guadariz flows through Magritta's realm
  near Avila (lex:Avila [Man O' War: Corsair map]). Realm level as for Central Magritta.
- **Analogue.** Lower Andalusia / Huelva: vanilla:STATE_LOWER_ANDALUSIA 67.
- **Climate layer.** Cfa 74 %, Cfb 16 %, Cs 11 %: temperate_forest_hill. I depart from it (as Nuja).
- **Proposal.** mediterranean, step 0, farm; vineyard, wheat, livestock, cotton. Raw arable 67. **Tier B.**

### STATE_SOUTHEAST_MAGRITTA — Southeast Magritta

- **Identity.** The south-east coast: the ports Almagora, Sitges and Aguilas, all in the realm of Cantonia on
  the two maps (fandom:Estalia#Cities and Settlements; fandom:Cantonia). Owner MAG. High confidence.
- **Canon.** Aguilas is the southernmost port on Estalia's eastern side, a shipbuilding centre, with the Del
  Campo hills clad in olive groves (lex:Aguilas [Fell Cargo ch. 17]; fandom:Aguilas, same footnote). A Black
  Library novel, so second-rank canon, but it is the only place-level farm text on the Estalian coast.
- **Analogue.** Murcia, Almeria, Valencia: the driest corner of Spain (Murcia 14 in of rain), esparto steppe
  inland, irrigated huertas on the coast (rw:Spain [1911 EB Spain]). vanilla:STATE_MURCIA 24,
  vanilla:STATE_VALENCIA 56.
- **Climate layer.** Cs 100 %: mediterranean. Agrees.
- **Proposal.** mediterranean, step 0, farm; vineyard, wheat, livestock, cotton. Vineyard stands in for the
  olive groves (there is no olive building). Raw arable 35. **Tier A** (through the hub Aguilas).

### STATE_EAST_MAGRITTA — East Magritta

- **Identity.** The landlocked east of the peninsula under the Abasko Mountains: Zaragoz (a duchy in
  Cantonia), Guakazar (Fandom: Gualeazar / Gualcazar, inland, Cantonia), Solsona (inland, Cantonia) and Raganos
  (a fortress on the Abasko, Cantonia), per fandom:Estalia#Cities and Settlements. Owner MAG. 17 provinces, 2
  impassable. High confidence.
- **Canon.** Zaragoz stands on a lonely crag ringed by pastureland; farms lie on higher ground to the north
  with orange groves and vineyards, and stock is driven down to the River Eboro to drink; the approach is dry,
  sandy ground with thorn and tall grass (fandom:Zaragoz#Geography [Zaragoz, novel by Brian Craig]; the page
  gives chapter footnotes for the novel but none on this paragraph). Seen from Tobaro the land west of the
  Abasko is "arid uplands" (fandom:Tobaro [WFRP Companion p. 79]); an Estalian king built the Valley of
  Windmills high in the Abasko to feed his people and abandoned it (lex:Abasko_Mountains [WFRP Companion
  p. 6]); a famine in the southern Estalian kingdoms drove Larhgoz to war (fandom:Larhgoz [Monstrous Arcanum
  pp. 7-8]). Sombra Wood, one of Estalia's two main forests, is in Cantonia south of the eastern Irranas
  (fandom:Sombra Wood [Old World web map]).
- **Analogue.** Aragon and La Mancha: dry-farmed wheat with long fallows, sheep, vines; Madrid 15 in of rain
  (rw:Spain [1911 EB Spain]). vanilla:STATE_ARAGON 34 (11 provinces), vanilla:STATE_NEW_CASTILE 51 (18).
- **Climate layer.** Cs 40 %, Cfb 37 %, Cfa 13 %, BSk 6 %, Df 4 %: mediterranean. Agrees on class.
- **Proposal.** mediterranean, step -1, farm; livestock, vineyard, wheat. Pasture round the town, groves and
  vines on the better ground, thorn scrub between, and recurrent famine: below typical. Vanilla's own meseta
  states sit at about 3 arable per province, at the bottom of the mediterranean class. Raw arable 44.
  **Tier A** (through the hub Zaragoz; novel-rank canon).

### STATE_WESTERN_IRRANAS — Western Irranas

- **Identity.** The Estalian side of the Irrana Mountains: Durango and Mount Zardele, "a settlement in the
  Irrana Mountains" in Novareno, and Montenas (Fandom: Montenas, inland, Magritta), per
  fandom:Estalia#Cities and Settlements. Owner MAG. 12 provinces, 3 impassable. High confidence.
- **Canon.** The Irranas are largely barren peaks, uninhabited but for a fierce hill people who hold pass
  fortresses, and bandits and goblins; the poorer mountain kingdoms envy Bilbali and Magritta
  (lex:Irrana_Mountains [WFRP 1e Rulebook pp. 270, 277, 279]). Grain is brought in (fandom:Irrana Mountains
  [Old World Armoury p. 11]).
- **Analogue.** Pyrenees and Cantabrian mountains: vanilla has no Pyrenean state; vanilla:STATE_SAVOY 20,
  vanilla:STATE_TYROL 30.
- **Climate layer.** BSk 60 %, Cfb 33 %, Df 7 %: steppe. Density is close to highland (4.6 against 5.3).
- **Proposal.** highland_alpine, step 0, pasture; livestock, wheat. "Largely barren" is what the highland
  class already means, so no step. Pasture for the same reason as the Estalian Highlands. Raw arable 12.
  **Tier A.**

### STATE_EAST_BILBALI — East Bilbali

- **Identity.** The north-east coast between Bilbali and the Bretonnian border: Vizeaya (a great port) and
  Graus (port), both in Novareno, and Guaniar, "not far from the Irrana Mountains", Novareno
  (fandom:Estalia#Cities and Settlements). Novareno is divided from Brionne by the River Niveau (lex:Novareno
  [Old World web map]). Owner BIL. Medium-high confidence.
- **Canon.** No canon land-use text found. Realm level only.
- **Analogue.** Navarre and the French Basque coast: vanilla:STATE_BASQUE_COUNTRY 42.
- **Climate layer.** Cfa 76 %, Cfb 17 %, BSk 7 %: temperate_forest_hill. I follow it.
- **Proposal.** temperate_forest_hill, step 0, farm; livestock, wheat, vineyard. Same reasoning as Cantabrio
  Road, without the wine text. Raw arable 50. **Tier B.**

### STATE_BLIGHTED_MARSHES — Blighted Marshes

- **Identity.** The Blighted Marshes at the head of the Tilean Sea, with Skavenblight. Owner SRY (Clan
  Skryre). High confidence.
- **Canon.** A great morass between Tilea and Estalia, from the northern shore of the Tilean Sea to the foot of
  the Irranas: stagnant black water, permanent fog, death to cross (lex:Blighted_Marshes [Plague Fleet
  pp. 51-52]; fandom:Blighted Marshes [Skaven 4e p. 5; WFRP 2e Rulebook p. 226]). The channel banks are lined
  with black corn (lex:Blighted_Marshes [Empire 4e p. 5]). Flotillas of Skaven slaves scour the reed beds for
  the crop, which is hauled to great mills that grind grain for "the starving masses" of Skavenblight
  (lex:Skavenblight [Skaven 4e pp. 6-7; White Dwarf 302 p. 38]; fandom:Skavenblight [Skaven 7e p. 10]). Black
  corn grows only in this marsh soil; it is the Skaven staple "out of necessity rather than choice"
  (fandom:Black Corn [Skaven 7e pp. 16-17]). Food shortage runs through Skavenblight's history
  (fandom:Skavenblight [Children of the Horned Rat pp. 28-29]). Human Tileans get nothing from the marsh.
- **Analogue.** The Pontine Marshes before reclamation: 80,000 ha with fewer than 1,000 people, herding only,
  malaria (rw:Pontine Marshes). No vanilla state is a marsh; the nearest are vanilla:STATE_LAZIO 60 (which
  contains the Pontine) and vanilla:STATE_ROMAGNA 40.
- **Climate layer.** BSk 58 %, Cs 21 %, Cfa 19 %, Cfb 2 %: steppe. Wrong for a swamp, though its low density
  (4.6) lands near my figure by accident.
- **Proposal.** mediterranean, step -2, farm; wheat only. There is no swamp class; I take the class of the
  surrounding Tilean lowland and the full two steps down. One crop: black corn is a milled grain, so
  `building_wheat_farm`; no vineyard, no ranch (nothing in the text grazes there). The marsh is cropped, by
  slaves, and still cannot feed its city: a small arable figure with a farm subsistence building is the
  honest reading. Raw arable 19. **Tier A.** Open question 3 (rice as the building for black corn).

### STATE_EASTERN_IRRANAS — Eastern Irranas

- **Identity.** The eastern Irranas where they run into the Vaults, north of the marshes (hub Stormwrath Peak
  is a Total War name; the other hubs are invented). Split: SRY 5 provinces, VMP (Kemmler's Host) 4; 4 of the 9
  provinces are impassable. Medium confidence.
- **Canon.** Range text as for the Western Irranas. The Irranas, being part of the Vaults, are much colder and
  more treacherous than the other ranges round Tilea (fandom:Tilea#Geography [Dogs of War 5e p. 76]). Kemmler
  built the fortress of Krinal in the Vaults in 2460 IC and raided northern Tilea and Carcassonne from it
  (lex:Tilea#History [White Dwarf 309 p. 61]).
- **Analogue.** High Pyrenees / western Alps: vanilla:STATE_SAVOY 20.
- **Climate layer.** BSk 100 %: steppe.
- **Proposal.** highland_alpine, step -1, pasture; livestock. Barren and the coldest part of the range, with
  nearly half the state impassable. Raw arable 3 (floor applies). **Tier A** for the range text.

### STATE_NORTH_TILEA — North Tilea

- **Identity.** The Principality of Miragliano: the city, Ebino, Ravola (canon town under Miragliano) and the
  land up to the mountain foot. Owner MIR. 18 provinces. High confidence.
- **Canon.** The city stands on islands and canals; its landward side is marsh, and swamps of reeds and
  shallow lakes stretch for leagues. Beyond them lie hills and gentle meadows, huge fields of grain and
  vegetables, orchards, vineyards and wide pastures for cows and sheep: the city's food source, guarded by the
  prince's forts (fandom:Miragliano#Surrounding Lands [Brunner the Bounty Hunter, "Beneath the Vaults"];
  Fandom only, novel-rank). Etobrutti is a grain-exporting village and Ravola a town famed for its vineyards
  (lex:Miragliano [Up in Arms pp. 52-53]); Ravola's are called the finest in Tilea (fandom:Ravola [Dogs of War
  5e p. 77; Up in Arms pp. 52-53]) and its sparkling wine is listed among the best (fandom:Wine [WFRP 4e
  Taverns of the Empire p. 16]). Bretonnian barons fought from 1382 to 1420 IC for those vineyards in the
  Irrana foothills (fandom:Ravola [Up in Arms pp. 57-58]). The Novalone Pass leads "onto the plains of
  Miragliano" (fandom:Irrana Mountains [WFRP 1e Rulebook p. 270]). The River Tarano runs from the Vaults to the
  Gulf of Pearls and divides Miragliano from Trantio (fandom:Tilea#Rivers [Dogs of War 5e p. 86 map]). Toward
  the north-east the soil turns cracked and stony, poor for crops but good for olives, sheep, goats and the
  grape of the sparkling wine (fandom:Campogrotta [WFRP 1e Death's Dark Shadow pp. 7-11]).
- **Analogue.** The Po plain with Venice's lagoon. rw:Lombardy [1911 EB]: irrigated plain of maize, rice, wheat
  and flax where crop failure is "hardly possible"; vines and silk on the lower slopes; pasture above.
  vanilla:STATE_LOMBARDY 110, vanilla:STATE_VENETIA 70, vanilla:STATE_EMILIA 60 (all temperate_river_plain).
- **Climate layer.** BSk 37 %, Cfa 21 %, Cs 17 %, Df 17 %, Cfb 9 %: steppe by plurality, though 47 % of the
  state reads humid temperate. I depart from it.
- **Proposal.** temperate_river_plain, step 0, farm; wheat, vineyard, livestock. Marsh, canals, a plain under
  a great range with named rivers crossing it, and big grain fields behind the swamp belt: this is the Po
  plain's class, the one class the climate layer can never produce by itself. The marsh belt and the stony
  north-east hold the step at 0. Mediterranean +1 would give nearly the same size (107 against 115). Raw
  arable 115, one Lombardy. **Tier A.** Open question 4.

### STATE_WEST_CARCASSONNE — West Carcassonne

- **Identity.** The ducal heart of Carcassonne: Castle Carcassonne, on an island in the River Songez, the
  westernmost Brienne tributary wholly inside the dukedom (fandom:Castle Carcassonne), with Embrun (Total War
  name) and Dragon Falls (canon [Knights of the Grail p. 66]). Owner CAR. 9 provinces, 1 impassable. High
  confidence.
- **Canon.** Three great tributaries of the Brienne cut the dukedom into four; there are narrow bands of
  arable along parts of the major rivers, and the overwhelming majority of the land is pastoral or mountain.
  Flocks graze the mountain foothills under armed "shepherds", and the castle town lives off the shepherd
  companies (lex:Carcassonne [Knights of the Grail ch. VI pp. 64-65]; fandom:Castle Carcassonne). Goblins and
  bandits raid in from the Irranas (lex:Irrana_Mountains).
- **Analogue.** The Pyrenean piedmont (Bearn, Bigorre, Ariege): valley-floor grain with transhumant flocks on
  the slopes (rw:Alps for the system). No matching vanilla state; vanilla:STATE_AUVERGNE_LIMOUSIN 110 is the
  nearest upland-pastoral French state and vanilla:STATE_WALES (forest-hill, farm) the nearest sheep country.
- **Climate layer.** Df 60 %, Cfb 31 %, Cfa 7 %, BSk 2 %: temperate_forest_hill. Agrees on class.
- **Proposal.** temperate_forest_hill, step -1, pasture; livestock, wheat. Pasture and ranch-first follow the
  "pastoral" text; the step down is for the mountain share, which canon counts as a large part of the dukedom.
  No vineyard: the real Aude is wine country, the canon dukedom is not. Raw arable 24. **Tier A.**

### STATE_NOVALONE_PASS — Novalone Pass

- **Identity.** The Novalone (Nuvolone) Pass, which carries most trade between Tilea and Bretonnia down onto
  the plains of Miragliano (fandom:Irrana Mountains [WFRP 1e Rulebook p. 270]), with the dwarf places round
  it: Kazad Frukund, the fort on the pass (fandom:Kazad Frukund [Dwarfs: Stone and Steel p. 112]), Karak
  Eksfilaz, Karak Kaferkammaz and Karak Bhufdar in the Vaults. Owner BRN (a goblin tribe) in the mod; in canon
  these are living dwarf holds. 6 provinces, 2 impassable. High confidence.
- **Canon.** Kazad Frukund produces grain for Karak Eksfilaz, as does the outpost Grung Mizpal; Karak Eksfilaz
  stands on a heavily forested aspen peak (fandom:Karak Eksfilaz [WFRP 4e Lords of Stone and Steel pp. 18,
  23]). Under Karak Kaferkammaz the human town of Mont Glace lives by pastoral farming, cheese and wool, sold
  to the dwarfs for the right to work the land (fandom:Karak Kaferkammaz [Dwarfs: Stone and Steel p. 112;
  Lords of Stone and Steel p. 23]). Karak Bhufdar sits in a valley of fir and oak and trades timber
  (fandom:Karak Bhufdar; no footnote). The Vaults' hanging valleys give excellent cattle pasture and
  nutritious if modest harvests (fandom:The Vaults [WFRP 1e Rulebook p. 274]).
- **Analogue.** Switzerland: valley grain and hay, summer herds on the alps, alpine pasture 35 % of farmland
  (rw:Alps). vanilla:STATE_EAST_SWITZERLAND 40, farm, rye livestock vineyard; vanilla:STATE_TYROL 30.
- **Climate layer.** Dc 56 %, BSk 34 %, Df 11 %: boreal_forest (2.1 per 1,000 px).
- **Proposal.** highland_alpine, step 0, pasture; livestock, rye. Typical alpine land by canon: cheese-and-wool
  towns and grain forts in the valleys. Pasture follows the standing ruling (the holds here are not among the
  named grain holds, and the mod's owner is a goblin tribe); the grain forts are why a grain farm stays on the
  list, and rye is the cold-valley grain of the Swiss analogue. Raw arable 5. **Tier A.** Open question 7.

### STATE_APUCCINI_MOUNTAINS — Apuccini Mountains

- **Identity.** The northern and central Apuccini: Karak Grom and its grain fort Kazad Sedazund, "the
  southernmost Dwarfen outpost in the Apuccini" (fandom:Karak Grom [Lords of Stone and Steel p. 24]); the
  other hubs are Total War names. Split: BRN 7 provinces, SAA 1; 3 of 8 impassable. High confidence.
- **Canon.** Two descriptions: thickly wooded peaks with heavily forested foothills, largely uninhabited but
  for bandits and goblins (WFRP 1e Rulebook pp. 270-271, 279); rugged and bare with sparse vegetation, but not
  as cold or snowbound as the ranges to the north (Dogs of War 5e pp. 75-76). Both are on
  lex:Apuccini_Mountains; fandom:Tilea#Geography carries the second. Marble is quarried for Trantio. Karak
  Grom is fed by Kazad Sedazund's grain and by the human town of Domatburg, which supplies grain, cheese and
  wool (fandom:Karak Grom [Lords of Stone and Steel p. 24]). A popular song is about an Apuccini goat herd
  (fandom:Apuccini Mountains [Drachenfels, prologue]).
- **Analogue.** The Apennines (the wiki's own trivia note says so): chestnut and beech woods, transhumant
  sheep to the Tavoliere (rw:Tavoliere). vanilla:STATE_ABRUZZO 25, farm; vanilla:STATE_UMBRIA 20.
- **Climate layer.** BSk 59 %, Dc 27 %, Df 14 %: steppe.
- **Proposal.** highland_alpine, step 0, pasture; livestock, wheat. The earlier draft's open question (wooded
  or bare) does not need settling: grain forts and a cheese-and-wool town on one side, "largely uninhabited"
  on the other, average to typical highland. Raw arable 5. **Tier A.**

### STATE_DARK_MAIDEN_PASS — Dark Maiden Pass

- **Identity.** The Dark Maiden (Stretto) Pass, the road across the Apuccini from Tilea to the Border Princes
  (fandom:Apuccini Mountains#Dark Maiden Pass [Renegade Crowns p. 6; Man O' War: Corsair]). All four hubs are
  invented and stacked. Owner SAA (Clan Skaar). 2 provinces, 1 impassable; 230 px. Identity confirmed; the
  pass itself has no descriptive text.
- **Canon.** No canon land-use text found for the pass. Range text as for the Apuccini Mountains.
- **Analogue.** An Apennine pass: no vanilla state of this size; vanilla:STATE_ABRUZZO 25 for the range.
- **Climate layer.** BSk 100 %: steppe.
- **Proposal.** highland_alpine, step 0, pasture; livestock. Same as its range, less the grain forts, which are
  further north. Raw arable 1 (floor applies). **Tier B** (range-level canon; nothing on the pass).

### STATE_VEREZZI — Verezzi

- **Identity.** The Republic of Verezzo: the city, the port Portomaggiore and Terrene (Total War names).
  Owner VER. 8 provinces, 1 impassable. High confidence.
- **Canon.** Verezzo lies inland and dominates "the fertile plain" from the only rising ground for miles
  (lex:Verezzo#Location; fandom:Verezzo [Dogs of War 5e p. 82]). Its villages: Ciabbatta and Riccotta, large
  grain-farming villages, and Veddia, a large citrus-farming village (lex:Verezzo [Up in Arms p. 54];
  Lexicanum only, the Fandom pages for these villages carry no farm text). The city became a republic when its
  prince hoarded grain in the famines of 2321-2399 IC (fandom:Verezzo; lex:Remas).
- **Analogue.** The Campanian and Latin plains: vanilla:STATE_CAMPANIA 90 (6 provinces),
  vanilla:STATE_LAZIO 60 (4): the densest farmland in vanilla's mediterranean class.
- **Climate layer.** BSk 56 %, Cs 41 %, BSh 2 %: steppe. I depart from it.
- **Proposal.** mediterranean, step +1, farm; wheat, vineyard, livestock. A canon "fertile plain" with two
  large grain villages is not steppe; it is the best kind of mediterranean land, as its Italian analogue is in
  vanilla. Vineyard stands in for the citrus groves. Raw arable 41. **Tier A.**

### STATE_REMAS — Remas

- **Identity.** The Republic of Remas: the city on its headland and lagoon, with Rifraffa and Stiani (Total
  War names). Owner REM. 6 provinces. High confidence.
- **Canon.** Remas became a republic in the long famines, when rats and mice ate the corn in the fields and
  the grain in the stores and grain had to be shipped from Bretonnia and the Empire (lex:Remas; fandom:Remas
  [Dogs of War 5e p. 81]): its normal state is to grow its own. A headland 100 miles long seals off a lagoon
  fed by many small rivers, and the Remans are called the world's greatest fishermen, salting much of the
  catch for export (fandom:Remas, "The City"; the paragraph carries no GW footnote, the page's footnotes
  around it are Tome of Salvation and Town Cryer 14). Coastal Tilea is green, fertile and easily cultivated
  (fandom:Tilea#Geography [Dogs of War 5e p. 76]).
- **Analogue.** Lazio and the Bay of Naples: vanilla:STATE_LAZIO 60, vanilla:STATE_CAMPANIA 90.
- **Climate layer.** Cs 95 %, BSk 5 %: mediterranean. Agrees on class.
- **Proposal.** mediterranean, step +1, farm; wheat, vineyard, livestock. The step is carried over from the
  earlier draft (SRB-05) and re-tested: the evidence is the self-feeding grain hinterland plus the realm
  statement on the coastal plains. It is thinner than Luccini's or Verezzo's; step 0 is defensible (open
  question 5). I kept farm rather than fishing village: the fishery is real in canon, but the city's bread is
  its own corn, and fishing wharves are a capped resource, outside this row. Raw arable 51. **Tier A.**

### STATE_TRANTINE_HILLS — Trantine Hills

- **Identity.** The Principality of Trantio: the city, the Trantine Hills, the port Viadaza, Urbimo, Ducieso
  ("a quiet town in the Trantine Hills", fandom:Trantine Hills) and Campogrotta at the foot of the Vaults.
  Owner TRA. 16 provinces. High confidence.
- **Canon.** Trantio is inland, in a hilly area, long a backwater (lex:Trantio). Its villages: Terramorta
  (farming), Torrico (a large olive-farming village), Varenna (a large sheep-farming village) and Viccia
  (sheep) (lex:Trantio [Up in Arms p. 54]; Lexicanum only). The Trantine Hills are rich in fruit orchards and
  olive groves (fandom:Trantine Hills [Inferno! 21, "Portrait of my Undying Lady"]; fandom:Tilea#Plains [Dogs
  of War 5e p. 86 map]), with abandoned merchant villas since greenskin raids from the Apuccini grew
  (fandom:Trantine Hills). Alcatani is a poor hamlet rich in apples, citrus, vines and olives
  (fandom:Alcatani [Dogs of War 5e pp. 6-7]). The north-east round Campogrotta has cracked, stony soil, bad
  for crops, good for olives, sheep, goats and vines (fandom:Campogrotta [Death's Dark Shadow pp. 7-11]).
  Marble comes down from the Apuccini.
- **Analogue.** Tuscany: wheat, wine and oil grown together on sharecropped hill farms, sheep, the Arno
  valley the fertile part (rw:Tuscany [1911 EB]). vanilla:STATE_TUSCANY 60, vanilla:STATE_UMBRIA 20.
- **Climate layer.** Cs 64 %, BSk 36 %: mediterranean. Agrees.
- **Proposal.** mediterranean, step 0, farm; vineyard, livestock, wheat. Tree crops and sheep lead, grain
  third: exactly the village list. Step 0: rich hills, stony north-east, abandoned villas. An orchard
  subsistence building would also fit the text (open question 8). Raw arable 67. **Tier A.**

### STATE_PLAINS_OF_LUCCINI — Plains of Luccini

- **Identity.** The Principality of Luccini on its plain: the city, Mintopua, Aldente, Capelli (Total War
  names). The Plain of Luccini runs from the city to the River Luparno (fandom:Tilea#Plains [Dogs of War 5e
  p. 86 map]). Owner LUC. 13 provinces. High confidence.
- **Canon.** Southern Tilea round Luccini is fertile and famous for fine horses and "copious granaries"
  (lex:Luccini [WFRP 1e Rulebook pp. 279-280]; fandom:Luccini, same footnote; fandom:Horses). The horses are
  bred on the great southern plains (lex:Luccini). The hot plain is rich in endless vineyards, olive groves
  and shepherds with their flocks (fandom:Luccini [Dogs of War 5e pp. 24-25]). The city exports grain, luxury
  goods and wool (lex:Luccini [Up in Arms p. 52]). The far south can be quite arid in high summer
  (fandom:Tilea#Geography [Dogs of War 5e p. 76]).
- **Analogue.** Apulia's Tavoliere and the Neapolitan and Sicilian wheat lands: 3,000 km2 of plain with winter
  sheep and summer drought; latifundia rotating wheat, barley and beans (rw:Tavoliere; rw:Sicily [1911 EB]).
  vanilla:STATE_APULIA 60 (7 provinces), vanilla:STATE_SICILY 60, vanilla:STATE_CAMPANIA 90.
- **Climate layer.** BSh 96 %, BSk 3 %, Cs 1 %: steppe (hot semi-arid). I depart from it; this is the largest
  single disagreement in the file (15 raw arable against 79).
- **Proposal.** mediterranean, step +1, farm; wheat, livestock, vineyard. Every canon line names this plain as
  Tilea's granary and stud; summer aridity is the dry-summer definition of the mediterranean class, not a
  steppe. Wheat first (granaries, grain exports), ranch second (horses, wool), vineyard third. Raw arable 79.
  **Tier A.**

### STATE_MONTE_CASTELLO — Monte Castello

- **Identity.** The south-east tip of the peninsula: the fortress of Monte Castello (canon), hub city Donalba,
  Pugno and Pavezzano (Total War names). Owner DON. 9 provinces. The fortress is certain. "Donalba" as a
  Tilean city is not on either wiki: the dump has the name only as a person, the Estalian Border Prince Desa
  Donalba (fandom:Border Princes [The Old World Rulebook p. 51]); the hub's worksheet source is the Old World
  web map, which I could not check. Medium confidence on the city.
- **Canon.** Monte Castello is the easternmost outpost of Tilea, south of the Apuccini, built against orc
  invasions from the east; beyond it lie the barren lands of the Border Princes (fandom:Monte Castello [Dogs
  of War 5e pp. 82-83]; lex:Monte_Castello [Town Cryer 28 p. 27]). No canon land-use text found for the
  district itself. Realm level: the far south is arid in high summer; Apuccini foothills are open woodland
  with goblins and brigands (fandom:Tilea#Geography [Dogs of War 5e p. 76]).
- **Analogue.** Calabria and Basilicata: steep, dry, poor, sheep and goats. vanilla:STATE_CALABRIA 30 (4
  provinces).
- **Climate layer.** BSk 57 %, BSh 43 %: steppe.
- **Proposal.** mediterranean, step -1, farm; livestock, wheat, vineyard. No place text, so this rests on the
  realm statement, the layer's semi-arid reading and the Calabrian analogue: a dry frontier at the mountain
  foot, below typical. Raw arable 29, one Calabria. **Tier B.**

### STATE_SARTOSA — Sartosa

- **Identity.** The island of Sartosa. Owner SRT. 5 provinces, 1,062 px. High confidence.
- **Canon.** A volcanic island under Mount Ertinia: very fertile soil, but so stony that farming is hard
  work; inland farms, most near the city, grow grapes, olives and wheat under pirate "protection"; the farms
  are small and the pirates hungry, so most food is imported; the sea supplies much of the diet; pearls are
  the legal export (lex:Sartosa [WFRP Companion pp. 72-78]; fandom:Sartosa [WFRP Companion p. 74]).
- **Analogue.** Sicily's shape and volcano at Malta's scale and food dependence: vanilla:STATE_SICILY 60,
  farm; vanilla:STATE_MALTA 5, orchard; vanilla:STATE_SARDINIA 15; vanilla:STATE_CORSICA 10, pasture.
  rw:Sicily [1911 EB]: tunny and coral fisheries, citrus and vines the high-value crops.
- **Climate layer.** BSh 75 %, BSk 25 %: steppe.
- **Proposal.** mediterranean, step 0, fishing village; vineyard, wheat. Fertile soil and stony fields cancel
  (step 0). A fishing village makes half a farm's grain and adds fish, which is the canon picture: the sea
  feeds the island and grain comes in by ship. The earlier draft (SRB-04) left farm-or-fishing open; the
  "most food must be imported" line settles it for me. Raw arable 17, between Sardinia and Malta.
  **Tier A.**

### STATE_SOUTHERN_SIREN_ISLES — Southern Siren Isles

- **Identity.** The southern part of the Isles of the Sirens (Fool's Rocks, Carvorna Archipelago) off Tobaro's
  coast, with the hub city Vedenza. The state name is the worksheet's invention. Owner TOB. 7 provinces. The
  archipelago is canon; whether Vedenza sits in this state or on the mainland opposite rests on a Total War
  placement. **Identity uncertain.**
- **Canon.** Countless small rocky islands line the coast round Tobaro, home to the Sirens (fandom:Isles of
  the Sirens [WFRP 4e Imperial Zoo pp. 86-87; Dogs of War 5e p. 42]); most are uninhabited by men
  (fandom:Tobaro [WFRP Companion p. 79]). Vedenza is a small city-state of about 10,500 on the coast by the
  archipelago, under Tobaro's influence; it exports olives and stone (lex:Vedenza [Up in Arms p. 54];
  Lexicanum only) and has a coastal plain to its north-west (lex:Vedenza [Monstrous Arcanum pp. 5-11]).
- **Analogue.** The Ionian and Aegean islands: vanilla:STATE_IONIAN_ISLANDS 10, orchard;
  vanilla:STATE_WEST_AEGEAN_ISLANDS 5, orchard; vanilla:STATE_MALTA 5, orchard.
- **Climate layer.** Cs 100 %: mediterranean. Agrees on class.
- **Proposal.** mediterranean, step -1, orchard; vineyard, livestock. Rock islands, mostly empty, whose one
  town sells olives: vanilla's own choice for small Mediterranean islands is the orchard, and the olive export
  is the canon hook for it. Raw arable 12. **Tier C** (identity).

### STATE_WESTERN_ESTALIAN_COAST — Western Estalian Coast

- **Identity.** The west coast on the Great Ocean: Verin and Jaraiz (inland, Obregon) and the port Muros
  (Obregon), per fandom:Estalia#Cities and Settlements; the "Estalian Littoral" of Fell Cargo ch. 15
  (fandom:Estalian Littoral). The state name is the worksheet's. Owner CNT. Medium-high confidence.
- **Canon.** No canon land-use text found. A Dark Elf raid on Muros left its people starving (lex:Los Cabos
  [Man O' War: Corsair quest]), which is about a raid, not the land. Realm level only.
- **Analogue.** Central Portugal: vanilla:STATE_BEIRA 65, vanilla:STATE_ESTREMADURA 30 (mediterranean, farm).
- **Climate layer.** Cfa 64 %, Cfb 36 %: temperate_forest_hill.
- **Proposal.** mediterranean, step 0, farm; wheat, vineyard, livestock. I put the class line between this
  state and Cefiro Hills to its north, as vanilla does between Beira and the Minho. Density is the same either
  way. Raw arable 55. **Tier B.**

### STATE_MIDDLE_BILBALI_01 — Middle Bilbali

- **Identity.** The landlocked interior behind the north coast: Potes (inland, Bilbali), Borgas (inland,
  Obregon), Azuara (inland, Novareno), per fandom:Estalia#Cities and Settlements; the Feroz Hills "at the
  heart of Bilbali's territory" are probably here (fandom:Feroz Hills; inference). Hub Gnaw Pit is a Skaven
  lair (fandom:Feroz Hills [Skaven 4e pp. 34-35 map]). Owner BIL. 12 provinces, no port. Medium confidence.
- **Canon.** No canon land-use text found for these places. Realm level: the interior is an arid plateau
  (fandom:Tilea#Geography [Dogs of War 5e p. 75]); a scorching Estalian Plain (fandom:Estalian Plain
  [Tamurkhan p. 158]); part of the hinterland is craggy grey rock with brambles and cactus
  (fandom:Estalia#Geography [The Red Duke ch. 15]); the northern kingdoms toward the Irranas are barren
  (lex:Estalia#Geography [WFB 3e p. 201]).
- **Analogue.** The northern meseta (Leon, Old Castile): dry-farmed wheat and barley, the Mesta's summer
  country (rw:Spain; rw:Mesta). vanilla:STATE_OLD_CASTILE 69 (22 provinces), vanilla:STATE_LEON 41 (10).
- **Climate layer.** Cfb 99 %: temperate_forest_hill. I depart from it.
- **Proposal.** mediterranean, step -1, farm; wheat, livestock, vineyard. #3676 puts rain-fed interior
  plateaus in the mediterranean class and vanilla's Castiles sit at its low end; canon calls the plateau arid.
  The layer's oceanic reading would give 53; this gives 38. Raw arable 38. **Tier B.** This is the row I am
  least sure of in Estalia: nothing canon speaks of this particular strip (open question 9).

### STATE_TOBARO — Tobaro

- **Identity.** The Principality of Tobaro on the Abasko coast, plus two hubs on the Estalian side of the
  range, Geulata and Larhgoz, which canon makes petty Estalian kingdoms hostile to Tobaro (fandom:Geulata,
  fandom:Larhgoz [Monstrous Arcanum pp. 7-8]). Owner TOB. 10 provinces, 1 impassable. High confidence for
  Tobaro; the state spans the range.
- **Canon.** The Abasko run almost 500 miles and drop to the sea in cliffs; a few fishing villages cling to
  them; silver and gems are mined and food is imported, the sea giving a plentiful but monotonous diet eked
  out by crops from a few high valleys (lex:Abasko_Mountains [WFRP 1e Rulebook pp. 279-280]). Tobaro's exports
  are silver and gems, traded for foodstuffs mostly with other Tilean states (lex:Tobaro [WFRP Companion
  pp. 79-86]). The coastal plain is narrow (fandom:Tobaro [WFRP Companion p. 79]). The city was resettled by
  shepherds and then farmers (fandom:Tobaro [WFRP Companion p. 80]). The Abasko are bare and sparsely
  vegetated like the Apuccini (fandom:Tilea#Geography [Dogs of War 5e p. 76]). Larhgoz was beset by famine
  (fandom:Larhgoz).
- **Analogue.** Liguria and Dalmatia: mountains to the water, terraces, fishing, bought grain.
  vanilla:STATE_DALMATIA 20 (mediterranean, farm); vanilla:STATE_PELOPONNESE 10.
- **Climate layer.** Cs 65 %, Cfb 35 %: mediterranean. Agrees on class.
- **Proposal.** mediterranean, step -2, fishing village; livestock, vineyard. Canon states outright that the
  land does not feed its people and that the sea does; that is the two-step case, and the result (16) sits
  beside Dalmatia. I keep the mediterranean class rather than highland_alpine because the evidence is a
  fertility statement about a Mediterranean coast and the fishing village needs the coast. The earlier draft
  (SRB-03) took one step; I take two. Raw arable 16. **Tier A.**

### STATE_CHATEAU_LOVARRE — Chateau Lovarre

- **Identity.** Chateau Lovarre, a Bretonnian castle in Carcassonne near the Tilean border, remote from the
  rest of Bretonnia (fandom:Château Lovarre [Warhammer Monthly 27, "Crusader"]); one of the castle-settlements
  guarding the Irrana passes (fandom:Irrana Mountains). Owner CAR. One province, 229 px. High confidence.
- **Canon.** No canon land-use text found for the castle. Range and dukedom text apply: barren Irranas;
  Carcassonne's foothill flocks.
- **Analogue.** A Pyrenean pass lordship (Andorra's scale): no vanilla state.
- **Climate layer.** BSk 100 %: steppe.
- **Proposal.** highland_alpine, step 0, pasture; livestock. Raw arable 1 (floor applies). **Tier B.**

### STATE_CARCASSONNE — Carcassonne

- **Identity.** Eastern Carcassonne, toward Athel Loren and the Vaults: Salignac-la-Rouge and Turin (Total
  War names) and Summersfall Fort, a hill fort "in the east of Carcassonne" (fandom:Summersfall Fort [Knights
  of the Grail p. 66]). Owner CAR. 9 provinces, 1 impassable. High confidence.
- **Canon.** As West Carcassonne (lex:Carcassonne [Knights of the Grail ch. VI pp. 64-65]). Kemmler's raids
  out of the Vaults fell on Carcassonne from 2470 IC (lex:Tilea#History [White Dwarf 309 p. 61]).
- **Analogue.** As West Carcassonne.
- **Climate layer.** Df 52 %, BSk 48 %: temperate_forest_hill by a hair.
- **Proposal.** temperate_forest_hill, step -1, pasture; livestock, wheat. Raw arable 25. **Tier A.**

### STATE_MIDDLE_TILEA — Middle Tilea

- **Identity.** The Principality of Pavona (hub city Pavona; other hubs invented). Owner PAV. 5 provinces,
  landlocked. High confidence.
- **Canon.** Pavona sits almost at the centre of Tilea, south of the Trantine Hills on the fertile plains
  between the River Remo and the Apuccini (fandom:Pavona [Dogs of War 5e p. 80; Brunner the Bounty Hunter]).
  Farmland and crowded peasant villages lie outside the walls, yet two days' ride away only a dirt road and
  ruined farmhouses remain (fandom:Pavona [Brunner]). Bucollia is a large wine-producing village and Organza a
  wool- and wine-exporting town (lex:Pavona; the Lexicanum footnote for both is Children of the Horned Rat
  ch. 4 p. 55, with Up in Arms p. 53 also listed). The inland states are mostly agricultural (lex:Tilea#Geography
  [WFRP 1e Rulebook p. 279]).
- **Analogue.** Umbria and inland Tuscany: vanilla:STATE_UMBRIA 20 (6 provinces), vanilla:STATE_TUSCANY 60.
- **Climate layer.** BSk 85 %, Cs 15 %: steppe. I depart from it.
- **Proposal.** mediterranean, step 0, farm; vineyard, livestock, wheat. "Fertile plains" argues for +1 and
  the empty country two days out argues against; I leave it at 0. Wine and wool are the named products, so
  they lead. Raw arable 27. **Tier A.**

### STATE_SUSSURRIO_WOOD — Sussurrio Wood

- **Identity.** Sussurrio Wood in southern Tilea, inside Luccini's lands (hub wood Sussurrio Wood; the other
  hubs are invented). Owner LUC. 5 provinces, landlocked. High confidence that the wood is here; the state
  also holds open land round it (inference from the hub "farm" anchor).
- **Canon.** With Tettoverde Wood it is one of the two biggest woodlands on the peninsula (fandom:Sussurrio
  Wood [Orcs and Goblins 8e p. 13]); the Worldroots of the Oak of Ages reach it (same page [Wood Elves 8e
  p. 8]); the Apuccini foothill forests are dangerous, with beasts, goblins and brigands (same page [WFRP 1e
  Rulebook p. 279]). No canon farm text.
- **Analogue.** The Sila and the wooded Lucanian uplands: vanilla:STATE_CALABRIA 30.
- **Climate layer.** BSk 51 %, BSh 49 %: steppe.
- **Proposal.** mediterranean, step -1, farm; livestock, wheat, vineyard. A state named for one of Tilea's two
  great woods carries less ploughland than the plain beside it. Raw arable 14. **Tier B.**

### STATE_BREGANALLE — Breganalle

- **Identity.** Western Carcassonne, toward the coast and the Estalian border: Breganalle, a Bretonnian town
  of Carcassonne that Kemmler destroyed in 2475 IC, raising its people as undead (fandom:The Vaults [White
  Dwarf 309, "Return of the Lichemaster"]), with the port Ferignac and Saint-Jacques (Total War names). Owner
  CAR. 9 provinces. High confidence (the earlier draft took the name for a Total War invention; it is in
  White Dwarf).
- **Canon.** Dukedom text as West Carcassonne. The town was wiped out 27 years before the game starts.
- **Analogue.** As West Carcassonne; the coastal end resembles the Basque coast.
- **Climate layer.** Cfa 44 %, BSk 26 %, Cfb 24 %, Df 7 %: temperate_forest_hill. Agrees on class.
- **Proposal.** temperate_forest_hill, step -1, pasture; livestock, wheat. Raw arable 28. **Tier B**
  (dukedom-level text; the only text about this place is its destruction).

<!-- ENTRIES-END -->

## 3. Rows

One row per state, file order. Tier counts: A 22, B 13, C 1. Classes: mediterranean 18, temperate_forest_hill 8,
highland_alpine 7, temperate_river_plain 3. Raw arable (before world scaling) sums to about 1,520; vanilla's
Italian states sum to about 790 and its Iberian states to about 790.

```csv
state_key,lore_class,fertility_step,subsistence,crops,tier,note,source
STATE_QUENELLES,temperate_forest_hill,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,"North pastoral, south arable; city on the Brienne; wheat is the Bretonnian staple",lex:Quenelles [Knights of the Grail] ; fandom:Quenelles [Knights of the Grail pp. 88-90] ; lex:Bretonnia [Knights of the Grail ch. I p. 6]
STATE_GRAVE_OF_CUILEUX,temperate_forest_hill,-1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,"Arable south of Quenelles, but a large tract (the Grave) is left unfarmed",lex:Quenelles [Knights of the Grail] ; fandom:Quenelles [Knights of the Grail pp. 88-90]
STATE_AQUITAINE,temperate_river_plain,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,"Almost entirely arable lowland; class used for its density, canon names no major river",lex:Aquitaine [Knights of the Grail ch. VI pp. 47-49]
STATE_BRIONNE,temperate_river_plain,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,"Mostly arable, some pasture east and south; port at the Brienne mouth",fandom:Brionne [Knights of the Grail pp. 61-62] ; lex:Bretonnia [Knights of the Grail ch. I p. 6]
STATE_CANTABRIO_ROAD,temperate_forest_hill,0,building_subsistence_farm,building_vineyard building_livestock_ranch building_wheat_farm,A,"Bilbali's north coast: famous dark red wine; humid Cantabrian-coast analogue",lex:Bilbali [Sea of Claws p. 139] ; fandom:Bilbali [Realms of Sorcery p. 234] ; rw:Spain [1911 EB Spain]
STATE_CEFIRO_HILLS,temperate_forest_hill,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,B,"North-west hill coast (canon Obregon); no land-use text; Galicia analogue",lex:Obregon [The Old World website map] ; lex:Estalia#Trade [WFRP 1e p. 277] ; rw:Spain [1911 EB Spain]
STATE_NUJA,mediterranean,0,building_subsistence_farm,building_vineyard building_wheat_farm building_livestock_ranch,B,"South-west coast (canon Avila); realm text only: fertile south coast, wine, oil, fruit",lex:Estalia#Trade [WFRP 1e p. 277] ; fandom:Estalia [The Old World RPG Player's Guide p. 187]
STATE_ESTALIAN_HIGHLANDS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Barren northern hill kingdoms on the Irrana flank; grain carried in; sheep country",lex:Estalia#Geography [WFB 3e p. 201] ; lex:Irrana_Mountains [WFRP 1e pp. 270-279] ; fandom:Irrana Mountains [Old World Armoury p. 11] ; fandom:Livestock [Old World Armoury p. 83]
STATE_CENTRAL_MAGRITTA,mediterranean,0,building_subsistence_farm,building_vineyard building_wheat_farm building_livestock_ranch building_cotton_plantation,B,"Magritta on the Tagos mouth: fertile south coast exporting wine, oil and fruit",lex:Estalia#Trade [WFRP 1e p. 277] ; fandom:Estalia [The Old World RPG Player's Guide p. 187] ; rw:Andalusia [1911 EB Spain]
STATE_WEST_MAGRITTA,mediterranean,0,building_subsistence_farm,building_vineyard building_wheat_farm building_livestock_ranch building_cotton_plantation,B,"South coast west of Magritta; realm text only",lex:Estalia#Trade [WFRP 1e p. 277] ; fandom:Estalia [The Old World RPG Player's Guide p. 187]
STATE_SOUTHEAST_MAGRITTA,mediterranean,0,building_subsistence_farm,building_vineyard building_wheat_farm building_livestock_ranch building_cotton_plantation,A,"Aguilas: hills clad in olive groves; south-east coast",lex:Aguilas [Fell Cargo ch. 17] ; lex:Estalia#Trade [WFRP 1e p. 277]
STATE_EAST_MAGRITTA,mediterranean,-1,building_subsistence_farm,building_livestock_ranch building_vineyard building_wheat_farm,A,"Zaragoz: pasture round the crag, orange groves and vines on higher ground, dry thorn scrub; arid uplands",fandom:Zaragoz#Geography [Zaragoz (novel)] ; fandom:Tobaro [WFRP Companion p. 79] ; rw:Castile [1911 EB Spain]
STATE_WESTERN_IRRANAS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,"Largely barren peaks; poor mountain kingdoms; pass fortresses",lex:Irrana_Mountains [WFRP 1e pp. 270-279]
STATE_EAST_BILBALI,temperate_forest_hill,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,B,"North-east coast (canon Novareno) under the Irranas; realm text only",lex:Novareno [The Old World website map] ; lex:Estalia#Trade [WFRP 1e p. 277] ; rw:Spain [1911 EB Spain]
STATE_BLIGHTED_MARSHES,mediterranean,-2,building_subsistence_farm,building_wheat_farm,A,"Fog-bound swamp; only crop is black corn cut by Skaven slaves; not human farmland",lex:Blighted_Marshes [Plague Fleet pp. 51-52; Empire 4e p. 5] ; lex:Skavenblight [Skaven 4e pp. 6-7]
STATE_EASTERN_IRRANAS,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch,A,"Barren, cold eastern Irranas where they join the Vaults",lex:Irrana_Mountains [WFRP 1e pp. 270-279] ; fandom:Tilea#Geography [Dogs of War 5e p. 76]
STATE_NORTH_TILEA,temperate_river_plain,0,building_subsistence_farm,building_wheat_farm building_vineyard building_livestock_ranch,A,"Miragliano: swamp belt, then huge grain fields, orchards, vineyards and pasture; Ravola wine; Po-plain analogue","fandom:Miragliano#Surrounding Lands [Brunner the Bounty Hunter, Beneath the Vaults] ; lex:Miragliano [Up in Arms pp. 52-53] ; fandom:Ravola [Dogs of War 5e p. 77] ; rw:Lombardy [1911 EB Lombardy]"
STATE_WEST_CARCASSONNE,temperate_forest_hill,-1,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,"Narrow arable bands on the rivers; otherwise pastoral or mountain; foothill sheep",lex:Carcassonne [Knights of the Grail ch. VI pp. 64-65]
STATE_NOVALONE_PASS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_rye_farm,A,"Vaults pass: dwarf grain fort, a cheese-and-wool town, cattle pasture and modest harvests in the valleys",fandom:Karak Eksfilaz [Lords of Stone and Steel p. 23] ; fandom:Karak Kaferkammaz [Dwarfs: Stone and Steel p. 112] ; fandom:The Vaults [WFRP 1e p. 274]
STATE_APUCCINI_MOUNTAINS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,"Rugged, largely uninhabited range, but Karak Grom is fed by a grain fort and a grain, cheese and wool town",lex:Apuccini_Mountains [WFRP 1e pp. 270-271; Dogs of War 5e pp. 75-76] ; fandom:Karak Grom [Lords of Stone and Steel p. 24]
STATE_DARK_MAIDEN_PASS,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch,B,"Canon pass across the southern Apuccini; no land-use text; range text applied",fandom:Apuccini Mountains#Dark Maiden Pass [Renegade Crowns p. 6] ; lex:Apuccini_Mountains [WFRP 1e pp. 270-271; Dogs of War 5e pp. 75-76]
STATE_VEREZZI,mediterranean,1,building_subsistence_farm,building_wheat_farm building_vineyard building_livestock_ranch,A,"Verezzo dominates a fertile plain; two large grain villages and a citrus village",lex:Verezzo [Up in Arms p. 54]
STATE_REMAS,mediterranean,1,building_subsistence_farm,building_wheat_farm building_vineyard building_livestock_ranch,A,"Feeds itself from its own corn fields; imported grain only when vermin ate the crop",lex:Remas ; fandom:Remas [Dogs of War 5e p. 81]
STATE_TRANTINE_HILLS,mediterranean,0,building_subsistence_farm,building_vineyard building_livestock_ranch building_wheat_farm,A,"Hill state: orchards and olive groves, an olive village, two sheep villages; stony north-east","lex:Trantio [Up in Arms p. 54] ; fandom:Trantine Hills [Inferno! 21] ; fandom:Campogrotta [Death's Dark Shadow pp. 7-11]"
STATE_PLAINS_OF_LUCCINI,mediterranean,1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,"Copious granaries; horses bred on the great southern plains; exports grain and wool; vineyards and olive groves",lex:Luccini [WFRP 1e pp. 279-280; Up in Arms p. 52] ; fandom:Luccini [Dogs of War 5e pp. 24-25]
STATE_MONTE_CASTELLO,mediterranean,-1,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,B,"Arid south-east frontier under the Apuccini; no land-use text; Calabria analogue",fandom:Tilea#Geography [Dogs of War 5e pp. 75-76] ; lex:Monte_Castello [Town Cryer 28 p. 27]
STATE_SARTOSA,mediterranean,0,building_subsistence_fishing_village,building_vineyard building_wheat_farm,A,"Fertile but stony volcanic isle: grapes, olives, wheat; most food imported; sea feeds much of the diet",lex:Sartosa [WFRP Companion pp. 72-78] ; fandom:Sartosa [WFRP Companion p. 74]
STATE_SOUTHERN_SIREN_ISLES,mediterranean,-1,building_subsistence_orchard,building_vineyard building_livestock_ranch,C,"Rocky Siren isles, mostly uninhabited; Vedenza exports olives and stone; identity rests on a hub placement",lex:Vedenza [Up in Arms p. 54] ; fandom:Isles of the Sirens [Imperial Zoo pp. 86-87] ; fandom:Tobaro [WFRP Companion p. 79]
STATE_WESTERN_ESTALIAN_COAST,mediterranean,0,building_subsistence_farm,building_wheat_farm building_vineyard building_livestock_ranch,B,"West coast (canon Obregon); realm text only; Portuguese-coast analogue",lex:Estalia#Trade [WFRP 1e p. 277] ; lex:Obregon [The Old World website map]
STATE_MIDDLE_BILBALI_01,mediterranean,-1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,B,"Landlocked northern interior: the arid plateau; meseta analogue",fandom:Tilea#Geography [Dogs of War 5e p. 75] ; lex:Estalia#Geography [WFB 3e p. 201] ; rw:Castile [1911 EB Spain]
STATE_TOBARO,mediterranean,-2,building_subsistence_fishing_village,building_livestock_ranch building_vineyard,A,"Abasko cliffs drop to the sea; fishing villages; food imported for silver; few high valleys",lex:Abasko_Mountains [WFRP 1e pp. 279-280] ; lex:Tobaro [WFRP Companion pp. 79-86]
STATE_CHATEAU_LOVARRE,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch,B,"One-province pass castle in the Irranas, held by Carcassonne; no land-use text","fandom:Château Lovarre [Warhammer Monthly 27, Crusader] ; lex:Irrana_Mountains [WFRP 1e pp. 270-279]"
STATE_CARCASSONNE,temperate_forest_hill,-1,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,"Narrow arable bands on the rivers; otherwise pastoral or mountain; foothill sheep",lex:Carcassonne [Knights of the Grail ch. VI pp. 64-65]
STATE_MIDDLE_TILEA,mediterranean,0,building_subsistence_farm,building_vineyard building_livestock_ranch building_wheat_farm,A,"Pavona: a wine village and a wool-and-wine town on plains under the Apuccini",lex:Pavona [Children of the Horned Rat p. 55; Up in Arms p. 53] ; fandom:Pavona [Dogs of War 5e p. 80]
STATE_SUSSURRIO_WOOD,mediterranean,-1,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,B,"One of the two biggest woods in Tilea, inside Luccini's lands; woodland lowers the farmed share",fandom:Sussurrio Wood [Orcs and Goblins 8e p. 13; Wood Elves 8e p. 8; WFRP 1e p. 279]
STATE_BREGANALLE,temperate_forest_hill,-1,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,B,"Western Carcassonne; dukedom text applied; the town itself was destroyed by Kemmler in 2475 IC","lex:Carcassonne [Knights of the Grail ch. VI pp. 64-65] ; fandom:The Vaults [White Dwarf 309, Return of the Lichemaster]"
```

## 4. Disagreements

### 4.1 Against the climate layer (`state_climate_index.json`, dominant zone -> class)

| state | layer reads | I propose | reason |
|---|---|---|---|
| Plains of Luccini | steppe (BSh 96 %) | mediterranean +1 | canon granary, horse plains, grain and wool exports |
| Verezzi | steppe (BSk 56 %) | mediterranean +1 | canon "fertile plain", large grain villages |
| Middle Tilea | steppe (BSk 85 %) | mediterranean 0 | canon fertile plains, wine and wool |
| Monte Castello | steppe | mediterranean -1 | realm text; ends close to the layer's intent (dry): 29 raw against 12 |
| Sussurrio Wood | steppe | mediterranean -1 | a canon wood, not grassland |
| Sartosa | steppe (BSh 75 %) | mediterranean 0, fishing village | canon fertile volcanic soil; grapes, olives, wheat |
| Blighted Marshes | steppe (BSk 58 %) | mediterranean -2 | a swamp; the sizes agree by accident (19 against 12) |
| North Tilea | steppe by plurality (BSk 37 %) | temperate_river_plain 0 | canon grain fields behind the marsh belt; Po-plain analogue |
| Nuja, Central and West Magritta, Western Estalian Coast | temperate_forest_hill (Cfa) | mediterranean 0 | wine, oil and fruit export coast; density unchanged |
| Middle Bilbali | temperate_forest_hill (Cfb 99 %) | mediterranean -1 | canon arid plateau; 38 against 53 |
| Estalian Highlands | temperate_forest_hill (Cfb) | highland_alpine 0, pasture | canon barren hill kingdoms; 7 against 20 |
| Western and Eastern Irranas, Apuccini, Dark Maiden Pass, Chateau Lovarre | steppe (BSk) | highland_alpine | named mountain ranges; densities are close (4.6 against 5.3) |
| Novalone Pass | boreal_forest (Dc 56 %) | highland_alpine 0 | the Vaults; canon valley farms and pasture |
| Aquitaine, Brionne | temperate_forest_hill (Cfb) | temperate_river_plain 0 | canon "almost entirely arable" / mostly arable |

Pattern, for whoever tunes the layer: it reads **all of lowland Tilea south of Trantio as semi-arid steppe**
(BSk/BSh). Canon describes a dry-summer mediterranean land with fertile plains. The gap is about a factor of
3.5 in density on five states and a factor of 5 on the Plains of Luccini. If the layer moved toward Cs for the
Tilean lowland, most Tilean rows here would shrink to a fertility step and a crop list. It also reads the
mountain rim as BSk rather than ET (the ranges do not register as high ground), so every range row in this
file is a class swap.

The layer and I **agree** on: Quenelles, Grave of Cuileux, the three Carcassonne states (forest-hill); the
three north-coast Estalian states and Cefiro Hills (forest-hill; here I follow the layer against the earlier
lead); Remas, Trantine Hills, Tobaro, Southeast and East Magritta, Southern Siren Isles (mediterranean).

### 4.2 Against the earlier part-A leads (`state_climate_classes.csv`, `agro_climate_overrides_draft.md`)

- **SRB-01 (Estalian interior = mediterranean).** Kept for Middle Bilbali, the only one of its four states
  left in the file (Miramar Hills, Pina Wood and South Bilbali are retired keys). I add step -1 on the
  arid-plateau text the draft did not use.
- **SRB-02 (Blighted Marshes down 2).** Confirmed. New: the marsh is a cropped Skaven grain source (black
  corn), so the subsistence building stays farm and the crop list is one grain building.
- **SRB-03 (Tobaro down 1, fishing village).** Fishing village confirmed. Step taken to -2: canon says the
  food is imported and only a few high valleys are cropped.
- **SRB-04 (Sartosa fishing village, step 0).** Confirmed. The draft's open question is closed by the line
  that most food must be imported (WFRP Companion p. 74).
- **SRB-05 (Luccini and Remas up 1).** Luccini confirmed with more text. Remas kept but flagged as the weaker
  of the two. **Verezzo added** at +1: the draft said it had no Lexicanum page; it has one, with a fertile
  plain and two large grain villages.
- **SRB-06** is the sibling's (Marshes of Madness).
- **BRE-01 (Aquitaine river plain).** Kept, with the caveat that canon denies a major river. Brionne joins
  the class on the Fandom land-use line the draft's Lexicanum extract lacked.
- **BRE-05 (Grave of Cuileux down 2).** Softened to -1: the state is all of south-west Quenelles.
- **BRE-06 (Carcassonne down 1, pasture).** Confirmed for all three states. Breganalle moves from "Total War
  name" to a canon town (White Dwarf 309).
- **Estalia coast = mediterranean in the class CSV.** Changed to temperate_forest_hill for Cantabrio Road,
  East Bilbali and Cefiro Hills (layer and Cantabrian analogue). No change in size.
- **North Tilea = mediterranean in the class CSV.** Changed to temperate_river_plain.
- **Mountain states (karaz_ankor rows in the CSV).** Class highland_alpine kept. New evidence: the dwarf
  grain forts and cheese-and-wool towns of the Vaults and Apuccini (Lords of Stone and Steel pp. 23-24). The
  draft's open question 4 (Apuccini wooded or bare) no longer decides anything.
- **Tiers.** The CSV's tier T rows (Total War names) are re-tiered: Nuja B, Chateau Lovarre B, Sussurrio Wood
  B, Breganalle B. All four names are on the wikis with GW or Black Library sources.

## 5. Open questions for Chris

1. **Grave of Cuileux: -1 or -2?** The state is the whole south-west of Quenelles (21 provinces). Canon says
   "a large area" there is unfarmed and that southern Quenelles is otherwise arable. I took -1. If the drawn
   state is meant to be the haunted tract itself, -2 is right.
2. **Aquitaine as river plain.** Canon: almost entirely arable, and no major river. The class is used for its
   density. If the class name must mean a river, use temperate_forest_hill +1 (23 per 1,000 px against 26).
3. **Black corn: wheat or rice building?** The Skaven crop is cut from reed beds by boat and then milled. I
   wrote `building_wheat_farm` with a farm subsistence. `building_rice_farm` (wet cultivation), or even
   `building_subsistence_rice_farm` (double the peasants per level, which suits a slave-packed marsh), would
   also fit. This is a design call on how Skavenblight should feed, not a lore gap.
4. **North Tilea: river plain or mediterranean +1?** Both give about 110 raw arable. River plain says "Po
   valley" and is the only way the model gets a river signal; mediterranean +1 keeps Tilea in one class.
5. **Remas +1.** Kept from SRB-05 on thinner evidence than Luccini or Verezzo. Say if you want it at 0.
6. **Plantation crops.** I found no canon cotton, tobacco, sugar, dye or silk growing in Tilea or Estalia
   (searched the dump pages for both realms and the eight Tilean cities). I dropped them everywhere except a
   cotton tail on the three Magritta coast states, kept only because the mediterranean default has it and
   Andalusia grew some. Do you want the Southern Realms to have any plantation crop? Vanilla gives its
   Italian and Spanish states cotton, silk, tobacco and sugar freely.
7. **The mod's owners against canon in the mountains.** Novalone Pass and most of the Apuccini belong to the
   goblin tag BRN and Dark Maiden Pass to Clan Skaar, while canon has four living dwarf holds there with
   grain forts and human client towns. I wrote pasture for the mod's owners. If these states are repainted
   to dwarfs, the canon supports `building_subsistence_farm` for Novalone Pass (grain forts): a new entry
   beside Karak Izor, Karak Azgaraz and Kraka Drak in the standing "grain holds" exception.
8. **Trantine Hills: farm or orchard subsistence?** Canon stresses orchards and olive groves. I kept farm
   (Tuscany's grain, vine and olive mix); orchard would make Trantio a grain importer.
9. **Middle Bilbali.** No text exists for this strip. I applied the "arid plateau" realm text and took it one
   step down, against a layer that reads it as oceanic. If you trust the layer more here, it is
   temperate_forest_hill 0 (53 raw against 38).
10. **Southern Siren Isles and Monte Castello identities.** Is Vedenza meant to be on these islands? Is
    "Donalba" (hub city and tag DON) a place on the Old World web map? Neither wiki has it as a Tilean city;
    the name appears only as the Estalian Border Prince Desa Donalba.
11. **Estalia's minor kingdoms.** The mod's CNT "Cantonia" sits on the west coast; the wikis put Cantonia in
    the south-east and Obregon and Avila in the west. No farmland row depends on it (I keyed on places, not
    kingdoms), but Lexicanum's trivia note says GW took those four kingdom names off its map in February 2025.
12. **Remas as the fishing city.** Fandom calls the Remans the world's greatest fishermen, on a lagoon (no GW
    footnote on that paragraph). I left the subsistence building as farm. If fishing-wharf caps are set per
    state later, Remas should be the high one in Tilea.

### 5b. What I could not do

- **Lexicanum corroboration after 2026-11-19.** Blocked (HTTP 429, then 403); I stopped, per the brief. Not
  corroborated on Lexicanum: the Brionne land-use line; the Miragliano hinterland paragraph (a Brunner
  novel); the Vaults pasture line (WFRP 1e p. 274); the Vaults and Apuccini dwarf grain forts (Lords of Stone
  and Steel); Zaragoz's geography (novel); the Sartosa food-import line; the sheep line (Old World Armoury
  p. 83); the Luccini vineyards-and-shepherds line (Dogs of War 5e pp. 24-25); Breganalle; Chateau Lovarre.
- **Fandom for the Up in Arms village lists.** The Trantio, Verezzo, Pavona and Miragliano village lines
  (olive, sheep, grain, citrus and wine villages) are on Lexicanum only; the dump's pages for those villages
  carry no farm text.
- **Real-world figures for 1836 itself.** The usable regional numbers are from the 1911 Britannica (1900-1905
  data); Italy has no national land statistics before 1909. A second round of web reading (Gironde and the
  Pyrenean departments for southern Bretonnia; Andalusian plantation crops) was cut off by the account usage
  limit, so southern Bretonnia's analogue rests on vanilla's own numbers plus the general French and Alpine
  sources.
- I did not open the GW books themselves; every book-and-page reference is carried from a wiki footnote.

## 6. Pages read

**Lexicanum (2026-11-19, 33 pages read; all later attempts refused):** Tilea, Miragliano, Remas, Luccini, Verezzo,
Trantio, Pavona, Tobaro, Sartosa, Blighted Marshes, Skavenblight, Apuccini Mountains, Abasko Mountains, Irrana
Mountains, Vaults, Vedenza, Monte Castello, Ravola, Estalia, Bilbali, Magritta, Avila, Cantonia, Novareno,
Obregon, Aguilas, Los Cabos, Porto Real, Quenelles, Aquitaine, Brionne, Carcassonne, Bretonnia. Not readable:
Tilean Sea (HTTP 403), Larhgoz and Wine (no such page).

**Fandom, live API (2026-11-19):** Tilea, Estalia, Blighted Marshes, Skavenblight, Black Corn, Remas, Luccini,
Miragliano, Verezzo, Sartosa, Tobaro, Trantio, Pavona, Carcassonne, Quenelles, Brionne, Aquitaine, Bilbali,
Magritta, Irrana Mountains, Abasko Mountains, Apuccini Mountains, The Vaults, Monte Castello, Vedenza.

**Fandom, local dump `sources/wiki/pages/` (2026-11-20; * = no farm-relevant text found):** Cuileux, Massif
Orcal, River Brienne, Dragon Falls, Trantine Hills, Sussurrio Wood, Tettoverde Wood, Isles of the Sirens,
Estalian Plain, Estalian Littoral, Nerja*, Geulata, Larhgoz, Wine, Livestock, Horses, Vedenza, Karak Grom,
Karak Bhufdar, Karak Eksfilaz, Karak Kaferkammaz, Kazad Frukund, Kazad Sedazund*, Domatburg*, Queekwell*,
Zarakzil, Portomaggiore*, Mintopua*, Pugno*, Organza*, Ravola, Viadaza*, Urbimo*, Campogrotta, Ebino*,
Catrazza*, Scorcio, Toscania*, Alcatani, Lumbrusco*, Ciabbatta*, Etobrutti*, Zaragoz, Tilean Sea, Cantonia*,
Avila*, Obregon*, Novareno*, Aguilas, Almagora*, Los Cabos*, Miramar Hills, Sombra Wood, Durango*, Reas*,
Feroz Hills, Valley of Windmills, Castle Carcassonne, Summersfall Fort, Derrevin Libre, Bone Hills, Chateau
Lovarre, Cantabrio Road, Apuccini Mountains, Irrana Mountains, The Vaults, Border Princes (for "Donalba"
only), Remas, Luccini, Miragliano, Tobaro, Sartosa, Verezzo, Pavona, Monte Castello, Magritta, Bilbali,
Estalia, Tilea, Trantio. The last twelve were also searched for cotton, sugar, tobacco, silk-growing, rice,
hemp and flax: no hit.

**Web (real-world half):**
- https://en.wikisource.org/wiki/1911_Encyclopædia_Britannica/Italy (first 100,000 characters: land use and crops)
- https://en.wikisource.org/wiki/1911_Encyclopædia_Britannica/Spain (first 100,000 characters)
- https://en.wikisource.org/wiki/1911_Encyclopædia_Britannica/Lombardy
- https://en.wikisource.org/wiki/1911_Encyclopædia_Britannica/Tuscany
- https://en.wikisource.org/wiki/1911_Encyclopædia_Britannica/Sicily (first 100,000 characters)
- https://en.wikipedia.org/wiki/Mesta
- https://en.wikipedia.org/wiki/Pontine_Marshes
- https://en.wikipedia.org/wiki/Tavoliere_delle_Puglie
- https://en.wikipedia.org/wiki/Transhumance_in_the_Alps
- https://en.wikipedia.org/wiki/Roman_Campagna (thin: abandonment to malaria, pastoral landscape, 2,100 km2)
- https://en.wikipedia.org/wiki/Maremma (thin: Maremmana cattle and horses, 5,000 km2)
- Not read (account usage limit on 2026-11-20): 1911 EB "Gironde" and "Basses-Pyrenees".
- https://en.wikipedia.org/wiki/Mezzadria (thin), https://en.wikipedia.org/wiki/Latifundium (nothing usable for
  1800-1900), https://en.wikipedia.org/wiki/Economic_history_of_Italy (first half; nothing on crops)
- Two web searches whose result summaries I used without opening the documents: the Statesman's Year-Book 1871
  Italian land table and the ISTAT historical-series note; the 1840 Statistique de la France fallow figure.
  Treat those three numbers as leads.
