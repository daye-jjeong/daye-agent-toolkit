#!/usr/bin/env python3
"""
Morning Briefing Script
오늘 캘린더 일정 + 목표 질문을 하나의 메시지로 발송.
Run via cron at 09:00 KST.

Merged from:
- schedule-advisor/scripts/daily_brief.py (calendar events)
- goal-planner/scripts/daily_goals_prompt.py (goals prompt)
"""
import subprocess
import datetime
import re
import sys

TELEGRAM_GROUP = "-1003242721592"
THREAD_ID = "167"  # 📅 일정/준비 관련 topic

WEEKDAY_KR = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}


def parse_korean_time(t_str):
    """Handle '오후 1:00' -> '13:00', '오전 9:00' -> '09:00'"""
    t_str = t_str.strip()
    is_pm = "오후" in t_str
    t_clean = t_str.replace("오후", "").replace("오전", "").strip()
    match = re.search(r'(\d+):(\d+)', t_clean)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if is_pm and h != 12:
            h += 12
        if not is_pm and h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"
    return t_str


def get_events():
    """Fetch today's events via icalBuddy"""
    cmd = [
        "/opt/homebrew/bin/icalBuddy",
        "-n", "-nc", "-b", "",
        "-ps", "||",
        "-eep", "url,attendees,notes",
        "-ic", "daye@ronik.io,개인,Personal,Taling,daye.jjeong@gmail.com",
        "eventsToday"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        lines = result.stdout.splitlines()
    except Exception as e:
        return [f"  Error: {e}"]

    formatted = []
    for line in lines:
        if not line.strip():
            continue
        if "||" in line:
            parts = line.split("||")
            title = parts[0].strip()
            time_range = parts[1].strip()
            start_part = time_range.split("-")[0].strip()
            time_str = parse_korean_time(start_part)
        else:
            title = line.strip()
            time_str = "종일"
        formatted.append(f"  [{time_str}] {title}")
    return formatted


def main():
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    weekday = WEEKDAY_KR[now.weekday()]

    # --- 일정 섹션 ---
    events = get_events()
    events_section = "\n".join(events) if events else "  오늘 일정 없음"

    # --- 목표 섹션 ---
    goals_section = (
        f"간단히 알려주시면 daily/{today}.yml에 기록해둘게요.\n"
        "예: 대시보드 배포, PT 숙제, 리서치 정리"
    )

    message = (
        f"📅 **모닝 브리핑** ({today} {weekday})\n\n"
        f"── 오늘 일정 ──\n{events_section}\n\n"
        f"── 오늘의 목표 ──\n{goals_section}"
    )

    result = subprocess.run([
        "clawdbot", "message", "send",
        "--target", TELEGRAM_GROUP,
        "--thread-id", THREAD_ID,
        "--message", message
    ], capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
