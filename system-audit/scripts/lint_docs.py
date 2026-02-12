#!/usr/bin/env python3
"""
doc-lint: 시스템 .md 파일 정합성 검사기
Usage: python3 lint_docs.py [--check all|refs|skills|models|duplicates|projects|stale|freshness] [--format text|json]
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta

# ─── 설정 ───────────────────────────────────────────────────────────────

CLAWD_ROOT = Path(os.environ.get("CLAWD_ROOT", Path.home() / "clawd"))

# 시스템 .md 파일 (루트 레벨)
SYSTEM_MD_FILES = [
    "AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md",
    "HEARTBEAT.md", "IDENTITY.md", "TOOLS.md"
]

# 활성 모델 목록 (AGENTS.md § 2.2 기준, 2026-02-12)
ACTIVE_MODELS = [
    "gpt-5.3-codex", "gpt-5.2", "gpt-5.2-codex",
    "claude-opus-4-6", "claude-sonnet-4-5", "claude-haiku-4-5",
    "gemini-3-pro-preview", "gemini-3-flash-preview",
    "gemini-3-pro", "gemini-3-flash",
    # provider 포함 형태
    "openai-codex/gpt-5.3-codex", "openai-codex/gpt-5.2", "openai-codex/gpt-5.2-codex",
    "anthropic/claude-opus-4-6", "anthropic/claude-sonnet-4-5", "anthropic/claude-haiku-4-5",
    "google-gemini-cli/gemini-3-pro-preview", "google-gemini-cli/gemini-3-flash-preview",
]

# 레거시 참조 감시 목록
STALE_PATTERNS = [
    {
        "pattern": r"jarvis-(?!HQ)",
        "label": "jarvis- prefix",
        "context": "스킬 prefix로 사용된 경우 (task-policy, banksalad-import 등으로 변경됨)",
        "severity": "warning",
    },
    {
        "pattern": r"(?<!/)\btask-os\b",
        "label": "task-os",
        "context": "task-policy로 변경됨",
        "severity": "warning",
    },
    {
        "pattern": r"notion_uploader",
        "label": "notion_uploader",
        "context": "yaml_writer로 대체됨",
        "severity": "warning",
    },
    {
        "pattern": r"\btasks\.yml\b",
        "label": "tasks.yml (레거시 태스크 형식)",
        "context": "per-task MD로 변경됨 (t-{project}-NNN.md)",
        "severity": "warning",
    },
    {
        "pattern": r"\bmingming-skills\b",
        "label": "mingming-skills",
        "context": "daye-agent-toolkit으로 변경됨",
        "severity": "warning",
    },
    {
        "pattern": r"\bclaude-skills\b",
        "label": "claude-skills",
        "context": "daye-agent-toolkit으로 변경됨",
        "severity": "warning",
    },
    {
        "pattern": r"gemini-2\.5",
        "label": "gemini-2.5 (사용 금지)",
        "context": "사용 금지 모델 — AGENTS.md § 2.2 참조",
        "severity": "error",
    },
    {
        "pattern": r"claude-opus-4-5(?!\d)",
        "label": "claude-opus-4-5 (구 모델명)",
        "context": "올바른 이름: claude-opus-4-6",
        "severity": "error",
    },
    {
        "pattern": r"\bgpt-5\.2\b(?!-codex).*\bprimary\b|\bprimary\b.*\bgpt-5\.2\b(?!-codex)",
        "label": "gpt-5.2 as primary (구 설정)",
        "context": "primary는 gpt-5.3-codex로 변경됨",
        "severity": "warning",
    },
]

# 잘못된 모델 이름 패턴
INVALID_MODEL_PATTERNS = [
    r"claude-opus-4-5(?!\d)",
    r"claude-sonnet-4-6",
    r"gemini-2\.5",
    r"gpt-4(?!\.)",  # gpt-4 단독 (gpt-4o는 OK)
    r"\bgpt-5\.2\b(?![\s\-])",  # gpt-5.2 단독 (gpt-5.2-codex는 OK) — 모델 목록 내부는 제외
]

# MEMORY.md 최신성 검사용 — deprecated 키워드/패턴
MEMORY_STALE_PATTERNS = [
    {
        "pattern": r"gpt-5\.2(?!-codex).*(?:primary|기본|메인)",
        "label": "gpt-5.2 as primary",
        "context": "primary는 gpt-5.3-codex. MEMORY.md 업데이트 필요",
    },
    {
        "pattern": r"claude-opus-4-5",
        "label": "claude-opus-4-5",
        "context": "현재 모델: claude-opus-4-6",
    },
    {
        "pattern": r"mingming-skills",
        "label": "mingming-skills 레포명",
        "context": "daye-agent-toolkit으로 변경됨",
    },
    {
        "pattern": r"\btasks\.yml\b",
        "label": "tasks.yml 참조",
        "context": "per-task MD(t-{project}-NNN.md)로 변경됨",
    },
    {
        "pattern": r"projects/_config/structure\.yml",
        "label": "projects/_config/structure.yml",
        "context": "memory/projects/config/로 이동됨",
    },
    {
        "pattern": r"projects/_goals/",
        "label": "projects/_goals/ 경로",
        "context": "memory/goals/로 이동됨",
    },
    {
        "pattern": r"\b~/clawd/projects/\b",
        "label": "~/clawd/projects/ (레거시 경로)",
        "context": "memory/projects/로 이동됨",
    },
]

# AGENTS.md 최신성 검사용
AGENTS_STALE_PATTERNS = [
    {
        "pattern": r"gpt-5\.2(?![\-\s]*codex).*(?:Primary|primary|기본)",
        "label": "gpt-5.2 as primary",
        "context": "primary는 gpt-5.3-codex로 변경됨",
    },
    {
        "pattern": r"memory/(?!projects|goals|state|docs|policy|reports|archive|finance|format|VAULT|MEMORY|\+inbox|YYYY)[a-z_]+\.json",
        "label": "memory/ 루트의 JSON 참조",
        "context": "상태 파일은 memory/state/로 이동됨",
    },
    {
        "pattern": r"projects/\*/tasks\.yml",
        "label": "projects/*/tasks.yml 참조",
        "context": "per-task MD(t-{project}-NNN.md)로 변경됨",
    },
]

# MEMORY.md 범위 검사 — 시스템 설정이 개인 메모리에 혼입되었는지 감지
MEMORY_SCOPE_PATTERNS = [
    # 섹션 헤더 (시스템 설정 섹션이 MEMORY.md에 있으면 안 됨)
    {
        "pattern": r"^##\s+(?:운영|기록)\s*원칙",
        "label": "운영/기록 원칙 섹션",
        "belongs_in": "AGENTS.md",
        "is_header": True,
    },
    {
        "pattern": r"^##\s+보안\s*원칙",
        "label": "보안 원칙 섹션",
        "belongs_in": "AGENTS.md § 3",
        "is_header": True,
    },
    {
        "pattern": r"^##\s+키/인증\s*관리",
        "label": "키/인증 관리 섹션",
        "belongs_in": "TOOLS.md",
        "is_header": True,
    },
    {
        "pattern": r"^##\s+워크스페이스.*구조",
        "label": "워크스페이스 구조 섹션",
        "belongs_in": "CLAUDE.md",
        "is_header": True,
    },
    {
        "pattern": r"^##\s+텔레그램\s+밍밍이",
        "label": "텔레그램 설정 섹션",
        "belongs_in": "TOOLS.md § Telegram",
        "is_header": True,
    },
    {
        "pattern": r"^##\s+(?:세션|session)\s*(?:정책|관리|보호)",
        "label": "세션 관리 정책 섹션",
        "belongs_in": "AGENTS.md § 2",
        "is_header": True,
    },
    # 콘텐츠 패턴 (시스템 설정 내용이 MEMORY.md 본문에 있으면 안 됨)
    {
        "pattern": r"(?:├──|└──|│\s+[├└])",
        "label": "디렉토리 트리 구조도",
        "belongs_in": "CLAUDE.md",
        "is_header": False,
    },
    {
        "pattern": r"~/.config/jarvis/keys/",
        "label": "키 스토어 경로",
        "belongs_in": "TOOLS.md",
        "is_header": False,
    },
    {
        "pattern": r"\bagents\.defaults\.",
        "label": "OpenClaw 설정값",
        "belongs_in": "config/ 또는 AGENTS.md",
        "is_header": False,
    },
    {
        "pattern": r"Tier\s+[123]\s*[:(]|도구\s*접근\s*등급",
        "label": "도구 접근 등급 정책",
        "belongs_in": "AGENTS.md § 2.1",
        "is_header": False,
    },
    {
        "pattern": r"\bsessions_spawn\b|메인\s*세션\s*=\s*대화\s*전용",
        "label": "세션 보호 정책",
        "belongs_in": "AGENTS.md § 2",
        "is_header": False,
    },
    {
        "pattern": r"\bSOT\b.*(?:memory|vault)|vault.*\bSOT\b",
        "label": "SOT 정의",
        "belongs_in": "AGENTS.md § 7.3",
        "is_header": False,
    },
]

# ─── 유틸리티 ───────────────────────────────────────────────────────────

class Issue:
    def __init__(self, check_type, severity, file, line, message, detail=""):
        self.check_type = check_type
        self.severity = severity  # "error" | "warning" | "info"
        self.file = file
        self.line = line
        self.message = message
        self.detail = detail

    def to_dict(self):
        return {
            "check": self.check_type,
            "severity": self.severity,
            "file": str(self.file),
            "line": self.line,
            "message": self.message,
            "detail": self.detail,
        }

    def __str__(self):
        icon = {"error": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(self.severity, "?")
        loc = f"{self.file}:{self.line}" if self.line else str(self.file)
        lines = [f"{icon} {self.check_type} | {loc}", f"   {self.message}"]
        if self.detail:
            lines.append(f"   → {self.detail}")
        return "\n".join(lines)


def read_file_lines(filepath):
    """파일을 읽어서 (line_number, line_text) 리스트 반환."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return list(enumerate(f.readlines(), 1))
    except (FileNotFoundError, PermissionError):
        return []


def is_in_code_block(lines, target_line):
    """해당 라인이 코드 블록(```) 안에 있는지 확인."""
    in_block = False
    for num, text in lines:
        if text.strip().startswith("```"):
            in_block = not in_block
        if num == target_line:
            return in_block
    return False


def get_system_md_files():
    """루트 시스템 .md 파일 목록 반환."""
    files = []
    for name in SYSTEM_MD_FILES:
        path = CLAWD_ROOT / name
        if path.exists():
            files.append(path)
    return files


def get_skill_dirs():
    """skills/ 내 실제 디렉토리 목록 반환."""
    skills_dir = CLAWD_ROOT / "skills"
    if not skills_dir.exists():
        return []
    return [d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]


def get_project_dirs():
    """memory/projects/ 내 실제 디렉토리 목록 반환."""
    projects_dir = CLAWD_ROOT / "memory" / "projects"
    if not projects_dir.exists():
        return []
    return [d.name for d in projects_dir.iterdir() if d.is_dir()]


# ─── 검사 함수 ──────────────────────────────────────────────────────────

def check_refs(issues):
    """참조 유효성 검사: .md에서 참조하는 파일 경로가 존재하는지."""
    path_pattern = re.compile(
        r'(?:`|")?'
        r'((?:skills|scripts|config|memory|docs|projects|data)/[A-Za-z0-9_\-./]+(?:\.\w+)?)'
        r'(?:`|")?'
    )
    # 템플릿 패턴 제외
    template_pattern = re.compile(r'\{[^}]+\}')
    # 플레이스홀더 경로 (예시용)
    placeholder_paths = {"skills/name", "scripts/domain", "data/domain"}

    checked = 0
    ok = 0

    for md_file in get_system_md_files():
        lines = read_file_lines(md_file)
        rel_name = md_file.relative_to(CLAWD_ROOT)

        for line_num, line_text in lines:
            if is_in_code_block(lines, line_num):
                continue

            for match in path_pattern.finditer(line_text):
                ref_path = match.group(1)

                # 템플릿/패턴 경로 스킵
                if template_pattern.search(ref_path):
                    continue
                # 와일드카드 스킵
                if "*" in ref_path:
                    continue
                # 날짜 패턴 스킵
                if re.search(r'YYYY|MM-DD', ref_path):
                    continue
                # 플레이스홀더 경로 스킵
                if ref_path.rstrip("/") in placeholder_paths:
                    continue

                checked += 1
                full_path = CLAWD_ROOT / ref_path

                # 파일 또는 디렉토리 존재 확인
                if full_path.exists() or full_path.with_suffix("").exists():
                    ok += 1
                else:
                    # 디렉토리로 끝나는 경우 (trailing /)
                    dir_path = full_path if ref_path.endswith("/") else full_path.parent / full_path.name
                    if not dir_path.exists():
                        issues.append(Issue(
                            "BROKEN_REF", "error",
                            rel_name, line_num,
                            f"참조: {ref_path}",
                            "파일/디렉토리 존재하지 않음"
                        ))

    return checked, ok


def check_skills(issues):
    """스킬 이름 일관성 검사."""
    existing_skills = set(get_skill_dirs())
    skill_ref_pattern = re.compile(r'skills/([A-Za-z0-9_\-]+)(?:/|`|"|\'|\s|\))')
    # 플레이스홀더 스킬 이름 (예시용)
    placeholder_skills = {"name", "example", "skill-name"}

    checked = 0
    ok = 0

    for md_file in get_system_md_files():
        lines = read_file_lines(md_file)
        rel_name = md_file.relative_to(CLAWD_ROOT)

        for line_num, line_text in lines:
            if is_in_code_block(lines, line_num):
                continue

            for match in skill_ref_pattern.finditer(line_text):
                skill_name = match.group(1)
                if skill_name in placeholder_skills:
                    continue
                checked += 1

                if skill_name in existing_skills:
                    ok += 1
                else:
                    issues.append(Issue(
                        "SKILL_NOT_FOUND", "error",
                        rel_name, line_num,
                        f"스킬 참조: skills/{skill_name}/",
                        f"skills/ 디렉토리에 '{skill_name}' 없음"
                    ))

    return checked, ok


def check_models(issues):
    """모델 이름 일관성 검사."""
    checked = 0
    found = 0

    for md_file in get_system_md_files():
        lines = read_file_lines(md_file)
        rel_name = md_file.relative_to(CLAWD_ROOT)

        for line_num, line_text in lines:
            if is_in_code_block(lines, line_num):
                continue

            for pattern in INVALID_MODEL_PATTERNS:
                match = re.search(pattern, line_text)
                if match:
                    found += 1
                    issues.append(Issue(
                        "INVALID_MODEL", "error",
                        rel_name, line_num,
                        f"잘못된 모델 참조: {match.group(0)}",
                        "AGENTS.md § 2.2의 활성 모델 목록 참조"
                    ))

    return checked, found


def check_duplicates(issues):
    """중복 콘텐츠 검사: 시스템 .md 파일 간 동일한 3줄 이상 연속 블록."""
    MIN_DUPLICATE_LINES = 3

    file_contents = {}
    for md_file in get_system_md_files():
        lines = read_file_lines(md_file)
        rel_name = str(md_file.relative_to(CLAWD_ROOT))
        text_lines = []
        in_block = False
        for num, text in lines:
            stripped = text.strip()
            if stripped.startswith("```"):
                in_block = not in_block
                continue
            if not in_block and stripped and not stripped.startswith("#"):
                text_lines.append((num, stripped))
        file_contents[rel_name] = text_lines

    found = 0
    checked_pairs = set()
    files = list(file_contents.keys())

    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            pair = (files[i], files[j])
            if pair in checked_pairs:
                continue
            checked_pairs.add(pair)

            lines_a = [t for _, t in file_contents[files[i]]]
            lines_b = [t for _, t in file_contents[files[j]]]

            for a_start in range(len(lines_a) - MIN_DUPLICATE_LINES + 1):
                window = lines_a[a_start:a_start + MIN_DUPLICATE_LINES]
                for b_start in range(len(lines_b) - MIN_DUPLICATE_LINES + 1):
                    if lines_b[b_start:b_start + MIN_DUPLICATE_LINES] == window:
                        a_line = file_contents[files[i]][a_start][0]
                        b_line = file_contents[files[j]][b_start][0]
                        found += 1
                        preview = window[0][:60] + "..." if len(window[0]) > 60 else window[0]
                        issues.append(Issue(
                            "DUPLICATE", "warning",
                            files[i], a_line,
                            f"중복 블록 ({MIN_DUPLICATE_LINES}줄+): \"{preview}\"",
                            f"동일 내용이 {files[j]}:{b_line}에도 존재"
                        ))
                        break

    return len(checked_pairs), found


def check_projects(issues):
    """프로젝트 구조 정합성 검사 (memory/projects/)."""
    projects_dir = CLAWD_ROOT / "memory" / "projects"
    if not projects_dir.exists():
        return 0, 0

    checked = 0
    ok = 0
    special_dirs = {"config", "_archive"}

    for d in sorted(projects_dir.iterdir()):
        if not d.is_dir():
            continue
        if d.name in special_dirs:
            continue

        checked += 1

        # 네이밍 규칙 확인: {type}--{name}
        if "--" not in d.name:
            issues.append(Issue(
                "PROJECT_NAMING", "warning",
                f"memory/projects/{d.name}", None,
                f"프로젝트 이름이 '{{type}}--{{name}}' 형식이 아님",
                "예: work--ronik, personal--health"
            ))
        else:
            # 필수 파일 확인: project.yml + t-{project}-NNN.md 1개 이상
            has_project = (d / "project.yml").exists()
            task_files = list(d.glob("t-*.md"))

            if has_project and task_files:
                ok += 1
            else:
                missing = []
                if not has_project:
                    missing.append("project.yml")
                if not task_files:
                    missing.append("t-{project}-NNN.md (태스크 파일 없음)")
                issues.append(Issue(
                    "PROJECT_MISSING_FILE", "warning",
                    f"memory/projects/{d.name}", None,
                    f"필수 파일 누락: {', '.join(missing)}",
                    ""
                ))

    return checked, ok


def check_stale(issues):
    """레거시 참조 검사."""
    found = 0

    for md_file in get_system_md_files():
        lines = read_file_lines(md_file)
        rel_name = md_file.relative_to(CLAWD_ROOT)

        for line_num, line_text in lines:
            if is_in_code_block(lines, line_num):
                continue

            for stale in STALE_PATTERNS:
                match = re.search(stale["pattern"], line_text)
                if match:
                    found += 1
                    issues.append(Issue(
                        "STALE_REF", stale["severity"],
                        rel_name, line_num,
                        f"레거시 참조: {match.group(0)} ({stale['label']})",
                        stale["context"]
                    ))

    return found


def check_freshness(issues):
    """MEMORY.md 및 AGENTS.md 내용 최신성 검사."""
    found = 0

    # MEMORY.md 검사
    memory_file = CLAWD_ROOT / "MEMORY.md"
    if memory_file.exists():
        lines = read_file_lines(memory_file)
        for line_num, line_text in lines:
            if is_in_code_block(lines, line_num):
                continue
            for stale in MEMORY_STALE_PATTERNS:
                match = re.search(stale["pattern"], line_text, re.IGNORECASE)
                if match:
                    found += 1
                    issues.append(Issue(
                        "STALE_CONTENT", "warning",
                        "MEMORY.md", line_num,
                        f"deprecated 정보: {match.group(0)} ({stale['label']})",
                        stale["context"]
                    ))

    # AGENTS.md 검사
    agents_file = CLAWD_ROOT / "AGENTS.md"
    if agents_file.exists():
        lines = read_file_lines(agents_file)
        for line_num, line_text in lines:
            if is_in_code_block(lines, line_num):
                continue
            for stale in AGENTS_STALE_PATTERNS:
                match = re.search(stale["pattern"], line_text, re.IGNORECASE)
                if match:
                    found += 1
                    issues.append(Issue(
                        "STALE_CONTENT", "warning",
                        "AGENTS.md", line_num,
                        f"deprecated 정보: {match.group(0)} ({stale['label']})",
                        stale["context"]
                    ))

    # MEMORY.md 범위 검사 (check_memory_scope에서 별도 수행하지만, freshness에서도 간단 체크)

    # MEMORY.md 마지막 수정일 체크 (30일 이상 미수정 시 경고)
    if memory_file.exists():
        import stat
        mtime = memory_file.stat().st_mtime
        from datetime import datetime
        last_mod = datetime.fromtimestamp(mtime).date()
        days_old = (date.today() - last_mod).days
        if days_old > 30:
            found += 1
            issues.append(Issue(
                "STALE_CONTENT", "info",
                "MEMORY.md", None,
                f"MEMORY.md가 {days_old}일간 미수정",
                "정기 리뷰/pruning 필요할 수 있음"
            ))

    return found


def check_memory_scope(issues):
    """MEMORY.md 범위 검사: 시스템 설정이 개인 메모리에 혼입되었는지."""
    memory_file = CLAWD_ROOT / "MEMORY.md"
    if not memory_file.exists():
        return 0

    lines = read_file_lines(memory_file)
    found = 0

    for line_num, line_text in lines:
        if is_in_code_block(lines, line_num):
            continue

        for scope in MEMORY_SCOPE_PATTERNS:
            match = re.search(scope["pattern"], line_text)
            if match:
                found += 1
                severity = "warning" if scope.get("is_header") else "info"
                issues.append(Issue(
                    "MEMORY_SCOPE", severity,
                    "MEMORY.md", line_num,
                    f"시스템 설정 혼입: {match.group(0)} ({scope['label']})",
                    f"→ {scope['belongs_in']}에 있어야 함"
                ))

    return found


# ─── 출력 ───────────────────────────────────────────────────────────────

def print_text_report(results, issues):
    """텍스트 형식 보고서."""
    print(f"\n📋 Doc Lint Report — {date.today()}")
    print("━" * 45)

    for check_name, (checked, ok_or_found, label) in results.items():
        if check_name in ("stale", "models", "duplicates", "freshness", "memory_scope"):
            icon = "✅" if ok_or_found == 0 else "⚠️"
            print(f"{icon} {label}: {ok_or_found} issue(s)")
        else:
            icon = "✅" if checked == ok_or_found else "⚠️"
            print(f"{icon} {label}: {ok_or_found}/{checked} OK" + (f" ({checked - ok_or_found} issues)" if checked != ok_or_found else ""))

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos = [i for i in issues if i.severity == "info"]

    total = len(issues)
    print(f"\n총 이슈: {total}건", end="")
    parts = []
    if errors:
        parts.append(f"🔴 {len(errors)} error")
    if warnings:
        parts.append(f"⚠️ {len(warnings)} warning")
    if infos:
        parts.append(f"ℹ️ {len(infos)} info")
    if parts:
        print(f" ({', '.join(parts)})")
    else:
        print(" 🎉")

    if issues:
        print("\n" + "─" * 45)
        print("상세 이슈:")
        print()
        for issue in sorted(issues, key=lambda x: (0 if x.severity == "error" else 1 if x.severity == "warning" else 2)):
            print(issue)
            print()


def print_json_report(results, issues):
    """JSON 형식 보고서."""
    report = {
        "summary": {},
        "issues": [i.to_dict() for i in issues],
        "total_issues": len(issues),
        "errors": len([i for i in issues if i.severity == "error"]),
        "warnings": len([i for i in issues if i.severity == "warning"]),
    }
    for check_name, (checked, ok_or_found, label) in results.items():
        report["summary"][check_name] = {
            "label": label,
            "checked": checked,
            "ok": ok_or_found,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))


# ─── 메인 ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="시스템 .md 파일 정합성 검사")
    parser.add_argument("--check", default="all",
                        choices=["all", "refs", "skills", "models", "duplicates", "projects", "stale", "freshness", "memory_scope"],
                        help="실행할 검사 유형")
    parser.add_argument("--format", default="text", choices=["text", "json"],
                        help="출력 형식")
    parser.add_argument("--root", default=None,
                        help="clawd 루트 디렉토리 (기본: ~/clawd)")
    args = parser.parse_args()

    global CLAWD_ROOT
    if args.root:
        CLAWD_ROOT = Path(args.root)

    if not CLAWD_ROOT.exists():
        print(f"❌ clawd 루트 디렉토리를 찾을 수 없음: {CLAWD_ROOT}", file=sys.stderr)
        sys.exit(1)

    issues = []
    results = {}
    checks = args.check

    if checks in ("all", "refs"):
        checked, ok = check_refs(issues)
        results["refs"] = (checked, ok, "참조 유효성")

    if checks in ("all", "skills"):
        checked, ok = check_skills(issues)
        results["skills"] = (checked, ok, "스킬 이름")

    if checks in ("all", "models"):
        _, found = check_models(issues)
        results["models"] = (0, found, "모델 이름")

    if checks in ("all", "duplicates"):
        checked, found = check_duplicates(issues)
        results["duplicates"] = (checked, found, "중복 콘텐츠")

    if checks in ("all", "projects"):
        checked, ok = check_projects(issues)
        results["projects"] = (checked, ok, "프로젝트 구조")

    if checks in ("all", "stale"):
        found = check_stale(issues)
        results["stale"] = (0, found, "레거시 참조")

    if checks in ("all", "freshness"):
        found = check_freshness(issues)
        results["freshness"] = (0, found, "내용 최신성")

    if checks in ("all", "memory_scope"):
        found = check_memory_scope(issues)
        results["memory_scope"] = (0, found, "MEMORY.md 범위")

    if args.format == "json":
        print_json_report(results, issues)
    else:
        print_text_report(results, issues)

    # Exit code: 1 if errors, 0 otherwise
    has_errors = any(i.severity == "error" for i in issues)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
