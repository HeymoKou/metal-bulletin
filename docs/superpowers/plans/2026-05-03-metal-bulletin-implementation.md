# 비철금속 시세 대시보드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NH선물 PDF 자동 수집·파싱 → JSON 저장 → GitHub Pages 모바일 대시보드

**Architecture:** GitHub Actions cron으로 매일 PDF 다운로드 + 파싱 → data/ 에 JSON 커밋. 프론트엔드는 정적 HTML/JS가 JSON fetch해서 렌더링. 4개 파이프라인 모듈(scraper, parser, exchange, builder)이 독립적으로 동작.

**Tech Stack:** Python 3.14 (uv), pdfplumber, requests, BeautifulSoup4, 순수 HTML/CSS/JS

---

## File Structure

```
metal-bulletin/
├── scraper/
│   └── download.py          # PDF 다운로드 (세션 관리, 페이지네이션, 파일 추출)
├── parser/
│   ├── parse.py             # PDF → daily JSON 변환 (메인 진입점)
│   ├── page1.py             # Page 1 파싱: LME 시세 + 정산가 + EV metals
│   ├── page2.py             # Page 2 파싱: 재고 + SHFE + market factors
│   └── page3.py             # Page 3 파싱: 귀금속
├── exchange/
│   └── fetch_krw.py         # 한국은행 ECOS API → USD/KRW 환율
├── builder/
│   └── build.py             # daily JSONs + exchange → metals/*.json + index.json
├── data/
│   ├── daily/               # {YYYY-MM-DD}.json (영업일별)
│   ├── metals/              # {metal}.json (광물별 시계열)
│   ├── exchange/
│   │   └── usd_krw.json
│   └── index.json
├── site/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tests/
│   ├── test_scraper.py
│   ├── test_parser.py
│   ├── test_exchange.py
│   └── test_builder.py
├── .github/
│   └── workflows/
│       └── collect.yml
├── .gitignore
└── pyproject.toml
```

---

### Task 1: 프로젝트 세팅 + .gitignore

**Files:**
- Modify: `pyproject.toml`
- Create: `.gitignore`
- Create: `data/daily/.gitkeep`
- Create: `data/metals/.gitkeep`
- Create: `data/exchange/.gitkeep`

- [ ] **Step 1: .gitignore 작성**

```gitignore
# Python
__pycache__/
*.pyc
.venv/

# Temp PDFs
tmp/

# OS
.DS_Store

# IDE
.idea/
.vscode/

# Samples (dev only)
samples/
```

- [ ] **Step 2: data 디렉토리 구조 생성**

```bash
mkdir -p data/daily data/metals data/exchange
touch data/daily/.gitkeep data/metals/.gitkeep data/exchange/.gitkeep
```

- [ ] **Step 3: pyproject.toml에 pytest 추가**

```toml
[project]
name = "metal-bulletin"
version = "0.1.0"
description = "비철금속 시세 자동 수집 및 대시보드"
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "beautifulsoup4>=4.14.3",
    "pdfplumber>=0.11.9",
    "requests>=2.33.1",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]
```

- [ ] **Step 4: 불필요한 파일 정리 + 커밋**

```bash
rm -f main.py
uv sync --group dev
git add .gitignore data/ pyproject.toml uv.lock
git rm -f main.py 2>/dev/null || true
git commit -m "chore: 프로젝트 구조 세팅"
```

---

### Task 2: Scraper — PDF 다운로드

**Files:**
- Create: `scraper/__init__.py`
- Create: `scraper/download.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: 테스트 작성 — scraper HTML 파싱**

`tests/test_scraper.py`:
```python
from scraper.download import extract_pdf_links


SAMPLE_HTML = """
<td class="fileDown">
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032340&FileNm=NHF+Daily+Metal+Bulletin+20260501.pdf"
       class="iconSty file" title="NHF Daily Metal Bulletin 20260501.pdf 첨부파일 다운로드">첨부파일</a>
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032340&FileNm=LME+Valuation+20260501.pdf"
       class="iconSty file" title="LME Valuation 20260501.pdf 첨부파일 다운로드">첨부파일</a>
</td>
<td class="fileDown">
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032338&FileNm=NHF+Daily+Metal+Bulletin+20260430.pdf"
       class="iconSty file" title="NHF Daily Metal Bulletin 20260430.pdf 첨부파일 다운로드">첨부파일</a>
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032338&FileNm=LME+Valuation+20260430.pdf"
       class="iconSty file" title="LME Valuation 20260430.pdf 첨부파일 다운로드">첨부파일</a>
</td>
<td class="fileDown">
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032319&FileNm=NHF+Weekly+Metal+Data+20260424.pdf"
       class="iconSty file" title="NHF Weekly Metal Data 20260424.pdf 첨부파일 다운로드">첨부파일</a>
</td>
"""


def test_extract_pdf_links_filters_daily_only():
    links = extract_pdf_links(SAMPLE_HTML)
    assert len(links) == 2
    assert links[0]["date"] == "2026-05-01"
    assert links[0]["file_id"] == "FILE_000000000032340"
    assert "NHF+Daily+Metal+Bulletin" in links[0]["url"]
    assert links[1]["date"] == "2026-04-30"


def test_extract_pdf_links_skips_weekly_and_valuation():
    links = extract_pdf_links(SAMPLE_HTML)
    for link in links:
        assert "Weekly" not in link["url"]
        assert "Valuation" not in link["url"]
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/test_scraper.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scraper'`

- [ ] **Step 3: extract_pdf_links 구현**

`scraper/__init__.py`: 빈 파일

`scraper/download.py`:
```python
import re
import argparse
import json
from pathlib import Path
from bs4 import BeautifulSoup
import requests

BASE_URL = "https://www.futures.co.kr"
BBS_ID = "BBSMSTR_000000000251"
SEARCH_URL = f"{BASE_URL}/bbs/boardSearch.do"
CONTENT_URL = f"{BASE_URL}/content/Getcontent.do?content=3000031"
DAILY_PATTERN = re.compile(r"NHF\+Daily\+Metal\+Bulletin\+(\d{8})\.pdf")


def extract_pdf_links(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a_tag in soup.select("td.fileDown a"):
        href = a_tag.get("href", "")
        match = DAILY_PATTERN.search(href)
        if not match:
            continue
        date_str = match.group(1)
        date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        file_id_match = re.search(r"atchFileId=(FILE_\d+)", href)
        if not file_id_match:
            continue
        links.append({
            "date": date,
            "file_id": file_id_match.group(1),
            "url": href,
        })
    return links


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    })
    session.get(BASE_URL)
    session.get(CONTENT_URL)
    return session


def fetch_page(session: requests.Session, page: int) -> str:
    if page == 1:
        resp = session.get(CONTENT_URL)
    else:
        resp = session.post(SEARCH_URL, data={
            "bbsId": BBS_ID,
            "pageIndex": str(page),
            "url": "content/research/KR_interestRate",
        })
    return resp.text


def download_pdf(session: requests.Session, url: str, dest: Path) -> bool:
    full_url = f"{BASE_URL}{url}" if url.startswith("/") else url
    resp = session.get(full_url)
    if resp.status_code == 200 and len(resp.content) > 0:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return True
    return False


def existing_dates(data_dir: Path) -> set[str]:
    return {f.stem for f in (data_dir / "daily").glob("*.json")}


def run(mode: str, data_dir: Path, tmp_dir: Path, max_pages: int = 7):
    session = create_session()
    done = existing_dates(data_dir)
    downloaded = []

    pages = range(1, 2) if mode == "latest" else range(1, max_pages + 1)
    for page_num in pages:
        html = fetch_page(session, page_num)
        links = extract_pdf_links(html)
        if not links:
            continue

        for link in links:
            if link["date"] in done:
                continue
            dest = tmp_dir / f"{link['date']}.pdf"
            if download_pdf(session, link["url"], dest):
                downloaded.append({"date": link["date"], "path": str(dest)})
                print(f"Downloaded: {link['date']}")

        if mode == "latest" and downloaded:
            break

    manifest = tmp_dir / "manifest.json"
    manifest.write_text(json.dumps(downloaded, ensure_ascii=False, indent=2))
    print(f"Total downloaded: {len(downloaded)}")
    return downloaded


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["latest", "backfill"], default="latest")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--tmp-dir", type=Path, default=Path("tmp/pdfs"))
    ap.add_argument("--max-pages", type=int, default=7)
    args = ap.parse_args()
    run(args.mode, args.data_dir, args.tmp_dir, args.max_pages)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/test_scraper.py -v
```
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add scraper/ tests/test_scraper.py
git commit -m "feat: scraper — PDF 다운로드 모듈"
```

---

### Task 3: Parser — Page 1 (LME 시세 + 정산가 + EV Metals)

**Files:**
- Create: `parser/__init__.py`
- Create: `parser/page1.py`
- Create: `tests/test_parser.py`

PDF Page 1 테이블 구조 (실제 샘플 기반):

**Table 1 (LME 시세):** 10r x 10c
- row 0-1: 헤더
- row 2: Cu Cash — [None, '12,942.76', '12,968.90', '13,041.90', '12,875.90', '12,896.40', '-46.36', '', '', '']
- row 3: Cu 3M — [None, '13,017.00', ...values..., bid, ask, open_interest]
- row 4: Al Cash
- row 5: Al 3M
- row 6: Zn (3M only, has bid/ask/OI)
- row 7: Pb (3M only)
- row 8: Ni (3M only)
- row 9: Sn (3M only)

**Table 2 (정산가):** 8r x 11c
- row 0-1: 헤더
- row 2-7: Cu, Al, Zn, Pb, Ni, Sn
- cols: [label, cash, 3m, cash(당일), cash_avg, 3m_avg, prev_cash, prev_3m, fwd1, fwd2, fwd3]

**Table 3 (EV Metals):** 8r x 11c
- row 4: [None, cobalt_may, cobalt_jul, lithium_may, ...]
- row 5: 변동폭
- row 6: 변동률

- [ ] **Step 1: 테스트 작성 — page1 파싱**

`tests/test_parser.py`:
```python
from parser.page1 import parse_lme_prices, parse_settlement, parse_ev_metals


SAMPLE_TABLE1 = [
    ['전일 금 일 Cash - 3M 미결제약정(O/I)\n변동폭', None, None, None, None, None, None, None, None, None],
    ['종가', None, '시가 고가(B) 저가(A) 종가(A)', None, None, None, '', 'BID ASK', None, '전일 변동폭'],
    [None, '12,942.76', '12,968.90', '13,041.90', '12,875.90', '12,896.40', '-46.36', '', '', ''],
    [None, '13,017.00', '13,047.00', '13,120.00', '12,954.00', '12,974.50', '-42.50', '-82.10', '-78.10', '265,325'],
    [None, '3,540.17', '3,548.31', '3,599.81', '3,547.81', '3,577.81', '37.64', '', '', ''],
    [None, '3,482.00', '3,482.50', '3,534.00', '3,482.00', '3,512.00', '30.00', '61.81', '65.81', '676,743'],
    [None, '3,358.00', '3,368.00', '3,395.00', '3,331.50', '3,338.00', '-20.00', '-9.86', '-7.86', '232,402'],
    [None, '1,952.50', '1,958.00', '1,963.00', '1,943.50', '1,950.50', '-2.00', '-7.05', '-5.05', '175,151'],
    [None, '19,355.00', '19,455.00', '19,645.00', '19,260.00', '19,345.00', '-10.00', '-187.87', '-177.87', '253,610'],
    [None, '49,005.00', '49,005.00', '49,645.00', '49,005.00', '49,620.00', '615.00', '-164.00', '-154.00', '20,837'],
]

SAMPLE_TABLE2 = [
    ['금 일 당월평균 전월평균', None, None, None, None, None, 'LME 정산가 (LONDON 17시00분)', None, None, None, None],
    ['', 'Cash 3M', None, 'Cash', 'Cash 3M', None, 'Cash 3M May Jun Jul', None, None, None, None],
    [None, '12895.00', '12967.00', '12895.00', '12891.38', '12969.88', '12916.40', '12996.50', '12943.14', '12970.73', '12987.01'],
    [None, '3584.00', '3523.00', '3584.00', '3600.63', '3545.73', '3585.81', '3522.00', '3590.91', '3562.08', '3540.84'],
    [None, '3349.00', '3343.00', '3349.00', '3361.55', '3368.83', '3335.64', '3344.50', '3346.13', '3353.55', '3352.11'],
    [None, '1945.00', '1956.00', '1945.00', '1922.65', '1946.15', '1942.95', '1949.00', '1952.39', '1951.12', '1948.08'],
    [None, '19180.00', '19385.00', '19180.00', '18005.75', '18193.25', '19182.13', '19365.00', '19216.38', '19282.38', '19348.00'],
    [None, '49200.00', '49350.00', '49200.00', '48941.75', '49092.50', '49264.00', '49423.00', '49319.00', '49359.00', '49422.00'],
]

SAMPLE_TABLE3 = [
    ['EV Metals', None, None, None, None, None, None, None, None, None, None],
    ['품목', '코발트 (CME Fastmarket MB)', None, '리튬 (CME Fastmarket MB)', None, None, '', None, None, None, None],
    [None, '2026-05-01', '2026-05-01', '2026-05-01', '2026-05-01', '', '', '', '', '', ''],
    [None, 'May26', 'Jul26', 'May26', None, None, None, None, None, None, None],
    [None, '57761.04', '59634.97', '45966.33', None, None, None, None, None, None, None],
    [None, '-154.32', '595.25', '771.62', None, None, None, None, None, None, None],
    [None, '-0.27%', '1.00%', '1.68%', None, None, None, None, None, None, None],
    [None, '', '', '', None, None, None, None, None, None, None],
]


def test_parse_lme_prices_copper():
    result = parse_lme_prices(SAMPLE_TABLE1)
    cu = result["copper"]
    assert cu["cash"]["prev_close"] == 12942.76
    assert cu["cash"]["close"] == 12896.40
    assert cu["cash"]["change"] == -46.36
    assert cu["3m"]["open"] == 13047.00
    assert cu["3m"]["high"] == 13120.00
    assert cu["3m"]["low"] == 12954.00
    assert cu["3m"]["close"] == 12974.50
    assert cu["3m"]["change"] == -42.50
    assert cu["bid"] == -82.10
    assert cu["ask"] == -78.10
    assert cu["open_interest"] == 265325


def test_parse_lme_prices_zinc():
    result = parse_lme_prices(SAMPLE_TABLE1)
    zn = result["zinc"]
    assert zn["3m"]["prev_close"] == 3358.00
    assert zn["3m"]["open"] == 3368.00
    assert zn["3m"]["close"] == 3338.00
    assert zn["bid"] == -9.86
    assert zn["open_interest"] == 232402


def test_parse_lme_prices_all_metals_present():
    result = parse_lme_prices(SAMPLE_TABLE1)
    assert set(result.keys()) == {"copper", "aluminum", "zinc", "lead", "nickel", "tin"}


def test_parse_settlement():
    result = parse_settlement(SAMPLE_TABLE2)
    cu = result["copper"]
    assert cu["cash"] == 12895.00
    assert cu["3m"] == 12967.00
    assert cu["monthly_avg"]["cash"] == 12891.38
    assert cu["monthly_avg"]["3m"] == 12969.88
    assert cu["prev_monthly_avg"]["cash"] == 12916.40
    assert cu["prev_monthly_avg"]["3m"] == 12996.50
    assert len(cu["forwards"]) == 3


def test_parse_ev_metals():
    result = parse_ev_metals(SAMPLE_TABLE3)
    assert result["cobalt"]["may26"] == 57761.04
    assert result["cobalt"]["jul26"] == 59634.97
    assert result["lithium"]["may26"] == 45966.33
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/test_parser.py -v
```
Expected: FAIL

- [ ] **Step 3: page1.py 구현**

`parser/__init__.py`: 빈 파일

`parser/page1.py`:
```python
METALS_ORDER = ["copper", "aluminum", "zinc", "lead", "nickel", "tin"]


def _num(val: str | None) -> float | None:
    if val is None or val.strip() == "" or val.strip() == "#N/A":
        return None
    return float(val.replace(",", ""))


def _int_num(val: str | None) -> int | None:
    n = _num(val)
    return int(n) if n is not None else None


def parse_lme_prices(table: list[list]) -> dict:
    """Parse Page 1 Table 1: LME 시세.

    Row layout:
    - rows[2],  rows[3]:  Cu Cash, Cu 3M
    - rows[4],  rows[5]:  Al Cash, Al 3M
    - rows[6]:            Zn (3M only, with bid/ask/OI)
    - rows[7]:            Pb
    - rows[8]:            Ni
    - rows[9]:            Sn
    """
    result = {}

    # Cu, Al: separate Cash and 3M rows
    for metal, cash_row_idx, tm_row_idx in [("copper", 2, 3), ("aluminum", 4, 5)]:
        cash_row = table[cash_row_idx]
        tm_row = table[tm_row_idx]
        result[metal] = {
            "cash": {
                "prev_close": _num(cash_row[1]),
                "open": _num(cash_row[2]),
                "high": _num(cash_row[3]),
                "low": _num(cash_row[4]),
                "close": _num(cash_row[5]),
                "change": _num(cash_row[6]),
            },
            "3m": {
                "prev_close": _num(tm_row[1]),
                "open": _num(tm_row[2]),
                "high": _num(tm_row[3]),
                "low": _num(tm_row[4]),
                "close": _num(tm_row[5]),
                "change": _num(tm_row[6]),
            },
            "bid": _num(tm_row[7]),
            "ask": _num(tm_row[8]),
            "open_interest": _int_num(tm_row[9]),
        }

    # Zn, Pb, Ni, Sn: single row = 3M data with bid/ask/OI
    for metal, row_idx in [("zinc", 6), ("lead", 7), ("nickel", 8), ("tin", 9)]:
        row = table[row_idx]
        result[metal] = {
            "3m": {
                "prev_close": _num(row[1]),
                "open": _num(row[2]),
                "high": _num(row[3]),
                "low": _num(row[4]),
                "close": _num(row[5]),
                "change": _num(row[6]),
            },
            "bid": _num(row[7]),
            "ask": _num(row[8]),
            "open_interest": _int_num(row[9]),
        }

    return result


def parse_settlement(table: list[list]) -> dict:
    """Parse Page 1 Table 2: LME 정산가.

    Rows 2-7 = Cu, Al, Zn, Pb, Ni, Sn.
    Cols: [label, cash, 3m, cash_today, cash_avg, 3m_avg, prev_cash, prev_3m, fwd1, fwd2, fwd3]
    """
    result = {}
    for i, metal in enumerate(METALS_ORDER):
        row = table[i + 2]
        result[metal] = {
            "cash": _num(row[1]),
            "3m": _num(row[2]),
            "monthly_avg": {
                "cash": _num(row[4]),
                "3m": _num(row[5]),
            },
            "prev_monthly_avg": {
                "cash": _num(row[6]),
                "3m": _num(row[7]),
            },
            "forwards": {
                "m1": _num(row[8]),
                "m2": _num(row[9]),
                "m3": _num(row[10]),
            },
        }
    return result


def parse_ev_metals(table: list[list]) -> dict:
    """Parse Page 1 Table 3: EV Metals (코발트, 리튬)."""
    contracts_row = table[3]
    values_row = table[4]

    result = {"cobalt": {}, "lithium": {}}
    # Col 1-2: cobalt contracts, Col 3+: lithium contracts
    for col, metal in [(1, "cobalt"), (2, "cobalt"), (3, "lithium")]:
        contract = contracts_row[col]
        value = _num(values_row[col])
        if contract and value is not None:
            result[metal][contract.lower()] = value

    return result
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/test_parser.py -v
```
Expected: all passed

- [ ] **Step 5: 커밋**

```bash
git add parser/ tests/test_parser.py
git commit -m "feat: parser page1 — LME 시세, 정산가, EV metals 파싱"
```

---

### Task 4: Parser — Page 2 (재고 + SHFE)

**Files:**
- Create: `parser/page2.py`
- Modify: `tests/test_parser.py`

PDF Page 2 테이블 구조:

**Table 1 (LME 재고):** 7r x 9c
- row 0: 헤더
- rows 1-6: Cu, Al, Zn, Pb, Ni, Sn
- cols: [label, prev, in, out, current, change, on_warrant, cancelled_warrant, cw_change]

**Table 6 (SHFE-LME Spread):** 8r x 10c
- row 0: 헤더
- rows 1-6: Cu, Al, Zn, Pb, Ni, Sn
- cols: [label, cny_rate, lme_3m_cny, lme_near_cny, tax%, lme_3m_incl, lme_near_incl, shfe_3m, shfe_near, premium_usd]
- Note: row 6 starts with 'SN' label, rows 1-5 start with None

**Table 4 (SHFE settle):** 6r x 1c — single column settle prices
- rows 0-5: Cu, Al, Zn, Pb, Ni, Sn settle in CNY

**Table 7 (Market Factors):** 3r x 9c
- row 0: values (S&P, Dow, 10Y, WTI, KRW, EUR, JPY, AUD, ZAR)
- row 1: changes
- row 2: % changes

- [ ] **Step 1: 테스트 작성 — page2 파싱**

Add to `tests/test_parser.py`:
```python
from parser.page2 import parse_inventory, parse_shfe_spread, parse_market_factors


SAMPLE_INVENTORY = [
    ['전일 반입 반출 금일 ON CANCELLED CW\n변동폭\n최종재고 (IN) (OUT) 최종재고 WRNT WRNT 변동폭', None, None, None, None, None, None, None, None],
    [None, '399725', '725', '1775', '398675', '-1050', '346250', '52425', '3550'],
    [None, '367050', '0', '2325', '364725', '-2325', '332600', '32125', '-2325'],
    [None, '98650', '0', '2400', '96250', '-2400', '86000', '10250', '-1825'],
    [None, '269575', '0', '1075', '268500', '-1075', '262825', '5675', '-1075'],
    [None, '277398', '0', '1002', '276396', '-1002', '262758', '13638', '-1002'],
    [None, '8590', '20', '135', '8475', '-115', '7940', '535', '65'],
]

SAMPLE_SHFE_SPREAD = [
    ['LME 3M LME 최근월물 ...header...', None, None, None, None, None, None, None, None, None],
    [None, '6.8265', '88,925', '88,561', '13%', '100,486', '100,074', '101,090', '101,080', '147.35'],
    [None, '6.8265', '23,961', '24,431', '13%', '27,076', '27,608', '24,485', '24,440', '-464.00'],
    [None, '6.8265', '23,138', '23,150', '13%', '26,146', '26,159', '23,700', '23,645', '-368.27'],
    [None, '6.8265', '13,291', '13,314', '13%', '15,019', '15,045', '16,675', '16,645', '234.35'],
    [None, '6.8265', '133,868', '132,853', '13%', '151,270', '150,124', '149,920', '149,430', '-101.66'],
    ['SN', '6.8265', '335,864', '335,154', '13%', '379,526', '378,724', '384,190', '383,270', '665.96'],
    ['Market Factors', None, None, None, None, None, None, None, None, None],
]

SAMPLE_MARKET_FACTORS = [
    ['7240.58', '49626.53', '110 22/32', '101.46', '1471.94', '1.1741', '156.9200', '0.7213', '16.6239'],
    ['31.57', '-25.61', '3/32', '-3.61', '-5.63', '0.0010', '0.40', '0.00', '-0.08'],
    ['0.44%', '-0.05%', '0.07%', '-3.44%', '-0.38%', '0.09%', '0.25%', '0.37%', '-0.49%'],
]


def test_parse_inventory_copper():
    result = parse_inventory(SAMPLE_INVENTORY)
    cu = result["copper"]
    assert cu["prev"] == 399725
    assert cu["in"] == 725
    assert cu["out"] == 1775
    assert cu["current"] == 398675
    assert cu["change"] == -1050
    assert cu["on_warrant"] == 346250
    assert cu["cancelled_warrant"] == 52425
    assert cu["cw_change"] == 3550


def test_parse_inventory_all_metals():
    result = parse_inventory(SAMPLE_INVENTORY)
    assert set(result.keys()) == {"copper", "aluminum", "zinc", "lead", "nickel", "tin"}


def test_parse_shfe_spread():
    result = parse_shfe_spread(SAMPLE_SHFE_SPREAD)
    assert result["cny_usd"] == 6.8265
    cu = result["metals"]["copper"]
    assert cu["shfe_settle"] == 101080
    assert cu["premium_usd"] == 147.35
    sn = result["metals"]["tin"]
    assert sn["premium_usd"] == 665.96


def test_parse_market_factors():
    result = parse_market_factors(SAMPLE_MARKET_FACTORS)
    assert result["krw_usd"] == 1471.94
    assert result["sp500"] == 7240.58
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/test_parser.py::test_parse_inventory_copper -v
```
Expected: FAIL

- [ ] **Step 3: page2.py 구현**

`parser/page2.py`:
```python
from parser.page1 import _num, _int_num, METALS_ORDER


def parse_inventory(table: list[list]) -> dict:
    """Parse Page 2 Table 1: LME 재고.

    Rows 1-6 = Cu, Al, Zn, Pb, Ni, Sn.
    Cols: [label, prev, in, out, current, change, on_warrant, cancelled_warrant, cw_change]
    """
    result = {}
    for i, metal in enumerate(METALS_ORDER):
        row = table[i + 1]
        result[metal] = {
            "prev": _int_num(row[1]),
            "in": _int_num(row[2]),
            "out": _int_num(row[3]),
            "current": _int_num(row[4]),
            "change": _int_num(row[5]),
            "on_warrant": _int_num(row[6]),
            "cancelled_warrant": _int_num(row[7]),
            "cw_change": _int_num(row[8]),
        }
    return result


def parse_shfe_spread(table: list[list]) -> dict:
    """Parse Page 2 Table 6: SHFE-LME Spread.

    Rows 1-6 = Cu, Al, Zn, Pb, Ni, Sn.
    Cols: [label, cny_rate, lme_3m_cny, lme_near_cny, tax, lme_3m_incl, lme_near_incl, shfe_3m, shfe_settle, premium_usd]
    """
    cny_usd = _num(table[1][1])
    metals = {}
    for i, metal in enumerate(METALS_ORDER):
        row = table[i + 1]
        metals[metal] = {
            "lme_3m_cny": _int_num(row[2]),
            "lme_near_cny": _int_num(row[3]),
            "lme_3m_incl_tax": _int_num(row[5]),
            "lme_near_incl_tax": _int_num(row[6]),
            "shfe_3m": _int_num(row[7]),
            "shfe_settle": _int_num(row[8]),
            "premium_usd": _num(row[9]),
        }
    return {"cny_usd": cny_usd, "metals": metals}


def parse_market_factors(table: list[list]) -> dict:
    """Parse Page 2 Table 7: Market Factors.

    Row 0: values, Row 1: changes, Row 2: % changes.
    Cols: [S&P, Dow, 10Y, WTI, KRW, EUR, JPY, AUD, ZAR]
    """
    values = table[0]
    changes = table[1]
    return {
        "sp500": _num(values[0]),
        "dow": _num(values[1]),
        "wti": _num(values[3]),
        "krw_usd": _num(values[4]),
        "eur_usd": _num(values[5]),
        "jpy_usd": _num(values[6]),
        "sp500_change": _num(changes[0]),
        "dow_change": _num(changes[1]),
        "wti_change": _num(changes[3]),
        "krw_change": _num(changes[4]),
    }
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/test_parser.py -v
```
Expected: all passed

- [ ] **Step 5: 커밋**

```bash
git add parser/page2.py tests/test_parser.py
git commit -m "feat: parser page2 — 재고, SHFE spread, market factors"
```

---

### Task 5: Parser — Page 3 (귀금속) + 통합 parse.py

**Files:**
- Create: `parser/page3.py`
- Create: `parser/parse.py`
- Modify: `tests/test_parser.py`

- [ ] **Step 1: 테스트 작성 — page3 + 통합**

Add to `tests/test_parser.py`:
```python
from parser.page3 import parse_precious_metals


SAMPLE_PRECIOUS = [
    ['SPOT LBMA / LPPM', None, None, None, None, None],
    ['', '현재가\n고가 저가', None, None, 'Price(구 London Fix)', None],
    ['', '(ASK)', None, None, 'AM PM', None],
    [None, '4642.23', '4660.07', '4560.40', '', None],
    [None, '76.180', '76.948', '73.018', '', None],
    [None, '2009.15', '2016.85', '1961.05', '1963.00', '1990.00'],
    [None, '1542.95', '1557.88', '1513.33', '1515.00', '1529.00'],
]


def test_parse_precious_metals():
    result = parse_precious_metals(SAMPLE_PRECIOUS)
    assert result["gold"]["spot"] == 4642.23
    assert result["gold"]["high"] == 4660.07
    assert result["gold"]["low"] == 4560.40
    assert result["silver"]["spot"] == 76.180
    assert result["platinum"]["spot"] == 2009.15
    assert result["platinum"]["am_fix"] == 1963.00
    assert result["palladium"]["pm_fix"] == 1529.00
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/test_parser.py::test_parse_precious_metals -v
```
Expected: FAIL

- [ ] **Step 3: page3.py 구현**

`parser/page3.py`:
```python
from parser.page1 import _num

PRECIOUS_ORDER = ["gold", "silver", "platinum", "palladium"]


def parse_precious_metals(table: list[list]) -> dict:
    """Parse Page 3 Table 1: LBMA/LPPM 귀금속.

    Rows 3-6 = Gold, Silver, Platinum, Palladium.
    Cols: [label, spot(ask), high, low, am_fix, pm_fix]
    Gold/Silver have no AM/PM fix (empty).
    """
    result = {}
    for i, metal in enumerate(PRECIOUS_ORDER):
        row = table[i + 3]
        entry = {
            "spot": _num(row[1]),
            "high": _num(row[2]),
            "low": _num(row[3]),
        }
        am = _num(row[4])
        pm = _num(row[5]) if len(row) > 5 else None
        if am is not None:
            entry["am_fix"] = am
        if pm is not None:
            entry["pm_fix"] = pm
        result[metal] = entry
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_parser.py -v
```
Expected: all passed

- [ ] **Step 5: 통합 parse.py 구현**

`parser/parse.py`:
```python
import argparse
import json
import re
from pathlib import Path
import pdfplumber

from parser.page1 import parse_lme_prices, parse_settlement, parse_ev_metals
from parser.page2 import parse_inventory, parse_shfe_spread, parse_market_factors
from parser.page3 import parse_precious_metals

METALS_ORDER = ["copper", "aluminum", "zinc", "lead", "nickel", "tin"]
DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def extract_date_from_pdf(pdf: pdfplumber.PDF) -> str:
    first_page_text = pdf.pages[0].extract_text() or ""
    for line in first_page_text.split("\n")[:5]:
        match = DATE_PATTERN.search(line)
        if match:
            return match.group(1)
    raise ValueError("Cannot extract date from PDF")


def parse_pdf(pdf_path: Path) -> dict:
    pdf = pdfplumber.open(pdf_path)
    if len(pdf.pages) < 3:
        raise ValueError(f"Expected at least 3 pages, got {len(pdf.pages)}")

    date = extract_date_from_pdf(pdf)

    # Page 1
    p1_tables = pdf.pages[0].extract_tables()
    if len(p1_tables) < 3:
        raise ValueError(f"Page 1: expected 3+ tables, got {len(p1_tables)}")
    lme_prices = parse_lme_prices(p1_tables[0])
    settlement = parse_settlement(p1_tables[1])
    ev_metals = parse_ev_metals(p1_tables[2])

    # Page 2
    p2_tables = pdf.pages[1].extract_tables()
    if len(p2_tables) < 7:
        raise ValueError(f"Page 2: expected 7+ tables, got {len(p2_tables)}")
    inventory = parse_inventory(p2_tables[0])
    shfe = parse_shfe_spread(p2_tables[5])
    market = parse_market_factors(p2_tables[6])

    # Page 3
    p3_tables = pdf.pages[2].extract_tables()
    if len(p3_tables) < 1:
        raise ValueError(f"Page 3: expected 1+ tables, got {len(p3_tables)}")
    precious = parse_precious_metals(p3_tables[0])

    # Combine per-metal data
    metals = {}
    for metal in METALS_ORDER:
        metals[metal] = {
            "lme": lme_prices[metal],
            "settlement": settlement[metal],
            "inventory": inventory[metal],
            "shfe": shfe["metals"][metal],
        }

    pdf.close()

    return {
        "date": date,
        "metals": metals,
        "ev_metals": ev_metals,
        "precious": precious,
        "fx": {"cny_usd": shfe["cny_usd"]},
        "market": market,
    }


def run(mode: str, data_dir: Path, tmp_dir: Path):
    daily_dir = data_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = tmp_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        pdfs = sorted(tmp_dir.glob("*.pdf"))
        manifest = [{"date": p.stem, "path": str(p)} for p in pdfs]

    parsed = 0
    for entry in manifest:
        pdf_path = Path(entry["path"])
        date = entry["date"]
        out_path = daily_dir / f"{date}.json"

        if out_path.exists():
            continue
        if not pdf_path.exists():
            print(f"SKIP (not found): {pdf_path}")
            continue

        try:
            data = parse_pdf(pdf_path)
            out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            parsed += 1
            print(f"Parsed: {date}")
        except Exception as e:
            print(f"ERROR parsing {date}: {e}")

    print(f"Total parsed: {parsed}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["latest", "backfill"], default="latest")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--tmp-dir", type=Path, default=Path("tmp/pdfs"))
    args = ap.parse_args()
    run(args.mode, args.data_dir, args.tmp_dir)
```

- [ ] **Step 6: 실제 PDF 파싱 통합 테스트 (수동)**

```bash
uv run python -m parser.parse --mode backfill --tmp-dir samples --data-dir data
cat data/daily/2026-05-01.json | python3 -m json.tool | head -50
```

Expected: JSON 출력에 6종 금속 데이터 정상 포함

- [ ] **Step 7: 커밋**

```bash
git add parser/page3.py parser/parse.py tests/test_parser.py
git commit -m "feat: parser 통합 — page3 귀금속 + parse.py 메인 진입점"
```

---

### Task 6: Exchange — 한국은행 환율 수집

**Files:**
- Create: `exchange/__init__.py`
- Create: `exchange/fetch_krw.py`
- Create: `tests/test_exchange.py`

한국은행 ECOS API: `https://ecos.bok.or.kr/api/StatisticSearch/{API_KEY}/json/kr/1/100/731Y001/D/{start}/{end}/0000001`
- 731Y001: 원/달러 환율 통계표
- 0000001: 매매기준율

- [ ] **Step 1: 테스트 작성**

`tests/test_exchange.py`:
```python
from exchange.fetch_krw import parse_bok_response


SAMPLE_RESPONSE = {
    "StatisticSearch": {
        "row": [
            {"TIME": "20260501", "DATA_VALUE": "1365.2"},
            {"TIME": "20260430", "DATA_VALUE": "1370.5"},
            {"TIME": "20260429", "DATA_VALUE": "1368.0"},
        ]
    }
}


def test_parse_bok_response():
    rates = parse_bok_response(SAMPLE_RESPONSE)
    assert len(rates) == 3
    assert rates[0]["date"] == "2026-05-01"
    assert rates[0]["rate"] == 1365.2
    assert rates[2]["date"] == "2026-04-29"


def test_parse_bok_response_empty():
    rates = parse_bok_response({"StatisticSearch": {"row": []}})
    assert rates == []
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/test_exchange.py -v
```
Expected: FAIL

- [ ] **Step 3: fetch_krw.py 구현**

`exchange/__init__.py`: 빈 파일

`exchange/fetch_krw.py`:
```python
import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import requests

BOK_API_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
STAT_CODE = "731Y001"
ITEM_CODE = "0000001"


def parse_bok_response(data: dict) -> list[dict]:
    rows = data.get("StatisticSearch", {}).get("row", [])
    rates = []
    for row in rows:
        time_str = row["TIME"]
        date = f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:8]}"
        rates.append({
            "date": date,
            "rate": float(row["DATA_VALUE"]),
        })
    return rates


def fetch_rates(api_key: str, start_date: str, end_date: str) -> list[dict]:
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")
    url = f"{BOK_API_URL}/{api_key}/json/kr/1/365/{STAT_CODE}/D/{start}/{end}/{ITEM_CODE}"
    resp = requests.get(url)
    resp.raise_for_status()
    return parse_bok_response(resp.json())


def run(data_dir: Path, api_key: str, start_date: str | None = None):
    exchange_dir = data_dir / "exchange"
    exchange_dir.mkdir(parents=True, exist_ok=True)
    out_path = exchange_dir / "usd_krw.json"

    if out_path.exists():
        existing = json.loads(out_path.read_text())
        existing_rates = existing.get("rates", [])
    else:
        existing_rates = []

    existing_dates = {r["date"] for r in existing_rates}

    if start_date is None:
        start_date = "2026-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")

    new_rates = fetch_rates(api_key, start_date, end_date)
    for rate in new_rates:
        if rate["date"] not in existing_dates:
            existing_rates.append(rate)
            existing_dates.add(rate["date"])

    existing_rates.sort(key=lambda r: r["date"], reverse=True)

    output = {
        "rates": existing_rates,
        "last_updated": existing_rates[0]["date"] if existing_rates else None,
    }
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Exchange rates: {len(existing_rates)} entries, latest: {output['last_updated']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--start-date", type=str, default=None)
    args = ap.parse_args()
    api_key = os.environ.get("BOK_API_KEY", "")
    if not api_key:
        print("ERROR: BOK_API_KEY environment variable not set")
        exit(1)
    run(args.data_dir, api_key, args.start_date)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_exchange.py -v
```
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add exchange/ tests/test_exchange.py
git commit -m "feat: exchange — 한국은행 ECOS API 환율 수집"
```

---

### Task 7: Builder — daily JSON → metals 시계열 + index.json

**Files:**
- Create: `builder/__init__.py`
- Create: `builder/build.py`
- Create: `tests/test_builder.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_builder.py`:
```python
import json
from pathlib import Path
from builder.build import build_metal_timeseries, build_index


DAILY_SAMPLE = {
    "date": "2026-05-01",
    "metals": {
        "copper": {
            "lme": {
                "cash": {"prev_close": 12942.76, "open": 12968.90, "high": 13041.90, "low": 12875.90, "close": 12896.40, "change": -46.36},
                "3m": {"prev_close": 13017.00, "open": 13047.00, "high": 13120.00, "low": 12954.00, "close": 12974.50, "change": -42.50},
                "bid": -82.10, "ask": -78.10, "open_interest": 265325,
            },
            "settlement": {"cash": 12895.00, "3m": 12967.00, "monthly_avg": {"cash": 12891.38, "3m": 12969.88}, "prev_monthly_avg": {"cash": 12916.40, "3m": 12996.50}, "forwards": {"m1": 12943.14, "m2": 12970.73, "m3": 12987.01}},
            "inventory": {"prev": 399725, "in": 725, "out": 1775, "current": 398675, "change": -1050, "on_warrant": 346250, "cancelled_warrant": 52425, "cw_change": 3550},
            "shfe": {"lme_3m_cny": 88925, "lme_near_cny": 88561, "lme_3m_incl_tax": 100486, "lme_near_incl_tax": 100074, "shfe_3m": 101090, "shfe_settle": 101080, "premium_usd": 147.35},
        },
    },
    "ev_metals": {"cobalt": {"may26": 57761.04}},
    "precious": {"gold": {"spot": 4642.23}},
    "fx": {"cny_usd": 6.8265},
    "market": {"krw_usd": 1471.94},
}

EXCHANGE_SAMPLE = {
    "rates": [
        {"date": "2026-05-01", "rate": 1365.20},
    ],
    "last_updated": "2026-05-01",
}


def test_build_metal_timeseries():
    dailies = [DAILY_SAMPLE]
    rates_map = {"2026-05-01": 1365.20}
    result = build_metal_timeseries("copper", dailies, rates_map)
    assert result["metal"] == "copper"
    assert result["symbol"] == "Cu"
    assert len(result["data"]) == 1
    day = result["data"][0]
    assert day["date"] == "2026-05-01"
    assert day["lme"]["cash"]["close"] == 12896.40
    assert day["inventory"]["current"] == 398675
    assert day["krw"]["cash"] == round(12896.40 * 1365.20)
    assert day["krw"]["rate"] == 1365.20


def test_build_index():
    dates = ["2026-01-02", "2026-05-01"]
    result = build_index(dates)
    assert result["last_updated"] == "2026-05-01"
    assert result["total_days"] == 2
    assert result["date_range"]["from"] == "2026-01-02"
    assert result["date_range"]["to"] == "2026-05-01"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/test_builder.py -v
```
Expected: FAIL

- [ ] **Step 3: build.py 구현**

`builder/__init__.py`: 빈 파일

`builder/build.py`:
```python
import argparse
import json
from pathlib import Path

METALS = {
    "copper": {"symbol": "Cu", "unit": "$/ton"},
    "aluminum": {"symbol": "Al", "unit": "$/ton"},
    "zinc": {"symbol": "Zn", "unit": "$/ton"},
    "lead": {"symbol": "Pb", "unit": "$/ton"},
    "nickel": {"symbol": "Ni", "unit": "$/ton"},
    "tin": {"symbol": "Sn", "unit": "$/ton"},
}


def build_metal_timeseries(metal: str, dailies: list[dict], rates_map: dict[str, float]) -> dict:
    info = METALS[metal]
    data = []
    for daily in dailies:
        date = daily["date"]
        m = daily["metals"].get(metal)
        if not m:
            continue

        rate = rates_map.get(date)
        cash_close = None
        tm_close = None

        lme = m.get("lme", {})
        if "cash" in lme:
            cash_close = lme["cash"].get("close")
        if "3m" in lme:
            tm_close = lme["3m"].get("close")

        krw = {}
        if rate:
            if cash_close is not None:
                krw["cash"] = round(cash_close * rate)
            if tm_close is not None:
                krw["3m"] = round(tm_close * rate)
            krw["rate"] = rate

        data.append({
            "date": date,
            "lme": lme,
            "settlement": m.get("settlement", {}),
            "inventory": m.get("inventory", {}),
            "shfe": m.get("shfe", {}),
            "krw": krw,
        })

    data.sort(key=lambda d: d["date"], reverse=True)

    return {
        "metal": metal,
        "symbol": info["symbol"],
        "unit": info["unit"],
        "last_updated": data[0]["date"] if data else None,
        "data": data,
    }


def build_index(dates: list[str]) -> dict:
    sorted_dates = sorted(dates)
    return {
        "last_updated": sorted_dates[-1] if sorted_dates else None,
        "metals": list(METALS.keys()),
        "total_days": len(sorted_dates),
        "date_range": {
            "from": sorted_dates[0] if sorted_dates else None,
            "to": sorted_dates[-1] if sorted_dates else None,
        },
    }


def run(data_dir: Path):
    daily_dir = data_dir / "daily"
    metals_dir = data_dir / "metals"
    metals_dir.mkdir(parents=True, exist_ok=True)

    # Load all daily JSONs
    dailies = []
    for f in sorted(daily_dir.glob("*.json")):
        dailies.append(json.loads(f.read_text()))

    if not dailies:
        print("No daily data found")
        return

    # Load exchange rates
    exchange_path = data_dir / "exchange" / "usd_krw.json"
    rates_map = {}
    if exchange_path.exists():
        exchange_data = json.loads(exchange_path.read_text())
        for r in exchange_data.get("rates", []):
            rates_map[r["date"]] = r["rate"]

    # Build per-metal timeseries
    for metal in METALS:
        ts = build_metal_timeseries(metal, dailies, rates_map)
        out = metals_dir / f"{metal}.json"
        out.write_text(json.dumps(ts, ensure_ascii=False, indent=2))
        print(f"Built: {metal} ({len(ts['data'])} days)")

    # Build index
    dates = [d["date"] for d in dailies]
    index = build_index(dates)
    index_path = data_dir / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2))
    print(f"Index: {index['total_days']} days, {index['date_range']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    args = ap.parse_args()
    run(args.data_dir)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_builder.py -v
```
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add builder/ tests/test_builder.py
git commit -m "feat: builder — daily→metals 시계열 변환 + index.json"
```

---

### Task 8: 소급 데이터 수집 (2026년 전체)

**Files:** 없음 (실행만)

- [ ] **Step 1: 2026년 PDF 소급 다운로드**

```bash
mkdir -p tmp/pdfs
uv run python -m scraper.download --mode backfill --data-dir data --tmp-dir tmp/pdfs --max-pages 7
```

Expected: ~80-100개 PDF 다운로드, `tmp/pdfs/manifest.json` 생성

- [ ] **Step 2: 전체 PDF 파싱**

```bash
uv run python -m parser.parse --mode backfill --data-dir data --tmp-dir tmp/pdfs
```

Expected: data/daily/ 에 ~80-100개 JSON 생성

- [ ] **Step 3: 파싱 결과 검증**

```bash
ls data/daily/*.json | wc -l
# 첫 번째와 마지막 파일 확인
cat data/daily/$(ls data/daily/ | head -1) | python3 -m json.tool | head -20
cat data/daily/$(ls data/daily/ | tail -1) | python3 -m json.tool | head -20
```

Expected: 6종 금속 데이터 정상 포함

- [ ] **Step 4: Builder 실행**

```bash
uv run python -m builder.build --data-dir data
```

Expected: data/metals/ 에 6개 JSON + data/index.json 생성

- [ ] **Step 5: 결과 검증 + 커밋**

```bash
cat data/index.json | python3 -m json.tool
wc -c data/metals/*.json
git add data/
git commit -m "data: 2026년 소급 데이터 수집"
```

---

### Task 9: GitHub Actions 워크플로우

**Files:**
- Create: `.github/workflows/collect.yml`

- [ ] **Step 1: 워크플로우 작성**

`.github/workflows/collect.yml`:
```yaml
name: Collect Metal Data

on:
  schedule:
    - cron: '0 10 * * 1-5'  # UTC 10:00 = KST 19:00, 평일
  workflow_dispatch:

permissions:
  contents: write

jobs:
  collect:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        run: uv sync

      - name: Download latest PDF
        run: uv run python -m scraper.download --mode latest --data-dir data --tmp-dir tmp/pdfs

      - name: Parse PDF
        run: uv run python -m parser.parse --mode latest --data-dir data --tmp-dir tmp/pdfs

      - name: Fetch exchange rates
        env:
          BOK_API_KEY: ${{ secrets.BOK_API_KEY }}
        run: uv run python -m exchange.fetch_krw --data-dir data

      - name: Build timeseries
        run: uv run python -m builder.build --data-dir data

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          if git diff --staged --quiet; then
            echo "No changes to commit"
          else
            git commit -m "data: $(date +%Y-%m-%d) 시세 업데이트"
            git push
          fi
```

- [ ] **Step 2: 커밋**

```bash
mkdir -p .github/workflows
git add .github/workflows/collect.yml
git commit -m "ci: GitHub Actions 일일 데이터 수집 워크플로우"
```

---

### Task 10: 모바일 프론트엔드 — HTML 골격 + 스크롤 UX

**Files:**
- Create: `site/index.html`
- Create: `site/style.css`
- Create: `site/app.js`

- [ ] **Step 1: index.html**

`site/index.html`:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>비철금속 시세</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header id="header">
    <span id="last-updated"></span>
    <span id="krw-rate"></span>
  </header>

  <nav id="metal-nav">
    <button data-metal="copper" class="active">Cu</button>
    <button data-metal="aluminum">Al</button>
    <button data-metal="zinc">Zn</button>
    <button data-metal="nickel">Ni</button>
    <button data-metal="lead">Pb</button>
    <button data-metal="tin">Sn</button>
  </nav>

  <main id="scroll-container">
    <section class="metal-section" data-metal="copper"></section>
    <section class="metal-section" data-metal="aluminum"></section>
    <section class="metal-section" data-metal="zinc"></section>
    <section class="metal-section" data-metal="nickel"></section>
    <section class="metal-section" data-metal="lead"></section>
    <section class="metal-section" data-metal="tin"></section>
  </main>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: style.css — 스크롤 스냅 + 모바일 레이아웃**

`site/style.css`:
```css
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg: #0f1117;
  --card: #1a1d27;
  --border: #2a2d37;
  --text: #e4e4e7;
  --muted: #71717a;
  --up: #22c55e;
  --down: #ef4444;
  --accent: #3b82f6;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
  height: 100dvh;
}

header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  color: var(--muted);
}

#metal-nav {
  position: fixed;
  top: 33px;
  left: 0;
  right: 0;
  z-index: 10;
  display: flex;
  gap: 4px;
  padding: 8px 16px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
}

#metal-nav button {
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--muted);
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

#metal-nav button.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

#scroll-container {
  height: 100dvh;
  overflow-y: scroll;
  scroll-snap-type: y mandatory;
  padding-top: 73px;
}

.metal-section {
  min-height: calc(100dvh - 73px);
  scroll-snap-align: start;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
}

.card-title {
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.metal-name {
  font-size: 24px;
  font-weight: 700;
}

.metal-symbol {
  color: var(--muted);
  font-size: 14px;
  margin-left: 8px;
}

.price-main {
  font-size: 32px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.change {
  font-size: 16px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.change.up { color: var(--up); }
.change.down { color: var(--down); }

.data-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.data-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.data-label {
  font-size: 11px;
  color: var(--muted);
}

.data-value {
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.chart-container {
  height: 120px;
  position: relative;
}

.chart-container svg {
  width: 100%;
  height: 100%;
}
```

- [ ] **Step 3: app.js — 데이터 로딩 + 렌더링**

`site/app.js`:
```javascript
const DATA_BASE = '../data';
const METAL_NAMES = {
  copper: '전기동', aluminum: '알루미늄', zinc: '아연',
  nickel: '니켈', lead: '납', tin: '주석',
};
const METAL_SYMBOLS = {
  copper: 'Cu', aluminum: 'Al', zinc: 'Zn',
  nickel: 'Ni', lead: 'Pb', tin: 'Sn',
};

const cache = {};

function fmt(n) {
  if (n == null) return '—';
  return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
}

function fmtInt(n) {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('en-US');
}

function changeClass(n) {
  if (n == null || n === 0) return '';
  return n > 0 ? 'up' : 'down';
}

function changePrefix(n) {
  if (n == null) return '';
  return n > 0 ? '+' : '';
}

function miniChart(data, key) {
  const values = data.slice(0, 30).reverse().map(d => {
    const lme = d.lme || {};
    const tm = lme['3m'] || lme['cash'] || {};
    return tm[key] ?? tm['close'];
  }).filter(v => v != null);

  if (values.length < 2) return '';

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 100;
  const h = 100;
  const step = w / (values.length - 1);

  const points = values.map((v, i) =>
    `${(i * step).toFixed(1)},${(h - ((v - min) / range) * h).toFixed(1)}`
  ).join(' ');

  const trending = values[values.length - 1] >= values[0];
  const color = trending ? 'var(--up)' : 'var(--down)';

  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/>
  </svg>`;
}

function renderSection(metal, ts) {
  const section = document.querySelector(`.metal-section[data-metal="${metal}"]`);
  if (!ts || !ts.data || ts.data.length === 0) {
    section.innerHTML = `<div class="card"><div class="card-title">데이터 없음</div></div>`;
    return;
  }

  const latest = ts.data[0];
  const lme = latest.lme || {};
  const cash = lme.cash || {};
  const tm = lme['3m'] || {};
  const inv = latest.inventory || {};
  const sett = latest.settlement || {};
  const shfe = latest.shfe || {};
  const krw = latest.krw || {};

  const mainPrice = tm.close ?? cash.close;
  const mainChange = tm.change ?? cash.change;

  section.innerHTML = `
    <div class="card">
      <div style="display:flex;align-items:baseline;justify-content:space-between">
        <div>
          <span class="metal-name">${METAL_NAMES[metal]}</span>
          <span class="metal-symbol">${METAL_SYMBOLS[metal]}</span>
        </div>
        <div style="text-align:right">
          <div class="price-main">$${fmt(mainPrice)}</div>
          <div class="change ${changeClass(mainChange)}">${changePrefix(mainChange)}${fmt(mainChange)}</div>
        </div>
      </div>
      <div class="chart-container">${miniChart(ts.data, 'close')}</div>
    </div>

    <div class="card">
      <div class="card-title">LME 시세</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">Cash</span>
          <span class="data-value">${fmt(cash.close)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">3M</span>
          <span class="data-value">${fmt(tm.close)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">시가</span>
          <span class="data-value">${fmt(tm.open ?? cash.open)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">고가</span>
          <span class="data-value">${fmt(tm.high ?? cash.high)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">저가</span>
          <span class="data-value">${fmt(tm.low ?? cash.low)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">미결제약정</span>
          <span class="data-value">${fmtInt(lme.open_interest)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">Bid</span>
          <span class="data-value">${fmt(lme.bid)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">Ask</span>
          <span class="data-value">${fmt(lme.ask)}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">정산가</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">Cash</span>
          <span class="data-value">${fmt(sett.cash)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">3M</span>
          <span class="data-value">${fmt(sett['3m'])}</span>
        </div>
        <div class="data-item">
          <span class="data-label">당월평균 Cash</span>
          <span class="data-value">${fmt(sett.monthly_avg?.cash)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">당월평균 3M</span>
          <span class="data-value">${fmt(sett.monthly_avg?.['3m'])}</span>
        </div>
        <div class="data-item">
          <span class="data-label">전월평균 Cash</span>
          <span class="data-value">${fmt(sett.prev_monthly_avg?.cash)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">전월평균 3M</span>
          <span class="data-value">${fmt(sett.prev_monthly_avg?.['3m'])}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">LME 재고</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">현재고</span>
          <span class="data-value">${fmtInt(inv.current)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">변동</span>
          <span class="data-value change ${changeClass(inv.change)}">${changePrefix(inv.change)}${fmtInt(inv.change)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">반입</span>
          <span class="data-value">${fmtInt(inv['in'])}</span>
        </div>
        <div class="data-item">
          <span class="data-label">반출</span>
          <span class="data-value">${fmtInt(inv.out)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">On Warrant</span>
          <span class="data-value">${fmtInt(inv.on_warrant)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">Cancelled Warrant</span>
          <span class="data-value">${fmtInt(inv.cancelled_warrant)}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">SHFE 비교</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">SHFE 정산가</span>
          <span class="data-value">${fmtInt(shfe.shfe_settle)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">프리미엄 (USD)</span>
          <span class="data-value change ${changeClass(shfe.premium_usd)}">${fmt(shfe.premium_usd)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">LME 3M (CNY)</span>
          <span class="data-value">${fmtInt(shfe.lme_3m_cny)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">LME 3M (세금포함)</span>
          <span class="data-value">${fmtInt(shfe.lme_3m_incl_tax)}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">원화 환산</div>
      <div class="data-grid">
        <div class="data-item">
          <span class="data-label">Cash (KRW)</span>
          <span class="data-value">₩${fmtInt(krw.cash)}</span>
        </div>
        <div class="data-item">
          <span class="data-label">3M (KRW)</span>
          <span class="data-value">₩${fmtInt(krw['3m'])}</span>
        </div>
        <div class="data-item">
          <span class="data-label">적용환율</span>
          <span class="data-value">${fmt(krw.rate)}</span>
        </div>
      </div>
    </div>
  `;
}

async function loadMetal(metal) {
  if (cache[metal]) return cache[metal];
  const resp = await fetch(`${DATA_BASE}/metals/${metal}.json`);
  if (!resp.ok) return null;
  const data = await resp.json();
  cache[metal] = data;
  return data;
}

async function loadIndex() {
  const resp = await fetch(`${DATA_BASE}/index.json`);
  if (!resp.ok) return null;
  return resp.json();
}

function updateNav(activeMetal) {
  document.querySelectorAll('#metal-nav button').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.metal === activeMetal);
  });
}

async function init() {
  const index = await loadIndex();
  if (index) {
    document.getElementById('last-updated').textContent = `업데이트: ${index.last_updated}`;
  }

  // Load and render all metals
  const metals = ['copper', 'aluminum', 'zinc', 'nickel', 'lead', 'tin'];
  for (const metal of metals) {
    const ts = await loadMetal(metal);
    if (ts) renderSection(metal, ts);
  }

  // Show KRW rate from first loaded metal
  const firstData = cache['copper'];
  if (firstData?.data?.[0]?.krw?.rate) {
    document.getElementById('krw-rate').textContent = `USD/KRW: ${fmt(firstData.data[0].krw.rate)}`;
  }

  // Scroll snap → nav sync
  const container = document.getElementById('scroll-container');
  const sections = document.querySelectorAll('.metal-section');

  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        updateNav(entry.target.dataset.metal);
      }
    }
  }, { root: container, threshold: 0.5 });

  sections.forEach(s => observer.observe(s));

  // Nav click → scroll to section
  document.querySelectorAll('#metal-nav button').forEach(btn => {
    btn.addEventListener('click', () => {
      const section = document.querySelector(`.metal-section[data-metal="${btn.dataset.metal}"]`);
      section.scrollIntoView({ behavior: 'smooth' });
    });
  });
}

init();
```

- [ ] **Step 4: GitHub Pages 배포 설정**

GitHub repo settings에서:
1. Settings → Pages → Source: Deploy from a branch
2. Branch: main, folder: / (root)

또는 `.github/workflows/collect.yml` 수정 불필요 — `site/` 폴더가 root에 있으므로 `index.html` 경로는 `site/index.html`.

GitHub Pages의 base URL을 위해, `site/app.js`의 `DATA_BASE` 경로가 올바른지 확인. GitHub Pages가 `site/index.html`을 서빙하면 `../data/` 경로로 data 접근 가능.

- [ ] **Step 5: 로컬 테스트**

```bash
cd site && python3 -m http.server 8080
```

브라우저에서 `http://localhost:8080` 열고:
- 6종 금속 스크롤 전환 동작
- 시세/재고/정산가/SHFE/환율 카드 표시
- 미니 차트 표시
- 상하 스크롤 시 네비게이션 하이라이트 동기화

- [ ] **Step 6: 커밋**

```bash
git add site/
git commit -m "feat: 모바일 프론트엔드 — 스크롤 기반 비철금속 대시보드"
```

---

### Task 11: 최종 점검 + README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README 작성**

`README.md`:
```markdown
# 비철금속 시세 대시보드

NH선물 일일금속시황 PDF 자동 수집 → 구조화 → 모바일 대시보드.

## 데이터

- **소스:** NH선물 Daily Metal Bulletin (futures.co.kr)
- **환율:** 한국은행 ECOS API (USD/KRW)
- **갱신:** GitHub Actions, 매일 KST 19:00 (평일)
- **광물:** 전기동(Cu), 알루미늄(Al), 아연(Zn), 니켈(Ni), 납(Pb), 주석(Sn)

## 사용법

### 소급 수집

```bash
uv sync
uv run python -m scraper.download --mode backfill --max-pages 7
uv run python -m parser.parse --mode backfill
BOK_API_KEY=xxx uv run python -m exchange.fetch_krw
uv run python -m builder.build
```

### 로컬 프론트엔드

```bash
cd site && python3 -m http.server 8080
```

## GitHub Secrets

- `BOK_API_KEY`: 한국은행 ECOS Open API 키
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: all passed

- [ ] **Step 3: 최종 커밋**

```bash
git add README.md
git commit -m "docs: README 작성"
```
