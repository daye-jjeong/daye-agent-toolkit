#!/usr/bin/env python3
"""life-dashboard-mcp DB module — SQLite access layer."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

DB_DIR = Path.home() / "life-dashboard"
DB_PATH = DB_DIR / "data.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_schema_initialized = False


def get_conn() -> sqlite3.Connection:
    global _schema_initialized
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if not _schema_initialized:
        conn.executescript(SCHEMA_PATH.read_text())
        _migrate(conn)
        _schema_initialized = True
    return conn


def _migrate(conn: sqlite3.Connection):
    """Additive schema migrations for existing databases."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(activities)").fetchall()}
    if "branch" not in cols:
        conn.execute("ALTER TABLE activities ADD COLUMN branch TEXT")
        conn.commit()


@contextmanager
def open_conn(auto_commit=True):
    """Context manager for get_conn(). Auto-commits on success, rolls back on error."""
    conn = get_conn()
    try:
        yield conn
        if auto_commit:
            conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_activity(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO activities (source, session_id, repo, branch, tag, summary,
            start_at, end_at, duration_min, file_count, error_count,
            has_tests, has_commits, token_total, raw_json)
        VALUES (:source, :session_id, :repo, :branch, :tag, :summary,
            :start_at, :end_at, :duration_min, :file_count, :error_count,
            :has_tests, :has_commits, :token_total, :raw_json)
        ON CONFLICT(source, session_id) DO UPDATE SET
            repo=excluded.repo, branch=excluded.branch,
            tag=excluded.tag, summary=excluded.summary,
            end_at=excluded.end_at, duration_min=excluded.duration_min,
            file_count=excluded.file_count, token_total=excluded.token_total,
            raw_json=excluded.raw_json
    """, data)


def update_daily_stats(conn: sqlite3.Connection, date_str: str):
    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT tag, repo, duration_min, start_at, end_at
        FROM activities
        WHERE start_at >= ? AND start_at < ?
    """, (date_str, next_date)).fetchall()

    if not rows:
        conn.execute("DELETE FROM daily_stats WHERE date = ?", (date_str,))
        return

    tags: dict[str, int] = {}
    repos: dict[str, int] = {}
    total_min = 0
    first_session = "99:99"
    last_end = "00:00"

    for r in rows:
        tag = r["tag"] or "기타"
        tags[tag] = tags.get(tag, 0) + 1
        repo = r["repo"] or "unknown"
        repos[repo] = repos.get(repo, 0) + 1
        total_min += r["duration_min"] or 0
        start_time = r["start_at"][11:16] if r["start_at"] and len(r["start_at"]) > 15 else "00:00"
        end_time = r["end_at"][11:16] if r["end_at"] and len(r["end_at"]) > 15 else start_time
        if start_time < first_session:
            first_session = start_time
        if end_time > last_end:
            last_end = end_time

    conn.execute("""
        INSERT INTO daily_stats (date, work_hours, session_count, tag_breakdown,
            repos, first_session, last_session_end)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            work_hours=excluded.work_hours, session_count=excluded.session_count,
            tag_breakdown=excluded.tag_breakdown, repos=excluded.repos,
            first_session=excluded.first_session, last_session_end=excluded.last_session_end,
            updated_at=datetime('now','localtime')
    """, (
        date_str,
        round(total_min / 60, 1),
        len(rows),
        json.dumps(tags, ensure_ascii=False),
        json.dumps(repos, ensure_ascii=False),
        first_session,
        last_end,
    ))


def get_coach_state(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT key, value FROM coach_state").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_coach_state(conn: sqlite3.Connection, key: str, value: str):
    conn.execute("""
        INSERT INTO coach_state (key, value, updated_at)
        VALUES (?, ?, datetime('now','localtime'))
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
    """, (key, value))


def insert_behavioral_signal(conn: sqlite3.Connection, signal: dict):
    conn.execute("""
        INSERT OR IGNORE INTO behavioral_signals (session_id, date, signal_type, content, repo)
        VALUES (:session_id, :date, :signal_type, :content, :repo)
    """, signal)


def get_repeated_signals(conn: sqlite3.Connection, date_str: str, days: int = 7, min_count: int = 2) -> list[dict]:
    """최근 N일간 반복된 행동 신호 집계."""
    since = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT content, signal_type, COUNT(*) as cnt
        FROM behavioral_signals
        WHERE date >= ? AND signal_type IN ('mistake', 'pattern')
        GROUP BY content, signal_type
        HAVING cnt >= ?
        ORDER BY cnt DESC
        LIMIT 10
    """, (since, min_count)).fetchall()
    return [{"content": r["content"], "signal_type": r["signal_type"], "count": r["cnt"]} for r in rows]


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


_PT_HW_UPDATABLE = {"status", "sets_reps", "notes", "completed_date"}


def update_pt_homework(conn: sqlite3.Connection, hw_id: int, updates: dict) -> bool:
    """Update PT homework. Returns True if row was found and updated."""
    bad_keys = set(updates) - _PT_HW_UPDATABLE
    if bad_keys:
        raise ValueError(f"Invalid columns for PT homework update: {bad_keys}")
    sets = ", ".join(f"{k}=:{k}" for k in updates)
    updates["id"] = hw_id
    cursor = conn.execute(f"UPDATE health_pt_homework SET {sets} WHERE id = :id", updates)
    return cursor.rowcount > 0


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
            sleep_hours=COALESCE(excluded.sleep_hours, sleep_hours),
            sleep_quality=COALESCE(excluded.sleep_quality, sleep_quality),
            steps=COALESCE(excluded.steps, steps),
            workout=COALESCE(excluded.workout, workout),
            stress=COALESCE(excluded.stress, stress),
            water_ml=COALESCE(excluded.water_ml, water_ml),
            notes=COALESCE(excluded.notes, notes)
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


# ── Pantry ──────────────────────────────────

PANTRY_STATUSES = {"재고 있음", "부족", "만료"}


def upsert_pantry_item(conn: sqlite3.Connection, data: dict):
    """식재료 upsert. 동일 name+location이 있으면 수량을 누적한다."""
    conn.execute("""
        INSERT INTO pantry_items (name, category, quantity, unit, location,
            purchase_date, expiry_date, status, notes, updated_at)
        VALUES (:name, :category, :quantity, :unit, :location,
            :purchase_date, :expiry_date, :status, :notes, datetime('now','localtime'))
        ON CONFLICT(name, location) DO UPDATE SET
            category=excluded.category, quantity=quantity + excluded.quantity, unit=excluded.unit,
            purchase_date=excluded.purchase_date, expiry_date=excluded.expiry_date,
            status=excluded.status, notes=excluded.notes,
            updated_at=datetime('now','localtime')
    """, data)


def query_pantry_items(conn: sqlite3.Connection, category: str | None = None,
                       location: str | None = None, status: str | None = None) -> list[dict]:
    clauses = []
    params = []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if location:
        clauses.append("location = ?")
        params.append(location)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = " AND ".join(clauses)
    sql = "SELECT * FROM pantry_items"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY category, name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def update_pantry_status(conn: sqlite3.Connection, item_id: int, status: str) -> bool:
    if status not in PANTRY_STATUSES:
        raise ValueError(f"Invalid pantry status: {status!r}. Must be one of {PANTRY_STATUSES}")
    cursor = conn.execute(
        "UPDATE pantry_items SET status = ?, updated_at = datetime('now','localtime') WHERE id = ?",
        (status, item_id),
    )
    return cursor.rowcount > 0


def delete_pantry_item(conn: sqlite3.Connection, item_id: int) -> bool:
    cursor = conn.execute("DELETE FROM pantry_items WHERE id = ?", (item_id,))
    return cursor.rowcount > 0


def query_expiring_pantry(conn: sqlite3.Connection, days_ahead: int = 3) -> dict:
    """유통기한 임박/만료 항목 조회."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    threshold = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    expired = [dict(r) for r in conn.execute("""
        SELECT * FROM pantry_items
        WHERE expiry_date IS NOT NULL AND expiry_date < ? AND status = '재고 있음'
        ORDER BY expiry_date
    """, (today_str,)).fetchall()]
    expiring = [dict(r) for r in conn.execute("""
        SELECT * FROM pantry_items
        WHERE expiry_date >= ? AND expiry_date <= ? AND status = '재고 있음'
        ORDER BY expiry_date
    """, (today_str, threshold)).fetchall()]
    return {"expiring": expiring, "expired": expired}
