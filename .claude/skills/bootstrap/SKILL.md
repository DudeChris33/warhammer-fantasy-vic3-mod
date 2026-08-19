---
name: bootstrap
description: One-time setup — analyze this codebase, fill every placeholder in the shipped workflow files, and write CLAUDE.md and .claude/rules/
user-invocable: true
---

Finish integrating the AI agent workflow into this project. The fixed scaffolding (skills, agents, `planning/`, `memory.md`) is already in place from the bootstrap bundle. Your job: verify git, analyze the codebase, generate the two per-project files (`CLAUDE.md`, `.claude/rules/`), and fill every `{{...}}` placeholder in the shipped files.

Derive everything from this project's actual structure, patterns, and conventions. Do not invent conventions and do not copy from other projects.

**Placeholder convention**: `{{NAME: guidance}}` tokens are bootstrap-time — you replace them now. Angle-bracket `<...>` fields inside document templates are usage-time — leave them untouched.

## Workflow

### 1. Git check

Run `git rev-parse --is-inside-work-tree`. If this is not a git repository, explain that the `/build` skill and all three sub-agents depend on git (`git diff HEAD~1`, commits) and ask the user whether to run `git init`. If they decline, continue, but record the limitation in the final report.

### 2. Analyze the project

Answer these internally before writing anything, from actual files:

- **Structure** — project type; primary language/framework and versions; how the codebase is organized; test framework, location, and the real commands; docs layout and whether a master index exists.
- **Conventions** — how core building blocks are defined (models, routes, handlers, views — whatever this stack uses); where domain logic lives; naming conventions; non-obvious patterns a new agent must know.
- **Security** — what is security-sensitive (auth, keys, tokens, permissions, attack surface) and where the security docs live.

Read at minimum: the root directory listing, `README.md` (if present), 2–3 representative source files (a core module, a route/handler, a test), the docs index (if present), and any existing agent instruction files.

### 3. Write `CLAUDE.md`

The compact master file, auto-loaded every session — a map, not a manual. Detailed conventions belong in `.claude/rules/`. Sections:

1. **Title + one-liner** — project name and a one-sentence description (stack included).
2. **Canonical entry point** *(if the project has a docs index)* — where to start for anything doc-related.
3. **Project layout** — a small table mapping the paths that matter to what lives there.
4. **How to work here** — verbatim structure:
   - **Rules** in `.claude/rules/*.md` are loaded automatically. Follow them.
   - **Skills** in `.claude/skills/` invoked with `/<name>`:
     - `/issue <description>` — investigate + document a bug
     - `/request <description>` — explore + document a feature request
     - `/plan <path/to/file.md>` — design implementation approach
     - `/build <path/to/file.md>` — implement, test, commit, review
     - `/project-memory` — show memory state
   - **Sub-agents** in `.claude/agents/` are spawned by `/build`:
     - `test-runner` — regression tests *(omit if removed in step 5)*
     - `docs-updater` — update docs from diff
     - `security-review` — security audit
5. **Workflow chain** — include this diagram:

   ```
   Bug or feature idea
         │
         ▼
   /issue or /request  ── writes ──►  planning/issues/ or planning/requests/
         │
         ▼
   /plan             ── appends ─►  ## Plan section
         │
         ▼
   /build            ── appends ─►  ## Resolution, moves to planning/done/
   ```

   Note that `/plan` must never be skipped — it's where file-level decisions get pinned down.
6. **Planning directory** — the tree (issues/ open bugs · requests/ open feature requests · done/ resolved · future/ backlog · rejected/ declined).
7. **Trust order** — ranked list for docs ↔ code conflicts (project docs → `.claude/rules/` → existing code patterns, adapted to the actual doc structure). On conflict: fix one side and update the other.
8. **Build + test** *(if applicable)* — the real commands, fast variants, and the pass criteria that must hold before any task is complete.
9. **Security callouts** *(if security-sensitive)* — the handful of facts an agent must never violate, with doc links.
10. **Non-negotiables** — 5–8 short rules that prevent the worst damage ("Read before editing", "No drive-by refactors", "No `git add -A`", "No `git push` unless asked", plus observed project-specific ones).

### 4. Write `.claude/rules/`

**`core.md`** — always. Open with: "These rules apply to all work in this repository. Non-negotiable." Sections: 1–3 domain-critical sections derived from the project (Security, Input Handling, Response Envelope, Persistence — whatever is most breakable here); **Forbidden Actions**; **Philosophy** (read before editing, minimal changes, where logic lives, confirm when uncertain); **Trust Order** (same as `CLAUDE.md`); **Delivery Checklist** (checkboxes; end with "Request/issue file moved to `planning/done/` with resolution filled in").

**One file per layer/domain actually present** — e.g. a Django API might get `api.md`, `models.md`, `testing.md`, `docs.md`, `performance.md`; an embedded project might get `firmware.md`, `python.md`, `testing.md`, `docs.md`. Each: `# <Layer> Rules`, short sections covering organization, the patterns to follow (real signatures/idioms from this codebase), naming, and what's forbidden at that layer. `testing.md` must include the real test commands and the regression-test rule (must fail before the fix, pass after — fix the code, never the test). `docs.md` must map which docs get updated when.

Every rule must trace to something you observed.

### 5. Fill the placeholders

Find every token: `grep -rn "{{" .claude planning memory.md` (ignore matches in `.claude/skills/bootstrap/`). Replace each per its inline guidance; where guidance says "or remove", delete the line if not applicable. Files and their tokens:

| File | Tokens |
|---|---|
| `memory.md` | PROJECT_NAME |
| `.claude/skills/issue/SKILL.md` | PROJECT_NAME, ISSUE_INVESTIGATE_HINTS, ISSUE_EXTRA_FIELDS, ISSUE_SECURITY_POINTER, ISSUE_RULES |
| `.claude/skills/request/SKILL.md` | PROJECT_NAME, REQUEST_EXPLORE_HINTS, REQUEST_EXTRA_FIELDS, REQUEST_RULES |
| `.claude/skills/plan/SKILL.md` | PROJECT_NAME, PLAN_EXPLORE_HINTS, PLAN_TEST_CRITERIA, PLAN_RULES |
| `.claude/skills/build/SKILL.md` | PROJECT_NAME, BUILD_TEST_COMMANDS, BUILD_RULES |
| `.claude/skills/project-memory/SKILL.md` | PROJECT_NAME, MEMORY_DIR |
| `.claude/agents/test-runner.md` | PROJECT_NAME, TEST_COMMAND, TEST_REPORT_LOCATION, TEST_RULES |
| `.claude/agents/docs-updater.md` | PROJECT_NAME, DOCS_ROUTING, DOCS_MAP, DOCS_RULES |
| `.claude/agents/security-review.md` | PROJECT_NAME, SECURITY_CRITICAL, SECURITY_WARNING, SECURITY_INFO, SECURITY_MODEL_DOCS |

**If the project has no test suite**: delete `.claude/agents/test-runner.md`, remove the `test-runner` bullet from step 7 of `.claude/skills/build/SKILL.md`, and omit it from `CLAUDE.md`'s sub-agent list. Note it under "What's missing" in the report.

### 6. Verify

- `grep -rn "{{" .claude planning memory.md` returns no matches outside `.claude/skills/bootstrap/`.
- `planning/` has all five folders (issues, requests, done, future, rejected) and both `_template.md` files.
- `CLAUDE.md` and `.claude/rules/core.md` exist; the sub-agent list matches the agents actually present.

### 7. Report

1. **Project type and stack** — what you found
2. **Key conventions captured** — the 3–5 most important non-obvious rules you encoded
3. **Files written and filled** — list with one-line description each
4. **What's missing** — anything you couldn't determine from the codebase that the user should fill in manually (including a declined `git init`, if applicable)
5. **First suggested action** — e.g. run `/request` to file the first feature, or `/issue` for a known bug
6. Note that `.claude/skills/bootstrap/` can now be deleted, or kept for reference.

## Rules for this bootstrap task

- Derive all rules from the actual codebase — do not invent conventions.
- If something is ambiguous, note it in the report as "What's missing."
- Keep all files concise — `CLAUDE.md` and rules load every thread, so token cost matters.
- Do not create migration files, install packages, or run project commands. The only state-changing command you may offer is `git init` (step 1, user-approved).
- Do not modify existing source code.
- If old workflow files exist (`Agent.md`, `prompts/` mode files), leave them in place and note them in the report.
