"""Antimony (Sb) — minor metal price scraper.

Source: scrapmonster.com (Antimony Ingot 99.65% min, item 655)
Five regional tables (EXW China, FOB China, Port India, Warehouse Rotterdam,
Warehouse Baltimore). Static HTML, ~7 latest rows per region — no AJAX needed.

Sb is not LME-listed; updates are monthly-ish, not daily. This scraper is
designed for daily polling: idempotent, returns latest snapshot, builder
detects new dates vs existing parquet.
"""
from __future__ import annotations

import logging
from typing import NamedTuple

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL = "https://www.scrapmonster.com/metal-prices/antimony-ingot-9965-min-price/655"
TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Tab id (1..5) → canonical region key
REGIONS: dict[int, str] = {
    1: "exw_china",
    2: "fob_china",
    3: "port_india",
    4: "rotterdam",
    5: "baltimore",
}

# Conversion factors → USD/MT
LB_PER_MT = 2204.62262
KG_PER_MT = 1000.0


class SbPrice(NamedTuple):
    date: str        # ISO YYYY-MM-DD
    region: str      # canonical key
    price: float     # raw price as published
    unit: str        # raw unit string ($US/MT, $US/Kg, $US/Lb)
    usd_per_mt: float  # normalized USD/MT


def to_usd_per_mt(price: float, unit: str) -> float:
    u = unit.lower()
    if "mt" in u:
        return price
    if "kg" in u:
        return price * KG_PER_MT
    if "lb" in u:
        return price * LB_PER_MT
    raise ValueError(f"unknown unit: {unit}")


def fetch_html(url: str = URL) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def parse(html: str) -> list[SbPrice]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[SbPrice] = []
    for tab_id, region in REGIONS.items():
        tbody = soup.find("tbody", id=f"historicaltable_{tab_id}")
        if not tbody:
            continue
        for tr in tbody.find_all("tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 3:
                continue
            date_str, price_str, unit = tds[0], tds[1], tds[2]
            if len(date_str) != 10 or date_str[4] != "-":
                continue
            try:
                price = float(price_str.replace(",", ""))
            except ValueError:
                continue
            try:
                usd_mt = to_usd_per_mt(price, unit)
            except ValueError as e:
                logger.warning("skip row region=%s date=%s: %s", region, date_str, e)
                continue
            out.append(SbPrice(date_str, region, price, unit, round(usd_mt, 2)))
    return out


def fetch() -> list[SbPrice]:
    """Fetch + parse. Returns empty list on failure (logged)."""
    try:
        html = fetch_html()
    except Exception as e:
        logger.warning("scrapmonster fetch failed: %s", e)
        return []
    return parse(html)


if __name__ == "__main__":
    import json
    rows = fetch()
    print(json.dumps([r._asdict() for r in rows], indent=2))
    print(f"\n{len(rows)} rows across {len({r.region for r in rows})} regions")
