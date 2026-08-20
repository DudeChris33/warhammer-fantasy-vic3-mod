# Handoff prompt — register an Old World region via paired anchor dots

Ready-to-paste prompt for a future session. The **Badlands + Nehekhara** tile is
the worked template (it superseded the Empire, which was done first and is not the
best example). Replace `<REGION>` / `<region>` and the dots filenames with the new
region's, then paste everything below the line.

---

Register another region of the Warhammer map onto our canvas using the paired-anchor-dot
workflow. **Badlands + Nehekhara is the worked template — read these first:**

* Seed: `tools/registration/seeds/tww3_old_world_mod_parchment_badlands_nehekhara.json` — mirror its shape.
* Derived record: `tools/registration/tww3_old_world_mod_parchment_badlands_nehekhara.json`.
* Example render: `tools/derived/badlands_nehekhara_anchor_dot_warp_example.png`.
* Mechanism: `tools/fit_registration.py` — the `landmarks` objective + `anchor_landmarks`,
  which accepts direct `canvas` landmarks (a pixel read straight off the reprojected
  globe = canvas frame). `objective: landmarks` never loads the source image.
* Follow CLAUDE.md's autonomy model: iterate the tooling loop yourself, render + SEND
  the PNG for my visual verdict, and STOP at sourcing and at commit.

**What I'll put in `sources/dots/` (local-only, gitignored):**

* `tww3_old_world_mod_parchment - dots_N.png` — the region cropped from the parent map,
  RGBA, alpha erased to transparency over everything OUTSIDE the region I want, plus
  solid dots in distinct pure-RGB marker colours on features I'm certain of (spread to
  coastal extremes, not just interior). The marker palette (every channel in
  {0,63,127,191,255}) is listed in `sources/dots/127 0 191.txt`.
* `terraqueous_globe_reprojected - dots_N.png` — the 8192×3616 reprojected globe
  (= our canvas/mask frame) with the SAME dots, matched by colour.

**Do this**

1. Read the CURRENT dims of both files fresh — I re-export between iterations, don't
   trust earlier numbers. Recover each dot centroid by exact RGB match (compact
   connected component, `alpha>0`). Pair by colour. Confirm the SAME set of colours is
   present in both — **detect the colours present, don't assume a fixed count** (Empire
   used 9, Dark Lands 14, Badlands 17).
2. Sanity-check: (a) render a crop-space thumbnail so the alpha excludes what I intended,
   and (b) fit a global affine over the pairs — a single wild-outlier residual flags a
   swapped/mispaired dot, whereas a smoothly spread residual is just projection curvature
   the thin-plate will absorb (Badlands' 16 pairs were mean 34 / max 89 px).
3. Write `tools/registration/seeds/<REGION>.json` modelled on the Badlands seed:
   `objective: "landmarks"`, `master_shape` = crop's native `[height, width]`, a lattice
   (~6×6, inset 0.03), and the N landmarks as `{name: <colour>, source: [crop px],
   canvas: [globe px]}`. Provisional record block, flagged `PROVISIONAL.`
4. Derive: `python tools/fit_registration.py --seed <REGION>`.
5. Diagnostic render (the Badlands/Dark-Lands style — neutral gray backdrop): thin-plate-warp
   the crop (respecting `alpha>0` only) onto the canvas via the dots, overlay
   `tools/derived/land_sea_mask.png` coastline (cyan) + dots (red rings), crop to footprint.
   SEND the PNG, read out alignment. Iterate if I ask — I may add coastal dots and
   re-export (back to step 1), or ask to hold out a dot for an A/B compare (as with
   Badlands' interior `yellow`: remove it from the seed's `landmarks` AND re-derive, and
   keep the crop window identical so the two renders are pixel-comparable).
6. On my accept: derive a clean, dot-free, alpha-preserved `sources/<REGION>.png` by
   nearest-neighbour-inpainting **ALL** markers out of my crop (including any held-out
   dot — it is still a marker in the image; dilate the exact-match mask ~3 px to swallow
   anti-alias halos, fill RGB from the nearest non-marker land pixel, keep alpha
   byte-identical, assert zero marker px remain). Point the seed's `source` at it, and
   refresh the committed example render at
   `tools/derived/<REGION>_anchor_dot_warp_example.png` from the clean source.
7. Gate: `python tools/worldgen/sources.py --verify` and `python tools/run_fixture.py --check`.
   Expect `--verify` to report the new source has "no row in SOURCES.md" — that is resolved
   only by `--update-manifest`, which is MY call. Do NOT run `--update-manifest` if other
   files in `sources/` have unrelated pending changes (all-or-nothing, would bless them).
   `run_fixture.py --check` must be fully green.
8. Commit on a branch when I say — seed + derived record + example render (message only,
   no push). The clean crop in `sources/` is gitignored and stays out of the commit.

**Gotchas (from Empire → Bretonnia → Kislev+Norsca → Dark Lands → Badlands+Nehekhara)**

* The crop's alpha is the exclusion — load RGBA, warp `alpha>0` only; `.convert("RGB")`
  drops it silently.
* I re-export/re-crop between iterations (dims + dot coords change). Re-read every pass.
  "Try again" usually means "I updated the file."
* `terraqueous_globe_reprojected.png` IS the canvas/mask frame — a dot on it is its
  canvas pixel directly, no globe fit.
* Whole-map fitting fails (inconsistent inter-region scale). Strictly per-region — one
  region, one crop, one seed. The x/y affine scales legitimately differ (Badlands ~0.427
  vs ~0.358); the thin-plate absorbs the non-affine curvature at each dot.
* Straight edges of the crop where alpha ends are interior borders with the neighbouring
  region, not coasts — no mask coastline is expected there; that is not misalignment.
* Holding out an interior dot can lower the residual (Badlands 17→16 dropped 39/112 to
  34/89 px) but leaves that feature positioned only by the thin-plate trend — it's a
  visual-verdict tradeoff, mine to call.

---

## Current state (2026-08-20, board item #2174 close-out)

All six placed sources exist in `sources/` again — the five parchment region
tiles (Empire, Bretonnia+Estalia+Tilea, Kislev+Norsca, Dark Lands,
Badlands+Nehekhara) plus the northern relief crop
(`start_warhammer_old_world_northern.png`) — re-derived from the surviving marked
dot crops in `sources/dots/`. `sources.py --verify` and `run_fixture.py --check`
are green; the manifest (`tools/SOURCES.md`) is reconciled and re-swept.

Steps 5 and 6 of the workflow above are now **committed scripts**, not session code:

* **Step 6 (clean source):** `python tools/inpaint_dot_markers.py --seed <stem>
  --dots <path>` — exact-RGB marker detection, seed-landmark centroid cross-check
  (wrong-file guard), dilated nearest-opaque-donor inpaint, alpha byte-identical,
  zero-marker-px assert. `--diff-against <existing>` guards a re-derivation against
  an already-accepted clean source. Two pre-convention crops (bretonnia, kislev)
  use off-palette dot colours; the script samples the dot colour at the seed
  landmark position as a fallback, still exact-RGB.
* **Step 5 (render):** `python tools/render_anchor_dot_example.py --all` — warps
  each clean source through its **committed** record (no re-fit) in the accepted
  style, writing `tools/derived/<region>_anchor_dot_warp_example.png` plus the
  combined nine-zone `old_world_anchor_dot_warp_combined.png`.

**Legacy-fit caveat for any future re-derive.** `fit_registration.py`'s landmarks
objective was rewritten (4580e9c) to bound the lattice to the dot hull + pad for
≥4 landmarks. The bretonnia, kislev_norsca, dark_lands and start_warhammer records
predate that (full-frame lattice) — **re-deriving them today changes their geometry
and shrinks their footprint to the dot hull + pad.** Recovering the lost periphery
needs edge dots from the user (a sourcing step). #2174 therefore ran **no** fit
re-derives; it only re-derived the clean image bytes (which `objective: landmarks`
never reads) and re-rendered through the unchanged records. Precedence promotion
and the empire/badlands boundary wiring are board item #2207.
