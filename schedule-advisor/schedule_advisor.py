#!/usr/bin/env python3
"""
schedule_advisor.py - LLM-powered schedule analysis
Takes JSON from fetch_schedule.py and generates briefings/alerts

This is the "skill" component of the hybrid architecture.
"""

import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# Add scripts directory to path for message deduplication
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from message_dedup import MessageDeduplicator, format_target

# Configuration
TELEGRAM_TOPIC_ID = "167"  # 📅 일정/준비 관련
TELEGRAM_CHANNEL_ID = "-1003242721592"  # JARVIS HQ
CLAWDBOT_CMD = "/opt/homebrew/bin/clawdbot"

# Initialize message deduplicator
dedup = MessageDeduplicator()

def send_message(text):
    """Send message to Telegram via clawdbot with deduplication."""
    if not text:
        return
    
    # Check for duplicate
    target = format_target(TELEGRAM_CHANNEL_ID, TELEGRAM_TOPIC_ID)
    if not dedup.check_and_record(text, target):
        print(f"Skipping duplicate message (sent within last 5 minutes)", file=sys.stderr)
        return
    
    cmd = [
        CLAWDBOT_CMD, "message", "send",
        "-t", TELEGRAM_CHANNEL_ID,
        "--thread-id", TELEGRAM_TOPIC_ID,
        "--message", text
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to send message: {e.stderr}", file=sys.stderr)

def format_time(event):
    """Format event start time as string."""
    if event.get("_is_all_day"):
        return "[종일]"
    
    hour = event.get("_start_hour")
    minute = event.get("_start_minute")
    if hour is not None and minute is not None:
        return f"{hour:02d}:{minute:02d}"
    
    # Fallback: parse from ISO string
    dt_str = event.get("_start_dt")
    if dt_str:
        try:
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime("%H:%M")
        except:
            pass
    
    return "[시간미정]"

def is_priority(event, level="P0"):
    """Check if event matches priority level."""
    summary = event.get("summary", "")
    if level == "P0":
        return any(k in summary for k in ["P0", "중요", "Urgent", "긴급"])
    elif level == "P1":
        return "P1" in summary
    return False

def cmd_brief(data):
    """Generate morning briefing."""
    events = data.get("events", [])
    
    if not events:
        send_message("📅 *오늘의 일정 브리핑*\n\n예정된 일정이 없습니다. 여유로운 하루 되세요!")
        return
    
    lines = ["📅 *오늘의 일정 브리핑*\n"]
    
    # Separate by priority
    p0_events = [e for e in events if is_priority(e, "P0")]
    p1_events = [e for e in events if is_priority(e, "P1") and not is_priority(e, "P0")]
    normal_events = [e for e in events if not is_priority(e, "P0") and not is_priority(e, "P1")]
    
    if p0_events:
        lines.append("🔴 *우선순위 높음 (P0)*")
        for event in p0_events:
            time_str = format_time(event)
            summary = event.get("summary", "(제목 없음)")
            location = event.get("location", "")
            loc_str = f" @ {location}" if location else ""
            lines.append(f"• `{time_str}` {summary}{loc_str}")
        lines.append("")
    
    if p1_events:
        lines.append("🟡 *중요 일정 (P1)*")
        for event in p1_events:
            time_str = format_time(event)
            summary = event.get("summary", "(제목 없음)")
            lines.append(f"• `{time_str}` {summary}")
        lines.append("")
    
    if normal_events:
        lines.append("📋 *일반 일정*")
        for event in normal_events:
            time_str = format_time(event)
            summary = event.get("summary", "(제목 없음)")
            lines.append(f"• `{time_str}` {summary}")
    
    # Add preparation suggestion
    lines.append("")
    if p0_events:
        lines.append("💡 *준비사항:* 중요 일정 전 10분 여유를 두세요.")
    else:
        lines.append("✨ 오늘도 좋은 하루 되세요!")
    
    send_message("\n".join(lines))

def cmd_check(data):
    """Generate midday progress check."""
    events = data.get("events", [])
    now = datetime.now().astimezone()
    
    # Filter upcoming events
    upcoming = []
    for event in events:
        if event.get("_is_all_day"):
            continue  # Skip all-day events for midday check
        
        dt_str = event.get("_start_dt")
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str)
                if dt > now:
                    upcoming.append(event)
            except:
                continue
    
    if not upcoming:
        # Check if it's late in the day
        if now.hour >= 18:
            send_message("✅ *일정 마감*\n\n오늘 모든 일정을 마쳤습니다. 수고하셨어요! 🎉")
        else:
            send_message("✅ *중간 점검*\n\n남은 일정이 없습니다. 편안한 오후 되세요.")
    else:
        lines = [f"⏳ *중간 점검* (남은 일정 {len(upcoming)}개)\n"]
        
        for event in upcoming[:5]:  # Show max 5
            time_str = format_time(event)
            summary = event.get("summary", "")
            priority = "🔴" if is_priority(event, "P0") else ""
            lines.append(f"{priority}• `{time_str}` {summary}")
        
        if len(upcoming) > 5:
            lines.append(f"\n... 외 {len(upcoming) - 5}개")
        
        send_message("\n".join(lines))

def cmd_remind(data):
    """Send proactive reminders for P0 tasks."""
    events = data.get("events", [])
    now = datetime.now().astimezone()
    
    for event in events:
        if not is_priority(event, "P0"):
            continue
        
        if event.get("_is_all_day"):
            continue  # No reminders for all-day events
        
        dt_str = event.get("_start_dt")
        if not dt_str:
            continue
        
        try:
            dt = datetime.fromisoformat(dt_str)
        except:
            continue
        
        # Check if within next 10-40 mins
        diff = dt - now
        minutes = diff.total_seconds() / 60
        
        if 10 < minutes <= 40:
            time_str = dt.strftime("%H:%M")
            summary = event.get("summary", "")
            location = event.get("location", "")
            loc_str = f"\n📍 {location}" if location else ""
            
            send_message(
                f"🚨 *P0 일정 임박*\n\n"
                f"`{time_str}` {summary}{loc_str}\n\n"
                f"⏰ {int(minutes)}분 후 시작합니다!"
            )

def main():
    parser = argparse.ArgumentParser(
        description="Schedule advisor - LLM analysis component"
    )
    parser.add_argument(
        "mode",
        choices=["brief", "check", "remind"],
        help="Analysis mode"
    )
    args = parser.parse_args()
    
    # Read JSON from stdin
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("Error: Invalid JSON input", file=sys.stderr)
        sys.exit(1)
    
    # Dispatch to mode handler
    if args.mode == "brief":
        cmd_brief(data)
    elif args.mode == "check":
        cmd_check(data)
    elif args.mode == "remind":
        cmd_remind(data)

if __name__ == "__main__":
    main()
