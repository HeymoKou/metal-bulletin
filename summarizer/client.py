"""Failover summarizer client.

Tries providers in order. First success wins. All fail → raw items returned
(summary fields = None) — pipeline never blocks on LLM.
"""
from __future__ import annotations

import logging
from typing import Protocol

from parser.news.models import EnrichedNewsItem, RawNewsItem

logger = logging.getLogger(__name__)


class SummarizerProvider(Protocol):
    name: str
    def summarize_batch(self, items: list[RawNewsItem]) -> list[EnrichedNewsItem]: ...


class SummarizerClient:
    def __init__(self, providers: list[SummarizerProvider], batch_size: int = 10):
        if not providers:
            raise ValueError("at least one provider required")
        self.providers = providers
        self.batch_size = batch_size

    def summarize(self, items: list[RawNewsItem]) -> list[EnrichedNewsItem]:
        if not items:
            return []
        out: list[EnrichedNewsItem] = []
        for i in range(0, len(items), self.batch_size):
            chunk = items[i : i + self.batch_size]
            out.extend(self._summarize_chunk(chunk))
        return out

    def _summarize_chunk(self, chunk: list[RawNewsItem]) -> list[EnrichedNewsItem]:
        for provider in self.providers:
            try:
                return provider.summarize_batch(chunk)
            except Exception as e:
                logger.warning("provider %s failed: %s", provider.name, e)
                continue
        logger.error("all providers failed, returning raw")
        return [EnrichedNewsItem(**item.model_dump(exclude={"url_hash"})) for item in chunk]
