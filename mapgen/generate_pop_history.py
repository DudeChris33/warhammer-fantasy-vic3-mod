#!/usr/bin/env python3
"""Write starting pops into ``common/history/pops/NN_*.txt`` and per-country
wealth/literacy into ``common/history/population/NN_*.txt``.

Reads the hand-authored ``mapgen/config/pop_history/*.json`` (see its README), the
emitted ``common/history/states`` (which (state, owner) pairs the game creates),
``common/country_definitions``, ``common/cultures``, ``common/religions`` and
``common/pop_types``; writes one file per land ``map_data/state_regions/NN_*.txt``
in each of the two history folders. Rules (exact integer splits, skipped owners
and cultures, dropped small pops, stable ordering) are in
``worldgen/pop_history.py``. Output is UTF-8 with a BOM and LF endings, like the
sibling generated files. A generated file set: never hand-edit it.

Usage::

    python mapgen/generate_pop_history.py                   # write both history folders
    python mapgen/generate_pop_history.py --check           # exit 1 if stale or invalid
    python mapgen/generate_pop_history.py --refresh-weights # rebuild config/pop_history/state_weights.json
    python mapgen/generate_pop_history.py --report-md PATH  # also write the review-sheet tables
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worldgen import pop_history as ph  # noqa: E402
from worldgen import state_history as sh  # noqa: E402

MOD_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = MOD_ROOT / "mapgen" / "config" / "pop_history"
BOM = b"\xef\xbb\xbf"


def load_world(root: Path) -> ph.World:
    ownership = json.loads((root / "mapgen" / "derived" / "state_ownership.json").read_text(encoding="utf-8"))
    history = {p.name: sh.parse_history_text(p.read_text(encoding="utf-8-sig"))
               for p in sorted((root / "common" / "history" / "states").glob("*.txt"))}
    return ph.World(
        states_by_file=sh.load_states_by_file(root / "map_data" / "state_regions"),
        ownership=ownership,
        history=history,
        countries=ph.load_countries(root / "common" / "country_definitions"),
        cultures=ph.load_cultures(root / "common" / "cultures"),
        religions=ph.load_ids(root / "common" / "religions"),
        pop_types=ph.load_ids(root / "common" / "pop_types"),
        slavery=ph.load_slavery(root / "mapgen" / "config" / "country_history"),
        homelands={k: v for p in sorted((root / "common" / "history" / "states").glob("*.txt"))
                   for k, v in sh.parse_homelands(p.read_text(encoding="utf-8-sig")).items()},
        tech_tier=_tiers(root / "mapgen" / "config" / "country_history"),
    )


def _tiers(d: Path) -> dict[str, int] | None:
    if not d.is_dir() or not list(d.glob("*.json")):
        return None
    out: dict[str, int] = {}
    for f in sorted(d.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for tag, v in doc.get("tags", {}).items():
            prof = doc.get("profiles", {}).get(v.get("profile"), {})
            out[tag] = v.get("tech_tier", prof.get("tech_tier", doc.get("baseline", {}).get("tech_tier")))
    return out


def build(root: Path, config_dir: Path) -> tuple[ph.Config, ph.World, ph.Plan, dict[str, str], dict[str, str]]:
    cfg = ph.load_config(config_dir)
    world = load_world(root)
    p = ph.plan(cfg, world)
    pops, population = ph.render_all(p)
    return cfg, world, p, pops, population


def _read(path: Path) -> str | None:
    return sh.normalize_text(path.read_text(encoding="utf-8")) if path.exists() else None


def run(root: Path, config_dir: Path, check: bool, report_md: Path | None = None) -> int:
    cfg, world, p, pops, population = build(root, config_dir)
    errors = ph.invariants(p, cfg) + ph.check_texts(pops, population, world)
    print(ph.summary(p, cfg))
    if report_md is not None:
        report_md.write_text(markdown_report(cfg, world, p), encoding="utf-8")
    out = {root / "common" / "history" / "pops": pops, root / "common" / "history" / "population": population}
    if check:
        for folder, texts in out.items():
            for name, text in sorted(texts.items()):
                if _read(folder / name) != text:
                    errors.append(f"{folder.relative_to(root)}/{name} is stale -- run generate_pop_history.py")
    else:
        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            return 1
        for folder, texts in out.items():
            folder.mkdir(parents=True, exist_ok=True)
            for name, text in sorted(texts.items()):
                (folder / name).write_bytes(BOM + text.encode("utf-8"))
        print(f"wrote {sum(len(t) for t in out.values())} files")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    return 1 if errors else 0


def markdown_report(cfg: ph.Config, world: ph.World, p: ph.Plan) -> str:
    """The review sheet: calibration table, top states per region file, overrides,
    wealth/literacy, skips and drops."""
    L: list[str] = [f"## Scale factor\n\ngame total = canon-scale figure x {cfg.scale}; minimum pop size {cfg.min_pop}.\n"]
    tot: dict[str, int] = {}
    uno = [u for u in p.units if u.tag == sh.UNO_TAG]
    for u in p.units:
        if u.tag != sh.UNO_TAG:
            tot[u.tag] = tot.get(u.tag, 0) + u.allot
    L += ["## Calibration (tags that own states)\n", "| Tag | Canon-scale | Game total | Confidence | Source |", "|---|---|---|---|---|"]
    for tag in sorted(tot):
        c = cfg.calib[tag]
        L.append(f"| {tag} | {c['canon']:,} | {tot[tag]:,} | {c['confidence']} | {c['source']} |")
    if uno and cfg.unclaimed:
        uc = cfg.unclaimed
        L += [f"\n## Unclaimed land (c:{sh.UNO_TAG}, outside calibration)\n",
              f"{len(uno)} states x {uc['culture']} {uc['size']:,} = {sum(u.allot for u in uno):,} people "
              f"(`calibration.json` `unclaimed_pop`; {uc['source']}). Not counted in the tag totals above.\n"]
    L.append("\n## Ten most populous states per region\n")
    for fname, us in p.files.items():
        top = sorted((u for u in us if u.tag != sh.UNO_TAG), key=lambda u: (-u.allot, u.key, u.tag))[:10]
        L.append(f"**{fname[:-4]}**\n")
        if not top:
            L.append("_no owned states_\n")
            continue
        L += ["| State | Owner | Population |", "|---|---|---|"]
        L += [f"| {u.key} | {u.tag} | {u.allot:,} |" for u in top]
        L.append("")
    L += ["## Distribution overrides\n", "| State | Tag | Override | Source | Why |", "|---|---|---|---|---|"]
    for o in cfg.dist_overrides:
        v = f"x{o['multiplier']}" if "multiplier" in o else f"share {o['share']}"
        L.append(f"| {o['key']} | {o.get('tag', '')} | {v} | {o['source']} | {o['why']} |")
    L += ["\n## Culture / religion overrides\n", "| State | Mode | Culture | Religion | Pop type | Share % | Source |", "|---|---|---|---|---|---|---|"]
    for tag, e in sorted(cfg.tag_mixes.items()):
        for m in e:
            L.append(f"| (all {tag}) | tag mix | {m['culture']} | {m.get('religion', '')} | {m.get('pop_type', '')} | {m['share']} | {m.get('source', '')} |")
    for o in cfg.state_mixes:
        for m in o["mix"]:
            L.append(f"| {o['key']} | {o['mode']} | {m['culture']} | {m.get('religion', '')} | {m.get('pop_type', '')} | {m['share']} | {m['source']} |")
    for (tag, cu), rules in sorted(cfg.religion_splits.items()):
        for r in rules:
            # share is percent of the culture's people in the tag, not of the state
            L.append(f"| (all {tag}) | religion split | {cu} | {r['religion']} | | {r['share']} | {r['source']} |")
    L += ["\n## Wealth / literacy\n", "| Tag | Wealth | Literacy | Why |", "|---|---|---|---|"]
    for tag in sorted(set(tot) | ({sh.UNO_TAG} if uno else set())):
        e = cfg.population[tag]
        L.append(f"| {tag} | {e['wealth']} | {e['literacy']} | {e['why']} |")
    L.append("\n## Skipped and dropped\n")
    L.append("**Skipped owners (no country definition):** " + (", ".join(f"{k}/{t}" for k, t in p.skipped_owners) or "none"))
    sk = [(u, s, r) for u in p.units for s, r in u.skipped]
    L.append("\n**Skipped pops:**\n")
    L += [f"- {u.key}/{u.tag}: {s.culture} {s.size:,} ({r})" for u, s, r in sk] or ["- none"]
    dr = [(u, d) for u in p.units for d in u.dropped]
    L.append(f"\n**Dropped (< {cfg.min_pop}):**\n")
    L += [f"- {u.key}/{u.tag}: {d.culture} {d.size}" for u, d in dr] or ["- none"]
    L += ["", "**Warnings:**", ""] + ([f"- {w}" for w in p.warnings] or ["- none"])
    return "\n".join(L) + "\n"


def refresh_weights(root: Path, config_dir: Path) -> int:
    by_file = sh.load_states_by_file(root / "map_data" / "state_regions")
    doc = ph.refresh_weights(root / "map_data" / "provinces.png",
                             root / "mapgen" / "derived" / "arable_heatmap.png", by_file,
                             root / "mapgen" / "config" / "hub_worksheet.json",
                             root / "mapgen" / "config" / "canon_cities.json")
    (config_dir / "state_weights.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(doc['states'])} state weights")
    return 0


def update_fixture(fixture: Path) -> int:
    _, _, _, pops, population = build(fixture / "game", fixture / "config")
    for label, texts in (("pops", pops), ("population", population)):
        (fixture / "expected" / label).mkdir(parents=True, exist_ok=True)
        for name, text in texts.items():
            (fixture / "expected" / label / name).write_bytes(BOM + text.encode("utf-8"))
    print("fixture expected/ rewritten")
    return 0


def run_fixture_check(fixture: Path) -> None:
    """Regression-check the generator on ``mapgen/fixtures/pop_history/`` (see its
    README): golden output, determinism, exact sums and the hard errors."""
    import copy
    import shutil
    import tempfile

    cfg, world, p, pops, population = build(fixture / "game", fixture / "config")
    exp = fixture / "expected"
    for label, texts in (("pops", pops), ("population", population)):
        for name, text in texts.items():
            golden = sh.normalize_text((exp / label / name).read_text(encoding="utf-8"))
            assert golden == text, f"pop_history fixture: {label}/{name} differs from expected/ (run --update-fixture)"
    assert not ph.invariants(p, cfg) and not ph.check_texts(pops, population, world)
    again = build(fixture / "game", fixture / "config")
    assert again[3] == pops and again[4] == population, "pop_history output must be deterministic"
    by = {(u.key, u.tag): u for u in p.units}
    # split state: one region_state per owner
    assert {t for k, t in by if k == "STATE_GAMMA"} == {"MID", "REI"}
    # skipped owner (no definition), skipped culture, religion override, exact-sum rounding
    assert p.skipped_owners == [("STATE_EPSILON", "XXX")], p.skipped_owners
    assert any(s.culture == "high_elf" for u in p.units for s, _ in u.skipped)
    assert any(x.religion == "cult_of_sigmar" for u in p.units for x in u.pops)
    odd = by[("STATE_ALPHA", "REI")]
    assert odd.allot % 3 and sum(x.size for x in odd.pops) + sum(x.size for x, _ in odd.skipped) \
        + sum(x.size for x in odd.dropped) == odd.allot, "rounding must keep the exact sum"
    assert ph.largest_remainder(10, [Fraction(1), Fraction(1), Fraction(1)]) == [4, 3, 3]
    assert any(u.dropped for u in p.units), "the fixture must drop a sub-minimum pop"
    # unclaimed land: one fixed goblin pop (default faith implied), outside the calibrated totals,
    # plus a POPULATION entry; a created pair left without pops is caught by check_texts
    uno = by[("STATE_BETA", sh.UNO_TAG)]
    assert [(x.culture, x.size, x.religion, x.pop_type) for x in uno.pops] == \
        [(cfg.unclaimed["culture"], cfg.unclaimed["size"], None, None)], uno.pops
    assert sh.UNO_TAG not in cfg.totals and "region_state:UNO" in pops["01_isle.txt"]
    assert any(t == sh.UNO_TAG for es in p.population.values() for t, _ in es)
    stripped = {f: ph.render_pops([u for u in us if u.tag != sh.UNO_TAG]) for f, us in p.files.items()}
    assert any("region_state:UNO is created" in e for e in ph.check_texts(stripped, population, world))

    def planned(mutate) -> ph.Plan:
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(fixture / "config", tmp / "config")
            mutate(tmp / "config")
            return ph.plan(ph.load_config(tmp / "config"), world)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def refuses(mutate, needle: str) -> None:
        try:
            planned(mutate)
        except ph.PopHistoryError as exc:
            assert needle in str(exc), f"expected {needle!r} in {exc}"
        else:
            raise AssertionError(f"expected a PopHistoryError containing {needle!r}")

    def edit(name, fn):
        def go(d: Path) -> None:
            doc = json.loads((d / name).read_text(encoding="utf-8"))
            fn(doc)
            (d / name).write_text(json.dumps(doc), encoding="utf-8")
        return go

    refuses(edit("state_overrides.json", lambda d: d["states"][0]["mix"][0].__setitem__("share", 7)), "not 100%")
    refuses(edit("state_overrides.json", lambda d: d["states"][0].__setitem__("key", "STATE_NOWHERE")), "not a state")
    refuses(edit("state_overrides.json", lambda d: d["states"][0].__setitem__("anchor", [1, 1])), "anchor")
    refuses(edit("calibration.json", lambda d: d["tags"].pop("MID")), "no calibration.json entry")
    refuses(edit("population.json", lambda d: d["tags"].pop("MID")), "no population.json entry")
    refuses(edit("calibration.json", lambda d: d.pop("unclaimed_pop")), "no 'unclaimed_pop'")
    refuses(edit("calibration.json", lambda d: d["unclaimed_pop"].__setitem__("culture", "nowhere")),
            "unclaimed_pop: culture")
    refuses(edit("calibration.json", lambda d: d["unclaimed_pop"].__setitem__("size", 5)), "min_pop_size")
    refuses(edit("population.json", lambda d: d["tags"].pop("UNO")), "no population.json entry")

    # religion splits (#8492): REI and MID move 25% of their default-faith middenlanders to Sigmar
    def pops_of(u: ph.Unit) -> list[tuple]:
        return [(x.culture, x.religion, x.pop_type, x.size) for x in u.pops]

    # homeland path: REI's 11,112 middenlanders in GAMMA split 8,334 / 2,778; the reiklanders do not move
    assert pops_of(by[("STATE_GAMMA", "REI")]) == [
        ("reiklander", None, None, 22223), ("middenlander", None, None, 8334),
        ("middenlander", "cult_of_sigmar", None, 2778)], pops_of(by[("STATE_GAMMA", "REI")])
    # add-row path, explicit default-faith entry and merge: ZETA/MID base middenlander 968 -> 726/242, the
    # explicit cult_of_ulric (default) entry 75 -> 56/19, both Sigmar parts merge with the explicit 450
    assert pops_of(by[("STATE_ZETA", "MID")]) == [
        ("middenlander", None, None, 782), ("middenlander", "cult_of_sigmar", None, 711)], \
        pops_of(by[("STATE_ZETA", "MID")])
    assert p.split_moved == {("REI", "middenlander", "cult_of_sigmar"): 2778,
                             ("MID", "middenlander", "cult_of_sigmar"): 2251 + 242 + 19}, p.split_moved
    assert not any("religion_splits" in w for w in p.warnings), p.warnings
    # without the rule: every other pop identical, each unit's middenlander total equal
    plain = planned(edit("state_overrides.json", lambda d: d.pop("religion_splits")))
    assert not plain.split_moved
    plain_by = {(u.key, u.tag): u for u in plain.units}
    assert set(plain_by) == set(by)
    for k, u in by.items():
        v = plain_by[k]
        assert [x for x in pops_of(u) if x[0] != "middenlander"] == \
            [x for x in pops_of(v) if x[0] != "middenlander"], k
        assert sum(x.size for x in u.pops if x.culture == "middenlander") == \
            sum(x.size for x in v.pops if x.culture == "middenlander"), k
        assert (u.allot, u.skipped, u.dropped) == (v.allot, v.skipped, v.dropped), k
    # share 100 is allowed: the whole culture moves, no empty default pop is emitted
    whole = planned(edit("state_overrides.json", lambda d: d["religion_splits"][1].__setitem__("share", 100)))
    whole_zeta = next(u for u in whole.units if (u.key, u.tag) == ("STATE_ZETA", "MID"))
    assert pops_of(whole_zeta) == [("middenlander", "cult_of_sigmar", None, 1493)], pops_of(whole_zeta)
    # warnings: MID has no halfling (rule unused); REI holds halflings with no rule of its own
    warned = planned(edit("state_overrides.json", lambda d: d["religion_splits"].append(
        {"tags": ["MID"], "culture": "halfling", "religion": "cult_of_sigmar", "share": 10,
         "source": "fixture", "why": "no halflings in MID"}))).warnings
    assert "religion_splits: c:MID has no halfling people to split; rule unused" in warned, warned
    assert any(w.startswith("religion_splits: c:REI has ") and "halfling people but no rule" in w
               for w in warned), warned

    def split_row(**kw):
        return lambda d: d["religion_splits"][0].update(kw)

    refuses(edit("state_overrides.json", split_row(share=0)), "above 0")
    refuses(edit("state_overrides.json", lambda d: d["religion_splits"].append(
        {**d["religion_splits"][0], "religion": "old_faith", "share": 80})), "over 100")
    refuses(edit("state_overrides.json", split_row(religion="cult_of_ulric")), "culture default")
    refuses(edit("state_overrides.json", lambda d: d["religion_splits"].append(dict(d["religion_splits"][0]))),
            "twice")
    refuses(edit("state_overrides.json", split_row(religion="nowhere")), "not defined")
    refuses(edit("state_overrides.json", split_row(culture="high_elf")), "not defined")
    refuses(edit("state_overrides.json", split_row(tags=["ZZZ"])), "country definition")
    # a stale emitted file is caught by check_texts
    bad = dict(pops)
    first = next(f for f, t in pops.items() if "POPS" in t)
    bad[first] = pops[first].replace("culture = reiklander", "culture = nowhere", 1)
    assert any("does not resolve" in e for e in ph.check_texts(bad, population, world))
    bad[first] = pops[first].replace("region_state:REI", "region_state:MID", 1)
    assert ph.check_texts(bad, population, world)
    unbalanced = {**pops, first: pops[first].rstrip("\n}\n") + "\n"}
    assert any("balance" in e for e in ph.check_texts(unbalanced, population, world))


from fractions import Fraction  # noqa: E402  (used by run_fixture_check)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if a generated file is stale or invalid")
    ap.add_argument("--refresh-weights", action="store_true", help="rebuild state_weights.json (numpy/Pillow)")
    ap.add_argument("--update-fixture", action="store_true", help="rewrite mapgen/fixtures/pop_history/expected/")
    ap.add_argument("--report-md", type=Path, help="write the review-sheet markdown to this path")
    args = ap.parse_args(argv)
    try:
        if args.update_fixture:
            return update_fixture(MOD_ROOT / "mapgen" / "fixtures" / "pop_history")
        if args.refresh_weights:
            return refresh_weights(MOD_ROOT, CONFIG_DIR)
        return run(MOD_ROOT, CONFIG_DIR, args.check, args.report_md)
    except ph.PopHistoryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
