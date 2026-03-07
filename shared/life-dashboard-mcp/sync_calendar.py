#!/usr/bin/env python3
"""Calendar events -> SQLite sync via macOS EventKit (Swift).

Usage:
    python3 sync_calendar.py                    # today
    python3 sync_calendar.py --date 2026-03-07  # specific date
    python3 sync_calendar.py --days 7           # last 7 days
"""

import argparse
import hashlib
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn, upsert_activity, update_daily_stats

KST = timezone(timedelta(hours=9))
SWIFT_SCRIPT = Path(__file__).resolve().parent / "cal_events.swift"

TAG_MAP = {
    "건강": "운동",
    "daye@ronik.io": "업무미팅",
    "개인": "개인",
    "업무": "업무",
    "학습": "학습",
}


def make_session_id(date_str: str, title: str, start: str) -> str:
    raw = f"{date_str}_{title}_{start}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"cal_{h}"


def fetch_events(from_date: str, to_date: str) -> list[dict]:
    """Run Swift script and parse pipe-delimited output."""
    try:
        result = subprocess.run(
            ["swift", str(SWIFT_SCRIPT), "--from", from_date, "--to", to_date],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        print("[sync_calendar] swift not found", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print("[sync_calendar] swift script timed out", file=sys.stderr)
        return []

    if result.returncode != 0:
        print(f"[sync_calendar] swift error: {result.stderr.strip()}", file=sys.stderr)
        return []

    events = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) != 4:
            continue
        cal_name, title, start, end = parts
        events.append({
            "calendar": cal_name.strip(),
            "title": title.strip(),
            "start": start.strip(),
            "end": end.strip(),
        })
    return events


def calc_duration_min(start: str, end: str) -> int:
    fmt = "%Y-%m-%d %H:%M"
    try:
        s = datetime.strptime(start, fmt)
        e = datetime.strptime(end, fmt)
        return max(0, int((e - s).total_seconds() / 60))
    except ValueError:
        return 0


def sync_date(conn, date_str: str) -> int:
    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    events = fetch_events(date_str, next_date)
    count = 0

    for ev in events:
        session_id = make_session_id(date_str, ev["title"], ev["start"])
        tag = TAG_MAP.get(ev["calendar"], ev["calendar"])
        duration = calc_duration_min(ev["start"], ev["end"])

        # Convert "YYYY-MM-DD HH:MM" to "YYYY-MM-DDTHH:MM:00"
        start_at = ev["start"].replace(" ", "T") + ":00" if len(ev["start"]) == 16 else ev["start"]
        end_at = ev["end"].replace(" ", "T") + ":00" if len(ev["end"]) == 16 else ev["end"]

        activity = {
            "source": "calendar",
            "session_id": session_id,
            "repo": "[캘린더]",
            "tag": tag,
            "summary": ev["title"],
            "start_at": start_at,
            "end_at": end_at,
            "duration_min": duration,
            "file_count": 0,
            "error_count": 0,
            "has_tests": 0,
            "has_commits": 0,
            "token_total": 0,
            "raw_json": "",
        }
        upsert_activity(conn, activity)
        count += 1

    if count > 0:
        update_daily_stats(conn, date_str)

    return count


def main():
    parser = argparse.ArgumentParser(description="Sync calendar events to SQLite")
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
                print(f"[sync_calendar] {date_str}: {count} events synced", file=sys.stderr)

        conn.commit()
        print(f"[sync_calendar] Total: {total} events synced across {len(dates)} days", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
