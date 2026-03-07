#!/usr/bin/env python3
"""life-dashboard-mcp DB module — SQLite access layer."""

import json
import sqlite3
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
        _schema_initialized = True
    return conn


def upsert_activity(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO activities (source, session_id, repo, tag, summary,
            start_at, end_at, duration_min, file_count, error_count,
            has_tests, has_commits, token_total, raw_json)
        VALUES (:source, :session_id, :repo, :tag, :summary,
            :start_at, :end_at, :duration_min, :file_count, :error_count,
            :has_tests, :has_commits, :token_total, :raw_json)
        ON CONFLICT(source, session_id) DO UPDATE SET
            repo=excluded.repo, tag=excluded.tag, summary=excluded.summary,
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
