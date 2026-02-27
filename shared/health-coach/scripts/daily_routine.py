#!/usr/bin/env python3
"""
Generate daily health routine checklist.

Reads today's check-in from Obsidian vault (if exists) to show progress.
stdlib only.
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import health_io


def get_daily_tip(weekday):
    """Day-of-week longevity tips."""
    tips = [
        "Monday: Antioxidant foods - blueberries, green tea, dark chocolate",
        "Tuesday: Protein 60g target - muscle maintenance is key to anti-aging",
        "Wednesday: Sunlight 15+ min - vitamin D synthesis for bone health",
        "Thursday: Stress management - meditation/breathing to reduce cortisol",
        "Friday: Sleep quality check - deep sleep is key to cell regeneration",
        "Saturday: Strength training - core strengthening + metabolic improvement",
        "Sunday: Weekly review - check this week's completion rate & set next week's goals",
    ]
    return tips[weekday]


def generate_daily_checklist():
    """Generate daily routine checklist, enriched with today's check-in data."""
    now = datetime.now()
    day_str = now.strftime("%Y-%m-%d (%A)")
    today_str = health_io.today()

    # Read today's check-in if available
    checkins = health_io.read_entries("check-ins", days=1)
    today_data = None
    for _, fm in checkins:
        if str(fm.get("date", "")) == today_str:
            today_data = fm
            break

    # Build progress section
    progress_lines = []
    if today_data:
        progress_lines.append("Today's check-in data:")
        if today_data.get("sleep_hours") is not None:
            sh = today_data["sleep_hours"]
            sq = today_data.get("sleep_quality", "?")
            progress_lines.append(f"  Sleep: {sh}h (quality: {sq}/10)")
        if today_data.get("steps") is not None:
            progress_lines.append(f"  Steps: {today_data['steps']}")
        if today_data.get("workout") is not None:
            progress_lines.append(
                f"  Workout: {'done' if today_data['workout'] else 'not yet'}"
            )
        if today_data.get("water") is not None:
            progress_lines.append(f"  Water: {today_data['water']}ml")
        if today_data.get("stress") is not None:
            progress_lines.append(f"  Stress: {today_data['stress']}/10")
    else:
        progress_lines.append("No check-in recorded yet today.")
        progress_lines.append(
            "Use track_health.py to record your daily metrics."
        )

    progress = "\n".join(progress_lines)

    checklist = f"""Daily Health Routine - {day_str}
{"=" * 60}

Morning (after waking up)
[ ] Record sleep (hours, quality)
[ ] Drink 500ml water
[ ] Stretching 5 min (neutral spine, breathing)
[ ] Breakfast (protein 20g+)

Afternoon
[ ] Walk after lunch (10+ min)
[ ] Lunch (high vegetable ratio)
[ ] Sunlight 15+ min
[ ] Drink 500ml more water

Evening
[ ] Walk after dinner (10+ min)
[ ] Light dinner (protein-focused)
[ ] PT homework / core exercise
[ ] Stress relief (meditation/breathing 10 min)

Before bed (23:00-23:30)
[ ] End screen time
[ ] Bedtime routine
[ ] Asleep before 00:00

{"=" * 60}

{progress}

{"=" * 60}

Tip of the day:
{get_daily_tip(now.weekday())}

Don't forget your evening check-in!"""

    return checklist


def main():
    parser = argparse.ArgumentParser(
        description="Generate daily health routine checklist"
    )
    parser.parse_args()
    print(generate_daily_checklist())


if __name__ == "__main__":
    main()
