"""Scratch: macro-region PARTITION of the reprojected Terraqueous Globe (red borders only, no fill/labels).

Every pixel of the canvas belongs to exactly one region: region "cores" (polygons, painted in dict order,
later wins, so no overlap) cover the land; every pixel outside all cores joins the nearest core, so no
holes. Ocean wedges are therefore "nearest region", not real membership.
Core polygons are in a 2000x883 display frame. Output goes to the gitignored mapgen/derived/.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources/originals/terraqueous_globe_reprojected.png"
OUT = ROOT / "mapgen/derived/macro_regions_proposal.png"
OUT_SMALL = ROOT / "mapgen/derived/macro_regions_proposal_2048.png"

# name -> list of polygons (a region may be several pieces, e.g. an island group)
REGIONS = {
    "naggaroth": [[(90,140),(190,150),(300,140),(450,130),(600,150),(560,330),(520,420),(380,440),(230,460),(160,330),(165,200)]],
    "northern_chaos_wastes": [[(0,0),(650,0),(650,100),(560,140),(450,132),(300,140),(190,150),(90,140),(0,110)]],
    "lustria": [[(360,440),(520,430),(700,470),(760,560),(800,700),(760,760),(600,800),(420,760),(350,620)]],
    "ulthuan": [[(590,250),(690,230),(780,250),(790,390),(660,415),(590,380)]],
    "norsca_kislev": [[(900,100),(960,60),(1070,0),(1130,60),(1150,160),(1090,170),(960,190),(900,160)]],
    "old_world_west": [
        [(815,200),(900,170),(1000,175),(1000,310),(985,320),(940,380),(860,340),(815,270)],
        [(770,130),(890,130),(885,205),(790,215)],  # Albion
    ],
    "empire": [[(1000,150),(1130,140),(1130,258),(1060,255),(1000,265)]],
    "border_badlands": [[(975,265),(1000,262),(1060,250),(1130,245),(1130,330),(1100,395),(1000,400),(940,380),(985,320)]],
    "darklands": [[(1130,130),(1210,140),(1270,250),(1290,340),(1230,375),(1120,380),(1120,300)]],
    "ogre_kingdoms": [[(1200,130),(1350,95),(1500,140),(1560,180),(1440,230),(1420,300),(1300,330),(1260,300),(1210,200)]],
    "kurgan_steppes": [[(1130,0),(1560,0),(1560,170),(1500,140),(1350,95),(1200,130),(1130,100)]],
    "hung_steppes": [[(1560,0),(1999,0),(1999,170),(1700,200),(1560,170)]],
    "grand_cathay": [[(1430,230),(1560,165),(1680,165),(1860,225),(1790,280),(1730,350),(1700,430),(1560,420),(1440,370),(1400,300)]],
    "nippon": [
        [(1790,285),(1895,260),(1905,340),(1850,470),(1730,470),(1740,380)],
        [(1840,500),(1990,500),(1990,620),(1840,620)],  # Lumbria
    ],
    "ind": [
        [(1310,350),(1440,370),(1570,420),(1540,500),(1460,540),(1340,560),(1290,520)],
        [(1230,340),(1300,340),(1300,410),(1230,410)],  # Dragon Isles
        [(1230,540),(1380,540),(1380,620),(1230,620)],  # Sun Island / Stars Archipelago
    ],
    "kuresh": [[(1540,430),(1700,440),(1760,540),(1740,720),(1640,740),(1640,880),(1590,880),(1560,640),(1510,540)]],
    "araby": [[(760,370),(880,340),(990,390),(940,420),(930,480),(800,520),(770,450)]],
    "nehekhara": [[(930,380),(1000,395),(1100,390),(1130,440),(1090,470),(960,470),(930,430)]],
    "southlands_north": [[(900,470),(1090,470),(1140,430),(1230,420),(1240,570),(1000,570),(900,525)]],
    "southlands_south": [[(900,525),(1000,570),(1240,570),(1180,700),(1080,790),(980,780),(930,650)]],
}

W, H = 4096, 1808            # working resolution; borders are upscaled to the 8192 canvas
G = 1024 / 2000              # display frame -> 1024x452 core grid
GW, GH = 1024, 452


def build_labels():
    names = list(REGIONS)
    core = np.full((GH, GW), -1, np.int16)
    for i, n in enumerate(names):
        m = Image.new("L", (GW, GH), 0)
        d = ImageDraw.Draw(m)
        for poly in REGIONS[n]:
            d.polygon([(x * G, y * G) for x, y in poly], fill=255)
        core[np.array(m) > 0] = i
    # nearest-core fill for unassigned cells (distance to core-edge cells)
    nb = np.zeros(core.shape, bool)
    nb[1:] |= core[1:] != core[:-1]; nb[:-1] |= core[:-1] != core[1:]
    nb[:, 1:] |= core[:, 1:] != core[:, :-1]; nb[:, :-1] |= core[:, :-1] != core[:, 1:]
    ey, ex = np.nonzero((core >= 0) & nb)
    elab = core[ey, ex]
    uy, ux = np.nonzero(core < 0)
    for a in range(0, len(uy), 4000):
        dy = uy[a:a + 4000, None] - ey[None]
        dx = ux[a:a + 4000, None] - ex[None]
        core[uy[a:a + 4000], ux[a:a + 4000]] = elab[np.argmin(dy * dy + dx * dx, axis=1)]
    assert (core >= 0).all()
    # smooth the label map: blur one-hot masks, upsample, argmax
    best = np.full((H, W), -1.0, np.float32)
    lab = np.zeros((H, W), np.int16)
    for i in range(len(names)):
        m = Image.fromarray(((core == i) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
        m = np.asarray(m.resize((W, H), Image.BILINEAR), np.float32)
        up = m > best
        best[up] = m[up]
        lab[up] = i
    return lab


def main():
    lab = build_labels()
    bd = np.zeros((H, W), bool)
    bd[1:] |= lab[1:] != lab[:-1]
    bd[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    line = Image.fromarray((bd * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    line = line.resize((8192, 3616), Image.BILINEAR).filter(ImageFilter.MaxFilter(3))
    img = Image.open(SRC).convert("RGB")
    red = Image.new("RGB", img.size, (225, 25, 25))
    img = Image.composite(red, img, line.point(lambda v: 255 if v > 60 else 0))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    img.resize((2048, 904), Image.LANCZOS).save(OUT_SMALL)


if __name__ == "__main__":
    main()
