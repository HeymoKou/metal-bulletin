"""GDELT 2.0 DOC API scraper.

Global multilingual news search (65 languages, auto-translated to English).
Free, no auth. Rate limit: 1 request per 5 seconds per IP.

API: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from parser.news.models import RawNewsItem
from scraper.news.base import NewsSource

logger = logging.getLogger(__name__)

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "metal-bulletin/0.1 (https://github.com/HeymoKou/metal-bulletin)"
TIMEOUT = 20

# 비철 6개 metals 영문 키워드 + 시장 컨텍스트.
# AND 절로 무관 단어 (Lockheed lead engineer 등) 회피.
DEFAULT_QUERY = (
    "(copper OR aluminum OR aluminium OR nickel OR zinc OR \"tin price\" "
    "OR \"lead price\" OR \"lead smelter\" OR \"lead market\") "
    "AND (price OR mine OR mining OR LME OR SHFE OR smelter OR supply OR demand OR strike OR sanction OR tariff)"
)


class GDELTScraper(NewsSource):
    name = "gdelt"
    lang = "multi"

    def __init__(self, query: str = DEFAULT_QUERY, timespan: str = "24h", maxrecords: int = 75):
        self.query = query
        self.timespan = timespan  # "24h", "7d", etc
        self.maxrecords = maxrecords

    def fetch(self) -> list[RawNewsItem]:
        params = {
            "query": self.query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": self.maxrecords,
            "sort": "datedesc",
            "timespan": self.timespan,
        }
        try:
            r = requests.get(
                GDELT_DOC_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            if r.status_code == 429:
                # Rate limit — wait 6s and retry once
                logger.warning("gdelt 429, retrying after 6s")
                time.sleep(6)
                r = requests.get(
                    GDELT_DOC_URL,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=TIMEOUT,
                )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("gdelt fetch failed err=%s", e)
            return []

        articles = data.get("articles", []) if isinstance(data, dict) else []
        return self._to_items(articles)

    def _to_items(self, articles: list[dict]) -> list[RawNewsItem]:
        now = datetime.now(timezone.utc)
        items: list[RawNewsItem] = []
        for a in articles:
            url = a.get("url") or ""
            title = a.get("title") or ""
            if not url or not title:
                continue
            lang = _normalize_lang(a.get("language"))
            published = self._parse_seendate(a.get("seendate"))
            items.append(RawNewsItem(
                source=self.name,
                url=url,
                title=title,
                snippet=None,
                fetched_at=now,
                lang=lang,
                published_at=published,
            ))
        return items

    @staticmethod
    def _parse_seendate(seen: str | None) -> datetime | None:  # noqa: D401
        return _parse_seendate_impl(seen)


def _normalize_lang(raw: str | None) -> str:
    """GDELT returns 'English'/'Chinese'/etc. Normalize to ISO 639-1 2-letter."""
    if not raw:
        return "en"
    code = raw.strip().lower()
    return {
        "english": "en", "eng": "en",
        "chinese": "zh", "zho": "zh", "zh": "zh",
        "korean": "ko", "kor": "ko",
        "japanese": "ja", "jpn": "ja",
        "spanish": "es", "spa": "es",
        "german": "de", "deu": "de",
        "french": "fr", "fra": "fr",
        "russian": "ru", "rus": "ru",
        "portuguese": "pt", "por": "pt",
    }.get(code, code[:2])


def _parse_seendate_impl(seen: str | None) -> datetime | None:
    """GDELT seendate format: '20260504T093000Z'."""
    if not seen:
        return None
    try:
        return datetime.strptime(seen, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
