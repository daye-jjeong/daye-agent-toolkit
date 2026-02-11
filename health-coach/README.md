# Health Coach

**AI-powered health advisor for personalized wellness guidance & longevity management**

## Purpose

Health Coach analyzes data collected by Health Tracker and provides tailored health advice, focusing on:
- Safe exercise routines (considering herniated disc)
- Symptom pattern analysis
- Exercise form guidance
- Lifestyle optimization
- Integrated longevity (저속노화) routine management

## Key Features

1. **Exercise Routine Suggestions** - Disc-safe core workouts
2. **Symptom Analysis** - Pattern recognition and triggers
3. **PT Homework Guide** - Detailed form instructions
4. **Lifestyle Advice** - Sleep, diet, stress management
5. **Daily Routine Management** - Morning/afternoon/evening/bedtime checklists
6. **Health Tracking** - Sleep, steps, workout, stress, water intake
7. **Weekly Reports** - Health data aggregation and trend analysis

## Quick Start

### Health Coach Commands
```bash
# Suggest a 15-minute core routine
python3 scripts/coach.py suggest-routine --duration 15 --focus core

# Analyze symptoms from the past week
python3 scripts/coach.py analyze-symptoms --period 7days

# Get detailed guide for an exercise
python3 scripts/coach.py guide-exercise --exercise "플랭크"
```

### Longevity Commands
```bash
# Check today's daily routine checklist
python3 scripts/daily_routine.py

# Track health metrics (sleep, steps, workout, etc.)
python3 scripts/track_health.py

# Generate weekly health report
python3 scripts/weekly_report.py
```

## Documentation

See `SKILL.md` for detailed usage, configuration, and automation setup.

## Safety First

All exercise recommendations:
- ✅ Neutral spine focus
- ✅ Controlled breathing
- ✅ Progressive difficulty
- ❌ No hyperextension
- ❌ No excessive rotation
- ❌ No pain-causing movements
