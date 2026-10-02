#!/usr/bin/env python3
"""Bootstrap renderer: paint ``state_ownership.png`` from a proposed assignment.

Chris repaints the PNG, not the proposal -- the PNG (read back by
``read_state_ownership.py``) is the source of truth. This script exists to
produce the first draft of it from ``state_ownership_proposal.json`` (one entry
per drawn state: ``owner`` = a tag or ``unowned``, or ``split`` = province ->
owner for the rare state divided between owners). It draws:

* each drawn state flat-filled with its owner's legend colour;
* out-of-scope placeholder states in the placeholder colour, water (sea and
  lakes) in the water colour;
* a thin state-border line on top, so borders stay visible while painting.

Runs from committed data only (``map_data/provinces.png``, the state files,
``provinces_index.json``); no ``sources/``, no globe backdrop. The written PNG
is refused if it already exists unless ``--force`` -- a repainted map is never
silently overwritten.

Usage::

    python mapgen/render_state_ownership.py                # write mapgen/config/state_ownership.png
    python mapgen/render_state_ownership.py --review       # also mapgen/derived/state_ownership_review.png
    python mapgen/render_state_ownership.py --roundtrip    # render + read back in memory, compare, write nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import raster, state_ownership as so  # noqa: E402

MOD_ROOT = Path(__file__).resolve().parent.parent
PROPOSAL_PATH = MOD_ROOT / "mapgen" / "config" / "state_ownership_proposal.json"
LEGEND_PATH = MOD_ROOT / "mapgen" / "config" / "state_ownership_legend.json"
PNG_PATH = MOD_ROOT / "mapgen" / "config" / "state_ownership.png"
REVIEW_PATH = MOD_ROOT / "mapgen" / "derived" / "state_ownership_review.png"


def load_assignment(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: dict = {}
    for key, entry in doc["states"].items():
        if "split" in entry:
            out[key] = dict(entry["split"])
        else:
            out[key] = entry["owner"]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proposal", type=Path, default=PROPOSAL_PATH)
    ap.add_argument("--legend", type=Path, default=LEGEND_PATH)
    ap.add_argument("--out", type=Path, default=PNG_PATH)
    ap.add_argument("--force", action="store_true", help="overwrite an existing --out")
    ap.add_argument("--border-width", type=int, choices=(1, 2), default=2)
    ap.add_argument("--review", action="store_true", help="also write the annotated half-size review render")
    ap.add_argument("--numbers", action="store_true", help="review render: also print each state's numeric id under its tag code")
    ap.add_argument("--labels", choices=("country", "tag", "state"), default="country", help="review render label: first 12 chars of the owning country's name (default), the owner tag code, or the state's localized name")
    ap.add_argument("--scale", type=float, default=0.5, help="review render scale (default 0.5; 1.0 for legible numbers)")
    ap.add_argument("--review-out", type=Path, default=REVIEW_PATH)
    ap.add_argument("--roundtrip", action="store_true", help="render, read back in memory, compare; write nothing")
    args = ap.parse_args(argv)

    try:
        legend = so.load_legend(args.legend)
        layout, placeholder, ids_anchor = so.load_inputs(MOD_ROOT)
        assignment = load_assignment(args.proposal)
        owners = so.province_owners(layout, assignment, placeholder, legend)
        img = so.render(layout, owners, legend, args.border_width)
        if args.roundtrip:
            back = so.assignment_of(so.read(layout, img, legend, placeholder, ids_anchor))
            want = so.normalize_assignment(assignment, layout)
            if back != want:
                diff = sorted(k for k in want if back.get(k) != want[k])
                print(f"render_state_ownership: ROUND-TRIP MISMATCH in {len(diff)} state(s): {diff[:8]}",
                      file=sys.stderr)
                return 1
            print(f"render_state_ownership: round-trip OK ({len(want)} drawn states).")
            return 0
        if args.out.exists() and not args.force:
            print(f"render_state_ownership: {args.out} exists -- it may hold Chris's repaint; "
                  f"pass --force to overwrite", file=sys.stderr)
            return 1
        raster.write_rgb_png(args.out, img)
        print(f"render_state_ownership: wrote {args.out}")
        if args.review:
            so.review_render(img, layout, owners, legend, scale=args.scale, numbers=args.numbers,
                labels=args.labels,
                state_names=so.load_state_names(MOD_ROOT) if args.labels == "state" else None).save(args.review_out)
            print(f"render_state_ownership: wrote {args.review_out}")
    except so.OwnershipError as exc:
        print(f"render_state_ownership: ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
