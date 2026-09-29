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

- `common/cultures/` instead groups by RACE/CULTURE-GROUP, not by region: a plain descriptive snake_case filename per group (`norscan_humans.txt`, `imperial_humans.txt`, `dwarven.txt`, `greenskin.txt`, `vampire.txt`, `chaos_dwarf.txt`, `nehekharan_araby.txt`, etc.), with every culture belonging to that race/group defined inside it regardless of which region's states its population actually lives in (Chris, 2026-09-03; supersedes this folder's original `NN_<region>.txt` layout from board item #3405). A culture id is global and referenced by other files (e.g. `common/country_definitions/`) purely by id, so this reshuffle never touches those ids — only which file defines them.

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

Files follow the same `NN_<region>.txt` shape as `common/cultures/` — one file per Old World region,
named for the region it covers (`02_empire.txt`), with formables split into a sibling
`common/country_formation/NN_<region>_formables.txt`. The tag roster itself is frozen in
`planning/tag_registry.md`; check a code there before authoring it.

**A tag's file is chosen by geography, not by its culture.** A tag lives in the
`NN_<region>.txt` for the region it's physically located in, even when its culture is defined in a
different (and, since `common/cultures/` now groups by race rather than region, differently-named)
`common/cultures/` file — that's a legal cross-file reference, since culture ids are global. Example:
`MOR` (Massif Orcal, a Greenskin holdout in the Bretonnian heartland) and `SKZ` (Skullsmasherz, the
Grey Mountains on Bretonnia's southern flank) are both defined in `03_brettonia.txt` and use
`orc`/`goblin` culture ids from `common/cultures/greenskin.txt`, because both sit geographically
inside/against Bretonnia even though their population isn't bretonnian. A tag near a region border
needs a real judgment call on which side it reads as.

A country definition entry:

```
TAG = {
	color = { R G B }
	country_type = recognized | unrecognized | colonial | company | decentralized
	tier = city_state | principality | grand_principality | kingdom | hegemony | empire
	cultures = { culture_id_1 culture_id_2 ... }
}
```

- `color` uses the **brace** form `{ R G B }` (0-255 integers), not `common/cultures/`' `rgb{ }`.
  Convention: reuse the polity's already-shipped culture color so tag and culture read as one thing;
  a formable that has no culture of its own takes a distinct shade of its heartland's color.
- `cultures` ids must exist somewhere under `common/cultures/` — in whichever race/group file that culture is defined (see the Naming section above; no longer a matching-region file).
- **`capital` is deliberately omitted** on every tag this mod ships until it has a real
  `STATE_*` to point at (land state-regions are emitted — see [testing.md](testing.md) —
  but not every tag has had its capital assignment revisited). Record the intended
  capital as a `# capital: <Name> — TODO` comment where it's still missing.

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
