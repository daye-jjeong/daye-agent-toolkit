---
name: spending-manager
description: 소비 분석 — 카테고리 요약, 추세, 미분류 정리, 예산 관리
---

# Spending Manager

소비 데이터 조회·분석 스킬. DB: `~/life-dashboard/data.db`

## 데이터 소스

- `finance_transactions` — 뱅크샐러드 import (banksalad-import 스킬)
- `finance_merchant_categories` — 미분류 merchant → 카테고리 매핑
- `coach_state` — 예산 설정 저장

## 스크립트

```bash
python3 {baseDir}/scripts/spending_query.py <mode> [options]
```

### 모드

| 모드 | 설명 | 예시 |
|------|------|------|
| `summary` | 기간별 카테고리 요약 | `--month 2026-03` 또는 `--from 2026-01-01 --to 2026-03-07` |
| `trend` | 월별 카테고리 비교 | `--months 3` (최근 N개월) |
| `top` | Top merchant + 반복 지출 | `--month 2026-03` |
| `uncategorized` | 미분류 merchant 목록 | (옵션 없음) |

모든 모드 출력: JSON (stdout)

## 사용 흐름

### 1. 요약 ("이번달 소비", "2월 소비 얼마야")
1. `spending_query.py summary --month YYYY-MM` 실행
2. JSON 결과를 한국어로 요약: 총 지출, 카테고리별 금액/비중, 고정비/변동비 분리

### 2. 추세 ("소비 추세", "지난 3개월 비교")
1. `spending_query.py trend --months N` 실행
2. 월별 총액 비교, 증감 큰 카테고리 하이라이트

### 3. 분석 ("어디서 많이 쓰지", "반복 지출")
1. `spending_query.py top --month YYYY-MM` 실행
2. Top 10 merchant, 주 1회 이상 반복 지출 패턴 분석

### 4. 재분류 ("미분류 정리")
1. `spending_query.py uncategorized` 실행
2. 미분류 merchant 목록을 사용자에게 보여주고 카테고리 매핑 제안
3. 사용자 확인 후 `finance_merchant_categories`에 INSERT
4. 기존 transactions의 category_l1도 UPDATE

### 5. 예산 ("예산 설정 식사 30만원")
1. `coach_state`에 `budget_{category}` 키로 저장
2. summary 실행 시 예산 대비 초과 여부 표시

## 카테고리 분류

고정비: 주거/통신, 자동차, 교육
변동비: 나머지 전부

## 출력 규칙

- 금액은 원 단위, 천원 이상은 쉼표 포맷
- 비중은 소수점 1자리 %
- 지출은 양수로 표시 (DB에는 음수로 저장됨)
