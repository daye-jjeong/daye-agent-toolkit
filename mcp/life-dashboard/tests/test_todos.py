"""todos + daily_checkins CRUD 테스트."""
import json
import sqlite3
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import upsert_schedule, get_schedule, get_schedules_by_date, delete_schedule, link_schedule_actual, upsert_todo, get_daily_checkins, get_capacity_status


def _setup_db():
    """인메모리 DB에 스키마 로드."""
    schema = (Path(__file__).resolve().parent.parent / "schema.sql").read_text()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema)
    return conn


def test_upsert_todo_defaults():
    from db import upsert_todo, get_todo
    conn = _setup_db()
    tid = upsert_todo(conn, {"title": "cube-backend PR 머지", "done_definition": "master 머지 + CI green"})
    conn.commit()
    t = get_todo(conn, tid)
    assert t["title"] == "cube-backend PR 머지"
    assert t["status"] == "backlog"
    assert t["done_definition"] == "master 머지 + CI green"
    assert t["created_at"] is not None
    assert t["started_at"] is None
    assert t["done_at"] is None
    conn.close()


def test_upsert_todo_full_fields():
    from db import upsert_todo, get_todo, upsert_project
    conn = _setup_db()
    pid = upsert_project(conn, "Cube 2026Q2", repo="cube-backend")
    tid = upsert_todo(conn, {
        "title": "cube-admin 기획",
        "done_definition": "기획서 v1 노션에 작성",
        "category": "업무",
        "priority": 1,
        "project_id": pid,
        "quarter": "2026Q2",
        "deadline": "2026-04-25",
        "estimated_min": 240,
    })
    conn.commit()
    t = get_todo(conn, tid)
    assert t["project_id"] == pid
    assert t["deadline"] == "2026-04-25"
    assert t["estimated_min"] == 240
    assert t["category"] == "업무"
    conn.close()


def test_get_todos_filter_by_status_and_category():
    from db import upsert_todo, get_todos
    conn = _setup_db()
    upsert_todo(conn, {"title": "업무 1", "category": "업무", "status": "backlog"})
    upsert_todo(conn, {"title": "개인 1", "category": "개인", "status": "backlog"})
    upsert_todo(conn, {"title": "업무 wip", "category": "업무", "status": "wip", "done_definition": "x"})
    conn.commit()

    backlog = get_todos(conn, status="backlog")
    assert len(backlog) == 2

    work = get_todos(conn, category="업무")
    assert len(work) == 2

    work_backlog = get_todos(conn, status="backlog", category="업무")
    assert len(work_backlog) == 1
    assert work_backlog[0]["title"] == "업무 1"
    conn.close()


def test_update_todo_status_done_definition_required():
    from db import upsert_todo, update_todo_status
    conn = _setup_db()
    tid = upsert_todo(conn, {"title": "준비 안 됨"})  # done_definition null
    conn.commit()
    with pytest.raises(ValueError, match="done_definition"):
        update_todo_status(conn, tid, "wip")
    conn.close()


def test_update_todo_status_wip_limit():
    from db import upsert_todo, update_todo_status, get_todos
    conn = _setup_db()
    ids = [upsert_todo(conn, {"title": f"t{i}", "done_definition": "x"}) for i in range(3)]
    update_todo_status(conn, ids[0], "wip")
    update_todo_status(conn, ids[1], "wip")
    conn.commit()

    with pytest.raises(ValueError, match="WIP limit"):
        update_todo_status(conn, ids[2], "wip")

    # force=True로 초과 허용
    update_todo_status(conn, ids[2], "wip", force=True)
    conn.commit()
    wip = get_todos(conn, status="wip")
    assert len(wip) == 3
    conn.close()


def test_update_todo_status_timestamps():
    from db import upsert_todo, update_todo_status, get_todo
    conn = _setup_db()
    tid = upsert_todo(conn, {"title": "t", "done_definition": "x"})
    conn.commit()

    update_todo_status(conn, tid, "wip")
    conn.commit()
    t = get_todo(conn, tid)
    assert t["started_at"] is not None
    assert t["done_at"] is None

    update_todo_status(conn, tid, "done")
    conn.commit()
    t = get_todo(conn, tid)
    assert t["done_at"] is not None
    conn.close()


def test_update_todo_status_wip_reentry_preserves_started_at():
    """wip → blocked → wip 재전환 시 started_at 유지."""
    from db import upsert_todo, update_todo_status, get_todo
    conn = _setup_db()
    tid = upsert_todo(conn, {"title": "t", "done_definition": "x"})
    conn.commit()

    update_todo_status(conn, tid, "wip")
    conn.commit()
    first_started = get_todo(conn, tid)["started_at"]
    assert first_started is not None

    update_todo_status(conn, tid, "blocked")
    conn.commit()

    update_todo_status(conn, tid, "wip")
    conn.commit()
    second_started = get_todo(conn, tid)["started_at"]
    assert second_started == first_started  # 재진입에서도 원래 값 유지
    conn.close()


def test_upsert_todo_update_path_does_not_change_status():
    """upsert_todo UPDATE는 메타데이터만 수정. status는 그대로 유지."""
    from db import upsert_todo, update_todo_status, get_todo
    conn = _setup_db()
    tid = upsert_todo(conn, {"title": "t", "done_definition": "x"})
    conn.commit()
    update_todo_status(conn, tid, "wip")
    conn.commit()
    assert get_todo(conn, tid)["status"] == "wip"

    # 메타 수정 + status='backlog' 시도 — UPDATE 경로는 status 무시
    upsert_todo(conn, {"id": tid, "title": "new title", "status": "backlog"})
    conn.commit()
    t = get_todo(conn, tid)
    assert t["title"] == "new title"
    assert t["status"] == "wip"  # 상태 전환은 update_todo_status 전용
    conn.close()


def test_update_todo_status_deferred_reason():
    from db import upsert_todo, update_todo_status, get_todo
    conn = _setup_db()
    tid = upsert_todo(conn, {"title": "t", "done_definition": "x"})
    conn.commit()

    update_todo_status(conn, tid, "deferred", reason="다음 분기로 연기")
    conn.commit()
    t = get_todo(conn, tid)
    assert t["status"] == "deferred"
    assert t["deferred_reason"] == "다음 분기로 연기"
    conn.close()


def test_get_overdue_todos():
    from db import upsert_todo, get_overdue_todos
    conn = _setup_db()
    upsert_todo(conn, {"title": "지남", "deadline": "2026-04-10"})
    upsert_todo(conn, {"title": "오늘", "deadline": "2026-04-21"})
    upsert_todo(conn, {"title": "내일", "deadline": "2026-04-22"})
    upsert_todo(conn, {"title": "완료됨", "deadline": "2026-04-10", "status": "done", "done_definition": "x"})
    upsert_todo(conn, {"title": "연기됨", "deadline": "2026-04-10", "status": "deferred"})
    conn.commit()

    overdue = get_overdue_todos(conn, as_of_date="2026-04-21")
    titles = [t["title"] for t in overdue]
    assert "지남" in titles
    assert "완료됨" not in titles
    assert "연기됨" not in titles
    assert "오늘" not in titles  # today는 overdue 아님
    conn.close()


def test_get_due_this_week_todos():
    from db import upsert_todo, get_due_this_week_todos
    conn = _setup_db()
    upsert_todo(conn, {"title": "오늘", "deadline": "2026-04-21"})
    upsert_todo(conn, {"title": "3일 뒤", "deadline": "2026-04-24"})
    upsert_todo(conn, {"title": "7일 뒤", "deadline": "2026-04-28"})
    upsert_todo(conn, {"title": "8일 뒤", "deadline": "2026-04-29"})
    upsert_todo(conn, {"title": "지남", "deadline": "2026-04-10"})
    conn.commit()

    week = get_due_this_week_todos(conn, as_of_date="2026-04-21")
    titles = [t["title"] for t in week]
    assert "3일 뒤" in titles
    assert "7일 뒤" in titles
    assert "8일 뒤" not in titles
    assert "지남" not in titles
    conn.close()


def test_get_todos_backlog_sort_order():
    from db import upsert_todo, get_todos
    conn = _setup_db()
    # deadline 있는 것 → 없는 것 순, deadline 내에서 임박 순, 같으면 priority 높은 순
    upsert_todo(conn, {"title": "deadline 없음 p1", "priority": 1})
    upsert_todo(conn, {"title": "내일 p3", "deadline": "2026-04-22", "priority": 3})
    upsert_todo(conn, {"title": "오늘 p2", "deadline": "2026-04-21", "priority": 2})
    upsert_todo(conn, {"title": "모레 p1", "deadline": "2026-04-23", "priority": 1})
    conn.commit()

    rows = get_todos(conn, status="backlog", sort="default")
    titles = [t["title"] for t in rows]
    assert titles == ["오늘 p2", "내일 p3", "모레 p1", "deadline 없음 p1"]
    conn.close()


def test_parent_id_self_reference():
    from db import upsert_todo, get_todo
    conn = _setup_db()
    parent = upsert_todo(conn, {"title": "cube-admin 기획", "done_definition": "x"})
    child1 = upsert_todo(conn, {"title": "범위 정의", "parent_id": parent, "done_definition": "y"})
    child2 = upsert_todo(conn, {"title": "와이어프레임", "parent_id": parent, "done_definition": "z"})
    conn.commit()

    p = get_todo(conn, parent)
    assert len(p["subtasks"]) == 2
    child_ids = {s["id"] for s in p["subtasks"]}
    assert child_ids == {child1, child2}
    conn.close()


def test_upsert_daily_checkin_and_get():
    from db import upsert_todo, upsert_daily_checkin, get_daily_checkin
    conn = _setup_db()
    t1 = upsert_todo(conn, {"title": "t1", "done_definition": "x"})
    t2 = upsert_todo(conn, {"title": "t2", "done_definition": "x"})
    conn.commit()

    upsert_daily_checkin(conn, "2026-04-21",
                         morning_wip_ids=[t1, t2],
                         morning_intent="오늘 PR 리뷰 3건")
    conn.commit()

    ck = get_daily_checkin(conn, "2026-04-21")
    assert ck["morning_intent"] == "오늘 PR 리뷰 3건"
    assert set(ck["morning_wip_ids"]) == {t1, t2}
    assert ck["missing_wip_ids"] == []
    conn.close()


def test_upsert_daily_checkin_idempotent():
    from db import upsert_daily_checkin, get_daily_checkin
    conn = _setup_db()
    upsert_daily_checkin(conn, "2026-04-21", morning_intent="처음")
    conn.commit()
    first_created = get_daily_checkin(conn, "2026-04-21")["created_at"]

    upsert_daily_checkin(conn, "2026-04-21",
                         evening_reflection="저녁 기록")
    conn.commit()

    ck = get_daily_checkin(conn, "2026-04-21")
    assert ck["morning_intent"] == "처음"  # 유지
    assert ck["evening_reflection"] == "저녁 기록"  # 추가
    assert ck["created_at"] == first_created  # 유지
    conn.close()


def test_daily_checkin_missing_wip_ids():
    """삭제된 todo id는 missing_wip_ids로 분리되어 반환."""
    from db import upsert_todo, upsert_daily_checkin, get_daily_checkin
    conn = _setup_db()
    t1 = upsert_todo(conn, {"title": "t1", "done_definition": "x"})
    t2 = upsert_todo(conn, {"title": "t2", "done_definition": "x"})
    conn.commit()

    upsert_daily_checkin(conn, "2026-04-21", morning_wip_ids=[t1, t2])
    conn.commit()

    # t2 삭제
    conn.execute("DELETE FROM todos WHERE id = ?", (t2,))
    conn.commit()

    ck = get_daily_checkin(conn, "2026-04-21")
    assert ck["morning_wip_ids"] == [t1]  # 유효한 것만
    assert ck["missing_wip_ids"] == [t2]  # 삭제된 것
    conn.close()


def test_daily_checkins_has_capacity_columns():
    """daily_checkins에 available_min, energy, blockers + 3 status 컬럼 있어야 함"""
    conn = _setup_db()
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_checkins)").fetchall()}
        assert "available_min" in cols
        assert "energy" in cols
        assert "blockers" in cols
        assert "available_status" in cols
        assert "energy_status" in cols
        assert "blockers_status" in cols
    finally:
        conn.close()


def test_daily_checkins_status_check_constraint():
    """status 컬럼 CHECK 제약 — invalid 값 거부"""
    conn = _setup_db()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO daily_checkins (date, available_status) VALUES (?, ?)",
                ("2026-04-28", "invalid_status"),
            )
            conn.commit()
    finally:
        conn.rollback()
        conn.close()


def test_daily_checkins_energy_check_constraint():
    """energy CHECK — low/mid/high만 허용"""
    conn = _setup_db()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO daily_checkins (date, energy) VALUES (?, ?)",
                ("2026-04-28", "extreme"),
            )
            conn.commit()
    finally:
        conn.rollback()
        conn.close()


def test_todo_schedules_table_exists():
    conn = _setup_db()
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='todo_schedules'").fetchall()
        assert len(rows) == 1
        cols = {r[1] for r in conn.execute("PRAGMA table_info(todo_schedules)").fetchall()}
        for c in ["id","todo_id","date","start_at","end_at","planned_min","notes","created_at"]:
            assert c in cols
    finally:
        conn.close()


def test_todo_schedules_check_planned_min_positive():
    from db import upsert_todo
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO todo_schedules (todo_id, date, planned_min) VALUES (?, ?, ?)",
                (tid, "2026-04-28", 0),
            )
            conn.commit()
    finally:
        conn.rollback()
        conn.close()


def test_todo_schedules_check_time_pair():
    from db import upsert_todo
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO todo_schedules (todo_id, date, start_at, end_at, planned_min) VALUES (?, ?, ?, ?, ?)",
                (tid, "2026-04-28", "14:00", None, 60),
            )
            conn.commit()
    finally:
        conn.rollback()
        conn.close()


def test_todo_schedules_partial_unique_time_slot():
    from db import upsert_todo
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        conn.execute(
            "INSERT INTO todo_schedules (todo_id, date, start_at, end_at, planned_min) VALUES (?, ?, ?, ?, ?)",
            (tid, "2026-04-28", "14:00", "16:00", 120),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO todo_schedules (todo_id, date, start_at, end_at, planned_min) VALUES (?, ?, ?, ?, ?)",
                (tid, "2026-04-28", "14:00", "16:00", 120),
            )
            conn.commit()
    finally:
        conn.rollback()
        conn.close()


def test_todo_schedules_partial_unique_allows_null_time_duplicates():
    """partial UNIQUE WHERE start_at IS NOT NULL → 시간 미지정 슬롯은 중복 허용."""
    conn = _setup_db()
    try:
        from db import upsert_todo
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        conn.execute(
            "INSERT INTO todo_schedules (todo_id, date, planned_min) VALUES (?, ?, ?)",
            (tid, "2026-04-28", 60),
        )
        conn.execute(
            "INSERT INTO todo_schedules (todo_id, date, planned_min) VALUES (?, ?, ?)",
            (tid, "2026-04-28", 90),
        )
        conn.commit()
        rows = conn.execute(
            "SELECT COUNT(*) FROM todo_schedules WHERE todo_id=? AND date=? AND start_at IS NULL",
            (tid, "2026-04-28"),
        ).fetchone()
        assert rows[0] == 2
    finally:
        conn.close()


def test_todo_schedule_actuals_table_exists():
    conn = _setup_db()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='todo_schedule_actuals'"
        ).fetchall()
        assert len(rows) == 1
        cols = {r[1] for r in conn.execute("PRAGMA table_info(todo_schedule_actuals)").fetchall()}
        for c in ["id","schedule_id","source_task_id","source_date","source_repo","source_summary","duration_min_snapshot","confirmed_at"]:
            assert c in cols, f"missing col: {c}"
    finally:
        conn.close()


def test_actuals_unique_4_tuple():
    """같은 (schedule_id, source_date, source_summary, source_repo) 중복 매핑 차단"""
    from db import upsert_todo
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        cur = conn.execute(
            "INSERT INTO todo_schedules (todo_id, date, planned_min) VALUES (?, ?, ?)",
            (tid, "2026-04-28", 60),
        )
        sid = cur.lastrowid
        conn.execute(
            "INSERT INTO todo_schedule_actuals (schedule_id, source_date, source_summary, source_repo, duration_min_snapshot) VALUES (?, ?, ?, ?, ?)",
            (sid, "2026-04-28", "summary A", "repo X", 30),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO todo_schedule_actuals (schedule_id, source_date, source_summary, source_repo, duration_min_snapshot) VALUES (?, ?, ?, ?, ?)",
                (sid, "2026-04-28", "summary A", "repo X", 30),
            )
            conn.commit()
    finally:
        conn.close()


def test_actuals_no_tasks_fk_survives_task_delete():
    """work-digest의 tasks 테이블 row 삭제가 actual mapping을 파괴하지 않음 (Codex v4 BLOCK 회귀)"""
    from db import upsert_todo
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        conn.execute(
            "INSERT INTO tasks (date, tag, summary, repo, duration_min) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-28", "구현", "task A", "repo X", 60),
        )
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO todo_schedules (todo_id, date, planned_min) VALUES (?, ?, ?)",
            (tid, "2026-04-28", 60),
        )
        sid = cur.lastrowid
        conn.execute(
            "INSERT INTO todo_schedule_actuals (schedule_id, source_task_id, source_date, source_summary, source_repo, duration_min_snapshot) VALUES (?, ?, ?, ?, ?, ?)",
            (sid, task_id, "2026-04-28", "task A", "repo X", 60),
        )
        conn.commit()

        # work-digest가 하루치 task 전체 교체 시뮬레이션
        conn.execute("DELETE FROM tasks WHERE date = ?", ("2026-04-28",))
        conn.commit()

        rows = conn.execute(
            "SELECT * FROM todo_schedule_actuals WHERE schedule_id = ?", (sid,)
        ).fetchall()
        assert len(rows) == 1, "tasks 삭제 후에도 actual은 보존되어야 함"
    finally:
        conn.close()


def test_actuals_schedule_delete_cascade():
    """schedule 삭제 시 actual은 CASCADE 삭제"""
    from db import upsert_todo
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        cur = conn.execute(
            "INSERT INTO todo_schedules (todo_id, date, planned_min) VALUES (?, ?, ?)",
            (tid, "2026-04-28", 60),
        )
        sid = cur.lastrowid
        conn.execute(
            "INSERT INTO todo_schedule_actuals (schedule_id, source_date, source_summary, source_repo, duration_min_snapshot) VALUES (?, ?, ?, ?, ?)",
            (sid, "2026-04-28", "task A", "repo X", 60),
        )
        conn.commit()
        conn.execute("DELETE FROM todo_schedules WHERE id = ?", (sid,))
        conn.commit()
        rows = conn.execute("SELECT * FROM todo_schedule_actuals WHERE schedule_id = ?", (sid,)).fetchall()
        assert len(rows) == 0
    finally:
        conn.close()


def test_actuals_unique_4_tuple_null_repo_allows_duplicates():
    """SQLite NULL semantics: source_repo=NULL인 두 행은 UNIQUE 충돌 안 함.
    의도된 동작 — work-digest 외부 활동(repo 미부여)이 같은 summary로 여러 번 들어와도
    각각 독립 snapshot으로 보관. 추가 dedup이 필요하면 wrapper 단에서 pre-check.
    """
    conn = _setup_db()
    try:
        from db import upsert_todo
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        cur = conn.execute(
            "INSERT INTO todo_schedules (todo_id, date, planned_min) VALUES (?, ?, ?)",
            (tid, "2026-04-28", 60),
        )
        sid = cur.lastrowid
        conn.execute(
            "INSERT INTO todo_schedule_actuals (schedule_id, source_date, source_summary, source_repo, duration_min_snapshot) VALUES (?, ?, ?, ?, ?)",
            (sid, "2026-04-28", "general work", None, 30),
        )
        conn.execute(
            "INSERT INTO todo_schedule_actuals (schedule_id, source_date, source_summary, source_repo, duration_min_snapshot) VALUES (?, ?, ?, ?, ?)",
            (sid, "2026-04-28", "general work", None, 45),
        )
        conn.commit()
        rows = conn.execute(
            "SELECT COUNT(*) FROM todo_schedule_actuals WHERE schedule_id=? AND source_repo IS NULL",
            (sid,),
        ).fetchone()
        assert rows[0] == 2, "NULL repo 행은 중복 허용되어야 함"
    finally:
        conn.close()


def test_upsert_daily_checkin_capacity_fields():
    """capacity 필드 6개를 한 번에 저장 + 조회 round-trip."""
    from db import upsert_daily_checkin, get_daily_checkin
    conn = _setup_db()
    try:
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_min=300, available_status="answered",
            energy="mid", energy_status="answered",
            blockers="두통", blockers_status="answered",
        )
        conn.commit()
        ck = get_daily_checkin(conn, "2026-04-28")
        assert ck["available_min"] == 300
        assert ck["energy"] == "mid"
        assert ck["blockers"] == "두통"
        assert ck["available_status"] == "answered"
        assert ck["energy_status"] == "answered"
        assert ck["blockers_status"] == "answered"
    finally:
        conn.close()


def test_upsert_daily_checkin_skip_status():
    """status='skipped' 명시 시 NULL 값과 함께 저장."""
    from db import upsert_daily_checkin, get_daily_checkin
    conn = _setup_db()
    try:
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_min=None, available_status="skipped",
        )
        conn.commit()
        ck = get_daily_checkin(conn, "2026-04-28")
        assert ck["available_min"] is None
        assert ck["available_status"] == "skipped"
    finally:
        conn.close()


def test_upsert_daily_checkin_status_none_preserves_existing():
    """status 인자 None이면 기존 DB 값 유지 (COALESCE/CASE 패턴 검증)."""
    from db import upsert_daily_checkin, get_daily_checkin
    conn = _setup_db()
    try:
        # 첫 번째: answered로 저장
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_min=300, available_status="answered",
        )
        conn.commit()
        # 두 번째: status=None, 다른 필드만 변경
        upsert_daily_checkin(
            conn, "2026-04-28",
            morning_intent="새 의도",
        )
        conn.commit()
        ck = get_daily_checkin(conn, "2026-04-28")
        assert ck["available_min"] == 300
        assert ck["available_status"] == "answered"  # 유지
        assert ck["morning_intent"] == "새 의도"
    finally:
        conn.close()


def test_upsert_daily_checkin_explicit_unknown_overwrites():
    """status='unknown' 명시 시 기존 status를 'unknown'으로 덮어씀 (None과 다름)."""
    from db import upsert_daily_checkin, get_daily_checkin
    conn = _setup_db()
    try:
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_min=300, available_status="answered",
        )
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_status="unknown",
        )
        ck = get_daily_checkin(conn, "2026-04-28")
        assert ck["available_status"] == "unknown"
    finally:
        conn.close()


def test_upsert_daily_checkin_skipped_with_value_stored_as_is():
    """status='skipped'이지만 value가 함께 들어오면 둘 다 저장 (db.py는 검증 안 함).
    'skipped' 시 value를 NULL로 정리하는 책임은 wrapper 단."""
    from db import upsert_daily_checkin, get_daily_checkin
    conn = _setup_db()
    try:
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_min=300, available_status="skipped",
        )
        ck = get_daily_checkin(conn, "2026-04-28")
        assert ck["available_min"] == 300
        assert ck["available_status"] == "skipped"
    finally:
        conn.close()


def test_upsert_schedule_minutes_only():
    """시간 미지정 — date + planned_min만으로 schedule 생성."""
    conn = _setup_db()
    try:
        from db import upsert_todo
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        sch = get_schedule(conn, sid)
        assert sch["planned_min"] == 120
        assert sch["start_at"] is None
        assert sch["end_at"] is None
    finally:
        conn.close()


def test_upsert_schedule_time_slot():
    """시간 슬롯 명시. db 함수는 planned_min을 그대로 저장 (계산은 wrapper 책임)."""
    conn = _setup_db()
    try:
        from db import upsert_todo
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(
            conn, todo_id=tid, date="2026-04-28",
            start_at="14:00", end_at="16:00", planned_min=120,
        )
        sch = get_schedule(conn, sid)
        assert sch["start_at"] == "14:00"
        assert sch["end_at"] == "16:00"
        assert sch["planned_min"] == 120
    finally:
        conn.close()


def test_upsert_schedule_partial_unique_violation():
    """동일 (todo_id, date, start_at, end_at) 시간 슬롯 중복 시 IntegrityError."""
    conn = _setup_db()
    try:
        from db import upsert_todo
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        upsert_schedule(
            conn, todo_id=tid, date="2026-04-28",
            start_at="14:00", end_at="16:00", planned_min=120,
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            upsert_schedule(
                conn, todo_id=tid, date="2026-04-28",
                start_at="14:00", end_at="16:00", planned_min=120,
            )
            conn.commit()
    finally:
        conn.close()


def test_get_schedules_by_date_orders_null_last():
    """get_schedules_by_date: 시간 슬롯 우선, 미지정은 NULLS LAST."""
    conn = _setup_db()
    try:
        from db import upsert_todo
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid_null = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=60)
        sid_pm = upsert_schedule(
            conn, todo_id=tid, date="2026-04-28",
            start_at="14:00", end_at="16:00", planned_min=120,
        )
        sid_am = upsert_schedule(
            conn, todo_id=tid, date="2026-04-28",
            start_at="09:00", end_at="10:00", planned_min=60,
        )
        rows = get_schedules_by_date(conn, "2026-04-28")
        assert [r["id"] for r in rows] == [sid_am, sid_pm, sid_null]
    finally:
        conn.close()


def test_get_schedule_returns_none_for_missing():
    """존재하지 않는 id는 None 반환 (raise 안 함)."""
    conn = _setup_db()
    try:
        assert get_schedule(conn, 99999) is None
    finally:
        conn.close()


def test_upsert_schedule_allows_multiple_null_time_same_day():
    """함수 레이어에서 partial UNIQUE NULL 허용 행동 명시 — 시간 미지정 슬롯 여러 개 OK."""
    conn = _setup_db()
    try:
        from db import upsert_todo
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid1 = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=60)
        sid2 = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=90)
        conn.commit()
        assert sid1 != sid2
        rows = get_schedules_by_date(conn, "2026-04-28")
        assert len(rows) == 2
    finally:
        conn.close()


def test_delete_schedule_removes_row_and_cascades():
    """delete_schedule은 row 삭제 + actual은 CASCADE."""
    conn = _setup_db()
    try:
        from db import upsert_todo
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=60)
        conn.execute(
            "INSERT INTO todo_schedule_actuals (schedule_id, source_date, source_summary, source_repo, duration_min_snapshot) VALUES (?, ?, ?, ?, ?)",
            (sid, "2026-04-28", "task A", "repo X", 30),
        )
        conn.commit()
        deleted = delete_schedule(conn, sid)
        conn.commit()
        assert deleted is True
        assert get_schedule(conn, sid) is None
        rows = conn.execute(
            "SELECT * FROM todo_schedule_actuals WHERE schedule_id = ?", (sid,)
        ).fetchall()
        assert len(rows) == 0


    finally:
        conn.close()


def test_delete_schedule_missing_returns_false():
    """존재하지 않는 id 삭제 시 False 반환."""
    conn = _setup_db()
    try:
        assert delete_schedule(conn, 99999) is False
    finally:
        conn.close()


def test_link_schedule_actual_reads_from_tasks():
    """wrapper가 task에서 date/duration/summary/repo 자동 조회 → snapshot 저장."""
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, repo, duration_min) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-28", "구현", "implement X", "repo Y", 90),
        )
        task_id = cur.lastrowid
        actual_id = link_schedule_actual(conn, schedule_id=sid, task_id=task_id)
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM todo_schedule_actuals WHERE id = ?", (actual_id,)
        ).fetchall()
        assert len(rows) == 1
        a = dict(rows[0])
        assert a["source_date"] == "2026-04-28"
        assert a["source_summary"] == "implement X"
        assert a["source_repo"] == "repo Y"
        assert a["duration_min_snapshot"] == 90
        assert a["source_task_id"] == task_id
    finally:
        conn.close()


def test_link_schedule_actual_rejects_date_mismatch():
    """task.date != schedule.date면 ValueError."""
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, duration_min) VALUES (?, ?, ?, ?)",
            ("2026-04-27", "구현", "wrong day task", 60),
        )
        task_id = cur.lastrowid
        with pytest.raises(ValueError, match="date mismatch"):
            link_schedule_actual(conn, schedule_id=sid, task_id=task_id)
    finally:
        conn.close()


def test_link_schedule_actual_missing_schedule_raises():
    """존재하지 않는 schedule_id는 ValueError."""
    conn = _setup_db()
    try:
        with pytest.raises(ValueError, match="schedule_id"):
            link_schedule_actual(conn, schedule_id=99999, task_id=1)
    finally:
        conn.close()


def test_link_schedule_actual_missing_task_raises():
    """존재하지 않는 task_id는 ValueError."""
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        with pytest.raises(ValueError, match="task_id"):
            link_schedule_actual(conn, schedule_id=sid, task_id=99999)
    finally:
        conn.close()


def test_link_schedule_actual_unique_4tuple_violation():
    """같은 (schedule_id, source_date, source_summary, source_repo) 두 번 link 시 IntegrityError."""
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, repo, duration_min) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-28", "구현", "task A", "repo X", 30),
        )
        task_id_1 = cur.lastrowid
        link_schedule_actual(conn, schedule_id=sid, task_id=task_id_1)
        conn.commit()
        # 동일 summary/repo 가진 두 번째 task
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, repo, duration_min) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-28", "구현", "task A", "repo X", 30),
        )
        task_id_2 = cur.lastrowid
        with pytest.raises(sqlite3.IntegrityError):
            link_schedule_actual(conn, schedule_id=sid, task_id=task_id_2)
    finally:
        conn.close()


def test_get_daily_checkins_range_half_open():
    """[start, end) half-open range: end_date 당일 row는 포함 안 됨."""
    conn = _setup_db()
    try:
        from db import upsert_daily_checkin
        upsert_daily_checkin(conn, "2026-04-25", available_min=360, available_status="answered")
        upsert_daily_checkin(conn, "2026-04-26", available_min=240, available_status="answered")
        upsert_daily_checkin(conn, "2026-04-28", available_min=300, available_status="answered")
        conn.commit()
        rows = get_daily_checkins(conn, "2026-04-25", "2026-04-27")
        dates = [r["date"] for r in rows]
        assert dates == ["2026-04-25", "2026-04-26"]
    finally:
        conn.close()


def test_get_daily_checkins_empty_range():
    """범위에 row 없으면 빈 리스트."""
    conn = _setup_db()
    try:
        rows = get_daily_checkins(conn, "2026-04-01", "2026-04-10")
        assert rows == []
    finally:
        conn.close()


def test_get_daily_checkins_orders_asc():
    """삽입 순서와 무관하게 date ASC 정렬."""
    conn = _setup_db()
    try:
        from db import upsert_daily_checkin
        upsert_daily_checkin(conn, "2026-04-26", available_min=240, available_status="answered")
        upsert_daily_checkin(conn, "2026-04-25", available_min=360, available_status="answered")
        conn.commit()
        rows = get_daily_checkins(conn, "2026-04-20", "2026-04-30")
        assert [r["date"] for r in rows] == ["2026-04-25", "2026-04-26"]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# get_capacity_status
# ---------------------------------------------------------------------------

def test_capacity_status_under_budget():
    """planned_total < available_min → planned_overbook False, missing_budget False."""
    conn = _setup_db()
    try:
        from db import upsert_daily_checkin
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        upsert_daily_checkin(conn, "2026-04-28", available_min=300, available_status="answered")
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        conn.commit()
        st = get_capacity_status(conn, "2026-04-28")
        assert st["available_min"] == 300
        assert st["planned_min_total"] == 120
        assert st["planned_overbook"] is False
        assert st["missing_budget"] is False
        assert st["remaining_min"] == 180
    finally:
        conn.close()


def test_capacity_status_planned_overbook():
    """planned_total > available_min → planned_overbook True."""
    conn = _setup_db()
    try:
        from db import upsert_daily_checkin
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        upsert_daily_checkin(conn, "2026-04-28", available_min=120, available_status="answered")
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=180)
        conn.commit()
        st = get_capacity_status(conn, "2026-04-28")
        assert st["planned_overbook"] is True
        assert st["remaining_min"] == -60
    finally:
        conn.close()


def test_capacity_status_actual_overrun():
    """actual_total > available_min → actual_overrun True."""
    conn = _setup_db()
    try:
        from db import upsert_daily_checkin
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        upsert_daily_checkin(conn, "2026-04-28", available_min=100, available_status="answered")
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=60)
        conn.execute(
            "INSERT INTO tasks (date, tag, summary, repo, duration_min) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-28", "구현", "task A", "repo X", 150),
        )
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        link_schedule_actual(conn, schedule_id=sid, task_id=task_id)
        conn.commit()
        st = get_capacity_status(conn, "2026-04-28")
        assert st["actual_min_total"] == 150
        assert st["actual_overrun"] is True
    finally:
        conn.close()


def test_capacity_status_time_conflicts():
    """겹치는 시간 슬롯 두 개 → time_conflicts 1개, overlap_min 정확."""
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", start_at="14:00", end_at="16:00", planned_min=120)
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", start_at="15:30", end_at="17:00", planned_min=90)
        conn.commit()
        st = get_capacity_status(conn, "2026-04-28")
        assert len(st["time_conflicts"]) == 1
        assert st["time_conflicts"][0]["overlap_min"] == 30
    finally:
        conn.close()


def test_capacity_status_missing_budget():
    """schedule 있고 available_min NULL이면 missing_budget=True, remaining_min=None."""
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=60)
        conn.commit()
        st = get_capacity_status(conn, "2026-04-28")
        assert st["missing_budget"] is True
        assert st["available_status"] == "unknown"
        assert st["remaining_min"] is None
    finally:
        conn.close()


def test_capacity_status_no_schedules_no_conflict_no_missing():
    """schedule 없으면 time_conflicts 빈 리스트, missing_budget False."""
    conn = _setup_db()
    try:
        from db import upsert_daily_checkin
        upsert_daily_checkin(conn, "2026-04-28", available_min=300, available_status="answered")
        conn.commit()
        st = get_capacity_status(conn, "2026-04-28")
        assert st["planned_min_total"] == 0
        assert st["time_conflicts"] == []
        assert st["missing_budget"] is False
        assert st["schedules"] == []
    finally:
        conn.close()


def test_capacity_status_skipped_does_not_flag_missing_budget():
    """available_status='skipped' + schedule 있어도 missing_budget=False (의도적 skip)."""
    conn = _setup_db()
    try:
        from db import upsert_daily_checkin
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_min=None, available_status="skipped",
        )
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=60)
        conn.commit()
        st = get_capacity_status(conn, "2026-04-28")
        assert st["missing_budget"] is False
        assert st["available_status"] == "skipped"
    finally:
        conn.close()


def test_capacity_status_unknown_with_schedule_flags_missing_budget():
    """available_status='unknown' + schedule 있으면 missing_budget=True (대답 안 한 상태)."""
    conn = _setup_db()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        # daily_checkin 자체가 없어서 status="unknown" (default fallback)
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=60)
        conn.commit()
        st = get_capacity_status(conn, "2026-04-28")
        assert st["missing_budget"] is True
        assert st["available_status"] == "unknown"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Task 9: checkin_save.py wrapper tests
# ---------------------------------------------------------------------------

def test_checkin_save_morning_requires_value_or_skip(tmp_path):
    """morning subcommand: --available-hours 또는 --skip-available 둘 중 하나 필수."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/checkin_save.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run(
        ["python3", str(script), "morning", "--date", "2026-04-28"],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode != 0
    assert "available" in r.stderr.lower()


def test_checkin_save_morning_with_value_and_skips(tmp_path):
    import subprocess, os, json
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/checkin_save.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "morning", "--date", "2026-04-28",
        "--available-hours", "5", "--skip-energy", "--skip-blockers",
        "--morning-intent", "test",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["available_min"] == 300
    assert out["available_status"] == "answered"
    assert out["energy_status"] == "skipped"
    assert out["blockers_status"] == "skipped"
    assert out["morning_intent"] == "test"


def test_checkin_save_morning_mutual_exclusive(tmp_path):
    """--available-hours와 --skip-available 둘 다 → 에러."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/checkin_save.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "morning", "--date", "2026-04-28",
        "--available-hours", "5", "--skip-available",
        "--skip-energy", "--skip-blockers",
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "mutually exclusive" in r.stderr.lower() or "exclusive" in r.stderr.lower()


def test_checkin_save_evening(tmp_path):
    """evening subcommand: reflection만."""
    import subprocess, os, json
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/checkin_save.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "evening", "--date", "2026-04-28",
        "--evening-reflection", "good day",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["evening_reflection"] == "good day"


def test_checkin_save_morning_negative_hours_rejected(tmp_path):
    """음수 --available-hours는 sqlite IntegrityError 노출 전에 친절한 에러로 차단."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/checkin_save.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "morning", "--date", "2026-04-28",
        "--available-hours", "-1.5", "--skip-energy", "--skip-blockers",
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert ">= 0" in r.stderr or "must be" in r.stderr.lower()


def test_checkin_save_morning_invalid_wip_ids_rejected(tmp_path):
    """--wip-ids에 비-정수 값 → 친절한 에러."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/checkin_save.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "morning", "--date", "2026-04-28",
        "--skip-available", "--skip-energy", "--skip-blockers",
        "--wip-ids", "13,abc",
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "wip-ids" in r.stderr.lower() or "integer" in r.stderr.lower()


def test_checkin_save_morning_wip_ids_with_whitespace(tmp_path):
    """--wip-ids 공백/trailing 콤마 허용."""
    import subprocess, os, json
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/checkin_save.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "morning", "--date", "2026-04-28",
        "--skip-available", "--skip-energy", "--skip-blockers",
        "--wip-ids", "13, 20, ",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    # get_daily_checkin은 wip_ids를 존재하는 todo id만 morning_wip_ids에, 나머지는 missing_wip_ids에 반환.
    # 테스트 DB에 todo가 없으므로 13,20은 missing_wip_ids에 들어간다.
    stored = sorted((out.get("morning_wip_ids") or []) + (out.get("missing_wip_ids") or []))
    assert stored == [13, 20]


def test_schedule_upsert_minutes_only(tmp_path):
    """시간 미지정 — --planned-min만으로 schedule 저장."""
    import subprocess, os, json
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_upsert.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    # setup todo
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    # run script
    r = subprocess.run([
        "python3", str(script), "--todo-id", str(tid),
        "--date", "2026-04-28", "--planned-min", "120",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["schedule"]["planned_min"] == 120
    assert out["schedule"]["start_at"] is None
    assert "capacity_status" in out


def test_schedule_upsert_time_slot_auto_planned_min(tmp_path):
    """--start/--end 명시 시 planned_min 자동 계산."""
    import subprocess, os, json
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_upsert.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        tid = upsert_todo(conn, {"title": "t2", "done_definition": "d", "category": "업무"})
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "--todo-id", str(tid),
        "--date", "2026-04-28", "--start", "14:00", "--end", "16:00",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["schedule"]["planned_min"] == 120
    assert out["schedule"]["start_at"] == "14:00"


def test_schedule_upsert_planned_min_mismatch_rejected(tmp_path):
    """시간 슬롯 + 명시한 --planned-min이 end-start와 다르면 에러."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_upsert.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        tid = upsert_todo(conn, {"title": "t3", "done_definition": "d", "category": "업무"})
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "--todo-id", str(tid),
        "--date", "2026-04-28", "--start", "14:00", "--end", "16:00",
        "--planned-min", "100",
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "mismatch" in r.stderr.lower() or "!=" in r.stderr


def test_schedule_upsert_unpaired_time_rejected(tmp_path):
    """--start만 있고 --end 없으면 에러."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_upsert.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        tid = upsert_todo(conn, {"title": "t4", "done_definition": "d", "category": "업무"})
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "--todo-id", str(tid),
        "--date", "2026-04-28", "--start", "14:00", "--planned-min", "60",
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "paired" in r.stderr.lower() or "start" in r.stderr.lower()


def test_schedule_upsert_unique_violation_friendly_error(tmp_path):
    """동일 시간 슬롯 두 번 → 친절한 에러 (raw IntegrityError 아님)."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_upsert.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        tid = upsert_todo(conn, {"title": "t5", "done_definition": "d", "category": "업무"})
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    args = [
        "python3", str(script), "--todo-id", str(tid),
        "--date", "2026-04-28", "--start", "14:00", "--end", "16:00",
    ]
    r1 = subprocess.run(args, capture_output=True, text=True, env=env)
    assert r1.returncode == 0, r1.stderr
    r2 = subprocess.run(args, capture_output=True, text=True, env=env)
    assert r2.returncode != 0
    assert "constraint" in r2.stderr.lower() or "schedule" in r2.stderr.lower()


def test_schedule_actual_link_reads_task(tmp_path):
    """task에서 자동 snapshot."""
    import subprocess, os, json
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo, upsert_schedule
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, repo, duration_min) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-28", "구현", "task X", "repo Y", 90),
        )
        task_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "--schedule-id", str(sid),
        "--task-id", str(task_id), "--date", "2026-04-28", "--todo-id", str(tid),
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["actual"]["duration_min_snapshot"] == 90
    assert out["actual"]["source_summary"] == "task X"
    assert out["actual"]["source_repo"] == "repo Y"
    assert "capacity_status" in out


def test_schedule_actual_link_rejects_todo_id_mismatch(tmp_path):
    """schedule이 다른 todo_id에 속하면 거부."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo, upsert_schedule
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        t1 = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        t2 = upsert_todo(conn, {"title": "t2", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(conn, todo_id=t1, date="2026-04-28", planned_min=60)
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, duration_min) VALUES (?, ?, ?, ?)",
            ("2026-04-28", "구현", "task A", 60),
        )
        task_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "--schedule-id", str(sid),
        "--task-id", str(task_id), "--date", "2026-04-28", "--todo-id", str(t2),
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "todo" in r.stderr.lower() and "mismatch" in r.stderr.lower()


def test_schedule_actual_link_rejects_date_mismatch(tmp_path):
    """--date가 schedule.date와 다르면 거부."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo, upsert_schedule
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        tid = upsert_todo(conn, {"title": "t1", "done_definition": "d", "category": "업무"})
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=60)
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, duration_min) VALUES (?, ?, ?, ?)",
            ("2026-04-28", "구현", "task A", 60),
        )
        task_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "--schedule-id", str(sid),
        "--task-id", str(task_id), "--date", "2026-04-27", "--todo-id", str(tid),
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "date" in r.stderr.lower() and "mismatch" in r.stderr.lower()


def test_schedule_actual_link_missing_schedule(tmp_path):
    """존재하지 않는 schedule_id → 친절한 에러."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "--schedule-id", "99999",
        "--task-id", "1", "--date", "2026-04-28", "--todo-id", "1",
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "schedule_id" in r.stderr.lower() or "not found" in r.stderr.lower()


def test_capacity_script_markdown_output(tmp_path):
    """기본 markdown 표 출력."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/capacity.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_daily_checkin
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_min=300, available_status="answered",
            energy="mid", energy_status="answered",
        )
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "--start", "2026-04-28", "--end", "2026-04-29",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "| 날짜 |" in r.stdout
    assert "04-28" in r.stdout
    assert "5.0h" in r.stdout  # 300 min = 5.0h


def test_capacity_script_skipped_row(tmp_path):
    """skipped status는 ℹ skipped 표시."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/capacity.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_daily_checkin
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        upsert_daily_checkin(
            conn, "2026-04-27",
            available_min=None, available_status="skipped",
        )
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "--start", "2026-04-27", "--end", "2026-04-28",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "skipped" in r.stdout


def test_capacity_script_no_data(tmp_path):
    """범위에 row 없으면 친절한 메시지."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/capacity.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "--start", "2026-04-01", "--end", "2026-04-10",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0
    assert "no daily_checkins" in r.stdout.lower() or "(no" in r.stdout


def test_capacity_script_default_range_is_7_days(tmp_path):
    """기본 범위: today-6 ~ today+1 (half-open) → 약 7일."""
    import subprocess, os
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/capacity.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_daily_checkin
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    conn = get_conn()
    try:
        # today's checkin
        upsert_daily_checkin(
            conn, today.strftime("%Y-%m-%d"),
            available_min=240, available_status="answered",
        )
        # 7-days-ago — should NOT appear (today-6 is the start)
        old = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        upsert_daily_checkin(
            conn, old,
            available_min=180, available_status="answered",
        )
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run(["python3", str(script)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "4.0h" in r.stdout  # today's row
    assert "3.0h" not in r.stdout  # old row excluded


# ---------------------------------------------------------------------------
# Task 13: todo_crud.py — tri-state estimated_min on add + WIP gate
# ---------------------------------------------------------------------------

def test_todo_crud_add_requires_estimated_or_skip(tmp_path):
    """add는 --estimated-min OR --skip-estimated 필수."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/todo_crud.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "add",
        "--title", "t", "--done-definition", "d", "--category", "업무",
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "estimated" in r.stderr.lower()


def test_todo_crud_add_with_estimated_succeeds(tmp_path):
    """--estimated-min 명시하면 add 성공."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/todo_crud.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "add",
        "--title", "t1", "--done-definition", "d", "--category", "업무",
        "--estimated-min", "60",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


def test_todo_crud_add_with_skip_estimated_succeeds(tmp_path):
    """--skip-estimated만 있으면 add 성공 (estimated_min은 NULL로 저장)."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/todo_crud.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "add",
        "--title", "t2", "--done-definition", "d", "--category", "업무",
        "--skip-estimated",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


def test_todo_crud_add_mutually_exclusive(tmp_path):
    """--estimated-min과 --skip-estimated 둘 다 → 에러."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/todo_crud.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    r = subprocess.run([
        "python3", str(script), "add",
        "--title", "t3", "--done-definition", "d", "--category", "업무",
        "--estimated-min", "60", "--skip-estimated",
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "exclusive" in r.stderr.lower()


def test_todo_crud_move_wip_blocks_when_estimated_null(tmp_path):
    """estimated_min NULL인 todo를 wip로 옮길 때 에러 (override 옵션 없으면)."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/todo_crud.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        tid = upsert_todo(conn, {"title": "x", "done_definition": "d", "category": "업무"})
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "move", "--id", str(tid), "--status", "wip",
    ], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "estimated" in r.stderr.lower()


def test_todo_crud_move_wip_with_override_succeeds(tmp_path):
    """--skip-estimated-check 명시하면 estimated_min NULL이어도 wip 전환 허용."""
    import subprocess, os
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/todo_crud.py"
    db_path = tmp_path / "test.db"
    env = {**os.environ, "LIFE_DASHBOARD_DB": str(db_path)}
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    os.environ["LIFE_DASHBOARD_DB"] = str(db_path)
    conn = get_conn()
    try:
        tid = upsert_todo(conn, {"title": "y", "done_definition": "d", "category": "업무"})
        conn.commit()
    finally:
        conn.close()
    del os.environ["LIFE_DASHBOARD_DB"]
    r = subprocess.run([
        "python3", str(script), "move", "--id", str(tid), "--status", "wip",
        "--skip-estimated-check",
    ], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
