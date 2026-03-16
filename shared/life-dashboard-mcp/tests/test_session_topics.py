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
