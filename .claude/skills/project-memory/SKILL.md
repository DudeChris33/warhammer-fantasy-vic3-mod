---
name: project-memory
description: Display the current state of project memory across its two layers
user-invocable: true
---

Display the current state of memory for Warhammer Fantasy Overhaul. There are two layers (see `CLAUDE.md`, *Memory layers*).

## Workflow

1. **Claude Code memory** — use the memory directory your system prompt reports for this project (do not hardcode a path). Read its `MEMORY.md` index, list the files, read each one.
2. **Maestro knowledge** — point to it rather than dumping it: the workspace id is `workspace` in `.claude/maestro.json`; work packets surface its entries automatically and `search_knowledge` (maestro MCP) reads them on demand. Call `get_knowledge_map` for the workspace and report its `duplicates` pairs and its retired (`stale`) entries as the hygiene check. The project knowledge base (the `project` id) is a frozen archive.
3. Present a summary table for layer 1:

| Name | Type | Description | Content Preview |
|------|------|-------------|-----------------|
| ... | ... | ... | ... |

Then one line on how to query knowledge.

## Rules
- Read-only — do not modify any memory files.
- If no memory files exist, report that memory is empty.
