#!/usr/bin/env python3
"""장보기 목록 생성 스크립트"""

import sys
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import open_conn, query_pantry_items


def main():
    with open_conn(auto_commit=False) as conn:
        items = query_pantry_items(conn, status="부족")

    if not items:
        print("부족한 식재료가 없습니다.")
        return

    print(f"장보기 목록\n")

    by_category: dict[str, list] = {}
    for item in items:
        by_category.setdefault(item["category"], []).append(item["name"])

    for category, names in sorted(by_category.items()):
        print(f"[{category}]")
        for name in names:
            print(f"  - {name}")

    print(f"\n총 {len(items)}개 항목")


if __name__ == "__main__":
    main()
