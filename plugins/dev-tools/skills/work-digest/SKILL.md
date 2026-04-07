---
name: work-digest
description: 일일 작업 다이제스트 — CC 세션 자동 기록 + 데이터 준비 파이프라인. 세션 수집, 요약, task 분해를 담당한다. "오늘 뭐 했지?", "작업 정리", "요약해줘" 등의 요청이나, life-coach 등 다른 스킬이 데이터 준비를 필요로 할 때 사용.
---

# Work Digest Skill

CC 세션 로그를 자동 기록하고, 데이터 준비 파이프라인으로 task 단위를 분해+요약한다.

## 스킬 경계

| 역할 | 담당 |
|------|------|
| 세션 기록 (hook) | work-digest |
| 데이터 준비 (수집→요약→task) | work-digest |
| 코칭 생성 + 리포트 | life-coach |

## 구조

```
work-digest/
├── SKILL.md
├── scripts/
│   ├── session_logger.py         # SessionEnd hook — 세션 메타+원본 자동 기록 (LLM 없음)
│   ├── active_session_scanner.py # 열린 세션 스캔 + 기록
│   ├── extract_session.py        # .jsonl → segments 추출 (결정적)
│   ├── extract_day.py            # 하루치 전체 세션 segments 추출
│   └── validate_tasks.py         # task 검증
```

## 자동 기록 (LLM 없음, 항상 동작)

### SessionEnd hook

```
세션 종료 → session_logger.py
  → parse_transcript_by_date(): 트랜스크립트를 날짜별 분할
  → sessions INSERT (start_at, end_at, duration_min, tokens, repo)
  → session_content INSERT (user_messages, files_changed, commands)
  → daily_stats 갱신
  → signals 추출 (LLM subprocess — decision/mistake/pattern)
  → 텔레그램 알림
```

## 데이터 준비 파이프라인

사용자 요청이나 다른 스킬(life-coach 등)의 호출로 실행된다.
5단계를 순서대로 따른다.

**원칙: 코드가 시간, LLM이 내용.**

### Step 1: 세션 수집

```bash
python3 {baseDir}/scripts/active_session_scanner.py
```

열린 세션을 탐색하여 DB에 반영한다.

### Step 2: 세션 요약

```bash
# 미요약 세션 확인
python3 {baseDir}/../../shared/life-dashboard-mcp/activity_writer.py unsummarized --date <DATE>
```

미요약 세션마다 태그+요약+status를 생성하여 저장:
```bash
python3 {baseDir}/../../shared/life-dashboard-mcp/activity_writer.py update-summary \
    --session-id <SID> --date <DATE> --tag "태그" --summary "요약" \
    --status completed
```
- `--status`: `completed`, `in_progress`, `blocked`, `follow_up`
- `--follow-up`: follow_up/blocked일 때 구체적 다음 행동 명시

### Step 3: Segment 추출 (결정적)

```bash
python3 {baseDir}/scripts/extract_day.py --date <DATE>
```

### Gate A: 데이터 정합성 검증

Step 3 완료 후, Step 4 진입 전에 실행.

1. **누락 세션 등록**: extract_day.py가 발견한 세션이 sessions 테이블에 없으면 자동 INSERT (repo, start_at, end_at, duration_min을 트랜스크립트에서 추출)
2. **미요약 확인**: `unsummarized --date <DATE>` 재실행 → 0건이어야 통과
3. **eval 일괄 처리**: `-claude` 레포 세션은 tag="eval", summary="자동 스킬 eval 세션"으로 일괄 처리
4. **가짜 건강 데이터 삭제**: eval 세션 시간대와 겹치는 건강 기록(health_exercises, health_symptoms, health_meals) 삭제
5. 미요약 잔존 시 해당 세션 요약 후 재확인

출력: 세션별 segments (시간 경계 확정, idle gap 기준 분리, 각 구간의 user messages + file edits)

### Step 4: Task 생성 (LLM)

extract_day.py `--flat` 출력과 기존 projects 목록을 참고하여 task를 생성한다.

```bash
# segment flat list
python3 {baseDir}/scripts/extract_day.py --date <DATE> --no-scan --flat

# 기존 projects 목록 (LLM에 함께 전달)
python3 -c "import sys; sys.path.insert(0,'{baseDir}/../../shared/life-dashboard-mcp'); from db import get_conn, get_projects; print([{'id':p['id'],'name':p['name'],'repo':p['repo']} for p in get_projects(get_conn(), 'active')])"
```

**핵심 원칙: task = 사용자가 한 일의 기능 단위. 세션이 아니라 segment 단위로 사고.**

**그룹핑 기준:**
- 같은 레포 + 같은 목표 (hint/files로 판단) → 1 task
- 다른 레포 → 다른 task
- 같은 레포 + 다른 목표 → 다른 task
- 한 세션의 segments가 여러 task에 분산될 수 있다
- **애매하면 분리.** project 레벨에서 연결되므로 과도한 병합보다 분리가 안전.

**segment 전수 검증:** 모든 input segment가 정확히 1개 task에 할당. 누락·중복 불허.

**project 연결:** 기존 projects 목록에 매칭되면 해당 name 사용, 없으면 새 name 제시.

**출력 형식:**
```json
[
  {
    "tag": "설계",
    "summary": "왜 → 뭘 → 결과 형식의 요약",
    "repo": "dy-minions-squad",
    "segments": [{"sid":"xxx","date":"YYYY-MM-DD","start":"HH:MM","end":"HH:MM","dur":N}, ...],
    "duration_min": 96,
    "status": "completed",
    "project": "프로젝트명"
  }
]
```

**완성 예시**: `{baseDir}/references/topic-creation-guide.md` 참조

### Step 5: 저장 + 검증

```bash
python3 {baseDir}/../../shared/life-dashboard-mcp/activity_writer.py update-tasks \
    --date <DATE> --tasks '<JSON array>'

python3 {baseDir}/scripts/validate_tasks.py --date <DATE>
```

### Gate B-1: 구조 검증

    python3 {baseDir}/scripts/validate_tasks.py --fix --date <DATE>

- eval 세션(`-claude` 레포) 면제, repo NULL 자동 채움, eval 태그 자동 변경
- 에러 0이면 Gate B-2로 진행
- 에러 있으면 해당 task 재생성 후 재검증 (최대 2회)
- 2회 실패 시 파이프라인 중단, 사용자에게 보고

### Gate B-2: 내용 품질 검증 (LLM 자기 검증)

**이 Gate를 건너뛰지 마라.** 스크립트 검증(B-1)은 구조만 본다. 내용이 실제로 유용한지는 여기서 판단한다.

`daily_coach.py --json` 출력의 tasks를 전체 읽고, 아래 체크를 **하나씩** 수행한다. 문제 발견 시 즉시 수정하고 Gate B-1부터 재실행. 모든 항목 통과해야 Phase 2로 진행.

#### 체크 1: 기능 단위로 묶여 있는가

task 목록을 위에서 아래로 읽으며 확인:
- 같은 목표의 연속 segment가 쪼개져 있으면 → 1개 task로 병합
- "이 task들을 사용자에게 보여주면, 사용자가 '이건 하나의 작업인데 왜 쪼개져 있어?'라고 할 것인가?" → 그렇다면 병합

병합 시:
```bash
python3 {baseDir}/../../shared/life-dashboard-mcp/activity_writer.py update-tasks \
    --date <DATE> --tasks '<병합된 JSON array>'
```

#### 체크 2: 불필요 task 없는가

- /exit, /clear, /login, /reload 같은 단순 명령이 독립 task → 인접 task에 포함하거나 삭제
- duration이 비정상 (2분 세션인데 45분으로 표시) → duration_min 수정

#### 체크 3: 요약이 코칭에 쓸 수 있는 수준인가

각 task summary를 읽고:
- "이 요약만 보고 코칭할 수 있는가?" — 뭘 했는지, 왜 했는지, 결과가 뭔지
- ".env 설정 후 /login 실행." → 부족. "텔레그램 봇 연결 시도 — 설정 + pair code 디버깅, 실패" → 충분
- 명령어 나열, 파일명만 나열은 부족

#### 체크 4: 태그-활동 일치

- 코드 수정했는데 "리뷰", 로그만 봤는데 "코딩" 등
- user_messages를 보고 실제 뭘 했는지 확인

#### 체크 5: eval 혼입

- eval 세션 내용이 실제 작업 task에 섞이지 않았는지

#### 통과 기준

- **PASS**: 모든 항목 이상 없음 → Phase 2로 진행
- **FAIL**: 하나라도 문제 → 수정 후 Gate B-1부터 재실행 (최대 2회)
- WARN 없음. 애매하면 고쳐라.

## 데이터 흐름

```
트랜스크립트 .jsonl (CC 실시간)
  ↓ SessionEnd hook
sessions + session_content + daily_stats + signals (자동)
  ↓ 데이터 준비 파이프라인 (사용자 요청 or life-coach 호출)
Step 1: scanner → 열린 세션 DB 반영
Step 2: unsummarized → 세션 요약
Step 3: extract_day.py → segments (결정적)
Step 4: LLM → tasks (기능 단위, segment 기반)
Step 5: update-tasks + validate
  ↓ life-coach
daily_report + coaching
```
