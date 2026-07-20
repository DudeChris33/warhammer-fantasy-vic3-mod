---
name: plan
description: Design implementation approach for an issue or request file, adds a Plan section
user-invocable: true
argument-hint: <path to issue or request file>
---

Design the implementation approach for a Warhammer Fantasy Overhaul issue or feature request. Do NOT implement anything.

## Workflow

1. **Read** — Read the issue/request file at $ARGUMENTS (or list open files in `planning/issues/` and `planning/requests/` and ask which one)
2. **Deep exploration** — Read ALL related source files referenced in the investigation section. Check for existing features, helpers, or patterns that can be reused. Confirm every effect/trigger/modifier/event target/on_action the plan will rely on against the matching `docs/*.log` file.
3. **Design** — Create a file-level implementation plan:

```markdown
## Plan

### Objective
<One sentence: what we're building/fixing and why>

### Steps (ordered)
1. **<File path>** — <what changes and why>
2. **<File path>** — <what changes and why>

### Design Decisions
- <Key choice>: <rationale>

### Edge Cases
- <What could go wrong, boundary conditions>

### Testing
- <How to verify — specific in-game steps>
- Must pass: mod loads in Victoria 3 with the change active, and `logs/error.log` shows no new errors referencing this mod's files (see [testing.md](../../rules/testing.md))

### Docs to Update
- <Which docs need changes>
```

4. **Present** — Show the plan to the user. Wait for confirmation. Iterate if needed.
5. **Append** — Add the `## Plan` section to the issue/request file. Set Status to "planned".
6. **Hand off** — Print: "Start new session, run `/build <file-path>`"

## Rules

- Do NOT implement anything. Planning and documentation only.
- Read all files in scope before designing.
- Reference actual file paths, function names, and line numbers.
- Resolve all open questions before marking as planned.
- Every plan touching user-facing content must include a step for its `localization/english/` (or `localization/replace/english/`) entries.
