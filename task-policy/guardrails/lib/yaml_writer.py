#!/usr/bin/env python3
"""
Task Writer for Obsidian Vault
Write/update task markdown files with Dataview-queryable frontmatter.
Replaces YAML-based task storage.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.task_io import (
    write_task,
    read_task,
    update_task,
    update_task_status as _update_task_status,
    add_deliverable_link as _add_deliverable_link,
    read_tasks as _read_tasks,
    find_task_by_id,
    today,
    now,
)


def write_task_to_yaml(project_folder: str, task_data: Dict) -> Dict:
    """
    Create task as markdown file with frontmatter in vault project folder.
    Backward-compatible API name.

    Args:
        project_folder: Path to project folder (e.g., "work/ronik")
        task_data: Task data dictionary with keys:
            - id: Task identifier (e.g., "t-ronik-007")
            - title: Task title
            - description: Task description
            - status: Task status (todo, in_progress, done)
            - priority: Priority level (high, medium, low)
            - start: ISO 8601 datetime (optional)
            - deadline: ISO 8601 date (optional)
            - tags: List of tags (optional)
            - model: AI model used (optional)
            - session_id: Session identifier (optional)

    Returns:
        {"success": bool, "path": str|None, "task_id": str|None, "error": str|None}
    """
    # Build body from description
    body_parts = []
    desc = task_data.pop("description", "")
    if desc:
        body_parts.append(f"## 작업 내용\n{desc}")

    body_parts.append("\n## 진행 로그")
    body_parts.append(f"- {today()} (system): 태스크 생성")

    body_parts.append("\n## 산출물")

    body = "\n".join(body_parts)

    # Map old field names to vault convention
    if "start_date" in task_data and "start" not in task_data:
        task_data["start"] = task_data.pop("start_date")
    if "due_date" in task_data and "deadline" not in task_data:
        task_data["deadline"] = task_data.pop("due_date")

    task_data.setdefault("created", today())

    return write_task(project_folder, task_data, body)


def update_task_status(project_folder: str, task_id: str, new_status: str) -> Dict:
    """
    Update task status.

    Args:
        project_folder: Path to project folder (used for backward compat, actually looks up by ID)
        task_id: Task ID to update
        new_status: New status (todo, in_progress, done)

    Returns:
        {"success": bool, "updated_at": str|None, "error": str|None}
    """
    task_path = find_task_by_id(task_id)
    if not task_path:
        return {
            "success": False,
            "updated_at": None,
            "error": f"Task not found: {task_id}"
        }

    return _update_task_status(task_path, new_status)


def read_tasks(project_folder: str) -> Dict:
    """
    Read all tasks from project folder.

    Args:
        project_folder: Path to project folder

    Returns:
        {"success": bool, "tasks": dict|None, "count": int, "error": str|None}
    """
    result = _read_tasks(project_folder)

    if result["success"]:
        # Convert list format to dict format for backward compat
        tasks_dict = {}
        for task in result["tasks"]:
            tid = task.get("id", task.get("_path", "unknown"))
            tasks_dict[tid] = task
        return {
            "success": True,
            "tasks": tasks_dict,
            "count": result["count"],
            "error": None
        }

    return result


def add_deliverable_link(project_folder: str, task_id: str, deliverable_path: str) -> Dict:
    """
    Add deliverable link to task.

    Args:
        project_folder: Path to project folder (backward compat)
        task_id: Task ID
        deliverable_path: Path to deliverable file/document

    Returns:
        {"success": bool, "error": str|None}
    """
    task_path = find_task_by_id(task_id)
    if not task_path:
        return {
            "success": False,
            "error": f"Task not found: {task_id}"
        }

    return _add_deliverable_link(task_path, deliverable_path)


if __name__ == "__main__":
    # Test
    print("=== Vault Task Writer Test ===\n")

    print("1. Listing existing tasks...")
    result = read_tasks("work/ronik")
    print(f"   Count: {result['count']}")
    if result['tasks']:
        for tid, task in list(result['tasks'].items())[:3]:
            print(f"   - [{tid}] {task.get('title', 'N/A')} ({task.get('status', '?')})")

    print("\nTest complete")
