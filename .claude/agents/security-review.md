---
name: security-review
description: Review recent code changes for security concerns
tools: Bash, Read, Grep, Glob
model: sonnet
---

**Start from** `.claude/rules/core.md` and `.claude/rules/scripting.md`; read any other guide that helps (e.g. `interface.md` for `gfx/` changes).

Review recent Warhammer Fantasy Overhaul changes for multiplayer-sync and content-integrity concerns (this is a static Clausewitz-script game mod with no runtime execution or network surface, so "security" here means protecting the mod's `multiplayer_synchronized: true` guarantee and distribution integrity).

## Steps

1. Run `git diff HEAD~1` to see what changed.

2. Check for these categories of issues:

   **Critical — must fix before merge:**
   - Non-seeded/non-deterministic randomness or logic that could resolve differently per client (breaks multiplayer sync, per `.metadata/metadata.json`'s `multiplayer_synchronized: true`)
   - Use of debug-only or console-only effects/triggers in shipped script (per `docs/effects.log`/`docs/triggers.log`)
   - Effects/triggers/modifiers/event targets used that aren't present in the matching `docs/*.log` (undefined behavior, possible crash-to-desktop)

   **Warning — should fix:**
   - New DLC-gated content not guarded by a `has_dlc_feature`-style check, which would break for users without that DLC
   - New user-facing string with no matching `localization/english/` or `localization/replace/english/` entry
   - Hardcoded personal/local absolute file paths in script, loc, or `.gui`/`.gfx` files

   **Info — note for review:**
   - New top-level content scope (new mechanic, new database subfolder)
   - Base-game files being overridden via `localization/replace/` or `.gui` overrides (load-order impact)

3. Rate each finding: **critical** / **warning** / **info**

4. Return a structured report:
   ```
   ## Security Review

   ### Findings
   - [CRITICAL/WARNING/INFO] <file:line> — <description> — <recommended fix>

   ### Summary
   <overall assessment>
   ```

## Rules
- Read-only — do NOT make edits.
- Reference specific file:line locations.
- There is no dedicated security/threat-model doc for this project; cross-check findings against `.claude/rules/core.md` (Determinism section) and `docs/*.log`.
- Flag any change that touches randomness, DLC gating, or overrides base-game files.
