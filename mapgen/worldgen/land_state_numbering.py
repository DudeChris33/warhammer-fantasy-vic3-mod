"""Geographic renumbering for land-region STATE ids (board #2930 follow-up,
2026-09-05: Chris asked for neighbouring regions to get numerically close ids
after noticing the raw region labels are scattered) — and, since board #4188,
**stable** STATE-number assignment across regens, mirroring board #3705's
province-id stability.

``land_regions_index.json``'s ``region`` field comes straight out of
:func:`worldgen.land_provinces.regions`'s flood-fill discovery order (via
``cells.renumber``), which is stable and deterministic but not geographic —
two regions that share a border can end up numbered, say, 15 and 312.
:func:`compute_state_numbers` computes a **Hilbert-curve** ordering of region
centroids instead, so walking region ids 1..N in order roughly walks the map.
It is a pure function of *only the current run's* centroids, so it renumbers
**every** region fresh each time — inserting or removing even one region
shifts nearly every other region's Hilbert rank, which is board #4188's bug
(a tiny land edit rewrites almost every ``state_regions/*.txt`` file, and
because ``land_naming.derive_state_keys``/``load_worksheet_names`` key canon
names off the number, silently reattaches names to the wrong region).

:func:`assign_state_numbers` fixes that the same way ``worldgen.province_ids``
fixed province colour+id: it keys each region's identity on its **stable
province-id set** (already stable per #3705) and overlap-matches it against a
committed record (``mapgen/derived/land_state_ids.json``) — an unchanged region
keeps its number, a genuinely new region gets a fresh number off a monotonic
high-water, and a removed region's number is retired for good rather than
being handed to whatever used to come after it. ``compute_state_numbers``
remains the bootstrap/fresh-numbering primitive :func:`assign_state_numbers`
falls back to when there is no committed index (the very first generation, an
explicit ``reassign``, or fixtures), and it is still what orders newly-issued
numbers among themselves.

Both ``generate_land_regions.py`` (the emitted ``STATE_LAND_NNN`` keys/ids,
which writes ``land_state_ids.json``) and ``render_land_regions_preview.py``
(the on-image numbers + CSV worksheet, which reads it read-only) call
:func:`assign_state_numbers` on **identical raw (unsnapped) region centroids**
so the two can never drift apart — the number on the render is always the
number actually shipped in ``map_data/state_regions/*.txt``.

This only renumbers the **STATE id/key** #2930 emits. It does not touch
``land_regions_index.json``'s own ``region`` field, ``provinces.png``'s
province colours, or any other committed index — those stay exactly as
``generate_provinces.py`` / ``worldgen.land_provinces`` produce them, so this
module never forces a province-bitmap regen.
"""
from __future__ import annotations

import sys

import numpy as np

from . import raster

#: 2**HILBERT_ORDER must cover the canvas's larger dimension. 8192x3616 needs
#: 2**13 = 8192.
HILBERT_ORDER = 13


def compute_state_numbers(region_cx: np.ndarray, region_cy: np.ndarray, n_regions: int) -> np.ndarray:
    """``state_number[region_label] -> 1..n_regions``, Hilbert-ordered by each
    region's canvas centroid.

    ``region_cx``/``region_cy`` are indexed by region label ``1..n_regions``
    (as returned by the same circular-mean centroid estimator
    ``generate_land_regions.py`` already computes for hub placement) — index 0
    is unused. Deterministic and a pure function of the centroids: two runs
    over the same input produce byte-identical output.
    """
    labels = np.arange(1, n_regions + 1)
    d = np.array([raster.hilbert_index(region_cx[r], region_cy[r], HILBERT_ORDER) for r in labels])
    order = np.argsort(d, kind="stable")  # index into `labels`, Hilbert-ascending
    state_number = np.zeros(n_regions + 1, dtype=np.int64)
    for rank, idx in enumerate(order, start=1):
        state_number[int(labels[idx])] = rank
    return state_number


def _hilbert_rank_order(region_cx: np.ndarray, region_cy: np.ndarray, region_ids: list[int]) -> list[int]:
    """``region_ids`` (a subset of region labels) sorted Hilbert-ascending by
    centroid — used to order freshly-issued STATE numbers among themselves."""
    if not region_ids:
        return []
    d = np.array([raster.hilbert_index(region_cx[r], region_cy[r], HILBERT_ORDER) for r in region_ids])
    order = np.argsort(d, kind="stable")
    return [region_ids[i] for i in order.tolist()]


def assign_state_numbers(
    region_cx: np.ndarray,
    region_cy: np.ndarray,
    n_regions: int,
    region_province_ids: dict[int, set[int]],
    province_area: dict[int, int],
    committed_index: dict | None,
    *,
    reassign: bool = False,
    log=None,
) -> tuple[np.ndarray, dict]:
    """Stable ``(state_number, new_index)`` for the current region cut (board #4188).

    ``region_cx``/``region_cy``/``n_regions``: as :func:`compute_state_numbers` —
    the raw (unsnapped) per-region centroids, indexed ``1..n_regions``.

    ``region_province_ids``: region label -> its set of **stable** province ids
    (``worldgen.province_ids.assign``'s ``id``, not the transient cut-order
    ``label``) — this run's identity for the region.

    ``province_area``: stable province id -> its current pixel area (the
    overlap weight — mirrors ``province_ids.assign``'s pixel-overlap tally).

    ``committed_index``: the parsed ``land_state_ids.json``
    (``{"state_number_high_water": int, "states": [{"state_number": int,
    "province_ids": [int, ...]}, ...]}``), or ``None``.

    ``reassign``: force the bootstrap branch (fresh ``compute_state_numbers``
    order) even when a committed index exists — the deliberate escape hatch
    after a wholesale province ``--reassign`` (mirrors
    ``worldgen.province_ids.assign``'s own ``reassign`` flag).

    ``log``: optional ``str -> None`` callable for a loud warning when the
    committed-index match collapses to zero (see below); silent if omitted.

    Returns ``state_number`` (``(n_regions + 1,)`` int64, index 0 unused — the
    same shape :func:`compute_state_numbers` returns) and ``new_index`` — the
    ``land_state_ids.json`` body to persist (the caller adds its own
    ``"canvas"`` key).

    **Bootstrap** (``reassign`` or no committed states): pure
    :func:`compute_state_numbers` order — byte-identical to the pre-#4188
    behaviour. High-water is ``n_regions + 1``.

    **Matched**: an area-weighted greedy-bijective overlap match between the
    current regions' stable province-id sets and the committed states' — a
    region overlapping a committed state's province ids keeps that state's
    number. Fully-specified tie order (overlap desc, then current region label
    asc, then committed state number asc — a strict total order, mirroring
    ``province_ids.assign``), so two runs (and a shuffled committed-state list)
    produce byte-identical output.

    **Unmatched** (genuinely new regions): fresh numbers issued in ascending
    Hilbert-rank order starting at ``max(committed high-water, max committed
    number + 1)`` — so newly-issued numbers are still geographically sensible
    relative to each other, and a first-ever generation (bootstrap) reproduces
    the same order fresh numbers would get here.

    **Retired**: a committed state with no current match simply does not
    appear in ``new_index`` — its number is never reused this run.

    **Safety net**: a non-empty committed index but **zero** matched regions
    is the total-overlap-collapse signature of an un-paired province
    ``--reassign`` (every province id changed, so every region's identity
    looks brand new) — falling through to "everything is new" would retire
    every state and detach every worksheet-carried canon name. Instead this
    falls back to the bootstrap branch and calls ``log`` with a loud warning
    telling the operator to re-run with ``--reassign`` (or that a paired
    reassign happened) — never a silent retire-all-and-renumber.
    """

    def _bootstrap() -> tuple[np.ndarray, dict]:
        numbers = compute_state_numbers(region_cx, region_cy, n_regions)
        states = [
            {"state_number": int(numbers[r]), "province_ids": sorted(region_province_ids.get(r, ()))}
            for r in range(1, n_regions + 1)
        ]
        return numbers, {"state_number_high_water": n_regions + 1, "states": states}

    committed_states = (committed_index or {}).get("states") or []
    if reassign or not committed_states:
        return _bootstrap()

    committed_pids = [set(int(x) for x in s["province_ids"]) for s in committed_states]
    committed_numbers = [int(s["state_number"]) for s in committed_states]

    # Candidate matches: (overlap, current region label, committed number).
    # Fully-specified tie order — a strict total order, no dict/set leak.
    candidates: list[tuple[int, int, int]] = []
    for r in range(1, n_regions + 1):
        pids = region_province_ids.get(r)
        if not pids:
            continue
        for ci, cpids in enumerate(committed_pids):
            shared = pids & cpids
            if not shared:
                continue
            overlap = sum(province_area.get(pid, 0) for pid in shared)
            if overlap > 0:
                candidates.append((overlap, r, committed_numbers[ci]))
    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))

    region_to_number: dict[int, int] = {}
    number_taken: set[int] = set()
    for _overlap, r, num in candidates:
        if r in region_to_number or num in number_taken:
            continue
        region_to_number[r] = num
        number_taken.add(num)

    if not region_to_number:
        msg = (
            "assign_state_numbers matched ZERO regions against a non-empty "
            f"{len(committed_states)}-state committed index — this is the signature of "
            "an un-paired province `--reassign` (every province id looks brand-new, so "
            "every region's identity does too). Falling back to a fresh bootstrap "
            "renumber instead of retiring every state. If this really was a deliberate "
            "province reassign, re-run this generator with --reassign to make it "
            "explicit and reseed the index."
        )
        if log:
            log(msg)
        else:
            print(f"WARNING: {msg}", file=sys.stderr)
        return _bootstrap()

    committed_high_water = int((committed_index or {}).get("state_number_high_water", 0))
    max_committed_number = max(committed_numbers) if committed_numbers else 0
    next_number = max(committed_high_water, max_committed_number + 1)

    unmatched = [r for r in range(1, n_regions + 1) if r not in region_to_number]
    for r in _hilbert_rank_order(region_cx, region_cy, unmatched):
        region_to_number[r] = next_number
        next_number += 1

    state_number = np.zeros(n_regions + 1, dtype=np.int64)
    for r, num in region_to_number.items():
        state_number[r] = num

    new_states = [
        {"state_number": int(state_number[r]), "province_ids": sorted(region_province_ids.get(r, ()))}
        for r in range(1, n_regions + 1)
    ]
    return state_number, {"state_number_high_water": next_number, "states": new_states}
