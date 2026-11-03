"""Per-zone projection of the traced Immortal Empires borders onto the canvas (#9016).

No single warp registers the IE parchment to the canvas (the two maps draw several
regions mirrored), so Chris split it into four zones (2026-10-20): 1 Naggaroth +
Lustria, 2 Nehekhara + the Southlands, 3 Norsca, 4 the Dark Lands and everything
east. Each zone gets its own thin-plate warp through its own landmark pairs.

**Pairs.** ``mapgen/config/ie_projection_pairs.csv``, one row per landmark pair of
Chris's review app (its ``reviewed.json`` is the one verdict record), columns
:data:`PAIR_COLUMNS`. ``--sync-review`` (:func:`sync_rows`) overwrites status,
coordinates and text from the app and never writes it; ``zone`` and ``held_out``
are project-owned: a new id takes the app's ``zone``, else the ``--zones-from``
CSV's, else blank, and an existing row's zone never changes in a sync. A row
turning rejected loses its zone and ``held_out``. ``confidence`` is the proposer's
uncalibrated score: carried for review, never used in a fit.

**Fit sets.** A zone's *drawn fit* is every accepted row whose ``zone`` names it
(plus pending rows with ``include_pending``); ``held_out`` never removes a row from
it, so the map does not depend on which pairs are held out. The *evaluation fit*
is the drawn fit minus held-out rows, used only to measure error on them.

**Held-out rule** (:func:`plan_held_out`, residual-blind, append-only): per zone,
n = clamp(round(0.1 N), 2, 4) of its N accepted pairs, or none when fewer than 8
would remain; eligible pairs are single-zone, not a vertex of a mirrored control
triangle, strictly inside the hull of the pairs that would remain, and more than
100 source px from every other accepted pair of the zone; picked farthest-point
from the zone centroid, ties by id.

**Method** (:func:`choose_method`): thin-plate on the drawn fit for each smoothing
in :data:`SMOOTHING_LAMBDAS` (0 = exact). Folds (Jacobian determinant <= 0) are
counted on the zone's line px and on a 4 px grid over its land; a candidate with
none on both is eligible, and the eligible one with the lowest leave-one-out
median wins (ties to the smaller smoothing). With none eligible the exact warp is
kept, flagged ``no_fold_free_method``, and ``fold_attribution`` names the pairs
whose removal clears most folds. The piecewise-affine (triangle) warp is reported
beside it (:func:`triangle_report`), never chosen.

**Seams.** Every line point is warped by its one owner zone (the snapped zone
raster; points within ``reach_px`` of mapped zones take the first of the priority
order). An 8-neighbour line edge between two owners is a seam bridge; the layer
draws it only up to ``seam_flag_px``, so the diagnostic layer carries no long fake
border, and longer ones are listed and drawn only on the review render.

Public API for #9018: :func:`load_projection`, :class:`Projection`,
:class:`ZoneWarp`, :func:`ie_land_mask`. Everything else is private to
``mapgen/project_ie_borders.py``. Frames: IE frame = master px 3703x2880, canvas =
8192x3616 px; point arrays are float64 (N, 2) x, y. Deterministic: no RNG, no clock.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage as nd
from scipy.interpolate import RBFInterpolator
from scipy.spatial import Delaunay, cKDTree

from worldgen import parchment, reproject, segment, sources

TOOLS_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = TOOLS_DIR / "config" / "ie_projection.json"
PAIRS_PATH = TOOLS_DIR / "config" / "ie_projection_pairs.csv"

PAIR_COLUMNS = ("id", "zone", "review_status", "held_out", "source_x", "source_y", "canvas_x",
                "canvas_y", "feature_type", "confidence", "proposer", "region", "description", "note")
STATUSES = ("accepted", "pending", "rejected")
MAPPED_ZONES = (1, 2, 3, 4)
SMOOTHING_LAMBDAS = (0.0, 1e2, 1e3, 1e4, 1e5, 1e6)
_CHUNK = 200_000


class PairsError(ValueError):
    """A pairs file or review database that fails validation (the CLI exits 2)."""


# --------------------------------------------------------------------------- pairs

@dataclass
class PairRow:
    id: str
    zone: str
    review_status: str
    held_out: str
    source_x: float
    source_y: float
    canvas_x: float
    canvas_y: float
    feature_type: str = ""
    confidence: float = 0.0
    proposer: str = ""
    region: str = ""
    description: str = ""
    note: str = ""

    @property
    def zones(self) -> tuple[int, ...]:
        return parse_zone_cell(self.zone)

    @property
    def src(self) -> tuple[float, float]:
        return self.source_x, self.source_y

    @property
    def dst(self) -> tuple[float, float]:
        return self.canvas_x, self.canvas_y


def parse_zone_cell(cell: str) -> tuple[int, ...]:
    out = []
    for t in cell.replace(",", ";").split(";"):
        t = t.strip()
        if t:
            if not t.isdigit():
                raise PairsError(f"zone cell {cell!r}: {t!r} is not a zone id")
            out.append(int(t))
    return tuple(sorted(set(out)))


def _num(v: float) -> str:
    v = float(v)
    return str(int(v)) if v == int(v) else f"{round(v, 3):.3f}".rstrip("0").rstrip(".")


def parse_pairs_text(text: str) -> list[PairRow]:
    text = text.replace("\r\n", "\n").lstrip("﻿")
    rd = csv.DictReader(io.StringIO(text))
    if tuple(rd.fieldnames or ()) != PAIR_COLUMNS:
        raise PairsError(f"pairs header {rd.fieldnames} != {list(PAIR_COLUMNS)}")
    rows = []
    for n, r in enumerate(rd, start=2):
        try:
            rows.append(PairRow(
                id=r["id"].strip(), zone=r["zone"].strip(), review_status=r["review_status"].strip(),
                held_out=r["held_out"].strip(), source_x=float(r["source_x"]), source_y=float(r["source_y"]),
                canvas_x=float(r["canvas_x"]), canvas_y=float(r["canvas_y"]),
                feature_type=r["feature_type"], confidence=float(r["confidence"] or 0), proposer=r["proposer"],
                region=r["region"], description=r["description"], note=r["note"]))
        except (TypeError, ValueError) as e:
            raise PairsError(f"pairs line {n} ({r.get('id')}): {e}") from None
    return rows


def format_pairs(rows: list[PairRow]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(PAIR_COLUMNS)
    for r in sorted(rows, key=lambda r: r.id):
        w.writerow([r.id, r.zone, r.review_status, r.held_out, _num(r.source_x), _num(r.source_y),
                    _num(r.canvas_x), _num(r.canvas_y), r.feature_type, _num(r.confidence), r.proposer,
                    r.region, r.description, r.note])
    return buf.getvalue()


def validate_rows(rows: list[PairRow], zone_ids=MAPPED_ZONES, source_size=(3703, 2880),
                  canvas_size=(8192, 3616), include_pending: bool = False) -> None:
    """Raise :class:`PairsError` naming the id and column of the first problem."""
    seen = set()
    for r in rows:
        if not r.id:
            raise PairsError("a row has an empty id")
        if r.id in seen:
            raise PairsError(f"{r.id}: duplicate id")
        seen.add(r.id)
        if r.review_status not in STATUSES:
            raise PairsError(f"{r.id}: review_status {r.review_status!r} not in {STATUSES}")
        zs = r.zones
        bad = [z for z in zs if z not in zone_ids]
        if bad:
            raise PairsError(f"{r.id}: zone {bad} not a mapped zone {tuple(zone_ids)}")
        if r.held_out not in ("", "1"):
            raise PairsError(f"{r.id}: held_out must be 1 or blank, got {r.held_out!r}")
        if r.review_status == "rejected" and (zs or r.held_out):
            raise PairsError(f"{r.id}: a rejected row has no zone and no held_out")
        if r.held_out and (r.review_status != "accepted" or len(zs) != 1):
            raise PairsError(f"{r.id}: held_out needs an accepted single-zone row")
        if not (0 <= r.source_x < source_size[0] and 0 <= r.source_y < source_size[1]):
            raise PairsError(f"{r.id}: source px {r.src} outside {source_size}")
        if not (0 <= r.canvas_x < canvas_size[0] and 0 <= r.canvas_y < canvas_size[1]):
            raise PairsError(f"{r.id}: canvas px {r.dst} outside {canvas_size}")
        if not 0 <= r.confidence <= 1:
            raise PairsError(f"{r.id}: confidence {r.confidence} outside [0, 1]")
    fit_status = ("accepted", "pending") if include_pending else ("accepted",)
    for z in zone_ids:
        fit = [r for r in rows if z in r.zones and r.review_status in fit_status]
        for attr in ("src", "dst"):
            pts = {}
            for r in fit:
                k = getattr(r, attr)
                if k in pts:
                    raise PairsError(f"{r.id}: same {attr} px as {pts[k]} in zone {z}'s fit")
                pts[k] = r.id


def read_pairs(path: Path = PAIRS_PATH) -> list[PairRow]:
    return parse_pairs_text(Path(path).read_text(encoding="utf-8"))


def write_pairs(rows: list[PairRow], path: Path = PAIRS_PATH) -> None:
    Path(path).write_text(format_pairs(rows), encoding="utf-8", newline="\n")


def sync_rows(rows: list[PairRow], db: dict, expected_sha: dict[str, str],
              zones_from: dict[str, str] | None = None) -> tuple[list[PairRow], list[str]]:
    """Land Chris's review database into the pair rows. Returns ``(rows, log)``.

    ``expected_sha`` = ``{"source": <IE master sha>, "target": <canvas sha>}`` from the
    manifest; a database whose image hashes differ is refused. The database never
    gets written."""
    imgs = db.get("images", {})
    for k in ("source", "target"):
        got = (imgs.get(k) or {}).get("sha256")
        if got != expected_sha[k]:
            raise PairsError(f"review database {k} image sha {str(got)[:12]}… != manifest {expected_sha[k][:12]}…")
    zones_from = zones_from or {}
    by_id = {r.id: r for r in rows}
    log, out, seen = [], [], set()
    for a in sorted(db.get("anchors", []), key=lambda a: a["id"]):
        i = a["id"]
        if i in seen:
            raise PairsError(f"{i}: duplicate id in the review database")
        seen.add(i)
        status = a.get("review_status", "")
        prov = f"{a.get('provenance', '')}:{a.get('proposal_method', '')}"
        new = PairRow(id=i, zone="", review_status=status, held_out="",
                      source_x=float(a["source_x"]), source_y=float(a["source_y"]),
                      canvas_x=float(a["target_x"]), canvas_y=float(a["target_y"]),
                      feature_type=a.get("feature_type", "") or "", confidence=float(a.get("confidence") or 0),
                      proposer=prov, region=a.get("region", "") or "",
                      description=a.get("label_or_description", "") or "", note=_one_line(a.get("notes", "")))
        old = by_id.get(i)
        if old is None:
            zone = str(a.get("zone") or "").strip() or zones_from.get(i, "").strip()
            zone = ";".join(str(z) for z in parse_zone_cell(zone) if z in MAPPED_ZONES) if zone else ""
            new.zone = zone
            log.append(f"new {i}: {status}, zone {zone or '-'}")
        else:
            new.zone, new.held_out = old.zone, old.held_out
            if old.review_status != status:
                log.append(f"status {i}: {old.review_status} -> {status}")
            if old.src != new.src or old.dst != new.dst:
                log.append(f"moved {i}: {old.src}->{new.src}, {old.dst}->{new.dst}")
        if status == "rejected" and (new.zone or new.held_out):
            log.append(f"rejected {i}: zone {new.zone or '-'} and held_out {new.held_out or '-'} cleared")
            new.zone, new.held_out = "", ""
        if new.held_out and status != "accepted":
            log.append(f"{status} {i}: held_out cleared")
            new.held_out = ""
        out.append(new)
    for r in rows:
        if r.id not in seen:
            log.append(f"kept {r.id}: in the pairs file, not in the review database")
            out.append(r)
    return sorted(out, key=lambda r: r.id), log


def _one_line(s) -> str:
    return " ".join(str(s or "").split())


def fit_rows(rows: list[PairRow], zone: int, include_pending: bool = False) -> list[PairRow]:
    ok = ("accepted", "pending") if include_pending else ("accepted",)
    return [r for r in rows if zone in r.zones and r.review_status in ok]


def _xy(rows, attr) -> np.ndarray:
    return np.array([getattr(r, attr) for r in rows], dtype=np.float64).reshape(-1, 2)


# --------------------------------------------------------------------------- warps

def _rbf(src, dst, lam: float) -> RBFInterpolator:
    return RBFInterpolator(src, dst, kernel="thin_plate_spline", degree=1, smoothing=lam)


def _eval(f, xy: np.ndarray) -> np.ndarray:
    xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
    if not len(xy):
        return np.zeros((0, 2))
    return np.concatenate([f(xy[k:k + _CHUNK]) for k in range(0, len(xy), _CHUNK)])


def _jac(f, xy: np.ndarray) -> np.ndarray:
    xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
    p = _eval(f, xy)
    jx = (_eval(f, xy + [0.5, 0.0]) - p) * 2
    jy = (_eval(f, xy + [0.0, 0.5]) - p) * 2
    return np.stack([jx, jy], axis=2)


@dataclass(frozen=True)
class ZoneWarp:
    """One zone's chosen thin-plate warp, IE px -> canvas px (``lam`` 0 = exact)."""

    zone: int
    lam: float
    ids: tuple[str, ...]
    src: np.ndarray = field(repr=False)
    dst: np.ndarray = field(repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_f", _rbf(self.src, self.dst, self.lam))
        object.__setattr__(self, "_hull", Delaunay(self.src))

    def forward(self, xy) -> np.ndarray:
        return _eval(self._f, xy)

    def jacobian(self, xy) -> np.ndarray:
        return _jac(self._f, xy)

    def inside_hull(self, xy) -> np.ndarray:
        xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
        return self._hull.find_simplex(xy) >= 0


def fittable(src: np.ndarray) -> bool:
    """At least 4 pairs, not all on one line."""
    if len(src) < 4:
        return False
    return np.linalg.matrix_rank(src - src.mean(0), tol=1e-6) == 2


def _folds(f, xy) -> int:
    if not len(xy):
        return 0
    return int((np.linalg.det(_jac(f, xy)) <= 0).sum())


def leave_one_out(src, dst, lam: float, idx=None) -> np.ndarray:
    n = len(src)
    idx = range(n) if idx is None else idx
    out = []
    for i in idx:
        keep = np.arange(n) != i
        out.append(float(np.hypot(*(_rbf(src[keep], dst[keep], lam)(src[i:i + 1])[0] - dst[i]))))
    return np.array(out)


def _stats(v) -> dict:
    v = np.asarray(v, dtype=np.float64)
    if not len(v):
        return {"n": 0}
    return {"n": int(len(v)), "median": r1(np.median(v)), "p95": r1(np.percentile(v, 95)), "max": r1(v.max())}


def r1(v) -> float:
    return round(float(v), 1)


def choose_method(src, dst, ids, line_xy, grid_xy, held_mask=None, lambdas=SMOOTHING_LAMBDAS) -> dict:
    """Compare thin-plate at each smoothing on the drawn fit and pick one (module doc)."""
    held_mask = np.zeros(len(src), bool) if held_mask is None else np.asarray(held_mask, bool)
    cands = []
    for lam in lambdas:
        f = _rbf(src, dst, lam)
        loo = leave_one_out(src, dst, lam)
        c = {"lam": float(lam), "loo": _stats(loo), "folds_lines": _folds(f, line_xy),
             "folds_land_grid": _folds(f, grid_xy),
             "in_sample_max": r1(np.hypot(*(f(src) - dst).T).max())}
        if len(line_xy):
            sv = np.linalg.svd(_jac(f, line_xy), compute_uv=False)
            c["scale_min"], c["scale_max"] = round(float(sv[:, 1].min()), 2), round(float(sv[:, 0].max()), 2)
        if held_mask.any():
            ev = _rbf(src[~held_mask], dst[~held_mask], lam)
            e = np.hypot(*(ev(src[held_mask]) - dst[held_mask]).T)
            c["held_out"] = {"by_id": {i: r1(v) for i, v in zip(np.asarray(ids)[held_mask], e)},
                             "median": r1(np.median(e))}
        c["_loo_median"] = float(np.median(loo))
        cands.append(c)
    elig = [c for c in cands if c["folds_lines"] == 0 and c["folds_land_grid"] == 0]
    out = {"candidates": cands, "flags": []}
    if elig:
        best = min(elig, key=lambda c: (c["_loo_median"], c["lam"]))
    else:
        best = cands[0]
        out["flags"].append("no_fold_free_method")
        out["fold_attribution"] = fold_attribution(src, dst, ids, line_xy, grid_xy)
    for c in cands:
        c.pop("_loo_median")
    out["lam"] = best["lam"]
    out["chosen"] = best
    return out


def fold_attribution(src, dst, ids, line_xy, grid_xy, top: int = 3) -> list[dict]:
    """Per drawn-fit pair: exact-warp folds with that pair removed; the top ``top``."""
    base = _folds(_rbf(src, dst, 0.0), line_xy) + _folds(_rbf(src, dst, 0.0), grid_xy)
    rows = []
    for i in range(len(src)):
        keep = np.arange(len(src)) != i
        if not fittable(src[keep]):
            continue
        f = _rbf(src[keep], dst[keep], 0.0)
        fl, fg = _folds(f, line_xy), _folds(f, grid_xy)
        rows.append({"id": str(ids[i]), "folds_lines_without": fl, "folds_land_grid_without": fg,
                     "cleared": base - fl - fg})
    rows.sort(key=lambda r: (-r["cleared"], r["id"]))
    return rows[:top]


def _orient(p) -> np.ndarray:
    a, b, c = p[:, 0], p[:, 1], p[:, 2]
    return np.sign((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))


def flipped_triangles(src, dst) -> list[tuple[int, int, int]]:
    """Delaunay triangles of ``src`` whose orientation flips on ``dst`` (mirrored)."""
    if len(src) < 3:
        return []
    tri = Delaunay(src)
    s = tri.simplices
    flip = _orient(src[s]) != _orient(dst[s])
    return [tuple(sorted(int(v) for v in t)) for t in s[flip]]


def triangle_report(src, dst, ids, line_xy) -> dict:
    """The piecewise-affine warp of ``reproject.py``, reported beside thin-plate, never chosen."""
    ids = np.asarray(ids)
    tri = Delaunay(src)
    s = tri.simplices
    flip = _orient(src[s]) != _orient(dst[s])
    simp = tri.find_simplex(line_xy) if len(line_xy) else np.zeros(0, int)
    inside = simp >= 0
    # per-triangle affine Jacobian
    J = np.zeros((len(s), 2, 2))
    for k, t in enumerate(s):
        A = np.c_[src[t], np.ones(3)]
        J[k] = np.linalg.lstsq(A, dst[t], rcond=None)[0][:2].T
    loo_tri, loo_tps, interior = [], [], []
    for i in range(len(src)):
        keep = np.arange(len(src)) != i
        if keep.sum() < 3 or Delaunay(src[keep]).find_simplex(src[i:i + 1])[0] < 0:
            continue
        f = reproject.InversePiecewiseAffineFit(Delaunay(src[keep]), dst[keep])
        cx, cy = f.to_canvas_px(src[i:i + 1, 0], src[i:i + 1, 1])
        loo_tri.append(float(np.hypot(cx[0] - dst[i, 0], cy[0] - dst[i, 1])))
        loo_tps.append(float(np.hypot(*(_rbf(src[keep], dst[keep], 0.0)(src[i:i + 1])[0] - dst[i]))))
        interior.append(str(ids[i]))
    rep = {"flipped_triangles": [sorted(str(ids[v]) for v in t) for t in s[flip]],
           "folds_lines": int(flip[simp[inside]].sum()) if len(simp) else 0,
           "outside_hull_pct": r1(100 * (~inside).mean()) if len(simp) else 0.0,
           "loo_interior": {"ids": interior, "triangle": _stats(loo_tri), "thin_plate_exact": _stats(loo_tps)},
           "kinks": _kinks(line_xy, simp, J)}
    return rep


def _kinks(line_xy, simp, J) -> dict:
    if len(line_xy) < 2:
        return {"crossings": 0}
    key = {(int(x), int(y)): k for k, (x, y) in enumerate(np.round(line_xy).astype(int))}
    vals = []
    for (x, y), k in key.items():
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            j = key.get((x + dx, y + dy))
            if j is None or simp[k] < 0 or simp[j] < 0 or simp[k] == simp[j]:
                continue
            a, b = J[simp[k]], J[simp[j]]
            vals.append(np.linalg.norm(a - b) / max(0.5 * (np.linalg.norm(a) + np.linalg.norm(b)), 1e-9))
    if not vals:
        return {"crossings": 0}
    v = np.array(vals)
    return {"crossings": int(len(v)), "p95": round(float(np.percentile(v, 95)), 2), "max": round(float(v.max()), 2)}


# --------------------------------------------------------------------------- held-out

def plan_held_out(rows: list[PairRow], zone: int, cfg: dict) -> dict:
    """Which pairs of ``zone`` to hold out next (module doc). Never reads a residual."""
    acc = [r for r in rows if zone in r.zones and r.review_status == "accepted"]
    N = len(acc)
    n = int(np.clip(np.floor(cfg["fraction"] * N + 0.5), cfg["min"], cfg["max"]))
    if N - n < cfg["min_eval_pairs"]:
        n = 0
    held = [r.id for r in acc if r.held_out]
    plan = {"accepted": N, "want": n, "have": len(held), "add": [], "flags": []}
    if n == 0:
        plan["flags"].append("too_few_pairs")
        return plan
    if len(held) >= n:
        return plan
    src, dst = _xy(acc, "src"), _xy(acc, "dst")
    ids = [r.id for r in acc]
    flip_v = {v for t in flipped_triangles(src, dst) for v in t}
    tree = cKDTree(src)
    near = {i for i in range(N) if len(tree.query_ball_point(src[i], cfg["correlated_px"])) > 1}
    chosen = [ids.index(h) for h in held]
    cent = src.mean(0)
    while len(chosen) < n:
        elig = []
        for i, r in enumerate(acc):
            if i in chosen or len(r.zones) != 1 or i in flip_v or i in near:
                continue
            rest = np.array([k for k in range(N) if k not in chosen and k != i])
            if len(rest) < 3 or not fittable(src[rest]):
                continue
            hull = Delaunay(src[rest])
            if hull.find_simplex(src[i:i + 1])[0] < 0 or _on_hull_edge(hull, src[i]):
                continue
            elig.append(i)
        if not elig:
            plan["flags"].append("fewer_eligible_than_wanted")
            break
        if chosen:
            d = [float(np.min(np.hypot(*(src[chosen] - src[i]).T))) for i in elig]
        else:
            d = [float(np.hypot(*(src[i] - cent))) for i in elig]
        best = sorted(range(len(elig)), key=lambda k: (-d[k], ids[elig[k]]))[0]
        chosen.append(elig[best])
        plan["add"].append(ids[elig[best]])
    return plan


def _on_hull_edge(hull: Delaunay, p, eps: float = 1e-6) -> bool:
    """``find_simplex`` accepts boundary points; "strictly inside" excludes them."""
    from scipy.spatial import ConvexHull
    h = ConvexHull(hull.points)
    return bool((np.abs(h.equations[:, :2] @ p + h.equations[:, 2]) < eps).any())


# --------------------------------------------------------------------------- zones

def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _land_from_climate(rgb: np.ndarray, lc: dict, size) -> np.ndarray:
    from PIL import Image
    m = parchment.painted_mask(rgb, exclude=[tuple(lc["exclude_box"])])
    m = segment.drop_small_components(m, lc["min_component_px"], wrap_x=False)
    m = ~segment.drop_small_components(~m, lc["min_component_px"], wrap_x=False)
    big = Image.fromarray((m * 255).astype(np.uint8)).resize(tuple(size), Image.BILINEAR)
    return np.asarray(big) > lc["threshold"]


def ie_land_mask(config_path: Path = CONFIG_PATH) -> np.ndarray:
    """bool (2880, 3703): IE land, from the manifest-verified climate sibling."""
    cfg = load_config(config_path)
    lc = cfg["frames"]["land"]
    return _land_from_climate(sources.load_source_image(lc["source"]), lc, cfg["frames"]["master"]["size"])


def _poly_mask(polys, shape) -> np.ndarray:
    from PIL import Image, ImageDraw
    im = Image.new("L", (shape[1], shape[0]))
    d = ImageDraw.Draw(im)
    for p in polys:
        d.polygon([tuple(v) for v in p], fill=255)
    return np.asarray(im) > 0


def zone_outlines(cfg: dict, land: np.ndarray) -> np.ndarray:
    """Unsnapped zone raster: 0 sea, mapped/unmapped zone ids, 6 other land."""
    H, W = land.shape
    zone = np.full((H, W), 6, np.int8)
    lab, _ = nd.label(land)
    for z in cfg["paint_order"]:
        o = cfg["zones"][str(z)]["outline"]
        if o["kind"] == "west_of_grey_line":
            gx, gy = np.array(o["grey_line"], dtype=np.float64).T
            south = np.arange(H)[:, None] > np.interp(np.arange(W), gx, gy)[None, :]
            low = [k for k, sl in enumerate(nd.find_objects(lab), 1)
                   if sl is not None and sl[0].start > o["drop_components_below_y"]]
            m = land & south & (np.arange(W)[None, :] < o["max_x"]) & ~np.isin(lab, low)
        elif o["kind"] == "polygons":
            m = _poly_mask(o["polygons"], (H, W))
        elif o["kind"] == "land_component":
            x, y = o["seed"]
            if not lab[y, x]:
                raise ValueError(f"zone {z}: seed {o['seed']} is not on land")
            m = lab == lab[y, x]
        else:
            raise ValueError(f"zone {z}: unknown outline kind {o['kind']!r}")
        zone[m] = z
    zone[~land] = 0
    return zone


def snap_zones(zone: np.ndarray, land: np.ndarray, net: np.ndarray, snap: dict):
    """Faces of the border network take their majority zone (>= ``majority``).
    Returns ``(snapped, unsnapped)``: ``unsnapped`` lists faces over the size limit that missed it."""
    from skimage.morphology import disk
    core = nd.binary_erosion(land, disk(snap["erode_px"])) & ~nd.binary_dilation(net, disk(snap["dilate_px"]))
    fl, nf = nd.label(core)
    _, (iy, ix) = nd.distance_transform_edt(fl == 0, return_indices=True)
    faces = np.where(land, fl[iy, ix], 0)
    cnt = np.zeros((nf + 1, 8), np.int64)
    np.add.at(cnt, (faces[land], zone[land]), 1)
    maj = cnt.argmax(1)
    frac = cnt.max(1) / np.maximum(cnt.sum(1), 1)
    ok = frac >= snap["majority"]
    ok[0] = False
    out = zone.copy()
    sel = land & ok[faces]
    out[sel] = maj[faces][sel]
    lim = snap.get("report_unsnapped_over_px", 0)
    uns = [{"face_px": int(cnt[f].sum()), "majority_zone": int(maj[f]), "share": round(float(frac[f]), 2)}
           for f in np.nonzero(~ok[1:])[0] + 1 if cnt[f].sum() > lim]
    uns.sort(key=lambda u: (-u["face_px"], u["majority_zone"]))
    return out, uns


def assign_owners(zone: np.ndarray, xy: np.ndarray, priority, reach: int, mapped=MAPPED_ZONES) -> np.ndarray:
    """Owner zone of each IE point: its own mapped zone, else the first of ``priority``
    found within ``reach`` px, else 0. Points outside the frame get 0."""
    H, W = zone.shape
    p = np.round(xy).astype(int)
    inb = (p[:, 0] >= 0) & (p[:, 0] < W) & (p[:, 1] >= 0) & (p[:, 1] < H)
    out = np.zeros(len(xy), np.int8)
    zp = np.pad(zone, reach)
    px, py = p[inb, 0] + reach, p[inb, 1] + reach
    g = np.zeros(inb.sum(), np.int8)
    for z in list(priority)[::-1]:
        hit = np.zeros(len(px), bool)
        for dy in range(-reach, reach + 1):
            for dx in range(-reach, reach + 1):
                hit |= zp[py + dy, px + dx] == z
        g[hit] = z
    own = zone[p[inb, 1], p[inb, 0]]
    g = np.where(np.isin(own, mapped), own, g)
    out[inb] = g
    return out


# --------------------------------------------------------------------------- lines

def line_graph(mask: np.ndarray):
    """Skeleton px of ``mask`` and their 8-neighbour edges: ``(xy, edges)``."""
    from skimage.morphology import skeletonize
    sk = skeletonize(mask)
    ys, xs = np.nonzero(sk)
    idx = -np.ones(sk.shape, np.int64)
    idx[ys, xs] = np.arange(len(ys))
    H, W = sk.shape
    edges = []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        y2, x2 = ys + dy, xs + dx
        ok = (y2 < H) & (x2 >= 0) & (x2 < W)
        ii = np.nonzero(ok)[0]
        jj = idx[y2[ii], x2[ii]]
        m = jj >= 0
        edges.append(np.c_[ii[m], jj[m]])
    return np.c_[xs, ys].astype(np.float64), np.concatenate(edges) if edges else np.zeros((0, 2), int)


def seam_edges(edges, owner, canvas_xy, flag_px: float):
    """Split line edges into drawn ones and long seam bridges; per-seam gap stats."""
    a, b = edges[:, 0], edges[:, 1]
    live = (owner[a] > 0) & (owner[b] > 0)
    cross = live & (owner[a] != owner[b])
    gap = np.hypot(*(canvas_xy[a] - canvas_xy[b]).T)
    long_ = cross & (gap > flag_px)
    draw = live & ~long_
    seams = {}
    for k in np.nonzero(cross)[0]:
        key = f"{min(owner[a[k]], owner[b[k]])}/{max(owner[a[k]], owner[b[k]])}"
        seams.setdefault(key, []).append(gap[k])
    stats = {k: {"crossings": len(v), "gap_median": r1(np.median(v)), "gap_max": r1(max(v)),
                 "long": int(sum(g > flag_px for g in v))} for k, v in sorted(seams.items())}
    return draw, long_, stats


def known_answer_stats(border_px: np.ndarray, region: np.ndarray, line_px: np.ndarray, shift: int) -> dict:
    """Distance from projected line px inside ``region`` to the nearest ``border_px``,
    beside the same statistic for the line px shifted by +-``shift`` in x and in y."""
    if not border_px.any():
        return {"count": 0, "flags": ["no_drawn_borders"]}
    edt = nd.distance_transform_edt(~border_px)
    H, W = region.shape

    def stat(dx, dy):
        p = line_px + [dx, dy]
        ok = (p[:, 0] >= 0) & (p[:, 0] < W) & (p[:, 1] >= 0) & (p[:, 1] < H)
        p = p[ok]
        p = p[region[p[:, 1], p[:, 0]]]
        if not len(p):
            return None
        d = edt[p[:, 1], p[:, 0]]
        return float(np.median(d)), float(np.percentile(d, 90)), int(len(d))

    act = stat(0, 0)
    if act is None:
        return {"count": 0, "flags": ["no_line_px_in_region"]}
    sh = [s for s in (stat(shift, 0), stat(-shift, 0), stat(0, shift), stat(0, -shift)) if s is not None]
    bm = float(np.median([s[0] for s in sh])) if sh else float("nan")
    bp = float(np.median([s[1] for s in sh])) if sh else float("nan")
    return {"count": act[2], "median": r1(act[0]), "p90": r1(act[1]),
            "baseline_median": r1(bm), "baseline_p90": r1(bp),
            "ratio_median": round(act[0] / bm, 2) if bm > 0 else None,
            "ratio_p90": round(act[1] / bp, 2) if bp > 0 else None}


def state_border_px(state_id: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """4-neighbour px where two different kept (nonzero) states meet."""
    s = np.where(keep, state_id, 0)
    out = np.zeros(s.shape, bool)
    for a, b, sl_a, sl_b in ((s[:, :-1], s[:, 1:], np.s_[:, :-1], np.s_[:, 1:]),
                             (s[:-1, :], s[1:, :], np.s_[:-1, :], np.s_[1:, :])):
        m = (a > 0) & (b > 0) & (a != b)
        out[sl_a] |= m
        out[sl_b] |= m
    return out


# --------------------------------------------------------------------------- analysis

def sha_lf(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@dataclass
class Analysis:
    cfg: dict
    rows: list
    include_pending: bool
    land: np.ndarray
    zones: np.ndarray
    unsnapped: list
    net_ie: np.ndarray
    line_xy: np.ndarray          # IE px, float
    line_edges: np.ndarray
    owner: np.ndarray
    warps: dict
    zone_reports: dict
    canvas_xy: np.ndarray
    outside_master: int


def lines_in_master(cfg: dict):
    """Skeleton of the traced border layer, mapped into IE master px."""
    lf = cfg["frames"]["lines"]
    rgb, alpha = sources.load_source_image_rgba(lf["source"])
    if list(rgb.shape[1::-1]) != lf["size"]:
        raise ValueError(f"{lf['source']}: size {rgb.shape[1::-1]} != {lf['size']}")
    mask = (rgb == np.array(lf["colour"], np.uint8)).all(-1)
    if alpha is not None:
        mask &= alpha > 0
    xy, edges = line_graph(mask)
    num, den = lf["to_master_scale"]
    return xy * (num / den), edges


def _raster_net(xy, shape) -> np.ndarray:
    H, W = shape
    p = np.round(xy).astype(int)
    ok = (p[:, 0] >= 0) & (p[:, 0] < W) & (p[:, 1] >= 0) & (p[:, 1] < H)
    m = np.zeros(shape, bool)
    m[p[ok, 1], p[ok, 0]] = True
    return m


def analyse(rows: list[PairRow], cfg: dict, include_pending: bool = False) -> Analysis:
    fr = cfg["frames"]
    size = fr["master"]["size"]
    land = _land_from_climate(sources.load_source_image(fr["land"]["source"]), fr["land"], size)
    raw = zone_outlines(cfg, land)
    line_xy, edges = lines_in_master(cfg)
    net = _raster_net(line_xy, land.shape)
    zones, uns = snap_zones(raw, land, net, cfg["snap"])
    owner = assign_owners(zones, line_xy, cfg["ownership"]["priority"], cfg["ownership"]["reach_px"])
    W, H = size
    outside = int(((line_xy[:, 0] >= W) | (line_xy[:, 1] >= H)).sum())
    warps, reps = {}, {}
    canvas_xy = np.full_like(line_xy, np.nan)
    for z in MAPPED_ZONES:
        fit = fit_rows(rows, z, include_pending)
        src, dst = _xy(fit, "src"), _xy(fit, "dst")
        ids = [r.id for r in fit]
        mine = owner == z
        rep = {"name": cfg["zones"][str(z)]["name"], "drawn_fit": ids, "line_px": int(mine.sum())}
        if not fittable(src):
            rep["flags"] = ["unfittable"]
            reps[z] = rep
            continue
        held = np.array([bool(r.held_out) for r in fit])
        gy, gx = np.mgrid[0:H:4, 0:W:4]
        gsel = zones[gy, gx] == z
        grid = np.c_[gx[gsel], gy[gsel]].astype(np.float64)
        lxy = line_xy[mine]
        m = choose_method(src, dst, ids, lxy, grid, held)
        rep["held_out_ids"] = [i for i, h in zip(ids, held) if h]
        rep["evaluation_fit"] = [i for i, h in zip(ids, held) if not h]
        rep.update({"method": {"kind": "thin_plate", "lam": m["lam"], "flags": m["flags"]},
                    "chosen": m["chosen"], "candidates": m["candidates"]})
        if "fold_attribution" in m:
            rep["fold_attribution"] = m["fold_attribution"]
        w = ZoneWarp(z, m["lam"], tuple(ids), src, dst)
        warps[z] = w
        rep["outside_pair_hull_pct"] = r1(100 * (~w.inside_hull(lxy)).mean()) if len(lxy) else 0.0
        rep["triangle_warp"] = triangle_report(src, dst, ids, lxy)
        rep["flipped_control_triangles"] = rep["triangle_warp"]["flipped_triangles"]
        canvas_xy[mine] = w.forward(lxy)
        reps[z] = rep
    return Analysis(cfg, rows, include_pending, land, zones, uns, net, line_xy, edges, owner, warps, reps,
                    canvas_xy, outside)


# --------------------------------------------------------------------------- public API

@dataclass(frozen=True)
class Projection:
    zones: np.ndarray            # int8 (2880, 3703): 0 sea, 1-4 mapped, 5 Ulthuan, 6 other
    warps: dict                  # zone -> ZoneWarp, the method the rule picked
    priority: tuple              # ownership order on seams
    snap: dict                   # the snap rule the zones were built with


def load_projection(include_pending: bool = False, pairs_path: Path = PAIRS_PATH,
                    config_path: Path = CONFIG_PATH) -> Projection:
    """Every mapped zone's warp; ``ValueError`` if one cannot be fitted."""
    cfg = load_config(config_path)
    rows = read_pairs(pairs_path)
    validate_rows(rows, include_pending=include_pending)
    a = analyse(rows, cfg, include_pending)
    missing = [z for z in MAPPED_ZONES if z not in a.warps]
    if missing:
        raise ValueError(f"zones {missing} cannot be fitted (fewer than 4 non-collinear pairs)")
    return Projection(a.zones, dict(a.warps), tuple(cfg["ownership"]["priority"]), dict(cfg["snap"]))
