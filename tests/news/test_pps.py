"""PPS scraper tests."""
from pathlib import Path

from scraper.news.pps import extract_pdf_text, parse_attachment_url, parse_list

FIX = Path(__file__).parent / "fixtures"


def test_parse_list_filters_two_series():
    html = (FIX / "pps_list.html").read_text(encoding="utf-8")
    items = parse_list(html)
    titles = [it["title"] for it in items]
    assert len(items) >= 8
    assert any("주간 경제" in t and "비철금속" in t for t in titles)
    assert any("주간희소금속" in t for t in titles)
    assert all(
        ("주간 경제" in t and "비철금속" in t) or "주간희소금속" in t
        for t in titles
    )
    for it in items:
        assert it["bbs_sn"].isdigit() and len(it["bbs_sn"]) == 10


def test_parse_attachment_url_strips_jsessionid():
    html = (FIX / "pps_view.html").read_text(encoding="utf-8")
    url = parse_attachment_url(html)
    assert url is not None
    assert url.startswith("/common/fileDown.do")
    assert "jsessionid" not in url.lower()
    assert "key=" in url and "sn=" in url


def test_parse_attachment_url_returns_none_when_missing():
    assert parse_attachment_url("<html>no attachment</html>") is None


def test_extract_pdf_text_dedupes_glyphs():
    import re as _re
    pdf_bytes = (FIX / "pps_sample.pdf").read_bytes()
    text = extract_pdf_text(pdf_bytes)
    assert len(text) > 500
    assert "주간" in text and "비철금속" in text
    # No 5+ Korean char repeats remain (artifact stripped)
    assert _re.search(r"([가-힣])\1{4,}", text) is None


def test_scraper_returns_raw_news_items(monkeypatch):
    from scraper.news.pps import PPSScraper
    from parser.news.models import RawNewsItem

    list_html = (FIX / "pps_list.html").read_text(encoding="utf-8")
    view_html = (FIX / "pps_view.html").read_text(encoding="utf-8")
    pdf_bytes = (FIX / "pps_sample.pdf").read_bytes()

    class FakeResp:
        def __init__(self, content, text=None, status=200):
            self.content = content
            self.text = text if text is not None else content.decode("utf-8", "replace")
            self.status_code = status

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    class FakeSession:
        def __init__(self):
            self.headers = {}
            self.cookies = {}

        def get(self, url, **kw):
            if "list.do" in url:
                return FakeResp(list_html.encode("utf-8"), list_html)
            if "fileDown.do" in url:
                return FakeResp(pdf_bytes)
            raise AssertionError(f"unexpected GET {url}")

        def post(self, url, **kw):
            if "view.do" in url:
                return FakeResp(view_html.encode("utf-8"), view_html)
            raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr("scraper.news.pps.requests.Session", FakeSession)
    monkeypatch.setattr("scraper.news.pps.time.sleep", lambda *_: None)
    items = PPSScraper(limit=2).fetch()
    assert len(items) == 2
    assert all(isinstance(i, RawNewsItem) for i in items)
    assert all(i.source == "pps" for i in items)
    assert all(i.lang == "ko" for i in items)
    assert all(i.snippet and len(i.snippet) > 100 for i in items)


def test_scraper_silent_fail_on_network_error(monkeypatch):
    from scraper.news.pps import PPSScraper

    class BrokenSession:
        def __init__(self):
            self.headers = {}
            self.cookies = {}

        def get(self, *a, **kw):
            raise RuntimeError("dns")

        def post(self, *a, **kw):
            raise RuntimeError("dns")

    monkeypatch.setattr("scraper.news.pps.requests.Session", BrokenSession)
    assert PPSScraper().fetch() == []
