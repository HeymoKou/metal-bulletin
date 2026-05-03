"""News pipeline pydantic models."""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

EventType = Literal["supply", "demand", "policy", "macro", "other"]
Sentiment = Literal[-1, 0, 1]
Metal = Literal["copper", "aluminum", "zinc", "nickel", "lead", "tin"]


class RawNewsItem(BaseModel):
    model_config = ConfigDict(frozen=False)

    source: str
    url: str
    title: str
    snippet: str | None = None
    fetched_at: datetime
    lang: str
    published_at: datetime | None = None

    @computed_field
    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:16]


class EnrichedNewsItem(RawNewsItem):
    title_ko: str | None = None
    summary_ko: str | None = None
    metals: list[Metal] = Field(default_factory=list)
    sentiment: Sentiment | None = None
    event_type: EventType | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class EventItem(BaseModel):
    date: date | str
    type: Literal["lme_stock", "lme_announce", "macro"]
    metal: str
    magnitude: float | None = None
    title: str
    url: str | None = None
    source: str | None = None
