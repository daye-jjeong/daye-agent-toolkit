#!/usr/bin/env python3
"""Health Tracker — 통합 기록 스크립트.

Usage:
    log.py exercise --type PT --duration 60 --exercises "플랭크, 데드버그" --feeling 좋았음
    log.py exercise --type PT --duration 60 --homework "플랭크 3세트, 버드독 10회"
    log.py symptom --type 허리디스크 --severity 중등도 --description "왼쪽 통증"
    log.py meal --type 점심 --food "삼겹살, 된장찌개" --portion 보통
    log.py meal --type 저녁 --skipped --notes "입맛 없음"
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "mcp" / "life-dashboard"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, insert_exercise, insert_symptom, insert_meal

NUTRITION_DB_PATH = Path(__file__).parent.parent / "config" / "nutrition_db.json"


# ── exercise ─────────────────────────────────────────────────

def cmd_exercise(args):
    now = datetime.now()
    data = {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.strftime("%H:%M"),
        "type": args.type,
        "duration_min": args.duration,
        "exercises": args.exercises or None,
        "feeling": args.feeling or None,
        "notes": args.notes or None,
    }

    conn = get_conn()
    try:
        insert_exercise(conn, data)
        conn.commit()
        print(f"[OK] 운동 기록: {args.type} ({args.duration}분)")

        if args.homework:
            _save_homework(conn, now, args.homework)

    finally:
        conn.close()


def _save_homework(conn, now, homework_str):
    """PT 숙제를 exercise 테이블에 homework 타입으로 저장."""
    items = [h.strip() for h in homework_str.split(",") if h.strip()]
    date_str = now.strftime("%Y-%m-%d")
    for item in items:
        conn.execute("""
            INSERT INTO health_exercises (date, timestamp, type, duration_min, exercises, notes)
            VALUES (?, ?, 'PT숙제-할일', 0, ?, '자동 등록')
            ON CONFLICT(date, timestamp, type) DO NOTHING
        """, (date_str, now.strftime("%H:%M:%S-") + item[:10], item))
    conn.commit()
    print(f"[OK] 숙제 {len(items)}개 등록: {', '.join(items)}")


# ── symptom ──────────────────────────────────────────────────

def cmd_symptom(args):
    now = datetime.now()
    data = {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.strftime("%H:%M"),
        "type": args.type,
        "severity": args.severity,
        "description": args.description or None,
        "trigger_factor": args.trigger or None,
        "duration": args.duration_time or None,
        "status": "active",
    }

    conn = get_conn()
    try:
        insert_symptom(conn, data)
        conn.commit()
    finally:
        conn.close()

    print(f"[OK] 증상 기록: {args.type} ({args.severity})")
    if args.description:
        print(f"     {args.description}")


# ── meal ─────────────────────────────────────────────────────

def cmd_meal(args):
    now = datetime.now()

    if args.skipped:
        data = {
            "date": now.strftime("%Y-%m-%d"),
            "timestamp": now.strftime("%H:%M"),
            "meal_type": args.type,
            "food_items": None,
            "portion": None,
            "skipped": 1,
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "notes": args.notes or "거름",
        }
        print(f"[OK] {args.type} 거름")
    else:
        food_list = [f.strip() for f in args.food.split(",")]
        nutrition = _estimate_nutrition(food_list, args.portion)
        data = {
            "date": now.strftime("%Y-%m-%d"),
            "timestamp": now.strftime("%H:%M"),
            "meal_type": args.type,
            "food_items": json.dumps(food_list, ensure_ascii=False),
            "portion": args.portion,
            "skipped": 0,
            "calories": nutrition["calories"],
            "protein_g": nutrition["protein"],
            "carbs_g": nutrition["carbs"],
            "fat_g": nutrition["fat"],
            "notes": args.notes or None,
        }
        print(f"[OK] {args.type} 기록: {', '.join(food_list)}")
        print(f"     {nutrition['calories']}kcal / "
              f"단 {nutrition['protein']}g / "
              f"탄 {nutrition['carbs']}g / "
              f"지 {nutrition['fat']}g")

    conn = get_conn()
    try:
        insert_meal(conn, data)
        conn.commit()
    finally:
        conn.close()


def _estimate_nutrition(food_items, portion):
    try:
        with open(NUTRITION_DB_PATH, "r", encoding="utf-8") as f:
            nutrition_db = json.load(f)
    except FileNotFoundError:
        return {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}

    multiplier = {"적음": 0.7, "보통": 1.0, "많음": 1.3}.get(portion, 1.0)
    totals = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}

    for item in food_items:
        item = item.strip()
        for foods in nutrition_db.values():
            for food_name, nutr in foods.items():
                if food_name in item or item in food_name:
                    totals["calories"] += nutr["calories"] * multiplier
                    totals["protein"] += nutr["protein"] * multiplier
                    totals["carbs"] += nutr["carbs"] * multiplier
                    totals["fat"] += nutr["fat"] * multiplier
                    break
            else:
                continue
            break

    return {k: round(v, 1) if k != "calories" else round(v) for k, v in totals.items()}


# ── CLI ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Health Tracker 기록")
    sub = parser.add_subparsers(dest="command")

    # exercise
    ex = sub.add_parser("exercise", help="운동 기록")
    ex.add_argument("--type", required=True, help="PT/수영/걷기/홈트/기타")
    ex.add_argument("--duration", required=True, type=int, help="운동 시간 (분)")
    ex.add_argument("--exercises", default="", help="운동 상세")
    ex.add_argument("--feeling", default="", help="좋았음/보통/힘들었음/고통스러움")
    ex.add_argument("--notes", default="", help="메모")
    ex.add_argument("--homework", default="", help="PT 숙제 (쉼표 구분)")

    # symptom
    sy = sub.add_parser("symptom", help="증상 기록")
    sy.add_argument("--type", required=True, help="허리디스크/메니에르병/기타")
    sy.add_argument("--severity", required=True, help="경증/중등도/심각")
    sy.add_argument("--description", default="", help="증상 설명")
    sy.add_argument("--trigger", default="", help="트리거 요인")
    sy.add_argument("--duration-time", default="", help="지속 시간")

    # meal
    ml = sub.add_parser("meal", help="식사 기록")
    ml.add_argument("--type", required=True, help="아침/점심/저녁/간식")
    ml.add_argument("--food", default="", help="음식 (쉼표 구분)")
    ml.add_argument("--portion", default="보통", help="적음/보통/많음")
    ml.add_argument("--skipped", action="store_true", help="거른 식사")
    ml.add_argument("--notes", default="", help="메모")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "meal" and not args.skipped and not args.food:
        print("[ERROR] --food 또는 --skipped 필요")
        sys.exit(1)

    {"exercise": cmd_exercise, "symptom": cmd_symptom, "meal": cmd_meal}[args.command](args)


if __name__ == "__main__":
    main()
