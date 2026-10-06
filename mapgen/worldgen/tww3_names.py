"""Parse the TWW3 Old World mod's region table (board #4363).

The pure half of the canon-name lookup: it turns
``sources/cr_oldworld_campaign/cr_oldworld_lookup/cr_oldworld_campaign.tsv``
into a colour -> region-key index, so a canvas point sampled against
``cr_oldworld_lookup.bmp`` can be resolved to the name TWW3 gives that ground.
The sibling of :mod:`worldgen.land_naming` — that module answers "which realm
owns this region", this one answers "what does the reference map call it".

**Pure: no I/O beyond the TSV parse.** The bitmap, the registration and every
canvas-space concern live in ``mapgen/tww3_name_lookup.py``, exactly as
``land_naming`` keeps its worksheet parse separate from the generator that
places regions. That split is what lets ``run_fixture.py --check`` exercise all
of this on a tiny synthetic table with no dependency on the real, gitignored
source.

The file shape (a TWW3 table export)
------------------------------------
Row 1 is a real header; row 2 is a metadata row
(``#regions_tables;0;db/regions_tables/cr_oldworld_campaign``); the rest is
data. The colour column is named ``unnamed colour group_1`` — **not**
``colour`` — and is the last column. ``000000`` is not a region colour: black
is void in the bitmap (the campaign map's sea and off-map), and the rows that
carry it are water/coast *names* with no paintable area. They are kept, and
exposed separately by :func:`water_name_bank`, rather than silently dropped:
they are a genuine canon-name bank for a later sea-naming pass, but they can
never be the answer to "what is at this land pixel".

What this deliberately does NOT do
----------------------------------
There is no ``slug -> display name`` transliteration helper. Cut during the
challenge review of #4363's plan as overengineering: every name this feeds goes
through mandatory human review before it reaches a worksheet, so an automated
guess at capitalisation and word order would add a second thing to check
without removing the first. Callers emit the **raw slug and raw key**, and the
reviewer types the display name.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

#: Every data key observed carries this prefix; :attr:`TWW3Region.slug` strips it
#: when present and is the whole key otherwise (never an error — a differently
#: prefixed export is still usable, just less pretty).
KEY_PREFIX = "cr_oldworld_region_"

#: The colour that means "no region here": the campaign map's sea / off-map.
WATER_HEX = "000000"

#: The exact header this parser was written against. A shape mismatch is a hard
#: error, not an adaptation: the colour lives in a positionally-identified column
#: with a non-obvious name, so a different export could silently hand back the
#: wrong field.
EXPECTED_HEADER = ("key", "owner_bundle", "faction_swapping_id",
                   "hidden_settlement_override", "terrain_patch_area",
                   "unnamed colour group_1")

#: A truncated/partial export is worse than no export — it would resolve some
#: points and silently return "unknown" for the rest, which reads like a
#: registration problem rather than a missing-data one. The real file carries
#: 1463 data rows; anything under this is refused outright.
MIN_DATA_ROWS = 1000

_HEX_RE = re.compile(r"^[0-9A-F]{6}$")


class TWW3NamesError(RuntimeError):
    """The region table is missing, malformed, or not the table we expect."""


@dataclass(frozen=True)
class TWW3Region:
    """One row of the region table.

    ``key`` is the verbatim TSV key; ``slug`` is it minus :data:`KEY_PREFIX`;
    ``hex`` is the uppercase 6-digit colour; ``is_water`` is ``hex ==``
    :data:`WATER_HEX` (a coast/sea name with no paintable area).
    """

    key: str
    slug: str
    hex: str
    is_water: bool


def load_tww3_regions(path: Path) -> list[TWW3Region]:
    """Parse the region table, preserving the file's own row order.

    Skips the ``#``-prefixed metadata row and any blank row. Raises
    :class:`TWW3NamesError` on a header shape mismatch, a malformed or blank
    colour, a duplicate non-black colour (two keys claiming one region is not
    resolvable), or a file with fewer than :data:`MIN_DATA_ROWS` data rows.
    """
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    if not rows:
        raise TWW3NamesError(f"{path.name}: file is empty")

    header = tuple(c.strip() for c in rows[0])
    if header != EXPECTED_HEADER:
        raise TWW3NamesError(
            f"{path.name}: unexpected header {list(header)!r}; expected "
            f"{list(EXPECTED_HEADER)!r}. The colour column is identified by name, "
            f"so a different export could hand back the wrong field silently."
        )

    out: list[TWW3Region] = []
    seen: dict[str, str] = {}
    for lineno, row in enumerate(rows[1:], start=2):
        if not row or not row[0].strip():
            continue
        key = row[0].strip()
        if key.startswith("#"):
            continue  # the #regions_tables metadata row
        if len(row) != len(EXPECTED_HEADER):
            raise TWW3NamesError(
                f"{path.name}:{lineno}: row has {len(row)} fields, expected "
                f"{len(EXPECTED_HEADER)} ({key!r})")
        colour = row[-1].strip().upper()
        if not colour:
            raise TWW3NamesError(f"{path.name}:{lineno}: {key!r} has a blank colour")
        if not _HEX_RE.match(colour):
            raise TWW3NamesError(
                f"{path.name}:{lineno}: {key!r} has a malformed colour {colour!r} "
                f"(expected 6 hex digits)")
        is_water = colour == WATER_HEX
        if not is_water:
            if colour in seen:
                raise TWW3NamesError(
                    f"{path.name}:{lineno}: colour {colour} is claimed by both "
                    f"{seen[colour]!r} and {key!r} — a sampled pixel could not be "
                    f"resolved to one region")
            seen[colour] = key
        slug = key[len(KEY_PREFIX):] if key.startswith(KEY_PREFIX) else key
        out.append(TWW3Region(key=key, slug=slug, hex=colour, is_water=is_water))

    if len(out) < MIN_DATA_ROWS:
        raise TWW3NamesError(
            f"{path.name}: only {len(out)} data rows, expected at least "
            f"{MIN_DATA_ROWS} — this looks like a truncated export")
    return out


def colour_index(regions: list[TWW3Region]) -> dict[str, TWW3Region]:
    """``hex -> region`` over the **non-water** rows only.

    Water rows are excluded because black is void in the bitmap: including them
    would map every sea pixel onto whichever coast name happened to be read
    last. Uniqueness is already enforced by :func:`load_tww3_regions`.
    """
    return {r.hex: r for r in regions if not r.is_water}


def water_name_bank(regions: list[TWW3Region]) -> list[TWW3Region]:
    """The black-keyed rows: canon sea/coast names with no paintable area.

    Exposed for a future sea-naming pass and for reporting; **nothing in board
    #4363 consumes it**. Kept rather than dropped at parse time so the count is
    visible and the names are not lost.
    """
    return [r for r in regions if r.is_water]
