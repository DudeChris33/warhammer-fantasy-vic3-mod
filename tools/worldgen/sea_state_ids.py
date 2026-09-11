"""Stable sea-zone STATE id + key assignment across map regens (board #4191).

The sea mirror of :mod:`worldgen.province_ids` (#3705) and
:mod:`worldgen.land_state_numbering` (#4188). Each sea zone emitted by
``generate_sea_zones.py`` carries a STATE ``id`` (the vanilla 3000+ band) and a
``STATE_<NAME>_NN`` ``key`` into ``sea_zones_index.json``, which
``generate_sea_regions.py`` turns into ``99_seas.txt`` / ``default.map``
``sea_starts`` / ``water_strategic_regions.txt`` / the sea loc, and which
``generate_land_regions.py`` reads for each coastal land state's
``naval_exit_id``. The pre-#4191 generator assigned both **by raster label
order** (``id = SEA_ID_START + label - 1``, and ``sea_naming.rekey_by_display_name``
numbering by first-pixel raster order), so removing a single zone slid every
higher zone's id, key and per-canon-sea ordinal down by one — rewriting
``99_seas.txt`` wholesale and, because the land side's ``naval_exit_id`` points
at these ids, leaving residual churn in ``state_regions/*.txt`` even after #4188.

:func:`assign` makes a regenerated sea cut **honour** the committed one, exactly
as ``province_ids.assign`` does for province colours+ids:

- **Matched** (best-overlap, greedy-bijective) current zone → the committed
  zone's ``id``; and its ``key`` **verbatim** *when its display name is
  unchanged* (so the ordinal + bare/``_NN`` form are preserved → zero churn). A
  geometry-unchanged zone overlaps its committed twin 100%, matches trivially,
  and keeps both.
- **Unmatched** current zone (genuinely new geometry) → a fresh ``id`` strictly
  above a monotonic ``sea_id_high_water``, and a fresh ``key`` in its
  display-name slug group off a per-slug ``ordinal_high_water``.
- **Renamed** matched zone (matched geometry, changed ``display_name``) → keeps
  its committed ``id`` (geometry unchanged) but **re-derives** its key (intended,
  localized churn — that is a deliberate config rename, not a raster shift).
- **Retired** committed zone (no current zone matched it) → its id, key and
  ordinal never reappear; the two high-waters never regress, so a retired id or
  key is a permanent gap.

**Identity is zone-layer pixel overlap** — the current ``sea_zones.png`` labels
matched against the committed ``sea_zones.png`` labels — *not* the stable sea
province id. ``generate_sea_zones.py`` runs **before** ``generate_provinces.py``,
so it does not yet hold this run's stable sea province ids; the only current-run
geometry it has is its own label array. This is the faithful analogue of
``province_ids.assign`` (which matches the current label layer against the
committed ``provinces.png``), and equivalent in practice to keying on the stable
sea province id, because ``generate_provinces.py`` folds each ``sea_zones.png``
label 1:1 into one sea province of identical pixels — the two overlap matches run
over the same pixel sets, and ``generate_sea_regions._join_colors``'s
area-consistency guard fails loudly if they ever diverge.

**Merges.** A :class:`schema.SeaZoneMerge` gives every member zone the same
config-driven key ``STATE_<merge>_01`` (``sea_naming.apply_naming_overrides``),
and ``rekey_by_display_name`` deliberately skips merged zones. This module keeps
each merged zone's config key untouched (``merged`` is passed in) and only
stabilises its **id** by geometry match — which keeps the group's ``min(id)``
(what the emitter uses) stable, so the land side's ``naval_exit_id`` stays put.

**Bootstrap / reassign.** With no committed baseline (the very first generation
and every fixture), either committed input ``None``, or ``reassign=True``,
:func:`assign` allocates fresh in label order exactly as the pre-#4191 generator
did (``id = SEA_ID_START + label - 1``, keys = the ``rekey_by_display_name``
output verbatim) — byte-identical, the deliberate escape hatch that pairs with a
province/land ``--reassign``. A non-empty committed index that matches **zero**
current zones (the un-paired-``--reassign`` signature) falls back to this branch
with a loud ``log`` warning rather than retiring every zone silently.

Pure and deterministic: a function of the current labels + current naming +
committed labels + committed index only, with no RNG and a fully-specified tie
order (overlap desc, then current label asc, then committed label asc; fresh ids
in ascending current-label order; fresh keys in per-slug first-pixel order) — no
dict/set iteration leaks into an id or key choice, so two dev machines produce
byte-identical output. Reading the committed baseline as a generator *input* does
not threaten multiplayer sync (which is about the committed *output* being
identical across clients, not the dev-side generation process).
"""
from __future__ import annotations

import sys

import numpy as np

from . import sea_naming


def _ordinal_of(key: str, display_name: str) -> int:
    """Read a committed/bootstrap key's ordinal in its **display-name slug** group.

    Recovery is by ``_slugify(display_name)`` prefix-strip, never blind
    trailing-``_\\d+`` parsing (board #4191 challenge #3): a display name ending
    in a digit — e.g. "Far Passage 3" → ``STATE_FAR_PASSAGE_3`` — has slug
    ``FAR_PASSAGE_3`` and is a **bare** key (ordinal 1), not slug ``FAR_PASSAGE``
    ordinal 3. A bare ``STATE_<slug>`` counts as ordinal 1; anything that does not
    match this zone's own display-slug prefix (e.g. a merge key whose stem is the
    merge name) counts as ordinal 1 too — conservative, only ever risks a harmless
    over-count of a slug's high-water, never an under-count that could reissue a
    retired ordinal.
    """
    slug = sea_naming._slugify(display_name)
    bare = f"STATE_{slug}"
    if key == bare:
        return 1
    prefix = bare + "_"
    if key.startswith(prefix):
        suffix = key[len(prefix):]
        if suffix.isdigit():
            return int(suffix)
    return 1


def _seed_ordinal_high_water(cells) -> dict[str, int]:
    """Bootstrap ``ordinal_high_water`` from committed/current cells.

    Iterates **every** cell (merged included — harmless: a merge's slug can only
    over-count, never under-count) and, per display-name slug, records
    ``max(ordinal) + 1``. This is what makes a slug whose zones were all *removed*
    stay "known" so a new same-slug zone is numbered off the high-water instead of
    reusing the retired bare/``_NN`` key.
    """
    ohw: dict[str, int] = {}
    for cell in cells:
        slug = sea_naming._slugify(cell["display_name"])
        ordinal = _ordinal_of(cell["key"], cell["display_name"])
        ohw[slug] = max(ohw.get(slug, 0), ordinal + 1)
    return ohw


def _fresh_key(slug: str, ordinal: int) -> str:
    return f"STATE_{slug}_{ordinal:0{max(2, len(str(ordinal)))}d}"


def assign(
    zones: np.ndarray,
    naming: dict[int, "sea_naming.SeaZoneName"],
    merged: set[int],
    committed_labels: np.ndarray | None,
    committed_index: dict | None,
    sea_id_start: int,
    *,
    reassign: bool = False,
    log=None,
):
    """Assign a stable ``(id_of_label, key_of_label, sea_id_high_water,
    ordinal_high_water)`` for the current sea-zone label layer.

    ``zones``: the current ``(H, W)`` sea-zone label array, ``1..n`` (0 = land) —
    exactly what ``sea_zones.extract`` produces.

    ``naming``: current per-label :class:`sea_naming.SeaZoneName` (post
    ``rekey_by_display_name``) — supplies each zone's ``display_name`` (the match
    name-change test and the fresh-key slug source), ``sea_group``, and its
    provisional ``key`` (used verbatim only in the bootstrap branch and for
    merged zones).

    ``merged``: the set of merged labels (from
    ``sea_naming.apply_naming_overrides``) — their keys are config-derived; this
    module keeps ``naming[label].key`` for them and only stabilises their id.

    ``committed_labels``: the committed ``sea_zones.png`` label array, or ``None``.

    ``committed_index``: the parsed committed ``sea_zones_index.json`` (its
    ``cells`` give committed ``label -> {id, key, display_name}``; its optional
    ``sea_id_high_water`` / ``ordinal_high_water`` carry forward), or ``None``.

    ``sea_id_start``: ``map_config.SEA_ID_START`` (the 3000 band base).

    ``reassign`` / either committed input ``None`` selects the bootstrap branch.

    ``log``: optional ``str -> None`` for the loud zero-overlap / size-mismatch
    warning; silent if omitted.

    Returns ``id_of_label`` (``{label: int}``), ``key_of_label`` (``{label:
    str}``), ``sea_id_high_water`` (the next unused id, to persist) and
    ``ordinal_high_water`` (``{slug: next ordinal}``, to persist).
    """
    n = int(zones.max())
    first = sea_naming._zone_first_pixel(zones, n)

    def _bootstrap():
        id_of = {lab: sea_id_start + lab - 1 for lab in range(1, n + 1)}
        key_of = {lab: naming[lab].key for lab in range(1, n + 1)}
        ohw = _seed_ordinal_high_water(
            [{"key": naming[lab].key, "display_name": naming[lab].display_name}
             for lab in range(1, n + 1)]
        )
        return id_of, key_of, sea_id_start + n, ohw

    committed_cells = (committed_index or {}).get("cells") or []
    if reassign or committed_labels is None or committed_index is None or not committed_cells:
        return _bootstrap()

    if committed_labels.shape != zones.shape:
        msg = (
            f"sea_state_ids.assign: committed sea_zones.png {committed_labels.shape} != "
            f"current {zones.shape} — a resized canvas invalidates pixel overlap; falling "
            f"back to a fresh label-order bootstrap. Re-seed the index deliberately."
        )
        (log or (lambda m: print(f"WARNING: {m}", file=sys.stderr)))(msg)
        return _bootstrap()

    # committed label -> its cell record (id / key / display_name).
    cell_of_committed = {int(c["label"]): c for c in committed_cells}

    # --- Overlap tally: (current label, committed label) -> pixel count ---
    new_flat = zones.ravel().astype(np.int64)
    com_flat = committed_labels.ravel().astype(np.int64)
    valid = (new_flat > 0) & (com_flat > 0)
    stride = int(com_flat.max()) + 1
    combined = new_flat[valid] * stride + com_flat[valid]
    ucomb, counts = np.unique(combined, return_counts=True)
    cur_arr = (ucomb // stride).tolist()
    com_arr = (ucomb % stride).tolist()

    # Candidate matches: (overlap, current label, committed label). Fully-specified
    # tie order (overlap desc, current label asc, committed label asc) — a strict
    # total order, mirroring province_ids.assign; no set/dict leak.
    candidates: list[tuple[int, int, int]] = []
    for cur, com, cnt in zip(cur_arr, com_arr, counts.tolist()):
        if com in cell_of_committed:
            candidates.append((cnt, cur, com))
    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))

    label_to_committed: dict[int, int] = {}
    committed_taken: set[int] = set()
    for _cnt, cur, com in candidates:
        if cur in label_to_committed or com in committed_taken:
            continue
        label_to_committed[cur] = com
        committed_taken.add(com)

    # Zero-overlap collapse -> bootstrap fallback + loud warning (mirrors
    # land_state_numbering's safety net); never a silent retire-all-and-renumber.
    if not label_to_committed:
        msg = (
            f"sea_state_ids.assign matched ZERO zones against a non-empty "
            f"{len(committed_cells)}-zone committed index — the signature of an un-paired "
            f"province/sea `--reassign` (every zone's pixels look brand-new). Falling back "
            f"to a fresh label-order bootstrap instead of retiring every zone. If this was "
            f"a deliberate reassign, re-run generate_sea_zones.py with --reassign."
        )
        (log or (lambda m: print(f"WARNING: {m}", file=sys.stderr)))(msg)
        return _bootstrap()

    # --- ids: matched keep committed id; unmatched get fresh above high-water ---
    committed_ids = [int(c["id"]) for c in committed_cells]
    next_id = max(committed_ids) + 1 if committed_ids else sea_id_start
    persisted_hw = committed_index.get("sea_id_high_water")
    if persisted_hw is not None:
        next_id = max(next_id, int(persisted_hw))

    id_of: dict[int, int] = {}
    for lab in range(1, n + 1):
        com = label_to_committed.get(lab)
        if com is not None:
            id_of[lab] = int(cell_of_committed[com]["id"])
        else:
            id_of[lab] = next_id
            next_id += 1

    # --- keys ---
    # ordinal_high_water: prefer the persisted dict, then fold in every committed
    # slug (first fixed run / defensive) so a retired slug stays known and monotonic.
    ohw: dict[str, int] = dict(committed_index.get("ordinal_high_water") or {})
    for slug, hw in _seed_ordinal_high_water(committed_cells).items():
        ohw[slug] = max(ohw.get(slug, 0), hw)

    key_of: dict[int, str] = {}
    fresh_labels: list[int] = []      # non-merged labels needing a fresh key
    for lab in range(1, n + 1):
        if lab in merged:
            key_of[lab] = naming[lab].key           # config-driven, already stable
            continue
        com = label_to_committed.get(lab)
        if com is not None and cell_of_committed[com]["display_name"] == naming[lab].display_name:
            key_of[lab] = cell_of_committed[com]["key"]   # verbatim: unchanged zone
        else:
            fresh_labels.append(lab)                 # new zone, or renamed

    # Group fresh labels by current display slug; issue keys deterministically.
    fresh_groups: dict[str, list[int]] = {}
    for lab in fresh_labels:
        fresh_groups.setdefault(sea_naming._slugify(naming[lab].display_name), []).append(lab)
    for slug in sorted(fresh_groups):
        labs = sorted(fresh_groups[slug], key=lambda l: (first[l][0], first[l][1], l))
        if slug in ohw:
            # Known slug (live verbatim member, or a now-retired one): always
            # numbered off the high-water — never a bare key that could collide
            # with or reuse a retired one.
            for lab in labs:
                ordinal = ohw[slug]
                key_of[lab] = _fresh_key(slug, ordinal)
                ohw[slug] = ordinal + 1
        else:
            # Brand-new slug this run: rekey_by_display_name's all-or-nothing rule
            # over the fresh members alone -> byte-identical to a bootstrap of the
            # same geometry (board #4191 challenge #2).
            if len(labs) == 1:
                key_of[labs[0]] = f"STATE_{slug}"
                ohw[slug] = 2
            else:
                width = max(2, len(str(len(labs))))
                for ordinal, lab in enumerate(labs, start=1):
                    key_of[lab] = f"STATE_{slug}_{ordinal:0{width}d}"
                ohw[slug] = len(labs) + 1

    return id_of, key_of, next_id, ohw
