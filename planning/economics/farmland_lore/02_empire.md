# Farmland lore dossier — The Empire (`02_empire.txt`), board #3679 (epic #3675)

Status: COMPLETE 2026-11-20. 30 states in `map_data/state_regions/02_empire.txt`, 30 entries, 30 rows (tiers A 21, B 8, C 1).
Section 0 is the raw research log kept from the first day; sections 1-6 are the dossier.

Note on scope: this file holds only part of the Empire. Nordland, Ostermark, Talabecland, North Ostland, Laurelorn and
`STATE_THE_WASTELAND` sit in `01_kislev.txt` (another dossier). Three states here are not Imperial at all:
`STATE_MARCHES_OF_COURONNE` (owner COU, Bretonnia), `STATE_GREY_LADY_PASS` (owner PAR, Parravon) and
`STATE_AXE_BITE_PASS` (owner KZF, Karak Ziflin).

## 0. Research log (raw findings, kept so a cut-off loses nothing; folded into sections 1-2 as they are written)

Canon read on the live wikis on 2026-11-19 before the Cloudflare stop (Lexicanum = `lex:`, Fandom = `fandom:`):

- lex:Averland [Sigmar's Heirs pp. 43-48; Empire 7e p. 18; Archives of the Empire I p. 7]: exports cattle, clothing, porcelain, horses, leather goods, wine; wide fertile plains, the Empire's best horses. Streissen: crop failure, famine and riots in 2502 IC.
- fandom:Averland#Geography [Sigmar's Heirs]: sun-drenched rolling plains with few woods between Upper Reik, Aver and Blue Reach; plains watered by annual river floods, abundant crops; west and centre: longhorn cattle driven to the stockyards of Averheim and Loningbruck; south-centre and east: viticulture (Grenzstadter White, Loningbruck Ruby); far east: mining, gems and furs in the foothills. Intro: economy "mostly on agriculture and the raising of cattle"; less fertile than Ostermark, valued as grazing.
- lex:Averheim [Sigmar's Heirs p. 46]: stockyards, cattle drives, slaughterhouses by the docks, meat barged down the Aver. lex:Heideck [SH pp. 46-47]: cattle market.
- lex:The_Moot [Empire 4e p. 53; Empire 7e p. 118; SH p. 59ff]: rich soil, bountiful harvests at the Blue Reach / Aver Reach junction; Stirland resents it.
- fandom:Mootland#Geography [SH pp. 59-63]: "perhaps the most fertile farmland in the central Empire"; rolling hills and grassland, open country; rain enough for regular good crops; Aver March (south-west of the Aver): large herds of sheep and goats, apples in the west; Auld Styrlande (north of the rivers): farming districts, the Moot's breadbasket; Fallow Hills / "Greenleafs" (south-east, in the loop of the Aver Reach): tobacco, a major cash crop.
- fandom:Old_World_Trade_and_Economy [cited 1c]: Reikland an agricultural centre with advanced farming; the Moot's pastures give the best beef and mutton, beer and flour; Middenheim grows just enough to feed itself; Nuln sells fine wines.
- lex:Reikland [SH pp. 77-84]: exports wine, textiles, precious metals, iron ore, cheese; fertile farmland, mines, Reikwald timber; most prosperous province.
- fandom:Reikland#Geography [SH pp. 77-85; WFRP 4e]: three regions: Grey Mountains, the fertile foothill Vorbergland, the Reikwald. Hägercrybs and Skaag Hills inside the Reikwald: sheep and mining. Rivers off the Grey Mountains matter for Vorbergland farming (the 2211 IC damming and "runtwater" march).
- fandom:Vorbergland [WFRP 4e pp. 80, 268, 270]: fertile valleys, rolling grassland; Suden Vorbergland (Böhrn, Ubersreik, Stimmigen, Dunkelberg) the most heavily cultivated part of Reikland, "Ranald's Garden", wine for export; the west is raided, sparsely peopled.
- lex:Eilhart [WFRP 4e p. 281]: ringed by vineyards, famous white wine. lex:Bögenhafen [Shadows over Bögenhafen pp. 6-8; WFRP 4e]: trades local wine and wood; Schaffenfest livestock fair; a merchant house deals in grain. lex:Grunburg [SH p. 82]: smoked cheese. lex:Altdorf#History: early Reikdorf raised cattle on fine pasture.
- lex:Reikwald_Forest [The Enemy Within p. 23]: mainly coniferous, deciduous along the rivers.
- lex:Wissenland / fandom:Wissenland#Geography [SH pp. 94-98]: fertile near the Reik, stonier and drier toward the mountains (flint in the fields); the west has dropped all but subsistence farming and lives on mines; east of the Söll rolling grassland for sheep, high-quality wool and furs (old Solland).
- fandom:Solland#Geography [Archives of the Empire I]: rich farmland around Pfeildorf, then lightly wooded hills, then cattle and sheep in the Black/Grey Mountain foothills, then mines (copper, tin, gold). lex:Pfeildorf [SH pp. 96-97]: centre of the Sudenland wool trade; fishing.
- lex:Josef_Bugman [Dwarfs 6e/8e]: the brewery stood by the Sol in the forest of eastern Wissenland.
- lex:Stirland [SH pp. 7, 85-87]: exports woollen goods, wine, salted fish, woodcrafts; poor province; less forested than the north, rolling plains for cattle and agriculture, densely settled along roads and rivers; eastern regions less fertile. lex:Wurtbad [SH pp. 86-88]: wine trade centre, all wine of western Stirland is sold through it; vineyards around the city.
- fandom:Stirland#Geography [SH pp. 85-89]: north bank strip is the last of the Great Forest; the west is the Stirhügel hill country, sheep-herding villages trading at Flensburg and Wörden; the east is Sylvania; Dwarfs of Zhufbar go south by Schramleben and through the Moot.
- lex:Sylvania [Vampire Counts 7e pp. 20-22; Undead 4e pp. 24-26; Sylvania the Cursed County pp. 4-5, 10]: rotted forest on bone-strewn soil, moor, bog; few viable crops, famine commonplace; infertile earth, thin goats and pigs; subsistence farming, only the larger towns export wool and vegetables.
- fandom:Sylvania#Geography / The Sylvanians [Night's Dark Masters pp. 84-91]: harsh winters, damp land of bogs and moors; peat fertilises the fields; thin soil laced with warpstone since 1111 IC; low yields, starvation a constant. South of Sylvania lies a barren tract of stinking marsh and fallow hills, claimed by Averland, held by Stirland, ignored by both.
- lex:Middenland [SH pp. 53-57; Empire 8e p. 26]: exports copper, iron, 'iron oak', timber, wine, wool, woollen goods; largely Drakwald. lex:Delberz [SH]: rich merchant town known for wines.
- fandom:Middenland#Geography/Economy [SH pp. 53-58; Middenheim: City of the White Wolf pp. 119-123]: Drakwald from the Wasteland's edge to Hochland; Midden Moors in the far west infertile hill and wetland; Schadensumpf bog north near Middenheim; Howling Hills in the south-east; economy is timber and agriculture; acidic forest soils, yet the Grand Duchy feeds itself with some surplus grain; little dairy (herds draw raiders); game meat.
- lex:Hochland / fandom:Hochland#Geography [SH pp. 49-52; Uniforms & Heraldry p. 18]: almost wholly forest; farms along the river banks and round villages are fertile, the province feeds itself; exports timber and woodcraft; Weiss Hills moor and fen. Lands round the Middle Mountains never resettled after Gorthor [Beastmen 7e pp. 27-31].
- lex:Ostland / fandom:Ostland#Geography [SH pp. 73-76; Uniforms & Heraldry pp. 36-39]: nearly all Forest of Shadows; the bull emblem is read as heavy use of cattle and oxen. lex:Wolfenburg [SH pp. 75-76]: timber. lex:Talabec [WFRP Companion p. 22]: the Wolfen leaves the Middle Mountains onto "the plains of Ostland" near Wolfenburg; the Drakwasser and the Talabec carry rich dark soil.
- lex:Middle_Mountains [The Horned Rat Companion ch. 9; Beasts of Chaos 6e p. 10]: forested mountains, goblins and beastmen, tenuous Imperial control.
- lex:Wasteland / fandom:The_Wasteland [Marienburg: Sold Down the River pp. 6-11, 16-20]: devastated moor and swamp; hamlets eke out a living, mostly along the Reik's alluvial plain; Manaanspoort Zee is "Marienburg's garden", haddock, halibut, herring, salted for export; Kleinland heath for sheep, wool one of few native exports; Klessen on the Gisoreux road; Erlach a mining village in the Pale Sisters foothills; Bitter Moors poisoned.
- lex:Helmgart [WFRP 4e p. 285]: fortress and market town at the head of Axe Bite Pass. lex:Grey_Mountains [Empire 4e p. 12]: poor in minerals, brigands and greenskins.
- lex:Great_Forest [SH p. 7; Empire 7e]: many parts cleared for farming.

Real-world sources read so far:

- rw:Germany 1878 land use [Statistisches Jahrbuch für das Deutsche Reich 1880, p. 21, https://digi.bib.uni-mannheim.de/fileadmin/statjahrb/514401303_1880/pdf/514401303_0027.pdf] (percent arable+garden+vineyard / meadow+pasture / forest): Reich 48.5 / 19.1 / 25.7; Rhineland 46.5 / 17.2 / 30.7; Hesse-Nassau 39.8 / 15.9 / 40.1; Westphalia 42.0 / 25.0 / 27.9; Hanover 32.6 / 45.4 / 15.8; Brandenburg 46.2 / 14.9 / 32.1; Pomerania 55.1 / 18.7 / 19.7; Franconia 45.6 / 14.2 / 34.9; rest of Bavaria east of the Rhine 37.7 / 23.4 / 31.4; Palatinate 46.3 / 9.4 / 38.6; Kingdom of Saxony 54.3 / 13.5 / 27.7; Württemberg 46.4 / 18.1 / 30.8; Baden 43.1 / 15.1 / 37.6; Hesse 51.0 / 13.2 / 31.3; Mecklenburg-Schwerin 57.1 / 12.9 / 16.8; Saxe-Weimar 56.0 / 12.1 / 25.3; Saxe-Meiningen 41.6 / 13.3 / 41.7; Schwarzburg-Rudolstadt 41.1 / 9.5 / 45.4; Brunswick 50.4 / 14.3 / 30.3; Anhalt 61.5 / 8.6 / 24.4; Alsace-Lorraine 49.6 / 14.3 / 30.6.
- rw:Germany 1800-1880 [U. Pfister, Univ. Münster lecture notes "Agrarwachstum, Agrarmodernisierung und Landreformen im 19. Jh.", https://www.wiwi.uni-muenster.de/wisoge/sites/wisoge/files/downloads/skripte/Grundlegung_Moderne/s06_landwirtschaft_19._jh.pdf]: pasture fell from about 18 % of land (1800) to 9.6 % (1883) as fallow and commons went under the plough; grain never under 55 % of arable; Westphalia 1822/35-1878/82 farmland +12.8 %; potato yield 6,875 kg/ha against rye 1,027 kg/ha (Westphalia 1878/82).
- rw:German wine [https://en.wikipedia.org/wiki/German_wine]: viticulture on the Rhine and tributaries (Mosel, Main, Neckar), climate limit about the 50th parallel, Saale-Unstrut the northernmost region; planted area peaked about 1500 at perhaps four times today's roughly 104,000 ha and shrank after (beer in the north, Thirty Years' War, Little Ice Age).
- rw:Netherlands 1833 [Thissen, Tijdschrift voor Historische Geografie 1991, via search summary]: about 900,000 ha, close to 30 % of the land, was "woeste grond" (heath, peat, drift sand).
- rw:Transylvania [History of Transylvania, https://www.mek.oszk.hu/03400/03407/html/304.html]: ploughland about 513,000 ha by 1830 and 623,000 ha in 1851 (the principality is about 5.7 M ha, so roughly a tenth); two-field system on about 59 % of ploughland in the northern Partium in 1820; 900,000-950,000 transhumant sheep in 1823-30.

Vanilla analogue numbers (read from the install): RHINELAND 55 farm wheat/livestock/vineyard; NORTH_RHINE 77; BADEN 50; WURTTEMBERG 70; BAVARIA 65; FRANCONIA 80 (all wheat/livestock/vineyard); HESSE 80 rye/livestock/vineyard; SAXONY 100 rye/livestock/vineyard; ANHALT 75, BRANDENBURG 50, HANNOVER 60, WESTPHALIA 60, BRUNSWICK 30, MECKLENBURG 25, POMERANIA 55 (all rye/livestock); HOLLAND 30, FRIESLAND 30, GELRE 40 (rye/livestock); BOHEMIA 195 rye/livestock/vineyard; TYROL 30, EAST_SWITZERLAND 40, WEST_SWITZERLAND 50 (highland); SOUTHERN_TRANSYLVANIA 50, NORTHERN_TRANSYLVANIA 50 (wheat/livestock/vineyard); NORMANDY 120, PICARDY 80. All `building_subsistence_farm`.

## 1. Realm picture

### 1.1 Canon

The Empire is forest first. Canon says so at realm level (fandom:Great_Forest [Sigmar's Heirs pp. 5-8]; lex:Rivers_of_The_Empire
[Empire 8e pp. 24-26]) and then draws a sharp north/south line through it. Sigmar's Heirs calls Reikland, Stirland,
Averland and the Moot the "breadbasket" provinces and has Ostlanders resent them for it (fandom:Ostland#Inhabitants
[Sigmar's Heirs pp. 73-76]; lex:Stirland cites the heading "The Southern and Western breadbasket" [SH p. 7]). North of the
Talabec and the lower Reik the provinces are forest with clearings: Middenland feeds itself on acid forest soil with a
little grain to spare and keeps few herds, Hochland is self-sufficient from riverside farms and sells timber, Ostland
clears patches from the Forest of Shadows. South of that line:

- **Reik valley and Reikland.** Fertile farmland, vineyards and dairy with a surplus for export; the foothill Vorbergland
  is fertile valley country and its south-east ("Ranald's Garden") is the most heavily cultivated land in the province and
  a wine exporter; the Reikwald's hill tracts (Hägercrybs, Skaag Hills) are sheep walks (fandom:Reikland#Geography
  [SH pp. 77-85; WFRP 4e]; fandom:Vorbergland [WFRP 4e pp. 80, 268, 270]; lex:Reikland [SH pp. 77-84]).
- **Averland.** Open plain with few woods, flooded yearly by its border rivers; cattle in the west and centre (stockyards
  at Averheim and Loningbruck), horses, wine in the south-centre and east, mines and furs at the mountain edge
  (fandom:Averland#Geography [SH pp. 43-48]; fandom:Averheim#Economy [SH p. 46; WFRP 3e The Enemy Within pp. 23-26]).
- **The Moot.** Called the best farmland of the central Empire: grain in the north, sheep, goats and apples in the
  south-west, tobacco in the south-east hills (fandom:Mootland#Geography [SH pp. 59-63]; fandom:Greenleaf
  [Archives of the Empire I p. 44]; lex:The_Moot [Empire 4e p. 53; Empire 7e p. 118]).
- **Stirland.** Rolling plain for cattle and crops, densely settled, but poor; sheep on the Stirhügel in the west, wine
  round Wurtbad, the Great Forest along the Stir, and Sylvania in the east (lex:Stirland [SH pp. 7, 85-87];
  fandom:Stirland#Geography [SH pp. 85-89]; fandom:Wurtbad [SH pp. 85-89]).
- **Wissenland.** Good land by the Reik, stone and subsistence farming toward the mountains in the west (wealth from
  mines), sheep grassland east of the Söll in old Solland (fandom:Wissenland#Geography [SH pp. 94-98];
  fandom:Solland#Geography [Archives of the Empire I]).
- **Sylvania.** Thin soil laced with warpstone since 1111 IC, bog, moor and rotted wood, low yields, hunger as a normal
  condition, goats and pigs, a little wool and vegetables from the larger towns (fandom:Sylvania [Night's Dark Masters
  pp. 84-91]; lex:Sylvania [Vampire Counts 7e pp. 20-22; Undead 4e pp. 24-26; Sylvania the Cursed County pp. 4-5, 10]).
- **Marienburg.** No farmland to speak of: the bay is called the city's garden and the source of most of its food, the
  Kleinland heath runs sheep and some cattle, the rest is moor and marsh (fandom:The_Wasteland#Geography
  [Marienburg: Sold Down the River pp. 7-11]; lex:Wasteland [same book pp. 6-10, 16-20]).

Old World Armoury adds the trade view: Reikland is an agricultural centre that improved its farming, the Moot rivals it
with beef, mutton, beer and flour, Middenheim grows just enough for itself, Nuln sells wine
(fandom:Old_World_Trade_and_Economy#Trade_Goods_in_the_Empire [Old World Armoury pp. 12-13]).

### 1.2 Real-world analogue (German lands, c. 1800-1880)

- **How much was farmed.** The first Reich-wide survey (1878) gives arable + garden + vineyard 48.5 %, meadow and pasture
  19.1 %, forest 25.7 %. The spread is the useful part: loess and river country at 55-61 % arable (Anhalt 61.5, Prussian
  Saxony 60.8, Saxe-Weimar 56.0, Kingdom of Saxony 54.3); the Rhine and Main lands at 43-47 % with 31-38 % forest
  (Rhineland 46.5 / 30.7, Württemberg 46.4 / 30.8, Franconia 45.6 / 34.9, Baden 43.1 / 37.6); upland forest states at
  40-41 % arable and 40-45 % forest (Hesse-Nassau, Saxe-Meiningen, Schwarzburg-Rudolstadt); the north-western heath
  and marsh at 32.6 % arable with 45.4 % rough grazing (Hanover) (rw:Germany 1878 [Statistisches Jahrbuch 1880 p. 21]).
  Around 1800 less was ploughed than this: pasture and commons were about 18 % of land and fell to 9.6 % by 1883
  (rw:Germany 1800-1880 [Pfister, Münster lecture notes]).
- **What that means for the fertility step.** Between the best and the most forested German states the arable share
  moves by a factor of about 1.5 (61 % against 40 %), and the heath north-west sits at about two thirds of the Reich
  mean. That is the size of one step (x1.5 / x0.67). I therefore use one step for "forest province" and "garden
  province", and keep two steps for land canon calls cursed, poisoned or abandoned.
- **Rye and wheat.** Vanilla splits Germany the way the 19th century did: rye for the northern plain and the central
  uplands (HANNOVER, WESTPHALIA, BRUNSWICK, HESSE, SAXONY, BRANDENBURG, POMERANIA, MECKLENBURG), wheat for the Rhine,
  the Main and the south (RHINELAND, NORTH_RHINE, BADEN, WURTTEMBERG, BAVARIA, FRANCONIA). Canon names no bread grain
  for the north (its only northern crop text is barley fields at Gladbeich in the Middle Mountain foothills,
  fandom:Gladbeich [Enemy Within vol. 4 The Horned Rat p. 102]), so the rye belt is an analogue call, not canon.
- **Wine.** German viticulture is a river-valley crop south of about 50 N (Rhine, Mosel, Main, Neckar), with
  Saale-Unstrut the northern outlier; the planted area peaked about 1500 and had shrunk since (rw:German wine
  [Wikipedia]). Canon wine country matches: Reikland's Vorbergland, Nuln, Averland, western Stirland. Canon also puts
  wine at Delberz in Middenland, north of anything the analogue supports; I follow canon there for that one state.
- **Cattle drives.** Averland's longhorn drives to city stockyards are the Hungarian Grey trade, not anything Bavarian:
  tens of thousands of head a year walked from the Hungarian plain to Vienna, Augsburg and Nuremberg in the 15th-16th
  centuries, over 100,000 in the 17th (rw:Hungary [https://en.wikipedia.org/wiki/Hungarian_Grey]).
- **Heath and upland sheep.** The Lüneburg Heath is the model for canon's sheep heaths (Kleinland, Stirhügel, old
  Solland, Howling Heights): thin sandy soil, Heidschnucke flocks, turf-manured patches of rye and buckwheat, thinly
  settled, still open heath until Hanover divided the commons after 1831 (rw:Lüneburg Heath
  [https://en.wikipedia.org/wiki/L%C3%BCneburg_Heath]).
- **Netherlands for Marienburg.** The real Holland was drained polder, dairy and bulb-and-flax country living partly on
  traded Baltic rye, with a herring fishery that had collapsed after 1700 (rw:Netherlands
  [https://en.wikipedia.org/wiki/Economic_history_of_the_Netherlands_(1500%E2%80%931815)]); even so about 30 % of the
  country was still heath, peat and drift sand in 1833 (rw:Netherlands 1833 [Thissen 1991, read as a search summary
  only]). Canon Marienburg has the waste without the polders.
- **Transylvania for Sylvania.** Ploughland was only about a tenth of the principality in 1830-51, two-field rotation
  still ruled, and close to a million sheep moved on transhumance (rw:Transylvania [History of Transylvania, MEK]).
- **Tobacco for the Moot.** Tobacco was a real German cash crop on the upper Rhine from the late 16th century
  (Hatzenbühl 1573, Mannheim, Baden); about 30,000 ha late in the 19th century, a third of it in Baden
  (rw:German tobacco [https://de.wikipedia.org/wiki/Tabakanbau_in_Deutschland]).
- **Alpine passes.** Valley-floor grain and hay with summer high pasture; alpine pasture is 35 % of Swiss farmland
  (rw:Alps [https://en.wikipedia.org/wiki/Alpine_transhumance]). Vanilla still gives every Alpine state a farm.

### 1.3 Vanilla calibration

All German, Dutch, Alpine and Transylvanian states are `building_subsistence_farm`. Arable, class
(`vanilla_state_climate_classes.csv`) and crops:

| analogue for | vanilla state | arable | class | crops |
|---|---|---|---|---|
| Reik valley, Nuln | RHINELAND / NORTH_RHINE / BADEN | 55 / 77 / 50 | river plain | wheat, livestock, vineyard |
| Vorbergland, Wurtbad | WURTTEMBERG / FRANCONIA | 70 / 80 | forest-hill | wheat, livestock, vineyard |
| Averland | BAVARIA / CENTRAL_HUNGARY | 65 / 110 | river plain | wheat, livestock, vineyard |
| Stirland | HESSE / SAXONY | 80 / 100 | forest-hill / river plain | rye, livestock, vineyard |
| Middenland, Drakwald | HANNOVER / WESTPHALIA / BRUNSWICK | 60 / 60 / 30 | forest-hill | rye, livestock |
| South Ostland | MECKLENBURG / POMERANIA | 25 / 55 | forest-hill / river plain | rye, livestock |
| Sylvania | NORTHERN_ / SOUTHERN_TRANSYLVANIA | 50 / 50 | forest-hill | wheat, livestock, vineyard (+ silk) |
| Marienburg | HOLLAND / FRIESLAND / GELRE | 30 / 30 / 40 | river plain / forest-hill | rye, livestock |
| passes, Middle Mountains | TYROL / SOUTH_TYROL / SAVOY / EAST_SWITZERLAND | 30 / 30 / 20 / 40 | highland | wheat or rye, livestock, vineyard |

No vanilla German state carries tobacco; OLD_CASTILE, EXTREMADURA and the Balkan states do, so the building is legal on
European farmland.

### 1.4 Where canon and analogue disagree, and which I follow

1. **Marienburg**: the analogue says the richest farmland in northern Europe, canon says a wasteland fed by its bay.
   Canon wins (fishing village, two steps down).
2. **Sylvania**: Transylvania was ordinary mixed farming with wine; canon is cursed ground. Canon wins (two steps down).
3. **Bread grain in the north**: canon silent, analogue says rye. Analogue fills the gap.
4. **Wine in Middenland**: analogue says no, canon names Delberz wines. Canon wins for `STATE_MIDDENLAND_PROPER` only.
5. **Averland**: the name and place suggest Bavaria or Swabia, the canon economy is a Hungarian cattle plain with wine
   hills. Canon wins: livestock first in the crop list.

### 1.5 What the rows do to the realm total

Indicative only (state pixels x vanilla world density of the class x the step multiplier, before the model's world
scaling): the climate layer alone gives these 30 states 1,112; the proposed rows also give 1,112. The rows do not add
land, they move it: about 290 out of the northern forest, Sylvania, the passes and Marienburg, and into the Moot, the
Reik and Aver plains and the Suden Vorbergland. Today's emitted stand-in total for the same states is 1,549.

## 2. Per-state entries

Format: identity; canon; analogue; climate layer (zone shares from `state_climate_index.json` and the class the zone map
gives); proposal; tier. "Indicative" is the unscaled number described in 1.5 (layer -> proposal), for comparison only.

### STATE_WEST_MIDDENLAND — West Middenland

- **Identity.** The Drakwald west of Middenheim toward the Wasteland border. Hubs Bokel, Deinste and Winsen are names
  from the TWW3 Old World table (leads only; none has a wiki article). Owners MID and, for three provinces, BLV (a
  goblin tag). Confidence in "western Drakwald": good, by position between Middenheim and Marienburg.
- **Canon.** Western Middenland is level ground under dense forest; the Drakwald runs from the Wasteland's edge to
  Hochland; beastmen and forest goblins hold the deep wood (fandom:Middenland#Geography [SH pp. 53-58]). The Grand
  Duchy's economy is timber and farming; the forest soils are acid, yet it feeds itself and stores a little grain;
  dairy herds are rare because they draw raiders (fandom:Middenland#Economy [Middenheim: City of the White Wolf
  pp. 120-121]). Exports: timber, wool, iron, copper (lex:Middenland [SH pp. 53-57]). No text on this tract by name.
- **Analogue.** Hanover / Brunswick forest and heath: vanilla:STATE_HANNOVER arable 60, farm, rye livestock;
  vanilla:STATE_BRUNSWICK 30, farm, rye livestock.
- **Climate layer.** Df 100 % -> temperate_forest_hill.
- **Proposal.** `temperate_forest_hill`, step -1, farm, `rye_farm livestock_ranch`. One step down for a province canon
  describes as mostly dark forest on acid soil, a third of it in goblin hands; grain before herds because canon says
  herds are the thing Middenland lacks. Indicative 53 -> 36.
- **Tier B.**

### STATE_MARCHES_OF_COURONNE — Marches of Couronne

- **Identity.** Bretonnian (owner COU), in this file by geography. Hubs Tancred Castle, Chantillon, Landrel Barrow;
  Landrel Barrow is placed "in the March of Couronne" by canon (fandom:Landrel_Barrow [Knights of the Grail p. 70]).
  Confident.
- **Canon.** The Marches take in the northern end of the Grey Mountains and wide plains too dry for most crops, which
  is why their people became Bretonnia's best horse-breeders; greenskin raids from the mountains
  (fandom:Couronne#Marches_of_Couronne [Knights of the Grail pp. 67-70]). Couronne proper, by contrast, is mostly arable.
- **Analogue.** Weak. A dry horse-breeding march has no clean German or French twin; the nearest vanilla shape is a
  western-steppe state with pasture (vanilla western_steppe states: 9 farm, 6 pasture, table 4.2b).
- **Climate layer.** Df 74 %, Dc 26 % -> temperate_forest_hill (humid). Canon says dry.
- **Proposal.** `steppe`, step 0, pasture, `livestock_ranch wheat_farm`. Canon gives both the dryness and the herding
  response in one sentence, so the class swap and the pasture building rest on the same citation. Indicative 44 -> 17.
- **Tier A.** The Bretonnia dossier should carry the same reading for the dukedom's other states.

### STATE_DRAKWALD_FOREST — Drakwald Forest

- **Identity.** South-western Drakwald from Carroburg on the Reik (city hub) north to Fassberg; owners CRB and SCU
  (two provinces, a Skaven clan). The Midden Moors of south-western Middenland fall in or beside it by position.
- **Canon.** A dark mixed forest, conifers on high ground, beastmen within (fandom:Middenland#Geography [SH pp. 53-58];
  fandom:Drakwald_Forest [Beasts of Chaos 6e p. 11; Empire 7e pp. 8-9]). The Midden Moors are an infertile tract of
  hill and wetland, known for trout, not crops (fandom:Middenland#Geography [SH pp. 53-58]; fandom:Midden_Moors
  [Archives of the Empire I p. 10]). Carroburg's page carries no land-use text.
- **Analogue.** vanilla:STATE_BRUNSWICK 30 (Harz and forest), vanilla:STATE_WESTPHALIA 60; Hesse-Nassau 40 % forest in 1878.
- **Climate layer.** Df 100 % -> temperate_forest_hill.
- **Proposal.** `temperate_forest_hill`, step -1, farm, `rye_farm livestock_ranch`. Forest by name and by text, with a
  moor on its western side. Indicative 80 -> 53 (still the largest northern state: it is the biggest by area).
- **Tier A** (the feature is the state). Matches the earlier EMP-04.

### STATE_VORBERGLAND — Vorbergland

- **Identity.** The northern and western Vorbergland with the Bögen valley: hubs Bögenhafen and Eilhart, both canon
  Reikland towns. Confident.
- **Canon.** Vorbergland is rolling hill and fertile valley between the Grey Mountains and the Reikwald; the rivers off
  the mountains carry its farming; the western end is wilder, raided and thinly peopled (fandom:Reikland#Vorbergland
  [SH pp. 77-85; WFRP 4e]; fandom:Vorbergland [WFRP 4e p. 268]). Eilhart is ringed by vineyards and known for white
  wine, lately for hopped beer from local grain (fandom:Eilhart [WFRP 4e p. 281]; lex:Eilhart agrees). Bögenhafen
  trades local wool and wine, hosts the spring livestock fair and a house dealing in grain (fandom:Bögenhafen
  [Shadows over Bögenhafen pp. 6-8; WFRP 4e p. 280]). Hallt nearby grows hops, grain and pumpkins and keeps sheep
  (fandom:Hallt [WFRP 4e Hell Rides to Hallt pp. 3-4]).
- **Analogue.** Baden / Württemberg hill and wine country: vanilla:STATE_WURTTEMBERG 70, farm, wheat livestock vineyard;
  vanilla:STATE_BADEN 50, same crops. Baden 1878: 43 % arable, 38 % forest.
- **Climate layer.** Df 98 % -> temperate_forest_hill. Agrees.
- **Proposal.** `temperate_forest_hill`, step 0, farm, `wheat_farm vineyard livestock_ranch`. The class default would
  give rye and no vines; canon names wine, wheat-country beer grain and wool. Fertile valleys and a wild western half
  cancel out, so no step. Indicative 55 -> 56.
- **Tier A.**

### STATE_AXE_BITE_PASS — Axe Bite Pass

- **Identity.** The pass itself above Helmgart, three provinces (one impassable); owner KZF (Karak Ziflin). Hubs
  Helspire and Castle Drachenfels are both canon ruins "near Axe Bite Pass" (fandom:Helspire [Empire 8e p. 22;
  WFRP 4e p. 287]).
- **Canon.** A sheer-sided valley; the fiefs along it live on tolls and inns, not land; one stretch sees the sun for
  under an hour a day (fandom:Axe_Bite_Pass [Knights of the Grail]). Karak Ziflin, north of the pass, lives on trade,
  iron and metalwork; one of its outlying mines also supplies grain (fandom:Karak_Ziflin [Lords of Stone and Steel
  pp. 19, 24]). No farming text for the pass.
- **Analogue.** Alpine pass valley: vanilla:STATE_TYROL 30, farm, wheat livestock vineyard; vanilla:STATE_SAVOY 20.
- **Climate layer.** Dc 83 %, Df 17 % -> boreal_forest (an altitude reading, not taiga).
- **Proposal.** `highland_alpine`, step -1, pasture, `livestock_ranch`. Class from the name and the text; one step down
  because canon says the pass lords do not live off the land; pasture is the standing dwarf-hold ruling. Canon check on
  that ruling: Lords of Stone and Steel gives Karak Ziflin a grain-producing settlement, so "dwarfs only herd" is not
  strictly true here, but one 300-dwarf mine does not make a grain hold. Indicative 2 -> 2 (floor).
- **Tier B.**

### STATE_REIKWALD_FOREST — Reikwald Forest

- **Identity.** Not mainly forest. Hubs Ubersreik, Grünburg and Dunkelberg (spelt "Dukelberg" in the worksheet) put the
  Suden Vorbergland and the Teufel valley inside this state, with the southern Reikwald between them and the Reik.
  Confident: all three towns are named in the canon text below.
- **Canon.** The south-eastern Vorbergland round Böhrn, Ubersreik, Stimmigen and Dunkelberg is the most fertile and most
  heavily cultivated part of Reikland, thick with farms, villages and vineyards, exporting wine in bulk; farmers are
  pushing the trees back (fandom:Vorbergland [WFRP 4e pp. 80, 268]; fandom:Reikland#Vorbergland). Stimmigen has its
  own apple and cider (fandom:Stimmigen [WFRP 4e p. 282]); Dunkelberg is a livestock and cloth market with bleachfields
  (fandom:Dunkelberg [SH p. 83; WFRP 4e p. 281]); the plain south of Stromdorf grows grain and hops and raises
  short-horned cattle (fandom:Stromdorf [WFRP 3e The Gathering Storm p. 9]); Grünburg's district sells smoked cheese
  (lex:Grunburg [SH p. 82]). The Reikwald itself is oak, pine, elm and beech with bandits, and its hill tracts run
  sheep (fandom:Reikland#Reikwald; fandom:Hägercrybs [WFRP 4e p. 267; SH p. 80]).
- **Analogue.** Upper Rhine and Neckar wine-and-wheat country: vanilla:STATE_ALSACE_LORRAINE 65 and
  vanilla:STATE_RHINELAND 55 (river plain, wheat livestock vineyard); vanilla:STATE_WURTTEMBERG 70.
- **Climate layer.** Df 89 %, Dc 11 % -> temperate_forest_hill.
- **Proposal.** `temperate_forest_hill`, step +1, farm, `wheat_farm vineyard livestock_ranch`. The class stays (it is
  hill country with a real forest in it) but canon's superlative for the Suden Vorbergland earns a step up. I stop
  short of `temperate_river_plain`: the text describes foothill valleys fed by mountain streams, not an alluvial plain.
  Indicative 46 -> 75.
- **Tier A.** Reverses the earlier EMP-06, which capped this state as a forest on its name alone.

### STATE_MOOTLAND — Mootland

- **Identity.** The Moot (owner MOO). Hubs Eicheschatten and Gipfel are canon Moot towns; Gipfel is the tobacco centre
  of the Greenleaf Hills, so the tobacco district is inside the state.
- **Canon.** Possibly the most fertile farmland of the central Empire; rolling open grassland with enough rain for
  reliable good crops; "Auld Styrlande" north of the rivers is the breadbasket; the Aver March in the south-west runs
  large flocks of sheep and goats and is famous for apples (Sauerapfel's orchards go on for miles); the south-east
  hills grow tobacco as a major cash crop (fandom:Mootland#Geography [SH pp. 59-63]; fandom:Gipfel [SH pp. 61-62];
  fandom:Greenleaf [Archives of the Empire I p. 44]; fandom:Sauerapfel [SH pp. 61-62]; lex:The_Moot corroborates the
  soil and harvests). Beef, mutton, beer and flour for export (fandom:Old_World_Trade_and_Economy [Old World Armoury
  p. 13]); Gorbad's horde found wheat fields round every village (fandom:Gorbad_Ironclaw, novel-level detail).
- **Analogue.** A small, intensively farmed lowland: vanilla:STATE_FLANDERS 90 (river plain, wheat livestock) and
  vanilla:STATE_BEKES 80 are the density models; tobacco as on the upper Rhine (rw:German tobacco).
- **Climate layer.** Df 78 %, Dc 22 % -> temperate_forest_hill; the layer has no river signal and reads the heightmap
  ramp at the eastern edge.
- **Proposal.** `temperate_river_plain`, step +1, farm, `wheat_farm livestock_ranch tobacco_plantation vineyard`.
  River plain from the Aver, Aver Reach and Blue Reach meeting here (`canon_rivers.csv` has the Aver row); +1 from the
  canon superlative. Vineyard last on the strength of the Moot's "hearty wines" and sherry (fandom:Wine_Tasting_
  Festival_of_Averheim [Realms of Sorcery p. 231]). Indicative 20 -> 63.
- **Tier A.** Keeps the earlier EMP-01 and adds the crop list.

### STATE_AULD_RYDING — Auld Ryding

- **Identity.** Uncertain. The name appears in neither wiki (dump index, redirects and both live searches). Hubs Hornau
  and Fort Bracher are TWW3 names; Schramleben is canon, a Stirland town on the Dwarf road from Zhufbar that avoids
  Sylvania and goes "south to Schramleben and then through the Moot" (fandom:Stirland#Geography [SH pp. 85-86]). Owner
  VSY; homelands Averlander and Sylvanian. By position (south of Drakenhof, east of the Moot, under the World's Edge) it
  is the tract Night's Dark Masters describes south of Sylvania: barren, stinking marsh and fallow hills, claimed by
  Averland, held by Stirland, ignored by both (fandom:Sylvania#Geography [NDM pp. 84-91]). That match is my inference.
- **Canon.** For that tract, the sentence above. Province level: Stirland and Averland pushed into "less fertile eastern
  regions" up to the mountain foothills (lex:Stirland [SH pp. 13-18]).
- **Analogue.** A Carpathian foothill march: vanilla:STATE_NORTHERN_TRANSYLVANIA 50, farm.
- **Climate layer.** Dc 78 %, BSk 22 % -> boreal_forest with a steppe fringe (heightmap ramp; indicative 6).
- **Proposal.** `temperate_forest_hill`, step -2, farm, `livestock_ranch rye_farm`. Two steps down only because canon
  calls the tract barren and unwanted; if the identification is wrong, drop to -1. Indicative 6 -> 16, close to what
  the earlier draft's `highland_alpine` at step 0 would give (12).
- **Tier C.**

### STATE_EAST_STIRLAND — East Stirland

- **Identity.** Stirland between Wurtbad and the Moot. Hubs Halstedt and Wörden are canon: Halstedt is the nearest
  Stirland town to the Moot's apple village and its main market (fandom:Sauerapfel [SH pp. 61-62]); Wördern is where
  the Moot Road meets the Old Dwarf Road and where Stirhügel shepherds trade (fandom:Stirland#Geography [SH pp. 85-89]).
- **Canon.** Stirland is less wooded than the north, rolling plain used for cattle and crops, thick with villages along
  roads and rivers, yet poor (lex:Stirland [SH pp. 7, 85-87]); counted among the breadbasket provinces
  (fandom:Ostland#Inhabitants [SH pp. 73-76]). Exports woollens, wine, salted fish, woodcraft (lex:Stirland [SH p. 85]).
- **Analogue.** Hesse / Thuringia mixed farming: vanilla:STATE_HESSE 80, farm, rye livestock vineyard; Saxe-Weimar 56 %
  arable in 1878.
- **Climate layer.** Df 100 % -> temperate_forest_hill. Agrees.
- **Proposal.** `temperate_forest_hill`, step 0, farm, `wheat_farm livestock_ranch`. The row only swaps the class
  default's rye for wheat: a "breadbasket" plain next to the Moot. No step: canon balances "densely settled farmland"
  against "poor province". Indicative 51 -> 51.
- **Tier A.**

### STATE_EAST_AVERLAND — East Averland

- **Identity.** Eastern Averland up to Black Fire Pass. Hubs Grenzstadt (fortress town at the pass's western end,
  fandom:Grenzstadt [SH pp. 47-48]) and Pfungzig (road end from the Moot, fandom:Mootland#Geography). Confident.
- **Canon.** In the south-centre and east cattle give way to vines: the best-regarded wines of the province, Grenzstadter
  White among them; the far east trades gems, ore and furs from the foothills (fandom:Averland#Geography [SH pp. 43-48];
  fandom:Grenzstadt [Realms of Sorcery p. 234]). The plains rise in the east to meet the mountains.
- **Analogue.** Franconian wine hills: vanilla:STATE_FRANCONIA 80, farm, wheat livestock vineyard (Franconia 1878: 46 %
  arable, 35 % forest).
- **Climate layer.** Dc 60 %, Df 40 % -> mostly boreal_forest. A heightmap artefact (the earlier draft measured 74 % of
  the state above 1,000 m); canon has no cold forest here.
- **Proposal.** `temperate_forest_hill`, step 0, farm, `vineyard livestock_ranch wheat_farm`. Class swap from the canon
  picture of rising wine country; vineyard first because this is where canon puts the province's wine.
  Indicative 21 -> 44.
- **Tier A.** Keeps EMP-09's class and adds the wine.


### STATE_AVERHEIM — Averheim

- **Identity.** The Aver valley round the provincial capital. Hubs Averheim and Streissen are canon Averland towns; the
  wood hub Einsamholz is a canon Moot town of the Aver March, so the state reaches the Moot's edge.
- **Canon.** Averland is fertile plain watered by the yearly floods of its border rivers, which the people accept as the
  price of abundant crops (fandom:Averland#Geography [SH pp. 43-48]). Cattle are the province's lifeblood and Averheim
  the heart of the trade: drives end in its stockyards, the meat is salted and barged down the Aver; horses are second;
  local vintners and a yearly wine festival; grain, meat and leather go to the dwarf holds (fandom:Averheim#Economy
  [SH p. 46; WFRP 3e The Enemy Within pp. 23, 26]; lex:Averheim and lex:Averland corroborate). A crop blight at
  Streissen caused famine and riots in 2502 IC (fandom:Streissen [SH p. 47]) — a one-year event at game start, not a
  soil fact.
- **Analogue.** vanilla:STATE_BAVARIA 65 (river plain, wheat livestock vineyard) for place;
  vanilla:STATE_CENTRAL_HUNGARY 110 (river plain, wheat livestock vineyard) for the cattle economy.
- **Climate layer.** Df 100 % -> temperate_forest_hill (no river signal).
- **Proposal.** `temperate_river_plain`, step 0, farm, `livestock_ranch wheat_farm vineyard`. River plain from the
  flood text and the Aver row in `canon_rivers.csv`; no step up, because Sigmar's Heirs itself rates the land below
  Ostermark's and values it as grazing. Livestock first. Indicative 43 -> 72.
- **Tier A.**

### STATE_SOLLAND — Solland

- **Identity.** Old Solland / Sudenland east of the Söll, down to the Black Mountains (owner WIS). Hubs Steingart and
  Kroppenleben are canon Wissenland towns (fandom:Steingart [SH p. 98]; fandom:Kroppenleben [SH pp. 96-97]); Wusterburg
  is canon too, though Sigmar's Heirs places it at the meeting of the pass roads. Moasach is a TWW3 name.
- **Canon.** East of the Söll the land is rolling grassland used for sheep; old Solland is famous for wool and for furs
  from the mountains; ruined villages from Gorbad's invasion still stand empty (fandom:Wissenland#Geography
  [SH pp. 94-98]; lex:Wissenland [SH pp. 94-95]). Archives of the Empire gives a north-to-south profile: rich farmland
  near Pfeildorf, then lightly wooded hills, then cattle and sheep country in the foothills, then mines
  (fandom:Solland#Geography [Archives of the Empire I]). An old river village lived on farms and granaries along the
  Sol (fandom:Helmstedt, a short story set in the 12th century IC).
- **Analogue.** Swabian Jura sheep country: vanilla:STATE_WURTTEMBERG 70, farm, wheat livestock vineyard
  (Württemberg 1878: 46 % arable, 18 % grass, 31 % forest).
- **Climate layer.** Df 99 % -> temperate_forest_hill. Agrees.
- **Proposal.** `temperate_forest_hill`, step 0, farm, `livestock_ranch wheat_farm`. The row sets crops only: sheep
  first, wheat for the northern farmland, no rye. No step down: the emptiness canon describes is depopulation (a pops
  matter), not poor soil. Indicative 69 -> 70.
- **Tier A.**

### STATE_WEST_STIRLAND — West Stirland

- **Identity.** Western Stirland with the Stirhügel. Hub Flensburg is canon: a market town west of the Stirhügel living
  on the sheep trade (fandom:Flensburg [SH pp. 85-86]).
- **Canon.** The west of the province is the Stirhügel hill country of barrows and sheep-herding villages that sell at
  Flensburg and Wördern (fandom:Stirland#Geography [SH pp. 85-89]); all wine grown in western Stirland must by decree
  be sold through Wurtbad (fandom:Wurtbad [SH p. 88]).
- **Analogue.** Hessian and Thuringian upland sheep and wine slopes: vanilla:STATE_HESSE 80, farm, rye livestock vineyard.
- **Climate layer.** Df 100 % -> temperate_forest_hill. Agrees.
- **Proposal.** `temperate_forest_hill`, step 0, farm, `livestock_ranch vineyard wheat_farm`. Crops only: sheep first,
  the wine canon assigns to this half of the province, then grain. Indicative 26 -> 26.
- **Tier A.**

### STATE_SOUTH_MIDDENLAND — South Middenland

- **Identity.** Middenland's Talabec bank between Altdorf and Talabheim. Hub Ahlenhof is canon as the Middenland river
  port to which Hochland's southern woodsmen send their logs (fandom:Hochland#Geography [SH pp. 49-52]); Schoppendorf
  has a merchants' guild in a WFRP Companion epigraph. The Howling Hills lie along its north.
- **Canon.** The Drakwald fills the land between Talabec, Reik and Middle Mountains (fandom:Middenland#Geography). The
  Howling Hills run from Middenheim almost to Talabheim: bare rocky tops, sodden heather moor, wooded valleys, a few
  shepherd hamlets on the eastern heights (fandom:Howling_Hills [The Nemesis Crown p. 9]). Province-level economy as
  for West Middenland.
- **Analogue.** Harz and Weser uplands: vanilla:STATE_BRUNSWICK 30, vanilla:STATE_HANNOVER 60 (rye livestock).
- **Climate layer.** Df 100 % -> temperate_forest_hill.
- **Proposal.** `temperate_forest_hill`, step -1, farm, `rye_farm livestock_ranch`. Forest plus a named barren upland.
  Indicative 47 -> 31.
- **Tier B.**

### STATE_SOUTH_OSTLAND — South Ostland

- **Identity.** Ostland south and east of the Middle Mountains. Hubs Wolfenburg (capital) and Wurzen (on the Talabec in
  the far south, fandom:Wurzen [SH p. 76]) are canon.
- **Canon.** Nearly all of Ostland lies under the Forest of Shadows; people clear patches for farms and settlements
  (fandom:Ostland [SH pp. 73-76]). Ostlanders resent the breadbasket provinces, so theirs is not one (same page). The
  Wolfen comes out of the Middle Mountains onto plains near Wolfenburg (lex:Talabec [WFRP Companion p. 22]); the city
  trades timber and pewter (lex:Wolfenburg [SH pp. 75-76]). The bull emblem is read by Lexicanum as heavy use of cattle
  and oxen (lex:Ostland, citing Uniforms & Heraldry pp. 36-39; Fandom does not repeat it). Wide tracts near the Middle
  Mountains were never resettled after Gorthor's invasion (lex:Hochland [Beastmen 7e pp. 27-31]).
- **Analogue.** Baltic forest belt: vanilla:STATE_MECKLENBURG 25, vanilla:STATE_EAST_PRUSSIA 40 (farm, rye livestock).
- **Climate layer.** Df 100 % -> temperate_forest_hill.
- **Proposal.** `temperate_forest_hill`, step -1, farm, `livestock_ranch rye_farm`. One step down for "almost wholly
  forest" and unresettled land; the class default's order (cattle, then rye) already suits the bull province.
  Indicative 72 -> 48.
- **Tier A** (Wolfenburg's plains and timber are text about this state).

### STATE_MIDDLE_MOUNTAINS — Middle Mountains

- **Identity.** The range's core: hubs Castle Lenkster, Karaz Ghumzul and Brass Keep are all canon sites in it; owner BRK.
- **Canon.** Forbidding peaks under dense forest, home to goblins and beastmen, claimed by four provinces and held by
  none; reputed barren even of ore; "a few exceptionally hardy farmers" work the foothills (fandom:Middle_Mountains
  [The Horned Rat Companion pp. 65-67]; lex:Middle_Mountains [same book ch. 9; Beasts of Chaos 6e p. 10]).
- **Analogue.** Harz / Thuringian Forest core, where forest ran to 42-45 % of land even at state scale (Saxe-Meiningen,
  Schwarzburg-Rudolstadt, 1878); vanilla:STATE_SAVOY 20, vanilla:STATE_TYROL 30 (highland, farm).
- **Climate layer.** Df 93 % -> temperate_forest_hill (the heightmap draws almost no relief here).
- **Proposal.** `highland_alpine`, step -1, farm, `livestock_ranch rye_farm`. Class from the name and text; one step
  down on "barren" and "a few hardy farmers"; crops override drops the highland default's wheat and vines.
  Indicative 9 -> 2.
- **Tier A.** Keeps EMP-08's class and adds the step.

### STATE_MIDDENHEIM — Middenheim

- **Identity.** The Grand Duchy's core round the Fauschlag, reaching east to Gruyden, a shrine town Sigmar's Heirs puts
  in Hochland on the Old Forest Road (fandom:Gruyden [SH p. 51]). Owner MID.
- **Canon.** The lands round the rock are not wealthy; their waterways rise from boggy ground; loggers have cut the
  Drakwald back round the Fauschlag and the larger towns; acid soils, yet the duchy feeds itself with some grain to
  spare; little dairy; game on the market stalls; farmers are estate tenants (fandom:Middenland#Lands_around_Middenheim
  and #Economy [Middenheim: City of the White Wolf pp. 119-121]). The city grows just enough for itself
  (fandom:Old_World_Trade_and_Economy [Old World Armoury p. 13]). The Schadensumpf bog lies to the north
  (fandom:Middenland#Geography). A foothill village shows wide barley fields and a grain mill (fandom:Gladbeich).
- **Analogue.** vanilla:STATE_HANNOVER 60, vanilla:STATE_BRUNSWICK 30 (farm, rye livestock).
- **Climate layer.** Df 100 % -> temperate_forest_hill.
- **Proposal.** `temperate_forest_hill`, step -1, farm, `rye_farm livestock_ranch`. Canon's own verdict is "enough and
  a little over" from poor, boggy, acid land; grain first, herds second. Indicative 63 -> 42.
- **Tier A.**

### STATE_REIKLAND_PROPER — Reikland Proper

- **Identity.** Altdorf and the Reik-Talabec confluence, with the Skaag Hills bank (Castle Grauenburg) and the northern
  Hägercrybs. Confident.
- **Canon.** Early Reikdorf had good fisheries, fertile farmland and fine pasture on the alluvial plain, and the
  Unberogens were rich in cattle (fandom:Altdorf#Reikdorf; lex:Altdorf#History agrees). The Talabec arrives heavy with
  black soil from the Middle Mountains and drops it at Altdorf (lex:Reik [WFRP 1e p. 283; Empire 8e pp. 24-26];
  fandom:Middle_Mountains). From north to south Reikland has fertile farmland, vineyards and dairy fields with a
  surplus to export (fandom:Reikland [SH pp. 77-85]); it "perfected advances in farming" (fandom:Old_World_Trade_and_
  Economy [Old World Armoury p. 13]). The Hägercrybs and Skaag Hills are wooded sheep hills (fandom:Hägercrybs).
- **Analogue.** vanilla:STATE_RHINELAND 55, vanilla:STATE_NORTH_RHINE 77, vanilla:STATE_ILE_DE_FRANCE 40 (river plain,
  farm, wheat livestock vineyard).
- **Climate layer.** Df 100 % -> temperate_forest_hill (no river signal).
- **Proposal.** `temperate_river_plain`, step 0, farm, `wheat_farm livestock_ranch vineyard`. The confluence plain is
  the textbook case for the class the layer cannot produce (`canon_rivers.csv` has Reik and Talabec rows). No step: the
  hill tracts inside the state offset the alluvium. Indicative 43 -> 73.
- **Tier A.**

### STATE_HELMGART — Helmgart

- **Identity.** One province: the fortress town at the Reikland end of Axe Bite Pass (owner REI). Certain.
- **Canon.** A fortress and market town cut into the mountainside between two sheer slopes; Bretonnian brandy and wine,
  dwarf metal and Reikland goods change hands there (fandom:Helmgart [SH p. 83; WFRP 4e p. 285]; lex:Helmgart agrees).
  No canon land-use text found.
- **Analogue.** An Alpine customs town: vanilla:STATE_SOUTH_TYROL 30 (4 provinces), highland, farm.
- **Climate layer.** Df 100 % -> temperate_forest_hill.
- **Proposal.** `highland_alpine`, step 0, farm, `livestock_ranch rye_farm`. Class from the canon siting in the
  mountains; no step without land-use text. At 332 px either class lands on the floor of 2. Indicative 5 -> 2.
- **Tier B.**

### STATE_GREY_LADY_PASS — Grey Lady Pass

- **Identity.** One province on the pass above Ubersreik; owner PAR. Hub Sanglac Castle is canon: an abandoned castle
  in the heart of the Grey Mountains in Parravon, taken and lost again by lords and orcs alike (fandom:Sanglac_Castle
  [Knights of the Grail p. 87]).
- **Canon.** Nothing on the castle's land. The Teufeltal on the Reikland side of the same pass is scrubby hillside fit
  for little but sheep, with a few vineyards by Tallerhof (fandom:Teufeltal [WFRP 3e Heroes Call p. 58]). Parravon lies
  almost wholly on rocky peaks and farms what little flat land it has (fandom:Parravon [Knights of the Grail pp. 85-86]).
- **Analogue.** vanilla:STATE_SAVOY 20, highland, farm.
- **Climate layer.** Dc 84 %, Df 16 % -> boreal_forest (altitude).
- **Proposal.** `highland_alpine`, step -1, pasture, `livestock_ranch`. One step down for a castle nobody can hold;
  pasture from the sheep text for the pass's own valley. Indicative 1 -> 1 (floor 2 applies).
- **Tier B.**

### STATE_DRAKENHOF — Drakenhof

- **Identity.** Southern Sylvania under the World's Edge: hubs Castle Drakenhof (the von Carstein seat), Swartzhafen and
  Leicheberg ("Licheburg" in the worksheet) are canon Sylvanian places. Owner VSY. Confident.
- **Canon.** Province level: thin soil laced with warpstone since 1111 IC, low yields, hunger a normal state; damp
  ground full of bogs and moors whose peat manures the fields; harsh winters under the mountain shadow
  (fandom:Sylvania#Geography and #The_Sylvanians [Night's Dark Masters pp. 84-91]). Villagers grow what they can in
  infertile earth and keep thin goats and pigs; only the bigger towns have wool and vegetables to send out
  (lex:Sylvania [Vampire Counts 7e pp. 20-22; Sylvania the Cursed County pp. 4-5, 10]). A cursed vintage is said to come
  from a small vineyard under the World's Edge (fandom:Annaliese [Realms of Sorcery p. 235]): flavour, not an industry.
- **Analogue.** vanilla:STATE_SOUTHERN_TRANSYLVANIA 50, farm, wheat livestock silk vineyard; real Transylvania ploughed
  about a tenth of its land in 1830-51 (rw:Transylvania).
- **Climate layer.** Dc 52 %, Df 31 %, BSk 16 %, ET 1 % -> mostly boreal_forest (the World's Edge ramp bleeding west;
  canon Sylvania is a basin of wood, moor and fen).
- **Proposal.** `temperate_forest_hill`, step -2, farm, `livestock_ranch rye_farm`. Class swap on the canon landscape;
  two steps down because canon says outright that the soil is poisoned and the crops fail. Farm, since canon's word is
  subsistence farming. Indicative 19 -> 20.
- **Tier B** (province text; no land-use text for this valley by name). Matches EMP-03.

### STATE_EAST_SYLVANIA — East Sylvania

- **Identity.** North-eastern Sylvania on the upper Stir: hub Waldenhof is the canon capital of Sylvania, passed by the
  Stir below its source (lex:Stir [Sylvania the Cursed County]; fandom:Waldenhof [SH pp. 86, 88]). Zherden and Eschen
  are TWW3 names. Owner VSY.
- **Canon.** As Drakenhof: province-level text only. The eastern part is called the bleakest, black castles on crags
  over the towns (fandom:Stirland#Geography [SH pp. 85-89]).
- **Analogue.** vanilla:STATE_NORTHERN_TRANSYLVANIA 50, farm, wheat livestock vineyard.
- **Climate layer.** Df 47 %, BSk 43 %, Dc 9 % -> a forest-hill / steppe split (ramp artefact again).
- **Proposal.** `temperate_forest_hill`, step -2, farm, `livestock_ranch rye_farm`. Same reasoning as Drakenhof.
  Indicative 19 -> 14.
- **Tier B.** Matches EMP-03.

### STATE_WEST_SYLVANIA — West Sylvania

- **Identity.** Western Sylvania from Templehof to the Grim Wood: hubs Templehof (the sombre gate town of Sylvania,
  fandom:Stirland#Geography), Vanhaldenschlosse (ruins "in the Grim Wood in western Sylvania", fandom:Vanhaldenschlosse
  [Night's Dark Masters p. 90]) and Fort Oberstyre are canon. Hel Fenn, Hunger Wood and Grim Moor lie in it. Owner VSY.
- **Canon.** Past Siegfriedhof the forest breaks into the Hunger and Grim Woods under unnatural fog and foul weather,
  then the Hel Fenn marsh (fandom:Stirland#Geography [SH pp. 85-89]; fandom:Hel_Fenn [Vampire Counts 8e p. 21]); Grim
  Moor is peat bog and cairns (lex:Sylvania [Vampire Counts 7e pp. 20-22]). Province-level soil and famine text as
  above. One counter-note: Siegfriedhof, on the Stirland side of this border, exports farm produce and timber
  (fandom:Siegfriedhof [The Thousand Thrones p. 174]), so the western edge is the least bad of the county.
- **Analogue.** vanilla:STATE_NORTHERN_TRANSYLVANIA 50.
- **Climate layer.** Df 100 % -> temperate_forest_hill. Class agrees; the layer knows nothing of the curse.
- **Proposal.** `temperate_forest_hill`, step -2, farm, `livestock_ranch rye_farm`. Named marsh, haunted wood and bog on
  top of the county-wide soil text. Indicative 47 -> 21. If Chris wants a gradient across Sylvania, this is the state
  to lift to -1.
- **Tier A** (named features of this state carry the land character). Matches EMP-02.

### STATE_WEST_AVERLAND — West Averland

- **Identity.** Western and central Averland south of the Aver: hub Heideck is canon, the crossroads town at the
  geographic centre of the province with a well-known cattle market (lex:Heideck [SH pp. 46-47]; fandom:Averland
  #Geography). Wuppertal is a TWW3 name. Owner AVE.
- **Canon.** Away from the rivers the plain rises gently to Heideck; the interior is small tenant villages on vast noble
  fiefs; in the west and centre the nobles raise longhorn cattle and drive them yearly to Averheim and Loningbruck;
  Loningbruck has the second-busiest stockyards and a cheap red wine (fandom:Averland#Geography [SH pp. 43-48];
  fandom:Loningbruck [SH p. 44; The Old World RPG Player's Guide p. 179]). The Brigundians' farms once fed their
  neighbours and sold barley to the dwarfs (fandom:Brigundian [The Life of Sigmar p. 50]).
- **Analogue.** vanilla:STATE_BAVARIA 65 and vanilla:STATE_CENTRAL_HUNGARY 110 (river plain, wheat livestock vineyard);
  the droving economy is the Hungarian Grey trade (rw:Hungary).
- **Climate layer.** Df 100 % -> temperate_forest_hill. Canon says few woods.
- **Proposal.** `temperate_river_plain`, step 0, farm, `livestock_ranch wheat_farm vineyard`. Open plain between the
  Aver and the Upper Reik, both of which flood it at the edges (`canon_rivers.csv` has the Aver row). Livestock first:
  this is the cattle half of the cattle province. I considered a step down for the drier interior and did not take
  it: grazing land still counts as arable in the engine (ranches draw on the same budget). Indicative 40 -> 67.
- **Tier A.**

### STATE_WURTBAD — Wurtbad

- **Identity.** The Stir bank round Stirland's capital (hub Wurtbad; Niedling and Klam are TWW3 names). Owner STI.
- **Canon.** Wurtbad sits where the Old Dwarf Road ends at the Stir, in thinning woods at the edge of the Great Forest;
  by decree all wine of western Stirland is sold through it, which earns it the name of the Empire's wine capital;
  vineyards surround the town; an important market for dwarf trade (fandom:Wurtbad [SH pp. 85-89]; lex:Wurtbad
  [SH pp. 86-88] and lex:Great_Forest agree). The north bank strip of the province is the last of the Great Forest
  (fandom:Stirland#Geography).
- **Analogue.** The Main valley round Würzburg: vanilla:STATE_FRANCONIA 80, forest-hill, farm, wheat livestock vineyard.
- **Climate layer.** Df 100 % -> temperate_forest_hill. Agrees.
- **Proposal.** `temperate_forest_hill`, step 0, farm, `vineyard wheat_farm livestock_ranch`. Crops only: vineyard
  first for the one town canon titles after its wine. No river-plain swap: the Stir here runs through forest, and
  canon gives no flood-plain text. Indicative 34 -> 34.
- **Tier A.**

### STATE_MIDDENLAND_PROPER — Middenland Proper

- **Identity.** The Altdorf-Middenheim road corridor from Delberz south to the Reik bank opposite Altdorf (port hub
  "Nordstadt" is the TWW3 name for Altdorf's north side). Hub Delberz is canon. Owner MID.
- **Canon.** Delberz, on the Delb, is a prosperous chartered trading town known for the quality of its local wines
  (fandom:Delberz [SH pp. 53, 56]; lex:Delberz agrees); wine and wool are on Middenland's export list (lex:Middenland
  [SH pp. 53-57]). The Delb runs from the Drakwald through Delberz to the Talabec just above Altdorf (lex:Talabec
  [WFRP Companion p. 22]). Province-level forest and soil text as for West Middenland.
- **Analogue.** vanilla:STATE_WESTPHALIA 60, vanilla:STATE_HESSE 80 (forest-hill, rye livestock, HESSE with vineyard).
  Real viticulture stopped south of here; canon overrides.
- **Climate layer.** Df 100 % -> temperate_forest_hill. Agrees.
- **Proposal.** `temperate_forest_hill`, step 0, farm, `rye_farm livestock_ranch vineyard`. Crops only: the class
  default plus the vines canon names. No step down, unlike the other Middenland states: this is the province's road
  and river corridor with its one "rich" town, and no canon moor or bog is placed in it. Indicative 66 -> 66.
- **Tier B** (the wine is town-level canon; class and step rest on province text).

### STATE_HOCHLAND — Hochland

- **Identity.** The province of Hochland (owner HOC): hubs Hergig (capital), Krudenwald and Fort Schippel (warden's
  fort of the Weiss Hills) are canon. The port hub is named Talabheim, which canon puts in Talabecland on the far
  bank; see open question 6.
- **Canon.** Heavily wooded, the eastern end of the Drakwald; farms on the river banks and round the villages are
  fertile because of the streams off the Middle Mountains, so the province feeds itself and imports only luxuries;
  exports timber and woodcraft, with lumber guilds floating logs to mills at Hergig, Krudenwald, Esk and Bergendorf;
  the Weiss Hills are thinly peopled moor and fen; a people of hunters and fishers (fandom:Hochland#Geography
  [SH pp. 49-52]; lex:Hochland [Uniforms & Heraldry p. 18] agrees on the forest). Land near the Middle Mountains was
  never resettled after Gorthor (lex:Hochland [Beastmen 7e pp. 27-31]).
- **Analogue.** Thuringian Forest states: Saxe-Meiningen 42 % arable, 42 % forest in 1878;
  vanilla:STATE_BRUNSWICK 30, vanilla:STATE_HESSE 80 (rye livestock).
- **Climate layer.** Df 74 %, Dc 26 % -> mostly temperate_forest_hill.
- **Proposal.** `temperate_forest_hill`, step -1, farm, `livestock_ranch rye_farm`. One step down as the forest cap;
  not two, because canon insists the farmed land is good and the province self-sufficient. Indicative 41 -> 36.
- **Tier A.** Matches EMP-06.

### STATE_KREUTZHOFEN — Kreutzhofen

- **Identity.** Western Wissenland between the Söll and the mountains: hubs Kreutzhofen and Meissen are canon towns of
  it (fandom:Kreutzhofen [Archives of the Empire I p. 11; Death's Dark Shadow]; fandom:Meissen [SH p. 97]). The farm
  hub is named for Bugman's Brewery, which canon sets beside the Sol in Wissenland's eastern forest (lex:Josef_Bugman
  [Dwarfs 6e/8e]). Owner WIS.
- **Canon.** Toward the mountains the land turns dry and stony, flint heaped at every field edge; western Wissenland
  has given up all but the barest subsistence farming and lives on mines; snow-melt floods the towns each spring,
  Meissen nearly drowned in 2484 IC (fandom:Wissenland#Geography [SH pp. 94-98]; lex:Wissenland [SH pp. 94-95] agrees
  almost word for word). Kreutzhofen itself has a grain mill, summer field work and a brewery
  (fandom:Kreutzhofen [Death's Dark Shadow pp. 14-32]).
- **Analogue.** Black Forest and Swabian Jura edge: vanilla:STATE_BADEN 50 (Baden 1878: 38 % forest);
  vanilla:STATE_EAST_SWITZERLAND 40 (highland, rye livestock vineyard).
- **Climate layer.** Df 78 %, Dc 22 % -> temperate_forest_hill.
- **Proposal.** `temperate_forest_hill`, step -2, farm, `livestock_ranch rye_farm`. Canon describes poor ploughland,
  not alpine pasture, so I keep the layer's class and take two steps on "barest subsistence farming". The earlier
  draft's `highland_alpine` at step 0 (EMP-10) lands within a quarter of this (indicative 12 against 16), so the
  choice changes the label and the crops more than the number. Indicative 29 -> 16.
- **Tier A.**

### STATE_WISSENLAND — Wissenland

- **Identity.** The Reik and Upper Reik bank from Nuln to Pfeildorf: hubs Nuln, Pfeildorf and Dotternbach are canon.
  Owner WIS.
- **Canon.** Wissenland's farmland is fertile near the Reik (fandom:Wissenland#Geography [SH pp. 94-98]); rich farmland
  lies round Pfeildorf (fandom:Solland#Geography [Archives of the Empire I]); Pfeildorf is the centre of the Sudenland
  wool trade and a fishing town (fandom:Pfeildorf [SH p. 96]; lex:Pfeildorf adds the fishing); Dotternbach in the
  foothills lives on fine wool (fandom:Dotternbach [Children of the Horned Rat pp. 118-122]). Nuln depends on the
  estates and villages around it for food, has a class of "Farmer Barons" with rent-paying tenants, and sells fine
  wines (fandom:Nuln#Inhabitants [Forges of Nuln]; fandom:Old_World_Trade_and_Economy [Old World Armoury p. 13]).
- **Analogue.** Upper Rhine plain: vanilla:STATE_BADEN 50, vanilla:STATE_RHINELAND 55 (river plain, wheat livestock
  vineyard).
- **Climate layer.** Df 100 % -> temperate_forest_hill (no river signal).
- **Proposal.** `temperate_river_plain`, step 0, farm, `wheat_farm vineyard livestock_ranch`. The class comes from
  "fertile near the Reik" plus the Reik, Upper Reik and Sol rows in `canon_rivers.csv`. Indicative 24 -> 40.
- **Tier A.**

### STATE_MARIENBURG — Marienburg

- **Identity.** The city, the Reik mouth and the country south-west of it: farm hub Klessen is the canon village at
  the edge of the Kleinland on the Gisoreux road, mine hub Erlach the canon mining village in the Pale Sisters
  foothills (fandom:The_Wasteland#South [Marienburg: Sold Down the River pp. 9-10]). The rest of the Wasteland is
  `STATE_THE_WASTELAND` in `01_kislev.txt`. Owner MAR.
- **Canon.** The Manaanspoort Zee is called the city's garden and the source of most of its food: haddock, halibut,
  herring; salted fish was its first export (fandom:The_Wasteland#Sea_of_Claws [same book p. 8]; lex:Wasteland
  [pp. 16-20]). Outside the city only scattered hamlets scrape a living, mostly on the Reik's alluvial strip. The
  Kleinland is heath used for sheep, its wool one of the few native exports, and its cattle and sheep are driven to
  the city's butchers (fandom:The_Wasteland#South; fandom:Marienburg [same book]). Halsdorph's one patch of fine
  farmland sank into the swamp. Grootscher Marsh lines the river; the Bitter Moors beyond the road are poisoned.
  No polder or reclamation text exists in either wiki; the only dike is the city's flood wall.
- **Analogue.** vanilla:STATE_HOLLAND 30 (4 provinces, river plain, farm, rye livestock), vanilla:STATE_FRIESLAND 30.
  The real Netherlands still had about 30 % heath and peat waste in 1833 (rw:Netherlands 1833); canon Marienburg is
  that waste without Holland's polders.
- **Climate layer.** Df 88 %, Dc 12 % -> temperate_forest_hill.
- **Proposal.** `temperate_forest_hill`, step -2, fishing village, `livestock_ranch`. Two steps down for a land canon
  names a wasteland; fishing village because canon says the sea feeds the city (the state is coastal); crops cut to
  the ranch because sheep and a few cattle are the only farming canon mentions. Result in play: a very large city on
  little arable, living on fish and imported grain, which is the canon Marienburg. Indicative 38 -> 19.
- **Tier A.** Matches EMP-07.

## 3. Rows

One row per state, file order, 30 rows.

```csv
state_key,lore_class,fertility_step,subsistence,crops,tier,note,source
STATE_WEST_MIDDENLAND,temperate_forest_hill,-1,building_subsistence_farm,building_rye_farm building_livestock_ranch,B,Western Drakwald: dense forest on acid soil; feeds itself; few herds; a third goblin-held,"fandom:Middenland#Geography [Sigmar's Heirs pp. 53-58] ; fandom:Middenland#Economy [Middenheim: City of the White Wolf pp. 120-121]"
STATE_MARCHES_OF_COURONNE,steppe,0,building_subsistence_pasture,building_livestock_ranch building_wheat_farm,A,Plains too dry for most crops; Bretonnia's horse-breeding march,fandom:Couronne#Marches_of_Couronne [Knights of the Grail pp. 67-70]
STATE_DRAKWALD_FOREST,temperate_forest_hill,-1,building_subsistence_farm,building_rye_farm building_livestock_ranch,A,Drakwald proper with the infertile Midden Moors on its west,"fandom:Middenland#Geography [Sigmar's Heirs pp. 53-58] ; fandom:Midden_Moors [Archives of the Empire I p. 10] ; fandom:Drakwald_Forest [Beasts of Chaos 6e p. 11]"
STATE_VORBERGLAND,temperate_forest_hill,0,building_subsistence_farm,building_wheat_farm building_vineyard building_livestock_ranch,A,Fertile foothill valleys; Eilhart white wine; Boegenhafen wool and wine; wild western end,"fandom:Vorbergland [WFRP 4e p. 268] ; fandom:Eilhart [WFRP 4e p. 281] ; fandom:Bögenhafen [Shadows over Bögenhafen pp. 6-8]"
STATE_AXE_BITE_PASS,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch,B,Sheer pass living on tolls; dwarf-held (pasture by standing ruling),"fandom:Axe_Bite_Pass [Knights of the Grail] ; fandom:Karak_Ziflin [Lords of Stone and Steel pp. 19, 24]"
STATE_REIKWALD_FOREST,temperate_forest_hill,1,building_subsistence_farm,building_wheat_farm building_vineyard building_livestock_ranch,A,Holds the Suden Vorbergland: Reikland's most cultivated land and its wine export,"fandom:Vorbergland [WFRP 4e pp. 80, 268] ; fandom:Reikland#Vorbergland [Sigmar's Heirs pp. 77-85] ; fandom:Stromdorf [The Gathering Storm p. 9]"
STATE_MOOTLAND,temperate_river_plain,1,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_tobacco_plantation building_vineyard,A,Best farmland of the central Empire; grain north; sheep and apples south-west; tobacco south-east,"fandom:Mootland#Geography [Sigmar's Heirs pp. 59-63] ; fandom:Greenleaf [Archives of the Empire I p. 44] ; lex:The_Moot [Empire 7e p. 118]"
STATE_AULD_RYDING,temperate_forest_hill,-2,building_subsistence_farm,building_livestock_ranch building_rye_farm,C,Identity inferred: the barren marsh-and-fallow-hill tract south of Sylvania,fandom:Sylvania#Geography [Night's Dark Masters pp. 84-91] ; fandom:Stirland#Geography [Sigmar's Heirs pp. 85-86]
STATE_EAST_STIRLAND,temperate_forest_hill,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch,A,Settled rolling plain for crops and cattle; a breadbasket province but a poor one,"lex:Stirland [Sigmar's Heirs pp. 7, 85-87] ; fandom:Stirland#Geography [Sigmar's Heirs pp. 85-89]"
STATE_EAST_AVERLAND,temperate_forest_hill,0,building_subsistence_farm,building_vineyard building_livestock_ranch building_wheat_farm,A,Averland's wine country (Grenzstadter White); mines and furs at the mountain edge,fandom:Averland#Geography [Sigmar's Heirs pp. 43-48] ; fandom:Grenzstadt [Realms of Sorcery p. 234]
STATE_AVERHEIM,temperate_river_plain,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,A,Flood-watered Aver plain; cattle stockyards; horses; wine festival,"fandom:Averland#Geography [Sigmar's Heirs pp. 43-48] ; fandom:Averheim#Economy [Sigmar's Heirs p. 46; WFRP 3e The Enemy Within pp. 23, 26]"
STATE_SOLLAND,temperate_forest_hill,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm,A,Rolling sheep grassland famous for wool; farmland in the north; ruins from Gorbad,fandom:Wissenland#Geography [Sigmar's Heirs pp. 94-98] ; fandom:Solland#Geography [Archives of the Empire I]
STATE_WEST_STIRLAND,temperate_forest_hill,0,building_subsistence_farm,building_livestock_ranch building_vineyard building_wheat_farm,A,Stirhuegel sheep hills (Flensburg market); western Stirland's wine,fandom:Stirland#Geography [Sigmar's Heirs pp. 85-89] ; fandom:Flensburg [Sigmar's Heirs pp. 85-86] ; fandom:Wurtbad [Sigmar's Heirs p. 88]
STATE_SOUTH_MIDDENLAND,temperate_forest_hill,-1,building_subsistence_farm,building_rye_farm building_livestock_ranch,B,Drakwald on the Talabec bank under the barren Howling Hills,fandom:Middenland#Geography [Sigmar's Heirs pp. 53-58] ; fandom:Howling_Hills [The Nemesis Crown p. 9]
STATE_SOUTH_OSTLAND,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,Forest of Shadows with cleared patches; plains by Wolfenburg; timber; not a breadbasket,fandom:Ostland [Sigmar's Heirs pp. 73-76] ; lex:Talabec [WFRP Companion p. 22] ; lex:Wolfenburg [Sigmar's Heirs pp. 75-76]
STATE_MIDDLE_MOUNTAINS,highland_alpine,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,Barren forested peaks; a few hardy foothill farmers; held by none,fandom:Middle_Mountains [The Horned Rat Companion pp. 65-67] ; lex:Middle_Mountains [Beasts of Chaos 6e p. 10]
STATE_MIDDENHEIM,temperate_forest_hill,-1,building_subsistence_farm,building_rye_farm building_livestock_ranch,A,Poor boggy acid land that just feeds the city; little dairy; timber,fandom:Middenland#Economy [Middenheim: City of the White Wolf pp. 119-121] ; fandom:Old_World_Trade_and_Economy [Old World Armoury p. 13]
STATE_REIKLAND_PROPER,temperate_river_plain,0,building_subsistence_farm,building_wheat_farm building_livestock_ranch building_vineyard,A,Reik-Talabec confluence: alluvial farmland and pasture on black river soil,fandom:Altdorf#Reikdorf ; lex:Reik [WFRP 1e p. 283; Empire 8e pp. 24-26] ; fandom:Reikland [Sigmar's Heirs pp. 77-85]
STATE_HELMGART,highland_alpine,0,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,Fortress and market town in the pass mouth; no canon land-use text found,fandom:Helmgart [Sigmar's Heirs p. 83; WFRP 4e p. 285]
STATE_GREY_LADY_PASS,highland_alpine,-1,building_subsistence_pasture,building_livestock_ranch,B,Abandoned castle in the high Grey Mountains; the pass's valley is sheep scrub,fandom:Sanglac_Castle [Knights of the Grail p. 87] ; fandom:Teufeltal [WFRP 3e Heroes Call p. 58]
STATE_DRAKENHOF,temperate_forest_hill,-2,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,Sylvania: warpstone-laced thin soil; bog and moor; low yields; goats and pigs,"fandom:Sylvania#Geography [Night's Dark Masters pp. 84-91] ; lex:Sylvania [Vampire Counts 7e pp. 20-22; Sylvania the Cursed County pp. 4-5, 10]"
STATE_EAST_SYLVANIA,temperate_forest_hill,-2,building_subsistence_farm,building_livestock_ranch building_rye_farm,B,Sylvania round Waldenhof: same poisoned soil; the bleakest eastern part,fandom:Sylvania#Geography [Night's Dark Masters pp. 84-91] ; fandom:Stirland#Geography [Sigmar's Heirs pp. 85-89]
STATE_WEST_SYLVANIA,temperate_forest_hill,-2,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,Hel Fenn marsh; Hunger and Grim Woods; Grim Moor peat bog; county-wide famine,fandom:Stirland#Geography [Sigmar's Heirs pp. 85-89] ; fandom:Hel_Fenn [Vampire Counts 8e p. 21] ; fandom:Sylvania#The_Sylvanians [Night's Dark Masters pp. 84-91]
STATE_WEST_AVERLAND,temperate_river_plain,0,building_subsistence_farm,building_livestock_ranch building_wheat_farm building_vineyard,A,Open plain of tenant villages and longhorn herds; Heideck cattle market,fandom:Averland#Geography [Sigmar's Heirs pp. 43-48] ; lex:Heideck [Sigmar's Heirs pp. 46-47] ; fandom:Loningbruck [Sigmar's Heirs p. 44]
STATE_WURTBAD,temperate_forest_hill,0,building_subsistence_farm,building_vineyard building_wheat_farm building_livestock_ranch,A,Wine capital of the Empire: vineyards round the town at the Great Forest's edge,fandom:Wurtbad [Sigmar's Heirs pp. 85-89] ; lex:Wurtbad [Sigmar's Heirs pp. 86-88]
STATE_MIDDENLAND_PROPER,temperate_forest_hill,0,building_subsistence_farm,building_rye_farm building_livestock_ranch building_vineyard,B,Altdorf-Middenheim road corridor in the Drakwald; Delberz known for its wines,"fandom:Delberz [Sigmar's Heirs pp. 53, 56] ; fandom:Middenland#Economy [Middenheim: City of the White Wolf pp. 120-121]"
STATE_HOCHLAND,temperate_forest_hill,-1,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,Mostly forest; fertile riverside farms keep it self-sufficient; exports timber,fandom:Hochland#Geography [Sigmar's Heirs pp. 49-52] ; lex:Hochland [Uniforms & Heraldry p. 18]
STATE_KREUTZHOFEN,temperate_forest_hill,-2,building_subsistence_farm,building_livestock_ranch building_rye_farm,A,Western Wissenland: stony dry fields; barest subsistence farming; wealth from mines,fandom:Wissenland#Geography [Sigmar's Heirs pp. 94-98] ; lex:Wissenland [Sigmar's Heirs pp. 94-95]
STATE_WISSENLAND,temperate_river_plain,0,building_subsistence_farm,building_wheat_farm building_vineyard building_livestock_ranch,A,Fertile Reik bank from Nuln to Pfeildorf; Nuln wines; Pfeildorf wool market,fandom:Wissenland#Geography [Sigmar's Heirs pp. 94-98] ; fandom:Solland#Geography [Archives of the Empire I] ; fandom:Pfeildorf [Sigmar's Heirs p. 96]
STATE_MARIENBURG,temperate_forest_hill,-2,building_subsistence_fishing_village,building_livestock_ranch,A,Fed by the Manaanspoort fishery; Kleinland sheep heath; marsh and moor; no polders in canon,fandom:The_Wasteland#Geography [Marienburg: Sold Down the River pp. 8-10] ; lex:Wasteland [Marienburg: Sold Down the River pp. 6-10 and 16-20]
```

## 4. Disagreements

### 4.1 With the climate layer's reading

| state | layer reads | proposal | reason |
|---|---|---|---|
| Mootland, Averheim, West Averland, Reikland Proper, Wissenland | temperate_forest_hill | temperate_river_plain | The layer has no river signal. Canon gives flood plain or alluvium for each (Aver floods, Reik-Talabec confluence, "fertile near the Reik") and `canon_rivers.csv` has the river rows. |
| Marches of Couronne | temperate_forest_hill (Df 74 %) | steppe, pasture | Canon: plains too dry for most crops, a horse-breeding march. |
| East Averland, Drakenhof, East Sylvania, Auld Ryding | mostly boreal_forest (Dc) with BSk fringes | temperate_forest_hill | The Dc/BSk shares follow the heightmap's World's Edge ramp, which runs too far west; canon has wine hills (East Averland) and a wooded, boggy basin (Sylvania). This is also a note for the heightmap owner, as EMP-03 and EMP-09 already said. |
| Axe Bite Pass, Grey Lady Pass | boreal_forest (Dc 83-84 %) | highland_alpine | Cold-by-altitude is being read as taiga. They are passes. |
| Middle Mountains, Helmgart | temperate_forest_hill (Df 93-100 %) | highland_alpine | The opposite artefact: canon mountains the heightmap draws low. |
| Reikwald Forest (+1), Mootland (+1) | step 0 | step up | Canon superlatives (most cultivated land in Reikland; best farmland of the central Empire). |
| West / South Middenland, Middenheim, Drakwald Forest, Hochland, South Ostland (-1) | step 0 | step down | Canon forest provinces with acid soil, moor or unresettled land. |
| the three Sylvania states, Kreutzhofen, Marienburg, Auld Ryding (-2) | step 0 | two steps down | Canon says the land fails: poisoned soil, barest subsistence, wasteland, barren tract. |
| Marienburg | farm | fishing village | Canon: the bay feeds the city. |
| Axe Bite Pass, Grey Lady Pass, Marches of Couronne | farm | pasture | Dwarf-hold ruling; sheep-scrub valley; horse-breeding march. |

Six states keep the layer's class and step and change only the crop list: Vorbergland, East Stirland, West Stirland,
Wurtbad, Solland, Middenland Proper.

### 4.2 With the earlier part-A leads (`state_climate_classes.csv`, `agro_climate_overrides_draft.md`)

- **EMP-01 Mootland**: kept (river plain, up one), crop list added (wheat, livestock, tobacco, vineyard).
- **EMP-02 / EMP-03 Sylvania**: kept (forest-hill, two down). I rate Drakenhof and East Sylvania tier B rather than A:
  the text is county-level.
- **EMP-04 Drakwald**: kept for `STATE_DRAKWALD_FOREST`; extended by the same reasoning to West Middenland, South
  Middenland and Middenheim, which part A left at step 0. `STATE_THE_BLACK_PIT` is no longer in this file.
- **EMP-05 Great Forest, EMP-11 Barren Hills**: those states are in `01_kislev.txt` now; not assessed here.
- **EMP-06 other named forests**: kept for Hochland. **Reversed for `STATE_REIKWALD_FOREST`**: the state holds
  Ubersreik, Grünburg and Dunkelberg, that is the Suden Vorbergland, so the forest cap by name was wrong; it goes up
  one instead of down one.
- **EMP-07 Marienburg**: kept (fishing village) and sharpened to two steps down, crops cut to the ranch. I looked for
  polder text again in the full Fandom dump and found none; the earlier refusal to apply a polders-up stands.
- **EMP-08 Middle Mountains**: class kept, one step down added on "barren" and "a few hardy farmers".
- **EMP-09 East Averland**: class kept; the open question it raised is answered by canon: this is the province's wine
  country, so forest-hill with vineyard first, not an extension of the river plain.
- **EMP-10 Kreutzhofen**: changed from `highland_alpine` step 0 to `temperate_forest_hill` step -2. Similar number,
  different label: canon describes stony ploughland abandoned to subsistence, not alpine pasture.
- **Part-A class rows not in the draft**: Marches of Couronne `steppe` kept, pasture added. Helmgart changed from
  forest-hill to highland (canon sites it in the mountains). Auld Ryding changed from `highland_alpine` ("no lore") to
  forest-hill two down on an inferred identification. Solland, Stirland states, Vorbergland: class kept, crops set.

## 5. Open questions for Chris

1. **Auld Ryding.** The name is in neither wiki. I read the state as the barren tract south of Sylvania that Night's
   Dark Masters says Averland claims and Stirland holds. Is that what you drew? If it is instead ordinary east
   Stirland along the Schramleben road, the step should be -1, not -2.
2. **Sylvania gradient.** All three states sit at -2 on county-wide text. West Sylvania borders Siegfriedhof, which
   exports farm produce. Do you want West Sylvania at -1 so the curse deepens eastward, or uniform?
3. **Averland's interior.** Both Averheim and West Averland are river plain at step 0. Canon's interior is grazing
   rather than tillage. Is river-plain density right for West Averland, or should the interior be one step down
   (67 -> 45 indicative)?
4. **Tobacco in the Moot.** Canon makes it a major cash crop; `building_tobacco_plantation` exists in the mod. Vanilla
   gives no German state tobacco. Yes or no on adding it?
5. **Middenland wine.** Canon names Delberz wines and lists wine among Middenland's exports, north of any real-world
   vineyard belt. I put a vineyard third in Middenland Proper only. Keep, or drop as flavour?
6. **Hochland's port hub is "Talabheim".** Canon Talabheim is Talabecland's capital on the south bank, and its crater
   holds fertile farmland. If the Taalbaston really lies inside `STATE_HOCHLAND` on your map, the state deserves step 0
   instead of -1; if the hub name is only a nearest-settlement label, -1 stands. Which is it?
7. **Dwarf pasture ruling on Axe Bite Pass.** Lords of Stone and Steel p. 24 gives Karak Ziflin a mine that also
   supplies grain. I kept pasture (one small settlement). Say if you would rather count Karak Ziflin with the grain
   holds.
8. **Non-Imperial states in this file.** Marches of Couronne (COU) and Grey Lady Pass (PAR) are Bretonnian and are
   also the Bretonnia dossier's business by culture. The rows here should win for these keys, or be reconciled with
   that dossier: your call which file is authoritative.
9. **Streissen 2502.** Canon has a crop blight, famine and riots at Streissen in the start year. Out of scope for
   arable; flagged in case you want an event.
10. **Rye in the north.** No canon bread grain exists for Middenland, Hochland or Ostland. Rye is the German analogue
    and vanilla's choice. Confirm you accept an analogue-only crop there.

## 6. Pages read

**Fandom dump, `sources/wiki/pages/` (primary, 2026-11-20).** Read in full or by section: Averheim, Axe Bite Pass,
Castle Lenkster, Couronne, Delberz, Dotternbach, Dunkelberg, Eicheschatten, Flensburg, Gipfel, Gladbeich, Greenleaf,
Grenzstadt, Gruyden, Hallt, Hel Fenn, Helmgart, Helmstedt, Helspire, Hochland, Howling Hills, Hägercrybs, Karak Ziflin,
Kroppenleben, Landrel Barrow, Leicheberg, Loningbruck, Meissen, Midden Moors, Middle Mountains, Montfort, Old World
Trade and Economy, Ostland, Parravon, Pfeildorf, Sanglac Castle, Sauerapfel, Schramleben, Siegfriedhof, Steingart,
Stimmigen, Streissen, Stromdorf, Tallerhof, Templehof, Teufeltal, Vanhaldenschlosse, Waldenhof, Weiss Hills, Wine
Tasting Festival of Averheim, Wissenburg, Wolfenburg, Wurtbad, Wurzen, Wördern, Annaliese, Brigundian. Keyword-searched
(land-use lines only): Altdorf, Bögenhafen, Brass Keep, Carroburg, Castle Drachenfels, Castle Drakenhof, Chantillon,
Drakwald Forest, Forest of Shadows, Fort Oberstyre, Great Forest, Grey Mountains, Kreutzhofen, Marienburg, Middenheim,
Nuln, Reikwald Forest, Schloss Grauenberg, Talabheim, The Empire, The Wasteland, Ubersreik, plus a crop-word scan of
every article in the Empire province categories (hits used: Eilhart, Gorbad Ironclaw, Mootland, Reikland, Vorbergland,
Middenland, Karak Azgaraz, Blood Wine). Black Venom was opened and is unrelated (a Tilean poison).

**Fandom live site (2026-11-19, before the dump existed).** Averland, Reikland, Wissenland, Stirland, Middenland,
Hochland, Ostland, Mootland, Sylvania, The Wasteland, Vorbergland, Solland, Grootscher Marsh, Hägercrybs, Skaag Hills,
Midden Moors, Howling Hills, Weiss Hills, Drakwald Forest, Reikwald Forest, Wine, Livestock, Tobacco, Beer, Old World
Trade and Economy.

**Lexicanum (2026-11-19).** 54 pages, all read before the 30-page cap was set: The Empire, Averland, The Moot,
Reikland, Wissenland, Stirland, Middenland, Hochland, Ostland, Sylvania, Solland, Drakwald, Reikwald Forest, Great
Forest, Middle Mountains, Grey Mountains, Axe Bite Pass, Helmgart, Farmer, Wasteland, Marienburg, Reik, Aver, Stir,
Sol, Talabec, Rivers of The Empire, Aver Reach, Altdorf, Wurtbad, Middenheim, Carroburg, Nuln, Averheim, Bögenhafen,
Ubersreik, Grunburg, Eilhart, Kemperbad, Hergig, Wolfenburg, Talabheim, Pfeildorf, Wissenburg, Kreutzhofen, Meissen,
Wusterburg, Grenzstadt, Heideck, Streissen, Delberz, Schramleben, Eicheschatten, Josef Bugman. Same-origin fetches
began returning the Cloudflare challenge (HTTP 403) that day; the last fourteen pages were read by ordinary page
navigation. No Lexicanum page was opened on 2026-11-20, under the new rule.

**Corroboration status.** Agreed on both wikis: Averland cattle, horses and wine; the Moot's soil; Reikland's exports;
the whole Wissenland land text; Stirland's plains, exports and Wurtbad wine; Sylvania's infertility; Middenland's
exports and Delberz wines; Hochland's forest; the Wasteland's Kleinland and fishery; Averheim's stockyards; Eilhart's
vineyards; Pfeildorf's wool; Heideck's cattle market. **Dump only, not corroborated on Lexicanum:** the Moot's three
sub-regions and tobacco; Vorbergland and Suden Vorbergland; Middenland's acid soils and lack of dairy; Hochland's
self-sufficiency; Solland's north-to-south profile; the Middle Mountains' "hardy farmers"; the Marches of Couronne's
dry plains; Teufeltal; the barren tract south of Sylvania; Stromdorf; Hallt; Karak Ziflin's grain; the Old World
Armoury trade paragraph. **Lexicanum only:** Ostland's bull read as cattle country; the Wolfen's "plains" by
Wolfenburg; the Talabec's black soil. **Disputed:** Lexicanum says the Reikwald is mainly coniferous and bounded by
the Middle Mountains; Fandom says oak, pine, elm and beech between the Reik and the Grey Mountains. I follow Fandom
(the Middle Mountains bound is a plain slip); nothing in a row depends on it.

**Web (real-world half).**
- https://digi.bib.uni-mannheim.de/fileadmin/statjahrb/514401303_1880/pdf/514401303_0027.pdf (Statistisches Jahrbuch für das Deutsche Reich 1880, p. 21: land use by state, 1878; read as a page image)
- https://www.wiwi.uni-muenster.de/wisoge/sites/wisoge/files/downloads/skripte/Grundlegung_Moderne/s06_landwirtschaft_19._jh.pdf (U. Pfister, lecture notes on German agriculture in the 19th century)
- https://en.wikipedia.org/wiki/German_wine
- https://en.wikipedia.org/wiki/Agriculture_in_Germany (thin; regional pattern only)
- https://en.wikipedia.org/wiki/Hungarian_Grey
- https://en.wikipedia.org/wiki/Alpine_transhumance
- https://en.wikipedia.org/wiki/L%C3%BCneburg_Heath
- https://en.wikipedia.org/wiki/Economic_history_of_the_Netherlands_(1500%E2%80%931815)
- https://de.wikipedia.org/wiki/Tabakanbau_in_Deutschland
- https://www.mek.oszk.hu/03400/03407/html/304.html (History of Transylvania, agriculture 1770-1830)
- Search summaries only, not opened: Thissen 1991 on Dutch waste land in 1833; Bittermann 1956 pasture shares.
- Failed: Britannica Germany agriculture (403); statistik-bw.de monthly (unreadable PDF); a Wikipedia Netherlands 1815-39 URL (404).

**Could not do.** No 1800-1850 land-use table for the German states (1878 is the earliest state-level survey found;
the 1800 figure is a national estimate). No vanilla pixel areas for the analogue states, so the analogue comparison is
on per-state arable, not density. The "indicative" numbers are unscaled and will move with the model's world scaling.
