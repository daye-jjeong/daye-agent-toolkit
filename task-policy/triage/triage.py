#!/usr/bin/env python3
"""
Task Triage - Auto-classify user requests into Epic/Project/Task.
Storage: Obsidian vault (~/clawd/memory/projects/).

Usage:
    python3 triage.py "user request" [--execute] [--auto-approve]

Default: dry-run mode (no writes)
"""

import sys
import os
import json
import re
from datetime import datetime, date
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.task_io import write_task, today, now, PROJECTS_DIR

# Configuration
CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {
    "projects_root": str(PROJECTS_DIR),
    "default_status": "todo",
    "default_priority": "medium",
    "dry_run_default": True,
    "auto_approve_keywords": ["진행해", "do it", "approve", "execute"],
    "similarity_threshold": 0.8
}

def load_config():
    """Load configuration from file or use defaults"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = json.load(f)
            return {**DEFAULT_CONFIG, **config}
    return DEFAULT_CONFIG

CONFIG = load_config()

# ============================================================================
# CLASSIFICATION LOGIC
# ============================================================================

def classify_request(user_request: str, context: dict = None) -> dict:
    """
    Classify user request into Epic/Project/Task

    Args:
        user_request: Raw user message
        context: Optional context (previous tasks, current projects)

    Returns:
        {
            "type": "Epic|Project|Task",
            "is_followup": bool,
            "parent_id": str|None,
            "parent_title": str|None,
            "reasoning": str,
            "suggested_title": str,
            "suggested_project": str|None,
            "confidence": float
        }
    """
    request_lower = user_request.lower()

    # 1. Check for follow-up indicators
    followup_keywords = ["v2", "개선", "수정", "추가", "리팩토링", "based on", "이어서", "버전", "업데이트"]
    is_followup = any(kw in request_lower for kw in followup_keywords)

    # 2. Size/scope indicators
    epic_keywords = ["플랫폼", "생태계", "전략", "이니셔티브", "프로그램", "캠페인"]
    project_keywords = ["구현", "연동", "자동화", "시스템", "파이프라인", "아키텍처", "가이드", "문서화"]
    task_keywords = ["리뷰", "작성", "확인", "수정", "테스트", "분석", "조회", "실행"]

    # 3. Duration indicators
    duration_patterns = {
        "Task": r"(\d+분|\d+시간|오늘|내일|today|tomorrow)",
        "Project": r"(\d+주|이번 주|다음 주|week)",
        "Epic": r"(\d+개?월|quarter|분기)"
    }

    # 4. Classify
    confidence = 0.5
    reasoning_parts = []

    # Check for Epic indicators
    if any(kw in request_lower for kw in epic_keywords):
        classification = "Epic"
        confidence = 0.8
        reasoning_parts.append("Epic keywords detected")

    # Check for Project indicators
    elif any(kw in request_lower for kw in project_keywords):
        classification = "Project"
        confidence = 0.75
        reasoning_parts.append("Project keywords detected")

    # Check for Task indicators (default)
    elif any(kw in request_lower for kw in task_keywords):
        classification = "Task"
        confidence = 0.9
        reasoning_parts.append("Task keywords detected")

    else:
        # Default heuristic: if short and specific -> Task
        if len(user_request) < 50:
            classification = "Task"
            confidence = 0.6
            reasoning_parts.append("Short request (< 50 chars) -> likely Task")
        else:
            classification = "Project"
            confidence = 0.5
            reasoning_parts.append("Medium request -> default to Project")

    # 5. Check duration patterns
    for cls, pattern in duration_patterns.items():
        if re.search(pattern, request_lower):
            if cls == classification:
                confidence += 0.1
            reasoning_parts.append(f"Duration pattern matches {cls}")

    # 6. Extract suggested title (clean up)
    suggested_title = user_request.strip()
    suggested_title = re.sub(r'(해줘|부탁|please|해주세요)$', '', suggested_title).strip()

    # 7. Suggest parent project (for Tasks)
    suggested_project = None
    if classification == "Task" and context:
        pass

    return {
        "type": classification,
        "is_followup": is_followup,
        "parent_id": None,
        "parent_title": None,
        "reasoning": " | ".join(reasoning_parts),
        "suggested_title": suggested_title,
        "suggested_project": suggested_project,
        "confidence": min(confidence, 1.0)
    }

# ============================================================================
# VAULT INTEGRATION
# ============================================================================

def get_project_folder(folder_name: str = None) -> str:
    """Get project folder path in vault"""
    if folder_name:
        return str(PROJECTS_DIR / folder_name)
    return str(PROJECTS_DIR)

def create_vault_entry(classification: dict, dry_run: bool = True, owner_name: str = "daye") -> dict:
    """
    Create vault task entry based on classification.

    Args:
        classification: Result from classify_request()
        dry_run: If True, only preview (no writes)
        owner_name: Default owner/assignee name

    Returns:
        {"path": str, "id": str, "title": str, "created": bool}
    """
    entry_type = classification["type"]
    title = classification["suggested_title"]

    if dry_run:
        print(f"\nDRY RUN - Would create {entry_type}:")
        print(f"   Title: {title}")
        print(f"   Owner: {owner_name}")
        print(f"   Priority: {CONFIG['default_priority']}")
        print(f"   Status: {CONFIG['default_status']}")
        print(f"   Start Date: [will be set when work begins]")
        print(f"   Due Date: [to be prompted]")
        if classification["is_followup"]:
            print(f"   Follow-up detected - would check for parent Task")
        return {
            "path": f"projects/dry-run-{entry_type.lower()}/t-dry-001.md",
            "id": "dry-run-id",
            "title": title,
            "created": False
        }

    # Determine project folder based on type
    if entry_type == "Task":
        project_folder = "work/default"
    else:
        slug = re.sub(r'[^a-z0-9가-힣]+', '-', title.lower()).strip('-')[:30]
        project_folder = f"work/{slug}"

    # Create task data
    task_data = {
        "title": title,
        "status": CONFIG["default_status"],
        "priority": CONFIG["default_priority"],
        "owner": owner_name,
    }

    result = write_task(project_folder, task_data)

    if result["success"]:
        return {
            "path": result["path"],
            "id": result["task_id"],
            "title": title,
            "created": True
        }
    else:
        print(f"Error creating vault entry: {result['error']}")
        return {
            "path": None,
            "id": None,
            "title": title,
            "created": False,
            "error": result["error"]
        }

# Backward-compatible alias
create_yaml_entry = create_vault_entry

def prompt_for_due_date() -> str:
    """Interactive prompt for due date"""
    print("\nDue Date가 설정되지 않았습니다.")
    print("   언제까지 완료해야 하나요? (예: 2026-02-10, 내일, 이번 주 금요일)")
    print("   또는 Enter를 눌러 나중에 설정:")

    user_input = input(">>> ").strip()

    if not user_input:
        return None

    if user_input == "내일":
        from datetime import timedelta
        return (date.today() + timedelta(days=1)).isoformat()
    elif user_input == "모레":
        from datetime import timedelta
        return (date.today() + timedelta(days=2)).isoformat()
    elif re.match(r'\d{4}-\d{2}-\d{2}', user_input):
        return user_input
    else:
        print("날짜 형식을 인식하지 못했습니다. 나중에 직접 설정하세요.")
        return None

# ============================================================================
# MAIN INTERFACE
# ============================================================================

def handle_user_request(user_message: str, auto_approve: bool = False) -> dict:
    """
    Main entry point - classify and create vault entry.

    Args:
        user_message: User's request
        auto_approve: Skip approval prompt (when user said "진행해")

    Returns:
        {"classification": dict, "yaml_entry": dict, "approved": bool}
    """
    # 1. Classify
    classification = classify_request(user_message)

    print(f"\nClassification Result:")
    print(f"   Type: {classification['type']}")
    print(f"   Title: {classification['suggested_title']}")
    print(f"   Confidence: {classification['confidence']:.0%}")
    print(f"   Reasoning: {classification['reasoning']}")
    if classification['is_followup']:
        print(f"   Follow-up detected")

    # 2. Determine if we should execute
    dry_run = CONFIG["dry_run_default"] and not auto_approve

    if dry_run and not auto_approve:
        print("\nDRY RUN MODE - No writes will be made")
        approve = input("   Proceed with vault creation? (y/N): ").strip().lower()
        if approve not in ['y', 'yes', '진행', '진행해']:
            print("Cancelled")
            return {
                "classification": classification,
                "yaml_entry": None,
                "approved": False
            }
        dry_run = False

    # 3. Create vault entry
    vault_entry = create_vault_entry(classification, dry_run=dry_run)

    # 4. Prompt for due date if created
    if vault_entry["created"] and not dry_run:
        due_date = prompt_for_due_date()
        if due_date and vault_entry.get("path"):
            from scripts.task_io import update_task
            update_task(vault_entry["path"], {"deadline": due_date})
            print(f"Due Date set: {due_date}")

    # 5. Return result
    if vault_entry["created"]:
        print(f"\nCreated: {vault_entry['path']}")

    return {
        "classification": classification,
        "yaml_entry": vault_entry,
        "approved": not dry_run
    }

# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Task Triage - Auto-classify and create vault entries")
    parser.add_argument("request", help="User request to classify")
    parser.add_argument("--execute", action="store_true", help="Execute (skip dry-run)")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve (no prompt)")
    parser.add_argument("--override-classification", choices=["Epic", "Project", "Task"],
                       help="Override auto-classification")

    args = parser.parse_args()

    # Override dry_run if --execute
    if args.execute:
        CONFIG["dry_run_default"] = False

    # Classify
    classification = classify_request(args.request)

    # Override if specified
    if args.override_classification:
        classification["type"] = args.override_classification
        classification["reasoning"] += f" | OVERRIDE: User specified {args.override_classification}"

    # Execute
    result = handle_user_request(args.request, auto_approve=args.auto_approve or args.execute)

    # Exit code
    sys.exit(0 if result["approved"] else 1)

if __name__ == "__main__":
    main()
