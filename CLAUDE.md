# Warhammer Fantasy Overhaul

A total-conversion mod for Victoria 3 that reskins the base game into the Warhammer Fantasy setting, using Clausewitz script (`.txt`), the PDX GUI format (`.gui`) and localization YAML (`.yml`). The supported game version is `supported_game_version` in `.metadata/metadata.json`. The mod is multiplayer-synchronized (`multiplayer_synchronized` in the same file), so scripted content must stay deterministic across clients.

**Scope.** The Old World, Ulthuan and the High Elf colonies are in scope (Ulthuan added by Chris on 2026-10-11, the colonies on 2026-10-12: islands off Lustria and the Southlands, the Gates of Calith and the Lost Isles of Elithis). All of it is drawn as states; the Ulthuan and colony states are still unnamed and unowned. The colonies and Ulthuan's islets are listed in `mapgen/config/in_scope_additions.json`, because the generator otherwise finds in-scope land by the density of state borders. **Timeline.** The game runs 2502.1.1 to 2602.1.1 IC (`common/defines/00_wh_defines.txt`). The Storm of Chaos and the End Times are out of scope: no scripted content for either (Chris, 2026-10-12); a possible future submod. All oceans are modelled globally; land outside the drawn regions is emitted as placeholder regions (seeded from `mapgen/config/out_of_scope_continents.json`; `placeholder_regions` in `mapgen/derived/land_regions_index.json` counts them), not as playable content.

## How guidance is organised

Two files are always loaded: this one and [core.md](.claude/rules/core.md) (trust order, vanilla-install rules, **all guardrails**, the build/test gate). Everything else is a **guide** in `.claude/rules/` with a `paths:` frontmatter, loaded when a session reads a matching file with the Read tool.

Auto-loading and the routing table below are a starting point, not a limit: read any other guide whenever you think it would help, and read a neighbour when your work touches its area (a culture needs the localization guide; a map change needs localization for generated names). Observed 2026-09-29 (#5850 canary probes): a Read of a matching file loads its guides in the main session and in sub-agents; Bash `cat`/`head` and a Write with no prior Read load nothing — if you reach files that way, open the guide yourself.

| Working on | Read |
|---|---|
| map, mapgen, sources, strategic regions, straits, map loc | [testing.md](.claude/rules/testing.md) (+ [localization.md](.claude/rules/localization.md)) |
| cultures, religions, traits, countries, formables, tag registry | [peoples.md](.claude/rules/peoples.md) + [localization.md](.claude/rules/localization.md) (+ [heraldry.md](.claude/rules/heraldry.md) for new tags) |
| coats of arms, flags, colour palette | [heraldry.md](.claude/rules/heraldry.md) (+ [peoples.md](.claude/rules/peoples.md)) |
| other `common/`, `events/`, vanilla restoration, neutralizing real-world refs anywhere | [scripting.md](.claude/rules/scripting.md) |
| localization | [localization.md](.claude/rules/localization.md) |
| `gfx/`, `interface/`, `gui/` | [interface.md](.claude/rules/interface.md) (+ [scripting.md](.claude/rules/scripting.md); [testing.md](.claude/rules/testing.md) for `gfx/map/`) |
| docs, rules, memory, agents, skills | [docs.md](.claude/rules/docs.md) |

## Layout

| Path | Contents |
|---|---|
| `common/` | Script "database" definitions, one subfolder per game database. Which vanilla folders are blanked is governed by `replace_paths` in `.metadata/metadata.json` — see [scripting.md](.claude/rules/scripting.md) before assuming an empty folder is a gap. |
| `events/` | Event script files (`.txt`) |
| `interface/` | `.gfx` sprite/icon declarations (currently only `.gitkeep`) |
| `gfx/` | Art assets and script-like gfx overrides — see [interface.md](.claude/rules/interface.md) |
| `localization/english/`, `localization/replace/english/` | New loc, and loc that overrides vanilla text |
| `map_data/` | Map and state regions — generated; see [testing.md](.claude/rules/testing.md) |
| `mapgen/` | Offline map generator + validator toolchain (Python); named `mapgen`, not `tools`, because vanilla reserves a `tools` folder — see [testing.md](.claude/rules/testing.md) and `mapgen/MAP_RUNBOOK.md` |
| `sources/` | Git-ignored, local-only reference imagery (provenance in `mapgen/SOURCES.md`) |
| `docs/` | Read-only game-generated script reference (`docs/*.log`) |
| `planning/` | Review-panel targets, `tag_registry.md`, `planning/economics/` (economics design notes) and the maestro skills' gitignored `.cache/` scratch. Not the tracker — the maestro board is. |
| `.metadata/metadata.json` | Mod descriptor |
| `deploy.ps1` | Mirrors the shipping folders into `Documents/Paradox Interactive/Victoria 3/mod/warhammer-fantasy` (the repo itself lives outside the game's mod folder — see [core.md](.claude/rules/core.md)); `-Pull` copies editor/game output back, `-Force` discards it |

## How to work here

- **Skills** in `.claude/skills/`, invoked with `/<name>`. Work tracking runs on the **maestro board** (via the maestro MCP), not local files; the board item's markdown workspec is the work record. `maestro-*` and `sites-verify` are Maestro pack skills — don't edit them locally. `review-panel` and `project-memory` belong to this repo.
  - `/maestro-task <description>` — explore, clarify, file work item(s) (stage=inbox)
  - `/maestro-scope <item-ids>` — scope item(s), append a `## Approach`, push back (stage=planned)
  - `/maestro-build <item-ids>` — claim, execute the plan with full build discipline, land at review/done
  - `/maestro-auto <item-ids>` — scope + build in one mostly-autonomous run, one approval gate
  - `/maestro-run <plan-id>` — execute an approved Plan in waves with fresh sub-agents
  - `/maestro-review` — commit-bound verdict for a teammate's ask, or the closing pass of your own build
  - `/maestro-vibe <description>` — small change with build discipline, no board ceremony
  - `/maestro-release-note` — draft the next release note from the actual diffs
  - `/sites-verify <url>` — look at a deployed maestro site (real pixels)
  - `/review-panel <target>` — convene the five-expert review panel on a plan, a diff, or a rendered artifact
  - `/project-memory` — show memory state
- `.claude/maestro.json` holds `workspace`, `board` and `project`; the maestro skills prompt to create it if missing.
- **Sub-agents** in `.claude/agents/`: `docs-updater` (update docs from a diff) and `security-review` (MP-desync and content-integrity review) are spawned by the build skills; `loremaster` (canon), `cartographer` (map craft), `geographer` (physical plausibility), `vic3-modding-expert` (engine correctness) and `game-designer` (play and scope) are the read-only `/review-panel` reviewers. Each starts from the guides named in its brief and may read others.

### Workflow chain

```
Bug or feature idea
      │
      ▼
/maestro-task   ── files ──►  board item, stage=inbox (the workspec)
      │
      ▼
/maestro-scope  ── appends ─►  ## Approach on the workspec (legacy name: ## Plan), stage=planned
      │
      ▼
/maestro-build  ── executes ─►  commits + activity trail, stage=review/done
```

`/maestro-scope` must never be skipped — it is where file-level decisions get pinned down. `/maestro-auto` runs scope + build as one approval-once run; `/maestro-vibe` is the lightweight path for a change too small to track. `/review-panel` is optional and can run at any point; its ruling is advisory and on anything visual the user is the final gate.

### Autonomy model

The generation/iteration loop is where to run long and unattended; sourcing and the visual verdict are where to stop and hand back. The failures on this project have come from stopping too early inside the loop (at an offline-green checkpoint) and from trying to own the two ends that are the user's.

- **Run autonomously** inside the tooling loop: edit a generator, LUT or hand-authored input, re-derive, run the offline gate, **render the map and send the PNG**, read it, diagnose, go again. Iterate to convergence; chain several regen→render passes in one turn. The concrete commands are in [testing.md](.claude/rules/testing.md).
- **Always stop and hand back** for: sourcing (choosing, adding, swapping or marking up imagery in `sources/` is Chris's — better source beats more tuning; if a result is capped by the source, say so and ask); the visual verdict (render, send, say what you see and what you'd change, then wait for accept/reject); and irreversible or scope-widening steps (`git commit` of map bitmaps only after the user accepted the visual; `git push`; new top-level folders).
- A loop-shaped request ("get the coastline right") means: iterate to convergence, render, return the PNG plus a recommendation — not a single edit-then-ask cycle.

## Memory layers

- **Claude Code memory** (`~/.claude/projects/.../memory/`) — per-device, per the memory-system instructions in the system prompt.
- **Maestro knowledge** — durable and visible to every session and agent via the MCP. Whenever you save a Claude Code memory, also call the maestro MCP's `add_knowledge` (project id in `.claude/maestro.json`) with the same content. Map `type` to `kind`: `feedback` → `rule`, `project` → `decision` (or `pattern`/`reference`), `reference` → `reference`, `user` → `rule`. **Maestro knowledge can be stale** (entries are written once and rarely updated; some still describe `tools/`, old decisions or superseded workflows): treat a hit as a lead, not a fact, and verify it against the repo (`.claude/rules/`, the code, `git log`) or the current Claude Code memory before acting on it. When the two disagree, the repo wins; fix or supersede the stale entry. Chris works on a single machine today (2026-09-28); the mirror is how conventions survive a machine change and reach Maestro agents.
- Current work state lives on the maestro board, not in a repo scratchpad. Long-lived conventions belong in a guide under `.claude/rules/`.
