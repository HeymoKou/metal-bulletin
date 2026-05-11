"""PPS 조달청 비축물자 주간 리포트 scraper.

Board: https://www.pps.go.kr/bichuk/bbs/list.do?key=00826
Two target series:
  - "주간 경제·비철금속 시장동향" (Cu/Al/Zn/Ni/Pb/Sn)
  - "주간희소금속가격동향"           (minor metals incl. Sb)
"""
from __future__ import annotations

import io
import logging
import re

import pdfplumber

logger = logging.getLogger(__name__)

# pdfplumber on Korean PDFs sometimes yields 5+ repeated chars (e.g. 주주주주주). Collapse.
_KOR_REPEAT_RE = re.compile(r"([가-힣])\1{3,}")


def extract_pdf_text(pdf_bytes: bytes, max_pages: int = 6) -> str:
    """Extract text from first `max_pages` of PDF. Collapses Korean glyph runs of 4+."""
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:max_pages]:
            t = page.extract_text() or ""
            if t:
                parts.append(t)
    raw = "\n".join(parts)
    return _KOR_REPEAT_RE.sub(r"\1", raw)

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


_ATTACH_RE = re.compile(
    r'href="(/common/fileDown\.do[^"]+)"',
    re.IGNORECASE,
)
_JSESSION_RE = re.compile(r";jsessionid=[^?]+", re.IGNORECASE)


def parse_attachment_url(html: str) -> str | None:
    m = _ATTACH_RE.search(html)
    if not m:
        return None
    return _JSESSION_RE.sub("", m.group(1))


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
