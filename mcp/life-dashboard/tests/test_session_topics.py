"""session_topics CRUD 테스트."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db import upsert_session, upsert_session_topics, get_session_topics, update_daily_stats


def _setup_db():
    """인메모리 DB에 스키마 로드."""
    schema = (Path(__file__).resolve().parent.parent / "schema.sql").read_text()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema)
    return conn


def _insert_session(conn, source="cc", session_id="test-123", date="2026-03-16"):
    """테스트용 세션 삽입."""
    upsert_session(conn, {
        "source": source, "session_id": session_id, "date": date,
        "repo": "test-repo", "branch": None, "tag": "코딩",
        "summary": "test summary", "summary_source": "llm",
        "status": "completed", "follow_up": None,
        "start_at": f"{date}T10:00:00+09:00", "end_at": f"{date}T12:00:00+09:00",
        "duration_min": 120, "file_count": 5, "error_count": 0,
        "has_tests": 1, "has_commits": 1, "token_total": 50000,
    })


def test_upsert_and_get():
    conn = _setup_db()
    _insert_session(conn)
    topics = [
        {"tag": "설계", "summary": "spec 작성", "repo": "test-repo", "duration_estimate_min": 60},
        {"tag": "코딩", "summary": "구현", "repo": "test-repo", "duration_estimate_min": 60},
    ]
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16", topics)
    result = get_session_topics(conn, "2026-03-16")
    assert len(result) == 2
    assert result[0]["tag"] == "설계"
    assert result[1]["tag"] == "코딩"
    assert result[0]["topic_order"] == 0
    assert result[1]["topic_order"] == 1


def test_upsert_replaces():
    """전체 교체 동작 확인."""
    conn = _setup_db()
    _insert_session(conn)
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16",
        [{"tag": "설계", "summary": "v1", "repo": "r"}])
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16",
        [{"tag": "코딩", "summary": "v2", "repo": "r"}, {"tag": "리뷰", "summary": "v2b", "repo": "r"}])
    result = get_session_topics(conn, "2026-03-16")
    assert len(result) == 2
    assert result[0]["summary"] == "v2"


def test_cascade_delete():
    """세션 삭제 시 토픽도 삭제."""
    conn = _setup_db()
    _insert_session(conn)
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16",
        [{"tag": "코딩", "summary": "test", "repo": "r"}])
    conn.execute("DELETE FROM sessions WHERE session_id = 'test-123'")
    result = get_session_topics(conn, "2026-03-16")
    assert len(result) == 0


def test_get_empty():
    """토픽 없는 날짜."""
    conn = _setup_db()
    result = get_session_topics(conn, "2026-03-16")
    assert result == []


def test_update_daily_stats_with_topics():
    """update_daily_stats가 토픽 기준 tag_breakdown 생성."""
    conn = _setup_db()
    _insert_session(conn)
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16", [
        {"tag": "설계", "summary": "s1", "repo": "r"},
        {"tag": "코딩", "summary": "s2", "repo": "r"},
        {"tag": "코딩", "summary": "s3", "repo": "r"},
    ])
    update_daily_stats(conn, "2026-03-16")
    row = conn.execute("SELECT tag_breakdown FROM daily_stats WHERE date = '2026-03-16'").fetchone()
    tags = json.loads(row["tag_breakdown"])
    assert tags["설계"] == 1
    assert tags["코딩"] == 2


def test_update_daily_stats_fallback_no_topics():
    """토픽 없으면 sessions.tag로 폴백."""
    conn = _setup_db()
    _insert_session(conn)  # tag="코딩", no topics
    update_daily_stats(conn, "2026-03-16")
    row = conn.execute("SELECT tag_breakdown FROM daily_stats WHERE date = '2026-03-16'").fetchone()
    tags = json.loads(row["tag_breakdown"])
    assert tags["코딩"] == 1


def test_invalid_tag_normalized():
    """유효하지 않은 tag는 기타로 정규화."""
    conn = _setup_db()
    _insert_session(conn)
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16",
        [{"tag": "INVALID_TAG", "summary": "test", "repo": "r"}])
    result = get_session_topics(conn, "2026-03-16")
    assert result[0]["tag"] == "기타"


def test_empty_summary_skipped():
    """빈 summary 토픽은 스킵."""
    conn = _setup_db()
    _insert_session(conn)
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16", [
        {"tag": "코딩", "summary": "", "repo": "r"},
        {"tag": "코딩", "summary": None, "repo": "r"},
        {"tag": "설계", "summary": "valid", "repo": "r"},
    ])
    result = get_session_topics(conn, "2026-03-16")
    assert len(result) == 1
    assert result[0]["summary"] == "valid"


def test_all_invalid_no_delete():
    """모든 토픽이 무효하면 기존 데이터 유지 (DELETE 안 함)."""
    conn = _setup_db()
    _insert_session(conn)
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16",
        [{"tag": "코딩", "summary": "existing", "repo": "r"}])
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16",
        [{"tag": "코딩", "summary": "", "repo": "r"}])
    result = get_session_topics(conn, "2026-03-16")
    assert len(result) == 1
    assert result[0]["summary"] == "existing"


def test_sync_session_cache():
    """토픽 저장 시 sessions.summary/tag 캐시 갱신."""
    conn = _setup_db()
    _insert_session(conn)
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16",
        [{"tag": "설계", "summary": "new summary", "repo": "r"}])
    row = conn.execute(
        "SELECT tag, summary, summary_source FROM sessions WHERE session_id='test-123'"
    ).fetchone()
    assert row["tag"] == "설계"
    assert row["summary"] == "new summary"
    assert row["summary_source"] == "llm"


def test_merge_intervals_hhmm():
    """_merge_intervals_minutes가 HH:MM 형식도 처리."""
    from db import _merge_intervals_minutes
    # HH:MM 형식 — date_str 제공 시 정상 계산
    result = _merge_intervals_minutes(
        [("10:00", "11:30"), ("11:00", "12:00")],
        date_str="2026-03-17",
    )
    assert result == 120  # 10:00~12:00 = 120분 (겹침 병합)


def test_merge_intervals_hhmm_no_date():
    """date_str 없이 HH:MM이면 0 반환 (파싱 불가)."""
    from db import _merge_intervals_minutes
    result = _merge_intervals_minutes([("10:00", "11:00")])
    assert result == 0


def test_upsert_topics_normalizes_hhmm():
    """upsert_session_topics가 HH:MM을 ISO로 변환하여 저장."""
    conn = _setup_db()
    _insert_session(conn)
    upsert_session_topics(conn, "cc", "test-123", "2026-03-16", [
        {"tag": "코딩", "summary": "work", "start_at": "10:05", "end_at": "11:30"},
    ])
    row = conn.execute(
        "SELECT start_at, end_at FROM session_topics WHERE date='2026-03-16'"
    ).fetchone()
    assert row["start_at"] == "2026-03-16T10:05:00"
    assert row["end_at"] == "2026-03-16T11:30:00"


def test_daily_stats_work_hours_uses_session_intervals():
    """work_hours는 세션 구간 병합으로 계산 (토픽이 아닌 세션 기준)."""
    conn = _setup_db()
    _insert_session(conn)  # 10:00~12:00 = 120분
    # 토픽이 있어도 work_hours는 세션 기준
    conn.execute(
        "INSERT INTO session_topics (source, session_id, date, topic_order, tag, summary, start_at, end_at, duration_estimate_min, status)"
        " VALUES ('cc','test-123','2026-03-16',0,'코딩','work','10:00','11:30',90,'completed')"
    )
    update_daily_stats(conn, "2026-03-16")
    row = conn.execute("SELECT work_hours FROM daily_stats WHERE date='2026-03-16'").fetchone()
    assert row["work_hours"] == 2.0  # 세션 10:00~12:00 = 120분


def test_daily_stats_ignores_topic_intervals_for_work_hours():
    """work_hours는 토픽 구간이 아닌 sessions.duration_min 합산."""
    conn = _setup_db()
    _insert_session(conn)  # duration_min=120
    # 토픽이 있어도 work_hours는 duration_min 기준
    conn.execute(
        "INSERT INTO session_topics (source, session_id, date, topic_order, tag, summary, start_at, end_at, duration_estimate_min, status)"
        " VALUES ('cc','test-123','2026-03-16',0,'ops','short','2026-03-16T00:00:00','2026-03-16T00:01:00',1,'completed')"
    )
    update_daily_stats(conn, "2026-03-16")
    row = conn.execute("SELECT work_hours FROM daily_stats WHERE date='2026-03-16'").fetchone()
    # session duration_min=120 → 2.0h
    assert row["work_hours"] == 2.0


def test_daily_stats_parallel_sessions():
    """병렬 세션의 work_hours는 duration_min 합산."""
    conn = _setup_db()
    upsert_session(conn, {
        "source": "cc", "session_id": "s1", "date": "2026-03-16",
        "repo": "r", "branch": None, "tag": "코딩",
        "summary": "a", "summary_source": "llm",
        "status": "completed", "follow_up": None,
        "start_at": "2026-03-16T10:00:00+09:00", "end_at": "2026-03-16T12:00:00+09:00",
        "duration_min": 120, "file_count": 0, "error_count": 0,
        "has_tests": 0, "has_commits": 0, "token_total": 0,
    })
    upsert_session(conn, {
        "source": "cc", "session_id": "s2", "date": "2026-03-16",
        "repo": "r", "branch": None, "tag": "코딩",
        "summary": "b", "summary_source": "llm",
        "status": "completed", "follow_up": None,
        "start_at": "2026-03-16T11:00:00+09:00", "end_at": "2026-03-16T13:00:00+09:00",
        "duration_min": 120, "file_count": 0, "error_count": 0,
        "has_tests": 0, "has_commits": 0, "token_total": 0,
    })
    update_daily_stats(conn, "2026-03-16")
    row = conn.execute("SELECT work_hours FROM daily_stats WHERE date='2026-03-16'").fetchone()
    # min(duration합 240, wall 10:00~13:00=180) = 180min = 3.0h
    assert row["work_hours"] == 3.0


if __name__ == "__main__":
    passed = failed = 0
    for name, func in list(globals().items()):
        if name.startswith("test_"):
            try:
                func()
                print(f"  PASS {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(failed)
