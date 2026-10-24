#!/usr/bin/env python3
"""Validate the starting-country data files in ``mapgen/config/country_history/``.

Each ``NN_<stem>.json`` describes, per region, a ``baseline`` package plus per-tag
overrides for every tag of that region that **owns land at the start**
(``mapgen/derived/state_ownership.json``; schema: ``mapgen/config/country_history/README.md``).
``profiles.json`` holds the full packages shared by whole peoples. Entries for tags that own
nothing live in ``dormant/`` and are not read. Generators turn these files into
``common/history/``; this linter is the gate that keeps them consistent with the mod's own
laws, interest groups, technologies and government types.

Hard errors (exit 1):

* an unknown law, law group, interest group, technology, good, institution, tax level or
  tariff level;
* a law that does not belong to its group key, more than one law for a group, or a law
  group with no law;
* a law whose unlock (``unlocking_technologies`` / ``unlocking_laws``) is not covered by the
  tag's starting technology (its culture preset, with the generator's ``TAG_TECH`` exceptions,
  plus its row in ``mapgen/config/starting_tech_extras.json``) or the chosen laws; an extra that
  is an unknown technology, whose own prerequisite is not covered, or that is keyed on a
  formable. The preset and extras come from ``worldgen/country_history.py`` (the generator's own
  inputs), so linter and generator cannot disagree;
* two chosen laws where one lists the other in ``disallowing_laws``;
* a tag that is not in the registry, is a formable, is in another region, owns no state at the
  start (move it to ``dormant/``), or an owner with no entry; a profile that is not a full package;
* a non-zero institution level that no chosen law grants (``institution =`` on the law);
* laws for which no government type matches (see below);
* a non-default choice with no ``source`` / ``why`` (a ``profile`` carries one for its whole
  bundle), or a justification with nothing to justify;
* a malformed ``next_election`` (or one that disagrees with whether the laws hold elections).

The government type is computed, never written: the first ``common/government_types`` entry, in
file order, whose ``possible`` passes (the engine's rule), from the laws, the definition's tier and
type, the ruling IGs, the subject type (``common/history/diplomacy`` pacts) and the owned-state
count (``any_scope_state = { count <= N }``).

Warnings never change the exit code: a government-type trigger that cannot be fully
evaluated before the pick (ruler- or market-dependent), a tag with no country definition (its tech is not
evaluated), an extra its preset already grants.

Deterministic: pure stdlib, sorted output, no clock, no environment reads.

Usage::

    python mapgen/validate_country_history.py                 # every region file
    python mapgen/validate_country_history.py 02_empire.json  # one file
    python mapgen/validate_country_history.py --dump-resolved scratchpad/x.json  # resolved packages + computed type
    python mapgen/validate_country_history.py --vanilla "<Victoria 3>/game"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import country_config as cc  # noqa: E402
from worldgen import country_history as ch  # noqa: E402
from worldgen.state_ownership import OwnershipError  # noqa: E402

DEFAULT_DATA_DIR = REPO / "mapgen" / "config" / "country_history"
DEFAULT_REGISTRY = REPO / "planning" / "tag_registry.md"
DEFAULT_EXTRAS = REPO / "mapgen" / "config" / "starting_tech_extras.json"
DEFAULT_OWNERSHIP = REPO / "mapgen" / "derived" / "state_ownership.json"
DEFAULT_SUBJECTS = REPO / "common" / "history" / "diplomacy"

TAX_LEVELS = ("very_low", "low", "medium", "high", "very_high")
CONFIDENCE = ("high", "medium", "low")
INSTITUTION_LEVELS = range(0, 6)
START_YEAR = 2502

# Vanilla folders are not in the mod's ``replace_paths`` for goods, institutions and trade
# levels, so the mod does not carry them. When neither ``--vanilla`` nor the game root has
# ``common/goods`` / ``common/institutions`` these bundled lists (Victoria 3 1.13, checked
# against the ids used by the mod's laws/modifiers and ``docs/*.log``) stand in.
BUNDLED_GOODS = frozenset("""
aeroplanes ammunition artillery automobiles clippers clothes coal coffee dye engines explosives
fabric fertilizer fine_art fish fruit furniture glass grain groceries hardwood iron ironclads
lead liquor luxury_clothes luxury_furniture manowars meat merchant_marine oil opium paper
porcelain radios rubber services silk small_arms steamers steel sugar sulfur tanks tea
telephones tobacco tools transportation wine wood
""".split())
BUNDLED_INSTITUTIONS = frozenset("""
institution_colonial_affairs institution_health_system institution_home_affairs
institution_police institution_schools institution_social_security
institution_workplace_safety
""".split())
TARIFF_LEVELS = frozenset("""
max_subventions high_subventions low_subventions no_tariffs_or_subventions
low_tariffs high_tariffs max_tariffs no_tariffs
""".split())

# Which distribution-of-power laws give a voting franchise (``country_has_voting_franchise``).
VOTING_LAWS = frozenset({"law_landed_voting", "law_wealth_voting", "law_census_voting",
                         "law_universal_suffrage"})

TOKEN = re.compile(r'"[^"]*"|[{}]|[<>]=?|[!?]?=|[^\s{}=<>"]+')


# ----------------------------------------------------------------------------------------
# Clausewitz script reader (just enough structure for the databases this linter reads)
# ----------------------------------------------------------------------------------------

def parse_pdx(text: str) -> list:
    """Parse script into ``[(key, value)]``; value is a str or a nested list; bare tokens
    have key ``None``. Duplicate keys are kept in order."""
    text = re.sub(r"#[^\n]*", "", text.lstrip("﻿"))
    toks = TOKEN.findall(text)
    pos = 0

    def block() -> list:
        nonlocal pos
        items: list = []
        while pos < len(toks):
            tok = toks[pos]
            if tok == "}":
                pos += 1
                return items
            if pos + 1 < len(toks) and toks[pos + 1] in ("=", "?=", "!=", "<", ">", "<=", ">="):
                key = tok + toks[pos + 1] if toks[pos + 1] in ("<", ">", "<=", ">=") else tok   # `count <= 2` -> `count<=`
                pos += 2
                if pos < len(toks) and toks[pos] == "{":
                    pos += 1
                    items.append((key, block()))
                else:
                    items.append((key, toks[pos]))
                    pos += 1
            else:
                items.append((None, tok))
                pos += 1
        return items

    return block()


def _read_dir(root: Path, rel: str) -> list:
    """All top-level entries of every ``*.txt`` under ``root/rel``, in filename order."""
    out: list = []
    folder = root / rel
    if folder.is_dir():
        for path in sorted(folder.glob("*.txt")):
            out.extend(parse_pdx(path.read_text(encoding="utf-8")))
    return out


def _vals(items: list, key: str) -> list:
    return [v for k, v in items if k == key]


def _bare(items) -> list[str]:
    return [v for k, v in items if k is None] if isinstance(items, list) else []


# ----------------------------------------------------------------------------------------
# Game data
# ----------------------------------------------------------------------------------------

class GameData:
    def __init__(self, game_root: Path, vanilla_root: Path | None = None):
        self.game_root = game_root
        self.notes: list[str] = []

        self.law_groups = {k for k, _ in _read_dir(game_root, "common/law_groups")}

        self.laws: dict[str, dict] = {}
        for key, body in _read_dir(game_root, "common/laws"):
            if not isinstance(body, list):
                continue
            group = next(iter(_vals(body, "group")), None)
            self.laws[key] = {
                "group": group,
                "unlock_techs": [t for b in _vals(body, "unlocking_technologies") for t in _bare(b)],
                "unlock_laws": [t for b in _vals(body, "unlocking_laws") for t in _bare(b)],
                "disallow": [t for b in _vals(body, "disallowing_laws") for t in _bare(b)],
                "institution": next(iter(_vals(body, "institution")), None),
            }

        self.igs = {k for k, _ in _read_dir(game_root, "common/interest_groups")}

        self.techs: dict[str, dict] = {}
        for key, body in _read_dir(game_root, "common/technology/technologies"):
            if not isinstance(body, list):
                continue
            self.techs[key] = {
                "era": next(iter(_vals(body, "era")), None),
                "requires": [t for b in _vals(body, "unlocking_technologies") for t in _bare(b)],
            }

        # starting technology: the generator's own inputs (preset effects, culture of each definition)
        self.presets = ch.load_preset_techs(game_root / "common/scripted_effects")
        self.cultures = ch.load_country_cultures(game_root / "common/country_definitions")

        self.gov_possible: dict[str, list] = {}
        for key, body in _read_dir(game_root, "common/government_types"):
            if isinstance(body, list):
                self.gov_possible[key] = next(iter(_vals(body, "possible")), [])

        self.triggers = {k: v for k, v in _read_dir(game_root, "common/scripted_triggers")
                         if isinstance(v, list)}

        self.definitions: dict[str, dict] = {}
        for key, body in _read_dir(game_root, "common/country_definitions"):
            if isinstance(body, list) and any(k == "tier" for k, _ in body):
                self.definitions[key] = {
                    "tier": next(iter(_vals(body, "tier")), None),
                    "country_type": next(iter(_vals(body, "country_type")), None),
                    "cultures": set(_bare(next(iter(_vals(body, "cultures")), []))),
                }

        self.goods = self._id_set([vanilla_root, game_root], "common/goods", BUNDLED_GOODS, "goods")
        self.institutions = self._id_set([vanilla_root, game_root], "common/institutions",
                                         BUNDLED_INSTITUTIONS, "institutions")

    def _id_set(self, roots, rel: str, fallback: frozenset, what: str) -> frozenset:
        for root in roots:
            if root is not None:
                found = {k for k, _ in _read_dir(root, rel)}
                if found:
                    return frozenset(found)
        self.notes.append(f"note: no {rel} on disk; using the bundled {what} list")
        return fallback

    def coverage(self, tag: str, extras: list[str]):
        """``(covered techs | None, label, errors, warnings)`` for one tag: its preset plus its extras.
        ``None`` = not evaluable (no country definition, or no preset for its culture)."""
        if tag not in self.cultures:
            return None, "", [], ["tech not evaluable: no country definition"]
        try:
            preset = ch.tech_effect(tag, self.cultures[tag])
        except OwnershipError as exc:
            return None, "", [str(exc)], []
        if preset is not None and preset not in self.presets:
            return None, "", [f"starting-technology preset {preset} is not defined in common/scripted_effects"], []
        base = set(self.presets[preset]) if preset else set()
        label = f"preset {preset}" if preset else "no preset"
        errors: list[str] = []
        warnings: list[str] = []
        covered = set(base)
        for tech in extras:
            if tech not in self.techs:
                errors.append(f"unknown tech {tech} in starting_tech_extras.json")
            elif tech in base:
                warnings.append(f"extra tech {tech} is already granted by {label}")
        covered |= {t for t in extras if t in self.techs}
        for tech in sorted(set(extras)):
            if tech in self.techs:
                reqs = self.techs[tech]["requires"]
                if reqs and not any(r in covered for r in reqs):
                    errors.append(f"extra tech {tech} needs one of {', '.join(reqs)}")
        return covered, label, errors, warnings


def load_registry(path: Path) -> dict[str, tuple[str, str]]:
    """``tag -> (region file stem, kind)`` from the roster tables."""
    reg: dict[str, tuple[str, str]] = {}
    row = re.compile(r"^\| ([A-Z]{3}) \| `(\d\d_\w+)` \| .*? \| (start|formable) \|")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = row.match(line)
        if m:
            reg[m.group(1)] = (m.group(2), m.group(3))
    return reg


# ----------------------------------------------------------------------------------------
# Government-type trigger evaluation (three-valued: True / False / None = unknown)
# ----------------------------------------------------------------------------------------

class Ctx:
    def __init__(self, game: GameData, laws: set[str], tier, country_type, igs: set[str],
                 cultures: set[str] | None = None, subject: str | None = None,
                 state_count: int | None = None):
        self.game = game
        self.subject = subject            # subject_type_<x> when the tag is a subject at the start
        self.state_count = state_count
        self.laws = laws
        self.tier = tier
        self.country_type = country_type
        self.igs = igs
        self.cultures = cultures
        self.franchise = bool(laws & VOTING_LAWS)
        self.unsupported: set[str] = set()


def _and(vals):
    if any(v is False for v in vals):
        return False
    return None if any(v is None for v in vals) else True


def _or(vals):
    if any(v is True for v in vals):
        return True
    return None if any(v is None for v in vals) else False


def _not(v):
    return None if v is None else (not v)


def _yes(value: str) -> bool:
    return value == "yes"


def eval_items(items: list, ctx: Ctx):
    return _and([_eval_one(k, v, ctx) for k, v in items if k is not None])


def _eval_one(key: str, value, ctx: Ctx):
    if key in ("AND",):
        return eval_items(value, ctx)
    if key == "OR":
        return _or([_eval_one(k, v, ctx) for k, v in value if k is not None])
    if key == "NOT":
        return _not(eval_items(value, ctx))
    if key == "NOR":
        return _not(_or([_eval_one(k, v, ctx) for k, v in value if k is not None]))
    if key == "custom_tooltip":
        return eval_items([(k, v) for k, v in value if k != "text"], ctx)
    if key == "always":
        return _yes(value)
    if key in ("has_law", "has_law_or_variant"):
        return value.split(":", 1)[-1] in ctx.laws
    if key == "country_has_primary_culture":
        return None if ctx.cultures is None else value.split(":", 1)[-1] in ctx.cultures
    if key == "country_tier":
        return None if ctx.tier is None else ctx.tier == value
    if key == "is_country_type":
        return None if ctx.country_type is None else ctx.country_type == value
    if key == "country_has_voting_franchise":
        return ctx.franchise == _yes(value)
    if key == "is_subject_type":
        return ctx.subject == value
    if key in ("overlord", "top_overlord"):
        return False if ctx.subject is None else None   # the overlord's own laws are not resolved here
    if key in ("has_variable", "has_modifier"):
        return False  # start tags carry no runtime flags
    if key == "any_scope_state" and isinstance(value, list):
        ops = {"count<=": lambda n, x: n <= x, "count>=": lambda n, x: n >= x,
               "count<": lambda n, x: n < x, "count>": lambda n, x: n > x}
        inner = [(k, v) for k, v in value if k is not None]
        if ctx.state_count is not None and inner and all(k in ops for k, _ in inner):
            return _and([ops[k](ctx.state_count, int(v)) for k, v in inner])
        ctx.unsupported.add(key)
        return None
    if key == "has_gov_regency":
        return not _yes(value)
    if key.startswith("ig:") and isinstance(value, list):
        ruling = key[3:] in ctx.igs
        inner = [(k, v) for k, v in value if k != "is_in_government"]
        flags = [ruling == _yes(v) for k, v in value if k == "is_in_government"]
        return _and(flags + ([eval_items(inner, ctx)] if inner else []))
    if key == "ruler":
        return None
    if key in ctx.game.triggers and isinstance(value, str):
        verdict = eval_items(ctx.game.triggers[key], ctx)
        return verdict if _yes(value) else _not(verdict)
    ctx.unsupported.add(key)
    return None


# ----------------------------------------------------------------------------------------
# Region files
# ----------------------------------------------------------------------------------------

def _no_dupes(pairs):
    seen: dict = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"duplicate key {k!r}")
        seen[k] = v
    return seen


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_dupes)


BASELINE_REQUIRED = ("laws", "ruling_igs", "tax_level", "taxed_goods", "institutions", "source", "why")
TAG_FIELDS = ("laws",) + cc.DIRECT_FIELDS
DIRECT_FIELDS = cc.DIRECT_FIELDS


@dataclass
class Inputs:
    """Everything a region file is checked against besides the game data."""
    extras: dict = field(default_factory=dict)        # tag -> extra techs (starting_tech_extras.json)
    profiles: dict | None = None                      # profiles.json (None = file absent)
    owners: set | None = None                         # tags that own land at start (None = gate off)
    counts: dict = field(default_factory=dict)        # tag -> states owned at start
    subjects: dict = field(default_factory=dict)      # tag -> subject type id (subject_type_protectorate, ...)


SUBJECT_PACT = re.compile(r"create_diplomatic_pact\s*=\s*\{\s*country\s*=\s*c:(\w+)\s*type\s*=\s*(\w+)")


def load_subjects(folder: Path) -> dict[str, str]:
    """``{subject tag: subject_type_<type>}`` from the ``create_diplomatic_pact`` blocks of ``common/history/diplomacy``."""
    out: dict[str, str] = {}
    if folder.is_dir():
        for path in sorted(folder.glob("*.txt")):
            text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
            for tag, kind in SUBJECT_PACT.findall(text):
                out[tag] = f"subject_type_{kind}"
    return out


def compute_government(game: GameData, laws: set[str], defn: dict | None, igs: set[str],
                       subject: str | None, state_count: int | None):
    """The government type the engine picks: the first ``common/government_types`` entry, in file order,
    whose ``possible`` passes. Returns ``(name | None, undecided names before it, unsupported triggers)``."""
    ctx = Ctx(game, laws, defn["tier"] if defn else None, defn["country_type"] if defn else None, igs,
              defn["cultures"] if defn else None, subject=subject, state_count=state_count)
    undecided: list[str] = []
    for name, possible in game.gov_possible.items():
        verdict = eval_items(possible, ctx)
        if verdict is True:
            return name, undecided, ctx.unsupported
        if verdict is None:
            undecided.append(name)
    return None, undecided, ctx.unsupported


def check_package(pkg: dict, game: GameData, where: str,
                  errors: list[str], warnings: list[str],
                  covered: set[str] | None = None, label: str = "",
                  check_institutions: bool = False) -> None:
    """Check one *effective* package (a baseline, a shared profile or a resolved tag).

    ``covered`` is the tag's starting technology (``None`` = not evaluable, so the unlock check is
    skipped, as for baselines and profiles). ``check_institutions`` makes a non-zero institution level
    need an active law that names the institution (``institution =`` on the law)."""
    def err(msg):
        errors.append(f"{where}: {msg}")

    laws = pkg.get("laws", {})
    if not isinstance(laws, dict):
        err("laws must be an object {law_group: law}")
        return

    chosen: dict[str, str] = {}
    for group, law in laws.items():
        if group not in game.law_groups:
            err(f"unknown law group {group}")
            continue
        if isinstance(law, list):
            err(f"more than one law for {group}: {', '.join(map(str, law))}")
            continue
        if law not in game.laws:
            err(f"unknown law {law} (group {group})")
            continue
        if game.laws[law]["group"] != group:
            err(f"law {law} belongs to {game.laws[law]['group']}, not {group}")
            continue
        chosen[group] = law
    for group in sorted(game.law_groups - set(laws)):
        err(f"missing law group {group}")

    active = set(chosen.values())
    for law in sorted(active):
        info = game.laws[law]
        if covered is None or not (info["unlock_techs"] or info["unlock_laws"]):
            continue
        if any(t in covered for t in info["unlock_techs"]) or \
                any(l in active for l in info["unlock_laws"]):
            continue
        needs = [f"tech {t}" for t in info["unlock_techs"]] + \
                [f"law {l}" for l in info["unlock_laws"]]
        err(f"{law} is locked: needs {' or '.join(needs)} ({label} + extras "
            f"+ chosen laws do not provide it)")
    for law in sorted(active):
        for other in game.laws[law]["disallow"]:
            if other in active:
                err(f"{law} is disallowed alongside {other}")

    for ig in pkg.get("ruling_igs", []):
        if ig not in game.igs:
            err(f"unknown interest group {ig}")
    n_igs = len(pkg.get("ruling_igs", []))
    if not 1 <= n_igs <= 3 or len(set(pkg.get("ruling_igs", []))) != n_igs:
        err(f"ruling_igs must be 1-3 distinct groups (got {pkg.get('ruling_igs')})")
    if pkg.get("tax_level") not in TAX_LEVELS:
        err(f"unknown tax_level {pkg.get('tax_level')!r}")
    for good in pkg.get("taxed_goods", []):
        if good not in game.goods:
            err(f"unknown good {good} in taxed_goods")
    for entry in pkg.get("tariffs", []):
        if not isinstance(entry, dict) or entry.get("kind") not in ("import", "export") \
                or entry.get("level") not in TARIFF_LEVELS:
            err(f"malformed tariff entry {entry!r} (kind import|export, level in {sorted(TARIFF_LEVELS)})")
        elif entry.get("goods") not in game.goods:
            err(f"unknown good {entry.get('goods')} in tariffs")
    granted = {game.laws[l]["institution"] for l in active if game.laws[l].get("institution")}
    for inst, level in pkg.get("institutions", {}).items():
        if inst not in game.institutions:
            err(f"unknown institution {inst}")
        elif level not in INSTITUTION_LEVELS or isinstance(level, bool):
            err(f"institution level for {inst} must be 0-5 (got {level!r})")
        elif check_institutions and level and inst not in granted:
            err(f"{inst} level {level} but no chosen law grants it (an institution exists only under a law "
                f"that names it); drop the level or choose the law")
    for ig in pkg.get("suggested_ig_names", {}):
        if ig not in game.igs:
            err(f"unknown interest group {ig} in suggested_ig_names")

    election = pkg.get("next_election")
    if election is not None:
        m = re.fullmatch(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", str(election))
        if not m or int(m.group(1)) < START_YEAR or not 1 <= int(m.group(2)) <= 12 \
                or not 1 <= int(m.group(3)) <= 31:
            err(f"next_election {election!r} must be YYYY.M.D on or after {START_YEAR}.1.1")
    holds_elections = bool(active & VOTING_LAWS)
    if holds_elections and election is None:
        err("laws hold elections (voting franchise) but next_election is missing")
    if not holds_elections and election is not None:
        err("next_election set but the laws hold no elections")


def _justify_keys(tag: dict) -> set[str]:
    keys = {f for f in DIRECT_FIELDS if f in tag}
    keys |= {f"laws.{g}" for g in tag.get("laws", {})}
    return keys


def _source_why(obj: dict) -> bool:
    return all(isinstance(obj.get(f), str) and obj.get(f).strip() for f in ("source", "why"))


def validate_profiles(path: Path, game: GameData, profiles: dict | None) -> tuple[list[str], list[str], int]:
    """``profiles.json``: each profile is a full package (every baseline field, one source and why)."""
    errors: list[str] = []
    warnings: list[str] = []
    name = path.name
    if profiles is None:
        return errors, warnings, 0
    if not isinstance(profiles, dict):
        return [f"{name}: 'profiles' must be an object"], warnings, 0
    for pname in sorted(profiles):
        prof = profiles[pname]
        where = f"{name} profile {pname}"
        if not isinstance(prof, dict):
            errors.append(f"{where}: must be an object")
            continue
        for fld in BASELINE_REQUIRED:
            if fld not in prof:
                errors.append(f"{where}: incomplete profile, missing {fld} (a profile is a full package)")
        for fld in sorted(set(prof) - set(TAG_FIELDS) - {"source", "why"}):
            errors.append(f"{where}: unknown field {fld}")
        if not _source_why(prof):
            errors.append(f"{where}: needs a non-empty source and why")
        check_package(prof, game, where, errors, warnings, check_institutions=True)
    return errors, warnings, len(profiles)


def validate_region_file(path: Path, game: GameData, registry: dict, inp: Inputs | None = None,
                         collect: dict | None = None) -> tuple[list[str], list[str], int]:
    """Check one region file. ``collect`` receives ``{tag: (resolved package, computed government type)}``."""
    inp = inp or Inputs()
    errors: list[str] = []
    warnings: list[str] = []
    stem = path.stem
    name = path.name
    profiles = inp.profiles or {}

    try:
        data = _load_json(path)
    except (ValueError, OSError) as exc:
        return [f"{name}: cannot read: {exc}"], [], 0
    if not isinstance(data, dict) or not isinstance(data.get("baseline"), dict) \
            or not isinstance(data.get("tags"), dict):
        return [f"{name}: needs top-level 'region', 'baseline' and 'tags' objects"], [], 0
    if data.get("region") != stem:
        errors.append(f"{name}: 'region' is {data.get('region')!r}, expected {stem!r}")
    if "profiles" in data:
        errors.append(f"{name}: region-local profiles are gone; define the profile once in profiles.json")

    baseline = data["baseline"]
    for fld in BASELINE_REQUIRED:
        if fld not in baseline:
            errors.append(f"{name}: baseline missing {fld}")
    for fld in sorted(set(baseline) - set(TAG_FIELDS) - {"source", "why"}):
        errors.append(f"{name}: baseline has unknown field {fld}")
    if not _source_why(baseline):
        errors.append(f"{name}: baseline needs a non-empty source and why")
    check_package(baseline, game, f"{name} baseline", errors, warnings)

    region_tags = {t: kind for t, (r, kind) in registry.items() if r == stem}
    for tag in sorted(data["tags"]):
        if tag not in registry:
            errors.append(f"{name}: {tag}: not in the tag registry")
        elif registry[tag][0] != stem:
            errors.append(f"{name}: {tag}: registry places it in {registry[tag][0]}")
        elif registry[tag][1] == "formable":
            errors.append(f"{name}: {tag}: is a formable (formables are out of scope)")
        if inp.owners is not None and tag not in inp.owners:
            errors.append(f"{name}: {tag}: owns no state at start; move the entry to dormant/")
    for tag, kind in sorted(region_tags.items()):
        if inp.owners is not None and tag in inp.owners and tag not in data["tags"]:
            errors.append(f"{name}: {tag}: owner has no entry")
        if kind == "formable" and tag in inp.extras:
            errors.append(f"{name}: {tag}: is a formable; starting_tech_extras.json keys only start tags")

    for tag in sorted(data["tags"]):
        entry = data["tags"][tag]
        where = f"{name}: {tag}"
        if not isinstance(entry, dict):
            errors.append(f"{where}: entry must be an object")
            continue
        for fld in sorted(set(entry) - set(TAG_FIELDS) - {"justify", "confidence", "note", "profile"}):
            errors.append(f"{where}: unknown field {fld}")
        base_pkg = baseline
        kind = "baseline"
        if "profile" in entry:
            if entry["profile"] not in profiles:
                errors.append(f"{where}: unknown profile {entry['profile']!r}"
                              + (" (profiles.json is missing)" if inp.profiles is None else ""))
            else:
                base_pkg = profiles[entry["profile"]]
                kind = "profile"
        if entry.get("confidence") not in CONFIDENCE:
            errors.append(f"{where}: confidence must be one of {', '.join(CONFIDENCE)}")
        justify = entry.get("justify", {})
        if not isinstance(justify, dict):
            errors.append(f"{where}: justify must be an object")
            justify = {}
        for fld in sorted(DIRECT_FIELDS):
            if fld in entry and entry[fld] == base_pkg.get(fld):
                errors.append(f"{where}: {fld} repeats the {kind}; drop it")
        for group, law in sorted(entry.get("laws", {}).items()):
            if base_pkg.get("laws", {}).get(group) == law:
                errors.append(f"{where}: laws.{group} repeats the {kind}; drop it")
        needed = _justify_keys(entry)
        for key in sorted(needed):
            j = justify.get(key)
            if not (isinstance(j, dict) and str(j.get("source", "")).strip()
                    and str(j.get("why", "")).strip()):
                errors.append(f"{where}: non-default {key} needs justify.{key}.source and .why")
        for key in sorted(set(justify) - needed):
            errors.append(f"{where}: justify.{key} has no matching override")

        eff = cc.layer(base_pkg, entry)
        covered, label, tech_errs, tech_warns = game.coverage(tag, inp.extras.get(tag, []))
        errors.extend(f"{where}: {e}" for e in tech_errs)
        warnings.extend(f"{where}: {w}" for w in tech_warns)
        check_package(eff, game, where, errors, warnings, covered=covered, label=label, check_institutions=True)

        # the government type the engine would pick
        if len(eff.get("laws", {})) == len(game.law_groups):
            defn = game.definitions.get(tag)
            gov, undecided, unsupported = compute_government(
                game, set(eff["laws"].values()), defn, set(eff.get("ruling_igs", [])),
                inp.subjects.get(tag), inp.counts.get(tag))
            if gov is None and not undecided:
                errors.append(f"{where}: no government type matches these laws")
            elif undecided:
                extra = f"; unsupported trigger(s) {', '.join(sorted(unsupported))}" if unsupported else ""
                head = ", ".join(undecided[:3]) + (" ..." if len(undecided) > 3 else "")
                why = "no country definition (tier/type unknown)" if defn is None else "ruler- or market-dependent trigger"
                where_pick = f"before the pick {gov}" if gov else "and no entry passes"
                warnings.append(f"{where}: government type not fully decidable ({len(undecided)} undecided "
                                f"{where_pick}: {head}; {why}{extra})")
            if collect is not None:
                collect[tag] = (eff, gov)
        elif collect is not None:
            collect[tag] = (eff, None)

    return errors, warnings, len(data["tags"])


def run(game_root: Path, data_dir: Path, registry_path: Path, files: list[str] | None = None,
        vanilla_root: Path | None = None, extras_path: Path = DEFAULT_EXTRAS,
        ownership_path: Path | None = DEFAULT_OWNERSHIP, subjects_dir: Path | None = DEFAULT_SUBJECTS,
        dump_path: Path | None = None) -> tuple[int, str]:
    """Validate; return ``(exit_code, report_text)`` (deterministic)."""
    game = GameData(game_root, vanilla_root)
    registry = load_registry(registry_path)
    inp = Inputs(extras=ch.load_tech_extras(extras_path) if extras_path.is_file() else {})
    profiles_path = data_dir / cc.PROFILES_FILE
    if profiles_path.is_file():
        try:
            inp.profiles = _load_json(profiles_path).get("profiles", {})
        except (ValueError, OSError) as exc:
            return 1, "\n".join(game.notes + [f"ERROR: {cc.PROFILES_FILE}: cannot read: {exc}"]) + "\n"
    if ownership_path is not None and ownership_path.is_file():
        doc = json.loads(ownership_path.read_text(encoding="utf-8"))
        inp.owners = ch.owner_tags(doc) - {"UNO"}
        inp.counts = ch.owner_state_counts(doc)
    if subjects_dir is not None:
        inp.subjects = load_subjects(subjects_dir)
    paths = cc.region_files(data_dir)
    if files:
        wanted = {Path(f).name for f in files}
        paths = [p for p in paths if p.name in wanted]
    lines = list(game.notes)
    failed = 0
    total = len(paths)
    if not paths:
        lines.append("no region files found")
        return 1, "\n".join(lines) + "\n"
    collect: dict = {}
    if inp.profiles is not None and not files:
        errors, warnings, n = validate_profiles(profiles_path, game, inp.profiles)
        total += 1
        lines.extend(f"warning: {w}" for w in warnings)
        if errors:
            failed += 1
            lines.extend(f"ERROR: {e}" for e in errors)
            lines.append(f"FAIL {profiles_path.name}: {len(errors)} error(s)")
        else:
            lines.append(f"OK {profiles_path.name}: {n} profile(s)")
    for path in paths:
        errors, warnings, n_tags = validate_region_file(path, game, registry, inp, collect)
        for w in warnings:
            lines.append(f"warning: {w}")
        if errors:
            failed += 1
            lines.extend(f"ERROR: {e}" for e in errors)
            lines.append(f"FAIL {path.name}: {len(errors)} error(s)")
        else:
            lines.append(f"OK {path.name}: {n_tags} tag(s)")
    if not files:
        for tag in sorted(set(inp.extras) - set(registry)):   # keys on tags outside the roster (future tags)
            for tech in inp.extras[tag]:
                if tech not in game.techs:
                    failed += 1
                    lines.append(f"ERROR: starting_tech_extras.json: {tag}: unknown tech {tech}")
    if dump_path is not None:
        dump = {}
        for tag in sorted(collect):
            pkg, gov = collect[tag]
            dump[tag] = {**pkg, "_gov": gov}
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(json.dumps(dump, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
        lines.append(f"dumped {len(dump)} resolved package(s) to {dump_path}")
    lines.append(f"{total - failed}/{total} file(s) valid")
    return (1 if failed else 0), "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="region file names to check (default: all)")
    parser.add_argument("--game-root", type=Path, default=REPO)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--extras", type=Path, default=DEFAULT_EXTRAS,
                        help="starting_tech_extras.json (default: the generator's)")
    parser.add_argument("--ownership", type=Path, default=DEFAULT_OWNERSHIP,
                        help="state_ownership.json: who owns land at the start (the gate covers owners only)")
    parser.add_argument("--subjects", type=Path, default=DEFAULT_SUBJECTS,
                        help="common/history/diplomacy folder (subject pacts feed the government triggers)")
    parser.add_argument("--dump-resolved", type=Path, default=None,
                        help="write every checked tag's resolved package and computed government type as sorted JSON")
    parser.add_argument("--vanilla", type=Path, default=None,
                        help="vanilla install `game` folder or mirror (goods/institutions)")
    parser.add_argument("--quiet", action="store_true", help="hide warnings")
    args = parser.parse_args(argv)
    code, report = run(args.game_root, args.data_dir, args.registry, args.files or None, args.vanilla,
                       args.extras, args.ownership, args.subjects, args.dump_resolved)
    if args.quiet:
        report = "".join(l for l in report.splitlines(True) if not l.startswith("warning:"))
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
