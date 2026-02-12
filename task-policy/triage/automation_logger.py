#!/usr/bin/env python3
"""
Automation Logger - Record cron/automation execution to Obsidian vault.
Ensures all automated work leaves a trace.
Storage: ~/openclaw/vault/projects/ + ~/.clawdbot/guardrails/automation.jsonl
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

# Log file location
LOG_DIR = Path.home() / ".clawdbot" / "guardrails"
AUTOMATION_LOG = LOG_DIR / "automation.jsonl"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.task_io import (
    write_task,
    find_task_by_id,
    update_task,
    read_task,
    today,
    now,
    VAULT_DIR,
    PROJECTS_DIR,
)


def log_automation_run(
    automation_name: str,
    status: str,  # "success" | "failure" | "partial"
    summary: str,
    message_id: Optional[str] = None,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Log automation execution to local JSONL + vault automation log.

    Args:
        automation_name: Name of cron job or automation (e.g., "Morning Brief")
        status: "success" | "failure" | "partial"
        summary: Brief summary of what was done
        message_id: Telegram message ID (if message was sent)
        error: Error message (if failed)
        metadata: Additional context (dict)

    Returns:
        {
            "success": bool,
            "log_path": str | None,
            "error": str | None
        }
    """
    try:
        timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        status_icon = {"success": "OK", "failure": "FAIL", "partial": "PARTIAL"}.get(status, "?")

        # 1. Append to JSONL log
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "automation": automation_name,
            "status": status,
            "summary": summary,
            "message_id": message_id,
            "error": error,
            "metadata": metadata or {}
        }

        with open(AUTOMATION_LOG, "a") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        # 2. Append to vault daily log (optional: ~/openclaw/vault/projects/goals/daily/)
        daily_log_dir = PROJECTS_DIR / "goals" / "daily"
        daily_log_file = daily_log_dir / f"{today()}.md"

        if daily_log_file.exists():
            # Append automation entry to daily log
            current = daily_log_file.read_text(encoding="utf-8")
            automation_entry = f"\n- **[{timestamp}]** {status_icon} {automation_name}: {summary}"
            if error:
                automation_entry += f" (Error: {error})"

            if "## Automation Log" not in current:
                current += f"\n\n## Automation Log\n{automation_entry}\n"
            else:
                current = current.replace(
                    "## Automation Log",
                    f"## Automation Log\n{automation_entry}",
                    1
                )
            daily_log_file.write_text(current, encoding="utf-8")

        return {
            "success": True,
            "log_path": str(AUTOMATION_LOG),
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "log_path": None,
            "error": str(e)
        }


def get_recent_logs(limit: int = 10) -> Dict:
    """
    Retrieve recent automation logs.

    Args:
        limit: Maximum number of log entries to return

    Returns:
        {
            "success": bool,
            "logs": List[Dict],
            "error": str | None
        }
    """
    try:
        if not AUTOMATION_LOG.exists():
            return {
                "success": True,
                "logs": [],
                "error": None,
                "message": "No automation logs yet"
            }

        logs = []
        with open(AUTOMATION_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    logs.append(json.loads(line))

        # Return last N entries
        return {
            "success": True,
            "logs": logs[-limit:],
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "logs": [],
            "error": str(e)
        }


def generate_automation_report(hours: int = 24) -> str:
    """
    Generate automation run summary report.

    Args:
        hours: Look-back period

    Returns:
        Markdown formatted report
    """
    if not AUTOMATION_LOG.exists():
        return "## Automation Report\n\nNo automation logs found."

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    logs = []
    with open(AUTOMATION_LOG, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if entry_time > cutoff:
                logs.append(entry)

    if not logs:
        return f"## Automation Report\n\nNo automation runs in last {hours} hours."

    # Count by status
    by_status = {"success": 0, "failure": 0, "partial": 0}
    for log in logs:
        s = log.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    report = f"""## Automation Report
**Period:** Last {hours} hours
**Total Runs:** {len(logs)}

### Summary
- OK: {by_status.get('success', 0)}
- FAIL: {by_status.get('failure', 0)}
- PARTIAL: {by_status.get('partial', 0)}

### Recent Events
"""
    for log in logs[-10:]:
        ts = log["timestamp"][:16]
        status = log.get("status", "?")
        name = log.get("automation", "unknown")
        summary = log.get("summary", "")
        icon = {"success": "OK", "failure": "FAIL", "partial": "PARTIAL"}.get(status, "?")
        report += f"- **{ts}** [{icon}] {name}: {summary}\n"

    return report


if __name__ == "__main__":
    # Test
    import argparse

    parser = argparse.ArgumentParser(description="Automation Logger")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Log command
    log_parser = subparsers.add_parser("log", help="Log automation run")
    log_parser.add_argument("name", help="Automation name")
    log_parser.add_argument("status", choices=["success", "failure", "partial"])
    log_parser.add_argument("summary", help="Summary of execution")
    log_parser.add_argument("--message-id", help="Telegram message ID")
    log_parser.add_argument("--error", help="Error message (if failed)")

    # List command
    list_parser = subparsers.add_parser("list", help="List recent logs")
    list_parser.add_argument("--limit", type=int, default=10, help="Number of logs to show")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("--hours", type=int, default=24, help="Look-back hours")

    args = parser.parse_args()

    if args.command == "log":
        result = log_automation_run(
            automation_name=args.name,
            status=args.status,
            summary=args.summary,
            message_id=args.message_id,
            error=args.error
        )

        if result["success"]:
            print(f"Logged to: {result['log_path']}")
        else:
            print(f"Failed: {result['error']}")

    elif args.command == "list":
        result = get_recent_logs(limit=args.limit)

        if result["success"]:
            print(f"Recent Automation Logs ({len(result['logs'])}):\n")
            for log in result["logs"]:
                ts = log["timestamp"][:16]
                status = log.get("status", "?")
                name = log.get("automation", "unknown")
                print(f"  [{status}] {ts} {name}: {log.get('summary', '')}")
        else:
            print(f"Failed: {result['error']}")

    elif args.command == "report":
        report = generate_automation_report(hours=args.hours)
        print(report)
