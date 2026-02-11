#!/usr/bin/env python3
"""
식재료 목록 조회 스크립트
"""

import argparse
from notion_client import NotionPantryClient

def main():
    parser = argparse.ArgumentParser(description="식재료 목록 조회")
    parser.add_argument("--category", help="카테고리 필터")
    parser.add_argument("--location", 
                       choices=["냉장", "냉동", "실온"],
                       help="위치 필터")
    
    args = parser.parse_args()
    
    client = NotionPantryClient()
    
    items = client.get_all_items_by_location(args.location)
    
    # 카테고리 필터링 (클라이언트 측)
    if args.category:
        items = [item for item in items if item["category"] == args.category]
    
    if not items:
        print("📭 식재료가 없습니다.")
        return
    
    print(f"📦 **식재료 목록** (총 {len(items)}개)\n")
    
    # 카테고리별로 그룹화
    by_category = {}
    for item in items:
        cat = item["category"] or "기타"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)
    
    for category, cat_items in sorted(by_category.items()):
        print(f"\n**{category}:**")
        for item in cat_items:
            print(f"  • {item['name']}: {item['quantity']}{item['unit']}")

if __name__ == "__main__":
    main()
