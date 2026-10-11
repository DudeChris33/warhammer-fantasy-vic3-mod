# Starting-country data (`mapgen/config/country_history/`)

Hand-authored input for a later generator that writes `common/history/countries/`. **Nothing here is game-read**: the files describe what each start tag looks like in **2502 IC** in this mod's Victoria 3 mechanics. `python mapgen/validate_country_history.py` is the gate; `python mapgen/run_fixture.py --check` regression-tests the validator against `mapgen/fixtures/country_history/`.

- One file per region, `NN_<stem>.json`, the same `NN_<stem>` as `common/country_definitions/` and the region files in `planning/tag_registry.md` (17 files: 00–13, 17–19; regions 14–16 are deferred with no tags).
- One entry per **start** tag of that region in the registry (223 in all). Formables are out of scope and rejected. Tags with no `common/country_definitions/` entry yet (most of 08–13 and 17–19) still get entries; the generator skips them until their definitions exist.
- Every non-default choice carries a `source` and a one-line `why`. Sources are `canon: …` (tabletop first), `TW:…` where tabletop is silent, `derived` (follows mechanically from other fields) or `inferred`. Anything the mod cannot express is listed under *Mechanics gaps*, never authored around.

## Tech-tier calibration

Recorded **before** any tag was assigned. The tiers are the mod's `effect_starting_technology_tier_N_tech` helpers (`common/scripted_effects/00_starting_inventions.txt`), read as industrial-era terms: tier 1 is Victoria 3's 1836 cutting edge (railways, steam, staff colleges), tier 7 is nothing at all.

| Tier | What the helper grants | Who sits here in 2502 IC, and why |
|---|---|---|
| 1 | Every era-1 tech + railways, mechanical tools, atmospheric engine, screw frigate, general staff, central archives, central banking… (13 era-2 techs) | **Chaos Dwarfs of Zharr-Naggrund only**: hell-forge industry, Iron Daemons, Hellcannons, Dreadquake mortars — the sole real industrial revolution in the setting |
| 2 | Every era-1 tech + mechanical tools, atmospheric engine, dialectics, egalitarianism, corporate charters | **Dwarf engineer-holds** (Karaz-a-Karak, Zhufbar: gyrocopters, organ guns, the Engineers' Guild), **Nuln** (Imperial Gunnery School, steam tanks), the other Chaos Dwarf cities, the **Imperial court of Cathay** (rocket batteries, Sky-Lanterns) |
| 3 | 31 era-1 techs: standing army, line infantry, artillery, academia, colonization, law enforcement, medical degrees, currency standards | The **rest of the Empire** (state troops, handgunners, cannon), **Marienburg** (+ banking, stock exchange), living **Dwarf holds**, the **Tilean** city-states, **Cathay**, **Ulthuan**, **Naggaroth** (Repeater crossbows, corsair fleets) — gunpowder or equivalent craft, no steam industry |
| 4 | 20 era-1 techs; no currency standards, colonization, law enforcement or academia | **Estalia**, **Araby** (learned but pre-industrial), Sartosa, the Moot, Sylvania, Solland, **overrun/besieged Dwarf holds** (industry lost) |
| 5 | 10 techs: manufacturies, shaft mining, standing army, drill, navigation, urbanization, rationalism, bureaucracy, international trade | **Bretonnia** (knights disdain powder), **Kislev**, the **Border Princes**, **Nehekhara** and the vampire realms (ancient arms, undead legions), the **Lizardmen** temple-cities (Old Ones' organisation, no industry) |
| 6 | Enclosure, standing army, urbanization | **Norsca**, Mousillon, the **Ogre** tribes (Leadbelchers and Ironblasters over a tribal floor), hobgoblins, ruined Lizardmen cities, Norse Lustria |
| 7 | Nothing | **Ungol** nomads, **greenskin** mobs (Badlands, Savage Orcs), the **Eastern Steppes** marauders |

Ranking, high to low: Chaos Dwarfs > Dwarf engineer-holds ≈ Nuln ≈ Cathay's court > Empire ≈ living Dwarf holds ≈ Tilea ≈ Ulthuan ≈ Naggaroth > Estalia ≈ Araby > Bretonnia ≈ Kislev ≈ Nehekhara ≈ Lizardmen > Norsca ≈ Ogres > greenskins ≈ Ungols. Effective tags per tier: 1 (1), 2 (6), 3 (49), 4 (21), 5 (55), 6 (37), 7 (27).

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
      "tech_tier": 2,                 // any baseline field: only what differs
      "laws": { "lawgroup_economic_system": "law_interventionism" },   // per-group override
      "justify": {                    // one entry per overridden field / law group
        "tech_tier": { "source": "canon: …", "why": "one line" },
        "laws.lawgroup_economic_system": { "source": "…", "why": "…" }
      }
    }
  }
}
```

**Baseline / profile / tag fields**

| Field | Meaning (generator emits) |
|---|---|
| `tech_tier` | 1–7 → `effect_starting_technology_tier_N_tech = yes` |
| `extra_techs` | ids → `add_technology_researched = <id>`; a tag value **replaces** the list |
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

- **Electoral aristocracies** (the Empire's Electors, Ulthuan's princes) → `law_landed_voting`; **merchant oligarchies** (Marienburg, Tilean republics) → `law_wealth_voting`; **absolute rulers** (Tzarina, Sultan, Witch King, Dragon Emperor, Tyrants, Warbosses) → `law_autocracy`; **council-of-nobles rule** → `law_oligarchy`. Priest-rule (Chaos Dwarf Sorcerer-Prophets, Slann, the Everqueen, Khainite Har Ganeth, the Knights of Origo) → `law_theocracy`.
- **Knights, Slayers, Saurus and Executioners** → `law_warrior_caste`; **state troops** → `law_national_militia`; **mercenary and standing regiments** → `law_professional_army`; **raised dead** → `law_peasant_levies`.
- **Tribes** never take `law_chiefdom`: it is `is_visible = is_country_type = decentralized`, and Norsca/Ungol/greenskin tags are defined `unrecognized`. They take monarchy + oligarchy/autocracy at low tier (see gaps).
- **Species with no gendered social structure** (greenskins, Ogres, Lizardmen) take the group default `law_no_womens_rights` as filler; Dwarfs, Elves and humans take `law_women_own_property` unless canon says otherwise. `rights_of_women`, `welfare`, `childrens_rights`, `labor_rights` and `free_speech` are otherwise the only choices the lower tiers can reach, so they are rarely a canon claim.
- `taxed_goods` (liquor, wine, tea, coffee, meat…) and institution levels are flavour picks marked `inferred` through the baseline `source`; they carry no canon claim.
- Where the tier cannot reach a law (its tech is not in the helper), the data uses the next reachable law or adds a prerequisite chain through `extra_techs`, and says so in `justify`.

## Validator

```
python mapgen/validate_country_history.py                 # all regions
python mapgen/validate_country_history.py 02_empire.json  # one
python mapgen/validate_country_history.py --vanilla "<Victoria 3>/game"   # read goods/institutions from vanilla
python mapgen/run_fixture.py --check                       # includes the validator fixture
```

Hard errors (exit 1): unknown law, law group, interest group, tech, good, institution, tax/tariff level or tier; a law under the wrong group, several laws in one group, or a missing group; a law whose unlock (`unlocking_technologies` or `unlocking_laws`) is not covered; an `extra_tech` whose prerequisite is missing; chosen laws where one `disallowing_laws` the other; a tag not in the registry, in another region, a formable, or a start tag with no entry; laws that fail `expected_government_type`'s `possible`; missing/stale/redundant `justify` entries or a missing `confidence`; a malformed or inconsistent `next_election`. Output is sorted and deterministic.

Modelling assumptions (verify in game when the history files load):

- A tier helper's `add_era_researched = era_N` covers **every** tech of that era (the helpers rely on it: tier 1/2 list only era-2 techs). If the engine grants only the era flag, tiers 1–2 lose their era-1 techs.
- A law is unlocked when **any** of its `unlocking_technologies` is covered **or any** `unlocking_laws` is active.
- `country_has_voting_franchise` = one of `law_landed_voting`, `law_wealth_voting`, `law_census_voting`, `law_universal_suffrage`.
- Start tags are independent (`is_subject_type` false), have no regency and no runtime variables; `ruler ?= { … }` triggers are unresolvable.
- Tier and country type come from `common/country_definitions/`. Without a definition, tier-dependent government triggers cannot be evaluated: the validator **warns** (60 tags today) instead of failing, and the check turns into an error the day a definition lands with a different tier.
- Goods and institutions are vanilla's (`common/goods`, `common/institutions` are not in `replace_paths`). The vanilla install was not reachable while authoring, so the validator carries a bundled list (Victoria 3 1.13, cross-checked against ids the mod's laws and `docs/*.log` mention) and uses `--vanilla` or the game root when those folders exist.

## Mechanics gaps

Warhammer concepts the mod's laws, IGs and techs cannot express (reported, not authored):

1. **Tribal governance.** `law_chiefdom`/`law_elder_council` are decentralized-only; the Norse, Ungol, Kurgan and greenskin tags are `unrecognized` principalities, so they read as monarchies. Either the tag types change or a tribal law is authored.
2. **Electoral college.** No law for an Emperor chosen by Electors; `law_landed_voting` gives *provincial* elections that canon does not have.
3. **Undead and vampiric rule.** Eternal rulers, raised legions, blood-stock peasantry: approximated by autocracy, `peasant_levies`/`professional_army`, `serfdom` and `debt_slavery`.
4. **Chaos worship and cult schisms.** No law or IG for a Ruinous Power; approximated by `ig_devout` in the ruling bloc.
5. **Confederation of warbands** (Border Princes, Eastern Steppes, greenskin Waaagh!) — the registry already asks for a law/government variant.
6. **Merchant-house republics** with no head of state (Marienburg, Tilea) fit parliamentary/presidential republic + wealth voting only loosely; no "Doge" or council-of-ten.
7. **Magic institutions** (Colleges of Magic, Saphery's White Tower, Lizardmen Slann, Chaos Dwarf Daemonsmiths): no IG or tech; `ig_intelligentsia`/`ig_devout` stand in.
8. **Guilds as political bodies** (Dwarf Engineers' and Runesmiths' Guilds): `ig_industrialists`/`ig_devout` stand in.
9. **Castes** (Lizardmen Saurus/Skink/Kroxigor, Chaos Dwarf Overseers, Cathay's mandarins) beyond `law_warrior_caste`.
10. **Slave-raiding economies** (Druchii, Chaos Dwarfs, Norse) are one law group (`slavery`); no raid-driven income model.
11. **Technology by branch.** One tier per tag cannot express Elves (high society, low industry), Ogres (gunpowder, no bureaucracy) or Cathay (rockets, closed borders): `extra_techs` patches a few cases only.

Also flagged for the tag registry: `KON` (Konquata) is "founded 2520 IC", eighteen years **after** the 2502 start.
