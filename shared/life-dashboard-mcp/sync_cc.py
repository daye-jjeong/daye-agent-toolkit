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
from parse_work_log import parse_work_log

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn, upsert_activity, update_daily_stats

KST = timezone(timedelta(hours=9))


def sync_date(conn, date_str: str) -> int:
    data = parse_work_log(date_str)
    sessions = data.get("sessions", [])
    count = 0

    for s in sessions:
        session_id = s.get("session_id", "")
        if not session_id:
            continue

        time_str = s.get("time", "00:00")
        start_at = f"{date_str}T{time_str}:00"

        end_time = s.get("end_time")
        if end_time:
            end_at = f"{date_str}T{end_time}:00"
        elif s.get("duration_min"):
            start_dt = datetime.strptime(start_at, "%Y-%m-%dT%H:%M:%S")
            end_dt = start_dt + timedelta(minutes=s["duration_min"])
            end_at = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            end_at = None

        has_tests = 0
        has_commits = 0
        test_keywords = {"pytest", "jest", "test", "vitest"}
        for cmd in s.get("commands", []):
            cmd_lower = cmd.lower()
            if any(kw in cmd_lower for kw in test_keywords):
                has_tests = 1
            if "git commit" in cmd_lower:
                has_commits = 1

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
