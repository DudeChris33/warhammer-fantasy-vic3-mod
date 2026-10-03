# Arable land: engine mechanics and vanilla calibration

| Field | Value |
|-------|-------|
| Type | findings |
| Status | complete (build); numbers regenerate with `--check` |
| Date | 2026-10-02 |
| Parent | #3675 Arable land and subsistence (epic) |
| Board | #3676 |
| Measured against | Victoria 3 1.13.11 (`.metadata/metadata.json:7` and the install's `launcher/launcher-settings.json` `rawVersion` agree) |
| Consumers | #3677 (climate model), #3678 (tooling), the future population epic, #2968 (province terrains), the #4921 arable heatmap |

Citation conventions: `file:line` paths are relative to this repo unless prefixed `vanilla` (the read-only install under `game/`); `docs/*.log` are the game-generated references. Where the mod's own file differs from vanilla the mod file is cited and the offset is stated.

## 1. Scope

What farmland does in the game, measured from primary sources: how `arable_land` caps rural buildings, how it silently feeds the peasants who fill unclaimed land, what it pulls on (population, migration, pollution, slave imports), and what the five subsistence buildings produce and where vanilla puts them. The second half is a calibration table, measured by script against the vanilla install, by the eleven climate classes fixed in section 4, plus the recommended basis for this map and a ruling on whether vanilla's five subsistence types cover the Warhammer peoples.

Out of scope: assigning any state's value (#3677), the biome model, authoring buildings, production methods or state traits, and any change to the #4921 heatmap. Nothing here is loaded by the game.

Every pops-per-arable figure is vanilla's own 1836 `common/history/pops` and is labelled as such; this mod starts 2512.1.1 (`common/defines/00_wh_defines.txt:13`).

## 2. Engine mechanics

### 2.1 Arable land is the shared level budget of the rural building groups

- `land_usage = rural` on `bg_agriculture` (`common/building_groups/00_building_groups.txt:90-93`), `bg_ranching` (`:142-145`) and `bg_plantations` (`:190-193`). The file's own key reference says `rural = Arable Land` and that an unspecified group takes the first non-default usage found up its parent tree (`:18-19`). That is how the two subsistence groups, which declare `parent_group = bg_agriculture` / `bg_ranching` (`:121`, `:169`), draw on the same budget.
- The two subsistence groups `bg_subsistence_agriculture` (`:120-138`) and `bg_subsistence_ranching` (`:168-186`) set `always_possible = yes`, `auto_place_buildings = yes` (`:125`, `:173`), `is_subsistence = yes` (`:127`, `:175`), `cash_reserves_max = 0` and `hires_unemployed_only = yes`, with `default_building` the farm (`:131`) and the pasture (`:179`). Vanilla's file is 6 lines earlier for all of these (this mod's copy carries a 6-line header and drops the `bg_monuments` `default_building`, which is irrelevant to arable; every line number above is the mod file's).
- The concept text states the consequence: arable land "must be shared between the building types that require it" and the amount "unused by other buildings may be used for subsistence buildings" (vanilla `localization/english/concepts_l_english.yml:837`); subsistence buildings "operate on any unclaimed arable land and do not require manual construction" (`:705`); a resource potential caps a building either per resource or "by the state's amount of arable land" (`:1579`).
- `create_building` accepts `level = arable_land`, "the necessary level to exhaust all available arable land in the state" (`docs/effects.log:835-837`).
- Where the number lives: a vanilla state region carries `subsistence_building`, `arable_land` and `arable_resources` (the rural building types it may host), e.g. vanilla `map_data/state_regions/00_west_europe.txt:3,11,12` (Svealand: pasture, 30, rye farm and livestock ranch). This mod's generator sets every land state to `building_subsistence_farm`, `arable_land = 10` and the same two resources (`mapgen/generate_land_regions.py:171-173`, carried by the `Economics` dataclass at `mapgen/worldgen/schema.py:1444`); all 524 land states in `map_data/state_regions/*.txt` read that way, so the current placeholder total for the 343 drawn states is 3,430 arable.
- Script surface: `arable_land` (trigger, state scope, `docs/triggers.log:8466`), `arable_land_country` (sums all states, `:8473`), `free_arable_land` (building scope, `:9618`), `is_subsistence_building` (building scope, `:12210`), and `add_arable_land` (effect, **state_region** scope, not state: `docs/effects.log:36-38`).

### 2.2 Peasants per level and the production-method tiers

Subsistence buildings are not buildable, expandable or downsizeable (`common/buildings/12_subsistence.txt:14-16`, repeated per building), have `min_raise_to_hire = 0.30` and `slaves_role = peasants` (`:17-18`, `:40-41`, `:62-63`, `:84-85`, `:106-107`). Employment per level is a `level_scaled` `building_employment_peasants_add`: 5,000 for farm, orchard, pasture and fishing village (`common/production_methods/12_subsistence.txt:13`, `:159`, `:223`, `:286`) and 10,000 for rice (`:349`). So a state's peasant capacity in subsistence is `arable x 5,000` (`x 10,000` for rice) minus whatever levels the other rural buildings take.

Each building has three production-method groups (`common/production_method_groups/12_subsistence.txt`): the base method (goods outputs, section 3), a home-workshop pair (`pm_home_workshops_no_*`, unlocked by `law_collectivized_agriculture`, halves the base goods; `pm_home_workshops_*`, which adds clothes, furniture and liquor and is disallowed under that law) and a serfdom group. The farm's serfdom group has five methods: `pm_serfdom_no`, `pm_serfdom` (`law_serfdom`, grain +0.5), `pm_corvee_labor`, `pm_peasant_proprietorship_building_subsistence` (employment -50 peasants, +50 farmers per level, `:101-104`) and `pm_homesteading_building_subsistence` (-100/+100, `:123-126`); the other four buildings carry one serfdom method each. `building_subsistence_output_add` (flat, `unscaled`: 3 or 4 per method) is the in-kind income that is not paid from building revenue (concept `:815`; modifier `docs/modifiers.log:118`, mult `:122`).

Mod versus vanilla: `common/production_methods/12_subsistence.txt` differs in two law ids only. `pm_serfdom_no` (`:48-61`) lacks vanilla's `law_latifundias` / `law_expanded_latifundias`, and `pm_corvee_labor` (`:63-66`) unlocks with `law_serfdom` where vanilla has `law_manorialism`. Outputs and employment are identical. `common/buildings/12_subsistence.txt` and `common/static_modifiers/00_code_static_modifiers.txt` are byte-identical to vanilla.

### 2.3 Population, migration and the defines that read arable

All in vanilla `common/defines/00_defines.txt` (this mod's `common/defines/00_wh_defines.txt` overrides none of them):

- `LOW_POP_THRESHOLD = 5000` and `HIGH_POP_THRESHOLD = 100000` are pops per arable land that trigger the low-pop and high-pop modifiers (`:1471-1472`).
- `MASS_MIGRATION_TARGET_MIN_ARABLE_LAND = 10`: a state needs at least 10 arable to be a mass-migration target (`:1575`; concept `:1298`).
- Migration pull from available subsistence employment is 2 percent per step, capped at 10 (`:1554-1555`), against 30 and 30 for non-subsistence jobs (`:1552-1553`): free peasant slots in subsistence pull weakly.
- `DEFAULT_SUBSISTENCE_BUILDING = "building_subsistence_farm"` (`:32`); the AI's colonisation weight reads arable as well (`common/defines/00_ai.txt:685`, `COLONY_ARABLE_LAND_WEIGHT = 10`).

### 2.4 Pollution

The formula is stated at `:401`: pollution impact = generated pollution of the state region / (`POLLUTION_TARGET_DIVISOR_BASE` + `POLLUTION_TARGET_DIVISOR_ARABLE_LAND_MULT` x sqrt(arable land of the state region)) / `POLLUTION_MAX`, with base 50 and multiplier 1.5 (`:402-403`). It is a square root, so arable 10, 100 and 500 give divisors of about 54.7, 65.0 and 83.5: arable dilutes pollution gently, and the concept text says the same ("the more arable land a state region has, the lower the impact", concept `:2022`).

### 2.5 Slave trade

`SLAVE_TRADE_ARABLE_LAND_EFFECT = 1` adds one slave per week for each arable land in the importing state, capped by `SLAVE_TRADE_ARABLE_LAND_EFFECT_MAX = 200` (`:591-592`), on a base of 100 per marker (`:590`); importing needs at least 500 non-subsistence vacancies (`:580`). Slaves in subsistence buildings consume goods multiplied by `SLAVE_BASKET_SUBSISTENCE_GOODS_MULT = 0.05` (`:567`), and every subsistence building sets `slaves_role = peasants` (section 2.2), so slaves fill peasant slots. This mod ships the five slavery laws at `common/laws/02_slavery.txt:5, 101, 151, 224, 316`.

### 2.6 Reservation modifiers and the mod's land-reform laws

`state_minimum_incorporated_subsistence_arable_land_add` is the minimum fraction of an incorporated state's arable reserved for subsistence buildings (`docs/modifiers.log:1819`); `building_minimum_incorporated_subsistence_employment_add` protects subsistence employment (`:78`); `building_unincorporated_subsistence_output_mult` scales output in unincorporated states (`:138`). The mod's `common/laws/01_land_reform.txt` applies them: `law_serfdom` 0.75 reserved and 0.5 protected employment (`:39-40`), `law_tenant_farmers` 0.25 (`:68`; the employment line is commented out at `:69`), `law_peasant_proprietorship` 0.35 (`:219`), `law_homesteading` 0.35 (`:285`). Vanilla's `law_manorialism` (0.5, vanilla `common/laws/01_land_reform.txt:121`) and the latifundia laws do not exist in this mod, which renames the same slot `law_serfdom`.

### 2.7 `low_pop_state` and the inert `HIGH_POP_THRESHOLD`

`low_pop_state` is a **bonus**: `state_birth_rate_mult = 0.5` (vanilla `common/static_modifiers/00_code_static_modifiers.txt:689-692`, comment at `:688`; loc "Sparsely Populated", vanilla `localization/english/core_l_english.yml:125`). Vanilla ships a loc string `high_pop_state "Overpopulated"` (`core_l_english.yml:138`) but no `high_pop_state` modifier anywhere under `common/` or `gui/`, and this mod's verbatim static-modifier file likewise lacks it, so `HIGH_POP_THRESHOLD` has no scripted consequence in 1.13.11 (inferred from the absent definition; the define's comment says it applies "the high pop modifier"). In vanilla 1836, 141 of 675 states sit below 5,000 pops per arable (table 4.0: frontier Americas, Siberia, Australia) and none is above 100,000. A `high_pop_state` definition is a design choice for the population epic; no item is filed from here.

### 2.8 State traits (record only; the mod's own `common/state_traits/` holds only `00_generic_traits.txt`, which differs, so these are vanilla paths)

- `good_soils`: `building_group_bg_agriculture_throughput_add = 0.1` (and plantations) (vanilla `common/state_traits/00_generic_traits.txt:36-41`); `black_soil` 0.15 (`06_eastern_europe_traits.txt:9-15`).
- Most river traits are infrastructure and market access only: Rhine (`05_western_europe_traits.txt:50-56`), Seine (`:86-91`), Euphrates and Yangtze likewise.
- The exceptions carry an agriculture throughput bonus of 0.2: `nile_river` (`07_africa_traits.txt:9-16`), `mesopotamian_floodplain` (`08_near_east_traits.txt:88-95`, the bonus at `:92-93`) and `indus_valley` (`09_india_traits.txt:1-8`).
- No vanilla trait mentions `arable` at all: traits change throughput, never the arable number itself.

## 3. The five subsistence buildings

Base production-method outputs per level of workforce (`common/production_methods/12_subsistence.txt`, the `workforce_scaled` block of each `default_building_*`; file comments give a notional value of 55 per 5,000 peasants, 100 for rice's 10,000):

| building | employment per level | goods (add) | base PM | home-workshop PMs | serfdom PMs |
|---|---|---|---|---|---|
| `building_subsistence_farm` | 5,000 | grain 1.0, fabric 0.5, wood 0.5, services 0.5 | `:1-16` | `:18-46` | `:48-144` (five methods) |
| `building_subsistence_orchard` | 5,000 | grain 0.25, fruit 0.5, fabric 0.5, wood 0.5, services 0.5 | `:146-162` | `:164-192` | `:194-208` (fruit 0.33, +3) |
| `building_subsistence_pasture` | 5,000 | grain 0.25, meat 0.5, fabric 0.75, wood 0.25, services 0.5 | `:210-226` | `:228-255` | `:257-271` (meat 0.33, +3) |
| `building_subsistence_fishing_village` | 5,000 | grain 0.5, fish 1.0, fabric 0.25, wood 0.25, services 0.5 | `:273-289` | `:291-319` | `:321-335` (fish 0.5, +3) |
| `building_subsistence_rice_farm` | 10,000 | grain 2.0, fabric 0.75, wood 0.75, services 1.0 | `:337-352` | `:354-382` | `:384-398` (grain 1.0, +3) |

What this implies for choosing a type: the choice sets the basket a state puts on the market. A pasture state makes a quarter of a farm's grain (0.25 against 1.0) and adds meat and more fabric, so a pasture region is a grain importer by construction; a fishing village makes half the grain but adds fish; rice doubles both the headcount per level and the grain, so, if outputs scale with the employed workforce, one level of rice yields about four times a farm level's grain (2.0 per worker-scale at 10,000 workers against 1.0 at 5,000). The farm is the only building with five serfdom methods; the other four have a single serfdom method.

Vanilla's use of each type, by script (all 675 land states): farm 447, pasture 83, orchard 26, fishing village 26, rice 93, with n, mean, median, min and max and named min/median/max states in table 4.2, the region-trait split in 4.2b and the class spread with examples across climates in 4.2c. The headline: farm is the default everywhere humid or temperate (temperate forest/hill, river plains, mountains), pasture is the arid/steppe/tundra choice, orchard is the oasis and Mesopotamian choice, fishing village is the island and arctic-coast choice, rice is monsoon Asia.

## 4. Calibration table (vanilla 1.13.11)

Eleven climate classes, fixed here; #3677 must reuse these ids verbatim (the `CLASS_IDS` constant of `mapgen/measure_vanilla_arable.py` is the machine copy):

| id | operational definition | vanilla anchor states |
|---|---|---|
| `arctic_boreal_coast` | high-latitude coasts, islands and tundra; fishing or herding economy (fishing village above 55 N or pasture above 60 N) | Iceland, Greenland, Northern Norway, Nenetsia, Chukotka, Kamchatka, Nunavut |
| `boreal_forest` | taiga, cold continental forest, roughly 50-67 N | Novgorod, Moscow, Norrland, Kola, Irkutsk |
| `temperate_river_plain` | humid or monsoon alluvial lowland fed by a major river, outside the equatorial forest belt | Ile-de-France, Normandy, Flanders, Lombardy, Bohemia, Kiev, Central Hungary |
| `temperate_forest_hill` | humid temperate mixed forest, hill and mid-relief country | Yorkshire, Wales, Auvergne-Limousin, Virginia, Kyoto |
| `mediterranean` | dry-summer coasts, islands and rain-fed interior plateaus, about 30-45 N | Languedoc, Tuscany, Sicily, Catalonia, California, Cape Colony |
| `steppe` | semi-arid grassland and continental plains | Kuban, Stavropol, Nebraska, Buenos Aires, Hinggan, Konya |
| `desert_river` | arid land watered by one great river or oasis belt | Lower, Middle and Upper Egypt, Dongola, Baghdad, Basra, Khiva, Fergana |
| `open_desert` | arid land with no river | Sahara, Libyan Desert, Nejd, Alxa, Arizona, Western Australia |
| `highland_alpine` | mountain and high-plateau states | Tyrol, East and West Switzerland, Savoy, Ngari, Lhasa, the Andes and Zagros states |
| `tropical_savanna` | seasonal-rain tropics and Sahel | Sahel states, Deccan (Hyderabad), Brazilian sertao and cerrado, Zambia, Bombay |
| `tropical_forest` | year-round humid tropics, Congo, Amazonia, Indonesia, mainland South-East Asia, Pacific islands | Congo, Amazonas, Laos, West Java, Fiji |

The class of each of the 675 vanilla land states is the hand-authored `mapgen/config/vanilla_state_climate_classes.csv` (columns `state_key,climate_class,basis,note`). `--propose` classified 469 states mechanically (rule order: coast and latitude first, then region traits, then per-file defaults); the build reviewed every row against real geography, overriding 112 mechanical rows and filling the other 206, so 318 rows carry `basis=manual` with a one-word note and 357 keep a mechanical basis. A state spanning two classes takes the dominant one. The script never re-infers a class from the proposal once the CSV exists.

Reading the tables: the **comparable geography** block uses the vanilla files whose land resembles the mod's Old World (West, South and East Europe, North Africa, the Middle East, Russia: 300 states); the **world** block uses all 675. A class with fewer than 8 comparable states is flagged `thin` and the world block is its reference; classes are never merged to pad n. Pixel areas come from vanilla's `provinces.png` under the Miller frame both maps share (`mapgen/config/canvas_frame.py`; vanilla's equator is measured at canvas row 2102.8 by `mapgen/measure_vanilla_frame.py`), true area is `px x canvas_frame.km2_per_px(latitude)`, and the four reference states in table 4.0 reproduce real area to within 1.5 percent. Islands are drawn oversized in vanilla (Malta about 4.7x), so island and fishing-village classes are read on the per-state columns.

<!-- BEGIN measure_vanilla_arable -->
<!-- generated by mapgen/measure_vanilla_arable.py; do not hand-edit (run it, then --check) -->

#### 4.0 Headline (all vanilla land states)

- Land states **675**; total arable **53,616**; mean 79.4, median 51, min 2, max 601.
- Deciles (p10..p90): 15 / 25 / 35 / 40 / 51 / 64 / 80 / 105 / 180.
- States with arable at or below 5: 32 (exactly 2: 5).
- Listed land provinces 40,717; arable per province 1.32.
- Comparable geography (vanilla files 00, 01, 02, 03, 08, 15): 300 states, median 42, mean 51.5, arable per 1,000 km^2 0.44 aggregate / 1.15 median.
- 1836 pops per arable (vanilla `common/history/pops`, vanilla's own start date): median 14,524 over 675 states; 141 states below 5,000 and 0 above 100,000.
- Area self-test (px x `canvas_frame.km2_per_px` at the state's mean row, vanilla Y0 2102.8): ILE_DE_FRANCE 11,922 vs 12,012 (-0.8 %); NORMANDY 29,722 vs 29,906 (-0.6 %); BOHEMIA 52,212 vs 52,065 (+0.3 %); ICELAND 104,524 vs 103,000 (+1.5 %).

#### 4.1 By vanilla file

| file | n | mean arable | median | pasture states | pops per arable (median) |
|---|---|---|---|---|---|
| 00_west_europe | 75 | 60.7 | 55 | 2 | 22,316 |
| 01_south_europe | 64 | 36.0 | 32 | 2 | 21,613 |
| 02_east_europe | 23 | 82.9 | 80 | 0 | 17,431 |
| 03_north_africa | 32 | 40.6 | 40 | 16 | 11,530 |
| 04_subsaharan_africa | 60 | 73.8 | 70 | 2 | 10,424 |
| 05_north_america | 78 | 116.4 | 100 | 14 | 2,536 |
| 06_central_america | 15 | 35.2 | 30 | 0 | 11,092 |
| 07_south_america | 53 | 66.2 | 50 | 7 | 3,270 |
| 08_middle_east | 40 | 38.1 | 35 | 9 | 14,748 |
| 09_central_asia | 25 | 63.2 | 55 | 3 | 13,214 |
| 10_india | 32 | 205.3 | 178 | 0 | 23,010 |
| 11_east_asia | 63 | 173.5 | 104 | 8 | 39,489 |
| 12_indonesia | 28 | 34.2 | 32 | 0 | 14,011 |
| 13_australasia | 9 | 29.0 | 30 | 3 | 3,275 |
| 14_siberia | 12 | 26.5 | 14 | 3 | 5,678 |
| 15_russia | 66 | 58.4 | 48 | 14 | 12,077 |

#### 4.2 By subsistence building

| type | n | mean | median | min | max | per 1,000 px | per 1,000 km^2 (agg / median) | pops per arable (median) | min / median / max state |
|---|---|---|---|---|---|---|---|---|---|
| farm | 447 | 73.3 | 60 | 2 | 505 | 7.61 | 0.47 / 0.94 | 14,377 | KOLA 2 / EASTERN_CAPE 60 / PUNJAB 505 |
| pasture | 83 | 35.1 | 30 | 2 | 300 | 0.74 | 0.07 / 0.08 | 6,215 | OB 2 / AMUR 30 / BUENOS_AIRES 300 |
| orchard | 26 | 45.3 | 40 | 5 | 120 | 7.09 | 0.35 / 0.43 | 13,263 | EAST_AEGEAN_ISLANDS 5 / LURISTAN 40 / SENEGAL 120 |
| fishing_village | 26 | 10.1 | 5 | 2 | 40 | 0.46 | 0.07 / 0.19 | 10,841 | ALAND 2 / TONGA 5 / NEW_BRUNSWICK 40 |
| rice | 93 | 177.4 | 107 | 10 | 601 | 25.94 | 1.31 / 1.35 | 35,320 | TARAPACA 10 / TOKAI 107 / EAST_BENGAL 601 |

Per-km^2 columns: vanilla draws small islands oversized (Malta about 4.7x, Azores 2.8x, Ryukyu 3.0x), so read island and `fishing_village` rows on the per-state columns.

#### 4.2b Subsistence building by region trait

Vanilla's own choice of type for the geography (states carrying the trait):

| trait | states | farm | pasture | orchard | fishing_village | rice |
|---|---|---|---|---|---|---|
| alps_mountains | 5 | 5 | 0 | 0 | 0 | 0 |
| rocky_mountains | 6 | 6 | 0 | 0 | 0 | 0 |
| andes | 17 | 10 | 4 | 0 | 0 | 3 |
| himalayas_mountains | 4 | 1 | 1 | 0 | 0 | 2 |
| zagros_mountains | 6 | 2 | 0 | 4 | 0 | 0 |
| atlas_mountains | 4 | 1 | 1 | 2 | 0 | 0 |
| caucasus_mountains | 3 | 3 | 0 | 0 | 0 | 0 |
| sahara_desert | 8 | 0 | 8 | 0 | 0 | 0 |
| arabian_desert | 2 | 0 | 2 | 0 | 0 | 0 |
| sahel | 8 | 1 | 6 | 1 | 0 | 0 |
| siberian_terrain | 8 | 0 | 6 | 0 | 2 | 0 |
| gobi_desert | 1 | 0 | 1 | 0 | 0 | 0 |
| australian_desert | 3 | 1 | 2 | 0 | 0 | 0 |
| western_steppe | 15 | 9 | 6 | 0 | 0 | 0 |
| eastern_steppe | 5 | 2 | 3 | 0 | 0 | 0 |
| pampas | 5 | 4 | 1 | 0 | 0 | 0 |
| the_great_plains | 4 | 4 | 0 | 0 | 0 | 0 |
| nile_river | 5 | 5 | 0 | 0 | 0 | 0 |
| mesopotamian_floodplain | 2 | 0 | 0 | 2 | 0 | 0 |
| euphrates_river | 7 | 3 | 1 | 3 | 0 | 0 |
| tigris_river | 4 | 0 | 0 | 4 | 0 | 0 |
| russian_forest | 14 | 14 | 0 | 0 | 0 | 0 |
| scandinavian_forests | 10 | 9 | 1 | 0 | 0 | 0 |

#### 4.2c Subsistence building by climate class

World block; the example is the state at that group's median arable, for up to four classes by count:

| type | classes used (n) | named examples across climates |
|---|---|---|
| farm | temperate_forest_hill (99), temperate_river_plain (69), tropical_savanna (54), mediterranean (52), highland_alpine (47), tropical_forest (43), steppe (36), boreal_forest (29), desert_river (13), open_desert (5) | temperate_forest_hill: YORKSHIRE 50; temperate_river_plain: BURGUNDY 80; tropical_savanna: SINALOA 60; mediterranean: EXTREMADURA 34 |
| pasture | open_desert (28), steppe (21), arctic_boreal_coast (12), tropical_savanna (8), highland_alpine (7), boreal_forest (4), desert_river (1), mediterranean (1), temperate_forest_hill (1) | open_desert: KERMAN 20; steppe: ASTRAKHAN 45; arctic_boreal_coast: UPPER_YENISEYSK 10; tropical_savanna: CHAD 30 |
| orchard | mediterranean (7), tropical_savanna (5), desert_river (4), highland_alpine (4), open_desert (3), steppe (2), tropical_forest (1) | mediterranean: IONIAN_ISLANDS 10; tropical_savanna: ZAMBEZIA 70; desert_river: BAGHDAD 40; highland_alpine: LURISTAN 40 |
| fishing_village | tropical_forest (13), arctic_boreal_coast (6), temperate_forest_hill (6), tropical_savanna (1) | tropical_forest: TONGA 5; arctic_boreal_coast: OKHOTSK 2; temperate_forest_hill: CONNECTICUT 15; tropical_savanna: BAHAMAS 10 |
| rice | temperate_river_plain (29), tropical_forest (26), temperate_forest_hill (18), tropical_savanna (9), highland_alpine (8), desert_river (2), steppe (1) | temperate_river_plain: HUNAN 330; tropical_forest: PEGU 40; temperate_forest_hill: CHUGOKU 101; tropical_savanna: CENTRAL_PROVINCES 205 |

#### 4.3 By climate class: comparable geography (300 states, vanilla files 00, 01, 02, 03, 08, 15)

| class | n | flag | mean | median | min | max | p10 | p25 | p75 | p90 | min / median / max state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arctic_boreal_coast | 7 | thin | 6.1 | 4 | 2 | 20 | 3 | 4 | 5 | 11 | ALAND 2 / SURGUT 4 / NORTHERN_NORWAY 20 |
| boreal_forest | 27 |  | 48.1 | 45 | 2 | 185 | 13 | 21 | 69 | 74 | KOLA 2 / KRASNOYARSK 45 / YAROSLAVL 185 |
| temperate_river_plain | 58 |  | 77.2 | 75 | 10 | 195 | 38 | 46 | 98 | 127 | DOBRUDJA 10 / ANHALT 75 / BOHEMIA 195 |
| temperate_forest_hill | 70 |  | 59.1 | 50 | 3 | 180 | 25 | 36 | 75 | 100 | GOTLAND 3 / SOUTHERN_TRANSYLVANIA 50 / ORYOL 180 |
| mediterranean | 57 |  | 38.7 | 30 | 5 | 120 | 9 | 20 | 60 | 69 | EAST_AEGEAN_ISLANDS 5 / PALESTINE 30 / LANGUEDOC 120 |
| steppe | 22 |  | 52.9 | 40 | 8 | 125 | 30 | 33 | 65 | 99 | KALMYKIA 8 / DIYARBAKIR 40 / ROSTOV 125 |
| desert_river | 13 |  | 57.9 | 40 | 20 | 150 | 30 | 38 | 80 | 89 | DEIR_EZ_ZOR 20 / UPPER_EGYPT 40 / FERGANA 150 |
| open_desert | 18 |  | 13.4 | 10 | 3 | 30 | 5 | 6 | 20 | 22 | MATRUH 3 / OMAN 10 / LARISTAN 30 |
| highland_alpine | 18 |  | 41.4 | 40 | 10 | 110 | 17 | 26 | 50 | 70 | ALTAI 10 / EAST_SWITZERLAND 40 / TABRIZ 110 |
| tropical_savanna | 10 |  | 38.4 | 40 | 4 | 70 | 18 | 30 | 48 | 61 | CAPE_VERDE 4 / KORDOFAN 40 / EASTERN_MALI 70 |
| tropical_forest | 0 | empty | - | - | - | - | - | - | - | - | - |

| class | provinces (median) | arable per province | per 1,000 px | per 1,000 km^2 (agg) | per 1,000 km^2 (median) | state km^2 (median) | km^2 p10 / p90 | pops per arable (median) |
|---|---|---|---|---|---|---|---|---|
| arctic_boreal_coast | 312 | 0.02 | 0.06 | 0.01 | 0.01 | 474,263 | 63,865 / 1,235,098 | 10,455 |
| boreal_forest | 51 | 0.62 | 2.72 | 0.34 | 0.46 | 99,812 | 39,558 / 304,351 | 13,594 |
| temperate_river_plain | 11 | 5.94 | 26.50 | 2.23 | 2.56 | 27,435 | 12,735 / 56,414 | 20,008 |
| temperate_forest_hill | 9 | 4.68 | 20.32 | 1.81 | 1.96 | 25,446 | 13,228 / 56,685 | 20,427 |
| mediterranean | 7 | 4.20 | 18.97 | 1.17 | 1.13 | 24,259 | 8,475 / 68,472 | 21,051 |
| steppe | 37 | 0.80 | 3.52 | 0.26 | 0.40 | 135,394 | 43,188 / 432,312 | 9,868 |
| desert_river | 33 | 1.65 | 7.05 | 0.37 | 0.37 | 132,470 | 54,025 / 202,909 | 9,794 |
| open_desert | 82 | 0.14 | 0.60 | 0.03 | 0.03 | 385,758 | 66,609 / 815,677 | 7,675 |
| highland_alpine | 18 | 1.60 | 7.01 | 0.42 | 0.49 | 66,536 | 16,271 / 196,082 | 15,767 |
| tropical_savanna | 76 | 0.42 | 1.86 | 0.08 | 0.09 | 394,281 | 196,342 / 830,360 | 11,833 |

#### 4.4 By climate class: world (675 states)

| class | n | flag | mean | median | min | max | p10 | p25 | p75 | p90 | min / median / max state |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arctic_boreal_coast | 18 |  | 9.3 | 5 | 2 | 20 | 2 | 3 | 18 | 20 | ALAND 2 / ICELAND 5 / YUKON_TERRITORY 20 |
| boreal_forest | 33 |  | 44.8 | 32 | 2 | 185 | 11 | 20 | 62 | 70 | KOLA 2 / UUSIMAA 32 / YAROSLAVL 185 |
| temperate_river_plain | 98 |  | 167.2 | 110 | 10 | 601 | 40 | 66 | 238 | 363 | DOBRUDJA 10 / LOMBARDY 110 / EAST_BENGAL 601 |
| temperate_forest_hill | 124 |  | 77.9 | 56 | 3 | 400 | 21 | 35 | 100 | 180 | DISTRICT_OF_COLUMBIA 3 / WALLONIA 55 / GUANGXI 400 |
| mediterranean | 60 |  | 43.4 | 34 | 5 | 300 | 9 | 20 | 60 | 70 | EAST_AEGEAN_ISLANDS 5 / ARAGON 34 / CALIFORNIA 300 |
| steppe | 60 |  | 93.1 | 62 | 8 | 500 | 30 | 40 | 106 | 222 | KALMYKIA 8 / SASKATCHEWAN 60 / TEXAS 500 |
| desert_river | 20 |  | 105.8 | 78 | 20 | 505 | 30 | 40 | 150 | 184 | DEIR_EZ_ZOR 20 / SINDH 75 / PUNJAB 505 |
| open_desert | 36 |  | 24.9 | 20 | 3 | 63 | 5 | 10 | 40 | 40 | MATRUH 3 / SEMNAN 20 / BALUCHISTAN 63 |
| highland_alpine | 66 |  | 62.8 | 50 | 10 | 200 | 18 | 30 | 80 | 135 | ALTAI 10 / INNER_MOROCCO 50 / MONTANA 200 |
| tropical_savanna | 77 |  | 85.9 | 60 | 4 | 400 | 30 | 40 | 90 | 160 | CAPE_VERDE 4 / ZAMBIA 60 / BOMBAY 400 |
| tropical_forest | 83 |  | 47.7 | 40 | 5 | 160 | 5 | 26 | 70 | 80 | ACRE 5 / LAOS 40 / VERACRUZ 160 |

| class | provinces (median) | arable per province | per 1,000 px | per 1,000 km^2 (agg) | per 1,000 km^2 (median) | state km^2 (median) | km^2 p10 / p90 | pops per arable (median) |
|---|---|---|---|---|---|---|---|---|
| arctic_boreal_coast | 383 | 0.02 | 0.06 | 0.01 | 0.01 | 615,696 | 80,666 / 1,677,288 | 3,622 |
| boreal_forest | 59 | 0.48 | 2.12 | 0.24 | 0.31 | 119,456 | 43,767 / 458,350 | 12,118 |
| temperate_river_plain | 16 | 5.95 | 26.15 | 1.84 | 2.36 | 43,962 | 15,173 / 168,453 | 21,554 |
| temperate_forest_hill | 11 | 3.55 | 15.51 | 1.10 | 1.66 | 33,615 | 12,924 / 146,976 | 19,346 |
| mediterranean | 8 | 3.63 | 16.29 | 0.99 | 1.08 | 25,520 | 8,959 / 87,860 | 20,907 |
| steppe | 58 | 1.04 | 4.57 | 0.34 | 0.40 | 194,240 | 73,114 / 647,876 | 6,676 |
| desert_river | 33 | 2.72 | 11.58 | 0.64 | 0.58 | 140,593 | 59,816 / 240,342 | 11,915 |
| open_desert | 79 | 0.23 | 0.99 | 0.05 | 0.08 | 304,290 | 84,645 / 915,188 | 6,279 |
| highland_alpine | 28 | 1.22 | 5.31 | 0.32 | 0.40 | 127,826 | 28,102 / 459,043 | 10,822 |
| tropical_savanna | 45 | 1.33 | 5.81 | 0.26 | 0.30 | 233,473 | 56,658 / 623,785 | 9,747 |
| tropical_forest | 21 | 1.35 | 5.78 | 0.25 | 0.28 | 116,062 | 28,072 / 379,222 | 15,760 |

#### 4.5 Class bands for the model (comparable block; world block for `thin` classes)

| class | band source | n | p25 | median | p75 | km^2 p10 / p90 | peasant capacity at median (x5,000) |
|---|---|---|---|---|---|---|---|
| arctic_boreal_coast | world (thin) | 18 | 3 | 5 | 18 | 80,666 / 1,677,288 | 25,000 |
| boreal_forest | comparable | 27 | 21 | 45 | 69 | 39,558 / 304,351 | 225,000 |
| temperate_river_plain | comparable | 58 | 46 | 75 | 98 | 12,735 / 56,414 | 375,000 |
| temperate_forest_hill | comparable | 70 | 36 | 50 | 75 | 13,228 / 56,685 | 250,000 |
| mediterranean | comparable | 57 | 20 | 30 | 60 | 8,475 / 68,472 | 150,000 |
| steppe | comparable | 22 | 33 | 40 | 65 | 43,188 / 432,312 | 200,000 |
| desert_river | comparable | 13 | 38 | 40 | 80 | 54,025 / 202,909 | 200,000 |
| open_desert | comparable | 18 | 6 | 10 | 20 | 66,609 / 815,677 | 50,000 |
| highland_alpine | comparable | 18 | 26 | 40 | 50 | 16,271 / 196,082 | 200,000 |
| tropical_savanna | comparable | 10 | 30 | 40 | 48 | 196,342 / 830,360 | 200,000 |
| tropical_forest | world (thin) | 83 | 26 | 40 | 70 | 28,072 / 379,222 | 200,000 |

#### 4.6 Leave-one-out back-test (comparable block)

Each state's arable is predicted from the other states of its class (classes with at least 3 others); a hit is a prediction within x0.67-1.5 of the real value.

| method | prediction | n tested | hit rate | pred / actual p10 | median | p90 |
|---|---|---|---|---|---|---|
| per_area | class median density x true km^2 | 300 | 36 % | 0.33 | 1.01 | 3.25 |
| per_state_median | class median arable per state | 300 | 46 % | 0.48 | 1.00 | 2.39 |
| sqrt_damped | class median x sqrt(km^2 / class median km^2) | 300 | 44 % | 0.42 | 1.04 | 2.32 |
| pop_anchored | 1836 pops / class median pops-per-arable | 300 | 67 % | 0.50 | 0.99 | 1.66 |

| class (comparable block) | n | log arable ~ log km^2 slope | r(log arable, log pops) |
|---|---|---|---|
| arctic_boreal_coast | 7 | 0.08 | 0.84 |
| boreal_forest | 27 | -0.18 | 0.89 |
| temperate_river_plain | 58 | 0.46 | 0.87 |
| temperate_forest_hill | 70 | 0.48 | 0.77 |
| mediterranean | 57 | 0.67 | 0.94 |
| steppe | 22 | 0.06 | 0.57 |
| desert_river | 13 | -0.25 | 0.66 |
| open_desert | 18 | 0.05 | 0.53 |
| highland_alpine | 18 | 0.18 | 0.72 |
| tropical_savanna | 10 | 0.47 | 0.83 |

#### 4.7 The mod's drawn states by realm file (sanity check, not an assignment)

Drawn states **343**, provinces **4,442** (12.95 per drawn state against vanilla's 60.3), measured under the mod frame (`canvas_frame.Y0` 2142.0). "Illustrative class" is a hand-set label per realm file (`REALM_ILLUSTRATIVE_CLASS` in the script) used only to size the realm total; it is never a state's class.

| realm | states | provinces | px | km^2 | latitude range | coastal (port) | illustrative class | class median | n x class median |
|---|---|---|---|---|---|---|---|---|---|
| badlands | 27 | 513 | 141,496 | 2,599,741 | 24.5 to 41.4 | 6 | steppe | 40 | 1,080 |
| brettonia | 36 | 300 | 81,854 | 971,637 | 44.1 to 55.8 | 23 | temperate_river_plain | 75 | 2,700 |
| dark_lands | 64 | 1,342 | 395,480 | 5,646,687 | 27.0 to 61.0 | 22 | steppe | 40 | 2,560 |
| empire | 45 | 498 | 130,950 | 1,441,745 | 45.1 to 57.6 | 30 | temperate_forest_hill | 50 | 2,250 |
| karaz_ankor | 61 | 469 | 274,647 | 4,465,808 | 18.5 to 58.1 | 14 | highland_alpine | 40 | 2,440 |
| kislev | 21 | 322 | 88,045 | 752,660 | 53.7 to 62.5 | 14 | boreal_forest | 45 | 945 |
| nehekhara | 11 | 174 | 46,510 | 988,189 | 18.9 to 24.3 | 9 | desert_river | 40 | 440 |
| norsca | 42 | 458 | 176,643 | 1,103,682 | 60.2 to 70.2 | 23 | boreal_forest | 45 | 1,890 |
| southern_realms | 36 | 366 | 103,567 | 1,556,168 | 34.2 to 46.5 | 24 | mediterranean | 30 | 1,080 |
| **total** | 343 | 4,442 | 1,439,192 | 19,526,318 | 18.5 to 70.2 | 165 | | | 15,385 |

- Naive per-state anchor: 343 drawn states x comparable median 42 = **14,406 arable** (peasant capacity 72.0 M at 5,000 per level); comparable p25-p75 band x 343 = 8,575 to 24,010 arable (42.9 to 120.0 M).
- Per-area cross-check: comparable aggregate density 0.44 per 1,000 km^2 x the mod's 19,526,318 km^2 = 8,681 arable.
<!-- END measure_vanilla_arable -->

## 5. Recommended basis and formulas

**Basis: per state, by climate class.** The per-class median with its p25-p75 band is primary; per-area density is only a realm-total sanity check; per-province is rejected.

Evidence that decides it (tables 4.0, 4.6, 4.7):

- Vanilla does not size arable by area. The leave-one-out back-test over the 300 comparable states predicts a state's arable from the other states of its class: class density x true km^2 lands within x0.67-1.5 of the real value for 36 percent of states (p90 of prediction over actual 3.25), the class's per-state median alone for 46 percent, a square-root size damping for 44 percent, and the state's own 1836 population divided by its class's median pops per arable for 67 percent. Within a class arable grows with area only sub-linearly (log-log slopes 0.46-0.67 in the temperate, Mediterranean and savanna classes, 0.05-0.08 for steppe, open desert and arctic, 0.18 for highland, negative for boreal forest and desert river) while it tracks 1836 population closely (r 0.72-0.94 outside steppe, open desert and desert river, where it is 0.53-0.66). Vanilla arable is a per-state, population-proxy slot count with a weak size term. (The original scoping measured 31/45/40/67 percent with the purely mechanical class rules; the reviewed class map gives 36/46/44/67. The ranking is unchanged and the decision with it.)
- Per province is rejected outright: vanilla's province density is a drawing artefact (arable per province runs from 0.02 in the arctic class to about 6 in the plain classes, table 4.3) and the mod's drawn states average 12.95 provinces against vanilla's 60.3.
- The residual gap between 46 and 67 percent is the settlement and lore judgment that #3677 owns (the multiplier `m`).

**Formula for #3677** (class bands from table 4.5: comparable block, world block for `thin` classes):

```
arable = clamp(round(median_class * m), p25_class, p75_class)
```

`m` is the model child's settlement/lore multiplier (default 1.0; a lore override may leave the band only with a written entry). #3677 realises it as three discrete positions, `low` / `mid` / `high` = p25 / median / p75, plus class overrides. Size term, outliers only: a state whose true km^2 lies outside its class's p10-p90 range (table 4.5) may move one band step (`low` to `mid` to `high`), never more; linear scaling (back-test p90 over actual 3.25) and square-root damping (44 percent, below the plain median's 46) are both rejected. Floor 2 (vanilla's minimum; 32 vanilla states are at or below 5). The `subsistence_building` default follows the class by the pattern in section 6 and tables 4.2b and 4.2c.

**For the population epic:**

```
peasant_capacity = arable * 5,000         (x 10,000 for building_subsistence_rice_farm;
                                           shrinks as other rural buildings take levels)
pops_1836_vanilla ~ arable * pops_per_arable(class, settlement)
```

Settlement bands from the per-file medians in table 4.1 (vanilla 1836): settled core about 17-23 k per arable (West Europe 22.3 k, South Europe 21.6 k, East Europe 17.4 k, India 23.0 k), periphery about 10-15 k (Russia 12.1 k, Middle East 14.7 k, North Africa 11.5 k, sub-Saharan Africa 10.4 k, Central Asia 13.2 k, Indonesia 14.0 k), frontier about 2-6 k (Siberia 5.7 k, North America 2.5 k, South America 3.3 k, Australasia 3.3 k; below 5 k the `low_pop_state` +50 percent birth rate applies, section 2.7). East Asia's 39.5 k reflects rice at 10,000 peasants per level.

**Illustration, not an assignment** (recomputed for the drawn roster in table 4.7): 343 drawn states x the comparable per-state median 42 = 14,406 arable, about 72 M peasant capacity; the comparable p25-p75 band spans 8,575 to 24,010 arable; the per-area cross-check gives 8,681 and the illustrative realm classes sum to 15,385. The current placeholder (10 per state) is 3,430, about a quarter of the naive anchor. The parent's old 6,700-21,000 bracket derived from the retired 267-state roster and is dropped; use these figures. One watch item for #3677: the mod's drawn states average 56,925 km^2 (19.5 M km^2 over 343 states), above the p90 of the temperate classes in table 4.5, so the outlier rule will fire often there once #3677's own class map exists; its owner should recount it and decide whether the band step stays.

## 6. Ruling: do vanilla's five subsistence types cover the Warhammer peoples?

**Ruling: yes, the five suffice; no gap is filed.** Procedure: lore first (what the realm's peasants eat and sell), then vanilla's usage pattern for the analogue, then the mechanical consequence; a gap exists only if a realm needs a peasants-per-level or an output basket no vanilla type approximates and the difference is visible in goods, employment or laws. Icon and name mismatches are flavour, not gaps.

Vanilla's own pattern (tables 4.2, 4.2b and 4.2c): its temperate mountain states are all `farm` (Alps 5 of 5, Rocky Mountains 6 of 6, Caucasus 3 of 3, Andes 10 of 17), so "pasture for mountain peoples" is not vanilla's pattern; pasture is the choice for arid, steppe and tundra states (Sahara 8 of 8, Arabian Desert 2 of 2, Sahel 6 of 8, Siberian terrain 6 of 8, Kirghizia, Nejd, Ngari), orchard for oasis belts and Mesopotamia (Tigris 4 of 4, Mesopotamian floodplain 2 of 2), fishing village for arctic coasts and islands, rice for monsoon Asia. The rule of thumb is by moisture, not by race.

By realm:

- **Dwarf holds.** Both patterns are documented and the choice is a lore call for #3677's rulebook, not a climate default: vanilla's analogue says `farm`; the lore-first default says `pasture` (goat and sheep herds, grain imported from the Empire, the canon trade dependency). The mechanics support the second reading: the pasture base method makes a quarter of the farm's grain (`common/production_methods/12_subsistence.txt:6` against `:215`), so a pasture hold is a grain importer by construction. #3677's draft already picks pasture.
- **Greenskin Badlands.** `pasture` (the Sahara/Sahel pattern).
- **Nehekhara.** `farm` along the Great Mortis (the Nile pattern: 5 of 5 farm, with the +0.2 agriculture trait, section 2.8) and `pasture` in the desert states.
- **Araby** (no drawn state in `08_araby.txt` today). `orchard` or `farm` (the Tigris/Euphrates/Maghreb pattern).
- **Chaos Dwarf slave economy.** Already carried: `slaves_role = peasants` on every subsistence building (`common/buildings/12_subsistence.txt:18, 41, 63, 85, 107`), the mod's slavery laws (`common/laws/02_slavery.txt:5, 101, 151, 224, 316`) and the arable-scaled import rate (`SLAVE_TRADE_ARABLE_LAND_EFFECT`, section 2.5), with slaves consuming only 5 percent of a normal basket in subsistence (`:567`). The building is `farm` or `pasture` by climate.
- **Undead and the Ogre Kingdoms.** The subsistence type is not the constraint: the building supplies peasants-per-level and a goods basket, and whether undead pops need food at all is a pop-needs and culture question outside this item's files, recorded for the population epic rather than treated as a missing building. The Ogre Kingdoms have no drawn state (`map_data/state_regions/11_ogre_kingdoms.txt`) and take the `eastern_steppe` pasture note only.

## 7. Handoff

- **#3677 (climate model).** The eleven ids, verbatim and in this order: `arctic_boreal_coast`, `boreal_forest`, `temperate_river_plain`, `temperate_forest_hill`, `mediterranean`, `steppe`, `desert_river`, `open_desert`, `highland_alpine`, `tropical_savanna`, `tropical_forest` (string-equal to the script's `CLASS_IDS`; #3677's plan runs that comparison). Class bands: table 4.5. Both density units are published (per 1,000 px and per 1,000 km^2, tables 4.2-4.4). Its `tabulate_state_prior.py` should import `canvas_frame.km2_per_px` (`mapgen/config/canvas_frame.py`) for its `area_km2` column; this item lands first.
- **#3678 (tooling).** Carry the row grammar #3677 fixes in the `arable_note` cell, `class=<slug>; pos=<low|mid|high>; ovr=<section 5 id|->`, so a validator can band-check later without a schema change; the class itself lives in #3677's `mapgen/config/state_climate_classes.csv`, keyed by canon state key.
- **Population epic.** The pops-per-arable bands and the `peasant_capacity` formula in section 5, and the `low_pop_state` / inert `high_pop_state` finding in section 2.7.
- **#2968 (province terrains).** `map_data/province_terrains.txt` is written uniformly as land `plains` today (`.claude/rules/testing.md:81`), so it carries no terrain signal; nothing in the cited files derives `arable_land` from province terrain, and arable must come from the class table.
- **#4921 heatmap.** `mapgen/derived/arable_heatmap.png` and `arable_heatmap_index.json` (built by `mapgen/generate_arable_heatmap.py` and `mapgen/worldgen/arable.py` from the hand-authored `mapgen/config/arable_lore.json`) are a relative prior with no `arable_land` numbers. The class bands in table 4.5 are the numeric calibration it deliberately lacks; no heatmap change is made here.

## 8. Reproduction

```
python mapgen/measure_vanilla_arable.py --selftest   # install-free: area formula, parser, class ids
python mapgen/measure_vanilla_arable.py              # writes gitignored mapgen/derived/vanilla_arable_{states.csv,calibration.md}
python mapgen/measure_vanilla_arable.py --check      # regenerates the block above and diffs it against this note
python mapgen/measure_vanilla_arable.py --propose    # mechanical class proposal (derived/vanilla_state_climate_proposal.csv)
```

`--check` needs the vanilla install (`--game PATH` overrides the default Steam path), `map_data/provinces.png` (Git LFS; the script refuses a pointer file with a `git lfs pull` hint) and the class CSV; it fails on any difference in the block, any unclassified vanilla state, any class id outside the fixed eleven, or an area self-test off by more than 5 percent. After a vanilla patch: re-run the default mode, re-review the class CSV against any new or renamed states, re-paste the block between the markers, and re-check. The script writes nothing inside the install, uses no clock and no RNG, and the block is byte-identical on re-run. The prose figures in sections 5 to 7 were copied from the block on 2026-10-02 and are not machine-checked; re-read them against the block when it changes.
