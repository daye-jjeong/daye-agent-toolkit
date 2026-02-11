#!/usr/bin/env python3
"""PT 숙제 트래킹 -- Obsidian vault 기반"""

import sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_io import write_entry, read_entries, update_entry, sanitize, today, CATEGORIES


def add_homework(exercise, sets_reps, notes=""):
    date = today()
    filename = f"{date}_{sanitize(exercise)}.md"
    fm = {"date": date, "exercise": exercise, "sets_reps": sets_reps,
          "status": "할 일", "completed": False}
    body = f"## 주의사항\n\n{notes}" if notes else ""
    fpath = write_entry("pt-homework", filename, fm, body)
    print(f"[OK] PT 숙제 추가: {exercise} ({sets_reps})")
    print(f"     파일: {fpath}")


def list_homework():
    entries = read_entries("pt-homework")
    pending = [(f, fm) for f, fm in entries if fm.get("status") in ("할 일", "진행중")]
    if not pending:
        print("[OK] 완료해야 할 숙제가 없어요!")
        return
    print(f"\nPT 숙제 목록 ({len(pending)}개):\n")
    for i, (fp, fm) in enumerate(pending, 1):
        print(f"{i}. {fm.get('exercise','?')} - {fm.get('sets_reps','')}")
        print(f"   받은 날짜: {fm.get('date','')} | 상태: {fm.get('status','')}")
        print(f"   파일: {fp.name}\n")


def complete_homework(filename):
    fpath = CATEGORIES["pt-homework"] / filename
    if not fpath.exists():
        print(f"[ERROR] 파일을 찾을 수 없음: {filename}")
        return False
    update_entry(fpath, {"status": "완료", "completed": True, "completed_date": today()})
    print(f"[OK] 숙제 완료: {filename}")
    return True


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
    cp.add_argument("--file", required=True, help="파일 이름 (.md)")
    args = parser.parse_args()

    if args.command == "add":
        add_homework(args.exercise, f"{args.sets}세트 x {args.reps}", args.notes)
    elif args.command == "list":
        list_homework()
    elif args.command == "complete":
        complete_homework(args.file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
