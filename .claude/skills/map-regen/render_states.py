#!/usr/bin/env python3
"""State-level review render: each state tinted, black state borders, dark grey = impassable,
optional numbered yellow markers. Reads only committed data (map_data/provinces.png + state files).

Show Chris states, not the province partition: the province render (render_provinces_preview.py)
buries state problems under ~5,500 province edges.

    python .claude/skills/map-regen/render_states.py                       # in-scope overview, half res
    python .claude/skills/map-regen/render_states.py --crop 4000,1000,4300,1200 --scale 4 \
        --mark 4139,1081,8 --mark 3560,1109,10 --out scratchpad/problem_spots.png

Names are labelled only on crops (<= 1200 px wide at the chosen scale) so they stay readable.
"""
import argparse
import glob
import hashlib
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parents[3]


def load_states():
    sid, imp, names = {}, set(), []
    for p in sorted(glob.glob(str(REPO / "map_data" / "state_regions" / "*.txt"))):
        text = Path(p).read_text(encoding="utf-8-sig")
        for m in re.finditer(r"(STATE_\w+)\s*=\s*\{(.*?)\n\}", text, re.S):
            key, body = m.groups()
            pr = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", body)
            if not pr:
                continue
            if key not in names:
                names.append(key)
            for c in pr.group(1).split():
                sid[int(c[1:], 16)] = names.index(key)
            im = re.search(r"impassable\s*=\s*\{([^}]*)\}", body)
            if im:
                imp.update(int(c[1:], 16) for c in im.group(1).split())
    loc = {}
    for p in glob.glob(str(REPO / "localization" / "replace" / "english" / "map" / "states_l_english.yml")):
        for m in re.finditer(r'^\s*(STATE_\w+):\d*\s+"([^"]*)"', Path(p).read_text(encoding="utf-8-sig"), re.M):
            loc[m.group(1)] = m.group(2)
    return sid, imp, names, loc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crop", default="750,150,5350,2650", help="x0,y0,x1,y1 in canvas px")
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--mark", action="append", default=[], help="x,y,label (repeatable)")
    ap.add_argument("--out", default="scratchpad/state_map.png")
    a = ap.parse_args()
    x0, y0, x1, y1 = (int(v) for v in a.crop.split(","))
    prov = np.array(Image.open(REPO / "map_data" / "provinces.png").convert("RGB"))[y0:y1, x0:x1]
    key = (prov[..., 0].astype(np.uint32) << 16) | (prov[..., 1].astype(np.uint32) << 8) | prov[..., 2]
    sid, imp, names, loc = load_states()
    uk, inv = np.unique(key, return_inverse=True)
    st = np.array([sid.get(int(c), -1) for c in uk])
    S = st[inv].reshape(key.shape)
    cols = np.array([[110 + hashlib.md5(n.encode()).digest()[i] % 120 for i in range(3)] for n in names]
                    + [[40, 60, 90]], np.uint8)
    img = cols[np.where(S < 0, len(names), S)]
    img[np.isin(key, list(imp))] = (70, 70, 70)
    b = np.zeros(S.shape, bool)
    b[:, 1:] |= S[:, 1:] != S[:, :-1]
    b[1:, :] |= S[1:, :] != S[:-1, :]
    img[b & (S >= 0)] = (0, 0, 0)
    im = Image.fromarray(img)
    z = a.scale
    im = im.resize((int(im.width * z), int(im.height * z)), Image.NEAREST)
    d = ImageDraw.Draw(im)
    if im.width <= 1200:
        font = ImageFont.truetype("arial.ttf", 16)
        for si, name in enumerate(names):
            ys, xs = np.nonzero(S == si)
            if len(xs) < 150:
                continue
            d.text((xs.mean() * z, ys.mean() * z), loc.get(name, name).replace("STATE_", ""), fill=(0, 0, 0),
                   font=font, anchor="mm", stroke_width=2, stroke_fill=(255, 255, 255))
    mf = ImageFont.truetype("arial.ttf", 22)
    for spec in a.mark:
        mx, my, label = spec.split(",", 2)
        px, py = (int(mx) - x0) * z, (int(my) - y0) * z
        d.ellipse([px - 16, py - 16, px + 16, py + 16], fill=(255, 255, 0), outline=(0, 0, 0), width=3)
        d.text((px, py), label, fill=(0, 0, 0), font=mf, anchor="mm")
    out = REPO / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    print(f"wrote {out}  ({im.width}x{im.height})")


if __name__ == "__main__":
    main()
