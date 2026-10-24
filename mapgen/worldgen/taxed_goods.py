"""Which goods a tag's own market produces at the start (#6638 phase A).

A good in a tag's ``taxed_goods`` (``mapgen/config/country_history``) must be produced somewhere in
that tag's own market, or the consumption tax on it is empty. "Produced" counts

* the goods a production method outputs (``goods_output_<good>_add``) for every method active in a
  building of ``common/history/buildings`` owned in the tag's states, and
* the same for the state's own subsistence building (``subsistence_building`` in
  ``map_data/state_regions``), which the engine creates and no history file lists: every method of
  its groups that the tag's starting techs and laws allow (liquor comes only from the subsistence
  home-workshops method, ``production_methods/12_subsistence.txt``).

The market is the tag's own states only: whether protectorates share their overlord's market is
unverified (vanilla's subject types carry no market key).

Pure and deterministic: files are read in sorted order, no clock, no randomness.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import building_history as bh

OUTPUT = re.compile(r"\bgoods_output_(\w+?)_add\b")


def load_pm_outputs(production_methods_dir: Path) -> dict[str, frozenset[str]]:
    """``{production method id: goods it outputs}`` (every ``goods_output_<good>_add`` in its body)."""
    out: dict[str, frozenset[str]] = {}
    for path in sorted(Path(production_methods_dir).glob("*.txt")):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        for key, _, body in bh.parse(text):
            if isinstance(body, list):
                out[key] = frozenset(OUTPUT.findall(_flatten(body)))
    return out


def _flatten(items) -> str:
    parts: list[str] = []
    for k, _, v in items:
        if isinstance(v, list):
            parts.append(_flatten(v))
        elif k:
            parts.append(k)
    return " ".join(parts)


def load_subsistence(state_regions_dir: Path) -> dict[str, str]:
    """``{STATE_KEY: subsistence building id}`` from ``map_data/state_regions``."""
    out: dict[str, str] = {}
    for path in sorted(Path(state_regions_dir).glob("*.txt")):
        if path.name.startswith("99_"):
            continue
        for key, _, body in bh.parse(path.read_text(encoding="utf-8-sig")):
            if key and key.startswith("STATE_") and isinstance(body, list):
                sub = bh._get(body, "subsistence_building")
                if isinstance(sub, str):
                    out[key] = sub
    return out


def _default_pms(world: bh.World, building: str) -> list[str]:
    """The methods a created building starts on when its history entry names none: each group's default."""
    bld = world.buildings.get(building)
    pms: list[str] = []
    for g in (bld.groups if bld else ()):
        options = world.groups.get(g, [])
        pick = next((m for m in options if m in world.pms and world.pms[m].is_default), options[0] if options else None)
        if pick:
            pms.append(pick)
    return pms


def produced_goods(world: bh.World, outputs: dict[str, frozenset[str]], subsistence: dict[str, str],
                   emitted_texts: dict[str, str]) -> dict[str, set[str]]:
    """``{tag: goods its own states produce at the start}``."""
    out: dict[str, set[str]] = {}
    for text in emitted_texts.values():
        for _state, tag, blds in bh.parse_emitted(text):
            goods = out.setdefault(tag, set())
            for b in blds:
                for pm in (b["pms"] or _default_pms(world, b["building"])):
                    goods |= outputs.get(pm, frozenset())
    for state, tags in sorted(world.owners.items()):
        sub = subsistence.get(state)
        bld = world.buildings.get(sub) if sub else None
        if bld is None:
            continue
        for tag in tags:
            ts = world.tags.get(tag)
            if ts is None:
                continue
            goods = out.setdefault(tag, set())
            for g in bld.groups:
                options = world.groups.get(g, [])
                for pm in options:
                    if pm in world.pms and bh.pm_gate(world.pms[pm], ts, set(options)) is None:
                        goods |= outputs.get(pm, frozenset())
    return out


def check(taxed: dict[str, list[str]], produced: dict[str, set[str]]) -> list[str]:
    """One error per (tag, good) that is taxed but produced nowhere in the tag's market."""
    errors: list[str] = []
    for tag in sorted(taxed):
        for good in taxed[tag]:
            if good not in produced.get(tag, ()):
                errors.append(f"c:{tag}: taxes {good} but no building or subsistence method in its own states produces it")
    return errors
