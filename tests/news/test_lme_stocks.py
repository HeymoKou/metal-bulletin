"""LME stocks scraper tests."""
from datetime import date
from unittest.mock import MagicMock

from scraper.lme.stocks import fetch_lme_stocks, parse_stocks

# Minimal HTML mimicking westmetall structure: prices block then stocks block.
SAMPLE_HTML = """
<table>
<tr><td><a href="?field=LME_Cu_cash" class="block">Copper </a></td>
    <td><a href="?field=LME_Cu_cash" class="block">12,895.00 </a></td>
    <td><a href="?field=LME_Cu_cash" class="block">12,967.00 </a></td></tr>
<tr><td><a href="?field=LME_Al_cash" class="block">Aluminium </a></td>
    <td><a href="?field=LME_Al_cash" class="block">3,584.00 </a></td>
    <td><a href="?field=LME_Al_cash" class="block">3,523.00 </a></td></tr>
</table>
<h2>Stocks</h2>
<table>
<tr><td><a href="?field=LME_Cu_cash" class="block">Copper </a></td>
    <td><a href="?field=LME_Cu_cash" class="block">398,675 </a></td>
    <td><a href="?field=LME_Cu_cash" class="block">-1,050 </a></td></tr>
<tr><td><a href="?field=LME_Al_cash" class="block">Aluminium </a></td>
    <td><a href="?field=LME_Al_cash" class="block">364,725 </a></td>
    <td><a href="?field=LME_Al_cash" class="block">-2,325 </a></td></tr>
<tr><td><a href="?field=LME_Sn_cash" class="block">Tin </a></td>
    <td><a href="?field=LME_Sn_cash" class="block">8,475 </a></td>
    <td><a href="?field=LME_Sn_cash" class="block">-115 </a></td></tr>
</table>
"""


def test_parse_stocks_extracts_correct_values():
    today = date(2026, 5, 4)
    events = parse_stocks(SAMPLE_HTML, today=today)

    by_metal = {e.metal: e for e in events}
    assert by_metal["copper"].magnitude == -1050.0
    assert "398,675" in by_metal["copper"].title
    assert by_metal["aluminum"].magnitude == -2325.0
    assert "364,725" in by_metal["aluminum"].title
    assert by_metal["tin"].magnitude == -115.0


def test_parse_stocks_skips_missing_metals():
    """Sample only has 3 of 6 metals — others silently skipped."""
    events = parse_stocks(SAMPLE_HTML)
    metals = {e.metal for e in events}
    assert metals == {"copper", "aluminum", "tin"}


def test_parse_stocks_event_type_and_source():
    events = parse_stocks(SAMPLE_HTML)
    for e in events:
        assert e.type == "lme_stock"
        assert e.source == "westmetall"
        assert e.url and "westmetall.com" in e.url


def test_parse_stocks_skips_price_only_blocks():
    """If a metal only has decimal-price entries, it must NOT match."""
    price_only = """
    <table>
    <tr><td><a href="?field=LME_Pb_cash" class="block">Lead </a></td>
        <td><a href="?field=LME_Pb_cash" class="block">2,134.50 </a></td>
        <td><a href="?field=LME_Pb_cash" class="block">2,140.00 </a></td></tr>
    </table>
    """
    events = parse_stocks(price_only)
    assert events == []


def test_fetch_handles_network_failure(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("network down")
    monkeypatch.setattr("scraper.lme.stocks.requests.get", boom)
    assert fetch_lme_stocks() == []


def test_fetch_calls_parser(monkeypatch):
    class MockResp:
        text = SAMPLE_HTML
        status_code = 200
        def raise_for_status(self): pass
    monkeypatch.setattr("scraper.lme.stocks.requests.get", lambda *a, **k: MockResp())
    events = fetch_lme_stocks()
    assert len(events) == 3
