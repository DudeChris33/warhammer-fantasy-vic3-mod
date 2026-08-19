# Switch the world-map canvas from plate carrée to Miller cylindrical

| Field | Value |
|-------|-------|
| Type | request |
| Status | resolved |
| Date | 2026-07-29 |
| Priority | high |

> **Resolved.** Both deliverables shipped: the Miller frame switch landed in
> commit `44995ed` ("World map: switch the ingestion canvas to Miller
> cylindrical"), and the downstream re-fits + regenerated artifacts were adopted
> in `3d3d88e`. `canvas_frame.py` is Miller, every canvas-side control point was
> migrated, and the plate-carrée-derived artifacts were regenerated. Frame params
> of record: Y0=2142, band +74.9/−57.4. Filed to `planning/done/` on 2026-08-18.

## Description

The ingestion canvas is currently a **plate-carrée** sheet (`tools/config/canvas_frame.py`).
Victoria 3's own map is **Miller cylindrical** — confirmed by the user and
measured against vanilla's shipped bitmap below. Miller is therefore the
requirement for the final product, and the canvas must change to match.

Two deliverables, in order:

1. **A Miller-reprojected copy of `sources/terraqueous_globe.jpg`** — the literal
   ask. Take the globe out of Natural Earth II and render it into the new Miller
   frame, so the target geometry can be eyeballed before anything is regenerated
   against it. Local-only (it embeds source pixels).
2. **The frame switch itself** — `canvas_frame.py` becomes Miller, `reproject.py`
   learns the new canvas parameterisation, every canvas-side control point is
   migrated, and every artifact derived from the globe is regenerated.

Per the user (this session): **all existing content derived from the Terraqueous
globe is now obsolete.** `land_sea_mask.png`, `heightmap.png`, `rivers.png`,
`state_labels.png`, `state_labels_index.json`, `COVERAGE.md` and
`derived/named/` are all products of the plate-carrée frame and do not survive
this change.

## Context

### What vanilla actually uses — measured, not assumed

No projection is declared anywhere in the vanilla install; the engine just
consumes a bitmap. So vanilla's frame was **measured** from its own data:
`game/map_data/state_regions/*.txt` names states after real places, and island
states are unambiguous anchors (the state footprint *is* the island). 25 island
states were resolved to province colours, their centroids computed from
`game/map_data/provinces.png` (8192×3616), and cylindrical projections fitted
against their real-world coordinates.

| Projection hypothesis | Residual RMS |
|---|---|
| **Miller cylindrical** | **12.9 px** |
| Gall stereographic | 15.8 px |
| Mercator | 33.5 px |
| Plate carrée (what we use today) | 37.5 px |

Miller wins, and the fit is a *true, unscaled* Miller: fitting the two axes
independently gives `R_lat / R_lon = 1.0068`, and the longitude scale comes out
at 1302.92 px/rad against the exact `8192 / 2π = 1303.797` — 0.07% off, i.e.
vanilla's 8192 px is exactly 360° of longitude.

Constraining `R` to the canvas and solving only the two offsets (median
estimator over the 25 anchors) gives vanilla's frame:

```
R          = 8192 / (2π) = 1303.7973 px/rad
x(lon 0)   = 4098.0                      → canvas x = 0 is lon −180.09
y(lat 0)   = 2102.3                      → the equator sits 58.14% down
top    y=0      → lat +74.0206
bottom y=3616   → lat  −58.6127
```

Residuals: median |dx| 3.8 px, median |dy| 2.4 px on an 8192-px canvas. The
handful of large residuals (Ceylon +65 px, Bermuda −43 px, Sakhalin, Luzon) are
where Vic3 takes cartographic liberties with small islands or where the state
includes more than the island — expected, and they do not move the fit.

Note the frame is **asymmetric about the equator**. That is a real property of
vanilla's map, not fit noise.

### What this costs the Warhammer world

Measured against the committed `tools/derived/land_sea_mask.png` (27.85% land):

| Candidate band | Land lost |
|---|---|
| **Vanilla's measured band, +74.02 / −58.61** | **0.79%** (0.363% north + 0.427% south) |
| Symmetric Miller at 8192×3616, ±66.86 | 7.10% |

Adopting vanilla's exact band costs under 1% of land, and much of what it crops
is not real content: the current mask has land on **rows 0 and 3615** — the
canvas's literal top and bottom edges — which is the artifact recorded in
[chaos-wastes-polar-fringe-misclassified.md](../issues/chaos-wastes-polar-fringe-misclassified.md).
That issue's own root-cause analysis names the NE-II → plate-carrée stretch at
79.45N as the cause. Moving the top edge to 74.02N attacks it at the frame
level. The symmetric alternative is rejected: 7.1% of land is a real loss.

### Why the code change is small but the blast radius is large

The plate-carrée assumption is well contained — a grep for `canvas_frame.` finds
it in exactly two modules (`config/canvas_frame.py`, `worldgen/reproject.py`).
Everything downstream works in canvas pixels and never converts to lon/lat.

But every committed number that was *derived through* the old frame changes
meaning: the canvas-side column of every registration record, `ANCHORS`, and
every generated bitmap. The fixture expectations bake the old frame in too, so
`run_fixture.py --check` will fail until they are regenerated.

One consequence worth stating rather than discovering later: under plate carrée
a canvas pixel was a constant number of square degrees; under Miller it is not.
The area/density logic in `tools/worldgen/cells.py` (`merge_small`,
`split_large`, `merge_to_target`, `sea_zones`) works in canvas px and needs **no
code change** — canvas area is *screen* area, which is what the player and the
engine both see, so this is arguably more correct than before. What does change
is the numbers: the thresholds and per-region density targets were tuned against
the plate-carrée mask and will land differently.

### Migration of control points is exact, not a re-authoring job

Every canvas-side coordinate currently committed was derived from lon/lat, not
eyeballed:

- `tools/registration/terraqueous_globe.json`'s control points are named
  graticule crossings ("meridian 90W × equator"), so their canvas column is
  simply recomputed under Miller.
- `config/canvas_frame.ANCHORS` were refined in S2 by pushing Terraqueous source
  px through the NE-II fit → lon/lat → canvas px.
- `tools/registration/seeds/*.json` pin canvas px to source px for the IE family.

So the migration is mechanical and lossless: **canvas px → lon/lat under the old
plate carrée → canvas px under the new Miller**. Re-picking anything by hand
would only add error.

### Not affected

Nothing here touches `common/`, `events/`, `gui/` or `localization/`. No effect,
trigger, modifier, event target or on_action is involved, so `docs/*.log` has no
bearing on this request — it is entirely offline `tools/` work plus the
generated bitmaps under `map_data/`. `config/map_config.py` is untouched: the
canvas stays 8192×3616 and the heightmap 16384×7232, matching vanilla.

## Acceptance Criteria

- [ ] A Miller-reprojected copy of `sources/terraqueous_globe.jpg` is rendered
      into the new frame and shown to the user, **before** anything is
      regenerated against it. Written under `tools/derived/` (gitignored — it
      embeds source pixels, per `tools/PROVENANCE.md`).
- [ ] `tools/config/canvas_frame.py` defines a Miller cylindrical frame using
      vanilla's measured constants (`R = 8192/2π`, equator at y ≈ 2102.3, top
      +74.0206, bottom −58.6127), with `lonlat_to_canvas` / `canvas_to_lonlat`
      exact inverses of each other.
- [ ] The measurement that produced those constants is committed as a rerunnable
      script, not just quoted — a future reader can re-derive the frame from the
      vanilla install.
- [ ] `tools/worldgen/reproject.py` treats the canvas as Miller in all four
      places it currently assumes linear latitude (`canvas_lonlat`,
      `ParametricFit.to_canvas`, `fit_parametric`, and the docstring).
- [ ] Every canvas-side control point migrated through lon/lat:
      `tools/registration/*.json`, `tools/registration/seeds/*.json`,
      `canvas_frame.ANCHORS`. `terraqueous_globe.json` re-fits to the same
      sub-pixel residual it has today (0.363 px RMS) — a worse residual means
      the migration is wrong.
- [ ] All generated artifacts regenerated from the new frame:
      `map_data/heightmap.png`, `map_data/rivers.png`,
      `tools/derived/land_sea_mask.png`, `tools/derived/state_labels.png`,
      `tools/derived/state_labels_index.json`, `tools/derived/COVERAGE.md`,
      `tools/derived/named/`.
- [ ] No land pixels on canvas rows 0 or `HEIGHT-1` (the polar-fringe artifact
      does not survive the reframe), or an explicit note saying why it does.
- [ ] Fixture expectations regenerated and `python tools/run_fixture.py --check`
      passes.
- [ ] `python tools/worldgen/sources.py --verify` and
      `python tools/validate_map.py --labels` pass.
- [ ] Regeneration is byte-reproducible: running the generators twice produces
      identical output (`.claude/rules/core.md` determinism).

## Investigation

- **What exists**:
  - `tools/config/canvas_frame.py:31-52` — `LON_MIN/MAX`, `LAT_MAX = 79.453125`,
    `_PX_PER_DEG_LAT`, and the two conversion helpers. The module docstring
    explicitly justifies the plate-carrée choice ("square graticule cells").
  - `tools/config/canvas_frame.py:98-115` — `ANCHORS`, 16 named feature
    positions in canvas px.
  - `tools/worldgen/reproject.py:341-353` (`canvas_lonlat`), `:169-182`
    (`ParametricFit.to_canvas`), `:204-215` (`fit_parametric`'s canvas px →
    lon/lat) — the four sites assuming latitude is linear in y.
  - `tools/registration/terraqueous_globe.json` — NE-II record, 11 graticule
    control points, `crop`, `footprint [0,0,8192,3616]`.
  - `tools/registration/*.json` + `tools/registration/seeds/*.json` — the IE
    parchment family and Total War records, all canvas-anchored.
  - `tools/derived/land_sea_mask.png`, `state_labels.png`,
    `state_labels_index.json`, `COVERAGE.md`, `named/` — the committed products
    of the current frame.
  - `game/map_data/state_regions/*.txt` + `game/map_data/provinces.png` — the
    vanilla ground truth the frame was measured from (read-only reference).

- **What changes**:
  - `tools/config/canvas_frame.py` — rewrite as a Miller frame.
  - `tools/worldgen/reproject.py` — Miller canvas parameterisation. Miller has a
    closed-form inverse (`lat = ((atan(exp(y/1.25)) − π/4) / 0.4)`), so no
    iterative solver is needed and determinism is preserved.
  - `tools/worldgen/schema.py:501-516` — only if a `miller_cylindrical`
    *source* projection kind is wanted; not required for the canvas change.
  - `tools/registration/*.json`, `tools/registration/seeds/*.json`,
    `tools/config/canvas_frame.ANCHORS` — migrated canvas coordinates.
  - New: a Miller reprojection render script (or a `--miller` mode on
    `tools/render_named_map.py`, which already renders into the globe's own
    pixel space through `reproject.fit_parametric`).
  - New: the committed vanilla-frame measurement script.
  - `map_data/heightmap.png`, `map_data/rivers.png`, `tools/derived/*` —
    regenerated, never hand-edited.
  - `tools/fixtures/boundary/expected/*`, `tools/fixtures/ingest/` — expectations
    regenerated.
  - Docs: `tools/SOURCES.md` (the globe's role text describes an NE-II →
    plate-carrée path), `tools/MAP_RUNBOOK.md`, `tools/PROVENANCE.md`,
    `planning/requests/world-map-source-driven.md`, and the two agent briefs
    that hardcode the old span — `.claude/agents/cartographer.md:56,98` and
    `.claude/agents/geographer.md:58,64,77`.

- **Constraints**:
  - The globe stays the single geometric authority (user decision #1,
    2026-07-25). This changes the *target frame*, not the source of truth.
  - Determinism: generated map data is static and MP-safe, but regeneration must
    be byte-identical (`config/map_config.SEED`, sorted iteration, no wall-clock).
  - Never hand-edit the generated bitmaps or the registration records
    (`CLAUDE.md` non-negotiables) — fix the frame and regenerate / re-fit.
  - `sources/` is local-only and gitignored; any render embedding source pixels
    cannot be committed.
  - The vanilla install is read-only. The measurement script reads it; it must
    never write there.
  - Canvas dimensions are fixed at 8192×3616 to match vanilla.

- **Related files**: `tools/generate_heightmap.py`, `tools/generate_rivers.py`,
  `tools/generate_state_labels.py`, `tools/fit_registration.py`,
  `tools/validate_map.py`, `tools/run_fixture.py`, `tools/qa_overlay.py`,
  `tools/worldgen/cells.py`, `tools/worldgen/sources.py`,
  `planning/issues/chaos-wastes-polar-fringe-misclassified.md`,
  `planning/requests/world-map-parchment-areas-onto-globe.md` (its Stage A/B work
  is built on the old frame and will need re-basing).

- **Endpoints/commands**:
  - New: a Miller reprojection render (new script or `render_named_map.py --miller`).
  - New: the vanilla-frame measurement script.
  - Unchanged surface, new output: `generate_heightmap.py`, `generate_rivers.py`,
    `generate_state_labels.py`, `fit_registration.py`, `validate_map.py`,
    `run_fixture.py`, `worldgen/sources.py --verify`.

- **Tests required**:
  - Round-trip: `lonlat_to_canvas` ∘ `canvas_to_lonlat` is identity to
    floating-point tolerance across the full canvas, including the wrap seam.
  - The vanilla measurement reproduces the committed frame constants from the
    read-only install.
  - `terraqueous_globe.json` re-fits at ≤ 0.363 px RMS after migration.
  - `python tools/run_fixture.py --check` against regenerated expectations.
  - `python tools/worldgen/sources.py --verify`, `python tools/validate_map.py --labels`.
  - Byte-reproducibility: two consecutive generator runs produce identical files.
  - Visual: the Miller globe render and a regenerated `derived/named/` sheet go
    to the user. The rendered map is the real gate — every offline check has
    been green before while the map was visually unusable.

- **Out of scope**:
  - Re-tuning the per-region state-density targets to the new frame. The numbers
    will shift; retargeting is the follow-up, tracked against the existing
    named-region requirements (Bretonnia ≥15, Empire ≥30, Cathay ≥40, 600–700
    total).
  - The parchment Stage A/B work in
    [world-map-parchment-areas-onto-globe.md](world-map-parchment-areas-onto-globe.md).
    It has to be re-based onto this frame, but that is that request's business.
  - `map_data/provinces.png` (S3b) — does not exist yet.
  - Fixing the corner-splinter blocker from the S3a-2 review panel.
  - Adding a `miller_cylindrical` *source* projection kind. No source in
    `tools/SOURCES.md` is drawn in Miller; this is a canvas change only.

- **Localization needed**: none. No user-facing string, no loc key, no `common/`
  or `events/` script is touched.

## Open decision for `/plan`

Vanilla's band is asymmetric (+74.02N / −58.61S) because Earth's landmasses are.
The Warhammer world has Chaos Wastes at **both** poles, so the southern crop is
the one place where copying vanilla exactly is a judgement call rather than a
measurement. It costs 0.427% of current land, most of it the polar-fringe
artifact — so the recommendation is to take vanilla's band as measured, and
revisit only if the southern Chaos Wastes turn out to need the room.

## Plan

> **Scope note (user decision, 2026-07-29).** Every other planning document is
> obsolete under this reframing. This request stands alone: the polar-fringe
> defect that survives the reframe is fixed *here*, not deferred. Measurements
> recorded in the superseded documents are still cited as evidence — a
> measurement does not go stale — but none of their rulings, sequencing or
> open questions bind this plan.

### Objective

Replace the plate-carrée ingestion canvas with a **Miller cylindrical** frame —
projection measured from vanilla's shipped map, latitude band pinned to the
user's own drawn northern limit — migrate every canvas-side control point through
lon/lat, **repair the polar classification the reframe exposes**, and regenerate
every artifact derived from the Terraqueous globe.

### Measurements taken while planning (2026-07-29)

Re-derived independently against the read-only vanilla install rather than taken
on trust from the request. Twelve island states resolved to province colours,
centroids computed from `game/map_data/provinces.png` (8192×3616):

| Hypothesis | median \|dy\| |
|---|---|
| **Miller** | **1.7 px** |
| Mercator | 16.0 px |
| Plate carrée | 22.6 px |
| Gall stereographic | 43.9 px |

Solved offsets **X0 = 4098.0, Y0 = 2102.1** (request said 2102.3 — 0.2 px apart
on a smaller anchor set). Sicily, Sardinia, Crete, Malta, Cyprus and Tasmania
land at ≤2.4 px. Miller confirmed.

| # | Measurement | Consequence |
|---|---|---|
| 1 | `fit_parametric` on `terraqueous_globe.json` reports **0.0019 px RMS** today | The acceptance criterion's 0.363 px is the *envelope-trace* residual — a source-space number this change cannot touch. The re-fit target is **0.0019 px**. |
| 2 | Two of the globe's control points sit at canvas y=0 / y=3616, i.e. lat ±79.453125. Under Miller those are y = **−258.6** and **+4463.2** | They cannot be migrated. `schema.ControlPoint.from_dict` rejects negative canvas coords; `sources.verify` rejects anything outside the canvas. The record must be **re-emitted**, not shifted. |
| 3 | Seed landmark `anchor` fields are **Terraqueous source px**, converted at fit time by `fit_registration.anchor_landmarks` | **No seed needs its landmarks edited.** All 22 checked: highest is `kislev_troll_country` at 66.90N, well inside the new band. |
| 4 | `fixtures/ingest/registration/synthetic_world.json` pins source y 0/64/128 to canvas y 0/1808/3616 under an `equirectangular` projection | Under Miller the interior points must move or the fit stops being exact and the record's own "the reported residual stays a real conditioning check" note becomes false. |
| 5 | `STATE_FIJI` straddles ±180; its arithmetic mean x is **2128 px** wrong | The measurement script must use a circular mean in longitude (or exclude seam-straddlers) or the estimator is poisoned. |
| 6 | Sweeping Y0 against the committed mask: symmetric (Y0 1809) → 7.04% land lost; vanilla (2102.3) → 0.775%; **2142 → 0.686%** | The band is a measured optimum, not a taste call. |
| 7 | `map_data/provinces.png` is 8192×3616 in **all five** installed mods that ship one — including `realms-of-exether`, a total conversion with its own invented world | Growing the canvas has no precedent and is off the table (user decision). |
| 8 | Classifying the globe's crop through the committed LUT: of **844,798** band-0 (−9000…−7000 m) pixels, **833,179 (98.6%) are enclosed** components and only **11,619 (1.4%) touch the oval's north rim** | **The polar fix is spatial, and the separation is nearly perfect.** A flood from the north rim reaches the polar blank and essentially none of the real abyssal basins. This is what the colorimetric rule cannot do. |
| 9 | Vanilla's own `heightmap.png` rows 0–200: **42.7% above value 100**, p95 ≈ 20,878, max 35,799 | **Land at canvas row 0 is normal**, not a defect — vanilla ships Greenland and the Arctic at its top edge. The polar band becoming land is correct, and the acceptance criterion "no land pixels on row 0" is the wrong test. |
| 10 | The adopted top edge is **74.905N**; the globe's drawn terrain limit measures **72.5–74.5N** | The blank-page band shrinks from ~113–158 canvas rows to **~17–102**, but does not vanish. It has to be classified deliberately rather than left to the LUT. |

#### The band — resolved on the user's own markup

The request left the southern crop open. The user answered it by drawing two 1 px
purple lines on a local-only annotated copy,
`sources/terraqueous_globe_for_reprojection.jpg` (4000×3256, pixel-identical to
`terraqueous_globe.jpg` apart from the markup), marking land they are content to
lose entirely. Recovered by differencing the two files: horizontal rules at
sub-pixel source rows **238.183** and **2020.155**, i.e. lat **+74.9050** and
**−74.8647** through the committed NE-II fit.

That band does **not fit**. `wrap_x` forces 8192 px = 360° of longitude, which
pins Miller's `R` at 8192/2π, which pins the canvas to **132.6°** of latitude.
The marked keep-band is 149.8° — **4283 Miller px against 3616**. 667 px has to
come out of land the user did not mark free, and with the canvas size fixed
(measurement 7) there is no way around it. Even a band covering every land pixel
in both hemispheres overflows by ~300 px.

Measured against `tools/derived/land_sea_mask.png`, spending the cut three ways:

| Y0 | top / bottom | land lost | land lost that was **not** marked free |
|---|---|---|---|
| 1809.3 (centres the marked band) | +66.91 / −66.84 | 7.044% | 6.821% |
| 2102.3 (vanilla's exact band) | +74.02 / −58.61 | 0.775% | 0.552% |
| **2142.0 (top on the north line)** | **+74.91 / −57.41** | **0.686%** | **0.466%** |

**Adopted: `Y0 = 2142.0`** (user decision, 2026-07-29). The canvas top edge lands
on the user's marked northern limit exactly, so the entire forced cut comes out of
the south; it is the minimum on both metrics; and it stays true, unscaled Miller
at vanilla's canvas size. Rejected: a 0.844 y-compression that would fit the whole
marked band, because it distorts every latitude including the Old World to save
0.47% of polar land.

What the southern cut costs, measured (38,453 px in 9 components between −57.41
and −74.86): one **~20,400 px island** at lon −68…−57 deleted outright, two
landmasses near 110–123E truncated, and **nothing below −66S** — the world runs
out of land there regardless. The reframe also deletes the *southern* half of the
polar-fringe defect outright: the bottom edge sits deep inside drawn terrain.

`terraqueous_globe_for_reprojection.jpg` is **markup, not a source**: it is not
registered, not added to `tools/SOURCES.md`, and never consumed. Adding it to the
manifest would make `sources.py --verify` go red the day the user deletes their
scratch file. Its role is recorded in the `canvas_frame` docstring as the
provenance of `Y0`.

### The frame

```
R  = WIDTH / 2*pi = 1303.7973 px/rad    (from wrap_x: 8192 px = 360 deg lon)
X0 = 4098.0     canvas x of lon 0       (measured against vanilla)
Y0 = 2142.0     canvas y of lat 0       (user's northern line, 2026-07-29)

top    y = 0     ->  +74.9052 N        bottom y = 3616  ->  -57.4084 S
canvas x = 0     ->  lon -180.0879     span 132.3136 deg
```

### Steps (ordered)

#### Phase 0 — baseline

1. **Commit the uncommitted working tree first** — 22 modified files plus
   `tools/render_named_map.py`, `tools/derived/named/`, and the fitted
   `tools/registration/wh3_dlc_ie_parchment_map_english.json`. The reason is not
   the superseded request that produced it: that code is **frame-independent**
   (glyph bridging in `worldgen/parchment.py`, cell tracing, the render script,
   the fixture extensions), this plan's Phase 5 re-runs all of it anyway, and
   without a committed baseline the Miller diff moves every registration and
   bitmap for two unrelated reasons at once and cannot be reviewed. If the user
   would rather discard that work instead, this step inverts to `git checkout --`
   on those paths and nothing else in the plan changes.

2. **Retire the superseded documents.** Set `Status` to `superseded` with a
   one-line pointer to this file, in `planning/requests/world-map-source-driven.md`,
   `planning/requests/world-map-parchment-areas-onto-globe.md`,
   `planning/requests/s3a2-review-panel-handoff.md` and
   `planning/issues/chaos-wastes-polar-fringe-misclassified.md`. They are **not**
   moved to `planning/rejected/` — nothing here was declined, and the directory
   would misrepresent why. The polar issue is absorbed into Phase 4 of this plan
   rather than left open.

#### Phase 1 — the measurement, committed and rerunnable

3. **`tools/measure_vanilla_frame.py`** — new, read-only against
   `C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game`. Parses
   `map_data/state_regions/*.txt` for state → province colour lists, reads
   `map_data/provinces.png`, computes per-state centroids, fits Miller / Gall /
   Mercator / plate carrée, prints the residual table and the median-estimated
   X0/Y0. The ~25-row island-state → real-world-coordinate table is a documented
   module constant, matching how `canvas_frame.ANCHORS` and `reproject`'s NE-II
   constants are already handled. Must: use a **circular mean** in longitude
   (measurement 5); use a **median** estimator (robust to Ceylon +65 px, Sakhalin,
   Bermuda, where the state is more than the island); assert it never opens the
   vanilla install for writing. `--json` writes a report under `tools/derived/`
   (gitignored).

#### Phase 2 — the frame

4. **`tools/config/canvas_frame.py`** — rewritten as Miller. Constants `R_CANVAS`,
   `X0`, `Y0`, `MILLER_K = 1.25`, `MILLER_C = 0.4`; derived `LAT_TOP`,
   `LAT_BOTTOM`, `LON_AT_X0`. Docstring records both provenances — the vanilla
   measurement for the projection and X0, the user's drawn line for Y0 — and
   points at step 3's script. `TERRAQUEOUS_OVAL` unchanged (source px,
   frame-independent). `ANCHORS` replaced with the migrated values:

   ```
   naggaroth (1828, 792)       ulthuan_ring (2791, 1414)     lustria (2237, 2450)
   norsca (4127, 470)          old_world_empire (4226, 819)  estalia (3783, 1147)
   araby (3656, 1678)          land_of_the_dead (4210, 1811) southland (4343, 2352)
   dark_lands (4968, 919)      dragon_isles (5234, 1720)     ogre_kingdoms (5868, 796)
   grand_cathay (6532, 919)    kingdoms_of_ind (6178, 1720)
   kingdoms_of_kuresh (6465, 2059)   nippon (7529, 1151)
   ```

   API decisions:
   - **Delete `LAT_MAX` / `LAT_MIN` / `LON_MIN` / `LON_MAX` / `_PX_PER_DEG_LAT`,
     do not redefine them.** Under Miller "px per degree of latitude" is not a
     constant. Leaving the names lets a stale consumer keep computing a plausible
     wrong number; deleting them turns every stale consumer into an
     `AttributeError` at import, which is what makes the blast radius knowable.
   - **Scale-aware helpers**: `lonlat_to_canvas(lon, lat, width=WIDTH,
     height=HEIGHT)` and `canvas_to_lonlat(x, y, width=WIDTH, height=HEIGHT)`,
     with `k = width / WIDTH` scaling R, X0 and Y0. `assert height ==
     round(HEIGHT * k)` so a non-uniform grid raises instead of silently
     distorting latitude. `HEIGHTMAP_SIZE` is exactly 2x; `INGEST_CANVAS`
     (512x226) is exactly 1/16.
   - **`lonlat_to_canvas` folds x mod width; `canvas_to_lonlat` does not.**
     `fit_parametric:206-208` depends on a seam control point recorded at
     x = WIDTH staying at +180 rather than folding to −180. The round-trip
     invariant is therefore: **latitude exact everywhere, longitude exact modulo
     width.**
   - **Drop the y-clamp.** Today's `max(0, min(HEIGHT, y))` was harmless under
     plate carrée; under Miller a feature at 78N would pin silently to row 0 and
     register wrong. Callers needing a clamp call `register.clamp_canvas`, which
     already exists.

5. **`tools/worldgen/reproject.py`** — the four sites that assume linear latitude,
   all delegating to the new helpers: module docstring (`:1`),
   `ParametricFit.to_canvas` (`:169-182`), `fit_parametric`'s canvas → lon/lat
   (`:204-215`, keeping the seam comment), `canvas_lonlat` (`:341-353`).
   `_project_norm_separable` is source-side and unchanged. Miller's inverse is
   closed-form (`lat = (atan(exp(y/1.25)) − pi/4) / 0.4`), so no iterative solver
   is added and determinism is preserved.

#### Phase 3 — migrate the hand-authored canvas coordinates

6. **`tools/migrate_frame_coords.py`** — new one-shot **authoring** command,
   documented alongside `--update-manifest` and `fit_registration.py`; the gate
   never runs it. Carries the *old* plate-carrée constants internally rather than
   reading the rewritten module. Rule: canvas px → lon/lat (old) → canvas px
   (new). Migrates control points and footprints of `TheEmpire.json`,
   `map-the-old-world.json`, `tww3_map_stitched.json`; emits the new `ANCHORS`
   block; handles steps 7 and 8. **Fails loudly** on any point it pushes outside
   `[0,W] x [0,H]` — never clamps. Clamping is how `map-the-old-world.json` became
   misregistered in S2.

7. **`tools/registration/terraqueous_globe.json`** — re-emitted, not shifted
   (measurement 2). Recover the NE-II fit from the committed record under the old
   frame (`cx=1999.55, cy=1129.29, sx=702.2114, sy=702.6857`, recovered at
   0.0019 px RMS), then write a fresh control-point table at named graticule
   crossings inside the new band — the same construction the record's own notes
   describe ("the control points below are that fit evaluated at named graticule
   crossings"). The two canvas-edge rows become central meridian x **74.9052N**
   and x **57.4084S**. Gate: re-fitting recovers all four constants to `< 0.01 px`
   at `rms_px <= 0.01`. A worse residual means the migration is wrong.

8. **`tools/fixtures/ingest/registration/synthetic_world.json`** — interior control
   points re-authored (measurement 4). The record's stated intent is "registers the
   synthetic fixture world edge-to-edge on the canvas", so the four corners stay —
   they *are* that constraint. The two interior points move to the canvas y of the
   latitude their source row implies under the new band (values emitted by step 6),
   keeping the equirectangular fit exact.

#### Phase 4 — the polar fix (absorbed from the superseded issue)

The reframe deletes the southern half of the defect and shrinks the northern
blank-page band from ~113–158 canvas rows to ~17–102 (measurement 10), but it
does not fix the classification. Two root causes remain, and both are fixed here.

9. **Make the paper rule spatial — `tools/worldgen/lut.py` + `tools/worldgen/ingest.py`.**
   The committed `paper_rgb [236,232,218]` and band 0 `[210,209,197]` are 40.6 RGB
   units apart while the actual polar page tone measures 42 units from paper and
   *closer to band 0*; a 3-unit LUT perturbation swings 37 points of the polar
   band. That is an ill-conditioned decision, not a mistyped constant, so it is
   removed rather than retuned:
   - `lut._palette` **drops paper from the nearest-RGB palette**. Classification
     becomes the 14 terrain bands only, with no two-way tie to lose.
   - A new spatial pass marks polar waste: flood from the oval's north rim
     (the crop's top edge, restricted to columns inside the fitted NE-II envelope)
     through pixels that are *not terrain colour* — winning band 0 together with a
     poor LUT distance. Everything the flood reaches becomes **land** at
     `paper_elevation_m` (300 m); everything it does not reach keeps its band
     verdict.
   - Measured justification (measurement 8): 98.6% of band-0 pixels are enclosed
     components that the flood never reaches, so real abyssal basins are untouched
     **by construction** rather than by threshold luck. The build reports the
     flipped-pixel count and the enclosed-basin count so the 98.6/1.4 split is
     visible in `COVERAGE.md`, not assumed.
   - `tools/lut/terraqueous_elevation.json` keeps `paper_elevation_m` (still the
     elevation the rule assigns) and its `notes` are rewritten: `paper_rgb` is no
     longer a classification swatch, and the note asserting the nearest-RGB rule
     is deleted rather than left to mislead.

10. **Fix the latitude-blind despeckle — `tools/generate_heightmap.py`.**
    `SOURCE_MIN_BLOB = 900` (`:114`) is fixed in *source* px while the
    reprojection stretch is strongly latitude-dependent, which is what turns a run
    of a few ambiguous source pixels into a several-hundred-px needle.
    `SOURCE_MAJORITY = 7` stays in source px — it targets drawn strokes, which are
    genuinely source-scale features — but the min-blob despeckle moves to the
    **canvas side**, where `CANVAS_MIN_BLOB` already means one thing and area is
    screen area. The existing comment's concern (a glyph is recognisably small at
    native size, and 4x larger after reprojection) is answered by raising the
    canvas threshold to the reprojected equivalent rather than by keeping a
    threshold whose meaning varies 2.3x across the map. The build reports the
    blob-count delta so the change is measured, not assumed.

11. **Acceptance test for the fix** — the superseded issue's own criteria, which
    remain the right ones, minus the one measurement 9 disproves:
    - Rows 0..220 of `map_data/heightmap.png` decode to a plausible waste
      elevation (~300 m), **not** the −888 m abyssal floor.
    - **No land component in canvas rows 0..260 with bounding-box aspect ratio
      > 8 and area < 40,000 px** — the needles and spikes are gone.
    - The southern join is a smooth boundary, reported as the count of connected
      components in the top band (currently 12).
    - **"No land pixels on canvas row 0" is explicitly retired as a test.** Polar
      waste is land by design, it is what the LUT always intended, and vanilla
      ships 42.7% of its own rows 0–200 above the ocean floor (measurement 9).
      Recording *why* is the acceptance criterion's own escape hatch.

12. **`tools/fixtures/ingest/`** — extend `make_source.py` with the case that let
    this ship: a **blank polar band contiguous with the north rim** and, in the
    same image, an **enclosed basin painted the same colour** at mid-latitude.
    Assert the first classifies as land at the waste elevation and the second
    stays sea. This is the direct regression test for measurement 8's 98.6/1.4
    split, and it rides the existing golden + determinism harness with no new
    machinery.

#### Phase 5 — regenerate, in dependency order

13. `python tools/generate_heightmap.py --mask-only` → new
    `tools/derived/land_sea_mask.png`.

14. **Deliverable #1 and the visual gate.** `tools/qa_overlay.py` gains `--plain`:
    write the warped source alone, without blending against `land_sea_mask.png`
    and without requiring it. Then
    `python tools/qa_overlay.py terraqueous_globe.jpg --plain --step 2` writes
    `tools/derived/qa_terraqueous_globe.png` at 4096x1808 — the Miller-reprojected
    globe. No new script is needed; `qa_overlay` already warps a registered source
    onto a reduced canvas. Local-only: it embeds source pixels, `tools/.gitignore`
    already excludes `derived/` by default, and it must **not** be added to the
    negation list. **Send it to the user and stop.** Nothing below runs until
    approved.

15. `python tools/generate_heightmap.py` → `map_data/heightmap.png`;
    `python tools/generate_rivers.py` → `map_data/rivers.png`.

16. **Re-fit the registration family against the new mask**, in dependency order:
    `total_war_map_colored`, `wh3_dlc_ie_parchment_map_english`, then
    `ie_macro_twin`, `ie_feature_image`, `ie_named_regions`. Report against the
    committed baselines:

    | Record | coarse IoU | refined IoU | landmark mean / max |
    |---|---|---|---|
    | `total_war_map_colored` | 0.5352 | 0.6617 | 312.2 / 844.6 |
    | `wh3_dlc_ie_parchment_map_english` | 0.5017 | 0.6193 | 426.9 / 872.1 |

    **No seed landmark edits** (measurement 3). The only seed change this should
    need is the `coarse` bracket: Miller moves the world down (max landmark \|dy\|
    **334.4 px**, dx **+2.0** uniform) and stretches it ~10% vertically, so
    `total_war_map_colored`'s optimum should move from scale_y 0.325 → ~0.358
    (bracket [0.26, 0.39]) and offset_y −14 → ~−10 (bracket [−32, 4]) — both
    interior, so the brackets should hold. **If a reported optimum lands on a
    bracket edge, widen the seed and re-run.** If a landmark check is materially
    worse than baseline, **stop and report** — do not adopt. Note the polar fix
    changes the silhouette these are scored against, so some movement is expected
    and is not by itself a regression.

17. `python tools/generate_state_labels.py --preview` → `state_labels.png`,
    `state_labels_index.json`, `COVERAGE.md`. Then
    `python tools/render_named_map.py --globe --tiles` → `tools/derived/named/`.

#### Phase 6 — fixtures and docs

18. **`tools/fixtures/ingest/expected/`** regenerated (`land_sea_mask.png`,
    `heightmap.png`, `ingest_stats.txt`) — frame-dependent *and* touched by the
    polar fix. **`tools/fixtures/boundary/expected/` is expected NOT to change**:
    it uses `control_point_warp` / `frame_alias` records against its own synthetic
    `mask.png` and never converts to lon/lat. If it changes, that is a **finding**
    — something frame-dependent leaked into the boundary path — and it must be
    explained before the golden is re-baked.

19. **`tools/run_fixture.py`** — new round-trip coverage: `canvas_to_lonlat` of
    `lonlat_to_canvas` is identity to 1e-9 in latitude across the full canvas and
    modulo width in longitude, at both `PROVINCES_SIZE` and `HEIGHTMAP_SIZE`; plus
    the non-uniform-grid assertion raising; plus the Phase 4 polar fixture.

20. **Docs** — see the table below.

### Design Decisions

- **The band is pinned to the user's drawn northern line, not to vanilla.** The
  markup made the open decision a measurement: `Y0 = 2142.0` is the minimum of both
  total and unmarked land loss, and puts the canvas top exactly on the line.
- **True, unscaled Miller at vanilla's canvas size.** A y-compression would fit the
  whole marked band but distorts every latitude including the Old World; growing
  the canvas has no precedent in any installed mod (measurement 7).
- **The polar rule becomes spatial, and paper leaves the palette.** The
  colorimetric decision is ill-conditioned by measurement, so it is removed rather
  than retuned — retuning it would be fitting noise. The spatial rule separates
  the two populations 98.6% / 1.4% (measurement 8), which is a structural property
  of the artwork rather than a threshold.
- **Polar waste is land, and land at row 0 is correct.** Canon (the Chaos Wastes
  are frozen waste, not ocean), the LUT's own stated intent
  (`paper_elevation_m: 300`), and vanilla's shipped heightmap (measurement 9) all
  agree. The request's "no land on row 0" criterion is retired with that reason
  recorded.
- **Delete the plate-carrée constants rather than redefine them.** An
  `AttributeError` at import beats a plausible wrong number at runtime.
- **Re-emit the globe record; migrate everything else.** Its polar control points
  cannot survive the reframe (measurement 2).
- **Seeds are source-anchored, so they migrate for free.** The single most useful
  thing found while planning: `anchor_landmarks` converts globe source px through
  the NE-II fit at fit time, so the whole seed-driven family follows the frame
  automatically (measurement 3).
- **`tools/worldgen/cells.py` needs no code change.** It works in canvas px, and
  canvas area is *screen* area — what the player and the engine both see. Under
  Miller a canvas pixel is no longer a constant number of square degrees, which
  makes this arguably more correct than before. The thresholds and per-region
  density targets will land differently; re-targeting them is out of scope (see
  "Now unowned").

### Edge Cases

- **Off-canvas control points.** The globe's two polar picks are the known case;
  the migration script fails loudly rather than clamping.
- **Wrap seam.** `lonlat_to_canvas` folds, `canvas_to_lonlat` does not, so a
  control point at x = WIDTH survives as +180. Pinned by step 19.
- **Non-uniform grid.** The assertion exists so a future non-multiple grid raises
  rather than distorting latitude silently.
- **The polar flood escaping south.** If the rim flood leaks through a gap in the
  drawn coastline it could paint a large area of real ocean as waste. Guard: cap
  the flood at a committed maximum latitude (it has no business below ~70N) and
  report the flooded area; a flood larger than the top band is a failure, not a
  result. The fixture's enclosed basin is the inverse test.
- **The polar band abutting the canvas edge.** With the top rows now land, the
  mask's north edge is a straight cut. That is intended and matches vanilla, but
  `segment.clean_land_mask`'s `close_radius`/`open_radius` operate without
  wrapping in y — confirm the morphology does not eat a row at the boundary.
- **`coarse` bracket edge.** Predicted interior, but predicted from an affine
  approximation to a nonlinear reframe *and* against a silhouette the polar fix
  changes. Check the reported optimum; don't assume.
- **`assign_macros` hard-errors** if the recovered contour count differs from
  `macro.PRINTED_COUNTS` (16). A materially worse master fit breaks contour
  closure — loud, not silent, but it is why step 16 reports before adopting.
- **The 0.363-vs-0.0019 confusion.** Holding the wrong number would either pass a
  broken migration or fail a correct one. The plan pins 0.0019.
- **Byte reproducibility.** No wall-clock and no unseeded RNG is introduced;
  `math.log` / `math.atan` / `math.exp` on float64 are deterministic, and the
  flood fill must iterate in a fixed order. Verify by running the generators twice
  into scratch dirs and diffing bytes.
- **MP desync is not reachable.** Nothing under `tools/` is loaded by Victoria 3.
  The property at stake is regeneration reproducibility.

### Testing

Nothing in this request is loaded by Victoria 3 — every output lives under
`tools/` and `map_data/`, and `map_data/provinces.png` does not exist until S3b —
so there is no `error.log` gate and no in-game step. The
[testing.md](../../.claude/rules/testing.md) requirement is satisfied vacuously
and deliberately.

```bash
python tools/measure_vanilla_frame.py
python tools/worldgen/sources.py --verify
python tools/validate_map.py --labels
python tools/run_fixture.py --check
```

Plus: the globe re-fit recovers `cx/cy/sx/sy` to <0.01 px at <=0.0019 px RMS; the
Phase 4 acceptance tests (step 11) pass; two consecutive generator runs are
byte-identical; and **the Miller globe render and the regenerated `derived/named/`
sheet go to the user**. The rendered map is the real gate — every offline check
has been green before while the map was visually unusable.

### Docs to Update

| File | Change |
|---|---|
| `tools/SOURCES.md` | Globe role text: NE-II → **Miller**, not plate carrée; new fit numbers for the re-fitted family. `terraqueous_globe_for_reprojection.jpg` is **not** added — it is markup, not a source |
| `tools/PROVENANCE.md` | The frame's provenance is now a measurement against the vanilla install plus the user's drawn northern limit; name `measure_vanilla_frame.py` |
| `tools/MAP_RUNBOOK.md` | New authoring commands (`measure_vanilla_frame.py`, `migrate_frame_coords.py`), `qa_overlay.py --plain`, and the Phase 5 regeneration order |
| `tools/lut/terraqueous_elevation.json` | `notes` rewritten: `paper_rgb` is no longer a classification swatch; the nearest-RGB assertion is deleted, not softened |
| `tools/derived/COVERAGE.md` | Regenerated — never hand-edited. Gains land-loss-to-reframe, the row-0 / row-3615 measurement, and the polar flood's flipped-pixel vs enclosed-basin counts |
| `.claude/agents/cartographer.md` | `:56` `LAT_MAX = 79.453125` → the Miller band; `:98` the 79.45N stretch figure |
| `.claude/agents/geographer.md` | `:58`, `:64`, `:77` — same |
| `CLAUDE.md` | `tools/` row: the canvas is Miller, measured from vanilla and pinned to the user's northern limit |
| `.claude/rules/testing.md` | **No change** — the gate triple is unchanged |
| Superseded docs | `world-map-source-driven.md`, `world-map-parchment-areas-onto-globe.md`, `s3a2-review-panel-handoff.md`, `chaos-wastes-polar-fringe-misclassified.md` — `Status: superseded` plus a pointer here (step 2) |

### Now unowned — needs its own request after this lands

Retiring the other documents leaves real work with no home. Recorded here so it
is dropped deliberately rather than lost:

- **Per-region state-density targets.** `TARGET_LAND_STATES = 659` /
  `TARGET_SEA_ZONES = 103` (`tools/generate_state_labels.py:67-68`) against a
  vanilla measurement of **675 land + 106 sea**, and the named-region requirements
  (Bretonnia ≥15, Empire ≥30, Cathay ≥40, 600–700 total). The reframe moves every
  one of these numbers; retargeting is a follow-up, not part of this change.
- **The corner-splinter artifact** in the state-label layer.
- **Name binding** — the parchment's printed labels bound to traced cells, and the
  alias table for the eleven forced single states. The geometry work survives in
  the committed code; the naming milestone does not have a plan any more.
- **S3b**: `provinces.png`, `adjacencies.csv`, `default.map`, state-region `.txt`.

### Localization

None. No user-facing string, no loc key, and no `common/` or `events/` script is
touched, so no `localization/english/` or `localization/replace/english/` entry is
required. `docs/*.log` has no bearing on this request — no effect, trigger,
modifier, event target or on_action is involved. The eventual naming pass will
need loc entries; it is listed under "Now unowned" above.
