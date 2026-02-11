# Meal Tracker - 설치 가이드

## 자동 설치 (권장)

```bash
cd ~/clawd/skills/meal-tracker

# Cron 작업 자동 등록
bash scripts/setup_cron.sh

# 설치 확인
crontab -l | grep meal
```

## 수동 설치

Cron 작업을 수동으로 등록하려면:

```bash
crontab -e
```

아래 내용을 추가:

```bash
# Meal Tracker - 식사 알림 및 요약
0 8 * * * cd ~/clawd && clawdbot cron once meal-reminder-breakfast "python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py breakfast"
30 12 * * * cd ~/clawd && clawdbot cron once meal-reminder-lunch "python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py lunch"
30 18 * * * cd ~/clawd && clawdbot cron once meal-reminder-dinner "python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py dinner"
0 20 * * * cd ~/clawd && clawdbot cron once meal-daily-summary "python3 ~/clawd/skills/meal-tracker/scripts/daily_summary.py"
```

저장 후 종료:
- vim: `:wq`
- nano: `Ctrl+X`, `Y`, `Enter`

## 설치 확인

```bash
# Cron 작업 확인
crontab -l | grep meal

# 알림 테스트
python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py breakfast

# 식사 기록 테스트
python3 ~/clawd/skills/meal-tracker/scripts/log_meal.py \
  --type "점심" \
  --food "테스트" \
  --portion "보통"

# 요약 테스트
python3 ~/clawd/skills/meal-tracker/scripts/daily_summary.py
```

## 제거

```bash
# Cron 작업 제거
crontab -e
# meal-reminder 관련 줄 삭제

# 또는 전체 제거
crontab -r
```

## 문제 해결

### "no crontab for user" 에러

처음 사용하는 경우 정상입니다. `crontab -e`로 새로 만들어주세요.

### 알림이 안 와요

1. Cron 작업 확인: `crontab -l`
2. 텔레그램 그룹 ID 확인: 스크립트에서 `-1003242721592`
3. 수동 테스트: `python3 scripts/meal_reminder.py breakfast`

### 권한 에러

```bash
chmod +x ~/clawd/skills/meal-tracker/scripts/*.py
chmod +x ~/clawd/skills/meal-tracker/scripts/*.sh
```

## 시간대 설정

macOS는 사용자 cron이 시스템 시간대를 따릅니다.
현재 시간대 확인:

```bash
date
```

한국 시간 (Asia/Seoul)으로 설정되어 있는지 확인하세요.
