"""Per-state land economics: the hand-authored worksheet, its fallback and its rules (board #3678).

One place for what ``generate_land_regions.py`` (emits it), ``validate_map.py``
(re-checks the emitted files) and ``render_land_economics_preview.py`` (draws it)
all need, so the three can never drift apart.

The worksheet, ``mapgen/config/land_economics_worksheet.csv``
-------------------------------------------------------------
Hand-authored like ``land_regions_worksheet.csv``: edited deliberately,
regenerated through (``generate_land_regions.py`` then
``generate_building_history.py``), never inferred from generator output. One
pre-seeded row per drawn state (343 at seeding), so the realm children fill
cells on an existing line and git merges stay line-stable; the loader does not
require the rows (an absent row is the same as an all-empty one).

* **Identity** (``IDENTITY_COLUMNS``): ``state_key`` is the canon ``STATE_<NAME>``
  block key (the primary key); ``anchor_x``/``anchor_y`` are the naming
  worksheet's anchor pixel for that state, verified by exact equality
  (:func:`check_worksheet_identity`) so a renamed state is recoverable
  (``generate_land_regions.py --rekey-economics``) instead of silently
  reattached. Never the transient STATE number, never a province colour.
  Identity columns are never value columns and belong to no epic's children.
* **Value columns** (``FARMLAND_COLUMNS``, this epic): ``arable_land`` (integer
  >= 0), ``subsistence_building`` (one of :data:`SUBSISTENCE_BUILDINGS`),
  ``arable_resources`` (space-separated building ids). An **empty cell means
  that column's default** (:func:`resolve_economics`), per column, so a row can
  carry only some columns. Empty ``arable_resources`` is therefore not
  expressible (vanilla ships none).
* **Notes** (``NOTE_COLUMNS``): ``arable_note`` / ``arable_source``, documentation
  only, never parsed.
* **Extension point**: #3688 appends its resource columns to ``KNOWN_COLUMNS``
  and its own resolve/check rules to this module. An unknown header is a hard
  error, never silently ignored.

Placeholders (out-of-scope land) never carry a row and always emit
:data:`DEFAULT_ECONOMICS`; they are classified by scope, never by key shape.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import NamedTuple

from . import schema

#: Today's placeholder economics, moved verbatim from ``generate_land_regions.py``.
#: Values only need to parse; ``capped_resources`` stays the placeholder until #3688.
DEFAULT_ECONOMICS = schema.Economics(
    subsistence_building="building_subsistence_farm",
    arable_land=10,
    arable_resources=["building_wheat_farm", "building_livestock_ranch"],
    capped_resources={"building_logging_camp": 10},
)


def default_economics() -> schema.Economics:
    """A fresh copy of :data:`DEFAULT_ECONOMICS` (the dataclass holds a list and a dict)."""
    d = DEFAULT_ECONOMICS
    return schema.Economics(d.subsistence_building, d.arable_land,
                            list(d.arable_resources), dict(d.capped_resources))


SUBSISTENCE_BUILDINGS = (
    "building_subsistence_farm", "building_subsistence_orchard", "building_subsistence_pasture",
    "building_subsistence_fishing_village", "building_subsistence_rice_farm",
)
FISHING_VILLAGE = "building_subsistence_fishing_village"
#: ``MASS_MIGRATION_TARGET_MIN_ARABLE_LAND`` in vanilla ``game/common/defines/00_defines.txt``
#: (the mod ships only ``00_wh_defines.txt``): below it a state is no mass-migration target.
MASS_MIGRATION_TARGET_MIN_ARABLE_LAND = 10

IDENTITY_COLUMNS = ("state_key", "anchor_x", "anchor_y")
FARMLAND_COLUMNS = ("arable_land", "subsistence_building", "arable_resources")
NOTE_COLUMNS = ("arable_note", "arable_source")
KNOWN_COLUMNS = (*IDENTITY_COLUMNS, *FARMLAND_COLUMNS, *NOTE_COLUMNS)

_KEY_RE = re.compile(r"^STATE_[A-Z0-9_]+$")


class EconomicsRow(NamedTuple):
    """One worksheet row. ``None`` is an empty cell, i.e. the default for that column only."""

    state_key: str
    anchor: tuple[int, int]
    arable_land: int | None
    subsistence_building: str | None
    arable_resources: list[str] | None
    arable_note: str
    arable_source: str
    line: int

    def has_values(self) -> bool:
        return (self.arable_land is not None or self.subsistence_building is not None
                or self.arable_resources is not None)


class EconomicsWorksheet(NamedTuple):
    rows: dict[str, EconomicsRow]  # file order
    columns: tuple[str, ...]


def load_economics_worksheet(path: Path) -> EconomicsWorksheet:
    """Parse the worksheet. Raises ``schema.SchemaError`` (file name plus line) on any
    structural problem; see the module docstring for the contract."""
    name = path.name
    rows: dict[str, EconomicsRow] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = tuple(reader.fieldnames or ())
        for col in IDENTITY_COLUMNS:
            if col not in columns:
                raise schema.SchemaError(f"{name}: missing required column '{col}'")
        unknown = [c for c in columns if c not in KNOWN_COLUMNS]
        if unknown:
            raise schema.SchemaError(
                f"{name}: unknown column(s) {unknown} (known: {list(KNOWN_COLUMNS)}) - "
                f"a new column is declared in worldgen.land_economics.KNOWN_COLUMNS first")
        for raw in reader:
            line = reader.line_num
            cell = {k: (v or "").strip() for k, v in raw.items() if k is not None}
            if raw.get(None):
                raise schema.SchemaError(f"{name} line {line}: more cells than the {len(columns)} header columns")
            if not any(cell.values()):
                continue
            key = cell["state_key"]
            if not _KEY_RE.match(key):
                raise schema.SchemaError(f"{name} line {line}: state_key {key!r} must match STATE_<UPPERCASE_NAME>")
            if key in rows:
                raise schema.SchemaError(
                    f"{name} line {line}: duplicate row for {key} (first at line {rows[key].line})")
            try:
                anchor = (int(cell["anchor_x"]), int(cell["anchor_y"]))
            except ValueError:
                raise schema.SchemaError(
                    f"{name} line {line}: {key} anchor_x/anchor_y must be integers, got "
                    f"{cell['anchor_x']!r}, {cell['anchor_y']!r}") from None
            arable_land: int | None = None
            if cell.get("arable_land"):
                try:
                    arable_land = int(cell["arable_land"])
                except ValueError:
                    raise schema.SchemaError(
                        f"{name} line {line}: {key} arable_land {cell['arable_land']!r} is not an integer") from None
                if arable_land < 0:
                    raise schema.SchemaError(f"{name} line {line}: {key} arable_land {arable_land} must be >= 0")
            resources: list[str] | None = None
            if cell.get("arable_resources"):
                if "," in cell["arable_resources"]:
                    raise schema.SchemaError(
                        f"{name} line {line}: {key} arable_resources must be space-separated, "
                        f"got {cell['arable_resources']!r}")
                resources = cell["arable_resources"].split()
            rows[key] = EconomicsRow(
                state_key=key, anchor=anchor, arable_land=arable_land,
                subsistence_building=cell.get("subsistence_building") or None,
                arable_resources=resources, arable_note=cell.get("arable_note", ""),
                arable_source=cell.get("arable_source", ""), line=line)
    return EconomicsWorksheet(rows=rows, columns=columns)


def resolve_economics(row: EconomicsRow | None, default: schema.Economics) -> schema.Economics:
    """Per-column fallback: a ``None`` cell (or no row) takes ``default``'s value.
    ``capped_resources`` always comes from ``default`` (#3688 replaces that line)."""
    if row is None:
        row = EconomicsRow("", (0, 0), None, None, None, "", "", 0)
    return schema.Economics(
        subsistence_building=row.subsistence_building or default.subsistence_building,
        arable_land=default.arable_land if row.arable_land is None else row.arable_land,
        arable_resources=list(default.arable_resources if row.arable_resources is None
                              else row.arable_resources),
        capped_resources=dict(default.capped_resources),
    )


# ---------------------------------------------------------------------------
# Building catalog (ids + group flags from this mod's common/)
# ---------------------------------------------------------------------------

class BuildingCatalog(NamedTuple):
    groups: dict[str, str]        # building id -> building_group
    rural: frozenset[str]         # ids whose group (or ancestor) sets land_usage = rural
    subsistence: frozenset[str]   # ids whose group sets is_subsistence = yes


def _top_level_blocks(text: str) -> dict[str, dict[str, str]]:
    """``name -> {key: value}`` for each top-level ``name = { ... }`` block; the value map holds
    the block's own depth-1 ``key = scalar`` lines. Comments (``#``) and quoted text are skipped
    when counting braces."""
    out: dict[str, dict[str, str]] = {}
    depth = 0
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0]
        if depth == 0:
            m = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*\{", line)
            if m:
                current = out.setdefault(m.group(1), {})
        elif depth == 1 and current is not None:
            m = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*)\s*$", line)
            if m:
                current.setdefault(m.group(1), m.group(2))
        depth += re.sub(r'"[^"]*"', "", line).count("{") - re.sub(r'"[^"]*"', "", line).count("}")
        if depth <= 0:
            depth = 0
            current = None
    return out


def load_building_catalog(buildings_dir: Path, building_groups_dir: Path) -> BuildingCatalog:
    """Every top-level ``building_<name> = {`` id under ``buildings_dir`` with its group, and the
    ``land_usage`` / ``is_subsistence`` flags resolved through ``parent_group`` chains."""
    group_defs: dict[str, dict[str, str]] = {}
    for path in sorted(building_groups_dir.glob("*.txt")):
        group_defs.update(_top_level_blocks(path.read_text(encoding="utf-8-sig", errors="replace")))
    groups: dict[str, str] = {}
    for path in sorted(buildings_dir.glob("*.txt")):
        for bid, body in _top_level_blocks(path.read_text(encoding="utf-8-sig", errors="replace")).items():
            if bid.startswith("building_"):
                groups[bid] = body.get("building_group", "")

    def land_usage(group: str) -> str:
        seen: set[str] = set()
        while group and group in group_defs and group not in seen:
            seen.add(group)
            if "land_usage" in group_defs[group]:
                return group_defs[group]["land_usage"]
            group = group_defs[group].get("parent_group", "")
        return ""

    rural = frozenset(b for b, g in groups.items() if land_usage(g) == "rural")
    subsistence = frozenset(b for b, g in groups.items()
                            if group_defs.get(g, {}).get("is_subsistence") == "yes")
    return BuildingCatalog(groups=groups, rural=rural, subsistence=subsistence)


# ---------------------------------------------------------------------------
# Rules (generator and validator both call these)
# ---------------------------------------------------------------------------

def check_economics(state_key: str, econ: schema.Economics, coastal: bool,
                    catalog: BuildingCatalog | None) -> tuple[list[str], list[str]]:
    """``(errors, warnings)`` for one state's economics, in a fixed rule order. ``coastal`` means
    the state emits a ``port`` hub. Without a ``catalog`` the id-existence and rural rules are skipped."""
    errors: list[str] = []
    warnings: list[str] = []
    sub = econ.subsistence_building
    if sub not in SUBSISTENCE_BUILDINGS:
        errors.append(f"{state_key}: subsistence_building {sub!r} is not one of "
                      f"{sorted(SUBSISTENCE_BUILDINGS)}")
    if sub == FISHING_VILLAGE and not coastal:
        errors.append(f"{state_key}: {FISHING_VILLAGE} needs a port hub, but the state is not coastal")
    if econ.arable_land < 0:
        errors.append(f"{state_key}: arable_land {econ.arable_land} must be >= 0")
    elif econ.arable_land < MASS_MIGRATION_TARGET_MIN_ARABLE_LAND:
        warnings.append(f"{state_key}: arable_land {econ.arable_land} is below "
                        f"MASS_MIGRATION_TARGET_MIN_ARABLE_LAND ({MASS_MIGRATION_TARGET_MIN_ARABLE_LAND}); "
                        f"the state is no mass-migration target")
    res = econ.arable_resources
    if not res:
        errors.append(f"{state_key}: arable_resources is empty")
    dupes = sorted({r for r in res if res.count(r) > 1})
    if dupes:
        errors.append(f"{state_key}: arable_resources lists {dupes} more than once")
    in_sub = sorted({r for r in res if r in SUBSISTENCE_BUILDINGS})
    if in_sub:
        errors.append(f"{state_key}: arable_resources must not contain subsistence building(s) {in_sub}")
    if catalog is not None:
        if sub not in catalog.groups:
            errors.append(f"{state_key}: subsistence_building {sub!r} is not defined under common/buildings/")
        missing = sorted({r for r in res if r not in catalog.groups})
        if missing:
            errors.append(f"{state_key}: arable_resources id(s) {missing} are not defined under common/buildings/")
        missing_cap = sorted(k for k in econ.capped_resources if k not in catalog.groups)
        if missing_cap:
            errors.append(f"{state_key}: capped_resources id(s) {missing_cap} are not defined under common/buildings/")
        not_rural = sorted({r for r in res if r in catalog.groups
                            and (r not in catalog.rural or r in catalog.subsistence)}
                           - set(in_sub))
        if not_rural:
            errors.append(f"{state_key}: arable_resources id(s) {not_rural} are not rural, "
                          f"non-subsistence buildings (land_usage = rural)")
    return errors, warnings


class StateIdentity(NamedTuple):
    """What a worksheet row is verified against: the state's naming anchor and its scope."""

    anchor: tuple[int, int] | None
    placeholder: bool


def check_worksheet_identity(
    rows: dict[str, EconomicsRow],
    identity: dict[str, StateIdentity],
    sea_keys: frozenset[str] | set[str] = frozenset(),
) -> tuple[list[str], list[tuple[EconomicsRow, str]]]:
    """Check every row's key and anchor against ``identity`` (``state key -> StateIdentity``).

    Returns ``(errors, rekeys)``: ``rekeys`` lists ``(row, current key)`` for rows whose key is
    unknown but whose anchor equals exactly one drawn state's naming anchor (the only case
    ``--rekey-economics`` repairs). Key and anchor resolving to different states, a dead anchor
    and a placeholder or sea key are errors with no auto-fix."""
    errors: list[str] = []
    rekeys: list[tuple[EconomicsRow, str]] = []
    by_anchor: dict[tuple[int, int], list[str]] = {}
    for k in sorted(identity):
        ident = identity[k]
        if not ident.placeholder and ident.anchor is not None:
            by_anchor.setdefault(ident.anchor, []).append(k)
    claimed: set[str] = set()
    for key, row in rows.items():
        where = f"row {row.line} {key}"
        ax, ay = row.anchor
        if key in sea_keys:
            errors.append(f"{where}: is a sea state; the worksheet covers drawn land states only")
        elif key in identity:
            ident = identity[key]
            if ident.placeholder:
                errors.append(f"{where}: is an out-of-scope placeholder state; placeholders stay on the "
                              f"default economics - delete the row")
            elif ident.anchor != (ax, ay):
                other = by_anchor.get((ax, ay), [])
                if other:
                    errors.append(f"{where}: key and anchor resolve to different states - anchor ({ax},{ay}) is "
                                  f"{other[0]}'s naming anchor but {key}'s is {_fmt(ident.anchor)}; fix the row by hand")
                else:
                    errors.append(f"{where}: anchor ({ax},{ay}) no longer equals the state's naming anchor "
                                  f"{_fmt(ident.anchor)} - re-anchor the row by hand")
        else:
            matches = by_anchor.get((ax, ay), [])
            if len(matches) == 1 and matches[0] not in rows and matches[0] not in claimed:
                claimed.add(matches[0])
                rekeys.append((row, matches[0]))
                errors.append(f"{where}: the state at anchor ({ax},{ay}) is now {matches[0]} - "
                              f"update state_key (or run --rekey-economics)")
            elif matches:
                errors.append(f"{where}: not a state, and anchor ({ax},{ay}) resolves to {matches} "
                              f"which already has a row or is ambiguous - delete or fix the row by hand")
            else:
                errors.append(f"{where}: not a state, and anchor ({ax},{ay}) matches no drawn state - "
                              f"row dead, delete it or re-anchor")
    return errors, rekeys


def _fmt(anchor: tuple[int, int] | None) -> str:
    return "(none)" if anchor is None else f"({anchor[0]},{anchor[1]})"


def load_naming_anchors(path: Path) -> dict[int, tuple[tuple[int, int], str]]:
    """``STATE number -> ((anchor_x, anchor_y), kind)`` from the naming worksheet
    (``land_regions_worksheet.csv``); ``kind`` is ``drawn`` or ``placeholder``."""
    out: dict[int, tuple[tuple[int, int], str]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[int(row["region_id"])] = ((int(row["anchor_x"]), int(row["anchor_y"])), row["kind"])
    return out


def rekey_worksheet_text(text: str, rekeys: list[tuple[EconomicsRow, str]]) -> str:
    """Rewrite only each stale row's ``state_key`` cell, every other byte preserved. Raises
    ``schema.SchemaError`` unless exactly one line starts with the old key's cell."""
    lines = text.splitlines(keepends=True)
    for row, new_key in rekeys:
        hits = [i for i, ln in enumerate(lines) if ln.startswith(row.state_key + ",")]
        if len(hits) != 1:
            raise schema.SchemaError(
                f"cannot rekey {row.state_key}: expected exactly one line starting with it, found {len(hits)}")
        i = hits[0]
        lines[i] = new_key + lines[i][len(row.state_key):]
    return "".join(lines)
