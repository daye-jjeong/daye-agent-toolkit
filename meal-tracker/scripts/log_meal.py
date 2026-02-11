#!/usr/bin/env python3
"""
Meal Tracker - 식사 기록 스크립트 (Obsidian vault 저장)

Usage:
    # 정상 식사
    python3 log_meal.py --type "점심" --food "삼겹살, 쌈채소, 된장찌개" --portion "보통"

    # 거른 식사
    python3 log_meal.py --type "저녁" --skipped --notes "입맛 없어서 건너뜀"
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# meals_io 임포트 (같은 디렉토리)
sys.path.insert(0, str(Path(__file__).parent))
import meals_io

NUTRITION_DB_PATH = Path(__file__).parent.parent / "config" / "nutrition_db.json"


def load_nutrition_db():
    """영양소 DB 로드"""
    with open(NUTRITION_DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def estimate_nutrition(food_items, portion):
    """음식 목록으로 영양소 추정"""
    nutrition_db = load_nutrition_db()

    total_cal = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0

    # 양에 따른 계수
    portion_multiplier = {
        "적음": 0.7,
        "보통": 1.0,
        "많음": 1.3
    }
    multiplier = portion_multiplier.get(portion, 1.0)

    for item in food_items:
        item = item.strip()
        found = False

        # 모든 카테고리에서 검색
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
        "fat": round(total_fat, 1)
    }


def log_meal(meal_type, food_items, portion, skipped, notes):
    """Obsidian vault에 식사 기록 저장"""
    now_str = meals_io.now()
    today_str = meals_io.today()
    timestamp = datetime.now().strftime("%H%M")

    if skipped:
        # 거른 식사
        frontmatter = {
            "date": today_str,
            "time": now_str,
            "type": "meal",
            "meal_type": meal_type,
            "skipped": True,
            "notes": notes or "거름",
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
        }
        print(f"[!] {meal_type} 거름 - {notes or '기록됨'}")
    else:
        # 정상 식사
        food_list = [f.strip() for f in food_items.split(',')]
        nutrition = estimate_nutrition(food_list, portion)

        frontmatter = {
            "date": today_str,
            "time": now_str,
            "type": "meal",
            "meal_type": meal_type,
            "food_items": ", ".join(food_list),
            "portion": portion,
            "skipped": False,
            "notes": notes or "",
            "calories": nutrition["calories"],
            "protein": nutrition["protein"],
            "carbs": nutrition["carbs"],
            "fat": nutrition["fat"],
        }

        print(f"[OK] {meal_type} 기록됨")
        print(f"   음식: {', '.join(food_list)}")
        print(f"   양: {portion}")
        print(f"   영양소: {nutrition['calories']}kcal, "
              f"단백질 {nutrition['protein']}g, "
              f"탄수화물 {nutrition['carbs']}g, "
              f"지방 {nutrition['fat']}g")

    # 파일명: 2026-02-11_1230_점심.md
    safe_type = meals_io.sanitize(meal_type)
    filename = f"{today_str}_{timestamp}_{safe_type}.md"

    fpath = meals_io.write_entry(filename, frontmatter)
    print(f"[OK] Obsidian vault 저장: {fpath}")

    return frontmatter


def main():
    parser = argparse.ArgumentParser(description="식사 기록")
    parser.add_argument("--type", required=True, help="아침/점심/저녁/간식")
    parser.add_argument("--food", help="음식 목록 (쉼표로 구분)")
    parser.add_argument("--portion", default="보통", help="적음/보통/많음")
    parser.add_argument("--skipped", action="store_true", help="거른 식사")
    parser.add_argument("--notes", help="메모")

    args = parser.parse_args()

    # 유효성 검사
    valid_types = ["아침", "점심", "저녁", "간식"]
    if args.type not in valid_types:
        print(f"[ERROR] 잘못된 식사 유형: {args.type}")
        print(f"   사용 가능: {', '.join(valid_types)}")
        sys.exit(1)

    if not args.skipped and not args.food:
        print("[ERROR] 음식을 입력하거나 --skipped 플래그를 사용하세요")
        sys.exit(1)

    # 기록
    log_meal(
        meal_type=args.type,
        food_items=args.food or "",
        portion=args.portion,
        skipped=args.skipped,
        notes=args.notes
    )


if __name__ == "__main__":
    main()
