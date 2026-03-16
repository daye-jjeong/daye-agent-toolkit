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
from activity_writer import auto_tag


def main():
    parser = argparse.ArgumentParser(description="Backfill '기타' tags")
    parser.add_argument("--apply", action="store_true", help="Actually update DB")
    args = parser.parse_args()

    conn = get_conn()
    try:
        # v2 sessions + session_content JOIN
        rows = conn.execute(
            "SELECT s.id, s.source, s.session_id, s.date, s.repo, s.tag, s.summary, "
            "       sc.topic, sc.commands "
            "FROM sessions s "
            "LEFT JOIN session_content sc USING (source, session_id, date) "
            "WHERE s.tag = '기타' OR s.tag = '' OR s.tag IS NULL"
        ).fetchall()

        if not rows:
            # fallback: v1 activities
            rows = conn.execute(
                "SELECT id, source, session_id, repo, tag, summary, raw_json "
                "FROM activities WHERE tag = '기타' OR tag = '' OR tag IS NULL"
            ).fetchall()
            table = "activities"
        else:
            table = "sessions"

        print(f"Found {len(rows)} untagged/기타 in {table}", file=sys.stderr)

        updated = 0
        for r in rows:
            try:
                summary = r["summary"] or ""
                if table == "sessions":
                    topic = r["topic"] or ""
                    commands = " ".join(json.loads(r["commands"] or "[]")[:5])
                else:
                    raw = json.loads(r["raw_json"] or "{}")
                    topic = raw.get("topic", "")
                    commands = " ".join(raw.get("commands", [])[:5])

                new_tag = auto_tag(summary, topic, commands)
                if new_tag != "기타":
                    print(f"  [{r['source']}] {r['session_id'][:8]}.. "
                          f"{r['repo']}: {r['tag']!r} → {new_tag!r}  ({summary[:60]})")
                    if args.apply:
                        conn.execute(
                            f"UPDATE {table} SET tag = ? WHERE id = ?",
                            (new_tag, r["id"]),
                        )
                    updated += 1
            except Exception as e:
                print(f"  [SKIP] {r['session_id'][:8]}: {e}", file=sys.stderr)

        if args.apply and updated > 0:
            conn.commit()
            dates = conn.execute(
                f"SELECT DISTINCT date as d FROM {table}"
            ).fetchall()
            for d in dates:
                update_daily_stats(conn, d["d"])
            conn.commit()

        print(f"\n{'Applied' if args.apply else 'Would update'}: {updated}/{len(rows)} {table}",
              file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
