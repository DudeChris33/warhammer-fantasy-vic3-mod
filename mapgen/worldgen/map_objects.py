"""Codec for Victoria 3 generated map-object files and their ``.bin`` transform tables (board #11534).

Vanilla's ``gfx/map/map_object_data/generated/*.txt`` declare objects (a mesh and a layer)
and place them in one of two storage forms, both holding the same record:

* ``transform_bin_file="gfx/map/map_object_data/<name>.bin"``: a headerless little-endian
  float32 table, ``RECORD_FLOATS`` (10) per instance, 40 bytes: position ``x y z``,
  rotation quaternion ``x y z w``, scale ``x y z``.
* inline ``count=N`` plus ``transform="..."``: the same rows as text, one per line, six
  decimals, the whole object closed by ``"}`` on its own line (no tab, no ``}`` line of its own).

An object with neither is a valid empty object (vanilla ships three). Position ``x`` is the
canvas x and ``z`` is the canvas height minus the canvas y (the locator frame of
``generate_map_locators.py``); ``y`` is 0 for every generated instance, the engine puts
objects on the terrain at load.

Files start with a UTF-8 BOM and use ``\\n``. This module touches no file by itself except
:func:`read_bin` and :func:`instances`; it never reads the vanilla install on its own.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

RECORD_FLOATS = 10
RECORD_BYTES = 40
BOM = "﻿"
#: Where the generated files point their ``transform_bin_file`` (mod-relative, forward slashes).
BIN_DIR = "gfx/map/map_object_data"

_OBJECT_SPLIT = re.compile(r"(?m)^[ \t]*object[ \t]*=[ \t]*\{")
_QUOTED = {k: re.compile(r'(?m)^[ \t]*' + k + r'[ \t]*=[ \t]*"([^"]*)"')
           for k in ("name", "layer", "pdxmesh", "entity", "transform_bin_file")}
_FLAG = {k: re.compile(r"(?m)^[ \t]*" + k + r"[ \t]*=[ \t]*(yes|no)\b")
         for k in ("clamp_to_water_level", "render_under_water", "generated_content")}
_COUNT = re.compile(r"(?m)^[ \t]*count[ \t]*=[ \t]*(\d+)")
_TRANSFORM = re.compile(r'(?m)^[ \t]*transform[ \t]*=[ \t]*"([^"]*)"')


@dataclass
class ObjectEntry:
    name: str
    clamp_to_water_level: str      # "yes" / "no", as written in the file
    render_under_water: str
    generated_content: str
    layer: str
    pdxmesh: str | None = None
    entity: str | None = None
    transform_bin_file: str | None = None
    inline: np.ndarray | None = None   # (N, 10) float32 when the object carries inline rows


def bin_path(name: str) -> str:
    """The mod-relative ``transform_bin_file`` value for object ``name``."""
    return f"{BIN_DIR}/{name}.bin"


def read_bin(path) -> np.ndarray:
    """A ``.bin`` as float32 ``(N, 10)``; raises when the size is not a multiple of 40 bytes."""
    data = Path(path).read_bytes()
    if len(data) % RECORD_BYTES:
        raise ValueError(f"{path}: {len(data)} bytes is not a multiple of {RECORD_BYTES}")
    return np.frombuffer(data, dtype="<f4").reshape(-1, RECORD_FLOATS).astype(np.float32)


def bin_bytes(a: np.ndarray) -> bytes:
    a = np.asarray(a)
    if a.ndim != 2 or a.shape[1] != RECORD_FLOATS:
        raise ValueError(f"expected (N, {RECORD_FLOATS}), got {a.shape}")
    return np.ascontiguousarray(a, "<f4").tobytes()


def yaw_quat(theta: float) -> tuple[float, float, float, float]:
    """Rotation quaternion ``(x, y, z, w)`` for a yaw of ``theta`` radians about the vertical axis."""
    return (0.0, math.sin(theta / 2.0), 0.0, math.cos(theta / 2.0))


def parse_object_file(text: str) -> list[ObjectEntry]:
    """Parse a generated object file (BOM and CRLF tolerated) into entries, in file order.

    Objects are split on ``object={`` at a line start: vanilla's inline objects close with
    ``"}`` and no newline-brace, so splitting on a closing ``}`` line would miss them. A
    ``count=`` is checked against the number of inline rows.
    """
    if text.startswith(BOM):
        text = text[1:]
    text = text.replace("\r\n", "\n")
    parts = _OBJECT_SPLIT.split(text)
    lead = "\n".join(ln for ln in parts[0].splitlines() if ln.strip() and not ln.lstrip().startswith("#"))
    if lead.strip():
        raise ValueError(f"unexpected text before the first object: {lead[:60]!r}")
    entries: list[ObjectEntry] = []
    for chunk in parts[1:]:
        fields: dict[str, str] = {}
        for key, rx in {**_QUOTED, **_FLAG}.items():
            m = rx.search(chunk)
            if m:
                fields[key] = m.group(1)
        for need in ("name", "layer", "clamp_to_water_level", "render_under_water", "generated_content"):
            if need not in fields:
                raise ValueError(f"object missing {need}: {chunk[:80]!r}")
        inline = None
        mt = _TRANSFORM.search(chunk)
        if mt:
            nums = np.array(mt.group(1).split(), dtype=np.float64)
            if nums.size % RECORD_FLOATS:
                raise ValueError(f"{fields['name']}: {nums.size} inline numbers, not a multiple of {RECORD_FLOATS}")
            inline = nums.reshape(-1, RECORD_FLOATS).astype(np.float32)
            mc = _COUNT.search(chunk)
            if mc and int(mc.group(1)) != len(inline):
                raise ValueError(f"{fields['name']}: count={mc.group(1)} but {len(inline)} inline rows")
        entries.append(ObjectEntry(
            name=fields["name"], clamp_to_water_level=fields["clamp_to_water_level"],
            render_under_water=fields["render_under_water"], generated_content=fields["generated_content"],
            layer=fields["layer"], pdxmesh=fields.get("pdxmesh"), entity=fields.get("entity"),
            transform_bin_file=fields.get("transform_bin_file"), inline=inline))
    return entries


def render_object_file(entries: list[ObjectEntry]) -> str:
    """Text of a generated object file: BOM, LF, tab-indented fields in vanilla's order.

    An entry with a ``transform_bin_file`` gets that line; an entry with inline rows is written
    in vanilla's inline form (``count=``, ``transform="..."`` and a closing ``"}``); an entry with
    neither is an empty object.
    """
    out = [BOM]
    for e in entries:
        out.append("object={\n")
        out.append(f'\tname="{e.name}"\n')
        out.append(f"\tclamp_to_water_level={e.clamp_to_water_level}\n")
        out.append(f"\trender_under_water={e.render_under_water}\n")
        out.append(f"\tgenerated_content={e.generated_content}\n")
        out.append(f'\tlayer="{e.layer}"\n')
        if e.pdxmesh:
            out.append(f'\tpdxmesh="{e.pdxmesh}"\n')
        if e.entity:
            out.append(f'\tentity="{e.entity}"\n')
        if e.inline is not None and len(e.inline):
            rows = "\n".join(" ".join(f"{float(v):.6f}" for v in r) for r in e.inline)
            out.append(f"\tcount={len(e.inline)}\n")
            out.append(f'\ttransform="{rows}\n"}}\n')
            continue
        if e.transform_bin_file:
            out.append(f'\ttransform_bin_file="{e.transform_bin_file}"\n')
        out.append("}\n")
    return "".join(out)


def instances(entry: ObjectEntry, root=None) -> np.ndarray:
    """The entry's instances: inline rows, else its ``.bin`` under ``root``, else an empty table."""
    if entry.inline is not None:
        return entry.inline
    if entry.transform_bin_file:
        if root is None:
            raise ValueError(f"{entry.name}: a .bin object needs a root to resolve {entry.transform_bin_file}")
        return read_bin(Path(root) / entry.transform_bin_file)
    return np.zeros((0, RECORD_FLOATS), np.float32)
