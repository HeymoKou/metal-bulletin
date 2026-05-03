"""KORES (한국광물공사) 일일자원뉴스 스크래퍼."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from parser.news.models import RawNewsItem
from scraper.news.base import NewsSource

logger = logging.getLogger(__name__)

KORES_BASE_URL = "https://www.kores.net"
KORES_LIST_PATH = "/views/cms/komis/price/kores_02_list.jsp"
TIMEOUT = 15


class KoresScraper(NewsSource):
    name = "kores"
    lang = "ko"

    def __init__(self, base_url: str = KORES_BASE_URL):
        self.base_url = base_url

    def fetch(self) -> list[RawNewsItem]:
        url = urljoin(self.base_url, KORES_LIST_PATH)
        try:
            resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "metal-bulletin/0.1"})
            resp.raise_for_status()
            return self._parse(resp.text)
        except Exception as e:
            logger.warning("kores fetch failed err=%s", e)
            return []

    def _parse(self, html: str) -> list[RawNewsItem]:
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table.board_list tbody tr")
        now = datetime.now(timezone.utc)
        items: list[RawNewsItem] = []
        for row in rows:
            link = row.select_one("td.title a")
            if not link:
                continue
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not href or not title:
                continue
            full_url = urljoin(self.base_url, href)
            items.append(RawNewsItem(
                source=self.name,
                url=full_url,
                title=title,
                fetched_at=now,
                lang=self.lang,
            ))
        return items
