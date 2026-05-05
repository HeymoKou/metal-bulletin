"""LME daily settlement prices via westmetall.com.

Cross-validated against NH 선물 PDF data (90 days, all 6 metals): Δ = 0.00.
Westmetall column labels are misleading — actual mapping:
  - 'bid' column → LME cash settlement (sett_cash)
  - 'ask' column → LME 3-month settlement (sett_3m)
  - 'stock' column → LME warehouse inventory (inv_current)

Use cases:
  - Holiday fallback when NH 선물 PDF not published (KR holiday but LME open)
  - 10-year+ historical backfill (data goes back to 2008)
  - Sanity check / cross-validation
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import NamedTuple

import requests

logger = logging.getLogger(__name__)

WESTMETALL_BASE = "https://www.westmetall.com/en/markdaten.php"
TIMEOUT = 15

SYMBOL_TO_METAL: dict[str, str] = {
    "Cu": "copper",
    "Al": "aluminum",
    "Zn": "zinc",
    "Ni": "nickel",
    "Pb": "lead",
    "Sn": "tin",
}
METAL_TO_SYMBOL = {v: k for k, v in SYMBOL_TO_METAL.items()}

MONTH_TO_NUM = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

# Row pattern: <td>DD. Month YYYY</td><td>cash_sett</td><td>3m_sett</td><td>stock</td>
ROW_RE = re.compile(
    r'<td[^>]*>\s*(\d{2})\.\s+(\w+)\s+(\d{4})\s*</td>'
    r'\s*<td[^>]*>\s*([\d,]+\.\d+)\s*</td>'
    r'\s*<td[^>]*>\s*([\d,]+\.\d+)\s*</td>'
    r'\s*<td[^>]*>\s*([\d,]+)\s*</td>'
)


class LMEDailyPrice(NamedTuple):
    date: date
    metal: str            # canonical metal key (copper/aluminum/...)
    sett_cash: float      # USD/ton
    sett_3m: float        # USD/ton
    inv_current: int      # tonnes


def fetch_metal_history(metal: str) -> list[LMEDailyPrice]:
    """Return all available daily prices (~10y+) for one metal."""
    symbol = METAL_TO_SYMBOL.get(metal)
    if not symbol:
        raise ValueError(f"unknown metal: {metal}")
    try:
        r = requests.get(
            WESTMETALL_BASE,
            params={"action": "table", "field": f"LME_{symbol}_cash"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return _parse(r.text, metal)
    except Exception as e:
        logger.warning("westmetall prices fetch failed metal=%s err=%s", metal, e)
        return []


def fetch_date(d: date, metals: list[str] | None = None) -> dict[str, LMEDailyPrice]:
    """Return per-metal price for a single date. Missing metals omitted."""
    metals = metals or list(METAL_TO_SYMBOL.keys())
    out: dict[str, LMEDailyPrice] = {}
    for metal in metals:
        history = fetch_metal_history(metal)
        for p in history:
            if p.date == d:
                out[metal] = p
                break
    return out


def _parse(html: str, metal: str) -> list[LMEDailyPrice]:
    rows: list[LMEDailyPrice] = []
    for day, month, year, cash, three_m, stock in ROW_RE.findall(html):
        if month not in MONTH_TO_NUM:
            continue
        try:
            d = date(int(year), MONTH_TO_NUM[month], int(day))
            rows.append(LMEDailyPrice(
                date=d,
                metal=metal,
                sett_cash=float(cash.replace(",", "")),
                sett_3m=float(three_m.replace(",", "")),
                inv_current=int(stock.replace(",", "")),
            ))
        except (ValueError, KeyError):
            continue
    return rows
