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
| synthetic_world.png | 256x128 | 1,977 | e1fda3165b0df41bc03392d83040abb05d586f0dc8da39a9900938a6dd369844 | Invented for this fixture by make_source.py | Synthetic whole-world ingestion source | yes |
<!-- MANIFEST:END -->
