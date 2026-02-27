#!/usr/bin/env python3
"""
PT 출석 체크 스크립트
최근 운동 기록에서 PT 출석 현황을 분석하고 리포트.
Google Calendar 의존 제거 -- exercise 로그 기반으로 동작.
"""

import sys
import argparse
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_io import read_entries, today


def check_attendance(days=7):
    """최근 N일 PT 출석 현황 확인"""
    entries = read_entries("exercises", days=days)
    pt_entries = [(f, fm) for f, fm in entries if fm.get("type") == "PT"]

    print(f"PT 출석 체크 (최근 {days}일)\n{'='*40}\n")

    if not pt_entries:
        print(f"[!] 최근 {days}일 PT 기록 없음")
        print("    PT 주 2회 목표를 유지하세요!\n")
        return

    # 날짜별 정리
    by_date = defaultdict(list)
    for fpath, fm in pt_entries:
        d = str(fm.get("date", ""))
        dur = fm.get("duration_min", "?")
        by_date[d].append(dur)

    print(f"PT 출석: {len(pt_entries)}회 ({len(by_date)}일)\n")
    for d in sorted(by_date.keys()):
        sessions = by_date[d]
        total = sum(s for s in sessions if isinstance(s, (int, float)))
        print(f"  {d}: {len(sessions)}회 ({total}분)")

    print()

    # 주 2회 목표 체크
    if days <= 7:
        target = 2
    else:
        target = (days // 7) * 2

    if len(pt_entries) >= target:
        print(f"[OK] 목표 달성! ({len(pt_entries)}/{target}회)")
    else:
        print(f"[!] 목표 미달 ({len(pt_entries)}/{target}회)")
        print("    PT 출석률을 높여보세요!")

    # 오늘 PT 여부
    todays = [fm for _, fm in pt_entries if str(fm.get("date", "")) == today()]
    if todays:
        print(f"\n[OK] 오늘 PT 기록 있음")
    else:
        print(f"\n[i] 오늘 PT 기록 없음")


def main():
    parser = argparse.ArgumentParser(description="PT 출석 체크")
    parser.add_argument("--days", type=int, default=7,
                        help="확인할 기간 (일, 기본: 7)")
    args = parser.parse_args()
    check_attendance(args.days)


if __name__ == "__main__":
    main()
