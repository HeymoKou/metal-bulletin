"""Common interface for news scrapers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from parser.news.models import RawNewsItem


class NewsSource(ABC):
    name: str
    lang: str

    @abstractmethod
    def fetch(self) -> list[RawNewsItem]:
        ...
