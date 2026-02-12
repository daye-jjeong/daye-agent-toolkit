#!/usr/bin/env python3
"""
Task Path & Deliverable Validation
Verify Obsidian vault task accessibility and deliverable paths
"""

import re
import sys
from typing import Dict, List
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.task_io import validate_task_path, is_accessible_path


def validate_task_ref(task_ref: str) -> Dict:
    """
    Validate that a task reference (path or ID) is accessible in the vault.

    Args:
        task_ref: Task file path or task ID (e.g., "t-ronik-001")

    Returns:
        {
            "valid": bool,
            "accessible": bool,
            "task_id": str | None,
            "title": str | None,
            "path": str | None,
            "error": str | None
        }
    """
    return validate_task_path(task_ref)


# Keep backward-compatible alias
validate_task_url = validate_task_ref


def is_accessible_url(url: str) -> bool:
    """
    Check if a URL/path is accessible (vault path, URL, or wiki-link).

    Args:
        url: URL or path to check

    Returns:
        True if accessible, False if inaccessible local path
    """
    return is_accessible_path(url)


def validate_deliverables(deliverables: List[Dict]) -> Dict:
    """
    Validate that all deliverables are accessible (not orphaned local paths).

    Args:
        deliverables: List of {"type": str, "url": str, "verified": bool}

    Returns:
        {
            "all_accessible": bool,
            "accessible_count": int,
            "local_count": int,
            "issues": List[str]
        }
    """
    accessible_count = 0
    local_count = 0
    issues = []

    for deliverable in deliverables:
        url = deliverable.get("url", "")

        if is_accessible_path(url):
            accessible_count += 1
            deliverable["verified"] = True
        else:
            local_count += 1
            deliverable["verified"] = False
            issues.append(f"Path not accessible: {url}")

    return {
        "all_accessible": local_count == 0,
        "accessible_count": accessible_count,
        "local_count": local_count,
        "issues": issues
    }


if __name__ == "__main__":
    # Test validation
    print("=== Task Validation Test ===\n")

    test_refs = [
        "t-ronik-001",
        "t-nonexistent-999",
        "/Users/dayejeong/openclaw/report.md",
    ]

    for ref in test_refs:
        print(f"Testing: {ref}")
        result = validate_task_ref(ref)
        print(f"  Valid: {result['valid']}")
        print(f"  Accessible: {result['accessible']}")
        if result.get("title"):
            print(f"  Title: {result['title']}")
        if result.get("error"):
            print(f"  Error: {result['error']}")
        print()
