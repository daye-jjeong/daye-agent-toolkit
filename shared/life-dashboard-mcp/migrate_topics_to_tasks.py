#!/usr/bin/env python3
"""session_topics → tasks 마이그레이션.

Usage:
    python3 migrate_topics_to_tasks.py              # dry-run
    python3 migrate_topics_to_tasks.py --execute     # 실행
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn


def migrate(execute: bool = False):
    conn = get_conn()

    # 이미 tasks에 데이터가 있으면 skip (idempotent)
    existing = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if existing > 0:
        print(f"[migrate] tasks already has {existing} rows — skipping", file=sys.stderr)
        conn.close()
        return

    rows = conn.execute("""
        SELECT st.date, st.tag, st.summary, st.repo,
               st.start_at, st.end_at, st.duration_estimate_min,
               st.status, st.follow_up, st.session_id
        FROM session_topics st
        ORDER BY st.date, st.id
    """).fetchall()

    print(f"[migrate] {len(rows)} session_topics → tasks", file=sys.stderr)

    for r in rows:
        seg = {
            "sid": r["session_id"],
            "date": r["date"],
            "start": (r["start_at"] or "00:00")[11:16] if r["start_at"] and len(r["start_at"]) >= 16 else (r["start_at"] or "00:00"),
            "end": (r["end_at"] or "00:00")[11:16] if r["end_at"] and len(r["end_at"]) >= 16 else (r["end_at"] or "00:00"),
            "dur": r["duration_estimate_min"] or 0,
        }
        segments_json = json.dumps([seg], ensure_ascii=False)

        if execute:
            conn.execute("""
                INSERT INTO tasks (date, tag, summary, repo, segments, duration_min, status, follow_up)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["date"], r["tag"] or "기타", r["summary"], r["repo"],
                segments_json, r["duration_estimate_min"] or 0,
                r["status"] or "completed", r["follow_up"],
            ))
        else:
            print(f"  [{r['date']}] [{r['tag']}] {r['summary'][:50]}", file=sys.stderr)

    if execute:
        # 백업 후 rename
        conn.execute("ALTER TABLE session_topics RENAME TO _session_topics_backup")
        conn.commit()
        final_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        print(f"[migrate] DONE: {final_count} tasks created, session_topics → _session_topics_backup", file=sys.stderr)
    else:
        print(f"[migrate] DRY RUN — pass --execute to apply", file=sys.stderr)

    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    migrate(args.execute)


if __name__ == "__main__":
    main()
