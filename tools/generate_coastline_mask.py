#!/usr/bin/env python3
"""Land/sea mask from the hand-traced coastline — the coastline authority.

The input is the finished black/white land fill ``oldworld-first/land_sea_mask.png``
(8192×3616 = the mod canvas, binarized first via ``binarize_cyan_mask.py`` — see
``--from-fill`` below). The same coastline is also carried as a cyan (0,255,255)
trace-only layer in ``terraqueous_globe_reprojected - full.ora#coasts``, but that
layer has no land fill of its own and cannot replace the flat PNG here (board
#5399: trace-parity between the two differs by ~145k px, while the flat PNG's
fill reproduces the committed mask exactly). Cyan is reserved for the coastline
trace (rivers moved to blue instead, board #3703 follow-up 2026-09-15) — before
that the trace was drawn magenta. Because it is drawn in canvas space it needs no
registration, and because it is a deliberate hand-trace it supersedes the
height-ramp extraction that ``generate_heightmap.py`` used to derive the coast
(user decision, 2026-08-14: "the traced coastline wins"; the ramp derivation was
deleted 2026-08-22). This tool is the sole owner of ``land_sea_mask.png``;
``generate_heightmap.py`` consumes the mask rather than re-deriving the shoreline.

Land vs sea is decided by **coastline topology**, not by globe colour (the globe's
sea is a desaturated grey that no hue test separates from land — the very problem
the trace exists to avoid):

1. The cyan line is the coast; it is the barrier.
2. Fill the gaps in the (anti-aliased) line, then flood-label the regions between
   lines. Assign every line pixel to its nearest region so the shoreline is crisp
   (1 px) rather than the width of the drawn stroke.
3. The world ocean is the largest region. Everything else is classified by
   **parity of coastline crossings from the ocean**: ocean = water (depth 0),
   the continents that touch it = land (depth 1), inland seas enclosed in a
   continent = water (depth 2), lake-islands = land (depth 3), and so on. This is
   exact and self-contained — no colour, no prior mask, no hand-curated lake list.

Navigable rivers the user drew as thin channels off the coast are continuous with
the world ocean, so they fall out as ocean-connected sea automatically (they become
their own navigable sea zones downstream — user note, 2026-08-14).

Everything it reads is committed (or the manifested source), and every step is a
pure function of the pixels, so a re-run reproduces the same mask.
"""
from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import cells, lakes, raster, sources  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = sources.source_ref("coastline_fill")
DEFAULT_OUT = TOOLS_DIR / "derived" / "land_sea_mask.png"
#: The companion inland-lake layer (board #3742), written alongside the mask in
#: --from-fill mode only. A boolean sibling of land_sea_mask.png (True where a
#: water pixel is an enclosed lake), the exact analogue of the committed
#: sea_zones.png. Downstream tools that don't find it fall back to the old
#: two-class (land/ocean) behaviour, byte-identical to before it existed.
DEFAULT_LAKE_OUT = TOOLS_DIR / "derived" / "lake_mask.png"

#: Ignore land specks smaller than this many px when reporting (not when masking).
_REPORT_MIN = 2000

#: Drop isolated land components strictly smaller than this many px, reclassifying
#: them as water (board #3705 follow-up). Pinned to validate_map's degenerate-
#: province floor (its default ``--min-province-area 4``): a land component below it
#: cannot legally become a province, so it is an artifact, not land. See
#: :func:`drop_land_specks`.
SPECK_MAX_PX = 4


def drop_land_specks(land: np.ndarray, min_px: int, wrap_x: bool = True,
                     log=print) -> tuple[np.ndarray, int, int]:
    """Reclassify tiny isolated land components (< ``min_px`` px) as water.

    A finished black/white fill exported to PNG can mint 1–3 px "islands" from
    anti-aliased near-white pixels stranded in the black sea — a stray export
    artifact, not real land (confirmed for the xD3DC0A "Western Ocean Mass" speck:
    absent from the GIMP layers, present only after the PNG export). Left in the
    mask each becomes its own micro land province below the degenerate-province
    floor (:mod:`validate_map`'s default 4 px) and — being a disconnected islet
    with no land neighbour — can never be merged away by
    :func:`worldgen.cells.merge_small`'s share-a-border merge downstream, so it
    ships as a 1-px state forever.

    The drop MUST happen here, at the sole owner of ``land_sea_mask.png`` and
    upstream of both the sea-zone and province cuts: the same speck removed only in
    :mod:`generate_provinces` would break its ``sea_zones.png`` tiles ``~land``
    invariant (the pixel would be navigable water the committed sea layer never
    labelled). Cleaning the mask keeps every downstream layer consistent by
    construction.

    Wrap-aware. ``min_px <= 1`` is a no-op (nothing is smaller than one pixel).
    Returns ``(cleaned_land, n_components_dropped, n_pixels_dropped)``.
    """
    if min_px <= 1 or not land.any():
        return land, 0, 0
    comp = cells.components(land.astype(np.int32), wrap_x)
    land_comp = np.where(land, comp, 0)          # keep only land-component labels
    sizes = np.bincount(land_comp.ravel())
    small = np.nonzero((sizes > 0) & (sizes < min_px))[0]
    small = small[small != 0]                    # 0 is water, never a "speck"
    if small.size == 0:
        return land, 0, 0
    drop = np.isin(land_comp, small)
    n_px = int(drop.sum())
    log(f"dropped {int(small.size)} land speck(s) < {min_px} px "
        f"({n_px} px total) -> water")
    return land & ~drop, int(small.size), n_px


def coast_line(rgb: np.ndarray) -> np.ndarray:
    """The drawn coastline: pure cyan, dilated to bridge anti-aliased gaps."""
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    line = (r < 70) & (g > 210) & (b > 210)
    return ndimage.binary_dilation(line, iterations=2)


def filled_mask(rgb: np.ndarray, log=print) -> np.ndarray:
    """Land/sea directly from a **finished** black/white fill (white = land).

    When the user hands over the land/sea split already filled in — a two-colour
    black (sea) / white (land) raster in canvas space — there is no coastline to
    flood-fill: the mask *is* the source. This reads white as land directly, so
    the user's own fill is the coastline authority verbatim (user directive,
    2026-08-23: "no regenerating the mask, just use the one in sources/"). Any
    anti-aliased grey at the black/white edge is decided by majority (>127).
    """
    land = (rgb.astype(np.int64).sum(axis=2) > 383)  # nearer white than black
    log(f"filled mask: land fraction {land.mean():.3f} "
        f"(white=land, {int(land.sum()):,} px)")
    return land


def _crisp_labels(line: np.ndarray) -> tuple[np.ndarray, int]:
    """Label the regions between the lines, then assign each line pixel to its
    nearest region so the land/sea boundary is a crisp 1 px shoreline rather than
    the width of the (dilated) drawn stroke."""
    lab, n = ndimage.label(~line)
    idx = ndimage.distance_transform_edt(lab == 0, return_distances=False,
                                         return_indices=True)
    return lab[tuple(idx)], n


def _adjacency(labf: np.ndarray, n: int) -> list[set[int]]:
    """Which regions share a coastline (are neighbours in the crisp label image)."""
    adj: list[set[int]] = [set() for _ in range(n + 1)]
    for A, B in ((labf[:, :-1], labf[:, 1:]), (labf[:-1, :], labf[1:, :])):
        d = A != B
        for u, v in zip(A[d].ravel(), B[d].ravel()):
            adj[int(u)].add(int(v)); adj[int(v)].add(int(u))
    return adj


def land_mask(rgb: np.ndarray, log=print) -> np.ndarray:
    line = coast_line(rgb)
    labf, n = _crisp_labels(line)
    sizes = np.bincount(labf.ravel(), minlength=n + 1)
    ocean = int(np.argmax(sizes[1:]) + 1)
    log(f"regions {n}, world ocean = region {ocean} "
        f"({100 * sizes[ocean] / labf.size:.1f}% of canvas)")

    # Parity BFS from the ocean: even depth = water, odd = land.
    adj = _adjacency(labf, n)
    depth = np.full(n + 1, -1, dtype=np.int64)
    depth[ocean] = 0
    q = deque([ocean])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v and depth[v] < 0:
                depth[v] = depth[u] + 1
                q.append(v)
    unreached = [i for i in range(1, n + 1) if depth[i] < 0]
    if unreached:  # regions the ocean cannot reach across any coast → treat as land
        log(f"  {len(unreached)} region(s) unreachable from ocean → land")
        for i in unreached:
            depth[i] = 1
    is_land = (depth % 2 == 1)
    land = is_land[labf]
    log(f"land fraction {land.mean():.3f}  "
        f"(land regions {int(is_land[1:].sum())}, water regions {int((~is_land[1:]).sum())})")
    return land


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", default=DEFAULT_SOURCE,
                   help="traced-coastline source in sources/ (manifested)")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT,
                   help="output mask path (default: the committed land_sea_mask.png)")
    p.add_argument("--direct", action="store_true",
                   help="read the source file directly, bypassing the manifest guard "
                        "(for a candidate run before the source is manifested)")
    p.add_argument("--from-fill", action="store_true",
                   help="the source is a finished black/white land fill (white=land), "
                        "not a cyan coastline trace — use it directly, no flood-fill")
    p.add_argument("--lake-out", type=Path, default=DEFAULT_LAKE_OUT,
                   help="companion lake-mask path written in --from-fill mode "
                        "(default: tools/derived/lake_mask.png)")
    p.add_argument("--speck-max", type=int, default=SPECK_MAX_PX,
                   help="drop isolated land components smaller than this many px as "
                        f"water — anti-aliased export artifacts (default {SPECK_MAX_PX}, "
                        "the degenerate-province floor; 0/1 disables)")
    args = p.parse_args(argv)

    if args.direct:
        rgba = sources.read_source_rgba(args.source, allow_empty=True)
        if rgba is None:
            raise SystemExit(f"--direct: '{args.source}' not found under sources/ or its searched subfolders")
        rgb = rgba[..., :3]
    else:
        rgb = sources.load_source_image(args.source)
    land = filled_mask(rgb) if args.from_fill else land_mask(rgb)
    # Reclassify tiny anti-aliased land specks as water before anything downstream
    # reads the mask, so a stray 1-px "island" never becomes a permanent micro
    # state (board #3705 follow-up). Runs before lakes.classify below so the lake
    # companion is computed from the cleaned land.
    land, _n_specks, _n_px = drop_land_specks(land, args.speck_max, map_config.WRAP_X)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    raster.write_mask_png(args.out, land)
    print(f"wrote {args.out}")

    # Companion inland-lake layer (board #3742). Only emitted from a finished
    # fill: enclosed black bodies that don't touch the world ocean are lakes. The
    # parity land_mask() path is legacy (the live source is a fill per project
    # memory) and emits no companion. An all-False mask (no lakes) is written and
    # is downstream-equivalent to the file being absent.
    if args.from_fill:
        lake = lakes.classify(land, map_config.WRAP_X, log=print)
        args.lake_out.parent.mkdir(parents=True, exist_ok=True)
        raster.write_mask_png(args.lake_out, lake)
        print(f"wrote {args.lake_out}  ({int(lake.sum()):,} lake px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
