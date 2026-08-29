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

- The first established convention is the culture foundation (#3405): zero-padded `NN_<topic>.txt` filenames within a database folder, ordered by loading/reading precedence (e.g. `common/discrimination_trait_groups/00_heritage_groups.txt`, `01_language_groups.txt`, `02_religious_heritage_groups.txt`; `common/religions/00_religions.txt`). When a folder has no such convention yet, pick a clear, descriptive snake_case filename (with or without a numeric prefix, e.g. `buildings_empire.txt`) and stay consistent with whatever is chosen going forward. `common/cultures/` follows the same `NN_<region>.txt` shape, one file per Old World region (`00_norsca.txt`, `01_kislev.txt`, `02_empire.txt`, etc.), with every culture belonging to that region defined inside it.

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

## Forbidden

- No non-deterministic effects (see [core.md](core.md) Determinism).
- No effect/trigger/modifier/event target not confirmed in `docs/*.log`.
- No hardcoded display text — route all user-facing strings through localization keys.
