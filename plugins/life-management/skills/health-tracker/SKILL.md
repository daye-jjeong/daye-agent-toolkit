---
name: health-tracker
description: 건강 활동을 SQLite DB에 기록하는 스킬. log.py 스크립트로 운동(PT/수영/걷기/홈트), 증상(허리디스크/메니에르병), 식사를 저장한다. 반드시 이 스킬을 사용해야 하는 상황 — 사용자가 운동했다고 말할 때, 아프다고 말할 때, 뭘 먹었다고 말할 때, 식사를 거렸다고 말할 때, PT 숙제를 받았다고 말할 때. "PT 갔다왔어", "허리 아파", "점심 먹었어", "수영 30분", "아침 거름", "플랭크 했어", "어지러워" 등 건강 관련 활동 보고에는 항상 이 스킬을 호출하라. 조회/분석/코칭은 life-coach가 담당하므로 이 스킬이 아님.
---

# Health Tracker

건강 데이터를 `~/life-dashboard/data.db`에 기록한다. 기록 전용 — 조회/분석/코칭은 life-coach가 담당.

## DB 테이블

| 테이블 | 용도 |
|--------|------|
| `health_exercises` | 운동 기록 (PT, 수영, 걷기, 홈트, PT숙제) |
| `health_symptoms` | 증상 기록 (허리디스크, 메니에르병) |
| `health_meals` | 식사 기록 (영양소 자동 추정) |

## 기록

### 운동
```bash
python3 {baseDir}/scripts/log.py exercise --type PT --duration 60 \
  --exercises "플랭크 3세트, 데드버그 10회" --feeling 좋았음
```

PT에서 숙제를 받았으면 `--homework`로 같이 등록:
```bash
python3 {baseDir}/scripts/log.py exercise --type PT --duration 60 \
  --exercises "플랭크, 데드버그" --homework "버드독 10회, 사이드플랭크 3세트"
```

집에서 숙제/홈트:
```bash
python3 {baseDir}/scripts/log.py exercise --type 홈트 --duration 15 \
  --exercises "플랭크 3세트"
```

### 증상
```bash
python3 {baseDir}/scripts/log.py symptom --type 허리디스크 --severity 중등도 \
  --description "왼쪽 통증" --trigger "오래 앉음"
```

### 식사
```bash
python3 {baseDir}/scripts/log.py meal --type 점심 \
  --food "삼겹살, 쌈채소, 된장찌개" --portion 보통

# 거른 경우
python3 {baseDir}/scripts/log.py meal --type 저녁 --skipped --notes "입맛 없음"
```

영양소는 `config/nutrition_db.json` 기반 자동 추정.

## 수정/삭제

잘못 기록한 경우 life-dashboard MCP 도구 또는 직접 SQL로 수정/삭제한다. 스크립트 없음 — LLM이 상황에 맞는 SQL을 직접 작성하는 게 더 유연하다.

## 안전 원칙 (허리디스크)

- **금지:** 과신전, 회전 (러시안 트위스트), 과도한 굴곡
- **권장:** 중립척추 유지 (플랭크, 데드버그, 버드독), 호흡과 함께, 점진적 강도 증가

## References

| File | 내용 |
|------|------|
| `config/nutrition_db.json` | 음식별 영양소 DB (식사 기록 시 칼로리 자동 추정에 사용) |
