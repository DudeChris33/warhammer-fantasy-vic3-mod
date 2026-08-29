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

- The first established convention is the culture foundation (#3405): zero-padded `NN_<topic>.txt` filenames within a database folder, ordered by loading/reading precedence (e.g. `common/discrimination_trait_groups/00_heritage_groups.txt`, `01_language_groups.txt`, `02_religious_heritage_groups.txt`; `common/religions/00_religions.txt`). When a folder has no such convention yet, pick a clear, descriptive snake_case filename (with or without a numeric prefix, e.g. `buildings_empire.txt`) and stay consistent with whatever is chosen going forward.

## Forbidden

- No non-deterministic effects (see [core.md](core.md) Determinism).
- No effect/trigger/modifier/event target not confirmed in `docs/*.log`.
- No hardcoded display text — route all user-facing strings through localization keys.
