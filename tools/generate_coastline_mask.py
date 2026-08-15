#!/usr/bin/env python3
"""Land/sea mask from the hand-traced coastline — the coastline authority.

The user traced the world's entire coastline as a magenta (255,0,255) line
directly on the canvas-space reprojected globe
(``sources/terraqueous_globe_reprojected - coasts.png``, 8192×3616 = the mod
canvas). Because it is drawn in canvas space it needs no registration, and because
it is a deliberate hand-trace it supersedes the height-ramp extraction that
``generate_heightmap.py`` used to derive the coast (user decision, 2026-08-14: "the
traced coastline wins"). This tool is now the owner of ``land_sea_mask.png``;
``generate_heightmap.py`` consumes the mask rather than re-deriving the shoreline.

Land vs sea is decided by **coastline topology**, not by globe colour (the globe's
sea is a desaturated grey that no hue test separates from land — the very problem
the trace exists to avoid):

1. The magenta line is the coast; it is the barrier.
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

from worldgen import raster, sources  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = "terraqueous_globe_reprojected - coasts.png"
DEFAULT_OUT = TOOLS_DIR / "derived" / "land_sea_mask.png"

#: Ignore land specks smaller than this many px when reporting (not when masking).
_REPORT_MIN = 2000


def coast_line(rgb: np.ndarray) -> np.ndarray:
    """The drawn coastline: pure magenta, dilated to bridge anti-aliased gaps."""
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    line = (r > 210) & (g < 70) & (b > 210)
    return ndimage.binary_dilation(line, iterations=2)


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
    args = p.parse_args(argv)

    if args.direct:
        rgb = np.asarray(Image.open(Path("sources") / args.source).convert("RGB"))
    else:
        rgb = sources.load_source_image(args.source)
    land = land_mask(rgb)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    raster.write_mask_png(args.out, land)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
