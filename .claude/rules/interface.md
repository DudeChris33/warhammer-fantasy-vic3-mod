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
- `gfx/` — the actual art assets, split by type: `coat_of_arms/`, `flags/`, `interface/icons/`, `loadingscreens/`, `map/`, `models/`, `particles/`, `portraits/`.

## Patterns

- Every icon referenced from `common/` script (e.g. a building or technology icon) needs a corresponding sprite declared in `interface/` pointing at the actual file under `gfx/interface/icons/`.
- Keep new `.gui` files scoped to overriding only the specific window/widget being changed — don't duplicate entire base-game UI files when a partial override will do.

## Forbidden

- No absolute local file paths in `.gui` or `.gfx` files — use mod-relative paths only.
- No orphaned references — every sprite/icon declared must point at a file that actually exists under `gfx/`.

## Authored `gfx/` overrides

`gfx/` is **not** blankable via `replace_paths` (only `common/`, `events/` and `map_data/` are eligible), so vanilla's gfx always merges underneath and this mod's files only override specific vanilla filenames. Never delete an override: that re-exposes vanilla's real-world references and reverts prior fixes. The doctrine itself (criterion, per-family authority table, `always = no # was:`) lives in [scripting.md](scripting.md).

Authored files: `gfx/portraits/portrait_modifiers/01_{accessories,beards,clothes,hairstyles,headgear}.txt` (5), `gfx/portraits/portrait_animations/animations.txt`, `gfx/map/front_entities/*` (3) and `gfx/map/city_data/city_types/*` (10). The map-keyed ones under `gfx/map/` (spline network, locators, fortifications) are covered in [testing.md](testing.md). `city_types/*` carry no live real-world refs — the 3–4 landmark buildings (`building_eiffel_tower`, `building_suez_canal`, `building_panama_canal`, `building_victoria_terminus`) were removed and survive only in each file's header comment; read-through only, no edits.

### Currency textures

Money shows as art, not text: every `@money!` in loc resolves (`gui/texticons.gui`) to `gfx/interface/icons/topbar/income_power_icon.dds`. The mod overrides four textures at their **vanilla paths** (no `gui/` or loc change; the mod has no `gui/` folder) so the vanilla £ is replaced by a gold crown:

- `gfx/interface/icons/topbar/income_power_icon.dds` (106x106, 7 mips) — the `@money!` icon, also used by topbar, treaty, ship and formation panels
- `gfx/interface/icons/generic_icons/money.dds` (106x106, 7 mips, same image) — diplomatic overview, right-click menu, custom tooltips, ship designer, money map mode
- `gfx/interface/icons/building_icons/building_browser_filter_icons/filter_icons_full_cash_reserves.dds` and `filter_icons_not_full_cash_reserves.dds` (140x140, no mips) — crown plus vanilla's green tick on "full"; "not full" is a dimmed, desaturated crown with no tick, as in vanilla

Rule: override a texture at its vanilla path and keep its dimensions, uncompressed BGRA format (fourCC 0) and mip count (compare the 128-byte header with the vanilla file; wrong size or padding shifts the `@money!` baseline everywhere). Provenance: derived from vanilla `law_icons/monarchy.dds` with the cross removed, recoloured to the `income_power_icon.dds` gold ramp. The top mip of `money.dds` is the **crown master** every other currency icon is built from.

**£ painted into other icons** (#6641). The #6641 scoping counted about 51 reachable vanilla icons with a £ in their own art (swept `gfx/interface` only). `artgen/currency_icons.py` rebuilds them from the vanilla file plus the crown master; the covered set is whatever `artgen/currency_icons.json` lists (tranche A, 21 icons: GDP gear and map modes, navy upkeep, foreign investment, outliner economy, state tax capacity and market capital, the PM and building-browser subsidy markers, consumption tax, max tariffs/subventions, privately owned, unemployed, per-capita and consumption taxation laws). These are generated files: change the recipe or the master and regenerate, from the repo root, in the pinned venv (`artgen/README.md`):

```
$env:VANILLA_ROOT = "<Steam library>\steamapps\common\Victoria 3\game"
mapgen\.venv\Scripts\python artgen\currency_icons.py --preview scratchpad\currency_icons   # contact sheet to judge
mapgen\.venv\Scripts\python artgen\currency_icons.py --write
mapgen\.venv\Scripts\python artgen\currency_icons.py --check    # vanilla header parity + byte-identical regeneration
```

- **One crown shape.** Raised or painted glyphs get the painted master, recoloured from the £'s own pixels. Flat, engraved and cut-out glyphs get a flat stencil cut from the master's own alpha outline (two cap windows punched where the master's cap panels are), never a separately drawn crown.
- **Format.** Each file keeps its vanilla header verbatim, size, pixel format and mip count (`artgen/dds.py`). `icons/state_status_icons/state_tax_capacity.dds` is the one DXT1 file (1 mip, punch-through alpha, Pillow's encoder; its edges show block loss at 2x); the rest are uncompressed BGRA.
- **Reachability.** Lens and sway icon paths (`lens_toolbar_icons/<key>`, `sways/<key>`) are built from keys by the engine; absence of a script reference is not proof either way.
- **Tranches B and C (#9195, #9196, accepted by Chris 2026-10-29): 30 more icons, 51 in all.** B: `law_icons/{wealth_voting, slave_trade, debt_slavery, commercial_agriculture, freeholders, guild_system}`, the five `diplomatic_treaties_articles_icons/*_treaties`, `principles_icons/{divine_economy, internal_trade}`, `production_method_icons/{privately_owned, power_of_the_purse, trade_quantity_1}`, `filter_icons_foreign_owners`. C: `objectives/economic_dominance`, `ai_strategy_icons/economic_imperialism` (topper erased), `invention_icons/currency_standards`, `war_goals/foreign_investment_rights`, `notification_icons/company`, `ideology_icons/plutocratic`, `diplomatic_action_icons/da_grant_investment_rights`, and six `lens_toolbar_icons/*`. Where the £ was a coin or currency mark rather than a lettered glyph (`wealth_voting`, `privately_owned`, `economic_imperialism`) the crown sits on a coin disc so it reads as the currency, not a monarch; `wealth_voting` also carries the `universal_suffrage` ballot box, and `privately_owned`'s coin is blue to match its blue hand. No recorded leaves. The 302 px laws keep vanilla's header and 9 mips; our small mips are a little softer than vanilla's, which does not show at the 80 px the laws display at.
- **Follow-ups.** None open for the £ sweep; the sweep counted about 51 and all are covered.

Left alone on purpose (paths under `gfx/interface/icons/`):

- everything in an `unused/` folder — never loaded;
- `law_icons/law_icon_parts/money.dds` — a compositing part, referenced nowhere in vanilla `common/` or `gui/`;
- `lens_toolbar_icons/bankroll{,_break}.dds`, `lens_toolbar_icons/trade_lens_button.dds`, `production_method_icons/{,no_}devine_economics.dds` — no matching key or reference in vanilla `common/` or `gui/`;
- `sways/bankroll.dds` (the money treaty article is `money_transfer`) and `lens_toolbar_icons/{fund_lobbies_break,tributary_obligation,tributary_break_obligation}.dds` (no such string in the exe) — no reachability evidence;
- the edge-on coins `diplomatic_action_icons/{da_request_investment_rights,decrease_payments}.dds` and `lens_toolbar_icons/{da_subject_request_investment_rights,decrease_payments}.dds` — the coin reads as a "3", not a £;
- the tutorial pencil sketches in `gfx/interface/tutorial/` (`balance_budget_5`, `treasury_p1`, `treasury_p2`) — sketch art, left as drawn (Chris, 2026-10-21).
