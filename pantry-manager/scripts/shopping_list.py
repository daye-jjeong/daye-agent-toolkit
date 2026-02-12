#!/usr/bin/env python3
"""
장보기 목록 생성 스크립트
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pantry_io


def main():
    items = pantry_io.get_shopping_list()

    if not items:
        print("✅ 부족한 식재료가 없습니다!")
        return

    print("🛒 **장보기 목록**\n")

    # 카테고리별로 그룹화
    by_category = {}
    for item in items:
        name = item.get("name", "Unknown")
        category = item.get("category", "기타") or "기타"

        if category not in by_category:
            by_category[category] = []
        by_category[category].append(name)

    for category, cat_items in sorted(by_category.items()):
        print(f"\n**{category}:**")
        for name in cat_items:
            print(f"  ☐ {name}")

    print(f"\n총 {len(items)}개 항목")


if __name__ == "__main__":
    main()
