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

USER_AGENT = "Mozilla/5.0 (compatible; metal-bulletin/0.1; +https://github.com/HeymoKou/metal-bulletin)"

# Phase 1a verified-working feeds. Dead feeds (kitco/commodity-tv/hankyung RSS) removed.
# KORES URL changed — deferred to Phase 1b reverse engineering.
RSS_FEEDS: list[dict] = [
    {"source": "snmnews", "url": "https://www.snmnews.com/rss/allArticle.xml", "lang": "ko"},
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
        parsed = feedparser.parse(feed["url"], agent=USER_AGENT)
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
