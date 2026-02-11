# Goal Planner Auto-Draft Rules

## Weekly Goal Auto-Generation Rules

1. Monthly goals with `priority: high` included first
2. KRs with empty `current` or low progress prioritized
3. Calendar events for the week's projects reflected
4. Maximum 5 goals (realistic scope)

## Daily Goal Auto-Generation Rules

1. Extract from weekly goals with `status: in_progress` or `todo`
2. Place today's calendar events in time_blocks first
3. Auto-place goal-related work in empty time slots
4. Energy level adjustments:
   - high: Difficult tasks in the morning
   - medium: Even distribution
   - low: Light tasks only, include rest time
5. top3 selects only the 3 highest-impact items

## Script Commands

```bash
# Monthly goal creation
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py monthly

# Weekly goal (auto-draft from monthly)
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py weekly

# Daily goal (auto-draft from weekly + calendar)
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py daily

# Specific date
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py daily --date 2026-02-11

# Dry-run (output only, no file creation)
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py weekly --dry-run

# Retrospective mode
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py retro --type daily
```

## Cron Integration (Recommended)

```
매일 08:30  -> create_goal.py daily --auto (auto-create + Telegram send)
매주 월 08:00 -> create_goal.py weekly --auto
매월 1일 09:00 -> create_goal.py monthly --interactive (interactive)
```
