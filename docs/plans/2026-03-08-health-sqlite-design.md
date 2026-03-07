# Health Skills SQLite Integration Design

## Summary

health 계열 스킬 3개의 데이터 저장소를 Obsidian vault에서 life-dashboard-mcp SQLite로 통합.
health-coach는 life-coach에 흡수하여 3개 스킬 체제로 전환.

## Design Decisions

| 결정 | 선택 | 이유 |
|------|------|------|
| 스키마 구조 | 도메인별 분리 테이블 (5개) | finance 테이블과 동일 패턴 |
| DB 함수 위치 | db.py에 직접 추가 | 현재 129줄, 추가 후 ~230줄로 분리 불필요 |
| cron 스크립트 | SQLite로 전환 | meals_io.py 삭제 시 같이 전환 필수 |
| health-coach | life-coach에 흡수 | "기록 스킬 + 코칭 스킬" 역할 분리 |
| health-tracker + meal-tracker | 별도 유지 | 도메인이 다르고 스킬 크기 적절 |

## Final Structure

```
변경 전 (4개 스킬):
  health-tracker  -> Obsidian vault (운동/증상/PT)
  health-coach    -> Obsidian vault (분석/코칭)
  meal-tracker    -> Obsidian vault (식사/영양)
  life-coach      -> SQLite (CC 세션 코칭)

변경 후 (3개 스킬):
  health-tracker  -> SQLite (운동/증상/PT)
  meal-tracker    -> SQLite (식사/영양)
  life-coach      -> SQLite (CC + 건강 + 식사 통합 코칭)
  health-coach    -> 삭제
```

## Schema - 5 Tables

```sql
CREATE TABLE IF NOT EXISTS health_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,              -- PT/수영/걷기/기타
    duration_min INTEGER NOT NULL,
    exercises TEXT,                   -- JSON array
    feeling TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(date, timestamp, type)
);

CREATE TABLE IF NOT EXISTS health_symptoms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,              -- 허리디스크/메니에르병/기타
    severity TEXT NOT NULL,          -- 경증/중등도/심각
    description TEXT NOT NULL,
    trigger TEXT,
    duration TEXT,
    status TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(date, timestamp, type)
);

CREATE TABLE IF NOT EXISTS health_pt_homework (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise TEXT NOT NULL,
    sets INTEGER,
    reps TEXT,
    notes TEXT,
    status TEXT DEFAULT '할 일',
    assigned_date TEXT NOT NULL,
    completed_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(exercise, assigned_date)
);

CREATE TABLE IF NOT EXISTS health_check_ins (
    date TEXT PRIMARY KEY,
    sleep_hours REAL,
    sleep_quality TEXT,
    steps INTEGER,
    workout INTEGER DEFAULT 0,
    stress INTEGER,
    water_ml INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS health_meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    meal_type TEXT NOT NULL,          -- 아침/점심/저녁/간식
    food_items TEXT,                  -- JSON array
    portion TEXT,
    skipped INTEGER DEFAULT 0,
    calories INTEGER,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(date, timestamp, meal_type)
);

CREATE INDEX IF NOT EXISTS idx_exercises_date ON health_exercises(date);
CREATE INDEX IF NOT EXISTS idx_symptoms_date ON health_symptoms(date);
CREATE INDEX IF NOT EXISTS idx_meals_date ON health_meals(date);
```

## db.py Extensions

```
insert_exercise(conn, data)
insert_symptom(conn, data)
insert_pt_homework(conn, data)
update_pt_homework(conn, id, updates)
upsert_check_in(conn, data)
insert_meal(conn, data)

query_exercises(conn, date_from, date_to, type=None)
query_symptoms(conn, date_from, date_to, type=None)
query_pt_homework(conn, status=None)
query_check_ins(conn, date_from, date_to)
query_meals(conn, date_from, date_to, meal_type=None)
```

## Script Changes

### health-tracker/scripts/
| File | Change |
|------|--------|
| health_io.py | DELETE |
| log_exercise.py | `from db import insert_exercise` |
| log_symptom.py | `from db import insert_symptom` |
| log_pt_homework.py | `from db import insert_pt_homework, update_pt_homework, query_pt_homework` |
| check_pt_attendance.py | `from db import query_exercises` |
| daily_reminder.py | `from db import query_pt_homework, query_exercises` |
| health_tracker.py | No change (subprocess wrapper) |

### meal-tracker/scripts/
| File | Change |
|------|--------|
| meals_io.py | DELETE |
| log_meal.py | `from db import insert_meal` |
| daily_summary.py | `from db import query_meals` (Telegram preserved) |
| meal_reminder.py | No change (Telegram only, no DB) |

### health-coach -> life-coach merge
| health-coach file | Destination |
|-------------------|-------------|
| coach.py subcommands | life-coach/scripts/health_cmds.py (new) |
| track_health.py | life-coach/scripts/track_health.py |
| analyze_health.py | health_cmds.py |
| weekly_report.py | life-coach/scripts/weekly_coach.py (health section) |
| daily_routine.py | life-coach/scripts/daily_routine.py |
| config/exercises.json | life-coach/references/exercises.json |
| health-coach skill | DELETE entirely |

### life-coach/scripts/daily_coach.py extension
- Add health section: query_exercises, query_meals, query_check_ins, query_symptoms
- Report includes: exercise status, meal summary, symptom alerts, check-in summary

### SKILL.md updates
- health-tracker: storage Obsidian -> SQLite
- meal-tracker: storage Obsidian -> SQLite
- life-coach: document merged health-coach capabilities

## Out of Scope
- Obsidian -> SQLite data migration (separate task)
- MCP server.py health resource exposure (follow-up if needed)
