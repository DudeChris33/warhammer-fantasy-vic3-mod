# World Map — P4: Scaffold + Boot

> **Superseded by [world-map-source-driven.md](../requests/world-map-source-driven.md)** (2026-07-21) — re-phased into S0–S6; this phase's work is inherited (essentially verbatim) by S4. Kept for history.

| Field | Value |
|-------|-------|
| Type | request (child of [world-map.md](world-map.md)) |
| Status | planned |
| Date | 2026-07-20 |
| Priority | high |
| Phase | 4 of 6 — **the boot milestone** |
| Gate | Game **boots into a session** with the mod; **zero mod-file lines in `logs/error.log`**; editor round-trip; state/SR map modes spot-checked |
| Depends on | P3 (provinces + states + regions + loc skeletons) — build back-to-back with P3 |

Child build file of the world-map master plan. P4 lands `replace_paths`, the throwaway `zz` political scaffold, and the vanilla-filename overrides that make the game boot cleanly on the new map. This is the phase that turns the (deliberately unbootable) P3 repo into a running session.

## Description

Add the `replace_paths` that stop vanilla state/strategic/history/country data from loading, generate a minimal throwaway political scaffold so every land state has an owner and the game reaches a session, override the handful of vanilla files in *kept* directories that still reference dead vanilla `STATE_`/tag identifiers, and iterate the `error.log` cleanup loop to zero. The scaffold is explicitly disposable (`zz_placeholder_*`) — real nations/cultures/pops are out of scope.

---

## Plan

### Objective
Boot the mod into a live session on the new Known World map with a clean `error.log`, using the smallest throwaway political layer that satisfies the engine's invariants.

### Steps (ordered)
1. **`.metadata/metadata.json`** — add the pinned `replace_paths` list (master plan's Exether-derived 1.13 set): `map_data/state_regions`; `common/strategic_regions`; `common/geographic_regions`; `common/country_definitions`; `common/country_creation`; `common/country_formation`; **all** `common/history/*` subfolders + `common/history` itself; `common/decisions`; `common/journal_entries`; `common/achievements`; `common/ai_strategies`; `common/company_types`; `common/dynamic_country_map_colors`; `common/dynamic_country_names`; `common/flag_definitions`; `common/coat_of_arms/coat_of_arms`; `common/ship_name_definitions`; `common/scripted_tests`; `common/scripted_buttons`; `common/scripted_progress_bars`; `events` + all vanilla `events/*` subfolders. **Kept vanilla** (verified to hold no `STATE_`/tag refs): cultures, religions, interest_groups, governments, government_types, social_classes, discrimination traits/groups, dna_data, character_templates, customizable_localization, buildings/goods/PMs/technology/laws.
2. **`common/cultures/zz_placeholder.txt`** — one **additive** culture (`cultures` is a *kept* dir) referencing vanilla `religion`/`heritage`/`language` keys (verified vanilla culture format: `color`, `religion`, `heritage`, `language`, `traditions`, name lists) with small generic first/last-name lists. Vanilla cultures stay loaded alongside it.
3. **`common/country_definitions/zz_placeholder.txt`** — ~10 recognized tags `ZZA`–`ZZJ`, each `country_type = recognized`, a `tier`, `cultures = { zz_placeholder }`, and a `capital = STATE_<x>` in its continent chunk (continent-sized ownership → readable map modes, sane AI load).
4. **`tools/generate_scaffold.py`** → **`common/history/states/00_states.txt`**, **`common/history/pops/00_pops.txt`**, **`common/history/countries/00_countries.txt`** — generated to cover **every** land state, using verified effects only ([effects.log](../../docs/effects.log)):
   - `STATES = { s:STATE_X = { create_state = { country = c:ZZx owned_provinces = { ... } } add_homeland = cu:zz_placeholder } }` — `create_state` is `state_region` scope; assign each state to a tag by continent.
   - `create_pop` (state scope) — minimal pops per state so the economy layer initializes.
   - `common/history/countries/` — minimal per-tag setup with the required `activate_law` set (governance/economy law categories) so each country is law-valid.
5. **Vanilla-filename overrides in kept dirs** (Exether's exact mechanism; strip dead refs, keep generic setup — never edit vanilla files):
   - `common/on_actions/{00_code_on_actions,00_on_actions_election,00_on_actions_half_yearly,00_on_actions_monthly,00_on_actions_yearly,ip4_on_actions}.txt` — strip fired vanilla event ids + tag/state-specific effects, keep generic setup hooks.
   - `common/buildings/10_canals.txt` — remove the `STATE_PANAMA`/`STATE_SUEZ` canal entries (verified: they reference `s:STATE_PANAMA` / `owns_entire_state_region = STATE_PANAMA`, dead after `replace_paths`).
   - `common/scripted_triggers/00_geography_triggers.txt` + `00_coa_triggers.txt` — keep the trigger *names* (other kept content may call them), stub the dead-content bodies.
6. **Minimal replacements inside replaced dirs** (each replaced dir needs ≥ its minimum content):
   - `common/flag_definitions/zz_placeholder_flags.txt` — DEFAULT list only (engine falls back to tag-as-COA-key per vanilla header docs).
   - `common/coat_of_arms/coat_of_arms/zz_placeholder_coa.txt` — flat-color coa per tag.
   - `common/ai_strategies/zz_placeholder_default.txt` — the vanilla default strategy with geographic references stripped (countries need ≥1 valid strategy).
7. **`tools/MAP_RUNBOOK.md`** (append P4 section) — editor **`nodes.dat` regeneration** over the new provinces (province adjacency/pathfinding graph — vanilla's is invalid once provinces change). Committed after regeneration.
8. **`error.log` cleanup loop** — launch, read `logs/error.log`, fix the source (override file or scaffold), repeat until zero mod-file lines. Exether's override inventory is the residual checklist; `vic3-tiger` runs from this phase onward.

### Design Decisions
- **Scaffold = zz culture + vanilla religion** (user-confirmed): one additive culture referencing vanilla religion/heritage/language keeps vanilla cultures/religions/IGs/governments/social-classes loaded (exploration verified they carry no `STATE_`/tag refs), minimizing scaffold surface. Tags are throwaway `ZZA`–`ZZJ`, named `zz_placeholder_*` for clean deletion when real nations arrive.
- **History via verified effects only**: `create_state` / `create_pop` / `add_homeland` / `activate_law` all confirmed in [effects.log](../../docs/effects.log) at the correct scopes (`create_state` → state_region, `create_pop` → state). No guessed syntax.
- **Overrides by filename, never by editing vanilla**: replacing a vanilla file by matching its path/name is the only sanctioned way to neutralize dead vanilla references in kept dirs ([localization.md](../../.claude/rules/localization.md)/[scripting.md](../../.claude/rules/scripting.md) forbid editing base-game files).
- **`nodes.dat` regenerated in P4** (not P2): it is a function of provinces, which first exist after P3.
- **Determinism/MP**: every shipped artifact is a static committed file, identical on all clients; the scaffold generators are seeded/sorted like the map generators. MP-safe by construction ([core.md](../../.claude/rules/core.md)).

### Edge Cases
- **Missing object-locator warnings**: object locators (city/farm/mine/wood/port models) are scheduled for P5. If their absence produces lines in `error.log` (vs. silent/visual-only gaps), locator generation moves **into P4's editor step** — the P4 gate is a clean `error.log`, and that wins over the phase boundary.
- **Vanilla content referencing dead tags/states** after `replace_paths`: this is exactly what the step-8 cleanup loop catches; fix by adding a filename override to the checklist, never by editing vanilla.
- **A replaced dir left empty** that the engine expects populated → boot error; the minimal replacements (step 6) exist to prevent that. Watch the log for "no default strategy"/"no flag" classes of error.
- **Editor rewriting `province_terrains.txt` or other generated text** during the `nodes.dat` pass → review `git diff`, commit only `nodes.dat`.
- **Placeholder `province_terrains.txt` (from P3)** must still parse here; if terrain-key errors appear, they trace to that placeholder and are fixed in P3's generator, not by hand-editing the file.

### Testing
- Reproduce-then-fix loop: capture each `error.log` line before changing script, verify it's gone after (per [testing.md](../../.claude/rules/testing.md) regression rule).
- **Gate (the milestone):** launch Victoria 3 with the mod, **load into a session**, and confirm `Documents/Paradox Interactive/Victoria 3/logs/error.log` has **zero lines referencing this mod's files**.
- Map editor opens + saves (nodes.dat regeneration) without errors.
- State and strategic-region map modes render and are visually spot-checked (continent-sized tag ownership visible).

### Docs to Update
- `tools/MAP_RUNBOOK.md` — P4 `nodes.dat` regeneration + cleanup-loop procedure.
- `.claude/rules/` — no new rule unless the cleanup loop establishes a reusable override convention worth recording.
- On completion, this milestone unblocks planning of **P5 (terrain + visuals)** and **P6 (regions + canon naming)**, which were deferred until real state data exists.

---

<!-- Filled in on resolution -->
## Resolution
**Status**: _pending_
**Files changed**: ...
**Tests added**: ...
**Validation**: ...
