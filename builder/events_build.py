"""Events parquet builder.

Append + dedupe by (date, type, metal). Yearly partitioned files.

Used by news.yml to fetch LME stock snapshots → data/events/{year}.parquet.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from parser.news.models import EventItem
from scraper.lme.stocks import fetch_lme_stocks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

EVENTS_SCHEMA = pa.schema([
    pa.field("date", pa.date32()),
    pa.field("type", pa.string()),
    pa.field("metal", pa.string()),
    pa.field("magnitude", pa.float32()),
    pa.field("title", pa.string()),
    pa.field("url", pa.string()),
    pa.field("source", pa.string()),
])


def _to_table(items: list[EventItem]) -> pa.Table:
    rows = {f.name: [] for f in EVENTS_SCHEMA}
    for it in items:
        d = it.date if hasattr(it.date, "year") else datetime.fromisoformat(str(it.date)).date()
        rows["date"].append(d)
        rows["type"].append(it.type)
        rows["metal"].append(it.metal)
        rows["magnitude"].append(it.magnitude)
        rows["title"].append(it.title)
        rows["url"].append(it.url)
        rows["source"].append(it.source)
    return pa.Table.from_pydict(rows, schema=EVENTS_SCHEMA)


def build_events_parquet(items: list[EventItem], out_dir: Path, year: int) -> None:
    """Append events, dedupe by (date, type, metal). Last write wins on dup."""
    if not items:
        logger.info("events_build: empty input, no-op")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{year}.parquet"
    new_table = _to_table(items)

    if out_file.exists():
        existing = pq.read_table(out_file)
        combined = pa.concat_tables([existing, new_table], promote_options="default")
        df = combined.to_pandas()
        # last-wins (newer fetch overwrites same-day metal stock)
        df = df.drop_duplicates(subset=["date", "type", "metal"], keep="last")
        combined = pa.Table.from_pandas(df, schema=EVENTS_SCHEMA, preserve_index=False)
    else:
        combined = new_table

    pq.write_table(combined, out_file, compression="zstd")
    logger.info("events_build: wrote %d rows to %s", combined.num_rows, out_file)


def main() -> None:
    events = fetch_lme_stocks()
    if not events:
        logger.warning("no events fetched")
        return
    # Group by record date year (handles year-boundary + backfill).
    by_year: dict[int, list[EventItem]] = {}
    for e in events:
        d = e.date if hasattr(e.date, "year") else datetime.fromisoformat(str(e.date)).date()
        by_year.setdefault(d.year, []).append(e)
    for year, year_events in by_year.items():
        build_events_parquet(year_events, Path("data/events"), year)


if __name__ == "__main__":
    main()
