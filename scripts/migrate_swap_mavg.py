"""One-shot migration: swap settlement.monthly_avg <-> prev_monthly_avg.

Operates on data/raw/*.parquet AND data/daily/*.json so that builder.build produces
correct series regardless of which source it loads from.

Fix for parser/page1.py column-index bug where MTD and prev-month averages were swapped.
"""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

RAW_DIR = Path("data/raw")
DAILY_DIR = Path("data/daily")


def swap_entry(d: dict) -> bool:
    changed = False
    for metal, mdata in d.get("metals", {}).items():
        sett = mdata.get("settlement")
        if not isinstance(sett, dict):
            continue
        mavg = sett.get("monthly_avg")
        pmavg = sett.get("prev_monthly_avg")
        if mavg is None and pmavg is None:
            continue
        sett["monthly_avg"] = pmavg
        sett["prev_monthly_avg"] = mavg
        changed = True
    return changed


def main() -> None:
    if DAILY_DIR.exists():
        swapped = 0
        total = 0
        for path in sorted(DAILY_DIR.glob("*.json")):
            total += 1
            d = json.loads(path.read_text())
            if swap_entry(d):
                swapped += 1
                path.write_text(json.dumps(d, ensure_ascii=False))
        print(f"daily/: {swapped}/{total} files swapped")

    for path in sorted(RAW_DIR.glob("*.parquet")):
        t = pq.read_table(path).to_pandas()
        new_json = []
        swapped = 0
        for s in t["json"]:
            d = json.loads(s)
            if swap_entry(d):
                swapped += 1
            new_json.append(json.dumps(d, ensure_ascii=False))
        t["json"] = new_json
        out = pa.Table.from_pandas(t, preserve_index=False)
        pq.write_table(out, path, compression="zstd")
        print(f"{path.name}: {swapped}/{len(t)} entries swapped")


if __name__ == "__main__":
    main()
