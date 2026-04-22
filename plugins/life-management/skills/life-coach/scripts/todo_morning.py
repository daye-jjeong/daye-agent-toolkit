#!/usr/bin/env python3
"""아침 액션 — 오늘 우선순위 계산 + JSON 출력.

대화 없음. 사용자 input 안 받음.
Claude 세션이 stdout JSON을 읽고 대화형으로 사용자에게 제시.

Usage:
    python3 todo_morning.py --date YYYY-MM-DD
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "mcp" / "life-dashboard"))
from db import (
    get_conn, get_todos, get_overdue_todos, get_due_this_week_todos,
    get_pending_tasks,
)

KST = ZoneInfo("Asia/Seoul")


def _slim(t: dict) -> dict:
    """todo row → 출력용 축약."""
    return {
        "id": t["id"],
        "title": t["title"],
        "status": t["status"],
        "done_definition": t.get("done_definition"),
        "category": t.get("category"),
        "priority": t.get("priority"),
        "project_name": t.get("project_name"),
        "deadline": t.get("deadline"),
        "estimated_min": t.get("estimated_min"),
        "quarter": t.get("quarter"),
    }


def build_morning(conn, date: str) -> dict:
    overdue = [_slim(t) for t in get_overdue_todos(conn, as_of_date=date)]

    today_rows = conn.execute("""
        SELECT t.*, p.name as project_name
        FROM todos t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.deadline IS NOT NULL
          AND DATE(t.deadline) = DATE(?)
          AND t.status NOT IN ('done', 'deferred')
        ORDER BY CASE WHEN t.priority IS NULL THEN 99 ELSE t.priority END ASC
    """, (date,)).fetchall()
    today_due = [_slim(dict(r)) for r in today_rows]

    this_week = [_slim(t) for t in get_due_this_week_todos(conn, as_of_date=date)]
    current_wip = [_slim(t) for t in get_todos(conn, status="wip")]
    backlog_top5 = [_slim(t) for t in get_todos(conn, status="backlog", sort="default")[:5]]

    pending_rows = get_pending_tasks(conn)[:5]
    pending_suggestions = [
        {
            "id": r["id"],
            "description": r["description"],
            "suggested_date": r["suggested_date"],
            "source_type": r["source_type"],
            "estimated_min": r.get("estimated_min"),
        }
        for r in pending_rows
    ]

    return {
        "date": date,
        "overdue": overdue,
        "today_due": today_due,
        "this_week_due": this_week,
        "current_wip": current_wip,
        "backlog_top5": backlog_top5,
        "pending_suggestions": pending_suggestions,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"),
                    help="기준 날짜 (KST). 기본: 오늘")
    args = ap.parse_args()

    conn = get_conn()
    try:
        result = build_morning(conn, args.date)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
