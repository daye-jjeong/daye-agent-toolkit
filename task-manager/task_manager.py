#!/usr/bin/env python3
"""
Task Manager - Vault 기반 태스크 CRUD

Obsidian vault (~/clawd/memory/projects/) 에 태스크를 생성/업데이트/완료.
Notion API 의존성 없음. stdlib만 사용.

Commands:
- create: 새 태스크 생성 (t-{prefix}-NNN.md)
- update-progress: Progress log 추가
- add-deliverable: 산출물 등록
- close: 태스크 완료 처리
- dry-run: 미리보기
"""

import sys
import json
import argparse
import os
import re
from datetime import datetime
from pathlib import Path

# Vault paths
VAULT_DIR = Path(os.environ.get("TASK_VAULT", "~/clawd/memory")).expanduser()
PROJECTS_DIR = VAULT_DIR / "projects"


def log(message, level="INFO"):
    """Simple logging to stderr"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", file=sys.stderr)


def get_kst_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M KST")


def sanitize(name, max_len=50):
    """파일시스템 안전한 이름."""
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', "", name)
    name = name.replace(" ", "_").strip("._")
    return name[:max_len] if name else "unknown"


def _write_frontmatter(filepath, fm, body=""):
    """frontmatter dict + body를 .md 파일로 작성."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif v is None or v == "":
            continue
        else:
            sv = str(v)
            if any(c in sv for c in ":#{}[]|>&*!?,"):
                lines.append(f'{k}: "{sv}"')
            else:
                lines.append(f"{k}: {sv}")
    lines.append("---")

    content = "\n".join(lines)
    if body:
        content += f"\n\n{body}\n"
    else:
        content += "\n"

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _parse_frontmatter(text):
    """마크다운 텍스트에서 frontmatter dict + body를 분리."""
    fm = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    val = val.strip().strip('"')
                    if val.lower() == "true":
                        val = True
                    elif val.lower() == "false":
                        val = False
                    else:
                        try:
                            val = int(val)
                        except ValueError:
                            try:
                                val = float(val)
                            except ValueError:
                                pass
                    fm[key.strip()] = val
    return fm, body


def _find_project_dir(project_name):
    """프로젝트 디렉토리 탐색 (work--X 또는 personal--X)."""
    if not PROJECTS_DIR.exists():
        return None
    for type_dir in PROJECTS_DIR.iterdir():
        if not type_dir.is_dir() or type_dir.name.startswith("_"):
            continue
        candidate = type_dir / project_name
        if candidate.is_dir():
            return candidate
        # type--name 패턴 탐색
        for proj in type_dir.iterdir():
            if proj.is_dir() and proj.name == project_name:
                return proj
    return None


def _next_task_id(project_dir, prefix):
    """프로젝트 내 다음 태스크 번호."""
    existing = list(project_dir.glob(f"t-{prefix}-*.md"))
    if not existing:
        return 1
    numbers = []
    for f in existing:
        m = re.search(rf"t-{re.escape(prefix)}-(\d+)\.md$", f.name)
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) + 1 if numbers else 1


def create_task(args):
    """Vault에 새 태스크 .md 파일 생성."""
    log(f"Creating Task: {args.name}")

    # 프로젝트 디렉토리 결정
    if args.project_dir:
        project_dir = PROJECTS_DIR / args.project_dir
    else:
        project_dir = PROJECTS_DIR / "personal" / "misc"

    project_dir.mkdir(parents=True, exist_ok=True)

    # 태스크 ID 생성
    prefix = args.prefix or sanitize(project_dir.name)[:10]
    task_num = _next_task_id(project_dir, prefix)
    task_id = f"t-{prefix}-{task_num:03d}"
    filename = f"{task_id}.md"

    # Frontmatter
    fm = {
        "id": task_id,
        "title": args.name,
        "status": "in_progress",
        "priority": args.priority.lower() if args.priority else "medium",
        "owner": "user",
        "created": datetime.now().strftime("%Y-%m-%d"),
        "updated_by": "task-manager",
    }
    if args.area:
        fm["area"] = args.area
    if args.tags:
        fm["tags"] = args.tags

    # Body
    acceptance_criteria = args.acceptance_criteria.split("|") if args.acceptance_criteria else ["To be defined"]
    task_breakdown = args.task_breakdown.split("|") if args.task_breakdown else ["To be defined"]
    timestamp = get_kst_timestamp()

    body_parts = [
        f"# {args.name}",
        "",
        "## Context",
        f"**Purpose:** {args.purpose or 'To be defined'}",
        f"**Created:** {timestamp}",
        "",
        "## Goals & Acceptance Criteria",
        f"**Goal:** {args.goal or 'To be defined'}",
        "",
    ]
    for c in acceptance_criteria:
        body_parts.append(f"- [ ] {c}")
    body_parts.extend([
        "",
        "## Task Breakdown",
    ])
    for i, step in enumerate(task_breakdown, 1):
        body_parts.append(f"{i}. {step}")
    body_parts.extend([
        "",
        "## Progress Log",
        f"### [{timestamp}] Started",
        "- Task created and initialized",
        "",
        "## Deliverables",
        "",
        "## Completion Summary",
        "*To be filled when status -> done*",
    ])
    body = "\n".join(body_parts)

    if args.dry_run:
        log("DRY RUN: Would create Task:", "INFO")
        print(json.dumps(fm, indent=2, ensure_ascii=False))
        print(body[:500])
        return

    fpath = _write_frontmatter(project_dir / filename, fm, body)
    log(f"Task created: {fpath}", "INFO")
    print(json.dumps({
        "status": "success",
        "task_id": task_id,
        "path": str(fpath),
    }, indent=2))


def update_progress(args):
    """태스크 파일에 progress log 추가."""
    log(f"Updating progress for: {args.task_id}")

    task_file = _find_task_file(args.task_id)
    if not task_file:
        log(f"Task not found: {args.task_id}", "ERROR")
        sys.exit(1)

    if args.dry_run:
        timestamp = get_kst_timestamp()
        log("DRY RUN: Would append progress entry:", "INFO")
        print(f"[{timestamp}] {args.status or 'Update'}\n{args.entry}")
        return

    text = task_file.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    timestamp = get_kst_timestamp()
    progress_entry = f"\n### [{timestamp}] {args.status or 'Update'}\n- {args.entry}\n"

    # Progress Log 섹션 뒤에 삽입
    if "## Progress Log" in body:
        idx = body.index("## Progress Log") + len("## Progress Log")
        body = body[:idx] + progress_entry + body[idx:]
    else:
        body += f"\n## Progress Log{progress_entry}"

    fm["updated_by"] = "task-manager"
    _write_frontmatter(task_file, fm, body)

    log("Progress updated", "INFO")
    print(json.dumps({"status": "success", "message": "Progress log updated"}))


def add_deliverable(args):
    """태스크에 산출물 등록."""
    log(f"Adding deliverable to: {args.task_id}")

    task_file = _find_task_file(args.task_id)
    if not task_file:
        log(f"Task not found: {args.task_id}", "ERROR")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d")
    deliverable_entry = (
        f"- **{args.version}** [{timestamp}]: {args.url}\n"
        f"  - Summary: {args.summary}\n"
        f"  - Format: {args.format or 'markdown'}"
    )

    if args.dry_run:
        log("DRY RUN: Would add deliverable:", "INFO")
        print(deliverable_entry)
        return

    text = task_file.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    if "## Deliverables" in body:
        idx = body.index("## Deliverables") + len("## Deliverables")
        body = body[:idx] + f"\n{deliverable_entry}\n" + body[idx:]
    else:
        body += f"\n## Deliverables\n{deliverable_entry}\n"

    fm["updated_by"] = "task-manager"
    _write_frontmatter(task_file, fm, body)

    log("Deliverable added", "INFO")
    print(json.dumps({"status": "success", "message": "Deliverable added"}))


def close_task(args):
    """태스크 완료 처리."""
    log(f"Closing Task: {args.task_id}")

    task_file = _find_task_file(args.task_id)
    if not task_file:
        log(f"Task not found: {args.task_id}", "ERROR")
        sys.exit(1)

    if args.dry_run:
        log("DRY RUN: Would close Task with summary:", "INFO")
        print(args.summary)
        return

    text = task_file.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    fm["status"] = "done"
    fm["completed"] = datetime.now().strftime("%Y-%m-%d")
    fm["updated_by"] = "task-manager"

    timestamp = get_kst_timestamp()
    if "## Completion Summary" in body:
        idx = body.index("## Completion Summary") + len("## Completion Summary")
        body = body[:idx] + f"\n**Completed:** {timestamp}\n{args.summary}\n" + body[idx:]
    else:
        body += f"\n## Completion Summary\n**Completed:** {timestamp}\n{args.summary}\n"

    _write_frontmatter(task_file, fm, body)

    log("Task closed", "INFO")
    print(json.dumps({"status": "success", "message": "Task closed"}))


def _find_task_file(task_id):
    """vault 전체에서 태스크 파일 탐색."""
    if not PROJECTS_DIR.exists():
        return None
    for f in PROJECTS_DIR.rglob(f"{task_id}.md"):
        return f
    # task_id가 파일 경로일 수도 있음
    p = Path(task_id)
    if p.exists():
        return p
    return None


def main():
    parser = argparse.ArgumentParser(description="Task Manager - Vault 기반 태스크 관리")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create command
    create_parser = subparsers.add_parser("create", help="태스크 생성")
    create_parser.add_argument("--name", required=True, help="태스크 이름")
    create_parser.add_argument("--purpose", help="목적")
    create_parser.add_argument("--goal", help="목표")
    create_parser.add_argument("--acceptance-criteria", help="완료 기준 (pipe-separated)")
    create_parser.add_argument("--task-breakdown", help="작업 단계 (pipe-separated)")
    create_parser.add_argument("--project-dir", help="프로젝트 디렉토리 (예: work/my-project)")
    create_parser.add_argument("--prefix", help="태스크 ID prefix (예: proj)")
    create_parser.add_argument("--priority", choices=["High", "Medium", "Low"], help="우선순위")
    create_parser.add_argument("--area", help="영역")
    create_parser.add_argument("--tags", help="태그 (comma-separated)")
    create_parser.add_argument("--dry-run", action="store_true", help="미리보기")

    # Update progress
    progress_parser = subparsers.add_parser("update-progress", help="Progress log 추가")
    progress_parser.add_argument("--task-id", required=True, help="태스크 ID (t-xxx-NNN)")
    progress_parser.add_argument("--entry", required=True, help="Progress 내용")
    progress_parser.add_argument("--status", help="상태 라벨")
    progress_parser.add_argument("--dry-run", action="store_true", help="미리보기")

    # Add deliverable
    deliverable_parser = subparsers.add_parser("add-deliverable", help="산출물 등록")
    deliverable_parser.add_argument("--task-id", required=True, help="태스크 ID")
    deliverable_parser.add_argument("--version", required=True, help="버전 (v1, v2)")
    deliverable_parser.add_argument("--url", required=True, help="산출물 경로/URL")
    deliverable_parser.add_argument("--summary", required=True, help="요약")
    deliverable_parser.add_argument("--format", help="포맷 (markdown, PDF 등)")
    deliverable_parser.add_argument("--dry-run", action="store_true", help="미리보기")

    # Close
    close_parser = subparsers.add_parser("close", help="태스크 완료")
    close_parser.add_argument("--task-id", required=True, help="태스크 ID")
    close_parser.add_argument("--summary", required=True, help="완료 요약")
    close_parser.add_argument("--dry-run", action="store_true", help="미리보기")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "create":
        create_task(args)
    elif args.command == "update-progress":
        update_progress(args)
    elif args.command == "add-deliverable":
        add_deliverable(args)
    elif args.command == "close":
        close_task(args)
    else:
        log(f"Unknown command: {args.command}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
