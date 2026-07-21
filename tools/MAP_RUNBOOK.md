# Map Runbook — desktop-client steps

The map pipeline is split between what the `tools/` scripts generate in code and
what only the **Victoria 3 desktop client** can produce (heightmap repack,
`nodes.dat`, object locators, session validation). Those client steps can't be
driven in this environment, so they're written up here click-by-click; the user
runs them and commits the resulting outputs.

This runbook grows one section per phase. Each section states: what to open,
exactly what to click, which files the game writes, and which of those to commit.

> **After every editor save, run `git diff` before committing.** The editor may
> rewrite more than intended (e.g. `province_terrains.txt`, locators). Commit
> only the files the step says to, and only when the diff is the expected
> regeneration.

---

## P1 — Tooling scaffold

**No game step.** P1 is entirely offline: it writes nothing the game loads
(everything lives under `tools/` + `vic3-tiger.conf`). Validation is:

```
python tools/run_fixture.py --check     # determinism + golden + validators
```

There is nothing to open in the client and nothing in `logs/error.log` to check.

---

<!-- ## P2 — Heightmap repack   (added when P2 is built) -->
<!-- ## P4 — nodes.dat + session boot -->
<!-- ## P5 — object locators + spline regeneration -->
