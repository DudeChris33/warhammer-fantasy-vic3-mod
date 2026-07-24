# River geometry (S2)

`rivers.json` is the committed source for `map_data/rivers.png`: the v1 canon
rivers as ordered **source-first** polylines, one `RiverStream` each (schema in
`tools/worldgen/schema.py`). `tools/generate_rivers.py` rasterizes them over the
committed `land_sea_mask.png` into a Vic3-valid indexed bitmap.

Each stream has a `mouth`:

- `"sea"` — the last pixel reaches open water (the river is trimmed at the first
  sea pixel, so a straight final segment cannot overshoot a concave coast);
- `"confluence"` — the last pixel is marked red and must land on another stream.

`width` is the downstream (widest) index of vanilla's blue ramp `(3, 4, 6, 8)`;
the body ramps up to it from the source. Validity — one green source per stream,
inland sources, mouths that connect, ~1-pixel width (vanilla tolerates a few 2×2
blocks; we cap well under a systematic-fault threshold) — is enforced in
`worldgen.rivers` **before** the PNG is written, so an authoring slip is an
offline error, never an in-game one.

## Provenance

Courses were traced against the reprojected coastline (`land_sea_mask.png`) with
the Empire river system informed by the *Empire of Man* rivers map
(`TheEmpireRivers.jpg`, consulted not warped — see `tools/SOURCES.md`). They are
**best-effort v1** placements (the plan's "good-faith registered tracing, not
survey accuracy"); the S6 naming pass refines courses and names.

## Regenerate

```
python tools/generate_rivers.py --preview   # -> map_data/rivers.png (+ a QA overlay)
```

The palette is `tools/lut/rivers_palette.json` (vanilla's exact indices).
