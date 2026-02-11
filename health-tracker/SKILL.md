---
name: health-tracker
description: 건강 상태 모니터링 + 운동/PT/증상 트래킹. Obsidian vault에 Dataview-queryable markdown으로 기록. 허리디스크/메니에르 증상 추적, PT 숙제 관리, 운동 기록, 패턴 분석.
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Health Tracker

**Version:** 0.2.0
**Updated:** 2026-02-11

건강 데이터를 Obsidian vault에 기록하고 분석하는 통합 건강 관리 시스템.

## 건강 정보

- **허리디스크:** 증상 모니터링, 패턴 분석
- **메니에르병:** 증상 추적
- **PT:** 주 2회 (필라테스)
- **목표:** 매일 운동 + 걷기

## Obsidian 저장 구조

```
~/mingming-vault/health/
  symptoms/          # 증상 기록
    2026-02-11_허리디스크.md
  exercises/         # 운동 기록
    2026-02-11_PT_60min.md
  pt-homework/       # PT 숙제
    2026-02-11_플랭크.md
  check-ins/         # 일일 건강 체크인 (health-coach에서 기록)
    checkin-2026-02-11.md
```

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
python {baseDir}/scripts/log_pt_homework.py complete --file "2026-02-11_플랭크.md"
```

### 패턴 분석
```bash
python {baseDir}/scripts/analyze_health.py --period week
python {baseDir}/scripts/analyze_health.py --period month
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

## Frontmatter Schema

### Symptom
```yaml
date: 2026-02-11
timestamp: "2026-02-11 14:30"
type: 허리디스크
severity: 중등도
status: 진행중
trigger: 오래 앉아있음
```

### Exercise
```yaml
date: 2026-02-11
timestamp: "2026-02-11 19:00"
type: PT
duration_min: 60
exercises: "플랭크 3세트, 데드버그 10회"
feeling: 좋았음
```

### PT Homework
```yaml
date: 2026-02-11
exercise: 플랭크
sets_reps: "3세트 x 30초"
status: 할 일
completed: false
```

## Dataview 쿼리 예시

```dataview
TABLE date, type, severity, status
FROM "health/symptoms"
SORT date DESC
LIMIT 10
```

```dataview
TABLE date, type, duration_min, feeling
FROM "health/exercises"
WHERE type = "PT"
SORT date DESC
```
