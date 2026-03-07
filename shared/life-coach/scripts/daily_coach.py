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
from _common import send_telegram, format_tokens, WEEKDAYS_KO, TAG_ICONS, TELEGRAM_MAX_CHARS

KST = timezone(timedelta(hours=9))
COACHING_TIMEOUT_SEC = 45
OVERWORK_THRESHOLD_HOURS = 8
PROMPTS_PATH = Path(__file__).resolve().parent.parent / "references" / "coaching-prompts.md"
PROJECTS_DIR = Path.home() / ".claude" / "projects"


def get_today_data(conn, date_str: str) -> dict:
    stats = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ?", (date_str,)
    ).fetchone()

    if not stats:
        return {"date": date_str, "has_data": False}

    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    activities = conn.execute("""
        SELECT repo, tag, summary, start_at, end_at, duration_min,
               token_total, error_count, has_tests, has_commits
        FROM activities WHERE start_at >= ? AND start_at < ? AND source = 'cc'
        ORDER BY start_at
    """, (date_str, next_date)).fetchall()

    sessions = [dict(a) for a in activities]
    return {
        "date": date_str,
        "has_data": True,
        "work_hours": stats["work_hours"],
        "session_count": stats["session_count"],
        "first_session": stats["first_session"],
        "last_session_end": stats["last_session_end"],
        "tag_breakdown": json.loads(stats["tag_breakdown"]) if stats["tag_breakdown"] else {},
        "repos": json.loads(stats["repos"]) if stats["repos"] else {},
        "sessions": sessions,
        "token_total": sum(s.get("token_total") or 0 for s in sessions),
    }


def build_data_section(data: dict) -> str:
    lines = []
    date_str = data["date"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = WEEKDAYS_KO[dt.weekday()]

    lines.append(f"날짜: {date_str} ({weekday})")
    lines.append(f"총 작업: {data['work_hours']}시간, {data['session_count']}세션")
    lines.append(f"시간대: {data['first_session']} ~ {data['last_session_end']}")
    token_total = data.get("token_total", 0)
    if token_total > 0:
        lines.append(f"토큰: {format_tokens(token_total)} tokens")

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
    line = (
        f"⏱ {data['session_count']}세션 · {data['work_hours']}시간 "
        f"· {data['first_session']}~{data['last_session_end']}"
    )
    token_total = data.get("token_total", 0)
    if token_total > 0:
        line += f" · {format_tokens(token_total)} tokens"
    return line


def _build_repos_detail(data: dict) -> str | None:
    """레포별 세션 상세."""
    sessions = data.get("sessions", [])
    if not sessions:
        return None
    repo_groups: dict[str, list[dict]] = {}
    for s in sessions:
        repo = s.get("repo") or "unknown"
        repo_groups.setdefault(repo, []).append(s)

    lines = ["📂 레포별:"]
    for repo, sess in sorted(repo_groups.items(), key=lambda x: len(x[1]), reverse=True):
        total_dur = sum(s.get("duration_min", 0) for s in sess)
        total_tok = sum(s.get("token_total", 0) for s in sess)
        parts = [f"{len(sess)}세션"]
        if total_dur > 0:
            h, m = divmod(total_dur, 60)
            parts.append(f"{h}시간 {m}분" if h else f"{m}분")
        if total_tok > 0:
            parts.append(f"{format_tokens(total_tok)} tokens")
        lines.append(f"  ▸ {repo} ({', '.join(parts)})")
        for s in sess[:3]:
            start = (s.get("start_at") or "")[11:16] or "?"
            tag = s.get("tag", "")
            summary = (s.get("summary") or "")[:80]
            lines.append(f"    - {start} [{tag}] {summary}")
    return "\n".join(lines)


def _build_pattern_feedback(data: dict) -> str | None:
    """규칙 기반 패턴 피드백."""
    if not data.get("has_data"):
        return None
    lines = []
    repos = data.get("repos", {})
    if len(repos) >= 3:
        lines.append(f"• {len(repos)}개 레포 컨텍스트 스위칭")
    sessions = data.get("sessions", [])
    total_errors = sum(s.get("error_count", 0) for s in sessions)
    if total_errors > 0:
        lines.append(f"• 에러 {total_errors}건 발생")
    if not any(s.get("has_tests") for s in sessions):
        lines.append("• 테스트 실행 0건")
    if not any(s.get("has_commits") for s in sessions):
        lines.append("• 커밋 0건")
    token_total = data.get("token_total", 0)
    if token_total > 0:
        lines.append(f"• 총 {format_tokens(token_total)} tokens 사용")
    if not lines:
        return None
    return "💡 패턴 피드백:\n" + "\n".join(f"  {l}" for l in lines)


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

    repos_detail = _build_repos_detail(data)
    if repos_detail:
        sections.append(repos_detail)

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

    feedback = _build_pattern_feedback(data)
    if feedback:
        sections.append(feedback)

    level = int(coach_state.get("escalation_level", "0"))
    sections.append(f"⚡ 코치 레벨: {level}")

    return "\n\n".join(sections)


def generate_llm_coaching(data_section: str, tone_level: int) -> str | None:
    tone_desc = f"Level {tone_level}"

    try:
        template = PROMPTS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"[daily_coach] prompt template not found: {PROMPTS_PATH}, using fallback", file=sys.stderr)
        template = "데이터를 보고 코칭해라."

    prompt = template.replace("{data_section}", data_section).replace("{tone_level}", tone_desc)

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--no-session-persistence"],
            input=prompt, capture_output=True, text=True, timeout=COACHING_TIMEOUT_SEC,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        if result.returncode != 0:
            print(f"[daily_coach] claude exit code {result.returncode}: {result.stderr.strip()}", file=sys.stderr)
    except FileNotFoundError:
        print("[daily_coach] claude CLI not found", file=sys.stderr)
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


def _find_project_memory(repo_name: str) -> Path | None:
    if not PROJECTS_DIR.exists():
        return None
    for entry in PROJECTS_DIR.iterdir():
        if entry.is_dir() and entry.name.endswith(repo_name):
            return entry / "memory"
    return None


def write_work_context(data: dict):
    """레포별 work-context.md를 각 프로젝트 auto memory에 기록."""
    sessions = data.get("sessions", [])
    if not sessions:
        return
    date_str = data["date"]
    repo_sessions: dict[str, list[dict]] = {}
    for s in sessions:
        repo = s.get("repo") or "unknown"
        repo_sessions.setdefault(repo, []).append(s)
    for repo, sess in repo_sessions.items():
        memory_dir = _find_project_memory(repo)
        if not memory_dir:
            continue
        lines = [
            "# 최근 작업 컨텍스트",
            f"<!-- auto-generated by daily_coach.py | {date_str} -->",
            "",
        ]
        for s in sess:
            tag = s.get("tag", "").strip()
            start = (s.get("start_at") or "")[11:16] or ""
            sm = (s.get("summary") or "").strip()
            if sm:
                prefix = f"[{tag}] " if tag else ""
                lines.append(f"- {start} {prefix}{sm}")
        lines.append("")
        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
            (memory_dir / "work-context.md").write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            print(f"[daily_coach] {repo} work-context write failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Daily coaching report")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    conn = get_conn()
    try:
        data = get_today_data(conn, args.date)
        coach_state = get_coach_state(conn)
        level = update_overwork_tracking(conn, data, coach_state)
        coach_state = get_coach_state(conn)  # re-read after update

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
    finally:
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

    write_work_context(data)


if __name__ == "__main__":
    main()
