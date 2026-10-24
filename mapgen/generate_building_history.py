#!/usr/bin/env python3
"""Write starting buildings into ``common/history/buildings/NN_*.txt``.

Reads the hand-authored ``mapgen/config/building_history/*.json`` (see its README), the
state resources in ``map_data/state_regions``, the emitted ``common/history/{states,pops,
countries}``, and the building / production-method / law / technology definitions in
``common/``; writes one file per land ``map_data/state_regions/NN_*.txt`` (the existing stub
names). The **tech gate** (nothing is emitted that the owner has not researched, failing
closed) and every other rule are documented in ``worldgen/building_history.py``;
``validate_building_history.py`` re-checks the emitted files with separate code and is run by
``--check``. Output is UTF-8 with a BOM and LF endings, like the sibling generated files. A
generated file set: never hand-edit it. Run it after ``generate_country_history.py``, and
again after any change to country history.

Usage::

    python mapgen/generate_building_history.py                   # write the files
    python mapgen/generate_building_history.py --check           # exit 1 if stale, invalid or a gate violation
    python mapgen/generate_building_history.py --report-md PATH  # also write the review-sheet tables
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_building_history as vbh  # noqa: E402
from worldgen import building_history as bh  # noqa: E402
from worldgen import state_history as sh  # noqa: E402

MOD_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = MOD_ROOT / "mapgen" / "config" / "building_history"
BOM = b"\xef\xbb\xbf"


def build(root: Path, config_dir: Path):
    cfg = bh.load_config(config_dir)
    world = bh.load_world(root)
    p = bh.plan(cfg, world)
    return cfg, world, p, bh.render_all(p)


def _read(path: Path) -> str | None:
    return sh.normalize_text(path.read_text(encoding="utf-8")) if path.exists() else None


def run(root: Path, config_dir: Path, check: bool, report_md: Path | None = None) -> int:
    cfg, world, p, texts = build(root, config_dir)
    errors = bh.invariants(p, cfg, world) + bh.check_texts(texts, world)
    errors += vbh.verify_texts(texts, root)          # the independent gate, on what would be written
    errors += [f"c:{t}: owns a building but its country history does not resolve (techs and laws unknown)"
               for t in sorted({u.tag for u in p.units}) if not (world.tags.get(t) and world.tags[t].resolved)]
    print(bh.summary(p, world))
    for w in p.warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    if report_md is not None:
        report_md.write_text(bh.markdown_report(cfg, world, p), encoding="utf-8")
    out = root / "common" / "history" / "buildings"
    if check:
        for name, text in sorted(texts.items()):
            if _read(out / name) != text:
                errors.append(f"common/history/buildings/{name} is stale -- run generate_building_history.py")
        errors += vbh.verify(root)                   # the committed files, not just the regenerated ones
    else:
        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            return 1
        out.mkdir(parents=True, exist_ok=True)
        for name, text in sorted(texts.items()):
            (out / name).write_bytes(BOM + text.encode("utf-8"))
        print(f"wrote {len(texts)} files")
    for e in sorted(set(errors)):
        print(f"ERROR: {e}", file=sys.stderr)
    return 1 if errors else 0


def update_fixture(fixture: Path) -> int:
    _, _, _, texts = build(fixture / "game", fixture / "config")
    (fixture / "expected").mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        (fixture / "expected" / name).write_bytes(BOM + text.encode("utf-8"))
    print("fixture expected/ rewritten")
    return 0


def run_fixture_check(fixture: Path) -> None:
    """Regression-check the generator and the verifier on ``mapgen/fixtures/building_history/``
    (see its README): golden output, determinism, the tech gate and its hard errors."""
    game, cfgdir = fixture / "game", fixture / "config"
    cfg, world, p, texts = build(game, cfgdir)
    for name, text in texts.items():
        golden = sh.normalize_text((fixture / "expected" / name).read_text(encoding="utf-8"))
        assert golden == text, f"building_history fixture: {name} differs from expected/ (run --update-fixture)"
    assert not bh.invariants(p, cfg, world) and not bh.check_texts(texts, world)
    assert not vbh.verify_texts(texts, game), vbh.verify_texts(texts, game)
    assert build(game, cfgdir)[3] == texts, "building_history output must be deterministic"
    allp = [(u.tag, u.key, x) for u in p.units for x in u.placed]
    by = {(u.key, u.tag): u for u in p.units}
    ids = {(t, x.building) for t, _, x in allp}
    # tech-free tags and tier gates
    assert ("AAA", "building_government_administration") in ids, "AAA (tier-5 setup) must get its admin building"
    assert ("BBB", "building_government_administration") not in ids, "BBB lacks tech_bureaucracy"
    assert not any(b == "building_railway" for _, b in ids), "no fixture tag has railways"
    # a tech-locked method is never chosen (the default method of the farm group needs a tech BBB lacks)
    for t, _, x in allp:
        for m in x.pms:
            need = set(world.pms[m].techs) - set(world.tags[t].techs)
            assert not need, f"{t}: {m} chosen without {need}"
    assert any("pm_basic_farming" in x.pms for t, _, x in allp if t == "BBB")
    assert any("pm_advanced_farming" in x.pms for t, _, x in allp if t == "AAA"), "a tag with the tech takes the default method"
    # an unresolvable tech set gets tech-free buildings only
    assert not world.tags["CCC"].resolved and not world.tags["CCC"].techs
    ccc = {x.building for t, _, x in allp if t == "CCC"}
    assert ccc and all(not world.buildings[b].techs for b in ccc), f"CCC got tech-gated buildings: {ccc}"
    assert "building_wheat_farm" not in ccc
    # split state: one block per owner
    assert {t for k, t in by if k == "STATE_GAMMA"} == {"AAA", "BBB"}
    # industry (#6637): in the owner's most populous state when it has the tech; a tag without it reports the drop
    mill = [(u.key, u.tag, x.levels) for u in p.units for x in u.placed if x.building == "building_fix_mill"]
    assert mill == [("STATE_DELTA", "AAA", 1)], mill
    assert any(b == "building_fix_mill" and "tech gate" in why for u in p.units if u.tag == "BBB" for b, why in u.dropped),         "BBB lacks manufacturies: the industry is dropped and the drop is reported"
    # small-state minimum (#6637): just above the floor one farm level fits the 40 % job cap, below it the unit stays empty
    eps, zeta = by[("STATE_EPSILON", "AAA")], by[("STATE_ZETA", "AAA")]
    assert [(x.building, x.levels, x.why) for x in eps.placed] == [("building_wheat_farm", 1, "small-state minimum")], eps.placed
    assert not zeta.placed and any(b == "small-state minimum" for b, _ in zeta.dropped), (zeta.placed, zeta.dropped)

    def refuses(mutate, needle: str, *needles: str) -> None:
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(cfgdir, tmp / "config")
            mutate(tmp / "config")
            bh.plan(bh.load_config(tmp / "config"), world)
        except bh.BuildingHistoryError as exc:
            for n in (needle,) + needles:
                assert n in str(exc), f"expected {n!r} in {exc}"
        else:
            raise AssertionError(f"expected a BuildingHistoryError containing {needle!r}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def edit(name, fn):
        def go(d: Path) -> None:
            doc = json.loads((d / name).read_text(encoding="utf-8"))
            fn(doc)
            (d / name).write_text(json.dumps(doc), encoding="utf-8")
        return go

    ov = lambda d: d["states"].append({"key": "STATE_ALPHA", "anchor": [10, 10], "owner": "BBB",   # noqa: E731
                                       "buildings": {"building_railway": 1}, "source": "inferred", "why": "test"})
    refuses(edit("state_overrides.json", ov), "railways", "BBB", "STATE_ALPHA", "building_railway")
    ov2 = lambda d: d["states"].append({"key": "STATE_BETA", "anchor": [20, 20], "owner": "CCC",   # noqa: E731
                                        "buildings": {"building_wheat_farm": 1}, "source": "inferred", "why": "test"})
    refuses(edit("state_overrides.json", ov2), "enclosure", "CCC", "STATE_BETA")
    refuses(edit("state_overrides.json", lambda d: d["states"][0].__setitem__("key", "STATE_NOWHERE")), "not a state")
    refuses(edit("state_overrides.json", lambda d: d["states"][0].__setitem__("anchor", [1, 1])), "anchor")
    refuses(edit("state_overrides.json", lambda d: d["states"][0]["buildings"].__setitem__("building_nope", 1)), "unknown building")
    refuses(edit("profiles.json", lambda d: d["archetypes"]["basic"].__setitem__("industry", {"building_nope": 1})), "unknown building")
    refuses(edit("profiles.json", lambda d: d["archetypes"]["basic"].__setitem__("industry", {"building_wheat_farm": 1})),
            "is not in common/buildings/01_industry.txt")
    refuses(edit("profiles.json", lambda d: d["archetypes"]["basic"].__setitem__("industry", {"building_fix_mill": -1})), "industry must be")
    refuses(edit("profiles.json", lambda d: d["tags"].pop("BBB")), "no profiles.json entry")
    refuses(edit("profiles.json", lambda d: d["archetypes"]["basic"].__setitem__("workforce_share", 0.9)), "job_share_cap")
    # the verifier catches hand-broken output files
    first = next(f for f, t in texts.items() if "region_state:BBB" in t)
    base = texts[first]

    def broken(new: dict[str, str], needle: str) -> None:
        errs = vbh.verify_texts({**texts, **new}, game)
        assert any(needle in e for e in errs), f"verifier missed {needle!r}: {errs}"

    broken({first: base.replace('building = "building_wheat_farm"', 'building = "building_railway"', 1)}, "needs tech railways")
    broken({first: base.replace('"pm_basic_farming"', '"pm_advanced_farming"', 1)}, "needs tech intensive_agriculture")
    broken({first: base.replace("region_state:BBB", "region_state:UNO", 1)}, "c:UNO")
    broken({first: base.replace("region_state:BBB", "region_state:CCC", 1)}, "history/states does not create")
    broken({first: base.rstrip("\n}\n") + "\n"}, "balance")
    drop = base.replace('activate_production_methods = { "pm_basic_farming" }', "activate_production_methods = { }", 1)
    broken({first: drop}, "no method for group")
    # a later change to country history invalidates a previously valid building
    tmp = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(game, tmp / "game")
        f = tmp / "game" / "common" / "history" / "countries" / "00_start_setup.txt"
        f.write_text(f.read_text(encoding="utf-8").replace("effect_fixture_tier_5 = yes", "effect_fixture_tier_6 = yes"), encoding="utf-8")
        errs = vbh.verify_texts(texts, tmp / "game")
        assert any("tech_bureaucracy" in e and "AAA" in e for e in errs), errs
        f.write_text(f.read_text(encoding="utf-8").replace("c:AAA ?= {", "c:AAA ?= {\n\t\tmystery_effect = yes", 1), encoding="utf-8")
        errs = vbh.verify_texts(texts, tmp / "game")
        assert any("unresolved" in e for e in errs), errs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if a generated file is stale, invalid or breaks the tech gate")
    ap.add_argument("--update-fixture", action="store_true", help="rewrite mapgen/fixtures/building_history/expected/")
    ap.add_argument("--report-md", type=Path, help="write the review-sheet markdown to this path")
    args = ap.parse_args(argv)
    try:
        if args.update_fixture:
            return update_fixture(MOD_ROOT / "mapgen" / "fixtures" / "building_history")
        return run(MOD_ROOT, CONFIG_DIR, args.check, args.report_md)
    except bh.BuildingHistoryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
