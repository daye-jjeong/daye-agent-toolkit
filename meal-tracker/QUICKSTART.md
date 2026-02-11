# Meal Tracker - 빠른 시작 가이드

## 1분 설치

### Step 1: Cron 작업 설정

```bash
cd ~/clawd/skills/meal-tracker
./scripts/setup_cron.sh
```

이것으로 끝! 자동으로 다음 시간에 알림이 옵니다:
- 08:00 - 아침 알림
- 12:30 - 점심 알림
- 18:30 - 저녁 알림
- 20:00 - 일일 요약

### Step 2: 테스트 (선택)

```bash
# 알림 테스트
python3 scripts/meal_reminder.py breakfast

# 식사 기록 테스트
python3 scripts/log_meal.py --type "점심" --food "샐러드, 닭가슴살" --portion "보통"

# 요약 테스트
python3 scripts/daily_summary.py
```

## 사용법

### 식사 기록

텔레그램 알림에 답장으로 메뉴를 알려주면 됩니다:
```
삼겹살, 쌈채소, 된장찌개 먹었어
```

또는 직접 명령어로:
```bash
python3 scripts/log_meal.py \
  --type "저녁" \
  --food "고등어, 샐러드, 현미밥" \
  --portion "많음"
```

### 거른 식사

```bash
python3 scripts/log_meal.py \
  --type "아침" \
  --skipped \
  --notes "입맛 없어서 못 먹음"
```

## 데이터 저장 위치

식사 기록은 Obsidian vault에 마크다운 파일로 저장됩니다:

```bash
# 오늘 기록 확인
ls ~/mingming-vault/meals/$(date +%Y-%m-%d)*.md
```

## 문제 해결

### 알림이 안 와요
```bash
# Cron 작업 확인
crontab -l | grep meal

# 수동 테스트
python3 ~/clawd/skills/meal-tracker/scripts/meal_reminder.py lunch
```

### 기록이 안 남아요
```bash
# vault 디렉토리 확인
ls -lh ~/mingming-vault/meals/

# 수동 기록 테스트
python3 ~/clawd/skills/meal-tracker/scripts/log_meal.py \
  --type "간식" \
  --food "바나나" \
  --portion "적음"
```

## 커스터마이징

### 알림 시간 변경

```bash
crontab -e
```

시간 포맷: `분 시 * * *`
- 예: `0 9 * * *` = 매일 09:00
- 예: `30 13 * * *` = 매일 13:30

### 영양소 DB 추가

`config/nutrition_db.json`에 음식 추가:

```json
{
  "간식": {
    "프로틴바": {
      "serving": "1개",
      "calories": 200,
      "protein": 20,
      "carbs": 20,
      "fat": 6
    }
  }
}
```

## Health Coach 연계

매일 20:00 요약은 자동으로 Health Coach와 공유됩니다. Health Coach가 다음을 분석합니다:
- 식사 패턴 (거른 식사, 입맛 변화)
- 영양소 균형
- 마운자로 부작용 관련 조언

## 다음 단계

- [ ] 음성으로 식사 기록 (Siri/Google Assistant)
- [ ] 사진으로 음식 인식 및 자동 기록
- [ ] 주간 리포트 생성
