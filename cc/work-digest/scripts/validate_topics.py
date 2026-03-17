#!/usr/bin/env python3
"""정리해줘 결과 검증 — segment vs topic 1:1 대조.

Usage:
    python3 validate_topics.py --date 2026-03-16
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_day import find_transcripts, merge_segments

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "shared" / "life-dashboard-mcp"))
from extract_session import extract
from db import get_conn

KST = timezone(timedelta(hours=9))


def validate(date_str: str) -> bool:
    sessions = find_transcripts(date_str)
    conn = get_conn()

    total_segments = 0
    total_topics = 0
    errors = []

    for s in sessions:
        if not s.get("transcript"):
            continue
        sid = s["session_id"]

        data = extract(s["transcript"], date_str)
        segments = merge_segments(data.get("segments", []))
        if not segments:
            continue

        topics = conn.execute(
            "SELECT start_at, end_at, duration_estimate_min, tag, summary FROM session_topics "
            "WHERE session_id = ? AND date = ? ORDER BY topic_order",
            (sid, date_str),
        ).fetchall()

        total_segments += len(segments)
        total_topics += len(topics)

        if len(segments) != len(topics):
            errors.append(f"{sid[:8]}: segments={len(segments)} topics={len(topics)} MISMATCH")
            continue

        for i, (seg, top) in enumerate(zip(segments, topics)):
            # 시간 일치 확인
            topic_start = top["start_at"][11:16] if top["start_at"] else "?"
            if seg["start"] != topic_start:
                errors.append(f"{sid[:8]} #{i}: seg.start={seg['start']} topic.start={topic_start}")

            # tag 확인
            if not top["tag"] or top["tag"] == "기타":
                errors.append(f"{sid[:8]} #{i}: tag={top['tag']} (should be specific)")

            # summary 확인
            if not top["summary"] or len(top["summary"]) < 10:
                errors.append(f"{sid[:8]} #{i}: summary too short ({len(top['summary'] or '')} chars)")

    conn.close()

    print(f"segments: {total_segments}, topics: {total_topics}")
    if errors:
        print(f"\n{len(errors)} errors:")
        for e in errors:
            print(f"  ✗ {e}")
        return False
    else:
        print("✓ all checks passed")
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    args = ap.parse_args()
    ok = validate(args.date)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
