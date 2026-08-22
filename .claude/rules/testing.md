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
`state_regions/`, `default.map`), the map localization, or the
source-registration data (`tools/SOURCES.md`, `tools/registration/`), run:

```
python tools/worldgen/sources.py --verify   # source manifest SHA-256 + registration cross-checks
python tools/validate_map.py --labels        # the state-label layer tiles the land/sea mask exactly
python tools/validate_map.py                # lints the repo map (repo-relative paths)
python tools/run_fixture.py --check          # regression-checks the toolchain itself
```

All must pass before the in-game `error.log` check below. This does not replace
the game load — it catches the offline-detectable class of error first. The
`sources.py --verify` step confirms the local `sources/` files still match the
committed SHA-256 manifest — a swapped or edited source that would silently
change a committed bitmap fails here. Refreshing a source after an *intentional*
change is the explicit `python tools/worldgen/sources.py --update-manifest`
action, never a side effect of a generator run.

`map_data/heightmap.png`, `map_data/rivers.png`,
`tools/derived/state_labels.png` and `tools/derived/sea_zones.png` (+
`tools/derived/sea_zones_index.json`) are generated, not hand-authored: after an
intentional source/LUT/registration/`tools/config/inland_lakes.json` change,
regenerate them with `python tools/generate_heightmap.py`, `python
tools/generate_rivers.py`, `python tools/generate_state_labels.py` and `python
tools/generate_sea_zones.py`, and re-run the checks above before committing.
`generate_sea_zones.py` is decoupled from the land cut — it reads the committed
`land_sea_mask.png` and the hand-drawn purple boundary source directly, and is
not wired into `state_labels.png`.
`--labels` is only meaningful once the state-label layer exists; `validate_map.py`
with no flag needs `map_data/provinces.png`, which arrives in S3b.

Registration records (`tools/registration/*.json`) are machine-fitted, not
hand-written: re-derive with `python tools/fit_registration.py --seed <stem>`
after editing the corresponding seed in `tools/registration/seeds/`. Like
`--update-manifest`, that is an explicit authoring action and never part of the
gate.

`tools/config/inland_lakes.json` is hand-authored geographic data, like a
registration seed: it lists the genuine enclosed lakes/seas to keep as water
(by interior seed pixel) when `generate_heightmap.py` fills false enclosed
water (drawn rivers, flooded marshes) to land. Edit it deliberately and
regenerate the heightmap through it — never infer or hand-edit it from a
regenerated bitmap.

`run_fixture.py --check` also regression-checks the source-driven pipeline itself
against committed synthetic fixtures, independent of the real `sources/`:
`tools/fixtures/ingest/` covers LUT classification, reprojection, segmentation,
compositing and river rasterization; `tools/fixtures/boundary/` covers the
boundary path (local-contrast ink, complement labelling, the `frame_alias` warp,
precedence stacking, mask intersection, nearest-label fill, density
reconciliation and sea zones). It also self-checks `worldgen/sea_zones.py`
in isolation (no golden fixture): a purple line drawn in the water splits it
into zones, a purple mark drawn on land is ignored, every water pixel ends up
labelled and no land pixel does, and two runs are byte-identical.

## Regression rule

When fixing a bug confirmed via `logs/error.log` or in-game behavior, first reproduce it (capture the exact error line or observed behavior) before changing script, so the fix can be verified against the same reproduction step afterward.

## Rules

- Never claim a change is "tested" without having loaded the mod in-game and checked `logs/error.log`.
- Never edit `logs/error.log` or any game-owned file to make an error disappear — fix the source in this mod.
