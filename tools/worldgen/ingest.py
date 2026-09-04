"""The ingestion core — one code path shared by the real run and the fixture.

``generate_heightmap.py`` orchestrates the real whole-world build (logging,
mosaic, the colored_globe relief layer, the map-editor hand-off); the offline fixture
(``run_fixture.py``) drives a tiny synthetic world through the same steps. If the
two used *different* code, the fixture would regression-test a parallel
reimplementation and prove nothing about the generator. So every step that is not
pure orchestration lives here, parameterised by canvas size and filter widths,
and both callers import it.

The steps, in order (source space, then canvas space):

    denoise -> classify -> polar rule -> de-ink -> smooth     (source res)
    reproject -> clean land mask (area despeckle lives here)  (canvas res)
    encode with the shoreline forced to the mask              (heightmap res)

Area despeckling sits on the canvas side on purpose: the source-to-canvas stretch
runs 4.0x to 15.4x across the band, so a threshold in source pixels does not mean
one thing. Canvas area is *screen* area, which is what the player and the engine
both see.

Everything is deterministic: no RNG, no wall-clock, no threaded kernels — the
same inputs give byte-identical output, which is what the fixture pins.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from worldgen import lut, reproject, schema, segment

# ---------------------------------------------------------------------------
# The spatial polar rule
# ---------------------------------------------------------------------------


#: Swatch indices blank page is allowed to classify as. Page is pale, and the
#: ramp's palest swatches are its *deepest* ocean, so page lands on band 0 or —
#: where the scan runs slightly darker — band 1. Both are needed: the southern
#: page wedge that reaches up between the arms of the Kuresh peninsula classifies
#: as band 1, and restricting to band 0 alone breaks the flood's connectivity
#: there and leaves a semicircular hole in drawn land.
#:
#: Widening it is safe, and that is measured rather than assumed: the flood's
#: stopping latitude is **unchanged** between {0}, {0,1} and {0,1,2} (north
#: 60.0/59.1/59.1 N, south -52.95 S in all three). If widening were letting the
#: flood into real ocean the stopping point would move. Band 2 is left out
#: because it buys nothing and is a genuinely common abyssal depth.
PAGE_BANDS = (0, 1)


@dataclass(frozen=True)
class PolarRim:
    """Where blank page may be reached from, for :func:`polar_waste`.

    The reference map leaves the polar Chaos Wastes un-inked at **both** poles.
    Deciding what that blank page *means* used to be a colour comparison, and it
    was ill-conditioned to the point of being unusable (see ``worldgen/lut``).
    This carries the geometry the replacement rule needs instead.

    The rule in one sentence: *blank page is what you can reach from the edge of
    the drawn world without crossing terrain.* The map has two such edges, and
    both are needed — the southern one is not cropped away by the Miller reframe
    the way the plan assumed. It reaches to -52.95 S, which is 4.5 degrees inside
    the canvas.

    ``envelope``
        Source-shaped bool: pixels inside the map's drawn envelope. Keeps the
        flood off the page margin, the title block and the polar insets, all of
        which are the same blank page and none of which are the world.
    ``north_seed`` / ``south_seed``
        Source row ranges to seed each flood from — a band rather than a single
        row, so one row of drawn boundary rule cannot starve it. ``south_seed``
        may be ``None`` for a source with no southern page.
    ``north_limit`` / ``south_limit``
        Hard caps: the north flood may not pass south of ``north_limit``, the
        south flood may not pass north of ``south_limit``. Safety nets, measured
        not to bind — see ``generate_heightmap.POLAR_FLOOD_*``.
    ``min_distance``
        Defaults to **0, i.e. off**, and that default is a measurement, not
        laziness. The intuition it was written for — that blank page sits far
        from the deepest-ocean swatch while real ocean sits on it, so distance
        could act as a barrier — is false on this source: sampled across the
        on-canvas polar band, page classifies as band 0 at a median distance of
        **10.0** (p95 26.8), the same neighbourhood as genuine deep ocean. Page
        and abyss are colorimetrically indistinguishable. That is the whole
        reason this rule is spatial, and a non-zero barrier here does not make it
        safer — it just deletes most of the polar band from consideration. Left
        as a knob for a future source whose page really does separate.
    """

    envelope: np.ndarray
    north_seed: tuple[int, int]
    north_limit: int
    south_seed: tuple[int, int] | None = None
    south_limit: int | None = None
    min_distance: float = 0.0
    bands: tuple[int, ...] = PAGE_BANDS


@dataclass(frozen=True)
class PolarReport:
    """What :func:`polar_waste` actually did, so the build can report it."""

    flipped: int          # pixels the rim floods claimed as waste
    enclosed: int         # page-band pixels they did NOT reach (the real basins)
    eligible: int         # page-band pixels considered at all
    band_zero: int        # page-band pixels in the envelope, total
    north_row: int        # southernmost row the NORTH flood reached (-1 if none)
    south_row: int        # northernmost row the SOUTH flood reached (-1 if none)

    @property
    def enclosed_fraction(self) -> float:
        return self.enclosed / self.band_zero if self.band_zero else 0.0


def polar_waste(band: np.ndarray, dist: np.ndarray, rim: PolarRim):
    """``(mask, report)`` — blank polar page, found by connectivity not colour.

    The rule in one sentence: *blank page is what you can reach from the top of
    the map without crossing terrain.* An enclosed basin in the middle of an
    ocean is unreachable by construction, however similar its colour, which is
    the thing no RGB threshold could deliver.

    Implemented as a labelling rather than an explicit flood loop, so there is no
    iteration order to get wrong and the result is byte-reproducible:
    ``ndimage.label`` is deterministic, and the seed labels are taken through a
    sorted ``np.unique``.
    """
    in_env = np.isin(band, rim.bands) & rim.envelope
    eligible = in_env.copy()
    if rim.min_distance > 0:
        eligible &= dist > rim.min_distance

    def flood(seed_rows: tuple[int, int], lo: int, hi: int) -> np.ndarray:
        e = eligible.copy()
        e[:max(0, lo)] = False
        e[min(e.shape[0], hi):] = False
        labels, _ = ndimage.label(e)
        seed = labels[seed_rows[0]:seed_rows[1]]
        picked = np.unique(seed[seed > 0])
        return np.isin(labels, picked) if picked.size else np.zeros_like(e)

    h = band.shape[0]
    north = flood(rim.north_seed, rim.north_seed[0], rim.north_limit)
    south = (flood(rim.south_seed, rim.south_limit, rim.south_seed[1])
             if rim.south_seed is not None else np.zeros_like(eligible))
    mask = north | south

    nr = np.nonzero(north.any(axis=1))[0]
    sr = np.nonzero(south.any(axis=1))[0]
    return mask, PolarReport(
        flipped=int(mask.sum()),
        enclosed=int((in_env & ~mask).sum()),
        eligible=int(eligible.sum()),
        band_zero=int(in_env.sum()),
        north_row=int(nr.max()) if nr.size else -1,
        south_row=int(sr.min()) if sr.size else -1,
    )


def ne2_envelope(fit, shape: tuple[int, int]) -> np.ndarray:
    """Source-shaped bool: pixels inside the drawn Natural Earth II oval.

    The oval's half-width at a given latitude is ``sx * pi * f(phi)`` — the same
    forward polynomial the reprojection uses — so this is the fitted envelope
    itself, not an eyeballed ellipse.
    """
    h, w = shape
    ys = np.arange(h, dtype=np.float64) + 0.5
    _, phi = reproject.ne2_inverse(np.zeros_like(ys), (fit.cy - ys) / fit.sy)
    half = fit.sx * np.pi * np.asarray(reproject.ne2_forward(1.0, phi)[0])
    xs = np.arange(w, dtype=np.float64) + 0.5
    return np.abs(xs[None, :] - fit.cx) <= half[:, None]


def source_row_for_lat(fit, lat_deg: float) -> int:
    """The source row a latitude falls on. Latitude-only, so it is a constant row."""
    y = reproject.ne2_forward(0.0, np.radians(lat_deg))[1]
    return int(round(fit.cy - fit.sy * float(y)))

# ---------------------------------------------------------------------------
# Source-space classification (the novel de-ink / despeckle stage)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceFields:
    """Everything the classify stage produces, at *source* resolution.

    ``elev`` is smoothed metres, ``land`` a smoothed 0..1 land fraction (float so
    the reprojected shoreline lands on a sub-pixel boundary rather than a
    stair-stepped one). ``dist`` (colour distance to the winning swatch), ``ink``
    (the erased lettering/graticule mask) and ``polar`` (what the rim flood
    claimed) are carried out for the caller to report on — they are diagnostics,
    not further inputs.
    """

    elev: np.ndarray
    land: np.ndarray
    dist: np.ndarray
    ink: np.ndarray
    polar: np.ndarray
    polar_report: PolarReport | None = None


def graticule_mask(lum: np.ndarray, *, bg: int = 9, coherence: int = 21,
                   threshold: float = 6.0, dilate: int = 1) -> np.ndarray:
    """Boolean mask of the source's ruled graticule — thin, straight, *dark* lines.

    The reference globe rules a latitude/longitude graticule directly over the
    terrain wash. Most of it is dark enough for :func:`lut.unexplained_ink` to
    catch, but its faintest segments (a dip of only ~10 luminance over the wash)
    slip under the ink thresholds, classify into a neighbouring elevation band,
    and survive as a regular grid embossed into the heightmap — visible even
    zoomed out.

    A plain darkness test cannot separate that faint graticule from ordinary
    terrain speckle. What distinguishes a graticule line is **structure**: it is
    dark relative to its *perpendicular* neighbours and it stays dark *coherently
    along its own axis* for a long run. This detector encodes exactly that, once
    per axis:

    * ``bg`` — a median over a short perpendicular window is the local background
      a line pixel is measured against (a line 1-3 px wide is invisible to a
      median that wide, so the median is the terrain *without* the line).
    * ``coherence`` — the perpendicular-darkness is averaged along the line axis;
      a real line reinforces over that run while isolated speckle averages toward
      zero. ``threshold`` is the surviving averaged darkness that counts as a line.

    Broad dark terrain (a mountain shadow, a forest) is not thin, so it never
    enters the perpendicular-darkness in the first place; that is what keeps this
    off real relief. ``dilate`` grows the mask to swallow each line's anti-aliased
    shoulder. All parameters are in source pixels.
    """
    from scipy import ndimage
    lum = lum.astype(np.float32)
    bg_h = ndimage.median_filter(lum, footprint=np.ones((1, bg), bool))
    v = ndimage.uniform_filter1d(np.clip(bg_h - lum, 0, None), coherence, axis=0, mode="nearest")
    bg_v = ndimage.median_filter(lum, footprint=np.ones((bg, 1), bool))
    h = ndimage.uniform_filter1d(np.clip(bg_v - lum, 0, None), coherence, axis=1, mode="nearest")
    mask = (v > threshold) | (h > threshold)
    if dilate > 0:
        mask = ndimage.binary_dilation(mask, iterations=int(dilate))
    return mask


def degrid_rgb(rgb: np.ndarray, *, sigma: float = 3.0, **mask_kw) -> np.ndarray:
    """Repair the ruled graticule in ``rgb`` *before* it is classified.

    Removing the graticule from the classified *elevation* is the wrong order:
    once a dark line has classified into the >7000 m band it is a thin ridge, and
    filling that ridge with :func:`lut.inpaint_nearest` leaves a seam straight
    down its centre (nearest-fill of an axis-aligned strip meets in the middle).
    So this fixes the *input* instead — it replaces the graticule pixels' colour
    with a **normalized-convolution** estimate of the terrain colour underneath
    (a Gaussian-weighted average of the non-graticule neighbours on *both* sides),
    which interpolates across the line without a centre seam. Classification then
    never sees a line to emboss.

    Only pixels in :func:`graticule_mask` change; everything else is byte-for-byte
    the input. Deterministic (median + Gaussian, no RNG).
    """
    from scipy import ndimage
    lum = rgb.astype(np.float32).mean(axis=2)
    mask = graticule_mask(lum, **mask_kw)
    valid = (~mask).astype(np.float32)
    denom = ndimage.gaussian_filter(valid, sigma)
    out = rgb.astype(np.float32).copy()
    for c in range(rgb.shape[2]):
        num = ndimage.gaussian_filter(rgb[..., c].astype(np.float32) * valid, sigma)
        filled = num / np.maximum(denom, 1e-6)
        out[..., c][mask] = filled[mask]
    return out.astype(rgb.dtype)


def classify_source(
    rgb: np.ndarray,
    elut: schema.ElevationLUT,
    *,
    denoise_size: int = 3,
    ink_dilate: int = lut.INK_DILATE,
    majority: int = 7,
    wrap_x: bool = False,
    elev_sigma: float = 2.0,
    land_sigma: float = 1.0,
    polar_rim: PolarRim | None = None,
    degrid: bool = False,
    despeckle: int = 0,
) -> SourceFields:
    """Colour image -> smoothed elevation + land fraction, with ink removed.

    The de-ink step is the one that matters most and is easiest to get wrong: the
    reference map's lettering and graticule classify as the darkest (highest)
    swatch, so without removing them every place name embosses into the heightmap
    as a mountain range. It is done here, at source resolution, before anything is
    reprojected — a stroke is still a few pixels wide here and its neighbours can
    fill it; after a 2-4x upscale it would be an unfixable ridge.

    ``polar_rim`` turns on the spatial polar-waste rule (:func:`polar_waste`).
    It runs *before* de-inking, because a pixel the flood has already decided is
    blank page must not then be inpainted from its neighbours.

    **Area despeckling is deliberately not done here.** It used to be — a
    ``min_blob`` in *source* pixels — but the source-to-canvas stretch runs from
    4.0x at the equator to 15.4x at the top of the band, so a fixed source
    threshold meant an effective canvas threshold that varied 3.8x across the map
    and was tightest exactly where the artwork is least reliable. It now happens
    once, on the canvas, where area is screen area and one number means one thing
    (``generate_heightmap.CANVAS_MIN_BLOB``). ``majority`` stays here: it targets
    drawn strokes, which are genuinely source-scale features.

    ``wrap_x`` is False for a cropped whole-world source (its left/right edges are
    the antimeridian, not neighbours) and True for a synthetic source that tiles
    the globe. The majority filter honours it so a coastline on the seam is not
    tulipped by edge effects.
    """
    den = lut.denoise(rgb, denoise_size)
    if degrid:
        # Repair the ruled graticule in the colour image before it can classify
        # into a band and emboss a regular grid into the elevation. See degrid_rgb.
        den = degrid_rgb(den)
    elev, is_land, dist, band = lut.classify(den, elut)

    polar = np.zeros(is_land.shape, dtype=bool)
    report = None
    if polar_rim is not None:
        polar, report = polar_waste(band, dist, polar_rim)
        elev = np.where(polar, np.float32(elut.paper_elevation_m), elev)
        is_land = is_land | polar

    # Ink is judged against terrain *or* page: blank page is not ink, even though
    # it is deliberately not a classification swatch. See lut.distance_to_paper.
    explained = np.minimum(dist, lut.distance_to_paper(den, elut))
    ink = lut.unexplained_ink(den, explained, dilate=ink_dilate) & ~polar
    elev = lut.inpaint_nearest(elev, ink)
    is_land = lut.inpaint_nearest(is_land, ink)

    is_land = segment.majority_filter(is_land, majority, wrap_x=wrap_x)

    elev = lut.smooth_elevation(elev, sigma=elev_sigma)
    if despeckle:
        # A light *uniform* median removes isolated single-pixel band-jitter (the
        # LUT turns every small colour wobble in the painted terrain wash into a
        # one-pixel bump) so the relief layer added downstream — colored_globe's
        # high-frequency texture — lands on a clean base instead of stacking on the
        # LUT's own speckle. Deliberately uniform, not the old low-ground-weighted
        # flatten: vanilla's plains are textured, not dead-flat, so this only kills
        # per-pixel noise and leaves real relief for the relief layer to sit on.
        elev = ndimage.median_filter(elev, size=despeckle).astype(np.float32)
    land_f = lut.smooth_elevation(is_land.astype(np.float32), sigma=land_sigma)
    return SourceFields(elev=elev, land=land_f, dist=dist, ink=ink,
                        polar=polar, polar_report=report)


# ---------------------------------------------------------------------------
# Reprojection onto the canvas (blocked, crop-clamped)
# ---------------------------------------------------------------------------


def clamped_source_coords(reg: schema.SourceRegistration, fit, y_rows, width, height):
    """Source coordinates for canvas rows ``y_rows``, clamped into the crop.

    Clamping rather than masking is deliberate for a whole-world source: the
    canvas seam at lon +-180 projects exactly onto the oval's drawn boundary
    rule, and sampling that black line would classify as the darkest swatch — a
    thin strip of false >7000 m "land" down both edges of the world. Clamping
    reuses the ocean pixel just inside the rule instead.
    """
    sx, sy = reproject.source_coords_parametric(fit, y_rows, width, height)
    if reg.crop is not None:
        x0, y0, x1, y1 = reg.crop
        np.clip(sx, x0, x1, out=sx)
        np.clip(sy, y0, y1, out=sy)
    return sx, sy


def reproject_plane(reg, fit, plane, out_w, out_h, *, block_rows, order=1, dtype=np.float32):
    """Reproject one source plane onto an ``out_w`` x ``out_h`` grid, in row blocks.

    Blocking bounds peak memory: only ``block_rows`` of the target's float
    coordinate grids exist at once, so a 118-megapixel heightmap builds in a few
    hundred MB rather than gigabytes.
    """
    out = np.empty((out_h, out_w), dtype=dtype)
    for y0 in range(0, out_h, block_rows):
        y1 = min(out_h, y0 + block_rows)
        rows = np.arange(y0, y1)
        sx, sy = clamped_source_coords(reg, fit, rows, out_w, out_h)
        out[y0:y1] = reproject.resample(plane, sx, sy, order=order)
    return out


# ---------------------------------------------------------------------------
# Heightmap encoding (metres -> vanilla uint16, shoreline forced to the mask)
# ---------------------------------------------------------------------------


def encode_heightmap(elev_m, land, *, sea_level, units_per_metre, shore_margin) -> np.ndarray:
    """Metres -> the uint16 encoding vanilla uses, with the shoreline forced.

    Any land pixel is pushed at least ``shore_margin`` above sea level and any
    sea pixel at least that far below, so the heightmap's coastline can never
    contradict the committed land/sea mask that provinces.png is cut from — a
    disagreement there is a coastal province the engine would render underwater.
    """
    v = np.round(sea_level + units_per_metre * np.asarray(elev_m, dtype=np.float32))
    np.clip(v, 0, 65535, out=v)
    out = v.astype(np.uint16)
    lo = np.uint16(sea_level + shore_margin)
    hi = np.uint16(sea_level - shore_margin)
    np.maximum(out, lo, out=out, where=land)
    np.minimum(out, hi, out=out, where=~land)
    return out


def upscale2_rows(mask: np.ndarray, y0: int, y1: int) -> np.ndarray:
    """Rows ``[y0, y1)`` of ``mask`` upscaled 2x on both axes.

    Computed for the row slice only, so the full 2x array never has to exist. The
    heightmap is exactly twice the canvas, so nearest-neighbour 2x is exact —
    which is what makes "force the heightmap shoreline to the canvas mask" a
    lossless operation rather than an approximate one.
    """
    src = mask[y0 // 2:(y1 + 1) // 2]
    big = np.repeat(np.repeat(src, 2, axis=0), 2, axis=1)
    return big[(y0 % 2):(y0 % 2) + (y1 - y0)]
