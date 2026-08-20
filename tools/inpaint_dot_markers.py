#!/usr/bin/env python3
"""Derive a clean, dot-free source from a paired-anchor-dot marked crop.

Step 6 of the paired-anchor-dot registration workflow
(``planning/requests/register-old-world-region-anchor-dot-handoff.md``) as a
deterministic, reusable script instead of ad-hoc session code: the user's marked
crop in ``sources/dots/`` carries pure-RGB marker dots on the features the seed's
landmarks name; this removes ALL of them (held-out and unused dots included — they
are still markers in the image) and writes the clean source the manifest row and
the registration record describe.

What it does, and the guarantees it asserts:

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
6. Keeps the alpha plane byte-identical, asserts zero marker px remain, writes
   ``sources/<source>`` and re-reads it to verify both facts survived the encode.

``--diff-against`` supports re-deriving a clean source that already exists (the
uniform-provenance pass): the freshly computed image is compared against the
given file FIRST, and the script hard-fails without writing if any pixel differs
outside the dilated marker disks (allowing ``DIFF_HALO_PX`` of slack for the
previous ad-hoc inpaint's differing halo radius) or if alpha differs anywhere.

Usage::

    python tools/inpaint_dot_markers.py --seed <stem> --dots <path>
    python tools/inpaint_dot_markers.py --seed <stem> --dots <path> \
        --diff-against sources/<existing>.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

TOOLS_DIR = Path(__file__).resolve().parent
SEED_DIR = TOOLS_DIR / "registration" / "seeds"
SOURCES_DIR = TOOLS_DIR.parent / "sources"

#: The marker palette: every channel drawn from these values (see
#: ``sources/dots/127 0 191.txt``), grayscale triples excluded below.
PALETTE_VALUES = (0, 63, 127, 191, 255)
#: A palette-coloured component smaller than this is a coincidence in the art,
#: not a marker dot (the known dots are ~12 px); reported, never inpainted.
MIN_MARKER_PX = 4
#: A seed landmark must sit within this of a detected centroid (the seeds were
#: authored FROM these centroids, so the match is sub-pixel unless the crop was
#: re-exported — which is a sourcing event, and a hard failure here).
LANDMARK_TOL_PX = 1.5
#: A sampled landmark colour whose exact-match px count exceeds this is art
#: (parchment fill), not a dot — hard fail rather than inpaint a whole region.
MAX_COLOR_PX = 20000
#: Exact-match mask dilation radius, to swallow anti-alias halos around a dot.
DILATE_PX = 3
#: --diff-against slack: a differing pixel may sit at most this far from an
#: exact marker pixel (covers a previous inpaint's slightly different halo
#: radius); anything farther means this script moved unrelated content.
DIFF_HALO_PX = 8.0


def log(msg: str) -> None:
    print(msg, flush=True)


def load_seed(stem: str) -> dict:
    path = SEED_DIR / f"{stem}.json"
    if not path.is_file():
        raise SystemExit(f"no seed file at {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


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


def detect_markers(rgb: np.ndarray, alpha: np.ndarray | None):
    """Marker components by exact palette match.

    Returns ``(marker_px_mask, components)`` where ``components`` is a list of
    ``{color, centroid_xy, n_px}`` for every kept (>= MIN_MARKER_PX) component,
    and ``marker_px_mask`` covers EVERY exact px of every kept component's
    colour — satellites of a real marker colour are marker ink too.
    """
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    in_palette = (
        np.isin(r, PALETTE_VALUES) & np.isin(g, PALETTE_VALUES) & np.isin(b, PALETTE_VALUES)
    )
    nongray = ~((r == g) & (g == b))
    cand = in_palette & nongray
    if alpha is not None:
        cand &= alpha > 0

    components: list[dict] = []
    ignored_specks = 0
    marker_mask = np.zeros(cand.shape, dtype=bool)
    codes = (
        r[cand].astype(np.uint32) << 16 | g[cand].astype(np.uint32) << 8 | b[cand].astype(np.uint32)
    )
    for code in sorted(set(int(c) for c in codes)):
        cr, cg, cb = (code >> 16) & 255, (code >> 8) & 255, code & 255
        mask_c = cand & (r == cr) & (g == cg) & (b == cb)
        labels, n = ndimage.label(mask_c)
        sizes = ndimage.sum_labels(np.ones_like(labels), labels, index=np.arange(1, n + 1))
        kept_any = False
        for i, size in enumerate(sizes, start=1):
            if size < MIN_MARKER_PX:
                ignored_specks += 1
                continue
            ys, xs = np.nonzero(labels == i)
            components.append({
                "color": (cr, cg, cb),
                "centroid": (float(xs.mean()), float(ys.mean())),
                "n_px": int(size),
            })
            kept_any = True
        if kept_any:
            # Every exact px of a marker colour is marker ink, satellites included
            # (alpha-agnostic: halo cores can cross a coastal alpha edge).
            marker_mask |= (r == cr) & (g == cg) & (b == cb)
    if ignored_specks:
        log(f"ignored {ignored_specks} sub-{MIN_MARKER_PX}px palette-coloured speck(s) — art, not markers")
    return marker_mask, components


def add_seed_sampled_colors(rgb: np.ndarray, alpha: np.ndarray | None, seed: dict,
                            marker_mask: np.ndarray, components: list[dict]) -> None:
    """Fallback for pre-palette-convention crops: sample unmatched landmarks.

    For every seed landmark with no detected centroid within LANDMARK_TOL_PX,
    read the most common non-gray colour in the 5x5 around its position and add
    that colour's exact-match components. Mutates ``marker_mask``/``components``
    in place. A landmark over blank parchment samples no stable non-gray colour
    (or a colour with no compact component at the landmark), so the cross-check
    still fails loudly for a genuinely missing dot.
    """
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    centroids = np.array([c["centroid"] for c in components], dtype=np.float64).reshape(-1, 2)
    seen_colors = {c["color"] for c in components}
    for lm in seed["landmarks"]:
        sx, sy = float(lm["source"][0]), float(lm["source"][1])
        if len(centroids) and np.hypot(centroids[:, 0] - sx, centroids[:, 1] - sy).min() <= LANDMARK_TOL_PX:
            continue
        xi, yi = int(sx), int(sy)
        patch = rgb[max(0, yi - 2):yi + 3, max(0, xi - 2):xi + 3].reshape(-1, 3)
        if alpha is not None:
            pa = alpha[max(0, yi - 2):yi + 3, max(0, xi - 2):xi + 3].reshape(-1)
            patch = patch[pa > 0]
        nongray = patch[~((patch[:, 0] == patch[:, 1]) & (patch[:, 1] == patch[:, 2]))]
        if nongray.size == 0:
            continue  # nothing to sample — the cross-check will name this landmark
        cols, counts = np.unique(nongray, axis=0, return_counts=True)
        cr, cg, cb = (int(v) for v in cols[counts.argmax()])
        if (cr, cg, cb) in seen_colors:
            continue  # colour already handled; the position mismatch is real
        mask_c = (r == cr) & (g == cg) & (b == cb)
        if alpha is not None:
            mask_c &= alpha > 0
        total = int(mask_c.sum())
        if total > MAX_COLOR_PX:
            raise SystemExit(
                f"landmark '{lm['name']}': sampled colour ({cr},{cg},{cb}) matches {total} px — "
                f"that is art, not a dot; refusing to inpaint it"
            )
        labels, n = ndimage.label(mask_c)
        sizes = ndimage.sum_labels(np.ones_like(labels), labels, index=np.arange(1, n + 1))
        added = 0
        for i, size in enumerate(sizes, start=1):
            if size < MIN_MARKER_PX:
                continue
            ys, xs = np.nonzero(labels == i)
            components.append({
                "color": (cr, cg, cb),
                "centroid": (float(xs.mean()), float(ys.mean())),
                "n_px": int(size),
            })
            added += 1
        if added:
            seen_colors.add((cr, cg, cb))
            marker_mask |= (r == cr) & (g == cg) & (b == cb)
            log(f"landmark '{lm['name']}': off-palette dot colour ({cr},{cg},{cb}) "
                f"sampled from the seed position — {added} component(s) added")


def crosscheck_landmarks(seed: dict, components: list[dict]) -> None:
    """Every seed landmark must have a detected centroid within LANDMARK_TOL_PX."""
    centroids = np.array([c["centroid"] for c in components], dtype=np.float64)
    used: dict[int, str] = {}
    failures: list[str] = []
    for lm in seed["landmarks"]:
        sx, sy = float(lm["source"][0]), float(lm["source"][1])
        d = np.hypot(centroids[:, 0] - sx, centroids[:, 1] - sy)
        i = int(d.argmin())
        if d[i] > LANDMARK_TOL_PX:
            failures.append(
                f"landmark '{lm['name']}' at ({sx}, {sy}): nearest detected centroid is "
                f"{d[i]:.2f} px away (> {LANDMARK_TOL_PX}) — wrong or re-exported dots file?"
            )
            continue
        if i in used:
            failures.append(
                f"landmark '{lm['name']}' matches the same component as '{used[i]}' — mis-paired dots?"
            )
            continue
        used[i] = lm["name"]
        components[i]["landmark"] = lm["name"]
        components[i]["dist_px"] = float(d[i])
    if failures:
        for f in failures:
            log(f"FAIL: {f}")
        raise SystemExit(
            f"{len(failures)} landmark(s) failed the centroid cross-check — refusing to inpaint. "
            f"If the user re-exported this crop, the seed must be re-derived from fresh dots (sourcing)."
        )


def inpaint(rgb: np.ndarray, alpha: np.ndarray | None, marker_mask: np.ndarray) -> np.ndarray:
    """Fill marker px from the nearest opaque non-marker pixel. Deterministic."""
    yy, xx = np.mgrid[-DILATE_PX:DILATE_PX + 1, -DILATE_PX:DILATE_PX + 1]
    disk = (yy * yy + xx * xx) <= DILATE_PX * DILATE_PX
    fill_mask = ndimage.binary_dilation(marker_mask, structure=disk)

    donor = ~fill_mask
    if alpha is not None:
        donor &= alpha > 0
    if not donor.any():
        raise SystemExit("no opaque non-marker donor pixels exist — nothing to fill from")

    _, (iy, ix) = ndimage.distance_transform_edt(~donor, return_indices=True)
    out = rgb.copy()
    fy, fx = np.nonzero(fill_mask)
    out[fy, fx] = rgb[iy[fy, fx], ix[fy, fx]]

    # The donor field is restricted by construction; assert it anyway — a
    # transparent donor would smear undefined RGB into the boundary-ink input.
    if alpha is not None:
        assert bool((alpha[iy[fy, fx], ix[fy, fx]] > 0).all()), "inpaint took RGB from a transparent donor"
    assert not bool(fill_mask[iy[fy, fx], ix[fy, fx]].any()), "inpaint took RGB from inside the marker mask"
    return out, fill_mask


def assert_no_marker_px(rgb: np.ndarray, alpha: np.ndarray | None,
                        marker_colors: set[tuple[int, int, int]], where: str) -> None:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    opaque = alpha > 0 if alpha is not None else np.ones(r.shape, dtype=bool)
    for cr, cg, cb in sorted(marker_colors):
        n = int((opaque & (r == cr) & (g == cg) & (b == cb)).sum())
        if n:
            raise SystemExit(f"{where}: {n} px of marker colour ({cr},{cg},{cb}) remain")


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

    seed = load_seed(args.seed)
    dots_path = Path(args.dots)
    if not dots_path.is_file():
        raise SystemExit(f"no dots file at {dots_path}")
    out_path = Path(args.out) if args.out else SOURCES_DIR / seed["source"]

    rgb, alpha = load_dots_image(dots_path)
    h, w = rgb.shape[:2]
    mh, mw = (int(v) for v in seed["master_shape"])
    log(f"dots          {dots_path} {w}x{h} ({'RGBA' if alpha is not None else 'RGB'})")
    if (h, w) != (mh, mw):
        raise SystemExit(
            f"dims mismatch: dots file is {w}x{h}, seed master_shape says {mw}x{mh} — "
            f"a re-exported crop needs a fresh fit, not an inpaint"
        )

    marker_mask, components = detect_markers(rgb, alpha)
    add_seed_sampled_colors(rgb, alpha, seed, marker_mask, components)
    if not components:
        raise SystemExit("no marker components detected — wrong file?")
    log(f"markers       {len(components)} component(s), {int(marker_mask.sum())} exact px, "
        f"{len(seed['landmarks'])} seed landmark(s)")

    crosscheck_landmarks(seed, components)
    for c in sorted(components, key=lambda c: c["color"]):
        tag = (f"landmark '{c['landmark']}' ({c['dist_px']:.2f} px)"
               if "landmark" in c else "extra — inpainted too")
        log(f"  rgb{c['color']}: centroid ({c['centroid'][0]:.1f}, {c['centroid'][1]:.1f}), "
            f"{c['n_px']} px — {tag}")
    extras = len(components) - len(seed["landmarks"])
    if extras:
        log(f"{extras} marker(s) beyond the seed's landmarks (held-out/unused dots) — inpainted too")

    out_rgb, fill_mask = inpaint(rgb, alpha, marker_mask)
    log(f"inpainted     {int(fill_mask.sum())} px (exact mask dilated {DILATE_PX} px)")

    marker_colors = {c["color"] for c in components}
    assert_no_marker_px(out_rgb, alpha, marker_colors, "in-memory result")

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
    assert_no_marker_px(rgb2, alpha2, marker_colors, str(out_path))
    log(f"wrote {out_path} (alpha byte-identical, zero marker px remain)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
