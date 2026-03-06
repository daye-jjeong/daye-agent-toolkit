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
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from _common import (
    WEEKDAYS_KO, WORK_TAGS_SET,
    format_tokens, send_telegram,
)

# ── Constants ────────────────────────────────────────
TELEGRAM_MAX_CHARS = 4096


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


def _format_tokens(n: int) -> str:
    return format_tokens(n)


def build_time_summary(summary: dict) -> str:
    """Build time summary line with token usage."""
    sessions = summary["total_sessions"]
    duration = format_duration(summary["total_duration_min"])
    files = summary["total_files"]
    tokens = summary.get("tokens", {})
    total_tokens = tokens.get("total", 0)
    line = f"\u23f1 {sessions}세션 \u00b7 {duration} \u00b7 파일 {files}개"
    if total_tokens > 0:
        line += f" \u00b7 {_format_tokens(total_tokens)} tokens"
    return line


NOISE_PATTERNS = [
    "<local-command-caveat>",
    "<command-name>",
    "Implement the following plan:",
]

# 태그 단어만 있는 요약은 노이즈 (예: "코딩", "리서치")


def _clean_summary(raw: str) -> str:
    """멀티라인 요약에서 의미 있는 내용만 추출."""
    if not raw:
        return ""
    lines = raw.strip().splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip().strip("*").strip()
        if not stripped:
            continue
        if stripped in WORK_TAGS_SET:
            continue
        # 마크다운 구분선, 헤딩 스킵
        if stripped.startswith("---") or stripped.startswith("##"):
            continue
        cleaned_lines.append(line.strip())
    return " ".join(cleaned_lines)[:200]


def _clean_topic(topic: str) -> str:
    """Clean up noisy topic strings."""
    for pat in NOISE_PATTERNS:
        if topic.startswith(pat):
            return ""
    t = topic.strip()
    # URL만 있는 토픽은 스킵
    if t.startswith("http://") or t.startswith("https://"):
        return ""
    return t


def _collect_repo_data(sessions: list[dict]) -> dict[str, dict]:
    """세션 리스트에서 레포별 topics, duration, tokens를 한 패스로 수집."""
    repos: dict[str, dict] = {}
    for s in sessions:
        repo = s["repo"]
        if repo not in repos:
            repos[repo] = {"topics": [], "duration": 0, "tokens": 0}
        rd = repos[repo]

        # duration + tokens
        rd["duration"] += s.get("duration_min") or 0
        t = s.get("tokens") or {}
        rd["tokens"] += sum(t.get(k, 0) for k in ("Input", "Output", "Cache read", "Cache create"))

        # topics (LLM 요약 우선, 중복 제거)
        summary = _clean_summary(s.get("summary", ""))
        if summary:
            # 이미 같은 내용이 있으면 스킵 (정확 일치)
            if summary not in rd["topics"]:
                rd["topics"].append(summary)
        else:
            cleaned = _clean_topic(s.get("topic", ""))
            if cleaned and cleaned not in rd["topics"]:
                rd["topics"].append(cleaned)
    return repos


TAG_ICONS = {
    "코딩": "\U0001f4bb",
    "디버깅": "\U0001f41b",
    "리서치": "\U0001f50d",
    "리뷰": "\U0001f4dd",
    "ops": "\u2699\ufe0f",
    "설정": "\U0001f527",
    "문서": "\U0001f4d6",
    "기타": "\U0001f4a1",
}


def build_tag_section(sessions: list[dict]) -> str | None:
    """Build tag breakdown section. Returns None if no tags."""
    tag_counts: dict[str, int] = {}
    for s in sessions:
        tag = s.get("tag", "").strip()
        if tag:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if not tag_counts:
        return None

    total = sum(tag_counts.values())
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

    parts = []
    for tag, count in sorted_tags:
        icon = TAG_ICONS.get(tag, "\U0001f4a1")
        pct = int(count / total * 100)
        parts.append(f"{icon}{tag} {count}건({pct}%)")

    return "\U0001f3f7 작업 유형: " + " · ".join(parts)


def build_repos_section(summary: dict, sessions: list[dict]) -> str:
    """Build repos section sorted by session count descending."""
    repo_counts = summary["repos"]  # {repo: count}
    repo_data = _collect_repo_data(sessions)

    sorted_repos = sorted(repo_counts.items(), key=lambda x: x[1], reverse=True)

    lines = ["\U0001f4c2 레포별 작업:"]
    for repo, count in sorted_repos:
        rd = repo_data.get(repo, {"topics": [], "duration": 0, "tokens": 0})
        dur_str = format_duration(rd["duration"]) if rd["duration"] > 0 else ""
        tok_str = _format_tokens(rd["tokens"]) if rd["tokens"] > 0 else ""
        parts = [f"{count}세션"]
        if dur_str:
            parts.append(dur_str)
        if tok_str:
            parts.append(tok_str)
        header = f"  ▸ {repo} ({', '.join(parts)})"
        lines.append(header)
        # 세션 수에 비례해 더 많이 표시 (최소 2, 최대 5)
        max_items = min(5, max(2, (count + 1) // 2))
        for t in rd["topics"][:max_items]:
            snippet = t[:120]
            if len(t) > 120:
                snippet += "..."
            lines.append(f"    - {snippet}")

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

    # Token usage feedback
    tokens = summary.get("tokens", {})
    total_tokens = tokens.get("total", 0)
    if total_tokens > 0:
        output_tokens = tokens.get("output", 0)
        api_calls = tokens.get("api_calls", 0)
        lines.append(f"\u2022 API {api_calls}회 · 출력 {_format_tokens(output_tokens)} tokens")
        cache_read = tokens.get("cache_read", 0)
        if cache_read > 0 and total_tokens > 0:
            cache_pct = int(cache_read / total_tokens * 100)
            lines.append(f"\u2022 캐시 활용률 {cache_pct}%")

    if not lines:
        return ""

    return "\U0001f4a1 패턴 피드백:\n" + "\n".join(f"  {l}" for l in lines)


def build_message(data: dict, use_llm: bool = False) -> str:
    """Build the full digest message from parsed JSON data."""
    date_str = data["date"]
    sessions = data.get("sessions", [])
    summary = data.get("summary")
    # Empty day
    if not sessions or summary is None:
        return build_empty_message(date_str)

    sections: list[str] = []

    # Header
    sections.append(build_header(date_str))

    # Time summary
    sections.append(build_time_summary(summary))

    # Tag breakdown
    tag_section = build_tag_section(sessions)
    if tag_section:
        sections.append(tag_section)

    # Repos
    repos_section = build_repos_section(summary, sessions)
    sections.append(repos_section)

    # Pattern feedback
    feedback = build_pattern_feedback(summary)
    if feedback:
        sections.append(feedback)

    # LLM 정리 + 리뷰 (--no-llm이 아닐 때만)
    if use_llm:
        review = generate_review(repos_section)
        if review:
            sections.append(review)

    message = "\n\n".join(sections)

    # Truncate if over Telegram limit
    if len(message) > TELEGRAM_MAX_CHARS:
        truncation_note = "\n\n... (truncated)"
        max_len = TELEGRAM_MAX_CHARS - len(truncation_note)
        message = message[:max_len] + truncation_note

    return message


REVIEW_TIMEOUT_SEC = 45


def generate_review(repos_section: str) -> str | None:
    """LLM으로 오늘의 정리 + 작업 내용 리뷰 생성."""
    prompt = (
        "다음은 오늘 하루 개발 작업 요약이다.\n\n"
        f"{repos_section}\n\n"
        "2개 섹션을 생성해라. 각 섹션은 2-3줄.\n\n"
        "📝 오늘의 정리\n"
        "- 오늘 전체 작업을 한 문단으로 정리. 핵심 성과 중심.\n\n"
        "🔍 리뷰\n"
        "- 오늘 작업 내용을 바탕으로, 후속으로 하면 좋을 작업을 구체적으로 제안.\n"
        "- 미완성이거나 연결되는 작업, 놓쳤을 수 있는 것 중심.\n"
        "- 일반론 말고 오늘 작업에 직접 연결되는 것만.\n\n"
        "형식:\n"
        "📝 오늘의 정리\n(내용)\n\n🔍 리뷰\n(내용)\n\n"
        "한국어로. 간결하게. 총 300자 이내."
    )

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=REVIEW_TIMEOUT_SEC,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        print(f"[daily_digest] review: claude returned code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(f"[daily_digest] review stderr: {result.stderr[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[daily_digest] review generation failed: {e}", file=sys.stderr)
    return None


# ── Work context (feedback loop) ─────────────────────

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _find_project_memory(repo_name: str) -> Path | None:
    """레포 이름에 매칭되는 프로젝트 memory 디렉토리 탐색."""
    if not PROJECTS_DIR.exists():
        return None
    for entry in PROJECTS_DIR.iterdir():
        if entry.is_dir() and entry.name.endswith(repo_name):
            return entry / "memory"
    return None


def write_work_context(data: dict):
    """레포별 work-context.md를 각 프로젝트의 auto memory에 기록."""
    sessions = data.get("sessions", [])
    if not sessions:
        return

    date_str = data["date"]

    # 레포별로 세션 그룹핑
    repo_sessions: dict[str, list[dict]] = {}
    for s in sessions:
        repo = s.get("repo", "unknown")
        repo_sessions.setdefault(repo, []).append(s)

    for repo, sessions_for_repo in repo_sessions.items():
        memory_dir = _find_project_memory(repo)
        if not memory_dir:
            continue

        lines = [
            "# 최근 작업 컨텍스트",
            f"<!-- auto-generated by daily_digest.py | {date_str} -->",
            "",
        ]

        for s in sessions_for_repo:
            sm = s.get("summary", "").strip()
            tag = s.get("tag", "").strip()
            time = s.get("time", "")
            if sm:
                prefix = f"[{tag}] " if tag else ""
                lines.append(f"- {time} {prefix}{sm}")
            elif s.get("topic", "").strip():
                lines.append(f"- {time} {s['topic'][:80]}")
        lines.append("")

        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
            ctx_path = memory_dir / "work-context.md"
            ctx_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            print(f"[daily_digest] {repo} work-context 쓰기 실패: {e}",
                  file=sys.stderr)



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
    else:
        # 구조화된 템플릿 + LLM 리뷰 (--no-llm이면 리뷰 스킵)
        message = build_message(data, use_llm=not args.no_llm)

    if args.dry_run:
        print(message)
    else:
        ok = send_telegram(message, chat_id_key="CHAT_ID_DAILY")
        if ok:
            print("[daily_digest] Telegram 전송 완료", file=sys.stderr)
        else:
            print("[daily_digest] Telegram 전송 실패", file=sys.stderr)
            sys.exit(1)

    # 작업 컨텍스트 갱신 (피드백 루프)
    write_work_context(data)


if __name__ == "__main__":
    main()
