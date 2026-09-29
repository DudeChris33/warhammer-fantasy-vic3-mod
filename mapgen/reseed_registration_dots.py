#!/usr/bin/env python3
"""Fold newly hand-marked anchor dots into a ``landmarks`` registration seed.

This is an **authoring tool**, not part of the offline gate — the paired-anchor
equivalent of ``fit_registration.py``/``sources.py --update-manifest``: run it
deliberately after the user adds new matched dot pairs to a seed's two "dots"
sheets, to detect the new dots, colour-pair them, name them and append them to
the seed's ``landmarks`` list. It then prints (or, with ``--fit``, runs) the
``fit_registration.py`` re-derive that turns the enlarged seed into the committed
registration record. The pure detection/pairing logic lives in
``worldgen/reseed_dots.py`` (self-checked by ``run_fixture.py --check``).

The seed's two sheets and their clean originals are derived by convention from
``dots_source`` (``"<master> - dots_N.png"``): the master original is
``<master>.png``, the canvas pair is ``terraqueous_globe_reprojected - dots_N.png``
and its original ``terraqueous_globe_reprojected.png`` (canvas space, where the
``canvas`` centroids are read — see ``fit_registration.anchor_landmarks``). An
optional ``dots_reseed`` block in the seed overrides any of these filenames and
carries the detection tuning (chroma floors, noisy rectangles, match tolerance).

Usage::

    python mapgen/reseed_registration_dots.py --seed tww3_old_world_mod_parchment_full
    python mapgen/reseed_registration_dots.py --seed <stem> --dry-run   # detect + report, write nothing
    python mapgen/reseed_registration_dots.py --seed <stem> --fit       # also re-run fit_registration
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import reseed_dots, sources  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
SEED_DIR = TOOLS_DIR / "registration" / "seeds"

#: The canvas image the ``canvas`` centroids are read off (see
#: ``fit_registration.anchor_landmarks`` — the reprojected globe IS canvas space).
CANVAS_BASE = "terraqueous_globe_reprojected"


def _load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


def _derive_names(seed: dict) -> dict:
    """Resolve the four image filenames + detection tuning from the seed."""
    dots_source = seed.get("dots_source")
    if not dots_source:
        raise SystemExit("seed has no 'dots_source' — not a paired-anchor-dot seed")
    if " - dots" not in dots_source:
        raise SystemExit(
            f"dots_source {dots_source!r} is not of the form '<master> - dots_N.png'")
    master_stem, rest = dots_source.split(" - dots", 1)
    suffix = " - dots" + rest  # e.g. ' - dots_7.png'

    cfg = dict(seed.get("dots_reseed", {}))
    return {
        "master_dots": cfg.get("master_dots", dots_source),
        "master_orig": cfg.get("master_original", f"{master_stem}.png"),
        "canvas_dots": cfg.get("canvas_dots", f"{CANVAS_BASE}{suffix}"),
        "canvas_orig": cfg.get("canvas_original", f"{CANVAS_BASE}.png"),
        "chroma_floor": int(cfg.get("chroma_floor", reseed_dots.DEFAULT_CHROMA_FLOOR)),
        "relaxed_chroma": cfg.get("relaxed_chroma"),
        "noisy_rects": tuple(tuple(r) for r in cfg.get("noisy_rects", ())),
        "match_tol_px": float(cfg.get("match_tol_px", reseed_dots.DEFAULT_MATCH_TOL_PX)),
        "max_colour_dist": float(
            cfg.get("max_colour_dist", reseed_dots.DEFAULT_MAX_COLOUR_DIST)),
    }


def reseed(stem: str, *, dry_run: bool = False, log=print) -> dict:
    seed_path = SEED_DIR / f"{stem}.json"
    if not seed_path.is_file():
        raise SystemExit(f"no seed file at {seed_path}")
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    if seed.get("objective") not in ("landmarks", "piecewise_affine", "landmark_refine"):
        raise SystemExit(
            f"seed objective {seed.get('objective')!r} is not landmark-based — "
            "reseeding dots only applies to a paired-anchor-dot seed")

    names = _derive_names(seed)
    paths = {k: sources.resolve_source_path(names[k])
             for k in ("master_dots", "master_orig", "canvas_dots", "canvas_orig")}
    for k, p in paths.items():
        if not p.is_file():
            raise SystemExit(f"{k} not found: expected {names[k]} (looked at {p})")
        log(f"{k:12s} {p}")

    master_orig = _load_rgb(paths["master_orig"])
    master_dots = _load_rgb(paths["master_dots"])
    canvas_orig = _load_rgb(paths["canvas_orig"])
    canvas_dots = _load_rgb(paths["canvas_dots"])

    m_dots = reseed_dots.detect_dots(
        master_orig, master_dots,
        chroma_floor=names["chroma_floor"], relaxed_chroma=names["relaxed_chroma"],
        noisy_rects=names["noisy_rects"])
    c_dots = reseed_dots.detect_dots(
        canvas_orig, canvas_dots, chroma_floor=names["chroma_floor"])
    log(f"detected      {len(m_dots)} master, {len(c_dots)} canvas dot(s)")

    landmarks = seed.setdefault("landmarks", [])
    m_new, m_matched = reseed_dots.select_new(
        m_dots, landmarks, "source", tol_px=names["match_tol_px"])
    c_new, c_matched = reseed_dots.select_new(
        c_dots, landmarks, "canvas", tol_px=names["match_tol_px"])
    log(f"already known  {m_matched} master, {c_matched} canvas "
        f"(of {len(landmarks)} landmarks)")
    log(f"new dots       {len(m_new)} master, {len(c_new)} canvas")

    pairs, up_m, up_c = reseed_dots.pair_by_colour(
        m_new, c_new, max_colour_dist=names["max_colour_dist"])
    for d in up_m:
        log(f"  UNPAIRED master {d.xy} colour {d.color} — no colour-matched canvas dot")
    for d in up_c:
        log(f"  UNPAIRED canvas {d.xy} colour {d.color} — no colour-matched master dot")

    existing_names = {lm["name"] for lm in landmarks if "name" in lm}
    new_landmarks = reseed_dots.name_pairs(pairs, existing_names)
    for lm, p in zip(new_landmarks, pairs):
        log(f"  + {lm['name']:12s} source {lm['source']}  canvas {lm['canvas']}  "
            f"(colour dist {p.colour_dist:.1f})")

    result = {
        "seed_path": seed_path,
        "added": new_landmarks,
        "unpaired_master": up_m,
        "unpaired_canvas": up_c,
        "total": len(landmarks) + len(new_landmarks),
    }
    if not new_landmarks:
        log("no new paired dots to fold — seed unchanged")
        return result

    landmarks.extend(new_landmarks)
    log(f"landmarks {len(landmarks) - len(new_landmarks)} -> {len(landmarks)}")
    if dry_run:
        log("--dry-run: seed NOT written")
        return result
    seed_path.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {seed_path}")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", required=True, help="seed stem under mapgen/registration/seeds/")
    ap.add_argument("--dry-run", action="store_true", help="detect + report, write nothing")
    ap.add_argument("--fit", action="store_true",
                    help="after folding, re-run fit_registration.py --seed <stem>")
    args = ap.parse_args(argv)

    result = reseed(args.seed, dry_run=args.dry_run)
    if result["added"] and not args.dry_run:
        if args.fit:
            import fit_registration
            print(f"\n=== fit_registration --seed {args.seed} ===")
            return fit_registration.main(["--seed", args.seed])
        print(f"\nNext: python mapgen/fit_registration.py --seed {args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
