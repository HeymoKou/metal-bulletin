# 비철금속 시세 대시보드 · LME Non-Ferrous Desk

NH선물 일일금속시황 PDF 자동 수집 → 구조화 JSON → 모바일 대시보드. 서버리스 (GitHub Pages).

## 데이터

- **소스:** NH선물 Daily Metal Bulletin (https://www.futures.co.kr)
- **광물:** Cu, Al, Zn, Ni, Pb, Sn (LME 6종)
- **필드:** LME 시세(Cash/3M, OHLC, bid/ask, OI), 정산가(+선물커브), 재고(반입/반출/CW), SHFE 비교(프리미엄), EV metals, 귀금속, KRW 환산
- **환율:** 한국은행 ECOS API 우선, PDF 내장 환율 자동 폴백 (`source` 필드 추적)
- **이력:** 최대 10년 소급 (가용 페이지 한계까지)

## 아키텍처

```
metal-bulletin/
├── scraper/          PDF 다운로드 (세션 + 페이지네이션)
├── parser/           PDF → daily JSON (page1/2/3 분리)
├── exchange/         한국은행 ECOS 환율 수집
├── builder/          daily → 광물별 연도 분할 시계열
├── data/
│   ├── daily/        {YYYY-MM-DD}.json (원본)
│   ├── metals/
│   │   └── {metal}/
│   │       ├── latest.json   최근 90일 (즉시 표시)
│   │       └── {YYYY}.json   연도별 풀 데이터
│   ├── exchange/usd_krw.json
│   └── index.json    메타 (가용 연도, 마지막 갱신)
├── site/             정적 vanilla JS 대시보드 (Bloomberg-density)
├── .github/workflows/
│   ├── collect.yml   매일 KST 19:00 자동 수집
│   └── pages.yml     site + data → GitHub Pages
└── tests/
```

**프론트 로딩 전략:** 초기 `index.json` + 6종 `latest.json` (90일) → 즉시 렌더링. 차트 확장 시 풀 시계열 lazy fetch (연도별 청크).

## 사용

### 소급 수집

```bash
uv sync
uv run python -m scraper.download --mode backfill --max-pages 212
uv run python -m parser.parse --mode backfill
uv run python -m builder.build
```

### 일일 갱신

```bash
uv run python -m scraper.download --mode latest
uv run python -m parser.parse --mode latest
uv run python -m builder.build
```

### 환율 (선택)

```bash
BOK_API_KEY=xxxxx uv run python -m exchange.fetch_krw
uv run python -m builder.build
```

ECOS 키 없으면 PDF 내장 환율 자동 사용.

### 로컬 프론트엔드

```bash
python3 -m http.server 8080 --directory .
# http://localhost:8080/site/
```

## 테스트

```bash
uv run pytest tests/ -v
```

## GitHub 배포

1. GitHub repo 생성, push
2. **Settings → Pages → Source: GitHub Actions**
3. (선택) **Settings → Secrets → BOK_API_KEY** 등록
4. `pages.yml` 워크플로우가 자동 배포 (push 시)
5. `collect.yml`이 매일 평일 KST 19:00 자동 데이터 수집

## 환율 소스

`builder/build.py` `resolve_rate()`:
- BOK ECOS rate → `source: "bok"`
- PDF `market.krw_usd` fallback → `source: "pdf"`
- 각 daily 엔트리 `krw.source` 필드로 추적
