#!/usr/bin/env python3
"""
레시피 추천 스크립트 (저속노화 기준)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pantry_io


def main():
    items = pantry_io.get_available_items()

    if not items:
        print("❌ 현재 사용 가능한 식재료가 없습니다.")
        return

    # 식재료 목록 출력
    ingredients = []
    for item in items:
        name = item.get("name", "Unknown")
        quantity = item.get("quantity", 0)
        unit = item.get("unit", "")
        ingredients.append(f"{name} ({quantity}{unit})")

    print("🥗 **현재 보유 식재료:**")
    for ing in ingredients:
        print(f"  • {ing}")

    print("\n🍳 **레시피 추천 (저속노화 기준):**")
    print("\n💡 에이전트에게 '현재 재료로 저속노화 메뉴 추천해줘'라고 요청하세요.")

    # 간단한 규칙 기반 추천
    print("\n📋 **기본 추천:**")

    ingredient_names = [item.get("name", "") for item in items]

    longevity_recipes = {
        "채소 볶음": ["채소", "올리브유", "마늘"],
        "샐러드": ["채소", "과일", "견과류"],
        "생선 구이": ["생선", "레몬", "허브"],
        "두부 조림": ["두부", "간장", "마늘"],
        "콩 스튜": ["콩", "토마토", "채소"],
    }

    suggested = []
    for recipe, required in longevity_recipes.items():
        matches = sum(1 for req in required if any(req in ing for ing in ingredient_names))
        if matches >= 2:
            suggested.append(recipe)

    if suggested:
        for recipe in suggested:
            print(f"  ✨ {recipe}")
    else:
        print("  (현재 재료로 추천할 메뉴가 없습니다)")


if __name__ == "__main__":
    main()
