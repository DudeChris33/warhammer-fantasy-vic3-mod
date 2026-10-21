# artgen

Offline generators for interface art that overrides a vanilla `gfx/` file. Not
loaded by the game and not shipped: `deploy.ps1` copies only the shipping
folders. Conventions and the leave list live in
[`.claude/rules/interface.md`](../.claude/rules/interface.md) ("Currency textures").

| File | Role |
|---|---|
| `dds.py` | DDS I/O shared by every generator: read a top mip, write an override with the vanilla file's own header, size, format and mip chain, check one against vanilla |
| `currency_icons.py` | Replaces the £ painted into vanilla icons with the mod's crown (#6641) |
| `currency_icons.json` | One recipe per icon; the list of files `currency_icons.py` owns |
| `law_icons.py` | Rebuilds the two fasces law icons, Guild State (`corporate_state`) and Estates Monarchy (`social_monarchy`), from vanilla art (#6642). Same `--preview DIR` / `--write` / `--check` modes; the preview sheet shows vanilla and new at 256, 64 and 48 px |

## Running

Use the pinned stack in `mapgen/.venv` (`mapgen/requirements.txt`): output is
byte-identical only on those versions. Point `VANILLA_ROOT` (or `--game`) at the
Victoria 3 install's `game` folder. It is only read, never written. From the
repo root:

```
$env:VANILLA_ROOT = "<Steam library>\steamapps\common\Victoria 3\game"
mapgen\.venv\Scripts\python artgen\currency_icons.py --preview scratchpad\currency_icons
mapgen\.venv\Scripts\python artgen\currency_icons.py --write
mapgen\.venv\Scripts\python artgen\currency_icons.py --check
```

- `--preview DIR` writes `<id>.png` (the icon as the game will see it, DXT1 loss
  included), `<id>_mask.png` (vanilla beside the detected glyph: red core, yellow
  zone refilled, blue protected) and `contact_sheet.png` (vanilla | new, enlarged
  and at display size). Nothing under `gfx/` is touched.
- `--write` writes every override under `gfx/` at its vanilla path.
- `--check` fails if an override is missing, its header or size differs from
  vanilla's, or it differs from a fresh regeneration.
- `--only ID ...` limits any mode to some recipes.

The crown master is the top mip of `gfx/interface/icons/generic_icons/money.dds`
(#6575). Change it, or a recipe, then `--preview`, judge the sheet, `--write`,
`--check` and commit the regenerated files. Never paint an output by hand.

## `dds.py`

```python
import dds
rgba = dds.read_top(path)                       # uint8 (h, w, 4) RGBA, RGB 0 under alpha 0
dds.write_like(vanilla_path, rgba, out_path)    # vanilla's 128-byte header + its layout
problems = dds.check_like(vanilla_path, out_path)   # [] when header, size and decode match
data = dds.encode_like(vanilla_path, rgba)      # the bytes write_like writes
shown = dds.decode_like(vanilla_path, rgba)     # top mip as written (block loss for DXT1)
```

Supported: uncompressed 32-bit BGRA with any mip count (a header recording 0
mips is one level), and single-level DXT1. Anything else raises. Mips are a 2x2
box filter in stored (sRGB) space, area-weighted at odd sizes so no row or
column is dropped, with RGB averaged by alpha. Against vanilla's own chains this
matched better than a plain box: vanilla's exact filter is not known.

## Recipe fields (`currency_icons.json`)

| Field | Meaning |
|---|---|
| `id`, `path` | Recipe name; the file's path under both the game folder and the repo |
| `like` | Copy every field from an earlier recipe, then override |
| `display` | Size in px the icon is judged at on the contact sheet (20 texticons, 40 most, 80 laws) |
| `region` | Where the £ is: `[x0, y0, x1, y1]` or `{"circle": [cx, cy, r]}`, fractions of the icon |
| `glyph` | `bright` / `dark` (luminance against `thresh`, a number or `"otsu"`), `solid` (bare glyph: the opaque components centred in `region`, `thresh` on alpha), `cutout` (holes enclosed by the silhouette) |
| `min_blob`, `dilate` | Drop specks under this many px; grow the glyph mask by this many px before refilling |
| `erase` | `region` refills the whole region (an embossed glyph whose edges fade into the field) |
| `fill` | `inpaint` (continue the field under the glyph) or `clear` (erase a bare glyph and its drop shadow; a new shadow is fitted to vanilla's) |
| `rim` | Cut-outs only: px of silhouette edge refilled around the hole |
| `crown` | `painted` (the master) or `stencil` (flat crown cut from the master's outline) |
| `colour` | Painted: `transfer` (the £'s own colours by luminance rank; `palette: region` ranks the whole region) or `tint` (master shading in the £'s median colour, for one-tone glyphs). Stencil: `flat` (the £'s median colour and alpha) or `punch` (cut out of the field) |
| `scale`, `dx`, `dy` | Crown size relative to the £'s box; offset in fractions of the icon |
| `stencil_stroke` | Least arch width in output px for a stencil (default 1) |
| `protect` | Restored from vanilla on top: `{"poly": [[x, y], ...], "grow": px}` (something in front of the £) and/or `{"red": true}` (a red no-sign stroke) |
