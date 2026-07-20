---
name: plan
description: Design implementation approach for an issue or request file, adds a Plan section
user-invocable: true
argument-hint: <path to issue or request file>
---

Design the implementation approach for a {{PROJECT_NAME}} issue or feature request. Do NOT implement anything.

## Workflow

1. **Read** — Read the issue/request file at $ARGUMENTS (or list open files in `planning/issues/` and `planning/requests/` and ask which one)
2. **Deep exploration** — Read ALL related source files referenced in the investigation section. Check for existing features, helpers, or patterns that can be reused. {{PLAN_EXPLORE_HINTS: one or two sentences pointing at this project's reference docs — or remove}}
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
- <How to verify — specific test commands, expected results>
- Must pass: {{PLAN_TEST_CRITERIA: the project's full test command and pass criteria}}

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
- {{PLAN_RULES: 1–2 additional project-specific rules, e.g. layers every plan must cover}}
