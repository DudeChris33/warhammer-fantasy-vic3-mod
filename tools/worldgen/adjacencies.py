"""Pure core of the adjacency pipeline (board #5563).

Hand-drawn yellow lines (each joining two provinces that do not touch: a strait,
an island link, a tunnel) -> one :class:`Line` per connected component -> two
province colours read under its endpoints -> a :class:`Crossing`. A hand-authored
worksheet (``tools/config/adjacency_worksheet.json``) then types each crossing and
:func:`emit_csv` writes ``map_data/adjacencies.csv``.

Everything here is a pure function of arrays / plain data — no I/O — so it is
deterministic and self-checkable (``run_fixture.py --check``).

Coordinates: every point here is in canvas (top-origin) ``(x, y)``. The engine
CSV's ``y`` is **bottom-origin**: :func:`emit_csv` writes ``H - 1 - y``.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

Color = tuple[int, int, int]
Point = tuple[int, int]

#: The exact paint colour of the source layer (no tolerance).
YELLOW_RGB = (255, 255, 0)
#: A window around an endpoint must have one province holding at least this share.
DOMINANT_FRACTION = 0.7
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
    """One drawn line: its two endpoints (canvas coords) or why it has none."""

    pixels: int
    centroid: Point
    a: Point | None
    b: Point | None
    reason: str = ""  # "" when ``a``/``b`` are valid, else "bad-shape: ..."


@dataclass(frozen=True)
class Crossing:
    """A resolved line: ``start`` sits in the From province, ``stop`` in To."""

    from_color: Color
    to_color: Color
    start: Point
    stop: Point
    pixels: int
    centroid: Point


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
        return Line(n_px, (cx, cy), None, None,
                    f"bad-shape: {off} skeleton px off the main path (loop / junction / merged lines)")
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

def resolve_endpoint(code_map: np.ndarray, p: Point, radius: int = 2, wrap_x: bool = True
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
        if ln.a is None or ln.b is None:
            skipped.append(Skipped(ln.centroid, ln.reason))
            continue
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
            pa, pb = (row.a_color, row.b_color) if m == 1 else (row.b_color, row.a_color)
            if cols[0] is None and pa is not None:
                cols[0] = pa
            if cols[1] is None and pb is not None:
                cols[1] = pb
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
            skipped.append(Skipped(ln.centroid, f"same-province ({color_token(ca)})", ln.a, ln.b))
            continue
        if kinds.get(ca) == "lake" or kinds.get(cb) == "lake":
            skipped.append(Skipped(ln.centroid, "lake endpoint (lakes are stateless)", ln.a, ln.b))
            continue
        if touching is not None and frozenset((ca, cb)) in touching:
            skipped.append(Skipped(ln.centroid,
                                   f"touching provinces ({color_token(ca)}/{color_token(cb)}) "
                                   "- no crossing needed", ln.a, ln.b))
            continue
        if color_code(ca) <= color_code(cb):
            crossings.append(Crossing(ca, cb, ln.a, ln.b, ln.pixels, ln.centroid))
        else:
            crossings.append(Crossing(cb, ca, ln.b, ln.a, ln.pixels, ln.centroid))
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


def type_kind_errors(pairs, kinds: dict) -> list[str]:
    """``sea`` rows must join land to land, ``canal_*`` rows sea to sea."""
    errors = []
    for c, row in pairs:
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
