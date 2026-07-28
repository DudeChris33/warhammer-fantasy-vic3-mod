# Chaos Wastes polar fringe classified as deep ocean, with spiked edges

| Field | Value |
|-------|-------|
| Type | bug |
| Status | open |
| Date | 2026-07-26 |
| Severity | high |

## Description

The northern polar band of the generated world — the Chaos Wastes / Northern
Wastes / Realm of Chaos fringe — comes out of the S2 heightmap pipeline as
**open ocean at the bottom of the elevation range**, with a **ragged, spiked
coastline** along its southern edge and stray needle-shaped islands scattered
through it.

Observed, measured on the committed artifacts:

- `tools/derived/land_sea_mask.png` canvas rows 0..110 (lat 79.45N down to
  74.6N) are **1.1–2.4% land**. Everything else on that band is sea.
- `map_data/heightmap.png` rows 0..220 (the same band at heightmap resolution)
  have a **median of −888 m** — the clamped floor of the encoding, i.e. the
  same value vanilla uses for its deepest abyssal plain.
- The land that *does* survive up there is not terrain. In canvas rows 0..260
  the mask holds 12 separate components, several of them long horizontal
  needles (e.g. 1090x172 px at x=1186, 320x52 at x=4081, 53x8 at x=133) — the
  "spikes" in the report.
- The transition at row ~110 is the map's *drawn* northern limit being read as
  a shoreline: land fraction climbs 2.4% → 6.6% → 13.8% → 21.6% over rows
  90→130, and the resulting boundary is a scalloped, finger-like edge rather
  than a coast.

Expected: the Chaos Wastes are **land** (frozen polar waste, per the LUT's own
stated intent — `paper_elevation_m: 300`), with a smooth, deliberately-drawn
southern limit, not a torn-paper edge promoted to a coastline.

This has already propagated downstream: in `tools/derived/state_labels.png`,
canvas rows 0..110 are **98.1% sea-zone cells** (884,387 sea px vs 16,733 land
px across 28 cells). Any S3b province cut from the current mask puts open ocean
where the Chaos Wastes belong.

## Context

Found by inspecting the committed S2/S3a artifacts against
`sources/terraqueous_globe.jpg`, which `CLAUDE.md` and
`tools/registration/terraqueous_globe.json` both designate as the trusted shape
and the sole owner of the coastline layer (`layer_precedence.coastline: 90`).

No game load is involved — this is entirely in the offline `tools/` pipeline,
upstream of any `.txt`/`.yml`/`.gui` script. Nothing here touches
`docs/*.log`-governed script syntax, and nothing here is non-deterministic:
the pipeline reproduces this result byte-identically every run. It is a
**content-correctness** bug, not an MP-desync one.

Reproduce with the committed data (no regeneration, read-only):

```bash
tools/.venv/Scripts/python.exe -c "import numpy as np; from PIL import Image; Image.MAX_IMAGE_PIXELS=None; m=np.array(Image.open('tools/derived/land_sea_mask.png').convert('L'))>127; print([round(100*m[y].mean(),1) for y in (0,40,80,110,140,200,320)])"
```

Prints `[1.7, 1.6, 1.9, 6.6, 25.1, 44.1, 51.4]` — the polar band is empty.

## Acceptance Criteria

- [ ] The polar fringe above the Terraqueous globe's drawn terrain limit is
      **land**, not ocean, on `tools/derived/land_sea_mask.png` and therefore on
      `map_data/heightmap.png`.
- [ ] Its southern edge is a smooth, intentional boundary — no scalloped fingers
      and no needle islands. Concretely: no land component in canvas rows 0..260
      with bounding-box aspect ratio > 8 and area < 40,000 px.
- [ ] The polar band is not encoded at the abyssal floor. Rows 0..220 of
      `map_data/heightmap.png` decode to a plausible waste elevation (the LUT's
      `paper_elevation_m` is 300 m), not −888 m.
- [ ] Whatever rule decides "blank page = polar waste" is **not** a nearest-RGB
      decision between `paper_rgb` and the deepest-ocean swatch — see root cause;
      that comparison is measurably unstable on this source.
- [ ] `tools/run_fixture.py --check` covers the polar-fringe rule with a
      synthetic fixture, so the behaviour is pinned rather than eyeballed.
- [ ] `python tools/worldgen/sources.py --verify`, `python tools/validate_map.py
      --labels` and `python tools/run_fixture.py --check` all pass after the fix,
      and `tools/derived/state_labels.png` is regenerated (the current one
      encodes the wrong answer).

## Investigation

- **Likely root cause**: the "blank page = polar land" rule in
  `tools/worldgen/lut.py` is a nearest-RGB tiebreak between two swatches that
  are not separable on this source. `tools/lut/terraqueous_elevation.json`
  commits `paper_rgb: [236, 232, 218]` and band 0 (−9000..−7000 m) as
  `[210, 209, 197]` — **40.6 RGB units apart**, so the decision boundary sits
  ~20 units from each. The actual page tone inside the polar oval measures
  **[208.5, 205.4, 190.8] to [215.9, 210.5, 195.6]** across three sampled
  patches — i.e. 42 units from the committed `paper_rgb` and *closer to the
  deep-ocean swatch than to the paper entry*. Measured per-pixel: the paper
  entry wins only **33.4% / 34.1% / 35.6%** of blank polar pixels (median
  distance to paper 27.4 vs 19.8 to band 0). The 7-px majority filter in
  `ingest.classify_source` then erases that minority, and the Chaos Wastes
  become the world's deepest ocean.

  The committed value is not simply mistyped — the classifier is
  **ill-conditioned** here. Re-running `ingest.classify_source` on a polar strip
  (source y 190..330, x 1450..2550) with `paper_rgb` perturbed gives land
  fractions of **23.1%** (committed `[236,232,218]`), **22.5%**
  (`[212,208,193]`), **59.7%** (`[216,211,196]`), **22.3%**
  (`[209,205,191]`). A 3-unit change in the LUT swings 37 points of the polar
  band. Any colorimetric fix would be re-tuning noise; the rule needs to become
  spatial (the polar blank is one region contiguous with the oval's north rim,
  whereas the −9000 m swatch appears in enclosed mid-latitude basins), or the
  polar fringe needs an explicit policy that stops reading land/sea from a
  source that does not draw it.

- **Second root cause (the "spikes" and the distortion specifically)**: the
  Terraqueous globe **has no drawn terrain north of ~72.5–74.5N**. Measured by
  walking source columns near the central meridian for the first sustained
  non-page run: sx=1500 → 74.32N, sx=1700 → 73.31N, sx=1900 → 74.52N, sx=2100 →
  74.52N, sx=2300 → 73.81N, sx=2500 → 72.51N. North of that the sheet carries
  only the words "REALM OF CHAOS", "CHAOS WASTELAND", "NORTHERN WASTES" over
  blank page, and the wash ends in a deliberately **torn/feathered artistic
  edge**. The canvas runs to 79.453125N (`tools/config/canvas_frame.py:34`), so
  the top ~110 canvas rows — 8192 x 110 ≈ 900k px, ~3% of the canvas — are being
  derived from a part of the source that contains no land/sea information at
  all, and the torn edge is the only high-contrast feature there, so it becomes
  the coastline.

- **Amplifier**: the despeckle thresholds are fixed in *source* pixels while the
  NE-II → plate-carrée reprojection stretch is strongly latitude-dependent.
  Measured canvas-px-per-source-px: **3.74x horizontal / 2.48x vertical at
  79.45N** (source width of a full parallel is only 2189 px there) against
  **2.19x / 1.83x at the equator** — a 2.3x difference in *area*. So
  `SOURCE_MIN_BLOB = 900` (`tools/generate_heightmap.py:114`) removes a blob of
  ~3,600 canvas px at the equator but only fails to remove one of ~8,400 canvas
  px at the pole, and `CANVAS_MIN_BLOB = 256`
  (`tools/generate_heightmap.py:83`) is far too small to catch what survives.
  A run of a handful of ambiguous source pixels near the pole therefore emerges
  as a several-hundred-pixel-long needle — exactly the observed artifacts.

- **Not the cause**: the *geometric* registration is sound and should not be
  touched. `reproject.fit_parametric` recovers the committed control points to
  **rms 0.0019 px**, the underlying envelope fit is 0.363 px rms, anisotropy
  |sx/sy − 1| = 0.00067, and the crop `[134, 132, 3866, 2127]` comfortably
  contains the whole northern band the canvas asks for (canvas row 0 samples
  source y = 194.7, x = 905..3094, all interior). No crop clamping occurs at the
  top edge. The word "registered" in the report is about the *content* landing
  wrong, not the projection.

- **Confidence**: high on both root causes — each is a direct measurement on the
  committed source and the committed artifacts, and the counterfactual re-run
  reproduces the failure through the real `ingest.classify_source` code path.

- **Code path**:
  - `tools/lut/terraqueous_elevation.json:27-29` — `paper_rgb`,
    `paper_elevation_m`, and the note asserting the rule that does not hold.
  - `tools/worldgen/lut.py:42-49` (`_palette`) — appends paper as just another
    swatch; `tools/worldgen/lut.py:52-75` (`classify`) — pure nearest-RGB
    argmin, no spatial term, ties resolved toward the earlier (ocean) index.
  - `tools/worldgen/ingest.py:77-90` (`classify_source`) — the 7-px majority
    filter and `min_blob` despeckle that convert the 1/3 minority into 0%.
  - `tools/generate_heightmap.py:83` (`CANVAS_MIN_BLOB = 256`),
    `tools/generate_heightmap.py:114` (`SOURCE_MIN_BLOB = 900`) — thresholds
    fixed in source px against a 2.3x latitude-varying area stretch.
  - `tools/config/canvas_frame.py:32-35` — `LAT_MAX = 79.453125`, with the
    comment "the top/bottom bands are the Chaos Wastes fringe", i.e. the frame
    knowingly extends past what the source draws, but nothing downstream acts on
    that.
  - `tools/generate_heightmap.py:283-295` — the coastline mosaic has exactly one
    layer, so there is no second source to outvote Terraqueous in the polar band.

- **Regression test**: none exists. `tools/run_fixture.py --check` covers LUT
  classification, reprojection, segmentation, compositing and river
  rasterization against `tools/fixtures/ingest/`, but no fixture exercises a
  blank polar fringe, which is why this shipped. The fix should add one. The
  read-only reproduction above (mask row profile `[1.7, 1.6, 1.9, 6.6, 25.1,
  44.1, 51.4]`) is the current failing observation to check against.

- **Related files**:
  - `sources/terraqueous_globe.jpg` (local-only; SHA-256 in `tools/SOURCES.md`)
  - `tools/lut/terraqueous_elevation.json`
  - `tools/worldgen/lut.py`, `tools/worldgen/ingest.py`, `tools/worldgen/segment.py`
  - `tools/generate_heightmap.py`
  - `tools/config/canvas_frame.py`
  - `tools/derived/land_sea_mask.png`, `map_data/heightmap.png` (generated —
    regenerate, never hand-edit)
  - `tools/derived/state_labels.png`, `tools/derived/state_labels_index.json`,
    `tools/derived/COVERAGE.md` (downstream; COVERAGE.md line 46 already lists
    "a polar source" as the lowest-value gap — that assessment predates this
    measurement and should be revisited)
  - `tools/run_fixture.py`, `tools/fixtures/ingest/`

- **In-game reproduction**: not applicable yet. `map_data/provinces.png` does
  not exist until S3b, so the mod does not currently define playable map
  geography and `logs/error.log` has nothing to say about this. The failure is
  fully visible offline in the committed bitmaps.

## Open design question for `/plan`

Two defensible directions, and the choice changes the whole implementation:

1. **Synthesize the fringe.** Treat everything north of the drawn terrain limit
   as polar waste land by rule (region-grow the blank page from the oval's north
   rim, floor it at `paper_elevation_m`, give it a smooth southern join). Cheap,
   no new source, and matches the LUT's stated intent — but the fringe's shape is
   then invented rather than sourced.
2. **Register a polar source.** Bring in a source that actually draws the Chaos
   Wastes and let it own the coastline layer above ~72N via the existing mosaic
   precedence (which `generate_heightmap.py:275-295` was explicitly built to
   allow as a data-only change). Faithful, but nothing currently in `sources/`
   is a whole-world polar view.

Either way the LUT's nearest-RGB paper rule and the latitude-blind blob
thresholds need addressing, since both cause artifacts independent of which
direction is chosen.
