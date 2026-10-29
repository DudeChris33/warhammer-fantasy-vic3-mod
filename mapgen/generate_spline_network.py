#!/usr/bin/env python3
"""Emit ``gfx/map/spline_network/spline_network.splnet``: the route network.

Board #9555. The engine's travel loader needs a land connection node in each
state of every adjacent pair, or it logs "Cannot connect state adjacency
connection, no connection node found in state" once per pair
(``travel_connection_definition.cpp``). Vanilla's file describes Earth, and the
engine does not build a usable land layer for this map: the map editor's
default-mode ``SplineNetwork.AppendAssets`` creates no land strips, its Strip
Tool routes a strip only while it is drawn by hand, and its nav-mesh pathing
fails on the Old World coast. So this script owns the **land layer**:

* one land hub per map-object locator instance, id ``state * 100 + slot``
  (slot 0 city, 1 farm, 2 mine, 3 port, 4 wood) at the locator's ``(x, z)`` —
  exactly what the editor's "auto-place hub anchors" writes;
* an in-state star, city -> each of farm, mine, port, wood, skipping a spoke
  whose two hubs coincide (the loader's ``disconnected_instate_fix_*`` covers it);
* one road per adjacent state pair under ``PAIR_RULE``, between the nearest hub
  pair that routes.

Every road is routed here, as a least-cost path (``skimage.graph.MCP_Geometric``)
over a cost raster that admits only the land of the road's own state(s): sea,
lake and third-state pixels are impassable, impassable provinces cost
``IMPASSABLE_COST`` and other land ``1 + SLOPE_WEIGHT * heightmap gradient``. A
road can therefore never cross the sea or a third state, which would be the
``route_graphics.cpp:734`` "connects state region to a non-adjacent one" class.
The pixel path is simplified (Ramer-Douglas-Peucker, ``RDP_EPS_PX``, never
letting a straightened segment cross more impassable or off-state pixels than
the path did) and
resampled to at most ``ANCHOR_SPACING_PX`` between anchors (vanilla's median
spacing on routed land strips is 8.4 px). Every land road is ``LAND_SPLINE_TYPE``
(railroad); dirt roads by terrain wait for the terrain pass.

The **naval layer** (harbour hubs ``0x800000 + state * 100``, naval and coastal
naval strips with their intermediates, and their lookups) comes from the map
editor's naval-mode ``AppendAssets`` and is kept byte-for-byte as data: it is
read from the shipped file, or once from ``--naval-from <path>``
(``mapgen/MAP_RUNBOOK.md``, "Route network"). The writer refuses a naval layer
whose harbours are not exactly the current port states plus the passable sea
states: state ids or ports changed, so the desktop naval step must be re-run.
There are no port-to-harbour strips; the loader pairs them by id.

``PAIR_RULE``: two land states are adjacent when a passable province of one
shares a pixel edge with a passable province of the other (4-neighbourhood, x
wraps under ``map_config.WRAP_X``). Pairs touching only through impassable
provinces, and strait-only pairs (the loader builds ``strait_crossing_*``
itself), get no road. Reconciled on the first load (2026-10-29, 432 states):
655 pairs, 650 routed. The game logged 0 travel "no connection node" lines
(697 with the empty network) and 0 ``route_graphics.cpp:734`` non-adjacent
lines, so the rule matches the engine's. The 5 unrouted pairs (one state in two
pieces, the neighbour touching the piece with no hub) and the 97 unroutable
spokes (hubs on separate islands) logged nothing. The one remaining travel line,
``:252`` "none of the nodes are connected to another state region", is an island
state whose harbour the engine's naval step gave no strip (#9784).

File format (Paradox binary script, u16 tokens; decoded while scoping #9555):
version ``0x00ee = i32 4``; counts ``0x045a = { i32 anchors i32 strips
i32 lookups }``; anchors ``0x05f4 = { { 0x000b = u32 id 0x004c = { f32 x f32 z } } ... }``,
strips ``0x05f5 = { { 0x000b = u64 id 0x05f7 = { u32 anchor ... } } ... }``,
lookups ``0x05f6 = { { 0x000b = u64 key 0x05f5 = { u64 strip ... } } ... }``; an
empty list is omitted. Strip id ``(index << 8) | spline_type``; lookup key
``(hi << 35) | (lo << 6) | spline_type`` over the strip's end anchors; anchors,
strips and lookups ascending by id. Intermediate anchors are
``0x10000000 + n``; land intermediates are numbered after the naval ones.

Frame: locator ``position={ x 0 z }`` = anchor ``{ x z }`` = ``provinces.png``
pixel ``(x - 0.5, 3616 - z - 0.5)``.

Inputs are all committed or generated: ``map_data/state_regions/*.txt``,
``map_data/provinces.png``, ``map_data/heightmap.png``, the five
``gfx/map/map_object_data/generated_map_object_locators_*.txt`` and the naval
layer. The output is a pure function of them, byte-identical across runs, and
static data the engine loads identically on every client.

Re-run after ``generate_map_locators.py``; after a regen that changes state ids
or ports, first re-run the desktop naval step.

Usage::

    python mapgen/generate_spline_network.py                          # write the file
    python mapgen/generate_spline_network.py --naval-from <splnet>    # bootstrap the naval layer
    python mapgen/generate_spline_network.py --check                  # fail if the file is not current
    python mapgen/generate_spline_network.py --render                 # also write scratchpad/ previews
"""
from __future__ import annotations

import argparse
import math
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.graph import MCP_Geometric

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from config import map_config  # noqa: E402
from worldgen.raster import read_gray16_png, read_rgb_png  # noqa: E402

MOD_ROOT = TOOLS_DIR.parent
STATE_DIR = MOD_ROOT / "map_data" / "state_regions"
PROVINCES_PNG = MOD_ROOT / "map_data" / "provinces.png"
HEIGHTMAP_PNG = MOD_ROOT / "map_data" / "heightmap.png"
LOCATOR_DIR = MOD_ROOT / "gfx" / "map" / "map_object_data"
OUT_PATH = MOD_ROOT / "gfx" / "map" / "spline_network" / "spline_network.splnet"
SCRATCH_DIR = MOD_ROOT / "scratchpad"  # previews; gitignored at the repo root

Image.MAX_IMAGE_PIXELS = None  # heightmap.png is 2x the canvas

CANVAS_W, CANVAS_H = map_config.PROVINCES_SIZE
WRAP_X = map_config.WRAP_X

# --- format ---------------------------------------------------------------
TOK_EQ, TOK_OPEN, TOK_CLOSE = 0x0001, 0x0003, 0x0004
VAL_I32, VAL_U32, VAL_F32, VAL_U64 = 0x000C, 0x0014, 0x000D, 0x029C
TOK_VERSION = 0x00EE
TOK_COUNTS = 0x045A
TOK_ANCHORS = 0x05F4
TOK_STRIPS = 0x05F5
TOK_LOOKUPS = 0x05F6
TOK_ID = 0x000B
TOK_POS = 0x004C
TOK_STRIP_ANCHORS = 0x05F7
TOK_LOOKUP_STRIPS = 0x05F5  # the lookup's strip list reuses the strips token
FORMAT_VERSION = 4

HARBOUR_FLAG = 0x800000
INTERMEDIATE_BASE = 0x10000000
NAVAL_TYPES = (2, 3)  # naval_route, coastal_naval_route (vanilla spline_types/00_default.txt)

# --- network --------------------------------------------------------------
#: Locator type -> hub slot (the hub id's last two digits).
SLOTS = {"city": 0, "farm": 1, "mine": 2, "port": 3, "wood": 4}
#: Spline type of every land road: 1 railroad (0 would be dirtroad).
LAND_SPLINE_TYPE = 1
#: Adjacency rule, see the module docstring.
PAIR_RULE = "passable-contact"

# --- routing --------------------------------------------------------------
#: High enough that a road crosses an impassable province only when its states touch nowhere else (Chris, 2026-10-29).
IMPASSABLE_COST = 1000.0
#: Cost per raw heightmap unit of gradient per canvas pixel (p95 on land ~550).
SLOPE_WEIGHT = 1.0 / 200.0
RDP_EPS_PX = 1.5
ANCHOR_SPACING_PX = 8.0
#: Search boxes around the two hubs, tried in order; ``None`` is the road's whole state window.
ROUTE_MARGINS_PX = (64, 256, None)


# ---------------------------------------------------------------------------
# Binary script
# ---------------------------------------------------------------------------

def _decode(data: bytes) -> list:
    """Generic token tree: ``("T", tok)`` for keys, ``"="``, scalars and nested lists."""
    stack: list[list] = [[]]
    i, n = 0, len(data)
    while i < n:
        (t,) = struct.unpack_from("<H", data, i)
        i += 2
        if t == TOK_OPEN:
            stack.append([])
        elif t == TOK_CLOSE:
            if len(stack) < 2:
                raise ValueError("unbalanced '}'")
            x = stack.pop()
            stack[-1].append(x)
        elif t == TOK_EQ:
            stack[-1].append("=")
        elif t == VAL_I32:
            stack[-1].append(("i32", struct.unpack_from("<i", data, i)[0]))
            i += 4
        elif t == VAL_U32:
            stack[-1].append(("u32", struct.unpack_from("<I", data, i)[0]))
            i += 4
        elif t == VAL_F32:
            stack[-1].append(("f32", data[i:i + 4]))  # raw bytes: pass-through is exact
            i += 4
        elif t == VAL_U64:
            stack[-1].append(("u64", struct.unpack_from("<Q", data, i)[0]))
            i += 8
        else:
            stack[-1].append(("T", t))
    if len(stack) != 1:
        raise ValueError("unbalanced '{'")
    return stack[0]


def _fields(block: list) -> dict[int, object]:
    """``{key token: value}`` for a ``key = value`` sequence."""
    out: dict[int, object] = {}
    for j in range(0, len(block) - 2, 3):
        k, eq, v = block[j], block[j + 1], block[j + 2]
        if not (isinstance(k, tuple) and k[0] == "T" and eq == "="):
            raise ValueError(f"unexpected token sequence at {j}")
        out[k[1]] = v
    return out


@dataclass
class Network:
    #: ``{anchor id: (x f32 bytes, z f32 bytes)}``
    anchors: dict[int, tuple[bytes, bytes]] = field(default_factory=dict)
    #: ``{strip id: [anchor ids]}``
    strips: dict[int, list[int]] = field(default_factory=dict)
    #: ``{lookup key: [strip ids]}``
    lookups: dict[int, list[int]] = field(default_factory=dict)


def parse(data: bytes) -> Network:
    top = _fields(_decode(data))
    if top.get(TOK_VERSION) != ("i32", FORMAT_VERSION):
        raise ValueError(f"unsupported version {top.get(TOK_VERSION)}")
    net = Network()
    for a in top.get(TOK_ANCHORS, []):
        f = _fields(a)
        x, z = f[TOK_POS]
        net.anchors[f[TOK_ID][1]] = (x[1], z[1])
    for s in top.get(TOK_STRIPS, []):
        f = _fields(s)
        net.strips[f[TOK_ID][1]] = [v[1] for v in f[TOK_STRIP_ANCHORS]]
    for lk in top.get(TOK_LOOKUPS, []):
        f = _fields(lk)
        net.lookups[f[TOK_ID][1]] = [v[1] for v in f[TOK_LOOKUP_STRIPS]]
    counts = [v[1] for v in top[TOK_COUNTS]]
    if counts != [len(net.anchors), len(net.strips), len(net.lookups)]:
        raise ValueError(f"header counts {counts} do not match the lists")
    return net


def encode(net: Network) -> bytes:
    out = bytearray()

    def tok(t: int) -> None:
        out.extend(struct.pack("<H", t))

    def key(t: int) -> None:
        tok(t)
        tok(TOK_EQ)

    key(TOK_VERSION)
    tok(VAL_I32)
    out.extend(struct.pack("<i", FORMAT_VERSION))
    key(TOK_COUNTS)
    tok(TOK_OPEN)
    for n in (len(net.anchors), len(net.strips), len(net.lookups)):
        tok(VAL_I32)
        out.extend(struct.pack("<i", n))
    tok(TOK_CLOSE)
    if net.anchors:
        key(TOK_ANCHORS)
        tok(TOK_OPEN)
        for aid in sorted(net.anchors):
            x, z = net.anchors[aid]
            tok(TOK_OPEN)
            key(TOK_ID)
            tok(VAL_U32)
            out.extend(struct.pack("<I", aid))
            key(TOK_POS)
            tok(TOK_OPEN)
            for v in (x, z):
                tok(VAL_F32)
                out.extend(v)
            tok(TOK_CLOSE)
            tok(TOK_CLOSE)
        tok(TOK_CLOSE)
    for list_tok, entries, item_tok, val in (
        (TOK_STRIPS, net.strips, TOK_STRIP_ANCHORS, (VAL_U32, "<I")),
        (TOK_LOOKUPS, net.lookups, TOK_LOOKUP_STRIPS, (VAL_U64, "<Q")),
    ):
        if not entries:
            continue
        key(list_tok)
        tok(TOK_OPEN)
        for eid in sorted(entries):
            tok(TOK_OPEN)
            key(TOK_ID)
            tok(VAL_U64)
            out.extend(struct.pack("<Q", eid))
            key(item_tok)
            tok(TOK_OPEN)
            for v in entries[eid]:
                tok(val[0])
                out.extend(struct.pack(val[1], v))
            tok(TOK_CLOSE)
            tok(TOK_CLOSE)
        tok(TOK_CLOSE)
    return bytes(out)


def f32(v: float) -> bytes:
    return struct.pack("<f", v)


def lookup_key(a: int, b: int, spline_type: int) -> int:
    lo, hi = min(a, b), max(a, b)
    return (hi << 35) | (lo << 6) | spline_type


def is_harbour(aid: int) -> bool:
    return aid < INTERMEDIATE_BASE and bool(aid & HARBOUR_FLAG)


# ---------------------------------------------------------------------------
# Naval layer
# ---------------------------------------------------------------------------

def naval_layer(net: Network) -> Network:
    """The harbour hubs, naval strips with their intermediates, and their lookups."""
    nav = Network()
    for sid, anchors in net.strips.items():
        if sid & 0xFF in NAVAL_TYPES:
            for aid in anchors:
                if not (is_harbour(aid) or aid >= INTERMEDIATE_BASE):
                    raise SystemExit(f"naval strip {sid} references land anchor {aid}")
            nav.strips[sid] = anchors
    used = {a for s in nav.strips.values() for a in s}
    for aid, pos in net.anchors.items():
        if is_harbour(aid) or (aid >= INTERMEDIATE_BASE and aid in used):
            nav.anchors[aid] = pos
    for k, sids in net.lookups.items():
        if all(s in nav.strips for s in sids):
            nav.lookups[k] = sids
    return nav


def check_naval(nav: Network, port_states: set[int], passable_seas: set[int]) -> list[str]:
    """Why the naval layer is stale for the current map (empty when it is current)."""
    harb = {(a & ~HARBOUR_FLAG) // 100 for a in nav.anchors if is_harbour(a)}
    want = port_states | passable_seas
    problems = []
    if not nav.strips:
        problems.append("no naval strips")
    if harb - want:
        problems.append(f"harbours of states that are not current ports or passable seas: {sorted(harb - want)}")
    if want - harb:
        problems.append(f"current ports or passable seas without a harbour: {sorted(want - harb)}")
    return problems


# ---------------------------------------------------------------------------
# Map inputs
# ---------------------------------------------------------------------------

@dataclass
class MapData:
    land_state: np.ndarray          # int32 state id per pixel, 0 where not land
    passable_state: np.ndarray      # same, 0 also on impassable provinces
    cost: np.ndarray                # float64 routing cost per land pixel (inf off land)
    hubs: dict[int, tuple[float, float]]  # land hub id -> locator (x, z)
    port_states: set[int]
    passable_seas: set[int]


def _hex_code(h: str) -> int:
    return int(h.lstrip("xX"), 16)


def parse_state_files() -> tuple[dict[int, dict], dict[int, dict]]:
    """``(land, sea)`` as ``{state id: {"provinces": [...], "impassable": set}}``."""
    land: dict[int, dict] = {}
    sea: dict[int, dict] = {}
    for f in sorted(STATE_DIR.glob("*.txt")):
        text = f.read_text(encoding="utf-8-sig")
        for m in re.finditer(r"(STATE_\w+)\s*=\s*\{(.*?)\n\}", text, re.S):
            body = m.group(2)
            sid = int(re.search(r"\bid\s*=\s*(\d+)", body).group(1))
            provs = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", body).group(1).replace('"', "").split()
            imp = re.search(r"\bimpassable\s*=\s*\{([^}]*)\}", body)
            rec = {
                "provinces": [_hex_code(p) for p in provs],
                "impassable": {_hex_code(p) for p in imp.group(1).replace('"', "").split()} if imp else set(),
            }
            target = sea if f.name.startswith("99_") else land
            if sid in land or sid in sea:
                raise SystemExit(f"duplicate state id {sid}")
            target[sid] = rec
    return land, sea


def read_locators() -> dict[int, tuple[float, float]]:
    """``{land hub id: (x, z)}`` from the five generated locator files."""
    hubs: dict[int, tuple[float, float]] = {}
    for k, slot in SLOTS.items():
        text = (LOCATOR_DIR / f"generated_map_object_locators_{k}.txt").read_text(encoding="utf-8-sig")
        for m in re.finditer(r"\bid=(\d+)\s+position=\{\s*(\S+)\s+\S+\s+(\S+)\s*\}", text):
            hubs[int(m.group(1)) * 100 + slot] = (float(m.group(2)), float(m.group(3)))
    return hubs


def load_map() -> MapData:
    land, sea = parse_state_files()
    rgb = read_rgb_png(PROVINCES_PNG)
    code = (rgb[..., 0].astype(np.int64) << 16) | (rgb[..., 1].astype(np.int64) << 8) | rgb[..., 2]
    uniq, inv = np.unique(code.ravel(), return_inverse=True)
    lut_all = np.zeros(len(uniq), dtype=np.int32)
    lut_pass = np.zeros(len(uniq), dtype=np.int32)
    lut_imp = np.zeros(len(uniq), dtype=bool)
    pos = {int(c): i for i, c in enumerate(uniq.tolist())}
    for sid, rec in land.items():
        for p in rec["provinces"]:
            i = pos.get(p)
            if i is None:
                raise SystemExit(f"state {sid}: province x{p:06X} is not in provinces.png")
            lut_all[i] = sid
            if p in rec["impassable"]:
                lut_imp[i] = True
            else:
                lut_pass[i] = sid
    inv = inv.reshape(code.shape)
    land_state = lut_all[inv]
    passable_state = lut_pass[inv]
    impassable = lut_imp[inv]

    h16 = read_gray16_png(HEIGHTMAP_PNG).astype(np.float64)
    fy, fx = h16.shape[0] // CANVAS_H, h16.shape[1] // CANVAS_W
    h = h16.reshape(CANVAS_H, fy, CANVAS_W, fx).mean(axis=(1, 3))
    gy, gx = np.gradient(h)
    cost = 1.0 + SLOPE_WEIGHT * np.hypot(gx, gy)
    cost[impassable] *= IMPASSABLE_COST
    cost[land_state == 0] = np.inf

    hubs = read_locators()
    port_states = {hid // 100 for hid in hubs if hid % 100 == SLOTS["port"]}
    passable_seas = {sid for sid, rec in sea.items() if not set(rec["provinces"]) <= rec["impassable"]}
    for hid in hubs:
        if hid // 100 not in land:
            raise SystemExit(f"locator hub {hid}: state {hid // 100} is not a land state")
    return MapData(land_state, passable_state, cost, hubs, port_states, passable_seas)


def adjacent_pairs(passable_state: np.ndarray) -> list[tuple[int, int]]:
    """State pairs sharing a pixel edge between passable provinces (x wraps under WRAP_X)."""
    s = passable_state
    parts = [(s[:, :-1], s[:, 1:]), (s[:-1, :], s[1:, :])]
    if WRAP_X:
        parts.append((s[:, -1:], s[:, :1]))
    found: set[int] = set()
    for a, b in parts:
        m = (a != b) & (a > 0) & (b > 0)
        lo = np.minimum(a[m], b[m]).astype(np.int64)
        hi = np.maximum(a[m], b[m]).astype(np.int64)
        found.update(np.unique((lo << 32) | hi).tolist())
    return sorted((p >> 32, p & 0xFFFFFFFF) for p in found)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def hub_pixel(xz: tuple[float, float]) -> tuple[int, int]:
    """(row, col) of a locator."""
    x, z = xz
    return int(round(CANVAS_H - z - 0.5)), int(round(x - 0.5)) % CANVAS_W


def wrap_dist(p: tuple[float, float], q: tuple[float, float]) -> float:
    dx = abs(p[0] - q[0])
    if WRAP_X:
        dx = min(dx, CANVAS_W - dx)
    return math.hypot(dx, p[1] - q[1])


class Router:
    def __init__(self, md: MapData) -> None:
        self.md = md
        ys, xs = np.nonzero(md.land_state)
        sids = md.land_state[ys, xs]
        self.cols: dict[int, np.ndarray] = {}
        self.rows: dict[int, tuple[int, int]] = {}
        order = np.argsort(sids, kind="stable")
        sids, ys, xs = sids[order], ys[order], xs[order]
        cuts = np.flatnonzero(np.diff(sids)) + 1
        for a, b in zip(np.concatenate(([0], cuts)), np.concatenate((cuts, [len(sids)]))):
            sid = int(sids[a])
            self.cols[sid] = np.unique(xs[a:b])
            self.rows[sid] = (int(ys[a:b].min()), int(ys[a:b].max()))
        self._windows: dict[tuple[int, ...], tuple[int, int, int, int]] = {}
        self._labels: dict[tuple[int, ...], np.ndarray] = {}

    def _component(self, states: tuple[int, ...], p: tuple[int, int]) -> int:
        """8-connected piece of the states' land holding window pixel ``p`` (the moves MCP makes)."""
        if states not in self._labels:
            start, span, r0, r1 = self._windows[states]
            cols = (np.arange(span) + start) % CANVAS_W
            mask = np.isin(self.md.land_state[r0:r1 + 1][:, cols], states)
            self._labels[states] = ndimage.label(mask, structure=np.ones((3, 3), dtype=bool))[0]
        return int(self._labels[states][p])

    def _window(self, states: tuple[int, ...]) -> tuple[int, int, int, int]:
        """(shift, x width, row0, row1): columns rolled so the states' widest empty gap is the seam."""
        cols = np.unique(np.concatenate([self.cols[s] for s in states]))
        if WRAP_X and len(cols) > 1:
            gaps = np.diff(np.concatenate((cols, [cols[0] + CANVAS_W])))
            g = int(np.argmax(gaps))
            start = int(cols[(g + 1) % len(cols)])
        else:
            start = int(cols[0])
        span = int(((cols - start) % CANVAS_W).max()) + 1 if WRAP_X else int(cols[-1] - cols[0]) + 1
        r0 = min(self.rows[s][0] for s in states)
        r1 = max(self.rows[s][1] for s in states)
        return start, span, r0, r1

    def route(self, states: tuple[int, ...], a: int, b: int) -> list[tuple[float, float]] | None:
        """Anchor points (x, z) from hub ``a`` to hub ``b``, ends included; ``None`` if unroutable."""
        md = self.md
        if states not in self._windows:
            self._windows[states] = self._window(states)
        start, span, r0, r1 = self._windows[states]
        h = r1 + 1 - r0
        pa, pb = hub_pixel(md.hubs[a]), hub_pixel(md.hubs[b])
        sa = (pa[0] - r0, (pa[1] - start) % CANVAS_W)
        sb = (pb[0] - r0, (pb[1] - start) % CANVAS_W)
        for p in (sa, sb):
            if not (0 <= p[0] < h and 0 <= p[1] < span) or int(md.land_state[p[0] + r0, (p[1] + start) % CANVAS_W]) not in states:
                return None
        if self._component(states, sa) != self._component(states, sb):
            return None  # the hubs are on separate pieces of land
        path = None
        for margin in ROUTE_MARGINS_PX:
            # Search a box around the two hubs first, growing it only when the path needs more room.
            y0 = 0 if margin is None else max(0, min(sa[0], sb[0]) - margin)
            x0 = 0 if margin is None else max(0, min(sa[1], sb[1]) - margin)
            y1 = h if margin is None else min(h, max(sa[0], sb[0]) + margin + 1)
            x1 = span if margin is None else min(span, max(sa[1], sb[1]) + margin + 1)
            cols = (np.arange(x0, x1) + start) % CANVAS_W
            box = md.cost[r0 + y0:r0 + y1][:, cols]
            box[~np.isin(md.land_state[r0 + y0:r0 + y1][:, cols], states)] = np.inf
            ba, bb = (sa[0] - y0, sa[1] - x0), (sb[0] - y0, sb[1] - x0)
            mcp = MCP_Geometric(box, fully_connected=True)
            cum, _ = mcp.find_costs([ba], [bb])
            if np.isfinite(cum[bb]):
                path = np.asarray(mcp.traceback(bb), dtype=np.float64)  # (row, col) from ba to bb
                pts = rdp(path, RDP_EPS_PX, ~np.isfinite(box) | (box >= IMPASSABLE_COST)) + (y0, x0)
                break
            if (y1 - y0, x1 - x0) == (h, span):
                break
        if path is None:
            return None
        pts = resample(pts, ANCHOR_SPACING_PX)
        out = []
        for r, c in pts[1:-1]:
            x = (c + start) % CANVAS_W + 0.5
            z = CANVAS_H - (r + r0) - 0.5
            out.append((round(x, 2), round(z, 2)))
        return [md.hubs[a]] + out + [md.hubs[b]]


def _blocked_on_chord(p: np.ndarray, q: np.ndarray, blocked: np.ndarray) -> int:
    """Blocked pixels the straight segment ``p``-``q`` (row, col) passes over."""
    n = max(1, int(math.ceil(max(abs(q[0] - p[0]), abs(q[1] - p[1])))) * 2)
    t = np.linspace(0.0, 1.0, n + 1)
    rows = np.rint(p[0] + (q[0] - p[0]) * t).astype(np.int64)
    cols = np.rint(p[1] + (q[1] - p[1]) * t).astype(np.int64)
    cells = np.unique(rows * blocked.shape[1] + cols)
    return int(blocked.ravel()[cells].sum())


def rdp(pts: np.ndarray, eps: float, blocked: np.ndarray) -> np.ndarray:
    """Ramer-Douglas-Peucker on a pixel path, iterative; keeps both ends.

    A span is also split when its chord passes over more ``blocked`` pixels
    (off-state or impassable) than the path itself does there, so straightening
    a path that hugs a narrow pass never cuts across the mountain beside it.
    """
    idx = pts.astype(np.int64)
    on_path = blocked[idx[:, 0], idx[:, 1]]
    keep = np.zeros(len(pts), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        seg = pts[j] - pts[i]
        rel = pts[i + 1:j] - pts[i]
        n = math.hypot(*seg)
        d = np.abs(seg[0] * rel[:, 1] - seg[1] * rel[:, 0]) / n if n else np.hypot(rel[:, 0], rel[:, 1])
        k = int(np.argmax(d))
        if d[k] > eps or _blocked_on_chord(pts[i], pts[j], blocked) > int(on_path[i:j + 1].sum()):
            if d[k] == 0:
                k = (j - i) // 2 - 1  # collinear but blocked: split at the middle
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return pts[keep]


def resample(pts: np.ndarray, spacing: float) -> np.ndarray:
    """Insert evenly spaced points so no two consecutive points are more than ``spacing`` apart."""
    out = [pts[0]]
    for p, q in zip(pts[:-1], pts[1:]):
        n = max(1, math.ceil(math.hypot(*(q - p)) / spacing))
        for t in range(1, n + 1):
            out.append(p + (q - p) * (t / n))
    return np.asarray(out)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

@dataclass
class Stats:
    hubs: int = 0
    spokes: int = 0
    coincident: int = 0
    spokes_dropped: list = field(default_factory=list)
    pairs: int = 0
    routed: int = 0
    pairs_dropped: list = field(default_factory=list)


def build(md: MapData, nav: Network) -> tuple[Network, Stats]:
    st = Stats()
    router = Router(md)
    roads: list[tuple[int, int, list[tuple[float, float]]]] = []

    by_state: dict[int, list[int]] = {}
    for hid in sorted(md.hubs):
        by_state.setdefault(hid // 100, []).append(hid)

    for sid, hids in sorted(by_state.items()):
        city = sid * 100 + SLOTS["city"]
        if city not in md.hubs:
            continue
        for hid in hids:
            if hid == city:
                continue
            if md.hubs[hid] == md.hubs[city]:
                st.coincident += 1
                continue
            pts = router.route((sid,), city, hid)
            if pts is None:
                st.spokes_dropped.append((city, hid))
                continue
            roads.append((city, hid, pts))
            st.spokes += 1

    pairs = adjacent_pairs(md.passable_state)
    st.pairs = len(pairs)
    for sa, sb in pairs:
        cands = sorted(
            (wrap_dist(md.hubs[a], md.hubs[b]), min(a, b), max(a, b))
            for a in by_state.get(sa, []) for b in by_state.get(sb, [])
        )
        for _, lo, hi in cands:
            pts = router.route((sa, sb), lo, hi)
            if pts is not None:
                roads.append((lo, hi, pts))
                st.routed += 1
                break
        else:
            st.pairs_dropped.append((sa, sb))

    net = Network(dict(nav.anchors), dict(nav.strips), dict(nav.lookups))
    for hid, (x, z) in md.hubs.items():
        net.anchors[hid] = (f32(x), f32(z))
    st.hubs = len(md.hubs)
    next_inter = max([a for a in nav.anchors if a >= INTERMEDIATE_BASE], default=INTERMEDIATE_BASE - 1) + 1
    next_index = max([s >> 8 for s in nav.strips if s & 0xFF == LAND_SPLINE_TYPE], default=-1) + 1
    for lo, hi, pts in sorted(roads, key=lambda r: (min(r[0], r[1]), max(r[0], r[1]))):
        if lo > hi:
            lo, hi, pts = hi, lo, pts[::-1]
        ids = [lo]
        for x, z in pts[1:-1]:
            net.anchors[next_inter] = (f32(x), f32(z))
            ids.append(next_inter)
            next_inter += 1
        ids.append(hi)
        strip = (next_index << 8) | LAND_SPLINE_TYPE
        next_index += 1
        net.strips[strip] = ids
        k = lookup_key(lo, hi, LAND_SPLINE_TYPE)
        if k in net.lookups:
            raise SystemExit(f"duplicate lookup for hubs {lo}/{hi}")
        net.lookups[k] = [strip]
    return net, st


# ---------------------------------------------------------------------------
# Render (dev-only, scratchpad/)
# ---------------------------------------------------------------------------

OLD_WORLD_BOX = (3500, 150, 4800, 1350)  # x0 y0 x1 y1, provinces.png pixels
_STRIP_RGB = {0: (235, 200, 40), 1: (210, 30, 30), 2: (40, 90, 230), 3: (150, 60, 200)}


def render(md: MapData, net: Network) -> list[Path]:
    from PIL import Image, ImageDraw

    land = md.land_state > 0
    base = np.full((CANVAS_H, CANVAS_W, 3), (205, 222, 238), dtype=np.uint8)
    shade = (md.land_state % 4).astype(np.int32) * 10
    for c, v in enumerate((214, 206, 186)):
        base[..., c] = np.where(land, v - shade, base[..., c])
    edge = np.zeros_like(land)
    s = md.land_state
    edge[:, 1:] |= s[:, 1:] != s[:, :-1]
    edge[1:, :] |= s[1:, :] != s[:-1, :]
    base[edge & land] = (150, 140, 120)
    im = Image.fromarray(base)
    d = ImageDraw.Draw(im)

    def px(aid: int) -> tuple[float, float]:
        x, z = (struct.unpack("<f", v)[0] for v in net.anchors[aid])
        return x - 0.5, CANVAS_H - z - 0.5

    for sid, aids in sorted(net.strips.items()):
        pts = [px(a) for a in aids]
        rgb = _STRIP_RGB.get(sid & 0xFF, (0, 0, 0))
        for p, q in zip(pts[:-1], pts[1:]):
            if abs(p[0] - q[0]) > CANVAS_W / 2:
                continue  # seam crossing
            d.line([p, q], fill=rgb, width=2)
    for aid in net.anchors:
        if aid < INTERMEDIATE_BASE:
            x, y = px(aid)
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(20, 20, 20) if not is_harbour(aid) else (20, 60, 160))
    SCRATCH_DIR.mkdir(exist_ok=True)
    full = SCRATCH_DIR / "spline_network_preview.png"
    half = SCRATCH_DIR / "spline_network_preview_half.png"
    crop = SCRATCH_DIR / "spline_network_preview_old_world.png"
    im.save(full)
    im.resize((CANVAS_W // 2, CANVAS_H // 2), Image.LANCZOS).save(half)
    im.crop(OLD_WORLD_BOX).save(crop)
    return [full, half, crop]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def compute(naval_source: Path) -> tuple[bytes, MapData, Network, Stats]:
    data = naval_source.read_bytes() if naval_source.is_file() else b""
    if not data:
        raise SystemExit(f"{naval_source}: missing or empty; bootstrap the naval layer with --naval-from")
    try:
        nav = naval_layer(parse(data))
    except (ValueError, KeyError, struct.error) as e:
        raise SystemExit(f"{naval_source}: does not decode ({e})")
    md = load_map()
    problems = check_naval(nav, md.port_states, md.passable_seas)
    if problems:
        raise SystemExit(
            f"{naval_source}: naval layer is stale for the current map; re-run the desktop naval step "
            "(mapgen/MAP_RUNBOOK.md, 'Route network'):\n  " + "\n  ".join(problems)
        )
    net, st = build(md, nav)
    return encode(net), md, net, st


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if the shipped file is not current")
    ap.add_argument("--naval-from", type=Path, help="take the naval layer from this splnet (default: the shipped file)")
    ap.add_argument("--render", action="store_true", help="also write review previews to scratchpad/")
    args = ap.parse_args(argv)
    if args.check and args.naval_from:
        ap.error("--check reads the naval layer from the shipped file")

    out, md, net, st = compute(args.naval_from or OUT_PATH)
    rel = OUT_PATH.relative_to(MOD_ROOT)
    print(
        f"hubs {st.hubs}; spokes {st.spokes} (coincident skipped {st.coincident}, unroutable "
        f"{len(st.spokes_dropped)}); pairs {st.pairs} ({PAIR_RULE}), routed {st.routed}, dropped {len(st.pairs_dropped)}"
    )
    for a, b in st.spokes_dropped:
        print(f"  spoke unroutable: {a} -> {b}")
    for a, b in st.pairs_dropped:
        print(f"  pair dropped: {a} / {b}")
    rc = 0
    if args.check:
        if OUT_PATH.read_bytes() != out:
            print(f"STALE {rel}")
            rc = 1
    else:
        OUT_PATH.write_bytes(out)
        print(f"wrote {rel}  ({len(net.anchors)} anchors, {len(net.strips)} strips, {len(net.lookups)} lookups)")
    if args.render:
        for p in render(md, net):
            print(f"render {p.relative_to(MOD_ROOT)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
