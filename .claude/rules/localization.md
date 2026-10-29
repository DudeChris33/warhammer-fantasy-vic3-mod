---
paths:
  - "localization/**/*"
---

# Localization Rules (`localization/`)

**Read when:** you are adding or changing any `.yml` under `localization/`, or authoring script that needs user-facing keys. **Covers:** loc format, file naming, new vs replace, the shared names file and vanilla-collision overrides. Loads automatically when you open a matching file with the Read tool — a starting point, not a boundary: read any other guide that would help, and read a neighbour whenever your work touches its area.

**Related guides:**
- [peoples.md](peoples.md) — culture, religion and country display-name keys
- [testing.md](testing.md) — generated map loc (state, hub, sea, canal names) is owned by the map pipeline
- [scripting.md](scripting.md) — `custom_localization.log` and general script rules

## Organization

- `localization/english/` — loc entries for new content this mod adds.
- `localization/replace/english/` — loc entries that override/replace vanilla base-game text. Use this instead of editing base-game files (which aren't part of this repo).
- Every `.yml` loc file must start with `l_english:` on its own line (UTF-8 with BOM, standard Paradox requirement) and use `\tkey:0 "text"` entries.

## Patterns

- Every key referenced by script (event titles/descriptions, decision names, building names, modifier display names, custom localization per `docs/custom_localization.log`) must have a matching loc entry — a missing key shows the raw key string in-game or crashes on some UI lookups.
- Keep loc file names aligned with the script folder/topic they cover (e.g. loc for `common/buildings/` content in a buildings-themed loc file). The culture foundation established the base convention: `localization/english/culture_foundation_<area>_l_english.yml`, split by database area — `..._heritages_`, `..._languages_`, `..._religions_` — carrying the display-name keys for the matching `common/discrimination_trait_groups/`, `common/discrimination_traits/` and `common/religions/` entries. Follow that `<topic>_<area>_l_english.yml` shape for later content.
- The Old World cultures established a second, per-database-file variant: one `localization/english/cultures_<group>_l_english.yml` per `common/cultures/*.txt` script file, carrying just the culture id → display-name keys for that file. `common/cultures/` groups by RACE/CULTURE-GROUP rather than region, so `<group>` is the race/group name (e.g. `cultures_imperial_humans_l_english.yml` for `imperial_humans.txt`, `cultures_greenskin_l_english.yml` for `greenskin.txt`), not a region.
- They also established a **shared, append-only** loc file for per-name display keys: `localization/english/cultures_names_l_english.yml`. Victoria 3 names are global, not per-culture, so this single file carries one key per unique name string used across every `common/cultures/*.txt` file, and every culture-authoring change appends to it rather than creating a new file. Before adding a name key, check it isn't already shipped by vanilla's own `localization/english/names_l_english.yml` (and any future `localization/replace/english/` override of it) — a key defined in both places is a duplicate-key error in the game log, so this file carries only names vanilla does not already key. Names vanilla already keys stay in the culture's name lists in `common/cultures/*.txt` but get no entry here.
- Display keys of country tags whose bare tag or `_ADJ` collides with a vanilla loc key (e.g. `MAR`) live in `localization/replace/english/countries_<region>_l_english.yml` rather than the `localization/english/` file for that region. Same rule as the states file below: the mod's name overrides vanilla's outright rather than dodging with a numeric fallback.
- `localization/replace/english/map/states_l_english.yml`, emitted by `mapgen/generate_land_regions.py`, is the first **generated** file to live under `localization/replace/english/` (never hand-edited — same "regenerate, don't edit" rule as any other generated map file). Land canon names are Warhammer-world region names, and one can coincide with a real-world vanilla Vic3 state name purely by chance (found via `STATE_AQUITAINE`, an in-game duplicate-loc-key error) — the mod's own name overrides vanilla's outright in that case rather than dodging the collision with a numeric fallback key, so the file is named and placed to match vanilla's own `states_l_english.yml` exactly. `validate_map.py`'s loc-coverage check reads both `localization/english/map/` and `localization/replace/english/map/` for this reason.
- `localization/replace/english/map/wh_hub_names_l_english.yml` (hub names, same generator) lives in `replace/` for the same reason: vanilla's `hub_names_l_english.yml` also defines `HUB_NAME_STATE_AQUITAINE_*`, and a file under `localization/english/map/` raised five duplicate-key errors.

- **Never give a mod loc file the same filename as a vanilla one under `localization/english/`.** The game shadows the whole vanilla file, so every vanilla key in it shows as a raw key in-game (hit with `characters_l_english.yml`, `power_blocs_l_english.yml`, `themes_l_english.yml`: `ideology_child`, `identity_sovereign_empire`, `notification_power_bloc_formed_name`). New content uses a `wh_`-prefixed or topic-unique name; deliberate same-key overrides go in `localization/replace/english/` (same filename is fine there). Check `game/localization/english/` for the name before creating a file.
- Culture, religion, and heritage/language trait and trait-group display names never start with "The": vanilla prints them mid-sentence, so a leading "The" renders "of the The …". Vanilla `acceptance_statuses_l_english.yml:87` is "of the [Religion.GetName] [concept_religion]", `:46` is "[Culture] [Religion] [PopType]", and `interfaces_l_english.yml:4791-4792` is "a homeland of the [Culture.GetName] culture, which shares the … [DiscriminationTrait.GetName]" / "[DiscriminationTraitGroup.GetName]". An inner "the" is fine ("Lady of the Lake", "Cult of the Ancestors"). Fixed for `old_faith`, `the_lady`, `mortuary_cult`, `the_great_maw` and `heritage_group_great_maw` in #8491.
- **Ideology names live in `localization/replace/english/wh_ideologies_l_english.yml`** (#9197, Chris 2026-10-29). The mod defines ideologies in `common/ideologies/` but has no ideology loc of its own; every display string is vanilla's, so a rename is an override of the vanilla key (ids never change). `ideology_fascist` = "Ironist", `ideology_integralist` = "Dogmatist", `party_fascist` = "Iron Party", to match the Iron State government. `*_movement` and `state_pop_support_movement_*` names inherit through `$...$`; keys that hard-code "Fascist" in prose are overridden one by one. Communist, Anarchist, Social Democrat, Vanguardist, Luddite and Utilitarian are kept. Event and vanilla fascism journal-entry strings are unreachable (`events/` is blanked; the mod has no `je_fascism_*`) and are left alone.

## Forbidden

- No hardcoded personal/local file paths in loc text.
- No editing vanilla loc files directly — use `localization/replace/english/` instead.

## Vanilla loc reference

Vanilla key names live in `game/localization/english/` in the vanilla install — check it to know what `localization/replace/english/` must override (install path and read-only rule: [core.md](core.md)).
