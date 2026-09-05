---
name: maestro-build
description: >-
  Claim one or more planned maestro board items (owner + stage=building),
  execute each ## Approach (legacy ## Plan) inside this repo with full build
  discipline, keep every item's activity trail updated (commits, tests,
  blockers), and land them at review/done via the maestro MCP.
user-invocable: true
argument-hint: <item-ids, e.g. "431" or "431 432" (omit to pick from the board)>
maestro-skill-version: 23
---

# Maestro Build â€” Execute a Planned Item

You are a senior engineer executing a scoped item one task at a time: minimal,
correct, tested code matching the repo's existing patterns and conventions (read
`AGENTS.md` when present, plus `CLAUDE.md` and applicable project rules). The
board item is the work record â€” keep its stage and activity trail current
throughout.

## One Item or Many

**Takes any number of ids** â€” `/maestro-build 431`, `/maestro-build 431 432
438`. **Sequential is the default.** In a repo whose suite targets a fixed port
and a shared database, and whose work commits to one branch in one working tree,
parallel builds collide on the port, corrupt the database and interleave
commits.

**Build in parallel only when both hold**, and say which:

1. **The repo isolates a checkout** â€” each worktree gets its own test database,
   port and cache namespace. Verify it; do not assume. The repo's git/testing
   rules say so explicitly when it does.
2. **The items are independent on disk** â€” no shared files, no migrations to the
   same app (two trees generate the same `000N_` and clash at merge), and
   neither consumes what the other creates.

Either one missing â†’ sequential. Parallelism is a speed optimization; a merge
conflict inside someone else's build is not.

Parallel runs one worktree per item, each on its own branch, then merges every
branch back **one at a time** and verifies once in the primary tree â€” each build
proved itself in isolation, and the combined tree is what ships. Clean up every
worktree and branch you created. Follow the repo's own worktree lifecycle where
it documents one; it will know setup steps (dependency install, gitignored
config) that a bare `git worktree add` skips.

With several ids, run the flow below per item, with these differences:

- **Confirm the whole roster once** â€” one wrong-id card per item, in one block,
  one ask â€” before the first claim, and call out two ids a digit apart.
- **Partition the items before starting.** Which build in parallel, which are
  forced sequential and by what â€” a shared file, a migration to the same app, a
  plan consuming a helper another plan creates. State the partition and the
  reason for every sequential edge; a batch that all goes one lane should say
  why that was the right call.
- **Merge and clean up before verifying.** Every branch back into the primary
  tree one at a time, every worktree and branch removed, then the closing run.
- **Claim, snapshot, build and comment per item** exactly as below, then leave
  each at `building` â€” built, not verified.
- **Verify once, at the end** (see "Verification Across Several Items"), and
  only then flip every green item in one pass.
- **A failed item does not fail the run.** Blocker comment, leave it at
  `building` with its owner intact, continue with the remaining **independent**
  items, halt the ones that depended on it, and say which.
- **Report once** for the run, one block per item.

Past two or three items, delegating each build to a fresh-context sub-agent
keeps the later plans from being executed by a session that has forgotten the
first â€” that is what `/maestro-auto` does, and it also handles the scoping and
folds everything into one approval gate.

## Board Resolution

Same as `maestro-task`: read Maestro's `.claude/maestro.json` repo config; on any miss, resolve via
`whoami()` / `list_workspaces()` / `list_boards()`, ask, offer to write the
file. Maestro unreachable **before claiming** â†’ stop with an explicit notice;
offer the repo's local build skill if one exists.

Also from `maestro-task` â€” **step 5: name boards and items when you report them, never bare ids**: `board "Backlog" (Maestro workspace, id 8)`, `#586 "An agent cannot see what it deployed"`, with the item URL (link format under "Reporting Back"). That lookup is far cheaper for you than for the user.

**Step 7: pass `client=` (the client you are running in) and `model=` (your model id) on every `create_board_item`, `update_board_item` and `comment_on_item` call.** The server cannot observe either â€” a write that omits them lands in the trail under the default label, "via Claude", whoever wrote it.

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
line, what you are doing right now â€” "running ingress tests") and `criteria` +
`criteria_count` (sparse per-criterion ticks keyed by 1-based ordinal into the
workspec's `### Acceptance Criteria` list, states `active`/`done`/`blocked`;
`criteria_count` is how many checkboxes you see and is required with every
criteria-bearing check-in). Check in at natural boundaries â€” a criterion
passed, a phase change, a blocker hit, a sub-agent dispatched or returned â€”
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
this session â€” never inferred from context, a workspec, or a prior session,
and never as part of an unattended run. The tools refuse agent-kind
credentials outright; on a human's credential the call records THEIR decision,
so relay it only when they actually said it, and pass `client=`/`model=` so
the record shows a session wrote it on their behalf.

`approve_board_item_plan` is the ONE approve verb, routed by what the item is
(#2905): on a Plan container (a top-level item with sub-items or wave data) it
records the ROSTER approval â€” {version, roster, waves snapshot} â€” legal from
any stage, and a later roster change honestly re-asks; on a sub-item or a
childless standalone task it records the item-level plan approval as before.
The reply's `scope` says which. Same human-only contract either way.

## Confirm the Item â€” the wrong-id gate

**An item id is not self-describing.** Ids get transposed, copied out of the
wrong session, or read off a stale list, and a build compounds it fastest: the
claim stamps stage and owner on someone else's item and the commits land before
anybody notices. So the gate comes **before the claim** â€” the first mutation in
this skill.

Required whenever the id came from an argument, a note, or another session.
Skip only if the user just picked the item off a list you presented this
session (they have seen the title), or waives it outright.

Build the card from **one** `get_work_packet(item)`. It carries the workspec,
the board and workspace **names**, who filed it, when the workspec last changed,
how long the item has sat in its stage, whether it was resumed from parked, its
parent, the verification contract, and the rules the workspec references â€” the
whole card, and most of the pre-flight below, in one call. Older server without
the tool: `get_board_item(item)` plus one `list_boards(<the item's workspace>)`
for the names, and say you fell back.

    #586 "An agent cannot see what it deployed â€” add preview_site"
    board "Backlog" Â· workspace "Maestro" Â· stage planned Â· must
    filed by Ian Starnes 2026-07-12 (2 weeks ago), scoped 2026-07-26
    part of #516 "Sites + domains â€” release hardening (epic)"
    https://maestromojo.com/app/#/board/8?item=586

    Agents ship sites they never see: deploy_site returns byte counts, not
    pixels. Wants an MCP render tool so an agent can look at what it
    deployed.

    Plan: new preview_site MCP tool over a server-side renderer, desktop +
    mobile presets, snapshot cached per revision. 3 commits, ~6 tests, both
    doc tracks.

    Build this one? (claiming it sets stage=building and owner=you)

- **Title first, then where it lives** â€” `board_name` and `workspace_name`; an
  id cannot be recognised.
- **Who filed it and when**: `filed.by` / `filed.age`, plus `spec_updated` â€”
  when the workspec last changed, which on a scoped item is when the plan was
  written. Give the plain words the packet already ships ("filed today",
  "spec updated 3 weeks ago"); a plan sitting for weeks may be stale. Note that
  any description save moves `spec_updated`, so it dates the workspec, not the
  scoping â€” you judge whether the change was a re-scope.
- **TL;DR in the requester's terms**, then **the plan in 2-3 lines** â€” what is
  about to be executed, and its size. On a build the plan is what is being
  confirmed; the problem statement just makes the item recognisable.
- **Name the parent** if it has one, and how many sub-items it has â€” an
  unexpected epic is the loudest wrong-id signal there is.

**Say these out loud before asking, whenever they are true:**

- The item's `board` is a **sibling board in the same workspace** â€” normal under
  a deliberate split; confirm it is the board you meant, since ids interleave
  across boards. A different `workspace` is almost always a wrong id, and would
  build another repo's work in this tree.
- Its stage is not `planned` â€” `inbox` means it was never scoped, `review` or
  `done` means it already shipped.
- `values.owner` is someone else (per step 3), or `whoami()` is not the filer.
  Not an error by itself, but the user should see whose work they are taking over
  before the claim writes their name on it â€” by NAME, which the packet's
  `people` map resolves from the owner id.
- `resumed_from_parked` is present. Say the `warning` verbatim when it carries
  one: the plan predates the resume and the item wants re-scoping, not building.
  When `spec_updated_after_resume` is true there is no warning â€” the workspec
  moved after the resume â€” but say the item was parked and resumed anyway.

Then wait for a clear answer; an ambiguous one is not a yes. If it is the wrong
item, ask for the right id â€” never go hunting the board for the item they
probably meant.

## Pre-Flight

1. **Pick the item(s).** With item-id arguments, use them â€” one or several.
   Without any, call
   `workspace_queue(workspace, stage="planned")` â€” it spans **every** board in
   the workspace, where `get_board(board)` sees only the board
   `.claude/maestro.json` names and reports a short queue, no error, wherever a
   team routes work across two. Rows span boards, so list candidates with
   **their board name** (id, title, board, priority) and ask which to build â€”
   the user may name more than one. Never claim silently.
   Read the reply's `boards` sidecar before presenting the list: a board whose
   `unmatched_stages` names `planned` does not carry that stage at all â€” re-ask
   it with a value from its own `stage_values` rather than reporting it empty.
   If `workspace_queue` is unavailable (older server), fall back to
   `get_board(board)` and say so.
2. `get_work_packet(item)` â€” one call for the whole pre-flight: the workspec,
   the names, the staleness facts, the contract, and the workspec's rules
   inlined under `rules.applied` (apply them; name any `rules.missing` slug out
   loud). The description must contain a `## Approach` â€” **or the legacy
   `## Plan` heading, which this skill reads forever**: ~300 shipped workspecs
   keep the old heading, there is no bulk rewrite, and this fallback is
   permanent â€” do not "clean it up". Neither heading â†’ stop and point at
   `/maestro-scope <item-id>`.
   **Heed the packet's `plan_gate`** (#2905) when the item is a sub-item of a
   Plan: `{parent_status, wave, blocked_by, warning}` says where this task
   sits in the parent's waves and which prerequisites are unfinished. It is
   advisory â€” building anyway is allowed â€” but say the warning out loud
   before proceeding past it.
   **Address the steering first.** The packet LEADS with
   `unaddressed_comments` â€” every human comment nobody has answered, oldest
   first, before the spec, and they arrive in THIS session so they get
   addressed in this session, before any other work. Addressing is explicit
   data, never prose: reply with
   `comment_on_item(item, <the answer>, addresses=[<those note ids>])` (or
   `addresses="all"`), one reply covering several where that reads better.
   Comments with intent `directive` REFUSE the item's move to done until
   addressed (or withdrawn by a human) â€” the flip answers with the blocking
   ids; `note` is FYI but still deserves the ack that clears the board's
   amber flag. A comment that changes the plan's shape is a re-scope signal,
   not something to quietly absorb â€” say so instead of building past it.
   **Refuse a `parked` item** â€” `stage.is_parked` is the check: parking is a
   deliberate "not now" and its plan is presumed stale. Say so and stop, naming
   the stage it was parked from (`stage.parked.prior_label`) â€” it is resumed
   from the board (or the drawer's Resume button) and re-scoped first.
   **Refuse a `rejected` item** â€” `stage.is_rejected` is the check: rejected
   work is never dispatchable. The packet's `stage.rejected` record says who
   declined it, when and why; say that and stop â€” a human reopens it from the
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
6. Pull the description to `planning/.cache/<item-id>.md` (gitignored) â€” the
   temporary working copy for the session. Never commit generated planning
   snapshots; the board item and its activity trail are the durable record.
7. **Read the verification tier** and set up for it. The step-2 packet already
   carries `quality_contract` â€” `{"tier", "run", "evidence"}`, the decision
   scoping made as data â€” so this costs no extra call. (Older server without
   `get_work_packet`: `get_board_item` returns the same key.) Read it from
   there; the `### Verification` prose is the human copy of the same thing and
   the fallback for items scoped before contracts shipped.
   With several items, read them all now and take the **highest** as the run's
   tier â€” the baseline decision below is made once, for the run, before the
   first claim:
   - **`full`** â†’ establish the repo's green baseline now, per its own test
     conventions. Red baseline â†’ stop and tell the user; don't build on red
     without their say-so.
   - **`targeted`** or **`none`** â†’ **no baseline run.** Start building.
     Whatever `run` names still runs, at every tier â€” that is where a bug's
     regression test rides on a `none` item.
   - **Neither a `quality_contract` nor a `### Verification` block** (a plan
     scoped before tiers existed, or one that skipped it) â†’ pick the tier
     yourself from the taxonomy in `maestro-scope`, and say which one you picked
     and why in workflow step 1. Never default to `full` because the plan is
     silent â€” that is the cost this mechanism exists to remove.

## Workflow

1. **Say what you're about to do differently.** The gate already showed what the
   item is; don't repeat it. It did not cover intent: before the first edit,
   state anything in the plan you already mean to deviate from, and re-name the
   item as a markdown link (see "Reporting Back") as the build's anchor. Then
   build.
2. Read every file the plan touches before editing â€” no blind edits.
3. **If the workspec says `Kind: bug`** â€” on the `## Spec` meta line, or in the
   header bullets of an item filed before that shape â€” write a regression test
   that reproduces the bug and confirm it FAILS before touching the fix.
4. Implement one logical unit at a time, following the repo's conventions.
   Write/finish tests immediately after each unit, not at the end. Fix failures
   in your code, not the tests.
5. Commit each logical unit per the repo's git conventions (no push unless the
   repo's rules say otherwise).
6. **After each commit / test run / blocker**, post to the trail:
   `comment_on_item(item, ...)` â€” commit hash + one-line summary, test counts, or
   the blocker. If the plan changed during the build, push the updated scratch
   file back with `update_board_item(item, description=...)`.
7. Update the repo's docs and changelog per its conventions.
8. **Verify at the plan's tier â€” that tier, not a bigger one.**
   - **`none`** â†’ no test run. Do the thing the plan's `Why:` line named in
     place of tests, and report both.
   - **`targeted`** â†’ run the modules the plan named, and stop there. Running a
     full sweep to feel safe spends the user's minutes on your comfort.
   - **`full`** â†’ run the repo's default suite and report it against the
     pre-flight baseline. `full` is a verification-coverage tier; it does not
     imply the test runner's `--full` slow/extended option.

   **Escalate freely, downgrade never.** If the diff acquired something the plan
   did not anticipate â€” a migration, a shared helper, a changed contract, a
   second app touched â€” move up a tier, run it, and say in the report that you
   escalated and why. Rewrite the contract in the same breath:
   `update_board_item(item, contract={"tier": "full", "run": [â€¦],
   "evidence": [â€¦]})`. The server records the tier change on the trail itself,
   so the item's declared tier keeps matching what actually ran instead of
   drifting behind it. Moving *down* a tier is the user's call, not yours.
9. **Close.** PR opened â†’ `update_board_item(item, values={"stage": "review"})`;
   committed straight to the main branch â†’ `values={"stage": "done"}`. Final
   comment on the trail: what changed + how to validate. Then report back to the
   user TL;DR-first (see below). **In a multi-item run, steps 8-9 do not happen
   per item** â€” the item stays at `building` and the next one starts; the run's
   single closing pass verifies and flips them all.
10. **On failure/blocker**: post a blocker comment, leave `stage=building` and
    the owner intact, and tell the user where it stands â€” in the same
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

- **The run's tier is the highest tier any item carries.** Two items editing the
  same file, or a helper one creates and another consumes, is a bound that held
  per-item and does not hold together â€” **escalate both and say so**. That
  judgement exists only at this level; no single plan can make it.
- **Any item at `full`** â†’ one green baseline before the first claim, the full
  suite once after the last item lands. Red baseline â†’ stop and tell the user;
  never build on red.
- **`targeted` / `none` only** â†’ no baseline. The closing run is the union of
  every item's named modules, run once, after the last item lands.
- **Every item at `none`** â†’ no closing run either. Say plainly that no suite
  ran, and what stood in for it per item.
- A bug's regression test is the one exception at any tier: it runs alone,
  before and after that item's fix, because a regression test nobody saw fail
  proves nothing. Seconds.
- **Red** â†’ attribute each failure to the item owning the touched files (the
  per-item commits make this unambiguous), fix in place, re-run the closing set.
  One sweep per fix round. An item you cannot get green stays at `building` with
  a blocker comment naming the failing tests; the rest still flip.
- **Green** â†’ flip every built item in one pass, `review` or `done` per step 9.

Nothing is `done` mid-run: until that sweep is green, the truth is "built".

## Attributing a Red Test Without a Baseline

A baseline answers exactly one question: *was this failure already there?* Buy
that answer when something actually fails, not up front on every build. When a
run comes back red below `full`:

1. **Read the failure first.** Most name your change unambiguously â€” the file,
   the assertion, the symbol you just touched.
2. If it doesn't, stash the working tree (`git stash -u`), re-run **that same
   targeted test**, and unstash. Seconds, and it settles the question where the
   doubt is.
3. A failure that predates you gets **reported, not silently fixed** â€” it is not
   yours and not part of this item. Say so in the summary.

`full` keeps its up-front baseline because attributing a red *suite* after the
fact is neither cheap nor unambiguous.

## Reporting Back

Both the step-1 orientation and the closing summary name the item as a **markdown
link**, never a bare id:

```
[#<id> <title> (<stage>)](<url>)
```

`url` comes from the tool result (`get_work_packet` and `get_board_item` both
return it) â€” never
hand-assemble a host. In a repo with a GitHub remote the client auto-linkifies a
bare `#123` to that repo's issue 123 â€” a live link to the wrong system.

The closing summary opens with a short block, before any detail:

- **What shipped** â€” the item title plus the original ask in one sentence, in
  the requester's terms, not the codebase's.
- **What changed** â€” the commits, one line each.
- **What deviated from the plan** â€” anything done differently and why, or
  "followed the plan" if nothing moved. Never let a deviation surface only in a
  diff.
- **Verification** â€” the tier, the commands run, and their result, stated
  plainly, and whether that was the planned tier or an escalation, with why. At
  `none`, say outright that no tests were run and what stood in for them â€” a
  reader must never infer that from silence. A test that failed, was skipped, or
  could not run goes here, never omitted.
- **Stage** â€” where the item landed, and what remains if it is not `done`.

Keep it to roughly 15 lines. Detail lives in the commits and the item's activity
trail â€” point at them, don't inline them. A multi-item run reports **once**: the
same five headings, one line per item under each, with Verification stated for
the run (its tier, the single closing sweep, and any escalation) rather than per
item â€” roughly 20 lines for the whole run.

A blocker report follows the same shape: name the item, what stopped it, what is
committed so far, and what you need to proceed.

## Outage Mid-Build

Never block the build on maestro. Finish locally against the scratch copy;
collect the stage flip and pending comments in your final summary as exact tool
calls for the user (or next session) to replay. Retry each push once before
queueing it.

## Forbidden

- Claiming or building an item the user has not confirmed â€” the
  gate is the only thing between a fat-fingered id and someone else's item
- Building an item with no `## Approach` (nor legacy `## Plan`), or claiming
  over someone else's owner without asking
- Expanding scope beyond the item; touching files outside the plan without
  flagging it first
- Building past the packet's `unaddressed_comments`, or answering them in
  prose without the `addresses=` data that actually clears them
- Writing no tests for a behavior change â€” the tier decides which tests are
  *run*, never whether the change is covered
- Downgrading the plan's verification tier without asking. Escalating is always
  yours to do; relaxing is the user's
- Reporting a build as verified when the tier's runs did not happen, or quietly
  running a default suite the plan did not ask for
- Leaving the item's stage stale after the build ends
- Closing a build without stating what deviated from the plan and how
  verification actually went
- Building several items concurrently in a repo with a shared test port,
  database or working tree, or flipping any of them past `building` before the
  run's single closing sweep is green
