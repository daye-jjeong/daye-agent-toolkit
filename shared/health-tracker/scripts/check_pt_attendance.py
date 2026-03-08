#!/usr/bin/env python3
"""PT 출석 체크 스크립트 — SQLite 기반."""

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, query_exercises


def check_attendance(days=7):
    today = datetime.now().strftime("%Y-%m-%d")
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_conn()
    try:
        pt_entries = query_exercises(conn, since, today, ex_type="PT")
    finally:
        conn.close()

    print(f"PT 출석 체크 (최근 {days}일)\n{'='*40}\n")

    if not pt_entries:
        print(f"[!] 최근 {days}일 PT 기록 없음")
        print("    PT 주 2회 목표를 유지하세요!\n")
        return

    by_date = defaultdict(list)
    for e in pt_entries:
        by_date[e["date"]].append(e["duration_min"])

    print(f"PT 출석: {len(pt_entries)}회 ({len(by_date)}일)\n")
    for d in sorted(by_date.keys()):
        sessions = by_date[d]
        total = sum(s for s in sessions if isinstance(s, (int, float)))
        print(f"  {d}: {len(sessions)}회 ({total}분)")

    print()
    target = 2 if days <= 7 else (days // 7) * 2

    if len(pt_entries) >= target:
        print(f"[OK] 목표 달성! ({len(pt_entries)}/{target}회)")
    else:
        print(f"[!] 목표 미달 ({len(pt_entries)}/{target}회)")
        print("    PT 출석률을 높여보세요!")

    todays = [e for e in pt_entries if e["date"] == today]
    if todays:
        print(f"\n[OK] 오늘 PT 기록 있음")
    else:
        print(f"\n[i] 오늘 PT 기록 없음")


def main():
    parser = argparse.ArgumentParser(description="PT 출석 체크")
    parser.add_argument("--days", type=int, default=7, help="확인할 기간 (일, 기본: 7)")
    args = parser.parse_args()
    check_attendance(args.days)


if __name__ == "__main__":
    main()
