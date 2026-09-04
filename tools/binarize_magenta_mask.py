"""Binarize a magenta-marked mask into pure black/white.

SOURCE-preprocessing utility, not part of the game or the committed map pipeline:
reads and (by default) overwrites a mask under the local-only, gitignored
``sources/`` folder. Any magenta (255, 0, 255) pixel becomes black; every other
pixel becomes white.

Usage (from the repo root, with tools/.venv active):
    python tools/binarize_magenta_mask.py                       # overwrite sources/gimp_exports/land_sea_mask.png
    python tools/binarize_magenta_mask.py --src A.png --out B.png
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "sources" / "gimp_exports" / "land_sea_mask.png"

MAGENTA = (255, 0, 255)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


def binarize(a: np.ndarray) -> np.ndarray:
    """Magenta -> black, then everything non-black -> white."""
    out = a.copy()
    magenta_mask = (a[:, :, 0] == MAGENTA[0]) & (a[:, :, 1] == MAGENTA[1]) & (a[:, :, 2] == MAGENTA[2])
    out[magenta_mask] = BLACK
    black_mask = (out[:, :, 0] == 0) & (out[:, :, 1] == 0) & (out[:, :, 2] == 0)
    out[~black_mask] = WHITE
    out[black_mask] = BLACK
    return out


def main():
    ap = argparse.ArgumentParser(description="Replace magenta with black, then non-black with white.")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC, help="mask PNG to read")
    ap.add_argument("--out", type=Path, default=None, help="PNG to write (default: overwrite --src)")
    args = ap.parse_args()
    out_path = args.out or args.src

    a = np.array(Image.open(args.src).convert("RGB"))
    result = binarize(a)
    Image.fromarray(result, "RGB").save(out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
