#!/usr/bin/env python3
"""정리해줘 결과 검증 — segment vs topic 1:1 대조 + eval 세션 면제 + --fix 모드.

Usage:
    python3 validate_topics.py --date 2026-03-16
    python3 validate_topics.py --fix --date 2026-03-16
"""
import argparse
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_day import find_transcripts, merge_segments

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "shared" / "life-dashboard-mcp"))
from extract_session import extract
from db import get_conn

KST = timezone(timedelta(hours=9))

VALID_TAGS = {"코딩", "디버깅", "리서치", "리뷰", "ops", "설정", "문서", "설계", "리팩토링", "eval", "기타"}


def _is_eval_repo(repo: str | None) -> bool:
    """repo 이름에 -claude 접미사가 있으면 eval 세션."""
    return bool(repo and repo.endswith("-claude"))


def _run_fixes(conn, date_str: str):
    """--fix 모드: validation 전에 DB를 정정한다.

    1. session_topics.repo가 NULL인 행 → 부모 sessions.repo로 채움
    2. -claude repo 세션 → session_topics.tag와 sessions.tag를 'eval'로 변경
    """
    # Fix 1: repo NULL 채우기
    fixed_repo = conn.execute("""
        UPDATE session_topics SET repo = (
            SELECT s.repo FROM sessions s
            WHERE s.source = session_topics.source
              AND s.session_id = session_topics.session_id
              AND s.date = session_topics.date
        )
        WHERE date = ? AND repo IS NULL
    """, (date_str,)).rowcount

    # Fix 2: -claude repo → tag='eval' (session_topics)
    fixed_eval_topics = conn.execute("""
        UPDATE session_topics SET tag = 'eval'
        WHERE date = ? AND repo LIKE '%-claude' AND tag != 'eval'
    """, (date_str,)).rowcount

    # Fix 2b: -claude repo → tag='eval' (sessions)
    fixed_eval_sessions = conn.execute("""
        UPDATE sessions SET tag = 'eval'
        WHERE date = ? AND repo LIKE '%-claude' AND (tag IS NULL OR tag != 'eval')
    """, (date_str,)).rowcount

    conn.commit()

    if fixed_repo or fixed_eval_topics or fixed_eval_sessions:
        print(f"[fix] repo NULL filled: {fixed_repo}, eval tag set: topics={fixed_eval_topics} sessions={fixed_eval_sessions}")
    else:
        print("[fix] nothing to fix")


def validate(date_str: str, fix: bool = False) -> bool:
    sessions = find_transcripts(date_str)
    conn = get_conn()

    if fix:
        _run_fixes(conn, date_str)

    total_segments = 0
    total_topics = 0
    eval_skipped = 0
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
            "SELECT start_at, end_at, duration_estimate_min, tag, summary, repo FROM session_topics "
            "WHERE session_id = ? AND date = ? ORDER BY topic_order",
            (sid, date_str),
        ).fetchall()

        # eval 세션 면제: 모든 topic의 repo가 -claude이면 skip
        if topics and all(_is_eval_repo(t["repo"]) for t in topics):
            eval_skipped += len(topics)
            continue

        total_segments += len(segments)
        total_topics += len(topics)

        # repo NULL 체크
        for i, top in enumerate(topics):
            if not top["repo"]:
                errors.append(f"{sid[:8]} #{i}: repo is NULL")

        if len(segments) != len(topics):
            errors.append(f"{sid[:8]}: segments={len(segments)} topics={len(topics)} MISMATCH")
            continue

        for i, (seg, top) in enumerate(zip(segments, topics)):
            # 시간 일치 확인
            raw_start = top["start_at"] or ""
            # start_at can be 'HH:MM' (5 chars) or 'YYYY-MM-DD HH:MM:SS' (19+ chars)
            if len(raw_start) >= 16:
                topic_start = raw_start[11:16]
            elif len(raw_start) == 5:
                topic_start = raw_start  # already 'HH:MM'
            else:
                topic_start = "?"
            if seg["start"] != topic_start:
                errors.append(f"{sid[:8]} #{i}: seg.start={seg['start']} topic.start={topic_start}")

            # tag 확인
            if not top["tag"] or top["tag"] not in VALID_TAGS:
                errors.append(f"{sid[:8]} #{i}: tag={top['tag']!r} (invalid)")
            elif top["tag"] == "기타":
                errors.append(f"{sid[:8]} #{i}: tag='기타' (should be specific)")

            # summary 확인
            if not top["summary"] or len(top["summary"]) < 10:
                errors.append(f"{sid[:8]} #{i}: summary too short ({len(top['summary'] or '')} chars)")

    # summary 반복 체크: 동일 summary가 3회 이상 나타나면 경고 (eval 제외)
    all_topics = conn.execute(
        "SELECT summary, repo FROM session_topics WHERE date = ?",
        (date_str,),
    ).fetchall()
    summary_counts = Counter(
        t["summary"] for t in all_topics
        if t["summary"] and not _is_eval_repo(t["repo"])
    )
    for summary_text, cnt in summary_counts.items():
        if cnt >= 3:
            errors.append(f"summary repeated {cnt}x: {summary_text[:60]}...")

    conn.close()

    print(f"segments: {total_segments}, topics: {total_topics}, eval_skipped: {eval_skipped}")
    if errors:
        print(f"\n{len(errors)} errors:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("all checks passed")
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    ap.add_argument("--fix", action="store_true", help="Auto-fix repo NULL and eval tags before validation")
    args = ap.parse_args()
    ok = validate(args.date, fix=args.fix)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
