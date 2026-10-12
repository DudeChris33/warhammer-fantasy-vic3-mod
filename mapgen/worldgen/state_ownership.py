"""Starting-ownership map: legend, render and read.

``mapgen/config/state_ownership.png`` is a hand-painted, flat-colour picture of
who owns each land state at the start date; this module is the one place that
knows how to turn an assignment into that picture (:func:`render`) and that
picture back into an assignment (:func:`read`). ``render_state_ownership.py``
and ``read_state_ownership.py`` are thin CLIs over it, and
``run_fixture.py --check`` round-trips it on the synthetic world.

Pixels are grouped by **province** (the province bitmap is the identity layer),
provinces by **state** (``map_data/state_regions/*.txt``). Anything not in a
land state's province list is water. The colour language is the legend
(``state_ownership_legend.json``): one exact RGB per owning tag plus four
reserved colours -- water, unowned land, out-of-scope placeholder land, and the
thin state-border line drawn on top. Border and water pixels never vote.

Deterministic and pure: no clock, no filesystem beyond the paths handed in, ties
broken by sorted owner token.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

Color = tuple[int, int, int]

RESERVED = ("water", "unowned", "placeholder", "border")
#: Pseudo-owners a province can vote for besides a tag.
UNOWNED = "unowned"
PLACEHOLDER = "placeholder"
_TAG_RE = re.compile(r"^[A-Z]{3}$")
_STATE_HEADER = re.compile(r"^(STATE_\w+)\s*=\s*\{", re.M)
_HEX = re.compile(r"x[0-9A-Fa-f]{6}")


class OwnershipError(ValueError):
    """A legend, assignment or painted map that cannot be used as given."""


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _pack(rgb: np.ndarray) -> np.ndarray:
    """``(H, W, 3)`` uint8 -> ``(H, W)`` uint32 ``0xRRGGBB``."""
    a = rgb.astype(np.uint32)
    return (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]


def _unpack(value: int) -> Color:
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


def _pack1(color: Color) -> int:
    return (int(color[0]) << 16) | (int(color[1]) << 8) | int(color[2])


def hex_token(color: Color) -> str:
    return "x{:02X}{:02X}{:02X}".format(*color)


def _token_color(token: str) -> Color:
    v = int(token[1:], 16)
    return _unpack(v)


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Legend:
    """Reserved colours plus one colour per owning tag."""

    reserved: dict[str, Color]
    tags: dict[str, Color]
    proposed: frozenset[str] = frozenset()
    names: dict[str, str] | None = None   # tag -> country/polity name (legend 'name')

    def color_owner(self) -> dict[int, str]:
        """Packed colour -> owner token (a tag, ``unowned`` or ``placeholder``).
        Water and border are not owners and are excluded."""
        out = {_pack1(c): t for t, c in self.tags.items()}
        out[_pack1(self.reserved[UNOWNED])] = UNOWNED
        out[_pack1(self.reserved[PLACEHOLDER])] = PLACEHOLDER
        return out

    def owner_color(self, owner: str) -> Color:
        if owner in (UNOWNED, PLACEHOLDER):
            return self.reserved[owner]
        if owner not in self.tags:
            raise OwnershipError(f"owner {owner!r} is not in the legend")
        return self.tags[owner]


def _color(value, where: str) -> Color:
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255 for v in value)):
        raise OwnershipError(f"{where}: colour must be [r, g, b] integers 0-255, got {value!r}")
    return (value[0], value[1], value[2])


def parse_legend(doc: dict, source: str = "legend") -> Legend:
    """Validate a decoded legend document. Every colour (reserved and tag) must
    be distinct: two owners sharing an RGB could not be told apart on read."""
    reserved_doc = doc.get("reserved")
    tags_doc = doc.get("tags")
    if not isinstance(reserved_doc, dict) or set(reserved_doc) != set(RESERVED):
        raise OwnershipError(f"{source}: 'reserved' must have exactly the keys {list(RESERVED)}")
    if not isinstance(tags_doc, dict) or not tags_doc:
        raise OwnershipError(f"{source}: 'tags' must be a non-empty object")
    reserved = {k: _color(reserved_doc[k], f"{source}: reserved.{k}") for k in RESERVED}
    tags: dict[str, Color] = {}
    proposed: set[str] = set()
    names: dict[str, str] = {}
    for tag, entry in tags_doc.items():
        if not _TAG_RE.match(tag):
            raise OwnershipError(f"{source}: {tag!r} is not a 3-letter uppercase tag")
        if not isinstance(entry, dict) or "color" not in entry:
            raise OwnershipError(f"{source}: tag {tag} needs an object with a 'color'")
        tags[tag] = _color(entry["color"], f"{source}: tag {tag}")
        if isinstance(entry.get("name"), str):
            names[tag] = entry["name"]
        if entry.get("proposed") is True:
            proposed.add(tag)
    seen: dict[Color, str] = {}
    for name, c in [(f"reserved.{k}", v) for k, v in reserved.items()] + list(tags.items()):
        if c in seen:
            raise OwnershipError(f"{source}: colour {list(c)} is used by both {seen[c]} and {name}")
        seen[c] = name
    return Legend(reserved, tags, frozenset(proposed), names)


def load_legend(path: Path) -> Legend:
    return parse_legend(json.loads(Path(path).read_text(encoding="utf-8")), source=Path(path).name)


# ---------------------------------------------------------------------------
# Land states
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class State:
    key: str
    id: int
    provinces: tuple[str, ...]   # "xRRGGBB", file order


def _match_brace(text: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise OwnershipError("unbalanced braces in a state file")


def parse_state_text(text: str) -> list[State]:
    states: list[State] = []
    idx = 0
    while True:
        m = _STATE_HEADER.search(text, idx)
        if not m:
            break
        open_idx = text.index("{", m.end() - 1)
        close_idx = _match_brace(text, open_idx)
        body = text[open_idx + 1:close_idx]
        idm = re.search(r"\bid\s*=\s*(\d+)", body)
        pm = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", body)
        if not idm or not pm:
            raise OwnershipError(f"{m.group(1)}: missing id or provinces")
        states.append(State(m.group(1), int(idm.group(1)),
                            tuple(t.upper().replace("X", "x", 1) for t in _HEX.findall(pm.group(1)))))
        idx = close_idx + 1
    return states


def load_land_states(state_regions_dir: Path) -> list[State]:
    """Every land state, sorted by key. ``99_seas.txt`` (sea states) is skipped;
    the land files are the ``NN_*.txt`` with NN below 99."""
    states: list[State] = []
    for path in sorted(Path(state_regions_dir).glob("*.txt")):
        if path.name.startswith("99_"):
            continue
        states.extend(parse_state_text(path.read_text(encoding="utf-8-sig")))
    keys = [s.key for s in states]
    if len(set(keys)) != len(keys):
        raise OwnershipError("duplicate STATE key across state_regions files")
    return sorted(states, key=lambda s: s.key)


class Layout:
    """The province bitmap grouped into land provinces and states.

    ``prov`` is per-pixel ``0`` (water / not in any land state) or ``1 + i`` for
    the i-th province in ``province_tokens``; ``state_of_prov[i]`` indexes
    ``states``.
    """

    def __init__(self, prov_rgb: np.ndarray, states: list[State]):
        if prov_rgb.ndim != 3 or prov_rgb.shape[2] != 3:
            raise OwnershipError("province bitmap must be (H, W, 3)")
        self.height, self.width = prov_rgb.shape[:2]
        self.states = states
        tokens: list[str] = []
        state_of: list[int] = []
        seen: dict[str, str] = {}
        for si, s in enumerate(states):
            for tok in s.provinces:
                if tok in seen:
                    raise OwnershipError(f"province {tok} is in both {seen[tok]} and {s.key}")
                seen[tok] = s.key
                tokens.append(tok)
                state_of.append(si)
        packed_tokens = np.array([_pack1(_token_color(t)) for t in tokens], dtype=np.uint32)
        order = np.argsort(packed_tokens, kind="stable")
        sorted_packed = packed_tokens[order]
        pix = _pack(prov_rgb)
        pos = np.searchsorted(sorted_packed, pix)
        pos[pos >= len(sorted_packed)] = 0
        hit = sorted_packed[pos] == pix
        self.prov = np.where(hit, order[pos] + 1, 0).astype(np.int32)
        self.province_tokens = tokens
        self.state_of_prov = np.array(state_of, dtype=np.int32)
        self.state_index = np.where(self.prov > 0, self.state_of_prov[np.maximum(self.prov - 1, 0)] + 1, 0).astype(np.int32)

    def province_pixel_counts(self) -> np.ndarray:
        return np.bincount(self.prov.ravel(), minlength=len(self.province_tokens) + 1)[1:]


def border_mask(state_index: np.ndarray, width: int = 1, wrap_x: bool = True) -> np.ndarray:
    """Land pixels on a state boundary. ``width=1`` marks only the pixel of the
    higher-indexed state of each touching pair (a 1 px line); ``width=2`` marks
    both sides. Land/water edges are never borders."""
    s = state_index
    mask = np.zeros(s.shape, dtype=bool)

    def mark(a: np.ndarray, b: np.ndarray, ma: np.ndarray, mb: np.ndarray) -> None:
        # a, b: touching pixel values; ma, mb: writable views of their mask cells
        differ = (a != b) & (a > 0) & (b > 0)
        if width >= 2:
            ma |= differ
            mb |= differ
        else:
            ma |= differ & (a > b)
            mb |= differ & (b > a)

    mark(s[:, :-1], s[:, 1:], mask[:, :-1], mask[:, 1:])
    mark(s[:-1, :], s[1:, :], mask[:-1, :], mask[1:, :])
    if wrap_x:
        mark(s[:, -1:], s[:, :1], mask[:, -1:], mask[:, :1])
    return mask


def placeholder_state_keys(states: list[State], placeholder_provinces: set[str]) -> set[str]:
    """States whose provinces are out-of-scope placeholders. A state mixing
    placeholder and drawn provinces is a generator bug, so it is an error."""
    out: set[str] = set()
    for s in states:
        flags = {t in placeholder_provinces for t in s.provinces}
        if flags == {True}:
            out.add(s.key)
        elif len(flags) > 1:
            raise OwnershipError(f"{s.key}: mixes placeholder and drawn provinces")
    return out


def load_state_names(mod_root: Path) -> dict[str, str]:
    """``STATE_*`` key -> English display name, from the generated map loc."""
    path = Path(mod_root) / "localization" / "replace" / "english" / "map" / "states_l_english.yml"
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r'\s*(STATE_\w+):\d*\s+"(.*?)"', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def load_inputs(mod_root: Path):
    """Read the committed map data: ``(layout, placeholder_states, ids_anchor)``.

    ``ids_anchor[key] = (state id, naming anchor)``. The naming anchor is the
    ``anchor_x``/``anchor_y`` of the state's row in ``land_regions_worksheet.csv``
    (rows are keyed by state id); ``None`` where the state has no row yet.
    """
    import csv

    from . import raster

    mod_root = Path(mod_root)
    states = load_land_states(mod_root / "map_data" / "state_regions")
    layout = Layout(raster.read_rgb_png(mod_root / "map_data" / "provinces.png"), states)
    index = json.loads((mod_root / "mapgen" / "derived" / "provinces_index.json").read_text(encoding="utf-8"))
    placeholder = {c["hex"].upper().replace("X", "x", 1) for c in index["cells"]
                   if c["kind"] == "land" and c.get("placeholder")}
    anchors: dict[int, list[int]] = {}
    with open(mod_root / "mapgen" / "config" / "land_regions_worksheet.csv", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            anchors[int(row["region_id"])] = [int(row["anchor_x"]), int(row["anchor_y"])]
    ids_anchor = {s.key: (s.id, anchors.get(s.id)) for s in states}
    return layout, placeholder_state_keys(states, placeholder), ids_anchor


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def province_owners(layout: Layout, assignment: dict, placeholder_states: set[str],
                    legend: Legend) -> list[str]:
    """Owner token per province (``layout.province_tokens`` order).

    ``assignment[state_key]`` is a token, or ``{province_token: token}`` for a
    split state. Every non-placeholder state must be present; placeholder
    states must be absent (they always take the placeholder colour).
    """
    keys = {s.key for s in layout.states}
    unknown = sorted(set(assignment) - keys)
    if unknown:
        raise OwnershipError(f"assignment names unknown states: {unknown[:5]}")
    bad_ph = sorted(k for k in assignment if k in placeholder_states)
    if bad_ph:
        raise OwnershipError(f"placeholder (out-of-scope) states must not be assigned: {bad_ph[:5]}")
    missing = sorted(keys - placeholder_states - set(assignment))
    if missing:
        raise OwnershipError(f"{len(missing)} drawn state(s) have no owner (first: {missing[:5]})")
    out: list[str] = []
    tok_index = {t: i for i, t in enumerate(layout.province_tokens)}
    per_prov: dict[int, str] = {}
    for key, val in assignment.items():
        si = next(i for i, s in enumerate(layout.states) if s.key == key)
        st = layout.states[si]
        if isinstance(val, str):
            _check_owner(val, legend, key)
            for tok in st.provinces:
                per_prov[tok_index[tok]] = val
        else:
            if set(val) != set(st.provinces):
                raise OwnershipError(f"{key}: a split must name every one of its {len(st.provinces)} provinces")
            for tok, owner in val.items():
                _check_owner(owner, legend, key)
                per_prov[tok_index[tok]] = owner
    for i, tok in enumerate(layout.province_tokens):
        si = int(layout.state_of_prov[i])
        if layout.states[si].key in placeholder_states:
            out.append(PLACEHOLDER)
        else:
            out.append(per_prov[i])
    return out


def _check_owner(owner: str, legend: Legend, key: str) -> None:
    if owner == PLACEHOLDER:
        raise OwnershipError(f"{key}: 'placeholder' is reserved for out-of-scope states")
    if owner != UNOWNED and owner not in legend.tags:
        raise OwnershipError(f"{key}: owner {owner!r} is not a tag in the legend")


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render(layout: Layout, owners: list[str], legend: Legend, border_width: int = 1,
           wrap_x: bool = True) -> np.ndarray:
    """The painted map: flat exact-RGB fills, water elsewhere, border on top."""
    palette = np.zeros((len(owners) + 1, 3), dtype=np.uint8)
    palette[0] = legend.reserved["water"]
    for i, o in enumerate(owners):
        palette[i + 1] = legend.owner_color(o)
    img = palette[layout.prov]
    img[border_mask(layout.state_index, border_width, wrap_x)] = legend.reserved["border"]
    return img


def adopt_new_states(layout: Layout, painted: np.ndarray, legend: Legend,
                     placeholder_states: set[str], border_width: int = 1,
                     wrap_x: bool = True) -> tuple[np.ndarray, list[str]]:
    """Paint as unowned every drawn state the map still shows as a placeholder.

    Land that comes into scope is drawn on a map painted while it was out of
    scope, so its states sit in the placeholder colour and the read refuses
    them. A drawn state is adopted when none of its pixels carries an owner
    colour other than the placeholder's: it is filled with the unowned colour
    and its state borders are redrawn. Every other pixel is left as painted, so
    a repaint is never disturbed. A drawn state that mixes the placeholder
    colour with a real owner is not touched: that is a paint error for the read
    to report. Returns ``(image, adopted state keys)``.
    """
    if painted.shape[:2] != (layout.height, layout.width):
        raise OwnershipError(
            f"painted map is {painted.shape[1]}x{painted.shape[0]}, expected {layout.width}x{layout.height}")
    packed = _pack(painted)
    n = len(layout.states)
    si = layout.state_index
    ph = packed == _pack1(legend.reserved[PLACEHOLDER])
    other = np.isin(packed, np.array(
        [k for k, o in legend.color_owner().items() if o != PLACEHOLDER], dtype=np.uint32))
    n_ph = np.bincount(si[ph & (si > 0)], minlength=n + 1)
    n_other = np.bincount(si[other & (si > 0)], minlength=n + 1)
    adopted = [i for i, s in enumerate(layout.states)
               if s.key not in placeholder_states and n_ph[i + 1] > 0 and n_other[i + 1] == 0]
    if not adopted:
        return painted, []
    img = painted.copy()
    mine = np.isin(si, np.array(adopted, dtype=np.int32) + 1)
    img[mine] = legend.reserved[UNOWNED]
    img[border_mask(si, border_width, wrap_x) & mine] = legend.reserved["border"]
    return img, [layout.states[i].key for i in adopted]


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def check_legend_colours(painted: np.ndarray, legend: Legend) -> None:
    """Hard error on any colour that is neither reserved nor a tag's."""
    packed = _pack(painted)
    values, counts = np.unique(packed, return_counts=True)
    known = {_pack1(c) for c in legend.reserved.values()} | {_pack1(c) for c in legend.tags.values()}
    for v, n in zip(values.tolist(), counts.tolist()):
        if v not in known:
            ys, xs = np.nonzero(packed == v)
            raise OwnershipError(
                f"colour {list(_unpack(v))} ({hex_token(_unpack(v))}) is not in the legend: "
                f"{n} px, first at x={int(xs[0])} y={int(ys[0])}")


def vote(layout: Layout, painted: np.ndarray, legend: Legend) -> list[str]:
    """Plurality owner per province, ignoring border and water pixels.

    Ties go to the lexicographically smallest owner token. A province with no
    votable pixel at all is a hard error (it cannot be read)."""
    check_legend_colours(painted, legend)
    owner_of = legend.color_owner()
    tokens = sorted(set(owner_of.values()))            # deterministic column order
    col = {t: i for i, t in enumerate(tokens)}
    lut_keys = np.array(sorted(owner_of), dtype=np.uint32)
    lut_cols = np.array([col[owner_of[int(k)]] for k in lut_keys], dtype=np.int64)
    packed = _pack(painted)
    pos = np.searchsorted(lut_keys, packed)
    pos[pos >= len(lut_keys)] = 0
    is_owner = (lut_keys[pos] == packed) & (layout.prov > 0)
    prov = layout.prov[is_owner].astype(np.int64) - 1
    cols = lut_cols[pos[is_owner]]
    n_prov = len(layout.province_tokens)
    table = np.bincount(prov * len(tokens) + cols, minlength=n_prov * len(tokens)).reshape(n_prov, len(tokens))
    out: list[str] = []
    for i in range(n_prov):
        row = table[i]
        if row.sum() == 0:
            st = layout.states[int(layout.state_of_prov[i])].key
            raise OwnershipError(
                f"province {layout.province_tokens[i]} ({st}) has no votable pixel "
                f"(all border/water) -- repaint part of it")
        out.append(tokens[int(np.argmax(row))])         # argmax = first max = smallest token
    return out


def group_states(layout: Layout, prov_owners: list[str], placeholder_states: set[str],
                 ids_anchor: dict[str, tuple[int, list | None]]) -> dict:
    """Per-state records. ``ids_anchor[key] = (state id, naming anchor | None)``."""
    by_state: dict[int, list[tuple[str, str]]] = {}
    for i, tok in enumerate(layout.province_tokens):
        by_state.setdefault(int(layout.state_of_prov[i]), []).append((tok, prov_owners[i]))
    out: dict[str, dict] = {}
    for si, s in enumerate(layout.states):
        pairs = by_state[si]
        sid, anchor = ids_anchor[s.key]
        rec: dict = {"id": sid, "naming_anchor": anchor}
        is_ph = s.key in placeholder_states
        rec["scope"] = "placeholder" if is_ph else "drawn"
        distinct = sorted({o for _, o in pairs})
        if is_ph and distinct != [PLACEHOLDER]:
            raise OwnershipError(f"{s.key}: out-of-scope state painted with {distinct}; it must be the placeholder colour")
        if not is_ph and PLACEHOLDER in distinct:
            raise OwnershipError(f"{s.key}: drawn state painted with the placeholder colour")
        if len(distinct) == 1:
            rec["owner"] = distinct[0]
        else:
            rec["owners"] = [{"owner": o, "provinces": sorted(t for t, oo in pairs if oo == o)}
                             for o in distinct]
        out[s.key] = rec
    return out


def read(layout: Layout, painted: np.ndarray, legend: Legend, placeholder_states: set[str],
         ids_anchor: dict[str, tuple[int, list | None]]) -> dict:
    if painted.shape[:2] != (layout.height, layout.width):
        raise OwnershipError(
            f"painted map is {painted.shape[1]}x{painted.shape[0]}, expected {layout.width}x{layout.height}")
    owners = vote(layout, painted, legend)
    return group_states(layout, owners, placeholder_states, ids_anchor)


def to_json(doc: dict) -> str:
    """Byte-stable JSON: sorted keys, 1-space indent, LF, trailing newline."""
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def assignment_of(states_doc: dict) -> dict:
    """``read`` output -> the assignment shape :func:`province_owners` takes
    (drawn states only), for round-trip comparison."""
    out: dict = {}
    for key, rec in states_doc.items():
        if rec["scope"] != "drawn":
            continue
        if "owner" in rec:
            out[key] = rec["owner"]
        else:
            out[key] = {tok: o["owner"] for o in rec["owners"] for tok in o["provinces"]}
    return out


def normalize_assignment(assignment: dict, layout: Layout) -> dict:
    """Collapse a split whose provinces all share one owner to a plain token, so
    an assignment compares equal to what :func:`read` reports."""
    out: dict = {}
    for key, val in assignment.items():
        if isinstance(val, dict) and len(set(val.values())) == 1:
            out[key] = next(iter(val.values()))
        else:
            out[key] = val
    return out


# ---------------------------------------------------------------------------
# Review render
# ---------------------------------------------------------------------------

def review_render(painted: np.ndarray, layout: Layout, prov_owners: list[str], legend: Legend,
                  scale: float = 0.5, crop: tuple[int, int, int, int] | None = None,
                  numbers: bool = False, labels: str = "country", state_names: dict[str, str] | None = None,
                  name_chars: int = 12):
    """Annotated review picture: the painted map at ``scale`` (nearest), tag codes
    at each drawn state's centroid, and a legend panel of the owners in use.
    ``labels`` picks the label: ``country`` (default) = first ``name_chars`` (12) characters
    of the owning country's name from the legend, ``tag`` = the tag code, ``state`` =
    the state's localized name (``state_names``: state key -> name).
    With ``numbers`` each label gains a second line: the state's numeric ``id``
    (the ``id =`` in ``map_data/state_regions/``, also in ``state_ownership.json``).

    ``crop`` is ``(x0, y0, x1, y1)`` in canvas pixels (default: the bounding box
    of the drawn land plus a margin). Returns a PIL image."""
    from PIL import Image, ImageDraw, ImageFont

    owner_of_prov = np.array([""] + prov_owners, dtype=object)
    drawn_mask = np.array([False] + [o != PLACEHOLDER for o in prov_owners])[layout.prov]
    if crop is None:
        ys, xs = np.nonzero(drawn_mask)
        pad = 24
        crop = (max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0),
                min(int(xs.max()) + pad + 1, layout.width), min(int(ys.max()) + pad + 1, layout.height))
    x0, y0, x1, y1 = crop
    img = Image.fromarray(np.ascontiguousarray(painted[y0:y1, x0:x1]), "RGB")
    sw, sh = max(int((x1 - x0) * scale), 1), max(int((y1 - y0) * scale), 1)
    img = img.resize((sw, sh), Image.NEAREST)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=11)

    sidx = layout.state_index[y0:y1, x0:x1]
    yy, xx = np.nonzero(sidx > 0)
    flat = sidx[yy, xx]
    order = np.argsort(flat, kind="stable")
    flat, yy, xx = flat[order], yy[order], xx[order]
    bounds = np.flatnonzero(np.diff(flat)) + 1
    starts = np.concatenate(([0], bounds))
    ends = np.concatenate((bounds, [len(flat)]))
    state_owner: dict[int, str] = {}
    for i, tok in enumerate(layout.province_tokens):
        si = int(layout.state_of_prov[i])
        state_owner.setdefault(si, prov_owners[i])
    used: dict[str, int] = {}
    for a, b in zip(starts, ends):
        si = int(flat[a]) - 1
        owner = state_owner[si]
        if owner == PLACEHOLDER:
            continue
        cx, cy = float(xx[a:b].mean()), float(yy[a:b].mean())
        # snap to the state's own pixel nearest the centroid so concave states still label inside
        d = (xx[a:b] - cx) ** 2 + (yy[a:b] - cy) ** 2
        j = int(np.argmin(d))
        px, py = int(xx[a:b][j] * scale), int(yy[a:b][j] * scale)
        code = {UNOWNED: "--"}.get(owner, owner)
        if labels == "country":
            code = "Unowned" if owner == UNOWNED else (legend.names or {}).get(owner, owner)[:name_chars]
        elif labels == "state":
            code = (state_names or {}).get(layout.states[si].key, layout.states[si].key)[:name_chars]
        used[owner] = used.get(owner, 0) + 1
        r, g, bl = legend.owner_color(owner)
        ink = (0, 0, 0) if (0.299 * r + 0.587 * g + 0.114 * bl) > 140 else (255, 255, 255)
        tw = draw.textlength(code, font=font)
        draw.text((px - tw / 2, py - 6), code, fill=ink, font=font)
        if numbers:
            num = str(layout.states[si].id)
            draw.text((px - draw.textlength(num, font=font) / 2, py + 5), num, fill=ink, font=font)

    entries = sorted(used.items())
    col_w, row_h = 210, 16
    per_col = max(len(entries) // 3 + 1, 1)
    panel_h = per_col * row_h + 12
    out = Image.new("RGB", (max(sw, col_w * 3 + 12), sh + panel_h), legend.reserved["water"])
    out.paste(img, (0, 0))
    d2 = ImageDraw.Draw(out)
    for n, (owner, count) in enumerate(entries):
        cx = 6 + (n // per_col) * col_w
        cy = sh + 6 + (n % per_col) * row_h
        d2.rectangle((cx, cy + 1, cx + 12, cy + 12), fill=legend.owner_color(owner), outline=(0, 0, 0))
        label = "unowned" if owner == UNOWNED else owner
        d2.text((cx + 18, cy), f"{label}  ({count})", fill=(255, 255, 255), font=font)
    return out
