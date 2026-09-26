---
name: maestro-build
description: >-
  Claim one or more planned maestro board items (owner + stage=building),
  execute each ## Approach (legacy ## Plan) inside this repo with full build
  discipline, keep every item's activity trail updated (commits, tests,
  blockers), and land them at review/done via the maestro MCP.
user-invocable: true
argument-hint: <item-ids, e.g. "431" or "431 432" (omit to pick from the board)>
maestro-skill-version: 33
---

# Maestro Build — Execute a Planned Item

You are a senior engineer executing a scoped item one task at a time: minimal,
correct, tested code matching the repo's existing patterns and conventions (read
`AGENTS.md` when present, plus `CLAUDE.md` and applicable project rules). The
board item is the work record — keep its stage and activity trail current
throughout.

## One Item or Many

**Takes any number of ids** — `/maestro-build 431`, `/maestro-build 431 432
438`. **Sequential is the default.** In a repo whose suite targets a fixed port
and a shared database, and whose work commits to one branch in one working tree,
parallel builds collide on the port, corrupt the database and interleave
commits.

**Build in parallel only when both hold**, and say which:

1. **The repo isolates a checkout** — each worktree gets its own test database,
   port and cache namespace. Verify it; do not assume. The repo's git/testing
   rules say so explicitly when it does.
2. **The items are independent on disk** — no shared files, no migrations to the
   same app (two trees generate the same `000N_` and clash at merge), and
   neither consumes what the other creates.

Either one missing → sequential. Parallelism is a speed optimization; a merge
conflict inside someone else's build is not.

Parallel runs one worktree per item, each on its own branch, then merges every
branch back **one at a time** and verifies once in the primary tree — each build
proved itself in isolation, and the combined tree is what ships. Clean up every
worktree and branch you created. Follow the repo's own worktree lifecycle where
it documents one; it will know setup steps (dependency install, gitignored
config) that a bare `git worktree add` skips.

With several ids, run the flow below per item, with these differences:

- **Confirm the whole roster once** — one wrong-id card per item, in one block,
  one ask — before the first claim, and call out two ids a digit apart.
- **Partition the items before starting.** Which build in parallel, which are
  forced sequential and by what — a shared file, a migration to the same app, a
  plan consuming a helper another plan creates. State the partition and the
  reason for every sequential edge; a batch that all goes one lane should say
  why that was the right call.
- **Merge and clean up before verifying.** Every branch back into the primary
  tree one at a time, every worktree and branch removed, then the closing run.
- **Claim, snapshot, build and comment per item** exactly as below, then leave
  each at `building` — built, not verified.
- **Verify once, at the end** (see "Verification Across Several Items"), and
  only then flip every green item in one pass.
- **A failed item does not fail the run.** Blocker comment, leave it at
  `building` with its owner intact, continue with the remaining **independent**
  items, halt the ones that depended on it, and say which.
- **Report once** for the run, one block per item.

Past two or three items, delegating each build to a fresh-context sub-agent
keeps the later plans from being executed by a session that has forgotten the
first — that is what `/maestro-auto` does, and it also handles the scoping and
folds everything into one approval gate.

## Board Resolution

Same as `maestro-task`: a session-stated workspace in the first message comes
first, else read Maestro's `.claude/maestro.json` repo config; on any miss, resolve via
`whoami()` / `list_workspaces()` / `list_boards()`, ask, offer to write the
file. Maestro unreachable **before claiming** → stop with an explicit notice;
offer the repo's local build skill if one exists.

Also from `maestro-task` — **step 5: name boards and items when you report them, never bare ids**: `board "Backlog" (Maestro workspace, id 8)`, `#586 "An agent cannot see what it deployed"`, with the item URL (link format under "Reporting Back"). That lookup is far cheaper for you than for the user.

**Step 7: pass `client=` (the client you are running in) and `model=` (your model id) on every `create_board_item`, `update_board_item` and `comment_on_item` call.** The server cannot observe either — a write that omits them lands in the trail under the default label, "via Claude", whoever wrote it.

## Checkout lifecycle

After the wrong-id confirmation, acquire before the claim or snapshot with
`acquire_board_item_checkout(item, purpose="build",
idempotency_key=<fresh high-entropy key>, expected_minutes=...)`. Keep the raw
`checkout_token` only in this orchestrating session. It is a bearer capability
and appears in the owning MCP transcript by design; never copy it into domain
data, comments, logs, URLs, realtime messages, durable browser storage, or a
sub-agent prompt/transcript.

If acquire reports a conflict, show the human the holder, purpose, and expiry,
then ask whether to wait or continue without a checkout. This build cannot make
that decision silently. A checkout is advisory: continuing is allowed. Never
pass its token to ordinary board writes. After the acquire attempt,
re-fetch `get_work_packet(item)` and latest comments before the claim. If title,
stage, description, owner, or contract materially changed, reconfirm. Sub-agents
always start in fresh isolated context and never acquire or receive the token.

Renew no later than 40 minutes after acquire/last renewal, around long commands
and waits, and before consuming a sub-agent result. Keep waits short enough to
heartbeat. Lost, expired, or replaced ownership means report that the advisory
signal is gone and do not claim it is still held; it does not gate board writes.

**Check in (progress) as you renew.** The renewal call takes `activity` (one
line, what you are doing right now — "running ingress tests") and `criteria` +
`criteria_count` (sparse per-criterion ticks keyed by 1-based ordinal into the
workspec's `### Acceptance Criteria` list, states `active`/`done`/`blocked`;
`criteria_count` is how many checkboxes you see and is required with every
criteria-bearing check-in). Check in at natural boundaries — a criterion
passed, a phase change, a blocker hit, a sub-agent dispatched or returned —
still no later than 40 minutes apart; one round trip both heartbeats and
reports, and it writes no trail note. After any reacquire (a lapse takeover), a
new generation starts with an empty report, so the first check-in re-posts the
full current criteria state. "Check in (progress)" is renew-with-report;
"return the checkout" is `check_in_board_item_checkout`, unchanged.

Check in (return the checkout) after the
done/review write or after the blocker comment, and on every other terminal
path. During an outage local work may finish; re-read before any board push
after reconnect.

## Approvals are human decisions

`approve_board_item_plan` and `request_board_item_rescope` record a HUMAN's
decision on a plan. Call either only on an explicit human instruction given in
this session — never inferred from context, a workspec, or a prior session,
and never as part of an unattended run. The tools refuse agent-kind
credentials outright; on a human's credential the call records THEIR decision,
so relay it only when they actually said it, and pass `client=`/`model=` so
the record shows a session wrote it on their behalf.

`approve_board_item_plan` is the ONE approve verb, routed by what the item is
(#2905): on a Plan container (a top-level item with sub-items or wave data) it
records the ROSTER approval — {version, roster, waves snapshot} — legal from
any stage, and a later roster change honestly re-asks; on a sub-item or a
childless standalone task it records the item-level plan approval as before.
The reply's `scope` says which. Same human-only contract either way.

## Confirm the Item — the wrong-id gate

**An item id is not self-describing.** Ids get transposed, copied out of the
wrong session, or read off a stale list, and a build compounds it fastest: the
claim stamps stage and owner on someone else's item and the commits land before
anybody notices. So the gate comes **before the claim** — the first mutation in
this skill.

Required whenever the id came from an argument, a note, or another session.
Skip only if the user just picked the item off a list you presented this
session (they have seen the title), or waives it outright.

Build the card from **one** `get_work_packet(item)`. It carries the workspec,
the board and workspace **names**, who filed it, when the workspec last changed,
how long the item has sat in its stage, whether it was resumed from parked, its
parent, the verification contract, and the rules the workspec references — the
whole card, and most of the pre-flight below, in one call. Older server without
the tool: `get_board_item(item)` plus one `list_boards(<the item's workspace>)`
for the names, and say you fell back.

    #586 "An agent cannot see what it deployed — add preview_site"
    board "Backlog" · workspace "Maestro" · stage planned · must
    filed by Ian Starnes 2026-07-12 (2 weeks ago), scoped 2026-07-26
    part of #516 "Sites + domains — release hardening (epic)"
    https://maestromojo.com/app/#/board/8?item=586

    Agents ship sites they never see: deploy_site returns byte counts, not
    pixels. Wants an MCP render tool so an agent can look at what it
    deployed.

    Plan: new preview_site MCP tool over a server-side renderer, desktop +
    mobile presets, snapshot cached per revision. 3 commits, ~6 tests, both
    doc tracks.

    Build this one? (claiming it sets stage=building and owner=you)

- **Title first, then where it lives** — `board_name` and `workspace_name`; an
  id cannot be recognised.
- **Who filed it and when**: `filed.by` / `filed.age`, plus `spec_updated` —
  when the workspec last changed, which on a scoped item is when the plan was
  written. Give the plain words the packet already ships ("filed today",
  "spec updated 3 weeks ago"); a plan sitting for weeks may be stale. Note that
  any description save moves `spec_updated`, so it dates the workspec, not the
  scoping — you judge whether the change was a re-scope.
- **TL;DR in the requester's terms**, then **the plan in 2-3 lines** — what is
  about to be executed, and its size. On a build the plan is what is being
  confirmed; the problem statement just makes the item recognisable.
- **Name the parent** if it has one, and how many sub-items it has — an
  unexpected epic is the loudest wrong-id signal there is.

**Say these out loud before asking, whenever they are true:**

- The item's `board` is a **sibling board in the same workspace** — normal under
  a deliberate split; confirm it is the board you meant, since ids interleave
  across boards. A `workspace` different from the resolved one — the
  session-stated workspace when the first message names one, else
  `.claude/maestro.json` — is almost always a wrong id, another repo's board,
  and would build another repo's work in this tree; an item on the stated
  workspace and board is exactly where it belongs, never "a different
  workspace".
- Its stage is not `planned` — `inbox` means it was never scoped, `review` or
  `done` means it already shipped.
- `values.owner` is someone else (per step 3), or `whoami()` is not the filer.
  Not an error by itself, but the user should see whose work they are taking over
  before the claim writes their name on it — by NAME, which the packet's
  `people` map resolves from the owner id.
- `resumed_from_parked` is present. Say the `warning` verbatim when it carries
  one: the plan predates the resume and the item wants re-scoping, not building.
  When `spec_updated_after_resume` is true there is no warning — the workspec
  moved after the resume — but say the item was parked and resumed anyway.

Then wait for a clear answer; an ambiguous one is not a yes. If it is the wrong
item, ask for the right id — never go hunting the board for the item they
probably meant.

## Pre-Flight

1. **Pick the item(s).** With item-id arguments, use them — one or several.
   Without any, call
   `workspace_queue(workspace, stage="planned")` — it spans **every** board in
   the workspace, where `get_board(board)` sees only the board
   `.claude/maestro.json` names and reports a short queue, no error, wherever a
   team routes work across two. Rows span boards, so list candidates with
   **their board name** (id, title, board, priority) and ask which to build —
   the user may name more than one. Never claim silently.
   Read the reply's `boards` sidecar before presenting the list: a board whose
   `unmatched_stages` names `planned` does not carry that stage at all — re-ask
   it with a value from its own `stage_values` rather than reporting it empty.
   If `workspace_queue` is unavailable (older server), fall back to
   `get_board(board)` and say so.
2. `get_work_packet(item)` — one call for the whole pre-flight: the workspec,
   the names, the staleness facts, the contract, and the workspec's rules
   inlined under `rules.applied` (apply them; name any `rules.missing` slug out
   loud). `knowledge.retrieved` carries the workspace entries nearest this
   workspec — read them like `rules.applied`, and say when one changes the
   plan. `skills.pinned` carries the workspace skills the workspec pins, in
   full, and `skills.retrieved` names up to three more nearest it: read the
   pinned ones, and each retrieved one whose `why` fits
   (`list_workspace_docs(workspace, kind="skill", slug=<slug>)`), before your
   first edit. The description must contain a `## Approach` — **or the legacy
   `## Plan` heading, which this skill reads forever**: ~300 shipped workspecs
   keep the old heading, there is no bulk rewrite, and this fallback is
   permanent — do not "clean it up". Neither heading → stop and point at
   `/maestro-scope <item-id>`.
   **Heed the packet's `plan_gate`** (#2905) when the item is a sub-item of a
   Plan: `{parent_status, wave, blocked_by, warning}` says where this task
   sits in the parent's waves and which prerequisites are unfinished. It is
   advisory — building anyway is allowed — but say the warning out loud
   before proceeding past it.
   **Address the steering first.** The packet LEADS with
   `unaddressed_comments` — every human comment nobody has answered, oldest
   first, before the spec, and they arrive in THIS session so they get
   addressed in this session, before any other work. Addressing is explicit
   data, never prose: reply with
   `comment_on_item(item, <the answer>, addresses=[<those note ids>])` (or
   `addresses="all"`), one reply covering several where that reads better.
   Comments with intent `directive` REFUSE the item's move to done until
   addressed (or withdrawn by a human) — the flip answers with the blocking
   ids; `note` is FYI but still deserves the ack that clears the board's
   amber flag. A comment that changes the plan's shape is a re-scope signal,
   not something to quietly absorb — say so instead of building past it.
   **Refuse a `parked` item** — `stage.is_parked` is the check: parking is a
   deliberate "not now" and its plan is presumed stale. Say so and stop, naming
   the stage it was parked from (`stage.parked.prior_label`) — it is resumed
   from the board (or the drawer's Resume button) and re-scoped first.
   **Refuse a `rejected` item** — `stage.is_rejected` is the check: rejected
   work is never dispatchable. The packet's `stage.rejected` record says who
   declined it, when and why; say that and stop — a human reopens it from the
   board (the drawer's Reopen button) and it re-enters intake, never a build.
   `stage.age` is how long it has sat where it is; a plan that has waited
   months deserves a sentence before you build on it.
3. If `values.owner` is already set to someone else, stop and ask before taking
   it over.
4. **Confirm.** Run the wrong-id gate above and get a yes. Nothing below this
   line is reversible for free: the claim writes to the item and implementation
   commits write to the repo.
5. **Claim** in one call:
   `update_board_item(item, values={"stage": "building", "owner": [<your user id from whoami()>]})`.
6. Pull the description to `planning/.cache/<item-id>.md` (gitignored) — the
   temporary working copy for the session. Never commit generated planning
   snapshots; the board item and its activity trail are the durable record.
7. **Read the verification tier** and set up for it. The step-2 packet already
   carries `quality_contract` — `{"tier", "run", "evidence"}`, the decision
   scoping made as data — so this costs no extra call. (Older server without
   `get_work_packet`: `get_board_item` returns the same key.) Read it from
   there; the `### Verification` prose is the human copy of the same thing and
   the fallback for items scoped before contracts shipped.
   With several items, read them all now and take the **highest** as the run's
   tier; it sizes the one closing run.
   - **No tier takes a baseline.** Nothing runs before the first edit; what a
     red run is judged against is already recorded — see "Judging a Red Run".
     Start building.
   - Whatever `run` names still runs, at every tier — that is where a bug's
     regression test rides on a `none` item.
   - **Neither a `quality_contract` nor a `### Verification` block** (a plan
     scoped before tiers existed, or one that skipped it) → pick the tier
     yourself from the taxonomy in `maestro-scope`, and say which one you picked
     and why in workflow step 1. Never default to `full` because the plan is
     silent — that is the cost this mechanism exists to remove.

## Workflow

1. **Say what you're about to do differently.** The gate already showed what the
   item is; don't repeat it. It did not cover intent: before the first edit,
   state anything in the plan you already mean to deviate from, and re-name the
   item as a markdown link (see "Reporting Back") as the build's anchor. Then
   build.
2. Read every file the plan touches before editing — no blind edits.
3. **If the workspec says `Kind: bug`** — on the `## Spec` meta line, or in the
   header bullets of an item filed before that shape — write a regression test
   that reproduces the bug and confirm it FAILS before touching the fix.
4. Implement one logical unit at a time, following the repo's conventions.
   Write/finish tests immediately after each unit, not at the end. Fix failures
   in your code, not the tests.
5. Commit each logical unit per the repo's git conventions (no push unless the
   repo's rules say otherwise).
6. **After each commit / test run / blocker**, post to the trail:
   `comment_on_item(item, ...)` — commit hash + one-line summary, test counts, or
   the blocker. If the plan changed during the build, push the updated scratch
   file back with `update_board_item(item, description=...)`.
7. **Verify at the plan's tier — that tier, not a bigger one.**
   - **`none`** → no test run. Do the thing the plan's `Why:` line named in
     place of tests, and report both.
   - **`targeted`** → run the modules the plan named, and stop there. Running a
     full sweep to feel safe spends the user's minutes on your comfort.
   - **`full`** → run the repo's default suite **once, after the change**, and
     judge any failure under "Judging a Red Run". `full` is a
     verification-coverage tier; it does not imply the test runner's `--full`
     slow/extended option. Off the integration branch — an item worktree, a
     side branch — use the runner's opt-out from reporting to Maestro (testit:
     `--no-maestro`), so a branch's verdict never stands as the project's
     status.

   **Escalate freely, downgrade never.** If the diff acquired something the plan
   did not anticipate — a migration, a shared helper or contract with callers
   across modules, a dependency bump — move up a tier, run it, and say in the
   report that you escalated and why. Rewrite the contract in the same breath:
   `update_board_item(item, contract={"tier": "full", "run": […],
   "evidence": […]})`. The server records the tier change on the trail itself,
   so the item's declared tier keeps matching what actually ran instead of
   drifting behind it. Moving *down* a tier is the user's call, not yours.
   **Prepare the human review handoff.** Before moving a finished task to
   Review, append or refresh `## Review handoff` in its workspec, after the
   Approach. Use these three `###` headings: `What to check` (a short checkbox
   list a person can perform), `Where to test` (the real build/environment and
   usable links), and `Expected outcome` (what success looks like). Name a
   pending release honestly; never claim staging work is live. Reuse the
   acceptance criteria rather than inventing new requirements. Builder test
   results and checkout ticks are evidence, never a human review verdict.
   The Review inbox falls back to acceptance criteria when this handoff is
   absent and explicitly labels a missing test location.

8. **The closing pass — review the change, then update its docs.** After the
   last commit and the tier's tests, in this order, both from `maestro-review`
   — that file is the one checklist and this is one of its two ways to run:
   - **Review your own diff** against the item: correctness, fit to the
     `## Approach`, the five security categories (permission gaps, data
     exposure, injection, auth bypass, secret leakage) and what the change
     leaves uncovered. Where the repo keeps its own review checklist under
     `.claude/agents/` (`security-review.md` or whatever it named it), run a
     fresh sub-agent on that file — its context is the independence you cannot
     give your own diff. With none, work `maestro-review`'s lists inline.
   - **Then the docs, from the diff as it landed** — not from the plan, which
     is what was intended. Same door: the repo's own `docs-updater` agent when
     it has one, otherwise `maestro-review`'s docs checklist inline, in the
     repo's own tracks and conventions. **"No docs needed, because …" is a
     complete answer**; silence is not.
   - Report both in the closing summary: the findings (with file and line),
     what you fixed, what you filed instead per the repo's findings rule, and
     what the docs step did. A pass that found nothing says so — it reads
     identically to a pass nobody ran otherwise.
   - Fix what the review finds **in this item** only when the item cannot be
     correct without it; anything else is an incidental finding and follows
     the repo's rule for those.
9. **Record what the build learned.** For each decision with a rejected
   alternative, rule the code now assumes, or measured/discovered truth:
   `upsert_workspace_doc(workspace, kind, slug, title, content)` with kind
   `decision` / `convention` / `fact`, one entry per fact, a stable slug, and
   a body a stranger can act on. Read the reply's `similar` before the next
   write — a near match means update that slug, not add a twin. Not recorded:
   transcripts, file dumps, tool logs, anything already in the repo's own
   docs.
10. **Close.** PR opened → `update_board_item(item, values={"stage": "review"})`;
   committed straight to the main branch → `values={"stage": "done"}`. Final
   comment on the trail: what changed + how to validate. Then report back to the
   user TL;DR-first (see below). **In a multi-item run, steps 7-10 do not happen
   per item** — the item stays at `building` and the next one starts; the run's
   single closing pass verifies every item, reviews each item's own diff and
   flips them all.
11. **On failure/blocker**: post a blocker comment, leave `stage=building` and
    the owner intact, and tell the user where it stands — in the same
    TL;DR-first shape. **Blocked on a human ANSWER rather than a failure?** In
    an interactive client chat (including the Agent Tool), ask the human in
    chat and wait there. Do not call `comment_on_item(question=...)` merely to
    mirror that interactive ask onto the board; the human is already present,
    and a second durable state can outlive the chat answer.

    For a real **async/background handoff**, use
    `ask_task_question(item, text, recipient, creation_key, blocking=true,
    client=..., model=...)` with the chosen eligible human and a fresh UUID.
    Read its exact answer with `get_task_question(question)` before resuming work;
    clarification, reading a bell and `addresses="all"` do not answer it.
    If the recipient is wrong, the requester/current recipient/manager can use
    `redirect_task_question` with the last read version and optional reason.
    Check in and stop while a blocking answer is pending.

    Only the authenticated current human recipient can answer with
    `answer_task_question`; an agent credential cannot impersonate them. A
    human-credential session may relay their explicit answer, visibly attributed
    via client/model. Never relay a different person's answer as your own.
    Managers must redirect to themselves before answering. When directed asks
    are not enabled, `comment_on_item(question=<text>)` remains the legacy
    unassigned adapter; its returned `resolve_question.arguments` names the
    exact asking note. Explicit addressing still checks answer authority.

## Verification Across Several Items

One closing run for the whole set, never one sweep per item.

- **The run's tier is the highest tier any item carries.** A helper or contract
  one item creates and another consumes is a bound that held per item and does
  not hold together — **escalate both to `full` and say so**. Two items editing
  one file keep their tiers: the closing union runs both items' modules against
  the combined tree. That judgement exists only at this level; no single plan
  can make it.
- **Any item at `full`** → the default suite once, after the last item lands.
  No baseline.
- **`targeted` / `none` only** → the closing run is the union of every item's
  named modules, run once, after the last item lands.
- **Every item at `none`** → no closing run either. Say plainly that no suite
  ran, and what stood in for it per item.
- A bug's regression test is the one exception at any tier: it runs alone,
  before and after that item's fix, because a regression test nobody saw fail
  proves nothing. Seconds.
- **Red** → judge it under "Judging a Red Run"; attribute new failures to the
  item owning the touched files (the per-item commits make this unambiguous),
  fix in place, re-run the closing set.
  One sweep per fix round. An item you cannot get green stays at `building` with
  a blocker comment naming the failing tests; the rest still flip.
- **Green** → flip every built item in one pass, `review` or `done` per step 10.

Nothing is `done` mid-run: until the closing verification is assessed, the truth
is "built".

## Judging a Red Run

No build takes a baseline. The one question a baseline answered — *was this
failure already there?* — is answered from what is already recorded, and only
for the tests that actually failed.

1. **The last recorded integration-branch run.** `test_status(project,
   branch="staging")` — the project in the repo's `.claude/maestro.json`, the
   branch its work merges into before release — returns that branch's latest
   run per suite with its failing tests, whatever other branches pushed since.
   Read the row for the suite you ran (the runner names it; testit names it
   after the preset, so a default run and an all-tier run are different rows)
   and say which commit and date you compared against. A test in its `failing`
   list was already red there. A session whose grant refuses the tool, or a
   server that refuses or ignores `branch` (its reply carries no `branch` key),
   has no record: go to step 4.
2. **The workspace's `known-flaky-tests` fact**, when it keeps one
   (`search_knowledge` or `get_workspace_context`). A listed test failing with
   its recorded signature is a known flake: name it and its item, and do not
   re-run the suite to rediscover it. The same test failing with a different
   message is not covered by the list.
3. **Anything left is this change's until shown otherwise.** Read the failure
   first — most name the change outright. If it doesn't, run that one test file
   alone on the integration branch's current commit, in a worktree of it: red
   there means it predates you. On a tree holding nothing but this item's work,
   `git stash -u`, the same targeted run and an unstash settle it too. On a
   **shared tree** — another session's or another agent's uncommitted work
   beside yours — never `git stash` and never `git checkout` over it: the stash
   stack is shared and you would take away changes that are not yours (#4358
   left 39 uncommitted paths in one tree, and a stash there would have swept
   them).
4. **No usable record** — no row for that branch and suite, or a runner that
   does not report — say so, and settle each failure by step 3.

Then act on what each failure is:

- **Within the approved fix**: keep the failing test as regression evidence and
  proceed with the authorized repair.
- **Already red, or a known flake, and isolated**: record the test and what it
  matched (the recorded run's commit, or the fact's item) on the trail, file a
  newly found pre-existing failure under the repo's findings policy, tell the
  user and continue without asking for another approval. Do not widen the build
  to fix it, skip it, or weaken its assertions. The work may go to **review**
  with those failures explicit in the trail and final report; never describe the
  suite as green or fully passing, or mark the work done on this exception. A
  release or integration gate still applies independently.
- **New, and this change's**: fix it in place and re-run the closing set.
- **Cannot verify the proposed change**: repair routine environment problems
  within the existing authorization. Pause only affected work if failures remain
  unattributable, prevent meaningful verification, or require a scope or product
  decision; explain the concrete blocker and ask only for the missing decision.

<a id="when-a-persona-agent-built-it"></a>

## When an Agent Built It

An item may come back built by a named agent teammate — a Lead or a Software
Engineer — rather than by you. Its reply names a branch and commit hashes; that
is a claim, never evidence.

1. **Fetch the branch it named** (`agent/<item id>-<role>`):
   `git fetch origin agent/<item id>-<role>`. Read the diff before anything
   else — what it changed, what it did not, and whether the tests it says it
   added actually fail without the change.
2. **Re-run the item's `quality_contract.run` yourself**, on that branch, in a
   worktree of it — never by switching branches in a tree that may hold other
   uncommitted work. Post **your** collected/passed/failed counts. The agent's
   numbers never substitute for a run you did.
3. **Never merge its branch into `main` or a staging branch without a person's
   yes** (Ian's decision 8). Asking is the step, not a formality: the agent
   pushed its own branch precisely so a person decides what lands.
4. If the work is short of the item, say so on the item and ask for a rework
   round rather than finishing it silently under the agent's name.

The teammate's own procedure is the workspace skill "How this team ships work" —
the same branch and worktree rule, written in its terms.

## When an Agent Teammate Runs This

**A teammate session is one where `whoami()`'s `session.persona_agent` is
non-null.** Every other session is interactive and the skill above applies
unchanged — including a brokered owner session in a desktop composer, whose
`authority` reads `agent_session` but whose `session.persona_agent` is null.

The build is the same build: read before editing, one logical unit at a time,
tests with each unit, the plan's tier, the trail kept current. What changes is
every gate that waits for a person.

| The gate above | As a teammate |
|---|---|
| Board Resolution — ask which workspace, offer to write `.claude/maestro.json` | The ask carried the item; resolve the rest from `get_work_packet(item)`. Never pick a board, never write a repository config file. Maestro unreachable: say so in your reply and stop. |
| The wrong-id gate — show the card, get a yes before the claim | **Check** instead of confirm: the packet's title and stage must match what the ask described, and a mismatch is refused **by name** before any claim or edit. `parked` and `rejected` still refuse outright. |
| Pre-Flight 1 — list candidates and ask which to build | Does not apply. An ask with no item id is refused; say you need one and stop. |
| Pre-Flight 3 — owner is someone else, stop and ask | Comment that it is owned, by name, and end the turn. Never take over an item. |
| Pre-Flight 5 — claim the item | Only if your role may edit items. Otherwise it was claimed for you — the Maestro made you its Owner, or the Lead holds the item and you work its piece under that checkout; take your own row's checkout when you are its Owner, and say which happened. |
| Checkout conflict — show the holder, ask whether to wait | Comment the holder, the purpose and the expiry, and end the turn. Do not wait and do not take it. |
| Approvals are human decisions | Not yours, ever. `approve_board_item_plan` and `request_board_item_rescope` record a *person's* decision and refuse an agent credential outright. A plan that needs approving is an `ask_person` (or `ask_task_question` for a deliberate task-record handoff) and then the turn ends. |
| Step 1 — say what you mean to do differently | Same words, posted as `comment_on_item` before the first edit, not spoken to a room. |
| Step 7 — downgrading a tier is the user's call | Escalate freely and say so. To go *down*, ask; until the answer comes, run the tier as written. At `full` the default suite is the Integrator's one run per wave, on staging; you run the contract's `run` entries. |
| Step 8 — the closing pass | **Two asks** — see below. |
| Step 10 — close, and report TL;DR-first to the user | Post the same TL;DR as a comment. On a Team whose flow hands out work, the stage is the Maestro's to move; otherwise **`review` is the top stage a teammate sets**, and `done` is somebody else's to set. |
| Step 11 — blocked on an answer: ask in chat and wait there | You are not sitting in a chat. `ask_person(question, item=…)` for someone who is around, `ask_task_question(item, …, blocking=true)` for a deliberate task-record handoff — then the waiting rule below. |
| Judging a Red Run — "ask only for the missing decision" | The same ask, then the waiting rule. Record the closing run (revision, command, counts, failing tests and what each matched) on the trail **first**, so the resumed turn does not pay for it twice. |
| "When an Agent Built It" — never merge without a person's yes | Unchanged, and it binds you hardest: push your own branch and report it. Never merge to `main`; merge to a staging branch only under a recorded human authorization. |

**The two closing checks are asks.** A teammate does not review its own work
and does not write its own documentation review:

- **The change review** goes to the Team's `reviewer` — the Code Reviewer on a
  default Dev Team — with `ask_agent`, naming the item, the branch and the
  **exact commit** (`git rev-parse HEAD`). It answers with a verdict in
  `maestro-review`'s format, on the item. A `changes needed` verdict is worked
  and re-asked: **two rework rounds, then the Lead decides.** Nothing you built
  is merged without a passing verdict naming the commit being merged, and a
  new commit voids the last verdict for the files it touched. **Ask and move
  on.** In the same turn tell the teammate who handed the item out that it is
  pushed — on a Team with a flow that frees you for your next task — and end
  the turn; never wait for the verdict. A push-back arrives later as a prompt:
  fix it on the same branch and re-ask with the new commit; the reviewer reads
  only what changed.
- **The docs** go to the Team's Docs Writer, found by Role through
  `list_teammates`, on a branch stacked on yours. With no Docs Writer on the
  Team, you write them yourself under `maestro-review`'s docs checklist and say
  so — "no docs needed, because …" counts, silence does not.
- Whoever wrote something never checks it. If you *are* the reviewer for this
  item, say so and hand the review to someone else.

**One hand-off path.** Every check is one Maestro teammate, asked with
`ask_agent` and recorded on the item. `ask_agent` may refuse for want of a live
acknowledged request (an owner console turn): then post on the item what is
ready and who should do it, and never claim a hand-off you did not make.

**The waiting rule — how a turn ends without stranding the item.** Before you
end a turn on an ask:

1. **Comment who you are waiting on and what for**, naming the teammate or the
   person, the question, and the commit if a review is what you asked for.
2. **`check_in_board_item_checkout`.** A lease runs an hour and an ask can take
   a day; holding it locks the item behind a session that has stopped thinking
   about it.
3. **End the turn** — no further post, no final text.

On resume: **re-acquire the checkout and re-read `get_work_packet(item)` before
anything else.** The packet is the only state this turn shares with the last,
and the branch, the verdict or the item may have moved while you waited. The
same on every rework round, however short.

## Reporting Back

Both the step-1 orientation and the closing summary name the item as a **markdown
link**, never a bare id:

```
[#<id> <title> (<stage>)](<url>)
```

`url` comes from the tool result (`get_work_packet` and `get_board_item` both
return it) — never
hand-assemble a host. In a repo with a GitHub remote the client auto-linkifies a
bare `#123` to that repo's issue 123 — a live link to the wrong system.

The closing summary opens with a short block, before any detail:

- **What shipped** — the item title plus the original ask in one sentence, in
  the requester's terms, not the codebase's.
- **What changed** — the commits, one line each.
- **What deviated from the plan** — anything done differently and why, or
  "followed the plan" if nothing moved. Never let a deviation surface only in a
  diff.
- **Verification** — the tier, the commands run, and their result, stated
  plainly, and whether that was the planned tier or an escalation, with why. At
  `none`, say outright that no tests were run and what stood in for them — a
  reader must never infer that from silence. A test that failed, was skipped, or
  could not run goes here, never omitted.
- **Stage** — where the item landed, and what remains if it is not `done`.

Keep it to roughly 15 lines. Detail lives in the commits and the item's activity
trail — point at them, don't inline them. A multi-item run reports **once**: the
same five headings, one line per item under each, with Verification stated for
the run (its tier, the single closing sweep, and any escalation) rather than per
item — roughly 20 lines for the whole run.

A blocker report follows the same shape: name the item, what stopped it, what is
committed so far, and what you need to proceed.

## Outage Mid-Build

Never block the build on maestro. Finish locally against the scratch copy;
collect the stage flip and pending comments in your final summary as exact tool
calls for the user (or next session) to replay. Retry each push once before
queueing it.

## Forbidden

- Claiming or building an item the user has not confirmed — the
  gate is the only thing between a fat-fingered id and someone else's item
- Building an item with no `## Approach` (nor legacy `## Plan`), or claiming
  over someone else's owner without asking
- Expanding scope beyond the item; touching files outside the plan without
  flagging it first
- Building past the packet's `unaddressed_comments`, or answering them in
  prose without the `addresses=` data that actually clears them
- Writing no tests for a behavior change — the tier decides which tests are
  *run*, never whether the change is covered
- Downgrading the plan's verification tier without asking. Escalating is always
  yours to do; relaxing is the user's
- Reporting a build as verified when the tier's runs did not happen, or quietly
  running a default suite the plan did not ask for
- Taking a baseline — any suite run before the change — at any tier, or
  re-running a whole suite to rediscover a failure the recorded run or the
  known-flaky list already explains
- Leaving the item's stage stale after the build ends
- Closing a build without the review-and-docs pass, or reporting a pass that
  did not run — "nothing found" and silence read identically, and only one of
  them is true
- Reviewing your own change and calling it independent
- Ending a turn on an ask without saying who it waits for and checking the
  checkout in
- Closing a build without stating what deviated from the plan and how
  verification actually went
- Building several items concurrently in a repo with a shared test port,
  database or working tree, or flipping any of them past `building` before the
  run's single closing sweep is green
