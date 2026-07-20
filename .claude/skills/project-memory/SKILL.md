---
name: project-memory
description: Display the current state of Claude Code project memory
user-invocable: true
---

Display the current state of Claude Code's project memory for {{PROJECT_NAME}}.

## Workflow

1. Read the memory index at `{{MEMORY_DIR: absolute path to this project's Claude Code memory directory — ~/.claude/projects/<path-slug>/memory, where <path-slug> is the project's absolute path with separators replaced by dashes}}/MEMORY.md`
2. List all memory files in that directory
3. Read each memory file
4. Present a summary table:

| Name | Type | Description | Content Preview |
|------|------|-------------|-----------------|
| ... | ... | ... | ... |

## Rules
- Read-only — do not modify any memory files.
- If no memory files exist, report that memory is empty.
