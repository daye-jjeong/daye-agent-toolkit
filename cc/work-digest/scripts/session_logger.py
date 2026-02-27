#!/usr/bin/env python3
"""Session Logger — Claude Code hook for work-digest.

모든 Claude Code 세션에서 발동하여 세션 마커를 기록:
  → {BASE_DIR}/work-log/YYYY-MM-DD.md

Hook events:
- PreCompact → 세션 마커 (mid-session 백업)
- SessionEnd → 세션 마커 (최종 기록)

stdin: { session_id, transcript_path, cwd, hook_event_name, ... }
"""

import sys
import json
import fcntl
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent.parent
WORK_LOG_DIR = BASE_DIR / "work-log"
STATE_FILE = WORK_LOG_DIR / "state" / "session_logger_state.json"
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


# ── stdin / state ─────────────────────────────────

def parse_stdin():
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return None


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"recorded": []}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def already_recorded(session_id: str, event: str) -> bool:
    """같은 세션+이벤트 조합의 중복 기록 방지."""
    state = load_state()
    key = f"{session_id}:{event}"
    if key in state.get("recorded", []):
        return True
    state.setdefault("recorded", []).append(key)
    state["recorded"] = state["recorded"][-50:]
    save_state(state)
    return False


# ── repo 식별 ─────────────────────────────────────

def detect_repo(cwd: str) -> str:
    """cwd에서 git repo 이름 추출. git 없으면 디렉토리명."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except Exception:
        pass
    return Path(cwd).name


# ── transcript 파싱 ───────────────────────────────

IDLE_THRESHOLD_SEC = 300  # 5분 이상 gap = idle로 간주


def parse_transcript(transcript_path: str) -> dict:
    """Parse .jsonl transcript — 수정 파일, 명령, 에러, 토픽, 토큰 추출."""
    files_modified = set()
    commands_run = []
    errors = []
    first_user_msg = ""
    timestamps: list[datetime] = []
    token_input = 0
    token_output = 0
    token_cache_read = 0
    token_cache_create = 0
    api_calls = 0

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if ts:
                    try:
                        timestamps.append(datetime.fromisoformat(ts))
                    except (ValueError, TypeError):
                        pass

                entry_type = entry.get("type", "")
                msg = entry.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else ""

                # First user message = session topic
                if not first_user_msg and entry_type == "user":
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                first_user_msg = block.get("text", "")[:120]
                                break
                    elif isinstance(content, str):
                        first_user_msg = content[:120]

                # Token usage (from assistant responses)
                if entry_type == "assistant" and isinstance(msg, dict):
                    usage = msg.get("usage", {})
                    if usage:
                        api_calls += 1
                        token_input += usage.get("input_tokens", 0)
                        token_output += usage.get("output_tokens", 0)
                        token_cache_read += usage.get("cache_read_input_tokens", 0)
                        token_cache_create += usage.get("cache_creation_input_tokens", 0)

                # Assistant tool calls
                if entry_type == "assistant" and isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        tool = block.get("name", "")
                        inp = block.get("input", {})

                        if tool in ("Edit", "Write"):
                            fp = inp.get("file_path", "")
                            if fp:
                                files_modified.add(fp)
                        if tool == "Bash":
                            cmd = inp.get("command", "")
                            if cmd:
                                commands_run.append(cmd[:80])

                # Tool results (errors)
                if entry_type == "tool_result":
                    data_field = entry.get("data", {})
                    text = ""
                    if isinstance(data_field, dict):
                        text = str(data_field.get("output", ""))[:120]
                    if text and ("error" in text.lower() or "Error" in text):
                        errors.append(text[:120])

    except (FileNotFoundError, PermissionError):
        pass

    # 활성 시간 계산: 연속 엔트리 간 gap이 임계값 이하인 것만 합산
    duration_min = None
    if len(timestamps) >= 2:
        active_sec = 0
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
            if 0 < gap <= IDLE_THRESHOLD_SEC:
                active_sec += gap
        duration_min = max(1, int(active_sec / 60))

    return {
        "files": sorted(files_modified),
        "commands": commands_run[:10],
        "errors": errors[:5],
        "topic": first_user_msg,
        "duration_min": duration_min,
        "tokens": {
            "input": token_input,
            "output": token_output,
            "cache_read": token_cache_read,
            "cache_create": token_cache_create,
            "api_calls": api_calls,
        },
    }


# ── 세션 마커 ─────────────────────────────────────

def _format_tokens(n: int) -> str:
    """Format token count: 1234 → 1.2K, 1234567 → 1.2M"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M tokens"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K tokens"
    return f"{n} tokens"


def build_frontmatter(now):
    date_str = now.strftime("%Y-%m-%d")
    weekday = WEEKDAYS_KO[now.weekday()]
    return (
        f"---\ndate: {date_str}\ntype: work-log\n"
        f"tags: [work-log]\n---\n\n# {date_str} ({weekday})\n\n"
    )


def build_session_section(session_id, data, now, repo):
    time_str = now.strftime("%H:%M")
    sid_short = session_id[:8] if session_id else "unknown"

    lines = []
    lines.append(f"## 세션 {time_str} ({sid_short}, {repo})")

    file_count = len(data["files"])
    duration = f"{data['duration_min']}분" if data["duration_min"] else "?분"
    tokens = data.get("tokens", {})
    total_tokens = sum(tokens.get(k, 0) for k in ("input", "output", "cache_read", "cache_create"))
    token_str = _format_tokens(total_tokens)
    lines.append(f"> 파일 {file_count}개 | {duration} | {token_str}")
    lines.append("")

    if data["topic"]:
        lines.append(f"**주제**: {data['topic']}")
        lines.append("")

    if data["files"]:
        lines.append("### 수정된 파일")
        home = str(Path.home())
        for fp in data["files"]:
            lines.append(f"- `{fp.replace(home, '~')}`")
        lines.append("")

    if data["commands"]:
        lines.append("### 실행 명령")
        for cmd in data["commands"][:5]:
            lines.append(f"- `{cmd}`")
        lines.append("")

    if data["errors"]:
        lines.append("### 에러/이슈")
        for err in data["errors"]:
            lines.append(f"- {err}")
        lines.append("")

    if tokens.get("api_calls", 0) > 0:
        lines.append("### 토큰")
        lines.append(f"- API 호출: {tokens['api_calls']}회")
        lines.append(f"- Input: {_format_tokens(tokens.get('input', 0))}")
        lines.append(f"- Output: {_format_tokens(tokens.get('output', 0))}")
        lines.append(f"- Cache read: {_format_tokens(tokens.get('cache_read', 0))}")
        lines.append(f"- Cache create: {_format_tokens(tokens.get('cache_create', 0))}")
        lines.append("")

    return "\n".join(lines) + "\n"


def write_session_marker(session_id, data, now, repo):
    """세션 마커를 daily log에 append."""
    WORK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    daily_file = WORK_LOG_DIR / f"{now.strftime('%Y-%m-%d')}.md"
    is_new = not daily_file.exists()
    section = build_session_section(session_id, data, now, repo)

    with open(daily_file, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            if is_new:
                f.write(build_frontmatter(now))
            f.write(section)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ── main ──────────────────────────────────────────

def main():
    hook_input = parse_stdin()
    if not hook_input:
        sys.exit(0)

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")
    cwd = hook_input.get("cwd", "")
    event = hook_input.get("hook_event_name", "")

    if not transcript_path or not Path(transcript_path).exists():
        sys.exit(0)

    now = datetime.now(KST)
    repo = detect_repo(cwd) if cwd else "unknown"
    data = parse_transcript(transcript_path)

    # 무의미한 세션은 스킵
    if not data["files"] and not data["commands"] and not data["topic"]:
        sys.exit(0)

    # 중복 방지
    if already_recorded(session_id, event):
        sys.exit(0)

    # 세션 마커 기록
    write_session_marker(session_id, data, now, repo)


if __name__ == "__main__":
    main()
