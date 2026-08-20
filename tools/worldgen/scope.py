"""Old-World rescope: the in-scope mask and the out-of-scope placeholder collapse.

Board item #2207 narrows the playable map to the Old World. The user's own
drawing (``sources/old_world_regions.png`` — the tww3 parchment master frame with
a magenta state-border network and ten flat per-macro fills painted on) is the
single authority for **where subdivision stops**: any pixel the user filled (or
bordered in magenta) is in scope; bare parchment is out of scope. Everything
out of scope collapses to one impassable placeholder cell per major continent.

The drawing is carried onto the canvas **piecewise**, through the five committed
crop registrations of the same master frame — each crop is an axis-aligned cutout
of the master, so its integer offset inside the master is recovered by an exact
template match (:func:`template_offset`) and the drawing is cut at that offset,
classified in the crop's own pixel space (:func:`classify_fills`), and warped
through the crop's record with the existing ``cells.warp_cells``. This module
holds the pixel logic that the whole-canvas generator and the offline boundary
fixture genuinely **share** — so ``run_fixture.py`` exercises the same functions
the real run does, on synthetic pixels, with no real ``sources/`` present:

* :func:`template_offset`   — deterministic exact-cutout offset of a crop in the master.
* :func:`classify_fills`    — exact-RGB fill/magenta classification, in source space.
* :func:`watershed_fill`    — flat-cost geodesic (within-mask) nearest-marker fill, wrap-aware.
* :func:`in_scope_mask`     — clip the assembled raw in-scope mask to land + two-way speck hygiene.
* :func:`collapse_out_of_scope` — label out-of-scope land into named placeholder cells.

Everything here is a pure function of its array inputs plus committed constants —
no RNG, no wall-clock — so a regenerated ``state_labels.png`` stays byte-identical
(the mod is multiplayer-synchronised).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from worldgen import cells

#: Audit floor (canvas px): an out-of-scope land component at or above this that
#: no seed in ``tools/config/out_of_scope_continents.json`` claims is a hard error
#: — a forgotten continent must be a deliberate config edit, never silently folded
#: into an island. Below it, an unclaimed component folds into the nearest
#: placeholder. Provisional against the real drawn scope; re-checked in the render
#: loop (measured unclaimed masses sit >=110k on the bbox proxy).
OOS_MAJOR_MIN = 50_000

#: Two-way speck-hygiene floor (canvas px): warping the drawn scope onto the canvas
#: and clipping to the coast both leave sub-pixel noise along edges. An out-of-scope
#: pinhole fully enclosed by in-scope land, or an in-scope sliver stranded on
#: out-of-scope land, smaller than this is reassigned to its surroundings. A
#: deliberately-filled in-scope *island* (no land neighbour) is never touched.
SCOPE_SPECK_MAX = 5_000


class ScopeError(RuntimeError):
    """The in-scope mask or the placeholder collapse cannot be built as declared."""


# ---------------------------------------------------------------------------
# Exact-cutout placement of a crop inside the master frame
# ---------------------------------------------------------------------------

def template_offset(master_gray: np.ndarray, crop_gray: np.ndarray,
                    crop_opaque: np.ndarray, refine: int = 3) -> tuple[int, int]:
    """Integer ``(dx, dy)`` placing ``crop``'s (0, 0) inside the master frame.

    Each Old World crop is an axis-aligned pixel cutout of the master parchment,
    so its position in the master is an exact integer offset. A fully-opaque
    window near the crop's opaque centroid is located in the master by normalised
    cross-correlation (:func:`skimage.feature.match_template` — FFT-based, and
    deterministic on the pinned stack), then the offset is **refined to the
    integer that maximises the exact-pixel match** of the crop's opaque pixels
    against the master over a small neighbourhood. That final argmax is a pure
    function of the pixels (an integer count, ties broken toward the lower
    ``(dy, dx)``), so it does not inherit any last-bit fragility from the FFT.

    Grayscale is enough to localise (the correlation peak is razor sharp against
    parchment); the refine step re-verifies on full pixels.
    """
    from skimage.feature import match_template

    mh, mw = master_gray.shape
    ch, cw = crop_gray.shape
    if ch > mh or cw > mw:
        raise ScopeError(f"crop {cw}x{ch} is larger than the master {mw}x{mh}")

    ys, xs = np.nonzero(crop_opaque)
    if not ys.size:
        raise ScopeError("crop has no opaque pixel to match on")
    cy, cx = int(round(ys.mean())), int(round(xs.mean()))
    win = 128
    oy = int(np.clip(cy - win // 2, 0, ch - win)) if ch >= win else 0
    ox = int(np.clip(cx - win // 2, 0, cw - win)) if cw >= win else 0
    wh, ww = min(win, ch), min(win, cw)
    # Slide the opaque window to a location that is fully opaque, so the template
    # carries no transparent (undefined) pixels.
    for _ in range(64):
        if crop_opaque[oy:oy + wh, ox:ox + ww].all():
            break
        oy = min(oy + wh // 2, ch - wh)
        if crop_opaque[oy:oy + wh, ox:ox + ww].all():
            break
        ox = min(ox + ww // 2, cw - ww)
    tmpl = crop_gray[oy:oy + wh, ox:ox + ww]
    res = match_template(master_gray, tmpl)
    py, px = np.unravel_index(int(np.argmax(res)), res.shape)
    dy0, dx0 = int(py) - oy, int(px) - ox

    # Refine: the offset maximising exact opaque-pixel agreement in a +/-refine box.
    best = None
    for ddy in range(-refine, refine + 1):
        for ddx in range(-refine, refine + 1):
            dy, dx = dy0 + ddy, dx0 + ddx
            if dy < 0 or dx < 0 or dy + ch > mh or dx + cw > mw:
                continue
            sub = master_gray[dy:dy + ch, dx:dx + cw]
            score = int((sub[crop_opaque] == crop_gray[crop_opaque]).sum())
            # Ties toward the lower (dy, dx) so the offset is fully determined.
            key = (-score, dy, dx)
            if best is None or key < best[0]:
                best = (key, dy, dx)
    if best is None:
        raise ScopeError("no in-bounds offset found for the crop in the master")
    return best[2], best[1]


# ---------------------------------------------------------------------------
# Exact-RGB fill / magenta classification (source space)
# ---------------------------------------------------------------------------

def _codes(rgb: np.ndarray) -> np.ndarray:
    return (rgb[..., 0].astype(np.uint32) << 16) | (rgb[..., 1].astype(np.uint32) << 8) \
        | rgb[..., 2].astype(np.uint32)


def classify_fills(rgb: np.ndarray, fill_to_macro: dict[tuple[int, int, int], int],
                   magenta_rgb: tuple[int, int, int] = (255, 0, 255)
                   ) -> tuple[np.ndarray, np.ndarray]:
    """``(in_scope_px, macro_px)`` for a region image, by exact-RGB match.

    The drawing's fills are flat, exact RGB (measured), so the classification is
    an exact equality — no tolerance, no threshold fitted to the data. ``in_scope_px``
    is any of the ten fills **or** the magenta border ink; ``macro_px`` carries the
    macro id for a filled pixel and 0 elsewhere (magenta and bare parchment). The
    result is in the region's own pixel space; the caller warps it onto the canvas.
    """
    code = _codes(rgb)
    macro_px = np.zeros(rgb.shape[:2], dtype=np.int32)
    in_scope_px = np.zeros(rgb.shape[:2], dtype=bool)
    for (r, g, b), mid in fill_to_macro.items():
        hit = code == ((r << 16) | (g << 8) | b)
        macro_px[hit] = int(mid)
        in_scope_px |= hit
    mr, mg, mb = magenta_rgb
    in_scope_px |= code == ((mr << 16) | (mg << 8) | mb)
    return in_scope_px, macro_px


# ---------------------------------------------------------------------------
# Flat-cost geodesic (within-mask) nearest-marker fill, wrap-aware
# ---------------------------------------------------------------------------

def watershed_fill(markers: np.ndarray, mask: np.ndarray, wrap_x: bool = True,
                   pad: int = 512) -> np.ndarray:
    """Grow each nonzero marker across ``mask`` by geodesic (within-mask) distance.

    A flat-cost :func:`skimage.segmentation.watershed`: every unmarked ``mask``
    pixel takes the label of the marker nearest it *through connected mask land*,
    never Euclidean across water or an out-of-scope gap. This is the primitive
    both the multi-seed placeholder split (:func:`collapse_out_of_scope`) and the
    generator's in-scope cell growth use, so "grown land can never cross a coast"
    holds identically in both.

    Wrap is handled by the same column-pad trick as :func:`cells.fill_nearest`;
    ``pad`` must exceed the widest seam-crossing flood (clamped to the width).
    """
    from skimage.segmentation import watershed

    pad = min(int(pad), mask.shape[1]) if wrap_x else 0
    m = cells._pad_x(mask, pad) if pad else mask
    mk = cells._pad_x(markers, pad) if pad else markers
    if not mk.any():
        raise ScopeError("watershed_fill: no marker to grow from")
    flat = np.zeros(m.shape, dtype=np.uint8)
    ws = watershed(flat, markers=mk.astype(np.int32), mask=m)
    ws = cells._unpad_x(ws, pad) if pad else ws
    out = np.asarray(ws, dtype=np.int32)
    out[~mask] = 0
    return out


# ---------------------------------------------------------------------------
# In-scope mask: clip to land + two-way speck hygiene
# ---------------------------------------------------------------------------

def _small_components(mask: np.ndarray, max_area: int, wrap_x: bool):
    """Yield ``(component_mask, area)`` for each connected piece of ``mask`` below
    ``max_area``."""
    comp = cells.components(mask.astype(np.int32), wrap_x)
    comp[~mask] = 0
    ids, areas = np.unique(comp[comp > 0], return_counts=True)
    for cid, area in zip(ids.tolist(), areas.tolist()):
        if area < max_area:
            yield comp == cid, area


def _land_neighbours(comp_mask: np.ndarray, land: np.ndarray, wrap_x: bool) -> np.ndarray:
    """Land pixels 4-adjacent to ``comp_mask`` but not in it (wrap-aware on x)."""
    nb = np.zeros_like(comp_mask)
    nb[:-1, :] |= comp_mask[1:, :]
    nb[1:, :] |= comp_mask[:-1, :]
    if wrap_x:
        nb |= np.roll(comp_mask, 1, axis=1)
        nb |= np.roll(comp_mask, -1, axis=1)
    else:
        nb[:, 1:] |= comp_mask[:, :-1]
        nb[:, :-1] |= comp_mask[:, 1:]
    return nb & land & ~comp_mask


def in_scope_mask(raw_in_scope: np.ndarray, land: np.ndarray,
                  speck_max: int = SCOPE_SPECK_MAX, wrap_x: bool = True) -> np.ndarray:
    """Final in-scope land mask from the assembled raw scope layer.

    ``raw_in_scope`` is "a drawn fill or the magenta network landed on this canvas
    pixel" (the union of the five warped crop contributions). This clips it to
    ``land`` and applies two-way speck hygiene:

    * an **out-of-scope pinhole** — a sub-``speck_max`` out-of-scope-land component
      touching no sea and only in-scope land — is filled *in* (a warp hole inside a
      filled region);
    * an **in-scope sliver** — a sub-``speck_max`` in-scope-land component whose only
      land adjacency is out-of-scope land — is pushed *out* (it would otherwise ship
      as an absurd tiny in-scope state, or trip the sub-256 floor);
    * an **in-scope island** — a sub-``speck_max`` in-scope component with no land
      neighbour at all (surrounded by sea) — is **kept**: the user filled it
      deliberately.
    """
    in_scope = raw_in_scope & land

    # (a) Fill out-of-scope pinholes fully enclosed by in-scope land.
    oos = land & ~in_scope
    fill_in = np.zeros_like(in_scope)
    for comp_mask, _area in _small_components(oos, speck_max, wrap_x):
        land_nb = _land_neighbours(comp_mask, land, wrap_x)
        if land_nb.any() and (in_scope[land_nb]).all():
            fill_in |= comp_mask
    in_scope = in_scope | fill_in

    # (b) Push in-scope slivers whose only land adjacency is out-of-scope land out.
    push_out = np.zeros_like(in_scope)
    for comp_mask, _area in _small_components(in_scope, speck_max, wrap_x):
        land_nb = _land_neighbours(comp_mask, land, wrap_x)
        if land_nb.any() and not in_scope[land_nb].any():
            push_out |= comp_mask
    in_scope = in_scope & ~push_out
    return in_scope


# ---------------------------------------------------------------------------
# Out-of-scope placeholder collapse
# ---------------------------------------------------------------------------

def collapse_out_of_scope(land: np.ndarray, in_scope: np.ndarray,
                          seeds: list[tuple[int, int]],
                          major_min: int = OOS_MAJOR_MIN,
                          wrap_x: bool = True) -> tuple[np.ndarray, dict]:
    """Label out-of-scope land into named placeholder cells (``1..M`` in seed order).

    Returns ``(labels, stats)``. ``labels`` is 0 on in-scope land and sea, and
    ``1..M`` on out-of-scope land, one label per config seed in authored order.

    Rules (each a hard :class:`ScopeError` when violated, never a silent fallback):

    * each seed must sit on **out-of-scope land** (a seed on water or on in-scope
      land is a config error);
    * a seed **claims** the whole connected out-of-scope component it lands in, at
      any size and any adjacency;
    * a component two or more seeds land in is **split geodesically** between them
      (Naggaroth + Lustria are one physical landmass; the southlands + the eastern
      lands are one component until the drawn scope severs them);
    * an unclaimed component of ``>= major_min`` px is a hard error naming its area
      and centroid (a forgotten continent, or land the user meant to fill and
      missed — the message says both);
    * every remaining unclaimed component **folds into the nearest placeholder by
      minimum pixel distance** (one wrap-aware EDT per placeholder; ties → the lower
      placeholder index) — an island joins its nearest continent's label even when
      in-scope land is nearer.
    """
    m = len(seeds)
    if m == 0:
        raise ScopeError("no out-of-scope continents configured")
    h, w = land.shape
    oos = land & ~in_scope
    comp = cells.components(oos.astype(np.int32), wrap_x)
    comp[~oos] = 0

    # Validate seeds and resolve the component each lands in.
    seed_comp: list[int] = []
    for i, (x, y) in enumerate(seeds):
        if not (0 <= x < w and 0 <= y < h):
            raise ScopeError(f"seed {i} ({x}, {y}) is outside the canvas {w}x{h}")
        if not land[y, x]:
            raise ScopeError(f"seed {i} ({x}, {y}) is on water, not land")
        if in_scope[y, x]:
            raise ScopeError(f"seed {i} ({x}, {y}) is on in-scope land, not an out-of-scope continent")
        seed_comp.append(int(comp[y, x]))

    by_comp: dict[int, list[int]] = {}
    for si, cid in enumerate(seed_comp):
        by_comp.setdefault(cid, []).append(si)

    labels = np.zeros((h, w), dtype=np.int32)
    claimed: set[int] = set()
    split_from: dict[int, int] = {}  # placeholder index -> co-seeds count in its component
    for cid, si_list in by_comp.items():
        cmask = comp == cid
        if len(si_list) == 1:
            labels[cmask] = si_list[0] + 1
        else:
            markers = np.zeros((h, w), dtype=np.int32)
            for local, si in enumerate(si_list, start=1):
                x, y = seeds[si]
                markers[y, x] = local
            ws = watershed_fill(markers, cmask, wrap_x)
            if int((ws[cmask] == 0).sum()):
                raise ScopeError(f"geodesic split left {int((ws[cmask] == 0).sum())} px of a "
                                 f"multi-seed component unassigned — seeds may coincide")
            local_to_label = np.zeros(len(si_list) + 1, dtype=np.int32)
            for local, si in enumerate(si_list, start=1):
                local_to_label[local] = si + 1
            labels[cmask] = local_to_label[ws[cmask]]
            for si in si_list:
                split_from[si] = len(si_list)
        claimed.add(cid)

    # Audit: an unclaimed major component is a hard error.
    all_ids, all_areas = np.unique(comp[comp > 0], return_counts=True)
    unclaimed = [(int(cid), int(area)) for cid, area in zip(all_ids.tolist(), all_areas.tolist())
                 if int(cid) not in claimed]
    big = []
    for cid, area in unclaimed:
        if area >= major_min:
            ys, xs = np.nonzero(comp == cid)
            big.append(f"component at centroid ({int(xs.mean())}, {int(ys.mean())}) = {area:,} px")
    if big:
        raise ScopeError(
            f"{len(big)} out-of-scope land component(s) >= {major_min:,} px are unclaimed by any "
            f"seed in out_of_scope_continents.json — add a seed (a forgotten continent), or the "
            f"user meant to fill this land in the scope drawing and missed it:\n  "
            + "\n  ".join(big))

    # Fold every small unclaimed component into the nearest placeholder (min pixel
    # distance to that placeholder's pixels; one wrap-aware EDT per placeholder).
    islands_folded = [0] * m
    folded_area = [0] * m
    if unclaimed:
        dist = np.empty((m, h, w), dtype=np.float32)
        for p in range(m):
            has_p = labels == (p + 1)
            if not has_p.any():
                raise ScopeError(f"placeholder {p + 1} won no pixels — its seed lost every tie")
            pad = min(512, w) if wrap_x else 0
            src = cells._pad_x(has_p, pad) if pad else has_p
            d = ndimage.distance_transform_edt(~src)
            dist[p] = cells._unpad_x(d, pad) if pad else d
        for cid, _area in unclaimed:
            cmask = comp == cid
            # distance of this component to each placeholder = min over its pixels
            per_p = np.array([float(dist[p][cmask].min()) for p in range(m)])
            p = int(np.argmin(per_p))  # ties -> lower index (argmin is stable)
            labels[cmask] = p + 1
            islands_folded[p] += 1
            folded_area[p] += int(cmask.sum())

    if int((labels[oos] == 0).sum()):
        raise ScopeError("out-of-scope land left unlabelled after the collapse")

    areas = np.bincount(labels.ravel(), minlength=m + 1)
    stats = {
        "placeholders": m,
        "per_placeholder": [
            {"index": p + 1, "area": int(areas[p + 1]),
             "islands_folded": islands_folded[p], "folded_area": folded_area[p],
             "split_seats": split_from.get(p, 1)}
            for p in range(m)
        ],
        "out_of_scope_land_px": int(oos.sum()),
    }
    return labels, stats
