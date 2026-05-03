"""Multi-feed RSS scraper.

Iterates configured feeds, parses with feedparser, returns RawNewsItem list.
Per-feed failure is logged and skipped — never raises.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import feedparser

from parser.news.models import RawNewsItem
from scraper.news.base import NewsSource

logger = logging.getLogger(__name__)

RSS_FEEDS: list[dict] = [
    {"source": "mining.com", "url": "https://www.mining.com/feed/", "lang": "en"},
    {"source": "kitco", "url": "https://www.kitco.com/rss/KitcoNews.xml", "lang": "en"},
    {"source": "commodity-tv", "url": "https://www.commodity-tv.com/api/feeds/rss/", "lang": "en"},
    {"source": "hankyung", "url": "https://www.hankyung.com/feed/economy", "lang": "ko"},
    {"source": "moneytoday", "url": "https://rss.mt.co.kr/mt_news.xml", "lang": "ko"},
]


class RSSScraper(NewsSource):
    name = "rss-multi"
    lang = "multi"

    def __init__(self, feeds: list[dict] | None = None):
        self.feeds = feeds if feeds is not None else RSS_FEEDS

    def fetch(self) -> list[RawNewsItem]:
        out: list[RawNewsItem] = []
        now = datetime.now(timezone.utc)
        for feed in self.feeds:
            try:
                items = self._fetch_one(feed, now)
                out.extend(items)
            except Exception as e:
                logger.warning("rss feed failed source=%s err=%s", feed["source"], e)
        return out

    def _fetch_one(self, feed: dict, now: datetime) -> list[RawNewsItem]:
        parsed = feedparser.parse(feed["url"])
        if parsed.bozo and not parsed.entries:
            return []
        items: list[RawNewsItem] = []
        for entry in parsed.entries:
            published = self._parse_published(entry)
            items.append(RawNewsItem(
                source=feed["source"],
                url=entry.get("link", ""),
                title=entry.get("title", ""),
                snippet=entry.get("summary", "")[:500] or None,
                fetched_at=now,
                lang=feed["lang"],
                published_at=published,
            ))
        return [i for i in items if i.url and i.title]

    @staticmethod
    def _parse_published(entry) -> datetime | None:
        for key in ("published_parsed", "updated_parsed"):
            tup = entry.get(key)
            if tup:
                try:
                    return datetime(*tup[:6], tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    continue
        return None
