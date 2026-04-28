# Capacity Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** spec v5 (`docs/superpowers/specs/2026-04-27-capacity-tracking-design.md`)를 구현 — life-coach 캐파/일정 시스템 Phase 1 (daily_checkins +6 컬럼, todo_schedules + todo_schedule_actuals 신규 테이블, wrapper 4개, /morning /evening /capacity 슬래시 커맨드, estimated_min 입력 정책, SKILL.md 인터뷰 가이드).

**Architecture:** SQLite 3 테이블 변경/생성 → db.py CRUD 함수 → script wrapper (argparse subcommand, identity 검증, idempotency) → 슬래시 커맨드 진입점 → SKILL.md 인터뷰 룰. 모든 read/write는 wrapper 경유. 에이전트는 db.py 직접 호출 금지.

**Tech Stack:** Python 3 (stdlib only), SQLite, pytest (in-memory DB), argparse subcommand, markdown commands.

---

## File Structure

### 신규 (7)
- `plugins/life-management/commands/morning.md` — `/morning` 진입점
- `plugins/life-management/commands/evening.md` — `/evening` 진입점
- `plugins/life-management/commands/capacity.md` — `/capacity` 진입점
- `plugins/life-management/skills/life-coach/scripts/checkin_save.py` — daily_checkin wrapper (morning/evening subcommand)
- `plugins/life-management/skills/life-coach/scripts/schedule_upsert.py` — schedule wrapper (planned_min 자동 계산, partial UNIQUE 검증)
- `plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py` — actual 브리지 wrapper (task 자동 조회, snapshot)
- `plugins/life-management/skills/life-coach/scripts/capacity.py` — 누적 조회 + 4종 flag

### 변경 (5)
- `mcp/life-dashboard/schema.sql` — daily_checkins +6 컬럼, todo_schedules + todo_schedule_actuals CREATE
- `mcp/life-dashboard/db.py` — 함수 6개 추가 (`upsert_daily_checkin` 확장, `upsert_schedule`, `link_schedule_actual`, `get_schedule`, `get_schedules_by_date`, `get_daily_checkins(start,end)`, `get_capacity_status(date)`). 신규 스키마는 schema.sql만 정의하고 라이브 DB에는 1회성 수동 적용 (db.py `_migrate`에 마이그레이션 분기 추가 금지)
- `mcp/life-dashboard/tests/test_todos.py` — 위 함수 + wrapper + silent fail 회귀 테스트
- `plugins/life-management/skills/life-coach/scripts/todo_crud.py` — estimated_min tri-state 정책
- `plugins/life-management/skills/life-coach/SKILL.md` — 슬래시 커맨드, 워크플로우 (wrapper 경유), 인터뷰 가이드, status 영속화 룰

---

### Task 1: Schema — daily_checkins 6 컬럼 추가

**Files:**
- Modify: `mcp/life-dashboard/schema.sql:160-167` (CREATE TABLE daily_checkins 확장)
- Modify: `mcp/life-dashboard/db.py:120-131` (_migrate 함수의 daily_checkins 분기 확장)
- Test: `mcp/life-dashboard/tests/test_todos.py` (신규 test 추가)

- [ ] **Step 1: Write the failing test**

`mcp/life-dashboard/tests/test_todos.py` 끝에 추가:

```python
def test_daily_checkins_has_capacity_columns():
    """daily_checkins에 available_min, energy, blockers + 3 status 컬럼 있어야 함"""
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn
    conn = get_conn()
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
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn
    conn = get_conn()
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
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn
    conn = get_conn()
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd mcp/life-dashboard && python -m pytest tests/test_todos.py::test_daily_checkins_has_capacity_columns -v
```
Expected: FAIL — `assert "available_min" in cols` 실패

- [ ] **Step 3: Update schema.sql**

`mcp/life-dashboard/schema.sql`의 `CREATE TABLE IF NOT EXISTS daily_checkins (...)`를 다음으로 교체:

```sql
CREATE TABLE IF NOT EXISTS daily_checkins (
    date TEXT PRIMARY KEY,
    morning_wip_ids TEXT,
    morning_intent TEXT,
    evening_reflection TEXT,
    available_min INTEGER CHECK (available_min IS NULL OR available_min >= 0),
    energy TEXT CHECK (energy IS NULL OR energy IN ('low','mid','high')),
    blockers TEXT,
    available_status TEXT NOT NULL DEFAULT 'unknown' CHECK (available_status IN ('answered','skipped','unknown')),
    energy_status TEXT NOT NULL DEFAULT 'unknown' CHECK (energy_status IN ('answered','skipped','unknown')),
    blockers_status TEXT NOT NULL DEFAULT 'unknown' CHECK (blockers_status IN ('answered','skipped','unknown')),
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

- [ ] **Step 4: Update db.py _migrate (additive ALTER for existing DBs)**

`mcp/life-dashboard/db.py`의 `_migrate(conn)` 함수 안, daily_checkins 분기 다음에 추가:

```python
    # daily_checkins additive: capacity columns
    try:
        dc_cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_checkins)").fetchall()}
        if dc_cols and "available_min" not in dc_cols:
            additions = [
                ("available_min", "INTEGER"),
                ("energy", "TEXT"),
                ("blockers", "TEXT"),
                ("available_status", "TEXT NOT NULL DEFAULT 'unknown'"),
                ("energy_status", "TEXT NOT NULL DEFAULT 'unknown'"),
                ("blockers_status", "TEXT NOT NULL DEFAULT 'unknown'"),
            ]
            for col, decl in additions:
                if col not in dc_cols:
                    conn.execute(f"ALTER TABLE daily_checkins ADD COLUMN {col} {decl}")
            conn.commit()
    except Exception:
        pass
```

Note: ALTER TABLE은 SQLite에서 CHECK 제약 직접 추가 불가. 새 DB는 schema.sql의 CREATE TABLE이 처리. ALTER는 컬럼만 추가.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd mcp/life-dashboard && python -m pytest tests/test_todos.py -k "daily_checkins" -v
```
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git -C /Users/dayejeong/git_workplace/daye-agent-toolkit/.worktrees/capacity-tracking add mcp/life-dashboard/schema.sql mcp/life-dashboard/db.py mcp/life-dashboard/tests/test_todos.py
git -C /Users/dayejeong/git_workplace/daye-agent-toolkit/.worktrees/capacity-tracking commit -m "feat(schema): daily_checkins + capacity columns (available_min, energy, blockers, status)"
```

---

### Task 2: Schema — todo_schedules 신규

**Files:**
- Modify: `mcp/life-dashboard/schema.sql` (CREATE TABLE 추가)
- Modify: `mcp/life-dashboard/db.py:_migrate` (CREATE 분기 추가)
- Test: `mcp/life-dashboard/tests/test_todos.py`

- [ ] **Step 1: Write failing tests**

```python
def test_todo_schedules_table_exists():
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='todo_schedules'").fetchall()
        assert len(rows) == 1
        cols = {r[1] for r in conn.execute("PRAGMA table_info(todo_schedules)").fetchall()}
        for c in ["id","todo_id","date","start_at","end_at","planned_min","notes","created_at"]:
            assert c in cols
    finally:
        conn.close()


def test_todo_schedules_check_planned_min_positive():
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn, upsert_todo
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
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
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn, upsert_todo
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
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
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn, upsert_todo
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd mcp/life-dashboard && python -m pytest tests/test_todos.py -k "todo_schedules" -v
```
Expected: 4 FAIL (table 없음)

- [ ] **Step 3: Add CREATE TABLE to schema.sql**

`mcp/life-dashboard/schema.sql`의 daily_checkins 정의 다음에 추가:

```sql
CREATE TABLE IF NOT EXISTS todo_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    todo_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    start_at TEXT,
    end_at TEXT,
    planned_min INTEGER NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    CHECK (
      (start_at IS NULL AND end_at IS NULL) OR
      (start_at IS NOT NULL AND end_at IS NOT NULL)
    ),
    CHECK (start_at IS NULL OR end_at > start_at),
    CHECK (start_at IS NULL OR start_at GLOB '[0-2][0-9]:[0-5][0-9]'),
    CHECK (end_at IS NULL OR end_at GLOB '[0-2][0-9]:[0-5][0-9]'),
    CHECK (planned_min > 0),
    FOREIGN KEY(todo_id) REFERENCES todos(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_todo_schedules_date ON todo_schedules(date);
CREATE INDEX IF NOT EXISTS idx_todo_schedules_todo ON todo_schedules(todo_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_time_slot
  ON todo_schedules(todo_id, date, start_at, end_at)
  WHERE start_at IS NOT NULL;
```

- [ ] **Step 4: Add migration in db.py _migrate**

`_migrate(conn)` 안 daily_checkins 분기 다음에:

```python
    if "todo_schedules" not in existing:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS todo_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                todo_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                start_at TEXT,
                end_at TEXT,
                planned_min INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                CHECK (
                  (start_at IS NULL AND end_at IS NULL) OR
                  (start_at IS NOT NULL AND end_at IS NOT NULL)
                ),
                CHECK (start_at IS NULL OR end_at > start_at),
                CHECK (start_at IS NULL OR start_at GLOB '[0-2][0-9]:[0-5][0-9]'),
                CHECK (end_at IS NULL OR end_at GLOB '[0-2][0-9]:[0-5][0-9]'),
                CHECK (planned_min > 0),
                FOREIGN KEY(todo_id) REFERENCES todos(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_todo_schedules_date ON todo_schedules(date);
            CREATE INDEX IF NOT EXISTS idx_todo_schedules_todo ON todo_schedules(todo_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_time_slot
              ON todo_schedules(todo_id, date, start_at, end_at)
              WHERE start_at IS NOT NULL;
        """)
        conn.commit()
```

- [ ] **Step 5: Run tests pass**

```bash
cd mcp/life-dashboard && python -m pytest tests/test_todos.py -k "todo_schedules" -v
```
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git -C /Users/dayejeong/git_workplace/daye-agent-toolkit/.worktrees/capacity-tracking add mcp/life-dashboard/schema.sql mcp/life-dashboard/db.py mcp/life-dashboard/tests/test_todos.py
git -C /Users/dayejeong/git_workplace/daye-agent-toolkit/.worktrees/capacity-tracking commit -m "feat(schema): todo_schedules with CHECK constraints + partial UNIQUE idempotency"
```

---

### Task 3: Schema — todo_schedule_actuals 브리지 (snapshot identity)

**Files:**
- Modify: `mcp/life-dashboard/schema.sql`
- Test: `mcp/life-dashboard/tests/test_todos.py`
- Live DB: `~/life-dashboard/data.db` (1회성 수동 적용 — Step 4)

- [ ] **Step 1: Write failing tests (snapshot identity, no tasks FK, schedule CASCADE)**

```python
def test_todo_schedule_actuals_table_exists():
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='todo_schedule_actuals'").fetchall()
        assert len(rows) == 1
        cols = {r[1] for r in conn.execute("PRAGMA table_info(todo_schedule_actuals)").fetchall()}
        for c in ["id","schedule_id","source_task_id","source_date","source_repo","source_summary","duration_min_snapshot","confirmed_at"]:
            assert c in cols
    finally:
        conn.close()


def test_actuals_unique_4_tuple():
    """같은 (schedule_id, source_date, source_summary, source_repo) 중복 매핑 차단"""
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn, upsert_todo
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        cur = conn.execute(
            "INSERT INTO todo_schedules (todo_id, date, planned_min) VALUES (?, ?, ?)",
            (tid, "2026-04-28", 60),
        )
        sid = cur.lastrowid
        conn.execute(
            "INSERT INTO todo_schedule_actuals (schedule_id, source_date, source_summary, source_repo, duration_min_snapshot) VALUES (?, ?, ?, ?, ?)",
            (sid, "2026-04-28", "summary A", "repo X", 30),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO todo_schedule_actuals (schedule_id, source_date, source_summary, source_repo, duration_min_snapshot) VALUES (?, ?, ?, ?, ?)",
                (sid, "2026-04-28", "summary A", "repo X", 30),
            )
            conn.commit()
    finally:
        conn.rollback()
        conn.close()


def test_actuals_no_tasks_fk_survives_task_delete():
    """tasks 테이블의 row 삭제가 actual mapping을 파괴하지 않음 (Codex v4 BLOCK 회귀)"""
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn, upsert_todo
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        # task 삽입
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

        # actual mapping은 보존되어야 함
        rows = conn.execute(
            "SELECT * FROM todo_schedule_actuals WHERE schedule_id = ?", (sid,)
        ).fetchall()
        assert len(rows) == 1, "tasks 삭제 후에도 actual은 보존되어야 함"
    finally:
        conn.rollback()
        conn.close()


def test_actuals_schedule_delete_cascade():
    """schedule 삭제 시 actual은 CASCADE 삭제"""
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db import get_conn, upsert_todo
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
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
        conn.rollback()
        conn.close()
```

- [ ] **Step 2: Run tests fail**

Expected: 4 FAIL (table 없음)

- [ ] **Step 3: Update schema.sql only**

`schema.sql`의 todo_schedules 다음에:

```sql
CREATE TABLE IF NOT EXISTS todo_schedule_actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    source_task_id INTEGER,
    source_date TEXT NOT NULL,
    source_repo TEXT,
    source_summary TEXT NOT NULL,
    duration_min_snapshot INTEGER NOT NULL,
    confirmed_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (schedule_id) REFERENCES todo_schedules(id) ON DELETE CASCADE,
    CHECK (duration_min_snapshot > 0),
    UNIQUE (schedule_id, source_date, source_summary, source_repo)
);
CREATE INDEX IF NOT EXISTS idx_schedule_actuals_schedule ON todo_schedule_actuals(schedule_id);
```

**db.py `_migrate`에 분기 추가 금지** — 신규 스키마는 schema.sql만 정의. 기존 라이브 DB에는 Step 4에서 1회성 수동 적용.

- [ ] **Step 4: 라이브 DB 1회성 수동 적용**

```bash
cp ~/life-dashboard/data.db ~/life-dashboard/data.db.bak.$(date +%Y%m%d-%H%M%S)
sqlite3 ~/life-dashboard/data.db < /tmp/task3-actuals.sql  # Step 3의 SQL을 임시 파일로 저장 후 실행
sqlite3 ~/life-dashboard/data.db "PRAGMA table_info(todo_schedule_actuals);"  # 검증
```

- [ ] **Step 5: Run tests pass**

```bash
cd mcp/life-dashboard && python -m pytest tests/test_todos.py -k "actuals" -v
```
Expected: 4 PASS (테스트는 `_setup_db()` 사용 — schema.sql 직접 로드)

- [ ] **Step 6: Commit**

```bash
git -C /Users/dayejeong/git_workplace/daye-agent-toolkit/.worktrees/capacity-tracking add mcp/life-dashboard/schema.sql mcp/life-dashboard/tests/test_todos.py
git -C /Users/dayejeong/git_workplace/daye-agent-toolkit/.worktrees/capacity-tracking commit -m "feat(schema): todo_schedule_actuals with immutable snapshot identity (no tasks FK)"
```

---

### Task 4: db.py — upsert_daily_checkin 시그니처 확장

**Files:** Modify `mcp/life-dashboard/db.py:647-670` (upsert_daily_checkin), Test `tests/test_todos.py`

- [ ] **Step 1: Write failing test**

```python
def test_upsert_daily_checkin_capacity_fields():
    from db import get_conn, upsert_daily_checkin, get_daily_checkin
    conn = get_conn()
    try:
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_min=300, available_status="answered",
            energy="mid", energy_status="answered",
            blockers="두통", blockers_status="answered",
        )
        ck = get_daily_checkin(conn, "2026-04-28")
        assert ck["available_min"] == 300
        assert ck["energy"] == "mid"
        assert ck["blockers"] == "두통"
        assert ck["available_status"] == "answered"
    finally:
        conn.close()


def test_upsert_daily_checkin_skip_status():
    from db import get_conn, upsert_daily_checkin, get_daily_checkin
    conn = get_conn()
    try:
        upsert_daily_checkin(
            conn, "2026-04-28",
            available_min=None, available_status="skipped",
        )
        ck = get_daily_checkin(conn, "2026-04-28")
        assert ck["available_min"] is None
        assert ck["available_status"] == "skipped"
    finally:
        conn.close()
```

- [ ] **Step 2: Run tests fail**

Expected: TypeError — `upsert_daily_checkin` 인자 모름

- [ ] **Step 3: Extend upsert_daily_checkin**

`mcp/life-dashboard/db.py`의 `upsert_daily_checkin`을 다음으로 교체:

```python
def upsert_daily_checkin(
    conn: sqlite3.Connection,
    date: str,
    *,
    morning_wip_ids: list[int] | None = None,
    morning_intent: str | None = None,
    evening_reflection: str | None = None,
    available_min: int | None = None,
    available_status: str | None = None,
    energy: str | None = None,
    energy_status: str | None = None,
    blockers: str | None = None,
    blockers_status: str | None = None,
) -> None:
    """daily_checkin upsert. 제공된 필드만 UPDATE (COALESCE).
    status 컬럼은 'answered'/'skipped'/'unknown' 중 하나.
    """
    wip_json = json.dumps(morning_wip_ids) if morning_wip_ids is not None else None
    conn.execute("""
        INSERT INTO daily_checkins (
            date, morning_wip_ids, morning_intent, evening_reflection,
            available_min, available_status, energy, energy_status, blockers, blockers_status
        )
        VALUES (
            :date, :wip, :intent, :reflection,
            :amin, COALESCE(:astatus,'unknown'), :energy, COALESCE(:estatus,'unknown'),
            :blockers, COALESCE(:bstatus,'unknown')
        )
        ON CONFLICT(date) DO UPDATE SET
            morning_wip_ids = COALESCE(excluded.morning_wip_ids, morning_wip_ids),
            morning_intent = COALESCE(excluded.morning_intent, morning_intent),
            evening_reflection = COALESCE(excluded.evening_reflection, evening_reflection),
            available_min = COALESCE(excluded.available_min, available_min),
            available_status = CASE WHEN :astatus IS NOT NULL THEN excluded.available_status ELSE available_status END,
            energy = COALESCE(excluded.energy, energy),
            energy_status = CASE WHEN :estatus IS NOT NULL THEN excluded.energy_status ELSE energy_status END,
            blockers = COALESCE(excluded.blockers, blockers),
            blockers_status = CASE WHEN :bstatus IS NOT NULL THEN excluded.blockers_status ELSE blockers_status END,
            updated_at = datetime('now','localtime')
    """, {
        "date": date, "wip": wip_json, "intent": morning_intent, "reflection": evening_reflection,
        "amin": available_min, "astatus": available_status,
        "energy": energy, "estatus": energy_status,
        "blockers": blockers, "bstatus": blockers_status,
    })
```

Note: status 인자가 None이면 기존 값 유지. 명시적으로 'answered'/'skipped'/'unknown' 넘겨야 변경.

- [ ] **Step 4: Tests pass**

```bash
cd mcp/life-dashboard && python -m pytest tests/test_todos.py -k "upsert_daily_checkin" -v
```

- [ ] **Step 5: Commit**

```
git ... add mcp/life-dashboard/db.py mcp/life-dashboard/tests/test_todos.py
git ... commit -m "feat(db): upsert_daily_checkin extended with capacity fields + status"
```

---

### Task 5: db.py — upsert_schedule (planned_min canonical)

**Files:** Modify `db.py`, Test `test_todos.py`

- [ ] **Step 1: Write failing test**

```python
def test_upsert_schedule_minutes_only():
    from db import get_conn, upsert_todo, upsert_schedule, get_schedule
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        sch = get_schedule(conn, sid)
        assert sch["planned_min"] == 120
        assert sch["start_at"] is None
    finally:
        conn.close()


def test_upsert_schedule_time_slot_auto_planned_min():
    """시간 슬롯이면 wrapper가 end-start 계산. db 함수는 planned_min 인자 그대로 받음."""
    from db import get_conn, upsert_todo, upsert_schedule, get_schedule
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28",
                              start_at="14:00", end_at="16:00", planned_min=120)
        sch = get_schedule(conn, sid)
        assert sch["start_at"] == "14:00"
        assert sch["planned_min"] == 120
    finally:
        conn.close()


def test_upsert_schedule_partial_unique_violation():
    import sqlite3
    from db import get_conn, upsert_todo, upsert_schedule
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        upsert_schedule(conn, todo_id=tid, date="2026-04-28",
                        start_at="14:00", end_at="16:00", planned_min=120)
        with pytest.raises(sqlite3.IntegrityError):
            upsert_schedule(conn, todo_id=tid, date="2026-04-28",
                            start_at="14:00", end_at="16:00", planned_min=120)
    finally:
        conn.rollback()
        conn.close()
```

- [ ] **Step 2: Run tests fail**

- [ ] **Step 3: Add upsert_schedule + get_schedule + get_schedules_by_date**

`db.py` 끝에 추가:

```python
def upsert_schedule(
    conn: sqlite3.Connection,
    *,
    todo_id: int,
    date: str,
    planned_min: int,
    start_at: str | None = None,
    end_at: str | None = None,
    notes: str | None = None,
) -> int:
    """todo_schedule INSERT. partial UNIQUE 위반 시 sqlite3.IntegrityError.
    planned_min은 항상 NOT NULL. wrapper가 시간 슬롯이면 end-start로 자동 계산해서 넘김.
    Returns: 생성된 schedule.id
    """
    cur = conn.execute("""
        INSERT INTO todo_schedules (todo_id, date, start_at, end_at, planned_min, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (todo_id, date, start_at, end_at, planned_min, notes))
    return cur.lastrowid


def get_schedule(conn: sqlite3.Connection, schedule_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM todo_schedules WHERE id = ?", (schedule_id,)).fetchone()
    return dict(row) if row else None


def get_schedules_by_date(conn: sqlite3.Connection, date: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM todo_schedules WHERE date = ? ORDER BY start_at NULLS LAST, id",
        (date,),
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```
git ... commit -m "feat(db): upsert_schedule + get_schedule + get_schedules_by_date"
```

---

### Task 6: db.py — link_schedule_actual (snapshot from tasks)

**Files:** Modify `db.py`, Test `test_todos.py`

- [ ] **Step 1: Write failing test**

```python
def test_link_schedule_actual_reads_from_tasks():
    """wrapper가 task에서 date/duration/summary/repo 자동 조회 → snapshot."""
    from db import get_conn, upsert_todo, upsert_schedule, link_schedule_actual
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        # task 삽입
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, repo, duration_min) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-28", "구현", "implement X", "repo Y", 90),
        )
        task_id = cur.lastrowid
        # actual link — 함수가 task에서 자동 조회
        actual_id = link_schedule_actual(conn, schedule_id=sid, task_id=task_id)
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
    """task.date != schedule.date면 거부."""
    from db import get_conn, upsert_todo, upsert_schedule, link_schedule_actual
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, duration_min) VALUES (?, ?, ?, ?)",
            ("2026-04-27", "구현", "wrong day task", 60),
        )
        task_id = cur.lastrowid
        with pytest.raises(ValueError, match="date mismatch"):
            link_schedule_actual(conn, schedule_id=sid, task_id=task_id)
    finally:
        conn.rollback()
        conn.close()
```

- [ ] **Step 2: Run tests fail**

- [ ] **Step 3: Add link_schedule_actual to db.py**

```python
def link_schedule_actual(
    conn: sqlite3.Connection,
    *,
    schedule_id: int,
    task_id: int,
) -> int:
    """task에서 date/duration/summary/repo 자동 조회 → snapshot으로 저장.
    schedule.date != task.date면 ValueError.
    UNIQUE 위반 시 sqlite3.IntegrityError.
    Returns: actual.id
    """
    sch = conn.execute(
        "SELECT date FROM todo_schedules WHERE id = ?", (schedule_id,)
    ).fetchone()
    if not sch:
        raise ValueError(f"schedule_id {schedule_id} not found")
    task = conn.execute(
        "SELECT date, summary, repo, duration_min FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if not task:
        raise ValueError(f"task_id {task_id} not found")
    if task["date"] != sch["date"]:
        raise ValueError(
            f"date mismatch: schedule.date={sch['date']} vs task.date={task['date']}"
        )
    cur = conn.execute("""
        INSERT INTO todo_schedule_actuals
            (schedule_id, source_task_id, source_date, source_repo, source_summary, duration_min_snapshot)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (schedule_id, task_id, task["date"], task["repo"], task["summary"], task["duration_min"]))
    return cur.lastrowid
```

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```
git ... commit -m "feat(db): link_schedule_actual reads task snapshot, validates date"
```

---

### Task 7: db.py — get_daily_checkins(start, end) range query

**Files:** Modify `db.py`, Test `test_todos.py`

- [ ] **Step 1: Write failing test**

```python
def test_get_daily_checkins_range():
    from db import get_conn, upsert_daily_checkin, get_daily_checkins
    conn = get_conn()
    try:
        upsert_daily_checkin(conn, "2026-04-25", available_min=360, available_status="answered")
        upsert_daily_checkin(conn, "2026-04-26", available_min=240, available_status="answered")
        upsert_daily_checkin(conn, "2026-04-28", available_min=300, available_status="answered")
        rows = get_daily_checkins(conn, "2026-04-25", "2026-04-27")
        dates = {r["date"] for r in rows}
        assert dates == {"2026-04-25", "2026-04-26"}
    finally:
        conn.close()
```

- [ ] **Step 2: Run test fail**

- [ ] **Step 3: Add get_daily_checkins**

```python
def get_daily_checkins(conn: sqlite3.Connection, start_date: str, end_date: str) -> list[dict]:
    """[start_date, end_date) 범위 daily_checkin row list. 날짜 ASC."""
    rows = conn.execute("""
        SELECT * FROM daily_checkins
        WHERE date >= ? AND date < ?
        ORDER BY date ASC
    """, (start_date, end_date)).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```
git ... commit -m "feat(db): get_daily_checkins range query"
```

---

### Task 8: db.py — get_capacity_status (4-way reconcile)

**Files:** Modify `db.py`, Test `test_todos.py`

- [ ] **Step 1: Write failing tests for 4 reconcile types**

```python
def test_capacity_status_under():
    from db import get_conn, upsert_todo, upsert_schedule, upsert_daily_checkin, get_capacity_status
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        upsert_daily_checkin(conn, "2026-04-28", available_min=300, available_status="answered")
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        st = get_capacity_status(conn, "2026-04-28")
        assert st["available_min"] == 300
        assert st["planned_min_total"] == 120
        assert st["planned_overbook"] is False
        assert st["missing_budget"] is False
    finally:
        conn.close()


def test_capacity_status_planned_overbook():
    from db import get_conn, upsert_todo, upsert_schedule, upsert_daily_checkin, get_capacity_status
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        upsert_daily_checkin(conn, "2026-04-28", available_min=120, available_status="answered")
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=180)
        st = get_capacity_status(conn, "2026-04-28")
        assert st["planned_overbook"] is True
    finally:
        conn.close()


def test_capacity_status_time_conflicts():
    from db import get_conn, upsert_todo, upsert_schedule, get_capacity_status
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", start_at="14:00", end_at="16:00", planned_min=120)
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", start_at="15:30", end_at="17:00", planned_min=90)
        st = get_capacity_status(conn, "2026-04-28")
        assert len(st["time_conflicts"]) == 1
        assert st["time_conflicts"][0]["overlap_min"] == 30
    finally:
        conn.close()


def test_capacity_status_missing_budget():
    """schedule 있는데 available_min NULL이고 status='unknown'이면 missing_budget=True."""
    from db import get_conn, upsert_todo, upsert_schedule, get_capacity_status
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=60)
        st = get_capacity_status(conn, "2026-04-28")
        assert st["missing_budget"] is True
        assert st["available_status"] == "unknown"
    finally:
        conn.close()
```

- [ ] **Step 2: Tests fail**

- [ ] **Step 3: Implement get_capacity_status**

```python
def _hhmm_to_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _time_overlap_min(a_start: str, a_end: str, b_start: str, b_end: str) -> int:
    a0, a1 = _hhmm_to_min(a_start), _hhmm_to_min(a_end)
    b0, b1 = _hhmm_to_min(b_start), _hhmm_to_min(b_end)
    return max(0, min(a1, b1) - max(a0, b0))


def get_capacity_status(conn: sqlite3.Connection, date: str) -> dict:
    """Reconcile capacity for a date. Returns 4-way status."""
    ck = conn.execute(
        "SELECT available_min, available_status FROM daily_checkins WHERE date = ?",
        (date,),
    ).fetchone()
    available_min = ck["available_min"] if ck else None
    available_status = ck["available_status"] if ck else "unknown"

    schedules = [dict(r) for r in conn.execute(
        "SELECT * FROM todo_schedules WHERE date = ? ORDER BY start_at NULLS LAST, id",
        (date,),
    ).fetchall()]

    planned_total = sum(s["planned_min"] for s in schedules)

    actual_total = (conn.execute("""
        SELECT COALESCE(SUM(a.duration_min_snapshot), 0)
        FROM todo_schedule_actuals a
        JOIN todo_schedules s ON s.id = a.schedule_id
        WHERE s.date = ?
    """, (date,)).fetchone()[0]) or 0

    # time conflicts: schedules with start_at, pairwise overlap > 0
    timed = [s for s in schedules if s["start_at"] and s["end_at"]]
    conflicts = []
    for i, a in enumerate(timed):
        for b in timed[i + 1:]:
            ov = _time_overlap_min(a["start_at"], a["end_at"], b["start_at"], b["end_at"])
            if ov > 0:
                conflicts.append({"a_id": a["id"], "b_id": b["id"], "overlap_min": ov})

    planned_overbook = available_min is not None and planned_total > available_min
    actual_overrun = available_min is not None and actual_total > available_min
    missing_budget = available_min is None and len(schedules) > 0
    remaining = (available_min - planned_total) if available_min is not None else None

    return {
        "available_min": available_min,
        "available_status": available_status,
        "planned_min_total": planned_total,
        "actual_min_total": actual_total,
        "planned_overbook": planned_overbook,
        "actual_overrun": actual_overrun,
        "time_conflicts": conflicts,
        "missing_budget": missing_budget,
        "remaining_min": remaining,
        "schedules": schedules,
    }
```

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```
git ... commit -m "feat(db): get_capacity_status with 4-way reconcile (overbook/overrun/conflicts/missing)"
```

---

### Task 9: scripts/checkin_save.py — morning subcommand

**Files:** Create `plugins/life-management/skills/life-coach/scripts/checkin_save.py`, Test via subprocess

- [ ] **Step 1: Write failing wrapper test**

`mcp/life-dashboard/tests/test_todos.py` 끝에:

```python
def test_checkin_save_morning_requires_value_or_skip():
    """morning subcommand: --available-hours 또는 --skip-available 둘 중 하나 필수."""
    import subprocess
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/checkin_save.py"
    r = subprocess.run(
        ["python3", str(script), "morning", "--date", "2026-04-28"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "available" in r.stderr.lower()


def test_checkin_save_morning_value():
    import subprocess, json
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/checkin_save.py"
    r = subprocess.run([
        "python3", str(script), "morning", "--date", "2026-04-28",
        "--available-hours", "5", "--skip-energy", "--skip-blockers",
        "--morning-intent", "test",
    ], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["available_min"] == 300
    assert out["available_status"] == "answered"
    assert out["energy_status"] == "skipped"
```

- [ ] **Step 2: Run tests fail**

- [ ] **Step 3: Create checkin_save.py with morning subcommand**

```python
#!/usr/bin/env python3
"""checkin_save — daily_checkin wrapper.

Subcommands:
  morning  — 캐파(available/energy/blockers) value/skip tri-state + intent + WIP ids
  evening  — reflection만

Usage:
  checkin_save.py morning --date YYYY-MM-DD
    (--available-hours N | --skip-available)
    (--energy low|mid|high | --skip-energy)
    (--blockers TEXT | --skip-blockers)
    [--morning-intent TEXT] [--wip-ids 13,20]

  checkin_save.py evening --date YYYY-MM-DD --evening-reflection TEXT
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "mcp" / "life-dashboard"))
from db import get_conn, upsert_daily_checkin, get_daily_checkin


def _resolve_tri_state(value, skip, name: str) -> tuple:
    if value is not None and skip:
        sys.exit(f"error: --{name} and --skip-{name} are mutually exclusive")
    if value is None and not skip:
        sys.exit(f"error: --{name} or --skip-{name} required")
    if skip:
        return None, "skipped"
    return value, "answered"


def cmd_morning(args):
    avail_value = int(args.available_hours * 60) if args.available_hours is not None else None
    avail_min, avail_status = _resolve_tri_state(avail_value, args.skip_available, "available")
    energy, energy_status = _resolve_tri_state(args.energy, args.skip_energy, "energy")
    blockers, blockers_status = _resolve_tri_state(args.blockers, args.skip_blockers, "blockers")
    wip_ids = [int(x) for x in args.wip_ids.split(",")] if args.wip_ids else None

    conn = get_conn()
    try:
        upsert_daily_checkin(
            conn, args.date,
            available_min=avail_min, available_status=avail_status,
            energy=energy, energy_status=energy_status,
            blockers=blockers, blockers_status=blockers_status,
            morning_intent=args.morning_intent,
            morning_wip_ids=wip_ids,
        )
        conn.commit()
        json.dump(get_daily_checkin(conn, args.date), sys.stdout, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


def cmd_evening(args):
    conn = get_conn()
    try:
        upsert_daily_checkin(conn, args.date, evening_reflection=args.evening_reflection)
        conn.commit()
        json.dump(get_daily_checkin(conn, args.date), sys.stdout, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("morning")
    m.add_argument("--date", required=True)
    m.add_argument("--available-hours", type=float)
    m.add_argument("--skip-available", action="store_true")
    m.add_argument("--energy", choices=["low", "mid", "high"])
    m.add_argument("--skip-energy", action="store_true")
    m.add_argument("--blockers")
    m.add_argument("--skip-blockers", action="store_true")
    m.add_argument("--morning-intent")
    m.add_argument("--wip-ids")
    m.set_defaults(func=cmd_morning)

    e = sub.add_parser("evening")
    e.add_argument("--date", required=True)
    e.add_argument("--evening-reflection", required=True)
    e.set_defaults(func=cmd_evening)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```
git ... add plugins/life-management/skills/life-coach/scripts/checkin_save.py mcp/life-dashboard/tests/test_todos.py
git ... commit -m "feat(scripts): checkin_save.py with morning/evening subcommands + tri-state args"
```

---

### Task 10: scripts/schedule_upsert.py

**Files:** Create wrapper, Test via subprocess

- [ ] **Step 1: Write failing tests**

```python
def test_schedule_upsert_minutes_only():
    import subprocess, json, sqlite3
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_upsert.py"
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    conn = get_conn()
    tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
    conn.commit()
    conn.close()
    r = subprocess.run([
        "python3", str(script), "--todo-id", str(tid),
        "--date", "2026-04-28", "--planned-min", "120",
    ], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["schedule"]["planned_min"] == 120
    assert "capacity_status" in out


def test_schedule_upsert_time_slot_auto_calc():
    import subprocess, json
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_upsert.py"
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    conn = get_conn()
    tid = upsert_todo(conn, title="t2", done_definition="d", category="업무")
    conn.commit()
    conn.close()
    r = subprocess.run([
        "python3", str(script), "--todo-id", str(tid),
        "--date", "2026-04-28", "--start", "14:00", "--end", "16:00",
    ], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["schedule"]["planned_min"] == 120
```

- [ ] **Step 2: Tests fail**

- [ ] **Step 3: Create schedule_upsert.py**

```python
#!/usr/bin/env python3
"""schedule_upsert — todo_schedule wrapper.

planned_min 자동 계산 (시간 슬롯이면 end-start).
Partial UNIQUE 위반 거부.
응답에 capacity_status 항상 포함.

Usage:
  schedule_upsert.py --todo-id N --date YYYY-MM-DD
    [--start HH:MM --end HH:MM]
    [--planned-min N]
    [--notes TEXT]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "mcp" / "life-dashboard"))
from db import get_conn, upsert_schedule, get_schedule, get_capacity_status


def _hhmm_to_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--todo-id", type=int, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--start", dest="start_at")
    ap.add_argument("--end", dest="end_at")
    ap.add_argument("--planned-min", type=int)
    ap.add_argument("--notes")
    args = ap.parse_args()

    if (args.start_at is None) != (args.end_at is None):
        sys.exit("error: --start and --end must be paired")

    if args.start_at:
        # auto-calc planned_min if not given
        calc = _hhmm_to_min(args.end_at) - _hhmm_to_min(args.start_at)
        if args.planned_min is None:
            args.planned_min = calc
        elif args.planned_min != calc:
            sys.exit(f"error: planned_min={args.planned_min} != end-start={calc}")
    else:
        if args.planned_min is None:
            sys.exit("error: --planned-min required when no time slot")

    conn = get_conn()
    try:
        try:
            sid = upsert_schedule(
                conn, todo_id=args.todo_id, date=args.date,
                start_at=args.start_at, end_at=args.end_at,
                planned_min=args.planned_min, notes=args.notes,
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            sys.exit(f"error: schedule constraint violation: {e}")

        result = {
            "schedule": get_schedule(conn, sid),
            "capacity_status": get_capacity_status(conn, args.date),
        }
        json.dump(result, sys.stdout, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```
git ... commit -m "feat(scripts): schedule_upsert.py with auto planned_min + capacity_status response"
```

---

### Task 11: scripts/schedule_actual_link.py

**Files:** Create wrapper, Test via subprocess

- [ ] **Step 1: Write failing tests**

```python
def test_schedule_actual_link_reads_task():
    import subprocess, json
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py"
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo, upsert_schedule
    conn = get_conn()
    try:
        tid = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        sid = upsert_schedule(conn, todo_id=tid, date="2026-04-28", planned_min=120)
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, repo, duration_min) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-28", "구현", "task X", "repo Y", 90),
        )
        task_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    r = subprocess.run([
        "python3", str(script), "--schedule-id", str(sid),
        "--task-id", str(task_id),
        "--date", "2026-04-28", "--todo-id", str(tid),
    ], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["actual"]["duration_min_snapshot"] == 90
    assert out["actual"]["source_summary"] == "task X"


def test_schedule_actual_link_rejects_id_mismatch():
    """schedule이 다른 todo면 거부."""
    import subprocess
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py"
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo, upsert_schedule
    conn = get_conn()
    try:
        t1 = upsert_todo(conn, title="t1", done_definition="d", category="업무")
        t2 = upsert_todo(conn, title="t2", done_definition="d", category="업무")
        sid = upsert_schedule(conn, todo_id=t1, date="2026-04-28", planned_min=60)
        cur = conn.execute(
            "INSERT INTO tasks (date, tag, summary, duration_min) VALUES (?, ?, ?, ?)",
            ("2026-04-28", "구현", "task A", 60),
        )
        task_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    r = subprocess.run([
        "python3", str(script), "--schedule-id", str(sid),
        "--task-id", str(task_id),
        "--date", "2026-04-28", "--todo-id", str(t2),  # mismatch
    ], capture_output=True, text=True)
    assert r.returncode != 0
    assert "todo" in r.stderr.lower() or "mismatch" in r.stderr.lower()
```

- [ ] **Step 2: Tests fail**

- [ ] **Step 3: Create schedule_actual_link.py**

```python
#!/usr/bin/env python3
"""schedule_actual_link — actual 브리지 wrapper.

wrapper가 task에서 date/duration/summary/repo 자동 조회 → snapshot.
schedule identity (date, todo_id) 재검증.
UNIQUE 4-tuple 위반 거부.

Usage:
  schedule_actual_link.py
    --schedule-id N --task-id M
    --date YYYY-MM-DD --todo-id K
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "mcp" / "life-dashboard"))
from db import get_conn, link_schedule_actual, get_capacity_status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule-id", type=int, required=True)
    ap.add_argument("--task-id", type=int, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--todo-id", type=int, required=True)
    args = ap.parse_args()

    conn = get_conn()
    try:
        # schedule identity 재검증
        sch = conn.execute(
            "SELECT date, todo_id FROM todo_schedules WHERE id = ?", (args.schedule_id,)
        ).fetchone()
        if not sch:
            sys.exit(f"error: schedule_id {args.schedule_id} not found")
        if sch["date"] != args.date:
            sys.exit(f"error: schedule.date={sch['date']} vs --date {args.date} mismatch")
        if sch["todo_id"] != args.todo_id:
            sys.exit(f"error: schedule.todo_id={sch['todo_id']} vs --todo-id {args.todo_id} mismatch")

        try:
            actual_id = link_schedule_actual(
                conn, schedule_id=args.schedule_id, task_id=args.task_id
            )
            conn.commit()
        except ValueError as e:
            sys.exit(f"error: {e}")
        except sqlite3.IntegrityError as e:
            sys.exit(f"error: actual constraint violation: {e}")

        actual = dict(conn.execute(
            "SELECT * FROM todo_schedule_actuals WHERE id = ?", (actual_id,)
        ).fetchone())
        result = {
            "actual": actual,
            "capacity_status": get_capacity_status(conn, args.date),
        }
        json.dump(result, sys.stdout, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```
git ... commit -m "feat(scripts): schedule_actual_link.py with task auto-snapshot + identity recheck"
```

---

### Task 12: scripts/capacity.py — markdown table output

**Files:** Create wrapper, Test via subprocess

- [ ] **Step 1: Write failing test**

```python
def test_capacity_script_markdown_output():
    import subprocess
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/capacity.py"
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_daily_checkin
    conn = get_conn()
    try:
        upsert_daily_checkin(conn, "2026-04-28", available_min=300, available_status="answered", energy="mid", energy_status="answered")
        conn.commit()
    finally:
        conn.close()
    r = subprocess.run([
        "python3", str(script), "--start", "2026-04-28", "--end", "2026-04-29",
    ], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "| 날짜 |" in r.stdout
    assert "2026-04-28" in r.stdout or "04-28" in r.stdout
```

- [ ] **Step 2: Test fail**

- [ ] **Step 3: Create capacity.py**

```python
#!/usr/bin/env python3
"""capacity — 누적 캐파 조회 + 4종 flag.

Usage:
  capacity.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]

기본: 최근 7일.
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "mcp" / "life-dashboard"))
from db import get_conn, get_daily_checkins, get_capacity_status

KST = ZoneInfo("Asia/Seoul")


def _fmt_h(minutes: int | None) -> str:
    if minutes is None:
        return "-"
    return f"{minutes / 60:.1f}h" if minutes else "0h"


def _status_str(st: dict) -> str:
    flags = []
    if st["available_status"] == "skipped":
        return "ℹ skipped"
    if st["missing_budget"]:
        flags.append("⚠ missing_budget")
    if st["planned_overbook"]:
        flags.append("⚠ planned_overbook")
    if st["actual_overrun"]:
        flags.append("⚠ actual_overrun")
    if st["time_conflicts"]:
        flags.append(f"⚠ time_conflicts({len(st['time_conflicts'])})")
    return ", ".join(flags) or "OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start")
    ap.add_argument("--end")
    args = ap.parse_args()

    today = datetime.now(KST).date()
    if not args.end:
        args.end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if not args.start:
        args.start = (today - timedelta(days=6)).strftime("%Y-%m-%d")

    conn = get_conn()
    try:
        rows = get_daily_checkins(conn, args.start, args.end)
        if not rows:
            print(f"(no daily_checkins in {args.start} ~ {args.end})")
            return

        print("| 날짜 | 가용 | 계획 | 실측 | 잔여 | 에너지 | 블로커 | 상태 |")
        print("|------|------|------|------|------|--------|--------|------|")
        for r in rows:
            st = get_capacity_status(conn, r["date"])
            avail = "(skipped)" if r["available_status"] == "skipped" else _fmt_h(r["available_min"])
            energy = r["energy"] or ("(skipped)" if r["energy_status"] == "skipped" else "-")
            blockers = (r["blockers"] or "")[:20] if r["blockers"] else ("(skipped)" if r["blockers_status"] == "skipped" else "-")
            print(f"| {r['date'][5:]} | {avail} | {_fmt_h(st['planned_min_total'])} | {_fmt_h(st['actual_min_total'])} | {_fmt_h(st['remaining_min'])} | {energy} | {blockers} | {_status_str(st)} |")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test pass**

- [ ] **Step 5: Commit**

```
git ... commit -m "feat(scripts): capacity.py with markdown table + 4-way flags"
```

---

### Task 13: scripts/todo_crud.py — estimated_min tri-state

**Files:** Modify `plugins/life-management/skills/life-coach/scripts/todo_crud.py`

- [ ] **Step 1: Write failing test**

```python
def test_todo_crud_add_requires_estimated_or_skip():
    import subprocess
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/todo_crud.py"
    r = subprocess.run([
        "python3", str(script), "add", "--title", "t", "--done-definition", "d", "--category", "업무",
    ], capture_output=True, text=True)
    assert r.returncode != 0
    assert "estimated" in r.stderr.lower()


def test_todo_crud_move_wip_requires_estimated():
    import subprocess
    repo = Path(__file__).resolve().parents[3]
    script = repo / "plugins/life-management/skills/life-coach/scripts/todo_crud.py"
    sys.path.insert(0, str(repo / "mcp/life-dashboard"))
    from db import get_conn, upsert_todo
    conn = get_conn()
    tid = upsert_todo(conn, title="x", done_definition="d", category="업무")
    conn.commit()
    conn.close()
    r = subprocess.run([
        "python3", str(script), "move", "--id", str(tid), "--status", "wip",
    ], capture_output=True, text=True)
    assert r.returncode != 0
    assert "estimated" in r.stderr.lower()
```

- [ ] **Step 2: Tests fail**

- [ ] **Step 3: Modify todo_crud.py — add cmd**

`todo_crud.py`의 `add` subcommand argparse에:
- `--estimated-min` (existing) 유지
- `--skip-estimated` (action="store_true") 추가

`add` handler 시작 부분에:

```python
if args.estimated_min is None and not args.skip_estimated:
    sys.exit("error: --estimated-min N or --skip-estimated required")
if args.estimated_min is not None and args.skip_estimated:
    sys.exit("error: --estimated-min and --skip-estimated mutually exclusive")
```

`move` handler에 wip 전환 전 검증 추가:

```python
if args.status == "wip":
    row = conn.execute("SELECT estimated_min FROM todos WHERE id = ?", (args.id,)).fetchone()
    if row and row["estimated_min"] is None and not args.skip_estimated_check:
        sys.exit(f"error: todo {args.id} estimated_min is NULL. Set --estimated-min or pass --skip-estimated-check to override")
```

`move` argparse에 `--skip-estimated-check` 옵션 추가.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```
git ... commit -m "feat(todo_crud): tri-state estimated_min on add + WIP transition check"
```

---

### Task 14: commands/morning.md

**Files:** Create `plugins/life-management/commands/morning.md`

- [ ] **Step 1: Create file**

```markdown
---
description: 아침 액션 — 우선순위 + 캐파 인터뷰 + WIP/슬롯 잡기
allowed-tools: Bash, Read
---

# /morning

매일 아침 1회 호출. life-coach skill의 **morning 액션** 진입점.

## 절차

1. `python3 plugins/life-management/skills/life-coach/scripts/todo_morning.py --date <오늘>` → 우선순위 JSON
2. 사용자에게 우선순위 제시 + 캐파 인터뷰 (life-coach SKILL.md §인터뷰 가이드라인 참조)
3. 사용자 답변을 wrapper로 저장:
   ```bash
   python3 plugins/life-management/skills/life-coach/scripts/checkin_save.py morning \
     --date <오늘> \
     (--available-hours N | --skip-available) \
     (--energy low|mid|high | --skip-energy) \
     (--blockers TEXT | --skip-blockers) \
     [--morning-intent TEXT] [--wip-ids 13,20]
   ```
4. WIP 슬롯 잡기:
   ```bash
   python3 plugins/life-management/skills/life-coach/scripts/schedule_upsert.py \
     --todo-id N --date <오늘> [--planned-min M | --start HH:MM --end HH:MM]
   ```
5. `python3 plugins/life-management/skills/life-coach/scripts/capacity.py --start <오늘> --end <내일>` → overbook/conflict 보고

## 룰

- 모든 read/write는 wrapper 경유. db.py 직접 호출 금지.
- 캐파 답이 모호하면 명확해질 때까지 재질문. "스킵" 명시일 때만 `--skip-*`.
- WIP limit 2 (todo_crud.py가 강제)
```

- [ ] **Step 2: Verify file exists**

```bash
ls plugins/life-management/commands/morning.md
```

- [ ] **Step 3: Commit**

```
git ... commit -m "feat(commands): /morning entry point"
```

---

### Task 15: commands/evening.md

**Files:** Create `plugins/life-management/commands/evening.md`

- [ ] **Step 1: Create file**

```markdown
---
description: 저녁 액션 — 계획 vs 실제 + actual 매칭 + reflection
allowed-tools: Bash, Read
---

# /evening

매일 저녁 1회. life-coach **evening 액션** 진입점.

## 절차

1. `python3 plugins/life-management/skills/life-coach/scripts/todo_evening.py --date <오늘>` → 계획 vs 실제 + loose match JSON
2. 매칭된 task 후보 제시 → 사용자 confirm:
   ```bash
   python3 plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py \
     --schedule-id N --task-id M --date <오늘> --todo-id K
   ```
   - wrapper가 task에서 date/duration/summary/repo 자동 조회
   - identity 재검증 + UNIQUE 4-tuple 검증
3. 매칭 거부/스킵이면 새 schedule 생성 후 매칭:
   ```bash
   schedule_upsert.py ... && schedule_actual_link.py ...
   ```
4. reflection 저장:
   ```bash
   python3 plugins/life-management/skills/life-coach/scripts/checkin_save.py evening \
     --date <오늘> --evening-reflection TEXT
   ```

## 룰

- actual 매칭은 schedule_id 명시 confirmation 후에만
- task duration은 wrapper가 task table에서 직접 읽음 (에이전트 입력 X)
```

- [ ] **Step 2-3: Verify + Commit**

```
git ... commit -m "feat(commands): /evening entry point"
```

---

### Task 16: commands/capacity.md

**Files:** Create `plugins/life-management/commands/capacity.md`

- [ ] **Step 1: Create file**

```markdown
---
description: 캐파 누적 조회 — markdown 표 + 4종 flag
allowed-tools: Bash, Read
---

# /capacity

캐파 데이터 누적 조회. 기본 최근 7일.

## 실행

```bash
python3 plugins/life-management/skills/life-coach/scripts/capacity.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

## 출력

markdown 표:

| 날짜 | 가용 | 계획 | 실측 | 잔여 | 에너지 | 블로커 | 상태 |

상태 4종:
- `OK` — 정상
- `⚠ planned_overbook` — `sum(planned_min) > available_min`
- `⚠ actual_overrun` — `sum(actual) > available_min`
- `⚠ time_conflicts(N)` — schedule 시간대 겹침
- `⚠ missing_budget` — schedule 있는데 캐파 답 안 함
- `ℹ skipped` — 캐파 명시 스킵
```

- [ ] **Step 2-3: Verify + Commit**

```
git ... commit -m "feat(commands): /capacity entry point"
```

---

### Task 17: SKILL.md update

**Files:** Modify `plugins/life-management/skills/life-coach/SKILL.md`

- [ ] **Step 1: Update sections**

`SKILL.md`에서 다음 변경:

(a) 슬래시 커맨드 섹션에 추가:

```markdown
| Command | 용도 |
|---------|------|
| `/morning` | 매일 아침 — 캐파 인터뷰 + WIP/슬롯 |
| `/evening` | 매일 저녁 — actual 매칭 + reflection |
| `/capacity` | 누적 캐파 조회 + 4종 flag |
| `/todo-list` | 전체 todo 단일 테이블 출력 |
```

(b) "축 1 액션 워크플로우" 섹션의 아침/저녁 액션 절차를 wrapper 호출 형태로 갱신 (commands/morning.md, evening.md 참조).

(c) 새 섹션 "인터뷰 가이드라인" 추가:

```markdown
### 인터뷰 가이드라인

매일 아침/저녁 인터뷰 시 따르는 룰. 데이터 정확도와 silent NULL 차단의 핵심.

**추출 룰**:
- **가용시간**: 숫자 명시 → `--available-hours N`. 모호("오전만") → 명확해질 때까지 재질문
- **에너지**: 키워드 매핑
  - `low`: "쩔쩔매", "방전", "지침", "피곤"
  - `mid`: "보통", "그럭저럭", "괜찮"
  - `high`: "쌩쌩", "활기", "좋음"
  - 매핑 안 되면 명확해질 때까지 재질문
- **블로커**: 자유 텍스트
- **actual schedule**: loose match 후보 제시 → 사용자가 schedule_id 명시 선택

**스킵 처리**:
- 사용자 "스킵"/"넘겨" 명시 → wrapper에 `--skip-*` 인자 → DB status='skipped' 기록
- 그 외엔 답할 때까지 인터뷰 (silent NULL 차단)

**캐파 단일 소스**: `daily_checkins.available_min`이 진실. schedule sum 초과 시 reconcile flag로 보고만 (강제 차단 X).

**SoT 룰**: 에이전트는 wrapper CLI만 호출. db.py 직접 호출 금지. 읽기도 wrapper(`capacity.py`) 경유.
```

- [ ] **Step 2: Verify SKILL.md still under 150 lines**

```bash
wc -l plugins/life-management/skills/life-coach/SKILL.md
```

150 line 초과면 detail은 references/ 로 분리.

- [ ] **Step 3: Commit**

```
git ... commit -m "docs(SKILL): /morning /evening /capacity commands + interview guidelines + SoT rules"
```

---

### Task 18: Final verification + ship-readiness

**Files:** All

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/.worktrees/capacity-tracking/mcp/life-dashboard && python -m pytest tests/test_todos.py -v
```
Expected: All tests PASS

- [ ] **Step 2: Smoke test full flow**

```bash
DATE=$(date +%Y-%m-%d)
TODO_ID=$(python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py add --title "smoke" --done-definition "d" --category 업무 --estimated-min 60 | jq -r .id)
python3 plugins/life-management/skills/life-coach/scripts/checkin_save.py morning --date $DATE --available-hours 5 --energy mid --skip-blockers --wip-ids $TODO_ID
python3 plugins/life-management/skills/life-coach/scripts/schedule_upsert.py --todo-id $TODO_ID --date $DATE --planned-min 60
python3 plugins/life-management/skills/life-coach/scripts/capacity.py --start $DATE --end $(date -v+1d +%Y-%m-%d)
python3 plugins/life-management/skills/life-coach/scripts/checkin_save.py evening --date $DATE --evening-reflection "smoke test"
python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py done --id $TODO_ID
```

Expected: 모든 명령 exit 0, capacity.py 출력에 1 row.

- [ ] **Step 3: Verify silent fail 회귀**

`tests/test_todos.py`에 회귀 테스트 추가 + 실행:
- task 삭제 후 actual 보존 (Task 3에서 작성됨, 통과 확인)
- partial UNIQUE 위반 거부
- tri-state missing 거부
- date mismatch 거부

- [ ] **Step 4: Final commit + push**

```bash
git -C /Users/dayejeong/git_workplace/daye-agent-toolkit/.worktrees/capacity-tracking log --oneline | head -20
```

worktree commit 정리 → master 머지 준비.

- [ ] **Step 5: Update SKILL.md / docs / changelog if needed**

ship 후 별도 작업 (master 머지 + 후속 todo 등록: #38, #36/#37 일정).

---

## Self-review checklist

작성 후:

1. **Spec coverage**: spec §4-12 각 섹션이 task로 매핑됐나?
   - §4 schema → Task 1, 2, 3 ✓
   - §5 reconcile → Task 8 ✓
   - §6 commands → Task 14, 15, 16 ✓
   - §7 데이터 플로우 → Task 9, 10, 11, 12 (wrapper) ✓
   - §8 estimated_min → Task 13 ✓
   - §9 인터뷰 → Task 17 ✓
   - §10 에러 처리 → 각 wrapper에 분산 ✓
   - §11 테스트 → 각 task 안 ✓
   - §12 변경 파일 12개 → 모두 cover ✓
   - §13 단계 commit → task 순서 일치 ✓
2. **Placeholder**: 없음 ✓
3. **Type consistency**: `upsert_schedule` 시그니처 Task 5 정의 ↔ Task 10 wrapper 호출 일관 ✓. `link_schedule_actual` 시그니처 Task 6 ↔ Task 11 일관 ✓.

---

## Execution

총 task 18개. TDD per task. 각 task 후 commit. 단계별 commit으로 bisect/rollback 용이.

**우선 순위**: 1 → 2 → 3 (schema) → 4-8 (db) → 9-13 (scripts) → 14-16 (commands) → 17 (SKILL) → 18 (verify).

스키마/db 함수까지 끝나면 wrapper는 병렬 진행 가능 (subagent-driven).
