"""Inland lakes — the third water class, split out of the world ocean.

Board #3742. Victoria 3 knows three kinds of province: land, navigable ``ocean``
and inland ``lakes`` (declared in ``map_data/default.map``'s ``lakes = { }`` block
and given the ``"lakes"`` terrain). This mod's offline toolchain only understood
two — land and ocean — so an enclosed water body had nowhere to go: it fell out
of the mask as ordinary water and became its **own** navigable sea zone
(``sea_zones.extract`` labels every water component, including a disconnected one;
``cells.fill_nearest`` only reassigns barrier pixels, never an enclosed body), so
an inland lake shipped as sailable open sea.

This module is the pure, wrap-aware, RNG-free core the generators wrap:

* :func:`classify` — of the water (``~land``), the *largest* connected component
  is the world ocean; every other component is an inland lake. The lake mask is a
  boolean companion layer (the exact analogue of the already-committed
  ``sea_zones.png``), so ``land_sea_mask.png`` stays a byte-identical 1-bit
  boolean read by the ~10 tools that assume ``water = ~land``.
* :func:`label` — one label per connected lake component (vanilla ships one
  province per lake; lakes carry no drawn boundary network to subdivide).
* :func:`assemble` — the three-way land / ocean / lake province-label layer, land
  ``1..N``, sea ``N+1..N+M``, lake ``N+M+1..N+M+K``, asserted total and disjoint.

Every step is a pure function of the committed mask (no RNG, no real-world state),
so a re-run reproduces byte-identical output — the determinism core.md requires of
a multiplayer-synchronized mod.
"""

from __future__ import annotations

import numpy as np

from worldgen import cells

#: A lake whose area exceeds this fraction of the world ocean's is *probably* a
#: navigable sea that a hand-drawn fill accidentally sealed off from the ocean
#: (a closed strait), not a real inland lake. Mis-classification is silent,
#: stateless and offline-uncatchable (``validate_map._check_lakes_stateless``
#: accepts a stateless lake of any size), so :func:`classify` logs a loud WARNING
#: — not a hard error, since a legitimately large lake may exist and the user's
#: render is the final gate.
OCEAN_WARN_FRACTION = 0.03


def classify(land: np.ndarray, wrap_x: bool = True,
             warn_fraction: float = OCEAN_WARN_FRACTION, log=None) -> np.ndarray:
    """Boolean lake mask: True where a water pixel is an enclosed inland lake.

    ``land`` is the boolean land mask. Of the water (``~land``), the largest
    wrap-aware connected component is the world ocean; every other component is a
    lake. Ties for "largest" break to the lowest component id (``np.argmax``),
    which is deterministic. Pure function of the mask — no RNG.
    """
    water = ~land
    bodies = cells.components(water.astype(np.int32), wrap_x)
    bodies[~water] = 0
    areas = np.bincount(bodies.ravel())
    if len(areas) <= 1:
        # No water at all — no ocean, no lakes.
        if log:
            log("  lakes: the mask has no water; no lakes")
        return np.zeros_like(land, dtype=bool)
    # areas[0] is the (land) background; the ocean is the largest real body.
    ocean_id = int(np.argmax(areas[1:]) + 1)
    ocean_area = int(areas[ocean_id])
    lake_mask = water & (bodies != ocean_id)

    if log:
        n_lake = sum(1 for i in range(1, len(areas)) if i != ocean_id and areas[i] > 0)
        log(f"  lakes: world ocean = body {ocean_id} ({ocean_area:,} px), "
            f"{n_lake} enclosed lake body(ies), {int(lake_mask.sum()):,} lake px")
        for i in range(1, len(areas)):
            if i == ocean_id or areas[i] == 0:
                continue
            if warn_fraction > 0 and areas[i] > ocean_area * warn_fraction:
                log(f"  WARNING: lake body {i} is {areas[i]:,} px, over "
                    f"{warn_fraction:.1%} of the world ocean ({ocean_area:,} px) — a "
                    f"navigable sea may have been sealed off from the ocean by the fill; "
                    f"verify on the rendered map")
    return lake_mask


def label(lake_mask: np.ndarray, wrap_x: bool = True) -> np.ndarray:
    """One label ``1..K`` per connected lake component (0 elsewhere), wrap-aware.

    Lakes are not subdivided — vanilla ships one province per lake, and there is
    no drawn boundary network to cut against — so a connected component *is* a
    province.
    """
    comp = cells.components(lake_mask.astype(np.int32), wrap_x)
    return cells.renumber(np.where(lake_mask, comp, 0))


def assemble(land_lab: np.ndarray, sea_lab: np.ndarray, lake_lab: np.ndarray,
             n_land: int, n_sea: int) -> np.ndarray:
    """Combine the three label layers into one province-label layer.

    Land keeps ``1..N``; sea becomes ``N+1..N+M``; lake becomes
    ``N+M+1..N+M+K``. Asserts the three sets are pixel-disjoint and that the
    result leaves no unlabelled pixel — the three-way tiling invariant, extracted
    so it is self-checkable without running ``generate_provinces.main``.
    """
    land_m = land_lab > 0
    sea_m = sea_lab > 0
    lake_m = lake_lab > 0
    if int((land_m & sea_m).sum()):
        raise cells.CellError("assemble: land and sea labels overlap")
    if int((land_m & lake_m).sum()):
        raise cells.CellError("assemble: land and lake labels overlap")
    if int((sea_m & lake_m).sum()):
        raise cells.CellError("assemble: sea and lake labels overlap")

    labels = np.zeros(land_lab.shape, dtype=np.int64)
    labels[land_m] = land_lab[land_m].astype(np.int64)
    labels[sea_m] = sea_lab[sea_m].astype(np.int64) + n_land
    labels[lake_m] = lake_lab[lake_m].astype(np.int64) + n_land + n_sea
    blank = int((labels == 0).sum())
    if blank:
        raise cells.CellError(
            f"assemble: {blank:,} pixel(s) carry no province label — the land / "
            f"ocean / lake layers do not tile the canvas")
    return labels
