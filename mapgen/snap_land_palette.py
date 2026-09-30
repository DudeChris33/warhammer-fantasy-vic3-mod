"""Dev-only: snap the land pixels of terraqueous_globe_reprojected.png to the 9-colour land palette.

Each land pixel snaps to its nearest palette colour. Gridlines and label text are "ink" (a pixel far
from every palette colour, or a thin dark feature): it is dropped and takes the class of the nearest
clean pixel. Rivers (blue-tinted thin lines) and the coastline (thin dark line hugging the land
edge) are kept as the original pixels. Class regions under SPECKLE_MIN px are merged into their
surroundings. Water is left as the original.
Writes sources/WIP/terraqueous_globe_reprojected_land_snapped.png (git-ignored).
"""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

Image.MAX_IMAGE_PIXELS = None
PALETTE = [  # glacier, then the 8 legend land bands (mapgen/lut/terraqueous_elevation.json)
    (222, 216, 201), (167, 171, 136), (201, 197, 160), (224, 210, 165), (213, 183, 151),
    (206, 161, 137), (174, 113, 109), (160, 89, 86), (142, 64, 57),
]
GLACIER_MAX_Y = 520   # glacier is polar page only; below this row it is never chosen
INK_DIST = 40         # RGB distance to the nearest palette colour above which a pixel is ink
TOPHAT = 12           # luminance a pixel sits below its 9px median to count as a thin dark line
BIG_WIN, BIG_DROP = 21, 60  # black top-hat window and depth that catch thick label strokes
INK_GROW = 2          # px the ink is dilated so anti-aliased fringes go with it
RIVER_DARK = 115      # luminance below which a river core can sit (deep rivers read near-black)
RIVER_MIN_EXTENT = 80 # a river is a long, slim dark component; letters and dashes are short
RIVER_MAX_FAT = 6     # component px per px of bbox diagonal above which it is text, not a line
RIVER_BLUE = 6        # b - r above which a dark thin pixel is a river
COAST_BAND = 4        # px from the land edge within which thin dark line is coastline
SPECKLE_MIN = 600     # class regions smaller than this many px are merged away...
SPECKLE_CLASSES = (0, 1, 2, 3)  # ...but only glacier and the 3 lowest land bands
BUFFER = 3            # px around rivers and coast exempt from all smoothing
MODE = 9

src = np.asarray(Image.open('sources/originals/terraqueous_globe_reprojected.png').convert('RGB'))
land0 = np.asarray(Image.open('mapgen/derived/land_sea_mask.png')).astype(bool)
land = ndi.binary_closing(land0, np.ones((9, 9), bool))  # rivers cut hairline holes in the fill
h, w, _ = src.shape
med = np.stack([ndi.median_filter(src[:, :, c], size=3) for c in range(3)], -1)
pal = np.array(PALETTE, float)
idx = np.empty((h, w), np.uint8)
dist = np.empty((h, w), np.float32)
for y0 in range(0, h, 256):
    blk = med[y0:y0 + 256].astype(float)
    d = ((blk[:, :, None, :] - pal[None, None]) ** 2).sum(-1)
    if y0 + 256 > GLACIER_MAX_Y:
        rows = np.arange(y0, min(y0 + 256, h)) >= GLACIER_MAX_Y
        d[rows, :, 0] = 1e12
    idx[y0:y0 + 256] = d.argmin(-1)
    dist[y0:y0 + 256] = np.sqrt(d.min(-1))

lum = src.astype(np.float32) @ np.array([0.3, 0.59, 0.11], np.float32)
thin = (ndi.median_filter(lum, size=9) - lum) > TOPHAT
big = (ndi.grey_closing(lum, size=(BIG_WIN, BIG_WIN)) - lum) > BIG_DROP
srcf = src.astype(int)
bluish = (srcf[:, :, 2] - srcf[:, :, 0]) > RIVER_BLUE
river = land & bluish & (lum < 175)  # no thin test: wide rivers are not thin
cand = land & (lum < RIVER_DARK) & ((srcf[:, :, 0] - srcf[:, :, 1]) < 30)  # dark, not red label text
lab, n = ndi.label(cand, structure=np.ones((3, 3), int))
area = np.bincount(lab.ravel(), minlength=n + 1)
dark_river = np.zeros(n + 1, bool)
for i, sl in enumerate(ndi.find_objects(lab), 1):
    hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    diag = float(np.hypot(hh, ww))
    if max(hh, ww) >= RIVER_MIN_EXTENT and min(hh, ww) > 3 and area[i] / diag < RIVER_MAX_FAT:
        dark_river[i] = True
river |= dark_river[lab]
river = ndi.binary_opening(ndi.binary_dilation(river, iterations=1), np.ones((2, 2), bool)) | river
edge = ndi.distance_transform_edt(land0) <= COAST_BAND
coast = edge & thin & ~bluish
keep = river | coast

ink = ((dist > INK_DIST) | thin | big) & land
ink = ndi.binary_dilation(ink, iterations=INK_GROW) & land  # includes keep: its fringe is filled
# sea pixels carry meaningless classes, so they never act as a fill source
_, (iy, ix) = ndi.distance_transform_edt(ink | ~land, return_indices=True)
idx = idx[iy, ix]

raw = idx.copy()
votes = np.stack([ndi.uniform_filter(((idx == k) & land).astype(np.float32), MODE) for k in range(9)], -1)
idx = votes.argmax(-1).astype(np.uint8)

small = np.zeros((h, w), bool)
for k in SPECKLE_CLASSES:
    lab, n = ndi.label(idx == k)
    if n:
        area = np.bincount(lab.ravel())
        small |= (area[lab] < SPECKLE_MIN) & (lab > 0)
_, (iy, ix) = ndi.distance_transform_edt(small | ~land, return_indices=True)
idx = idx[iy, ix]
near = ndi.distance_transform_edt(~keep) <= BUFFER
idx = np.where(near, raw, idx)

out = src.copy()
snap = land & ~keep
out[snap] = np.array(PALETTE, np.uint8)[idx][snap]
Image.fromarray(out).save('sources/WIP/terraqueous_globe_reprojected_land_snapped.png')
print('land', land.mean(), 'river px', river.sum(), 'coast px', coast.sum(), 'ink px', ink.sum())
print('usage', np.round(np.bincount(idx[land], minlength=9) / land.sum(), 4))
