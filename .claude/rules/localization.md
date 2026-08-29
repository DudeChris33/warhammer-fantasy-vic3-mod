# Localization Rules (`localization/`)

## Organization

- `localization/english/` — loc entries for new content this mod adds.
- `localization/replace/english/` — loc entries that override/replace vanilla base-game text. Use this instead of editing base-game files (which aren't part of this repo).
- Every `.yml` loc file must start with `l_english:` on its own line (UTF-8 with BOM, standard Paradox requirement) and use `\tkey:0 "text"` entries.

## Patterns

- Every key referenced by script (event titles/descriptions, decision names, building names, modifier display names, custom localization per `docs/custom_localization.log`) must have a matching loc entry — a missing key shows the raw key string in-game or crashes on some UI lookups.
- Keep loc file names aligned with the script folder/topic they cover (e.g. loc for `common/buildings/` content in a buildings-themed loc file). The first established convention is the culture foundation (#3405): `localization/english/culture_foundation_<area>_l_english.yml`, split by database area — `..._heritages_`, `..._languages_`, `..._religions_` — carrying the display-name keys for the matching `common/discrimination_trait_groups/`, `common/discrimination_traits/` and `common/religions/` entries. Follow that `<topic>_<area>_l_english.yml` shape for later content.

## Forbidden

- No hardcoded personal/local file paths in loc text.
- No editing vanilla loc files directly — use `localization/replace/english/` instead.
