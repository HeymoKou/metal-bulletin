"""KORES scraper tests."""
from pathlib import Path
from scraper.news.kores import KORES_BASE_URL, KoresScraper

FIXTURE = Path(__file__).parent / "fixtures" / "kores_sample.html"


def test_parse_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = KoresScraper()
    items = scraper._parse(html)
    assert len(items) == 2
    assert items[0].title == "전기동 가격, 중국 수요 증가로 상승"
    assert items[0].url.startswith("https://")
    assert items[0].lang == "ko"
    assert items[0].source == "kores"


def test_fetch_handles_network_failure():
    scraper = KoresScraper(base_url="http://localhost:1/nonexistent")
    items = scraper.fetch()
    assert items == []


def test_relative_url_resolved():
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = KoresScraper()
    items = scraper._parse(html)
    for item in items:
        assert item.url.startswith(KORES_BASE_URL)


def test_fetch_calls_parse(monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = KoresScraper()

    class MockResp:
        text = html
        status_code = 200
        def raise_for_status(self): pass

    monkeypatch.setattr("scraper.news.kores.requests.get", lambda *a, **k: MockResp())
    items = scraper.fetch()
    assert len(items) == 2
