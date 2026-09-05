# Testing Rules

There is no compiler and no automated test suite for Clausewitz script — validation happens by loading the mod in Victoria 3 itself.

## Validation procedure

1. Launch Victoria 3 with this mod enabled.
2. Load into a game (main menu script parsing alone won't catch every error — get to a session if the change touches `events/` or `history/`).
3. Check `logs/error.log`, located one level above the game's `mod/` folder — i.e. `Documents/Paradox Interactive/Victoria 3/logs/error.log` (this mod folder is `Documents/Paradox Interactive/Victoria 3/mod/warhammer-fantasy/`).
4. Any new line referencing a file in this mod is a failure. Fix the **script**, not the log.

## Map data (offline pre-commit lint)

Map text and bitmaps additionally have an **offline** validator — there is no
reason to load the game to catch a duplicate province claim or a missing hub.
One-time setup: create a local virtualenv and install the pinned deps — see
`tools/requirements.txt` for the exact commands. The project convention is a
`tools/.venv` (already gitignored) — activate it before running any `tools/`
script. Before committing anything
under `map_data/` (province bitmap, `heightmap.png`, `rivers.png`,
`state_regions/`, `default.map`, `adjacencies.csv`), the water strategic regions
(`common/strategic_regions/water_strategic_regions.txt`), the map localization, or
the source-registration data (`tools/SOURCES.md`, `tools/registration/`), run:

```
python tools/worldgen/sources.py --verify       # source manifest SHA-256 + registration cross-checks
python tools/validate_map.py --province-bitmap   # the province bitmap tiles the mask + agrees with its index and the sea layer
python tools/validate_map.py --sea               # sea engine files: 99_seas colours ⊆ sea_starts ⊆ provinces.png sea colours; every sea state grouped + localized
python tools/run_fixture.py --check              # regression-checks the toolchain itself
python tools/validate_map.py                     # full crosscheck (needs both sea + land states — see below)
```

The `--sea` subset check is the sea-side gate for board #2929's emitted files
(`99_seas.txt`, `default.map` `sea_starts`, `water_strategic_regions.txt`, the sea
loc), useful on its own when only the sea side has changed. The full no-flag
`validate_map.py` needs *every* province colour claimed by a state, land and sea
both — it started passing once board #2930 emitted the land states
(`00_norsca.txt`) alongside the already-shipped sea files, and stays the gate to
run whenever either side changes. **A province-bitmap regen invalidates both
emitted state files, not just the one whose input changed**: `99_seas.txt`'s
colours are `provinces_index.json`-label-keyed (`land_provinces + zone_label`), so
a `generate_provinces.py` run that changes the land province count shifts every
sea colour even though nothing about the sea zones themselves changed — this bit
board #2930 (the committed `99_seas.txt` had gone stale after a source update
regenerated `provinces.png`, 714→708 regions). Re-run **both**
`generate_sea_regions.py` and `generate_land_regions.py` after any
`generate_provinces.py` regen, not just the one whose upstream index moved.

All must pass before the in-game `error.log` check below. This does not replace
the game load — it catches the offline-detectable class of error first. The
`sources.py --verify` step confirms the local `sources/` files still match the
committed SHA-256 manifest — a swapped or edited source that would silently
change a committed bitmap fails here. Refreshing a source after an *intentional*
change is the explicit `python tools/worldgen/sources.py --update-manifest`
action, never a side effect of a generator run.

`tools/derived/land_sea_mask.png`, `map_data/heightmap.png`, `map_data/rivers.png`,
`tools/derived/state_labels.png`, `tools/derived/sea_zones.png` (+
`tools/derived/sea_zones_index.json`) and `map_data/provinces.png` (+
`tools/derived/provinces_index.json` + `tools/derived/land_regions_index.json`, the
region→province grouping) are generated, not hand-authored: after an
intentional source/LUT/registration change, regenerate them with `python
tools/generate_coastline_mask.py` (the sole owner of `land_sea_mask.png` — either
flood-filled from the user's traced coastline in `sources/land_sea_mask.png`, or,
with `--from-fill`, read directly when that source is already a finished
black/white land fill rather than a coastline trace), `python
tools/generate_heightmap.py` (which now *consumes* that mask — the old
height-ramp mask derivation was deleted 2026-08-22), `python
tools/generate_rivers.py`, `python tools/generate_state_labels.py`, `python
tools/generate_sea_zones.py` and `python tools/generate_provinces.py`, and re-run
the checks above before committing. The mask moves first; every downstream layer
is regenerated from it.
The sea engine files `map_data/state_regions/99_seas.txt`,
`common/strategic_regions/water_strategic_regions.txt`, and `map_data/default.map`'s
`sea_starts` block are emitted by `python tools/generate_sea_regions.py` (board
#2929) — it joins `provinces_index.json` (colours) with `sea_zones_index.json`
(canon keys/ids), so regenerate rather than hand-edit them (`default.map`'s other
keys and `adjacencies.csv`'s strait rows stay hand-authored). The old staged
`tools/derived/seas_99_seas.txt` / `seas_sea_starts.txt` are removed.
`map_data/state_regions/00_norsca.txt`, `common/strategic_regions/land_strategic_regions.txt`
and `localization/english/map/wh_land_states_l_english.yml` are emitted the same
way by `python tools/generate_land_regions.py` (board #2930) — it joins
`land_regions_index.json` (708 regions) with `provinces_index.json` and
`sea_zones_index.json` (naval-exit resolution by real land↔sea pixel adjacency);
regenerate rather than hand-edit. All 708 regions land in one file with one
strategic region — the 20-file realm split is deferred to #2931, so nothing here
survives that rewrite. `tools/render_land_regions_preview.py` is the matching
**dev-only** naming aid, outside the gate above: a numbered review PNG + CSV
worksheet, draping the real TWW3 parchment art under the tinted regions via
`tools/project_regions.py`'s existing five-crop registration wherever it covers
the canvas (an `on_parchment` CSV column flags which regions that is), so the
person doing #2931's naming pass reads real printed names off the render
directly. Two earlier automated-guess attempts were tried and dropped
(2026-09-05): nearest real-world vanilla Vic3 state by lon/lat (a coincidental-
Earth-geography heuristic the user rejected outright) and OCR of the parchment
itself (Tesseract garbled almost everything on the stylised, curved-baseline
font even after rotation sweeps, contrast stretching and despeckling). Neither
tool nor its derived output exists any more. `python tools/run_fixture.py --check` also exercises
`worldgen.statefile.stack_hubs`, the hub-stacking fallback `pick_hubs` cannot
cover (a state with fewer passable provinces than it needs — every placeholder
and any small drawn region).
`generate_sea_zones.py` and `generate_provinces.py` are both decoupled from the
land cut — each reads the committed `land_sea_mask.png` and its own hand-drawn
source directly (the purple sea-zone network, the magenta state-region network),
and neither is wired into `state_labels.png`. `generate_provinces.py` (board
#2773) folds the already-committed `sea_zones.png` in as the sea provinces
(labels `N+1..N+M` after land `1..N`); the land side comes from
`tools/worldgen/land_provinces.py`, the land mirror of `worldgen/sea_zones.py` —
it flood-fills the hand-drawn magenta network into barrier-respecting state
regions, then subdivides each drawn region into provinces (no province crosses a
magenta line); an out-of-scope far continent with no interior magenta is
classified a placeholder and kept whole as one passable placeholder province (Vic3
stacks every hub on one province, so a landmass needs only one passable province
to boot as a legal state; `impassable` is uniformly `false` on land, and the
out-of-scope signal is carried separately as the `placeholder` flag).
`worldgen/sea_zones.py`'s `extract` also gained a `split_disconnected`
connectivity repair (the nearest-label fill can tear a zone into two
disconnected pieces sharing one label; `land_provinces.regions` mirrors the
same repair).
`--labels` is only meaningful once the state-label layer exists; the plain
`validate_map.py` (no flag) additionally needs `state_regions/*.txt`, which
hasn't been authored yet (S3b) — until then, `--province-bitmap` is the check
for `map_data/provinces.png` itself.

Registration records (`tools/registration/*.json`) are machine-fitted, not
hand-written: re-derive with `python tools/fit_registration.py --seed <stem>`
after editing the corresponding seed in `tools/registration/seeds/`. Like
`--update-manifest`, that is an explicit authoring action and never part of the
gate.

`tools/config/inland_lakes.json` is hand-authored geographic data, like a
registration seed: it lists the genuine enclosed lakes/seas to keep as water
(by interior seed pixel) when the mask pipeline distinguishes them from false
enclosed water (drawn rivers, flooded marshes). **As of 2026-08-22 no code reads
it**: `generate_coastline_mask.py`, now the sole owner of `land_sea_mask.png`,
classifies enclosed seas as water by coastline parity alone, needing no lake
list. The file (and `schema.load_inland_lakes`) is orphaned pending a decision to
keep or retire it.

`run_fixture.py --check` also regression-checks the source-driven pipeline itself
against committed synthetic fixtures, independent of the real `sources/`:
`tools/fixtures/ingest/` covers LUT classification, reprojection, segmentation,
compositing and river rasterization; `tools/fixtures/boundary/` covers the
boundary path (local-contrast ink, complement labelling, the `frame_alias` warp,
precedence stacking, mask intersection, nearest-label fill, density
reconciliation and sea zones). It also self-checks `worldgen/sea_zones.py`
in isolation (no golden fixture): a purple line drawn in the water splits it
into zones, a purple mark drawn on land is ignored, every water pixel ends up
labelled and no land pixel does, and two runs are byte-identical. It likewise
self-checks `worldgen/land_provinces.py` in isolation: a magenta line drawn on
land splits it into regions while a magenta mark in water is ignored, a
landmass dense with interior magenta is classed drawn and one bare of it a
placeholder, subdividing a drawn region never crosses the magenta boundary
while a placeholder region stays one province, every land pixel ends up
labelled and no water pixel does, and two runs are byte-identical.

## Regression rule

When fixing a bug confirmed via `logs/error.log` or in-game behavior, first reproduce it (capture the exact error line or observed behavior) before changing script, so the fix can be verified against the same reproduction step afterward.

## Rules

- Never claim a change is "tested" without having loaded the mod in-game and checked `logs/error.log`.
- Never edit `logs/error.log` or any game-owned file to make an error disappear — fix the source in this mod.
