#!/usr/bin/env python3
"""운동 기록 스크립트 — SQLite 저장."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, insert_exercise


def log_exercise(exercise_type, duration, exercises="", notes="", feeling=""):
    date = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H:%M")

    data = {
        "date": date,
        "timestamp": timestamp,
        "type": exercise_type,
        "duration_min": int(duration),
        "exercises": exercises or None,
        "feeling": feeling or None,
        "notes": notes or None,
    }

    conn = get_conn()
    try:
        insert_exercise(conn, data)
        conn.commit()
    finally:
        conn.close()

    print(f"[OK] 운동 기록 완료: {exercise_type} ({duration}분)")


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
    log_exercise(args.type, args.duration, args.exercises, args.notes, args.feeling)


if __name__ == "__main__":
    main()
