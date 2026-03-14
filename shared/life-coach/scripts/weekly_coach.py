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
from db import get_conn, get_coach_state, query_exercises, query_symptoms, query_meals, query_check_ins, get_repeated_signals, get_mistake_trends

_WD_SCRIPTS = Path(__file__).resolve().parent.parent.parent.parent / "cc" / "work-digest" / "scripts"
sys.path.insert(0, str(_WD_SCRIPTS))
from _common import send_telegram, format_tokens, WEEKDAYS_KO, TAG_ICONS, TELEGRAM_MAX_CHARS

KST = timezone(timedelta(hours=9))

from _helpers import find_project_memory, get_pending_work


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
        "WHERE start_at >= ? AND start_at < ?",
        (mon, next_sun),
    ).fetchone()
    total_tokens = token_row["total"]

    # work-context용 세션 요약 (필요 컬럼만)
    context_rows = conn.execute(
        "SELECT repo, summary, start_at FROM activities "
        "WHERE start_at >= ? AND start_at < ? ORDER BY start_at",
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

    # health data (graceful fallback if tables not yet migrated)
    try:
        exercises = query_exercises(conn, mon, sun)
        symptoms = query_symptoms(conn, mon, sun)
        meals = query_meals(conn, mon, sun)
        checkins = query_check_ins(conn, mon, sun)
    except Exception:
        exercises, symptoms, meals, checkins = [], [], [], []

    # behavioral signals (weekly aggregate)
    try:
        all_signals = conn.execute(
            "SELECT signal_type, content, COUNT(*) as cnt "
            "FROM behavioral_signals WHERE date >= ? AND date <= ? "
            "GROUP BY signal_type, content ORDER BY cnt DESC",
            (mon, sun),
        ).fetchall()
        weekly_signals = [{"signal_type": r["signal_type"], "content": r["content"], "count": r["cnt"]}
                          for r in all_signals]
        repeated = get_repeated_signals(conn, sun, days=7, min_count=2)
    except Exception:
        weekly_signals, repeated = [], []

    # ── 주간 점검 4종 ──
    review_items = {}

    # 1) "기타" 태그 세션 수
    try:
        untagged = conn.execute(
            "SELECT COUNT(*) as cnt FROM activities "
            "WHERE start_at >= ? AND start_at < ? AND (tag = '기타' OR tag = '' OR tag IS NULL)",
            (mon, next_sun),
        ).fetchone()
        review_items["untagged_sessions"] = untagged["cnt"]
    except Exception as e:
        print(f"[weekly_coach] untagged sessions query failed: {e}", file=sys.stderr)
        review_items["untagged_sessions"] = 0

    # 2) 미분류 mistake 수
    try:
        mt = get_mistake_trends(conn, sun, days=7)
        review_items["uncategorized_mistakes"] = len(mt.get("uncategorized", []))
        review_items["mistake_trends"] = mt
    except Exception as e:
        print(f"[weekly_coach] mistake trends query failed: {e}", file=sys.stderr)
        review_items["uncategorized_mistakes"] = 0
        review_items["mistake_trends"] = {"by_category": [], "uncategorized": [], "total": 0}

    # 3) empty summary 세션 수
    try:
        empty_sum = conn.execute(
            "SELECT COUNT(*) as cnt FROM activities "
            "WHERE start_at >= ? AND start_at < ? AND (summary = '' OR summary IS NULL)",
            (mon, next_sun),
        ).fetchone()
        review_items["empty_summaries"] = empty_sum["cnt"]
    except Exception as e:
        print(f"[weekly_coach] empty summaries query failed: {e}", file=sys.stderr)
        review_items["empty_summaries"] = 0

    # 4) stale worktrees
    try:
        review_items["stale_worktrees"] = get_pending_work()
    except Exception as e:
        print(f"[weekly_coach] stale worktrees scan failed: {e}", file=sys.stderr)
        review_items["stale_worktrees"] = []

    return {
        "dates": dates,
        "daily": daily,
        "total_sessions": total_sessions,
        "total_hours": round(total_hours, 1),
        "total_tokens": total_tokens,
        "tags": tags,
        "repos": repos,
        "context_rows": [dict(r) for r in context_rows],
        "exercises": exercises,
        "symptoms": symptoms,
        "meals": meals,
        "check_ins": checkins,
        "weekly_signals": weekly_signals,
        "repeated_patterns": repeated,
        "review_items": review_items,
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


def _build_behavioral_section(data: dict) -> str | None:
    """주간 행동 신호 집계 + 반복 패턴."""
    lines = []

    signals = data.get("weekly_signals", [])
    if signals:
        by_type: dict[str, list[tuple[str, int]]] = {}
        for s in signals:
            by_type.setdefault(s["signal_type"], []).append((s["content"], s["count"]))
        type_labels = {"decision": "결정", "mistake": "시행착오", "pattern": "패턴"}
        for t, label in type_labels.items():
            items = by_type.get(t, [])
            if items:
                top = items[:5]
                formatted = ", ".join(
                    f"{c}({n})" if n > 1 else c for c, n in top
                )
                lines.append(f"  {label}: {formatted}")

    repeated = data.get("repeated_patterns", [])
    if repeated:
        if lines:
            lines.append("")
        lines.append("  ⚠️ 반복 패턴:")
        for r in repeated[:5]:
            lines.append(f"    - \"{r['content']}\" ({r['count']}회)")

    if not lines:
        return None
    return "🧠 주간 행동 신호:\n" + "\n".join(lines)


def _build_health_weekly(data: dict) -> str | None:
    lines = []

    exercises = data.get("exercises", [])
    if exercises:
        ex_days = len(set(e["date"] for e in exercises))
        total_min = sum(e["duration_min"] for e in exercises)
        pt_count = len([e for e in exercises if e["type"] == "PT"])
        lines.append(f"  운동 {ex_days}일 ({total_min}분) · PT {pt_count}회/2")

    symptoms = data.get("symptoms", [])
    if symptoms:
        lines.append(f"  증상 {len(symptoms)}건")

    meals = data.get("meals", [])
    if meals:
        eaten = len([m for m in meals if not m.get("skipped")])
        skipped = len([m for m in meals if m.get("skipped")])
        lines.append(f"  식사 {eaten}끼 · 거름 {skipped}끼")

    checkins = data.get("check_ins", [])
    if checkins:
        sleep_data = [c["sleep_hours"] for c in checkins if c.get("sleep_hours")]
        if sleep_data:
            avg_sleep = sum(sleep_data) / len(sleep_data)
            lines.append(f"  평균 수면 {avg_sleep:.1f}h ({len(checkins)}일 체크인)")

    if not lines:
        return None
    return "💊 주간 건강:\n" + "\n".join(lines)


def _build_review_section(data: dict) -> str | None:
    """주간 점검 결과."""
    ri = data.get("review_items", {})
    if not ri:
        return None
    lines = []
    untagged = ri.get("untagged_sessions", 0)
    if untagged > 0:
        lines.append(f"  🏷 미분류 태그: {untagged}세션")
    uncategorized = ri.get("uncategorized_mistakes", 0)
    if uncategorized > 0:
        lines.append(f"  ⚠️ 미분류 mistake: {uncategorized}건")
    empty = ri.get("empty_summaries", 0)
    if empty > 0:
        lines.append(f"  📝 빈 summary: {empty}세션")
    stale = ri.get("stale_worktrees", [])
    if stale:
        repos = set(w.get("repo", "") for w in stale)
        lines.append(f"  🌿 활성 worktree: {len(stale)}개 ({', '.join(sorted(repos)[:5])})")
    if not lines:
        return None
    return "🔍 주간 점검:\n" + "\n".join(lines)


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

    behavioral = _build_behavioral_section(data)
    if behavioral:
        sections.append(behavioral)

    health_weekly = _build_health_weekly(data)
    if health_weekly:
        sections.append(health_weekly)

    review = _build_review_section(data)
    if review:
        sections.append(review)

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
        ok = send_telegram(message, chat_id_key="CHAT_ID_WEEKLY", silent=True)
        if ok:
            print("[weekly_coach] telegram sent", file=sys.stderr)
        else:
            print("[weekly_coach] telegram failed (check CHAT_ID_COACH)", file=sys.stderr)
            sys.exit(1)

    write_weekly_context(data)


if __name__ == "__main__":
    main()
