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

### 3. Node.js 20 deprecation warning

actions/checkout@v4 + setup-uv 사용 중. 2026-09-16 이후 Node 20 지원 종료. 그 전에 v5+ 또는 Node 24 force 필요. 비긴급.

## 진행 로그

- 02:18 KST — main merge + push
- 02:19 KST — 첫 워크플로우 실행 33s 성공, 1 row만 나옴 (소스 죽음 발견)
- 02:23 KST — RSS feeds 정비 commit + push
- 02:24 KST — 두 번째 워크플로우 1m11s 성공, **22 rows** (snmnews 11 + mining.com 10 + moneytoday 1)
- 02:25 KST — 데이터 품질 확인: 6 metals 다 분포, confidence median 0.9, sentiment 균형, 한국어 요약 정확
- 02:26 KST — Supabase 검토 → 보류 결정

## 진행 로그

(타임라인 — 각 step별 결과)
