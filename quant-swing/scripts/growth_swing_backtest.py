#!/usr/bin/env python3
"""Multi-asset swing backtest (Top-N momentum among breakout signals).

Rules (default):
- Universe: growth tickers (configurable)
- Regime filter: QQQ close > SMA(200)
- Entry signal: close breaks above rolling max(lookback=50)
- Selection: among entry candidates, pick top N by momentum (mom_lookback=63d total return)
- Risk control: ATR(14) trailing stop at highest_close_since_entry - k*ATR
- Position sizing: risk-based (risk_per_trade% of equity). Optional cap by max positions.
- Execution model: close-to-close with next-day position changes (avoid lookahead).

This is research code, not financial advice.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf


def fetch_nasdaq100_tickers() -> list[str]:
    """Fetch current Nasdaq-100 constituents from Wikipedia.

    Caveat: this is NOT survivorship-free. It's a practical proxy to remove
    hand-picked ticker bias, but still has survivorship/selection bias.

    Wikipedia can block default user agents (403). We fetch HTML with a
    browser-like UA and parse it.
    """
    import requests

    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    html = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        },
        timeout=30,
    ).text

    import io

    tables = pd.read_html(io.StringIO(html))

    for t in tables:
        cols = [c.lower() for c in t.columns.astype(str)]
        if "ticker" in cols or "symbol" in cols:
            col = t.columns[cols.index("ticker") if "ticker" in cols else cols.index("symbol")]
            tickers = (
                t[col]
                .astype(str)
                .str.replace(r"\s+", "", regex=True)
                .str.replace(".", "-", regex=False)
                .tolist()
            )
            tickers = [x for x in tickers if x and x != "nan"]
            return sorted(set(tickers))

    raise RuntimeError("Failed to parse Nasdaq-100 tickers from Wikipedia")


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


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
    if len(r) < 50 or r.std() == 0:
        return 0.0
    return float(np.sqrt(252) * r.mean() / r.std())


@dataclass
class Trade:
    ticker: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_px: float
    exit_px: float
    pnl: float
    hold_days: int


def download_ohlc(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    raw = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    out: dict[str, pd.DataFrame] = {}

    if isinstance(raw.columns, pd.MultiIndex):
        for t in tickers:
            if t not in raw.columns.get_level_values(0):
                continue
            df = raw[t].copy()
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            out[t] = df
    else:
        # single ticker
        df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna()
        out[tickers[0]] = df

    return out


def run_backtest(
    universe: list[str],
    start: str,
    end: str,
    data_override: dict[str, pd.DataFrame] | None = None,
    top_n: int = 3,
    breakout_lookback: int = 50,
    mom_lookback: int = 63,
    atr_n: int = 14,
    atr_k: float = 2.0,
    regime_sma: int = 200,
    risk_per_trade: float = 0.02,
    max_total_heat: float = 0.06,
    fee_bps: float = 2.0,
    slip_bps: float = 20.0,
    execution: str = "next_open",
    max_per_cluster: int = 2,
    cluster_map: dict[str, str] | None = None,
    universe_source: str = "static",  # static|nasdaq100|rule
    universe_size: int = 50,
    adv_lookback: int = 60,
    rebalance: str = "M",
    slip_tier_bps: dict[str, float] | None = None,
) -> tuple[pd.Series, list[Trade]]:
    # Universe candidates
    universe_candidates = list(universe)
    if universe_source == "nasdaq100":
        universe_candidates = fetch_nasdaq100_tickers()

    tickers = sorted(set(universe_candidates + ["QQQ"]))
    data = data_override if data_override is not None else download_ohlc(tickers, start, end)

    if "QQQ" not in data:
        raise SystemExit("QQQ data missing")

    # Align dates
    idx = data["QQQ"].index
    for t in universe_candidates:
        if t in data:
            idx = idx.union(data[t].index)
    idx = idx.sort_values()

    # Build feature frames
    open_ = pd.DataFrame({t: data[t]["Open"].reindex(idx) for t in tickers if t in data})
    close = pd.DataFrame({t: data[t]["Close"].reindex(idx) for t in tickers if t in data})
    high = pd.DataFrame({t: data[t]["High"].reindex(idx) for t in tickers if t in data})
    low = pd.DataFrame({t: data[t]["Low"].reindex(idx) for t in tickers if t in data})
    vol = pd.DataFrame({t: data[t]["Volume"].reindex(idx) for t in tickers if t in data})

    # Regime filter
    qqq = close["QQQ"].dropna()
    regime = (qqq > sma(qqq, regime_sma)).reindex(idx).fillna(False)

    # Breakout signals per ticker
    breakout = {}
    momentum = {}
    atr_map = {}
    for t in universe_candidates:
        if t not in data:
            continue
        px = close[t]
        breakout[t] = (px >= px.rolling(breakout_lookback).max()).astype(int)
        momentum[t] = (px / px.shift(mom_lookback) - 1.0)
        df = pd.DataFrame({"High": high[t], "Low": low[t], "Close": close[t]})
        atr_map[t] = atr(df, atr_n)

    fee = fee_bps / 10000.0
    slip_default = slip_bps / 10000.0

    # simple default clusters (avoid holding too many highly correlated names)
    if cluster_map is None:
        cluster_map = {
            # mega-cap tech
            "AAPL": "mega_tech",
            "MSFT": "mega_tech",
            "GOOGL": "mega_tech",
            "AMZN": "mega_tech",
            "META": "mega_tech",
            "TSLA": "mega_tech",
            # semis
            "NVDA": "semis",
            "AMD": "semis",
            # software
            "MDB": "software",
            "DDOG": "software",
            "TEAM": "software",
            "ESTC": "software",
            "PLTR": "software",
            # diversifiers
            "TLT": "rates",
            "GLD": "gold",
            "XLE": "energy",
            "XLF": "financials",
            "IWM": "smallcaps",
        }

    equity = pd.Series(index=idx, dtype=float)
    equity.iloc[0] = 1.0

    # Slippage tiers (bps) by cluster (or fallback to default)
    # This is a pragmatic proxy for "mega-cap/ETF cheaper, midcap growth more expensive".
    if slip_tier_bps is None:
        slip_tier_bps = {
            "mega_tech": 10.0,
            "semis": 15.0,
            "software": 20.0,
            "rates": 8.0,
            "gold": 8.0,
            "energy": 10.0,
            "financials": 10.0,
            "smallcaps": 15.0,
        }

    def slip_for(tk: str) -> float:
        grp = (cluster_map or {}).get(tk, tk)
        bps = slip_tier_bps.get(grp, slip_bps)
        return float(bps) / 10000.0 if bps is not None else slip_default

    # Precompute eligible universe per date (rule-based universe)
    eligible_map: dict[pd.Timestamp, set[str]] = {}
    if universe_source == "static":
        for dt in idx:
            eligible_map[dt] = set(universe_candidates)
    else:
        # universe_source == nasdaq100 or rule (monthly liquidity-ranked universe)
        dollar_vol = (close * vol).rolling(adv_lookback).mean()
        # rebal dates
        if rebalance.upper() == "M":
            rebal_dates = idx.to_series().groupby(idx.to_period("M")).max().tolist()
        elif rebalance.upper() == "W":
            rebal_dates = idx.to_series().groupby(idx.to_period("W")).max().tolist()
        else:
            raise ValueError(f"Unsupported rebalance='{rebalance}' (use 'M' or 'W')")
        rebal_dates = [pd.Timestamp(d) for d in rebal_dates]

        current = set()
        for dt in idx:
            if dt in rebal_dates:
                dv = dollar_vol.loc[dt, universe_candidates].dropna()
                # basic liquidity filter
                dv = dv[dv > 0]
                top = dv.sort_values(ascending=False).head(universe_size).index.tolist()
                current = set(top)
            eligible_map[dt] = set(current)

    # Portfolio state
    positions: dict[str, dict] = {}  # ticker -> {shares, entry_px, entry_date, high_close}
    trades: list[Trade] = []

    def cluster_counts(pos: dict[str, dict]) -> dict[str, int]:
        c: dict[str, int] = {}
        for tk in pos.keys():
            grp = (cluster_map or {}).get(tk, tk)
            c[grp] = c.get(grp, 0) + 1
        return c

    for i, dt in enumerate(idx):
        if i == 0:
            continue

        prev_dt = idx[i - 1]

        prev_eq = float(equity.loc[prev_dt])
        if pd.isna(prev_eq):
            prev_eq = float(equity.iloc[i - 1])

        # --- Step 1) Mark-to-market overnight gap: prev close -> today's open
        eq_open = prev_eq
        if positions:
            prev_values = {}
            total_val = 0.0
            for t, pos in positions.items():
                c0 = close.loc[prev_dt, t]
                o1 = open_.loc[dt, t]
                if pd.isna(c0) or pd.isna(o1):
                    continue
                v = pos["shares"] * float(c0)
                prev_values[t] = v
                total_val += v
            if total_val > 0:
                gap_ret = 0.0
                for t, v in prev_values.items():
                    r = float(open_.loc[dt, t]) / float(close.loc[prev_dt, t]) - 1.0
                    gap_ret += (v / total_val) * r
                eq_open = prev_eq * (1.0 + gap_ret)

        # --- Step 2) Decide exits/entries based on yesterday's close, execute at today's open
        dt_open_positions = dict(positions)

        # Stop check uses prev close (decision), exit at dt open if breached
        exits = []
        for t, pos in list(dt_open_positions.items()):
            px_prev = close.loc[prev_dt, t]
            if pd.isna(px_prev):
                continue
            # update trailing high up to prev close
            pos["high_close"] = max(pos["high_close"], float(px_prev))
            a = atr_map[t].loc[prev_dt]
            if pd.isna(a):
                continue
            stop = pos["high_close"] - atr_k * float(a)
            if float(px_prev) < stop:
                exits.append(t)

        eq_after_trades = eq_open

        # Apply exits at open (sell worse by slippage)
        for t in exits:
            pos = dt_open_positions.pop(t)
            o_px = open_.loc[dt, t]
            if pd.isna(o_px):
                continue
            entry_px = pos["entry_px"]
            s = slip_for(t)
            exit_px = float(o_px) * (1.0 - s)
            eq_after_trades *= (1.0 - fee)
            pnl = exit_px / entry_px - 1.0
            trades.append(
                Trade(
                    ticker=t,
                    entry_date=pos["entry_date"],
                    exit_date=dt,
                    entry_px=entry_px,
                    exit_px=exit_px,
                    pnl=pnl,
                    hold_days=(dt - pos["entry_date"]).days,
                )
            )

        # Entries based on prev close signals; execute at dt open
        prev_regime_on = bool(regime.loc[prev_dt])
        if prev_regime_on:
            slots = max(0, top_n - len(dt_open_positions))
            if slots > 0:
                candidates = []
                eligible_prev = eligible_map.get(prev_dt, set())
                for t in universe_candidates:
                    if t in dt_open_positions:
                        continue
                    if t not in eligible_prev:
                        continue
                    if t not in breakout:
                        continue
                    b = breakout[t].loc[prev_dt]
                    if pd.isna(b) or int(b) != 1:
                        continue
                    m = momentum[t].loc[prev_dt]
                    if pd.isna(m):
                        continue
                    a = atr_map[t].loc[prev_dt]
                    o_px = open_.loc[dt, t]
                    if pd.isna(a) or pd.isna(o_px) or float(a) <= 0:
                        continue
                    # cluster constraint
                    grp = (cluster_map or {}).get(t, t)
                    if max_per_cluster is not None:
                        cc = cluster_counts(dt_open_positions)
                        if cc.get(grp, 0) >= max_per_cluster:
                            continue
                    candidates.append((float(m), t))

                candidates.sort(reverse=True)
                pick = [t for _, t in candidates[:slots]]

                current_heat = len(dt_open_positions) * risk_per_trade
                for t in pick:
                    if current_heat + risk_per_trade > max_total_heat + 1e-9:
                        break
                    o_px = open_.loc[dt, t]
                    a = float(atr_map[t].loc[prev_dt])
                    if pd.isna(o_px) or a <= 0:
                        continue
                    s = slip_for(t)
                    entry_px = float(o_px) * (1.0 + s)
                    stop_dist = atr_k * a
                    if stop_dist <= 0:
                        continue
                    dollar_risk = eq_after_trades * risk_per_trade
                    shares = dollar_risk / stop_dist
                    if shares <= 0:
                        continue
                    eq_after_trades *= (1.0 - fee)
                    dt_open_positions[t] = {
                        "shares": float(shares),
                        "entry_px": entry_px,
                        "entry_date": dt,
                        "high_close": float(close.loc[prev_dt, t]) if not pd.isna(close.loc[prev_dt, t]) else entry_px,
                    }
                    current_heat += risk_per_trade

        # --- Step 3) Intraday mark-to-market: open -> close for positions held after open trades
        eq_close = eq_after_trades
        if dt_open_positions:
            open_values = {}
            total_val = 0.0
            for t, pos in dt_open_positions.items():
                o1 = open_.loc[dt, t]
                c1 = close.loc[dt, t]
                if pd.isna(o1) or pd.isna(c1):
                    continue
                v = pos["shares"] * float(o1)
                open_values[t] = v
                total_val += v
            if total_val > 0:
                day_ret = 0.0
                for t, v in open_values.items():
                    r = float(close.loc[dt, t]) / float(open_.loc[dt, t]) - 1.0
                    day_ret += (v / total_val) * r
                eq_close = eq_after_trades * (1.0 + day_ret)

        # Update trailing highs at close
        for t, pos in dt_open_positions.items():
            c1 = close.loc[dt, t]
            if pd.isna(c1):
                continue
            pos["high_close"] = max(pos["high_close"], float(c1))

        positions = dt_open_positions
        equity.loc[dt] = eq_close

    equity = equity.dropna()
    return equity, trades


def summarize(equity: pd.Series, trades: list[Trade]) -> pd.DataFrame:
    daily = equity.pct_change().fillna(0)
    winrate = np.mean([t.pnl > 0 for t in trades]) if trades else 0.0
    avg_hold = np.mean([t.hold_days for t in trades]) if trades else 0.0
    out = pd.DataFrame(
        {
            "CAGR": [cagr(equity)],
            "MDD": [max_drawdown(equity)],
            "Sharpe": [sharpe(daily)],
            "Trades": [len(trades)],
            "Winrate": [winrate],
            "AvgHoldDays": [avg_hold],
        }
    )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--top_n", type=int, default=3)
    ap.add_argument("--breakout", type=int, default=50)
    ap.add_argument("--mom", type=int, default=63)
    ap.add_argument("--atr_n", type=int, default=14)
    ap.add_argument("--atr_k", type=float, default=2.0)
    ap.add_argument("--risk", type=float, default=0.02)
    ap.add_argument("--heat", type=float, default=0.06)
    ap.add_argument("--fee_bps", type=float, default=2.0)
    ap.add_argument("--slip_bps", type=float, default=20.0)
    ap.add_argument(
        "--slip_tiers",
        default=None,
        help="Optional slippage tiers in bps, keyed by cluster, e.g. 'mega_tech=10,semis=15,software=20,rates=8'",
    )
    ap.add_argument("--max_per_cluster", type=int, default=2)
    ap.add_argument("--universe_source", default="static", choices=["static", "nasdaq100", "rule"])
    ap.add_argument("--universe_size", type=int, default=50)
    ap.add_argument("--adv_lookback", type=int, default=60)
    args = ap.parse_args()

    end = args.end or datetime.now().strftime("%Y-%m-%d")

    universe = [
        # default universe (used when universe_source=static)
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

    slip_tier_bps = None
    if args.slip_tiers:
        slip_tier_bps = {}
        for part in args.slip_tiers.split(","):
            if not part.strip():
                continue
            k, v = part.split("=")
            slip_tier_bps[k.strip()] = float(v)

    equity, trades = run_backtest(
        universe=universe,
        start=args.start,
        end=end,
        top_n=args.top_n,
        breakout_lookback=args.breakout,
        mom_lookback=args.mom,
        atr_n=args.atr_n,
        atr_k=args.atr_k,
        risk_per_trade=args.risk,
        max_total_heat=args.heat,
        fee_bps=args.fee_bps,
        slip_bps=args.slip_bps,
        max_per_cluster=args.max_per_cluster,
        universe_source=args.universe_source,
        universe_size=args.universe_size,
        adv_lookback=args.adv_lookback,
        slip_tier_bps=slip_tier_bps,
    )

    summ = summarize(equity, trades)
    print(summ.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    # Yearly returns
    yr = equity.resample("YE").last().pct_change().dropna()
    if len(yr):
        yr.index = yr.index.year
        print("\nYearly returns")
        print(yr.to_string(float_format=lambda x: f"{x:,.3f}"))

    # Top tickers by trade count
    if trades:
        tc = pd.Series([t.ticker for t in trades]).value_counts().head(10)
        print("\nTop trade counts")
        print(tc.to_string())


if __name__ == "__main__":
    main()
