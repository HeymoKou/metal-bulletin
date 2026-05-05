# 비철금속 데스크 · LME Non-Ferrous

NH선물 PDF + westmetall fallback + 다국어 뉴스 → Apache Parquet → 서버리스 GitHub Pages 대시보드.
매일 자동 갱신. 10년+ 시계열. 한국어 비철 산업 뉴스 LLM 요약 통합.

**Live:** https://heymokou.github.io/metal-bulletin/

## 데이터

### 가격 (LME 6종 + minor)
- **Primary:** NH선물 Daily Metal Bulletin (https://www.futures.co.kr) — full schema (LME Cash/3M OHLC, bid/ask, OI, 정산가 + 선물커브, 재고 반입/반출/CW, SHFE 프리미엄, KRW 환산)
- **Fallback:** westmetall.com — KR 공휴일/NH 미발행 시 자동 (settlement + inventory minimal)
- **광물:** Cu, Al, Zn, Ni, Pb, Sn (LME) + Sb (minor, EXW China)
- **이력:** 2015-10-01 ~ 현재
- **환율:** 한국은행 ECOS (USD/EUR/CNY) → PDF 내장 → null (`krw.source` 추적)

### 뉴스
- **소스:** mining.com / moneytoday / 철강금속신문 (RSS) + GDELT 2.0 (글로벌 다국어) + nonferrous.or.kr (산업트렌드)
- **분류:** 한국어 동음이의 차단 + LLM 사전 필터 → Gemini 2.5 Flash 배치 요약 (구조화 JSON 스키마)
- **이벤트:** LME stocks 일일 스냅샷 (westmetall) → 재고 |Δ| 임계값 차트 마커

## 아키텍처

→ 자세한 다이어그램은 [docs/architecture.md](docs/architecture.md).

## 사용

### 소급 수집
```bash
uv sync
uv run python -m scraper.download --mode backfill --max-pages 212
uv run python -m parser.parse --mode backfill
uv run python -m builder.build
```

### 일일 갱신 (Actions 자동)
```bash
uv run python -m scraper.download --mode latest
uv run python -m parser.parse --mode latest
uv run python -m builder.lme_backfill --mode fallback   # KR 공휴일 cover
uv run python -m builder.build
```

### 뉴스 파이프라인 (Actions 자동, 일 2회 KST 9시/21시)
```bash
GEMINI_API_KEY=xxx uv run python -m scraper.news.run
uv run python -m parser.news.run
uv run python -m summarizer.run
uv run python -m builder.news_build
uv run python -m builder.events_build
uv run python -m builder.news_manifest
```

### 환율 (선택)
```bash
ECOS_API_KEY=xxx uv run python -m exchange.fetch_krw
```

### 로컬 프론트엔드
```bash
python3 -m http.server 8080
# http://localhost:8080/site/
```

### 테스트
```bash
uv run pytest tests/       # Python 113
npm run smoke              # JS Parquet 로드 8
```

## GitHub 배포

1. repo push
2. Settings → Pages → Source: **GitHub Actions**
3. Settings → Secrets:
   - `GEMINI_API_KEY` (뉴스 LLM)
   - `ECOS_API_KEY` (환율, 선택)
4. `pages.yml` 자동 배포 (push 시)
5. `collect.yml` KST 평일 9~19시 매시 폴링 (오늘 완료 시 즉시 종료)
6. `news.yml` UTC 0/12 (KST 9/21시) 일 2회

## 절대 변경 금지

- `data/series/` 스키마 (Parquet 컬럼명) — 변경 시 manifest schema bump + FE unflatten 동기화
- `data/manifest.json` 키 (`metals`, `years`, `latest_window`)
- 광물 키 이름 (`copper`, `aluminum`, `zinc`, `nickel`, `lead`, `tin`)

## 추가 문서
- [docs/architecture.md](docs/architecture.md) — 시스템 다이어그램 (mermaid)
- [CLAUDE.md](CLAUDE.md) — 다음 세션용 컨텍스트
