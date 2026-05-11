"""One-shot migration: rename misleading 'monthly_avg' → 'lme_settle' across all data.

History:
- Original parser stored PDF col[6-7] under settlement.monthly_avg. col[6-7] is
  actually LME 정산가 (London 17:00) — NOT MTD average. Label was misleading.
- True MTD average (PDF col[3]) was never captured. FE now reads MTD from
  manifest.metals.{metal}.current_month_avg computed in builder from daily series.
- This migration renames the existing field/column to its correct semantic name
  so historical data is no longer mislabeled. Values are preserved.

Files migrated:
  - data/daily/*.json:   settlement.monthly_avg → settlement.lme_settle
  - data/raw/*.parquet:  same key rename inside the JSON column
  - data/series/{metal}/*.parquet:  column rename sett_mavg_{cash,3m} → sett_lme_settle_{cash,3m}
"""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DAILY_DIR = Path("data/daily")
RAW_DIR = Path("data/raw")
SERIES_DIR = Path("data/series")

OLD_KEY = "monthly_avg"
NEW_KEY = "lme_settle"
RENAME_COLS = {
    "sett_mavg_cash": "sett_lme_settle_cash",
    "sett_mavg_3m": "sett_lme_settle_3m",
}


def _rename_in_settlement(d: dict) -> bool:
    changed = False
    for _metal, mdata in d.get("metals", {}).items():
        sett = mdata.get("settlement")
        if isinstance(sett, dict) and OLD_KEY in sett:
            sett[NEW_KEY] = sett.pop(OLD_KEY)
            changed = True
    return changed


def migrate_daily() -> None:
    if not DAILY_DIR.exists():
        return
    files = sorted(DAILY_DIR.glob("*.json"))
    changed_count = 0
    for path in files:
        d = json.loads(path.read_text())
        if _rename_in_settlement(d):
            path.write_text(json.dumps(d, ensure_ascii=False))
            changed_count += 1
    print(f"daily/: {changed_count}/{len(files)} files renamed")


def migrate_raw() -> None:
    if not RAW_DIR.exists():
        return
    for path in sorted(RAW_DIR.glob("*.parquet")):
        t = pq.read_table(path).to_pandas()
        renamed = 0
        new_json: list[str] = []
        for s in t["json"]:
            d = json.loads(s)
            if _rename_in_settlement(d):
                renamed += 1
            new_json.append(json.dumps(d, ensure_ascii=False))
        t["json"] = new_json
        out = pa.Table.from_pandas(t, preserve_index=False)
        pq.write_table(out, path, compression="zstd")
        print(f"{path.name}: {renamed}/{len(t)} entries renamed")


def migrate_series() -> None:
    if not SERIES_DIR.exists():
        return
    for metal_dir in sorted(SERIES_DIR.iterdir()):
        if not metal_dir.is_dir():
            continue
        for path in sorted(metal_dir.glob("*.parquet")):
            t = pq.read_table(path)
            cols = list(t.column_names)
            need = [c for c in RENAME_COLS if c in cols]
            if not need:
                continue
            new_names = [RENAME_COLS.get(c, c) for c in cols]
            t = t.rename_columns(new_names)
            pq.write_table(t, path, compression="zstd")
            print(f"{metal_dir.name}/{path.name}: renamed {need}")


def main() -> None:
    migrate_daily()
    migrate_raw()
    migrate_series()


if __name__ == "__main__":
    main()
