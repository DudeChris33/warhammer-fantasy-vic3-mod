# Handoff prompt — build a clean land_sea_mask from the traced coastline, then a new heightmap

Paste the block below into a fresh session.

---

Build the mod's coastline **land/sea mask** from the user's hand-traced coastline, make it the committed authority, then **regenerate the heightmap** to conform to it (the current heightmap is bad). Read `CLAUDE.md`, `.claude/rules/*`, and `memory/*` first — especially the Autonomy model in CLAUDE.md, `memory/feedback-visual-artifact-is-the-real-gate.md`, and `memory/project-miller-canvas-is-the-frame.md`. This touches committed, multiplayer-synced bitmaps (`tools/derived/land_sea_mask.png`, `map_data/heightmap.png`), so **the user gates every rendered result before anything commits**; a green offline check is never sufficient to commit.

## The decision already made (do not relitigate)
The user traced the entire world coastline as a magenta (255,0,255) line directly on the **canvas-space** reprojected globe `sources/terraqueous_globe_reprojected_with_coast.png` (8192×3616 = the mod canvas, so it needs no registration). This hand-trace **supersedes** the height-ramp coast that `generate_heightmap.py` used to extract — "the traced coastline wins" (user, 2026-08-14). Ownership is settled: a **dedicated tool owns the mask**, and `generate_heightmap.py` becomes a **consumer** of the mask (it conforms relief to the mask; it no longer derives the shoreline).

## Part 1 — the land/sea mask (mostly done, needs finishing + committing)
A working tool already exists in the tree: **`tools/generate_coastline_mask.py`** (drafted and validated this session — land fraction 0.379, world ocean 62% of canvas, Ulthuan's Inner Sea correctly sea, rivers preserved, self-contained). Its method (keep it — it is correct and needs no colour/prior-mask/lake-list):
1. Coast = the magenta line, dilated 2px to bridge anti-aliased gaps.
2. Label the regions between lines; assign each line pixel to its nearest region so the shoreline is a **crisp 1px** coast, not the drawn stroke width.
3. World ocean = the largest region. Classify everything else by **parity of coastline crossings from the ocean**: ocean = water (depth 0), continents touching it = land (1), inland seas enclosed in a continent = water (2), lake-islands = land (3)… Exact, self-contained.
- **Navigable rivers**: the user drew thin channels off the coast; they are continuous with the world ocean so they fall out as ocean-connected sea automatically, and **must stay that way** — in-game they become their own navigable sea zones (user, 2026-08-14). Do not solidify them.

To finish it: **manifest the source** (`python tools/worldgen/sources.py --update-manifest` after adding an Origin/Role row for `terraqueous_globe_reprojected_with_coast.png`; then the tool runs without `--direct`); sanity-check for spurious tiny water specks (there are ~427 water regions — most are fine, but consider a min-area floor for water so a stray enclosed pixel isn't a "sea"); render the mask and **send it to the user to gate**; then write `tools/derived/land_sea_mask.png` and run the offline gate (`python tools/worldgen/sources.py --verify`, `python tools/validate_map.py`, `python tools/run_fixture.py --check`). Add a `tools/run_fixture.py` fixture for the new tool if you extend it. Update `tools/SOURCES.md` / `tools/PROVENANCE.md` / `CLAUDE.md` to record that the mask is now **trace-derived, not height-ramp-derived**.

## Part 2 — a new heightmap (the current one is bad)
`map_data/heightmap.png` is bad per the user — **first ask them exactly what's wrong** (coast mismatch? enclosed-water artifacts? relief quality? sea-floor?) and reproduce the complaint before changing anything. Then rewire `tools/generate_heightmap.py` so it **consumes the new `land_sea_mask.png` as the authoritative land/sea** (relief only where the mask says land; sea level where it says sea) instead of deriving the coast from the globe's height ramp. The existing enclosed-water / `tools/config/inland_lakes.json` logic in that generator is now largely subsumed by the mask (inland seas are already water in the mask) — reconcile, don't duplicate. Regenerate, render, and **gate with the user**; re-run the offline map gate (`validate_map.py`, `run_fixture.py --check`) and, once the user accepts the visual, the in-game `error.log` check per `.claude/rules/testing.md`.

## Key facts / pitfalls
- The reprojected globe's **sea is a desaturated grey**, not blue — no hue test separates land from sea on it. That's the whole reason the hand-traced coast exists; do **not** try to re-derive the coast from globe colour.
- The mask is the **sole coastline authority** (user decision #1) — every downstream consumer (heightmap, registrations, state labels) conforms to it.
- Do not commit either bitmap on offline checks alone; the rendered artifact + the user's yes is the gate.
- After the mask changes, `colored_globe`'s registration (and any other) should be re-fit against it and the IE region-slicing handoff (`planning/ie-map-region-slicing-handoff.md`) picks up the new mask automatically.

## Working tree you inherit (uncommitted)
- `tools/generate_coastline_mask.py` (new, validated, uses `--direct` until the source is manifested).
- `tools/fit_registration.py` + `tools/worldgen/parchment.py`: `flat_sea` / `blue_sea` / `landmark_refine` additions (unrelated to the mask, leave them).
- `tools/SOURCES.md`: `colored_globe.jpg` registered, `old_world_black_white_colored.png` manifested (seed only, deferred). `terraqueous_globe_reprojected_with_coast.png` is **not yet manifested** — that's Part 1's job.
- Committed `land_sea_mask.png` and `map_data/heightmap.png` are the OLD versions until this work replaces them.

## How to work
Follow CLAUDE.md's Autonomy model: iterate the loop (edit tool/config → regenerate → offline gate → render → send the user the PNG → diagnose → repeat) autonomously to convergence, chaining passes; stop and hand back for the user's visual verdict on the mask and the heightmap, and before any commit. First action: read `tools/generate_coastline_mask.py` and run it (`--direct`) to reproduce the validated mask, render it, and confirm the coastline with the user before finishing Part 1.
