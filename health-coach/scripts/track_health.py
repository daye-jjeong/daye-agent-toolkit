#!/usr/bin/env python3
"""
Record daily health check-in metrics to Obsidian vault.

Writes a .md file to ~/openclaw/vault/health/check-ins/ with frontmatter
containing sleep, steps, workout, stress, water, and notes.
stdlib only.
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import health_io


def record_checkin(
    sleep_hours=None,
    sleep_quality=None,
    steps=None,
    workout=False,
    stress=None,
    water=None,
    notes="",
):
    """Write a check-in entry to health/check-ins/."""
    date_str = health_io.today()
    filename = f"checkin-{date_str}.md"

    frontmatter = {
        "date": date_str,
        "type": "check-in",
    }

    if sleep_hours is not None:
        frontmatter["sleep_hours"] = sleep_hours
    if sleep_quality is not None:
        frontmatter["sleep_quality"] = sleep_quality
    if steps is not None:
        frontmatter["steps"] = steps
    frontmatter["workout"] = workout
    if stress is not None:
        frontmatter["stress"] = stress
    if water is not None:
        frontmatter["water"] = water

    body = ""
    if notes:
        body = f"## Notes\n\n{notes}"

    fpath = health_io.write_entry("check-ins", filename, frontmatter, body)
    print(f"Check-in recorded: {fpath}")

    # Print summary
    print(f"\n  Date: {date_str}")
    if sleep_hours is not None:
        print(f"  Sleep: {sleep_hours}h", end="")
        if sleep_quality is not None:
            print(f" (quality: {sleep_quality}/10)", end="")
        print()
    if steps is not None:
        print(f"  Steps: {steps}")
    print(f"  Workout: {'yes' if workout else 'no'}")
    if stress is not None:
        print(f"  Stress: {stress}/10")
    if water is not None:
        print(f"  Water: {water}ml")
    if notes:
        print(f"  Notes: {notes}")


def main():
    parser = argparse.ArgumentParser(
        description="Record daily health check-in to Obsidian vault"
    )
    parser.add_argument(
        "--sleep-hours", type=float, help="Hours of sleep (e.g., 7.5)"
    )
    parser.add_argument(
        "--sleep-quality", type=int, help="Sleep quality 1-10"
    )
    parser.add_argument("--steps", type=int, help="Step count")
    parser.add_argument(
        "--workout",
        action="store_true",
        default=False,
        help="Exercised today",
    )
    parser.add_argument("--stress", type=int, help="Stress level 1-10")
    parser.add_argument("--water", type=int, help="Water intake in ml")
    parser.add_argument("--notes", type=str, default="", help="Free-text notes")

    args = parser.parse_args()

    # If no args at all, show help
    if all(
        v is None or v is False or v == ""
        for v in [
            args.sleep_hours,
            args.sleep_quality,
            args.steps,
            args.workout if args.workout else None,
            args.stress,
            args.water,
            args.notes if args.notes else None,
        ]
    ):
        parser.print_help()
        print("\nExample:")
        print(
            "  python3 track_health.py --sleep-hours 7.5 --sleep-quality 8 "
            "--steps 8500 --workout --stress 3 --water 2000 --notes 'Felt good'"
        )
        sys.exit(0)

    record_checkin(
        sleep_hours=args.sleep_hours,
        sleep_quality=args.sleep_quality,
        steps=args.steps,
        workout=args.workout,
        stress=args.stress,
        water=args.water,
        notes=args.notes,
    )


if __name__ == "__main__":
    main()
