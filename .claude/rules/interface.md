# Interface & Art Rules (`gui/`, `interface/`, `gfx/`)

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
