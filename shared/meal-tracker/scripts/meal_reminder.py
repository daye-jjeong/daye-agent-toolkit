#!/usr/bin/env python3
"""
Meal Tracker - 식사 알림 스크립트

Usage:
    python3 meal_reminder.py breakfast
    python3 meal_reminder.py lunch
    python3 meal_reminder.py dinner
"""

import sys
import subprocess
from datetime import datetime

TELEGRAM_GROUP = "-1003242721592"
TOPIC_PT = "169"  # 🏋️ PT/운동 토픽 (건강 관련)

MESSAGES = {
    "breakfast": {
        "emoji": "🍳",
        "question": "다예, 아침 먹었어?",
        "suggestions": "가벼운 거라도 먹는 게 좋아!\n예: 달걀, 요거트, 바나나, 토스트"
    },
    "lunch": {
        "emoji": "🍱",
        "question": "점심 시간이야! 뭐 먹을래?",
        "suggestions": "입맛 없어도 단백질은 챙기자!\n예: 닭가슴살, 고등어, 두부, 달걀"
    },
    "dinner": {
        "emoji": "🍽️",
        "question": "저녁 먹었어?",
        "suggestions": "너무 무거운 건 피하고, 소화 잘 되는 걸로!\n예: 샐러드, 미역국, 생선"
    }
}

def send_reminder(meal_type):
    if meal_type not in MESSAGES:
        print(f"❌ Unknown meal type: {meal_type}")
        print("Available: breakfast, lunch, dinner")
        sys.exit(1)
    
    msg = MESSAGES[meal_type]
    now = datetime.now().strftime("%H:%M")
    
    message = f"""{msg['emoji']} **식사 시간 알림** ({now})

{msg['question']}

{msg['suggestions']}

💊 마운자로 복용 중이라 입맛 없을 수 있지만, 조금이라도 먹는 게 중요해!

먹었으면 답장으로 메뉴 알려줘. 내가 기록할게! 📝
거르면 "거름"이라고 알려줘."""
    
    cmd = [
        "clawdbot", "message", "send",
        "-t", TELEGRAM_GROUP,
        "--thread-id", TOPIC_PT,
        "-m", message
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ {meal_type.capitalize()} reminder sent!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to send reminder: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 meal_reminder.py <breakfast|lunch|dinner>")
        sys.exit(1)
    
    meal_type = sys.argv[1].lower()
    send_reminder(meal_type)
