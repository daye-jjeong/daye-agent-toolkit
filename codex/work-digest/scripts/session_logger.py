#!/usr/bin/env python3
"""Codex session logger for work-digest."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _common import BASE_DIR, WEEKDAYS_KO, WORK_TAGS, WORK_TAGS_SET, format_tokens, send_telegram


KST = timezone(timedelta(hours=9))
IDLE_THRESHOLD_SEC = 300
SUMMARY_TIMEOUT_SEC = 60
BEHAVIOR_TIMEOUT_SEC = 60
CONVERSATION_MAX_CHARS = 8000
CODEX_BIN_CANDIDATES = ("/opt/homebrew/bin/codex", "/usr/local/bin/codex")
WORK_LOG_DIR = BASE_DIR / "work-log"
STATE_FILE = BASE_DIR / "state" / "session_logger_state.json"


def load_state() -> dict[str, list[str]]:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"recorded": []}


def save_state(state: dict[str, list[str]]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def already_recorded(session_id: str, event: str) -> bool:
    state = load_state()
    key = f"{session_id}:{event}"
    recorded = state.setdefault("recorded", [])
    if key in recorded:
        return True
    recorded.append(key)
    state["recorded"] = recorded[-100:]
    save_state(state)
    return False


def detect_repo(cwd: str) -> str:
    if not cwd:
        return "unknown"
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).name
    except Exception:
        pass
    return Path(cwd).name


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _iter_entries(transcript_path: str):
    try:
        with open(transcript_path, "r") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield json.loads(stripped)
                except json.JSONDecodeError:
                    continue
    except (FileNotFoundError, PermissionError):
        return


def _get_payload(entry: dict) -> dict:
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else {}


def _extract_content_text(content) -> str:
    texts: list[str] = []
    if isinstance(content, str):
        if content.strip():
            texts.append(content.strip())
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") in {"input_text", "output_text", "text"}:
                text = str(block.get("text", "")).strip()
                if text:
                    texts.append(text)
    return "\n".join(texts).strip()


def _normalize_user_text(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""
    if normalized.startswith("<environment_context>") and normalized.endswith("</environment_context>"):
        return ""
    return normalized


def _truncate_text(text: str, max_chars: int = CONVERSATION_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n...(중략)...\n" + text[-half:]


def _parse_arguments(raw: str | dict | None) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_command(args: dict) -> str:
    cmd = args.get("cmd")
    if isinstance(cmd, str) and cmd.strip():
        return cmd.strip()

    command = args.get("command")
    if isinstance(command, list) and command:
        if len(command) >= 3 and command[0] in {"bash", "zsh", "/bin/bash", "/bin/zsh"} and command[1] == "-lc":
            return str(command[2]).strip()
        return " ".join(str(part) for part in command if part).strip()
    return ""


def _append_unique(parts: list[str], line: str) -> None:
    if not line:
        return
    if parts and parts[-1] == line:
        return
    parts.append(line)


def _to_kst(timestamp: datetime | None) -> datetime | None:
    if timestamp is None:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(KST)


def _format_time(timestamp: datetime | None) -> str | None:
    local_timestamp = _to_kst(timestamp)
    return local_timestamp.strftime("%H:%M") if local_timestamp else None


def _extract_failure_text(raw_output: str) -> str | None:
    output = raw_output.strip()
    if not output:
        return None

    try:
        parsed_output = json.loads(output)
    except json.JSONDecodeError:
        parsed_output = None

    if isinstance(parsed_output, dict):
        metadata = parsed_output.get("metadata", {})
        exit_code = metadata.get("exit_code") if isinstance(metadata, dict) else None
        text_output = str(parsed_output.get("output", "")).strip()
        if exit_code not in (None, 0):
            if text_output:
                return text_output[:200]
            return f"Process exited with code {exit_code}"
        return None

    process_match = re.search(r"Process exited with code (\d+)", output)
    if process_match:
        exit_code = int(process_match.group(1))
        if exit_code != 0:
            if "Output:\n" in output:
                body = output.split("Output:\n", 1)[1].strip()
                if body:
                    return body[:200]
            return f"Process exited with code {exit_code}"

    if "failed in sandbox" in output.lower() or "execution error" in output.lower():
        exit_match = re.search(r"exit_code:\s*(\d+)", output)
        exit_code = int(exit_match.group(1)) if exit_match else 1
        for label in ("aggregated_output", "stderr", "stdout"):
            stream_match = re.search(
                rf"{label}: StreamOutput \{{ text: \"(.*?)\", truncated_after_lines:",
                output,
                re.DOTALL,
            )
            if not stream_match:
                continue
            text = stream_match.group(1).replace("\\n", "\n").replace('\\"', '"').strip()
            if text:
                return text[:200]
        return f"Process exited with code {exit_code}"

    if "error" in output.lower():
        return output[:200]

    return None


def resolve_codex_bin() -> str | None:
    wrapper_path = (BASE_DIR / "scripts" / "codex-wrapper.sh").resolve()
    candidates: list[str] = []

    env_candidate = os.environ.get("CODEX_REAL_BIN", "").strip()
    if env_candidate:
        candidates.append(env_candidate)

    discovered = shutil.which("codex")
    if discovered:
        candidates.append(discovered)

    candidates.extend(CODEX_BIN_CANDIDATES)

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.exists() or not os.access(path, os.X_OK):
            continue
        try:
            if path.resolve() == wrapper_path:
                continue
        except OSError:
            pass
        return str(path)

    return None


def extract_conversation(transcript_path: str) -> str:
    parts: list[str] = []
    for entry in _iter_entries(transcript_path):
        entry_type = entry.get("type")
        payload = _get_payload(entry)

        if entry_type == "event_msg" and payload.get("type") == "user_message":
            message = _normalize_user_text(str(payload.get("message", "")))
            if message:
                _append_unique(parts, f"User: {message}")
            continue

        if entry_type == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
            text = _normalize_user_text(_extract_content_text(payload.get("content")))
            if text:
                _append_unique(parts, f"User: {text}")
            continue

        if entry_type == "response_item" and payload.get("type") == "message" and payload.get("role") == "assistant":
            text = _extract_content_text(payload.get("content"))
            if text:
                _append_unique(parts, f"Assistant: {text}")

    return _truncate_text("\n".join(parts))


def extract_compaction_text(transcript_path: str) -> str:
    parts: list[str] = []
    for entry in _iter_entries(transcript_path):
        if entry.get("type") != "compacted":
            continue

        replacement_history = _get_payload(entry).get("replacement_history", [])
        for item in replacement_history:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            role = item.get("role")
            text = _extract_content_text(item.get("content"))
            if not text:
                continue
            prefix = "User" if role == "user" else "Assistant"
            parts.append(f"{prefix}: {text}")

    return _truncate_text("\n".join(parts), max_chars=3000)


def extract_user_messages(transcript_path: str) -> str:
    """transcript에서 user 메시지만 추출 (행동 추출용)."""
    parts: list[str] = []
    for entry in _iter_entries(transcript_path):
        entry_type = entry.get("type")
        payload = _get_payload(entry)

        if entry_type == "event_msg" and payload.get("type") == "user_message":
            message = _normalize_user_text(str(payload.get("message", "")))
            if message:
                parts.append(message)

        if entry_type == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
            text = _normalize_user_text(_extract_content_text(payload.get("content")))
            if text:
                parts.append(text)

    return _truncate_text("\n".join(parts), max_chars=3000)


def _parse_signals_response(raw: str) -> dict | None:
    """Parse JSON behavioral signals from LLM response."""
    cleaned = raw.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned)
        if match:
            cleaned = match.group(1)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None
    result = {}
    for key in ("decisions", "mistakes", "patterns"):
        items = data.get(key, [])
        if isinstance(items, list):
            result[key] = [str(item)[:60] for item in items if item]
        else:
            result[key] = []
    if not any(result.values()):
        return None
    return result


def extract_behavioral_signals(user_messages: str, repo: str, cwd: str) -> dict | None:
    """codex exec로 사용자 행동 신호 추출. 실패 시 None."""
    if not user_messages.strip():
        return None
    codex_bin = resolve_codex_bin()
    if not codex_bin:
        return None

    prompt = (
        f"레포: {repo}\n\n"
        "다음은 Codex CLI 세션에서 사용자가 보낸 메시지들이다.\n\n"
        f"{user_messages}\n\n"
        "이 사용자의 행동 신호를 추출해라. 각 항목은 1줄, 30자 이내.\n"
        "- decisions: 사용자가 명시적 선택을 한 것 (A 대신 B 선택 등)\n"
        "- mistakes: 되돌린 것, 교정한 것, 시행착오\n"
        "- patterns: 관찰되는 작업 습관 (좋든 나쁘든)\n"
        "없으면 빈 배열.\n\n"
        'JSON으로만 출력. 다른 텍스트 없이:\n'
        '{"decisions": [...], "mistakes": [...], "patterns": [...]}'
    )

    try:
        result = subprocess.run(
            [codex_bin, "exec", "--ephemeral", "-C", cwd],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=BEHAVIOR_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        print(f"[session_logger] extract_behavioral_signals timed out ({BEHAVIOR_TIMEOUT_SEC}s)", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"[session_logger] extract_behavioral_signals failed: {exc}", file=sys.stderr)
        return None

    if result.returncode != 0:
        print(f"[session_logger] codex exec returned {result.returncode}: {result.stderr[:200]}", file=sys.stderr)
        return None
    if not result.stdout.strip():
        return None
    return _parse_signals_response(result.stdout.strip())


def _parse_summary_response(raw: str) -> dict[str, str]:
    lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
    tag = "기타"
    text_lines: list[str] = []

    for index, line in enumerate(lines):
        if index == 0 and line.startswith("[") and "]" in line:
            candidate = line[1 : line.index("]")].strip()
            if candidate in WORK_TAGS_SET:
                tag = candidate
                rest = line[line.index("]") + 1 :].strip()
                if rest:
                    text_lines.append(rest)
                continue
        text_lines.append(line)

    text = "\n".join(text_lines).strip()
    if not text:
        text = raw.strip()
    return {"tag": tag, "text": text}


def summarize_session(conversation: str, repo: str, cwd: str) -> dict[str, str] | None:
    if not conversation.strip():
        return None
    codex_bin = resolve_codex_bin()
    if not codex_bin:
        print("[session_logger] Codex binary not found", file=sys.stderr)
        return None

    tags_str = ", ".join(WORK_TAGS)
    prompt = (
        f"레포: {repo}\n\n"
        "다음은 Codex CLI 세션의 대화 내용이다.\n\n"
        f"{conversation}\n\n"
        "1줄째: 작업 유형 태그 하나를 골라라. "
        f"선택지: {tags_str}\n"
        "태그 선택 기준 (가장 비중이 큰 작업 기준으로 1개만):\n"
        "- 코딩: 새 기능 구현, 파일 생성, 스크립트 작성\n"
        "- 디버깅: 버그 수정, 에러 해결, 원인 분석\n"
        "- 리서치: 조사, 탐색, 문서 읽기, 비교 분석\n"
        "- 리뷰: 코드 리뷰, PR 리뷰, 감사(audit)\n"
        "- ops: 배포, 인프라, 서버 운영, 크론 관리\n"
        "- 설정: 환경 설정, 설치, 구성 변경\n"
        "- 문서: README, 문서 작성, SKILL.md 작성\n"
        "- 설계: 브레인스토밍, plan 작성, 아키텍처 설계\n"
        "- 리팩토링: 기존 코드 구조 변경, 정리, 통합\n"
        "- 기타: 위 9개 중 어느 것도 맞지 않을 때만\n\n"
        "2줄째부터: 이 세션에서 한 작업을 한국어 2-3줄로 요약해라. "
        "결과물/변경사항 중심으로 쓰라 (예: 'sync_codex.py 신규 작성, JSONL 파싱 + work-log 오버레이로 세션 데이터 SQLite 동기화'). "
        "프로세스 설명(브레인스토밍, 리뷰, 머지 등)은 생략하라. "
        "사용자가 입력한 원문이 아니라, 실제 수행된 작업의 결과를 쓰라. "
        "파일 경로나 명령어는 생략하고 작업의 의미만 쓰라.\n\n"
        "형식:\n[태그]\n요약 내용"
    )

    try:
        result = subprocess.run(
            [codex_bin, "exec", "--ephemeral", "-C", cwd],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=SUMMARY_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        print(f"[session_logger] summarize_session timed out ({SUMMARY_TIMEOUT_SEC}s)", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"[session_logger] summarize_session failed: {exc}", file=sys.stderr)
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None
    return _parse_summary_response(result.stdout.strip())


def parse_transcript(transcript_path: str) -> dict:
    commands: list[str] = []
    errors: list[str] = []
    timestamps: list[datetime] = []
    topic = ""
    cwd = ""
    last_agent_message = ""
    task_complete_message = ""
    compaction_detected = False
    approval_count = 0
    tokens = {"input": 0, "cached_input": 0, "output": 0, "reasoning_output": 0, "total": 0}

    for entry in _iter_entries(transcript_path):
        payload = _get_payload(entry)
        timestamp = _parse_timestamp(entry.get("timestamp"))
        if timestamp is not None:
            timestamps.append(timestamp)

        entry_type = entry.get("type")
        payload_type = payload.get("type")

        if entry_type == "session_meta" and not cwd:
            cwd = str(payload.get("cwd", "")).strip()

        if entry_type == "turn_context" and not cwd:
            cwd = str(payload.get("cwd", "")).strip()

        if entry_type == "event_msg" and payload_type == "user_message" and not topic:
            candidate = _normalize_user_text(str(payload.get("message", "")))
            if candidate:
                topic = candidate[:120]
                continue

        if entry_type == "response_item" and payload_type == "message" and payload.get("role") == "user" and not topic:
            candidate = _normalize_user_text(_extract_content_text(payload.get("content")))
            if candidate:
                topic = candidate[:120]
                continue

        if entry_type == "event_msg" and payload_type == "agent_message":
            last_agent_message = str(payload.get("message", "")).strip()
            continue

        if entry_type == "response_item" and payload_type == "message" and payload.get("role") == "assistant":
            text = _extract_content_text(payload.get("content"))
            if text:
                last_agent_message = text
            continue

        if entry_type == "event_msg" and payload_type == "task_complete":
            task_complete_message = str(payload.get("last_agent_message", "")).strip()
            continue

        if entry_type == "event_msg" and payload_type == "token_count":
            info = payload.get("info")
            if isinstance(info, dict):
                total_usage = info.get("total_token_usage", {})
                if isinstance(total_usage, dict):
                    tokens = {
                        "input": int(total_usage.get("input_tokens", 0) or 0),
                        "cached_input": int(total_usage.get("cached_input_tokens", 0) or 0),
                        "output": int(total_usage.get("output_tokens", 0) or 0),
                        "reasoning_output": int(total_usage.get("reasoning_output_tokens", 0) or 0),
                        "total": int(total_usage.get("total_tokens", 0) or 0),
                    }
            continue

        if entry_type == "compacted":
            compaction_detected = True
            continue

        if entry_type == "event_msg" and payload_type == "context_compacted":
            compaction_detected = True
            continue

        if entry_type == "response_item" and payload_type == "function_call":
            args = _parse_arguments(payload.get("arguments"))
            command = _extract_command(args)
            if command:
                commands.append(command)
            if args.get("sandbox_permissions") == "require_escalated" or args.get("with_escalated_permissions") is True:
                approval_count += 1
            continue

        if entry_type == "response_item" and payload_type == "function_call_output":
            failure = _extract_failure_text(str(payload.get("output", "")))
            if failure:
                errors.append(failure)

    duration_min = None
    if len(timestamps) >= 2:
        active_seconds = 0
        for previous, current in zip(timestamps, timestamps[1:]):
            gap = (current - previous).total_seconds()
            if 0 < gap <= IDLE_THRESHOLD_SEC:
                active_seconds += gap
        if active_seconds > 0:
            duration_min = max(1, int(active_seconds / 60))

    start_at = _to_kst(timestamps[0]) if timestamps else None
    end_at = _to_kst(timestamps[-1]) if timestamps else None

    return {
        "cwd": cwd,
        "topic": topic,
        "commands": commands,
        "command_count": len(commands),
        "tokens": tokens,
        "approval_count": approval_count,
        "compaction_detected": compaction_detected,
        "last_agent_message": last_agent_message,
        "task_complete_message": task_complete_message,
        "files": [],
        "errors": errors[:5],
        "duration_min": duration_min,
        "start_at": start_at,
        "end_at": end_at,
        "start_time": _format_time(start_at),
        "end_time": _format_time(end_at),
    }


def _format_tokens(n: int) -> str:
    return format_tokens(n, suffix=" tokens")


def build_frontmatter(now: datetime) -> str:
    date_str = now.strftime("%Y-%m-%d")
    weekday = WEEKDAYS_KO[now.weekday()]
    return (
        f"---\n"
        f"date: {date_str}\n"
        "type: work-log\n"
        "source: codex\n"
        "tags: [work-log, codex]\n"
        "---\n\n"
        f"# {date_str} ({weekday})\n\n"
    )


def build_session_section(session_id: str, data: dict, now: datetime, repo: str, event: str) -> str:
    time_str = data.get("start_time") or now.strftime("%H:%M")
    end_time = data.get("end_time")
    if end_time and end_time != time_str:
        time_label = f"{time_str}~{end_time}"
    else:
        time_label = time_str

    sid_short = session_id[:8] if session_id else "unknown"
    tokens = data.get("tokens", {})
    total_tokens = int(tokens.get("total") or 0)
    if total_tokens <= 0:
        total_tokens = sum(int(tokens.get(key, 0) or 0) for key in ("input", "cached_input", "output", "reasoning_output"))

    duration = f"{data['duration_min']}분" if data.get("duration_min") else "?분"
    lines = [
        f"## 세션 {time_label} ({sid_short}, {repo})",
        f"> source: codex | event: {event}",
        f"> 파일 {len(data.get('files', []))}개 | {duration} | {_format_tokens(total_tokens)}",
        "",
    ]

    summary = data.get("summary")
    if isinstance(summary, dict):
        tag = summary.get("tag", "")
        text = summary.get("text", "").strip()
        tag_prefix = f"[{tag}] " if tag else ""
        if text:
            lines.extend([f"**요약**: {tag_prefix}{text}", ""])
    elif data.get("task_complete_message"):
        lines.extend([f"**결과**: {data['task_complete_message']}", ""])
    elif data.get("topic"):
        lines.extend([f"**주제**: {data['topic']}", ""])

    signals = data.get("behavioral_signals")
    if signals:
        if signals.get("decisions"):
            lines.extend([f"**결정**: {' ; '.join(signals['decisions'])}", ""])
        if signals.get("mistakes"):
            lines.extend([f"**시행착오**: {' ; '.join(signals['mistakes'])}", ""])
        if signals.get("patterns"):
            lines.extend([f"**패턴**: {' ; '.join(signals['patterns'])}", ""])

    if data.get("commands"):
        lines.append("### 실행 명령")
        for command in data["commands"][:5]:
            lines.append(f"- `{command}`")
        lines.append("")

    if data.get("errors"):
        lines.append("### 에러/이슈")
        for error in data["errors"]:
            lines.append(f"- {error}")
        lines.append("")

    if any(tokens.values()):
        lines.append("### 토큰")
        lines.append(f"- Input: {_format_tokens(int(tokens.get('input', 0) or 0))}")
        lines.append(f"- Cached input: {_format_tokens(int(tokens.get('cached_input', 0) or 0))}")
        lines.append(f"- Output: {_format_tokens(int(tokens.get('output', 0) or 0))}")
        lines.append(f"- Reasoning output: {_format_tokens(int(tokens.get('reasoning_output', 0) or 0))}")
        lines.append(f"- Total: {_format_tokens(total_tokens)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_session_marker(session_id: str, data: dict, now: datetime, repo: str, event: str) -> None:
    marker_time = data.get("end_at")
    log_time = marker_time if isinstance(marker_time, datetime) else now
    WORK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    daily_file = WORK_LOG_DIR / f"{log_time.strftime('%Y-%m-%d')}.md"
    section = build_session_section(session_id, data, log_time, repo, event)

    with open(daily_file, "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(build_frontmatter(log_time))
            handle.write(section)
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def send_session_telegram(data: dict, repo: str, duration_min: int | None) -> None:
    summary = data.get("summary")
    if isinstance(summary, dict):
        tag = summary.get("tag", "")
        text = summary.get("text", "")
        tag_prefix = f"[{tag}] " if tag else ""
        message = f"[Codex] {repo} — {tag_prefix}{text}"
    else:
        topic = data.get("topic") or data.get("task_complete_message") or "작업 완료"
        message = f"[Codex] {repo} — {topic[:100]}"

    if duration_min:
        message = f"{message} ({duration_min}분)"

    if len(message) > 4096:
        message = message[:4090] + "..."
    send_telegram(message, chat_id_key="CHAT_ID_SESSION", silent=True)


def _build_compaction_summary(data: dict, transcript_path: str, repo: str, cwd: str) -> dict[str, str] | None:
    text = extract_compaction_text(transcript_path).strip()
    if not text:
        return None
    # LLM 요약 시도 (compaction 텍스트도 결과 중심으로)
    summary = summarize_session(text, repo, cwd)
    if summary:
        return summary
    # LLM 실패 시: User: 접두사 제거 + 첫 문장 추출
    first_line = text.splitlines()[0].strip()
    if first_line.startswith("User: "):
        first_line = first_line[6:]
    if first_line.startswith("Assistant: "):
        first_line = first_line[11:]
    return {"tag": "기타", "text": first_line[:300]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--transcript-path", required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--cwd", default="")
    args = parser.parse_args()

    transcript = Path(args.transcript_path)
    if not transcript.exists():
        sys.exit(0)

    data = parse_transcript(str(transcript))
    effective_cwd = args.cwd or data.get("cwd", "")
    repo = detect_repo(effective_cwd)

    if not any(
        [
            data.get("topic"),
            data.get("commands"),
            data.get("compaction_detected"),
            data.get("last_agent_message"),
            data.get("task_complete_message"),
        ]
    ):
        sys.exit(0)

    session_id = args.session_id or transcript.stem
    if already_recorded(session_id, args.event):
        sys.exit(0)

    now = datetime.now(KST)
    if args.event == "session_end":
        from concurrent.futures import ThreadPoolExecutor

        conversation = extract_conversation(str(transcript))
        user_msgs = extract_user_messages(str(transcript))
        work_cwd = effective_cwd or str(transcript.parent)

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                summary_future = pool.submit(summarize_session, conversation, repo, work_cwd)
                signals_future = pool.submit(extract_behavioral_signals, user_msgs, repo, work_cwd)

                try:
                    summary = summary_future.result(timeout=SUMMARY_TIMEOUT_SEC + 10)
                    if summary:
                        data["summary"] = summary
                except Exception as e:
                    print(f"[session_logger] summary future failed: {e}", file=sys.stderr)

                try:
                    signals = signals_future.result(timeout=BEHAVIOR_TIMEOUT_SEC + 10)
                    if signals:
                        data["behavioral_signals"] = signals
                except Exception as e:
                    print(f"[session_logger] signals future failed: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[session_logger] ThreadPool failed: {e}", file=sys.stderr)
    elif args.event == "compaction":
        summary = _build_compaction_summary(data, str(transcript), repo, effective_cwd or str(transcript.parent))
        if summary:
            data["summary"] = summary

    write_session_marker(session_id, data, now, repo, args.event)

    if args.event == "session_end":
        send_session_telegram(data, repo, data.get("duration_min"))


if __name__ == "__main__":
    main()
