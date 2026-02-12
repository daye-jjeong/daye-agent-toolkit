#!/usr/bin/env python3
"""Cross-repo Vault Recorder — 유저 레벨 Claude Code hook.

모든 Claude Code 세션에서 발동하여:
1. 세션 마커 → {vault}/YYYY-MM-DD.md (작업 레포 정보 포함)
2. t-*.md 수정 감지 → 해당 태스크의 ## 진행 로그 자동 append

Hook events:
- PreCompact → 세션 마커만 (mid-session 백업)
- SessionEnd → 세션 마커 + 태스크 진행 로그 (최종 기록)

설정: ~/.claude/cc-config.json 의 vault_root 경로 사용
stdin: { session_id, transcript_path, cwd, hook_event_name, ... }
"""

import sys
import json
import re
import fcntl
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
CONFIG_FILE = Path.home() / ".claude" / "cc-config.json"
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


def _load_vault_root() -> Path:
    """cc-config.json에서 vault 경로 읽기. 없으면 기본값."""
    try:
        config = json.loads(CONFIG_FILE.read_text())
        return Path(config["vault_root"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return Path.home() / "openclaw" / "vault"


VAULT_ROOT = _load_vault_root()
STATE_FILE = VAULT_ROOT / "state" / "vault_recorder_state.json"


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

def parse_transcript(transcript_path: str) -> dict:
    """Parse .jsonl transcript — 수정 파일, 명령, 에러, 토픽 추출."""
    files_modified = set()
    commands_run = []
    errors = []
    first_user_msg = ""
    session_start = None
    session_end = None

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if ts:
                    if session_start is None:
                        session_start = ts
                    session_end = ts

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

    duration_min = None
    if session_start and session_end:
        try:
            start = datetime.fromisoformat(session_start)
            end = datetime.fromisoformat(session_end)
            duration_min = int((end - start).total_seconds() / 60)
        except (ValueError, TypeError):
            pass

    return {
        "files": sorted(files_modified),
        "commands": commands_run[:10],
        "errors": errors[:5],
        "topic": first_user_msg,
        "duration_min": duration_min,
    }


# ── 세션 마커 ─────────────────────────────────────

def build_frontmatter(now):
    date_str = now.strftime("%Y-%m-%d")
    weekday = WEEKDAYS_KO[now.weekday()]
    return (
        f"---\ndate: {date_str}\ntype: session\nauthor: mingming\n"
        f"updated_by: claude-code\nupdated_at: {now.isoformat()}\n"
        f"tags: [session]\n---\n\n# {date_str} ({weekday})\n\n"
    )


def build_session_section(session_id, data, now, repo):
    time_str = now.strftime("%H:%M")
    sid_short = session_id[:8] if session_id else "unknown"

    lines = []
    lines.append(f"## 세션 {time_str} (claude-code, {sid_short}, {repo})")

    file_count = len(data["files"])
    duration = f"{data['duration_min']}분" if data["duration_min"] else "?분"
    lines.append(f"> 수정 파일 {file_count}개 | {duration}")
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

    return "\n".join(lines) + "\n"


def write_session_marker(session_id, data, now, repo):
    """세션 마커를 daily log에 append."""
    VAULT_ROOT.mkdir(parents=True, exist_ok=True)
    daily_file = VAULT_ROOT / f"{now.strftime('%Y-%m-%d')}.md"
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


# ── 태스크 진행 로그 자동 append ──────────────────

def find_modified_tasks(files: list) -> list:
    """수정된 파일 중 t-*.md 패턴인 것만 필터."""
    tasks = []
    for fp in files:
        p = Path(fp)
        if p.name.startswith("t-") and p.name.endswith(".md") and p.exists():
            tasks.append(p)
    return tasks


def append_task_progress(task_path: Path, repo: str, all_files: list):
    """t-*.md의 ## 진행 로그 섹션에 한 줄 append + frontmatter 갱신."""
    try:
        text = task_path.read_text(encoding="utf-8")
    except Exception:
        return

    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    now_iso = now.strftime("%Y-%m-%dT%H:%M")

    # 오늘 이미 같은 repo에서 기록했으면 스킵
    if f"- {today} (claude-code):" in text and repo in text.split(f"- {today} (claude-code):")[-1].split("\n")[0]:
        return

    # 관련 파일 수 (해당 태스크 자체 제외)
    other_files = [f for f in all_files if f != str(task_path)]
    file_count = len(other_files)

    log_line = f"- {today} (claude-code): {repo}에서 작업, 파일 {file_count}개 수정"

    if "## 진행 로그" in text:
        parts = text.split("## 진행 로그", 1)
        rest = parts[1]
        next_section = rest.find("\n## ")
        if next_section == -1:
            text = text.rstrip() + "\n" + log_line + "\n"
        else:
            insert_at = len(parts[0]) + len("## 진행 로그") + next_section
            text = text[:insert_at] + "\n" + log_line + text[insert_at:]
    else:
        text = text.rstrip() + "\n\n## 진행 로그\n" + log_line + "\n"

    # frontmatter updated_at / updated_by 갱신
    text = re.sub(r"updated_at:.*", f"updated_at: {now_iso}", text, count=1)
    text = re.sub(r"updated_by:.*", "updated_by: claude-code", text, count=1)

    task_path.write_text(text, encoding="utf-8")


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

    # 1. 세션 마커 — 모든 이벤트에서
    write_session_marker(session_id, data, now, repo)

    # 2. 태스크 진행 로그 — SessionEnd에서만
    if event == "SessionEnd":
        modified_tasks = find_modified_tasks(data["files"])
        for task_path in modified_tasks:
            append_task_progress(task_path, repo, data["files"])


if __name__ == "__main__":
    main()
