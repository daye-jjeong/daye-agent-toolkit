#!/usr/bin/env python3
"""일일 알림 스크립트 — SQLite 기반."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, query_pt_homework, query_exercises


def homework_reminder():
    print("PT 숙제 알림\n")
    conn = get_conn()
    try:
        pending_todo = query_pt_homework(conn, status="할 일")
        pending_wip = query_pt_homework(conn, status="진행중")
    finally:
        conn.close()
    pending = pending_todo + pending_wip

    if not pending:
        print("[OK] 미완료 숙제 없음")
        return

    print(f"미완료 숙제 {len(pending)}개:\n")
    for idx, h in enumerate(pending, 1):
        print(f"  {idx}. {h['exercise']} - {h.get('sets_reps', '')} (받은 날짜: {h['assigned_date']})")
    print()


def exercise_check():
    print("오늘 운동 체크\n")
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        todays = query_exercises(conn, today, today)
    finally:
        conn.close()

    if todays:
        print(f"[OK] 오늘 운동 {len(todays)}개 기록됨:\n")
        for e in todays:
            print(f"  - {e['type']} ({e['duration_min']}분)")
        print()
    else:
        print("[!] 오늘 운동 기록 없음")
        print("    간단한 걷기라도 하면 좋을 것 같아요!\n")


def main():
    parser = argparse.ArgumentParser(description="일일 알림")
    parser.add_argument("--type", required=True, choices=["homework", "exercise"], help="알림 종류")
    args = parser.parse_args()

    if args.type == "homework":
        homework_reminder()
    elif args.type == "exercise":
        exercise_check()


if __name__ == "__main__":
    main()
