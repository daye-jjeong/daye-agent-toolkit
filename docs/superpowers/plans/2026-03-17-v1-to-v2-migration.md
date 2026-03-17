# v1→v2 DB 마이그레이션 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v1 테이블(activities, behavioral_signals) 코드 의존성을 v2(sessions, signals)로 전환하고 v1 코드 제거

**Architecture:** 기존 v2 테이블 구조 유지. Writer(session_logger) → Reader(collect.py) 순서로 전환 후 v1 코드 삭제.

**Tech Stack:** Python3, SQLite, pytest

**Spec:** `docs/superpowers/specs/2026-03-17-v1-to-v2-migration-design.md`

---

### Task 1: CC session_logger 버그 수정 — signals 실패 시 record_sessions 호출

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py:680-715`

- [ ] **Step 1: signals 실패 경로를 record_sessions로 통합**

현재 (680-715행):
```python
if event == "SessionEnd":
    user_msgs = extract_user_messages(transcript_path)
    signals = None
    try:
        signals = extract_behavioral_signals(user_msgs, repo)
    except Exception as e:
        print(f"[session_logger] signals failed: {e}", file=sys.stderr)

    if signals:
        _, branch = detect_repo_and_branch(cwd) if cwd else ("unknown", None)
        record_sessions("cc", session_id, by_date, repo, branch,
                       behavioral_signals=signals,
                       is_session_end=True)
    else:
        # 직접 SQL UPDATE — record_sessions 우회
        try:
            from db import get_conn as _get_conn
            ...
```

변경:
```python
if event == "SessionEnd":
    user_msgs = extract_user_messages(transcript_path)
    signals = None
    try:
        signals = extract_behavioral_signals(user_msgs, repo)
    except Exception as e:
        print(f"[session_logger] signals failed: {e}", file=sys.stderr)

    _, branch = detect_repo_and_branch(cwd) if cwd else ("unknown", None)
    record_sessions("cc", session_id, by_date, repo, branch,
                   behavioral_signals=signals,
                   is_session_end=True)
```

핵심: `if signals:` 분기 제거. signals가 None이어도 record_sessions 호출. record_sessions 내부에서 signals가 None이면 signal insert를 건너뛰고, is_session_end=True이므로 status='completed' 설정됨.

- [ ] **Step 2: 커밋**

```bash
git add cc/work-digest/scripts/session_logger.py
git commit -m "fix: SessionEnd에서 signals 실패 시에도 record_sessions 호출"
```

---

### Task 2: Codex 로거 v2 전환 — record_activities → record_sessions

**Files:**
- Modify: `codex/work-digest/scripts/session_logger.py:19,769,802-804`

- [ ] **Step 1: import 변경**

```python
# Before (line 19):
from activity_writer import record_activities

# After:
from activity_writer import record_sessions
```

- [ ] **Step 2: 첫 번째 호출 변경 (mid-session recording)**

```python
# Before (line 769):
record_activities("codex", session_id, by_date, repo)

# After:
record_sessions("codex", session_id, by_date, repo)
```

- [ ] **Step 3: 두 번째 호출 변경 (session_end/compaction)**

```python
# Before (lines 802-804):
if summary or signals:
    record_activities("codex", session_id, by_date, repo,
                    summary=summary, behavioral_signals=signals)

# After:
if summary or signals:
    record_sessions("codex", session_id, by_date, repo,
                   summary=summary, behavioral_signals=signals,
                   is_session_end=(args.event == "session_end"))
```

- [ ] **Step 4: 커밋**

```bash
git add codex/work-digest/scripts/session_logger.py
git commit -m "feat: Codex 로거 record_activities→record_sessions 전환"
```

---

### Task 3: self-profile collect.py v2 전환

**Files:**
- Modify: `shared/self-profile/scripts/collect.py:32-39,165-200`
- Modify: `shared/self-profile/tests/test_collect.py:10-26`
- Modify: `shared/self-profile/tests/conftest.py` (변경 없을 수 있음 — schema.sql이 v2 포함하므로)

- [ ] **Step 1: 테스트 fixture를 v2 테이블로 변경**

`test_collect.py` — `_insert_activity` → `_insert_session`, `_insert_signal` → v2 signals:

```python
def _insert_session(conn, *, source="cc", session_id="s1", repo="test-repo",
                    tag="코딩", start_at="2026-03-01 10:00", end_at="2026-03-01 10:30",
                    date="2026-03-01", duration_min=30):
    conn.execute("""
        INSERT INTO sessions (source, session_id, date, repo, tag, start_at, end_at, duration_min)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (source, session_id, date, repo, tag, start_at, end_at, duration_min))
    conn.commit()


def _insert_signal(conn, *, session_id="s1", date="2026-03-01",
                   signal_type="mistake", content="test signal", repo="test-repo",
                   reasoning=None):
    conn.execute("""
        INSERT INTO signals (session_id, date, signal_type, content, reasoning, repo)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, date, signal_type, content, reasoning, repo))
    conn.commit()
```

테스트 본문에서 `_insert_activity` 호출을 모두 `_insert_session`으로 변경. `date` 파라미터 추가 필요 (sessions는 date NOT NULL).

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd shared/self-profile && python3 -m pytest tests/ -v
```

Expected: 실패 (collect.py가 아직 activities 조회)

- [ ] **Step 3: collect.py 쿼리 전환 — _query_activities → _query_sessions**

```python
def _query_sessions(conn, start: str, next_end: str) -> list:
    """sessions 테이블 1회 쿼리. sessions + daily_trend 양쪽에서 사용."""
    return conn.execute("""
        SELECT source, repo, tag, start_at, duration_min
        FROM sessions
        WHERE date >= ? AND date < ?
        ORDER BY start_at
    """, (start, next_end)).fetchall()
```

변경 포인트:
- 함수명: `_query_activities` → `_query_sessions`
- 테이블: `activities` → `sessions`
- WHERE: `start_at >= ? AND start_at < ?` → `date >= ? AND date < ?` (sessions는 date 컬럼이 NOT NULL이므로 더 정확)

`_collect_from_conn`에서 호출부도 변경: `_query_activities` → `_query_sessions`

- [ ] **Step 4: collect.py 쿼리 전환 — _collect_behavioral_signals → v2 signals**

```python
def _collect_behavioral_signals(conn, start: str, end: str) -> dict:
    """Query signals (v2) and build summary."""
    rows = conn.execute("""
        SELECT signal_type, content, reasoning, date, repo
        FROM signals
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
    """, (start, end)).fetchall()

    by_type: dict[str, list[dict]] = {st: [] for st in SIGNAL_TYPES}
    content_counts: dict[str, dict] = {}

    for r in rows:
        entry = {
            "content": r["content"],
            "reasoning": r["reasoning"],
            "date": r["date"],
            "repo": r["repo"] or "",
        }
        st = r["signal_type"]
        if st in by_type:
            by_type[st].append(entry)

        key = r["content"]
        if key not in content_counts:
            content_counts[key] = {"content": key, "count": 0, "type": st}
        content_counts[key]["count"] += 1

    repeat_signals = sorted(
        [v for v in content_counts.values() if v["count"] >= 2],
        key=lambda x: x["count"], reverse=True
    )

    return {
        "summary": {f"{st}s_count": len(by_type[st]) for st in SIGNAL_TYPES},
        "top_decisions": by_type["decision"][:_TOP_SIGNALS_LIMIT],
        "top_mistakes": by_type["mistake"][:_TOP_SIGNALS_LIMIT],
        "top_patterns": by_type["pattern"][:_TOP_SIGNALS_LIMIT],
        "repeat_signals": repeat_signals[:_TOP_SIGNALS_LIMIT],
        "decision_profile": _build_decision_profile(by_type["decision"]),
    }
```

변경: `behavioral_signals` → `signals`, `reasoning` 필드 추가.

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
cd shared/self-profile && python3 -m pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 6: 커밋**

```bash
git add shared/self-profile/scripts/collect.py shared/self-profile/tests/test_collect.py
git commit -m "feat: self-profile collect.py를 v2 테이블(sessions, signals)로 전환"
```

---

### Task 4: v1 코드 제거

**Files:**
- Modify: `shared/life-dashboard-mcp/activity_writer.py:1-10,27-36,240-308`
- Modify: `shared/life-dashboard-mcp/db.py:32-57,87-102,258-262,277-286,299-305,113-118`
- Modify: `shared/life-dashboard-mcp/schema.sql:1-62`
- Modify: `shared/life-dashboard-mcp/backfill_tags.py:35-67`

- [ ] **Step 1: activity_writer.py — record_activities 삭제 + import/docstring 정리**

삭제 대상:
- Line 6: `from activity_writer import record_activities  # v1 — Codex compat (activities table)` docstring
- Line 30: `upsert_activity, insert_behavioral_signal,` import
- Lines 240-308: `record_activities()` 함수 전체

docstring 변경:
```python
"""Activity Writer — shared SQLite recording for CC and Codex session loggers.

Usage (library):
    from activity_writer import record_sessions
```

import 변경:
```python
from db import (
    get_conn,
    upsert_session, upsert_session_content, upsert_session_topics, insert_signal,
    upsert_followup_chain, update_daily_stats,
    upsert_coaching_entry, upsert_task_suggestion,
    update_task_resolution, update_followup_resolution,
    get_coaching_entry, get_pending_tasks, get_open_followups,
)
```

- [ ] **Step 2: db.py — v1 함수 삭제**

삭제:
- Lines 32-57: `_migrate()` 함수 전체 (activities 컬럼 마이그레이션)
- Line 27: `_migrate(conn)` 호출 제거
- Lines 87-102: `upsert_activity()` 함수
- Lines 258-262: `insert_behavioral_signal()` 함수

- [ ] **Step 3: db.py — fallback 분기 제거**

`update_daily_stats` (lines 113-118) — activities fallback 삭제:
```python
# Before:
    rows = conn.execute("SELECT ... FROM sessions WHERE date = ?", ...).fetchall()
    if not rows:
        rows = conn.execute("SELECT ... FROM activities WHERE ...", ...).fetchall()

# After:
    rows = conn.execute("SELECT ... FROM sessions WHERE date = ?", ...).fetchall()
```

`get_repeated_signals` (lines 277-286) — behavioral_signals fallback 삭제:
```python
# Before:
    rows = conn.execute("SELECT ... FROM signals ...").fetchall()
    if not rows:
        rows = conn.execute("SELECT ... FROM behavioral_signals ...").fetchall()

# After:
    rows = conn.execute("SELECT ... FROM signals ...").fetchall()
```

`get_mistake_trends` (lines 299-305) — behavioral_signals fallback 삭제:
```python
# Before:
    rows = conn.execute("SELECT ... FROM signals ...").fetchall()
    if not rows:
        rows = conn.execute("SELECT ... FROM behavioral_signals ...").fetchall()

# After:
    rows = conn.execute("SELECT ... FROM signals ...").fetchall()
```

- [ ] **Step 4: schema.sql — v1 테이블 정의 제거**

삭제 (lines 1-26 + 50-62):
- `CREATE TABLE IF NOT EXISTS activities (...)` + 인덱스 3개
- `CREATE TABLE IF NOT EXISTS behavioral_signals (...)` + 인덱스 3개

주의: `daily_stats`, `coach_state` 테이블 정의는 유지 (v1이 아님).

- [ ] **Step 5: backfill_tags.py — v1 fallback 제거**

```python
# Before (lines 35-43):
        if not rows:
            # fallback: v1 activities
            rows = conn.execute(
                "SELECT id, source, session_id, repo, tag, summary, raw_json "
                "FROM activities WHERE tag = '기타' OR tag = '' OR tag IS NULL"
            ).fetchall()
            table = "activities"
        else:
            table = "sessions"

# After:
        table = "sessions"
```

Also remove the `if table == "sessions": ... else: ...` branch in the loop (lines 51-57), keeping only the sessions path:
```python
            topic = r["topic"] or ""
            commands = " ".join(json.loads(r["commands"] or "[]")[:5])
```

- [ ] **Step 6: 기존 테스트 실행**

```bash
cd shared/life-dashboard-mcp && python3 -m pytest tests/ -v
cd shared/self-profile && python3 -m pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 7: 커밋**

```bash
git add shared/life-dashboard-mcp/activity_writer.py shared/life-dashboard-mcp/db.py \
        shared/life-dashboard-mcp/schema.sql shared/life-dashboard-mcp/backfill_tags.py
git commit -m "refactor: v1 테이블(activities, behavioral_signals) 코드 제거"
```

---

### Task 5: 검증

- [ ] **Step 1: 전체 테스트 실행**

```bash
cd shared/life-dashboard-mcp && python3 -m pytest tests/ -v
cd shared/self-profile && python3 -m pytest tests/ -v
```

- [ ] **Step 2: v1 잔존 참조 검색**

```bash
grep -rn "activities\|behavioral_signals\|record_activities\|upsert_activity\|insert_behavioral_signal" \
  shared/life-dashboard-mcp/ shared/self-profile/ cc/work-digest/ codex/work-digest/ \
  --include="*.py" --include="*.sql" | grep -v "test_" | grep -v "__pycache__"
```

Expected: 0 matches (테스트 파일 제외)
