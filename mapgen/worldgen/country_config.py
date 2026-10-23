"""The resolved per-tag view of ``mapgen/config/country_history/*.json``.

One merge (baseline <- profile <- tag, per law group; ``tech_tier`` the same way) serves every
consumer, so they cannot disagree: the slave-pop gate (``pop_history.load_slavery``), the tech-tier
warning (``generate_pop_history``) and the law lines ``generate_country_history`` emits
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


@dataclass(frozen=True)
class Resolved:
    laws: dict[str, str] = field(default_factory=dict)   # law group -> law id, merged
    tech_tier: int | None = None


def load_resolved(country_history_dir: Path | None) -> dict[str, Resolved] | None:
    """``{tag: Resolved}`` over every ``*.json`` in the folder, or ``None`` when the folder or
    its JSON files are not in the tree."""
    if country_history_dir is None or not Path(country_history_dir).is_dir():
        return None
    files = sorted(Path(country_history_dir).glob("*.json"))
    if not files:
        return None
    out: dict[str, Resolved] = {}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        base = d.get("baseline", {})
        for tag, v in d.get("tags", {}).items():
            prof = d.get("profiles", {}).get(v.get("profile"), {})
            laws = {**base.get("laws", {}), **prof.get("laws", {}), **v.get("laws", {})}
            out[tag] = Resolved(laws=laws, tech_tier=v.get("tech_tier", prof.get("tech_tier", base.get("tech_tier"))))
    return out


def slavery_law(resolved: dict[str, Resolved], tag: str) -> str:
    """The tag's ``lawgroup_slavery`` law, or ``law_slavery_banned`` (the engine's own fallback)."""
    r = resolved.get(tag)
    return r.laws.get(SLAVERY_GROUP, SLAVERY_BANNED) if r else SLAVERY_BANNED


def starting_laws(resolved: dict[str, Resolved]) -> dict[str, list[str]]:
    """``{tag: [law id, ...]}`` the generator activates after the politics effect. Only the
    slavery law for now; later items append their laws to the same lists."""
    return {tag: [slavery_law(resolved, tag)] for tag in sorted(resolved)}
