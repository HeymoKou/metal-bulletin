"""PPS scraper tests."""
from pathlib import Path

from scraper.news.pps import parse_list

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
