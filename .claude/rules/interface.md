---
paths:
  - "gfx/**/*"
  - "interface/**/*"
  - "gui/**/*"
---

# Interface & Art Rules (`gui/`, `interface/`, `gfx/`)

**Read when:** you are editing `gfx/`, `interface/` or `gui/`. **Covers:** sprite/icon declarations and the inventory of authored `gfx/` override files. Loads automatically when you open a matching file with the Read tool — a starting point, not a boundary: read any other guide that would help, and read a neighbour whenever your work touches its area.

**Related guides:**
- [scripting.md](scripting.md) — the neutralize-don't-delete doctrine and resolve-or-dangle criterion these overrides follow
- [testing.md](testing.md) — `gfx/map/` map-keyed overrides and generated locators
- [heraldry.md](heraldry.md) — coat-of-arms emblem textures

## Organization

- `gui/` — custom widget definitions (`.gui`) that extend or override base-game UI.
- `interface/` — `.gfx` files declaring sprite/icon references used by `gui/` and script (e.g. building/technology icons).
- `gfx/` — the actual art assets, split by type: `flags/`, `interface/icons/`, `loadingscreens/`, `map/`, `models/`, `particles/`, `portraits/`.

## Patterns

- Every icon referenced from `common/` script (e.g. a building or technology icon) needs a corresponding sprite declared in `interface/` pointing at the actual file under `gfx/interface/icons/`.
- Keep new `.gui` files scoped to overriding only the specific window/widget being changed — don't duplicate entire base-game UI files when a partial override will do.

## Forbidden

- No absolute local file paths in `.gui` or `.gfx` files — use mod-relative paths only.
- No orphaned references — every sprite/icon declared must point at a file that actually exists under `gfx/`.

## Authored `gfx/` overrides

`gfx/` is **not** blankable via `replace_paths` (only `common/`, `events/` and `map_data/` are eligible), so vanilla's gfx always merges underneath and this mod's files only override specific vanilla filenames. Never delete an override: that re-exposes vanilla's real-world references and reverts prior fixes. The doctrine itself (criterion, per-family authority table, `always = no # was:`) lives in [scripting.md](scripting.md).

Authored files: `gfx/portraits/portrait_modifiers/01_{accessories,beards,clothes,hairstyles,headgear}.txt` and `gfx/map/city_data/city_types/*` (10). `city_types/*` carry no live real-world refs — the 3–4 landmark buildings (`building_eiffel_tower`, `building_suez_canal`, `building_panama_canal`, `building_victoria_terminus`) were removed and survive only in each file's header comment; read-through only, no edits.
