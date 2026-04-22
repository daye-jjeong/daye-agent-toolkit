# Life Coach CLI Reference

온디맨드 코칭 절차에서 사용하는 CLI 명령어 모음. SKILL.md의 Phase 1-3에서 참조.

## Phase 1: 데이터 준비

세션 수집·요약·토픽 분해는 work-digest 스킬이 담당한다.
work-digest SKILL.md의 데이터 준비 파이프라인(Step 1~5)을 실행한 뒤 아래로 진행.

### 1-1. JSON 데이터 추출 (stderr 분리 필수)

```bash
# 일일 (2>/dev/null로 scanner 로그 분리)
python3 {baseDir}/scripts/daily_coach.py --json --date <DATE> 2>/dev/null > /tmp/_coach_data_<DATE>.json
# 주간
python3 {baseDir}/scripts/weekly_coach.py --json --date <DATE> 2>/dev/null > /tmp/_coach_data_weekly_<DATE>.json
```

## Phase 2: 코칭 생성

### 2-1. 이전 코칭 참조

```bash
python3 {baseDir}/../../../../mcp/life-dashboard/activity_writer.py previous-coaching --date <DATE>
```

## Phase 3: 저장 + 리포트

### 3-1. 코칭 저장

```bash
python3 {baseDir}/../../../../mcp/life-dashboard/activity_writer.py save-coaching \
    --date <DATE> --period daily \
    --content /tmp/coaching_<DATE>.md \
    --sections '{"summary":"...","structure_review":"...","coaching":"...","question":"..."}'
```

### 3-2. 태스크 관리

```bash
# 태스크 제안 저장
python3 {baseDir}/../../../../mcp/life-dashboard/activity_writer.py save-task \
    --date <DATE> --description "태스크 설명" --estimated-min 30 --priority 1 --source-type coaching

# 태스크 해소
python3 {baseDir}/../../../../mcp/life-dashboard/activity_writer.py resolve-task \
    --id <TASK_ID> --status done --date <DATE> --method auto

# Follow-up 해소
python3 {baseDir}/../../../../mcp/life-dashboard/activity_writer.py resolve-followup \
    --id <CHAIN_ID> --status resolved --date <DATE> --note "해소 사유"
```

### 3-3. HTML 리포트

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

---

## 축 1 액션 CLI — 신규

### todo_crud.py

순수 CLI. 대화 없음. stdout JSON, stderr 에러, exit 0 성공 / 1 실패.

**add** — 새 todo를 backlog에 추가
```
python3 todo_crud.py add --title "..." \
    [--done-definition "..."] [--category 업무|개인|건강|재정|관계] \
    [--priority 1|2|3] [--project "..."] [--repo "..."] [--parent-id N] \
    [--quarter "2026Q2"] [--deadline "YYYY-MM-DD"] \
    [--estimated-min N] [--notes "..."]
```
출력: `{"id": N, "title": "...", "status": "backlog"}`

**list** — 필터링된 todo 목록
```
python3 todo_crud.py list [--status backlog|wip|done|blocked|deferred] \
    [--category "..."] [--sort default|priority|deadline] [--limit N]
```
sort=default 정렬: deadline 있는 것 먼저 (임박 순) → priority 높은 순 → 오래된 것 순

**show** — 단일 todo (subtasks 포함)
```
python3 todo_crud.py show --id N
```

**move** — 상태 전환 (검증 포함)
```
python3 todo_crud.py move --id N --status wip|done|blocked|deferred|backlog \
    [--reason "..."] [--force]
```
- WIP 전환: `done_definition` null이면 거부
- WIP 전환: 현재 WIP 2개면 거부 (`--force`로 override, stderr 로그)
- `deferred`: `--reason` 권장
- backlog→wip: started_at 자동
- *→done: done_at 자동

**defer** — `move --status deferred`의 별칭
```
python3 todo_crud.py defer --id N --reason "..."
```

**done** — `move --status done`의 별칭. 부모 todo면 미완료 subtask 확인 (`--force`로 override)
```
python3 todo_crud.py done --id N [--force]
```

### todo_morning.py

```
python3 todo_morning.py [--date YYYY-MM-DD]
```
기본 date: 오늘 (KST).

출력 JSON 스키마:
- `date`: 기준 날짜
- `overdue`: deadline 지난 todos (status NOT IN done/deferred)
- `today_due`: deadline 오늘
- `this_week_due`: deadline +1 ~ +7일
- `current_wip`: status=wip todos
- `backlog_top5`: 기본 정렬 상위 5
- `pending_suggestions`: `task_suggestions` pending 최신 5건 (read-only 참고)

### todo_evening.py

```
python3 todo_evening.py [--date YYYY-MM-DD] [--skip-digest]
```

동작 순서:
1. daily_checkin (morning_intent, morning_wip_ids) 조회
2. `tasks` 조회. 비어있고 `--skip-digest` 아니면 work-digest Step 1-3 실행
3. Step 4(LLM)가 필요하면 `needs_llm_task_generation: true` 반환 → Claude 세션이 수행 후 재호출
4. 실패 시 `fallback: true` + `raw_sessions` 채움
5. loose matching (repo + keyword overlap score ≥ 0.3)

출력 JSON 스키마:
- `date`, `morning_intent`, `morning_wip_ids`, `missing_wip_ids`
- `actual_tasks`: tasks 테이블 rows
- `fallback`: bool
- `raw_sessions`: fallback일 때 채워짐
- `loose_matches`: `[{wip_id, wip_title, matched_tasks: [{..., match_score}]}]`
- `unmatched_actual`: 계획에 없던 예정 외 tasks
- `needs_llm_task_generation`: bool
