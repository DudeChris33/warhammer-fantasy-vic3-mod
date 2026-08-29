---
name: maestro-run
description: >-
  Execute an approved Plan's roster end to end in one orchestrating session:
  verify the board-recorded roster approval, run the waves in the Plan's own
  order, hand each task to a fresh sub-agent, re-run every verification claim
  instead of believing it, put the human's decisions on the Plan's trail in
  plain English, and close with a full-roster reconciliation. The roster was
  approved on the board before this run started, so the run executes rather
  than proposes.
user-invocable: true
argument-hint: <one approved Plan item id, e.g. "2900">
maestro-skill-version: 2
---

# Maestro Run — Execute an Approved Plan

A Plan is a board item whose sub-items are its roster and whose waves are the
order they ship in. A human already recorded their approval of that roster
against a version of it, and **that record — not a yes in this chat — is the
entry gate**. So this run executes: it does not propose the work, re-plan it,
or approve anything.

You are the orchestrator, not the builder:

- **Sub-agents touch code.** Scoping, red-teaming and building each run in a
  fresh-context sub-agent. They read, plan, edit, test and commit; they never
  write to the board and never hold a lease.
- **You own the board, the leases and every decision.** Every
  `update_board_item`, `comment_on_item`, stage flip, checkout and question goes
  through you, so a sub-agent that dies mid-task never leaves a half-updated
  board.
- **You verify by re-executing.** A sub-agent's test result is a claim, not
  evidence. Re-running it is the whole point of the orchestrator existing.

## When to Use It

**One approved Plan item id**, whatever its roster size — `/maestro-run 2900`.

- **`/maestro-auto`** for flat filed items that have no Plan: it scopes them,
  builds them, and creates its own in-session approval gate along the way.
- **`/maestro-scope` + `/maestro-build`** when the plan should be read before it
  is pushed to the item, or the build steered as it happens.
- **`/maestro-vibe`** for work too small to track.

A childless Plan (`progress.total == 0`) is the plan-of-one: legal, approvable,
and run as a single task — the Plan item itself.

Given several ids, ask which one is the Plan; this skill takes exactly one.
Given a roster task's id instead of the Plan's, name the parent and offer to run
that.

## Board Resolution

Same as `maestro-task`: read Maestro's `.claude/maestro.json` repo config; on any
miss, resolve via `whoami()` / `list_workspaces()` / `list_boards()`, ask, offer
to write the file. Maestro unreachable or unauthenticated → stop with an explicit
notice; never fall back silently. This run cannot read a roster approval it
cannot reach, and one that assumes an approval it never saw is exactly the
failure the gate exists to prevent. Call `get_board(board, items=False)` once and
keep the column schema; match stage options **by value**.

Also from `maestro-task` — **step 5: name boards and items when you report them,
never bare ids.** `board "Backlog" (Maestro workspace, id 8)`, `#586 "An agent
cannot see what it deployed"`, with the item URL (format below); that lookup is
far cheaper for you than for the user.

**Step 7: pass `client=` (the client you are running in) and `model=` (your model
id) on every `update_board_item`, `comment_on_item` and checkout call.** The
server cannot observe either — a write that omits them lands in the trail under
the default label, "via Claude", whoever wrote it.

## Naming an Item

Name the Plan and every roster task to the user — the gate card, checkpoints,
the final report — as a markdown link, never a bare id:

```
[#<id> <title> (<stage>)](<url>)
```

`url` comes from the tool result: `get_work_packet` and `get_board_item` return
one; `get_board` returns an `item_url_template` with `{id}` to substitute. Never
hand-assemble a host. In a repo with a GitHub remote the client auto-linkifies a
bare `#123` to that repo's issue 123 — a live link to the wrong system.

## Pre-Flight — the approval gate

1. **Read the Plan.** `get_work_packet(<plan id>)`. Its `plan` key carries the
   whole steering picture: `approval` (who approved which roster version, when),
   `status`, `waves` (each with its ordered `tasks`), `unscheduled`, `progress`
   (`shipped` / `total` / `parked` / `rejected`), `roster_drift` and `mismatch`.
2. **Read every roster task.** One `get_work_packet` per task, before the gate.
   The Plan payload is enough to sequence a run and not enough to execute one: a
   task row carries `{id, title, stage, checkout, blocked_by}` and nothing else —
   no verification tier, no run commands, no rules, no unaddressed comments.
   Those live only on the task's own packet, and every one of them changes what
   you do with that task.
3. **Refuse and stop** when any of these hold. None of them is a warning:
   - **`plan` is null** — the id is a sub-item (or a read you have no member
     access to). Name its parent and offer to run that instead.
   - **`status == "unapproved"`** — nobody approved this roster. The run never
     approves it; say what is missing and stop.
   - **`status == "roster_changed"`** — the roster moved after approval. Print
     `roster_drift.added` / `removed` / `reordered` / `dead` and stop. Re-approval
     is a human act on the board, not something to work around.
4. **`status == "approved"` with children and `waves == []` is its own branch.**
   A Plan can be approved with no waves record: the snapshot stores `waves: []`,
   every child lands in `unscheduled`, and "run the waves" would ship nothing
   while reporting success. Ask the human which they want — run `unscheduled` as
   one implicit wave (sequenced by shared files, per the Run Loop), or stop so
   waves can be written. Never pick silently.
5. **Say these out loud, without stopping:**
   - `roster_drift.dead` ids at `approved` status — the approval snapshot names
     children since archived or re-parented. Run the live roster; report the dead
     ids rather than dropping them silently.
   - `mismatch` entries (`done_with_open_children` / `open_with_children_done`) —
     the Plan and its children already disagree before you start.
   - `unscheduled` tasks — active children in no wave. **They are not part of
     this run** unless step 4's decision just made them one, and they are listed
     again at reconciliation.
   - `plan.progress` — record it verbatim as the run's **opening scoreboard**.
     Every number in the closing report is measured against it.
6. **Address the steering first.** Work the PLAN's `unaddressed_comments` before
   anything else: `comment_on_item(<plan>, <the answer>, addresses=[<note ids>])`
   (or `addresses="all"`). This is not politeness. A `directive` left standing on
   the Plan makes the server's own parent rollup refuse, and that refusal
   surfaces as an error on the **last task's** stage write — the run fails at its
   final step, not at close-out. Per-task unaddressed directives are addressed
   before that task dispatches.
7. **Decide the baseline now.** From the per-task packets, note whether any
   task's `contract.tier` is `full`. That is the only thing that triggers a
   run-level baseline, and the Run Loop takes it before the first edit.
8. **Present the roster card and get one yes.** One block per wave, in the Plan's
   order:

       Plan [#2900 "Sites + domains — release hardening"](…) · board "Backlog"
       · workspace "Maestro" · roster approved by Ian Starnes 2026-08-20
       (version 3) · progress 1 shipped / 6 total

       Wave 1
         [#2941 "Provision the unknown-site page"](…) · planned · targeted
         [#2942 "Rate-limit the claim endpoint"](…) · inbox · not scoped yet
       Wave 2
         [#2944 "Delegated ACME for BYO domains"](…) · planned · full
           blocked_by: #2941, #2942
       Unscheduled (not in this run): [#2951 "Cert expiry alerts"](…)

       Run this roster — 6 tasks, 2 waves, one closing suite at the end?

   Every task gets its link, stage, `checkout` holder (by NAME, from the packet's
   `people` map) and `blocked_by`. **That yes is the wrong-id confirm, not an
   approval** — approval already exists on the board, and this ask exists because
   an id is not self-describing. Wait for a clear answer; an ambiguous one is not
   a yes.

## Checkout lifecycle

The orchestrator — not any sub-agent — owns every checkout token.

Take one lease on the **PLAN item** for the whole run:
`acquire_board_item_checkout(<plan>, purpose="build", idempotency_key=<fresh
high-entropy key>, expected_minutes=…)`. `purpose` accepts only `"scope"` or
`"build"`; there is no `"run"`, and `build` is the honest one for a session that
is shipping code. Then take a per-task lease before that task's scope or build,
and check it in on its terminal path — the stage write, the blocker comment, a
cancellation, a dropped task. Use a fresh high-entropy idempotency key per
acquisition generation.

Renew every lease no later than 40 minutes after the acquire or last renewal,
immediately before and after long waits and commands, and before accepting a
sub-agent's result. Keep waits short enough to heartbeat.

A checkout is advisory. If an acquire reports a conflict, show the human the
holder, purpose and expiry and ask whether to wait or continue; continuing
**without a checkout** is allowed once they say so, and a task whose row already
shows another holder gets that same decision before it dispatches, even though
the roster was approved. What is never allowed is pretending: lost, expired or
replaced ownership is reported as gone, not as still held.

Never pass a checkout token to ordinary board writes. It is a bearer capability,
visible in the owning MCP transcript by design and nowhere else: never copy it
into a workspec, comment, log, URL, realtime message, durable browser storage, or
a sub-agent's prompt. Every post-acquire sub-agent starts in fresh isolated
context and receives the workspec, never the raw token or the owning transcript.

After every acquire, re-read the packet and latest comments before starting. A
material title, stage, description or contract change since the gate needs
reconfirmation.

## Live Progress on the Plan

The Plan lease is how mission control watches this run. `renew_board_item_checkout`
carries the report and writes no trail note, so one round trip both heartbeats
and reports:

- **`activity`** is the live sentence — "wave 2 of 3 — building #2941",
  "re-running the closing suite", "blocked: waiting on a human answer".
- **`criteria` + `criteria_count`** tick the PLAN workspec's
  `### Acceptance Criteria` ordinals as tasks land. Send them **only when the
  Plan's workspec actually has that checkbox list**. The list is a filing
  convention, not a server guarantee, and `criteria_count` must be at least 1 —
  on a Plan without one, send `activity` alone.

**A rejected report rejects the renewal with it.** Criteria ticked against a Plan
that has no criteria list do not degrade to an activity-only check-in; the whole
call fails and the heartbeat is silently lost. On any check-in error, re-renew
bare immediately, then fix the payload.

After a reacquire the report starts empty, so the first check-in of the new
generation re-posts the full current state rather than a delta.

Check in at wave boundaries, at each dispatch and return, and on every blocker —
still never more than 40 minutes apart. Task-level progress needs no extra
writes: mission control reads each task's stage straight out of the Plan payload.

## The Run Loop

**Wave order is the Plan's, not yours.** Before each wave, re-read
`get_work_packet(<plan id>)`: a `status` that is no longer `approved` stops the
run (see "Stop Conditions"). A task whose `blocked_by` is non-empty does not
dispatch.

Two asymmetric traps in the server's own derivation. Neither is a bug; both read
as green and are not:

- **`blocked_by` empty is not "prerequisites delivered".** Parked and rejected
  both count as finished, so a parked wave-1 task unblocks wave 2 while its
  foundation is missing. That is a human checkpoint, not a green light.
- **`review` is not finished.** A prerequisite that landed at `review` — the PR
  path — blocks its dependents server-side and keeps blocking them until somebody
  merges it. When a wave stalls on a `review`-stage prerequisite, surface it as a
  named checkpoint (merge it, accept it, or re-sequence) rather than waiting for
  a state that will not arrive on its own.

The run's own shipped count is therefore not `progress.shipped`, which counts
`done` only. Reconcile the difference explicitly rather than quoting one as the
other.

**Within a wave, sequence by shared files.** Two tasks whose plans touch the same
file, or migrate the same app, run in order. The rest parallelize only where the
repo's own rules say a checkout is isolated — its own test database, port and
cache namespace. Verify that against the repo's rules; do not infer it from the
existence of worktrees.

**Route each task from its own packet:**

- `inbox` with no `## Approach` (nor the legacy `## Plan` heading, which is read
  forever) → a read-only scoping agent first, then a build agent.
- `planned` with an approach → build.
- parked or rejected → skip and report; parking is a deliberate "not now" and its
  plan is presumed stale.
- already `done` or `review` → count as shipped, do not re-run.

**Baseline before the first edit.** If any task's `contract.tier` is `full` —
known since Pre-Flight — take the repo's green baseline once, for the whole run,
before the first build agent starts. A red baseline stops the run; never build a
roster on red. Below `full` there is no baseline at all.

**Record cross-plan seams before the builds that consume them.** Where two roster
tasks share a contract, helper, file or migration, post the seam on each task's
trail with `comment_on_item` naming the other item and the shape both sides must
honor, then hand those note ids to both briefs. A seam agreed in your head and
not on the trail is a seam the second agent never sees.

## Per-Task Agent Briefs

Every brief carries, without exception:

- **The item id and its work packet** — the workspec, its rules, its contract.
- **The binding trail note ids** it must honor, quoted by id: seams recorded
  above, human directives, deviations already accepted in this run. "Honor the
  trail" is not a brief; the ids are.
- **The as-built shapes of roster siblings already landed in this run** — actual
  names and signatures as built, not as planned. The plan is what was intended;
  the agent has to compile against what exists.
- **The repo's Maestro workflow** — its own rules files, git conventions, test
  commands and doc tracks.
- **That task's verification contract**, tier and named runs included.

**Scoping agents are read-only.** They return the complete updated description
(human block, `## Spec`, the `## Approach` they just wrote) plus, separately: the
files they intend to touch, the verification contract in `{"tier", "run",
"evidence"}` shape, schema and migration impact, contract changes for existing
callers, and a premise check naming anything in the workspec that turned out
false or already shipped.

**Build agents** edit and commit per the repo's git conventions, run **no** suite
— they write tests as part of the change and verification is yours — never `git
push`, and never write to the board. The one exception is a bug's regression
test, which the agent runs alone before the fix and after, because a regression
test nobody saw fail proves nothing.

No agent ever receives a checkout token, and no agent ever calls a board tool.

## Review Is Re-Execution

**A sub-agent's report is a claim.** Accepting it without re-running it is how a
vacuous pass ships, and it is the single failure this skill exists to prevent.
The gate is tier-aware:

- **`targeted`** → re-run that task's `contract.run` commands yourself, in the
  primary tree.
- **`full`** → the `run` entries are riders; run them if named, but the real
  proof is the run-level closing suite below.
- **`none`** → the contract names what stands in for tests: a rendered page, a
  command's output, a config taking effect. Verify **that named thing**. Zero
  tests collected is the expected shape here, not a failure.

**Everywhere: compare exact numbers.** Run, passed, failed, skipped — against the
baseline or the previous run, never "green" against "green".

Treat as a FAIL, at any tier that claims tests:

- a run that collected zero tests
- a target that matched no module
- a file collected but wholly skipped
- a count that did not move when the change claimed to add tests
- any "passed" whose output contains an import error or an early exit

**Verify the record too**, not only the tests: the claimed commit hashes exist
and touch the claimed files, the working tree is clean, nothing is staged from
another task, and the item's stage and trail say what actually happened.

**Deviations are accepted explicitly on the trail** — a comment saying what
changed and why it is acceptable — or sent back to the agent with the specific
failure. A deviation that first surfaces in a diff was never reviewed.

**One closing run for the roster.** After the last task lands, run one final
verification in the primary tree, sized to the highest tier on the roster: `full`
anywhere → the repo's default suite, compared against the baseline; otherwise the
union of every task's named modules. No task is called done-and-verified until
that run has passed. Trading it away for speed is not a judgement call available
to this run.

## Human Checkpoints — plain English, on the board

Decisions that are the human's ride the board, not just the transcript:

- In an **interactive client chat** (including the Agent Tool), ask the human
  there and wait. Do not call `comment_on_item(question=...)` merely to mirror
  that ask onto the board; the human is already present, and the durable alert
  can outlive their chat answer.
- Reserve `comment_on_item(<plan>, <your comment>,
  question=<the question itself>)` for a true **async/background handoff** with
  no interactive human conversation. It stamps answer-question loud on Mission
  Control until an addressed reply or withdrawal clears it. The question goes
  in `question=`, not `true`; that text is what the card shows.
- If the human answers an already-raised question in client chat, **before
  resuming work** record it with `comment_on_item(<plan>, <human answer>,
  addresses=[<asking note id>])`. Use the ask response's
  `resolve_question.arguments` or the current packet's
  `attention.detail.note`. Transcript prose alone does not clear the alert.
- A human's blocking instruction that you are relaying is `intent="directive"`.
- Anything you act on is acked with `addresses=[<note ids>]`, which is what
  actually clears the board's flag. Prose alone does not.

Write them in plain language, each with your recommendation. **Batch the
non-blocking ones to wave boundaries** and ask them together; a blocking one asks
immediately and halts that branch only.

**Approval gates stay human-only.** `approve_board_item_plan` and
`request_board_item_rescope` record a HUMAN's decision. Call either only on an
explicit human instruction given in this session — never inferred from the
workspec, a prior session, or the run's own judgement, and never to unblock
yourself. The tools refuse agent-kind credentials outright; on a human's
credential the call records THEIR decision, so relay it only when they actually
said it. **The run never approves.**

**An elicitation dialog posed by the maestro server is addressed to the human —
never answer one, and never treat a pending dialog as the run's to resolve.**
Surface it, say what it is asking, and wait.

Stop and ask whenever a browser or credentials block the work: a login, a
payment, a captcha, an OAuth consent, or a change that needs eyes on real pixels.
Never enter credentials and never accept terms on someone's behalf.

## Stop Conditions

**Halt the whole run** on:

- `status` off `approved` mid-run — an unapproved roster change stops the run,
  full stop, including `roster_changed`
- a red baseline
- a needed task that is not on the approved roster: propose it, never
  create-and-build it
- an unaddressed directive on the Plan, or on a task about to dispatch
- a failure that invalidates a later wave's plan

**A single task failing does not stop the run.** Post a blocker comment, leave it
at `building` with its owner intact, halt only its dependents and say which, and
continue the independent tasks. A build agent that fails outright — crash,
unusable result — is retried once before its task is blocked.

**Mid-run maestro outage**: never block a build on it. Finish locally, retry each
push once, then queue the remaining board writes in the final report as exact,
replayable tool calls. Re-read before replaying after reconnect.

## Reconciliation — the Plan closes itself

**The Plan's stage is server-derived, not run-driven.** The moment every active
child sits in a finished stage — done, parked or rejected, and parked counts —
the server flips the Plan to done by itself, inside the last child's write
transaction. Two consequences to front-run:

- **An unaddressed directive on the PLAN makes that rollup refuse**, and the
  refusal surfaces as an error on the **last task's** stage write, naming the
  Plan's blocking notes. So every Plan directive is addressed before the final
  task flips, not at close-out. This is why Pre-Flight step 6 comes first.
- **A roster finishing {done, done, parked} auto-closes the Plan anyway**, with
  undelivered work inside it. Say so in the report rather than letting a `done`
  Plan stand as "all shipped".

Before calling the run complete, re-read `get_work_packet(<plan id>)` and walk
the **full** roster, `unscheduled` included. One line per task: the link, what
shipped, its stage now, the verification result **with the real numbers**, and
any deviation accepted. Then:

- Compare `progress` against the run's opening scoreboard, naming the parked and
  `review` gap explicitly — `progress.shipped` counts `done` only.
- Name every task that is not `done` and what it needs.
- Post that full-roster report as a `comment_on_item` on the **Plan item's
  trail** — that is the durable record, not this transcript.
- Check in the Plan checkout.
- Give the user the same thing TL;DR-first, roughly 20 lines, every item a
  markdown link.

**The run never writes the Plan's stage itself.** If the rollup has not fired
because work remains, the report says why the Plan stays open.

## Forbidden

- Starting on an unapproved or drifted roster — `unapproved` and
  `roster_changed` are refusals, not warnings
- Running an approved-but-unwaved roster without the human choosing that
- Approving a plan or requesting a re-scope without an explicit human instruction
  given in this session
- Answering an elicitation dialog addressed to the human
- Dispatching a task whose prerequisites are unfinished, or treating an empty
  `blocked_by` behind a parked prerequisite as a green light
- Accepting a sub-agent's test result without re-running it, or reporting a
  claimed pass as verified fact
- Letting a sub-agent write to the board, hold a checkout token, or push
- Creating roster tasks mid-run
- Writing the Plan's stage by hand
- Concurrent builds where the repo does not isolate checkouts
- Trading the re-execution gate or the closing run away for speed
- Ending the run with any task's stage stale, or without the full-roster report
  on the Plan's trail
