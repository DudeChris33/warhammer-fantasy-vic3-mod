"""Sea zones from the user's hand-drawn boundary network.

Board #2593. Vanilla Victoria 3 (105 sea zones) and Realms of Exether (169)
organise their seas as named geographic bodies *shaped by the land* — coast-
hugging coastal seas, straits and gulfs, plus a few large open oceans — not
equal-area tiles. Rather than approximate that with a seed-Voronoi (which came
out blocky), the user drew the zone boundaries by hand as a purple (127,0,255)
line network on the canvas-space reprojected globe
(``sources/terraqueous_globe_reprojected - sea_zones.png``), the same idiom as
the coastline trace ``generate_coastline_mask.py`` consumes. (The magenta
255,0,255 line in that file is the *coast*; the land/sea split comes from the
committed mask, so only the purple matters here.)

:func:`extract` turns that drawing into a label layer, exactly as drawn:

1. Detect the purple line and dilate it to bridge anti-aliased gaps.
2. Only the parts of the line **in the water** subdivide the sea — lines drawn
   on land are ignored. Cut the water into connected regions separated by the
   in-water line (wrap-aware).
3. Give each line pixel the nearest region's label, so a zone boundary is a
   crisp 1 px line rather than the width of the drawn stroke.
4. Merge sub-floor slivers (a coastal trace running just off the mask coast
   shaves thin offcuts) into a neighbour.

Every step is a pure function of the committed mask + the drawn source + the
knobs (no RNG), so a re-run reproduces byte-identical zones — the determinism
core.md requires of a multiplayer-synchronized mod.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from worldgen import cells

#: The user's SEA-ZONE boundary colour. The red channel separates it from the
#: coast, which is drawn magenta (255,0,255) in the same file.
_PURPLE_RED = (60, 195)


def purple_lines(rgb: np.ndarray) -> np.ndarray:
    """The hand-drawn sea-zone boundary line (purple 127,0,255), tolerant of
    anti-aliasing."""
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    return (r >= _PURPLE_RED[0]) & (r <= _PURPLE_RED[1]) & (g < 80) & (b > 190)


def extract(land: np.ndarray, drawn: np.ndarray, dilate: int = 2,
            merge_floor: int = 1200, wrap_x: bool = True, log=None) -> np.ndarray:
    """Sea-zone labels (0 on land, ``1..n`` per zone) from the drawn network.

    ``land`` is the boolean land mask; ``drawn`` is the RGB sea-zone source.
    See the module docstring for the method.
    """
    water = ~land
    line = purple_lines(drawn)
    if dilate:
        line = ndimage.binary_dilation(line, iterations=dilate)
    barrier = line & water
    if log:
        log(f"  purple line {int(line.sum()):,} px, in-water barrier {int(barrier.sum()):,} px")

    # Connected components of the water minus the in-water barrier (wrap-aware).
    free = water & ~barrier
    comp = cells.components(free.astype(np.int32), wrap_x)
    zones = cells.renumber(np.where(free, comp, 0))
    if log:
        log(f"  {int(zones.max())} raw regions between the lines")

    # Crisp 1-px boundaries: each barrier pixel takes the nearest region's label.
    zones = cells.fill_nearest(zones, water, wrap_x)
    # Drop stray slivers (coastal-trace offcuts, accidental marks).
    zones = cells.merge_small(zones, merge_floor, wrap_x)
    zones = cells.renumber(zones)
    if int((zones == 0).sum()) != int(land.sum()):
        raise cells.CellError(
            "sea-zone layer does not tile the water exactly: "
            f"{int((zones == 0).sum()):,} unlabelled px vs {int(land.sum()):,} land px"
        )
    if log:
        log(f"  {int(zones.max())} sea zones")
    return zones
