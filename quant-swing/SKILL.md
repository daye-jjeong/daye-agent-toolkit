---
name: quant-swing
description: Growth Breakout Momentum 스윙 전략 실행/분석
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

## 스크립트

| 파일 | 용도 | 티어 |
|------|------|------|
| `scripts/growth_swing_backtest.py` | Growth Breakout Momentum 백테스트 | Tier 1 |
| `scripts/growth_walkforward.py` | Walk-forward 평가 (3y train / 1y test) | Tier 1 |
| `scripts/mdb_backtest.py` | MDB 백테스트 | Tier 1 |

## Example runs

### Single backtest (rule-based universe, more realistic)
```bash
/Users/dayejeong/clawd/.venv/bin/python /Users/dayejeong/clawd/skills/quant-swing/scripts/growth_swing_backtest.py \
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
/Users/dayejeong/clawd/.venv/bin/python /Users/dayejeong/clawd/skills/quant-swing/scripts/growth_swing_backtest.py \
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
/Users/dayejeong/clawd/.venv/bin/python /Users/dayejeong/clawd/skills/quant-swing/scripts/growth_walkforward.py \
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
