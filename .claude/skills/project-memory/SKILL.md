---
name: project-memory
description: Display the current state of project memory across its three layers
user-invocable: true
---

Display the current state of memory for Warhammer Fantasy Overhaul. There are three layers (see `CLAUDE.md`, *Memory layers*).

## Workflow

1. **Claude Code memory** — use the memory directory your system prompt reports for this project (do not hardcode a path). Read its `MEMORY.md` index, list the files, read each one.
2. **`memory.md`** — read the git-tracked scratchpad at the repo root.
3. **Maestro knowledge** — point to it rather than dumping it: the project id is in `.claude/maestro.json`; `search_knowledge` (maestro MCP) reads the durable, cross-session entries.
4. Present a summary table for layer 1:

| Name | Type | Description | Content Preview |
|------|------|-------------|-----------------|
| ... | ... | ... | ... |

Then a short section for `memory.md` (current focus and open questions) and one line on how to query knowledge.

## Rules
- Read-only — do not modify any memory files.
- If no memory files exist, report that memory is empty.
