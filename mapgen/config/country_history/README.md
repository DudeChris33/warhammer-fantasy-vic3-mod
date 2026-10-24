# Starting-country data (`mapgen/config/country_history/`)

Hand-authored input for a later generator that writes `common/history/countries/`. **Two generators read this folder** (everything else here is still unread by the game): `generate_pop_history.py` (each tag's slavery law gates `slaves` pops) and, since #9028, `generate_country_history.py` (the slavery law only, as `activate_law`, until #6638 emits the rest), both through `mapgen/worldgen/country_config.py`. The files describe what each start tag looks like in **2502 IC** in this mod's Victoria 3 mechanics. `python mapgen/validate_country_history.py` is the gate; `python mapgen/run_fixture.py --check` regression-tests the validator against `mapgen/fixtures/country_history/`.

- One file per region, `NN_<stem>.json`, the same `NN_<stem>` as `common/country_definitions/` and the region files in `planning/tag_registry.md` (17 files: 00–13, 17–19; regions 14–16 are deferred with no tags).
- One entry per **start** tag of that region in the registry (231 in all, counted from the files; `UNO` has none). Formables are out of scope and rejected. Tags with no `common/country_definitions/` entry yet (most of 08–13 and 17–19) still get entries; the generator skips them until their definitions exist.
- Every non-default choice carries a `source` and a one-line `why`. Sources are `canon: …` (tabletop first), `TW:…` where tabletop is silent, `derived` (follows mechanically from other fields) or `inferred`. Anything the mod cannot express is listed under *Mechanics gaps*, never authored around.

## Starting technology

This folder holds **no** technology. A tag's starting tech is what `generate_country_history.py` emits: the preset of its first culture (`CULTURE_TECH` in `mapgen/worldgen/country_history.py`, with the per-tag `TAG_TECH` exceptions) from `common/scripted_effects/00_starting_inventions.txt`, plus its row in `mapgen/config/starting_tech_extras.json`. The validator imports those helpers and checks every law's `unlocking_technologies` against that coverage, so the linter and the generator cannot disagree (#8459). A tag with no country definition warns (`tech not evaluable`) and its laws are not lock-checked until a definition lands. If a law is locked, swap it for the nearest allowed law (with a `why`) or add the tech to `starting_tech_extras.json`; never put tech in these files.

## File shape

```jsonc
{
  "region": "02_empire",              // = file stem
  "baseline": { … },                  // the region default, every tag inherits it
  "profiles": { "name": { … } },      // optional named partial packages (see below)
  "tags": {
    "REI": {
      "profile": "name",              // optional: layer this profile over the baseline
      "confidence": "high",           // high | medium | low  (low = baseline left for lack of canon)
      "note": "free text",            // optional
      "tax_level": "high",            // any baseline field: only what differs
      "laws": { "lawgroup_economic_system": "law_interventionism" },   // per-group override
      "justify": {                    // one entry per overridden field / law group
        "tax_level": { "source": "canon: …", "why": "one line" },
        "laws.lawgroup_economic_system": { "source": "…", "why": "…" }
      }
    }
  }
}
```

**Baseline / profile / tag fields**

| Field | Meaning (generator emits) |
|---|---|
| `laws` | **all 24** law groups → `activate_law = law_type:<law>`; overrides merge per group. Presets (`effect_starting_politics_*`) are not used, so nothing fills a group silently |
| `ruling_igs` | 1–3 distinct ids → `ig:<ig> = { add_ruling_interest_group = yes }` |
| `tax_level` | `very_low … very_high` → `set_tax_level` |
| `taxed_goods` | good ids (no `g:`) → `add_taxed_goods = g:<good>` |
| `tariffs` | optional `[{goods, kind: import\|export, level}]` → `set_<kind>_tariff_level` |
| `institutions` | `{institution_id: 0–5}` → `set_institution_investment_level` |
| `next_election` | `YYYY.M.D` ≥ 2502.1.1 → `set_next_election_date`; **present iff a voting-franchise law is active** (`null` in a tag removes an inherited date) |
| `expected_government_type` | a `common/government_types/` id whose `possible` the laws must satisfy; the generator does not emit it |
| `suggested_ig_names` | `{ig: "Setting name"}` — **note only**, no loc is authored here |
| `source`, `why` | required on the baseline and on every profile |

**Profiles are an extension of the brief.** A region whose tags fall into two or three genuinely different packages (a tribal confederation inside feudal Kislev, greenskin holdouts inside Bretonnia, vampire lords inside the Southern Realms) would otherwise repeat 20 law overrides per tag with 20 identical justifications. A profile is a named partial package with **one** `source`/`why` for the whole bundle; a tag layers `baseline ← profile ← its own overrides`. Tag-level overrides on top of a profile still need their own `justify` entries. Profiles are region-local.

`expected_government_type` overrides on a tag and the matching `next_election` changes are generated mechanically from the tag's laws and country tier (`source: derived`); the substantive choices are the laws.

## Mapping conventions

- **Electoral aristocracies** (Ulthuan's princes, the Moot's Elder) → `law_landed_voting`; **hereditary Elector Counts and Tilean merchant princes** → `law_oligarchy` (no provincial election; the Emperor's election is gap #2); **merchant republics** (Marienburg, and Remas and Verezzo on non-tabletop sources) → `law_wealth_voting`; **absolute rulers** (Tzar, Sultan, Witch King, Dragon Emperor, Tyrants, Warbosses) → `law_autocracy`; **council-of-nobles rule** → `law_oligarchy`. Priest-rule (Chaos Dwarf Sorcerer-Prophets, Slann, the Everqueen, Khainite Har Ganeth, the Knights of Origo) → `law_theocracy`.
- **Knights, Slayers, Saurus and Executioners** → `law_warrior_caste`; **state troops** → `law_national_militia`; **mercenary and standing regiments** → `law_professional_army`; **raised dead** → `law_peasant_levies`.
- **Tribes** (Norse, Ungol, Kurgan, greenskin) take `law_chiefdom`: #9037 widened it, and `law_elder_council`'s visibility, from decentralized countries to `wh_country_is_tribal_realm` (`unrecognized` and a tribal culture, `common/scripted_triggers/02_wh_tribal_triggers.txt`). Greenskins read as `gov_greenskin_warband` (Warboss), the others as `gov_chiefdom` (Chieftain). `generate_country_history.py` emits the law (ahead of #6638). Vampire, Skaven, wood elf and ogre tags keep monarchy.
- **Species with no gendered social structure** (greenskins, Ogres, Lizardmen) take the group default `law_no_womens_rights` as filler; Dwarfs, Elves and humans take `law_women_own_property` unless canon says otherwise. `rights_of_women`, `welfare`, `childrens_rights`, `labor_rights` and `free_speech` are otherwise the only choices the lower tiers can reach, so they are rarely a canon claim.
- `taxed_goods` (liquor, wine, tea, coffee, meat…) and institution levels are flavour picks marked `inferred` through the baseline `source`; they carry no canon claim.
- Where a tag's starting tech cannot reach a law, the data uses the nearest reachable law and says so in `why` (or, for a few canon cases, the tag gets an extra in `starting_tech_extras.json`).

## Validator

```
python mapgen/validate_country_history.py                 # all regions
python mapgen/validate_country_history.py 02_empire.json  # one
python mapgen/validate_country_history.py --vanilla "<Victoria 3>/game"   # read goods/institutions from vanilla
python mapgen/run_fixture.py --check                       # includes the validator fixture
```

Hard errors (exit 1): unknown law, law group, interest group, tech, good, institution or tax/tariff level; a law under the wrong group, several laws in one group, or a missing group; a law whose unlock (`unlocking_technologies` or `unlocking_laws`) is not covered; an extra in `starting_tech_extras.json` that is an unknown tech, lacks its prerequisite or is keyed on a formable; chosen laws where one `disallowing_laws` the other; a tag not in the registry, in another region, a formable, or a start tag with no entry; laws that fail `expected_government_type`'s `possible`; missing/stale/redundant `justify` entries or a missing `confidence`; a malformed or inconsistent `next_election`. Output is sorted and deterministic.

Modelling assumptions (verify in game when the history files load):

- The presets list every tech they grant (no `add_era_researched`; `load_preset_techs` ignores it), so the validator and the generator see the same techs.
- A law is unlocked when **any** of its `unlocking_technologies` is covered **or any** `unlocking_laws` is active.
- `country_has_voting_franchise` = one of `law_landed_voting`, `law_wealth_voting`, `law_census_voting`, `law_universal_suffrage`.
- Start tags are independent (`is_subject_type` false), have no regency and no runtime variables; `ruler ?= { … }` triggers are unresolvable.
- Government tier and country type come from `common/country_definitions/`. Without a definition, tier-dependent government triggers cannot be evaluated: the validator **warns** (60 tags today) instead of failing, and the check turns into an error the day a definition lands with a different tier.
- Goods and institutions are vanilla's (`common/goods`, `common/institutions` are not in `replace_paths`). The vanilla install was not reachable while authoring, so the validator carries a bundled list (Victoria 3 1.13, cross-checked against ids the mod's laws and `docs/*.log` mention) and uses `--vanilla` or the game root when those folders exist.

## Mechanics gaps

Warhammer concepts the mod's laws, IGs and techs cannot express (reported, not authored):

1. **Tribal governance.** *Resolved (#9037):* `law_chiefdom` and `law_elder_council` are visible to tribal realms through `wh_country_is_tribal_realm`; tribal tags start under Chiefdom (greenskins as a Warband).
2. **Electoral college.** No law for an Emperor chosen by Electors; `law_landed_voting` gives *provincial* elections that canon does not have.
3. **Undead and vampiric rule.** Eternal rulers, raised legions, blood-stock peasantry: approximated by autocracy, `peasant_levies`/`professional_army`, `serfdom` and `debt_slavery`.
4. **Chaos worship and cult schisms.** No law or IG for a Ruinous Power; approximated by `ig_devout` in the ruling bloc.
5. **Confederation of warbands** (Border Princes, Eastern Steppes, greenskin Waaagh!) — the registry already asks for a law/government variant.
6. **Merchant-house republics** with no head of state (Marienburg, Tilea) fit parliamentary/presidential republic + wealth voting only loosely; no "Doge" or council-of-ten.
7. **Magic institutions** (Colleges of Magic, Saphery's White Tower, Lizardmen Slann, Chaos Dwarf Daemonsmiths): no IG or tech; `ig_intelligentsia`/`ig_devout` stand in.
8. **Guilds as political bodies** (Dwarf Engineers' and Runesmiths' Guilds): `ig_industrialists`/`ig_devout` stand in.
9. **Castes** (Lizardmen Saurus/Skink/Kroxigor, Chaos Dwarf Overseers, Cathay's mandarins) beyond `law_warrior_caste`.
10. **Slave-raiding economies** (Druchii, Chaos Dwarfs, Norse) are one law group (`slavery`); no raid-driven income model.
11. **Technology by branch.** One preset per people cannot express Elves (high society, low industry), Ogres (gunpowder, no bureaucracy) or Cathay (rockets, closed borders): `starting_tech_extras.json` patches a few cases. Human Sylvania and the Moot no longer start behind the Empire, because they have no preset of their own (they take the Empire preset by culture).
12. **Colonial administration.** The High Elf colonies (`CDU`, `FDW`, `TEL`, `TOS`, `GCL`, `TEH`, #8444) are `colonial` subjects of Lothern but do not take `law_colonial_administration`: `generate_country_history.py` emits the culture preset, `effect_starting_politics_traditional` and only this folder's slavery law (#9028). They run as `gov_principality` (profile `asur_colony` in `17_ulthuan.json`), not as `gov_colonial_administration`/`gov_crown_colony`, until the generator emits laws.

Also flagged for the tag registry: `KON` (Konquata) is "founded 2520 IC", eighteen years **after** the 2502 start.
