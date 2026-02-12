#!/usr/bin/env python3
"""
Subagent Watchdog Script

Monitors subagent sessions for inactivity (>5 min) and sends group alerts.
- 5분 무응답 감지 (HEARTBEAT.md 정책 통일)
- JARVIS HQ 그룹 알림 (TOOLS.md 정책)
- 30분 쿨다운 (중복 알림 방지)
- 상태 파일: vault/state/subagent-watchdog-state.json

Usage:
  ./scripts/watchdog-subagent.py
  
Cron:
  */5 * * * * /path/to/watchdog-subagent.py >> /tmp/watchdog_subagent.log 2>&1
"""

import subprocess
import json
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Configuration
STATE_FILE = Path.home() / "openclaw" / "vault" / "state" / "subagent-watchdog-state.json"
INACTIVE_THRESHOLD_MINUTES = 5  # Unified with HEARTBEAT.md policy
COOLDOWN_MINUTES = 30
DRY_RUN = "--dry-run" in sys.argv

def log(msg):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

def run_clawdbot_command(args):
    """Execute clawdbot CLI command and return output"""
    try:
        result = subprocess.run(
            ["clawdbot"] + args,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        log("⚠️ clawdbot command timeout")
        return "", 1
    except FileNotFoundError:
        log("❌ clawdbot CLI not found in PATH")
        return "", 1

def get_active_subagents():
    """Get list of active subagent sessions from clawdbot sessions list"""
    output, returncode = run_clawdbot_command(["sessions", "list", "--json"])
    
    if returncode != 0:
        log(f"⚠️ Failed to get sessions list: {returncode}")
        return []
    
    try:
        data = json.loads(output) if output.strip() else {}
        sessions = data.get("sessions", [])
    except json.JSONDecodeError:
        log("⚠️ Failed to parse sessions JSON")
        return []
    
    # Filter for subagent sessions only
    subagents = [
        s for s in sessions 
        if s.get("key", "").startswith("agent:main:subagent:")
    ]
    
    return subagents

def load_state():
    """Load watchdog state from file"""
    if not STATE_FILE.exists():
        return {"lastAlerts": {}}
    
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log(f"⚠️ Failed to load state: {e}")
        return {"lastAlerts": {}}

def save_state(state):
    """Save watchdog state to file"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        log(f"❌ Failed to save state: {e}")

def get_session_last_activity(session):
    """
    Get last activity timestamp from session object (in seconds).
    Converts updatedAt from milliseconds to seconds.
    """
    now = int(time.time())
    
    # updatedAt is in milliseconds, convert to seconds
    if "updatedAt" in session:
        return session["updatedAt"] // 1000
    
    # Fallback: assume now (no penalty for new sessions)
    return now

def send_alert(session_id, inactive_minutes):
    """Send alert to JARVIS HQ group (per TOOLS.md policy)"""
    message = (
        f"⚠️ Subagent 무응답 감지\n\n"
        f"Session: {session_id}\n"
        f"무응답 시간: {inactive_minutes}분\n\n"
        f"확인 필요: 작업이 멈췄거나 블로킹됐을 수 있습니다."
    )
    
    if DRY_RUN:
        log(f"[DRY-RUN] Would send alert: {message[:100]}...")
        return True
    
    # Send to JARVIS HQ group + topic (per TOOLS.md: all automated messages to group)
    output, returncode = run_clawdbot_command([
        "message", "send",
        "--channel", "telegram",
        "--target", "-1003242721592",  # JARVIS HQ group
        "--thread-id", "167",  # 📅 일정/준비 (system/operational alerts)
        "--message", message
    ])
    
    if returncode == 0:
        log(f"✅ Alert sent for {session_id}")
        return True
    else:
        log(f"❌ Failed to send alert for {session_id}")
        return False

def check_subagents():
    """Main watchdog logic"""
    log("Starting subagent watchdog check...")
    
    subagents = get_active_subagents()
    
    if not subagents:
        log("No active subagents found")
        return
    
    log(f"Found {len(subagents)} active subagent(s)")
    
    state = load_state()
    last_alerts = state.get("lastAlerts", {})
    now = int(time.time())
    alerts_sent = 0
    
    for session in subagents:
        session_id = session.get("key", "unknown")
        last_activity = get_session_last_activity(session)
        inactive_seconds = now - last_activity
        inactive_minutes = inactive_seconds // 60
        
        log(f"Checking {session_id}: {inactive_minutes} min inactive")
        
        # Check if inactive threshold exceeded
        if inactive_minutes < INACTIVE_THRESHOLD_MINUTES:
            continue
        
        # Check cooldown period
        last_alert_time = last_alerts.get(session_id, 0)
        cooldown_seconds = COOLDOWN_MINUTES * 60
        time_since_last_alert = now - last_alert_time
        
        if time_since_last_alert < cooldown_seconds:
            remaining = (cooldown_seconds - time_since_last_alert) // 60
            log(f"⏳ Cooldown active for {session_id} ({remaining} min remaining)")
            continue
        
        # Send alert
        log(f"⚠️ Inactive threshold exceeded: {session_id} ({inactive_minutes} min)")
        
        if send_alert(session_id, inactive_minutes):
            last_alerts[session_id] = now
            alerts_sent += 1
    
    # Save updated state
    if alerts_sent > 0:
        state["lastAlerts"] = last_alerts
        save_state(state)
        log(f"Sent {alerts_sent} alert(s)")
    else:
        log("No alerts sent")

if __name__ == "__main__":
    try:
        check_subagents()
    except KeyboardInterrupt:
        log("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Unexpected error: {e}")
        sys.exit(1)
