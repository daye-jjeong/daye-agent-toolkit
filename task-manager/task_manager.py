#!/usr/bin/env python3
"""
Task Manager - Notion Task Management Skill
Manages Tasks and Projects with standardized templates and progress tracking.

Commands:
- create: Create new Task with template
- update-progress: Append progress checkpoint (internal log)
- add-deliverable: Add deliverable version to Task
- close: Mark Task as Done with completion summary
- dry-run: Preview Task creation without executing
"""

import sys
import json
import argparse
import os
from datetime import datetime
import urllib.request
import urllib.parse

# Constants
NOTION_API_VERSION = "2022-06-28"
NOTION_KEY_PATH = os.path.expanduser("~/.config/notion/api_key_daye_personal")
TASKS_DB_ID = "8e0e8902-0c60-4438-8bbf-abe10d474b9b"
PROJECTS_DB_ID = "92f50099-1567-4f34-9827-c197238971f6"

# Template strings
TASK_BODY_TEMPLATE = """# {name}

## 📋 Context
**Purpose:** {purpose}
**Part of:** {project_url}
**Requested by:** {requester}
**Created:** {created_at}

---

## 🎯 Goals & Acceptance Criteria
**Goal:** {goal}

**Acceptance Criteria:**
{acceptance_criteria}

---

## 🗂️ Task Breakdown
{task_breakdown}

---

## 🔍 Progress Log (Internal)
*Chronological checkpoints during execution. NOT user-facing.*

### [{timestamp}] Started
- Task created and initialized

---

## 🎨 Deliverables
*All outputs from this task. MUST be accessible (no local-only paths).*

---

## 💡 Decisions & Trade-offs
*Key decisions made during execution.*

---

## 🔗 Related Links
{related_links}

---

## ✅ Completion Summary
*To be filled when Status → Done*
"""


def log(message, level="INFO"):
    """Simple logging to stderr"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", file=sys.stderr)


def load_notion_key():
    """Load Notion API key from config file"""
    try:
        with open(NOTION_KEY_PATH, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        log(f"Notion API key not found at {NOTION_KEY_PATH}", "ERROR")
        sys.exit(1)


def notion_request(method, endpoint, data=None):
    """Make Notion API request"""
    api_key = load_notion_key()
    url = f"https://api.notion.com/v1/{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json"
    }
    
    req_data = json.dumps(data).encode('utf-8') if data else None
    
    try:
        request = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        log(f"Notion API error: {e.code} - {error_body}", "ERROR")
        return None
    except Exception as e:
        log(f"Request failed: {str(e)}", "ERROR")
        return None


def get_kst_timestamp():
    """Get current timestamp in KST"""
    # Note: Using naive datetime since we're formatting as string
    # In production, use pytz or dateutil for proper timezone handling
    return datetime.now().strftime("%Y-%m-%d %H:%M KST")


def create_task_body(name, purpose, project_url, goal, acceptance_criteria, task_breakdown, related_links="", requester="User"):
    """Generate Task body from template"""
    criteria_list = "\n".join([f"- [ ] {c}" for c in acceptance_criteria])
    breakdown_list = "\n".join([f"{i+1}. {step}" for i, step in enumerate(task_breakdown)])
    
    return TASK_BODY_TEMPLATE.format(
        name=name,
        purpose=purpose,
        project_url=project_url or "N/A",
        requester=requester,
        created_at=get_kst_timestamp(),
        goal=goal,
        acceptance_criteria=criteria_list,
        task_breakdown=breakdown_list,
        timestamp=get_kst_timestamp(),
        related_links=related_links or "N/A"
    )


def create_task(args):
    """Create new Task in Notion with template"""
    log(f"Creating Task: {args.name}")
    
    # Build properties
    properties = {
        "Name": {
            "title": [{"text": {"content": args.name}}]
        },
        "Status": {
            "status": {"name": "In Progress"}
        },
        "Start Date": {
            "date": {"start": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")}
        }
    }
    
    # Add optional properties
    if args.priority:
        properties["Priority"] = {"select": {"name": args.priority}}
    
    if args.project_id:
        properties["Project"] = {"relation": [{"id": args.project_id}]}
    
    if args.area:
        properties["Area"] = {"select": {"name": args.area}}
    
    if args.tags:
        properties["Tags"] = {"multi_select": [{"name": tag} for tag in args.tags.split(",")]}
    
    # Build page body
    acceptance_criteria = args.acceptance_criteria.split("|") if args.acceptance_criteria else ["To be defined"]
    task_breakdown = args.task_breakdown.split("|") if args.task_breakdown else ["To be defined"]
    
    body_content = create_task_body(
        name=args.name,
        purpose=args.purpose or "To be defined",
        project_url=args.project_url or "",
        goal=args.goal or "To be defined",
        acceptance_criteria=acceptance_criteria,
        task_breakdown=task_breakdown,
        related_links=args.related_links or ""
    )
    
    # Convert markdown to Notion blocks (simplified - heading + paragraph)
    blocks = []
    for line in body_content.split('\n'):
        if line.strip().startswith('# '):
            # Heading
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": line.strip('# ')}}]
                }
            })
        elif line.strip().startswith('## '):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": line.strip('## ')}}]
                }
            })
        elif line.strip().startswith('### '):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": line.strip('### ')}}]
                }
            })
        elif line.strip():
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line}}]
                }
            })
    
    # Dry run?
    if args.dry_run:
        log("DRY RUN: Would create Task with properties:", "INFO")
        print(json.dumps(properties, indent=2))
        log("Body preview (first 500 chars):", "INFO")
        print(body_content[:500])
        return
    
    # Create page
    payload = {
        "parent": {"database_id": TASKS_DB_ID},
        "properties": properties,
        "children": blocks[:100]  # Notion API limit: 100 blocks per request
    }
    
    result = notion_request("POST", "pages", payload)
    
    if result:
        task_url = result.get("url")
        task_id = result.get("id")
        log(f"✅ Task created: {task_url}", "INFO")
        print(json.dumps({"status": "success", "task_id": task_id, "url": task_url}, indent=2))
    else:
        log("❌ Failed to create Task", "ERROR")
        sys.exit(1)


def update_progress(args):
    """Append progress entry to Task's Progress Log"""
    log(f"Updating progress for Task: {args.task_id}")
    
    # Fetch existing page blocks
    blocks_response = notion_request("GET", f"blocks/{args.task_id}/children")
    
    if not blocks_response:
        log("Failed to fetch Task blocks", "ERROR")
        sys.exit(1)
    
    # Find Progress Log section (heading_2 with "Progress Log")
    progress_section_idx = None
    blocks = blocks_response.get("results", [])
    
    for i, block in enumerate(blocks):
        if block.get("type") == "heading_2":
            text_content = block.get("heading_2", {}).get("rich_text", [])
            if text_content and "Progress Log" in text_content[0].get("text", {}).get("content", ""):
                progress_section_idx = i
                break
    
    if progress_section_idx is None:
        log("Progress Log section not found in Task", "ERROR")
        sys.exit(1)
    
    # Create new progress entry block
    timestamp = get_kst_timestamp()
    new_entry = {
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": f"[{timestamp}] {args.status or 'Update'}"}}]
        }
    }
    
    entry_content = {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": args.entry}}]
        }
    }
    
    # Append after Progress Log heading
    # Note: Notion API requires block_id of the parent to append
    # Simplified: append to page (not ideal, but works)
    
    if args.dry_run:
        log("DRY RUN: Would append progress entry:", "INFO")
        print(f"[{timestamp}] {args.status or 'Update'}\n{args.entry}")
        return
    
    # Append blocks
    append_payload = {"children": [new_entry, entry_content]}
    result = notion_request("PATCH", f"blocks/{args.task_id}/children", append_payload)
    
    if result:
        log("✅ Progress updated", "INFO")
        print(json.dumps({"status": "success", "message": "Progress log updated"}))
    else:
        log("❌ Failed to update progress", "ERROR")
        sys.exit(1)


def add_deliverable(args):
    """Add deliverable entry to Task's Deliverables section"""
    log(f"Adding deliverable to Task: {args.task_id}")
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    deliverable_entry = f"- **{args.version}** ([{timestamp}]): [{args.url}]({args.url})\n  - Summary: {args.summary}\n  - Format: {args.format or 'Notion page'}"
    
    if args.dry_run:
        log("DRY RUN: Would add deliverable:", "INFO")
        print(deliverable_entry)
        return
    
    # Append to Deliverables section (simplified: append to page)
    deliverable_block = {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": deliverable_entry}}]
        }
    }
    
    append_payload = {"children": [deliverable_block]}
    result = notion_request("PATCH", f"blocks/{args.task_id}/children", append_payload)
    
    if result:
        log("✅ Deliverable added", "INFO")
        print(json.dumps({"status": "success", "message": "Deliverable added"}))
    else:
        log("❌ Failed to add deliverable", "ERROR")
        sys.exit(1)


def close_task(args):
    """Mark Task as Done and add completion summary"""
    log(f"Closing Task: {args.task_id}")
    
    # Update Status property
    properties = {
        "Status": {"status": {"name": "Done"}}
    }
    
    if args.dry_run:
        log("DRY RUN: Would close Task with summary:", "INFO")
        print(args.summary)
        return
    
    # Update properties
    result = notion_request("PATCH", f"pages/{args.task_id}", {"properties": properties})
    
    if not result:
        log("❌ Failed to update Task status", "ERROR")
        sys.exit(1)
    
    # Add completion summary to body
    timestamp = get_kst_timestamp()
    summary_blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "✅ Completion Summary"}}]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": f"**Completed:** {timestamp}"}}]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": args.summary}}]
            }
        }
    ]
    
    append_result = notion_request("PATCH", f"blocks/{args.task_id}/children", {"children": summary_blocks})
    
    if append_result:
        log("✅ Task closed successfully", "INFO")
        print(json.dumps({"status": "success", "message": "Task closed"}))
    else:
        log("⚠️ Status updated but failed to add completion summary", "WARN")


def main():
    parser = argparse.ArgumentParser(description="Task Manager - Notion Task Management")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create new Task")
    create_parser.add_argument("--name", required=True, help="Task name")
    create_parser.add_argument("--purpose", help="Task purpose")
    create_parser.add_argument("--goal", help="Task goal")
    create_parser.add_argument("--acceptance-criteria", help="Acceptance criteria (pipe-separated)")
    create_parser.add_argument("--task-breakdown", help="Task steps (pipe-separated)")
    create_parser.add_argument("--project-id", help="Project ID to link")
    create_parser.add_argument("--project-url", help="Project URL for reference")
    create_parser.add_argument("--priority", choices=["High", "Medium", "Low"], help="Priority")
    create_parser.add_argument("--area", help="Work area")
    create_parser.add_argument("--tags", help="Comma-separated tags")
    create_parser.add_argument("--related-links", help="Related links")
    create_parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    
    # Update progress command
    progress_parser = subparsers.add_parser("update-progress", help="Update progress log")
    progress_parser.add_argument("--task-id", required=True, help="Task ID")
    progress_parser.add_argument("--entry", required=True, help="Progress entry")
    progress_parser.add_argument("--status", help="Status label (e.g., 'In Progress', 'Blocked')")
    progress_parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    
    # Add deliverable command
    deliverable_parser = subparsers.add_parser("add-deliverable", help="Add deliverable")
    deliverable_parser.add_argument("--task-id", required=True, help="Task ID")
    deliverable_parser.add_argument("--version", required=True, help="Version (e.g., v1, v2)")
    deliverable_parser.add_argument("--url", required=True, help="Deliverable URL")
    deliverable_parser.add_argument("--summary", required=True, help="Brief summary")
    deliverable_parser.add_argument("--format", help="Format (e.g., 'Notion page', 'PDF')")
    deliverable_parser.add_argument("--dry-run", action="store_true", help="Preview without adding")
    
    # Close command
    close_parser = subparsers.add_parser("close", help="Close Task")
    close_parser.add_argument("--task-id", required=True, help="Task ID")
    close_parser.add_argument("--summary", required=True, help="Completion summary")
    close_parser.add_argument("--dry-run", action="store_true", help="Preview without closing")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to command handlers
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
