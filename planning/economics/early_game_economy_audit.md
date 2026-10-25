# Early-game economy audit: Talsyn (TLS) start, 2512-04-10

| Field | Value |
|-------|-------|
| Type | findings (audit; no redesign) |
| Status | file-derived findings complete; in-game figures `PENDING in-game confirmation` (Chris's readings, section 8) |
| Date | 2026-10-04 |
| Board | #6577 |
| Related | #3675 Arable land and subsistence (epic), #3684 State resources (epic; #3687, #3688), #6375 (country-history generator) |
| Measured against | Victoria 3 1.13.11 (`.metadata/metadata.json`); vanilla values cited as `vanilla` from the read-only install |
| Consumers | the follow-ups FU-1..FU-3 (section 6), Chris's decision on AC3 (section 7) |

Citation conventions: `file:line` paths are relative to this repo unless prefixed `vanilla`; `docs/*.log` are the game-generated references. Every figure that only the running game can supply carries the marker `PENDING in-game confirmation`; nothing marked that way is a fact yet. The figures taken from the report that opened this item (revenue 864, minting 559, timber about -58%, grain about -62%, "No Laws providing Institutions") are the reporter's in-game readings and are quoted as reported, not re-measured here.

## 1. Scope

The report: in the Talsyn start, about two thirds of revenue is minting (559 of 864), income, consumption and dividend taxes read zero, timber and grain sell far below base price, nearly every other good sits at the +75% price cap, the only buildings are farms, ranches, logging camps, barracks and manors, and the Institutions tab says "No Laws providing Institutions". This note ties each symptom to the script that causes it and marks it **intended**, **placeholder (already tracked)** or **gap (new follow-up)**.

Out of scope: rebalancing, any change to `common/`, `map_data/`, `localization/` or `mapgen/config/`. Nothing here is loaded by the game.

TLS is `country_type = unrecognized`, `tier = principality`, culture `wood_elf` (`common/country_definitions/03_brettonia.txt:250-256`). Its history file is generated and sets only tier-6 tech and traditional politics (`common/history/countries/tls - talsyn.txt`: `effect_starting_technology_tier_6_tech`, `effect_starting_politics_traditional`). Tier-6 tech is three techs: `enclosure`, `standing_army`, `urbanization` (`common/scripted_effects/00_starting_inventions.txt:132-141`). TLS owns five states in `common/history/states/03_brettonia.txt` (STATE_TALSYN, STATE_YI_EDRI_ETERNOS, STATE_KING_S_GLADE, STATE_TYR_VANNA, STATE_HALLS_OF_EQUOS); their pops in `common/history/pops/03_brettonia.txt` are 23,079 / 16,663 / 83,796 / 10,838 / 15,624, total 150,000.

## 2. Minting

**Finding: intended vanilla behaviour on a near-zero tax base.**

- The static modifier `base_values` grants `country_minting_add = 500` (`common/static_modifiers/00_code_static_modifiers.txt:24`; the file is a verbatim vanilla copy).
- The `country_gdp` modifier adds `country_minting_add = 1` scaled by country GDP divided by `COUNTRY_GDP_MODIFIER_DIVISOR` (`common/static_modifiers/00_code_static_modifiers.txt:801-804`; the define is 1000 in vanilla `common/defines/00_defines.txt:365`, capped by `COUNTRY_GDP_MODIFIER_MAX_MULTIPLIER` 200000 at `:366`; the mod's defines do not override either).
- Nothing else in the mod adds minting to TLS. The other sources are the gold mine and gold field production methods (`common/production_methods/03_mines.txt:807`, `:844`, `:881`, `:918`, `:957`, `:989`, `:1009`; both buildings need `prospecting`, `common/buildings/03_mines.txt:106`, `:132`), `country_minting_mult` techs (`banking`, `central_banking`, `mutual_funds`, `international_exchange_standards`, `modern_financial_instruments`; `common/technology/technologies/30_society.txt:198`, `:557`, `:1067`, `:1314`, `:1486`) and one company prosperity bonus (`common/company_types/99_basic_companies.txt:624`). TLS has none of those techs and no company.
- Arithmetic only: 559 - 500 = 59, so the GDP term would be about 59, which would mean a GDP near 59,000. That is an inference from the reported total, not a reading. `PENDING in-game confirmation`: the Budget > Minting tooltip shows the real split. The GDP term may differ if another multiplier applies.
- Why it dominates: the flat 500 is a vanilla constant that every country gets, while taxes scale with taxed pops and trade (section 3). With one 83,796-pop state holding all the buildings, the tax lines are small, so a constant 500 is most of the budget. Vanilla's minting share at its 1836 start is not measured here.

Verdict: **intended** (vanilla engine behaviour). Whether the flat 500 should be reduced for a mod where most realms are not mercantile is a rebalancing question and out of scope.

## 3. Taxes

**Finding: zero income, consumption and dividend tax follows from the starting laws; consumption tax additionally has no taxed goods to apply to.**

- `effect_starting_politics_traditional` (`common/scripted_effects/00_political_setup.txt:58`) has a `decentralized` branch (`:69-80`, consumption-based taxation) and an `else` branch (`:81-90`) that TLS takes as `unrecognized`: `law_monarchy`, `law_land_based_taxation`, `law_mercantilism`, `law_serfdom`, `law_right_of_assembly`, `law_closed_borders`, `law_no_workers_rights`.
- `law_land_based_taxation` (`common/laws/01_taxation.txt:52-97`) grants only `tax_consumption_add` and `tax_land_add` at each tax level; there is no income-tax term. Dividends tax comes only from proportional and graduated taxation (`tax_dividends_add`, `common/laws/01_taxation.txt:174` and `:230` onward). So income and dividends tax are zero by law, not by a bug.
- Consumption tax needs goods marked taxed with `add_taxed_goods`. No file in this mod sets it (`grep add_taxed_goods` over `common/` returns nothing); vanilla's history uses it 52 times (`vanilla common/history/countries/*.txt`). So the consumption tax line has nothing to apply to. This is the placeholder-grade output of the generated country history (#6375); `mapgen/validate_country_history.py:6` and `mapgen/config/country_history/README.md:3` both call the country-history generator "a later task".
- The remaining 305 of the reported 864 (864 - 559) is therefore probably land tax, possibly with tariffs. `PENDING in-game confirmation`: Budget > tax lines (land tax versus tariffs) and the active tax level, which no history line sets for TLS.
- The data that would replace the placeholder exists but no generator reads its tax data (correction 2026-10-23, #9028: pop history reads its slavery law and tech tier, country history its slavery law): `mapgen/config/country_history/03_brettonia.json:231-235` gives TLS only `profile: wood_elf_realm`, confidence `low`; The `wood_elf_realm` profile (`:78-98`) sets `tech_tier: 6`, `law_consumption_based_taxation` and `tax_level: "very_low"` but no `taxed_goods`, so TLS would inherit the baseline `taxed_goods: ["wine"]` (`:36-39`), a good no TLS state can produce (wine comes only from `building_vineyard`, `common/buildings/02_agro.txt:161`, which needs `enclosure` and the resource). The validator accepts it (`mapgen/validate_country_history.py` reports `OK 03_brettonia.json: 22 tag(s)`); it does not check producibility. That is FU-2.

Verdict: zero income/dividend tax **intended** (laws); empty consumption tax **placeholder** (#6375 generator, "later task") with the producibility rule as a **gap** (FU-2).

## 4. Market

**Finding: three stacked causes, none a bug, two of them placeholders.**

### 4.1 What TLS actually builds

Only STATE_KING_S_GLADE (83,796 pops) has buildings: barracks, a wheat farm, a livestock ranch and a logging camp, the last three owned by a manor house (`common/history/buildings/03_brettonia.txt:913-966`; the other four TLS states have none). The report's category table for TLS reads agriculture 2, military 1, resource 1 levels, 150,000 pops, jobs share 10.3% and highest state share 18.4% (`generate_building_history.py --check` report, "Jobs vs. pops" section, re-derived 2026-10-04). The same report lists 12 dropped placements for TLS: livestock ranch x4, logging camp x4, wheat farm x4, all "workforce share".

Why the small states get nothing: the `wood_elf_realm` archetype has `workforce_share` 0.2 (`mapgen/config/building_history/profiles.json:125-137`) and the planner sizes each state's budget as `int(workforce_share * pop)` (`mapgen/worldgen/building_history.py:734`). Each rural building level employs about 5,000 (`common/production_methods/02_agro.txt:1-14`, `:497-509`; `common/production_methods/09_misc_resource.txt:1-15`). A state under about 25,000 pops therefore rounds to no level. Four of TLS's five states are below that. The remaining pops are subsistence (the generator's design: "the rest of the pops stay on subsistence").

World-wide the generated history places 967 buildings in 263 region states with 231 dropped, and **no manufactory of any kind**: wheat farm 262, logging camp 191, livestock ranch 166, barracks 163, trade centre 74, construction sector 67, port 22, government administration 20, shipyard 2 (tally over `common/history/buildings/*.txt`, re-derived 2026-10-04).

### 4.2 Goods by producer

Producers are read from the files, not inferred from prices. "Selected PMs" are the production methods the generated TLS buildings activate (`common/history/buildings/03_brettonia.txt:913-966`); the quantities are the raw `workforce_scaled` coefficients, not tons per week. "Other producers" is every building in this mod whose production methods can output the good (so it includes optional methods TLS does not select), with the unlocking tech from `common/buildings/*.txt`. TLS tier-6 techs: `enclosure`, `standing_army`, `urbanization`. The subsistence farm (every TLS state's default, `mapgen/worldgen/land_economics.py:49-54`) outputs grain 1.0, fabric 0.5, wood 0.5 and services 0.5 per workforce unit in its base method (`common/production_methods/12_subsistence.txt:1-16`).

Cause key: **tech** the producing building is locked behind a tech TLS lacks; **resource** the producing building needs a state resource every state lacks today (all 524 land states carry the same placeholder resources, `mapgen/worldgen/land_economics.py:49-54`, tracked in #3675 / #3684 / #3687 / #3688); **history** TLS could build it (tech open) but the generated history places none; **pop-only** produced only by the subsistence pops.

| Good | TLS producer (selected PMs) | Other producers (unlocking tech) | Cause if absent or thin |
|---|---|---|---|
| grain | wheat farm `pm_simple_farming`, grain 20 (`02_agro.txt:1-14`); subsistence farms, grain 1.0 | other staple farms (enclosure); the farm/orchard/pasture/fishing/rice subsistence types | present |
| wood | logging camp `pm_simple_forestry`, wood 30 (`09_misc_resource.txt:1-15`); subsistence farms, wood 0.5 | logging camp, subsistence types | present |
| fabric | livestock ranch `pm_simple_ranch`, fabric 5 (`02_agro.txt:449-457`); subsistence farms, fabric 0.5 | cotton plantation (enclosure) | present |
| meat | livestock ranch `pm_open_air_stockyards`, meat 10 (`02_agro.txt:497-509`) | subsistence pasture, whaling station (navigation) | present |
| services | subsistence farms, services 0.5 | urban center (urbanization; TLS has it) | history (no urban center placed); subsistence only |
| fish | none | fishing wharf (no tech), subsistence fishing village | resource (no TLS state has the fish resource placeholder; `capped_resources` is logging only) |
| hardwood | none (`pm_no_hardwood`, `09_misc_resource.txt:69`) | logging camp hardwood methods | history (PM choice) |
| fruit | none | banana plantation, staple farms via secondary methods (enclosure), subsistence orchard | history (`pm_no_secondary`, `02_agro.txt:121`) |
| sugar, liquor | none | staple farms via secondary methods (enclosure), food industry (manufacturies) | history (`pm_no_secondary`); tech for the factories |
| groceries | none | food industry (manufacturies) | tech |
| clothes, luxury_clothes | none (home-workshop methods of subsistence farms disallowed here, `12_subsistence.txt:18-46`) | textile mill (manufacturies) | tech |
| furniture, luxury_furniture | none | furniture manufactory (manufacturies) | tech |
| paper, glass, porcelain, tools | none | paper mill, glassworks, tooling workshop (all manufacturies) | tech |
| fertilizer, explosives | none | chemical plant, explosives factory (intensive_agriculture) | tech |
| wine, tea, tobacco, opium, silk, dye | none | vineyard and plantations (enclosure; resource-gated per state) | resource |
| coal, iron, lead, sulfur | none | mines (shaft_mining) | tech and resource |
| gold | none | gold mine, gold field (prospecting) | tech and resource |
| steel, engines, oil, electricity, rubber, telephones, radios, automobiles, tanks, aeroplanes, small_arms, artillery, ammunition, fine_art | none | steel mill (steelworking), motor industry (atmospheric_engine), oil rig (pumpjacks), power plant (electrical_generation), rubber (rubber_mastication), electrics (telephone), automotive (combustion_engine), arms and artillery (gunsmithing), munition plant (percussion_cap), art academy (romanticism) | tech |
| merchant_marine, clippers, steamers, transportation | none | port, shipyard (navigation), railway (railways), urban center (urbanization) | tech (urban center: history) |
| manowars, ironclads, coffee | not found by the producer tally | no production-method output found by the parser (these goods are built or produced through other paths, or the tally missed them) | unresolved; not asserted |

The tally was produced with an ad hoc parse of `common/buildings`, `common/production_method_groups` and `common/production_methods`; optional methods mean "other producers" over-counts what a given country could ever run, and the three unresolved goods are a parser limit, not a finding.

What the table shows, from the files:

- TLS's own buildings produce grain, wood, fabric and meat, and have no goods inputs at all (no `goods_input_*` appears in any selected PM; `pm_no_organization` and the farm methods carry none). So the generated economy is self-contained and produces no processed good.
- Every processing building needs `manufacturies` (food, textile, furniture, glass, tooling, paper; `common/buildings/01_industry.txt:3-127`) or later, none of which tier 6 grants. Under tier-6 tech no processed good can be built. The planned data keeps wood elves at tier 6 on purpose ("held at tier 6 as the mod's lowest elven rung (no industry)", `mapgen/config/country_history/03_brettonia.json:97-98`, profile at `:78`), so this is a **design question** (FU-3), not a defect in the generator.
- `building_construction_sector` needs only `urbanization` (`common/buildings/13_construction.txt:3`), which TLS lacks at HEAD (corrected in #6637: the wood elf preset has no `urbanization`), so none can be built; `wood_elf_realm` keeps `construction: 0`.

### 4.3 The +75% prices and the timber/grain discount

- A good at the +75% cap does not mean zero supply. The cap is reached once demand is roughly double supply, and TLS does produce fabric (ranch, subsistence farms) and meat. Reading the cap as "nobody makes it" is not supported by the files.
- Grain and wood selling far below base price is not explained by TLS's building output alone, which is one wheat farm and one logging camp. The likelier source is the roughly 150,000 peasants' subsistence output (grain 1.0 and wood 0.5 per workforce unit on every subsistence farm) reaching the market. Vanilla's concept text supports the mechanism: subsistence buildings "operate on any unclaimed arable land" and produce in kind (`vanilla localization/english/concepts_l_english.yml:705`); `building_subsistence_output_add` is the in-kind income that is not paid from building revenue (`docs/modifiers.log:118`, mult `:122`). `PENDING in-game confirmation`: Market > supply/demand for grain, wood, fabric and clothes with the sell orders by building type (does subsistence output reach the market, or only the wheat farm and logging camp?). `arable_land_engine_research.md` section 3 stays as written unless this reading contradicts it.
- `PENDING in-game confirmation`: whether TLS is its own market or shares one. If it shares one, the supply analysis must include that market's other buildings.

Verdict: building gap **gap** (FU-1, small-state quantization and no industry placement); processing goods locked by tier-6 tech **intended per current calibration, design question** (FU-3); resource-gated goods **placeholder** (#3675 / #3684 / #3687 / #3688); the grain and wood glut **PENDING in-game confirmation** (hypothesis only).

## 5. Institutions

**Finding: the empty Institutions tab is expected at this start.**

- `common/institutions` is not in `replace_paths` (`.metadata/metadata.json`), so the institutions load from vanilla. The Institutions panel lists laws that provide an institution. Every such law in `common/laws/` except one is gated on a tech TLS lacks: schools (`rationalism`, `academia`, `empiricism`), health (`medical_degrees`, `pharmaceuticals`), police (`tech_bureaucracy`, `law_enforcement`, `mass_surveillance`), colonial affairs (`colonization`), workplace safety (`labor_movement`, `human_rights`), social security (`democracy`, `labor_movement`, `human_rights`), and the home-affairs laws `law_national_guard` (`law_enforcement`, `common/laws/00_internal_security.txt:22-36`) and `law_secret_police` (`central_archives`, `:67-81`). None of those techs is in TLS's tier-6 set.
- The one exception is `law_guaranteed_liberties` (`common/laws/00_internal_security.txt:106-117`, institution `institution_home_affairs`): it lists `unlocking_laws = { law_right_of_assembly law_protected_speech }`, and `law_right_of_assembly` is active at start (`common/scripted_effects/00_political_setup.txt:63`, `:86`). So it is available at start by the file's data. Whether it is enactable (interest-group support) and how the engine reads a two-law `unlocking_laws` list are `PENDING in-game confirmation` (Laws > Internal Security).
- "No Laws providing Institutions" therefore means no active law provides one, which matches the starting law set (none of the active laws in section 3 carries an `institution` line).

Verdict: **intended**. AC3 asks for the decision to be "noted where players will see it"; this document is not shipped (`planning/` is outside the deploy set). See the open question in section 7.

## 6. Verdict table and follow-ups

| Symptom | Cause (from files) | Verdict |
|---|---|---|
| Minting 559 of 864 | `base_values` flat 500 plus `country_gdp`; no other source | intended (vanilla) |
| Income and dividend tax 0 | `law_land_based_taxation` has no income or dividend terms | intended |
| Consumption tax 0 | no `add_taxed_goods` in generated country history | placeholder (#6375, generator "a later task"); producibility rule is a gap (FU-2) |
| Planned tax data inert | `mapgen/config/country_history/` its tax data is read by no generator (correction 2026-10-23, #9028: pop history reads its slavery law and tech tier, country history its slavery law); TLS inherits wine | gap (FU-2) |
| No buildings in 4 of 5 states | `workforce_share` 0.2 times pop under about 25,000 rounds to no level | gap (FU-1) |
| No processing industry anywhere | all processing buildings need `manufacturies`+; archetypes place none; tier-6 tech | gap (FU-1) and design question (FU-3) |
| Resource goods absent | all 524 states carry the same placeholder resources | placeholder (#3675, #3684, #3687, #3688) |
| Timber about -58%, grain about -62% | hypothesis: subsistence output reaching the market | PENDING in-game confirmation |
| Most other goods at +75% | demand about double supply; not read as zero supply | PENDING in-game confirmation |
| Institutions tab empty | all institution laws but one are tech-gated; active laws provide none | intended; note placement per section 7 |

Follow-up drafts (to be filed after a duplicate check on the board, finished items included):

- **FU-1 (gap): Building history places no industry.** **Done in #6637 (commit 428a020):** archetypes carry an `industry` field and a small-state minimum level exists (units below about 12,900 pops stay on subsistence, intended). Add an industry/manufactory field to the archetypes (or a per-tag `set`) so tier-5+ tags start with food, textile and furniture where canon supports it; review the small-state quantization (under about 25,000 pops gives no buildings) and the construction-sector-0 archetypes. Touches `mapgen/config/building_history/`, `mapgen/worldgen/building_history.py`, the validator and the regenerated `common/history/buildings/`.
- **FU-2 (gap): Generate country history from `mapgen/config/country_history/`** (laws, tax level, taxed goods, institutions) instead of `effect_starting_politics_traditional`, with a rule that `taxed_goods` must be producible by the tag's market. TLS's entry is only `profile: wood_elf_realm` at low confidence, so this changes little for TLS until per-tag laws exist. Cite `mapgen/validate_country_history.py:6` and `mapgen/config/country_history/README.md:3`, which already call the generator "a later task", when checking for duplicates.
- **FU-3 (design question, Chris and game-designer): tier-6 isolated markets.** **Resolved by #9035 (2026-10-25):** ogres get `manufacturies`, Norsca/orcs/goblins `urbanization`, the Ungol a new preset, wood elves `enclosure` and `urbanization` (no industry, deliberately), and the vampire realms take their culture's neighbours' knowledge (Empire, Tomb Kings, Bretonnia; STR keeps the vampire preset). Closed markets come from the law data, not from missing trade tech.
- Resource placeholders are not a new item: comment on #3684 instead.

## 7. Open question: AC3

AC3 says to note the empty-Institutions decision "where players will see it". Nothing in `planning/` reaches a player. Recommended: record the decision in this audit (section 5) and reword AC3 to that; a player-facing tooltip or localization note would be a separate follow-up with its own in-game and `error.log` gate. Alternative: add a localization note inside this item, which turns it from docs-only into a game-read change. Chris decides.

## 8. Manual checks (Chris, fresh TLS start from HEAD after `.\deploy.ps1`)

Use a fresh start; a save from an older build may differ from HEAD. Each line closes one `PENDING in-game confirmation` marker above; post the readings on #6577 and the verdicts get finalized and the markers removed.

- [ ] Budget > Minting tooltip: the base and GDP terms (section 2; expected 500 plus about 59 if the file reading holds).
- [ ] Budget > tax lines: land tax versus tariffs, and the active tax level (section 3).
- [ ] Market > supply and demand for grain, wood, fabric and clothes, with sell orders by building type: does subsistence output reach the market (section 4.3)?
- [ ] Market > member countries: is TLS its own market (section 4.3)?
- [ ] Laws > Internal Security: does Guaranteed Liberties appear, and is it enactable (section 5)?
- [ ] Construction > point source: the construction sector is not built, yet the tab may show "1 under construction"; what is the source?
- [ ] Identify the "2 of 10" slots panel seen in the report.
