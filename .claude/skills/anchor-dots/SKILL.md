---
name: anchor-dots
description: Propose paired anchor dots between any source image and the canvas for Chris to review - precise shared landmarks, leave-one-out fit, disagreement renders and the two flat dot sheets, all in scratchpad/
user-invocable: true
---

`/anchor-dots <source image> [canvas image]` places paired anchor dots between a source map and the canvas (default `sources/originals/terraqueous_globe_reprojected.png`). The output is a review set for Chris: the dot list, two dot sheets, renders and a fit report. It never registers anything. Distilled from the 2026-10-19 run on `warhammer-world-map-8k-cropped.png` (three passes; Chris set the dot standard below). Background: `mapgen/SOURCES.md` (paired-anchor-dot sheets, the `ulthuan/` section) and `.claude/rules/testing.md`.

## What a dot is (Chris, 2026-10-19)

A dot pair says "these two points are meant to be the same place". The maps will disagree; the goal is the best projection we can make, so we can see where and how they disagree. High error at a correct pair is a finding, not a reason to delete it.

Each dot sits **exactly** on one small landmark that you can point to on both maps by its local shape and neighbours:

- the innermost point of a bay beside a recognisable run of coast;
- the tip of a small spit or peninsula, for example the one beside a river mouth;
- a river mouth, a confluence, or a distinctive bump or curve in a river's course (inland);
- the two ends of a lake, not its centre;
- the centre of a matching bend (river or border).

Purely geographic: **never labels, label positions or icons.** A vague pick ("mid west coast", "somewhere on this cape", a lake centre) is not a dot.

Leave a coast undotted when:

- it is hidden by fog, cloud, a label or an icon on either map (don't guess under it);
- the two maps draw it too differently to name one shared point (archipelago mazes, a sea that is open on one map and closed on the other);
- it lies outside the source's extent.

Name these in the report.

## Ground rules

- Never edit an original. Everything goes to `scratchpad/dots/<source stem>/` (gitignored). Never put sheets in `sources/` or touch the manifest: adding sources is Chris's.
- Chris is the visual gate. Iterate autonomously to a set you'd defend, then send the PNGs and wait. Don't commit anything.
- Run in the session's main thread: the work is reading paired crops. Batch pairs and read images rather than delegating.
- If the fit stays poor with good dots, say so and why (projection, stylisation), rather than adding dots until the number looks good.

## Tool

`python .claude/skills/anchor-dots/dots.py <cmd>` with the mapgen venv (`mapgen/.venv/Scripts/python.exe`), from the repo root. Run it with no arguments for the full usage. `--work DIR` picks the work folder; the default is the last one `init` set up.

| Command | Use |
|---|---|
| `init --src PATH [--canvas] [--ora]` | Work folder, source water/coast mask, canvas `coasts` and `rivers` layers from `full.ora`, previews. Check `water_check.png`: red should trace the source coast. If not, tune `water_br` / `water_gr` in `config.json` and re-run `init`. |
| `pair sx0 sy0 sx1 sy1 cx0 cy0 cx1 cy1` | **The main tool.** Source and canvas crops side by side at equal height, with a fine grid labelled in native pixels, the canvas coast (cyan) and rivers (blue) drawn on, and current dots named. |
| `tile sx0 sy0 size` | Source, source warped by the current dots, and canvas. Use once there are ~20 dots, to find where the current fit puts a source feature on the canvas. |
| `water x0 y0 x1 y1` | Source crop with water tinted red: shows rivers under forest and checks the coast classifier. |
| `crop s\|c x0 y0 x1 y1` | One image, gridded. |
| `set name sx sy cx cy [conf] [kind] [--note]` | Add or move a pick (`-` keeps a value). Kind `coast` snaps to the nearest coast pixel (source 4 px, canvas 10 px); `point` stays exact (river, lake end, islet, bend). |
| `del name ...` | Remove picks. |
| `all` | `build` (dots.json, unique flat colours, overlap check), `fit`, `render`, `sheets`. |

Chris can hand-edit `picks.json` and re-run `all`.

## Workflow

1. **Survey.** `init`, then read `src_preview.png` and `canvas_preview.png`. Note the extent (cropped ends, alpha 0), fog and cloud, and labels printed over land, and which landmasses both maps show.
2. **First pass, 3–5 anchors per landmass.** Use unmistakable extremes: island tips, a peninsula's end, a deep bay's head. Find them with `pair` on generous boxes. Pairs must be right more than they must be many: the warp from these places every later crop.
3. **Sweep coast by coast** with `pair`, at about 2–4x on the source. Per crop: name the shared shapes, give each its exact pixel on both grids, then `set`. Re-read with `pair` at higher zoom before committing a pick. Typical density: one dot per 150–250 canvas px of coast.
4. **Islands: match by shape and neighbours, never by nearest position.** Island order is a known trap (Nippon, Dragon Isles). Check each island pair in a zoomed `pair` first. Mark island chains at 3–4 points, or leave them out.
5. **Inland.** Rivers on the canvas come from the `.ora`; on the source, use `water` to find them under forest. Use mouths, confluences and distinctive bends; lakes get a dot at each end. Where the river networks don't clearly match, skip them and say so.
6. **`all`, then read** the fit report (median and p95 leave-one-out, worst dots, folds), `disagreement.png` and `warp_blend.png`. For each of the worst dots, re-open `pair` and decide:
   - the pick is wrong: fix it (the 8k run found four wrong picks this way);
   - the pick is right and the maps disagree: keep it and report it;
   - the landmark is ambiguous: drop it.

   Repeat until the remaining high-error dots are all real disagreements.
7. **Deliver.** Send `disagreement.png`, `warp_blend.png`, `overview_src.png`, `overview_canvas.png`, the `rev_*.png` region pairs and `uncertainty.png`. Report:
   - dot count and leave-one-out median and p95, against the previous pass if there is one;
   - the worst dots, and what each says about where the maps disagree;
   - what was left undotted, and why;
   - the two sheet paths: `<src stem>_dots.png` and `<canvas stem>_dots_<src stem>.png`.

## Reading the numbers

- **Leave-one-out (LOO):** drop one dot, fit the rest, measure in canvas px how far the dropped dot lands from its pick. It mixes pick error with real disagreement between the maps. Picking error from careful picks is about 5 source px.
- **Error grows with distance from the nearest dot**: roughly 0.35–0.45 times that distance in the 8k run. `uncertainty.png` maps this estimate; it is typical, not a bound.
- **Thin-plate vs affine:** thin-plate should beat affine by a lot. If it doesn't, the source's projection is the problem, not the dots.
- **Folds** (the warp flipping over on itself) must be 0. A near-fold at an extreme anisotropy means a wrong pair close by.
- **Interiors stay uncertain** when only the coasts are dotted. In the 8k run, coast dots alone left about 70% of land inside the hull estimated under 100 px of error.

## Sheet convention

Flat exact-RGB discs, 12 px (`dot_px` in `config.json`; scale it with resolution and say so). Each colour is unique per pair, with no antialiasing, drawn on copies. Colours used for markup elsewhere are banned: cyan, magenta, lavender, orange, river blue, city blue, state-merge green, white and black. `sheets` checks that no original pixel already has a dot colour and that every disc has its full pixel count. Dots belong on the outermost coast where they can go, because the warp covers only the convex hull of the dots.
