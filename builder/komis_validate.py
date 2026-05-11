"""KOMIS cross-validation builder.

Compares our latest-day settlement Cash/3M (from data/series) against KOMIS LME
quotes, writes append-only validation records, and updates manifest with
summary.

Output:
  data/komis/validation.parquet  schema:
    date (str YYYY-MM-DD)
    metal (str)
    ours_cash (float)
    komis_cash (float)
    diff_cash (float)
    ours_3m (float)
    komis_3m (float)
    diff_3m (float)
    komis_invt (float)
    checked_at (timestamp UTC iso)

manifest.komis:
  {last_checked, last_date, max_abs_diff_cash, max_abs_diff_3m, mismatches: [...]}
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scraper.komis import KomisQuote, fetch

logger = logging.getLogger(__name__)

# Tolerance: prices are quoted to 2 decimals, so any abs diff > 0.5 = real divergence.
DIFF_THRESHOLD = 0.5


def _read_existing(path: Path) -> dict[tuple[str, str], None]:
    """Return set of (date, metal) already recorded — used to de-dupe."""
    if not path.exists():
        return {}
    try:
        t = pq.read_table(path)
        keys = {}
        for row in t.to_pylist():
            keys[(row["date"], row["metal"])] = None
        return keys
    except Exception as e:
        logger.warning("komis validation read failed err=%s", e)
        return {}


def _load_ours(data_dir: Path, metal: str, date: str) -> tuple[float | None, float | None]:
    """Return (sett_cash, sett_3m) for date from latest.parquet, or (None, None)."""
    path = data_dir / "series" / metal / "latest.parquet"
    if not path.exists():
        return (None, None)
    try:
        t = pq.read_table(path, columns=["date", "sett_cash", "sett_3m"]).to_pylist()
        for row in t:
            if row["date"] == date:
                return (row.get("sett_cash"), row.get("sett_3m"))
    except Exception as e:
        logger.warning("ours read failed metal=%s err=%s", metal, e)
    return (None, None)


def build_records(
    quotes: list[KomisQuote], data_dir: Path, now: datetime
) -> list[dict]:
    rows: list[dict] = []
    for q in quotes:
        if not q.date:
            continue
        ours_cash, ours_3m = _load_ours(data_dir, q.metal, q.date)
        diff_cash = (q.cash - ours_cash) if (q.cash is not None and ours_cash is not None) else None
        diff_3m = (q.m3 - ours_3m) if (q.m3 is not None and ours_3m is not None) else None
        rows.append({
            "date": q.date,
            "metal": q.metal,
            "ours_cash": ours_cash,
            "komis_cash": q.cash,
            "diff_cash": diff_cash,
            "ours_3m": ours_3m,
            "komis_3m": q.m3,
            "diff_3m": diff_3m,
            "komis_invt": q.invt,
            "checked_at": now.isoformat(),
        })
    return rows


def _write_parquet(rows: list[dict], path: Path) -> None:
    existing: list[dict] = []
    if path.exists():
        try:
            existing = pq.read_table(path).to_pylist()
        except Exception as e:
            logger.warning("komis validation existing read failed err=%s", e)

    # De-dupe by (date, metal) — keep newest record (i.e. the incoming one)
    seen: set[tuple[str, str]] = set((r["date"], r["metal"]) for r in rows)
    merged = [r for r in existing if (r["date"], r["metal"]) not in seen] + rows
    merged.sort(key=lambda r: (r["date"], r["metal"]))
    schema = pa.schema([
        ("date", pa.string()),
        ("metal", pa.string()),
        ("ours_cash", pa.float64()),
        ("komis_cash", pa.float64()),
        ("diff_cash", pa.float64()),
        ("ours_3m", pa.float64()),
        ("komis_3m", pa.float64()),
        ("diff_3m", pa.float64()),
        ("komis_invt", pa.float64()),
        ("checked_at", pa.string()),
    ])
    t = pa.Table.from_pylist(merged, schema=schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, path, compression="zstd")


def _summarize_for_manifest(rows: list[dict], now: datetime) -> dict:
    if not rows:
        return {"last_checked": now.isoformat(), "status": "no_data"}
    latest_date = max(r["date"] for r in rows)
    diffs_cash = [abs(r["diff_cash"]) for r in rows if r["diff_cash"] is not None]
    diffs_3m = [abs(r["diff_3m"]) for r in rows if r["diff_3m"] is not None]
    mismatches = [
        {"metal": r["metal"], "diff_cash": r["diff_cash"], "diff_3m": r["diff_3m"]}
        for r in rows
        if (r["diff_cash"] is not None and abs(r["diff_cash"]) > DIFF_THRESHOLD)
        or (r["diff_3m"] is not None and abs(r["diff_3m"]) > DIFF_THRESHOLD)
    ]
    return {
        "last_checked": now.isoformat(),
        "last_date": latest_date,
        "max_abs_diff_cash": round(max(diffs_cash), 4) if diffs_cash else None,
        "max_abs_diff_3m": round(max(diffs_3m), 4) if diffs_3m else None,
        "mismatches": mismatches,
        "status": "ok" if not mismatches else "mismatch",
    }


def run(data_dir: Path = Path("data")) -> None:
    now = datetime.now(timezone.utc)
    quotes = fetch()
    if not quotes:
        logger.warning("komis returned no quotes; skipping validation")
        return

    rows = build_records(quotes, data_dir, now)
    _write_parquet(rows, data_dir / "komis" / "validation.parquet")

    summary = _summarize_for_manifest(rows, now)
    manifest_path = data_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest["komis"] = summary
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    print(
        f"komis: {len(rows)} rows checked, status={summary['status']}, "
        f"max_diff_cash={summary.get('max_abs_diff_cash')}, "
        f"max_diff_3m={summary.get('max_abs_diff_3m')}"
    )
    if summary.get("mismatches"):
        for m in summary["mismatches"]:
            print(f"  MISMATCH {m['metal']}: Δcash={m['diff_cash']} Δ3m={m['diff_3m']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
