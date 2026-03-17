# Session Topics Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 세션 내 작업 단위(토픽)를 분리 기록하여 리포트와 집계에서 개별 작업이 축소되지 않고 표시되도록 한다.

**Architecture:** session_topics 테이블(1:N from sessions)로 토픽 분해 결과를 저장. Layer 2(enrichment)에서 코드 신호 + LLM으로 토픽을 생성하고, 소비자(daily_report, daily_coach, timeline)는 session_topics를 기준으로 작업 내용을 표시. 시간/토큰 통계는 sessions에서만 산출.

**Tech Stack:** Python 3 stdlib (sqlite3, json, argparse), SQLite

**Spec:** `docs/superpowers/specs/2026-03-16-session-topics.md`

---

## File Structure

| 파일 | 역할 | 변경 유형 |
|------|------|-----------|
| `shared/life-dashboard-mcp/schema.sql` | session_topics DDL | Modify |
| `shared/life-dashboard-mcp/db.py` | upsert/get CRUD | Modify |
| `shared/life-dashboard-mcp/activity_writer.py` | record_sessions + update-topics CLI | Modify |
| `cc/work-digest/scripts/session_logger.py` | summarize_session → 토픽 배열, 코드 경계 감지 | Modify |
| `cc/work-digest/scripts/active_session_scanner.py` | 기존 topics 보호 | Modify |
| `shared/life-coach/scripts/daily_coach.py` | 두 스트림(sessions + topics) 반환 | Modify |
| `shared/life-coach/scripts/daily_report.py` | 토픽별 표시 | Modify |
| `shared/life-coach/scripts/timeline_html.py` | 토픽별 바 | Modify |
| `shared/life-coach/scripts/_helpers.py` | dedup 분리 | Modify |
| `shared/life-coach/SKILL.md` | Step 3a 토픽 분해 지침 | Modify |
| `shared/life-dashboard-mcp/tests/test_session_topics.py` | DB CRUD 테스트 | Create |

---

## Chunk 1: DB 기반 — 스키마 + CRUD + CLI

### Task 1: schema.sql — session_topics 테이블 추가

**Files:**
- Modify: `shared/life-dashboard-mcp/schema.sql`

- [ ] **Step 1: session_topics CREATE TABLE 추가**

기존 `session_content` CREATE 문 아래에 추가:

```sql
-- ── Session Topics (1:N from sessions) ──────────
CREATE TABLE IF NOT EXISTS session_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    topic_order INTEGER NOT NULL DEFAULT 0,
    tag TEXT,
    summary TEXT NOT NULL,
    repo TEXT,
    duration_estimate_min INTEGER,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, session_id, date, topic_order),
    FOREIGN KEY (source, session_id, date)
        REFERENCES sessions(source, session_id, date)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_topics_date ON session_topics(date);
CREATE INDEX IF NOT EXISTS idx_session_topics_tag ON session_topics(tag);
CREATE INDEX IF NOT EXISTS idx_session_topics_fk ON session_topics(source, session_id, date);
```

- [ ] **Step 2: 검증 — DB 초기화 테스트**

```bash
cd shared/life-dashboard-mcp
python3 -c "from db import get_conn; c=get_conn(); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])"
```

Expected: `session_topics`가 목록에 포함.

- [ ] **Step 3: 커밋**

```bash
git add shared/life-dashboard-mcp/schema.sql
git commit -m "feat: add session_topics table to schema"
```

### Task 2: db.py — CRUD 함수 추가

**Files:**
- Modify: `shared/life-dashboard-mcp/db.py`
- Create: `shared/life-dashboard-mcp/tests/test_session_topics.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_session_topics.py
"""session_topics CRUD 테스트."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db import get_conn, upsert_session, upsert_session_topics, get_session_topics, update_daily_stats

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
    for name, func in list(globals().items()):
        if name.startswith("test_"):
            try:
                func()
                print(f"  PASS {name}")
            except Exception as e:
                print(f"  FAIL {name}: {e}")
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd shared/life-dashboard-mcp
python3 tests/test_session_topics.py
```

Expected: `upsert_session_topics` not found 에러.

- [ ] **Step 3: db.py에 CRUD 함수 구현**

`update_daily_stats()` 아래에 추가:

```python
def upsert_session_topics(
    conn: sqlite3.Connection,
    source: str, session_id: str, date: str,
    topics: list[dict],
):
    """session_topics 전체 교체 (DELETE + INSERT)."""
    conn.execute(
        "DELETE FROM session_topics WHERE source=? AND session_id=? AND date=?",
        (source, session_id, date),
    )
    for i, t in enumerate(topics):
        if not t.get("summary"):
            continue
        conn.execute("""
            INSERT INTO session_topics (source, session_id, date, topic_order, tag, summary, repo, duration_estimate_min)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (source, session_id, date, i, t.get("tag"), t["summary"], t.get("repo"), t.get("duration_estimate_min")))


def get_session_topics(conn: sqlite3.Connection, date: str) -> list[dict]:
    """해당 날짜의 모든 session_topics 조회."""
    rows = conn.execute("""
        SELECT st.*, s.source as s_source, s.status, s.has_commits, s.has_tests,
               s.start_at, s.duration_min, s.token_total
        FROM session_topics st
        JOIN sessions s USING (source, session_id, date)
        WHERE st.date = ?
        ORDER BY s.start_at, st.topic_order
    """, (date,)).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: update_daily_stats()에 토픽 기준 tag_breakdown 추가**

`update_daily_stats()` 함수에서 `tags` 집계 부분을 수정:

기존 `update_daily_stats()` 함수 전체를 교체. 핵심 변경: tag 집계를 session_topics에서 먼저 시도하고, 없으면 sessions.tag 폴백. repos/total_min/first/last는 sessions 기준 유지.

```python
def update_daily_stats(conn: sqlite3.Connection, date_str: str):
    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    # v2: sessions 테이블 우선, 없으면 activities fallback
    rows = conn.execute("""
        SELECT tag, repo, duration_min, start_at, end_at
        FROM sessions
        WHERE date = ?
    """, (date_str,)).fetchall()
    if not rows:
        rows = conn.execute("""
            SELECT tag, repo, duration_min, start_at, end_at
            FROM activities
            WHERE start_at >= ? AND start_at < ?
        """, (date_str, next_date)).fetchall()

    if not rows:
        conn.execute("DELETE FROM daily_stats WHERE date = ?", (date_str,))
        return

    # tag_breakdown: 토픽 기준 우선, 없으면 sessions.tag 폴백
    topic_rows = conn.execute(
        "SELECT tag FROM session_topics WHERE date = ?", (date_str,)
    ).fetchall()

    tags: dict[str, int] = {}
    if topic_rows:
        for r in topic_rows:
            tag = r["tag"] or "기타"
            tags[tag] = tags.get(tag, 0) + 1
    else:
        for r in rows:
            tag = r["tag"] or "기타"
            tags[tag] = tags.get(tag, 0) + 1

    # repos, total_min, first/last — sessions 기준 (변경 없음)
    repos: dict[str, int] = {}
    total_min = 0
    first_session = "99:99"
    last_end = "00:00"

    for r in rows:
        repo = r["repo"] or "unknown"
        repos[repo] = repos.get(repo, 0) + 1
        total_min += r["duration_min"] or 0
        start_time = r["start_at"][11:16] if r["start_at"] and len(r["start_at"]) > 15 else "00:00"
        end_time = r["end_at"][11:16] if r["end_at"] and len(r["end_at"]) > 15 else start_time
        if start_time < first_session:
            first_session = start_time
        if end_time > last_end:
            last_end = end_time

    conn.execute("""
        INSERT INTO daily_stats (date, work_hours, session_count, tag_breakdown,
            repos, first_session, last_session_end)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            work_hours=excluded.work_hours, session_count=excluded.session_count,
            tag_breakdown=excluded.tag_breakdown, repos=excluded.repos,
            first_session=excluded.first_session, last_session_end=excluded.last_session_end,
            updated_at=datetime('now','localtime')
    """, (
        date_str,
        round(total_min / 60, 1),
        len(rows),
        json.dumps(tags, ensure_ascii=False),
        json.dumps(repos, ensure_ascii=False),
        first_session,
        last_end,
    ))
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
cd shared/life-dashboard-mcp
python3 tests/test_session_topics.py
```

Expected: 모든 테스트 PASS.

- [ ] **Step 6: 커밋**

```bash
git add shared/life-dashboard-mcp/db.py shared/life-dashboard-mcp/tests/test_session_topics.py
git commit -m "feat: db.py — upsert_session_topics, get_session_topics, topic-based tag_breakdown"
```

### Task 3: activity_writer.py — record_sessions + update-topics CLI

**Files:**
- Modify: `shared/life-dashboard-mcp/activity_writer.py`

- [ ] **Step 1: record_sessions()에 topics 파라미터 추가**

시그니처에 `topics: list[dict] | None = None` 추가. summary 처리 후, topics가 있으면 session_topics INSERT + sessions.summary 캐시:

```python
def record_sessions(
    source: str,
    session_id: str,
    by_date: dict[str, dict],
    repo: str,
    branch: str | None = None,
    summary: dict | None = None,
    topics: list[dict] | None = None,  # NEW
    behavioral_signals: dict | None = None,
    is_session_end: bool = False,
) -> dict[str, str]:
```

기존 summary 로직 아래에 추가:

```python
            # session_topics — topics가 있으면 해당 date의 토픽 저장
            if topics:
                date_topics = [t for t in topics if t.get("date", date_str) == date_str]
                if not date_topics:
                    date_topics = topics  # date 필드 없으면 전부 현재 date에 귀속
                if date_topics:
                    from db import upsert_session_topics
                    upsert_session_topics(conn, source, session_id, date_str, date_topics)
                    # sessions.summary/tag 캐시 — 첫 번째 토픽으로
                    first = date_topics[0]
                    conn.execute("""
                        UPDATE sessions SET summary = ?, tag = ?, summary_source = 'llm'
                        WHERE source = ? AND session_id = ? AND date = ?
                    """, (first["summary"], first.get("tag"), source, session_id, date_str))
```

- [ ] **Step 2: update-topics CLI 추가**

`cmd_update_summary` 아래에 추가:

```python
def cmd_update_topics(args):
    """Step 3a용: 세션의 토픽을 전체 교체."""
    conn = get_conn()
    try:
        topics = json.loads(args.topics)
        if not isinstance(topics, list) or not topics:
            print("Error: --topics must be a non-empty JSON array", file=sys.stderr)
            sys.exit(1)
        # 검증
        valid = [t for t in topics if t.get("summary")]
        if not valid:
            print("Error: no valid topics (summary required)", file=sys.stderr)
            sys.exit(1)
        if len(valid) > 10:
            print(f"Warning: {len(valid)} topics, capping at 10", file=sys.stderr)
            valid = valid[:10]
        upsert_session_topics(conn, "cc", args.session_id, args.date, valid)
        # sessions.summary/tag 캐시
        first = valid[0]
        conn.execute("""
            UPDATE sessions SET summary = ?, tag = ?, summary_source = 'llm'
            WHERE source = 'cc' AND session_id = ? AND date = ?
        """, (first["summary"], first.get("tag"), args.session_id, args.date))
        update_daily_stats(conn, args.date)
        conn.commit()
        print(f"Updated {len(valid)} topics for {args.session_id}", file=sys.stderr)
    finally:
        conn.close()
```

argparse에 추가:

```python
    p_topics = sub.add_parser("update-topics", help="Replace session topics")
    p_topics.add_argument("--session-id", required=True)
    p_topics.add_argument("--date", required=True)
    p_topics.add_argument("--topics", required=True, help='JSON array: [{"tag":"..","summary":"..","repo":".."}]')
```

dispatch에 추가:

```python
        "update-topics": cmd_update_topics,
```

- [ ] **Step 3: CLI 테스트**

```bash
cd shared/life-dashboard-mcp
# 먼저 테스트 세션 존재 확인 후 update-topics 실행
python3 activity_writer.py update-topics --session-id test-123 --date 2026-03-16 \
  --topics '[{"tag":"설계","summary":"spec 작성","repo":"test"}]'
```

Expected: 세션이 없으면 에러, 있으면 "Updated 1 topics" 출력.

- [ ] **Step 4: 커밋**

```bash
git add shared/life-dashboard-mcp/activity_writer.py
git commit -m "feat: activity_writer — topics param in record_sessions + update-topics CLI"
```

---

## Chunk 2: 생산자 — session_logger 토픽 분해

### Task 4: session_logger.py — summarize_session 토픽 배열 리턴

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py`

- [ ] **Step 1: summarize_session() 프롬프트 변경**

기존 프롬프트(line 178-202)를 토픽 배열 리턴 형식으로 교체:

```python
def summarize_session(conversation: str, repo: str) -> list[dict] | None:
    """claude CLI로 세션 토픽 분해 + 요약. 실패 시 None.

    Returns: [{"tag": "코딩", "summary": "...", "repo": "..."}, ...] or None
    """
    if not conversation.strip():
        return None
    tags_str = ", ".join(WORK_TAGS)
    prompt = (
        f"레포: {repo}\n\n"
        f"다음은 Claude Code 세션의 대화 내용이다.\n\n"
        f"{conversation}\n\n"
        "이 세션에서 수행한 작업을 토픽별로 분해하라.\n"
        "하나의 작업만 했으면 1개, 여러 작업을 오갔으면 각각 분리.\n\n"
        "토픽 분리 기준:\n"
        "- 다른 레포로 전환 → 별도 토픽\n"
        "- 다른 브랜치로 전환 → 별도 토픽\n"
        "- 명확히 다른 목적의 작업 → 별도 토픽\n"
        "- 같은 목적의 연속 작업 → 하나로 합침\n\n"
        f"각 토픽의 태그 선택지: {tags_str}\n\n"
        "요약 기준:\n"
        "- 무엇을(기능/모듈), 왜(문제/목적), 결과(산출물/변경)\n"
        "- 브랜치명이 있으면 포함\n"
        "- 나쁜 예: '설계 논의', 'PR 리뷰'\n"
        "- 좋은 예: 'session logger 파이프라인 개편 — 열린 세션 누락 해결'\n\n"
        "JSON 배열로만 답하라. 다른 텍스트 금지:\n"
        '[{"tag": "태그", "summary": "요약", "repo": "레포명"}]'
    )
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "sonnet", "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=SUMMARY_TIMEOUT_SEC,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _parse_topics_response(result.stdout.strip(), repo)
    except subprocess.TimeoutExpired:
        print(f"[session_logger] summarize_session timed out ({SUMMARY_TIMEOUT_SEC}s)", file=sys.stderr)
    except FileNotFoundError:
        print("[session_logger] 'claude' CLI not found on PATH", file=sys.stderr)
    except Exception as e:
        print(f"[session_logger] summarize_session failed: {type(e).__name__}: {e}", file=sys.stderr)
    return None
```

- [ ] **Step 2: _parse_topics_response() 추가**

기존 `_parse_summary_response()` 아래에 추가:

```python
def _parse_topics_response(raw: str, fallback_repo: str) -> list[dict] | None:
    """JSON 토픽 배열 파싱 + 검증."""
    # JSON 블록 추출 (```json ... ``` 또는 bare JSON)
    import re
    json_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not json_match:
        # 폴백: 기존 단일 요약 형식 시도
        old = _parse_summary_response(raw)
        if old:
            return [{"tag": old.get("tag", "기타"), "summary": old["text"], "repo": fallback_repo}]
        return None
    try:
        topics = json.loads(json_match.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(topics, list) or not topics:
        return None
    # 검증: summary 필수, tag 검증, 10개 상한
    valid = []
    for t in topics[:10]:
        if not isinstance(t, dict) or not t.get("summary"):
            continue
        tag = t.get("tag", "기타")
        if tag not in WORK_TAGS:
            tag = "기타"
        valid.append({
            "tag": tag,
            "summary": t["summary"],
            "repo": t.get("repo", fallback_repo),
        })
    return valid if valid else None
```

- [ ] **Step 3: main()에서 topics 전달**

`session_logger.py` main() 함수에서 `record_sessions` 호출 부분(line 760):

기존:
```python
record_sessions("cc", session_id, by_date, repo, branch,
               summary=summary, behavioral_signals=signals,
               is_session_end=True)
```

변경:
```python
# summary가 list면 새 토픽 형식, dict면 기존 형식
topics = summary if isinstance(summary, list) else None
legacy_summary = summary if isinstance(summary, dict) else None
# 토픽에서 대표 summary dict 생성 (기존 호환)
if topics and not legacy_summary:
    first = topics[0]
    legacy_summary = {"tag": first["tag"], "text": first["summary"]}
record_sessions("cc", session_id, by_date, repo, branch,
               summary=legacy_summary, topics=topics,
               behavioral_signals=signals,
               is_session_end=True)
```

- [ ] **Step 4: 커밋**

```bash
git add cc/work-digest/scripts/session_logger.py
git commit -m "feat: session_logger — topic-array summarization + _parse_topics_response"
```

### Task 5: active_session_scanner.py — 기존 topics 보호

**Files:**
- Modify: `cc/work-digest/scripts/active_session_scanner.py`

- [ ] **Step 1: scanner에서 record_sessions 호출 시 topics=None 명시**

scanner는 Layer 1만 수행 (토픽 생성 안 함). 기존 토픽이 있으면 덮어쓰지 않도록 record_sessions에 topics=None (기본값)으로 호출. 현재 코드에서 이미 summary=None으로 호출하므로, topics도 기본값 None이라 변경 불필요.

확인만:

```bash
grep -n "record_sessions" cc/work-digest/scripts/active_session_scanner.py
```

Expected: topics 파라미터 없이 호출 → 기본값 None → 기존 토픽 보호됨.

- [ ] **Step 2: 커밋 (변경 없으면 skip)**

---

## Chunk 3: 소비자 — daily_coach, daily_report, timeline

### Task 6: _helpers.py — dedup 분리

**Files:**
- Modify: `shared/life-coach/scripts/_helpers.py`

- [ ] **Step 1: dedup_sessions 유지, topics용 함수 추가 불필요**

현재 `dedup_sessions()`는 session_id prefix 기반 중복 제거. topics 스트림은 dedup 대상이 아니므로 호출하지 않으면 된다. 함수 자체는 변경 불필요.

확인 사항: topics를 쓰는 곳에서 dedup을 호출하지 않도록 주의.

### Task 7: daily_coach.py — 두 스트림 반환

**Files:**
- Modify: `shared/life-coach/scripts/daily_coach.py`

- [ ] **Step 1: get_today_data()에 topics 스트림 추가**

`get_today_data()` 함수에서 `sessions` 조회 후, session_topics JOIN 추가:

```python
    # v2: session_topics 조회
    from db import get_session_topics
    topic_rows = get_session_topics(conn, date_str)
```

return dict에 추가:

```python
        "topics": topic_rows,  # session_topics JOIN 결과
```

- [ ] **Step 2: _build_repos_detail() 텍스트 모드도 topics 대응**

`daily_coach.py`의 `_build_repos_detail(data)` (텔레그램 텍스트 모드)도 topics가 있으면 토픽별 표시:

```python
def _build_repos_detail(data: dict) -> str | None:
    sessions = data.get("sessions", [])
    topics = data.get("topics", [])
    if not sessions:
        return None

    lines = ["📂 레포별:"]
    if topics:
        # 토픽 기준 표시
        repo_topics: dict[str, list[dict]] = {}
        for t in topics:
            repo = (t.get("repo") or "unknown").split("/")[-1]
            repo_topics.setdefault(repo, []).append(t)
        for repo, ts in sorted(repo_topics.items()):
            lines.append(f"  ▸ {repo}")
            for t in ts[:5]:
                tag = t.get("tag", "")
                summary = (t.get("summary") or "")[:80]
                lines.append(f"    - [{tag}] {summary}")
    else:
        # 기존 세션 기반 로직
        for repo, total_dur, total_tok, branch_groups in group_sessions_by_repo_branch(sessions):
            # ... 기존 코드 유지 ...
    return "\n".join(lines)
```

- [ ] **Step 3: 커밋**

```bash
git add shared/life-coach/scripts/daily_coach.py
git commit -m "feat: daily_coach — add topics stream to get_today_data"
```

### Task 8: daily_report.py — 토픽별 표시

**Files:**
- Modify: `shared/life-coach/scripts/daily_report.py`

- [ ] **Step 1: _build_work_items() 토픽 입력 수용**

`_build_work_items()` 함수를 `_build_work_items(sessions, topics=None)`으로 변경.
topics가 있으면 토픽별 표시, 없으면 기존 세션별 표시 (폴백):

```python
def _build_work_items(sessions: list[dict], topics: list[dict] | None = None) -> str:
    """토픽별(우선) 또는 세션별 작업 표시."""
    if topics:
        return _build_topic_items(topics)
    # 기존 세션별 로직 (폴백)
    # ... 기존 코드 유지 ...
```

새 함수:

```python
def _build_topic_items(topics: list[dict]) -> str:
    """session_topics 기준 작업 표시."""
    items = []
    for t in topics:
        tag = t.get("tag") or "기타"
        tag_color = TAG_COLORS.get(tag, "#707070")
        summary = _esc(t.get("summary") or "(요약 없음)")
        status = t.get("status", "in_progress")
        status_badge = _status_badge(status)
        source = t.get("s_source") or t.get("source", "")
        src_html = ""
        if source:
            src_color = SOURCE_COLORS.get(source, "#888")
            src_html = f'<span class="src-tag" style="color:{src_color}">[{source}]</span> '
        dur = t.get("duration_estimate_min")
        meta_parts = []
        if dur:
            meta_parts.append(f"~{dur}m")
        if t.get("has_commits"):
            meta_parts.append("커밋")
        meta_str = (
            f' <span class="work-meta">({", ".join(meta_parts)})</span>'
            if meta_parts else ""
        )
        items.append(
            f'<div class="work-item">'
            f'{status_badge}'
            f'{src_html}'
            f'<span class="sess-tag" style="color:{tag_color}">[{tag}]</span> '
            f'<span class="work-summary">{summary}{meta_str}</span>'
            f'</div>'
        )
    return "".join(items)
```

- [ ] **Step 2: _build_repos_detail()에 topics 전달**

`_build_repos_detail(data)` 호출 시 topics를 전달하도록 변경:

```python
def _build_repos_detail(data: dict) -> str:
    sessions = data.get("sessions", [])
    topics = data.get("topics", [])
    if not sessions and not topics:
        return ""

    # topics가 있으면 repo별 토픽 그룹핑
    if topics:
        repo_topics: dict[str, list[dict]] = {}
        for t in topics:
            repo = (t.get("repo") or "unknown").split("/")[-1]
            repo_topics.setdefault(repo, []).append(t)
        rows = []
        for repo, ts in sorted(repo_topics.items()):
            inner_html = _build_topic_items(ts)
            rows.append(
                f'<div class="repo-group">'
                f'<div class="repo-name">{_esc(repo)}</div>'
                f'{inner_html}'
                f'</div>'
            )
        # ... legend + return ...
```

기존 세션 기반 로직은 `else:` 분기로 유지.

- [ ] **Step 3: build_daily_report()에서 topics 전달 확인**

`_build_repos_detail(data)` 호출 시 data에 topics가 이미 포함 (Task 7에서 추가). 변경 불필요.

- [ ] **Step 4: 수동 테스트**

```bash
cd shared/life-coach/scripts
python3 daily_coach.py --json --date 2026-03-16 | python3 daily_report.py --output /tmp/test_topics.html
open /tmp/test_topics.html
```

Expected: 토픽이 있는 세션은 토픽별로 개별 표시. 없는 세션은 기존 방식.

- [ ] **Step 5: 커밋**

```bash
git add shared/life-coach/scripts/daily_report.py
git commit -m "feat: daily_report — topic-based work items + repo detail"
```

### Task 9: timeline_html.py — 토픽별 바

**Files:**
- Modify: `shared/life-coach/scripts/timeline_html.py`

- [ ] **Step 1: prep() 함수에서 topics 우선 사용**

```python
def prep(sessions, topics=None):
    """토픽(우선) 또는 세션에서 타임라인 데이터 생성."""
    if topics:
        return [
            {
                "repo":     (t.get("repo") or "?").split("/")[-1],
                "tag":      t.get("tag") or "기타",
                "start":    (t.get("start_at") or "00:00")[11:16],
                "duration": t.get("duration_estimate_min") or 30,
                "summary":  (t.get("summary") or "")[:100],
            }
            for t in topics
        ]
    return [
        {
            "repo":     (s.get("repo") or "?").split("/")[-1],
            "tag":      s.get("tag") or "기타",
            "start":    (s.get("start_at") or "00:00")[11:16],
            "duration": s.get("duration_min") or 30,
            "summary":  (s.get("summary") or "")[:100],
        }
        for s in dedup(sessions)
    ]
```

- [ ] **Step 2: build() 함수에서 topics 전달 (daily 모드만)**

daily 모드만 변경. weekly 모드는 이번 범위 밖이므로 기존 세션 기반 유지.

```python
    else:
        # daily 모드 — topics 우선
        return title, [{
            "date":       date_str,
            "label":      f'{dt.month}/{dt.day}({WEEKDAY[dt.weekday()]})',
            "work_hours": data.get("work_hours", 0),
            "sessions":   prep(data.get("sessions", []), topics=data.get("topics")),
        }]
```

weekly 모드의 `prep(d.get("activities", []))` 호출은 변경 없음 (topics 파라미터 기본값 None → 세션 기반 동작).

- [ ] **Step 3: 커밋**

```bash
git add shared/life-coach/scripts/timeline_html.py
git commit -m "feat: timeline — topic-based bars with session fallback"
```

---

## Chunk 4: SKILL.md 업데이트

### Task 10: life-coach SKILL.md — Step 3a 토픽 분해 지침

**Files:**
- Modify: `shared/life-coach/SKILL.md`

- [ ] **Step 1: Step 3a에 토픽 분해 절차 추가**

기존 "세션 요약을 DB에 업데이트" 섹션을 확장. 기존 `update-summary` CLI는 유지하면서 `update-topics` 추가:

```markdown
**3a-1. 토픽 분해 (NEW)**

각 세션의 session_content를 보고 **작업 단위별로 분해**한다.

토픽 분리 기준:
- 다른 레포로 전환 → 별도 토픽
- 다른 브랜치로 전환 → 별도 토픽
- 명확히 다른 목적의 작업 → 별도 토픽
- 같은 목적의 연속 작업 → 하나로 합침

한 작업만 한 세션은 토픽 1개. 무리하게 쪼개지 마라.

\`\`\`bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py update-topics \
    --session-id <SID> --date <DATE> \
    --topics '[{"tag":"설계","summary":"spec 작성 — 3계층 분리","repo":"daye-agent-toolkit"},{"tag":"코딩","summary":"DB CRUD 구현","repo":"daye-agent-toolkit"}]'
\`\`\`

**3a-2. 세션 요약 + 상태 업데이트 (기존)**

update-topics를 실행한 세션은 update-summary도 함께 실행하여 상태를 업데이트한다.
```

- [ ] **Step 2: 커밋**

```bash
git add shared/life-coach/SKILL.md
git commit -m "docs: SKILL.md — add topic decomposition to Step 3a"
```

### Task 11: 통합 테스트 — 전체 파이프라인

- [ ] **Step 1: DB 테스트 재실행**

```bash
cd shared/life-dashboard-mcp
python3 tests/test_session_topics.py
```

Expected: 모든 PASS.

- [ ] **Step 2: daily_report 수동 테스트**

```bash
cd shared/life-coach/scripts
python3 daily_coach.py --json | python3 daily_report.py --output /tmp/test_final.html
open /tmp/test_final.html
```

Expected: 토픽 있는 세션은 개별 작업 단위로 표시.

- [ ] **Step 3: update-topics CLI 테스트**

실제 세션이 있는 날짜로:
```bash
cd shared/life-dashboard-mcp
python3 activity_writer.py update-topics --session-id <실제SID> --date <실제DATE> \
  --topics '[{"tag":"코딩","summary":"테스트용 토픽","repo":"test"}]'
```

- [ ] **Step 4: 최종 커밋 (필요 시)**
