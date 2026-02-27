#!/usr/bin/env python3
"""
Meal Tracker - 일일 요약 스크립트 (Obsidian vault 기반)

20:00에 실행되어 오늘 식사 요약을 전송합니다.
Health Coach와 연계하여 조언도 제공합니다.

Usage:
    python3 daily_summary.py
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

# meals_io 임포트 (같은 디렉토리)
sys.path.insert(0, str(Path(__file__).parent))
import meals_io

TELEGRAM_GROUP = "-1003242721592"
TOPIC_PT = "169"  # PT/운동 토픽


def load_today_meals():
    """오늘 식사 기록을 Obsidian vault에서 불러오기"""
    today_str = meals_io.today()
    entries = meals_io.read_entries(days=1, filters={"type": "meal"})

    # 오늘 날짜만 필터
    today_meals = []
    for filepath, fm in entries:
        if str(fm.get("date", "")) == today_str:
            today_meals.append(fm)

    return today_meals


def generate_summary(meals):
    """식사 요약 생성"""
    if not meals:
        return {
            "total_meals": 0,
            "skipped": 3,
            "total_calories": 0,
            "total_protein": 0,
            "total_carbs": 0,
            "total_fat": 0,
            "meals_by_type": {}
        }

    summary = {
        "total_meals": 0,
        "skipped": 0,
        "total_calories": 0,
        "total_protein": 0,
        "total_carbs": 0,
        "total_fat": 0,
        "meals_by_type": {}
    }

    for meal in meals:
        if meal.get("skipped"):
            summary["skipped"] += 1
        else:
            summary["total_meals"] += 1
            summary["total_calories"] += meal.get("calories", 0)
            summary["total_protein"] += meal.get("protein", 0)
            summary["total_carbs"] += meal.get("carbs", 0)
            summary["total_fat"] += meal.get("fat", 0)

        meal_type = meal.get("meal_type", "기타")
        summary["meals_by_type"][meal_type] = meal

    return summary


def generate_message(summary, meals):
    """텔레그램 메시지 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 헤더
    message = f"**오늘의 식사 요약** ({now})\n\n"

    # 식사 현황
    message += "**식사 현황**\n"
    message += f"- 먹은 식사: {summary['total_meals']}/3\n"
    message += f"- 거른 식사: {summary['skipped']}/3\n\n"

    # 식사별 상세
    if meals:
        message += "**상세 기록**\n"
        for meal in meals:
            meal_type = meal.get("meal_type", "")
            if meal.get("skipped"):
                message += f"- {meal_type}: 거름"
                if meal.get("notes"):
                    message += f" ({meal['notes']})"
                message += "\n"
            else:
                food = meal.get("food_items", "")
                portion = meal.get("portion", "")
                message += f"- {meal_type}: {food} ({portion})\n"
        message += "\n"

    # 영양소 요약
    if summary['total_meals'] > 0:
        message += "**영양소 합계**\n"
        message += f"- 칼로리: {summary['total_calories']}kcal\n"
        message += f"- 단백질: {summary['total_protein']:.1f}g\n"
        message += f"- 탄수화물: {summary['total_carbs']:.1f}g\n"
        message += f"- 지방: {summary['total_fat']:.1f}g\n\n"

    # 조언
    message += "**Health Coach 조언**\n"

    if summary['skipped'] == 0:
        message += "오늘 세 끼 다 챙겨 먹었네! 훌륭해!\n"
    elif summary['skipped'] == 1:
        message += "한 끼 거른 것 같아. 내일은 세 끼 다 챙기자!\n"
    elif summary['skipped'] == 2:
        message += "두 끼나 거렀네... 마운자로 부작용 심한가? 내일은 꼭 챙겨 먹자!\n"
    else:
        message += "오늘 거의 안 먹었어! 입맛 없어도 프로틴쉐이크라도 마시자. 건강 중요해!\n"

    # 단백질 체크
    if summary['total_meals'] > 0:
        if summary['total_protein'] < 60:
            message += "단백질이 부족해! (목표: 60g 이상)\n"
        else:
            message += f"단백질 충분! ({summary['total_protein']:.1f}g)\n"

    message += "\n내일도 잘 챙겨 먹자!"

    return message


def send_summary():
    """요약 전송"""
    meals = load_today_meals()
    summary = generate_summary(meals)
    message = generate_message(summary, meals)

    cmd = [
        "clawdbot", "message", "send",
        "-t", TELEGRAM_GROUP,
        "--thread-id", TOPIC_PT,
        "-m", message
    ]

    try:
        subprocess.run(cmd, check=True)
        print("[OK] Daily summary sent!")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to send summary: {e}")
        return False

    return True


if __name__ == "__main__":
    send_summary()
