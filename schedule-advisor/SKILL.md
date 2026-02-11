# Schedule Advisor


**Version:** 0.1.0
**Updated:** 2026-02-03
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

**Type:** Hybrid Skill (Data Script + LLM Analysis)  
**Architecture:** Part of the three-tier hybrid pattern

## Overview

Schedule Advisor is the **decision layer** of the hybrid schedule management system. It receives structured JSON from `fetch_schedule.py` and generates intelligent briefings, alerts, and recommendations.

## Architecture

### Hybrid Pipeline

```
┌─────────────────────┐
│ scripts/            │
│ fetch_schedule.py   │ ← Pure data fetching (0 tokens)
│ • gog calendar API  │
│ • Filter/normalize  │
│ • Output JSON       │
└──────────┬──────────┘
           │ JSON
           ▼
┌─────────────────────┐
│ skills/             │
│ schedule-advisor    │ ← LLM analysis (200-400 tokens)
│ • Prioritization    │
│ • Formatting        │
│ • Alerts            │
│ • Suggestions       │
└──────────┬──────────┘
           │
           ▼
      Telegram
```

## Modes

### 1. **brief** - Morning briefing
- Time: 8:00 AM daily
- Input: Today's events (from `fetch_schedule.py --today`)
- Output: Formatted briefing with:
  - Timeline view
  - Priority markers (P0/P1)
  - Preparation suggestions

### 2. **check** - Midday check-in
- Time: 2:00 PM daily
- Input: Remaining today events
- Output: Progress check with:
  - Completed vs remaining
  - Upcoming alerts
  - Encouragement message

### 3. **remind** - Proactive P0 alerts
- Time: Every 30 mins (8 AM - 8 PM)
- Input: Next 30-60 min events
- Output: Urgent alerts for:
  - P0 tasks
  - "중요" / "Urgent" keywords
  - 10-40 min advance warning

## Usage

### Command-line (development)
```bash
# Fetch data + analyze
python3 ~/clawd/scripts/fetch_schedule.py today | \
  python3 ~/clawd/skills/schedule-advisor/schedule_advisor.py brief

# Direct skill invocation (for testing)
python3 ~/clawd/skills/schedule-advisor/schedule_advisor.py brief < sample_events.json
```

### Cron (production)
```cron
# Morning brief: fetch → analyze
0 8 * * * /Users/dayejeong/clawd/scripts/fetch_schedule.py today | /Users/dayejeong/clawd/skills/schedule-advisor/schedule_advisor.py brief

# Midday check
0 14 * * * /Users/dayejeong/clawd/scripts/fetch_schedule.py today | /Users/dayejeong/clawd/skills/schedule-advisor/schedule_advisor.py check

# P0 reminders (every 30 min, 8am-8pm)
*/30 8-20 * * * /Users/dayejeong/clawd/scripts/fetch_schedule.py today | /Users/dayejeong/clawd/skills/schedule-advisor/schedule_advisor.py remind
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

## Configuration

**Telegram Output:**
- Group ID: `-1003242721592` (JARVIS HQ)
- Topic ID: `167` (📅 일정/준비 관련)

**Priority Keywords:**
- P0: Critical/urgent tasks
- P1: High priority
- (no marker): Normal priority

**Excluded Calendars:**
- "로닉 공용", "Ronik Public", "SKT" (filtered in fetch_schedule.py)

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
- → Script can handle with 0 tokens

**Analysis requires judgment:**
- Prioritization based on context
- Natural language formatting
- Personalized suggestions ("준비물 챙기세요")
- Motivational messaging
- → LLM adds value here

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

## See Also

- **AGENTS.md:** Three-tier architecture policy (Script/Hybrid/Skill)
- **scripts/fetch_schedule.py:** Data fetching component
- **docs/skills_audit_2026-02-02.md:** Conversion rationale
