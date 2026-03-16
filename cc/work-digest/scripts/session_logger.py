#!/usr/bin/env python3
"""Session Logger — Claude Code hook for work-digest.

모든 Claude Code 세션에서 발동하여 활동을 SQLite에 직접 기록.

Hook events:
- PreCompact → SQLite 기록 (mid-session 백업)
- SessionEnd → SQLite 기록 + LLM 요약 + 텔레그램

stdin: { session_id, transcript_path, cwd, hook_event_name, ... }
"""

import sys
import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

from _common import WORK_TAGS, send_telegram

_MCP_DIR = Path(__file__).resolve().parent.parent.parent.parent / "shared" / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from activity_writer import record_sessions

KST = timezone(timedelta(hours=9))


# ── stdin ─────────────────────────────────────────

def parse_stdin():
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return None


# ── repo 식별 ─────────────────────────────────────

def detect_repo_and_branch(cwd: str) -> tuple[str, str | None]:
    """cwd에서 (repo 이름, branch) 추출. worktree면 원본 레포 이름 반환.

    branch가 main/master이면 None 반환 (태스크 식별 의미 없음).
    """
    repo = Path(cwd).name
    branch = None
    try:
        # --git-common-dir: worktree에서는 원본 레포의 .git 경로 반환
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            git_common = Path(result.stdout.strip())
            if not git_common.is_absolute():
                git_common = (Path(cwd) / git_common).resolve()
            repo = git_common.parent.name
    except Exception:
        pass

    try:
        br_result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if br_result.returncode == 0:
            br = br_result.stdout.strip()
            if br and br not in ("main", "master", "HEAD"):
                branch = br
    except Exception:
        pass
    return repo, branch


# ── 시스템 태그 제거 ──────────────────────────────

_SYSTEM_TAG_RE = re.compile(
    r"<(?:system-reminder|local-command-caveat|antml:\w+|available-deferred-tools"
    r"|fast_mode_info|EXTREMELY_\w*IMPORTANT)"
    r"[^>]*>[\s\S]*?</(?:system-reminder|local-command-caveat|antml:\w+"
    r"|available-deferred-tools|fast_mode_info|EXTREMELY_\w*IMPORTANT)>",
)


def strip_system_tags(text: str) -> str:
    """시스템 주입 태그 제거 (<system-reminder>, <local-command-caveat> 등)."""
    cleaned = _SYSTEM_TAG_RE.sub("", text)
    # 닫히지 않은 태그도 제거 (truncated content)
    cleaned = re.sub(
        r"<(?:system-reminder|local-command-caveat)[^>]*>.*",
        "", cleaned, flags=re.DOTALL,
    )
    return cleaned.strip()


# ── transcript 파싱 ───────────────────────────────

IDLE_THRESHOLD_SEC = 300  # 5분 이상 gap = idle로 간주
SUMMARY_TIMEOUT_SEC = 60
CONVERSATION_MAX_CHARS = 8000


def _extract_text_from_entry(entry: dict) -> str | None:
    """transcript 엔트리에서 텍스트 추출. 시스템 태그 제거."""
    msg = entry.get("message", {})
    content = msg.get("content", "") if isinstance(msg, dict) else ""
    texts = []
    if isinstance(content, str) and content.strip():
        cleaned = strip_system_tags(content.strip())
        if cleaned:
            texts.append(cleaned[:500])
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                cleaned = strip_system_tags(block.get("text", "").strip())
                if cleaned:
                    texts.append(cleaned[:500])
    return "\n".join(texts) if texts else None


def _truncate_text(text: str, max_chars: int = CONVERSATION_MAX_CHARS) -> str:
    if len(text) > max_chars:
        half = max_chars // 2
        text = text[:half] + "\n...(중략)...\n" + text[-half:]
    return text


def extract_conversation(transcript_path: str) -> str:
    """transcript에서 user/assistant 텍스트만 추출 (요약용)."""
    parts = []
    try:
        with open(transcript_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                entry_type = entry.get("type", "")
                if entry_type not in ("user", "assistant"):
                    continue
                text = _extract_text_from_entry(entry)
                if text:
                    role = "User" if entry_type == "user" else "Assistant"
                    parts.append(f"{role}: {text}")
    except (FileNotFoundError, PermissionError):
        pass
    return _truncate_text("\n".join(parts))


def extract_user_messages(transcript_path: str) -> str:
    """transcript에서 user 메시지만 추출 (행동 추출용)."""
    parts = []
    try:
        with open(transcript_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "user":
                    continue
                text = _extract_text_from_entry(entry)
                if text:
                    parts.append(text)
    except (FileNotFoundError, PermissionError):
        pass
    return _truncate_text("\n---\n".join(parts))


def summarize_session(conversation: str, repo: str) -> dict | None:
    """claude CLI로 세션 요약 + 태그 생성. 실패 시 None.

    Returns: {"tag": "코딩", "text": "요약 내용"} or None
    """
    if not conversation.strip():
        return None
    tags_str = ", ".join(WORK_TAGS)
    prompt = (
        f"레포: {repo}\n\n"
        f"다음은 Claude Code 세션의 대화 내용이다.\n\n"
        f"{conversation}\n\n"
        "1줄째: 작업 유형 태그 하나를 골라라. "
        f"선택지: {tags_str}\n"
        "태그 선택 기준 (가장 비중이 큰 작업 기준으로 1개만):\n"
        "- 코딩: 새 기능 구현, 파일 생성, 스크립트 작성\n"
        "- 디버깅: 버그 수정, 에러 해결, 원인 분석\n"
        "- 리서치: 조사, 탐색, 문서 읽기, 영상 정리, 비교 분석\n"
        "- 리뷰: 코드 리뷰, PR 리뷰, 감사(audit)\n"
        "- ops: 배포, 인프라, 서버 운영, 에이전트 레지스트리, 큐 관리\n"
        "- 설정: 환경 설정, 설치, 구성 변경, alias 추가\n"
        "- 문서: README, 문서 작성, SKILL.md 작성\n"
        "- 설계: 브레인스토밍, plan 작성, 아키텍처 설계, 스킬 설계\n"
        "- 리팩토링: 기존 코드 구조 변경, 정리, 통합, 마이그레이션\n"
        "- 기타: 위 9개 중 어느 것도 맞지 않을 때만. "
        "복합 작업이면 가장 비중이 큰 것을 골라라. 기타를 쓰지 마라.\n\n"
        "2줄째부터: 이 세션에서 한 작업을 한국어 2-3줄로 요약해라.\n"
        "반드시 포함: 무엇을(어떤 기능/모듈), 왜(어떤 문제/목적), 결과(어떤 산출물/변경).\n"
        "브랜치명이 대화에 나오면 포함.\n"
        "나쁜 예: '설계 논의', 'PR 리뷰', '디버깅' — 뭘 했는지 모름.\n"
        "좋은 예: 'session logger 파이프라인 개편 — 열린 세션 누락 문제 해결 위해 "
        "active_session_scanner + date-split 구현, work-log markdown 제거하고 SQLite 직접 기록으로 전환.'\n\n"
        "형식:\n[태그]\n요약 내용"
    )
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "sonnet", "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=SUMMARY_TIMEOUT_SEC,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _parse_summary_response(result.stdout.strip())
    except subprocess.TimeoutExpired:
        print(f"[session_logger] summarize_session timed out ({SUMMARY_TIMEOUT_SEC}s)", file=sys.stderr)
    except FileNotFoundError:
        print("[session_logger] 'claude' CLI not found on PATH", file=sys.stderr)
    except Exception as e:
        print(f"[session_logger] summarize_session failed: {type(e).__name__}: {e}", file=sys.stderr)
    return None


_TAG_KEYWORDS = {
    "디버깅": ["디버깅", "버그", "에러", "fix", "debug", "원인 파악", "원인 분석"],
    "코딩": ["구현", "생성", "추가", "작성", "신규", "feat", "implement"],
    "리서치": ["리서치", "조사", "탐색", "분석", "비교", "검토", "파악"],
    "설계": ["설계", "design", "plan", "브레인스토밍", "아키텍처"],
    "리팩토링": ["리팩토링", "refactor", "통합", "정리", "마이그레이션"],
    "ops": ["배포", "deploy", "인프라", "레지스트리", "큐", "크론", "cron"],
    "설정": ["설정", "설치", "config", "alias", "환경"],
    "리뷰": ["리뷰", "review", "감사", "audit"],
    "문서": ["문서", "README", "SKILL.md", "doc"],
}


def _reclassify_tag(tag: str, text: str) -> str:
    """tag가 '기타'이면 summary 키워드로 재분류."""
    if tag != "기타" or not text:
        return tag
    text_lower = text.lower()
    best_tag = "기타"
    best_count = 0
    for candidate, keywords in _TAG_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_tag = candidate
    return best_tag if best_count > 0 else "기타"


def _parse_summary_response(raw: str) -> dict:
    """Parse '[태그]\\n요약' format from LLM response."""
    lines = raw.strip().splitlines()
    tag = "기타"
    text_lines = []

    for line in lines:
        stripped = line.strip()
        # [태그] 형식 감지
        if stripped.startswith("[") and "]" in stripped:
            candidate = stripped[1:stripped.index("]")].strip()
            if candidate in WORK_TAGS:
                tag = candidate
                # 같은 줄에 태그 뒤 텍스트가 있으면 요약에 포함
                rest = stripped[stripped.index("]") + 1:].strip()
                if rest:
                    text_lines.append(rest)
                continue
        if stripped:
            text_lines.append(stripped)

    text = _clean_summary_text("\n".join(text_lines))
    tag = _reclassify_tag(tag, text)
    return {"tag": tag, "text": text}


# 코드블록, 파일 경로, 마크다운 문법을 정제
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_FILE_PATH_RE = re.compile(r"(?:~?/[\w._-]+){2,}")
_MD_HEADER_RE = re.compile(r"^#{1,4}\s+", re.MULTILINE)


def _clean_summary_text(text: str) -> str:
    """LLM 요약에서 코드블록, 파일경로, 마크다운 문법 제거."""
    text = _CODE_BLOCK_RE.sub("", text)
    # 인라인 코드: 백틱만 벗기고 내용은 유지
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = _FILE_PATH_RE.sub("", text)
    text = _MD_HEADER_RE.sub("", text)
    # 연속 공백/빈줄 정리
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()[:300]


BEHAVIOR_TIMEOUT_SEC = 60


def extract_behavioral_signals(user_messages: str, repo: str) -> dict | None:
    """sonnet으로 사용자 행동 신호 추출. 실패 시 None.

    Returns: {"decisions": [...], "mistakes": [...], "patterns": [...]} or None
    """
    if not user_messages.strip():
        return None
    prompt = (
        f"레포: {repo}\n\n"
        "다음은 Claude Code 세션에서 사용자가 보낸 메시지들이다.\n\n"
        f"{user_messages}\n\n"
        "이 사용자의 행동 신호를 추출해라.\n"
        "- decisions: 사용자가 명시적 선택을 한 것. **반드시 판단 근거(왜 A가 아니라 B를 선택했는지)를 포함**해라.\n"
        "  나쁜 예: '별도 프로젝트로 분리'\n"
        "  좋은 예: 'self-profile을 별도 worktree로 분리 — 기존 레포에 넣으면 scope이 커지고 독립 배포가 어려워서'\n"
        "- mistakes: 되돌린 것, 교정한 것, 시행착오. 무엇을 왜 되돌렸는지.\n"
        "- patterns: 관찰되는 작업 습관 (좋든 나쁘든). 구체적 행동과 맥락.\n"
        "각 항목은 1-2줄. 글자 수 제한 없음. 없으면 빈 배열.\n\n"
        'JSON으로만 출력. 다른 텍스트 없이:\n'
        '{"decisions": [...], "mistakes": [...], "patterns": [...]}'
    )
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "sonnet", "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=BEHAVIOR_TIMEOUT_SEC,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _parse_signals_response(result.stdout.strip())
    except subprocess.TimeoutExpired:
        print(f"[session_logger] extract_behavioral_signals timed out ({BEHAVIOR_TIMEOUT_SEC}s)", file=sys.stderr)
    except FileNotFoundError:
        print("[session_logger] 'claude' CLI not found on PATH", file=sys.stderr)
    except Exception as e:
        print(f"[session_logger] extract_behavioral_signals failed: {type(e).__name__}: {e}", file=sys.stderr)
    return None


def _parse_signals_response(raw: str) -> dict | None:
    """Parse JSON behavioral signals from LLM response."""
    # JSON 블록 추출 (```json ... ``` 또는 bare JSON)
    cleaned = raw.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned)
        if match:
            cleaned = match.group(1)
    # { 로 시작하는 부분 찾기
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
            result[key] = [str(item) for item in items if item]
        else:
            result[key] = []
    if not any(result.values()):
        return None
    return result


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
    has_commits = False

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
                                raw = strip_system_tags(block.get("text", ""))
                                if raw:
                                    first_user_msg = raw[:120]
                                    break
                    elif isinstance(content, str):
                        raw = strip_system_tags(content)
                        if raw:
                            first_user_msg = raw[:120]

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
                                if not has_commits and "git commit" in cmd.lower():
                                    has_commits = True
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

    # 종료 시간: 마지막 타임스탬프를 KST로 변환
    end_time_str = None
    if timestamps:
        last_ts = timestamps[-1]
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        end_kst = last_ts.astimezone(KST)
        end_time_str = end_kst.strftime("%H:%M")

    # 시작 시간: 가장 이른 타임스탬프를 KST로 변환
    start_kst = None
    if timestamps:
        first_ts = min(timestamps)
        if first_ts.tzinfo is None:
            first_ts = first_ts.replace(tzinfo=timezone.utc)
        start_kst = first_ts.astimezone(KST)

    return {
        "files": sorted(files_modified),
        "commands": commands_run[:10],
        "errors": errors[:5],
        "topic": first_user_msg,
        "duration_min": duration_min,
        "end_time": end_time_str,
        "start_kst": start_kst,
        "has_commits": has_commits,
        "tokens": {
            "input": token_input,
            "output": token_output,
            "cache_read": token_cache_read,
            "cache_create": token_cache_create,
            "api_calls": api_calls,
        },
    }


def parse_transcript_by_date(transcript_path: str, fallback_date: str | None = None) -> dict[str, dict]:
    """Parse transcript and split by KST date.

    Returns: {"2026-03-14": ParsedData, "2026-03-15": ParsedData, ...}
    각 ParsedData는 parse_transcript()와 동일한 구조.
    """
    by_date: dict[str, dict] = {}
    current_date = fallback_date

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                entry_date = current_date
                entry_ts = None
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        kst_dt = dt.astimezone(KST)
                        entry_date = kst_dt.strftime("%Y-%m-%d")
                        entry_ts = kst_dt
                        current_date = entry_date
                    except (ValueError, TypeError):
                        pass

                if not entry_date:
                    continue

                if entry_date not in by_date:
                    by_date[entry_date] = {
                        "files": set(),
                        "commands": [],
                        "errors": [],
                        "topic": "",
                        "user_messages": [],
                        "agent_messages": [],
                        "timestamps": [],
                        "token_input": 0,
                        "token_output": 0,
                        "token_cache_read": 0,
                        "token_cache_create": 0,
                        "api_calls": 0,
                        "has_commits": False,
                    }

                acc = by_date[entry_date]
                if entry_ts:
                    acc["timestamps"].append(entry_ts)

                entry_type = entry.get("type", "")
                msg = entry.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else ""

                if not acc["topic"] and entry_type == "user":
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                raw = strip_system_tags(block.get("text", ""))
                                if raw:
                                    acc["topic"] = raw[:120]
                                    break
                    elif isinstance(content, str):
                        raw = strip_system_tags(content)
                        if raw:
                            acc["topic"] = raw[:120]

                # user_messages 수집 (date-slice local)
                if entry_type == "user":
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                raw = strip_system_tags(block.get("text", ""))
                                if raw:
                                    acc["user_messages"].append(raw[:500])
                    elif isinstance(content, str):
                        raw = strip_system_tags(content)
                        if raw:
                            acc["user_messages"].append(raw[:500])

                # agent_messages 수집 (최대 5개)
                if entry_type == "assistant" and isinstance(content, list) and len(acc["agent_messages"]) < 5:
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "").strip()
                            if text:
                                acc["agent_messages"].append(text[:500])
                                break

                if entry_type == "assistant" and isinstance(msg, dict):
                    usage = msg.get("usage", {})
                    if usage:
                        acc["api_calls"] += 1
                        acc["token_input"] += usage.get("input_tokens", 0)
                        acc["token_output"] += usage.get("output_tokens", 0)
                        acc["token_cache_read"] += usage.get("cache_read_input_tokens", 0)
                        acc["token_cache_create"] += usage.get("cache_creation_input_tokens", 0)

                if entry_type == "assistant" and isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        tool = block.get("name", "")
                        inp = block.get("input", {})
                        if tool in ("Edit", "Write"):
                            fp = inp.get("file_path", "")
                            if fp:
                                acc["files"].add(fp)
                        if tool == "Bash":
                            cmd = inp.get("command", "")
                            if cmd:
                                if not acc["has_commits"] and "git commit" in cmd.lower():
                                    acc["has_commits"] = True
                                acc["commands"].append(cmd[:80])

                if entry_type == "tool_result":
                    data_field = entry.get("data", {})
                    text = ""
                    if isinstance(data_field, dict):
                        text = str(data_field.get("output", ""))[:120]
                    if text and ("error" in text.lower() or "Error" in text):
                        acc["errors"].append(text[:120])
    except (FileNotFoundError, PermissionError):
        pass

    result = {}
    for date_str, acc in by_date.items():
        timestamps = acc["timestamps"]
        duration_min = None
        if len(timestamps) >= 2:
            active_sec = 0
            sorted_ts = sorted(timestamps)
            for i in range(1, len(sorted_ts)):
                gap = (sorted_ts[i] - sorted_ts[i - 1]).total_seconds()
                if 0 < gap <= IDLE_THRESHOLD_SEC:
                    active_sec += gap
            duration_min = max(1, int(active_sec / 60))

        start_kst = min(timestamps) if timestamps else None
        end_kst = max(timestamps) if timestamps else None
        end_time_str = end_kst.strftime("%H:%M") if end_kst else None

        result[date_str] = {
            "files": sorted(acc["files"]),
            "commands": acc["commands"][:10],
            "errors": acc["errors"][:5],
            "topic": acc["topic"],
            "user_messages": acc["user_messages"],
            "agent_messages": acc["agent_messages"],
            "duration_min": duration_min,
            "end_time": end_time_str,
            "start_kst": start_kst,
            "has_commits": acc["has_commits"],
            "tokens": {
                "input": acc["token_input"],
                "output": acc["token_output"],
                "cache_read": acc["token_cache_read"],
                "cache_create": acc["token_cache_create"],
                "api_calls": acc["api_calls"],
            },
        }

    return result


# ── scan_and_record ───────────────────────────────

def scan_and_record(session_id: str, transcript_path: str, cwd: str) -> dict[str, dict]:
    """코어: transcript를 날짜별로 분할하여 SQLite에 직접 기록."""
    repo, branch = detect_repo_and_branch(cwd) if cwd else ("unknown", None)
    by_date = parse_transcript_by_date(transcript_path)
    if not by_date:
        return {}
    record_sessions("cc", session_id, by_date, repo, branch)
    return by_date


# ── Telegram ──────────────────────────────────────

def send_session_telegram(data: dict, repo: str, duration_min: int | None, summary: dict | None = None):
    """세션 종료 시 요약을 텔레그램으로 전송."""
    branch = data.get("branch")
    repo_label = f"{repo}/{branch}" if branch else repo
    if summary:
        tag = summary.get("tag", "")
        text = summary.get("text", "")
        tag_str = f"[{tag}] " if tag else ""
        msg = f"✅ {repo_label} — {tag_str}{text}"
    else:
        topic = data.get("topic", "작업 완료")
        msg = f"✅ {repo_label} — {topic[:100]}"

    dur = f" ({duration_min}분)" if duration_min else ""
    msg = f"{msg}{dur}"
    if len(msg) > 4096:
        msg = msg[:4090] + "..."

    send_telegram(msg, chat_id_key="CHAT_ID_SESSION", silent=True)


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

    by_date = scan_and_record(session_id, transcript_path, cwd)
    if not by_date:
        sys.exit(0)

    repo, _ = detect_repo_and_branch(cwd) if cwd else ("unknown", None)

    # SessionEnd: LLM 요약 + 행동 추출 (세션 전체 대상, 1회)
    if event == "SessionEnd":
        from concurrent.futures import ThreadPoolExecutor

        conversation = extract_conversation(transcript_path)
        user_msgs = extract_user_messages(transcript_path)
        summary = None
        signals = None

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                summary_future = pool.submit(summarize_session, conversation, repo)
                signals_future = pool.submit(extract_behavioral_signals, user_msgs, repo)

                try:
                    summary = summary_future.result(timeout=SUMMARY_TIMEOUT_SEC + 10)
                except Exception as e:
                    print(f"[session_logger] summary failed: {e}", file=sys.stderr)

                try:
                    signals = signals_future.result(timeout=BEHAVIOR_TIMEOUT_SEC + 10)
                except Exception as e:
                    print(f"[session_logger] signals failed: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[session_logger] ThreadPool failed: {e}", file=sys.stderr)

        if summary or signals:
            _, branch = detect_repo_and_branch(cwd) if cwd else ("unknown", None)
            record_sessions("cc", session_id, by_date, repo, branch,
                           summary=summary, behavioral_signals=signals)
        else:
            # Layer 2 실패 → SessionEnd이므로 최소한 status를 completed로
            from db import get_conn as _get_conn
            _conn = _get_conn()
            for _d in by_date:
                _conn.execute("""
                    UPDATE sessions SET status = 'completed'
                    WHERE source = 'cc' AND session_id = ? AND date = ?
                      AND status = 'in_progress'
                """, (session_id, _d))
            _conn.commit()
            _conn.close()

        # 텔레그램 전송
        last_data = by_date[max(by_date.keys())]
        total_duration = sum(d.get("duration_min") or 0 for d in by_date.values())
        send_session_telegram(last_data, repo, total_duration or None, summary)


if __name__ == "__main__":
    main()
