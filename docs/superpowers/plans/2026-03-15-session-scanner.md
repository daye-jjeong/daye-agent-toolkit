# Session Scanner Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CC 세션이 열려있어도 daily coaching report에 누락 없이 기록되도록, 날짜 분할 + 활성 세션 스캐너를 구현한다.

**Architecture:** session_logger.py의 transcript 파싱을 날짜별로 분할하는 코어 함수(`parse_transcript_by_date`)로 리팩토링하고, 활성 세션을 탐색하는 scanner를 추가한다. daily_coach.py가 실행 시 scanner → sync → report 순서로 호출한다.

**Tech Stack:** Python 3 stdlib only (sqlite3, json, subprocess, fcntl)

**Spec:** `docs/superpowers/specs/2026-03-15-session-scanner-design.md`

---

## Chunk 1: 코어 리팩토링 + 스키마

### Task 1: SQLite 스키마 마이그레이션

**Files:**
- Modify: `shared/life-dashboard-mcp/schema.sql`
- Modify: `shared/life-dashboard-mcp/db.py:31-37` (`_migrate` 함수)
- Modify: `shared/life-dashboard-mcp/db.py:54-68` (`upsert_activity` 함수)

- [ ] **Step 1: schema.sql에 date 컬럼 + 새 unique index 추가**

`schema.sql` 23줄의 기존 unique index를 변경:

```sql
-- 기존:
CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_session ON activities(source, session_id);
-- 변경:
CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_session ON activities(source, session_id, date);
```

activities 테이블에 `date TEXT` 컬럼 추가 (`end_at` 다음, `duration_min` 이전):

```sql
    date TEXT,
```

- [ ] **Step 2: db.py _migrate()에 date 컬럼 마이그레이션 추가**

`db.py:31-37`의 `_migrate` 함수에 추가:

```python
def _migrate(conn: sqlite3.Connection):
    """Additive schema migrations for existing databases."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(activities)").fetchall()}
    if "branch" not in cols:
        conn.execute("ALTER TABLE activities ADD COLUMN branch TEXT")
        conn.commit()
    if "date" not in cols:
        conn.execute("ALTER TABLE activities ADD COLUMN date TEXT")
        conn.execute("UPDATE activities SET date = date(start_at) WHERE date IS NULL")
        conn.commit()
    # Recreate unique index with date column
    indices = {r[1] for r in conn.execute("PRAGMA index_list(activities)").fetchall()}
    if "idx_activities_session" in indices:
        idx_info = conn.execute("PRAGMA index_info(idx_activities_session)").fetchall()
        col_names = {r[2] for r in idx_info}
        if "date" not in col_names:
            conn.execute("DROP INDEX idx_activities_session")
            conn.execute("CREATE UNIQUE INDEX idx_activities_session ON activities(source, session_id, date)")
            conn.commit()
```

- [ ] **Step 3: db.py upsert_activity()의 ON CONFLICT 절 변경**

`db.py:54-68`을 변경:

```python
def upsert_activity(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO activities (source, session_id, repo, branch, tag, summary,
            start_at, end_at, date, duration_min, file_count, error_count,
            has_tests, has_commits, token_total, raw_json)
        VALUES (:source, :session_id, :repo, :branch, :tag, :summary,
            :start_at, :end_at, :date, :duration_min, :file_count, :error_count,
            :has_tests, :has_commits, :token_total, :raw_json)
        ON CONFLICT(source, session_id, date) DO UPDATE SET
            repo=excluded.repo, branch=excluded.branch,
            tag=COALESCE(excluded.tag, tag),
            summary=COALESCE(excluded.summary, summary),
            end_at=excluded.end_at, duration_min=excluded.duration_min,
            file_count=excluded.file_count, token_total=excluded.token_total,
            raw_json=excluded.raw_json
    """, data)
```

`COALESCE`를 tag/summary에 사용: scanner가 NULL로 넣은 뒤 SessionEnd가 값을 채울 때 NULL로 덮어쓰지 않도록.

- [ ] **Step 4: sync_cc.py에 date 필드 추가**

`sync_cc.py:95-116`의 activity dict에 `"date": date_str` 추가:

```python
            activity = {
                "source": "cc",
                "session_id": session_id,
                "repo": s.get("repo", "unknown"),
                "branch": s.get("branch"),
                "tag": s.get("tag", "") or auto_tag(
                    s.get("summary", ""), s.get("topic", ""),
                    " ".join(s.get("commands", [])[:5]),
                ),
                "summary": s.get("summary", "") or (
                    s.get("topic", "") if s.get("topic", "").strip() not in _NON_WORK_PATTERNS else ""
                ),
                "start_at": start_at,
                "end_at": end_at,
                "date": date_str,  # ← 추가
                "duration_min": s.get("duration_min"),
                "file_count": s.get("file_count", 0),
                "error_count": len(s.get("errors", [])),
                "has_tests": has_tests,
                "has_commits": has_commits,
                "token_total": token_total,
                "raw_json": json.dumps(s, ensure_ascii=False),
            }
```

- [ ] **Step 5: 마이그레이션 테스트**

Run: `python3 -c "import sys; sys.path.insert(0, 'shared/life-dashboard-mcp'); from db import get_conn; c = get_conn(); print([r[1] for r in c.execute('PRAGMA table_info(activities)').fetchall()]); print([r[1] for r in c.execute('PRAGMA index_list(activities)').fetchall()]); c.close()"`

Expected: `date` 컬럼 존재, `idx_activities_session` index에 3컬럼.

- [ ] **Step 6: 커밋**

```bash
git add shared/life-dashboard-mcp/schema.sql shared/life-dashboard-mcp/db.py shared/life-dashboard-mcp/sync_cc.py
git commit -m "feat: add date column to activities + composite unique index"
```

---

### Task 2: session_logger.py — parse_transcript_by_date 추출

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py:392-523` (`parse_transcript` 리팩토링)

- [ ] **Step 1: parse_transcript_by_date() 함수 작성**

기존 `parse_transcript()`를 유지하면서, 날짜별로 분할하는 새 함수를 추가.
`session_logger.py`의 `parse_transcript` 바로 아래에 추가:

```python
def parse_transcript_by_date(transcript_path: str, fallback_date: str | None = None) -> dict[str, dict]:
    """Parse transcript and split by KST date.

    Returns: {"2026-03-14": ParsedData, "2026-03-15": ParsedData, ...}
    각 ParsedData는 parse_transcript()와 동일한 구조.
    """
    # 날짜별 accumulator
    by_date: dict[str, dict] = {}
    current_date = fallback_date  # timestamp 없는 첫 엔트리용 fallback

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                # timestamp → KST 날짜 결정
                ts = entry.get("timestamp")
                entry_date = current_date
                entry_ts = None
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        kst_dt = dt.astimezone(KST)
                        entry_date = kst_dt.strftime("%Y-%m-%d")
                        entry_ts = kst_dt
                        current_date = entry_date
                    except (ValueError, TypeError):
                        pass

                if not entry_date:
                    continue

                # 해당 날짜의 accumulator 초기화
                if entry_date not in by_date:
                    by_date[entry_date] = {
                        "files": set(),
                        "commands": [],
                        "errors": [],
                        "topic": "",
                        "timestamps": [],
                        "token_input": 0,
                        "token_output": 0,
                        "token_cache_read": 0,
                        "token_cache_create": 0,
                        "api_calls": 0,
                        "has_commits": False,
                    }

                acc = by_date[entry_date]
                if entry_ts:
                    acc["timestamps"].append(entry_ts)

                entry_type = entry.get("type", "")
                msg = entry.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else ""

                # First user message per date = topic
                if not acc["topic"] and entry_type == "user":
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                raw = strip_system_tags(block.get("text", ""))
                                if raw:
                                    acc["topic"] = raw[:120]
                                    break
                    elif isinstance(content, str):
                        raw = strip_system_tags(content)
                        if raw:
                            acc["topic"] = raw[:120]

                # Token usage
                if entry_type == "assistant" and isinstance(msg, dict):
                    usage = msg.get("usage", {})
                    if usage:
                        acc["api_calls"] += 1
                        acc["token_input"] += usage.get("input_tokens", 0)
                        acc["token_output"] += usage.get("output_tokens", 0)
                        acc["token_cache_read"] += usage.get("cache_read_input_tokens", 0)
                        acc["token_cache_create"] += usage.get("cache_creation_input_tokens", 0)

                # Tool calls
                if entry_type == "assistant" and isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        tool = block.get("name", "")
                        inp = block.get("input", {})
                        if tool in ("Edit", "Write"):
                            fp = inp.get("file_path", "")
                            if fp:
                                acc["files"].add(fp)
                        if tool == "Bash":
                            cmd = inp.get("command", "")
                            if cmd:
                                if not acc["has_commits"] and "git commit" in cmd.lower():
                                    acc["has_commits"] = True
                                acc["commands"].append(cmd[:80])

                # Tool result errors
                if entry_type == "tool_result":
                    data_field = entry.get("data", {})
                    text = ""
                    if isinstance(data_field, dict):
                        text = str(data_field.get("output", ""))[:120]
                    if text and ("error" in text.lower() or "Error" in text):
                        acc["errors"].append(text[:120])
    except (FileNotFoundError, PermissionError):
        pass

    # accumulator → ParsedData 형식으로 변환
    result = {}
    for date_str, acc in by_date.items():
        timestamps = acc["timestamps"]
        duration_min = None
        if len(timestamps) >= 2:
            active_sec = 0
            sorted_ts = sorted(timestamps)
            for i in range(1, len(sorted_ts)):
                gap = (sorted_ts[i] - sorted_ts[i - 1]).total_seconds()
                if 0 < gap <= IDLE_THRESHOLD_SEC:
                    active_sec += gap
            duration_min = max(1, int(active_sec / 60))

        start_kst = min(timestamps) if timestamps else None
        end_kst = max(timestamps) if timestamps else None
        end_time_str = end_kst.strftime("%H:%M") if end_kst else None

        result[date_str] = {
            "files": sorted(acc["files"]),
            "commands": acc["commands"][:10],
            "errors": acc["errors"][:5],
            "topic": acc["topic"],
            "duration_min": duration_min,
            "end_time": end_time_str,
            "start_kst": start_kst,
            "has_commits": acc["has_commits"],
            "tokens": {
                "input": acc["token_input"],
                "output": acc["token_output"],
                "cache_read": acc["token_cache_read"],
                "cache_create": acc["token_cache_create"],
                "api_calls": acc["api_calls"],
            },
        }

    return result
```

- [ ] **Step 2: 수동 검증 — 활성 세션 transcript로 테스트**

Run: `python3 -c "
import sys; sys.path.insert(0, 'cc/work-digest/scripts')
from session_logger import parse_transcript_by_date
result = parse_transcript_by_date('$HOME/.claude/projects/-Users-dayejeong-git-workplace-cube-backend/eb29c9dd-ace8-4cab-b17e-1645c1a235a7.jsonl')
for d, data in sorted(result.items()):
    print(f'{d}: {data[\"duration_min\"]}min, {len(data[\"files\"])} files, topic={data[\"topic\"][:50]}')
"`

Expected: 날짜별로 분할된 데이터가 출력됨.

- [ ] **Step 3: 커밋**

```bash
git add cc/work-digest/scripts/session_logger.py
git commit -m "feat: add parse_transcript_by_date for date-split logging"
```

---

### Task 3: session_logger.py — dedup + work-log 섹션 교체 + scan_and_record

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py:42-63` (dedup 함수)
- Modify: `cc/work-digest/scripts/session_logger.py:622-640` (write_session_marker)
- Modify: `cc/work-digest/scripts/session_logger.py:669-732` (main)

- [ ] **Step 1: dedup 함수를 session_id:date 키로 변경 + state 락 + TTL**

`session_logger.py:42-63`을 교체:

```python
def load_state() -> dict:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(STATE_FILE), os.O_RDONLY | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            content = STATE_FILE.read_text() if STATE_FILE.stat().st_size > 0 else "{}"
            return json.loads(content)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"recorded": {}}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(STATE_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, json.dumps(state, indent=2).encode())
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _cleanup_state(state: dict) -> dict:
    """7일 이상 된 엔트리 제거, 100개 제한."""
    recorded = state.get("recorded", {})
    if not isinstance(recorded, dict):
        # migrate from old list format — 기존 dedup state 유실은 의도적.
        # 1회성 재기록이 발생하지만 work-log 섹션 교체로 중복 방지됨.
        return {"recorded": {}}
    cutoff = (datetime.now(KST) - timedelta(days=7)).strftime("%Y-%m-%d")
    cleaned = {k: v for k, v in recorded.items() if v >= cutoff}
    # 100개 제한: 오래된 것부터 제거
    if len(cleaned) > 100:
        sorted_items = sorted(cleaned.items(), key=lambda x: x[1])
        cleaned = dict(sorted_items[-100:])
    return {"recorded": cleaned}


def already_recorded(session_id: str, date_str: str, force: bool = False) -> bool:
    """같은 session_id+date 조합의 중복 기록 방지.

    force=True: 기록을 덮어쓰기 위해 항상 False 반환 (SessionEnd용).
    """
    key = f"{session_id}:{date_str}"
    state = load_state()
    state = _cleanup_state(state)

    if not force and key in state.get("recorded", {}):
        save_state(state)
        return True

    state.setdefault("recorded", {})[key] = date_str
    save_state(state)
    return False
```

- [ ] **Step 2: write_session_marker를 섹션 교체 방식으로 변경**

`session_logger.py:622-640`을 교체:

```python
def write_session_marker(session_id, data, date_kst, repo):
    """세션 마커를 daily log에 기록.

    같은 session_id 섹션이 이미 있으면 교체, 없으면 append.
    date_kst: 기록할 날짜의 datetime (KST).
    """
    WORK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    daily_file = WORK_LOG_DIR / f"{date_kst.strftime('%Y-%m-%d')}.md"
    section = build_session_section(session_id, data, date_kst, repo)
    sid_short = session_id[:8] if session_id else "unknown"

    with open(daily_file, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read()

            if not content:
                # 새 파일: frontmatter + section
                f.seek(0)
                f.write(build_frontmatter(date_kst))
                f.write(section)
            else:
                # 같은 session_id 섹션 찾아서 교체
                pattern = rf"## 세션 [^\n]*\({sid_short},[^\n]*\n"
                match = re.search(pattern, content)
                if match:
                    # 다음 ## 또는 파일 끝까지가 이 섹션
                    section_start = match.start()
                    next_section = re.search(r"\n## 세션 ", content[match.end():])
                    if next_section:
                        section_end = match.end() + next_section.start() + 1  # +1 for \n
                    else:
                        section_end = len(content)
                    new_content = content[:section_start] + section + content[section_end:]
                    f.seek(0)
                    f.truncate()
                    f.write(new_content)
                else:
                    # 없으면 append
                    f.seek(0, 2)
                    f.write(section)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```

- [ ] **Step 3: scan_and_record() 코어 함수 추가**

`write_session_marker` 아래에 추가:

```python
def scan_and_record(session_id: str, transcript_path: str, cwd: str, force: bool = False) -> dict[str, dict]:
    """코어: transcript를 날짜별로 분할하여 work-log에 기록.

    Returns: {date_str: parsed_data} — 기록된 날짜별 데이터.
    """
    repo, branch = detect_repo_and_branch(cwd) if cwd else ("unknown", None)
    by_date = parse_transcript_by_date(transcript_path)

    if not by_date:
        return {}

    recorded = {}
    for date_str, data in sorted(by_date.items()):
        data["branch"] = branch

        # 무의미한 날짜 슬라이스 스킵
        if not data["files"] and not data["commands"] and not data["topic"]:
            continue

        # 중복 방지
        if already_recorded(session_id, date_str, force=force):
            continue

        # work-log에 기록
        date_kst = data.get("start_kst") or datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=KST)
        write_session_marker(session_id, data, date_kst, repo)
        recorded[date_str] = data

    return recorded
```

- [ ] **Step 4: main() 함수를 scan_and_record 기반으로 변경**

`session_logger.py:669-732`를 교체:

```python
def main():
    hook_input = parse_stdin()
    if not hook_input:
        sys.exit(0)

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")
    cwd = hook_input.get("cwd", "")
    event = hook_input.get("hook_event_name", "")

    if not transcript_path or not Path(transcript_path).exists():
        sys.exit(0)

    force = (event == "SessionEnd")
    recorded = scan_and_record(session_id, transcript_path, cwd, force=force)

    if not recorded:
        sys.exit(0)

    repo = Path(cwd).name if cwd else "unknown"
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            git_common = Path(result.stdout.strip())
            if not git_common.is_absolute():
                git_common = (Path(cwd) / git_common).resolve()
            repo = git_common.parent.name
    except Exception:
        pass

    # SessionEnd: LLM 요약 + 행동 추출 (세션 전체 대상, 1회)
    if event == "SessionEnd":
        from concurrent.futures import ThreadPoolExecutor

        conversation = extract_conversation(transcript_path)
        user_msgs = extract_user_messages(transcript_path)
        summary = None
        signals = None

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                summary_future = pool.submit(summarize_session, conversation, repo)
                signals_future = pool.submit(extract_behavioral_signals, user_msgs, repo)

                try:
                    summary = summary_future.result(timeout=SUMMARY_TIMEOUT_SEC + 10)
                except Exception as e:
                    print(f"[session_logger] summary future failed: {e}", file=sys.stderr)

                try:
                    signals = signals_future.result(timeout=BEHAVIOR_TIMEOUT_SEC + 10)
                except Exception as e:
                    print(f"[session_logger] signals future failed: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[session_logger] ThreadPool failed: {e}", file=sys.stderr)

        # 요약을 마지막 활동 날짜의 work-log 섹션에 업데이트
        if summary or signals:
            last_date = max(recorded.keys())
            last_data = recorded[last_date]
            if summary:
                last_data["summary"] = summary
            if signals:
                last_data["behavioral_signals"] = signals
            date_kst = last_data.get("start_kst") or datetime.strptime(last_date, "%Y-%m-%d").replace(tzinfo=KST)
            write_session_marker(session_id, last_data, date_kst, repo)

        # 텔레그램 전송
        last_date = max(recorded.keys())
        last_data = recorded[last_date]
        total_duration = sum(d.get("duration_min") or 0 for d in recorded.values())
        send_session_telegram(last_data, repo, total_duration or None)
```

- [ ] **Step 5: 수동 검증 — hook 시뮬레이션**

기존 work-log 백업 후, 테스트 transcript로 main()이 날짜별로 work-log를 생성하는지 확인.

- [ ] **Step 6: 커밋**

```bash
git add cc/work-digest/scripts/session_logger.py
git commit -m "feat: refactor session_logger with date-split scan_and_record"
```

---

## Chunk 2: Scanner + Daily Coach 연동

### Task 4: active_session_scanner.py 작성

**Files:**
- Create: `cc/work-digest/scripts/active_session_scanner.py`

- [ ] **Step 1: scanner 모듈 작성**

```python
#!/usr/bin/env python3
"""Active Session Scanner — find open CC sessions and record them.

열려있는 CC 세션의 transcript를 탐색하여 work-log에 기록.
session_logger.py의 scan_and_record()를 재사용.

Usage:
    python3 active_session_scanner.py              # scan all active sessions
    python3 active_session_scanner.py --dry-run    # list only, don't record
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# session_logger.py와 같은 디렉토리
sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_logger import scan_and_record

KST = timezone(timedelta(hours=9))
SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _cwd_to_project_hash(cwd: str) -> str:
    """cwd 경로를 CC project hash로 변환.

    /Users/dayejeong/git_workplace/cube-backend → -Users-dayejeong-git-workplace-cube-backend
    """
    return "-" + cwd.lstrip("/").replace("/", "-").replace("_", "-")


def _resolve_cwd_for_worktree(cwd: str) -> str | None:
    """worktree cwd에서 원본 레포 경로를 추출."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            git_common = Path(result.stdout.strip())
            if not git_common.is_absolute():
                git_common = (Path(cwd) / git_common).resolve()
            # .git → parent is repo root
            return str(git_common.parent)
    except Exception:
        pass
    return None


def find_transcript(session_id: str, cwd: str) -> Path | None:
    """세션 ID와 cwd로 transcript JSONL 경로를 탐색."""
    # 1차: cwd 직접 변환
    project_hash = _cwd_to_project_hash(cwd)
    candidate = PROJECTS_DIR / project_hash / f"{session_id}.jsonl"
    if candidate.exists():
        return candidate

    # 2차: worktree → 원본 레포 경로로 재시도
    original_cwd = _resolve_cwd_for_worktree(cwd)
    if original_cwd and original_cwd != cwd:
        project_hash = _cwd_to_project_hash(original_cwd)
        candidate = PROJECTS_DIR / project_hash / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate

    # 3차: projects 전체 검색 (fallback)
    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate

    return None


def _is_pid_alive(pid: int) -> bool:
    """프로세스가 살아있는지 확인."""
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True  # 프로세스 존재하지만 권한 없음
    except ProcessLookupError:
        return False


def get_active_sessions() -> list[dict]:
    """~/.claude/sessions/*.json에서 활성 세션 목록 수집."""
    sessions = []
    if not SESSIONS_DIR.exists():
        return sessions

    for session_file in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(session_file.read_text())
            sessions.append({
                "pid": data["pid"],
                "session_id": data["sessionId"],
                "cwd": data["cwd"],
                "started_at": data.get("startedAt", 0),
                "alive": _is_pid_alive(data["pid"]),
                "file": session_file,
            })
        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(f"[scanner] failed to read {session_file}: {e}", file=sys.stderr)

    return sessions


def scan_active_sessions(dry_run: bool = False) -> int:
    """모든 활성 세션을 스캔하여 work-log에 기록.

    Returns: 기록된 세션 수.
    """
    sessions = get_active_sessions()
    if not sessions:
        return 0

    recorded_count = 0
    for s in sessions:
        session_id = s["session_id"]
        cwd = s["cwd"]

        transcript = find_transcript(session_id, cwd)
        if not transcript:
            print(f"[scanner] no transcript for {session_id[:8]} ({Path(cwd).name})", file=sys.stderr)
            continue

        if dry_run:
            status = "ALIVE" if s["alive"] else "DEAD"
            started = datetime.fromtimestamp(s["started_at"] / 1000, KST).strftime("%m/%d %H:%M")
            print(f"  {status} | {started} | {Path(cwd).name} | {session_id[:8]} | {transcript}")
            continue

        try:
            result = scan_and_record(session_id, str(transcript), cwd, force=False)
            if result:
                dates = ", ".join(sorted(result.keys()))
                print(f"[scanner] {session_id[:8]} ({Path(cwd).name}): recorded {dates}", file=sys.stderr)
                recorded_count += len(result)
        except Exception as e:
            print(f"[scanner] {session_id[:8]} failed: {e}", file=sys.stderr)

    return recorded_count


def main():
    parser = argparse.ArgumentParser(description="Scan active CC sessions")
    parser.add_argument("--dry-run", action="store_true", help="List sessions only")
    args = parser.parse_args()

    count = scan_active_sessions(dry_run=args.dry_run)
    if not args.dry_run:
        print(f"[scanner] Total: {count} date-slices recorded", file=sys.stderr)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 수동 검증 — dry-run**

Run: `python3 cc/work-digest/scripts/active_session_scanner.py --dry-run`

Expected: 활성 세션 목록이 출력됨 (ALIVE/DEAD, 시작 시간, 레포, transcript 경로).

- [ ] **Step 3: 실제 스캔 테스트**

Run: `python3 cc/work-digest/scripts/active_session_scanner.py`

Expected: `[scanner] ... recorded 2026-03-14, 2026-03-15` 형태로 기록됨.

work-log 확인: `cat cc/work-digest/work-log/2026-03-14.md | head -50`

- [ ] **Step 4: 커밋**

```bash
git add cc/work-digest/scripts/active_session_scanner.py
git commit -m "feat: add active session scanner for open CC sessions"
```

---

### Task 5: daily_coach.py — scanner + sync 연동

**Files:**
- Modify: `shared/life-coach/scripts/daily_coach.py:399-432` (main 함수)

- [ ] **Step 1: daily_coach.py에 scanner + sync import 추가**

`daily_coach.py` 상단 import 영역에 추가:

```python
_SCANNER_DIR = Path(__file__).resolve().parent.parent.parent.parent / "cc" / "work-digest" / "scripts"
```

- [ ] **Step 2: main() 함수에 scanner → sync 호출 추가**

`daily_coach.py:399-432`의 `main()` 함수를 수정. `data = get_today_data(conn, args.date)` 호출 전에 scanner + sync를 추가:

```python
def main():
    parser = argparse.ArgumentParser(description="Daily coaching report")
    parser.add_argument("--dry-run", action="store_true", help="stdout only")
    parser.add_argument("--json", action="store_true", help="JSON data for LLM on-demand coaching")
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    # 1) 열린 세션 스캔 → work-log에 기록
    try:
        sys.path.insert(0, str(_SCANNER_DIR))
        from active_session_scanner import scan_active_sessions
        scan_active_sessions()
    except Exception as e:
        print(f"[daily_coach] scanner failed: {e}", file=sys.stderr)

    # 2) work-log → SQLite 동기화
    try:
        _sync_dir = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
        sys.path.insert(0, str(_sync_dir))
        from sync_cc import sync_date as sync_cc_date
        from db import get_conn as get_db_conn
        sync_conn = get_db_conn()
        try:
            sync_cc_date(sync_conn, args.date)
            sync_conn.commit()
        finally:
            sync_conn.close()
    except Exception as e:
        print(f"[daily_coach] sync failed: {e}", file=sys.stderr)

    conn = get_conn()
    try:
        data = get_today_data(conn, args.date)
        # ... (이하 기존 코드 동일)
```

- [ ] **Step 3: end-to-end 테스트**

Run: `python3 shared/life-coach/scripts/daily_coach.py --dry-run --date 2026-03-14`

Expected: 이전에 누락되었던 세션들이 포함된 daily report가 출력됨. 5세션 → 기존보다 많은 세션 수.

- [ ] **Step 4: sync 후 SQLite 확인**

Run: `sqlite3 ~/life-dashboard/data.db "SELECT source, repo, tag, summary, date, duration_min FROM activities WHERE date = '2026-03-14' ORDER BY start_at;"`

Expected: 기존 5건 + 새로 스캔된 세션들이 보임.

- [ ] **Step 5: 커밋**

```bash
git add shared/life-coach/scripts/daily_coach.py
git commit -m "feat: integrate session scanner + sync into daily coach pipeline"
```
