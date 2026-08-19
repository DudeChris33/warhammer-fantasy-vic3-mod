# Handoff prompt — IE map via region slicing

Paste the block below into a fresh session.

---

Work **solely** on registering the Total War: Warhammer 3 Immortal Empires parchment map (`sources/tww3_ie_parchment.jpg`, 3703×2880) onto the mod's coastline by **region slicing**: carve it into landmasses, fit each independently, composite. Do not touch any other source. Read `CLAUDE.md`, `.claude/rules/*`, and `memory/*` first — especially `memory/project-map-registration-landmark-wall.md` and the Autonomy model section of CLAUDE.md.

> **UPDATE 2026-08-14 — the coastline authority changed.** The user hand-traced the entire world coastline (a magenta line) directly on the canvas-space reprojected globe (`sources/terraqueous_globe_reprojected_with_coast.png`), and it now **supersedes the height-ramp mask** ("the traced coastline wins"). A new tool `tools/generate_coastline_mask.py` builds `tools/derived/land_sea_mask.png` from it by coastline topology (validated: land 0.379, self-contained, rivers preserved as navigable sea). **Fit the IE regions against whatever `tools/derived/land_sea_mask.png` currently is** — it is still the fitting objective and still the sole coastline authority; just be aware it may have been regenerated from the trace (a separate handoff covers building the clean mask + a new heightmap). If the mask has visibly changed since you last saw it, that is expected. Nothing else in this plan changes.

## Why region slicing (don't re-litigate this)
Whole-map registration of this source is capped at IoU ~0.62 and cannot go higher: Immortal Empires is a *playable* map with **nonuniform scaling** — Ulthuan is drawn ~2× its true world-size — so a single smooth thin-plate warp can't shrink Ulthuan while leaving the Old World alone. Only a per-region local transform gets past this. (Contrast `colored_globe.jpg`, just registered whole-world at IoU 0.65 because it's a proper world map with balanced land/sea. IE is the opposite case — see both records/seeds.)

## Approach
For each landmass — **Ulthuan, the Old World, Naggaroth, Lustria, the Southlands, Cathay**, plus major island groups:
1. Crop the source's silhouette **and** the committed mask (`tools/derived/land_sea_mask.png`) to that region's bounding box.
2. Fit the region silhouette to the cropped mask (coarse affine + thin-plate refine) **within the cropped frame** — inside one landmass the land/sea is balanced, so the coarse silhouette IoU locks sharply, with no inflation and no reliance on hand-picked landmarks.
3. Map the fitted control points back to full-canvas coordinates.
4. Composite the per-region fits and render a combined qa overlay.

**Start with an Ulthuan proof-of-concept**: carve Ulthuan, fit it standalone, render the overlay, confirm with the user (Ulthuan is self-contained and should lock tightly — the user has already done this by hand). Then roll out to the other regions.

## Key facts
- **The mask is the sole coastline authority** (`tools/derived/land_sea_mask.png`, user decision #1). Region fits are *scored against* it; nothing moves a shoreline.
- **This source has no extractable ocean** — its sea is the same parchment as its land. Its silhouette comes from the climate sibling `sources/tww3_climate.jpg` via `parchment.painted_mask`, scaled by `to_master_scale`. The existing whole-world seed `tools/registration/seeds/wh3_dlc_ie_parchment_map_english.json` has the exact silhouette spec, the 12 landmarks (globe px on `terraqueous_globe.jpg` → canvas via its committed NE-II fit), and the coarse/lattice/refine structure. Use it as the per-region template. Its committed record is `tools/registration/wh3_dlc_ie_parchment_map_english.json`.
- **Fitting tool**: `python tools/fit_registration.py --seed <stem>` (add `--dry-run`). Objectives: `silhouette`, `landmarks`, `landmark_refine`. Silhouette `kind`s: `flat_colour`, `painted`, `flat_sea` (per-seed sea RGB), `blue_sea` (blue-dominance). The last two + `landmark_refine` exist in the current uncommitted working tree.
- **You will likely add a region-crop capability** to the fitter: fit a cropped silhouette against a cropped mask region-of-interest, scoring IoU **only within the region box**, then emit full-canvas control points. The current tool scores against the whole mask — a land-heavy partial silhouette scored whole-map **inflates** (measured; do not do it).
- **By-eye landmark picking is unreliable** (see the memory file). Region silhouette fitting is chosen precisely to avoid it — a balanced-crop coarse sweep locks without landmarks. If a region genuinely needs landmark anchoring, **ask the user for the pixel picks**; do not guess.

## Verify + gate
- **The visual gate** is `python tools/qa_overlay.py <source>` → `tools/derived/qa_<stem>.png` (source warped through its registration, mask coastline in magenta). Render it and **send it to the user** — this, not offline IoU and not the state_labels overlay, is the real gate. The user is the final authority on any rendered map.
- **Offline gate** before committing anything under `tools/registration/` or `map_data/`: `python tools/worldgen/sources.py --verify` and `python tools/run_fixture.py --check`. Green offline is a precondition to continue, never a stopping point or grounds to commit.
- Do **not** commit records/bitmaps on offline checks alone. Do **not** overwrite the committed IE master record or regenerate `state_labels` (it feeds `generate_state_labels.py`, an MP-synced bitmap) without the user's explicit go — prefer **new per-region records** over touching the master.

## Working tree you inherit (uncommitted)
- `tools/fit_registration.py` + `tools/worldgen/parchment.py`: `flat_sea`, `blue_sea`, `landmark_refine` additions.
- `tools/SOURCES.md`: `colored_globe.jpg` registered; `old_world_black_white_colored.png` manifested (seed only, deferred — it hit the landmark wall).
- Seeds `colored_globe.json`, `old_world_black_white_colored.json`; record `colored_globe.json`.
- IE master seed/record at committed state (a measured re-fit was rejected as an interior regression — leave it).

## How to work
Follow CLAUDE.md's Autonomy model: iterate the loop (edit region seed/crop → fit → offline gate → render qa overlay → diagnose → repeat) autonomously to convergence, chaining passes; stop and hand back for the user's visual verdict on each region and before any commit. Ask the user for region boundaries or landmark corrections rather than guessing — geography is their call. First action: read the IE and `colored_globe` seeds as templates, propose the Ulthuan region box, and carve+fit Ulthuan as the proof-of-concept.
