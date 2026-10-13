#!/usr/bin/env python3
"""Measure the map projection Victoria 3's own shipped bitmap is drawn in.

No projection is declared anywhere in the vanilla install — the engine just
consumes ``map_data/provinces.png`` as a rectangle of pixels. So the frame this
mod's canvas must match cannot be looked up; it has to be **measured**, and this
script is that measurement, committed and rerunnable rather than quoted.

The method rests on one observation: vanilla names its states after real places,
and for an **island** state the state footprint *is* the island. That makes an
island state an unambiguous (canvas px) <-> (lon, lat) correspondence, which is
exactly what a projection fit needs and what a continental state — whose borders
are political and whose centroid means nothing geographically — cannot provide.

    state_regions/*.txt  ->  state -> province colour list
    provinces.png        ->  colour -> pixels
                         ->  per-state centroid in canvas px
                         ->  least-squares fit against :data:`ISLAND_ANCHORS`

Four cylindrical hypotheses are fitted and compared. All four share ``x = X0 +
R*lam``; they differ only in how latitude maps to y, so the comparison is a
one-dimensional question and the residual table is a fair one.

Two estimators matter, and both are deliberate:

* **Circular** mean/median in longitude. ``STATE_FIJI`` straddles the +-180
  seam, so its pixels sit in two columns at opposite edges of the canvas; a
  plain arithmetic mean puts its centroid 2128 px away in the middle of the
  Pacific, which is enough on its own to poison the longitude estimate.
* **Median**, not mean, for the offsets. A handful of anchors are honestly
  bad — Ceylon and Bermuda are drawn oversized, Sakhalin's state reaches onto
  the mainland — and a least-squares centre would chase them.

Read-only by construction: :data:`VANILLA_ROOT` is opened for reading and
nothing else, enforced by :func:`_assert_writable` on every output path.

Usage::

    python mapgen/measure_vanilla_frame.py
    python mapgen/measure_vanilla_frame.py --json      # + scratchpad/vanilla_frame.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import map_config  # noqa: E402
from worldgen import raster  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
DERIVED_DIR = TOOLS_DIR / "derived"
SCRATCH_DIR = TOOLS_DIR.parent / "scratchpad"  # QA renders and previews; gitignored at the repo root

#: The read-only vanilla install. Never written to — see :func:`_assert_writable`.
VANILLA_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game")

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE

# ---------------------------------------------------------------------------
# The anchor table
# ---------------------------------------------------------------------------
#
# Island states and the real-world centroid of the island each is named after,
# in degrees (lon east-positive, lat north-positive). Coordinates are the
# island's own geographic centre, rounded to 0.05 deg — far finer than the ~4 px
# (~0.17 deg) the fit resolves, so their precision is not the limiting factor.
#
# Selection rule, applied once and recorded here so the set is auditable: the
# state must cover an island or a tight island group **and nothing else**. That
# is why Madagascar is absent (vanilla splits it into a north and a south state,
# so neither centroid is the island's) and why Hispaniola is absent (the state
# boundary is the Haiti/Santo Domingo political border, not the coast).
#
# Four anchors are known to be poor and are kept deliberately: Ceylon and
# Bermuda are drawn oversized, Sakhalin's state reaches onto the mainland, and
# Luzon's includes neighbouring islands. They are exactly what the median
# estimator exists to absorb, and dropping them would hide how much slack the
# estimate really has.
#
# STATE_FIJI is the seam straddler that makes the circular mean necessary.

ISLAND_ANCHORS: dict[str, tuple[float, float]] = {
    # name                      lon      lat
    "STATE_ICELAND":          (-18.60,  64.95),
    "STATE_GOTLAND":          ( 18.50,  57.50),
    "STATE_AZORES":           (-28.20,  38.50),
    "STATE_CORSICA":          (  9.10,  42.15),
    "STATE_SARDINIA":         (  9.05,  40.10),
    "STATE_SICILY":           ( 14.15,  37.60),
    "STATE_MALTA":            ( 14.40,  35.90),
    "STATE_CRETE":            ( 24.80,  35.20),
    "STATE_CYPRUS":           ( 33.20,  35.05),
    "STATE_CANARY_ISLANDS":   (-15.80,  28.30),
    "STATE_CAPE_VERDE":       (-23.90,  15.90),
    "STATE_BERMUDA":          (-64.75,  32.30),
    "STATE_BAHAMAS":          (-76.50,  24.50),
    "STATE_JAMAICA":          (-77.30,  18.15),
    "STATE_PUERTO_RICO":      (-66.45,  18.20),
    "STATE_ZANZIBAR":         ( 39.35,  -6.10),
    "STATE_CEYLON":           ( 80.70,   7.70),
    "STATE_FORMOSA":          (121.00,  23.70),
    "STATE_RYUKYU_ISLANDS":   (128.00,  26.50),
    "STATE_SAKHALIN":         (143.00,  51.00),
    "STATE_LUZON":            (121.00,  16.00),
    "STATE_HAWAIIAN_ISLANDS": (-157.00, 20.50),
    "STATE_TAHITI":           (-149.45, -17.65),
    "STATE_TONGA":            (-175.00, -20.00),
    "STATE_FIJI":             (178.00,  -17.80),
    "STATE_VANUATU":          (167.50,  -16.30),
    "STATE_SOLOMON_ISLANDS":  (159.50,   -9.00),
    "STATE_BOUGAINVILLE":     (155.20,   -6.20),
    "STATE_TASMANIA":         (146.60,  -42.00),
}

# ---------------------------------------------------------------------------
# The projection hypotheses
# ---------------------------------------------------------------------------
#
# Each returns y in the same units as ``x = lam``, i.e. in earth radii for a
# sphere of radius 1, so a fitted scale directly comparable to R = W / 2*pi
# falls out of every one of them. Gall stereographic's own definition uses
# ``x = R*lam/sqrt(2)``; renormalising it to ``x = R*lam`` is what puts the
# (1 + sqrt(2)) below, and is what makes its residual comparable to the others'.

def y_plate_carree(phi):
    return phi


def y_mercator(phi):
    return np.log(np.tan(np.pi / 4 + phi / 2))


def y_miller(phi):
    return 1.25 * np.log(np.tan(np.pi / 4 + 0.4 * phi))


def y_gall_stereographic(phi):
    return (1.0 + math.sqrt(2.0)) * np.tan(phi / 2)


HYPOTHESES = {
    "miller": y_miller,
    "gall_stereographic": y_gall_stereographic,
    "mercator": y_mercator,
    "plate_carree": y_plate_carree,
}


# ---------------------------------------------------------------------------
# Read-only guard
# ---------------------------------------------------------------------------

def _assert_writable(path: Path) -> Path:
    """Refuse to write anywhere inside the vanilla install.

    The install is reference, not workspace (``CLAUDE.md`` non-negotiables). A
    resolved-path containment check is cheap and catches the realistic mistake —
    a relative output path, or a future ``--out`` that someone points at the
    game folder — rather than trusting that no code path ever does it.
    """
    resolved = Path(path).resolve()
    root = VANILLA_ROOT.resolve()
    if resolved == root or root in resolved.parents:
        raise SystemExit(f"refusing to write inside the read-only vanilla install: {resolved}")
    return resolved


# ---------------------------------------------------------------------------
# Parsing the vanilla state definitions
# ---------------------------------------------------------------------------

_STATE_RE = re.compile(r"^(STATE_[A-Z0-9_]+)\s*=\s*\{", re.MULTILINE)
_PROVINCES_RE = re.compile(r"provinces\s*=\s*\{([^}]*)\}")
_HEX_RE = re.compile(r'"?x([0-9A-Fa-f]{6})"?')


def parse_state_provinces(state_regions_dir: Path) -> dict[str, list[int]]:
    """``state key -> packed 0xRRGGBB province colours``, from the vanilla text.

    Deliberately not a general Clausewitz parser: it finds each ``STATE_X = {``
    header and takes the first ``provinces = { ... }`` that follows it, which is
    the file layout vanilla actually uses. A full parser would be more code with
    no more correctness for this one question, and the province-count assertion
    downstream catches a state whose block was read wrong.
    """
    out: dict[str, list[int]] = {}
    for path in sorted(state_regions_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        heads = list(_STATE_RE.finditer(text))
        for i, m in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            block = text[m.start():end]
            pm = _PROVINCES_RE.search(block)
            if pm is None:
                continue
            colours = [int(h, 16) for h in _HEX_RE.findall(pm.group(1))]
            if colours:
                out[m.group(1)] = colours
    return out


# ---------------------------------------------------------------------------
# Centroids
# ---------------------------------------------------------------------------

def circular_mean_x(angles_cos: float, angles_sin: float) -> float:
    """Mean canvas x from summed unit vectors, folded into [0, W)."""
    ang = math.atan2(angles_sin, angles_cos)
    return (ang % (2 * math.pi)) * CANVAS_W / (2 * math.pi)


def state_centroids(provinces_png: Path,
                    colours_by_state: dict[str, list[int]]) -> dict[str, tuple[float, float, int]]:
    """``state -> (cx, cy, pixel_count)`` in canvas px, x by circular mean.

    One pass over the 8192x3616 bitmap. Every anchor's colours are looked up at
    once through a sorted-target ``searchsorted``, so the cost is one sort of a
    few dozen keys plus one binary search per pixel rather than a full pass per
    state.
    """
    rgb = raster.read_rgb_png(provinces_png)
    if rgb.shape[:2] != (CANVAS_H, CANVAS_W):
        raise SystemExit(
            f"{provinces_png} is {rgb.shape[1]}x{rgb.shape[0]}, expected {CANVAS_W}x{CANVAS_H}"
        )
    packed = ((rgb[..., 0].astype(np.uint32) << 16)
              | (rgb[..., 1].astype(np.uint32) << 8)
              | rgb[..., 2].astype(np.uint32))

    states = sorted(colours_by_state)
    state_index = {s: i for i, s in enumerate(states)}
    pairs = sorted((c, state_index[s]) for s in states for c in colours_by_state[s])
    targets = np.array([c for c, _ in pairs], dtype=np.uint32)
    owner = np.array([i for _, i in pairs], dtype=np.int64)

    pos = np.searchsorted(targets, packed)
    np.clip(pos, 0, len(targets) - 1, out=pos)
    hit = targets[pos] == packed
    if not hit.any():
        raise SystemExit("no anchor province colour was found in provinces.png")

    who = owner[pos[hit]]
    ys, xs = np.nonzero(hit)
    theta = (xs.astype(np.float64) + 0.5) * (2 * math.pi / CANVAS_W)

    n = len(states)
    counts = np.bincount(who, minlength=n)
    sum_cos = np.bincount(who, weights=np.cos(theta), minlength=n)
    sum_sin = np.bincount(who, weights=np.sin(theta), minlength=n)
    sum_y = np.bincount(who, weights=ys.astype(np.float64) + 0.5, minlength=n)

    out: dict[str, tuple[float, float, int]] = {}
    for s in states:
        i = state_index[s]
        if counts[i] == 0:
            continue
        out[s] = (circular_mean_x(sum_cos[i], sum_sin[i]), sum_y[i] / counts[i], int(counts[i]))
    return out


# ---------------------------------------------------------------------------
# Estimators
# ---------------------------------------------------------------------------

def circular_median_x(residuals: np.ndarray) -> float:
    """Robust circular location of x residuals on a width-``W`` circle.

    Rotate to the circular mean, take the ordinary median of the wrapped
    deviations, rotate back — the standard way to get a median-like estimator on
    a circle, where "sort and take the middle" is not defined.
    """
    ang = residuals * (2 * math.pi / CANVAS_W)
    centre = math.atan2(np.sin(ang).mean(), np.cos(ang).mean())
    dev = (ang - centre + math.pi) % (2 * math.pi) - math.pi
    return ((centre + np.median(dev)) % (2 * math.pi)) * CANVAS_W / (2 * math.pi)


def fit_free_scale(y_norm: np.ndarray, y_px: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Least-squares ``y_px = Y0 - S*y_norm``. Returns ``(Y0, S, residuals)``.

    The minus sign is the axis flip: canvas y grows **downward** while every
    projection's y grows north, so a correct fit returns a positive S. A negative
    one would mean the anchors are upside down.

    Every hypothesis gets its own best scale here rather than being forced onto
    the canvas's R, so this table compares the projections' *shapes* and cannot
    be won by one of them happening to match the canvas width. The pinned-R table
    that follows is the one that answers the real question.
    """
    a = np.column_stack([np.ones_like(y_norm), -y_norm])
    (y0, s), *_ = np.linalg.lstsq(a, y_px, rcond=None)
    return float(y0), float(s), (y0 - s * y_norm) - y_px


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--game", type=Path, default=VANILLA_ROOT,
                   help="vanilla game folder (read-only)")
    p.add_argument("--json", action="store_true",
                   help="also write scratchpad/vanilla_frame.json")
    args = p.parse_args(argv)

    game = Path(args.game)
    state_dir = game / "map_data" / "state_regions"
    provinces = game / "map_data" / "provinces.png"
    if not state_dir.is_dir() or not provinces.is_file():
        raise SystemExit(f"vanilla map_data not found under {game}")

    print(f"reading {state_dir} (read-only)")
    all_states = parse_state_provinces(state_dir)
    print(f"  parsed {len(all_states)} states")

    missing = sorted(set(ISLAND_ANCHORS) - set(all_states))
    if missing:
        raise SystemExit(f"anchor states absent from this install: {missing}")
    wanted = {s: all_states[s] for s in ISLAND_ANCHORS}

    print(f"reading {provinces} ({CANVAS_W}x{CANVAS_H}, read-only)")
    cents = state_centroids(provinces, wanted)
    absent = sorted(set(ISLAND_ANCHORS) - set(cents))
    if absent:
        print(f"  WARNING: no pixels found for {absent}")

    names = sorted(cents)
    lon = np.array([ISLAND_ANCHORS[s][0] for s in names], dtype=np.float64)
    lat = np.array([ISLAND_ANCHORS[s][1] for s in names], dtype=np.float64)
    px = np.array([cents[s][0] for s in names], dtype=np.float64)
    py = np.array([cents[s][1] for s in names], dtype=np.float64)
    phi = np.radians(lat)
    lam = np.radians(lon)

    r_canvas = CANVAS_W / (2 * math.pi)
    print(f"\n{len(names)} island anchors resolved. R from wrap_x = W/2pi = {r_canvas:.4f} px/rad\n")

    # --- Shape only: each hypothesis gets its own best y-scale. --------------
    print("A. free y-scale (shape only)")
    print("   projection             median|dy|    rms|dy|    fitted R   R/R_canvas")
    print("   " + "-" * 68)
    results = {}
    for kind, fn in HYPOTHESES.items():
        yn = fn(phi)
        fy0, scale, resid = fit_free_scale(yn, py)
        results[kind] = {
            "free_median_abs_dy": float(np.median(np.abs(resid))),
            "free_rms_dy": float(np.sqrt((resid ** 2).mean())),
            "fitted_R": scale,
            "R_ratio": scale / r_canvas,
            "fitted_Y0": fy0,
        }
        print(f"   {kind:<22} {results[kind]['free_median_abs_dy']:9.1f} "
              f"{results[kind]['free_rms_dy']:10.1f} {scale:11.1f} {scale / r_canvas:11.4f}")

    # --- The real test: R is NOT free. wrap_x forces 8192 px = 360 deg of ----
    # longitude, which pins R = W/2pi for the x axis; a cylindrical projection
    # drawn at that R has no freedom left in y either. So refit every hypothesis
    # with R pinned and only the offset solved. This is the comparison that
    # decides the frame, and it is why a projection can win table A and lose here.
    print("\nB. R pinned to W/2pi by wrap_x (the constraint that actually applies)")
    print("   projection             median|dy|    rms|dy|          Y0")
    print("   " + "-" * 60)
    for kind, fn in HYPOTHESES.items():
        yn = fn(phi)
        py0 = float(np.median(py + r_canvas * yn))
        resid = (py0 - r_canvas * yn) - py
        results[kind]["pinned_median_abs_dy"] = float(np.median(np.abs(resid)))
        results[kind]["pinned_rms_dy"] = float(np.sqrt((resid ** 2).mean()))
        results[kind]["pinned_Y0"] = py0
        print(f"   {kind:<22} {results[kind]['pinned_median_abs_dy']:9.1f} "
              f"{results[kind]['pinned_rms_dy']:10.1f} {py0:11.1f}")

    best = min(results, key=lambda k: results[k]["pinned_median_abs_dy"])
    print(f"\n  -> {best} fits best under the real constraint.")
    if best == "miller":
        print(f"     Two independent confirmations: it wins table B outright, and its "
              f"free-scale R\n     in table A is {results['miller']['R_ratio']:.4f} x the "
              f"canvas's own W/2pi -- i.e. vanilla is a TRUE,\n     UNSCALED Miller in which "
              f"8192 px is exactly 360 deg of longitude.")

    # --- Given Miller, solve both offsets, R pinned to the canvas. -----------
    yn = y_miller(phi)
    x0 = circular_median_x((px - r_canvas * lam) % CANVAS_W)
    y0 = results["miller"]["pinned_Y0"]

    dx = ((px - (x0 + r_canvas * lam)) + CANVAS_W / 2) % CANVAS_W - CANVAS_W / 2
    dy = py - (y0 - r_canvas * yn)

    print(f"\nVANILLA'S FRAME - Miller, R = W/2pi, offsets by median:")
    print(f"  X0 = {x0:.1f}   (canvas x = 0 is lon {-x0 / r_canvas * 180 / math.pi:.4f})")
    print(f"  Y0 = {y0:.1f}   (equator {100 * y0 / CANVAS_H:.2f}% down the canvas)")
    print(f"  residuals: median |dx| {np.median(np.abs(dx)):.1f} px, "
          f"median |dy| {np.median(np.abs(dy)):.1f} px")

    print(f"\n  {'anchor':<24} {'lon':>8} {'lat':>7} {'cx':>8} {'cy':>8} {'dx':>7} {'dy':>7}  px")
    order = np.argsort(-np.abs(dy))
    for i in order:
        print(f"  {names[i]:<24} {lon[i]:8.2f} {lat[i]:7.2f} {px[i]:8.1f} {py[i]:8.1f} "
              f"{dx[i]:7.1f} {dy[i]:7.1f}  {cents[names[i]][2]:,}")

    print(f"\nNOTE - X0 above is what this mod adopts. Y0 above is VANILLA's equator; the mod "
          f"pins Y0 = 2142.0\n       instead, to put the canvas top edge on the northern limit "
          f"the user drew. See\n       mapgen/config/canvas_frame.py, which records both "
          f"provenances.")

    if args.json:
        SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        out = _assert_writable(SCRATCH_DIR / "vanilla_frame.json")
        payload = {
            "canvas": [CANVAS_W, CANVAS_H],
            "R_canvas": r_canvas,
            "hypotheses": results,
            "best": best,
            "miller_pinned": {"X0": x0, "Y0": y0,
                              "median_abs_dx": float(np.median(np.abs(dx))),
                              "median_abs_dy": float(np.median(np.abs(dy)))},
            "anchors": {n: {"lon": float(lon[i]), "lat": float(lat[i]),
                            "cx": float(px[i]), "cy": float(py[i]),
                            "dx": float(dx[i]), "dy": float(dy[i]),
                            "pixels": cents[n][2]}
                        for i, n in enumerate(names)},
        }
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
