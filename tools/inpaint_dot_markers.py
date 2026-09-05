#!/usr/bin/env python3
"""CLI wrapper for one-off inspection/debugging of the dot-marker derivation.

Step 6 of the paired-anchor-dot registration workflow
(``planning/requests/register-old-world-region-anchor-dot-handoff.md``): the
user's marked crop in ``sources/dots/`` carries pure-RGB marker dots on the
features the seed's landmarks name; this removes ALL of them (held-out and
unused dots included — they are still markers in the image) and, on request,
writes the clean source the manifest row and the registration record used to
describe (see history — as of board #3570 the crop is no longer cached as a
file; every pipeline caller re-derives it in memory via
``tools/worldgen/derive_crop.derive_clean_source`` on every load instead).

What it does, and the guarantees it asserts (now implemented in
``tools/worldgen/derive_crop.py`` — see that module for the algorithm):

1. Reads the seed (``tools/registration/seeds/<stem>.json``) for the source
   filename, ``master_shape`` and landmark pixel positions. The registration
   RECORD is never touched — this script moves image bytes, not geometry, and
   ``objective: landmarks`` fits never read the source image anyway.
2. Asserts the dots file's dimensions equal ``master_shape`` (a re-exported crop
   changes dims — that is a sourcing event, not something to paper over).
3. Recovers marker components by EXACT RGB match against the marker palette
   (every channel in {0, 63, 127, 191, 255}, grayscale triples excluded so a
   grayscale relief crop like the z10 tile cannot self-match), on ``alpha>0``
   where the crop carries an alpha mask. A fully-opaque RGB crop is valid — no
   alpha is required. Components smaller than ``MIN_MARKER_PX`` are reported and
   ignored (art can coincidentally hit a palette triple on one stray pixel).
   Two crops predate the 5-value palette convention (bretonnia 2026-08-14,
   kislev_norsca 2026-08-15: dots like (255,128,0), (100,100,255)), so any seed
   landmark the palette scan leaves unmatched falls back to sampling the dot's
   ACTUAL colour at the landmark position and exact-matching that — still exact
   RGB, still seed-driven, and a genuinely missing dot still fails the
   cross-check below because blank parchment yields no compact component there.
4. Asserts every seed landmark's source px matches a detected centroid within
   ``LANDMARK_TOL_PX`` (wrong-file guard — hard fail). Detected markers beyond
   the seed's landmarks are expected (held-out A/B dots, unused spares) and are
   inpainted with the rest.
5. Dilates the exact-match mask by ``DILATE_PX`` to swallow anti-alias halos,
   then fills RGB from the nearest non-marker pixel with ``alpha>0``
   (``scipy.ndimage.distance_transform_edt`` indices — deterministic). Dots sit
   at coastal alpha edges, so an unrestricted donor would smear undefined RGB
   from under the transparency into the boundary-ink input.
6. Keeps the alpha plane byte-identical, asserts zero marker px remain. If
   ``--out`` (or the default write path) is requested, writes it and re-reads
   it to verify both facts survived the encode.

``--diff-against`` supports diffing a fresh derivation against a file that
already exists (e.g. a previously cached copy, kept locally for comparison): the
freshly computed image is compared against the given file FIRST, and the script
hard-fails without writing if any pixel differs outside the dilated marker disks
(allowing ``DIFF_HALO_PX`` of slack for a previous ad-hoc inpaint's differing
halo radius) or if alpha differs anywhere.

Usage::

    python tools/inpaint_dot_markers.py --seed <stem> --dots <path>
    python tools/inpaint_dot_markers.py --seed <stem> --dots <path> \
        --diff-against sources/<existing>.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import derive_crop  # noqa: E402
from worldgen import sources as sources_mod  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
SOURCES_DIR = TOOLS_DIR.parent / "sources"

#: --diff-against slack: a differing pixel may sit at most this far from an
#: exact marker pixel (covers a previous inpaint's slightly different halo
#: radius); anything farther means this script moved unrelated content.
DIFF_HALO_PX = 8.0


def log(msg: str) -> None:
    print(msg, flush=True)


def load_dots_image(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    """``(rgb, alpha)`` uint8 arrays; ``alpha`` is None for an RGB image.

    Only the two modes the workflow produces are accepted; anything else is
    refused rather than silently converted, because a mode conversion would
    change bytes this script promises not to touch.
    """
    with Image.open(path) as im:
        if im.mode == "RGBA":
            arr = np.asarray(im, dtype=np.uint8)
            return arr[..., :3].copy(), arr[..., 3].copy()
        if im.mode == "RGB":
            return np.asarray(im, dtype=np.uint8).copy(), None
        raise SystemExit(f"{path}: unsupported image mode '{im.mode}' (expected RGBA or RGB)")


def diff_against(existing: Path, rgb_new: np.ndarray, alpha_new: np.ndarray | None,
                 marker_mask: np.ndarray) -> None:
    """Hard-fail if the fresh derivation differs from ``existing`` beyond the dots."""
    rgb_old, alpha_old = load_dots_image(existing)  # same loader: RGBA/RGB only
    if rgb_old.shape != rgb_new.shape:
        raise SystemExit(f"--diff-against: {existing} is {rgb_old.shape[1]}x{rgb_old.shape[0]}, "
                         f"derivation is {rgb_new.shape[1]}x{rgb_new.shape[0]}")
    if (alpha_old is None) != (alpha_new is None):
        raise SystemExit(f"--diff-against: alpha channel presence differs vs {existing}")
    if alpha_old is not None and not np.array_equal(alpha_old, alpha_new):
        raise SystemExit(f"--diff-against: alpha plane differs vs {existing} — script bug, not writing")

    differs = (rgb_old != rgb_new).any(axis=2)
    n = int(differs.sum())
    if n == 0:
        log(f"diff vs {existing.name}: byte-identical RGB")
        return
    dist_to_marker = ndimage.distance_transform_edt(~marker_mask)
    worst = float(dist_to_marker[differs].max())
    log(f"diff vs {existing.name}: {n} px differ, farthest {worst:.1f} px from exact marker ink")
    if worst > DIFF_HALO_PX:
        raise SystemExit(
            f"--diff-against: differing pixels reach {worst:.1f} px from any marker "
            f"(> {DIFF_HALO_PX}) — the script moved unrelated content; not writing"
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", required=True, help="seed stem under tools/registration/seeds/")
    p.add_argument("--dots", required=True, help="the user's marked crop (sources/dots/...)")
    p.add_argument("--out", default=None,
                   help="output path (default: sources/<seed source name>)")
    p.add_argument("--diff-against", default=None,
                   help="existing clean source to compare with before writing (hard-fails "
                        "if differences reach beyond the dilated marker disks)")
    args = p.parse_args(argv)

    seed = derive_crop.load_seed(args.seed)
    dots_path = Path(args.dots)
    if not dots_path.is_file():
        raise SystemExit(f"no dots file at {dots_path}")
    out_path = Path(args.out) if args.out else sources_mod.resolve_source_path(seed["source"], SOURCES_DIR)

    rgb, alpha = load_dots_image(dots_path)
    h, w = rgb.shape[:2]
    mh, mw = (int(v) for v in seed["master_shape"])
    log(f"dots          {dots_path} {w}x{h} ({'RGBA' if alpha is not None else 'RGB'})")
    if (h, w) != (mh, mw):
        raise SystemExit(
            f"dims mismatch: dots file is {w}x{h}, seed master_shape says {mw}x{mh} — "
            f"a re-exported crop needs a fresh fit, not an inpaint"
        )

    marker_mask, components = derive_crop.detect_markers(rgb, alpha)
    derive_crop.add_seed_sampled_colors(rgb, alpha, seed, marker_mask, components)
    if not components:
        raise SystemExit("no marker components detected — wrong file?")
    log(f"markers       {len(components)} component(s), {int(marker_mask.sum())} exact px, "
        f"{len(seed['landmarks'])} seed landmark(s)")

    derive_crop.crosscheck_landmarks(seed, components)
    for c in sorted(components, key=lambda c: c["color"]):
        tag = (f"landmark '{c['landmark']}' ({c['dist_px']:.2f} px)"
               if "landmark" in c else "extra — inpainted too")
        log(f"  rgb{c['color']}: centroid ({c['centroid'][0]:.1f}, {c['centroid'][1]:.1f}), "
            f"{c['n_px']} px — {tag}")
    extras = len(components) - len(seed["landmarks"])
    if extras:
        log(f"{extras} marker(s) beyond the seed's landmarks (held-out/unused dots) — inpainted too")

    out_rgb, fill_mask = derive_crop.inpaint(rgb, alpha, marker_mask)
    log(f"inpainted     {int(fill_mask.sum())} px (exact mask dilated {derive_crop.DILATE_PX} px)")

    marker_colors = {c["color"] for c in components}
    derive_crop.assert_no_marker_px(out_rgb, alpha, marker_colors, "in-memory result")

    if args.diff_against:
        diff_against(Path(args.diff_against), out_rgb, alpha, marker_mask)

    if alpha is not None:
        out_img = Image.fromarray(np.dstack([out_rgb, alpha]), mode="RGBA")
    else:
        out_img = Image.fromarray(out_rgb, mode="RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path)

    # Re-read: both promises must survive the encode.
    rgb2, alpha2 = load_dots_image(out_path)
    if alpha is not None and not np.array_equal(alpha2, alpha):
        raise SystemExit(f"{out_path}: written alpha plane differs from the input's — encode bug")
    derive_crop.assert_no_marker_px(rgb2, alpha2, marker_colors, str(out_path))
    log(f"wrote {out_path} (alpha byte-identical, zero marker px remain)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
