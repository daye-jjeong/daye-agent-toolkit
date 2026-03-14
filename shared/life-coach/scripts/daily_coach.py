#!/usr/bin/env python3
"""Daily Coach — life-dashboard data-based daily coaching report.

Usage:
    python3 daily_coach.py                 # template report → telegram
    python3 daily_coach.py --dry-run       # stdout only
    python3 daily_coach.py --json          # JSON data (for LLM on-demand coaching)
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import get_conn, get_coach_state, set_coach_state, get_repeated_signals, \
    query_exercises, query_symptoms, query_meals, query_check_ins, query_expiring_pantry, \
    get_mistake_trends

_WD_SCRIPTS = Path(__file__).resolve().parent.parent.parent.parent / "cc" / "work-digest" / "scripts"
sys.path.insert(0, str(_WD_SCRIPTS))
from _common import send_telegram, format_tokens, WEEKDAYS_KO, TAG_ICONS, TELEGRAM_MAX_CHARS

KST = timezone(timedelta(hours=9))
OVERWORK_THRESHOLD_HOURS = 8

from _helpers import find_project_memory, group_sessions_by_repo_branch, has_meaningful_branches, get_pending_work


def get_today_data(conn, date_str: str) -> dict:
    stats = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ?", (date_str,)
    ).fetchone()

    if not stats:
        return {"date": date_str, "has_data": False}

    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    activities = conn.execute("""
        SELECT source, repo, branch, tag, summary, start_at, end_at, duration_min,
               token_total, error_count, has_tests, has_commits, raw_json
        FROM activities WHERE start_at >= ? AND start_at < ?
        ORDER BY start_at
    """, (date_str, next_date)).fetchall()

    sessions = []
    for a in activities:
        s = dict(a)
        # raw_json에서 LLM 요약에 필요한 context 추출
        raw = json.loads(s.pop("raw_json", "null") or "{}")
        if raw.get("commands"):
            s["commands"] = raw["commands"][:5]
        if raw.get("user_messages"):
            s["user_messages"] = [m[:200] for m in raw["user_messages"][:3]]
        if raw.get("agent_messages"):
            s["agent_messages"] = [m[:200] for m in raw["agent_messages"][:2]]
        if raw.get("files_changed"):
            s["files_changed"] = raw["files_changed"][:10]
        if raw.get("topic"):
            s["topic"] = raw["topic"][:200]
        sessions.append(s)

    # 오늘의 행동 신호
    signals = conn.execute("""
        SELECT signal_type, content FROM behavioral_signals WHERE date = ?
    """, (date_str,)).fetchall()
    today_signals = [{"type": r["signal_type"], "content": r["content"]} for r in signals]

    # 최근 7일 반복 패턴
    repeated = get_repeated_signals(conn, date_str, days=7, min_count=2)

    # health data (graceful fallback if tables not yet migrated)
    try:
        exercises = query_exercises(conn, date_str, date_str)
        symptoms = query_symptoms(conn, date_str, date_str)
        meals = query_meals(conn, date_str, date_str)
        checkins = query_check_ins(conn, date_str, date_str)
    except Exception:
        exercises, symptoms, meals, checkins = [], [], [], []

    try:
        pantry_expiry = query_expiring_pantry(conn, days_ahead=3)
    except Exception as e:
        print(f"[daily_coach] pantry query failed: {e}", file=sys.stderr)
        pantry_expiry = {"expiring": [], "expired": []}

    try:
        pending = get_pending_work()
    except Exception as e:
        print(f"[daily_coach] pending work scan failed: {e}", file=sys.stderr)
        pending = []

    try:
        mistake_trends = get_mistake_trends(conn, date_str, days=14)
    except Exception as e:
        print(f"[daily_coach] mistake trends query failed: {e}", file=sys.stderr)
        mistake_trends = {"by_category": [], "uncategorized": [], "total": 0}

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
        "behavioral_signals": today_signals,
        "repeated_patterns": repeated,
        "exercises": exercises,
        "symptoms": symptoms,
        "meals": meals,
        "check_in": checkins[0] if checkins else None,
        "pantry_expiry": pantry_expiry,
        "pending_work": pending,
        "mistake_trends": mistake_trends,
    }


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


def _fmt_session_line(s: dict, indent: str = "    ") -> str:
    start = (s.get("start_at") or "")[11:16] or "?"
    tag = s.get("tag", "")
    summary = (s.get("summary") or "")[:80]
    return f"{indent}- {start} [{tag}] {summary}"


def _build_repos_detail(data: dict) -> str | None:
    """레포별 (> 브랜치별) 세션 상세."""
    sessions = data.get("sessions", [])
    if not sessions:
        return None

    lines = ["📂 레포별:"]
    for repo, total_dur, total_tok, branch_groups in group_sessions_by_repo_branch(sessions):
        sess_count = sum(len(bs) for bs in branch_groups.values())
        parts = [f"{sess_count}세션"]
        if total_dur > 0:
            h, m = divmod(total_dur, 60)
            parts.append(f"{h}시간 {m}분" if h else f"{m}분")
        if total_tok > 0:
            parts.append(f"{format_tokens(total_tok)} tokens")
        lines.append(f"  ▸ {repo} ({', '.join(parts)})")

        if has_meaningful_branches(branch_groups):
            for branch, bsess in branch_groups.items():
                if branch:
                    lines.append(f"    📌 {branch}")
                indent = "      " if branch else "    "
                for s in bsess[:3]:
                    lines.append(_fmt_session_line(s, indent))
        else:
            all_sess = list(branch_groups.values())[0] if branch_groups else []
            for s in all_sess[:3]:
                lines.append(_fmt_session_line(s))
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
    return "💡 패턴 피드백:\n" + "\n".join(f"  {ln}" for ln in lines)


def _build_behavioral_section(data: dict) -> str | None:
    """오늘의 행동 신호 + 반복 패턴."""
    lines = []
    signals = data.get("behavioral_signals", [])
    if signals:
        by_type: dict[str, list[str]] = {}
        for s in signals:
            by_type.setdefault(s["type"], []).append(s["content"])
        type_labels = {"decision": "결정", "mistake": "시행착오", "pattern": "패턴"}
        for t, label in type_labels.items():
            items = by_type.get(t, [])
            if items:
                lines.append(f"  {label}: {', '.join(items[:5])}")

    repeated = data.get("repeated_patterns", [])
    if repeated:
        if lines:
            lines.append("")
        lines.append("  ⚠️ 반복 패턴 (최근 7일):")
        for r in repeated:
            lines.append(f"    - \"{r['content']}\" ({r['count']}회)")

    if not lines:
        return None
    return "🧠 행동 신호:\n" + "\n".join(lines)


def _build_health_section(data: dict) -> str | None:
    lines = []

    ci = data.get("check_in")
    if ci:
        parts = []
        if ci.get("sleep_hours"):
            parts.append(f"수면 {ci['sleep_hours']}h")
        if ci.get("steps"):
            parts.append(f"걸음 {ci['steps']}")
        if ci.get("stress"):
            parts.append(f"스트레스 {ci['stress']}/10")
        if ci.get("water_ml"):
            parts.append(f"수분 {ci['water_ml']}ml")
        if parts:
            lines.append("  " + " · ".join(parts))

    exercises = data.get("exercises", [])
    if exercises:
        ex_parts = [f"{e['type']} {e['duration_min']}분" for e in exercises]
        lines.append(f"  운동: {', '.join(ex_parts)}")
    else:
        lines.append("  운동 기록 없음")

    meals = data.get("meals", [])
    eaten = [m for m in meals if not m.get("skipped")]
    skipped = [m for m in meals if m.get("skipped")]
    if meals:
        total_cal = sum(m.get("calories", 0) or 0 for m in eaten)
        total_protein = sum(m.get("protein_g", 0) or 0 for m in eaten)
        lines.append(f"  식사: {len(eaten)}끼 ({total_cal}kcal, 단백질 {total_protein:.0f}g)")
        if skipped:
            lines.append(f"  거른 끼니: {len(skipped)}끼")
    else:
        lines.append("  식사 기록 없음")

    symptoms = data.get("symptoms", [])
    if symptoms:
        sym_parts = [f"{s['type']}({s['severity']})" for s in symptoms]
        lines.append(f"  증상: {', '.join(sym_parts)}")

    if not lines:
        return None
    return "💊 건강:\n" + "\n".join(lines)


def _build_pantry_section(data: dict) -> str | None:
    pantry = data.get("pantry_expiry", {})
    expired = pantry.get("expired", [])
    expiring = pantry.get("expiring", [])
    if not expired and not expiring:
        return None
    lines = []
    if expired:
        lines.append(f"  만료: {', '.join(i['name'] for i in expired)}")
    if expiring:
        lines.append(f"  임박: {', '.join(i['name'] for i in expiring)}")
    return "🧊 유통기한:\n" + "\n".join(lines)


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

    health = _build_health_section(data)
    if health:
        sections.append(health)

    pantry = _build_pantry_section(data)
    if pantry:
        sections.append(pantry)

    feedback = _build_pattern_feedback(data)
    if feedback:
        sections.append(feedback)

    behavior = _build_behavioral_section(data)
    if behavior:
        sections.append(behavior)

    level = int(coach_state.get("escalation_level", "0"))
    sections.append(f"⚡ 코치 레벨: {level}")

    return "\n\n".join(sections)


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
        memory_dir = find_project_memory(repo)
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
    parser.add_argument("--dry-run", action="store_true", help="stdout only")
    parser.add_argument("--json", action="store_true", help="JSON data for LLM on-demand coaching")
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    conn = get_conn()
    try:
        data = get_today_data(conn, args.date)
        coach_state = get_coach_state(conn)
        update_overwork_tracking(conn, data, coach_state)
        coach_state = get_coach_state(conn)  # re-read after update

        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
            return

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
