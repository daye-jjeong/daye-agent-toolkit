#!/usr/bin/env python3
"""schedule_actual_link — actual 브리지 wrapper.

wrapper가 task에서 date/duration/summary/repo 자동 조회 → snapshot.
schedule identity (date, todo_id) 재검증.
UNIQUE 4-tuple 위반 거부.

Usage:
  schedule_actual_link.py
    --schedule-id N --task-id M
    --date YYYY-MM-DD --todo-id K
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "mcp" / "life-dashboard"))
from db import get_conn, link_schedule_actual, get_capacity_status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule-id", type=int, required=True)
    ap.add_argument("--task-id", type=int, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--todo-id", type=int, required=True)
    args = ap.parse_args()

    conn = get_conn()
    try:
        # schedule identity 재검증
        sch = conn.execute(
            "SELECT date, todo_id FROM todo_schedules WHERE id = ?", (args.schedule_id,)
        ).fetchone()
        if not sch:
            sys.exit(f"error: schedule_id {args.schedule_id} not found")
        if sch["date"] != args.date:
            sys.exit(f"error: schedule.date={sch['date']} vs --date {args.date} date mismatch")
        if sch["todo_id"] != args.todo_id:
            sys.exit(f"error: schedule.todo_id={sch['todo_id']} vs --todo-id {args.todo_id} todo mismatch")

        try:
            actual_id = link_schedule_actual(
                conn, schedule_id=args.schedule_id, task_id=args.task_id
            )
            conn.commit()
        except ValueError as e:
            sys.exit(f"error: {e}")
        except sqlite3.IntegrityError as e:
            sys.exit(f"error: actual constraint violation: {e}")

        actual = dict(conn.execute(
            "SELECT * FROM todo_schedule_actuals WHERE id = ?", (actual_id,)
        ).fetchone())
        result = {
            "actual": actual,
            "capacity_status": get_capacity_status(conn, args.date),
        }
        json.dump(result, sys.stdout, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
