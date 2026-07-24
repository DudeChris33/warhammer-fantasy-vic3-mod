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

## S2 — Heightmap repack + main-menu boot

**Goal of this step:** the offline tools have written a new `map_data/heightmap.png`
(16-bit, 16384×7232) and `map_data/rivers.png`; the game does not read
`heightmap.png` directly at runtime — it reads the *packed* set the map editor
produces from it. So the editor has to repack once, and those packed files get
committed.

### 0. Offline first (already done by the tools)

```
python tools/worldgen/sources.py --verify   # sources match the manifest
python tools/generate_heightmap.py           # -> map_data/heightmap.png (+ tools/derived/land_sea_mask.png)
python tools/generate_rivers.py              # -> map_data/rivers.png
python tools/run_fixture.py --check          # determinism + goldens + validators
```

Confirm `git status` shows `map_data/heightmap.png`, `map_data/rivers.png`, and
`tools/derived/land_sea_mask.png` staged/modified. Everything else in
`tools/derived/` is a QA render and is gitignored.

> **Nothing in `common/`, `events/`, `gui/`, or `localization/` changed in S2,**
> and `map_data/provinces.png`, `default.map`, and `state_regions/` stay vanilla
> on purpose — the map will look wrong (WH relief under vanilla provinces) at this
> gate. That is the intended de-risk: it isolates the editor-repack + boot loop
> before the S3 province overhaul.

### 1. Repack the heightmap in the map editor

1. Launch Victoria 3 with **this mod enabled** and the **`-debug_mode`** launch
   option (Steam → Victoria 3 → Properties → Launch Options), which unlocks the
   in-game map editor.
2. Main menu → open the **Map Editor** (or press the editor hotkey; it loads the
   active mod's map).
3. The editor reads the mod's new `heightmap.png`. Trigger the heightmap
   **repack / pack heightmap** action (Map Editor → *Heightmap* panel → *Pack*;
   the exact label varies by patch — it is the action that regenerates the
   compressed topology). It writes, into the mod's `map_data/`:
   - `packed_heightmap.png`
   - `indirection_heightmap.png`
   - `heightmap.heightmap`
4. **Save** from the editor.

### 2. Commit only the intended files

```
git diff --stat map_data/
```

Commit `packed_heightmap.png`, `indirection_heightmap.png`, and
`heightmap.heightmap`. If the editor also rewrote `province_terrains.txt`,
`nodes.dat`, or anything else, **do not commit those in S2** — revert them
(`git checkout -- map_data/<file>`); they belong to S3/S4. See the top-of-file
rule: after every editor save, `git diff` and commit only what this step lists.

### 3. Boot gate

1. Relaunch the mod and load to the **main menu** (a session is not required for
   the S2 gate — provinces are still vanilla).
2. Open `Documents/Paradox Interactive/Victoria 3/logs/error.log`.
3. **Gate: zero lines referencing this mod's files.** If the game does not show
   the new relief, or the log complains that `map_data` was not overridden, the
   mod may need `replace_paths="map_data"` in `.metadata/metadata.json` earlier
   than planned — note it and raise it; the S4 scaffold adds `replace_paths`
   anyway. Fix the **source** (the generator or the registration data), never the
   `error.log` or a game-owned file.

---

<!-- ## S4 — nodes.dat + session boot -->
<!-- ## S5 — object locators + spline regeneration -->
