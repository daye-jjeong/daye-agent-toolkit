#!/usr/bin/env python3
"""capacity — 누적 캐파 조회 + 4종 flag.

Usage:
  capacity.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]

기본: 최근 7일.
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "mcp" / "life-dashboard"))
from db import get_conn, get_daily_checkins, get_capacity_status

KST = ZoneInfo("Asia/Seoul")


def _fmt_h(minutes: int | None) -> str:
    if minutes is None:
        return "-"
    return f"{minutes / 60:.1f}h" if minutes else "0h"


def _status_str(st: dict) -> str:
    flags = []
    if st["available_status"] == "skipped":
        return "ℹ skipped"
    if st["missing_budget"]:
        flags.append("⚠ missing_budget")
    if st["planned_overbook"]:
        flags.append("⚠ planned_overbook")
    if st["actual_overrun"]:
        flags.append("⚠ actual_overrun")
    if st["time_conflicts"]:
        flags.append(f"⚠ time_conflicts({len(st['time_conflicts'])})")
    return ", ".join(flags) or "OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start")
    ap.add_argument("--end")
    args = ap.parse_args()

    today = datetime.now(KST).date()
    if not args.end:
        args.end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if not args.start:
        args.start = (today - timedelta(days=6)).strftime("%Y-%m-%d")

    conn = get_conn()
    try:
        rows = get_daily_checkins(conn, args.start, args.end)
        if not rows:
            print(f"(no daily_checkins in {args.start} ~ {args.end})")
            return

        print("| 날짜 | 가용 | 계획 | 실측 | 잔여 | 에너지 | 블로커 | 상태 |")
        print("|------|------|------|------|------|--------|--------|------|")
        for r in rows:
            st = get_capacity_status(conn, r["date"])
            avail = "(skipped)" if r["available_status"] == "skipped" else _fmt_h(r["available_min"])
            energy = r["energy"] or ("(skipped)" if r["energy_status"] == "skipped" else "-")
            blockers = (r["blockers"] or "")[:20] if r["blockers"] else ("(skipped)" if r["blockers_status"] == "skipped" else "-")
            print(f"| {r['date'][5:]} | {avail} | {_fmt_h(st['planned_min_total'])} | {_fmt_h(st['actual_min_total'])} | {_fmt_h(st['remaining_min'])} | {energy} | {blockers} | {_status_str(st)} |")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
