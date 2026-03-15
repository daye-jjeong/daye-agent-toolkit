# Direct SQLite Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CC와 Codex session_logger가 work-log markdown 없이 SQLite에 직접 기록하도록 리팩토링한다.

**Architecture:** 공유 `activity_writer.py`가 ParsedData → SQLite 변환을 담당. CC/Codex 양쪽 session_logger가 각자의 날짜 분할 파서 출력을 `record_activities()`로 전달. 에이전트용 CLI로 미요약 세션 조회/업데이트 지원.

**Tech Stack:** Python 3 stdlib only (sqlite3, json, argparse)

**Spec:** `docs/superpowers/specs/2026-03-15-direct-sqlite-design.md`

---

## Chunk 1: 공유 코어 + CC 리팩토링

### Task 1: activity_writer.py 작성

**Files:**
- Create: `shared/life-dashboard-mcp/activity_writer.py`
- Move from: `shared/life-dashboard-mcp/_sync_common.py` (auto_tag 함수)

- [ ] **Step 1: activity_writer.py 작성 — record_activities + auto_tag**

`_sync_common.py`의 `auto_tag()` 및 관련 상수를 이동하고, `record_activities()` 함수 추가.

```python
#!/usr/bin/env python3
"""Activity Writer — shared SQLite recording for CC and Codex session loggers.

Usage (library):
    from activity_writer import record_activities
    record_activities("cc", session_id, by_date, repo, branch)

Usage (CLI):
    python3 activity_writer.py unsummarized --date 2026-03-15
    python3 activity_writer.py update-summary --session-id X --date Y --tag "코딩" --summary "..."
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn, upsert_activity, update_daily_stats, insert_behavioral_signal

KST = timezone(timedelta(hours=9))

# ── auto_tag (moved from _sync_common.py) ─────────────────

TAG_KEYWORDS: list[tuple[str, list[str]]] = [
    ("디버깅", ["debug", "디버깅", "에러", "error", "fix", "버그", "traceback", "stack trace",
               "동작 안", "동작안해", "왜 안"]),
    ("리뷰", ["review", "리뷰", "code quality", "pr review", "approved", "rejected",
             "git diff", "검토", "괜찮은지", "수정할건"]),
    ("리서치", ["리서치", "research", "조사", "비교", "추천", "어떤게 있을까", "프레임워크"]),
    ("설계", ["설계", "design", "기획", "plan", "아키텍처", "brainstorm",
             "목업", "mockup", "mock-up", "검증", "verify"]),
    ("설정", ["설정", "config", "setup", "셋업", "install", "init"]),
    ("문서", ["문서", "SKILL.md", "README", "documentation", "표준화", "문서화"]),
    ("리팩토링", ["리팩토링", "refactor", "정리", "통합", "consolidat"]),
    ("ops", ["deploy", "배포", "cron", "monitor", "운영", "워치독",
            "thread list", "task list", "minions"]),
    ("코딩", ["구현", "implement", "추가", "생성", "만들", "작성", "feature",
             "write_file", "apply_diff", "create_file"]),
]

_WORD_BOUNDARY_KW = frozenset({"error", "fix", "init", "plan"})


def _kw_matches(kw: str, text: str) -> bool:
    kw_lower = kw.lower()
    if kw_lower in _WORD_BOUNDARY_KW:
        return bool(re.search(r"\b" + re.escape(kw_lower) + r"\b", text))
    return kw_lower in text


def auto_tag(*text_sources: str) -> str:
    text = " ".join(text_sources).lower()
    for tag, keywords in TAG_KEYWORDS:
        if any(_kw_matches(kw, text) for kw in keywords):
            return tag
    return "기타"


# ── record_activities ─────────────────────────────

_SIGNAL_TYPE_MAP = {"decisions": "decision", "mistakes": "mistake", "patterns": "pattern"}
_TEST_KEYWORDS = frozenset({"pytest", "jest", "test", "vitest"})
_TEST_PATTERNS = ("npm run test", "npx test", "npm test", "bun test")


def record_activities(
    source: str,
    session_id: str,
    by_date: dict[str, dict],
    repo: str,
    branch: str | None = None,
    summary: dict | None = None,
    behavioral_signals: dict | None = None,
) -> dict[str, str]:
    """날짜별 분할 데이터를 SQLite에 직접 기록.

    Returns: {date_str: session_id} — 기록된 날짜별.
    """
    if not by_date:
        return {}

    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    recorded = {}
    dates = sorted(by_date.keys())
    last_date = dates[-1]

    try:
        for date_str in dates:
            data = by_date[date_str]

            # 무의미한 슬라이스 skip
            if not data.get("files") and not data.get("commands") and not data.get("topic"):
                continue

            tokens = data.get("tokens", {})
            token_total = sum(tokens.get(k, 0) for k in ("input", "output", "cache_read", "cache_create"))

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

            # 마지막 날짜에 summary/tag 적용
            tag = None
            summary_text = None
            if date_str == last_date and summary:
                tag = summary.get("tag")
                summary_text = summary.get("text")
            if not tag:
                tag = auto_tag(data.get("topic", ""), " ".join(data.get("commands", [])[:5]))

            activity = {
                "source": source,
                "session_id": session_id,
                "repo": repo,
                "branch": branch,
                "tag": tag if (date_str == last_date and summary) else None,
                "summary": summary_text if (date_str == last_date and summary) else None,
                "start_at": start_at,
                "end_at": end_at,
                "date": date_str,
                "duration_min": data.get("duration_min"),
                "file_count": len(data.get("files", [])),
                "error_count": len(data.get("errors", [])),
                "has_tests": has_tests,
                "has_commits": 1 if has_commits else 0,
                "token_total": token_total,
                "raw_json": json.dumps({
                    "topic": data.get("topic", ""),
                    "files_changed": data.get("files", []),
                    "commands": data.get("commands", [])[:10],
                    "errors": data.get("errors", [])[:5],
                }, ensure_ascii=False),
            }
            upsert_activity(conn, activity)
            recorded[date_str] = session_id

            # behavioral signals (마지막 날짜에만)
            if date_str == last_date and behavioral_signals:
                for plural, singular in _SIGNAL_TYPE_MAP.items():
                    for content in behavioral_signals.get(plural, []):
                        insert_behavioral_signal(conn, {
                            "session_id": session_id,
                            "date": date_str,
                            "signal_type": singular,
                            "content": content,
                            "repo": repo,
                        })

        # daily_stats 업데이트
        for date_str in recorded:
            update_daily_stats(conn, date_str)

        conn.commit()
    finally:
        conn.close()

    return recorded


# ── CLI ───────────────────────────────────────────

def cmd_unsummarized(args):
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT session_id, date, repo, source, raw_json
            FROM activities
            WHERE date = ? AND (tag IS NULL OR summary IS NULL)
            ORDER BY start_at
        """, (args.date,)).fetchall()
        results = []
        for r in rows:
            raw = json.loads(r["raw_json"] or "{}")
            results.append({
                "session_id": r["session_id"],
                "date": r["date"],
                "repo": r["repo"],
                "source": r["source"],
                "topic": raw.get("topic", ""),
            })
        print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def cmd_update_summary(args):
    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        cursor = conn.execute("""
            UPDATE activities
            SET tag = ?, summary = ?
            WHERE session_id = ? AND date = ?
        """, (args.tag, args.summary, args.session_id, args.date))
        if cursor.rowcount == 0:
            print(f"No activity found: {args.session_id} / {args.date}", file=sys.stderr)
            sys.exit(1)
        update_daily_stats(conn, args.date)
        conn.commit()
        print(f"Updated: {args.session_id} [{args.tag}] {args.summary[:50]}", file=sys.stderr)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Activity Writer CLI")
    sub = parser.add_subparsers(dest="command")

    p_unsummarized = sub.add_parser("unsummarized", help="List unsummarized sessions")
    p_unsummarized.add_argument("--date", required=True)

    p_update = sub.add_parser("update-summary", help="Update session summary")
    p_update.add_argument("--session-id", required=True)
    p_update.add_argument("--date", required=True)
    p_update.add_argument("--tag", required=True)
    p_update.add_argument("--summary", required=True)

    args = parser.parse_args()
    if args.command == "unsummarized":
        cmd_unsummarized(args)
    elif args.command == "update-summary":
        cmd_update_summary(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 수동 검증**

Run: `python3 shared/life-dashboard-mcp/activity_writer.py unsummarized --date 2026-03-14`
Expected: JSON 출력 (tag=NULL인 세션 목록 또는 빈 배열).

Run: `python3 -c "from activity_writer import record_activities; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: 커밋**

```bash
git add shared/life-dashboard-mcp/activity_writer.py
git commit -m "feat: add activity_writer.py — shared SQLite recording + CLI"
```

---

### Task 2: CC session_logger.py — SQLite 직접 기록으로 전환

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py`

이 태스크는 큰 리팩토링이므로 단계적으로 진행.

- [ ] **Step 1: markdown 관련 함수 제거**

다음 함수/상수를 제거:
- `WORK_LOG_DIR`, `STATE_FILE` 상수
- `load_state()`, `save_state()`, `_cleanup_state()`, `already_recorded()` 함수
- `_format_tokens()` (로컬 wrapper)
- `build_frontmatter()`, `build_session_section()`, `write_session_marker()` 함수

`_common`에서 `format_tokens` import도 제거 (activity_writer가 대체).

- [ ] **Step 2: scan_and_record()를 record_activities 기반으로 변경**

```python
import sys
from pathlib import Path

# activity_writer import
_MCP_DIR = Path(__file__).resolve().parent.parent.parent.parent / "shared" / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from activity_writer import record_activities


def scan_and_record(session_id: str, transcript_path: str, cwd: str) -> dict[str, dict]:
    """코어: transcript를 날짜별로 분할하여 SQLite에 기록."""
    repo, branch = detect_repo_and_branch(cwd) if cwd else ("unknown", None)
    by_date = parse_transcript_by_date(transcript_path)
    if not by_date:
        return {}

    record_activities("cc", session_id, by_date, repo, branch)
    return by_date
```

`force` 파라미터 제거 — SQLite upsert가 dedup을 담당하므로 항상 upsert.

- [ ] **Step 3: main()을 새 구조로 변경**

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

    by_date = scan_and_record(session_id, transcript_path, cwd)
    if not by_date:
        sys.exit(0)

    repo, branch = detect_repo_and_branch(cwd) if cwd else ("unknown", None)

    # SessionEnd: LLM 요약 + 행동 추출
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
                    print(f"[session_logger] summary failed: {e}", file=sys.stderr)
                try:
                    signals = signals_future.result(timeout=BEHAVIOR_TIMEOUT_SEC + 10)
                except Exception as e:
                    print(f"[session_logger] signals failed: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[session_logger] ThreadPool failed: {e}", file=sys.stderr)

        if summary or signals:
            record_activities("cc", session_id, by_date, repo, branch,
                            summary=summary, behavioral_signals=signals)

        # 텔레그램 전송
        last_date = max(by_date.keys())
        last_data = by_date[last_date]
        total_duration = sum(d.get("duration_min") or 0 for d in by_date.values())
        send_session_telegram(last_data, repo, total_duration or None, summary)
```

- [ ] **Step 4: send_session_telegram 시그니처 업데이트**

summary를 파라미터로 받도록 변경:

```python
def send_session_telegram(data: dict, repo: str, duration_min: int | None, summary: dict | None = None):
    branch = data.get("branch")
    repo_label = f"{repo}/{branch}" if branch else repo
    if summary:
        tag = summary.get("tag", "")
        text = summary.get("text", "")
        tag_str = f"[{tag}] " if tag else ""
        msg = f"✅ {repo_label} — {tag_str}{text}"
    else:
        topic = data.get("topic", "작업 완료")
        msg = f"✅ {repo_label} — {topic[:100]}"
    dur = f" ({duration_min}분)" if duration_min else ""
    msg = f"{msg}{dur}"
    if len(msg) > 4096:
        msg = msg[:4090] + "..."
    send_telegram(msg, chat_id_key="CHAT_ID_SESSION", silent=True)
```

- [ ] **Step 5: 수동 검증**

Run: `python3 -c "import sys; sys.path.insert(0, 'cc/work-digest/scripts'); import session_logger; print('OK:', hasattr(session_logger, 'scan_and_record'))"`
Expected: `OK: True`

`write_session_marker`, `build_session_section` 등이 없는지 확인:
Run: `grep -n "write_session_marker\|build_session_section\|build_frontmatter\|WORK_LOG_DIR\|STATE_FILE\|load_state\|save_state\|already_recorded\|_cleanup_state" cc/work-digest/scripts/session_logger.py`
Expected: 결과 없음.

- [ ] **Step 6: 커밋**

```bash
git add cc/work-digest/scripts/session_logger.py
git commit -m "refactor: CC session_logger writes directly to SQLite, remove markdown"
```

---

### Task 3: active_session_scanner.py 업데이트

**Files:**
- Modify: `cc/work-digest/scripts/active_session_scanner.py`

scan_and_record의 시그니처가 변경되었으므로 (force 파라미터 제거, 반환값 변경) 그에 맞게 업데이트.

- [ ] **Step 1: scan_and_record 호출부 업데이트**

`force=False` 인자 제거 (더 이상 존재하지 않음). `scan_and_record`는 이제 `by_date` dict를 반환.

```python
        try:
            result = scan_and_record(session_id, str(transcript), cwd)
            if result:
                dates = ", ".join(sorted(result.keys()))
                print(f"[scanner] {session_id[:8]} ({Path(cwd).name}): recorded {dates}", file=sys.stderr)
                recorded_count += len(result)
        except Exception as e:
            print(f"[scanner] {session_id[:8]} failed: {e}", file=sys.stderr)
```

- [ ] **Step 2: 수동 검증 — dry-run**

Run: `python3 cc/work-digest/scripts/active_session_scanner.py --dry-run`
Expected: 활성 세션 목록 출력.

- [ ] **Step 3: 커밋**

```bash
git add cc/work-digest/scripts/active_session_scanner.py
git commit -m "fix: update scanner for new scan_and_record signature"
```

---

## Chunk 2: Codex 리팩토링 + 정리

### Task 4: Codex session_logger.py — parse_rollout_by_date + SQLite 직접 기록

**Files:**
- Modify: `codex/work-digest/scripts/session_logger.py`

- [ ] **Step 1: parse_rollout_by_date() 추가**

기존 `parse_transcript()` (line 474) 바로 아래에 추가. 기존 `parse_transcript`의 로직을 날짜별로 분할하는 버전.

```python
def parse_rollout_by_date(transcript_path: str) -> dict[str, dict]:
    """Parse Codex rollout JSONL and split by KST date.

    Returns: {"2026-03-14": ParsedData, ...}
    ParsedData는 CC의 parse_transcript_by_date()와 동일한 구조.
    """
    by_date: dict[str, dict] = {}
    current_date = None
    prev_token_total = 0  # 누적값 → 증분 계산용

    for entry in _iter_entries(transcript_path):
        payload = _get_payload(entry)
        timestamp = _parse_timestamp(entry.get("timestamp"))

        entry_date = current_date
        if timestamp is not None:
            kst_dt = _to_kst(timestamp)
            if kst_dt:
                entry_date = kst_dt.strftime("%Y-%m-%d")
                current_date = entry_date

        if not entry_date:
            continue

        if entry_date not in by_date:
            by_date[entry_date] = {
                "files": set(),
                "commands": [],
                "errors": [],
                "topic": "",
                "timestamps": [],
                "token_total": 0,
                "has_commits": False,
            }

        acc = by_date[entry_date]
        if timestamp is not None:
            acc["timestamps"].append(timestamp)

        entry_type = entry.get("type")
        payload_type = payload.get("type")

        # user message → topic (first per date)
        if not acc["topic"]:
            if entry_type == "event_msg" and payload_type == "user_message":
                candidate = _normalize_user_text(str(payload.get("message", "")))
                if candidate:
                    acc["topic"] = candidate[:120]
            elif entry_type == "response_item" and payload_type == "message" and payload.get("role") == "user":
                candidate = _normalize_user_text(_extract_content_text(payload.get("content")))
                if candidate:
                    acc["topic"] = candidate[:120]

        # tokens (cumulative → track for delta)
        if entry_type == "event_msg" and payload_type == "token_count":
            info = payload.get("info")
            if isinstance(info, dict):
                total_usage = info.get("total_token_usage", {})
                if isinstance(total_usage, dict):
                    new_total = int(total_usage.get("total_tokens", 0) or 0)
                    if new_total > prev_token_total:
                        delta = new_total - prev_token_total
                        acc["token_total"] += delta
                        prev_token_total = new_total

        # commands
        if entry_type == "response_item" and payload_type == "function_call":
            args = _parse_arguments(payload.get("arguments"))
            command = _extract_command(args)
            if command:
                acc["commands"].append(command)
                if not acc["has_commits"] and "git commit" in command.lower():
                    acc["has_commits"] = True
            # file changes
            name = payload.get("name", "")
            if name in ("write_file", "apply_diff", "create_file"):
                fpath = args.get("path", "") or args.get("file_path", "")
                if fpath:
                    acc["files"].add(fpath)

        # errors
        if entry_type == "response_item" and payload_type == "function_call_output":
            failure = _extract_failure_text(str(payload.get("output", "")))
            if failure:
                acc["errors"].append(failure)

    # accumulator → ParsedData
    result = {}
    for date_str, acc in by_date.items():
        timestamps = acc["timestamps"]
        duration_min = None
        if len(timestamps) >= 2:
            active_sec = 0
            for prev, curr in zip(timestamps, timestamps[1:]):
                gap = (curr - prev).total_seconds()
                if 0 < gap <= IDLE_THRESHOLD_SEC:
                    active_sec += gap
            if active_sec > 0:
                duration_min = max(1, int(active_sec / 60))

        start_kst = _to_kst(min(timestamps)) if timestamps else None
        end_kst = _to_kst(max(timestamps)) if timestamps else None

        result[date_str] = {
            "files": sorted(acc["files"]),
            "commands": acc["commands"][:10],
            "errors": acc["errors"][:5],
            "topic": acc["topic"],
            "duration_min": duration_min,
            "end_time": end_kst.strftime("%H:%M") if end_kst else None,
            "start_kst": start_kst,
            "has_commits": acc["has_commits"],
            "tokens": {
                "input": 0, "output": 0,
                "cache_read": 0, "cache_create": 0,
                "api_calls": acc["token_total"],  # Codex는 total만 추적
            },
        }

    return result
```

- [ ] **Step 2: main()을 record_activities 기반으로 변경**

markdown 관련 함수 제거 + record_activities 호출:

```python
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--transcript-path", required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--cwd", default="")
    args = parser.parse_args()

    transcript = Path(args.transcript_path)
    if not transcript.exists():
        sys.exit(0)

    by_date = parse_rollout_by_date(str(transcript))
    if not by_date:
        sys.exit(0)

    # cwd fallback: parse_transcript에서 추출하던 것을 여기서 처리
    effective_cwd = args.cwd
    if not effective_cwd:
        # session_meta에서 cwd 추출
        for entry in _iter_entries(str(transcript)):
            if entry.get("type") == "session_meta":
                effective_cwd = str(_get_payload(entry).get("cwd", ""))
                break
            if entry.get("type") == "turn_context":
                effective_cwd = str(_get_payload(entry).get("cwd", ""))
                break

    repo = detect_repo(effective_cwd)
    session_id = args.session_id or transcript.stem

    # SQLite에 기록 (요약 없이)
    record_activities("codex", session_id, by_date, repo)

    # session_end / compaction: LLM 요약
    summary = None
    signals = None

    if args.event == "session_end":
        from concurrent.futures import ThreadPoolExecutor
        conversation = extract_conversation(str(transcript))
        user_msgs = extract_user_messages(str(transcript))
        work_cwd = effective_cwd or str(transcript.parent)

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                summary_future = pool.submit(summarize_session, conversation, repo, work_cwd)
                signals_future = pool.submit(extract_behavioral_signals, user_msgs, repo, work_cwd)
                try:
                    summary = summary_future.result(timeout=SUMMARY_TIMEOUT_SEC + 10)
                except Exception as e:
                    print(f"[session_logger] summary failed: {e}", file=sys.stderr)
                try:
                    signals = signals_future.result(timeout=BEHAVIOR_TIMEOUT_SEC + 10)
                except Exception as e:
                    print(f"[session_logger] signals failed: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[session_logger] ThreadPool failed: {e}", file=sys.stderr)

    elif args.event == "compaction":
        summary = _build_compaction_summary(
            parse_transcript(str(transcript)), str(transcript),
            repo, effective_cwd or str(transcript.parent),
        )

    if summary or signals:
        record_activities("codex", session_id, by_date, repo,
                        summary=summary, behavioral_signals=signals)

    if args.event == "session_end":
        last_data = by_date[max(by_date.keys())]
        total_dur = sum(d.get("duration_min") or 0 for d in by_date.values())
        send_session_telegram(last_data, repo, total_dur or None, summary)
```

- [ ] **Step 3: markdown 관련 함수/상수 제거**

제거 대상:
- `WORK_LOG_DIR`, `STATE_FILE` 상수
- `load_state()`, `save_state()`, `already_recorded()` 함수
- `_format_tokens()`, `build_frontmatter()`, `build_session_section()`, `write_session_marker()` 함수

activity_writer import 추가:
```python
_MCP_DIR = Path(__file__).resolve().parent.parent.parent.parent / "shared" / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from activity_writer import record_activities
```

send_session_telegram도 CC와 동일하게 summary 파라미터 추가.

- [ ] **Step 4: 수동 검증**

Run: `python3 -c "import sys; sys.path.insert(0, 'codex/work-digest/scripts'); from session_logger import parse_rollout_by_date; print('OK')"`
Expected: `OK`

실제 Codex 세션으로 테스트:
Run: `python3 -c "
import sys; sys.path.insert(0, 'codex/work-digest/scripts')
from session_logger import parse_rollout_by_date
result = parse_rollout_by_date('$HOME/.codex/sessions/2026/03/14/rollout-2026-03-14T14-13-37-019ceac3-a85a-71d1-b99e-d6fac8ee95a6.jsonl')
for d, data in sorted(result.items()):
    print(f'{d}: {data[\"duration_min\"]}min, {len(data[\"files\"])} files, topic={data[\"topic\"][:50]}')
"`
Expected: 날짜별 분할 데이터 출력.

- [ ] **Step 5: 커밋**

```bash
git add codex/work-digest/scripts/session_logger.py
git commit -m "refactor: Codex session_logger writes directly to SQLite, add parse_rollout_by_date"
```

---

### Task 5: daily_coach.py — sync 제거

**Files:**
- Modify: `shared/life-coach/scripts/daily_coach.py`

- [ ] **Step 1: sync 호출 블록 제거**

`main()` 함수에서 sync 관련 코드 제거:

```python
    # 제거할 부분:
    # 2) work-log → SQLite 동기화 (CC + Codex)
    # try:
    #     from sync_cc import sync_date as sync_cc_date
    #     from sync_codex import sync_date as sync_codex_date
    #     ...
```

`scan_active_sessions()`만 유지:

```python
    # 1) 열린 세션 스캔 → SQLite 직접 기록
    try:
        from active_session_scanner import scan_active_sessions
        scan_active_sessions()
    except Exception as e:
        print(f"[daily_coach] scanner failed: {e}", file=sys.stderr)

    conn = get_conn()
    try:
        data = get_today_data(conn, args.date)
        ...
```

- [ ] **Step 2: 수동 검증**

Run: `python3 shared/life-coach/scripts/daily_coach.py --dry-run --date 2026-03-14 2>&1 | head -5`
Expected: daily report 출력 (sync 에러 없이).

- [ ] **Step 3: 커밋**

```bash
git add shared/life-coach/scripts/daily_coach.py
git commit -m "refactor: remove sync calls from daily_coach, data comes directly from session loggers"
```

---

### Task 6: 파일 삭제 + cron 정리

**Files:**
- Delete: `shared/life-dashboard-mcp/sync_cc.py`
- Delete: `shared/life-dashboard-mcp/sync_codex.py`
- Delete: `shared/life-dashboard-mcp/_sync_common.py`
- Delete: `shared/life-dashboard-mcp/cron.json`
- Delete: `cc/work-digest/scripts/parse_work_log.py`
- Delete: `cc/work-digest/scripts/daily_digest.py`
- Delete: `cc/work-digest/scripts/weekly_digest.py`

- [ ] **Step 1: 파일 삭제**

```bash
git rm shared/life-dashboard-mcp/sync_cc.py
git rm shared/life-dashboard-mcp/sync_codex.py
git rm shared/life-dashboard-mcp/_sync_common.py
git rm shared/life-dashboard-mcp/cron.json
git rm cc/work-digest/scripts/parse_work_log.py
git rm cc/work-digest/scripts/daily_digest.py
git rm cc/work-digest/scripts/weekly_digest.py
```

- [ ] **Step 2: 깨진 import 확인**

Run: `grep -rn "sync_cc\|sync_codex\|_sync_common\|parse_work_log\|daily_digest\|weekly_digest" shared/ cc/ codex/ --include="*.py" | grep -v "__pycache__" | grep -v "work-log/"`
Expected: 결과 없음 (이전 태스크에서 모든 참조 제거 완료).

- [ ] **Step 3: 커밋**

```bash
git commit -m "chore: delete deprecated sync scripts, parse_work_log, daily/weekly digest"
```

---

### Task 7: 문서 업데이트

**Files:**
- Modify: `shared/life-coach/SKILL.md`
- Modify: `shared/life-coach/cron.json`
- Modify: `cc/work-digest/SKILL.md`

- [ ] **Step 1: life-coach SKILL.md — sync 호출 제거 + daily-coach 워크플로우 업데이트**

`sync_cc.py` / `sync_codex.py` 호출 부분을 제거하고, daily-coach 워크플로우에 미요약 세션 처리 단계 추가.

- [ ] **Step 2: life-coach cron.json — daily-coach instructions 업데이트**

```json
{
    "name": "daily-coach",
    "schedule": "0 21 * * *",
    "target": "daily-coach",
    "reason": "cron: daily-coach",
    "instructions": "life-coach 스킬의 '일일 코칭' 절차를 따르세요. 먼저 active_session_scanner.py를 실행하고, 미요약 세션이 있으면 activity_writer.py로 요약을 업데이트한 뒤 코칭을 생성하세요."
}
```

- [ ] **Step 3: work-digest SKILL.md — parse_work_log, daily_digest 참조 제거**

파이프라인 설명을 "session_logger → SQLite 직접 기록"으로 변경.

- [ ] **Step 4: 커밋**

```bash
git add shared/life-coach/SKILL.md shared/life-coach/cron.json cc/work-digest/SKILL.md
git commit -m "docs: update SKILL.md and cron for direct-sqlite pipeline"
```
