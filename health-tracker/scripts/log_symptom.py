#!/usr/bin/env python3
"""
증상 기록 스크립트
허리디스크/메니에르병 증상 발생 시 Obsidian vault에 기록
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_io import write_entry, sanitize, today, now


def log_symptom(symptom_type, severity, description, trigger="", duration="", status="진행중"):
    """증상을 Obsidian vault에 기록"""
    date = today()
    timestamp = now()
    filename = f"{date}_{sanitize(symptom_type)}.md"

    frontmatter = {
        "date": date,
        "timestamp": timestamp,
        "type": symptom_type,
        "severity": severity,
        "status": status,
    }
    if trigger:
        frontmatter["trigger"] = trigger
    if duration:
        frontmatter["duration"] = duration

    body = f"## {symptom_type} - {date}\n\n{description}"

    fpath = write_entry("symptoms", filename, frontmatter, body)
    print(f"[OK] 증상 기록 완료: {symptom_type} ({severity})")
    print(f"     파일: {fpath}")
    return fpath


def main():
    parser = argparse.ArgumentParser(description="건강 증상 기록")
    parser.add_argument("--type", required=True,
                        choices=["허리디스크", "메니에르병", "기타"],
                        help="증상 종류")
    parser.add_argument("--severity", required=True,
                        choices=["경증", "중등도", "심각"],
                        help="심각도")
    parser.add_argument("--description", required=True, help="증상 상세 설명")
    parser.add_argument("--trigger", default="", help="트리거 요인 (선택)")
    parser.add_argument("--duration", default="", help="지속 시간 (선택)")
    parser.add_argument("--status", default="진행중",
                        choices=["진행중", "완화", "완료"],
                        help="상태 (기본: 진행중)")

    args = parser.parse_args()

    log_symptom(
        args.type,
        args.severity,
        args.description,
        args.trigger,
        args.duration,
        args.status,
    )


if __name__ == "__main__":
    main()
