---
name: project-memory
description: Display the current state of Claude Code project memory
user-invocable: true
---

Display the current state of Claude Code's project memory for Warhammer Fantasy Overhaul.

## Workflow

1. Read the memory index at `C:\Users\Chris Cyr\.claude\projects\C--Users-Chris-Cyr-Documents-Paradox-Interactive-Victoria-3-mod-warhammer-fantasy\memory\MEMORY.md`
2. List all memory files in that directory
3. Read each memory file
4. Present a summary table:

| Name | Type | Description | Content Preview |
|------|------|-------------|-----------------|
| ... | ... | ... | ... |

## Rules
- Read-only — do not modify any memory files.
- If no memory files exist, report that memory is empty.
