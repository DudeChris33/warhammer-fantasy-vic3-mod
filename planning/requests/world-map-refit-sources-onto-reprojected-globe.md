# Refit a subset of source maps onto the reprojected globe (coastline alignment)

| Field | Value |
|-------|-------|
| Type | request |
| Status | planned |
| Date | 2026-08-12 |
| Priority | medium |

## Description

Register — mostly newly — a specific subset of reference maps so their geography
lines up, **by coastline**, with the canvas-space
`sources/terraqueous_globe_reprojected.png`. The reprojected globe is a *faithful*
Miller reprojection of `terraqueous_globe.jpg` (user, 2026-08-12: no geometry
edits), canvas-sized at 8192×3616 = exactly `WIDTH × HEIGHT`. Geometrically it is
therefore identical to the on-the-fly NE-II→Miller reprojection the toolchain
already computes; its value here is as a **canvas-space coastline reference** each
other map can be fitted against.

The user's framing is important and sets the acceptance bar: Warhammer Fantasy
maps are deliberately inconsistent ("unreliable-narrator cartographer" convention),
so these sources **will not line up perfectly** and are not expected to. Success is
each source's coastline placed as closely as *that source* allows, with the
residual measured and recorded honestly — not forced to a hard threshold. Where a
source has no coastline signal a fit can lock onto, that finding is recorded and
the source is marked not-usable-for-geometry rather than given a false placement
(the precedent set for `old_world_terrain.jpg` / `TheEmpire` in S3a).

## Context

The registration mechanism already exists (`tools/fit_registration.py` + seeds in
`tools/registration/seeds/` → committed records in `tools/registration/*.json`),
and coastline/silhouette IoU is already its primary objective. What this request
does is point that machinery at a named subset of sources, using the reprojected
globe as the coastline reference, and produce/refresh their committed records.

Current anchor chain (for context — see `SOURCES.md` "The Terraqueous Globe is the
most trusted source"):

- Silhouette objective = `tools/derived/land_sea_mask.png` (the globe's coastline,
  reprojected on the fly from `terraqueous_globe.jpg`).
- Landmark anchor side = pixels picked on `terraqueous_globe.jpg`, pushed through
  its committed NE-II fit to canvas px.

Because the reprojected PNG is a faithful reprojection, "align coastline to the
reprojected globe" and "silhouette-fit against `land_sea_mask.png`" are the **same
comparison** geometrically. Whether the fitter reads the reprojected PNG directly
or keeps using `land_sea_mask.png` is a mechanics decision for `/plan`; the
coastline being matched is identical either way, and the committed
`land_sea_mask.png` remains the sole coastline authority (user decision #1,
2026-07-25) — nothing in this request moves a shoreline.

## The subset (7 sources, deduplicated)

The user's list contained `the_empire_2.jpg` twice; confirmed a slip (single
entry). Current state per `tools/SOURCES.md` and `tools/registration/`:

| Source | Registered today? | Notes for the fit |
|---|---|---|
| `tww3_ie_parchment.jpg` | **Yes** (`wh3_dlc_ie_parchment_map_english.json`) | Re-fit against the reprojected-globe coastline for consistency with the rest. Minimal expected movement (same objective geometry). **The only subset member that feeds a generator** — see Constraints. |
| `satellite_globe.jpg` | No — **de-registered in S2** | Whole-world. S2 measured it "does not register" (flat IoU response, no peak, 63.9–69.0% vs 60.0% chance). Retry is in scope; the same negative result is a live risk and, if it recurs, is the finding — do not manufacture a placement. |
| `the_empire_1.jpg` | No — TBD in manifest | Regional (Empire only, 5426×5091). Limited coastline (Sea of Claws north, western Empire/Bretonnian coast) → short coastal arc to match on. Origin/Role still TBD. |
| `the_empire_2.jpg` | No | Regional Empire map (1920×1301), the clean counterpart of `the_empire_2_rivers_drawn.jpg`. Same limited-coastline caveat. |
| `tww3_old_world_mod_parchment.png` | No | Old World line chloropleth (4096×4096), denser than IE. Great Ocean coast to the west. Corner vignettes + Galleon's Graveyard spiral are user-flagged as taking liberties and must be excluded. |
| `mega_detailed_old_world.jpg` | No — TBD | **385 MB** Old World relief map. Origin/Role TBD. Likely a relief illustration, not a chloropleth → coastline-extraction risk (see Constraints). Performance/memory concern. |
| `start_warhammer_old_world_z10.png` | No | 6658×9824, ~120 MB, stitched official Old World base tiles. Whole-continent coastline available, but art-only relief (no region fills). |

## Acceptance Criteria

- [ ] Each of the 7 sources has a committed `tools/registration/<stem>.json`
      produced from a committed seed under `tools/registration/seeds/`, fitted with
      the coastline of `terraqueous_globe_reprojected.png` (equivalently
      `land_sea_mask.png`) as the alignment objective.
- [ ] Every record's `notes` carries the fit's own measured numbers (coarse/refined
      IoU, folded fraction, anisotropy, landmark residual) — the placement carries
      its own evidence, per the existing convention.
- [ ] Any source whose coastline cannot be reliably locked (no usable silhouette,
      or a flat/ambiguous fit response) is recorded as such and marked
      not-usable-for-geometry, **not** given a forced placement. `satellite_globe.jpg`
      and `mega_detailed_old_world.jpg` are the likeliest to land here.
- [ ] `tools/SOURCES.md` updated: `Registered` flag flipped for each source that
      earns a real record; TBD `Origin`/`Role` cells filled for `the_empire_1.jpg`
      and `mega_detailed_old_world.jpg`; manifest refreshed via
      `python tools/worldgen/sources.py --update-manifest` (the deliberate action,
      not a side effect).
- [ ] `python tools/worldgen/sources.py --verify` passes (SHA-256 + registration
      cross-checks, incl. no alias-of-alias).
- [ ] `python tools/run_fixture.py --check` passes (toolchain regression).
- [ ] If the `tww3_ie_parchment.jpg` re-fit moves its control points enough to
      change `generate_state_labels.py` output, regenerate the affected bitmap(s),
      run `python tools/validate_map.py --labels`, and check the in-game
      `logs/error.log` clean per `.claude/rules/testing.md`. If it does not move
      them materially, state that and skip the regen.

## Investigation

- **What exists**:
  - `tools/fit_registration.py` — the authoring tool. Silhouette objective already
    supported (`silhouette()`, kinds `flat_colour` / `painted`), plus a
    `landmarks`-only fallback for sources with no measurable silhouette, plus
    `frame_alias`. Anchors landmarks through `ANCHOR_SOURCE = terraqueous_globe.jpg`'s
    NE-II fit (`anchor_landmarks()`).
  - Seeds today: `tools/registration/seeds/{ie_climate_map, ie_named_regions,
    total_war_map_colored, wh3_dlc_ie_parchment_map_english}.json`.
  - Records today: `tools/registration/{terraqueous_globe, ie_named_regions,
    map-the-old-world, total_war_map_colored, wh3_dlc_ie_parchment_map_english}.json`.
    (`TheEmpire.json` is deleted on the working tree.)
  - `sources/terraqueous_globe_reprojected.png` — canvas-sized reprojection, **not
    consumed by any script** (confirmed: no `.py` reference outside `.venv`).
  - `tools/config/canvas_frame.py` — the Miller frame the canvas means.
  - `tools/worldgen/reproject.py` — `fit_parametric` (NE-II), `fit_warp`
    (control-point warp), `fit_alias`.
  - `tools/worldgen/parchment.py` — `flat_map_cells`, `painted_mask` (the two
    silhouette extractors).
- **What changes** (all under `tools/`, none in game content):
  - New: 6 seed files + 6 records for the currently-unregistered sources.
  - Modified: re-fit `wh3_dlc_ie_parchment_map_english.json` from its seed against
    the reprojected-globe objective.
  - `tools/SOURCES.md` manifest rows (Registered flag, TBD Origin/Role).
  - Possibly `tools/fit_registration.py` **only if** `/plan` decides the objective
    should be read from `terraqueous_globe_reprojected.png` directly rather than
    from `land_sea_mask.png`. Given "faithful reprojection," this is optional and
    equivalent; recommend deferring unless it simplifies coastline extraction.
- **Constraints**:
  - **Coastline-extraction risk on relief art.** `old_world_terrain.jpg` was ruled
    NOT USABLE FOR GEOMETRY in S3a precisely because it is a relief illustration
    with lettering, not a chloropleth — a threshold finds the coastal shadow band,
    not the coast. `the_empire_1/2`, `mega_detailed_old_world`, and
    `start_warhammer_old_world_z10` are the same class of art and carry the same
    risk; `painted_mask` may not yield a clean silhouette. This is the single
    biggest threat to the request and why the acceptance criteria explicitly allow
    "not usable" as an honest outcome.
  - **Regional coverage.** The Empire maps cover a fraction of the world with a
    short coastal arc; a coastline IoU over a small, mostly-inland region is weakly
    constrained. Expect landmark-assisted fits there, and larger residuals.
  - **`satellite_globe.jpg` prior non-registration** (S2). Retrying is fine but the
    measurement said it does not place; treat a flat response as the result.
  - **Large files.** `mega_detailed_old_world.jpg` (385 MB) and
    `start_warhammer_old_world_z10.png` (120 MB, 6658×9824) — memory/time budget for
    the LUT/threshold and coarse sweep; classify-before-reproject at source res as
    the existing pipeline does.
  - **Rubber-sheet warps are acceptable** because the mask stays the sole coastline
    authority — local scale error moves an interior feature, never a shoreline.
  - **Determinism / downstream bitmaps.** Registration itself is offline tooling,
    not loaded by the game (no MP-sync impact directly). But committed bitmaps
    *derived* from registrations are MP-synchronized. Of this subset, only
    `tww3_ie_parchment.jpg` currently feeds a generator (`generate_state_labels.py`
    `BOUNDARY_SOURCES` + `MACRO_CLEAN_MASTER`), so its re-fit is the only one that
    can move a committed bitmap; the other six are not yet wired into any generator,
    so registering them changes no committed output on its own. Any regeneration
    must stay byte-deterministic and be re-linted.
- **Related files**: `tools/fit_registration.py`, `tools/registration/seeds/*.json`,
  `tools/registration/*.json`, `tools/SOURCES.md`, `tools/config/canvas_frame.py`,
  `tools/worldgen/{reproject,parchment,register,schema,sources,segment}.py`,
  `tools/generate_state_labels.py`, `tools/validate_map.py`, `tools/run_fixture.py`,
  `sources/terraqueous_globe_reprojected.png`,
  `tools/derived/land_sea_mask.png`.
- **Endpoints/commands**: authoring — `python tools/fit_registration.py --seed
  <stem>` per source (add `--dry-run` to report without writing). Gate —
  `python tools/worldgen/sources.py --verify`, `python tools/run_fixture.py --check`,
  and (only if `tww3_ie_parchment` moves) `python tools/generate_state_labels.py`
  + `python tools/validate_map.py --labels`.
- **Tests required**: `sources.py --verify` and `run_fixture.py --check` after every
  record written; per-source, confirm the fit's reported IoU/residual is an interior
  maximum (not a boundary of the sweep) or is honestly recorded as non-registering;
  for `tww3_ie_parchment`, diff `generate_state_labels.py` output and, if changed,
  the in-game `error.log` check.
- **Out of scope**:
  - Editing the coastline authority — the reprojected globe is faithful and the
    committed `land_sea_mask.png` is unchanged.
  - Wiring any newly-registered source into `generate_heightmap.py` /
    `generate_state_labels.py` (relief-detail, boundary, naming passes are a later
    stage — S6). This request only *places* the sources; it does not consume them.
  - The `terraqueous_globe_reprojected - rivers.png` working layer and any river
    work.
  - Regenerating `heightmap.png` / `rivers.png`; only `state_labels` may need it,
    and only if the `ie_parchment` re-fit moves.
  - Reviving `old_world_terrain.jpg` / `TheEmpire` — not in the requested subset.
- **Localization needed**: none. This is offline `tools/` work; it authors no
  user-facing keys and touches no `localization/`, `common/`, `events/`, or `gui/`.

## Open question for /plan

Should the coastline objective be **read from `terraqueous_globe_reprojected.png`
directly**, or keep using `tools/derived/land_sea_mask.png`? They are geometrically
identical here (faithful reprojection), so this is a mechanics/ergonomics call, not
a geometry one — decide it in `/plan`. The tie-breaker to weigh: reading the named
reference the user pointed at vs. the churn of teaching `fit_registration.py` a new
objective source when the existing mask already encodes the same coastline.

> Resolved in the Plan below: keep `land_sea_mask.png`.

## Plan

### Objective
Register the 7-source subset against the committed coastline, producing an honest
placement — or an honest *non*-placement — for each. From measured pixel evidence
(below) most will be landmark-fitted or not-usable rather than silhouette-locked;
the deliverable is correct placements that carry their own evidence, not a forced
record per source.

### Resolved open questions
- **Coastline objective source** → use the committed `tools/derived/land_sea_mask.png`,
  not `sources/terraqueous_globe_reprojected.png`. The reprojected PNG is a faithful
  (geometry-unedited) Miller reprojection, so the two are geometrically identical as a
  fit objective; reading the PNG directly is new code for zero geometric gain, and the
  mask stays the sole coastline authority (user decision #1). Deferred, per the
  request's own recommendation. The local `terraqueous_globe_reprojected - coastline.png`
  / `…_with_coast.paint` (the latter dated 2026-08-13) are treated as QA/tracing aids,
  not adopted as the objective — flag if that is wrong.
- **Landmark ownership** (decided 2026-08-13) → **Claude takes the first pass** at
  source-side landmarks (reusing the solved globe anchors), runs every fit, and sends a
  QA overlay per source; the **user gives the visual verdict and corrects landmark
  picks** where the overlay or fit numbers show them off, and Claude re-fits. The fit is
  self-measuring (IoU, landmark residual, folded fraction), so a bad pick shows up in
  both the numbers and the overlay.

### Measured silhouette reality (planning inspection, 2026-08-13)
None of the six new sources has a flat ocean fill, so the exact `flat_colour` path
(what made `tww3_colored.png` an exact silhouette) is unavailable for all of them:
- `tww3_old_world_mod_parchment.png` (4096²) — ocean is bare parchment, not blue (0.0%
  blue-dominant, chroma spread 0.02): the same "sea = same paper as land" problem as the
  IE parchment → `painted` only if its land regions are colour-filled, else `landmarks`.
- `the_empire_1.jpg` (5426×5091), `the_empire_2.jpg` (1920×1301) — textured relief, no
  flat sea (≤0.1% blue) → `landmarks`.
- `start_warhammer_old_world_z10.png` (6658×9824, 120 MB) — relief tiles, no flat sea →
  `landmarks`, memory-bounded.
- `satellite_globe.jpg` (637×358) — biome render; dominant pixel is the side letterbox
  (RGB 8,8,8, 28.9%), consistent with the S2 "does not register" finding → retry, expect
  a flat response.
- `mega_detailed_old_world.jpg` (29952×22528 = 675 MP) — relief, memory risk → bounded
  downsample attempt, likely not-usable.

### Steps (ordered)
1. **`tools/registration/wh3_dlc_ie_parchment_map_english.json`** — re-fit from its
   existing seed (`python tools/fit_registration.py --seed wh3_dlc_ie_parchment_map_english`).
   No new landmarks. Diff control points vs. the committed record; if they move
   `generate_state_labels.py`'s boundary/macro inputs materially, regenerate
   `state_labels` (+ `validate_map.py --labels`, in-game `error.log`); else record "no
   material move" and skip regen. Satisfies AC #7. Runs first — fully autonomous.
2. **`tools/registration/seeds/tww3_old_world_mod_parchment.json`** + record — determine
   land-fill: `painted` silhouette + landmarks if land is colour-filled; `landmarks`
   objective if the ocean is bare parchment. Reuse Old World globe anchors (Reikland,
   Kislev, Norsca, Araby, Bretonnian/Tilean coast). Exclude the four corner vignettes +
   the Galleon's Graveyard spiral (user-flagged liberties).
3. **`tools/registration/seeds/the_empire_2.json`**, **`tools/registration/seeds/the_empire_1.json`**
   + records — `landmarks` objective. Short coastal arc (Sea of Claws, Reik mouth /
   Marienburg, western Empire / Bretonnian coast); larger residuals expected; picks are
   load-bearing.
4. **`tools/registration/seeds/start_warhammer_old_world_z10.json`** + record —
   `landmarks` objective, whole-continent; classify-before-reproject at source res,
   memory-bounded.
5. **`tools/registration/seeds/satellite_globe.json`** — silhouette retry; exclude the
   side letterbox (x≈87–548). Expect the S2 flat response → documented negative, no
   placement record.
6. **`tools/registration/seeds/mega_detailed_old_world.json`** — 675 MP memory-bounded
   downsample attempt → likely documented negative, no record.
7. **QA overlay per fit** (the mechanism behind `tools/derived/qa_*.png`) → send to the
   user for the visual verdict + landmark corrections; re-fit to convergence.
8. **`tools/SOURCES.md`** — flip `Registered` per outcome; fill TBD `Origin`/`Role` for
   `the_empire_1` and `mega_detailed_old_world`; add S2-style prose for any documented
   negative; then `python tools/worldgen/sources.py --update-manifest`.
9. Run the offline gate; move this file to `planning/done/` with `## Resolution`.

### AC1 vs AC3 reconciliation
The gate binds manifest `Registered` ⟺ record existence. So: a source that locks a
placement → committed `registration/<stem>.json` + `Registered=yes`; a source that
returns a flat/ambiguous response → committed **seed** + documented negative in
`SOURCES.md` + `Registered=no`, no placement record (the `satellite_globe` S2
precedent). Not every source ends with a record — "recorded as such, not given a forced
placement" (AC3) requires exactly this.

### Edge cases
- Parchment re-fit moving `state_labels` — the only step that can touch a committed,
  MP-synced bitmap; diff and conditionally regenerate.
- A `landmarks`-only fit has no independent check — its landmark residual *is* the
  objective, so the record's notes must state the weaker guarantee (folded-fraction /
  anisotropy still computed on the warp).
- `satellite_globe` letterbox is on the sides, not the top.
- `mega_detailed` may OOM at 675 MP → document + mark not-usable rather than force it.
- No alias-of-alias — if any source proves a crop-twin of a registered master, use
  `frame_alias` to the master (never to another alias).

### Testing
- After each record: `python tools/worldgen/sources.py --verify` +
  `python tools/run_fixture.py --check`; confirm each fit's IoU/residual is an interior
  maximum of its sweep, or is honestly recorded as non-registering.
- Visual: a QA overlay per fit — the real gate — sent to the user.
- Only if the parchment re-fit moves `state_labels`: `python tools/validate_map.py --labels`,
  then load the mod and confirm `logs/error.log` is clean for this mod's files (see
  [testing.md](../../.claude/rules/testing.md)).

### Docs to Update
- `tools/SOURCES.md` — manifest rows + any documented-negative prose.
- This request → `## Resolution`, moved to `planning/done/`.
- Localization: none — offline `tools/` work; authors no user-facing keys, touches no
  `common/`/`events/`/`gui/`/`localization/`.
