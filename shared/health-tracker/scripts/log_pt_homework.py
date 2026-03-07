#!/usr/bin/env python3
"""PT 숙제 트래킹 — SQLite 기반."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, insert_pt_homework, update_pt_homework, query_pt_homework


def add_homework(exercise, sets_reps, notes=""):
    date = datetime.now().strftime("%Y-%m-%d")
    data = {
        "exercise": exercise,
        "sets_reps": sets_reps,
        "notes": notes or None,
        "status": "할 일",
        "assigned_date": date,
    }
    conn = get_conn()
    try:
        insert_pt_homework(conn, data)
        conn.commit()
    finally:
        conn.close()
    print(f"[OK] PT 숙제 추가: {exercise} ({sets_reps})")


def list_homework():
    conn = get_conn()
    try:
        pending = [h for h in query_pt_homework(conn) if h["status"] in ("할 일", "진행중")]
    finally:
        conn.close()
    if not pending:
        print("[OK] 완료해야 할 숙제가 없어요!")
        return
    print(f"\nPT 숙제 목록 ({len(pending)}개):\n")
    for i, h in enumerate(pending, 1):
        print(f"{i}. {h['exercise']} - {h.get('sets_reps', '')}")
        print(f"   받은 날짜: {h['assigned_date']} | 상태: {h['status']}")
        print(f"   ID: {h['id']}\n")


def complete_homework(hw_id):
    date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        update_pt_homework(conn, hw_id, {"status": "완료", "completed_date": date})
        conn.commit()
    finally:
        conn.close()
    print(f"[OK] 숙제 완료: ID {hw_id}")


def main():
    parser = argparse.ArgumentParser(description="PT 숙제 관리")
    sub = parser.add_subparsers(dest="command", help="명령")
    ap = sub.add_parser("add", help="숙제 추가")
    ap.add_argument("--exercise", required=True, help="운동 이름")
    ap.add_argument("--sets", required=True, help="세트 수")
    ap.add_argument("--reps", required=True, help="횟수 (또는 시간)")
    ap.add_argument("--notes", default="", help="주의사항")
    sub.add_parser("list", help="미완료 숙제 목록")
    cp = sub.add_parser("complete", help="숙제 완료")
    cp.add_argument("--id", required=True, type=int, help="숙제 ID")
    args = parser.parse_args()

    if args.command == "add":
        add_homework(args.exercise, f"{args.sets}세트 x {args.reps}", args.notes)
    elif args.command == "list":
        list_homework()
    elif args.command == "complete":
        complete_homework(args.id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
