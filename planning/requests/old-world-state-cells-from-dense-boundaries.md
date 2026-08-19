# Carve the Old World into state-region cells from the newly-registered dense boundaries

| Field | Value |
|-------|-------|
| Type | request |
| Status | planned |
| Date | 2026-08-15 |
| Priority | high |

## Description

Advance the S3a **state-label layer** (`tools/generate_state_labels.py` →
`tools/derived/state_labels.png`) by feeding it the interior boundary lines from
the recently-registered dense Old World chloropleth. Concretely: wire the four
paired-anchor-dot per-region registrations of `tww3_old_world_mod_parchment.png`
into the boundary-source stack so their region lines actually **cut cells**, then
re-run the extraction and carve the **Old World** — the Empire, Bretonnia,
Kislev/Norsca, and the Darklands — into named state-region cells at vanilla-order
density (~659 land / ~103 sea across the whole map; per-region minimums from
`tools/regions/named_regions.json` for the Old World macros).

This is the "layer S3b cuts ~40k provinces from" — **not** `map_data/provinces.png`
itself (that remains a later step). The deliverable is a re-cut, gated
`state_labels.png` whose Old World reads as a real map, replacing the last
rendered result the user rejected ("all swirly, Bretonnia is 3 states"). The rest
of the world keeps its current IE / `tww3_colored` cells this round.

## Context

The state-label generator already exists and runs whole-canvas, but its last
commit was WIP "blocked on macro grouping" (3d3d88e), and the last overlay the
user saw was rejected on sight. Since then the project cleared the **map
registration landmark wall** with the user's paired-anchor-dot workflow (see
[[project-map-registration-landmark-wall]]): the dense Old World mod parchment
was carved into region crops and each was placed against the traced-coastline
mask —

- `tww3_old_world_mod_parchment_empire.png` (record committed)
- `tww3_old_world_mod_parchment_bretonnia.png` — actually the whole SW block
  (Bretonnia + Estalia + Tilea) (record committed)
- `tww3_old_world_mod_parchment_kislev_norsca.png` (record committed)
- `tww3_old_world_mod_parchment_dark_lands.png` (seed **and** record currently
  **untracked** on the working tree — commit as part of this work)

`tools/SOURCES.md` records all four as *"Places the tile only … contributes no
coastline and no geometry yet; boundary extraction deferred to S6."* **This
request ends that deferral for the Old World.** The source itself is described in
the manifest as a *"Denser Old World boundary network — a line chloropleth,
markedly denser than IE over the same arc"* — exactly the interior-boundary
signal the generator was missing where IE alone left the Old World too coarse.

Why now: the boundary source is finally placed accurately (per-region local warps,
exact at every user dot), the coastline authority is settled
(`tools/derived/land_sea_mask.png`, trace-derived), and the macro/naming source
(`total_war_states_per_strat_region.jpg`, `ie_macro_grouping` role) is back in the
manifest — so the pieces the extraction needs are all in place for the first time.

Doctrine that governs this work (do not relitigate):
- The **rendered overlay is the real gate**, offline-green is only a precondition
  (see [[feedback-visual-artifact-is-the-real-gate]] and CLAUDE.md Autonomy model).
- The **mask is the sole coastline authority** — the new sources add interior
  boundaries only; nothing here moves a shoreline (SOURCES.md decision #1).
- The map is judged by **named-region requirements**, not global stats (see
  [[project-map-regions-named-requirements]]): the Old World macros carry explicit
  minimums (Empire ≥30, Bretonnia ≥15, Kislev ≥10, Darklands ≥30) plus named
  single-state requirements (Laurelorn Forest, Middle Mountains, the Moot in the
  Empire; Crater of Zharr ≥10 in the Darklands).

## Acceptance Criteria

- [ ] The four `tww3_old_world_mod_parchment_*` per-region records are consumed by
      the boundary-source stack (added to `BOUNDARY_SOURCES` with an extraction
      kind), each with a `boundaries` precedence **above** IE (100) and
      `tww3_colored` (95) within its own footprint, and each clipped to its crop's
      **alpha>0 footprint** (the crops carry an intentional binary alpha mask —
      transparent = excluded regions; extraction must not invent cells there).
- [ ] `tww3_old_world_mod_parchment_dark_lands.{seed,record}.json` are committed
      (currently untracked), and `tools/SOURCES.md` is updated to flip each of the
      four crops from "no geometry yet / deferred to S6" to "boundary source"
      (and `--update-manifest` run if any source bytes changed — not otherwise).
- [ ] Re-running `python tools/generate_state_labels.py` produces a
      `state_labels.png` in which the **Old World** (Empire, Bretonnia+Estalia+Tilea,
      Kislev/Norsca, Darklands) is carved at vanilla-order density — the "swirly /
      Bretonnia = 3 states" failure is gone and each Old World macro's cell count
      meets or exceeds its `named_regions.json` `min_states` (or the shortfall is
      reported honestly in `COVERAGE.md` with the source-coverage reason).
- [ ] Macro grouping runs (not the degraded "every cell macro 0" path) so Old
      World cells bind to the correct named macro via `named_regions.json` anchors —
      or, if macro grouping is still blocked, the block is diagnosed and its cause
      named rather than shipped degraded.
- [ ] The rendered overlay (`--preview` / `render_named_map.py` / a qa render) is
      **sent to the user and accepted** before anything is committed. No map bitmap
      is banked on offline checks alone.
- [ ] Offline gate green before the visual is even offered:
      `python tools/worldgen/sources.py --verify`,
      `python tools/validate_map.py --labels`,
      `python tools/run_fixture.py --check` (add/extend a boundary fixture if the
      extraction path gains a new kind).
- [ ] Rest-of-world cells are **not degraded** by the change — a source only adds
      density inside its footprint, so Cathay/Lustria/Naggaroth/etc. should be
      byte-unchanged or measurably no worse; confirm in `COVERAGE.md`.

## Investigation

- **What exists**:
  - `tools/generate_state_labels.py` — the S3a generator. Boundary stack is the
    explicit dict `BOUNDARY_SOURCES` (currently
    `{"tww3_colored.png": "flat_colour", "tww3_ie_parchment.jpg": "ink_bridged"}`,
    [generate_state_labels.py:109](tools/generate_state_labels.py)), extraction
    kinds `flat_colour` / `ink` / `ink_bridged`, per-source `BOUNDARY_EXCLUDE`
    panels, precedence from each registration's `precedence_for("boundaries")`,
    macro grouping via `assign_macros` (`ie_macro_grouping` role, degrades to macro
    0 if absent — [generate_state_labels.py:320](tools/generate_state_labels.py)),
    density reconciliation (`TARGET_LAND_STATES = 659`, `MIN/MAX_AREA_FRACTION`,
    `SLIVER_FRACTION`, `MIN_CELL_AREA`), and `COVERAGE.md` per-macro reporting. Its
    own header already names `tww3_old_world_mod_parchment.png` as the recommended
    densifier ([generate_state_labels.py:532](tools/generate_state_labels.py)).
  - `tools/registration/tww3_old_world_mod_parchment_{empire,bretonnia,kislev_norsca}.json`
    (committed) + `_dark_lands.json` (untracked) — the four per-region records,
    `objective=landmarks`, placed via user anchor dots, alpha-masked footprints.
    Matching seeds under `tools/registration/seeds/`.
  - `tools/worldgen/{cells,macro,parchment,raster,schema,sources,register}.py` —
    the extraction/warp/stack/macro machinery the generator calls.
  - `tools/regions/named_regions.json` — name→anchor→`min_states` bindings; the
    acceptance test for the Old World macros.
  - `tools/derived/{state_labels.png,state_labels_index.json,COVERAGE.md,land_sea_mask.png}`
    — current (stale, pre-source) outputs to reproduce and beat.
- **What changes** (all under `tools/`, none in game content):
  - `tools/generate_state_labels.py` — extend `BOUNDARY_SOURCES` with the four
    crops + their extraction kind; likely per-source footprint handling (alpha
    mask) if not already applied for cropped sources; possibly `BOUNDARY_EXCLUDE`
    entries for the crops' excluded vignettes.
  - The four per-region **registration records** — likely need a `boundaries`
    precedence added (they were authored `objective=landmarks` "no geometry"), and
    `_dark_lands` committed. Re-derive from seeds via `tools/fit_registration.py`
    if the seed changes; **do not hand-edit records**.
  - `tools/worldgen/*` — only if the ink extraction / footprint-clip / precedence
    stack needs a new capability for an alpha-masked crop source (a `/plan` call).
  - `tools/SOURCES.md` — Role cells for the four crops flipped to boundary sources;
    manifest refresh only on an intentional source-byte change.
  - `tools/run_fixture.py` fixtures — extend the boundary fixture set if a new
    extraction kind or footprint path is added.
- **Constraints**:
  - **Alpha-masked crops.** `.convert("RGB")` silently drops the intentional alpha
    footprint (the exact bug called out in
    [[project-map-registration-landmark-wall]]); extraction and precedence-stack
    must honor `alpha>0` as the source's contributing region, or cells will bleed
    into deliberately-excluded areas.
  - **Precedence, not blending.** Boundary layers stack by precedence and are never
    blended; the crops must out-rank IE only *inside their footprint* so the rest
    of the world is untouched.
  - **Macro grouping may still be the blocker.** Commit 3d3d88e shipped WIP
    "blocked on macro grouping"; `total_war_states_per_strat_region.jpg`
    (`ie_macro_grouping`) has since been restored. `/plan` must re-run current
    output first and confirm whether macro grouping now runs or is still degraded —
    reproduce before changing (regression rule, testing.md).
  - **Density reconciliation can hide the source.** `SLIVER_FRACTION` /
    `MIN_AREA_FRACTION` were tuned against IE-only cells; a denser source may trip
    the split/merge thresholds differently (the S3a precedent: a sliver threshold
    above the median cell deleted half the traced network — see
    [[feedback-visual-artifact-is-the-real-gate]]). Watch the before/after in
    `COVERAGE.md`.
  - **Determinism.** `state_labels.png` must stay byte-deterministic (re-run →
    identical). No non-seeded randomness. It is a `tools/derived` intermediate not
    loaded by the game, but it is the seed for the MP-synced `provinces.png` later,
    so it inherits the determinism requirement.
  - **Old World first is a gate scope, not a canvas restriction.** The generator
    still runs whole-canvas; "Old World first" means the acceptance/visual verdict
    is on those four macros this round, and the new sources only add density within
    their Old World footprints.
- **Related files**: `tools/generate_state_labels.py`,
  `tools/registration/tww3_old_world_mod_parchment_*.json` (+ seeds),
  `tools/regions/named_regions.json`, `tools/SOURCES.md`,
  `tools/worldgen/{cells,macro,parchment,raster,schema,sources,register}.py`,
  `tools/fit_registration.py`, `tools/qa_overlay.py`, `tools/render_named_map.py`,
  `tools/validate_map.py`, `tools/run_fixture.py`,
  `tools/derived/{state_labels.png,COVERAGE.md,land_sea_mask.png}`.
- **Endpoints/commands**:
  - Re-derive a record (only if a seed changes): `python tools/fit_registration.py --seed <stem>`.
  - Generate: `python tools/generate_state_labels.py --preview`.
  - Visual: `python tools/render_named_map.py` / `python tools/qa_overlay.py <source>` → send the PNG.
  - Gate: `python tools/worldgen/sources.py --verify`,
    `python tools/validate_map.py --labels`, `python tools/run_fixture.py --check`.
- **Tests required**: after every generator run, the three offline checks above;
  confirm each new boundary source's coverage % and precedence in the run log /
  `COVERAGE.md`; confirm Old World macro cell counts against `named_regions.json`
  `min_states`; confirm rest-of-world macros are byte-unchanged or no worse; a
  `run_fixture.py` fixture for any new extraction/footprint path. The real gate is
  the rendered overlay, accepted by the user.
- **Out of scope**:
  - `map_data/provinces.png` and `map_data/state_regions/*.txt` (the S3b province
    subdivision + text) — this request stops at the state-cell layer.
  - Wiring the non-Old-World sources (`colored_globe`, `named_globe`,
    `the_empire_*`, `start_warhammer_*`, `mega_detailed_*`) into boundaries.
  - Re-fitting any registration against the coastline (the crops are already
    placed and accepted; only a `boundaries` precedence may be added).
  - Any heightmap / rivers / coastline change — the mask stays authoritative.
  - Canon naming of individual states (S6); the sub-region single-state
    requirements (Laurelorn, Middle Mountains, the Moot, Crater of Zharr) are
    *measured/reported* here, authored later.
- **Localization needed**: **none.** This is offline `tools/` work producing a
  derived bitmap with placeholder `STATE_MACRO..` keys; it authors no user-facing
  loc keys and touches no `localization/`, `common/`, `events/`, or `gui/`. Real
  state loc arrives with the S3b province/state-region text.

## Open questions for /plan

1. **Extraction kind for the crops** — `ink` vs `ink_bridged`? The Old World mod
   parchment is a textured line chloropleth like IE (lettering bridged into
   barriers), so `ink_bridged` is the likely match; confirm against the source and
   the `INK_WINDOW`/`INK_OFFSET`/`MIN_SOURCE_CELL` params, which were tuned for IE.
2. **Where the alpha footprint is enforced** — in `extract_source_cells`, in the
   warp/stack, or in the record's declared footprint. Pick one authority so a crop
   never contributes outside `alpha>0`.
3. **Is macro grouping actually unblocked** now that
   `total_war_states_per_strat_region.jpg` is restored? Re-run current output first
   and decide whether this request also has to fix macro grouping or merely relies
   on it.
4. **Precedence values** for the four crops relative to IE (100) and `tww3_colored`
   (95), and whether all four share one value or differ.

## Plan

### Objective
Wire the four `tww3_old_world_mod_parchment_*` per-region crops into
`generate_state_labels.py`'s boundary stack as alpha-clipped, above-IE
`ink_bridged` sources, so their dense region lines cut real Old World state cells —
replacing the rejected "swirly / Bretonnia = 3 states" result — while honestly
diagnosing (not fixing) the still-blocked macro grouping.

### State reproduced first (regression rule, testing.md)
- **Offline gate is currently RED** — `python tools/worldgen/sources.py --verify`
  reports 4 errors: (a) `registration 'tww3_old_world_mod_parchment_dark_lands.png'
  has no row in SOURCES.md` (the untracked dark_lands record points at an
  unmanifested source); (b/c) `terraqueous_globe_reprojected - dots_4.png` and
  `tww3_old_world_mod_parchment - dots_4.png` SHA/dims drift (user re-exported the
  dot-picking scratch — `1962→1965` px etc.), non-consumed but carry manifest rows.
- **Macro grouping is still blocked, and for a different reason than the code
  states.** `assign_macros` searches for role `ie_macro_grouping`; **no record
  carries it** ([generate_state_labels.py:331](tools/generate_state_labels.py)). The
  only macro source is `ie_named_regions.json` (role `named_macro_regions`, source
  `total_war_states_per_strat_region.jpg`), a **0.553-scale `frame_alias`** of the
  parchment master. `macro.annotation_mask` differences the twin against the master
  pixel-for-pixel (`twin.shape == clean.shape`), so a rescaled alias cannot feed it —
  pointing the code at it would raise `MacroError`, not group. The current skip
  message ("nothing registered in its place") is stale/false.
- **Re-fitting the crops is safe.** All four are `objective=landmarks` (thin-plate
  through fixed user anchor dots); a re-run reproduces identical control points, and
  the seed's `record.layer_precedence` rides through `fit_registration._emit`
  unchanged ([fit_registration.py:376](tools/fit_registration.py)). So precedence is
  edited in the **seed**, then re-derived.
- **Alpha is dropped today.** `sources.load_source_image` does `.convert("RGB")`
  ([sources.py:286](tools/worldgen/sources.py)); the record `footprint` is the
  *lattice bbox* (includes transparent corners — [fit_registration.py:383](tools/fit_registration.py)),
  so it cannot stand in for the alpha mask. Per-pixel alpha must be honored explicitly.

### Decisions taken with the user (2026-08-15)
- **Macro grouping: diagnose + defer.** Name the real cause in code + `COVERAGE.md`;
  count Old World cells via the crop footprints. No `macro.py` re-tooling this round.
- **Global target may drift into the 600–700 band.** Prefer satisfying Old World
  `min_states` over snapping the total to 659 and merging Old World cells away.
- **Crop boundary precedence: 110 / 111 / 112 / 113** (empire / bretonnia /
  kislev_norsca / dark_lands), distinct (`stack_layers` rejects ties globally),
  comfortably above IE(100) and `tww3_colored`(95).

### Steps (ordered)
1. **[tools/worldgen/sources.py](tools/worldgen/sources.py)** — add
   `load_source_image_rgba(filename, …) -> (rgb, alpha|None)`: same SHA-256 guard as
   `load_source_image`, opens with PIL, splits the alpha plane (returns `None` when
   the source is opaque). The **single authority** for a crop's real footprint.
   Leave `load_source_image` untouched.
2. **[tools/worldgen/cells.py](tools/worldgen/cells.py) — `warp_cells`** — add
   optional `src_valid: np.ndarray | None`. When given, warp it nearest alongside the
   labels and `covers &= warped_valid`. Load-bearing: stops a crop from suppressing
   IE/`tww3_colored` in its own transparent holes (a hole would otherwise blank the
   lower layer via `stack_layers`, then get Voronoi-filled). Default `None` keeps
   every existing caller and the boundary fixture byte-identical.
3. **[tools/generate_state_labels.py](tools/generate_state_labels.py)**
   - Extend `BOUNDARY_SOURCES` with the four crops. Generalize its value from a bare
     kind-string to allow an optional per-source ink-params override, so the crops
     carry their own window/offset/glyph bounds without disturbing the IE master's
     tuned constants (start by reusing the master's; tune only if the render shows
     the finer Old World lines/letters mis-thresholding).
   - `extract_source_cells`: for a crop, load via `load_source_image_rgba`, zero
     labels where `alpha==0`, and return the `alpha>0` mask as `valid`.
   - `build_layers`: thread each crop's `valid` into `warp_cells`.
   - **Old World per-macro counts without the blocked twin:** in `render_coverage`,
     report the land-cell count whose majority area falls inside each crop's warped
     `alpha>0` footprint, against `named_regions.json` `min_states` (Empire ≥30,
     Bretonnia+Estalia+Tilea ≥15, Kislev ≥10, Darklands ≥30). The crops **are** the
     Old World macro footprints, so this measures density directly.
   - `assign_macros`: replace the stale skip message with the accurate diagnosis (a
     macro source exists — `named_macro_regions` — but it is a 0.553-scale
     `frame_alias`, incompatible with the pixel-difference path, which needs a
     frame-aligned twin). Same wording into the `COVERAGE.md` macro section.
   - **Global-target drift:** relax the snap so the total may land in the 600–700
     band when the Old World needs it (e.g. widen `merge_to_target`'s tolerance /
     raise the effective target rather than forcing 659). Exact mechanism settled in
     the loop; the intent — never merge a legitimate Old World cell away to hit 659 —
     is fixed.
4. **The four seeds** `tools/registration/seeds/tww3_old_world_mod_parchment_*.json`
   — set `record.layer_precedence.boundaries` to 110/111/112/113; leave
   `coastline`/`relief` at their provisional lows (crops contribute neither).
   Re-derive each record: `python tools/fit_registration.py --seed <stem>` (never
   hand-edit the records).
5. **[tools/SOURCES.md](tools/SOURCES.md)** — run
   `python tools/worldgen/sources.py --update-manifest` (sanctioned: user added the
   dark_lands crop and re-exported the dots scratch). By hand: fill Origin/Role for
   `_dark_lands` and `_kislev_norsca` (currently TBD) and flip all four crop Role
   cells from "no geometry yet / deferred to S6" to boundary-source language. Commit
   the untracked `_dark_lands.{seed,record}.json`.
6. **[tools/fixtures/boundary/](tools/fixtures/boundary)** — extend the fixture for
   the alpha path: add a small RGBA synthetic crop (a transparent hole over the base
   parchment) + its registration fixture at a precedence above the base in
   `make_source.py`; in `run_fixture.build_boundary`, load it via the new RGBA loader
   and assert (a) it contributes cells only where `alpha>0`, and (b) the base layer's
   cell **survives** inside the crop's transparent hole. Regenerate `expected/` via
   `python tools/run_fixture.py --update`.

### Design Decisions
- **Alpha authority = the loader, enforced in two consumers** (extraction: no cells
  where transparent; coverage: `warp_cells` `src_valid`). The footprint box is the
  lattice bbox and cannot be the authority. (Open question 2 resolved.)
- **`ink_bridged` extraction kind** for the crops — same textured-line-chloropleth
  idiom as IE, with a per-source params override for scale differences. (Open
  question 1 resolved.)
- **Precedence lives in the seeds**, re-derived through `_emit`; records stay
  machine-fitted. (Open question 4 resolved: 110–113.)
- **Macro grouping diagnosed, not fixed** (Open question 3 resolved): re-tooling
  `macro.py` to warp/rescale the alias into the master frame is a separate request.

### Edge Cases
- **Global target couples regions.** Adding hundreds of Old World cells shifts
  `merge_to_target`'s per-round thresholds, so rest-of-world will **not** be
  byte-identical — honest target is "measurably no worse," reported as before/after
  macro deltas in `COVERAGE.md`. The 600–700-band decision covers the total.
- **Crop ink-params scale.** Old World lines/letters sit at a different px scale than
  the IE master; `GLYPH_MAX_SIDE`/`GLYPH_MIN_HEIGHT` may need per-crop values — the
  params override, tuned in the loop against the render.
- **Crop footprint overlap** (empire/dark_lands boxes overlap) is harmless: alpha
  masks are disjoint and distinct precedence resolves any shared pixel.
- **Determinism** preserved — nearest-neighbour warp, `_farthest_seeds`, no RNG added.

### Testing
- Offline gate green **before** any render: `python tools/worldgen/sources.py
  --verify`, `python tools/validate_map.py --labels`, `python tools/run_fixture.py
  --check` (with the extended alpha fixture).
- `COVERAGE.md`: Old World per-crop counts ≥ `min_states` (or shortfall named with
  the source-coverage reason); rest-of-world before/after delta; corrected macro
  diagnosis.
- **The real gate is the rendered overlay** (`python tools/render_named_map.py` /
  `python tools/qa_overlay.py <source>`) — sent to the user and accepted before
  anything commits. No map bitmap banked on offline checks alone.
- No in-game `error.log` step: `tools/`-only, produces a `tools/derived`
  intermediate, authors no `common/`/`events/`/`gui/`/`localization/` content.

### Docs to Update
- `tools/SOURCES.md` — crop Role cells + manifest refresh (Step 5).
- `tools/derived/COVERAGE.md` — regenerated with the Old World per-crop counts and
  corrected macro section.
- `.claude/rules/*` — no change required; if the per-source ink-params override
  becomes a reusable convention, record it in `.claude/rules/` during `/build`.

### Localization
None. This is offline `tools/` work producing a derived bitmap with placeholder
`STATE_MACRO..` keys; it authors no user-facing loc and touches no `localization/`.
Real state loc arrives with the S3b province/state-region text.
