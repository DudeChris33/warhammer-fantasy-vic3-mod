# Fixture: synthetic ingestion source (S2)

A tiny (256×128) **invented** whole-world image that drives the S2 source-driven
front-end offline, with zero third-party IP and zero game dependency. Because the
pixels are our own, this source **is committed** (unlike the real `sources/`), so
the fixture runs on a clean clone.

It exercises the *same* `worldgen.ingest` core the real generator uses — not a
parallel reimplementation — so a regression in reprojection, LUT classification,
de-inking, despeckling, mask cleanup, or heightmap encoding trips it.

## What it deliberately contains

`make_source.py` paints, using the fixture LUT's own swatch colours:

- a **stepped elevation ramp** (walks every band of `lut.json`);
- two landmasses, one **crossing the x=0 seam** (wrap handling);
- an **inland sea** and a **small island** (lake / island area filters);
- **ink strokes** — a label block + ruled graticule in a dark red close to the
  highest swatch, reproducing the real defect that embossed place names into the
  heightmap as mountains;
- **single-pixel speckle** (majority filter).

## Files

| File | Role |
|---|---|
| `make_source.py` | Regenerates `synthetic_world.png` deterministically. |
| `synthetic_world.png` | The committed source (our pixels). |
| `SOURCES.md` | Fixture manifest — same parser + SHA-256 guard as the real one. |
| `lut.json` | Fixture elevation LUT (invented swatches; carries `ink_rgb`). |
| `registration/synthetic_world.json` | Equirectangular placement edge-to-edge. |
| `expected/` | Byte-exact golden: `land_sea_mask.png`, `heightmap.png`, `ingest_stats.txt`. |

## Commands

```
python mapgen/run_fixture.py --check                    # runs this fixture too (offline gate)
python mapgen/fixtures/ingest/make_source.py            # after changing the synthetic world
python mapgen/run_fixture.py --update-fixture-manifest  # refresh its SHA-256
python mapgen/run_fixture.py --update                   # rewrite the golden (review the diff)
```
