#!/usr/bin/env python3
"""task 품질 검증 — tag/summary/segments/repo 체크 + --fix 모드.

Usage:
    python3 validate_tasks.py --date 2026-03-31
    python3 validate_tasks.py --fix --date 2026-03-31
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "shared" / "life-dashboard-mcp"))
from db import get_conn, _VALID_TAGS

KST = timezone(timedelta(hours=9))


def validate(date_str: str, fix: bool = False) -> list[str]:
    conn = get_conn()
    errors = []

    rows = conn.execute("SELECT * FROM tasks WHERE date = ?", (date_str,)).fetchall()
    if not rows:
        print(f"[validate_tasks] {date_str}: 0 tasks — nothing to validate", file=sys.stderr)
        conn.close()
        return []

    for r in rows:
        tid = r["id"]
        # 1. tag 유효성
        if r["tag"] not in _VALID_TAGS:
            errors.append(f"task {tid}: invalid tag '{r['tag']}'")
            if fix:
                conn.execute("UPDATE tasks SET tag = '기타' WHERE id = ?", (tid,))

        # 2. summary 길이
        if not r["summary"] or len(r["summary"]) < 10:
            errors.append(f"task {tid}: summary too short: '{r['summary']}'")

        # 3. repo NULL
        if not r["repo"]:
            errors.append(f"task {tid}: repo is NULL")

        # 4. segments JSON 유효성
        try:
            segs = json.loads(r["segments"]) if isinstance(r["segments"], str) else r["segments"]
            if not isinstance(segs, list):
                errors.append(f"task {tid}: segments is not a list")
        except (json.JSONDecodeError, TypeError):
            errors.append(f"task {tid}: segments is invalid JSON")

        # 5. duration_min > 0
        if (r["duration_min"] or 0) <= 0:
            errors.append(f"task {tid}: duration_min is {r['duration_min']}")

    # 6. 중복 summary 검사
    summaries = [r["summary"] for r in rows]
    from collections import Counter
    for s, cnt in Counter(summaries).items():
        if cnt >= 3:
            errors.append(f"duplicate summary x{cnt}: '{s[:50]}'")

    if fix:
        conn.commit()
    conn.close()

    for e in errors:
        print(f"  ERROR: {e}", file=sys.stderr)
    print(f"[validate_tasks] {date_str}: {len(rows)} tasks, {len(errors)} errors", file=sys.stderr)
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()
    errors = validate(args.date, args.fix)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
