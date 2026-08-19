---
name: review-panel
description: Convene the five-expert review panel — loremaster, cartographer, geographer, vic3 modding expert, veteran game designer — on a plan, a diff, or a rendered artifact
user-invocable: true
argument-hint: <planning file | artifact path | commit range | "working" | question> [--only <roles>]
---

Convene the Warhammer Fantasy Overhaul review panel. Five specialists review the
same target independently and in parallel; you merge their verdicts into one
ruling. **Nothing is fixed here** — the panel produces findings; the maestro
skills act on them (`/maestro-task` to file a fix as a board item, `/maestro-scope`
to re-plan an existing one).

The panel is advisory. On anything visual, **the user is the final gate** — a panel
PASS never substitutes for the user looking at the render.

## The panel

| Agent | Owns |
|---|---|
| `loremaster` | Warhammer Fantasy canon — names, places, factions, era, tone |
| `cartographer` | Map craft — shapes, borders, projection, legibility |
| `geographer` | Physical plausibility — elevation, climate, coasts, rivers |
| `vic3-modding-expert` | Engine correctness — script, formats, loc, determinism |
| `game-designer` | Play and scope — granularity, systems fit, sequencing |

## Workflow

### 1. Resolve the target

From `$ARGUMENTS`. Accept any of:

- **A planning file** (`planning/**/*.md`) — review the plan or issue itself: is it
  correct, complete, and worth building?
- **An artifact** (`tools/derived/qa_*.png`, `map_data/*.png`, …) — review the
  output.
- **A commit, range, or `working`** — review the diff. Default to
  `git diff HEAD~1` for a single commit, `git diff` for `working`.
- **A free-text question** — a design fork the user wants five opinions on.
- **Empty** — list the open files in `planning/issues/` and `planning/requests/`
  plus `git status`, and ask which. Do not guess.

An `--only <roles>` suffix (comma-separated, e.g. `--only lore,cartography`) runs a
subset. Map loose names onto the agents; if a name is ambiguous, ask.

### 2. Gather the context yourself, then write a scope brief

**Subagents start cold.** They see only what you hand them, so the quality of the
brief determines the quality of the review. Before spawning, read the target and
everything it depends on, then compose one brief — handed **verbatim and identical**
to every panelist:

```markdown
## Review target
<what is being reviewed, in one sentence, and which milestone it belongs to>

## Files to read
<exact paths — the target, the plan section governing it, related issues>

## Artifacts to open
<exact paths to every render/bitmap that must be looked at, or "none exist yet — say so">

## Acceptance criteria in force
<the actual gate this must clear, quoted from the planning file — not paraphrased>

## Already measured — do not re-derive
<facts and numbers the planning files already establish, with their values>

## Settled decisions — not open for re-litigation
<choices the user has fixed, so panelists flag rather than reopen them>

## Explicitly out of scope
<what belongs to a later milestone>

## How to report
<the output contract from your agent definition; verdict PASS | CONCERNS | BLOCK>
```

Two sections matter more than the rest. **"Already measured"** stops five agents
burning tokens re-deriving what the plan of record already states. **"Settled
decisions"** stops the panel relitigating choices the user has made — the panel
critiques execution against the decision, not the decision, unless a panelist has
a substantive reason, which lands as a NOTE.

If the target is visual and no render exists, say so in the brief rather than
sending the panel to look at nothing.

### 3. Spawn the panel

Spawn all selected agents **in a single message** so they run concurrently. Give
each the same scope brief plus one line naming its lane.

Wait for every panelist to report. **Never synthesize partial results**, and never
write or predict a panelist's findings yourself — if the user asks before the
reports land, say the panel is still sitting.

### 4. Synthesize

Merge into one report. The synthesis is the value — do not just concatenate five
reports.

- **Deduplicate**, keeping the framing from whichever panelist owns the lane.
- **Surface disagreement explicitly.** Where two panelists conflict — the
  loremaster wants a region split that the game-designer says fragments play —
  that tension is the most useful output of the whole exercise. Present both, then
  rule with a one-line rationale. Never average them into mush.
- **Promote cross-lane observations.** A "Not my lane" note that the owning
  panelist missed is a real finding — say who raised it and who missed it.
- **Discount unsubstantiated findings.** Every finding is supposed to cite a file,
  a line, or a number. Drop the ones that do not, and note that you dropped them.
- **Weigh by lane.** On an engine claim the vic3-modding-expert outranks the
  others; on canon the loremaster does; on whether the map reads, the cartographer
  does. A panelist reaching outside its lane is a hint, not a verdict.

Report:

```markdown
# Review Panel — <target> — <YYYY-MM-DD>

**Ruling**: PASS | PASS WITH CONCERNS | BLOCK
**Panel**: <roles that sat> — <verdict from each>

## Blocking
- **[<role>]** <finding> — <evidence> — <what to do>

## Concerns
- **[<role>]** ...

## Disagreements
- <role> vs <role> on <topic>: <both positions> → **Ruling**: <call + rationale>

## Notes
- **[<role>]** ...

## Not raised
<anything the panel structurally could not check — no render existed, no game load
was done, a lane was skipped via --only>
```

The ruling is **BLOCK** if any panelist blocks in its own lane. It is **PASS WITH
CONCERNS** if there are concerns but no blocks. Reserve plain **PASS** for a clean
sheet, and be honest when it is one.

### 5. Record

If the target was a planning file, offer to append the report as a
`## Review Panel — <YYYY-MM-DD>` section. If it was a **maestro board item** (its
workspec or `## Plan`), the equivalent record is a comment on that item through
the maestro skills — offer that instead. **Ask before writing either** — the user
may want to act on it first. This project records review outcomes in the record of
the work (see commit `6a3ee9d`, which recorded a rejection), so a rejection is
worth writing down as much as a pass.

The panel changes no board stage and moves no file between `planning/` folders —
it only records findings; acting on them is a scope/build skill's job.

### 6. Hand off

State plainly what happens next:

- BLOCK on a defect → `/maestro-task <description>` to file it (or, on an existing
  board item, record the finding on the item)
- BLOCK on the approach → `/maestro-scope <item-id>` to re-plan
- PASS WITH CONCERNS → `/maestro-build <item-id>`, carrying the concerns
- Visual target → render the artifact and **send it to the user**, who is the real
  gate

## Rules

- **The panel never edits anything.** No fixes, no regenerating bitmaps, no
  `--update-manifest`, no `fit_registration.py`. Findings only.
- **Spawn in parallel, in one message.** Wait for all of them.
- **A green offline gate is not a PASS.** On S3a every machine check passed while
  the rendered map was unusable — swirled cells, Bretonnia as 3 states, spiked
  corners — because the checks assert structural invariants (does it tile, is it
  deterministic) that a partition of noise also satisfies. If the target is visual
  and nobody looked at a picture, the panel has not reviewed it.
- **Never claim a game-load verification that did not happen.** If the target
  touches `common/`, `events/`, `gui/`, `localization/` or `map_data/` and no
  `logs/error.log` check has been done, that goes under "Not raised".
- **Preserve disagreement.** Do not sand the panel down into consensus.
- **PASS is a real verdict.** A panel that always finds something is a panel nobody
  reads. Equally, do not soften a BLOCK to be agreeable.
