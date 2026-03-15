#!/usr/bin/env python3
"""Activity Writer — shared SQLite recording for CC and Codex session loggers.

Usage (library):
    from activity_writer import record_activities
    record_activities("cc", session_id, by_date, repo, branch)

Usage (CLI):
    python3 activity_writer.py unsummarized --date 2026-03-15
    python3 activity_writer.py update-summary --session-id X --date Y --tag "코딩" --summary "..."
"""

import argparse
import json
import re
import sys
from datetime import timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn, upsert_activity, update_daily_stats, insert_behavioral_signal

KST = timezone(timedelta(hours=9))

# ── auto_tag (moved from _sync_common.py) ─────────────────

TAG_KEYWORDS: list[tuple[str, list[str]]] = [
    ("디버깅", ["debug", "디버깅", "에러", "error", "fix", "버그", "traceback", "stack trace",
               "동작 안", "동작안해", "왜 안"]),
    ("리뷰", ["review", "리뷰", "code quality", "pr review", "approved", "rejected",
             "git diff", "검토", "괜찮은지", "수정할건"]),
    ("리서치", ["리서치", "research", "조사", "비교", "추천", "어떤게 있을까", "프레임워크"]),
    ("설계", ["설계", "design", "기획", "plan", "아키텍처", "brainstorm",
             "목업", "mockup", "mock-up", "검증", "verify"]),
    ("설정", ["설정", "config", "setup", "셋업", "install", "init"]),
    ("문서", ["문서", "SKILL.md", "README", "documentation", "표준화", "문서화"]),
    ("리팩토링", ["리팩토링", "refactor", "정리", "통합", "consolidat"]),
    ("ops", ["deploy", "배포", "cron", "monitor", "운영", "워치독",
            "thread list", "task list", "minions"]),
    ("코딩", ["구현", "implement", "추가", "생성", "만들", "작성", "feature",
             "write_file", "apply_diff", "create_file"]),
]

_WORD_BOUNDARY_KW = frozenset({"error", "fix", "init", "plan"})


def _kw_matches(kw: str, text: str) -> bool:
    kw_lower = kw.lower()
    if kw_lower in _WORD_BOUNDARY_KW:
        return bool(re.search(r"\b" + re.escape(kw_lower) + r"\b", text))
    return kw_lower in text


def auto_tag(*text_sources: str) -> str:
    text = " ".join(text_sources).lower()
    for tag, keywords in TAG_KEYWORDS:
        if any(_kw_matches(kw, text) for kw in keywords):
            return tag
    return "기타"


# ── record_activities ─────────────────────────────

_SIGNAL_TYPE_MAP = {"decisions": "decision", "mistakes": "mistake", "patterns": "pattern"}
_TEST_KEYWORDS = frozenset({"pytest", "jest", "test", "vitest"})
_TEST_PATTERNS = ("npm run test", "npx test", "npm test", "bun test")


def record_activities(
    source: str,
    session_id: str,
    by_date: dict[str, dict],
    repo: str,
    branch: str | None = None,
    summary: dict | None = None,
    behavioral_signals: dict | None = None,
) -> dict[str, str]:
    """날짜별 분할 데이터를 SQLite에 직접 기록.

    Returns: {date_str: session_id} — 기록된 날짜별.
    """
    if not by_date:
        return {}

    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    recorded = {}
    dates = sorted(by_date.keys())
    last_date = dates[-1]

    try:
        for date_str in dates:
            data = by_date[date_str]

            if not data.get("files") and not data.get("commands") and not data.get("topic"):
                continue

            tokens = data.get("tokens", {})
            token_total = sum(tokens.get(k, 0) for k in ("input", "output", "cache_read", "cache_create"))
            # Codex는 api_calls에 total tokens를 넣으므로 fallback
            if token_total == 0:
                token_total = tokens.get("api_calls", 0)

            has_tests = 0
            has_commits = data.get("has_commits", False)
            for cmd in data.get("commands", []):
                cmd_lower = cmd.lower()
                if any(kw in cmd_lower for kw in _TEST_KEYWORDS) or \
                   any(pat in cmd_lower for pat in _TEST_PATTERNS):
                    has_tests = 1

            start_kst = data.get("start_kst")
            start_at = start_kst.strftime("%Y-%m-%dT%H:%M:%S") if start_kst else f"{date_str}T00:00:00"
            end_time = data.get("end_time")
            end_at = f"{date_str}T{end_time}:00" if end_time else None

            # summary/tag: 마지막 날짜에만 적용
            tag = None
            summary_text = None
            if date_str == last_date and summary:
                tag = summary.get("tag")
                summary_text = summary.get("text")

            activity = {
                "source": source,
                "session_id": session_id,
                "repo": repo,
                "branch": branch,
                "tag": tag,
                "summary": summary_text,
                "start_at": start_at,
                "end_at": end_at,
                "date": date_str,
                "duration_min": data.get("duration_min"),
                "file_count": len(data.get("files", [])),
                "error_count": len(data.get("errors", [])),
                "has_tests": has_tests,
                "has_commits": 1 if has_commits else 0,
                "token_total": token_total,
                "raw_json": json.dumps({
                    "topic": data.get("topic", ""),
                    "files_changed": data.get("files", []),
                    "commands": data.get("commands", [])[:10],
                    "errors": data.get("errors", [])[:5],
                }, ensure_ascii=False),
            }
            upsert_activity(conn, activity)
            recorded[date_str] = session_id

            if date_str == last_date and behavioral_signals:
                for plural, singular in _SIGNAL_TYPE_MAP.items():
                    for content in behavioral_signals.get(plural, []):
                        insert_behavioral_signal(conn, {
                            "session_id": session_id,
                            "date": date_str,
                            "signal_type": singular,
                            "content": content,
                            "repo": repo,
                        })

        for date_str in recorded:
            update_daily_stats(conn, date_str)

        conn.commit()
    finally:
        conn.close()

    return recorded


# ── CLI ───────────────────────────────────────────

def cmd_unsummarized(args):
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT session_id, date, repo, source, raw_json
            FROM activities
            WHERE date = ? AND (tag IS NULL OR summary IS NULL)
            ORDER BY start_at
        """, (args.date,)).fetchall()
        results = []
        for r in rows:
            raw = json.loads(r["raw_json"] or "{}")
            results.append({
                "session_id": r["session_id"],
                "date": r["date"],
                "repo": r["repo"],
                "source": r["source"],
                "topic": raw.get("topic", ""),
            })
        print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def cmd_update_summary(args):
    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        cursor = conn.execute("""
            UPDATE activities
            SET tag = ?, summary = ?
            WHERE session_id = ? AND date = ?
        """, (args.tag, args.summary, args.session_id, args.date))
        if cursor.rowcount == 0:
            print(f"No activity found: {args.session_id} / {args.date}", file=sys.stderr)
            sys.exit(1)
        update_daily_stats(conn, args.date)
        conn.commit()
        print(f"Updated: {args.session_id} [{args.tag}] {args.summary[:50]}", file=sys.stderr)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Activity Writer CLI")
    sub = parser.add_subparsers(dest="command")

    p_unsummarized = sub.add_parser("unsummarized", help="List unsummarized sessions")
    p_unsummarized.add_argument("--date", required=True)

    p_update = sub.add_parser("update-summary", help="Update session summary")
    p_update.add_argument("--session-id", required=True)
    p_update.add_argument("--date", required=True)
    p_update.add_argument("--tag", required=True)
    p_update.add_argument("--summary", required=True)

    args = parser.parse_args()
    if args.command == "unsummarized":
        cmd_unsummarized(args)
    elif args.command == "update-summary":
        cmd_update_summary(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
