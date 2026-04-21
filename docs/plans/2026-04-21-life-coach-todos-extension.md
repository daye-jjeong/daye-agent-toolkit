# Life-Coach Todos Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** life-coach에 개인 todo 관리 축을 추가한다 — `todos` / `daily_checkins` 테이블 + CRUD + 아침/저녁 액션 + 이번 분기 backlog 초기화.

**Architecture:** `mcp/life-dashboard/schema.sql`에 todos/daily_checkins 테이블 추가 → `db.py`에 CRUD + 검증 함수 8개 → `life-coach/scripts/`에 순수 CLI 3종 (`todo_crud.py`, `todo_morning.py`, `todo_evening.py`) → SKILL.md 재구성 (축 1 액션 / 축 2 분석) → backlog 초기화. Claude 세션이 대화를, 스크립트가 data I/O + business rule 검증을 담당한다.

**Tech Stack:** Python 3.12, SQLite (WAL), pytest, zoneinfo

**Spec:** `docs/plans/2026-04-21-life-coach-todos-extension-design.md`

**Timebox:** 2026-04-21(월) ~ 2026-04-27(일). 실패 시 lean 대안(노션 1페이지 + Claude 대화).

---

## 사전 조건 (구현 시작 전 반드시 수행)

현재 세션은 `main` 브랜치에서 설계 문서만 작성함. 코드 수정은 **worktree에서만**.

- [ ] **Step A: worktree 생성**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit
git worktree add -b feat/life-coach-todos ../daye-agent-toolkit-todos main
cd ../daye-agent-toolkit-todos
npm ci 2>/dev/null || true  # node 프로젝트 아니면 skip
```

- [ ] **Step B: LSP 정상화 (선택)**

```bash
code --add "$(pwd)"  # 선택 — VS Code 쓰면
```

- [ ] **Step C: 확인**

```bash
git branch --show-current
# expected: feat/life-coach-todos
git log -1 --oneline
# expected: 가장 최근 main 커밋
```

이후 모든 Task는 이 worktree 안에서 수행.

---

## 파일 구조

| 파일 | 역할 | 변경 |
|------|------|------|
| `mcp/life-dashboard/schema.sql` | DB 스키마 | todos + daily_checkins 테이블 추가 |
| `mcp/life-dashboard/db.py` | DB 접근 레이어 | `_migrate` 확장 + 함수 8개 추가 |
| `mcp/life-dashboard/tests/test_todos.py` | 테스트 | 신규 |
| `plugins/life-management/skills/life-coach/scripts/todo_crud.py` | 순수 CLI (add/list/show/move/defer/done) | 신규 |
| `plugins/life-management/skills/life-coach/scripts/todo_morning.py` | 아침 액션 — JSON 출력 | 신규 |
| `plugins/life-management/skills/life-coach/scripts/todo_evening.py` | 저녁 액션 — work-digest 호출 + JSON 출력 | 신규 |
| `plugins/life-management/skills/life-coach/SKILL.md` | 스킬 가이드 | 재구성 (축 1/축 2 분리, 자동 cron 폐기) |
| `plugins/life-management/skills/life-coach/references/cli-reference.md` | CLI 레퍼런스 | 신규 3개 스크립트 섹션 추가 |

---

### Task 1: 스키마 + DB 함수 (todos, daily_checkins)

**Files:**
- Modify: `mcp/life-dashboard/schema.sql` (tasks 테이블 바로 뒤, 라인 130 근처)
- Modify: `mcp/life-dashboard/db.py` (`_migrate` 확장 + 함수 추가)
- Create: `mcp/life-dashboard/tests/test_todos.py`

- [ ] **Step 1: test_todos.py — 기본 CRUD 테스트 작성**

파일 생성: `mcp/life-dashboard/tests/test_todos.py`

```python
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
```

- [ ] **Step 2: test_todos.py — WIP limit + Done 정의 의무 테스트 추가**

같은 파일 아래에 이어서 추가:

```python
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
```

- [ ] **Step 3: test_todos.py — 쿼리 함수 테스트 (overdue, this_week, sort) 추가**

```python
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
```

- [ ] **Step 4: test_todos.py — daily_checkins 테스트 추가**

```python
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
```

- [ ] **Step 5: 테스트 실행 — FAIL 확인**

```bash
python3 -m pytest mcp/life-dashboard/tests/test_todos.py -v
```
Expected: 전부 FAIL — `upsert_todo`, `get_todo`, `update_todo_status`, `get_overdue_todos`, `get_due_this_week_todos`, `upsert_daily_checkin`, `get_daily_checkin` 없음

- [ ] **Step 6: schema.sql에 todos + daily_checkins 추가**

`mcp/life-dashboard/schema.sql`의 `tasks` 테이블 블록(`CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);` 바로 뒤)에 아래 삽입:

```sql

-- ── Todos (prospective, 사용자 관리 할일) ───────

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    done_definition TEXT,
    status TEXT NOT NULL DEFAULT 'backlog',
    priority INTEGER,
    project_id INTEGER,
    parent_id INTEGER,
    category TEXT,
    quarter TEXT,
    deadline TEXT,
    estimated_min INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    started_at TEXT,
    done_at TEXT,
    deferred_reason TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (parent_id) REFERENCES todos(id)
);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_deadline ON todos(deadline);
CREATE INDEX IF NOT EXISTS idx_todos_category ON todos(category);
CREATE INDEX IF NOT EXISTS idx_todos_parent ON todos(parent_id);

-- ── Daily Checkins (매일 아침/저녁 의식 기록) ──

CREATE TABLE IF NOT EXISTS daily_checkins (
    date TEXT PRIMARY KEY,
    morning_wip_ids TEXT,
    morning_intent TEXT,
    evening_reflection TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

- [ ] **Step 7: db.py `_migrate` 확장 — todos/daily_checkins 자동 생성**

`mcp/life-dashboard/db.py`의 `_migrate` 함수 끝(daily_stats summary 처리 뒤, 라인 87 근처)에 추가:

```python
    # todos + daily_checkins 테이블 마이그레이션
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "todos" not in existing:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done_definition TEXT,
                status TEXT NOT NULL DEFAULT 'backlog',
                priority INTEGER,
                project_id INTEGER,
                parent_id INTEGER,
                category TEXT,
                quarter TEXT,
                deadline TEXT,
                estimated_min INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                started_at TEXT,
                done_at TEXT,
                deferred_reason TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (parent_id) REFERENCES todos(id)
            );
            CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
            CREATE INDEX IF NOT EXISTS idx_todos_deadline ON todos(deadline);
            CREATE INDEX IF NOT EXISTS idx_todos_category ON todos(category);
            CREATE INDEX IF NOT EXISTS idx_todos_parent ON todos(parent_id);
        """)
        conn.commit()
    if "daily_checkins" not in existing:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS daily_checkins (
                date TEXT PRIMARY KEY,
                morning_wip_ids TEXT,
                morning_intent TEXT,
                evening_reflection TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
        """)
        conn.commit()
```

- [ ] **Step 8: db.py에 todos/daily_checkins 함수 8개 추가**

`mcp/life-dashboard/db.py`의 `get_tasks` 함수 뒤(라인 369 근처)에 아래 블록 삽입:

```python
# ── Todos + Daily Checkins ───────────────────────────

_VALID_TODO_STATUS = {"backlog", "wip", "done", "blocked", "deferred"}
_WIP_LIMIT = 2


def upsert_todo(conn: sqlite3.Connection, data: dict) -> int:
    """todos INSERT or UPDATE (id 있으면 UPDATE). id 반환.

    필수: title. 기본: status='backlog'.
    """
    if not data.get("title"):
        raise ValueError("title is required")

    status = data.get("status", "backlog")
    if status not in _VALID_TODO_STATUS:
        raise ValueError(f"invalid status: {status}")

    if data.get("id"):
        todo_id = data["id"]
        conn.execute("""
            UPDATE todos SET
                title = :title,
                done_definition = :done_definition,
                status = :status,
                priority = :priority,
                project_id = :project_id,
                parent_id = :parent_id,
                category = :category,
                quarter = :quarter,
                deadline = :deadline,
                estimated_min = :estimated_min,
                notes = :notes
            WHERE id = :id
        """, {
            "id": todo_id,
            "title": data["title"],
            "done_definition": data.get("done_definition"),
            "status": status,
            "priority": data.get("priority"),
            "project_id": data.get("project_id"),
            "parent_id": data.get("parent_id"),
            "category": data.get("category"),
            "quarter": data.get("quarter"),
            "deadline": data.get("deadline"),
            "estimated_min": data.get("estimated_min"),
            "notes": data.get("notes"),
        })
        return todo_id

    cursor = conn.execute("""
        INSERT INTO todos (
            title, done_definition, status, priority, project_id, parent_id,
            category, quarter, deadline, estimated_min, notes
        )
        VALUES (
            :title, :done_definition, :status, :priority, :project_id, :parent_id,
            :category, :quarter, :deadline, :estimated_min, :notes
        )
    """, {
        "title": data["title"],
        "done_definition": data.get("done_definition"),
        "status": status,
        "priority": data.get("priority"),
        "project_id": data.get("project_id"),
        "parent_id": data.get("parent_id"),
        "category": data.get("category"),
        "quarter": data.get("quarter"),
        "deadline": data.get("deadline"),
        "estimated_min": data.get("estimated_min"),
        "notes": data.get("notes"),
    })
    return cursor.lastrowid  # type: ignore[return-value]


def get_todo(conn: sqlite3.Connection, todo_id: int) -> dict | None:
    """단일 todo 반환. subtasks(JSON list)도 포함."""
    row = conn.execute("""
        SELECT t.*, p.name as project_name
        FROM todos t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.id = ?
    """, (todo_id,)).fetchone()
    if not row:
        return None
    t = dict(row)
    subtasks = conn.execute(
        "SELECT id, title, status, done_at FROM todos WHERE parent_id = ? ORDER BY id",
        (todo_id,),
    ).fetchall()
    t["subtasks"] = [dict(s) for s in subtasks]
    return t


def get_todos(
    conn: sqlite3.Connection,
    status: str | None = None,
    category: str | None = None,
    sort: str = "default",
) -> list[dict]:
    """todos 목록 조회. status/category 필터 지원.

    sort="default": deadline 있는 것 먼저, 임박 순, priority 높은 순, created_at 순.
    """
    clauses = []
    params: list = []
    if status:
        clauses.append("t.status = ?")
        params.append(status)
    if category:
        clauses.append("t.category = ?")
        params.append(category)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""

    if sort == "default":
        order = """
            ORDER BY
                CASE WHEN t.deadline IS NULL THEN 1 ELSE 0 END,
                t.deadline ASC,
                CASE WHEN t.priority IS NULL THEN 99 ELSE t.priority END ASC,
                t.created_at ASC
        """
    elif sort == "priority":
        order = "ORDER BY CASE WHEN t.priority IS NULL THEN 99 ELSE t.priority END ASC, t.created_at ASC"
    elif sort == "deadline":
        order = "ORDER BY CASE WHEN t.deadline IS NULL THEN 1 ELSE 0 END, t.deadline ASC, t.created_at ASC"
    else:
        order = "ORDER BY t.id"

    sql = f"""
        SELECT t.*, p.name as project_name
        FROM todos t
        LEFT JOIN projects p ON t.project_id = p.id
        {where}
        {order}
    """
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_todo_status(
    conn: sqlite3.Connection,
    todo_id: int,
    new_status: str,
    reason: str | None = None,
    force: bool = False,
) -> None:
    """status 전환 + 검증 + timestamp 자동 세팅.

    규칙:
    - WIP 전환: 이미 wip 2개면 거부 (force=True로 무시 가능, stderr 로그)
    - WIP 전환: done_definition 없으면 거부
    - backlog→wip: started_at 세팅
    - *→done: done_at 세팅
    - deferred: deferred_reason 저장
    """
    if new_status not in _VALID_TODO_STATUS:
        raise ValueError(f"invalid status: {new_status}")

    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if not row:
        raise ValueError(f"todo {todo_id} not found")

    if new_status == "wip":
        if not row["done_definition"]:
            raise ValueError(
                f"todo {todo_id}: done_definition is required before WIP transition"
            )
        current_wip = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE status = 'wip' AND id != ?",
            (todo_id,),
        ).fetchone()[0]
        if current_wip >= _WIP_LIMIT and not force:
            raise ValueError(
                f"WIP limit {_WIP_LIMIT} exceeded (current: {current_wip}). Use force=True to override."
            )
        if current_wip >= _WIP_LIMIT and force:
            print(
                f"[warn] WIP limit exceeded via force flag (now {current_wip + 1})",
                file=sys.stderr,
            )

    fields = ["status = :status"]
    params: dict = {"id": todo_id, "status": new_status}

    # backlog/blocked → wip 전환: started_at 세팅 (wip/deferred에서 다시 wip로는 started_at 유지)
    if new_status == "wip" and row["started_at"] is None:
        fields.append("started_at = datetime('now','localtime')")

    if new_status == "done":
        fields.append("done_at = datetime('now','localtime')")

    if new_status == "deferred":
        fields.append("deferred_reason = :reason")
        params["reason"] = reason

    set_clause = ", ".join(fields)
    conn.execute(f"UPDATE todos SET {set_clause} WHERE id = :id", params)


def get_overdue_todos(conn: sqlite3.Connection, as_of_date: str) -> list[dict]:
    """deadline이 as_of_date 이전이고 status NOT IN (done, deferred)인 todos."""
    rows = conn.execute("""
        SELECT t.*, p.name as project_name
        FROM todos t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.deadline IS NOT NULL
          AND DATE(t.deadline) < DATE(?)
          AND t.status NOT IN ('done', 'deferred')
        ORDER BY t.deadline ASC
    """, (as_of_date,)).fetchall()
    return [dict(r) for r in rows]


def get_due_this_week_todos(conn: sqlite3.Connection, as_of_date: str) -> list[dict]:
    """deadline이 as_of_date+1 ~ as_of_date+7인 todos (오늘 제외)."""
    rows = conn.execute("""
        SELECT t.*, p.name as project_name
        FROM todos t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.deadline IS NOT NULL
          AND DATE(t.deadline) > DATE(?)
          AND DATE(t.deadline) <= DATE(?, '+7 days')
          AND t.status NOT IN ('done', 'deferred')
        ORDER BY t.deadline ASC
    """, (as_of_date, as_of_date)).fetchall()
    return [dict(r) for r in rows]


def upsert_daily_checkin(
    conn: sqlite3.Connection,
    date: str,
    *,
    morning_wip_ids: list[int] | None = None,
    morning_intent: str | None = None,
    evening_reflection: str | None = None,
) -> None:
    """daily_checkin upsert. 제공된 필드만 UPDATE (COALESCE)."""
    wip_json = json.dumps(morning_wip_ids) if morning_wip_ids is not None else None
    conn.execute("""
        INSERT INTO daily_checkins (date, morning_wip_ids, morning_intent, evening_reflection)
        VALUES (:date, :wip, :intent, :reflection)
        ON CONFLICT(date) DO UPDATE SET
            morning_wip_ids = COALESCE(excluded.morning_wip_ids, morning_wip_ids),
            morning_intent = COALESCE(excluded.morning_intent, morning_intent),
            evening_reflection = COALESCE(excluded.evening_reflection, evening_reflection),
            updated_at = datetime('now','localtime')
    """, {
        "date": date,
        "wip": wip_json,
        "intent": morning_intent,
        "reflection": evening_reflection,
    })


def get_daily_checkin(conn: sqlite3.Connection, date: str) -> dict | None:
    """daily_checkin 조회. morning_wip_ids 무결성 검증 (missing_wip_ids 분리)."""
    row = conn.execute(
        "SELECT * FROM daily_checkins WHERE date = ?", (date,)
    ).fetchone()
    if not row:
        return None
    ck = dict(row)

    wip_raw = ck.get("morning_wip_ids")
    wip_ids = json.loads(wip_raw) if wip_raw else []
    missing: list[int] = []
    valid: list[int] = []
    if wip_ids:
        placeholders = ",".join("?" * len(wip_ids))
        existing = {
            r[0]
            for r in conn.execute(
                f"SELECT id FROM todos WHERE id IN ({placeholders})", wip_ids
            ).fetchall()
        }
        for tid in wip_ids:
            if tid in existing:
                valid.append(tid)
            else:
                missing.append(tid)
    ck["morning_wip_ids"] = valid
    ck["missing_wip_ids"] = missing
    return ck
```

참고: `sys` import가 필요하면 `db.py` 상단에 `import sys` 추가 (이미 있으면 skip — 현재 db.py는 `sqlite3`, `json`, `re` 등만 import).

- [ ] **Step 9: db.py 상단에 `import sys` 추가 (없으면)**

```python
# db.py 상단, 다른 import 근처에 추가
import sys
```

- [ ] **Step 10: 테스트 실행 — PASS 확인**

```bash
python3 -m pytest mcp/life-dashboard/tests/test_todos.py -v
```
Expected: 모든 테스트 PASS. FAIL이 있으면 수정 후 재실행.

- [ ] **Step 11: 기존 테스트 회귀 확인**

```bash
python3 -m pytest mcp/life-dashboard/tests/ -v
```
Expected: 기존 `test_tasks.py`, `test_session_topics.py` 전부 통과.

- [ ] **Step 12: 커밋**

```bash
git add mcp/life-dashboard/schema.sql mcp/life-dashboard/db.py mcp/life-dashboard/tests/test_todos.py
git commit -m "feat(life-dashboard): add todos + daily_checkins tables + CRUD functions

- schema.sql에 todos, daily_checkins 테이블 추가 (tasks와 축 분리: prospective)
- db.py에 upsert_todo, get_todo, get_todos, update_todo_status 추가
- WIP limit 2 + Done 정의 의무 검증 포함
- get_overdue_todos, get_due_this_week_todos 추가
- upsert_daily_checkin, get_daily_checkin (morning_wip_ids 무결성 검증 포함)
- _migrate에 자동 마이그레이션 추가"
```

---

### Task 2: `todo_crud.py` — 순수 CLI

**Files:**
- Create: `plugins/life-management/skills/life-coach/scripts/todo_crud.py`

스크립트는 순수 CLI. 대화 없음. stdout JSON + stderr 에러.

- [ ] **Step 1: todo_crud.py 골격 + argparse 작성**

파일 생성: `plugins/life-management/skills/life-coach/scripts/todo_crud.py`

```python
#!/usr/bin/env python3
"""todo CRUD CLI — 순수 one-shot. 대화 없음.

Usage:
    python3 todo_crud.py add --title "..." [--done-definition "..."] [--category ...] ...
    python3 todo_crud.py list [--status backlog] [--category 업무] [--sort default]
    python3 todo_crud.py show --id N
    python3 todo_crud.py move --id N --status wip [--reason "..."] [--force]
    python3 todo_crud.py defer --id N --reason "..."
    python3 todo_crud.py done --id N
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "mcp" / "life-dashboard"))
from db import (
    get_conn, upsert_todo, get_todo, get_todos, update_todo_status, upsert_project,
)


def _print_json(obj) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


def cmd_add(args):
    data = {
        "title": args.title,
        "done_definition": args.done_definition,
        "category": args.category,
        "priority": args.priority,
        "parent_id": args.parent_id,
        "quarter": args.quarter,
        "deadline": args.deadline,
        "estimated_min": args.estimated_min,
        "notes": args.notes,
    }
    conn = get_conn()
    try:
        if args.project:
            pid = upsert_project(conn, args.project, repo=args.repo)
            data["project_id"] = pid
        tid = upsert_todo(conn, data)
        conn.commit()
        _print_json({"id": tid, "title": args.title, "status": "backlog"})
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_list(args):
    conn = get_conn()
    try:
        rows = get_todos(conn, status=args.status, category=args.category, sort=args.sort)
        if args.limit:
            rows = rows[: args.limit]
        _print_json(rows)
    finally:
        conn.close()


def cmd_show(args):
    conn = get_conn()
    try:
        t = get_todo(conn, args.id)
        if not t:
            print(f"Error: todo {args.id} not found", file=sys.stderr)
            sys.exit(1)
        _print_json(t)
    finally:
        conn.close()


def cmd_move(args):
    conn = get_conn()
    try:
        update_todo_status(conn, args.id, args.status, reason=args.reason, force=args.force)
        conn.commit()
        t = get_todo(conn, args.id)
        _print_json({"id": args.id, "status": t["status"], "started_at": t["started_at"], "done_at": t["done_at"]})
    except ValueError as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_defer(args):
    conn = get_conn()
    try:
        update_todo_status(conn, args.id, "deferred", reason=args.reason)
        conn.commit()
        _print_json({"id": args.id, "status": "deferred", "deferred_reason": args.reason})
    except ValueError as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_done(args):
    conn = get_conn()
    try:
        # 부모 todo라면 subtasks 확인
        t = get_todo(conn, args.id)
        if t and t.get("subtasks"):
            unfinished = [s for s in t["subtasks"] if s["status"] != "done"]
            if unfinished and not args.force:
                titles = ", ".join(s["title"] for s in unfinished)
                print(f"Warning: unfinished subtasks remain: {titles}. Use --force to override.", file=sys.stderr)
                sys.exit(1)
        update_todo_status(conn, args.id, "done")
        conn.commit()
        _print_json({"id": args.id, "status": "done"})
    except ValueError as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Create todo (default status=backlog)")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--done-definition", dest="done_definition")
    p_add.add_argument("--category")
    p_add.add_argument("--priority", type=int)
    p_add.add_argument("--project")
    p_add.add_argument("--repo")
    p_add.add_argument("--parent-id", dest="parent_id", type=int)
    p_add.add_argument("--quarter")
    p_add.add_argument("--deadline", help="ISO: YYYY-MM-DD or YYYY-MM-DDTHH:MM")
    p_add.add_argument("--estimated-min", dest="estimated_min", type=int)
    p_add.add_argument("--notes")

    p_list = sub.add_parser("list", help="List todos")
    p_list.add_argument("--status", choices=["backlog", "wip", "done", "blocked", "deferred"])
    p_list.add_argument("--category")
    p_list.add_argument("--sort", default="default", choices=["default", "priority", "deadline"])
    p_list.add_argument("--limit", type=int)

    p_show = sub.add_parser("show", help="Show single todo with subtasks")
    p_show.add_argument("--id", required=True, type=int)

    p_move = sub.add_parser("move", help="Transition status")
    p_move.add_argument("--id", required=True, type=int)
    p_move.add_argument("--status", required=True,
                        choices=["backlog", "wip", "done", "blocked", "deferred"])
    p_move.add_argument("--reason")
    p_move.add_argument("--force", action="store_true",
                        help="Override WIP limit or unfinished-subtask warning")

    p_defer = sub.add_parser("defer", help="Defer with reason")
    p_defer.add_argument("--id", required=True, type=int)
    p_defer.add_argument("--reason", required=True)

    p_done = sub.add_parser("done", help="Mark done (checks unfinished subtasks)")
    p_done.add_argument("--id", required=True, type=int)
    p_done.add_argument("--force", action="store_true")

    dispatch = {
        "add": cmd_add,
        "list": cmd_list,
        "show": cmd_show,
        "move": cmd_move,
        "defer": cmd_defer,
        "done": cmd_done,
    }
    args = ap.parse_args()
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실행 권한 설정**

```bash
chmod +x plugins/life-management/skills/life-coach/scripts/todo_crud.py
```

- [ ] **Step 3: 수동 CLI 테스트 — add**

```bash
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "테스트 todo" --done-definition "이거 지우면 끝" --category "테스트"
```
Expected: `{"id": N, "title": "테스트 todo", "status": "backlog"}` stdout

- [ ] **Step 4: 수동 CLI 테스트 — list**

```bash
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py list --status backlog
```
Expected: JSON array, 방금 추가한 todo 포함

- [ ] **Step 5: 수동 CLI 테스트 — move (성공)**

방금 받은 id를 사용:
```bash
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py move --id <ID> --status wip
```
Expected: `{"id": N, "status": "wip", "started_at": "...", "done_at": null}`

- [ ] **Step 6: 수동 CLI 테스트 — move done**

```bash
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py move --id <ID> --status done
```
Expected: `{"id": N, "status": "done", ...}`. 그 후 지움:
```bash
sqlite3 ~/life-dashboard/data.db "DELETE FROM todos WHERE category='테스트';"
```

- [ ] **Step 7: 커밋**

```bash
git add plugins/life-management/skills/life-coach/scripts/todo_crud.py
git commit -m "feat(life-coach): add todo_crud.py — 순수 CLI for todos

- add/list/show/move/defer/done 서브커맨드
- stdout JSON, stderr 에러
- WIP limit + Done 정의 강제는 db.py에서 검증 (CLI는 통과/거부만)"
```

---

### Task 3: `todo_morning.py` — 아침 액션 JSON 출력

**Files:**
- Create: `plugins/life-management/skills/life-coach/scripts/todo_morning.py`

- [ ] **Step 1: todo_morning.py 작성**

```python
#!/usr/bin/env python3
"""아침 액션 — 오늘 우선순위 계산 + JSON 출력.

대화 없음. 사용자 input 안 받음.
Claude 세션이 stdout JSON을 읽고 대화형으로 사용자에게 제시.

Usage:
    python3 todo_morning.py --date YYYY-MM-DD
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "mcp" / "life-dashboard"))
from db import (
    get_conn, get_todos, get_overdue_todos, get_due_this_week_todos,
    get_pending_tasks,
)

KST = ZoneInfo("Asia/Seoul")


def _slim(t: dict) -> dict:
    """todo row → 출력용 축약."""
    return {
        "id": t["id"],
        "title": t["title"],
        "status": t["status"],
        "done_definition": t.get("done_definition"),
        "category": t.get("category"),
        "priority": t.get("priority"),
        "project_name": t.get("project_name"),
        "deadline": t.get("deadline"),
        "estimated_min": t.get("estimated_min"),
        "quarter": t.get("quarter"),
    }


def build_morning(conn, date: str) -> dict:
    overdue = [_slim(t) for t in get_overdue_todos(conn, as_of_date=date)]

    today_rows = conn.execute("""
        SELECT t.*, p.name as project_name
        FROM todos t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.deadline IS NOT NULL
          AND DATE(t.deadline) = DATE(?)
          AND t.status NOT IN ('done', 'deferred')
        ORDER BY CASE WHEN t.priority IS NULL THEN 99 ELSE t.priority END ASC
    """, (date,)).fetchall()
    today_due = [_slim(dict(r)) for r in today_rows]

    this_week = [_slim(t) for t in get_due_this_week_todos(conn, as_of_date=date)]
    current_wip = [_slim(t) for t in get_todos(conn, status="wip")]
    backlog_top5 = [_slim(t) for t in get_todos(conn, status="backlog", sort="default")[:5]]

    pending_rows = get_pending_tasks(conn)[:5]
    pending_suggestions = [
        {
            "id": r["id"],
            "description": r["description"],
            "suggested_date": r["suggested_date"],
            "source_type": r["source_type"],
            "estimated_min": r.get("estimated_min"),
        }
        for r in pending_rows
    ]

    return {
        "date": date,
        "overdue": overdue,
        "today_due": today_due,
        "this_week_due": this_week,
        "current_wip": current_wip,
        "backlog_top5": backlog_top5,
        "pending_suggestions": pending_suggestions,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"),
                    help="기준 날짜 (KST). 기본: 오늘")
    args = ap.parse_args()

    conn = get_conn()
    try:
        result = build_morning(conn, args.date)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실행 권한**

```bash
chmod +x plugins/life-management/skills/life-coach/scripts/todo_morning.py
```

- [ ] **Step 3: 수동 테스트 (빈 DB 상태)**

```bash
python3 plugins/life-management/skills/life-coach/scripts/todo_morning.py --date 2026-04-21
```
Expected: 모든 섹션이 빈 array인 JSON (todos/daily_checkins 비어있는 초기 상태).

```json
{
  "date": "2026-04-21",
  "overdue": [],
  "today_due": [],
  "this_week_due": [],
  "current_wip": [],
  "backlog_top5": [],
  "pending_suggestions": []
}
```

- [ ] **Step 4: 데이터 넣고 재테스트**

```bash
# 샘플 todo 3개 추가
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "임박 테스트 1" --done-definition "x" --deadline "2026-04-21" --priority 1
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "임박 테스트 2" --done-definition "x" --deadline "2026-04-23"
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "임박 테스트 3" --done-definition "x" --deadline "2026-04-10"

python3 plugins/life-management/skills/life-coach/scripts/todo_morning.py --date 2026-04-21
```
Expected: `overdue`에 "임박 테스트 3", `today_due`에 "임박 테스트 1", `this_week_due`에 "임박 테스트 2".

- [ ] **Step 5: 정리**

```bash
sqlite3 ~/life-dashboard/data.db "DELETE FROM todos WHERE title LIKE '임박 테스트%';"
```

- [ ] **Step 6: 커밋**

```bash
git add plugins/life-management/skills/life-coach/scripts/todo_morning.py
git commit -m "feat(life-coach): add todo_morning.py — 아침 액션 JSON 출력

- overdue / today_due / this_week_due / current_wip / backlog_top5 / pending_suggestions
- 대화 없음. stdout JSON only. Claude 세션이 대화 담당.
- KST 기준. task_suggestions read-only 포함 (최신 5건)"
```

---

### Task 4: `todo_evening.py` — 저녁 액션 + work-digest 폴백

**Files:**
- Create: `plugins/life-management/skills/life-coach/scripts/todo_evening.py`

- [ ] **Step 1: todo_evening.py 작성**

```python
#!/usr/bin/env python3
"""저녁 액션 — 계획 vs 실제 대조 JSON 출력.

동작:
  1) 해당 날짜 daily_checkin (morning_intent, morning_wip_ids) 조회
  2) 해당 날짜 tasks 조회. 비어있으면 work-digest Step 1-3 시도
     - Step 4는 LLM이 수행 (스크립트 아님) → needs_llm_task_generation=true 플래그
     - 실패 시 raw_sessions 폴백
  3) loose matching: repo/title keyword로 매칭
  4) stdout JSON

Usage:
    python3 todo_evening.py --date YYYY-MM-DD [--skip-digest]
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO_ROOT / "mcp" / "life-dashboard"))
from db import get_conn, get_tasks, get_daily_checkin, get_todos

WORK_DIGEST_DIR = REPO_ROOT / "plugins" / "dev-tools" / "skills" / "work-digest" / "scripts"
KST = ZoneInfo("Asia/Seoul")


def _slim_task(t: dict) -> dict:
    return {
        "id": t["id"],
        "tag": t["tag"],
        "summary": t["summary"],
        "repo": t.get("repo"),
        "duration_min": t.get("duration_min"),
        "status": t.get("status"),
        "follow_up": t.get("follow_up"),
        "project_name": t.get("project_name"),
    }


def _fetch_raw_sessions(conn, date: str) -> list[dict]:
    rows = conn.execute("""
        SELECT session_id, repo, tag, summary, start_at, end_at, duration_min, status
        FROM sessions
        WHERE date = ?
        ORDER BY start_at
    """, (date,)).fetchall()
    return [dict(r) for r in rows]


def _try_work_digest(date: str) -> tuple[bool, str]:
    """Step 1 (scanner) + Step 3 (extract) 시도. 결과는 DB에 쌓임.

    Step 2 (세션 요약, LLM)와 Step 4 (task 생성, LLM)는 이 스크립트가 하지 않음.
    LLM 수행은 Claude 세션의 몫.

    Returns:
        (success, message)
    """
    try:
        r = subprocess.run(
            ["python3", str(WORK_DIGEST_DIR / "active_session_scanner.py")],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            return False, f"scanner failed: {r.stderr[:200]}"
        r2 = subprocess.run(
            ["python3", str(WORK_DIGEST_DIR / "extract_day.py"),
             "--date", date, "--no-scan"],
            capture_output=True, text=True, timeout=120,
        )
        if r2.returncode != 0:
            return False, f"extract_day failed: {r2.stderr[:200]}"
        return True, "ok"
    except subprocess.TimeoutExpired as e:
        return False, f"timeout: {e}"
    except FileNotFoundError as e:
        return False, f"work-digest script not found: {e}"


def _tokens(text: str) -> set[str]:
    """간단 한국어/영문 단어 토큰. 2글자 이상."""
    if not text:
        return set()
    raw = re.findall(r"[A-Za-z가-힣0-9]{2,}", text.lower())
    return set(raw)


def _match_score(wip_title: str, task_summary: str, wip_repo: str | None, task_repo: str | None) -> float:
    """loose match score 0.0 ~ 1.0."""
    score = 0.0
    if wip_repo and task_repo:
        w = wip_repo.split("/")[-1].lower()
        t = task_repo.split("/")[-1].lower()
        if w == t:
            score += 0.5
    wip_toks = _tokens(wip_title)
    task_toks = _tokens(task_summary)
    if wip_toks and task_toks:
        overlap = wip_toks & task_toks
        score += min(0.5, 0.1 * len(overlap))
    return round(min(score, 1.0), 2)


def build_evening(conn, date: str, skip_digest: bool = False) -> dict:
    # 1. 아침 체크인
    checkin = get_daily_checkin(conn, date) or {
        "morning_intent": None, "morning_wip_ids": [], "missing_wip_ids": [], "evening_reflection": None
    }

    # 2. tasks 조회
    tasks = get_tasks(conn, date)
    fallback = False
    raw_sessions: list[dict] = []
    needs_llm = False

    if not tasks and not skip_digest:
        ok, msg = _try_work_digest(date)
        if ok:
            # Step 1-3 성공. tasks 재조회 시도 (LLM Step 4 안 돌았으면 여전히 비어있음)
            tasks = get_tasks(conn, date)
            if not tasks:
                # Step 4 (LLM)가 필요하다는 flag
                needs_llm = True
                fallback = True
                raw_sessions = _fetch_raw_sessions(conn, date)
        else:
            # Step 1-3 실패 → 폴백
            fallback = True
            raw_sessions = _fetch_raw_sessions(conn, date)

    elif not tasks and skip_digest:
        fallback = True
        raw_sessions = _fetch_raw_sessions(conn, date)

    # 3. loose matching (tasks 있을 때만)
    loose_matches: list[dict] = []
    unmatched_actual: list[dict] = []

    if tasks:
        wip_ids = checkin.get("morning_wip_ids") or []
        wip_todos = []
        if wip_ids:
            placeholders = ",".join("?" * len(wip_ids))
            rows = conn.execute(f"""
                SELECT t.*, p.name as project_name
                FROM todos t LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.id IN ({placeholders})
            """, wip_ids).fetchall()
            wip_todos = [dict(r) for r in rows]

        matched_task_ids: set[int] = set()
        for w in wip_todos:
            wip_repo = None
            if w.get("project_id"):
                pr = conn.execute(
                    "SELECT repo FROM projects WHERE id = ?", (w["project_id"],)
                ).fetchone()
                if pr:
                    wip_repo = pr["repo"]
            matches = []
            for t in tasks:
                s = _match_score(w["title"], t["summary"], wip_repo, t.get("repo"))
                if s >= 0.3:
                    matches.append({**_slim_task(t), "match_score": s})
                    matched_task_ids.add(t["id"])
            loose_matches.append({
                "wip_id": w["id"],
                "wip_title": w["title"],
                "matched_tasks": sorted(matches, key=lambda x: -x["match_score"]),
            })
        unmatched_actual = [
            _slim_task(t) for t in tasks if t["id"] not in matched_task_ids
        ]

    return {
        "date": date,
        "morning_intent": checkin.get("morning_intent"),
        "morning_wip_ids": checkin.get("morning_wip_ids") or [],
        "missing_wip_ids": checkin.get("missing_wip_ids") or [],
        "actual_tasks": [_slim_task(t) for t in tasks],
        "fallback": fallback,
        "raw_sessions": raw_sessions,
        "loose_matches": loose_matches,
        "unmatched_actual": unmatched_actual,
        "needs_llm_task_generation": needs_llm,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    ap.add_argument("--skip-digest", action="store_true",
                    help="work-digest 재시도 없이 현재 tasks/sessions만 사용")
    args = ap.parse_args()

    conn = get_conn()
    try:
        result = build_evening(conn, args.date, skip_digest=args.skip_digest)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실행 권한**

```bash
chmod +x plugins/life-management/skills/life-coach/scripts/todo_evening.py
```

- [ ] **Step 3: 수동 테스트 — skip-digest 폴백**

```bash
python3 plugins/life-management/skills/life-coach/scripts/todo_evening.py \
    --date 2026-04-21 --skip-digest
```
Expected:
- `fallback: true` (tasks 비어있을 때)
- `raw_sessions`: 해당 날짜 세션들 (없으면 빈 array)
- `needs_llm_task_generation: false`

- [ ] **Step 4: 수동 테스트 — work-digest 호출 경로 (선택)**

```bash
python3 plugins/life-management/skills/life-coach/scripts/todo_evening.py --date 2026-04-21
```
Expected: 실제 work-digest 호출됨. Step 2/4가 LLM이라 결과에 따라:
- Step 1-3 성공, tasks 여전히 비어있음 → `needs_llm_task_generation: true`, `fallback: true`
- 이미 tasks 있음 → matching 결과

Claude 세션이 이 플래그 받으면 Step 4(LLM) 수행 후 `--skip-digest`로 재호출.

- [ ] **Step 5: 커밋**

```bash
git add plugins/life-management/skills/life-coach/scripts/todo_evening.py
git commit -m "feat(life-coach): add todo_evening.py — 저녁 액션 (work-digest 호출 + 폴백)

- tasks 조회 + loose matching (repo + keyword overlap)
- tasks 비어있으면 work-digest Step 1-3 호출 시도
- Step 4 (LLM) 필요 시 needs_llm_task_generation=true 플래그
- 실패 시 raw_sessions 폴백
- KST 기준. 대화 없음."
```

---

### Task 5: SKILL.md 재구성 + cli-reference.md 업데이트

**Files:**
- Modify: `plugins/life-management/skills/life-coach/SKILL.md`
- Modify: `plugins/life-management/skills/life-coach/references/cli-reference.md`

- [ ] **Step 1: SKILL.md 재구성 — "모드" 섹션 교체**

`plugins/life-management/skills/life-coach/SKILL.md`를 읽고, 기존 "모드" 섹션 (대략 라인 28-35)을 아래로 교체:

```markdown
## 두 축 구조

life-coach는 두 축으로 구성된다. 두 축은 저장소도 트리거도 다르다.

### 축 1: 액션 (NEW) — 수동 invoke, 대화형, 상태 관리

| 액션 | 트리거 | 역할 | 저장 |
|------|--------|------|------|
| `todo-morning` | `/coach todo-morning`, "오늘 뭐할까", "아침 체크인" | WIP 2개 확정 + intent 기록 | `daily_checkins`, `todos` |
| `todo-evening` | `/coach todo-evening`, "오늘 뭐했지", "저녁 체크인" | work-digest 실행 + 계획 vs 실제 대조 + reflection | `daily_checkins` |
| `todo-crud` | `/coach todo add/list/move/...` | todo CRUD | `todos` |

스크립트 I/O 계약: 순수 JSON 입출력. 대화는 Claude 세션이 담당.
상세: `references/cli-reference.md`.

### 축 2: 분석 모드 (EXISTING) — on-demand, 리포트 중심

| 모드 | 트리거 | 데이터 범위 | 결과물 |
|------|--------|------------|--------|
| **데일리** | `/coach daily`, "오늘 리포트" | 특정 날짜 | HTML 리포트 (coaching_entries) |
| **위클리** | `/coach weekly`, "주간 리포트" | 해당 주 전체 | HTML 리포트 |
| **온디맨드** | 특정 주제 요청 | 요청에 따라 | 대화형 or HTML |

**자동 cron 폐기**: 과거에 매일 21시 daily, 매주 일 21시 weekly cron이 있었으나 dead 상태. Phase 1에서 자동 실행 복구하지 않는다. 모두 **on-demand 수동 invoke**. Phase 2+에서 아침/저녁 액션의 자동화와 함께 재검토.

분석 모드의 기존 Phase 1-3 워크플로우(데이터 준비 → 코칭 → 리포트)는 변경 없음.
```

- [ ] **Step 2: SKILL.md에 신규 액션 워크플로우 섹션 추가**

위 섹션 바로 아래에 추가:

```markdown
## 축 1 액션 워크플로우 (아침/저녁/CRUD)

### 아침 액션 (todo-morning)

1. `todo_morning.py --date <오늘>` 실행 → JSON 수신
2. Claude가 사용자에게 섹션별 출력 (Overdue / Today / This Week / WIP / Backlog top5 / AI 제안 참고)
3. 사용자에게 질문: 오늘 WIP 2개 어느 todo? 오늘 intent?
4. 선택 받음 → `todo_crud.py move --id N --status wip` (필요 시) + `upsert_daily_checkin` 저장
5. 아침 intent 확정 후 사용자 격려 멘트 (Korean tone 규칙 준수 — 아첨 금지)

### 저녁 액션 (todo-evening)

1. `todo_evening.py --date <오늘>` 실행 → JSON 수신
2. `needs_llm_task_generation: true`면 → Claude가 work-digest Step 4 (task 생성) 수행 →
   `activity_writer.py update-tasks`로 저장 → `todo_evening.py --skip-digest`로 재호출
3. `fallback: true`면 → 사용자에게 "raw sessions로 폴백" 보고 + raw_sessions 요약 제시
4. 정상 경로면: morning_intent + loose_matches + unmatched_actual 대조 제시
5. 사용자에게 reflection 질문 (왜 미완료인지? 내일로 이월? 등)
6. `upsert_daily_checkin(..., evening_reflection=...)` 저장
7. 내일 WIP 후보 제안 (다음 날 아침 액션에 반영)

### CRUD 액션 (todo add/list/move/defer/done/show)

`todo_crud.py`를 사용자 요청에 맞게 invoke. 예:
- "cube-admin 기획 backlog에 추가" → `todo_crud.py add --title "cube-admin 기획" --done-definition "..." --category 업무 --quarter 2026Q2`
- "#15 WIP로" → `todo_crud.py move --id 15 --status wip`
- "WIP 보여줘" → `todo_crud.py list --status wip`

### 운영 규칙 (강제)

- **WIP limit 2** — 초과 시 `--force`로만 허용
- **Done 정의 의무** — `done_definition` 없이 WIP 전환 불가
- **새 할일 → backlog 직행** — WIP 바로 진입 금지
- **KST 기준** — 모든 날짜는 Asia/Seoul
```

- [ ] **Step 3: SKILL.md의 Scripts 테이블 업데이트**

기존 Scripts 테이블(라인 107 부근)에 아래 3행 추가:

```markdown
| `todo_crud.py` | todo CRUD CLI (add/list/show/move/defer/done) |
| `todo_morning.py` | 아침 액션 — 오늘 우선순위 + AI 제안 참고 JSON 출력 |
| `todo_evening.py` | 저녁 액션 — work-digest 호출 + 계획 vs 실제 loose matching JSON 출력 |
```

- [ ] **Step 4: SKILL.md의 References 테이블 확인**

`references/cli-reference.md`가 이미 있다면 변경 불필요. 없으면 다음 Step에서 생성.

- [ ] **Step 5: cli-reference.md에 신규 CLI 섹션 추가**

`plugins/life-management/skills/life-coach/references/cli-reference.md` 파일 끝에 추가 (파일이 없으면 새로 생성):

```markdown

---

## 축 1 액션 CLI — 신규

### todo_crud.py

순수 CLI. 대화 없음. stdout JSON, stderr 에러, exit 0 성공 / 1 실패.

**add** — 새 todo를 backlog에 추가
```
python3 todo_crud.py add --title "..." \
    [--done-definition "..."] [--category 업무|개인|건강|재정|관계] \
    [--priority 1|2|3] [--project "..."] [--repo "..."] [--parent-id N] \
    [--quarter "2026Q2"] [--deadline "YYYY-MM-DD"] \
    [--estimated-min N] [--notes "..."]
```
출력: `{"id": N, "title": "...", "status": "backlog"}`

**list** — 필터링된 todo 목록
```
python3 todo_crud.py list [--status backlog|wip|done|blocked|deferred] \
    [--category "..."] [--sort default|priority|deadline] [--limit N]
```
sort=default 정렬: deadline 있는 것 먼저 (임박 순) → priority 높은 순 → 오래된 것 순

**show** — 단일 todo (subtasks 포함)
```
python3 todo_crud.py show --id N
```

**move** — 상태 전환 (검증 포함)
```
python3 todo_crud.py move --id N --status wip|done|blocked|deferred|backlog \
    [--reason "..."] [--force]
```
- WIP 전환: `done_definition` null이면 거부
- WIP 전환: 현재 WIP 2개면 거부 (`--force`로 override, stderr 로그)
- `deferred`: `--reason` 권장
- backlog→wip: started_at 자동
- *→done: done_at 자동

**defer** — `move --status deferred`의 별칭
```
python3 todo_crud.py defer --id N --reason "..."
```

**done** — `move --status done`의 별칭. 부모 todo면 미완료 subtask 확인 (`--force`로 override)
```
python3 todo_crud.py done --id N [--force]
```

### todo_morning.py

```
python3 todo_morning.py [--date YYYY-MM-DD]
```
기본 date: 오늘 (KST).

출력 JSON 스키마:
- `date`: 기준 날짜
- `overdue`: deadline 지난 todos (status NOT IN done/deferred)
- `today_due`: deadline 오늘
- `this_week_due`: deadline +1 ~ +7일
- `current_wip`: status=wip todos
- `backlog_top5`: 기본 정렬 상위 5
- `pending_suggestions`: `task_suggestions` pending 최신 5건 (read-only 참고)

### todo_evening.py

```
python3 todo_evening.py [--date YYYY-MM-DD] [--skip-digest]
```

동작 순서:
1. daily_checkin (morning_intent, morning_wip_ids) 조회
2. `tasks` 조회. 비어있고 `--skip-digest` 아니면 work-digest Step 1-3 실행
3. Step 4(LLM)가 필요하면 `needs_llm_task_generation: true` 반환 → Claude 세션이 수행 후 재호출
4. 실패 시 `fallback: true` + `raw_sessions` 채움
5. loose matching (repo + keyword overlap score ≥ 0.3)

출력 JSON 스키마:
- `date`, `morning_intent`, `morning_wip_ids`, `missing_wip_ids`
- `actual_tasks`: tasks 테이블 rows
- `fallback`: bool
- `raw_sessions`: fallback일 때 채워짐
- `loose_matches`: `[{wip_id, wip_title, matched_tasks: [{..., match_score}]}]`
- `unmatched_actual`: 계획에 없던 예정 외 tasks
- `needs_llm_task_generation`: bool
```

- [ ] **Step 6: 커밋**

```bash
git add plugins/life-management/skills/life-coach/SKILL.md \
        plugins/life-management/skills/life-coach/references/cli-reference.md
git commit -m "docs(life-coach): 축 1 (액션) / 축 2 (분석 모드) 분리 + 신규 CLI 레퍼런스

- SKILL.md: 기존 '모드' 섹션을 두 축 구조로 재구성
- 자동 cron 폐기 명시 (Phase 2+에서 재검토)
- daily/weekly → on-demand로 정체성 재정의
- 신규 액션 워크플로우 (todo-morning/evening/crud) 추가
- cli-reference.md에 신규 3개 스크립트 I/O 계약 추가"
```

---

### Task 6: 이번 분기(2026Q2) Backlog 초기화

**Files:** (없음 — CLI 호출로 DB 데이터 입력)

- [ ] **Step 1: 6개 기본 todo 추가**

아래 명령을 차례로 실행. 각 실행 후 출력된 id를 확인.

```bash
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "cube-backend 머지" \
    --done-definition "master에 머지 + CI green + 릴리즈 노트 작성" \
    --category "업무" --priority 1 --quarter "2026Q2" \
    --project "Cube Backend" --repo "cube-backend"

python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "cube-archive 초안" \
    --done-definition "스펙 문서 v1 노션에 작성 (범위/데이터 모델/마이그레이션 전략 포함)" \
    --category "업무" --priority 2 --quarter "2026Q2" \
    --project "Cube Archive"

python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "자동 캘리브레이션 스킬" \
    --done-definition "스킬 SKILL.md + 핵심 스크립트 작성 + 실제 머신 1회 성공" \
    --category "업무" --priority 2 --quarter "2026Q2" \
    --project "Cube 자동 캘리브레이션"

python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "식재료 리포트 스킬 완성" \
    --done-definition "리포트 생성 전체 플로우 성공 + 실제 데이터로 1회 검증" \
    --category "업무" --priority 2 --quarter "2026Q2" \
    --project "Cube 식재료 리포트"

python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "cube-admin 기획" \
    --done-definition "기획서 v1 노션에 작성 (범위/주요 화면 와이어프레임/API 스펙)" \
    --category "업무" --priority 1 --quarter "2026Q2" \
    --deadline "2026-04-25" --estimated-min 240 \
    --project "Cube Admin"

python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add \
    --title "pm-bot sdk 마이그레이션 (spike)" \
    --done-definition "claude sdk 기반 minimal pm-bot 동작 확인 (1개 기능 end-to-end)" \
    --category "업무" --priority 1 --quarter "2026Q2" \
    --estimated-min 2400 \
    --notes "1주 timebox spike. 안 끝나면 중단하고 lean 대안 검토." \
    --project "pm-bot"
```

- [ ] **Step 2: Backlog 확인**

```bash
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py list \
    --status backlog --sort default
```
Expected: 위 6개가 정렬되어 JSON array로 반환. `cube-admin 기획`이 deadline 있어서 먼저.

- [ ] **Step 3: 초기화 커밋 (데이터만, 파일 변경 없음)**

없음. 이 단계는 DB 데이터라 git 커밋 대상 아님. 스킬 운영 결과로 `~/life-dashboard/data.db`에만 반영.

---

### Task 7: 통합 테스트 + 머지

- [ ] **Step 1: 전체 테스트 실행**

```bash
python3 -m pytest mcp/life-dashboard/tests/ -v
```
Expected: 기존 + `test_todos.py` 전부 PASS.

- [ ] **Step 2: 아침 액션 실제 실행 (Claude 세션 권장)**

Claude 세션에서:

```
사용자: /coach todo-morning
```

예상 흐름:
1. Claude가 `todo_morning.py --date 2026-04-21` 실행
2. JSON 받아 섹션별 사용자에게 제시
3. Claude가 "오늘 WIP 2개 선택 + intent?" 질문
4. 사용자 답변 → Claude가 `todo_crud.py move` + `upsert_daily_checkin` 호출

- [ ] **Step 3: 저녁 액션 실제 실행**

```
사용자: /coach todo-evening
```

예상 흐름:
1. Claude가 `todo_evening.py --date 2026-04-21` 실행
2. `needs_llm_task_generation=true`면 Claude가 Step 4 수행 후 재호출
3. loose_matches 기반 대화 → reflection 수집 → `upsert_daily_checkin` 저장

- [ ] **Step 4: 설계 문서 APPROVED 상태 업데이트**

`docs/plans/2026-04-21-life-coach-todos-extension-design.md`의 header 라인을 `Status: DRAFT → APPROVED 대기` → `Status: APPROVED (2026-04-27)` 로 변경. 7일 timebox 종료 시점에 맞춰 수정.

- [ ] **Step 5: worktree → main rebase + 정리**

```bash
cd ../daye-agent-toolkit-todos
git rebase master
# 충돌 있으면 해결 후 git rebase --continue
```

커밋 히스토리 정리가 필요하면 `git rebase -i master`로 `fix:` squash + dist 최종 커밋에 반영.

- [ ] **Step 6: 사용자 승인 대기 (머지 전 게이트)**

이 시점에 사용자에게 변경 요약 제시:
- 추가된 테이블 2개
- 추가된 db.py 함수 8개
- 추가된 스크립트 3개
- life-coach SKILL.md 재구성
- 초기 backlog 6개

사용자의 명시적 머지 승인을 기다린다. (프로젝트 규칙: 머지엔 사용자 명시 승인 필수)

- [ ] **Step 7: 머지**

사용자 승인 후:

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit  # main 레포
git merge --no-ff feat/life-coach-todos
# 필요 시 git push origin master
```

- [ ] **Step 8: worktree 정리**

```bash
git worktree remove ../daye-agent-toolkit-todos
git branch -d feat/life-coach-todos
```

- [ ] **Step 9: CLAUDE.md 업데이트 필요 여부 판단**

이번 변경으로 프로젝트 관습이 바뀐 부분이 있으면 (예: dev-tools/plugin 구조 변경, 새 MCP 함수 호출 방식 등) CLAUDE.md 업데이트. 단순 기능 추가면 생략 가능.

- [ ] **Step 10: 1주 timebox 회고 기록**

`docs/plans/2026-04-21-life-coach-todos-extension-design.md` 맨 아래에 Appendix 추가:

```markdown
## Appendix: 1주 Timebox 회고 (2026-04-27)

- 실제 소요: ?
- MVP 동작: YES / NO
- Phase 2 우선 항목:
- 1주 운영 후 발견한 gap:
- 작동하지 않은 것:
- 다음 개선 방향:
```

---

## Self-Review (Plan 작성 완료 후)

작성자가 실행. 발견한 이슈는 인라인 수정.

### 1. Spec coverage 체크

설계 문서의 각 섹션이 Plan에 반영됐는지 대조:

| Spec 섹션 | Plan 반영 | Task |
|---|---|---|
| 스코프 잠금 선언 | ✅ | 헤더 + Task 0 (worktree) |
| todos 스키마 | ✅ | Task 1 Step 6 |
| daily_checkins 스키마 | ✅ | Task 1 Step 6 |
| db.py 함수 8개 | ✅ | Task 1 Step 8 |
| priority 정렬 규칙 | ✅ | Task 1 Step 8 (get_todos sort=default) + Step 3 test |
| morning_wip_ids 무결성 | ✅ | Task 1 Step 8 (get_daily_checkin) + Step 4 test |
| life-coach 재구성 (두 축 분리) | ✅ | Task 5 Step 1-2 |
| 자동 cron 폐기 | ✅ | Task 5 Step 1 |
| todo_crud.py I/O 계약 | ✅ | Task 2 + cli-reference Step 5 |
| todo_morning.py I/O 계약 | ✅ | Task 3 + cli-reference |
| todo_evening.py + 폴백 경로 | ✅ | Task 4 (fallback=true + raw_sessions) |
| task_suggestions read-only 노출 | ✅ | Task 3 Step 1 (pending_suggestions 필드) |
| 운영 규칙 (WIP 2, Done 정의, KST) | ✅ | Task 1 Step 8 (update_todo_status) + Task 5 Step 2 |
| 2026Q2 backlog 초기화 | ✅ | Task 6 |

### 2. Placeholder 스캔

금지 패턴 전수 검사 — "TBD", "TODO", "similar to", "fill in" — 없음 확인.

### 3. 타입 일관성

- `update_todo_status(conn, todo_id, new_status, reason=None, force=False)` — Task 1, 2, 3 모두 같은 시그니처
- `upsert_daily_checkin(conn, date, *, morning_wip_ids, morning_intent, evening_reflection)` — keyword-only 인자. Task 3, 4에서도 동일 패턴
- `get_daily_checkin` 반환에 `missing_wip_ids` 필드 — test + CLI에서 일관
- `pending_suggestions` 필드명 — morning.py 출력 ↔ cli-reference 일치

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-04-21-life-coach-todos-extension.md`.**

두 가지 실행 옵션:

### 1. Subagent-Driven (추천)

- `superpowers:subagent-driven-development` 사용
- Task별로 fresh subagent 디스패치 (Claude sonnet)
- Task 간 리뷰 게이트
- 반복 TDD 루프
- 병렬화 가능한 Task 없음 (의존 순차) — 순차 실행

### 2. Inline Execution

- `superpowers:executing-plans` 사용
- 현재 세션에서 batch 실행
- 체크포인트마다 리뷰

### 그리고 미리 박아둔 게이트

- **Task 0 (사전 조건)**: 반드시 worktree 먼저 (`feat/life-coach-todos`). main에서 코드 수정 금지.
- **Task 7 Step 6**: 머지 전 사용자 명시 승인 필수.
- **Timebox 게이트**: 2026-04-27 일요일 기준 MVP 동작 안 하면 스킬 접고 lean 대안으로 전환.

어느 접근을 쓸지 알려주면 그 스킬 invoke.
