"""Dedupe + classify pending news. Writes filtered list back."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from parser.news.classify import is_relevant
from parser.news.dedupe import dedupe
from parser.news.models import RawNewsItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    pending = Path("data/news_pending.json")
    if not pending.exists():
        logger.warning("no pending file, skip")
        return

    raw = json.loads(pending.read_text(encoding="utf-8"))
    items = [RawNewsItem.model_validate(r) for r in raw]
    logger.info("loaded %d raw items", len(items))

    deduped = dedupe(items)
    logger.info("after dedupe: %d", len(deduped))

    relevant = [i for i in deduped if is_relevant(i)]
    logger.info("after classify: %d", len(relevant))

    pending.write_text(
        json.dumps([i.model_dump(mode="json") for i in relevant], ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
