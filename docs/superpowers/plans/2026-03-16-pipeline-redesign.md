# Pipeline Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** life-dashboard 데이터 파이프라인을 3계층(Ingestion→Enrichment→Coaching)으로 재설계하여 데이터 품질을 보장하고, 코칭/태스크/follow-up을 DB에 구조화하여 저장한다.

**Architecture:** 기존 activities 테이블을 sessions + session_content로 분리 (원본 보존), signals/coaching_entries/task_suggestions/followup_chains 신규 테이블 추가. Layer 1은 LLM 없이 동작, Layer 2는 best-effort enrichment, Layer 3는 코칭 저장+추적.

**Tech Stack:** Python 3 stdlib (sqlite3, json, argparse), SQLite

**Spec:** `docs/superpowers/specs/2026-03-16-pipeline-redesign.md`

---

## Chunk 1: DB 기반 — 스키마 + CRUD + CLI

### Task 1: schema.sql — 새 테이블 추가

**Files:**
- Modify: `shared/life-dashboard-mcp/schema.sql`

- [ ] **Step 1: sessions 테이블 추가**

기존 activities CREATE 문 아래에 추가. activities는 건드리지 않음 (Codex 호환).

```sql
-- ── Work Tracking (v2) ──────────────────────────

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    repo TEXT,
    branch TEXT,
    tag TEXT,
    summary TEXT,
    summary_source TEXT DEFAULT 'pending',
    status TEXT DEFAULT 'in_progress',
    follow_up TEXT,
    start_at TEXT NOT NULL,
    end_at TEXT,
    duration_min INTEGER DEFAULT 0,
    file_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    has_tests INTEGER DEFAULT 0,
    has_commits INTEGER DEFAULT 0,
    token_total INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, session_id, date)
);

CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_summary_source ON sessions(summary_source);
```

- [ ] **Step 2: session_content 테이블 추가**

```sql
CREATE TABLE IF NOT EXISTS session_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    topic TEXT,
    user_messages TEXT,
    agent_messages TEXT,
    files_changed TEXT,
    commands TEXT,
    errors TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, session_id, date),
    FOREIGN KEY (source, session_id, date)
        REFERENCES sessions(source, session_id, date)
        ON DELETE CASCADE
);
```

- [ ] **Step 3: signals 테이블 추가**

```sql
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    content TEXT NOT NULL,
    reasoning TEXT,
    repo TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(session_id, signal_type, content)
);

CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(date);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);
```

- [ ] **Step 4: coaching_entries, task_suggestions, followup_chains 추가**

```sql
CREATE TABLE IF NOT EXISTS coaching_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    period_type TEXT NOT NULL,
    content TEXT NOT NULL,
    sections TEXT NOT NULL,
    escalation_level INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, period_type)
);

CREATE INDEX IF NOT EXISTS idx_coaching_date ON coaching_entries(date);

CREATE TABLE IF NOT EXISTS task_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suggested_date TEXT NOT NULL,
    description TEXT NOT NULL,
    estimated_min INTEGER,
    priority INTEGER,
    source_type TEXT NOT NULL,
    origin_session_id TEXT,
    status TEXT DEFAULT 'pending',
    resolved_date TEXT,
    resolved_session_id TEXT,
    resolution_method TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(suggested_date, description)
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON task_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_tasks_date ON task_suggestions(suggested_date);

CREATE TABLE IF NOT EXISTS followup_chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_session_id TEXT NOT NULL,
    origin_date TEXT NOT NULL,
    origin_repo TEXT,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    resolved_date TEXT,
    resolved_session_id TEXT,
    resolution_note TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(origin_session_id, origin_date, description)
);

CREATE INDEX IF NOT EXISTS idx_followup_status ON followup_chains(status);
CREATE INDEX IF NOT EXISTS idx_followup_origin_date ON followup_chains(origin_date);
```

- [ ] **Step 5: 수동 검증**

`get_conn()`이 `schema.sql`을 `executescript()`으로 실행하므로 새 테이블이 자동 생성된다. 별도 `_migrate()` 변경 불필요 — `CREATE TABLE IF NOT EXISTS`가 이미 적용.

```bash
cd shared/life-dashboard-mcp
python3 -c "from db import get_conn; c=get_conn(); print([r[1] for r in c.execute('SELECT * FROM pragma_table_list').fetchall()])"
```

sessions, session_content, signals, coaching_entries, task_suggestions, followup_chains가 목록에 있는지 확인.

- [ ] **Step 6: 커밋**

```bash
git add shared/life-dashboard-mcp/schema.sql
git commit -m "feat: add v2 schema — sessions, session_content, signals, coaching tables"
```

### Task 2: db.py — 새 CRUD 함수

**Files:**
- Modify: `shared/life-dashboard-mcp/db.py`

- [ ] **Step 1: upsert_session() 추가**

`upsert_activity()` 아래에 추가. scanner 우선순위 규칙 포함:

```python
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
            tag=COALESCE(tag, excluded.tag),
            summary=COALESCE(summary, excluded.summary),
            summary_source=CASE
                WHEN summary_source IN ('llm', 'manual') THEN summary_source
                ELSE COALESCE(excluded.summary_source, summary_source)
            END,
            status=CASE
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
```

- [ ] **Step 2: insert_session_content() 추가**

```python
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
```

- [ ] **Step 3: insert_signal() 추가**

```python
def insert_signal(conn: sqlite3.Connection, signal: dict):
    """signals 테이블 INSERT OR IGNORE."""
    conn.execute("""
        INSERT OR IGNORE INTO signals (session_id, date, signal_type, content, reasoning, repo)
        VALUES (:session_id, :date, :signal_type, :content, :reasoning, :repo)
    """, signal)
```

- [ ] **Step 4: coaching/task/followup CRUD 추가**

```python
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
                           method: str, notes: str | None = None):
    conn.execute("""
        UPDATE task_suggestions
        SET status=?, resolved_date=?, resolved_session_id=?, resolution_method=?, notes=?
        WHERE id=?
    """, (status, resolved_date, resolved_session_id, method, notes, task_id))


def upsert_followup_chain(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT OR IGNORE INTO followup_chains
            (origin_session_id, origin_date, origin_repo, description)
        VALUES (:origin_session_id, :origin_date, :origin_repo, :description)
    """, data)


def update_followup_resolution(conn: sqlite3.Connection, chain_id: int, status: str,
                               resolved_date: str, resolved_session_id: str | None,
                               resolution_note: str | None = None):
    conn.execute("""
        UPDATE followup_chains
        SET status=?, resolved_date=?, resolved_session_id=?, resolution_note=?
        WHERE id=?
    """, (status, resolved_date, resolved_session_id, resolution_note, chain_id))
```

- [ ] **Step 5: update_daily_stats()를 sessions 참조로 전환**

기존 `update_daily_stats()`에서 `FROM activities` → `FROM sessions`. 함수 시그니처는 동일:

```python
def update_daily_stats(conn: sqlite3.Connection, date_str: str):
    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT tag, repo, duration_min, start_at, end_at
        FROM sessions
        WHERE date = ?
    """, (date_str,)).fetchall()
    # ... 이하 로직 동일
```

- [ ] **Step 6: get_repeated_signals, get_mistake_trends를 signals 참조로 전환**

기존 `FROM behavioral_signals` → `FROM signals`. reasoning 컬럼 추가:

```python
def get_repeated_signals(conn, date_str, days=7, min_count=2):
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
```

`get_mistake_trends`도 동일하게 `FROM signals WHERE signal_type = 'mistake'`.

- [ ] **Step 7: coaching/task/followup 쿼리 함수 추가**

```python
def get_coaching_entry(conn, date_str: str, period_type: str = "daily") -> dict | None:
    row = conn.execute(
        "SELECT * FROM coaching_entries WHERE date = ? AND period_type = ?",
        (date_str, period_type)
    ).fetchone()
    return dict(row) if row else None


def get_pending_tasks(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM task_suggestions WHERE status = 'pending' ORDER BY priority, suggested_date"
    ).fetchall()
    return [dict(r) for r in rows]


def get_open_followups(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT *, CAST(julianday('now', 'localtime') - julianday(origin_date) AS INTEGER) as days_open
        FROM followup_chains WHERE status = 'open'
        ORDER BY origin_date
    """).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 8: 수동 검증**

```bash
python3 -c "
from db import get_conn, upsert_session, upsert_session_content
c = get_conn()
upsert_session(c, {'source':'cc','session_id':'test','date':'2026-03-16','repo':'test','branch':None,'tag':'코딩','summary':None,'summary_source':'pending','status':'in_progress','follow_up':None,'start_at':'2026-03-16T10:00:00','end_at':None,'duration_min':10,'file_count':0,'error_count':0,'has_tests':0,'has_commits':0,'token_total':1000})
upsert_session_content(c, {'source':'cc','session_id':'test','date':'2026-03-16','topic':'test topic','user_messages':'[]','agent_messages':'[]','files_changed':'[]','commands':'[]','errors':'[]'})
c.commit()
row = c.execute('SELECT * FROM sessions WHERE session_id=\"test\"').fetchone()
print(dict(row))
c.execute('DELETE FROM sessions WHERE session_id=\"test\"')
c.commit()
print('OK')
"
```

- [ ] **Step 9: 커밋**

```bash
git add shared/life-dashboard-mcp/db.py
git commit -m "feat: db.py — add v2 CRUD functions for sessions, signals, coaching tables"
```

### Task 3: activity_writer.py — record_sessions + CLI 전환

**Files:**
- Modify: `shared/life-dashboard-mcp/activity_writer.py`

- [ ] **Step 1: import 전환**

```python
from db import get_conn, upsert_session, upsert_session_content, insert_signal, \
    upsert_followup_chain, update_daily_stats
```

기존 `upsert_activity, insert_behavioral_signal` import는 codex wrapper용으로만 유지.

- [ ] **Step 2: record_sessions() 작성**

기존 `record_activities()` 로직을 새 테이블 기반으로 재작성. 기존 상수 `_SIGNAL_TYPE_MAP`, `_TEST_KEYWORDS`, `_TEST_PATTERNS`, `auto_tag()` 함수는 그대로 유지:

```python
def record_sessions(
    source: str,
    session_id: str,
    by_date: dict[str, dict],
    repo: str,
    branch: str | None = None,
    summary: dict | None = None,
    behavioral_signals: dict | None = None,
) -> dict[str, str]:
    """날짜별 분할 데이터를 sessions + session_content에 기록."""
    if not by_date:
        return {}

    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    recorded = {}
    dates = sorted(by_date.keys())
    primary_date = dates[0]  # 시작 날짜를 primary로

    try:
        for date_str in dates:
            data = by_date[date_str]
            if not data.get("files") and not data.get("commands") and not data.get("topic"):
                continue

            tokens = data.get("tokens", {})
            token_total = sum(tokens.get(k, 0) for k in ("input", "output", "cache_read", "cache_create"))
            if token_total == 0:
                token_total = tokens.get("api_calls", 0)

            has_tests = 0
            has_commits = data.get("has_commits", False)
            for cmd in data.get("commands", []):
                cmd_lower = cmd.lower()
                if any(kw in cmd_lower for kw in _TEST_KEYWORDS) or \
                   any(pat in cmd_lower for pat in _TEST_PATTERNS):
                    has_tests = 1

            start_kst = data.get("start_kst")
            start_at = start_kst.strftime("%Y-%m-%dT%H:%M:%S") if start_kst else f"{date_str}T00:00:00"
            end_time = data.get("end_time")
            end_at = f"{date_str}T{end_time}:00" if end_time else None

            # Layer 1: tag만 auto, summary는 NULL (pending)
            tag = auto_tag(data.get("topic", ""), " ".join(data.get("commands", [])[:5]))

            # summary는 마지막 날짜에만, LLM이 성공한 경우만
            summary_text = None
            summary_source = "pending"
            status = "in_progress"
            if summary and date_str == dates[-1]:
                if summary.get("text"):
                    summary_text = summary["text"]
                    summary_source = "llm"
                if summary.get("tag"):
                    tag = summary["tag"]
                if summary.get("status"):
                    status = summary["status"]
            # SessionEnd: 닫힌 세션이 in_progress로 남지 않도록
            # LLM이 blocked/follow_up 판정하지 않았으면 모두 completed
            # (has_commits 여부와 무관 — 세션이 끝났으면 completed)
            if status == "in_progress":
                status = "completed"

            session_data = {
                "source": source, "session_id": session_id, "date": date_str,
                "repo": repo, "branch": branch, "tag": tag,
                "summary": summary_text, "summary_source": summary_source,
                "status": status, "follow_up": summary.get("follow_up") if summary else None,
                "start_at": start_at, "end_at": end_at,
                "duration_min": data.get("duration_min"),
                "file_count": len(data.get("files", [])),
                "error_count": len(data.get("errors", [])),
                "has_tests": has_tests, "has_commits": 1 if has_commits else 0,
                "token_total": token_total,
            }
            upsert_session(conn, session_data)

            # session_content — 원본 보존 (date-slice local)
            content_data = {
                "source": source, "session_id": session_id, "date": date_str,
                "topic": data.get("topic", ""),
                "user_messages": json.dumps(data.get("user_messages", []), ensure_ascii=False),
                "agent_messages": json.dumps(data.get("agent_messages", []), ensure_ascii=False),
                "files_changed": json.dumps(data.get("files", []), ensure_ascii=False),
                "commands": json.dumps(data.get("commands", [])[:20], ensure_ascii=False),
                "errors": json.dumps(data.get("errors", [])[:10], ensure_ascii=False),
            }
            upsert_session_content(conn, content_data)
            recorded[date_str] = session_id

            # followup_chains — status가 follow_up/blocked이면 자동 생성
            if status in ("follow_up", "blocked") and (summary and summary.get("follow_up")):
                upsert_followup_chain(conn, {
                    "origin_session_id": session_id,
                    "origin_date": date_str,
                    "origin_repo": repo,
                    "description": summary["follow_up"],
                })

        # signals — primary date에 1회 기록
        # 현재 extract_behavioral_signals()는 str 리스트를 반환.
        # reasoning을 채우려면 LLM 프롬프트를 {"content": str, "reasoning": str} 형식으로 변경해야 함.
        # 이번 구현에서는 기존 str 형식도 지원하되, dict 형식이 오면 reasoning도 저장.
        if behavioral_signals:
            for plural, singular in _SIGNAL_TYPE_MAP.items():
                items = behavioral_signals.get(plural, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            content_text = item.get("content", "")
                            reasoning_text = item.get("reasoning")
                        else:
                            content_text = str(item)
                            reasoning_text = None
                        if content_text:
                            insert_signal(conn, {
                                "session_id": session_id,
                                "date": primary_date,
                                "signal_type": singular,
                                "content": content_text,
                                "reasoning": reasoning_text,
                                "repo": repo,
                            })

        for date_str in recorded:
            update_daily_stats(conn, date_str)

        conn.commit()
    finally:
        conn.close()

    return recorded
```

- [ ] **Step 3: record_activities()를 thin wrapper로 변경**

```python
def record_activities(source, session_id, by_date, repo, branch=None,
                      summary=None, behavioral_signals=None):
    """Codex 호환용 wrapper — 기존 activities 테이블에 기록."""
    # 기존 로직 유지 (구 스키마 대상)
    # ... (기존 코드 그대로)
```

기존 `record_activities()` 코드를 그대로 두되, 이름만 유지. CC용 새 코드는 `record_sessions()`를 호출.

- [ ] **Step 4: CLI unsummarized 전환 — sessions + session_content 참조**

```python
def cmd_unsummarized(args):
    conn = get_conn()
    try:
        if hasattr(args, 'before') and args.before:
            # catch-up: 과거 pending 세션
            rows = conn.execute("""
                SELECT s.session_id, s.date, s.repo, s.source,
                       sc.topic, sc.user_messages
                FROM sessions s
                LEFT JOIN session_content sc USING (source, session_id, date)
                WHERE s.date < ? AND s.summary_source = 'pending'
                ORDER BY s.date, s.start_at
            """, (args.before,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT s.session_id, s.date, s.repo, s.source,
                       sc.topic, sc.user_messages
                FROM sessions s
                LEFT JOIN session_content sc USING (source, session_id, date)
                WHERE s.date = ? AND s.summary_source = 'pending'
                ORDER BY s.start_at
            """, (args.date,)).fetchall()
        results = []
        for r in rows:
            results.append({
                "session_id": r["session_id"], "date": r["date"],
                "repo": r["repo"], "source": r["source"],
                "topic": r["topic"] or "",
                "user_messages": r["user_messages"],
            })
        print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        conn.close()
```

- [ ] **Step 5: CLI update-summary 전환 — sessions 참조**

```python
def cmd_update_summary(args):
    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        summary_source = args.summary_source or "llm"
        sets = ["tag = ?", "summary = ?", f"summary_source = ?"]
        params = [args.tag, args.summary, summary_source]
        if args.status:
            sets.append("status = ?")
            params.append(args.status)
        if args.follow_up:
            sets.append("follow_up = ?")
            params.append(args.follow_up)
        params.extend([args.session_id, args.date])
        cursor = conn.execute(f"""
            UPDATE sessions
            SET {', '.join(sets)}
            WHERE session_id = ? AND date = ?
        """, params)
        if cursor.rowcount == 0:
            print(f"No session found: {args.session_id} / {args.date}", file=sys.stderr)
            sys.exit(1)

        # follow_up/blocked → followup_chains 자동 생성
        if args.status in ("follow_up", "blocked") and args.follow_up:
            upsert_followup_chain(conn, {
                "origin_session_id": args.session_id,
                "origin_date": args.date,
                "origin_repo": None,
                "description": args.follow_up,
            })

        update_daily_stats(conn, args.date)
        conn.commit()
        print(f"Updated: {args.session_id} [{args.tag}] {args.summary[:50]}", file=sys.stderr)
    finally:
        conn.close()
```

- [ ] **Step 6: CLI 플래그 추가**

```python
# unsummarized에 --before 추가
p_unsummarized.add_argument("--before", help="Catch-up: list pending sessions before this date")

# update-summary에 --summary-source 추가 (기존 parser에)
p_update.add_argument("--summary-source", dest="summary_source",
                      choices=["llm", "manual"], default="llm")
```

- [ ] **Step 7: 수동 검증**

```bash
python3 activity_writer.py unsummarized --date 2026-03-16
python3 activity_writer.py unsummarized --before 2026-03-16
```

- [ ] **Step 8: 커밋**

```bash
git add shared/life-dashboard-mcp/activity_writer.py
git commit -m "feat: activity_writer — record_sessions + CLI v2 (sessions/session_content)"
```

### Task 4: server.py + sync_calendar.py 전환

**Files:**
- Modify: `shared/life-dashboard-mcp/server.py`
- Modify: `shared/life-dashboard-mcp/sync_calendar.py`

- [ ] **Step 1: server.py — activities → sessions 쿼리 전환**

`server.py`에서 `FROM activities`를 모두 `FROM sessions`로 변경. 컬럼은 동일하므로 테이블명만 치환. `raw_json` 참조가 있으면 `JOIN session_content`로 변경.

- [ ] **Step 2: backfill_tags.py — activities → sessions**

`FROM activities` → `FROM sessions`. 1회성 스크립트이므로 테이블명 치환만:

```python
from db import get_conn, update_daily_stats, upsert_session
# FROM activities WHERE tag = '기타' → FROM sessions WHERE tag = '기타'
```

- [ ] **Step 3: sync_calendar.py — upsert_activity → upsert_session**

```python
from db import get_conn, upsert_session, update_daily_stats
```

`upsert_activity(conn, activity)` → `upsert_session(conn, session_data)`. 컬럼 매핑:
- `raw_json` 제거
- `summary_source='manual'` 추가 (캘린더 이벤트는 요약이 타이틀)
- `status='completed'` 추가

- [ ] **Step 3: 수동 검증**

```bash
python3 -c "from server import app; print('MCP server imports OK')"
python3 sync_calendar.py --dry-run 2026-03-16
```

- [ ] **Step 4: 커밋**

```bash
git add shared/life-dashboard-mcp/server.py shared/life-dashboard-mcp/sync_calendar.py
git commit -m "feat: server.py + sync_calendar — migrate to sessions table"
```

---

## Chunk 2: Ingestion — session_logger + scanner

### Task 5: session_logger.py — user/agent messages 추출 + Layer 1/2 분리

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py`

- [ ] **Step 1: parse_transcript_by_date()에 user_messages, agent_messages 추출 추가**

기존 `parse_transcript_by_date()`가 반환하는 `by_date[date_str]` dict에 두 필드 추가.

**주의**: 현재 transcript 포맷에서 entry type은 `"user"` (not `"human"`), content는 문자열 또는 text block 리스트.

acc 초기값에 추가:
```python
"user_messages": [],
"agent_messages": [],
```

기존 topic 추출 블록(line 560-571) 근처에 user_messages 수집 추가:

```python
# user_messages 수집 (topic 추출 로직 바로 아래)
if entry_type == "user":
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                raw = strip_system_tags(block.get("text", ""))
                if raw:
                    acc["user_messages"].append(raw[:500])
    elif isinstance(content, str):
        raw = strip_system_tags(content)
        if raw:
            acc["user_messages"].append(raw[:500])

# agent_messages 수집 (assistant 블록에서, 최대 5개)
if entry_type == "assistant" and isinstance(content, list):
    if len(acc["agent_messages"]) < 5:
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    acc["agent_messages"].append(text[:500])
                    break
```

result 딕셔너리에 추가 (line 626-642 근처):
```python
result[date_str] = {
    # ... 기존 필드 ...
    "user_messages": acc["user_messages"],
    "agent_messages": acc["agent_messages"],
}
```

- [ ] **Step 2: scan_and_record()에서 record_activities → record_sessions 전환**

**중요**: 현재 구조를 유지한다. `scan_and_record()`는 Layer 1 헬퍼로, `main()`에서 호출된다. SessionEnd의 Layer 2 (summary/signals)는 `main()`에서 별도로 `record_sessions()`를 다시 호출한다.

```python
from activity_writer import record_sessions  # 기존 record_activities 대신

def scan_and_record(session_id: str, transcript_path: str, cwd: str) -> dict[str, dict]:
    """Layer 1: transcript를 날짜별로 분할하여 sessions + session_content에 기록."""
    repo, branch = detect_repo_and_branch(cwd) if cwd else ("unknown", None)
    by_date = parse_transcript_by_date(transcript_path)
    if not by_date:
        return {}
    record_sessions("cc", session_id, by_date, repo, branch)
    # summary=None, signals=None → Layer 1만 (summary_source='pending')
    return by_date
```

- [ ] **Step 3: main()의 SessionEnd 블록에서 Layer 2 배선**

기존 main() 구조 유지 — `scan_and_record()`로 Layer 1 실행 후, SessionEnd이면 LLM 시도 후 `record_sessions()`를 다시 호출:

```python
# main() 내 SessionEnd 블록 (line 704-732):
if event == "SessionEnd":
    # ... 기존 ThreadPoolExecutor로 summary/signals 추출 ...

    if summary or signals:
        _, branch = detect_repo_and_branch(cwd) if cwd else ("unknown", None)
        record_sessions("cc", session_id, by_date, repo, branch,
                        summary=summary, behavioral_signals=signals)
    else:
        # Layer 2 실패 → SessionEnd이므로 최소한 status를 completed로
        # (scan_and_record에서 이미 Layer 1 기록됨, status만 업데이트)
        conn = get_conn()
        for date_str in by_date:
            conn.execute("""
                UPDATE sessions SET status = 'completed'
                WHERE source = 'cc' AND session_id = ? AND date = ?
                  AND status = 'in_progress'
            """, (session_id, date_str))
        conn.commit()
        conn.close()
```

**topic → summary fallback 제거**: `summarize_session()` 실패 시 topic을 summary에 넣는 기존 코드가 있으면 삭제. summary=NULL(pending) 유지.

- [ ] **Step 4: 수동 검증**

hook을 직접 테스트하긴 어려우므로, `scan_and_record()`를 임포트해서 테스트 transcript로 실행:

```bash
python3 -c "
from session_logger import parse_transcript_by_date
# 가장 최근 transcript 파일로 테스트
import glob, os
logs = sorted(glob.glob(os.path.expanduser('~/.claude/logs/sessions/*/transcript.jsonl')), key=os.path.getmtime)
if logs:
    result = parse_transcript_by_date(logs[-1])
    for date, data in result.items():
        print(f'{date}: user_msgs={len(data.get(\"user_messages\",[]))}, agent_msgs={len(data.get(\"agent_messages\",[]))}')
"
```

- [ ] **Step 5: 커밋**

```bash
git add cc/work-digest/scripts/session_logger.py
git commit -m "feat: session_logger — Layer 1/2 split, user/agent messages extraction"
```

### Task 6: active_session_scanner.py — sessions 참조 전환

**Files:**
- Modify: `cc/work-digest/scripts/active_session_scanner.py`

- [ ] **Step 1: import 전환**

`from activity_writer import record_sessions` (기존 `record_activities` 대신)

- [ ] **Step 2: scan_and_record 호출 확인**

**현재 구조**: `active_session_scanner.py`는 `session_logger.scan_and_record()`에 위임한다. scan_and_record() 내부에서 이미 `record_sessions()`를 호출하므로 scanner 자체는 import만 바꾸면 된다.

`from session_logger import scan_and_record` — 이 import는 이미 있음. scan_and_record()가 내부적으로 record_sessions()를 호출하므로 scanner 코드 변경 최소화.

- [ ] **Step 3: 수동 검증**

```bash
python3 active_session_scanner.py --dry-run
```

- [ ] **Step 4: 커밋**

```bash
git add cc/work-digest/scripts/active_session_scanner.py
git commit -m "feat: scanner — migrate to record_sessions (Layer 1 only)"
```

---

## Chunk 3: Coaching — daily_coach + weekly_coach 전환

### Task 7: daily_coach.py — sessions 전환 + coaching 저장 쿼리

**Files:**
- Modify: `shared/life-coach/scripts/daily_coach.py`

- [ ] **Step 1: import 전환**

```python
from db import get_conn, get_coach_state, set_coach_state, get_repeated_signals, \
    query_exercises, query_symptoms, query_meals, query_check_ins, query_expiring_pantry, \
    get_mistake_trends, get_coaching_entry, get_pending_tasks, get_open_followups
```

- [ ] **Step 2: get_today_data() — activities → sessions + session_content**

모든 `FROM activities` → `FROM sessions`. `raw_json` 참조 → `JOIN session_content`:

```python
sessions = conn.execute("""
    SELECT s.*, sc.topic, sc.user_messages, sc.agent_messages,
           sc.files_changed, sc.commands
    FROM sessions s
    LEFT JOIN session_content sc USING (source, session_id, date)
    WHERE s.date = ?
    ORDER BY s.start_at
""", (date_str,)).fetchall()
```

- [ ] **Step 3: behavioral_signals → signals 참조 전환**

기존 `FROM behavioral_signals` → `FROM signals`.

- [ ] **Step 4: _get_unresolved_followups() → followup_chains 기반으로 변경**

기존 repo 매칭 로직 제거, `get_open_followups()` 사용:

```python
def _get_followup_data(conn) -> dict:
    """코칭에 필요한 follow-up/task 데이터."""
    return {
        "open_followups": get_open_followups(conn),
        "pending_tasks": get_pending_tasks(conn),
        "yesterday_coaching": get_coaching_entry(conn, yesterday_str, "daily"),
    }
```

- [ ] **Step 5: JSON 출력에 새 데이터 포함**

`get_today_data()` 반환값에 추가:

```python
return {
    # ... 기존 필드들 ...
    "open_followups": followup_data["open_followups"],
    "pending_tasks": followup_data["pending_tasks"],
    "yesterday_coaching": followup_data["yesterday_coaching"],
}
```

- [ ] **Step 6: 수동 검증**

```bash
python3 daily_coach.py --json --date 2026-03-16 2>/dev/null | python3 -m json.tool | head -30
```

- [ ] **Step 7: 커밋**

```bash
git add shared/life-coach/scripts/daily_coach.py
git commit -m "feat: daily_coach — migrate to sessions/signals, add coaching data queries"
```

### Task 8: weekly_coach.py — sessions 전환

**Files:**
- Modify: `shared/life-coach/scripts/weekly_coach.py`

- [ ] **Step 1: activities → sessions 전환**

`FROM activities` → `FROM sessions`. 모든 쿼리.

- [ ] **Step 2: behavioral_signals → signals 전환**

`FROM behavioral_signals` → `FROM signals`.

- [ ] **Step 3: blocked_resolution → followup_chains 기반**

기존 "같은 repo 후속 세션" 로직 → `get_open_followups()` 사용.

- [ ] **Step 4: coaching_entries 주간 집계 추가**

```python
coaching_entries = conn.execute("""
    SELECT date, sections FROM coaching_entries
    WHERE date >= ? AND date <= ? AND period_type = 'daily'
    ORDER BY date
""", (monday_str, sunday_str)).fetchall()
```

- [ ] **Step 5: 수동 검증**

```bash
python3 weekly_coach.py --json 2>/dev/null | python3 -m json.tool | head -30
```

- [ ] **Step 6: 커밋**

```bash
git add shared/life-coach/scripts/weekly_coach.py
git commit -m "feat: weekly_coach — migrate to sessions/signals/followup_chains"
```

### Task 9: _helpers.py — dedup 연결

**Files:**
- Modify: `shared/life-coach/scripts/_helpers.py`

- [ ] **Step 1: dedup_sessions()를 sessions 기준으로 수정하고 daily_coach에서 호출**

기존 함수가 `(start_at, repo, tag)` 기준 중복 제거였는데, 새 스키마에서는 `(source, session_id, date)` UNIQUE이므로 DB 레벨에서 이미 중복 방지됨. dedup은 **표시 레벨** 중복만 처리 — 같은 session_id의 short/full sid 문제:

```python
def dedup_sessions(sessions: list[dict]) -> list[dict]:
    """같은 session_id prefix를 가진 중복 세션 제거."""
    seen = {}
    for s in sessions:
        sid = s.get("session_id", "")
        # full UUID가 short prefix를 포함하면 full 우선
        key = sid[:8] if len(sid) > 8 else sid
        if key not in seen or len(sid) > len(seen[key].get("session_id", "")):
            seen[key] = s
    return list(seen.values())
```

- [ ] **Step 2: daily_coach.py에서 호출**

```python
from _helpers import dedup_sessions
# get_today_data() 내:
sessions = dedup_sessions([dict(r) for r in sessions_raw])
```

- [ ] **Step 3: 커밋**

```bash
git add shared/life-coach/scripts/_helpers.py shared/life-coach/scripts/daily_coach.py
git commit -m "fix: dedup_sessions — connect to daily_coach, handle short/full sid"
```

---

## Chunk 4: Reports + SKILL.md

### Task 10: daily_report.py — 날짜 기반 파일명 + data contract 업데이트

**Files:**
- Modify: `shared/life-coach/scripts/daily_report.py`

- [ ] **Step 1: follow-up 섹션을 새 data contract에 맞게 수정**

기존 `_build_followup_section(data)` (line 238-277)은 `yesterday_followups`에서 `resolved` 불리언을 읽는다. 새 구조에서는 `open_followups`(followup_chains 기반) + `pending_tasks`를 읽도록 변경:

```python
def _build_followup_section(data: dict) -> str:
    """open follow-ups + pending tasks 표시."""
    followups = data.get("open_followups", [])
    tasks = data.get("pending_tasks", [])
    if not followups and not tasks:
        return ""

    items = []
    for f in followups:
        days = f.get("days_open", 0)
        cls = "followup-urgent" if days >= 3 else "followup-open"
        items.append(f'<div class="{cls}">🔗 [{days}일] {_esc(f["description"])} ({_esc(f.get("origin_repo",""))})</div>')
    for t in tasks:
        days = ... # calculate from suggested_date
        cls = "task-urgent" if days >= 3 else "task-pending"
        items.append(f'<div class="{cls}">📋 {_esc(t["description"])} ({t.get("estimated_min","?")}분)</div>')

    return f'<div class="section"><h3>미해소 항목</h3>{"".join(items)}</div>'
```

- [ ] **Step 2: 출력 파일명에 날짜 포함**

```python
# 기존:
# output_path = args.output or "/tmp/daily_report.html"
# 새:
date_str = data.get("date", "unknown")
default_output = f"/tmp/daily_report_{date_str}.html"
output_path = args.output or default_output
```

- [ ] **Step 2: --output 플래그 확인/추가**

이미 있으면 유지, 없으면:

```python
parser.add_argument("--output", help="Output HTML file path")
```

- [ ] **Step 3: 커밋**

```bash
git add shared/life-coach/scripts/daily_report.py
git commit -m "fix: daily_report — date-based output filename"
```

### Task 11: weekly_report.py — 날짜 기반 파일명

**Files:**
- Modify: `shared/life-coach/scripts/weekly_report.py`

- [ ] **Step 1: 동일 패턴 적용**

```python
# weekly_coach.py의 반환값에 week_start 키가 없으므로 dates["monday"]를 사용
# (또는 weekly_coach.py에서 week_start를 추가)
date_str = data.get("monday", data.get("date_range", "unknown").split("~")[0].strip())
default_output = f"/tmp/weekly_report_{date_str}.html"
output_path = args.output or default_output
```

- [ ] **Step 2: 커밋**

```bash
git add shared/life-coach/scripts/weekly_report.py
git commit -m "fix: weekly_report — date-based output filename"
```

### Task 12: SKILL.md — 코칭 저장 절차 추가

**Files:**
- Modify: `shared/life-coach/SKILL.md`

- [ ] **Step 1: Step 3에 코칭 저장 절차 추가**

기존 Step 3e 이후에:

```markdown
#### Step 3e. 코칭 저장

이전 단계에서 생성한 코칭 마크다운을 DB에 저장:

코칭 마크다운을 저장할 때 **sections JSON도 함께 전달**한다. LLM이 코칭을 생성하면서 각 섹션 헤더(##)를 파싱하여 JSON으로 분해:

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py save-coaching \
    --date <DATE> --period daily \
    --content /tmp/coaching_<DATE>.md \
    --sections '{"summary":"오늘의 정리 내용","structure_review":"구조 리뷰 내용","coaching":"코칭 내용","question":"마무리 질문"}'
```

**sections 분해 책임**: CC 세션의 LLM이 코칭 마크다운을 생성한 뒤, 각 섹션을 JSON 키로 분리하여 `--sections` 인자로 전달. SKILL.md에 이 절차를 명시.

태스크 제안도 구조화하여 저장:

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py save-task \
    --date <DATE> --description "태스크 설명" --estimated-min 30 --priority 1 --source-type coaching
```

태스크 해소:

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py resolve-task \
    --id <TASK_ID> --status done --date <DATE> --method auto
```

Follow-up 해소:

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py resolve-followup \
    --id <CHAIN_ID> --status resolved --date <DATE> --note "해소 사유"
```
```

**주의:** activity_writer.py에 `save-coaching`, `save-task` CLI 커맨드를 추가해야 함 (Task 3에서 빠졌으면 여기서 추가).

- [ ] **Step 2: Step 3b에 이전 코칭 참조 절차 추가**

```markdown
#### Step 3b. 이전 코칭 참조

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py previous-coaching --date <DATE>
```

이 명령은 어제 coaching_entries + pending task_suggestions + open followup_chains를 JSON으로 출력.
코칭 생성 시 이 데이터를 참조하여 태스크 이행 여부 판단, follow-up 에스컬레이션에 활용.
```

- [ ] **Step 3: 커밋**

```bash
git add shared/life-coach/SKILL.md
git commit -m "feat: SKILL.md — add coaching storage + previous coaching reference steps"
```

### Task 13: coaching-prompts.md — 태스크 점검 + follow-up 체인 섹션

**Files:**
- Modify: `shared/life-coach/references/coaching-prompts.md`

- [ ] **Step 1: 일일 코칭 프레임에 섹션 추가**

`### 🔍 구조 리뷰` 앞에 삽입:

```markdown
### 📋 어제 태스크 점검
- `previous-coaching` 출력의 `pending_tasks`를 확인.
- 오늘 세션 데이터와 대조하여 이행 여부 판단.
- LLM이 판단 가능하면 자동 해소 → `save-task --resolve` 호출.
- 판단 불가하면 코칭 본문에 "이 태스크는 어떻게 됐어?" 포함.
- 3일 이상 pending: 강조하여 언급.
- 7일 이상 pending: "의도적으로 안 하는 건가?" 직접 질문.

### 🔗 Follow-up 체인 점검
- `previous-coaching` 출력의 `open_followups`를 확인.
- 오늘 세션의 session_content를 보고 실제 해소 여부 판단.
  (단순히 "같은 repo 작업"이 아니라 내용 기반 판단)
- 해소된 건: resolution_note와 함께 update.
- 미해소 + days_open >= 3: 에스컬레이션.
```

- [ ] **Step 2: 기존 `blocked_resolution` 참조를 followup_chains 기반으로 수정**

주간 코칭 섹션의 `### 🚧 블로커 해소 현황` (line 140-143):
- 기존: "같은 repo에서 후속 세션이 있으면 resolved" 설명 제거
- 새: "followup_chains 테이블의 status 기반. 코칭 시 LLM이 내용 기반으로 해소 판단"

- [ ] **Step 3: SKILL.md의 구 참조 정리**

`shared/life-coach/SKILL.md`에서:
- `raw_json` 참조 제거 → `session_content` 참조로 변경
- report 출력 예시의 고정 파일명 → 날짜 기반 파일명으로 변경
- `resolve-task`, `resolve-followup` CLI 예시 추가

- [ ] **Step 4: 커밋**

```bash
git add shared/life-coach/references/coaching-prompts.md shared/life-coach/SKILL.md
git commit -m "feat: coaching-prompts + SKILL.md — followup_chains migration, raw_json removal"
```

### Task 14: activity_writer.py — 코칭 저장 CLI 추가

**Files:**
- Modify: `shared/life-dashboard-mcp/activity_writer.py`

- [ ] **Step 1: save-coaching CLI 커맨드**

```python
def cmd_save_coaching(args):
    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        content = Path(args.content).read_text() if Path(args.content).exists() else args.content
        sections = json.loads(args.sections) if args.sections else {}
        upsert_coaching_entry(conn, {
            "date": args.date,
            "period_type": args.period,
            "content": content,
            "sections": json.dumps(sections, ensure_ascii=False),
            "escalation_level": args.escalation_level or 0,
        })
        conn.commit()
        print(f"Coaching saved: {args.date} ({args.period})", file=sys.stderr)
    finally:
        conn.close()
```

- [ ] **Step 2: save-task CLI 커맨드**

```python
def cmd_save_task(args):
    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        upsert_task_suggestion(conn, {
            "suggested_date": args.date,
            "description": args.description,
            "estimated_min": args.estimated_min,
            "priority": args.priority or 99,
            "source_type": args.source_type or "coaching",
            "origin_session_id": args.origin_session_id,
            "status": "pending",
        })
        conn.commit()
        print(f"Task saved: {args.description[:50]}", file=sys.stderr)
    finally:
        conn.close()
```

- [ ] **Step 3: previous-coaching CLI 커맨드**

```python
def cmd_previous_coaching(args):
    conn = get_conn()
    try:
        yesterday = (datetime.strptime(args.date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        coaching = get_coaching_entry(conn, yesterday, "daily")
        pending = get_pending_tasks(conn)
        followups = get_open_followups(conn)
        result = {
            "yesterday_coaching": dict(coaching) if coaching else None,
            "pending_tasks": pending,
            "open_followups": followups,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        conn.close()
```

- [ ] **Step 4: resolve-task, resolve-followup CLI 커맨드**

```python
def cmd_resolve_task(args):
    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        update_task_resolution(conn, args.id, args.status, args.date,
                              args.session_id, args.method, args.notes)
        conn.commit()
        print(f"Task {args.id} → {args.status}", file=sys.stderr)
    finally:
        conn.close()


def cmd_resolve_followup(args):
    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        update_followup_resolution(conn, args.id, args.status, args.date,
                                   args.session_id, args.note)
        conn.commit()
        print(f"Followup {args.id} → {args.status}", file=sys.stderr)
    finally:
        conn.close()
```

- [ ] **Step 5: main()에 새 커맨드 등록**

```python
p_coaching = sub.add_parser("save-coaching")
p_coaching.add_argument("--date", required=True)
p_coaching.add_argument("--period", required=True, choices=["daily", "weekly"])
p_coaching.add_argument("--content", required=True, help="Markdown content or file path")
p_coaching.add_argument("--sections", help="JSON sections")
p_coaching.add_argument("--escalation-level", type=int, dest="escalation_level")

p_task = sub.add_parser("save-task")
p_task.add_argument("--date", required=True)
p_task.add_argument("--description", required=True)
p_task.add_argument("--estimated-min", type=int, dest="estimated_min")
p_task.add_argument("--priority", type=int)
p_task.add_argument("--source-type", dest="source_type", default="coaching")
p_task.add_argument("--origin-session-id", dest="origin_session_id")

p_prev = sub.add_parser("previous-coaching")
p_prev.add_argument("--date", required=True)

p_resolve_task = sub.add_parser("resolve-task")
p_resolve_task.add_argument("--id", required=True, type=int)
p_resolve_task.add_argument("--status", required=True, choices=["done", "skipped", "deferred"])
p_resolve_task.add_argument("--date", required=True)
p_resolve_task.add_argument("--session-id", dest="session_id")
p_resolve_task.add_argument("--method", default="user", choices=["auto", "user"])
p_resolve_task.add_argument("--notes")

p_resolve_followup = sub.add_parser("resolve-followup")
p_resolve_followup.add_argument("--id", required=True, type=int)
p_resolve_followup.add_argument("--status", required=True, choices=["resolved", "abandoned", "superseded"])
p_resolve_followup.add_argument("--date", required=True)
p_resolve_followup.add_argument("--session-id", dest="session_id")
p_resolve_followup.add_argument("--note")

# dispatch:
elif args.command == "save-coaching":
    cmd_save_coaching(args)
elif args.command == "save-task":
    cmd_save_task(args)
elif args.command == "previous-coaching":
    cmd_previous_coaching(args)
elif args.command == "resolve-task":
    cmd_resolve_task(args)
elif args.command == "resolve-followup":
    cmd_resolve_followup(args)
```

- [ ] **Step 5: 수동 검증**

```bash
# 코칭 저장 테스트
python3 activity_writer.py save-coaching --date 2026-03-16 --period daily --content "테스트 코칭" --sections '{"summary":"test"}'
# 태스크 저장 테스트
python3 activity_writer.py save-task --date 2026-03-16 --description "테스트 태스크" --estimated-min 15 --priority 1
# 이전 코칭 조회
python3 activity_writer.py previous-coaching --date 2026-03-17
```

- [ ] **Step 6: import 추가**

```python
from datetime import datetime, timedelta
from db import ..., get_coaching_entry, get_pending_tasks, get_open_followups, \
    upsert_coaching_entry, upsert_task_suggestion
```

- [ ] **Step 7: 커밋**

```bash
git add shared/life-dashboard-mcp/activity_writer.py
git commit -m "feat: activity_writer CLI — save-coaching, save-task, previous-coaching commands"
```

### Task 15: 최종 통합 검증

- [ ] **Step 1: 전체 파이프라인 테스트**

```bash
# 1. scanner로 현재 세션 기록
python3 cc/work-digest/scripts/active_session_scanner.py

# 2. 오늘 데이터 확인
python3 shared/life-dashboard-mcp/activity_writer.py unsummarized --date 2026-03-16

# 3. daily coach JSON 추출
python3 shared/life-coach/scripts/daily_coach.py --json --date 2026-03-16 2>/dev/null | python3 -m json.tool | head -50

# 4. daily coach template report
python3 shared/life-coach/scripts/daily_coach.py --dry-run --date 2026-03-16
```

- [ ] **Step 2: DB 확인**

```bash
cd shared/life-dashboard-mcp && python3 -c "
from db import get_conn
c = get_conn()
for table in ['sessions', 'session_content', 'signals', 'coaching_entries', 'task_suggestions', 'followup_chains']:
    count = c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(f'{table}: {count} rows')
"
```

- [ ] **Step 3: 커밋 (없으면 skip)**
