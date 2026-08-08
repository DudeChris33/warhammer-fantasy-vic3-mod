# S3a-2 review panel — handoff prompts

| Field | Value |
|-------|-------|
| Status | superseded |

> **Superseded (2026-08-04) by
> [world-map-miller-projection-canvas.md](world-map-miller-projection-canvas.md).**
> The plan these findings blocked no longer exists in the form they were written
> against. The findings themselves were not answered here and are not silently
> dropped: the two mask-level blockers are fixed in that request's Phase 4, and
> the naming/density work is recorded under its "Now unowned" section as needing
> its own request.

The five-expert review panel sat on the **S3a-2 plan**
(`planning/requests/world-map-source-driven.md:1395-1806`) on **2026-07-28** and
returned a unanimous **BLOCK** — loremaster, cartographer, geographer,
vic3-modding-expert and game-designer all blocked in their own lanes.

This file holds one paste-able prompt per finding cluster, so each can be tracked
and fixed independently rather than disappearing into a single re-plan. Findings
are grouped where one change fixes several; the grouping is stated in each prompt
so it can be split if wanted.

**The panel report itself is not yet committed** — it lives in the session
transcript. Every prompt below therefore carries its own evidence inline and
stands alone.

## Ordering

Prompt **1 is the critical path** — it gates S3a-2 *and* the S4 boot. Prompts 2–5
are the remaining blocks. Prompts 6–10 are concerns and can run in parallel.
Prompt 11 is not a work item; it is the open-questions list.

Numbers attributed to a panelist below were measured by that panelist, not by the
synthesiser. Re-verify anything load-bearing before acting on it — in particular
the vanilla-install counts in prompt 6.

---

## 1 — Polar fringe: fix before S3a-2 (BLOCK, all five panelists)

An issue file already exists. This prompt amends it and plans it.

```
/plan planning/issues/chaos-wastes-polar-fringe-misclassified.md

The review panel blocked S3a-2 on this issue, unanimously and in all five lanes.
Before planning, add three findings to the issue file that it does not currently
record:

1. IT BLOCKS S3a-2, NOT JUST S2. tools/regions/named_regions.json:25,41 sets
   northern_chaos_wastes min_states 20 and southern_chaos_wastes min_states 10;
   the S3a-2 two-stage allocation lands them at 46 and 13. Measured against the
   committed land_sea_mask.png: rows 0..110 hold 16,733 land px and rows
   3300..3616 hold 9,446 px - together 2.09 states' worth at the 12,517 px mean.
   The geographer measured 100,276 px north of 72.5N (8.0 states), 27,508 px in
   the whole southern polar zone (2.2 states), 5,845 px south of 70S (0.5
   states). The cartographer found only 3 distinct land cells touching rows
   3300..3616, two already needles (246 px at aspect 12.8, 208 px at aspect
   10.6). So S3a-2's self-gate "every region meets its min_states" is
   unsatisfiable without shattering the torn fringe into ~1,000 px crumbs.

2. THE ACCEPTANCE CRITERIA MISS THE LARGEST ARTIFACT. The issue's criterion
   bounds needles at "aspect ratio > 8 AND area < 40,000 px". The cartographer
   rendered the NW corner at native resolution and found a 48,070 px comb of
   stacked splinters at x 0-624 / y 0-307 - streaks 150-400 px long and 5-15 px
   tall, plus an isolated 160x49 spindle at x 501-661 / y 27-75. It is far too
   large to be caught by the current criterion, and it is visibly the user's own
   third S3a complaint ("weird spiky bits on the corners"). Add a criterion that
   catches it.

3. A POLAR SOURCE MAY ALREADY BE REGISTERED. The issue's open design question
   offers "synthesize the fringe" vs "register a polar source" and says nothing
   in sources/ is a whole-world polar view. The loremaster found that
   total_war_map_colored.png - ALREADY the registered primary boundary source -
   draws the northern Chaos Wastes as fully provinced, named land, reading off
   rows 0-320: Frozen City, Palace of Ruin, Palace of Princes, Severed Tower of
   Sorcerers, The Twisted Towers, The Howling Citadel, Fortress of the Damned,
   Blood Mountain, Atorak, Dargoth. This materially changes the cost of option 2.
   Verify it, then decide.

Also settle the sequencing consequence in the plan: the fix rewrites
land_sea_mask.png, which is the raster every S3a-2 region border is cut from
(cells are intersected with the mask, and S3a-2 additionally makes sea a region
barrier). So any S3a-2 output in the polar bands is throwaway until this lands.
Note that this fix must also precede the S4 boot: six game-read files are already
committed under map_data/ and heightmap.png rows 0..220 already encode the defect.
```

---

## 2 — Budget arithmetic and gate thresholds (BLOCK ×2)

Covers: Southern Realms floor-bound at 17 (game-designer + vic3-modding-expert,
independently reproduced); the `>` vs `>=` guard; the unquantified 66.6%
criterion; the uncapped catch-all; forced-vs-sub-region counting.

```
/request S3a-2's budget arithmetic and self-gate thresholds are wrong in four
ways that let a green gate ship a wrong answer. All are in
planning/requests/world-map-source-driven.md:1395-1806 and
tools/regions/named_regions.json.

1. THE SOUTHERN REALMS MARGIN IS FALSE. The plan (:1540-1544) says
   "TW3-proportional gives it 20, so it clears - but only by three". Two
   panelists independently re-ran the ADOPTED two-stage allocation and got 17,
   floor-bound, at every point in the 600-700 band. The "20" comes from the
   single-stage scaling the same section rejects two paragraphs earlier; the plan
   states the correct answer itself at :1537 ("southern_realms (17) become
   floor-bound"). At 17: Estalia 5 + Tilea 4 + Border Princes 6 + Skavenblight +
   Sartosa = exactly 17, ZERO remaining for the Border Princes' internal
   mountains (the requirement explicitly says "excluding the internal mountains")
   or the Estalian coast.

2. THE GUARD CANNOT FIRE. The edge case at :1752 detects "a sub-region minimum
   EXCEEDING its region's quota". 17 <= 17 does not exceed, so it stays silent
   while a user requirement is discarded. Change to >= with stated slack, e.g.
   quota >= sum(sub_mins) + forced_in_region + 2.

3. THE 66.6% CRITERION IS UNQUANTIFIED AND POSSIBLY VACUOUS. :1783 reads "land
   bound to a named region is materially above today's 66.6%" - passable at 68%.
   Worse, if the outer_world catch-all counts as "a named region" the metric is
   100% by construction. Split it into two numbers: land bound to one of the 17
   (EXCLUDING the catch-all) >= a stated figure, and catch-all area <= a stated
   cap. Panel suggestions ranged 85-88% bound and ~10% / ~66 states capped.

4. THE CATCH-ALL HAS NO CEILING. :1534 makes it "area-proportional" with no cap.
   The plan works its example at 20% (132 of 660) but today's measured unclaimed
   land is 33.4%, which gives ~220 - more states than the entire named Old World
   combined (Empire 48 + Bretonnia 15 + Kislev 13 + Athel Loren 5 + Southern
   Realms 17 = 98), over territory with no boundary source at all.

5. UNSTATED: does a forced state count toward a SUB-REGION minimum? Lock
   bookkeeping (:1591) covers region quotas only. Skavenblight and Sartosa sit in
   Tilea / Border Princes territory. If they count, Southern Realms has 2 spare;
   if not, 0. That is the entire slack on the tightest budget in the plan. Pin it
   in the schema.

Remedy direction: either raise southern_realms.min_states with the user, or
constrain the bisected catch-all share so no region lands floor-bound at zero
slack. Do not build on the "clears by three" claim.
```

---

## 3 — Forced-state anchors: six of eleven have no source (BLOCK)

Covers: the six unsourced anchors, plus Albion's missing parent region.

```
/request Six of S3a-2's eleven forced single states have no anchor source, while
the plan makes the anchor field mandatory - so a build either invents them or
stalls on its own gate.

Plan step 1 (planning/requests/world-map-source-driven.md:1650-1652) specifies
forced_states as "11 entries, each {name, region, anchor_source, anchor,
label_read}", and user decision 3 (:1526-1528) fixes the mechanism as "picked by
the build from the primary map's own printed place names". But the plan's own
measurement at :1500-1503 lists exactly FIVE printed names: Massif Orcal,
Laurelorn, Oak of Ages, Skavenblight, Sartosa.

Unaccounted: Middle Mountains, the Moot, Albion, and the three Great Bastion
states. The self-gate at :1781 asserts "all 11 forced states exist, each exactly
one cell containing its anchor". Inventing six anchors would violate the
CLAUDE.md non-negotiable against invented content.

The Great Bastion is the sharpest case: :1749-1751 says it "is a wall, not a cell
- its three states must be cut from the border cells along Cathay's northern
frontier rather than claimed from the traced network", which is unspecified work
deferred to the review gate. 27% of the forced-state deliverable is either
unsatisfiable by the stated gate or satisfied by something the plan never
describes. Note the loremaster verified the Bastion's PLACEMENT is canon-correct
(drawn as an east-west wall between Hsingchu/Nan-Gau/Nan-Kuo and the steppe camps)
but that the three-way split is a Total War subdivision - the tabletop draws one
Bastion. Record that provenance rather than letting it read as tabletop canon.

ALBION HAS NO PARENT REGION AT ALL. tools/regions/named_regions.json:51 lists it
as "Albion (an island)" while every other forced state names one ("in
Bretonnia", "all in the Empire", "both in the Southern Realms", "in Athel Loren",
"in Cathay"). The schema requires `region`, and lock bookkeeping charges a locked
cell toward its region's quota - with no region it charges nothing. The loremaster
found Albion IS drawn on the named map, as a separate closed loop west of the
Norsca mainland, i.e. in the norsca class - but regions are claimed by anchor,
norsca has one anchor at [761,222] inside the mainland loop, and per-loop anchors
are added only for `islands`. As written Albion falls to outer_world.

Deliver: measure whether the six names are printed on total_war_map_colored.png or
any registered source; name an explicit second locator for those that are not (the
two-line-weight fallback at :1511-1515, or user-supplied positions for exactly
those six); specify the Great Bastion cut or move it to S3b and drop the count to
8; and pin Albion's region.
```

---

## 4 — Region roster: Nehekhara absent, Araby contradictory (CONCERN, loremaster)

```
/request The S3a-2 named-region roster has a canon gap and an internal
contradiction, both in tools/regions/named_regions.json and the plan at
planning/requests/world-map-source-driven.md:1395-1806.

1. NEHEKHARA APPEARS NOWHERE. Not as a region, not as a sub-region, not as a
   forced state. The `southlands` contour swallows the Land of the Dead - Khemri,
   Lahmia, Zandri, the Tomb Kings - into one region with the jungle Southlands.
   The loremaster's point: Nehekhara is a DEAD land, the single most distinctive
   polity at that latitude and a culture that must not be adapted as an ordinary
   developing market. Folding it into "Southlands" makes it invisible to every
   downstream system. Minimum remedy: record it as a named sub-region of
   southlands with a minimum, using the same mechanism already planned for
   Estalia / Tilea / Border Princes / Crater of Zharr.

2. ARABY IS RECORDED TWO WAYS. The plan at :1532 says the catch-all "holds Ind,
   Khuresh, Nippon, Araby and the Eastern Steppes". The loremaster cropped the
   named map at source (480,930)-(1150,1250) and found the black `Southlands (54)`
   contour visibly enclosing the whole north-western bulge - the Araby peninsula -
   and running east along its northern coast. One record is wrong, and the
   two-stage budget (132 + 528 = 660) rests on which. Resolve it in writing.
   Araby's living sultanates (Copher, Lashiek, Al-Haikk, Martek) are a separate
   question from Nehekhara's dead cities; consider whether either deserves its own
   named region rather than sub-region status.

3. RELATED, RECORDED NOT BLOCKING: `badlands_and_mountains` at min_states 40
   absorbs the entire World's Edge Mountains - the Karaz Ankor (Karaz-a-Karak,
   Karak Eight Peaks, Zhufbar, Barak Varr, Karak Kadrin, Peak Pass) - alongside
   the greenskin Badlands, giving the Dwarf realm no legible strategic identity.
   A `world_s_edge` sub-region with a minimum costs the same as the four already
   planned.

4. ALSO: `islands` and `badlands_and_mountains` are non-canon coinages that
   S3a-2 bakes into ~46 provisional STATE_<REGION>_NNNN identifiers (plus ~132
   under outer_world). Canon naming is deferred to S6 by settled decision, so this
   is not a violation - but identifiers stick, and `islands` names nothing: the
   plan itself measures its anchor sitting in open sea outside all eight loops
   (:1456), so nothing in the repo records WHICH islands it means. Worth resolving
   the eight loops to actual places before the name freezes.
```

---

## 5 — Inter-region density proportionality (CONCERN, geographer + cartographer)

```
/request S3a-2 has no check that state density is proportionate BETWEEN
neighbouring regions, and two panelists found it failing in opposite directions.
The plan's check_proportions() (planning/requests/world-map-source-driven.md:1662)
is framed only as a LEAK detector - area too large for the printed count - and
catches neither case.

1. TOO FINE. The geographer measured Ulthuan as one clean 96,447 px component
   (x 2551-3008, y 796-1247) against min_states 25 and a TW3-proportional 32,
   giving 3,014-3,858 px per state against the world mean of 12,517 - subdivided
   3.2-4.2x finer than everywhere else.

2. TOO COARSE, AT THE WORST POSSIBLE BORDER. The cartographer measured Bretonnia
   floor-bound at 15 against the Empire at ~49, a roughly 5:1 mean state area step
   (~2.2x linear) running down the most-scrutinised border on the map - the exact
   region whose density the user complained about by name in the S3a rejection.

Neither is caught by any reported metric. Deliver: have check_proportions() report
implied and achieved mean state area per region against the global mean in BOTH
directions, surface any region below ~0.5x or above ~2x, and flag any adjacent
pair whose mean areas differ by more than ~2.5:1 - all in COVERAGE.md before the
review gate, so the user rules on it rather than discovering it in the render.

Related, from the game-designer: the Northern Chaos Wastes receives ~46 states
against the Empire's ~48, because TW3 prints 48 settlements there for a battle
game. That is ~7% of the world's state budget, 26 above the user's own floor of
20, spent where Victoria 3 has no economic loop and settled decision #13 makes the
inner band impassable anyway. Nobody chose 46 - it fell out of an uncapped
multiplier. Consider capping regions whose floor sits far below their TW3 share
(both Chaos Wastes; arguably naggaroth 40->53 and mountains_of_mourn 14->18) at or
near their floor, and returning the recovered ~30 states to the Old World, which
is where the plan measures its tightest squeeze. Settled decision #7 fixes
TW3-proportional as the METHOD; this is about capping the surplus, not replacing
the method.
```

---

## 6 — Vanilla reference counts are wrong in committed code and docs (CONCERN)

```
/issue Two vanilla figures the map pipeline anchors its arithmetic on are wrong,
measured by two panelists independently against the supported 1.13.9 install
(launcher/launcher-settings.json rawVersion "1.13.9").

1. STATE COUNT. Vanilla game/map_data/state_regions/*.txt contains 675 land + 106
   sea = 781 state blocks (regex ^STATE_[A-Z_0-9]+\s*=\s*\{ at column 0, no
   duplicates). The repo records 659 land + 103 sea, and
   tools/generate_state_labels.py:67 hardcodes TARGET_LAND_STATES = 659 -
   described in tools/derived/COVERAGE.md:10-11 as "vanilla's own count". The
   error is 2.4% on mean state area; the 600-700 band absorbs it, but the figure
   is quoted as measured fact throughout the plan of record and is wrong.

2. STRATEGIC REGION COUNT. Vanilla game/common/strategic_regions/ contains 36 LAND
   strategic regions across 6 files (african 6, east_asia 7, europe 7,
   north_america 5, south_america 4, west_south_asia 7) plus 105 water in a 7th.
   planning/requests/world-map-source-driven.md:1055 states "Vanilla has 47 land
   strategic regions across 7 files". 47 is in fact the number of STATE_ ids
   inside region_southern_europe, vanilla's LARGEST land strategic region - a
   plausible transcription slip. This one is a 30% error and it distorts any
   argument about how coarse our 18-region grouping is.

Both were measured independently by the vic3-modding-expert and (for the SR count)
the game-designer. Re-verify, then correct TARGET_LAND_STATES, COVERAGE.md's
target line, and the plan text at :1055 - and check whether any other arithmetic
in the plan of record was derived from either figure.
```

---

## 7 — `named_regions.json` has no schema loader and no authoring command (CONCERN)

```
/request The committed file the whole S3a-2 milestone rests on gets no validation
and no defined authoring path.

1. NO LOADER. tools/regions/named_regions.json is committed (git ls-files
   tools/regions) but NO Python under tools/ reads it - a grep for
   "named_regions" across tools/**/*.py returns nothing. S3a-2 step 1 roughly
   triples its content: contour_palette, per-region contour_colours / anchors /
   seals / close_radius, catch_all, budget, allocation, 11 forced_states, 4
   sub_regions. Steps 1-10 never mention tools/worldgen/schema.py. Every other
   committed input in this pipeline has a typed loader with cross-checks -
   load_registration_file (schema.py:697), load_elevation_lut (:761),
   load_state_file (:409), _cross_check (:473). Without one, a contour_colours
   entry naming a palette class that does not exist, or a typo'd region name in a
   forced_states or sub_regions entry, surfaces as a KeyError deep inside
   extraction or - worse - as a silently empty region.

   Deliver load_named_regions() in schema.py with cross-checks: every
   contour_colours class exists in contour_palette; every forced_states.region and
   sub_regions.region names a declared region; sum(min_states) +
   catch_all.min_states <= budget.max.

2. THE BUILD WRITES ITS OWN COMMITTED INPUT. User decision 3 (:1526-1528) has the
   BUILD pick the forced-state anchors, and step 1 stores them in
   named_regions.json - a hand-authored committed file. Same for contour_palette,
   "sampled from the image and committed, never guessed" (:1599-1600). No
   authoring command is named for either. This contradicts the discipline
   .claude/rules/testing.md makes explicit for every other committed input:
   "python tools/worldgen/sources.py --update-manifest ... never a side effect of a
   generator run", and likewise fit_registration.py --seed. It also hollows out
   the gate's own "byte-identical re-run of generate_state_labels.py" (:1773),
   which only means something if the generator's inputs are frozen.

   Deliver: a named authoring command (e.g. tools/pick_anchors.py --write /
   --sample-palette), and an explicit statement that generate_state_labels.py
   READS named_regions.json and never writes it.

3. WHILE HERE - two byte-reproducibility risks the vic3-modding-expert flagged in
   step 5, which changes merge ordering: the single canvas pass replacing "18
   masked passes" (:1677) must iterate regions in SORTED id order, not dict/set
   insertion order; and _farthest_seeds (tools/worldgen/cells.py:380) inside
   split_large must stay tie-break-stable when a lock removes candidates. Note
   this is reproducibility, NOT MP determinism - nothing under tools/ is read by
   the game, and the committed bitmaps are the MP source of truth, so no desync is
   reachable here.
```

---

## 8 — Region extraction robustness: silent losses (CONCERN, geographer + cartographer)

```
/request Two ways S3a-2's region extraction can silently produce a wrong answer,
neither covered by its stated checks.

1. ENCLOSED INLAND WATER SPLITS A REGION, AND THE ORPHAN LOBE VANISHES. S3a-2
   makes the barrier "strokes UNION sea UNION outside-footprint"
   (planning/requests/world-map-source-driven.md:1611-1614), and sea includes
   enclosed inland water. The geographer labelled the committed mask and found 7
   water bodies, 6 of them ENCLOSED - the largest 12,778 px at x 4078-4253 /
   y 1088-1245 and 5,284 px at x 6541-6640 / y 1935-2066, both interior to the
   5.79M px mega-continent. An inland sea of that size severs a region into two
   complement components, only one of which holds an anchor. The plan hard-errors
   on TWO ANCHORS IN ONE COMPONENT (:1616-1621) but is silent on ONE REGION, TWO
   COMPONENTS, ONE ANCHOR - the unclaimed lobe silently falls to outer_world.
   That is precisely the class of silent mis-grouping that made S3a's layer
   unusable. Require extract() to report every unclaimed complement component
   above some area with its bounding box, and fail rather than dropping it.

2. split_at_group IMPORTS A BORDER FROM A DIFFERENT WARP, UNREPORTED. The Design
   section (:1630-1636) says cells take their region by PIXEL MAJORITY, absorbing
   drift smaller than a cell; the Edge Cases and step 5 (:1741-1743) say cells
   straddling a region border are CUT at it so counts are exact. Those are
   different mechanisms with different visual consequences. A cut imports the IE
   frame's region raster border - a line from a different warp than the one the
   cells came from (total_war_map_colored.png, its own 80-point warp, IoU 0.6617) -
   directly into the map as a STATE border that is drawn on no source. The plan
   reports the thin-majority (<60%) fraction, which measures the assignment path,
   but reports NO count of cells cut and no size distribution of the resulting
   fragments. Report both in COVERAGE.md and gate fragments against the relative
   sliver threshold.
```

---

## 9 — The review-gate artifact cannot show what it is meant to gate (CONCERN, cartographer)

```
/request S3a-2's review gate is the user inspecting
tools/derived/qa_state_labels.png, and that artifact cannot show the milestone's
headline deliverables.

Measured by the cartographer: tools/qa_overlay.py:42 sets STEP = 8 and :107-108
decimates via labels[::step, ::step], so the review artifact is a 1024x452
rendering of an 8192x3616 canvas. At that scale the mean land state is 14x14
preview px, the smallest committed cell is 3.2 preview px, and the magenta
coastline overlay is 1 preview px = 8 canvas px thick - which is why every coast
in the current render is smothered in a magenta rim eating a quarter of each
coastal state's visible area. Decimation also FRAGMENTS the coastline: 38 land
components at full resolution become 86 at step 8.

S3a-2's deliverables are eleven forced SINGLE states - Sartosa and Albion are
small islands - and an "Islands" region of eight small loops. None are reviewable
at 3-14 preview px under a magenta rim.

Separately: plan step 8 (:1695-1697) asks the overlay to "print region name +
achieved/quota", but qa_overlay.py contains NO text facility at all - grep for
font|ImageDraw|text returns only the --step flag and comments. It is pure numpy
array writes through raster.write_rgb_png.

This matters more than usual because this project has already shipped a milestone
where every machine check passed while the rendered map was unusable, and because
the vic3-modding-expert explicitly named this artifact the one thing it could not
judge from its own lane.

Deliver: pin STEP at 2 or 4 for the label overlay (or emit additional
per-region native-resolution crops); reconsider the magenta coastal rim weight;
and either add the text facility or move the achieved/quota table entirely into
COVERAGE.md.
```

---

## 10 — S3a-2 forecloses two S3b choices (CONCERN, game-designer + vic3-modding-expert)

```
/request Two S3b consequences that S3a-2 bakes in and cannot be fixed later
without redoing the binding.

1. NAMED REGION == STRATEGIC REGION GIVES 18 AGAINST VANILLA'S 36. The plan makes
   them identical (planning/requests/world-map-source-driven.md:1742-1743, "no
   state spans two strategic regions in S3b"; settled decision #6, "Nippon and the
   Eastern Steppes share a strategic region"). Measured on the 1.13.9 install by
   two panelists: vanilla has 36 land strategic regions, mean 18.8 states, max 47
   (region_southern_europe), then region_balkans 36, region_western_europe 33,
   region_central_america 30. The S3a-2 allocation puts naggaroth at 53, lustria
   54, badlands 54, the_empire ~49 - each at or above vanilla's maximum - and
   outer_world at 132, which is 2.8x it. Strategic regions drive the player's
   map-mode grouping and the AI's theatre/front evaluation.

   Nothing in the user's requirements demands 18; the requirement is per-region
   STATE MINIMUMS. Remedy: state in the plan that a named region is a QUOTA GROUP,
   not necessarily a strategic region, so S3b is free to sub-partition (Cathay ->
   north/south, outer_world -> Ind / Nippon / Araby / Eastern Steppes).
   split_at_group still works; it just stops implying the S3b partition.

   UNVERIFIED and worth settling: whether the engine imposes any hard cap on
   states per strategic region. Strategic regions are a common/ database so
   docs/*.log has nothing to say. Check
   game/map_data/state_regions/strategic_regions.md, or author a test SR with >47
   states in a scratch mod and check logs/error.log.

2. THE PROVISIONAL KEY IS THE IDENTIFIER, SO S6's RENAME IS A MULTI-FILE ATOMIC
   EDIT. :1685 makes the provisional key STATE_<REGION>_NNNN. Verified in the
   install that the state-region block name IS the loc key - STATE_NORTH_SEA = {
   at game/map_data/state_regions/99_seas.txt:99 and STATE_NORTH_SEA: "North Sea"
   at game/localization/english/map/seas_l_english.yml:19. So the provisional key
   gets written into map_data/state_regions/, into common/strategic_regions/
   states = { } lists, and into common/history/states/, and S6 must rewrite it in
   all of them at once.

   Cheap mitigation available NOW: vanilla's stable handle is the numeric id = N
   (99_seas.txt:100; id = 1 on STATE_SVEALAND in 00_west_europe.txt). Emit and pin
   that id in state_labels_index.json during S3a-2, so S6's rename becomes a
   name-and-loc change against a stable id rather than a graph rewrite.

   UNVERIFIED: whether Vic3 supports any state-region rename/alias mechanism that
   would soften this. Check state_regions.md and the vanilla install for an
   alias / replace / old_name key.
```

---

## 11 — Open questions

Not work items. These are the panel's two live disagreements, plus the items no
panelist could verify. The synthesiser ruled on the disagreements; both rulings
are advisory and the user is the final gate.

### Disagreements the panel did not resolve among itself

**Q1 — How should sub-regions (Estalia, Tilea, Border Princes, Crater of Zharr)
be located?**

- *game-designer*: drop `tools/worldgen/legend.py` entirely. A new module plus
  fixture goldens to place 25 states (3.8% of the budget), when the plan itself
  concedes dots are "a locator, not a density driver" (Cathay has 12 dots against
  a 40-state minimum) and that "the requirement is a count, not a geometry; a
  count is met by splitting an existing cell and needs only a footprint"
  (:1571). Four hand-authored footprint boxes in `named_regions.json` satisfy the
  same requirement with zero new code and are directly hand-checkable, which a dot
  detector is not. The plan already has an authored source-px primitive for this
  class of problem — `seals` (:1645).
- *loremaster*: keep the dots, but only as a **seed**, then bound each sub-region
  by the drawn cell network — because the 24 legend swatches are **faction
  ownership colours, not geographic labels**. Chaos Dwarf holdings extend across
  the Darklands well beyond the caldera; the Crater of Zharr is a specific
  volcanic caldera around Zharr-Naggrund, not "wherever Chaos Dwarfs live". Same
  defect hits Border Princes (many settlements greenskin- or undead-held, so
  faction dots under-select) and Estalia (canonically not a unified state at all).
- **Synthesiser's ruling**: authored footprints; drop `legend.py`. The loremaster's
  canon objection is the stronger argument *for* the game-designer's remedy — if
  faction ownership does not delineate the place, seeding from it buys little a
  hand-checkable box does not. **Open for the user to overrule.**

**Q2 — Fix the polar fringe first, or descope the Chaos Wastes quotas and build
S3a-2 now?**

- All five panelists offered the same two options and none chose between them.
- **Synthesiser's ruling**: fix first — for two reasons no single panelist could
  weigh. The fix rewrites `land_sea_mask.png`, the raster every S3a-2 region
  border is cut from, so building first makes both polar bands provably throwaway;
  and the loremaster's finding that the already-registered
  `total_war_map_colored.png` draws the northern Wastes fully provinced means the
  issue's "register a polar source" option may already be largely paid for, which
  materially lowers the cost of fixing first. **Open for the user to overrule.**

### Unverified — nobody on the panel could confirm these

- Whether Victoria 3 imposes a **hard limit on states per strategic region**.
  Bears on the 132-state `outer_world`. Not in `docs/*.log` (strategic regions are
  a `common/` database).
- Whether Vic3 supports any **state-region rename/alias mechanism**, which would
  soften S6's identifier rewrite.
- Whether the six unlabelled forced states (Middle Mountains, the Moot, Albion,
  ×3 Great Bastion) are **printed anywhere** on `total_war_map_colored.png` or
  another registered source.
- Whether region-aware reconciliation stays **byte-reproducible across Python
  versions**. Only same-machine re-runs are gated today. (Reproducibility, not MP
  determinism — the latter is not at risk.)
- Whether **675 land + 106 sea** is the correct 1.13.9 figure, or whether the
  panel's regex count included blocks vanilla comments out at load.

### Recorded, deliberately not acted on

- `total_war_map_colored.png`'s clean-cell count is on record two ways — the plan
  and `world-map-s3a2-handoff.md:18` say **748**, `tools/SOURCES.md:92` says **681
  clean closed cells**. Three panelists judged it not load-bearing (S3a-2 drives
  density from per-region quotas, not source cell count; the current run traces
  1,860 cells before filling). All three said the same thing: do not let step 10's
  `SOURCES.md` edit resolve it silently to whichever number is convenient.
- The loremaster read **"Moussillon"** off the primary source where canon is
  **Mousillon**, and self-flagged it as unverified against a GW publication. The
  broader point is certain: that map interleaves canon toponyms (Altdorf, Nuln,
  Marienburg, Quenelles, Magritta, Karak Izor) with TW-invented settlement names
  (Grung Zint, Fester Spike, Blackclaw Lair). State in the schema that `label_read`
  is provenance-only and never becomes a localization string.
- `.metadata/metadata.json` has empty `id`, `version`, `short_description` and
  `tags`. The vic3-modding-expert checked this against a working shipped local mod
  (`mod/BNW/`) with identical empty fields that loads. **Not a finding** — recorded
  so it is not raised as one later.
