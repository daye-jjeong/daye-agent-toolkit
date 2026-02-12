#!/usr/bin/env python3
"""
Deliverable Detection & Validation
Extract deliverables from work output and validate accessibility
"""

import re
import sys
from pathlib import Path
from typing import List, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.task_io import is_accessible_path


def extract_deliverables(text: str, file_paths: List[str] = None) -> List[Dict]:
    """
    Extract deliverables from subagent output

    Args:
        text: Subagent final report or output
        file_paths: List of file paths created during work

    Returns:
        List of deliverables:
        [
            {"type": "vault_page", "url": "path/to/file.md", "verified": False},
            {"type": "file", "url": "path/to/file.md", "verified": False},
        ]
    """
    deliverables = []

    # Pattern 1: Wiki-links (Obsidian)
    wikilink_pattern = r"\[\[([^\]]+)\]\]"
    wikilinks = re.findall(wikilink_pattern, text)
    for link in wikilinks:
        deliverables.append({
            "type": "vault_page",
            "url": f"[[{link}]]",
            "verified": False,
            "source": "wiki_link"
        })

    # Pattern 2: HTTP/HTTPS URLs
    url_pattern = r"(https?://[^\s\)]+)"
    urls = re.findall(url_pattern, text)
    for url in urls:
        deliverables.append({
            "type": "web_url",
            "url": url,
            "verified": False,
            "source": "extracted_from_text"
        })

    # Pattern 3: Markdown file links
    md_file_pattern = r"\[([^\]]+)\]\(([^)]+\.md)\)"
    md_files = re.findall(md_file_pattern, text)
    for title, path in md_files:
        deliverables.append({
            "type": "markdown_file",
            "url": path,
            "verified": False,
            "title": title,
            "source": "markdown_link"
        })

    # Pattern 4: Vault file paths (~/openclaw/vault/...)
    vault_pattern = r"(~/openclaw/vault/[^\s\)]+)"
    vault_paths = re.findall(vault_pattern, text)
    for vpath in vault_paths:
        if vpath not in [d["url"] for d in deliverables]:
            deliverables.append({
                "type": "vault_file",
                "url": vpath,
                "verified": False,
                "source": "vault_path"
            })

    # Pattern 5: Explicit file paths
    if file_paths:
        for path in file_paths:
            deliverables.append({
                "type": "file",
                "url": path,
                "verified": False,
                "source": "explicit_file_path"
            })

    # Pattern 6: Look for deliverables section in Korean task bodies
    deliverable_section_pattern = r"## 산출물\s*\n(.*?)(?=\n##|$)"
    deliverable_section_match = re.search(deliverable_section_pattern, text, re.DOTALL)
    if deliverable_section_match:
        section_content = deliverable_section_match.group(1)
        # Extract paths/URLs from this section
        section_urls = re.findall(r"(https?://[^\s\)]+)", section_content)
        section_wikilinks = re.findall(r"\[\[([^\]]+)\]\]", section_content)
        section_paths = re.findall(r"(~/[^\s\)]+|/[^\s\)]+\.(?:md|pdf|csv|txt))", section_content)

        existing_urls = {d["url"] for d in deliverables}

        for url in section_urls:
            if url not in existing_urls:
                deliverables.append({
                    "type": "deliverable_section_url",
                    "url": url,
                    "verified": False,
                    "source": "deliverable_section"
                })

        for link in section_wikilinks:
            wiki_url = f"[[{link}]]"
            if wiki_url not in existing_urls:
                deliverables.append({
                    "type": "deliverable_section_wikilink",
                    "url": wiki_url,
                    "verified": False,
                    "source": "deliverable_section"
                })

        for path in section_paths:
            if path not in existing_urls:
                deliverables.append({
                    "type": "deliverable_section_file",
                    "url": path,
                    "verified": False,
                    "source": "deliverable_section"
                })

    return deliverables


def check_deliverables(
    session_id: str,
    final_output: str,
    file_paths: List[str] = None
) -> Dict:
    """
    Check if deliverables exist and are accessible

    Args:
        session_id: Session identifier
        final_output: Subagent final report
        file_paths: Optional list of created files

    Returns:
        {
            "has_deliverables": bool,
            "all_accessible": bool,
            "deliverables": List[Dict],
            "validation": Dict,
            "action_required": str | None
        }
    """
    from .validator import validate_deliverables

    # Extract deliverables
    deliverables = extract_deliverables(final_output, file_paths)

    if not deliverables:
        return {
            "has_deliverables": False,
            "all_accessible": False,
            "deliverables": [],
            "validation": {"all_accessible": False, "issues": ["No deliverables found"]},
            "action_required": "upload_required"
        }

    # Validate accessibility
    validation = validate_deliverables(deliverables)

    # Determine action required
    action_required = None
    if not validation["all_accessible"]:
        action_required = "upload_required"

    return {
        "has_deliverables": True,
        "all_accessible": validation["all_accessible"],
        "deliverables": deliverables,
        "validation": validation,
        "action_required": action_required
    }


def detect_created_files(work_dir: Path, before_snapshot: List[Path] = None) -> List[str]:
    """
    Detect newly created files in deliverable directories

    Args:
        work_dir: Working directory (e.g., /Users/dayejeong/openclaw)
        before_snapshot: List of files before work started

    Returns:
        List of newly created file paths
    """
    deliverable_dirs = [
        work_dir / "docs",
        work_dir / "reports",
        work_dir / "guides",
        work_dir / "output",
    ]

    current_files = []
    for dir_path in deliverable_dirs:
        if dir_path.exists():
            current_files.extend(dir_path.rglob("*.md"))
            current_files.extend(dir_path.rglob("*.pdf"))
            current_files.extend(dir_path.rglob("*.csv"))

    if before_snapshot:
        new_files = [f for f in current_files if f not in before_snapshot]
    else:
        # If no snapshot, consider files modified in last hour
        from datetime import datetime, timedelta
        one_hour_ago = datetime.now().timestamp() - 3600
        new_files = [f for f in current_files if f.stat().st_mtime > one_hour_ago]

    return [str(f) for f in new_files]


if __name__ == "__main__":
    # Test deliverable extraction
    print("=== Deliverable Extraction Test ===\n")

    test_output = """
    ## 작업 완료

    분석 리포트를 작성했습니다.

    ## 산출물
    - vault 페이지: [[ai-trends-report]]
    - 웹 링크: https://example.com/report.pdf
    - 로컬 문서: [가이드](./docs/guide.md)
    - vault 경로: ~/openclaw/vault/projects/work/ronik/deliverables/report.md

    ## 참고
    추가 자료는 /Users/dayejeong/openclaw/output/data.csv 참조
    """

    deliverables = extract_deliverables(test_output, ["/Users/dayejeong/openclaw/output/data.csv"])

    print(f"Found {len(deliverables)} deliverables:\n")
    for d in deliverables:
        print(f"  Type: {d['type']}")
        print(f"  URL: {d['url']}")
        print(f"  Source: {d['source']}")
        print()

    # Test check_deliverables
    result = check_deliverables("test-session", test_output)
    print(f"Has deliverables: {result['has_deliverables']}")
    print(f"All accessible: {result['all_accessible']}")
    print(f"Action required: {result['action_required']}")
