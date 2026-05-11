# PPS 조달청 주간 리포트 뉴스 통합

**Date:** 2026-05-11
**Status:** Design approved, awaiting implementation plan

## 목적

조달청(www.pps.go.kr) "비축물자 → 국제원자재시장동향 → 비철/희소금속 시장동향" 게시판의 두 시리즈 주간 리포트를 기존 뉴스 파이프라인에 통합한다. snmnews 만으로는 누락되는 정부 공식 시장 동향을 보강한다.

## 대상 게시물

게시판 URL: `https://www.pps.go.kr/bichuk/bbs/list.do?key=00826`

수집 대상 (제목 prefix 매칭):

- "주간 경제·비철금속 시장동향" — Cu/Al/Zn/Ni/Pb/Sn 주간 리포트
- "주간 희소금속 가격동향" — Sb 포함 minor metals 리포트

각 게시물은 PDF 첨부파일이 본문(HTML 본문은 제목/요약뿐). 게시 주기: 주간 (월~수 게시 관찰).

## 데이터 흐름

```
PPSScraper (신규)
  ├─ list page HTML scrape (key=00826)
  ├─ 제목 prefix 필터 (두 시리즈)
  ├─ 게시물 상세 페이지 → PDF attachment URL 추출
  └─ PDF 다운로드 → pdfplumber 텍스트 추출 → RawNewsItem
       │   source="pps", url=PDF 직링 (또는 게시물 URL), title=게시물 제목
       │   content=PDF 텍스트 본문
       ↓
classify (source='pps' bypass — 항상 비철 관련 confirmed)
       ↓
dedupe (url_hash 기준)
       ↓
summarizer (Gemini Flash) → summary_ko
       ↓
news_build → data/news/{year}.parquet (기존 스키마)
       ↓
site/news.js → 'PPS 정부공식' 배지 (별도 색상)
```

## 변경 파일

### 신규

- `scraper/news/pps.py` — `NewsSource` 인터페이스 구현
  - HTTP fetch list page, parse 게시물 row (제목/날짜/상세URL)
  - 제목 prefix 필터
  - 상세 페이지 → attachment endpoint URL 추출
  - PDF 다운로드 → pdfplumber로 텍스트 추출 (실패 시 title-only fallback)
  - `RawNewsItem` 리스트 반환
- `tests/news/test_pps.py` — list page HTML fixture + PDF fixture로 unit test

### 수정

- `scraper/news/run.py` — `scrapers = [RSSScraper(), PPSScraper()]`
- `parser/news/classify.py` — `source == 'pps'`이면 키워드 분류 skip하고 비철 confirmed로 통과
- `site/news.js` — source 배지 스타일에 `pps` 케이스 (정부 신뢰 표시용 색상, 예: 진한 파랑)

## 스케줄링

기존 `.github/workflows/news.yml` (KST 9시/21시, 일 2회) 재사용. PPS는 주간 갱신이지만 매 실행마다 동일 글이 dedupe로 차단됨. 추가 workflow 불필요.

## 견고성

- **PPS 사이트 다운/구조 변경** — scraper 단독 실패는 silent하게 처리. 기존 silent-fail guard는 모든 scraper가 0건일 때만 fail하므로 snmnews가 살아있으면 파이프라인 통과.
- **PDF 텍스트 추출 실패** — title만 가지고 RawNewsItem 생성. summary_ko = null로 통과.
- **robots.txt** — `/kor/bbs/`만 차단. `/bichuk/bbs/`는 미차단으로 확인됨. 그래도 User-Agent 명시 및 1초 sleep.
- **세션 ID 동적 URL** — 상세 페이지 URL이 동적이면 list page에서 직접 attachment URL을 추출하거나, 게시물 ID로 다시 fetch.

## 테스트

`tests/news/fixtures/pps_list.html` — list page 샘플
`tests/news/fixtures/pps_sample.pdf` — PDF 샘플

테스트 케이스:

- list 파싱 → 두 시리즈만 필터링 확인
- PDF 텍스트 추출 → 핵심 키워드(예: "구리", "$/ton") 포함 확인
- 제목 prefix 매칭 — false positive 방지 ("주간 경제·비철금속" 외의 글 제외)
- 사이트 실패 시 빈 리스트 반환 (예외 던지지 않음)

## Out of scope

- PDF 첨부 직접 임베드 (iframe 뷰어) — 디자인 단계에서 제외 결정
- 별도 카드 섹션 신설 — 뉴스 drawer 통합으로 결정
- PPS 게시물 archive 보관 — enriched parquet에 url+title+summary 보존됨
