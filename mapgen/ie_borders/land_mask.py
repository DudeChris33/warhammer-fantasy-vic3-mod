"""IE parchment land mask from its climate-map sibling (same recipe as fit_registration).

Step 1 of the IE border trace. Run order, from the repo root with mapgen/.venv active:
    python mapgen/ie_borders/land_mask.py
    python mapgen/ie_borders/trace_climate.py
    python mapgen/ie_borders/trace_ie.py
    python mapgen/ie_borders/combine.py
Writes intermediates to scratchpad/ie_borders/; combine.py writes the marked copy
``sources/tww3_ie_parchment - state_borders.png`` (local-only, like every source).
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "scratchpad" / "ie_borders"   # intermediates, git-ignored
HERE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "mapgen"))
from worldgen import parchment, segment, sources  # noqa: E402

rgb = sources.load_source_image("tww3_climate.jpg")
m = parchment.painted_mask(rgb, exclude=[(2040, 0, 2471, 400)])
m = segment.drop_small_components(m, 400, wrap_x=False)
m = ~segment.drop_small_components(~m, 400, wrap_x=False)
big = Image.fromarray((m * 255).astype(np.uint8)).resize((3703, 2880), Image.BILINEAR)
big.save(HERE / "land_mask.png")
ie = Image.open(ROOT / "sources/originals/tww3_ie_parchment.jpg").convert("RGB")
ov = np.array(ie).astype(np.float32)
mk = np.array(big) > 127
ov[mk] = ov[mk] * 0.6 + np.array([0, 160, 0]) * 0.4
Image.fromarray(ov.astype(np.uint8)).resize((1234, 960)).save(HERE / "land_mask_ov.png")
print("land frac", mk.mean())
