# Starting buildings (`mapgen/config/building_history/`)

Hand-authored input for `mapgen/generate_building_history.py`, which writes `common/history/buildings/NN_<stem>.txt` (one file per `map_data/state_regions/NN_<stem>.txt`). Nothing here is game-read. The 2502 IC start date is fixed.

## The tech gate (read this first)

A building or production method placed in a country that has not researched its unlocking technology **crashes the game at load**. So:

- **What a tag has researched comes only from `common/history/countries/*.txt`**: its `effect_starting_technology_tier_N_tech` (expanded through `common/scripted_effects/`, nested effects included) plus any `add_technology_researched`. Never from `mapgen/config/country_history/`, a definition's `tier`, or lore. A tag whose block cannot be fully evaluated (unknown construct, duplicated or missing block) is **unresolved**: no techs and no laws.
- A building needs **every** tech in its `unlocking_technologies`; a building with a `possible` trigger is never emitted. This covers `building_manor_house`, `building_financial_district` and anything else emitted as a side effect.
- Exactly one production method per group, each passing: every tech; `unlocking_laws` all active and `disallowing_laws` none active (the tag's starting laws are expanded from `effect_starting_politics_*`; an unresolved tag fails any method with a law condition); `unlocking_production_methods` among the building's other chosen methods; none of `unlocking_principles` / `unlocking_identity` / `unlocking_company_categories` / `unlocking_geographic_regions`. The strict reading (all, not any) is used throughout, so the gate can only reject more than the engine. The `is_default` method is preferred, else the first permitted. A group with no permitted method **drops the building** (reported).
- An override that asks for a building or method the owner has not unlocked is a **hard error** naming tag, state, building / method and the missing tech. Nothing is silently downgraded.
- `mapgen/validate_building_history.py` re-derives all of this from the emitted files and the current country history with separate code. `generate_building_history.py --check` runs it, so a later change to country history that invalidates a building fails the gate. **Any change to country history requires re-running the generator.**

What a tag can build depends on its starting-technology preset (its culture's `effect_starting_technology_*`, plus `starting_tech_extras.json`), read from the emitted country history. A realm without `manufacturies` (22 owners at #6637: wood elves, vampires, Norsca, ogres, ...) cannot build any industry building, so the `industry` an archetype lists is dropped for it and the drop is reported; #9035 decides whether they should. Canon that needs more is in `blocked.json` → `blocked_by_tech`.

## Files

| File | Contents |
|---|---|
| `profiles.json` | `archetypes` (named development packages, each with `source` + `why`) and `tags` (every tag that owns a non-UNO state names one archetype; a tag-level `set` overrides single fields and needs a `justify` entry per field) |
| `state_overrides.json` | Per-state canon specifics, keyed on the canon state key **and** its `naming_anchor` from `state_ownership.json`, never the STATE number. `buildings` is `{building_id: levels}`; optional `owner` for a split state. Each has `source` (canon citation, Total War, or `inferred`) and `why`. |
| `blocked.json` | `blocked_by_resources` (canon buildings the state has no resource for yet), `blocked_by_tech` (canon the owner cannot build yet) and `gaps` (Warhammer concepts with no fitting building). Never emitted. The generator warns when a blocker has gone away. |

### Archetype fields

`admin` (government administration levels, placed in the tag's most populous state), `barracks_levels` split over the `barracks_states` most populous states, `construction` (construction sector levels, top state), `port_level` in up to `port_states` port-hub states, `trade_level` in up to `trade_states` states (port states first), `farm_share` and `logging_share` (fraction of the state's `arable_land` / logging cap worked commercially; the rest stays subsistence), `workforce_share` (cap on jobs, as a share of the state's pops), and `industry` (`{building id: levels}` of `01_industry.txt` buildings, e.g. `building_food_industry`, `building_textile_mill`, `building_furniture_manufactory`, placed in the tag's most populous state *before* ports, trade and farms so the capital's workforce share feeds them first; the tech gate drops what the owner cannot build; a tag-level `set` of `industry` replaces the whole object and needs a `justify`; `{}` for none).

## Rules the generator enforces

- **Resource limits** (state resources are placeholders today: `arable_land = 10`, wheat + livestock, logging 10, no mines): an arable building must be in the state's `arable_resources` and total arable levels fit `arable_land`; a capped building must be in `capped_resources` within its cap; port-type buildings (`city_type = port`) only in states with a `port` hub.
- **Jobs vs. pops**: jobs per level are the sum of `building_employment_*_add` under `level_scaled` of the chosen methods. Total jobs in a (state, owner) may not exceed **40 %** of that owner's pops in `common/history/pops` (hard cap, also checked on the plan); an archetype's `workforce_share` sets the working target at or below that (20-40 %). Buildings that no longer fit are clipped or dropped, and the rest of the pops stay on subsistence. Subsistence buildings are never emitted (the game creates them).
- **Ownership** (as vanilla `common/history/buildings`): government, military and construction buildings, ports and trade centres are country-owned (`add_ownership = { country = { country levels } }`). Resource buildings (farms, ranches, plantations, mines, logging) are owned through `building_manor_house` and industry (incl. shipyards) through `building_financial_district`, via `add_ownership = { building = { type country levels region } }`. Vanilla never creates the manor house / financial district itself (the game builds it from `add_ownership`), so neither does the generator; their jobs still count against the job share, and their techs are gated like any building. A tag with `law_collectivized_agriculture` (resource buildings) or `law_command_economy` (industry), an unresolved tag, or one that cannot place the owner building keeps them country-owned. No start tag runs those laws today.
- **Small-state minimum (#6637)**: a (state, owner) unit that would end with no job-bearing building gets one level of its first eligible farm, or failing that its logging camp, even past its `workforce_share` but never past the 40 % hard cap (the owner building's jobs count against it). A unit below about **12,900 pops** (5,000 jobs per rural level plus a manor house's 150, over 40 %) cannot staff even one level and **stays on subsistence: that is intended**, not a gap (15 units at #6637, e.g. Tyr Vanna 10,838).
- Only (state, owner) pairs that `common/history/states` creates; nothing for `c:UNO`.
- **Hard errors**: an unknown id, an override whose key and anchor do not match a state, a tag with no profile, a tech-gate violation, an override that breaks a resource, port or job limit.

## Checked against vanilla

The `create_building` / `add_ownership` shapes, `region = "STATE_X"`, `reserves = 1` and the `activate_production_methods` list were checked against vanilla `game/common/history/buildings/` (private mirror `DudeChris33/game---copy`).
