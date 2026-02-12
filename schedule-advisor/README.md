# Schedule Advisor - Hybrid Architecture Example

This skill demonstrates the **three-tier hybrid pattern** introduced in Feb 2026.

## Quick Start

### Test the pipeline locally

```bash
# Test data fetching (should output JSON)
python3 skills/schedule-advisor/scripts/fetch_schedule.py today

# Test full pipeline (fetch → analyze)
python3 skills/schedule-advisor/scripts/fetch_schedule.py today | \
  python3 skills/schedule-advisor/schedule_advisor.py brief
```

### Update cron jobs

**Old (monolithic):**
```cron
0 8 * * * /Users/dayejeong/openclaw/skills/schedule-manager/schedule_manager.py brief
```

**New (hybrid pipeline):**
```cron
0 8 * * * /Users/dayejeong/openclaw/skills/schedule-advisor/scripts/fetch_schedule.py --today | /Users/dayejeong/openclaw/skills/schedule-advisor/schedule_advisor.py brief
```

## Architecture Benefits

1. **Token savings:** 75% reduction (data fetching is free)
2. **Separation of concerns:** Data vs decision logic
3. **Easier testing:** Can test fetch/analysis independently
4. **Reusability:** Other skills can consume fetch_schedule.py output

## Files

- `scripts/fetch_schedule.py` - Data fetching (0 tokens)
- `skills/schedule-advisor/schedule_advisor.py` - Analysis (200-400 tokens)
- `SKILL.md` - Full documentation

## Migration Checklist

- [x] Create fetch_schedule.py script
- [x] Create schedule-advisor skill
- [ ] Update cron jobs (manual step required)
- [ ] Test for 1 week
- [ ] Remove old schedule_manager.py (or archive)

## Rollback Plan

If issues arise:
```bash
# Restore old cron
crontab -e
# Replace pipeline with: skills/schedule-manager/schedule_manager.py.backup

# Verify backup exists
ls -la skills/schedule-manager/schedule_manager.py.backup
```
