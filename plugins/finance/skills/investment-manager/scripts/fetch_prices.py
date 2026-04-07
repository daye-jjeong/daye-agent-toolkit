#!/usr/bin/env python3
"""Save price snapshots to DB.

LLM이 WebSearch로 조회한 시세를 DB에 저장하는 스크립트.
시세 조회 자체는 LLM이 수행하고, 이 스크립트는 저장만 담당.

Usage:
  python fetch_prices.py --products "엔비디아,애플" --prices "130.5,195.2"
  python fetch_prices.py --products "엔비디아" --prices "130.5" --currency USD
  python fetch_prices.py --products "삼성전자" --prices "58000" --date 2026-03-07
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn  # noqa: E402


def save_prices(conn, products, prices, currency="KRW", date_str=None, source=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    results = []
    for product, price in zip(products, prices):
        name = product.strip()
        try:
            val = float(price)
            conn.execute("""
                INSERT INTO finance_price_snapshots
                    (product_name, date, price, currency, source)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(product_name, date) DO UPDATE SET
                    price=excluded.price,
                    currency=excluded.currency,
                    source=excluded.source
            """, (name, date_str, val, currency, source))
            results.append({"product": name, "price": val, "status": "saved"})
        except (ValueError, sqlite3.Error) as e:
            results.append({"product": name, "error": str(e), "status": "error"})

    conn.commit()
    return {"date": date_str, "results": results}


def main():
    parser = argparse.ArgumentParser(description="Save price snapshots")
    parser.add_argument("--products", required=True, help="Comma-separated product names")
    parser.add_argument("--prices", required=True, help="Comma-separated prices")
    parser.add_argument("--currency", default="KRW")
    parser.add_argument("--date", dest="date_str", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--source", default="web_search")
    args = parser.parse_args()

    products = args.products.split(",")
    prices = args.prices.split(",")

    if len(products) != len(prices):
        print(f"Error: products ({len(products)}) and prices ({len(prices)}) count mismatch")
        sys.exit(1)

    conn = get_conn()
    try:
        result = save_prices(conn, products, prices, args.currency, args.date_str, args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
