"""한국비철금속협회 scraper tests."""
from pathlib import Path
from unittest.mock import MagicMock

from scraper.news.nonferrous import NONFERROUS_BASE_URL, NonferrousScraper

FIXTURE = Path(__file__).parent / "fixtures" / "nonferrous_sample.html"


def test_parse_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = NonferrousScraper()
    items = scraper._parse(html)
    # 4 entries in fixture, but seq=4959 dup → 3 unique
    assert len(items) == 3
    assert items[0].title == "\"금·구리 상승세 앞질렀다\"…1년 새 557% 급등한 '텅스텐'"
    assert items[0].source == "nonferrous"
    assert items[0].lang == "ko"
    assert items[0].url.startswith(NONFERROUS_BASE_URL)
    assert "seq=5002" in items[0].url


def test_dedupes_by_seq():
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = NonferrousScraper()
    items = scraper._parse(html)
    seqs = [i.url.split("seq=")[-1] for i in items]
    assert len(set(seqs)) == len(seqs)  # all unique


def test_fetch_handles_network_failure():
    scraper = NonferrousScraper(base_url="http://localhost:1/nonexistent")
    assert scraper.fetch() == []


def test_fetch_calls_parse(monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")

    class MockResp:
        text = html
        status_code = 200
        def raise_for_status(self): pass

    monkeypatch.setattr("scraper.news.nonferrous.requests.get", lambda *a, **k: MockResp())
    scraper = NonferrousScraper()
    items = scraper.fetch()
    assert len(items) == 3
