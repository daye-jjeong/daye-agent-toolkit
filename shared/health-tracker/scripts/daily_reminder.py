#!/usr/bin/env python3
"""
일일 알림 스크립트
- homework: 미완료 PT 숙제 표시
- exercise: 오늘 운동 기록 유무 확인
Obsidian vault 기반, 콘솔 출력.
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_io import read_entries, today


def homework_reminder():
    """미완료 PT 숙제 출력"""
    print("PT 숙제 알림\n")
    entries = read_entries("pt-homework")
    pending = [(f, fm) for f, fm in entries
               if fm.get("status") in ("할 일", "진행중")]

    if not pending:
        print("[OK] 미완료 숙제 없음")
        return

    print(f"미완료 숙제 {len(pending)}개:\n")
    for idx, (fpath, fm) in enumerate(pending, 1):
        exercise = fm.get("exercise", "?")
        sets_reps = fm.get("sets_reps", "")
        assigned = fm.get("date", "")
        print(f"  {idx}. {exercise} - {sets_reps} (받은 날짜: {assigned})")
    print()


def exercise_check():
    """오늘 운동 기록 확인"""
    print("오늘 운동 체크\n")
    date = today()
    entries = read_entries("exercises", days=1)
    todays = [(f, fm) for f, fm in entries if str(fm.get("date", "")) == date]

    if todays:
        print(f"[OK] 오늘 운동 {len(todays)}개 기록됨:\n")
        for _, fm in todays:
            ex_type = fm.get("type", "운동")
            dur = fm.get("duration_min", "?")
            print(f"  - {ex_type} ({dur}분)")
        print()
    else:
        print("[!] 오늘 운동 기록 없음")
        print("    간단한 걷기라도 하면 좋을 것 같아요!\n")


def main():
    parser = argparse.ArgumentParser(description="일일 알림")
    parser.add_argument("--type", required=True,
                        choices=["homework", "exercise"],
                        help="알림 종류")
    args = parser.parse_args()

    if args.type == "homework":
        homework_reminder()
    elif args.type == "exercise":
        exercise_check()


if __name__ == "__main__":
    main()
