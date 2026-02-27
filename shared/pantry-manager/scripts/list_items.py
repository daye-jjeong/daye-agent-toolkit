#!/usr/bin/env python3
"""
식재료 목록 조회 스크립트
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pantry_io


def main():
    parser = argparse.ArgumentParser(description="식재료 목록 조회")
    parser.add_argument("--category", help="카테고리 필터")
    parser.add_argument("--location",
                       choices=["냉장", "냉동", "실온"],
                       help="위치 필터")

    args = parser.parse_args()

    items = pantry_io.get_all_items_by_location(args.location)

    # 카테고리 필터링
    if args.category:
        items = [item for item in items if item.get("category") == args.category]

    if not items:
        print("📭 식재료가 없습니다.")
        return

    print(f"📦 **식재료 목록** (총 {len(items)}개)\n")

    # 카테고리별로 그룹화
    by_category = {}
    for item in items:
        cat = item.get("category", "기타") or "기타"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)

    for category, cat_items in sorted(by_category.items()):
        print(f"\n**{category}:**")
        for item in cat_items:
            print(f"  • {item.get('name', '?')}: {item.get('quantity', 0)}{item.get('unit', '')}")


if __name__ == "__main__":
    main()
