#!/usr/bin/env python3
"""식사 기록 스크립트 — SQLite 저장."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, insert_meal

NUTRITION_DB_PATH = Path(__file__).parent.parent / "config" / "nutrition_db.json"


def load_nutrition_db():
    with open(NUTRITION_DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def estimate_nutrition(food_items, portion):
    nutrition_db = load_nutrition_db()
    total_cal = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    portion_multiplier = {"적음": 0.7, "보통": 1.0, "많음": 1.3}
    multiplier = portion_multiplier.get(portion, 1.0)

    for item in food_items:
        item = item.strip()
        found = False
        for category, foods in nutrition_db.items():
            for food_name, nutrition in foods.items():
                if food_name in item or item in food_name:
                    total_cal += nutrition['calories'] * multiplier
                    total_protein += nutrition['protein'] * multiplier
                    total_carbs += nutrition['carbs'] * multiplier
                    total_fat += nutrition['fat'] * multiplier
                    found = True
                    break
            if found:
                break

    return {
        "calories": round(total_cal),
        "protein": round(total_protein, 1),
        "carbs": round(total_carbs, 1),
        "fat": round(total_fat, 1),
    }


def log_meal(meal_type, food_items, portion, skipped, notes):
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H:%M")

    if skipped:
        data = {
            "date": today,
            "timestamp": timestamp,
            "meal_type": meal_type,
            "food_items": None,
            "portion": None,
            "skipped": 1,
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "notes": notes or "거름",
        }
        print(f"[!] {meal_type} 거름 - {notes or '기록됨'}")
    else:
        food_list = [f.strip() for f in food_items.split(',')]
        nutrition = estimate_nutrition(food_list, portion)
        data = {
            "date": today,
            "timestamp": timestamp,
            "meal_type": meal_type,
            "food_items": json.dumps(food_list, ensure_ascii=False),
            "portion": portion,
            "skipped": 0,
            "calories": nutrition["calories"],
            "protein_g": nutrition["protein"],
            "carbs_g": nutrition["carbs"],
            "fat_g": nutrition["fat"],
            "notes": notes or None,
        }
        print(f"[OK] {meal_type} 기록됨")
        print(f"   음식: {', '.join(food_list)}")
        print(f"   양: {portion}")
        print(f"   영양소: {nutrition['calories']}kcal, "
              f"단백질 {nutrition['protein']}g, "
              f"탄수화물 {nutrition['carbs']}g, "
              f"지방 {nutrition['fat']}g")

    conn = get_conn()
    try:
        insert_meal(conn, data)
        conn.commit()
    finally:
        conn.close()

    return data


def main():
    parser = argparse.ArgumentParser(description="식사 기록")
    parser.add_argument("--type", required=True, help="아침/점심/저녁/간식")
    parser.add_argument("--food", help="음식 목록 (쉼표로 구분)")
    parser.add_argument("--portion", default="보통", help="적음/보통/많음")
    parser.add_argument("--skipped", action="store_true", help="거른 식사")
    parser.add_argument("--notes", help="메모")
    args = parser.parse_args()

    valid_types = ["아침", "점심", "저녁", "간식"]
    if args.type not in valid_types:
        print(f"[ERROR] 잘못된 식사 유형: {args.type}")
        print(f"   사용 가능: {', '.join(valid_types)}")
        sys.exit(1)

    if not args.skipped and not args.food:
        print("[ERROR] 음식을 입력하거나 --skipped 플래그를 사용하세요")
        sys.exit(1)

    log_meal(args.type, args.food or "", args.portion, args.skipped, args.notes)


if __name__ == "__main__":
    main()
