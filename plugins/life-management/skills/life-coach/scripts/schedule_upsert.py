#!/usr/bin/env python3
"""schedule_upsert — todo_schedule wrapper.

planned_min 자동 계산 (시간 슬롯이면 end-start).
Partial UNIQUE 위반 거부.
응답에 capacity_status 항상 포함.

Usage:
  schedule_upsert.py --todo-id N --date YYYY-MM-DD
    [--start HH:MM --end HH:MM]
    [--planned-min N]
    [--notes TEXT]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "mcp" / "life-dashboard"))
from db import get_conn, upsert_schedule, get_schedule, get_capacity_status


def _hhmm_to_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--todo-id", type=int, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--start", dest="start_at")
    ap.add_argument("--end", dest="end_at")
    ap.add_argument("--planned-min", type=int)
    ap.add_argument("--notes")
    args = ap.parse_args()

    if (args.start_at is None) != (args.end_at is None):
        sys.exit("error: --start and --end must be paired")

    if args.start_at:
        # auto-calc planned_min if not given
        calc = _hhmm_to_min(args.end_at) - _hhmm_to_min(args.start_at)
        if args.planned_min is None:
            args.planned_min = calc
        elif args.planned_min != calc:
            sys.exit(f"error: planned_min={args.planned_min} != end-start={calc}")
    else:
        if args.planned_min is None:
            sys.exit("error: --planned-min required when no time slot")

    conn = get_conn()
    try:
        try:
            sid = upsert_schedule(
                conn, todo_id=args.todo_id, date=args.date,
                start_at=args.start_at, end_at=args.end_at,
                planned_min=args.planned_min, notes=args.notes,
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            sys.exit(f"error: schedule constraint violation: {e}")

        result = {
            "schedule": get_schedule(conn, sid),
            "capacity_status": get_capacity_status(conn, args.date),
        }
        json.dump(result, sys.stdout, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
