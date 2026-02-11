---
name: quant-swing
description: Run and critique the "Growth Breakout Momentum Top3" swing strategy (QQQ regime + breakout + top-N momentum + ATR stop + risk sizing) with realistic execution (next-open), slippage stress tests, and walk-forward evaluation. Use to produce a concise daily strategy-aware briefing and to re-run tests when rules change.
---

# Jarvis Quant Swing


**Version:** 0.1.0
**Updated:** 2026-02-03
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

## What it is
A research/ops skill to:
- run the strategy backtest
- run walk-forward evaluation
- stress test slippage
- print a short, actionable summary (not investment advice)

## Strategy (current)
- Regime: QQQ close > SMA(200)
- Entry: close breaks above rolling max (breakout lookback)
- Selection: top-N by 63d momentum among breakout candidates
- Exit: ATR trailing stop (highest close since entry - k*ATR)
- Sizing: risk-based per trade with total heat cap
- Execution: **signal at close(t-1) -> trade at open(t)** (next-open)

## Scripts
- `/Users/dayejeong/clawd/portfolio/growth_swing_backtest.py`
- `/Users/dayejeong/clawd/portfolio/growth_walkforward.py`

## Example runs

### Single backtest (rule-based universe, more realistic)
```bash
/Users/dayejeong/clawd/.venv/bin/python /Users/dayejeong/clawd/portfolio/growth_swing_backtest.py \
  --start 2019-01-01 \
  --breakout 100 \
  --atr_k 2.5 \
  --fee_bps 2 \
  --slip_bps 20 \
  --max_per_cluster 1 \
  --universe_source nasdaq100 \
  --universe_size 50 \
  --adv_lookback 60
```

### Single backtest (tiered slippage by cluster)
```bash
/Users/dayejeong/clawd/.venv/bin/python /Users/dayejeong/clawd/portfolio/growth_swing_backtest.py \
  --start 2019-01-01 \
  --breakout 100 \
  --atr_k 2.5 \
  --fee_bps 2 \
  --slip_bps 20 \
  --slip_tiers 'mega_tech=10,semis=15,software=20,rates=8,gold=8,energy=10,financials=10,smallcaps=15' \
  --max_per_cluster 1
```

### Walk-forward (3y train / 1y test, with slippage + rule-based universe)
```bash
/Users/dayejeong/clawd/.venv/bin/python /Users/dayejeong/clawd/portfolio/growth_walkforward.py \
  --start_year 2019 \
  --end_year 2025 \
  --grid_breakout 80,100,120 \
  --grid_atr_k 2.0,2.5 \
  --slip_bps 20 \
  --max_per_cluster 1 \
  --universe_source nasdaq100 \
  --universe_size 50 \
  --adv_lookback 60
```

## Notes
- Keep slippage stress tests (20–50bp) as default sanity.
- Avoid leaking secrets into logs.
