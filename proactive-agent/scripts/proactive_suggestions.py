#!/usr/bin/env python3
"""
Proactive Suggestions Script (통합)

자동 제안 크론 — proactive_check.py 기능 흡수
- 무조건 보내기 (승인 요청 없음)
- 23:00~08:00 제외 (자는 시간)
- 1~3개 제안만
- inputs: 시스템 이벤트, 오늘 태스크, 대화 컨텍스트,
          내일 캘린더 마감, 밀린 태스크, 실패 큐
- outputs: JSON 출력 (크론 페이로드가 LLM 호출 및 전송 처리)

Merged from:
- proactive_suggestions.py (data gathering + JSON output)
- proactive_check.py (calendar/backlog/system checks)

Usage:
  ./scripts/proactive_suggestions.py [--dry-run]
"""

import json
import os
import sys
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple

# Configuration
WORKSPACE = Path("/Users/dayejeong/clawd")
STATE_FILE = WORKSPACE / "memory" / "proactive-suggestions-state.json"
PROJECTS_DIR = WORKSPACE / "memory" / "projects"

# Limits
MAX_DAILY_SENDS = 10
LOOKBACK_HOURS = 4
DUPLICATE_WINDOW_HOURS = 24

# Sleep hours (KST)
SLEEP_START_HOUR = 23
SLEEP_END_HOUR = 8

DRY_RUN = "--dry-run" in sys.argv


def log(msg: str):
    """Log with timestamp to stderr"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", file=sys.stderr)


def is_sleep_time() -> bool:
    """Check if current time is in sleep hours"""
    now = datetime.now()
    hour = now.hour
    return hour >= SLEEP_START_HOUR or hour < SLEEP_END_HOUR


def load_state() -> Dict:
    """Load state file"""
    if not STATE_FILE.exists():
        return {
            "lastRun": None,
            "sentToday": 0,
            "lastSendDate": None,
            "recentHashes": []
        }
    
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log(f"⚠️ Failed to load state: {e}")
        return {"lastRun": None, "sentToday": 0, "lastSendDate": None, "recentHashes": []}


def save_state(state: Dict):
    """Save state file"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except IOError as e:
        log(f"❌ Failed to save state: {e}")


def check_daily_limit(state: Dict) -> Tuple[bool, str]:
    """Check if daily send limit reached"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    if state.get("lastSendDate") != today:
        state["sentToday"] = 0
        state["lastSendDate"] = today
    
    if state["sentToday"] >= MAX_DAILY_SENDS:
        return False, f"Daily limit reached ({MAX_DAILY_SENDS})"
    
    return True, "OK"


def get_recent_cron_errors() -> List[str]:
    """Get recent cron errors"""
    try:
        result = subprocess.run(
            ["clawdbot", "cron", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return []
        
        # Parse text output for error status
        errors = []
        lines = result.stdout.strip().split("\n")[1:]  # Skip header
        
        for line in lines:
            if "error" in line.lower():
                # Extract name (first column before schedule)
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[1]
                    errors.append(name)
        
        return errors[:3]
    except Exception as e:
        log(f"⚠️ Failed to get cron errors: {e}")
        return []


def get_stuck_sessions() -> int:
    """Get count of stuck sessions"""
    try:
        result = subprocess.run(
            ["clawdbot", "sessions", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return 0
        
        # Simple heuristic: count "subagent" sessions (text parsing)
        stuck_count = result.stdout.count("subagent:")
        
        # Assume sessions listed are active, so if many subagents exist, some might be stuck
        # This is a simplification; real detection requires age checking
        return stuck_count if stuck_count > 1 else 0
    except Exception as e:
        log(f"⚠️ Failed to get stuck sessions: {e}")
        return 0


def _parse_frontmatter(text: str) -> Dict:
    """Parse YAML frontmatter from markdown text."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip().strip("'\"")
    return fm


def get_today_remaining_tasks() -> List[str]:
    """Get today's remaining tasks from vault t-*.md files"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        remaining = []

        for task_file in PROJECTS_DIR.rglob("t-*.md"):
            try:
                fm = _parse_frontmatter(task_file.read_text(encoding="utf-8"))
            except Exception:
                continue

            deadline = str(fm.get("deadline", ""))
            status = fm.get("status", "todo")

            if deadline == today and status not in ("done", "on_hold"):
                remaining.append(fm.get("title", "(untitled)"))

        return remaining[:5]
    except Exception as e:
        log(f"⚠️ Failed to get vault tasks: {e}")
        return []


def get_calendar_deadlines() -> List[str]:
    """Check for important events tomorrow (absorbed from proactive_check.py)"""
    try:
        result = subprocess.run([
            "/opt/homebrew/bin/icalBuddy",
            "-n", "-nc", "-b", "",
            "-ps", "||",
            "-ic", "daye@ronik.io,개인,Personal,daye.jjeong@gmail.com",
            "eventsToday+1"
        ], capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return []

        important_keywords = ["회의", "미팅", "발표", "제출", "마감", "PT", "수업"]
        deadlines = []
        seen = set()

        for event in result.stdout.strip().split("\n"):
            if not event.strip() or "today at" in event:
                continue
            title = event.split("location:")[0].split("notes:")[0].split("tomorrow at")[0].strip()
            if title in seen:
                continue
            seen.add(title)
            if any(kw in event for kw in important_keywords):
                deadlines.append(title)

        return deadlines[:3]
    except Exception:
        return []


def get_overdue_tasks() -> List[str]:
    """Check vault for overdue high-priority tasks (absorbed from proactive_check.py)"""
    try:
        today = date.today().isoformat()
        overdue = []

        for task_file in PROJECTS_DIR.rglob("t-*.md"):
            try:
                fm = _parse_frontmatter(task_file.read_text(encoding="utf-8"))
            except Exception:
                continue

            if (fm.get("priority") == "high"
                    and fm.get("status") not in ("done", "on_hold")
                    and fm.get("deadline", "")
                    and str(fm["deadline"]) < today):
                overdue.append(fm.get("title", "(untitled)"))

        return overdue[:5]
    except Exception:
        return []


def get_failed_tasks_count() -> int:
    """Check failed tasks queue (absorbed from proactive_check.py)"""
    try:
        queue_file = WORKSPACE / "memory" / "failed_tasks_queue.json"
        if not queue_file.exists():
            return 0
        with open(queue_file) as f:
            return len(json.load(f).get("tasks", []))
    except Exception:
        return 0


def get_recent_conversation_context() -> str:
    """Get brief summary of recent conversation"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        memory_file = WORKSPACE / "memory" / f"{today}.md"
        
        if not memory_file.exists():
            return "없음"
        
        content = memory_file.read_text(encoding='utf-8')
        lines = content.strip().split("\n")
        recent = "\n".join(lines[-10:])
        
        if len(recent) > 500:
            recent = recent[-500:]
        
        return recent.strip() or "없음"
    except Exception as e:
        log(f"⚠️ Failed to get conversation context: {e}")
        return "없음"


def main():
    """Main execution - output JSON for cron payload to process"""
    log("Starting proactive suggestions...")
    
    # Check sleep time
    if is_sleep_time():
        log("⏰ Sleep time (23:00-08:00), skipping")
        print(json.dumps({"skip": True, "reason": "sleep_time"}))
        return
    
    # Load state
    state = load_state()
    
    # Check daily limit
    can_send, reason = check_daily_limit(state)
    if not can_send:
        log(f"🚫 {reason}")
        print(json.dumps({"skip": True, "reason": "daily_limit", "sentToday": state["sentToday"]}))
        return
    
    # Gather inputs (기존)
    log("📊 Gathering inputs...")
    cron_errors = get_recent_cron_errors()
    stuck_count = get_stuck_sessions()
    today_tasks = get_today_remaining_tasks()
    conversation_context = get_recent_conversation_context()

    # Gather inputs (proactive_check.py에서 흡수)
    calendar_deadlines = get_calendar_deadlines()
    overdue_tasks = get_overdue_tasks()
    failed_tasks = get_failed_tasks_count()

    log(f"  - Cron errors: {len(cron_errors)}")
    log(f"  - Stuck sessions: {stuck_count}")
    log(f"  - Today tasks: {len(today_tasks)}")
    log(f"  - Calendar deadlines: {len(calendar_deadlines)}")
    log(f"  - Overdue tasks: {len(overdue_tasks)}")
    log(f"  - Failed tasks: {failed_tasks}")

    # Output JSON for cron payload to process
    output = {
        "skip": False,
        "inputs": {
            "cronErrors": cron_errors,
            "stuckSessions": stuck_count,
            "todayTasks": today_tasks,
            "conversationContext": conversation_context,
            "calendarDeadlines": calendar_deadlines,
            "overdueTasks": overdue_tasks,
            "failedTasksCount": failed_tasks,
            "timestamp": datetime.now().isoformat(),
            "lookbackHours": LOOKBACK_HOURS
        },
        "state": {
            "sentToday": state["sentToday"],
            "maxDaily": MAX_DAILY_SENDS
        }
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))
    
    # Update lastRun in state
    state["lastRun"] = datetime.now().isoformat()
    save_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"skip": True, "reason": "error", "error": str(e)}))
        sys.exit(1)
