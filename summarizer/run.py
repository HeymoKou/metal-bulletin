"""Summarize pending → enriched, write to news_enriched.json."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from parser.news.models import RawNewsItem
from summarizer.client import SummarizerClient
from summarizer.providers.gemini import GeminiProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    pending = Path("data/news_pending.json")
    if not pending.exists():
        logger.warning("no pending file, skip")
        return

    raw = json.loads(pending.read_text(encoding="utf-8"))
    items = [RawNewsItem.model_validate(r) for r in raw]
    if not items:
        logger.info("no items to summarize")
        return

    providers = []
    if os.environ.get("GEMINI_API_KEY"):
        providers.append(GeminiProvider())
    if not providers:
        logger.error("no LLM provider configured (GEMINI_API_KEY missing)")
        return

    client = SummarizerClient(providers=providers, batch_size=10)
    enriched = client.summarize(items)
    null_count = sum(1 for e in enriched if e.summary_ko is None)
    logger.info("summarized %d items (null=%d)", len(enriched), null_count)

    # Silent-fail guard: items 5건 이상에서 100% null이면 LLM 전체 outage.
    # 5건 미만은 정상 (입력 적음) — false positive 방지.
    if len(enriched) >= 5 and null_count == len(enriched):
        logger.error(
            "FRESHNESS FAIL: all %d summarize attempts returned null (LLM outage)", len(enriched)
        )
        raise SystemExit(2)

    out = Path("data/news_enriched.json")
    out.write_text(
        json.dumps([e.model_dump(mode="json") for e in enriched], ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
