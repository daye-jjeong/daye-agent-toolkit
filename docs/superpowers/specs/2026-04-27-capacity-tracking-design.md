# Capacity Tracking — 통합 캐파/일정 시스템 (Phase 1 단일 milestone)

**Date**: 2026-04-27 (created), 2026-04-28 (revised v2/v3/v4)
**Owner**: daye
**Status**: Design (brainstorming, post-adversarial revision v5 — ship-ready)
**Related**: todo #35 (Phase 1) — life-coach 개선
**Codex review history**:
- v1 (2026-04-27): H1/H2/H3/M4 4 finding
- v2 (2026-04-28, gpt-5.5): 7 finding + 4 silent fail
- v3 (2026-04-28): v2 #1~#4, #6, #7 반영
- v4 (2026-04-28): v3 ship 권고 4개 반영
- v5 (2026-04-28): v4 BLOCK 해소 — `todo_schedule_actuals`를 immutable snapshot identity로 변경 (work-digest task 재생성에도 actual 보존)

## 1. 배경

매일 할일 관리 문제: 놓침 / 까먹음 / 방향 틂. 캐파 데이터를 **구조화 + 누적**해야 추천 엔진(#37) 가능.

본 spec은 **Phase 1 단일 milestone** — 데이터 모델 입력/검증/저장/조회까지 한 번에 닫혀야 의미 있음.

캘린더 동기, 누적 시각화, 추천 엔진, 종속성은 후속 (§14).

## 2. 목표 / 비목표

**목표**:
- `daily_checkins` +3 캐파 필드 + +3 status 컬럼 (영속화)
- `todo_schedules` 신규 — 분할 작업 + 시간 슬롯 + idempotency
- `todo_schedule_actuals` 신규 브리지 — work-digest task 연결, stale 방지, 중복 방지
- 아침/저녁 — 자연어 인터뷰 → script wrapper subcommand → DB
- `/morning` `/evening` `/capacity` 슬래시 커맨드
- estimated_min 입력 정책 (1-B + 1-C, tri-state 인자)
- **캐파 단일 소스** + **planned/actual/conflict 분리 reconcile** + **field status 영속화**

**비목표** (별도 todo):
- iCloud + EventKit MCP → **#38**
- 누적 시각화 + 방향 전환 추적 → **#36**
- 추천 엔진 → **#37**
- todos `blocked_by` → 별도

## 3. 아키텍처

```
[입력]   사용자 자연어
  ↓
[인터뷰] 에이전트 — 묻고 듣고 모호하면 재질문 (SKILL.md)
  ↓
[Wrapper] script CLI subcommand — 인자 검증, 변환, FK/identity 재검증, idempotency
  ↓
[Storage] db.py — schema CHECK + UNIQUE 통과 시 INSERT/UPDATE
  ↓
[활용]   `/capacity` 누적 / 추천(#37) / 캘린더(#38)
```

**핵심 원칙 (v4 강화)**:
- SoT 레이어: `schema.sql → db.py → scripts → SKILL.md/commands`. 역순 금지
- 에이전트는 wrapper CLI만 호출. db.py 직접 호출 금지. read도 wrapper 경유
- **field status 영속화**: 'answered' / 'skipped' / 'unknown'을 DB에 저장. NULL value 의미 모호성 차단
- 추출 실패는 wrapper 거부 → 재질문
- **idempotency**: 같은 슬롯 두 번 저장 차단 (partial unique index)
- **task identity 자동 검증**: actual 매칭 시 wrapper가 task table에서 `date`/`duration_min` 직접 읽음. 에이전트가 못 위조
- 단일 진실: `daily_checkins.available_min`이 캐파 budget. reconcile 4종 분리

## 4. DB 스키마

### 4.1 daily_checkins (기존 확장)

```sql
ALTER TABLE daily_checkins ADD COLUMN available_min INTEGER
  CHECK (available_min IS NULL OR available_min >= 0);
ALTER TABLE daily_checkins ADD COLUMN energy TEXT
  CHECK (energy IS NULL OR energy IN ('low','mid','high'));
ALTER TABLE daily_checkins ADD COLUMN blockers TEXT;

ALTER TABLE daily_checkins ADD COLUMN available_status TEXT NOT NULL DEFAULT 'unknown'
  CHECK (available_status IN ('answered','skipped','unknown'));
ALTER TABLE daily_checkins ADD COLUMN energy_status TEXT NOT NULL DEFAULT 'unknown'
  CHECK (energy_status IN ('answered','skipped','unknown'));
ALTER TABLE daily_checkins ADD COLUMN blockers_status TEXT NOT NULL DEFAULT 'unknown'
  CHECK (blockers_status IN ('answered','skipped','unknown'));
```

| 컬럼 | 타입 | 의미 |
|------|------|------|
| `available_min` | INTEGER NULL | 가용 분(min) — **캐파 budget 단일 소스** |
| `energy` | TEXT NULL CHECK | 컨디션 |
| `blockers` | TEXT NULL | 자유 텍스트 |
| `available_status` | TEXT NOT NULL CHECK | 'answered' / 'skipped' / 'unknown' |
| `energy_status` | TEXT NOT NULL CHECK | 동일 |
| `blockers_status` | TEXT NOT NULL CHECK | 동일 |

**Codex v3 #1 반영**: status 영속화. legacy row는 default 'unknown'. wrapper가 'answered' 또는 'skipped'를 명시적으로 설정해야 NULL 의미 분명.

### 4.2 todo_schedules (신규)

```sql
CREATE TABLE IF NOT EXISTS todo_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    todo_id INTEGER NOT NULL,
    date TEXT NOT NULL,                        -- 'YYYY-MM-DD' (KST)
    start_at TEXT,                             -- 'HH:MM' NULL OK
    end_at TEXT,                               -- 'HH:MM' NULL OK
    planned_min INTEGER NOT NULL,              -- canonical duration. wrapper가 시간 슬롯이면 자동 계산
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    CHECK (
      (start_at IS NULL AND end_at IS NULL) OR
      (start_at IS NOT NULL AND end_at IS NOT NULL)
    ),
    CHECK (start_at IS NULL OR end_at > start_at),
    CHECK (start_at IS NULL OR start_at GLOB '[0-2][0-9]:[0-5][0-9]'),
    CHECK (end_at IS NULL OR end_at GLOB '[0-2][0-9]:[0-5][0-9]'),
    CHECK (planned_min > 0),

    FOREIGN KEY(todo_id) REFERENCES todos(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_todo_schedules_date ON todo_schedules(date);
CREATE INDEX IF NOT EXISTS idx_todo_schedules_todo ON todo_schedules(todo_id);

-- Codex v3 #4 반영: idempotency. 시간 슬롯 있는 row는 (todo_id, date, start_at, end_at) UNIQUE
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_time_slot
  ON todo_schedules(todo_id, date, start_at, end_at)
  WHERE start_at IS NOT NULL;
```

**Codex v3 #4 반영**: partial unique index. 시간 슬롯 있는 row의 같은 (todo, 날짜, 시작/끝) 중복 차단. 시간 미지정 row는 사용자가 의도적으로 여러 분량 슬롯 잡을 수 있으니 UNIQUE 안 걸음.

### 4.3 todo_schedule_actuals (신규 브리지 — immutable snapshot identity)

```sql
CREATE TABLE IF NOT EXISTS todo_schedule_actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    -- task identity snapshot (immutable, no FK to tasks)
    source_task_id INTEGER,                    -- 참고용. FK 없음 — work-digest 재생성에도 안정
    source_date TEXT NOT NULL,                 -- task 확정 시점의 task.date
    source_repo TEXT,                          -- task 확정 시점의 task.repo
    source_summary TEXT NOT NULL,              -- task 확정 시점의 task.summary
    duration_min_snapshot INTEGER NOT NULL,    -- 확정 시점 duration. wrapper가 task에서 자동 읽어 저장
    confirmed_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (schedule_id) REFERENCES todo_schedules(id) ON DELETE CASCADE,
    CHECK (duration_min_snapshot > 0),

    -- 같은 schedule + 같은 source(date, summary, repo) 중복 매핑 차단
    UNIQUE (schedule_id, source_date, source_summary, source_repo)
);
CREATE INDEX IF NOT EXISTS idx_schedule_actuals_schedule ON todo_schedule_actuals(schedule_id);
```

**Codex v4 BLOCK 해소**:
- `tasks`에 FK 없음 — work-digest의 `upsert_tasks` "하루치 전체 교체"가 actual mapping을 삭제하지 않음 (silent data loss 차단)
- `source_*` 4개 컬럼이 immutable snapshot identity 역할 — task 재생성과 무관하게 actual은 사용자가 확정한 시점의 값으로 freeze
- `source_task_id`는 NULL 허용 + FK 없음. 단순 참고용
- UNIQUE 키는 `(schedule_id, source_date, source_summary, source_repo)` — 같은 schedule에 같은 task 중복 매핑 차단
- **NULL repo 동작**: SQLite UNIQUE는 NULL을 distinct로 취급. `source_repo=NULL`인 행끼리는 UNIQUE 충돌 안 함 — 의도된 동작 (work-digest 외부 활동, repo 미부여 task가 같은 summary여도 독립 snapshot). 추가 dedup이 필요하면 wrapper 단(`schedule_actual_link.py`)에서 pre-check로 처리.
- schedule 삭제 시에는 actual도 같이 삭제 (`schedule_id` ON DELETE CASCADE — 정상 흐름)
- wrapper가 `duration_min_snapshot`, `source_date`, `source_summary`, `source_repo`를 모두 task table에서 직접 조회 후 snapshot (에이전트 입력 X)

### 4.4 todos (변경 없음)

`estimated_min` 그대로. 입력 정책은 §8.

## 5. 캐파 reconciliation (분리 4종)

`daily_checkins.available_min` 단일 소스. 4가지 분리 보고:

| 키 | 의미 |
|---|---|
| `planned_overbook` | `sum(planned_min) > available_min` (계획 단계) |
| `actual_overrun` | `sum(actual via 브리지) > available_min` (실제 단계) |
| `time_conflicts` | 같은 날 schedule 시간대 겹침 list |
| `missing_budget` | `available_min` NULL이면서 schedule 존재. status로 의도 구분 — `available_status='unknown'`이면 진짜 missing, `'skipped'`면 의도적 (보고만) |

```python
def get_capacity_status(conn, date: str) -> dict:
    """
    Returns:
        {
            "available_min": int | None,
            "available_status": str,  # 'answered' / 'skipped' / 'unknown'
            "planned_min_total": int,
            "actual_min_total": int,
            "planned_overbook": bool,
            "actual_overrun": bool,
            "time_conflicts": [{"a_id": int, "b_id": int, "overlap_min": int}, ...],
            "missing_budget": bool,
            "schedules": [...]
        }
    """
```

**Codex v3 #6 반영 (write wrapper에 capacity_status 포함)**: `schedule_upsert.py`와 `schedule_actual_link.py` 응답에 `capacity_status` 항상 포함 (저장 직후 충돌 가시화).

## 6. 슬래시 커맨드

| 커맨드 | 역할 | 빈도 |
|---|---|---|
| `/morning` | 우선순위 + 캐파 인터뷰 + WIP/슬롯 | 매일 1회 |
| `/evening` | 계획 vs 실제 + actual 매칭 + reflection | 매일 1회 |
| `/capacity` | 캐파 누적 조회 + 4종 flag | 온디맨드 |

## 7. 데이터 플로우

### 7.1 `/morning`

1. 에이전트가 `todo_morning.py --date <오늘>` → 우선순위 JSON
2. 사용자에게 우선순위 제시 + 캐파 인터뷰 (§9)
3. **`checkin_save.py morning` subcommand** — phase별 required field matrix:
   ```bash
   # 정상
   checkin_save.py morning --date 2026-04-28 \
     --available-hours 5 --energy mid --blockers "두통" \
     --morning-intent "..." --wip-ids 13,20

   # 또는 skip
   checkin_save.py morning --date 2026-04-28 \
     --skip-available --skip-energy --skip-blockers \
     --morning-intent "..."
   ```
   - morning subcommand는 available/energy/blockers 각각 `--value` 또는 `--skip-*` 둘 중 하나 필수
   - wrapper가 status 컬럼 자동 설정 ('answered' / 'skipped')
4. WIP 슬롯 잡기:
   ```bash
   schedule_upsert.py --todo-id 35 --date 2026-04-28 --planned-min 120
   schedule_upsert.py --todo-id 13 --date 2026-04-28 --start 14:00 --end 16:00
   ```
   - wrapper가 시간 슬롯이면 `planned_min = end - start` 자동 계산
   - partial UNIQUE index가 같은 시간 슬롯 중복 차단 (idempotency)
   - 응답에 `capacity_status` 포함 (§5)
5. 에이전트가 `capacity.py --date <오늘>` 호출 → 4종 flag 보고

### 7.2 `/evening`

1. 에이전트가 `todo_evening.py --date <오늘>` → 계획 vs 실제 + loose match
2. 매칭된 task 후보 제시:
   - "13에 task #1234가 매칭. schedule (id=42) 14:00-16:00에 연결할래?"
3. 사용자 confirm 시 wrapper:
   ```bash
   schedule_actual_link.py \
     --schedule-id 42 --task-id 1234 \
     --date 2026-04-28 --todo-id 13
   ```
   - **wrapper가 task table에서 `task.date`, `task.duration_min`, `task.summary`, `task.repo` 모두 조회** → 4개 컬럼 모두 `source_*`로 snapshot 저장
   - 에이전트는 `--duration-min`/`--summary`/`--repo` 등 안 넘김 (snapshot 위조 차단)
   - schedule identity 재검증 (date == 2026-04-28, todo_id == 13)
   - `UNIQUE (schedule_id, source_date, source_summary, source_repo)`로 중복 매칭 차단
   - `--task-id`는 wrapper 호출 시점의 task 식별. 저장은 `source_task_id` (참고용, FK 없음)
4. matching 거부/스킵이면 새 schedule + 매칭 동시 생성 가능
5. **`checkin_save.py evening` subcommand**:
   ```bash
   checkin_save.py evening --date 2026-04-28 \
     --evening-reflection "..."
   ```
   - evening subcommand는 reflection 외 캐파 인자 안 받음
   - morning에서 이미 저장된 캐파 status는 변경 안 함

### 7.3 `/capacity`

```bash
capacity.py --start 2026-04-22 --end 2026-04-28
```

- `get_daily_checkins(start, end)` + 각 날짜 `get_capacity_status(date)`
- markdown 표 (status 표시):
  ```
  | 날짜 | 가용 | 계획 | 실측 | 잔여 | 에너지 | 블로커 | 상태 |
  |------|------|------|------|------|--------|--------|------|
  | 04-25 | 6h | 4h | 3.5h | 2h | mid | 없음 | OK |
  | 04-26 | 4h | 5h | 6h | -1h | low | 두통 | ⚠ planned_overbook, actual_overrun |
  | 04-27 | (skipped) | 3h | 2h | - | mid | - | ℹ skipped |
  | 04-28 | (no answer) | 2h | 0h | - | (skipped) | - | ⚠ missing_budget |
  | 04-29 | 5h | 4h | 4h | 1h | high | - | ⚠ time_conflicts: 14:00-16:00 / 15:30-17:00 |
  ```
- 인자 없으면 기본 최근 7일

## 8. estimated_min 입력 정책 (1-B + 1-C)

- **추가 시 (1-B)**: 에이전트가 추정 제안. `todo_crud.py add` 호출 시 `--estimated-min N` 또는 `--skip-estimated` 둘 중 하나 필수
- **WIP 전환 시 (1-C)**: `todo_crud.py move --status wip` 시 `estimated_min` NULL이면 거부 → 재질문 → `--estimated-min N` 또는 `--skip-estimated` 명시
- 명시 스킵하면 NULL 유지 (silent NULL 아님)

## 9. 인터뷰 가이드라인 (SKILL.md)

### 9.1 추출 룰

- **가용시간**: 숫자 명시 → `--available-hours N`. 모호 → 명확해질 때까지 재질문. 사용자가 "스킵"이라 명시 시에만 `--skip-available`
- **에너지**: 키워드 매핑. 매핑 안 되면 명확해질 때까지 재질문
- **블로커**: 자유 텍스트
- **actual schedule**: loose match 후보 제시 → 사용자가 schedule 명시 선택 → wrapper가 identity 자동 검증

### 9.2 스킵 처리

- 사용자 "스킵"/"넘겨" 명시 → wrapper에 `--skip-*` 인자 전달 → DB status='skipped' 기록
- 그 외엔 답할 때까지 인터뷰
- 추출 실패 시 wrapper가 인자 미달로 거부 → 재질문 (silent NULL/unknown 차단)

## 10. 에러 처리

- CHECK/FK 위반 → wrapper 에러 → 재질문
- `--value` 또는 `--skip-*` 둘 다 누락 → exit 1 (silent NULL 차단)
- **partial UNIQUE 위반** (시간 슬롯 idempotency) → wrapper 거부, 기존 schedule_id 안내 (update면 `--schedule-id` 사용 안내)
- schedule_id identity 불일치 → wrapper 거부
- `task_id` 중복 매핑 (UNIQUE) → wrapper 거부
- task date vs schedule date 불일치 → wrapper 거부
- planned_overbook / actual_overrun / time_conflicts → 보고만 (write 응답 + `/capacity`)
- estimated_min 인자 누락 (add/WIP 전환) → wrapper 거부 → 재질문

## 11. 테스트

- `tests/test_todos.py` 확장:
  - `daily_checkins` 6개 새 컬럼 + CHECK
  - `todo_schedules` CRUD + CHECK 5개 + partial UNIQUE
  - `todo_schedule_actuals` snapshot identity (source_date/summary/repo) + UNIQUE 4-tuple + schedule CASCADE + tasks FK 없음 (work-digest 재실행 후 actual 보존 회귀 테스트)
  - `get_capacity_status` 4종 flag
  - `get_daily_checkins(start, end)`
- script wrapper 테스트 (subprocess):
  - `checkin_save.py morning` — value/skip 인자 강제, 둘 다 누락 시 exit 1, status 자동 설정
  - `checkin_save.py evening` — reflection만 받음, morning 데이터 영향 없음 검증
  - `schedule_upsert.py` — planned_min 자동 계산, 시간 페어 위반 거부, partial UNIQUE 위반 거부, 응답에 capacity_status 포함
  - `schedule_actual_link.py` — task에서 date/duration/summary/repo 자동 조회, identity 재검증, UNIQUE 위반 거부, date 불일치 거부, **work-digest 재실행 후 actual 매핑 보존 회귀**
  - `capacity.py` — 4종 flag 출력, status 표시
- **silent fail 회귀 테스트** (v2 + v3):
  - 시간만 있는 schedule이 0분으로 누락되는지 (기대: 안 누락 — planned_min NOT NULL)
  - stale schedule_id로 다른 todo update 가능한지 (기대: 거부)
  - missing arg로 silent NULL 저장되는지 (기대: 거부)
  - `available_status` 없이 NULL 저장 가능한지 (기대: default='unknown')
  - 같은 시간 슬롯 두 번 저장 시 두 배 되는지 (기대: 거부)
  - task_id 중복 매핑 가능한지 (기대: 거부)
  - 에이전트가 위조한 duration_min 저장되는지 (기대: 못 함 — wrapper가 task에서 읽음)
- 인터뷰 가이드라인은 매뉴얼 검증

## 12. 변경 파일

### 신규 (7개)
| 파일 | 내용 |
|------|------|
| `plugins/life-management/commands/morning.md` | `/morning` 진입점 |
| `plugins/life-management/commands/evening.md` | `/evening` 진입점 |
| `plugins/life-management/commands/capacity.md` | `/capacity` 진입점 |
| `plugins/life-management/skills/life-coach/scripts/checkin_save.py` | morning/evening subcommand. value/skip tri-state |
| `plugins/life-management/skills/life-coach/scripts/schedule_upsert.py` | wrapper. planned_min 자동 계산 + partial UNIQUE 검증 + capacity_status 응답 |
| `plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py` | actual 브리지 wrapper. task 자동 조회 + identity 검증 + UNIQUE 검증 |
| `plugins/life-management/skills/life-coach/scripts/capacity.py` | 누적 조회 + 4종 flag |

### 변경 (5개)
| 파일 | 변경 |
|------|------|
| `mcp/life-dashboard/schema.sql` | daily_checkins +6 컬럼 (CHECK), todo_schedules CREATE (CHECK 5개 + partial UNIQUE), todo_schedule_actuals CREATE (snapshot identity, schedule CASCADE만, tasks FK 없음) |
| `mcp/life-dashboard/db.py` | 마이그레이션 ALTER, `upsert_daily_checkin` 시그니처 확장 (status 인자), `upsert_schedule` / `link_schedule_actual` / `get_schedule` / `get_schedules_by_date` / `get_daily_checkins(start, end)` / `get_capacity_status(date)` 추가 |
| `mcp/life-dashboard/tests/test_todos.py` | 위 함수 + wrapper + silent fail 회귀 |
| `plugins/life-management/skills/life-coach/scripts/todo_crud.py` | estimated_min value/skip tri-state |
| `plugins/life-management/skills/life-coach/SKILL.md` | 슬래시 커맨드, 워크플로우 (wrapper 경유 강조), 인터뷰 가이드, 단일 소스 룰, status 영속화 룰 |

**합계 12개 파일** (신규 7 + 변경 5)

## 13. 단계별 commit 전략

1. **schema** — 3 테이블 변경/생성 (status 컬럼 + partial UNIQUE 포함) + 마이그레이션
2. **db functions** — 함수 + 단위 테스트
3. **wrapper scripts** — 4 wrapper + subcommand + 인자 강제 + idempotency + identity 재검증 + silent fail 회귀
4. **estimated_min policy** — `todo_crud.py` + 테스트
5. **slash commands** — commands/ 3개
6. **SKILL.md** — 워크플로우 + 인터뷰 + status 룰

## 14. Out of scope

- 캘린더 양방향 동기 — **#38**
- 누적 시각화 + 방향 전환 추적 — **#36**
- 추천 엔진 — **#37**
- todos `blocked_by` — 별도

## 15. Codex review 대응 v5

| Codex finding | v5 반영 |
|---|---|
| **v3 #1 status 영속화** | `daily_checkins` 3 status 컬럼 (§4.1) — v4 effective 유지 |
| **v3 #2 checkin subcommand 분리** | morning/evening subcommand (§7.1, §7.2) — v4 effective 유지 |
| **v3 #3 actual identity** | wrapper가 task에서 date/duration/summary/repo 직접 조회 (§7.2) — v4 partial → v5 effective |
| **v3 #4 schedule_upsert idempotency** | partial UNIQUE index (§4.2) — v4 effective 유지 |
| **v3 #5 wrapper 우회 시스템 불변식** | spec 선언 + 회귀 테스트 (§11). DB layer 추가 강제는 향후 phase |
| **v3 #6 write 응답에 capacity_status** | wrapper 응답에 포함 (§5, §7) — v4 effective 유지 |
| **v4 BLOCK: work-digest task 전체 교체 → actual silent data loss** | `todo_schedule_actuals`를 immutable snapshot identity로 변경. tasks FK 제거. source_date/summary/repo/task_id snapshot 컬럼 추가. UNIQUE 4-tuple. tasks 재생성 무관 (§4.3) |

### 최종 verdict 표 (v5)

| v2 finding | v5 verdict |
|---|---|
| #1 planned_min NULL → 0분 누락 | ✅ effective (NOT NULL + wrapper 자동 계산 + partial UNIQUE) |
| #2 schedule_id confirmation | ✅ effective (identity 재검증 + UNIQUE 4-tuple) |
| #3 wrapper 경유 강제 | partial (spec + 회귀 테스트. DB layer 강제는 향후) |
| #4 tri-state | ✅ effective (status 영속화) |
| #6 actual stale | ✅ effective (immutable snapshot, tasks FK 없음) |
| #7 reconcile 4종 | ✅ effective (write 응답 포함) |

#3 외에는 모두 effective. #3은 spec layer 한계라 향후 phase에서 DB API 자체에 tri-state 타입 도입으로 강화.
