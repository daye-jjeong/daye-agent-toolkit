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
