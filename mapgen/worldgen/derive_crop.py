#!/usr/bin/env python3
"""Derive a clean, dot-free (rgb, alpha) crop from its paired-anchor-dot sheet.

The reusable core of the paired-anchor-dot workflow's inpaint step (see
``mapgen/inpaint_dot_markers.py``, now a thin CLI wrapper over this module): a
pure, deterministic function of a dots sheet's pixels plus its registration
seed, with zero file I/O and no dependency on ``worldgen.sources`` (that module
imports this one, so the reverse import would cycle). Callers re-run
:func:`derive_clean_source` on every load instead of caching a materialized
copy, so the crop and the dots sheet it comes from can never drift apart
(board #3570).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage

SEED_DIR = Path(__file__).resolve().parent.parent / "registration" / "seeds"

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


def log(msg: str) -> None:
    print(msg, flush=True)


def load_seed(stem: str, seed_dir: Path = SEED_DIR) -> dict:
    path = seed_dir / f"{stem}.json"
    if not path.is_file():
        raise SystemExit(f"no seed file at {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def detect_markers(rgb: np.ndarray, alpha: np.ndarray | None, keep_colours=()):
    """Marker components by exact palette match.

    ``keep_colours`` lists exact RGB triples that are in the palette but are
    not dots (a border network drawn on the same sheet); they are left alone.

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
    for kr, kg, kb in keep_colours:
        cand &= ~((r == kr) & (g == kg) & (b == kb))
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


def derive_clean_source(rgb: np.ndarray, alpha: np.ndarray | None, seed: dict
                        ) -> tuple[np.ndarray, np.ndarray | None]:
    """Derive the dot-free (rgb, alpha) for one paired-anchor-dot crop, in
    memory. `rgb`/`alpha` are the dots sheet's own pixels (as
    sources.load_source_image_rgba or an equivalent direct read returns
    them); `seed` is the parsed registration seed. No file I/O, no RNG — a
    pure, deterministic function of its inputs, so a caller re-runs it on
    every load instead of caching a materialized copy (board #3570). A seed's
    optional ``keep_colours`` (exact RGB triples) names same-sheet markup that
    must survive into the result instead of being inpainted as dots."""
    h, w = rgb.shape[:2]
    mh, mw = (int(v) for v in seed["master_shape"])
    if (h, w) != (mh, mw):
        raise SystemExit(
            f"dots sheet is {w}x{h}, seed master_shape says {mw}x{mh} — "
            f"a re-exported crop needs a fresh fit, not an inpaint"
        )
    keep = tuple(tuple(int(v) for v in c) for c in seed.get("keep_colours", ()))
    marker_mask, components = detect_markers(rgb, alpha, keep)
    add_seed_sampled_colors(rgb, alpha, seed, marker_mask, components)
    if not components:
        raise SystemExit("no marker components detected — wrong file?")
    crosscheck_landmarks(seed, components)
    out_rgb, _fill_mask = inpaint(rgb, alpha, marker_mask)
    marker_colors = {c["color"] for c in components}
    assert_no_marker_px(out_rgb, alpha, marker_colors, "in-memory result")
    return out_rgb, alpha
