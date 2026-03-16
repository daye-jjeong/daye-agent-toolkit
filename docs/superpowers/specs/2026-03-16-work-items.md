# Work Items — 실시간 작업 단위 기록

## 목적

사용자가 한 작업을 **기능 단위로, 정확한 시간에, 발생 시점에** 기록한다.
세션 종료를 기다리지 않고, 작업 전환 시점에 즉시 경계를 기록하고,
요약은 사용자가 원할 때 on-demand로 생성한다.

## 배경

3차례 리팩토링의 교훈:
1. pipeline-redesign: sessions/session_content 분리 → 데이터 무결성 확보
2. session_topics: 세션 하위에 토픽 분해 → 세션이 부모인 구조의 한계 발견
3. 이번: **작업 단위가 주체**, 세션은 출처

핵심 전환: "세션 끝난 후 사후 재구성" → "발생 시점에 기록"

## 아키텍처

```
UserPromptSubmit hook (매 메시지, LLM 없음)
  → 작업 전환 감지 → work_item 경계(start_at/end_at) 기록

SessionEnd hook (세션 종료, LLM 없음)
  → 마지막 work_item.end_at 기록
  → sessions + session_content INSERT (기존대로)

사용자 트리거 ("정리해줘" / 코칭 스킬)
  → 트랜스크립트 해당 구간 읽기
  → summary, tag, status, follow_up, signals 생성
```

**LLM 호출은 자동 파이프라인에 없다.** hook은 전부 경량. 요약은 사용자가 원할 때만.

**UserPromptSubmit hook**: CC hook 이벤트로 지원됨. hook stdin으로 `session_id`, `session_cwd`, `user_message` 전달. LLM 없는 경량 스크립트(regex + DB write)라 매 프롬프트 실행해도 성능 영향 미미 (<50ms).

## 스키마

### work_items (NEW — 주 테이블)

```sql
CREATE TABLE IF NOT EXISTS work_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,           -- 출처 세션 (provenance, FK 아님)
    source TEXT NOT NULL DEFAULT 'cc',
    repo TEXT,
    branch TEXT,                        -- worktree 이름 또는 branch
    date TEXT NOT NULL,
    start_at TEXT NOT NULL,             -- hook이 기록한 정확한 시작
    end_at TEXT,                        -- hook이 기록한 정확한 종료 (NULL = 진행중)
    -- 아래는 사용자 트리거 시 채움 (NULL 허용)
    tag TEXT,
    summary TEXT,
    status TEXT DEFAULT 'in_progress',  -- completed, in_progress, blocked, follow_up
    follow_up TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(session_id, start_at)
);

CREATE INDEX IF NOT EXISTS idx_work_items_date ON work_items(date);
CREATE INDEX IF NOT EXISTS idx_work_items_status ON work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_repo ON work_items(repo);
```

**sessions와의 관계**: work_items.session_id는 FK 아님 (provenance only). work_items가 sessions보다 먼저 생성될 수 있음 (세션 첫 메시지에서 hook이 work_item 생성 → SessionEnd에서 sessions INSERT). 정상 케이스.

**cross-session 작업 연결**: `repo + branch`가 같으면 같은 기능으로 추론. branch가 NULL(main 직접 작업)이면 사용자 트리거 시 LLM이 summary 기반으로 연결 판단. 1차 스코프에서는 자동 연결 안 함, followup_chains가 이 역할 담당.

### work_item_signals (NEW — 기존 signals 대체)

```sql
CREATE TABLE IF NOT EXISTS work_item_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_item_id INTEGER NOT NULL,
    signal_type TEXT NOT NULL,          -- 'decision', 'mistake', 'pattern'
    content TEXT NOT NULL,
    reasoning TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (work_item_id) REFERENCES work_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wi_signals_type ON work_item_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_wi_signals_work_item ON work_item_signals(work_item_id);
```

**기존 signals 테이블**: 유지 (삭제 안 함). 새 코드는 work_item_signals만 사용. 기존 signals 데이터는 자연스럽게 미사용. `get_repeated_signals()`, `get_mistake_trends()`를 work_item_signals 기준으로 변경.

### 기존 테이블

| 테이블 | 변경 | 이유 |
|--------|------|------|
| sessions | 유지, summary/tag 캐시 중단 | 세션 메타(duration, tokens) 통계용 |
| session_content | 유지 | 원본 보존 (요약 생성 시 읽음) |
| signals | 유지 (미사용) | 기존 데이터 보존, 새 코드는 work_item_signals |
| session_topics | 유지 (미사용) | 기존 데이터 보존, 새 코드는 work_items |
| daily_stats | tag_breakdown을 work_items 기준으로 변경 | |
| coaching_entries, task_suggestions, followup_chains | 유지 | coaching 레이어 |

## UserPromptSubmit Hook

### 작업 전환 감지 로직

```python
def on_user_prompt(hook_input: dict):
    """LLM 없이 작업 전환 감지. 경량."""
    session_id = hook_input["session_id"]
    cwd = hook_input.get("cwd", "")
    message = hook_input.get("user_message", "")

    repo, branch = detect_repo_and_branch(cwd)
    now = datetime.now(KST)
    date = now.strftime("%Y-%m-%d")

    current = get_open_work_item(session_id)

    switched = False
    if current:
        if current["repo"] != repo:
            switched = True
        elif branch and current["branch"] != branch:
            switched = True
        elif _is_topic_switch(message):
            switched = True

    if switched and current:
        close_work_item(current["id"], end_at=now)

    if switched or not current:
        create_work_item(session_id, source="cc", repo=repo, branch=branch,
                        date=date, start_at=now)
```

### 발화 패턴 감지

```python
_SWITCH_PATTERNS = [
    r"이제\s+.+\s*(하자|할게|하겠)",
    r"다른\s*(거|작업|것)\s*(하자|할게|보자)",
    r"(먼저|일단)\s+.+\s*(하자|할게|보자)",
    r"/clear",
    # 영어
    r"(let's|now)\s+(work on|switch to|move to)",
    r"(start|begin)\s+(working on|with)",
]
```

**"이어서/계속" 패턴은 전환이 아님** — 같은 작업 continuation. 패턴에서 제외.

## SessionEnd Hook

```python
def on_session_end(hook_input: dict):
    session_id = hook_input["session_id"]

    # 1. 열린 work_item 종료
    current = get_open_work_item(session_id)
    if current:
        close_work_item(current["id"], end_at=datetime.now(KST))

    # 2. sessions + session_content INSERT (기존 로직 유지, LLM 없음)
    # parse_transcript_by_date() → record_sessions() (session_topics 제거)
```

## 사용자 트리거 (요약 생성)

사용자가 "정리해줘" / "뭐 했지?" / 코칭 스킬 실행 시:

```
1. work_items 조회 (summary가 NULL인 것들)
2. 각 work_item의 start_at~end_at 구간 트랜스크립트 읽기
   - 트랜스크립트 .jsonl에서 타임스탬프 기반 슬라이싱
   - 경계 margin ±30초 적용 (hook 시각 vs 메시지 시각 차이 보정)
3. LLM이 생성:
   - summary: 무엇을/왜/결과/의사결정
   - tag: 코딩, 설계, 디버깅 등
   - status: completed / in_progress / blocked / follow_up
   - follow_up: 후속 작업
   - signals: decisions, mistakes, patterns
4. DB 업데이트 (work_items + work_item_signals)
```

## daily_stats.tag_breakdown

```python
# work_items 기준 (tag가 있는 것만)
tags_from_wi = SELECT tag, COUNT(*) FROM work_items
               WHERE date = ? AND tag IS NOT NULL GROUP BY tag

# tag가 전부 NULL이면 (사용자가 아직 요약 안 함) → sessions.tag fallback
if not tags_from_wi:
    tags_from_sessions = SELECT tag, COUNT(*) FROM sessions
                         WHERE date = ? GROUP BY tag
```

## 소비자 변경

| 파일 | 변경 |
|------|------|
| `daily_report.py` | work_items 기반 레포 그룹핑 + 타임라인 |
| `daily_coach.py` | work_items 조회, sessions는 통계만 |
| `timeline_html.py` | work_items start_at/end_at 직접 사용, idle gap 자연 표현 |
| `weekly_coach.py` | work_item_signals 기준 반복 패턴, work_items 주간 집계 |
| `weekly_report.py` | work_item_signals 기준 |
| `_helpers.py` | group_topics_by_repo → group_work_items_by_repo 전환 |

## 변경 파일 목록

### 신규

| 파일 | 역할 |
|------|------|
| `cc/work-digest/hooks/user_prompt_hook.py` | UserPromptSubmit hook — 작업 전환 감지 |

### 변경

| 파일 | 변경 |
|------|------|
| `shared/life-dashboard-mcp/schema.sql` | work_items + work_item_signals DDL 추가 |
| `shared/life-dashboard-mcp/db.py` | create/close/get work_item CRUD, get_repeated_signals/get_mistake_trends를 work_item_signals 기준, update_daily_stats fallback |
| `shared/life-dashboard-mcp/activity_writer.py` | record_sessions()에서 session_topics 로직 삭제, cmd_update_topics 삭제 |
| `cc/work-digest/scripts/session_logger.py` | SessionEnd에서 work_item 종료, summarize_session()/LLM subprocess 삭제, topic_segments/work_unit 관련 함수 삭제 |
| `cc/work-digest/scripts/active_session_scanner.py` | session_topics 생성 로직 삭제, sessions 갱신만 유지 |
| `shared/life-coach/SKILL.md` | Step 3a를 on-demand 요약으로 변경 |
| `shared/life-coach/scripts/daily_coach.py` | work_items 조회, sessions는 통계만 |
| `shared/life-coach/scripts/daily_report.py` | work_items 기반 표시 |
| `shared/life-coach/scripts/timeline_html.py` | work_items start_at/end_at 직접 사용 |
| `shared/life-coach/scripts/weekly_coach.py` | work_item_signals 참조 |
| `shared/life-coach/scripts/weekly_report.py` | work_item_signals 참조 |
| `shared/life-coach/scripts/_helpers.py` | group_work_items_by_repo |

### 삭제 대상 코드

| 위치 | 대상 |
|------|------|
| `db.py` | `upsert_session_topics()`, `get_session_topics()`, `_VALID_TAGS`, session_topics migration 블록 |
| `activity_writer.py` | `cmd_update_topics()`, `record_sessions()` 내 session_topics/topic_segments 분기 전체 |
| `session_logger.py` | `summarize_session()`, `_parse_topics_response()`, `_compute_topic_segments()`, `_compute_work_unit_time_ranges()`, `_extract_work_unit()`, `file_timeline` 수집, `activity_segments` 계산 |
| `active_session_scanner.py` | projects 디렉토리 스캔 (work_items hook이 대체), session_topics proto-topic 생성 |

## 비변경

- sessions, session_content 스키마 (유지)
- signals, session_topics 테이블 (유지, 미사용)
- coaching_entries, task_suggestions, followup_chains (유지)
- 건강/재무/식재료 테이블 (유지)

## 전환 전략

- session_topics, signals 테이블 DROP 안 함 (기존 데이터 보존)
- 새 코드는 work_items, work_item_signals만 참조
- scanner의 sessions 갱신은 유지 (통계용)
