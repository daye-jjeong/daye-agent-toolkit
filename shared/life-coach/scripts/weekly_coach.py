#!/usr/bin/env python3
"""Weekly Coach — life-dashboard data-based weekly coaching report.

Usage:
    python3 weekly_coach.py                    # template report → telegram
    python3 weekly_coach.py --dry-run          # stdout only
    python3 weekly_coach.py --json             # JSON data (for LLM on-demand coaching)
    python3 weekly_coach.py --date 2026-03-02  # specific week (any date in that week)
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import get_conn, get_coach_state

_WD_SCRIPTS = Path(__file__).resolve().parent.parent.parent.parent / "cc" / "work-digest" / "scripts"
sys.path.insert(0, str(_WD_SCRIPTS))
from _common import send_telegram, format_tokens, WEEKDAYS_KO, TAG_ICONS, TELEGRAM_MAX_CHARS

KST = timezone(timedelta(hours=9))

from _helpers import find_project_memory


def get_week_dates(ref_date: str) -> list[str]:
    """ref_date가 속한 주의 월~일 날짜 리스트."""
    dt = datetime.strptime(ref_date, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def get_week_data(conn, dates: list[str]) -> dict:
    """7일간 daily_stats + activities 집계."""
    mon, sun = dates[0], dates[6]
    next_sun = (datetime.strptime(sun, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # daily_stats 조회
    stats_rows = conn.execute(
        "SELECT * FROM daily_stats WHERE date >= ? AND date <= ? ORDER BY date",
        (mon, sun),
    ).fetchall()
    stats_by_date = {r["date"]: dict(r) for r in stats_rows}

    # 토큰 합계 (SQL SUM)
    token_row = conn.execute(
        "SELECT COALESCE(SUM(token_total), 0) AS total FROM activities "
        "WHERE start_at >= ? AND start_at < ? AND source = 'cc'",
        (mon, next_sun),
    ).fetchone()
    total_tokens = token_row["total"]

    # work-context용 세션 요약 (필요 컬럼만)
    context_rows = conn.execute(
        "SELECT repo, summary, start_at FROM activities "
        "WHERE start_at >= ? AND start_at < ? AND source = 'cc' ORDER BY start_at",
        (mon, next_sun),
    ).fetchall()

    # 일별 집계
    daily = []
    total_sessions = 0
    total_hours = 0.0
    tags: dict[str, int] = {}
    repos: dict[str, int] = {}

    for date_str in dates:
        s = stats_by_date.get(date_str)
        if s:
            daily.append({
                "date": date_str,
                "weekday": WEEKDAYS_KO[datetime.strptime(date_str, "%Y-%m-%d").weekday()],
                "sessions": s["session_count"],
                "work_hours": s["work_hours"],
            })
            total_sessions += s["session_count"]
            total_hours += s["work_hours"]
            for tag, cnt in json.loads(s["tag_breakdown"] or "{}").items():
                tags[tag] = tags.get(tag, 0) + cnt
            for repo, cnt in json.loads(s["repos"] or "{}").items():
                repos[repo] = repos.get(repo, 0) + cnt
        else:
            daily.append({
                "date": date_str,
                "weekday": WEEKDAYS_KO[datetime.strptime(date_str, "%Y-%m-%d").weekday()],
                "sessions": 0,
                "work_hours": 0,
            })

    return {
        "dates": dates,
        "daily": daily,
        "total_sessions": total_sessions,
        "total_hours": round(total_hours, 1),
        "total_tokens": total_tokens,
        "tags": tags,
        "repos": repos,
        "context_rows": [dict(r) for r in context_rows],
    }


def _build_header(dates: list[str]) -> str:
    mon = datetime.strptime(dates[0], "%Y-%m-%d")
    sun = datetime.strptime(dates[6], "%Y-%m-%d")
    return (
        f"📊 {mon.month}/{mon.day}({WEEKDAYS_KO[mon.weekday()]})"
        f"~{sun.month}/{sun.day}({WEEKDAYS_KO[sun.weekday()]}) 주간 코칭"
    )


def _build_weekly_stats(data: dict) -> str:
    line = f"⏱ {data['total_sessions']}세션 · {data['total_hours']}시간"
    if data["total_tokens"] > 0:
        line += f" · {format_tokens(data['total_tokens'])} tokens"
    return line


def _build_daily_chart(data: dict) -> str:
    lines = ["📅 일별:"]
    for d in data["daily"]:
        bar = "█" * min(d["sessions"], 15)
        hours_str = f"{d['work_hours']}h" if d["work_hours"] > 0 else "-"
        lines.append(f"  {d['weekday']} {bar} {d['sessions']}세션 {hours_str}")
    return "\n".join(lines)


def _build_tag_section(data: dict) -> str | None:
    tags = data.get("tags", {})
    if not tags:
        return None
    total = sum(tags.values())
    sorted_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)
    parts = []
    for tag, count in sorted_tags:
        icon = TAG_ICONS.get(tag, "💡")
        pct = int(count / total * 100)
        parts.append(f"{icon}{tag} {count}건({pct}%)")
    return "🏷 " + " · ".join(parts)


def _build_repos_section(data: dict) -> str | None:
    repos = data.get("repos", {})
    if not repos:
        return None
    sorted_repos = sorted(repos.items(), key=lambda x: x[1], reverse=True)
    lines = ["📂 레포별:"]
    for repo, count in sorted_repos[:8]:
        lines.append(f"  ▸ {repo} ({count}세션)")
    return "\n".join(lines)


def _build_reflect_section(data: dict) -> str | None:
    """규칙 기반 reflect 질문."""
    questions = []
    repo_count = len(data.get("repos", {}))
    if repo_count >= 5:
        questions.append(f"{repo_count}개 레포에 분산 작업 — 다음 주 집중할 레포를 정할까?")
    if data["repos"]:
        top_repo, top_count = max(data["repos"].items(), key=lambda x: x[1])
        total = data["total_sessions"]
        top_pct = int(top_count / total * 100) if total else 0
        if top_pct >= 40:
            questions.append(f"{top_repo}에 {top_pct}% 집중 — 마일스톤 점검 시점?")
    tags = data.get("tags", {})
    if tags:
        total_tagged = sum(tags.values())
        debug_count = tags.get("디버깅", 0)
        if total_tagged and int(debug_count / total_tagged * 100) >= 25:
            questions.append("디버깅 비중 높음 — 테스트 커버리지 점검 필요?")
    if data["total_hours"] > 40:
        questions.append(f"이번 주 {data['total_hours']}시간 — 페이스 조절이 필요한가?")
    active_days = sum(1 for d in data["daily"] if d["sessions"] > 0)
    if active_days >= 6:
        questions.append("6일 이상 연속 작업 — 의도한 건가, 쉬는 날이 필요한가?")
    if not questions:
        return None
    lines = ["🔮 다음 주 생각해볼 것:"]
    for q in questions[:3]:
        lines.append(f"  • {q}")
    return "\n".join(lines)


def build_template_report(data: dict, coach_state: dict) -> str:
    sections = [_build_header(data["dates"])]

    if data["total_sessions"] == 0:
        sections.append("이번 주 기록된 세션 없음.")
        return "\n\n".join(sections)

    sections.append(_build_weekly_stats(data))
    sections.append(_build_daily_chart(data))

    tag_section = _build_tag_section(data)
    if tag_section:
        sections.append(tag_section)

    repos_section = _build_repos_section(data)
    if repos_section:
        sections.append(repos_section)

    reflect = _build_reflect_section(data)
    if reflect:
        sections.append(reflect)

    level = int(coach_state.get("escalation_level", "0"))
    sections.append(f"⚡ 코치 레벨: {level}")

    return "\n\n".join(sections)


def write_weekly_context(data: dict):
    """레포별 주간 work-context.md 갱신."""
    if data["total_sessions"] == 0:
        return
    mon, sun = data["dates"][0], data["dates"][6]
    # 레포별 세션 요약 (튜플로 저장하여 re-parse 방지)
    repo_summaries: dict[str, list[tuple[str, str]]] = {}
    for r in data.get("context_rows", []):
        repo = r.get("repo") or "unknown"
        sm = (r.get("summary") or "").strip()
        date_str = (r.get("start_at") or "")[:10]
        if sm and date_str:
            repo_summaries.setdefault(repo, []).append((date_str, sm))

    for repo, count in data["repos"].items():
        memory_dir = find_project_memory(repo)
        if not memory_dir:
            continue
        lines = [
            "# 최근 작업 컨텍스트",
            f"<!-- auto-generated by weekly_coach.py | {mon}~{sun} -->",
            "",
            f"이번 주 {count}세션 작업.",
            "",
        ]
        for date_str, sm in repo_summaries.get(repo, [])[:8]:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                lines.append(f"- {dt.month}/{dt.day}: {sm}")
            except ValueError:
                lines.append(f"- {date_str}: {sm}")
        lines.append("")
        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
            (memory_dir / "work-context.md").write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            print(f"[weekly_coach] {repo} work-context write failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Weekly coaching report")
    parser.add_argument("--dry-run", action="store_true", help="stdout only")
    parser.add_argument("--json", action="store_true", help="JSON data for LLM on-demand coaching")
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"),
                        help="Any date in the target week")
    args = parser.parse_args()

    dates = get_week_dates(args.date)
    conn = get_conn()
    try:
        data = get_week_data(conn, dates)
        coach_state = get_coach_state(conn)

        if args.json:
            # context_rows is for work-context only, not needed in JSON output
            output = {k: v for k, v in data.items() if k != "context_rows"}
            print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
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
            print("[weekly_coach] telegram sent", file=sys.stderr)
        else:
            print("[weekly_coach] telegram failed (check CHAT_ID_COACH)", file=sys.stderr)
            sys.exit(1)

    write_weekly_context(data)


if __name__ == "__main__":
    main()
