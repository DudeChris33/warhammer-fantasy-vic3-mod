---
paths:
  - "common/coat_of_arms/**/*"
  - "common/flag_definitions/**/*"
  - "common/named_colors/**/*"
  - "common/power_bloc_coa_pieces/**/*"
  - "gfx/coat_of_arms/**/*"
---

# Heraldry (`coat_of_arms`, `flag_definitions`)

**Read when:** you are editing a coat of arms, a flag definition, the colour palette (`common/named_colors/`), or emblem textures. **Covers:** the COA and flag-definition schema, the greenskin house style and power bloc arms. Loads automatically when you open a matching file with the Read tool — a starting point, not a boundary: read any other guide that would help, and read a neighbour whenever your work touches its area.

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

## Colour palette

`common/named_colors` is listed in `replace_paths`. `00_coa_colors.txt` is the port of vanilla's palette; `01_wh_coa_colors.txt` holds the mod-native tinctures (`colors = { name = hsv360 { h s v } }`, e.g. `morrslieb_green`, `ice_blue`, `orc_green`). Append a new tincture to `01_wh_coa_colors.txt` only when a region's heraldry needs a colour the ported palette doesn't cover, with a comment naming the item and region that needed it. Every `color1`/`color2`/`color3` name in a COA block must exist in one of the two files.

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

## Placeholder-tag heraldry

A placeholder tag — a deliberately generic stand-in such as the `XS*` Skaven
clans (see [peoples.md](peoples.md)) — wears the house style of the culture it
actually carries, not of the people it stands in for: the `XS*` tags carry
`goblin`, so they follow the greenskin house style above. Give each placeholder
**one** distinct charge (no two placeholders share a texture) and **no
iconography of the people it stands in for** (no rat device on an `XS*` tag): a
Skaven charge on goblin pops would assert an identity the tag does not have.
The block comment says it is a placeholder and that the device is a disclosed
invention. When the real people get a culture and their own tags, those tags
get their own heraldry; the placeholder's arms are not migrated. `UNO`
(Unclaimed Lands, `98_unclaimed.txt`) follows the same rule: goblin stand-in, so
greenskin house style, with an open hand (`ce_hand`) as its one charge.

## Wood-elf and ogre house styles

Established by #6373 for the `wood_elf` and `ogre` tags; binding on later tags of either people.

- **Wood elves (Asrai).** An autumn/forest palette (`green_dark`, `brown`, `red_dark`, `orange`,
  `saffron`, `golden`, `yellow_dark`, with `pearl`/`bone_white` as light fields; `SOT`'s twilight
  `purple` is the one recorded exception) and one nature or
  hunt charge per realm: trees, leaves, forest beasts, the hunter's arrowhead or falcon. No crowns,
  crosses or fleurs: the Asrai realms are not feudal kingdoms. A charge with a non-wood-elf detail
  (the unicorn's collar and chain) sets that slot to the body's tone.
- **Ogres.** Two tinctures per coat (one field colour, one charge colour) and a motif from the
  tribes' own culture: the gut-plate (a plain disc), the Great Maw (a horns-up crescent), or a
  blast for a gut-cannon tribe. Never an eye (RED's reserved device) and never a lightning bolt
  (too close to the banned `ce_lightning_bolt_nacista`).

## Power bloc coats of arms

Established by #6574. A power bloc's arms are rolled by the engine from vanilla's random
bloc template, which this mod ports in part across three blanked folders:

- `common/coat_of_arms/template_lists/` — `coa_templates.txt` (`power_bloc = { 3000 =
  template_power_bloc_1 }`), `color_lists.txt` (`power_bloc_colors`),
  `colored_emblem_lists.txt` (`power_bloc_shield`, `power_bloc_center`) and
  `textured_emblem_lists.txt` (`power_bloc_top`, `power_bloc_side`, `power_bloc_frame`).
  Only the power-bloc lists are ported; vanilla's other random lists (`all`, `anarchy`,
  `chartered_company`, `normal_colors`, …) are a separate gap.
- `common/coat_of_arms/coat_of_arms/03_random_power_bloc.txt` — `template_power_bloc_1`,
  verbatim.
- `common/power_bloc_coa_pieces/` — the catalogue the bloc customization screen offers.

The engine side lives in vanilla `common/defines/00_graphics.txt` `NPowerBlocCoa`, which this
mod does not override: `COLOR_LIST_NAME` must name a list in `color_lists.txt` (a missing one
renders every bloc solid magenta), and `PIECE_LAYERS_ORDER` plus the `*_SCALE`/`*_POSITION`
values must match the template's layer order, scales and positions. Change one side, change
both.

**One curated texture set.** The random lists and the pieces catalogue carry the same
curated set; the catalogue additionally offers `pb_frame_04` and vanilla's blank "none"
pieces `pb_center_11`, `pb_top_06`, `pb_side_06`. All textures are vanilla's own `pb_*.dds`,
reused in place. Curation is by exclusion from vanilla, and the rule is **global**: it
applies to every `pb_*` twin of a `ce_*` charge, not only to greenskin tags, and it binds any
later addition to either file. Keep only setting-neutral charges; exclude:

- fascist, extremist and communist symbols (the `pb_` twins of house-style rule 5's list,
  runes, `pb_walknut`, `pb_kolovrat`, hammer-and-sickle pieces);
- living-culture sacred art (the `pb_` twins of rule 6's list, the triskel family);
- real-world national and state emblems and place-named charges (`pb_eagle_*`, `pb_bear`,
  `pb_maple_leaf*`, national suns, southern crosses, …);
- colonial or classical figure scenes and out-of-setting fauna (`pb_center_01`/`02`/`09`,
  `pb_top_03` elephant);
- real-world scripts and letters (`pb_omega`, `pb_sigma`, `pb_delta`, `pb_infinity`), the
  pentagram, and anything religious or ideological (every vanilla `special_selection` pool).

A doubtful charge is dropped and recorded in the file's header comment rather than kept
(`pb_star_05_ring` reads as a red-star roundel). No `special_selection` ships today; bespoke
per-realm bloc arms can be added later as `special_selection` entries in the `power_bloc`
list keyed on this mod's own tags (vanilla's `c:GBR`-style blocks are the model), each with a
fixed template beside `template_power_bloc_1`.
