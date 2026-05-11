"""KOMIS (한국자원정보서비스) BaseMetals scraper for cross-validation.

Fetches latest-day LME Cash + 3M settlement per metal from
https://www.komis.or.kr/Komis/RsrcPrice/BaseMetals via internal ajax.

Endpoint: POST /Komis/RsrcPrice/ajax/getMnrlPrcByMnrkndUnqCd
Required: JSESSIONID acquired by first hitting the BaseMetals page.

KOMIS prc-criteria cdKey differs per metal (verified 2026-05-12):
    Ni MNRL0002 → CASH 502, 3M 497
    Cu MNRL0008 → CASH 501, 3M 503
    Zn MNRL0023 → CASH 561, 3M 581
    Al MNRL0009 → CASH 495, 3M 496
    Pb MNRL0022 → CASH 499, 3M 500
    Sn MNRL0016 → CASH 493, 3M 494

IP block note: KOMIS blocks AWS ASN ranges (200 + empty body); Azure (GH Actions
runners) and Oracle Cloud Japan pass. Local KR home IPs always work.
"""
from __future__ import annotations

import logging
from typing import NamedTuple

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.komis.or.kr"
PAGE_PATH = "/Komis/RsrcPrice/BaseMetals"
AJAX_PATH = "/Komis/RsrcPrice/ajax/getMnrlPrcByMnrkndUnqCd"
TIMEOUT = 20

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Mapping our metal key → (KOMIS mnrkndUnqCd, CASH cdKey, 3M cdKey)
METALS: dict[str, tuple[str, int, int]] = {
    "copper":   ("MNRL0008", 501, 503),
    "aluminum": ("MNRL0009", 495, 496),
    "zinc":     ("MNRL0023", 561, 581),
    "nickel":   ("MNRL0002", 502, 497),
    "lead":     ("MNRL0022", 499, 500),
    "tin":      ("MNRL0016", 493, 494),
}


class KomisQuote(NamedTuple):
    metal: str
    date: str           # YYYY-MM-DD
    cash: float | None
    m3: float | None
    invt: float | None  # LME inventory (tons)


def _fmt_ymd(yyyymmdd: str) -> str:
    """20260508 → 2026-05-08"""
    if len(yyyymmdd) == 8 and yyyymmdd.isdigit():
        return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
    return yyyymmdd


def _parse_one(payload: dict, metal: str, key: str) -> float | None:
    """Pull cmercPrc-style float from dataAvg.stdMap[key]."""
    std = (payload.get("dataAvg") or {}).get("stdMap") or {}
    node = std.get(key) or {}
    v = node.get("cmercPrc")
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        logger.warning("komis parse %s/%s cmercPrc=%r non-numeric", metal, key, v)
        return None


def fetch(year: int | None = None) -> list[KomisQuote]:
    """Fetch latest available day's Cash + 3M per metal.

    year: range upper bound (defaults to current calendar year). KOMIS returns
    last-day-in-window as CRTRYMD when srchStartDate==srchEndDate==year.

    Returns one KomisQuote per metal. None values stay None — caller decides.
    """
    from datetime import datetime, timezone

    yr = year or datetime.now(timezone.utc).strftime("%Y")
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})

    try:
        sess.get(BASE_URL + PAGE_PATH, timeout=TIMEOUT).raise_for_status()
    except Exception as e:
        logger.warning("komis page fetch failed err=%s", e)
        return []

    out: list[KomisQuote] = []
    for metal, (mcd, cash_cd, m3_cd) in METALS.items():
        cash_data = _fetch_one_metric(sess, mcd, cash_cd, yr)
        if cash_data is None:
            continue
        m3_payload = _fetch_metric_payload(sess, mcd, m3_cd, yr)
        m3 = _parse_one(m3_payload, metal, "CRTRYMD") if m3_payload else None
        cash_payload = cash_data["payload"]
        cash = _parse_one(cash_payload, metal, "CRTRYMD")
        date = _fmt_ymd(
            ((cash_payload.get("dataAvg") or {}).get("stdMap") or {})
            .get("CRTRYMD", {}).get("crtrYmd", "")
        )
        first = (cash_payload.get("data") or {}).get("defaultMnrl") or []
        invt = None
        if first:
            try:
                invt = float(str(first[0].get("invt") or "0").replace(",", "")) or None
            except ValueError:
                invt = None
        out.append(KomisQuote(metal=metal, date=date, cash=cash, m3=m3, invt=invt))
    return out


def _fetch_metric_payload(
    sess: requests.Session, mcd: str, prc_cd: int, year: str
) -> dict | None:
    body = {
        "mnrkndUnqRadioCd": mcd,
        "srchMnrkndUnqCd": mcd,
        "srchPrcCrtr": str(prc_cd),
        "srchAvgOpt": "DAY",
        "srchField": "year",
        "srchStartDate": str(year),
        "srchEndDate": str(year),
        "lmeInvt": "Y",
    }
    try:
        r = sess.post(
            BASE_URL + AJAX_PATH,
            data=body,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": BASE_URL + PAGE_PATH,
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("komis ajax failed mcd=%s prc=%s err=%s", mcd, prc_cd, e)
        return None


def _fetch_one_metric(
    sess: requests.Session, mcd: str, prc_cd: int, year: str
) -> dict | None:
    """Convenience wrapper used to keep retry / future caching options open."""
    p = _fetch_metric_payload(sess, mcd, prc_cd, year)
    if not p:
        return None
    return {"payload": p}
