"""River network from the user's hand-traced cyan river lines (board #3703).

The rivers on the map used to be *derived* from the heightmap's drainage
(``hydro.py``) — dense, terrain-following, but wrong for a fictional world: big
channels ran through the Nehekharan desert and the Reik did not exist. This
module replaces that with a **source-driven** network: the user draws the canon
rivers by hand as a pure-cyan ``(0, 255, 255)`` line network on the canvas (the
same idiom as the coastline / sea-zone / state-region traces
``sea_zones.py`` and ``land_provinces.py`` consume), and the tools turn that
drawing into the ordered source→mouth streams the vanilla ``rivers.png`` model
needs.

The pipeline, all deterministic (sorted iteration, fixed neighbour order, no RNG):

1. **Extract + union** the cyan line(s), dilated to bridge anti-aliasing gaps.
2. **Skeletonize** to a 1-px centreline and clip to land (no river on water).
3. **Graph** the skeleton — pixels by 8-neighbour degree into endpoints (deg 1),
   junctions (deg >= 3) and the deg-2 chains (edges) between them. Short spurs
   (skeletonization twigs off a main line) are pruned so they do not become fake
   headwaters, and the graph is asserted to be a **forest** — a cycle has no
   valid source→mouth orientation and is a hard error, not a silent corruption.
4. **Orient** flow around the three water classes (board #3742). Each connected
   tree has exactly one *outlet* (mouth); every other leaf is a *source* (a spring
   or a lake-fed outflow). The outlet is chosen by priority: the **ocean** (the
   navigable sea) if any endpoint reaches it, else a **lake** the river drains
   into (the lowest lake-adjacent endpoint), else — an **endorheic** river — the
   lowest inland endpoint, where it dries into a marsh or sink (the Marshes of
   Madness). The tree is rooted at that outlet and every edge oriented downstream
   toward it. So a lake→sea river (one ocean outlet, one lake source) and a
   lake→lake or inland-terminating river are all valid — only a genuine sea delta,
   **two separate ocean outlets** on one connected shape, is rejected (draw each
   distributary as its own line; there is deliberately no index-2 split support).
5. **Stitch maximal Horton/Strahler stems**: one green source per real headwater;
   at each junction the highest-order inflow continues the same stream (ties →
   longer upstream length → lower elevation → pixel order) and the other inflows
   terminate as separate ``confluence`` tributaries whose last pixel is 8-adjacent
   to the stream they join (marked red MERGE). This is exactly vanilla's model,
   and avoids the spurious extra source + sawtooth-width defects a naive
   per-segment split would paint.
6. **Width** from the stem's Strahler order mapped onto the vanilla ramp
   ``(3, 4, 6, 8)``, unless a matched name overrides it.
7. **Name** each stream by resolving each anchor pixel to exactly one stream
   (opt-in; the engine has no river names — the names exist only so #3677 /
   #3687 can reference a specific river through ``rivers_index.json``).

The resulting :class:`schema.RiverStream` list feeds ``worldgen.rivers.rasterize``
unchanged: its Bresenham over already-adjacent skeleton pixels is the identity,
so it reuses the source/merge painting, the width ramp and the full strict
validator (contiguity, on-land, inland source, mouth-reaches-water/confluence,
the 2×2-block caps) exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from worldgen import schema

#: Pure cyan (0, 255, 255) — the traced river-line colour. Distinct from magenta
#: (coast/borders 255,0,255), purple (sea zones 127,0,255) and every vanilla
#: river-palette blue, and absent from the globe terrain and state-region fills,
#: so extraction tolerates either backdrop. Matched tolerant of anti-aliasing.
_CYAN_MAX_R = 80          # red channel stays low
_CYAN_MIN_G = 180         # green + blue both high
_CYAN_MIN_B = 180

#: How far a manual river_overrides anchor may sit from the nearest river node.
_OVERRIDE_ANCHOR_TOL = 60.0

# 8-neighbour offsets in a fixed (dy, dx) order, so every tie-break is
# deterministic and independent of dict/set iteration order.
_D8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))

# Compass flow directions as (dx, dy) in image space (+x = east, +y = south), for
# manual river_overrides: the mouth is the endpoint furthest in this direction.
_FLOW_VEC = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0),
             "NE": (1, -1), "NW": (-1, -1), "SE": (1, 1), "SW": (-1, 1)}


class RiverNetworkError(RuntimeError):
    """A traced river network cannot be turned into valid source→mouth streams.

    Always actionable: the message names the offending pixel(s) and what the user
    should redraw, so a bad trace is a loud offline error rather than a subtly
    wrong ``rivers.png``.
    """


@dataclass(frozen=True)
class ExtractResult:
    """The streams plus the derived metadata ``generate_rivers.py`` serializes."""

    streams: list[schema.RiverStream]
    #: name -> {"mouth", "length_px", "width"} — the per-river core of
    #: rivers_index.json (state_keys are joined in later, once real states exist).
    index: dict[str, dict]
    #: Auto-named (unnamed) streams longer than the advisory threshold, each
    #: {"name", "length_px"} — surfaced so a major river cannot silently go
    #: unnamed. Not an error (naming is opt-in).
    unnamed: list[dict] = field(default_factory=list)
    #: Blocking trace problems, when built with ``strict=False`` (else these are
    #: raised). Each is {"kind", "x", "y", "detail"} — a canvas coordinate a
    #: diagnostic render can mark and a message the user can act on.
    issues: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Colour extraction
# ---------------------------------------------------------------------------

def cyan_lines(rgb: np.ndarray) -> np.ndarray:
    """Boolean mask of the hand-drawn cyan river line, tolerant of anti-aliasing."""
    r = rgb[..., 0].astype(int)
    g = rgb[..., 1].astype(int)
    b = rgb[..., 2].astype(int)
    return (r <= _CYAN_MAX_R) & (g >= _CYAN_MIN_G) & (b >= _CYAN_MIN_B)


def cyan_network(rgb: np.ndarray, dilate: int = 2) -> np.ndarray:
    """The cyan line, dilated to bridge anti-aliased gaps (mirrors
    ``sea_zones.extract``'s dilation of the drawn boundary)."""
    line = cyan_lines(rgb)
    if dilate:
        line = ndimage.binary_dilation(line, iterations=dilate)
    return line


# ---------------------------------------------------------------------------
# Skeleton graph
# ---------------------------------------------------------------------------

def _neighbors8(y: int, x: int, h: int, w: int, wrap_x: bool):
    """Every in-bounds 8-neighbour (wrap-aware). Used for water adjacency, where
    a pixel is a mouth if it touches sea in *any* of the 8 directions."""
    for dy, dx in _D8:
        ny = y + dy
        if ny < 0 or ny >= h:
            continue
        nx = x + dx
        if nx < 0 or nx >= w:
            if not wrap_x:
                continue
            nx %= w
        yield (ny, nx)


def _wrapx(x: int, w: int, wrap_x: bool) -> int | None:
    if 0 <= x < w:
        return x
    if wrap_x:
        return x % w
    return None


def _topo_neighbors(y: int, x: int, S: set[tuple[int, int]], h: int, w: int, wrap_x: bool):
    """Topological skeleton neighbours of ``(y, x)`` within ``S``.

    An 8-connected 1-px skeleton counts a diagonal neighbour even when an
    orthogonal skeleton cell already connects the pair by an L-path — which turns
    every T/Y junction into a spurious triangle and makes the graph read as
    cyclic. The standard fix: an orthogonal neighbour is always an edge; a
    diagonal neighbour ``(dy, dx)`` is an edge only when **neither** of its two
    shared orthogonal cells ``(y+dy, x)`` and ``(y, x+dx)`` is in the skeleton
    (otherwise the diagonal is redundant). This yields the true topology — a clean
    tree at a junction — while keeping genuine diagonal staircases connected.
    """
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ny = y + dy
        if ny < 0 or ny >= h:
            continue
        nx = _wrapx(x + dx, w, wrap_x)
        if nx is not None and (ny, nx) in S:
            yield (ny, nx)
    for dy, dx in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        ny = y + dy
        if ny < 0 or ny >= h:
            continue
        nx = _wrapx(x + dx, w, wrap_x)
        if nx is None or (ny, nx) not in S:
            continue
        # Shared orthogonal cells: (y+dy, x) and (y, x+dx). If either is skeleton,
        # the diagonal is an L-path shortcut — not a distinct edge.
        ay, ax = y + dy, _wrapx(x, w, wrap_x)
        by, bx = y, _wrapx(x + dx, w, wrap_x)
        a_in = 0 <= ay < h and ax is not None and (ay, ax) in S
        b_in = 0 <= by < h and bx is not None and (by, bx) in S
        if a_in or b_in:
            continue
        yield (ny, nx)


def _skeletonize(mask: np.ndarray) -> np.ndarray:
    from skimage.morphology import skeletonize
    return skeletonize(mask)


def _degree_map(pixels: set[tuple[int, int]], h: int, w: int, wrap_x: bool
                ) -> dict[tuple[int, int], int]:
    deg: dict[tuple[int, int], int] = {}
    for (y, x) in pixels:
        deg[(y, x)] = sum(1 for _ in _topo_neighbors(y, x, pixels, h, w, wrap_x))
    return deg


@dataclass
class _Edge:
    """One skeleton edge: an ordered pixel chain between two node pixels."""

    a: tuple[int, int]
    b: tuple[int, int]
    chain: list[tuple[int, int]]  # a .. b, inclusive, 8-adjacent

    def from_node(self, node: tuple[int, int]) -> list[tuple[int, int]]:
        """The chain oriented to start at ``node``."""
        if self.chain[0] == node:
            return self.chain
        return self.chain[::-1]

    @property
    def inner_len(self) -> int:
        return len(self.chain)


def _trace_edges(pixels: set[tuple[int, int]], deg: dict, nodes: set,
                 h: int, w: int, wrap_x: bool) -> list[_Edge]:
    """Trace the deg-2 chains between nodes into deduplicated edges."""
    edges: list[_Edge] = []
    seen: set[tuple] = set()
    for node in sorted(nodes):
        for p in sorted(_topo_neighbors(*node, pixels, h, w, wrap_x)):
            chain = [node, p]
            prev, cur = node, p
            while cur not in nodes:
                nxts = [nb for nb in _topo_neighbors(*cur, pixels, h, w, wrap_x)
                        if nb != prev]
                if len(nxts) != 1:
                    break  # deg-2 guarantees exactly one; safety valve
                prev, cur = cur, nxts[0]
                chain.append(cur)
            key = tuple(chain)
            rkey = tuple(chain[::-1])
            canon = min(key, rkey)
            if canon in seen:
                continue
            seen.add(canon)
            edges.append(_Edge(a=chain[0], b=chain[-1], chain=chain))
    return edges


def _prune_spurs(pixels: set[tuple[int, int]], h: int, w: int, wrap_x: bool,
                 spur_len: int) -> set[tuple[int, int]]:
    """Remove short deg-1 twigs hanging off a junction (skeletonization
    artefacts of a dilated stroke), leaving genuine streams intact.

    Only a twig whose far end is a **junction** (deg >= 3) is a spur; a short
    stand-alone line (both ends deg 1) is a real, if small, drawn river and is
    kept (it will be judged by the stranded / mouth rules downstream). Iterates
    to a fixed point so a twig exposed by removing another is also caught.
    """
    S = set(pixels)
    while True:
        deg = _degree_map(S, h, w, wrap_x)
        removed_any = False
        endpoints = sorted(px for px, d in deg.items() if d == 1)
        for ep in endpoints:
            if ep not in S:
                continue
            chain = [ep]
            prev, cur = None, ep
            while True:
                nxts = [nb for nb in _topo_neighbors(*cur, S, h, w, wrap_x)
                        if nb != prev]
                if len(nxts) != 1:
                    break
                prev, cur = cur, nxts[0]
                chain.append(cur)
                if deg.get(cur, 0) != 2:
                    break
            far = chain[-1]
            # A spur ends at a junction; drop the twig (keep the junction pixel).
            if deg.get(far, 0) >= 3 and (len(chain) - 1) <= spur_len:
                for px in chain[:-1]:
                    S.discard(px)
                removed_any = True
        if not removed_any:
            return S


# ---------------------------------------------------------------------------
# Components, orientation, Strahler stems
# ---------------------------------------------------------------------------

def _components(pixels: set[tuple[int, int]], h: int, w: int, wrap_x: bool
                ) -> list[set[tuple[int, int]]]:
    """8-connected components of the skeleton pixels (wrap-aware, deterministic)."""
    remaining = set(pixels)
    out: list[set[tuple[int, int]]] = []
    for start in sorted(pixels):
        if start not in remaining:
            continue
        remaining.discard(start)
        comp = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            for nb in _topo_neighbors(*cur, pixels, h, w, wrap_x):
                if nb in remaining:
                    remaining.discard(nb)
                    comp.add(nb)
                    stack.append(nb)
        out.append(comp)
    return out


def _elevation_at(elevation, px):
    if elevation is None:
        return 0.0
    return float(elevation[px[0], px[1]])


def _snap_mouths(pixels: set[tuple[int, int]], land: np.ndarray, wrap_x: bool,
                 snap: float) -> tuple[set[tuple[int, int]], int]:
    """Extend a river endpoint that falls just short of the coastline so it
    actually reaches the mask's water.

    The river trace and the committed land/sea mask are two independent hand-drawn
    layers, so a river drawn to the coast typically ends a pixel or two short of
    where the mask puts the water — which would fail the strict "a mouth must be
    8-adjacent to water" rule for no real reason. For each deg-1 endpoint that sits
    within ``snap`` px of water but is not yet touching it, draw the short straight
    line (on land) to the nearest coast-land pixel and add it, so the mouth
    genuinely reaches water. Endpoints farther than ``snap`` from water are left
    alone — those are genuinely inland and stay a loud stranded-line error.
    Deterministic (endpoints processed in sorted order). Returns the (possibly
    grown) pixel set and the number of endpoints snapped.
    """
    if snap <= 0:
        return pixels, 0
    from skimage.draw import line as _line

    h, w = land.shape
    water = ~land
    S = set(pixels)
    deg = _degree_map(S, h, w, wrap_x)
    R = int(np.ceil(snap))
    snapped = 0
    for (y, x) in sorted(p for p, d in deg.items() if d == 1):
        if any(water[ny, nx] for ny, nx in _neighbors8(y, x, h, w, wrap_x)):
            continue  # already a mouth
        best = None
        best_d = snap + 1e-9
        for dy in range(-R, R + 1):
            ny = y + dy
            if ny < 0 or ny >= h:
                continue
            for dx in range(-R, R + 1):
                nx = _wrapx(x + dx, w, wrap_x)
                if nx is None or not land[ny, nx]:
                    continue
                if not any(water[my, mx] for my, mx in _neighbors8(ny, nx, h, w, wrap_x)):
                    continue  # not a coast-land pixel
                d = (dy * dy + dx * dx) ** 0.5
                if d < best_d:
                    best_d, best = d, (dy, dx)
        if best is None:
            continue
        dy, dx = best
        # Draw in the unwrapped frame (x may go out of range), then fold x back.
        rr, cc = _line(y, x, y + dy, x + dx)
        for ly, lx in zip(rr.tolist(), cc.tolist()):
            fx = _wrapx(lx, w, wrap_x)
            if fx is None or not (0 <= ly < h) or not land[ly, fx]:
                continue
            S.add((ly, fx))
        snapped += 1
    return S, snapped


def extract_streams(network: np.ndarray, land: np.ndarray,
                    elevation: np.ndarray | None = None,
                    names: "list[schema.CanonRiverName]" = (),
                    *, lake: np.ndarray | None = None,
                    overrides: "list[schema.RiverOverride]" = (),
                    wrap_x: bool = True, spur_len: int = 8,
                    anchor_tol: float = 8.0, name_threshold: int = 40,
                    mouth_snap: float = 4.0, strict: bool = True,
                    ) -> ExtractResult:
    """Turn a drawn cyan river ``network`` (bool, canvas-sized) into ordered
    source→mouth :class:`schema.RiverStream` s. See the module docstring.

    ``land`` is the committed land/sea mask (True = land). ``lake`` is the inland
    lake mask (True where a water pixel is an enclosed lake, board #3742); absent,
    every water pixel is ocean. ``elevation`` is the committed heightmap (any
    monotone-with-height array), used to break a continuation tie and to pick the
    endorheic sink (lowest endpoint) when a river has no ocean outlet; ``None``
    falls back to pixel order. ``names`` are the anchor-keyed canon names; each
    must resolve to exactly one stream. ``name_threshold`` sizes the advisory
    unnamed-stream report only.
    """
    if network.shape != land.shape:
        raise RiverNetworkError(
            f"network {network.shape} and land mask {land.shape} differ in size")
    h, w = land.shape

    # Skeletonize wrap-aware on x: skimage's skeletonize does not wrap, so a river
    # crossing the x=0 / x=w-1 seam would lose its edge column and tear into two
    # stranded pieces. Roll a margin of the far side onto each edge, skeletonize
    # the padded strip, then crop back — so the seam is thinned with continuity.
    if wrap_x and w > 2:
        m = min(16, w // 2)
        padded = np.concatenate([network[:, -m:], network, network[:, :m]], axis=1)
        skel = _skeletonize(padded)[:, m:m + w] & land
    else:
        skel = _skeletonize(network) & land
    pixels: set[tuple[int, int]] = {(int(y), int(x)) for y, x in zip(*np.nonzero(skel))}
    if not pixels:
        raise RiverNetworkError("no cyan river pixels on land after skeletonization")

    pixels = _prune_spurs(pixels, h, w, wrap_x, spur_len)
    # Extend near-miss endpoints to the mask coastline (trace vs mask are two
    # independent hand layers; a river drawn to the coast often ends a pixel or
    # two short of the mask's water). Endpoints farther than mouth_snap stay a
    # loud stranded-line error below.
    pixels, _n_snapped = _snap_mouths(pixels, land, wrap_x, mouth_snap)
    deg = _degree_map(pixels, h, w, wrap_x)
    nodes = {px for px, d in deg.items() if d == 1 or d >= 3}
    edges = _trace_edges(pixels, deg, nodes, h, w, wrap_x)

    # Blocking issues are collected and raised together at the end (strict), so a
    # real trace surfaces its whole list of coordinates to fix in one pass rather
    # than one error per run; with strict=False they are returned for a diagnostic
    # render instead. Each is {"kind", "x", "y", "detail"}.
    issues: list[dict] = []

    def _issue(kind: str, x: int, y: int, detail: str) -> None:
        issues.append({"kind": kind, "x": int(x), "y": int(y), "detail": detail})

    # A skeleton pixel touched by no edge is either a pure loop (no endpoints /
    # junctions to anchor an edge) or an isolated speck. Loops have no valid
    # source→mouth orientation → hard error; specks are dropped as noise.
    covered = {px for e in edges for px in e.chain}
    orphan = pixels - covered
    if orphan:
        for comp in _components(orphan, h, w, wrap_x):
            if len(comp) >= 2:
                loop = sorted(comp)[0]
                _issue("loop", loop[1], loop[0],
                       "closed loop — a loop has no source→mouth flow; redraw it "
                       "as an open line")

    # Three water classes (board #3742): the ocean (navigable sea) is a river's
    # true outlet; a lake can be a river's *source* (a lake-fed outflow) or an
    # endorheic *sink* (a river draining into it); genuinely inland land is where
    # an endorheic river dries up (the Marshes of Madness). ``lake`` is the lake
    # mask; absent, every water pixel is ocean and the old behaviour holds.
    water = ~land
    lake_m = lake if lake is not None else np.zeros(land.shape, dtype=bool)
    ocean = water & ~lake_m

    def _adj(px: tuple[int, int], mask: np.ndarray) -> bool:
        return any(mask[ny, nx] for ny, nx in _neighbors8(*px, h, w, wrap_x))

    # Build the node adjacency (undirected), grouped by connected component via
    # union-find over the edges.
    adj: dict[tuple[int, int], list[tuple[tuple[int, int], _Edge]]] = {n: [] for n in nodes}
    parent_uf: dict[tuple[int, int], tuple[int, int]] = {n: n for n in nodes}

    def _find(x):
        while parent_uf[x] != x:
            parent_uf[x] = parent_uf[parent_uf[x]]
            x = parent_uf[x]
        return x

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent_uf[max(ra, rb)] = min(ra, rb)

    for e in edges:
        adj[e.a].append((e.b, e))
        adj[e.b].append((e.a, e))
        _union(e.a, e.b)

    comp_nodes: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for n in nodes:
        comp_nodes.setdefault(_find(n), []).append(n)

    # Resolve manual flow overrides (river_overrides.json) to their component by
    # the anchor's nearest *skeleton pixel* (the rivers are dense, so nearest node
    # can land on a neighbour's endpoint) — that pixel's edge names the component.
    override_by_comp: dict[tuple[int, int], "schema.RiverOverride"] = {}
    if overrides:
        from worldgen.raster import point_distance as _pdist
        pix_comp: dict[tuple[int, int], tuple[int, int]] = {}
        for e in edges:
            r = _find(e.a)
            for px in e.chain:
                pix_comp[px] = r
        pix_list = sorted(pix_comp)
        for ov in overrides:
            ax, ay = ov.anchor
            best_px, best_d = None, float("inf")
            for px in pix_list:
                d = _pdist((ax, ay), (px[1], px[0]), w, wrap_x)
                if d < best_d:
                    best_d, best_px = d, px
            if best_px is None or best_d > _OVERRIDE_ANCHOR_TOL:
                raise RiverNetworkError(
                    f"river override anchor {list(ov.anchor)} (flow {ov.flow}) is not on any "
                    f"drawn river — nearest river pixel {best_d:.0f}px away")
            override_by_comp[pix_comp[best_px]] = ov

    streams: list[tuple[list[tuple[int, int]], str, str, int, bool]] = []  # (pixels, head, mouth, order, coastal_source)
    dropped_short = 0  # sub-2px degenerate channels (1px islands) quietly dropped

    for root_key in sorted(comp_nodes):
        cnodes = comp_nodes[root_key]
        cnode_set = set(cnodes)
        cedges = [e for e in edges if e.a in cnode_set]
        endpoints = sorted(n for n in cnodes if deg[n] == 1)
        ov = override_by_comp.get(root_key)
        comp_override = ov is not None

        if comp_override:
            # Manual flow override: the mouth is the endpoint furthest in the
            # named compass direction; the opposite end is the source (coastal or
            # not — the rasterizer's inland-source rule is waived for it).
            vx, vy = _FLOW_VEC[ov.flow]
            mouth = max(endpoints, key=lambda n: (vx * n[1] + vy * n[0], n))
            outlets = {mouth}
        # Where does this network drain? Ocean-adjacent leaves are outlets — a
        # delta may reach the sea at several. With no ocean outlet the river is
        # endorheic: the single lowest endpoint drains it (a lake it flows into,
        # else an inland marsh/desert sink). Board #3742/#3703.
        elif (ocean_leaves := [n for n in endpoints if _adj(n, ocean)]):
            # A river needs a headwater: at least one leaf that is NOT an ocean
            # mouth (an inland spring or a lake-fed outflow). A shape whose every
            # end reaches the sea is a sourceless channel between two coastal
            # points, not a river — report it.
            if not any(n not in set(ocean_leaves) for n in endpoints):
                o = sorted(ocean_leaves)[0]
                _issue("no-source", o[1], o[0],
                       "both ends reach the sea with no inland source — a river "
                       "needs a headwater; connect it to its inland course, or "
                       "remove this coastal channel")
                continue
            outlets = set(ocean_leaves)
        else:
            pool = [n for n in endpoints if _adj(n, lake_m)] or endpoints
            if not pool:
                continue  # a degenerate component with no endpoint; nothing to draw
            outlets = {min(pool, key=lambda n: (_elevation_at(elevation, n), n))}

        # Orient the network into a flow DAG. BFS distance-to-outlet is the primary
        # potential; a strict node rank (dist, elevation, pixel) then orients every
        # edge from higher rank to lower — a total order, so the result cannot
        # contain a directed cycle. Divergence (a split node: 1 in, >=2 out) and
        # reconvergence (a merge: >=2 in, 1 out) both fall out of this, so a delta
        # and a river-island around which the channel splits and rejoins are both
        # valid, not errors.
        dist: dict[tuple[int, int], int] = {o: 0 for o in outlets}
        bfsq = sorted(outlets)
        qi = 0
        while qi < len(bfsq):
            cur = bfsq[qi]
            qi += 1
            for (nb, _e) in adj[cur]:
                if nb not in dist:
                    dist[nb] = dist[cur] + 1
                    bfsq.append(nb)

        def _rank(n, _d=dist):
            return (_d.get(n, 1 << 30), _elevation_at(elevation, n), n)

        out_e: dict[tuple[int, int], list[tuple[tuple[int, int], _Edge]]] = {n: [] for n in cnodes}
        in_e: dict[tuple[int, int], list[tuple[tuple[int, int], _Edge]]] = {n: [] for n in cnodes}
        for e in cedges:
            u, v = (e.a, e.b) if _rank(e.a) > _rank(e.b) else (e.b, e.a)
            out_e[u].append((v, e))
            in_e[v].append((u, e))

        # Strahler order + upstream pixel length, processed sources-first (high rank).
        node_order: dict[tuple[int, int], int] = {}
        up_len: dict[tuple[int, int], int] = {}
        for n in sorted(cnodes, key=_rank, reverse=True):
            ins = in_e[n]
            if not ins:
                node_order[n], up_len[n] = 1, 0
            else:
                ords = sorted((node_order[u] for (u, _e) in ins), reverse=True)
                node_order[n] = ords[0] + 1 if len(ords) > 1 and ords[1] == ords[0] else ords[0]
                up_len[n] = sum(up_len[u] + e.inner_len - 1 for (u, e) in ins)

        # The main branch continues the trunk: at a merge, the biggest tributary;
        # at a split, the longest distributary. The others start/end as markers.
        main_in: dict[tuple[int, int], _Edge] = {}
        main_out: dict[tuple[int, int], _Edge] = {}
        for n in cnodes:
            if in_e[n]:
                main_in[n] = min(in_e[n], key=lambda t: (-node_order[t[0]], -up_len[t[0]],
                                                         _elevation_at(elevation, t[0]), t[0]))[1]
            if out_e[n]:
                main_out[n] = max(out_e[n], key=lambda t: (t[1].inner_len, t[0]))[1]

        def _mouth_kind(n):
            return "sea" if _adj(n, water) else "endorheic"

        def _walk(start, first_v, first_edge, head):
            # A source stem keeps the source node pixel (green at pts[0]); a split
            # distributary drops the split node (it lives on the trunk) and starts
            # at the pixel after it (yellow at pts[0]).
            chain = first_edge.from_node(start)
            pts = list(chain) if head == "source" else list(chain[1:])
            term, arrived, cur = first_v, first_edge, first_v
            while True:
                if main_in.get(cur) is arrived:          # we are the trunk into cur
                    if not out_e[cur]:                   # cur is the outlet
                        return pts, head, _mouth_kind(cur), node_order[cur]
                    e2 = main_out[cur]                   # continue along the trunk
                    w = e2.b if e2.a == cur else e2.a
                    pts.extend(e2.from_node(cur)[1:])
                    term, arrived, cur = w, e2, w
                    continue
                # a tributary into a merge (or into the outlet node): end before cur
                if pts and pts[-1] == cur:
                    pts = pts[:-1]
                return pts, head, "confluence", node_order[term]

        for n in sorted(cnodes):
            outs = sorted(out_e[n], key=lambda t: t[0])
            if not outs:
                continue
            mo = main_out.get(n)
            src_node = not in_e[n]
            for (v, e) in outs:
                if e is mo and not src_node:
                    continue                              # trunk continuation of an upstream stem
                head = "source" if (src_node and e is mo) else "split"
                pts, hd, mk, order = _walk(n, v, e, head)
                if len(pts) < 2:
                    # A sub-2px channel is a 1px-island / adjacent split-and-rejoin
                    # — cartographically nothing. Drop it (the trunk still carries
                    # the flow through) rather than erroring on a degenerate pixel.
                    dropped_short += 1
                    continue
                # In an override component the forced source may sit on the coast;
                # waive the rasterizer's inland-source rule for its source heads.
                streams.append((pts, hd, mk, order, comp_override and hd == "source"))

    if issues and strict:
        head = (f"{len(issues)} river network problem(s) — fix the trace and re-run "
                f"(coords are canvas x, y):")
        raise RiverNetworkError(
            head + "".join(f"\n  - {i['kind']} at (x={i['x']}, y={i['y']}): {i['detail']}"
                           for i in issues))

    result = _finalize(streams, names, h, w, wrap_x, anchor_tol, name_threshold)
    return ExtractResult(streams=result.streams, index=result.index,
                         unnamed=result.unnamed, issues=issues)


def _finalize(streams, names, h, w, wrap_x, anchor_tol, name_threshold) -> ExtractResult:
    from worldgen.raster import point_distance

    ramp = schema.RIVER_WIDTH_RAMP

    # Deterministic auto-order: by first pixel (stem[0]).
    streams = sorted(streams, key=lambda s: s[0][0])
    auto = []
    for i, (stem, head, mouth_kind, order, coastal_source) in enumerate(streams):
        width = ramp[min(max(order, 1) - 1, len(ramp) - 1)]
        pts_xy = [(x, y) for (y, x) in stem]
        auto.append({
            "auto_name": f"river_{i:04d}",
            "points": pts_xy,
            "stem_yx": stem,
            "head": head,
            "mouth": mouth_kind,
            "width": width,
            "length_px": len(stem),
            "coastal_source": coastal_source,
        })

    # Resolve each anchor to exactly one stream by nearest river pixel.
    name_by_stream: dict[int, str] = {}
    for cn in names:
        ax, ay = cn.anchor
        best_i, best_d = -1, float("inf")
        tie = False
        for i, s in enumerate(auto):
            for (px, py) in s["points"]:
                d = point_distance((ax, ay), (px, py), w, wrap_x)
                if d < best_d - 1e-9:
                    best_d, best_i, tie = d, i, False
                elif abs(d - best_d) <= 1e-9 and i != best_i:
                    tie = True
        if best_i < 0 or best_d > anchor_tol:
            raise RiverNetworkError(
                f"river name '{cn.name}': anchor {list(cn.anchor)} is not on any "
                f"river line (nearest pixel {best_d:.1f}px away, tolerance {anchor_tol})"
            )
        if tie:
            raise RiverNetworkError(
                f"river name '{cn.name}': anchor {list(cn.anchor)} is equidistant from "
                f"two rivers — move it onto the intended line"
            )
        if best_i in name_by_stream:
            raise RiverNetworkError(
                f"rivers '{name_by_stream[best_i]}' and '{cn.name}' both resolve to the "
                f"same stream — one anchor per river"
            )
        name_by_stream[best_i] = cn.name
        if cn.width is not None:
            auto[best_i]["width"] = cn.width
        if cn.mouth is not None and cn.mouth != auto[best_i]["mouth"]:
            raise RiverNetworkError(
                f"river name '{cn.name}': declared mouth '{cn.mouth}' contradicts the "
                f"traced topology ('{auto[best_i]['mouth']}') — remove the override"
            )

    out_streams: list[schema.RiverStream] = []
    index: dict[str, dict] = {}
    unnamed: list[dict] = []
    for i, s in enumerate(auto):
        name = name_by_stream.get(i, s["auto_name"])
        out_streams.append(schema.RiverStream(
            name=name, points=s["points"], mouth=s["mouth"], width=s["width"], head=s["head"],
            coastal_source=s["coastal_source"]))
        index[name] = {"head": s["head"], "mouth": s["mouth"],
                       "length_px": s["length_px"], "width": s["width"]}
        if i not in name_by_stream and s["length_px"] >= name_threshold:
            unnamed.append({"name": name, "length_px": s["length_px"]})

    return ExtractResult(streams=out_streams, index=index, unnamed=unnamed)
