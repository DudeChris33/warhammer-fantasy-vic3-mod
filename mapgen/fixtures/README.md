# Fixture: synthetic world

A tiny (128×64) hand-built world that exercises the province/state generator +
validator path offline, with **zero game dependency**. `mapgen/run_fixture.py`
rasterizes `world/` into `expected/` and regression-checks it byte-for-byte.

Two further fixtures cover the source-driven front end, each with its own
committed synthetic source (our own pixels, so they run on a clean clone with no
`sources/` present):

| Fixture | Covers | README |
|---|---|---|
| `ingest/` | whole-world ingestion — LUT classification, reprojection, segmentation, compositing, river rasterization (S2) | `ingest/README.md` |
| `boundary/` | the boundary path — local-contrast ink, complement labelling, the `frame_alias` warp, precedence stacking, mask intersection, nearest-label fill, density reconciliation, sea zones (S3a) | `boundary/make_source.py` docstring |

All three run under the same `mapgen/run_fixture.py --check` / `--update`.

## `world/` — committed input geometry

| File | Contents |
|---|---|
| `coastlines/mainland.json` | Big rectangular landmass (holds ALPHA + BETA). |
| `coastlines/driftland.json` | Landmass whose x extends past the canvas width (112→140) — it **wraps the `x=0` seam**. |
| `coastlines/isle.json` | Small island (holds DELTA). |
| `relief.json`, `rivers.json` | Schema-valid relief/river data for this fixture (loaded + validated; not rasterized to pixels here — the whole-world heightmap/rivers pipeline is the separate `mapgen/fixtures/ingest/` fixture above). |
| `states/*.json` | The state-cell partition — see below. |

## The four land states + two sea zones

| State | Role it exercises |
|---|---|
| `STATE_ALPHA` | **Coastal** (gets `port` + `naval_exit_id`) **and** has an `impassable` sub-region carved into its own province. Its polygon has a hole where BETA sits. |
| `STATE_BETA` | **Landlocked** (fully enclosed by ALPHA) — validator confirms it has *no* port / naval exit. |
| `STATE_GAMMA` | **Straddles the `x=0` seam** — covers the wrap-aware distance, polygon fill, coastal detection, centroid, and Voronoi paths at the seam. |
| `STATE_DELTA` | A second coastal state on its own island. |
| `STATE_SEA_WEST`, `STATE_SEA_EAST` | Single-province sea zones (ids 3000+), assigned by nearest-seed Voronoi over the ocean; targets of the `naval_exit_id`s. |

## `expected/` — committed golden outputs

`provinces.png`, `state_regions/*.txt` (+ `99_seas.txt`), `default.map`, and the
localization skeletons. These are byte-for-byte regression fixtures: git is told
not to normalize their line endings (`.gitattributes`), and `run_fixture.py
--check` fails on any drift. Regenerate them with `run_fixture.py --update` after
an intentional generator change, and review the diff.

## Commands

```
python mapgen/run_fixture.py --check     # offline gate: determinism + golden + validators
python mapgen/run_fixture.py --update    # rewrite golden outputs (after intentional changes)
python mapgen/validate_map.py --fixture  # run just the linter over expected/
```
