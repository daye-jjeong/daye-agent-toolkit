#!/usr/bin/env python3
"""식재료 목록 조회 스크립트"""

import argparse
import sys
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import open_conn, query_pantry_items


def main():
    parser = argparse.ArgumentParser(description="식재료 목록 조회")
    parser.add_argument("--category", help="카테고리 필터")
    parser.add_argument("--location", choices=["냉장", "냉동", "실온"])
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    with open_conn(auto_commit=False) as conn:
        items = query_pantry_items(conn, category=args.category, location=args.location)

    if args.json:
        import json
        print(json.dumps(items, ensure_ascii=False, indent=2, default=str))
        return

    if not items:
        print("식재료가 없습니다.")
        return

    print(f"식재료 목록 (총 {len(items)}개)\n")

    by_category: dict[str, list] = {}
    for item in items:
        by_category.setdefault(item["category"], []).append(item)

    for category, cat_items in sorted(by_category.items()):
        print(f"[{category}]")
        for item in cat_items:
            print(f"  {item['name']}: {item['quantity']}{item['unit']} ({item['location']})")
        print()


if __name__ == "__main__":
    main()
