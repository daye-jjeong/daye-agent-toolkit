---
name: life-coach
description: 통합 라이프 코칭 — 작업 패턴 + 건강/운동/식사 분석
version: 1.0.0
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Life Coach Skill

**Version:** 0.7.0 | **Updated:** 2026-03-14

CC/OpenClaw/Calendar 활동 + 건강/운동/식사 데이터를 기반으로 통합 코칭 리포트를 생성한다.
데이터는 life-dashboard-mcp SQLite에서 조회. health-coach 기능을 흡수.

## 온디맨드 코칭 (/coach)

**당신은 코치다.** 스크립트는 데이터를 수집하는 도구일 뿐이다.
데이터를 단순히 나열하지 마라 — 패턴을 읽고, 해석하고, 제안하고, 질문해라.

### 절차 (반드시 순서대로)

#### Step 1. DB 동기화

데이터가 빠짐없이 모여야 정확한 코칭이 된다. **먼저 sync를 돌려라.**

```bash
# life-dashboard-mcp 디렉토리 기준
python3 {baseDir}/../life-dashboard-mcp/sync_cc.py --date <DATE>
python3 {baseDir}/../life-dashboard-mcp/sync_codex.py --date <DATE>
```

출력에서 synced 세션 수를 확인. 0이면 해당 날짜에 로그가 없는 것.

#### Step 2. JSON 데이터 추출

```bash
# 일일
python3 {baseDir}/scripts/daily_coach.py --json --date <DATE> > /tmp/_coach_data.json
# 주간
python3 {baseDir}/scripts/weekly_coach.py --json > /tmp/_coach_data.json
```

`has_data: false`이면 sync가 안 된 것이니 Step 1을 다시 확인.

#### Step 3. LLM 코칭 + 레포별 요약 생성

`references/coaching-prompts.md` 프레임으로 데이터를 해석하고 **두 가지 파일**을 생성한다.
escalation_level에 따른 톤 변화도 적용 (아래 "톤 에스컬레이션" 참조).

**3a. 레포별 요약 JSON** → `/tmp/repo_summaries.json`

세션의 `summary` 필드는 사용자 프롬프트라 의미 없는 경우가 많다.
`commands`, `user_messages`, `agent_messages`, `files_changed`, `branch` 등을 종합해서
**실제로 뭘 했는지** 구체적으로 요약한다.

**요약 품질 기준:**
- 단순히 "디버깅" "리뷰" 같은 한 단어 X → 어떤 기능/파일을 어떤 목적으로 작업했는지
- 브랜치명이 있으면 포함
- commands에서 실제 작업 맥락 추론 (git diff, pytest, 특정 파일 경로 등)
- "이 요약만 읽고 어떤 기능을 작업했는지 알 수 있는가?" 기준으로 판단

```json
{
  "dy-minions-squad": [
    "[CC] [문서] fix/cron-retry-and-reply-routing — 워치독 스캔 머지 + state-sot-unification worktree 변경사항 리뷰. 머지 보류",
    "[CC] [디버깅] OpenClaw 텔레그램 봇 응답 경로 추적 — openclaw logs에서 lane/session 로그 분석"
  ],
  "cube-backend": [
    "[Codex] [설계] conveyor-belt-monitoring-v2 목업 검증 — RDS/MCP 접근 확인, 유닛 수 수정",
    "[CC] [리뷰] order-queue-str worktree에서 queue.service.ts 변경사항 diff 리뷰"
  ]
}
```

키는 레포 이름(short name), 값은 기능별 작업 요약 리스트. 단일 문자열도 허용.

**각 항목 앞에 반드시:**
- `[CC]` 또는 `[Codex]` — 세션 source (sessions[].source 참조)
- `[태그]` — 작업 유형. summary가 부정확하면 commands/messages에서 재판단

**3b. 코칭 마크다운** → `/tmp/coaching.md`

**3a의 레포별 요약을 먼저 완성한 뒤** 코칭을 작성한다. "오늘의 정리"는 레포별 요약의 상위 집약이어야 하기 때문.

코칭 결과를 마크다운으로 저장:
- 섹션 헤더 사용: `## 오늘의 정리`, `## 코칭`, `## 내일 이어할 것` 등
- **레포별 상세는 여기에 넣지 않는다** (3a의 JSON이 HTML "레포별 작업" 섹션에 직접 들어감)

**"오늘의 정리" 필수 항목:**
- CC 세션 수/시간/토큰, Codex 세션 수/시간/토큰 (source별 분리)
- 각 세션이 어떤 레포에서 무슨 작업이었는지 한줄 요약 (3a 기반)
- 태그 분포

**이 단계를 건너뛰면 HTML에 코칭이 빠지고 세션 원문이 그대로 노출된다.**

#### Step 4. HTML 리포트 생성

```bash
# 일일 — --coaching + --repo-summaries 둘 다 전달
python3 {baseDir}/scripts/daily_report.py \
  --input /tmp/_coach_data.json \
  --coaching /tmp/coaching.md \
  --repo-summaries /tmp/repo_summaries.json
open /tmp/daily_report.html

# 주간
python3 {baseDir}/scripts/weekly_report.py \
  --input /tmp/_coach_data.json \
  --coaching /tmp/coaching.md \
  --repo-summaries /tmp/repo_summaries.json
open /tmp/weekly_report.html
```

#### 의도 확인

사용자가 특정 부분만 요청하면 해당 섹션만 깊게 분석.
아무 말 없으면 `references/coaching-prompts.md` 전체 프레임 적용.

#### 대안: MCP 도구 사용
life-dashboard MCP의 `get_today_summary` 도구로도 데이터 조회 가능.

## 코칭 프레임

### 톤 에스컬레이션

coach_state의 escalation_level에 따라 톤 변경:
- Level 0 (B+C): 데이터 보여주고 질문. 부드러운 넛지.
- Level 1 (B): 3일 연속 10h+ → 직접적 제안.
- Level 2 (A): 7일 연속 or 미개선 → 직설적 지시.

### 일일 코칭 구성

1. **오늘의 정리** — 작업 시간, 세션 상세, 토큰 사용량
2. **레포별 상세** — 세션 수, 작업시간, 핵심 요약, 커밋 여부
3. **집중도 지표** — 세션 평균 길이, 짧은 세션(<15분) 비율, 작업 완료율(has_commits)
4. **코칭** — 행동 신호/반복 패턴/과작업/수면 패턴 기반 제안
5. **자동화 제안** — 반복 명령/패턴 감지
6. **내일 이어할 것** — 진행중 작업
7. **건강** — check_in, exercises, meals, symptoms
8. **유통기한** — pantry_expiry (만료/임박)
9. **마무리 질문** — 데이터 기반 reflection 질문 1개

### 주간 코칭 구성

1. **주간 정리** — 총 세션, 시간, 토큰
2. **태그·레포 분포** — 태그별/레포별 비율, 편중 분석
3. **요일별 생산성** — daily[].work_hours 기반 생산적인 요일 패턴
4. **휴식 패턴** — 무작업일 수 및 시점
5. **방향성 코칭** — weekly_signals + 이전 코칭 연속성 추적
6. **주간 건강 요약** — exercises, meals, check_ins
7. **다음 주 생각해볼 것** — 패턴 기반 reflect 질문
8. **주간 점검** — review_items 데이터 기반 4종 점검 + 교정

### 주간 점검 절차

주간 코칭에서 `review_items` 데이터를 확인하고 다음을 교정한다:

1. **미분류 태그 (untagged_sessions)**: "기타"로 분류된 세션의 raw_json을 보고 올바른 태그로 수정. 반복되는 패턴이면 `_sync_common.py`의 TAG_KEYWORDS에 키워드 추가.
2. **미분류 mistake (uncategorized_mistakes)**: 분류되지 않은 mistake 신호를 확인하고 `references/mistake-categories.json`에 새 키워드 추가.
3. **빈 summary (empty_summaries)**: summary가 비어있는 세션을 확인. sync 로직 개선이 필요한지 판단.
4. **stale worktree (stale_worktrees)**: 오래된 worktree가 있으면 머지 또는 정리 여부를 사용자에게 제안.

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
| `daily_report.py` | 일일 HTML 리포트 생성 → /tmp/daily_report.html (`--coaching` 지원) |
| `weekly_report.py` | 주간 HTML 리포트 생성 → /tmp/weekly_report.html (`--coaching` 지원) |
| `timeline_html.py` | 인터랙티브 타임라인 HTML (standalone / 리포트에 임베드) |
| `timeline_chart.py` | PNG 타임라인 차트 생성 → /tmp/work_timeline.png |
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
