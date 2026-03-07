# Life Coach P1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** CC 세션 데이터를 SQLite에 통합하고, work-digest를 보강하고, 일일 코칭 리포트를 텔레그램으로 전송하는 파이프라인 구축.

**Architecture:** life-dashboard-mcp(Python MCP 서버)가 CC work-log 데이터를 SQLite에 수집·정규화. life-coach 스킬의 daily_coach.py가 MCP 도구로 데이터를 조회하여 LLM 코칭 리포트 생성 + 텔레그램 전송. work-digest의 session_logger.py에 종료 시간과 태그 품질 개선 반영.

**Tech Stack:** Python 3.12, sqlite3 (stdlib), mcp Python SDK, claude CLI (haiku)

**Design:** `docs/plans/2026-03-07-life-coach-design.md`

---

## Task 1: work-digest 보강 — 세션 종료 시간 추가

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py:205-313` (parse_transcript)
- Modify: `cc/work-digest/scripts/session_logger.py:331-385` (build_session_section)
- Modify: `cc/work-digest/scripts/parse_work_log.py:28-34` (RE_SESSION_HEADER)
- Modify: `cc/work-digest/scripts/parse_work_log.py:89-217` (parse_session_block)

**Step 1: session_logger.py — parse_transcript에서 end_time 반환**

`parse_transcript()`의 반환 dict에 `end_time` 필드 추가. transcript의 마지막 유효 timestamp를 KST로 변환하여 `HH:MM` 문자열로 저장.

```python
# parse_transcript 함수 끝, return 직전 (약 300행 근처)
# timestamps 리스트의 마지막 항목에서 end_time 추출
end_time_str = None
if timestamps:
    last_ts = timestamps[-1]
    # UTC → KST 변환
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    end_kst = last_ts.astimezone(KST)
    end_time_str = end_kst.strftime("%H:%M")

return {
    "files": sorted(files_modified),
    "commands": commands_run[:10],
    "errors": errors[:5],
    "topic": first_user_msg,
    "duration_min": duration_min,
    "end_time": end_time_str,  # 추가
    "tokens": { ... },
}
```

**Step 2: session_logger.py — build_session_section 헤더에 종료 시간 포함**

`## 세션 00:03 (sid, repo)` → `## 세션 00:03~00:40 (sid, repo)` 형식으로 변경.

```python
# build_session_section 함수 내 (약 336행)
time_str = now.strftime("%H:%M")
end_time = data.get("end_time")
if end_time and end_time != time_str:
    time_range = f"{time_str}~{end_time}"
else:
    time_range = time_str

lines.append(f"## 세션 {time_range} ({sid_short}, {repo})")
```

**Step 3: parse_work_log.py — 헤더 regex 확장**

기존: `## 세션 13:46 (8ed2bc46, repo)`
신규: `## 세션 13:46~14:20 (8ed2bc46, repo)` — `~HH:MM` 옵셔널 매치.

```python
RE_SESSION_HEADER = re.compile(
    r"^##\s+세션\s+(\d{1,2}:\d{2})(?:~(\d{1,2}:\d{2}))?\s+\("
    r"(?:[\w-]+,\s*)?"
    r"([0-9a-f]{8}),\s*"
    r"([^\)]+)"
    r"\)\s*$"
)
```

`parse_session_block`에서 group(2)로 end_time 추출:

```python
time_str = header_match.group(1)
end_time = header_match.group(2)  # None if no ~end
session_id = header_match.group(3)
repo = header_match.group(4).strip()
```

반환 dict에 `"end_time": end_time` 추가.

**Step 4: 검증**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit
# 기존 work-log 파싱 (end_time 없는 레거시 형식이 깨지지 않는지)
python3 cc/work-digest/scripts/parse_work_log.py --date 2026-03-07 | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'sessions: {len(d[\"sessions\"])}'); [print(f'  {s[\"time\"]} end={s.get(\"end_time\",\"N/A\")} {s[\"repo\"]}') for s in d['sessions']]"
```

Expected: 기존 세션들은 `end_time=None`, 새 세션부터 값이 채워짐.

**Step 5: 커밋**

```bash
git add cc/work-digest/scripts/session_logger.py cc/work-digest/scripts/parse_work_log.py
git commit -m "feat(work-digest): 세션 종료 시간(end_time) 기록 추가"
```

---

## Task 2: work-digest 보강 — 요약 태그 품질 개선

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py:146-177` (summarize_session)
- Modify: `cc/work-digest/scripts/_common.py:19` (WORK_TAGS)

**Step 1: 태그 세분화**

`_common.py`의 `WORK_TAGS`에 세분화 태그 추가. "기타"로 빠지는 케이스를 줄인다.

```python
# _common.py
WORK_TAGS = [
    "코딩", "디버깅", "리서치", "리뷰", "ops",
    "설정", "문서", "설계", "리팩토링", "기타",
]
```

추가: `설계` (brainstorming/plan 작업), `리팩토링` (기존 코드 구조 변경)

**Step 2: LLM 프롬프트 개선**

`summarize_session()`의 프롬프트를 수정하여 "기타" 사용을 줄인다.

```python
prompt = (
    f"레포: {repo}\n\n"
    f"다음은 Claude Code 세션의 대화 내용이다.\n\n"
    f"{conversation}\n\n"
    "1줄째: 작업 유형 태그 하나를 골라라. "
    f"선택지: {tags_str}\n"
    "태그 선택 기준:\n"
    "- 코딩: 새 기능 구현, 파일 생성\n"
    "- 디버깅: 버그 수정, 에러 해결\n"
    "- 리서치: 조사, 탐색, 문서 읽기\n"
    "- 리뷰: 코드 리뷰, PR 리뷰\n"
    "- ops: 배포, 인프라, 서버 운영\n"
    "- 설정: 환경 설정, 설치, 구성 변경\n"
    "- 문서: README, 문서 작성\n"
    "- 설계: 브레인스토밍, plan 작성, 아키텍처 설계\n"
    "- 리팩토링: 기존 코드 구조 변경, 정리, 통합\n"
    "- 기타: 위 어디에도 해당하지 않을 때만 사용\n\n"
    "2줄째부터: 이 세션에서 한 작업을 한국어 2-3줄로 요약해라. "
    "구체적으로 뭘 만들었는지, 뭘 고쳤는지, 뭘 조사했는지 중심으로. "
    "파일 경로나 명령어는 생략하고 작업의 의미만 쓰라.\n\n"
    "형식:\n[태그]\n요약 내용"
)
```

**Step 3: daily_digest.py TAG_ICONS 업데이트**

```python
# daily_digest.py 와 weekly_digest.py의 TAG_ICONS에 추가
TAG_ICONS = {
    ...
    "설계": "\U0001f4d0",      # 📐
    "리팩토링": "\u267b\ufe0f", # ♻️
}
```

**Step 4: 검증**

```bash
# 실제 세션 transcript로 테스트 (가장 최근 세션)
LATEST=$(ls -t ~/.claude/projects/*/sessions/*/transcript.jsonl 2>/dev/null | head -1)
python3 -c "
import sys; sys.path.insert(0, 'cc/work-digest/scripts')
from session_logger import extract_conversation, summarize_session
conv = extract_conversation('$LATEST')
result = summarize_session(conv, 'test-repo')
print(result)
"
```

Expected: 태그가 구체적으로 나옴 (설계, 리팩토링 등). "기타" 비율 감소.

**Step 5: 커밋**

```bash
git add cc/work-digest/scripts/_common.py cc/work-digest/scripts/session_logger.py cc/work-digest/scripts/daily_digest.py cc/work-digest/scripts/weekly_digest.py
git commit -m "feat(work-digest): 태그 세분화(설계/리팩토링) + 프롬프트 개선"
```

---

## Task 3: life-dashboard-mcp — SQLite 스키마 + DB 모듈

**Files:**
- Create: `shared/life-dashboard-mcp/db.py`
- Create: `shared/life-dashboard-mcp/schema.sql`

**Step 1: schema.sql 작성**

```sql
-- shared/life-dashboard-mcp/schema.sql
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,          -- 'cc', 'openclaw', 'calendar'
    session_id TEXT,               -- CC session_id or null
    repo TEXT,
    tag TEXT,
    summary TEXT,
    start_at TEXT NOT NULL,        -- ISO 8601 KST
    end_at TEXT,                   -- ISO 8601 KST
    duration_min INTEGER,
    file_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    has_tests INTEGER DEFAULT 0,   -- boolean
    has_commits INTEGER DEFAULT 0, -- boolean
    token_total INTEGER DEFAULT 0,
    raw_json TEXT,                 -- 원본 JSON (디버깅/마이그레이션용)
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(start_at);
CREATE INDEX IF NOT EXISTS idx_activities_source ON activities(source);
CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_session ON activities(source, session_id);

CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,         -- YYYY-MM-DD
    work_hours REAL,
    session_count INTEGER,
    tag_breakdown TEXT,            -- JSON: {"코딩": 5, "디버깅": 2}
    repos TEXT,                    -- JSON: {"repo1": 3, "repo2": 1}
    first_session TEXT,            -- HH:MM
    last_session_end TEXT,         -- HH:MM
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS coach_state (
    key TEXT PRIMARY KEY,
    value TEXT,                    -- JSON
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 초기 coach_state
INSERT OR IGNORE INTO coach_state (key, value) VALUES
    ('escalation_level', '0'),
    ('consecutive_overwork_days', '0'),
    ('consecutive_no_exercise_days', '0');
```

**Step 2: db.py — DB 접근 모듈**

```python
#!/usr/bin/env python3
"""life-dashboard-mcp DB module — SQLite 접근 레이어."""

import json
import sqlite3
from pathlib import Path

DB_DIR = Path.home() / "life-dashboard"
DB_PATH = DB_DIR / "data.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_conn() -> sqlite3.Connection:
    """DB 연결 반환. 최초 호출 시 스키마 초기화."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # 스키마 적용 (IF NOT EXISTS이므로 멱등)
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def upsert_activity(conn: sqlite3.Connection, data: dict):
    """활동 레코드 upsert (session_id 기준 중복 방지)."""
    conn.execute("""
        INSERT INTO activities (source, session_id, repo, tag, summary,
            start_at, end_at, duration_min, file_count, error_count,
            has_tests, has_commits, token_total, raw_json)
        VALUES (:source, :session_id, :repo, :tag, :summary,
            :start_at, :end_at, :duration_min, :file_count, :error_count,
            :has_tests, :has_commits, :token_total, :raw_json)
        ON CONFLICT(source, session_id) DO UPDATE SET
            tag=excluded.tag, summary=excluded.summary,
            end_at=excluded.end_at, duration_min=excluded.duration_min,
            file_count=excluded.file_count, token_total=excluded.token_total,
            raw_json=excluded.raw_json
    """, data)


def update_daily_stats(conn: sqlite3.Connection, date_str: str):
    """특정일의 daily_stats를 activities에서 재계산."""
    rows = conn.execute("""
        SELECT tag, repo, duration_min, start_at, end_at
        FROM activities
        WHERE date(start_at) = ? AND source = 'cc'
    """, (date_str,)).fetchall()

    if not rows:
        conn.execute("DELETE FROM daily_stats WHERE date = ?", (date_str,))
        return

    tags: dict[str, int] = {}
    repos: dict[str, int] = {}
    total_min = 0
    first_session = "99:99"
    last_end = "00:00"

    for r in rows:
        tag = r["tag"] or "기타"
        tags[tag] = tags.get(tag, 0) + 1
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


def get_coach_state(conn: sqlite3.Connection) -> dict:
    """코칭 상태 전체 반환."""
    rows = conn.execute("SELECT key, value FROM coach_state").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_coach_state(conn: sqlite3.Connection, key: str, value: str):
    """코칭 상태 업데이트."""
    conn.execute("""
        INSERT INTO coach_state (key, value, updated_at)
        VALUES (?, ?, datetime('now','localtime'))
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
    """, (key, value))
```

**Step 3: 검증**

```bash
python3 -c "
import sys; sys.path.insert(0, 'shared/life-dashboard-mcp')
from db import get_conn, get_coach_state
conn = get_conn()
print('Tables:', [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])
print('Coach state:', get_coach_state(conn))
conn.close()
"
```

Expected: `Tables: ['activities', 'daily_stats', 'coach_state']`, coach_state에 초기값 3개.

**Step 4: 커밋**

```bash
git add shared/life-dashboard-mcp/schema.sql shared/life-dashboard-mcp/db.py
git commit -m "feat(life-dashboard): SQLite 스키마 + DB 모듈"
```

---

## Task 4: life-dashboard-mcp — CC work-log 동기화

**Files:**
- Create: `shared/life-dashboard-mcp/sync_cc.py`

work-digest의 work-log/*.md를 파싱하여 SQLite activities 테이블에 적재.
`parse_work_log.py`를 subprocess로 호출하지 않고, 로직을 직접 import하여 사용.

**Step 1: sync_cc.py 작성**

```python
#!/usr/bin/env python3
"""CC work-log → SQLite 동기화.

work-digest/work-log/*.md를 파싱하여 activities 테이블에 upsert.

Usage:
    python3 sync_cc.py                    # 오늘 동기화
    python3 sync_cc.py --date 2026-03-07  # 특정일
    python3 sync_cc.py --days 7           # 최근 7일
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# work-digest 스크립트 import를 위한 경로 추가
_WORK_DIGEST_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "cc" / "work-digest" / "scripts"
sys.path.insert(0, str(_WORK_DIGEST_SCRIPTS))

from parse_work_log import parse_work_log  # type: ignore

# 자체 DB 모듈
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn, upsert_activity, update_daily_stats

KST = timezone(timedelta(hours=9))


def sync_date(conn, date_str: str) -> int:
    """특정일의 work-log를 파싱하여 DB에 upsert. 삽입/갱신 건수 반환."""
    data = parse_work_log(date_str)
    sessions = data.get("sessions", [])
    count = 0

    for s in sessions:
        session_id = s.get("session_id", "")
        if not session_id:
            continue

        # start_at 생성: date + time
        time_str = s.get("time", "00:00")
        start_at = f"{date_str}T{time_str}:00"

        # end_at: end_time이 있으면 사용, 없으면 start + duration 추정
        end_time = s.get("end_time")
        if end_time:
            end_at = f"{date_str}T{end_time}:00"
        elif s.get("duration_min"):
            start_dt = datetime.strptime(start_at, "%Y-%m-%dT%H:%M:%S")
            end_dt = start_dt + timedelta(minutes=s["duration_min"])
            end_at = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            end_at = None

        # 테스트/커밋 여부 확인
        has_tests = 0
        has_commits = 0
        test_keywords = {"pytest", "jest", "test", "vitest"}
        for cmd in s.get("commands", []):
            cmd_lower = cmd.lower()
            if any(kw in cmd_lower for kw in test_keywords):
                has_tests = 1
            if "git commit" in cmd_lower:
                has_commits = 1

        # 토큰 합계
        tokens = s.get("tokens") or {}
        token_total = sum(tokens.get(k, 0) for k in
                         ("Input", "Output", "Cache read", "Cache create"))

        activity = {
            "source": "cc",
            "session_id": session_id,
            "repo": s.get("repo", "unknown"),
            "tag": s.get("tag", ""),
            "summary": s.get("summary", "") or s.get("topic", ""),
            "start_at": start_at,
            "end_at": end_at,
            "duration_min": s.get("duration_min"),
            "file_count": s.get("file_count", 0),
            "error_count": len(s.get("errors", [])),
            "has_tests": has_tests,
            "has_commits": has_commits,
            "token_total": token_total,
            "raw_json": json.dumps(s, ensure_ascii=False),
        }
        upsert_activity(conn, activity)
        count += 1

    if count > 0:
        update_daily_stats(conn, date_str)

    return count


def main():
    parser = argparse.ArgumentParser(description="Sync CC work-log to SQLite")
    parser.add_argument("--date", help="Sync specific date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=1, help="Sync last N days (default: 1)")
    args = parser.parse_args()

    conn = get_conn()

    if args.date:
        dates = [args.date]
    else:
        today = datetime.now(KST)
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(args.days)]

    total = 0
    for date_str in dates:
        count = sync_date(conn, date_str)
        total += count
        if count > 0:
            print(f"[sync_cc] {date_str}: {count} sessions synced", file=sys.stderr)

    conn.commit()
    conn.close()
    print(f"[sync_cc] Total: {total} sessions synced across {len(dates)} days", file=sys.stderr)


if __name__ == "__main__":
    main()
```

**Step 2: 검증 — 오늘 데이터 동기화 테스트**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit
python3 shared/life-dashboard-mcp/sync_cc.py --date 2026-03-07

# DB 확인
python3 -c "
import sys; sys.path.insert(0, 'shared/life-dashboard-mcp')
from db import get_conn
conn = get_conn()
rows = conn.execute('SELECT start_at, end_at, repo, tag, duration_min FROM activities WHERE date(start_at) = \"2026-03-07\" ORDER BY start_at').fetchall()
for r in rows:
    print(f'{r[\"start_at\"]} ~ {r[\"end_at\"]} | {r[\"repo\"]} | {r[\"tag\"]} | {r[\"duration_min\"]}min')
stats = conn.execute('SELECT * FROM daily_stats WHERE date = \"2026-03-07\"').fetchone()
if stats:
    print(f'Daily: {stats[\"work_hours\"]}h, {stats[\"session_count\"]} sessions')
conn.close()
"
```

Expected: 14개 세션이 activities에 삽입, daily_stats에 집계 1행.

**Step 3: 최근 7일 동기화 테스트**

```bash
python3 shared/life-dashboard-mcp/sync_cc.py --days 7
```

**Step 4: 커밋**

```bash
git add shared/life-dashboard-mcp/sync_cc.py
git commit -m "feat(life-dashboard): CC work-log → SQLite 동기화 스크립트"
```

---

## Task 5: life-dashboard-mcp — MCP 서버

**Files:**
- Create: `shared/life-dashboard-mcp/server.py`
- Create: `shared/life-dashboard-mcp/requirements.txt`

MCP 서버. 코칭 스크립트와 `/coach` 온디맨드가 이 서버의 도구를 호출.

**Step 1: requirements.txt**

```
mcp>=1.0.0
```

**Step 2: server.py — 최소 MCP 서버 (3개 도구)**

```python
#!/usr/bin/env python3
"""life-dashboard MCP server — 통합 활동 데이터 조회."""

import json
from datetime import datetime, timezone, timedelta

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from db import get_conn, get_coach_state, set_coach_state

KST = timezone(timedelta(hours=9))
app = Server("life-dashboard")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_today_summary",
            description="오늘의 활동 요약 — 작업시간, 세션수, 태그, 레포별 분포",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_date_summary",
            description="특정일의 활동 요약",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD"}
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="get_weekly_summary",
            description="최근 7일 활동 요약 — 일별 작업시간, 패턴 분석",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_date": {"type": "string", "description": "끝 날짜 YYYY-MM-DD (기본: 오늘)"}
                },
            },
        ),
    ]


def _build_date_summary(conn, date_str: str) -> dict:
    """특정일 활동 요약 생성."""
    stats = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ?", (date_str,)
    ).fetchone()

    if not stats:
        return {"date": date_str, "has_data": False}

    activities = conn.execute("""
        SELECT repo, tag, summary, start_at, end_at, duration_min
        FROM activities WHERE date(start_at) = ? AND source = 'cc'
        ORDER BY start_at
    """, (date_str,)).fetchall()

    return {
        "date": date_str,
        "has_data": True,
        "work_hours": stats["work_hours"],
        "session_count": stats["session_count"],
        "first_session": stats["first_session"],
        "last_session_end": stats["last_session_end"],
        "tag_breakdown": json.loads(stats["tag_breakdown"]) if stats["tag_breakdown"] else {},
        "repos": json.loads(stats["repos"]) if stats["repos"] else {},
        "sessions": [
            {
                "repo": a["repo"],
                "tag": a["tag"],
                "summary": a["summary"][:150] if a["summary"] else "",
                "start": a["start_at"][11:16] if a["start_at"] else "",
                "end": a["end_at"][11:16] if a["end_at"] else "",
                "duration_min": a["duration_min"],
            }
            for a in activities
        ],
        "coach_state": get_coach_state(conn),
    }


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    conn = get_conn()
    try:
        if name == "get_today_summary":
            today = datetime.now(KST).strftime("%Y-%m-%d")
            result = _build_date_summary(conn, today)

        elif name == "get_date_summary":
            result = _build_date_summary(conn, arguments["date"])

        elif name == "get_weekly_summary":
            end = arguments.get("end_date") or datetime.now(KST).strftime("%Y-%m-%d")
            end_dt = datetime.strptime(end, "%Y-%m-%d")
            days = []
            for i in range(6, -1, -1):
                d = (end_dt - timedelta(days=i)).strftime("%Y-%m-%d")
                days.append(_build_date_summary(conn, d))
            total_hours = sum(d.get("work_hours", 0) for d in days if d["has_data"])
            active_days = sum(1 for d in days if d["has_data"])
            result = {
                "period": f"{days[0]['date']} ~ {days[-1]['date']}",
                "total_work_hours": round(total_hours, 1),
                "active_days": active_days,
                "daily": days,
                "coach_state": get_coach_state(conn),
            }
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    finally:
        conn.close()


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**Step 3: 검증 — 서버 시작 테스트**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/shared/life-dashboard-mcp
pip install mcp 2>/dev/null  # 이미 설치되어 있을 수 있음
python3 -c "from server import app; print('Server module loads OK')"
```

**Step 4: .mcp.json 등록 테스트 (수동)**

```bash
# CC에서 MCP 서버로 사용하려면 .mcp.json에 추가
# 이 단계에서는 수동 검증만. 등록은 Task 8에서.
echo '서버 모듈 로드 확인 완료. MCP 등록은 Task 8에서.'
```

**Step 5: 커밋**

```bash
git add shared/life-dashboard-mcp/server.py shared/life-dashboard-mcp/requirements.txt
git commit -m "feat(life-dashboard): MCP 서버 — get_today/date/weekly_summary"
```

---

## Task 6: life-coach 스킬 — SKILL.md + .claude-skill

**Files:**
- Create: `shared/life-coach/SKILL.md`
- Create: `shared/life-coach/.claude-skill`

**Step 1: .claude-skill**

```json
{
  "name": "life-coach",
  "version": "0.1.0",
  "description": "일일/주간 라이프 코칭 — 작업 패턴 분석, 자동화 제안, 건강 넛지. 코칭, 리뷰, 하루 정리, 방향성, 과작업, 운동이 필요할 때 사용.",
  "entrypoint": "SKILL.md"
}
```

**Step 2: SKILL.md**

```markdown
---
name: life-coach
description: 일일/주간 라이프 코칭 — 작업 패턴 분석, 자동화 제안, 건강 넛지
---

# Life Coach Skill

**Version:** 0.1.0 | **Status:** P1

CC/OpenClaw/Calendar 활동 데이터를 기반으로 일일/주간 코칭 리포트를 생성한다.
데이터는 life-dashboard-mcp에서 조회.

## 온디맨드 사용 (/coach)

1. life-dashboard MCP의 `get_today_summary` 도구 호출
2. 결과를 바탕으로 아래 코칭 프레임 적용
3. 세션 내에서 코칭 대화

## 코칭 프레임

### 톤 에스컬레이션

coach_state의 escalation_level에 따라 톤 변경:
- Level 0 (B+C): 데이터 보여주고 질문. 부드러운 넛지.
- Level 1 (B): 3일 연속 10h+ → 직접적 제안.
- Level 2 (A): 7일 연속 or 미개선 → 직설적 지시.

### 일일 코칭 구성

1. **오늘의 정리** — 작업 시간, 레포별 요약, 태그 비율
2. **코칭** — 과작업, 수면 패턴, 집중도 기반 제안
3. **자동화 제안** — 반복 명령/작업 감지
4. **내일 캘린더** — 예정된 일정 (P2에서 추가)
5. **건강 넛지** — 운동, 휴식

### 주간 코칭 구성 (P2에서 추가)

주간 트렌드 분석 + 방향성 코칭.

## 자동화

| Cron | Script | 설명 |
|------|--------|------|
| `0 21 * * *` | `scripts/daily_coach.py` | 매일 21시 코칭 리포트 |
| `0 21 * * 0` | (P2) `scripts/weekly_coach.py` | 주간 코칭 |

## Scripts

| Script | Purpose |
|--------|---------|
| `daily_coach.py` | 일일 코칭 리포트 → 텔레그램 |

## References

| File | 내용 |
|------|------|
| `references/coaching-prompts.md` | LLM 코칭 프롬프트 템플릿 |
```

**Step 3: 커밋**

```bash
git add shared/life-coach/SKILL.md shared/life-coach/.claude-skill
git commit -m "feat(life-coach): 스킬 정의 — SKILL.md + .claude-skill"
```

---

## Task 7: life-coach — 코칭 프롬프트 + daily_coach.py

**Files:**
- Create: `shared/life-coach/references/coaching-prompts.md`
- Create: `shared/life-coach/scripts/daily_coach.py`

**Step 1: coaching-prompts.md**

```markdown
# 코칭 프롬프트 템플릿

## 일일 코칭

아래는 오늘 하루 작업 데이터이다.

{data_section}

다음 3개 섹션을 생성해라. 각 섹션 2-4줄. 총 500자 이내.

### 📝 오늘의 정리
- 하루 전체를 한 문단으로 요약. 핵심 성과 중심.

### 🔍 코칭
- 데이터에서 보이는 패턴 1-2개를 짚고, 구체적 제안.
- 과작업(8h+), 새벽 작업, 컨텍스트 스위칭, 운동 부재 등.
- 톤 레벨: {tone_level}
  - Level 0: 질문형 + 부드러운 넛지. "내일은 어떻게 할까?"
  - Level 1: 직접적 제안. "내일은 6시간 이하로 제한하는 게 좋겠다."
  - Level 2: 지시형. "내일 오후 7시 이후 작업 금지."

### 🤖 자동화 제안
- 반복되는 작업/명령이 있으면 자동화 방법 제안.
- 없으면 이 섹션 생략.

한국어로. 간결하게. 번역체 금지.
```

**Step 2: daily_coach.py**

```python
#!/usr/bin/env python3
"""Daily Coach — life-dashboard 데이터 기반 일일 코칭 리포트.

Usage:
    python3 daily_coach.py                 # LLM 코칭 + 텔레그램
    python3 daily_coach.py --dry-run       # stdout 출력만
    python3 daily_coach.py --no-llm        # 템플릿만
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# DB 모듈
_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import get_conn, get_coach_state, set_coach_state, update_daily_stats

# work-digest 공용 유틸
_WD_SCRIPTS = Path(__file__).resolve().parent.parent.parent.parent / "cc" / "work-digest" / "scripts"
sys.path.insert(0, str(_WD_SCRIPTS))
from _common import send_telegram, format_tokens, WEEKDAYS_KO

KST = timezone(timedelta(hours=9))
TELEGRAM_MAX_CHARS = 4096
COACHING_TIMEOUT_SEC = 45
OVERWORK_THRESHOLD_HOURS = 8
PROMPTS_PATH = Path(__file__).resolve().parent.parent / "references" / "coaching-prompts.md"


def get_today_data(conn, date_str: str) -> dict:
    """DB에서 오늘 활동 데이터 조회."""
    stats = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ?", (date_str,)
    ).fetchone()

    if not stats:
        return {"date": date_str, "has_data": False}

    activities = conn.execute("""
        SELECT repo, tag, summary, start_at, end_at, duration_min, token_total
        FROM activities WHERE date(start_at) = ? AND source = 'cc'
        ORDER BY start_at
    """, (date_str,)).fetchall()

    return {
        "date": date_str,
        "has_data": True,
        "work_hours": stats["work_hours"],
        "session_count": stats["session_count"],
        "first_session": stats["first_session"],
        "last_session_end": stats["last_session_end"],
        "tag_breakdown": json.loads(stats["tag_breakdown"]) if stats["tag_breakdown"] else {},
        "repos": json.loads(stats["repos"]) if stats["repos"] else {},
        "sessions": [dict(a) for a in activities],
    }


TAG_ICONS = {
    "코딩": "💻", "디버깅": "🐛", "리서치": "🔍", "리뷰": "📝",
    "ops": "⚙️", "설정": "🔧", "문서": "📖", "설계": "📐",
    "리팩토링": "♻️", "기타": "💡",
}


def build_data_section(data: dict) -> str:
    """코칭 프롬프트에 넣을 데이터 섹션 구성."""
    lines = []
    date_str = data["date"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = WEEKDAYS_KO[dt.weekday()]

    lines.append(f"날짜: {date_str} ({weekday})")
    lines.append(f"총 작업: {data['work_hours']}시간, {data['session_count']}세션")
    lines.append(f"시간대: {data['first_session']} ~ {data['last_session_end']}")

    # 태그
    tags = data.get("tag_breakdown", {})
    if tags:
        tag_parts = [f"{TAG_ICONS.get(t, '💡')}{t} {c}건" for t, c in
                     sorted(tags.items(), key=lambda x: x[1], reverse=True)]
        lines.append(f"작업 유형: {', '.join(tag_parts)}")

    # 레포
    repos = data.get("repos", {})
    if repos:
        repo_parts = [f"{r}({c}세션)" for r, c in
                      sorted(repos.items(), key=lambda x: x[1], reverse=True)]
        lines.append(f"레포: {', '.join(repo_parts)}")

    # 세션별 요약 (최대 8개)
    sessions = data.get("sessions", [])
    if sessions:
        lines.append("")
        lines.append("세션별:")
        for s in sessions[:8]:
            start = s.get("start_at", "")[11:16] if s.get("start_at") else "?"
            tag = s.get("tag", "")
            summary = (s.get("summary", "") or "")[:80]
            repo = s.get("repo", "")
            dur = s.get("duration_min", 0)
            lines.append(f"- {start} [{tag}] {repo}: {summary} ({dur}분)")

    return "\n".join(lines)


def build_template_report(data: dict, coach_state: dict) -> str:
    """LLM 없이 템플릿 기반 리포트."""
    date_str = data["date"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = WEEKDAYS_KO[dt.weekday()]

    sections = []
    sections.append(f"🏋️ {dt.month}/{dt.day}({weekday}) 데일리 코칭")

    if not data["has_data"]:
        sections.append("오늘 기록된 세션 없음.")
        return "\n\n".join(sections)

    # 시간 요약
    sections.append(
        f"⏱ {data['session_count']}세션 · {data['work_hours']}시간 "
        f"· {data['first_session']}~{data['last_session_end']}"
    )

    # 태그
    tags = data.get("tag_breakdown", {})
    if tags:
        parts = [f"{TAG_ICONS.get(t, '💡')}{t} {c}건" for t, c in
                 sorted(tags.items(), key=lambda x: x[1], reverse=True)]
        sections.append("🏷 " + " · ".join(parts))

    # 레포
    repos = data.get("repos", {})
    if repos:
        repo_lines = ["📂 레포별:"]
        for r, c in sorted(repos.items(), key=lambda x: x[1], reverse=True)[:5]:
            repo_lines.append(f"  ▸ {r} ({c}세션)")
        sections.append("\n".join(repo_lines))

    # 건강 넛지
    nudges = []
    if data["work_hours"] >= OVERWORK_THRESHOLD_HOURS:
        nudges.append(f"⚠️ {data['work_hours']}시간 작업 — 과작업 주의")
    if data["first_session"] and data["first_session"] < "06:00":
        nudges.append("🌙 새벽 작업 감지 — 수면 패턴 주의")
    overwork_days = int(coach_state.get("consecutive_overwork_days", "0"))
    if overwork_days >= 3:
        nudges.append(f"🔥 {overwork_days}일 연속 과작업 — 번아웃 위험")
    if nudges:
        sections.append("\n".join(nudges))

    level = int(coach_state.get("escalation_level", "0"))
    sections.append(f"⚡ 코치 레벨: {level}")

    return "\n\n".join(sections)


def generate_llm_coaching(data_section: str, tone_level: int) -> str | None:
    """LLM으로 코칭 생성."""
    tone_desc = {0: "Level 0", 1: "Level 1", 2: "Level 2"}.get(tone_level, "Level 0")

    try:
        template = PROMPTS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        template = "데이터를 보고 코칭해라."

    prompt = template.replace("{data_section}", data_section).replace("{tone_level}", tone_desc)

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--no-session-persistence"],
            input=prompt, capture_output=True, text=True, timeout=COACHING_TIMEOUT_SEC,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        print(f"[daily_coach] LLM 실패: {e}", file=sys.stderr)
    return None


def update_overwork_tracking(conn, data: dict):
    """과작업 연속일 추적 + 에스컬레이션 레벨 업데이트."""
    state = get_coach_state(conn)
    overwork_days = int(state.get("consecutive_overwork_days", "0"))
    level = int(state.get("escalation_level", "0"))

    if data["has_data"] and data["work_hours"] >= OVERWORK_THRESHOLD_HOURS:
        overwork_days += 1
    else:
        overwork_days = 0

    # 에스컬레이션
    if overwork_days >= 7:
        level = 2
    elif overwork_days >= 3:
        level = max(level, 1)
    elif overwork_days == 0 and level > 0:
        level = max(0, level - 1)  # 개선 시 하향

    set_coach_state(conn, "consecutive_overwork_days", str(overwork_days))
    set_coach_state(conn, "escalation_level", str(level))
    conn.commit()

    return level


def main():
    parser = argparse.ArgumentParser(description="Daily coaching report")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    conn = get_conn()
    data = get_today_data(conn, args.date)
    coach_state = get_coach_state(conn)
    level = update_overwork_tracking(conn, data)

    if not data["has_data"]:
        message = build_template_report(data, coach_state)
    elif args.no_llm:
        message = build_template_report(data, coach_state)
    else:
        data_section = build_data_section(data)
        llm_result = generate_llm_coaching(data_section, level)
        if llm_result:
            # 헤더 + LLM 코칭 + 레벨 표시
            dt = datetime.strptime(args.date, "%Y-%m-%d")
            weekday = WEEKDAYS_KO[dt.weekday()]
            header = f"🏋️ {dt.month}/{dt.day}({weekday}) 데일리 코칭"
            stats_line = (
                f"⏱ {data['session_count']}세션 · {data['work_hours']}시간 "
                f"· {data['first_session']}~{data['last_session_end']}"
            )
            message = f"{header}\n\n{stats_line}\n\n{llm_result}\n\n⚡ 코치 레벨: {level}"
        else:
            message = build_template_report(data, coach_state)

    # Truncate
    if len(message) > TELEGRAM_MAX_CHARS:
        message = message[:TELEGRAM_MAX_CHARS - 20] + "\n\n... (truncated)"

    conn.close()

    if args.dry_run:
        print(message)
    else:
        ok = send_telegram(message, chat_id_key="CHAT_ID_COACH", silent=True)
        if ok:
            print("[daily_coach] 텔레그램 전송 완료", file=sys.stderr)
        else:
            print("[daily_coach] 텔레그램 전송 실패 (CHAT_ID_COACH 확인)", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 3: 검증 — dry-run**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit

# 먼저 오늘 데이터 sync
python3 shared/life-dashboard-mcp/sync_cc.py --date 2026-03-07

# dry-run (템플릿)
python3 shared/life-coach/scripts/daily_coach.py --dry-run --no-llm --date 2026-03-07

# dry-run (LLM)
python3 shared/life-coach/scripts/daily_coach.py --dry-run --date 2026-03-07
```

Expected: 템플릿은 구조화된 리포트 출력. LLM은 코칭 메시지 포함.

**Step 4: 커밋**

```bash
git add shared/life-coach/references/coaching-prompts.md shared/life-coach/scripts/daily_coach.py
git commit -m "feat(life-coach): 일일 코칭 리포트 — daily_coach.py + 프롬프트"
```

---

## Task 8: 인프라 — telegram.conf + MCP 등록 + cron

**Files:**
- Modify: `cc/work-digest/telegram.conf` (CHAT_ID_COACH 추가)
- Create: `shared/life-coach/cron.json` (OpenClaw cron 등록용)

**Step 1: telegram.conf에 코칭 채널 추가**

```
# 기존 내용 유지 + 추가:
CHAT_ID_COACH=-100XXXXXXXXXX
```

사용자에게 텔레그램에서 코칭 전용 topic/채널을 만들고 chat_id를 확인해달라고 안내. 임시로 `CHAT_ID`(개인 DM)를 사용할 수도 있음.

**Step 2: cron.json (OpenClaw용)**

```json
[
  {
    "schedule": "0 21 * * *",
    "command": "python3 {baseDir}/scripts/daily_coach.py",
    "description": "일일 코칭 리포트 → 텔레그램"
  }
]
```

**Step 3: CC에서 MCP 서버 등록 안내**

`.mcp.json`에 추가하는 방법을 사용자에게 안내 (P1에서는 수동 등록):

```json
{
  "mcpServers": {
    "life-dashboard": {
      "command": "python3",
      "args": ["shared/life-dashboard-mcp/server.py"],
      "cwd": "/Users/dayejeong/git_workplace/daye-agent-toolkit"
    }
  }
}
```

**Step 4: sync cron 등록**

CC work-log → SQLite 동기화를 위한 cron:

```bash
# 매시간 동기화 (또는 daily_coach.py 실행 전에 sync)
# daily_coach.py 내부에서 sync를 호출하는 것도 방법 — 아래 Step 5에서 처리
```

실제로는 daily_coach.py 실행 직전에 sync_cc.py를 호출하는 wrapper를 cron에 등록하는 게 단순하다:

cron.json 수정:
```json
[
  {
    "schedule": "0 21 * * *",
    "command": "python3 {baseDir}/../life-dashboard-mcp/sync_cc.py --days 1 && python3 {baseDir}/scripts/daily_coach.py",
    "description": "CC sync + 일일 코칭 리포트"
  }
]
```

**Step 5: 커밋**

```bash
git add cc/work-digest/telegram.conf shared/life-coach/cron.json
git commit -m "feat(life-coach): cron 등록 + telegram 채널 설정"
```

---

## Task 9: 통합 검증 — end-to-end dry-run

**Step 1: 전체 파이프라인 실행**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit

# 1) 최근 7일 CC 데이터 동기화
python3 shared/life-dashboard-mcp/sync_cc.py --days 7

# 2) DB 상태 확인
python3 -c "
import sys; sys.path.insert(0, 'shared/life-dashboard-mcp')
from db import get_conn
conn = get_conn()
for row in conn.execute('SELECT date, work_hours, session_count FROM daily_stats ORDER BY date').fetchall():
    print(f'{row[\"date\"]}: {row[\"work_hours\"]}h, {row[\"session_count\"]} sessions')
conn.close()
"

# 3) 오늘 코칭 dry-run (LLM)
python3 shared/life-coach/scripts/daily_coach.py --dry-run --date 2026-03-07

# 4) 어제 코칭 dry-run (비교용)
python3 shared/life-coach/scripts/daily_coach.py --dry-run --date 2026-03-06
```

**Step 2: 레거시 호환 확인**

```bash
# work-digest 기존 파이프라인이 깨지지 않는지 확인
python3 cc/work-digest/scripts/parse_work_log.py --date 2026-03-07 | python3 cc/work-digest/scripts/daily_digest.py --dry-run --no-llm
```

Expected: 기존 daily_digest 출력 정상. 새 end_time 필드가 있어도 기존 코드에 영향 없음.

**Step 3: 최종 커밋**

통합 검증 후 수정사항이 있으면 수정 후 커밋.

```bash
git add -A
git commit -m "fix: 통합 검증 후 수정사항 반영"
```

---

## 요약

| Task | 파일 | 내용 |
|------|------|------|
| 1 | session_logger.py, parse_work_log.py | 세션 종료 시간 추가 |
| 2 | _common.py, session_logger.py, daily/weekly_digest.py | 태그 세분화 + 프롬프트 개선 |
| 3 | life-dashboard-mcp/db.py, schema.sql | SQLite 스키마 + DB 모듈 |
| 4 | life-dashboard-mcp/sync_cc.py | CC work-log → SQLite 동기화 |
| 5 | life-dashboard-mcp/server.py | MCP 서버 (3개 도구) |
| 6 | life-coach/SKILL.md, .claude-skill | 스킬 정의 |
| 7 | life-coach/daily_coach.py, coaching-prompts.md | 일일 코칭 리포트 |
| 8 | telegram.conf, cron.json | 인프라 설정 |
| 9 | (전체) | 통합 검증 |
