#!/usr/bin/env python3
"""레시피 추천 스크립트 (저속노화 기준)"""

import sys
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import open_conn, query_pantry_items


def main():
    with open_conn(auto_commit=False) as conn:
        items = query_pantry_items(conn, status="재고 있음")

    if not items:
        print("현재 사용 가능한 식재료가 없습니다.")
        return

    print("현재 보유 식재료:")
    for item in items:
        print(f"  {item['name']} ({item['quantity']}{item['unit']})")

    print("\n에이전트에게 '현재 재료로 저속노화 메뉴 추천해줘'라고 요청하세요.")

    ingredient_names = [item["name"] for item in items]

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
        print("\n기본 추천:")
        for recipe in suggested:
            print(f"  {recipe}")


if __name__ == "__main__":
    main()
