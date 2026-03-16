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


def summarize_session(conversation: str, repo: str) -> list[dict] | None:
    """claude CLI로 세션 토픽 분해 + 요약. 실패 시 None.

    Returns: [{"tag": "코딩", "summary": "...", "repo": "..."}, ...] or None
    """
    if not conversation.strip():
        return None
    tags_str = ", ".join(WORK_TAGS)
    prompt = (
        f"레포: {repo}\n\n"
        f"다음은 Claude Code 세션의 대화 내용이다.\n\n"
        f"{conversation}\n\n"
        "이 세션에서 수행한 작업을 **기능/작업 단위**별로 분해하라.\n"
        "하나의 기능만 작업했으면 1개, 여러 기능을 오갔으면 각각 분리.\n\n"
        "토픽 = 기능 단위 (activity type이 아님):\n"
        "- 같은 기능의 설계→구현→리뷰는 하나의 토픽으로 합침\n"
        "- 다른 레포/worktree로 전환 → 별도 토픽\n"
        "- 같은 레포에서 명확히 다른 기능 작업 → 별도 토픽\n"
        "- 나쁜 분해: [설계] spec 작성 / [코딩] 구현 / [리뷰] PR review (활동 유형별 분해)\n"
        "- 좋은 분해: pipeline-redesign — spec + 구현 + 리뷰 완료 (기능 단위)\n\n"
        f"각 토픽의 태그 (가장 비중 큰 활동 기준): {tags_str}\n\n"
        "요약 기준:\n"
        "- 기능명 — 무엇을 왜 했고, 결과는 무엇인지\n"
        "- worktree/브랜치명이 있으면 포함\n"
        "- 나쁜 예: '설계 논의', 'PR 리뷰', '디버깅'\n"
        "- 좋은 예: 'pipeline-redesign — 3계층 분리 아키텍처 설계 + 구현 + 리뷰 완료'\n\n"
        "각 토픽의 status:\n"
        "- completed: 작업 완료 (커밋, 머지 등)\n"
        "- in_progress: 아직 진행중\n"
        "- follow_up: 후속 작업 필요 (follow_up 필드에 내용 기술)\n"
        "- blocked: 외부 의존성으로 막힘\n\n"
        "JSON 배열로만 답하라. 다른 텍스트 금지:\n"
        '[{"tag": "태그", "summary": "기능명 — 상세 요약", "repo": "레포명", "status": "completed", "follow_up": "후속 작업 (없으면 null)"}]'
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
            return _parse_topics_response(result.stdout.strip(), repo)
    except subprocess.TimeoutExpired:
        print(f"[session_logger] summarize_session timed out ({SUMMARY_TIMEOUT_SEC}s)", file=sys.stderr)
    except FileNotFoundError:
        print("[session_logger] 'claude' CLI not found on PATH", file=sys.stderr)
    except Exception as e:
        print(f"[session_logger] summarize_session failed: {type(e).__name__}: {e}", file=sys.stderr)
    return None


def _parse_topics_response(raw: str, fallback_repo: str) -> list[dict] | None:
    """JSON 토픽 배열 파싱 + 검증. 실패 시 기존 형식 폴백."""
    json_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not json_match:
        print("[session_logger] _parse_topics_response: no JSON array, trying legacy format", file=sys.stderr)
        old = _parse_summary_response(raw)
        if old:
            return [{"tag": old.get("tag", "기타"), "summary": old["text"], "repo": fallback_repo}]
        return None
    try:
        topics = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"[session_logger] _parse_topics_response JSON parse failed: {e}", file=sys.stderr)
        return None
    if not isinstance(topics, list) or not topics:
        return None
    valid = []
    for t in topics[:10]:
        if not isinstance(t, dict) or not t.get("summary"):
            continue
        tag = t.get("tag", "기타")
        if tag not in WORK_TAGS:
            tag = "기타"
        topic = {
            "tag": tag,
            "summary": t["summary"],
            "repo": t.get("repo", fallback_repo),
        }
        if t.get("status"):
            topic["status"] = t["status"]
        if t.get("follow_up"):
            topic["follow_up"] = t["follow_up"]
        valid.append(topic)
    skipped = len(topics[:10]) - len(valid)
    if skipped:
        print(f"[session_logger] _parse_topics_response: skipped {skipped} invalid topics", file=sys.stderr)
    return valid if valid else None


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


def _extract_work_unit(file_path: str) -> tuple[str, str]:
    """파일 경로에서 (repo, work_unit) 추출.

    work_unit = worktree 이름이 있으면 worktree명, 없으면 repo명.
    다양한 경로 패턴 지원:
      .claude/worktrees/pipeline-redesign/... → ("daye-agent-toolkit", "pipeline-redesign")
      /git_workplace/cube-backend/... → ("cube-backend", "cube-backend")
      ~/.openclaw/workspace-mingming/... → ("openclaw", "workspace-mingming")
      ~/dy-minions-squad-fix-.../... → ("dy-minions-squad-fix-...", "dy-minions-squad-fix-...")
      ~/.claude/projects/-Users-...-dy-minions-squad/... → ("dy-minions-squad", "dy-minions-squad")
    """
    parts = file_path.split("/")

    # worktree 경로: .claude/worktrees/<name>/...
    for i, p in enumerate(parts):
        if p == "worktrees" and i + 1 < len(parts):
            wt_name = parts[i + 1]
            repo = ""
            for j, q in enumerate(parts):
                if q == "git_workplace" and j + 1 < len(parts):
                    repo = parts[j + 1]
                    break
            return (repo or wt_name, wt_name)

    # 일반 경로: git_workplace/<repo>/...
    for i, p in enumerate(parts):
        if p == "git_workplace" and i + 1 < len(parts):
            return (parts[i + 1], parts[i + 1])

    # .openclaw/workspace-<name>/...
    for i, p in enumerate(parts):
        if p == ".openclaw" and i + 1 < len(parts):
            return ("openclaw", parts[i + 1])

    # .claude/projects/-Users-...-<repo>/...
    for i, p in enumerate(parts):
        if p == "projects" and i + 1 < len(parts) and parts[i + 1].startswith("-"):
            project_hash = parts[i + 1]
            # 마지막 하이픈 구분 단어들에서 레포명 추출
            segments = project_hash.split("-")
            # -Users-dayejeong-git-workplace-daye-agent-toolkit → daye-agent-toolkit
            # -Users-dayejeong-dy-minions-squad → dy-minions-squad
            if "git" in segments and "workplace" in segments:
                idx = segments.index("workplace")
                repo = "-".join(segments[idx + 1:])
            else:
                # Users, dayejeong 등 제거 후 나머지
                repo = "-".join(segments[3:]) if len(segments) > 3 else project_hash
            return (repo, repo) if repo else ("", "")

    # home directory 직접 경로: ~/some-project-name/...
    home = str(Path.home())
    if file_path.startswith(home):
        rel = file_path[len(home):].strip("/")
        top_dir = rel.split("/")[0] if "/" in rel else rel
        if top_dir and not top_dir.startswith("."):
            return (top_dir, top_dir)

    return ("", "")


def _compute_topic_segments(file_timeline: list[tuple], all_timestamps: list, idle_threshold: int = 300) -> list[dict]:
    """파일 작업의 work_unit 전환 + 메시지 타임스탬프 → 토픽 구간 목록.

    Returns: [{"work_unit": str, "repo": str, "start_at": str, "end_at": str, "duration_min": int}, ...]
    각 구간은 같은 work_unit에서 연속 작업한 시간. idle gap으로 분리.
    """
    if not all_timestamps:
        return []

    # 1. 파일 작업에서 (timestamp, work_unit, repo) 이벤트 수집
    file_events = []
    for ts, fp in sorted(file_timeline):
        repo, wu = _extract_work_unit(fp)
        if wu:
            file_events.append((ts, wu, repo))

    # 2. 모든 타임스탬프를 시간순 정렬하고, 각 시점의 "현재 work_unit" 결정
    # file 이벤트가 있는 시점에서 work_unit이 바뀜. 없으면 이전 work_unit 유지.
    sorted_all = sorted(all_timestamps)
    file_idx = 0
    sorted_file = sorted(file_events)

    current_wu = ""
    current_repo = ""
    segments = []
    seg_start = sorted_all[0]
    seg_end = sorted_all[0]

    for ts in sorted_all:
        # 이 시점까지의 file 이벤트 처리 → work_unit 업데이트
        while file_idx < len(sorted_file) and sorted_file[file_idx][0] <= ts:
            _, wu, repo = sorted_file[file_idx]
            if wu != current_wu and current_wu:
                # work_unit 전환 → 이전 구간 저장
                dur = max(1, int((seg_end - seg_start).total_seconds() / 60))
                segments.append({
                    "work_unit": current_wu, "repo": current_repo,
                    "start_at": seg_start.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                    "end_at": seg_end.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                    "duration_min": dur,
                })
                seg_start = ts
            current_wu = wu
            current_repo = repo
            file_idx += 1

        # idle gap 체크
        gap = (ts - seg_end).total_seconds()
        if gap > idle_threshold and current_wu:
            # idle gap → 이전 구간 저장, 새 구간 시작
            dur = max(1, int((seg_end - seg_start).total_seconds() / 60))
            segments.append({
                "work_unit": current_wu, "repo": current_repo,
                "start_at": seg_start.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "end_at": seg_end.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "duration_min": dur,
            })
            seg_start = ts

        seg_end = ts

    # 마지막 구간
    if current_wu:
        dur = max(1, int((seg_end - seg_start).total_seconds() / 60))
        segments.append({
            "work_unit": current_wu, "repo": current_repo,
            "start_at": seg_start.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "end_at": seg_end.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "duration_min": dur,
        })
    elif sorted_all:
        # file 작업 없는 세션 → 전체를 하나의 구간으로
        dur = max(1, int((seg_end - seg_start).total_seconds() / 60))
        segments.append({
            "work_unit": "", "repo": "",
            "start_at": seg_start.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "end_at": seg_end.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "duration_min": dur,
        })

    # 같은 work_unit의 연속 구간 병합 + 2분 이하 잡음 흡수
    merged = []
    for seg in segments:
        if merged and merged[-1]["work_unit"] == seg["work_unit"]:
            merged[-1]["end_at"] = seg["end_at"]
            merged[-1]["duration_min"] += seg["duration_min"]
        elif seg["duration_min"] <= 2 and merged:
            # 2분 이하 구간 → 이전 구간에 흡수
            merged[-1]["end_at"] = seg["end_at"]
            merged[-1]["duration_min"] += seg["duration_min"]
        else:
            merged.append(dict(seg))

    return merged


def _compute_work_unit_time_ranges(file_timeline: list[tuple]) -> dict[str, dict]:
    """file_timeline [(timestamp, path), ...] → {work_unit: {start_at, end_at, duration_min, repo}}

    work_unit = worktree 이름 또는 repo 이름. 기능 단위별 실제 작업 시간.
    """
    if not file_timeline:
        return {}

    unit_events: dict[str, list] = {}
    unit_repo: dict[str, str] = {}
    for ts, fp in sorted(file_timeline):
        repo, work_unit = _extract_work_unit(fp)
        if work_unit:
            unit_events.setdefault(work_unit, []).append(ts)
            unit_repo[work_unit] = repo

    result = {}
    for unit, timestamps in unit_events.items():
        if not timestamps:
            continue
        first = min(timestamps)
        last = max(timestamps)
        dur = max(1, int((last - first).total_seconds() / 60))
        result[unit] = {
            "start_at": first.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "end_at": last.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "duration_min": dur,
            "repo": unit_repo[unit],
        }
    return result


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
                        "file_timeline": [],  # [(timestamp, file_path), ...] 시간순 파일 작업
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

                # user_messages 수집 (date-slice local, 최대 20개)
                if entry_type == "user" and len(acc["user_messages"]) < 20:
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
                                if entry_ts:
                                    acc["file_timeline"].append((entry_ts, fp))
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

        # file_timeline → work_unit_time_ranges + topic_segments
        work_unit_time_ranges = _compute_work_unit_time_ranges(acc.get("file_timeline", []))
        topic_segments = _compute_topic_segments(
            acc.get("file_timeline", []), timestamps, IDLE_THRESHOLD_SEC
        )

        # 활동 구간 (idle gap > 5분 기준으로 분리)
        activity_segments = []
        if len(timestamps) >= 2:
            sorted_ts = sorted(timestamps)
            seg_start = sorted_ts[0]
            seg_end = sorted_ts[0]
            for i in range(1, len(sorted_ts)):
                gap = (sorted_ts[i] - sorted_ts[i - 1]).total_seconds()
                if gap > IDLE_THRESHOLD_SEC:
                    # 이전 구간 저장
                    dur = max(1, int((seg_end - seg_start).total_seconds() / 60))
                    activity_segments.append({
                        "start": seg_start.strftime("%H:%M"),
                        "end": seg_end.strftime("%H:%M"),
                        "duration_min": dur,
                    })
                    seg_start = sorted_ts[i]
                seg_end = sorted_ts[i]
            # 마지막 구간
            dur = max(1, int((seg_end - seg_start).total_seconds() / 60))
            activity_segments.append({
                "start": seg_start.strftime("%H:%M"),
                "end": seg_end.strftime("%H:%M"),
                "duration_min": dur,
            })

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
            "work_unit_time_ranges": work_unit_time_ranges,
            "topic_segments": topic_segments,
            "activity_segments": activity_segments,
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
    try:
        record_sessions("cc", session_id, by_date, repo, branch)
    except Exception as e:
        print(f"[session_logger] record_sessions failed: {e}", file=sys.stderr)
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
        legacy_summary = None

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
            # summarize_session()은 항상 list[dict] 리턴 (새 토픽 형식)
            topics = summary if isinstance(summary, list) else None
            # topics가 있으면 legacy summary dict 파생 (텔레그램 등 하위 호환)
            if topics:
                first = topics[0]
                legacy_summary = {"tag": first["tag"], "text": first["summary"]}
            else:
                legacy_summary = summary if isinstance(summary, dict) else None
            record_sessions("cc", session_id, by_date, repo, branch,
                           summary=legacy_summary, topics=topics,
                           behavioral_signals=signals,
                           is_session_end=True)
        else:
            # Layer 2 실패 → SessionEnd이므로 최소한 status를 completed로
            try:
                from db import get_conn as _get_conn
                _conn = _get_conn()
                try:
                    for _d in by_date:
                        _conn.execute("""
                            UPDATE sessions SET status = 'completed'
                            WHERE source = 'cc' AND session_id = ? AND date = ?
                              AND status = 'in_progress'
                        """, (session_id, _d))
                    _conn.commit()
                finally:
                    _conn.close()
            except Exception as e:
                print(f"[session_logger] status update failed: {e}", file=sys.stderr)

        # 텔레그램 전송
        last_data = by_date[max(by_date.keys())]
        total_duration = sum(d.get("duration_min") or 0 for d in by_date.values())
        send_session_telegram(last_data, repo, total_duration or None, legacy_summary)


if __name__ == "__main__":
    main()
