"""tasks + projects CRUD 테스트."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db import upsert_session, update_daily_stats, get_conn


def _setup_db():
    """인메모리 DB에 스키마 로드."""
    schema = (Path(__file__).resolve().parent.parent / "schema.sql").read_text()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema)
    return conn


def test_upsert_project_and_get():
    from db import upsert_project, get_projects
    conn = _setup_db()
    pid = upsert_project(conn, "Juliet 운영 자동화", repo="dy-minions-squad")
    conn.commit()
    projects = get_projects(conn)
    assert len(projects) == 1
    assert projects[0]["name"] == "Juliet 운영 자동화"
    assert projects[0]["id"] == pid

    # 같은 name+repo → 기존 id 반환 (UNIQUE 보장)
    pid2 = upsert_project(conn, "Juliet 운영 자동화", repo="dy-minions-squad")
    assert pid2 == pid
    conn.close()


def test_upsert_project_different_repo():
    from db import upsert_project, get_projects
    conn = _setup_db()
    pid1 = upsert_project(conn, "에러 수정", repo="cube-backend")
    pid2 = upsert_project(conn, "에러 수정", repo="dy-minions-squad")
    conn.commit()
    assert pid1 != pid2
    assert len(get_projects(conn)) == 2
    conn.close()


def test_upsert_tasks_and_get():
    from db import upsert_tasks, get_tasks
    conn = _setup_db()
    tasks = [
        {
            "tag": "설계",
            "summary": "Juliet cron 점검",
            "repo": "dy-minions-squad",
            "segments": [
                {"sid": "be72d12a", "date": "2026-03-31", "start": "11:27", "end": "11:56", "dur": 29},
                {"sid": "dc9eaa53", "date": "2026-03-31", "start": "12:16", "end": "13:47", "dur": 67},
            ],
            "duration_min": 96,
            "status": "completed",
        },
        {
            "tag": "코딩",
            "summary": "Agent Budget Cap 구현",
            "repo": "dy-minions-squad",
            "segments": [
                {"sid": "8c5ade26", "date": "2026-03-31", "start": "11:40", "end": "14:44", "dur": 103},
            ],
            "duration_min": 103,
            "status": "completed",
        },
    ]
    upsert_tasks(conn, "2026-03-31", tasks)
    conn.commit()

    result = get_tasks(conn, "2026-03-31")
    assert len(result) == 2
    assert result[0]["tag"] == "설계"
    assert result[0]["duration_min"] == 96
    segs = json.loads(result[0]["segments"])
    assert len(segs) == 2
    assert segs[0]["sid"] == "be72d12a"
    conn.close()


def test_upsert_tasks_replaces():
    from db import upsert_tasks, get_tasks
    conn = _setup_db()
    upsert_tasks(conn, "2026-03-31", [
        {"tag": "코딩", "summary": "첫 번째", "segments": [], "duration_min": 10},
    ])
    upsert_tasks(conn, "2026-03-31", [
        {"tag": "설계", "summary": "두 번째", "segments": [], "duration_min": 20},
    ])
    conn.commit()
    result = get_tasks(conn, "2026-03-31")
    assert len(result) == 1
    assert result[0]["summary"] == "두 번째"
    conn.close()


def test_tasks_with_project():
    from db import upsert_project, upsert_tasks, get_tasks
    conn = _setup_db()
    pid = upsert_project(conn, "Juliet", repo="dy-minions-squad")
    upsert_tasks(conn, "2026-03-31", [
        {"tag": "설계", "summary": "Juliet 작업", "segments": [], "duration_min": 50, "project_id": pid},
    ])
    conn.commit()
    result = get_tasks(conn, "2026-03-31")
    assert result[0]["project_id"] == pid
    conn.close()
