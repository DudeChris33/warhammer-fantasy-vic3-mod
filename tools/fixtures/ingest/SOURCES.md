# Fixture source manifest

Stands in for `tools/SOURCES.md` when the ingestion fixture runs. Same format,
same parser, same SHA-256 guard — so `--check` exercises the real verification
path rather than a stub of it.

Unlike the real manifest, the file it pins **is** committed: `synthetic_world.png`
is our own invented pixels (see `make_source.py`), so there is no third-party IP
to keep out of the repo, and the fixture therefore runs on a clean clone.

If `make_source.py` is re-run, this manifest must be refreshed:

```
python tools/fixtures/ingest/make_source.py
python tools/run_fixture.py --update-fixture-manifest
python tools/run_fixture.py --update
```

<!-- MANIFEST:BEGIN -->
| File | Dims | Bytes | SHA-256 | Origin | Role | Registered |
|---|---|---|---|---|---|---|
| synthetic_world.png | 256x128 | 2,323 | 808b54756f36e3c2401a0905602b1918fdf3fc0984ffdeea687ec89e4137d46f | Invented for this fixture by make_source.py | Synthetic whole-world ingestion source | yes |
<!-- MANIFEST:END -->
