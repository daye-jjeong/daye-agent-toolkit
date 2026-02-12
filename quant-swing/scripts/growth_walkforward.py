#!/usr/bin/env python3
"""Walk-forward (rolling) evaluation for growth swing strategy.

We choose parameters on a training window, then evaluate on the next test window.
This helps assess robustness (reduces overfitting risk).

Default config:
- Universe: preset growth tickers (same as growth_swing_backtest.py)
- Strategy: breakout + top-N momentum + ATR trailing stop + QQQ regime filter
- Train: 3 years
- Test: 1 year
- Grid search on breakout lookback and ATR k (kept small on purpose)

Not financial advice.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime

import numpy as np
import pandas as pd

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from portfolio.growth_swing_backtest import run_backtest, summarize


UNIVERSE = [
    # growth
    "MDB",
    "NVDA",
    "META",
    "MSFT",
    "AMZN",
    "GOOGL",
    "AAPL",
    "TSLA",
    "PLTR",
    "DDOG",
    "AMD",
    "TEAM",
    "ESTC",
    # diversifiers
    "XLF",
    "XLE",
    "GLD",
    "TLT",
    "IWM",
]


def year_bounds(y: int) -> tuple[str, str]:
    return f"{y}-01-01", f"{y+1}-01-01"


def slice_period_equity(equity: pd.Series, start: str, end: str) -> pd.Series:
    e = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index < pd.Timestamp(end))]
    return e


def period_return(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start_year", type=int, default=2019)
    ap.add_argument("--end_year", type=int, default=None, help="last test year inclusive")
    ap.add_argument("--train_years", type=int, default=3)
    ap.add_argument("--top_n", type=int, default=3)
    ap.add_argument("--mom", type=int, default=63)
    ap.add_argument("--atr_n", type=int, default=14)
    ap.add_argument("--risk", type=float, default=0.02)
    ap.add_argument("--heat", type=float, default=0.06)
    ap.add_argument("--fee_bps", type=float, default=2.0)
    ap.add_argument("--slip_bps", type=float, default=20.0)
    ap.add_argument("--max_per_cluster", type=int, default=2)
    ap.add_argument("--universe_source", default="static", choices=["static", "nasdaq100", "rule"])
    ap.add_argument("--universe_size", type=int, default=50)
    ap.add_argument("--adv_lookback", type=int, default=60)
    ap.add_argument("--regime_sma", type=int, default=200)

    # small grid (keep it conservative)
    ap.add_argument("--grid_breakout", default="50,80,100")
    ap.add_argument("--grid_atr_k", default="2.0,2.5")

    args = ap.parse_args()

    now_year = int(datetime.now().strftime("%Y"))
    end_year = args.end_year or (now_year - 1)  # avoid partial year by default

    grid_breakout = [int(x) for x in args.grid_breakout.split(",") if x.strip()]
    grid_k = [float(x) for x in args.grid_atr_k.split(",") if x.strip()]

    rows = []
    stitched = 1.0

    for test_year in range(args.start_year + args.train_years, end_year + 1):
        train_start_year = test_year - args.train_years
        train_start, _ = year_bounds(train_start_year)
        _, train_end = year_bounds(test_year)  # up to test_year-12-31
        test_start, test_end = year_bounds(test_year)

        # grid search on train window
        best = None
        best_score = -1e9
        for b in grid_breakout:
            for k in grid_k:
                equity, trades = run_backtest(
                    universe=UNIVERSE,
                    start=train_start,
                    end=train_end,
                    top_n=args.top_n,
                    breakout_lookback=b,
                    mom_lookback=args.mom,
                    atr_n=args.atr_n,
                    atr_k=k,
                    regime_sma=args.regime_sma,
                    risk_per_trade=args.risk,
                    max_total_heat=args.heat,
                    fee_bps=args.fee_bps,
                    slip_bps=args.slip_bps,
                    max_per_cluster=args.max_per_cluster,
                    universe_source=args.universe_source,
                    universe_size=args.universe_size,
                    adv_lookback=args.adv_lookback,
                )
                summ = summarize(equity, trades).iloc[0].to_dict()

                # score = Sharpe with mild penalty for deep drawdown
                score = float(summ["Sharpe"]) + 0.25 * float(summ["MDD"])  # MDD is negative
                if score > best_score:
                    best_score = score
                    best = {"breakout": b, "atr_k": k, "train": summ}

        # evaluate on test year using the chosen params
        equity_full, trades_full = run_backtest(
            universe=UNIVERSE,
            start=train_start,
            end=test_end,
            top_n=args.top_n,
            breakout_lookback=best["breakout"],
            mom_lookback=args.mom,
            atr_n=args.atr_n,
            atr_k=best["atr_k"],
            regime_sma=args.regime_sma,
            risk_per_trade=args.risk,
            max_total_heat=args.heat,
            fee_bps=args.fee_bps,
            slip_bps=args.slip_bps,
            max_per_cluster=args.max_per_cluster,
            universe_source=args.universe_source,
            universe_size=args.universe_size,
            adv_lookback=args.adv_lookback,
        )
        eq_test = slice_period_equity(equity_full, test_start, test_end)
        r = period_return(eq_test)
        stitched *= (1.0 + r)

        rows.append(
            {
                "test_year": test_year,
                "chosen_breakout": best["breakout"],
                "chosen_atr_k": best["atr_k"],
                "train_sharpe": best["train"]["Sharpe"],
                "train_mdd": best["train"]["MDD"],
                "test_return": r,
                "stitched_equity": stitched,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No walk-forward rows. Adjust start_year/end_year.")

    print(df.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    total_years = len(df)
    total_ret = float(df["stitched_equity"].iloc[-1] - 1.0)
    cagr_like = float((df["stitched_equity"].iloc[-1]) ** (1 / total_years) - 1)
    worst_year = float(df["test_return"].min())
    best_year = float(df["test_return"].max())

    print("\nWalk-forward summary")
    print(
        " ".join(
            [
                f"years={total_years}",
                f"total_return={total_ret:,.3f}",
                f"geometric_avg={cagr_like:,.3f}",
                f"worst_year={worst_year:,.3f}",
                f"best_year={best_year:,.3f}",
            ]
        )
    )


if __name__ == "__main__":
    main()
