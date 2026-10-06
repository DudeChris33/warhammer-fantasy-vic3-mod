#!/usr/bin/env python3
"""Crop the TWW3 campaign map's printed label layer around each name suggestion
(board #4414) — the human-readable cross-check for ``mapgen/tww3_name_lookup.py``.

**Dev-only, gitignored output.** Everything this writes lands under
``mapgen/derived/tww3_text_crops/`` (covered by ``mapgen/.gitignore``'s
``derived/*``); nothing reaches ``mapgen/config/`` or any committed file. Like
#4363 and #4364 this produces *evidence for a human*: #4363 resolves a canvas
point to a TWW3 region **key** through a colour lookup, and that key is a
database slug (``cr_oldworld_region_helmgart``), not the name actually printed on
the map. This script shows the printed label sitting at that exact point, so a
reviewer can confirm — by eye, which is the only authority here — that the slug
and the cartography agree before either reaches a worksheet.

Why the transform is free
-------------------------
``sources/cr_oldworld_campaign/campaign_map/cr_oldworld_map_text.png`` is the
campaign map's text layer: RGBA, transparent everywhere but the drawn labels,
and it shares the 8192-px campaign-map frame that
``mapgen/render_cr_lookup_overlay.py`` (#4364) established is the 4096-px
parchment master at exactly 2x. So a canvas point reaches it through the very
same chain #4363 already uses, with no new registration and no new constant::

    canvas px --(fit.to_source_px)--> master px --(x LOOKUP_SCALE)--> text px

:data:`TEXT_SCALE` is imported from ``tww3_name_lookup``, never re-declared, and
``run_fixture.py --check`` asserts the two agree. Unlike the lookup bitmap the
text layer is 8192x**8192** — no duplicate padding row, hence no ``DROP_ROW``
here (also asserted).

PROVISIONAL FOUNDATION
----------------------
``mapgen/registration/tww3_old_world_mod_parchment_full.json`` marks itself
"PROVISIONAL until the user accepts the diagnostic render". Every crop here is
centred through it and inherits that — which is the other thing this render is
good for: a systematic offset between the crosshair and the label it should be
sitting on is visible evidence about the placement itself.

Worksheet seed
--------------
Each crop also shows the name ``mapgen/config/land_regions_worksheet.csv`` (the
persisted, hand-edited land-naming input) already carries for whatever region
currently owns that pixel — relocated forward through the same anchor-pixel
technique ``render_land_regions_preview.py`` uses, so it can never disagree
with what that render would show. It is a **starting point for triage**, not a
verdict: the worksheet predates this cross-check entirely.

Anchor drift
------------
A crop is only meaningful if the point still resolves to the region the CSV row
was written for. Suggestion CSVs are written by a separate run and the province
cut (and therefore the anchors in the ``--propose-hubs`` report) moves; so every
row's own ``hex`` column is re-sampled against the live lookup and a mismatch is
flagged **ANCHOR DRIFT** — a distinct crosshair colour, a caption tag and an
``index.html`` flag — rather than being presented as a clean suggestion.

Usage::

    python mapgen/render_tww3_text_crops.py                       # the anchors report
    python mapgen/render_tww3_text_crops.py --report mapgen/derived/tww3_hub_suggestions.csv
    python mapgen/render_tww3_text_crops.py --status all --limit 40
    python mapgen/render_tww3_text_crops.py --at 4091 898
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tww3_name_lookup as tnl  # noqa: E402

# The text layer is 8192², far past Pillow's decompression-bomb guard — which is
# aimed at hostile uploads, not at local reference art whose dimensions this
# script asserts explicitly before using.
Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DERIVED_DIR = TOOLS_DIR / "derived"
OUT_DIR = DERIVED_DIR / "tww3_text_crops"

#: The persisted, hand-edited land-naming input (267 named regions as of #4363's
#: own build) — a starting point for triage, not a source of truth: a name here
#: may itself be provisional, or may not be the region the crop's point resolves
#: to at all once #4363's suggestions are reviewed. See :func:`load_worksheet_seed`.
CONFIG_WORKSHEET = TOOLS_DIR / "config" / "land_regions_worksheet.csv"

#: The printed-label layer, a sibling of the lookup bitmap in the same gitignored
#: dump. Its absence is the expected state on every device but Chris's.
MAP_TEXT_PNG = tnl.DATASET_DIR / "campaign_map" / "cr_oldworld_map_text.png"

#: Master px -> text px. **Imported, never re-declared**: the text layer and the
#: lookup bitmap live in the same campaign-map frame, so a divergence between the
#: two constants would silently point this render at different ground than the
#: suggestion it is checking. ``run_fixture.py --check`` pins the equality.
TEXT_SCALE = tnl.LOOKUP_SCALE
#: The text layer's frame, asserted against the file on disk (never adapted to).
#: Deliberately equal to :data:`tww3_name_lookup.LOOKUP_SIZE` — same frame.
TEXT_SIZE = 8192

#: Crosshair colours: the normal centre marker, and the one used when the row's
#: own ``hex`` no longer matches what the live lookup reads at that point.
CROSSHAIR_RGB = (255, 0, 255)
DRIFT_RGB = (255, 140, 0)
#: The region-outline overlay: the boundary of the region actually sampled.
OUTLINE_RGB = (0, 255, 255)
#: Gap left clear at the centre of the crosshair so the marker never covers the
#: glyphs it is pointing at.
CROSSHAIR_GAP = 14
CROSSHAIR_WIDTH = 2

BACKGROUNDS = {"cream": (238, 228, 203), "white": (255, 255, 255)}

#: Statuses worth looking at by default. Deliberately NOT just ``ok``: the two
#: deferred-to-human statuses from ``--propose-hubs`` (``ambiguous``,
#: ``centroid-outside-region``) are exactly the rows a printed label can settle.
DEFAULT_STATUSES = "ok,ambiguous,centroid-outside-region"
#: Rows that sort first, because they are the ones needing a human verdict.
PRIORITY_STATUSES = ("ambiguous", "centroid-outside-region")

_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")


def log(msg: str = "") -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------

def require_text_layer() -> None:
    """Clean-skip when the label layer is not on this device.

    The ``validate_map._check_canon_cities`` idiom, reached in two steps: the
    shared dataset check first (``mapgen/tww3_name_lookup.require_dataset``), then
    this one file, because the dump can be present without the campaign-map
    export having been made.
    """
    tnl.require_dataset()
    if MAP_TEXT_PNG.is_file():
        return
    log(f"{tnl.rel(MAP_TEXT_PNG)}: label layer not present on this device — "
        f"dev-only render, skipping")
    sys.exit(0)


def load_text_layer() -> np.ndarray:
    """``(8192, 8192, 4)`` uint8 RGBA. Loaded once, cropped many times.

    A different measured size is a hard error, never a silent adaptation: a
    differently-framed export would make :data:`TEXT_SCALE` wrong and every crop
    would be centred on the wrong ground while looking perfectly plausible.
    """
    with Image.open(MAP_TEXT_PNG) as im:
        w, h = im.size
        if (w, h) != (TEXT_SIZE, TEXT_SIZE):
            raise SystemExit(
                f"{MAP_TEXT_PNG.name} is {w}x{h}, expected {TEXT_SIZE}x{TEXT_SIZE} "
                f"(the campaign-map frame = the 4096-px parchment master at "
                f"{TEXT_SCALE}x). A different size is a different export and the "
                f"scale constant this render shares with tww3_name_lookup.py would "
                f"be wrong for it.")
        return np.asarray(im.convert("RGBA"), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Worksheet seed (best-effort — never blocks a crop)
# ---------------------------------------------------------------------------

def load_worksheet_seed() -> tuple[np.ndarray | None, dict[int, str]]:
    """Canvas-pixel region label raster + the old worksheet's name for each label.

    ``mapgen/config/land_regions_worksheet.csv`` is the persisted, hand-edited
    naming input. Its rows carry ``anchor_x``/``anchor_y`` — the region's own
    centroid pixel at the time a human named it — and identity is that pixel, not
    the row's ``region_id`` (which is a Hilbert-ordered STATE number that
    reshuffles across a regen). ``render_land_regions_preview.py`` already
    established the fix for that: relocate a name forward by resampling the
    CURRENT region-label raster at the row's own stored anchor. This reuses the
    exact same technique so a crop's name seed can never disagree with what that
    render would show for the same pixel.

    A name found this way is a **starting point**, not a verdict — it predates
    #4363's TWW3 cross-check entirely, and the region under a given pixel may
    have moved or split since the worksheet row was last touched. That is
    exactly what the crop is for a human to judge.

    Returns ``(None, {})`` — never raises — when the worksheet or the supporting
    derived province/region indices are not on disk. Seeding is a convenience;
    its absence must never block a crop the way the label layer's absence does.
    """
    if not CONFIG_WORKSHEET.is_file():
        return None, {}
    try:
        lab, _areas = tnl.load_region_labels()
    except SystemExit as exc:
        log(f"worksheet seed    skipped ({exc})")
        return None, {}

    names: dict[int, str] = {}
    with CONFIG_WORKSHEET.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("name") or "").strip()
            ax_raw, ay_raw = row.get("anchor_x"), row.get("anchor_y")
            if not (name and ax_raw and ay_raw):
                continue
            ax, ay = int(float(ax_raw)), int(float(ay_raw))
            if not (0 <= ax < tnl.CANVAS_W and 0 <= ay < tnl.CANVAS_H):
                continue
            label = int(lab[ay, ax])
            if label > 0:
                names[label] = name
    return lab, names


def seed_name_at(lab: np.ndarray | None, names: dict[int, str], x: int, y: int) -> str:
    """The worksheet's name for whichever region currently owns canvas ``(x, y)``."""
    if lab is None or not (0 <= x < tnl.CANVAS_W and 0 <= y < tnl.CANVAS_H):
        return ""
    label = int(lab[y, x])
    return names.get(label, "") if label > 0 else ""


# ---------------------------------------------------------------------------
# Report parsing
# ---------------------------------------------------------------------------

#: The three CSV shapes ``mapgen/tww3_name_lookup.py`` can write. Detected by
#: column presence, never guessed at from the filename.
KIND_ANCHORS = "anchors"
KIND_HUBS = "hubs"


def detect_report_kind(fieldnames: list[str]) -> str:
    """Which ``tww3_name_lookup.py`` report is this? Hard-errors on anything else.

    * ``anchor_x``/``anchor_y`` + ``land_region_id``  -> ``--propose-hubs``
    * ``anchor_x``/``anchor_y`` + ``region_id``       -> ``--anchors-only``
    * no anchors, but ``region_id`` + ``candidate_1`` -> the ``--regions`` vote
      report, which carries no anchors at all and so cannot be cropped.

    Named explicitly rather than silently misclassified: a vote report read as an
    anchor report would crop nothing and look like an empty result.
    """
    cols = set(fieldnames or ())
    has_anchor = {"anchor_x", "anchor_y"} <= cols
    if has_anchor and "land_region_id" in cols:
        return KIND_HUBS
    if has_anchor and "region_id" in cols:
        return KIND_ANCHORS
    if "region_id" in cols and "candidate_1" in cols:
        raise SystemExit(
            "this is a --regions vote report and carries no anchors; re-run "
            "mapgen/tww3_name_lookup.py --anchors-only or --propose-hubs and point "
            "--report at its CSV")
    raise SystemExit(
        f"unrecognised report shape: columns {sorted(cols)}. Expected an "
        f"--anchors-only report (region_id + anchor_x/anchor_y) or a --propose-hubs "
        f"report (land_region_id + anchor_x/anchor_y).")


@dataclass(frozen=True)
class Row:
    """One croppable suggestion, normalised across the two report shapes."""

    label: str        # the caption's left-hand identity, e.g. "region_id=12"
    stem: str         # output filename stem, pre-sanitisation
    slug: str
    x: int
    y: int
    status: str
    hexcode: str      # the row's OWN recorded colour ("" when the row has none)
    margin: str
    source: str
    area: int         # sort weight; 0 when the report carries no area column


def _int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def read_report(path: Path) -> tuple[str, list[Row]]:
    if not path.is_file():
        raise SystemExit(
            f"{tnl.rel(path)} not found — generate it first with "
            f"`python mapgen/tww3_name_lookup.py --anchors-only` (or --propose-hubs)")
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        kind = detect_report_kind(list(reader.fieldnames or []))
        raw = list(reader)

    rows: list[Row] = []
    for r in raw:
        slug = (r.get("tww3_slug") or "").strip()
        margin = (r.get("margin_lookup_px") or r.get("margin_px") or "").strip()
        if kind == KIND_HUBS:
            ident = (r.get("tww3_key") or slug or "?").strip()
            label = f"hub={ident}"
            stem = f"hub_{slug or ident}"
        else:
            ident = (r.get("region_id") or "?").strip()
            label = f"region_id={ident}"
            stem = f"region_{ident}_{slug}" if slug else f"region_{ident}"
        rows.append(Row(
            label=label,
            stem=stem,
            slug=slug,
            x=_int(r.get("anchor_x"), -1),
            y=_int(r.get("anchor_y"), -1),
            status=(r.get("status") or "").strip(),
            hexcode=(r.get("hex") or "").strip(),
            margin=margin,
            source=(r.get("source") or "").strip(),
            area=_int(r.get("area_lookup_px") or r.get("area_px")),
        ))
    return kind, rows


def order_rows(rows: list[Row]) -> list[Row]:
    """Most-in-need-of-a-human first, then biggest region first.

    The ordering only matters when ``--limit`` truncates, which is precisely when
    it matters most: an arbitrary first N would show the rows nobody needed to see.
    """
    def key(r: Row) -> tuple[int, int]:
        return (0 if r.status in PRIORITY_STATUSES else 1, -r.area)
    return sorted(rows, key=key)


# ---------------------------------------------------------------------------
# The drift test (pure, so run_fixture.py can exercise it directly)
# ---------------------------------------------------------------------------

def is_anchor_drift(sampled_hex: str, row_hex: str) -> bool:
    """Has the ground under this anchor changed since the report was written?

    Compares the live lookup sample against the colour the CSV row recorded, in
    the format both sides already use: an uppercase 6-digit hex string
    (``worldgen.tww3_names`` normalises the TSV to upper, and
    ``Lookup.hex_at_lookup`` formats with ``%02X``). The comparison is
    case-insensitive anyway so a hand-edited row cannot produce a phantom drift.

    A row with **no** recorded colour (the ``--propose-hubs`` report's rows carry
    one; an ``outside``/``out-of-scope`` anchor row does not) cannot drift — there
    is nothing to disagree with — so it is never flagged.
    """
    if not row_hex or not sampled_hex:
        return False
    return sampled_hex.strip().lower() != row_hex.strip().lower()


# ---------------------------------------------------------------------------
# Crop rendering
# ---------------------------------------------------------------------------

def crop_box(tx: int, ty: int, half: int) -> tuple[int, int, int, int]:
    """The crop window, clamped to the text frame. May be off-centre at an edge."""
    return (max(0, tx - half), max(0, ty - half),
            min(TEXT_SIZE, tx + half), min(TEXT_SIZE, ty + half))


def flatten(text_rgba: np.ndarray, box: tuple[int, int, int, int],
            bg: tuple[int, int, int]) -> Image.Image:
    """The RGBA label crop composited onto an opaque ground.

    The layer is transparent everywhere but the glyphs, so without a ground it
    renders as nothing at all in most viewers.
    """
    x0, y0, x1, y1 = box
    tile = Image.fromarray(text_rgba[y0:y1, x0:x1], mode="RGBA")
    ground = Image.new("RGBA", tile.size, (*bg, 255))
    return Image.alpha_composite(ground, tile).convert("RGB")


def draw_outline(img: Image.Image, lookup_arr: np.ndarray,
                 box: tuple[int, int, int, int], tx: int, ty: int) -> int:
    """Trace the boundary of the region the centre point actually sampled.

    The lookup bitmap shares this frame post-row-drop, so the same window indexes
    both. A neighbour-difference over the ``== sampled colour`` mask is the same
    boundary extraction ``render_cr_lookup_overlay.extract_borders`` does, on one
    region instead of all of them. Returns the pixel count (0 when the centre is
    void/black, which has no meaningful boundary).
    """
    x0, y0, x1, y1 = box
    block = lookup_arr[y0:y1, x0:x1]
    target = lookup_arr[ty, tx]
    if not int(target.sum()):
        return 0
    mask = np.all(block == target, axis=2)
    edge = np.zeros(mask.shape, dtype=bool)
    diff_x = mask[:, :-1] != mask[:, 1:]
    edge[:, :-1] |= diff_x
    edge[:, 1:] |= diff_x
    diff_y = mask[:-1, :] != mask[1:, :]
    edge[:-1, :] |= diff_y
    edge[1:, :] |= diff_y
    edge &= mask
    if not edge.any():
        return 0
    arr = np.asarray(img, dtype=np.uint8).copy()
    arr[edge] = OUTLINE_RGB
    img.paste(Image.fromarray(arr, mode="RGB"))
    return int(edge.sum())


def draw_crosshair(img: Image.Image, cx: int, cy: int, rgb: tuple[int, int, int]) -> None:
    """Four short arms around ``(cx, cy)``, leaving the centre glyphs uncovered."""
    d = ImageDraw.Draw(img)
    w, h = img.size
    g, t = CROSSHAIR_GAP, CROSSHAIR_WIDTH
    d.rectangle([0, cy - t // 2, max(0, cx - g), cy - t // 2 + t - 1], fill=rgb)
    d.rectangle([min(w, cx + g), cy - t // 2, w - 1, cy - t // 2 + t - 1], fill=rgb)
    d.rectangle([cx - t // 2, 0, cx - t // 2 + t - 1, max(0, cy - g)], fill=rgb)
    d.rectangle([cx - t // 2, min(h, cy + g), cx - t // 2 + t - 1, h - 1], fill=rgb)


def add_caption(img: Image.Image, text: str, drift: bool) -> Image.Image:
    """Stamp a caption bar under the crop.

    Drawn at 1x with the default bitmap font and upscaled NEAREST — the
    ``render_cr_lookup_overlay.draw_legend`` pattern, so there is no font
    dependency and no per-device rendering difference.
    """
    scale = 2
    bar_w = max(1, img.width // scale)
    bar_h = 14
    tile = Image.new("RGB", (bar_w, bar_h), (32, 24, 16) if not drift else (96, 42, 0))
    ImageDraw.Draw(tile).text((4, 2), text, fill=(235, 235, 235))
    bar = tile.resize((bar_w * scale, bar_h * scale), Image.NEAREST)
    out = Image.new("RGB", (img.width, img.height + bar.height), (32, 24, 16))
    out.paste(img, (0, 0))
    out.paste(bar, (0, img.height))
    return out


# ---------------------------------------------------------------------------
# Output naming
# ---------------------------------------------------------------------------

def safe_stem(stem: str) -> str:
    cleaned = _SAFE_RE.sub("_", stem).strip("_")
    return cleaned or "crop"


def unique_path(stem: str, used: set[str]) -> Path:
    """``<stem>.png``, or ``<stem>_2.png`` etc. — a duplicate row never overwrites."""
    base = safe_stem(stem)
    name = base
    n = 1
    while name in used:
        n += 1
        name = f"{base}_{n}"
    used.add(name)
    return OUT_DIR / f"{name}.png"


# ---------------------------------------------------------------------------
# index.html
# ---------------------------------------------------------------------------

_HTML_HEAD = """<!doctype html>
<meta charset="utf-8">
<title>TWW3 printed-label crops</title>
<style>
 body {{ font: 13px/1.5 system-ui, sans-serif; background: #1b1b1b; color: #e8e8e8;
        margin: 24px; }}
 h1 {{ font-size: 18px; }}
 p.note {{ color: #b9b9b9; max-width: 70em; }}
 table {{ border-collapse: collapse; }}
 td, th {{ border-top: 1px solid #3a3a3a; padding: 8px 10px; vertical-align: top;
           text-align: left; }}
 img {{ width: 420px; image-rendering: pixelated; background: #000; }}
 code {{ background: #2a2a2a; padding: 1px 4px; }}
 .drift {{ color: #ffab40; font-weight: bold; }}
 .skip {{ color: #9a9a9a; }}
 .seed {{ color: #8ec9ff; }}
</style>
<h1>TWW3 printed-label crops</h1>
<p class="note">{intro}</p>
"""


def write_index(entries: list[dict], skipped: list[dict], meta: dict) -> Path:
    intro = html.escape(
        f"Report {meta['report']} ({meta['kind']}). {len(entries)} crop(s), "
        f"{meta['drift']} flagged ANCHOR DRIFT, {len(skipped)} skipped, "
        f"{meta['filtered']} filtered out by --status {meta['statuses']}. "
        "Each crop is cr_oldworld_map_text.png at the suggestion's own canvas "
        "point, through the PROVISIONAL tww3_old_world_mod_parchment_full "
        "registration; the magenta crosshair is that point and the cyan outline "
        "is the sampled region's boundary. Where shown, 'worksheet seed' is the "
        "name mapgen/config/land_regions_worksheet.csv already carries for "
        "whatever region currently owns that pixel — a starting point predating "
        "this cross-check, not a verdict. Dev-only, gitignored: accepting a "
        "name into mapgen/config/ is a separate human step.")
    parts = [_HTML_HEAD.format(intro=intro)]
    if entries:
        parts.append("<table>\n<tr><th>crop</th><th>suggestion</th></tr>\n")
        for e in entries:
            drift = ('<div class="drift">ANCHOR DRIFT — the live lookup reads '
                     f'{html.escape(e["sampled_hex"])} here, the row recorded '
                     f'{html.escape(e["row_hex"])}</div>\n') if e["drift"] else ""
            parts.append(
                f'<tr><td><img src="{html.escape(e["file"])}" '
                f'alt="{html.escape(e["label"])}"></td><td>'
                f'<div><b>{html.escape(e["guess"])}</b></div>\n'
                + (f'<div class="seed">worksheet seed: {html.escape(e["seed"])}</div>\n'
                   if e["seed"] else "")
                + f'<div>{html.escape(e["label"])} &middot; status '
                f'{html.escape(e["status"])}'
                + (f' &middot; margin {html.escape(e["margin"])} px' if e["margin"] else "")
                + f'</div>\n<div>canvas ({e["x"]}, {e["y"]}) &rarr; text px '
                f'({e["tx"]}, {e["ty"]})</div>\n{drift}'
                + (f'<pre><code>{html.escape(e["source"])}</code></pre>\n'
                   if e["source"] else "")
                + "</td></tr>\n")
        parts.append("</table>\n")
    else:
        parts.append("<p class=\"note\">No crops were produced.</p>\n")
    if skipped:
        parts.append("<h2>Skipped</h2>\n<table>\n")
        for s in skipped:
            parts.append(f'<tr><td class="skip">{html.escape(s["label"])}</td>'
                         f'<td class="skip">{html.escape(s["why"])}</td></tr>\n')
        parts.append("</table>\n")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "index.html"
    path.write_text("".join(parts), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def render(lookup: tnl.Lookup, text_rgba: np.ndarray, rows: list[Row], *,
           half: int, bg: tuple[int, int, int], outline: bool,
           seed_lab: np.ndarray | None = None,
           seed_names: dict[int, str] | None = None) -> tuple[list[dict], list[dict]]:
    entries: list[dict] = []
    skipped: list[dict] = []
    used: set[str] = set()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for row in rows:
        mx, my = lookup.fit.to_source_px(np.array([float(row.x)]), np.array([float(row.y)]))
        mxf, myf = float(mx[0]), float(my[0])
        # The same "did the registration place this at all" test to_lookup_px
        # applies — a point outside the Delaunay hull comes back as a large
        # negative sentinel, which must be reported, never cropped at (0, 0).
        inside = (np.isfinite(mxf) and np.isfinite(myf)
                  and 0 <= mxf <= tnl.MASTER_SIZE - 1 and 0 <= myf <= tnl.MASTER_SIZE - 1)
        if not inside:
            skipped.append({"label": f"{row.label} ({row.slug})",
                            "why": "skipped (outside registered frame)"})
            continue
        tx = int(min(TEXT_SIZE - 1, max(0, round(mxf * TEXT_SCALE))))
        ty = int(min(TEXT_SIZE - 1, max(0, round(myf * TEXT_SCALE))))

        sampled = lookup.hex_at_lookup(tx, ty)
        drift = is_anchor_drift(sampled, row.hexcode)
        seed = seed_name_at(seed_lab, seed_names or {}, row.x, row.y)

        box = crop_box(tx, ty, half)
        img = flatten(text_rgba, box, bg)
        if outline:
            draw_outline(img, lookup.arr, box, tx, ty)
        draw_crosshair(img, tx - box[0], ty - box[1],
                       DRIFT_RGB if drift else CROSSHAIR_RGB)
        detail = ", ".join(p for p in (row.status,
                                       f"margin {row.margin} px" if row.margin else "")
                           if p)
        caption = (f"{row.label}  guess: {row.slug or '(none)'}"
                   + (f"  ({detail})" if detail else "")
                   + (f"  worksheet: {seed}" if seed else "")
                   + ("  ANCHOR DRIFT" if drift else ""))
        img = add_caption(img, caption, drift)

        path = unique_path(row.stem, used)
        img.save(path)
        entries.append({
            "file": path.name, "label": row.label, "guess": row.slug or "(none)",
            "status": row.status, "margin": row.margin, "source": row.source,
            "x": row.x, "y": row.y, "tx": tx, "ty": ty, "seed": seed,
            "drift": drift, "sampled_hex": sampled, "row_hex": row.hexcode,
        })
    return entries, skipped


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--report", type=Path, default=tnl.NAME_SUGGESTIONS_CSV,
                      help=f"suggestion CSV to crop from (default "
                           f"{tnl.NAME_SUGGESTIONS_CSV.name}); the shape is detected "
                           f"from its columns")
    mode.add_argument("--at", nargs=2, type=int, metavar=("X", "Y"),
                      help="crop one ad-hoc canvas point instead of a report")
    p.add_argument("--status", default=DEFAULT_STATUSES,
                   help=f"comma-separated status filter, or 'all' (default "
                        f"{DEFAULT_STATUSES} — the two deferred-to-human statuses "
                        f"are included deliberately)")
    p.add_argument("--limit", type=int, default=0,
                   help="cap the number of crops (0 = no cap)")
    p.add_argument("--half", type=int, default=300,
                   help="crop half-width in text px (default 300, i.e. 600x600)")
    p.add_argument("--outline-off", action="store_true",
                   help="skip the sampled region's boundary overlay (debug only — "
                        "the outline is what shows WHICH region the label belongs to)")
    p.add_argument("--bg", choices=sorted(BACKGROUNDS), default="cream",
                   help="opaque ground the transparent label layer is flattened onto")
    args = p.parse_args(argv)
    if args.half < 1:
        raise SystemExit("--half must be >= 1")

    require_text_layer()

    # The report is read and filtered BEFORE the ~200 MB of bitmaps below, so a
    # missing, empty or wrong-shaped CSV is answered in a second rather than after
    # a long load that was never going to be used.
    filtered = 0
    rows: list[Row] = []
    if args.at:
        kind = "ad-hoc point"
        report_name = f"--at {args.at[0]} {args.at[1]}"
        statuses = "n/a"
    else:
        kind, all_rows = read_report(args.report)
        report_name = tnl.rel(args.report)
        log(f"report            {report_name} ({kind}, {len(all_rows)} rows)")
        if not all_rows:
            log("nothing to crop — the report has no data rows")
            return 0
        statuses = args.status
        if args.status.strip().lower() == "all":
            rows = list(all_rows)
        else:
            keep = {s.strip() for s in args.status.split(",") if s.strip()}
            rows = [r for r in all_rows if r.status in keep]
        filtered = len(all_rows) - len(rows)
        rows = order_rows(rows)
        if args.limit and len(rows) > args.limit:
            log(f"showing {args.limit} of {len(rows)} (raise --limit)")
            rows = rows[:args.limit]
        if not rows:
            log(f"nothing to crop — all {len(all_rows)} row(s) filtered out by "
                f"--status {args.status}")
            return 0

    lookup = tnl.Lookup()
    text_rgba = load_text_layer()
    seed_lab, seed_names = load_worksheet_seed()
    if seed_names:
        log(f"worksheet seed    {len(seed_names)} name(s) from {tnl.rel(CONFIG_WORKSHEET)} "
            f"(a starting point predating the #4363 cross-check, not a verdict)")
    log(f"label layer       {MAP_TEXT_PNG.name} {TEXT_SIZE}x{TEXT_SIZE} RGBA "
        f"(master x{TEXT_SCALE:g}, shared with {tnl.LOOKUP_BMP.name})")
    log(f"registration      {tnl.FULL_SOURCE} ({lookup.reg.projection}, "
        f"{len(lookup.reg.control_points)} control points) — PROVISIONAL per its own "
        f"record; every crop here inherits that")

    bg = BACKGROUNDS[args.bg]
    if args.at:
        # Resolve the point through the same lookup ``tww3_name_lookup.py --at``
        # uses, so the caption states what the crop is evidence FOR rather than
        # leaving the reviewer to run that script separately for the same pixel.
        s = lookup.name_at(args.at[0], args.at[1])
        rows = [Row(label=f"canvas=({args.at[0]}, {args.at[1]})",
                    stem=f"at_{args.at[0]}_{args.at[1]}",
                    slug=s.region.slug if s.region else "", x=args.at[0],
                    y=args.at[1], status=s.status, hexcode=s.hex or "",
                    margin="" if s.margin_px != s.margin_px else f"{s.margin_px:.0f}",
                    source=tnl.source_citation(s.region) if s.region else "", area=0)]

    entries, skipped = render(lookup, text_rgba, rows, half=args.half, bg=bg,
                              outline=not args.outline_off,
                              seed_lab=seed_lab, seed_names=seed_names)
    drift = sum(1 for e in entries if e["drift"])
    index = write_index(entries, skipped, {
        "report": report_name, "kind": kind, "drift": drift,
        "filtered": filtered, "statuses": statuses})

    log("")
    log(f"crops             {len(entries)} written to {tnl.rel(OUT_DIR)}")
    log(f"anchor drift      {drift} row(s) no longer sample the colour their report "
        f"recorded — flagged, not presented as clean suggestions")
    log(f"skipped           {len(skipped)} outside the registered frame"
        + (f"; filtered {filtered} by --status" if filtered else ""))
    if args.at and entries:
        log(f"wrote {tnl.rel(OUT_DIR / entries[0]['file'])}")
    log(f"wrote {tnl.rel(index)}")
    log("NOTE: evidence for a human. Nothing here is written to mapgen/config/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
