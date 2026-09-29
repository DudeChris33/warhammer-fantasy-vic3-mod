"""The pure arable-potential field (board #4921, epic #3675).

A single continuous, canvas-aligned raster of *relative* arable potential over the
drawn Old World — barren -> breadbasket — with **no Victoria 3 ``arable_land``
numbers** anywhere. It sits *before* the epic's calibration work and is the shared
physical+lore prior the realm children (#3679-#3686) sample instead of each
re-deriving one. Proportions only: a normalized 0..1 intensity, water/lake/
impassable pinned to zero.

This module is the **pure core**: :func:`build_field` composes four documented
factors on the canvas grid and returns a float field plus a provenance stats dict.
Zero I/O, no RNG, no wall-clock — the driver ``mapgen/generate_arable_heatmap.py``
reads the committed inputs, calls this, and encodes the 16-bit PNG. The whole thing
is a pure function of committed inputs, so regeneration is byte-identical (the
repo's regenerate-never-hand-edit discipline; "MP determinism" here means
reproducibility, not engine MP-sync — the raster is never loaded by Victoria 3).

The field
=========

``field = C(lat) . T(elev, slope) . H(river, coast) . M(wind) . L(lore)``, masked to
zero off passable land, tone-curved, then percentile-normalized to 0..1.

1. **Climate ``C(lat)``** — a closed-form smooth latitude envelope (post-scope
   review panel, geographer): a temperate breadbasket bump peaking at ~50 deg
   (Reikland/Bretonnia, not a naive ~30 deg optimum that would rank Araby above
   the Empire), a modest humid-tropical shoulder near the equator, and — the
   panel's must-fix — a **subtropical-arid trough at ~23 deg** so Araby (~20 N)
   and Nehekhara (~14.5 N) sit in the Hadley-descent desert minimum instead of
   handing the map's largest arable discontinuity entirely to the lore layer. A
   hard polar taper falls out of the temperate bump's own decay (Chaos-waste
   extremes -> ~0). Latitude is x-independent, so ``C`` is one row vector
   broadcast across the canvas.

2. **Terrain ``T``** — from the committed heightmap (metres above sea level,
   canvas grid). Two multiplicative parts: an **elevation** term (lowland -> 1,
   ramping to ~0 across a high-elevation band) and a **slope** term (flat -> 1,
   steep -> suppressed), the slope taken from the gradient of a Gaussian-smoothed
   elevation whose sigma **bridges the shoreline sea-level step** (panel cross-lane
   note) so no dark suppression fringe fights the coast boost. This is what makes
   the Worlds Edge / Grey / Vaults spines read barren with no lore input.

3. **Hydrology ``H >= 1``** — a bounded multiplier, not a 0..1 factor:
   ``1 + a.w.exp(-d_river/lr) + b.C.exp(-d_coast/lc)`` where ``d_river`` /
   ``d_coast`` are Euclidean distance transforms from the drawn river pixels and
   the sea edge. The **coast** term is gated by the climate factor ``C`` (panel
   must-fix: an ungated coast boost lifts arid coastlines — the Namib/Atacama
   problem). The **river** term is deliberately *not* climate-gated but the base
   ``C`` still multiplies through, so under the pinned "current arable" decision a
   desert river reads net-barren unless lore lifts it (Nehekhara's dead Vitae),
   while a temperate river valley reads as the fertile floor. The river term is
   weighted by the drawn stream width so the Reik/Talabec/Stir/Aver dominate.

3b. **Moisture / rain shadow ``M``** — prevailing-wind advection reusing the
   three-cell belt premise of ``render_wind_patterns.py`` (its zonal, moisture
   -bearing component). Ocean is the moisture source; over land, moisture is
   advected zonally from the upwind coast, losing a fixed fraction per px of
   overland fetch (**continentality** — hardens the deep interior, e.g. Kislev's
   steppe) and an orographic fraction wherever terrain rises into the wind (**rain
   shadow** — the lee of a range goes barren, e.g. the Dark Lands east of the
   Worlds Edge, Cathay's Warpstone Desert). This is what lets interior/lee deserts
   read barren *physically* rather than one hand-placed lore blight at a time; the
   latitude ``C`` still owns the subtropical (Araby/Nehekhara) deserts. Bounded to
   ``[moist_floor, 1]`` and toggleable (``moist_enable``) for a physical-only
   fallback.

4. **Lore ``L``** — from the committed ``mapgen/config/arable_lore.json`` anchor
   zones (:class:`worldgen.schema.ArableLoreZone`). ``L`` starts at 1.0; each zone
   multiplies a smooth radial bump (smoothstep falloff, 1.0 at the radius), a
   breadbasket lifting (factor>1) and a blight suppressing (factor<1). Overlapping
   zones compose multiplicatively. This is climate/curse adjustment — blessed
   vales, deserts, Chaos taint — *not* re-suppressing terrain the physical model
   already handles.

Then: mask to zero off ``passable``; **normalize** by the P-th percentile
(default 99.5) of the passable field so one blessed outlier can't crush the ramp;
clip to [0,1]; apply a **gamma tone curve** (panel/cartographer must-fix — a heavy
``C.T.H.L`` tail under a linear stretch reads as "mostly barren with thin bright
ribbons"; gamma<1 lifts the populated mid-range into a smooth cropland gradient).
The normalization value, gamma, and the field histogram are returned for the
sidecar so any shift between regenerations is visible in a diff.
"""

from __future__ import annotations

from dataclasses import dataclass, field as _dc_field

import numpy as np
from scipy import ndimage

__all__ = ["ArableParams", "climate_curve", "build_field"]


# ---------------------------------------------------------------------------
# Tunable constants (named here per the generate_rivers idiom; the driver
# threads the handful that are CLI-tunable — gamma and the norm percentile).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ArableParams:
    # --- climate C(lat), degrees ---
    #: Temperate breadbasket bump: peak latitude, width (deg), amplitude.
    temp_peak: float = 50.0
    temp_sigma: float = 15.0
    temp_amp: float = 1.0
    #: Humid-tropical shoulder near the equator: amplitude, width (deg).
    trop_amp: float = 0.45
    trop_sigma: float = 12.0
    #: Subtropical-arid trough (Hadley descent): centre lat, width, depth (0..1).
    arid_lat: float = 23.0
    arid_sigma: float = 8.0
    arid_depth: float = 0.78

    # --- terrain T ---
    #: Elevation suppression band, metres above sea level: full arable at/below
    #: ``elev_lo_m``, ramping (smoothstep) to zero at/above ``elev_hi_m``.
    elev_lo_m: float = 400.0
    elev_hi_m: float = 2600.0
    #: Gaussian sigma (canvas px) on the elevation field before the slope gradient
    #: — wide enough to bridge the shoreline sea-level step and denoise.
    elev_smooth_sigma: float = 6.0
    #: Slope suppression: the slope (m per canvas px) mapped to full suppression is
    #: this percentile of the passable-land slope; a robust, data-adaptive scale.
    slope_pctl: float = 96.0
    #: Floor on the slope term so a merely-hilly region is not driven to zero.
    slope_floor: float = 0.12

    # --- hydrology H ---
    #: River-proximity boost amplitude and decay length (canvas px).
    river_amp: float = 1.3
    river_lambda: float = 22.0
    #: Reference drawn width (rivers.png ramp tops out at 8) and the floor weight a
    #: narrow river still earns, so width only *modulates* the boost.
    river_width_ref: float = 8.0
    river_width_floor: float = 0.35
    #: Coast-proximity boost amplitude and decay length (canvas px). Climate-gated.
    coast_amp: float = 0.55
    coast_lambda: float = 34.0

    # --- moisture / rain shadow M (wind patterns) ---
    #: Prevailing-wind moisture advection, reusing the three-cell belt premise of
    #: render_wind_patterns.py: moisture-bearing air travels *zonally* from the
    #: upwind ocean (westerlies |lat| in [30,60) source to the west; trades/polar
    #: source to the east — the physically dominant moisture-transport direction,
    #: the flow that sets real rain shadows like the Gobi/Atacama/Patagonia). Off
    #: -> the pre-wind physical-only field (self-check + clean fallback).
    moist_enable: bool = True
    #: Overland-fetch decay length (canvas px): moisture falls to 1/e over this many
    #: px of overland travel from the upwind coast (continentality — hardens the
    #: deep interior, e.g. Kislev's steppe).
    moist_lambda: float = 550.0
    #: Orographic loss: metres of *upwind ascent* for a 1/e moisture drop (rain
    #: shadow — air climbing a range rains out on the windward side, leaving the lee
    #: barren, e.g. the Dark Lands east of the Worlds Edge, the Warpstone Desert).
    #: Descent does not restore moisture.
    moist_oro_m: float = 700.0
    #: Floor on the moisture factor so the driest continental interior is suppressed,
    #: not zeroed (steppe still farms a little).
    moist_floor: float = 0.18
    #: Gaussian sigma (canvas px) smoothing the advected moisture field. The zonal
    #: scan is per-row independent, so a sharp row-to-row elevation change trails a
    #: 1px horizontal streak downwind; this blends adjacent rows back together
    #: (0 disables). Small enough to keep the macro rain-shadow / continentality
    #: gradient, large enough to erase the streaks.
    moist_smooth_sigma: float = 10.0

    # --- normalization + tone ---
    #: Percentile of the passable field used as the 1.0 reference.
    norm_pctl: float = 99.5
    #: Tone-curve exponent applied after normalization (gamma<1 lifts the mid).
    gamma: float = 0.62
    #: Histogram bins recorded in the stats (provenance / diff visibility).
    hist_bins: int = 32

    def weights(self) -> dict:
        """The factor weights + normalization knobs, for the provenance sidecar."""
        return {
            "climate": {"temp_peak": self.temp_peak, "temp_sigma": self.temp_sigma,
                        "temp_amp": self.temp_amp, "trop_amp": self.trop_amp,
                        "trop_sigma": self.trop_sigma, "arid_lat": self.arid_lat,
                        "arid_sigma": self.arid_sigma, "arid_depth": self.arid_depth},
            "terrain": {"elev_lo_m": self.elev_lo_m, "elev_hi_m": self.elev_hi_m,
                        "elev_smooth_sigma": self.elev_smooth_sigma,
                        "slope_pctl": self.slope_pctl, "slope_floor": self.slope_floor},
            "hydrology": {"river_amp": self.river_amp, "river_lambda": self.river_lambda,
                          "river_width_ref": self.river_width_ref,
                          "river_width_floor": self.river_width_floor,
                          "coast_amp": self.coast_amp, "coast_lambda": self.coast_lambda},
            "moisture": {"moist_enable": self.moist_enable, "moist_lambda": self.moist_lambda,
                         "moist_oro_m": self.moist_oro_m, "moist_floor": self.moist_floor,
                         "moist_smooth_sigma": self.moist_smooth_sigma},
            "normalization": {"norm_pctl": self.norm_pctl, "gamma": self.gamma},
        }


def _smoothstep(t: np.ndarray) -> np.ndarray:
    """Hermite smoothstep on ``t`` clipped to [0,1]: 0 at 0, 1 at 1, flat ends."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------------------
# 1. Climate
# ---------------------------------------------------------------------------

def climate_curve(lat_deg: np.ndarray, p: ArableParams) -> np.ndarray:
    """Climate suitability in [0,1] for each latitude (degrees).

    Temperate bump + tropical shoulder, then a multiplicative subtropical-arid
    trough. Pure and closed-form (no iterative solver), so it never breaks
    byte-exact regeneration.
    """
    a = np.abs(np.asarray(lat_deg, dtype=np.float64))
    temperate = p.temp_amp * np.exp(-(((a - p.temp_peak) / p.temp_sigma) ** 2))
    tropical = p.trop_amp * np.exp(-((a / p.trop_sigma) ** 2))
    base = temperate + tropical
    arid = 1.0 - p.arid_depth * np.exp(-(((a - p.arid_lat) / p.arid_sigma) ** 2))
    return np.clip(base * arid, 0.0, 1.0)


# ---------------------------------------------------------------------------
# 2. Terrain
# ---------------------------------------------------------------------------

def _terrain_factor(elev_m: np.ndarray, passable: np.ndarray, p: ArableParams) -> np.ndarray:
    """Elevation x slope suitability in [0,1] on the canvas grid.

    ``elev_m`` is metres above sea level (0 in the sea), so the shoreline carries
    no artificial cliff; the field is Gaussian-smoothed before the slope gradient
    so the small residual step never paints a coastal suppression fringe.
    """
    elev_s = ndimage.gaussian_filter(elev_m.astype(np.float32), p.elev_smooth_sigma)

    # Elevation term: lowland -> 1, high ground -> 0 across [lo, hi] metres.
    t_elev = 1.0 - _smoothstep((elev_s - p.elev_lo_m) / max(p.elev_hi_m - p.elev_lo_m, 1e-6))

    # Slope term: |grad elev| in metres per canvas px, robustly scaled.
    gy, gx = np.gradient(elev_s)
    slope = np.hypot(gx, gy)
    if passable.any():
        scale = float(np.percentile(slope[passable], p.slope_pctl))
    else:
        scale = 0.0
    if scale > 0.0:
        t_slope = 1.0 - (1.0 - p.slope_floor) * _smoothstep(slope / scale)
    else:
        t_slope = np.ones_like(slope)

    return np.clip(t_elev * t_slope, 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# 3. Hydrology
# ---------------------------------------------------------------------------

def _hydrology_boost(sea: np.ndarray, river: np.ndarray, river_width: np.ndarray | None,
                     climate: np.ndarray, p: ArableParams) -> np.ndarray:
    """Bounded fertility multiplier ``H >= 1`` from river + coast proximity.

    River proximity is weighted by the local drawn stream width (so trunk rivers
    dominate). Coast proximity is gated by the climate factor so arid coasts are
    not lifted (panel must-fix). Distance transforms are Euclidean; the Old World
    sits far from the wrap seam, so seam wrap is irrelevant here (documented).
    """
    h = np.ones(sea.shape, dtype=np.float32)

    if river.any():
        # Nearest-river distance and the width of that nearest river pixel.
        d_river, inds = ndimage.distance_transform_edt(~river, return_indices=True)
        if river_width is not None:
            near_w = river_width[tuple(inds)]
            w = p.river_width_floor + (1.0 - p.river_width_floor) * np.clip(
                near_w / max(p.river_width_ref, 1e-6), 0.0, 1.0)
        else:
            w = 1.0
        h = h + p.river_amp * w * np.exp(-d_river / p.river_lambda)

    if sea.any() and not sea.all():
        d_coast = ndimage.distance_transform_edt(~sea)
        h = h + p.coast_amp * climate * np.exp(-d_coast / p.coast_lambda)

    return h.astype(np.float32)


# ---------------------------------------------------------------------------
# 3b. Moisture / rain shadow (prevailing-wind advection)
# ---------------------------------------------------------------------------

def _zonal_upwind_from_west(lat_per_row: np.ndarray) -> np.ndarray:
    """Per-row bool: True where the prevailing wind's moisture source is to the WEST.

    The three-cell belt premise of ``render_wind_patterns.wind_vector``, reduced to
    its zonal component (the moisture-bearing direction): the mid-latitude
    **westerlies** (``|lat|`` in [30, 60)) carry ocean air eastward, so their source
    lies to the west; the **trades** (``|lat| < 30``) and **polar easterlies**
    (``|lat| >= 60``) blow westward, so their source lies to the east.
    """
    a = np.abs(np.asarray(lat_per_row, dtype=np.float64))
    return (a >= 30.0) & (a < 60.0)


def _scan_moisture(sea: np.ndarray, elev_m: np.ndarray, from_west: np.ndarray,
                   p: ArableParams, wrap_x: bool) -> np.ndarray:
    """Zonal upwind moisture advection ``M`` in [0,1] on the canvas grid.

    Ocean is the moisture source (``M = 1``). Over land, moisture is advected one px
    at a time from the upwind neighbour, losing a fixed fraction per px of overland
    fetch (``moist_lambda`` — continentality) and an orographic fraction whenever the
    terrain *rises* into the wind (``moist_oro_m`` — rain shadow; descent does not
    restore it). Two single-direction sweeps (west->east for westerly rows,
    east->west for trade/polar rows) are selected per row. Pure, closed-form and
    deterministic — a fixed column loop of vectorised row ops, byte-exact on rerun.
    """
    h, w = sea.shape
    decay = float(np.exp(-1.0 / max(p.moist_lambda, 1e-6)))
    inv_oro = 1.0 / max(p.moist_oro_m, 1e-6)
    sea_f = sea.astype(np.float32)

    def sweep(step: int) -> np.ndarray:
        # step +1: west->east (upwind is the pixel to the west, x-1).
        # step -1: east->west (upwind is the pixel to the east, x+1).
        m = sea_f.copy()
        order = range(1, w) if step > 0 else range(w - 2, -1, -1)
        # Seam-wrap the first column of the sweep from the far edge, so a landmass
        # touching the seam still draws moisture from the ocean across it.
        if wrap_x:
            first = 0 if step > 0 else w - 1
            up = (w - 1) if step > 0 else 0
            rise = np.maximum(0.0, elev_m[:, first] - elev_m[:, up])
            cand = decay * m[:, up] * np.exp(-rise * inv_oro)
            m[:, first] = np.where(sea[:, first], 1.0, cand)
        for x in order:
            up = x - step
            rise = np.maximum(0.0, elev_m[:, x] - elev_m[:, up])
            cand = decay * m[:, up] * np.exp(-rise * inv_oro)
            m[:, x] = np.where(sea[:, x], 1.0, cand)
        return m

    m_we = sweep(+1)
    m_ew = sweep(-1)
    return np.where(from_west[:, None], m_we, m_ew).astype(np.float32)


def _moisture_factor(sea: np.ndarray, elev_m: np.ndarray, lat_per_row: np.ndarray,
                     p: ArableParams, wrap_x: bool) -> np.ndarray:
    """Rain-shadow / continentality suitability in ``[moist_floor, 1]`` on the grid.

    ``moist_enable=False`` returns an all-ones identity (the pre-wind physical-only
    field), for the self-check and a clean fallback.
    """
    if not p.moist_enable:
        return np.ones(sea.shape, dtype=np.float32)
    m = _scan_moisture(sea, elev_m, _zonal_upwind_from_west(lat_per_row), p, wrap_x)
    if p.moist_smooth_sigma > 0.0:
        # Blend the per-row scan's downwind streaks (deterministic, mode='wrap' on x
        # so the seam matches the wrap-aware sweep).
        m = ndimage.gaussian_filter(m, p.moist_smooth_sigma, mode=("nearest", "wrap"))
    return (p.moist_floor + (1.0 - p.moist_floor) * np.clip(m, 0.0, 1.0)).astype(np.float32)


# ---------------------------------------------------------------------------
# 4. Lore
# ---------------------------------------------------------------------------

def _lore_factor(zones, shape: tuple[int, int], wrap_x: bool) -> np.ndarray:
    """Multiplicative lore field ``L`` (1.0 where no zone reaches).

    Each zone multiplies ``1 + (factor-1) . w`` where ``w`` is a smoothstep bump
    (1 at the anchor, 0 at/after the radius). Overlapping zones compose. Distances
    are wrap-aware in x to stay correct near the seam and deterministic everywhere.
    """
    h, w = shape
    lore = np.ones((h, w), dtype=np.float32)
    if not zones:
        return lore
    ys = np.arange(h, dtype=np.float32)[:, None]
    xs = np.arange(w, dtype=np.float32)[None, :]
    for z in zones:
        ax, ay = float(z.anchor[0]), float(z.anchor[1])
        dx = xs - ax
        if wrap_x:
            dx = dx - w * np.round(dx / w)
        dy = ys - ay
        dist = np.sqrt(dx * dx + dy * dy)
        bump = 1.0 - _smoothstep(dist / float(z.radius))
        lore *= 1.0 + (float(z.factor) - 1.0) * bump
    return lore


# ---------------------------------------------------------------------------
# Compose
# ---------------------------------------------------------------------------

def build_field(*, lat_per_row: np.ndarray, elev_m: np.ndarray, sea: np.ndarray,
                passable: np.ndarray, river: np.ndarray,
                river_width: np.ndarray | None, lore_zones,
                params: ArableParams | None = None, wrap_x: bool = True
                ) -> tuple[np.ndarray, dict]:
    """Compose the arable field and return ``(field float32 in [0,1], stats)``.

    Args:
        lat_per_row: ``(H,)`` latitude in degrees for each canvas row.
        elev_m: ``(H, W)`` metres above sea level (0 in the sea).
        sea: ``(H, W)`` bool ocean mask (for the coast distance).
        passable: ``(H, W)`` bool where the field is defined — land minus lakes and
            any impassable layer. Everything off it is pinned to 0.
        river: ``(H, W)`` bool drawn river pixels.
        river_width: ``(H, W)`` float local drawn width (0 off-river) or ``None``.
        lore_zones: iterable of :class:`worldgen.schema.ArableLoreZone`.
        params: :class:`ArableParams` (defaults if ``None``).
        wrap_x: wrap distances on the x axis (lore only; hydrology is seam-far).

    The output is 0 on every non-passable pixel and a smooth proportional ramp on
    passable land. ``stats`` carries the normalization value, gamma, factor
    weights, the passable-field histogram and summary quantiles (provenance).
    """
    p = params or ArableParams()
    h, w = passable.shape
    if elev_m.shape != (h, w) or sea.shape != (h, w) or river.shape != (h, w):
        raise ValueError("build_field: elev_m, sea, river must all be (H, W) canvas-aligned")
    if lat_per_row.shape != (h,):
        raise ValueError(f"build_field: lat_per_row must be ({h},), got {lat_per_row.shape}")

    climate = climate_curve(lat_per_row, p).astype(np.float32)[:, None]  # (H,1) -> broadcast
    climate_f = np.broadcast_to(climate, (h, w))
    terrain = _terrain_factor(elev_m, passable, p)
    hydro = _hydrology_boost(sea, river, river_width, climate_f, p)
    moisture = _moisture_factor(sea, elev_m, lat_per_row, p, wrap_x)
    lore = _lore_factor(lore_zones, (h, w), wrap_x)

    field = (climate_f * terrain * hydro * moisture * lore).astype(np.float32)
    field = field * passable  # mask off water / lake / impassable

    # Normalize by the passable-field percentile so a blessed outlier can't crush
    # the ramp; degenerate (no passable land / flat-zero) -> an all-zero field.
    sample = field[passable]
    denom = float(np.percentile(sample, p.norm_pctl)) if sample.size else 0.0
    if denom > 0.0:
        field = np.clip(field / denom, 0.0, 1.0)
        field = np.power(field, p.gamma, dtype=np.float32)
    else:
        field = np.zeros_like(field)
    field = (field * passable).astype(np.float32)

    # Provenance: histogram + quantiles over passable land (post tone curve).
    pv = field[passable]
    if pv.size:
        counts, edges = np.histogram(pv, bins=p.hist_bins, range=(0.0, 1.0))
        quant = {q: float(np.percentile(pv, q)) for q in (1, 25, 50, 75, 95, 99, 99.5)}
        summary = {"min": float(pv.min()), "max": float(pv.max()), "mean": float(pv.mean())}
    else:
        counts = np.zeros(p.hist_bins, dtype=int)
        edges = np.linspace(0.0, 1.0, p.hist_bins + 1)
        quant, summary = {}, {"min": 0.0, "max": 0.0, "mean": 0.0}

    stats = {
        "weights": p.weights(),
        "norm_value": denom,
        "norm_pctl": p.norm_pctl,
        "gamma": p.gamma,
        "passable_px": int(passable.sum()),
        "histogram": {"bins": p.hist_bins,
                      "edges": [float(e) for e in edges.tolist()],
                      "counts": [int(c) for c in counts.tolist()]},
        "quantiles": quant,
        "summary": summary,
    }
    return field, stats
