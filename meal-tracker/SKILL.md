---
name: meal-tracker
description: GLP-1 약물 기반 식사 기록 + 영양 모니터링 + 리마인더
---

# Meal Tracker - 사용법


**Version:** 0.2.0
**Updated:** 2026-02-11
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

## 개요

마운자로 5.0 복용 중 식사 모니터링을 위한 자동화 스킬입니다.

## 저장소

**Obsidian vault:** `~/mingming-vault/meals/`

식사 기록은 Dataview-queryable frontmatter를 가진 마크다운 파일로 저장됩니다.

### 파일 형식 예시

```markdown
---
date: 2026-02-11
time: 2026-02-11 12:30
type: meal
meal_type: 점심
food_items: "삼겹살, 쌈채소, 된장찌개"
portion: 보통
skipped: false
calories: 500
protein: 29.0
carbs: 82.0
fat: 38.5
notes: 입맛 괜찮았음
---
```

### Dataview 쿼리 예시

```dataview
TABLE meal_type, food_items, calories, protein
FROM "meals"
WHERE type = "meal" AND date = date(today)
SORT time ASC
```

## 주요 명령어

### 1. 수동 식사 기록

```bash
python3 {baseDir}/scripts/log_meal.py \
  --type "점심" \
  --food "삼겹살, 쌈채소, 된장찌개" \
  --portion "보통" \
  --notes "입맛 괜찮았음"
```

**파라미터:**
- `--type` : 아침/점심/저녁/간식
- `--food` : 먹은 음식 (쉼표로 구분)
- `--portion` : 적음/보통/많음
- `--notes` : 메모 (선택)
- `--skipped` : 거른 경우 이 플래그 추가

### 2. 거른 식사 기록

```bash
python3 {baseDir}/scripts/log_meal.py \
  --type "저녁" \
  --skipped \
  --notes "입맛 없어서 건너뜀"
```

### 3. 일일 요약 보기

```bash
python3 {baseDir}/scripts/daily_summary.py
```

## 자동화 스케줄

### 식사 알림
- **08:00** - "다예, 아침 먹었어?"
- **12:30** - "점심 시간이야! 뭐 먹을래?"
- **18:30** - "저녁 먹었어?"

### 일일 요약
- **20:00** - 오늘 식사 요약 + Health Coach 연계

## 필드 설명

- **date** - 식사 날짜 (YYYY-MM-DD)
- **time** - 식사 시간 (YYYY-MM-DD HH:MM)
- **type** - 항상 "meal" (Dataview 필터용)
- **meal_type** - 아침/점심/저녁/간식
- **food_items** - 먹은 음식 목록
- **portion** - 섭취량 (적음/보통/많음)
- **skipped** - 거른 여부 (true/false)
- **notes** - 입맛, 기분 등 메모
- **calories** - 추정 칼로리
- **protein/carbs/fat** - 영양소 (g)

## 영양소 추정

간단한 음식 DB 기반으로 영양소를 자동 추정합니다:

**예시:**
- 밥 1공기 (210g) -> 310kcal, 단백질 5g, 탄수화물 68g, 지방 0.5g
- 삼겹살 100g -> 330kcal, 단백질 17g, 탄수화물 0g, 지방 30g
- 달걀 1개 -> 70kcal, 단백질 6g, 탄수화물 0.5g, 지방 5g

**정확도:** 대략적인 추정치입니다. 정확한 영양 분석이 필요하면 Health Coach에게 문의하세요.

## Health Coach 연계

매일 20:00 요약 시 Health Coach에게 데이터 전달:
- 오늘 섭취한 총 칼로리
- 단백질/탄수화물/지방 비율
- 거른 식사 여부
- 입맛 변화 패턴

Health Coach가 이를 기반으로 조언을 제공합니다.

## 트러블슈팅

### vault 디렉토리가 없을 때

meals 디렉토리는 첫 기록 시 자동 생성됩니다. 수동 생성:

```bash
mkdir -p ~/mingming-vault/meals
```

### 알림이 안 올 때

```bash
# Cron 작업 확인
crontab -l | grep meal

# 수동 테스트
python3 {baseDir}/scripts/meal_reminder.py breakfast
```

## 팁

1. **거르지 말기:** 입맛 없어도 조금이라도 먹기 (Health Coach 조언 참고)
2. **간식도 기록:** 과일, 견과류 등도 기록하면 패턴 파악 가능
3. **메모 활용:** "입맛 없음", "속쓰림" 등 증상 기록 -> 마운자로 부작용 분석
