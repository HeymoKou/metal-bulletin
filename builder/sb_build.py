"""Antimony (Sb) parquet builder.

Reads existing data/series/antimony/{year}.parquet (if any), merges with the
latest scraped snapshot from scraper.sb, writes back per-year + latest.parquet.

Schema (wide, one row per date — all values normalized to USD/MT):
  date | exw_china | fob_china | port_india | rotterdam | baltimore | _source

Idempotent: re-running with no new dates is a no-op write (file rewrites the
same content). New dates are inserted; existing dates have their region values
upserted only when the scraper provides a non-null value for that region.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scraper.sb import REGIONS, SbPrice, fetch

logger = logging.getLogger(__name__)

METAL_KEY = "antimony"
SOURCE = "scrapmonster"
LATEST_WINDOW = 90

REGION_KEYS = list(REGIONS.values())  # exw_china, fob_china, port_india, rotterdam, baltimore

SCHEMA = pa.schema([
    pa.field("date", pa.string()),
    *(pa.field(r, pa.float64()) for r in REGION_KEYS),
    pa.field("_source", pa.string()),
])


def rows_from_scrape(prices: list[SbPrice]) -> dict[str, dict]:
    """Group scraped points by date → wide row dict."""
    by_date: dict[str, dict] = {}
    for p in prices:
        row = by_date.setdefault(p.date, {"date": p.date, "_source": SOURCE})
        # If multiple values for same (date, region) — last one wins (shouldn't happen in practice)
        row[p.region] = p.usd_per_mt
    # Fill missing regions with None
    for row in by_date.values():
        for r in REGION_KEYS:
            row.setdefault(r, None)
    return by_date


def load_existing(metal_dir: Path) -> dict[str, dict]:
    """Load all existing yearly parquets into {date: row} dict."""
    out: dict[str, dict] = {}
    if not metal_dir.exists():
        return out
    for f in sorted(metal_dir.glob("*.parquet")):
        if f.stem == "latest":
            continue
        try:
            table = pq.read_table(f)
            for row in table.to_pylist():
                out[row["date"]] = row
        except Exception as e:
            logger.warning("failed to read %s: %s", f, e)
    return out


def merge(existing: dict[str, dict], scraped: dict[str, dict]) -> tuple[dict[str, dict], list[str]]:
    """Upsert scraped rows into existing. Returns (merged, new_dates)."""
    new_dates: list[str] = []
    for date, srow in scraped.items():
        if date not in existing:
            existing[date] = srow
            new_dates.append(date)
            continue
        # Merge region values (only update non-null new values)
        erow = existing[date]
        for r in REGION_KEYS:
            v = srow.get(r)
            if v is not None:
                erow[r] = v
        erow["_source"] = srow.get("_source", erow.get("_source"))
    return existing, new_dates


def rows_to_table(rows: list[dict]) -> pa.Table:
    cols = {f.name: [r.get(f.name) for r in rows] for f in SCHEMA}
    arrays = [pa.array(cols[f.name], type=f.type) for f in SCHEMA]
    return pa.Table.from_arrays(arrays, schema=SCHEMA)


def write_parquet(table: pa.Table, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table, path,
        compression="zstd", compression_level=9,
        use_dictionary=True, write_statistics=True,
    )


def write_series(rows_by_date: dict[str, dict], metal_dir: Path) -> list[int]:
    rows = sorted(rows_by_date.values(), key=lambda r: r["date"], reverse=True)

    write_parquet(rows_to_table(rows[:LATEST_WINDOW]), metal_dir / "latest.parquet")

    by_year: dict[int, list[dict]] = {}
    for r in rows:
        by_year.setdefault(int(r["date"][:4]), []).append(r)

    for y, yrows in by_year.items():
        write_parquet(rows_to_table(yrows), metal_dir / f"{y}.parquet")

    return sorted(by_year.keys(), reverse=True)


def run(data_dir: Path) -> dict:
    """Fetch + merge + write. Returns summary dict."""
    metal_dir = data_dir / "series" / METAL_KEY

    prices = fetch()
    if not prices:
        logger.warning("no Sb data scraped; skipping build")
        return {"new_dates": [], "total": 0, "years": []}

    scraped = rows_from_scrape(prices)
    existing = load_existing(metal_dir)
    merged, new_dates = merge(existing, scraped)
    years = write_series(merged, metal_dir)

    summary = {
        "new_dates": sorted(new_dates),
        "total": len(merged),
        "years": years,
        "latest_date": max(merged) if merged else None,
    }
    print(
        f"antimony: {len(merged)} rows, "
        f"{len(new_dates)} new ({summary['latest_date']}), "
        f"years {years[-1] if years else '-'}~{years[0] if years else '-'}"
    )
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    args = ap.parse_args()
    run(args.data_dir)
