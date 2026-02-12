#!/usr/bin/env python3
"""
Task Property Helpers
Auto-update Task properties according to POLICY.md.
Storage: Obsidian vault (~/clawd/memory/projects/).
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.task_io import (
    find_task_by_id,
    read_task,
    update_task,
    today,
    now,
)


def set_task_start_date(task_id: str) -> dict:
    """
    Set Start Date to current datetime when work begins.

    Per POLICY.md: Start Date = when first action begins (NOT at creation)

    Args:
        task_id: Task ID (e.g., "t-ronik-001")

    Returns:
        {
            "success": bool,
            "start_date": str (ISO 8601) | None,
            "error": str | None
        }
    """
    try:
        task_path = find_task_by_id(task_id)
        if not task_path:
            return {
                "success": False,
                "start_date": None,
                "error": f"Task not found: {task_id}",
                "skipped": False
            }

        result = read_task(task_path)
        if not result["success"]:
            return {
                "success": False,
                "start_date": None,
                "error": result["error"],
                "skipped": False
            }

        fm = result["frontmatter"]

        # Check if Start Date already set
        if fm.get("start"):
            return {
                "success": True,
                "start_date": str(fm["start"]),
                "error": None,
                "skipped": True,
                "reason": "Start Date already set"
            }

        # Set Start Date to now
        now_iso = now()
        update_result = update_task(task_path, {"start": now_iso})

        if update_result["success"]:
            return {
                "success": True,
                "start_date": now_iso,
                "error": None,
                "skipped": False
            }
        else:
            return {
                "success": False,
                "start_date": None,
                "error": update_result["error"],
                "skipped": False
            }

    except Exception as e:
        return {
            "success": False,
            "start_date": None,
            "error": str(e),
            "skipped": False
        }


def set_task_owner(task_id: str, owner_name: str = "daye") -> dict:
    """
    Set Task owner/assignee (CRITICAL: always required).

    Args:
        task_id: Task ID (e.g., "t-ronik-001")
        owner_name: Owner name (default: "daye")

    Returns:
        {
            "success": bool,
            "owner": str,
            "error": str | None
        }
    """
    try:
        task_path = find_task_by_id(task_id)
        if not task_path:
            return {
                "success": False,
                "owner": None,
                "error": f"Task not found: {task_id}"
            }

        result = update_task(task_path, {"owner": owner_name})

        return {
            "success": result["success"],
            "owner": owner_name if result["success"] else None,
            "error": result.get("error")
        }

    except Exception as e:
        return {
            "success": False,
            "owner": None,
            "error": str(e)
        }


def set_task_priority(task_id: str, priority: str = "medium") -> dict:
    """
    Set Task priority (default: medium if not set).

    Args:
        task_id: Task ID (e.g., "t-ronik-001")
        priority: Priority value (high/medium/low)

    Returns:
        {
            "success": bool,
            "priority": str,
            "error": str | None
        }
    """
    try:
        task_path = find_task_by_id(task_id)
        if not task_path:
            return {
                "success": False,
                "priority": None,
                "error": f"Task not found: {task_id}",
                "skipped": False
            }

        result = read_task(task_path)
        if not result["success"]:
            return {
                "success": False,
                "priority": None,
                "error": result["error"],
                "skipped": False
            }

        fm = result["frontmatter"]

        # Check if Priority already set
        if fm.get("priority"):
            return {
                "success": True,
                "priority": fm["priority"],
                "error": None,
                "skipped": True,
                "reason": "Priority already set"
            }

        update_result = update_task(task_path, {"priority": priority})

        return {
            "success": update_result["success"],
            "priority": priority if update_result["success"] else None,
            "error": update_result.get("error"),
            "skipped": False
        }

    except Exception as e:
        return {
            "success": False,
            "priority": None,
            "error": str(e),
            "skipped": False
        }


def ensure_task_defaults(task_id: str, owner: str = "daye", priority: str = "medium",
                         set_start_date: bool = False) -> dict:
    """
    Ensure all required Task properties are set with defaults.

    Args:
        task_id: Task ID (e.g., "t-ronik-001")
        owner: Owner name (default: "daye")
        priority: Priority (default: "medium")
        set_start_date: Whether to set Start Date (only if work is starting)

    Returns:
        {
            "success": bool,
            "results": {
                "owner": dict,
                "priority": dict,
                "start_date": dict | None
            },
            "error": str | None
        }
    """
    results = {}

    # Set Owner (CRITICAL)
    results["owner"] = set_task_owner(task_id, owner)

    # Set Priority (if not set)
    results["priority"] = set_task_priority(task_id, priority)

    # Set Start Date (only if requested)
    if set_start_date:
        results["start_date"] = set_task_start_date(task_id)
    else:
        results["start_date"] = {"skipped": True, "reason": "Not starting work yet"}

    # Check if any critical operation failed
    success = results["owner"]["success"] and results["priority"]["success"]

    return {
        "success": success,
        "results": results,
        "error": None if success else "Some operations failed (see results)"
    }


if __name__ == "__main__":
    # Test
    import argparse

    parser = argparse.ArgumentParser(description="Task property helpers")
    parser.add_argument("task_id", help="Task ID (e.g., t-ronik-001)")
    parser.add_argument("--owner", default="daye", help="Owner name")
    parser.add_argument("--priority", default="medium", help="Priority (high/medium/low)")
    parser.add_argument("--start-work", action="store_true", help="Set Start Date (work beginning)")

    args = parser.parse_args()

    result = ensure_task_defaults(
        args.task_id,
        owner=args.owner,
        priority=args.priority,
        set_start_date=args.start_work
    )

    status_icon = "OK" if result['success'] else "FAIL"
    print(f"\n{status_icon} Task defaults updated:")
    for key, value in result["results"].items():
        s = "OK" if value.get("success", False) else "SKIP" if value.get("skipped") else "FAIL"
        print(f"  {s} {key}: {value}")
