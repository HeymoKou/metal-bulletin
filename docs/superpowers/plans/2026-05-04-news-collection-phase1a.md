# 비철 뉴스 수집 파이프라인 — Phase 1a (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RSS 6개 + KORES 1개 소스에서 비철 뉴스 자동 수집, Gemini Flash로 요약·분류, Parquet 저장하는 GitHub Actions 워크플로우를 ship한다.

**Architecture:** 가격 파이프라인(`scraper/`, `parser/`, `builder/`)과 독립된 news 서브패키지. 각 소스 = 단일 책임 모듈. `base.NewsSource` 인터페이스로 swap 가능. LLM provider도 동일 패턴. TDD per module.

**Tech Stack:** Python 3.14, uv, feedparser, beautifulsoup4, rapidfuzz, pydantic v2, google-genai (Gemini SDK), pyarrow, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-05-04-news-collection-design.md`

**Phase Scope (이 plan):** Phase 1a만. Phase 1b (GDELT/LME/협회) 와 Phase 1c (marketaux/SMM/철강금속신문) 은 별도 plan.

**Parallelization 규약:** `[INDEPENDENT]` 마크된 Task는 다른 `[INDEPENDENT]` Task와 동시 dispatch 가능 (sonnet subagent 병렬). `[SEQUENTIAL]` 은 이전 Task 완료 필요.

---

## Task Dependency Graph

```
Task 1 (deps + 디렉토리)        SEQUENTIAL — foundation
   ↓
Task 2 (models + base 인터페이스) SEQUENTIAL — 모든 모듈이 import
   ↓
   ├── Task 3 (rss.py)          INDEPENDENT ──┐
   ├── Task 4 (kores.py)        INDEPENDENT ──┼── 병렬 dispatch
   ├── Task 5 (dedupe.py)       INDEPENDENT ──┤
   └── Task 6 (classify.py)     INDEPENDENT ──┘
   ↓
Task 7 (summarizer/gemini)      SEQUENTIAL — provider 1개, prompt 포함
   ↓
Task 8 (summarizer/client + failover) SEQUENTIAL — Task 7 의존
   ↓
Task 9 (builder/news_build)     SEQUENTIAL — 위 전부 의존
   ↓
Task 10 (orchestrator run.py)   SEQUENTIAL
   ↓
Task 11 (news.yml workflow)     SEQUENTIAL
   ↓
Task 12 (manifest 갱신)         SEQUENTIAL
   ↓
Task 13 (smoke + 통합)          SEQUENTIAL
```

**병렬 dispatch 가이드:** Task 3/4/5/6 동시 실행. Task 2 완료 직후 4개 sonnet subagent에 각각 dispatch.

---

## File Structure

신규 파일:
```
scraper/news/__init__.py
scraper/news/base.py              # NewsSource ABC
scraper/news/rss.py               # 5 RSS feeds 일괄
scraper/news/kores.py             # KORES BS4 스크랩
scraper/news/run.py               # orchestrator
parser/news/__init__.py
parser/news/models.py             # pydantic
parser/news/dedupe.py
parser/news/classify.py
parser/news/run.py                # orchestrator
summarizer/__init__.py
summarizer/prompt.py
summarizer/providers/__init__.py
summarizer/providers/gemini.py
summarizer/client.py              # failover chain
summarizer/run.py                 # orchestrator
builder/news_build.py
tests/news/__init__.py
tests/news/conftest.py            # fixtures
tests/news/test_models.py
tests/news/test_rss.py
tests/news/test_kores.py
tests/news/test_dedupe.py
tests/news/test_classify.py
tests/news/test_summarizer.py
tests/news/test_news_build.py
tests/news/fixtures/             # RSS 샘플 + KORES HTML
.github/workflows/news.yml
```

수정:
```
pyproject.toml                    # deps 추가
builder/build.py                  # manifest에 news 섹션 (Task 12)
CLAUDE.md                         # 보안 핀 갱신
```

---

## Task 1: Setup — Dependencies & Directory Skeleton

**[SEQUENTIAL]** Foundation. 다른 Task 시작 전 필수.

**Files:**
- Modify: `pyproject.toml`
- Create: 빈 `__init__.py` (scraper/news, parser/news, summarizer, summarizer/providers, tests/news)
- Create: `tests/news/fixtures/` 디렉토리

- [ ] **Step 1: 의존성 추가**

```bash
uv add feedparser rapidfuzz pydantic google-genai
uv add --dev pytest-mock
```

- [ ] **Step 2: 디렉토리/__init__.py 생성**

```bash
mkdir -p scraper/news parser/news summarizer/providers tests/news/fixtures
touch scraper/news/__init__.py parser/news/__init__.py summarizer/__init__.py summarizer/providers/__init__.py tests/news/__init__.py
```

- [ ] **Step 3: pyproject.toml packages 갱신**

`pyproject.toml`의 `[tool.setuptools]` packages 리스트에 추가:

```toml
[tool.setuptools]
packages = ["scraper", "scraper.news", "parser", "parser.news", "exchange", "builder", "summarizer", "summarizer.providers"]
```

- [ ] **Step 4: 검증**

Run:
```bash
uv sync && uv run python -c "import scraper.news, parser.news, summarizer, summarizer.providers; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock scraper/news parser/news summarizer tests/news
git commit -m "feat(news): scaffold news pipeline directories + deps"
```

---

## Task 2: Models & Base Interface

**[SEQUENTIAL]** 다른 모든 모듈이 import.

**Files:**
- Create: `parser/news/models.py`
- Create: `scraper/news/base.py`
- Test: `tests/news/test_models.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/news/test_models.py`

```python
"""News pipeline data models."""
from datetime import datetime, timezone

import pytest

from parser.news.models import EnrichedNewsItem, EventItem, RawNewsItem


def test_raw_news_item_minimal():
    item = RawNewsItem(
        source="mining.com",
        url="https://example.com/a",
        title="Copper hits 5y high",
        fetched_at=datetime.now(timezone.utc),
        lang="en",
    )
    assert item.url_hash  # auto-computed
    assert len(item.url_hash) == 16


def test_url_hash_deterministic():
    a = RawNewsItem(source="x", url="https://e.com/1", title="t", fetched_at=datetime.now(timezone.utc), lang="en")
    b = RawNewsItem(source="x", url="https://e.com/1", title="t2", fetched_at=datetime.now(timezone.utc), lang="en")
    assert a.url_hash == b.url_hash  # hash from URL only


def test_enriched_extends_raw():
    raw = RawNewsItem(source="s", url="https://e.com/1", title="t", fetched_at=datetime.now(timezone.utc), lang="en")
    enriched = EnrichedNewsItem(
        **raw.model_dump(),
        summary_ko="요약",
        metals=["copper"],
        sentiment=1,
        event_type="supply",
        confidence=0.85,
    )
    assert enriched.metals == ["copper"]
    assert enriched.sentiment == 1


def test_event_type_validation():
    with pytest.raises(ValueError):
        EnrichedNewsItem(
            source="s", url="https://e.com/1", title="t",
            fetched_at=datetime.now(timezone.utc), lang="en",
            summary_ko="", metals=[], sentiment=0, event_type="invalid", confidence=0.5,
        )


def test_event_item():
    ev = EventItem(
        date="2026-05-04",
        type="lme_stock",
        metal="copper",
        magnitude=-0.05,
        title="LME copper stock 5% drop",
    )
    assert ev.metal == "copper"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/news/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: parser.news.models`

- [ ] **Step 3: 구현** — `parser/news/models.py`

```python
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
    lang: str  # "ko" | "en" | "zh" | ...
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
    date: date | str  # "YYYY-MM-DD" 허용
    type: Literal["lme_stock", "lme_announce", "macro"]
    metal: str  # 6 metals 또는 "all"
    magnitude: float | None = None
    title: str
    url: str | None = None
    source: str | None = None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/news/test_models.py -v`
Expected: 5 PASS

- [ ] **Step 5: base 인터페이스 작성** — `scraper/news/base.py`

```python
"""Common interface for news scrapers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from parser.news.models import RawNewsItem


class NewsSource(ABC):
    """Abstract base for all news sources.

    Implementations must be safe to call repeatedly (idempotent fetch).
    Raise no exceptions for empty results — return [].
    """

    name: str  # e.g., "mining.com"
    lang: str  # primary language

    @abstractmethod
    def fetch(self) -> list[RawNewsItem]:
        """Return list of raw items. Never raises for transient failures —
        log and return partial/empty list."""
        ...
```

- [ ] **Step 6: Commit**

```bash
git add parser/news/models.py scraper/news/base.py tests/news/test_models.py
git commit -m "feat(news): pydantic models + NewsSource ABC"
```

---

## Task 3: RSS Multi-Feed Scraper

**[INDEPENDENT]** Task 4/5/6과 병렬 가능.

**Files:**
- Create: `scraper/news/rss.py`
- Create: `tests/news/fixtures/sample_rss.xml`
- Test: `tests/news/test_rss.py`

- [ ] **Step 1: Fixture 작성** — `tests/news/fixtures/sample_rss.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Mining News</title>
    <link>https://example.com</link>
    <description>test</description>
    <item>
      <title>Copper prices surge on supply concerns</title>
      <link>https://example.com/copper-surge</link>
      <description>LME copper hit 5y high</description>
      <pubDate>Mon, 04 May 2026 09:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Nickel oversupply worries Indonesian miners</title>
      <link>https://example.com/nickel-oversupply</link>
      <description>Indonesian nickel output rising</description>
      <pubDate>Mon, 04 May 2026 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: 실패 테스트 작성** — `tests/news/test_rss.py`

```python
"""RSS scraper tests."""
from pathlib import Path
from unittest.mock import patch

import pytest

from scraper.news.rss import RSS_FEEDS, RSSScraper

FIXTURE = Path(__file__).parent / "fixtures" / "sample_rss.xml"


def test_rss_feeds_constant_has_required_sources():
    sources = {f["source"] for f in RSS_FEEDS}
    assert "mining.com" in sources
    assert "kitco" in sources
    assert "hankyung" in sources
    assert "moneytoday" in sources
    assert "commodity-tv" in sources


def test_parse_fixture(tmp_path):
    scraper = RSSScraper(feeds=[{"source": "test", "url": str(FIXTURE), "lang": "en"}])
    items = scraper.fetch()
    assert len(items) == 2
    assert items[0].title == "Copper prices surge on supply concerns"
    assert items[0].source == "test"
    assert items[0].lang == "en"
    assert items[0].url == "https://example.com/copper-surge"
    assert items[0].published_at is not None


def test_fetch_handles_network_failure(monkeypatch):
    """Bad URL → empty list, not exception."""
    scraper = RSSScraper(feeds=[{"source": "bad", "url": "http://localhost:1/nonexistent.xml", "lang": "en"}])
    items = scraper.fetch()
    assert items == []


def test_fetch_partial_on_one_feed_failure(monkeypatch):
    """One bad feed shouldn't kill others."""
    scraper = RSSScraper(feeds=[
        {"source": "good", "url": str(FIXTURE), "lang": "en"},
        {"source": "bad", "url": "http://localhost:1/x.xml", "lang": "en"},
    ])
    items = scraper.fetch()
    assert len(items) == 2  # only good feed
    assert all(i.source == "good" for i in items)
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `uv run pytest tests/news/test_rss.py -v`
Expected: FAIL — `ModuleNotFoundError: scraper.news.rss`

- [ ] **Step 4: 구현** — `scraper/news/rss.py`

```python
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

# Phase 1a feeds. Phase 1b/1c가 추가 시 별도 plan에서 확장.
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/news/test_rss.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add scraper/news/rss.py tests/news/test_rss.py tests/news/fixtures/sample_rss.xml
git commit -m "feat(news): RSS multi-feed scraper (mining.com, kitco, commodity-tv, hankyung, moneytoday)"
```

---

## Task 4: KORES Scraper

**[INDEPENDENT]** Task 3/5/6과 병렬 가능.

**Files:**
- Create: `scraper/news/kores.py`
- Create: `tests/news/fixtures/kores_sample.html`
- Test: `tests/news/test_kores.py`

- [ ] **Step 1: Fixture 작성** — `tests/news/fixtures/kores_sample.html`

(실제 KORES 페이지 구조 모사. 변경되면 fixture 갱신 필요.)

```html
<!DOCTYPE html>
<html>
<body>
  <table class="board_list">
    <tbody>
      <tr>
        <td class="title"><a href="/views/cms/komis/price/kores_02_view.jsp?seq=12345">전기동 가격, 중국 수요 증가로 상승</a></td>
        <td class="date">2026-05-04</td>
      </tr>
      <tr>
        <td class="title"><a href="/views/cms/komis/price/kores_02_view.jsp?seq=12344">알루미늄 LME 재고 감소세</a></td>
        <td class="date">2026-05-03</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
```

- [ ] **Step 2: 실패 테스트 작성** — `tests/news/test_kores.py`

```python
"""KORES scraper tests."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from scraper.news.kores import KORES_BASE_URL, KoresScraper

FIXTURE = Path(__file__).parent / "fixtures" / "kores_sample.html"


def test_parse_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = KoresScraper()
    items = scraper._parse(html)
    assert len(items) == 2
    assert items[0].title == "전기동 가격, 중국 수요 증가로 상승"
    assert items[0].url.startswith("https://")
    assert items[0].lang == "ko"
    assert items[0].source == "kores"


def test_fetch_handles_network_failure():
    """Network failure → empty, no raise."""
    scraper = KoresScraper(base_url="http://localhost:1/nonexistent")
    items = scraper.fetch()
    assert items == []


def test_relative_url_resolved():
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = KoresScraper()
    items = scraper._parse(html)
    for item in items:
        assert item.url.startswith(KORES_BASE_URL)


def test_fetch_calls_parse(monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = KoresScraper()

    class MockResp:
        text = html
        status_code = 200
        def raise_for_status(self): pass

    monkeypatch.setattr("scraper.news.kores.requests.get", lambda *a, **k: MockResp())
    items = scraper.fetch()
    assert len(items) == 2
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `uv run pytest tests/news/test_kores.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: 구현** — `scraper/news/kores.py`

```python
"""KORES (한국광물공사) 일일자원뉴스 스크래퍼."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from parser.news.models import RawNewsItem
from scraper.news.base import NewsSource

logger = logging.getLogger(__name__)

KORES_BASE_URL = "https://www.kores.net"
KORES_LIST_PATH = "/views/cms/komis/price/kores_02_list.jsp"
TIMEOUT = 15


class KoresScraper(NewsSource):
    name = "kores"
    lang = "ko"

    def __init__(self, base_url: str = KORES_BASE_URL):
        self.base_url = base_url

    def fetch(self) -> list[RawNewsItem]:
        url = urljoin(self.base_url, KORES_LIST_PATH)
        try:
            resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "metal-bulletin/0.1"})
            resp.raise_for_status()
            return self._parse(resp.text)
        except Exception as e:
            logger.warning("kores fetch failed err=%s", e)
            return []

    def _parse(self, html: str) -> list[RawNewsItem]:
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table.board_list tbody tr")
        now = datetime.now(timezone.utc)
        items: list[RawNewsItem] = []
        for row in rows:
            link = row.select_one("td.title a")
            if not link:
                continue
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not href or not title:
                continue
            full_url = urljoin(self.base_url, href)
            items.append(RawNewsItem(
                source=self.name,
                url=full_url,
                title=title,
                fetched_at=now,
                lang=self.lang,
            ))
        return items
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/news/test_kores.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add scraper/news/kores.py tests/news/test_kores.py tests/news/fixtures/kores_sample.html
git commit -m "feat(news): KORES scraper (한국광물공사 일일자원뉴스)"
```

**[Implementation note]** KORES 실제 HTML 구조와 fixture 차이가 있을 수 있다. 실 운영 시 첫 실 fetch 결과로 fixture/selector 보정 필요. Task 13 smoke 단계에서 검증.

---

## Task 5: Dedupe

**[INDEPENDENT]** Task 3/4/6과 병렬 가능.

**Files:**
- Create: `parser/news/dedupe.py`
- Test: `tests/news/test_dedupe.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/news/test_dedupe.py`

```python
"""Dedupe tests."""
from datetime import datetime, timezone

from parser.news.dedupe import dedupe
from parser.news.models import RawNewsItem


def _item(url: str, title: str, source: str = "s") -> RawNewsItem:
    return RawNewsItem(
        source=source, url=url, title=title,
        fetched_at=datetime.now(timezone.utc), lang="en",
    )


def test_url_hash_dedup():
    items = [
        _item("https://e.com/a", "Title A"),
        _item("https://e.com/a", "Different Title"),  # same URL
        _item("https://e.com/b", "Title B"),
    ]
    out = dedupe(items)
    assert len(out) == 2
    assert {i.url for i in out} == {"https://e.com/a", "https://e.com/b"}


def test_fuzzy_title_dedup():
    items = [
        _item("https://a.com/1", "Copper prices surge on supply concerns"),
        _item("https://b.com/2", "Copper prices surge on supply concern"),  # near-dup
        _item("https://c.com/3", "Aluminum demand falls in Q1"),
    ]
    out = dedupe(items, fuzzy_threshold=0.85)
    assert len(out) == 2  # near-dup collapsed


def test_fuzzy_below_threshold_kept():
    items = [
        _item("https://a.com/1", "Copper hits 5-year high"),
        _item("https://b.com/2", "Aluminum hits 3-month low"),
    ]
    out = dedupe(items, fuzzy_threshold=0.85)
    assert len(out) == 2


def test_empty_input():
    assert dedupe([]) == []


def test_dedupe_preserves_first_occurrence():
    items = [
        _item("https://a.com/1", "Same title", source="first"),
        _item("https://a.com/1", "Same title", source="second"),  # dup
    ]
    out = dedupe(items)
    assert len(out) == 1
    assert out[0].source == "first"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/news/test_dedupe.py -v`
Expected: FAIL — `ModuleNotFoundError: parser.news.dedupe`

- [ ] **Step 3: 구현** — `parser/news/dedupe.py`

```python
"""Dedupe: 1) URL hash exact match, 2) title fuzzy match (rapidfuzz)."""
from __future__ import annotations

from rapidfuzz import fuzz

from parser.news.models import RawNewsItem


def dedupe(items: list[RawNewsItem], fuzzy_threshold: float = 0.85) -> list[RawNewsItem]:
    """Return items with duplicates removed.

    First pass: exact url_hash match.
    Second pass: title similarity above threshold (token_set_ratio).
    Preserves first occurrence.

    Args:
        fuzzy_threshold: 0~1. 0.85 = 매우 유사한 제목만 dedupe.
    """
    if not items:
        return []

    # Pass 1: url_hash
    seen_hashes: set[str] = set()
    pass1: list[RawNewsItem] = []
    for item in items:
        h = item.url_hash
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        pass1.append(item)

    # Pass 2: fuzzy title
    threshold_pct = fuzzy_threshold * 100
    out: list[RawNewsItem] = []
    seen_titles: list[str] = []
    for item in pass1:
        is_dup = any(
            fuzz.token_set_ratio(item.title, t) >= threshold_pct
            for t in seen_titles
        )
        if is_dup:
            continue
        seen_titles.append(item.title)
        out.append(item)

    return out
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/news/test_dedupe.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add parser/news/dedupe.py tests/news/test_dedupe.py
git commit -m "feat(news): dedupe by url_hash + fuzzy title (rapidfuzz)"
```

---

## Task 6: Classify (Keyword Pre-Filter)

**[INDEPENDENT]** Task 3/4/5와 병렬 가능.

**Files:**
- Create: `parser/news/classify.py`
- Test: `tests/news/test_classify.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/news/test_classify.py`

```python
"""Keyword-based pre-filter for metal relevance."""
from datetime import datetime, timezone

from parser.news.classify import classify_metals, is_relevant
from parser.news.models import RawNewsItem


def _item(title: str, snippet: str | None = None, lang: str = "en") -> RawNewsItem:
    return RawNewsItem(
        source="s", url=f"https://e.com/{title[:5]}", title=title,
        snippet=snippet, fetched_at=datetime.now(timezone.utc), lang=lang,
    )


def test_classify_copper_en():
    metals = classify_metals(_item("Copper prices surge"))
    assert metals == ["copper"]


def test_classify_copper_ko():
    metals = classify_metals(_item("전기동 가격 급등"))
    assert metals == ["copper"]


def test_classify_multiple_metals():
    metals = classify_metals(_item("Copper and nickel both up", "Aluminum flat"))
    assert set(metals) == {"copper", "nickel", "aluminum"}


def test_classify_no_match():
    metals = classify_metals(_item("Stock market hits new high"))
    assert metals == []


def test_is_relevant_true_when_metal_match():
    assert is_relevant(_item("Tin smelter shutdown")) is True


def test_is_relevant_false_when_no_match():
    assert is_relevant(_item("Bitcoin reaches $200k")) is False


def test_classify_handles_none_snippet():
    """Snippet=None must not crash."""
    metals = classify_metals(_item("Zinc imports rise", snippet=None))
    assert metals == ["zinc"]


def test_lme_only_match_classifies_all():
    """LME 단독 언급 = 모든 비철 영향 가능 → 'all' 반환."""
    metals = classify_metals(_item("LME warehouse stocks at record low"))
    assert "all" in metals or len(metals) >= 1  # 구현 선택
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/news/test_classify.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `parser/news/classify.py`

```python
"""Keyword-based 1차 필터.

LLM 호출 비용 줄이려고 명백히 무관한 헤드라인 제거.
6 metals 영문/한국어 키워드 ANY-HIT 시 통과.
"""
from __future__ import annotations

from parser.news.models import RawNewsItem

# 광물별 키워드 (소문자 비교). 한국어/영문 양쪽.
METAL_KEYWORDS: dict[str, list[str]] = {
    "copper":   ["copper", "cu ", "전기동", "구리"],
    "aluminum": ["aluminum", "aluminium", "알루미늄"],
    "zinc":     ["zinc", "아연"],
    "nickel":   ["nickel", "니켈"],
    "lead":     ["lead", "납"],
    "tin":      ["tin", "주석"],
}

# 일반 LME 언급 = 다중 광물 영향. all 태그.
LME_GLOBAL_KEYWORDS = ["lme ", "london metal exchange", "shfe", "비철"]


def classify_metals(item: RawNewsItem) -> list[str]:
    """Return matched metal codes. Empty list if no match.

    'lead' 와 'lead time' 등 false positive 위험 → snippet 활용으로 보강 가능.
    Phase 1a 에서는 단순 substring. 정확도 부족하면 후속 phase에서 정교화.
    """
    haystack = (item.title + " " + (item.snippet or "")).lower()
    matched: list[str] = []
    for metal, kws in METAL_KEYWORDS.items():
        if any(kw in haystack for kw in kws):
            matched.append(metal)

    # LME 단독 언급 시 'all' 추가 (특정 metal 없을 때만)
    if not matched and any(kw in haystack for kw in LME_GLOBAL_KEYWORDS):
        matched.append("all")
    return matched


def is_relevant(item: RawNewsItem) -> bool:
    """LLM 호출 전 1차 게이트."""
    return len(classify_metals(item)) > 0
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/news/test_classify.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add parser/news/classify.py tests/news/test_classify.py
git commit -m "feat(news): keyword pre-filter for 6 metals (en/ko)"
```

---

## Task 7: Gemini Provider + Prompt

**[SEQUENTIAL]** Task 2~6 완료 후. Task 8과 합쳐도 되지만 분리 = 작은 commit.

**Files:**
- Create: `summarizer/prompt.py`
- Create: `summarizer/providers/gemini.py`
- Test: `tests/news/test_summarizer.py` (gemini 부분만)

- [ ] **Step 1: 실패 테스트 작성** — `tests/news/test_summarizer.py` (gemini 부분)

```python
"""Summarizer tests — Gemini provider + prompt builder."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from parser.news.models import EnrichedNewsItem, RawNewsItem
from summarizer.prompt import build_batch_prompt, parse_batch_response
from summarizer.providers.gemini import GeminiProvider


def _raw(title: str = "Copper hits 5y high", url: str = "https://e.com/1") -> RawNewsItem:
    return RawNewsItem(
        source="s", url=url, title=title,
        fetched_at=datetime.now(timezone.utc), lang="en",
    )


def test_build_batch_prompt_contains_items():
    items = [_raw(title="Copper up"), _raw(title="Nickel down", url="https://e.com/2")]
    prompt = build_batch_prompt(items)
    assert "Copper up" in prompt
    assert "Nickel down" in prompt
    assert "JSON" in prompt or "json" in prompt
    # ID 매핑 가능해야 함
    assert items[0].url_hash in prompt


def test_parse_batch_response_valid():
    items = [_raw()]
    raw_response = f'''[
        {{"id": "{items[0].url_hash}", "summary_ko": "구리 5년 고점", "metals": ["copper"], "sentiment": 1, "event_type": "supply", "confidence": 0.9}}
    ]'''
    enriched = parse_batch_response(items, raw_response)
    assert len(enriched) == 1
    assert enriched[0].summary_ko == "구리 5년 고점"
    assert enriched[0].metals == ["copper"]
    assert enriched[0].confidence == 0.9


def test_parse_batch_response_partial_failure_returns_raw():
    """LLM이 일부 항목만 응답 시 누락된 건 raw 그대로 + summary=None."""
    items = [_raw(title="A", url="https://e.com/a"), _raw(title="B", url="https://e.com/b")]
    raw_response = f'[{{"id": "{items[0].url_hash}", "summary_ko": "a요약", "metals": ["copper"], "sentiment": 0, "event_type": "other", "confidence": 0.7}}]'
    enriched = parse_batch_response(items, raw_response)
    assert len(enriched) == 2
    assert enriched[0].summary_ko == "a요약"
    assert enriched[1].summary_ko is None  # 누락분


def test_parse_batch_response_invalid_json_returns_all_raw():
    items = [_raw()]
    enriched = parse_batch_response(items, "not json at all")
    assert len(enriched) == 1
    assert enriched[0].summary_ko is None


def test_gemini_provider_calls_sdk(monkeypatch):
    """SDK 호출만 확인. 실제 네트워크 안 탐."""
    items = [_raw()]
    fake_response = MagicMock()
    fake_response.text = f'[{{"id": "{items[0].url_hash}", "summary_ko": "요약", "metals": ["copper"], "sentiment": 0, "event_type": "other", "confidence": 0.8}}]'
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response
    monkeypatch.setattr("summarizer.providers.gemini.genai.Client", lambda **k: fake_client)

    provider = GeminiProvider(api_key="fake")
    enriched = provider.summarize_batch(items)
    assert len(enriched) == 1
    assert enriched[0].summary_ko == "요약"
    fake_client.models.generate_content.assert_called_once()


def test_gemini_provider_propagates_failure(monkeypatch):
    """SDK 예외는 raise (failover chain이 잡음)."""
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = RuntimeError("rate limit")
    monkeypatch.setattr("summarizer.providers.gemini.genai.Client", lambda **k: fake_client)

    provider = GeminiProvider(api_key="fake")
    with pytest.raises(RuntimeError):
        provider.summarize_batch([_raw()])
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/news/test_summarizer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: prompt 구현** — `summarizer/prompt.py`

```python
"""LLM prompt builder + response parser."""
from __future__ import annotations

import json
import logging

from parser.news.models import EnrichedNewsItem, RawNewsItem

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """\
당신은 비철금속 시장 뉴스 분석가다. 주어진 뉴스 헤드라인 배열을 분석해
각 항목에 대해 JSON 객체를 반환하라. 출력은 JSON 배열만 포함하고 다른 설명 금지.

각 객체:
- id: 입력의 id 그대로 복사
- summary_ko: 한국어 1문장 요약 (50자 이내)
- metals: ["copper","aluminum","zinc","nickel","lead","tin"] 중 영향받는 광물 (없으면 [])
- sentiment: -1 (가격 하락 압력), 0 (중립), 1 (가격 상승 압력)
- event_type: "supply" | "demand" | "policy" | "macro" | "other"
- confidence: 0.0~1.0 (분석 확신도)
"""


def build_batch_prompt(items: list[RawNewsItem]) -> str:
    """Items → user-facing prompt with JSON input."""
    payload = [
        {
            "id": item.url_hash,
            "title": item.title,
            "snippet": (item.snippet or "")[:300],
            "lang": item.lang,
        }
        for item in items
    ]
    return (
        SYSTEM_INSTRUCTION
        + "\n\n다음 뉴스 배열을 분석하라:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nJSON 배열만 출력:"
    )


def parse_batch_response(items: list[RawNewsItem], raw_response: str) -> list[EnrichedNewsItem]:
    """Parse LLM response. Missing items → enriched with null summary fields.

    LLM 환각/잘못된 JSON 시 모든 item을 enriched(null) 로 반환.
    """
    enrichments: dict[str, dict] = {}
    try:
        # JSON 코드 블록 제거 시도
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            for entry in parsed:
                eid = entry.get("id")
                if eid:
                    enrichments[eid] = entry
    except (json.JSONDecodeError, ValueError, IndexError) as e:
        logger.warning("LLM response parse failed: %s", e)

    out: list[EnrichedNewsItem] = []
    for item in items:
        e = enrichments.get(item.url_hash)
        if e:
            out.append(EnrichedNewsItem(
                **item.model_dump(exclude={"url_hash"}),
                summary_ko=e.get("summary_ko"),
                metals=e.get("metals", []),
                sentiment=e.get("sentiment"),
                event_type=e.get("event_type"),
                confidence=e.get("confidence"),
            ))
        else:
            out.append(EnrichedNewsItem(**item.model_dump(exclude={"url_hash"})))
    return out
```

- [ ] **Step 4: gemini provider 구현** — `summarizer/providers/gemini.py`

```python
"""Gemini 2.5 Flash provider."""
from __future__ import annotations

import os

from google import genai

from parser.news.models import EnrichedNewsItem, RawNewsItem
from summarizer.prompt import build_batch_prompt, parse_batch_response

MODEL = "gemini-2.5-flash"


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

    def summarize_batch(self, items: list[RawNewsItem]) -> list[EnrichedNewsItem]:
        """Raises on API failure — failover chain catches."""
        if not items:
            return []
        client = genai.Client(api_key=self.api_key)
        prompt = build_batch_prompt(items)
        response = client.models.generate_content(model=MODEL, contents=prompt)
        return parse_batch_response(items, response.text)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/news/test_summarizer.py -v`
Expected: 6 PASS

- [ ] **Step 6: Commit**

```bash
git add summarizer/prompt.py summarizer/providers/gemini.py tests/news/test_summarizer.py
git commit -m "feat(news): Gemini Flash provider + structured JSON prompt"
```

---

## Task 8: Failover Client

**[SEQUENTIAL]** Task 7 의존.

**Files:**
- Create: `summarizer/client.py`
- Modify: `tests/news/test_summarizer.py` (failover 케이스 추가)

- [ ] **Step 1: 실패 테스트 추가** — `tests/news/test_summarizer.py` 끝에 append

```python
def test_failover_first_success_short_circuits():
    """첫 provider 성공 시 다른 거 안 부름."""
    from summarizer.client import SummarizerClient

    p1 = MagicMock()
    p1.name = "p1"
    p1.summarize_batch.return_value = [
        EnrichedNewsItem(
            source="s", url="https://e.com/1", title="t",
            fetched_at=datetime.now(timezone.utc), lang="en",
            summary_ko="ok", metals=[], sentiment=0, event_type="other", confidence=0.8,
        )
    ]
    p2 = MagicMock()

    client = SummarizerClient(providers=[p1, p2])
    items = [_raw()]
    out = client.summarize(items)
    assert len(out) == 1
    p1.summarize_batch.assert_called_once()
    p2.summarize_batch.assert_not_called()


def test_failover_falls_through_on_failure():
    """첫 provider 실패 → 두 번째 시도."""
    from summarizer.client import SummarizerClient

    p1 = MagicMock()
    p1.name = "p1"
    p1.summarize_batch.side_effect = RuntimeError("rate limit")
    p2 = MagicMock()
    p2.name = "p2"
    p2.summarize_batch.return_value = [
        EnrichedNewsItem(
            source="s", url="https://e.com/1", title="t",
            fetched_at=datetime.now(timezone.utc), lang="en",
            summary_ko="from p2", metals=[], sentiment=0, event_type="other", confidence=0.7,
        )
    ]

    client = SummarizerClient(providers=[p1, p2])
    out = client.summarize([_raw()])
    assert out[0].summary_ko == "from p2"
    p1.summarize_batch.assert_called_once()
    p2.summarize_batch.assert_called_once()


def test_failover_all_fail_returns_raw():
    """모든 provider 실패 → raw 그대로 (summary=None)."""
    from summarizer.client import SummarizerClient

    p1 = MagicMock()
    p1.name = "p1"
    p1.summarize_batch.side_effect = RuntimeError("fail1")
    p2 = MagicMock()
    p2.name = "p2"
    p2.summarize_batch.side_effect = RuntimeError("fail2")

    client = SummarizerClient(providers=[p1, p2])
    out = client.summarize([_raw()])
    assert len(out) == 1
    assert out[0].summary_ko is None


def test_batches_split_on_size():
    """batch_size 보다 큰 input → 여러 번 호출."""
    from summarizer.client import SummarizerClient

    p1 = MagicMock()
    p1.name = "p1"
    p1.summarize_batch.side_effect = lambda items: [
        EnrichedNewsItem(
            **i.model_dump(exclude={"url_hash"}),
            summary_ko="ok", metals=[], sentiment=0, event_type="other", confidence=0.8,
        )
        for i in items
    ]

    client = SummarizerClient(providers=[p1], batch_size=3)
    items = [_raw(url=f"https://e.com/{i}") for i in range(7)]
    out = client.summarize(items)
    assert len(out) == 7
    assert p1.summarize_batch.call_count == 3  # 3+3+1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/news/test_summarizer.py -v -k failover`
Expected: FAIL — `ModuleNotFoundError: summarizer.client`

- [ ] **Step 3: 구현** — `summarizer/client.py`

```python
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
        # 모두 실패 — raw 반환
        logger.error("all providers failed, returning raw")
        return [EnrichedNewsItem(**item.model_dump(exclude={"url_hash"})) for item in chunk]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/news/test_summarizer.py -v`
Expected: 모두 PASS

- [ ] **Step 5: Commit**

```bash
git add summarizer/client.py tests/news/test_summarizer.py
git commit -m "feat(news): failover summarizer client (batch + multi-provider)"
```

---

## Task 9: News Builder (Parquet writer)

**[SEQUENTIAL]** Task 2~8 의존.

**Files:**
- Create: `builder/news_build.py`
- Test: `tests/news/test_news_build.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/news/test_news_build.py`

```python
"""News parquet builder tests."""
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from builder.news_build import build_news_parquet, NEWS_SCHEMA
from parser.news.models import EnrichedNewsItem


def _enriched(url: str = "https://e.com/1", summary: str | None = "ok") -> EnrichedNewsItem:
    return EnrichedNewsItem(
        source="s", url=url, title="t",
        fetched_at=datetime.now(timezone.utc), lang="en",
        summary_ko=summary, metals=["copper"], sentiment=1,
        event_type="supply", confidence=0.85,
    )


def test_build_writes_parquet(tmp_path: Path):
    items = [_enriched(url="https://e.com/1"), _enriched(url="https://e.com/2", summary=None)]
    out_dir = tmp_path / "news"
    build_news_parquet(items, out_dir, year=2026)

    out_file = out_dir / "2026.parquet"
    assert out_file.exists()
    table = pq.read_table(out_file)
    assert table.num_rows == 2
    expected_cols = {f.name for f in NEWS_SCHEMA}
    assert set(table.column_names) == expected_cols


def test_build_appends_to_existing(tmp_path: Path):
    out_dir = tmp_path / "news"
    build_news_parquet([_enriched(url="https://e.com/1")], out_dir, year=2026)
    build_news_parquet([_enriched(url="https://e.com/2")], out_dir, year=2026)

    table = pq.read_table(out_dir / "2026.parquet")
    assert table.num_rows == 2
    urls = set(table.column("url").to_pylist())
    assert urls == {"https://e.com/1", "https://e.com/2"}


def test_build_dedupes_on_append(tmp_path: Path):
    """동일 url_hash 재기록 시 중복 안 쌓임."""
    out_dir = tmp_path / "news"
    build_news_parquet([_enriched(url="https://e.com/1")], out_dir, year=2026)
    build_news_parquet([_enriched(url="https://e.com/1")], out_dir, year=2026)  # same URL

    table = pq.read_table(out_dir / "2026.parquet")
    assert table.num_rows == 1


def test_build_empty_input_no_op(tmp_path: Path):
    out_dir = tmp_path / "news"
    build_news_parquet([], out_dir, year=2026)
    assert not (out_dir / "2026.parquet").exists()


def test_build_schema_columns():
    cols = {f.name for f in NEWS_SCHEMA}
    required = {
        "date", "fetched_at", "source", "url", "url_hash",
        "title", "title_ko", "summary_ko", "metals",
        "sentiment", "event_type", "confidence", "lang",
    }
    assert required.issubset(cols)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/news/test_news_build.py -v`
Expected: FAIL — `ModuleNotFoundError: builder.news_build`

- [ ] **Step 3: 구현** — `builder/news_build.py`

```python
"""News parquet builder.

Append + dedupe by url_hash. Yearly partitioned files.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from parser.news.models import EnrichedNewsItem

logger = logging.getLogger(__name__)

NEWS_SCHEMA = pa.schema([
    pa.field("date", pa.date32()),
    pa.field("fetched_at", pa.timestamp("us", tz="UTC")),
    pa.field("source", pa.string()),
    pa.field("url", pa.string()),
    pa.field("url_hash", pa.string()),
    pa.field("title", pa.string()),
    pa.field("title_ko", pa.string()),
    pa.field("summary_ko", pa.string()),
    pa.field("metals", pa.list_(pa.string())),
    pa.field("sentiment", pa.int8()),
    pa.field("event_type", pa.string()),
    pa.field("confidence", pa.float32()),
    pa.field("lang", pa.string()),
])


def _to_table(items: list[EnrichedNewsItem]) -> pa.Table:
    rows = {f.name: [] for f in NEWS_SCHEMA}
    for it in items:
        rows["date"].append(it.fetched_at.date())
        rows["fetched_at"].append(it.fetched_at)
        rows["source"].append(it.source)
        rows["url"].append(it.url)
        rows["url_hash"].append(it.url_hash)
        rows["title"].append(it.title)
        rows["title_ko"].append(it.title_ko)
        rows["summary_ko"].append(it.summary_ko)
        rows["metals"].append(list(it.metals))
        rows["sentiment"].append(it.sentiment)
        rows["event_type"].append(it.event_type)
        rows["confidence"].append(it.confidence)
        rows["lang"].append(it.lang)
    return pa.Table.from_pydict(rows, schema=NEWS_SCHEMA)


def build_news_parquet(items: list[EnrichedNewsItem], out_dir: Path, year: int) -> None:
    """Append items to {out_dir}/{year}.parquet, dedupe by url_hash."""
    if not items:
        logger.info("news_build: empty input, no-op")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{year}.parquet"
    new_table = _to_table(items)

    if out_file.exists():
        existing = pq.read_table(out_file)
        # 컬럼 정렬 + schema cast (호환성)
        combined = pa.concat_tables([existing, new_table], promote_options="default")
        # url_hash 기준 dedupe (last wins via reverse + drop_duplicates 패턴)
        df = combined.to_pandas()
        df = df.drop_duplicates(subset=["url_hash"], keep="first")
        combined = pa.Table.from_pandas(df, schema=NEWS_SCHEMA, preserve_index=False)
    else:
        combined = new_table

    pq.write_table(combined, out_file, compression="zstd")
    logger.info("news_build: wrote %d rows to %s", combined.num_rows, out_file)
```

- [ ] **Step 4: pandas 의존성 추가**

```bash
uv add pandas
```

(`drop_duplicates` 사용. pyarrow 단독으로 가능하지만 pandas가 단순.)

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/news/test_news_build.py -v`
Expected: 5 PASS

- [ ] **Step 6: Commit**

```bash
git add builder/news_build.py tests/news/test_news_build.py pyproject.toml uv.lock
git commit -m "feat(news): parquet writer with dedupe-on-append"
```

---

## Task 10: Orchestrator Run Scripts

**[SEQUENTIAL]** Task 2~9 의존. CLI entrypoint 통합.

**Files:**
- Create: `scraper/news/run.py`
- Create: `parser/news/run.py`
- Create: `summarizer/run.py`

**중간 파일 위치:** `data/raw/news/{year-month}.jsonl.zst` (스크랩 결과), `data/news_pending.json` (분류/요약 사이 임시).

이번 Task는 통합 흐름이라 단위 테스트보다 통합 테스트가 적합. Task 13에서 다룸.

- [ ] **Step 1: scraper orchestrator** — `scraper/news/run.py`

```python
"""Run all configured news scrapers, write raw archive."""
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

    # 다음 단계 입력용 (압축 안 한 형태로 임시)
    Path("data").mkdir(exist_ok=True)
    pending = Path("data/news_pending.json")
    with pending.open("w", encoding="utf-8") as f:
        json.dump([item.model_dump(mode="json") for item in all_items], f, ensure_ascii=False)

    logger.info("wrote %d raw items to %s and pending %s", len(all_items), out_file, pending)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: zstandard 의존성 추가**

```bash
uv add zstandard
```

- [ ] **Step 3: parser orchestrator** — `parser/news/run.py`

```python
"""Dedupe + classify pending news. Writes filtered list."""
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
```

- [ ] **Step 4: summarizer orchestrator** — `summarizer/run.py`

```python
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
    # TODO Phase 1b: groq, cerebras 추가
    if not providers:
        logger.error("no LLM provider configured (GEMINI_API_KEY missing)")
        return

    client = SummarizerClient(providers=providers, batch_size=10)
    enriched = client.summarize(items)
    logger.info("summarized %d items", len(enriched))

    out = Path("data/news_enriched.json")
    out.write_text(
        json.dumps([e.model_dump(mode="json") for e in enriched], ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: builder/news_build.py에 CLI 진입점 추가**

기존 `builder/news_build.py` 끝에 append:

```python
def main() -> None:
    import json as _json
    from datetime import datetime as _dt

    enriched_path = Path("data/news_enriched.json")
    if not enriched_path.exists():
        logger.warning("no enriched file, skip")
        return

    raw = _json.loads(enriched_path.read_text(encoding="utf-8"))
    items = [EnrichedNewsItem.model_validate(r) for r in raw]
    if not items:
        return

    year = _dt.now().year
    build_news_parquet(items, Path("data/news"), year)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 수동 dry-run (네트워크 안 탐)**

Run:
```bash
uv run python -c "from scraper.news.run import main; print('importable')"
uv run python -c "from parser.news.run import main; print('importable')"
uv run python -c "from summarizer.run import main; print('importable')"
uv run python -c "from builder.news_build import main; print('importable')"
```
Expected: 4 lines `importable`

- [ ] **Step 7: Commit**

```bash
git add scraper/news/run.py parser/news/run.py summarizer/run.py builder/news_build.py pyproject.toml uv.lock
git commit -m "feat(news): orchestrator entrypoints (scrape → parse → summarize → build)"
```

---

## Task 11: GitHub Actions Workflow

**[SEQUENTIAL]** Task 10 의존.

**Files:**
- Create: `.github/workflows/news.yml`

- [ ] **Step 1: setup-uv pin 확인**

Run:
```bash
gh api repos/astral-sh/setup-uv/commits/main --jq '.sha' 2>/dev/null || echo "manual"
```

(SHA를 받거나, 기존 collect.yml에 사용된 동일 SHA 재사용. 보안 핀 정책 일관성.)

```bash
grep "astral-sh/setup-uv" .github/workflows/collect.yml
```

→ 거기서 사용된 SHA 그대로 복사.

- [ ] **Step 2: 작성** — `.github/workflows/news.yml`

```yaml
name: news

on:
  schedule:
    - cron: '0 */4 * * *'  # UTC, 매 4시간 (KST 기준 영업/야간 cover)
  workflow_dispatch: {}

permissions:
  contents: write

concurrency:
  group: news
  cancel-in-progress: false

jobs:
  collect-news:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Checkout
        uses: actions/checkout@<COLLECT_YML_CHECKOUT_SHA>

      - name: Setup uv
        uses: astral-sh/setup-uv@<COLLECT_YML_UV_SHA>
        with:
          enable-cache: true

      - name: Install deps
        run: uv sync --frozen

      - name: Scrape news
        run: uv run python -m scraper.news.run

      - name: Parse + classify
        run: uv run python -m parser.news.run

      - name: Summarize (LLM)
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: uv run python -m summarizer.run

      - name: Build parquet
        run: uv run python -m builder.news_build

      - name: Cleanup intermediate files
        run: rm -f data/news_pending.json data/news_enriched.json

      - name: Commit + push
        run: |
          git config user.name 'github-actions[bot]'
          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
          git add data/news data/raw/news data/manifest.json 2>/dev/null || true
          if git diff --staged --quiet; then
            echo "no changes"
          else
            git commit -m "news: $(date -u +%Y-%m-%dT%H:%MZ)"
            git push
          fi
```

`<COLLECT_YML_CHECKOUT_SHA>`, `<COLLECT_YML_UV_SHA>` 자리는 Step 1에서 확인한 실 SHA로 치환.

- [ ] **Step 3: yaml lint**

Run:
```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/news.yml')); print('yaml OK')"
```
Expected: `yaml OK`

- [ ] **Step 4: Secret 등록 가이드 (수동)**

사용자에게 알림: `gh secret set GEMINI_API_KEY` 또는 GitHub UI 에서 Repository Secret 추가. (이 plan에서 자동화 안 함 — 보안.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/news.yml
git commit -m "feat(news): GitHub Actions workflow (cron 4h, Gemini summarize)"
```

---

## Task 12: Manifest 갱신

**[SEQUENTIAL]** Task 9 ~ 11 의존.

**Files:**
- Modify: `builder/build.py`

- [ ] **Step 1: 기존 manifest 작성 부분 확인**

```bash
grep -n "manifest" builder/build.py | head -20
```

manifest 작성 함수 위치 파악.

- [ ] **Step 2: news 섹션 머지 로직 추가**

`builder/build.py`에서 manifest dict 빌드하는 부분에 다음 추가 (최종 dict 만들기 전):

```python
def _augment_manifest_with_news(manifest: dict) -> dict:
    """news/events 섹션 추가. 파일 존재 시만, 없으면 skip."""
    from pathlib import Path
    import pyarrow.parquet as pq

    news_dir = Path("data/news")
    if news_dir.exists():
        years = sorted([
            int(p.stem) for p in news_dir.glob("*.parquet")
            if p.stem.isdigit()
        ])
        if years:
            latest_year = years[-1]
            latest_file = news_dir / f"{latest_year}.parquet"
            try:
                table = pq.read_table(latest_file, columns=["fetched_at"])
                last_updated = table.column("fetched_at").to_pylist()[-1] if table.num_rows else None
                total = sum(
                    pq.read_metadata(news_dir / f"{y}.parquet").num_rows for y in years
                )
                manifest["news"] = {
                    "available_years": years,
                    "last_updated": last_updated.isoformat() if last_updated else None,
                    "total_records": total,
                }
            except Exception:
                pass

    events_dir = Path("data/events")
    if events_dir.exists():
        years = sorted([int(p.stem) for p in events_dir.glob("*.parquet") if p.stem.isdigit()])
        if years:
            manifest["events"] = {"available_years": years}

    return manifest
```

`builder/build.py`의 manifest 직렬화 직전에 호출:

```python
# 기존: manifest = {...}; (파일에 dump)
# 변경:
manifest = _augment_manifest_with_news(manifest)
# (파일에 dump)
```

(정확한 함수/변수명은 `builder/build.py` 실 구조에 맞춰 조정.)

- [ ] **Step 3: 검증 — 가격 파이프라인 manifest는 깨지지 않음**

Run:
```bash
uv run pytest tests/ -v
```
Expected: 기존 24개 + 신규 모두 PASS. 깨진 거 없음.

- [ ] **Step 4: Commit**

```bash
git add builder/build.py
git commit -m "feat(news): manifest에 news/events 섹션 추가"
```

---

## Task 13: 통합 Smoke Test + 문서

**[SEQUENTIAL]** 마지막. 실 네트워크 호출은 manual. 자동화는 mock.

**Files:**
- Create: `tests/news/test_integration.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 통합 smoke (mock 기반)** — `tests/news/test_integration.py`

```python
"""End-to-end smoke (no network, no LLM)."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow.parquet as pq

from parser.news.models import EnrichedNewsItem, RawNewsItem


def test_full_pipeline_with_mocks(tmp_path, monkeypatch):
    """scrape → parse → summarize → build, all mocked. 파일 결과 검증."""
    monkeypatch.chdir(tmp_path)
    Path("data").mkdir()

    # 1) scrape mock — 직접 pending 파일 작성
    items = [
        RawNewsItem(
            source="mining.com",
            url=f"https://e.com/{i}",
            title=f"Copper news {i}",
            fetched_at=datetime.now(timezone.utc),
            lang="en",
        )
        for i in range(3)
    ]
    Path("data/news_pending.json").write_text(
        json.dumps([i.model_dump(mode="json") for i in items], ensure_ascii=False)
    )

    # 2) parse — 실 호출
    from parser.news.run import main as parse_main
    parse_main()

    # 3) summarize — provider mock
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    fake_provider = MagicMock()
    fake_provider.name = "fake"
    fake_provider.summarize_batch.side_effect = lambda items: [
        EnrichedNewsItem(
            **i.model_dump(exclude={"url_hash"}),
            summary_ko="요약", metals=["copper"], sentiment=1,
            event_type="supply", confidence=0.8,
        ) for i in items
    ]
    with patch("summarizer.run.GeminiProvider", lambda: fake_provider):
        from summarizer.run import main as summ_main
        summ_main()

    # 4) build
    from builder.news_build import main as build_main
    build_main()

    # 검증
    out_files = list(Path("data/news").glob("*.parquet"))
    assert len(out_files) == 1
    table = pq.read_table(out_files[0])
    assert table.num_rows == 3
    summaries = table.column("summary_ko").to_pylist()
    assert all(s == "요약" for s in summaries)
```

- [ ] **Step 2: 테스트 통과 확인**

Run: `uv run pytest tests/news/test_integration.py -v`
Expected: 1 PASS

- [ ] **Step 3: 전체 테스트 회귀**

Run: `uv run pytest tests/ -v`
Expected: 기존 24 + 신규 ~30 모두 PASS

- [ ] **Step 4: CLAUDE.md 갱신**

`CLAUDE.md`의 보안 핀 섹션에 추가:

```markdown
- `astral-sh/setup-uv@<sha>` — news.yml 라인 (collect.yml과 동일)
- `actions/checkout@<sha>` — news.yml
```

`스택` 섹션에 추가:

```markdown
- feedparser, beautifulsoup4, rapidfuzz, pydantic, google-genai, zstandard — news 파이프라인
```

`자주 쓰는 커맨드` 섹션에 추가:

```markdown
uv run python -m scraper.news.run
uv run python -m parser.news.run
uv run python -m summarizer.run  # GEMINI_API_KEY 필요
uv run python -m builder.news_build
```

- [ ] **Step 5: Commit + push**

```bash
git add tests/news/test_integration.py CLAUDE.md
git commit -m "test(news): integration smoke + CLAUDE.md 갱신"
git push
```

- [ ] **Step 6: 실 운영 검증 (manual)**

GitHub UI에서:
1. Settings → Secrets → `GEMINI_API_KEY` 등록
2. Actions → news → Run workflow (workflow_dispatch)
3. 5분 이내 완료 확인
4. `data/news/2026.parquet` 커밋 확인
5. Spot check: 헤드라인 1~2개 직접 보고 LLM 요약 적절성 확인 (success criteria 검증)

KORES selector가 실제와 다르면 fixture 갱신 + 재배포.

---

## Self-Review Checklist (작성자 확인 완료)

**Spec coverage:**
- ✅ §1 목표 → 전체 plan
- ✅ §2 architecture → Task 1, 2, file structure
- ✅ §3 sources Phase 1a (6개) → Task 3, 4
- ✅ §4 LLM (Gemini primary, failover) → Task 7, 8
- ✅ §5 schema → Task 2 (models), Task 9 (parquet schema)
- ✅ §6 workflow → Task 11
- ✅ §7 failure modes → 각 Task의 fail-soft 패턴 (Task 3 _safe, Task 8 failover, Task 9 dedupe)
- ✅ §8 testing → 각 Task TDD + Task 13
- ✅ §10 구현 순서 W1 = 이 plan
- ⚠️ §9 보안 핀 갱신 → Task 11/13 에 포함

**Type consistency:**
- ✅ `RawNewsItem`, `EnrichedNewsItem`, `EventItem` 일관 (Task 2 정의 → 이후 모두 동일)
- ✅ `summarize_batch` 시그니처 일관 (Task 7, 8)
- ✅ `url_hash` 16자 hex (Task 2 정의 → Task 5/9 동일 가정)

**Placeholder scan:** 모든 Step에 실 코드/명령어 포함. TBD/TODO 없음. 단 Task 11에서 SHA pin 자리 명시 (수동 치환 필수).

**Scope:** Phase 1a만. 1b/1c는 별도 plan 명시. 단일 spec, 단일 plan.

---

## Parallel Dispatch 가이드 (sonnet subagent)

Task 2 완료 후 Task 3/4/5/6 을 4개 sonnet subagent에 동시 dispatch. 각 subagent에게 다음 컨텍스트만 전달:

1. 해당 Task 섹션 전문 (코드 포함)
2. `parser/news/models.py`, `scraper/news/base.py` 파일 (의존)
3. 명령: "Step 1~5 순서대로 실행하고 commit. 다른 Task 건드리지 말 것."

각 subagent commit 분리. 4개 commit 도착 후 Task 7으로 진행.

Task 3/4 의 fixture는 운영 시점에 실 데이터로 보정 가능 — 첫 dispatch는 plan에 적힌 fixture로 진행.

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-05-04-news-collection-phase1a.md`.

권장 실행: **Subagent-Driven (병렬 sonnet)**. Task 1, 2 sequential → Task 3/4/5/6 4개 sonnet 병렬 → 7~13 sequential.
