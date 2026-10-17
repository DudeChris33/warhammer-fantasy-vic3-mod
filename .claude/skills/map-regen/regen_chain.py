#!/usr/bin/env python3
"""Run the map regeneration chain in order, stop on the first failure.

Usage (repo root):
    python .claude/skills/map-regen/regen_chain.py                      # provinces -> locators/heatmap
    python .claude/skills/map-regen/regen_chain.py --from land_regions  # resume after a fix
    python .claude/skills/map-regen/regen_chain.py --from rivers        # coast/river/sea sources changed too
    python .claude/skills/map-regen/regen_chain.py --list
    python .claude/skills/map-regen/regen_chain.py --gate               # offline gate only
    python .claude/skills/map-regen/regen_chain.py --skip-mixed-state-merges   # only on Chris's say-so, per run

Never refreshes the source manifest (that follows a user source change, run `sources.py
--update-manifest` yourself). The only automatic repair is re-anchoring an override
whose naming anchor drifted a few px after a re-cut (pop_history / building_history).
Full per-step logs go to scratchpad/regen/<step>.log.
"""
from __future__ import annotations

import argparse
import glob
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MAPGEN = REPO / "mapgen"
LOGS = REPO / "scratchpad" / "regen"
SKIP_WRAPPER = Path(__file__).resolve().parent / "skip_mixed_state_merges.py"
MAX_ANCHOR_SHIFT = 40  # px; a bigger move is a different state, not drift

STEPS = [
    ("rivers", "generate_rivers.py"),
    ("state_labels", "generate_state_labels.py"),
    ("sea_zones", "generate_sea_zones.py"),
    ("provinces", "generate_provinces.py"),
    ("sea_regions", "generate_sea_regions.py"),
    ("land_regions", "generate_land_regions.py"),
    ("ownership", "read_state_ownership.py"),
    ("state_history", "generate_state_history.py"),
    ("country_history", "generate_country_history.py"),
    ("pop_weights", "generate_pop_history.py --refresh-weights"),
    ("pop_history", "generate_pop_history.py"),
    ("building_history", "generate_building_history.py"),
    ("terrains", "generate_province_terrains.py"),
    ("adj_sync", "generate_adjacencies.py --sync"),
    ("adj_write", "generate_adjacencies.py --write"),
    ("locators", "generate_map_locators.py"),
    ("heatmap", "generate_arable_heatmap.py"),
]
DEFAULT_FROM = "provinces"

GATE = [
    "read_state_ownership.py --check",
    "generate_state_history.py --check",
    "generate_pop_history.py --check",
    "generate_country_history.py --check",
    "generate_map_locators.py --check",
    "generate_building_history.py --check",
    "validate_building_history.py",
    "worldgen/sources.py --verify",
    "validate_map.py --province-bitmap",
    "validate_map.py --sea",
    "run_fixture.py --check",
    "validate_map.py",
    "generate_flatmap_textures.py --check",
    "generate_adjacencies.py --check",
]

ANCHOR_RE = re.compile(
    r"(STATE_\w+) anchor \[(\d+), (\d+)\] no longer matches the state.s naming anchor \[(\d+), (\d+)\]")


def python() -> str:
    for p in (MAPGEN / ".venv" / "Scripts" / "python.exe", MAPGEN / ".venv" / "bin" / "python"):
        if p.is_file():
            return str(p)
    return sys.executable


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    log.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    log.write_text(out, encoding="utf-8")
    return p.returncode, out


def tail(out: str, n: int = 6) -> str:
    lines = [l for l in out.splitlines() if l.strip() and "WARNING" not in l and not l.startswith("warning")]
    return "\n".join(l[:230] for l in lines[-n:])


def reanchor(err_line: str) -> bool:
    """Patch one drifted override anchor in pop_history / building_history; False if not safe."""
    m = ANCHOR_RE.search(err_line)
    if not m:
        return False
    key, x, y, nx, ny = m.groups()
    if abs(int(x) - int(nx)) > MAX_ANCHOR_SHIFT or abs(int(y) - int(ny)) > MAX_ANCHOR_SHIFT:
        print(f"  anchor of {key} moved more than {MAX_ANCHOR_SHIFT}px ({x},{y}) -> ({nx},{ny}); not auto-fixing")
        return False
    pat = re.compile(rf"(\[\s*){x}(\s*,\s*){y}(\s*\])")
    for p in glob.glob(str(MAPGEN / "config" / "pop_history" / "*.json")) + \
            glob.glob(str(MAPGEN / "config" / "building_history" / "*.json")):
        s = Path(p).read_text(encoding="utf-8")
        i = s.find(f'"{key}"')
        while i != -1:
            seg = s[i:i + 400]
            new, n = pat.subn(lambda mm: f"{mm.group(1)}{nx}{mm.group(2)}{ny}{mm.group(3)}", seg, count=1)
            if n:
                Path(p).write_bytes((s[:i] + new + s[i + 400:]).encode("utf-8"))
                print(f"  re-anchored {key}: ({x},{y}) -> ({nx},{ny}) in {Path(p).name}")
                return True
            i = s.find(f'"{key}"', i + 1)
    return False


def run_step(name: str, spec: str, skip_mixed: bool) -> bool:
    py = python()
    if name == "provinces" and skip_mixed:
        cmd = [py, str(SKIP_WRAPPER)]
    else:
        parts = spec.split()
        cmd = [py, str(MAPGEN / parts[0]), *parts[1:]]
    for _ in range(80):
        rc, out = run(cmd, LOGS / f"{name}.log")
        err = next((l for l in out.splitlines() if l.startswith("ERROR") and "anchor" in l), "")
        if rc != 0 and err and name in ("pop_history", "building_history") and reanchor(err):
            continue
        print(f"== {name}: {'ok' if rc == 0 else 'FAILED'}\n{tail(out)}")
        return rc == 0
    return False


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles are cp1252
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", default=DEFAULT_FROM, choices=[n for n, _ in STEPS])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--gate", action="store_true", help="run only the offline gate")
    ap.add_argument("--skip-mixed-state-merges", action="store_true",
                    help="drop state_merges lines that join in-scope to out-of-scope land (per run, Chris's say-so)")
    a = ap.parse_args()
    if a.list:
        for n, s in STEPS:
            print(f"{n:18} {s}")
        print("\ngate:\n  " + "\n  ".join(GATE))
        return 0
    py = python()
    if not a.gate:
        rc, out = run([py, str(MAPGEN / "worldgen" / "sources.py"), "--verify"], LOGS / "verify.log")
        if rc != 0:
            print("source manifest does not verify; stop and ask Chris (moved sources, or run --update-manifest after a re-export):")
            print(tail(out, 12))
            return 1
        names = [n for n, _ in STEPS]
        for n, s in STEPS[names.index(a.start):]:
            if not run_step(n, s, a.skip_mixed_state_merges):
                print(f"\nstopped at '{n}'; fix it, then resume with --from {n}  (log: scratchpad/regen/{n}.log)")
                return 1
    print("\n######## offline gate")
    bad = 0
    for g in GATE:
        parts = g.split()
        rc, out = run([py, str(MAPGEN / parts[0]), *parts[1:]], LOGS / ("gate_" + g.replace(" ", "_").replace("/", "_") + ".log"))
        print(f"== {g}: {'ok' if rc == 0 else 'FAILED'}")
        if rc != 0:
            print(tail(out, 8))
            bad += 1
    print(f"\ngate: {len(GATE) - bad}/{len(GATE)} passed. The rendered map is still the real gate (see SKILL.md).")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
