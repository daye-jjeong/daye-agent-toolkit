---
name: life-coach
description: 일일/주간 라이프 코칭 — 작업 패턴 분석, 자동화 제안, 건강 넛지
---

# Life Coach Skill

**Version:** 0.1.0 | **Status:** P1

CC/OpenClaw/Calendar 활동 데이터를 기반으로 일일/주간 코칭 리포트를 생성한다.
데이터는 life-dashboard-mcp에서 조회.

## 온디맨드 사용 (/coach)

1. life-dashboard MCP의 `get_today_summary` 도구 호출
2. 결과를 바탕으로 아래 코칭 프레임 적용
3. 세션 내에서 코칭 대화

## 코칭 프레임

### 톤 에스컬레이션

coach_state의 escalation_level에 따라 톤 변경:
- Level 0 (B+C): 데이터 보여주고 질문. 부드러운 넛지.
- Level 1 (B): 3일 연속 10h+ → 직접적 제안.
- Level 2 (A): 7일 연속 or 미개선 → 직설적 지시.

### 일일 코칭 구성

1. **오늘의 정리** — 작업 시간, 레포별 요약, 태그 비율
2. **코칭** — 과작업, 수면 패턴, 집중도 기반 제안
3. **자동화 제안** — 반복 명령/작업 감지
4. **내일 캘린더** — 예정된 일정 (P2에서 추가)
5. **건강 넛지** — 운동, 휴식

### 주간 코칭 구성 (P2에서 추가)

주간 트렌드 분석 + 방향성 코칭.

## 자동화

| Cron | Script | 설명 |
|------|--------|------|
| `0 21 * * *` | `scripts/daily_coach.py` | 매일 21시 코칭 리포트 |
| `0 21 * * 0` | (P2) `scripts/weekly_coach.py` | 주간 코칭 |

## Scripts

| Script | Purpose |
|--------|---------|
| `daily_coach.py` | 일일 코칭 리포트 → 텔레그램 |

## References

| File | 내용 |
|------|------|
| `references/coaching-prompts.md` | LLM 코칭 프롬프트 템플릿 |
