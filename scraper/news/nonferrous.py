"""한국비철금속협회 (nonferrous.or.kr) 산업트렌드 게시판 스크래퍼.

`/bbs/?bid=trend` 페이지에서 비철 산업 동향 뉴스 헤드라인 fetch.
"""
from __future__ import annotations

import html as html_lib
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

from parser.news.models import RawNewsItem
from scraper.news.base import NewsSource

logger = logging.getLogger(__name__)

NONFERROUS_BASE_URL = "https://www.nonferrous.or.kr"
TREND_PATH = "/bbs/?bid=trend"
TIMEOUT = 15

# 게시판 내 article 링크: '?act=bbs&subAct=view&bid=trend&page=1&order_type=desc&seq=NNNN'
LINK_RE = re.compile(
    r'<a [^>]*?href="([^"]+subAct=view[^"]+bid=trend[^"]+)"[^>]*?>([^<]{5,200})</a>',
    re.IGNORECASE,
)


class NonferrousScraper(NewsSource):
    name = "nonferrous"
    lang = "ko"

    def __init__(self, base_url: str = NONFERROUS_BASE_URL):
        self.base_url = base_url

    def fetch(self) -> list[RawNewsItem]:
        url = urljoin(self.base_url, TREND_PATH)
        # Realistic Chrome headers — Korean assoc site sensitive to non-browser UAs/IPs.
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": self.base_url + "/",
        }
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            items = self._parse(r.text)
            if not items:
                logger.warning(
                    "nonferrous: 0 items parsed (status=%d, len=%d). "
                    "Possible geo-block or HTML structure change.",
                    r.status_code, len(r.text),
                )
            return items
        except Exception as e:
            logger.warning("nonferrous fetch failed err=%s", e)
            return []

    def _parse(self, html: str) -> list[RawNewsItem]:
        now = datetime.now(timezone.utc)
        items: list[RawNewsItem] = []
        seen_seqs: set[str] = set()
        for href, title in LINK_RE.findall(html):
            # href 시작 '?...' relative — base URL + bbs/ path 결합
            if href.startswith("?"):
                full_url = urljoin(self.base_url + "/bbs/", href)
            else:
                full_url = urljoin(self.base_url, href)

            # seq 추출해 page param 차이로 인한 중복 방지
            m = re.search(r"seq=(\d+)", href)
            seq = m.group(1) if m else None
            if seq:
                if seq in seen_seqs:
                    continue
                seen_seqs.add(seq)

            cleaned_title = html_lib.unescape(title).strip()
            cleaned_title = re.sub(r"\s+", " ", cleaned_title)
            if not cleaned_title:
                continue
            items.append(RawNewsItem(
                source=self.name,
                url=full_url,
                title=cleaned_title,
                fetched_at=now,
                lang=self.lang,
            ))
        return items
