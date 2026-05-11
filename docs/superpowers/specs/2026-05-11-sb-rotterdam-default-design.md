# Sb 안티모니 메인 가격/차트를 Rotterdam으로 변경

**Date:** 2026-05-11
**Status:** Design approved, awaiting implementation plan

## 목적

Sb(안티모니) 대시보드의 메인 가격과 차트 기본 시리즈를 현재 `exw_china`(중국 EXW)에서 `rotterdam`(로테르담 창고)으로 교체. 5개 지역(EXW China, FOB China, Port India, Rotterdam, Baltimore) 비교 테이블은 그대로 유지.

## 배경

`scraper/sb.py`가 ScrapMonster에서 5개 지역 가격을 모두 수집. `data/series/antimony/*.parquet`에 5개 컬럼 모두 저장 중. FE는 메인 시세 표시와 차트에 `exw_china`를 hardcoded.

User 요청: 메인 표시 기준을 rotterdam으로 변경. 5지역 비교 카드는 그대로.

## 변경 범위

파일: `site/app.js` 일부 위치 (총 4곳)

| 라인 | 현재 | 변경 |
|------|------|------|
| 378 | `function minorPriceSeries(data, region = 'exw_china', count = 24)` | `region = 'rotterdam'` |
| 390 | `minorPriceSeries(ts.data, 'exw_china', 24)` | `'rotterdam'` |
| 392-393 | `latest.exw_china`, `ts.data[1]?.exw_china` | `latest.rotterdam`, `ts.data[1]?.rotterdam` |
| 486-487 | `latest?.exw_china`, `ts?.data?.[1]?.exw_china` | `rotterdam` |
| 926 | `minorPriceSeries(data, 'exw_china', data.length)` | `'rotterdam'` |

**유지:** line 357-361 (5지역 한/영 라벨), 369-373 (5지역 flatten), 398 (5지역 비교 테이블).

## Edge cases

- **Rotterdam 가격이 결측인 날** — 기존 `num()` helper가 NaN 반환. 차트는 gap, 메인 가격은 직전 valid 값 표시 (현재 `exw_china`에도 동일 처리 적용 중).
- **신규 minor metal 추가** — `minorPriceSeries` 시그니처 그대로. Sb 외 minor metal이 추가되면 기본 region을 따로 결정.

## 테스트

기존 `npm run smoke` 통과 여부 확인. 추가 단위 테스트는 사소한 컬럼 교체이므로 불필요.

수동 검증: `site/desk` 페이지에서 Sb 카드의 메인 가격이 5지역 비교 테이블의 Rotterdam 행과 일치하는지 확인.

## Out of scope

- 사용자가 차트 region을 토글하는 UI — 별도 작업
- exw_china/baltimore/등 컬럼 제거 — 5지역 비교 테이블 유지
- backend 변경 — 데이터는 그대로
