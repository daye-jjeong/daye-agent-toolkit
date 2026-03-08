---
name: life-coach
description: 통합 라이프 코칭 — 작업 패턴 + 건강/운동/식사 분석
version: 1.0.0
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Life Coach Skill

**Version:** 0.4.0 | **Updated:** 2026-03-08

CC/OpenClaw/Calendar 활동 + 건강/운동/식사 데이터를 기반으로 통합 코칭 리포트를 생성한다.
데이터는 life-dashboard-mcp SQLite에서 조회. health-coach 기능을 흡수.

## 온디맨드 사용 (/coach)

스크립트가 데이터를 수집하고, LLM이 직접 코칭을 수행한다.

### 일일 코칭
1. `python3 scripts/daily_coach.py --json` 실행 → JSON 데이터 획득
2. `references/coaching-prompts.md`의 일일 코칭 프레임 적용
3. 데이터 기반으로 코칭 대화

### 주간 코칭
1. `python3 scripts/weekly_coach.py --json` 실행 → JSON 데이터 획득
2. `references/coaching-prompts.md`의 주간 코칭 프레임 적용
3. 주간 트렌드 + 방향성 코칭 대화

### 대안: MCP 도구 사용
life-dashboard MCP의 `get_today_summary` 도구로도 데이터 조회 가능.

## 코칭 프레임

### 톤 에스컬레이션

coach_state의 escalation_level에 따라 톤 변경:
- Level 0 (B+C): 데이터 보여주고 질문. 부드러운 넛지.
- Level 1 (B): 3일 연속 10h+ → 직접적 제안.
- Level 2 (A): 7일 연속 or 미개선 → 직설적 지시.

### 일일 코칭 구성

1. **오늘의 정리** — 작업 시간, 세션 상세, 토큰 사용량
2. **레포별 상세** — 세션 수, 작업시간, 토큰, 요약 (daily_digest에서 이관)
3. **코칭** — 과작업, 수면 패턴, 집중도 기반 제안
4. **패턴 피드백** — 컨텍스트 스위칭, 에러, 테스트/커밋 현황
5. **자동화 제안** — 반복 명령/작업 감지
6. **건강 넛지** — 운동, 휴식

### 주간 코칭 구성

1. **주간 정리** — 총 세션, 시간, 토큰
2. **일별 활동** — 바 차트 (daily_stats 기반)
3. **태그/레포 분포** — 작업 유형 편중 분석
4. **방향성 코칭** — 주간 트렌드 기반 다음 주 방향 제안
5. **다음 주 생각해볼 것** — 패턴 기반 reflect 질문

## 자동화

| Cron | Script | 설명 |
|------|--------|------|
| `0 21 * * *` | `scripts/daily_coach.py` | 매일 21시 코칭 리포트 |
| `0 21 * * 0` | `scripts/weekly_coach.py` | 매주 일요일 21시 주간 코칭 |

## Scripts

| Script | Purpose |
|--------|---------|
| `daily_coach.py` | 일일 데이터 수집 + 템플릿 리포트 → 텔레그램 (건강 섹션 포함) |
| `weekly_coach.py` | 주간 데이터 수집 + 템플릿 리포트 → 텔레그램 (건강 섹션 포함) |
| `health_cmds.py` | 건강 코칭 서브커맨드 (루틴 추천, 증상 분석, 운동 가이드, 라이프스타일 조언, 건강 체크) |
| `track_health.py` | 일일 건강 체크인 기록 (수면, 걸음수, 운동, 스트레스, 수분) |
| `daily_routine.py` | 일일 건강 루틴 체크리스트 |

### 스크립트 플래그

| 플래그 | 동작 |
|--------|------|
| (없음) | 템플릿 리포트 → 텔레그램 전송 (cron 기본) |
| `--dry-run` | 템플릿 리포트 → stdout |
| `--json` | 구조화 JSON 데이터 → stdout (온디맨드 LLM 코칭용) |

## References

| File | 내용 |
|------|------|
| `references/coaching-prompts.md` | LLM 코칭 프레임 (온디맨드에서 LLM이 직접 적용) |
| `references/exercises.json` | 허리디스크 안전 운동 DB (코어/하체/유연성/유산소) |
| `references/routines.json` | 운동 루틴 프리셋 |

## 건강 코칭 (health-coach 통합)

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

### 일일 건강 체크인
```bash
python3 {baseDir}/scripts/track_health.py \
  --sleep-hours 7 --sleep-quality 8 --steps 8500 \
  --workout --stress 3 --water 2000
```

### 일일 루틴 확인
```bash
python3 {baseDir}/scripts/daily_routine.py
```

### 안전 원칙 (허리디스크)

- **금지:** 과신전, 회전 (러시안 트위스트), 과도한 굴곡
- **권장:** 중립척추 유지 (플랭크, 데드버그, 버드독), 호흡과 함께, 점진적 강도 증가
