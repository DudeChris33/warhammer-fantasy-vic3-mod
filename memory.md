# Warhammer Fantasy Overhaul Working Memory

## Memory Hygiene Rules
- Keep compact and current.
- Cap each section to 5 active bullets max.
- Prefer outcomes and decisions over narrative.
- Move completed items to Archive.

## Current Focus
- Map pipeline: full regen landed (`54ef8dd`, 2026-09-27) plus adjacencies/straits (`82b3a06`); #5744 (canal straits) and #5525 (rebuild the map editor pack — likely load-crash cause) are the live map items.
- Docs restructure #5850: slim core (`CLAUDE.md` + `core.md`) plus path-scoped guides in `.claude/rules/`; see its board item for the audit report.
- Content epics in flight: bespoke coats of arms (#3621 children), lore hubs (#3663 children), impassable land (#3704).

## Key Decisions
- Guardrails live only in the always-loaded `core.md`; guides load by `paths:` when a matching file is Read (Bash reads and sub-agents are checked in #5850's loading probe).
- Land provinces are regenerated only through the generators; state borders and `sources/` stay Chris's to change.
- Chris works on a single machine (2026-09-28); the rules mirror and Maestro knowledge are how conventions reach other agents and survive a machine change.

## In-Progress Work
- #5850 docs restructure: commits A–D landed; memory triage, Maestro mirror re-sync and the audit report remain.
- Many COA/lore-hub children sit at `building`/`review` awaiting Chris's visual verdict.

## Open Questions
- Do path-scoped guides load for sub-agents and Bash reads? (#5850 canary probes answer this.)
- Renaming `testing.md` → `map.md` and `interface.md` → `gfx.md` once the open items citing the old names close.

## Archive
- Rules split into core + eight guides, drift audit against code, agents/skills repointed (#5850, 2026-09-29).
