#!/usr/bin/env python3
"""Pre-fill '#N' comments on the blank rows of mapgen/config/adjacency_worksheet.json.

N is the line's number on the review render, i.e. the 'number' column of
scratchpad/adjacencies_table.csv (run `generate_adjacencies.py --review` first). Do NOT use the
'untyped rows (numbers as in the review table)' list that `--sync` prints: that is the worksheet
row index and drifts from the render whenever a drawn line was skipped.

Only blank rows (no type) are touched; Chris's typed rows and comments are never changed.
Re-run --review after a --sync, because the numbering follows the current drawn lines.
"""
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SHEET = REPO / "mapgen" / "config" / "adjacency_worksheet.json"
TABLE = REPO / "scratchpad" / "adjacencies_table.csv"

tab = {}
for r in csv.DictReader(TABLE.open(encoding="utf-8")):
    k = frozenset({(int(r["start_x"]), int(r["start_y"])), (int(r["stop_x"]), int(r["stop_y"]))})
    tab[k] = int(r["number"])

raw = SHEET.read_bytes()
nl = "\r\n" if b"\r\n" in raw else "\n"
data = json.loads(raw.decode("utf-8"))
done, missed = [], 0
for row in data["adjacencies"]:
    if row.get("type"):
        continue
    n = tab.get(frozenset({tuple(row["a"]), tuple(row["b"])}))
    if n is None:
        missed += 1
        continue
    row["comment"] = f"#{n}"
    done.append(n)
text = json.dumps(data, indent=2, ensure_ascii=False).replace("\n", nl)
SHEET.write_bytes((text + (nl if raw.endswith(b"\n") else "")).encode("utf-8"))
print(f"numbered {len(done)} blank row(s), {missed} not on the current table: {sorted(done)}")
