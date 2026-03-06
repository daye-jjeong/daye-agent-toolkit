#!/usr/bin/env python3
"""Weekly Digest — 주간 작업 리포트 생성 + Telegram 전송.

월~일 7일간의 daily work-log를 집계하여 주간 트렌드를 분석한다.
LLM 요약 + 템플릿 fallback 구조는 daily_digest.py와 동일.

Usage:
    python3 weekly_digest.py                    # 이번 주 (LLM + Telegram)
    python3 weekly_digest.py --date 2026-03-02  # 해당 주 월요일 기준
    python3 weekly_digest.py --dry-run          # stdout 출력만
    python3 weekly_digest.py --no-llm           # 템플릿만
"""

import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
TELEGRAM_MAX_CHARS = 4096
TELEGRAM_CHAT_ID = "8514441011"
TELEGRAM_BOT_TOKEN = "8584213613:AAE5h2B3m9hGD1nIMUmLvcTmSwJDph25lic"

BASE_DIR = Path(__file__).resolve().parent.parent
PARSE_SCRIPT = Path(__file__).resolve().parent / "parse_work_log.py"


# ── Data collection ──────────────────────────────

def get_week_dates(ref_date: str) -> list[str]:
    """ref_date가 속한 주의 월~일 날짜 리스트 반환."""
    dt = datetime.strptime(ref_date, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def collect_week_data(dates: list[str]) -> dict:
    """각 날짜의 parse_work_log 결과를 수집."""
    daily_data = []
    for date_str in dates:
        try:
            result = subprocess.run(
                ["python3", str(PARSE_SCRIPT), "--date", date_str],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                daily_data.append(data)
            else:
                daily_data.append({"date": date_str, "sessions": [], "summary": None})
        except Exception:
            daily_data.append({"date": date_str, "sessions": [], "summary": None})
    return {"dates": dates, "daily": daily_data}


# ── Aggregation ──────────────────────────────────

def aggregate_week(week_data: dict) -> dict:
    """주간 집계 통계."""
    total_sessions = 0
    total_duration = 0
    total_files = 0
    repos: dict[str, int] = {}
    tags: dict[str, int] = {}
    daily_sessions: list[dict] = []  # {date, count, duration}
    all_summaries: list[str] = []

    for day in week_data["daily"]:
        sessions = day.get("sessions", [])
        summary = day.get("summary")
        day_count = len(sessions)
        day_duration = 0

        for s in sessions:
            total_sessions += 1
            dur = s.get("duration_min") or 0
            total_duration += dur
            day_duration += dur
            total_files += s.get("file_count", 0)

            repo = s.get("repo", "unknown")
            repos[repo] = repos.get(repo, 0) + 1

            tag = s.get("tag", "").strip()
            if tag:
                tags[tag] = tags.get(tag, 0) + 1

            sm = s.get("summary", "").strip()
            if sm:
                all_summaries.append(f"{day['date']} {repo}: {sm}")

        daily_sessions.append({
            "date": day["date"],
            "weekday": WEEKDAYS_KO[datetime.strptime(day["date"], "%Y-%m-%d").weekday()],
            "sessions": day_count,
            "duration_min": day_duration,
        })

    return {
        "total_sessions": total_sessions,
        "total_duration_min": total_duration,
        "total_files": total_files,
        "repos": repos,
        "tags": tags,
        "daily_sessions": daily_sessions,
        "summaries": all_summaries,
    }


# ── Message building ────────────────────────────

TAG_ICONS = {
    "코딩": "\U0001f4bb", "디버깅": "\U0001f41b", "리서치": "\U0001f50d",
    "리뷰": "\U0001f4dd", "ops": "\u2699\ufe0f", "설정": "\U0001f527",
    "문서": "\U0001f4d6", "기타": "\U0001f4a1",
}


def format_duration(total_min: int) -> str:
    hours = total_min // 60
    minutes = total_min % 60
    if hours == 0:
        return f"{minutes}분"
    if minutes == 0:
        return f"{hours}시간"
    return f"{hours}시간 {minutes}분"


def build_reflect_section(agg: dict) -> str | None:
    """규칙 기반 reflect 질문 생성. 데이터 패턴에서 질문을 도출."""
    questions: list[str] = []

    # 레포 수가 많으면 → 집중 질문
    repo_count = len(agg["repos"])
    if repo_count >= 5:
        questions.append(
            f"{repo_count}개 레포에 분산 작업 — 다음 주는 집중할 레포를 정할까?"
        )

    # 특정 레포 세션 비중이 높으면 → 장기 프로젝트 질문
    if agg["repos"]:
        total = agg["total_sessions"]
        top_repo, top_count = max(agg["repos"].items(), key=lambda x: x[1])
        top_pct = int(top_count / total * 100) if total else 0
        if top_pct >= 40:
            questions.append(
                f"{top_repo}에 {top_pct}% 집중 — 마일스톤 점검이 필요한 시점?"
            )

    # 디버깅 비율 높으면 → 테스트 질문
    if agg["tags"]:
        total_tagged = sum(agg["tags"].values())
        debug_count = agg["tags"].get("디버깅", 0)
        debug_pct = int(debug_count / total_tagged * 100) if total_tagged else 0
        if debug_pct >= 25:
            questions.append(
                f"디버깅 {debug_pct}% — 테스트 커버리지나 코드 품질 점검 필요?"
            )

    # 작업 시간이 길면 → 번아웃 질문
    if agg["total_duration_min"] > 40 * 60:  # 40시간+
        hours = agg["total_duration_min"] // 60
        questions.append(
            f"이번 주 {hours}시간 작업 — 페이스 조절이 필요한가?"
        )

    # 활동 없는 날이 없으면 → 휴식 질문
    active_days = sum(1 for d in agg["daily_sessions"] if d["sessions"] > 0)
    if active_days >= 6:
        questions.append("6일 이상 연속 작업 — 의도한 건가, 쉬는 날이 필요한가?")

    if not questions:
        return None

    lines = ["\U0001f52e 다음 주 생각해볼 것:"]
    for q in questions[:3]:  # 최대 3개
        lines.append(f"  \u2022 {q}")
    return "\n".join(lines)


def build_message(dates: list[str], agg: dict) -> str:
    """Build weekly digest message."""
    mon = datetime.strptime(dates[0], "%Y-%m-%d")
    sun = datetime.strptime(dates[6], "%Y-%m-%d")
    header = f"\U0001f4ca {mon.month}/{mon.day}({WEEKDAYS_KO[mon.weekday()]})~{sun.month}/{sun.day}({WEEKDAYS_KO[sun.weekday()]}) 주간 리포트"

    if agg["total_sessions"] == 0:
        return f"{header}\n\n이번 주 기록된 세션이 없습니다."

    sections = [header]

    # 주간 요약
    sections.append(
        f"\u23f1 {agg['total_sessions']}세션 \u00b7 "
        f"{format_duration(agg['total_duration_min'])} \u00b7 "
        f"파일 {agg['total_files']}개"
    )

    # 일별 활동
    daily_lines = ["\U0001f4c5 일별:"]
    for d in agg["daily_sessions"]:
        bar = "\u2588" * min(d["sessions"], 15)  # 최대 15칸
        dur = format_duration(d["duration_min"]) if d["duration_min"] else "-"
        daily_lines.append(f"  {d['weekday']} {bar} {d['sessions']}세션 {dur}")
    sections.append("\n".join(daily_lines))

    # 태그 비율
    if agg["tags"]:
        total_tagged = sum(agg["tags"].values())
        sorted_tags = sorted(agg["tags"].items(), key=lambda x: x[1], reverse=True)
        parts = []
        for tag, count in sorted_tags:
            icon = TAG_ICONS.get(tag, "\U0001f4a1")
            pct = int(count / total_tagged * 100)
            parts.append(f"{icon}{tag} {count}건({pct}%)")
        sections.append("\U0001f3f7 작업 유형: " + " · ".join(parts))

    # 레포 순위
    if agg["repos"]:
        sorted_repos = sorted(agg["repos"].items(), key=lambda x: x[1], reverse=True)
        repo_lines = ["\U0001f4c2 레포별:"]
        for repo, count in sorted_repos[:8]:
            repo_lines.append(f"  {repo}  {count}세션")
        sections.append("\n".join(repo_lines))

    # Reflect — 다음 주 생각해볼 것
    reflect = build_reflect_section(agg)
    if reflect:
        sections.append(reflect)

    message = "\n\n".join(sections)
    if len(message) > TELEGRAM_MAX_CHARS:
        message = message[:TELEGRAM_MAX_CHARS - 20] + "\n\n... (truncated)"
    return message


# ── LLM analysis ────────────────────────────────

def analyze_with_llm(dates: list[str], agg: dict) -> str | None:
    """주간 데이터를 LLM으로 분석."""
    json_str = json.dumps(agg, ensure_ascii=False, indent=2)
    mon = dates[0]
    sun = dates[6]
    prompt = (
        f"다음은 {mon}~{sun} 주간 Claude Code 작업 통계 JSON이다.\n\n"
        f"{json_str}\n\n"
        "주간 작업 리포트를 한국어로 작성해라. 텔레그램 메시지 형태, 4096자 이내.\n"
        "섹션: 주간 요약, 일별 활동 패턴, 작업 유형 분석, 레포별 작업, 주간 피드백, 🔮 다음 주 생각해볼 것.\n"
        "피드백: 집중 요일, 작업 유형 편중, 개선 제안 등.\n"
        "'다음 주 생각해볼 것' 섹션 규칙:\n"
        "- 데이터에서 관찰되는 패턴을 바탕으로 2-3개 질문을 던져라.\n"
        "- 예: 특정 레포에 3일 이상 연속 작업 → '장기 프로젝트인가? 마일스톤 점검 필요?'\n"
        "- 예: 디버깅 비율 30%+ → '테스트 커버리지 점검 시점?'\n"
        "- 예: 레포가 5개+ → '컨텍스트 스위칭이 많았는데, 다음 주는 집중할 레포를 정할까?'\n"
        "- 답을 주지 말고 질문만 던져라. 판단은 사용자가 한다."
    )
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--no-session-persistence"],
            input=prompt, capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            if len(output) > TELEGRAM_MAX_CHARS:
                output = output[:TELEGRAM_MAX_CHARS - 20] + "\n\n... (truncated)"
            return output
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return None


# ── Telegram ────────────────────────────────────

def send_telegram(message: str):
    payload = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data=payload,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                print("[weekly_digest] Telegram 전송 완료", file=sys.stderr)
            else:
                print(f"[weekly_digest] Telegram API error: {result}", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        print(f"[weekly_digest] Telegram 전송 실패: {e}", file=sys.stderr)
        sys.exit(1)


# ── Work context (feedback loop) ─────────────────

WORK_CONTEXT_PATH = Path.home() / ".claude" / "work-context.md"


def write_weekly_context(dates: list[str], agg: dict):
    """주간 작업 컨텍스트를 ~/.claude/work-context.md에 기록.

    daily_digest가 쓰는 같은 파일을 덮어쓴다 (주간이 더 포괄적).
    """
    if agg["total_sessions"] == 0:
        return

    mon = dates[0]
    sun = dates[6]

    lines = [
        "# 최근 작업 컨텍스트",
        f"<!-- auto-generated by weekly_digest.py | {mon}~{sun} -->",
        "",
        f"## {mon}~{sun} 주간 요약",
        "",
    ]

    # 레포별 세션 수 + 요약들
    sorted_repos = sorted(agg["repos"].items(), key=lambda x: x[1], reverse=True)
    for repo, count in sorted_repos:
        lines.append(f"### {repo} ({count}세션)")
        # 해당 레포의 요약들
        repo_summaries = [s for s in agg["summaries"] if f" {repo}: " in s]
        for sm in repo_summaries[:5]:
            # "2026-03-05 repo: 요약" → "3/5: 요약"
            parts = sm.split(": ", 1)
            if len(parts) == 2:
                date_part = parts[0].split(" ")[0]  # "2026-03-05"
                try:
                    dt = datetime.strptime(date_part, "%Y-%m-%d")
                    lines.append(f"- {dt.month}/{dt.day}: {parts[1]}")
                except ValueError:
                    lines.append(f"- {sm}")
            else:
                lines.append(f"- {sm}")
        lines.append("")

    # 태그 분포
    if agg["tags"]:
        sorted_tags = sorted(agg["tags"].items(), key=lambda x: x[1], reverse=True)
        total = sum(agg["tags"].values())
        tag_parts = [f"{t} {c}건({int(c/total*100)}%)" for t, c in sorted_tags]
        lines.append(f"작업 유형: {', '.join(tag_parts)}")
        lines.append("")

    # 일별 활동 패턴
    active_days = [d for d in agg["daily_sessions"] if d["sessions"] > 0]
    if active_days:
        busiest = max(active_days, key=lambda d: d["sessions"])
        lines.append(f"가장 활발: {busiest['weekday']}({busiest['sessions']}세션)")
        lines.append("")

    try:
        WORK_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
        WORK_CONTEXT_PATH.write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        print(f"[weekly_digest] work-context 쓰기 실패: {e}", file=sys.stderr)


# ── CLI ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate weekly work digest")
    parser.add_argument(
        "--date",
        default=datetime.now(KST).strftime("%Y-%m-%d"),
        help="Any date in the target week (default: today KST)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    dates = get_week_dates(args.date)
    week_data = collect_week_data(dates)
    agg = aggregate_week(week_data)

    if agg["total_sessions"] == 0 or args.no_llm:
        message = build_message(dates, agg)
    else:
        message = analyze_with_llm(dates, agg)
        if message is None:
            message = build_message(dates, agg)

    if args.dry_run:
        print(message)
    else:
        send_telegram(message)

    # 주간 작업 컨텍스트 갱신 (피드백 루프)
    write_weekly_context(dates, agg)


if __name__ == "__main__":
    main()
