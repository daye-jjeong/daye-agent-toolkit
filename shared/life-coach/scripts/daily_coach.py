#!/usr/bin/env python3
"""Daily Coach — life-dashboard data-based daily coaching report.

Usage:
    python3 daily_coach.py                 # LLM coaching + telegram
    python3 daily_coach.py --dry-run       # stdout only
    python3 daily_coach.py --no-llm        # template only
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import get_conn, get_coach_state, set_coach_state

_WD_SCRIPTS = Path(__file__).resolve().parent.parent.parent.parent / "cc" / "work-digest" / "scripts"
sys.path.insert(0, str(_WD_SCRIPTS))
from _common import send_telegram, WEEKDAYS_KO, TAG_ICONS, TELEGRAM_MAX_CHARS

KST = timezone(timedelta(hours=9))
COACHING_TIMEOUT_SEC = 45
OVERWORK_THRESHOLD_HOURS = 8
PROMPTS_PATH = Path(__file__).resolve().parent.parent / "references" / "coaching-prompts.md"


def get_today_data(conn, date_str: str) -> dict:
    stats = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ?", (date_str,)
    ).fetchone()

    if not stats:
        return {"date": date_str, "has_data": False}

    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    activities = conn.execute("""
        SELECT repo, tag, summary, start_at, end_at, duration_min, token_total
        FROM activities WHERE start_at >= ? AND start_at < ? AND source = 'cc'
        ORDER BY start_at
    """, (date_str, next_date)).fetchall()

    return {
        "date": date_str,
        "has_data": True,
        "work_hours": stats["work_hours"],
        "session_count": stats["session_count"],
        "first_session": stats["first_session"],
        "last_session_end": stats["last_session_end"],
        "tag_breakdown": json.loads(stats["tag_breakdown"]) if stats["tag_breakdown"] else {},
        "repos": json.loads(stats["repos"]) if stats["repos"] else {},
        "sessions": [dict(a) for a in activities],
    }


def build_data_section(data: dict) -> str:
    lines = []
    date_str = data["date"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = WEEKDAYS_KO[dt.weekday()]

    lines.append(f"날짜: {date_str} ({weekday})")
    lines.append(f"총 작업: {data['work_hours']}시간, {data['session_count']}세션")
    lines.append(f"시간대: {data['first_session']} ~ {data['last_session_end']}")

    tags = data.get("tag_breakdown", {})
    if tags:
        tag_parts = [f"{TAG_ICONS.get(t, '💡')}{t} {c}건" for t, c in
                     sorted(tags.items(), key=lambda x: x[1], reverse=True)]
        lines.append(f"작업 유형: {', '.join(tag_parts)}")

    repos = data.get("repos", {})
    if repos:
        repo_parts = [f"{r}({c}세션)" for r, c in
                      sorted(repos.items(), key=lambda x: x[1], reverse=True)]
        lines.append(f"레포: {', '.join(repo_parts)}")

    sessions = data.get("sessions", [])
    if sessions:
        lines.append("")
        lines.append("세션별:")
        for s in sessions[:8]:
            start = s.get("start_at", "")[11:16] if s.get("start_at") else "?"
            tag = s.get("tag", "")
            summary = (s.get("summary", "") or "")[:80]
            repo = s.get("repo", "")
            dur = s.get("duration_min", 0)
            lines.append(f"- {start} [{tag}] {repo}: {summary} ({dur}분)")

    return "\n".join(lines)


def _build_header(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = WEEKDAYS_KO[dt.weekday()]
    return f"🏋️ {dt.month}/{dt.day}({weekday}) 데일리 코칭"


def _build_stats_line(data: dict) -> str:
    return (
        f"⏱ {data['session_count']}세션 · {data['work_hours']}시간 "
        f"· {data['first_session']}~{data['last_session_end']}"
    )


def build_template_report(data: dict, coach_state: dict) -> str:
    sections = [_build_header(data["date"])]

    if not data["has_data"]:
        sections.append("오늘 기록된 세션 없음.")
        return "\n\n".join(sections)

    sections.append(_build_stats_line(data))

    tags = data.get("tag_breakdown", {})
    if tags:
        parts = [f"{TAG_ICONS.get(t, '💡')}{t} {c}건" for t, c in
                 sorted(tags.items(), key=lambda x: x[1], reverse=True)]
        sections.append("🏷 " + " · ".join(parts))

    repos = data.get("repos", {})
    if repos:
        repo_lines = ["📂 레포별:"]
        for r, c in sorted(repos.items(), key=lambda x: x[1], reverse=True)[:5]:
            repo_lines.append(f"  ▸ {r} ({c}세션)")
        sections.append("\n".join(repo_lines))

    nudges = []
    if data["work_hours"] >= OVERWORK_THRESHOLD_HOURS:
        nudges.append(f"⚠️ {data['work_hours']}시간 작업 — 과작업 주의")
    if data["first_session"] and data["first_session"] < "06:00":
        nudges.append("🌙 새벽 작업 감지 — 수면 패턴 주의")
    overwork_days = int(coach_state.get("consecutive_overwork_days", "0"))
    if overwork_days >= 3:
        nudges.append(f"🔥 {overwork_days}일 연속 과작업 — 번아웃 위험")
    if nudges:
        sections.append("\n".join(nudges))

    level = int(coach_state.get("escalation_level", "0"))
    sections.append(f"⚡ 코치 레벨: {level}")

    return "\n\n".join(sections)


def generate_llm_coaching(data_section: str, tone_level: int) -> str | None:
    tone_desc = f"Level {tone_level}"

    try:
        template = PROMPTS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        template = "데이터를 보고 코칭해라."

    prompt = template.replace("{data_section}", data_section).replace("{tone_level}", tone_desc)

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--no-session-persistence"],
            input=prompt, capture_output=True, text=True, timeout=COACHING_TIMEOUT_SEC,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        print(f"[daily_coach] LLM failed: {e}", file=sys.stderr)
    return None


def update_overwork_tracking(conn, data: dict, coach_state: dict):
    overwork_days = int(coach_state.get("consecutive_overwork_days", "0"))
    level = int(coach_state.get("escalation_level", "0"))

    if data["has_data"] and data["work_hours"] >= OVERWORK_THRESHOLD_HOURS:
        overwork_days += 1
    else:
        overwork_days = 0

    if overwork_days >= 7:
        level = 2
    elif overwork_days >= 3:
        level = max(level, 1)
    elif overwork_days == 0 and level > 0:
        level = max(0, level - 1)

    set_coach_state(conn, "consecutive_overwork_days", str(overwork_days))
    set_coach_state(conn, "escalation_level", str(level))
    conn.commit()

    return level


def main():
    parser = argparse.ArgumentParser(description="Daily coaching report")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    conn = get_conn()
    data = get_today_data(conn, args.date)
    coach_state = get_coach_state(conn)
    level = update_overwork_tracking(conn, data, coach_state)

    if not data["has_data"] or args.no_llm:
        message = build_template_report(data, coach_state)
    else:
        data_section = build_data_section(data)
        llm_result = generate_llm_coaching(data_section, level)
        if llm_result:
            header = _build_header(args.date)
            stats_line = _build_stats_line(data)
            message = f"{header}\n\n{stats_line}\n\n{llm_result}\n\n⚡ 코치 레벨: {level}"
        else:
            message = build_template_report(data, coach_state)

    if len(message) > TELEGRAM_MAX_CHARS:
        message = message[:TELEGRAM_MAX_CHARS - 20] + "\n\n... (truncated)"

    conn.close()

    if args.dry_run:
        print(message)
    else:
        ok = send_telegram(message, chat_id_key="CHAT_ID_COACH", silent=True)
        if ok:
            print("[daily_coach] telegram sent", file=sys.stderr)
        else:
            print("[daily_coach] telegram failed (check CHAT_ID_COACH)", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
