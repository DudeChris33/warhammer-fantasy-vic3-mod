"""The resolved per-tag view of ``mapgen/config/country_history/*.json``.

One merge (a shared profile from ``profiles.json`` or the region baseline, then the tag, per law group) serves every
consumer, so they cannot disagree: the slave-pop gate (``pop_history.load_slavery``)
and the law lines ``generate_country_history`` emits
(``country_history.plan(laws=...)``). Neutral on purpose: the pop generator must not import the
country emitter.

Pure and deterministic: files are read in sorted order, no clock, no randomness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SLAVERY_BANNED = "law_slavery_banned"
SLAVERY_GROUP = "lawgroup_slavery"
GOVERNANCE_GROUP = "lawgroup_governance_principles"
CHIEFDOM = "law_chiefdom"
TRADE_GROUP = "lawgroup_trade_policy"
ISOLATIONISM = "law_isolationism"


PROFILES_FILE = "profiles.json"
#: Package fields other than ``laws`` (which merge per law group); a tag value replaces the whole field.
DIRECT_FIELDS = ("ruling_igs", "tax_level", "taxed_goods", "tariffs", "institutions", "next_election",
                 "suggested_ig_names")


class ConfigError(ValueError):
    """The country_history data is inconsistent (a tag names a missing profile, ...)."""


@dataclass(frozen=True)
class Resolved:
    laws: dict[str, str] = field(default_factory=dict)   # law group -> law id, merged
    package: dict = field(default_factory=dict)          # laws + every direct field, merged (no None)


def region_files(country_history_dir: Path) -> list[Path]:
    """The ``NN_<stem>.json`` region files, sorted (``profiles.json`` and ``dormant/`` are not regions)."""
    return sorted(Path(country_history_dir).glob("[0-9][0-9]_*.json"))


def load_profiles(country_history_dir: Path) -> dict[str, dict]:
    """``{name: full package}`` from ``profiles.json`` ({} when the file is absent)."""
    path = Path(country_history_dir) / PROFILES_FILE
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("profiles", {})


def layer(base: dict, top: dict) -> dict:
    """``top`` over ``base``: direct fields replace (a ``null`` removes one), ``laws`` merge per law group."""
    eff = {k: v for k, v in base.items() if k in DIRECT_FIELDS}
    eff["laws"] = dict(base.get("laws", {}))
    for name in DIRECT_FIELDS:
        if name in top:
            eff[name] = top[name]
    eff["laws"].update(top.get("laws", {}))
    return {k: v for k, v in eff.items() if v is not None}


def tag_package(entry: dict, baseline: dict, profiles: dict[str, dict]) -> dict:
    """One tag's resolved package: its profile (a full package, so the region baseline is skipped) or the
    region baseline, then the tag's own overrides. Raises :class:`ConfigError` for an unknown profile."""
    name = entry.get("profile")
    if name is None:
        return layer(baseline, entry)
    if name not in profiles:
        raise ConfigError(f"profile {name!r} is not in {PROFILES_FILE}")
    return layer(profiles[name], entry)


def load_resolved(country_history_dir: Path | None) -> dict[str, Resolved] | None:
    """``{tag: Resolved}`` over every region file in the folder, or ``None`` when the folder or
    its JSON files are not in the tree."""
    if country_history_dir is None or not Path(country_history_dir).is_dir():
        return None
    files = region_files(country_history_dir)
    if not files:
        return None
    profiles = load_profiles(country_history_dir)
    out: dict[str, Resolved] = {}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        base = d.get("baseline", {})
        for tag, v in d.get("tags", {}).items():
            pkg = tag_package(v, base, profiles)
            out[tag] = Resolved(laws=pkg["laws"], package=pkg)
    return out


def slavery_law(resolved: dict[str, Resolved], tag: str) -> str:
    """The tag's ``lawgroup_slavery`` law, or ``law_slavery_banned`` (the engine's own fallback)."""
    r = resolved.get(tag)
    return r.laws.get(SLAVERY_GROUP, SLAVERY_BANNED) if r else SLAVERY_BANNED


def starting_budget(resolved: dict[str, Resolved]) -> dict[str, tuple[str, list[str]]]:
    """``{tag: (tax_level, taxed goods in file order)}`` from the resolved packages (#6638 phase A)."""
    return {tag: (r.package["tax_level"], list(r.package.get("taxed_goods", [])))
            for tag, r in sorted(resolved.items()) if "tax_level" in r.package}


def starting_laws(resolved: dict[str, Resolved]) -> dict[str, list[str]]:
    """``{tag: [law id, ...]}`` the generator activates after the politics effect: the slavery law
    (#9028) and, for a tag whose governance principle resolves to ``law_chiefdom``, that law (#9037;
    the rest of the governance group waits for #6638) and, for a tag whose trade policy resolves to
    ``law_isolationism``, that law (#9035: closed markets come from the data, not from missing tech)."""
    out: dict[str, list[str]] = {}
    for tag in sorted(resolved):
        laws = [slavery_law(resolved, tag)]
        if resolved[tag].laws.get(GOVERNANCE_GROUP) == CHIEFDOM:
            laws.append(CHIEFDOM)
        if resolved[tag].laws.get(TRADE_GROUP) == ISOLATIONISM:
            laws.append(ISOLATIONISM)
        out[tag] = laws
    return out
