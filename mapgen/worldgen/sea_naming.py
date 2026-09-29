"""Assign each hand-drawn sea zone a Warhammer-canon sea group.

Board #2698, follow-up to the #2593 partition. The 154 zones from
``worldgen.sea_zones.extract`` are numbered placeholders; this gives each one a
canon sea group (the Sea of Claws, the Great Ocean, the Black Gulf, ...) from the
hand-authored seed config ``mapgen/config/sea_zones.json`` (``schema.load_sea_zones``).
:func:`assign` gives every zone a provisional ``STATE_<SEA_GROUP>_NN`` key;
:func:`rekey_by_display_name` then rebuilds each non-merged zone's key from its
own final display name (``STATE_<NAME>_NN``) once :func:`apply_zone_names` has
overlaid the per-zone worksheet names, so the key that lands in ``99_seas.txt``
matches the name a player actually sees rather than its parent sea group.

The assignment is a **per-pixel seed-Voronoi plurality**, deliberately NOT
nearest-seed-of-centroid: the hand-drawn zones are crescent / seam-crossing
coastal shapes whose arithmetic centroid can fall on land or inside another zone.
Instead every canon seed is rasterized, one wrap-aware Euclidean Voronoi
(``cells.fill_nearest``) is grown over the whole water mask, and each zone is
given the canon sea that owns the **plurality** of its pixels. That is robust to
any zone shape and is total by construction — ``fill_nearest`` labels every water
pixel given at least one seed (the schema guarantees ``>= 1``), and every zone
pixel is water.

Everything is deterministic and byte-reproducible (core.md): no RNG, no
dict-order iteration. Plurality ties break to the lower canon index (the authored
order ``load_sea_zones`` preserves), then the lower seed index; the ordinal ``NN``
within a sea orders its zones by their wrap-robust first raster pixel, with the
label id as the final tie-break.
"""

from __future__ import annotations

import re
from typing import NamedTuple

import numpy as np

from worldgen import cells, schema


class SeaZoneName(NamedTuple):
    """The naming a zone label carries into ``sea_zones_index.json``."""

    key: str          # STATE_<SEA_GROUP>_NN
    sea_group: str    # the canon sea's `name` token
    display_name: str  # the shared localized display text


def apply_zone_names(naming: dict[int, "SeaZoneName"], zones: np.ndarray,
                     config: schema.SeaZoneConfig) -> dict[int, "SeaZoneName"]:
    """Overlay the per-zone naming worksheet's individual display names.

    Unlike a merge, this does not touch ``key``/``sea_group`` — a named zone keeps
    its ordinary ``STATE_<group>_NN`` key, only ``display_name`` changes. Applied
    before :func:`apply_naming_overrides` so a merge (which does replace the key)
    still wins for any zone that is both individually named and merged. Raises
    :class:`cells.CellError` if a ``zone_names`` seed is not on a sea zone.
    """
    naming = dict(naming)
    for zn in config.zone_names:
        sx, sy = zn.seed
        lab = int(zones[sy, sx])
        if lab == 0:
            raise cells.CellError(
                f"zone_names seed ({sx}, {sy}) is not on a sea zone (it is on land) — "
                f"the seed is wrong or stale"
            )
        prev = naming[lab]
        naming[lab] = SeaZoneName(key=prev.key, sea_group=prev.sea_group,
                                  display_name=zn.display_name)
    return naming


def apply_naming_overrides(naming: dict[int, "SeaZoneName"], zones: np.ndarray,
                           config: schema.SeaZoneConfig
                           ) -> tuple[dict[int, "SeaZoneName"], set[int], set[int]]:
    """Overlay merge names and the impassable flag onto an :func:`assign` result.

    A "merge" does **not** relabel pixels: fusing separate water bodies into one
    province produces a disconnected province bitmap, which Vic3 rejects (found
    2026-08-31 trying to fuse the three Maelstrom pieces — none of them touch).
    Instead every zone in a :class:`schema.SeaZoneMerge` keeps its own label and
    province colour but is given the *same* key (so the emitter groups them into
    one multi-province ``STATE_<name>``, exactly how vanilla lists several
    province colours under one ``impassable = { ... }`` — see
    ``mapgen/generate_sea_regions.py``) and the same sea_group/display_name.

    Returns the patched naming dict, the set of impassable labels (every zone in
    an ``impassable``-flagged merge, plus every ``impassable_seeds`` pixel), and
    the set of merged labels (every zone folded into a :class:`schema.SeaZoneMerge`
    — :func:`rekey_by_display_name` must leave these alone, since their shared key
    is what groups them into one state, not a per-zone name derivation). Raises
    :class:`cells.CellError` if a merge/impassable seed is not on a sea zone.
    """
    naming = dict(naming)
    impassable: set[int] = set()
    merged: set[int] = set()
    for m in config.merges:
        key = f"STATE_{m.name}_01"
        for (sx, sy) in m.seeds:
            lab = int(zones[sy, sx])
            if lab == 0:
                raise cells.CellError(
                    f"merge '{m.name}' seed ({sx}, {sy}) is not on a sea zone (it is on land) — "
                    f"the seed is wrong or stale"
                )
            naming[lab] = SeaZoneName(key=key, sea_group=m.name, display_name=m.display_name)
            merged.add(lab)
            if m.impassable:
                impassable.add(lab)
    for (sx, sy) in config.impassable_seeds:
        lab = int(zones[sy, sx])
        if lab == 0:
            raise cells.CellError(
                f"impassable seed ({sx}, {sy}) is not on a sea zone (it is on land) — "
                f"the seed is wrong or stale"
            )
        impassable.add(lab)
    return naming, impassable, merged


def _slugify(display_name: str) -> str:
    """``STATE_`` key stem for a display name: upper-case, non-alnum runs -> ``_``."""
    slug = re.sub(r"[^A-Z0-9]+", "_", display_name.upper()).strip("_")
    return slug or "SEA"


def rekey_by_display_name(naming: dict[int, "SeaZoneName"], zones: np.ndarray,
                          skip: set[int]) -> dict[int, "SeaZoneName"]:
    """Replace each zone's ``STATE_<sea_group>_NN`` key with one built from its own
    final ``display_name`` instead of its parent canon sea group.

    Applied last, after :func:`apply_zone_names` has overlaid the per-zone
    worksheet names: without this, an individually named zone (e.g. "Shard
    Coast") kept the key of the generic sea group it was assigned to (e.g.
    ``STATE_SEA_OF_CHILL_01``), so the id in ``99_seas.txt`` and the loc key told
    a different story than the name a player actually sees. ``skip`` (the merged
    labels from :func:`apply_naming_overrides`) is left untouched — a merge's
    shared key is what groups its several zones into one Vic3 state, not a name
    derivation to repeat per zone.

    Several zones can legitimately share a display name (repeated placeholder
    names like "Central Far Ocean Passage"), so the ``NN`` ordinal still
    disambiguates within each name, ordered by the zones' wrap-robust first pixel
    for reproducibility — the same rule :func:`assign` uses within a sea group.
    A name that is not shared gets a bare ``STATE_<NAME>`` key with no ordinal —
    "Shard Coast" is the only Shard Coast, so ``STATE_SHARD_COAST_01`` would
    imply a second one that does not exist.
    """
    naming = dict(naming)
    first = _zone_first_pixel(zones, int(zones.max()))
    groups: dict[str, list[int]] = {}
    for lab, nm in naming.items():
        if lab in skip:
            continue
        groups.setdefault(_slugify(nm.display_name), []).append(lab)
    for slug, labels in groups.items():
        ordered = sorted(labels, key=lambda l: (first[l][0], first[l][1], l))
        if len(ordered) == 1:
            prev = naming[ordered[0]]
            naming[ordered[0]] = SeaZoneName(key=f"STATE_{slug}", sea_group=prev.sea_group,
                                             display_name=prev.display_name)
            continue
        width = max(2, len(str(len(ordered))))
        for ordinal, lab in enumerate(ordered, start=1):
            prev = naming[lab]
            naming[lab] = SeaZoneName(key=f"STATE_{slug}_{ordinal:0{width}d}",
                                      sea_group=prev.sea_group, display_name=prev.display_name)
    return naming


def _seed_owner(sea_labels: np.ndarray, land: np.ndarray,
                config: schema.SeaZoneConfig, wrap_x: bool, log=None) -> np.ndarray:
    """Wrap-aware seed-Voronoi owner (canon index + 1) over the water mask.

    Warns (does not error) if a canon seed rasterizes onto a land pixel: it still
    acts as a Voronoi source, but is probably a mis-pick the author wants to know
    about. The full-width pad guarantees a correct seam fill even though the canon
    seeds are far sparser than the partition's own farthest-point seeds.
    """
    water = ~land
    seed_img = np.zeros(sea_labels.shape, dtype=np.int32)
    for ci, sea in enumerate(config.canon_seas):
        for (sx, sy) in sea.seeds:
            if land[sy, sx] and log:
                log(f"  WARNING: canon seed for {sea.name} at ({sx}, {sy}) is on land — "
                    f"probably a mis-pick; it still seeds the Voronoi")
            seed_img[sy, sx] = ci + 1
    return cells.fill_nearest(seed_img, water, wrap_x, pad=sea_labels.shape[1])


def _zone_first_pixel(sea_labels: np.ndarray, n: int) -> dict[int, tuple[int, int]]:
    """Each zone's first pixel in raster order — its ``(y, x)`` ordinal key.

    ``np.unique(..., return_index=True)`` gives the first flattened index of every
    label, which is exactly the topmost-then-leftmost pixel: a real pixel of the
    zone, so the key does not depend on where the seam is cut.
    """
    flat = sea_labels.ravel()
    uniq, first_idx = np.unique(flat, return_index=True)
    w = sea_labels.shape[1]
    first: dict[int, tuple[int, int]] = {}
    for lab, idx in zip(uniq.tolist(), first_idx.tolist()):
        if lab != 0:
            first[int(lab)] = divmod(int(idx), w)  # (y, x)
    return first


def assign(sea_labels: np.ndarray, land: np.ndarray, config: schema.SeaZoneConfig,
           wrap_x: bool, log=None) -> dict[int, SeaZoneName]:
    """Map every zone label ``1..n`` to its :class:`SeaZoneName`.

    ``sea_labels`` is the ``0``=land / ``1..n``=zone layer; ``land`` the boolean
    land mask; ``config`` the loaded :class:`schema.SeaZoneConfig`. Raises
    :class:`cells.CellError` if an override pixel is not on a sea zone.
    """
    n = int(sea_labels.max())
    owner = _seed_owner(sea_labels, land, config, wrap_x, log=log)

    # Per-zone plurality: bincount the canon owner over the zone's pixels and take
    # the argmax. bincount+argmax returns the lowest index on a tie, which is the
    # lower-canon-index tie-break we want; the authored order gives that meaning.
    n_canon = len(config.canon_seas)
    zone_canon: dict[int, int] = {}
    for lab in range(1, n + 1):
        m = sea_labels == lab
        counts = np.bincount(owner[m], minlength=n_canon + 1)
        counts[0] = 0  # index 0 is "no seed" — cannot happen in water, but be safe
        zone_canon[lab] = int(np.argmax(counts))  # 1-based canon index

    # Overrides: reassign a single zone, keyed on an interior pixel of it.
    for ov in config.overrides:
        ox, oy = ov.zone_seed
        lab = int(sea_labels[oy, ox])
        if lab == 0:
            raise cells.CellError(
                f"sea-zone override at ({ox}, {oy}) is not on a sea zone (it is on land) — "
                f"the seed is wrong or stale"
            )
        ci = next(i for i, s in enumerate(config.canon_seas) if s.name == ov.canon_sea)
        zone_canon[lab] = ci + 1

    # Zero-zone canon seas: a declared sea that won nothing is almost certainly an
    # authoring miss (a seed in the wrong water body), so say so loudly.
    won: dict[int, list[int]] = {i: [] for i in range(1, n_canon + 1)}
    for lab, ci in zone_canon.items():
        won[ci].append(lab)
    if log:
        for i, sea in enumerate(config.canon_seas):
            zones = won[i + 1]
            if not zones:
                log(f"  WARNING: canon sea {sea.name} won 0 zones — likely an authoring miss")
            else:
                log(f"  {sea.name}: {len(zones)} zones")

    # Ordinal NN within each canon sea, ordered by the wrap-robust first pixel.
    first = _zone_first_pixel(sea_labels, n)
    out: dict[int, SeaZoneName] = {}
    for i, sea in enumerate(config.canon_seas):
        zones = sorted(won[i + 1], key=lambda l: (first[l][0], first[l][1], l))
        width = max(2, len(str(len(zones))))
        for ordinal, lab in enumerate(zones, start=1):
            key = f"STATE_{sea.name}_{ordinal:0{width}d}"
            out[lab] = SeaZoneName(key=key, sea_group=sea.name, display_name=sea.display_name)
    return out
