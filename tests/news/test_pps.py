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
