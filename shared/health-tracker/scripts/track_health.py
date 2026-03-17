#!/usr/bin/env python3
"""Record daily health check-in — SQLite 저장."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn, upsert_check_in


def record_checkin(sleep_hours=None, sleep_quality=None, steps=None,
                   workout=False, stress=None, water=None, notes=""):
    date_str = datetime.now().strftime("%Y-%m-%d")
    data = {
        "date": date_str,
        "sleep_hours": sleep_hours,
        "sleep_quality": sleep_quality,
        "steps": steps,
        "workout": 1 if workout else 0,
        "stress": stress,
        "water_ml": water,
        "notes": notes or None,
    }

    conn = get_conn()
    try:
        upsert_check_in(conn, data)
        conn.commit()
    finally:
        conn.close()

    print(f"Check-in recorded: {date_str}")
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


def main():
    parser = argparse.ArgumentParser(description="Record daily health check-in")
    parser.add_argument("--sleep-hours", type=float)
    parser.add_argument("--sleep-quality", type=int)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--workout", action="store_true", default=False)
    parser.add_argument("--stress", type=int)
    parser.add_argument("--water", type=int, help="Water intake in ml")
    parser.add_argument("--notes", type=str, default="")
    args = parser.parse_args()

    if all(v is None or v is False or v == "" for v in [
        args.sleep_hours, args.sleep_quality, args.steps,
        args.workout if args.workout else None,
        args.stress, args.water, args.notes if args.notes else None,
    ]):
        parser.print_help()
        sys.exit(0)

    record_checkin(args.sleep_hours, args.sleep_quality, args.steps,
                   args.workout, args.stress, args.water, args.notes)


if __name__ == "__main__":
    main()
