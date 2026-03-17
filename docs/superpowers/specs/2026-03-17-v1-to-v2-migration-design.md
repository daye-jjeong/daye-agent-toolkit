# v1→v2 DB 마이그레이션 설계

## 목표

life-dashboard DB의 v1 테이블(`activities`, `behavioral_signals`)에 대한 모든 코드 의존성을 v2 테이블(`sessions`, `signals`)로 전환하고, v1 코드를 제거한다.

## 배경

session_logger(CC)가 v2 `record_sessions`로 전환되었지만, 소비자(self-profile, Codex 로거)가 여전히 v1을 사용하여 데이터 단절 발생:
- `activities`: 3/17 데이터 0건 (CC가 더 이상 쓰지 않음)
- `behavioral_signals`: 3/14 이후 멈춤
- `self-profile/collect.py`가 v1만 조회 → 최근 데이터 누락

## v1 vs v2 테이블 매핑

| v1 | v2 | 차이점 |
|----|-----|--------|
| `activities` | `sessions` | v2에 summary_source, status 추가. raw_json 제거 |
| `behavioral_signals` | `signals` | v2에 reasoning 필드 추가 |

컬럼 구조가 거의 동일하므로 쿼리 대상만 교체하면 된다.

## 변경 범위

### 1. self-profile/scripts/collect.py — 쿼리 전환

- `_query_activities()` → sessions 테이블 조회로 변경
- `_collect_behavioral_signals()` → signals 테이블 조회 + reasoning 필드 포함
- `_build_daily_trend()` → sessions 기반 데이터 사용

### 2. self-profile/tests/test_collect.py — fixture 전환

- v1 테이블 INSERT → v2 테이블 INSERT

### 3. codex/work-digest/scripts/session_logger.py — 호출 전환

- `record_activities` → `record_sessions` 전환
- `is_session_end` 파라미터 추가 (session_end 이벤트 시)
- record_sessions가 이미 plain string + dict 둘 다 처리하므로 signal 포맷 변경 불필요

### 4. life-dashboard-mcp/activity_writer.py — v1 함수 제거

- `record_activities()` 함수 전체 삭제
- export에서 제거

### 5. life-dashboard-mcp/db.py — v1 함수/fallback 제거

- `upsert_activity()` 삭제
- `insert_behavioral_signal()` 삭제
- `get_repeated_signals()`: behavioral_signals fallback 분기 삭제
- `get_mistake_trends()`: behavioral_signals fallback 분기 삭제
- `update_daily_stats()`: activities fallback 분기 삭제
- v1 관련 migration 코드 삭제

### 6. life-dashboard-mcp/schema.sql — v1 테이블 정의 제거

- activities CREATE TABLE + 인덱스 삭제
- behavioral_signals CREATE TABLE + 인덱스 삭제

### 7. life-dashboard-mcp/backfill_tags.py — v1 fallback 제거

- activities fallback 경로 삭제, sessions만 조회

### 8. cc/work-digest/scripts/session_logger.py — 버그 수정

- signals 실패 시에도 `record_sessions(is_session_end=True)` 호출하도록 변경
- 현재: 실패 시 직접 SQL UPDATE만 → record_sessions 내부 로직 우회

## 안 바꾸는 것

- collect.py 함수 구조/시그니처
- record_sessions 내부 로직
- v2 테이블 스키마
- 실제 DB의 v1 테이블 (DROP하지 않음, 히스토리 보존)

## 검증 기준

- self-profile collect.py 테스트 통과
- 기존 session_topics 테스트 통과
- Codex 로거가 sessions 테이블에 정상 기록 확인
- CC session_logger SessionEnd에서 status=completed 정상 처리 확인
