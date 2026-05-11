"""RSS scraper tests."""
from pathlib import Path
import pytest
from scraper.news.rss import RSS_FEEDS, RSSScraper

FIXTURE = Path(__file__).parent / "fixtures" / "sample_rss.xml"


def test_rss_feeds_constant_has_required_sources():
    sources = {f["source"] for f in RSS_FEEDS}
    assert "snmnews" in sources


def test_parse_fixture():
    scraper = RSSScraper(feeds=[{"source": "test", "url": str(FIXTURE), "lang": "en"}])
    items = scraper.fetch()
    assert len(items) == 2
    assert items[0].title == "Copper prices surge on supply concerns"
    assert items[0].source == "test"
    assert items[0].lang == "en"
    assert items[0].url == "https://example.com/copper-surge"
    assert items[0].published_at is not None


def test_fetch_handles_network_failure():
    scraper = RSSScraper(feeds=[{"source": "bad", "url": "http://localhost:1/nonexistent.xml", "lang": "en"}])
    items = scraper.fetch()
    assert items == []


def test_fetch_partial_on_one_feed_failure():
    scraper = RSSScraper(feeds=[
        {"source": "good", "url": str(FIXTURE), "lang": "en"},
        {"source": "bad", "url": "http://localhost:1/x.xml", "lang": "en"},
    ])
    items = scraper.fetch()
    assert len(items) == 2
    assert all(i.source == "good" for i in items)
