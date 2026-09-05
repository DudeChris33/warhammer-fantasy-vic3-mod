"""Geographic renumbering for land-region STATE ids (board #2930 follow-up,
2026-09-05: Chris asked for neighbouring regions to get numerically close ids
after noticing the raw region labels are scattered).

``land_regions_index.json``'s ``region`` field comes straight out of
:func:`worldgen.land_provinces.regions`'s flood-fill discovery order (via
``cells.renumber``), which is stable and deterministic but not geographic —
two regions that share a border can end up numbered, say, 15 and 312. This
module computes a **Hilbert-curve** ordering of region centroids instead, so
walking region ids 1..N in order roughly walks the map. Both
``generate_land_regions.py`` (the emitted ``STATE_LAND_NNN`` keys/ids) and
``render_land_regions_preview.py`` (the on-image numbers + CSV worksheet)
import :func:`compute_state_numbers` so the two can never drift apart — the
number on the render is always the number actually shipped in
``map_data/state_regions/00_norsca.txt``.

This only renumbers the **STATE id/key** #2930 emits. It does not touch
``land_regions_index.json``'s own ``region`` field, ``provinces.png``'s
province colours, or any other committed index — those stay exactly as
``generate_provinces.py`` / ``worldgen.land_provinces`` produce them, so this
module never forces a province-bitmap regen.
"""
from __future__ import annotations

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
