"""Run all configured news scrapers, write raw archive + pending file."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import zstandard as zstd

from scraper.news.kores import KoresScraper
from scraper.news.rss import RSSScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/news")


def main() -> None:
    scrapers = [RSSScraper(), KoresScraper()]
    all_items = []
    for scraper in scrapers:
        items = scraper.fetch()
        logger.info("scraper=%s fetched=%d", scraper.name, len(items))
        all_items.extend(items)

    if not all_items:
        logger.warning("no items fetched")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    out_file = RAW_DIR / f"{now.strftime('%Y-%m')}.jsonl.zst"

    cctx = zstd.ZstdCompressor(level=10)
    with open(out_file, "ab") as f, cctx.stream_writer(f) as compressor:
        for item in all_items:
            compressor.write((item.model_dump_json() + "\n").encode("utf-8"))

    Path("data").mkdir(exist_ok=True)
    pending = Path("data/news_pending.json")
    with pending.open("w", encoding="utf-8") as f:
        json.dump([item.model_dump(mode="json") for item in all_items], f, ensure_ascii=False)

    logger.info("wrote %d raw items to %s and pending %s", len(all_items), out_file, pending)


if __name__ == "__main__":
    main()
