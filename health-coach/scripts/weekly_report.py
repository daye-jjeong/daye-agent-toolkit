#!/usr/bin/env python3
"""
Generate weekly health report from Obsidian vault data.

Reads last 7 days of check-ins, exercises, and symptoms from
~/mingming-vault/health/ and computes summary statistics.
stdlib only.
"""

import sys
import argparse
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import health_io


def generate_weekly_report():
    """Build weekly health report from Obsidian data."""
    today = date.today()
    week_start = today - timedelta(days=6)
    week_end = today

    header = (
        f"Weekly Health Report\n"
        f"{week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}\n"
        f"{'=' * 60}"
    )

    # ── Read data ──────────────────────────────────────
    checkins = health_io.read_entries("check-ins", days=7)
    exercises = health_io.read_entries("exercises", days=7)
    symptoms = health_io.read_entries("symptoms", days=7)

    lines = [header, ""]

    # ── Check-in stats ─────────────────────────────────
    lines.append("CHECK-IN SUMMARY")
    lines.append("-" * 40)

    if not checkins:
        lines.append("No check-in data for the past 7 days.")
        lines.append("Use track_health.py to start recording.")
    else:
        lines.append(f"Days recorded: {len(checkins)}/7")
        lines.append("")

        # Sleep
        sleep_hours = [
            fm.get("sleep_hours")
            for _, fm in checkins
            if fm.get("sleep_hours") is not None
        ]
        sleep_quality = [
            fm.get("sleep_quality")
            for _, fm in checkins
            if fm.get("sleep_quality") is not None
        ]

        if sleep_hours:
            avg_sleep = sum(sleep_hours) / len(sleep_hours)
            min_sleep = min(sleep_hours)
            max_sleep = max(sleep_hours)
            lines.append(
                f"Sleep: avg {avg_sleep:.1f}h "
                f"(range: {min_sleep:.1f}-{max_sleep:.1f}h, "
                f"{len(sleep_hours)} days recorded)"
            )
            good_sleep = sum(1 for h in sleep_hours if h >= 7)
            lines.append(f"  7h+ goal: {good_sleep}/{len(sleep_hours)} days")
        if sleep_quality:
            avg_qual = sum(sleep_quality) / len(sleep_quality)
            lines.append(f"  Quality: avg {avg_qual:.1f}/10")

        # Steps
        steps_data = [
            fm.get("steps")
            for _, fm in checkins
            if fm.get("steps") is not None
        ]
        if steps_data:
            avg_steps = sum(steps_data) / len(steps_data)
            lines.append(
                f"Steps: avg {avg_steps:.0f}/day "
                f"({len(steps_data)} days recorded)"
            )

        # Workout
        workout_days = sum(
            1 for _, fm in checkins if fm.get("workout") is True
        )
        lines.append(f"Workout days: {workout_days}/{len(checkins)}")

        # Stress
        stress_data = [
            fm.get("stress")
            for _, fm in checkins
            if fm.get("stress") is not None
        ]
        if stress_data:
            avg_stress = sum(stress_data) / len(stress_data)
            lines.append(f"Stress: avg {avg_stress:.1f}/10")

        # Water
        water_data = [
            fm.get("water")
            for _, fm in checkins
            if fm.get("water") is not None
        ]
        if water_data:
            avg_water = sum(water_data) / len(water_data)
            good_water = sum(1 for w in water_data if w >= 1500)
            lines.append(
                f"Water: avg {avg_water:.0f}ml/day "
                f"(1.5L+ goal: {good_water}/{len(water_data)} days)"
            )

    lines.append("")

    # ── Exercise stats ─────────────────────────────────
    lines.append("EXERCISE LOG")
    lines.append("-" * 40)

    if not exercises:
        lines.append("No exercise records for the past 7 days.")
    else:
        lines.append(f"Total exercise entries: {len(exercises)}")
        # Group by exercise name
        ex_counts = {}
        for _, fm in exercises:
            name = fm.get("name", fm.get("exercise", "unknown"))
            ex_counts[name] = ex_counts.get(name, 0) + 1
        for name, count in sorted(ex_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {name}: {count}x")

    lines.append("")

    # ── Symptom stats ──────────────────────────────────
    lines.append("SYMPTOM LOG")
    lines.append("-" * 40)

    if not symptoms:
        lines.append("No symptom records for the past 7 days. (Good!)")
    else:
        lines.append(f"Total symptom entries: {len(symptoms)}")
        sym_counts = {}
        sev_sums = {}
        for _, fm in symptoms:
            name = fm.get("symptom", fm.get("name", "unknown"))
            sym_counts[name] = sym_counts.get(name, 0) + 1
            sev = fm.get("severity", fm.get("intensity", 0))
            if isinstance(sev, (int, float)):
                sev_sums[name] = sev_sums.get(name, 0) + sev

        for name, count in sorted(sym_counts.items(), key=lambda x: -x[1]):
            avg_sev = sev_sums.get(name, 0) / count if count else 0
            lines.append(f"  {name}: {count}x (avg severity: {avg_sev:.1f})")

    lines.append("")

    # ── Insights ───────────────────────────────────────
    lines.append("=" * 60)
    lines.append("INSIGHTS")
    lines.append("-" * 40)

    if checkins:
        # Generate data-driven insights
        sleep_hrs = [
            fm.get("sleep_hours")
            for _, fm in checkins
            if fm.get("sleep_hours") is not None
        ]
        if sleep_hrs:
            avg = sum(sleep_hrs) / len(sleep_hrs)
            if avg < 7:
                lines.append(
                    f"  - Sleep deficit: averaging {avg:.1f}h. "
                    "Aim for 7-8 hours."
                )
            else:
                lines.append(
                    f"  - Sleep on track: averaging {avg:.1f}h."
                )

        workout_ct = sum(1 for _, fm in checkins if fm.get("workout") is True)
        if workout_ct < 3:
            lines.append(
                f"  - Only {workout_ct} workout days. "
                "Target: 3+ per week."
            )
        else:
            lines.append(f"  - Good workout consistency: {workout_ct} days.")

        if symptoms:
            lines.append(
                f"  - {len(symptoms)} symptom entries recorded. "
                "Review patterns with: coach.py analyze-symptoms"
            )
    else:
        lines.append("  - Start recording daily check-ins for personalized insights.")
        lines.append("  - Use: track_health.py --sleep-hours 7 --steps 8000 ...")

    lines.append("")
    lines.append(
        "Consistency is the key to longevity. "
        "Small daily actions compound over time."
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly health report from Obsidian vault data"
    )
    parser.parse_args()
    print(generate_weekly_report())


if __name__ == "__main__":
    main()
