---
name: life-coach
description: 통합 라이프 코칭 — 작업 패턴 + 건강/운동/식사 분석
version: 0.8.0
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Life Coach Skill

CC/OpenClaw/Calendar 활동 + 건강/운동/식사 데이터를 기반으로 통합 코칭 리포트를 생성한다.
데이터는 life-dashboard-mcp SQLite에서 조회.

**당신은 코치다.** 스크립트는 데이터를 수집하는 도구일 뿐이다.
데이터를 단순히 나열하지 마라 — 패턴을 읽고, 해석하고, 제안하고, 질문해라.

## 스킬 경계

| 스킬 | 책임 | 이 스킬이 하지 않는 것 |
|------|------|----------------------|
| **life-coach** | 코칭 생성 + 저장 + HTML 리포트 | 건강 기록/루틴, 토픽 생성 가이드 |
| **work-digest** | 세션 기록 + 토픽 분해 + 요약 가이드 | 코칭 |
| **health-tracker** | 운동/증상/PT/체크인 기록 + 루틴 + 분석 | 코칭 통합 |

## 온디맨드 코칭 (/coach)

### Phase 1: 데이터 준비

#### 1-1. 열린 세션 스캔

```bash
python3 {baseDir}/../../cc/work-digest/scripts/active_session_scanner.py
```

#### 1-2. 미요약 세션 확인 + 요약

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py unsummarized --date <DATE>
```

미요약 세션이 있으면 태그+요약을 생성하여 업데이트:

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py update-summary \
    --session-id <SID> --date <DATE> --tag "태그" --summary "요약" \
    --status completed --follow-up "다음 액션 (없으면 생략)"
```

**요약 작성 기준은 work-digest SKILL.md "Step 2: 토픽 생성 (LLM)" 참조.** 여기서 중복 정의하지 않는다.

`--status` 값: `completed`, `in_progress`, `blocked`, `follow_up`

#### 1-3. 토픽이 없으면 분해

session_topics가 없으면 work-digest 스킬의 "정리해줘" 절차를 실행한다. 상세: work-digest SKILL.md.

#### 1-4. JSON 데이터 추출

```bash
# 일일
python3 {baseDir}/scripts/daily_coach.py --json --date <DATE> > /tmp/_coach_data_<DATE>.json
# 주간
python3 {baseDir}/scripts/weekly_coach.py --json > /tmp/_coach_data_weekly_<DATE>.json
```

`has_data: false`이면 Phase 1을 다시 확인.

### Phase 2: 코칭 생성

#### 2-1. 이전 코칭 참조

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py previous-coaching --date <DATE>
```

출력(yesterday_coaching, pending_tasks, open_followups)을 참조하여:
- 어제 태스크 제안 이행 여부 판단
- follow-up 에스컬레이션 결정
- 연속 패턴 분석

#### 2-2. 코칭 마크다운 생성

`references/coaching-prompts.md` 프레임으로 데이터를 해석하고 `/tmp/coaching_<DATE>.md` 생성.
섹션 헤더 사용: `## 오늘의 정리`, `## 코칭`, `## 내일 이어할 것` 등.

**"오늘의 정리" 필수 항목:**
- CC 세션 수/시간/토큰, Codex 세션 수/시간/토큰 (source별 분리)
- 각 세션이 어떤 레포에서 무슨 작업이었는지 한줄 요약
- 태그 분포

### Phase 3: 저장 + 리포트

#### 3-1. 코칭 저장

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py save-coaching \
    --date <DATE> --period daily \
    --content /tmp/coaching_<DATE>.md \
    --sections '{"summary":"...","structure_review":"...","coaching":"...","question":"..."}'
```

#### 3-2. 태스크 + follow-up 관리

```bash
# 태스크 제안 저장
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py save-task \
    --date <DATE> --description "태스크 설명" --estimated-min 30 --priority 1 --source-type coaching

# 태스크 해소
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py resolve-task \
    --id <TASK_ID> --status done --date <DATE> --method auto

# Follow-up 해소
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py resolve-followup \
    --id <CHAIN_ID> --status resolved --date <DATE> --note "해소 사유"
```

#### 3-3. HTML 리포트

```bash
# 일일
python3 {baseDir}/scripts/daily_report.py \
  --input /tmp/_coach_data_<DATE>.json --coaching /tmp/coaching_<DATE>.md
open /tmp/daily_report_<DATE>.html

# 주간
python3 {baseDir}/scripts/weekly_report.py \
  --input /tmp/_coach_data_weekly_<DATE>.json --coaching /tmp/coaching_weekly_<DATE>.md
open /tmp/weekly_report_<DATE>.html
```

## 의도 확인

사용자가 특정 부분만 요청하면 해당 섹션만 깊게 분석.
아무 말 없으면 `references/coaching-prompts.md` 전체 프레임 적용.
life-dashboard MCP의 `get_today_summary` 도구로도 데이터 조회 가능.

## 톤 에스컬레이션

coach_state의 escalation_level에 따라 톤 변경:
- Level 0 (B+C): 데이터 보여주고 질문. 부드러운 넛지.
- Level 1 (B): 3일 연속 10h+ → 직접적 제안.
- Level 2 (A): 7일 연속 or 미개선 → 직설적 지시.

## 코칭 구성

일일/주간 섹션 구성과 상세 프롬프트는 `references/coaching-prompts.md` 참조.

**일일**: 오늘의 정리 → 레포별 상세 → 집중도 지표 → 구조 리뷰 → 태스크 제안 → 코칭 → 건강 → 유통기한 → 마무리 질문
**주간**: 주간 정리 → 태그·레포 분포 → 요일별 생산성 → 휴식 패턴 → Follow-up 현황 → 방향성 코칭 → 건강 요약 → 다음 주 질문 → 주간 점검

### 주간 점검 (review_items 기반)

1. **미분류 태그**: "기타" 세션 → 올바른 태그 수정. 반복 패턴은 TAG_KEYWORDS에 추가.
2. **미분류 mistake**: `references/mistake-categories.json`에 새 키워드 추가.
3. **빈 summary**: sync 로직 개선 필요한지 판단.
4. **stale worktree**: 머지 또는 정리 여부를 사용자에게 제안.

## 자동화

| Cron | Script | 설명 |
|------|--------|------|
| `0 21 * * *` | `scripts/daily_coach.py` | 매일 21시 코칭 리포트 |
| `0 21 * * 0` | `scripts/weekly_coach.py` | 매주 일요일 21시 주간 코칭 |

## Scripts

| Script | Purpose |
|--------|---------|
| `daily_coach.py` | 일일 데이터 수집 + 템플릿 리포트 → 텔레그램 |
| `weekly_coach.py` | 주간 데이터 수집 + 템플릿 리포트 → 텔레그램 |
| `daily_report.py` | 일일 HTML 리포트 → /tmp/ (`--coaching` 지원) |
| `weekly_report.py` | 주간 HTML 리포트 → /tmp/ (`--coaching` 지원) |
| `timeline_html.py` | 인터랙티브 타임라인 HTML |
| `timeline_chart.py` | PNG 타임라인 차트 → /tmp/work_timeline.png |

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
| `references/mistake-categories.json` | mistake 키워드 → 카테고리 매핑 |
