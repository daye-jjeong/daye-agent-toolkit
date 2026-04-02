# Task/Project 기반 작업 기록 재설계 — 구현 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** session_topics를 tasks+projects 테이블로 대체하여, segment 기반 의미적 작업 묶음 + project 단위 장기 추적을 구현한다.

**Architecture:** schema.sql에 projects/tasks 테이블 추가 → db.py에 CRUD 함수 → activity_writer.py CLI 교체 → extract_day.py에 --flat 모드 → timeline_html/daily_report/daily_coach를 tasks 기반으로 전환 → 마이그레이션 스크립트로 기존 데이터 변환 → SKILL.md/가이드 재작성.

**Tech Stack:** Python 3.12, SQLite, pytest

**Spec:** `docs/specs/2026-04-01-task-project-redesign.md`

---

## 파일 구조

| 파일 | 역할 | 변경 |
|------|------|------|
| `shared/life-dashboard-mcp/schema.sql` | DB 스키마 | projects, tasks 테이블 추가 |
| `shared/life-dashboard-mcp/db.py` | DB 접근 레이어 | upsert_tasks, get_tasks, upsert_project, get_projects, 마이그레이션 |
| `shared/life-dashboard-mcp/activity_writer.py` | CLI | update-topics → update-tasks |
| `shared/life-dashboard-mcp/tests/test_session_topics.py` | 테스트 | → test_tasks.py로 재작성 |
| `cc/work-digest/scripts/extract_day.py` | segment 추출 | --flat 모드 추가 |
| `shared/life-coach/scripts/timeline_html.py` | 타임라인 렌더링 | segments 기반 |
| `shared/life-coach/scripts/daily_coach.py` | 데이터 수집 | get_session_topics → get_tasks |
| `shared/life-coach/scripts/daily_report.py` | HTML 리포트 | topic → task 기반 |
| `shared/life-coach/scripts/_helpers.py` | 공유 헬퍼 | group_topics_by_repo → group_tasks_by_repo |
| `cc/work-digest/scripts/validate_topics.py` | 검증 | → validate_tasks.py |
| `cc/work-digest/SKILL.md` | 스킬 가이드 | Step 4~5 재작성 |
| `cc/work-digest/references/topic-creation-guide.md` | 토픽 가이드 | task 기반으로 재작성 |

---

### Task 1: 스키마 + DB 함수 (projects, tasks)

**Files:**
- Modify: `shared/life-dashboard-mcp/schema.sql:73-98`
- Modify: `shared/life-dashboard-mcp/db.py:106-120,192-270`
- Create: `shared/life-dashboard-mcp/tests/test_tasks.py`

- [ ] **Step 1: test_tasks.py — projects CRUD 테스트 작성**

```python
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
```

- [ ] **Step 2: test_tasks.py — tasks CRUD 테스트 작성**

아래를 같은 파일에 추가:

```python
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
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

Run: `python3 -m pytest shared/life-dashboard-mcp/tests/test_tasks.py -v`
Expected: FAIL — `upsert_project`, `get_projects`, `upsert_tasks`, `get_tasks` 없음

- [ ] **Step 4: schema.sql에 projects, tasks 테이블 추가**

`shared/life-dashboard-mcp/schema.sql`의 session_topics 블록(라인 73-98) **뒤에** 추가:

```sql
-- ── Projects ──────────────────────────────────

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    repo TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(name, repo)
);

-- ── Tasks (replaces session_topics) ───────────

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    tag TEXT NOT NULL,
    summary TEXT NOT NULL,
    repo TEXT,
    segments TEXT NOT NULL DEFAULT '[]',
    duration_min INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'completed',
    follow_up TEXT,
    project_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(date);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
```

- [ ] **Step 5: db.py에 CRUD 함수 추가**

`shared/life-dashboard-mcp/db.py`에 `get_session_topics` 함수 뒤에 추가:

```python
_VALID_TASK_TAGS = {"코딩", "디버깅", "리서치", "리뷰", "ops", "설정", "문서", "설계", "리팩토링", "기타"}


def upsert_project(conn: sqlite3.Connection, name: str, repo: str | None = None) -> int:
    """project를 가져오거나 없으면 생성. id 반환."""
    row = conn.execute(
        "SELECT id FROM projects WHERE name = ? AND repo IS ?", (name, repo)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE projects SET updated_at = datetime('now','localtime') WHERE id = ?",
            (row["id"],),
        )
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO projects (name, repo) VALUES (?, ?)", (name, repo)
    )
    return cursor.lastrowid


def get_projects(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    """프로젝트 목록 조회. status 필터 가능."""
    if status:
        rows = conn.execute("SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def upsert_tasks(conn: sqlite3.Connection, date: str, tasks: list[dict]):
    """하루치 tasks 전체 교체 (DELETE + INSERT)."""
    conn.execute("DELETE FROM tasks WHERE date = ?", (date,))
    for t in tasks:
        tag = t.get("tag", "기타")
        if tag not in _VALID_TASK_TAGS:
            tag = "기타"
        summary = t.get("summary", "")
        if not summary:
            continue
        segments = t.get("segments", [])
        segments_json = json.dumps(segments, ensure_ascii=False) if isinstance(segments, list) else segments
        duration_min = t.get("duration_min", 0) or 0
        conn.execute("""
            INSERT INTO tasks (date, tag, summary, repo, segments, duration_min, status, follow_up, project_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date, tag, summary, t.get("repo"), segments_json, duration_min,
            t.get("status", "completed"), t.get("follow_up"), t.get("project_id"),
        ))


def get_tasks(conn: sqlite3.Connection, date: str) -> list[dict]:
    """해당 날짜의 모든 tasks 조회."""
    rows = conn.execute("""
        SELECT t.*, p.name as project_name
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.date = ?
        ORDER BY t.id
    """, (date,)).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 6: db.py의 update_daily_stats에서 session_topics → tasks 폴백 추가**

`shared/life-dashboard-mcp/db.py:117-130`의 tag_breakdown 로직을 수정:

```python
    # tag_breakdown: tasks 우선 → session_topics 폴백 → sessions.tag 폴백
    task_rows = conn.execute(
        "SELECT tag FROM tasks WHERE date = ?", (date_str,)
    ).fetchall()
    topic_rows = conn.execute(
        "SELECT tag FROM session_topics WHERE date = ?", (date_str,)
    ).fetchall() if not task_rows else []

    tags: dict[str, int] = {}
    tag_source = task_rows or topic_rows
    if tag_source:
        for r in tag_source:
            tag = r["tag"] or "기타"
            tags[tag] = tags.get(tag, 0) + 1
    else:
        for r in rows:
            tag = r["tag"] or "기타"
            tags[tag] = tags.get(tag, 0) + 1
```

- [ ] **Step 7: db.py에 마이그레이션 함수 추가**

`_migrate` 함수(db.py:34)에 tasks/projects 테이블 자동 생성 추가:

```python
    # tasks + projects 테이블 마이그레이션
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "projects" not in existing:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                repo TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                UNIQUE(name, repo)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                tag TEXT NOT NULL,
                summary TEXT NOT NULL,
                repo TEXT,
                segments TEXT NOT NULL DEFAULT '[]',
                duration_min INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'completed',
                follow_up TEXT,
                project_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(date);
            CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
        """)
        conn.commit()
```

- [ ] **Step 8: 테스트 실행 — 통과 확인**

Run: `python3 -m pytest shared/life-dashboard-mcp/tests/test_tasks.py -v`
Expected: 전부 PASS

- [ ] **Step 9: 커밋**

```bash
git add shared/life-dashboard-mcp/schema.sql shared/life-dashboard-mcp/db.py shared/life-dashboard-mcp/tests/test_tasks.py
git commit -m "feat: projects + tasks 스키마 및 CRUD 함수 추가"
```

---

### Task 2: activity_writer.py — update-tasks CLI

**Files:**
- Modify: `shared/life-dashboard-mcp/activity_writer.py:320-346,451-454`

- [ ] **Step 1: cmd_update_tasks 함수 작성**

`shared/life-dashboard-mcp/activity_writer.py`의 `cmd_update_topics` 함수(라인 320) 아래에 추가:

```python
def cmd_update_tasks(args):
    """하루치 tasks 전체 교체."""
    try:
        tasks = json.loads(args.tasks)
    except json.JSONDecodeError as e:
        print(f"Error: --tasks is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(tasks, list) or not tasks:
        print("Error: --tasks must be a non-empty JSON array", file=sys.stderr)
        sys.exit(1)

    conn = get_conn()
    try:
        # project 연결 처리
        for t in tasks:
            project_name = t.pop("project", None)
            if project_name:
                from db import upsert_project
                t["project_id"] = upsert_project(conn, project_name, repo=t.get("repo"))

        from db import upsert_tasks
        upsert_tasks(conn, args.date, tasks)
        update_daily_stats(conn, args.date)
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE date = ?", (args.date,)
        ).fetchone()[0]
        print(f"Updated {count} tasks for {args.date}", file=sys.stderr)
    except Exception as e:
        conn.rollback()
        print(f"Error: DB operation failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()
```

- [ ] **Step 2: argparse에 update-tasks 서브커맨드 등록**

`activity_writer.py` 라인 451 부근, `p_topics` 다음에 추가:

```python
    p_tasks = sub.add_parser("update-tasks", help="Replace daily tasks")
    p_tasks.add_argument("--date", required=True)
    p_tasks.add_argument("--tasks", required=True, help='JSON array: [{"tag":"..","summary":"..","repo":"..","segments":[...],"project":".."}]')
```

dispatch dict에 추가:

```python
        "update-tasks": cmd_update_tasks,
```

- [ ] **Step 3: CLI 테스트**

Run:
```bash
python3 shared/life-dashboard-mcp/activity_writer.py update-tasks \
    --date 2026-03-31 \
    --tasks '[{"tag":"설계","summary":"테스트 task","repo":"test","segments":[],"duration_min":10}]'
```
Expected: `Updated 1 tasks for 2026-03-31`

- [ ] **Step 4: 커밋**

```bash
git add shared/life-dashboard-mcp/activity_writer.py
git commit -m "feat: update-tasks CLI 서브커맨드 추가"
```

---

### Task 3: extract_day.py — --flat 모드

**Files:**
- Modify: `cc/work-digest/scripts/extract_day.py:136-175`

- [ ] **Step 1: flatten_by_repo 함수 작성**

`cc/work-digest/scripts/extract_day.py`의 `main()` 함수 앞에 추가:

```python
_NOISE_PREFIXES = ("<task-notification", "Base directory for this skill:")


def _clean_hint(messages: list[str]) -> str:
    """첫 의미있는 사용자 메시지에서 hint 추출."""
    for m in messages:
        if any(m.startswith(p) for p in _NOISE_PREFIXES):
            continue
        if m.startswith("/") and len(m) < 20:  # /exit, /clear 등
            continue
        return m[:60].replace("\n", " ").strip()
    return ""


def flatten_by_repo(session_segments: list[dict]) -> dict[str, list[dict]]:
    """세션별 segments → 레포별 시간순 flat list."""
    by_repo: dict[str, list[dict]] = {}
    for s in session_segments:
        repo = (s.get("repo") or "unknown").split("/")[-1]
        for seg in s.get("segments", []):
            by_repo.setdefault(repo, []).append({
                "sid": s["session_id"],
                "start": seg["start"],
                "end": seg["end"],
                "dur": seg["duration_min"],
                "hint": _clean_hint(seg.get("message_texts", [])),
                "files": seg.get("file_names", []),
            })
    # 레포별 시간순 정렬
    for segs in by_repo.values():
        segs.sort(key=lambda x: x["start"])
    return by_repo
```

- [ ] **Step 2: main()에 --flat 플래그 추가**

```python
    ap.add_argument("--flat", action="store_true", help="레포별 시간순 flat list 출력")
```

output 생성 후, `json.dump` 앞에 분기:

```python
    if args.flat:
        flat = flatten_by_repo(output)
        json.dump(flat, sys.stdout, ensure_ascii=False, indent=2)
    else:
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
```

- [ ] **Step 3: 테스트 실행**

Run: `python3 cc/work-digest/scripts/extract_day.py --date 2026-03-31 --no-scan --flat 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(list(d.keys())); print(len([s for ss in d.values() for s in ss]), 'segments')"`

Expected: 레포 이름 리스트 + segment 개수

- [ ] **Step 4: 커밋**

```bash
git add cc/work-digest/scripts/extract_day.py
git commit -m "feat: extract_day.py --flat 모드 — 레포별 시간순 segment list"
```

---

### Task 4: timeline_html.py — segments 기반 렌더링

**Files:**
- Modify: `shared/life-coach/scripts/timeline_html.py:34-102`

- [ ] **Step 1: prep() 함수에 tasks 경로 추가**

현재 `prep(sessions, topics=None)` 시그니처를 `prep(sessions, topics=None, tasks=None)`으로 변경.

tasks가 있으면 topics/sessions 대신 tasks의 segments를 사용:

```python
def prep(sessions, topics=None, tasks=None):
    """타임라인 데이터 생성. tasks 있으면 segment 기반, 없으면 기존 로직."""
    if tasks:
        items = []
        for t in tasks:
            segments = t.get("segments", [])
            if isinstance(segments, str):
                segments = json.loads(segments)
            tag = t.get("tag") or "기타"
            repo = (t.get("repo") or "?").split("/")[-1]
            summary = (t.get("summary") or "")[:100]
            for seg in segments:
                items.append({
                    "repo": repo,
                    "tag": tag,
                    "start": seg.get("start", "00:00"),
                    "duration": seg.get("dur", 30),
                    "summary": summary,
                })
        return sorted(items, key=lambda x: x["start"]) if items else []

    if topics:
        # ... 기존 topics 로직 유지 (폴백)
```

- [ ] **Step 2: build() 함수에서 tasks 전달**

`build()` 함수의 daily 분기(라인 124-133)에서:

```python
    else:
        # ...
        return title, [{
            "date":       date_str,
            "label":      f'{dt.month}/{dt.day}({WEEKDAY[dt.weekday()]})',
            "work_hours": data.get("work_hours", 0),
            "sessions":   prep(
                data.get("sessions", []),
                topics=data.get("topics"),
                tasks=data.get("tasks"),
            ),
        }]
```

- [ ] **Step 3: 기존 테스트 통과 확인**

Run: `python3 -m pytest shared/life-dashboard-mcp/tests/ -v`
Expected: 기존 테스트 전부 PASS (tasks=None일 때 기존 로직)

- [ ] **Step 4: 커밋**

```bash
git add shared/life-coach/scripts/timeline_html.py
git commit -m "feat: timeline_html.py tasks/segments 기반 렌더링 추가"
```

---

### Task 5: daily_coach.py + daily_report.py — tasks 기반 전환

**Files:**
- Modify: `shared/life-coach/scripts/daily_coach.py:18-21,148`
- Modify: `shared/life-coach/scripts/daily_report.py:25,144-214,405-482`
- Modify: `shared/life-coach/scripts/_helpers.py:41-55`

- [ ] **Step 1: daily_coach.py — get_tasks import + data에 tasks 추가**

`shared/life-coach/scripts/daily_coach.py` 라인 18-21의 import에 `get_tasks` 추가:

```python
from db import get_conn, get_coach_state, set_coach_state, get_repeated_signals, \
    query_exercises, query_symptoms, query_meals, query_check_ins, query_expiring_pantry, \
    get_mistake_trends, get_coaching_entry, get_pending_tasks, get_open_followups, \
    get_session_topics, update_daily_summary, get_tasks
```

라인 148 (`"topics": get_session_topics(conn, date_str)`) 뒤에 추가:

```python
        "tasks": get_tasks(conn, date_str),
```

- [ ] **Step 2: _helpers.py — group_tasks_by_repo 추가**

`shared/life-coach/scripts/_helpers.py`의 `group_topics_by_repo` 함수 뒤에 추가:

```python
def group_tasks_by_repo(tasks: list[dict]) -> dict[str, list[dict]]:
    """tasks를 repo 단축명 기준으로 그룹핑."""
    groups: dict[str, list[dict]] = {}
    for t in tasks:
        repo = (t.get("repo") or "?").split("/")[-1]
        groups.setdefault(repo, []).append(t)
    return groups
```

- [ ] **Step 3: daily_report.py — _build_task_items 함수 추가**

`shared/life-coach/scripts/daily_report.py`에 `_build_topic_items` 함수 뒤에 추가:

```python
def _build_task_items(tasks: list[dict]) -> str:
    """tasks 기준 작업 표시."""
    items = []
    for t in tasks:
        tag = t.get("tag") or "기타"
        tag_color = TAG_COLORS.get(tag, "#707070")
        summary = _esc(t.get("summary") or "(요약 없음)")
        status = t.get("status", "completed")
        status_badge = _status_badge(status)
        dur = t.get("duration_min", 0)
        meta_parts = []
        if dur:
            meta_parts.append(f"{dur}m")
        project_name = t.get("project_name")
        if project_name:
            meta_parts.append(project_name)
        meta_str = f' <span class="work-meta">({", ".join(meta_parts)})</span>' if meta_parts else ""
        follow_up = t.get("follow_up", "")
        follow_html = f' <span class="follow-up">→ {_esc(follow_up)}</span>' if follow_up else ""
        items.append(
            f'<div class="work-item">'
            f'{status_badge}'
            f'<span class="sess-tag" style="color:{tag_color}">[{tag}]</span> '
            f'<span class="work-summary">{summary}{meta_str}{follow_html}</span>'
            f'</div>'
        )
    return "".join(items)
```

- [ ] **Step 4: daily_report.py — _build_repos_detail에 tasks 분기 추가**

`_build_repos_detail` 함수(라인 405)의 시작 부분에 tasks 우선 분기:

```python
def _build_repos_detail(data: dict, repo_summaries=None) -> str:
    tasks = data.get("tasks", [])
    if tasks:
        from _helpers import group_tasks_by_repo
        task_repos = group_tasks_by_repo(tasks)
        rows = []
        for repo, ts in sorted(task_repos.items()):
            inner_html = _build_task_items(ts)
            rows.append(
                f'<div class="repo-group">'
                f'<div class="repo-name">{_esc(repo)}</div>'
                f'{inner_html}'
                f'</div>'
            )
        if not rows:
            return ""
        legend = (
            '<div class="status-legend">'
            '<span style="color:#7ABD7E">✓</span> 완료 '
            '<span style="color:#888">◦</span> 진행중 '
            '<span style="color:#E07B5A">✕</span> 블로커 '
            '<span style="color:#F0C040">→</span> 후속필요'
            '</div>'
        )
        return f'<div class="section"><h3>레포별 작업</h3>{legend}{"".join(rows)}</div>'

    # 기존 topics/sessions 폴백
    sessions = data.get("sessions", [])
    topics = data.get("topics", [])
    # ... (기존 코드 유지)
```

- [ ] **Step 5: 리포트 생성 테스트**

Run:
```bash
python3 shared/life-coach/scripts/daily_coach.py --json --date 2026-03-31 2>/dev/null | python3 shared/life-coach/scripts/daily_report.py --output /tmp/test_report.html 2>&1
```
Expected: `[daily_report] saved: /tmp/test_report.html` — tasks가 아직 비어있으면 기존 topics 폴백 동작

- [ ] **Step 6: 커밋**

```bash
git add shared/life-coach/scripts/daily_coach.py shared/life-coach/scripts/daily_report.py shared/life-coach/scripts/_helpers.py
git commit -m "feat: daily report를 tasks 기반으로 전환 (topics 폴백 유지)"
```

---

### Task 6: validate_tasks.py

**Files:**
- Create: `cc/work-digest/scripts/validate_tasks.py`

- [ ] **Step 1: validate_tasks.py 작성**

```python
#!/usr/bin/env python3
"""task 품질 검증 — tag/summary/segments/repo 체크 + --fix 모드.

Usage:
    python3 validate_tasks.py --date 2026-03-31
    python3 validate_tasks.py --fix --date 2026-03-31
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "shared" / "life-dashboard-mcp"))
from db import get_conn

KST = timezone(timedelta(hours=9))
_VALID_TAGS = {"코딩", "디버깅", "리서치", "리뷰", "ops", "설정", "문서", "설계", "리팩토링", "기타"}


def validate(date_str: str, fix: bool = False) -> list[str]:
    conn = get_conn()
    errors = []

    rows = conn.execute("SELECT * FROM tasks WHERE date = ?", (date_str,)).fetchall()
    if not rows:
        print(f"[validate_tasks] {date_str}: 0 tasks — nothing to validate", file=sys.stderr)
        conn.close()
        return []

    for r in rows:
        tid = r["id"]
        # 1. tag 유효성
        if r["tag"] not in _VALID_TAGS:
            errors.append(f"task {tid}: invalid tag '{r['tag']}'")
            if fix:
                conn.execute("UPDATE tasks SET tag = '기타' WHERE id = ?", (tid,))

        # 2. summary 길이
        if not r["summary"] or len(r["summary"]) < 10:
            errors.append(f"task {tid}: summary too short: '{r['summary']}'")

        # 3. repo NULL
        if not r["repo"]:
            errors.append(f"task {tid}: repo is NULL")

        # 4. segments JSON 유효성
        try:
            segs = json.loads(r["segments"]) if isinstance(r["segments"], str) else r["segments"]
            if not isinstance(segs, list):
                errors.append(f"task {tid}: segments is not a list")
        except (json.JSONDecodeError, TypeError):
            errors.append(f"task {tid}: segments is invalid JSON")

        # 5. duration_min > 0
        if (r["duration_min"] or 0) <= 0:
            errors.append(f"task {tid}: duration_min is {r['duration_min']}")

    # 6. 중복 summary 검사
    summaries = [r["summary"] for r in rows]
    from collections import Counter
    for s, cnt in Counter(summaries).items():
        if cnt >= 3:
            errors.append(f"duplicate summary x{cnt}: '{s[:50]}'")

    if fix:
        conn.commit()
    conn.close()

    for e in errors:
        print(f"  ERROR: {e}", file=sys.stderr)
    print(f"[validate_tasks] {date_str}: {len(rows)} tasks, {len(errors)} errors", file=sys.stderr)
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()
    errors = validate(args.date, args.fix)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 커밋**

```bash
git add cc/work-digest/scripts/validate_tasks.py
git commit -m "feat: validate_tasks.py — task 품질 검증"
```

---

### Task 7: 마이그레이션 스크립트

**Files:**
- Create: `shared/life-dashboard-mcp/migrate_topics_to_tasks.py`

- [ ] **Step 1: 마이그레이션 스크립트 작성**

```python
#!/usr/bin/env python3
"""session_topics → tasks 마이그레이션.

Usage:
    python3 migrate_topics_to_tasks.py              # dry-run
    python3 migrate_topics_to_tasks.py --execute     # 실행
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn


def migrate(execute: bool = False):
    conn = get_conn()

    # 이미 tasks에 데이터가 있으면 skip (idempotent)
    existing = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if existing > 0:
        print(f"[migrate] tasks already has {existing} rows — skipping", file=sys.stderr)
        conn.close()
        return

    rows = conn.execute("""
        SELECT st.date, st.tag, st.summary, st.repo,
               st.start_at, st.end_at, st.duration_estimate_min,
               st.status, st.follow_up, st.session_id
        FROM session_topics st
        ORDER BY st.date, st.id
    """).fetchall()

    print(f"[migrate] {len(rows)} session_topics → tasks", file=sys.stderr)

    for r in rows:
        seg = {
            "sid": r["session_id"],
            "date": r["date"],
            "start": (r["start_at"] or "00:00")[11:16] if r["start_at"] and len(r["start_at"]) >= 16 else (r["start_at"] or "00:00"),
            "end": (r["end_at"] or "00:00")[11:16] if r["end_at"] and len(r["end_at"]) >= 16 else (r["end_at"] or "00:00"),
            "dur": r["duration_estimate_min"] or 0,
        }
        segments_json = json.dumps([seg], ensure_ascii=False)

        if execute:
            conn.execute("""
                INSERT INTO tasks (date, tag, summary, repo, segments, duration_min, status, follow_up)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["date"], r["tag"] or "기타", r["summary"], r["repo"],
                segments_json, r["duration_estimate_min"] or 0,
                r["status"] or "completed", r["follow_up"],
            ))
        else:
            print(f"  [{r['date']}] [{r['tag']}] {r['summary'][:50]}", file=sys.stderr)

    if execute:
        # 백업 후 rename
        conn.execute("ALTER TABLE session_topics RENAME TO _session_topics_backup")
        conn.commit()
        final_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        print(f"[migrate] DONE: {final_count} tasks created, session_topics → _session_topics_backup", file=sys.stderr)
    else:
        print(f"[migrate] DRY RUN — pass --execute to apply", file=sys.stderr)

    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    migrate(args.execute)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: dry-run 테스트**

Run: `python3 shared/life-dashboard-mcp/migrate_topics_to_tasks.py`
Expected: session_topics 행 목록 출력 + "DRY RUN" 메시지

- [ ] **Step 3: 커밋 (마이그레이션 실행은 별도)**

```bash
git add shared/life-dashboard-mcp/migrate_topics_to_tasks.py
git commit -m "feat: session_topics → tasks 마이그레이션 스크립트"
```

---

### Task 8: SKILL.md + 가이드 재작성

**Files:**
- Modify: `cc/work-digest/SKILL.md:95-233`
- Modify: `cc/work-digest/references/topic-creation-guide.md`

- [ ] **Step 1: SKILL.md Step 4~5 재작성**

`cc/work-digest/SKILL.md`의 Step 4(라인 95~143)와 Step 5(라인 145~155)를 교체:

```markdown
### Step 4: Task 생성 (LLM)

extract_day.py `--flat` 출력과 기존 projects 목록을 참고하여 task를 생성한다.

```bash
# segment flat list
python3 {baseDir}/scripts/extract_day.py --date <DATE> --no-scan --flat

# 기존 projects 목록 (LLM에 함께 전달)
python3 -c "import sys; sys.path.insert(0,'{baseDir}/../../shared/life-dashboard-mcp'); from db import get_conn, get_projects; print([{'id':p['id'],'name':p['name'],'repo':p['repo']} for p in get_projects(get_conn(), 'active')])"
```

**핵심 원칙: task = 사용자가 한 일의 기능 단위. 세션이 아니라 segment 단위로 사고.**

**그룹핑 기준:**
- 같은 레포 + 같은 목표 (hint/files로 판단) → 1 task
- 다른 레포 → 다른 task
- 같은 레포 + 다른 목표 → 다른 task
- 한 세션의 segments가 여러 task에 분산될 수 있다
- **애매하면 분리.** project 레벨에서 연결되므로 과도한 병합보다 분리가 안전.

**segment 전수 검증:** 모든 input segment가 정확히 1개 task에 할당. 누락·중복 불허.

**project 연결:** 기존 projects 목록에 매칭되면 해당 name 사용, 없으면 새 name 제시.

**출력 형식:**
```json
[
  {
    "tag": "설계",
    "summary": "왜 → 뭘 → 결과 형식의 요약",
    "repo": "dy-minions-squad",
    "segments": [{"sid":"xxx","date":"YYYY-MM-DD","start":"HH:MM","end":"HH:MM","dur":N}, ...],
    "duration_min": 96,
    "status": "completed",
    "project": "프로젝트명"
  }
]
```

### Step 5: 저장 + 검증

```bash
python3 {baseDir}/../../shared/life-dashboard-mcp/activity_writer.py update-tasks \
    --date <DATE> --tasks '<JSON array>'

python3 {baseDir}/scripts/validate_tasks.py --date <DATE>
```
```

- [ ] **Step 2: references/topic-creation-guide.md를 task 기반으로 재작성**

핵심만 변경: "토픽" → "task", session 단위 → segment 단위, project 연결 예시 추가.

- [ ] **Step 3: Gate B 관련 섹션도 tasks 기준으로 업데이트**

validate_topics.py → validate_tasks.py, session_topics → tasks 참조 전부 교체.

- [ ] **Step 4: 커밋**

```bash
git add cc/work-digest/SKILL.md cc/work-digest/references/topic-creation-guide.md
git commit -m "docs: SKILL.md + 가이드를 task/segment 기반으로 재작성"
```

---

### Task 9: 통합 테스트 — 3/31 데이터로 검증

- [ ] **Step 1: 마이그레이션 실행**

```bash
python3 shared/life-dashboard-mcp/migrate_topics_to_tasks.py --execute
```

Expected: `DONE: N tasks created, session_topics → _session_topics_backup`

- [ ] **Step 2: validate_tasks.py 실행**

```bash
python3 cc/work-digest/scripts/validate_tasks.py --date 2026-03-31
```

Expected: 에러 0 또는 기존 데이터 품질 이슈만

- [ ] **Step 3: 리포트 재생성**

```bash
python3 shared/life-coach/scripts/daily_coach.py --json --date 2026-03-31 2>/dev/null \
  | python3 shared/life-coach/scripts/daily_report.py --output /tmp/daily_report_tasks.html 2>&1
open /tmp/daily_report_tasks.html
```

Expected: 레포별 작업이 tasks 기반으로 표시, 타임라인이 segment별로 정확히 분포

- [ ] **Step 4: 전체 테스트 실행**

```bash
python3 -m pytest shared/life-dashboard-mcp/tests/ -v
```

Expected: 기존 + 신규 테스트 전부 PASS

- [ ] **Step 5: 최종 커밋**

```bash
git add -A
git commit -m "feat: task/project 기반 작업 기록 — 통합 테스트 완료"
```
