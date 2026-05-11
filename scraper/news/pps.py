"""PPS 조달청 비축물자 주간 리포트 scraper.

Board: https://www.pps.go.kr/bichuk/bbs/list.do?key=00826
Two target series:
  - "주간 경제·비철금속 시장동향" (Cu/Al/Zn/Ni/Pb/Sn)
  - "주간희소금속가격동향"           (minor metals incl. Sb)
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# <a href="#none" onclick="goView('2605060014', '0001');">
#   주간 경제&middot;비철금속 시장동향(26.5.6)
# </a>
_ROW_RE = re.compile(
    r"goView\('(\d{10})',\s*'[^']*'\)\s*;?\s*\"\s*>\s*([\s\S]{1,500}?)</a>",
    re.IGNORECASE,
)


def _normalize_title(raw: str) -> str:
    t = re.sub(r"<[^>]+>", "", raw)
    t = t.replace("&middot;", "·").replace("&nbsp;", " ")
    return " ".join(t.split())


def _is_target(title: str) -> bool:
    if "주간희소금속" in title:
        return True
    if "주간 경제" in title and "비철금속" in title:
        return True
    return False


def parse_list(html: str) -> list[dict]:
    out = []
    seen: set[str] = set()
    for sn, raw_title in _ROW_RE.findall(html):
        if sn in seen:
            continue
        title = _normalize_title(raw_title)
        if not _is_target(title):
            continue
        seen.add(sn)
        out.append({"bbs_sn": sn, "title": title})
    return out
