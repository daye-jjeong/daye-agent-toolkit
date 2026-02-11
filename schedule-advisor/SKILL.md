---
name: schedule-advisor
description: 캘린더 데이터 기반 브리핑, 알림, 일정 추천
---

# Schedule Advisor

**Version:** 0.1.0 | **Updated:** 2026-02-03 | **Status:** Experimental
**Type:** Hybrid Skill (Data Script + LLM Analysis)

## Overview

Schedule Advisor is the decision layer of the hybrid schedule management system.
Receives structured JSON from `fetch_schedule.py` and generates intelligent briefings, alerts, and recommendations.

## Trigger

Runs via cron (brief/check/remind modes) or manual invocation.

## Modes

### 1. brief -- Morning briefing (8:00 AM)
- Input: Today's events (from `fetch_schedule.py --today`)
- Output: Timeline view, priority markers (P0/P1), preparation suggestions

### 2. check -- Midday check-in (2:00 PM)
- Input: Remaining today events
- Output: Completed vs remaining, upcoming alerts, encouragement

### 3. remind -- Proactive P0 alerts (every 30 min, 8AM-8PM)
- Input: Next 30-60 min events
- Output: Urgent alerts for P0 tasks, 10-40 min advance warning

## Core Workflow

1. `fetch_schedule.py` fetches calendar data via gog API (0 tokens)
2. Pipe JSON to `schedule_advisor.py` with mode argument
3. LLM analyzes, prioritizes, and formats output (200-400 tokens)
4. Send result to Telegram topic 167

## Usage

```bash
# Fetch + analyze
python3 ~/clawd/scripts/fetch_schedule.py today | \
  python3 ~/clawd/skills/schedule-advisor/schedule_advisor.py brief
```

### Cron (production)

```cron
0 8 * * *     fetch_schedule.py today | schedule_advisor.py brief
0 14 * * *    fetch_schedule.py today | schedule_advisor.py check
*/30 8-20 * * * fetch_schedule.py today | schedule_advisor.py remind
```

## Configuration

| Setting | Value |
|---------|-------|
| Telegram Group | `-1003242721592` (JARVIS HQ) |
| Telegram Topic | `167` |
| Priority Keywords | P0 (critical), P1 (high), default (normal) |
| Excluded Calendars | "로닉 공용", "Ronik Public", "SKT" |

## Architecture & Token Economics

Hybrid pipeline: deterministic data fetch (0 tokens) + LLM analysis (200-400 tokens).
75% token reduction vs monolithic approach.

**상세 (pipeline diagram, input JSON format, design rationale, migration notes)**: `{baseDir}/references/architecture-detail.md` 참고

## See Also

- **scripts/fetch_schedule.py:** Data fetching component
- **AGENTS.md:** Three-tier architecture policy
