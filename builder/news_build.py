"""News parquet builder.

Append + dedupe by url_hash. Yearly partitioned files.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from parser.news.models import EnrichedNewsItem

logger = logging.getLogger(__name__)

NEWS_SCHEMA = pa.schema([
    pa.field("date", pa.date32()),
    pa.field("fetched_at", pa.timestamp("us", tz="UTC")),
    pa.field("source", pa.string()),
    pa.field("url", pa.string()),
    pa.field("url_hash", pa.string()),
    pa.field("title", pa.string()),
    pa.field("title_ko", pa.string()),
    pa.field("summary_ko", pa.string()),
    pa.field("metals", pa.list_(pa.string())),
    pa.field("sentiment", pa.int8()),
    pa.field("event_type", pa.string()),
    pa.field("confidence", pa.float32()),
    pa.field("lang", pa.string()),
])


def _to_table(items: list[EnrichedNewsItem]) -> pa.Table:
    rows = {f.name: [] for f in NEWS_SCHEMA}
    for it in items:
        rows["date"].append(it.fetched_at.date())
        rows["fetched_at"].append(it.fetched_at)
        rows["source"].append(it.source)
        rows["url"].append(it.url)
        rows["url_hash"].append(it.url_hash)
        rows["title"].append(it.title)
        rows["title_ko"].append(it.title_ko)
        rows["summary_ko"].append(it.summary_ko)
        rows["metals"].append(list(it.metals))
        rows["sentiment"].append(it.sentiment)
        rows["event_type"].append(it.event_type)
        rows["confidence"].append(it.confidence)
        rows["lang"].append(it.lang)
    return pa.Table.from_pydict(rows, schema=NEWS_SCHEMA)


def build_news_parquet(items: list[EnrichedNewsItem], out_dir: Path, year: int) -> None:
    """Append items to {out_dir}/{year}.parquet, dedupe by url_hash."""
    if not items:
        logger.info("news_build: empty input, no-op")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{year}.parquet"
    new_table = _to_table(items)

    if out_file.exists():
        existing = pq.read_table(out_file)
        # Normalize schema (pandas roundtrip elsewhere can upgrade string → large_string).
        try:
            existing = existing.cast(NEWS_SCHEMA)
        except (pa.ArrowInvalid, pa.ArrowTypeError) as e:
            logger.warning("existing schema cast failed err=%s; via pandas fallback", e)
            existing = pa.Table.from_pandas(
                existing.to_pandas(), schema=NEWS_SCHEMA, preserve_index=False
            )
        combined = pa.concat_tables([existing, new_table], promote_options="default")
        df = combined.to_pandas()
        # Repair stale null-enriched rows: prefer rows with summary_ko over null ones.
        # Sort: non-null summary first, then keep first per url_hash.
        df["_has_summary"] = df["summary_ko"].notna().astype(int)
        df = df.sort_values(["_has_summary", "fetched_at"], ascending=[False, False])
        df = df.drop_duplicates(subset=["url_hash"], keep="first")
        df = df.drop(columns=["_has_summary"])
        combined = pa.Table.from_pandas(df, schema=NEWS_SCHEMA, preserve_index=False)
    else:
        combined = new_table

    pq.write_table(combined, out_file, compression="zstd")
    logger.info("news_build: wrote %d rows to %s", combined.num_rows, out_file)


def main() -> None:
    enriched_path = Path("data/news_enriched.json")
    if not enriched_path.exists():
        logger.warning("no enriched file, skip")
        return

    raw = json.loads(enriched_path.read_text(encoding="utf-8"))
    items = [EnrichedNewsItem.model_validate(r) for r in raw]
    if not items:
        return

    # Group items by their fetched_at year — supports backfill across year boundaries.
    by_year: dict[int, list[EnrichedNewsItem]] = {}
    for it in items:
        by_year.setdefault(it.fetched_at.year, []).append(it)
    for year, year_items in by_year.items():
        build_news_parquet(year_items, Path("data/news"), year)


if __name__ == "__main__":
    main()
