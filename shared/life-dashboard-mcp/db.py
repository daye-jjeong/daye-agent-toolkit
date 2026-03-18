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
    conn.execute("PRAGMA busy_timeout=5000")
    if not _schema_initialized:
        conn.executescript(SCHEMA_PATH.read_text())
        _migrate(conn)
        _schema_initialized = True
    return conn


def _migrate(conn: sqlite3.Connection):
    """Additive schema migrations for existing databases."""
    # session_topics: additive column migrations
    try:
        st_cols = {r[1] for r in conn.execute("PRAGMA table_info(session_topics)").fetchall()}
        if st_cols:
            for col, default in [("start_at", None), ("end_at", None), ("status", "'completed'"), ("follow_up", None)]:
                if col not in st_cols:
                    default_clause = f" DEFAULT {default}" if default else ""
                    conn.execute(f"ALTER TABLE session_topics ADD COLUMN {col} TEXT{default_clause}")
            conn.commit()
    except Exception:
        pass


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


def _merge_intervals_minutes(intervals: list[tuple[str, str]]) -> int:
    """ISO timestamp 구간 리스트를 병합하여 겹치지 않는 총 분을 반환."""
    if not intervals:
        return 0
    parsed = []
    for s, e in intervals:
        try:
            start = datetime.fromisoformat(s)
            end = datetime.fromisoformat(e)
            if end > start:
                parsed.append((start, end))
        except (ValueError, TypeError):
            continue
    if not parsed:
        return 0
    parsed.sort()
    merged = [parsed[0]]
    for start, end in parsed[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    total = sum((e - s).total_seconds() for s, e in merged)
    return round(total / 60)


def update_daily_stats(conn: sqlite3.Connection, date_str: str):
    rows = conn.execute("""
        SELECT tag, repo, duration_min, start_at, end_at
        FROM sessions
        WHERE date = ?
    """, (date_str,)).fetchall()

    if not rows:
        conn.execute("DELETE FROM daily_stats WHERE date = ?", (date_str,))
        return

    # tag_breakdown: 토픽 기준 우선, 없으면 sessions.tag 폴백
    topic_rows = conn.execute(
        "SELECT tag FROM session_topics WHERE date = ?", (date_str,)
    ).fetchall()

    tags: dict[str, int] = {}
    if topic_rows:
        for r in topic_rows:
            tag = r["tag"] or "기타"
            tags[tag] = tags.get(tag, 0) + 1
    else:
        for r in rows:
            tag = r["tag"] or "기타"
            tags[tag] = tags.get(tag, 0) + 1

    repos: dict[str, int] = {}
    first_session = "99:99"
    last_end = "00:00"
    intervals = []
    sum_duration = 0

    for r in rows:
        repo = r["repo"] or "unknown"
        repos[repo] = repos.get(repo, 0) + 1
        sum_duration += r["duration_min"] or 0
        start_time = r["start_at"][11:16] if r["start_at"] and len(r["start_at"]) > 15 else "00:00"
        end_time = r["end_at"][11:16] if r["end_at"] and len(r["end_at"]) > 15 else start_time
        if start_time < first_session:
            first_session = start_time
        if end_time > last_end:
            last_end = end_time
        s = r["start_at"] or ""
        e = r["end_at"] or s
        if len(s) >= 16 and len(e) >= 16:
            intervals.append((s, e))

    # work_hours: 토픽 있으면 토픽 구간 병합 (정확), 없으면 세션 duration 합산 폴백
    topic_intervals = conn.execute(
        "SELECT start_at, end_at FROM session_topics "
        "WHERE date = ? AND start_at IS NOT NULL AND end_at IS NOT NULL",
        (date_str,),
    ).fetchall()
    if topic_intervals:
        total_min = _merge_intervals_minutes(
            [(r["start_at"], r["end_at"]) for r in topic_intervals]
        )
    else:
        merged_wall = _merge_intervals_minutes(intervals)
        total_min = min(sum_duration, merged_wall) if merged_wall else sum_duration

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


_VALID_TAGS = {"코딩", "디버깅", "리서치", "리뷰", "ops", "설정", "문서", "설계", "리팩토링", "기타"}


def upsert_session_topics(
    conn: sqlite3.Connection,
    source: str, session_id: str, date: str,
    topics: list[dict],
    sync_session_cache: bool = True,
):
    """session_topics 전체 교체 (DELETE + INSERT) + sessions.summary 캐시 동기화.

    검증: summary 빈 값 skip, tag 유효성, 10개 상한.
    sync_session_cache=True면 첫 번째 토픽으로 sessions.summary/tag 캐시 갱신.
    """
    valid = []
    for t in topics[:10]:
        if not t.get("summary"):
            continue
        tag = t.get("tag", "기타")
        if tag not in _VALID_TAGS:
            tag = "기타"
        valid.append({**t, "tag": tag})

    if not valid:
        return

    # duration_estimate_min 자동 채우기 — 명시 안 된 토픽은 세션 시간 균등 분배
    any_missing = any(not t.get("duration_estimate_min") for t in valid)
    if any_missing:
        row = conn.execute(
            "SELECT duration_min FROM sessions WHERE source=? AND session_id=? AND date=?",
            (source, session_id, date),
        ).fetchone()
        session_dur = row["duration_min"] if row and row["duration_min"] else 30
        per_topic = max(1, session_dur // len(valid))
        for t in valid:
            if not t.get("duration_estimate_min"):
                t["duration_estimate_min"] = per_topic

    conn.execute(
        "DELETE FROM session_topics WHERE source=? AND session_id=? AND date=?",
        (source, session_id, date),
    )
    for i, t in enumerate(valid):
        conn.execute("""
            INSERT INTO session_topics (source, session_id, date, topic_order, tag, summary, repo, start_at, end_at, duration_estimate_min, status, follow_up)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (source, session_id, date, i, t["tag"], t["summary"], t.get("repo"), t.get("start_at"), t.get("end_at"), t.get("duration_estimate_min"), t.get("status", "completed"), t.get("follow_up")))

    if sync_session_cache and valid:
        first = valid[0]
        conn.execute("""
            UPDATE sessions SET summary = ?, tag = ?, summary_source = 'llm'
            WHERE source = ? AND session_id = ? AND date = ?
        """, (first["summary"], first["tag"], source, session_id, date))


def get_session_topics(conn: sqlite3.Connection, date: str) -> list[dict]:
    """해당 날짜의 모든 session_topics 조회 (부모 session 메타 포함)."""
    rows = conn.execute("""
        SELECT st.*, s.source as s_source, s.status, s.has_commits, s.has_tests,
               s.start_at, s.duration_min, s.token_total
        FROM session_topics st
        JOIN sessions s USING (source, session_id, date)
        WHERE st.date = ?
        ORDER BY s.start_at, st.topic_order
    """, (date,)).fetchall()
    return [dict(r) for r in rows]


def get_coach_state(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT key, value FROM coach_state").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_coach_state(conn: sqlite3.Connection, key: str, value: str):
    conn.execute("""
        INSERT INTO coach_state (key, value, updated_at)
        VALUES (?, ?, datetime('now','localtime'))
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
    """, (key, value))


def get_repeated_signals(conn: sqlite3.Connection, date_str: str, days: int = 7, min_count: int = 2) -> list[dict]:
    """최근 N일간 반복된 행동 신호 집계."""
    since = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT content, signal_type, COUNT(*) as cnt
        FROM signals
        WHERE date >= ? AND signal_type IN ('mistake', 'pattern')
        GROUP BY content, signal_type
        HAVING cnt >= ?
        ORDER BY cnt DESC LIMIT 10
    """, (since, min_count)).fetchall()
    return [{"content": r["content"], "signal_type": r["signal_type"], "count": r["cnt"]} for r in rows]


def get_mistake_trends(conn: sqlite3.Connection, date_str: str, days: int = 14) -> dict:
    """최근 N일간 mistake 신호를 카테고리별로 집계."""
    since = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT content, COUNT(*) as cnt
        FROM signals
        WHERE date >= ? AND date <= ? AND signal_type = 'mistake'
        GROUP BY content ORDER BY cnt DESC
    """, (since, date_str)).fetchall()

    # Load category definitions from life-coach skill (cross-module dependency)
    cat_path = Path(__file__).resolve().parent.parent / "life-coach" / "references" / "mistake-categories.json"
    categories: dict = {}
    if cat_path.exists():
        categories = json.loads(cat_path.read_text()).get("categories", {})

    by_cat: dict[str, list[tuple[str, int]]] = {}
    uncategorized = []
    total = 0

    for r in rows:
        content, cnt = r["content"], r["cnt"]
        total += cnt
        content_lower = content.lower()
        matched = False
        for cat_key, cat_def in categories.items():
            if any(kw.lower() in content_lower for kw in cat_def.get("keywords", [])):
                by_cat.setdefault(cat_key, []).append((content, cnt))
                matched = True
                break
        if not matched:
            uncategorized.append({"content": content, "count": cnt})

    result_cats = []
    for cat_key, items in sorted(by_cat.items(), key=lambda x: sum(c for _, c in x[1]), reverse=True):
        cat_def = categories[cat_key]
        result_cats.append({
            "category": cat_key,
            "label": cat_def.get("label", cat_key),
            "count": sum(c for _, c in items),
            "examples": [c for c, _ in items[:3]],
        })

    return {"by_category": result_cats, "uncategorized": uncategorized, "total": total}


# ── Sessions v2 CRUD ──────────────────────────


def upsert_session(conn: sqlite3.Connection, data: dict):
    """sessions 테이블 upsert. scanner 컬럼별 우선순위 적용."""
    conn.execute("""
        INSERT INTO sessions (source, session_id, date, repo, branch, tag, summary,
            summary_source, status, follow_up,
            start_at, end_at, duration_min, file_count, error_count,
            has_tests, has_commits, token_total)
        VALUES (:source, :session_id, :date, :repo, :branch, :tag, :summary,
            :summary_source, :status, :follow_up,
            :start_at, :end_at, :duration_min, :file_count, :error_count,
            :has_tests, :has_commits, :token_total)
        ON CONFLICT(source, session_id, date) DO UPDATE SET
            repo=excluded.repo,
            branch=COALESCE(excluded.branch, branch),
            tag=CASE
                WHEN excluded.summary_source IN ('llm', 'manual') THEN COALESCE(excluded.tag, tag)
                ELSE COALESCE(tag, excluded.tag)
            END,
            summary=CASE
                WHEN excluded.summary_source IN ('llm', 'manual') THEN excluded.summary
                ELSE COALESCE(summary, excluded.summary)
            END,
            summary_source=CASE
                WHEN excluded.summary_source IN ('llm', 'manual') THEN excluded.summary_source
                WHEN summary_source IN ('llm', 'manual') THEN summary_source
                ELSE COALESCE(excluded.summary_source, summary_source)
            END,
            status=CASE
                WHEN excluded.summary_source IN ('llm', 'manual') THEN excluded.status
                WHEN status IN ('completed', 'blocked', 'follow_up') THEN status
                ELSE COALESCE(excluded.status, status)
            END,
            follow_up=COALESCE(excluded.follow_up, follow_up),
            end_at=excluded.end_at,
            duration_min=excluded.duration_min,
            file_count=excluded.file_count,
            error_count=excluded.error_count,
            token_total=excluded.token_total,
            has_tests=MAX(has_tests, excluded.has_tests),
            has_commits=MAX(has_commits, excluded.has_commits)
    """, data)


def upsert_session_content(conn: sqlite3.Connection, data: dict):
    """session_content upsert — 최신 상태로 교체."""
    conn.execute("""
        INSERT INTO session_content (source, session_id, date, topic,
            user_messages, agent_messages, files_changed, commands, errors)
        VALUES (:source, :session_id, :date, :topic,
            :user_messages, :agent_messages, :files_changed, :commands, :errors)
        ON CONFLICT(source, session_id, date) DO UPDATE SET
            topic=excluded.topic,
            user_messages=excluded.user_messages,
            agent_messages=excluded.agent_messages,
            files_changed=excluded.files_changed,
            commands=excluded.commands,
            errors=excluded.errors
    """, data)


def insert_signal(conn: sqlite3.Connection, signal: dict):
    """signals 테이블 INSERT OR IGNORE."""
    conn.execute("""
        INSERT OR IGNORE INTO signals (session_id, date, signal_type, content, reasoning, repo)
        VALUES (:session_id, :date, :signal_type, :content, :reasoning, :repo)
    """, signal)


def upsert_coaching_entry(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO coaching_entries (date, period_type, content, sections, escalation_level)
        VALUES (:date, :period_type, :content, :sections, :escalation_level)
        ON CONFLICT(date, period_type) DO UPDATE SET
            content=excluded.content, sections=excluded.sections,
            escalation_level=excluded.escalation_level
    """, data)


def upsert_task_suggestion(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO task_suggestions (suggested_date, description, estimated_min,
            priority, source_type, origin_session_id, status)
        VALUES (:suggested_date, :description, :estimated_min,
            :priority, :source_type, :origin_session_id, :status)
        ON CONFLICT(suggested_date, description) DO UPDATE SET
            estimated_min=excluded.estimated_min, priority=excluded.priority,
            source_type=excluded.source_type, origin_session_id=excluded.origin_session_id
    """, data)


def update_task_resolution(conn: sqlite3.Connection, task_id: int, status: str,
                           resolved_date: str, resolved_session_id: str | None,
                           method: str, notes: str | None = None) -> bool:
    cursor = conn.execute("""
        UPDATE task_suggestions
        SET status=?, resolved_date=?, resolved_session_id=?, resolution_method=?, notes=?
        WHERE id=?
    """, (status, resolved_date, resolved_session_id, method, notes, task_id))
    return cursor.rowcount > 0


def upsert_followup_chain(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT OR IGNORE INTO followup_chains
            (origin_session_id, origin_date, origin_repo, description)
        VALUES (:origin_session_id, :origin_date, :origin_repo, :description)
    """, data)


def update_followup_resolution(conn: sqlite3.Connection, chain_id: int, status: str,
                               resolved_date: str, resolved_session_id: str | None,
                               resolution_note: str | None = None) -> bool:
    cursor = conn.execute("""
        UPDATE followup_chains
        SET status=?, resolved_date=?, resolved_session_id=?, resolution_note=?
        WHERE id=?
    """, (status, resolved_date, resolved_session_id, resolution_note, chain_id))
    return cursor.rowcount > 0


def get_coaching_entry(conn: sqlite3.Connection, date_str: str, period_type: str = "daily") -> dict | None:
    row = conn.execute(
        "SELECT * FROM coaching_entries WHERE date = ? AND period_type = ?",
        (date_str, period_type)
    ).fetchone()
    return dict(row) if row else None


def get_pending_tasks(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM task_suggestions WHERE status = 'pending' ORDER BY priority, suggested_date"
    ).fetchall()
    return [dict(r) for r in rows]


def get_open_followups(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT *, CAST(julianday('now', 'localtime') - julianday(origin_date) AS INTEGER) as days_open
        FROM followup_chains WHERE status = 'open'
        ORDER BY origin_date
    """).fetchall()
    return [dict(r) for r in rows]


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
