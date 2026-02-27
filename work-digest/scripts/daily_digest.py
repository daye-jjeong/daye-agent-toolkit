#!/usr/bin/env python3
"""Daily Digest — JSON → LLM 분석 or 템플릿 → Telegram.

Reads parse_work_log.py JSON from stdin, generates a digest message
(via claude CLI or fallback template), and sends to Telegram.

Usage:
    python3 parse_work_log.py | python3 daily_digest.py              # LLM + Telegram
    python3 parse_work_log.py | python3 daily_digest.py --dry-run    # LLM + stdout
    python3 parse_work_log.py | python3 daily_digest.py --no-llm     # template only
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path

# ── Telegram config ──────────────────────────────────
TELEGRAM_CHAT_ID = "8514441011"  # 개인 DM (notify.sh와 동일)
TELEGRAM_BOT_TOKEN_DEFAULT = "8584213613:AAE5h2B3m9hGD1nIMUmLvcTmSwJDph25lic"

# ── Constants ────────────────────────────────────────
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
TELEGRAM_MAX_CHARS = 4096
TOPIC_SNIPPET_MAX = 30
TOPIC_SNIPPETS_PER_REPO = 2
BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_TEMPLATE = BASE_DIR / "references" / "prompt-template.md"


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


# ── LLM analysis via claude CLI ──────────────────────

def _load_system_prompt() -> str:
    """Load system prompt from prompt-template.md."""
    try:
        text = PROMPT_TEMPLATE.read_text(encoding="utf-8")
        # Extract content between first ``` pair in ## System Prompt
        in_block = False
        lines = []
        for line in text.splitlines():
            if line.strip() == "```" and not in_block:
                in_block = True
                continue
            if line.strip() == "```" and in_block:
                break
            if in_block:
                lines.append(line)
        return "\n".join(lines) if lines else ""
    except FileNotFoundError:
        return ""


def analyze_with_llm(data: dict) -> str | None:
    """Call claude CLI in print mode for natural language analysis.

    Returns LLM-generated message, or None if claude CLI unavailable.
    Uses haiku for cost efficiency (~0.001 USD per call).
    """
    system_prompt = _load_system_prompt()
    json_str = json.dumps(data, ensure_ascii=False, indent=2)

    user_prompt = (
        f"다음은 오늘({data['date']})의 Claude Code 작업 로그 JSON입니다.\n\n"
        f"{json_str}\n\n"
        "위 데이터를 분석해서 일일 작업 다이제스트를 생성해주세요.\n"
        "텔레그램 메시지 형태로, 4096자 이내로 작성해주세요.\n"
        "4개 섹션: 오늘의 요약, 레포별 작업, 목표 대비 진행(목표 데이터 있을 때만), 패턴 피드백."
    )

    cmd = [
        "claude", "-p",
        "--model", "haiku",
        "--no-session-persistence",
    ]
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    try:
        result = subprocess.run(
            cmd,
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            # Truncate if over Telegram limit
            if len(output) > TELEGRAM_MAX_CHARS:
                output = output[:TELEGRAM_MAX_CHARS - 20] + "\n\n... (truncated)"
            return output
        print(f"[daily_digest] claude CLI returned code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(f"[daily_digest] stderr: {result.stderr[:200]}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("[daily_digest] claude CLI not found — falling back to template", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("[daily_digest] claude CLI timeout (60s) — falling back to template", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[daily_digest] claude CLI error: {e} — falling back to template", file=sys.stderr)
        return None


# ── Telegram send ────────────────────────────────────

def send_telegram(message: str) -> None:
    """Send message to Telegram via Bot API (stdlib only, no requests)."""
    # 환경변수보다 스크립트 내장 토큰 우선 (일관성)
    bot_token = TELEGRAM_BOT_TOKEN_DEFAULT

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                print("[daily_digest] Telegram 전송 완료", file=sys.stderr)
            else:
                print(f"[daily_digest] Telegram API error: {result}", file=sys.stderr)
                sys.exit(1)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[daily_digest] Telegram HTTP {e.code}: {body[:200]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[daily_digest] Telegram 연결 실패: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[daily_digest] Telegram 전송 실패: {e}", file=sys.stderr)
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
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM analysis, use template-based message only",
    )
    args = parser.parse_args()

    # Read JSON from stdin
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[daily_digest] Error: invalid JSON from stdin: {e}", file=sys.stderr)
        sys.exit(1)

    # Empty day — no LLM needed
    if not data.get("sessions"):
        message = build_empty_message(data.get("date", "?"))
    elif args.no_llm:
        message = build_message(data)
    else:
        # Try LLM first, fallback to template
        message = analyze_with_llm(data)
        if message is None:
            print("[daily_digest] Using template fallback", file=sys.stderr)
            message = build_message(data)

    if args.dry_run:
        print(message)
    else:
        send_telegram(message)


if __name__ == "__main__":
    main()
