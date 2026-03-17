---
name: meal-tracker
description: GLP-1 약물 기반 식사 기록 + 영양 모니터링 — SQLite 기록
version: 1.1.0
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Meal Tracker

마운자로 5.0 복용 중 식사 모니터링. DB: `~/life-dashboard/data.db` → `health_meals` 테이블.
식사 데이터는 life-coach 일일 코칭에서 건강 섹션으로 통합된다.

## 식사 기록

```bash
python3 {baseDir}/scripts/log_meal.py \
  --type "점심" \
  --food "삼겹살, 쌈채소, 된장찌개" \
  --portion "보통" \
  --notes "입맛 괜찮았음"
```

파라미터:
- `--type`: 아침/점심/저녁/간식
- `--food`: 먹은 음식 (쉼표로 구분)
- `--portion`: 적음/보통/많음
- `--notes`: 메모 (선택)
- `--skipped`: 거른 경우 이 플래그 추가

### 거른 식사

```bash
python3 {baseDir}/scripts/log_meal.py \
  --type "저녁" --skipped --notes "입맛 없어서 건너뜀"
```

### 일일 요약

```bash
python3 {baseDir}/scripts/daily_summary.py
```

## 자동화 스케줄

식사 알림:
- **08:00** — 아침
- **12:30** — 점심
- **18:30** — 저녁

설치: `bash {baseDir}/scripts/setup_cron.sh`

## SQLite 컬럼

| 컬럼 | 설명 |
|------|------|
| date | 식사 날짜 (YYYY-MM-DD) |
| timestamp | 식사 시간 (HH:MM) |
| meal_type | 아침/점심/저녁/간식 |
| food_items | 먹은 음식 목록 |
| portion | 섭취량 (적음/보통/많음) |
| skipped | 거른 여부 (0/1) |
| notes | 입맛, 기분 등 메모 |
| calories | 추정 칼로리 |
| protein/carbs/fat | 영양소 (g) |

## 영양소 추정

`config/nutrition_db.json` 기반 자동 추정. 대략적인 수치.

## Scripts

| 파일 | 용도 |
|------|------|
| `scripts/log_meal.py` | 식사 기록 CLI |
| `scripts/daily_summary.py` | 일일 영양 요약 |
| `scripts/meal_reminder.py` | 식사 시간 알림 |

## 팁

- 입맛 없어도 조금이라도 먹기
- 간식도 기록하면 패턴 파악 가능
- "입맛 없음", "속쓰림" 등 증상 메모 → 마운자로 부작용 분석에 활용
