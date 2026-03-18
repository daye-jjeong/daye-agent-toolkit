#!/usr/bin/env python3
"""Activity Writer — shared SQLite recording for CC and Codex session loggers.

Usage (library):
    from activity_writer import record_sessions

Usage (CLI):
    python3 activity_writer.py unsummarized --date 2026-03-16
    python3 activity_writer.py unsummarized --before 2026-03-16
    python3 activity_writer.py update-summary --session-id X --date Y --tag "코딩" --summary "..."
    python3 activity_writer.py save-coaching --date 2026-03-16 --period daily --content "..."
    python3 activity_writer.py save-task --date 2026-03-16 --description "..." --priority 1
    python3 activity_writer.py previous-coaching --date 2026-03-16
    python3 activity_writer.py resolve-task --id 1 --status done --date 2026-03-16
    python3 activity_writer.py resolve-followup --id 1 --status resolved --date 2026-03-16
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import (
    get_conn,
    upsert_session, upsert_session_content, upsert_session_topics, insert_signal,
    upsert_followup_chain, update_daily_stats,
    upsert_coaching_entry, upsert_task_suggestion,
    update_task_resolution, update_followup_resolution,
    get_coaching_entry, get_pending_tasks, get_open_followups,
)

KST = timezone(timedelta(hours=9))

# ── auto_tag ─────────────────────────────────────

TAG_KEYWORDS: list[tuple[str, list[str]]] = [
    ("디버깅", ["debug", "디버깅", "에러", "error", "fix", "버그", "traceback", "stack trace",
               "동작 안", "동작안해", "왜 안", "누락", "원인", "문제", "안 되", "안되",
               "실패", "깨진", "broken"]),
    ("리뷰", ["review", "리뷰", "code quality", "pr review", "approved", "rejected",
             "git diff", "검토", "괜찮은지", "수정할건", "품질", "점검"]),
    ("리서치", ["리서치", "research", "조사", "비교", "추천", "어떤게 있을까", "프레임워크",
               "분석", "파악", "알아봐"]),
    ("설계", ["설계", "design", "기획", "plan", "아키텍처", "brainstorm",
             "목업", "mockup", "mock-up", "검증", "verify",
             "구조", "방향", "전략"]),
    ("설정", ["설정", "설치", "config", "setup", "셋업", "install", "init",
             "환경", "세팅"]),
    ("문서", ["문서", "SKILL.md", "README", "documentation", "표준화", "문서화",
             "번역", "translate"]),
    ("리팩토링", ["리팩토링", "refactor", "정리", "통합", "consolidat", "마이그레이션", "migration",
                "전환", "제거", "cleanup"]),
    ("ops", ["deploy", "배포", "cron", "monitor", "운영", "워치독",
            "thread list", "task list", "minions", "텔레그램", "알림", "스케줄"]),
    ("코딩", ["구현", "implement", "추가", "생성", "만들", "작성", "feature",
             "write_file", "apply_diff", "create_file", "수정", "변경"]),
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


# ── Shared constants ─────────────────────────────

_SIGNAL_TYPE_MAP = {"decisions": "decision", "mistakes": "mistake", "patterns": "pattern"}
_TEST_KEYWORDS = frozenset({"pytest", "jest", "test", "vitest"})
_TEST_PATTERNS = ("npm run test", "npx test", "npm test", "bun test")


# ── Shared preparation ───────────────────────────

def _prepare_fields(data: dict, date_str: str) -> dict | None:
    """날짜별 데이터에서 공통 필드를 추출. skip할 데이터면 None 반환."""
    if not data.get("files") and not data.get("commands") and not data.get("topic"):
        return None

    tokens = data.get("tokens", {})
    token_total = sum(tokens.get(k, 0) for k in ("input", "output", "cache_read", "cache_create"))
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

    return {
        "token_total": token_total,
        "has_tests": has_tests,
        "has_commits": 1 if has_commits else 0,
        "start_at": start_at,
        "end_at": end_at,
        "file_count": len(data.get("files", [])),
        "error_count": len(data.get("errors", [])),
        "duration_min": data.get("duration_min"),
    }


# ── record_sessions (v2) ─────────────────────────

def record_sessions(
    source: str,
    session_id: str,
    by_date: dict[str, dict],
    repo: str,
    branch: str | None = None,
    summary: dict | None = None,
    behavioral_signals: dict | None = None,
    is_session_end: bool = False,
) -> dict[str, str]:
    """v2: 날짜별 분할 데이터를 sessions + session_content에 기록."""
    if not by_date:
        return {}

    recorded = {}
    dates = sorted(by_date.keys())
    import sys as _sys
    primary_date = dates[0]

    conn = get_conn()
    try:
        for date_str in dates:
            data = by_date[date_str]
            fields = _prepare_fields(data, date_str)
            if not fields:
                continue

            # Layer 1: tag만 auto, summary는 NULL (pending)
            tag = auto_tag(data.get("topic", ""), " ".join(data.get("commands", [])[:5]))

            # summary는 마지막 날짜에만, LLM이 성공한 경우만
            summary_text = None
            summary_source = "pending"
            status = "in_progress"
            follow_up_text = None
            if summary and date_str == dates[-1]:
                if summary.get("text"):
                    summary_text = summary["text"]
                    summary_source = "llm"
                if summary.get("tag"):
                    tag = summary["tag"]
                if summary.get("status"):
                    status = summary["status"]
                follow_up_text = summary.get("follow_up")
            # SessionEnd: 닫힌 세션이 in_progress로 남지 않도록
            # scanner(is_session_end=False)에서는 in_progress 유지
            if is_session_end and status == "in_progress":
                status = "completed"

            session_data = {
                "source": source, "session_id": session_id, "date": date_str,
                "repo": repo, "branch": branch, "tag": tag,
                "summary": summary_text, "summary_source": summary_source,
                "status": status, "follow_up": follow_up_text,
                **fields,
            }
            upsert_session(conn, session_data)

            # session_content — 원본 보존 (date-slice local)
            content_data = {
                "source": source, "session_id": session_id, "date": date_str,
                "topic": data.get("topic", ""),
                "user_messages": json.dumps(data.get("user_messages", []), ensure_ascii=False),
                "agent_messages": json.dumps(data.get("agent_messages", []), ensure_ascii=False),
                "files_changed": json.dumps(data.get("files", []), ensure_ascii=False),
                "commands": json.dumps(data.get("commands", [])[:20], ensure_ascii=False),
                "errors": json.dumps(data.get("errors", [])[:10], ensure_ascii=False),
            }
            upsert_session_content(conn, content_data)
            recorded[date_str] = session_id

            # followup_chains — status가 follow_up/blocked이면 자동 생성
            if status in ("follow_up", "blocked") and follow_up_text:
                upsert_followup_chain(conn, {
                    "origin_session_id": session_id,
                    "origin_date": date_str,
                    "origin_repo": repo,
                    "description": follow_up_text,
                })

        # signals — primary date에 1회 기록
        if behavioral_signals:
            for plural, singular in _SIGNAL_TYPE_MAP.items():
                items = behavioral_signals.get(plural, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            content_text = item.get("content", "")
                            reasoning_text = item.get("reasoning")
                        else:
                            content_text = str(item)
                            reasoning_text = None
                        if content_text:
                            insert_signal(conn, {
                                "session_id": session_id,
                                "date": primary_date,
                                "signal_type": singular,
                                "content": content_text,
                                "reasoning": reasoning_text,
                                "repo": repo,
                            })

        for date_str in recorded:
            update_daily_stats(conn, date_str)

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[record_sessions] DB error: {e}", file=_sys.stderr)
        return {}
    finally:
        conn.close()

    return recorded


# ── CLI ───────────────────────────────────────────

def cmd_unsummarized(args):
    if not args.date and not args.before:
        print("Error: --date or --before required", file=sys.stderr)
        sys.exit(1)
    conn = get_conn()
    try:
        if args.before:
            rows = conn.execute("""
                SELECT s.session_id, s.date, s.repo, s.source,
                       sc.topic, sc.user_messages
                FROM sessions s
                LEFT JOIN session_content sc USING (source, session_id, date)
                WHERE s.date < ? AND s.summary_source = 'pending'
                ORDER BY s.date, s.start_at
            """, (args.before,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT s.session_id, s.date, s.repo, s.source,
                       sc.topic, sc.user_messages
                FROM sessions s
                LEFT JOIN session_content sc USING (source, session_id, date)
                WHERE s.date = ? AND s.summary_source = 'pending'
                ORDER BY s.start_at
            """, (args.date,)).fetchall()
        results = []
        for r in rows:
            results.append({
                "session_id": r["session_id"], "date": r["date"],
                "repo": r["repo"], "source": r["source"],
                "topic": r["topic"] or "",
                "user_messages": json.loads(r["user_messages"] or "[]"),
            })
        print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def cmd_update_summary(args):
    conn = get_conn()

    try:
        summary_source = getattr(args, 'summary_source', None) or "llm"
        sets = ["tag = ?", "summary = ?", "summary_source = ?"]
        params = [args.tag, args.summary, summary_source]
        if args.status:
            sets.append("status = ?")
            params.append(args.status)
        if args.follow_up:
            sets.append("follow_up = ?")
            params.append(args.follow_up)
        params.extend([args.session_id, args.date])
        cursor = conn.execute(f"""
            UPDATE sessions
            SET {', '.join(sets)}
            WHERE session_id = ? AND date = ?
        """, params)
        if cursor.rowcount == 0:
            print(f"No session found: {args.session_id} / {args.date}", file=sys.stderr)
            sys.exit(1)

        # follow_up/blocked → followup_chains 자동 생성
        if args.status in ("follow_up", "blocked") and args.follow_up:
            upsert_followup_chain(conn, {
                "origin_session_id": args.session_id,
                "origin_date": args.date,
                "origin_repo": None,
                "description": args.follow_up,
            })

        update_daily_stats(conn, args.date)
        conn.commit()
        print(f"Updated: {args.session_id} [{args.tag}] {args.summary[:50]}", file=sys.stderr)
    finally:
        conn.close()


def cmd_update_topics(args):
    """Step 3a용: 세션의 토픽을 전체 교체."""
    try:
        topics = json.loads(args.topics)
    except json.JSONDecodeError as e:
        print(f"Error: --topics is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(topics, list) or not topics:
        print("Error: --topics must be a non-empty JSON array", file=sys.stderr)
        sys.exit(1)

    conn = get_conn()
    try:
        upsert_session_topics(conn, "cc", args.session_id, args.date, topics)
        update_daily_stats(conn, args.date)
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM session_topics WHERE source='cc' AND session_id=? AND date=?",
            (args.session_id, args.date),
        ).fetchone()[0]
        print(f"Updated {count} topics for {args.session_id}", file=sys.stderr)
    except Exception as e:
        conn.rollback()
        print(f"Error: DB operation failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_save_coaching(args):
    conn = get_conn()

    try:
        content_path = Path(args.content)
        content = content_path.read_text() if content_path.exists() else args.content
        sections = json.loads(args.sections) if args.sections else {}
        upsert_coaching_entry(conn, {
            "date": args.date,
            "period_type": args.period,
            "content": content,
            "sections": json.dumps(sections, ensure_ascii=False),
            "escalation_level": args.escalation_level or 0,
        })
        conn.commit()
        print(f"Coaching saved: {args.date} ({args.period})", file=sys.stderr)
    finally:
        conn.close()


def cmd_save_task(args):
    conn = get_conn()

    try:
        upsert_task_suggestion(conn, {
            "suggested_date": args.date,
            "description": args.description,
            "estimated_min": args.estimated_min,
            "priority": args.priority or 99,
            "source_type": args.source_type or "coaching",
            "origin_session_id": args.origin_session_id,
            "status": "pending",
        })
        conn.commit()
        print(f"Task saved: {args.description[:50]}", file=sys.stderr)
    finally:
        conn.close()


def cmd_previous_coaching(args):
    conn = get_conn()
    try:
        yesterday = (datetime.strptime(args.date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        coaching = get_coaching_entry(conn, yesterday, "daily")
        pending = get_pending_tasks(conn)
        followups = get_open_followups(conn)
        result = {
            "yesterday_coaching": dict(coaching) if coaching else None,
            "pending_tasks": pending,
            "open_followups": followups,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        conn.close()


def cmd_resolve_task(args):
    conn = get_conn()
    try:
        found = update_task_resolution(conn, args.id, args.status, args.date,
                                       args.session_id, args.method, args.notes)
        if not found:
            print(f"No task found with id={args.id}", file=sys.stderr)
            sys.exit(1)
        conn.commit()
        print(f"Task {args.id} → {args.status}", file=sys.stderr)
    finally:
        conn.close()


def cmd_resolve_followup(args):
    conn = get_conn()
    try:
        found = update_followup_resolution(conn, args.id, args.status, args.date,
                                            args.session_id, args.note)
        if not found:
            print(f"No followup found with id={args.id}", file=sys.stderr)
            sys.exit(1)
        conn.commit()
        print(f"Followup {args.id} → {args.status}", file=sys.stderr)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Activity Writer CLI")
    sub = parser.add_subparsers(dest="command")

    p_unsummarized = sub.add_parser("unsummarized", help="List unsummarized sessions")
    p_unsummarized.add_argument("--date", help="List pending sessions for this date")
    p_unsummarized.add_argument("--before", help="Catch-up: list pending sessions before this date")

    p_update = sub.add_parser("update-summary", help="Update session summary")
    p_update.add_argument("--session-id", required=True)
    p_update.add_argument("--date", required=True)
    p_update.add_argument("--tag", required=True)
    p_update.add_argument("--summary", required=True)
    p_update.add_argument("--status", choices=["completed", "in_progress", "blocked", "follow_up"])
    p_update.add_argument("--follow-up", dest="follow_up", help="Next action description")
    p_update.add_argument("--summary-source", dest="summary_source",
                          choices=["llm", "manual"], default="llm")

    p_topics = sub.add_parser("update-topics", help="Replace session topics")
    p_topics.add_argument("--session-id", required=True)
    p_topics.add_argument("--date", required=True)
    p_topics.add_argument("--topics", required=True, help='JSON array: [{"tag":"..","summary":"..","repo":".."}]')

    p_coaching = sub.add_parser("save-coaching", help="Save coaching entry")
    p_coaching.add_argument("--date", required=True)
    p_coaching.add_argument("--period", required=True, choices=["daily", "weekly"])
    p_coaching.add_argument("--content", required=True, help="Markdown content or file path")
    p_coaching.add_argument("--sections", help="JSON sections")
    p_coaching.add_argument("--escalation-level", type=int, dest="escalation_level")

    p_task = sub.add_parser("save-task", help="Save task suggestion")
    p_task.add_argument("--date", required=True)
    p_task.add_argument("--description", required=True)
    p_task.add_argument("--estimated-min", type=int, dest="estimated_min")
    p_task.add_argument("--priority", type=int)
    p_task.add_argument("--source-type", dest="source_type", default="coaching")
    p_task.add_argument("--origin-session-id", dest="origin_session_id")

    p_prev = sub.add_parser("previous-coaching", help="Get yesterday coaching + pending tasks")
    p_prev.add_argument("--date", required=True)

    p_resolve_task = sub.add_parser("resolve-task", help="Resolve a task suggestion")
    p_resolve_task.add_argument("--id", required=True, type=int)
    p_resolve_task.add_argument("--status", required=True, choices=["done", "skipped", "deferred"])
    p_resolve_task.add_argument("--date", required=True)
    p_resolve_task.add_argument("--session-id", dest="session_id")
    p_resolve_task.add_argument("--method", default="user", choices=["auto", "user"])
    p_resolve_task.add_argument("--notes")

    p_resolve_followup = sub.add_parser("resolve-followup", help="Resolve a followup chain")
    p_resolve_followup.add_argument("--id", required=True, type=int)
    p_resolve_followup.add_argument("--status", required=True, choices=["resolved", "abandoned", "superseded"])
    p_resolve_followup.add_argument("--date", required=True)
    p_resolve_followup.add_argument("--session-id", dest="session_id")
    p_resolve_followup.add_argument("--note")

    args = parser.parse_args()
    dispatch = {
        "unsummarized": cmd_unsummarized,
        "update-summary": cmd_update_summary,
        "update-topics": cmd_update_topics,
        "save-coaching": cmd_save_coaching,
        "save-task": cmd_save_task,
        "previous-coaching": cmd_previous_coaching,
        "resolve-task": cmd_resolve_task,
        "resolve-followup": cmd_resolve_followup,
    }
    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
