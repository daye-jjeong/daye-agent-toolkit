---
name: investment-report
description: 일일 투자 포트폴리오 리포트 생성
---

# Jarvis Investment Report Skill


**Version:** 0.2.0
**Updated:** 2026-02-12
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Active

This skill standardizes how to generate **domestic(KR)** and **US** portfolio reports from vault markdown and format them for messaging.

## Data sources
- Vault: `memory/finance/investments/*.md` (banksalad-import 스킬로 생성)
- Script: `scripts/portfolio_report.py`
- Snapshots dir (for day-over-day): `portfolio/snapshots/`

## Command (generate JSON)

```bash
python3 /Users/dayejeong/clawd/skills/investment-report/scripts/portfolio_report.py --top 5
```

Options:
- `--vault <path>` — 투자 데이터 디렉토리 (기본: `~/clawd/memory/finance/investments`)
- `--top <N>` — Top N 종목 수 (기본: 5)
- `--snapshot-dir <path>` — 스냅샷 디렉토리 (기본: `~/clawd/portfolio/snapshots`)

## Output rules (must follow)

### 1) Always split KR vs US
- KR = institution != 토스증권 AND name not startswith `TIGER`
- US = institution == 토스증권 OR name startswith `TIGER`

### 2) Include both cumulative + day-over-day
- Cumulative: total valuation, total PnL, total return %
- Day-over-day: use `daily.deltaPnL` if `daily.available=true`; otherwise state "전일 데이터 없음"

### 3) Triggers (rule-based, not trading advice)
- **Concentration**: Top1 weight >= 35% → "비중 쏠림" 경고
- **Loss cluster**: Top losers contains >=2 holdings with returnPct <= -30% → "손실군" 경고
- **Event risk**: if top holdings have earnings/regulation/rates headlines today → "이벤트" 경고

### 4) Tone constraints
- Never say "buy/sell now" as a directive.
- Use phrasing like: "유지/비중조절 검토/손절·리밸런싱 기준 재점검".

## Message template (Telegram/Slack)

- Header: `[투자-국내]` or `[투자-해외]`
- 10–15 lines total.
- Prefer bullets.

Example sections:
- 총 평가금액
- 누적 손익 / 누적 수익률
- 최근 1일 손익(전일 대비)
- Top holdings TOP5 (name/broker/weight/return)
- Top losers TOP5 (name/pnl/return)
- Triggers: 1–2 lines

## 스크립트

| 파일 | 용도 | 티어 |
|------|------|------|
| `scripts/portfolio_report.py` | vault markdown 파싱 → JSON 요약 생성 | Tier 1 |
| `scripts/render_report.py` | JSON → 텔레그램 메시지 렌더링 | Tier 1 |
| `scripts/toss_parse_snapshot.py` | 토스증권 스냅샷 파싱 (일별 비교용) | Tier 1 |
