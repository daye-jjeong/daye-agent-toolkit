---
name: health-tracker
description: 운동/증상/PT 트래킹 — SQLite 기록
version: 1.0.0
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Health Tracker

**Version:** 0.3.0
**Updated:** 2026-03-08

건강 데이터를 life-dashboard SQLite DB에 기록하는 트래킹 시스템. 분석/조언은 life-coach 담당.

## 건강 정보

- **허리디스크:** 증상 모니터링, 패턴 분석
- **메니에르병:** 증상 추적
- **PT:** 주 2회 (필라테스)
- **목표:** 매일 운동 + 걷기

## SQLite 테이블

데이터는 `life-dashboard-mcp/life_dashboard.db`에 저장된다.

| 테이블 | 용도 | 주요 컬럼 |
|--------|------|-----------|
| `health_exercises` | 운동 기록 | date, type, duration_min, exercises, feeling |
| `health_symptoms` | 증상 기록 | date, type, severity, description, trigger, status |
| `health_pt_homework` | PT 숙제 | date, exercise, sets_reps, status, completed |

## 사용법

### 증상 기록
```bash
python {baseDir}/scripts/log_symptom.py \
  --type "허리디스크" --severity "중등도" --description "허리 왼쪽 통증"
```

### 운동 기록
```bash
python {baseDir}/scripts/log_exercise.py \
  --type "PT" --duration 60 --exercises "플랭크 3세트, 데드버그 10회" --feeling "좋았음"
```

### PT 숙제 관리
```bash
# 추가
python {baseDir}/scripts/log_pt_homework.py add \
  --exercise "플랭크" --sets 3 --reps "30초" --notes "배에 힘 주고"

# 목록
python {baseDir}/scripts/log_pt_homework.py list

# 완료
python {baseDir}/scripts/log_pt_homework.py complete --id N
```

### PT 출석 체크
```bash
python {baseDir}/scripts/check_pt_attendance.py --days 7
```

### 일일 알림
```bash
python {baseDir}/scripts/daily_reminder.py --type homework
python {baseDir}/scripts/daily_reminder.py --type exercise
```

### 인터랙티브 메뉴
```bash
python {baseDir}/scripts/health_tracker.py
```
