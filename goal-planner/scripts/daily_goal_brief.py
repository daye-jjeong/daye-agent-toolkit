#!/usr/bin/env python3
"""
Daily Goal Brief - Telegram daily goal briefing script
Reads goal YAML files and sends a formatted summary via Telegram.
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any, Dict, List

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install PyYAML", file=sys.stderr)
    sys.exit(1)

# Configuration
TELEGRAM_GROUP = "-1003242721592"
THREAD_ID = "167"  # 📅 일정/준비 관련 topic

# Path setup
CLAWD_ROOT = Path(__file__).resolve().parent.parent.parent  # openclaw/
VAULT_DIR = CLAWD_ROOT / "vault"
PROJECTS_ROOT = VAULT_DIR / "projects"
GOALS_ROOT = VAULT_DIR / "goals"

# Weekday names in Korean
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


def load_yaml_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load YAML file, handle errors gracefully."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
        return None


def calc_kr_percent(kr: Any) -> Optional[int]:
    """Calculate single key_result completion percentage."""
    if isinstance(kr, str):
        # String-only KR, we can't parse progress
        return None

    if not isinstance(kr, dict):
        return None

    current = str(kr.get("current", "")).strip()
    target = str(kr.get("target", "")).strip()

    if not current or current == "0":
        return 0

    # Text status
    if current in ("완료", "done"):
        return 100
    if current in ("진행중", "진행 중", "in_progress"):
        return 50

    # Numeric extraction
    t_nums = re.findall(r"[\d.]+", target)
    c_nums = re.findall(r"[\d.]+", current)

    if t_nums and c_nums:
        try:
            t = float(t_nums[0])
            c = float(c_nums[0])
            if t > 0:
                return min(100, round(c / t * 100))
        except (ValueError, IndexError):
            return 0

    return 0


def get_kr_display(kr: Any) -> tuple[str, Optional[int]]:
    """Get display text and progress for a key_result."""
    if isinstance(kr, str):
        return kr, None

    if not isinstance(kr, dict):
        return str(kr), None

    description = kr.get("description", "")
    current = kr.get("current", "")
    target = kr.get("target", "")

    # Build display suffix
    suffix = ""
    if target:
        if isinstance(current, int) or (isinstance(current, str) and current.isdigit()):
            suffix = f" ({current}/{target})"
        elif current:
            suffix = f" ({current})"

    percent = calc_kr_percent(kr)
    display_text = f"{description}{suffix}"

    return display_text, percent


def get_kr_icon(percent: Optional[int]) -> str:
    """Get status icon for key_result."""
    if percent is None:
        return "⬜"
    if percent >= 100:
        return "✅"
    if percent > 0:
        return "🔄"
    return "⬜"


def make_progress_bar(percent: int, width: int = 10) -> str:
    """Create a text progress bar."""
    filled = round(percent / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def get_monthly_goals_file(date: datetime) -> Path:
    """Get monthly goals file path for given date."""
    return GOALS_ROOT / "monthly" / f"{date.strftime('%Y-%m')}.yml"


def get_weekly_goals_file(date: datetime) -> Path:
    """Get weekly goals file path for given date (YYYY-Www format)."""
    iso_cal = date.isocalendar()
    return GOALS_ROOT / "weekly" / f"{iso_cal.year}-W{iso_cal.week:02d}.yml"


def get_daily_goals_file(date: datetime) -> Path:
    """Get daily goals file path for given date."""
    return GOALS_ROOT / "daily" / f"{date.strftime('%Y-%m-%d')}.yml"


def parse_task_frontmatter(text: str) -> Dict[str, Any]:
    """Parse YAML frontmatter from t-*.md file."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: Dict[str, Any] = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip().strip("'\"")
    return fm


def find_deadline_tasks(date: datetime) -> List[Dict[str, Any]]:
    """Find all tasks with deadline on given date."""
    tasks = []

    if not PROJECTS_ROOT.exists():
        return tasks

    target_date_str = date.strftime("%Y-%m-%d")

    for task_file in PROJECTS_ROOT.rglob("t-*.md"):
        try:
            fm = parse_task_frontmatter(task_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        deadline = str(fm.get("deadline", ""))
        if deadline == target_date_str:
            fm["project_name"] = task_file.parent.name
            tasks.append(fm)

    return tasks


def format_monthly_section(date: datetime) -> str:
    """Format monthly goals section."""
    monthly_file = get_monthly_goals_file(date)
    monthly_data = load_yaml_file(monthly_file)

    if not monthly_data or "goals" not in monthly_data:
        return "📅 이번 달: (목표 미설정 - 알려주시면 기록할게요!)"

    theme = monthly_data.get("theme", "")
    goals = monthly_data.get("goals", [])

    # Calculate overall progress
    all_percents = []
    for goal in goals:
        krs = goal.get("key_results", [])
        for kr in krs:
            p = calc_kr_percent(kr)
            if p is not None:
                all_percents.append(p)

    overall_percent = round(sum(all_percents) / len(all_percents)) if all_percents else 0
    progress_bar = make_progress_bar(overall_percent)

    lines = [f"📅 이번 달: {theme}"]
    lines.append(f"  {progress_bar} {overall_percent}%")

    # List goals with their progress
    for goal in goals:
        title = goal.get("title", "")
        krs = goal.get("key_results", [])

        if not krs:
            lines.append(f"  ⬜ {title}")
            continue

        # Calculate goal progress from KRs
        kr_percents = [calc_kr_percent(kr) for kr in krs]
        kr_percents = [p for p in kr_percents if p is not None]
        goal_percent = round(sum(kr_percents) / len(kr_percents)) if kr_percents else 0
        goal_icon = get_kr_icon(goal_percent)

        lines.append(f"  {goal_icon} {title}")

        # Show key results
        for kr in krs:
            display_text, percent = get_kr_display(kr)
            icon = get_kr_icon(percent)
            lines.append(f"    {icon} {display_text}")

    return "\n".join(lines)


def format_weekly_section(date: datetime) -> str:
    """Format weekly goals section."""
    weekly_file = get_weekly_goals_file(date)
    weekly_data = load_yaml_file(weekly_file)

    if not weekly_data or "goals" not in weekly_data:
        return "📆 이번 주: (목표 미설정 - 알려주시면 기록할게요!)"

    goals = weekly_data.get("goals", [])
    period = weekly_data.get("period", "")

    iso_cal = date.isocalendar()
    week_num = iso_cal.week

    # Calculate progress from statuses
    done_count = 0
    total_count = len(goals)
    all_percents = []

    for goal in goals:
        status = goal.get("status", "").lower()
        if status == "done":
            done_count += 1
            all_percents.append(100)
        elif status == "in_progress":
            all_percents.append(50)
        else:  # todo, etc
            all_percents.append(0)

    overall_percent = round(sum(all_percents) / len(all_percents)) if all_percents else 0
    progress_bar = make_progress_bar(overall_percent)

    lines = [f"📆 이번 주 (W{week_num:02d}): {done_count}/{total_count} 완료"]
    lines.append(f"  {progress_bar} {overall_percent}%")

    # List goals
    for goal in goals:
        title = goal.get("title", "")
        status = goal.get("status", "").lower()

        if status == "done":
            icon = "✅"
        elif status == "in_progress":
            icon = "🔄"
        else:
            icon = "⬜"

        lines.append(f"  {icon} {title}")

    return "\n".join(lines)


def format_daily_section(date: datetime) -> str:
    """Format daily goals section."""
    daily_file = get_daily_goals_file(date)
    daily_data = load_yaml_file(daily_file)

    if not daily_data:
        return "📌 오늘 할 일:\n  (목표 미설정 - 알려주시면 기록할게요!)"

    # Support both 'goals' key and 'top3'/'checklist' structure
    goals = daily_data.get("goals", [])
    top3 = daily_data.get("top3", [])
    checklist = daily_data.get("checklist", [])

    # Merge top3 + checklist into unified items list
    items = []
    for item in top3:
        if isinstance(item, str):
            items.append({"title": item, "status": "todo"})
        else:
            items.append({"title": item.get("title", ""), "status": item.get("status", "todo")})

    for item in checklist:
        if isinstance(item, dict):
            done = item.get("done", False)
            items.append({"title": item.get("task", ""), "status": "done" if done else "todo"})

    # Also handle classic 'goals' format
    for goal in goals:
        if isinstance(goal, str):
            items.append({"title": goal, "status": "todo"})
        else:
            items.append({"title": goal.get("title", ""), "status": goal.get("status", "todo")})

    if not items:
        return "📌 오늘 할 일:\n  (목표 미설정 - 알려주시면 기록할게요!)"

    done_count = sum(1 for i in items if i["status"].lower() == "done")
    total_count = len(items)

    lines = [f"📌 오늘 할 일: {done_count}/{total_count} 완료"]

    for item in items:
        status = item["status"].lower()
        if status == "done":
            icon = "✅"
        elif status == "in_progress":
            icon = "🔄"
        else:
            icon = "⬜"
        lines.append(f"  {icon} {item['title']}")

    return "\n".join(lines)


def format_deadline_section(deadline_tasks: List[Dict[str, Any]]) -> str:
    """Format deadline tasks section."""
    if not deadline_tasks:
        return ""

    lines = ["🔥 오늘 마감:"]
    for task in deadline_tasks:
        task_id = task.get("id", "")
        title = task.get("title", "")
        lines.append(f"  • {task_id} ({title})")

    return "\n".join(lines)


def format_message(date: datetime) -> str:
    """Format complete message."""
    weekday_ko = WEEKDAYS_KO[date.weekday()]
    date_str = date.strftime("%Y-%m-%d")

    header = f"📊 목표 브리핑 ({date_str} {weekday_ko})\n"

    sections = [
        header,
        format_monthly_section(date),
        "",
        format_weekly_section(date),
        "",
        format_daily_section(date),
    ]

    deadline_tasks = find_deadline_tasks(date)
    if deadline_tasks:
        sections.append("")
        sections.append(format_deadline_section(deadline_tasks))

    return "\n".join(sections)


def send_telegram_message(message: str) -> bool:
    """Send message via Telegram."""
    try:
        result = subprocess.run(
            [
                "clawdbot",
                "message",
                "send",
                "-t",
                TELEGRAM_GROUP,
                "--thread-id",
                THREAD_ID,
                message,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error sending Telegram message: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Send daily goal briefing to Telegram"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print to console without sending to Telegram",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Override today's date (YYYY-MM-DD format)",
    )

    args = parser.parse_args()

    # Determine date
    if args.date:
        try:
            date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date format. Use YYYY-MM-DD", file=sys.stderr)
            return 1
    else:
        date = datetime.now()

    # Format message
    try:
        message = format_message(date)
    except Exception as e:
        print(f"Error formatting message: {e}", file=sys.stderr)
        return 1

    # Print message
    print(message)

    # Send or dry-run
    if args.dry_run:
        print("\n[DRY RUN - Message not sent to Telegram]")
        return 0

    # Send to Telegram
    if send_telegram_message(message):
        print("\n✅ Message sent to Telegram")
        return 0
    else:
        print("\n❌ Failed to send message to Telegram", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
