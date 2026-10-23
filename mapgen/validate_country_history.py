#!/usr/bin/env python3
"""Validate the starting-country data files in ``mapgen/config/country_history/``.

Each ``NN_<stem>.json`` describes, per region, a ``baseline`` package plus per-tag
overrides for every *start* tag of that region in ``planning/tag_registry.md`` (schema:
``mapgen/config/country_history/README.md``). A later task generates
``common/history/countries/`` from these files; this linter is the gate that keeps them
consistent with the mod's own laws, interest groups, technologies and government types.

Hard errors (exit 1):

* an unknown law, law group, interest group, technology, good, institution, tax level,
  tariff level or tech-tier helper;
* a law that does not belong to its group key, more than one law for a group, or a law
  group with no law;
* a law whose unlock (``unlocking_technologies`` / ``unlocking_laws``) is not covered by the
  tag's tier helper + ``extra_techs`` / chosen laws, or an ``extra_tech`` whose own
  prerequisite is not covered;
* two chosen laws where one lists the other in ``disallowing_laws``;
* a tag that is not in the registry, is a formable, is in another region, or a start tag of
  the region with no entry;
* laws that do not satisfy the trigger of the tag's ``expected_government_type``;
* a non-default choice with no ``source`` / ``why`` (a ``profile`` carries one for its whole
  bundle), or a justification with nothing to justify;
* a malformed ``next_election`` (or one that disagrees with whether the laws hold elections).

Warnings never change the exit code: a government-type trigger that cannot be fully
evaluated (tier or ruler unknown), redundant ``extra_techs``.

Deterministic: pure stdlib, sorted output, no clock, no environment reads.

Usage::

    python mapgen/validate_country_history.py                 # every region file
    python mapgen/validate_country_history.py 02_empire.json  # one file
    python mapgen/validate_country_history.py --vanilla "<Victoria 3>/game"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO / "mapgen" / "config" / "country_history"
DEFAULT_REGISTRY = REPO / "planning" / "tag_registry.md"

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
                key = tok
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

        self.tier_helpers: dict[int, set[str]] = {}
        for key, body in _read_dir(game_root, "common/scripted_effects"):
            m = re.fullmatch(r"effect_starting_technology_tier_(\d)_tech", key)
            if not m or not isinstance(body, list):
                continue
            eras = set(_vals(body, "add_era_researched"))
            techs = set(_vals(body, "add_technology_researched"))
            for tech, info in self.techs.items():
                if info["era"] in eras:
                    techs.add(tech)
            self.tier_helpers[int(m.group(1))] = techs

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
                 cultures: set[str] | None = None):
        self.game = game
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
    if key in ("is_subject_type", "has_variable", "has_modifier", "overlord", "top_overlord"):
        return False  # start tags are independent, have no regency and carry no runtime flags
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


BASELINE_REQUIRED = ("tech_tier", "extra_techs", "laws", "ruling_igs", "tax_level", "taxed_goods",
                     "institutions", "expected_government_type", "source", "why")
TAG_FIELDS = ("tech_tier", "extra_techs", "laws", "ruling_igs", "tax_level", "taxed_goods",
              "tariffs", "institutions", "next_election", "expected_government_type",
              "suggested_ig_names")
DIRECT_FIELDS = tuple(f for f in TAG_FIELDS if f != "laws")


def _layer(base: dict, top: dict) -> dict:
    """``top`` over ``base``: fields replace, ``laws`` merge per law group."""
    eff = {k: v for k, v in base.items() if k in TAG_FIELDS}
    eff["laws"] = dict(base.get("laws", {}))
    for field in DIRECT_FIELDS:
        if field in top:
            eff[field] = top[field]
    eff["laws"].update(top.get("laws", {}))
    return eff


def check_package(pkg: dict, game: GameData, where: str, defn: dict | None,
                  errors: list[str], warnings: list[str], evaluate_gov: bool = True) -> None:
    """Check one *effective* package (baseline, profile or baseline+overrides).

    ``evaluate_gov`` is off for baselines and profiles: a government trigger depends on the
    tag's tier and country type, so only the resolved tag is evaluated."""
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

    # technology coverage
    tier = pkg.get("tech_tier")
    covered: set[str] = set()
    if tier not in game.tier_helpers:
        err(f"unknown tech_tier {tier!r} (helpers: {sorted(game.tier_helpers)})")
    else:
        covered |= game.tier_helpers[tier]
    extras = pkg.get("extra_techs", [])
    for tech in extras:
        if tech not in game.techs:
            err(f"unknown tech {tech} in extra_techs")
        elif tech in covered:
            warnings.append(f"{where}: extra tech {tech} is already granted by tier {tier}")
    covered |= {t for t in extras if t in game.techs}
    for tech in sorted(set(extras)):
        if tech in game.techs:
            reqs = game.techs[tech]["requires"]
            if reqs and not any(r in covered for r in reqs):
                err(f"extra tech {tech} needs one of {', '.join(reqs)}")

    active = set(chosen.values())
    for law in sorted(active):
        info = game.laws[law]
        if not (info["unlock_techs"] or info["unlock_laws"]):
            continue
        if any(t in covered for t in info["unlock_techs"]) or \
                any(l in active for l in info["unlock_laws"]):
            continue
        needs = [f"tech {t}" for t in info["unlock_techs"]] + \
                [f"law {l}" for l in info["unlock_laws"]]
        err(f"{law} is locked: needs {' or '.join(needs)} (tier {tier} + extra_techs "
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
    for inst, level in pkg.get("institutions", {}).items():
        if inst not in game.institutions:
            err(f"unknown institution {inst}")
        if level not in INSTITUTION_LEVELS or isinstance(level, bool):
            err(f"institution level for {inst} must be 0-5 (got {level!r})")
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

    gov = pkg.get("expected_government_type")
    if gov not in game.gov_possible:
        err(f"unknown expected_government_type {gov!r}")
    elif evaluate_gov and len(chosen) == len(game.law_groups):
        ctx = Ctx(game, active, defn["tier"] if defn else None,
                  defn["country_type"] if defn else None, set(pkg.get("ruling_igs", [])),
                  defn["cultures"] if defn else None)
        verdict = eval_items(game.gov_possible[gov], ctx)
        if verdict is False:
            err(f"laws do not satisfy {gov}'s possible trigger")
        elif verdict is None:
            why = "no country definition (tier/type unknown)" if defn is None else "ruler-dependent trigger"
            extra = f"; unsupported trigger(s) {', '.join(sorted(ctx.unsupported))}" if ctx.unsupported else ""
            warnings.append(f"{where}: {gov} not fully evaluable ({why}{extra})")


def _justify_keys(tag: dict) -> set[str]:
    keys = {f for f in DIRECT_FIELDS if f in tag}
    keys |= {f"laws.{g}" for g in tag.get("laws", {})}
    return keys


def validate_region_file(path: Path, game: GameData, registry: dict) -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    warnings: list[str] = []
    stem = path.stem
    name = path.name

    try:
        data = _load_json(path)
    except (ValueError, OSError) as exc:
        return [f"{name}: cannot read: {exc}"], [], 0
    if not isinstance(data, dict) or not isinstance(data.get("baseline"), dict) \
            or not isinstance(data.get("tags"), dict):
        return [f"{name}: needs top-level 'region', 'baseline' and 'tags' objects"], [], 0
    if data.get("region") != stem:
        errors.append(f"{name}: 'region' is {data.get('region')!r}, expected {stem!r}")

    baseline = data["baseline"]
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        errors.append(f"{name}: profiles must be an object")
        profiles = {}
    for field in BASELINE_REQUIRED:
        if field not in baseline:
            errors.append(f"{name}: baseline missing {field}")
    for field in sorted(set(baseline) - set(TAG_FIELDS) - {"source", "why"}):
        errors.append(f"{name}: baseline has unknown field {field}")
    if not all(isinstance(baseline.get(f), str) and baseline.get(f).strip() for f in ("source", "why")):
        errors.append(f"{name}: baseline needs a non-empty source and why")
    check_package(baseline, game, f"{name} baseline", None, errors, warnings, evaluate_gov=False)

    # Profiles: named partial packages layered over the baseline (one source/why for the
    # whole bundle) that several tags share, e.g. a tribal confederacy in a feudal region.
    profile_pkgs: dict[str, dict] = {}
    for pname in sorted(profiles):
        prof = profiles[pname]
        pwhere = f"{name} profile {pname}"
        if not isinstance(prof, dict):
            errors.append(f"{pwhere}: must be an object")
            continue
        for field in sorted(set(prof) - set(TAG_FIELDS) - {"source", "why"}):
            errors.append(f"{pwhere}: unknown field {field}")
        if not all(isinstance(prof.get(f), str) and prof.get(f).strip() for f in ("source", "why")):
            errors.append(f"{pwhere}: needs a non-empty source and why")
        for field in sorted(DIRECT_FIELDS):
            if field in prof and prof[field] == baseline.get(field):
                errors.append(f"{pwhere}: {field} repeats the baseline; drop it")
        for group, law in sorted(prof.get("laws", {}).items()):
            if baseline.get("laws", {}).get(group) == law:
                errors.append(f"{pwhere}: laws.{group} repeats the baseline; drop it")
        profile_pkgs[pname] = _layer(baseline, prof)
        check_package(profile_pkgs[pname], game, pwhere, None, errors, warnings, evaluate_gov=False)

    region_tags = {t: kind for t, (r, kind) in registry.items() if r == stem}
    for tag in sorted(data["tags"]):
        if tag not in registry:
            errors.append(f"{name}: {tag}: not in the tag registry")
        elif registry[tag][0] != stem:
            errors.append(f"{name}: {tag}: registry places it in {registry[tag][0]}")
        elif registry[tag][1] == "formable":
            errors.append(f"{name}: {tag}: is a formable (formables are out of scope)")
    for tag, kind in sorted(region_tags.items()):
        if kind == "start" and tag not in data["tags"]:
            errors.append(f"{name}: {tag}: start tag has no entry")

    for tag in sorted(data["tags"]):
        entry = data["tags"][tag]
        where = f"{name}: {tag}"
        if not isinstance(entry, dict):
            errors.append(f"{where}: entry must be an object")
            continue
        for field in sorted(set(entry) - set(TAG_FIELDS) - {"justify", "confidence", "note", "profile"}):
            errors.append(f"{where}: unknown field {field}")
        base_pkg = baseline
        if "profile" in entry:
            if entry["profile"] not in profile_pkgs:
                errors.append(f"{where}: unknown profile {entry['profile']!r}")
            else:
                base_pkg = profile_pkgs[entry["profile"]]
        if entry.get("confidence") not in CONFIDENCE:
            errors.append(f"{where}: confidence must be one of {', '.join(CONFIDENCE)}")
        justify = entry.get("justify", {})
        if not isinstance(justify, dict):
            errors.append(f"{where}: justify must be an object")
            justify = {}
        for field in sorted(DIRECT_FIELDS):
            if field in entry and entry[field] == base_pkg.get(field):
                errors.append(f"{where}: {field} repeats the {'profile' if base_pkg is not baseline else 'baseline'}; drop it")
        for group, law in sorted(entry.get("laws", {}).items()):
            if base_pkg.get("laws", {}).get(group) == law:
                errors.append(f"{where}: laws.{group} repeats the {'profile' if base_pkg is not baseline else 'baseline'}; drop it")
        needed = _justify_keys(entry)
        for key in sorted(needed):
            j = justify.get(key)
            if not (isinstance(j, dict) and str(j.get("source", "")).strip()
                    and str(j.get("why", "")).strip()):
                errors.append(f"{where}: non-default {key} needs justify.{key}.source and .why")
        for key in sorted(set(justify) - needed):
            errors.append(f"{where}: justify.{key} has no matching override")

        eff = _layer(base_pkg, entry)
        check_package(eff, game, where, game.definitions.get(tag), errors, warnings)

    return errors, warnings, len(data["tags"])


def run(game_root: Path, data_dir: Path, registry_path: Path, files: list[str] | None = None,
        vanilla_root: Path | None = None) -> tuple[int, str]:
    """Validate; return ``(exit_code, report_text)`` (deterministic)."""
    game = GameData(game_root, vanilla_root)
    registry = load_registry(registry_path)
    paths = sorted(data_dir.glob("[0-9][0-9]_*.json"))
    if files:
        wanted = {Path(f).name for f in files}
        paths = [p for p in paths if p.name in wanted]
    lines = list(game.notes)
    failed = 0
    if not paths:
        lines.append("no region files found")
        return 1, "\n".join(lines) + "\n"
    for path in paths:
        errors, warnings, n_tags = validate_region_file(path, game, registry)
        for w in warnings:
            lines.append(f"warning: {w}")
        if errors:
            failed += 1
            lines.extend(f"ERROR: {e}" for e in errors)
            lines.append(f"FAIL {path.name}: {len(errors)} error(s)")
        else:
            lines.append(f"OK {path.name}: {n_tags} tag(s)")
    lines.append(f"{len(paths) - failed}/{len(paths)} region file(s) valid")
    return (1 if failed else 0), "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="region file names to check (default: all)")
    parser.add_argument("--game-root", type=Path, default=REPO)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--vanilla", type=Path, default=None,
                        help="vanilla install `game` folder or mirror (goods/institutions)")
    parser.add_argument("--quiet", action="store_true", help="hide warnings")
    args = parser.parse_args(argv)
    code, report = run(args.game_root, args.data_dir, args.registry, args.files or None, args.vanilla)
    if args.quiet:
        report = "".join(l for l in report.splitlines(True) if not l.startswith("warning:"))
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
