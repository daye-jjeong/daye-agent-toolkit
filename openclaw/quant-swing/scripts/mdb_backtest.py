#!/usr/bin/env python3
"""Simple, reproducible swing-strategy backtests for MDB.

- Data source: yfinance (daily adjusted close)
- No leverage, no shorting
- One position at a time (all-in cash when long)
- Costs: configurable per-trade fee in bps

This is not financial advice; it's a research utility.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    years = days / 365.25
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def sharpe(daily_returns: pd.Series) -> float:
    r = daily_returns.dropna()
    if r.std() == 0 or len(r) < 20:
        return 0.0
    return float(np.sqrt(252) * r.mean() / r.std())


@dataclass
class Result:
    name: str
    cagr: float
    mdd: float
    sharpe: float
    trades: int
    winrate: float
    avg_hold_days: float


def backtest_signals(px: pd.Series, signal: pd.Series, fee_bps: float = 2.0) -> tuple[pd.Series, dict]:
    """Backtest long/cash with signals in {0,1} where 1 means long at close (next day open proxy).

    We approximate execution at close-to-close; costs applied on position changes.
    """
    df = pd.DataFrame({"px": px, "sig": signal}).dropna()
    df["sig"] = df["sig"].clip(0, 1)

    # Use next-day position to avoid lookahead: decide at close t, hold from t+1
    df["pos"] = df["sig"].shift(1).fillna(0)
    df["ret"] = df["px"].pct_change().fillna(0)

    # Costs on position changes
    df["turn"] = df["pos"].diff().abs().fillna(0)
    fee = fee_bps / 10000.0
    df["net_ret"] = df["pos"] * df["ret"] - df["turn"] * fee

    equity = (1 + df["net_ret"]).cumprod()

    # Trades / winrate / holding
    # trade defined by entry pos 0->1 and exit 1->0
    entries = df.index[df["pos"].diff().fillna(0) == 1]
    exits = df.index[df["pos"].diff().fillna(0) == -1]
    trades = min(len(entries), len(exits) + (1 if len(exits) < len(entries) else 0))

    # Pair trades
    pairs = []
    ei = 0
    xi = 0
    while ei < len(entries):
        e = entries[ei]
        # find first exit after entry
        while xi < len(exits) and exits[xi] <= e:
            xi += 1
        x = exits[xi] if xi < len(exits) else df.index[-1]
        pairs.append((e, x))
        ei += 1

    pnl = []
    holds = []
    for e, x in pairs:
        if e not in df.index or x not in df.index:
            continue
        e_px = df.loc[e, "px"]
        x_px = df.loc[x, "px"]
        pnl.append(x_px / e_px - 1)
        holds.append((x - e).days)

    pnl = np.array(pnl) if pnl else np.array([])
    winrate = float((pnl > 0).mean()) if len(pnl) else 0.0
    avg_hold = float(np.mean(holds)) if holds else 0.0

    stats = {
        "trades": int(len(pnl)),
        "winrate": winrate,
        "avg_hold_days": avg_hold,
    }

    return equity, stats


def strat_breakout(px: pd.Series, lookback: int = 50) -> pd.Series:
    hi = px.rolling(lookback).max()
    sig = (px >= hi).astype(int)
    return sig


def strat_sma_cross(px: pd.Series, fast: int = 20, slow: int = 100) -> pd.Series:
    f = px.rolling(fast).mean()
    s = px.rolling(slow).mean()
    sig = (f > s).astype(int)
    return sig


def strat_mean_reversion_rsi(px: pd.Series, rsi_n: int = 14, entry: float = 30.0, exit: float = 55.0) -> pd.Series:
    # Classic RSI on close-to-close changes
    d = px.diff()
    up = d.clip(lower=0).rolling(rsi_n).mean()
    dn = (-d.clip(upper=0)).rolling(rsi_n).mean()
    rs = up / dn.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    sig = pd.Series(0, index=px.index, dtype=float)
    in_pos = False
    for t in px.index:
        if pd.isna(rsi.loc[t]):
            sig.loc[t] = 1 if in_pos else 0
            continue
        if not in_pos and rsi.loc[t] <= entry:
            in_pos = True
        elif in_pos and rsi.loc[t] >= exit:
            in_pos = False
        sig.loc[t] = 1 if in_pos else 0
    return sig


def strat_gap_reversion(px: pd.Series, gap_n: int = 1, z: float = -2.0, lookback: int = 20, exit_z: float = -0.5) -> pd.Series:
    """Approx: use daily returns; enter after large negative return vs recent std (z-score).

    For swing, this approximates 'panic drop then rebound'.
    """
    r = px.pct_change(gap_n)
    mu = r.rolling(lookback).mean()
    sd = r.rolling(lookback).std()
    zscore = (r - mu) / sd

    sig = pd.Series(0, index=px.index, dtype=float)
    in_pos = False
    for t in px.index:
        if pd.isna(zscore.loc[t]):
            sig.loc[t] = 1 if in_pos else 0
            continue
        if not in_pos and zscore.loc[t] <= z:
            in_pos = True
        elif in_pos and zscore.loc[t] >= exit_z:
            in_pos = False
        sig.loc[t] = 1 if in_pos else 0
    return sig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="MDB")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--fee_bps", type=float, default=2.0)
    args = ap.parse_args()

    end = args.end or datetime.now().strftime("%Y-%m-%d")

    df = yf.download(args.ticker, start=args.start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise SystemExit("No data downloaded")

    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        # yfinance can return multi-column even for a single ticker
        close = close.iloc[:, 0]
    px = close.dropna()

    strategies = {
        "Buy&Hold": pd.Series(1, index=px.index, dtype=float),
        "SMA 20/100": strat_sma_cross(px, 20, 100),
        "Breakout 50": strat_breakout(px, 50),
        "RSI MR 30/55": strat_mean_reversion_rsi(px, 14, 30, 55),
        "Gap MR z=-2": strat_gap_reversion(px, 1, -2.0, 20, -0.5),
    }

    results: list[Result] = []
    for name, sig in strategies.items():
        equity, st = backtest_signals(px, sig, fee_bps=args.fee_bps)
        daily = equity.pct_change().fillna(0)
        results.append(
            Result(
                name=name,
                cagr=cagr(equity),
                mdd=max_drawdown(equity),
                sharpe=sharpe(daily),
                trades=st["trades"],
                winrate=st["winrate"],
                avg_hold_days=st["avg_hold_days"],
            )
        )

    out = pd.DataFrame([r.__dict__ for r in results]).set_index("name")
    out = out.sort_values("sharpe", ascending=False)
    pd.set_option("display.max_columns", 20)
    print(out.to_string(float_format=lambda x: f"{x:,.3f}"))


if __name__ == "__main__":
    main()
