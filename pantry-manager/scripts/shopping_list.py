#!/usr/bin/env python3
"""
장보기 목록 생성 스크립트
"""

from notion_client import NotionPantryClient

def main():
    client = NotionPantryClient()
    
    # "부족" 상태인 아이템 조회
    filter_dict = {
        "property": "Status",
        "select": {"equals": "부족"}
    }
    
    items = client.query_items(filter_dict)
    
    if not items:
        print("✅ 부족한 식재료가 없습니다!")
        return
    
    print("🛒 **장보기 목록**\n")
    
    # 카테고리별로 그룹화
    by_category = {}
    for item in items:
        props = item["properties"]
        name = props["Name"]["title"][0]["text"]["content"] if props["Name"]["title"] else "Unknown"
        category = props.get("Category", {}).get("select", {}).get("name", "기타")
        
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(name)
    
    for category, cat_items in sorted(by_category.items()):
        print(f"\n**{category}:**")
        for item in cat_items:
            print(f"  ☐ {item}")
    
    print(f"\n총 {len(items)}개 항목")

if __name__ == "__main__":
    main()
