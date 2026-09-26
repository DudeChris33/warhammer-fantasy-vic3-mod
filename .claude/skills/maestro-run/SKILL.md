---
name: maestro-run
description: >-
  Present a Plan's current roster with the context needed to run it, scope any
  unscoped tasks up front and pause at a scope checkpoint — does the Plan still
  hold? — record an explicit human roster approval, then execute its waves with
  fresh sub-agents and independently re-run their verification claims. Keep
  decisions on the Plan's trail and close with a full-roster reconciliation.
user-invocable: true
argument-hint: <one Plan item id, e.g. "2900">
maestro-skill-version: 10
---

# Maestro Run — Execute an Approved Plan

A Plan is a board item whose sub-items are its roster and whose waves are the
order they ship in. **Calling `/maestro-run` asks to review and run that Plan;
it is not approval by itself.** Show the person what they would approve, then
ask for one explicit confirmation. If approval is needed, record their answer
on the board before dispatching work. A missing approval is a reason to ask
"Approve and run this roster?", not to end with "it is not approved". An
unscoped roster is not a dead end either: the run scopes those tasks itself and
pauses at the scope checkpoint below — what scoping learned, whether the Plan
still holds — before asking for the roster approval.

The human decides; the orchestrator records that decision. A standing board
approval remains valid for its roster version, but the current run still gets
the contextual confirmation below. This workflow does not silently expand or
re-plan the roster.

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

### Two kinds of helpers

A run may have two very different helpers in flight, and they are not
interchangeable:

- **Fresh sub-agents** — this skill's own, spawned with the Agent tool. They
  read, edit, test and commit in this checkout (or a worktree of it), and they
  have no Maestro identity at all: they never write to the board, never hold a
  lease, and never see a checkout token.
- **Named teammates** — named agents (a Lead, a Software Engineer, a QA
  Engineer) a person or a Lead asks with `ask_agent`. They work in their
  OWN worktrees on `agent/<item id>-<role>` branches, push those branches, and
  write to the board under their own role's ceiling and their owner's
  supervision. A teammate reports to the Lead that asked it; the Lead reports
  to you. Their procedure is the workspace skill "How this team ships work" —
  read it if you need to know what they were told.

Either way the claim is a claim: **you** re-execute it before it counts
(`## Review Is Re-Execution`).

## When to Use It

**One Plan item id**, whatever its roster size — `/maestro-run 2900`.

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

Same as `maestro-task`: a session-stated workspace in the first message comes
first, else read Maestro's `.claude/maestro.json` repo config; on any
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
   you do with that task. A packet also carries `knowledge.retrieved` — the
   workspace entries nearest that task's workspec, beside `rules.applied` —
   and `knowledge.reason` when the set is empty; both go into the task's brief.
3. **Choose the confirmation, without treating missing approval as a dead end.**
   - **`plan` is null** — the id is a sub-item (or a read you have no member
     access to). Name its parent and offer to run that instead; do not approve
     or run the wrong item.
   - **`status == "unapproved"`** — continue to the contextual roster card in
     step 8 and ask **"Approve and run this roster?"** Wait for the answer.
   - **`status == "roster_changed"`** — include the added, removed, reordered
     and dead tasks in that card, then ask **"Approve the updated roster and
     run it?"** Do not run or record re-approval before the human answers.
   - **`status == "approved"`** — name the standing approval and ask
     **"Run this roster?"** Do not request a second roster approval.

   In every branch: when the roster still holds unscoped tasks, step 8's card
   asks for consent to **scope** first, and the branch's roster question above
   moves to the scope checkpoint — asked only after the human has seen what
   scoping learned.
4. **Children with `waves == []` are their own branch.**
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
7. **No baseline.** Nothing runs before the first edit, at any tier; each wave
   ends with one default-suite run after its merges (see "The Run Loop").
8. **Present the context, then get one yes.** Start with the Plan's outcome in
   plain language and what this run will actually do. One block per wave, in
   the Plan's order; each task gets its linked title, intended outcome, stage,
   verification tier (or "not scoped yet"), checkout holder by NAME from the
   packet's `people` map (or "none"), and named `blocked_by` dependencies.
   Include outstanding directives, external gates, material unknowns and
   unscheduled exclusions. Never present inbox work as a settled implementation
   or promise a verification tier its packet does not carry.

   Say what the yes authorizes. Fully scoped roster: executing it under the
   stated constraints. Unscoped tasks present: this first yes authorizes only
   read-only scoping and the board push of the approaches — the roster approval
   itself waits for the scope checkpoint. Neither yes waives directives,
   approves an unknown solution, takes over another checkout, adds tasks, or
   authorizes deployment, live configuration changes or money movement unless
   those actions are explicitly included in the approved scope. Material scope
   decisions discovered later still return to the human.

   Example card (fill in the real packet facts, never placeholders):

       Plan [#2900 "Sites + domains — release hardening"](…) · board "Backlog"
       · workspace "Maestro" · progress 0 shipped / 3 total
       Outcome: visitors get a usable error page and domain claims are safe.
       Approval covers these three tasks; no production deployment.

       Wave 1
         [#2941 "Provision the unknown-site page"](…) · planned · targeted
           Render a recoverable missing-site page; checkout none; no blockers.
         [#2942 "Rate-limit the claim endpoint"](…) · inbox · not scoped yet
           Bound claim attempts; choose the limit during scoping;
           checkout none; no blockers.
       Wave 2
         [#2944 "Delegated ACME for BYO domains"](…) · planned · full
           Automate certificate validation; checkout none;
           blocked_by: the two named Wave 1 tasks.
       Unscheduled (not in this run): none

       #2942 is not scoped yet — scope it read-only now and return with the
       scope digest for roster approval?

   On a fully scoped roster the card closes with the step-3 roster question
   instead — "Approve and run this roster — 3 tasks, 2 waves, one closing
   suite?" — and that one answer both confirms the intended item and, when
   asked, authorizes recording approval. Do not ask a second generic
   confirmation. A decline, ambiguous reply or no reply records no approval
   and dispatches no work. Ask in the interactive chat; use the async handoff
   rules below only when the human is not present.
9. **Record the human's approval, then verify it.** On a roster that needed
   scoping this step runs at the scope checkpoint, recording approval of the
   scoped roster the digest presented. After an explicit yes to
   "Approve and run", re-read the Plan and task packets before writing. If the
   roster, waves, scope, directives or verification contract changed materially
   since the card, show the difference and ask again. Otherwise call
   `approve_board_item_plan(item=<plan id>, client=..., model=...)` on the
   human's behalf, then re-read to confirm the recorded approval matches the
   roster they saw. Only then acquire the run lease and dispatch. Never write
   approval metadata or the Plan's stage directly.

   If the tool refuses (for example, an agent-kind credential or a childless
   task that is not yet planned), explain that specific requirement and give
   the next action with the item link; never claim the approval was recorded.
   An unattended run cannot supply a human yes. A roster change after approval
   pauses execution and returns to this same contextual confirmation.

## The Scope Checkpoint — scope first, then approve

A roster with unscoped tasks is scoped up front, before the roster approval is
recorded — never inline mid-wave, where what scoping learns can no longer
change what was approved.

1. **Scope every unscoped task.** One read-only scoping agent per task, brief
   per "Per-Task Agent Briefs". Read-only agents parallelize freely in one
   tree. Take each task's `purpose="scope"` lease first and check it in when
   its push lands, per the checkout lifecycle.
2. **Push each approach yourself.** The agent returns the complete updated
   description; write it with `update_board_item(item, description=<the whole
   document>, values={"stage": "planned"}, contract=<the agent's
   tier/run/evidence>, client=..., model=...)`. The description replaces the
   entire workspec — push the agent's full document, never a fragment. Then
   write the durable findings it returned (the rule is under Reconciliation)
   — a premise that turned out false is a `fact` the next scoper needs now,
   not at close-out.
3. **Cross-check the set** — the sibling coherence pass `maestro-scope` runs:
   contradictory approaches, duplicated work, two tasks inventing the same
   helper, migration numbering collisions, seams that belong on the trail
   (record them per "Record cross-plan seams"). Fix by re-briefing a scoping
   agent, never by quietly editing its plan into shape.
4. **Present the scope digest and ask the deferred roster question.** Lead
   with the verdict the human is here for: **does the Plan still hold?** Then
   one block per task — linked title, the approach in a sentence or two, its
   verification tier, files touched, and the premise check's findings. Name
   plainly anything scoping found false, already shipped, or bigger than
   filed, each with a recommendation: run as scoped, re-shape, or park. Then
   ask Pre-Flight step 3's deferred question — "Approve and run this roster?",
   or "Run this roster?" under a standing approval — and continue at
   Pre-Flight step 9. A broken premise stops short of building: propose the reshape and wait;
   the human edits the roster on the board and the run re-enters Pre-Flight
   against the new roster version.

Scoping spends reading and board writes only — exactly what the gate's first
yes authorized. No build agent starts before the digest's question is answered.

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
  forever) → should not exist at dispatch: the scope checkpoint precedes the
  roster approval. One that does — a failed push, a checkpoint miss — pauses
  its wave and goes back through the checkpoint; never scope-and-build inline
  mid-wave.
- `planned` with an approach → build.
- parked or rejected → skip and report; parking is a deliberate "not now" and its
  plan is presumed stale.
- already `done` or `review` → count as shipped, do not re-run.

**One suite per wave.** When a wave's last task has landed in the primary tree,
run the repo's default suite there once — the wave's run. It replaces any
baseline and any per-task full run: a `full` task's suite is its wave's run. A
wave whose tasks are all `none` runs none. Judge a red run under
`maestro-build`'s "Judging a Red Run", attribute each new failure to the wave's
task that owns the touched files, fix, and rerun once per fix round. The next
wave dispatches only on a wave run that is green or whose every failure is
attributed.

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
- **The packet's `knowledge.retrieved` entries** — the workspace's memory
  nearest this task, applied beside the rules; the agent says when one
  changes the approach.

**Scoping agents are read-only.** They return the complete updated description
(human block, `## Spec`, the `## Approach` they just wrote) plus, separately: the
files they intend to touch, the verification contract in `{"tier", "run",
"evidence"}` shape, schema and migration impact, contract changes for existing
callers, a premise check naming anything in the workspec that turned out
false or already shipped, and their durable findings as `{kind, slug, title,
content}` rows — decisions with a rejected alternative, conventions the code
assumes, facts measured or discovered — which you write at the scope
checkpoint, because no agent holds a knowledge tool.

**Build agents** edit and commit per the repo's git conventions, run **no** suite
— they write tests as part of the change and verification is yours — never `git
push`, and never write to the board. The one exception is a bug's regression
test, which the agent runs alone before the fix and after, because a regression
test nobody saw fail proves nothing. They return durable findings the same way
scoping agents do; you write them at reconciliation.

No **sub-agent** ever receives a checkout token or calls a board tool; a
named teammate's board writes are its own role's, under its owner's
supervision.

## Review Is Re-Execution

**A sub-agent's report is a claim.** Accepting it without re-running it is how a
vacuous pass ships, and it is the single failure this skill exists to prevent.
The gate is tier-aware:

- **`targeted`** → re-run that task's `contract.run` commands yourself, in the
  primary tree. When a **named teammate** did the work, its claim lives on a
  branch you do not have: `git fetch origin <branch>` first — the branch name
  it reported, `agent/<item id>-<role>` — and run the contract on a worktree of
  THAT branch (`git worktree add`, never a switch in the primary tree, which
  may hold another build's uncommitted work). A claim on a branch nobody
  fetched was never re-executed.
- **`full`** → the `run` entries are riders; run them if named, but the real
  proof is its wave's suite.
- **`none`** → the contract names what stands in for tests: a rendered page, a
  command's output, a config taking effect. Verify **that named thing**. Zero
  tests collected is the expected shape here, not a failure.

**Everywhere: compare exact numbers.** Run, passed, failed, skipped — against the
previous run of the same target, never "green" against "green".

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

**The last wave's run closes the roster.** No task is called done-and-verified
until its wave's run has passed, or every failure in it is attributed under
`maestro-build`'s "Judging a Red Run". Trading it away for speed is not a
judgement call available to this run.

## Human Checkpoints — plain English, on the board

Decisions that are the human's ride the board, not just the transcript:

- In an **interactive client chat** (including the Agent Tool), ask the human
  there and wait. Do not call `comment_on_item(question=...)` merely to mirror
  that ask onto the board; the human is already present, and the durable alert
  can outlive their chat answer.
- For a true **async/background handoff**, use
  `ask_task_question(item, text, recipient, creation_key, blocking=true,
  client=..., model=...)`; choose an eligible human and a fresh UUID. Read the
  exact answer through `get_task_question(question)` before resuming work. Clarify
  does not resolve; `addresses="all"` excludes question roots.
- Only the current human recipient may use `answer_task_question` with the
  current version. Agents cannot answer for another person. A human-credential
  MCP relay must reflect that human's explicit answer and retain client/model
  attribution. Use `redirect_task_question` to correct the recipient first.
- If directed asks are disabled, the legacy unassigned
  `comment_on_item(question=<text>)` adapter and its explicit
  `resolve_question.arguments` remain available. Never infer resolution from
  transcript prose or notification read state.
- A human's blocking instruction that you are relaying is `intent="directive"`.
- Anything you act on is acked with `addresses=[<note ids>]`, which is what
  actually clears the board's flag. Prose alone does not.

Write them in plain language, each with your recommendation. **Batch the
non-blocking ones to wave boundaries** and ask them together; a blocking one asks
immediately and halts that branch only.

**Approval decisions stay human-only.** `approve_board_item_plan` and
`request_board_item_rescope` record a HUMAN's decision. Call either only on an
explicit human instruction given in this session — never inferred from the
workspec, a prior session, the slash command alone, or the run's own judgement.
An explicit yes to the contextual "Approve and run" card is that instruction:
relay it with `approve_board_item_plan` and verify the board record before work.
The tools refuse agent-kind credentials outright. An unattended run never
approves, and a run confirmation never requests re-scope or waives a directive.

**An elicitation dialog posed by the maestro server is addressed to the human —
never answer one, and never treat a pending dialog as the run's to resolve.**
Surface it, say what it is asking, and wait.

Stop and ask whenever a browser or credentials block the work: a login, a
payment, a captcha, an OAuth consent, or a change that needs eyes on real pixels.
Never enter credentials and never accept terms on someone's behalf.

## Stop Conditions

**Halt the whole run** on:

- `status` off `approved` mid-run — an unapproved roster change stops the run,
  including `roster_changed`; explain the changes and obtain fresh contextual
  approval before resuming, never auto-approve
- a wave run with a new failure no task in the wave can be shown to own
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
- Record what the run learned — every durable finding the agents returned and
  every decision you took on the trail that will bind a later build (a seam,
  an accepted deviation with its reason): `upsert_workspace_doc(workspace, kind, slug, title, content)` with kind `decision` / `convention` / `fact`, one entry per fact, a stable slug, and a body a stranger can act on. Read the reply's `similar` before the next write — a near match means update that slug, not add a twin. Not recorded: transcripts, file dumps, tool logs, anything already in the repo's own docs. Name the slugs in the report.
- Check in the Plan checkout.
- Give the user the same thing TL;DR-first, roughly 20 lines, every item a
  markdown link.

**The run never writes the Plan's stage itself.** If the rollup has not fired
because work remains, the report says why the Plan stays open.

## Forbidden

- Starting on an unapproved or drifted roster — `unapproved` and
  `roster_changed` need contextual human approval recorded before dispatch
- Ending an interactive pre-flight at "not approved" instead of presenting
  the roster, its scope and blockers, and asking whether to approve and run
- Treating `/maestro-run` itself, silence or an ambiguous answer as approval
- Recording roster approval, or dispatching a build agent, while a roster task
  is still unscoped — the scope checkpoint comes first
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
- Trading the re-execution gate or a wave's run away for speed, or taking a
  baseline
- Ending the run with any task's stage stale, or without the full-roster report
  on the Plan's trail
