#!/bin/bash
# Meal Tracker - Cron 자동 설정 스크립트

echo "🔧 Meal Tracker cron 작업 설정 중..."

# 현재 crontab 백업
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null

# Meal Tracker 작업 추가
(crontab -l 2>/dev/null | grep -v "meal-reminder\|meal-daily-summary"; cat <<EOF
# Meal Tracker - 식사 알림 및 요약
0 8 * * * cd ~/clawd && clawdbot cron once meal-reminder-breakfast "python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py breakfast"
30 12 * * * cd ~/clawd && clawdbot cron once meal-reminder-lunch "python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py lunch"
30 18 * * * cd ~/clawd && clawdbot cron once meal-reminder-dinner "python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py dinner"
0 20 * * * cd ~/clawd && clawdbot cron once meal-daily-summary "python3 ~/clawd/skills/meal-tracker/scripts/daily_summary.py"
EOF
) | crontab -

echo "✅ Cron 작업 설정 완료!"
echo ""
echo "📋 설정된 작업:"
crontab -l | grep meal
echo ""
echo "확인: crontab -l"
