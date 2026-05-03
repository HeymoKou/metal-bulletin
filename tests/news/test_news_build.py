"""News parquet builder tests."""
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from builder.news_build import NEWS_SCHEMA, build_news_parquet
from parser.news.models import EnrichedNewsItem


def _enriched(url: str = "https://e.com/1", summary: str | None = "ok") -> EnrichedNewsItem:
    return EnrichedNewsItem(
        source="s", url=url, title="t",
        fetched_at=datetime.now(timezone.utc), lang="en",
        summary_ko=summary, metals=["copper"], sentiment=1,
        event_type="supply", confidence=0.85,
    )


def test_build_writes_parquet(tmp_path: Path):
    items = [_enriched(url="https://e.com/1"), _enriched(url="https://e.com/2", summary=None)]
    out_dir = tmp_path / "news"
    build_news_parquet(items, out_dir, year=2026)

    out_file = out_dir / "2026.parquet"
    assert out_file.exists()
    table = pq.read_table(out_file)
    assert table.num_rows == 2
    expected_cols = {f.name for f in NEWS_SCHEMA}
    assert set(table.column_names) == expected_cols


def test_build_appends_to_existing(tmp_path: Path):
    out_dir = tmp_path / "news"
    build_news_parquet([_enriched(url="https://e.com/1")], out_dir, year=2026)
    build_news_parquet([_enriched(url="https://e.com/2")], out_dir, year=2026)

    table = pq.read_table(out_dir / "2026.parquet")
    assert table.num_rows == 2
    urls = set(table.column("url").to_pylist())
    assert urls == {"https://e.com/1", "https://e.com/2"}


def test_build_dedupes_on_append(tmp_path: Path):
    out_dir = tmp_path / "news"
    build_news_parquet([_enriched(url="https://e.com/1")], out_dir, year=2026)
    build_news_parquet([_enriched(url="https://e.com/1")], out_dir, year=2026)

    table = pq.read_table(out_dir / "2026.parquet")
    assert table.num_rows == 1


def test_build_empty_input_no_op(tmp_path: Path):
    out_dir = tmp_path / "news"
    build_news_parquet([], out_dir, year=2026)
    assert not (out_dir / "2026.parquet").exists()


def test_build_schema_columns():
    cols = {f.name for f in NEWS_SCHEMA}
    required = {
        "date", "fetched_at", "source", "url", "url_hash",
        "title", "title_ko", "summary_ko", "metals",
        "sentiment", "event_type", "confidence", "lang",
    }
    assert required.issubset(cols)
