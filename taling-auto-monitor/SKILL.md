---
name: taling-auto-monitor
description: 탈잉 챌린지 자동 감지 (Telegram) → 체크리스트 생성 → Obsidian vault 저장
---

# Taling Auto Monitor Skill


**Version:** 2.0.0
**Updated:** 2026-02-11
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Production

**Type:** Tier 1 (Pure Script)
**Token Cost:** 0 (No LLM calls)

## Purpose

Auto-detect and track Taling Challenge file uploads in JARVIS HQ topic 168.
- Generate checklist with ✅/❌/⚠️ + evidence
- Save to Obsidian vault (`~/mingming-vault/taling/checklists/`) with Dataview-queryable frontmatter
- Send formatted Telegram message with results
- Append Google Form link when ALL items complete

## Integration Points

- **Input**: Telegram Bot API (getUpdates polling)
- **State**: `memory/taling_checklist_state.json`
- **Output**: Obsidian vault (Dataview-queryable markdown) + Telegram alerts
- **Google Form**: Auto-appended on complete checklist

## Vault Structure

```
~/mingming-vault/taling/
  checklists/
    2026-02-09.md    # Daily checklist with frontmatter
    2026-02-10.md
    ...
```

### Frontmatter Schema

```yaml
---
type: taling-checklist
date: 2026-02-09
day_type: 월수금
status: Done          # "Done" | "In Progress"
passed: 8
total: 8
all_complete: true
updated: 2026-02-09 23:00
---
```

### Dataview Query Example

```dataview
TABLE date, status, passed + "/" + total AS "Progress"
FROM "taling/checklists"
WHERE type = "taling-checklist"
SORT date DESC
LIMIT 14
```

## Scripts

| Script | Purpose |
|--------|---------|
| `checklist_automation.py` | Main automation (Obsidian vault + Google Form) |
| `test_checklist_automation.py` | Unit tests |
| `scripts/taling_io.py` | Obsidian vault I/O helper (read/write markdown with frontmatter) |

## Invocation

```bash
# Checklist automation (recommended)
*/10 8-23 * * * /Users/dayejeong/clawd/skills/taling-auto-monitor/checklist_automation.py check

# Manual
./checklist_automation.py check
./checklist_automation.py reset

# Run tests
python test_checklist_automation.py
```

## Architecture Rationale

**Why Tier 1 (Script)?**
- File pattern matching is deterministic (regex)
- Message parsing is rule-based (JSON)
- No natural language understanding needed
- State tracking is simple key-value storage
- 0 tokens vs 500-1000 tokens for LLM-based solution

**Why Obsidian vault (not Notion)?**
- No API key or network dependency for storage
- Local-first, works offline
- Dataview plugin enables rich queries without external services
- Consistent with other skills (health-tracker uses same pattern)
- Simpler deployment, fewer failure modes

**Why Cron Polling (not Webhook)?**
- Taling challenge doesn't require real-time response (10min delay OK)
- No public URL needed for local MacBook
- Simpler deployment, easier debugging

## Token Economics

**This approach:** 0 tokens
**LLM-based alternative:** ~500 tokens/check x 78 checks/day = 39,000 tokens/day
**60-day challenge:** 2,340,000 tokens saved
