# DB 스키마 상세

`~/life-dashboard/data.db` 전체 테이블 컬럼 정의.
원본: `schema.sql`

> **공통 컬럼:** 모든 테이블에 `created_at TEXT DEFAULT (datetime('now', 'localtime'))` 존재 (아래 생략).
> `daily_stats`, `coach_state`, `finance_investments`, `finance_loans`, `pantry_items`는 추가로 `updated_at` 보유.

---

## 작업 기록 (Work Tracking)

### activities (v1 호환 — Codex 세션 로거)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| source | TEXT NOT NULL | 세션 소스 |
| session_id | TEXT | 세션 식별자 |
| repo | TEXT | 레포 이름 |
| branch | TEXT | 브랜치 |
| tag | TEXT | 작업 태그 |
| summary | TEXT | 요약 |
| start_at | TEXT NOT NULL | 시작 시각 |
| end_at | TEXT | 종료 시각 |
| date | TEXT | 날짜 |
| duration_min | INTEGER | 소요 시간(분) |
| file_count | INTEGER | 변경 파일 수 |
| error_count | INTEGER | 에러 수 |
| has_tests | INTEGER | 테스트 포함 여부 |
| has_commits | INTEGER | 커밋 포함 여부 |
| token_total | INTEGER | 토큰 사용량 |
| status | TEXT | `in_progress` / `completed` |
| follow_up | TEXT | 후속 작업 |
| raw_json | TEXT | 원본 JSON |

**Unique:** `(source, session_id, date)`

### sessions (v2)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| source | TEXT NOT NULL | 세션 소스 |
| session_id | TEXT NOT NULL | 세션 식별자 |
| date | TEXT NOT NULL | 날짜 |
| repo | TEXT | 레포 이름 |
| branch | TEXT | 브랜치 |
| tag | TEXT | 작업 태그 |
| summary | TEXT | 요약 |
| summary_source | TEXT | `pending` / `llm` / `manual` |
| status | TEXT | `in_progress` / `completed` / `blocked` / `follow_up` |
| follow_up | TEXT | 후속 작업 |
| start_at | TEXT NOT NULL | 시작 시각 |
| end_at | TEXT | 종료 시각 |
| duration_min | INTEGER | 소요 시간(분) |
| file_count | INTEGER | 변경 파일 수 |
| error_count | INTEGER | 에러 수 |
| has_tests | INTEGER | 테스트 포함 |
| has_commits | INTEGER | 커밋 포함 |
| token_total | INTEGER | 토큰 사용량 |

**Unique:** `(source, session_id, date)`

### session_content

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| source | TEXT NOT NULL | 세션 소스 |
| session_id | TEXT NOT NULL | 세션 식별자 |
| date | TEXT NOT NULL | 날짜 |
| topic | TEXT | 주제 |
| user_messages | TEXT | 사용자 메시지 |
| agent_messages | TEXT | 에이전트 메시지 |
| files_changed | TEXT | 변경 파일 목록 |
| commands | TEXT | 실행 명령어 |
| errors | TEXT | 에러 내용 |

**FK:** `(source, session_id, date)` → `sessions`

### daily_stats

| 컬럼 | 타입 | 설명 |
|------|------|------|
| date | TEXT PK | 날짜 |
| work_hours | REAL | 총 작업 시간 |
| session_count | INTEGER | 세션 수 |
| tag_breakdown | TEXT | 태그별 분포 (JSON) |
| repos | TEXT | 레포별 분포 (JSON) |
| first_session | TEXT | 첫 세션 시각 |
| last_session_end | TEXT | 마지막 세션 종료 |

### signals (v2)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| session_id | TEXT NOT NULL | 세션 식별자 |
| date | TEXT NOT NULL | 날짜 |
| signal_type | TEXT NOT NULL | `mistake` / `pattern` / `decision` |
| content | TEXT NOT NULL | 신호 내용 |
| reasoning | TEXT | 근거 |
| repo | TEXT | 레포 |

**Unique:** `(session_id, signal_type, content)`

### coach_state

| 컬럼 | 타입 | 설명 |
|------|------|------|
| key | TEXT PK | 상태 키 |
| value | TEXT | 값 |

**기본값:** `escalation_level=0`, `consecutive_overwork_days=0`, `consecutive_no_exercise_days=0`

### coaching_entries

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| date | TEXT NOT NULL | 날짜 |
| period_type | TEXT NOT NULL | `daily` / `weekly` |
| content | TEXT NOT NULL | 코칭 본문 |
| sections | TEXT NOT NULL | 섹션 구조 (JSON) |
| escalation_level | INTEGER | 에스컬레이션 단계 |

**Unique:** `(date, period_type)`

### task_suggestions

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| suggested_date | TEXT NOT NULL | 제안일 |
| description | TEXT NOT NULL | 설명 |
| estimated_min | INTEGER | 예상 소요(분) |
| priority | INTEGER | 우선순위 |
| source_type | TEXT NOT NULL | 출처 유형 |
| origin_session_id | TEXT | 원본 세션 |
| status | TEXT | `pending` / `done` / `skipped` / `deferred` |
| resolved_date | TEXT | 해결일 |
| resolved_session_id | TEXT | 해결 세션 |
| resolution_method | TEXT | 해결 방법 |
| notes | TEXT | 비고 |

**Unique:** `(suggested_date, description)`

### followup_chains

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| origin_session_id | TEXT NOT NULL | 원본 세션 |
| origin_date | TEXT NOT NULL | 원본 날짜 |
| origin_repo | TEXT | 원본 레포 |
| description | TEXT NOT NULL | 설명 |
| status | TEXT | `open` / `resolved` |
| resolved_date | TEXT | 해결일 |
| resolved_session_id | TEXT | 해결 세션 |
| resolution_note | TEXT | 해결 메모 |

**Unique:** `(origin_session_id, origin_date, description)`

---

## 헬스

### health_exercises

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| date | TEXT NOT NULL | 날짜 |
| timestamp | TEXT NOT NULL | 시각 |
| type | TEXT NOT NULL | 운동 유형 |
| duration_min | INTEGER NOT NULL | 소요(분) |
| exercises | TEXT | 세부 운동 (JSON) |
| feeling | TEXT | 느낌 |
| notes | TEXT | 비고 |

**Unique:** `(date, timestamp, type)`

### health_symptoms

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| date | TEXT NOT NULL | 날짜 |
| timestamp | TEXT NOT NULL | 시각 |
| type | TEXT NOT NULL | 증상 유형 |
| severity | TEXT NOT NULL | 심각도 |
| description | TEXT NOT NULL | 설명 |
| trigger_factor | TEXT | 유발 요인 |
| duration | TEXT | 지속 시간 |
| status | TEXT | `진행중` 기본 |

**Unique:** `(date, timestamp, type)`

### health_pt_homework

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| exercise | TEXT NOT NULL | 운동명 |
| sets_reps | TEXT | 세트/횟수 |
| notes | TEXT | 비고 |
| status | TEXT | `할 일` 기본 |
| assigned_date | TEXT NOT NULL | 배정일 |
| completed_date | TEXT | 완료일 |

**Unique:** `(exercise, assigned_date)`

### health_check_ins

| 컬럼 | 타입 | 설명 |
|------|------|------|
| date | TEXT PK | 날짜 |
| sleep_hours | REAL | 수면 시간 |
| sleep_quality | INTEGER | 수면 질 |
| steps | INTEGER | 걸음 수 |
| workout | INTEGER | 운동 여부 |
| stress | INTEGER | 스트레스 |
| water_ml | INTEGER | 수분 섭취(ml) |
| notes | TEXT | 비고 |

### health_meals

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| date | TEXT NOT NULL | 날짜 |
| timestamp | TEXT NOT NULL | 시각 |
| meal_type | TEXT NOT NULL | 아침/점심/저녁/간식 |
| food_items | TEXT | 음식 항목 (JSON) |
| portion | TEXT | 포션 크기 |
| skipped | INTEGER | 결식 여부 |
| calories | INTEGER | 칼로리 |
| protein_g | REAL | 단백질(g) |
| carbs_g | REAL | 탄수화물(g) |
| fat_g | REAL | 지방(g) |
| notes | TEXT | 비고 |

**Unique:** `(date, timestamp, meal_type)`

---

## 식재료

### pantry_items

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| name | TEXT NOT NULL | 식재료명 |
| category | TEXT NOT NULL | 카테고리 |
| quantity | REAL NOT NULL | 수량 |
| unit | TEXT NOT NULL | 단위 |
| location | TEXT NOT NULL | 보관 위치 |
| purchase_date | TEXT | 구매일 |
| expiry_date | TEXT | 유통기한 |
| status | TEXT | `재고 있음` 기본 |
| notes | TEXT | 비고 |

**Unique:** `(name, location)` — upsert 시 수량 누적(+)

---

## 금융

### finance_transactions

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| date | TEXT NOT NULL | 거래일 |
| time | TEXT | 거래 시각 |
| amount | REAL NOT NULL | 금액 |
| currency | TEXT | `KRW` 기본 |
| tx_type | TEXT | 거래 유형 |
| category_l1 | TEXT | 1차 카테고리 |
| category_l2 | TEXT | 2차 카테고리 |
| merchant | TEXT | 가맹점 |
| payment | TEXT | 결제 수단 |
| memo | TEXT | 메모 |
| import_key | TEXT NOT NULL UNIQUE | 중복 방지 키 |
| source | TEXT | `banksalad` 기본 |

### finance_investments

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| product_name | TEXT NOT NULL | 상품명 |
| product_type | TEXT | 상품 유형 |
| institution | TEXT | 기관 |
| invested | REAL | 투자 원금 |
| current_value | REAL | 현재 가치 |
| return_pct | REAL | 수익률 |
| currency | TEXT | `KRW` 기본 |
| source | TEXT | `banksalad` 기본 |

**Unique:** `(product_name, institution)`

### finance_loans

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| loan_name | TEXT NOT NULL | 대출명 |
| loan_type | TEXT | 대출 유형 |
| institution | TEXT | 기관 |
| principal | REAL | 원금 |
| outstanding | REAL | 잔액 |
| interest_rate | REAL | 이자율 |
| start_date | TEXT | 시작일 |
| end_date | TEXT | 만기일 |
| source | TEXT | 데이터 출처 (`banksalad` 기본) |

**Unique:** `(loan_name, institution, principal)`

### finance_price_snapshots

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동증가 |
| product_name | TEXT NOT NULL | 상품명 |
| date | TEXT NOT NULL | 날짜 |
| price | REAL NOT NULL | 가격 |
| currency | TEXT | `KRW` 기본 |
| source | TEXT | 데이터 출처 |

**Unique:** `(product_name, date)`

### finance_merchant_categories

| 컬럼 | 타입 | 설명 |
|------|------|------|
| merchant | TEXT PK | 가맹점명 |
| category_l1 | TEXT NOT NULL | 1차 카테고리 |
| category_l2 | TEXT | 2차 카테고리 |
