#!/usr/bin/env python3
"""Independent tech-gate verifier for ``common/history/buildings/*.txt``.

A building or production method in a country that has not researched its unlocking
technology crashes the game at load. This script re-derives the answer from scratch and
shares **no code** with ``generate_building_history.py`` / ``worldgen/building_history.py``
(own scanner, own effect evaluator, own gate), so a bug in the generator's selection logic
cannot hide here.

It parses the **emitted** building files and the **current** ``common/history/countries``
and fails on:

* a tag whose techs / laws cannot be fully resolved from its start-setup block and that
  still has a building or method needing any tech or law (unresolved = no techs, no laws);
* a building whose ``unlocking_technologies`` are not all researched by the owner, or that
  has a ``possible`` trigger;
* a production method whose techs are not all researched, whose ``unlocking_laws`` are not
  all active, whose ``disallowing_laws`` are active, whose ``unlocking_production_methods``
  are not all among the building's chosen methods, or that carries an
  ``unlocking_principles`` / ``unlocking_identity`` / ``unlocking_company_categories`` /
  ``unlocking_geographic_regions`` entry;
* a building without exactly one method per production method group;
* a ``region_state`` the state history does not create, a ``c:UNO`` block, an owner that is
  not a defined country, an unknown building / method id.

Gate semantics are deliberately the strict reading (every listed tech / law / method is
required) so that the verifier can only reject more than the engine, never less.

Usage::

    python mapgen/validate_building_history.py            # exit 1 on any violation
    python mapgen/validate_building_history.py --root DIR # another mod root (fixtures)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
GATE_FIELDS_BLOCK = ("unlocking_principles", "unlocking_identity", "unlocking_company_categories",
                     "unlocking_geographic_regions")


# --- a tiny scanner: depth-aware statement list -------------------------------------------

def _clean(text: str) -> str:
    return re.sub(r"#[^\n]*", "", text.replace("﻿", ""))


def _statements(body: str) -> list[tuple[str, str | None, str]]:
    """Statements of one block body as ``(key, kind, value)`` where kind is ``'='`` and value a
    scalar, ``'{'`` and value the raw inner text of a block, or ``(None-key)`` bare words."""
    out: list[tuple[str, str | None, str]] = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c.isspace():
            i += 1
            continue
        j = i
        if c == '"':
            j = body.index('"', i + 1) + 1
        else:
            while j < n and not body[j].isspace() and body[j] not in "={}":
                j += 1
        key = body[i:j].strip('"')
        k = j
        while k < n and body[k].isspace():
            k += 1
        if k < n and body[k] in "=<>!?" and key:
            while k < n and body[k] in "=<>!?":
                k += 1
            while k < n and body[k].isspace():
                k += 1
            if k < n and body[k] == "{":
                depth, m = 0, k
                while m < n:
                    if body[m] == "{":
                        depth += 1
                    elif body[m] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    m += 1
                else:
                    raise ValueError("unbalanced braces")
                out.append((key, "{", body[k + 1:m]))
                i = m + 1
            else:
                if body[k] == '"':
                    e = body.index('"', k + 1) + 1
                else:
                    e = k
                    while e < n and not body[e].isspace() and body[e] not in "{}":
                        e += 1
                out.append((key, "=", body[k:e].strip('"')))
                i = e
        else:
            if key:
                out.append((key, None, ""))
            i = max(j, i + 1)
    return out


def _words(body: str) -> list[str]:
    return [k for k, kind, _ in _statements(body) if kind is None]


def _blocks(path: Path) -> dict[str, str]:
    return {k: v for k, kind, v in _statements(_clean(path.read_text(encoding="utf-8"))) if kind == "{"}


def _field_words(body: str, name: str) -> list[str]:
    for k, kind, v in _statements(body):
        if k == name and kind == "{":
            return _words(v)
    return []


def _has(body: str, name: str) -> bool:
    return any(k == name for k, _, _ in _statements(body))


# --- definitions ----------------------------------------------------------------------------

def load_defs(root: Path):
    c = root / "common"
    buildings, groups, pms, law_group, ctypes = {}, {}, {}, {}, {}
    for p in sorted((c / "buildings").glob("*.txt")):
        for k, v in _blocks(p).items():
            buildings[k] = {"techs": _field_words(v, "unlocking_technologies"),
                            "groups": _field_words(v, "production_method_groups"), "possible": _has(v, "possible")}
    for p in sorted((c / "production_method_groups").glob("*.txt")):
        for k, v in _blocks(p).items():
            groups[k] = _field_words(v, "production_methods")
    for p in sorted((c / "production_methods").glob("*.txt")):
        for k, v in _blocks(p).items():
            pms[k] = {"techs": _field_words(v, "unlocking_technologies"), "laws_in": _field_words(v, "unlocking_laws"),
                      "laws_out": _field_words(v, "disallowing_laws"), "pms_in": _field_words(v, "unlocking_production_methods"),
                      "bad": [f for f in GATE_FIELDS_BLOCK if _has(v, f)]}
    for p in sorted((c / "laws").glob("*.txt")):
        for k, v in _blocks(p).items():
            g = [x for kk, kind, x in _statements(v) if kk == "group" and kind == "="]
            law_group[k] = g[0] if g else k
    for p in sorted((c / "country_definitions").glob("*.txt")):
        for k, v in _blocks(p).items():
            if re.fullmatch(r"[A-Z][A-Z0-9]{2}", k) and not re.search(r"dynamic_country_definition\s*=\s*yes", v):
                m = re.search(r"country_type\s*=\s*(\w+)", v)
                ctypes[k] = m.group(1) if m else None
    effects = {}
    for p in sorted((c / "scripted_effects").glob("*.txt")):
        effects.update(_blocks(p))
    return buildings, groups, pms, law_group, ctypes, effects


# --- tech / law resolution (from the emitted country history only) ---------------------------

class Unresolved(Exception):
    pass


def _run(body: str, ctype, techs: set, laws: dict, effects, law_group, stack=()):
    prev = None
    for key, kind, val in _statements(body):
        was, prev = prev, None
        if key == "add_technology_researched" and kind == "=":
            techs.add(val)
        elif key == "add_era_researched" or key in ("set_tax_level", "add_taxed_goods"):
            pass
        elif key == "activate_law" and kind == "=" and val.startswith("law_type:"):
            law = val.split(":", 1)[1]
            laws[law_group.get(law, law)] = law
        elif key == "if" and kind == "{":
            inner = _statements(val)
            lim = [s for s in inner if s[0] == "limit"]
            if len(lim) != 1 or lim[0][1] != "{":
                raise Unresolved("if without evaluable limit")
            conds = _statements(lim[0][2])
            if len(conds) != 1 or conds[0][0] != "is_country_type" or conds[0][1] != "=":
                raise Unresolved("unevaluable limit")
            prev = (ctype == conds[0][2])
            if prev:
                rest = "\n".join(f"{k} = {{ {v} }}" if kd == "{" else (f"{k} = {v}" if kd == "=" else k)
                                 for k, kd, v in inner if k != "limit")
                _run(rest, ctype, techs, laws, effects, law_group, stack)
        elif key == "else" and kind == "{":
            if was is None:
                raise Unresolved("else without if")
            if not was:
                _run(val, ctype, techs, laws, effects, law_group, stack)
        elif kind == "=" and val == "yes" and key in effects:
            if key in stack:
                raise Unresolved("cycle")
            _run(effects[key], ctype, techs, laws, effects, law_group, stack + (key,))
        else:
            raise Unresolved(f"cannot evaluate {key}")


def tag_sets(root: Path, ctypes, effects, law_group) -> dict[str, tuple[set, set] | None]:
    """``{tag: (techs, laws)}`` or ``None`` for an unresolvable / duplicated / undefined tag."""
    out: dict[str, tuple[set, set] | None] = {}
    seen: dict[str, int] = {}
    for p in sorted((root / "common" / "history" / "countries").glob("*.txt")):
        for key, kind, val in _statements(_clean(p.read_text(encoding="utf-8"))):
            if key != "COUNTRIES" or kind != "{":
                continue
            for k2, kd2, v2 in _statements(val):
                if not (k2.startswith("c:") and kd2 == "{"):
                    continue
                tag = k2[2:]
                seen[tag] = seen.get(tag, 0) + 1
                if tag not in ctypes or seen[tag] > 1:
                    out[tag] = None
                    continue
                techs: set = set()
                laws: dict = {}
                try:
                    _run(v2, ctypes[tag], techs, laws, effects, law_group)
                    out[tag] = (techs, set(laws.values()))
                except (Unresolved, ValueError):
                    out[tag] = None
    return out


# --- emitted buildings --------------------------------------------------------------------------

def _owners(root: Path) -> dict[str, set[str]]:
    res: dict[str, set[str]] = {}
    for p in sorted((root / "common" / "history" / "states").glob("*.txt")):
        for key, kind, val in _statements(_clean(p.read_text(encoding="utf-8"))):
            if key != "STATES" or kind != "{":
                continue
            for sk, sd, sv in _statements(val):
                if sk.startswith("s:") and sd == "{":
                    for ck, cd, cv in _statements(sv):
                        if ck == "create_state" and cd == "{":
                            for k3, d3, v3 in _statements(cv):
                                if k3 == "country" and d3 == "=" and v3.startswith("c:"):
                                    res.setdefault(sk[2:], set()).add(v3[2:])
    return res


def verify_texts(texts: dict[str, str], root: Path) -> list[str]:
    buildings, groups, pms, law_group, ctypes, effects = load_defs(root)
    sets = tag_sets(root, ctypes, effects, law_group)
    owners = _owners(root)
    errs: list[str] = []
    for name, text in sorted(texts.items()):
        try:
            top = [(k, kd, v) for k, kd, v in _statements(_clean(text))]
        except ValueError as exc:
            errs.append(f"{name}: {exc}")
            continue
        if text.count("{") != text.count("}"):
            errs.append(f"{name}: braces do not balance")
            continue
        for k, kd, v in top:
            if k != "BUILDINGS" or kd != "{":
                errs.append(f"{name}: unexpected top-level entry {k!r}")
                continue
            for sk, sd, sv in _statements(v):
                if not (sk.startswith("s:") and sd == "{"):
                    errs.append(f"{name}: unexpected entry {sk!r} under BUILDINGS")
                    continue
                state = sk[2:]
                for rk, rd, rv in _statements(sv):
                    if not (rk.startswith("region_state:") and rd == "{"):
                        errs.append(f"{name}: {state}: unexpected entry {rk!r}")
                        continue
                    tag = rk.split(":", 1)[1]
                    where = f"{name}: {state}/c:{tag}"
                    if tag == "UNO":
                        errs.append(f"{where}: buildings for c:UNO")
                    if tag not in owners.get(state, set()):
                        errs.append(f"{where}: history/states does not create this (state, owner)")
                    if tag not in sets:
                        errs.append(f"{where}: no c:{tag} block in common/history/countries")
                    s = sets.get(tag)
                    techs, laws = s if s else (set(), set())
                    for bk, bd, bv in _statements(rv):
                        if bk != "create_building" or bd != "{":
                            errs.append(f"{where}: unexpected entry {bk!r}")
                            continue
                        errs += _check_building(where, tag, s is not None, techs, laws, bv, buildings, groups, pms)
    return errs


def _check_building(where, tag, resolved, techs, laws, body, buildings, groups, pms) -> list[str]:
    errs: list[str] = []
    st = _statements(body)
    bid = next((v for k, kd, v in st if k == "building" and kd == "="), None)
    if bid is None or bid not in buildings:
        return [f"{where}: unknown building {bid!r}"]
    b = buildings[bid]
    if b["possible"]:
        errs.append(f"{where}: {bid} has a possible trigger (not provable statically)")
    for t in b["techs"]:
        if t not in techs:
            errs.append(f"{where}: {bid} needs tech {t}, which c:{tag} has not researched"
                        + ("" if resolved else " (tech set unresolved)"))
    own = next((v for k, kd, v in st if k == "add_ownership" and kd == "{"), None)
    if own is not None:
        for k, kd, v in _statements(own):
            if kd == "{":
                inner = {a: c for a, ad, c in _statements(v) if ad == "="}
                if k == "building":
                    ob = inner.get("type")
                    if ob not in buildings:
                        errs.append(f"{where}: ownership building {ob!r} is unknown")
                    else:
                        for t in buildings[ob]["techs"]:
                            if t not in techs:
                                errs.append(f"{where}: ownership building {ob} needs tech {t}, which c:{tag} has not researched")
                        if buildings[ob]["possible"]:
                            errs.append(f"{where}: ownership building {ob} has a possible trigger")
                    if inner.get("country") != f"c:{tag}":
                        errs.append(f"{where}: ownership country {inner.get('country')!r} is not c:{tag}")
                elif k == "country" and inner.get("country") != f"c:{tag}":
                    errs.append(f"{where}: ownership country {inner.get('country')!r} is not c:{tag}")
    apm = next((v for k, kd, v in st if k == "activate_production_methods" and kd == "{"), None)
    chosen = _words(apm) if apm is not None else []
    for m in chosen:
        if m not in pms:
            errs.append(f"{where}: {bid}: unknown production method {m}")
        elif not any(m in groups.get(g, []) for g in b["groups"]):
            errs.append(f"{where}: {bid}: {m} is not a method of any of the building's groups")
    for g in b["groups"]:                       # methods are shared between groups, so count per group
        members = [m for m in chosen if m in groups.get(g, [])]
        if not members:
            errs.append(f"{where}: {bid}: no method for group {g}")
        elif len(members) > 1:
            errs.append(f"{where}: {bid}: two methods ({', '.join(members)}) for group {g}")
    for m in chosen:
        if m not in pms:
            continue
        p = pms[m]
        for t in p["techs"]:
            if t not in techs:
                errs.append(f"{where}: {bid}: {m} needs tech {t}, which c:{tag} has not researched"
                            + ("" if resolved else " (tech set unresolved)"))
        for x in p["bad"]:
            errs.append(f"{where}: {bid}: {m} carries {x}")
        if p["laws_in"] or p["laws_out"]:
            if not resolved:
                errs.append(f"{where}: {bid}: {m} has a law condition and c:{tag}'s laws are unresolved")
            else:
                for l in p["laws_in"]:
                    if l not in laws:
                        errs.append(f"{where}: {bid}: {m} needs law {l}")
                for l in p["laws_out"]:
                    if l in laws:
                        errs.append(f"{where}: {bid}: {m} is disallowed by law {l}")
        for x in p["pms_in"]:
            if x not in chosen:
                errs.append(f"{where}: {bid}: {m} needs method {x} among the building's methods")
    return errs


def verify(root: Path) -> list[str]:
    d = root / "common" / "history" / "buildings"
    texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.txt"))}
    return verify_texts(texts, root)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = ap.parse_args(argv)
    errs = verify(args.root)
    for e in errs:
        print(f"ERROR: {e}", file=sys.stderr)
    if errs:
        print(f"validate_building_history: {len(errs)} violation(s)", file=sys.stderr)
        return 1
    n = len(list((args.root / "common" / "history" / "buildings").glob("*.txt")))
    print(f"validate_building_history: {n} files pass the tech gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
