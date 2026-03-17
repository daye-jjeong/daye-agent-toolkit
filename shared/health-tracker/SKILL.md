---
name: health-tracker
description: 운동/증상/PT/건강체크인 트래킹 + 루틴 추천 + 분석 — SQLite 기록
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Health Tracker

건강 데이터를 life-dashboard SQLite DB에 기록하고, 루틴 추천/증상 분석을 제공한다.
코칭 통합(일일/주간 리포트)은 life-coach 담당.

## 건강 정보

- **허리디스크:** 증상 모니터링, 패턴 분석
- **메니에르병:** 증상 추적
- **PT:** 주 2회 (필라테스)
- **목표:** 매일 운동 + 걷기

## DB: `~/life-dashboard/data.db`

| 테이블 | 용도 | 주요 컬럼 |
|--------|------|-----------|
| `health_exercises` | 운동 기록 | date, type, duration_min, exercises, feeling |
| `health_symptoms` | 증상 기록 | date, type, severity, description, trigger, status |
| `health_pt_homework` | PT 숙제 | date, exercise, sets_reps, status, completed |
| `health_check_ins` | 일일 체크인 | date (PK), sleep_hours, sleep_quality, steps, workout, stress, water_ml |

## 기록

### 운동 기록
```bash
python3 {baseDir}/scripts/log_exercise.py \
  --type "PT" --duration 60 --exercises "플랭크 3세트, 데드버그 10회" --feeling "좋았음"
```

### 증상 기록
```bash
python3 {baseDir}/scripts/log_symptom.py \
  --type "허리디스크" --severity "중등도" --description "허리 왼쪽 통증"
```

### 일일 건강 체크인
```bash
python3 {baseDir}/scripts/track_health.py \
  --sleep-hours 7 --sleep-quality 8 --steps 8500 \
  --workout --stress 3 --water 2000
```

### PT 숙제 관리
```bash
python3 {baseDir}/scripts/log_pt_homework.py add \
  --exercise "플랭크" --sets 3 --reps "30초" --notes "배에 힘 주고"
python3 {baseDir}/scripts/log_pt_homework.py list
python3 {baseDir}/scripts/log_pt_homework.py complete --id N
```

### PT 출석 체크
```bash
python3 {baseDir}/scripts/check_pt_attendance.py --days 7
```

### 일일 알림
```bash
python3 {baseDir}/scripts/daily_reminder.py --type homework
python3 {baseDir}/scripts/daily_reminder.py --type exercise
```

### 인터랙티브 메뉴
```bash
python3 {baseDir}/scripts/health_tracker.py
```

## 분석 + 루틴

### 운동 루틴 추천
```bash
python3 {baseDir}/scripts/health_cmds.py suggest-routine --level beginner --focus core --duration 15
```

### 증상 패턴 분석
```bash
python3 {baseDir}/scripts/health_cmds.py analyze-symptoms --period 7days
```

### 운동 가이드
```bash
python3 {baseDir}/scripts/health_cmds.py guide-exercise --exercise "플랭크"
```

### 라이프스타일 조언
```bash
python3 {baseDir}/scripts/health_cmds.py lifestyle-advice --category sleep
```

### 종합 건강 체크
```bash
python3 {baseDir}/scripts/health_cmds.py health-checkup
```

### 일일 루틴 체크리스트
```bash
python3 {baseDir}/scripts/daily_routine.py
```

## 안전 원칙 (허리디스크)

- **금지:** 과신전, 회전 (러시안 트위스트), 과도한 굴곡
- **권장:** 중립척추 유지 (플랭크, 데드버그, 버드독), 호흡과 함께, 점진적 강도 증가

## References

| File | 내용 |
|------|------|
| `references/exercises.json` | 허리디스크 안전 운동 DB (코어/하체/유연성/유산소) |
| `references/routines.json` | 운동 루틴 프리셋 |
