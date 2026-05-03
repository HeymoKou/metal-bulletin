# 비철금속 시세 대시보드

NH선물 일일금속시황 PDF 자동 수집 → 구조화 JSON → 모바일 대시보드.

## 데이터

- **소스:** NH선물 Daily Metal Bulletin (futures.co.kr)
- **광물:** 전기동(Cu), 알루미늄(Al), 아연(Zn), 니켈(Ni), 납(Pb), 주석(Sn)
- **필드:** LME 시세(Cash/3M), 정산가, 재고, SHFE 비교, EV metals, 귀금속, USD/KRW
- **환율 소스:** 1순위 한국은행 ECOS, 2순위 PDF 내장 환율 (자동 폴백)

## 구조

```
metal-bulletin/
├── scraper/         PDF 다운로드
├── parser/          PDF → daily JSON
├── exchange/        한국은행 ECOS 환율 수집 (선택)
├── builder/         daily → metals 시계열 + index
├── data/
│   ├── daily/       영업일별 원본
│   ├── metals/      광물별 시계열 (프론트엔드용)
│   ├── exchange/    USD/KRW 시계열
│   └── index.json   메타데이터
├── site/            정적 모바일 대시보드
└── tests/
```

## 사용

### 소급 수집 (전체)

```bash
uv sync
mkdir -p tmp/pdfs
uv run python -m scraper.download --mode backfill --max-pages 7
uv run python -m parser.parse --mode backfill
uv run python -m builder.build
```

### 일일 갱신

```bash
uv run python -m scraper.download --mode latest
uv run python -m parser.parse --mode latest
uv run python -m builder.build
```

### 환율 강화 (선택)

ECOS API 키 있으면:

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

## 환율 소스 전환

`builder/build.py` `resolve_rate()`:
- ECOS rate 있으면 → BOK 사용 (`source: "bok"`)
- 없으면 → PDF `market.krw_usd` 폴백 (`source: "pdf"`)

각 daily 엔트리의 `krw.source` 필드로 추적 가능.
