# Task/Project 기반 작업 기록 재설계

## 배경

현재 `session_topics`는 세션에 종속되어 있어서:
- 한 세션에서 여러 작업을 해도 1토픽으로 뭉쳐짐
- 여러 세션에서 같은 작업을 해도 연결 불가
- 시간 범위가 세션 전체(idle 포함)로 잡혀서 타임라인이 부정확

## 목표

"내가 언제 뭘 했는지"를 정확히 기록하고 시각화한다.
- 데일리: task 단위로 오늘 뭘 했는지
- 주간/월간: project 단위로 어디에 시간을 쓰고 있는지

## 데이터 계층

```
project: "Juliet 운영 자동화" (주~월 단위)
  └─ task: "cron 구성 점검 + 인터뷰 플로우 설계" (하루 단위)
       └─ segments: 세션별 활동 구간 (분 단위, 코드가 자동 추출)
```

- **segment**: extract_session.py가 idle 5분 기준으로 추출. 별도 테이블 없음 (매번 추출).
- **task**: LLM이 segments를 의미적으로 묶어서 생성. session_topics 대체. **하루 단위** — 이틀 이상 걸치는 작업은 날짜별 task + 같은 project로 연결.
- **project**: task들의 상위 묶음. LLM이 task 생성 시 기존/신규 project에 연결.

## 스키마

### tasks (session_topics 대체)

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                    -- YYYY-MM-DD
    tag TEXT NOT NULL,                     -- 코딩, 설계, 디버깅, ...
    summary TEXT NOT NULL,                 -- LLM 요약 (왜→뭘→결과)
    repo TEXT,                             -- 주 레포 (단축명)
    segments TEXT NOT NULL DEFAULT '[]',   -- JSON: [{"sid":"xxx","date":"YYYY-MM-DD","start":"HH:MM","end":"HH:MM","dur":N}, ...]
    duration_min INTEGER NOT NULL DEFAULT 0, -- segments dur 합
    status TEXT NOT NULL DEFAULT 'completed', -- completed, in_progress, blocked
    follow_up TEXT,                        -- 후속 작업
    project_id INTEGER,                    -- FK → projects (nullable)
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE INDEX idx_tasks_date ON tasks(date);
CREATE INDEX idx_tasks_project ON tasks(project_id);
```

### projects (신규)

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                    -- "Juliet 운영 자동화"
    repo TEXT,                             -- 주 레포
    status TEXT NOT NULL DEFAULT 'active', -- active, completed, paused
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(name, repo)                     -- 동일 project 중복 방지
);
```

### session_topics 폐기

마이그레이션 스크립트에서:
1. session_topics → tasks 변환 (segment 정보 없는 건 세션 start_at/duration으로 폴백)
2. `ALTER TABLE session_topics RENAME TO _session_topics_backup`
3. 검증 완료 후 `DROP TABLE _session_topics_backup` (수동)

## extract_day.py 변경: --flat 모드

현재 출력 (세션별 segments):
```json
[
  {"session_id": "be72d12a", "repo": "dy-minions-squad", "segments": [...]},
  {"session_id": "c19a3a93", "repo": "dy-minions-squad", "segments": [...]}
]
```

`--flat` 추가 출력 (레포별 시간순 flat list):
```json
{
  "dy-minions-squad": [
    {"sid": "c9ef905e", "start": "11:27", "end": "12:39", "dur": 50,
     "hint": "딥패트롤 검증 보강", "files": ["deep-checks.md"]},
    {"sid": "be72d12a", "start": "11:27", "end": "11:56", "dur": 29,
     "hint": "Juliet subagent dispatch", "files": ["core-skills.ts"]},
    ...
  ],
  "cube-backend": [...]
}
```

- `hint`: 첫 사용자 메시지에서 노이즈 제거 후 1줄 (task-notification, skill loading 등 제외)
- `files`: 수정 파일명
- `sid`: task 저장 시 segments에 기록할 session_id

## SKILL.md Step 4 변경: segment 기반 task 생성

### 입력

extract_day.py `--flat` 출력 (레포별 segment timeline)

### LLM 지시 핵심

1. **세션 단위로 사고하지 마라.** segment 단위로 본다.
2. 같은 목표의 segments를 묶어서 1 task. 판단 기준:
   - hint(첫 메시지)와 files가 같은 주제를 가리키면 → 같은 task
   - 다른 레포 → 다른 task
   - 같은 레포 + 다른 목표 → 다른 task
   - **애매하면 분리.** 나중에 project 레벨에서 연결되므로 과도한 병합보다 분리가 안전.
3. 한 세션의 segments가 여러 task에 분산될 수 있다.
4. duration_min = 해당 task에 속하는 segments의 dur 합.
5. 각 task에 기존 project 연결 또는 새 project 생성.
   - LLM에 기존 projects 목록(id + name + repo)을 함께 전달.
   - 기존 project와 매칭되면 해당 id 사용, 없으면 새 project name 제시.
6. **segment 전수 검증**: 모든 input segment가 정확히 1개 task에 할당되어야 한다. 누락·중복 불허.

### 출력 형식

```json
[
  {
    "tag": "설계",
    "summary": "Juliet cron 구성 점검 + 인터뷰 플로우 설계 — ...",
    "repo": "dy-minions-squad",
    "segments": [
      {"sid": "be72d12a", "date": "2026-03-31", "start": "11:27", "end": "11:56"},
      {"sid": "dc9eaa53", "date": "2026-03-31", "start": "12:16", "end": "13:47"}
    ],
    "duration_min": 96,
    "status": "completed",
    "project": "Juliet 운영 자동화"
  },
  ...
]
```

## 타임라인 렌더링 변경

현재: topic당 1개 바 (start_at 위치, duration_estimate_min 길이)
변경: task의 segments를 풀어서 각각 바로 그림. 같은 task의 segments는 같은 색/라벨.

```
timeline_html.py prep():
  for task in tasks:
    for seg in task.segments:
      items.append({
        "repo": task.repo,
        "tag": task.tag,
        "start": seg.start,
        "duration": seg.dur,
        "summary": task.summary,
      })
```

## 데일리 리포트 변경

레포별 작업 섹션: session_topics 대신 tasks를 레포별로 그룹핑. 기존 UI 구조 유지.

## 주간/월간 리포트 (후속)

project 단위로:
- 총 투입 시간 (tasks의 duration_min 합)
- task 히스토리 (날짜별)
- 상태 추이

이 스펙에서는 데일리 리포트 대응까지만 구현. 주간/월간은 후속 작업.

## 마이그레이션

1. projects, tasks 테이블 생성
2. 기존 session_topics → tasks 변환 (idempotent — tasks에 이미 있는 date+summary 조합은 skip):
   - segments 필드: `[{"sid": session_id, "date": date, "start": start_at, "end": end_at}]`
   - project_id: null (수동 연결 또는 후속 배치)
3. `ALTER TABLE session_topics RENAME TO _session_topics_backup`
4. 검증 완료 후 수동 `DROP TABLE _session_topics_backup`
4. db.py, activity_writer.py에서 session_topics 참조를 tasks로 교체
5. daily_coach.py: `get_session_topics()` → `get_tasks()`
6. daily_report.py: topic 기반 → task 기반
7. timeline_html.py: segments 기반 렌더링
8. validate_topics.py → validate_tasks.py

## 영향 범위

| 파일 | 변경 |
|------|------|
| shared/life-dashboard-mcp/db.py | 스키마, get_tasks(), upsert_tasks(), 마이그레이션 |
| shared/life-dashboard-mcp/activity_writer.py | update-topics → update-tasks CLI |
| cc/work-digest/scripts/extract_day.py | --flat 모드 추가 |
| cc/work-digest/scripts/validate_topics.py | → validate_tasks.py |
| cc/work-digest/SKILL.md | Step 4~5 재작성 |
| cc/work-digest/references/topic-creation-guide.md | task 기반으로 재작성 |
| shared/life-coach/scripts/daily_coach.py | get_session_topics → get_tasks |
| shared/life-coach/scripts/daily_report.py | topic → task 기반 렌더링 |
| shared/life-coach/scripts/timeline_html.py | segments 기반 렌더링 |
| shared/life-coach/scripts/_helpers.py | group_topics_by_repo → group_tasks_by_repo |
