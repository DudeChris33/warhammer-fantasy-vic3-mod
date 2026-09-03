# Scripting Rules (`common/`, `events/`)

Covers Clausewitz script: game database definitions in `common/` and event files in `events/`.

## Organization

- `common/` has one subfolder per database (`buildings/`, `cultures/`, `decisions/`, `laws/`, `technology/technologies/`, `scripted_effects/`, `scripted_triggers/`, `scripted_values/`, `history/...`, etc.). Put new entries in the matching existing subfolder — don't create a new top-level `common/` subfolder unless the database genuinely doesn't have one yet.
- `events/` holds event files as flat `.txt` files (no subfolders currently). Every event file must declare a unique `namespace = <name>` at the top, and every event id must be `namespace.NNNN`.
- Reusable script logic (a check or calculation used in more than one place) belongs in `common/scripted_effects/`, `common/scripted_triggers/`, or `common/scripted_values/` rather than being duplicated inline.

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
`MOR` (Massif Orcal, a Greenskin holdout in the Bretonnian heartland) is defined in `03_brettonia.txt`
and uses `orc`/`goblin` culture ids from `common/cultures/greenskin.txt`, because it's geographically
part of Bretonnia even though its population isn't bretonnian. Contrast `SKZ` (Grey Mountains, on
Bretonnia's *border*), which stays in `06_badlands.txt` because that mountain range is Badlands
territory, not Bretonnian.

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

## `common/scripted_triggers/` compatibility stubs (#3447)

Vanilla folders that are *not* in `replace_paths` (e.g. `common/battle_conditions/`, and the
`gfx/` building/train/ship graphics data) still load and still call scripted triggers whose own
definitions this mod declined to restore. When a dropped vanilla trigger's real body transitively
depends on `replace_paths`-blanked data — `is_in_geographic_region = geographic_region_*`,
`cu:<real-world culture>` ids, `heritage_group_*` discrimination trait groups, journal entries —
**restore it as a stub under its original name** rather than porting the vanilla body, which would
only dangle. Keep the stub bodies to `always = no` / `always = yes` (both confirmed in
`docs/triggers.log`) so they stay deterministic. Where the vanilla body ports cleanly because it
depends only on engine-side keys rather than content ids (e.g. `has_culture_graphics = european`),
restore it verbatim instead of stubbing.

Every stub must record, in a comment above it, **whether it is a true no-op or silently prunes
dependent content** — do not present all stubs as clean equivalences. Most graphics-selection
triggers are genuine no-ops: a false result just falls through to the default visual variant.
`is_in_guerilla_war` in `01_legacy_compat_triggers.txt` is the counter-example and the model for
the disclosure: stubbing it false permanently disables the ~6 vanilla battle-condition variants
gated on it evaluating `= yes`, which is the right call today but is a disclosed content gap with a
follow-up owed. Pick the stub value that matches vanilla's own fallback semantics — a trigger that
is vanilla's `NOR`-over-everything catch-all (e.g. `gfx_has_no_culture_trains_trigger`) stubs to
`yes`, not `no`.

Compatibility stubs live either in `01_legacy_compat_triggers.txt` (cross-cutting one-offs) or in a
file named after the vanilla file they stand in for (`00_gfx_buildings_graphics_triggers.txt`).
Before adding one, grep `common/` for the trigger id — a duplicate definition is a game-log error.

## Forbidden

- No non-deterministic effects (see [core.md](core.md) Determinism).
- No effect/trigger/modifier/event target not confirmed in `docs/*.log`.
- No hardcoded display text — route all user-facing strings through localization keys.
