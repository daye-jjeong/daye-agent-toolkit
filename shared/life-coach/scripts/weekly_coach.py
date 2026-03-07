#!/usr/bin/env python3
"""Weekly Coach — life-dashboard data-based weekly coaching report.

Usage:
    python3 weekly_coach.py                 # LLM coaching + telegram
    python3 weekly_coach.py --dry-run       # stdout only
    python3 weekly_coach.py --no-llm        # template only
    python3 weekly_coach.py --date 2026-03-02  # specific week (any date in that week)
"""

import argparse
import json
import subprocess
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
COACHING_TIMEOUT_SEC = 60
PROMPTS_PATH = Path(__file__).resolve().parent.parent / "references" / "coaching-prompts.md"
PROJECTS_DIR = Path.home() / ".claude" / "projects"


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

    # activities 조회 (주간 전체)
    activities = conn.execute("""
        SELECT repo, tag, summary, start_at, end_at, duration_min,
               token_total, error_count, has_tests, has_commits
        FROM activities WHERE start_at >= ? AND start_at < ? AND source = 'cc'
        ORDER BY start_at
    """, (mon, next_sun)).fetchall()

    # 일별 집계
    daily = []
    total_sessions = 0
    total_hours = 0.0
    total_tokens = 0
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

    for a in activities:
        total_tokens += a["token_total"] or 0

    all_sessions = [dict(a) for a in activities]

    return {
        "dates": dates,
        "daily": daily,
        "total_sessions": total_sessions,
        "total_hours": round(total_hours, 1),
        "total_tokens": total_tokens,
        "tags": tags,
        "repos": repos,
        "sessions": all_sessions,
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


def build_data_section(data: dict) -> str:
    """LLM 프롬프트에 전달할 데이터 텍스트."""
    mon, sun = data["dates"][0], data["dates"][6]
    lines = [
        f"기간: {mon} ~ {sun}",
        f"총: {data['total_sessions']}세션, {data['total_hours']}시간, {format_tokens(data['total_tokens'])} tokens",
        "",
        "일별:",
    ]
    for d in data["daily"]:
        lines.append(f"  {d['date']}({d['weekday']}): {d['sessions']}세션, {d['work_hours']}h")
    tags = data.get("tags", {})
    if tags:
        lines.append("")
        tag_parts = [f"{t} {c}건" for t, c in sorted(tags.items(), key=lambda x: x[1], reverse=True)]
        lines.append(f"태그: {', '.join(tag_parts)}")
    repos = data.get("repos", {})
    if repos:
        lines.append("")
        repo_parts = [f"{r}({c}세션)" for r, c in sorted(repos.items(), key=lambda x: x[1], reverse=True)]
        lines.append(f"레포: {', '.join(repo_parts)}")
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


def generate_llm_coaching(data_section: str, tone_level: int) -> str | None:
    tone_desc = f"Level {tone_level}"
    try:
        full_template = PROMPTS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        full_template = ""

    # 주간 섹션 추출
    marker = "## 주간 코칭"
    idx = full_template.find(marker)
    if idx >= 0:
        template = full_template[idx:]
    else:
        template = (
            "다음은 주간 작업 데이터이다.\n\n{data_section}\n\n"
            "주간 트렌드와 방향성 코칭을 해라. 톤: {tone_level}. 한국어. 500자 이내."
        )

    prompt = template.replace("{data_section}", data_section).replace("{tone_level}", tone_desc)

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--no-session-persistence"],
            input=prompt, capture_output=True, text=True, timeout=COACHING_TIMEOUT_SEC,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        if result.returncode != 0:
            print(f"[weekly_coach] claude exit code {result.returncode}: {result.stderr.strip()}", file=sys.stderr)
    except FileNotFoundError:
        print("[weekly_coach] claude CLI not found", file=sys.stderr)
    except Exception as e:
        print(f"[weekly_coach] LLM failed: {e}", file=sys.stderr)
    return None


def _find_project_memory(repo_name: str) -> Path | None:
    if not PROJECTS_DIR.exists():
        return None
    for entry in PROJECTS_DIR.iterdir():
        if entry.is_dir() and entry.name.endswith(repo_name):
            return entry / "memory"
    return None


def write_weekly_context(data: dict):
    """레포별 주간 work-context.md 갱신."""
    if data["total_sessions"] == 0:
        return
    mon, sun = data["dates"][0], data["dates"][6]
    # 레포별 세션 요약
    repo_summaries: dict[str, list[str]] = {}
    for s in data.get("sessions", []):
        repo = s.get("repo") or "unknown"
        sm = (s.get("summary") or "").strip()
        date_str = (s.get("start_at") or "")[:10]
        if sm and date_str:
            repo_summaries.setdefault(repo, []).append(f"{date_str}: {sm}")

    for repo, count in data["repos"].items():
        memory_dir = _find_project_memory(repo)
        if not memory_dir:
            continue
        lines = [
            "# 최근 작업 컨텍스트",
            f"<!-- auto-generated by weekly_coach.py | {mon}~{sun} -->",
            "",
            f"이번 주 {count}세션 작업.",
            "",
        ]
        for sm in repo_summaries.get(repo, [])[:8]:
            try:
                date_part = sm.split(":")[0].strip()
                dt = datetime.strptime(date_part, "%Y-%m-%d")
                rest = sm[len(date_part) + 2:]
                lines.append(f"- {dt.month}/{dt.day}: {rest}")
            except (ValueError, IndexError):
                lines.append(f"- {sm}")
        lines.append("")
        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
            (memory_dir / "work-context.md").write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            print(f"[weekly_coach] {repo} work-context write failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Weekly coaching report")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"),
                        help="Any date in the target week")
    args = parser.parse_args()

    dates = get_week_dates(args.date)
    conn = get_conn()
    try:
        data = get_week_data(conn, dates)
        coach_state = get_coach_state(conn)
        level = int(coach_state.get("escalation_level", "0"))

        if data["total_sessions"] == 0 or args.no_llm:
            message = build_template_report(data, coach_state)
        else:
            data_section = build_data_section(data)
            llm_result = generate_llm_coaching(data_section, level)
            if llm_result:
                header = _build_header(dates)
                stats = _build_weekly_stats(data)
                message = f"{header}\n\n{stats}\n\n{llm_result}\n\n⚡ 코치 레벨: {level}"
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
            print("[weekly_coach] telegram sent", file=sys.stderr)
        else:
            print("[weekly_coach] telegram failed (check CHAT_ID_COACH)", file=sys.stderr)
            sys.exit(1)

    write_weekly_context(data)


if __name__ == "__main__":
    main()
