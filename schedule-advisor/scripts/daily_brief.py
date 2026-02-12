#!/usr/bin/env python3
import subprocess
import datetime
import re
import sys

def parse_korean_time(t_str):
    # Handle "오후 1:00" -> "13:00"
    # Handle "오전 9:00" -> "09:00"
    t_str = t_str.strip()
    is_pm = "오후" in t_str
    t_clean = t_str.replace("오후", "").replace("오전", "").strip()
    
    # Check for HH:MM
    match = re.search(r'(\d+):(\d+)', t_clean)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if is_pm and h != 12: h += 12
        if not is_pm and h == 12: h = 0
        return f"{h:02d}:{m:02d}"
    return t_str

def get_events():
    # Fetch today's events
    # Include: daye@ronik.io, 개인 (Personal), Taling, Gmail
    cmd = [
        "/opt/homebrew/bin/icalBuddy",
        "-n", "-nc", "-b", "",
        "-ps", "||",
        "-eep", "url,attendees,notes",
        "-ic", "daye@ronik.io,개인,Personal,Taling,daye.jjeong@gmail.com",
        "eventsToday"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        lines = result.stdout.splitlines()
    except Exception as e:
        return [f"Error fetching calendars: {e}"]

    formatted = []
    for line in lines:
        if not line.strip(): continue
        
        # line: "Title||Time - Time" or "Title" (all day)
        if "||" in line:
            parts = line.split("||")
            title = parts[0].strip()
            time_range = parts[1].strip()
            
            # Extract start time
            start_part = time_range.split("-")[0].strip()
            time_str = parse_korean_time(start_part)
        else:
            title = line.strip()
            time_str = "All Day"
            
        formatted.append(f"[{time_str}] {title}")
        
    return formatted

def main():
    events = get_events()
    
    dt = datetime.datetime.now().strftime("%Y-%m-%d %a")
    header = f"📅 **Morning Briefing** ({dt})"
    
    if not events:
        body = "No events today."
    else:
        # Sort by time? icalBuddy usually sorts, but "All Day" comes last or first.
        # We'll trust icalBuddy order for now.
        body = "\n".join(events)
        
    message = f"{header}\n\n{body}"
    
    # Send to Telegram
    # Use topic 167 (Morning brief) from TOOLS.md if available, or just default.
    # TOOLS.md says: 📅 일정/준비 관련 → 토픽 ID: 167
    subprocess.run([
        "clawdbot", "message", "send", 
        "--target", "-1003242721592", # JARVIS HQ
        "--thread-id", "167",   # Topic 167
        "--message", message
    ])

if __name__ == "__main__":
    main()
