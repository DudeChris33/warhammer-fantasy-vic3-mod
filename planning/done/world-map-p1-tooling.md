# World Map — P1: Tooling Scaffold

| Field | Value |
|-------|-------|
| Type | request (child of [world-map.md](world-map.md)) |
| Status | planned |
| Date | 2026-07-20 |
| Priority | high |
| Phase | 1 of 6 (P1–P4 planned; P5–P6 to be planned after P3/P4 outputs exist) |
| Gate | **Offline** — fixture pipeline + validators pass; **no game-read files touched** |

Child build file of the world-map master plan. `/build` this first. Pipeline model (user-confirmed 2026-07-20): **all map bitmaps are generated in code** — I hand-encode the world's geometry (coastlines, relief, rivers, state cells) as committed data under `tools/`, and generator scripts rasterize it. No human painting; the only human steps in the whole project are the Victoria 3 desktop-client ones (map-editor repack, session validation), which start in P2.

## Description

Stand up the `tools/` generator + validator toolchain and the geometry-data schema that P2–P6 depend on, and prove the whole code path end-to-end on a **synthetic fixture world** — entirely offline. This phase writes nothing the game loads: every file lives under `tools/`, which is kept out of mod content folders (`common/`, `map_data/`, `gfx/`, `localization/`).

---

## Plan

### Objective
Establish a deterministic, reproducible Python toolchain (`tools/`) — geometry schema, rasterization libs, generators' shared scaffolding, and a map validator — verified on a tiny synthetic fixture, so every later phase generates map data from committed source rather than opaque binaries.

### Steps (ordered)
1. **`tools/requirements.txt`** — pin the stack: Python 3, `Pillow`, `numpy`. Exether already ships Python tooling (`state_validator.py`, `convert_png_to_dds.py`), so the toolchain is precedented here. No other deps.
2. **`tools/config/map_config.py`** — the single source of determinism knobs: committed integer `SEED`; canvas dims `PROVINCES_SIZE = (8192, 3616)` and `HEIGHTMAP_SIZE = (16384, 7232)`; id bands `LAND_ID_START = 1`, `SEA_ID_START = 3000`; `WRAP_X = True`; the `# AUTOGEN` marker string. **Determinism rules baked in:** every generator seeds its RNG from `SEED` only, iterates over sorted keys, and never reads wall-clock, filesystem entropy, or OS state (per [core.md](../../.claude/rules/core.md)).
3. **`tools/worldgen/schema.py`** — define + document the geometry-data schema consumed by later phases (validated on load, not just duck-typed):
   - `coastlines` — list of landmass polygons in `provinces.png` canvas coords (with hole support for inland seas); the canonical land/sea boundary shared by P2 (heightmap) and P3 (provinces).
   - `relief` — `sea_level`, mountain ridge polylines with heights, coastal falloff distance, seeded fractal-noise params.
   - `rivers` — named polylines.
   - `states` — per-state: `key` (`STATE_*`), macro-file, seed geometry (polygon or seed-point set) inside the land mask, `coastal` flag, `naval_exit` sea key, placeholder economics block, optional `impassable` sub-region.
4. **`tools/worldgen/raster.py`** — shared rasterization/geometry libs: indexed-PNG read/write with **no anti-aliasing and no lossy re-save** (every pixel an exact `xRRGGBB`); globally-unique color allocator (deterministic sequence, skips reserved sea band collisions); **wrap-aware** point/segment distance at the `x=0/x=8191` seam.
5. **`tools/validate_map.py`** — the pre-commit map linter. Port the two checks from Exether's [`state_validator.py`](../../../realms-of-exether/map_data/state_validator.py) (province claimed by exactly one state; each declared hub is one of the state's own provinces) and add:
   - `port`/`naval_exit_id` present **iff** the state has coastal pixels; `naval_exit_id` points at a real sea-zone id.
   - degenerate-province detection (1-pixel / sub-threshold / disconnected cells).
   - `provinces.png` ↔ state-file color cross-check **both directions** (no province color missing from all state files; no state color absent from the bitmap).
   - id-band conformance (land ≥ 1, sea ≥ 3000, no overlap) and lakes-not-in-any-state.
   - loc-key coverage (every `STATE_*` / sea / `region_*` key has a `localization/english/map/` entry).
   - Paths come from **argparse**, defaulting to repo-relative — **no hardcoded absolute path** (this fixes the anti-pattern at `state_validator.py:139`, which would also violate the [core.md](../../.claude/rules/core.md) "no personal absolute paths" rule if copied).
6. **`vic3-tiger.conf`** (repo root) — adapt Exether's [`vic3-tiger.conf`](../../../realms-of-exether/vic3-tiger.conf) (community linter config) to this mod's `replace_paths` set. Committed now; wired into the workflow from P4 onward (P1–P3 touch no game-read files it would lint).
7. **`tools/fixtures/`** — a tiny synthetic world (small canvas, 2 landmasses, ~4 states incl. one coastal + one with an impassable cell) as committed geometry JSON, plus its expected generator outputs, so the full path (schema → raster → province subdivision stub → state-file text → validators) is exercised with zero game dependency and regression-checked byte-for-byte.
8. **`tools/MAP_RUNBOOK.md`** — skeleton of the click-by-click desktop-client runbook (map-editor repack, `terrain.regenerate`, session validation); grows one section per phase, starting empty (P1 has no game step).
9. **`tools/PROVENANCE.md`** — running list of the published cartography consulted when I encode geometry (Warhammer Fantasy Wiki / Lexicanum, GW Old World map, TW:Warhammer campaign map), so IP provenance is auditable **without committing any reference image** (per the request's IP/asset-provenance constraint).

### Design Decisions
- **Toolchain = Python + Pillow + numpy**: precedented by Exether's own Python scripts; Pillow gives exact indexed-PNG control (critical — `provinces.png` must be pixel-exact); numpy for the heightmap/Voronoi array math in P2/P3.
- **One seed, committed**: `SEED` lives in `map_config.py` so any regeneration reproduces byte-identical output — the determinism guarantee that makes the generated bitmaps MP-safe by construction.
- **Geometry as committed data, not opaque bitmaps**: the schema (step 3) is the reproducibility contract from the master plan — the whole map must be regenerable from `tools/` + one documented manual pass.
- **Validator is Python, supersedes the PowerShell port**: Exether's [`validate_provinces.ps1`](../../../realms-of-exether/tools/validate_provinces.ps1) (hub-in-provinces only) is folded into `validate_map.py`; one validator, richer checks, cross-platform.
- **`tools/` stays out of loaded content**: Exether ships `.py` inside `map_data/` without issue, but we keep shipped folders clean — the game never parses `tools/`.

### Edge Cases
- Color allocator exhausting or colliding with the reserved sea band → allocator asserts and fails loudly rather than emitting a dupe.
- Fixture must exercise the wrap seam (a state straddling `x=0`) so the wrap-aware distance metric is covered before the real world uses it.
- A generator importing wall-clock/`random` without the seed → add a lightweight determinism self-check in the fixture run (re-run twice, diff outputs).
- Windows path handling — argparse defaults resolve repo-relative via `pathlib`, never a drive-letter literal.

### Testing
- `python tools/validate_map.py --fixture` (or equivalent) over `tools/fixtures/` passes all checks.
- Full fixture pipeline run reproduces the committed expected outputs byte-for-byte on a second run (determinism check).
- `vic3-tiger.conf` parses (dry run).
- **No game load required and none possible** — P1 writes nothing under `common/`, `map_data/`, `gfx/`, `localization/`, so there is nothing for `logs/error.log` to report. This is the one phase whose gate is purely offline (see [testing.md](../../.claude/rules/testing.md)).

### Docs to Update
- `CLAUDE.md` project-layout table — add a `tools/` row (generator/validator scripts + runbook; not loaded by the game).
- `.claude/rules/testing.md` — add: run `python tools/validate_map.py` before committing any map text.
- `.claude/rules/scripting.md` (Naming) / `.claude/rules/localization.md` — no change yet; the `wh_` prefix + `localization/english/map/` conventions are recorded when the first such files land in P3.

---

## Resolution
- **Date**: 2026-07-20
- **Status**: done
- **Summary**: Stood up the offline `tools/` toolchain and proved it end-to-end on a synthetic fixture. Nothing game-loaded was touched — the phase writes only under `tools/` plus `vic3-tiger.conf`. Delivered: the determinism config (`config/map_config.py`, committed `SEED`), the validated-on-load geometry schema (`worldgen/schema.py`), the shared raster/geometry libs (`worldgen/raster.py` — lossless RGB-PNG IO, deterministic globally-unique colour allocator, wrap-aware distance/Voronoi/polygon-fill/connectivity), state-region text emission + hub auto-pick (`worldgen/statefile.py`), the map linter (`validate_map.py`, argparse repo-relative paths — fixes the hardcoded-path anti-pattern), the fixture pipeline runner (`run_fixture.py`) with a committed synthetic world + byte-exact golden outputs, the adapted `vic3-tiger.conf`, and the `MAP_RUNBOOK.md` / `PROVENANCE.md` skeletons. The fixture exercises the seam, a coastal state, a landlocked state, and an impassable sub-region.
- **Files changed**:
  - New: `tools/requirements.txt`, `tools/.gitignore`, `tools/config/{__init__,map_config}.py`, `tools/worldgen/{__init__,schema,raster,statefile}.py`, `tools/validate_map.py`, `tools/run_fixture.py`, `tools/fixtures/README.md`, `tools/fixtures/world/**` (coastlines/relief/rivers/states JSON), `tools/fixtures/expected/**` (golden outputs), `tools/MAP_RUNBOOK.md`, `tools/PROVENANCE.md`, `vic3-tiger.conf`, `.gitattributes`.
  - Modified: `CLAUDE.md` (project-layout `tools/` row), `.claude/rules/testing.md` (offline map-lint note).
  - Also committed the world-map plan of record (`world-map.md` + P2–P4 child files).
- **Tests** (all offline — P1 touches no game-read files, so there is nothing for `logs/error.log` to report; this is the one phase whose gate is purely offline):
  - `python tools/run_fixture.py --check` → determinism (two runs byte-identical), regression (matches committed golden), and `validate_map` all checks pass.
  - `python tools/validate_map.py --fixture` passes standalone.
  - Validator teeth confirmed via 5 negative mutations (missing naval_exit, foreign hub, landlocked-with-port, duplicate province claim, missing loc entry) — each flagged; plus a schema negative test (coastal-without-naval-exit rejected on load).
  - `vic3-tiger.conf` brace-balanced (tiger itself runs from P4; not installed here).
- **Commit**: `fef6ccd` (build); resolution + move-to-done in the follow-up commit.
