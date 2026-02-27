#!/usr/bin/env python3
"""Render concise KR/US investment report text from portfolio_report.py JSON.

Usage:
  python render_report.py < report.json --section kr
  python render_report.py < report.json --section us

This script intentionally avoids any trading directives.
"""

from __future__ import annotations

import argparse
import json


def fmt_money(x: float) -> str:
    # Keep simple; caller knows KRW vs USD context.
    return f"{x:,.0f}" if abs(x) >= 100 else f"{x:,.2f}"


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "-"
    return f"{x*100:,.1f}%" if abs(x) <= 3 else f"{x:,.1f}%"  # handle already-percent vs ratio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", choices=["kr", "us"], required=True)
    args = ap.parse_args()

    data = json.load(open(0, "r", encoding="utf-8"))
    sec = data[args.section]

    header = "[투자-국내]" if args.section == "kr" else "[투자-해외]"

    total_val = sec.get("totalValuation", 0.0)
    total_pnl = sec.get("totalPnL", 0.0)
    total_ret = sec.get("totalReturnPct")

    daily = (data.get("daily") or {}).get(args.section) if (data.get("daily") or {}).get("available") else None
    daily_pnl = daily.get("deltaPnL") if daily else None

    lines: list[str] = []
    lines.append(f"{header} 데일리 리포트")
    lines.append(f"- 총 평가금액: {fmt_money(total_val)}")
    lines.append(f"- 누적 손익: {fmt_money(total_pnl)} / 누적 수익률: {fmt_pct(total_ret)}")
    if daily_pnl is None:
        lines.append(f"- 최근 1일 손익(전일 대비): 전일 데이터 없음")
    else:
        lines.append(f"- 최근 1일 손익(전일 대비): {fmt_money(daily_pnl)}")

    # top holdings
    lines.append("- Top holdings (TOP5)")
    for h in sec.get("topHoldings", [])[:5]:
        w = h.get("weight", 0.0) * 100
        rp = h.get("returnPct")
        lines.append(f"  - {h.get('name')} / {h.get('broker')} / {w:,.1f}% / {fmt_pct(rp)}")

    # top losers
    losers = sec.get("topLosers", [])[:5]
    lines.append("- Top losers (리스크 TOP5)")
    for h in losers:
        lines.append(f"  - {h.get('name')} / {fmt_money(h.get('pnl',0.0))} / {fmt_pct(h.get('returnPct'))}")

    # triggers
    triggers = []
    top1 = sec.get("topHoldings", [{}])[0]
    if top1 and float(top1.get("weight", 0.0)) >= 0.35:
        triggers.append(f"비중 쏠림: {top1.get('name')} {float(top1.get('weight',0.0))*100:,.1f}%")

    loss_cluster = sum(1 for h in losers if (h.get("returnPct") is not None and float(h.get("returnPct")) <= -30.0))
    if loss_cluster >= 2:
        triggers.append(f"손실군: -30% 이하 {loss_cluster}개 → 기준 재점검")

    if triggers:
        lines.append("- 트리거(단정X): " + " / ".join(triggers))
        lines.append("- 액션(검토): 유지 또는 비중조절·손절/리밸런싱 기준 재점검")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
