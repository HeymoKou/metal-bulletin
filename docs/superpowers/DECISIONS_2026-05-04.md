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

(이 섹션은 진행 중 발견된 항목으로 계속 업데이트)

## 진행 로그

(타임라인 — 각 step별 결과)
