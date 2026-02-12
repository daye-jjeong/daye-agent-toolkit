#!/usr/bin/env python3
"""
Proactive Suggestions Script

자동 제안 크론 (점검/조치와 분리)
- 무조건 보내기 (승인 요청 없음)
- 23:00~08:00 제외 (자는 시간)
- 1~3개 제안만
- inputs: 최근 시스템 이벤트, 오늘 남은 일정, 최근 대화 컨텍스트
- outputs: JSON 출력 (크론 페이로드가 LLM 호출 및 전송 처리)

Usage:
  ./scripts/proactive_suggestions.py [--dry-run]

Cron:
  크론 페이로드에서 이 스크립트의 출력을 읽어 LLM 호출 및 메시지 전송
"""

import json
import os
import sys
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
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


def get_today_remaining_tasks() -> List[str]:
    """Get today's remaining tasks from vault tasks.yml files"""
    try:
        import yaml

        today = datetime.now().strftime("%Y-%m-%d")
        remaining = []

        for tasks_file in PROJECTS_DIR.rglob("tasks.yml"):
            try:
                with open(tasks_file) as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                continue

            for task in data.get("tasks", []):
                deadline = str(task.get("deadline", ""))
                status = task.get("status", "todo")

                if deadline == today and status not in ("done", "on_hold"):
                    remaining.append(task.get("title", "(untitled)"))

        return remaining[:5]
    except Exception as e:
        log(f"⚠️ Failed to get vault tasks: {e}")
        return []


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
    
    # Gather inputs
    log("📊 Gathering inputs...")
    cron_errors = get_recent_cron_errors()
    stuck_count = get_stuck_sessions()
    today_tasks = get_today_remaining_tasks()
    conversation_context = get_recent_conversation_context()
    
    log(f"  - Cron errors: {len(cron_errors)}")
    log(f"  - Stuck sessions: {stuck_count}")
    log(f"  - Today tasks: {len(today_tasks)}")
    
    # Output JSON for cron payload to process
    output = {
        "skip": False,
        "inputs": {
            "cronErrors": cron_errors,
            "stuckSessions": stuck_count,
            "todayTasks": today_tasks,
            "conversationContext": conversation_context,
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
