"""Climate zones: a rule-based Koppen layer for the drawn world (board #8202).

Reads three things — the land/sea mask, the heightmap and Chris's drawing of warm (red) and cold (cyan)
ocean currents — and returns one of fourteen Koppen-style zones for every land cell. Rain is the sum of
the ingredients of a climate guide, each fed by a moisture tracer carried inland from the sea and cut
by mountains: ``Wt`` (carried east by the westerlies), ``Et`` (carried west by the trades), ``Mt``
(summer inflow of warm sea air, by least-cost path). Temperature comes from latitude, continentality,
marine air, current-carried warmth and lapse rate.

This module is the pure core: arrays in, array out, no file reads, no clock, no randomness. The driver
(``generate_climate_zones.py``) does the I/O. It was ported from the prototype ``model3.py`` and the
class grid it produces at the accepted settings is cell-for-cell the one Chris accepted on 2026-10-13.

Provenance of the settings (``mapgen/config/climate_settings.json`` over :data:`DEFAULT`): fitted against
real-Earth climate normals by coordinate search (Beck et al. Koppen map as truth, about a hundred city
normals, NOAA ETOPO1 elevations at 15 arc-minutes from NOAA CoastWatch ERDDAP, 2026-10-09), then
hand-adjusted. Earth agreement at the last fit (iteration 15): 62% exact zone, 78% broad group. The
calibration harness is not kept in the repo — its truth map, station table and ETOPO download cannot be
rebuilt from it — so the settings are frozen by acceptance, not re-fittable here.

Known limits (recorded, not fixed here):

* ``pole_ice=7.0`` was chosen by eye for where the ice line sits; Earth cannot calibrate it (its north is
  an ocean, only Antarctica is polar land) and the rule costs about half a point of Earth agreement.
* Grand Cathay comes out largely desert: the model treats the seas behind Nippon as enclosed. Left dry
  by decision; that land is out of scope.
* The far-east heightmap carries baked-in label text as relief.
* A current stroke only reaches about 240 km (``cur_sig``) from a coast; strokes in open ocean do nothing.
* Tilea and inland Estalia come out cold steppe, the Estalian coast Mediterranean; southern Araby grades
  to steppe and savanna.
* The prototype's soft rainfall patches ("lore nudges") are not ported; keep it that way unless Chris asks.

The layer depends on ``map_data/heightmap.png`` and ``mapgen/derived/land_sea_mask.png``: regenerating
either moves the picture. ``generate_climate_zones.py --check`` then reports stale; the response is to
re-render and have Chris accept the new picture, never to loosen the check.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.graph import MCP_Geometric

from config import canvas_frame as cf
from config import map_config

#: (code, name, Beck et al. colour). The index into this list is the class id written to the layer.
CLASSES = [
    ("Af", "Tropical rainforest", (0, 0, 255)), ("Am", "Tropical monsoon", (0, 120, 255)),
    ("Aw", "Savanna", (70, 170, 250)), ("BWh", "Hot desert", (255, 0, 0)),
    ("BWk", "Cold desert", (255, 150, 150)), ("BSh", "Hot semi-arid", (245, 165, 0)),
    ("BSk", "Cold semi-arid", (255, 220, 100)), ("Cs", "Mediterranean", (255, 255, 0)),
    ("Cfa", "Humid subtropical", (200, 255, 80)), ("Cfb", "Oceanic", (100, 255, 80)),
    ("Df", "Humid continental", (0, 255, 255)), ("Dc", "Subarctic", (0, 125, 125)),
    ("ET", "Tundra", (178, 178, 178)), ("EF", "Ice cap", (102, 102, 102)),
]
IDX = {c[0]: i for i, c in enumerate(CLASSES)}

#: The prototype's working scale: the canvas at 1/4 (2048x904). Another scale changes the picture.
SCALE = 4

# The defaults are the prototype's, verbatim: settings files omit keys and rely on these.
DEFAULT = dict(
    # temperature (fitted to city normals)
    t0=29.189, t2=34.0, t6=5.068, tcap=26.156, amp_sea=9, amp_cont=19.451, amp_pow=1.413, sum_frac=0.65, win_frac=0.9, sum_bonus=2.233, win_bonus=2.149, hi_bonus=0, cur_t=5.682, lapse=4.0, cont_len=2000, arctic_cool=7.061, cur_len=1693.055, cur_win=1, mar_bonus=6.85, mar_mid=0.428, sum_mar=0.234, amp_polar=0.141, ice_lat=66,
    dry_heat=5.0,
    # sea sources
    src_warm=0.3, src_cold=0.7, open_lo=0.3,
    # carried by the westerlies / distance from the east coast
    w_len=2500.0, w_oro=1500.0, e_len=2500.0, e_oro=2500.0, mix=6.0, trade_edge=30.0,
    # summer inflow of warm sea air (monsoon, humid east sides, rainforest)
    m_len=500.0, m_eq=8.0, m_rec_e0=0.2, cur_sig=12.0, pole_ice=14.0, m_open_lo=0.1, m_open_sig=35.0, m_sea=1500.0, m_rec_sig=10.0, m_bar=6.0, m_east=0.5, bar_sig=30.0, bar_lo=800.0, bar_span=700.0, crest_lo=2500.0, m_oro=2000.0, m_sst=19.0, cold_block=3.0, 
    # tropical summer rains
    trop_amp=340.0, trop_w=-6.0, trop_wsoft=6.0, trop_p=24.0, trop_psoft=8.0, trop_bar=9.0, trop_pow=1.0, m_half=0.25, trop_floor=0.6, itcz_cold=0.8,
    # humid subtropics
    sub_amp=150.0, sub_lo=20.0, sub_hi=40.0, sub_soft=5.0, sub_pow=1.0, sub_winter=0.35,
    # fronts of the westerlies
    front_amp=130.0, front_lat=52.0, front_shift=6.0, front_sig_w=18.0, front_sig_s=10.0, front_summer=0.6, front_east=0.9, east_winter=0.4,
    front_pow=0.7, front_floor=0.05, tfac_k=0.03,
    # summer convection over mid-latitude land
    conv_amp=120.0, conv_lat=50.0, conv_sig=15.0, conv_floor=0.2, conv_pow=0.5, conv_mar=0.25,
    # the summer high on west sides (Mediterranean dry summer)
    med_amp=0.9, med_lat=38.0, med_sig=8.0,
    base=2.0, oro_gain=0.5,
    # classification
    c_d=0.0, cs_ratio=2.2, cs_dry=40.0, seas_k=1.6, warm_months=4.0, eq_amp=110.0, eq_sig=9.0, eq_bar=1.0, eq_pow=3.0,
)

def read_currents(path):
    """Warm (red) and cold (cyan) current strokes from Chris's drawing, as 0..1 masks.

    Works on either export: strokes alone on a transparent background, or strokes over the flat green
    land / blue sea. Red shows as a raised red channel with little green; cyan as green and blue both
    high (a coast edge, green fading to blue, never has both)."""
    with Image.open(path) as im:
        a = np.asarray(im.convert("RGBA")).astype(np.float32)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3] / 255.0
    red = np.clip(r / 255.0, 0, 1) * (g < 128) * al
    cya = np.clip((g + b - 255.0) / 255.0, 0, 1) * (r < 100) * al
    red[red < 0.25] = 0
    cya[cya < 0.25] = 0
    return red, cya


def prepare_inputs(land_full, heightmap, red_full, cya_full, S=SCALE):
    """Reduce the full-resolution inputs to the model grid (canvas / ``S``).

    ``land_full`` is the 8192x3616 land mask (bool), ``heightmap`` the 16384x7232 heightmap (any numeric
    dtype), ``red_full`` / ``cya_full`` the stroke masks at canvas size. The reductions are the
    prototype's: BOX resize of the mask, an (2S x 2S) block mean of the heightmap, an SxS block mean of
    the strokes (scaled by S)."""
    Wc, Hc = cf.WIDTH, cf.HEIGHT
    W, H = Wc // S, Hc // S
    R = Wc / (2 * np.pi) / S
    Y0 = cf.Y0 / S
    m = Image.fromarray(np.where(land_full, 255, 0).astype(np.uint8), mode="L").resize((W, H), Image.BOX)
    land = np.asarray(m) > 127
    hm = np.asarray(heightmap).astype(np.float32)
    elev = hm.reshape(H, 2 * S, W, 2 * S).mean(axis=(1, 3))
    elev = np.clip((elev - map_config.HEIGHT_SEA_LEVEL) / map_config.HEIGHT_UNITS_PER_METRE, 0, None) * land
    box = lambda a: np.asarray(a, np.float32).reshape(H, S, W, S).mean(axis=(1, 3)) * S
    return dict(W=W, H=H, R=R, Y0=Y0, S=S, land=land, elev=elev, red=box(red_full), cya=box(cya_full))


def run(I, P=None, want_fields=False):
    """Class grid for prepared inputs ``I`` (see :func:`prepare_inputs`) at the scale ``I["S"]``."""
    p = dict(DEFAULT)
    if P:
        p.update(P)
    S = I["S"]
    W, H, R, Y0, land = I["W"], I["H"], I["R"], I["Y0"], I["land"]
    SC = 4.0 / S
    KM = 40075.017 / W
    G = lambda a, s: ndi.gaussian_filter(np.asarray(a, np.float32), s * SC, mode=("nearest", "wrap"))
    yy = np.arange(H, dtype=np.float32)[:, None] * np.ones((1, W), np.float32)
    lat = np.degrees((np.arctan(np.exp(((Y0 - (yy + 0.5)) / R) / 1.25)) - np.pi / 4) / 0.4)
    alat = np.abs(lat)
    hemi = np.where(lat >= 0, 1.0, -1.0)
    landf = land.astype(np.float32)
    ocean = 1 - landf
    elev = ndi.gaussian_filter(I["elev"], 3.0 * SC, mode=("nearest", "wrap"))
    elev_s = G(elev, 3)
    land_wide = G(landf, 45)
    mons = np.clip(-hemi * np.gradient(G(landf, 60), axis=0) * 110.0 / SC, 0, 1)
    mons = G(mons * np.clip((alat - 4) / 6, 0, 1) * np.clip((38 - alat) / 8, 0, 1), 10)
    dxk = KM * np.cos(np.radians(lat[:, 0]))            # km per px along a row
    dyk = KM * np.cos(np.radians(0.8 * lat[:, 0]))      # km per px along a column

    # ---- currents
    a = G(I["red"], p["cur_sig"]) - G(I["cya"], p["cur_sig"])      # how far a drawn line reaches sideways
    nz = np.abs(a)[np.abs(a) > 0.01]
    cur = np.clip(a / (np.percentile(nz, 80) if nz.size else 1.0), -1, 1)
    owt = np.maximum(G(ocean, 14), 0.05)
    cur_coast = G(cur * ocean, 14) / owt
    cold_inf = np.clip(3.0 * G(np.clip(-cur, 0, 1) * ocean, 25), 0, 1)
    open_sea = np.clip((G(ocean, 60) - 0.3) / 0.4, 0, 1)
    src = (1.0 + p["src_warm"] * np.clip(cur, 0, 1) - p["src_cold"] * np.clip(-cur, 0, 1)) * (p["open_lo"] + (1 - p["open_lo"]) * open_sea)
    src = G(src * ocean, 4) / np.maximum(G(ocean, 4), 0.05)

    def zonal(source, length, oro_h, eastward):
        """Carry a tracer along rows. Returns (tracer, windward climb fraction)."""
        e = elev_s if eastward else elev_s[:, ::-1]
        s_ = source if eastward else source[:, ::-1]
        o = ocean.astype(bool) if eastward else ocean.astype(bool)[:, ::-1]
        dec = np.exp(-dxk / length)
        v = np.zeros(H, np.float32)
        out = np.zeros((H, W), np.float32)
        lift = np.zeros((H, W), np.float32)
        for _ in range(2):                      # second pass closes the wrap
            for x in range(W):
                climb = np.clip(e[:, x] - e[:, x - 1], 0, None)
                f = 1 - np.exp(-climb / oro_h) if oro_h else 0.0
                lift[:, x] = v * f
                v = np.where(o[:, x], np.maximum(s_[:, x], v * dec), v * dec * (1 - f))
                out[:, x] = v
        if not eastward:
            out, lift = out[:, ::-1], lift[:, ::-1]
        return out, lift

    def inflow(east):
        """Summer inflow of warm, moist sea air. It spreads inland from any warm open
        sea by the easiest path. It reaches further over rainforest (recycled rain),
        toward a mountain barrier (monsoon) and on the east side of a continent, and
        it is stopped by ranges and by cold-current water."""
        sst = tsl + 3.0 + 5.0 * cur
        # a sea feeds the land if it is big enough; a sea behind an island chain still counts, a narrow gulf does not
        open_m = np.clip((G(ocean, p["m_open_sig"]) - 0.25) / 0.25, 0, 1)
        srcm = src * np.maximum(open_m, p["m_open_lo"]) * np.clip((sst - p["m_sst"]) / 6.0, 0, 1)
        dkm = KM * 0.5 * (np.cos(np.radians(lat)) + np.cos(np.radians(0.8 * lat)))
        # rain falling on tropical forest is recycled and carried on, most of all on the trade-wind (east) side
        recyc = p["m_eq"] * np.exp(-(lat / p["m_rec_sig"]) ** 2) * (p["m_rec_e0"] + (1 - p["m_rec_e0"]) * np.clip(east, 0, 1))
        L = p["m_len"] * (1 + recyc + p["m_bar"] * bar + p["m_east"] * east)
        gy, gx = np.gradient(G(elev, 8))            # only real ranges count as barriers, not hills
        cost = dkm / L + np.hypot(gx, gy) / (2.0 * p["m_oro"])
        cost = np.where(land, cost, dkm / p["m_sea"] + p["cold_block"] * np.clip(-cur, 0, 1) * dkm / 100.0).astype(np.float64) + 1e-6
        pad = W // 4
        cpad = np.concatenate([cost[:, -pad:], cost, cost[:, :pad]], 1)
        spad = np.concatenate([srcm[:, -pad:], srcm, srcm[:, :pad]], 1)
        opad = np.concatenate([~land[:, -pad:], ~land, ~land[:, :pad]], 1)
        out = np.zeros(cpad.shape, np.float32)
        for lev in (1.0, 0.75, 0.5, 0.25):
            st = np.argwhere(opad & (spad >= lev))
            if len(st) == 0:
                continue
            c, _ = MCP_Geometric(cpad).find_costs(st)
            out = np.maximum(out, lev * np.exp(-c).astype(np.float32))
        out = out[:, pad:pad + W]
        return np.where(land, out, srcm)

    def landmix(v):
        return np.where(land, G(v, p["mix"]), v)

    # ---- temperature
    # marine air: open, ice-free sea upwind. Frozen or enclosed seas moderate little.
    open_t = np.clip((G(ocean, 60) - 0.25) / 0.25, 0, 1)
    tsrc = (0.2 + 0.8 * open_t) * np.clip((p["ice_lat"] - alat + 14.0 * cur) / 6.0, 0.1, 1.0)
    icy = np.clip(2.0 * G(ocean * (1 - np.clip((p["ice_lat"] - alat + 14.0 * cur) / 6.0, 0, 1)), 12), 0, 1)
    mw, _ = zonal(tsrc, p["cont_len"], 0, True)
    me, _ = zonal(tsrc, p["cont_len"], 0, False)
    mar = np.where(alat > 30, mw, me)
    mar = np.where(land, G(mar * landf, 5) / np.maximum(G(landf, 5), 0.05), 1.0)
    cont = np.clip(1 - mar, 0, 1) * land
    cw, _ = zonal(cur * ocean, p["cur_len"], 2500.0, True)
    ce, _ = zonal(cur * ocean, p["cur_len"], 2500.0, False)
    cur_in = np.where(land, G(np.where(alat > 30, cw, ce), 5), cur)
    # land that runs on toward the pole with no sea beyond it carries an ice sheet (Earth's north has an
    # ocean there; Antarctica is the model). Look 8 and 14 degrees poleward and ask how much of it is land.
    lat_p = np.clip(lat + 8.0 * hemi, -89.0, 89.0)
    row_p = Y0 - R * 1.25 * np.log(np.tan(np.pi / 4 + 0.4 * np.radians(lat_p))) - 0.5
    xx_ = np.arange(W, dtype=np.float32)[None, :] * np.ones((H, 1), np.float32)
    lw_ = G(landf, 25)
    pol = ndi.map_coordinates(lw_, [row_p, xx_], order=1, mode="nearest")
    lat_q = np.clip(lat + 14.0 * hemi, -89.0, 89.0)
    row_q = Y0 - R * 1.25 * np.log(np.tan(np.pi / 4 + 0.4 * np.radians(lat_q))) - 0.5
    pol = np.minimum(pol, ndi.map_coordinates(lw_, [row_q, xx_], order=1, mode="nearest"))   # land all the way, not a peninsula
    polar_land = np.clip((pol - 0.75) / 0.2, 0, 1) * np.clip((alat - 58.0) / 12.0, 0, 1) * land
    sl = np.sin(np.radians(lat))
    tsl = np.minimum(p["tcap"], p["t0"] - p["t2"] * sl ** 2 - p["t6"] * sl ** 6)
    g = np.clip(np.sin(np.radians(alat)) / np.sin(np.radians(60)), 0, 1.1) ** p["amp_pow"]

    def temperature(season):
        half = ((p["amp_sea"] + p["amp_cont"] * cont) * g + 1.0) * (1.0 - p["amp_polar"] * np.clip((alat - 64) / 10, 0, 1))
        summer = season * hemi > 0
        hi = p["hi_bonus"] * np.clip((alat - 45) / 20, 0, 1) * np.clip((75 - alat) / 12, 0, 1)
        t = tsl + np.where(summer, p["sum_frac"] * half + p["sum_bonus"] * g * (p["sum_mar"] + (1 - p["sum_mar"]) * cont) + hi, -p["win_frac"] * half + p["win_bonus"] * g)
        t = t + p["cur_t"] * np.clip(g, 0.25, None) * cur_in * np.where(summer, 0.7, p["cur_win"])
        t = t + p["mar_bonus"] * g * (mar - p["mar_mid"]) * land
        t = t - np.where(summer, p["arctic_cool"] * icy, 0.0) - p["pole_ice"] * polar_land
        return t - p["lapse"] * elev / 1000.0

    T = {s: temperature(s) for s in (1, -1)}

    # ---- moisture tracers
    Wt, Wl = zonal(src, p["w_len"], p["w_oro"], True)
    Et, El = zonal(src, p["e_len"], p["e_oro"], False)
    Wt, Et = landmix(Wt), landmix(Et)
    Wl, El = G(Wl, 3), G(El, 3)
    # broad high ground (a plateau or a wide range), not single peaks: the game heightmap exaggerates small relief
    crest = ndi.maximum_filter(elev_s, size=max(3, int(round(24 * SC))), mode=("nearest", "wrap"))
    bar = np.maximum(np.clip((G(elev, p["bar_sig"]) - p["bar_lo"]) / p["bar_span"], 0, 1),
                     G(np.clip((crest - p["crest_lo"]) / 1500.0, 0, 1), 12)) * np.clip((50 - alat) / 10.0, 0, 1)
    Mraw = landmix(inflow(Et))
    Mt = Mraw ** 2 / (Mraw ** 2 + p["m_half"] ** 2) * (1 + p["m_half"] ** 2)   # moist or not: regimes are sharper than a smooth fade
    eqband = np.exp(-(lat / 8.0) ** 2)

    def precip(season):
        summer = (season * hemi > 0).astype(np.float32)
        winter = 1 - summer
        # tropical rains follow the sun, further poleward where a barrier holds the monsoon
        ls = lat * season                                         # degrees toward the summer pole
        S_ = np.clip((ls - p["trop_w"]) / p["trop_wsoft"], 0, 1) * np.clip((p["trop_p"] + p["trop_bar"] * bar - ls) / p["trop_psoft"], 0, 1)
        wet = np.maximum(Mt, p["trop_floor"] * eqband * (1 - p["itcz_cold"] * cold_inf))
        p_trop = p["trop_amp"] * S_ * wet ** p["trop_pow"] + p["eq_amp"] * np.exp(-(lat / (p["eq_sig"] * (1 + p["eq_bar"] * bar))) ** 2) * wet ** p["eq_pow"]   # the equator is wet all year
# the humid subtropics take over exactly where the tropical rains fade, so no dry seam is left between them
        fade = 1 - np.clip((p["trop_p"] + p["trop_bar"] * bar - alat) / p["trop_psoft"], 0, 1)
        band = fade * np.clip((p["sub_hi"] - alat) / p["sub_soft"], 0, 1)
        p_sub = p["sub_amp"] * band * Mt ** p["sub_pow"] * (summer + p["sub_winter"] * winter)
        # fronts: storm track near 42 in winter, 58 in summer, and narrower in summer
        fc = p["front_lat"] + p["front_shift"] * (summer - winter)
        fr = np.exp(-((alat - fc) / np.where(summer > 0, p["front_sig_s"], p["front_sig_w"])) ** 2)
        eastf = np.maximum(Et, Mt) * (1 - winter * p["east_winter"] * cont)
        hum = np.maximum(np.maximum(Wt, p["front_east"] * eastf), p["front_floor"])
        med = 1.0 - p["med_amp"] * summer * np.exp(-((alat - p["med_lat"]) / p["med_sig"]) ** 2) * (1 - np.clip(2.0 * np.maximum(Et, Mt), 0, 1))
        tfac = np.clip(np.exp(p["tfac_k"] * (T[season] - 10.0)), 0.3, 1.5)
        p_front = p["front_amp"] * (winter + p["front_summer"] * summer) * fr * hum ** p["front_pow"] * med * tfac
        cv = np.exp(-((alat - p["conv_lat"]) / p["conv_sig"]) ** 2) * summer
        p_conv = (p["conv_amp"] * cv * np.maximum(np.maximum(Wt, np.maximum(Et, Mt)), p["conv_floor"]) ** p["conv_pow"] * med
                  * (p["conv_mar"] + (1 - p["conv_mar"]) * cont) * np.clip((T[season] - 6.0) / 10.0, 0, 1))
        tot = p_trop + p_sub + p_front + p_conv + p["base"]
        lift = np.where(alat > p["trade_edge"], Wl, El)
        tot = tot * (1 + p["oro_gain"] * np.clip(lift * 4, 0, 2))
        return G(tot, 1.5)

    Pm = {s: precip(s) for s in (1, -1)}
    for s in (1, -1):
        dry = np.clip(1 - Pm[s] / 40.0, 0, 1) * np.clip((40 - alat) / 10, 0, 1) * land * np.exp(-elev / 2000.0)
        T[s] = T[s] + np.where(s * hemi > 0, p["dry_heat"], 0.4 * p["dry_heat"]) * dry
    snow = (np.maximum(T[1], T[-1]) < 5) & land & (alat > 55)
    for s in (1, -1):
        T[s] = T[s] - 5.0 * G(snow, 3)

    # ---- Koppen
    Tsum = np.where(hemi > 0, T[1], T[-1]); Twin = np.where(hemi > 0, T[-1], T[1])
    Psum = np.where(hemi > 0, Pm[1], Pm[-1]); Pwin = np.where(hemi > 0, Pm[-1], Pm[1])
    Tmax = np.maximum(T[1], T[-1]); Tmin = np.minimum(T[1], T[-1])
    Tann = (Tmax + Tmin) / 2; amp = np.maximum((Tmax - Tmin) / 2, 0.01)
    # the two values are the peak and the trough month; a wet season is shorter than half a year
    Pann = 6 * (Psum + Pwin) - p["seas_k"] * np.abs(Psum - Pwin)
    Pdry = np.minimum(Psum, Pwin)
    fs = Psum / np.maximum(Psum + Pwin, 1e-3)
    pth = np.maximum(2 * Tann + np.where(fs >= 0.7, 28, np.where(fs <= 0.3, 0, 14)), 1.0)
    months_warm = 12 / np.pi * np.arccos(np.clip((10 - Tann) / amp, -1, 1))
    k = np.full((H, W), IDX["Df"], np.uint8)
    E = Tmax < 10
    B = (Pann < 10 * pth) & ~E
    A = (Tmin >= 18) & ~B & ~E
    C = (Tmin >= p["c_d"]) & (Tmin < 18) & ~B & ~E
    D = ~(A | B | C | E)
    k[A] = IDX["Aw"]
    k[A & (Pdry >= 100 - Pann / 25)] = IDX["Am"]
    k[A & (Pdry >= 60)] = IDX["Af"]
    k[B] = np.where(Tann >= 18, IDX["BSh"], IDX["BSk"])[B]
    BW = B & (Pann < 5 * pth)
    k[BW] = np.where(Tann >= 18, IDX["BWh"], IDX["BWk"])[BW]
    k[C] = np.where(Tmax >= 22, IDX["Cfa"], IDX["Cfb"])[C]
    k[C & (Psum < p["cs_dry"]) & (Psum < Pwin / p["cs_ratio"])] = IDX["Cs"]
    k[C & (months_warm < p["warm_months"])] = IDX["Cfb"]
    k[D] = np.where(months_warm < p["warm_months"], IDX["Dc"], IDX["Df"])[D]
    k[E] = np.where(Tmax < 0, IDX["EF"], IDX["ET"])[E]
    best = np.zeros(k.shape, np.float32); out = k.copy()
    for i in range(len(CLASSES)):
        f = G((k == i), 2.0) * land
        m = f > best
        out[m] = i; best[m] = f[m]
    res = dict(k=out, land=land, lat=lat)
    if want_fields:
        res.update(Tsum=Tsum, Twin=Twin, Psum=Psum, Pwin=Pwin, cont=cont, cur=cur, elev=elev, Wt=Wt, Et=Et, Mt=Mt, bar=bar)
    return res
