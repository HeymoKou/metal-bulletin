# 2026-05-11 세션 요약

5개 요청 + 사후 검증/대응 기록.

## 요청 및 결과

| # | 요청 | 결과 | 핵심 commits |
|---|------|------|--------------|
| 1 | 정산가 column shift bug 진단/수정 | ✅ 완료 — live 반영 | `2018866` parser swap + migration |
| 2 | 뉴스 snmnews만 수집 | ✅ 완료 — purge 39 row legacy | `471a6b0`, `fc4f6eb` purge |
| 3 | 조달청 PPS 주간리포트 통합 | 🟡 defer — code 보존, CI 차단 확정 | `07393e6` ~ `7cf236b`, `fc4f6eb` defer |
| 4 | Sb hero/chart rotterdam | ✅ 완료 — label까지 수정 | `63451ea`, `4155733` label fix |
| 5 | KOMIS API 통합 | ❌ drop — LME CASH 100% 중복 검증 | — |

## #1 정산가 swap 상세

**진단** (`/superpowers:systematic-debugging`):
- `sett_mavg_cash` 5월 내내 12891.38 고정 → 4월 평균 의심
- `sett_prev_mavg_cash` 매일 변동 → 5월 누적 의심
- 4월 daily mean 계산: 12891.375 → 12891.38과 일치 → 전월평균 확정
- **PDF col[4-5] = 전월평균, col[6-7] = 당월평균** (코드는 반대 매핑)

**수정 범위:**
- `parser/page1.py:73-80` 인덱스 swap
- `scripts/migrate_swap_mavg.py` — 일회성 마이그레이션, `data/raw/*.parquet` + `data/daily/*.json` swap (2015~ 2630 entries)
- `data/raw/2026.parquet` git restore 후 daily/에 missing 4 dates 복원 (builder 재실행이 raw 덮어쓴 incident)
- `builder.build` 재실행 → series + manifest 재생성
- `tests/test_parser.py` fixture 기댓값 swap

**Verification (live):** Cu 2026-05-08 `당월평균 Cash = $13,515.39`, `전월평균 Cash = $12,891.38` (browser screenshot 검증).

## #2 뉴스 source 정리

`scraper/news/rss.py`: mining.com/moneytoday 제거 → snmnews만.
`scraper/news/run.py`: GDELTScraper 제거, PPSScraper 도입 → 후에 CI block 확인 후 다시 RSS-only.
`scripts/purge_old_news_sources.py`: parquet upsert로 잔존한 39 row 정리.

## #3 PPS 통합 (Defer)

8-task plan 따라 구현 완료:
- `scraper/news/pps.py` — list HTML scrape + view POST + PDF download + pdfplumber 텍스트 추출
- `parser/news/classify.py:is_relevant` — `source == 'pps'` bypass
- Glyph dedupe: 한국어 4+ 연속 동일 char → 1 (pdfplumber artifact 처리)
- `tests/news/test_pps.py` — 6 fixture-based tests, monkeypatch network
- Live local test: 2 items 정상 (snippet 1421/8863 char)

**CI 차단 검증 (2026-05-11):**

| 호스트 | IP | 결과 |
|--------|----|----|
| 로컬 (heymo Mac, KR 가정) | 124.5.248.6 | ✅ HTTP 200, 1907 byte |
| GitHub Actions (AWS us-east) | — | ❌ `ConnectionResetError(104)` |
| Teleport bastion (AWS Tokyo) | 54.249.202.64 | ❌ empty response |
| **Lambda ap-northeast-2 (Seoul)** | **15.165.8.180** | ❌ `Connection reset by peer` |

→ PPS가 ASN/cloud-IP-range 기반 차단. region 변경 무의미. KR residential IP만 통과.

**대안 검토 (defer):**
- Smartproxy/BrightData KR residential proxy: $5-30/월
- 집 Mac launchd cron: 무료, Mac on 시
- Tailscale + 집 RPi runner: RPi 1회비
- **현 결정**: defer 유지 — 추가 인프라 비용 0.

`scripts/lambda_pps_test.py` — stdlib only Lambda 검증 코드 보존.

## #4 Sb rotterdam 전환

`site/app.js` 6곳 `exw_china` → `rotterdam`:
- `minorPriceSeries` default region
- hero `mainPrice`, `prev`, label tag
- nav pill `close`/`prev`
- expand-minor chart title

5지역 비교 테이블 유지 (라벨/맵 그대로).

**Live verification (browser screenshot):**
- Hero: `$26,438.16 ROTTERDAM · 기준` ✓ (initially `EXW China · 기준` 라벨 남아있어 `4155733` 후속 fix)
- delta +$1,583.42 (+6.37%) = rotterdam day-over-day 정확

## #5 KOMIS drop 근거

- data.go.kr KOMIS Open API: **0건** (Korean Public Data Portal 검색)
- kores.net OpenAPI 페이지: 403 Forbidden
- KOMIS 비철 페이지 (komis.or.kr): JS-rendered (Playwright 필요)
- KOMIS 비철 LME CASH = NH PDF의 sett_cash와 동일 source: **2026-05-08 Ni 18890.0 양쪽 일치** 확인
- → 추가 가치 없음, 통합 무의미

## 테스트 상태

- Python: 132 tests pass (66 기존 + PPS 6 + classify 1 + structural smoke 12 + 추가)
- JS smoke: 8/8 pass
- `tests/test_post_migration_smoke.py`: 12 structural invariant 검증 (settlement migration, source pipeline, classify bypass, Sb rotterdam, parquet schema)

## Live verification

- Cu 정산가 박스 screenshot 확인 (당월/전월 모두 정확)
- Sb 안티몬 박스 screenshot 확인 (Rotterdam 라벨 + 정확한 delta)
- Pages 배포 모두 success
- live parquet 데이터 정합성 검증
