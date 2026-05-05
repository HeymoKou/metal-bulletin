"""LME prices scraper tests."""
from datetime import date
from unittest.mock import MagicMock

from scraper.lme.prices import (
    LMEDailyPrice,
    SYMBOL_TO_METAL,
    fetch_metal_history,
    _parse,
)

SAMPLE_HTML = """
<table>
<tr>
  <td>04. May 2026</td>
  <td>9,123.50</td>
  <td>9,150.00</td>
  <td>398,675</td>
</tr>
<tr>
  <td>03. May 2026</td>
  <td>9,100.00</td>
  <td>9,128.00</td>
  <td>399,500</td>
</tr>
<tr>
  <td>02. May 2026</td>
  <td>9,080.00</td>
  <td>9,110.00</td>
  <td>400,000</td>
</tr>
</table>
"""


def test_parse_extracts_rows():
    rows = _parse(SAMPLE_HTML, "copper")
    assert len(rows) == 3
    assert rows[0].date == date(2026, 5, 4)
    assert rows[0].sett_cash == 9123.50
    assert rows[0].sett_3m == 9150.00
    assert rows[0].inv_current == 398675
    assert rows[0].metal == "copper"


def test_parse_handles_invalid_month():
    bad_html = """
    <td>04. Foo 2026</td><td>1,000.00</td><td>1,001.00</td><td>500</td>
    """
    assert _parse(bad_html, "copper") == []


def test_parse_skips_malformed_numbers():
    """Comma format expected — bare integer w/o decimal must skip."""
    html = """
    <td>04. May 2026</td><td>abc</td><td>9,150.00</td><td>500</td>
    """
    rows = _parse(html, "copper")
    assert rows == []


def test_fetch_metal_history_unknown_metal():
    import pytest
    with pytest.raises(ValueError):
        fetch_metal_history("gold")


def test_fetch_metal_history_network_failure(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("network down")
    monkeypatch.setattr("scraper.lme.prices.requests.get", boom)
    assert fetch_metal_history("copper") == []


def test_fetch_metal_history_ok(monkeypatch):
    class MockResp:
        text = SAMPLE_HTML
        status_code = 200
        def raise_for_status(self): pass

    monkeypatch.setattr("scraper.lme.prices.requests.get", lambda *a, **k: MockResp())
    rows = fetch_metal_history("copper")
    assert len(rows) == 3
    assert rows[0].metal == "copper"


def test_symbol_to_metal_covers_six():
    assert set(SYMBOL_TO_METAL.values()) == {
        "copper", "aluminum", "zinc", "nickel", "lead", "tin",
    }
