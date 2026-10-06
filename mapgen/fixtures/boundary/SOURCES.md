# Boundary fixture source manifest

Stands in for `mapgen/SOURCES.md` when the S3a boundary fixture runs. Same format,
same parser, same SHA-256 guard — so `--check` exercises the real verification
path rather than a stub of it.

Unlike the real manifest, the files it pins **are** committed: they are our own
invented pixels (see `make_source.py`), so there is no bulk of PNGs to keep out
of the repo and the fixture runs on a clean clone with no `sources/` present.

If `make_source.py` is re-run, this manifest must be refreshed:

```
python mapgen/fixtures/boundary/make_source.py
python mapgen/run_fixture.py --update-fixture-manifest
python mapgen/run_fixture.py --update
```

<!-- MANIFEST:BEGIN -->
| File | Dims | Bytes | SHA-256 | Origin | Role | Registered |
|---|---|---|---|---|---|---|
| synthetic_parchment.png | 320x240 | 9,781 | a9fd0b81776016ce2e46a54d001aae4ed24874e6e2721a847a17e0a94fdd1f19 | Invented for this fixture by make_source.py | Synthetic boundary-network source (frame master) | yes |
| synthetic_parchment_crop.png | 320x240 | 5,267 | 2f4777180afcdb837085e9b3b171549b1c7cc3e83e7345ae5851feb8c7d43459 | Invented for this fixture by make_source.py | Alpha-masked region crop — exercises the src_valid / alpha-footprint path | yes |
| synthetic_parchment_half.png | 160x120 | 3,718 | bc36b5ff38f688f96b804bf5bb541278d1e06b221744e6743873686c522c0faf | Invented for this fixture by make_source.py | Half-scale sibling — exercises the frame_alias path | yes |
<!-- MANIFEST:END -->
