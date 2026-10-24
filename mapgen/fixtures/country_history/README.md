# Fixture: starting-country data linter

Synthetic miniature of the game data `mapgen/validate_country_history.py` reads (4 law groups, 9 laws, 4 IGs, 4 techs, two starting-technology presets named like the real ones, 6 government types, 6 country definitions on real culture ids) plus `data/starting_tech_extras.json` plus a fixture tag registry and four region files:

| File | Exercises |
|---|---|
| `data/00_test.json` | The valid path: baseline, a `profile` with an election, tag overrides with `justify`, a good extra (`starting_tech_extras.json`), and the "government trigger not evaluable without a country definition" warning (FXC) |
| `data/01_bad.json` | Every tag-level error class: unknown ids, several laws in a group, locked laws (by preset tech and by `unlocking_laws`), disallowed pairs, wrong government type, extras that are unknown, lack a prerequisite or are keyed on a formable, formable/unregistered/wrong-region/missing tags, malformed elections, `justify` bookkeeping |
| `data/02_bad_baseline.json` | Baseline errors: missing law group, stray removed tech fields (`unknown field`), empty `ruling_igs`, missing `why` |
| `data/03_dupe_key.json` | A duplicate JSON key |

`expected/report.txt` is the committed golden validator report (byte-for-byte, `-text` in `.gitattributes`). `run_fixture.py --check` fails if the report drifts, if the run is not deterministic, if any error class in `COUNTRY_HISTORY_NEEDLES` stops being reported, or if `00_test.json` is rejected. After an intentional linter change: `python mapgen/run_fixture.py --update-country-history`, then review the diff.
