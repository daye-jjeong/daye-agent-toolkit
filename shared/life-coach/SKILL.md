---
name: life-coach
description: 통합 라이프 코칭 — 작업 패턴 + 건강/운동/식사 분석
version: 0.7.0
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

#### Step 1. 열린 세션 스캔 + 미요약 세션 요약

```bash
# 열린 CC 세션을 SQLite에 기록
python3 {baseDir}/../../cc/work-digest/scripts/active_session_scanner.py

# 미요약 세션 확인
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py unsummarized --date <DATE>
```

미요약 세션이 있으면, topic을 보고 태그+요약을 생성하여 업데이트:

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py update-summary \
    --session-id <SID> --date <DATE> --tag "태그" --summary "요약"
```

#### Step 2. JSON 데이터 추출

```bash
# 일일 — 파일명에 날짜 포함 (덮어쓰기 방지)
python3 {baseDir}/scripts/daily_coach.py --json --date <DATE> > /tmp/_coach_data_<DATE>.json
# 주간
python3 {baseDir}/scripts/weekly_coach.py --json > /tmp/_coach_data_weekly_<DATE>.json
```

`has_data: false`이면 sync가 안 된 것이니 Step 1을 다시 확인.

#### Step 3. LLM 코칭 + 레포별 요약 생성

`references/coaching-prompts.md` 프레임으로 데이터를 해석하고 **두 가지 파일**을 생성한다.
escalation_level에 따른 톤 변화도 적용 (아래 "톤 에스컬레이션" 참조).

**3a-1. 토픽 분해**

각 세션의 session_content를 보고 **작업 단위별로 분해**한다.

토픽 분리 기준:
- 다른 레포로 전환 → 별도 토픽
- 다른 브랜치로 전환 → 별도 토픽
- 명확히 다른 목적의 작업 → 별도 토픽
- 같은 목적의 연속 작업 → 하나로 합침

한 작업만 한 세션은 토픽 1개. 무리하게 쪼개지 마라.

**토픽 = 기능 단위** (활동 유형이 아님):
- 같은 기능의 설계→구현→리뷰는 **하나의 토픽**으로 합침
- 나쁜 분해: [설계] spec / [코딩] 구현 / [리뷰] PR review (활동 유형별)
- 좋은 분해: pipeline-redesign — spec + 구현 + 리뷰 완료 (기능 단위)

**토픽별 필수 필드:**
- `tag`: 가장 비중 큰 활동 유형 (코딩, 설계, 디버깅 등)
- `summary`: 무엇을/왜/결과/의사결정 포함. 코칭에서 태스크 관리/제안/우선순위 판단에 쓸 수 있는 수준
- `repo`: 작업한 레포
- `start_at`: 작업 시작 시각 (file_timeline에서 추출 가능하면 실제 시간, 아니면 추정)
- `duration_estimate_min`: 소요 시간
- `status`: completed / in_progress / blocked / follow_up
- `follow_up`: 후속 작업이나 블로커 설명 (없으면 생략)

**요약 품질 기준 (코칭 활용 수준):**
- 이 요약만 읽고 "다음에 뭘 해야 하는지", "이 작업이 왜 중요한지" 판단할 수 있어야 함
- 반복 패턴/문제는 명시적으로 기록 (예: "rule 추가했는데 계속 반복됨")
- 토픽 간 인과관계가 있으면 언급 (예: "리포트 품질 문제 → pipeline-redesign 착수")

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py update-topics \
    --session-id <SID> --date <DATE> \
    --topics '[{"tag":"코딩","summary":"pipeline-redesign — 3계층 분리 설계 + 6개 테이블 구현 + 소비자 전환 + 리뷰 후 머지 완료","repo":"daye-agent-toolkit","start_at":"2026-03-16T12:27:00+09:00","duration_estimate_min":118,"status":"completed"},{"tag":"설계","summary":"오케스트레이터 개편 — 태스크 분해/위임 재정의, AGENTS.md 수정","repo":"dy-minions-squad","start_at":"2026-03-16T14:00:00+09:00","duration_estimate_min":120,"status":"in_progress","follow_up":"워커 위임 테스트 필요"}]'
```

**3a-2. 세션 요약 + 상태 업데이트**

update-topics를 실행한 세션도 update-summary로 상태를 업데이트한다.
JSON 데이터의 각 세션을 확인하고, summary가 부정확하거나 topic 수준이면 `commands`, `user_messages`, `agent_messages`, `files_changed`, `branch`를 종합해서 구체적인 요약으로 업데이트한다.

**요약 품질 기준:**
- **무엇을**(어떤 기능/모듈) **왜**(어떤 문제/목적) **결과**(뭐가 만들어졌거나 바뀌었는지) 중심
- 브랜치명, worktree 이름이 있으면 포함
- **수단(명령어)을 적지 마라** — "git log로 확인", "rg로 검색" 같은 건 수단이지 결과가 아님
- **"이 요약만 읽고 어떤 기능이 어떻게 바뀌었는지, 다음에 뭘 해야 하는지 알 수 있는가?"** 기준

**상태 마커 (필수):**
요약 앞에 반드시 상태를 붙인다:
- `[완료]` — 작업이 끝남 (커밋, 머지, 배포 등)
- `[진행중]` — 아직 작업 중이거나 다음 세션에서 이어야 함
- `[블로커: ...]` — 다른 사람/시스템의 응답이 필요해서 멈춤
- `[후속: ...]` — 이 세션에서 발견한 것에 대한 다음 액션

**의사결정 컨텍스트:**
왜 그런 선택을 했는지 이유가 있으면 포함 (예: "gpt-5.4→sonnet 변경 — 비용 절감 + 응답 품질 유사")

**나쁜 예 (금지):**
- `"설계 논의"` ← 뭘 설계했는지 모름
- `"PR 리뷰"` ← 어떤 PR인지 모름
- `"git log/diff로 변경 이력 확인"` ← 수단
- `"order status 점검. Datadog 로그 확인 필요"` ← 상태 없음, 했는지 안 했는지 모름

**좋은 예:**
- summary: `"session logger 파이프라인 전면 개편 — 열린 세션 누락 해결. active_session_scanner + date-split 구현"` + `--status completed`
- summary: `"kemii MVP 설계 — spec + plan + HTML 목업 작성 완료"` + `--status follow_up --follow-up "다음 세션에서 구현 착수"`
- summary: `"order status/item status 전환 흐름 점검 — 비정상 패턴 의심"` + `--status blocked --follow-up "Datadog 로그 확인 + 백엔드 개발자 공유 필요"`
- summary: `"OpenClaw 모델 변경 — mingming gpt-5.4→sonnet (비용 절감). opus 추가"` + `--status completed`

```bash
# 각 세션에 대해 반복. 상태 마커는 summary에 넣지 말고 --status / --follow-up으로 분리.
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py update-summary \
    --session-id <SID> --date <DATE> --tag "태그" --summary "구체적 요약" \
    --status completed \
    --follow-up "다음 액션 (없으면 생략)"
```

`--status` 값: `completed`, `in_progress`, `blocked`, `follow_up`
`--follow-up`: 블로커 설명이나 다음 액션 (없으면 생략)

**모든 세션에 대해 반복.** 이 요약이 타임라인과 레포별 작업 양쪽에 그대로 사용된다.

**3b. 코칭 마크다운** → `/tmp/coaching_<DATE>.md`

**3a를 먼저 완성한 뒤** 코칭을 작성한다.

코칭 결과를 마크다운으로 저장:
- 섹션 헤더 사용: `## 오늘의 정리`, `## 코칭`, `## 내일 이어할 것` 등

**"오늘의 정리" 필수 항목:**
- CC 세션 수/시간/토큰, Codex 세션 수/시간/토큰 (source별 분리)
- 각 세션이 어떤 레포에서 무슨 작업이었는지 한줄 요약 (3a 기반)
- 태그 분포

**이 단계를 건너뛰면 HTML에 코칭이 빠지고 세션 원문이 그대로 노출된다.**

#### Step 3b-1. 이전 코칭 참조

코칭 생성 전에 어제 코칭 + pending 태스크 + open follow-up을 확인:

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py previous-coaching --date <DATE>
```

이 출력(yesterday_coaching, pending_tasks, open_followups)을 코칭 생성 시 참조하여:
- 어제 태스크 제안 이행 여부 판단
- follow-up 에스컬레이션 결정
- 연속 패턴 분석

#### Step 3e. 코칭 저장

코칭 마크다운을 생성한 뒤, **섹션별로 분해**하여 DB에 저장:

```bash
# 코칭 저장 (sections JSON은 LLM이 마크다운에서 분해)
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py save-coaching \
    --date <DATE> --period daily \
    --content /tmp/coaching_<DATE>.md \
    --sections '{"summary":"...","structure_review":"...","coaching":"...","question":"..."}'

# 태스크 제안 저장 (각 제안마다 반복)
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py save-task \
    --date <DATE> --description "태스크 설명" --estimated-min 30 --priority 1 --source-type coaching

# 태스크 해소 (LLM이 판단 가능한 것)
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py resolve-task \
    --id <TASK_ID> --status done --date <DATE> --method auto

# Follow-up 해소
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py resolve-followup \
    --id <CHAIN_ID> --status resolved --date <DATE> --note "해소 사유"
```

#### Step 4. HTML 리포트 생성

```bash
# 일일
python3 {baseDir}/scripts/daily_report.py \
  --input /tmp/_coach_data_<DATE>.json \
  --coaching /tmp/coaching_<DATE>.md
open /tmp/daily_report_<DATE>.html

# 주간
python3 {baseDir}/scripts/weekly_report.py \
  --input /tmp/_coach_data_weekly_<DATE>.json \
  --coaching /tmp/coaching_weekly_<DATE>.md
open /tmp/weekly_report_<DATE>.html
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
2. **레포별 상세** — 세션 수, 작업시간, 핵심 요약, status/follow_up
3. **집중도 지표** — 세션 평균 길이, 짧은 세션(<15분) 비율, 작업 완료율
4. **구조 리뷰** — 블로커 점검, 후속 작업 위험, 빠진 것, 구조 문제 지적
5. **태스크 제안** — 내일 해야 할 구체적 태스크 (예상 시간 + 우선순위)
6. **코칭** — 의사결정 패턴 분석, 시행착오 예방, 시간대 적절성
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

1. **미분류 태그 (untagged_sessions)**: "기타"로 분류된 세션의 session_content를 보고 올바른 태그로 수정. 반복되는 패턴이면 `activity_writer.py`의 TAG_KEYWORDS에 키워드 추가.
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
