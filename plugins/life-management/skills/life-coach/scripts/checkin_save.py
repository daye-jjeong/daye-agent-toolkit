#!/usr/bin/env python3
"""checkin_save — daily_checkin wrapper.

Subcommands:
  morning  — 캐파(available/energy/blockers) value/skip tri-state + intent + WIP ids
  evening  — reflection만

Usage:
  checkin_save.py morning --date YYYY-MM-DD
    (--available-hours N | --skip-available)
    (--energy low|mid|high | --skip-energy)
    (--blockers TEXT | --skip-blockers)
    [--morning-intent TEXT] [--wip-ids 13,20]

  checkin_save.py evening --date YYYY-MM-DD --evening-reflection TEXT
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "mcp" / "life-dashboard"))
from db import get_conn, upsert_daily_checkin, get_daily_checkin


def _resolve_tri_state(value, skip, name: str) -> tuple:
    if value is not None and skip:
        sys.exit(f"error: --{name} and --skip-{name} are mutually exclusive")
    if value is None and not skip:
        sys.exit(f"error: --{name} or --skip-{name} required")
    if skip:
        return None, "skipped"
    return value, "answered"


def cmd_morning(args):
    avail_value = int(args.available_hours * 60) if args.available_hours is not None else None
    avail_min, avail_status = _resolve_tri_state(avail_value, args.skip_available, "available")
    energy, energy_status = _resolve_tri_state(args.energy, args.skip_energy, "energy")
    blockers, blockers_status = _resolve_tri_state(args.blockers, args.skip_blockers, "blockers")
    wip_ids = [int(x) for x in args.wip_ids.split(",")] if args.wip_ids else None

    conn = get_conn()
    try:
        upsert_daily_checkin(
            conn, args.date,
            available_min=avail_min, available_status=avail_status,
            energy=energy, energy_status=energy_status,
            blockers=blockers, blockers_status=blockers_status,
            morning_intent=args.morning_intent,
            morning_wip_ids=wip_ids,
        )
        conn.commit()
        json.dump(get_daily_checkin(conn, args.date), sys.stdout, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


def cmd_evening(args):
    conn = get_conn()
    try:
        upsert_daily_checkin(conn, args.date, evening_reflection=args.evening_reflection)
        conn.commit()
        json.dump(get_daily_checkin(conn, args.date), sys.stdout, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("morning")
    m.add_argument("--date", required=True)
    m.add_argument("--available-hours", type=float)
    m.add_argument("--skip-available", action="store_true")
    m.add_argument("--energy", choices=["low", "mid", "high"])
    m.add_argument("--skip-energy", action="store_true")
    m.add_argument("--blockers")
    m.add_argument("--skip-blockers", action="store_true")
    m.add_argument("--morning-intent")
    m.add_argument("--wip-ids")
    m.set_defaults(func=cmd_morning)

    e = sub.add_parser("evening")
    e.add_argument("--date", required=True)
    e.add_argument("--evening-reflection", required=True)
    e.set_defaults(func=cmd_evening)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
