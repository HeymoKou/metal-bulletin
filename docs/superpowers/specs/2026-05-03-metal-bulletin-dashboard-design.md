# 비철금속 시세 대시보드 설계

## 개요

NH선물(futures.co.kr)의 일일 비철금속 시황 PDF를 자동 수집·파싱하여 구조화된 JSON으로 저장하고, GitHub Pages로 모바일 대시보드를 서빙한다. 한국은행 ECOS API로 USD/KRW 환율을 반영한다.

대상 사용자: 비철금속 전문 업체. 풀 데이터 제공 (시세, 재고, 정산가, SHFE 비교 등).

## 아키텍처

```
GitHub Actions (cron, 매일)
    │
    ├── scraper  ─→  PDF 다운로드 (임시, git 미포함)
    ├── parser   ─→  PDF → data/daily/{date}.json
    ├── exchange ─→  한국은행 API → data/exchange/usd_krw.json
    ├── builder  ─→  daily + exchange → data/metals/{metal}.json
    └── git push ─→  data/ 변경분 커밋
    
GitHub Pages
    └── site/    ─→  정적 HTML/JS, metals/*.json fetch해서 렌더링
```

## 프로젝트 구조

```
metal-bulletin/
├── scraper/          # PDF 다운로드
│   └── download.py
├── parser/           # PDF → 구조화 데이터
│   └── parse.py
├── exchange/         # 한국은행 환율 수집
│   └── fetch_krw.py
├── builder/          # daily JSON → 광물별 시계열 JSON
│   └── build.py
├── data/
│   ├── daily/        # 영업일별 파싱 결과 (원본 기록)
│   │   ├── 2026-01-02.json
│   │   └── ...
│   ├── metals/       # 광물별 시계열 (프론트엔드용)
│   │   ├── copper.json
│   │   ├── aluminum.json
│   │   ├── zinc.json
│   │   ├── nickel.json
│   │   ├── lead.json
│   │   └── tin.json
│   ├── exchange/
│   │   └── usd_krw.json
│   └── index.json    # 최신일자, 메타데이터
├── site/             # GitHub Pages 프론트엔드
│   ├── index.html
│   ├── app.js
│   └── style.css
├── .github/
│   └── workflows/
│       └── collect.yml
├── pyproject.toml
└── README.md
```

## Phase 1: 데이터 파이프라인

### 1-1. Scraper (scraper/download.py)

futures.co.kr 게시판에서 PDF 다운로드.

**동작:**
1. requests.Session()으로 메인 페이지 접속 → JSESSIONID 획득
2. 게시판 페이지 순회 (POST /bbs/boardSearch.do)
3. HTML에서 atchFileId, FileNm 추출
4. PDF 다운로드 → 임시 디렉토리 (tmp/pdfs/)

**페이지네이션:**
- POST body: `bbsId=BBSMSTR_000000000251&pageIndex={N}&url=content/research/KR_interestRate`
- 15개/페이지, 2026년 데이터는 페이지 1~7

**다운로드 대상:** `NHF Daily Metal Bulletin {YYYYMMDD}.pdf`만. LME Valuation은 같은 atchFileId에서 두번째 파일이라 0 bytes 반환 — 제외.

**모드:**
- `--backfill`: 지정 기간 전체 소급 다운로드
- `--latest`: 가장 최근 게시글만 (Actions 일일 실행용)
- 이미 data/daily/ 에 해당 날짜 JSON 있으면 스킵

### 1-2. Parser (parser/parse.py)

PDF에서 비철금속 6종 데이터 추출 → JSON.

**추출 대상 (광물별: Cu, Al, Zn, Ni, Pb, Sn):**

```json
{
  "date": "2026-05-01",
  "metals": {
    "copper": {
      "lme": {
        "cash": { "close": 12896.40, "change": -46.36 },
        "3m": { "open": 13047.00, "high": 13120.00, "low": 12954.00, "close": 12974.50, "change": -42.50 },
        "bid": -82.10,
        "ask": -78.10,
        "open_interest": 265325
      },
      "settlement": {
        "cash": 12895.00,
        "3m": 12967.00,
        "monthly_avg": { "cash": 12891.38, "3m": 12969.88 },
        "prev_monthly_avg": { "cash": 12916.40, "3m": 12996.50 },
        "forwards": { "may": 12943.14, "jun": 12970.73, "jul": 12987.01 }
      },
      "inventory": {
        "prev": 399725,
        "in": 725,
        "out": 1775,
        "current": 398675,
        "change": -1050,
        "on_warrant": 346250,
        "cancelled_warrant": 52425,
        "cw_change": 3550
      },
      "shfe": {
        "settle": 101080,
        "lme_shfe_premium": 147.35
      }
    }
  },
  "ev_metals": {
    "cobalt": { "may26": 57761.04, "jul26": 59634.97 },
    "lithium": { "may26": 45966.33 }
  },
  "precious": {
    "gold": { "spot": 4642.23, "high": 4660.07, "low": 4560.40 },
    "silver": { "spot": 76.180, "high": 76.948, "low": 73.018 }
  },
  "fx": {
    "cny_usd": 6.8265
  }
}
```

**파싱 전략:**
- pdfplumber로 테이블 추출
- Page 1 Table 1: LME 시세 (행 순서: Cu, Cu 3M, Al, Al 3M, Zn, Zn 3M, Ni, Ni 3M, Pb, Pb 3M, Sn, Sn 3M — 실제 매핑은 PDF 샘플로 확정)
- Page 1 Table 2: LME 정산가
- Page 2 Table 1: LME 재고
- Page 2 Table 6: SHFE 비교
- 검증: 필수 필드 누락 시 에러 로깅, 빈 JSON 생성하지 않음

### 1-3. Exchange (exchange/fetch_krw.py)

한국은행 ECOS Open API로 USD/KRW 일일 환율 수집.

**출력:** data/exchange/usd_krw.json
```json
{
  "rates": [
    { "date": "2026-05-01", "rate": 1365.20 },
    { "date": "2026-04-30", "rate": 1370.50 }
  ],
  "last_updated": "2026-05-01"
}
```

API 키: GitHub Secrets (`BOK_API_KEY`)로 관리.

### 1-4. Builder (builder/build.py)

daily JSON + exchange JSON → 광물별 시계열 JSON 생성.

**출력 예시:** data/metals/copper.json
```json
{
  "metal": "copper",
  "symbol": "Cu",
  "unit": "$/ton",
  "last_updated": "2026-05-01",
  "data": [
    {
      "date": "2026-05-01",
      "lme": { "cash": 12896.40, "3m": 12974.50, "change": -42.50 },
      "settlement": { "cash": 12895.00, "3m": 12967.00 },
      "inventory": { "current": 398675, "change": -1050, "cancelled_warrant": 52425 },
      "shfe": { "settle": 101080, "premium": 147.35 },
      "krw": { "cash": 17605843, "3m": 17712590, "rate": 1365.20 }
    }
  ]
}
```

data/index.json:
```json
{
  "last_updated": "2026-05-01",
  "metals": ["copper", "aluminum", "zinc", "nickel", "lead", "tin"],
  "total_days": 83,
  "date_range": { "from": "2026-01-02", "to": "2026-05-01" }
}
```

## Phase 2: GitHub Actions 자동화

### Workflow (.github/workflows/collect.yml)

```yaml
schedule: cron "0 10 * * 1-5"  # UTC 10:00 = KST 19:00, 평일만
```

1. uv 설치 + 의존성
2. `uv run python scraper/download.py --latest`
3. `uv run python parser/parse.py --latest`
4. `uv run python exchange/fetch_krw.py`
5. `uv run python builder/build.py`
6. 변경분 있으면 git commit + push

수동 dispatch도 가능 (workflow_dispatch).

## Phase 3: 모바일 프론트엔드

GitHub Pages 정적 사이트. 스크롤 기반 광물 전환 UX.

**UX:**
- 풀스크린 스크롤: 한 화면 = 한 광물
- 스크롤 다운 → Cu → Al → Zn → Ni → Pb → Sn
- 각 광물 섹션: 시세 카드, 재고 카드, SHFE 비교, 원화 환산가
- 변동폭: 상승 녹색, 하락 적색, 수치 + %
- 미니 차트: 최근 30일 시세/재고 추이 (inline SVG 또는 Canvas)
- 상단: 최종 업데이트 일시 + USD/KRW 환율

**데이터 로딩:**
- 초기: index.json fetch → 첫 광물(copper.json) fetch
- 스크롤 시: 다음 광물 JSON lazy fetch
- 캐시: 한번 로드한 광물은 메모리 보관

**기술:**
- 순수 HTML/CSS/JS (프레임워크 없음)
- CSS scroll-snap으로 광물 전환
- 라이브러리 최소화 — 차트만 경량 라이브러리 또는 직접 SVG

## 검증 & 안전장치

- **파싱 검증:** 필수 6종 금속 데이터 누락 시 커밋 안 함, Actions 실패 알림
- **데이터 범위 검증:** 가격이 이전 대비 ±50% 이상이면 경고 (오파싱 감지)
- **PDF 구조 변경 감지:** 테이블 수/컬럼 수가 예상과 다르면 에러
- **git diff 추적:** daily JSON이 git에 있으므로 변경 이력 자동 보존
