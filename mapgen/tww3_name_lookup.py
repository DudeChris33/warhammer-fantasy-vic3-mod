#!/usr/bin/env python3
"""Point-sample a canvas location to a TWW3 canon region name (board #4363).

**Dev-only, gitignored output, not wired into any generator.** This writes only
to ``mapgen/derived/`` and never to ``mapgen/config/`` — it produces *suggestions
for a human to review*, which is the whole design: board #4363's acceptance
criteria make human review mandatory before any name reaches a worksheet, so
this script deliberately has no path that edits committed naming data.

What it does
------------
``sources/cr_oldworld_campaign/cr_oldworld_lookup/cr_oldworld_lookup.bmp`` is
TWW3's region partition of the Old World, one flat colour per region, keyed by
``cr_oldworld_campaign.tsv``. That bitmap shares the 8192-px campaign-map frame,
which is the 4096-px parchment master at exactly 2x (established by board
#4364). So a canvas pixel resolves to a canon name through the existing
``tww3_old_world_mod_parchment_full`` registration plus one scale factor::

    canvas px --(fit.to_source_px)--> master px --(x LOOKUP_SCALE)--> lookup px
             --> flat colour --> TSV row --> canon region key

Point-sampling, not raster warping. ``mapgen/render_cr_lookup_overlay.py``
(#4364) warps the whole partition for a visual verdict; this samples a handful
of points. Same transform, far less to go wrong: #4364 measured a repeatable
**dx = +1 lookup px** resample-convention bias between the campaign map and the
parchment master (~0.2 canvas px through this registration), which matters for a
pixel-accurate raster comparison and is nothing at all for a point that lands
hundreds of px inside a region. This script therefore uses the same
``LOOKUP_OFFSET_X = 0`` as #4364, and reports the per-sample distance to the
nearest differently-coloured pixel (``margin_px``) so a sample that IS near a
boundary is visible as such rather than quietly trusted.

Scope filter (Chris, 2026-09-12)
--------------------------------
**Land not drawn in ``sources/originals/tww3_old_world_mod_parchment_cropped.png``
is out of scope for naming.** That file is the same 4096² master frame carrying
the same art (verified: mean abs difference 0.0001 over 20k opaque samples,
versus 28.8 at a 7-px shift), with everything this mod does not cover erased to
alpha 0 — 13.5% of the frame, in an irregular interior shape, so its full-image
bounding box is useless and the **alpha channel** is the only real extent. A
sample that resolves perfectly well but lands on an erased pixel is reported
``out-of-scope`` and never becomes a suggestion. This is a second, distinct
exclusion from ``outside``: ``outside`` means the registration could not place
the point at all, ``out-of-scope`` means it placed fine on ground this mod does
not name.

PROVISIONAL FOUNDATION
----------------------
``mapgen/registration/tww3_old_world_mod_parchment_full.json`` marks itself
"PROVISIONAL until the user accepts the diagnostic render". Every coordinate
this prints inherits that. If the placement moves, every suggestion here moves
with it — which is another reason nothing is auto-written.

Modes::

    python mapgen/tww3_name_lookup.py --anchors-only          # sample worksheet anchors
    python mapgen/tww3_name_lookup.py --anchors-only --worksheet mapgen/config/land_regions_worksheet.csv
    python mapgen/tww3_name_lookup.py --regions               # per-region footprint vote
    python mapgen/tww3_name_lookup.py --propose-hubs          # reverse: TSV key -> canvas
    python mapgen/tww3_name_lookup.py --at 4091 898           # one point
    python mapgen/tww3_name_lookup.py --city-dots --state-file 02_empire   # dots -> names (#3666)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import reproject, schema, tww3_names  # noqa: E402

# The lookup is 8192x8193, far past Pillow's decompression-bomb guard — which is
# aimed at hostile uploads, not at local reference art whose dimensions this
# script asserts explicitly before using.
Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
SOURCES_DIR = REPO_ROOT / "sources"
DERIVED_DIR = TOOLS_DIR / "derived"
CONFIG_DIR = TOOLS_DIR / "config"
REGISTRATION_DIR = TOOLS_DIR / "registration"

#: Reference data, gitignored and absent on most
#: devices — see :func:`require_dataset` for the clean skip.
DATASET_DIR = SOURCES_DIR / "cr_oldworld_campaign"
LOOKUP_BMP = DATASET_DIR / "cr_oldworld_lookup" / "cr_oldworld_lookup.bmp"
LOOKUP_TSV = DATASET_DIR / "cr_oldworld_lookup" / "cr_oldworld_campaign.tsv"

#: The registration record this samples through (PROVISIONAL — see above).
FULL_SOURCE = "tww3_old_world_mod_parchment_full.png"
#: The naming-scope authority (Chris, 2026-09-12): the same master frame and the
#: same art as ``FULL_SOURCE``'s own source, with every area this mod does not
#: cover erased to alpha 0. Its **alpha channel** is the extent — the opaque
#: region is an irregular interior shape whose bounding box is the whole image.
SCOPE_SOURCE = "tww3_old_world_mod_parchment_cropped.png"
#: The master frame the registration places, in master px.
MASTER_SIZE = 4096
#: Master px -> lookup px. Confirmed by board #4364 (FFT phase correlation,
#: scale sweep decisive at 2.00, zero offset).
LOOKUP_SCALE = 2.0
LOOKUP_SIZE = int(MASTER_SIZE * LOOKUP_SCALE)
#: The bitmap is 8192x**8193** and it is a genuine tie which row is padding (row
#: 0 duplicates row 1, row 8192 duplicates row 8191). Dropping row 0 matches
#: ``mapgen/render_cr_lookup_overlay.py`` — the two scripts MUST agree or they
#: would disagree about the same pixel. The residual ambiguity is 1 lookup px
#: = 0.5 master px, far below what point-sampling a region interior can care
#: about, and reported by ``margin_px`` where it could matter.
DROP_ROW = 0
#: Deliberately 0, matching #4364: the measured +1 lookup px is a resample
#: convention, ~0.2 canvas px here, disclosed rather than silently applied.
LOOKUP_OFFSET_X = 0

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

#: Default worksheet for ``--anchors-only``: the **current** derived cut written
#: by ``mapgen/render_land_regions_preview.py``, not the committed
#: ``mapgen/config/`` copy. The two can disagree on the region set (they did at
#: the time of this board item: 376 rows here vs 369 there), and the current cut
#: is what any new naming has to attach to.
DEFAULT_WORKSHEET = DERIVED_DIR / "land_regions_worksheet.csv"
CONFIG_WORKSHEET = CONFIG_DIR / "land_regions_worksheet.csv"

PROVINCES_PATH = REPO_ROOT / "map_data" / "provinces.png"
PROVINCES_INDEX_PATH = DERIVED_DIR / "provinces_index.json"
LAND_REGIONS_INDEX_PATH = DERIVED_DIR / "land_regions_index.json"

NAME_SUGGESTIONS_CSV = DERIVED_DIR / "tww3_name_suggestions.csv"
HUB_SUGGESTIONS_CSV = DERIVED_DIR / "tww3_hub_suggestions.csv"

#: The citation string a reviewer copies into the worksheet's ``source`` column
#: when they accept a suggestion. One format, generated in one place.
SOURCE_TEMPLATE = "canon: cr_oldworld_campaign/{slug} (TWW3 Old World mod region table)"

#: ``--propose-hubs`` deny list: key prefixes that are TWW3 *gameplay* landmarks,
#: not settlements, and would be nonsense as a Victoria 3 hub name.
#:
#: * ``monolith_`` — the Norscan monolith mechanic's capture points (25 keys with
#:   this prefix, 33 keys mentioning a monolith). A battlefield objective, not a
#:   town.
#: * ``wreck_of_`` — shipwreck landmark sites (``wreck_of_the_unsinkable`` and
#:   friends, 11 keys). Named flotsam, not a place anyone lives.
#:
#: Everything else is left in and flagged for review rather than guessed at: the
#: table also carries ``castle_``, ``fort_``, ``temple_``, ``tower_``, ``camp``
#: and ``circle_of_`` keys, and those ARE plausible settlements/holds in this
#: setting (``castle_drakenhof``, ``karak_*``), so filtering by those prefixes
#: would throw away real names. The reviewer is the filter for those.
HUB_DENY_PREFIXES = ("monolith_", "wreck_of_")

#: ``--propose-hubs`` unanimity ring: eight points at this lookup-px radius
#: around a candidate centroid must all sample the same key, or the row is
#: flagged ``ambiguous`` rather than proposed. 16 lookup px = 8 master px is a
#: comfortable multiple of both the row tie and the +1 offset bias.
UNANIMITY_RADIUS_LOOKUP_PX = 16
#: How far out ``margin_px`` looks for a differently-coloured pixel before
#: reporting ">= this". Bounds the cost; anything past it is "well inside".
MARGIN_PROBE_MAX_LOOKUP_PX = 64


def log(msg: str = "") -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Dataset presence
# ---------------------------------------------------------------------------

def require_dataset() -> None:
    """Clean-skip when the reference dataset is not on this device.

    The ``validate_map._check_canon_cities`` idiom: a gitignored local working
    file's absence is the expected state on every device but Chris's, so this
    exits 0 with a plain explanation rather than raising.
    """
    if DATASET_DIR.is_dir() and LOOKUP_BMP.is_file() and LOOKUP_TSV.is_file():
        return
    log(f"{rel(DATASET_DIR)}: reference dataset not present on this "
        f"device — dev-only lookup, skipping")
    sys.exit(0)


# ---------------------------------------------------------------------------
# The lookup itself
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Sample:
    """One resolved point.

    ``status`` is one of:

    * ``ok``       — landed on a colour with a TSV row (``region`` is set)
    * ``water``    — landed on void black: the campaign map's sea / off-map
    * ``unkeyed``  — landed on a real colour that has **no** TSV row (colour
      ``600954`` is the known large one, board #4364)
    * ``outside``  — the canvas point is outside the registration's master frame
    * ``out-of-scope`` — placed fine, but on ground erased from
      :data:`SCOPE_SOURCE`: land this mod does not cover, never a suggestion
    """

    status: str
    region: tww3_names.TWW3Region | None
    hex: str | None
    margin_px: float


class Lookup:
    """The bitmap + TSV + registration, loaded once and sampled many times."""

    def __init__(self, buffer_px: float = 0.0) -> None:
        regs = {r.source: r for r in schema.load_registrations(REGISTRATION_DIR)}
        if FULL_SOURCE not in regs:
            raise SystemExit(
                f"{FULL_SOURCE}: no committed registration record — run "
                f"mapgen/fit_registration.py --seed tww3_old_world_mod_parchment_full")
        self.reg = regs[FULL_SOURCE]
        # fit_placement, never fit_warp: this record is a piecewise_affine_warp
        # and fit_warp refuses that kind outright.
        self.fit = reproject.fit_placement(self.reg, regs, buffer_px=buffer_px)
        self._inverse = None  # lazily fitted; only --propose-hubs needs it

        self.regions = tww3_names.load_tww3_regions(LOOKUP_TSV)
        self.index = tww3_names.colour_index(self.regions)
        self.water = tww3_names.water_name_bank(self.regions)
        self.arr = self._load_bitmap()
        self.scope = self._load_scope_mask()

    @staticmethod
    def _load_scope_mask() -> np.ndarray:
        """``(4096, 4096)`` bool: True where this mod's naming scope covers the
        master frame, read from :data:`SCOPE_SOURCE`'s alpha channel.

        Required, not optional: without it every out-of-scope sample would be
        silently proposed as a name. A palette+transparency PNG is converted via
        ``RGBA`` rather than read raw, so the transparency reaches the alpha band
        however Pillow stored it.
        """
        from worldgen import sources as sources_mod
        path = sources_mod.resolve_source_path(SCOPE_SOURCE, SOURCES_DIR)
        if not path.is_file():
            raise SystemExit(
                f"sources/{SCOPE_SOURCE} is missing — it is the naming-scope "
                f"authority (Chris, 2026-09-12: land not drawn there is out of scope) "
                f"and this script must not suggest names without it")
        with Image.open(path) as im:
            if im.size != (MASTER_SIZE, MASTER_SIZE):
                raise SystemExit(
                    f"{SCOPE_SOURCE} is {im.size[0]}x{im.size[1]}, expected "
                    f"{MASTER_SIZE}x{MASTER_SIZE} — the scope mask must share the "
                    f"master frame this registration places")
            alpha = np.asarray(im.convert("RGBA"), dtype=np.uint8)[..., 3]
        return alpha > 0

    @staticmethod
    def _load_bitmap() -> np.ndarray:
        with Image.open(LOOKUP_BMP) as im:
            w, h = im.size
            if (w, h) != (LOOKUP_SIZE, LOOKUP_SIZE + 1):
                raise SystemExit(
                    f"{LOOKUP_BMP.name} is {w}x{h}, expected {LOOKUP_SIZE}x"
                    f"{LOOKUP_SIZE + 1}. A different size is a different export and "
                    f"every scale/row constant in this script would be wrong for it.")
            arr = np.asarray(im.convert("RGB"), dtype=np.uint8)
        keep = np.arange(arr.shape[0]) != DROP_ROW
        return np.ascontiguousarray(arr[keep])

    @property
    def inverse(self):
        if self._inverse is None:
            self._inverse = reproject.fit_placement_inverse(self.reg)
        return self._inverse

    # -- coordinate plumbing ------------------------------------------------

    def to_lookup_px(self, cx, cy):
        """Canvas px -> ``(lookup x, lookup y, inside, in_scope)``.

        ``inside`` is "the registration placed this point in the master frame";
        ``in_scope`` is "and that master pixel is drawn in :data:`SCOPE_SOURCE`".
        They are separate on purpose — see the scope-filter note in the module
        docstring. ``in_scope`` is False wherever ``inside`` is False.
        """
        mx, my = self.fit.to_source_px(np.asarray(cx, dtype=np.float64),
                                       np.asarray(cy, dtype=np.float64))
        inside = (np.isfinite(mx) & np.isfinite(my)
                  & (mx >= 0) & (mx <= MASTER_SIZE - 1)
                  & (my >= 0) & (my <= MASTER_SIZE - 1))
        mxi = np.clip(np.rint(np.where(inside, mx, 0.0)), 0, MASTER_SIZE - 1).astype(np.int64)
        myi = np.clip(np.rint(np.where(inside, my, 0.0)), 0, MASTER_SIZE - 1).astype(np.int64)
        in_scope = inside & self.scope[myi, mxi]
        lx = np.clip(np.rint(mx * LOOKUP_SCALE) + LOOKUP_OFFSET_X, 0, LOOKUP_SIZE - 1)
        ly = np.clip(np.rint(my * LOOKUP_SCALE), 0, LOOKUP_SIZE - 1)
        return lx.astype(np.int64), ly.astype(np.int64), inside, in_scope

    def master_in_scope(self, mx: float, my: float) -> bool:
        """Is this master-frame point inside the naming scope?"""
        if not (0 <= mx <= MASTER_SIZE - 1 and 0 <= my <= MASTER_SIZE - 1):
            return False
        return bool(self.scope[int(round(my)), int(round(mx))])

    def hex_at_lookup(self, lx: int, ly: int) -> str:
        r, g, b = self.arr[ly, lx]
        return f"{int(r):02X}{int(g):02X}{int(b):02X}"

    # -- the actual lookup --------------------------------------------------

    def name_at(self, canvas_x: float, canvas_y: float, margin: bool = True) -> Sample:
        """Resolve one canvas point to a TWW3 region (see :class:`Sample`)."""
        lx, ly, inside, in_scope = self.to_lookup_px(canvas_x, canvas_y)
        if not bool(inside):
            return Sample("outside", None, None, 0.0)
        if not bool(in_scope):
            # Placed fine, but on ground erased from the cropped parchment —
            # deliberately reported before the colour is consulted, so an
            # out-of-scope point can never leave here carrying a name.
            return Sample("out-of-scope", None, None, 0.0)
        hx = self.hex_at_lookup(int(lx), int(ly))
        m = self._margin(int(lx), int(ly), hx) if margin else float("nan")
        if hx == tww3_names.WATER_HEX:
            return Sample("water", None, hx, m)
        region = self.index.get(hx)
        if region is None:
            return Sample("unkeyed", None, hx, m)
        return Sample("ok", region, hx, m)

    def _margin(self, lx: int, ly: int, hx: str) -> float:
        """Distance (lookup px) to the nearest differently-coloured pixel.

        Answers "is this sample deep inside a region, or right on an edge" —
        the only place the ±1 px frame ambiguities could flip an answer. Probes
        growing square rings and stops at
        :data:`MARGIN_PROBE_MAX_LOOKUP_PX` (reported as that value, i.e. "well
        inside"), so the cost is bounded.
        """
        target = np.array([int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)],
                          dtype=np.uint8)
        for r in range(1, MARGIN_PROBE_MAX_LOOKUP_PX + 1):
            x0, x1 = max(0, lx - r), min(LOOKUP_SIZE, lx + r + 1)
            y0, y1 = max(0, ly - r), min(LOOKUP_SIZE, ly + r + 1)
            block = self.arr[y0:y1, x0:x1]
            if not np.all(block == target):
                return float(r)
        return float(MARGIN_PROBE_MAX_LOOKUP_PX)

    def unanimous(self, lx: int, ly: int, hx: str,
                  radius: int = UNANIMITY_RADIUS_LOOKUP_PX) -> bool:
        """Do eight points on a ring of ``radius`` all carry colour ``hx``?"""
        offs = [(radius, 0), (-radius, 0), (0, radius), (0, -radius),
                (radius, radius), (radius, -radius), (-radius, radius), (-radius, -radius)]
        for dx, dy in offs:
            px, py = lx + dx, ly + dy
            if not (0 <= px < LOOKUP_SIZE and 0 <= py < LOOKUP_SIZE):
                return False
            if self.hex_at_lookup(px, py) != hx:
                return False
        return True


def source_citation(region: tww3_names.TWW3Region) -> str:
    return SOURCE_TEMPLATE.format(slug=region.slug)


# ---------------------------------------------------------------------------
# Name agreement (a deliberately rough heuristic)
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase alphanumeric words, for a coarse name comparison."""
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text.lower()).split())


def agrees(worksheet_name: str, slug: str) -> bool:
    """Does the sampled TSV slug plausibly refer to the worksheet's own name?

    A **rough heuristic, reported as such**: either normalized string contains
    the other, or they share a word of 4+ characters. It is there to answer
    "does this reference map broadly agree with the naming pass already done",
    not to decide any individual name — every accepted name goes through a human.
    """
    a, b = _normalize(worksheet_name), _normalize(slug)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    aw = {w for w in a.split() if len(w) >= 4}
    bw = {w for w in b.split() if len(w) >= 4}
    return bool(aw & bw)


# ---------------------------------------------------------------------------
# Region label raster (only the region-aware modes need it)
# ---------------------------------------------------------------------------

def load_region_labels() -> tuple[np.ndarray, dict[int, int]]:
    """Per-pixel land-region label layer + region -> area.

    Reuses ``render_land_regions_preview._build_region_labels`` verbatim rather
    than re-deriving the province -> region mapping, so this can never disagree
    with the render or the generator about which region owns a pixel.
    """
    for path in (PROVINCES_PATH, PROVINCES_INDEX_PATH, LAND_REGIONS_INDEX_PATH):
        if not path.is_file():
            raise SystemExit(f"{path} not found — run generate_provinces.py / "
                             f"generate_land_regions.py first")
    import render_land_regions_preview as rlp
    from worldgen import raster

    prov_index = json.loads(PROVINCES_INDEX_PATH.read_text(encoding="utf-8"))
    land_regions = json.loads(LAND_REGIONS_INDEX_PATH.read_text(encoding="utf-8"))
    rgb = raster.read_rgb_png(PROVINCES_PATH)
    lab = rlp._build_region_labels(rgb, prov_index["cells"], land_regions["cells"],
                                   int(prov_index["land_provinces"]))
    areas = {int(c["region"]): int(c["area"]) for c in land_regions["cells"]}
    return lab, areas


# ---------------------------------------------------------------------------
# Mode: --anchors-only
# ---------------------------------------------------------------------------

def rel(path: Path) -> str:
    """``path`` relative to the repo root when it is under it, else as given.

    A user-supplied ``--worksheet`` may be a relative path or point outside the
    repo; logging must not be the thing that fails.
    """
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def read_worksheet(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"{path} not found")
    with path.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run_anchors(lookup: Lookup, worksheet: Path) -> int:
    """Point-sample every worksheet anchor and report resolve + agreement rates.

    The cheap mode, and the one board #4363's Step 0 re-measurement runs: an
    anchor is one point, so this is ~400 samples rather than a 30-megapixel
    per-region vote.
    """
    rows = read_worksheet(worksheet)
    log(f"worksheet         {rel(worksheet)}  ({len(rows)} rows)")

    out: list[dict] = []
    counts = {"ok": 0, "water": 0, "unkeyed": 0, "outside": 0, "out-of-scope": 0}
    named = 0
    agreed = 0
    by_kind: dict[str, list[int]] = {}
    for row in rows:
        try:
            ax, ay = int(float(row["anchor_x"])), int(float(row["anchor_y"]))
        except (KeyError, TypeError, ValueError):
            raise SystemExit(f"{worksheet.name}: row {row.get('region_id')!r} has no usable anchor")
        s = lookup.name_at(ax, ay)
        counts[s.status] += 1
        name = (row.get("name") or "").strip()
        kind = row.get("kind", "")
        tally = by_kind.setdefault(kind, [0, 0, 0])  # [rows, resolved, agreed]
        tally[0] += 1
        tally[1] += s.status == "ok"
        ok_agree = False
        if name:
            named += 1
            if s.status == "ok" and agrees(name, s.region.slug):
                agreed += 1
                tally[2] += 1
                ok_agree = True
        out.append({
            "region_id": row.get("region_id", ""),
            "worksheet_name": name,
            "kind": kind,
            "anchor_x": ax,
            "anchor_y": ay,
            "status": s.status,
            "tww3_key": s.region.key if s.region else "",
            "tww3_slug": s.region.slug if s.region else "",
            "hex": s.hex or "",
            "margin_lookup_px": "" if s.margin_px != s.margin_px else f"{s.margin_px:.0f}",
            "agrees": "yes" if ok_agree else ("no" if name and s.status == "ok" else ""),
            "source": source_citation(s.region) if s.region else "",
        })

    total = len(rows)
    log("")
    log("anchor sample report")
    log(f"  anchors           {total}")
    log(f"  resolved (ok)     {counts['ok']} ({100.0 * counts['ok'] / total:.1f}%) — "
        f"landed on a colour with a TSV key")
    log(f"  water             {counts['water']} — void black: campaign-map sea / off-map")
    log(f"  unkeyed           {counts['unkeyed']} — a real colour with NO TSV row "
        f"(600954 is the known large one, board #4364)")
    log(f"  outside footprint {counts['outside']} — canvas point outside the "
        f"{FULL_SOURCE} master frame")
    log(f"  out of scope      {counts['out-of-scope']} — placed fine, but on ground "
        f"erased from {SCOPE_SOURCE}: land this mod does not cover (Chris, 2026-09-12)")
    log(f"  unmatched hex     0 — by construction: an exact-hex point sample is keyed, "
        f"unkeyed, water, out of scope or outside; there is no sixth outcome")
    log(f"  worksheet-named   {named} row(s) carry a name")
    if named:
        log(f"  name agreement    {agreed}/{named} ({100.0 * agreed / named:.1f}%) — "
            f"ROUGH heuristic (substring or a shared 4+-char word), not a verdict "
            f"on any individual name")
    else:
        log(f"  name agreement    n/a — this worksheet carries NO names, so agreement "
            f"cannot be measured against it")
    log("  by kind:")
    for kind, (n, res, agr) in sorted(by_kind.items()):
        log(f"    {kind:<12} {n:>4} rows   resolved {res:>4} "
            f"({100.0 * res / n if n else 0:.1f}%)   agreed {agr}")

    write_csv(NAME_SUGGESTIONS_CSV, out)
    return 0


# ---------------------------------------------------------------------------
# Mode: --regions (full footprint plurality vote)
# ---------------------------------------------------------------------------

def run_regions(lookup: Lookup, worksheet: Path, top: int = 3, step: int = 4) -> int:
    """Plurality vote over each land region's whole footprint.

    Heavier and more robust than ``--anchors-only``: a region whose centroid
    happens to sit on a neighbour's ground still votes correctly. ``step``
    subsamples the canvas grid (every 4th px by default) — at 8192x3616 that is
    ~1.9M points, plenty for a plurality and 16x cheaper than every pixel.
    Reports the top ``top`` candidates with each one's vote fraction, plus the
    **margin** between first and second, which is what says whether the vote was
    decisive or a coin flip.
    """
    lab, areas = load_region_labels()
    n_regions = int(lab.max())
    log(f"region labels     {n_regions} regions from the current province cut")

    ys, xs = np.mgrid[0:CANVAS_H:step, 0:CANVAS_W:step]
    ys = ys.ravel()
    xs = xs.ravel()
    region_of = lab[ys, xs]
    keep = region_of > 0
    ys, xs, region_of = ys[keep], xs[keep], region_of[keep]
    log(f"vote points       {ys.size:,} land samples (every {step}th px)")

    lx, ly, inside, in_scope = lookup.to_lookup_px(xs, ys)
    # -1 = outside the master frame, -2 = placed but out of naming scope. Both are
    # kept as votes rather than dropped, so a region that is MOSTLY out of scope
    # wins "(out of scope)" and is visibly not a naming candidate.
    packed = np.full(ys.size, -1, dtype=np.int64)
    packed[inside & ~in_scope] = -2
    block = lookup.arr[ly[in_scope], lx[in_scope]]
    packed[in_scope] = ((block[:, 0].astype(np.int64) << 16)
                        | (block[:, 1].astype(np.int64) << 8) | block[:, 2].astype(np.int64))

    votes: dict[int, dict[int, int]] = {}
    order = np.argsort(region_of, kind="stable")
    region_sorted = region_of[order]
    packed_sorted = packed[order]
    bounds = np.searchsorted(region_sorted, np.arange(1, n_regions + 2))
    for r in range(1, n_regions + 1):
        chunk = packed_sorted[bounds[r - 1]:bounds[r]]
        if chunk.size == 0:
            votes[r] = {}
            continue
        vals, cnts = np.unique(chunk, return_counts=True)
        votes[r] = {int(v): int(c) for v, c in zip(vals.tolist(), cnts.tolist())}

    names = {}
    for row in read_worksheet(worksheet):
        try:
            names[int(row["region_id"])] = (row.get("name") or "").strip()
        except (KeyError, ValueError):
            continue

    out: list[dict] = []
    decisive = 0
    for r in range(1, n_regions + 1):
        tally = votes[r]
        total = sum(tally.values()) or 1
        ranked = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
        cand: list[tuple[str, float]] = []
        for val, cnt in ranked:
            if val == -1:
                label = "(outside footprint)"
            elif val == -2:
                label = "(out of scope)"
            else:
                hx = f"{val:06X}"
                if hx == tww3_names.WATER_HEX:
                    label = "(water/void)"
                else:
                    reg = lookup.index.get(hx)
                    label = reg.slug if reg else f"(unkeyed {hx})"
            cand.append((label, cnt / total))
        margin = (cand[0][1] - cand[1][1]) if len(cand) > 1 else cand[0][1] if cand else 0.0
        decisive += bool(cand) and margin >= 0.25
        top_reg = None
        if ranked and ranked[0][0] >= 0:
            top_reg = lookup.index.get(f"{ranked[0][0]:06X}")
        in_scope_frac = 1.0 - (tally.get(-1, 0) + tally.get(-2, 0)) / total
        out.append({
            "region_id": r,
            "worksheet_name": names.get(r, ""),
            "area_px": areas.get(r, 0),
            "candidate_1": cand[0][0] if cand else "",
            "fraction_1": f"{cand[0][1]:.3f}" if cand else "",
            "candidate_2": cand[1][0] if len(cand) > 1 else "",
            "fraction_2": f"{cand[1][1]:.3f}" if len(cand) > 1 else "",
            "candidate_3": cand[2][0] if len(cand) > 2 else "",
            "fraction_3": f"{cand[2][1]:.3f}" if len(cand) > 2 else "",
            "margin": f"{margin:.3f}",
            "in_scope_fraction": f"{in_scope_frac:.3f}",
            "source": source_citation(top_reg) if top_reg else "",
        })

    log(f"  decisive votes    {decisive}/{n_regions} regions won by >= 0.25 of the vote")
    write_csv(NAME_SUGGESTIONS_CSV, out)
    return 0


# ---------------------------------------------------------------------------
# Mode: --propose-hubs (reverse: TSV key -> canvas point -> land region)
# ---------------------------------------------------------------------------

def run_propose_hubs(lookup: Lookup) -> int:
    """Reverse lookup: where on this mod's map does each TWW3 region sit?

    For each keyed colour: its centroid in the bitmap, mapped source -> canvas
    by the registration's inverse, resolved to a land region. Three guards, all
    of which **flag or skip** rather than crash:

    * ``ambiguous`` — the eight-point unanimity ring around the centroid does not
      all read the same key. A crescent or ring-shaped region's centroid can land
      on a neighbour; this catches that without needing the region's full mask.
    * ``centroid-outside-region`` — the centroid pixel itself is not that
      region's colour. Same failure, detected directly.
    * ``no-land-region`` — the canvas point resolves to no land region of this
      mod's own cut (sea, or off the drawn map).

    Plus the scope filter: a centroid whose master pixel is erased from
    :data:`SCOPE_SOURCE` is dropped from the report entirely (counted as
    ``out-of-scope``), because it names land this mod does not cover.
    """
    deny_hits: list[str] = []
    keyed = []
    for hx, reg in lookup.index.items():
        if reg.slug.startswith(HUB_DENY_PREFIXES):
            deny_hits.append(reg.slug)
            continue
        keyed.append((hx, reg))
    log(f"TSV keys          {len(lookup.index)} keyed regions, "
        f"{len(deny_hits)} filtered as gameplay-only "
        f"(prefixes {list(HUB_DENY_PREFIXES)}), {len(keyed)} proposed")

    # Centroids: a compact int32 LUT maps the 2^24 packed colour space onto the
    # ~1.3k colours we care about, so the accumulation is three bincounts over
    # small arrays per row block rather than a 67-megapixel unique/inverse.
    lut = np.zeros(1 << 24, dtype=np.int32)
    for i, (hx, _reg) in enumerate(keyed):
        lut[int(hx, 16)] = i + 1
    n = len(keyed)
    cnt = np.zeros(n + 1, dtype=np.int64)
    sx = np.zeros(n + 1, dtype=np.float64)
    sy = np.zeros(n + 1, dtype=np.float64)
    BLOCK = 512
    for y0 in range(0, LOOKUP_SIZE, BLOCK):
        y1 = min(y0 + BLOCK, LOOKUP_SIZE)
        blk = lookup.arr[y0:y1]
        packed = ((blk[..., 0].astype(np.int64) << 16)
                  | (blk[..., 1].astype(np.int64) << 8) | blk[..., 2].astype(np.int64))
        idx = lut[packed].ravel()
        gy, gx = np.mgrid[y0:y1, 0:LOOKUP_SIZE]
        cnt += np.bincount(idx, minlength=n + 1)
        sx += np.bincount(idx, weights=gx.ravel().astype(np.float64), minlength=n + 1)
        sy += np.bincount(idx, weights=gy.ravel().astype(np.float64), minlength=n + 1)
    del lut

    lab, _areas = load_region_labels()
    inverse = lookup.inverse

    out: list[dict] = []
    stats = {"ok": 0, "ambiguous": 0, "centroid-outside-region": 0,
             "no-land-region": 0, "absent": 0, "out-of-scope": 0}
    for i, (hx, reg) in enumerate(keyed):
        slot = i + 1
        if cnt[slot] == 0:
            stats["absent"] += 1
            continue
        lx = int(round(sx[slot] / cnt[slot]))
        ly = int(round(sy[slot] / cnt[slot]))
        # Scope first: an out-of-scope region never reaches the report at all,
        # so no reviewer can accept a name for land this mod does not cover.
        if not lookup.master_in_scope(lx / LOOKUP_SCALE, ly / LOOKUP_SCALE):
            stats["out-of-scope"] += 1
            continue
        status = "ok"
        if lookup.hex_at_lookup(lx, ly) != hx:
            status = "centroid-outside-region"
        elif not lookup.unanimous(lx, ly, hx):
            status = "ambiguous"
        mx, my = lx / LOOKUP_SCALE, ly / LOOKUP_SCALE
        cx, cy = inverse.to_canvas_px(np.array([mx]), np.array([my]))
        cxi, cyi = int(round(float(cx[0]))), int(round(float(cy[0])))
        region_id = 0
        if 0 <= cxi < CANVAS_W and 0 <= cyi < CANVAS_H:
            region_id = int(lab[cyi, cxi])
        if region_id == 0 and status == "ok":
            status = "no-land-region"
        stats[status] += 1
        out.append({
            "tww3_key": reg.key,
            "tww3_slug": reg.slug,
            "hex": hx,
            "area_lookup_px": int(cnt[slot]),
            "anchor_x": cxi,
            "anchor_y": cyi,
            "land_region_id": region_id,
            "status": status,
            "source": source_citation(reg),
        })

    log("")
    log("hub proposal report")
    log(f"  proposable        {stats['ok']} (centroid unambiguous AND inside a land region)")
    log(f"  ambiguous         {stats['ambiguous']} (unanimity ring disagreed — review by hand)")
    log(f"  centroid off-reg  {stats['centroid-outside-region']} (non-convex region; "
        f"its centroid is not its own colour)")
    log(f"  no land region    {stats['no-land-region']} (canvas point is not land in "
        f"this mod's own cut)")
    log(f"  absent from bmp   {stats['absent']} (TSV key with zero pixels in the bitmap)")
    log(f"  out of scope      {stats['out-of-scope']} (centroid erased from "
        f"{SCOPE_SOURCE} — dropped from the report, never proposable)")
    log(f"  filtered          {len(deny_hits)} gameplay-only keys: "
        f"{sorted(deny_hits)[:6]}{' ...' if len(deny_hits) > 6 else ''}")
    log("  NOTE: every row here is a SUGGESTION. Nothing is written to "
        "mapgen/config/hub_worksheet.json by this script, by design (#4363 makes "
        "human review mandatory).")
    write_csv(HUB_SUGGESTIONS_CSV, out)
    return 0


# ---------------------------------------------------------------------------
# Mode: --city-dots (forward: each painted city dot -> state + TWW3 name, #3666)
# ---------------------------------------------------------------------------

STATE_REGIONS_DIR = REPO_ROOT / "map_data" / "state_regions"
STATES_LOC = REPO_ROOT / "localization" / "replace" / "english" / "map" / "states_l_english.yml"
LAND_SEA_MASK_PATH = DERIVED_DIR / "land_sea_mask.png"
ARABLE_PATH = DERIVED_DIR / "arable_heatmap.png"
HEIGHTMAP_PATH = REPO_ROOT / "map_data" / "heightmap.png"


def city_dots_csv_path(stem: str) -> Path:
    return DERIVED_DIR / f"tww3_city_dots_{stem}.csv"


def run_city_dots(lookup: Lookup, state_file: Path | None) -> int:
    """Forward-sample every painted city dot (``full.ora#cities``, the same
    :func:`land_provinces.city_dots` anchors ``generate_provinces.py`` seeds) and
    report, per dot: owning state (off the committed ``state_regions/*.txt``),
    province hex, coastal flag, arable (16-bit heatmap) and height, plus the TWW3
    region it samples to. The hub-drafting name bank for the realm children of
    #3663 (board #3666).

    **Read-only**: writes only the gitignored
    ``mapgen/derived/tww3_city_dots_<stem>.csv``; never ``mapgen/config/``. A
    ``dedupe`` flag marks dots that sample the same TWW3 region (one canon name,
    several dots — a human picks which dot carries it). ``--state-file`` limits the
    report to the states of one state-regions file.
    """
    import re

    import validate_map as vm
    from worldgen import land_provinces, raster, sources as sources_mod

    cities_ref = sources_mod.source_ref("cities")
    rgba = sources_mod.read_source_rgba(cities_ref, allow_empty=True)
    if rgba is None:
        log(f"{cities_ref}: cities layer not present on this device — skipping")
        return 0
    land = raster.read_mask_png(LAND_SEA_MASK_PATH)
    dots = land_provinces.city_dots(rgba, land)
    del rgba
    log(f"city dots         {len(dots)} on land ({cities_ref})")

    prov = raster.read_rgb_png(PROVINCES_PATH)
    prov_index = json.loads(PROVINCES_INDEX_PATH.read_text(encoding="utf-8"))
    cell_of = {tuple(int(v) for v in c["color"]): c for c in prov_index["cells"]}
    arable = raster.read_gray16_png(ARABLE_PATH) if ARABLE_PATH.is_file() else None
    with Image.open(HEIGHTMAP_PATH) as im:
        height = np.asarray(im)
    if height.ndim == 3:
        height = height[..., 0]

    files = sorted(STATE_REGIONS_DIR.glob("*.txt"))
    if state_file is not None:
        want = state_file.stem if state_file.suffix else str(state_file)
        files = [f for f in files if f.stem == Path(want).stem]
        if not files:
            raise SystemExit(f"--state-file {state_file}: no such file in {rel(STATE_REGIONS_DIR)}")
    state_of: dict[tuple[int, int, int], tuple[str, str]] = {}
    for f in files:
        for st in vm.parse_state_file(f):
            for col in st.provinces:
                state_of[tuple(col)] = (st.key, f.stem)
    names: dict[str, str] = {}
    if STATES_LOC.is_file():
        for m in re.finditer(r'^\s*(STATE_\w+):\d*\s+"([^"]*)"',
                             STATES_LOC.read_text(encoding="utf-8-sig"), re.M):
            names[m.group(1)] = m.group(2)

    out: list[dict] = []
    for x, y in dots:
        col = tuple(int(v) for v in prov[y, x])
        owner = state_of.get(col)
        if owner is None:
            continue  # not in the filtered file(s), or not a land state
        key, stem = owner
        cell = cell_of.get(col, {})
        s = lookup.name_at(x, y)
        out.append({
            "state_key": key,
            "state_name": names.get(key, ""),
            "state_file": stem,
            "anchor_x": x,
            "anchor_y": y,
            "province_hex": raster.color_to_hex(col),
            "coastal": "yes" if cell.get("coastal") else "no",
            "impassable": "yes" if cell.get("impassable") else "no",
            "arable": int(arable[y, x]) if arable is not None else "",
            "height": int(height[y, x]),
            "status": s.status,
            "tww3_slug": s.region.slug if s.region else "",
            "margin_lookup_px": "" if s.margin_px != s.margin_px else f"{s.margin_px:.0f}",
            "dedupe": "",
            "source": source_citation(s.region) if s.region else "",
        })
    by_slug: dict[str, int] = {}
    for r in out:
        if r["tww3_slug"]:
            by_slug[r["tww3_slug"]] = by_slug.get(r["tww3_slug"], 0) + 1
    for r in out:
        if r["tww3_slug"] and by_slug[r["tww3_slug"]] > 1:
            r["dedupe"] = f"shared-by-{by_slug[r['tww3_slug']]}"
    out.sort(key=lambda r: (r["state_file"], r["state_key"], r["anchor_y"], r["anchor_x"]))
    n_states = len({r["state_key"] for r in out})
    log(f"  dots reported     {len(out)} in {n_states} state(s); "
        f"{sum(1 for r in out if r['status'] == 'ok')} resolve to a TWW3 region, "
        f"{sum(1 for r in out if r['dedupe'])} share a region with another dot")
    log("  NOTE: suggestions only — nothing is written to mapgen/config/.")
    stem = files[0].stem if state_file is not None and len(files) == 1 else "all"
    write_csv(city_dots_csv_path(stem), out)
    return 0


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        log(f"nothing to write to {rel(path)}")
        return
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    log(f"wrote {rel(path)}  ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--anchors-only", action="store_true",
                      help="point-sample every land-region worksheet anchor (cheap; the "
                           "board #4363 Step 0 measurement)")
    mode.add_argument("--regions", action="store_true",
                      help="plurality-vote each land region's whole footprint (heavier, "
                           "more robust than a single anchor point)")
    mode.add_argument("--propose-hubs", action="store_true",
                      help="reverse lookup: each TWW3 key's centroid -> a canvas anchor "
                           "+ the land region it falls in")
    mode.add_argument("--at", nargs=2, type=int, metavar=("X", "Y"),
                      help="resolve one canvas pixel and print the result")
    mode.add_argument("--city-dots", action="store_true",
                      help="forward-sample every painted city dot -> state, province, "
                           "coastal/arable/height + TWW3 name (board #3666); writes "
                           "mapgen/derived/tww3_city_dots_<stem>.csv")
    p.add_argument("--state-file", type=Path, default=None,
                   help="--city-dots: only dots in this map_data/state_regions file "
                        "(path or stem, e.g. 02_empire)")
    p.add_argument("--worksheet", type=Path, default=DEFAULT_WORKSHEET,
                   help=f"land-region worksheet to sample (default the CURRENT derived "
                        f"cut, {DEFAULT_WORKSHEET.name} in mapgen/derived/, not the "
                        f"committed mapgen/config/ copy)")
    p.add_argument("--step", type=int, default=4,
                   help="--regions grid subsample stride in canvas px (default 4)")
    p.add_argument("--hull-buffer-px", type=float, default=0.0,
                   help="extrapolate this many canvas px past the outer hull edge "
                        "(default 0 — the strict footprint; a sample past the hull is "
                        "reported 'outside' rather than guessed)")
    args = p.parse_args(argv)

    require_dataset()
    lookup = Lookup(buffer_px=args.hull_buffer_px)
    log(f"registration      {FULL_SOURCE} ({lookup.reg.projection}, "
        f"{len(lookup.reg.control_points)} control points) — PROVISIONAL per its own "
        f"record; every coordinate here inherits that")
    log(f"region table      {len(lookup.regions)} rows, {len(lookup.index)} keyed "
        f"colours, {len(lookup.water)} water/coast names (not sampled)")
    log(f"naming scope      {SCOPE_SOURCE} alpha: {100.0 * lookup.scope.mean():.1f}% of "
        f"the master frame is in scope; anything outside it is reported "
        f"'out-of-scope' and never suggested")

    if args.at:
        s = lookup.name_at(args.at[0], args.at[1])
        log("")
        log(f"canvas ({args.at[0]}, {args.at[1]}): {s.status}"
            + (f" -> {s.region.key} (slug '{s.region.slug}', colour {s.hex}, "
               f"{s.margin_px:.0f} lookup px from the nearest edge)" if s.region
               else (f" (colour {s.hex})" if s.hex else "")))
        if s.region:
            log(f"  citation: {source_citation(s.region)}")
        return 0
    if args.regions:
        return run_regions(lookup, args.worksheet, step=args.step)
    if args.propose_hubs:
        return run_propose_hubs(lookup)
    if args.city_dots:
        return run_city_dots(lookup, args.state_file)
    return run_anchors(lookup, args.worksheet)


if __name__ == "__main__":
    raise SystemExit(main())
