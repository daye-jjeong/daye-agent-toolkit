#!/usr/bin/env python3
"""
Daily Goals Prompt Script
Sends a Telegram message asking Daye about today's goals.
Run via cron at 09:30 KST.
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

TELEGRAM_GROUP = "-1003242721592"
THREAD_ID = "167"  # 📅 일정/준비 관련 topic

def send_telegram_message(message: str) -> bool:
    """Send message via clawdbot CLI"""
    try:
        result = subprocess.run(
            ["clawdbot", "message", "send", "-t", TELEGRAM_GROUP, 
             "--thread-id", THREAD_ID, message],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception:
        return False

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().strftime("%A")
    weekday_kr = {
        "Monday": "월요일", "Tuesday": "화요일", "Wednesday": "수요일",
        "Thursday": "목요일", "Friday": "금요일", "Saturday": "토요일", "Sunday": "일요일"
    }.get(weekday, weekday)
    
    message = f"""🌅 **오늘의 목표 ({today}, {weekday_kr})**

오늘 하루 어떤 것들을 해볼까요?

간단히 알려주시면 `memory/goals/daily/{today}.yml`에 기록해둘게요.

예시:
- 밍밍 대시보드 Cloudflare 배포
- PT 숙제 30분
- 투자 리서치 정리"""

    success = send_telegram_message(message)
    if not success:
        print("Error: Failed to send daily goals prompt", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
