"""Run all configured news scrapers, write pending file for next pipeline stage.

Raw archive 제거: enriched parquet에 url+title+summary 보존됨. 재요약 욕구 약함.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from scraper.news.rss import RSSScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    # KoresScraper deferred — URL reverse engineering needed (Phase 1b)
    scrapers = [RSSScraper()]
    all_items = []
    for scraper in scrapers:
        items = scraper.fetch()
        logger.info("scraper=%s fetched=%d", scraper.name, len(items))
        all_items.extend(items)

    if not all_items:
        logger.warning("no items fetched")
        return

    Path("data").mkdir(exist_ok=True)
    pending = Path("data/news_pending.json")
    with pending.open("w", encoding="utf-8") as f:
        json.dump([item.model_dump(mode="json") for item in all_items], f, ensure_ascii=False)

    logger.info("wrote %d items to %s", len(all_items), pending)


if __name__ == "__main__":
    main()
