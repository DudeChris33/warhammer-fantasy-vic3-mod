# Project the Immortal Empires parchment's land and sea areas onto the Terraqueous globe

| Field | Value |
|-------|-------|
| Type | request |
| Status | superseded |
| Date | 2026-07-28 |
| Priority | high |

> **Superseded (2026-08-04) by
> [world-map-miller-projection-canvas.md](world-map-miller-projection-canvas.md).**
> Its Stage A/B work is built on the plate-carrée canvas and would have to be
> re-based onto the Miller frame. The traced-geometry code itself survives
> (committed in `72d797d`); the plan around it does not.

## Description

Take the drawn **land and sea areas** of
`sources/wh3_dlc_ie_parchment_map_english.jpg` — the Immortal Empires parchment
master, which is a full chloropleth: every land province *and* every sea is drawn
as a closed cell and printed with its name — and project them, through the
committed registration machinery, onto the geometry of
`sources/terraqueous_globe.jpg`.

Two things come out of it:

1. **A local-only review render** — a copy of `terraqueous_globe.jpg` in its own
   4000×3256 pixel space, with the projected cell outlines and names drawn on it,
   for the user to eyeball and mark up. This is the review gate.
2. **Committed vector data** — the projected cells as named polygons/anchors on
   the canvas, which then *become the state cells* (user decision, this session),
   superseding `total_war_map_colored.png` as the primary boundary network, and
   whose sea cells become named sea-zone footprints.

The purpose is pre-emptive: it attacks the **states problems** the S3a-2 review
panel blocked on, at the source layer, rather than patching them downstream.

## Context

### Why this is being asked for now

The [S3a-2 plan](world-map-source-driven.md#plan--s3a-2-named-region-binding--per-region-density-2026-07-26)
was **BLOCKed unanimously** by the review panel on 2026-07-28. Reading the
blocking findings, most of them are symptoms of one root cause: *the pipeline has
geometry with no names, so names have to be reattached by inference*.

| Panel finding | What a named chloropleth does to it |
|---|---|
| 33.4% of land unclaimed by any named region; catch-all is ~220 of 660 states of invented filler | The parchment names its whole frame; the globe's own printed names cover the rest. The catch-all should approach zero. |
| Six of eleven forced single states have no anchor source, and inventing one violates a `CLAUDE.md` non-negotiable | The parchment *draws and names* them. **All 11 confirmed this session** — see the forced-state table below. The blocker is dissolved, not mitigated. |
| Sub-region quotas (Estalia ≥5, Tilea ≥4, Border Princes ≥6) have no footprint to count inside | Verified visually: **Estalia**, **Tilea**, **Western Border Princes**, **Eastern Border Princes**, **The Vaults** are all printed labels over multi-cell areas — exactly the sub-region footprints the quotas need. |
| Five of 17 macros are each claimed by 2–3 named regions, so per-region quotas cannot be enforced | Names come from the same artwork as the geometry, so there is no macro/name mismatch to reconcile. |
| The 108 sea cells are synthetic Lloyd-relaxed seats (`tools/worldgen/cells.py:460`) with no names | The parchment draws and names them: Sea of Dread, Lizard Sea, Sea of Storms, Straits of Nagash, The Bitter Sea, Tilean Sea, Kraken Sea, Northern Sea of Chaos, … |

It does **not** fix the two mask-level blockers (polar fringe, corner splinters) —
see Out of scope.

### What the parchment actually contains (inspected this session)

- **3703×2880**, full IE campaign frame. Land cells at roughly Victoria 3 state
  granularity — a crop over Bretonnia/Tilea shows Bastonne, Carcassonne, Forest of
  Chalons, Talsyn, The Vaults, Wissenland, Solland, Averland, Black Mountains,
  Blood River Valley, Western Badlands, each an ink-bounded closed cell.
- **Sea is a chloropleth too** — thin drawn lines over the dark water wash divide
  it into named seas, confirmed on a crop of the Sea of Dread / Lizard Sea / Sea
  of Storms / Straits of Nagash cluster.
- **Label granularity varies and is not one-per-cell.** "Reikland" names one cell;
  "Tilea" and "Estalia" name a multi-cell area. That is a feature, not a problem —
  it is precisely the two-level (region / sub-region) binding S3a-2 needs. But the
  build must not assume every cell gets a name.
- **A printed name is often not the name the requirement uses.** The parchment
  labels **provinces, not settlements**, so canonical place names and printed
  names diverge exactly where the requirements are most specific — see the forced
  -state table below. Two consequences for the build: the names file needs an
  **alias field**, and the transcription must be reviewed by someone who knows the
  setting, because a requirement can be silently missed by a transcription that is
  perfectly accurate.
- **The typeface renders U as V** — "Yn Edri Eternos" reads as "Vn Edri Eternos"
  at a glance. Transcription must normalise this deliberately rather than
  per-label, and the reviewed names file is where it gets caught.
- **Text crosses boundaries**, which is the known failure mode (11 of 17 contours
  on a first pass, per the S3a-2 handoff) and needs handling, not hoping.
- Its **northern polar band is fully provinced land** — Ironfrost Glacier, The
  Frigid Wasteland, The Road of Skulls, Deadwood, The Shard Lands, Northern
  Wastes, The Cold Mires, The Eternal Lagoon, Bloodfire Falls — and its southern
  edge likewise (The Southern Wastes, The Abyssal Glacier, The Daemonium Hills,
  The Ice-Fire Plains). See the coastline constraint below for why that does *not*
  automatically become land.

### The eleven forced single states, checked against the artwork

The S3a-2 review blocked because six of these had no anchor source. Inspecting
the parchment directly, with the user's pointers (2026-07-28):

| Required state | Printed on the parchment as | Status |
|---|---|---|
| Albion | Albion | ✅ own cell |
| Laurelorn Forest | Laurelorn Forest | ✅ own cell |
| Middle Mountains | The Middle Mountains | ✅ own cell |
| The Moot | **Mootland** | ✅ own cell (alias) |
| Oak of Ages | **Yn Edri Eternos** | ✅ own cell (alias) |
| Great Bastion ×3 | **Western Great Bastion**, **Central Great Bastion**, **Eastern Great Bastion** | ✅ three own cells, north of "Lands of Stone and Steel" |
| Massif Orcal | **Barrows of Cuileux** | ✅ own cell (alias) |
| Skavenblight | **The Blighted Marshes** | ✅ own cell (alias) |
| Sartosa | **Pirate's Current** | ✅ own cell (alias) |

**All eleven have a printed anchor. None has to be invented** — the panel's
fifth blocking finding is dissolved rather than mitigated.

Six of the eleven are aliases, which is why that field is load-bearing rather
than a convenience: nothing in the imagery would lead a transcription pass —
machine or otherwise — from "Sartosa" to "Pirate's Current". Only setting
knowledge does, which makes the reviewed names file the authority and the user
its reviewer.

Two things the build must measure rather than assume:

- **Each of these labels must resolve to exactly one cell.** A forced *single*
  state requires it, and a label printed over a multi-cell area (the way "Tilea"
  and "Estalia" are) would mean that requirement needs a sub-cell anchor instead.
  Report the cell count under every forced-state label; anything other than 1 is a
  finding.
- **The three Bastion cells are markedly smaller than the mean state** — thin
  strips along the wall. That is the concrete instance of the open question the
  S3a-2 handoff raised ("how a forced single state survives the merge/split
  passes without distorting its neighbours"): here the risk is not distortion but
  *erasure* by the merge pass.

Adjacent, and free: the parchment draws the wood-elf realms **Argwylon**,
**Torgovann**, **Wydrioth** and **Talsyn** as their own cells around Yn Edri
Eternos, so `athel_loren`'s `min_states: 5` is satisfied by drawn, named
geometry rather than by quota allocation.

### What the globe contains that the parchment does not

The IE frame is not the world. Areas the globe draws and names but the parchment
never reaches: **NIPPON, KINGDOMS OF IND, KINGDOMS OF KURESH, LUMBRIA
ARCHIPELAGO, EMERALD MEADOWS, HUNG LANDS, GREAT EASTERN STEPPES, HOLLOW HEIGHTS,
WYRD JUNGLES, TEMPEST LAND, LOST ISLES OF ELITHIS**, and the seas **FAR OCEAN,
OCEAN OF DREAD, SEA OF SQUALLS, SEA OF WRATH, SEA OF RAGE, JADE SEA**. Those
printed globe labels fill the gap (user decision), so nothing outside the IE frame
has to be invented either.

### Registration state — the master has a seed but no fitted record

`tools/registration/seeds/wh3_dlc_ie_parchment_map_english.json` is authored and
complete (silhouette objective borrowed from the climate map at
`to_master_scale [1.4985835, 1.4984391]`, a 10×8 lattice thin-plate warp, 12
hand-identified landmark pairs held out as an independent check, `role:
ie_boundary_frame_master`, `layer_precedence {boundaries: 40, coastline: 5,
relief: 5}`), but **`tools/fit_registration.py --seed
wh3_dlc_ie_parchment_map_english` has never been run** — there is no
`tools/registration/wh3_dlc_ie_parchment_map_english.json`. Today the master is
referenced only as `MACRO_CLEAN_MASTER` (`tools/generate_state_labels.py:123`),
for *differencing* against its annotated twin, a role explicitly documented as
needing no registration. Fitting it is step one of this request.

Note also that `Immortal-Empires-Map-Feature-Image-scaled.jpg` — the currently
registered IE boundary source — is a **16:9 crop, `y[224..2296]` of 2880**, so it
excludes both polar bands. The master and its pixel-identical twin
`pizqenw9rd791.jpg` are the only whole-frame members of the family.

## Acceptance Criteria

**Registration**

- [ ] `tools/registration/wh3_dlc_ie_parchment_map_english.json` is committed,
      produced by `python tools/fit_registration.py --seed
      wh3_dlc_ie_parchment_map_english` and never hand-edited.
- [ ] The fit reports both its silhouette IoU against `land_sea_mask.png` and its
      held-out `landmark_check_px`, and both are recorded in `tools/SOURCES.md`.
      The fit is only accepted if the landmark check is comparable to the family's
      existing records; a worse fit is reported, not silently adopted.

**Cell extraction**

- [ ] The parchment's land cells are traced across the whole frame and the count
      is reported. Expectation to *measure*, not assume: the TW3 reference in
      `tools/regions/named_regions.json` totals 554 states across 17 regions, and
      the target band is 600–700 land states.
- [ ] The parchment's **sea** cells are traced as their own network (they sit on
      the dark water wash, not the paper, so they need their own threshold path)
      and the count is reported.
- [ ] Label text crossing a boundary does not break the enclosing loop: detected
      text regions are masked out of the ink layer before contours are closed.
      The number of cells recovered **before and after** text masking is reported
      — this is the measurement that says whether the detector earned its
      dependency — and any region where the loop still fails is listed rather
      than filled in.
- [ ] ≥95% of the IE footprint's mask-land is covered by a traced land cell; the
      shortfall is reported per named region.

**Coastline — the globe still wins everywhere (user decision, this session)**

- [ ] Every projected cell is intersected with the committed
      `tools/derived/land_sea_mask.png`. Asserted and reported: **0 px** of
      mask-sea becomes a land state, **0 px** of mask-land becomes a sea zone.
- [ ] The parchment's polar provinces therefore clip to (near) nothing while
      [chaos-wastes-polar-fringe-misclassified.md](../issues/chaos-wastes-polar-fringe-misclassified.md)
      is open. That is expected; the build reports how many named cells were lost
      to clipping and where, and does **not** work around it.

**Names**

- [ ] Every printed label on the parchment is transcribed into a committed,
      human-readable names file with, per entry: the name as printed, `kind`
      (`land` | `sea`), a source-pixel anchor, and a confidence/`needs_review`
      flag. Low-confidence reads are surfaced as a list for the user, never
      guessed.
- [ ] The globe's own printed labels for the areas outside the IE frame are
      transcribed the same way, into the same schema, tagged by source.
- [ ] Transcription is an **authoring action** (like `--update-manifest` and
      `fit_registration.py`), never part of the offline gate. The gate reads the
      committed file; it never re-reads the imagery.
- [ ] The names file has a Python schema loader under `tools/` and is validated by
      it — the panel's standing complaint that `tools/regions/named_regions.json`
      has no loader must not be repeated for a file three times its size.
- [ ] **Zero invented names.** Any cell with no label over it is recorded as
      unnamed in a committed audit list.
- [ ] The names file carries an **alias** field, so a requirement written against
      a canon name resolves to the cell printed under a different one — the known
      cases being Oak of Ages → "Yn Edri Eternos", The Moot → "Mootland", Massif
      Orcal → "Barrows of Cuileux", Skavenblight → "The Blighted Marshes" and
      Sartosa → "Pirate's Current". All eleven aliases are recorded in the names
      file up front, and each forced state is reported as *matched to a printed
      label (via which alias)* with **the number of cells under it** — anything
      other than 1 is a finding for the user, never a licence to place an anchor
      by hand.
- [ ] A forced single state **survives density reconciliation**: exempt from the
      merge pass, never absorbed into a neighbour, never split. The three Great
      Bastion cells are the test case, being thin strips well below the mean state
      area, and each forced state's final area and cell count is reported.

**Binding and density**

- [ ] Each name binds to the cell(s) its anchor falls in. Two-level binding is
      explicit: a label over one cell names a state; a label spanning several
      names a sub-region/region containing them.
- [ ] The share of land belonging to no named region is reported, against the
      current **33.4%** baseline.
- [ ] Named sea areas become the sea-zone footprints inside the IE footprint,
      replacing the synthetic seats from `tools/worldgen/cells.py:460` there;
      outside it, globe sea names or the existing fallback. Every named sea area
      has ≥1 zone, and the total is reported against `TARGET_SEA_ZONES`.

**Artifacts and gate**

- [ ] A **local-only** composite render exists: a copy of `terraqueous_globe.jpg`
      at full 4000×3256 with projected cell outlines and names drawn on. It is
      gitignored, and it is **sent to the user** — the user's visual approval is
      the gate for this milestone — every offline check was green the last time
      the map was visually unusable, so no green gate substitutes for it.
- [ ] A **committed** render drawn from our own pixels only (no source art):
      flat-coloured cells plus names, at a resolution where the smallest cells and
      their labels are legible. `tools/qa_overlay.py` is `STEP = 8` → 1024×452 with
      a 14×14 px mean state and **no text facility at all**; at that scale the
      deliverable is not reviewable, so this needs either a higher-resolution
      render or a zoom-tile set, plus text rendering.
- [ ] `python tools/worldgen/sources.py --verify`, `python tools/validate_map.py
      --labels` and `python tools/run_fixture.py --check` all pass.
- [ ] New fixtures cover the added paths — sea-cell extraction, text-crossing
      handling, name→cell binding — under `tools/fixtures/`, against synthetic
      inputs, so none of it is eyeballed.
- [ ] Re-running the generators produces **byte-identical** output.
- [ ] `tools/SOURCES.md`, `tools/PROVENANCE.md` and `tools/derived/COVERAGE.md`
      updated: the parchment master gains a registration and a promoted role,
      `total_war_map_colored.png` is demoted from primary boundary network, and
      the per-region tracing log gains a row.

## Investigation

- **What exists**:
  - `tools/registration/seeds/wh3_dlc_ie_parchment_map_english.json` — complete,
    unfitted seed for the master (silhouette objective, lattice, 12 landmarks).
  - `tools/fit_registration.py` — `--seed <stem>` fits and writes
    `tools/registration/<source>.json`; `--dry-run` fits and reports only.
  - `tools/worldgen/parchment.py:*` — `ink_mask()` (local-contrast threshold) and
    `cells_from_ink()` already do exactly the land-cell tracing this needs;
    `flat_map_cells()` is the flat-fill path used for `total_war_map_colored.png`.
  - `tools/worldgen/cells.py` — `warp_cells()`, `stack_layers()`, mask
    intersection, nearest-label fill, `prune_slivers()`, `sea_zones()` (the
    synthetic seats to be replaced inside the IE footprint).
  - `tools/generate_state_labels.py:109-112` — `BOUNDARY_SOURCES`, deliberately an
    explicit dict so adding a source is a deliberate edit; `:123`
    `MACRO_CLEAN_MASTER` already names the parchment master for differencing.
  - `tools/worldgen/reproject.py` — the NE-II fit (0.363 px RMS). It maps
    canvas → globe source pixels in the forward direction, which is exactly what
    the globe-space composite needs; **no inverse has to be derived**.
  - `tools/regions/named_regions.json` — the 17 macro regions with `min_states`
    and the pending forced-state / sub-region requirements. This request's names
    file supersedes most of its `_comment_pending` section.
  - `tools/derived/state_labels_index.json` — current state: 613 land + 108 sea
    cells, `target_land_states 659`, `target_sea_zones 103`, `target_area 12517`.

- **What changes**:
  - `tools/registration/wh3_dlc_ie_parchment_map_english.json` — **new**
    (machine-fitted).
  - `tools/registration/seeds/wh3_dlc_ie_parchment_map_english.json` — likely
    edited: the seed declares `boundaries: 40`, which must be raised above
    `total_war_map_colored.png`'s 95 for the parchment cells to *be* the states.
  - A new names file under `tools/regions/` (e.g. `parchment_areas.json`) plus a
    schema loader/validator under `tools/worldgen/`.
  - `tools/requirements-authoring.txt` — **new**: the text-detector dependency,
    deliberately outside the gated exact-pin set in `tools/requirements.txt`.
  - `tools/worldgen/parchment.py` — a sea-cell extraction path, and text-crossing
    handling.
  - `tools/worldgen/cells.py` — named sea-zone footprints replacing synthetic
    seats inside the IE footprint.
  - `tools/generate_state_labels.py` — `BOUNDARY_SOURCES` gains the master;
    name→cell binding; reporting.
  - A new render script (globe-space composite, local-only output) and text
    rendering for the committed neutral render.
  - `tools/derived/state_labels.png`, `state_labels_index.json`, `COVERAGE.md` —
    regenerated, never hand-edited.
  - `tools/SOURCES.md`, `tools/PROVENANCE.md`, `tools/MAP_RUNBOOK.md`,
    `.claude/rules/testing.md` if the gate commands change.
  - `planning/requests/world-map-source-driven.md` — this supersedes part of the
    S3a-2 plan and must say so.

- **Constraints**:
  - **The globe owns every coastline, no exceptions** (user decision, this
    session; standing decision #1, 2026-07-25). The parchment contributes interior
    area boundaries and names only. This is what makes a rubber-sheeted
    registration acceptable — local scale error moves a border a few px inside a
    landmass and cannot put a coast in the sea.
  - **Sequencing.** With the globe winning everywhere, the parchment's polar
    provinces have no geometry to land on until
    [chaos-wastes-polar-fringe-misclassified.md](../issues/chaos-wastes-polar-fringe-misclassified.md)
    is fixed — and that fix **rewrites the mask every cell here is clipped
    against**. The review panel already ruled *fix the mask first* for S3a-2 for
    exactly this reason. Doing this request first is defensible (the IE arc is
    99% of the value and the clipping is reported, not hidden), but the plan must
    take the call explicitly rather than inherit it.
  - **No committed source art.** `tools/PROVENANCE.md`: only our own derived
    pixels are committed, `sources/` is gitignored. The globe-backed composite is
    therefore local-only; the committed render must be drawn from our own pixels.
  - **OCR: split detection from reading.** The user has authorised new
    dependencies (2026-07-28), which changes the shape of this step but not the
    conclusion about reading. Classical OCR will not transcribe this artwork
    well — curved baselines ("Lizard Sea" arcs), vertical text ("The Dragon
    Isles"), a decorative serif that renders U as V, all over parchment texture
    and frequently overlapping the very boundary lines being traced. What an
    engine *is* good at is **detection**: locating text regions with oriented
    bounding boxes. So:
    - **Detection → a dependency.** Detected text boxes serve two jobs at once:
      they bound what gets read, and they give the **text mask** the cell tracer
      needs in order to erase labels before closing contours. That is the direct
      fix for the known 11-of-17 first-pass failure mode, and it is worth the
      dependency on its own even if not one character is transcribed.
    - **Reading → vision, per detected box.** Best accuracy on this typeface and
      these baselines, and the reader is also the one who recognises that "Yn
      Edri Eternos" is the Oak of Ages.
    - **The engine's own transcription is kept as a cross-check**, not discarded:
      where engine and reading disagree, the entry is flagged `needs_review`
      rather than silently resolved. Two independent reads is cheap here and is
      the only automatic error signal available.
  - **Keep the new dependency out of the gated pin set.** `tools/requirements.txt`
    is exact-pinned (numpy 2.2.6, Pillow 12.3.0, scipy 1.15.3, scikit-image
    0.25.2, Python 3.10.7) so `run_fixture.py --check` is byte-reproducible on a
    clean clone. A detector — especially a torch-backed one (EasyOCR/CRAFT, docTR,
    PaddleOCR) — is neither small nor bit-deterministic, and nothing in the gate
    should depend on it. It belongs in a separate authoring-only requirements file
    (e.g. `tools/requirements-authoring.txt`), used by the transcription command
    and by nothing else. This is consistent with how `--update-manifest` and
    `fit_registration.py` are already treated: authoring actions whose *outputs*
    are committed and reviewed, and which the gate never re-runs.
    `tesseract` is not currently on PATH; if the chosen detector is
    tesseract-based, its native binary must be documented in
    `tools/MAP_RUNBOOK.md` as a local install step, since it cannot be pinned the
    way the Python stack is.
  - **Determinism / MP**: nothing here is loaded by Victoria 3 — every output
    lives under `tools/`, and no `docs/*.log`-governed surface is touched. MP
    desync is not reachable from `tools/`; the property at stake is **generator
    byte-reproducibility**. Watch the two known ordering risks: region iteration
    order, and tie-breaks in seeded fills.
  - **Unresolved, inherited, not in scope to fix here**: the panel measured
    vanilla at **675 land + 106 sea** state blocks against the hardcoded
    `TARGET_LAND_STATES = 659` / `TARGET_SEA_ZONES = 103`
    (`tools/generate_state_labels.py:67-68`), and **36** vanilla land strategic
    regions against the "47" recorded in the plan. Flag it; don't silently
    re-target on the way past.

- **Related files**: `sources/wh3_dlc_ie_parchment_map_english.jpg`,
  `sources/terraqueous_globe.jpg`, `sources/pizqenw9rd791.jpg`,
  `sources/3274025515_preview_WH3 climate map 6.0.3.jpg`,
  `sources/Immortal-Empires-Map-Feature-Image-scaled.jpg`,
  `sources/total_war_states_per_strat_region.jpg` (all local-only, hash-pinned in
  `tools/SOURCES.md`); `tools/derived/land_sea_mask.png` (the coastline);
  `planning/issues/chaos-wastes-polar-fringe-misclassified.md`;
  `planning/requests/world-map-source-driven.md`;
  `planning/requests/s3a2-review-panel-handoff.md`.

- **Endpoints/commands**:
  - `python tools/fit_registration.py --seed wh3_dlc_ie_parchment_map_english`
    (authoring)
  - a new authoring command for text **detection** (oriented boxes + the text
    mask the tracer consumes) and one for the names file (transcription in,
    validated committed JSON out) — both named and documented, not implicit, and
    both outside the gate
  - a new render command producing the local-only globe composite
  - `python tools/generate_state_labels.py` (regeneration)
  - gate, unchanged: `python tools/worldgen/sources.py --verify`, `python
    tools/validate_map.py --labels`, `python tools/run_fixture.py --check`

- **Tests required**: fixtures under `tools/fixtures/` for sea-cell extraction on
  a dark wash, a label crossing a cell boundary, name→cell anchor binding
  (including a label spanning multiple cells), mask intersection asserting the
  zero-crossover property, and byte-identical regeneration. Plus the two visual
  gates: the local-only globe composite sent to the user, and the committed
  neutral render.

- **Out of scope**:
  - Fixing the polar fringe or the corner splinters — both live in the mask, and
    both are their own work
    ([chaos-wastes-polar-fringe-misclassified.md](../issues/chaos-wastes-polar-fringe-misclassified.md)
    and the cartographer's S3a-2 finding).
  - S3b: `provinces.png`, `adjacencies.csv`, `default.map`, state region `.txt`.
  - Navigable rivers (Ruin, Reik, Talabec, Stir, Lynsk, Cathay's) and their strait
    crossings — S3b/S6.
  - Emitting any `.yml` localization, `common/` script or `map_data/` text.
  - Re-targeting `TARGET_LAND_STATES` / `TARGET_SEA_ZONES` (flag only).
  - Loading the mod in-game — nothing here is read by Victoria 3.

- **Localization needed**: **none in this milestone.** It produces no
  user-facing text and writes no `.yml`. What it does produce is the *name
  inventory* — ~500+ canon land and sea names with geometry bound to them — that
  the S6 naming pass turns into `localization/english/` entries and
  `STATE_<REGION>_NNNN` state-region blocks. Worth recording now, per the panel:
  the state-region block name **is** the loc key, so pinning a stable numeric
  `id` alongside each name in the index would make S6's rename a single-file edit
  instead of a multi-file atomic one.

## Plan

### Objective

Register the Immortal Empires parchment master, trace its interior area network
with the lettering *bridged* rather than erased, project it onto the committed
canvas, and bind the map's own printed names to the resulting cells — so the
state layer is drawn-and-named geometry instead of anonymous contours plus
inferred labels.

### Measurements taken while planning (2026-07-28)

Everything below is measured on `sources/wh3_dlc_ie_parchment_map_english.jpg`
(3703×2880) through the committed `worldgen.parchment` primitives. Three of them
**correct the request** and change the design; they are stated here so the build
starts from the evidence rather than re-deriving it.

| # | Measurement | Consequence |
|---|---|---|
| 1 | Naive `ink_mask(41,12)` → `cells_from_ink(150)`: **1143 cells**, only **619 ≥1000 px**, median 1281 px, largest **854,893 px** | The naive path is not usable as-is. The largest cell is the headline defect. |
| 2 | Ink separates cleanly by shape: the whole line network is **4 connected components holding 1.19M of 1.68M ink px**, against **3854 compact blobs** (292k px) at a clear **9–16 px** glyph height | Glyph detection needs no OCR engine. Confirms the classical path. |
| 3 | Bridging glyph blobs into the barrier (close 7×21, dilate 3×3): cells ≥1000 px **619 → 906 (+46%)**, ≥2000 px **482 → 629** | **The request has the operation backwards.** See "Text is bridged, not erased". |
| 4 | Threshold sweep with bridging: `offset=12` → 885 cells ≥1000 px, max blob 852k; `offset=9` → **915**, max **818k**; `offset=7` → 920, max 765k (at 26.5% ink) | Adopt `offset=9`. Beyond that the ink cost rises faster than the recovery. |
| 5 | Morphological **closing** of the barrier makes it *worse*: max blob 852k → **2.19M** at close3 | Closing is measured and rejected. Do not retry it. |
| 6 | Visual inspection of four ocean crops (`(150,1400)-(1150,2100)`, `(1900,150)-(2900,850)`, `(900,2100)-(1900,2800)`, plus a native-scale patch at `(700,1600)-(1000,1900)`): open water is **bare parchment with no drawn rule**. What reads as a sea network at reduced scale is coastline shore-wash. A handful of faint rules do exist (e.g. across the Southern Straits) | **The sea is not a chloropleth.** See "Sea names are seeds, not footprints". |
| 7 | Faint-ink + length-filter extraction over the ocean: `offset=4` marks 20.1% of open water and still leaves a **686,742 px** undivided cell | Sea-cell tracing is measured and rejected as a requirement. |
| 8 | `tools/registration/ie_macro_twin.json` carries **80 control points in master-pixel space** (x 74–3629, y 510–2832). Its seed is still `objective: frame_alias` of the master; its notes say it was "BAKED STANDALONE (2026-07-25)" only because the master had been removed from `sources/`. Same for `ie_feature_image`. The master is back in `sources/` | The master's placement already exists. See step 2. |
| 9 | The twin's control points start at master **y 510** — the parchment's northern polar band lies **outside the control-point hull** | The polar provinces are lost twice over: extrapolated warp *and* mask clipping. Report, do not work around. |
| 10 | `PIL.ImageFont.load_default(size=N)` returns a bundled scalable FreeType face (no external font file) under the pinned Pillow 12.3.0 | Text rendering needs no new dependency and stays byte-reproducible. |

#### Text is bridged, not erased

The request's acceptance criterion says "detected text regions are **masked out**
of the ink layer before contours are closed". That cannot be right, and
measurement 3 shows why. `cells_from_ink` labels the *complement* of ink, so
adding ink can only ever cut the complement into **more** pieces — text can never
merge two cells by being present. What actually merges them is that the
cartographer **interrupts the ruled border to make room for the label**, leaving a
physical gap that the complement leaks through between the letters. Erasing the
text widens that leak. Filling the detected label region into the barrier bridges
it, and the bridge is then handed back to the neighbours by `cells.fill_nearest`
— converting an unrecoverable *merge* into a recoverable *border a few px off*,
exactly the trade `cells_from_ink`'s own docstring argues for.

#### Sea names are seeds, not footprints

Measurements 6 and 7 retire the "sea chloropleth" premise. The parchment names
large stretches of open water (`The Great Ocean`, `Sea of Serpents`, `The
Southern Straits`, `Middle Sea`, `Straits of Lothern`, `Shark Straits`, …) but
draws almost no dividing rules, and the few it draws carve the ocean into a
handful of very large seas — nowhere near the ~103 sea zones the target wants.
So a sea name becomes a **seat**: its anchor replaces one of
`cells._farthest_seeds`' synthetic seats inside the IE footprint, and
`cells.sea_zones` partitions around it as it already does. Every named sea then
has ≥1 zone **by construction** rather than by a fragile extraction, and the
acceptance criterion is met more strongly than tracing would meet it. Seats
beyond the named ones stay synthetic, so `TARGET_SEA_ZONES` is still reachable.

#### Design decisions taken with the user (2026-07-28)

1. **Text detection: classical, no new dependency.** Glyph-shaped ink components
   grouped into label blobs, cross-checked against an independent signal — the
   master differenced against the already-registered de-lettered
   `Immortal-Empires-Map-Feature-Image-scaled.jpg`, the same technique
   `worldgen/macro.py` already uses on the annotated twin. Reading stays a vision
   pass per box. **`tools/requirements-authoring.txt` is not created**; nothing is
   added to `tools/requirements.txt`.
2. **Registration: fit the master, then re-alias the family.** Restores the
   topology the seeds and `SOURCES.md` still describe.
3. **Two build stages with a render gate between them.** Stage A is geometry and
   renders with cells **unnamed**; Stage B is the transcription and binding.
4. **Committed render: per-macro-region zoom tiles** plus one whole-world index
   sheet, drawn from our own pixels only.

#### Sequencing against the polar-fringe fix — the call

`chaos-wastes-polar-fringe-misclassified.md` stays open and this work proceeds
**now**, deliberately, contradicting the S3a-2 panel's "fix the mask first"
ruling for this request only. Three reasons the panel could not weigh:

- The expensive deliverable is the **names file**, whose anchors are stored in
  *source* pixels. It is completely independent of `land_sea_mask.png` and
  survives the mask fix untouched.
- The polar band is already lost for a second, independent reason (measurement
  9): it sits outside the control-point hull, so fixing the mask alone would not
  recover it. Both fixes are needed and neither blocks the other.
- Every land cell outside the two polar bands — 99% of the IE arc's value — is
  unaffected by the mask fix, because that fix only moves the polar coastline.

What the build owes in exchange: it **reports** how many named cells clip to
nothing and where, per named region, and does not work around it.

### Steps (ordered)

#### Stage A — registration, geometry, renders (cells unnamed)

1. **`tools/registration/seeds/wh3_dlc_ie_parchment_map_english.json`** — raise
   `record.layer_precedence.boundaries` **40 → 100**, above
   `total_war_map_colored.png`'s 95, so the parchment cells *are* the states
   (user decision). Amend `record.notes` to state the promoted role and that the
   three siblings alias back to it. Leave the silhouette/coarse/lattice/landmark
   blocks untouched — they are authored and complete.

2. **Fit the master.** `python tools/fit_registration.py --seed
   wh3_dlc_ie_parchment_map_english` → new
   `tools/registration/wh3_dlc_ie_parchment_map_english.json`. Then, **before
   adopting it**, report three numbers side by side:
   - `refined_iou`, `folded_fraction`, `anisotropy_p99` from the fit's own
     `FIT:` block;
   - `landmark_check_px` (mean/max) against the family's existing record —
     `total_war_map_colored.json` sits at mean **312.2**, max **844.6**;
   - the **displacement against the twin's current placement**: evaluate the new
     master warp at `ie_macro_twin.json`'s 80 control-point source positions and
     report the mean/p90/max canvas distance from their committed canvas
     positions.

   If the landmark check is materially worse than the family's records, **stop
   and report** — do not adopt. This is the acceptance criterion's "a worse fit is
   reported, not silently adopted".

3. **Re-alias the family onto the master.** Their seeds are already
   `objective: frame_alias` pointing at the master, so this is three re-runs plus
   one one-line seed edit:
   - `python tools/fit_registration.py --seed ie_macro_twin` (identity alias)
   - `python tools/fit_registration.py --seed ie_feature_image` (scale
     1.4390625/1.4388889, offset 8/224)
   - **`tools/registration/seeds/ie_named_regions.json`** — repoint
     `frame_alias.of` from `pizqenw9rd791.jpg` to
     `wh3_dlc_ie_parchment_map_english.jpg`. Scale and offset are **unchanged**,
     because the twin→master alias is the identity; update the `_comment` to say
     so. This is required, not cosmetic: `sources.verify` rejects an alias whose
     parent is itself an alias (`tools/worldgen/sources.py:207-219`).
   - `python tools/fit_registration.py --seed ie_named_regions`

   Result: parchment cells, parchment names, macro contours and the 17 region
   names all resolve through **one** warp.

4. **`tools/worldgen/parchment.py`** — three new source-pixel primitives, matching
   the module's existing "pure function of pixels plus committed constants"
   contract:
   - `glyph_mask(ink)` → ink components that are glyph-shaped. Committed
     constants from measurement 2: `GLYPH_MIN_AREA = 20`, `GLYPH_MAX_SIDE = 60`,
     `GLYPH_MIN_HEIGHT = 6`, `GLYPH_MIN_FILL = 0.15`.
   - `label_blobs(glyphs)` → an `int32` label image, one id per detected label
     region, by anisotropic closing (`LABEL_CLOSE = (7, 21)` — wide, because
     letter spacing is horizontal) plus a 3×3 dilation. Returns the labelled
     image so Stage B gets bbox, centroid and pixel footprint per blob for free.
   - `INK_OFFSET_MASTER = 9` as a named constant, with the measurement-4 sweep
     recorded in the module docstring so the value is evidence, not taste.

   Explicitly **not** added: a morphological closing of the barrier
   (measurement 5), and a faint-ink sea network (measurements 6–7). Both are
   recorded as measured-and-rejected in the docstring so they are not retried.

5. **`tools/generate_state_labels.py`** — consume the master:
   - `BOUNDARY_SOURCES` gains `"wh3_dlc_ie_parchment_map_english.jpg":
     "ink_bridged"` and **drops** `"Immortal-Empires-Map-Feature-Image-scaled.jpg"`.
     The feature image is the same artwork at lower resolution behind a 16:9 crop;
     with the master at precedence 100 covering a superset of its footprint,
     `stack_layers` would suppress it everywhere, so keeping it in the dict costs
     a full warp for zero contribution. Its **registration record stays** — Stage
     B uses it as the independent text-mask cross-check. `total_war_map_colored.png`
     stays at 95, demoted from primary to complement: it now wins only outside the
     master's coverage.
   - New `extract_source_cells` branch `ink_bridged`: `ink_mask(offset=9)` →
     `glyph_mask` → `label_blobs` → barrier = `ink | blobs` → `cells_from_ink`.
     It logs cells **before and after** bridging — the measurement the acceptance
     criterion demands.
   - New headline metrics into `stats`, all of which COVERAGE.md reports:
     `traced_cells_before_bridge`, `traced_cells_after_bridge`,
     `largest_traced_cell_px`, IE-footprint land coverage %, and — the number
     nobody currently reports — **the share of final land area whose borders came
     from `split_large` rather than from a traced line**, i.e. how much of this
     map is drawn versus tessellated.

6. **`tools/render_named_map.py`** — new, the two review artifacts:
   - `--globe` → **local-only**. `terraqueous_globe.jpg` at its native 4000×3256
     with projected cell outlines drawn on. The mapping is forward and already
     committed: `reproject.fit_parametric(regs["terraqueous_globe.jpg"])` then
     `.to_canvas(gx, gy, 8192, 3616)` per globe pixel → sample
     `state_labels.png` nearest → outline where the sampled label differs from a
     neighbour. No inverse has to be derived. Output lands in `tools/derived/`,
     which `tools/.gitignore:21` already excludes by default — no gitignore change
     needed, and the file must **not** be added to the negation list.
   - `--tiles` → **committed**, drawn from our own pixels only. One PNG per macro
     region at its canvas bounding box, long side capped at 2400 px and
     nearest-upscaled if the region is smaller, so a small region stays legible;
     plus `index.png`, one whole-world sheet at STEP 2. Flat macro-tinted cells,
     1 px outlines, coastline at 1 canvas px (not the STEP-8 magenta rim the
     cartographer measured eating a quarter of each coastal state). Text via
     `ImageFont.load_default(size=)`. Written to `tools/derived/named/`.
   - **`tools/.gitignore`** — add `!derived/named/` and `!derived/named/*.png`
     to the existing negation block, with a comment naming them as the S3a-2
     review deliverable.

7. **`tools/fixtures/boundary/`** — extend the synthetic parchment
   (`make_source.py`) with two authored features and re-bake the golden:
   - a ruled border **interrupted by a run of glyph-shaped blobs**, so the fixture
     fails if bridging regresses. Assert `cells_after > cells_before` and that the
     specific bridged cell is closed.
   - a label region **spanning two cells**, so Stage B's binding has a fixture to
     land on.

   `build_boundary` calls the same `parchment`/`cells` functions the real run
   does, so this rides the existing determinism + golden + `--labels` lint
   harness (`tools/run_fixture.py:563-732`) with no new machinery.

8. **Docs (Stage A).**
   - `tools/SOURCES.md` — master row: `Registered` `no` → `yes`, role rewritten
     from "clean counterpart for macro grouping only" to the primary boundary and
     name source; `total_war_map_colored.png` role demoted from **PRIMARY
     BOUNDARY SOURCE**; feature-image role restated as text-mask cross-check;
     record the fit's IoU and `landmark_check_px` per the acceptance criterion.
     Do **not** silently resolve the 748-vs-681 clean-cell discrepancy the panel
     flagged (`s3a2-review-panel-handoff.md:539-544`) — state both and say it is
     unresolved.
   - `tools/PROVENANCE.md` — the alias-topology paragraph is currently stale
     (it describes aliases the records no longer carry); correct it, and add the
     per-region tracing-log row.
   - `tools/MAP_RUNBOOK.md` — the new authoring and render commands under S3a.
   - `.claude/rules/testing.md` — **no change**. The gate triple is unchanged;
     every new command is authoring or rendering and sits outside it.

9. **Stage A gate.** `sources.py --verify`, `validate_map.py --labels`,
   `run_fixture.py --check`, then **send the globe composite to the user**. The
   user's visual approval is the gate; no green check substitutes for it
   (2026-07-26 precedent: every offline check passed while the map was unusable).

#### Stage B — names

10. **`tools/regions/parchment_areas.json`** — new, hand-authored, committed. One
    entry per printed label:

    ```json
    {"id": 1, "source": "parchment", "printed": "Yn Edri Eternos",
     "aliases": ["Oak of Ages"], "kind": "land", "level": "state",
     "box": [1290, 1160, 1372, 1196], "anchor": [1331, 1178],
     "blob_id": 417, "confidence": "high", "needs_review": false,
     "detected_read": null}
    ```

    - `source` is `parchment` or `globe`, so the globe's own labels for NIPPON,
      KINGDOMS OF IND, KURESH, the HUNG LANDS, the FAR OCEAN &c. use the same
      schema, tagged by origin (acceptance criterion).
    - `level` is `state` | `sub_region` | `region` — the two-level binding, made
      explicit at authoring time rather than inferred from cell count.
    - `aliases` is load-bearing, not a convenience: six of the eleven forced
      states are printed under a different name and nothing in the imagery leads
      from "Sartosa" to "Pirate's Current". All eleven aliases from the request's
      forced-state table go in up front.
    - `detected_read` holds the independent cross-check (step 12). Where it
      disagrees with `printed`, `needs_review` is `true` and the entry is
      surfaced, never silently resolved.

11. **`tools/worldgen/schema.py`** — `load_parchment_areas(path)`, modelled on the
    existing `load_registration_file` (`:697`) / `load_elevation_lut` (`:761`) /
    `_cross_check` (`:473`) pattern. This directly answers panel finding #7, which
    must not be repeated for a file three times the size of `named_regions.json`.
    Cross-checks: unique `id`; `kind`/`level`/`confidence` in their enums;
    `anchor` inside the master's committed `crop`; `anchor` inside `box`; no alias
    colliding with another entry's `printed` or `aliases`; and **every one of the
    eleven forced-state canon names resolves to exactly one entry** via `printed`
    or `aliases`. While here, add `load_named_regions()` for
    `tools/regions/named_regions.json` — the panel's standing complaint, and the
    new file has to cross-check against it anyway.

12. **`tools/transcribe_labels.py`** — new, an **authoring** command, documented
    as such alongside `--update-manifest` and `fit_registration.py`. The gate
    never runs it; it reads imagery, the gate reads only the committed JSON.
    - `--detect` → runs `glyph_mask`/`label_blobs`, writes a local-only candidate
      list (blob id, bbox, centroid, pixel count) and local-only crop tiles for
      the vision pass. Tile grid ~1000×700 source px with 15% overlap → ~25
      tiles; measured label density is ~25/tile over ocean and ~45/tile over the
      Empire, so expect **600–800 labels** across roughly 25–30 vision reads.
      This is the milestone's dominant cost.
    - `--cross-check` → the independent second read: difference the master
      against the de-lettered feature image through its committed alias affine
      (the `macro.annotation_mask` technique) and report which detected blobs the
      difference does and does not confirm. Blobs confirmed by only one of the
      two signals are flagged for review.
    - `--merge <file.json>` → validates a transcription batch through
      `load_parchment_areas` and merges it into the committed file, sorted by
      `id`, so re-running is idempotent and the diff is readable.
    - **Normalisation is deliberate and global**, not per-label: the typeface
      renders U as V, so the reader records what the word *is* (`Yn Edri
      Eternos`), and the rule is stated once in the file header rather than
      re-decided 700 times.

13. **`tools/worldgen/naming.py`** — new, canvas-side binding:
    - Warp each label's **stroke footprint** (not just its anchor point) through
      the master's registration and count traced-cell pixels under it. A point
      anchor is the wrong primitive here: labels are rotated and follow curves
      (`The Southern Straits`, `Southern Grey Mountains`), so a centroid can land
      on a border or in a neighbour. The footprint gives the cell set *and* the
      per-cell pixel counts, which is exactly the "**number of cells under this
      label**" the acceptance criteria demand.
    - `level: state` → the majority cell takes the name.
    - `level: sub_region` / `region` → the cell set becomes a named group,
      satisfying the Estalia ≥5 / Tilea ≥4 / Border Princes ≥6 / The Vaults
      quotas with a real footprint to count inside.
    - Reports every cell with no label over it into a generated audit list —
      **generated, not authored**, because it depends on the cell network. It
      belongs in `tools/derived/`, not in the hand-authored names file.

14. **`tools/worldgen/cells.py`** — forced-state protection. `merge_small`,
    `merge_to_target` and `split_large` gain
    `protect: frozenset[int] = frozenset()`. A protected cell is excluded from
    `small` (never merged away), excluded from `cand` (never absorbs a neighbour —
    growth is distortion too), and skipped by `split_large`. The three Great
    Bastion cells are the test case: thin strips well below the mean state area,
    where the risk is **erasure by the merge pass**, which is the concrete
    instance of the open question the S3a-2 handoff raised. Also: `sea_zones`
    gains `named_seats` — canvas anchors that replace `_farthest_seeds` output
    inside the IE footprint, per "Sea names are seeds, not footprints". Iterate
    `protect` and `named_seats` in **sorted** order; this is the
    byte-reproducibility risk the panel flagged at
    `s3a2-review-panel-handoff.md:341-348`.

15. **`tools/generate_state_labels.py`** (Stage B pass) — wire binding in and
    report. New in `state_labels_index.json` per cell: `name`, `aliases`,
    `region`, `sub_region`, and a **stable numeric `id`**. The `id` is the panel's
    cheap mitigation (`s3a2-review-panel-handoff.md:456-468`): vanilla's stable
    handle is `id = N`, the state-region block name *is* the loc key, so pinning
    an id now turns S6's rename into a name-and-loc change against a stable id
    instead of a multi-file atomic graph rewrite. New in COVERAGE.md:
    - forced states: for each of the eleven, the alias it matched through, its
      **cell count** (anything other than 1 is a finding, never a licence to
      place an anchor by hand), and its final area;
    - **share of land belonging to no named region**, against the 33.4% baseline;
    - per-named-region shortfall in IE-footprint land coverage;
    - named cells lost entirely to mask clipping, with where — the polar
      sequencing debt this plan explicitly takes on;
    - sea zones per named sea, and the total against `TARGET_SEA_ZONES`;
    - the unnamed-cell audit list.

16. **`tools/fixtures/`** — new fixture coverage for Stage B against synthetic
    inputs, so none of it is eyeballed: name→cell binding for a label inside one
    cell and a label spanning three; alias resolution; a protected cell surviving
    a merge round that would otherwise absorb it; a named seat producing its own
    sea zone; and the zero-crossover mask assertion (0 px of mask-sea in a land
    state, 0 px of mask-land in a sea zone). The last is already enforced by
    `tools/generate_state_labels.py:343` and checked by
    `validate_map.validate_labels` check #2 — the fixture pins it rather than
    adding machinery.

17. **Docs (Stage B).** `tools/SOURCES.md` + `tools/PROVENANCE.md` gain the names
    file; `tools/MAP_RUNBOOK.md` documents the transcription command;
    `tools/regions/named_regions.json`'s `_comment_pending` block is superseded
    where `parchment_areas.json` now covers it (forced states, sub-region
    footprints) and **narrowed, not deleted**, for what it still owns (navigable
    rivers → S3b/S6). `planning/requests/world-map-source-driven.md` gains a note
    that this request supersedes part of the S3a-2 plan.

18. **Flag, do not fix.** Record in COVERAGE.md without re-targeting:
    `TARGET_LAND_STATES = 659` / `TARGET_SEA_ZONES = 103`
    (`tools/generate_state_labels.py:67-68`) against the panel's measured vanilla
    **675 land + 106 sea**; and 36 vanilla land strategic regions against the
    "47" in the plan of record.

19. **Localization — none in this milestone**, and the reason is worth stating
    rather than leaving as an omission. Nothing here writes `.yml`, and nothing
    here is read by Victoria 3 — every output lives under `tools/`. What this
    milestone produces is the **name inventory** (600–800 canon land and sea
    names with geometry bound to them) that the S6 naming pass turns into
    `localization/english/` entries and `STATE_<REGION>_NNNN` blocks. Step 15's
    stable numeric `id` is the concrete hand-off that makes that pass cheap.

### Design Decisions

- **Bridge the labels, do not erase them.** Measured: +46% usable cells. The
  request's wording is inverted; the rationale is in "Text is bridged, not
  erased" above.
- **Classical glyph detection, no OCR dependency.** Measurement 2 shows the
  signal is unambiguous — 4 giant line components against 3854 compact blobs at a
  clean 9–16 px glyph height. `tools/requirements.txt` stays exact-pinned and
  `run_fixture.py --check` stays byte-reproducible on a clean clone, which a
  torch-backed detector would have put at risk for a job the pixels already
  answer.
- **The master becomes the family's parent, not a fourth independent fit.** Its
  control points already exist inside `ie_macro_twin.json`; the siblings' seeds
  still declare the alias. Fitting the master and re-baking the siblings from
  their own seeds restores one warp for cells, names, macro contours and region
  names. An independent fit would leave the parchment's cells and the twin's
  macro contours — the *same picture* — landing in two different places.
- **Sea names are seats.** Measured (6, 7): the ocean has almost no drawn rules.
  Seeding `sea_zones` guarantees "every named sea has ≥1 zone" by construction,
  where tracing would have delivered a 686k-px undivided cell and a fragile
  threshold.
- **The globe still owns every coastline, no exceptions.** Unchanged
  (`tools/generate_state_labels.py:224`, `:343`). This is what makes a
  rubber-sheeted registration acceptable: local scale error moves an interior
  border a few px inside a landmass and cannot put a coast in the sea.
- **Reported metric nobody currently has: drawn versus tessellated.** The share
  of final land area whose borders came from `split_large` rather than a traced
  line. Both the user's S3a rejection and the panel's density findings are really
  about this number, and it is currently invisible.
- **Text rendering via Pillow's bundled face.** No system font lookup, so the
  committed tiles stay byte-reproducible across machines under the pinned Pillow.

### Edge Cases

- **The 818k-px merged blob survives.** After bridging at `offset=9` the largest
  traced cell is still 818,062 px — faint or broken ruled lines over a large
  area, not a text problem (bridging moved it only 854,893 → 852,522; the
  threshold moved it to 818,062). This is a *recoverable* error by
  `cells_from_ink`'s own argument: the merged cell is still a closed region of
  roughly the right shape, and `split_large` partitions it. It must be
  **reported**, not hidden — it is the honest answer to "how much of this map is
  drawn".
- **Rivers are ink.** The parchment draws its river network in the same idiom as
  its borders, so a cell bisected by a river traces as two cells. This inflates
  the traced count and is absorbed by the merge pass. Report the traced count
  before and after reconciliation so the inflation is visible.
- **Letter counters become junk cells.** The interior of an `o` or an `e` is a
  closed region ~200 px across. `MIN_SOURCE_CELL = 150` catches most; bridging
  removes the rest by making the whole label solid. Confirm the p10 traced cell
  area rises after bridging.
- **The northern polar band is lost twice.** Outside the control-point hull
  (measurement 9) *and* clipped by the mask. Report which named cells vanish;
  do not extrapolate the warp to rescue them and do not work around the mask.
- **A forced-state label resolving to ≠1 cell.** Report as a finding and stop.
  The request is explicit that this is never a licence to place an anchor by hand.
  If the Great Bastion's three strips resolve to one merged cell, that is
  information about the tracing, not a reason to invent geometry.
- **A protected cell that is genuinely tiny.** `validate_map.validate_labels`
  check #7 flags cells below the 256 px floor *with a same-kind neighbour*. A
  protected Bastion strip could trip it. If it does, that is a real finding about
  whether a three-way Bastion split is representable at this canvas scale —
  surface it to the user rather than loosening the lint.
- **Precedence collision.** `stack_layers` rejects a tie by design
  (`tools/worldgen/cells.py:233-239`). Master 100 / `total_war_map_colored` 95 /
  feature image 50 are distinct; the feature image is no longer consumed
  regardless.
- **Alias chain.** `sources.verify` rejects an alias whose parent is an alias.
  Step 3 repoints `ie_named_regions` for exactly this reason; forgetting it turns
  the gate red immediately, which is the desired failure mode.
- **Re-fitting the master moves the macro grouping.** `assign_macros` hard-errors
  if the recovered contour count ≠ `macro.PRINTED_COUNTS` (16). A worse master
  fit could break contour closure. That failure is loud, not silent — but it is
  the reason step 2 reports the twin-displacement number before adopting.
- **Byte reproducibility.** Iterate labels, protected cells and named seats in
  sorted id order; keep `_farthest_seeds` tie-break-stable when a protected cell
  removes candidates. Nothing here is read by the game, so **MP desync is not
  reachable** — the property at stake is regeneration reproducibility.

### Testing

Nothing in this milestone is loaded by Victoria 3 — every output lives under
`tools/` — so there is no `error.log` gate and no in-game step. The
`.claude/rules/testing.md` requirement is satisfied vacuously and deliberately,
the same way S3a's runbook section records it (`tools/MAP_RUNBOOK.md:148-153`).

Offline gate (unchanged, all three must pass at each stage):

```bash
python tools/worldgen/sources.py --verify
python tools/validate_map.py --labels
python tools/run_fixture.py --check
```

Regeneration and review artifacts:

```bash
python tools/generate_state_labels.py --preview
python tools/render_named_map.py --globe --tiles
```

Determinism check, per the acceptance criterion: run
`generate_state_labels.py` twice into scratch dirs and diff the bytes;
`run_fixture.py --check` already does this for the fixture path.

**Stage A gate:** the globe composite is **sent to the user** and the user
approves the geometry. **Stage B gate:** the per-region committed tiles are sent,
and COVERAGE.md's forced-state and quota tables read clean. On anything visual
the user is the final gate — every offline check was green the last time the map
was visually unusable.

### Docs to Update

| File | Change |
|---|---|
| `tools/SOURCES.md` | Master `Registered` → yes, promoted role, fit numbers; `total_war_map_colored.png` demoted from primary; feature image restated as text cross-check; names file added; 748-vs-681 left explicitly unresolved |
| `tools/PROVENANCE.md` | Correct the stale alias-topology paragraph; new per-region tracing-log row |
| `tools/MAP_RUNBOOK.md` | New authoring commands (`transcribe_labels.py`) and the render command under S3a |
| `tools/derived/COVERAGE.md` | Regenerated — never hand-edited. Gains forced-state, quota, clipping, drawn-vs-tessellated and unnamed-cell reporting |
| `tools/.gitignore` | Negations for `derived/named/` |
| `tools/regions/named_regions.json` | `_comment_pending` narrowed to what `parchment_areas.json` does not supersede |
| `planning/requests/world-map-source-driven.md` | Note that this supersedes part of the S3a-2 plan |
| `.claude/rules/testing.md` | **No change** — the gate triple is unchanged |
| `CLAUDE.md` | The `tools/` row gains the names file and its loader as committed, machine-validated inputs |
