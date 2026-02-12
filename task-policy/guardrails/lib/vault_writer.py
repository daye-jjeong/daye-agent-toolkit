#!/usr/bin/env python3
"""
Vault Deliverable Writer
Save deliverables to Obsidian vault with Korean-by-default + footer policy.
Obsidian vault 기반 산출물 저장.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.task_io import (
    save_deliverable,
    read_task,
    add_deliverable_link,
    parse_frontmatter,
    format_frontmatter,
)


def upload_deliverable_to_notion(
    file_path: str,
    task_url: str,
    task_id: str,
    session_id: str,
    model: str = "unknown",
    language: str = "ko",
    workspace: str = "personal"
) -> Dict:
    """
    Save a deliverable file to the Obsidian vault as a linked document.
    Backward-compatible API name (was Notion uploader).

    Args:
        file_path: Path to deliverable file (.md, .txt, etc.)
        task_url: Task file path or task ID
        task_id: Task ID (e.g., "t-ronik-001")
        session_id: Session identifier
        model: AI model used (for footer)
        language: "ko" (default) or "en"
        workspace: Ignored (was Notion workspace, kept for API compat)

    Returns:
        {
            "success": bool,
            "page_url": str | None,  -- vault path
            "page_id": str | None,   -- task_id
            "error": str | None
        }
    """
    # Resolve task file path
    task_filepath = _resolve_task_path(task_url, task_id)
    if not task_filepath:
        return {
            "success": False,
            "page_url": None,
            "page_id": None,
            "error": f"Task not found: {task_url} / {task_id}"
        }

    result = save_deliverable(
        file_path=file_path,
        task_filepath=task_filepath,
        session_id=session_id,
        model=model,
        language=language
    )

    if result["success"]:
        return {
            "success": True,
            "page_url": result["vault_path"],
            "page_id": task_id,
            "error": None
        }
    else:
        return {
            "success": False,
            "page_url": None,
            "page_id": None,
            "error": result["error"]
        }


def update_task_deliverables_section(
    task_id: str,
    deliverable_urls: List[str],
    workspace: str = "personal"
) -> Dict:
    """
    Update task's deliverables section with links.
    Backward-compatible API (was Notion block update).

    Args:
        task_id: Task ID (e.g., "t-ronik-001")
        deliverable_urls: List of deliverable paths to add
        workspace: Ignored (kept for API compat)

    Returns:
        {
            "success": bool,
            "updated_count": int,
            "error": str | None
        }
    """
    from scripts.task_io import find_task_by_id

    task_filepath = find_task_by_id(task_id)
    if not task_filepath:
        return {
            "success": False,
            "updated_count": 0,
            "error": f"Task not found: {task_id}"
        }

    updated = 0
    last_error = None

    for url in deliverable_urls:
        result = add_deliverable_link(task_filepath, url)
        if result["success"]:
            updated += 1
        else:
            last_error = result["error"]

    return {
        "success": updated > 0 or not deliverable_urls,
        "updated_count": updated,
        "error": last_error
    }


def _resolve_task_path(task_url: str, task_id: str) -> str:
    """Resolve task reference to file path."""
    from scripts.task_io import find_task_by_id, validate_task_path

    # Try task_url as direct path
    if task_url:
        p = Path(task_url)
        if p.exists() and p.suffix == ".md":
            return str(p)

    # Try task_id lookup
    if task_id:
        found = find_task_by_id(task_id)
        if found:
            return found

    # Try task_url as ID
    if task_url:
        found = find_task_by_id(task_url)
        if found:
            return found

    return None


if __name__ == "__main__":
    print("=== Vault Writer Test (Manual) ===\n")
    print("Create a test markdown file and update the paths below to test:")
    print("  test_file = Path('./test_deliverable.md')")
    print("  test_task_id = 't-ronik-001'")
    print()
    print("Then run: python3 vault_writer.py")
