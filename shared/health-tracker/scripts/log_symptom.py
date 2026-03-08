#!/usr/bin/env python3
"""증상 기록 스크립트 — SQLite 저장."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, insert_symptom


def log_symptom(symptom_type, severity, description, trigger="", duration="", status="진행중"):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%H:%M")

    data = {
        "date": date,
        "timestamp": timestamp,
        "type": symptom_type,
        "severity": severity,
        "description": description,
        "trigger_factor": trigger or None,
        "duration": duration or None,
        "status": status,
    }

    conn = get_conn()
    try:
        insert_symptom(conn, data)
        conn.commit()
    finally:
        conn.close()

    print(f"[OK] 증상 기록 완료: {symptom_type} ({severity})")


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
    log_symptom(args.type, args.severity, args.description, args.trigger, args.duration, args.status)


if __name__ == "__main__":
    main()
