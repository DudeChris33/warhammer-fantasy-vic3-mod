# Scripting Rules (`common/`, `events/`)

Covers Clausewitz script: game database definitions in `common/` and event files in `events/`.

## Organization

- `common/` has one subfolder per database (`buildings/`, `cultures/`, `decisions/`, `laws/`, `technology/technologies/`, `scripted_effects/`, `scripted_triggers/`, `scripted_values/`, `history/...`, etc.). Put new entries in the matching existing subfolder — don't create a new top-level `common/` subfolder unless the database genuinely doesn't have one yet.
- `events/` holds event files as flat `.txt` files (no subfolders currently). Every event file must declare a unique `namespace = <name>` at the top, and every event id must be `namespace.NNNN`.
- Reusable script logic (a check or calculation used in more than one place) belongs in `common/scripted_effects/`, `common/scripted_triggers/`, or `common/scripted_values/` rather than being duplicated inline.

## `.metadata/metadata.json` `replace_paths`

`replace_paths` can only name folders under `common/`, `events/`, or `map_data/` — those
are the three trees the engine will blank per the loader's own rules; nothing else is a
valid entry.

A folder goes in `replace_paths` once this mod blanks and/or replaces **every** vanilla
file that folder ships — whether by authoring full replacement content for each file
(same filename, new body) or by leaving some deliberately empty. Once it's listed, the
engine doesn't load any of vanilla's files for that folder at all, so any per-file
"blank" stub that existed only to suppress a vanilla file becomes redundant — remove
those stubs when the folder is added. A folder that only replaces *some* of vanilla's
files for a database (leaving the rest to merge in normally) does not qualify — see the
`character_roles` example in `CLAUDE.md`.

Every folder listed in `replace_paths` must be tracked by git even when this mod hasn't
authored any content for it yet — git doesn't track empty directories, so give it a
`.gitkeep`. A folder that already carries real authored files doesn't need one; add
`.gitkeep` only where nothing else keeps the folder present.

## Patterns

- Validate every effect/trigger/modifier against `docs/effects.log`, `docs/triggers.log`, or `docs/modifiers.log` before use — these logs list the exact scope requirements.
- Validate every `event_target:` scope link against `docs/event_targets.log` (Input Scopes / Output Scopes columns).
- Validate every `on_action` hook against `docs/on_actions.log`, including its `Expected Scope`.
- Custom localization functions used in loc strings must be defined per `docs/custom_localization.log` before being referenced.

## Naming

- The first established convention is the culture foundation (#3405): zero-padded `NN_<topic>.txt` filenames within a database folder, ordered by loading/reading precedence (e.g. `common/discrimination_trait_groups/00_heritage_groups.txt`, `01_language_groups.txt`, `02_religious_heritage_groups.txt`; `common/religions/00_religions.txt`). When a folder has no such convention yet, pick a clear, descriptive snake_case filename (with or without a numeric prefix, e.g. `buildings_empire.txt`) and stay consistent with whatever is chosen going forward. `common/country_definitions/` and `common/country_formation/` follow that `NN_<region>.txt` shape, one file per Old World region — see their own schema section below.
- `common/cultures/` instead groups by RACE/CULTURE-GROUP, not by region: a plain descriptive snake_case filename per group (`norscan_humans.txt`, `imperial_humans.txt`, `dwarven.txt`, `greenskin.txt`, `vampire.txt`, `chaos_dwarf.txt`, `nehekharan_araby.txt`, etc.), with every culture belonging to that race/group defined inside it regardless of which region's states its population actually lives in (Chris, 2026-09-03; supersedes this folder's original `NN_<region>.txt` layout from board item #3405). A culture id is global and referenced by other files (e.g. `common/country_definitions/`) purely by id, so this reshuffle never touches those ids — only which file defines them.

## `common/cultures/` entry schema (epic #3404, #3406-#3409)

Nothing in `docs/*.log` documents the `common/cultures` database — this schema was confirmed against a vanilla reference install/repo via real in-game `error.log` testing, not guessed. Every culture entry needs:

- `color = rgb{ R G B }` (0-255 integers; `hsv{ h s v }` is the other valid form) — cosmetic only.
- `religion = <id>` — a religion id from `common/religions/`.
- `heritage = <id>` and `language = <id>` — **separate top-level fields**, each a single discrimination-trait id from `common/discrimination_traits/`. They are NOT wrapped in a `traits = { }` block — that shape was tried and is rejected outright by the parser.
- `traditions = { }` — required; an empty block is currently valid and is what this mod uses.
- `obsessions = { }` — goods ids; empty until this mod authors `common/goods/`.
- Name lists (`male_common_first_names`, `female_common_first_names`, `noble_last_names`, `common_last_names`), `graphics` and `ethnicities` using vanilla portrait/graphics ids (custom art is out of scope for epic #3404).

Every culture additionally requires, elsewhere:

- Three modifier-type registrations in `common/modifier_type_definitions/`: `country_<culture>_cultural_acceptance_add`, `country_fervor_target_<culture>_add`, `state_<culture>_standard_of_living_add` — each `{decimals=1 color=good game_data={ai_value=0}}` — appended to `culture_cultural_acceptance_modifier_types.txt`, `culture_fervor_target_modifier_types.txt` and `culture_standard_of_living_modifier_types.txt` respectively.
- Six static-modifier blocks (a `_positive`/`_negative` pair for each of the three concepts above) appended to the matching `common/static_modifiers/culture_*_modifiers.txt` file. Victoria 3 requires both variants for every culture id or it's an in-game error. Both use magnitude `1`, differing only by icon (`modifier_flag_positive.dds` / `modifier_flag_negative.dds`) — this is genuine vanilla behavior, confirmed against the vanilla reference, not a mistake to "fix".

These three modifier-type files and three static-modifier files are append-only — every later culture-authoring item adds its own entries to the existing files rather than creating new ones per culture.

## `common/religions/` standard-of-living + icon requirements (board #3541)

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

## `common/country_definitions/` + `common/country_formation/` entry schema (epic #3414, #3416)

Neither database is documented in `docs/*.log`; these shapes were confirmed against the vanilla
install during scoping. Neither folder is listed in `.metadata/metadata.json`'s `replace_paths`, so
vanilla's own tags still load and this mod's files only *add* to them.

Files follow the same `NN_<region>.txt` shape as `common/cultures/` — one file per Old World region,
named for the region it covers (`02_empire.txt`), with formables split into a sibling
`common/country_formation/NN_<region>_formables.txt`. The tag roster itself is frozen in
`planning/tag_registry.md` (epic #3414); check a code there before authoring it.

**A tag's file is chosen by geography, not by its culture (Chris, 2026-09-03).** A tag lives in the
`NN_<region>.txt` for the region it's physically located in, even when its culture is defined in a
different (and, since `common/cultures/` now groups by race rather than region, differently-named)
`common/cultures/` file — that's a legal cross-file reference, since culture ids are global. Example:
`MOR` (Massif Orcal, a Greenskin holdout in the Bretonnian heartland) and `SKZ` (Skullsmasherz, the
Grey Mountains on Bretonnia's southern flank) are both defined in `03_brettonia.txt` and use
`orc`/`goblin` culture ids from `common/cultures/greenskin.txt`, because both sit geographically
inside/against Bretonnia even though their population isn't bretonnian. A tag near a region border
needs a real judgment call on which side it reads as — `SKZ` was first drafted in `06_badlands.txt`
on the assumption a border mountain range defaults to the neighboring region's own tag file, then
moved once Chris confirmed it reads as Bretonnian geography instead (2026-09-03).

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
- **`capital` is deliberately omitted** on every tag this mod ships (established by board item
  #3416). No land `map_data/state_regions/` exist yet — only the sea zones emitted by
  `tools/generate_sea_regions.py` — so any `capital = STATE_*` would dangle. Record the intended
  capital as a `# capital: <Name> — TODO once land state-regions exist` comment and add the real
  field once land states are authored.

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
major-formation key until `common/diplomatic_plays` and `common/geographic_regions` are authored —
both are currently blanked via `replace_paths` and hold no entries, so a reference would dangle.
`is_country_type` and `country_has_primary_culture` are both confirmed country-scope triggers in
`docs/triggers.log`.

Loc lives in `localization/english/countries_<region>_l_english.yml`, one file per script file, with
two keys per tag: the bare tag (display name) and `<TAG>_ADJ` (adjective).

## Compatibility stubs and partial ports (#3447, widened #3537)

Applies to `common/scripted_triggers/`, `common/scripted_effects/` and `common/on_actions/` alike.

Two kinds of caller keep calling script this mod declined to restore. Either the calling file
belongs to a folder that is *not* in `replace_paths` (e.g. `common/battle_conditions/`, and the
`gfx/` building/train/ship graphics data), so vanilla's own copy still loads and still calls it; or
the calling file was itself restored into this mod by epic #3292 and its body kept a call that the
restoration pass did not bring across (`is_princely_state`, called from this mod's own
`common/ai_strategies/` files). Both fail the same way and take the same remedy; note which one a
new stub belongs to, since the second is self-inflicted.

Every restoration falls into one of three categories, and the comment above the entry must say
which:

- **Clean port** — the vanilla body depends only on engine-side keys or on content this mod
  actually ships, so restore it verbatim. Record the vanilla file and line.
- **Partial port** — most of the vanilla body ports, but named branches must be dropped. The
  comment must name *exactly* which branches were dropped, why, and what that prunes in play. A
  partial port whose comment only says "adapted" is not acceptable. If dropping the offending
  calls empties an `if` branch outright, drop the branch too rather than leaving an effect-less
  `if`.
- **Inert stub** — an empty body (`{ }` for a scripted effect, `effect = {}` for an on_action,
  `always = no` / `always = yes` for a trigger; all confirmed valid, and vanilla itself ships an
  empty-bodied scripted effect in `00_starting_inventions.txt`). Keep trigger stubs to a constant
  so they stay deterministic, and pick the value matching vanilla's own fallback semantics — a
  trigger that is vanilla's `NOR`-over-everything catch-all (e.g.
  `gfx_has_no_culture_trains_trigger`) stubs to `yes`, not `no`.

### Port-vs-stub decision rule (load-error taxonomy, confirmed #3537)

What forces a drop is whether the reference is a *hard load error* or merely inert:

| Reference to a missing object | Consequence |
|---|---|
| `has_modifier` / `add_modifier` / `remove_modifier` on an undefined named modifier | **hard load error** — must be dropped or the modifier restored |
| `has_journal_entry` on a missing journal-entry type | **hard load error** — must be dropped |
| `add_journal_entry` on a missing journal-entry type | silently inert — drop for hygiene, but it is not what forces a partial port |

So a body that only *adds* a missing journal entry can be ported and trimmed at leisure, while one
that *checks* a missing modifier or journal entry cannot be ported at all until the object exists.
Prefer restoring the missing object where it is generic (board #3539 restored the nine regency
modifiers, which turned `remove_regency_modifier` from a planned stub into a clean port).

Every stub must record, in a comment above it, **whether it is a true no-op or silently prunes
dependent content** — do not present all stubs as clean equivalences. Most graphics-selection
triggers are genuine no-ops: a false result just falls through to the default visual variant.
`is_in_guerilla_war` in `01_legacy_compat_triggers.txt` is the counter-example and the model for
the disclosure: stubbing it false permanently disables the ~6 vanilla battle-condition variants
gated on it evaluating `= yes`, which is the right call today but is a disclosed content gap with a
follow-up owed. `is_princely_state` (#3537) is the same shape on the effects/AI side: four
`common/ai_strategies/` branches prune when it returns no.

Compatibility triggers live either in `01_legacy_compat_triggers.txt` (cross-cutting one-offs) or in
a file named after the vanilla file they stand in for (`00_gfx_buildings_graphics_triggers.txt`).
Restored scripted effects follow the second shape only — one file per vanilla file, under vanilla's
own filename (`00_victoria_ip4_scripted_effects.txt`, `00_victoria_ip3_scripted_effects.txt`,
`00_victoria_ep2_scripted_effects.txt`, #3537), carrying just the entries that file's live call
sites still need. Restored on_actions go into the existing `common/on_actions/00_code_on_actions.txt`
beside their vanilla neighbours, keeping vanilla's `# Root = …` / `# scope:… =` header comments.
Before adding any of them, grep `common/` for the id — a duplicate definition is a game-log error.

## Forbidden

- No non-deterministic effects (see [core.md](core.md) Determinism).
- No effect/trigger/modifier/event target not confirmed in `docs/*.log`.
- No hardcoded display text — route all user-facing strings through localization keys.
