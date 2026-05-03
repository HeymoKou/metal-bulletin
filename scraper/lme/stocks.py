"""LME warehouse stocks scraper via westmetall.com.

LME 공식은 vendor 라이선스 + 403 (programmatic block). westmetall은 무료 미러.
Daily snapshot of 6 metals + delta from previous day.

Output: list[EventItem] with type='lme_stock', metal=<6 metals>, magnitude=delta_tonnes.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import requests

from parser.news.models import EventItem

logger = logging.getLogger(__name__)

WESTMETALL_URL = "https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Stocks_Cu"
TIMEOUT = 15

# westmetall HTML uses field=LME_<Symbol>_cash for each metal row.
SYMBOL_TO_METAL: dict[str, str] = {
    "Cu": "copper",
    "Al": "aluminum",
    "Zn": "zinc",
    "Ni": "nickel",
    "Pb": "lead",
    "Sn": "tin",
}

# Each metal block looks like:
#   field=LME_<Sym>_cash" class="block">\s*<NAME>\s*</a>
#   ...field=LME_<Sym>_cash"...>\s*<STOCK>\s*</a>
#   ...field=LME_<Sym>_cash"...>\s*<DELTA>\s*</a>
# We extract two consecutive numbers following the metal-symbol field reference.
NUMBER_RE = re.compile(r">\s*([+-]?[\d,]+)\s*</a>")


def fetch_lme_stocks() -> list[EventItem]:
    try:
        r = requests.get(WESTMETALL_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=TIMEOUT)
        r.raise_for_status()
        return parse_stocks(r.text)
    except Exception as e:
        logger.warning("lme_stocks fetch failed err=%s", e)
        return []


def parse_stocks(html: str, today: date | None = None) -> list[EventItem]:
    """Extract per-metal current stock + delta from westmetall stocks page.

    Page has both a price table and a stocks table referencing same `LME_<sym>_cash`
    field. Stocks table follows the price table — find the stocks-table row per metal
    by matching name cell + 2 numeric cells (no decimals = stocks, decimals = prices).
    """
    today = today or datetime.now(timezone.utc).date()
    out: list[EventItem] = []
    # Stocks rows look like:
    #   field=LME_<Sym>_cash" class="block">\nNAME </a>
    #   ... field=LME_<Sym>_cash" class="block">\nSTOCK_NUM </a>
    #   ... field=LME_<Sym>_cash" class="block">\nDELTA_NUM </a>
    # Prices rows have decimal point (e.g., "12,895.00") — anchor on integer-only.
    for symbol, metal in SYMBOL_TO_METAL.items():
        # Find rows where THREE consecutive `field=LME_<sym>_cash` references
        # contain: name (text), stock (integer with comma), delta (integer with sign).
        row_re = re.compile(
            rf'field=LME_{symbol}_cash"[^>]*?>\s*[A-Za-z]+\s*</a>'                  # name
            rf'[\s\S]{{0,500}}?'
            rf'field=LME_{symbol}_cash"[^>]*?>\s*([\d,]+)\s*</a>'                   # stock (no decimal)
            rf'[\s\S]{{0,500}}?'
            rf'field=LME_{symbol}_cash"[^>]*?>\s*([+-]?[\d,]+)\s*</a>',             # delta
            re.IGNORECASE,
        )
        m = row_re.search(html)
        if not m:
            logger.debug("lme_stocks: no stocks row match for %s", symbol)
            continue
        try:
            stock = int(m.group(1).replace(",", ""))
            delta = int(m.group(2).replace(",", ""))
        except ValueError:
            continue
        # Sanity check — stocks should be > 100 tonnes (well above 0)
        if stock < 100:
            logger.debug("lme_stocks: %s stock %d looks like a price, skipping", symbol, stock)
            continue
        out.append(EventItem(
            date=today.isoformat(),
            type="lme_stock",
            metal=metal,
            magnitude=float(delta),
            title=f"LME {metal} stock: {stock:,} t (Δ{delta:+,})",
            url=WESTMETALL_URL,
            source="westmetall",
        ))
    return out
