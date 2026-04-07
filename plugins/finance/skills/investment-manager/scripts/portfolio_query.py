#!/usr/bin/env python3
"""Portfolio query — finance_investments 기반 포트폴리오 조회 JSON 출력.

Usage:
  python portfolio_query.py summary --top 5
  python portfolio_query.py risk
  python portfolio_query.py holding --name 엔비디아
"""

import argparse
import json
import sys
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn  # noqa: E402


def _is_us(product_name, institution):
    return institution == "토스증권" or product_name.startswith("TIGER")


def _holding_dict(row, total_val):
    val = row["current_value"] or 0
    return {
        "name": row["product_name"],
        "institution": row["institution"],
        "product_type": row["product_type"],
        "invested": row["invested"] or 0,
        "current_value": val,
        "pnl": val - (row["invested"] or 0),
        "return_pct": row["return_pct"] or 0,
        "weight": round(val / total_val * 100, 2) if total_val else 0,
    }


def summary(conn, top_n=5):
    rows = conn.execute("""
        SELECT product_name, product_type, institution,
               invested, current_value, return_pct
        FROM finance_investments
        ORDER BY current_value DESC
    """).fetchall()

    kr, us = [], []
    for r in rows:
        (_us_list := us if _is_us(r["product_name"], r["institution"]) else kr).append(r)

    def _summarize(holdings, label):
        total_invested = sum(r["invested"] or 0 for r in holdings)
        total_val = sum(r["current_value"] or 0 for r in holdings)
        total_pnl = total_val - total_invested
        return_pct = round(total_pnl / total_invested * 100, 2) if total_invested else 0

        all_items = [_holding_dict(r, total_val) for r in holdings]
        by_value = sorted(all_items, key=lambda x: x["current_value"], reverse=True)
        by_pnl_asc = sorted(all_items, key=lambda x: x["pnl"])

        return {
            "label": label,
            "count": len(holdings),
            "total_invested": total_invested,
            "total_value": total_val,
            "total_pnl": total_pnl,
            "return_pct": return_pct,
            "top_holdings": by_value[:top_n],
            "top_losers": by_pnl_asc[:top_n],
        }

    kr_sum = _summarize(kr, "국내")
    us_sum = _summarize(us, "해외")
    return {
        "kr": kr_sum,
        "us": us_sum,
        "total_value": kr_sum["total_value"] + us_sum["total_value"],
        "total_invested": kr_sum["total_invested"] + us_sum["total_invested"],
    }


def risk(conn):
    rows = conn.execute("""
        SELECT product_name, institution, invested, current_value, return_pct
        FROM finance_investments
        ORDER BY current_value DESC
    """).fetchall()

    total_val = sum(r["current_value"] or 0 for r in rows)
    warnings = []

    # 비중 쏠림: Top1 >= 35%
    if rows and total_val:
        top1_weight = (rows[0]["current_value"] or 0) / total_val * 100
        if top1_weight >= 35:
            warnings.append({
                "type": "concentration",
                "message": f"{rows[0]['product_name']} 비중 {top1_weight:.1f}% — 쏠림 경고",
                "severity": "high",
            })

    # 손실군: 수익률 <= -30% 종목 2개 이상
    losers = [r for r in rows if (r["return_pct"] or 0) <= -30]
    if len(losers) >= 2:
        names = [r["product_name"] for r in losers]
        warnings.append({
            "type": "loss_cluster",
            "message": f"손실군 {len(losers)}개 종목: {', '.join(names)}",
            "severity": "high",
            "holdings": [{"name": r["product_name"], "return_pct": r["return_pct"]} for r in losers],
        })

    # 단일 증권사 집중
    by_inst = {}
    for r in rows:
        inst = r["institution"] or "기타"
        by_inst[inst] = by_inst.get(inst, 0) + (r["current_value"] or 0)
    for inst, val in by_inst.items():
        pct = val / total_val * 100 if total_val else 0
        if pct >= 80:
            warnings.append({
                "type": "broker_concentration",
                "message": f"{inst} 집중 {pct:.1f}%",
                "severity": "medium",
            })

    return {
        "total_value": total_val,
        "holding_count": len(rows),
        "warnings": warnings,
        "warning_count": len(warnings),
    }


def holding_detail(conn, name):
    rows = conn.execute("""
        SELECT product_name, product_type, institution,
               invested, current_value, return_pct
        FROM finance_investments
        WHERE product_name LIKE ?
        ORDER BY current_value DESC
    """, (f"%{name}%",)).fetchall()

    if not rows:
        return {"found": False, "query": name}

    total_invested = sum(r["invested"] or 0 for r in rows)
    total_val = sum(r["current_value"] or 0 for r in rows)

    holdings = [{
        "institution": r["institution"],
        "invested": r["invested"] or 0,
        "current_value": r["current_value"] or 0,
        "pnl": (r["current_value"] or 0) - (r["invested"] or 0),
        "return_pct": r["return_pct"] or 0,
    } for r in rows]

    # 시세 스냅샷 히스토리
    try:
        snapshots = conn.execute("""
            SELECT date, price FROM finance_price_snapshots
            WHERE product_name LIKE ?
            ORDER BY date DESC LIMIT 10
        """, (f"%{name}%",)).fetchall()
    except Exception:
        snapshots = []

    return {
        "found": True,
        "name": rows[0]["product_name"],
        "total_invested": total_invested,
        "total_value": total_val,
        "total_pnl": total_val - total_invested,
        "return_pct": round((total_val - total_invested) / total_invested * 100, 2) if total_invested else 0,
        "by_institution": holdings,
        "price_history": [{"date": s["date"], "price": s["price"]} for s in snapshots],
    }


def main():
    parser = argparse.ArgumentParser(description="Portfolio query")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_sum = sub.add_parser("summary")
    p_sum.add_argument("--top", type=int, default=5)

    sub.add_parser("risk")

    p_hold = sub.add_parser("holding")
    p_hold.add_argument("--name", required=True)

    args = parser.parse_args()
    conn = get_conn()
    try:
        if args.mode == "summary":
            result = summary(conn, top_n=args.top)
        elif args.mode == "risk":
            result = risk(conn)
        elif args.mode == "holding":
            result = holding_detail(conn, args.name)
        else:
            parser.print_help()
            sys.exit(1)

        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
