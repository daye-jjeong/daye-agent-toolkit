#!/usr/bin/env python3
"""Codex CLI session JSONL -> SQLite sync.

Two data sources are merged per session:
1. Codex work-log markdown (LLM summary + tag from session_logger.py)
2. Raw JSONL session files (timestamps, tokens, files, agent messages)

Work-log provides better summaries (LLM-generated) and tags.
JSONL provides accurate timestamps, token counts, and file changes.

Usage:
    python3 sync_codex.py                    # today
    python3 sync_codex.py --date 2026-03-11  # specific date
    python3 sync_codex.py --days 7           # last 7 days
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import subprocess

from db import get_conn, upsert_activity, update_daily_stats, insert_behavioral_signal
from _sync_common import auto_tag

KST = timezone(timedelta(hours=9))
SESSION_ROOT = Path.home() / ".codex" / "sessions"
CODEX_WORK_LOG_DIR = (
    Path(__file__).resolve().parent.parent.parent / "codex" / "work-digest" / "work-log"
)

FILE_WRITE_NAMES = frozenset({"write_file", "apply_diff", "create_file"})
COMMAND_NAMES = frozenset({"shell", "execute", "run_command", "exec_command"})
TEST_KEYWORDS = frozenset({"pytest", "jest", "test", "vitest"})
TEST_PATTERNS = ("npm run test", "npx test", "npm test", "bun test")

_HAS_KOREAN = re.compile(r"[\uac00-\ud7a3]")

# ── Work-log parser (extracts LLM summaries + tags) ─────────────────────────

_RE_SESSION_HEADER = re.compile(
    r"^##\s+세션\s+\d{1,2}:\d{2}(?:~\d{1,2}:\d{2})?\s+\(([0-9a-f]{8})"
)
_RE_SUMMARY = re.compile(r"^\*\*요약\*\*:\s*(?:\[([^\]]+)\]\s*)?(.+)$")
_RE_RESULT = re.compile(r"^\*\*결과\*\*:\s*(.+)$")
_RE_TOPIC = re.compile(r"^\*\*주제\*\*:\s*(.+)$")
_RE_DECISIONS = re.compile(r"^\*\*결정\*\*:\s*(.+)$")
_RE_MISTAKES = re.compile(r"^\*\*시행착오\*\*:\s*(.+)$")
_RE_PATTERNS = re.compile(r"^\*\*패턴\*\*:\s*(.+)$")

_SIGNAL_TYPE_MAP = {"decisions": "decision", "mistakes": "mistake", "patterns": "pattern"}


def _parse_work_log_summaries(date_str: str) -> dict[str, dict]:
    """Parse codex work-log markdown, return {session_id_prefix: {tag, summary}}."""
    md_path = CODEX_WORK_LOG_DIR / f"{date_str}.md"
    if not md_path.exists():
        return {}

    result: dict[str, dict] = {}
    current_sid = ""
    current_data: dict = {}

    for line in md_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        hdr = _RE_SESSION_HEADER.match(stripped)
        if hdr:
            if current_sid and current_data:
                result[current_sid] = current_data
            current_sid = hdr.group(1)
            current_data = {}
            continue

        if not current_sid:
            continue

        sm = _RE_SUMMARY.match(stripped)
        if sm:
            current_data["tag"] = sm.group(1) or ""
            current_data["summary"] = sm.group(2).strip()
            continue

        rm = _RE_RESULT.match(stripped)
        if rm and "summary" not in current_data:
            current_data["summary"] = rm.group(1).strip()
            continue

        tm = _RE_TOPIC.match(stripped)
        if tm and "summary" not in current_data:
            current_data["summary"] = tm.group(1).strip()
            continue

        # Behavioral signals (decisions/mistakes/patterns separated by " ; ")
        dm = _RE_DECISIONS.match(stripped)
        if dm:
            current_data.setdefault("decisions", []).extend(
                s.strip() for s in dm.group(1).split(" ; ") if s.strip()
            )
            continue
        mm = _RE_MISTAKES.match(stripped)
        if mm:
            current_data.setdefault("mistakes", []).extend(
                s.strip() for s in mm.group(1).split(" ; ") if s.strip()
            )
            continue
        pm = _RE_PATTERNS.match(stripped)
        if pm:
            current_data.setdefault("patterns", []).extend(
                s.strip() for s in pm.group(1).split(" ; ") if s.strip()
            )
            continue

    if current_sid and current_data:
        result[current_sid] = current_data

    return result


# ── JSONL parser (timestamps, tokens, files, agent messages) ─────────────────


_DISPATCH_PATTERNS = re.compile(
    r"^(You are |Code quality |Spec compliance |Implement Task |"
    r"Review |Fix |다음 세션 시작)",
    re.IGNORECASE,
)


def _first_sentence(text: str) -> str:
    """Extract first sentence (up to period, newline, or 120 chars)."""
    for delim in (".\n", ".\r", ". ", "\n\n", "\n"):
        idx = text.find(delim)
        if 0 < idx < 200:
            return text[: idx + 1].strip()
    return text[:120].strip()


def _pick_summary(agent_msgs: list[str], user_msgs: list[str]) -> str:
    """Pick the best summary from session messages.

    Priority:
    1. Korean agent message (agent describing work result in Korean)
    2. Korean user message (interactive session)
    3. Last agent message (likely contains work result)
    4. First sentence of user message (but skip dispatch prompts)
    """
    # Korean agent message = agent describing work result
    for msg in agent_msgs[:5]:
        if _HAS_KOREAN.search(msg) and not _DISPATCH_PATTERNS.match(msg):
            return _first_sentence(msg)

    # Korean user message = interactive session
    for msg in user_msgs[:3]:
        if _HAS_KOREAN.search(msg) and not _DISPATCH_PATTERNS.match(msg):
            return _first_sentence(msg)

    # Last agent message (more likely to contain result than first)
    for msg in reversed(agent_msgs[:5]):
        if not _DISPATCH_PATTERNS.match(msg):
            return _first_sentence(msg)

    # User message fallback (skip dispatch patterns)
    for msg in user_msgs[:3]:
        if not _DISPATCH_PATTERNS.match(msg):
            return _first_sentence(msg)

    # Final fallback
    if agent_msgs:
        return _first_sentence(agent_msgs[-1])

    return ""


def _parse_session(path: Path) -> dict | None:
    """Parse a single Codex JSONL session file into an activity dict."""
    lines = path.read_text().splitlines()
    if len(lines) < 5:
        return None

    session_id = ""
    cwd = ""
    model = ""
    user_msgs: list[str] = []
    agent_msgs: list[str] = []
    files_changed: set[str] = set()
    commands: list[str] = []
    errors: list[str] = []
    total_tokens = 0
    ts_first = ""
    ts_last = ""

    for line in lines:
        try:
            e = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        ts = e.get("timestamp", "")
        if ts and (not ts_first or ts < ts_first):
            ts_first = ts
        if ts and ts > ts_last:
            ts_last = ts

        etype = e.get("type", "")

        if etype == "session_meta":
            payload = e.get("payload") or {}
            session_id = payload.get("id", "") or path.stem
            cwd = payload.get("cwd", "")
            continue

        if etype == "turn_context":
            payload = e.get("payload") or {}
            if not model:
                model = payload.get("model", "")
            continue

        if etype == "event_msg":
            payload = e.get("payload") or {}
            msg_type = payload.get("type", "")
            if msg_type == "user_message":
                msg = payload.get("message", "").strip()
                if msg:
                    user_msgs.append(msg)
            elif msg_type == "agent_message":
                msg = payload.get("message", "").strip()
                if msg:
                    agent_msgs.append(msg)
            elif msg_type == "token_count":
                info = payload.get("info") or {}
                total = info.get("total_token_usage") or {}
                t = total.get("total_tokens", 0)
                if t > total_tokens:
                    total_tokens = t
            continue

        if etype == "response_item":
            payload = e.get("payload") or {}
            if payload.get("type") == "function_call":
                name = payload.get("name", "")
                if name in FILE_WRITE_NAMES:
                    try:
                        args = json.loads(payload.get("arguments", "{}"))
                        fpath = args.get("path", "") or args.get("file_path", "")
                        if fpath:
                            files_changed.add(fpath)
                    except (json.JSONDecodeError, ValueError):
                        pass
                elif name in COMMAND_NAMES:
                    try:
                        args = json.loads(payload.get("arguments", "{}"))
                        # exec_command uses "cmd", others use "command"
                        cmd = args.get("cmd") or args.get("command", [])
                        if isinstance(cmd, list) and len(cmd) >= 3 and cmd[1] == "-lc":
                            commands.append(str(cmd[2]))
                        elif isinstance(cmd, list):
                            commands.append(" ".join(str(c) for c in cmd))
                        elif isinstance(cmd, str) and cmd.strip():
                            commands.append(cmd.strip())
                    except (json.JSONDecodeError, ValueError):
                        pass
            elif payload.get("type") == "function_call_output":
                output = str(payload.get("output", ""))
                if "exit_code" in output:
                    exit_match = re.search(r"exit_code[\":\s]+(\d+)", output)
                    if exit_match and int(exit_match.group(1)) != 0:
                        errors.append(output[:200])

    if not session_id:
        return None

    repo = Path(cwd).name if cwd else "unknown"
    summary = _pick_summary(agent_msgs, user_msgs)
    # auto_tag: user_msgs + agent first sentences only (avoid code in messages)
    agent_first = [_first_sentence(m) for m in agent_msgs[:3]]
    tag = auto_tag(*user_msgs[:3], *agent_first)

    # branch detection from cwd
    branch = None
    if cwd:
        try:
            result = subprocess.run(
                ["git", "-C", cwd, "branch", "--show-current"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                branch = result.stdout.strip()
        except Exception:
            pass

    # has_tests / has_commits from commands
    # Skip read-only prefixes (sed, cat, rg, grep, head, tail, nl) to avoid
    # false positives like "sed ... test-driven-development/SKILL.md"
    _READ_PREFIXES = ("sed ", "cat ", "rg ", "grep ", "head ", "tail ", "nl ")
    has_tests = 0
    has_commits = 0
    for cmd in commands:
        cmd_lower = cmd.lower()
        if cmd_lower.startswith(_READ_PREFIXES):
            continue
        if not has_tests:
            if any(kw in cmd_lower for kw in TEST_KEYWORDS) or \
               any(pat in cmd_lower for pat in TEST_PATTERNS):
                has_tests = 1
        if not has_commits and "git commit" in cmd_lower:
            has_commits = 1

    start_at = None
    end_at = None
    duration_min = None
    if ts_first:
        try:
            dt_start = datetime.fromisoformat(ts_first.replace("Z", "+00:00")).astimezone(KST)
            start_at = dt_start.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    if ts_last:
        try:
            dt_end = datetime.fromisoformat(ts_last.replace("Z", "+00:00")).astimezone(KST)
            end_at = dt_end.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    if start_at and end_at:
        try:
            dt_s = datetime.strptime(start_at, "%Y-%m-%dT%H:%M:%S")
            dt_e = datetime.strptime(end_at, "%Y-%m-%dT%H:%M:%S")
            duration_min = max(1, int((dt_e - dt_s).total_seconds() / 60))
        except ValueError:
            pass

    return {
        "source": "codex",
        "session_id": session_id,
        "repo": repo,
        "branch": branch,
        "tag": tag,
        "summary": summary,
        "start_at": start_at,
        "end_at": end_at,
        "duration_min": duration_min,
        "file_count": len(files_changed),
        "error_count": len(errors),
        "has_tests": has_tests,
        "has_commits": has_commits,
        "token_total": total_tokens,
        "raw_json": json.dumps({
            "session_id": session_id,
            "cwd": cwd,
            "model": model,
            "user_messages": user_msgs[:10],
            "agent_messages": agent_msgs[:5],
            "files_changed": sorted(files_changed),
            "commands": commands[:10],
            "total_tokens": total_tokens,
        }, ensure_ascii=False),
    }


# ── Sync ─────────────────────────────────────────────────────────────────────


def sync_date(conn, date_str: str) -> int:
    """Sync all Codex sessions for a given date."""
    parts = date_str.split("-")
    session_dir = SESSION_ROOT / parts[0] / parts[1] / parts[2]
    if not session_dir.is_dir():
        return 0

    # Load LLM summaries from work-log (if session_logger ran)
    work_log = _parse_work_log_summaries(date_str)

    count = 0
    for jsonl_path in sorted(session_dir.glob("*.jsonl")):
        try:
            activity = _parse_session(jsonl_path)
            if not activity or not activity["start_at"]:
                continue

            # Overlay work-log data (LLM summary + tag) if available
            sid = activity["session_id"]
            sid_prefix = sid[:8]
            wl = work_log.get(sid_prefix)
            if wl:
                if wl.get("summary"):
                    summary = wl["summary"]
                    # Strip "User: " prefix from compaction-derived summaries
                    if summary.startswith("User: "):
                        summary = summary[6:]
                    activity["summary"] = summary
                if wl.get("tag") and wl["tag"] != "기타":
                    activity["tag"] = wl["tag"]

            upsert_activity(conn, activity)
            count += 1

            # Insert behavioral signals from work-log (if available)
            if wl:
                try:
                    for plural, singular in _SIGNAL_TYPE_MAP.items():
                        for content in wl.get(plural, []):
                            insert_behavioral_signal(conn, {
                                "session_id": sid,
                                "date": date_str,
                                "signal_type": singular,
                                "content": content,
                                "repo": activity.get("repo", ""),
                            })
                except Exception as e:
                    print(f"[sync_codex] failed to sync behavioral signals for {sid}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[sync_codex] failed to parse {jsonl_path.name}: {e}", file=sys.stderr)

    if count > 0:
        update_daily_stats(conn, date_str)

    return count


def main():
    parser = argparse.ArgumentParser(description="Sync Codex sessions to SQLite")
    parser.add_argument("--date", help="Sync specific date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=1, help="Sync last N days (default: 1)")
    args = parser.parse_args()

    conn = get_conn()
    try:
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
                print(f"[sync_codex] {date_str}: {count} sessions synced", file=sys.stderr)

        conn.commit()
        print(f"[sync_codex] Total: {total} sessions synced across {len(dates)} days", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
