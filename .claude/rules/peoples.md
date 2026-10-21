---
paths:
  - "common/cultures/**/*"
  - "common/religions/**/*"
  - "common/discrimination_trait_groups/**/*"
  - "common/discrimination_traits/**/*"
  - "common/country_definitions/**/*"
  - "common/country_formation/**/*"
  - "common/modifier_type_definitions/{culture,religion}_*"
  - "common/static_modifiers/{culture,religion}_*"
  - "planning/tag_registry.md"
---

# Peoples and Polities (`cultures`, `religions`, `country_definitions`)

**Read when:** you are editing cultures, religions, heritage/language trait groups and traits, country definitions, formables, or `planning/tag_registry.md`. **Covers:** entry schemas, the modifier-type/static-modifier registrations every culture and religion needs, and the country/formable layout. Loads automatically when you open a matching file with the Read tool — a starting point, not a boundary: read any other guide that would help, and read a neighbour whenever your work touches its area.

**Related guides:**
- [localization.md](localization.md) — display-name keys, the shared names file, country loc (including `replace/` for tags that collide with vanilla)
- [heraldry.md](heraldry.md) — every new tag needs a coat of arms and a flag definition
- [scripting.md](scripting.md) — `replace_paths`, the `docs/*.log` authority, resolve-or-dangle checks against authored ids
- [testing.md](testing.md) — capital `STATE_*` ids come from the generated state files

## Naming

- `common/cultures/` groups by RACE/CULTURE-GROUP, not by region (the culture foundation itself uses zero-padded `NN_<topic>.txt` files — see [scripting.md](scripting.md), *Naming*): a plain descriptive snake_case filename per group (`norscan_humans.txt`, `imperial_humans.txt`, `dwarven.txt`, `greenskin.txt`, `vampire.txt`, `chaos_dwarf.txt`, `nehekharan_araby.txt`, etc.), with every culture belonging to that race/group defined inside it regardless of which region's states its population actually lives in (Chris, 2026-09-03; supersedes this folder's original `NN_<region>.txt` layout from board item #3405). A culture id is global and referenced by other files (e.g. `common/country_definitions/`) purely by id, so this reshuffle never touches those ids — only which file defines them.

## `common/cultures/` entry schema

Nothing in `docs/*.log` documents the `common/cultures` database — this schema was confirmed against a vanilla reference install/repo via real in-game `error.log` testing, not guessed. (Established by the Old World cultures work.) Every culture entry needs:

- `color = rgb{ R G B }` (0-255 integers; `hsv{ h s v }` is the other valid form) — cosmetic only.
- `religion = <id>` — a religion id from `common/religions/`.
- `heritage = <id>` and `language = <id>` — **separate top-level fields**, each a single discrimination-trait id from `common/discrimination_traits/`. They are NOT wrapped in a `traits = { }` block — that shape was tried and is rejected outright by the parser.
- `traditions = { }` — required; an empty block is currently valid and is what this mod uses.
- `obsessions = { }` — goods ids; empty until this mod defines its own goods (`common/goods/` is not in `replace_paths`, so vanilla's goods still load).
- Name lists (`male_common_first_names`, `female_common_first_names`, `noble_last_names`, `common_last_names`), `graphics` and `ethnicities` using vanilla portrait/graphics ids (custom art is out of scope for now).

Every culture additionally requires, elsewhere:

- Three modifier-type registrations in `common/modifier_type_definitions/`: `country_<culture>_cultural_acceptance_add`, `country_fervor_target_<culture>_add`, `state_<culture>_standard_of_living_add` — each `{decimals=1 color=good game_data={ai_value=0}}` — appended to `culture_cultural_acceptance_modifier_types.txt`, `culture_fervor_target_modifier_types.txt` and `culture_standard_of_living_modifier_types.txt` respectively.
- Six static-modifier blocks (a `_positive`/`_negative` pair for each of the three concepts above) appended to the matching `common/static_modifiers/culture_*_modifiers.txt` file. Victoria 3 requires both variants for every culture id or it's an in-game error. Both use magnitude `1`, differing only by icon (`modifier_flag_positive.dds` / `modifier_flag_negative.dds`) — this is genuine vanilla behavior, confirmed against the vanilla reference, not a mistake to "fix".

These three modifier-type files and three static-modifier files are append-only — every later culture-authoring item adds its own entries to the existing files rather than creating new ones per culture.

## `common/religions/` standard-of-living + icon requirements

Religions carry the same standard-of-living obligation as cultures, and it is a **hard engine
error** if missed (`religion.cpp:92 Missing religion sol static modifier`). Every religion id in
`common/religions/` additionally requires, elsewhere:

- one `state_<religion>_standard_of_living_add` modifier-type registration (`{decimals=1 color=good
  game_data={ai_value=0}}`) in `common/modifier_type_definitions/religion_standard_of_living_modifier_types.txt`
  — vanilla keeps these in its own `99_todo_sort_into_other_files.txt`, this repo splits them out to
  mirror the culture equivalent;
- a `<religion>_standard_of_living_modifier_positive` / `_negative` static-modifier pair in
  `common/static_modifiers/religion_standard_of_living_modifiers.txt`, both magnitude `1`, differing
  only by icon — genuine vanilla behavior, confirmed against vanilla's own
  `common/static_modifiers/08_religion_standard_of_living.txt`, not a mistake to "fix".

Both files are **append-only**: a later religion adds its entries to them rather than creating new
per-religion files.

A religion's `icon` must name a file that actually exists under vanilla's
`gfx/interface/icons/religion_icons/`, or it is a `virtualfilesystem.cpp:569` missing-texture error.
The full vanilla set is: `animist`, `atheist`, `catholic`, `confucianism`, `coptic`, `gelugpa`,
`hindu`, `ibadi`, `jewish`, `mahayana`, `orthodox`, `protestant`, `shiite`, `shinto`, `sikh`,
`sunni`, `theravada` (all `.dds`). Note `confucianism`, not `confucian`, and there is no
`oriental_orthodox` — use `coptic`. These vanilla icons are placeholders pending custom art.

## `common/country_definitions/` + `common/country_formation/` entry schema

Neither database is documented in `docs/*.log`; these shapes were confirmed against the vanilla
install during scoping. **Both folders are listed in `.metadata/metadata.json`'s `replace_paths`**, so
vanilla's own tags do not load — a tag exists only if this mod's files define it.

Files follow an `NN_<region>.txt` shape, one file per Old World region (unlike `common/cultures/`, which groups by race),
named for the region it covers (`02_empire.txt`), with formables split into a sibling
`common/country_formation/NN_<region>_formables.txt`. The tag roster itself is frozen in
`planning/tag_registry.md`; check a code there before authoring it.

**A tag's file is chosen by geography, not by its culture.** A tag lives in the
`NN_<region>.txt` for the region it's physically located in, even when its culture is defined in a
different (and, since `common/cultures/` now groups by race rather than region, differently-named)
`common/cultures/` file — that's a legal cross-file reference, since culture ids are global. Example:
`MOR` (Massif Orcal, a Greenskin holdout in the Bretonnian heartland) and `SKZ` (Skullsmasherz, the
Grey Mountains on Bretonnia's southern flank) are both defined in `03_brettonia.txt` and use
`mountain_orc`/`goblin` culture ids from `common/cultures/greenskin.txt`, because both sit geographically
inside/against Bretonnia even though their population isn't bretonnian. A tag near a region border
needs a real judgment call on which side it reads as.

**Exception — a people with its own registry region keeps its roster together.** When
`planning/tag_registry.md` gives a tag a region whose file is that people's own, the registry's region
column wins over the geography of its states: the Norse dwarf holds (`KRD`, `KOR`, `KRV`) live in
`04_karaz_ankor.txt` and the ogre tribes in `11_ogre_kingdoms.txt` although their states sit in other
regions' state files (#6373). Say so in the file or block comment. A people with no region file of its
own — the wood elves — files each tag by geography as above.

A country definition entry:

```
TAG = {
	color = { R G B }
	country_type = recognized | unrecognized | colonial | company | decentralized
	tier = city_state | principality | grand_principality | kingdom | hegemony | empire
	cultures = { culture_id_1 culture_id_2 ... }
	capital = STATE_<KEY>
}
```

- A start-owner's starting technology comes from its first listed `cultures` entry, not its `tier`: `generate_country_history.py` maps each culture to a culture-group preset (`effect_starting_technology_<group>_tech` in `common/scripted_effects/00_starting_inventions.txt`) through `CULTURE_TECH` in `mapgen/worldgen/country_history.py`, with `TAG_TECH` for exceptions (`UNO`). A new culture, or a tag with no `cultures`, needs a row there or the generator errors ([testing.md](testing.md)).
- `color` uses the **brace** form `{ R G B }` (0-255 integers), not `common/cultures/`' `rgb{ }`.
  Convention: reuse the polity's already-shipped culture color so tag and culture read as one thing;
  a formable that has no culture of its own takes a distinct shade of its heartland's color.
  **Exception — tags defined for the painted start map:** a tag first painted in
  `mapgen/config/state_ownership.png` copies its colour exactly from
  `mapgen/config/state_ownership_legend.json`, because the PNG is keyed on that RGB and the legend
  wins (#6373). Say so in the file's comment above those blocks, and drop the legend entry's
  `proposed` flag (setting its final `name` and `note`) in the same change.
- **A painted start owner needs a definition.** Every owner tag in `mapgen/derived/state_ownership.json`
  must have a non-dynamic entry here (the D00-D99 `dynamic_country_definition` slots don't count), or
  `generate_state_history.py` holds its states back and `validate_map.py` fails ([testing.md](testing.md)).
  It also needs a `mapgen/config/pop_history/calibration.json` total and a `population.json`
  wealth/literacy entry (directly or through a `groups` row), or `generate_pop_history.py` errors, and a
  `mapgen/config/building_history/profiles.json` `tags` row, or `generate_building_history.py` errors (#8444).
- `cultures` ids must exist somewhere under `common/cultures/` — in whichever race/group file that culture is defined (see *Naming* above; no longer a matching-region file).
- A tag's `cultures` no longer drive homelands (#8604): `add_homeland` comes only from the hand-authored `mapgen/config/state_homelands.json` ([testing.md](testing.md)). The owner's `cultures` only seed a new state's row (`--sync-homelands`) and still set the pop-mix fallback for a state whose list is `[]`.
- **Placeholder tags (`XS*`).** A state owner the setting needs but no named polity can yet represent gets
  a deliberately generic stand-in rather than an invented nation. The `XS*` codes are the Skaven ones:
  "Skaven Clan <letter> (placeholder)", adjective "Skaven", `skaven` culture (#8646; goblin until then),
  `unrecognized`/`principality`, filed by the geography of their states, heraldry per
  [heraldry.md](heraldry.md)'s placeholder rule. Each block's comment states the limits. The codes
  are frozen like any shipped tag, so real clans get **new** codes and supersede these tags; a
  placeholder is never renamed into a real polity. Record each one in `planning/tag_registry.md`.
- **`UNO` (Unclaimed Lands)** is the one placeholder that is not painted: the `decentralized`
  owner of every `unowned` and out-of-scope `placeholder` state, mapped from those tokens by
  `generate_state_history.py` (#6391). `common/country_definitions/98_unclaimed.txt`,
  `principality`, `goblin` as a disclosed stand-in culture, no capital, no homelands in its
  states, no legend entry. Never paint it and never rename it into a real polity.
- **Disclosed stand-in cultures.** When no authored culture fits a tag, use the most honest existing
  one and say in the block comment and the registry row what it does not describe (e.g. `BRK`
  `norscan` for a Chaos garrison, `VMP` `sylvanian_vampire` for Kemmler's non-vampire host). Do not
  author a new culture to fill the gap inside a tag item.
- **`capital`** goes right after `cultures`, as in vanilla's `00_countries.txt`, and names a
  `STATE_*` key from `map_data/state_regions/` (Chris-approved, #3658):
  - **C1 canon seat.** A tag's capital is the state holding its canon seat's city hub (any hub
    type), whoever owns that state at start. Claimants and formables keep their canon seat as
    capital even when another tag holds it; vanilla does the same (`POL`, `ITA`, and 12 tags on
    `STATE_AMHARA`). Comment the seat where the state name doesn't make it obvious.
    **Where no named hub exists** (Ulthuan and the High Elf colonies, #8444, Chris-accepted
    2026-10-21), C1 is the state judged to hold the canon seat from the state name and canon
    geography, commented `seat inferred: no named hub`; a seat that cannot be placed with
    confidence falls to C2. A seat that straddles states takes the larger by province count
    (Lothern: `STATE_LOTHERN_WEST`).
  - **C2 no canon seat, owns land.** Use its largest owned state by province count in
    `mapgen/derived/state_ownership.json`, commented `non-canon`; a tie goes to the higher
    `arable_land` (#8444).
  - **C3 no canon seat, owns nothing.** Omit `capital` and write `# capital: none - <reason>`.
  - Never use a `STATE_LAND_<n>` key: it is an unnamed state's key and changes on regeneration.
  - No offline gate checks these keys. After a state rename or regeneration
    (`generate_land_regions`), grep `capital =` in `common/country_definitions/` against
    `map_data/state_regions/*.txt`.

  Per-file status (a file still marked pending keeps its `# capital: <Name> — TODO` comments and
  is not yet out of compliance):
  - `02_empire.txt` — done (#3658).
  - `00_norsca.txt`, `01_kislev.txt`, `03_brettonia.txt` — done (#3659).
  - `04_karaz_ankor.txt`, `10_dark_lands.txt` — done (#3660).
  - `05_southern_realms.txt`, `06_badlands.txt`, `07_nehekhara.txt` — done (#3661).
  - `17_ulthuan.txt` — done (#8444).
  - `11_ogre_kingdoms.txt` — pending. `98_unclaimed.txt` (`UNO`) has no capital by design, and
    `99_dynamic.txt` holds the dynamic slots.

A formation entry stays in the **minor/culture-based shape**:

```
TAG = {
	use_culture_states = yes
	required_states_fraction = 0.75
	ai_will_do = { always = yes }

	possible = {
		is_country_type = recognized
		OR = { country_has_primary_culture = cu:<culture> ... }
	}
}
```

Do **not** add `unification_play`, `leadership_play`, `geographic_region` or any other
major-formation key until the matching plays and regions are authored. `common/diplomatic_plays` now
holds 31 generic plays but none for unification or leadership, and `common/geographic_regions` is still
empty, so such a reference would dangle.
`is_country_type` and `country_has_primary_culture` are both confirmed country-scope triggers in
`docs/triggers.log`.

Loc lives in `localization/english/countries_<region>_l_english.yml`, one file per script file, with
two keys per tag: the bare tag (display name) and `<TAG>_ADJ` (adjective).
