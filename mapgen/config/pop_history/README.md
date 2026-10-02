# Starting-population inputs (`mapgen/config/pop_history/`)

Hand-authored input for `python mapgen/generate_pop_history.py`, which writes `common/history/pops/NN_*.txt` and `common/history/population/NN_*.txt` (generated: never hand-edit them). Review the numbers here, regenerate, then `--check`.

## Scale factor

**game total = canon-scale figure × 5** (`scale_factor` in `calibration.json`).

- Tabletop Warhammer gives settlements and realms medieval-sized populations (a great city in the low hundred-thousands, an Empire province in the hundreds of thousands) and is inconsistent between editions. Vanilla Victoria 3 is balanced for 1836 Earth, where one state holds hundreds of thousands to millions and the economy, buildings and pop-type ratios assume that scale.
- Multiplying canon-scale figures by 5 puts an Imperial province at roughly 1–3 million and the Old World at about 52 million, so a typical state lands around 150–700k, in vanilla's band, while every realm keeps its canon *rank* (Reikland > Wissenland > Middenland > the north-eastern provinces; Bretonnia a dense Empire-scale peasantry; Kislev, Norsca and the Border Princes thin).
- The canon-scale figures themselves are **inferred from canon rank**, not quoted from a book: no tabletop source gives a population per realm that this repo can cite, and the exact city figures vary by edition and could not be checked from this environment. Each entry's `source` says `inferred: <what the rank rests on>`. Change `scale_factor` to rescale everything at once.

## Files

| File | Holds |
|---|---|
| `calibration.json` | `scale_factor`, `min_pop_size`, and per start tag `canon` (people at canon scale), `source`, `why`, `confidence`. `groups: [{tags, canon, ...}]` give each listed tag the same figure. A tag that owns a state with no entry is a hard error. |
| `distribution.json` | How a tag's total spreads over its states: weight = (arable heatmap mass + `floor_permille`/1000 × area) × (1 + `city_boost` × named city hubs + `canon_city_boost` × canon cities) × `multiplier`. `overrides[]` (`key` + `anchor`, one of `multiplier` / `share`, `source`, `why`; `tag` when a state is split) change one state; `share` fixes its fraction of the tag total. |
| `state_weights.json` | **Derived** by `generate_pop_history.py --refresh-weights` (needs numpy/Pillow) from `map_data/provinces.png`, `mapgen/derived/arable_heatmap.png` (read `arable_lore.json` for what the heatmap means), `hub_worksheet.json` and `canon_cities.json`. Re-run after a province regen. Integers only, so the generator is exact. |
| `state_overrides.json` | `tags{TAG: {mix}}` a tag-wide default mix (shares sum to exactly 100); `states[]` (`key` + `anchor`, `tag` when split, `mode`, `mix`). Mix entries: `culture`, `share` (percent), optional `religion` (only when not the culture's default; one equal to the default is folded away), optional `pop_type` (deliberate only; `slaves` needs the owner's `lawgroup_slavery` ≠ `law_slavery_banned` in `country_history/`), `source`, `why`. `mode: "add"` carves minorities (sum above 0, below 100) out of the default; `mode: "replace"` is the whole mix (sum exactly 100). |
| `population.json` | Per tag `wealth` (`very_high high medium low`) and `literacy` (`very_high high middling low very_low baseline`), `source`, `why`. The generator warns when a literacy level is outside the usual band for the tag's tech tier in `country_history/`. |

**Default mix** for a state with no override: the state's homelands (`add_homeland` in `common/history/states`, themselves derived from the owner's `cultures`), the owner's primary cultures counting double.

Per-state keys are the canon `STATE_<NAME>` plus `anchor` (the `naming_anchor` in `state_ownership.json`); a key that no longer exists, or an anchor that moved, is a hard error, so a repaint or rename cannot silently re-target an override.

## Generator rules (see `mapgen/worldgen/pop_history.py`)

- Exact integers by largest remainder: a tag's states sum to its total; a state's pops plus skipped plus dropped pops sum to its allotment.
- Only (state, owner) pairs that `common/history/states` creates are emitted. Owners without a country definition are skipped and reported.
- A culture, religion or pop type not defined in this mod (the distant regions' cultures, e.g. `high_elf`) is skipped and reported, never emitted.
- A pop under `min_pop_size` is dropped and reported.
- The generator prints every skip and drop; `--report-md PATH` writes the review tables (calibration, top states, overrides, wealth/literacy).
