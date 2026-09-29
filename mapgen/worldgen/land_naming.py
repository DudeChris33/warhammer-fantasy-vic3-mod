"""Assign each land STATE region a canon Warhammer realm + display name.

Board #2931, follow-up to the structural land emission in #2930. Two
user-authored inputs drive this, both hand-edited data in the same family as
``mapgen/config/inland_lakes.json`` (edited deliberately, regenerated through,
never inferred from a bitmap):

* ``mapgen/config/land_regions_worksheet.csv`` -- per-STATE canon display names
  (``region_id`` is the Hilbert-ordered STATE number from
  ``worldgen.land_state_numbering.compute_state_numbers``, not the raw
  ``land_regions_index.json`` region label -- see that module's docstring).
* ``sources/terraqueous_globe_reprojected - strategic_regions.png`` -- a flat
  fill painting of realm territory, classified against
  ``mapgen/config/strategic_region_colors.json`` by exact RGB (the flat-fill
  idiom ``worldgen.scope.classify_fills`` already uses for the older
  ``old_world_regions.png``, not the sea side's seed-Voronoi -- the input
  shapes differ). Confirmed 2026-09-05 (image analysis + user correction): the
  painting is a byte-identical top-left crop of the main 8192x3616 canvas
  coordinate frame (zero offset, zero scale -- IoU 0.9999 against the already-
  registered ``state_regions.png`` magenta network), so no seed/TPS
  registration is needed, and the colours themselves are arbitrary MS Paint
  swatch picks carrying no relationship to ``old_world_region_colors.json``.

Realm assignment is a **plurality vote**, not centroid-nearest (mirrors why
``sea_naming.py`` avoids centroid lookups for irregular, elongated shapes):
each region's STATE takes the realm colour that owns the most of its pixels
within the painting's coverage. Every region also gets a confidence margin
(top-two colour-vote fractions) so a close call -- most likely a mis-registered
boundary rather than genuine ambiguity -- is flagged to a review log instead of
shipping silently, since ``validate_map.py`` checks structural totality, not
realm correctness.

A region with **zero** votes (entirely outside the painting's coverage, or
covering only unclassified pixels) is an out-of-scope placeholder by
construction -- ``assign_out_of_scope_continent`` gives it the nearest (wrap-
aware) named continent from ``mapgen/config/out_of_scope_continents.json``
instead of a realm.

Deterministic and RNG-free throughout (core.md): the same inputs always
produce the same assignment.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np

MARKER_RGB = (255, 0, 255)


# ---------------------------------------------------------------------------
# Worksheet names (mapgen/config/land_regions_worksheet.csv)
# ---------------------------------------------------------------------------

#: Trailing parenthetical author annotations -- "(weak)", "(dedup)",
#: "(weak+dedup)", "(tbd)", etc. -- are the user's own authoring notes to
#: themselves, never text to ship in loc or fold into a STATE key. Applied
#: repeatedly since a name could in principle carry more than one such group.
_ANNOTATION_RE = re.compile(r"\s*\([^()]*\)\s*$")


def _strip_annotations(raw: str) -> str:
    prev = raw
    while True:
        stripped = _ANNOTATION_RE.sub("", prev).strip()
        if stripped == prev:
            return stripped
        prev = stripped


class WorksheetNames(NamedTuple):
    """The result of loading the naming worksheet.

    ``names`` is keyed by STATE number (``region_id`` in the CSV) with any
    trailing parenthetical annotation already stripped -- that's the user's
    own authoring note to themselves, not text to ship in loc. ``weak`` lists
    the STATE numbers whose annotation mentioned "weak" (a low-confidence
    flag), for a loremaster review pass to see explicitly rather than the tag
    silently vanishing.
    """

    names: dict[int, str]
    weak: list[int]


def load_worksheet_names(path: Path) -> WorksheetNames:
    """Parse the naming worksheet into STATE number -> canon name.

    Only rows with a non-empty ``name`` contribute -- a blank name (every
    ``on_parchment=False`` out-of-scope placeholder, plus any not-yet-named
    drawn region) is left for the caller's own fallback, never invented here.
    """
    names: dict[int, str] = {}
    weak: list[int] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = (row.get("name") or "").strip()
            if not raw:
                continue
            state_num = int(row["region_id"])
            stripped = _strip_annotations(raw)
            if "weak" in raw.lower() and "weak" not in stripped.lower():
                weak.append(state_num)
            names[state_num] = stripped
    return WorksheetNames(names=names, weak=weak)


# ---------------------------------------------------------------------------
# Colour -> realm legend (mapgen/config/strategic_region_colors.json)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RealmFill:
    rgb: tuple[int, int, int]
    realm: str
    file_stem: str
    continent: str


@dataclass(frozen=True)
class RealmLegend:
    fills: list[RealmFill]
    excluded_rgbs: set[tuple[int, int, int]]
    border_rgb: tuple[int, int, int]

    def rgb_to_index(self) -> dict[tuple[int, int, int], int]:
        """Each configured fill's RGB -> its 1-based index into ``fills``."""
        return {f.rgb: i + 1 for i, f in enumerate(self.fills)}


def load_strategic_region_colors(path: Path) -> RealmLegend:
    data = json.loads(path.read_text(encoding="utf-8"))
    fills = []
    seen: set[tuple[int, int, int]] = set()
    for i, raw in enumerate(data["fills"]):
        rgb = tuple(int(v) for v in raw["rgb"])
        if len(rgb) != 3 or not all(0 <= v <= 255 for v in rgb):
            raise ValueError(f"{path.name}.fills[{i}].rgb: expected an [r, g, b] byte triple, got {rgb!r}")
        if rgb in seen:
            raise ValueError(f"{path.name}: duplicate fill colour {rgb!r}")
        seen.add(rgb)
        fills.append(RealmFill(rgb=rgb, realm=raw["realm"], file_stem=raw["file_stem"],
                               continent=raw["continent"]))
    excluded = {tuple(int(v) for v in e["rgb"]) for e in data.get("excluded", [])}
    if excluded & seen:
        raise ValueError(f"{path.name}: a colour is both a fill and excluded: {excluded & seen}")
    border = tuple(int(v) for v in data["border"]["rgb"])
    realms = [f.realm for f in fills]
    dupes = {r for r in realms if realms.count(r) > 1}
    if dupes:
        raise ValueError(f"{path.name}: duplicate realm name(s) {sorted(dupes)}")
    return RealmLegend(fills=fills, excluded_rgbs=excluded, border_rgb=border)


# ---------------------------------------------------------------------------
# Per-region realm assignment by pixel-plurality vote
# ---------------------------------------------------------------------------

class RealmAssignment(NamedTuple):
    realm: str | None       # None => no vote at all (out-of-scope by construction)
    file_stem: str | None
    continent: str | None
    votes: int              # total classified (non-border/excluded/unmatched) pixels seen
    top_fraction: float      # winning realm's share of `votes` (0.0 if votes == 0)
    margin: float            # (top - runner-up) share of `votes` (0.0 if votes == 0 or 1 realm)


#: Below this vote-share margin between the top two realms, a region's call is
#: close enough to flag for review rather than trust silently (a plurality
#: vote always returns *some* winner even for a straddling/mis-registered
#: region -- see the module docstring).
CONFIDENCE_MARGIN_FLOOR = 0.10


def _classify_pixels(rgb: np.ndarray, legend: RealmLegend) -> np.ndarray:
    """``(H, W)`` int array: each pixel's 1-based fill index (0 = border/excluded/unmatched)."""
    code = ((rgb[..., 0].astype(np.int64) << 16)
            | (rgb[..., 1].astype(np.int64) << 8) | rgb[..., 2].astype(np.int64))
    out = np.zeros(rgb.shape[:2], dtype=np.int64)
    for fill, idx in legend.rgb_to_index().items():
        r, g, b = fill
        out[code == ((r << 16) | (g << 8) | b)] = idx
    return out


def assign_realms(region_of_pixel: np.ndarray, n_regions: int,
                  strategic_rgb: np.ndarray, legend: RealmLegend) -> dict[int, RealmAssignment]:
    """Vote every region's realm from the strategic-regions painting.

    ``region_of_pixel`` is ``(H, W)`` region-id-or-0, already restricted to the
    painting's own coverage rectangle (a top-left crop of the main canvas --
    the caller slices the full-canvas province/region label arrays to this
    image's shape before calling, since no warp is needed). ``n_regions`` is
    the total region count (region ids ``1..n_regions``); regions with no
    pixels in this crop at all get an all-zero vote and thus ``realm=None``.
    """
    fill_idx = _classify_pixels(strategic_rgb, legend)
    mask = (region_of_pixel > 0) & (fill_idx > 0)
    n_fills = len(legend.fills)
    keys = region_of_pixel[mask].astype(np.int64) * (n_fills + 1) + fill_idx[mask]
    uniq, counts = np.unique(keys, return_counts=True)
    votes = np.zeros((n_regions + 1, n_fills + 1), dtype=np.int64)
    votes[uniq // (n_fills + 1), uniq % (n_fills + 1)] = counts

    out: dict[int, RealmAssignment] = {}
    for region_id in range(1, n_regions + 1):
        row = votes[region_id]
        total = int(row.sum())
        if total == 0:
            out[region_id] = RealmAssignment(None, None, None, 0, 0.0, 0.0)
            continue
        order = np.argsort(-row, kind="stable")
        top_idx, second_idx = int(order[0]), int(order[1]) if n_fills > 1 else int(order[0])
        top_count, second_count = int(row[top_idx]), int(row[second_idx])
        fill = legend.fills[top_idx - 1]
        out[region_id] = RealmAssignment(
            realm=fill.realm, file_stem=fill.file_stem, continent=fill.continent,
            votes=total, top_fraction=top_count / total,
            margin=(top_count - second_count) / total,
        )
    return out


def weak_confidence_regions(assignments: dict[int, RealmAssignment]) -> list[int]:
    """Region ids whose plurality margin is below :data:`CONFIDENCE_MARGIN_FLOOR`.

    Excludes regions with ``votes == 0`` (those are out-of-scope, not a close
    call) -- flags only a region that DID get classified but by a thin margin.
    """
    return sorted(r for r, a in assignments.items()
                  if a.realm is not None and a.margin < CONFIDENCE_MARGIN_FLOOR)


# ---------------------------------------------------------------------------
# Out-of-scope continent fallback (nearest-seed, wrap-aware)
# ---------------------------------------------------------------------------

def assign_out_of_scope_continent(region_cx: np.ndarray, region_cy: np.ndarray,
                                  region_ids: list[int], continents: list,
                                  canvas_width: int) -> dict[int, str]:
    """Region id -> nearest out-of-scope continent's raw config ``name`` slug.

    Callers title-case the slug for display and separately map it to a
    ``map_data/state_regions/`` file stem -- this function only answers "which
    continent," not "what does it display as" or "which file."

    Distance is wrap-aware Euclidean from the region's centroid to each
    continent's seed pixel (``x`` wraps at ``canvas_width``, ``y`` does not --
    matching every other x-wrap distance calculation in this pipeline). This is
    a coarser classification than the connected-component + geodesic split
    ``worldgen.scope.collapse_out_of_scope`` does for the *older*
    ``old_world_regions.png`` pipeline (unused by the current magenta-network
    generator, board #2930's own placeholder regions come from interior-magenta
    density, not that seed collapse) -- adequate here since this only drives a
    cosmetic display name for an out-of-scope placeholder state, not gameplay
    geometry.
    """
    out: dict[int, str] = {}
    half = canvas_width / 2.0
    for rid in region_ids:
        cx, cy = float(region_cx[rid]), float(region_cy[rid])
        best_name = None
        best_d2 = None
        for cont in continents:
            sx, sy = cont.seed
            dx = abs(cx - sx)
            if dx > half:
                dx = canvas_width - dx
            dy = cy - sy
            d2 = dx * dx + dy * dy
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_name = cont.name
        out[rid] = best_name
    return out


# ---------------------------------------------------------------------------
# Canon name resolution
# ---------------------------------------------------------------------------

def canon_name_for(state_num: int, worksheet: WorksheetNames,
                   out_of_scope_name: str | None) -> str | None:
    """The name to ship for this STATE, or ``None`` to keep the AUTOGEN fallback.

    The worksheet always wins when it has a name (the user's own naming pass is
    the source of truth, never re-derived). Otherwise an out-of-scope
    placeholder gets its continent's plain display name. A drawn, in-scope
    region with neither is a real content gap -- left ``None`` so the caller's
    existing ``AUTOGEN_MARKER`` fallback still applies and the gap stays
    visible rather than being silently invented.
    """
    name = worksheet.names.get(state_num)
    if name:
        return name
    return out_of_scope_name


# ---------------------------------------------------------------------------
# STATE key derivation from worksheet names
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^A-Z0-9]+")


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("_", name.upper()).strip("_")
    return slug or "STATE"


def derive_state_keys(worksheet: WorksheetNames) -> dict[int, str]:
    """STATE number -> ``STATE_<SLUG>`` for every worksheet-named region.

    User decision 2026-09-05: a named region's key comes from its own worksheet
    name (annotations already stripped by :func:`load_worksheet_names`), not
    the numeric ``STATE_LAND_NNN`` placeholder -- mirrors
    ``sea_naming.rekey_by_display_name``'s reasoning (the key a player-facing
    tool or save file shows should match the name they actually see). Applies
    only to STATE numbers present in ``worksheet.names`` -- an unnamed region
    (out-of-scope placeholder, or a real naming gap) keeps its numeric key,
    since there is no name to derive one from.

    Two different names can slugify to the same key (punctuation/case
    differences); a colliding group gets an ordinal suffix
    (``STATE_<SLUG>_01``, ``_02``, ...) ordered by STATE number for
    reproducibility, while a unique slug gets the bare key with no ordinal.
    """
    groups: dict[str, list[int]] = {}
    for state_num, name in worksheet.names.items():
        groups.setdefault(_slugify(name), []).append(state_num)
    out: dict[int, str] = {}
    for slug, state_nums in groups.items():
        if len(state_nums) == 1:
            out[state_nums[0]] = f"STATE_{slug}"
            continue
        for ordinal, state_num in enumerate(sorted(state_nums), start=1):
            out[state_num] = f"STATE_{slug}_{ordinal:02d}"
    return out
