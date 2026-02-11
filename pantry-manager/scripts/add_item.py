#!/usr/bin/env python3
"""
식재료 추가 스크립트
"""

import argparse
from notion_client import NotionPantryClient

def main():
    parser = argparse.ArgumentParser(description="식재료 추가")
    parser.add_argument("--name", required=True, help="식재료명")
    parser.add_argument("--category", required=True, 
                       choices=["채소", "과일", "육류", "가공식품", "조미료", "유제품", "기타"],
                       help="카테고리")
    parser.add_argument("--quantity", type=float, required=True, help="수량")
    parser.add_argument("--unit", required=True, 
                       choices=["개", "g", "ml", "봉지", "팩"],
                       help="단위")
    parser.add_argument("--location", required=True,
                       choices=["냉장", "냉동", "실온"],
                       help="보관 위치")
    parser.add_argument("--expiry", help="유통기한 (YYYY-MM-DD)")
    parser.add_argument("--purchase", help="구매일 (YYYY-MM-DD, 기본: 오늘)")
    parser.add_argument("--notes", default="", help="메모")
    
    args = parser.parse_args()
    
    client = NotionPantryClient()
    
    result = client.add_item(
        name=args.name,
        category=args.category,
        quantity=args.quantity,
        unit=args.unit,
        location=args.location,
        expiry_date=args.expiry,
        purchase_date=args.purchase,
        notes=args.notes
    )
    
    if result["success"]:
        print(f"✅ {args.name} 추가 완료!")
        print(f"   📦 {args.quantity}{args.unit} / {args.location}")
        if args.expiry:
            print(f"   📅 유통기한: {args.expiry}")
    else:
        print(f"❌ 추가 실패: {result['error']}")

if __name__ == "__main__":
    main()
