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
