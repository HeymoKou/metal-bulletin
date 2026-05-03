# 비철금속 데스크 · LME Non-Ferrous

NH선물 일일금속시황 PDF → Apache Parquet → 모바일 GitHub Pages.
서버리스. 매일 자동 갱신. 10년 시계열.

**Live:** https://heymokou.github.io/metal-bulletin/

## 데이터

- **소스:** NH선물 Daily Metal Bulletin (https://www.futures.co.kr)
- **광물:** Cu, Al, Zn, Ni, Pb, Sn (LME 6종)
- **필드:** LME Cash/3M (OHLC, bid/ask, OI), 정산가 + 선물커브, 재고 (반입/반출/CW), SHFE 비교 (프리미엄), KRW 환산
- **환율:** 한국은행 ECOS 우선 → PDF 내장 환율 폴백 (`source` 필드 추적)
- **이력:** 2015-10-01 ~ 현재 (10년+)

## 아키텍처

```
metal-bulletin/
├── scraper/          PDF 다운로드 (futures.co.kr)
├── parser/           PDF → daily JSON
│   ├── parse.py      통합 진입점
│   ├── page1.py      LME 시세 + 정산가 + EV metals
│   ├── page2.py      재고 + SHFE + market factors
│   └── page3.py      귀금속
├── exchange/         한국은행 ECOS 환율 (선택)
├── builder/          daily JSON → Parquet 시계열 + manifest
├── data/
│   ├── raw/{year}.parquet            영업일별 원본 JSON 아카이브
│   ├── series/{metal}/
│   │   ├── latest.parquet            최근 90일 (즉시 표시)
│   │   └── {year}.parquet            연도별 시계열
│   ├── exchange.parquet              USD/KRW 시계열
│   └── manifest.json                 단일 메타 (광물 정보, 가용 연도, 마지막 갱신)
├── site/             정적 vanilla JS 대시보드 (GitHub Pages)
├── tests/            pytest
└── .github/workflows/
    ├── collect.yml   매시 폴링, 오늘 완료 시 즉시 종료
    └── pages.yml     site + data → GitHub Pages
```

**프론트 로딩:** manifest + 6 latest.parquet 즉시 fetch (~190KB) → 차트 확장 시 연도별 lazy load.

## 사용

### 소급 수집

```bash
uv sync
uv run python -m scraper.download --mode backfill --max-pages 212
uv run python -m parser.parse --mode backfill
uv run python -m builder.build
```

### 일일 갱신 (Actions가 자동 실행)

```bash
uv run python -m scraper.download --mode latest
uv run python -m parser.parse --mode latest
uv run python -m builder.build
```

### 환율 강화 (선택)

```bash
BOK_API_KEY=xxxxx uv run python -m exchange.fetch_krw
uv run python -m builder.build
```

ECOS 키 없으면 PDF 내장 환율 자동 사용.

### 로컬 프론트엔드

```bash
python3 -m http.server 8080
# http://localhost:8080/site/
```

### 테스트

```bash
uv run pytest tests/      # Python (24)
npm run smoke             # JS Parquet 로드 (6)
```

## GitHub 배포

1. repo push
2. Settings → Pages → Source: **GitHub Actions**
3. (선택) Settings → Secrets → `BOK_API_KEY`
4. `pages.yml` 자동 배포 (push 시)
5. `collect.yml` KST 평일 9~19시 매시 폴링

## 환율 source

`builder.resolve_rate()`:
- BOK ECOS rate → `source: "bok"`
- PDF `market.krw_usd` fallback → `source: "pdf"`
- 각 daily 엔트리 `krw.source`로 추적
