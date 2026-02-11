#!/usr/bin/env python3
"""
레시피 추천 스크립트 (저속노화 기준)
"""

import os
from notion_client import NotionPantryClient

def main():
    client = NotionPantryClient()
    
    # 현재 재고 있는 식재료 조회
    filter_dict = {
        "property": "Status",
        "select": {"equals": "재고 있음"}
    }
    
    items = client.query_items(filter_dict)
    
    if not items:
        print("❌ 현재 사용 가능한 식재료가 없습니다.")
        return
    
    # 식재료 목록 추출
    ingredients = []
    for item in items:
        props = item["properties"]
        name = props["Name"]["title"][0]["text"]["content"] if props["Name"]["title"] else "Unknown"
        quantity = props.get("Quantity", {}).get("number", 0)
        unit = props.get("Unit", {}).get("select", {}).get("name", "")
        
        ingredients.append(f"{name} ({quantity}{unit})")
    
    print("🥗 **현재 보유 식재료:**")
    for ing in ingredients:
        print(f"  • {ing}")
    
    print("\n🍳 **레시피 추천 (저속노화 기준):**")
    print("\n💡 OpenAI API를 사용하여 레시피를 생성하려면:")
    print("   에이전트에게 '현재 재료로 저속노화 메뉴 추천해줘'라고 요청하세요.")
    print("\n   또는 다음 명령어를 실행:")
    print("   clawdbot message send -t @me '현재 냉장고 재료로 저속노화 메뉴 추천해줘'")
    
    # 간단한 규칙 기반 추천
    print("\n📋 **기본 추천:**")
    
    ingredient_names = [item.split(" (")[0] for item in ingredients]
    
    # 저속노화 메뉴 예시
    longevity_recipes = {
        "채소 볶음": ["채소", "올리브유", "마늘"],
        "샐러드": ["채소", "과일", "견과류"],
        "생선 구이": ["생선", "레몬", "허브"],
        "두부 조림": ["두부", "간장", "마늘"],
        "콩 스튜": ["콩", "토마토", "채소"]
    }
    
    suggested = []
    for recipe, required in longevity_recipes.items():
        # 간단한 매칭 (재료명에 키워드 포함 여부)
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
