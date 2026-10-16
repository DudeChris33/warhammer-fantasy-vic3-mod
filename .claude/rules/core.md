# Core Rules

Always loaded, like `CLAUDE.md`. Everything here is non-negotiable; area detail lives in the path-scoped guides (routing table in `CLAUDE.md`).

## Trust order

On conflict, in this order — then fix the losing side to match:

1. `docs/*.log` — what the game engine actually accepts.
2. The vanilla install — what shipped content actually does.
3. `.claude/rules/` — this repo's conventions.
4. Existing script patterns already committed in `common/`/`events/`.

## Vanilla install

The unmodded Victoria 3 install is on disk and is the authority on the shape of the data this mod replaces (file formats, naming, what a "normal" entry looks like). **Read the vanilla file before authoring its mod counterpart.** `docs/*.log` says what syntax is legal; vanilla says what real content looks like.

```
C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game
```

Its layout mirrors this mod's (`common/`, `events/`, `gui/`, `interface/`, `gfx/`, `localization/english/`, `map_data/`, …). Useful starting points: `game/map_data/` and `game/map_data/state_regions/` (map and state formats — see [testing.md](testing.md)), `game/common/<db>/` (canonical example set for any database — see [scripting.md](scripting.md)), `game/localization/english/` (vanilla key names — see [localization.md](localization.md)).

A private, read-only GitHub mirror of vanilla's `common/`, `events/`, `localization/` and `map_data/` exists for machines where the Steam install isn't reachable; ask the user for its URL when needed. It is not part of this repo and nothing from it is committed here. Copy what's needed into this mod folder and modify the copy.

External references are fine for background — the Vic3 modding wiki (`https://vic3.paradoxwikis.com/Modding`) and Paradox dev diaries (design intent behind a mechanic). `docs/*.log` or the live vanilla install wins on exact syntax and current behaviour; older dev diaries predate patches, so flag one that may be outdated.

## Guardrails

Each is one line here; the detail is in the owning guide. A breach is costly or hard to reverse, so these are never moved behind a guide.

- **The repo is not the mod folder.** The repo lives at `Documents/Modding/Vic3/warhammer-fantasy`; `Documents/Paradox Interactive/Victoria 3/mod/warhammer-fantasy` is a deploy target (only `.metadata`, `common`, `events`, `gfx`, `gui`, `interface`, `localization`, `map_data`, `thumbnail.png`) so `sources/`, `mapgen/`, `.git`, `planning/`, `.claude/` stay out of the Workshop upload. Edit in the repo, never in the deployed copy; `deploy.ps1` mirrors repo → mod folder and refuses to overwrite files the game or map editor wrote there until you run `deploy.ps1 -Pull`. A new shipping folder must be added to `$shipDirs` in `deploy.ps1`.
- **Never write to the vanilla install** — read-only reference; copy and edit the copy. Note the in-game map editor itself writes into the base-game folder (`mapgen/MAP_RUNBOOK.md`), so follow its steps and `git diff` after every editor save.
- **Never hand-edit `docs/*.log`** — the game generates them.
- **Confirm before use**: every effect, trigger, modifier, event target, on_action and custom-loc key must be confirmed in the matching `docs/*.log`; never invent content or leave a `{{...}}` placeholder. Detail: [scripting.md](scripting.md).
- **Determinism**: the mod is multiplayer-synchronized (`.metadata/metadata.json`). No non-seeded randomness, nothing reading time/filesystem/OS state, no debug-only effects. Use the game's seeded `random_list`/`random`. Script cannot read or write outside this mod folder, and nothing should assume it can.
- **Never hand-edit a generated map file**; regenerate through the file's owner — a `mapgen/` script or, for `map_data/heightmap.heightmap`, the in-game map editor. The ownership table is in [testing.md](testing.md). Generated files: `map_data/` except `default.map`'s hand-authored keys (`sea_starts` and `lakes` are generated) and the authored readme `map_data/state_regions/state_regions.md`; everything tracked under `mapgen/derived/`; `mapgen/registration/*.json`; `common/strategic_regions/*`; `common/history/states/*`; `common/history/pops/*`; `common/history/population/*`; `common/history/countries/*`; `common/history/buildings/*`; `common/strait_definitions/canals.txt`; `localization/**/map/*` (including `localization/replace/english/map/states_l_english.yml`); `gfx/map/map_object_data/generated_map_object_locators_*`; `gfx/map/textures/{flatmap,land_mask}.dds`; `gfx/map/dynamic_masks/exclusion_mask.dds`. Hand-authored inputs meant to be edited deliberately are listed in testing.md.
- **Sources and state borders are Chris's to change** — imagery in `sources/`, the magenta state-border network, the `province_merges` and `state_merges` layers of `full.ora`. Province cuts inside a state may move via the generator; state borders stay frozen. If a result is capped by the source, say so and ask for imagery — never browse for or substitute your own. `--update-manifest` follows a user source change, never precedes one.
- **The rendered map is the gate**: render it, send the PNG, state what you see, and wait for Chris's verdict before committing map bitmaps or calling a map done. A green offline check is a precondition, never a stopping point.
- **Git**: no `git add -A` (stage specific files), no `git push` unless asked, no personal absolute paths in committed script, loc, gui or gfx files.
- **No drive-by refactors**: touch only what the task needs; no new top-level folders without checking.

## Build + test gate

There is no compiler and no automated test suite for Clausewitz script — validation is loading the mod in Victoria 3.

1. If the change touches `map_data/`, `common/strategic_regions/`, map loc or source-registration data, run the offline map gate first (see [testing.md](testing.md)).
2. Run `.\deploy.ps1` (repo root) to mirror the shipping folders into the game's mod folder, then launch Victoria 3 with this mod enabled. Get into a game session if the change touches `events/` or `history/` — main-menu parsing alone won't catch every error.
3. Check `logs/error.log` (`Documents/Paradox Interactive/Victoria 3/logs/error.log`; the deployed mod is `.../Victoria 3/mod/warhammer-fantasy/`) after every change touching `common/`, `events/`, `gui/`, `localization/` or `map_data/`.
4. Any new line referencing a file of this mod is a failure. Fix the **script**, never the log; never edit `error.log` or any game-owned file to make an error disappear.
5. Never claim a change is "tested" without having loaded the mod in-game and checked the log.

**Regression rule.** When fixing a bug confirmed via `error.log` or in-game behaviour, first reproduce it (capture the exact error line or observed behaviour) before changing script, so the fix can be verified against the same reproduction.

Docs-only changes touch no game-read file and have no in-game gate.

## Localization and presentation

Domain logic lives in `common/` and `events/`; presentation text in `localization/`; UI layout in `gui/` + `interface/`. Never hardcode display text in script — every new user-facing key gets an entry in `localization/english/` (overrides of vanilla text go in `localization/replace/english/`, never by editing base-game files). Detail: [localization.md](localization.md).

## Philosophy

- Read before editing — the relevant `docs/*.log` entry, the vanilla counterpart, and sibling files in the target folder first.
- Minimal changes — a bug fix touches the smallest set of files that fixes it.
- Confirm with the user when a design decision isn't pinned down by the item's `## Approach` (legacy `## Plan`).
- Judgment: when a technical call is Claude's to make, make it with a rationale rather than deferring; treat inherited tooling and scaffolding as suspect and audit it rather than preserving it blindly.

## Delivery checklist

- [ ] Every effect/trigger/modifier/event target used is confirmed present in the matching `docs/*.log`
- [ ] New user-facing text has a `localization/english/` (or `localization/replace/english/`) entry
- [ ] No non-deterministic script added
- [ ] Mod loaded in-game and `logs/error.log` checked clean for this mod's files
- [ ] Only specific, relevant files staged — no `git add -A`
- [ ] Board item landed at `review`/`done` with its activity trail updated (commits, verification) — via the maestro MCP, not a local file move
