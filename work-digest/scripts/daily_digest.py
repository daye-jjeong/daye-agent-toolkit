#!/usr/bin/env python3
"""Daily Digest — JSON → formatted summary → Telegram.

Reads parse_work_log.py JSON from stdin, generates a formatted summary
message, and sends it to Telegram via clawdbot.

Usage:
    python3 parse_work_log.py | python3 daily_digest.py
    python3 parse_work_log.py | python3 daily_digest.py --dry-run
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime

# ── Telegram config ──────────────────────────────────
TELEGRAM_GROUP = "-1003242721592"
THREAD_ID = None  # work-digest 전용 토픽 — 생성 후 설정

# ── Constants ────────────────────────────────────────
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
TELEGRAM_MAX_CHARS = 4096
TOPIC_SNIPPET_MAX = 30
TOPIC_SNIPPETS_PER_REPO = 2


# ── Message building ────────────────────────────────

def build_header(date_str: str) -> str:
    """Build header: 📋 M/DD(요일) 작업 다이제스트"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday_ko = WEEKDAYS_KO[dt.weekday()]
    return f"\U0001f4cb {dt.month}/{dt.day}({weekday_ko}) 작업 다이제스트"


def build_empty_message(date_str: str) -> str:
    """Build message for days with no sessions."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday_ko = WEEKDAYS_KO[dt.weekday()]
    return f"\U0001f4cb {dt.month}/{dt.day}({weekday_ko}) — 오늘 기록된 세션이 없습니다."


def format_duration(total_min: int) -> str:
    """Format duration as Xh Ym, omitting zero parts."""
    hours = total_min // 60
    minutes = total_min % 60
    if hours == 0:
        return f"{minutes}분"
    if minutes == 0:
        return f"{hours}시간"
    return f"{hours}시간 {minutes}분"


def build_time_summary(summary: dict) -> str:
    """Build time summary line."""
    sessions = summary["total_sessions"]
    duration = format_duration(summary["total_duration_min"])
    files = summary["total_files"]
    return f"\u23f1 {sessions}세션 \u00b7 {duration} \u00b7 파일 {files}개"


def _clean_topic(topic: str) -> str:
    """Clean up noisy topic strings."""
    # Strip local-command-caveat wrapper
    if topic.startswith("<local-command-caveat>"):
        return ""
    # Strip "Implement the following plan:" generic text
    if topic.strip() == "Implement the following plan:":
        return ""
    return topic.strip()


def _collect_repo_topics(sessions: list[dict]) -> dict[str, list[str]]:
    """Collect cleaned, non-empty topics per repo."""
    repo_topics: dict[str, list[str]] = {}
    for s in sessions:
        repo = s["repo"]
        if repo not in repo_topics:
            repo_topics[repo] = []
        cleaned = _clean_topic(s.get("topic", ""))
        if cleaned:
            repo_topics[repo].append(cleaned)
    return repo_topics


def build_repos_section(summary: dict, sessions: list[dict]) -> str:
    """Build repos section sorted by session count descending."""
    repos = summary["repos"]  # {repo: count}
    repo_topics = _collect_repo_topics(sessions)

    sorted_repos = sorted(repos.items(), key=lambda x: x[1], reverse=True)

    lines = ["\U0001f4c2 레포별:"]
    for repo, count in sorted_repos:
        topics = repo_topics.get(repo, [])
        snippets = []
        for t in topics[:TOPIC_SNIPPETS_PER_REPO]:
            snippet = t[:TOPIC_SNIPPET_MAX]
            if len(t) > TOPIC_SNIPPET_MAX:
                snippet += "..."
            snippets.append(snippet)

        if snippets:
            topics_str = ", ".join(snippets)
            line = f"  {repo}  {count}세션 ({topics_str})"
        else:
            line = f"  {repo}  {count}세션"
        lines.append(line)

    return "\n".join(lines)


def build_goals_section(goals: dict | None) -> str | None:
    """Build goals section. Returns None if no goals data."""
    if goals is None:
        return None

    items: list[dict] = []

    # top3 format: list of {title, status} or {name, status}
    if "top3" in goals and isinstance(goals["top3"], list):
        for item in goals["top3"]:
            if isinstance(item, dict):
                title = item.get("title") or item.get("name", "")
                status = item.get("status", "todo")
                items.append({"title": title, "status": status})

    # checklist format: list of {title, done} or {name, done}
    if "checklist" in goals and isinstance(goals["checklist"], list):
        for item in goals["checklist"]:
            if isinstance(item, dict):
                title = item.get("title") or item.get("name", "")
                done = item.get("done", False)
                status = item.get("status", "done" if done else "todo")
                items.append({"title": title, "status": status})

    if not items:
        return None

    status_icons = {
        "done": "\u2705",
        "in_progress": "\u26a0\ufe0f",
        "todo": "\u274c",
    }

    lines = ["\U0001f3af 목표 대비:"]
    for item in items:
        icon = status_icons.get(item["status"], "\u274c")
        title = item["title"]
        status_label = {
            "done": "완료",
            "in_progress": "진행 중",
            "todo": "작업 흔적 없음",
        }.get(item["status"], item["status"])
        lines.append(f"  {icon} {title} \u2192 {status_label}")

    return "\n".join(lines)


def build_pattern_feedback(summary: dict) -> str:
    """Build rule-based pattern feedback section."""
    lines: list[str] = []

    repo_count = len(summary["repos"])
    if repo_count >= 3:
        lines.append(f"\u2022 {repo_count}개 레포 컨텍스트 스위칭")

    total_errors = summary["total_errors"]
    if total_errors > 0:
        lines.append(f"\u2022 에러 {total_errors}건 발생")

    if not summary["has_tests"]:
        lines.append("\u2022 테스트 실행 0건")

    if not summary["has_commits"]:
        lines.append("\u2022 커밋 0건")

    total_duration_min = summary["total_duration_min"]
    if total_duration_min > 480:
        lines.append("\u2022 8시간 이상 장시간 작업")

    total_sessions = summary["total_sessions"]
    if total_duration_min < 30 and total_sessions > 0:
        lines.append("\u2022 짧은 세션이 많았음 — 집중 시간 확보 필요")

    if not lines:
        return ""

    return "\U0001f4a1 패턴 피드백:\n" + "\n".join(f"  {l}" for l in lines)


def build_message(data: dict) -> str:
    """Build the full digest message from parsed JSON data."""
    date_str = data["date"]
    sessions = data.get("sessions", [])
    summary = data.get("summary")
    goals = data.get("goals")

    # Empty day
    if not sessions or summary is None:
        return build_empty_message(date_str)

    sections: list[str] = []

    # Header
    sections.append(build_header(date_str))

    # Time summary
    sections.append(build_time_summary(summary))

    # Repos
    sections.append(build_repos_section(summary, sessions))

    # Goals (optional)
    goals_section = build_goals_section(goals)
    if goals_section:
        sections.append(goals_section)

    # Pattern feedback
    feedback = build_pattern_feedback(summary)
    if feedback:
        sections.append(feedback)

    message = "\n\n".join(sections)

    # Truncate if over Telegram limit
    if len(message) > TELEGRAM_MAX_CHARS:
        truncation_note = "\n\n... (truncated)"
        max_len = TELEGRAM_MAX_CHARS - len(truncation_note)
        message = message[:max_len] + truncation_note

    return message


# ── Telegram send ────────────────────────────────────

def send_telegram(message: str) -> None:
    """Send message to Telegram via clawdbot CLI."""
    cmd = ["clawdbot", "message", "send", "-t", TELEGRAM_GROUP]
    if THREAD_ID:
        cmd.extend(["--thread-id", str(THREAD_ID)])
    cmd.extend(["-m", message])

    try:
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True, timeout=30
        )
        print(f"[daily_digest] Telegram 전송 완료", file=sys.stderr)
        if result.stdout.strip():
            print(f"[daily_digest] {result.stdout.strip()}", file=sys.stderr)
    except FileNotFoundError:
        print(
            "[daily_digest] Error: clawdbot not found. Is it installed and in PATH?",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[daily_digest] Telegram 전송 실패: {e}", file=sys.stderr)
        if e.stderr:
            print(f"[daily_digest] stderr: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("[daily_digest] Telegram 전송 타임아웃 (30초)", file=sys.stderr)
        sys.exit(1)


# ── CLI ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate daily work digest and send to Telegram"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print message to stdout without sending to Telegram",
    )
    args = parser.parse_args()

    # Read JSON from stdin
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[daily_digest] Error: invalid JSON from stdin: {e}", file=sys.stderr)
        sys.exit(1)

    message = build_message(data)

    if args.dry_run:
        print(message)
    else:
        send_telegram(message)


if __name__ == "__main__":
    main()
