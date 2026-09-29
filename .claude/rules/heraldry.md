---
paths:
  - "common/coat_of_arms/**/*"
  - "common/flag_definitions/**/*"
  - "common/named_colors/**/*"
  - "gfx/coat_of_arms/**/*"
---

# Heraldry (`coat_of_arms`, `flag_definitions`)

**Read when:** you are editing a coat of arms, a flag definition, the colour palette (`common/named_colors/`), or emblem textures. **Covers:** the COA and flag-definition schema and the greenskin house style. Loads automatically when you open a matching file with the Read tool — a starting point, not a boundary: read any other guide that would help, and read a neighbour whenever your work touches its area.

**Related guides:**
- [peoples.md](peoples.md) — tags, region-file order, culture colours
- [interface.md](interface.md) — emblem textures under `gfx/`
- [scripting.md](scripting.md) — general script rules and `docs/*.log`

## `common/coat_of_arms/` + `common/flag_definitions/` schema

Neither database is documented in `docs/*.log`; the vanilla install is the sole
authority for both — confirm every `texture`/`pattern`/`color` reference and
colour-slot count against real vanilla usage before writing a block, the same
discipline every shipped COA file follows. Both folders are listed in `.metadata/metadata.json`'s `replace_paths`, so
vanilla's own files for them do not load at all — a tag with no entry in this
mod's own files gets no coat of arms and no flag.

- **`common/coat_of_arms/coat_of_arms/<region>.txt`** — one block per country tag,
  keyed on the tag, in the same order as that region's
  `common/country_definitions/` file:
  ```
  TAG = {
  	pattern = "<pattern_file>.tga|.dds"
  	color1 = "<name>"
  	color2 = "<name>"

  	colored_emblem = {
  		texture = "<ce_file>.dds"
  		color1 = "<name>"
  		color2 = "<name>"
  		[color3 = "<name>"]
  		instance = { position = { x y } scale = { x y } [rotation = N] }
  	}
  }
  ```
  `pattern` always takes exactly `color1`+`color2` (no `color3`) across every
  pattern in the vanilla catalog. A `colored_emblem`'s colour-slot count
  (2 or 3) is emblem-specific and must be confirmed from a real vanilla (or
  vendored) usage — never guessed; where only a partial usage is found, the
  unconfirmed slot is set defensively to the same tone as slot 1 (the
  convention `AVE` established). A `colored_emblem` block may repeat
  (layering charges) and a single `colored_emblem` may carry multiple `instance =`
  blocks (repeating the same charge at different placements/scales — negative
  `x` in `scale` mirrors the charge horizontally). Every block needs a comment
  recording its canon-confidence bucket (canon-firm / soft / disclosed
  invention / disclosed substitution) and, for a reused or vendored texture, the
  disclosure format in the two conventions below.
- **`common/flag_definitions/<region>.txt`** — required alongside every COA file:
  this mod's own `00_flag_definitions.txt` DEFAULT block is unconditional at
  `priority = 0`, which masks every bespoke COA unless a higher-priority,
  tag-named `flag_definition` block exists. One block per tag, `priority = 100`,
  `trigger = { always = yes }` (confirmed valid in `docs/triggers.log`) — see any
  shipped `common/flag_definitions/<region>.txt` for the exact shape.

Both files are required together — a COA with no matching `flag_definition`
entry parses cleanly but never renders in-game.

## Greenskin house style (Badlands/Orcs & Goblins)

Established for `common/coat_of_arms/coat_of_arms/06_badlands.txt` and binding on
every later greenskin-tag COA file (Dark Lands hobgoblins etc.) so the whole
faction reads as one visual family distinct from the "civilised" human/dwarf/elf
tag files:

1. One charge, two max; oversized, off-centre/skewed — never a centred, evenly-
   scaled single charge.
2. Two-colour fields max. No quartering, gironny, checker, orle, laurel, wreath,
   or crown framing.
3. Closed palette: `black`, `black_light`, `orc_green`, `goblin_moss`,
   `green_dark`, `bone`, `gore_red`, `red_dark`, `dirty_iron`, `grey`,
   `yellow_dark`, `saffron`, `morrslieb_green`.
4. No "civilised" charges (cross, crown, laurel, wreath, fleur, lion/eagle-as-
   full-beast). A claw or a boar-as-secondary-mark is fine; a rampant eagle is
   not.
5. Banned — real-world extremist association: `ce_wolfsangel*`,
   `ce_triskel_wolfsangel`, `ce_odal_square`, `ce_rune_algiz`/`hagal`/`tiwaz`,
   `ce_balkenkreuz`, `ce_iron_cross`, `ce_arrow_cross`,
   `ce_three_arrows_square`, `ce_cross_hlinka`, `ce_cross_fatherland_front`,
   `ce_parteiadler`, `ce_reichsadler`, `ce_eagle_fascist_stylized`,
   `ce_eagle_italy_fascist`, `ce_lightning_bolt_nacista`, `ce_labrys_petain`,
   `ce_labrys_ppf`, `ce_falange`, `ce_falanga`, `ce_vlajka_emblem`,
   `ce_moors_head`.
6. Banned — real-world ethnographic/sacred art of a living culture (distinct
   from the separate "loreful fit beats real-world-adjacency avoidance"
   directive elsewhere in the epic, which is about not dodging a generic
   real-world-resembling charge for a good canon/name fit — not about
   respecting a specific living culture's sacred imagery): `ce_masai_shield`,
   `ce_nguni_shield*`, `ce_shield_african`, `ce_bull_head_african`,
   `ce_kanaga`, `ce_kanaka`, `ce_wiphala`, `ce_hiawathas_belt`,
   `ce_native_american_pattern_diamond`, `ce_thunderbird`, `ce_totem_kanak`,
   `ce_comanche_sun`, `ce_hand_dreaming`, `te_lakota_medicine_wheel`,
   `te_buffalo_painted_skull`.
7. Provenance convention for any Realms of Exether asset: copy the `.dds` into
   this mod's own `gfx/coat_of_arms/colored_emblems/` (plain git, no LFS),
   comment above the using block:
   `# emblem: Realms of Exether (gfx/coat_of_arms/colored_emblems/<file>.dds), reuse grant`
8. Emblem-reuse disclosure convention: when reusing a texture another shipped
   sibling used, add a one-line comment naming the sibling tag/file and the
   distinguishing recolour.
9. Reserved-devices list so nothing duplicates across later siblings (Dark
   Lands hobgoblins etc.): eye (RED), crooked moon (CRM), fang-pair (RFG),
   horned beast-skull (BNR), toothed border concept (BTO).
10. Shared family cue for the three "Broken" tribes (BKA/BTO/BRN): each carries
    a deliberately skewed or chipped charge.
