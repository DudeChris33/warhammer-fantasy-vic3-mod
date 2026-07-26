# S3a-2 handoff — prompt for the re-planning session

Paste the block below to start the re-plan. Everything it references is committed.

---

```
/plan planning/requests/world-map-source-driven.md

Re-plan S3a as S3a-2. S3a's offline gate passes but I rejected its visual review,
and my per-region requirements turned out to need something the milestone was
never scoped for. Read the "S3a — post-review rework (2026-07-25), REVIEW GATE NOT
PASSED" section of the plan of record first — the diagnosis is already measured
there, don't re-derive it.

State of play: the swirl / density / spike bugs are FIXED and committed (c6849a4);
the primary boundary source is now total_war_map_colored.png (flat-fill ocean =
exact silhouette, 748 clean cells, fitted IoU 0.6617); current output is 613 land
+ 108 sea cells and looks correct. Name binding is committed (601be43) in
tools/regions/named_regions.json.

The blocker, already measured: the macro grouping does not correspond to my 17
named regions. Five macros are each claimed by 2-3 regions (Naggaroth+Ulthuan,
Norsca+Empire, Badlands+Southlands, Mountains of Mourn+Islands, N.Chaos
Wastes+Bretonnia+Southern Realms), so per-region quotas cannot be enforced on it.

What S3a-2 has to deliver:
1. Replace the macro layer with contours extracted from
   total_war_states_per_strat_region.jpg, which names its 17 regions. First pass
   gets 11/17; the misses are label text crossing a contour and breaking the loop.
2. Bind every cell to a named region (anchors are already authored and resolve to
   sub-pixel accuracy).
3. Drive density reconciliation from per-region min_states rather than one global
   number, honouring 600-700 land states in total.
4. Forced single states: Massif Orcal, Laurelorn Forest, Middle Mountains, the
   Moot, Skavenblight, Sartosa, Albion, Oak of Ages, and three for the Great
   Bastion. These need sub-region anchors — propose how to place them and which
   ones you want me to sanity-check, rather than guessing.
5. Sub-region quotas inside a macro: Estalia >=5, Tilea >=4, Border Princes >=6
   (excluding internal mountains), Crater of Zharr >=10 ideally matching the Old
   World mod map.

Out of scope for S3a-2, confirm you agree: navigable rivers (Ruin, Reik, Talabec,
Stir, Lynsk, Cathay's main rivers) and their strait crossings are S3b
adjacencies.csv + S6 strait_definitions.

Open questions I want the plan to answer, not assume:
- Is per-region quota enforcement a change to the reconciliation step only, or
  does it need the cell extraction to run per region?
- Whether the Old World mod map is worth registering for Crater of Zharr density,
  given it has no exact silhouette.
- How a forced single state survives the merge/split passes without distorting
  its neighbours.
```

---

## Why this needs a re-plan rather than another `/build`

S3a was scoped as *"produce a committed state-label layer that tiles the mask at
vanilla-order granularity"*. It does that. The requirements list changes the
acceptance test to *"...and satisfies per-named-region minimums, with specific
named places as their own states"*, which needs name→geometry binding as a
**prerequisite** — inverting the plan's ordering, where canon naming is S6.

That is a change of milestone shape, not a defect in the build.

## Things not to re-derive (all measured this session)

| Fact | Value |
|---|---|
| Warp anisotropy caused the swirls | median 2.63, p90 6.85, p99 20.1, max 394 — now bounded at 3.0 |
| IoU alone is an insufficient objective | it scores silhouette overlap, not whether interior borders survive the warp |
| Traced cells are finer than a vanilla state | median warped source cell 3,648 px vs a 12,517 px target |
| Sliver pruning must be relative to the cell | an absolute threshold near the target deletes the network itself |
| TW3's own state distribution | 554 across 17 regions — proportions reference only, not truth |
| Macro/name mismatch | 5 macros claimed by 2–3 named regions each |
| Named-map contour extraction | 11 of 17 on a first pass; gaps are label text crossing contours |
| Anchor resolution accuracy | 0.3–1.1 px through the committed warp; must snap to nearest land afterwards |
