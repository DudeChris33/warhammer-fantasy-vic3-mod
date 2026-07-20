---
name: issue
description: Investigate a bug report, confirm if possible, write a structured issue file to planning/issues/
user-invocable: true
argument-hint: <description of the problem>
---

Investigate a bug in the {{PROJECT_NAME}} project. Do NOT fix it — investigation and documentation only.

## Workflow

1. **Parse** — Read the bug description from $ARGUMENTS (or ask user to describe it)
2. **Investigate** — Read relevant source files, trace the code path. {{ISSUE_INVESTIGATE_HINTS: one or two sentences pointing at this project's reference docs for expected behavior — e.g. its API/command reference and docs index}}
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
{{ISSUE_EXTRA_FIELDS: extra Investigation bullets this project needs, e.g. cross-layer impact — or remove this line}}
```

5. **Hand off** — Print the file path and: "Start new session, run `/plan planning/issues/<slug>.md`"

## Rules

- Do NOT fix the bug. Investigation and documentation only.
- Read files before drawing conclusions.
- If it's a security bug, flag it explicitly. {{ISSUE_SECURITY_POINTER: where this project's security docs live — or remove}}
- {{ISSUE_RULES: 1–3 additional project-specific rules, e.g. layers to always check}}
