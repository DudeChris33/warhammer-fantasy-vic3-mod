---
name: request
description: Explore codebase, clarify scope, write a structured feature request file to planning/requests/
user-invocable: true
argument-hint: <description of what you want>
---

Explore the codebase and document a feature request for the {{PROJECT_NAME}} project. Do NOT implement anything.

## Workflow

1. **Parse** — Read the feature description from $ARGUMENTS (or ask user what they want)
2. **Explore** — Read relevant source files. Check what exists, what would need to change, and any constraints. {{REQUEST_EXPLORE_HINTS: one or two sentences pointing at this project's reference docs — e.g. its API/command reference and docs index}}
3. **Clarify** — Ask questions until scope is unambiguous: API contract, permissions, edge cases, out-of-scope items.
4. **Document** — Write `planning/requests/<slug>.md` using this template:

```markdown
# <Title>

| Field | Value |
|-------|-------|
| Type | request |
| Status | open |
| Date | <YYYY-MM-DD> |
| Priority | high / medium / low |

## Description
<What we're building and why>

## Context
<Current state, what exists, why this is needed>

## Acceptance Criteria
- [ ] <Specific, testable criteria>

## Investigation
- **What exists**: <current relevant code with file paths>
- **What changes**: <list of files to create or modify>
- **Constraints**: <limits, security requirements, backward compat, etc.>
- **Related files**: <list>
- **Endpoints/commands**: <new or modified surface area>
- **Tests required**: <what to test>
- **Out of scope**: <explicitly excluded items>
{{REQUEST_EXTRA_FIELDS: extra Investigation fields or a cross-layer impact subsection this project needs — or remove this line}}
```

5. **Hand off** — Print the file path and: "Start new session, run `/plan planning/requests/<slug>.md`"

## Rules

- Do NOT implement anything. Exploration and documentation only.
- Resolve ambiguities with the user before finalizing.
- Reference actual file paths and function names.
- {{REQUEST_RULES: 1–3 additional project-specific rules, e.g. layers whose impact must always be assessed}}
