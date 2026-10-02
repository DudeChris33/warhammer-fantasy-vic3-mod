# Fixture: starting-country data linter

Synthetic miniature of the game data `mapgen/validate_country_history.py` reads (4 law groups, 9 laws, 4 IGs, 4 techs, tier helpers 1–3, 6 government types, 5 country definitions) plus a fixture tag registry and four region files:

| File | Exercises |
|---|---|
| `data/00_test.json` | The valid path: baseline, a `profile` with an election, tag overrides with `justify`, an `extra_techs` prerequisite chain, and the "government trigger not evaluable without a country definition" warning (FXC) |
| `data/01_bad.json` | Every tag-level error class: unknown ids, several laws in a group, locked laws (by tech and by `unlocking_laws`), disallowed pairs, extra-tech prerequisites, wrong government type, formable/unregistered/wrong-region/missing tags, malformed elections, `justify` bookkeeping |
| `data/02_bad_baseline.json` | Baseline errors: missing law group, unknown tier, empty `ruling_igs`, missing `why` |
| `data/03_dupe_key.json` | A duplicate JSON key |

`expected/report.txt` is the committed golden validator report (byte-for-byte, `-text` in `.gitattributes`). `run_fixture.py --check` fails if the report drifts, if the run is not deterministic, if any error class in `COUNTRY_HISTORY_NEEDLES` stops being reported, or if `00_test.json` is rejected. After an intentional linter change: `python mapgen/run_fixture.py --update-country-history`, then review the diff.
