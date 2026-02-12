# Meal Tracker

**마운자로 복용 중 식사 모니터링 전문 스킬**

## 목적

- 마운자로 5.0 복용 부작용 (입맛 없음, 식사 거름) 모니터링
- 규칙적인 식사 습관 형성
- 영양소 섭취 트래킹
- Health Coach와 데이터 연계

## 기능

### 1. 자동 식사 알림
- **08:00** - 아침 식사 리마인더
- **12:30** - 점심 식사 리마인더
- **18:30** - 저녁 식사 리마인더

### 2. 식사 기록
- 메뉴, 양, 시간 기록
- Obsidian vault (~/clawd/memory/meals/) 저장
- Dataview-queryable frontmatter
- 거른 식사 추적

### 3. 영양소 추정
- 칼로리, 단백질, 탄수화물, 지방 자동 계산
- 간단한 영양소 DB 기반 추정

### 4. 일일 요약
- **20:00** - 하루 식사 요약 (Health Coach 연계)
- 패턴 분석 및 조언

## 파일 구조

```
meal-tracker/
├── README.md              # 이 파일
├── SKILL.md              # 사용법
├── scripts/
│   ├── meals_io.py       # Obsidian vault I/O 모듈
│   ├── meal_reminder.py  # 식사 알림
│   ├── log_meal.py       # 식사 기록
│   └── daily_summary.py  # 일일 요약
└── config/
    ├── nutrition_db.json # 영양소 데이터
    └── cron_schedule.txt # Cron 스케줄
```

## Obsidian vault 구조

**디렉토리:** `~/clawd/memory/meals/`

각 식사 기록은 frontmatter가 포함된 마크다운 파일로 저장됩니다:

- date (YYYY-MM-DD)
- time (YYYY-MM-DD HH:MM)
- type: meal (Dataview 필터용)
- meal_type (아침/점심/저녁/간식)
- food_items (text)
- portion (적음/보통/많음)
- skipped (true/false)
- notes (text)
- calories (number)
- protein (number, g)
- carbs (number, g)
- fat (number, g)

## 설치

```bash
# Cron 작업 등록
crontab -e

# 아래 내용 추가:
0 8 * * * cd ~/clawd && clawdbot cron once meal-reminder-breakfast "python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py breakfast"
30 12 * * * cd ~/clawd && clawdbot cron once meal-reminder-lunch "python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py lunch"
30 18 * * * cd ~/clawd && clawdbot cron once meal-reminder-dinner "python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py dinner"
0 20 * * * cd ~/clawd && clawdbot cron once meal-daily-summary "python3 ~/clawd/skills/meal-tracker/scripts/daily_summary.py"
```
