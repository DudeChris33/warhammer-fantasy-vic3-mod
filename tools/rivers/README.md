# Rivers (S2)

`map_data/rivers.png` is **derived from the terrain**, not hand-drawn:

```
map_data/heightmap.png + tools/derived/land_sea_mask.png
  -> fill depressions -> D8 flow direction -> flow accumulation   (worldgen/hydro.py)
  -> channels (accum >= threshold), thinned to ~1 px
  -> width ramp by flow + green headwater sources
  -> map_data/rivers.png   (indexed, vanilla palette)
```

Regenerate with:

```
python tools/generate_rivers.py --preview
```

## Why derived

The first S2 attempt hand-authored a dozen polylines. They were sparse and
straight, and bore no relation to the valleys beneath them — the user's verdict
("the rivers map not so much") was correct.

Computing the drainage from the committed heightmap fixes that at the root. The
network meanders through the real terrain, gathers into dendritic basins, and
reaches the coastline **by construction** — river mouths cannot disagree with the
shoreline, because the same land mask produced both. It is also ~30x denser
(85k river pixels vs 2.8k), which is what a world map should look like.

`rivers.json` and the polyline path in `worldgen/rivers.py` are retained: the
schema, the vanilla palette, and the validity rules (1 px width, inland sources,
mouths that connect, contiguous paths) are still the authority on what a legal
`rivers.png` is, and the polyline path is how a hand-corrected watercourse would
be added if one is ever needed.

## Canon naming (S6)

Which channel is the Reik, the Talabec, the Stir — that is the S6 naming pass.
The user annotated `sources/TheEmpireRivers - drawn on.jpg` (canon courses drawn
in red over the GW Empire map) to guide it. That annotation is a **topology
guide**, not geometry: it says which rivers exist and how they connect, while the
courses come from the DEM, so every river follows a real valley regardless of how
precisely the annotated map registers.

Extraction of the annotation is a solved step when S6 needs it: difference the
drawn-on map against the clean `TheEmpireRivers.jpg` (same image, one annotated),
which isolates the strokes and drops the coats of arms — they are bright red in
*both* images, so no colour threshold or shape heuristic is required.

## Tuning

| Knob | Meaning |
|---|---|
| `--threshold N` | Upstream-cell count for a cell to be a channel. Lower = denser. |
| `--step N` | Hydrology downscale vs the canvas. Coarser routing yields the trunk rivers a player sees rather than hair-fine capillaries. |
| `WIDTH_BREAKS` | Accumulation fractions mapping flow to vanilla's blue width ramp. |

The palette is `tools/lut/rivers_palette.json` (vanilla's exact indices, measured
from the shipped file).
