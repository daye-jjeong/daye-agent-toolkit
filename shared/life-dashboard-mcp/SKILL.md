---
name: life-dashboard-mcp
description: 공유 SQLite DB MCP 서버 — 활동·건강·금융·식재료 통합 저장소. 독립 스킬 아님, 다른 스킬이 내부적으로 참조.
user-invocable: false
disable-model-invocation: true
---

## 역할

`~/life-dashboard/data.db` (SQLite) 를 공유 저장소로 제공하며, 다음 두 가지 인터페이스를 노출한다.

1. **MCP 서버** (`server.py`) — 활동 데이터 조회용 도구 3종
2. **Python 라이브러리** (`db.py`, `activity_writer.py`) — 다른 스킬이 직접 import

---

## 의존 스킬 (참조 관계)

| 스킬 | 참조 방식 | 주요 테이블 |
|------|-----------|-------------|
| `life-coach` | activity_writer.py CLI + MCP 도구 | `sessions`, `session_content`, `coaching_entries`, `task_suggestions`, `signals` |
| `health-tracker` | db.py 직접 import | `health_exercises`, `health_symptoms`, `health_pt_homework`, `health_check_ins` |
| `meal-tracker` | db.py 직접 import | `health_meals` |
| `pantry-manager` | db.py 직접 import | `pantry_items` |
| `banksalad-import` | db.py 직접 import | `finance_transactions`, `finance_investments`, `finance_loans`, `finance_price_snapshots` |

---

## MCP 도구 인터페이스

서버 이름: `life-dashboard`
프로토콜: stdio (MCP 1.0+)
기동: `python3 server.py`

### 도구 목록

#### `get_today_summary`
오늘(KST) 활동 요약을 반환한다.

```json
Input:  {}
Output: {
  "date": "YYYY-MM-DD",
  "has_data": true,
  "work_hours": 5.2,
  "session_count": 8,
  "first_session": "09:15",
  "last_session_end": "18:43",
  "tag_breakdown": {"코딩": 4, "리뷰": 2, "설계": 2},
  "repos": {"cube-backend": 5, "daye-agent-toolkit": 3},
  "sessions": [...],
  "coach_state": {"escalation_level": "0", "consecutive_overwork_days": "1", ...}
}
```

#### `get_date_summary`
특정일 활동 요약.

```json
Input:  {"date": "2026-03-15"}
Output: (get_today_summary와 동일 구조)
```

#### `get_weekly_summary`
최근 7일 합산 요약.

```json
Input:  {"end_date": "2026-03-17"}   // 생략 시 오늘
Output: {
  "period": "2026-03-11 ~ 2026-03-17",
  "total_work_hours": 34.5,
  "active_days": 6,
  "daily": [...],   // 각 날짜의 date_summary
  "coach_state": {...}
}
```

---

## DB 접근 레이어 (db.py)

**DB 경로:** `~/life-dashboard/data.db`
**스키마 초기화:** `get_conn()` 호출 시 `schema.sql` 자동 적용 (멱등)
**WAL 모드** 활성화, 동시 쓰기 충돌 방지.

import 패턴 및 activity_writer.py CLI 사용법은 `references/api-reference.md` 참조.

---

## DB 스키마 개요

4개 도메인, 총 21개 테이블. 상세 컬럼 정의는 `references/schema-detail.md` 참조.

| 도메인 | 테이블 | 역할 |
|--------|--------|------|
| **작업** | `sessions` | v2 세션 (source, session_id, date 복합 PK) |
| | `activities` | v1 호환 (Codex 세션 로거, 레거시) |
| | `session_content` | 세션 원문 (messages, files, commands, errors) |
| | `daily_stats` | 일별 집계 캐시 |
| | `signals` | v2 행동 신호 (mistake, pattern, decision) |
| | `behavioral_signals` | v1 행동 신호 (레거시) |
| | `coaching_entries` | 코칭 내용 (daily/weekly/monthly) |
| | `task_suggestions` | 코칭에서 추출한 태스크 제안 |
| | `followup_chains` | follow-up 추적 |
| | `coach_state` | escalation_level 등 코치 상태 KV |
| **헬스** | `health_exercises`, `health_symptoms`, `health_pt_homework`, `health_check_ins`, `health_meals` | 운동·증상·PT·체크인·식사 |
| **식재료** | `pantry_items` | 식재료 재고 (name+location unique) |
| **금융** | `finance_transactions`, `finance_investments`, `finance_loans`, `finance_price_snapshots`, `finance_merchant_categories` | 거래·투자·대출·시세·가맹점매핑 |

---

## 크론 (cron.json)

| 이름 | 스케줄 | 동작 |
|------|--------|------|
| `life-dashboard-sync` | 매일 20:50 | `sync_calendar.py --days 1` — 캘린더 → SQLite |

---

## 주의 사항

- `get_conn()` 은 `_schema_initialized` 전역 플래그를 사용하므로 **프로세스당 한 번만 초기화**된다. 다중 프로세스 환경에서는 각자 초기화.
- `sessions` v2 테이블이 있으면 `activities` v1보다 우선 사용 (`daily_stats` 집계, `get_repeated_signals` 등).
- `upsert_pantry_item`은 같은 `(name, location)` 충돌 시 **수량을 누적(+)** 한다 — 덮어쓰지 않음.
