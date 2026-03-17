# Life Coach CLI Reference

온디맨드 코칭 절차에서 사용하는 CLI 명령어 모음. SKILL.md의 Phase 1-3에서 참조.

## Phase 1: 데이터 준비

### 1-1. 열린 세션 스캔

```bash
python3 {baseDir}/../../cc/work-digest/scripts/active_session_scanner.py
```

### 1-2. 미요약 세션 확인

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py unsummarized --date <DATE>
```

### 1-2. 세션 요약 업데이트

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py update-summary \
    --session-id <SID> --date <DATE> --tag "태그" --summary "요약" \
    --status completed --follow-up "다음 액션 (없으면 생략)"
```

`--status` 값: `completed`, `in_progress`, `blocked`, `follow_up`

### 1-4. JSON 데이터 추출

```bash
# 일일
python3 {baseDir}/scripts/daily_coach.py --json --date <DATE> > /tmp/_coach_data_<DATE>.json
# 주간
python3 {baseDir}/scripts/weekly_coach.py --json > /tmp/_coach_data_weekly_<DATE>.json
```

## Phase 2: 코칭 생성

### 2-1. 이전 코칭 참조

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py previous-coaching --date <DATE>
```

## Phase 3: 저장 + 리포트

### 3-1. 코칭 저장

```bash
python3 {baseDir}/../life-dashboard-mcp/activity_writer.py save-coaching \
    --date <DATE> --period daily \
    --content /tmp/coaching_<DATE>.md \
    --sections '{"summary":"...","structure_review":"...","coaching":"...","question":"..."}'
```

### 3-2. 태스크 관리

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
