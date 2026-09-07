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
4. **Orient** flow: a *mouth* is a deg-1 endpoint 8-adjacent to water (per the
   committed land/sea mask); each connected tree is rooted at its single mouth
   and every edge oriented downstream toward it. A tree with **no** mouth is a
   stranded inland line (hard error); a tree with **two or more** mouths would
   need a divergent junction (a drawn delta fork) and is rejected with guidance
   to draw each distributary as its own line (the settled option-2 convention —
   there is deliberately no index-2 split support).
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

# 8-neighbour offsets in a fixed (dy, dx) order, so every tie-break is
# deterministic and independent of dict/set iteration order.
_D8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


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


def extract_streams(network: np.ndarray, land: np.ndarray,
                    elevation: np.ndarray | None = None,
                    names: "list[schema.CanonRiverName]" = (),
                    *, wrap_x: bool = True, spur_len: int = 8,
                    anchor_tol: float = 8.0, name_threshold: int = 40,
                    ) -> ExtractResult:
    """Turn a drawn cyan river ``network`` (bool, canvas-sized) into ordered
    source→mouth :class:`schema.RiverStream` s. See the module docstring.

    ``land`` is the committed land/sea mask (True = land). ``elevation`` is the
    committed heightmap (any monotone-with-height array) used only to break an
    otherwise-exact continuation tie; ``None`` falls back to pixel order.
    ``names`` are the anchor-keyed canon names; each must resolve to exactly one
    stream. ``name_threshold`` sizes the advisory unnamed-stream report only.
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
    deg = _degree_map(pixels, h, w, wrap_x)
    nodes = {px for px, d in deg.items() if d == 1 or d >= 3}
    edges = _trace_edges(pixels, deg, nodes, h, w, wrap_x)

    # A skeleton pixel touched by no edge is either a pure loop (no endpoints /
    # junctions to anchor an edge) or an isolated speck. Loops have no valid
    # source→mouth orientation → hard error; specks are dropped as noise.
    covered = {px for e in edges for px in e.chain}
    orphan = pixels - covered
    if orphan:
        for comp in _components(orphan, h, w, wrap_x):
            if len(comp) >= 2:
                loop = sorted(comp)[0]
                raise RiverNetworkError(
                    f"river network contains a closed loop near {(loop[1], loop[0])} "
                    f"(x, y) — a loop has no source→mouth flow; redraw it as an open line"
                )

    water = ~land

    def _is_mouth(px: tuple[int, int]) -> bool:
        return any(water[ny, nx] for ny, nx in _neighbors8(*px, h, w, wrap_x))

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

    streams: list[tuple[list[tuple[int, int]], str, int]] = []  # (pixels(y,x), mouth, order)

    for root_key in sorted(comp_nodes):
        cnodes = comp_nodes[root_key]
        cnode_set = set(cnodes)
        cedges = [e for e in edges if e.a in cnode_set]
        # Forest invariant per component: a tree has exactly nodes-1 edges.
        if len(cedges) != len(cnodes) - 1:
            sample = sorted(cnode_set)[0]
            raise RiverNetworkError(
                f"river component near {(sample[1], sample[0])} (x, y) is not a tree "
                f"({len(cnodes)} nodes, {len(cedges)} edges) — it contains a cycle; "
                f"redraw it without a closed loop"
            )
        endpoints = sorted(n for n in cnodes if deg[n] == 1)
        mouths = [n for n in endpoints if _is_mouth(n)]
        if not mouths:
            sample = endpoints[0] if endpoints else sorted(cnode_set)[0]
            raise RiverNetworkError(
                f"river near {(sample[1], sample[0])} (x, y) reaches no water — every "
                f"river must end at the sea; extend it to the coast or remove it"
            )
        if len(mouths) >= 2:
            m0, m1 = sorted(mouths)[:2]
            raise RiverNetworkError(
                f"river forks to two mouths, at {(m0[1], m0[0])} and {(m1[1], m1[0])} "
                f"(x, y) — draw each distributary as its own separate line to the sea "
                f"(the delta convention); index-2 splits are unsupported"
            )
        mouth = mouths[0]

        # Root the tree at the mouth: BFS gives each node its downstream parent.
        parent_of: dict[tuple[int, int], tuple[int, int] | None] = {mouth: None}
        parent_edge: dict[tuple[int, int], _Edge | None] = {mouth: None}
        children: dict[tuple[int, int], list[tuple[int, int]]] = {n: [] for n in cnodes}
        order_bfs = [mouth]
        seen_bfs = {mouth}
        qi = 0
        while qi < len(order_bfs):
            cur = order_bfs[qi]
            qi += 1
            for (nb, e) in sorted(adj[cur], key=lambda t: t[0]):
                if nb in seen_bfs:
                    continue
                seen_bfs.add(nb)
                parent_of[nb] = cur
                parent_edge[nb] = e
                children[cur].append(nb)
                order_bfs.append(nb)

        # Strahler order + subtree pixel length, post-order (reverse BFS).
        strahler: dict[tuple[int, int], int] = {}
        sub_len: dict[tuple[int, int], int] = {}
        for cur in reversed(order_bfs):
            kids = children[cur]
            if not kids:  # a source leaf
                strahler[cur] = 1
                sub_len[cur] = 0
                continue
            kid_orders = sorted((strahler[k] for k in kids), reverse=True)
            top = kid_orders[0]
            strahler[cur] = top + 1 if len(kid_orders) > 1 and kid_orders[1] == top else top
            sub_len[cur] = sum(sub_len[k] + parent_edge[k].inner_len - 1 for k in kids)

        # Main child at each junction: highest order, then longest subtree, then
        # lowest elevation at the child pixel, then pixel order.
        main_child: dict[tuple[int, int], tuple[int, int]] = {}
        for cur in cnodes:
            kids = children[cur]
            if len(kids) >= 1:
                main_child[cur] = min(
                    kids,
                    key=lambda k: (-strahler[k], -sub_len[k],
                                   _elevation_at(elevation, k), k),
                )

        sources = sorted(n for n in endpoints if n != mouth)
        if not sources:
            # A lone mouth with no inland source (a 2-node path both-ends-water is
            # already caught as >=2 mouths; this is the degenerate 1-edge case).
            raise RiverNetworkError(
                f"river at {(mouth[1], mouth[0])} (x, y) has no inland source")

        for src in sources:
            stem: list[tuple[int, int]] = [src]
            cur = src
            mouth_kind = "sea"
            while True:
                par = parent_of[cur]
                e = parent_edge[cur]
                chain = e.from_node(cur)  # cur .. par
                if par == mouth:
                    stem.extend(chain[1:])          # include the mouth pixel
                    mouth_kind = "sea"
                    break
                if main_child.get(par) == cur:
                    stem.extend(chain[1:])          # through the junction (own it)
                    cur = par
                    continue
                # A tributary: stop before the junction (it belongs to the main
                # stem); the last pixel is 8-adjacent to it and marked MERGE.
                stem.extend(chain[1:-1])
                mouth_kind = "confluence"
                break
            if len(stem) < 2:
                bad = stem[0] if stem else src
                raise RiverNetworkError(
                    f"river branch at {(bad[1], bad[0])} (x, y) is too short — a source "
                    f"sits directly on a confluence; lengthen the drawn line"
                )
            # Width from the stem's most-downstream Strahler order (the trunk's
            # order for a sea stem, the last junction it owns for a tributary),
            # so the trunk renders wider than a headwater — vanilla's model.
            order = _stem_terminal_order(
                strahler, children, main_child, src, parent_of, mouth)
            streams.append((stem, mouth_kind, order))

    return _finalize(streams, names, h, w, wrap_x, anchor_tol, name_threshold)


def _stem_terminal_order(strahler, children, main_child, src, parent_of, mouth) -> int:
    """The Strahler order at a tributary stem's downstream-most node (the last
    junction it owns before it merges), used to pick the stem's width."""
    cur = src
    order = strahler[src]
    while True:
        par = parent_of[cur]
        if par == mouth:
            return strahler[cur]
        if main_child.get(par) == cur:
            order = strahler[cur]
            cur = par
            continue
        return order


def _finalize(streams, names, h, w, wrap_x, anchor_tol, name_threshold) -> ExtractResult:
    from worldgen.raster import point_distance

    ramp = schema.RIVER_WIDTH_RAMP

    # Deterministic auto-order: by source pixel (stem[0]).
    streams = sorted(streams, key=lambda s: s[0][0])
    auto = []
    for i, (stem, mouth_kind, order) in enumerate(streams):
        width = ramp[min(max(order, 1) - 1, len(ramp) - 1)]
        pts_xy = [(x, y) for (y, x) in stem]
        auto.append({
            "auto_name": f"river_{i:04d}",
            "points": pts_xy,
            "stem_yx": stem,
            "mouth": mouth_kind,
            "width": width,
            "length_px": len(stem),
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
            name=name, points=s["points"], mouth=s["mouth"], width=s["width"]))
        index[name] = {"mouth": s["mouth"], "length_px": s["length_px"], "width": s["width"]}
        if i not in name_by_stream and s["length_px"] >= name_threshold:
            unnamed.append({"name": name, "length_px": s["length_px"]})

    return ExtractResult(streams=out_streams, index=index, unnamed=unnamed)
