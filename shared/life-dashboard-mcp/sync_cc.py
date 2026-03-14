#!/usr/bin/env python3
"""CC work-log -> SQLite sync.

Usage:
    python3 sync_cc.py                    # today
    python3 sync_cc.py --date 2026-03-07  # specific date
    python3 sync_cc.py --days 7           # last 7 days
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_WORK_DIGEST_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "cc" / "work-digest" / "scripts"
sys.path.insert(0, str(_WORK_DIGEST_SCRIPTS))
from parse_work_log import parse_work_log, TEST_KEYWORDS, TEST_PATTERNS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn, upsert_activity, update_daily_stats, insert_behavioral_signal
from _sync_common import auto_tag

KST = timezone(timedelta(hours=9))
_SIGNAL_TYPE_MAP = {"decisions": "decision", "mistakes": "mistake", "patterns": "pattern"}
_NON_WORK_PATTERNS = {"<command-name>/clear</command-name>", "/clear", "/compact"}


def _is_non_work_session(session: dict) -> bool:
    """실제 작업이 아닌 세션 판별 (/clear, /compact 등).

    topic이 /clear여도 파일 변경이나 충분한 duration이 있으면 실제 작업.
    """
    summary = session.get("summary", "").strip()
    topic = session.get("topic", "").strip()
    # 유의미한 summary가 있으면 실제 작업
    if summary and summary not in _NON_WORK_PATTERNS:
        return False
    # topic도 non-work 패턴이 아니면 실제 작업
    if topic not in _NON_WORK_PATTERNS:
        return False
    # Topic/summary matches non-work pattern, but check for actual work signals
    if session.get("file_count", 0) > 0:
        return False
    if (session.get("duration_min") or 0) >= 5:
        return False
    return True


def sync_date(conn, date_str: str) -> int:
    data = parse_work_log(date_str)
    sessions = data.get("sessions", [])
    count = 0

    for s in sessions:
        session_id = s.get("session_id", "")
        if not session_id:
            continue

        # /clear 등 실제 작업이 아닌 세션 필터링
        if _is_non_work_session(s):
            continue

        try:
            time_str = s.get("time", "00:00")
            start_at = f"{date_str}T{time_str}:00"

            end_time = s.get("end_time")
            if end_time:
                if end_time < time_str:  # midnight crossing
                    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    end_at = f"{next_day}T{end_time}:00"
                else:
                    end_at = f"{date_str}T{end_time}:00"
            elif s.get("duration_min"):
                start_dt = datetime.strptime(start_at, "%Y-%m-%dT%H:%M:%S")
                end_dt = start_dt + timedelta(minutes=s["duration_min"])
                end_at = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                end_at = None

            has_tests = 0
            has_commits = 1 if s.get("has_commits_meta") else 0
            for cmd in s.get("commands", []):
                cmd_lower = cmd.lower()
                if any(kw in cmd_lower for kw in TEST_KEYWORDS) or any(pat in cmd_lower for pat in TEST_PATTERNS):
                    has_tests = 1
                if not has_commits and "git commit" in cmd_lower:
                    has_commits = 1

            tokens = s.get("tokens") or {}
            token_total = sum(tokens.get(k, 0) for k in
                             ("Input", "Output", "Cache read", "Cache create"))

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

            try:
                for plural, singular in _SIGNAL_TYPE_MAP.items():
                    for content in s.get(plural, []):
                        insert_behavioral_signal(conn, {
                            "session_id": session_id,
                            "date": date_str,
                            "signal_type": singular,
                            "content": content,
                            "repo": s.get("repo", ""),
                        })
            except Exception as e:
                print(f"[sync_cc] failed to sync behavioral signals for {session_id}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[sync_cc] failed to sync session {session_id}: {e}", file=sys.stderr)

    if count > 0:
        update_daily_stats(conn, date_str)

    return count


def main():
    parser = argparse.ArgumentParser(description="Sync CC work-log to SQLite")
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
                print(f"[sync_cc] {date_str}: {count} sessions synced", file=sys.stderr)

        conn.commit()
        print(f"[sync_cc] Total: {total} sessions synced across {len(dates)} days", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
