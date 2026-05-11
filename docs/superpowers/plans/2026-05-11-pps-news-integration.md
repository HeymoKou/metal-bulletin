# PPS 조달청 주간 리포트 뉴스 통합 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scrape 조달청 비철/희소금속 주간 리포트 PDFs, extract text, route through existing news pipeline (Gemini 요약), display in news drawer with 'pps' source badge.

**Architecture:** New `PPSScraper` (NewsSource impl) does two HTTP roundtrips per item — POST `/bichuk/bbs/view.do?key=00826&bbsSn=<id>` for detail, GET `/common/fileDown.do?key=<docKey>&sn=1` for PDF — then pdfplumber extracts text into `RawNewsItem.snippet`. Classifier bypasses keyword filter when `source == 'pps'`. FE renders 'pps' badge with distinct color.

**Tech Stack:** Python 3.14, requests, pdfplumber (already in pyproject), pytest, vanilla JS ESM.

---

## File Structure

| Path | Role |
|------|------|
| `scraper/news/pps.py` | NEW — PPSScraper |
| `tests/news/test_pps.py` | NEW — unit tests |
| `tests/news/fixtures/pps_list.html` | EXISTS — already saved |
| `tests/news/fixtures/pps_view.html` | EXISTS — already saved |
| `tests/news/fixtures/pps_sample.pdf` | EXISTS — already saved |
| `parser/news/classify.py` | MODIFY — source bypass |
| `scraper/news/run.py` | MODIFY — add PPSScraper |
| `site/news.js` | MODIFY — pps badge color |
| `site/style.css` | MODIFY — `.news-source--pps` class |

---

## Task 1: List page parser

Parses `bbsSn` ID + title from list HTML. Two title prefixes filtered: "주간 경제·비철금속" and "주간희소금속". Title 'middle dot' is `&middot;` (U+00B7) in HTML — match flexible.

**Files:**
- Create: `scraper/news/pps.py`
- Test: `tests/news/test_pps.py`

- [ ] **Step 1: Write failing test for list parser**

```python
# tests/news/test_pps.py
from pathlib import Path
from scraper.news.pps import parse_list

FIX = Path(__file__).parent / "fixtures"


def test_parse_list_filters_two_series():
    html = (FIX / "pps_list.html").read_text(encoding="utf-8")
    items = parse_list(html)
    titles = [it["title"] for it in items]
    # Page 1 has 10 items, all of the two target series
    assert len(items) >= 8
    assert any("주간 경제" in t and "비철금속" in t for t in titles)
    assert any("주간희소금속" in t for t in titles)
    # Off-topic posts (e.g., "공지사항") must not appear
    assert all(("주간 경제" in t and "비철금속" in t) or "주간희소금속" in t for t in titles)
    # bbsSn = 10 ASCII digits
    for it in items:
        assert it["bbs_sn"].isdigit() and len(it["bbs_sn"]) == 10
```

- [ ] **Step 2: Run — expect ImportError**

```
uv run pytest tests/news/test_pps.py::test_parse_list_filters_two_series -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scraper.news.pps'`.

- [ ] **Step 3: Implement `parse_list` only**

```python
# scraper/news/pps.py
"""PPS 조달청 비축물자 주간 리포트 scraper.

Board: https://www.pps.go.kr/bichuk/bbs/list.do?key=00826
Two target series:
  - "주간 경제·비철금속 시장동향" (Cu/Al/Zn/Ni/Pb/Sn)
  - "주간희소금속가격동향"           (minor metals incl. Sb)
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# <a href="#none" onclick="goView('2605060014', '0001');">
#   주간 경제&middot;비철금속 시장동향(26.5.6)
# </a>
_ROW_RE = re.compile(
    r"goView\('(\d{10})',\s*'[^']*'\)\s*\"\s*>\s*([\s\S]{1,500}?)</a>",
    re.IGNORECASE,
)


def _normalize_title(raw: str) -> str:
    t = re.sub(r"<[^>]+>", "", raw)
    t = t.replace("&middot;", "·").replace("&nbsp;", " ")
    return " ".join(t.split())


def _is_target(title: str) -> bool:
    if "주간희소금속" in title:
        return True
    if "주간 경제" in title and "비철금속" in title:
        return True
    return False


def parse_list(html: str) -> list[dict]:
    out = []
    seen: set[str] = set()
    for sn, raw_title in _ROW_RE.findall(html):
        if sn in seen:
            continue
        title = _normalize_title(raw_title)
        if not _is_target(title):
            continue
        seen.add(sn)
        out.append({"bbs_sn": sn, "title": title})
    return out
```

- [ ] **Step 4: Run — expect PASS**

```
uv run pytest tests/news/test_pps.py::test_parse_list_filters_two_series -v
```

- [ ] **Step 5: Commit**

```bash
git add scraper/news/pps.py tests/news/test_pps.py tests/news/fixtures/pps_list.html
git commit -m "feat(news): PPS list parser, filters two target series"
```

---

## Task 2: Detail page → PDF download URL

`view.do` returns HTML containing `<a href="/common/fileDown.do?key=<docKey>&sn=1">`. Note: docKey ≠ bbsSn (e.g. bbsSn `2605060014` → docKey `202605060008`). The HTML href contains a `;jsessionid=...` segment that must be stripped before reuse.

**Files:**
- Modify: `scraper/news/pps.py`
- Modify: `tests/news/test_pps.py`

- [ ] **Step 1: Failing test for `parse_attachment_url`**

```python
def test_parse_attachment_url_strips_jsessionid():
    html = (FIX / "pps_view.html").read_text(encoding="utf-8")
    from scraper.news.pps import parse_attachment_url
    url = parse_attachment_url(html)
    assert url is not None
    assert url.startswith("/common/fileDown.do")
    assert "jsessionid" not in url.lower()
    assert "key=" in url and "sn=" in url


def test_parse_attachment_url_returns_none_when_missing():
    from scraper.news.pps import parse_attachment_url
    assert parse_attachment_url("<html>no attachment</html>") is None
```

- [ ] **Step 2: Run — expect FAIL (function not defined)**

```
uv run pytest tests/news/test_pps.py -v
```

- [ ] **Step 3: Implement**

Append to `scraper/news/pps.py`:

```python
_ATTACH_RE = re.compile(
    r'href="(/common/fileDown\.do[^"]+)"',
    re.IGNORECASE,
)
_JSESSION_RE = re.compile(r";jsessionid=[^?]+", re.IGNORECASE)


def parse_attachment_url(html: str) -> str | None:
    m = _ATTACH_RE.search(html)
    if not m:
        return None
    return _JSESSION_RE.sub("", m.group(1))
```

- [ ] **Step 4: PASS**

```
uv run pytest tests/news/test_pps.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scraper/news/pps.py tests/news/test_pps.py tests/news/fixtures/pps_view.html
git commit -m "feat(news): PPS attachment URL extractor"
```

---

## Task 3: PDF text extraction (with dedupe of repeated glyphs)

pdfplumber on the sample produces strings like `주주주주주간간간간간` — Korean PDF chars are layered. Collapse runs of identical Korean chars longer than 4 to a single char. Latin/digit untouched.

**Files:**
- Modify: `scraper/news/pps.py`
- Modify: `tests/news/test_pps.py`

- [ ] **Step 1: Failing test**

```python
def test_extract_pdf_text_dedupes_glyphs():
    from scraper.news.pps import extract_pdf_text
    pdf_bytes = (FIX / "pps_sample.pdf").read_bytes()
    text = extract_pdf_text(pdf_bytes)
    assert len(text) > 500
    # Sample PDF has "주간 경제·비철금속 시장 동향" in header
    assert "주간" in text and "비철금속" in text
    # No 5+ Korean char repeats (artifact removed)
    import re
    assert re.search(r"([가-힣])\1{4,}", text) is None
```

- [ ] **Step 2: FAIL**

```
uv run pytest tests/news/test_pps.py::test_extract_pdf_text_dedupes_glyphs -v
```

- [ ] **Step 3: Implement**

```python
import io
import pdfplumber

_KOR_REPEAT_RE = re.compile(r"([가-힣])\1{1,}")


def extract_pdf_text(pdf_bytes: bytes, max_pages: int = 6) -> str:
    """Extract text from first `max_pages` of PDF. Collapses Korean glyph runs."""
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:max_pages]:
            t = page.extract_text() or ""
            if t:
                parts.append(t)
    raw = "\n".join(parts)
    # Collapse e.g. 주주주주주 → 주
    return _KOR_REPEAT_RE.sub(r"\1", raw)
```

- [ ] **Step 4: PASS**

```
uv run pytest tests/news/test_pps.py::test_extract_pdf_text_dedupes_glyphs -v
```

- [ ] **Step 5: Commit**

```bash
git add scraper/news/pps.py tests/news/test_pps.py tests/news/fixtures/pps_sample.pdf
git commit -m "feat(news): PPS PDF text extractor with glyph dedupe"
```

---

## Task 4: PPSScraper class (full fetch flow)

Wire parts together. Use realistic Chrome UA + session cookie jar so jsessionid persists. 1.5s sleep between PDFs. Per-item failure logged, never raised. Caps at first 8 list items per run (≈4 weeks of two-series content).

**Files:**
- Modify: `scraper/news/pps.py`
- Modify: `tests/news/test_pps.py`

- [ ] **Step 1: Failing test (uses monkeypatch — no real network)**

```python
def test_scraper_returns_raw_news_items(monkeypatch):
    from scraper.news.pps import PPSScraper
    from parser.news.models import RawNewsItem

    list_html = (FIX / "pps_list.html").read_text(encoding="utf-8")
    view_html = (FIX / "pps_view.html").read_text(encoding="utf-8")
    pdf_bytes = (FIX / "pps_sample.pdf").read_bytes()

    class FakeResp:
        def __init__(self, content, text=None, status=200):
            self.content = content
            self.text = text if text is not None else content.decode("utf-8", "replace")
            self.status_code = status
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    class FakeSession:
        def __init__(self):
            self.headers = {}
            self.cookies = {}
        def get(self, url, **kw):
            if "list.do" in url:
                return FakeResp(list_html.encode("utf-8"), list_html)
            if "fileDown.do" in url:
                return FakeResp(pdf_bytes)
            raise AssertionError(f"unexpected GET {url}")
        def post(self, url, **kw):
            if "view.do" in url:
                return FakeResp(view_html.encode("utf-8"), view_html)
            raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr("scraper.news.pps.requests.Session", FakeSession)
    items = PPSScraper(limit=2).fetch()
    assert len(items) == 2
    assert all(isinstance(i, RawNewsItem) for i in items)
    assert all(i.source == "pps" for i in items)
    assert all(i.lang == "ko" for i in items)
    assert all(i.snippet and len(i.snippet) > 100 for i in items)


def test_scraper_silent_fail_on_network_error(monkeypatch):
    from scraper.news.pps import PPSScraper
    class BrokenSession:
        def __init__(self):
            self.headers = {}
            self.cookies = {}
        def get(self, *a, **kw): raise RuntimeError("dns")
        def post(self, *a, **kw): raise RuntimeError("dns")
    monkeypatch.setattr("scraper.news.pps.requests.Session", BrokenSession)
    assert PPSScraper().fetch() == []
```

- [ ] **Step 2: FAIL**

```
uv run pytest tests/news/test_pps.py -v
```

- [ ] **Step 3: Implement**

Append to `scraper/news/pps.py`:

```python
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

from parser.news.models import RawNewsItem
from scraper.news.base import NewsSource

BASE_URL = "https://www.pps.go.kr"
LIST_PATH = "/bichuk/bbs/list.do?key=00826"
VIEW_PATH = "/bichuk/bbs/view.do?key=00826"
TIMEOUT = 20
SLEEP_BETWEEN = 1.5

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class PPSScraper(NewsSource):
    name = "pps"
    lang = "ko"

    def __init__(self, base_url: str = BASE_URL, limit: int = 8):
        self.base_url = base_url
        self.limit = limit

    def fetch(self) -> list[RawNewsItem]:
        try:
            sess = requests.Session()
            sess.headers.update({
                "User-Agent": UA,
                "Accept-Language": "ko-KR,ko;q=0.9",
            })
            list_html = sess.get(
                urljoin(self.base_url, LIST_PATH), timeout=TIMEOUT
            ).text
        except Exception as e:
            logger.warning("pps list fetch failed err=%s", e)
            return []

        rows = parse_list(list_html)[: self.limit]
        out: list[RawNewsItem] = []
        now = datetime.now(timezone.utc)
        for row in rows:
            try:
                item = self._fetch_one(sess, row, now)
                if item:
                    out.append(item)
            except Exception as e:
                logger.warning("pps item failed bbs_sn=%s err=%s", row["bbs_sn"], e)
            time.sleep(SLEEP_BETWEEN)
        return out

    def _fetch_one(self, sess, row: dict, now: datetime) -> RawNewsItem | None:
        view_url = urljoin(self.base_url, VIEW_PATH)
        r = sess.post(
            view_url,
            data={"bbsSn": row["bbs_sn"], "key": "00826"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        attach_path = parse_attachment_url(r.text)
        if not attach_path:
            logger.info("pps no attachment for bbs_sn=%s", row["bbs_sn"])
            return None
        pdf_url = urljoin(self.base_url, attach_path)
        snippet: str | None
        try:
            pdf_resp = sess.get(pdf_url, timeout=TIMEOUT)
            pdf_resp.raise_for_status()
            snippet = extract_pdf_text(pdf_resp.content)
        except Exception as e:
            logger.warning("pps pdf extract failed bbs_sn=%s err=%s", row["bbs_sn"], e)
            snippet = None
        return RawNewsItem(
            source="pps",
            url=pdf_url,
            title=row["title"],
            snippet=snippet,
            fetched_at=now,
            lang="ko",
            published_at=None,
        )
```

- [ ] **Step 4: PASS**

```
uv run pytest tests/news/test_pps.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scraper/news/pps.py tests/news/test_pps.py
git commit -m "feat(news): PPSScraper end-to-end (list → view → PDF)"
```

---

## Task 5: Classifier bypass for `source='pps'`

PPS posts are domain-confirmed (조달청 official) — keyword filter would discard them since title is generic ("주간 경제·비철금속 시장동향"). Bypass in `is_relevant`.

**Files:**
- Modify: `parser/news/classify.py`
- Modify: `tests/news/test_classify.py` (extend existing)

- [ ] **Step 1: Failing test**

Append to `tests/news/test_classify.py`:

```python
def test_pps_source_bypasses_keyword_filter():
    from datetime import datetime, timezone
    from parser.news.classify import is_relevant
    from parser.news.models import RawNewsItem
    item = RawNewsItem(
        source="pps",
        url="https://www.pps.go.kr/common/fileDown.do?key=X&sn=1",
        title="주간 경제·비철금속 시장동향(26.5.6)",
        snippet=None,
        fetched_at=datetime.now(timezone.utc),
        lang="ko",
    )
    assert is_relevant(item) is True
```

- [ ] **Step 2: FAIL**

```
uv run pytest tests/news/test_classify.py::test_pps_source_bypasses_keyword_filter -v
```

- [ ] **Step 3: Modify `is_relevant`**

```python
# parser/news/classify.py — replace existing is_relevant
def is_relevant(item: RawNewsItem) -> bool:
    if item.source == "pps":
        return True
    return len(classify_metals(item)) > 0
```

- [ ] **Step 4: PASS**

```
uv run pytest tests/news/ -v
```

- [ ] **Step 5: Commit**

```bash
git add parser/news/classify.py tests/news/test_classify.py
git commit -m "feat(news): bypass keyword filter for source=pps"
```

---

## Task 6: Wire PPSScraper into pipeline

**Files:**
- Modify: `scraper/news/run.py`

- [ ] **Step 1: Edit run.py**

Replace:

```python
from scraper.news.rss import RSSScraper
```

With:

```python
from scraper.news.pps import PPSScraper
from scraper.news.rss import RSSScraper
```

And replace:

```python
    scrapers = [RSSScraper()]
```

With:

```python
    scrapers = [RSSScraper(), PPSScraper()]
```

- [ ] **Step 2: Verify imports**

```
uv run python -c "from scraper.news.run import main; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Run existing tests, confirm no regression**

```
uv run pytest tests/ -q
```
Expected: ALL PASS.

- [ ] **Step 4: Commit**

```bash
git add scraper/news/run.py
git commit -m "feat(news): enable PPSScraper in default pipeline"
```

---

## Task 7: FE 'pps' source badge

News drawer renders `<span>${escAttr(n.source)}</span>` (site/news.js:241). Add CSS for distinct color when source is 'pps'.

**Files:**
- Modify: `site/news.js` (around line 241)
- Modify: `site/style.css`

- [ ] **Step 1: Inspect current source-tag markup**

Open `site/news.js` and find the `<span>${escAttr(n.source)}</span>` render site. Replace with:

```js
<span class="news-source news-source--${escAttr(n.source)}">${escAttr(n.source)}</span>
```

(Pre-edit verification: `grep -n 'escAttr(n.source)' site/news.js` should show exactly one match. If multiple, update them all the same way.)

- [ ] **Step 2: Add CSS rule**

Append to `site/style.css`:

```css
.news-source--pps {
  background: #0a4a8f;
  color: #fff;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}
```

- [ ] **Step 3: Smoke test**

```
npm run smoke
```
Expected: 8 passed.

- [ ] **Step 4: Manual browser check**

Open the site, open news drawer, verify pps badge renders distinctly (until first pps run completes, no live pps item — fixture verification only).

- [ ] **Step 5: Commit**

```bash
git add site/news.js site/style.css
git commit -m "feat(site): distinct badge color for pps news source"
```

---

## Task 8: End-to-end live verification

After all prior tasks, run the real pipeline against live PPS, confirm output.

- [ ] **Step 1: Live scraper smoke**

```
uv run python -c "from scraper.news.pps import PPSScraper; xs = PPSScraper(limit=2).fetch(); print(len(xs)); [print(x.title, x.url, len(x.snippet or '')) for x in xs]"
```
Expected: 2 items, both with non-empty snippet (>500 chars), URLs ending `&sn=1`.

- [ ] **Step 2: Run news pipeline (skip Gemini if no key)**

```
uv run python -m scraper.news.run && uv run python -m parser.news.run
```
Expected: pending file → deduped + classified output, PPS items survive classification.

- [ ] **Step 3: Update CLAUDE.md news section**

In `CLAUDE.md`, under "뉴스 파이프라인", change the sources line from `snmnews` only to include PPS:

```
- 소스: snmnews 철강금속신문 (RSS) + 조달청 PPS 비축물자 주간리포트 (PDF)
```

- [ ] **Step 4: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: note PPS source in news pipeline"
```

- [ ] **Step 5: Push**

```bash
git push
```
