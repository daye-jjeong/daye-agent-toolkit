#!/usr/bin/env python3
"""
Notion Deliverable Uploader
Auto-upload deliverables to Notion with Korean-by-default + footer policy
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from skills.notion.client import NotionClient
from skills.notion.markdown_converter import markdown_to_blocks


# Footer template (Korean by default)
FOOTER_TEMPLATE_KO = """
---

**생성 정보**
- 생성일: {timestamp}
- AI 모델: {model}
- 세션: {session_id}
- 원본 Task: [링크]({task_url})
"""

FOOTER_TEMPLATE_EN = """
---

**Generation Info**
- Created: {timestamp}
- AI Model: {model}
- Session: {session_id}
- Source Task: [Link]({task_url})
"""


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
    Upload a deliverable file to Notion as a child page
    
    Args:
        file_path: Path to deliverable file (.md, .txt, etc.)
        task_url: Parent Task URL
        task_id: Parent Task page ID
        session_id: Session identifier
        model: AI model used (for footer)
        language: "ko" (default) or "en"
        workspace: Notion workspace ("personal" or "ronik")
        
    Returns:
        {
            "success": bool,
            "page_url": str | None,
            "page_id": str | None,
            "error": str | None
        }
    """
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        return {
            "success": False,
            "page_url": None,
            "page_id": None,
            "error": f"File not found: {file_path}"
        }
    
    # Read file content
    try:
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {
            "success": False,
            "page_url": None,
            "page_id": None,
            "error": f"Failed to read file: {e}"
        }
    
    # Extract title from filename or first line
    title = file_path_obj.stem
    if content.startswith("# "):
        first_line = content.split("\n")[0]
        title = first_line.replace("# ", "").strip()
    
    # Add footer
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    footer = (FOOTER_TEMPLATE_KO if language == "ko" else FOOTER_TEMPLATE_EN).format(
        timestamp=timestamp,
        model=model,
        session_id=session_id,
        task_url=task_url
    )
    
    full_content = content + "\n" + footer
    
    # Convert markdown to Notion blocks
    try:
        blocks = markdown_to_blocks(full_content)
    except Exception as e:
        return {
            "success": False,
            "page_url": None,
            "page_id": None,
            "error": f"Failed to convert markdown: {e}"
        }
    
    # Create Notion page
    try:
        notion = NotionClient(workspace=workspace)
        
        # Create child page under Task
        page = notion.create_page(
            parent={"page_id": task_id.replace("-", "")},
            properties={
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            }
        )
        
        page_id = page["id"]
        page_url = page.get("url", f"https://notion.so/{page_id}")
        
        # Append blocks in batches (Notion limit: 100 blocks/request)
        notion.append_blocks_batch(page_id, blocks)
        
        return {
            "success": True,
            "page_url": page_url,
            "page_id": page_id,
            "error": None
        }
    
    except Exception as e:
        return {
            "success": False,
            "page_url": None,
            "page_id": None,
            "error": f"Notion API error: {e}"
        }


def update_task_deliverables_section(
    task_id: str,
    deliverable_urls: List[str],
    workspace: str = "personal"
) -> Dict:
    """
    Update Task's '산출물' section with deliverable URLs
    
    Args:
        task_id: Task page ID
        deliverable_urls: List of deliverable URLs to add
        workspace: Notion workspace
        
    Returns:
        {
            "success": bool,
            "updated_count": int,
            "error": str | None
        }
    """
    try:
        notion = NotionClient(workspace=workspace)
        
        # Fetch current page blocks
        page_blocks = notion.get(f"/v1/blocks/{task_id}/children")
        
        # Find 산출물 section
        deliverable_block_id = None
        for block in page_blocks.get("results", []):
            if block.get("type") == "heading_2":
                heading_text = block["heading_2"]["rich_text"]
                if heading_text and "산출물" in heading_text[0]["text"]["content"]:
                    deliverable_block_id = block["id"]
                    break
        
        # Create new blocks for deliverables
        new_blocks = []
        for url in deliverable_urls:
            new_blocks.append({
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "- "}},
                        {"type": "text", "text": {"content": url, "link": {"url": url}}}
                    ]
                }
            })
        
        if deliverable_block_id:
            # Append after existing 산출물 section
            notion.append_blocks(deliverable_block_id, new_blocks)
        else:
            # Create 산출물 section
            section_blocks = [{
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "산출물"}}]}
            }] + new_blocks
            
            notion.append_blocks(task_id, section_blocks)
        
        return {
            "success": True,
            "updated_count": len(deliverable_urls),
            "error": None
        }
    
    except Exception as e:
        return {
            "success": False,
            "updated_count": 0,
            "error": f"Failed to update Task: {e}"
        }


if __name__ == "__main__":
    # Test (requires valid test file and task)
    print("=== Notion Uploader Test (Manual) ===\n")
    print("Create a test markdown file and update the paths below to test:")
    print("  test_file = Path('./test_deliverable.md')")
    print("  test_task_id = 'your-task-id'")
    print()
    print("Then run: python3 notion_uploader.py")
