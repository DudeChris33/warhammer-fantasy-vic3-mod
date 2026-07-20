---
name: issue
description: Investigate a bug report, confirm if possible, write a structured issue file to planning/issues/
user-invocable: true
argument-hint: <description of the problem>
---

Investigate a bug in the Warhammer Fantasy Overhaul project. Do NOT fix it — investigation and documentation only.

## Workflow

1. **Parse** — Read the bug description from $ARGUMENTS (or ask user to describe it)
2. **Investigate** — Read relevant script/loc/gui files, trace the effect/trigger/event chain. Cross-check every effect, trigger, modifier, event target, on_action, or custom localization key against the matching `docs/*.log` file to confirm expected behavior and scope requirements.
3. **Confirm** — Best-effort confirmation through code analysis. If a regression test is feasible, write and run it to demonstrate the failure.
4. **Document** — Write `planning/issues/<slug>.md` using this template:

```markdown
# <Title>

| Field | Value |
|-------|-------|
| Type | bug |
| Status | open |
| Date | <YYYY-MM-DD> |
| Severity | critical / high / medium / low |

## Description
<What's broken — observed vs expected behavior>

## Context
<Where this was found, how to reproduce>

## Acceptance Criteria
- [ ] <What "fixed" looks like>

## Investigation
- **Likely root cause**: <what's wrong and where>
- **Confidence**: high / medium / low
- **Code path**: <file:line references>
- **Regression test**: <test or command sequence that demonstrates the bug>
- **Related files**: <list of files involved>
- **In-game reproduction**: <steps to reproduce and the exact `logs/error.log` line, if any>
```

5. **Hand off** — Print the file path and: "Start new session, run `/plan planning/issues/<slug>.md`"

## Rules

- Do NOT fix the bug. Investigation and documentation only.
- Read files before drawing conclusions.
- If the bug involves non-determinism (would desync multiplayer), flag it explicitly — see [core.md](../../rules/core.md).
- Always check whether the bug traces to a mismatch with `docs/*.log` (wrong scope, deprecated effect, etc.) before assuming it's a logic error.
