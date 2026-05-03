"""Dedupe tests."""
from datetime import datetime, timezone
from parser.news.dedupe import dedupe
from parser.news.models import RawNewsItem


def _item(url: str, title: str, source: str = "s") -> RawNewsItem:
    return RawNewsItem(
        source=source, url=url, title=title,
        fetched_at=datetime.now(timezone.utc), lang="en",
    )


def test_url_hash_dedup():
    items = [
        _item("https://e.com/a", "Title A"),
        _item("https://e.com/a", "Different Title"),
        _item("https://e.com/b", "Title B"),
    ]
    out = dedupe(items)
    assert len(out) == 2
    assert {i.url for i in out} == {"https://e.com/a", "https://e.com/b"}


def test_fuzzy_title_dedup():
    items = [
        _item("https://a.com/1", "Copper prices surge on supply concerns"),
        _item("https://b.com/2", "Copper prices surge on supply concern"),
        _item("https://c.com/3", "Aluminum demand falls in Q1"),
    ]
    out = dedupe(items, fuzzy_threshold=0.85)
    assert len(out) == 2


def test_fuzzy_below_threshold_kept():
    items = [
        _item("https://a.com/1", "Copper hits 5-year high"),
        _item("https://b.com/2", "Aluminum hits 3-month low"),
    ]
    out = dedupe(items, fuzzy_threshold=0.85)
    assert len(out) == 2


def test_empty_input():
    assert dedupe([]) == []


def test_dedupe_preserves_first_occurrence():
    items = [
        _item("https://a.com/1", "Same title", source="first"),
        _item("https://a.com/1", "Same title", source="second"),
    ]
    out = dedupe(items)
    assert len(out) == 1
    assert out[0].source == "first"
