---
name: health-coach
description: Health Tracker 데이터를 분석하여 맞춤 건강 조언 제공. 허리디스크 안전 운동 추천, 증상 패턴 분석, PT 숙제 가이드, 저속노화 루틴 관리. Obsidian vault 기반.
---

# Health Coach

**Version:** 0.3.0
**Updated:** 2026-02-11

Health Tracker가 Obsidian에 기록한 데이터를 분석하여 맞춤형 건강 조언을 제공하는 AI 코치.

## 역할 분리

- **Health Tracker:** 기록/모니터링 전담 → `health/symptoms/`, `health/exercises/`, `health/pt-homework/`
- **Health Coach:** 조언/가이드/분석 전담 + 일일 체크인 → `health/check-ins/`

## 기능

### 1. 운동 루틴 제안 (허리디스크 고려)
- 중립척추 유지 코어 운동 추천
- 과신전/회전 동작 필터링
- 단계별 난이도 조절

### 2. 증상 분석 및 조언
- Obsidian health/ 데이터 기반 패턴 분석
- 빈도, 강도, 트리거 요인 식별

### 3. PT 숙제 가이드
- 자세 상세 설명 + 주의사항
- 변형 동작 (쉽게/어렵게)

### 4. 일일 건강 체크인 (저속노화)
- 수면, 걸음수, 운동, 스트레스, 수분 섭취 기록

### 5. 주간 리포트
- 7일 데이터 종합 분석 + 인사이트

## 사용법

### 운동 루틴 제안
```bash
python {baseDir}/scripts/coach.py suggest-routine --level beginner --focus core --duration 15
```

### 증상 패턴 분석
```bash
python {baseDir}/scripts/coach.py analyze-symptoms --period 7days
```

### PT 숙제 가이드
```bash
python {baseDir}/scripts/coach.py guide-exercise --exercise "플랭크"
```

### 라이프스타일 조언
```bash
python {baseDir}/scripts/coach.py lifestyle-advice --category sleep
```

### 종합 건강 체크
```bash
python {baseDir}/scripts/coach.py health-checkup
```

### 일일 건강 체크인
```bash
python {baseDir}/scripts/track_health.py \
  --sleep-hours 7 --sleep-quality 8 --steps 8500 \
  --workout --stress 3 --water 2000
```

### 일일 루틴 확인
```bash
python {baseDir}/scripts/daily_routine.py
```

### 주간 리포트
```bash
python {baseDir}/scripts/weekly_report.py
```

## Check-in Frontmatter

```yaml
type: check_in
date: 2026-02-11
sleep_hours: 7
sleep_quality: 8
steps: 8500
workout: true
stress: 3
water: 2000
```

## 안전 원칙 (허리디스크)

- **금지:** 과신전 (백익스텐션, 코브라), 회전 (러시안 트위스트), 과도한 굴곡
- **권장:** 중립척추 유지 (플랭크, 데드버그, 버드독), 호흡과 함께, 점진적 강도 증가

## Notes

- 모든 조언은 **의학적 진단/치료 아님** (참고용)
- 심한 통증 시 전문의 상담 권장
