---
name: map-regen
description: Regenerate the map after Chris re-exports full.ora - manifest, provinces through adjacencies, offline gate, state-level renders, deploy, error.log triage, commits
user-invocable: true
---

Full regen after a source change (`/map-regen`). Distilled from the 2026-10-15 run. Guardrails stay in `.claude/rules/core.md`; step detail in `.claude/rules/testing.md`. Scripts live next to this file; paths are repo-relative.

## Ground rules

- Run the loop autonomously; **stop for**: Chris's sources/paint, per-run exemptions, naming/design calls, and the visual verdict.
- `--update-manifest` only after Chris says he re-exported. Then `sources.py --verify` must pass. Missing or moved files (`WIP/` is excluded by design, `archive/` too): stop and ask; never copy or substitute imagery.
- **Alpha 0 is never paint.** Read layers only through `sources.read_source_rgba` / `worldgen.raster.read_rgb_png`. Ad-hoc analysis that opens the `.ora` with raw `convert("RGB")` shows ghost pixels (erased strokes keep RGB) and gives wrong diagnoses.
- Chris is often still in GIMP. A manifest that fails minutes after passing means a file is still being written: wait, re-check, don't chase.

## Steps

1. `python mapgen/worldgen/sources.py --update-manifest` (after his say-so), then `--verify`. Report the CHANGED lines.
2. `python .claude/skills/map-regen/regen_chain.py` (provinces -> adjacencies -> locators -> heatmap, then the offline gate). `--from <step>` resumes; `--from rivers` when coast/river/sea sources changed; `--list` shows steps. Run in the background, it takes 10-15 min (provinces ~6). It re-anchors drifted pop/building overrides itself (<= 40 px) and stops on anything else.
3. Fix the stop with the playbook below, resume with `--from`.
4. Offline gate green is a precondition only. **Render and send**: `render_states.py` (state-level, never the province partition) and, for adjacencies, `generate_adjacencies.py --review` (`scratchpad/adjacencies_preview.png`). Say what you see, wait for the verdict.
5. Commit only after Chris accepts the visual (below), then deploy and have him load the game; triage `error.log`.

## Stop playbook

| Stop | Cause | Action |
|---|---|---|
| `verify`: manifest mismatch / file missing | re-export, or Chris moved sources | update-manifest only after his say-so; moved/missing: ask. A layer that moved into `full.ora` needs `source_layers.json` repointed (`...full.ora#<layer>`). |
| provinces: hub 'X' resolves into island-override archipelago | a `province_merges` line overlaps the main landmass, fusing it | check visible (alpha > 0) red only; send the touch sites; Chris trims them. |
| provinces: `state_merges` ... join in-scope land to out-of-scope land | generator rule rejects lines Chris considers fine (generator fix is an open follow-up) | ask; **only if he says so for this run**, `regen_chain.py --skip-mixed-state-merges` (logs each dropped line, changes nothing in the repo). The exemption does not carry to the next run. |
| land_regions: economics worksheet "not a state ... row dead" / "re-anchor by hand" | states merged away or centroids moved | rows with no values (check!): delete dead rows, rewrite drifted anchors from the log's naming anchor. Rows with values: ask. `--rekey-economics` only fixes renamed keys. |
| ownership: `STATE_X: drawn state painted with the placeholder colour` | a new state has no paint | `render_state_ownership.py --adopt-new-states` (paints it unowned, touches only fully-placeholder states); say which. |
| pop weights: no entry for STATE_X | new state | `generate_pop_history.py --refresh-weights` (the chain already runs it). |
| building history: `X is not a state` / key rules naming a vanished state | a state name was dropped/changed | map each to current region (anchor -> worksheet row); **Chris decides** restore name / re-key / drop. Never guess. |
| building history: `N jobs exceed 40% of M pops` | merged state's auto farms fill the whole budget, owner (manor) jobs added later push it over | tag-level `set` in `profiles.json` (e.g. `workforce_share` 0.35) with a `justify` entry; state it in the report. |
| adjacencies `--sync` parked rows / new blank rows | lines redrawn | see Adjacencies. |
| adjacencies `--write`: type 'sea' joins land to land (or reverse) | a line's endpoints changed province | Chris retypes the row. |
| splines: `naval layer is stale for the current map` | state ids or ports changed, so the shipped harbours no longer match | after the deploy, Chris runs the desktop naval step (`mapgen/MAP_RUNBOOK.md`, "Route network"); move its output into the repo, then `--from splines`. |

## Adjacencies

- `--review` writes the numbered table + render. **Number = table 'number' column / the number on the render.** The `--sync` line "untyped rows (numbers as in the review table)" is the worksheet row index and is off whenever a drawn line was skipped. Never quote it.
- `prefill_adjacency_numbers.py` writes `#N` into the comment of blank rows (matched by endpoints) so Chris can match rows to the render without counting. It never touches typed rows. Re-run `--review` first after any `--sync`.
- `--sync` parks rows whose line vanished under `stale` (never deletes). Report parked typed rows: a typed canal whose line was redrawn as a plain crossing is Chris's call (he may want it as `sea`); a vanished canal line means the strait definition goes away on `--write`, which can be intentional.
- Untyped = missing strait/crossing definitions. They need type + comment from Chris; `--write` skips blank rows.
- Row typing is Chris's; ask, or propose a table (type + comment per row, with the render) and wait for his yes.

## Commit (after he accepts the visual)

Specific paths, no `git add -A`, no push, end with the `Co-Authored-By` line from the session reminder. `.claude/` is git-ignored: new skill files need `git add -f`. Three commits:

1. tooling/code (`mapgen/*.py`, `worldgen/`, `run_fixture.py`)
2. hand-authored inputs (`mapgen/config/**`, `SOURCES.md`, `state_ownership.png`)
3. generated output (`map_data/`, `common/{history,strategic_regions,strait_definitions}`, `gfx/map/map_object_data`, `localization/**/map`, `mapgen/derived/*` that changed)

`full.ora` is tracked (LFS): commit it only if Chris says so. Leave other sessions' untracked files alone.

## Deploy and in-game check

`.\deploy.ps1`. Its drift guard counts files that exist only in the repo (new files) as "drift" and refuses. Before `-Force`, prove there is no real drift: scan the mod folder for files missing from the repo or newer **and** different. Only then `.\deploy.ps1 -Force`. Verify a few deployed hashes. Chris loads the game; then read `Documents/Paradox Interactive/Victoria 3/logs/error.log`.

Triage by source tag (the log names no files; normalise tags/numbers and count):
- `travel_connection_definition`: the route network (`generate_spline_network.py`, #9555) cleared the "no connection node" lines (0 on 2026-10-29). Any `:393`/`:398` line, or a `route_graphics.cpp:734` "non-adjacent" line, is this regen's: the land layer is stale or `PAIR_RULE` no longer matches the engine. `:252` "none of the nodes are connected to another state region" on an island state is a harbour the editor's naval step gave no strip (#9784).
- `country_law_manager` Mercantilism, `concept_religious_trait` loc, `je_meiji_restoration_get_faction_sgui`, `culture_graphics_type`, variable lint: not map output; report, don't fix unprompted.
- Anything naming `map_data`, a state, province, adjacency, pop or building is this regen's: fix the script, never the log.
- The log cannot say whether a session started; ask Chris. Don't call the in-game gate passed without it.

## Reporting

Short. What changed, what is unverified, what is Chris's. Each decision as a one-line question with a recommendation.
