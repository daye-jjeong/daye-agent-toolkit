#!/usr/bin/env python3
"""식재료 추가 스크립트"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import open_conn, upsert_pantry_item


def main():
    parser = argparse.ArgumentParser(description="식재료 추가")
    parser.add_argument("--name", required=True, help="식재료명")
    parser.add_argument("--category", required=True,
                       choices=["채소", "과일", "육류", "가공식품", "조미료", "유제품", "기타"])
    parser.add_argument("--quantity", type=float, required=True)
    parser.add_argument("--unit", required=True,
                       choices=["개", "g", "ml", "봉지", "팩"])
    parser.add_argument("--location", required=True,
                       choices=["냉장", "냉동", "실온"])
    parser.add_argument("--expiry", help="유통기한 (YYYY-MM-DD)")
    parser.add_argument("--purchase", help="구매일 (YYYY-MM-DD, 기본: 오늘)")
    parser.add_argument("--notes", default="")

    args = parser.parse_args()

    data = {
        "name": args.name,
        "category": args.category,
        "quantity": args.quantity,
        "unit": args.unit,
        "location": args.location,
        "purchase_date": args.purchase or datetime.now().strftime("%Y-%m-%d"),
        "expiry_date": args.expiry,
        "status": "재고 있음",
        "notes": args.notes or None,
    }

    with open_conn() as conn:
        upsert_pantry_item(conn, data)

    print(f"OK: {args.name} {args.quantity}{args.unit} / {args.location}")
    if args.expiry:
        print(f"   유통기한: {args.expiry}")


if __name__ == "__main__":
    main()
