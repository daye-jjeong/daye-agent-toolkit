#!/usr/bin/env python3
"""
fetch_schedule.py - Pure data fetching for calendar events
Zero LLM dependencies. Outputs structured JSON for downstream analysis.

Fetches from BOTH:
- Google calendars via gog
- Local macOS calendars via icalBuddy

Usage:
    python3 fetch_schedule.py [--today|--upcoming|--all]
    
Output: JSON to stdout
"""

import sys
import json
import subprocess
import argparse
import re
from datetime import datetime, timedelta

# Configuration
EXCLUDED_KEYWORDS = ["로닉 공용", "Ronik Public", "SKT"]
EXCLUDED_LOCAL_CALENDARS = ["오늘내일", "언젠가", "완료", "마트", "위시리스트", "대한민국 공휴일"]
GOG_CMD = "/opt/homebrew/bin/gog"
ICALBUDDY_CMD = "icalBuddy"

def run_command(cmd):
    """Execute shell command and return stdout."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command {cmd}: {e.stderr}", file=sys.stderr)
        return None

def get_calendars():
    """Get list of Google calendar IDs to query, applying exclusion logic."""
    json_out = run_command([GOG_CMD, "calendar", "calendars", "--json"])
    if not json_out:
        return []
    
    try:
        data = json.loads(json_out)
    except json.JSONDecodeError:
        print("Failed to parse calendar list JSON", file=sys.stderr)
        return []

    calendars = data.get("calendars", [])
    valid_ids = []
    
    for cal in calendars:
        summary = cal.get("summary", "")
        # Filter exclusions
        if any(k.lower() in summary.lower() for k in EXCLUDED_KEYWORDS):
            continue
        
        valid_ids.append(cal["id"])
        
    return valid_ids

def parse_icalbuddy_output(output):
    """Parse icalBuddy text output into structured events."""
    events = []
    lines = output.strip().split('\n')
    current_event = None
    
    for line in lines:
        # Event title line starts with bullet
        if line.startswith('• '):
            if current_event:
                events.append(current_event)
            
            # Parse: • title (calendar)
            match = re.match(r'• (.+?) \((.+?)\)$', line)
            if match:
                title, calendar = match.groups()
                current_event = {
                    "summary": title,
                    "calendar": calendar,
                    "source": "local",
                    "description": "",
                    "location": "",
                    "attendees": []
                }
        elif current_event and line.strip():
            # Parse metadata lines (indented)
            if line.startswith('    '):
                line_content = line.strip()
                
                if line_content.startswith('location:'):
                    current_event["location"] = line_content.replace('location:', '').strip()
                elif line_content.startswith('notes:'):
                    current_event["description"] = line_content.replace('notes:', '').strip()
                elif line_content.startswith('attendees:'):
                    attendees_str = line_content.replace('attendees:', '').strip()
                    current_event["attendees"] = [{"email": a.strip()} for a in attendees_str.split(',')]
                elif re.match(r'(오전|오후)', line_content):
                    # Time line
                    current_event["time_str"] = line_content
                else:
                    # Additional notes
                    if current_event["description"]:
                        current_event["description"] += "\n" + line_content
                    else:
                        current_event["description"] = line_content
    
    if current_event:
        events.append(current_event)
    
    return events

def get_local_events(time_filter="today"):
    """Fetch events from local macOS calendars via icalBuddy."""
    # Build calendar exclusion args
    exclude_args = []
    for cal in EXCLUDED_LOCAL_CALENDARS:
        exclude_args.extend(["-ec", cal])
    
    # Also exclude calendars matching EXCLUDED_KEYWORDS
    for keyword in EXCLUDED_KEYWORDS:
        exclude_args.extend(["-ec", keyword])
    
    # Build time filter
    if time_filter == "today":
        cmd = [ICALBUDDY_CMD, "-n"] + exclude_args + ["eventsToday"]
    elif time_filter == "upcoming":
        cmd = [ICALBUDDY_CMD, "-n"] + exclude_args + ["eventsToday+7"]
    else:
        # Get next 30 days for "all"
        cmd = [ICALBUDDY_CMD, "-n"] + exclude_args + ["eventsFrom:today", "to:today+30"]
    
    output = run_command(cmd)
    if not output or output == "No events found":
        return []
    
    events = parse_icalbuddy_output(output)
    
    # Additional keyword filter for calendar names in parsed events
    filtered_events = []
    for event in events:
        cal_name = event.get("calendar", "")
        if any(k.lower() in cal_name.lower() for k in EXCLUDED_KEYWORDS):
            continue
        filtered_events.append(event)
    
    events = filtered_events
    
    # Normalize to match Google event structure
    normalized = []
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    for event in events:
        # Extract time if present
        time_str = event.get("time_str", "")
        
        # Try to parse Korean time format (오전/오후 HH:MM)
        start_time = None
        if time_str:
            time_match = re.search(r'(오전|오후)\s*(\d{1,2}):(\d{2})', time_str)
            if time_match:
                ampm, hour, minute = time_match.groups()
                hour = int(hour)
                minute = int(minute)
                
                if ampm == "오후" and hour != 12:
                    hour += 12
                elif ampm == "오전" and hour == 12:
                    hour = 0
                
                start_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Build normalized event
        norm_event = {
            "summary": event["summary"],
            "description": event.get("description", ""),
            "location": event.get("location", ""),
            "source": "local",
            "calendar_name": event.get("calendar", ""),
            "_is_all_day": start_time is None
        }
        
        if start_time:
            norm_event["start"] = {"dateTime": start_time.isoformat()}
            norm_event["_sort_key"] = start_time.isoformat()
            norm_event["_start_dt"] = start_time.isoformat()
            norm_event["_start_hour"] = start_time.hour
            norm_event["_start_minute"] = start_time.minute
        else:
            norm_event["start"] = {"date": today_str}
            norm_event["_sort_key"] = today_str
            norm_event["_start_dt"] = today_str
        
        normalized.append(norm_event)
    
    return normalized

def get_events(time_filter="today"):
    """
    Fetch calendar events from both Google and local calendars.
    
    Args:
        time_filter: "today", "upcoming" (next 7 days), or "all"
    
    Returns:
        dict with metadata and events list
    """
    all_events = []
    
    # 1. Fetch Google calendar events
    calendar_ids = get_calendars()
    
    # Date flags for gog
    flags = []
    if time_filter == "today":
        flags = ["--today"]
    elif time_filter == "upcoming":
        flags = ["--days", "7"]
    # else: no flags = all future events
    
    for cal_id in calendar_ids:
        cmd = [GOG_CMD, "calendar", "events", cal_id, "--json"] + flags
        json_out = run_command(cmd)
        if not json_out:
            continue
            
        try:
            data = json.loads(json_out)
        except json.JSONDecodeError:
            continue

        events = data.get("events", []) 
        
        for event in events:
            # Filter Declined events
            attendees = event.get("attendees", [])
            me = next((a for a in attendees if a.get("self")), None)
            if me and me.get("responseStatus") == "declined":
                continue
            
            # Normalize start time for sorting
            start = event.get("start", {})
            dt_str = start.get("dateTime") or start.get("date")
            if not dt_str:
                continue
            
            # Add normalized fields for downstream processing
            event["source"] = "google"
            event["_sort_key"] = dt_str
            event["_is_all_day"] = "date" in start and "dateTime" not in start
            
            # Add parsed datetime for easier processing
            if event["_is_all_day"]:
                event["_start_dt"] = dt_str  # YYYY-MM-DD format
            else:
                try:
                    dt = datetime.fromisoformat(dt_str)
                    event["_start_dt"] = dt.isoformat()
                    event["_start_hour"] = dt.hour
                    event["_start_minute"] = dt.minute
                except:
                    continue
            
            all_events.append(event)
    
    # 2. Fetch local calendar events
    local_events = get_local_events(time_filter)
    all_events.extend(local_events)
            
    # Sort by start time
    all_events.sort(key=lambda x: x["_sort_key"])
    
    # Build output structure
    output = {
        "metadata": {
            "fetch_time": datetime.now().isoformat(),
            "time_filter": time_filter,
            "total_events": len(all_events),
            "google_events": len([e for e in all_events if e.get("source") == "google"]),
            "local_events": len([e for e in all_events if e.get("source") == "local"]),
            "excluded_google_keywords": EXCLUDED_KEYWORDS,
            "excluded_local_calendars": EXCLUDED_LOCAL_CALENDARS
        },
        "events": all_events
    }
    
    return output

def main():
    parser = argparse.ArgumentParser(
        description="Fetch calendar events as structured JSON"
    )
    parser.add_argument(
        "time_filter",
        nargs="?",
        default="today",
        choices=["today", "upcoming", "all"],
        help="Time range filter (default: today)"
    )
    args = parser.parse_args()
    
    data = get_events(args.time_filter)
    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
