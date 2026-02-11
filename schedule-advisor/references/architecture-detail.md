# Schedule Advisor Architecture Detail

## Hybrid Pipeline

```
┌─────────────────────┐
│ scripts/            │
│ fetch_schedule.py   │ <- Pure data fetching (0 tokens)
│ • gog calendar API  │
│ • Filter/normalize  │
│ • Output JSON       │
└──────────┬──────────┘
           │ JSON
           ▼
┌─────────────────────┐
│ skills/             │
│ schedule-advisor    │ <- LLM analysis (200-400 tokens)
│ • Prioritization    │
│ • Formatting        │
│ • Alerts            │
│ • Suggestions       │
└──────────┬──────────┘
           │
           ▼
      Telegram
```

## Input Format

Expects JSON from stdin with structure:
```json
{
  "metadata": {
    "fetch_time": "2026-02-02T08:00:00+09:00",
    "time_filter": "today",
    "total_events": 5
  },
  "events": [
    {
      "summary": "P0 Team standup",
      "start": {"dateTime": "2026-02-02T09:00:00+09:00"},
      "_is_all_day": false,
      "_start_hour": 9,
      "_start_minute": 0,
      "location": "Zoom",
      "attendees": [...]
    }
  ]
}
```

## Token Economics

**Before (monolithic skill):**
- 800-1,200 tokens per invocation
- 3-5 daily invocations = 2,400-6,000 tokens/day

**After (hybrid):**
- Data fetching: 0 tokens (pure script)
- Analysis only: 200-400 tokens per invocation
- 3-5 daily invocations = 600-2,000 tokens/day

**Savings:** 75% reduction (1,800-4,000 tokens/day saved)

## Design Rationale

### Why Hybrid?

**Data fetching is deterministic:**
- gog API calls are pure I/O
- Calendar filtering is rule-based
- Date/time parsing requires no NLP
- Script can handle with 0 tokens

**Analysis requires judgment:**
- Prioritization based on context
- Natural language formatting
- Personalized suggestions ("준비물 챙기세요")
- Motivational messaging
- LLM adds value here

This is the canonical example of a **hybrid architecture** candidate:
- Clear separation between data and decision
- Deterministic fetch, intelligent analysis
- High token savings with zero quality loss

## Migration Notes

**Deprecated:** `skills/schedule-manager/schedule_manager.py` (monolithic)
**Replaced by:** Two-component hybrid (2026-02-02)

**Breaking changes:**
- Cron jobs must be updated to use pipeline syntax
- Output format unchanged (transparent to user)

**Rollback:**
- Old monolithic script preserved at `skills/schedule-manager/schedule_manager.py.backup`
- Can revert cron if issues arise
