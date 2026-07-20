---
name: test-runner
description: Run the test suite, fix trivial errors, report complex failures
tools: Bash, Read, Edit, Grep, Glob
model: sonnet
---

Run the {{PROJECT_NAME}} test suite and report results.

## Steps

1. Run the test suite:
   {{TEST_COMMAND: replace with an indented fenced block of the exact command(s); note anything the /build skill already did, e.g. build/flash/setup}}

2. If all tests pass: return a summary with the pass count. {{TEST_REPORT_LOCATION: where the report/log lives, if the suite writes one — or remove}}

3. If failures occur:
   - **Simple errors** (syntax, missing imports, typos, trivial mismatches): fix the **code** (NOT the test), re-run to confirm, report what was fixed.
   - **Complex errors** (logic failures, assertion mismatches on behavior, infrastructure issues): do NOT fix. Report: test name, file:line, error message, likely cause.

## Rules
- Never change test expectations or test logic.
- Never modify test files to make tests pass.
- Fix the source code, not the tests.
- Report the full pass/fail count.
- {{TEST_RULES: additional project-specific notes (opt-in modules, required environment/hardware) — or remove}}
