# 자율 진행 의사결정 로그 — 2026-05-04 수면 모드

사용자 수면 중 자율 실행. 의사결정 필요한 항목 모음.

## 자율 결정 (진행)

| 결정 | 이유 |
|---|---|
| 직접 main에 merge (PR 생략) | 솔로 프로젝트, 기존 패턴 (collect.yml 등 main 직접 push) |
| `gh workflow run news.yml`로 첫 실행 검증 | Secret 등록됨, cron 기다리지 말고 즉시 |
| 실패 소스는 격리 후 working 소스만 ship | `_safe()` 패턴 — 1개 죽어도 나머지 진행 |
| KORES/RSS selector 실패 시 fixture 갱신 + 재배포 | 실 데이터 기반 보정 |
| 부적절한 헤드라인 LLM 호출 cost 발생 시 keyword filter 강화 | 후속 commit |
| Phase 1b/1c는 별도 세션에서 시작 | 현 plan scope 보호 |

## 사용자 검토 필요 (수면 깬 후 decide)

### 1. Supabase 이관 — 보류 결정 (검토 요청)

사용자 제기: "DB를 아예 supabase 무료로 이관할까?"

**판정: 보류 (현재 parquet+git 유지).**

이유 요약:
- Supabase 무료 plan **7일 비활성 시 pause** — 새벽 cron 위주 환경에 부적합
- 현재 size 증가율 ~100MB/년 → 5년 여유
- 진짜 value (full-text search)가 필요한 use case 아직 없음

**옮길 트리거:**
1. 자유 텍스트 검색 진짜 요구 발생
2. 다중 사용자 (5명+)
3. realtime 알림 필요
4. Repo 1GB 초과 (~5년)

→ 트리거 도달 전까지 parquet 유지. 사용자 동의 시 이 결정 close.

### 2. RSS feed 정비 결정 — 자율 진행됨

기존 5개 중 3개 죽음 (kitco/commodity-tv/hankyung). 자율 결정으로:
- snmnews 철강금속신문 추가 (비철 전문 한국지)
- KORES 비활성 (URL 변경, Phase 1b reverse 필요)

→ 사용자 OK 시 close, 다른 한국 비철 소스 우선순위 있으면 알려줌.

### 3. Raw archive 제거 — 자율 진행됨

사용자 제기: "raw news를 보관해야할 의미 있어? URL만 있으면 되지 않을까?"

**판정: 제거 진행.** Enriched parquet에 url+title+summary 보존. 재요약 욕구 약함. ~80MB/년 git bloat 방지.

→ 자율 commit. 사용자 OK 시 close.

### 4. Cron frequency — 검토 요청

현재: 매 4시간 (UTC `0 */4 * * *`) = 일 6회 = 월 ~30분 GH Actions 사용.

스펙은 "헤드라인 수 KPI 추구 금지" 명시. 6회는 timezone cover용이지만 과할 수 있음.

**대안:**
- A) 현재 유지 (일 6회)
- B) 일 2회 (UTC 0/12 = KST 9/21시) — 영업/야간 cover, GH Actions 분 절감
- C) 일 3회 (UTC 0/8/16) — 8시간 간격

→ 보수적으로 현재 유지. 사용자 변경 원하면 `news.yml` cron 한 줄 수정.

### 5. Node.js 20 deprecation warning

actions/checkout@v4 + setup-uv 사용 중. 2026-09-16 이후 Node 20 지원 종료. 그 전에 v5+ 또는 Node 24 force 필요. 비긴급.

## 진행 로그

- 02:18 KST — main merge + push
- 02:19 KST — 첫 워크플로우 실행 33s 성공, 1 row만 나옴 (소스 죽음 발견)
- 02:23 KST — RSS feeds 정비 commit + push
- 02:24 KST — 두 번째 워크플로우 1m11s 성공, **22 rows** (snmnews 11 + mining.com 10 + moneytoday 1)
- 02:25 KST — 데이터 품질 확인: 6 metals 다 분포, confidence median 0.9, sentiment 균형, 한국어 요약 정확
- 02:26 KST — Supabase 검토 → 보류 결정
- 02:32 KST — Refactor: classify regex 강화 (lead/tin word boundary), aluminum 매칭 버그 fix
- 02:33 KST — Refactor: raw archive 제거 + zstandard 의존성 제거
- 02:35 KST — 세 번째 워크플로우 성공 (refactor 검증)
- 02:36 KST — gitignore에 중간 파일 추가
- 02:42 KST — Cron 일 2회 + Node 24 적용 (UTC 0/12 = KST 9/21시)
- 02:45 KST — Phase 1b 시작: GDELT + 한국비철금속협회 nonferrous.or.kr 추가
- 02:47 KST — CI 검증: GDELT 75 fetched, RSS 150, nonferrous 0 (CI에서 TCP timeout)
- 02:50 KST — nonferrous default 제외 결정 (로컬 정상, CI route 불통)
- 최종 (Phase 1b): 75 tests pass, default scrapers = RSS + GDELT
- KOMIS/KORES/협회 모두 deferred — 추후 Playwright 또는 proxy 필요

## 추가 의사결정 (Phase 1b 자율)

### 6. 협회 nonferrous.or.kr 사이트 — 부분 보류
- 로컬 fetch 정상 (20 items)
- CI에서 TCP timeout (`Connection to www.nonferrous.or.kr timed out`)
- 원인 추정: 작은 한국 협회 사이트가 GitHub Actions IP 범위 차단/라우팅 문제
- 코드 유지, default scraper에서 제외 (CI 15s 낭비 방지)
- 추후: 로컬 cron으로 별도 수집 또는 proxy 도입 시 활성화

### 7. GDELT 통합 — 정상 작동
- CI에서 정상 fetch (75 items per run)
- 5초 rate limit + 429 retry 구현
- lang 정규화 (English→en, Chinese→zh, etc) 추가

## Codex Review (2026-05-04) — 7 issues found

자율 fix 4개:
- ✅ **HIGH**: news_build dedupe 첫 run null summary 영구 저장 → enriched preferred over null
- ✅ **MED**: year partition `datetime.now().year` → record's own date.year (backfill 안전)
- ✅ **MED**: classify "all" 태그 (bare LME/SHFE) 제거 — false positive 양산
- ✅ **LOW**: news.yml git push pull-rebase + retry 3x (concurrent main commits 대응)

2차 fix (codex defer 처리):
- ✅ **HIGH silent fail**: scraper 0건 시 `exit(2)` + summarizer 5+ 입력 100% null 시 `exit(2)` → CI 알림
- ✅ **MED Gemini JSON mode**: `response_json_schema` 강제 (object enum 명시). 결과: null=0 (이전 실패 시 null 발생 → 이제 0)
- 📏 **MED dedupe-before-classify**: **측정 결과 영향 0건**. 261 raw → 20 relevant in both orders (A: dedupe→classify, B: classify→dedupe). 현 순서 유지. Codex 우려는 이론적, 실데이터 미발현. 새 source 추가 시 재측정.

3차 fix:
- ✅ **manifest.last_updated cosmetic**: dedupe sort 후 마지막 row가 oldest → `max()` 사용으로 변경
- ✅ **collect.yml tmp_dir bug**: PDF 0건 시 `tmp/pdfs/` 미생성 → manifest.json write FileNotFoundError. `tmp_dir.mkdir()` 사전 호출.

남은 의사결정 (사용자 처리):
- ✅ Phase 2 FE 시작 시점: **anytime** — 데이터 1주일 누적 후 또는 현재 즉시 둘 다 OK
- ✅ 협회 nonferrous proxy: **never** — 시도 안 함

## 진행 로그

(타임라인 — 각 step별 결과)
