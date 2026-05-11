# CLAUDE.md

서버리스 비철금속 데스크. 다음 세션이 빨리 따라잡기 위한 핵심만.

## 스택
- Python 3.14 (uv) — scraper/parser/exchange/builder/summarizer
- Apache Parquet (pyarrow, zstd) — 데이터 저장 포맷
- Vanilla JS ESM + hyparquet (CDN, 정확 버전 핀) — 프론트
- GitHub Pages + Actions
- 뉴스 파이프라인: feedparser, beautifulsoup4, rapidfuzz, pydantic, google-genai (Gemini Flash)

## 데이터 플로우
PDF (NH선물) **OR** westmetall.com → daily JSON → Parquet (`data/series/{metal}/{year}.parquet` + `latest.parquet`) → 프론트 fetch
- `data/manifest.json` = 단일 메타 소스 (광물 정보, 가용 연도, 마지막 갱신)
- `data/raw/{year}.parquet` = daily JSON 아카이브 (재구축 입력), 2008~ 18년 시계열
- `data/daily/` = 빌드 캐시, **gitignored**, raw에서 복원 가능 (`builder.load_dailies()`)

## LME 가격 출처 이중화 + KOMIS cross-validation
- **Primary**: NH선물 PDF — full schema (lme cash/3m OHLC, bid/ask, OI, settlement, forwards, lme_settle, inventory breakdown, SHFE)
- **Fallback**: westmetall.com — minimal (settlement.cash, settlement.3m, inventory.current). KR 공휴일에 NH 미발행 시 자동 적용.
- **Cross-validation 1**: westmetall과 NH PDF 90일 비교 결과 6 metals × 3 columns Δ=0.00 (완전 일치).
- **Cross-validation 2 (실시간, 2026-05-12~)**: KOMIS BaseMetals ajax로 6 metals daily LME Cash/3M fetch → `data/komis/validation.parquet` 누적 저장. manifest.komis에 last_date/max_diff/mismatch 요약.
  - 모듈: `scraper/komis.py` (KomisQuote + fetch), `builder/komis_validate.py` (build_records + manifest 갱신).
  - threshold: |Δ| > 0.5 USD → mismatch (가격 quote가 2dp니 사실상 모든 의미있는 차이를 잡음).
  - KOMIS IP 차단: AWS ASN block ✗, Azure (GH Actions) + Oracle Cloud Japan + 로컬 KR ✓ (2026-05-12 확인). GH Actions에서 정상 작동.
- 합성 JSON은 `_source: "westmetall"` 플래그 — FE에서 일부 필드 null 처리 필요.
- 명령어:
  - `uv run python -m builder.lme_backfill --mode {backfill|validate|fallback}`
  - `uv run python -m builder.komis_validate`

## 광물 메타 단일 소스
`builder.METALS` 딕셔너리 (build.py:11) → `data/manifest.json`에 직렬화 → 프론트는 manifest만 읽음.
- 광물 추가/이름 수정은 `builder/build.py:11`만 수정 → 빌더 재실행
- 프론트 하드코딩 없음 (`site/app.js:11-12`은 `let`, init 시 manifest로 채워짐)

## 워크플로우
- `collect.yml` — KST 평일 9~19시 매시. `manifest.last_updated == 오늘(KST)`이면 모든 step 스킵 (~5초 종료).
- `news.yml` — 일 2회 (UTC `0 0,12 * * *` = KST 9시/21시). 비철 뉴스 수집 → Gemini 요약 → `data/news/{year}.parquet`. `GEMINI_API_KEY` secret 필요.
- `pages.yml` — site/ + data/ → Pages. push 트리거.

## 뉴스 파이프라인
PDF 가격과 독립. 4단계: scrape → parse (dedupe+classify) → summarize (Gemini Flash batch) → build parquet.
- 소스: snmnews 철강금속신문 (RSS) — CI에서 실제 작동
- PPS 조달청 비축물자 주간리포트 (PDF→pdfplumber): code+test 보존, **CI 미사용** — 한국 gov 사이트가 모든 cloud IP 차단 (AWS us-east/tokyo/seoul 전부 `ConnectionResetError 104`). 2026-05-11 Lambda ap-northeast-2 (15.165.8.180) 직접 검증. 로컬 KR 가정 IP에서만 작동. `scripts/lambda_pps_test.py`에 stdlib-only 재현 코드.
- 폐기된 소스: mining.com/moneytoday RSS, GDELT 2.0 API, 한국비철금속협회 (헤드라인 오프토픽 다수 → snmnews만)
- KORES/KOMIS deferred — KOMIS 비철 LME CASH는 우리 sett_cash와 100% 중복 (2026-05-08 Ni 18890.0 일치 검증). data.go.kr 자체 Open API 없음.
- LLM provider 인터페이스 (`SummarizerProvider` Protocol) → 추후 groq/cerebras failover 확장 가능
- 분류 1차 필터 (`parser/news/classify.py`) → 무관 헤드라인은 LLM 안 부름 (비용 절감)
- 출력 스키마: `data/news/{year}.parquet` (date, source, url, url_hash, title, summary_ko, metals, sentiment, event_type, confidence, lang)
- 이벤트 스키마: `data/events/{year}.parquet` (date, type, metal, magnitude, title, url, source) — LME stocks 일일 스냅샷 via westmetall
- raw 아카이브 없음 (enriched parquet에 url+title 보존, 재요약 욕구 약해 제거)

## 보안 핀 (변경 시 갱신 필요)
- `actions/checkout@93cb6efe...` (v5, Node 24) — collect/news/pages.yml
- `astral-sh/setup-uv@08807647...` (v8.1.0, Node 24) — collect/news.yml
- `hyparquet@1.25.6`, `hyparquet-compressors@1.1.1` — site/app.js 라인 4-5

## 파서 강건성 (히스토릭 PDF)
- 날짜 형식 3종 지원: ISO, DD-MM-YYYY (구버전), YYYY.MM.DD
- `_safe()` 래퍼로 섹션별 부분 파싱 허용 — 한 페이지 깨져도 가능한 데이터는 보존
- SHFE 테이블 인덱스는 헤더 텍스트로 동적 탐지 (PDF 레이아웃 변동 대응)
- `_warnings` 필드에 부분 실패 기록

## settlement 컬럼 매핑 (PDF page0 table[1])
NH PDF 정산가 테이블 11 cols. 2026-05-11 라벨 정정 + 소급 마이그레이션 적용:

| col | PDF 헤더 | parser key | series 컬럼 |
|-----|----------|-----------|-------------|
| 1 | 금일 Cash (KRX 17:00) | `cash` | `sett_cash` |
| 2 | 금일 3M | `3m` | `sett_3m` |
| 3 | **당월평균 Cash** (PDF 자체 계산) | (저장 안 함 — manifest current_month_avg 사용) | — |
| 4 | 전월평균 Cash | `prev_monthly_avg.cash` | `sett_prev_mavg_cash` |
| 5 | 전월평균 3M | `prev_monthly_avg.3m` | `sett_prev_mavg_3m` |
| 6 | **LME 정산가 Cash** (LONDON 17:00) | `lme_settle.cash` | `sett_lme_settle_cash` |
| 7 | **LME 정산가 3M** | `lme_settle.3m` | `sett_lme_settle_3m` |
| 8/9/10 | forwards M+1/M+2/M+3 | `forwards.m1/m2/m3` | `sett_fwd_m1/m2/m3` |

**중요:**
- PDF에 **당월평균 3M 컬럼은 없음**. 진짜 당월평균 Cash는 col[3] 단일.
- FE 당월평균 Cash/3M 표시는 **builder가 daily 시리즈에서 직접 계산**한 `manifest.metals.{metal}.current_month_avg`에서 가져옴. (PDF col[3] 정확성과 일치, 3M은 우리 계산이지만 동일 방식이라 일관성.)
- col[6-7]은 LME 공식 (London 17:00) — 금일 Cash와는 다른 시점 (KRX 17:00 vs London 17:00 발표 시차).

**과거 마이그레이션 (2026-05-11):**
- swap 1차: col[4-5] ↔ col[6-7] (`migrate_swap_mavg.py`, 2015~ 2630 entries) — `prev_monthly_avg` 매핑은 이걸로 정확해졌음.
- rename 2차: `settlement.monthly_avg` → `settlement.lme_settle` (`migrate_rename_lme_settle.py`) + series 컬럼 `sett_mavg_*` → `sett_lme_settle_*`. 라벨이 의미와 일치하도록 정정. 값은 그대로 보존.

검증: 2026-05-08 Pb manifest `current_month_avg.cash` = 1969.20 (PDF col[3]와 정확히 일치, 5월 daily mean 1969.20 = (1945+1967+1987+1980+1967)/5 검산).

## 환율 폴백
`builder.resolve_rate()`: BOK ECOS → PDF 내장 → None. 각 daily 엔트리 `krw.source` 추적.

## 테스트
- `uv run pytest tests/` — 66+ (Python, 가격 24 + 뉴스 42)
- `npm run smoke` — 6 (JS Parquet 로드 + 스키마)

## 자주 쓰는 커맨드
```bash
# 가격 파이프라인
uv run python -m scraper.download --mode latest
uv run python -m parser.parse --mode latest
uv run python -m builder.build

# 뉴스 파이프라인 (GEMINI_API_KEY 필요)
uv run python -m scraper.news.run
uv run python -m parser.news.run
uv run python -m summarizer.run
uv run python -m builder.news_build

gh run list --repo HeymoKou/metal-bulletin --limit 5
```

## 절대 변경 금지
- `data/series/` 스키마 (Parquet 컬럼명) — 변경 시 manifest.schema 버전 bump + FE unflatten 동기화
- `data/manifest.json` 키 (특히 `metals`, `years`, `latest_window`)
- 광물 키 이름 (`copper`, `aluminum`, `zinc`, `nickel`, `lead`, `tin`) — series 디렉토리명과 매칭
