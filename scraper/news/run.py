"""Run all configured news scrapers, write pending file for next pipeline stage.

Raw archive 제거: enriched parquet에 url+title+summary 보존됨. 재요약 욕구 약함.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from scraper.news.pps import PPSScraper
from scraper.news.rss import RSSScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    scrapers = [RSSScraper(), PPSScraper()]
    per_source_counts: dict[str, int] = {}
    all_items = []
    for scraper in scrapers:
        items = scraper.fetch()
        per_source_counts[scraper.name] = len(items)
        logger.info("scraper=%s fetched=%d", scraper.name, len(items))
        all_items.extend(items)

    # Silent-fail guard: 모든 active scrapers가 0이면 outage. Exit non-zero → CI 알림.
    # 단일 source 0은 격리된 실패로 정상 (RSS 1개 죽어도 다른 소스로 cover).
    if not all_items:
        logger.error(
            "FRESHNESS FAIL: all %d scrapers returned 0 items. counts=%s",
            len(scrapers), per_source_counts,
        )
        raise SystemExit(2)

    Path("data").mkdir(exist_ok=True)
    pending = Path("data/news_pending.json")
    with pending.open("w", encoding="utf-8") as f:
        json.dump([item.model_dump(mode="json") for item in all_items], f, ensure_ascii=False)

    logger.info("wrote %d items to %s", len(all_items), pending)


if __name__ == "__main__":
    main()
