---
name: maestro-scope
description: >-
  Pull one or more maestro board items, scope each inside this repo with full
  investigation rigor, append a file-level ## Approach to every workspec, and
  push them back (stage=planned) via the maestro MCP.
user-invocable: true
argument-hint: <item-ids, e.g. "431" or "431 432" (omit to pick from the board)>
maestro-skill-version: 34
---

# Maestro Scope — Design the Approach on the Item

Vocabulary (#2905): **"Plan" means the parent unit** — a top-level item's
approved roster of tasks in dependency waves. The task-level design section
this skill writes is **`## Approach`**. Legacy workspecs keep their `## Plan`
heading — the build skill reads both, permanently; there is no bulk rewrite of
historical descriptions.

Scoping runs **inside the target repo** with full code access; only storage
differs — the approach goes back to the item's workspec, not a local planning
file.

## One Item or Many

**Takes any number of ids** — `/maestro-scope 431`, `/maestro-scope 431 432
438`. Scoping is read-only, so it parallelizes cleanly.

- **One item** → run the workflow below inline, in this session.
- **Several** → run the wrong-id gate over the whole roster in one block, then
  **spawn one fresh-context sub-agent per item, all in one message**. Each runs
  workflow steps 3-6 for its item with read-only repo access and returns the
  complete updated description (human block + `## Spec` + `## Approach`), its
  files-touched list, its verification tier, schema/contract impact, and its
  premise check. Then, in this session:
  - **Cross-check the plans before pushing anything** — two plans changing the
    same function or contract in incompatible directions, two migrating the same
    table, the same helper added twice, one item another makes obsolete. Amend
    the affected plans, say what changed, and **escalate to `full` a tier a
    sibling plan invalidates** (a helper or contract one plan creates and
    another consumes bounds nothing per item; two plans editing one file keep
    their tiers, and the closing union runs both plans' modules).
  - **Present once** for the set: the step-7 TL;DR per item, plus the cross-item
    findings and a build order where a dependency forces one.
  - **Push each item** per step 8, and report which landed and which did not.
- Cap it around six ids. Past that the presentation is a review nobody does —
  propose the highest-priority ones and say what you left.

**Never scope several items inline, one after another, in this session** — by
the fourth plan the session has forgotten the first item's code. Delegate, or
do them in separate sessions.

## Board Resolution

Same as `maestro-task`: a session-stated workspace in the first message comes
first, else read Maestro's `.claude/maestro.json` repo config; on any
miss, resolve via `whoami()` / `list_workspaces()` / `list_boards()`, ask, offer
to write the file. Unreachable or unauthenticated → stop with an explicit
notice; offer the repo's local scoping skill if one exists. Never fall back
silently.

Two of its rules apply here too:

- **Name boards and items when you report them — never bare ids**: `board
  "Backlog" (Maestro workspace, id 8)`, `#586 "An agent cannot see what it
  deployed"`, plus the item URL (link form under Rules).
- **Pass `client=` (the client you are running in) and `model=` (your model id)
  on every `create_board_item`, `update_board_item` and `comment_on_item`
  call.** The server cannot observe either, so a silent write lands in the trail
  under the default label — "via Claude", whoever wrote it.

## Checkout lifecycle

After the wrong-id confirmation and before deep work, call
`acquire_board_item_checkout(item, purpose="scope", idempotency_key=<fresh
high-entropy key>, expected_minutes=...)`. Keep the returned `checkout_token`
only in this orchestrating session. It is a bearer capability that necessarily
appears in this tool transcript; never put it in the workspec, comments,
metadata, logs, URLs, realtime messages, durable browser storage, or any
sub-agent prompt/transcript.

If acquire reports a conflict, show the human the holder, purpose, and expiry,
then ask whether to wait or continue without a checkout. A checkout is advisory:
the human may choose to continue. Never pass its token to ordinary board writes.
Immediately after the acquire attempt, re-fetch `get_work_packet(item)`
and the latest comments. If the title, stage, or description materially changed,
repeat the roster confirmation before continuing. Every post-acquire sub-agent
starts in fresh/isolated context and receives the workspec, never the token or
owning transcript.

Renew with `renew_board_item_checkout` no later than 40 minutes after acquire
or the last renewal, immediately before and after long commands/waits, and
before accepting a sub-agent result. Keep waits short enough to heartbeat. A
`checkout_lost`, `checkout_expired`, or `checkout_replaced` means the advisory
signal is gone: report it and do not pretend the lease is still held. It does
not authorize or block item writes, and the token is used only for renew and
check-in lifecycle calls.

**Report the phase as you renew.** Pass `activity` with the renewal — the
scoping phase in a few words ("exploring", "drafting plan", "challenging") —
at each phase change, still no later than 40 minutes apart. One round trip
both heartbeats and reports, and it writes no trail note. Scope check-ins
rarely carry `criteria` ticks; those are the build's progress vocabulary.

On every terminal path—including success, refusal, blocker, exception, or user
cancellation—call `check_in_board_item_checkout`. If Maestro was unavailable,
local analysis may finish; re-read before any later board push.

## Confirm the Item — the wrong-id gate

**An item id is not self-describing.** Ids get transposed or read off a stale
list, and the failure is silent: scoping completes on the wrong item and
rewrites its workspec. This has happened repeatedly. Before any exploration —
before any scratch file is written or any sub-agent spawns — show the user what
**every** id resolved to and get a yes. Several ids: one card each, in one
block, one ask at the end; and say so explicitly when two of them are a digit
apart, which is the transposition this gate exists to catch.

Required whenever the id came from an argument, a note, or another session. Skip
only when the user just picked the item off a list you presented this session
(they have seen the title), or when they waive it outright.

Build the card from **one** `get_work_packet(item)`. It carries everything the
card needs — the workspec, the board and workspace **names**, who filed it and
when, how long it has sat in its stage, its parent, and the rules the workspec
references — so nothing here needs a second call. Older server without the tool:
`get_board_item(item)` plus one `list_boards(<the item's workspace>)` for the
names, and say you fell back.

    #586 "An agent cannot see what it deployed — add preview_site"
    board "Backlog" · workspace "Maestro" · stage inbox · must
    filed by Ian Starnes on 2026-07-29 (today)
    part of #516 "Sites + domains — release hardening (epic)"
    https://maestromojo.com/app/#/board/8?item=586

    Agents ship sites they never see: deploy_site returns byte counts, not
    pixels, and every cheap substitute (the browser pane, headless Chrome)
    lies in a different direction. Wants an MCP render tool so an agent can
    look at what it deployed.

    Scope this one?

- **Title first, then where it lives** — `board_name` and `workspace_name`; an
  id cannot be recognised.
- **Filer and age**: `filed.by` and `filed.age`, plus `spec_updated` when the
  workspec has been touched since. Both ship the plain words already ("today",
  "3 weeks ago") — give them, not just the date; a bare date doesn't register as
  stale.
- **TL;DR in the requester's terms**, 2-3 sentences — the problem and what they
  want, not the codebase's framing, which is not what the user recognises. Quote
  the workspec's human block rather than re-deriving one.
- **Parent and sub-item count**, if it has them — an unexpected epic is the
  loudest wrong-id signal there is.

**Say these out loud before asking, whenever they are true:**

- The item's `board` is a **sibling board in the same workspace** — normal under
  a deliberate split, but confirm it is the board you meant; ids interleave
  across boards. A `workspace` different from the resolved one — the
  session-stated workspace when the first message names one, else
  `.claude/maestro.json` — is almost always a wrong id, another repo's board;
  an item on the stated workspace and board is exactly where it belongs,
  never "a different workspace".
- It already has a `## Approach` (or a legacy `## Plan`) — it is scoped, and
  re-scoping overwrites it.
- Its stage is `building`, `review` or `done`, or `values.owner` is someone else
  — live work with a person attached. Name that person: the packet's `people`
  resolves owner ids to names, so "owned by [7]" is never the sentence.
  (`parked` and `rejected` are refused outright, per step 1.)
- You are not authenticated as the filer — `whoami()` is free, make the call.
  Not an error on a shared board, but say whose work it is: "the wrong person
  scoping it" is half of how the wrong item gets scoped.

None is a hard refusal except `parked` and `rejected` — but the user must see
them **before** saying yes, not after the workspec has been rewritten.

Then wait for a clear answer; an ambiguous one is not a yes. If it is the wrong
item, ask for the right id — never go hunting for the item they probably meant.

## Workflow

1. **Pick the item(s).** With item-id arguments, use them — one or several.
   Otherwise call
   `workspace_queue(workspace, stage="inbox")` — it spans **every** board in the
   workspace, where `get_board(board)` sees only the board
   `.claude/maestro.json` names and silently under-reports when work spans two.
   List candidates with **their board name** (id, title, board, priority) and
   ask which to scope — the user may name more than one. Never pick silently.
   Read the reply's `boards` sidecar first: a board whose `unmatched_stages`
   names `inbox` does not carry that stage at all — re-ask it with a value from
   its own `stage_values` rather than reporting it empty. If `workspace_queue`
   is unavailable (older server), fall back to `get_board(board)` and say so.
   **Skip `parked` items**: parking is a deliberate "not now", so a parked item
   is never a candidate unless the user names it outright.
   **Refuse `rejected` items outright**: a rejected stage is a recorded "we
   decided not to do this" (the item's `rejected` record says why). It is not
   scoped, not resumed here — a human reopens it from the board first; say so
   and stop.
2. **Pull, then confirm.** `get_work_packet(item)` → run the wrong-id gate and
   get a yes **before** anything else in this step. Only then write the packet's
   `description` verbatim to `planning/.cache/<item-id>.md` (create
   `planning/.cache/` if absent; make sure it is gitignored — offer to add the
   entry). That file is the session's working copy: edit it, not the item. Read
   the activity trail too — requester comments are scope input, and the
   packet LEADS with `unaddressed_comments` (every human comment nobody has
   answered) precisely so scoping starts from them. They get addressed in
   this session: the step-8 plan-summary comment carries `addresses="all"`,
   recording that the steering shaped the plan.
3. **Context.** The packet already carries the rules the workspec's `Apply
   rules:` line names, inlined under `rules.applied` — apply them; that is the
   full text, not a summary. **Say any `rules.missing` slug out loud**: the
   workspec told you to apply a rule that resolves to nothing, and that is the
   user's to fix, not yours to skip silently. `knowledge.retrieved` is the
   workspace's memory nearest this item — apply it beside `rules.applied`;
   `knowledge.reason` says why it is empty. `skills` names the workspace
   skills this item needs: `skills.pinned` is the full text of each skill the
   workspec's `Apply skills:` line names — apply it like a rule, and say any
   `skills.missing` slug out loud; `skills.retrieved` is up to three more
   nearest the workspec, each with the `why` its own first paragraph gives —
   read each one that fits with
   `list_workspace_docs(workspace, kind="skill", slug=<slug>)`.
   `skills.reason` says why that list is empty. Call
   `get_workspace_context(workspace)` only for a workspec naming no rules at
   all. Read the workspace's `challenge` doc for step 6 with
   `list_workspace_docs(workspace, kind="skill", slug="challenge")`.
4. **Deep exploration.** Read every file the workspec references; check existing
   patterns and helpers in the target app; fetch framework docs when framework
   features are involved. Depth must match a local scoping session — the board
   changes storage, not rigor.

   **Choose the simplest correct approach.**
   - Search the existing implementation, nearby features, and framework helpers
     first. Name what the approach will reuse or extend.
   - Scope only what is needed to satisfy the stated outcome. Exclude
     speculative future requirements and unrelated cleanup.
   - Prefer a direct change using established patterns. Introduce an
     abstraction, dependency, configuration option, or new layer only when a
     concrete requirement needs it; explain why the existing approach is
     insufficient.
   - Keep the approach proportional to the work. A small change should have a
     short plan. Include edge cases, tests, and documentation that matter to the
     actual behavior.
   - Simplicity must preserve correctness, permissions, and required error
     handling.

5. **Design.** Append a `## Approach` section to the scratch file. Write the
   heading line as `## Approach` — it's the form every reader expects first;
   the save guard refuses an item in Planned with no plan it can find.
   - Objective (exact outcome)
   - Ordered implementation steps with file paths
   - Design decisions (why this approach over alternatives)
   - Edge cases and error handling
   - Testing plan (what to add/update)
   - Documentation plan
   - A `### Verification` subsection (see below) — required.
   - An ``Apply skills: `<slug>` `` line under `## Spec`, beside any
     `Apply rules:` line, for each workspace skill the build must read that
     `skills.retrieved` did not name or that is too decisive to leave to
     relevance — a built-in skill is never retrieved, so pin it when the build
     needs it. Name only slugs that land under `skills.pinned`; drop a seeded
     pin that does not fit.

   It must be complete enough to execute without re-exploring. Resolve open
   decisions; don't leave both options.

   **Write it for the build session, not for a reader following your
   reasoning** — it is read once, by a session that must not miss the one
   constraint it contains:
   - **State each fact once.** A constraint in three sections is three places to
     update.
   - **Conclusions, not the investigation.** "`_vector_leg` has no distance
     floor (`knowledge.py:333`)" — not how it was found; a measurement earns its
     place only when the *number* is load-bearing.
   - **Terse bullets carrying `file:line`.** The build session greps them.
   - **Full sentences, though.** Compress by removing repetition and narrative,
     never by abbreviating: a fragment that saves ten tokens and costs one
     misread constraint is a bad trade.

   Two duties on the workspec above the plan, settled at the push in step 8 —
   draft them here:
   - **Convert a legacy-shape workspec** (`# H1` + `## Description` /
     `## Context`, filed before the two-tier template) to the current shape in
     the scratch file: human block distilled from Description and Context,
     everything technical below the `---` under `## Spec`. Scoping is the
     migration path; an item that passes through and stays legacy-shaped never
     gets converted at all.
   - **Refresh the human block** when scoping changed the story — a false
     premise, a different defect than the one filed, scope that moved. A block
     still describing a problem that turned out not to exist is the failure this
     shape exists to prevent.
6. **Challenge — an independent red-team of the draft approach.** The author
   does not grade their own homework. Spawn ONE fresh-context agent (e.g.
   general-purpose, read access to the repo) with the workspec, the draft
   `## Approach`, and the workspace `challenge` skill doc (slug `challenge`, from
   step 3; if the workspace lacks it, brief the agent with its core rules: name
   untested assumptions, argue the strongest opposing case, never invent a flaw
   to perform thoroughness). Its brief: **refute the plan** — the untested
   assumption most likely to be wrong, the strongest failure scenario, the
   weakest design decision. **Challenge unnecessary complexity as well as
   correctness:** what can be removed, what existing code was overlooked, and
   could a smaller change satisfy the same outcome? A hypothetical future need
   is not sufficient reason to expand scope.

   Verify the objections yourself (measure, read,
   re-derive; the challenger may not run code), then give each a disposition in
   a `### Challenge` subsection of the plan — **a table, one row per
   objection**, not a narrative:

       | # | Objection | Disposition | Evidence / what changed |
       |---|-----------|-------------|-------------------------|
       | 1 | <the objection in one line> | **amended** | <what changed in the plan> |
       | 2 | <the objection in one line> | **rebutted** | <the evidence, file:line> |

   `amended` says what changed; `rebutted` carries evidence or reasoning, never
   "considered". "No substantive challenge" is a valid verdict on small items,
   recorded as that one line instead of a table. A plan with an undispositioned
   objection is not ready to present.
7. **Present — lead with a TL;DR**, since the user is running many sessions and
   will not remember what `<item-id>` refers to. Open with a short block, before
   any detail:
   - **What this item is** — the title, plus the original ask in one sentence in
     the requester's terms, not the codebase's.
   - **What scoping changed** — only findings that change the shape of the work:
     a workspec assumption that turned out false, a bug found on the way, an
     overlapping item that already shipped. Omit if nothing moved.
   - **The plan** — 2-4 lines.
   - **Challenged** — what the red-team objected to and what it changed;
     surviving rebuttals the user might overturn go under Decisions to confirm.
     "No substantive challenge" is reportable as-is.
   - **Decisions to confirm** — ones you resolved that the user might reverse;
     name the option you took and why.
   - **Size and verification** — commits, tests, docs touched, plus the
     verification tier and its one-line bound; the user may well overturn the
     tier, and it is far cheaper here than mid-build.

   Roughly 15 lines. The scratch file holds the full plan — link it, don't
   inline it. Then iterate until confirmed.
8. **Push.** Two checks first, in this order — the push replaces the whole
   description, so anything not done by now is gone:
   - **Re-read the human block against the final plan.** An `amended`
     disposition from step 6 can change what the item *is*, leaving the block
     step 5 drafted describing the old understanding. The block that ships must
     match the plan that ships.
   - **Archive a superseded premise before overwriting it.** When the item no
     longer says what it said — a bug that turned out not to be one, a cause
     that turned out to be something else — `comment_on_item(item, <the original
     description, verbatim>)` **first**. The trail records "Description updated"
     but never the old text, so this comment is the only durable copy. The new
     description keeps a ≤3-line summary of the corrected claim so a reader
     knows the record changed; the plan is the authority.

   Then resolve the workflow column's `planned` role and the purpose-marked
   Risk column from the fresh board schema. Assess Risk from migrations,
   contract/security changes, blast radius, unknowns, rollback and verification
   difficulty. On re-scope, record whether evidence preserves or changes the
   prior Risk. Never guess a slug or value; report a missing/incompatible
   semantic column. Push `update_board_item(item, description=<full scratch file contents>,
   values={<resolved planned role>, <resolved risk>}, contract={"tier": …, "run": […],
   "evidence": […]})` — description replaces whole; `contract` carries the same
   verification decision as data (see below) — and
   `comment_on_item(item, <3-5 line plan summary>, addresses="all")` — the
   summary is the reply that ADDRESSES the trail's unaddressed comments
   (step 2 read them as scope input; this records them answered).
   Record scoping's durable findings as knowledge too —
   `upsert_workspace_doc(workspace, kind, slug, title, content)` with kind
   `decision` / `convention` / `fact`, slug-addressed, the reply's `similar`
   checked before each write (a near match means update that slug, not add a
   twin); a premise that turned out false is a `fact`. Not recorded:
   transcripts, file dumps, anything already in the repo's own docs.
   **The push's `values` also carry the milestone stamp** — see "Milestone
   stamp" below — **and, on a horizon-purpose board, the horizon stamp**
   (see "Horizon stamp"); resolve both before this call so stamps and stage
   land in one write.
   **Scoping a PARENT (a Plan) whose sub-items have a build order?** Push the
   roster as data on the same call: `plan={"waves": [[<wave-1 ids>], …],
   "depends": {…}}` (#2905) — waves of active child ids, depends edges
   pointing strictly earlier. That is what the Plan panel renders and what a
   child's work packet warns from; approval stays a separate human decision
   (`approve_board_item_plan` or the portal), never this push.
   **Every edge counts.** A task with depends edges is handed out as soon as
   those tasks are merged, whatever its wave; one with none waits for every
   task of the earlier waves. Give each task an edge to every task whose code
   it uses or whose files it touches, and create the tasks with no Owner — the
   Team's Maestro hands them out. A wave that touches authentication,
   permissions or money gets the line `Security review: wave <N>` in the
   Plan's description, which asks for the reviewer's whole-wave security
   review before that wave closes.
9. Hand off: "run `/maestro-build <item-id>` to build it" — name the item title
   alongside the id; that line is often read back in a later session. Several
   items scoped in this session hand off as one line carrying every id
   (`/maestro-build 431 432 438`, or `/maestro-auto` for the unsupervised
   route), in the build order the cross-check produced.

## Milestone stamp — trajectory upkeep at the push

Milestones only work if the journey writes them: nothing else populates the
trajectory rail, and anything agents don't maintain, dies. When the item's
board carries a milestone column, settle the stamp at the step-8 push, in
this order — first match wins:

- **The item already has one** → keep it. Scoping never re-buckets work.
- **The parent has one** → stamp the same milestone id in the push's
  `values`. The parent Plan's own milestone column value IS the
  Plan↔milestone link — no other registry exists.
- **The parent has a `due` date but no milestone** → the Plan's date wants to
  be a milestone. **Reuse before create**: `list_milestones(workspace)` and
  take an existing row matching the parent's title (or whose `ends` equals
  the due date) if one exists; only then
  `manage_milestone(workspace, "create", name=<parent title>, ends=<parent
  due>)`. Stamp BOTH the parent and the item with it. If the Plan's due date
  and its existing milestone's `ends` disagree, re-date the milestone
  (`manage_milestone(..., "date", ends=<due>)`) — the Plan is the authority.
- **No parent signal** → `list_milestones(workspace)` and ask ONCE, inside
  the step-7 presentation ("which milestone does this land in — or none?"),
  quoting the reply's `no_milestone` count so the human sees the unbucketed
  pile they are adding to. "None" is an acceptable answer; never ask twice.
- **No milestone column on the board, or `manage_milestone` denied** (it
  needs `manage_boards`) → say so in the step-7/9 report and push without.
  **The stamp never blocks a push.**

Two interactive scope sessions can still double-create from one dated Plan
(`create_milestone` has no name idempotency) — accepted: a duplicate is
human-visible and fixable by archive. Under `/maestro-auto` the rule is
inherit-only; that skill says so itself.

## Horizon stamp — same upkeep, dispatch vocabulary

When the item's board carries a category column marked `purpose: "horizon"`
(the schema from the step-2 packet / `get_board` says so), settle the
horizon value at the step-8 push, beside the milestone stamp:

- **The item already has one** → keep it. Scoping never re-buckets work —
  the same rule as milestones.
- **No value yet** → stamp `next` in the push's `values`. A planned item
  sits in the default orbit unless the plan itself surfaced real urgency;
  step 7 asks about the horizon **only** in that case ("this looks like it
  wants `now` — agree?"), never as a routine question.
- Write only values the column defines — a column without `next` gets no
  stamp. Legacy moscow boards get no horizon stamp at all; their moscow
  value is filing's business, untouched here.

**The stamp never blocks a push.**

## Verification Tier — how much testing this change actually needs

**A scoping decision, and it belongs here.** By step 4 you know the change's
blast radius better than the build session ever will — and without a call from
you it defaults to the expensive option.

**Every tier below describes what the *build* will do — scoping itself runs no
tests.** A run in the checkout you scope from contends with any build or
scoping session sharing that checkout; the question it would answer — what is
already red — is answered by the project's last recorded integration-branch run
(`test_status`). Reproducing a bug you are scoping is the one exception: run
that one test, not a suite, and never while a build is running in the same
checkout.

Append a `### Verification` subsection naming exactly one tier:

- **`none`** — a test run would prove nothing. Docs, changelog, comments, skill
  or prose files; or a change verified directly and more convincingly by other
  means — loading the config and reading back the resolved value, running the
  one command the change affects. **No test run, before or after.** The `Why:`
  line must say what stands in for the tests.
- **`targeted`** — the default, where most items land. The behavior change is
  contained inside test modules you can **name**. No baseline run; the build
  runs the named modules after the change. A bug whose cause is still unknown
  is targeted too: its regression test plus the modules around it; the wave's
  run is the net. Name them explicitly — "the relevant tests" is not a plan, it
  is the build session guessing with your authority.
- **`full`** — only three triggers, and the `Why:` line names which: a
  migration or schema change; a shared helper, setting or contract with callers
  across modules; a dependency or framework bump. The build runs the repo's
  default suite **once, after the change** — never before; inside a Plan wave
  that run is the wave's one run after its merges — you take neither. A `full`
  verification tier does not imply the runner's `--full` slow/extended option.

Format:

    ### Verification

    - **Tier:** targeted
    - **Run:** the repo's test command for the `sites` module only
    - **Why:** the change is confined to one renderer service and the module
      that covers it — no migration, no shared helper, no contract another
      module reads.

**Push the same decision as data.** The block above is the human form and
stays. Step 8's `update_board_item` also carries it as `contract={"tier":
"targeted", "run": ["<the commands, verbatim>"], "evidence": ["tests"]}` — one
push, no extra ceremony. A build then reads the tier instead of parsing your
prose, and every later change to it is recorded on the item's trail, so a
downgrade cannot happen quietly.

- **`run`** — the commands, verbatim. Required at `targeted`, where they *are*
  the tier. At `none` and `full` they name riders that run anyway: the bug
  regression test below, or a `full` item's extra check.
- **`evidence`** — what proof this item owes: `tests` / `visual` / `manual` /
  `command`. Suggested vocabulary so items stay comparable, never enforced;
  empty is legal when the runs are the whole story.
- Unknown keys are refused. The contract is three fields until something
  actually reads a fourth — don't invent one.

Pick the **lowest** tier that would actually catch this change breaking. Doubt
between two tiers does **not** resolve upward: name the modules you can bound,
and say in the `Why:` line what they cover and what they leave to the wave's
one full run. A tier with no stated bound is a guess wearing a label. A bug's
regression test runs at every tier, on its own, before and after the fix; that
is targeted by nature and costs seconds.

## Push Failures

Retry once. If it still fails, keep the scratch file and tell the user exactly
which item to sync manually (`planning/.cache/<item-id>.md` →
`update_board_item(<id>, description=...)`). Never lose the plan.

## When an Agent Teammate Runs This

**A teammate session is one where `whoami()`'s `session.persona_agent` is
non-null.** Every other session is interactive and the skill above applies
unchanged — including a brokered owner session in a desktop composer, whose
`authority` reads `agent_session` but whose `session.persona_agent` is null.

As a teammate you have nobody in the room. The work above does not change —
the exploration, the design, the challenge, the verification tier, the push
are the same. What changes is every gate that waits for a person: each one
maps to a team step or stops with its reason. **None is skipped silently.**

| The gate above | As a teammate |
|---|---|
| Board Resolution — ask which workspace, offer to write `.claude/maestro.json` | The ask carried the item; resolve everything else from `get_work_packet(item)`. Never pick a board, never write a repository config file. Maestro unreachable: say so in your reply and stop — there is no local fallback for an item you cannot read. |
| The wrong-id gate — show the card, get a yes | Nobody is there to say yes, so **check** instead of confirm: the packet's title and stage must match what the ask described. A mismatch is refused **by name** ("you asked for #431 'Add preview_site'; #431 is 'Rotate the signing key'") and the turn ends. Never scope the item you think was meant. `parked` and `rejected` still refuse outright. |
| Step 1 — list candidates and ask which to scope | Does not apply. An ask with no item id is refused, not answered with a board pick; say you need an item id and stop. |
| More ids than one ask should carry | One ask, one item. Scope the first, name the others in your reply, and let the asker send them separately. |
| Checkout conflict — show the holder, ask whether to wait | Do not wait and do not take it. Comment who holds it, for what, and until when; end the turn. The asker decides. |
| Step 6 — spawn a fresh sub-agent to refute the draft | **The same: spawn one fresh-context, read-only sub-agent of your own engine** with the same refute brief, in this turn — no waiting on a teammate. It is the one sub-agent this skill allows (see "One hand-off path" below): copy every objection it returns into the `### Challenge` table word for word, so the table is the record. **Whoever wrote the Approach never challenges it**, so an engine with no sub-agents asks `ask_agent(<the Team's builder>)` instead (never the reviewer who will later review the code). Verify every objection yourself before dispositioning it — the `### Challenge` table is still required, and an undispositioned objection still means not ready: never set Planned before it is settled. |
| Step 7 — present the TL;DR and iterate until confirmed | Post the same TL;DR with `comment_on_item`, then end the turn. Do not wait for a reply in the same turn, and never read silence as a yes. |
| The milestone question inside step 7 | Inherit from the parent when it has one (the order above is otherwise unchanged). With no parent signal, stamp nothing, and say in the TL;DR comment that the milestone is unset and who should pick it. Never ask, never guess a bucket. |
| The horizon question inside step 7 | Stamp `next` as above. Real urgency is reported in the comment, never asked. |
| Decisions to confirm | Resolve them, and record the option and the reason under Design decisions. A decision only the person can make — a product choice, a trade-off with their money or their users in it — is one `ask_person` and the turn ends there. |
| "Ask before re-scoping an owned item" | Comment that it is owned (by name) or already `building`, and end the turn. |
| Push Failures — tell the user which item to sync by hand | Retry once, then say the failure in your reply with the plan text, so it is recoverable. You have no scratch file to point at. |

**A Lead with workers** (`whoami()`'s `session.persona_agent.workers` is above
zero). Steps 3–5 — exploration, design and the draft — go to one worker per
item with `delegate`: the item id, the workspec as pulled, the base revision,
and "return the complete description". The checkout stays yours and the
waiting rule below applies unchanged: comment that a worker is drafting, check
it in, end the turn. On the answer, re-acquire, read the draft and any file it
names against the code — the Approach is yours — then run step 6 and every
push yourself. Step 6 is the row above, unchanged, and never goes to a worker:
`delegate` picks the least-busy worker, which is usually the one that just
drafted.

**Running as a worker** (`whoami()`'s `session.persona_agent.parent` is
non-null). Steps 3–5 only, read-only: no checkout, no `update_board_item`, no
comment, no ask, no challenge — every gate in the table is your Lead's. Pull
with `get_work_packet(item)`, apply its rules, and draft the complete
description (human block + `## Spec` + `## Approach` with its
`### Verification`). Write it to `planning/.cache/workers/<request id>.md` in
the folder you started in and answer with the premise check, the plan in a few
lines, files touched, tier, open decisions and that path.

**Push the draft before you challenge.** Steps 5 → 6 → 8 become 5 → **push**
→ 6 → push again. The item is your working copy: a teammate's turn can end
between the draft and the challenge (the challenge is an ask, and an ask can
take a day), and an Approach that exists only in this session's head does not
survive that. Push the draft `## Approach` with `update_board_item` before the
challenge ask, then push the amended plan and the `### Challenge` table after
it. Write no `planning/.cache` file: other agents share the folder you started
in — except a worker's one result file, `planning/.cache/workers/<request id>.md`,
a name no one else writes.

**One hand-off path, one exception.** Every hand-off but the step 6 challenge
is one Maestro teammate, asked with `ask_agent` — or, for a Lead's own
workers, `delegate` — and recorded: the ask and its answer are kept as
requests, a worker's in its private room. The challenge is the exception
because its whole output lands on the item as the `### Challenge` table,
objections word for word, and because a red-team that waits a day for a
teammate is the step that gets skipped. `ask_agent` may refuse for want of a
live acknowledged request (an owner console turn); then say on the item what
is ready and who should do it, and never claim a hand-off you did not make.

**The waiting rule — how a turn ends without stranding the item.** Before you
end a turn on an ask:

1. **Comment who you are waiting on and what for**, on the item, naming the
   teammate or the person and the question.
2. **`check_in_board_item_checkout`.** A lease runs an hour and an ask can
   take a day, so holding it is how an item ends up locked by a session that
   is no longer thinking about it.
3. **End the turn** — no further post, no final text.

On resume: **re-acquire the checkout and re-read `get_work_packet(item)`
before anything else.** The packet is the only state this turn shares with the
last one, and the item may have moved while you waited. The same on every
rework round, however short.

## Rules

- Do NOT implement. Planning and documentation only.
- Never explore, plan or push against an item the user has not confirmed — run
  the wrong-id gate above.
- The challenge exchange (step 6) travels WITH the plan — it is part of the
  workspec pushed to the board, so the build session and the user see what was
  objected to and how it was answered.
- Every summary — the step-7 presentation and any later recap — names the item
  as a markdown link, `[#<id> <title> (<stage>)](<url>)`, taking `url` from the
  tool result (`get_work_packet` and `get_board_item` both return it) rather
  than assembling a host. A
  bare id is not placeable by a user juggling parallel sessions, and in a repo
  with a GitHub remote a bare `#123` is auto-linkified to that repo's issue 123
  — a live link to the wrong system.
- Every endpoint designed must have fail-closed permissions.
- **Never assign `none` to a change that alters runtime behavior with nothing
  named in its place.** The tier decides how the build spends its time; an
  optimistic one spends it on nothing at all.
- Keep repo dumps out of the workspec — reference file paths.
- If the item is already `building` or has an owner, ask before re-scoping.
- Running as an agent teammate: never hand the challenge to a worker, and
  never end a turn on an ask without saying who it waits for and checking the
  checkout in.
