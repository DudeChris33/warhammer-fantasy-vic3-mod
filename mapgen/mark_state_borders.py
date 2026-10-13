"""Draw magenta marker lines over the STATE-REGION boundaries of the dense Old World
state-regions map, producing the ``marker_lines`` input the boundary extraction consumes.

This is a SOURCE-preprocessing step, not part of the game or the committed map pipeline:
it reads the pristine copy of the map and writes the marked copy back into the local-only,
gitignored ``sources/`` folder. The magenta convention matches
``mapgen/worldgen/parchment.marker_barrier``: pure (255, 0, 255), detected at max-channel
distance <= 80, dilated 2 px at extraction time.

The map draws four kinds of dark ink plus roads; only ONE of them is wanted:

  STATE-REGION borders  -- solid near-black stroke, ~3-4 px core        -> mark magenta
  internal province borders -- same ink, but only ~1-2 px wide          -> leave
  rivers / lakes / sea  -- same ink family, >= 5-6 px wide (tapering)   -> leave
                           (rivers are unioned into the barrier by the extractor itself)
  lettering             -- region / river / road names, same ink        -> leave
  roads                 -- light orange ribbon, edges V >= ~85          -> excluded by the
                           ink threshold entirely

So the classifier is: threshold the ink (V < INK_V keeps boundary/river/text ink but not
road edges or parchment), skeletonize it, cut the skeleton into short chunks, and measure
each chunk's EFFECTIVE stroke width: darkness integrated along the perpendicular at every
skeleton pixel (anti-aliasing makes a hard second threshold unreliable — the same stroke
reads 2 px or 3 px depending on where it crosses the pixel grid, while its integrated
ink mass is stable). State borders sit in a width band between province hairlines and
river ribbons. Lettering that survives the ink threshold is removed twice over: isolated
words by compact-component shape up front, and letters touching linework later by the
chunk filters (short length, high local ink density). Chunks hugging the alpha edge (the
canvas cut) are never marked.

Usage (from the repo root, with mapgen/.venv active):
    python mapgen/mark_state_borders.py            # write the marked PNG + QA thumbnail
    python mapgen/mark_state_borders.py --preview  # write only the class-coloured overlay
    python mapgen/mark_state_borders.py --src A.png --out B.png
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "sources" / "claude_old_world_state_regions_pristine.png"
DEFAULT_OUT = ROOT / "sources" / "claude_old_world_state_regions.png"
QA_DIR = ROOT / "scratchpad"

#: Hand-authored patch data, like ``mapgen/config/inland_lakes.json``: the residue the
#: classifier cannot decide. ``paint`` holds [[x, y], ...] polylines forced magenta
#: (borders the artist drew too faint to detect); ``erase`` holds [x, y, w, h] boxes
#: whose automatic markings are suppressed (stubborn false positives). Coordinates are
#: full-resolution source pixels. Edit deliberately and re-run; never generated.
OVERRIDES = ROOT / "mapgen" / "config" / "state_border_overrides.json"

MAGENTA = (255, 0, 255)

INK_V = 80            # ink = max(R,G,B) < this; parchment >= ~150, road edges >= ~85
DARK_FLOOR = 170      # darkness D = clip(DARK_FLOOR - V, 0, DARK_SPAN) / DARK_SPAN
DARK_SPAN = 130       # ... so V<=40 counts as full ink, V>=170 as none
PERP_REACH = 4.0      # half-length of the perpendicular sampling ray, px
PERP_STEP = 0.5       # sampling step along the ray, px
RUN_D = 0.3           # darkness that keeps the contiguous run alive (V <= ~131)
STATE_W_MIN = 1.7     # effective-width band for a state border segment, px
STATE_W_MAX = 4.3     # above this it's a river / lake / sea fill
MIN_STATE_LEN = 12    # segments shorter than this are letter strokes / debris, px
DENSITY_BOX = 21      # neighbourhood for the local ink-density text veto
DENSITY_MAX = 0.30    # short state-width segments above this density are lettering
DENSITY_VETO_LEN = 25 # ... but a segment at least this long is a border passing
                      # ... under a label, and the veto does not apply
RULED_MIN_LEN = 150   # the artwork's ruled frame lines: at least this long ...
RULED_STRAIGHT = 0.995  # ... with endpoint distance / path length at least this
LIGHT_BLUR = 5        # parchment detector: local mean V above LIGHT_V_MIN
LIGHT_V_MIN = 165
DEEP_DARK_DIST = 25   # a segment this far from any parchment is inside the sea /
                      # a lake fill: artwork (map frame, decoration), not a border —
                      # a river spine is never more than ~7 px from its light banks
CONT_MAX_LEN = 160    # total crawl budget for a thin continuation of a state strand
CONT_W_MIN = 1.2      # ... every crawled piece at least this wide (or a tiny stub)
CONT_STUB_LEN = 20    # ... pieces this short may be any width (letter fragments)
CONT_ALIGN = 0.55     # ... every piece collinear with the anchor tangent (|cos|)
HOP_MAX = 14.0        # a crawl may jump a broken stretch this long ...
HOP_OFFSET = 3.0      # ... staying this close to the anchor line ...
HOP_V_MAX = 150       # ... when faint ink (median V below this) spans the jump
TRACE_V_MAX = 150     # the faint-stroke tracer follows ink lighter than the
TRACE_MAX_STEPS = 60  # ... threshold but darker than this, up to this many px,
TRACE_ALIGN = 0.35    # ... never bending past this |cos| against the local tangent
TRACE_ROAD_MAX = 22   # ... and may cross road ribbon for at most this many steps
ROAD_V_MIN = 195      # road ribbon core: bright ...
ROAD_RB_MIN = 85      # ... and strongly orange (R - B); parchment stays below
ROAD_FRAC_MIN = 0.25  # a hop chord is a road crossing when at least this much of
                      # it is ribbon core and nearly all the rest is ink
CHAIN_STRAIGHT = 0.985  # ruled-chain veto: piece straightness and mutual alignment
CHAIN_MIN_PIECE = 40  # ... pieces at least this long ...
CHAIN_MIN_TOTAL = 350 # ... chaining into at least this much dead-straight line
CHAIN_OFFSET = 4.0    # ... within this perpendicular offset of the seed's line
ALPHA_MARGIN = 6      # skeleton this close to the alpha edge is the canvas cut, px
PAINT_RADIUS = 3      # magenta stroke half-width (disk radius), px
SKEL_STIPPLE_MIN = 40    # skeleton stage: drop isolated skeleton components under
                         # this many px (individual stipple flecks are 1-8 px, the
                         # real mesh is 150+); done pre-dilation so flecks can never
                         # merge into a surviving blob
STIPPLE_AREA_MIN = 400   # dilated-stage backstop: isolated components under this, px
STIPPLE_BLOB_AREA = 1500 # ... and up to here too when compact (a merged dot cluster)
STIPPLE_BLOB_FILL = 0.40 # ... area / bbox-area above which it's a blob, not a line

ADOPT_MAX_LEN = 40    # a rejected segment this short, joining two state strands at
ADOPT_W_MIN = 1.15    # ... both ends and at least this wide, is adopted (text gaps,
                      # ... junction stubs) so borders stay continuous

GLYPH_MAX_AREA = 4500     # component-level word removal: max ink px of one word blob
GLYPH_MAX_SIDE = 220      # ... max bbox side, px
GLYPH_MAX_EDT = 2.7       # ... letter strokes stay thinner than river ribbons
GLYPH_CLOSE = 5           # letters are welded into words before measuring elongation
GLYPH_MAX_ELONG = 14.0    # bbox diag^2 / area: words compact, long lines elongated
GLYPH_MIN_LINE_LEN = 40   # never glyph-remove a component whose skeleton runs this long


def _disk(radius: int) -> np.ndarray:
    y, x = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    return (x * x + y * y) <= radius * radius


def _ring(radius: int) -> np.ndarray:
    y, x = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    r2 = x * x + y * y
    return (r2 <= radius * radius) & (r2 >= (radius - 2) * (radius - 2))


def remove_isolated_words(ink: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Drop compact word-shaped components that touch no long linework.

    Letters are first closed into word blobs; a blob is lettering when it is small,
    thin-stroked and compact (low bbox-diagonal^2/area elongation). A component whose
    own skeleton contains a run longer than GLYPH_MIN_LINE_LEN is linework and immune,
    however word-like its bbox looks. Returns (cleaned ink, removed mask).
    """
    closed = ndi.binary_closing(ink, _disk(GLYPH_CLOSE // 2))
    lbl, n = ndi.label(closed, structure=np.ones((3, 3), int))
    edt = ndi.distance_transform_edt(ink)
    removed = np.zeros_like(ink)
    for i, sl in enumerate(ndi.find_objects(lbl), 1):
        if sl is None:
            continue
        blob = lbl[sl] == i
        comp = blob & ink[sl]
        area = int(comp.sum())
        if area == 0 or area > GLYPH_MAX_AREA:
            continue
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if max(h, w) > GLYPH_MAX_SIDE:
            continue
        if (h * h + w * w) / area > GLYPH_MAX_ELONG:
            continue
        if edt[sl][comp].max() > GLYPH_MAX_EDT:
            continue
        sk = skeletonize(comp)
        if int(sk.sum()) >= GLYPH_MIN_LINE_LEN and _longest_run(sk) >= GLYPH_MIN_LINE_LEN:
            continue
        removed[sl][comp] = True
    return ink & ~removed, removed


def _longest_run(sk: np.ndarray) -> int:
    """Length (px count) of the longest simple path segment in a small skeleton."""
    ncount = ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8),
                          mode="constant") - sk.astype(np.uint8)
    runs = sk & (ncount == 2)
    lbl, n = ndi.label(runs, structure=np.ones((3, 3), int))
    if n == 0:
        return int(sk.sum())
    return int(np.bincount(lbl.ravel())[1:].max())


def _order_path(px: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Order the pixels of one simple skeleton run (path or cycle) by walking it."""
    pset = set(px)
    nbrs = {}
    for (y, x) in px:
        nbrs[(y, x)] = [(y + dy, x + dx)
                        for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                        if (dy or dx) and (y + dy, x + dx) in pset]
    start = next((p for p in px if len(nbrs[p]) < 2), px[0])
    order, seen, cur = [start], {start}, start
    while True:
        nxt = [p for p in nbrs[cur] if p not in seen]
        if not nxt:
            break
        cur = nxt[0]
        order.append(cur)
        seen.add(cur)
    return order


def _effective_widths(path: list[tuple[int, int]], D: np.ndarray) -> np.ndarray:
    """Darkness integrated along the perpendicular at every pixel of an ordered path.

    A saturated 3 px stroke reads ~3.0 regardless of how anti-aliasing quantised it,
    and regardless of the skeleton riding a little off-centre. Each half-ray is
    integrated only over its CONTIGUOUS dark run (samples darker than RUN_D) starting
    at the skeleton: the walk stops at the first light sample, so the partner rail of
    a road — beyond the bright ribbon — and any letter beside the line never count,
    while the pixels of the stroke itself always do. Inside broad fills (lakes, sea)
    the run never breaks and the reading saturates high, classifying them 'wide'.
    """
    pts = np.asarray(path, dtype=np.float64)          # (n, 2) as (y, x)
    centre = D[pts[:, 0].astype(int), pts[:, 1].astype(int)]
    if len(pts) == 1:
        return centre * PERP_STEP
    ahead = np.minimum(np.arange(len(pts)) + 3, len(pts) - 1)
    behind = np.maximum(np.arange(len(pts)) - 3, 0)
    tang = pts[ahead] - pts[behind]
    norm = np.linalg.norm(tang, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    tang /= norm
    perp = np.stack([-tang[:, 1], tang[:, 0]], axis=1)
    offsets = np.arange(PERP_STEP, PERP_REACH + 1e-6, PERP_STEP)
    total = centre * PERP_STEP
    for sign in (1.0, -1.0):
        sy = pts[:, 0, None] + sign * perp[:, 0, None] * offsets[None, :]
        sx = pts[:, 1, None] + sign * perp[:, 1, None] * offsets[None, :]
        vals = ndi.map_coordinates(D, [sy.ravel(), sx.ravel()],
                                   order=1, mode="constant", cval=0.0)
        vals = vals.reshape(len(pts), -1)
        alive = np.cumprod(vals >= RUN_D, axis=1)      # 1 while the dark run holds
        total = total + (vals * alive).sum(axis=1) * PERP_STEP
    return total


class Segment:
    __slots__ = ("path", "width", "cls", "ends", "tangents")

    def __init__(self, path, width, cls, ends):
        self.path = path      # ordered [(y, x), ...]
        self.width = width    # median effective width, px
        self.cls = cls        # "state" | "thin" | "wide" | "dense" | "edge"
        self.ends = ends      # (node keys adjacent to path[0], to path[-1])
        k = min(5, len(path) - 1)
        t0 = np.array([path[0][0] - path[k][0], path[0][1] - path[k][1]], float)
        t1 = np.array([path[-1][0] - path[-1 - k][0], path[-1][1] - path[-1 - k][1]], float)
        self.tangents = tuple(t / n if (n := np.linalg.norm(t)) else t for t in (t0, t1))


def _segment_ends(path, node_at):
    """Node keys adjacent to each end of an ordered path (empty tuple = free end)."""
    out = []
    for p in (path[0], path[-1]):
        y, x = p
        keys = {node_at[yy, xx] for yy in range(y - 1, y + 2) for xx in range(x - 1, x + 2)
                if 0 <= yy < node_at.shape[0] and 0 <= xx < node_at.shape[1]
                and node_at[yy, xx] > 0}
        out.append(tuple(sorted(keys)))
    return tuple(out)


def classify_segments(ink: np.ndarray, alpha: np.ndarray, V: np.ndarray,
                      rgb: np.ndarray):
    """Skeletonize the ink and classify junction-to-junction segments by stroke width.

    A whole segment gets one verdict from the median of its per-pixel effective
    widths — a border whose reading wobbles around the threshold no longer flaps
    chunk by chunk, and a tapering river stays river out to its thin tail. Then two
    continuity passes: short rejected segments joining two state strands at both ends
    are adopted (lettering and road crossings cut borders into exactly such pieces),
    and nearby aligned state endpoints are bridged across free gaps.

    Returns (segments, node_at, masks) where masks maps class name -> skeleton mask.
    """
    sk = skeletonize(ink)
    D = np.clip((DARK_FLOOR - V.astype(np.float32)) / DARK_SPAN, 0.0, 1.0)
    density = ndi.uniform_filter(ink.astype(np.float32), DENSITY_BOX)
    alpha_edt = ndi.distance_transform_edt(alpha > 0)

    # Deep inside the sea / a lake fill, far from any parchment, linework is artwork
    # (the ruled map frame, decorations), never a border. Rivers hug their light
    # banks and are untouched by this.
    light = (ndi.uniform_filter(V.astype(np.float32), LIGHT_BLUR) > LIGHT_V_MIN) & (alpha > 0)
    dark_depth = ndi.distance_transform_edt(~light)

    ncount = ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8),
                          mode="constant") - sk.astype(np.uint8)
    runs = sk & (ncount == 2)
    nodes = sk & ~runs
    node_at, _ = ndi.label(nodes, structure=np.ones((3, 3), int))
    # A road crossing or letter weld shatters one junction into several node
    # components a pixel or two apart; merge them so adjacency sees ONE junction.
    clusters, _ = ndi.label(ndi.binary_dilation(nodes, _disk(2)),
                            structure=np.ones((3, 3), int))
    labels, first = np.unique(node_at.ravel(), return_index=True)
    cluster_of = np.zeros(int(labels.max()) + 1, np.int32)
    cluster_of[labels] = clusters.ravel()[first]
    node_at = np.where(node_at > 0, cluster_of[node_at], 0)
    lbl, n = ndi.label(runs, structure=np.ones((3, 3), int))

    segments = []
    for i, sl in enumerate(ndi.find_objects(lbl), 1):
        if sl is None:
            continue
        ys, xs = np.nonzero(lbl[sl] == i)
        px = [(y + sl[0].start, x + sl[1].start) for y, x in zip(ys, xs)]
        path = _order_path(px)
        widths = _effective_widths(path, D)
        cy = [p[0] for p in path]
        cx = [p[1] for p in path]
        w = float(np.median(widths))
        end_dist = float(np.hypot(path[0][0] - path[-1][0], path[0][1] - path[-1][1]))
        if float(np.median(alpha_edt[cy, cx])) < ALPHA_MARGIN:
            cls = "edge"                           # canvas cut: never mark
        elif float(np.median(dark_depth[cy, cx])) >= DEEP_DARK_DIST:
            cls = "edge"                           # frame/decoration in the open sea
        elif len(path) >= RULED_MIN_LEN and end_dist / len(path) >= RULED_STRAIGHT:
            cls = "edge"                           # ruled frame line: real borders wobble
        elif w >= STATE_W_MAX:
            cls = "wide"
        elif w < STATE_W_MIN:
            cls = "thin"
        elif len(path) < MIN_STATE_LEN:
            cls = "dense"
        elif (len(path) < DENSITY_VETO_LEN
              and float(np.median(density[cy, cx])) > DENSITY_MAX):
            cls = "dense"                          # a letter stroke, not a border
        else:
            cls = "state"
        segments.append(Segment(path, w, cls, _segment_ends(path, node_at)))

    road = (V >= ROAD_V_MIN) & (rgb[..., 0].astype(np.int16)
                                - rgb[..., 2].astype(np.int16) >= ROAD_RB_MIN)
    _veto_ruled_chains(segments)
    _adopt_connectors(segments)
    connectors = _grow_continuations(segments, V, road)
    _adopt_connectors(segments)
    masks = {c: np.zeros_like(sk) for c in ("state", "thin", "wide", "dense")}
    for seg in segments:
        if seg.cls in masks:
            m = masks[seg.cls]
            for (y, x) in seg.path:
                m[y, x] = True
    for hop in connectors:
        for (y, x) in hop:
            masks["state"][y, x] = True
    return segments, node_at, masks


def _adopt_connectors(segments):
    """Adopt rejected segments that keep the state-border network continuous.

    Two adoption rules, iterated to stability (capped) so a chain of small pieces —
    letter strokes and junction stubs welded onto a border by a label — heals piece
    by piece from both ends:

      connector -- a short thin/dense piece joining state strands at both ends
                   (whatever its angle: crossings produce perpendicular stubs);
      continuation -- a longer thin segment whose ends both CONTINUE a state strand
                   tangent-aligned (never a T-off): a border the artist drew thin,
                   e.g. where it squeezes past a place name. Width-floored so true
                   hairline province lines stay out.

    'wide' (river) and 'edge' segments are never adopted.
    """
    node_state = {}                                # node key -> outward state tangents

    def register(seg):
        for keys, tang in zip(seg.ends, seg.tangents):
            for k in keys:
                node_state.setdefault(k, []).append(tang)

    for seg in segments:
        if seg.cls == "state":
            register(seg)

    for _ in range(4):
        changed = 0
        for seg in segments:
            if seg.cls not in ("thin", "dense"):
                continue
            a, b = seg.ends
            if not a or not b or a == b:
                continue
            if (len(seg.path) <= ADOPT_MAX_LEN and seg.width >= ADOPT_W_MIN
                    and any(k in node_state for k in a)
                    and any(k in node_state for k in b)):
                seg.cls = "state"
                register(seg)
                changed += 1
        if not changed:
            break


def _seg_dir(seg) -> np.ndarray:
    v = np.array([seg.path[-1][0] - seg.path[0][0],
                  seg.path[-1][1] - seg.path[0][1]], float)
    n = np.linalg.norm(v)
    return v / n if n else v


def _veto_ruled_chains(segments):
    """Reclassify chains of dead-straight collinear state pieces as artwork.

    The map's ruled frame lines cross borders and coast hatching, which chops them
    into junction-to-junction pieces individually too short for the single-segment
    straightness veto. But the pieces stay perfectly collinear across those chops —
    while hand-drawn borders wobble — so: seed on any straight state piece, gather
    every straight state piece that is tangent-parallel AND lies on the seed's
    infinite line, and if the collected run is long enough, none of it is a border.
    """
    idx = [i for i, s in enumerate(segments)
           if s.cls == "state" and len(s.path) >= CHAIN_MIN_PIECE]
    straight = []
    for i in idx:
        s = segments[i]
        end_dist = float(np.hypot(s.path[0][0] - s.path[-1][0],
                                  s.path[0][1] - s.path[-1][1]))
        if end_dist / len(s.path) >= CHAIN_STRAIGHT:
            straight.append(i)
    done = set()
    for i in straight:
        if i in done:
            continue
        si = segments[i]
        d = _seg_dir(si)
        p0 = np.array(si.path[0], float)
        chain = [i]
        for j in straight:
            if j == i or j in done:
                continue
            sj = segments[j]
            if abs(float(np.dot(_seg_dir(sj), d))) < CHAIN_STRAIGHT:
                continue
            mid = np.array(sj.path[len(sj.path) // 2], float)
            off = mid - p0
            if abs(float(off[0] * d[1] - off[1] * d[0])) > CHAIN_OFFSET:
                continue
            chain.append(j)
        total = sum(len(segments[j].path) for j in chain)
        if len(chain) >= 2 and total >= CHAIN_MIN_TOTAL:
            for j in chain:
                segments[j].cls = "edge"
            done.update(chain)


def _grow_continuations(segments, V: np.ndarray, road: np.ndarray) -> list[tuple]:
    """Crawl outward from every state strand end along collinear thin pieces, and
    adopt the crawled path if it reconnects to another state strand.

    This is how a border the artist drew thin — squeezing past a place name, chopped
    into fragments by the letters welded onto it — gets healed: each fragment only
    ever touches state at ONE end, so both-ends adoption can never reach it. The
    crawl stays collinear with the anchor tangent (a province line T-ing off at an
    angle is never entered), every crawled piece must be border-plausible (wide
    enough, or a tiny stub), and nothing is adopted unless the far side lands on
    state again.

    Where the faint stroke drops below the ink threshold entirely, the skeleton
    breaks and no junction joins the fragments — the crawl then HOPS the break:
    a short forward jump onto another fragment's endpoint, allowed only when faint
    ink actually spans the jump. Committed hops are returned as (y0, x0, y1, x1)
    connector lines for the caller to paint.
    """
    incidence = {}
    for i, seg in enumerate(segments):
        for e, keys in enumerate(seg.ends):
            for k in keys:
                incidence.setdefault(k, []).append((i, e))

    # endpoint registry on a coarse grid, for gap hops
    CELL = 16

    def grid_key(p):
        return (int(p[0]) // CELL, int(p[1]) // CELL)

    epgrid = {}
    for i, seg in enumerate(segments):
        for e in (0, 1):
            p = seg.path[0] if e == 0 else seg.path[-1]
            epgrid.setdefault(grid_key(p), []).append((i, e, p))

    def endpoints_near(pos, radius):
        cy, cx = grid_key(pos)
        r = int(radius) // CELL + 1
        out = []
        for gy in range(cy - r, cy + r + 1):
            for gx in range(cx - r, cx + r + 1):
                out.extend(epgrid.get((gy, gx), ()))
        return out

    def gap_spans(p, q):
        """A hop is legitimate over faint ink (a label-broken stroke) OR over a road
        ribbon (a border interrupted by a crossing road, whose bright core would
        fail any darkness test)."""
        n = max(int(np.hypot(q[0] - p[0], q[1] - p[1])) * 2, 2)
        ys = np.linspace(p[0], q[0], n).round().astype(int)
        xs = np.linspace(p[1], q[1], n).round().astype(int)
        if float(np.median(V[ys, xs])) <= HOP_V_MAX:
            return True
        on_road = road[ys, xs]
        inkish = V[ys, xs] <= HOP_V_MAX
        return (float(on_road.mean()) >= ROAD_FRAC_MIN
                and float((on_road | inkish).mean()) >= 0.8)

    def hop_candidates(pos, tang, seen):
        cands = []
        for (j, je, q) in endpoints_near(pos, HOP_MAX):
            if j in seen:
                continue
            d = np.array([q[0] - pos[0], q[1] - pos[1]], float)
            dist = float(np.linalg.norm(d))
            if not (2.0 <= dist <= HOP_MAX):
                continue
            fwd = float(np.dot(d, tang))
            if fwd < 2.0:
                continue                              # not ahead of the strand end
            if abs(float(d[0] * tang[1] - d[1] * tang[0])) > HOP_OFFSET:
                continue
            if not gap_spans(pos, q):
                continue
            cands.append((dist, j, je, tuple(int(v) for v in q)))
        cands.sort()
        return cands

    seg_at = np.zeros(V.shape, np.int32)             # skeleton px -> segment id + 1
    for i, seg in enumerate(segments):
        for (y, x) in seg.path:
            seg_at[y, x] = i + 1

    def line_px(p, q):
        n = max(int(np.hypot(q[0] - p[0], q[1] - p[1])) * 2, 2)
        ys = np.linspace(p[0], q[0], n).round().astype(int)
        xs = np.linspace(p[1], q[1], n).round().astype(int)
        return tuple(zip(ys.tolist(), xs.tolist()))

    def faint_trace(pos, dirv, skip):
        """Follow a fainter-than-threshold stroke from a dead end until it lands on
        another segment's pixel; returns (traced px, segment id) or None. Steered
        greedily to the darkest of five forward directions, momentum-smoothed, and
        stopped when nothing forward is darker than TRACE_V_MAX."""
        p = np.array(pos, float)
        d = np.array(dirv, float)
        if float(np.linalg.norm(d)) < 0.5:
            return None                              # no usable direction (tiny stub)
        h, w = V.shape
        path = []
        road_steps = 0
        for step in range(TRACE_MAX_STEPS):
            best = None
            for ang in (-0.6, -0.3, 0.0, 0.3, 0.6):
                c, s = np.cos(ang), np.sin(ang)
                nd = np.array([d[0] * c - d[1] * s, d[0] * s + d[1] * c])
                q = p + nd
                iy, ix = int(round(q[0])), int(round(q[1]))
                if not (1 <= iy < h - 1 and 1 <= ix < w - 1):
                    continue
                v = float(V[iy, ix])
                if road[iy, ix]:
                    v = min(v, float(TRACE_V_MAX))   # ribbon core is crossable ...
                if v <= TRACE_V_MAX and (best is None or v < best[0]):
                    best = (v, nd, q, iy, ix)
            if best is None:
                return None
            if road[best[3], best[4]]:
                road_steps += 1                      # ... but never for long
                if road_steps > TRACE_ROAD_MAX:
                    return None
            _, nd, p, iy, ix = best
            d = d * 0.6 + nd * 0.4
            n = float(np.linalg.norm(d))
            if n < 1e-6:
                return None
            d /= n
            path.append((iy, ix))
            if step >= 3:
                win = seg_at[iy - 1:iy + 2, ix - 1:ix + 2]
                hit = win[win > 0]
                for hid in hit:
                    j = int(hid) - 1
                    if j not in skip:
                        return path, j
        return None

    def crawl(anchor_i, tang, start_keys, start_pos):
        # BFS over (cum length, position, local tangent, node keys, trail, hops)
        frontier = [(0.0, tuple(start_pos), tuple(tang), tuple(start_keys), (), ())]
        seen_segs = {anchor_i}
        while frontier:
            frontier.sort(key=lambda t: t[0])
            cum, pos, ltang, keys, trail, hops = frontier.pop(0)
            ltang = np.array(ltang)
            reachable = [(j, je, None) for k in keys for (j, je) in incidence.get(k, ())]
            reachable += [(j, je, line_px(pos, q)) for (_, j, je, q)
                          in hop_candidates(pos, ltang, seen_segs)]
            advanced = False
            for (j, je, hop) in reachable:
                seg = segments[j]
                if j in seen_segs:
                    continue
                new_hops = hops + ((hop,) if hop else ())
                if seg.cls == "state" and (trail or hop):
                    return trail, new_hops               # reconnected: commit
                if seg.cls not in ("thin", "dense"):
                    continue
                if len(seg.path) > CONT_MAX_LEN or cum + len(seg.path) > CONT_MAX_LEN:
                    continue
                if seg.width < CONT_W_MIN and len(seg.path) > CONT_STUB_LEN:
                    continue
                if (len(seg.path) > 6
                        and abs(float(np.dot(seg.tangents[je], tang))) < CONT_ALIGN):
                    continue                          # tiny stubs have no real tangent
                if (len(seg.path) > CONT_STUB_LEN
                        and abs(float(np.dot(_seg_dir(seg), tang))) < CONT_ALIGN):
                    continue
                seen_segs.add(j)
                advanced = True
                far_keys = seg.ends[1 - je]
                far_pos = seg.path[-1] if je == 0 else seg.path[0]
                out_tang = seg.tangents[1 - je]
                gap = len(hop) / 2.0 if hop else 0.0
                frontier.append((cum + len(seg.path) + gap, tuple(far_pos),
                                 tuple(out_tang), tuple(far_keys), trail + (j,), new_hops))
            state_nearby = any(segments[j].cls == "state"
                               for k in keys for (j, _) in incidence.get(k, ())
                               if j not in seen_segs)
            if not advanced and not state_nearby and cum + 4 <= CONT_MAX_LEN:
                # true dead end: follow the faint stroke itself
                traced = faint_trace(pos, ltang, seen_segs)
                if traced is not None:
                    tpath, j = traced
                    seg = segments[j]
                    if abs(float(np.dot(ltang, tang))) >= TRACE_ALIGN:
                        if seg.cls == "state":
                            return trail, hops + (tuple(tpath),)
                        if (seg.cls in ("thin", "dense")
                                and len(seg.path) <= CONT_MAX_LEN
                                and cum + len(tpath) + len(seg.path) <= CONT_MAX_LEN
                                and (seg.width >= CONT_W_MIN
                                     or len(seg.path) <= CONT_STUB_LEN)):
                            seen_segs.add(j)
                            landing = np.array(tpath[-1], float)
                            d0 = np.hypot(*(np.array(seg.path[0], float) - landing))
                            d1 = np.hypot(*(np.array(seg.path[-1], float) - landing))
                            je = 0 if d0 <= d1 else 1
                            far_keys = seg.ends[1 - je]
                            far_pos = seg.path[-1] if je == 0 else seg.path[0]
                            out_tang = seg.tangents[1 - je]
                            frontier.append((cum + len(tpath) + len(seg.path),
                                             tuple(far_pos), tuple(out_tang),
                                             tuple(far_keys), trail + (j,),
                                             hops + (tuple(tpath),)))
        return None, ()

    connectors = []
    for _ in range(2):
        adopted = 0
        for i, seg in enumerate(segments):
            if seg.cls != "state":
                continue
            for e in (0, 1):
                pos = seg.path[0] if e == 0 else seg.path[-1]
                trail, hops = crawl(i, seg.tangents[e], seg.ends[e], pos)
                if trail is None and not hops:
                    continue
                for j in trail:
                    segments[j].cls = "state"
                connectors.extend(hops)
                adopted += len(trail) + len(hops)
        if not adopted:
            break
    return connectors




def strip_skeleton_flecks(state: np.ndarray) -> tuple[np.ndarray, int]:
    """Remove isolated skeleton components too short to be a border, pre-dilation.

    On the 1-px skeleton a real border link is a connected path wired into the mesh
    (150+ px), while shore beading and mottled-patch dots are separate flecks of a
    few px each. Cutting them here — before the stroke is dilated — stops neighbouring
    flecks from fusing into a blob that would survive the dilated-stage area filter.
    """
    lbl, n = ndi.label(state, structure=np.ones((3, 3), int))
    if n == 0:
        return state, 0
    areas = np.bincount(lbl.ravel())
    drop = areas < SKEL_STIPPLE_MIN
    drop[0] = False
    removed = int(areas[drop].sum())
    if removed:
        state = state & ~drop[lbl]
    return state, removed


def strip_stipple(state: np.ndarray) -> tuple[np.ndarray, int]:
    """Drop isolated magenta components too small to be real borders.

    Real state borders wire into the connected mesh, so a genuine border is never a
    small island of its own; what IS a small island is stipple — the scalloped
    shore-ink beading and the dotted streaks over mottled interior patches (marsh,
    shadow), each fleck a separate tiny component. Removed in two tiers: everything
    under STIPPLE_AREA_MIN, plus larger-but-compact blobs up to STIPPLE_BLOB_AREA
    where several flecks merged (a real border of that area is a thin line — low
    bbox fill — while a dot cluster is roundish). The mesh and every sizeable
    regional sub-network sit far above both and are untouched. Runs before overrides
    so a hand-painted line is never stripped.
    """
    lbl, n = ndi.label(state, structure=np.ones((3, 3), int))
    if n == 0:
        return state, 0
    areas = np.bincount(lbl.ravel())
    drop = np.zeros(areas.shape[0], bool)
    drop[areas < STIPPLE_AREA_MIN] = True
    for i in np.nonzero((areas >= STIPPLE_AREA_MIN) & (areas < STIPPLE_BLOB_AREA))[0]:
        ys, xs = np.nonzero(lbl == i)
        bbox = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
        if areas[i] / bbox > STIPPLE_BLOB_FILL:
            drop[i] = True
    drop[0] = False
    removed = int(areas[drop].sum())
    if removed:
        state = state & ~drop[lbl]
    return state, removed


def apply_overrides(paint: np.ndarray) -> np.ndarray:
    """Fold the hand-authored patch file into the final (dilated) paint mask.

    Applied last, after stipple stripping, so a ``paint`` line is never stripped and
    an ``erase`` box always wins. Paint polylines are drawn at the full stroke width;
    erase boxes are cleared afterward. See the OVERRIDES docstring above.
    """
    if not OVERRIDES.exists():
        return paint
    data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    paint = paint.copy()
    lines = np.zeros_like(paint)
    for line in data.get("paint", ()):
        pts = [(float(x), float(y)) for x, y in line]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(int(np.hypot(y1 - y0, x1 - x0)) * 2, 2)
            ys = np.linspace(y0, y1, n).round().astype(int)
            xs = np.linspace(x0, x1, n).round().astype(int)
            lines[ys, xs] = True
    if lines.any():
        paint |= ndi.binary_dilation(lines, _disk(PAINT_RADIUS))
    for box in data.get("erase", ()):
        x, y, w, h = (int(v) for v in box)
        paint[y:y + h, x:x + w] = False
    print(f"overrides: {len(data.get('paint', ()))} paint lines, "
          f"{len(data.get('erase', ()))} erase boxes")
    return paint


def report_loose_ends(segments, state: np.ndarray) -> list[tuple[int, int]]:
    """State strand ends that nothing continues — the genuine break sites.

    An end is NOT loose when a state/wide/edge segment shares its junction (the
    border, a river or the canvas cut carries on), or when any OTHER state strand
    lies within healing distance (the paint stroke's dilation plus the extractor's
    own closes gaps that small on its own). What survives is a border that stops
    against nothing: written to a QA file for eyeballing; genuine breaks become
    'paint' overrides.
    """
    HEAL = 6
    incidence = {}
    for i, seg in enumerate(segments):
        for keys in seg.ends:
            for k in keys:
                incidence.setdefault(k, []).append(i)
    strand_lbl, _ = ndi.label(state, structure=np.ones((3, 3), int))
    h, w = state.shape
    loose = []
    for i, seg in enumerate(segments):
        if seg.cls != "state":
            continue
        for e in (0, 1):
            keys = seg.ends[e]
            p = seg.path[0] if e == 0 else seg.path[-1]
            continued = any(segments[j].cls in ("state", "wide", "edge")
                            for k in keys for j in incidence.get(k, ()) if j != i)
            if continued:
                continue
            y, x = int(p[0]), int(p[1])
            own = strand_lbl[y, x]
            win = strand_lbl[max(0, y - HEAL):y + HEAL + 1, max(0, x - HEAL):x + HEAL + 1]
            near = set(np.unique(win)) - {0, own}
            if near:
                continue                            # another strand heals under paint
            loose.append((x, y))
    return loose


def main():
    ap = argparse.ArgumentParser(description="Mark state-region borders in magenta.")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC, help="pristine source PNG")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="marked PNG to write")
    ap.add_argument("--preview", action="store_true",
                    help="write only the class-coloured overlay, do not mark")
    ap.add_argument("--preview-width", action="store_true",
                    help="write only a width-band overlay for threshold calibration")
    args = ap.parse_args()

    im = Image.open(args.src)
    rgba = np.asarray(im.convert("RGBA")).copy()
    rgb = rgba[..., :3]
    alpha = rgba[..., 3]
    V = rgb.max(axis=2)
    ink = (V < INK_V) & (alpha > 0)
    ink, words = remove_isolated_words(ink)
    print(f"ink px {int(ink.sum()):,}  removed word px {int(words.sum()):,}")

    segments, node_at, masks = classify_segments(ink, alpha, V, rgb)
    state, thin, wide, dense = (masks[c] for c in ("state", "thin", "wide", "dense"))
    # Two-stage stipple removal: cut skeleton flecks first (so they can't fuse into
    # blobs under dilation), then a dilated-stage area backstop for anything left.
    state, fleck_px = strip_skeleton_flecks(state)
    paint = ndi.binary_dilation(state, _disk(PAINT_RADIUS))
    paint, stipple_px = strip_stipple(paint)
    print(f"stripped stipple: {fleck_px:,} skeleton px + {stipple_px:,} dilated px")
    paint = apply_overrides(paint)
    loose = report_loose_ends(segments, paint)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    (QA_DIR / "qa_state_border_loose_ends.json").write_text(
        json.dumps(loose), encoding="utf-8")
    print(f"painted px {int(paint.sum()):,}  thin {int(thin.sum()):,}  "
          f"wide {int(wide.sum()):,}  text-dense {int(dense.sum()):,}  "
          f"loose ends {len(loose)}")
    ws = np.array([s.width for s in segments])
    ls = np.array([len(s.path) for s in segments])
    print("segment effective-width histogram (weighted by length):")
    for lo in np.arange(0.5, 7.0, 0.5):
        m = (ws >= lo) & (ws < lo + 0.5)
        print(f"  {lo:.1f}-{lo + 0.5:.1f}: {int(ls[m].sum()):,}")

    QA_DIR.mkdir(parents=True, exist_ok=True)
    if args.preview_width:
        # width bands: <1.2 dk-green, <1.4 green, <1.55 yellow-green, <1.8 yellow,
        # <2.2 orange, <3.0 red, <4.3 magenta, else blue (river)
        bands = [(1.2, (0, 100, 0)), (1.4, (0, 200, 0)), (1.55, (150, 220, 0)),
                 (1.8, (255, 220, 0)), (2.2, (255, 140, 0)), (3.0, (255, 0, 0)),
                 (4.3, (255, 0, 255)), (99.0, (0, 90, 255))]
        ov = rgb.copy()
        band_masks = [np.zeros_like(ink) for _ in bands]
        for seg in segments:
            b = next(i for i, (lim, _) in enumerate(bands) if seg.width < lim)
            m = band_masks[b]
            for (y, x) in seg.path:
                m[y, x] = True
        for (lim, col), m in zip(bands, band_masks):
            ov[ndi.binary_dilation(m, _disk(1))] = col
        out = QA_DIR / "qa_mark_state_borders_widths.png"
        Image.fromarray(ov).save(out)
        print("wrote", out)
        return
    if args.preview:
        ov = rgb.copy()
        ov[ndi.binary_dilation(words, _disk(1))] = [255, 160, 0]
        ov[ndi.binary_dilation(thin, _disk(1))] = [0, 160, 0]
        ov[ndi.binary_dilation(wide, _disk(1))] = [0, 90, 255]
        ov[ndi.binary_dilation(dense, _disk(1))] = [255, 220, 0]
        ov[paint] = list(MAGENTA)
        ring = np.zeros(paint.shape, bool)
        for (x, y) in loose:
            ring[max(0, y - 7):y + 8, max(0, x - 7):x + 8] |= _ring(7)[
                max(0, 7 - y):15 - max(0, y + 8 - paint.shape[0]),
                max(0, 7 - x):15 - max(0, x + 8 - paint.shape[1])]
        ov[ring] = [0, 255, 255]
        out = QA_DIR / "qa_mark_state_borders_preview.png"
        Image.fromarray(ov).save(out)
        print("wrote", out)
        return

    rgba[..., :3][paint] = MAGENTA
    Image.fromarray(rgba).save(args.out)
    print("wrote", args.out)
    qa = Image.fromarray(rgba[..., :3])
    qa.thumbnail((2000, 2000))
    qa.save(QA_DIR / "qa_mark_state_borders.png")
    print("wrote", QA_DIR / "qa_mark_state_borders.png")


if __name__ == "__main__":
    main()
