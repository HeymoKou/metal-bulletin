# CLAUDE.md

서버리스 비철금속 데스크. 다음 세션이 빨리 따라잡기 위한 핵심만.

## 스택
- Python 3.14 (uv) — scraper/parser/exchange/builder/summarizer
- Apache Parquet (pyarrow, zstd) — 데이터 저장 포맷
- Vanilla JS ESM + hyparquet (CDN, 정확 버전 핀) — 프론트
- GitHub Pages + Actions
- 뉴스 파이프라인: feedparser, beautifulsoup4, rapidfuzz, pydantic, google-genai (Gemini Flash)

## 데이터 플로우
PDF (NH선물) → daily JSON → Parquet (`data/series/{metal}/{year}.parquet` + `latest.parquet`) → 프론트 fetch
- `data/manifest.json` = 단일 메타 소스 (광물 정보, 가용 연도, 마지막 갱신)
- `data/raw/{year}.parquet` = daily JSON 아카이브 (재구축 입력)
- `data/daily/` = 빌드 캐시, **gitignored**, raw에서 복원 가능 (`builder.load_dailies()`)

## 광물 메타 단일 소스
`builder.METALS` 딕셔너리 (build.py:11) → `data/manifest.json`에 직렬화 → 프론트는 manifest만 읽음.
- 광물 추가/이름 수정은 `builder/build.py:11`만 수정 → 빌더 재실행
- 프론트 하드코딩 없음 (`site/app.js:11-12`은 `let`, init 시 manifest로 채워짐)

## 워크플로우
- `collect.yml` — KST 평일 9~19시 매시. `manifest.last_updated == 오늘(KST)`이면 모든 step 스킵 (~5초 종료).
- `news.yml` — 일 2회 (UTC `0 0,12 * * *` = KST 9시/21시). 비철 뉴스 수집 → Gemini 요약 → `data/news/{year}.parquet`. `GEMINI_API_KEY` secret 필요.
- `pages.yml` — site/ + data/ → Pages. push 트리거.

## 뉴스 파이프라인
PDF 가격과 독립. 4단계: scrape (RSS+KORES) → parse (dedupe+classify) → summarize (Gemini Flash batch) → build parquet.
- 소스: mining.com, kitco, commodity-tv, hankyung, moneytoday (RSS) + KORES 일일자원뉴스 (스크랩)
- LLM provider 인터페이스 (`SummarizerProvider` Protocol) → 추후 groq/cerebras failover 확장 가능
- 분류 1차 필터 (`parser/news/classify.py`) → 무관 헤드라인은 LLM 안 부름 (비용 절감)
- 출력 스키마: `data/news/{year}.parquet` (date, source, url, url_hash, title, summary_ko, metals, sentiment, event_type, confidence, lang)
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
