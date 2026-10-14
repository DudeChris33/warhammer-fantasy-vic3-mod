"""ChaosRobie's region partition as a guide for new state borders (board #8210).

Pure functions: no paths, no sources, no RNG, no clock. ``mapgen/propose_cr_borders.py`` is
the CLI that feeds them real files; ``run_fixture.py`` exercises them on synthetic rasters.

What lives here is only what no other module does:

* **Decode** ``cr_combi_expanded_lookup.tga`` (16-bit colour-mapped; PIL cannot open it).
* **Place** the lookup's land on ours **without anchor dots** (Chris, 2026-10-14): a moment
  seed, a coarse affine sweep by two-sided IoU, then a thin-plate residual field from any
  landmarks Claude placed. The partition is a *guide*, not a set of borders to reproduce.
* **Snap** borders to rivers and impassable edges, **line** the labels for the generator's
  region stage, **close** the scope cut, and report per-state **provenance**.

The rest of the chain (``cells.warp_cells``, ``fill_nearest``, ``prune_slivers``,
``merge_small``, ``merge_to_target``, ``split_large``) is reused from ``cells``, following
``generate_state_labels.py``.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.interpolate import RBFInterpolator

from worldgen import cells, register, schema


class PartitionError(RuntimeError):
    """The lookup, a box or a placement cannot be used as declared."""


# ---------------------------------------------------------------------------
# Lookup decode
# ---------------------------------------------------------------------------

_TGA_HEADER = struct.Struct("<BBBHHBHHHHBB")  # idlen cmtype imgtype cmstart cmlen cmdepth x y w h bpp desc


def decode_lookup(data: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Decode a colour-mapped 16-bit-index TGA into ``(idx uint16 HxW, palette uint8 Nx3 RGB)``.

    The descriptor byte of the shipped file is ``0x10`` (bit 5, top-left origin, is *clear*), yet
    its rows are stored **top-down** as-is (measured 2026-10-14: reading it bottom-up puts Ulthuan
    south of Naggaroth, and the CR pathing preview of the same frame confirms top-down). So the
    rows are kept exactly as stored and the descriptor's origin bit is deliberately ignored.
    """
    if len(data) < _TGA_HEADER.size:
        raise PartitionError("lookup: shorter than a TGA header")
    (idlen, cmtype, imgtype, cmstart, cmlen, cmdepth,
     _x0, _y0, w, h, bpp, _desc) = _TGA_HEADER.unpack_from(data, 0)
    if cmtype != 1 or imgtype != 1 or bpp != 16 or cmdepth != 32:
        raise PartitionError(
            f"lookup: expected colour-mapped (1,1), 16 bpp indices, 32-bit palette; got "
            f"cmtype={cmtype} imgtype={imgtype} bpp={bpp} cmdepth={cmdepth}")
    if idlen != 0:
        raise PartitionError(f"lookup: unexpected image-id field ({idlen} bytes)")
    # The header's colour-map "first entry index" reads 18 in the shipped file, which is the byte
    # offset the palette starts at, not an index shift: pixel values index the palette directly
    # (measured 2026-10-14: index 12 is a real region with 322 k px, so a shift of 18 is wrong).
    pal_off = _TGA_HEADER.size
    pix_off = pal_off + cmlen * 4
    expect = pix_off + w * h * 2
    if len(data) != expect:
        raise PartitionError(f"lookup: {len(data)} bytes, expected exactly {expect} "
                             f"({w}x{h}, {cmlen} palette entries)")
    bgra = np.frombuffer(data, dtype=np.uint8, count=cmlen * 4, offset=pal_off).reshape(cmlen, 4)
    palette = np.ascontiguousarray(bgra[:, [2, 1, 0]])
    idx = np.frombuffer(data, dtype="<u2", count=w * h, offset=pix_off).reshape(h, w).astype(np.uint16)
    if int(idx.max()) >= cmlen:
        raise PartitionError("lookup: a pixel indexes past the palette")
    return idx, palette


def void_index(palette: np.ndarray) -> int:
    """The one palette index whose colour is ``000000`` (sea and off-map)."""
    hit = np.flatnonzero(~palette.any(axis=1))
    if hit.size != 1:
        raise PartitionError(f"lookup: expected exactly one 000000 palette entry, found {hit.size}")
    return int(hit[0])


#: The lookup spans the whole parchment frame with a per-axis scale and zero offset:
#: ``px = lx * 6400/3200``, ``py = ly * 4480/1941`` (measured 2026-10-14: the lookup's interior
#: region edges over Ulthuan sit a median 1 parchment px from Chris's accepted magenta lines).
PARCHMENT_SIZE = (6400, 4480)
LOOKUP_TO_PARCHMENT = (6400 / 3200, 4480 / 1941)


def to_parchment_frame(idx: np.ndarray, void: int,
                       box: tuple[int, int, int, int] | None = None) -> np.ndarray:
    """Nearest per-axis upsample of the lookup to the parchment frame, as int32 labels.

    Void becomes 0, every other palette index ``index + 1``. ``box`` (parchment px,
    ``x0, y0, x1, y1``) returns only that window; the whole frame is about 115 MB, so the CLI
    asks for the window it needs.
    """
    pw, ph = PARCHMENT_SIZE
    x0, y0, x1, y1 = box if box is not None else (0, 0, pw, ph)
    if x0 < 0 or y0 < 0 or x1 > pw or y1 > ph or x1 <= x0 or y1 <= y0:
        raise PartitionError(f"cr_box {box} lies outside the {pw}x{ph} parchment frame")
    sx, sy = LOOKUP_TO_PARCHMENT
    lx = np.minimum(((np.arange(x0, x1) + 0.5) / sx).astype(np.int64), idx.shape[1] - 1)
    ly = np.minimum(((np.arange(y0, y1) + 0.5) / sy).astype(np.int64), idx.shape[0] - 1)
    out = idx[np.ix_(ly, lx)].astype(np.int32) + 1
    out[out == void + 1] = 0
    return out


# ---------------------------------------------------------------------------
# Same-rule land on both sides
# ---------------------------------------------------------------------------

def crop_box(arr: np.ndarray, box: tuple[int, int, int, int], wrap: bool = False) -> np.ndarray:
    """``arr[y0:y1, x0:x1]``; with ``wrap`` columns are taken modulo the width, so a box with
    ``x1`` past the right edge (across the seam) comes back contiguous."""
    x0, y0, x1, y1 = box
    if wrap and (x0 < 0 or x1 > arr.shape[1]):
        return arr[y0:y1][:, np.arange(x0, x1) % arr.shape[1]]
    return arr[y0:y1, x0:x1]


def box_land(mask: np.ndarray, min_component: int = 400) -> np.ndarray:
    """The union of land components of at least ``min_component`` px (4-connected).

    The same rule is used for CR's land and for ours, with no drawn-zone masking: two silhouettes
    cut by different rules fit the cuts, not the coasts (scoping measured IoU 0.52 vs 0.75).
    """
    lab, n = ndimage.label(mask)
    if n == 0:
        return np.zeros_like(mask, dtype=bool)
    sizes = np.bincount(lab.ravel())
    keep = sizes >= min_component
    keep[0] = False
    return keep[lab]


def edge_cut(land: np.ndarray) -> dict[str, float]:
    """Fraction of each edge of a cropped land mask that runs over land."""
    return {
        "top": float(land[0].mean()), "bottom": float(land[-1].mean()),
        "left": float(land[:, 0].mean()), "right": float(land[:, -1].mean()),
    }


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

DEFAULT_FIT = {
    "coarse_step": 4,        # reduced-grid factor of the first sweep
    "scale_pct": 10.0,       # +- scale sweep around the moment seed
    "scale_step_pct": 2.0,
    "offset_px": 15,         # +- offset sweep in reduced px
    "offset_step": 2,
    "lattice": [9, 9],       # control lattice over cr_box
    "influence_px": 150.0,   # a landmark's pull fades to the affine this far out
    "min_component": 400,
}


@dataclass(frozen=True)
class Landmark:
    name: str
    source: tuple[float, float]   # crop-local parchment px (origin = cr_box corner)
    canvas: tuple[float, float]   # crop-local canvas px (origin = box corner)
    feature: str = ""


def _moments(mask: np.ndarray) -> tuple[float, float, float, float]:
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        raise PartitionError("placement: a silhouette is empty (check box / cr_box)")
    return float(xs.mean()), float(ys.mean()), float(xs.std()) or 1.0, float(ys.std()) or 1.0


def _sweep(centre: float, pct: float, step_pct: float) -> np.ndarray:
    k = int(round(pct / step_pct))
    return np.array([centre * (1.0 + i * step_pct / 100.0) for i in range(-k, k + 1)])


def _offsets(centre: float, half: int, step: int) -> np.ndarray:
    return np.array([centre + i for i in range(-half, half + 1, step)], dtype=np.float64)


def fit_placement(src_land: np.ndarray, canvas_land: np.ndarray, landmarks: list[Landmark],
                  params: dict | None = None, log=None
                  ) -> tuple[np.ndarray, np.ndarray, dict]:
    """Place CR's land on ours. ``src_land`` / ``canvas_land`` are same-rule boolean crops
    (parchment px / canvas px, each origin at its own box corner).

    Returns ``(src_pts, canvas_pts, info)``, control points in those crop-local frames:

    1. **Moment seed** — centroid and std of each silhouette give scale and offset.
    2. **Coarse affine** — ``register.coarse_affine`` over a declared sweep, then a finer one.
       This is the placement. ``register.refine`` stays opt-in elsewhere: on Ulthuan it raised
       IoU while worsening interior error.
    3. **Landmark correction** — a lattice over the CR crop through the affine, plus a
       thin-plate residual field from the landmarks. Pins (zero residual) at lattice points
       farther than ``influence_px`` from every landmark keep the placement the affine away from
       them; the placement is exact at every landmark.
    """
    p = {**DEFAULT_FIT, **(params or {})}
    log = log or (lambda *_: None)
    st = int(p["coarse_step"])
    sh, sw = src_land.shape
    ch, cw = canvas_land.shape

    # Both stages work on masks reduced by the same factor, so the scale is unchanged between
    # them and an offset in reduced px is ``offset / step``.
    s_r, c_r = src_land[::st, ::st], canvas_land[::st, ::st]
    smx, smy, ssx, ssy = _moments(s_r)
    cmx, cmy, csx, csy = _moments(c_r)
    seed_scale = (csx / ssx, csy / ssy)
    seed_off = (cmx - seed_scale[0] * smx, cmy - seed_scale[1] * smy)
    best = register.coarse_affine(
        s_r, c_r,
        _sweep(seed_scale[0], p["scale_pct"], p["scale_step_pct"]),
        _sweep(seed_scale[1], p["scale_pct"], p["scale_step_pct"]),
        _offsets(seed_off[0], int(p["offset_px"]), int(p["offset_step"])),
        _offsets(seed_off[1], int(p["offset_px"]), int(p["offset_step"])))
    log(f"    coarse 1/{st}: IoU {best.iou:.4f} scale ({best.scale[0]:.4f}, {best.scale[1]:.4f})")

    st2 = max(1, st // 2)
    if st2 != st:
        s2, c2 = src_land[::st2, ::st2], canvas_land[::st2, ::st2]
        k = st // st2
        best = register.coarse_affine(
            s2, c2,
            _sweep(best.scale[0], 2.0, 1.0), _sweep(best.scale[1], 2.0, 1.0),
            _offsets(best.offset[0] * k, 3, 1), _offsets(best.offset[1] * k, 3, 1))
        scale = best.scale
        off = (best.offset[0] * st2, best.offset[1] * st2)
        log(f"    fine   1/{st2}: IoU {best.iou:.4f} scale ({scale[0]:.4f}, {scale[1]:.4f})")
    else:
        scale, off = best.scale, (best.offset[0] * st, best.offset[1] * st)
    info: dict = {
        "seed_scale": [round(v, 4) for v in seed_scale],
        "scale": [round(float(scale[0]), 5), round(float(scale[1]), 5)],
        "offset": [round(float(off[0]), 2), round(float(off[1]), 2)],
        "coarse_iou": round(float(best.iou), 4),
    }

    nx, ny = (int(v) for v in p["lattice"])
    src_pts = register.lattice_box((0.0, 0.0, float(sw), float(sh)), nx, ny)
    aff = np.column_stack([src_pts[:, 0] * scale[0] + off[0], src_pts[:, 1] * scale[1] + off[1]])

    lm_src = np.array([lm.source for lm in landmarks], dtype=np.float64).reshape(-1, 2)
    lm_cvs = np.array([lm.canvas for lm in landmarks], dtype=np.float64).reshape(-1, 2)
    lm_aff = np.column_stack([lm_src[:, 0] * scale[0] + off[0], lm_src[:, 1] * scale[1] + off[1]])
    resid = lm_cvs - lm_aff
    info["landmarks"] = [
        {"name": lm.name, "feature": lm.feature, "residual_px": round(float(np.hypot(*r)), 1)}
        for lm, r in zip(landmarks, resid)]

    canvas_pts = aff.copy()
    if len(landmarks):
        field = _residual_field(lm_aff, resid, aff, float(p["influence_px"]))
        canvas_pts = aff + field(aff)
        # The landmarks themselves become control points: exact there by construction. A lattice
        # point that sits on a landmark is dropped, since two coincident points make the
        # thin-plate system singular.
        dup = np.hypot(src_pts[:, None, 0] - lm_src[None, :, 0],
                       src_pts[:, None, 1] - lm_src[None, :, 1]).min(axis=1) < 1.0
        src_pts, canvas_pts = src_pts[~dup], canvas_pts[~dup]
        src_pts = np.concatenate([src_pts, lm_src])
        canvas_pts = np.concatenate([canvas_pts, lm_cvs])

    info.update(_warp_quality(src_pts, canvas_pts, src_land, canvas_land))
    if info["folded_fraction"] > 0:
        info["warning"] = ("the final warp folds; landmarks may disagree with each other - "
                           "see their residuals")
    return src_pts, canvas_pts, info


def _residual_field(lm_aff: np.ndarray, resid: np.ndarray, lattice_aff: np.ndarray,
                    influence: float):
    """Callable canvas-point -> displacement, exact at the landmarks, ~0 far from them."""
    n = len(lm_aff)
    if n < 3:
        mean = resid.mean(axis=0)
        return lambda pts: np.broadcast_to(mean, np.shape(pts)).copy() * _fade(pts, lm_aff, influence)[:, None]
    d = np.hypot(lattice_aff[:, None, 0] - lm_aff[None, :, 0],
                 lattice_aff[:, None, 1] - lm_aff[None, :, 1]).min(axis=1)
    pins = lattice_aff[d > influence]
    pts = np.concatenate([lm_aff, pins]) if len(pins) else lm_aff
    val = np.concatenate([resid, np.zeros((len(pins), 2))]) if len(pins) else resid
    rbf = RBFInterpolator(pts, val, kernel="thin_plate_spline", degree=1)
    return lambda q: rbf(np.asarray(q, dtype=np.float64))


def _fade(pts, anchors: np.ndarray, influence: float) -> np.ndarray:
    """1 at an anchor falling to 0 at ``influence`` px (used only for <3 landmarks)."""
    q = np.asarray(pts, dtype=np.float64)
    d = np.hypot(q[:, None, 0] - anchors[None, :, 0], q[:, None, 1] - anchors[None, :, 1]).min(axis=1)
    return np.clip(1.0 - d / influence, 0.0, 1.0)


def _warp_quality(src_pts, canvas_pts, src_land, canvas_land) -> dict:
    step = 8
    r = register.warp_mask(src_pts, canvas_pts, src_land, canvas_land.shape, step=step)
    small = canvas_land[::step, ::step]
    h, w = r.land.shape
    return {
        "iou": round(float(register.two_sided_iou(r.land[:small.shape[0], :small.shape[1]],
                                                  small[:h, :w])), 4),
        "folded_fraction": round(float(r.folded), 5),
        "anisotropy_p99": round(float(r.anisotropy), 2),
    }


def placement_record(source: str, src_pts: np.ndarray, canvas_pts: np.ndarray,
                     crop_shape: tuple[int, int], src_shape: tuple[int, int]
                     ) -> schema.SourceRegistration:
    """An in-memory ``control_point_warp`` record for ``cells.warp_cells``; never written.

    Built directly rather than through ``from_dict``: crop-local canvas points may be negative
    (CR's box can land partly outside our crop) and the schema forbids that for committed
    records, which this is not. The footprint is the whole crop (the box + 64 px the caller cut).
    """
    cps = [schema.ControlPoint((float(sx), float(sy)), (float(cx), float(cy)), "cr_partition")
           for (sx, sy), (cx, cy) in zip(src_pts, canvas_pts)]
    h, w = crop_shape
    return schema.SourceRegistration(
        source=source, role="cr_partition_placement", projection="control_point_warp",
        control_points=cps, crop=None, footprint=(0.0, 0.0, float(w), float(h)),
        precedence=0, layer_precedence={}, frame_alias=None, master_shape=tuple(src_shape))


def forward_map(src_pts: np.ndarray, canvas_pts: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Where crop-local source px land on the canvas crop, through the same control points."""
    rbf = RBFInterpolator(np.asarray(src_pts), np.asarray(canvas_pts),
                          kernel="thin_plate_spline", degree=1)
    return rbf(np.asarray(pts, dtype=np.float64))


# ---------------------------------------------------------------------------
# Borders: lines, closing lines, snap, provenance
# ---------------------------------------------------------------------------

def lines_from_labels(labels: np.ndarray, scope: np.ndarray) -> np.ndarray:
    """A scope pixel is marked when its right or down 4-neighbour is scope land with a
    different label. One pixel of line is enough to block the generator's 4-connected fill."""
    out = np.zeros(labels.shape, dtype=bool)
    a, b = labels[:, :-1], labels[:, 1:]
    m = (a != b) & scope[:, :-1] & scope[:, 1:] & (a > 0) & (b > 0)
    out[:, :-1] |= m
    a, b = labels[:-1], labels[1:]
    m = (a != b) & scope[:-1] & scope[1:] & (a > 0) & (b > 0)
    out[:-1] |= m
    return out


def closing_line(scope: np.ndarray, open_land: np.ndarray) -> np.ndarray:
    """Scope pixels 4-adjacent to land that is outside scope but undrawn and touching it
    (the box or hull cut), so no proposed state is open to the rest of an unlined continent."""
    near = np.zeros(scope.shape, dtype=bool)
    near[:, 1:] |= open_land[:, :-1]
    near[:, :-1] |= open_land[:, 1:]
    near[1:] |= open_land[:-1]
    near[:-1] |= open_land[1:]
    return near & scope & ~open_land


def _pair_boundaries(labels: np.ndarray, scope: np.ndarray) -> dict[tuple[int, int], np.ndarray]:
    """Boundary pixels (both sides) per unordered label pair, as boolean full-size masks."""
    pairs: dict[tuple[int, int], np.ndarray] = {}

    def add(a, b, ya, xa, yb, xb):
        m = (a != b) & (a > 0) & (b > 0)
        for y, x in zip(*np.nonzero(m)):
            key = (int(min(a[y, x], b[y, x])), int(max(a[y, x], b[y, x])))
            if key not in pairs:
                pairs[key] = []
            pairs[key].append((y + ya, x + xa, y + yb, x + xb))

    ls = np.where(scope, labels, 0)
    add(ls[:, :-1], ls[:, 1:], 0, 0, 0, 1)
    add(ls[:-1], ls[1:], 0, 0, 1, 0)
    out = {}
    for key in sorted(pairs):
        arr = np.array(pairs[key], dtype=np.int64)
        m = np.zeros(labels.shape, dtype=bool)
        m[arr[:, 0], arr[:, 1]] = True
        m[arr[:, 2], arr[:, 3]] = True
        out[key] = m
    return out


def snap_to_features(labels: np.ndarray, scope: np.ndarray, features: np.ndarray,
                     snap_px: int = 8, follow_frac: float = 0.6) -> tuple[np.ndarray, dict]:
    """Move a border onto a river or impassable edge that already runs along most of it.

    A pair (a, b) qualifies when at least ``follow_frac`` of its shared boundary lies within
    ``snap_px`` of a feature. Its band is the boundary dilated by ``snap_px``, inside scope and
    inside a or b. The band is cut by the feature into pieces; it snaps only when at least one
    piece has an a-majority and one a b-majority among its neighbours outside the band, so a
    river that ends mid-band changes nothing (that pair is reported, not moved). Computed
    against the pre-snap raster; bands that overlap an earlier pair's band are skipped.
    """
    out = labels.copy()
    report = {"snapped": [], "not_followed": [], "not_splitting": [], "overlap_skipped": []}
    if not features.any():
        return out, report
    dist = ndimage.distance_transform_edt(~features)
    used = np.zeros(labels.shape, dtype=bool)
    for (a, b), bnd in _pair_boundaries(labels, scope).items():
        frac = float((dist[bnd] <= snap_px).mean())
        if frac < follow_frac:
            report["not_followed"].append([a, b, round(frac, 2)])
            continue
        band = ndimage.binary_dilation(bnd, iterations=int(snap_px)) & scope & ((labels == a) | (labels == b))
        if (band & used).any():
            report["overlap_skipped"].append([a, b])
            continue
        free = band & ~features
        comp, n = ndimage.label(free)
        votes: dict[int, int] = {}
        for c in range(1, n + 1):
            piece = comp == c
            ring = ndimage.binary_dilation(piece) & scope & ~band
            na = int((labels[ring] == a).sum())
            nb = int((labels[ring] == b).sum())
            votes[c] = a if na > nb else (b if nb > na else 0)
        if a not in votes.values() or b not in votes.values():
            report["not_splitting"].append([a, b])
            continue
        assign = np.zeros(labels.shape, dtype=np.int32)
        for c, v in votes.items():
            if v:
                assign[comp == c] = v
        have = assign > 0
        idx = ndimage.distance_transform_edt(~have, return_distances=False, return_indices=True)
        filled = assign[tuple(idx)]
        out[band] = filled[band]
        used |= band
        report["snapped"].append([a, b, round(frac, 2)])
    return out, report


def provenance(final: np.ndarray, sampled: np.ndarray) -> dict[int, dict]:
    """Per final state: area, anchor (max distance-to-edge pixel; ties lowest y then x) and the
    CR source labels covering it, as ``{cr_label: share}``. ``sampled`` is the CR label raster
    after the warp and mask, before the fill (0 where CR reached nothing)."""
    out: dict[int, dict] = {}
    for lab in (int(v) for v in np.unique(final) if v > 0):
        m = final == lab
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        loc = np.pad(m[y0:y1, x0:x1], 1)
        d = ndimage.distance_transform_edt(loc)[1:-1, 1:-1]
        top = np.argwhere(d == d.max())
        ay, ax = top[np.lexsort((top[:, 1], top[:, 0]))[0]]
        vals, counts = np.unique(sampled[m & (sampled > 0)], return_counts=True)
        tot = int(m.sum())
        out[lab] = {
            "area_px": tot,
            "anchor": [int(ax + x0), int(ay + y0)],
            "cr_shares": {int(v): round(float(c) / tot, 4) for v, c in zip(vals, counts)},
        }
    return out
