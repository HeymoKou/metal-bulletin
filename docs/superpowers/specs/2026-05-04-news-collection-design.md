# 비철금속 뉴스 수집 파이프라인 — Design Spec

- **Date:** 2026-05-04
- **Status:** APPROVED (Phase 1 scope)
- **Author:** heymo
- **Branch:** (TBD on implementation)
- **Scope:** Backend 수집 파이프라인만. 프론트 통합은 별도 spec.

---

## 1. 목표

GitHub Actions에서 무료로 비철 6개 광물(copper, aluminum, zinc, nickel, lead, tin) 관련 뉴스/이벤트를 자동 수집하고 LLM으로 요약·분류해 Parquet에 저장한다. 본인이 매일 30분씩 수동으로 뉴스 모으고 차트와 대조하던 작업을 0분으로 줄인다.

### Success Criteria

- 일 6회(매 4시간) 자동 실행, 평균 5분 이내 완료
- **시그널 품질 우선:** 가격 영향 큰 이벤트(LME stock 변동, 공급망 disruption, 정책 발표) 누락 없음. 한가한 날 0건도 정상.
- LLM 요약 정확도: 사용자 spot check 기준 confidence ≥ 0.6 항목 중 80% 이상 적절
- 비용 0원 (Gemini/GDELT/RSS/GitHub Actions free tier 내)
- 1개 소스 실패 시 다른 소스로 cover (격리된 실패)
- **Anti-goal:** 헤드라인 수 KPI 추구 금지. 노이즈 채우는 것보다 비워두는 게 낫다.

### Out of Scope

- 프론트 표시 방식 (마커/팝업/패널) — 별도 spec (Phase 2)
- 가격 forecast (Prophet/statsforecast) — 별도 검토
- 푸시 알림 (Slack/Email)
- 사용자 다중화 (현재 단일 사용자)

---

## 2. Architecture

```
metal-bulletin/
├─ scraper/news/              # 소스별 fetch (single responsibility)
│  ├─ __init__.py
│  ├─ base.py                 # 공통 인터페이스: fetch() -> list[RawNewsItem]
│  ├─ rss.py                  # Tier 1: feedparser, RSS 일괄
│  ├─ gdelt.py                # Tier 2: GDELT 2.0 DOC API
│  ├─ kores.py                # Tier 2: 한국광물공사 BS4
│  ├─ nonferrous.py           # Tier 2: 한국비철금속협회
│  ├─ lme.py                  # Tier 2: LME 공시 + warehouse stocks
│  └─ marketaux.py            # Tier 3: marketaux API
├─ parser/news/
│  ├─ dedupe.py               # url_hash + 제목 fuzzy
│  ├─ classify.py             # 키워드 1차 필터
│  └─ models.py               # pydantic: RawNewsItem, EnrichedNewsItem, EventItem
├─ summarizer/
│  ├─ client.py               # Gemini primary + failover chain
│  ├─ prompt.py               # batch JSON output 프롬프트
│  └─ providers/
│     ├─ gemini.py
│     ├─ groq.py
│     └─ cerebras.py
├─ builder/
│  ├─ news_build.py           # → data/news/{year}.parquet
│  └─ events_build.py         # → data/events/{year}.parquet
├─ tests/news/                # ~16개 신규 테스트
├─ data/
│  ├─ news/{year}.parquet     # 가공 결과
│  ├─ events/{year}.parquet   # LME/매크로 이벤트
│  └─ raw/news/{year-month}.jsonl.zst  # 원본 아카이브
└─ .github/workflows/
   └─ news.yml                # 별도 워크플로우, collect.yml과 독립
```

설계 원칙:
- 소스 모듈 1개 = 파일 1개. 추가/제거 단순.
- 모든 scraper는 `base.NewsSource` 인터페이스 구현 (`fetch() -> list[RawNewsItem]`).
- LLM provider도 동일 인터페이스 (`summarize_batch(items) -> list[EnrichedNewsItem]`) 로 swap 가능.
- 가격 파이프라인(`scraper/`, `parser/`, `builder/build.py`)과 분리. 광물 메타는 `builder.METALS` 단일 소스 그대로 재사용.

---

## 3. Data Sources (우선순위)

### Phase 1a — MVP (Week 1)

| 소스 | 타입 | 언어 | 모듈 |
|---|---|---|---|
| mining.com | RSS | en | rss.py |
| Kitco Mining News | RSS | en | rss.py |
| Commodity-TV | RSS | en | rss.py |
| 한국경제 | RSS | ko | rss.py |
| 머니투데이 | RSS | ko | rss.py |
| KORES 일일자원뉴스 | scrape (공공) | ko | kores.py |

### Phase 1b — 확장 (Week 2)

| 소스 | 타입 | 언어 | 모듈 |
|---|---|---|---|
| GDELT 2.0 DOC API | API | 다국어→en 자동번역 | gdelt.py |
| LME News + Warehouse Stocks | scrape (공식) | en | lme.py |
| 한국비철금속협회 | scrape (공식) | ko | nonferrous.py |

### Phase 1c — Optional (Week 3)

| 소스 | 타입 | 비고 |
|---|---|---|
| marketaux | API | 무료 tier, commodities entity |
| SMM news.metal.com | scrape | robots.txt 사전 확인 |
| 철강금속신문 | scrape | robots.txt 사전 확인 |
| Reuters Commodities | RSS (제한적) | 헤드라인만 |

스크랩 가드: 모든 scrape 모듈은 robots.txt 자동 체크하고 disallow 시 NotImplementedError 발생. ToS 위반 방지.

---

## 4. LLM Strategy

### Primary: Gemini 2.5 Flash

- 무료 1500 req/day, 1M context, JSON 모드 지원
- API key: `GEMINI_API_KEY` (GitHub Secrets)

### Failover Chain

1. Gemini 2.5 Flash
2. Groq Llama 3.3 70B (`GROQ_API_KEY`)
3. Cerebras Llama (`CEREBRAS_API_KEY`)
4. fail-soft: LLM 없이 raw 저장 (`summary_ko=null`, `confidence=null`)

각 provider는 동일 출력 스키마 보장. provider별 어댑터에서 정규화.

### Batch & Cost

- 10 헤드라인/call → 일 30~50 헤드라인 → 일 3~5 calls
- 무료 한도 대비 0.3% 이하
- 1차 키워드 필터(`classify.py`) 통과한 항목만 LLM 호출

### Prompt (structured JSON output)

Input:
```json
[
  {"id": "abc123", "title": "...", "snippet": "본문 200자"},
  ...
]
```

Output:
```json
[
  {
    "id": "abc123",
    "summary_ko": "한 문장 요약",
    "metals": ["copper", "nickel"],
    "sentiment": -1,
    "event_type": "supply",
    "confidence": 0.85
  }
]
```

`event_type` enum: `supply | demand | policy | macro | other`
`sentiment`: `-1 | 0 | 1` (가격 영향 방향)
`confidence`: 0~1 float

---

## 5. Data Schema

### `data/news/{year}.parquet`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| date | date32 | KST 기준 |
| fetched_at | timestamp[us, UTC] | |
| source | string | "mining.com", "kores", "gdelt", ... |
| url | string | |
| url_hash | string | SHA256 처음 16자, dedupe 키 |
| title | string | 원문 제목 |
| title_ko | string | nullable, 비한국어 시 번역 |
| summary_ko | string | nullable (LLM 실패 시) |
| metals | list\<string\> | ["copper", ...] |
| sentiment | int8 | -1/0/1, nullable |
| event_type | string | nullable |
| confidence | float32 | 0~1, nullable |
| lang | string | "ko"/"en"/"zh"/... |

압축: zstd. 정렬: date desc, fetched_at desc.

### `data/events/{year}.parquet`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| date | date32 | |
| type | string | "lme_stock", "lme_announce", "macro" |
| metal | string | 6 metals 중 하나 또는 "all" |
| magnitude | float32 | stock 변동률 등, nullable |
| title | string | |
| url | string | nullable |
| source | string | |

### `data/raw/news/{year-month}.jsonl.zst`

원본 응답 그대로 1줄/항목. 재구축 입력. 가격 파이프라인의 `data/raw/`와 동일 패턴.

### Manifest 갱신

`data/manifest.json`에 추가:

```json
{
  "news": {
    "available_years": [2026],
    "last_updated": "2026-05-04T12:00:00+09:00",
    "sources": ["mining.com", "kores", ...],
    "total_records": 1234
  },
  "events": {
    "available_years": [2026],
    "last_updated": "2026-05-04T12:00:00+09:00"
  }
}
```

기존 `metals`, `years`, `latest_window` 키는 변경 없음.

---

## 6. GitHub Actions Workflow

`.github/workflows/news.yml`:

```yaml
name: news

on:
  schedule:
    - cron: '0 */4 * * *'    # UTC, 매 4시간 = 일 6회
  workflow_dispatch:

permissions:
  contents: write

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@<sha>
      - uses: astral-sh/setup-uv@<sha>
      - name: Install deps
        run: uv sync
      - name: Scrape news
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          MARKETAUX_KEY: ${{ secrets.MARKETAUX_KEY }}
        run: |
          uv run python -m scraper.news.run
          uv run python -m parser.news.run
          uv run python -m summarizer.run
          uv run python -m builder.news_build
          uv run python -m builder.events_build
      - name: Commit
        run: |
          git config user.name 'github-actions'
          git config user.email 'github-actions@github.com'
          git add data/news data/events data/raw/news data/manifest.json
          git diff --staged --quiet || git commit -m "news: $(date -u +%Y-%m-%dT%H:%MZ)"
          git push
```

자원 사용량:
- 5분/run × 일 6회 = 30분/일
- 월 ~15시간 = 무료 2000분 한도 7% 미만

`collect.yml`(가격)과 격리. 한쪽 실패가 다른쪽 막지 않음.

---

## 7. Failure Modes

| 실패 시나리오 | 대응 |
|---|---|
| 1개 소스 fetch 실패 | `_safe()` 래퍼로 격리, `_warnings` 필드 기록, 나머지 소스 정상 진행 (가격 파이프라인 패턴 재사용) |
| LLM provider rate limit | failover chain 순차 시도. 전부 실패 시 `summary_ko=null`로 raw 저장 |
| robots.txt 변경/disallow | scrape 모듈이 NotImplementedError. 단위 테스트에서 사전 감지 |
| 중복 폭주 | url_hash 1차 dedupe + 제목 fuzzy(rapidfuzz, similarity > 0.85) 2차 dedupe |
| Parquet 파일 크기 폭증 | 연도별 분할 + zstd. raw는 월별 jsonl.zst |
| LLM 환각/오분류 | confidence < 0.6 마킹. FE에서 필터링 (이 spec scope 밖) |
| GDELT API 장애 | failure tolerance: 결과 0건이어도 워크플로우 성공 처리 |
| API key 누락 | Gemini key는 필수. 누락 시 워크플로우 실패. fallback key는 optional |
| 시간대 혼동 | 모든 timestamp UTC 저장, KST 변환은 표시 시점 |

---

## 8. Testing Strategy

신규 테스트 ~16개:

- `tests/news/test_dedupe.py` (3) — url hash, fuzzy match, edge cases
- `tests/news/test_classify.py` (6) — 6 광물별 키워드 hit
- `tests/news/test_rss_parse.py` (3) — fixture 기반 RSS 파싱
- `tests/news/test_llm_failover.py` (2) — mock provider chain
- `tests/news/test_schema.py` (1) — parquet 스키마 검증
- `tests/news/test_robots_guard.py` (1) — robots.txt 차단 시 raise

기존 24 + 신규 16 = 40개. `uv run pytest tests/`.

JS smoke test는 변경 없음 (FE 통합 시점에 추가).

---

## 9. 보안 핀 (CLAUDE.md에 추가 필요)

- `astral-sh/setup-uv@<sha>` — news.yml
- `actions/checkout@<sha>` — news.yml
- 새 의존성 버전 핀 (`pyproject.toml`):
  - `feedparser`
  - `beautifulsoup4`
  - `rapidfuzz`
  - `google-genai` (Gemini SDK)
  - `groq` (fallback)
  - `httpx` (이미 있을 가능성)
  - `pydantic`

---

## 10. 구현 순서 (4 weeks)

| Week | 산출물 |
|---|---|
| 1 | scraper/rss + parser/dedupe + summarizer/gemini + builder/news_build + news.yml + 1a 소스 6개 → MVP 운영 |
| 2 | gdelt.py + lme.py + nonferrous.py + events_build.py → 커버리지 점프 |
| 3 | marketaux + (조건부) SMM/철강금속신문 + 테스트 정비 → 안정화 |
| 4 | (별도 spec) 프론트 통합 phase 시작 |

각 주차 종료 시 `git push` → 실 데이터 누적 확인 → 다음 주차 결정.

---

## 11. 미해결 질문 (별도 spec에서)

- 프론트 UX: 차트 마커 vs 팝업 vs 사이드 패널 vs 별도 페이지 — Phase 2 spec
- 알림: 큰 이벤트(LME stock ±5% 등) 시 슬랙/메일 푸시 여부
- 다국어 confidence 차이: 한국어 ko 모델 별도 사용 여부
- 장기 보존 정책: 5년+ 데이터 cold storage 분리 여부
- 사용자 분석: 어떤 뉴스를 클릭했는지 추적해 ranking 학습 (long term)

---

## 12. 변경 이력

- 2026-05-04: 초안 (office-hours 세션 결과 반영)
