#!/usr/bin/env python3
"""One-shot: carry every hand-authored canvas coordinate from plate carree to Miller.

An **authoring** command, in the same family as ``worldgen/sources.py
--update-manifest`` and ``fit_registration.py``: it rewrites committed data on
purpose, so it is never part of the pre-commit gate and never runs as a side
effect of a generator. Run it once, review the diff, commit.

The migration is mechanical and lossless, because every canvas coordinate now
committed was *derived* from lon/lat rather than eyeballed::

    canvas px --(old plate carree)--> lon/lat --(new Miller)--> canvas px

The old constants are **carried here rather than imported**, deliberately: the
module that held them has been rewritten, and a migration that read its own
"before" state from the "after" file would be a no-op that looked like a success.

It **fails loudly** on any point that lands outside the canvas and never clamps.
Clamping is how ``map-the-old-world.json`` became misregistered in S2 — a control
point pinned to an edge stops describing its feature but keeps voting in the fit.

Two records cannot be migrated this way and are handled separately:

* ``terraqueous_globe.json`` — two of its control points sit on the old canvas's
  polar edges (lat +-79.453125), which are off the Miller canvas entirely
  (y = -258.6 and +4463.2). It is **re-emitted**: the NE-II fit is recovered from
  the committed record under the old frame and re-evaluated at fresh graticule
  crossings inside the new band, which is the same construction the record's own
  notes describe.
* ``fixtures/ingest/registration/synthetic_world.json`` — its four corners *are*
  its stated constraint ("registers the synthetic fixture world edge-to-edge")
  and must stay; only the two interior points move, to the canvas y their source
  row now implies.

Usage::

    python mapgen/migrate_frame_coords.py --dry-run     # print, write nothing
    python mapgen/migrate_frame_coords.py               # rewrite the records
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

from config import canvas_frame  # noqa: E402  (the NEW frame)
from worldgen import reproject  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
REGISTRATION_DIR = TOOLS_DIR / "registration"
FIXTURE_REG = TOOLS_DIR / "fixtures" / "ingest" / "registration" / "synthetic_world.json"

W, H = canvas_frame.WIDTH, canvas_frame.HEIGHT

# ---------------------------------------------------------------------------
# The OLD frame, frozen here on purpose (see the module docstring)
# ---------------------------------------------------------------------------

OLD_LON_MIN, OLD_LON_MAX = -180.0, 180.0
OLD_LAT_MAX = 79.453125
OLD_LAT_MIN = -79.453125
_OLD_PX_PER_DEG_LON = W / (OLD_LON_MAX - OLD_LON_MIN)
_OLD_PX_PER_DEG_LAT = H / (OLD_LAT_MAX - OLD_LAT_MIN)


def old_canvas_to_lonlat(x: float, y: float) -> tuple[float, float]:
    """The retired plate-carree reading of a canvas pixel. Does not fold x."""
    return (OLD_LON_MIN + x / _OLD_PX_PER_DEG_LON,
            OLD_LAT_MAX - y / _OLD_PX_PER_DEG_LAT)


class MigrationError(RuntimeError):
    """A coordinate could not be carried across the frames."""


#: Stamped into every migrated record's ``notes``, and refused on sight next run.
#: A canvas -> canvas migration is not idempotent: running it twice would apply
#: the reframe to already-reframed coordinates and land the world several hundred
#: pixels south, with nothing in the output looking obviously wrong. The globe
#: record catches a double-run on its own (the recovered NE-II fit falls apart),
#: but the three warp records have no such self-check, so they get this one.
MIGRATED_MARK = "MIGRATED to the Miller canvas frame (migrate_frame_coords.py, 2026-08-04)."


def _guard_already_migrated(data: dict, name: str) -> None:
    if MIGRATED_MARK in data.get("notes", ""):
        raise MigrationError(
            f"{name} is already marked as migrated. Re-running would apply the reframe "
            f"twice. Restore the pre-migration record from git before running this again."
        )


def _stamp(data: dict, extra: str = "") -> None:
    data["notes"] = (data.get("notes", "").rstrip() + " " + MIGRATED_MARK + " " + extra).strip()


def migrate_point(x: float, y: float, what: str, *, allow_seam: bool = True) -> tuple[float, float]:
    """One canvas point, old frame -> new frame. Raises if it leaves the canvas.

    ``allow_seam`` keeps a point recorded at exactly ``x = WIDTH`` there instead
    of folding it to 0: ``fit_parametric`` needs the seam pick to read back as
    +180, not -180 (see ``canvas_frame.canvas_to_lonlat``).
    """
    lon, lat = old_canvas_to_lonlat(x, y)
    nx, ny = canvas_frame.lonlat_to_canvas(lon, lat)
    nx, ny = float(nx) + 0.0, float(ny) + 0.0   # +0.0 folds IEEE -0.0 to 0.0
    if allow_seam and abs(x - W) < 1e-9:
        nx = float(W)
    if not (0.0 <= nx <= W) or not (0.0 <= ny <= H):
        raise MigrationError(
            f"{what}: ({x:.2f}, {y:.2f}) is lon {lon:.4f} lat {lat:.4f}, which lands at "
            f"({nx:.2f}, {ny:.2f}) — outside the {W}x{H} canvas. "
            f"This point cannot be migrated and must be re-authored, not clamped."
        )
    return (round(nx, 2), round(ny, 2))


def migrate_box(box, what: str) -> list[float]:
    """A footprint ``[x0, y0, x1, y1]``, migrated corner-wise and re-ordered.

    Latitude is nonlinear in y now, so the two corners do not move by the same
    amount; taking min/max after migrating both is what keeps the box a box.
    """
    x0, y0, x1, y1 = (float(v) for v in box)
    ax, ay = migrate_point(x0, y0, f"{what} (x0,y0)", allow_seam=False)
    bx, by = migrate_point(x1, y1, f"{what} (x1,y1)", allow_seam=False)
    return [min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)]


# ---------------------------------------------------------------------------
# Warp records: migrate control points + footprint in place
# ---------------------------------------------------------------------------

WARP_RECORDS = ("TheEmpire.json", "map-the-old-world.json", "tww3_map_stitched.json")


def migrate_warp_record(path: Path, dry_run: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    _guard_already_migrated(data, path.name)
    moved = []
    for i, cp in enumerate(data["control_points"]):
        ox, oy = cp["canvas"]
        nx, ny = migrate_point(ox, oy, f"{path.name}.control_points[{i}]")
        cp["canvas"] = [nx, ny]
        moved.append((cp.get("note", ""), ox, oy, nx, ny))
    old_fp = list(data["footprint"])
    data["footprint"] = migrate_box(old_fp, f"{path.name}.footprint")

    print(f"\n{path.name}")
    for note, ox, oy, nx, ny in moved:
        print(f"   ({ox:7.1f},{oy:7.1f}) -> ({nx:7.1f},{ny:7.1f})  dy {ny - oy:+7.1f}  {note}")
    print(f"   footprint {old_fp} -> {data['footprint']}")
    _stamp(data, "Control points and footprint were carried through lon/lat, not re-picked: "
                 "canvas px -> old plate carree -> lon/lat -> Miller. The source-side picks "
                 "are untouched, so the features they name are unchanged.")
    if not dry_run:
        _write_json(path, data)


# ---------------------------------------------------------------------------
# The globe: re-emitted, not shifted
# ---------------------------------------------------------------------------

GLOBE = "terraqueous_globe.json"

#: Graticule crossings to re-emit the globe's control points at. Chosen the same
#: way the S2 record chose its own: spread across the oval so the two scale
#: parameters are well conditioned, all comfortably inside the new band
#: (+74.905 / -57.408), and all inside the record's crop.
GLOBE_GRATICULE = [
    (-170.0, 0.0, "meridian 170W x equator"),
    (-90.0, 0.0, "meridian 90W x equator"),
    (0.0, 0.0, "central meridian x equator"),
    (90.0, 0.0, "meridian 90E x equator"),
    (170.0, 0.0, "meridian 170E x equator"),
    (0.0, 60.0, "central meridian x 60N"),
    (0.0, -50.0, "central meridian x 50S"),
    (-120.0, 40.0, "meridian 120W x 40N"),
    (120.0, -40.0, "meridian 120E x 40S"),
    ("north_edge", None, "central meridian x canvas north edge"),
    ("south_edge", None, "central meridian x canvas south edge"),
]


def recover_old_globe_fit(path: Path):
    """The NE-II fit the committed globe record encodes, read under the OLD frame.

    This is the one thing the migration must not get wrong: the fit *is* the
    geometric authority, and it is a property of the artwork, not of the canvas.
    Reading it back through the retired frame recovers exactly the constants S2
    measured — which the caller asserts.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    lon, lat, sxp, syp = [], [], [], []
    for cp in data["control_points"]:
        lo, la = old_canvas_to_lonlat(*cp["canvas"])
        lon.append(lo)
        lat.append(la)
        sxp.append(cp["source"][0])
        syp.append(cp["source"][1])
    X, Y = reproject._project_norm("natural_earth_2", np.array(lon), np.array(lat))
    sxp = np.array(sxp, dtype=np.float64)
    syp = np.array(syp, dtype=np.float64)
    (cx, sx), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(X), X]), sxp, rcond=None)
    (cy, sy), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(Y), -Y]), syp, rcond=None)
    r = np.concatenate([(cx + sx * X) - sxp, (cy - sy * Y) - syp])
    return (float(cx), float(cy), float(sx), float(sy),
            float(np.sqrt((r ** 2).mean())), data)


#: Replacement ``notes`` for the globe record. Written whole rather than appended:
#: the old text describes the plate-carree construction, including two control
#: points that no longer exist, so amending it would leave a record that
#: contradicts its own contents.
GLOBE_NOTES = (
    "Terraqueous Globe - Natural Earth II, stated in the map's own legend ('Compromise "
    "pseudocylindrical projection Natural Earth II') and confirmed by measurement. The "
    "NE-II envelope was fitted in S2 (2026-07-23) by tracing the oval's drawn boundary "
    "curve across 2001 rows and least-squares fitting the envelope to it, giving centre "
    "(1999.55, 1129.29), scale sx=702.2114 sy=702.6857, inlier RMS 0.363 px with every "
    "traced row inside 10 px. Two independent checks pass - sx/sy = 0.99933 (isotropic, "
    "i.e. drawn to true NE-II proportions, which a wrong polynomial could not produce "
    "alongside a sub-pixel envelope fit), and the fitted graticule lands within ~2 px of "
    "the map's own printed degree labels (170W at x=234, measured 236; equator y=1129, "
    "measured 1130; 20S y=1378, measured 1377). "
    "RE-EMITTED for the Miller canvas (2026-08-04): the S2 fit above is a property of the "
    "ARTWORK, not of the canvas, so it was recovered unchanged from the previous record "
    "(0.0019 px rms) and re-evaluated at graticule crossings inside the new band. The two "
    "old polar picks could not be migrated - they sat at lat +-79.453125, which under "
    "Miller is y = -258.6 and +4463.2, off the canvas - so the edge picks are now the "
    "band's own limits, 74.9052N and 57.4084S. reproject.py recovers the same four "
    "constants from this table to 0.002 px. "
    "Crop is the oval interior, inset ~4 px from the drawn boundary rule so the black "
    "envelope line is never sampled; the generator clamps into the crop rather than "
    "masking, because the canvas seam at lon +-180 lands exactly on that rule. The polar "
    "insets (from y=2148) and the title/legend block sit outside it. Highest coastline "
    "precedence: this is the only whole-world source registered to sub-pixel accuracy, so "
    "it - not the regional relief - defines the shoreline."
)


def reemit_globe(path: Path, dry_run: bool) -> None:
    cx, cy, sx, sy, rms, data = recover_old_globe_fit(path)
    _guard_already_migrated(data, path.name)
    print(f"\n{path.name} — RE-EMITTED (its polar control points are off the Miller canvas)")
    print(f"   recovered S2 fit under the old frame: centre=({cx:.4f}, {cy:.4f}) "
          f"scale=({sx:.4f}, {sy:.4f}) rms={rms:.6f} px")
    if rms > 0.01:
        raise MigrationError(
            f"recovering the NE-II fit from {path.name} gave {rms:.4f} px rms — expected "
            f"<= 0.01. The committed record has been hand-edited; fix it before migrating."
        )

    fit = reproject.ParametricFit("natural_earth_2", cx, cy, sx, sy, rms, 0.0)
    cps = []
    for lon, lat, note in GLOBE_GRATICULE:
        if lat is None:
            # The two canvas-edge picks: the latitude is whatever the new band's
            # edge row *is*, so they pin the frame's own limits rather than a
            # round number that would sit just off the edge.
            north = lon == "north_edge"
            lat = canvas_frame.LAT_TOP if north else canvas_frame.LAT_BOTTOM
            note = f"{note} ({abs(lat):.4f}{'N' if north else 'S'})"
            lon = 0.0
        sxp, syp = fit.to_source(lon, lat)
        cxx, cyy = canvas_frame.lonlat_to_canvas(lon, lat)
        cps.append({
            "source": [round(float(sxp), 2), round(float(syp), 2)],
            "canvas": [round(float(cxx), 2), round(float(cyy), 2)],
            "note": note,
        })
    data["control_points"] = cps

    for cp in cps:
        print(f"   src ({cp['source'][0]:7.2f},{cp['source'][1]:7.2f}) -> "
              f"canvas ({cp['canvas'][0]:7.2f},{cp['canvas'][1]:7.2f})  {cp['note']}")

    # Prove the re-emitted table recovers the same four constants.
    lon2, lat2, sx2, sy2 = [], [], [], []
    for cp in cps:
        lo, la = canvas_frame.canvas_to_lonlat(*cp["canvas"])
        lon2.append(float(lo))
        lat2.append(float(la))
        sx2.append(cp["source"][0])
        sy2.append(cp["source"][1])
    X, Y = reproject._project_norm("natural_earth_2", np.array(lon2), np.array(lat2))
    sx2 = np.array(sx2)
    sy2 = np.array(sy2)
    (ncx, nsx), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(X), X]), sx2, rcond=None)
    (ncy, nsy), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(Y), -Y]), sy2, rcond=None)
    r = np.concatenate([(ncx + nsx * X) - sx2, (ncy - nsy * Y) - sy2])
    nrms = float(np.sqrt((r ** 2).mean()))
    drift = max(abs(ncx - cx), abs(ncy - cy), abs(nsx - sx), abs(nsy - sy))
    print(f"   re-fit from the new table: centre=({ncx:.4f}, {ncy:.4f}) "
          f"scale=({nsx:.4f}, {nsy:.4f}) rms={nrms:.6f} px  max drift {drift:.6f} px")
    if drift > 0.01 or nrms > 0.01:
        raise MigrationError(
            f"re-emitted globe record recovers the fit to {drift:.4f} px at {nrms:.4f} px rms — "
            f"expected < 0.01 on both. The migration is wrong; do not commit it."
        )
    data["notes"] = GLOBE_NOTES
    _stamp(data)
    if not dry_run:
        _write_json(path, data)


# ---------------------------------------------------------------------------
# The fixture's synthetic world
# ---------------------------------------------------------------------------

#: The fixture source's own dimensions (``fixtures/ingest/synthetic_world.png``).
FIXTURE_SOURCE = (256, 128)


def migrate_fixture(path: Path, dry_run: bool) -> None:
    """Move the two interior points; the four corners are the record's constraint.

    This record does **not** take the generic canvas-to-canvas rule, and getting
    that wrong would quietly break the fixture. The record declares an
    ``equirectangular`` source pinned edge-to-edge on the canvas, so its geometry
    is defined by the corners: source x spans the canvas's full longitude range
    and source y its full latitude range, both linearly *in lon/lat*. An interior
    control point is therefore correct only if it sits on those two lines — which
    means deriving its canvas position from its **source** pixel, not migrating
    its old canvas position.

    Migrating the canvas side instead would move the centre point to (4098, 2142)
    — canvas centre, lon/lat origin — while leaving its source pixel at (128, 64),
    which is *not* where lon 0 falls once the band is asymmetric. The fit would
    stop being exact, and the record's own note ("the reported residual stays a
    real conditioning check rather than a fitted-away one") would become false.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    sw, sh = FIXTURE_SOURCE
    lon0, lat0 = canvas_frame.canvas_to_lonlat(0.0, 0.0)
    lon1, lat1 = canvas_frame.canvas_to_lonlat(float(W), float(H))

    print(f"\n{path.name}")
    print(f"   corners pin source x 0..{sw} to lon {float(lon0):.4f}..{float(lon1):.4f}, "
          f"source y 0..{sh} to lat {float(lat0):.4f}..{float(lat1):.4f}")
    for i, cp in enumerate(data["control_points"]):
        ox, oy = (float(v) for v in cp["canvas"])
        if (ox in (0.0, float(W))) and (oy in (0.0, float(H))):
            print(f"   ({ox:7.1f},{oy:7.1f}) kept - corner (the record's stated constraint)")
            continue
        sx, sy = (float(v) for v in cp["source"])
        lon = float(lon0) + (sx / sw) * (float(lon1) - float(lon0))
        lat = float(lat0) + (sy / sh) * (float(lat1) - float(lat0))
        nx, ny = canvas_frame.lonlat_to_canvas(lon, lat)
        nx, ny = round(float(nx), 2), round(float(ny), 2)
        if not (0.0 <= nx <= W) or not (0.0 <= ny <= H):
            raise MigrationError(
                f"{path.name}.control_points[{i}] lands at ({nx}, {ny}) — off canvas")
        cp["canvas"] = [nx, ny]
        print(f"   ({ox:7.1f},{oy:7.1f}) -> ({nx:7.1f},{ny:7.1f})  dy {ny - oy:+7.1f}  "
              f"from source ({sx:.0f},{sy:.0f}) = lon {lon:.4f} lat {lat:.4f}  "
              f"{cp.get('note', '')}")
    _assert_fixture_exact(data, sw, sh)
    # Idempotent by construction — the interior points are derived from their
    # SOURCE pixel, so re-running recomputes the same answer rather than
    # compounding. Stamped for the record, not guarded.
    _stamp(data, "The four corners are unchanged (they are the record's edge-to-edge "
                 "constraint); the two interior points were re-derived from their source "
                 "pixel through the new band, so the fit stays exact and its residual "
                 "stays a real conditioning check.")
    if not dry_run:
        _write_json(path, data)


def _assert_fixture_exact(data: dict, sw: int, sh: int) -> None:
    """The re-authored table must still fit its equirectangular record exactly."""
    lon, lat, sxp, syp = [], [], [], []
    for cp in data["control_points"]:
        lo, la = canvas_frame.canvas_to_lonlat(*cp["canvas"])
        lon.append(float(lo))
        lat.append(float(la))
        sxp.append(cp["source"][0])
        syp.append(cp["source"][1])
    X = np.array(lon)
    Y = np.array(lat)
    sxp = np.array(sxp, dtype=np.float64)
    syp = np.array(syp, dtype=np.float64)
    (cx, sx), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(X), X]), sxp, rcond=None)
    (cy, sy), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(Y), -Y]), syp, rcond=None)
    r = np.concatenate([(cx + sx * X) - sxp, (cy - sy * Y) - syp])
    rms = float(np.sqrt((r ** 2).mean()))
    # The floor is the 2-decimal rounding of the committed canvas coordinates:
    # 0.005 canvas px carries through to ~4e-05 source px on this 256-px source.
    # The failure this guards against — deriving the interior points from their
    # old *canvas* position instead of their source pixel — misplaces them by
    # 8.75 degrees of latitude, i.e. ~8.5 source px, so the two are five orders
    # of magnitude apart and the threshold does not need to be tight to separate
    # them.
    print(f"   equirectangular re-fit: rms {rms:.3e} px (redundant-by-construction; the "
          f"floor is 2-decimal coordinate rounding)")
    if rms > 1e-3:
        raise MigrationError(
            f"fixture record re-fits at {rms:.3e} px rms — the interior points are no longer "
            f"redundant with the corners, so the fixture's conditioning check is broken."
        )


# ---------------------------------------------------------------------------
# Anchors
# ---------------------------------------------------------------------------

#: The plate-carree ANCHORS block as committed before this migration. Frozen here
#: for the same reason the old frame constants are: the module that held it has
#: already been rewritten, so re-running this script has to reproduce the same
#: answer rather than migrate an already-migrated table a second time.
OLD_ANCHORS: dict[str, tuple[int, int]] = {
    "naggaroth":          (1826, 590),
    "ulthuan_ring":       (2789, 1103),
    "lustria":            (2235, 2114),
    "norsca":             (4125, 370),
    "old_world_empire":   (4224, 610),
    "estalia":            (3781, 870),
    "araby":              (3654, 1350),
    "land_of_the_dead":   (4208, 1479),
    "southland":          (4341, 2017),
    "dark_lands":         (4966, 686),
    "dragon_isles":       (5232, 1391),
    "ogre_kingdoms":      (5866, 593),
    "grand_cathay":       (6530, 686),
    "kingdoms_of_ind":    (6176, 1391),
    "kingdoms_of_kuresh": (6463, 1725),
    "nippon":             (7527, 873),
}


def emit_anchors() -> None:
    """Print the migrated ANCHORS block, and check it against what is committed.

    The block is printed for pasting, but the check is the point: ``canvas_frame``
    already carries migrated values, so a disagreement here means one of the two
    was derived differently and the discrepancy has to be resolved before anything
    is regenerated against it.
    """
    print("\nANCHORS (for config/canvas_frame.py):")
    pad = max(len(k) for k in OLD_ANCHORS) + 4
    disagreed = []
    for name, (ox, oy) in sorted(OLD_ANCHORS.items()):
        nx, ny = migrate_point(float(ox), float(oy), f"ANCHORS[{name}]")
        new = (round(nx), round(ny))
        committed = canvas_frame.ANCHORS.get(name)
        flag = ""
        if committed is not None and committed != new:
            flag = f"   <-- committed says {committed}"
            disagreed.append(name)
        key = f'"{name}":'
        print(f"    {key:<{pad}}{new},{flag}")
    if disagreed:
        print(f"  WARNING: {len(disagreed)} committed anchor(s) disagree with the migration: "
              f"{disagreed}")
    else:
        print("  committed ANCHORS agree with the migration exactly.")


# ---------------------------------------------------------------------------

#: Collapses a fully-numeric JSON array back onto one line. ``json.dumps(indent=2)``
#: puts every number on its own row, which turns a 2-element control point into
#: eight lines and makes these hand-reviewed records unreadable in a diff.
_NUMERIC_ARRAY = re.compile(
    r"\[\s*\n\s*(-?\d[\d.eE+-]*(?:,\s*\n\s*-?\d[\d.eE+-]*)*)\s*\n\s*\]"
)


def _compact_numeric_arrays(text: str) -> str:
    return _NUMERIC_ARRAY.sub(
        lambda m: "[" + ", ".join(p.strip() for p in m.group(1).split(",")) + "]", text
    )


def _write_json(path: Path, data: dict) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False)
    path.write_text(_compact_numeric_arrays(text) + "\n", encoding="utf-8")
    print(f"   wrote {path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="print the migration, write nothing")
    args = p.parse_args(argv)

    print(f"old frame: plate carree, lat +-{OLD_LAT_MAX}")
    print(f"new frame: Miller, R={canvas_frame.R_CANVAS:.4f} X0={canvas_frame.X0} "
          f"Y0={canvas_frame.Y0}  ({canvas_frame.LAT_TOP:.4f}N .. {canvas_frame.LAT_BOTTOM:.4f}S)")

    for name in WARP_RECORDS:
        migrate_warp_record(REGISTRATION_DIR / name, args.dry_run)
    reemit_globe(REGISTRATION_DIR / GLOBE, args.dry_run)
    migrate_fixture(FIXTURE_REG, args.dry_run)
    emit_anchors()

    if args.dry_run:
        print("\n--dry-run: nothing written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
