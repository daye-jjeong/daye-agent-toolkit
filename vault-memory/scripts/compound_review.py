#!/usr/bin/env python3
"""
Compound Review — 야간 자동 세션 리뷰 + 장기 기억 반영

Tier 2 (Hybrid): 규칙 기반 추출 + 선택적 LLM 판단
Cron: 30 22 * * * python3 ~/clawd/skills/vault-memory/scripts/compound_review.py

워크플로우:
1. 오늘 세션 로그 파싱
2. 핵심 배움 → MEMORY.md 후보
3. 정책 결정 → AGENTS.md 후보
4. 중복 체크 후 반영
5. Git commit (변경 시)
"""

import os
import re
import sys
import subprocess
import fcntl
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path.home() / "clawd"
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_MD = BASE_DIR / "MEMORY.md"
AGENTS_MD = BASE_DIR / "AGENTS.md"
LOG_FILE = Path("/tmp/compound_review.log")

# 정책 키워드 — AGENTS.md에 반영할 결정 감지용
POLICY_KEYWORDS = ["항상", "규칙으로", "정책 추가", "매번", "금지", "필수", "never", "always", "must"]

# Quick Reference가 있으면 compress가 이미 처리한 것
COMPRESS_MARKER = "## Quick Reference"


def log(msg: str):
    """로그를 파일 + stdout에 기록."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def read_file(path: Path) -> str:
    """파일 읽기. 없으면 빈 문자열."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def parse_sessions(content: str) -> list[dict]:
    """세션 로그에서 세션별 카테고리 항목 추출."""
    sessions = []
    # 세션 헤더: ## 세션 HH:MM (플랫폼, id) 또는 ## 세션 (플랫폼, id) (레거시)
    session_pattern = re.compile(r"^## 세션\s+(?:(\d{2}:\d{2})\s+)?\((.+?)\)", re.MULTILINE)
    matches = list(session_pattern.finditer(content))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_text = content[start:end]

        session = {
            "time": match.group(1) or "unknown",
            "platform": match.group(2),
            "결정사항": extract_category(section_text, "결정사항"),
            "핵심 배움": extract_category(section_text, "핵심 배움"),
            "해결한 문제": extract_category(section_text, "해결한 문제"),
            "에러/이슈": extract_category(section_text, "에러/이슈"),
            "미완료/대기": extract_category(section_text, "미완료/대기"),
        }
        sessions.append(session)

    return sessions


def extract_category(text: str, category: str) -> list[str]:
    """섹션 텍스트에서 특정 카테고리의 불릿 항목들 추출."""
    pattern = re.compile(rf"### {re.escape(category)}\n(.*?)(?=\n### |\n## |\Z)", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return []

    items = []
    for line in match.group(1).strip().split("\n"):
        line = line.strip()
        if line.startswith("- "):
            items.append(line[2:].strip())
    return items


def find_memory_candidates(sessions: list[dict]) -> list[str]:
    """MEMORY.md에 올릴 후보 추출 (핵심 배움 중 재사용 가치 높은 것)."""
    candidates = []
    for s in sessions:
        for item in s["핵심 배움"]:
            # 구체적이고 재사용 가능한 배움만 (너무 짧거나 일반적인 것 제외)
            if len(item) > 15:
                candidates.append(item)
    return candidates


def find_agents_candidates(sessions: list[dict]) -> list[str]:
    """AGENTS.md에 올릴 후보 추출 (정책 키워드 포함 결정)."""
    candidates = []
    for s in sessions:
        for item in s["결정사항"]:
            if any(kw in item.lower() for kw in POLICY_KEYWORDS):
                candidates.append(item)
    return candidates


def _normalize(text: str) -> str:
    """비교용 정규화 — 알파벳/숫자/한글만 남기고 소문자화."""
    return re.sub(r"[^a-z0-9가-힣]", "", text.lower())


def is_duplicate(item: str, existing_content: str) -> bool:
    """기존 내용에 이미 유사 항목이 있는지 체크."""
    norm_item = _normalize(item)
    norm_content = _normalize(existing_content)
    # 앞 30자로 판별 (충분히 고유)
    key = norm_item[:30]
    return len(key) > 10 and key in norm_content


def append_to_memory(candidates: list[str]) -> int:
    """MEMORY.md의 Lessons Learned 섹션에 항목 추가."""
    content = read_file(MEMORY_MD)
    added = 0

    new_items = []
    for item in candidates:
        if not is_duplicate(item, content):
            new_items.append(item)

    if not new_items:
        return 0

    today = date.today().isoformat()
    entry = f"\n### {today} — Compound Review\n"
    for item in new_items:
        entry += f"- {item}\n"

    # "Lessons Learned" 섹션 찾기, 없으면 끝에 추가
    if "## Lessons Learned" in content:
        # 섹션 끝에 추가
        pattern = re.compile(r"(## Lessons Learned.*?)(\n## |\Z)", re.DOTALL)
        match = pattern.search(content)
        if match:
            insert_pos = match.end(1)
            content = content[:insert_pos] + entry + content[insert_pos:]
    else:
        content += f"\n## Lessons Learned\n{entry}"

    with open(MEMORY_MD, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(content)
        fcntl.flock(f, fcntl.LOCK_UN)

    return len(new_items)


def append_to_agents(candidates: list[str]) -> int:
    """AGENTS.md의 Learned Lessons 섹션에 항목 추가."""
    content = read_file(AGENTS_MD)
    added = 0

    new_items = []
    for item in candidates:
        if not is_duplicate(item, content):
            new_items.append(item)

    if not new_items:
        return 0

    today = date.today().isoformat()
    entry = f"\n### {today}\n"
    for item in new_items:
        entry += f"- {item}\n"

    # "Learned Lessons" 섹션 찾기
    if "## Learned Lessons" in content:
        pattern = re.compile(r"(## Learned Lessons.*?)(\n## |\Z)", re.DOTALL)
        match = pattern.search(content)
        if match:
            insert_pos = match.end(1)
            content = content[:insert_pos] + entry + content[insert_pos:]
    else:
        # 파일 끝에 섹션 추가
        content += f"\n## Learned Lessons\n\n> Compound Review가 세션에서 추출한 운영 교훈. 월간 pruning 대상.\n{entry}"

    with open(AGENTS_MD, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(content)
        fcntl.flock(f, fcntl.LOCK_UN)

    return len(new_items)


def git_commit(memory_added: int, agents_added: int):
    """변경사항 git commit (gitignored 파일은 제외)."""
    today = date.today().isoformat()
    files_to_add = []

    # MEMORY.md는 gitignored (민감 파일) → 커밋 대상 아님
    if agents_added > 0:
        files_to_add.append("AGENTS.md")

    if not files_to_add:
        log(f"No git-trackable changes (memory: +{memory_added}, agents: +{agents_added})")
        return

    try:
        subprocess.run(
            ["git", "add"] + files_to_add,
            cwd=BASE_DIR,
            capture_output=True,
            check=True,
        )
        msg = f"compound: daily review {today} (+{memory_added} memory, +{agents_added} agents)"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=BASE_DIR,
            capture_output=True,
            check=True,
        )
        log(f"Git commit: {msg}")
    except subprocess.CalledProcessError as e:
        log(f"Git commit failed: {e.stderr.decode() if e.stderr else str(e)}")


def main():
    # 인자로 날짜 지정 가능: python3 compound_review.py 2026-02-11
    target_str = sys.argv[1] if len(sys.argv) > 1 else date.today().strftime("%Y-%m-%d")
    session_file = MEMORY_DIR / f"{target_str}.md"

    log(f"=== Compound Review Start: {target_str} ===")

    # 1. 세션 로그 확인
    content = read_file(session_file)
    if not content:
        log("No session log found for today. Skipping.")
        return

    # 2. 세션 파싱
    sessions = parse_sessions(content)
    if not sessions:
        log("No sessions found in today's log. Skipping.")
        return

    log(f"Found {len(sessions)} session(s)")

    # 3. 후보 추출
    memory_candidates = find_memory_candidates(sessions)
    agents_candidates = find_agents_candidates(sessions)

    log(f"Memory candidates: {len(memory_candidates)}")
    log(f"Agents candidates: {len(agents_candidates)}")

    # 4. 반영 (중복 체크 포함)
    memory_added = append_to_memory(memory_candidates) if memory_candidates else 0
    agents_added = append_to_agents(agents_candidates) if agents_candidates else 0

    log(f"Added to MEMORY.md: {memory_added}")
    log(f"Added to AGENTS.md: {agents_added}")

    # 5. Git commit
    if memory_added > 0 or agents_added > 0:
        git_commit(memory_added, agents_added)

    log(f"=== Compound Review Done ===\n")


if __name__ == "__main__":
    main()
