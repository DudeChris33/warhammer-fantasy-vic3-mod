# Farmland lore dossier: Bretonnia group (`map_data/state_regions/03_brettonia.txt`)

Board item #3680, epic #3675. Written across two runs (2026-11-19 and 2026-11-20). 36 states in the file.
Status line (kept current): **COMPLETE** - 36 entries, 36 rows (2026-11-20).

Citation forms: `lex:` = Lexicanum page read in the browser on 2026-11-19 (nine pages, before Cloudflare began
challenging every request); `fandom:` = article read from the local dump `sources/wiki/pages/`; `rw:` = real-world
source read on the web; `vanilla:` = the vanilla install's `map_data/state_regions`. Anything marked *lead* was
not read by me and is not evidence.

## 0. What is in this file (it is not the fourteen dukedoms)

The file holds 36 states. Located by province centroid on `map_data/provinces.png` and by owner
(`mapgen/derived/state_ownership.json`):

| Block | States | Owner tags |
|---|---|---|
| Northern and western dukedoms | L_ANGUILLE, COURONNE, LYONESSE, LYONESSE_HILLS, ARTOIS, GISOREUX, OIS_GAP, BASTONNE, CASTLE_SANGASSE, BORDELEAUX, MONTFORT, PARRAVON | LAN, COU, LYO, LYO, ART (+OKP 2 provinces), GIS, GIS, BAS, BAS, BOR, MNF, PAR |
| Mousillon | MOUSILLON (owned by Lyonesse), CASTLE_MOUSILLON (owned by Mousillon) | LYO, MOU |
| Upper Grismerie strip | LAND_735 (centroid 3975,921, between Massif Orcal and Parravon; unnamed) | QUE |
| Greenskin mountains | MASSIF_ORCAL, PALE_SISTERS | MOR, SKZ |
| Grey Mountain dwarf holds | CROOKED_CORRIDOR (Karak Ziflin), NORTH_GREY_MOUNTAINS (Karak Azgaraz hub, owner Karak Norn), SOUTH_GREY_MOUNTAINS (Karak Norn) | KZF, KNO, KNO |
| Athel Loren (13 states) | ANMYR, GLADE_OF_ETERNAL_MOONLIGHT, WATERFALL_PALACE, ARGWYLON, TAL_ESTH, WYDRIOTH, TORGOVANN, GLADE_OF_ETERNAL_MIDNIGHT, YI_EDRI_ETERNOS, KING_S_GLADE, TALSYN, HALLS_OF_EQUOS, TYR_VANNA | ANM, ANM, ARG, ARG, WYD, WYD, TRG, TRG, TLS, TLS, TLS, TLS, TLS |
| Albion (3 states, unnamed) | LAND_736 (north, centroid 3382,608), LAND_079 (centre, 3332,702), LAND_078 (south plus islet, 3336,751) | unowned |

**Not in this file**: Aquitaine, Brionne, Quenelles proper, Carcassonne, the Grave of Cuileux (all in
`05_southern_realms.txt`) and the Marches of Couronne. They belong to another dossier.

## 1. Realm picture

### 1.0 Summary

**Canon.** Knights of the Grail (WFRP 2e) gives each dukedom an explicit arable-versus-pastoral line, and both
wikis reproduce it. Realm rule: strip farming with wheat dominant, barley and vegetables beside it, vines and
orchards on steep ground with sheep under them, pigs at the forest edge. By dukedom, for the ones in this file:
L'Anguille is the best land (nearly all arable, fertile, mild, near year-round harvest); Couronne proper,
Bordeleaux and both halves of Lyonesse are "mostly/mainly arable"; Bordeleaux is the wine exporter; Bastonne is
arable in the west and pastoral in the east; Gisoreux is mostly pastoral hill country with arable only along the
Sannez; Artois is forest with stock-keeping stockade villages; Montfort and Parravon are mountain dukedoms, the
first a food importer, the second saved by one fertile vale; Mousillon's remnant is swamp and scrub. Round them:
two greenskin ranges canon calls barren (Massif Orcal, Pale Sisters), Grey Mountain dwarf holds that do grow
grain at Azgaraz and Norn, Athel Loren where the Asrai hunt and nothing has them ploughing, and Albion, a
rain-drowned bog where few crops grow.

**Analogue.** Bretonnia is medieval France seen through Arthurian romance, and the dukedoms map cleanly:
L'Anguille and Couronne on Normandy and Picardy (grain plain behind chalk cliffs, horse country, no vines),
Lyonesse on Brittany, Bordeleaux on the Bordelais, Bastonne and northern Quenelles on the Loire and Burgundy
margins, Artois on the Ardennes, Gisoreux on the western bocage, Montfort and Parravon on Savoy and the Jura,
the Massif Orcal on the Massif Central, Mousillon on the undrained Sologne and Landes, Albion on the Highlands
and western Ireland. France about 1836-1850 had some 5.3-5.9 million ha under wheat alone, a third to a half of
its arable in fallow each year, vines everywhere south of Normandy and Brittany, rye and buckwheat on the poor
west and centre, and horse-breeding concentrated in Normandy and the Perche.

**Where canon and analogue differ, and which I follow.** (1) Vanilla gives Normandy, Brittany and Guyenne
vineyards; the 1911 Britannica says vines stop short of Normandy and Brittany, and canon names wine only for
Bordeleaux and one Gisoren valley. I follow canon plus the real vine line: no vineyard in L'Anguille, Couronne
or Lyonesse. (2) Vanilla lists wheat first for every French state; for Bordeleaux I put the vineyard first on
canon. (3) Vanilla uses the farm subsistence type for all of western Europe including its mountains; I keep
farm for every Bretonnian-owned state, and use pasture only where canon shows a people who do not till
(greenskins, Wood Elves, Albion's cattle chiefs, Karak Ziflin's goatherds). (4) Canon is silent on any
north-south split of Albion; all three states get one row.

Working notes follow.

### 1.1 Canon read on Lexicanum, 2026-11-19 (nine pages; paraphrased)

- **lex:Bretonnia#Farming [Knights of the Grail ch. I p. 6]**: each peasant family works one strip of arable;
  wheat is the dominant crop, with barley and vegetables; vineyards and orchards are common on steep land, often
  with sheep grazed beneath them; pigs forage the forest edge. Shepherds and shepherdesses fight off Beastmen and
  greenskins.
- **lex:Bretonnia#Peasantry [Bretonnia 6e p. 42]**: peasants surrender nine tenths of their crop to the lord.
- **lex:Bretonnia#Rivers [Knights of the Grail ch. I p. 9]**: Brienne rises in Loren; Gilleau rises in the Massif
  Orcal and reaches the sea at Bordeleaux; Grismerie is the largest, broad and slow, from near Parravon to the sea
  in the marshes of Mousillon; Sannez is narrow, deep and swift, through Couronne to L'Anguille.
- **lex:Bretonnia#History [Bretonnia 5e pp. 10-16]**: the Bretonni took the fertile valleys and drove the
  greenskins into the wilderness.
- **lex:L'Anguille#lead and #Geography [Knights of the Grail ch. VI pp. 43-46]**: most of the dukedom is arable;
  inland L'Anguille is almost entirely arable, the soil fertile, the weather mild (the sea-cliffs take the storms),
  harvests through most of the year; villages keep narrow strips of woodland for timber and pig forage; the
  southern reach lies in the Forest of Arden; the coast is short, cliff-bound and nearly unsettled outside the
  city; city folk are sailors, fishermen and traders, country folk are farmers (a turnip harvest is mentioned);
  the city sits at the mouth of the Sannez.
- **lex:Couronne#lead and #Geography and #The People [Knights of the Grail ch. VI pp. 67-70]**: Couronne proper
  lies north of the Sannez and is mostly arable, with pastoral land in the south and east where it nears the Pale
  Sisters and the Grey Mountains; the coast is rugged, storm-lashed and raided; the Marches (a separate state, not
  in this file) are plains too dry for most crops and the best horse-breeding country in Bretonnia; in Couronne
  horse breeding is so general that most peasants have the use of a horse; greenskins from the Grey Mountains raid
  the south-east.
- **lex:Lyonesse#Geography [Knights of the Grail ch. VI pp. 74-77]**: rugged coast with many small islands,
  where most coastal villages sit; the north is hilly with caves and underground rivers; the south has dozens of
  small rivers and lakes, turning to marsh near Mousillon; the Forest of Arden reaches the south-east. Barley
  Motte is a cursed holding near the L'Anguille border. Sigmarsheim is an Empire outpost in the Forest of Arden.
- **lex:Mousillon#lead, #Locations, #Landuin and the Fall [Barony of the Damned ch. I pp. 7-9, ch. II pp. 11-12
  and 19-25; Vampire Counts 5e p. 17; Undead 4e p. 11]**: a small duchy on the west coast between Lyonesse,
  Gisoreux and Bordeleaux; Lyonesse took its most fertile parts in the 1900s IC; the land is little more than a
  swamp fed by the Grismerie, very poor farming, the prized food being frogs, snails and slugs; the Grismerie
  floods the poor quarters of the city every spring; the main business is smuggling; the Orphan Hills are low
  hills in the east; the Victory of Landuin battlefield keeps unusually good soil; the Forest of Arden marks the
  north-west frontier; the Guerac Circle is the site of the Oak of Prophecy.
- **lex:Artois#lead, #Geography, #The People [Knights of the Grail ch. VI pp. 51-53]**: all of the dukedom but a
  small western strip lies inside the Forest of Arden; the land outside the forest is mostly arable and holds
  most of the people; forest villages are stockaded and raise animals rather than crops, because stock can be
  brought inside when Beastmen attack (at least yearly); woodsmen and charcoal burners; destroyed villages dot the
  east. Larret is the largest town.
- **lex:Bordeleaux#lead, #Geography, #The People [Knights of the Grail ch. VI pp. 54-57 as Lexicanum numbers it;
  Sea of Claws p. 82]**: the kingdom's largest wine exporter, a land of farms and vineyards; mostly arable with
  some pastoral land near the coast; high cliffs, over a dozen natural harbours and more fishing villages; the
  south-east corner is under the Forest of Chalons (villages there do flourish); in the north the coastal hills
  of Bordeleaux stand over the swamp of Mousillon at the Grismerie mouth; wine from the Bordelen coast is fine
  and abundant, mostly drunk locally, and local wine sells at half the normal price.
- **lex:Bastonne#Geography, #The People [Knights of the Grail ch. VI pp. 54-57]**: bounded north and east by the
  Grismerie and south by the Gilleau; the west is mainly arable, the east pastoral; the Massif Orcal spills over
  from Quenelles and west of it much of the Forest of Chalons lies in Bastonne, nearly uninhabited (logging
  villages rarely last five years); the Black Chasm runs along the northern edge of the Massif and stops the
  Massif's Orcs raiding the heart of the dukedom; mountain villages are cut off under their own baron. The page
  also says two neighbouring dukedoms are short of land that is not forest or mountain, and that Montfort has
  virtually no land outside the Grey Mountains.
- **lex:Parravon#lead, #People [Knights of the Grail ch. VI pp. 85-97; Bretonnia 5e p. 7]**: much of the duchy
  is forest or mountain; most people live in the fertile Parravon Vale; the southern border with Athel Loren is a
  line of ancient trees; the Parravonese are reluctant to fell trees.

### 1.2 Real-world analogue: France c. 1800-1850 (sources read)

- **rw:France, crops by region [EB1911 "France", en.wikisource.org/wiki/1911_Encyclopaedia_Britannica/France]**:
  about 94% of the country counted cultivable; forest about 18%; cereals about a third of the cultivated area.
  Wheat: French Flanders, the Seine basin (Beauce, Brie), the lower Loire and upper Garonne. Rye: the poor land of
  the Central Plateau and western Brittany. Buckwheat: Brittany. Vines everywhere except the extreme north,
  Normandy and Brittany; main regions the Mediterranean fringe, Gironde, lower Loire, Rhone valley, Burgundy,
  Champagne, Charente. Cider apples north-west of a Paris to Loire-mouth line. Horses bred in great numbers in
  Normandy, Perche, the Cotentin and maritime Flanders; northern Brittany a dairy and horse district; Cantal and
  Aubrac cattle on the Central Plateau.
- **rw:France, wheat area [NBER series via FRED, fred.stlouisfed.org/data/A0133BFRA563NNBR]**: wheat acreage
  4.59 million ha in 1815, 5.29 million in 1836, 5.53 million in 1840, 5.95 million in 1850 (about 10% of the
  national territory under wheat alone at the Victoria 3 start date).
- **rw:France, rotation and fallow [en.wikipedia.org/wiki/Economic_history_of_France; sites.ohio.edu/chastain/ip/peaf.htm]**:
  three-field rotation in the north, two-field in the south, so a third to a half of the arable lay fallow each
  year; grain was sown even on the poorest soils; outside favoured districts farming was subsistence polyculture;
  commons, forest grazing and gleaning carried the poor; 26.8 of 35.4 million French were rural in 1846.
- **rw:Normandy [en.wikipedia.org/wiki/Normandy]**: cattle and dairy the leading sector, cider not wine,
  horse-breeding with two national studs, bocage of small hedged fields in the west, only 12.8% wooded.
- **rw:Bocage [en.wikipedia.org/wiki/Bocage]**: hedged mixed woodland-and-pasture country in Normandy, Brittany
  and the west; pastoral farming dominant; dispersed hamlets.
- **rw:Brittany [EB1911 France]**: rye and buckwheat on poor soil in the west; dairy and horses in the north.
- **rw:Bordeaux [en.wikipedia.org/wiki/History_of_Bordeaux_wine]**: Dutch engineers drained the Medoc marshes in
  the 1600s and vines were planted on them; the vineyard was organised into named districts by 1725; the 1855
  classification ranked the Medoc estates. Export trade to England and the Low Countries.
- **rw:Landes of Gascony [en.wikipedia.org/wiki/Landes_of_Gascony]**: before the 1857 drainage law a bare,
  waterlogged, malarial moor; rye and millet on tiny plots, sheep kept mainly for manure, shepherds on stilts.
- **rw:Sologne [en.wikipedia.org/wiki/Sologne]**: about 5,000 km2 of ill-drained sand and clay with pools and
  marsh; reclaimed and planted with pine under Napoleon III in the mid 1800s.
- **rw:Massif Central [en.wikipedia.org/wiki/Massif_Central]**: about 15% of mainland France; stock-raising
  dominates the uplands (cattle in the west, sheep on the southern limestone plateaus), cereals only in the
  Limagne plain.
- **rw:Alps [en.wikipedia.org/wiki/Alpine_transhumance]**: alpine pasture is 35% of Swiss farmland and 13% of
  the country; cattle the main activity on the Alpine edge from about 1300; grain and hay only on valley floors.
- **rw:Scottish Highlands [en.wikipedia.org/wiki/Scottish_Highlands]**: one estimate puts cultivable land at
  about 9%; black cattle sold south and oatmeal bought in; potatoes the crofting staple by the 1840s.
- **rw:Ireland [en.wikipedia.org/wiki/Agriculture_in_Ireland]**: in 1845 potatoes covered a little under a third
  of the tilled acreage (over 2 million acres); livestock and up to a quarter of the grain were exported;
  today 50.7% permanent pasture against 15.4% arable.

### 1.3 Vanilla's own numbers for the analogue states (read from the install; px from `mapgen/derived/vanilla_arable_states.csv`)

| vanilla state | class in `vanilla_state_climate_classes.csv` | arable | px | arable per 1,000 px | subsistence | crops |
|---|---|---|---|---|---|---|
| STATE_NORMANDY | temperate_river_plain | 120 | 2452 | 48.9 | farm | wheat, livestock, vineyard |
| STATE_PICARDY | temperate_river_plain | 80 | 1588 | 50.4 | farm | wheat, livestock |
| STATE_ILE_DE_FRANCE | temperate_river_plain | 40 | 971 | 41.2 | farm | wheat, livestock, vineyard |
| STATE_MAINE_ANJOU | temperate_river_plain | 112 | 1964 | 57.0 | farm | wheat, livestock, vineyard |
| STATE_ORLEANS | temperate_river_plain | 70 | 2713 | 25.8 | farm | wheat, livestock, vineyard |
| STATE_BURGUNDY | temperate_river_plain | 80 | 2642 | 30.3 | farm | wheat, livestock, vineyard |
| STATE_BRITTANY | temperate_forest_hill | 120 | 2940 | 40.8 | farm | wheat, livestock, vineyard |
| STATE_POITOU | temperate_forest_hill | 90 | 2491 | 36.1 | farm | wheat, livestock, vineyard |
| STATE_AQUITAINE | temperate_forest_hill | 90 | 2683 | 33.5 | farm | wheat, livestock, vineyard |
| STATE_GUYENNE | temperate_forest_hill | 90 | 2491 | 36.1 | farm | wheat, livestock, vineyard |
| STATE_FRANCHE_COMTE | temperate_forest_hill | 50 | 1314 | 38.1 | farm | wheat, livestock, vineyard |
| STATE_LORRAINE | temperate_forest_hill | 55 | 1405 | 39.1 | farm | wheat, livestock, vineyard |
| STATE_WALLONIA (Ardennes) | temperate_forest_hill | 55 | 1453 | 37.9 | farm | wheat, livestock |
| STATE_SAVOY | highland_alpine | 20 | 802 | 24.9 | farm | wheat, livestock, cotton, vineyard |
| STATE_WEST_SWITZERLAND | highland_alpine | 50 | 1329 | 37.6 | farm | rye, livestock, vineyard |
| STATE_EAST_SWITZERLAND | highland_alpine | 40 | 1804 | 22.2 | farm | rye, livestock, vineyard |
| STATE_TYROL | highland_alpine | 30 | 1779 | 16.9 | farm | wheat, livestock, vineyard |
| STATE_WALES | temperate_forest_hill | 40 | 1907 | 21.0 | farm | rye, livestock |
| STATE_HIGHLANDS | temperate_forest_hill | 30 | 5346 | 5.6 | farm | rye, livestock |
| STATE_CONNAUGHT | temperate_forest_hill | 75 | 1794 | 41.8 | farm | rye, livestock |
| STATE_ICELAND | arctic_boreal_coast | 5 | 16772 | 0.3 | fishing village | rye, livestock |

France in vanilla is far denser than the world-block class densities the model uses (26.15 river plain, 15.51
forest-hill), so the model will give Bretonnia less arable per pixel than vanilla gives France whatever class is
chosen. That is a property of the approved model (world parity), not something a row should fight; the rows
below only rank the states against each other.

## 2. Per-state entries (file order)

Passable area is the state's province pixels minus impassable provinces (canvas px, from `provinces_index.json`).
"Layer" is `mapgen/derived/state_climate_index.json`.

### STATE_L_ANGUILLE - "L'Anguille" (owner LAN; 17 provinces, 4,387 px, coastal)

- **Identity**: the Dukedom of L'Anguille, whole. Hubs: L'Anguille city, Grasgar Castle (canon, KotG). Certain.
- **Canon**: most of the dukedom is arable and inland L'Anguille almost entirely so; fertile soil, mild weather
  because the sea-cliffs take the storms, harvests through most of the year; villages keep thin woodland strips
  for timber and pig forage; the southern reach is Forest of Arden; the coast is short, cliff-bound and nearly
  unsettled outside the city; townsfolk are sailors, fishermen and traders, country folk farmers (turnips are
  named); the city stands at the mouth of the Sannez. lex:L'Anguille#Geography and fandom:L'Anguille#Geography,
  #Inhabitants [Knights of the Grail pp. 41-46 (Fandom) / 43-46 (Lexicanum)]. Both wikis agree.
- **Analogue**: Normandy's Pays de Caux and the Caen plain: chalk cliffs, loam plateau, wheat, no vines
  (rw:France EB1911: no vines in Normandy). vanilla:STATE_NORMANDY arable 120, farm, wheat/livestock/vineyard
  (48.9 per 1,000 px); vanilla:STATE_PICARDY arable 80, wheat/livestock.
- **Layer**: Cfb 98.5% -> temperate_forest_hill (unscaled default about 68).
- **Proposal**: `temperate_river_plain`, step **+1**, `building_subsistence_farm`, crops `wheat_farm
  livestock_ranch`. The canon text is the strongest arable statement in the realm (nearly all arable, fertile,
  near year-round harvest) and names a river mouth, so the class moves to river plain and one step up
  (unscaled about 172; vanilla Normandy on the same area would be about 215). Wheat first because the canon
  countryside is grain and root crops; no vineyard because neither canon nor the analogue puts vines on this
  coast. **Tier A.**

### STATE_COURONNE - "Couronne" (owner COU; 21 provinces, 5,407 px, coastal)

- **Identity**: Couronne proper (north of the Sannez, the cape on the Sea of Chaos). The Marches are a separate
  state outside this file. Hubs: Couronne city (canon). Certain.
- **Canon**: Couronne proper is mostly arable, with pastoral land in the south and east where it nears the Pale
  Sisters and Grey Mountains; a rugged, storm-lashed, raided coast with stockaded villages; horse-breeding is so
  general that most peasants have the use of a horse; the Sannez (narrow, deep, swift) runs through to
  L'Anguille. lex:Couronne#Geography, #The People and fandom:Couronne#Geography, #The Couronnians [Knights of
  the Grail pp. 67-70]; lex:Bretonnia#Rivers [Knights of the Grail p. 9]. Both wikis agree.
- **Analogue**: Normandy (Perche and the Cotentin: the horse country of France, rw:France EB1911; cattle and
  horse-breeding with two national studs, rw:Normandy) and Picardy grain. vanilla:STATE_NORMANDY arable 120,
  farm, wheat/livestock/vineyard; vanilla:STATE_PICARDY arable 80, wheat/livestock.
- **Layer**: Cfb 59%, Df 36%, Dc 5% -> temperate_forest_hill (unscaled about 84).
- **Proposal**: `temperate_river_plain`, step **0**, `building_subsistence_farm`, crops `wheat_farm
  livestock_ranch`. "Mostly arable" on a named river supports the plain class; the pastoral south-east and the
  storm coast argue against a step up (unscaled about 141). Ranch second carries the horses. No vineyard
  (analogue north of the vine line, canon silent). **Tier A.**

### STATE_PALE_SISTERS - "Pale Sisters" (owner SKZ, greenskins; 5 provinces, 3,268 px of which 2,550 impassable; landlocked)

- **Identity**: the Pale Sisters range between Couronne and Gisoreux. The name is canon; the hubs (Garban Hold,
  Grung Zint) are TWW3 region-table names, not canon evidence. Range identity certain; the owner and hubs are the
  mod's.
- **Canon**: a northern spur of the Grey Mountains, largely barren, home to brigands and a few Goblins; white
  rock, rounded peaks, cliffs and many high valleys that are hard to reach; still, more Gisorens live here than
  in the Grey Mountains. fandom:Pale Sisters#lead [WFRP 1e Core pp. 274-275; Knights of the Grail p. 71; Arcane
  Journal: Kingdom of Bretonnia p. 7]. The land where Couronne nears the range is pastoral (lex:Couronne#Geography
  [KotG pp. 67-70]). One valley, the Valle Florida, is a warm sun-trap where vineyards flourish
  (fandom:Gisoreux#Valle Florida [KotG pp. 70-73]); whether it falls in this state or in Gisoreux is not
  determinable from the map (see open questions). Not corroborated on Lexicanum (blocked).
- **Analogue**: Vosges and Jura mid-mountain: summer pasture, little arable. vanilla:STATE_FRANCHE_COMTE arable
  50 (38 per 1,000 px), vanilla:STATE_EAST_SWITZERLAND arable 40, rye/livestock/vineyard.
- **Layer**: Dc 56%, Df 43% -> boreal_forest (2.12 per 1,000 px; unscaled about 1.5 on 718 passable px).
- **Proposal**: `highland_alpine`, step **-1**, `building_subsistence_pasture`, crops `livestock_ranch`.
  Mountain terrain at a temperate latitude is highland, not boreal taiga; "largely barren" earns the step down
  (unscaled about 2.5). Pasture follows the standing greenskin ruling and the canon pastoral fringe. **Tier A.**

### STATE_GISOREUX - "Gisoreux" (owner GIS; 13 provinces, 3,684 px of which 589 impassable; river port)

- **Identity**: the Dukedom of Gisoreux west of the mountains: the Plains of Gisoreux (city hub at 3886,840),
  North Gisoreux (Oisillon hub at 3844,779; canon puts Oisillon about 100 miles north of the capital) and the
  dukedom's share of the Forest of Arden. Certain.
- **Canon**: four regions. The Plains of Gisoreux are in fact mostly pastoral and very hilly and hold just over
  half the people; North Gisoreux, between the Sannez and the Pale Sisters, is also mostly pastoral with
  substantial arable along the Sannez, on land cleared from the Forest of Arden over a thousand years; the forest
  south and east of the river has stockaded villages, north of it no village survives a year; the fourth region
  is mountain. The lead adds "arable plains to the south" worked by ordinary peasant farmers, trappers and
  woodsmen in the east. Vineyards flourish in the Valle Florida. fandom:Gisoreux#lead, #Geography, #Valle Florida
  [Knights of the Grail pp. 70-73]. Lexicanum page blocked (HTTP 403); lex:Bastonne#The People [KotG pp. 54-57]
  says two of Bastonne's neighbours are short of land that is neither forest nor mountain.
- **Analogue**: the bocage of lower Normandy and Maine, hedged pasture with grain in the valleys
  (rw:Bocage; rw:Normandy), shading into the Ardennes. vanilla:STATE_BRITTANY arable 120 (40.8 per 1,000 px,
  temperate_forest_hill), vanilla:STATE_WALLONIA arable 55, wheat/livestock.
- **Layer**: Cfb 88%, Df 12% -> temperate_forest_hill (unscaled about 48 on 3,095 passable px). Agrees.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_farm`, crops `livestock_ranch
  wheat_farm vineyard`. Canon calls both settled regions mostly pastoral, so the ranch leads; wheat for the Sannez
  and southern strips; vineyard for the Valle Florida. Subsistence stays farm: vanilla keeps pasture for arid,
  steppe and tundra states and uses farm for every hedged-pasture state of western Europe (#3676 section 6).
  **Tier A.**

### STATE_BASTONNE - "Bastonne" (owner BAS; 12 provinces, 3,249 px; river port)

- **Identity**: western and central Bastonne (Castle Bastonne at 3888,886; Humble Chapel hub is canon). The
  eastern, Massif-side part of the dukedom is STATE_CASTLE_SANGASSE. Certain.
- **Canon**: bounded north and east by the Grismerie and south by the Gilleau; the west mainly arable, the east
  pastoral; much of the Forest of Chalons lies in the dukedom west of the Massif Orcal and is nearly empty of
  people (logging villages rarely last five years; Undead and Beastmen raid north out of it); the Black Chasm
  shuts the Massif's Orcs out of the heartland. lex:Bastonne#Geography [KotG pp. 54-57] and
  fandom:Bastonne#Geography [KotG pp. 16, 54-56]. Both wikis agree.
- **Analogue**: the middle Loire and Poitou: mixed wheat and vine country with large forests (rw:France EB1911:
  wheat on the lower Loire, vines on the lower Loire). vanilla:STATE_POITOU arable 90 (36.1 per 1,000 px),
  vanilla:STATE_ORLEANS arable 70 (25.8), both wheat/livestock/vineyard.
- **Layer**: Cfb 96% -> temperate_forest_hill (unscaled about 50). Agrees.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_farm`, crops `wheat_farm
  livestock_ranch vineyard`. Arable west and an unpeopled forest south cancel out; no step. Crops are the realm
  set (wheat dominant, vines on slopes: lex:Bretonnia#Farming [KotG p. 6]). **Tier A.**

### STATE_MONTFORT - "Montfort" (owner MNF; 4 provinces, 1,205 px; river port)

- **Identity**: the Bretonnian foot of the Dukedom of Montfort (Tharravil is a canon settlement). Certain.
- **Canon**: the dukedom lies almost wholly inside the Grey Mountains; within Bretonnia it has only a narrow
  strip of pastoral land; farmland is scarce and not especially fertile; it barely feeds itself in a good year
  and imports food after any bad harvest, which greenskin raids make common; every mountain community depends on
  food brought in by traders; income is the Axe Bite Pass tolls and iron mining; flat land is kept for crops and
  stock, houses go on the slopes. fandom:Montfort#lead, #Geography, #The Montfortians [Knights of the Grail
  pp. 78-79]. lex:Bastonne#The People [KotG pp. 54-57] agrees (virtually no land outside the Grey Mountains).
  Lexicanum's own Montfort page was blocked.
- **Analogue**: Savoy and the Vosges valleys. vanilla:STATE_SAVOY arable 20 (24.9 per 1,000 px, highland_alpine),
  vanilla:STATE_TYROL arable 30 (16.9).
- **Layer**: Df 94% -> temperate_forest_hill (unscaled about 19).
- **Proposal**: `highland_alpine`, step **0**, `building_subsistence_farm`, crops `livestock_ranch wheat_farm`.
  A food-importing mountain dukedom is typical highland land, so the class carries the penalty and no further
  step is needed (unscaled about 6). Ranch first for the pastoral strip; no vineyard. **Tier A.**

### STATE_CROOKED_CORRIDOR - "Crooked Corridor" (owner KZF, Karak Ziflin; 4 provinces, 2,145 px of which 1,740 impassable; landlocked)

- **Identity**: the Crooked Corridor pass in the Grey Mountains with Karak Ziflin and Blackstone Tower. All three
  are canon names. Certain.
- **Canon**: a smugglers' pass, shut by snow all winter, long known only to smugglers and goatherds; Blackstone
  Tower guards it and has been ceded to Karak Ziflin. fandom:Montfort#Crooked Corridor [WFRP 4e Core p. 284].
  Karak Ziflin is the smallest Grey Dwarf hold, windswept, trading by two roads to Axe Bite Pass; its outlying
  mine Grung Ardzufak (about 300 dwarfs) supplies the hold with metalwork and grain.
  fandom:Karak Ziflin#lead, #Subsidiary Settlements [Lords of Stone and Steel pp. 19, 24]. Not corroborated on
  Lexicanum.
- **Analogue**: high Alpine pass country. vanilla:STATE_TYROL arable 30, farm; rw:Alps (pasture above, grain
  only on valley floors).
- **Layer**: Df 73%, Dc 27% -> temperate_forest_hill (unscaled about 6 on 405 passable px).
- **Proposal**: `highland_alpine`, step **0**, `building_subsistence_pasture`, crops `livestock_ranch`.
  Standing ruling (dwarf holds herd) and the canon goatherds agree. Canon does name one grain-supplying
  outpost, which is not enough to make Ziflin a grain hold; flagged in open questions. **Tier A.**

### STATE_OIS_GAP - "Ois Gap" (owner GIS; 2 provinces, 487 px of which 235 impassable; landlocked)

- **Identity**: the Ois (Gisoreux) Gap between the Pale Sisters and the Grey Mountains, with Fort Bergbres.
  Canon names (WFRP 1e). Certain.
- **Canon**: Fort Bergbres sits mid-gap at the bridge over the Ois, population 225, a customs post and supply
  station for the crossing of the Bitter Moors; the Ois rises in the Grey Mountains and Pale Sisters and runs
  through the gap; the northern tip of the Grey Mountains sinks here into hills, the main road between
  Bretonnia and the Empire. fandom:Fort Bergbres [Marienburg: Sold Down the River p. 10]; fandom:River Ois
  [WFRP 1e Core p. 274]; fandom:Grey Mountains#Geography [Sigmar's Heir p. 5]. **No canon land-use text found**
  for the gap itself; dukedom-level text says Gisoreux's hill country is pastoral
  (fandom:Gisoreux#Geography [KotG pp. 70-73]).
- **Analogue**: the Belfort Gap / Saverne col: a hill saddle, road and garrison economy.
  vanilla:STATE_FRANCHE_COMTE arable 50.
- **Layer**: Dc 93% -> boreal_forest (unscaled about 0.5 on 252 passable px).
- **Proposal**: `highland_alpine`, step **0**, `building_subsistence_farm`, crops `livestock_ranch rye_farm`.
  Hill-pass terrain, not taiga; pastoral by the dukedom text; rye as the cold-upland grain (rw:France EB1911:
  rye on the poor uplands). Tiny either way (about 1). **Tier B.**

### STATE_PARRAVON - "Parravon" (owner PAR; 5 provinces, 1,240 px of which 212 impassable; river port)

- **Identity**: the Dukedom of Parravon: the city (hub at 4002,923) and Parravon Vale at the head of the
  Grismerie. Certain.
- **Canon**: like Gisoreux and Montfort the dukedom sits almost wholly on mountain, the little flat land going
  to farming; most of it is mountain or the north-eastern Forest of Loren; forest villages live by herding pigs,
  gathering and minimal farming; most of the people are in Parravon Vale, a fertile valley whose rim is pastoral
  and whose centre, running down to the Grismerie, is arable; the Grey Mountains are less jagged here, so more
  people can live and farm in them than further north; the Parravonese log the Loren sparingly.
  fandom:Parravon#lead, #Geography [Knights of the Grail pp. 85-86]; lex:Parravon#lead, #People [KotG pp. 85-97
  as Lexicanum numbers it; Bretonnia 5e p. 7]. Both wikis agree. The Grismerie rises near Parravon
  (lex:Bretonnia#Rivers [KotG p. 9]).
- **Analogue**: an Alpine fore-valley such as the Gresivaudan or the Valais floor. vanilla:STATE_WEST_SWITZERLAND
  arable 50 (37.6 per 1,000 px), farm, rye/livestock/vineyard; vanilla:STATE_SAVOY arable 20 (24.9).
- **Layer**: Df 98% -> temperate_forest_hill (unscaled about 16 on 1,028 passable px).
- **Proposal**: `highland_alpine`, step **+1**, `building_subsistence_farm`, crops `wheat_farm livestock_ranch
  vineyard`. A mountain dukedom, but one whose people sit in a valley canon calls fertile and arable, and whose
  slopes canon calls more farmable than Montfort's: highland stepped up once (unscaled about 8, against 6 for
  the larger Montfort). Wheat first for the arable valley floor; vineyard on the realm rule (vines on steep
  land, lex:Bretonnia#Farming [KotG p. 6]) and the Swiss analogue. **Tier A.**

### STATE_NORTH_GREY_MOUNTAINS - "North Grey Mountains" (owner KNO; 5 provinces, 2,110 px of which 1,686 impassable; landlocked)

- **Identity**: the Grey Mountains east of Parravon with Karak Azgaraz as city hub (4066,932); Blood Keep is a
  second hub. Canon places Azgaraz in Eyrie Peak, two days from Grey Lady Pass and four days north of Parravon,
  which fits. The owner is Karak Norn because Azgaraz's own tag is dormant. Identity certain.
- **Canon**: Azgaraz's herders bring mountain cattle down to graze in the warm months; fortified farms grow
  mountain hops and barley for the brewers and wheat for bread, with turnips, beans, parsnips and mustard;
  lakeside farms at Copper Tarn grow hops and a hardy wheat milled inside the hold; goat-herders work the upper
  mountain; three outposts supply grain (one also cheese); the hold exports ale, metalwork and furs through
  Ubersreik. fandom:Karak Azgaraz#Society [Archives of the Empire I p. 69], #Surface Features and #The Mountain
  Top [WFRP 3e Book of Grudges pp. 16-29], #Subsidiary Settlements. Not corroborated on Lexicanum.
- **Analogue**: Tyrol: valley-floor grain under high pasture. vanilla:STATE_TYROL arable 30, farm,
  wheat/livestock/vineyard.
- **Layer**: Df 73%, Dc 27% -> temperate_forest_hill (unscaled about 7 on 424 passable px).
- **Proposal**: `highland_alpine`, step **0**, `building_subsistence_farm`, crops `wheat_farm livestock_ranch`.
  The standing ruling names Karak Azgaraz a grain hold and the dump bears it out: wheat, barley and hops are
  grown at the hold itself. Farm, wheat first. **Tier A.**

### STATE_ANMYR - "Anmyr" (owner ANM; 7 provinces, 1,786 px of which 399 impassable; landlocked)

- **Identity**: Anmyr, the Witherhold, a High Realm of Athel Loren (canon name; the hub "Halls of Anaereth" is a
  TWW3 name with no article in the dump). Realm identity certain; its exact extent is the mod's.
- **Canon**: a realm in decline: the blood of Morghur poisoned the land for leagues, whole groves wither each
  year, and the ground under the dead elm Addaivoch is barren and lifeless. fandom:Anmyr [Wood Elves 8e p. 12].
  Realm level: the Asrai hunt the forest's animals for food and clothing and waste nothing
  (fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]); their feasts are woodland game and Elven wine
  (fandom:Wood Elves#Government [Wood Elves 8e p. 9]). **No canon text has the Wood Elves ploughing or keeping
  fields.** A dump article (Wine) says land in the glades is set aside for grapes, but it cites Total War, so it
  is a lead, not evidence. Not corroborated on Lexicanum.
- **Analogue**: none farmed. The nearest real case is a royal hunting forest (Fontainebleau, the New Forest):
  game and wood, no plough. Vanilla has no unfarmed temperate state to quote.
- **Layer**: Cfb 59%, Df 41% -> temperate_forest_hill (unscaled about 22 on 1,387 passable px).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  A forest whose people live by the hunt and do not clear it is the floor of its class, and this realm is
  blighted besides. Pasture is chosen for its basket (meat and fabric, the "food and clothing" of the canon
  line), not for herding; see open question 1. **Tier A** for the blight, B for the subsistence call.

### STATE_MASSIF_ORCAL - "Massif Orcal" (owner MOR, greenskins; 11 provinces, 5,248 px of which 2,735 impassable; landlocked)

- **Identity**: the Massif Orcal in the heart of Bretonnia; hubs Black Chasm and Barrows of Cuileux are canon
  places (the second belongs to Quenelles lore), Orquemont is a TWW3 name. Certain.
- **Canon**: a rocky highland of sheer cliffs above the Forest of Chalons, held by Orcs and Goblins left over
  from the hordes driven out at the kingdom's founding; barren and desolate, thin soil, sickly pines and
  brambles, no game, no minerals, no fertile land, shunned by Bretonnians. fandom:Massif Orcal [White Dwarf 249
  p. 19; the "barren" passage is cited to the novel Blood of the Dragon]. Knights of the Grail is milder: low,
  rounded, cave-riddled mountains full of greenskins, the source of the Gilleau; few humans live there and most
  villages are sacked within years, though a few fortified ones (Viefin) survive; northern Quenelles around it
  is pastoral. fandom:Quenelles#Geography [KotG pp. 88-90]; lex:Bastonne#Geography [KotG pp. 54-57] (mountain
  villages cut off by the Black Chasm). Not corroborated on Lexicanum's own Massif Orcal page (blocked).
- **Analogue**: the Massif Central's poorest uplands (Margeride, Causses): rye patches and stock, emigration
  country (rw:Massif Central; rw:France EB1911: rye on the Central Plateau). Vanilla has no separate Auvergne
  state; vanilla:STATE_TYROL arable 30 (16.9 per 1,000 px) is the nearest highland number.
- **Layer**: Df 51%, Dc 43%, Cfb 6% -> temperate_forest_hill (unscaled about 39 on 2,513 passable px).
- **Proposal**: `highland_alpine`, step **-1**, `building_subsistence_pasture`, crops `livestock_ranch`.
  Highland by terrain; one step down for the repeated canon statement that nothing fertile is there (unscaled
  about 9; today's stand-in value is 103). Pasture by the standing greenskin ruling. I stop at -1, not -2,
  because the harshest wording comes from a novel and the RPG book has humans holding villages there.
  **Tier A.**

### STATE_BORDELEAUX - "Bordeleaux" (owner BOR; 13 provinces, 3,396 px; coastal)

- **Identity**: the Dukedom of Bordeleaux (city, Turris Vigilans and Raisol are canon names). Certain.
- **Canon**: the kingdom's largest wine exporter, a land of farms and vineyards; mostly arable and well suited to
  cereals and vines, with less fertile grazing near the coast; high cliffs, over a dozen natural harbours and
  more fishing villages; the south-east corner is Forest of Chalons with villages that do thrive; the city's
  trade rests almost wholly on wine from the Morceaux Valley; local wine is abundant, mostly drunk at home and
  sells at half the usual price. fandom:Bordeleaux#lead, #Bordelaux City, #The Bordelens [Knights of the Grail
  pp. 58-59; WFRP 1e Core p. 275]; lex:Bordeleaux#lead, #Geography [KotG ch. VI; Sea of Claws p. 82]. Both
  wikis agree on the text; Lexicanum's page range (54-57) duplicates Bastonne's, so I follow Fandom's 58-59.
  The Gilleau reaches the sea at Bordeleaux (lex:Bretonnia#Rivers [KotG p. 9]).
- **Analogue**: the Bordelais (rw:Bordeaux: Medoc drained and planted in the 1600s, districts fixed by 1725,
  the 1855 classification; rw:France EB1911: Gironde among the chief vine regions). vanilla:STATE_GUYENNE arable
  90 (36.1 per 1,000 px), farm, wheat/livestock/vineyard; vanilla:STATE_AQUITAINE arable 90.
- **Layer**: Cfb 100% -> temperate_forest_hill (unscaled about 53).
- **Proposal**: `temperate_river_plain`, step **0**, `building_subsistence_farm`, crops `vineyard wheat_farm
  livestock_ranch`. Mostly arable land on two river mouths earns the plain class (unscaled about 89). Vineyard
  is first on purpose: in a large state the first building takes most of the starting farm budget, and canon
  makes wine this dukedom's export. Vanilla lists wheat first for Guyenne; canon outranks it here. **Tier A.**

### STATE_MOUSILLON - "Mousillon" (owner LYO, Lyonesse; 12 provinces, 3,384 px; coastal)

- **Identity**: despite the name this is **not** the cursed swamp. The owner is Lyonesse and the state lies
  west of STATE_CASTLE_MOUSILLON, so it is the former Mousillon land Lyonesse annexed: the southern half of the
  present dukedom of Lyonesse. Sigmarsheim (farm hub) is canon as an Imperial outpost in the Forest of Arden
  inside Lyonesse; Martel and Portsall are TWW3 names. Identity by owner and position: confident, but inferred.
- **Canon**: Lyonesse took most of Mousillon's land, its most fertile part, after Duke Merovech's crime (1814 IC
  in Knights of the Grail; Lexicanum says "the 1900s IC"). Southern Lyonesse is mainly arable, crossed by dozens
  of small rivers that widen into lakes with fortified islands; near the Mousillon border the lakes spread and
  a few areas turn marshy, but the true marshes only begin inside the cursed dukedom; a tongue of the Forest of
  Arden reaches in, its lake islands holding small villages. fandom:Lyonesse#Geography [Knights of the Grail
  pp. 74-76]; fandom:Mousillon#Geography [KotG pp. 81-83]; lex:Mousillon#lead [Barony of the Damned pp. 11-12];
  lex:Lyonesse#Geography [KotG pp. 74-77].
- **Analogue**: the lower Loire and the Breton marches (Pays de Retz, Brenne lake country): wet arable lowland.
  vanilla:STATE_MAINE_ANJOU arable 112 (57 per 1,000 px, temperate_river_plain), farm, wheat/livestock/vineyard.
- **Layer**: Cfb 100% -> temperate_forest_hill (unscaled about 52).
- **Proposal**: `temperate_river_plain`, step **0**, `building_subsistence_farm`, crops `wheat_farm
  livestock_ranch`. Mainly arable lake-and-river lowland, the good half of old Mousillon (unscaled about 88).
  The earlier draft (BRE-02) stepped this state down twice as "Mousillon"; that was a naming error and I reverse
  it. No vineyard: canon names none and the Breton analogue is north of the vine. **Tier B** (canon text is
  explicit, the state-to-region match is by owner and position).

### STATE_ARTOIS - "Artois" (owners ART, and OKP for 2 of 13 provinces; 3,516 px of which 349 impassable; landlocked)

- **Identity**: the Dukedom of Artois with the Forest of Arden; Larret and Castle Artois are canon. The two OKP
  provinces are the mod's Oak of Prophecy glade; canon puts the Oak at the Guerac Circle, which both wikis file
  under Mousillon (lex:Mousillon#Locations [Knights of the Grail p. 83]). Certain for the dukedom.
- **Canon**: the only dukedom given over to forest: all but a small western strip lies inside the Forest of
  Arden; the land outside is mostly arable and holds most of the people; forest villages are stockaded and keep
  animals instead of crops because stock can be driven inside when Beastmen come, which is at least yearly;
  woodsmen and charcoal burners; ruined villages across the east. fandom:Artois#lead [Knights of the Grail
  pp. 51-52]; lex:Artois#Geography [KotG pp. 51-53]. The forest itself is a huge oak wood with many marshes and
  lakes and oversized Beastmen (fandom:Forest of Arden [White Dwarf 310 pp. 111-112; Beastmen 7e pp. 20-21]).
  Both wikis agree.
- **Analogue**: the Ardennes: forest, poor soil, stock and charcoal (the name is the borrowing).
  vanilla:STATE_WALLONIA arable 55 (37.9 per 1,000 px), farm, wheat/livestock.
- **Layer**: Cfb 100% -> temperate_forest_hill (unscaled about 49 on 3,167 passable px). Agrees on class.
- **Proposal**: `temperate_forest_hill`, step **-1**, `building_subsistence_farm`, crops `livestock_ranch
  wheat_farm`. The class already assumes a wooded country; a dukedom that is nearly all forest with villages
  that cannot keep crops sits one step below it (unscaled about 33). Ranch first for the forest stock-raisers,
  wheat for the western strip. **Tier A.**

### STATE_LYONESSE - "Lyonesse" (owner LYO; 12 provinces, 3,186 px; coastal)

- **Identity**: the old lands of Lyonesse around the capital (Castle Lyonesse hub at 3690,759) and the island
  coast. Certain.
- **Canon**: one of the largest dukedoms; a rugged coast with a great many small islands whose harbours are
  better than the mainland's, so most coastal villages are on the islands (the isles are called barren, Landri
  the one that supports a fair population); inland both halves of the dukedom are mainly arable; the northern,
  original half is dotted with mottes, round flat-topped hills under a hundred feet with caves and underground
  rivers, each now castled. Repanse de Lyonesse was a shepherdess. fandom:Lyonesse#Geography, #Siege of
  Lyonesse [Knights of the Grail pp. 74-76; the island passage is from the novel Knight of the Realm];
  lex:Lyonesse#Geography [KotG pp. 74-77]. Both wikis agree.
- **Analogue**: Brittany's north coast (islands, rias, mixed grain and stock; no vines; dairy and horses in the
  north: rw:France EB1911). vanilla:STATE_BRITTANY arable 120 (40.8 per 1,000 px, temperate_forest_hill), farm.
- **Layer**: Cfb 100% -> temperate_forest_hill (unscaled about 49). Agrees on class.
- **Proposal**: `temperate_forest_hill`, step **+1**, `building_subsistence_farm`, crops `wheat_farm
  livestock_ranch`. "Mainly arable" is more than the class's typical wooded hill country, and vanilla Brittany
  is the densest forest-hill state in France, so one step up (unscaled about 74). Farm, not fishing village:
  the island villages are a coastal fringe and canon does not say the dukedom lives by the sea. No vineyard
  (analogue). **Tier A.**

### STATE_LAND_078 - "Land 078" (unowned; 9 provinces, 2,246 px; coastal) - Albion, south

- **Identity**: the southern Albion state with its islet (centroid 3336,751; `in_scope_additions.json` joins the
  islet at 3338,782 to the south state). Unnamed. Identity as "south Albion" is certain; canon gives no
  north/centre/south division, so nothing ties particular canon places to it.
- **Canon** (island level): Albion was once sunny cropland; the stone circles drew rain and storm and the
  fertile land became bog where few crops grow, the soil itself tainted and fields turned to quagmire; constant
  gales and rain leave the ground infertile to all but the hardiest plants; fens, marshes and moors crossed by
  log causeways; settlements are rare, often stilt villages on lake islands or marsh; the coastal tribes build
  the larger towns; chieftains rear cattle (and would rather raid); a fishing village (Ohbuhu) is named.
  fandom:Albion#Origins [Shadows Over Albion p. 6], #Religion [Archives of the Empire III pp. 57-58],
  #Geography [Town Cryer 15 pp. 4-6], #Society, #Humans, #Notable Locations [White Dwarf 259-260]. The article's
  "Isles of Albion" section (seaweed-manured wheat, hill sheep; White Dwarf 137, the novel Storm Warriors) is
  marked by the wiki as retconned, so I do not use it. Not corroborated on Lexicanum.
- **Analogue**: the Scottish Highlands and western Ireland about 1800-1845: roughly 9% cultivable, black cattle
  sold out and meal bought in, potatoes and oats on small plots (rw:Scottish Highlands; rw:Ireland).
  vanilla:STATE_HIGHLANDS arable 30 over 5,346 px (5.6 per 1,000 px), farm, rye/livestock;
  vanilla:STATE_CONNAUGHT arable 75 (41.8 per 1,000 px).
- **Layer**: no entry (the Albion states are newer than `state_climate_index.json`).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch
  rye_farm`. Wet temperate upland at the bottom of its class: 7.0 per 1,000 px after the step, close to
  vanilla's Highlands (5.6). Pasture because canon has cattle and almost no crops; rye stands for the hardy
  northern grain as it does in vanilla Britain. **Tier B.**

### STATE_LAND_079 - "Land 079" (unowned; 55 provinces, 15,614 px; coastal) - Albion, centre

- **Identity**: the central and largest Albion state (centroid 3332,702). Unnamed. Certain as geometry.
- **Canon**: as STATE_LAND_078. One detail bears on the centre: the mists that once hid the coast still lie
  thickest over the middle of the island, where parties blunder into the marshes
  (fandom:Albion#Shadows Gather [White Dwarf 259-260]).
- **Analogue, layer**: as STATE_LAND_078.
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch
  rye_farm`. Same row as the south (unscaled about 109 on this very large state; see open question 5 on
  whether that is still too much for a bog island with rare settlements). **Tier B.**

### STATE_TORGOVANN - "Torgovann" (owner TRG; 5 provinces, 1,462 px; landlocked)

- **Identity**: Torgovann, the Forge of Starlight, a High Realm of Athel Loren, with Vaul's Anvil (both canon).
  Certain.
- **Canon**: the realm of smiths and artisans; beech glades around the forge-temple of Vaul's Anvil.
  fandom:Torgovann [Wood Elves 8e p. 12]. No land-use text of its own. Realm level as under STATE_ANMYR: the
  Asrai hunt for food and clothing and feast on game and wine; nothing has them farming
  (fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27], #Government [8e p. 9]).
- **Analogue**: an unfarmed hunting forest; no vanilla state to quote.
- **Layer**: Df 100% -> temperate_forest_hill (unscaled about 23). Agrees on class.
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The Athel Loren row (see STATE_ANMYR and open question 1). **Tier B.**

### STATE_YI_EDRI_ETERNOS - "Yi Edri Eternos" (owner TLS; 1 province, 241 px; landlocked)

- **Identity**: the Oak of Ages, whose Elven name the dump gives as "Yn Edri Eternos" (the state key drops the
  n). Canon place inside Talsyn. Certain.
- **Canon**: the spiritual heart of Athel Loren, where Ariel winters and spellsingers are taught; no land use.
  fandom:Oak of Ages; fandom:Talsyn [Wood Elves 8e p. 10].
- **Layer**: Df 100% -> temperate_forest_hill (unscaled about 4).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  A sacred grove of one province; the Athel Loren row. **Tier B.**

### STATE_KING_S_GLADE - "King's Glade" (owner TLS; 6 provinces, 1,431 px; landlocked)

- **Identity**: the King's Glade, seat of Ariel and Orion (canon, inside Talsyn). Certain.
- **Canon**: a vast clearing ringed by ancient oaks, with a city woven from living trees above and below
  ground, hidden by magic. fandom:King's Glade; fandom:Talsyn [Wood Elves 8e p. 10]. No land use.
- **Layer**: Df 100% -> temperate_forest_hill (unscaled about 22).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The Athel Loren row. **Tier B.**

### STATE_SOUTH_GREY_MOUNTAINS - "South Grey Mountains" (owner KNO; 5 provinces, 1,643 px of which 1,302 impassable; landlocked)

- **Identity**: the kingdom of Karak Norn above Athel Loren (hub Karak Norn; the mine hub Khazid Grimaz is a
  canon village of the hold). Certain.
- **Canon**: Karak Norn, "Barren Earth Hold", the largest Grey Mountain hold, on a forested, valley-ringed peak
  with the high meadow of Lookout Plateau; its kingdom has small towns, villages, mines and farmsteads along
  four trade roads, and a "Fertile Valley"; the human town of Bergheim (about 3,000) pays grain, cheese and wool
  for its land, Khazid Grimaz (about 2,000) supplies grain, Khazid Thran (about 2,600) specialises in cereals
  and metalwork. fandom:Karak Norn#lead, #Geography, #Subsidiary Settlements [Lords of Stone and Steel
  pp. 24-32; Stone and Steel pp. 36-37]. Race level: the highlands round most holds are barren, a few herders
  keep goats and a few farmers grow stunted barley and wheat inside the walls (fandom:Dwarfs, passage carries no
  footnote). Not corroborated on Lexicanum.
- **Analogue**: Tyrol / Graubunden. vanilla:STATE_TYROL arable 30, vanilla:STATE_EAST_SWITZERLAND arable 40
  (rye/livestock/vineyard), both farm.
- **Layer**: Dc 58%, Df 42% -> boreal_forest (unscaled under 1 on 341 passable px).
- **Proposal**: `highland_alpine`, step **0**, `building_subsistence_farm`, crops `wheat_farm livestock_ranch`.
  **This departs from the standing ruling** (dwarf holds herd, except Izor, Azgaraz and Kraka Drak): the dump
  gives Karak Norn three cereal-growing dependencies and a named fertile valley, at least as much grain evidence
  as Azgaraz has. If Chris keeps the ruling, the row becomes `building_subsistence_pasture`, `livestock_ranch`
  (open question 2). The arable is about 2 either way. **Tier A.**

### STATE_TAL_ESTH - "Tal Esth" (owner WYD; 1 province, 489 px; landlocked)

- **Identity**: uncertain. The only mention of "Tal Esth" in the dump is in End Times text (a ruin), which is
  outside the timeline and tells nothing of land use. By owner it is part of Wydrioth, the Pine Crags.
- **Canon**: none for the place. Wydrioth: steep slopes grown into a living fortress of oak and rockbriar,
  always at war with the dwarfs and greenskins of the Grey Mountains. fandom:Wydrioth [Wood Elves 8e p. 12].
- **Layer**: Df 100% -> temperate_forest_hill (unscaled about 8).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The Athel Loren row. **Tier C.**

### STATE_LYONESSE_HILLS - "Lyonesse Hills" (owner LYO; 8 provinces, 2,307 px; coastal)

- **Identity**: northern Lyonesse, the motte country against L'Anguille. Barley Motte (farm hub) is canon as a
  cursed holding near the L'Anguille border (lex:Lyonesse#Locations [KotG pp. 74-77]); Soleil and Dason are
  TWW3 names. Confident.
- **Canon**: the northern, original lands of Lyonesse are mainly arable and dotted with mottes, steep round
  hills under a hundred feet with level tops, caves and underground rivers, every one now castled.
  fandom:Lyonesse#Geography [Knights of the Grail pp. 74-76]; lex:Lyonesse#Geography [KotG pp. 74-77].
- **Analogue**: northern Brittany and the Cotentin (dairy, horses, grain; no vines: rw:France EB1911).
  vanilla:STATE_BRITTANY arable 120 (40.8 per 1,000 px), farm.
- **Layer**: Cfb 99% -> temperate_forest_hill (unscaled about 36). Agrees on class.
- **Proposal**: `temperate_forest_hill`, step **+1**, `building_subsistence_farm`, crops `wheat_farm
  livestock_ranch`. Same reasoning as STATE_LYONESSE: mainly arable, so one step above typical hill country
  (unscaled about 54). The mottes are small and do not make it upland. **Tier A.**

### STATE_CASTLE_SANGASSE - "Castle Sangasse" (owner BAS; 7 provinces, 1,441 px; river port)

- **Identity**: eastern Bastonne, between Castle Bastonne and Montfort (centroid 3911,868). Castle Sangasse is
  canon as the seat of the Earl of Sangasse in Bastonne, near Garamont (fandom:Castle Sangasse [Knights of
  Bretonnia omnibus]); the novels do not place it east or west, so the state's position is the mod's.
  Identity as "eastern Bastonne" rests on owner and position.
- **Canon**: Bastonne's eastern regions are pastoral, its west arable; the Massif Orcal spills into the dukedom
  and its mountain villages are cut off behind the Black Chasm. fandom:Bastonne#Geography [KotG pp. 16, 54-56];
  lex:Bastonne#Geography [KotG pp. 54-57].
- **Analogue**: the Morvan and Charolais edge of Burgundy: cattle pasture under a massif (rw:France EB1911).
  vanilla:STATE_BURGUNDY arable 80 (30.3 per 1,000 px), farm, wheat/livestock/vineyard.
- **Layer**: Cfb 94%, Df 6% -> temperate_forest_hill (unscaled about 22). Agrees.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_farm`, crops `livestock_ranch
  wheat_farm`. Typical hill country; the ranch leads because canon makes the east pastoral. **Tier B.**

### STATE_WATERFALL_PALACE - "Waterfall Palace" (owner ARG; 3 provinces, 774 px of which 183 impassable; landlocked)

- **Identity**: the Waterfall Palace of the Naiad Court, a canon place (fandom:Nymphs), in Argwylon by owner.
  Confident.
- **Canon**: the naiads hold court amid a hundred waterfalls; Argwylon's rivers are alive with naiads and its
  waterfalls sing. fandom:Nymphs; fandom:Argwylon [Wood Elves 8e p. 11]. No land use.
- **Layer**: Df 100% -> temperate_forest_hill (unscaled about 9).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The Athel Loren row. **Tier B.**

### STATE_ARGWYLON - "Argwylon" (owner ARG; 3 provinces, 880 px; landlocked)

- **Identity**: Argwylon, the Moonspring Glades, a High Realm of Athel Loren (canon). The city hub "Feast Halls
  of the Wardancers" belongs in canon to another realm, Fyr Darric (fandom:Fyr Darric [Wood Elves 8e]); that is
  a hub-placement matter, not a land-use one. Realm identity certain.
- **Canon**: a realm of mages, rivers full of naiads and singing waterfalls, where old Ulthuan traditions and
  written records survive. fandom:Argwylon [Wood Elves 8e p. 11]. No land use; realm-level text as under
  STATE_ANMYR.
- **Layer**: Df 100% -> temperate_forest_hill (unscaled about 14).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The Athel Loren row. **Tier B.**

### STATE_GLADE_OF_ETERNAL_MOONLIGHT - "Glade of Eternal Moonlight" (owner ANM; 3 provinces, 868 px of which 125 impassable; landlocked)

- **Identity**: the Glade of Eternal Moonlight is named once in the dump, as the place the prophetess Naieth's
  household defended (fandom:Slaughter at Bleak Meadow); no article of its own and no location given. The mod
  gives it to Anmyr. Uncertain.
- **Canon**: none for the place; Athel Loren realm-level text only.
- **Layer**: Df 100% -> temperate_forest_hill (unscaled about 12).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The Athel Loren row; Anmyr's blight is not assumed to reach it. **Tier C.**

### STATE_CASTLE_MOUSILLON - "Castle Mousillon" (owner MOU; 6 provinces, 1,742 px; river port)

- **Identity**: the rump of the cursed Dukedom of Mousillon, by owner. On the mod's map it sits inland on the
  Grismerie, east of the Lyonesse-owned STATE_MOUSILLON; canon puts the city at the river's mouth. The land-use
  text applies whichever way the border was drawn. Confident.
- **Canon**: the smallest, poorest dukedom; what Lyonesse left is coastal swamp with islands of firmer ground in
  the west and rocky hills of thorn scrub and Forest of Arden edge in the north and east; fog, gales and hail;
  very poor farmland, most of it swamp fed by the sluggish Grismerie, peasants at bare subsistence, the best
  food frogs and snails gathered by licensed swampaires, birds limed on branches; the valley is such poor
  ground that probably no village owns a horse; trade is barter and smuggling; the Orphan Hills are bracken and
  scrub; the Victory of Landuin field alone keeps good soil; each tower of the Cordon Sanitaire grows its own
  food. fandom:Mousillon#Geography [Knights of the Grail pp. 81-83], #Swamping, #Barter and Money, #Transport
  [Barony of the Damned pp. 6-9, 26-27], #Orphan Hills [BotD pp. 19-22]; lex:Mousillon#Locations [Barony of the
  Damned pp. 7-9, 19-25; Vampire Counts 5e p. 17]. Both wikis agree.
- **Analogue**: the Sologne and the Landes before drainage: waterlogged, feverish, rye and millet on scraps,
  sheep for manure (rw:Sologne; rw:Landes of Gascony). Vanilla folds both into larger states
  (vanilla:STATE_ORLEANS arable 70, 25.8 per 1,000 px, the lowest density in northern France).
- **Layer**: Cfb 100% -> temperate_forest_hill (unscaled about 27).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_farm`, crops `rye_farm
  livestock_ranch`. The model has no marsh class; two steps down is the floor (unscaled about 12; the stand-in
  value today is 59). Farm, because canon says the peasants do farm, badly. Rye as the poor-soil grain of the
  analogue; no wheat, no vineyard. **Tier A.**

### STATE_GLADE_OF_ETERNAL_MIDNIGHT - "Glade of Eternal Midnight" (owner TRG; 3 provinces, 764 px of which 158 impassable; landlocked)

- **Identity**: no article and no mention in the dump under this name. The name resembles Modryn, the Night
  Glens (glades that never see sunlight: fandom:Modryn [Wood Elves 8e]), but that is my inference from the name
  only; the mod gives the state to Torgovann. Uncertain.
- **Canon**: none for the place; Athel Loren realm-level text only.
- **Layer**: Df 99% -> temperate_forest_hill (unscaled about 9).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The Athel Loren row. **Tier C.**

### STATE_TYR_VANNA - "Tyr Vanna" (owner TLS; 2 provinces, 419 px; landlocked)

- **Identity**: "the halls of Tyr Vanna" appear once in the dump, in End Times text, with no description. Out
  of timeline and silent on land. By owner part of Talsyn. Uncertain.
- **Canon**: none usable.
- **Layer**: Df 88%, BSk 12% -> temperate_forest_hill (unscaled about 6).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The Athel Loren row. **Tier C.**

### STATE_TALSYN - "Talsyn" (owner TLS; 2 provinces, 535 px; landlocked)

- **Identity**: Talsyn, the Grove of Eternity (canon); the hub Tal Amere is a TWW3 name. Realm identity certain;
  this state is its southern edge (the King's Glade and the Oak are separate states).
- **Canon**: the largest and most prosperous High Realm, backbone of the forest's armies, where elves and forest
  spirits are closest and the worldroots meet. fandom:Talsyn [Wood Elves 8e p. 10]. "Prosperous" is said of an
  elven realm, not of farmland; no land use.
- **Layer**: BSk 65%, Df 35% -> **steppe** (unscaled about 2).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  Canon names it a grove at the heart of an enchanted forest; the layer's dry reading is a border artefact of
  the Brienne lowland to the south. Athel Loren row (unscaled about 4). **Tier B.**

### STATE_HALLS_OF_EQUOS - "Halls of Equos" (owner TLS; 1 province, 360 px; landlocked)

- **Identity**: inferred. No "Halls of Equos" in the dump, but "Equos" is the kindred and title of Lord Edrael
  of Equos, ruler of Cavaroc, the Skymark Reaches, which canon puts on Athel Loren's southern border; this state
  is on the southern border. So: probably Cavaroc, filed by the mod under Talsyn's tag.
- **Canon** (if Cavaroc): the land of the meadow glades, sparsely wooded grassland plains; its elves are
  horsemasters and the first to ride to war; Bretonnian dukes covet these plains. fandom:Cavaroc [Wood Elves 8e
  p. 11].
- **Analogue**: horse pasture on open grassland (the Camargue rather than the Beauce).
- **Layer**: BSk 67%, Df 33% -> steppe (unscaled about 1.6). Agrees with the canon grassland reading.
- **Proposal**: `steppe`, step **0**, `building_subsistence_pasture`, crops `livestock_ranch`. The one Athel
  Loren state where canon describes open grass and herds of horses, and the layer independently says the same.
  **Tier C** (the identification is mine).

### STATE_WYDRIOTH - "Wydrioth" (owner WYD; 5 provinces, 1,265 px; landlocked)

- **Identity**: Wydrioth, the Pine Crags (canon), against the Grey Mountains; hub "Crag Halls of Findol" is a
  TWW3 name built on the canon lord Findol. Certain.
- **Canon**: steep slopes shaped into a living fortress of skycrown oak and rockbriar, forever raided by dwarfs
  and greenskins; dwarf traders who entered were killed. fandom:Wydrioth [Wood Elves 8e p. 12];
  fandom:Wood Elves#Corruption and Bloodshed. No land use.
- **Layer**: Df 100% -> temperate_forest_hill (unscaled about 20).
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch`.
  The Athel Loren row. **Tier B.**

### STATE_LAND_735 - "Land 735" (owner QUE; 6 provinces, 1,527 px; river port) - northern Quenelles on the Grismerie

- **Identity**: inferred from owner and position. Centroid 3975,921, between STATE_MASSIF_ORCAL to the west and
  STATE_PARRAVON to the east, south of STATE_MONTFORT, owned by Quenelles. Canon says Quenelles surrounds the
  Massif Orcal and is divided from Montfort and Parravon by the Grismerie, so this is the north-eastern arm of
  Quenelles on the river's left bank. Unnamed; the fortified town of Viefin, at the end of the Axe Bite road,
  is the one canon settlement likely to fall in it.
- **Canon**: broadly, northern Quenelles is pastoral and the south arable; the north is dominated by the Massif
  Orcal, whose greenskins raid the settlements round it; villages near the Massif are usually sacked within
  years, the survivors heavily fortified. fandom:Quenelles#lead, #Geography [Knights of the Grail pp. 88-90].
  Lexicanum's Quenelles page was never reached.
- **Analogue**: the Bourbonnais and Forez between the Massif Central and the upper Loire: cattle country with
  grain in the valley (rw:France EB1911, Charolais and Central Plateau cattle). vanilla:STATE_BURGUNDY arable 80
  (30.3 per 1,000 px), farm, wheat/livestock/vineyard.
- **Layer**: no entry (state newer than the index). Its neighbours read Df.
- **Proposal**: `temperate_forest_hill`, step **0**, `building_subsistence_farm`, crops `livestock_ranch
  wheat_farm`. Raided pastoral hill country on a navigable river: typical of the class, ranch first (unscaled
  about 24; stand-in today 52). **Tier B** (canon is explicit for northern Quenelles; the match is by position).

### STATE_LAND_736 - "Land 736" (unowned; 35 provinces, 9,018 px; coastal) - Albion, north

- **Identity**: the northern Albion state (centroid 3382,608). Unnamed. Certain as geometry.
- **Canon, analogue, layer**: as STATE_LAND_078. Nothing read distinguishes the north of the island.
- **Proposal**: `temperate_forest_hill`, step **-2**, `building_subsistence_pasture`, crops `livestock_ranch
  rye_farm` (unscaled about 63). **Tier B.**

<!-- STATES-APPEND -->

### Progress

Entries written: 36 of 36.

## 3. Rows

```csv
state_key,lore_class,fertility_step,subsistence,crops,tier,note,source
STATE_L_ANGUILLE,temperate_river_plain,1,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,"Almost all arable, fertile soil, mild weather, harvests most of the year; Sannez mouth; no vines on this coast","lex:L'Anguille#Geography [Knights of the Grail pp. 43-46] ; fandom:L'Anguille#Geography [Knights of the Grail pp. 41-46] ; rw:Normandy [EB1911 France] ; vanilla:STATE_NORMANDY arable 120"
STATE_COURONNE,temperate_river_plain,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,"Couronne proper mostly arable, pastoral toward the Pale Sisters; horse-breeding everywhere; Sannez runs through","lex:Couronne#Geography [Knights of the Grail pp. 67-70] ; fandom:Couronne#Geography [Knights of the Grail pp. 67-70] ; lex:Bretonnia#Rivers [Knights of the Grail p. 9] ; vanilla:STATE_NORMANDY arable 120"
STATE_PALE_SISTERS,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch,A,"Largely barren white-rock range, brigands and a few goblins; pastoral fringe; greenskin owner herds","fandom:Pale Sisters#lead [WFRP 1e Core pp. 274-275; Knights of the Grail p. 71] ; lex:Couronne#Geography [Knights of the Grail pp. 67-70]"
STATE_GISOREUX,temperate_forest_hill,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,A,"Plains and North Gisoreux both mostly pastoral and hilly; arable along the Sannez; Valle Florida vineyards","fandom:Gisoreux#Geography [Knights of the Grail pp. 70-73] ; fandom:Gisoreux#Valle Florida [Knights of the Grail pp. 70-73] ; vanilla:STATE_BRITTANY arable 120"
STATE_BASTONNE,temperate_forest_hill,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,"West mainly arable, east pastoral; much of the empty Forest of Chalons inside it","lex:Bastonne#Geography [Knights of the Grail pp. 54-57] ; fandom:Bastonne#Geography [Knights of the Grail pp. 16, 54-56] ; vanilla:STATE_POITOU arable 90"
STATE_MONTFORT,highland_alpine,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm,A,"Almost all in the Grey Mountains; little and infertile farmland; imports food after any bad harvest","fandom:Montfort#Geography [Knights of the Grail pp. 78-79] ; lex:Bastonne#The People [Knights of the Grail pp. 54-57] ; vanilla:STATE_SAVOY arable 20"
STATE_CROOKED_CORRIDOR,highland_alpine,0,building_subsistence_pasture,building_livestock_ranch,A,"Snow-shut smugglers' pass known to goatherds; Karak Ziflin herds (standing dwarf ruling)","fandom:Montfort#Crooked Corridor [WFRP 4e Core p. 284] ; fandom:Karak Ziflin#Subsidiary Settlements [Lords of Stone and Steel pp. 19, 24]"
STATE_OIS_GAP,highland_alpine,0,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,"Hill pass with Fort Bergbres; no land-use text for the gap; Gisoreux hill country is pastoral","fandom:Fort Bergbres [Marienburg: Sold Down the River p. 10] ; fandom:Gisoreux#Geography [Knights of the Grail pp. 70-73] ; rw:France rye uplands [EB1911 France]"
STATE_PARRAVON,highland_alpine,1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,"Mountain dukedom; most people in fertile Parravon Vale, arable centre and pastoral rim","fandom:Parravon#Geography [Knights of the Grail pp. 85-86] ; lex:Parravon#People [Knights of the Grail pp. 85-97] ; vanilla:STATE_WEST_SWITZERLAND arable 50"
STATE_NORTH_GREY_MOUNTAINS,highland_alpine,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,"Karak Azgaraz: fortified farms grow wheat, barley and hops; mountain cattle and goats; grain hold ruling holds","fandom:Karak Azgaraz#Society [Archives of the Empire I p. 69] ; fandom:Karak Azgaraz#Surface Features [WFRP 3e Book of Grudges pp. 16-29] ; vanilla:STATE_TYROL arable 30"
STATE_ANMYR,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,A,"Witherhold: Morghur's blight, withering groves, barren soil; Asrai hunt, no fields","fandom:Anmyr [Wood Elves 8e p. 12] ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_MASSIF_ORCAL,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch,A,"Barren greenskin highland, thin soil, no fertile land; few fortified human villages","fandom:Massif Orcal [White Dwarf 249 p. 19] ; fandom:Quenelles#Geography [Knights of the Grail pp. 88-90] ; rw:Massif Central [EB1911 France]"
STATE_BORDELEAUX,temperate_river_plain,0,building_subsistence_farm,building_vineyard building_wheat_farm building_livestock_ranch,A,"Largest wine exporter; mostly arable, suited to cereals and vines; Morceaux Valley wine; Gilleau mouth","fandom:Bordeleaux#lead [Knights of the Grail pp. 58-59; WFRP 1e Core p. 275] ; lex:Bordeleaux#Geography [Knights of the Grail ch. VI] ; rw:Bordeaux [en.wikipedia.org/wiki/History_of_Bordeaux_wine] ; vanilla:STATE_GUYENNE arable 90"
STATE_MOUSILLON,temperate_river_plain,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch,B,"Owned by Lyonesse: the fertile ex-Mousillon land, mainly arable lake and river country; not the swamp","fandom:Lyonesse#Geography [Knights of the Grail pp. 74-76] ; fandom:Mousillon#Geography [Knights of the Grail pp. 81-83] ; lex:Mousillon#lead [Barony of the Damned pp. 11-12] ; vanilla:STATE_MAINE_ANJOU arable 112"
STATE_ARTOIS,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_wheat_farm,A,"All but a western strip inside the Forest of Arden; forest villages keep stock, not crops","fandom:Artois#lead [Knights of the Grail pp. 51-52] ; lex:Artois#Geography [Knights of the Grail pp. 51-53] ; vanilla:STATE_WALLONIA arable 55"
STATE_LYONESSE,temperate_forest_hill,1,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,"Mainly arable inland; island coast with offshore villages; motte hills; no vines (Breton analogue)","fandom:Lyonesse#Geography [Knights of the Grail pp. 74-76] ; lex:Lyonesse#Geography [Knights of the Grail pp. 74-77] ; vanilla:STATE_BRITTANY arable 120"
STATE_LAND_078,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch building_rye_farm,B,"South Albion: rain-bound bog and fen where few crops grow; cattle chieftains; rare stilt villages","fandom:Albion#Origins [Shadows Over Albion p. 6] ; fandom:Albion#Religion [Archives of the Empire III pp. 57-58] ; rw:Scottish Highlands [en.wikipedia.org/wiki/Scottish_Highlands] ; vanilla:STATE_HIGHLANDS arable 30"
STATE_LAND_079,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch building_rye_farm,B,"Central Albion: thickest mists, marsh and moor; few crops; cattle","fandom:Albion#Origins [Shadows Over Albion p. 6] ; fandom:Albion#Geography [Town Cryer 15 pp. 4-6] ; vanilla:STATE_HIGHLANDS arable 30"
STATE_TORGOVANN,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,B,"Forge of Starlight: smiths' realm in beech forest; Asrai hunt, no fields","fandom:Torgovann [Wood Elves 8e p. 12] ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_YI_EDRI_ETERNOS,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,B,"Oak of Ages, sacred heart of Athel Loren; no land use","fandom:Oak of Ages ; fandom:Talsyn [Wood Elves 8e p. 10] ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_KING_S_GLADE,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,B,"King's Glade: clearing and living-tree city of Ariel and Orion; no fields","fandom:King's Glade ; fandom:Talsyn [Wood Elves 8e p. 10] ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_SOUTH_GREY_MOUNTAINS,highland_alpine,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,"Karak Norn: three cereal-growing dependencies and a Fertile Valley; departs from the dwarf pasture ruling","fandom:Karak Norn#Subsidiary Settlements [Lords of Stone and Steel pp. 24-26] ; fandom:Karak Norn#Geography [Lords of Stone and Steel pp. 27-32] ; vanilla:STATE_TYROL arable 30"
STATE_TAL_ESTH,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,C,"Name attested only in End Times text; by owner part of Wydrioth, the Pine Crags","fandom:Wydrioth [Wood Elves 8e p. 12] ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_LYONESSE_HILLS,temperate_forest_hill,1,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,"Northern Lyonesse: mainly arable, dotted with castled mottes; no vines (Breton analogue)","fandom:Lyonesse#Geography [Knights of the Grail pp. 74-76] ; lex:Lyonesse#Geography [Knights of the Grail pp. 74-77] ; vanilla:STATE_BRITTANY arable 120"
STATE_CASTLE_SANGASSE,temperate_forest_hill,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm,B,"Eastern Bastonne by owner and position: the pastoral side under the Massif Orcal","fandom:Bastonne#Geography [Knights of the Grail pp. 16, 54-56] ; fandom:Castle Sangasse [Knights of Bretonnia omnibus] ; vanilla:STATE_BURGUNDY arable 80"
STATE_WATERFALL_PALACE,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,B,"Naiad court among waterfalls in Argwylon; no land use","fandom:Nymphs ; fandom:Argwylon [Wood Elves 8e p. 11] ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_ARGWYLON,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,B,"Moonspring Glades: mages' realm of rivers and waterfalls; no fields","fandom:Argwylon [Wood Elves 8e p. 11] ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_GLADE_OF_ETERNAL_MOONLIGHT,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,C,"Named once in the dump with no location; Athel Loren row by owner","fandom:Slaughter at Bleak Meadow ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_CASTLE_MOUSILLON,temperate_forest_hill,-2,building_subsistence_farm,building_rye_farm building_livestock_ranch,A,"Cursed rump duchy: Grismerie swamp and thorn hills, very poor farming, frogs and snails, no horses","fandom:Mousillon#Geography [Knights of the Grail pp. 81-83] ; fandom:Mousillon#Swamping [Barony of the Damned pp. 6-9] ; lex:Mousillon#Locations [Barony of the Damned pp. 7-9] ; rw:Landes of Gascony [en.wikipedia.org/wiki/Landes_of_Gascony]"
STATE_GLADE_OF_ETERNAL_MIDNIGHT,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,C,"No canon text under this name; Athel Loren row by owner","fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_TYR_VANNA,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,C,"Name attested only in End Times text; Athel Loren row by owner","fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_TALSYN,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,B,"Grove of Eternity: forest realm, not the steppe the layer reads; no fields","fandom:Talsyn [Wood Elves 8e p. 10] ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_HALLS_OF_EQUOS,steppe,0,building_subsistence_pasture,building_livestock_ranch,C,"Probably Cavaroc (Lord Edrael of Equos): sparsely wooded grassland plains, horsemasters","fandom:Cavaroc [Wood Elves 8e p. 11]"
STATE_WYDRIOTH,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch,B,"Pine Crags: steep living fortress against dwarfs and greenskins; no fields","fandom:Wydrioth [Wood Elves 8e p. 12] ; fandom:Wood Elves#The Sundering [Wood Elves 8e pp. 15-27]"
STATE_LAND_735,temperate_forest_hill,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm,B,"Northern Quenelles on the Grismerie by owner and position: pastoral, raided from the Massif Orcal","fandom:Quenelles#Geography [Knights of the Grail pp. 88-90] ; vanilla:STATE_BURGUNDY arable 80"
STATE_LAND_736,temperate_forest_hill,-2,building_subsistence_pasture,building_livestock_ranch building_rye_farm,B,"North Albion: bog, fen and moor where few crops grow; cattle","fandom:Albion#Origins [Shadows Over Albion p. 6] ; fandom:Albion#Religion [Archives of the Empire III pp. 57-58] ; vanilla:STATE_HIGHLANDS arable 30"
```

## 4. Disagreements

### 4.1 With the climate layer (`state_climate_index.json`, zone -> class)

| State | Layer class | Proposed | Reason |
|---|---|---|---|
| L_ANGUILLE, COURONNE, BORDELEAUX, MOUSILLON (LYO) | temperate_forest_hill | temperate_river_plain | Canon "mostly / almost entirely arable" on the Sannez, Gilleau, Morceaux and the Lyonesse lake country; the layer has no river signal |
| MONTFORT, PARRAVON, MASSIF_ORCAL, CROOKED_CORRIDOR, NORTH_GREY_MOUNTAINS | temperate_forest_hill (Df) | highland_alpine | Canon mountain country; Df at this latitude is the layer reading altitude as cold forest |
| PALE_SISTERS, OIS_GAP, SOUTH_GREY_MOUNTAINS | boreal_forest (Dc) | highland_alpine | Same: these are peaks and passes in a temperate latitude, not taiga |
| TALSYN | steppe (BSk 65%) | temperate_forest_hill | Canon grove at the heart of the forest |
| HALLS_OF_EQUOS | steppe | steppe | Agreement, noted because it is the only Athel Loren state left off the forest row |
| All other Athel Loren states, ARTOIS, GISOREUX, BASTONNE, CASTLE_SANGASSE, LYONESSE, LYONESSE_HILLS, CASTLE_MOUSILLON | temperate_forest_hill | same class | Only the step differs: -2 Athel Loren and Castle Mousillon, -1 Artois, +1 both Lyonesse states |
| LAND_078, LAND_079, LAND_736, LAND_735 | no entry | see rows | States newer than the index |

### 4.2 With the earlier draft (`agro_climate_overrides_draft.md`, BRE-01 to BRE-07, and `state_climate_classes.csv`)

- **BRE-01 (L'Anguille river plain)**: confirmed, and strengthened to step +1. The draft's objection ("no canon
  river authored") falls: canon puts the Sannez mouth at the city. The Aquitaine half is outside this file.
- **BRE-02 (Mousillon, two steps down, both states)**: **half wrong.** It holds for STATE_CASTLE_MOUSILLON (owner
  MOU). STATE_MOUSILLON is owned by Lyonesse and is the fertile land Lyonesse annexed, mainly arable; I move it
  up to river plain, step 0.
- **BRE-03 (Athel Loren down two)**: confirmed on new evidence (the Asrai hunt; no farming text), with three
  changes: subsistence set to pasture for the hunting basket; STATE_HALLS_OF_EQUOS split off as steppe grassland
  (Cavaroc); STATE_TALSYN moved off the layer's steppe reading. The draft's "T" tier for six glades is reported
  here as B or C by what the dump actually attests.
- **BRE-04 (Montfort one step down on forest-hill, highland as alternative)**: I take the alternative,
  `highland_alpine` step 0. Canon: almost all of the dukedom is in the Grey Mountains.
- **BRE-05 (Grave of Cuileux)**: outside this file. Confirmed in passing: fandom:Quenelles#Geography says it is
  not farmed.
- **BRE-06 (Carcassonne)**: outside this file.
- **BRE-07 (Artois one step down)**: confirmed.
- `state_climate_classes.csv` had STATE_PALE_SISTERS as temperate_forest_hill (I propose highland, -1, on
  "largely barren"), STATE_PARRAVON as temperate_forest_hill (I propose highland +1), STATE_BASTONNE and
  STATE_GISOREUX as temperate_forest_hill (kept), STATE_BORDELEAUX as river plain (kept), and the dwarf pass
  states as highland (kept).
- Standing rulings re-tested: Karak Azgaraz as a grain hold **confirmed** (wheat, barley and hops at the hold).
  "Dwarf holds herd" **confirmed for Karak Ziflin** (goatherds on the pass) and **contradicted for Karak Norn**
  (three cereal dependencies, a Fertile Valley). Greenskins herding: nothing read contradicts it; canon calls
  both their ranges barren.

## 5. Open questions for Chris

1. **Wood Elf subsistence type.** Canon read: the Asrai hunt the forest's animals for food and clothing and
   feast on game and wine; no text has them tilling. I propose `building_subsistence_pasture` for its basket
   (meat and fabric). The alternative is `building_subsistence_orchard` (fruit) if you would rather read them as
   gatherers. The dump's Wine article says glades are set aside for grapes, but cites Total War; if you accept
   that, add `building_vineyard` to the Athel Loren crop lists.
2. **Karak Norn: farm or pasture?** The row proposes farm against the standing ruling. Your call.
3. **Karak Ziflin** has one grain-supplying outpost (Grung Ardzufak, about 300 dwarfs). I left it a herding
   hold. Fine?
4. **STATE_MOUSILLON's name.** It is Lyonesse's southern half, good farmland. The name invites exactly the
   mistake the earlier draft made. Rename (e.g. South Lyonesse), or keep and rely on the row?
5. **Albion's total.** Three states at forest-hill step -2 come to about 188 unscaled arable on 26,900 px,
   near vanilla's Highlands density. Canon says settlements are rare. If that reads too rich, the next rung is
   `highland_alpine` step -1 (about 96). Canon gives no basis for ranking north, centre and south.
6. **Valle Florida** (canon wine valley in the Pale Sisters, Gisoreux): I credited its vineyard to
   STATE_GISOREUX because STATE_PALE_SISTERS is orc-owned. If the valley should sit in the Pale Sisters state,
   move the vineyard.
7. **Identifications by inference**: STATE_LAND_735 as north-eastern Quenelles (owner and position);
   STATE_CASTLE_SANGASSE as eastern Bastonne (owner and position; the novels only say "near Garamont");
   STATE_HALLS_OF_EQUOS as Cavaroc (from "Equos"); STATE_GLADE_OF_ETERNAL_MIDNIGHT possibly Modryn (name only);
   STATE_TAL_ESTH and STATE_TYR_VANNA are attested only in End Times text.
8. **Hub placement noticed in passing, not a farmland matter**: canon puts the Feast Halls of the Wardancers in
   Fyr Darric, not Argwylon; the Oak of Prophecy (Guerac Circle) is filed by both wikis under Mousillon, while
   the OKP provinces sit in STATE_ARTOIS; the city of Mousillon is canonically at the Grismerie mouth, while the
   MOU-owned state is drawn inland of the LYO-owned one.
9. **Page numbers disagree between the wikis** for Knights of the Grail (L'Anguille 41-46 vs 43-46; Bordeleaux
   58-59 vs 54-57; Parravon 85-86 vs 85-97; Artois 51-52 vs 51-53). The text agrees; I quote both where I have
   both and prefer Fandom's for Bordeleaux.
10. **Mousillon annexation date**: 1814 IC in Knights of the Grail (Fandom), "the 1900s IC" on Lexicanum. Not
    material to the rows.

## 6. Pages read

**Lexicanum (2026-11-19, browser pane, before the Cloudflare challenge)**: Bretonnia, Couronne, L'Anguille,
Lyonesse, Mousillon, Artois, Bordeleaux, Bastonne, Parravon. Blocked by HTTP 403 `cf-mitigated: challenge` and
never read there: Gisoreux, Montfort, Quenelles and everything after.

**Web (real world)**:
- https://en.wikisource.org/wiki/1911_Encyclopaedia_Britannica/France (Agriculture section)
- https://fred.stlouisfed.org/data/A0133BFRA563NNBR (NBER wheat acreage, France)
- https://en.wikipedia.org/wiki/Economic_history_of_France
- https://sites.ohio.edu/chastain/ip/peaf.htm (Peasant agriculture, France, 1848 encyclopedia)
- https://en.wikipedia.org/wiki/Agriculture_in_France (modern figures only)
- https://en.wikipedia.org/wiki/Normandy
- https://en.wikipedia.org/wiki/Brittany (little of use)
- https://en.wikipedia.org/wiki/Bocage
- https://en.wikipedia.org/wiki/History_of_Bordeaux_wine
- https://en.wikipedia.org/wiki/Landes_of_Gascony
- https://en.wikipedia.org/wiki/Sologne
- https://en.wikipedia.org/wiki/Massif_Central
- https://en.wikipedia.org/wiki/Beauce,_France (little of use)
- https://en.wikipedia.org/wiki/Alpine_transhumance
- https://en.wikipedia.org/wiki/Scottish_Highlands
- https://en.wikipedia.org/wiki/Agriculture_in_Ireland
- https://en.wikipedia.org/wiki/Great_French_Wine_Blight (nothing of use)
- https://www.cambridge.org/core/journals/journal-of-economic-history/article/agricultural-revolution-in-nineteenthcentury-france/BA7A409CBE0F4782088ACE578218B311 (abstract and notes only)
- Not readable: the Toronto PDF `economics.utoronto.ca/munro5/18FRENAG.pdf` (binary), fr.wikipedia Histoire de
  l'agriculture en France (404), Springer s13595-020-00987-5 (login wall). No national 1840 land-use table was
  found; the 1840 Statistique agricole is the primary source and I did not reach it.

**Fandom dump (`sources/wiki/pages/`, read 2026-11-20)**: Gisoreux, Montfort, Pale Sisters, Karak Ziflin,
Couronne, L'Anguille, Bastonne, Grey Mountains, Fort Bergbres, River Ois, Gisoreux Gap, Parravon, Massif Orcal,
Forest of Chalons, Forest of Arden, Karak Azgaraz, Karak Norn, Quenelles, Athel Loren, Anmyr, Argwylon, Talsyn,
Torgovann, Wydrioth, King's Glade, Vaul's Anvil, Wild Heath, Cavaroc, Modryn, Fyr Darric, Cythral, Arranoc,
Atylwyth, Oak of Ages, Wood Elves (keyword passages and footnotes), Wine (Wood Elven Wine section), Lyonesse,
Mousillon, Bordeleaux, Artois, Albion (Geography, Society, Religion, Origins, Canon Conflict and keyword
passages; the article is 113,000 characters and I did not read it end to end), Castle Sangasse, Dwarfs (food
passage only). Grepped by name with one-line hits only: Nymphs, Slaughter at Bleak Meadow, The End Times,
Sanglac Castle.

**Not corroborated on Lexicanum** (blocked by the Cloudflare challenge on 2026-11-19; no second attempt was
made on 2026-11-20, as the brief's stop rule applies): everything cited `fandom:` only, that is Gisoreux,
Montfort, Pale Sisters, Massif Orcal, Quenelles, the Grey Mountain holds, all of Athel Loren and Albion. The
dukedoms where I hold both wikis (L'Anguille, Couronne, Lyonesse, Mousillon, Artois, Bordeleaux, Bastonne,
Parravon) agree on every land-use statement.

**Could not do**: a national 1840 land-use table for France (arable, pasture, vine, forest, waste shares); the
web tool hit the account limit before the Britannica county articles, the Ardennes and the Irish bog figures
were read, so those analogues rest on the sources listed above and are thinner than I wanted.
