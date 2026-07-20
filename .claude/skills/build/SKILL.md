---
name: build
description: Implement a planned issue or request — code, tests, commit, then spawn test/docs/security agents
user-invocable: true
argument-hint: <path to planned file>
---

Implement a planned {{PROJECT_NAME}} issue or feature request.

## Workflow

1. **Read** — Read the planned file at $ARGUMENTS. It must have a `## Plan` section. If not, tell the user to run `/plan` first.
2. **Read all files in scope** — Read every file listed in the plan before writing any code.
3. **Confirm** — Present the plan summary to the user. Get explicit confirmation before implementing.
4. **Implement** — Follow the plan step by step. Adhere to all rules in `.claude/rules/`.
5. **Test** — Run the test pipeline:
   {{BUILD_TEST_COMMANDS: replace with an indented fenced block of the real test command(s), the fast variants, and the pass criteria}}
   - Fix failures in the **code**, not the tests
6. **Commit** — Stage specific files only (never `git add -A`). Do not push.
7. **Spawn post-build agents** in parallel:
   - **test-runner** — run full test suite for regressions
   - **docs-updater** — update docs based on git diff
   - **security-review** — review diff for security concerns
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
- All tests must pass before the task is done.
- {{BUILD_RULES: 2–4 project-specific must-dos worth repeating here, e.g. required helpers, registration steps, cross-layer sync}}
