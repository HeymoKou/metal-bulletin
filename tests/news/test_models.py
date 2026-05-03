"""News pipeline data models."""
from datetime import datetime, timezone

import pytest

from parser.news.models import EnrichedNewsItem, EventItem, RawNewsItem


def test_raw_news_item_minimal():
    item = RawNewsItem(
        source="mining.com",
        url="https://example.com/a",
        title="Copper hits 5y high",
        fetched_at=datetime.now(timezone.utc),
        lang="en",
    )
    assert item.url_hash
    assert len(item.url_hash) == 16


def test_url_hash_deterministic():
    a = RawNewsItem(source="x", url="https://e.com/1", title="t", fetched_at=datetime.now(timezone.utc), lang="en")
    b = RawNewsItem(source="x", url="https://e.com/1", title="t2", fetched_at=datetime.now(timezone.utc), lang="en")
    assert a.url_hash == b.url_hash


def test_enriched_extends_raw():
    raw = RawNewsItem(source="s", url="https://e.com/1", title="t", fetched_at=datetime.now(timezone.utc), lang="en")
    enriched = EnrichedNewsItem(
        **raw.model_dump(exclude={"url_hash"}),
        summary_ko="요약",
        metals=["copper"],
        sentiment=1,
        event_type="supply",
        confidence=0.85,
    )
    assert enriched.metals == ["copper"]
    assert enriched.sentiment == 1


def test_event_type_validation():
    with pytest.raises(ValueError):
        EnrichedNewsItem(
            source="s", url="https://e.com/1", title="t",
            fetched_at=datetime.now(timezone.utc), lang="en",
            summary_ko="", metals=[], sentiment=0, event_type="invalid", confidence=0.5,
        )


def test_event_item():
    ev = EventItem(
        date="2026-05-04",
        type="lme_stock",
        metal="copper",
        magnitude=-0.05,
        title="LME copper stock 5% drop",
    )
    assert ev.metal == "copper"
