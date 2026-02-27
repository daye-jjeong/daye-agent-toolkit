#!/usr/bin/env python3
"""
운동 기록 스크립트
PT/수영/걷기 등 운동 기록을 Obsidian vault에 저장
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_io import write_entry, sanitize, today, now


def log_exercise(exercise_type, duration, exercises="", notes="", feeling=""):
    """운동 기록을 Obsidian vault에 저장"""
    date = today()
    timestamp = now()
    filename = f"{date}_{sanitize(exercise_type)}.md"

    frontmatter = {
        "date": date,
        "timestamp": timestamp,
        "type": exercise_type,
        "duration_min": int(duration),
    }
    if exercises:
        frontmatter["exercises"] = exercises
    if feeling:
        frontmatter["feeling"] = feeling

    body = ""
    if notes:
        body = f"## 메모\n\n{notes}"

    fpath = write_entry("exercises", filename, frontmatter, body)
    print(f"[OK] 운동 기록 완료: {exercise_type} ({duration}분)")
    print(f"     파일: {fpath}")
    return fpath


def main():
    parser = argparse.ArgumentParser(description="운동 기록")
    parser.add_argument("--type", required=True,
                        choices=["PT", "수영", "걷기", "기타"],
                        help="운동 종류")
    parser.add_argument("--duration", required=True, type=int,
                        help="운동 시간 (분)")
    parser.add_argument("--exercises", default="",
                        help="운동 상세 (예: 플랭크 3세트, 데드버그 10회)")
    parser.add_argument("--notes", default="", help="메모")
    parser.add_argument("--feeling", default="",
                        choices=["", "좋았음", "보통", "힘들었음", "고통스러움"],
                        help="운동 후 느낌")

    args = parser.parse_args()

    log_exercise(
        args.type,
        args.duration,
        args.exercises,
        args.notes,
        args.feeling,
    )


if __name__ == "__main__":
    main()
