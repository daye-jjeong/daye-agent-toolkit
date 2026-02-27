#!/usr/bin/env python3
"""
Health Tracker 메인 스크립트
대화형 인터페이스로 간편하게 사용 (Obsidian vault 기반)
"""

import sys
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def run(cmd):
    subprocess.run(cmd)


def print_menu():
    print("\n" + "=" * 50)
    print("  Health Tracker")
    print("=" * 50)
    print("\n1. 증상 기록 (허리디스크/메니에르병)")
    print("2. 운동 기록 (PT/수영/걷기)")
    print("3. PT 숙제 관리")
    print("4. PT 출석 체크")
    print("5. 건강 패턴 분석")
    print("6. 미완료 PT 숙제 보기")
    print("0. 종료")
    print("\n" + "=" * 50)


def log_symptom_interactive():
    print("\n증상 기록\n")
    print("증상 종류:")
    print("1. 허리디스크")
    print("2. 메니에르병")
    print("3. 기타")
    type_choice = input("선택 (1-3): ").strip()
    type_map = {"1": "허리디스크", "2": "메니에르병", "3": "기타"}
    symptom_type = type_map.get(type_choice, "기타")

    print("\n심각도:")
    print("1. 경증")
    print("2. 중등도")
    print("3. 심각")
    severity_choice = input("선택 (1-3): ").strip()
    severity_map = {"1": "경증", "2": "중등도", "3": "심각"}
    severity = severity_map.get(severity_choice, "경증")

    description = input("\n증상 상세 설명: ").strip()
    trigger = input("트리거 요인 (선택, Enter로 스킵): ").strip()
    duration = input("지속 시간 (선택, Enter로 스킵): ").strip()

    cmd = [
        "python3", str(SCRIPT_DIR / "log_symptom.py"),
        "--type", symptom_type,
        "--severity", severity,
        "--description", description,
    ]
    if trigger:
        cmd.extend(["--trigger", trigger])
    if duration:
        cmd.extend(["--duration", duration])
    run(cmd)


def log_exercise_interactive():
    print("\n운동 기록\n")
    print("운동 종류:")
    print("1. PT")
    print("2. 수영")
    print("3. 걷기")
    print("4. 기타")
    type_choice = input("선택 (1-4): ").strip()
    type_map = {"1": "PT", "2": "수영", "3": "걷기", "4": "기타"}
    exercise_type = type_map.get(type_choice, "기타")

    duration = input("\n운동 시간 (분): ").strip()
    if not duration.isdigit():
        print("[ERROR] 숫자를 입력하세요")
        return

    exercises = input("운동 상세 (선택, Enter로 스킵): ").strip()
    notes = input("메모 (선택, Enter로 스킵): ").strip()

    print("\n운동 후 느낌:")
    print("1. 좋았음")
    print("2. 보통")
    print("3. 힘들었음")
    print("4. 고통스러움")
    print("0. 선택 안 함")
    feeling_choice = input("선택 (0-4): ").strip()
    feeling_map = {"1": "좋았음", "2": "보통", "3": "힘들었음", "4": "고통스러움"}
    feeling = feeling_map.get(feeling_choice, "")

    cmd = [
        "python3", str(SCRIPT_DIR / "log_exercise.py"),
        "--type", exercise_type,
        "--duration", duration,
    ]
    if exercises:
        cmd.extend(["--exercises", exercises])
    if notes:
        cmd.extend(["--notes", notes])
    if feeling:
        cmd.extend(["--feeling", feeling])
    run(cmd)


def pt_homework_menu():
    print("\nPT 숙제 관리\n")
    print("1. 숙제 추가")
    print("2. 숙제 목록 보기")
    print("3. 숙제 완료 처리")
    print("0. 뒤로")
    choice = input("\n선택: ").strip()

    if choice == "1":
        exercise = input("운동 이름: ").strip()
        sets = input("세트 수: ").strip()
        reps = input("횟수 (또는 시간): ").strip()
        notes = input("주의사항 (선택, Enter로 스킵): ").strip()
        cmd = [
            "python3", str(SCRIPT_DIR / "log_pt_homework.py"), "add",
            "--exercise", exercise, "--sets", sets, "--reps", reps,
        ]
        if notes:
            cmd.extend(["--notes", notes])
        run(cmd)
    elif choice == "2":
        run(["python3", str(SCRIPT_DIR / "log_pt_homework.py"), "list"])
    elif choice == "3":
        run(["python3", str(SCRIPT_DIR / "log_pt_homework.py"), "list"])
        filename = input("\n파일 이름 (완료할 숙제의 .md): ").strip()
        if not filename:
            print("[ERROR] 파일 이름을 입력하세요")
            return
        run(["python3", str(SCRIPT_DIR / "log_pt_homework.py"),
             "complete", "--file", filename])


def main():
    while True:
        print_menu()
        choice = input("\n선택: ").strip()

        if choice == "1":
            log_symptom_interactive()
        elif choice == "2":
            log_exercise_interactive()
        elif choice == "3":
            pt_homework_menu()
        elif choice == "4":
            run(["python3", str(SCRIPT_DIR / "check_pt_attendance.py")])
        elif choice == "5":
            print("\n1. 주간 리포트")
            print("2. 월간 리포트")
            p = input("\n선택 (1-2): ").strip()
            period = "week" if p == "1" else "month"
            run(["python3", str(SCRIPT_DIR / "analyze_health.py"),
                 "--period", period])
        elif choice == "6":
            run(["python3", str(SCRIPT_DIR / "log_pt_homework.py"), "list"])
        elif choice == "0":
            print("\n건강하세요!")
            break
        else:
            print("\n[ERROR] 잘못된 선택입니다")

        input("\nEnter를 눌러 계속...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n건강하세요!")
        sys.exit(0)
