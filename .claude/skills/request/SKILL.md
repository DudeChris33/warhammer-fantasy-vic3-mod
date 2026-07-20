---
name: request
description: Explore codebase, clarify scope, write a structured feature request file to planning/requests/
user-invocable: true
argument-hint: <description of what you want>
---

Explore the codebase and document a feature request for the Warhammer Fantasy Overhaul project. Do NOT implement anything.

## Workflow

1. **Parse** — Read the feature description from $ARGUMENTS (or ask user what they want)
2. **Explore** — Read relevant script/loc/gui files. Check what exists, what would need to change, and any constraints. Check `docs/effects.log`, `docs/triggers.log`, `docs/modifiers.log`, `docs/event_targets.log`, and `docs/on_actions.log` to confirm the game actually supports what's being requested before scoping it.
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
- **Localization needed**: <which new loc keys this requires>
```

5. **Hand off** — Print the file path and: "Start new session, run `/plan planning/requests/<slug>.md`"

## Rules

- Do NOT implement anything. Exploration and documentation only.
- Resolve ambiguities with the user before finalizing.
- Reference actual file paths and script/effect/trigger names.
- Always assess localization impact (new keys needed) and multiplayer-determinism impact (see [core.md](../../rules/core.md)).
