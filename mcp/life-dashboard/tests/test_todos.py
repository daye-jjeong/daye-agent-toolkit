"""todos + daily_checkins CRUD 테스트."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


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
    import pytest
    from db import upsert_todo, update_todo_status
    conn = _setup_db()
    tid = upsert_todo(conn, {"title": "준비 안 됨"})  # done_definition null
    conn.commit()
    with pytest.raises(ValueError, match="done_definition"):
        update_todo_status(conn, tid, "wip")
    conn.close()


def test_update_todo_status_wip_limit():
    import pytest
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
    import pytest
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
    import pytest
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
    import pytest
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
