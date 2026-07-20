---
name: build
description: Implement a planned issue or request — code, tests, commit, then spawn test/docs/security agents
user-invocable: true
argument-hint: <path to planned file>
---

Implement a planned Warhammer Fantasy Overhaul issue or feature request.

## Workflow

1. **Read** — Read the planned file at $ARGUMENTS. It must have a `## Plan` section. If not, tell the user to run `/plan` first.
2. **Read all files in scope** — Read every file listed in the plan before writing any code.
3. **Confirm** — Present the plan summary to the user. Get explicit confirmation before implementing.
4. **Implement** — Follow the plan step by step. Adhere to all rules in `.claude/rules/`.
5. **Test** — There is no automated test suite (Clausewitz script has no offline validator). Ask the user to load the mod in Victoria 3 and confirm `logs/error.log` (at `Documents/Paradox Interactive/Victoria 3/logs/error.log`) shows no new errors referencing this mod's files — see [testing.md](../../rules/testing.md).
   - Fix failures in the **script**, not by suppressing the error
6. **Commit** — Stage specific files only (never `git add -A`). Do not push.
7. **Spawn post-build agents** in parallel:
   - **docs-updater** — update docs based on git diff
   - **security-review** — review diff for multiplayer-desync and content-integrity concerns
8. **Resolve** — Append `## Resolution` section to the file:
   ```markdown
   ## Resolution
   - **Date**: <YYYY-MM-DD>
   - **Summary**: <what was done>
   - **Files changed**: <list>
   - **Tests**: <pass count / criteria met>
   - **Commit**: <hash>
   ```
   Move the file to `planning/done/`.
9. **Report** — Summarize what was built, tested, and any agent findings.

## Rules

- Confirm before implementing.
- Read before editing — always.
- Commit but never push. Stage specific files only.
- The user must confirm a clean `logs/error.log` before the task is done.
- Every effect/trigger/modifier/event target/on_action used must be confirmed against `docs/*.log`.
- Every new user-facing string needs a `localization/english/` (or `localization/replace/english/`) entry.
- Preserve multiplayer determinism — no non-seeded randomness or debug-only effects.
