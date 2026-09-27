"""Pure core of the adjacency pipeline (board #5563, canal junctions #5744).

Hand-drawn yellow lines (each joining two provinces that do not touch: a strait,
an island link, a tunnel) -> one :class:`Line` per connected component -> two
province colours read under its endpoints -> a :class:`Crossing`. A hand-authored
worksheet (``tools/config/adjacency_worksheet.json``) then types each crossing and
:func:`emit_csv` writes ``map_data/adjacencies.csv``.

A canal is drawn as a 4-arm "+"/"X" junction instead of a plain 2-endpoint line:
one glyph combining the sea-to-sea crossing (still one ``canal_*`` row in the
CSV, unchanged) with the two flanking land provinces (a :class:`Crossing`'s
``land_pair``, consumed only by ``common/strait_definitions`` — board #5744).
Junction topology reuses ``river_network``'s topology-aware skeleton primitives
(the same diagonal-redundancy handling that keeps a river T/Y junction from
reading as a spurious triangle) rather than a second implementation.

Everything here is a pure function of arrays / plain data — no I/O — so it is
deterministic and self-checkable (``run_fixture.py --check``).

Coordinates: every point here is in canvas (top-origin) ``(x, y)``. The engine
CSV's ``y`` is **bottom-origin**: :func:`emit_csv` writes ``H - 1 - y``.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from worldgen import river_network as rn

Color = tuple[int, int, int]
Point = tuple[int, int]

#: The exact paint colour of the source layer (no tolerance).
YELLOW_RGB = (255, 255, 0)
#: A window around an endpoint must have one province holding at least this share.
DOMINANT_FRACTION = 0.65
#: Endpoint window radius (1 = 3x3): provinces can be narrow, a wider window straddles them.
ENDPOINT_RADIUS = 1
#: Skeleton pixels allowed off the endpoint-to-endpoint path (spur tolerance).
SPUR_PX = 4
#: Worksheet-to-line endpoint match tolerance (px, Chebyshev).
MATCH_TOL = 4

ADJACENCIES_HEADER = (
    "From;To;Type;Through;start_x;start_y;stop_x;stop_y;adjacency_rule_name;Comment"
)


def color_code(c: Color) -> int:
    return (c[0] << 16) | (c[1] << 8) | c[2]


def code_color(code: int) -> Color:
    return ((code >> 16) & 0xFF, (code >> 8) & 0xFF, code & 0xFF)


def color_token(c: Color) -> str:
    return "x%02X%02X%02X" % c


@dataclass(frozen=True)
class Line:
    """One drawn line: its two endpoints (canvas coords) or why it has none.

    ``leaves`` is set instead of ``a``/``b`` for a 4-arm "+"/"X" canal junction
    (mutually exclusive): the 4 leaf endpoints, unpaired — :func:`classify_lines`
    decides the sea/land split by resolved province kind."""

    pixels: int
    centroid: Point
    a: Point | None
    b: Point | None
    reason: str = ""  # "" when ``a``/``b`` (or ``leaves``) are valid, else "bad-shape: ..."
    leaves: tuple[Point, Point, Point, Point] | None = None


@dataclass(frozen=True)
class Crossing:
    """A resolved line: ``start`` sits in the From province, ``stop`` in To.

    ``land_pair``/``land_points`` are set only for a crossing resolved from a
    canal junction mark (board #5744): the two flanking land provinces' colours
    and canvas points (same order), sorted by colour code for determinism.
    Neither is ever emitted to ``adjacencies.csv`` — ``land_pair`` is consumed by
    the ``common/strait_definitions`` emitter; ``land_points`` lets a worksheet
    row keep its identity across a canal's redraw from a plain line to a
    junction (its ``a``/``b`` are the line's *original* endpoints, which the "+"
    convention keeps as the land leaves — see :func:`sync_worksheet`)."""

    from_color: Color
    to_color: Color
    start: Point
    stop: Point
    pixels: int
    centroid: Point
    land_pair: tuple[Color, Color] | None = None
    land_points: tuple[Point, Point] | None = None


@dataclass(frozen=True)
class Skipped:
    centroid: Point
    reason: str
    a: Point | None = None
    b: Point | None = None


# ---------------------------------------------------------------------------
# Line extraction
# ---------------------------------------------------------------------------

def _label_wrap(mask: np.ndarray, wrap_x: bool) -> tuple[np.ndarray, int]:
    """8-connected labels of ``mask``, x-seam components merged when ``wrap_x``."""
    from skimage import measure

    labels = measure.label(mask, connectivity=2, background=0).astype(np.int64)
    n = int(labels.max())
    if wrap_x and labels.shape[1] > 1 and n:
        parent = list(range(n + 1))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        h = labels.shape[0]
        left, right = labels[:, 0], labels[:, -1]
        for y in range(h):
            if not left[y]:
                continue
            for dy in (-1, 0, 1):
                yy = y + dy
                if 0 <= yy < h and right[yy]:
                    ra, rb = find(int(left[y])), find(int(right[yy]))
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
        remap = np.array([find(i) for i in range(n + 1)], dtype=np.int64)
        labels = remap[labels]
    return labels, n


def _neighbors8(p: Point, pts: set[Point]):
    x, y = p
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                q = (x + dx, y + dy)
                if q in pts:
                    yield q


def _bfs(start: Point, pts: set[Point]) -> tuple[dict[Point, int], dict[Point, Point]]:
    dist = {start: 0}
    prev: dict[Point, Point] = {}
    dq = deque([start])
    while dq:
        p = dq.popleft()
        for q in sorted(_neighbors8(p, pts)):
            if q not in dist:
                dist[q] = dist[p] + 1
                prev[q] = p
                dq.append(q)
    return dist, prev


def _junction_clusters(pts_yx: set[tuple[int, int]], S: set[tuple[int, int]],
                       deg: dict[tuple[int, int], int], h: int, w: int
                       ) -> list[set[tuple[int, int]]]:
    """Group ``pts_yx`` (the degree>=3 pixels of ``S``) into maximal clusters
    representing one physical intersection each. A hand-drawn "+"/"X" junction's
    plateau is not always directly 8-connected among its own high-degree pixels —
    it can skeletonize with a short (<=``SPUR_PX``) degree-2 gap between two
    branch pixels (measured: board #5744) — so two junction pixels joined by a
    short chain are the same intersection, collapsed to one node, same as two
    directly-adjacent ones."""
    nodes = pts_yx | {p for p, d in deg.items() if d == 1}
    edges = rn._trace_edges(S, deg, nodes, h, w, False)
    parent = {p: p for p in pts_yx}

    def find(p: tuple[int, int]) -> tuple[int, int]:
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    for e in edges:
        if e.a in pts_yx and e.b in pts_yx and e.inner_len <= SPUR_PX:
            ra, rb = find(e.a), find(e.b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    groups: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for p in pts_yx:
        groups.setdefault(find(p), set()).add(p)
    return list(groups.values())


def _try_junction(pts: set[Point], n_px: int, centroid: Point, to_canvas) -> Line:
    """A component whose 2-endpoint BFS-diameter path leaves pixels unaccounted
    for: check whether it is a deliberate 4-arm "+"/"X" canal junction (board
    #5744) rather than a genuine bad shape. Requires exactly one junction (a
    connected cluster of degree>=3 skeleton pixels, collapsed to one node — see
    :func:`_junction_clusters`) and exactly 4 leaves. No arm-length cap: measured
    and confirmed with Chris that a mark may legitimately carry one arm much
    longer than the others (``canal_isles_of_doom``) — the sea/land kind-pairing
    check in :func:`classify_lines` is the real safety net, not geometry."""
    h = max(y for _, y in pts) + 2
    w = max(x for x, _ in pts) + 2
    S = {(y, x) for x, y in pts}
    deg = rn._degree_map(S, h, w, False)
    leaves_yx = [p for p, d in deg.items() if d == 1]
    junction_px = {p for p, d in deg.items() if d >= 3}
    if not junction_px:
        return Line(n_px, centroid, None, None,
                    "bad-shape: no junction pixel found (loop or malformed shape)")
    clusters = _junction_clusters(junction_px, S, deg, h, w)
    if len(clusters) != 1:
        return Line(n_px, centroid, None, None,
                    f"bad-shape: {len(clusters)} separate junctions found in one "
                    "line (need exactly 1 for a '+'/'X' canal mark)")
    if len(leaves_yx) != 4:
        return Line(n_px, centroid, None, None,
                    f"bad-shape: {len(leaves_yx)} leaves found (need exactly 4 "
                    "for a '+'/'X' canal mark) - marks drawn too close together "
                    "can't be told apart; space them out")
    leaves = tuple(sorted(to_canvas(x, y) for y, x in leaves_yx))
    return Line(n_px, centroid, None, None, "", leaves=leaves)


def _line_from_pixels(xs: np.ndarray, ys: np.ndarray, width: int, wrap_x: bool) -> Line:
    """Skeletonize one component and pick its two endpoints (or report bad-shape)."""
    from skimage.morphology import skeletonize

    n_px = int(xs.size)
    shift = 0
    if wrap_x and int(xs.min()) == 0 and int(xs.max()) == width - 1:
        shift = width // 2  # component crosses the seam: rotate it away from the edge
        xs = (xs + shift) % width
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    crop = np.zeros((y1 - y0 + 3, x1 - x0 + 3), dtype=bool)
    crop[ys - y0 + 1, xs - x0 + 1] = True
    sk = skeletonize(crop)
    ky, kx = np.nonzero(sk)

    def to_canvas(px: int, py: int) -> Point:
        return ((px + x0 - 1 - shift) % width, py + y0 - 1)

    pts = {(int(x), int(y)) for x, y in zip(kx, ky)}
    cx = int(round(float(np.mean((xs - shift) % width))))
    cy = int(round(float(ys.mean())))
    if len(pts) < 2:
        return Line(n_px, (cx, cy), None, None, "bad-shape: too short (dot)")
    seed = min(pts)
    d0, _ = _bfs(seed, pts)
    far = max(sorted(d0), key=lambda p: d0[p])
    d1, prev = _bfs(far, pts)
    if len(d1) != len(pts):
        return Line(n_px, (cx, cy), None, None, "bad-shape: skeleton is disconnected")
    other = max(sorted(d1), key=lambda p: d1[p])
    ends = sorted([far, other])
    path = {other}
    cur = other
    while cur != far:
        cur = prev[cur]
        path.add(cur)
    off = len(pts) - len(path)
    if off > SPUR_PX:
        return _try_junction(pts, n_px, (cx, cy), to_canvas)
    a, b = to_canvas(*ends[0]), to_canvas(*ends[1])
    if a == b:
        return Line(n_px, (cx, cy), None, None, "bad-shape: endpoints coincide")
    return Line(n_px, (cx, cy), a, b)


def extract_lines(mask: np.ndarray, wrap_x: bool = True) -> list[Line]:
    """One :class:`Line` per connected component of ``mask``, in a total order
    (by centroid, then pixel count) so the numbering is reproducible."""
    labels, n = _label_wrap(mask, wrap_x)
    width = mask.shape[1]
    lines: list[Line] = []
    if not n:
        return lines
    ys_all, xs_all = np.nonzero(labels)
    lab = labels[ys_all, xs_all]
    order = np.argsort(lab, kind="stable")
    lab_s = lab[order]
    bounds = np.flatnonzero(np.diff(lab_s)) + 1
    for sel in np.split(order, bounds):
        lines.append(_line_from_pixels(xs_all[sel], ys_all[sel], width, wrap_x))
    lines.sort(key=lambda ln: (ln.centroid[1], ln.centroid[0], ln.pixels))
    return lines


# ---------------------------------------------------------------------------
# Endpoint -> province
# ---------------------------------------------------------------------------

def resolve_endpoint(code_map: np.ndarray, p: Point, radius: int = ENDPOINT_RADIUS, wrap_x: bool = True
                     ) -> tuple[Color | None, list[Color]]:
    """The dominant province colour in a ``radius`` window around ``p``.

    Returns ``(colour, [])`` when one colour holds >= DOMINANT_FRACTION of the
    window, else ``(None, candidates)`` (most frequent first) — a tip on a border
    is reported, never silently picked."""
    h, w = code_map.shape
    x, y = p
    ys = np.arange(max(0, y - radius), min(h, y + radius + 1))
    xs = np.arange(x - radius, x + radius + 1)
    if wrap_x:
        xs = xs % w
    else:
        xs = xs[(xs >= 0) & (xs < w)]
    win = code_map[np.ix_(ys, xs)].ravel()
    vals, counts = np.unique(win, return_counts=True)
    order = sorted(range(len(vals)), key=lambda i: (-int(counts[i]), int(vals[i])))
    ranked = [code_color(int(vals[i])) for i in order]
    if counts[order[0]] / win.size >= DOMINANT_FRACTION:
        return ranked[0], []
    return None, ranked


def _cheb(p: Point, q: Point, width: int | None) -> int:
    dx = abs(p[0] - q[0])
    if width:
        dx = min(dx, width - dx)
    return max(dx, abs(p[1] - q[1]))


def _match_ends(row_a: Point, row_b: Point, p: Point, q: Point, tol: int, width: int | None
                ) -> int:
    """0 = no match, 1 = a~p & b~q, 2 = a~q & b~p."""
    if _cheb(row_a, p, width) <= tol and _cheb(row_b, q, width) <= tol:
        return 1
    if _cheb(row_a, q, width) <= tol and _cheb(row_b, p, width) <= tol:
        return 2
    return 0


def _classify_junction(ln: Line, code_map: np.ndarray, kinds: dict[Color, str],
                       wrap_x: bool
                       ) -> tuple[Point, Color, Point, Color, tuple[Color, Color],
                                 tuple[Point, Point]] | Skipped:
    """Resolve a 4-leaf canal-junction :class:`Line` (board #5744) to its sea pair
    (point, colour for each of the two sea leaves — the touching/lake/orientation
    checks in :func:`classify_lines` still apply to these, unchanged) plus its
    land pair (colours only, never emitted to the CSV).

    Tries every way to split the 4 leaves into 2 unordered pairs and keeps the
    one pairing where one pair resolves to (sea, sea) and the other to
    (land, land), with distinct colours within each pair (a pair resolving to one
    province on both sides — e.g. an unsplit isthmus — is not valid). Zero or
    more than one qualifying pairing is reported, never guessed."""
    leaves = ln.leaves
    resolved: list[tuple[Point, Color | None, list[Color]]] = []
    for pt in leaves:
        c, cand = resolve_endpoint(code_map, pt, wrap_x=wrap_x)
        resolved.append((pt, c, cand))
    bad = [i for i, (_, c, _) in enumerate(resolved) if c is None]
    if bad:
        names = ", ".join(f"leaf{i}=" + "/".join(color_token(c) for c in resolved[i][2][:3])
                          for i in bad)
        return Skipped(ln.centroid, f"junction: ambiguous endpoint ({names}); pin it in the "
                       "worksheet with land_a_color/land_b_color")
    pairings = (((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2)))
    valid = []
    for (i0, i1), (j0, j1) in pairings:
        p0, c0, _ = resolved[i0]
        p1, c1, _ = resolved[i1]
        p2, c2, _ = resolved[j0]
        p3, c3, _ = resolved[j1]
        if c0 == c1 or c2 == c3:
            continue
        k01 = (kinds.get(c0), kinds.get(c1))
        k23 = (kinds.get(c2), kinds.get(c3))
        if k01 == ("sea", "sea") and k23 == ("land", "land"):
            valid.append(((p0, c0), (p1, c1), (c2, c3), (p2, p3)))
        elif k23 == ("sea", "sea") and k01 == ("land", "land"):
            valid.append(((p2, c2), (p3, c3), (c0, c1), (p0, p1)))
    if not valid:
        return Skipped(ln.centroid, "junction: no leaf pairing resolves to one sea/sea pair "
                       "and one land/land pair")
    if len(valid) > 1:
        return Skipped(ln.centroid, f"junction: {len(valid)} different leaf pairings all "
                       "resolve validly - ambiguous")
    (sea_pa, sea_ca), (sea_pb, sea_cb), land_pair, land_points = valid[0]
    if color_code(land_pair[1]) < color_code(land_pair[0]):
        land_pair = (land_pair[1], land_pair[0])
        land_points = (land_points[1], land_points[0])
    return sea_pa, sea_ca, sea_pb, sea_cb, land_pair, land_points


def classify_lines(lines: list[Line], code_map: np.ndarray, kinds: dict[Color, str],
                   touching: set[frozenset] | None = None, pins=(), wrap_x: bool = True,
                   tol: int = MATCH_TOL) -> tuple[list[Crossing], list[Skipped]]:
    """Resolve every line to a :class:`Crossing` or a :class:`Skipped` with a reason.

    ``pins`` are worksheet rows (anything with ``a``/``b`` points and optional
    ``a_color``/``b_color``) that fix an ambiguous endpoint's colour by hand."""
    width = code_map.shape[1] if wrap_x else None
    crossings: list[Crossing] = []
    skipped: list[Skipped] = []
    for ln in lines:
        land_pair: tuple[Color, Color] | None = None
        land_points: tuple[Point, Point] | None = None
        if ln.leaves is not None:
            result = _classify_junction(ln, code_map, kinds, wrap_x)
            if isinstance(result, Skipped):
                skipped.append(result)
                continue
            pa, ca, pb, cb, land_pair, land_points = result
        elif ln.a is None or ln.b is None:
            skipped.append(Skipped(ln.centroid, ln.reason))
            continue
        else:
            pa, pb = ln.a, ln.b
            cols: list[Color | None] = []
            cands: list[list[Color]] = []
            for pt in (ln.a, ln.b):
                c, cand = resolve_endpoint(code_map, pt, wrap_x=wrap_x)
                cols.append(c)
                cands.append(cand)
            for row in pins:
                m = _match_ends(row.a, row.b, ln.a, ln.b, tol, width)
                if not m:
                    continue
                p_a, p_b = (row.a_color, row.b_color) if m == 1 else (row.b_color, row.a_color)
                if cols[0] is None and p_a is not None:
                    cols[0] = p_a
                if cols[1] is None and p_b is not None:
                    cols[1] = p_b
            bad = [i for i in (0, 1) if cols[i] is None]
            if bad:
                names = ", ".join(
                    ("a" if i == 0 else "b") + "=" + "/".join(color_token(c) for c in cands[i][:3])
                    for i in bad)
                skipped.append(Skipped(ln.centroid, f"ambiguous endpoint ({names}); pin it in the "
                                       "worksheet with a_color/b_color", ln.a, ln.b))
                continue
            ca, cb = cols
        if ca == cb:
            skipped.append(Skipped(ln.centroid, f"same-province ({color_token(ca)})", pa, pb))
            continue
        if kinds.get(ca) == "lake" or kinds.get(cb) == "lake":
            skipped.append(Skipped(ln.centroid, "lake endpoint (lakes are stateless)", pa, pb))
            continue
        # A junction's land pair can never be a lake: _classify_junction's own
        # pairing search only accepts a pair whose kind is exactly "land", so a
        # lake leaf just leaves every pairing invalid ("no leaf pairing...") —
        # no separate lake check is reachable here.
        # A junction's sea pair is exempt from the touching-provinces skip (board
        # #5744, Chris's call): two sea zones can share a border far from a canal
        # site (measured: every real junction's sea pair does), which is
        # irrelevant to whether THIS chokepoint needs its own controllable
        # crossing. The touching check still applies to an ordinary "sea"/
        # "canal_*" 2-endpoint line, where two directly-adjacent land provinces
        # genuinely make an extra connection redundant.
        if land_pair is None and touching is not None and frozenset((ca, cb)) in touching:
            skipped.append(Skipped(ln.centroid,
                                   f"touching provinces ({color_token(ca)}/{color_token(cb)}) "
                                   "- no crossing needed", pa, pb))
            continue
        if color_code(ca) <= color_code(cb):
            crossings.append(Crossing(ca, cb, pa, pb, ln.pixels, ln.centroid,
                                      land_pair, land_points))
        else:
            crossings.append(Crossing(cb, ca, pb, pa, ln.pixels, ln.centroid,
                                      land_pair, land_points))
    crossings.sort(key=lambda c: (color_code(c.from_color), color_code(c.to_color),
                                  c.start[0], c.start[1]))
    return crossings, skipped


# ---------------------------------------------------------------------------
# Worksheet matching + emission
# ---------------------------------------------------------------------------

def match_worksheet(crossings: list[Crossing], rows, width: int | None = None,
                    tol: int = MATCH_TOL):
    """Pair worksheet rows to crossings by endpoint coordinates.

    Returns ``(pairs, untyped, errors)``. ``pairs`` is ``[(crossing, row)]``;
    ``untyped`` the crossings no row claims; ``errors`` every ambiguity — a row
    matching two crossings, a crossing matched by two rows, or a row matching none
    (stale). Nothing is resolved greedily."""
    errors: list[str] = []
    row_hits: list[list[int]] = [[] for _ in rows]
    cross_hits: list[list[int]] = [[] for _ in crossings]
    for i, row in enumerate(rows):
        for j, c in enumerate(crossings):
            if _match_ends(row.a, row.b, c.start, c.stop, tol, width):
                row_hits[i].append(j)
                cross_hits[j].append(i)
            elif c.land_points is not None and _match_ends(
                    row.a, row.b, c.land_points[0], c.land_points[1], tol, width):
                row_hits[i].append(j)
                cross_hits[j].append(i)
    pairs = []
    for i, row in enumerate(rows):
        if not row_hits[i]:
            errors.append(f"worksheet row {list(row.a)}->{list(row.b)} matches no drawn line "
                          "(stale, or its line was skipped - see the review report)")
        elif len(row_hits[i]) > 1:
            errors.append(f"worksheet row {list(row.a)}->{list(row.b)} matches "
                          f"{len(row_hits[i])} drawn lines")
    for j, c in enumerate(crossings):
        if len(cross_hits[j]) > 1:
            errors.append(f"drawn line {list(c.start)}->{list(c.stop)} is claimed by "
                          f"{len(cross_hits[j])} worksheet rows")
    if not errors:
        for j, c in enumerate(crossings):
            if cross_hits[j]:
                pairs.append((c, rows[cross_hits[j][0]]))
    untyped = [c for j, c in enumerate(crossings) if not cross_hits[j]]
    return pairs, untyped, errors


class _Probe:
    """Duck-typed worksheet row for matching raw JSON rows against crossings."""

    def __init__(self, raw: dict) -> None:
        self.a = (int(raw["a"][0]), int(raw["a"][1]))
        self.b = (int(raw["b"][0]), int(raw["b"][1]))


def sync_worksheet(crossings: list[Crossing], raw_rows: list[dict], width: int | None = None,
                   tol: int = MATCH_TOL):
    """Carry the hand-authored worksheet over to the current drawn lines.

    ``raw_rows`` are the worksheet's JSON dicts, other fields untouched. Each row is
    matched to the crossing whose two endpoints are both within ``tol`` px (either
    order) — or, when a crossing carries ``land_points`` (a canal redrawn as a "+"
    junction, board #5744), also against those: the "+" convention keeps the
    line's *original* two endpoints as its land leaves, so a row typed before the
    redraw still recognises its canal by them even though the crossing's own
    start/stop (the new sea leaves) are unrecognisable coordinates. A matched row
    keeps its type/comment/pins and has its endpoints refreshed to the crossing's
    sea pair (keeping the row's own a/b orientation) — never to the land points,
    which are not what the CSV or the worksheet identity model use going forward.
    A crossing no row claims becomes a blank stub in line order. A row matching no
    line is NOT deleted: it is returned in ``stale`` so the caller can park it.
    Ambiguity (a row on two lines, a line under two rows) is an error and nothing
    is rewritten.

    Returns ``(rows, stale, errors, stats)``; ``rows`` is ordered like the numbered
    review table (From, To, start_x, start_y).
    """
    probes = [_Probe(r) for r in raw_rows]
    row_hits: list[list[int]] = [[] for _ in raw_rows]
    cross_hits: list[list[int]] = [[] for _ in crossings]
    for i, p in enumerate(probes):
        for j, c in enumerate(crossings):
            if _match_ends(p.a, p.b, c.start, c.stop, tol, width):
                row_hits[i].append(j)
                cross_hits[j].append(i)
            elif c.land_points is not None and _match_ends(
                    p.a, p.b, c.land_points[0], c.land_points[1], tol, width):
                row_hits[i].append(j)
                cross_hits[j].append(i)
    errors = []
    for i, h in enumerate(row_hits):
        if len(h) > 1:
            errors.append(f"worksheet row {list(probes[i].a)}->{list(probes[i].b)} "
                          f"matches {len(h)} drawn lines")
    for j, h in enumerate(cross_hits):
        if len(h) > 1:
            errors.append(f"drawn line {list(crossings[j].start)}->{list(crossings[j].stop)} "
                          f"is claimed by {len(h)} worksheet rows")
    if errors:
        return [], [], errors, {}
    out: list[dict] = []
    moved = 0
    for j, c in enumerate(crossings):
        if cross_hits[j]:
            i = cross_hits[j][0]
            raw = dict(raw_rows[i])
            # A land_points-only match (the row's a/b are the pre-redraw canal
            # line, not this crossing's own sea pair) has no orientation to
            # preserve; falls through to the else arm below, same as a plain
            # reversed match.
            m = _match_ends(probes[i].a, probes[i].b, c.start, c.stop, tol, width)
            a, b = (c.start, c.stop) if m == 1 else (c.stop, c.start)
            if (probes[i].a, probes[i].b) != (a, b):
                moved += 1
            raw["a"], raw["b"] = [a[0], a[1]], [b[0], b[1]]
            out.append(raw)
        else:
            out.append({"a": [c.start[0], c.start[1]], "b": [c.stop[0], c.stop[1]],
                        "type": "", "comment": ""})
    stale = [raw_rows[i] for i, h in enumerate(row_hits) if not h]
    stats = {"kept": sum(1 for h in cross_hits if h), "moved": moved,
             "new": sum(1 for h in cross_hits if not h), "stale": len(stale)}
    return out, stale, [], stats


def type_kind_errors(pairs, kinds: dict) -> list[str]:
    """``sea`` rows must join land to land, ``canal_*`` rows sea to sea."""
    errors = []
    for c, row in pairs:
        if not row.type:
            continue  # untyped stub
        want = "land" if row.type == "sea" else "sea"
        got = (kinds.get(c.from_color), kinds.get(c.to_color))
        if got != (want, want):
            errors.append(f"worksheet row {list(row.a)}->{list(row.b)}: type {row.type!r} joins "
                          f"{want} to {want}, but this line joins {got[0]} to {got[1]}")
    return errors


def emit_csv(pairs, height: int) -> str:
    """``adjacencies.csv`` text: header + rows sorted by (From, To, start_x,
    start_y), engine ``y`` = ``height - 1 - y``, ``Through`` -1, empty rule name,
    LF joins, no trailing newline (a trailing newline is a malformed last row)."""
    pairs = [cr for cr in pairs if cr[1].type]  # an untyped stub is not emitted
    ordered = sorted(pairs, key=lambda cr: (color_code(cr[0].from_color),
                                            color_code(cr[0].to_color),
                                            cr[0].start[0], cr[0].start[1]))
    out = [ADJACENCIES_HEADER]
    for c, row in ordered:
        out.append(";".join([
            color_token(c.from_color), color_token(c.to_color), row.type, "-1",
            str(c.start[0]), str(height - 1 - c.start[1]),
            str(c.stop[0]), str(height - 1 - c.stop[1]),
            "", row.comment or "None",
        ]))
    return "\n".join(out)
