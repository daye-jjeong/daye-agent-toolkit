#!/usr/bin/env python3
"""One-off: backfill '기타' tags using auto_tag.

Usage:
    python3 backfill_tags.py              # dry-run (변경 사항만 출력)
    python3 backfill_tags.py --apply      # 실제 DB 업데이트
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn, update_daily_stats
from _sync_common import auto_tag


def main():
    parser = argparse.ArgumentParser(description="Backfill '기타' tags")
    parser.add_argument("--apply", action="store_true", help="Actually update DB")
    args = parser.parse_args()

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, source, session_id, repo, tag, summary, raw_json "
            "FROM activities WHERE tag = '기타' OR tag = '' OR tag IS NULL"
        ).fetchall()
        print(f"Found {len(rows)} untagged/기타 activities", file=sys.stderr)

        updated = 0
        for r in rows:
            try:
                raw = json.loads(r["raw_json"] or "{}")
                summary = r["summary"] or ""
                topic = raw.get("topic", "")
                commands = " ".join(raw.get("commands", [])[:5])
                new_tag = auto_tag(summary, topic, commands)
                if new_tag != "기타":
                    print(f"  [{r['source']}] {r['session_id'][:8]}.. "
                          f"{r['repo']}: {r['tag']!r} → {new_tag!r}  ({summary[:60]})")
                    if args.apply:
                        conn.execute(
                            "UPDATE activities SET tag = ? WHERE id = ?",
                            (new_tag, r["id"]),
                        )
                    updated += 1
            except Exception as e:
                print(f"  [SKIP] {r['session_id'][:8]}: {e}", file=sys.stderr)

        if args.apply and updated > 0:
            conn.commit()
            # daily_stats도 재계산
            dates = conn.execute(
                "SELECT DISTINCT substr(start_at, 1, 10) as d FROM activities"
            ).fetchall()
            for d in dates:
                update_daily_stats(conn, d["d"])
            conn.commit()

        print(f"\n{'Applied' if args.apply else 'Would update'}: {updated}/{len(rows)} activities",
              file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
