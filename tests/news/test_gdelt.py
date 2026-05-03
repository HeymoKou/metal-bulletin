"""GDELT scraper tests (mocked)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from scraper.news.gdelt import GDELTScraper


def _mock_response(articles: list[dict], status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {"articles": articles}
    r.raise_for_status = MagicMock()
    return r


def test_fetch_parses_articles(monkeypatch):
    fake_articles = [
        {
            "url": "https://example.com/copper-1",
            "title": "Copper hits 5y high",
            "language": "English",
            "seendate": "20260504T093000Z",
        },
        {
            "url": "https://example.cn/铜价",
            "title": "Tongjia shangzhang",
            "language": "Chinese",
            "seendate": "20260504T100000Z",
        },
    ]
    monkeypatch.setattr("scraper.news.gdelt.requests.get",
                        lambda *a, **k: _mock_response(fake_articles))
    scraper = GDELTScraper()
    items = scraper.fetch()
    assert len(items) == 2
    assert items[0].source == "gdelt"
    assert items[0].title == "Copper hits 5y high"
    assert items[0].lang == "en"
    assert items[0].published_at is not None


def test_fetch_handles_network_error(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("network down")
    monkeypatch.setattr("scraper.news.gdelt.requests.get", boom)
    scraper = GDELTScraper()
    assert scraper.fetch() == []


def test_fetch_handles_429_with_retry(monkeypatch):
    """429 → 6s sleep → retry once."""
    calls = []
    sleep_calls = []
    def fake_get(*a, **k):
        calls.append(k.get("params"))
        if len(calls) == 1:
            return _mock_response([], status=429)
        return _mock_response([{
            "url": "https://e.com/1", "title": "Copper up",
            "language": "English", "seendate": "20260504T100000Z",
        }])
    monkeypatch.setattr("scraper.news.gdelt.requests.get", fake_get)
    monkeypatch.setattr("scraper.news.gdelt.time.sleep", lambda s: sleep_calls.append(s))

    scraper = GDELTScraper()
    items = scraper.fetch()
    assert len(items) == 1
    assert len(calls) == 2
    assert sleep_calls == [6]


def test_fetch_skips_invalid_articles(monkeypatch):
    fake_articles = [
        {"url": "", "title": "no url"},
        {"url": "https://e.com/x", "title": ""},
        {"url": "https://e.com/ok", "title": "Valid one", "language": "English"},
    ]
    monkeypatch.setattr("scraper.news.gdelt.requests.get",
                        lambda *a, **k: _mock_response(fake_articles))
    scraper = GDELTScraper()
    items = scraper.fetch()
    assert len(items) == 1
    assert items[0].title == "Valid one"


def test_seendate_parsing():
    parsed = GDELTScraper._parse_seendate("20260504T093045Z")
    assert parsed.year == 2026 and parsed.month == 5 and parsed.day == 4
    assert parsed.tzinfo is timezone.utc
    assert GDELTScraper._parse_seendate(None) is None
    assert GDELTScraper._parse_seendate("invalid") is None
