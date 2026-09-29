# Map Runbook — desktop-client steps

The map pipeline is split between what the `mapgen/` scripts generate in code and
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

> ## ⚠ The map editor writes into the BASE GAME folder
>
> **Observed 2026-07-25, during the S2 repack.** The editor did not confine its
> output to the mod. It wrote into
> `steamapps/common/Victoria 3/game/map_data/`, overwriting the shipped
> `packed_heightmap.png`, `indirection_heightmap.png`, `heightmap.heightmap`,
> `nodes.dat` — **and also `provinces.png` and the whole `state_regions/`
> directory**, none of which the repack step should touch at all.
>
> Consequences, in order of how much they matter:
>
> 1. **Vanilla and every other mod are affected.** The game reads the *packed*
>    heightmap at runtime, so a base install carrying our packed set renders
>    Warhammer terrain in unrelated saves.
> 2. **The originals are gone**, not backed up by the editor. Recover with Steam →
>    Victoria 3 → Properties → Installed Files → **Verify integrity of game
>    files**, which re-downloads exactly the changed files.
> 3. **Do not commit the base-game files into this repo.** The re-saved
>    `provinces.png` / `state_regions/` are vanilla's real-world Earth data; they
>    are not ours, they are not what this mod ships, and committing base-game
>    content is an IP problem as well as simply wrong. Only the packed heightmap
>    set derived from *our* `heightmap.png` belongs here.
>
> **Before running the editor:** back up `game/map_data/` (or be ready to verify
> integrity afterwards). **After running it:** check the base game folder's
> timestamps, not just `git status` in the mod — the mod's working tree looks
> clean precisely because the damage lands outside it.

---

## P1 — Tooling scaffold

**No game step.** P1 is entirely offline: it writes nothing the game loads
(everything lives under `mapgen/` + `vic3-tiger.conf`). Validation is:

```
python mapgen/run_fixture.py --check     # determinism + golden + validators
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
python mapgen/worldgen/sources.py --verify   # sources match the manifest
python mapgen/generate_coastline_mask.py      # -> mapgen/derived/land_sea_mask.png (from the traced coastline)
python mapgen/generate_heightmap.py           # -> map_data/heightmap.png (consumes the mask above)
python mapgen/generate_rivers.py              # -> map_data/rivers.png (from the user's blue river trace; board #3703)
python mapgen/run_fixture.py --check          # determinism + goldens + validators
```

> **Exporting a source (board #5399).** A multi-layer GIMP `.xcf` master gets a
> sibling OpenRaster export: GIMP *File → Export As…* → same folder, same stem,
> `.ora`. Tools then read a concern (coastline trace, rivers, sea zones, state
> borders, impassable terrain) out of it by `stack.xml` layer name, via the ref
> in `mapgen/config/source_layers.json`. The land/sea fill is the one exception —
> export `land_sea_mask.png` as a flat PNG, run it through `binarize_cyan_mask.py`,
> then `sources.py --update-manifest` to pin the new hash.

> **Rivers are source-driven (board #3703), not heightmap drainage.**
> `generate_rivers.py` reads the hand-traced pure-blue (`0,0,255`) river network
> (`terraqueous_globe_reprojected - full.ora#rivers`, via `mapgen/config/source_layers.json`'s
> `rivers` key — board #5399, cyan is reserved for the coastline trace —
> canvas-native, or the layers in `mapgen/config/river_sources.json`) and the
> optional anchor-keyed names
> in `mapgen/config/canon_river_names.json`, not the terrain. Regenerating the real
> `map_data/rivers.png` is a **user-gated visual step**: render it with `python
> mapgen/render_rivers_preview.py`, send the PNG, and only commit the bitmap after
> the user accepts it. Until a trace is accepted, the tooling ships green on the
> `run_fixture.py --check` synthetic fixtures with no new `rivers.png` committed.

Confirm `git status` shows `map_data/heightmap.png`, `map_data/rivers.png`, and
`mapgen/derived/land_sea_mask.png` staged/modified. Everything else in
`mapgen/derived/` is a QA render and is gitignored.

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
git status -s map_data/
```

Commit `packed_heightmap.png`, `indirection_heightmap.png`,
`heightmap.heightmap`, and `nodes.dat` — the set the editor derives from our
`heightmap.png`. (`nodes.dat` was originally deferred to S4, but it is
regenerated by this same pack action and was present for the boot that passed the
gate, so it is committed as part of the validated state; S3/S4 will regenerate it
once real provinces exist.)

**Restore `heightmap.png` if the editor re-saved it.** It did in S2: the file grew
45.9 MB → 50.6 MB. Verified pixel-for-pixel identical, so the editor only
re-encoded the PNG — but the committed copy must stay the *generator's* output, or
it is no longer byte-reproducible from `generate_heightmap.py`:

```
git restore map_data/heightmap.png
```

Anything else the editor touched (`province_terrains.txt`, locators, base-game
files — see the warning at the top) does **not** get committed here.

### 3. Boot gate

1. Relaunch the mod and load to the **main menu** (a session is not required for
   the S2 gate — provinces are still vanilla).
2. Open `Documents/Paradox Interactive/Victoria 3/logs/error.log`.
3. **Gate: zero lines referencing this mod's files.** Fix the **source** (the
   generator or the registration data), never the `error.log` or a game-owned
   file.

**Result (2026-07-25): PASSED.** 381-line log, **zero** lines referencing this
mod, `map_data`, `heightmap`, or any of our files. Its contents were pre-existing
engine/DLC noise (`MISSING_DLC_ENTRY`, `pdx_data_factory` version promotion) plus
other mods' game rules read from old autosaves (`wsr_*`, `bloodtithe_mode`,
`animal_kingdoms`) — none of it ours. The editor also accepted the 16-bit
`heightmap.png` and repacked it without altering a single elevation value, which
independently confirms the format and the measured `4884` / `5.5 units/m`
encoding.

---

## S3a — state-label layer (no desktop step)

S3a touches **no game-read file**: it produces `mapgen/derived/state_labels.png`,
its index, and `COVERAGE.md`, all of which the engine never sees. There is no
editor session and no boot gate. It is listed here only so the absence is
deliberate rather than an omission.

Its gate is offline plus one human judgement:

```
python mapgen/worldgen/sources.py --verify
python mapgen/validate_map.py --labels
python mapgen/run_fixture.py --check
python mapgen/qa_overlay.py --labels          # writes mapgen/derived/qa_state_labels.png
```

then **look at `mapgen/derived/qa_state_labels.png` and read
`mapgen/derived/COVERAGE.md`**. Registration quality is not knowable until the
overlay renders, which is exactly why S3a was split out ahead of S3b: a
control-point correction here costs one re-fit, whereas the same correction after
40k provinces have been cut costs a full regeneration.

Re-deriving a registration is an explicit authoring action, not part of the gate:

```
python mapgen/fit_registration.py --seed <stem>      # rewrites mapgen/registration/<stem>.json
python mapgen/generate_state_labels.py --preview     # then regenerate the layer
```

### S3a — named chloropleth (parchment areas onto the globe)

`world-map-parchment-areas-onto-globe.md` registers the Immortal Empires
parchment master directly (rather than only as the macro-annotated twin's
differencing counterpart) and promotes it to the primary boundary source,
with its lettering *bridged* into the traced barrier instead of erased. Two
new authoring/render commands, both outside the gate:

```
python mapgen/fit_registration.py --seed wh3_dlc_ie_parchment_map_english   # the master itself
python mapgen/render_named_map.py --globe            # local-only globe-space review render
python mapgen/render_named_map.py --tiles            # committed per-macro tiles + index.png
```

`--globe` writes `mapgen/derived/globe_named_review.png` — a copy of
`terraqueous_globe.jpg` with the projected cell network outlined, embedding
source pixels, so it is **never committed** (gitignored by default) and is
the render **sent to the user** for the Stage A visual gate. `--tiles` writes
`mapgen/derived/named/*.png` — flat macro-tinted cells drawn from our own
pixels only, which **are** committed (`mapgen/.gitignore` carries an explicit
negation for `derived/named/`).

Stage B (transcribing the printed names and binding them to cells) is a
separate follow-on request; Stage A's renders show geometry only, unnamed.

**Carry into S4:** `nodes.dat` must be regenerated in the editor once real
provinces exist (S3b). Back up `game/map_data/` before that session — see the
warning at the top of this file.

## S4 — heightmap repack + session boot (the real-province boot)

**Goal of this step:** the offline tools have now cut real whole-world provinces
(`map_data/provinces.png`, board #2773) and emitted every text map-config file —
the sea engine (`99_seas.txt`, `default.map` `sea_starts`,
`water_strategic_regions.txt`, #2929), the land states (`state_regions/*.txt`,
#2930/#2931), a header-only `adjacencies.csv` (#3542), and now
`province_terrains.txt` (#2968). What is still missing is the **compressed
topology the engine actually reads at runtime**: `packed_heightmap.png`,
`indirection_heightmap.png`, a refreshed `heightmap.heightmap`, and a `nodes.dat`
regenerated against the new provinces. Those are **desktop-only** — only the
in-game map editor's repack produces them (exactly as in S2). This step is the
integration close-out of the **#2700 bootable-map milestone**; the offline tools
cannot perform it.

### 0. Offline first (already done by the tools)

Regenerate `province_terrains.txt` alongside the sea/land emitters — a
`generate_provinces.py` regen reshuffles every province colour (#3705), so all
three colour-keyed emitters must re-run together, then re-validate:

```
python mapgen/generate_provinces.py            # -> map_data/provinces.png (+ derived indices)
python mapgen/generate_sea_regions.py          # -> 99_seas.txt + default.map sea_starts + water regions
python mapgen/generate_land_regions.py         # -> state_regions/*.txt + strategic regions + loc
python mapgen/generate_province_terrains.py    # -> map_data/province_terrains.txt (#2968)
python mapgen/worldgen/sources.py --verify
python mapgen/validate_map.py --province-bitmap # now also checks province_terrains coverage
python mapgen/validate_map.py --sea
python mapgen/validate_map.py                   # full crosscheck (land + sea states)
python mapgen/run_fixture.py --check
```

### 1. Repack the heightmap in the map editor

Identical mechanics to S2 §1 — launch with `-debug_mode`, open the **Map
Editor**, trigger the heightmap **repack / pack** action, **Save**. It writes into
the mod's `map_data/`:
- `packed_heightmap.png`
- `indirection_heightmap.png`
- `heightmap.heightmap`
- `nodes.dat` (regenerated for the new provinces)

> **⚠ The editor writes into the BASE GAME folder** — see the warning at the top
> of this file. Back up `game/map_data/` (or be ready to *Verify integrity of game
> files*) before running it, and check the base-game folder's timestamps
> afterwards, not just `git status` in the mod.

### 2. Commit only the intended files

```
git status -s map_data/
```

Commit `packed_heightmap.png`, `indirection_heightmap.png`,
`heightmap.heightmap`, and `nodes.dat`.

- **`git restore map_data/heightmap.png`** if the editor re-encoded it (it did in
  S2 — grew but stayed pixel-identical); the committed copy must remain the
  *generator's* byte-for-byte output.
- **Do NOT commit the editor's own `province_terrains.txt` rewrite.** The map
  editor regenerates that file from *painted* terrain, which this mod does not yet
  have, so its output is garbage. The committed authority is
  `generate_province_terrains.py`'s output (a uniform plains/ocean placeholder);
  `git restore map_data/province_terrains.txt` if the editor touched it.
- Anything else the editor touched (locators, base-game files) does **not** get
  committed here.

### 3. Boot gate

1. Relaunch the mod and **load into a session** (a session is required now —
   provinces, states, and terrain are all real, so main-menu parsing alone won't
   exercise them).
2. Open `Documents/Paradox Interactive/Victoria 3/logs/error.log`.
3. **Gate: zero lines referencing this mod's files, and no crash on map load.**
   Fix the **source** (a generator, the registration data, or a state/terrain
   emitter), never the `error.log` or a game-owned file.

**Result (2026-09-28, board #5525): boot gate PASSED after a different fix.** The pack was
never the cause of the load crash. The crash was an empty starting gamestate (no countries),
which also made the editor itself uncatchable; see `.claude/rules/testing.md`, "Load crash
root cause". Facts learned running this section:

- **The editor needs a loadable gamestate.** It builds the same starting gamestate as a new
  game, so with zero countries in `common/history/` it crashes about 50 seconds after script
  load, before any click. Ship at least one country that owns a state before trying §1.
- **What a Pack + Save writes into the mod** (not just the four pack files): re-encoded
  `heightmap.png` and `provinces.png` (verified pixel-identical to the generator output),
  rewritten `state_regions/99_seas.txt`, the five `generated_map_object_locators_*.txt` and
  `fortification_locators.txt`, a 36-byte `spline_network.splnet`, and about 320 untracked
  `gfx/map/map_object_data/*.bin` files. Commit only the four pack files. Restore the tracked
  rewrites with `git restore --source=HEAD --worktree -- <paths>`; delete the untracked
  `.bin` files with `git clean -f -- 'gfx/map/map_object_data/*.bin'`. A pixel comparison
  (`numpy`/`PIL`, LFS-smudged HEAD copy) is the way to prove a re-encode lost nothing.
- **`heightmap.heightmap` is the editor's output, `should_wrap_x=no`, and stays unedited.** The
  hand-edited `wrap=yes` from `1d66fdd` was not what made the game crash; `default.map`'s
  `wrap_x = yes` is what matters for wrapping.
- **The base install was not damaged.** *Verify integrity* re-acquired about 20 files but every
  `game/map_data/` hash was unchanged; the July file dates come from a Steam patch. Judge by
  hash, never by timestamp, and note that `git status` in the mod cannot see base-game edits.
- **The pack looks stale or wrong in the editor for a separate reason.** The materials, colour
  map, land mask, flat map and vegetation placement still come from vanilla's Earth layers
  under `gfx/map/` (`terrain/detail_index.tga`, `detail_intensity.tga`, `textures/colormap.dds`,
  `flatmap*.dds`, `land_mask.dds`, `dynamic_masks/exclusion_mask.dds`,
  `map_object_data/generated/*`), which the mod does not override. A repack cannot fix those.

<!-- ## S5 — object locators + spline regeneration -->
