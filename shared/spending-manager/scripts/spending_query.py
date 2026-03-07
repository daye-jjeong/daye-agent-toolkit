#!/usr/bin/env python3
"""Spending query script — finance_transactions 집계 JSON 출력.

Usage:
  python spending_query.py summary --month 2026-03
  python spending_query.py summary --from 2026-01-01 --to 2026-03-07
  python spending_query.py trend --months 3
  python spending_query.py top --month 2026-03
  python spending_query.py uncategorized
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, get_coach_state  # noqa: E402

FIXED_CATEGORIES = {"주거/통신", "자동차", "교육"}


def _month_range(month_str: str):
    """YYYY-MM -> (start_date, end_date) where end is exclusive next month."""
    dt = datetime.strptime(month_str, "%Y-%m")
    start = dt.strftime("%Y-%m-%d")
    if dt.month == 12:
        end_dt = dt.replace(year=dt.year + 1, month=1)
    else:
        end_dt = dt.replace(month=dt.month + 1)
    end = end_dt.strftime("%Y-%m-%d")
    return start, end


def _category_expr():
    """finance_merchant_categories 매핑을 반영한 카테고리 조회용 SQL expression."""
    return """
        COALESCE(
            mc.category_l1,
            CASE WHEN t.category_l1 = '미분류' THEN NULL ELSE t.category_l1 END,
            '미분류'
        )
    """


def summary(conn, month=None, date_from=None, date_to=None):
    if month:
        date_from, date_to = _month_range(month)
    elif not date_from or not date_to:
        now = datetime.now()
        date_from, date_to = _month_range(now.strftime("%Y-%m"))

    cat_expr = _category_expr()

    rows = conn.execute(f"""
        SELECT {cat_expr} as category,
               COUNT(*) as cnt,
               ROUND(SUM(ABS(t.amount))) as total
        FROM finance_transactions t
        LEFT JOIN finance_merchant_categories mc ON t.merchant = mc.merchant
        WHERE t.tx_type = '지출'
          AND t.date >= ? AND t.date < ?
        GROUP BY category
        ORDER BY total DESC
    """, (date_from, date_to)).fetchall()

    total_spending = sum(r["total"] or 0 for r in rows)

    categories = []
    for r in rows:
        cat = r["category"] or "미분류"
        amt = r["total"] or 0
        categories.append({
            "category": cat,
            "amount": amt,
            "count": r["cnt"],
            "pct": round(amt / total_spending * 100, 1) if total_spending else 0,
            "type": "fixed" if cat in FIXED_CATEGORIES else "variable",
        })

    fixed = sum(c["amount"] for c in categories if c["type"] == "fixed")
    variable = sum(c["amount"] for c in categories if c["type"] == "variable")

    # 예산 체크
    try:
        state = get_coach_state(conn)
        budgets = {k.replace("budget_", ""): float(v) for k, v in state.items() if k.startswith("budget_")}
    except Exception:
        budgets = {}

    budget_status = []
    for cat_name, limit in budgets.items():
        spent = next((c["amount"] for c in categories if c["category"] == cat_name), 0)
        budget_status.append({
            "category": cat_name,
            "budget": limit,
            "spent": spent,
            "remaining": limit - spent,
            "over": spent > limit,
        })

    return {
        "period": {"from": date_from, "to": date_to},
        "total": total_spending,
        "fixed": fixed,
        "variable": variable,
        "categories": categories,
        "budgets": budget_status,
    }


def trend(conn, months=3):
    now = datetime.now()
    # 월 목록 생성 (day=1 고정으로 ValueError 방지)
    month_list = []
    y, m = now.year, now.month
    for _ in range(months):
        month_list.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1

    # 전체 기간 단일 쿼리
    oldest_start, _ = _month_range(month_list[-1])
    _, newest_end = _month_range(month_list[0])
    cat_expr = _category_expr()

    rows = conn.execute(f"""
        SELECT strftime('%Y-%m', t.date) as ym,
               {cat_expr} as category,
               ROUND(SUM(ABS(t.amount))) as total
        FROM finance_transactions t
        LEFT JOIN finance_merchant_categories mc ON t.merchant = mc.merchant
        WHERE t.tx_type = '지출'
          AND t.date >= ? AND t.date < ?
        GROUP BY ym, category
    """, (oldest_start, newest_end)).fetchall()

    # 월별 집계
    by_month = {}
    for r in rows:
        ym = r["ym"]
        cat = r["category"] or "미분류"
        amt = r["total"] or 0
        if ym not in by_month:
            by_month[ym] = {}
        by_month[ym][cat] = amt

    results = []
    for ms in reversed(month_list):
        cats = by_month.get(ms, {})
        total = sum(cats.values())
        fixed = sum(v for k, v in cats.items() if k in FIXED_CATEGORIES)
        variable = total - fixed
        results.append({
            "month": ms,
            "total": total,
            "fixed": fixed,
            "variable": variable,
            "categories": cats,
        })

    return {"months": results}


def top_merchants(conn, month=None):
    if month:
        date_from, date_to = _month_range(month)
    else:
        now = datetime.now()
        date_from, date_to = _month_range(now.strftime("%Y-%m"))

    rows = conn.execute("""
        SELECT merchant, COUNT(*) as cnt, ROUND(SUM(ABS(amount))) as total
        FROM finance_transactions
        WHERE tx_type = '지출' AND date >= ? AND date < ?
          AND merchant IS NOT NULL
        GROUP BY merchant
        ORDER BY total DESC
        LIMIT 15
    """, (date_from, date_to)).fetchall()

    merchants = [{"merchant": r["merchant"], "count": r["cnt"], "amount": r["total"]} for r in rows]

    # 반복 지출 (주 1회 이상 = 월 4회 이상)
    recurring = [m for m in merchants if m["count"] >= 4]

    return {
        "period": {"from": date_from, "to": date_to},
        "top_merchants": merchants,
        "recurring": recurring,
    }


def uncategorized(conn):
    rows = conn.execute("""
        SELECT t.merchant, COUNT(*) as cnt, ROUND(SUM(ABS(t.amount))) as total
        FROM finance_transactions t
        LEFT JOIN finance_merchant_categories mc ON t.merchant = mc.merchant
        WHERE t.tx_type = '지출'
          AND (t.category_l1 = '미분류' OR t.category_l1 IS NULL)
          AND mc.merchant IS NULL
          AND t.merchant IS NOT NULL
        GROUP BY t.merchant
        ORDER BY cnt DESC
    """).fetchall()

    return {
        "count": len(rows),
        "merchants": [{"merchant": r["merchant"], "tx_count": r["cnt"], "total": r["total"]} for r in rows],
    }


def main():
    parser = argparse.ArgumentParser(description="Spending query")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_sum = sub.add_parser("summary")
    p_sum.add_argument("--month", help="YYYY-MM")
    p_sum.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    p_sum.add_argument("--to", dest="date_to", help="YYYY-MM-DD")

    p_trend = sub.add_parser("trend")
    p_trend.add_argument("--months", type=int, default=3)

    p_top = sub.add_parser("top")
    p_top.add_argument("--month", help="YYYY-MM")

    sub.add_parser("uncategorized")

    args = parser.parse_args()
    conn = get_conn()
    try:
        if args.mode == "summary":
            result = summary(conn, month=args.month, date_from=args.date_from, date_to=args.date_to)
        elif args.mode == "trend":
            result = trend(conn, months=args.months)
        elif args.mode == "top":
            result = top_merchants(conn, month=args.month)
        elif args.mode == "uncategorized":
            result = uncategorized(conn)
        else:
            parser.print_help()
            sys.exit(1)

        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
