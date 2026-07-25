# World Map (source-driven redo) — Known World physical map traced from reference imagery

| Field | Value |
|-------|-------|
| Type | request |
| Status | planned |
| Date | 2026-07-21 |
| Priority | high |

> **Supersedes [world-map.md](world-map.md) and its child plans [world-map-p2-heightmap.md](world-map-p2-heightmap.md) / [world-map-p3-provinces-states.md](world-map-p3-provinces-states.md) / [world-map-p4-scaffold-boot.md](world-map-p4-scaffold-boot.md).** Same end goal (entire Known World physical map + throwaway scaffold that boots into a session), same canvas, same MP-safety model. What changes is the **front of the pipeline**: geometry is now **derived from committed reference imagery** (`sources/`) instead of hand-encoded as JSON coordinate lists. The built P1 toolchain ([world-map-p1-tooling.md](../done/world-map-p1-tooling.md)) is **reused**, not discarded — this redo replaces the geometry-authoring model, not the whole toolchain.

## Description

Rebuild Victoria 3's map as the entire **Warhammer Fantasy Known World** (physical layer only), this time by **image-processing the reference maps the user compiled in `sources/`** — reprojecting, registering, segmenting, and tracing them onto the Vic3 canvas — rather than typing coastline/relief/state coordinates by hand from memory.

The previous attempt ([world-map.md](world-map.md)) hand-encoded the world's geometry as JSON polylines under `tools/worldgen/geometry/`. Its own P2 plan flagged the weakness: *"encoding a recognizable whole-world coastline as coordinates — without tracing reference images — is bounded in accuracy."* The `sources/` folder is the fix. This request re-scopes the physical-map effort around a **source-ingestion / extraction stage** that produces the same downstream geometry the existing generators already consume, so `raster.py`, `statefile.py`, `validate_map.py`, and the fixture harness stay in service.

Scope decisions taken with the user (2026-07-21):

1. **Reset the whole map pipeline** — this request replaces `world-map.md`'s production model and its P2–P4 child plans. `/plan` re-phases the physical map end-to-end (ingestion → boot) around source derivation. The built P1 tooling is reused where still valid; `world-map-p1-tooling.md` stays in `planning/done/`.
2. **`sources/` stays local, gitignored** — the toolchain reads the reference images from local disk; `sources/` is added to a repo-root `.gitignore` and never committed (third-party IP + ~40 MB of binaries). Provenance + a checksum manifest are committed in its place. The **committed generated bitmaps** (`map_data/provinces.png`, `heightmap.png`, …) remain the authoritative, MP-synced artifacts — gameplay/MP determinism does not depend on `sources/`.
3. **Image-process / trace directly** — the ingestion stage reprojects and traces the sources onto the canvas: whole-world sources → coastline + heightmap; detailed regional maps → state/province boundaries. Highest fidelity to the compiled references; most new tooling.

Everything else from the prior request's design that is **not** about how geometry is authored still holds and is inherited by reference (extent = entire Known World; vanilla-identical canvas; `wrap_x = yes`; hybrid-fringe Chaos Wastes; Voronoi province subdivision of state cells; zz-placeholder scaffold; `replace_paths` list; loc conventions; determinism-by-committed-bitmaps). `/plan` should pull those forward from [world-map.md](world-map.md) rather than re-deciding them.

## Context

- **Prior state**: [world-map.md](world-map.md) master request (status `planned`) + six-child plan. Only **P1 (tooling) is built** (commit `fef6ccd`, resolved in `planning/done/`); P2/P3/P4 were planned but never built; P5/P6 were never planned. So nothing under `map_data/`, `common/`, `gfx/`, or `localization/` exists yet — the redo starts from the same clean slate, just with a better front-end.
- **What P1 already gives us (reused)**:
  - `tools/config/map_config.py` — committed `SEED`, canvas dims `PROVINCES_SIZE=(8192,3616)` / `HEIGHTMAP_SIZE=(16384,7232)`, id bands (`LAND_ID_START=1`, `SEA_ID_START=3000`), `WRAP_X=True`, AUTOGEN marker. **Reused unchanged.**
  - `tools/worldgen/raster.py` — lossless indexed-PNG IO (no AA / no lossy re-save), deterministic globally-unique colour allocator, wrap-aware distance / Voronoi / polygon-fill / connectivity. **Reused** — Voronoi still subdivides state cells into provinces; the coastline it fills now comes from tracing instead of hand-typed polygons.
  - `tools/worldgen/statefile.py` — state-region text emission + hub auto-pick. **Reused.**
  - `tools/validate_map.py` — the pre-commit linter (province uniqueness, hub membership, port/naval-exit rules, id bands, loc coverage, lakes-not-in-states, both-direction bitmap↔state cross-check). **Reused + extended** with source-registration checks.
  - `tools/run_fixture.py` + `tools/fixtures/**` — offline determinism/regression harness with golden outputs. **Reused / adapted** (add a synthetic "traced" fixture).
  - `vic3-tiger.conf`, `tools/MAP_RUNBOOK.md`, `tools/PROVENANCE.md` skeletons. **Reused.**
  - **What changes in the toolchain**: `tools/worldgen/schema.py` — the *downstream* schema (coastline polygons, relief, rivers, state cells) is kept so generators stay compatible, but its geometry is now **produced by the ingestion stage**, and a **new upstream schema** describes source registration (per-source projection, control points, crop, role). A **new ingestion module set** (reproject / segment / trace / mosaic) is added.
- **`sources/` inventory** (measured 2026-07-21; all local, to be gitignored):

  | File | Dims | Projection / nature | Role in pipeline |
  |---|---|---|---|
  | `ljzbtm288r891.jpg` ("Terraqueous Globe") | 4000×3256 | Natural Earth II pseudocylindrical (oval); **real elevation ramp −7000→+7000 m** + polar insets | **Whole-world heightmap** (color→height LUT) + whole-world coastline — **needs reprojection** to the flat canvas |
  | `images.steamusercontent.jpg` | **637×358** | Already rectangular (equirectangular-ish) satellite/biome render | **Coarse whole-world registration + land/sea layout** — low-res, so a *reference frame*, not a tracing master |
  | `map-the-old-world.jpg` | 3016×2080 | GW regional map, top-down | **Old World / Badlands / Dark Lands / Araby / Land of the Dead** state & province boundaries |
  | `TheEmpire.webp` | ~ (webp) | GW Empire provinces map | **Empire internal state subdivision** (Reikland, Ostland, Talabecland, Stirland, Averland, Middenland, Nordland, Ostermark, Wissenland, Sylvania, Hochland, Mootland) |
  | `tww3_map_stitched.png` (+ `_top/bot_left/right`, `.paint`) | 2531×1961 | Total War: Warhammer 3 Immortal Empires campaign relief, near-top-down | **High-detail coastline + relief** for its covered arc (Naggaroth/Lustria/Ulthuan → Old World → Southlands → Dark Lands → western Cathay/Ind) |
  | `Warhammer_olde_world_map.webp` | ~ (webp) | "Landes & Seas of the Worlde," whole-world stylized, every region labelled | **Naming + extent confirmation** (Nippon, Ind, Khuresh, Cathay, Ogre Kingdoms, Eastern Steppes placement) |
  | `updated-warhammer-the-old-world-map…webp` | ~ (webp) | Old World relief w/ faction shields | Old World relief cross-check |

- **Key practical finding**: there is **no single high-resolution, already-equirectangular, whole-world source.** The one rectangular whole-world image is 637 px wide; the high-res whole-world image is in Natural Earth II; the sharpest sources are regional. So "trace directly" is a **mosaic-and-register** problem — align mixed-projection, mixed-resolution partial sources onto one canvas via hand-picked control points, then composite. This is the central new tooling challenge and the main thing `/plan` must design.
- **Format authorities unchanged**: vanilla `game\map_data\state_regions\state_regions.md`, `strategic_regions.md`, `geographic_regions.md`, `strait_definitions.md`, and `common\terrain\01_terrain.txt` remain the ground truth for the text formats. **Realms of Exether** remains the working 1.13 total-conversion reference for `replace_paths` + the boot scaffold.

## Acceptance Criteria

**Source ingestion & registration (new):**
- [ ] `sources/` is gitignored (repo-root `.gitignore`) and never committed; a committed **manifest** (`tools/SOURCES.md` or similar) lists each source's filename, dimensions, SHA-256, origin, and pipeline role, so the exact inputs are auditable without shipping the art.
- [ ] Each source used has a committed **registration record** (projection type, hand-picked control points / crop, target canvas footprint, role) under `tools/` — enough to re-derive its placement deterministically given the local file.
- [ ] The Terraqueous elevation ramp is captured as a committed **colour→height LUT**; the heightmap derivation is reproducible from `(local source + committed LUT + committed control points)`.
- [ ] Whole-world sources reprojected to the flat canvas (Natural Earth II → equirectangular for Terraqueous; direct for the satellite render); regional sources georeferenced onto their canvas footprint; overlaps composited by a documented precedence (hi-res regional wins inside its footprint, whole-world fills the rest).

**Physical map bitmaps (generated in code, committed):**
- [ ] `map_data/provinces.png` at 8192×3616, pixel-exact, every province a unique `xRRGGBB`; land/sea boundary **traced from the composited coastline mask**; whole Known World present.
- [ ] `map_data/heightmap.png` at 16384×7232 (true 16-bit grayscale) derived from the composited relief (Terraqueous LUT + TW3/Old-World relief where sharper), then **repacked via the in-game map editor** per the runbook (committed `packed_heightmap.png`, `indirection_heightmap.png`, `heightmap.heightmap`, `nodes.dat`).
- [ ] `map_data/rivers.png` for the v1 canon river list (per [world-map.md](world-map.md)), traced from the regional sources, vanilla palette.
- [ ] `map_data/default.map` (`wrap_x = yes`, `sea_starts`, `lakes`), `map_data/province_terrains.txt`, `map_data/adjacencies.csv` — as specified in the prior P3 plan.

**Regions / states / scaffold / boot (inherited from prior plan):**
- [ ] Engine invariants hold (province in exactly one state; sea state = one province; coastal state has `port` + valid `naval_exit_id`; every state in exactly one strategic region; hubs are own-state provinces) — enforced by `validate_map.py`.
- [ ] `common/strategic_regions/`, `common/geographic_regions/`, `common/strait_definitions/` populated per the prior plan.
- [ ] `.metadata/metadata.json` gains the `replace_paths` set from [world-map.md](world-map.md); throwaway `zz_placeholder` scaffold + vanilla-filename overrides land in the same milestone.
- [ ] **Game boots to main menu and into a session**; `Documents/Paradox Interactive/Victoria 3/logs/error.log` has zero lines referencing this mod's files ([testing.md](../../.claude/rules/testing.md)). Map editor round-trips; terrain/state/SR map modes spot-checked.

**Tooling & reproducibility:**
- [ ] New ingestion modules committed under `tools/` (reprojection, segmentation, tracing, mosaic/compositing) with deterministic output given the local sources + committed registration data.
- [ ] `validate_map.py` extended; `run_fixture.py` gains a synthetic traced-source fixture with golden outputs so the ingestion path is regression-checked offline.
- [ ] `tools/MAP_RUNBOOK.md` + `tools/PROVENANCE.md` updated; `tools/requirements.txt` updated for any new image-processing dependency.
- [ ] Documented reproducibility contract: the map is regenerable from **`tools/` + the local `sources/` folder** (not from a clean clone alone — see Constraints); committed bitmaps are the MP source of truth regardless.

**Localization:** unchanged from [world-map.md](world-map.md) — every `STATE_*`, sea, `region_*`, geographic region (+`_desc`), and hub name; AUTOGEN skeletons ship with the phase that introduces the keys; canon naming pass reads names off `Warhammer_olde_world_map.webp` + the regional maps.

## Investigation

- **What exists**:
  - Prior plan of record: [world-map.md](world-map.md) (+ P2/P3/P4 in `planning/requests/`, P1 in `planning/done/`). This request supersedes the first four; `/plan` or the first `/build` should move `world-map.md` + `world-map-p2/p3/p4` to `planning/rejected/` with a one-line "superseded by world-map-source-driven.md" note, and leave `world-map-p1-tooling.md` in `done/` (reused).
  - Built toolchain under `tools/` (see Context — `config/map_config.py`, `worldgen/{schema,raster,statefile}.py`, `validate_map.py`, `run_fixture.py`, `fixtures/**`, `MAP_RUNBOOK.md`, `PROVENANCE.md`), plus `vic3-tiger.conf`, `.gitattributes`.
  - `sources/` (untracked, `?? sources/`) — the 12 reference files inventoried above.
  - Repo-root `.gitignore`: **does not exist yet** (only `tools/.gitignore` for `.venv`/`__pycache__`/`fixtures/_out`). Adding `sources/` needs a new root `.gitignore`.
- **What changes / gets created**:
  - `.gitignore` (repo root) — add `sources/`.
  - `tools/` ingestion stage (new modules; exact layout is a `/plan` decision) — reprojection (Natural Earth II → equirectangular), land/sea segmentation, coastline/river tracing, control-point georeferencing + mosaic compositing, elevation-ramp LUT extraction.
  - `tools/worldgen/schema.py` — extend with the source-registration schema; keep the downstream geometry schema so generators are unchanged.
  - `tools/SOURCES.md` (manifest w/ SHA-256) + `tools/PROVENANCE.md` update; `tools/requirements.txt` update.
  - All the generated content from the prior plan (`map_data/*`, `common/strategic_regions|geographic_regions|strait_definitions`, scaffold `common/*`, `localization/english/map/*`, `.metadata/metadata.json` `replace_paths`) — unchanged targets, now fed by traced geometry.
- **Constraints**:
  - **No single hi-res equirectangular whole-world source** (see Context) → mosaic of mixed projections/resolutions with hand-picked control points is unavoidable; per-source alignment error is a real risk and a `/plan` concern, not a boot-gate condition (boot gate = clean `error.log`, not cartographic exactness).
  - **New dependency likely**: reprojection + contour tracing beyond Pillow/numpy may need `scipy`, `opencv-python`, or `scikit-image`. Adding deps is a `/plan` decision (prior toolchain deliberately pinned only Pillow+numpy); whatever is chosen goes in `tools/requirements.txt` and must stay deterministic (no wall-clock/OS entropy).
  - **Reproducibility is weakened by the gitignore decision**: with `sources/` local-only, the map is **not** regenerable from a clean clone — only from a clone **plus** the user's `sources/`. The committed bitmaps remain byte-identical across MP clients (so MP/gameplay determinism is fully preserved — [core.md](../../rules/core.md)); it is only the *regenerate-from-scratch* property that now depends on local inputs. The committed manifest (filenames + SHA-256) mitigates by pinning exactly which inputs produced the committed output.
  - **IP / provenance**: `sources/` mixes GW-published cartography, a Total War screenshot mosaic, and fan cartography — kept out of the repo by decision #2. Only our derived bitmaps (our own pixels) are committed; `PROVENANCE.md` + the manifest record what was consulted. This is stricter than, and consistent with, the prior request's IP stance.
  - **Determinism of image processing**: deterministic given fixed inputs + fixed control points + committed `SEED`; enforce via the fixture harness (re-run → byte-identical) exactly as P1 did.
  - **Unchanged engine constraints**: vanilla canvas (8192×3616 / 16384×7232, tile_size 65); `provinces.png` pixel-exact; replacing `map_data/state_regions` requires `replace_paths` + scaffold in the same milestone or the game won't boot; map-editor artifacts (`packed_heightmap`, `nodes.dat`, locators) stay human-run per the runbook (no desktop GUI automation in this environment).
- **Related files**: [world-map.md](world-map.md) (inherited design decisions — the authority for everything not about geometry authoring); `tools/**` (reused toolchain); vanilla `state_regions.md` / `strategic_regions.md` / `geographic_regions.md` / `terrain\01_terrain.txt` (formats); Realms of Exether (`replace_paths` + boot reference); `docs/event_targets.log` (confirms `state_region`/`strategic_region` scopes for future script — no script added here).
- **Endpoints / commands**: **no script surface added** — this request introduces zero effects/triggers/modifiers/event-targets/on-actions, so `docs/*.log` has nothing to confirm for it (the map layer is native bitmap/database content, not scripted). New identifiers exposed to future script are the same as before: `STATE_*` keys, sea-zone ids, `region_*` keys, geographic-region `short_key`s.
- **Tests required**: offline `validate_map.py` + `vic3-tiger` on generated text; `run_fixture.py --check` determinism/regression incl. the new traced-source fixture; in-game session boot with clean `error.log`; map-editor round-trip; map-mode visual spot-checks. Additionally: a visual QA pass overlaying the generated coastline against the registered sources (alignment sanity), since fidelity is the whole point of the redo.
- **Out of scope** (unchanged from [world-map.md](world-map.md), plus): real nations/cultures/religions/pops/economy/buildings/tech/laws/flags; papermap/loading-screen/city-art/3D polish; music/sound; non-English loc; content east of the geography. **Also out of scope**: committing `sources/` or any third-party art; a fully-headless generator for the map-editor binaries; pixel-perfect cartographic exactness (good-faith registered tracing, not survey accuracy).
- **Localization needed**: same key set as [world-map.md](world-map.md) — thousands of `STATE_*` / sea / `region_*` / geographic-region(+`_desc`) / hub keys, AUTOGEN skeletons per phase, canon names read from `Warhammer_olde_world_map.webp` + the regional maps in the naming pass.

---

## Plan

Master plan for the source-driven physical-map redo. Re-phases the whole physical
map end-to-end (source ingestion → session boot) into **S0–S6**, superseding
[world-map.md](world-map.md)'s P1–P6 breakdown. Each S-phase is an independently
`/build`-able milestone with its own gate; S1–S3 are detailed here to file level
(the novel ingestion work), S4 inherits old [P4](world-map-p4-scaffold-boot.md)
almost verbatim, and S5–S6 inherit old P5/P6 with their detailed `/plan` deferred
until real state data exists (exactly as world-map.md deferred P5/P6). User
decisions taken 2026-07-21 (this session): dependency stack and the ingestion
hand-off model are left to my judgment for best outcome, and the built P1
toolchain is to be treated as *suspect* — audited and reworked where weak, not
preserved for its own sake.

### Objective

Rebuild the entire Warhammer Known World physical map by **image-processing the
committed `sources/` reference imagery** (reproject → register → segment → trace →
composite) into the same downstream artifacts the built P1 toolchain already
produces, so `raster.py` / `statefile.py` / `validate_map.py` / the fixture
harness stay in service and only the *front of the pipeline* is new — then boot a
throwaway `zz_placeholder` scaffold into a live session with a clean `error.log`.

### Inherited design decisions (pulled forward from [world-map.md](world-map.md) — not re-decided)

- **Extent**: entire Known World (Old World, Ulthuan, Naggaroth, Lustria,
  Southlands, Darklands, Mountains of Mourn/Ogre lands, Cathay, Ind, Khuresh,
  Nippon, Eastern Steppes + oceans).
- **Canvas identical to vanilla**: `PROVINCES_SIZE = (8192, 3616)`,
  `HEIGHTMAP_SIZE = (16384, 7232)`, `tile_size = 65` — already committed in
  `tools/config/map_config.py`. Never changed.
- **`wrap_x = yes`**: lore-consistent circumnavigation; every distance/adjacency
  computation stays wrap-aware. (Reprojected equirectangular output is
  seam-clean in x *by construction* — a strict improvement over hand-typed seam
  polygons.)
- **Chaos Wastes — hybrid fringe**: canvas top/bottom cut inside the polar Wastes
  as vanilla cuts the Arctic; innermost band = `impassable = { … }` inside
  ordinary edge states; outer fringe = playable tundra/snow. No all-impassable
  states.
- **Voronoi province subdivision** of state cells (seeded, wrap-aware,
  vanilla-order density ~30–45k provinces); min-area merge + connectivity repair.
- **Placeholder economics** (uniform parse-valid values); real economy is a
  later request.
- **`zz_placeholder` throwaway scaffold** + the Exether-derived `replace_paths`
  set + vanilla-filename overrides in kept dirs (the full lists live in old
  [P4](world-map-p4-scaffold-boot.md) — inherited verbatim by S4).
- **Loc convention**: `localization/english/map/wh_{states,seas,strategic_regions,
  geographic_regions,hub_names}_l_english.yml`, UTF-8 BOM, `l_english:`,
  `# AUTOGEN` markers pending the S6 canon pass.
- **Determinism-by-committed-bitmaps**: every shipped artifact is a static
  committed file identical on all clients → MP-safe by construction
  ([core.md](../../.claude/rules/core.md)). Gameplay/MP determinism does **not**
  depend on `sources/`.
- **Rivers v1 canon list** and the vanilla format authorities
  (`state_regions.md`, `strategic_regions.md`, `geographic_regions.md`,
  `strait_definitions.md`, `01_terrain.txt`; Realms of Exether for
  `replace_paths` + boot) are inherited unchanged.

### New architecture — the source-ingestion front-end (the real design work)

**Two-stage pipeline with a committed *raster* hand-off.**

- **Stage A — ingestion (needs local `sources/`)**: reproject → segment →
  register → composite the mixed-projection, mixed-resolution partial sources
  onto one canvas. Emits committed *derived rasters* — `land_sea_mask.png` and
  `state_labels.png` (canvas-res, our own pixels), the 16-bit `heightmap.png`,
  and traced river polylines.
- **Stage B — generation (needs only committed data)**: the P1-lineage
  generators consume those rasters → `provinces.png`, state/SR/region text,
  `default.map`, adjacencies, loc.

**Why a raster hand-off, not the existing polygon JSON.** The built generators
already operate on *pixel sets* internally: `run_fixture.build_partition`
rasterizes coastline/state polygons to pixels and then Voronoi-labels pixels. The
polygon JSON is merely the *input format* the synthetic fixture happens to use.
Tracing produces masks natively, and round-tripping a traced mask back through
hand-authored polygons that must **exactly tile** the mask (the fixture's
`if set(owner) != land_mask: raise RuntimeError`, `run_fixture.py:124`) is brittle
and lossy. Consuming the composited mask directly is faithful to the acceptance
criterion "land/sea boundary **traced from the composited coastline mask**," and
yields a bonus property: `provinces.png` stays regenerable from the committed
`state_labels.png` + `SEED` **without** `sources/`. The polygon schema is
retained only for the synthetic fixtures and as an optional hand-correction path.

**Reuse posture — P1 is a starting point, not a fixed foundation.** P1's offline
gate currently passes (`run_fixture.py --check` and `validate_map.py --fixture`
both clean — verified this session), so it is *correct at fixture scale* (128×64).
It is **unproven at real-canvas scale** (~29.6M province px / ~118M heightmap px)
and carries architectural smells. Audit-and-rework plan:

- **Keep (sound disciplines):** the determinism config (`map_config.py`,
  committed `SEED`); the validate-on-load schema pattern (`schema.py`); lossless
  no-AA PNG IO and the deterministic globally-unique `ColorAllocator`
  (`raster.py`); wrap-aware distance/centroid math; the validator's *checks*
  (`validate_map.py`); the state-text emission + hub auto-pick (`statefile.py`);
  and the fixture/golden byte-exact regression *methodology* (`run_fixture.py`).
- **Rework (weak parts):**
  - Promote the generator logic currently living **inside** `run_fixture.py`
    (`build_partition`, `allocate_colors`, `repair_connectivity`,
    `merge_small_land`, `build_map`) into importable `tools/worldgen/` modules
    (`partition.py`, `generate_provinces.py`, …) that both the fixture and the
    real run import — the generator must not live only in the test harness.
  - Vectorize the brute-force hot paths that cannot scale: `voronoi_labels`
    (`raster.py:142`, O(pixels×seeds) pure Python) → `scipy.ndimage.
    distance_transform_edt(return_indices=True)` with horizontal wrap-padding;
    the per-pixel RGB write loop (`run_fixture.py:299`) → numpy scatter; the
    pure-Python `connected_components`/`ProvinceBitmap` in the validator →
    `scipy.ndimage.label` for the real bitmap.
  - Drop the polygon-exact-tiling partition model for the real world in favour
    of the label-raster path (above).

**Dependencies.** Add **scipy** and **scikit-image** (both pinned in
`tools/requirements.txt`); keep Pillow + numpy (Pillow 12.3.0 already reads every
source incl. `.webp` — no image-IO dep needed). Rationale: with install
size/time an explicit non-constraint, the pick is weighted on *best outcome +
determinism*. scikit-image's `transform.warp` / `PiecewiseAffineTransform` /
`measure.find_contours` / morphology / threshold tools are higher-level,
well-tested, and deterministic (numpy/scipy-backed); scipy supplies
`ndimage.distance_transform_edt` (vectorized wrap-padded nearest-label) and
`interpolate.RBFInterpolator` (control-point warp field). **opencv-python was
rejected** despite consolidating these ops, because its threaded/SIMD kernels
carry determinism caveats that are a poor fit for a byte-identical MP pipeline.
All chosen ops are deterministic given fixed inputs (no wall-clock/OS entropy,
no stochastic segmentation).

**Registration & manifest.** `sources/` is gitignored (repo-root `.gitignore`,
new) and never committed. In its place:
- `tools/SOURCES.md` — committed manifest: filename, auto-measured dims, SHA-256,
  origin, and pipeline role for each source (records `tww3_map_stitched.paint` as
  the editable master and `tww3_map_stitched.png` (2531×1961) as the consumed
  flat artifact).
- Per-source **registration records** (`tools/registration/<source>.json`,
  committed): projection type, hand-picked control-point pairs (source px ↔
  canvas px), crop (excludes e.g. Terraqueous' polar insets), target canvas
  footprint, role, and compositing precedence.
- Control points are **hand-picked by viewing each image** (Read tool renders
  JPG/PNG/WEBP) against a reference canvas layout — the judgment-heavy step, done
  during `/build`.
- A `tools/worldgen/sources.py` loader verifies each source's **SHA-256 against
  the manifest on load** and hard-fails on mismatch, so a swapped/edited source
  can never silently change a committed bitmap; refreshing a source is an
  explicit `--update-manifest` action.

**Reprojection** (two paths, both deterministic, numpy/scipy only):
1. **Terraqueous oval → equirectangular** via the published **Natural Earth II
   *forward* polynomial** implemented in-house — forward-only inverse-warp (for
   each target equirect pixel's (lon,lat), sample the source at
   `NE2_forward(lon,lat)`), so no iterative inverse and no `pyproj`. Control
   points fit the image's scale/center/graticule.
2. **Everything else** (GW regional maps, TW3 relief, the 637×358 satellite
   frame) via a **control-point smooth warp** — `RBFInterpolator` /
   `PiecewiseAffineTransform` building a source→canvas coordinate field, resampled
   with `ndimage.map_coordinates` / `skimage.transform.warp`.

**Segmentation, elevation, compositing.**
- Land/sea mask by colour threshold + `ndimage` morphology → the shoreline comes
  from the **mask**, not the noisy hillshaded elevation.
- Elevation from the committed **colour→height LUT** (Terraqueous ramp, broad
  bands), with TW3 / Old-World relief composited where sharper.
- **Compositing precedence** (documented): the hi-res regional source wins inside
  its registered footprint; the reprojected whole-world layer fills the rest.
  The 637px satellite render anchors the global lon/lat frame/extent; Terraqueous
  supplies detailed coastline + elevation within it.

**Determinism / reproducibility contract.** Every committed bitmap is a pure
function of `(local sources + committed registration records + committed
colour→height LUT + committed SEED + the pinned toolchain)`. The committed
manifest pins *which* source bytes produced the committed output. Regenerate-from-
clean-clone is (by the gitignore decision) **not** a property — regeneration needs
the clone **plus** the user's `sources/`; but MP/gameplay determinism is fully
preserved because the committed bitmaps are byte-identical across clients. Fixture
harness enforces "re-run → byte-identical" exactly as P1 did.

**Artifact provenance** (what's local vs. committed vs. sources-dependent):

| Artifact | Committed? | Needs `sources/` to (re)produce? |
|---|---|---|
| `sources/*` (12 images incl. `.paint` master) | **No** — gitignored | are the inputs |
| `tools/SOURCES.md` manifest (name, dims, SHA-256, origin, role) | Yes | no — audit record |
| Registration records (projection, control points, crop, footprint, role, precedence) | Yes | no |
| Colour→height LUT | Yes | no |
| `land_sea_mask.png`, `state_labels.png` (canvas-res, our pixels) | Yes | yes to re-derive; **no** to consume |
| `map_data/heightmap.png` (16-bit) | Yes (MP source of truth) | yes to re-derive |
| `map_data/provinces.png` | Yes (MP source of truth) | **no** — Voronoi from committed mask + SEED |
| state / SR / region / adjacency / loc text | Yes | no |
| Editor binaries (`packed_heightmap`, `indirection_heightmap`, `heightmap.heightmap`, `nodes.dat`, locators) | Yes | human editor step (runbook) |

### Steps (ordered) — S0–S6

**S0 — Housekeeping** *(first `/build`, before S1)*
- `git mv planning/requests/world-map.md planning/rejected/` and likewise
  `world-map-p2-heightmap.md` / `world-map-p3-provinces-states.md` /
  `world-map-p4-scaffold-boot.md`; append a one-line
  `> Superseded by world-map-source-driven.md` note to each.
- Leave `planning/done/world-map-p1-tooling.md` in `done/` (its toolchain is
  reused/reworked, not discarded).

**S1 — Source registration foundation** *(gate: offline)*
1. **`.gitignore`** (repo root, new) — add `sources/` (+ keep tools' existing
   ignores). No other tracked path affected.
2. **`tools/SOURCES.md`** (new) — the SHA-256 manifest (dims auto-measured with
   Pillow; roles per the request's inventory table).
3. **`tools/worldgen/schema.py`** — extend with a **registration schema**
   (`SourceRegistration`: role, projection kind, control-point pairs, crop,
   footprint, precedence), validated on load like the existing geometry schema.
4. **`tools/registration/<source>.json`** (new, committed) — one record per used
   source; control points hand-picked by viewing each image.
5. **`tools/worldgen/sources.py`** (new) — manifest loader + **SHA-256
   verify-on-load** guard + Pillow reader; `--update-manifest` refresh path.
6. **`tools/requirements.txt`** — add pinned `scipy` + `scikit-image`.
7. **`tools/PROVENANCE.md`** — record the real sources now consulted (supersedes
   the "none yet — P1 fixture only" row).
- Gate: manifest SHA-check passes against the local `sources/`; schema +
  registration records load; a registration self-test passes. No game-read files
  touched → purely offline (like the old P1 gate).

**S2 — Reproject + whole-world heightmap / coastline / rivers** *(gate: boots to **main menu**, `error.log` clean)*
1. **`tools/worldgen/reproject.py`** (new) — NE II forward polynomial +
   control-point warp; equirectangular output at canvas/heightmap res.
2. **`tools/worldgen/segment.py`** (new) — land/sea mask (threshold + `ndimage`
   morphology).
3. **`tools/worldgen/lut.py`** (new) — colour→height LUT extraction + apply
   (committed LUT under `tools/`).
4. **`tools/worldgen/composite.py`** (new) — precedence-based mosaic.
5. **`tools/worldgen/raster.py`** — add `write_gray16_png` (Pillow `I;16`) + mask
   IO (current writer is 8-bit RGB only).
6. **`tools/generate_heightmap.py`** (new) → **`map_data/heightmap.png`** (16-bit,
   16384×7232); emit committed **`land_sea_mask.png`**.
7. **`tools/generate_rivers.py`** (new) → **`map_data/rivers.png`** (v1 canon
   rivers traced from regional sources; sample vanilla palette at gen time).
8. **`tools/run_fixture.py`** — add a **synthetic traced-source fixture** (a tiny
   invented source PNG + registration → reproject/segment → mask) with byte-exact
   golden outputs. (Synthetic pixels — no third-party IP committed.)
9. **`tools/MAP_RUNBOOK.md`** — append the editor **heightmap-repack** section
   (open mod, pack, save; commit `packed_heightmap.png`,
   `indirection_heightmap.png`, `heightmap.heightmap`).
- Design: **heightmap + rivers only**; `provinces.png` / `default.map` /
  `state_regions` stay vanilla so the repo still parses and boots to the main
  menu — de-risks the editor+boot loop before the province overhaul (inherited
  from old P2).
- Gate: generators deterministic (re-run → byte-identical); after the editor
  repack, game reaches **main menu** and `logs/error.log` has zero mod-file
  lines; editor round-trip clean.

**S3 — Provinces + states from the composited label mask** *(gate: offline; repo intentionally unbootable until S4 — build back-to-back)*
1. **Regional segmentation → `state_labels.png`** (canvas-res, committed):
   traced Old World / Empire internal boundaries from `map-the-old-world.jpg` +
   `TheEmpire.webp` where we have them; seed-Voronoi (over the S2 land mask)
   fills the rest. Ocean → single-province sea-zone labels.
2. **Per-state metadata records** (committed) — `key` (`STATE_*`), macro,
   `coastal`, `naval_exit`, placeholder `economics`, optional `impassable`
   (geometry now comes from the label raster, not a polygon).
3. **`tools/worldgen/partition.py`** + **`tools/generate_provinces.py`** (new) —
   promote + **vectorize** the partition/subdivision logic out of
   `run_fixture.py`; wrap-aware Voronoi subdivision of each label region into
   ~40–70 provinces via `scipy.ndimage.distance_transform_edt`; reuse
   `ColorAllocator`, connectivity repair, min-area merge → **`map_data/provinces.png`**.
4. **`tools/generate_state_regions.py`** (new, reuses `statefile.py`) →
   **`map_data/state_regions/NN_<macro>.txt`** + **`99_seas.txt`**.
5. **`tools/generate_default_map.py`** → **`map_data/default.map`**
   (`wrap_x = yes`, full `sea_starts`, stateless `lakes`).
6. **`tools/generate_adjacencies.py`** → **`map_data/adjacencies.csv`** (verified
   10-column format + committed sea-crossing table).
7. **`common/strategic_regions/<area>_strategic_regions.txt`** +
   **`water_strategic_regions.txt`** — every state in exactly one SR.
8. **`localization/english/map/wh_{states,seas,strategic_regions}_l_english.yml`**
   — `# AUTOGEN` skeletons (ship with the keys they cover).
9. **`map_data/province_terrains.txt`** — minimal placeholder (land→`plains`,
   sea→`ocean`) so S4 can boot; S5 regenerates it properly.
10. **`tools/validate_map.py`** — extend with **source-registration checks**
    (every used source has a manifest + registration record; the label raster
    covers the land mask with no gap/overlap; footprints lie within the canvas);
    swap the pure-Python bitmap scans for `ndimage.label` at real scale.
- Gate: `validate_map.py` + `vic3-tiger` + `run_fixture.py --check` (incl. the
  new traced-source fixture) all pass. No game-load gate here.

**S4 — Scaffold + boot** *(the boot milestone; gate: **boots into a session**, zero mod-file lines in `error.log`)* — inherits old [P4](world-map-p4-scaffold-boot.md) **essentially verbatim**: `.metadata/metadata.json` `replace_paths`; `zz_placeholder` culture + `ZZA`–`ZZJ` tags; `tools/generate_scaffold.py` → `common/history/{states,pops,countries}` via verified effects only (`create_state`, `create_pop`, `add_homeland`, `activate_law`); vanilla-filename overrides in kept dirs; minimal replacements in replaced dirs; editor `nodes.dat` regen; `error.log` cleanup loop. **No source-driven change** — deferred detail lives in the old P4 file, to be pulled in when S4 is built.

**S5 — Terrain + visuals** *(inherits old P5; detailed `/plan` deferred until S3/S4 land)* — terrain assignment + all `gfx/map` visual layers + editor locator/spline regen + `content_source/map_objects`. **Source-driven improvement:** terrain/biome is now derivable from the satellite render + composited relief rather than hand-assigned.

**S6 — Regions + canon naming** *(inherits old P6; detailed `/plan` deferred)* — geographic regions, straits, and the canon naming pass over all loc. **Source-driven improvement:** the naming pass now reads canon place-names directly off `Warhammer_olde_world_map.webp` + the regional maps (Read tool), instead of from memory.

### Design Decisions
- **Committed raster hand-off** (masks, not round-tripped polygons) — faithful to
  "trace the mask," robust against a traced boundary, keeps `provinces.png`
  regenerable from committed data alone. (User: "do what you think is best.")
- **scipy + scikit-image, pinned; opencv rejected on determinism grounds** —
  best-outcome pick with size/time an explicit non-constraint. (User: "whatever
  you recommend for the best outcome.")
- **P1 audited & reworked, not preserved wholesale** — keep the sound disciplines,
  vectorize the brute-force primitives, promote generators out of the fixture
  runner, drop polygon-exact-tiling. (User: "existing P1 content is suspect.")
- **NE II reprojection is forward-polynomial + in-house** (no `pyproj`) so it is
  deterministic and dependency-light; regional/satellite sources use
  control-point warps.
- **SHA-256 verify-on-load** is the reproducibility guard that lets `sources/`
  stay local without risking silent bitmap drift.
- **Fidelity is best-effort, not a boot gate** — the boot gate is a clean
  `error.log`; cartographic exactness is checked by a visual overlay QA pass, not
  gated.
- Everything else (canvas, `wrap_x`, Chaos Wastes, Voronoi, scaffold model,
  `replace_paths`, loc conventions) is inherited from
  [world-map.md](world-map.md) unchanged.

### Edge Cases
- **NE II + hillshaded-colour elevation** are the two top fidelity risks — the
  oval's polar insets are cropped pre-reprojection; the coastline's crispness
  comes from the segmented mask (not elevation); TW3/Old-World relief is
  composited where the Terraqueous colour ramp is ambiguous. None of this is a
  boot-gate condition.
- **No single hi-res equirectangular whole-world source** → the mosaic is
  unavoidable; per-source alignment error is real and is why precedence +
  control-point warps + a visual overlay QA exist.
- **Real-canvas scale** (~29.6M / ~118M px): the P1 brute-force primitives
  (`voronoi_labels`, per-pixel loops, pure-Python connectivity) must be
  vectorized before the full run — flagged as S2/S3 rework, not discovered late.
- **Source swapped without a manifest refresh** → SHA verify hard-fails loudly.
- **Committed masks drifting from `sources/`** → the SHA pin + explicit
  `--update-manifest` is the only sanctioned refresh path.
- **Heightmap↔provinces coastline mismatch** → the land/sea mask is authored once
  in S2 and upscaled 2× (nearest) to force the heightmap shoreline to match the
  province shoreline exactly.
- **Seam continuity** at `x=0/x=8191` is automatic post-reprojection
  (equirectangular is periodic in lon); the province Voronoi wrap-pads the array.
- **Editor sessions rewriting generated text** (e.g. `province_terrains.txt`,
  locators) → `git diff` after every editor save; commit only the intended
  regeneration (inherited runbook discipline).
- **16-bit depth** — verify `heightmap.png` writes as true 16-bit grayscale
  (`I;16`), not 8-bit, or the editor pack rejects it.

### Testing
- **Offline** (every phase touching map text/bitmaps): `python tools/validate_map.py`,
  `python tools/run_fixture.py --check` (determinism + golden + validators, incl.
  the new traced-source fixture), `vic3-tiger`, and the SHA-256 manifest verify.
- **S2 gate**: after the editor heightmap repack, game reaches the **main menu**
  on the new relief; `Documents/Paradox Interactive/Victoria 3/logs/error.log`
  has zero lines referencing this mod's files ([testing.md](../../.claude/rules/testing.md)).
- **S4 gate (the milestone)**: game **loads into a session**; `error.log` clean
  of mod-file lines; map editor round-trips (`nodes.dat` regen); state/SR map
  modes spot-checked.
- **Fidelity QA** (not a gate): overlay the generated coastline against the
  registered sources to sanity-check alignment — fidelity is the whole point of
  the redo.
- Must pass at every game-gated phase: mod loads in Victoria 3 and `logs/error.log`
  shows no new errors referencing this mod's files.

### Docs to Update
- `tools/requirements.txt` — add pinned `scipy` + `scikit-image` (S1).
- `tools/SOURCES.md` (new, S1), `tools/PROVENANCE.md` (S1, real sources),
  `tools/MAP_RUNBOOK.md` (S2 heightmap repack, S4 `nodes.dat`).
- `CLAUDE.md` project-layout `tools/` row — note the ingestion stage +
  local-only gitignored `sources/` + the SHA manifest (S1).
- `.claude/rules/testing.md` — add the manifest-SHA verify + traced-source
  fixture to the offline map-lint step (S1).
- `.claude/rules/scripting.md` (Naming) + `.claude/rules/localization.md` —
  record the `wh_` prefix + `localization/english/map/` + `NN_<macro>.txt` /
  `<area>_strategic_regions.txt` conventions when the first such files land (S3),
  as the prior plan intended.
- `.claude/rules/interface.md` — `gfx/map` repaint set when S5 is planned.

## Resolution

**Phased delivery (S0–S6).** This master plan stays in `planning/requests/` until
all phases land; each `/build` milestone is recorded below as it is built. Moving
it to `planning/done/` waits for S6.

### S0 + S1 — source-registration foundation ✅ built (2026-07-21)

- **Commit**: `28d462c` — "World map S0+S1: source-registration foundation" (18 files).
- **Summary**:
  - **S0**: moved `world-map.md` + `world-map-p2/p3/p4` to `planning/rejected/`
    with a "superseded" note; `world-map-p1-tooling.md` stays in `planning/done/`
    (its toolchain is reused).
  - **S1**: repo-root `.gitignore` (`sources/` local-only, never committed);
    `tools/SOURCES.md` — SHA-256 manifest of all 12 sources (filename, dims, bytes,
    SHA-256, origin, role, registered); `tools/worldgen/sources.py` — manifest
    loader + **SHA-256 verify-on-load guard** + `--update-manifest` refresh +
    `--verify` self-test + verified `load_source_image`; `SourceRegistration`
    schema added to `tools/worldgen/schema.py` (projection / control points / crop /
    footprint / precedence, validated on load); `tools/registration/*.json` records
    for the 5 registered sources (Terraqueous, satellite frame, Old-World map,
    Empire map, TW3 stitched relief) with hand-picked control points;
    `tools/config/canvas_frame.py` — plate-carrée lon/lat frame + Natural-Earth-II
    oval reference + approximate feature anchors (S2-refined); `scipy` +
    `scikit-image` pinned in `tools/requirements.txt`; docs updated
    (`tools/PROVENANCE.md`, `CLAUDE.md`, `.claude/rules/testing.md`).
- **Tests / gate (offline, all green)**:
  - `python tools/worldgen/sources.py --verify` — manifest SHA-256 + registration
    cross-checks pass against the local `sources/`.
  - `python tools/validate_map.py --fixture` and `python tools/run_fixture.py
    --check` — the P1 gate stays green after the `schema.py` extension.
  - `--update-manifest` verified **idempotent**; the SHA-256 guard verified to
    **fire on a tampered manifest**, and `load_source_image` verified to **refuse**
    altered bytes; `scipy 1.15.3` / `scikit-image 0.25.2` confirmed to install on
    the pinned stack (Python 3.10.7, numpy 2.2.6, Pillow 12.3.0).
- **Not gated here**: cartographic fidelity of the control points is best-effort
  seeds (refined by S2's real reprojection + a visual overlay QA pass, per the
  plan). S1 touches **no game-loaded files**, so there is no in-game `error.log`
  gate for this milestone.
- **Post-build agent review**:
  - *docs-updater* — clean; all doc updates (CLAUDE.md, testing.md, PROVENANCE.md)
    verified accurate against the code (commands, paths, dep list, marker names),
    no edits needed.
  - *security-review* — **no critical / MP-desync findings**; the SHA-256 guard,
    manifest parser, and schema validator all held up under direct empirical
    attack (tampered bytes, malformed manifest rows, hostile registration JSON,
    out-of-bounds control points), and `--update-manifest` reproduced the manifest
    byte-for-byte. Two non-fatal warnings, both addressed in the follow-up commit:
    (1) `update_manifest()` silently flipped `Registered`→`no` when a registration
    record failed to load — **fixed**: it now surfaces a loud `WARNING` note and
    leaves the `Registered` column untouched (verified); (2) the plan file was
    untracked so the commit's links dangled — **fixed** by committing this file.
    INFO items deferred to S2: exact-pin `scipy`/`scikit-image` (or add a lock)
    before real reprojection lands; per-layer (relief vs. boundary) precedence.

### S2 — reproject + whole-world heightmap / coastline / rivers ✅ built (2026-07-24), **game gate pending**

- **Commits**: `64bf2f0` — "World map S2: reproject + whole-world heightmap /
  coastline / rivers" (40 files); `8e2a371` — "derive rivers from terrain
  drainage, not hand-drawn lines" (11 files).
- **Summary**:
  - **Reprojection**: `tools/worldgen/reproject.py` — Natural Earth II forward
    polynomial (constants from PROJ's `natearth2.cpp`) + a control-point
    thin-plate warp. The Terraqueous oval's projection was **measured, not
    assumed**: its drawn boundary was traced across 2001 rows and the NE-II
    envelope least-squares fitted, giving centre (1999.55, 1129.29), scale
    702.21/702.69, **inlier RMS 0.363 px**. Two independent confirmations —
    `sx/sy = 0.99933` (isotropic, as a true NE-II rendering must be) and the
    fitted graticule landing within ~2 px of the map's own printed degree labels.
    `tools/registration/ljzbtm288r891.json` was re-cut to exact graticule
    crossings, and `config/canvas_frame.ANCHORS` refined through the true
    projection (corrections up to 317 px — S1's equirectangular approximation was
    ~4° of longitude out toward the limbs).
  - **Elevation**: `tools/lut/terraqueous_elevation.json` — the 14-band legend
    ramp sampled from the source (per-channel sd 1.0–4.3); `worldgen/lut.py`
    classifies, then **erases the map's own lettering and graticule** (ink
    classifies as the >7000 m swatch — measured 6003 m mean against 822 m for
    land overall — so without this every place name embossed into the heightmap
    as a mountain range) and inpaints from non-ink neighbours.
  - **Heightmap**: `map_data/heightmap.png`, 16384×7232 true 16-bit. The uint16
    encoding was **measured from vanilla** rather than invented: splitting the
    shipped heightmap on the real land/sea mask puts sea level at **4884** and
    the scale at **5.5 units/m** (which places Everest at 53548 against vanilla's
    observed max of 53469). TW3 relief is composited as *zero-mean* high-frequency
    detail on land only, so it sharpens ridges but cannot move a coastline.
  - **Coastline**: committed `tools/derived/land_sea_mask.png` — 27.85% land, 36
    land bodies, 11 water bodies. The mask is authored once at canvas resolution
    and forced onto the heightmap (nearest 2×, exact by construction), so the
    relief shoreline can never contradict the mask S3 cuts provinces from.
  - **Rivers**: `map_data/rivers.png` — **derived from the terrain**, not drawn.
    `worldgen/hydro.py` (priority-flood depression fill → D8 flow direction →
    flow accumulation → headwaters) yields the drainage network; 85,579 river px
    across ~1,300 branches, vanilla palette (measured exactly from the shipped
    file: 254=sea, 255=land, 0=source, 1=merge, 3–11 width ramp), 0 2×2 blocks.
    Mouths meet the coast **by construction** — the same land mask produced both.
  - **Toolchain rework**: `worldgen/ingest.py` holds the shared classify →
    reproject → clean → encode core that *both* the real generator and the
    fixture run (the generator does not live only in the test harness);
    `raster.py` gained 16-bit gray / 1-bit mask / indexed-palette IO;
    `composite.py` resolves layers by **per-layer** precedence (coastline vs
    relief — closing the S1 review's deferred item) and rejects precedence ties;
    `qa_overlay.py` renders the fidelity-QA overlays.
  - **Fixture**: `tools/fixtures/ingest/` — a synthetic whole-world source of our
    own pixels (so it is committed and runs on a clean clone) carrying every
    feature the real pipeline must survive: seam-crossing landmass, lake, island,
    label/graticule ink, speckle. Byte-exact goldens; plus composite and rivers
    self-checks in `run_fixture.py`.
- **Tests / gate (offline, all green)**:
  - `python tools/worldgen/sources.py --verify` — manifest SHA-256 + registration
    cross-checks pass.
  - `python tools/run_fixture.py --check` — determinism, goldens, validators, the
    new ingestion fixture, and the composite/rivers self-checks all pass.
  - **All three generators byte-deterministic**: re-running
    `generate_heightmap.py` / `generate_rivers.py` reproduces `heightmap.png`,
    `rivers.png`, and `land_sea_mask.png` byte-for-byte (independently confirmed
    by the security-review agent in fresh processes).
  - **Fidelity QA**: the Terraqueous overlay shows the generated coastline
    tracing every landmass, with the NE-II graticule resolving to a straight
    orthogonal grid — the visual confirmation that the projection is right.
- **⚠ Not yet done — the S2 game gate**: the in-game **map-editor heightmap
  repack** + boot to the main menu with a clean `error.log`. Click-by-click steps
  are in `tools/MAP_RUNBOOK.md` (§ S2). The map will *look* wrong at this gate
  (WH relief under vanilla provinces) — that is the intended de-risk, isolating
  the editor+boot loop before the S3 province overhaul.
- **Decisions taken during the build** (deviations from the plan, with cause):
  - **The satellite render was de-registered.** S1 gave it the "coarse global
    frame anchor" role; measured, it does not register — sweeping latitude
    half-span 60°–100° and longitude offset ±20° gave 63.9%–69.0% agreement with
    **no peak**, against a 60.0% chance level. A correct registration produces a
    sharp maximum. Its record was deleted rather than left committed-but-wrong
    (the exact class of silently-wrong data the SHA guard exists to prevent); the
    frame is now set by the 0.363 px NE-II fit. Its S1 crop was also wrong (the
    letterbox is left/right, not top). Documented in `tools/SOURCES.md`.
  - **Rivers are DEM-derived, superseding the plan's "traced from regional
    sources".** Tracing was attempted and failed on measurement: the Old World
    map's control-point warp is badly misregistered (visible in
    `qa_map-the-old-world.png`), the Terraqueous river lines segment into ≤25 px
    fragments, and the Empire map's rivers do not colour-separate. A first pass
    of hand-authored polylines was built, shipped, and then **rejected by the
    user as inadequate** — correctly; they were sparse and straight. Deriving the
    drainage from the heightmap is both better-looking and structurally sound.
  - **Canon river naming deferred to S6** (it already owned the naming pass). The
    user annotated the Empire map with canon courses in red; it is recorded as a
    **topology guide** (which channel is the Reik), not geometry, since the
    courses come from the DEM. Stroke extraction is solved and documented:
    difference the annotated map against the clean one, which isolates the
    strokes and cancels the coats of arms (bright red in both).
  - **`scipy`/`scikit-image` exact-pinned** (S1 review INFO item): the ingestion
    fixture's goldens are byte-exact and these libraries' float output can differ
    across versions.
- **Post-build agent review**:
  - *docs-updater* — updated `CLAUDE.md` (tools row, the now-false "only
    `.gitkeep`" claim, `map_data/` in the build+test loop, a non-negotiable
    against hand-editing generated bitmaps), `.claude/rules/testing.md` (the
    generators + the ingestion fixture), and `tools/fixtures/README.md`.
    Correctly left `docs/` and the scripting/loc rules alone — S2 adds no
    `common/`/`localization/` content.
  - *security-review* — **no MP-desync risk and no SHA-guard bypass**, verified
    empirically rather than by reading: two independent real-process runs
    reproduced the committed bitmaps exactly, and every `sources/` read goes
    through `load_source_image`. Two WARNING-level latent validator gaps, **both
    fixed in `8e2a371`**: (1) river vertices were not bounds-checked and
    out-of-canvas ones were silently clipped, letting a *discontiguous* path pass
    every check — now rejected at load, plus an 8-adjacency contiguity assertion;
    (2) the 2×2-block rule was a raw count that could not distinguish real
    junctions from a parallel run — now also gates on the longest contiguous run,
    with both limits **calibrated against vanilla** (21 blocks, longest run 5)
    after the first-cut limit was found to reject vanilla's own file.

### S3–S6 — pending

**S3** (provinces + states from the composited label mask) is the next `/build`,
and can start from the committed `land_sea_mask.png` without re-running ingestion.
S4 (scaffold + boot), S5 (terrain + visuals), S6 (regions + canon naming, now
including river identification from the annotated Empire map) follow.
