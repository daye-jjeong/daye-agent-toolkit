# Health Skills SQLite Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** health 계열 스킬 3개의 I/O를 Obsidian vault에서 life-dashboard-mcp SQLite로 전환하고, health-coach를 life-coach에 흡수하여 3개 스킬 체제로 통합.

**Architecture:** 5개 health 테이블을 schema.sql에 추가하고, db.py에 CRUD 함수를 추가. 각 스킬 스크립트가 health_io.py/meals_io.py 대신 db.py를 import. health-coach의 코칭/분석 기능은 life-coach로 이동.

**Tech Stack:** Python 3 (stdlib only), SQLite3, life-dashboard-mcp의 db.py 패턴

---

### Task 1: schema.sql에 health 테이블 추가

**Files:**
- Modify: `shared/life-dashboard-mcp/schema.sql:132` (파일 끝에 추가)

**Step 1: schema.sql 끝에 health 테이블 5개 + 인덱스 추가**

```sql
-- ── Health ──────────────────────────────────

CREATE TABLE IF NOT EXISTS health_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    exercises TEXT,
    feeling TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, timestamp, type)
);

CREATE TABLE IF NOT EXISTS health_symptoms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT NOT NULL,
    trigger_factor TEXT,
    duration TEXT,
    status TEXT DEFAULT '진행중',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, timestamp, type)
);

CREATE TABLE IF NOT EXISTS health_pt_homework (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise TEXT NOT NULL,
    sets_reps TEXT,
    notes TEXT,
    status TEXT DEFAULT '할 일',
    assigned_date TEXT NOT NULL,
    completed_date TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(exercise, assigned_date)
);

CREATE TABLE IF NOT EXISTS health_check_ins (
    date TEXT PRIMARY KEY,
    sleep_hours REAL,
    sleep_quality INTEGER,
    steps INTEGER,
    workout INTEGER DEFAULT 0,
    stress INTEGER,
    water_ml INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS health_meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    food_items TEXT,
    portion TEXT,
    skipped INTEGER DEFAULT 0,
    calories INTEGER,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, timestamp, meal_type)
);

CREATE INDEX IF NOT EXISTS idx_health_exercises_date ON health_exercises(date);
CREATE INDEX IF NOT EXISTS idx_health_symptoms_date ON health_symptoms(date);
CREATE INDEX IF NOT EXISTS idx_health_meals_date ON health_meals(date);
```

**주의:** `trigger`는 SQLite 예약어이므로 컬럼명을 `trigger_factor`로 변경. 스크립트의 `--trigger` CLI 인자는 유지하되 DB 저장 시 `trigger_factor` 키 사용.

**Step 2: 검증**

Run: `python3 -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.executescript(open('shared/life-dashboard-mcp/schema.sql').read()); print([r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])"`

Expected: 기존 테이블 + health_exercises, health_symptoms, health_pt_homework, health_check_ins, health_meals

**Step 3: Commit**

```bash
git add shared/life-dashboard-mcp/schema.sql
git commit -m "feat: add health tables to life-dashboard schema"
```

---

### Task 2: db.py에 health CRUD 함수 추가

**Files:**
- Modify: `shared/life-dashboard-mcp/db.py:129` (파일 끝에 추가)

**Step 1: db.py 끝에 health 함수 추가**

```python
# ── Health ──────────────────────────────────


def insert_exercise(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO health_exercises (date, timestamp, type, duration_min, exercises, feeling, notes)
        VALUES (:date, :timestamp, :type, :duration_min, :exercises, :feeling, :notes)
        ON CONFLICT(date, timestamp, type) DO UPDATE SET
            duration_min=excluded.duration_min, exercises=excluded.exercises,
            feeling=excluded.feeling, notes=excluded.notes
    """, data)


def insert_symptom(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO health_symptoms (date, timestamp, type, severity, description, trigger_factor, duration, status)
        VALUES (:date, :timestamp, :type, :severity, :description, :trigger_factor, :duration, :status)
        ON CONFLICT(date, timestamp, type) DO UPDATE SET
            severity=excluded.severity, description=excluded.description,
            trigger_factor=excluded.trigger_factor, duration=excluded.duration, status=excluded.status
    """, data)


def insert_pt_homework(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO health_pt_homework (exercise, sets_reps, notes, status, assigned_date)
        VALUES (:exercise, :sets_reps, :notes, :status, :assigned_date)
        ON CONFLICT(exercise, assigned_date) DO UPDATE SET
            sets_reps=excluded.sets_reps, notes=excluded.notes, status=excluded.status
    """, data)


def update_pt_homework(conn: sqlite3.Connection, hw_id: int, updates: dict):
    sets = ", ".join(f"{k}=:{k}" for k in updates)
    updates["id"] = hw_id
    conn.execute(f"UPDATE health_pt_homework SET {sets} WHERE id = :id", updates)


def query_pt_homework(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    if status:
        rows = conn.execute(
            "SELECT * FROM health_pt_homework WHERE status = ? ORDER BY assigned_date DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM health_pt_homework ORDER BY assigned_date DESC").fetchall()
    return [dict(r) for r in rows]


def upsert_check_in(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO health_check_ins (date, sleep_hours, sleep_quality, steps, workout, stress, water_ml, notes)
        VALUES (:date, :sleep_hours, :sleep_quality, :steps, :workout, :stress, :water_ml, :notes)
        ON CONFLICT(date) DO UPDATE SET
            sleep_hours=excluded.sleep_hours, sleep_quality=excluded.sleep_quality,
            steps=excluded.steps, workout=excluded.workout, stress=excluded.stress,
            water_ml=excluded.water_ml, notes=excluded.notes
    """, data)


def insert_meal(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO health_meals (date, timestamp, meal_type, food_items, portion, skipped, calories, protein_g, carbs_g, fat_g, notes)
        VALUES (:date, :timestamp, :meal_type, :food_items, :portion, :skipped, :calories, :protein_g, :carbs_g, :fat_g, :notes)
        ON CONFLICT(date, timestamp, meal_type) DO UPDATE SET
            food_items=excluded.food_items, portion=excluded.portion, skipped=excluded.skipped,
            calories=excluded.calories, protein_g=excluded.protein_g, carbs_g=excluded.carbs_g,
            fat_g=excluded.fat_g, notes=excluded.notes
    """, data)


def query_exercises(conn: sqlite3.Connection, date_from: str, date_to: str, ex_type: str | None = None) -> list[dict]:
    if ex_type:
        rows = conn.execute(
            "SELECT * FROM health_exercises WHERE date >= ? AND date <= ? AND type = ? ORDER BY date, timestamp",
            (date_from, date_to, ex_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM health_exercises WHERE date >= ? AND date <= ? ORDER BY date, timestamp",
            (date_from, date_to),
        ).fetchall()
    return [dict(r) for r in rows]


def query_symptoms(conn: sqlite3.Connection, date_from: str, date_to: str, sym_type: str | None = None) -> list[dict]:
    if sym_type:
        rows = conn.execute(
            "SELECT * FROM health_symptoms WHERE date >= ? AND date <= ? AND type = ? ORDER BY date, timestamp",
            (date_from, date_to, sym_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM health_symptoms WHERE date >= ? AND date <= ? ORDER BY date, timestamp",
            (date_from, date_to),
        ).fetchall()
    return [dict(r) for r in rows]


def query_check_ins(conn: sqlite3.Connection, date_from: str, date_to: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM health_check_ins WHERE date >= ? AND date <= ? ORDER BY date",
        (date_from, date_to),
    ).fetchall()
    return [dict(r) for r in rows]


def query_meals(conn: sqlite3.Connection, date_from: str, date_to: str, meal_type: str | None = None) -> list[dict]:
    if meal_type:
        rows = conn.execute(
            "SELECT * FROM health_meals WHERE date >= ? AND date <= ? AND meal_type = ? ORDER BY date, timestamp",
            (date_from, date_to, meal_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM health_meals WHERE date >= ? AND date <= ? ORDER BY date, timestamp",
            (date_from, date_to),
        ).fetchall()
    return [dict(r) for r in rows]
```

**Step 2: import 검증**

Run: `cd shared/life-dashboard-mcp && python3 -c "from db import insert_exercise, insert_symptom, insert_pt_homework, update_pt_homework, query_pt_homework, upsert_check_in, insert_meal, query_exercises, query_symptoms, query_check_ins, query_meals; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add shared/life-dashboard-mcp/db.py
git commit -m "feat: add health CRUD functions to db.py"
```

---

### Task 3: health-tracker 스크립트 SQLite 전환

**Files:**
- Modify: `shared/health-tracker/scripts/log_exercise.py` (전체 재작성)
- Modify: `shared/health-tracker/scripts/log_symptom.py` (전체 재작성)
- Modify: `shared/health-tracker/scripts/log_pt_homework.py` (전체 재작성)
- Modify: `shared/health-tracker/scripts/check_pt_attendance.py` (전체 재작성)
- Modify: `shared/health-tracker/scripts/daily_reminder.py` (전체 재작성)
- No change: `shared/health-tracker/scripts/health_tracker.py` (subprocess wrapper)

공통 패턴: `health_io` import를 `db` import로 교체. sys.path를 `life-dashboard-mcp`로 설정.

**Step 1: log_exercise.py 재작성**

```python
#!/usr/bin/env python3
"""운동 기록 스크립트 — SQLite 저장."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, insert_exercise


def log_exercise(exercise_type, duration, exercises="", notes="", feeling=""):
    date = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H:%M")

    data = {
        "date": date,
        "timestamp": timestamp,
        "type": exercise_type,
        "duration_min": int(duration),
        "exercises": exercises or None,
        "feeling": feeling or None,
        "notes": notes or None,
    }

    conn = get_conn()
    try:
        insert_exercise(conn, data)
        conn.commit()
    finally:
        conn.close()

    print(f"[OK] 운동 기록 완료: {exercise_type} ({duration}분)")


def main():
    parser = argparse.ArgumentParser(description="운동 기록")
    parser.add_argument("--type", required=True,
                        choices=["PT", "수영", "걷기", "기타"],
                        help="운동 종류")
    parser.add_argument("--duration", required=True, type=int,
                        help="운동 시간 (분)")
    parser.add_argument("--exercises", default="",
                        help="운동 상세 (예: 플랭크 3세트, 데드버그 10회)")
    parser.add_argument("--notes", default="", help="메모")
    parser.add_argument("--feeling", default="",
                        choices=["", "좋았음", "보통", "힘들었음", "고통스러움"],
                        help="운동 후 느낌")
    args = parser.parse_args()
    log_exercise(args.type, args.duration, args.exercises, args.notes, args.feeling)


if __name__ == "__main__":
    main()
```

**Step 2: log_symptom.py 재작성**

```python
#!/usr/bin/env python3
"""증상 기록 스크립트 — SQLite 저장."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, insert_symptom


def log_symptom(symptom_type, severity, description, trigger="", duration="", status="진행중"):
    date = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H:%M")

    data = {
        "date": date,
        "timestamp": timestamp,
        "type": symptom_type,
        "severity": severity,
        "description": description,
        "trigger_factor": trigger or None,
        "duration": duration or None,
        "status": status,
    }

    conn = get_conn()
    try:
        insert_symptom(conn, data)
        conn.commit()
    finally:
        conn.close()

    print(f"[OK] 증상 기록 완료: {symptom_type} ({severity})")


def main():
    parser = argparse.ArgumentParser(description="건강 증상 기록")
    parser.add_argument("--type", required=True,
                        choices=["허리디스크", "메니에르병", "기타"],
                        help="증상 종류")
    parser.add_argument("--severity", required=True,
                        choices=["경증", "중등도", "심각"],
                        help="심각도")
    parser.add_argument("--description", required=True, help="증상 상세 설명")
    parser.add_argument("--trigger", default="", help="트리거 요인 (선택)")
    parser.add_argument("--duration", default="", help="지속 시간 (선택)")
    parser.add_argument("--status", default="진행중",
                        choices=["진행중", "완화", "완료"],
                        help="상태 (기본: 진행중)")
    args = parser.parse_args()
    log_symptom(args.type, args.severity, args.description, args.trigger, args.duration, args.status)


if __name__ == "__main__":
    main()
```

**Step 3: log_pt_homework.py 재작성**

```python
#!/usr/bin/env python3
"""PT 숙제 트래킹 — SQLite 기반."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, insert_pt_homework, update_pt_homework, query_pt_homework


def add_homework(exercise, sets_reps, notes=""):
    date = datetime.now().strftime("%Y-%m-%d")
    data = {
        "exercise": exercise,
        "sets_reps": sets_reps,
        "notes": notes or None,
        "status": "할 일",
        "assigned_date": date,
    }
    conn = get_conn()
    try:
        insert_pt_homework(conn, data)
        conn.commit()
    finally:
        conn.close()
    print(f"[OK] PT 숙제 추가: {exercise} ({sets_reps})")


def list_homework():
    conn = get_conn()
    try:
        pending = [h for h in query_pt_homework(conn) if h["status"] in ("할 일", "진행중")]
    finally:
        conn.close()
    if not pending:
        print("[OK] 완료해야 할 숙제가 없어요!")
        return
    print(f"\nPT 숙제 목록 ({len(pending)}개):\n")
    for i, h in enumerate(pending, 1):
        print(f"{i}. {h['exercise']} - {h.get('sets_reps', '')}")
        print(f"   받은 날짜: {h['assigned_date']} | 상태: {h['status']}")
        print(f"   ID: {h['id']}\n")


def complete_homework(hw_id):
    date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        update_pt_homework(conn, hw_id, {"status": "완료", "completed_date": date})
        conn.commit()
    finally:
        conn.close()
    print(f"[OK] 숙제 완료: ID {hw_id}")


def main():
    parser = argparse.ArgumentParser(description="PT 숙제 관리")
    sub = parser.add_subparsers(dest="command", help="명령")
    ap = sub.add_parser("add", help="숙제 추가")
    ap.add_argument("--exercise", required=True, help="운동 이름")
    ap.add_argument("--sets", required=True, help="세트 수")
    ap.add_argument("--reps", required=True, help="횟수 (또는 시간)")
    ap.add_argument("--notes", default="", help="주의사항")
    sub.add_parser("list", help="미완료 숙제 목록")
    cp = sub.add_parser("complete", help="숙제 완료")
    cp.add_argument("--id", required=True, type=int, help="숙제 ID")
    args = parser.parse_args()

    if args.command == "add":
        add_homework(args.exercise, f"{args.sets}세트 x {args.reps}", args.notes)
    elif args.command == "list":
        list_homework()
    elif args.command == "complete":
        complete_homework(args.id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**주의:** `complete` 서브커맨드가 `--file` 대신 `--id`로 변경됨. SKILL.md에도 반영 필요 (Task 9).

**Step 4: check_pt_attendance.py 재작성**

```python
#!/usr/bin/env python3
"""PT 출석 체크 스크립트 — SQLite 기반."""

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, query_exercises


def check_attendance(days=7):
    today = datetime.now().strftime("%Y-%m-%d")
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_conn()
    try:
        pt_entries = query_exercises(conn, since, today, ex_type="PT")
    finally:
        conn.close()

    print(f"PT 출석 체크 (최근 {days}일)\n{'='*40}\n")

    if not pt_entries:
        print(f"[!] 최근 {days}일 PT 기록 없음")
        print("    PT 주 2회 목표를 유지하세요!\n")
        return

    by_date = defaultdict(list)
    for e in pt_entries:
        by_date[e["date"]].append(e["duration_min"])

    print(f"PT 출석: {len(pt_entries)}회 ({len(by_date)}일)\n")
    for d in sorted(by_date.keys()):
        sessions = by_date[d]
        total = sum(s for s in sessions if isinstance(s, (int, float)))
        print(f"  {d}: {len(sessions)}회 ({total}분)")

    print()
    target = 2 if days <= 7 else (days // 7) * 2

    if len(pt_entries) >= target:
        print(f"[OK] 목표 달성! ({len(pt_entries)}/{target}회)")
    else:
        print(f"[!] 목표 미달 ({len(pt_entries)}/{target}회)")
        print("    PT 출석률을 높여보세요!")

    todays = [e for e in pt_entries if e["date"] == today]
    if todays:
        print(f"\n[OK] 오늘 PT 기록 있음")
    else:
        print(f"\n[i] 오늘 PT 기록 없음")


def main():
    parser = argparse.ArgumentParser(description="PT 출석 체크")
    parser.add_argument("--days", type=int, default=7, help="확인할 기간 (일, 기본: 7)")
    args = parser.parse_args()
    check_attendance(args.days)


if __name__ == "__main__":
    main()
```

**Step 5: daily_reminder.py 재작성**

```python
#!/usr/bin/env python3
"""일일 알림 스크립트 — SQLite 기반."""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, query_pt_homework, query_exercises


def homework_reminder():
    print("PT 숙제 알림\n")
    conn = get_conn()
    try:
        all_hw = query_pt_homework(conn)
    finally:
        conn.close()
    pending = [h for h in all_hw if h["status"] in ("할 일", "진행중")]

    if not pending:
        print("[OK] 미완료 숙제 없음")
        return

    print(f"미완료 숙제 {len(pending)}개:\n")
    for idx, h in enumerate(pending, 1):
        print(f"  {idx}. {h['exercise']} - {h.get('sets_reps', '')} (받은 날짜: {h['assigned_date']})")
    print()


def exercise_check():
    print("오늘 운동 체크\n")
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        todays = query_exercises(conn, today, today)
    finally:
        conn.close()

    if todays:
        print(f"[OK] 오늘 운동 {len(todays)}개 기록됨:\n")
        for e in todays:
            print(f"  - {e['type']} ({e['duration_min']}분)")
        print()
    else:
        print("[!] 오늘 운동 기록 없음")
        print("    간단한 걷기라도 하면 좋을 것 같아요!\n")


def main():
    parser = argparse.ArgumentParser(description="일일 알림")
    parser.add_argument("--type", required=True, choices=["homework", "exercise"], help="알림 종류")
    args = parser.parse_args()

    if args.type == "homework":
        homework_reminder()
    elif args.type == "exercise":
        exercise_check()


if __name__ == "__main__":
    main()
```

**Step 6: 검증**

Run: 각 스크립트 `--help` 실행
```bash
python3 shared/health-tracker/scripts/log_exercise.py --help
python3 shared/health-tracker/scripts/log_symptom.py --help
python3 shared/health-tracker/scripts/log_pt_homework.py --help
python3 shared/health-tracker/scripts/check_pt_attendance.py --help
python3 shared/health-tracker/scripts/daily_reminder.py --help
```
Expected: 모두 에러 없이 help 출력

**Step 7: health_io.py 삭제**

```bash
rm shared/health-tracker/scripts/health_io.py
```

**Step 8: Commit**

```bash
git add shared/health-tracker/scripts/
git commit -m "feat: convert health-tracker scripts to SQLite"
```

---

### Task 4: meal-tracker 스크립트 SQLite 전환

**Files:**
- Modify: `shared/meal-tracker/scripts/log_meal.py` (전체 재작성)
- Modify: `shared/meal-tracker/scripts/daily_summary.py` (전체 재작성)
- Delete: `shared/meal-tracker/scripts/meals_io.py`
- No change: `shared/meal-tracker/scripts/meal_reminder.py` (Telegram 발송만, DB 미사용)

**Step 1: log_meal.py 재작성**

```python
#!/usr/bin/env python3
"""식사 기록 스크립트 — SQLite 저장."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, insert_meal

NUTRITION_DB_PATH = Path(__file__).parent.parent / "config" / "nutrition_db.json"


def load_nutrition_db():
    with open(NUTRITION_DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def estimate_nutrition(food_items, portion):
    nutrition_db = load_nutrition_db()
    total_cal = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    portion_multiplier = {"적음": 0.7, "보통": 1.0, "많음": 1.3}
    multiplier = portion_multiplier.get(portion, 1.0)

    for item in food_items:
        item = item.strip()
        found = False
        for category, foods in nutrition_db.items():
            for food_name, nutrition in foods.items():
                if food_name in item or item in food_name:
                    total_cal += nutrition['calories'] * multiplier
                    total_protein += nutrition['protein'] * multiplier
                    total_carbs += nutrition['carbs'] * multiplier
                    total_fat += nutrition['fat'] * multiplier
                    found = True
                    break
            if found:
                break

    return {
        "calories": round(total_cal),
        "protein": round(total_protein, 1),
        "carbs": round(total_carbs, 1),
        "fat": round(total_fat, 1),
    }


def log_meal(meal_type, food_items, portion, skipped, notes):
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H:%M")

    if skipped:
        data = {
            "date": today,
            "timestamp": timestamp,
            "meal_type": meal_type,
            "food_items": None,
            "portion": None,
            "skipped": 1,
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "notes": notes or "거름",
        }
        print(f"[!] {meal_type} 거름 - {notes or '기록됨'}")
    else:
        food_list = [f.strip() for f in food_items.split(',')]
        nutrition = estimate_nutrition(food_list, portion)
        data = {
            "date": today,
            "timestamp": timestamp,
            "meal_type": meal_type,
            "food_items": json.dumps(food_list, ensure_ascii=False),
            "portion": portion,
            "skipped": 0,
            "calories": nutrition["calories"],
            "protein_g": nutrition["protein"],
            "carbs_g": nutrition["carbs"],
            "fat_g": nutrition["fat"],
            "notes": notes or None,
        }
        print(f"[OK] {meal_type} 기록됨")
        print(f"   음식: {', '.join(food_list)}")
        print(f"   양: {portion}")
        print(f"   영양소: {nutrition['calories']}kcal, "
              f"단백질 {nutrition['protein']}g, "
              f"탄수화물 {nutrition['carbs']}g, "
              f"지방 {nutrition['fat']}g")

    conn = get_conn()
    try:
        insert_meal(conn, data)
        conn.commit()
    finally:
        conn.close()

    return data


def main():
    parser = argparse.ArgumentParser(description="식사 기록")
    parser.add_argument("--type", required=True, help="아침/점심/저녁/간식")
    parser.add_argument("--food", help="음식 목록 (쉼표로 구분)")
    parser.add_argument("--portion", default="보통", help="적음/보통/많음")
    parser.add_argument("--skipped", action="store_true", help="거른 식사")
    parser.add_argument("--notes", help="메모")
    args = parser.parse_args()

    valid_types = ["아침", "점심", "저녁", "간식"]
    if args.type not in valid_types:
        print(f"[ERROR] 잘못된 식사 유형: {args.type}")
        print(f"   사용 가능: {', '.join(valid_types)}")
        sys.exit(1)

    if not args.skipped and not args.food:
        print("[ERROR] 음식을 입력하거나 --skipped 플래그를 사용하세요")
        sys.exit(1)

    log_meal(args.type, args.food or "", args.portion, args.skipped, args.notes)


if __name__ == "__main__":
    main()
```

**Step 2: daily_summary.py 재작성**

```python
#!/usr/bin/env python3
"""식사 일일 요약 — SQLite 기반, 텔레그램 전송."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, query_meals

TELEGRAM_GROUP = "-1003242721592"
TOPIC_PT = "169"


def load_today_meals():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        return query_meals(conn, today, today)
    finally:
        conn.close()


def generate_summary(meals):
    if not meals:
        return {
            "total_meals": 0, "skipped": 3,
            "total_calories": 0, "total_protein": 0,
            "total_carbs": 0, "total_fat": 0, "meals_by_type": {},
        }

    summary = {
        "total_meals": 0, "skipped": 0,
        "total_calories": 0, "total_protein": 0,
        "total_carbs": 0, "total_fat": 0, "meals_by_type": {},
    }

    for meal in meals:
        if meal.get("skipped"):
            summary["skipped"] += 1
        else:
            summary["total_meals"] += 1
            summary["total_calories"] += meal.get("calories", 0) or 0
            summary["total_protein"] += meal.get("protein_g", 0) or 0
            summary["total_carbs"] += meal.get("carbs_g", 0) or 0
            summary["total_fat"] += meal.get("fat_g", 0) or 0
        summary["meals_by_type"][meal["meal_type"]] = meal

    return summary


def generate_message(summary, meals):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"**오늘의 식사 요약** ({now})\n\n"
    message += "**식사 현황**\n"
    message += f"- 먹은 식사: {summary['total_meals']}/3\n"
    message += f"- 거른 식사: {summary['skipped']}/3\n\n"

    if meals:
        message += "**상세 기록**\n"
        for meal in meals:
            mt = meal.get("meal_type", "")
            if meal.get("skipped"):
                message += f"- {mt}: 거름"
                if meal.get("notes"):
                    message += f" ({meal['notes']})"
                message += "\n"
            else:
                food = meal.get("food_items", "")
                portion = meal.get("portion", "")
                message += f"- {mt}: {food} ({portion})\n"
        message += "\n"

    if summary['total_meals'] > 0:
        message += "**영양소 합계**\n"
        message += f"- 칼로리: {summary['total_calories']}kcal\n"
        message += f"- 단백질: {summary['total_protein']:.1f}g\n"
        message += f"- 탄수화물: {summary['total_carbs']:.1f}g\n"
        message += f"- 지방: {summary['total_fat']:.1f}g\n\n"

    message += "**Health Coach 조언**\n"
    if summary['skipped'] == 0:
        message += "오늘 세 끼 다 챙겨 먹었네! 훌륭해!\n"
    elif summary['skipped'] == 1:
        message += "한 끼 거른 것 같아. 내일은 세 끼 다 챙기자!\n"
    elif summary['skipped'] == 2:
        message += "두 끼나 거렀네... 마운자로 부작용 심한가? 내일은 꼭 챙겨 먹자!\n"
    else:
        message += "오늘 거의 안 먹었어! 입맛 없어도 프로틴쉐이크라도 마시자. 건강 중요해!\n"

    if summary['total_meals'] > 0:
        if summary['total_protein'] < 60:
            message += "단백질이 부족해! (목표: 60g 이상)\n"
        else:
            message += f"단백질 충분! ({summary['total_protein']:.1f}g)\n"

    message += "\n내일도 잘 챙겨 먹자!"
    return message


def send_summary():
    meals = load_today_meals()
    summary = generate_summary(meals)
    message = generate_message(summary, meals)

    cmd = [
        "clawdbot", "message", "send",
        "-t", TELEGRAM_GROUP,
        "--thread-id", TOPIC_PT,
        "-m", message,
    ]

    try:
        subprocess.run(cmd, check=True)
        print("[OK] Daily summary sent!")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to send summary: {e}")
        return False
    return True


if __name__ == "__main__":
    send_summary()
```

**Step 3: meals_io.py 삭제**

```bash
rm shared/meal-tracker/scripts/meals_io.py
```

**Step 4: 검증**

```bash
python3 shared/meal-tracker/scripts/log_meal.py --help
python3 shared/meal-tracker/scripts/daily_summary.py --help 2>/dev/null || echo "no --help (direct run)"
```
Expected: log_meal.py help 출력, daily_summary.py import 에러 없음

**Step 5: Commit**

```bash
git add shared/meal-tracker/scripts/
git commit -m "feat: convert meal-tracker scripts to SQLite"
```

---

### Task 5: health-coach를 life-coach로 흡수

**Files:**
- Create: `shared/life-coach/scripts/health_cmds.py` (coach.py 서브커맨드 이동)
- Create: `shared/life-coach/scripts/track_health.py` (체크인 기록)
- Create: `shared/life-coach/scripts/daily_routine.py` (일일 루틴)
- Move: `shared/health-coach/config/exercises.json` → `shared/life-coach/references/exercises.json`
- Move: `shared/health-coach/config/routines.json` → `shared/life-coach/references/routines.json`

**Step 1: health_cmds.py 생성**

health-coach/scripts/coach.py의 HealthCoach 클래스를 SQLite 기반으로 재작성.
exercises.json 경로를 `references/`로 변경.

```python
#!/usr/bin/env python3
"""Health commands — exercise routines, symptom analysis, guides, lifestyle advice, checkup.

Migrated from health-coach/scripts/coach.py. Data source: SQLite.
"""

import json
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import (get_conn, query_exercises, query_symptoms,
                query_check_ins, query_meals)

_REFS_DIR = Path(__file__).resolve().parent.parent / "references"


class HealthCoach:
    def __init__(self):
        self.exercises_db = self._load_exercises()

    def _load_exercises(self):
        exercises_path = _REFS_DIR / "exercises.json"
        try:
            with open(exercises_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Exercise database not found: {exercises_path}", file=sys.stderr)
            sys.exit(1)

    def suggest_routine(self, duration=15, focus="core", level="beginner"):
        focus_map = {
            "core": "core_stability", "lower": "lower_body",
            "flexibility": "flexibility", "cardio": "cardio_low_impact",
        }
        category_key = focus_map.get(focus, "core_stability")
        exercises = self.exercises_db.get(category_key, [])

        today = datetime.now().strftime("%Y-%m-%d")
        since = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        conn = get_conn()
        try:
            recent = query_exercises(conn, since, today)
        finally:
            conn.close()

        print(f"\n{duration}min {focus} routine (level: {level})")
        print("=" * 60)

        if recent:
            print(f"\n[recent exercises - last 3 days: {len(recent)} entries]")
            for e in recent[-3:]:
                print(f"  - {e['date']}: {e.get('type', '?')}")

        filtered = [ex for ex in exercises if ex.get("level") == level or ex.get("level") == "all"]
        if not filtered:
            filtered = exercises

        num_exercises = min(3 if duration <= 15 else 4, len(filtered))
        selected = filtered[:num_exercises]

        print("\nRecommended exercises:\n")
        for i, ex in enumerate(selected, 1):
            print(f"{i}. {ex['name']}")
            print(f"   Target: {ex['target']}")
            if "sets_reps" in ex:
                print(f"   Sets: {ex['sets_reps']}")
            elif "duration" in ex:
                print(f"   Duration: {ex['duration']}")
            print(f"   How: {ex['description']}")
            print(f"   Breathing: {ex.get('breathing', 'N/A')}")
            print(f"   Caution: {ex['caution']}")
            print()

        print("AVOID these movements (disk herniation precaution):")
        for avoid in self.exercises_db.get("avoid", [])[:3]:
            print(f"  X {avoid['name']}: {avoid['reason']}")

        print("\n" + "=" * 60)
        print("\nSafety rules:")
        print("  - Maintain neutral spine")
        print("  - Breathe with movement")
        print("  - Stop immediately if pain occurs")
        print("  - Increase intensity gradually")

    def analyze_symptoms(self, period="7days"):
        days = int(period.replace("days", ""))
        today = datetime.now().strftime("%Y-%m-%d")
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        conn = get_conn()
        try:
            entries = query_symptoms(conn, since, today)
        finally:
            conn.close()

        print(f"\nSymptom analysis: {since} ~ {today}")
        print("=" * 60)

        if not entries:
            print(f"\nNo symptom records found in the last {days} days.")
            return

        symptom_counts = {}
        severity_counts = {}
        for e in entries:
            name = e["type"]
            symptom_counts[name] = symptom_counts.get(name, 0) + 1
            sev = e.get("severity", "")
            severity_counts.setdefault(name, []).append(sev)

        print(f"\nTotal symptom records: {len(entries)}")
        print("\nSymptom frequency:")
        for name, count in sorted(symptom_counts.items(), key=lambda x: -x[1]):
            sevs = severity_counts.get(name, [])
            print(f"  {name}: {count}x (severities: {', '.join(sevs)})")

    def guide_exercise(self, exercise_name, level="beginner"):
        print(f"\n{exercise_name} - Detailed Guide")
        print("=" * 60)

        found = None
        for category in ["core_stability", "lower_body", "flexibility", "cardio_low_impact"]:
            for ex in self.exercises_db.get(category, []):
                if exercise_name.lower() in ex["name"].lower():
                    found = ex
                    break
            if found:
                break

        if not found:
            print(f"\nExercise not found: {exercise_name}")
            print("\nAvailable exercises:")
            for cat in ["core_stability", "lower_body", "flexibility", "cardio_low_impact"]:
                for ex in self.exercises_db.get(cat, []):
                    print(f"  - {ex['name']}")
            return

        print(f"\nName: {found['name']}")
        print(f"Level: {found['level']}")
        print(f"Target: {found['target']}")
        if "sets_reps" in found:
            print(f"\nSets/Reps: {found['sets_reps']}")
        elif "duration" in found:
            print(f"\nDuration: {found['duration']}")
        print(f"\nHow to perform:\n  {found['description']}")
        print(f"\nBreathing:\n  {found['breathing']}")
        print(f"\nCaution:\n  {found['caution']}")
        if "progression" in found:
            print(f"\nProgression:\n  {found['progression']}")
        if "common_mistakes" in found:
            print("\nCommon mistakes:")
            for mistake in found["common_mistakes"]:
                print(f"  - {mistake}")

    def lifestyle_advice(self, category="sleep"):
        advice = {
            "sleep": {
                "title": "Sleep Optimization (Spinal Health)",
                "tips": [
                    "Side sleeping (pillow between knees)",
                    "Mattress: medium firmness",
                    "Pillow height: keep neck/spine aligned",
                    "No prone sleeping",
                    "Light stretching before bed",
                    "Consistent sleep schedule (7-8 hours)",
                    "Room temperature: 18-20C",
                ],
                "avoid": ["Hard floor", "Pillow too high", "Prone sleeping", "Late-night screen time"],
            },
            "diet": {
                "title": "Spinal Health Diet",
                "tips": [
                    "Anti-inflammatory: salmon, nuts, blueberries",
                    "Calcium: milk, cheese, broccoli",
                    "Vitamin D: sunlight, salmon, eggs",
                    "Protein: muscle recovery",
                    "Omega-3: reduce inflammation",
                    "Hydration: 2L+ daily",
                ],
                "avoid": ["Processed food", "Excess sugar", "Trans fats", "Too much caffeine"],
            },
            "posture": {
                "title": "Daily Posture Correction",
                "tips": [
                    "Sitting: lumbar support, feet flat",
                    "Monitor: eye level, arm's length",
                    "Stand/stretch every 30 minutes",
                    "Lifting: bend knees, keep object close",
                ],
                "avoid": ["Prolonged sitting", "Bending to lift", "Crossing legs"],
            },
            "stress": {
                "title": "Stress Management",
                "tips": [
                    "Breathing: diaphragmatic 5 min",
                    "Meditation: 10 min daily",
                    "Walking: 20-30 min in nature",
                    "Set limits: do only what you can",
                ],
                "avoid": ["Overwork", "Sleep deprivation", "Social isolation"],
            },
        }

        if category not in advice:
            print(f"Unknown category: {category}")
            print("Available: sleep, diet, posture, stress")
            return

        info = advice[category]
        print(f"\n{info['title']}")
        print("=" * 60)

        if category == "sleep":
            today = datetime.now().strftime("%Y-%m-%d")
            since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            conn = get_conn()
            try:
                checkins = query_check_ins(conn, since, today)
            finally:
                conn.close()
            sleep_data = [c["sleep_hours"] for c in checkins if c.get("sleep_hours")]
            if sleep_data:
                avg = sum(sleep_data) / len(sleep_data)
                print(f"\n[Your avg sleep last 7 days: {avg:.1f}h]")

        print("\nRecommendations:")
        for tip in info["tips"]:
            print(f"  - {tip}")
        print("\nAvoid:")
        for avoid in info["avoid"]:
            print(f"  - {avoid}")

    def health_checkup(self):
        print("\nComprehensive Health Check")
        print("=" * 60)

        today = datetime.now().strftime("%Y-%m-%d")
        conn = get_conn()
        try:
            checkins = query_check_ins(conn, today, today)
            today_data = checkins[0] if checkins else None

            since_3d = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
            symptoms = query_symptoms(conn, since_3d, today)
        finally:
            conn.close()

        if today_data:
            print(f"\nToday's check-in ({today}):")
            for key in ["sleep_hours", "sleep_quality", "steps", "workout", "stress", "water_ml", "notes"]:
                val = today_data.get(key)
                if val is not None:
                    print(f"  {key}: {val}")
        else:
            print(f"\nNo check-in recorded for today ({today}).")
            print("Use track_health.py to record your daily metrics.")

        if symptoms:
            print(f"\nRecent symptoms (last 3 days): {len(symptoms)}")
            for s in symptoms[-3:]:
                print(f"  - {s['date']}: {s['type']} (severity: {s['severity']})")

        print("\nDaily checklist:")
        items = [
            ("Exercise", "Did you move for 15+ minutes today?"),
            ("Posture", "Did you use lumbar support while sitting?"),
            ("Stretching", "Did you stand/stretch every 30 minutes?"),
            ("Hydration", "Did you drink 1.5L+ water?"),
            ("Sleep", "Did you sleep 7+ hours last night?"),
            ("Pain", "Did you have back pain today?"),
            ("Stress", "Did you spend time managing stress?"),
        ]
        for label, question in items:
            status = " "
            if today_data:
                if label == "Exercise" and today_data.get("workout"):
                    status = "x"
                elif label == "Hydration" and (today_data.get("water_ml", 0) or 0) >= 1500:
                    status = "x"
                elif label == "Sleep" and (today_data.get("sleep_hours", 0) or 0) >= 7:
                    status = "x"
            print(f"  [{status}] {question}")


def main():
    parser = argparse.ArgumentParser(description="Health Coach commands (SQLite-backed)")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    rp = subparsers.add_parser("suggest-routine", help="Suggest exercise routine")
    rp.add_argument("--duration", type=int, default=15)
    rp.add_argument("--focus", choices=["core", "lower", "flexibility", "cardio"], default="core")
    rp.add_argument("--level", choices=["beginner", "intermediate", "advanced"], default="beginner")

    sp = subparsers.add_parser("analyze-symptoms", help="Analyze symptom patterns")
    sp.add_argument("--period", default="7days")

    gp = subparsers.add_parser("guide-exercise", help="Detailed exercise guide")
    gp.add_argument("--exercise", required=True)
    gp.add_argument("--level", choices=["beginner", "intermediate", "advanced"], default="beginner")

    lp = subparsers.add_parser("lifestyle-advice", help="Lifestyle guidance")
    lp.add_argument("--category", choices=["sleep", "diet", "posture", "stress"], required=True)

    subparsers.add_parser("health-checkup", help="Comprehensive health check")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    coach = HealthCoach()
    if args.command == "suggest-routine":
        coach.suggest_routine(args.duration, args.focus, args.level)
    elif args.command == "analyze-symptoms":
        coach.analyze_symptoms(args.period)
    elif args.command == "guide-exercise":
        coach.guide_exercise(args.exercise, args.level)
    elif args.command == "lifestyle-advice":
        coach.lifestyle_advice(args.category)
    elif args.command == "health-checkup":
        coach.health_checkup()


if __name__ == "__main__":
    main()
```

**Step 2: track_health.py 생성 (life-coach/scripts/)**

```python
#!/usr/bin/env python3
"""Record daily health check-in — SQLite 저장."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, upsert_check_in


def record_checkin(sleep_hours=None, sleep_quality=None, steps=None,
                   workout=False, stress=None, water=None, notes=""):
    date_str = datetime.now().strftime("%Y-%m-%d")
    data = {
        "date": date_str,
        "sleep_hours": sleep_hours,
        "sleep_quality": sleep_quality,
        "steps": steps,
        "workout": 1 if workout else 0,
        "stress": stress,
        "water_ml": water,
        "notes": notes or None,
    }

    conn = get_conn()
    try:
        upsert_check_in(conn, data)
        conn.commit()
    finally:
        conn.close()

    print(f"Check-in recorded: {date_str}")
    if sleep_hours is not None:
        print(f"  Sleep: {sleep_hours}h", end="")
        if sleep_quality is not None:
            print(f" (quality: {sleep_quality}/10)", end="")
        print()
    if steps is not None:
        print(f"  Steps: {steps}")
    print(f"  Workout: {'yes' if workout else 'no'}")
    if stress is not None:
        print(f"  Stress: {stress}/10")
    if water is not None:
        print(f"  Water: {water}ml")


def main():
    parser = argparse.ArgumentParser(description="Record daily health check-in")
    parser.add_argument("--sleep-hours", type=float)
    parser.add_argument("--sleep-quality", type=int)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--workout", action="store_true", default=False)
    parser.add_argument("--stress", type=int)
    parser.add_argument("--water", type=int, help="Water intake in ml")
    parser.add_argument("--notes", type=str, default="")
    args = parser.parse_args()

    if all(v is None or v is False or v == "" for v in [
        args.sleep_hours, args.sleep_quality, args.steps,
        args.workout if args.workout else None,
        args.stress, args.water, args.notes if args.notes else None,
    ]):
        parser.print_help()
        sys.exit(0)

    record_checkin(args.sleep_hours, args.sleep_quality, args.steps,
                   args.workout, args.stress, args.water, args.notes)


if __name__ == "__main__":
    main()
```

**Step 3: daily_routine.py 복사**

health-coach/scripts/daily_routine.py를 life-coach/scripts/로 복사.
health_io import를 db import로 변경.

원본을 읽어서 필요한 변경만 반영. (health_io.read_entries → query_check_ins)

**Step 4: config 파일 이동**

```bash
mkdir -p shared/life-coach/references
cp shared/health-coach/config/exercises.json shared/life-coach/references/exercises.json
cp shared/health-coach/config/routines.json shared/life-coach/references/routines.json
```

**Step 5: 검증**

```bash
python3 shared/life-coach/scripts/health_cmds.py --help
python3 shared/life-coach/scripts/track_health.py --help
```
Expected: 에러 없이 help 출력

**Step 6: Commit**

```bash
git add shared/life-coach/scripts/health_cmds.py shared/life-coach/scripts/track_health.py \
        shared/life-coach/scripts/daily_routine.py shared/life-coach/references/
git commit -m "feat: absorb health-coach into life-coach"
```

---

### Task 6: daily_coach.py + weekly_coach.py에 건강 섹션 추가

**Files:**
- Modify: `shared/life-coach/scripts/daily_coach.py` (health 섹션 추가)
- Modify: `shared/life-coach/scripts/weekly_coach.py` (health 섹션 추가)

**Step 1: daily_coach.py에 health import + 데이터 수집 + 섹션 빌더 추가**

db.py import에 health 함수 추가:
```python
from db import get_conn, get_coach_state, set_coach_state, get_repeated_signals, \
    query_exercises, query_symptoms, query_meals, query_check_ins
```

`get_today_data()` 함수 끝에 health 데이터 추가:
```python
    # health data
    exercises = query_exercises(conn, date_str, date_str)
    symptoms = query_symptoms(conn, date_str, date_str)
    meals = query_meals(conn, date_str, date_str)
    checkins = query_check_ins(conn, date_str, date_str)

    return {
        # ... existing fields ...
        "exercises": [dict(e) for e in exercises],
        "symptoms": [dict(s) for s in symptoms],
        "meals": [dict(m) for m in meals],
        "check_in": dict(checkins[0]) if checkins else None,
    }
```

새 섹션 빌더:
```python
def _build_health_section(data: dict) -> str | None:
    lines = []

    # Check-in
    ci = data.get("check_in")
    if ci:
        parts = []
        if ci.get("sleep_hours"):
            parts.append(f"수면 {ci['sleep_hours']}h")
        if ci.get("steps"):
            parts.append(f"걸음 {ci['steps']}")
        if ci.get("stress"):
            parts.append(f"스트레스 {ci['stress']}/10")
        if ci.get("water_ml"):
            parts.append(f"수분 {ci['water_ml']}ml")
        if parts:
            lines.append("  " + " · ".join(parts))

    # Exercise
    exercises = data.get("exercises", [])
    if exercises:
        ex_parts = [f"{e['type']} {e['duration_min']}분" for e in exercises]
        lines.append(f"  운동: {', '.join(ex_parts)}")
    else:
        lines.append("  운동 기록 없음")

    # Meals
    meals = data.get("meals", [])
    eaten = [m for m in meals if not m.get("skipped")]
    skipped = [m for m in meals if m.get("skipped")]
    if meals:
        total_cal = sum(m.get("calories", 0) or 0 for m in eaten)
        total_protein = sum(m.get("protein_g", 0) or 0 for m in eaten)
        lines.append(f"  식사: {len(eaten)}끼 ({total_cal}kcal, 단백질 {total_protein:.0f}g)")
        if skipped:
            lines.append(f"  거른 끼니: {len(skipped)}끼")
    else:
        lines.append("  식사 기록 없음")

    # Symptoms
    symptoms = data.get("symptoms", [])
    if symptoms:
        sym_parts = [f"{s['type']}({s['severity']})" for s in symptoms]
        lines.append(f"  증상: {', '.join(sym_parts)}")

    if not lines:
        return None
    return "💊 건강:\n" + "\n".join(lines)
```

`build_template_report()`에 health 섹션 삽입 (nudges 섹션 이후):
```python
    health = _build_health_section(data)
    if health:
        sections.append(health)
```

**Step 2: weekly_coach.py에 유사하게 주간 건강 요약 추가**

`get_week_data()`에 주간 health 집계:
```python
from db import get_conn, get_coach_state, query_exercises, query_symptoms, query_meals, query_check_ins

# get_week_data() 끝에:
    exercises = query_exercises(conn, mon, sun)
    symptoms = query_symptoms(conn, mon, sun)
    meals = query_meals(conn, mon, sun)
    checkins = query_check_ins(conn, mon, sun)

    return {
        # ... existing fields ...
        "exercises": exercises,
        "symptoms": symptoms,
        "meals": meals,
        "check_ins": checkins,
    }
```

`_build_health_weekly()` 섹션 빌더:
```python
def _build_health_weekly(data: dict) -> str | None:
    lines = []

    exercises = data.get("exercises", [])
    if exercises:
        ex_days = len(set(e["date"] for e in exercises))
        total_min = sum(e["duration_min"] for e in exercises)
        pt_count = len([e for e in exercises if e["type"] == "PT"])
        lines.append(f"  운동 {ex_days}일 ({total_min}분) · PT {pt_count}회/2")

    symptoms = data.get("symptoms", [])
    if symptoms:
        lines.append(f"  증상 {len(symptoms)}건")

    meals = data.get("meals", [])
    if meals:
        eaten = len([m for m in meals if not m.get("skipped")])
        skipped = len([m for m in meals if m.get("skipped")])
        lines.append(f"  식사 {eaten}끼 · 거름 {skipped}끼")

    checkins = data.get("check_ins", [])
    if checkins:
        sleep_data = [c["sleep_hours"] for c in checkins if c.get("sleep_hours")]
        if sleep_data:
            avg_sleep = sum(sleep_data) / len(sleep_data)
            lines.append(f"  평균 수면 {avg_sleep:.1f}h ({len(checkins)}일 체크인)")

    if not lines:
        return None
    return "💊 주간 건강:\n" + "\n".join(lines)
```

**Step 3: 검증**

```bash
python3 shared/life-coach/scripts/daily_coach.py --dry-run
python3 shared/life-coach/scripts/weekly_coach.py --dry-run
```
Expected: 기존 섹션 출력 + 건강 섹션 (데이터 있으면 표시, 없으면 "기록 없음")

**Step 4: Commit**

```bash
git add shared/life-coach/scripts/daily_coach.py shared/life-coach/scripts/weekly_coach.py
git commit -m "feat: add health sections to daily/weekly coach reports"
```

---

### Task 7: SKILL.md 업데이트 + health-coach 삭제

**Files:**
- Modify: `shared/health-tracker/SKILL.md`
- Modify: `shared/meal-tracker/SKILL.md`
- Modify: `shared/life-coach/SKILL.md`
- Delete: `shared/health-coach/` (전체 디렉토리)

**Step 1: health-tracker/SKILL.md 업데이트**

- description: "운동/증상/PT 트래킹 — SQLite 기록"
- Obsidian 저장 구조 → SQLite 테이블 설명으로 교체
- 스크립트 사용법은 유지하되 `log_pt_homework.py complete --id N`으로 변경

**Step 2: meal-tracker/SKILL.md 업데이트**

- description: "GLP-1 약물 기반 식사 기록 + 영양 모니터링"
- 저장소: Obsidian vault → SQLite
- Dataview 쿼리 섹션 제거

**Step 3: life-coach/SKILL.md 업데이트**

- description에 건강 코칭 포함
- health-coach에서 이동된 서브커맨드 문서화: health_cmds.py, track_health.py, daily_routine.py
- Scripts 테이블에 새 스크립트 추가
- References에 exercises.json, routines.json 추가

**Step 4: health-coach 디렉토리 삭제**

```bash
rm -rf shared/health-coach
```

**Step 5: health-coach/.claude-skill의 symlink 정리**

```bash
# install-cc에서 자동 처리되지만, 수동 확인
ls -la ~/.claude/skills/ | grep health-coach
# 있으면 삭제
rm -f ~/.claude/skills/health-coach
```

**Step 6: CLAUDE.md 업데이트**

스킬 목록에서 health-coach 제거, health-tracker/meal-tracker/life-coach 설명 업데이트.

**Step 7: Commit**

```bash
git add shared/health-tracker/SKILL.md shared/meal-tracker/SKILL.md \
        shared/life-coach/SKILL.md CLAUDE.md
git rm -rf shared/health-coach
git commit -m "feat: update SKILL.md files, delete health-coach"
```

---

### Task 8: 최종 검증

**Step 1: 모든 스크립트 import 검증**

```bash
for f in shared/health-tracker/scripts/log_exercise.py \
         shared/health-tracker/scripts/log_symptom.py \
         shared/health-tracker/scripts/log_pt_homework.py \
         shared/health-tracker/scripts/check_pt_attendance.py \
         shared/health-tracker/scripts/daily_reminder.py \
         shared/meal-tracker/scripts/log_meal.py \
         shared/meal-tracker/scripts/daily_summary.py \
         shared/life-coach/scripts/health_cmds.py \
         shared/life-coach/scripts/track_health.py \
         shared/life-coach/scripts/daily_coach.py \
         shared/life-coach/scripts/weekly_coach.py; do
    python3 -c "import importlib.util; spec=importlib.util.spec_from_file_location('m','$f'); mod=importlib.util.module_from_spec(spec)" 2>&1 | grep -i error && echo "FAIL: $f" || echo "OK: $f"
done
```

**Step 2: --help 실행 확인**

```bash
python3 shared/health-tracker/scripts/log_exercise.py --help
python3 shared/life-coach/scripts/health_cmds.py --help
python3 shared/meal-tracker/scripts/log_meal.py --help
python3 shared/life-coach/scripts/daily_coach.py --help
```

**Step 3: dry-run 확인**

```bash
python3 shared/life-coach/scripts/daily_coach.py --dry-run
python3 shared/life-coach/scripts/weekly_coach.py --dry-run
```

**Step 4: health_io.py / meals_io.py 잔여 참조 확인**

```bash
grep -r "health_io" shared/ --include="*.py"
grep -r "meals_io" shared/ --include="*.py"
```
Expected: 결과 없음 (삭제된 파일 외 참조 없어야 함)

**Step 5: make install-cc 재실행**

```bash
make install-cc
```
