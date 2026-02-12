#!/usr/bin/env python3
"""Parse '뱅샐현황' sheet from the yearly portfolio workbook and emit a compact summary.

Designed for Clawdbot cron runs (no pandas).

Assumptions (confirmed by Daye):
- Column B (2): asset type (e.g., '주식')
- Column C (3): broker
- Column D (4): name/ticker label
- Column F (6): principal (invested)
- Column G (7): valuation
- Column H (8): returnPct

US vs KR rule (confirmed by Daye):
- If broker == '토스증권' => US
- If name starts with 'TIGER' => include in US report as well
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from glob import glob
from typing import Any, Dict, List, Optional, Tuple

import openpyxl

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


@dataclass
class Holding:
    asset: str
    broker: str
    name: str
    principal: float
    valuation: float
    return_pct: Optional[float]

    @property
    def pnl(self) -> float:
        return (self.valuation or 0.0) - (self.principal or 0.0)


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return float(x)
    if isinstance(x, str):
        s = x.strip().replace(",", "")
        if s in ("", "-"):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def parse_holdings(path: str, sheet: str = "뱅샐현황", max_rows: int = 400) -> List[Holding]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]

    out: List[Holding] = []
    started = False

    for row in ws.iter_rows(min_row=1, max_row=max_rows, min_col=1, max_col=8, values_only=True):
        asset = row[1]  # col B
        broker = row[2]  # col C
        name = row[3]  # col D
        principal = _to_float(row[5])
        valuation = _to_float(row[6])
        retpct = _to_float(row[7])

        if asset == "주식" and broker and name:
            started = True
            if principal is None or valuation is None:
                # still include but will be less useful
                principal = principal or 0.0
                valuation = valuation or 0.0
            out.append(
                Holding(
                    asset=str(asset),
                    broker=str(broker),
                    name=str(name),
                    principal=float(principal),
                    valuation=float(valuation),
                    return_pct=retpct,
                )
            )
        else:
            # stop after we have started and we hit a non-stock block for a while
            if started and asset and isinstance(asset, str) and asset != "주식":
                break

    return out


def split_kr_us(holds: List[Holding]) -> Tuple[List[Holding], List[Holding]]:
    us: List[Holding] = []
    kr: List[Holding] = []
    for h in holds:
        is_us = (h.broker == "토스증권") or (h.name.startswith("TIGER"))
        (us if is_us else kr).append(h)
    return kr, us


def summarize(holds: List[Holding], top_n: int = 5) -> Dict[str, Any]:
    total_val = sum(h.valuation for h in holds) or 0.0
    total_principal = sum(h.principal for h in holds) or 0.0
    total_pnl = total_val - total_principal
    total_return_pct = (total_pnl / total_principal) if total_principal else None

    def with_weight(h: Holding) -> Dict[str, Any]:
        w = (h.valuation / total_val) if total_val else 0.0
        return {
            "name": h.name,
            "broker": h.broker,
            "principal": h.principal,
            "valuation": h.valuation,
            "pnl": h.pnl,
            "returnPct": h.return_pct,
            "weight": w,
        }

    top_holdings = sorted(holds, key=lambda x: x.valuation, reverse=True)[:top_n]
    top_winners = sorted(holds, key=lambda x: x.pnl, reverse=True)[:top_n]
    top_losers = sorted(holds, key=lambda x: x.pnl)[:top_n]

    return {
        "count": len(holds),
        "totalPrincipal": total_principal,
        "totalValuation": total_val,
        "totalPnL": total_pnl,
        "totalReturnPct": total_return_pct,
        "topHoldings": [with_weight(h) for h in top_holdings],
        "topWinners": [with_weight(h) for h in top_winners],
        "topLosers": [with_weight(h) for h in top_losers],
    }


def _today_ymd_kst() -> str:
    if ZoneInfo is None:
        return datetime.now().strftime("%Y-%m-%d")
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")


def _load_latest_snapshot(snapshot_dir: str) -> Optional[Dict[str, Any]]:
    paths = sorted(glob(os.path.join(snapshot_dir, "*.json")))
    if not paths:
        return None
    # pick the most recent snapshot file
    with open(paths[-1], "r", encoding="utf-8") as f:
        return json.load(f)


def _compute_daily_delta(cur: Dict[str, Any], prev: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not prev:
        return {"available": False}

    out: Dict[str, Any] = {"available": True}
    for k in ("kr", "us"):
        try:
            c = cur[k]
            p = prev[k]
            out[k] = {
                "deltaValuation": (c.get("totalValuation", 0.0) - p.get("totalValuation", 0.0)),
                "deltaPnL": (c.get("totalPnL", 0.0) - p.get("totalPnL", 0.0)),
            }
        except Exception:
            out[k] = {"deltaValuation": None, "deltaPnL": None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--sheet", default="뱅샐현황")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--snapshot-dir", default=None, help="If set, writes daily snapshot and computes delta vs last snapshot")
    args = ap.parse_args()

    holds = parse_holdings(args.file, sheet=args.sheet)
    kr, us = split_kr_us(holds)

    cur = {
        "asOf": _today_ymd_kst(),
        "file": args.file,
        "sheet": args.sheet,
        "kr": summarize(kr, top_n=args.top),
        "us": summarize(us, top_n=args.top),
    }

    if args.snapshot_dir:
        os.makedirs(args.snapshot_dir, exist_ok=True)
        prev = _load_latest_snapshot(args.snapshot_dir)
        cur["daily"] = _compute_daily_delta({"kr": cur["kr"], "us": cur["us"]}, prev)
        snap_path = os.path.join(args.snapshot_dir, f"{cur['asOf']}.json")
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump({"asOf": cur["asOf"], "kr": cur["kr"], "us": cur["us"]}, f, ensure_ascii=False)
        cur["snapshotPath"] = snap_path

    print(json.dumps(cur, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
