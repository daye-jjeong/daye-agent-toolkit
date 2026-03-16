# Life-Dashboard 데이터 파이프라인 재설계

## 목적

모든 작업 행동을 체계적으로 기록하고, 재활용 가능한 데이터로 쌓는다.
코칭 내용, 태스크 제안, follow-up 체인을 DB에 구조화하여 저장하고,
다음날/주간 코칭에서 이전 데이터를 참조할 수 있게 한다.

## 배경

현재 파이프라인은 여러 차례 증분 수정을 거치면서 구조 문제가 누적되었다:

1. **수집과 분석이 뒤섞여 있다** — session_logger가 LLM 요약과 원본 수집을 동시에 처리. LLM 실패 시 원본 데이터 품질도 저하 (topic이 summary가 됨)
2. **코칭이 일회성이다** — /tmp에 마크다운 생성 후 버림. 다음날 참조 불가
3. **상태 추적이 스냅샷이다** — follow_up 해소를 매번 계산만 하고 이력 미보존. "같은 repo 작업 = 해소"라는 부정확한 판단

### 기존 파이프라인의 구체적 문제

| 문제 | 파일 | 영향 |
|------|------|------|
| Topic이 summary로 그대로 들어감 | session_logger.py | 요약 품질 저하 |
| raw_json에 user/agent messages 미저장 | activity_writer.py | 세션 내용 재구성 불가 |
| Behavioral signals가 last_date에만 기록 | activity_writer.py | 패턴 분석 날짜 오류 |
| dedup_sessions() 정의만 있고 호출 안 됨 | _helpers.py | 세션 중복 표시 |
| SessionEnd + scanner 동시 호출 시 데이터 손실 | session_logger.py, scanner.py | summary/signals 덮어쓰기 |
| 코칭 내용 미저장 | life-coach SKILL.md | 이전 코칭 참조 불가 |
| follow_up 해소를 repo 일치로만 판단 | daily_coach.py | 오판 빈발 |
| daily_report.py 파일명 고정 | daily_report.py | 덮어쓰기 |

## 아키텍처: 3계층 분리

```
┌─────────────────────────────────────────────┐
│  Layer 3: COACHING (life-coach)             │
│  코칭 생성 + 저장 + 태스크 추적             │
│  coaching_entries, task_suggestions         │
├─────────────────────────────────────────────┤
│  Layer 2: ENRICHMENT (on-demand/hook)       │
│  LLM 요약, 행동 신호, follow-up 체인        │
│  → 실패해도 Layer 1 데이터는 온전           │
├─────────────────────────────────────────────┤
│  Layer 1: INGESTION (work-digest hooks)     │
│  세션 파싱 + 즉시 저장 (LLM 의존 없음)     │
│  sessions, session_content                  │
└─────────────────────────────────────────────┘
```

**핵심 원칙**: Layer 1은 LLM 없이 동작한다. 파싱한 원본 데이터를 그대로 저장.
LLM 요약/신호 추출은 Layer 2에서 별도 수행. LLM 실패해도 원본은 항상 존재.

## 스킬 경계

| 스킬 | 계층 | 역할 | 변경 |
|------|------|------|------|
| `work-digest` | Layer 1 | CC 세션 수집 (hooks) | user/agent messages 추가, LLM 호출 분리 |
| `life-dashboard-mcp` | 공유 DB | 스키마 + CRUD + MCP | 새 스키마, enrichment API |
| `life-coach` | Layer 2+3 | 분석 + 코칭 | 코칭 저장, 태스크 추적, follow-up 체인 |

## 스키마

기존 activities 테이블을 sessions + session_content로 대체.
기존 behavioral_signals를 signals로 대체.
coaching_entries, task_suggestions, followup_chains 신규.
daily_stats, coach_state는 유지.
건강/재무/식재료 테이블은 변경 없음.

### sessions (activities 대체)

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- 'cc', 'codex'
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    repo TEXT,
    branch TEXT,
    tag TEXT,
    summary TEXT,
    summary_source TEXT DEFAULT 'pending', -- 'pending', 'auto', 'llm', 'manual'
    status TEXT DEFAULT 'in_progress',     -- 'completed', 'in_progress', 'blocked', 'follow_up'
    follow_up TEXT,
    start_at TEXT NOT NULL,
    end_at TEXT,
    duration_min INTEGER DEFAULT 0,
    file_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    has_tests INTEGER DEFAULT 0,
    has_commits INTEGER DEFAULT 0,
    token_total INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, session_id, date)
);

CREATE INDEX idx_sessions_date ON sessions(date);
CREATE INDEX idx_sessions_source ON sessions(source);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_summary_source ON sessions(summary_source);
```

`summary_source` 값:
- `pending` — Layer 1에서 저장 직후. LLM 처리 대기. summary는 NULL.
- `llm` — LLM이 생성한 요약 (hook 또는 코칭에서).
- `manual` — 사용자 또는 코칭 시 LLM이 수정.

**`auto` 제거**: topic 기반 summary를 만드는 것은 없애려는 문제를 다시 도입하므로, `pending`(summary=NULL) 상태를 유지하고 LLM 또는 수동 요약만 허용.

### session_content (NEW — 원본 보존)

```sql
CREATE TABLE session_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    topic TEXT,                        -- 첫 사용자 메시지 (raw)
    user_messages TEXT,                -- JSON array (해당 date-slice의 메시지만, 전체 복제 아님)
    agent_messages TEXT,               -- JSON array (해당 date-slice의 첫 N개)
    files_changed TEXT,                -- JSON array
    commands TEXT,                     -- JSON array
    errors TEXT,                       -- JSON array
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, session_id, date),
    FOREIGN KEY (source, session_id, date)
        REFERENCES sessions(source, session_id, date)
        ON DELETE CASCADE
);
```

sessions와 1:1 관계. FK로 참조 무결성 보장. 분리 이유:
- sessions 테이블을 가볍게 유지 (쿼리 성능)
- 원본 데이터는 분석/재처리용으로 별도 보관
- LLM 요약 재생성 시 session_content에서 원본 읽기
- sessions 삭제 시 session_content도 CASCADE 삭제

### signals (behavioral_signals 대체)

```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,                -- 세션의 primary date (date-slice 기준)
    signal_type TEXT NOT NULL,         -- 'decision', 'mistake', 'pattern'
    content TEXT NOT NULL,
    reasoning TEXT,                    -- 의사결정 맥락 (WHY)
    repo TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(session_id, signal_type, content)
);

CREATE INDEX idx_signals_date ON signals(date);
CREATE INDEX idx_signals_type ON signals(signal_type);
```

변경점:
- `reasoning` 컬럼 추가 — 의사결정의 "왜"를 별도 저장
- UNIQUE에서 date 제외 — 신호는 세션 전체에서 추출되므로 세션당 1건. date는 세션의 primary date를 기록 (기존 last_date 문제 해결: 세션이 시작된 날짜 사용)
- multi-day 세션: 신호를 날짜별로 쪼개지 않음 (전체 대화 맥락에서 추출하므로 쪼개면 중복)

### coaching_entries (NEW)

```sql
CREATE TABLE coaching_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    period_type TEXT NOT NULL,         -- 'daily', 'weekly'
    content TEXT NOT NULL,             -- 전체 코칭 마크다운
    sections TEXT NOT NULL,            -- JSON: 섹션별 분리 저장
    escalation_level INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, period_type)
);

CREATE INDEX idx_coaching_date ON coaching_entries(date);
```

`date` 규칙:
- `period_type='daily'`: 해당 일자 (YYYY-MM-DD)
- `period_type='weekly'`: 해당 주의 월요일 (week anchor). 같은 주에 여러 번 실행해도 UNIQUE로 upsert.

`sections` JSON 구조 (키는 coaching-prompts.md 섹션에 따라 유동적, 아래는 대표 예시):

```json
{
  "summary": "오늘의 정리 텍스트",
  "repo_detail": "레포별 상세 텍스트",
  "focus_metrics": "집중도 지표",
  "structure_review": "구조 리뷰 텍스트",
  "task_suggestions": "태스크 제안 텍스트",
  "coaching": "코칭 텍스트",
  "followup_review": "follow-up 해소 점검",
  "health": "건강 섹션",
  "question": "마무리 질문"
}
```

활용:
- 다음날 코칭: `SELECT sections->>'task_suggestions' FROM coaching_entries WHERE date = 어제`
- 주간 코칭: 일주일치 `structure_review`를 모아서 반복 패턴 탐지
- 장기 트렌드: escalation_level 변화 추적

### task_suggestions (NEW)

```sql
CREATE TABLE task_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suggested_date TEXT NOT NULL,
    description TEXT NOT NULL,
    estimated_min INTEGER,
    priority INTEGER,                  -- 1=highest
    source_type TEXT NOT NULL,         -- 'coaching', 'follow_up', 'blocker'
    origin_session_id TEXT,
    -- 해소 추적
    status TEXT DEFAULT 'pending',     -- 'pending', 'done', 'skipped', 'deferred'
    resolved_date TEXT,
    resolved_session_id TEXT,
    resolution_method TEXT,            -- 'auto', 'user'
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(suggested_date, description)
);

CREATE INDEX idx_tasks_status ON task_suggestions(status);
CREATE INDEX idx_tasks_date ON task_suggestions(suggested_date);
```

해소 판단 로직 (하이브리드):

1. **LLM 자동 판단** (resolution_method='auto'):
   - 오늘 세션에서 matching repo + branch + 관련 커밋 → `done`
   - 예: "cube-backend PR 머지" → 오늘 cube-backend에서 has_commits=1 → auto-resolve

2. **판단 불가 시 사용자에게 질문** (resolution_method='user'):
   - 코칭 시 "이 태스크는 어떻게 됐어?" 형태로 포함
   - 예: "설계 방향 결정" → 세션 데이터만으로 판단 불가 → 질문

3. **에스컬레이션**:
   - 3일 이상 pending → 코칭에서 강조
   - 7일 이상 pending → "이건 의도적으로 안 하는 건가?" 직접 질문

### followup_chains (NEW)

```sql
CREATE TABLE followup_chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_session_id TEXT NOT NULL,
    origin_date TEXT NOT NULL,
    origin_repo TEXT,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'open',        -- 'open', 'resolved', 'abandoned', 'superseded'
    resolved_date TEXT,
    resolved_session_id TEXT,
    resolution_note TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(origin_session_id, origin_date, description)
);

CREATE INDEX idx_followup_status ON followup_chains(status);
CREATE INDEX idx_followup_origin_date ON followup_chains(origin_date);
```

`days_open` 제거: 파생값이므로 저장하지 않고 `julianday('now') - julianday(origin_date)`로 쿼리 시 계산.

**생성 규칙 (idempotent upsert)**:
- `INSERT OR IGNORE` — UNIQUE(origin_session_id, origin_date, description)으로 중복 방지.
- scanner와 SessionEnd가 같은 세션을 여러 번 기록해도 체인은 1건만 생성.
- **생성 시점 2곳**:
  1. `record_sessions()` — Layer 2에서 status=follow_up/blocked 판정 시
  2. **코칭 Step 3c** — 코칭에서 처음 follow_up/blocked로 판정된 세션도 체인 생성 (record_sessions()에서 못 만든 건 여기서 catch)

**해소**: 코칭 시점에 LLM이 판단 — "같은 repo 작업 여부"가 아니라 세션 내용을 보고 실제로 해소됐는지 확인. 에스컬레이션 기준은 `julianday(date) - julianday(origin_date) >= 3`.

### daily_stats (유지)

```sql
CREATE TABLE daily_stats (
    date TEXT PRIMARY KEY,
    work_hours REAL,
    session_count INTEGER,
    tag_breakdown TEXT,
    repos TEXT,
    first_session TEXT,
    last_session_end TEXT,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);
```

### coach_state (유지)

```sql
CREATE TABLE coach_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);
```

## 파이프라인 상세

### Layer 1: Ingestion (session_logger.py 변경)

```
SessionEnd hook:
  1. parse_transcript_by_date()
     - 기존: topic, files_changed, commands, errors 추출
     - 추가: user_messages (전체), agent_messages (첫 N개)

  2. date별 split 후 각 date-slice에 대해:
     a. sessions INSERT
        - summary_source='pending' (LLM 아직 안 함)
        - tag=auto_tag() (키워드 기반)
        - summary=NULL (topic을 summary로 넣지 않음!)
     b. session_content INSERT
        - topic, user_messages, agent_messages, files, commands, errors

  3. Layer 2 시도 (best-effort, 실패해도 OK)
     - summarize_session() → sessions.summary UPDATE, summary_source='llm'
     - extract_behavioral_signals() → signals INSERT (세션당 1회, primary date 사용)
     - status=follow_up/blocked → followup_chains INSERT OR IGNORE
     - SessionEnd이므로 세션은 끝남 → has_commits 기반으로 status 판정:
       has_commits=1 → 'completed', LLM이 blocked/follow_up 판정하면 해당 값, 그 외 'completed'
       (닫힌 세션이 'in_progress'로 영구 남는 것 방지)

  4. daily_stats 갱신
```

핵심 변경:
- **summary=NULL로 시작** — topic을 summary에 넣지 않음. pending 상태로 두고 Layer 2가 채움.
- **user_messages, agent_messages 저장** — session_content에 원본 보존.
- **Layer 2가 실패해도** sessions + session_content는 항상 저장됨.

### Scanner 변경 (active_session_scanner.py)

```
Cron 호출:
  1. 열린 세션 탐색 (기존과 동일)
  2. parse_transcript_by_date() → sessions + session_content UPSERT
  3. Upsert 컬럼별 우선순위:
     - summary: COALESCE(기존값, NULL) — 기존 summary가 있으면 유지
     - summary_source: 기존값이 'llm'/'manual'이면 유지, 'pending'이면 업데이트 가능
     - tag: COALESCE(기존값, 새값) — 기존 tag 유지
     - status: 기존값이 'completed'/'blocked'/'follow_up'이면 유지 (scanner가 'in_progress'로 되돌리지 않음)
     - end_at, duration_min, token_total, file_count: 항상 최신값으로 업데이트 (열린 세션은 계속 변함)
     - session_content: REPLACE (최신 상태 반영)
```

### Layer 2: Enrichment

두 가지 실행 경로, LLM 호출 방식이 다르다:

**경로 A: SessionEnd hook (session_logger.py)**
- LLM 호출: `claude -p` subprocess (hook 스크립트 예외 규칙 적용)
- 타이밍: 세션 종료 직후, best-effort
- 실패 시: summary_source='pending' 유지, Layer 1 데이터는 온전

**경로 B: 코칭 시작 시 (SKILL.md Step 3a)**
- LLM 호출: CC 세션의 LLM이 직접 수행 (subprocess 아님)
- 타이밍: /coach 온디맨드 호출 시
- 동작: summary_source='pending'인 세션의 session_content를 읽고 LLM이 직접 요약 생성

```
경로 B의 SKILL.md 절차:

Step 3a. 미처리 세션 보강 (catch-up 포함)
  1. pending 세션 조회 (오늘 + 과거 미처리):
     python3 {baseDir}/../life-dashboard-mcp/activity_writer.py unsummarized --date <DATE>
     python3 {baseDir}/../life-dashboard-mcp/activity_writer.py unsummarized --before <DATE>  ← 과거 pending catch-up
  2. 각 세션의 session_content(topic, user_messages)를 보고 태그+요약 생성
  3. update-summary CLI로 DB 업데이트 (기존과 동일한 인터페이스)
```

이 구조는 `no-subprocess-llm` 규칙과 호환:
- hook(경로 A): 세션 외부 실행, subprocess 허용
- 스킬(경로 B): CC 세션 LLM이 직접 수행, subprocess 아님

### Enrichment 함수 위치

| 함수 | 파일 | 용도 |
|------|------|------|
| `summarize_session()` | `session_logger.py` | hook에서 subprocess LLM 호출 |
| `extract_behavioral_signals()` | `session_logger.py` | hook에서 subprocess LLM 호출 |
| `unsummarized` CLI | `activity_writer.py` | pending 세션 조회 (SKILL.md에서 호출) |
| `update-summary` CLI | `activity_writer.py` | 요약 업데이트 (SKILL.md에서 호출) |

### Layer 3: Coaching (SKILL.md 변경)

기존 Step 3에 추가:

```
Step 3: LLM 코칭
  3a. 미처리 세션 보강 (Layer 2 호출)
  3b. 이전 코칭 참조
      - SELECT * FROM coaching_entries WHERE date = 어제 AND period_type = 'daily'
      - SELECT * FROM task_suggestions WHERE status = 'pending'
      - SELECT * FROM followup_chains WHERE status = 'open'
  3c. 세션 요약 업데이트 (기존과 동일)
  3d. 코칭 생성
      - coaching-prompts.md 프레임 적용
      - 어제 코칭 대비 변화 분석
      - 어제 태스크 제안 이행 여부 판단
  3e. 코칭 저장 (idempotent — 같은 날짜에 재실행해도 안전)
      - coaching_entries UPSERT (ON CONFLICT(date, period_type) DO UPDATE — 재실행 시 덮어쓰기)
      - task_suggestions UPSERT (ON CONFLICT(suggested_date, description) DO UPDATE — 중복 방지)
      - task_suggestions UPDATE (이행 판단 — auto/user)
      - followup_chains INSERT OR IGNORE (중복 방지) + UPDATE (해소 판단)
      - status 변경된 세션 → followup_chains 생성 (코칭에서 처음 판정된 건도 catch)
```

### coaching-prompts.md 변경

기존 프레임에 추가할 섹션:

```markdown
### 📋 어제 태스크 점검
- `task_suggestions`에서 pending 태스크를 가져와 오늘 세션과 대조.
- LLM이 판단 가능: 매칭되는 repo + 관련 작업이 있으면 자동 해소.
- LLM이 판단 불가: "이 태스크는 어떻게 됐어?" 형태로 질문에 포함.
- 3일 이상 pending: 강조하여 언급.
- 7일 이상 pending: "의도적으로 안 하는 건가?" 직접 질문.

### 🔗 Follow-up 체인 점검
- `followup_chains`에서 open 항목을 가져와 점검.
- 오늘 세션의 session_content를 보고 실제 해소 여부 판단.
  (단순히 "같은 repo 작업"이 아니라 내용 기반 판단)
- 해소된 건: resolution_note와 함께 resolved로 업데이트.
- 미해소 + `julianday('now') - julianday(origin_date) >= 3`: 에스컬레이션.
```

## 리포트 변경

### daily_report.py

- 출력 파일명: `/tmp/daily_report_<DATE>.html` (날짜 포함)
- `--output` 플래그 추가 (커스텀 경로 지원)

### weekly_report.py

- 출력 파일명: `/tmp/weekly_report_<DATE>.html`
- `--output` 플래그 추가

## 마이그레이션

기존 데이터 마이그레이션 하지 않음. 새 스키마로 clean start.
- `_migrate()` 함수에서 구 테이블(activities, behavioral_signals) 존재 시 DROP하지 않고 무시.
- 새 테이블만 CREATE IF NOT EXISTS.
- 구 테이블 데이터는 자연스럽게 사용되지 않음 (새 코드는 새 테이블만 참조).

## 변경 파일 목록

### life-dashboard-mcp (공유 DB)

| 파일 | 변경 |
|------|------|
| `schema.sql` | 새 스키마 (sessions, session_content, signals, coaching_entries, task_suggestions, followup_chains) |
| `db.py` | 새 CRUD 함수 (upsert_session, insert_session_content, insert_signal, insert_coaching_entry, insert_task_suggestion, upsert_followup_chain), update_daily_stats()를 sessions 테이블 참조로 전환, get_repeated_signals/get_mistake_trends를 signals 테이블 참조로 전환, _migrate() 업데이트 |
| `activity_writer.py` | `record_sessions()`로 리네이밍 — sessions + session_content + followup_chains 기록. CLI 커맨드(unsummarized, update-summary)를 sessions/session_content 테이블 참조로 전환. `unsummarized --before` 플래그 추가 (과거 pending catch-up). `record_activities()`는 codex 호환용 thin wrapper로 유지 |
| `server.py` | MCP 쿼리를 activities → sessions 테이블 참조로 전환 |
| `sync_calendar.py` | `upsert_activity()` → `upsert_session()` 호출로 변경 (source='calendar') |
| `backfill_tags.py` | activities → sessions 참조 전환 |

### work-digest (CC hooks)

| 파일 | 변경 |
|------|------|
| `session_logger.py` | Layer 1/2 분리: parse에서 user/agent messages 추출 → session_content 저장, summary=NULL로 시작 (topic을 summary에 넣지 않음), Layer 2는 best-effort |
| `active_session_scanner.py` | sessions 테이블 참조, 기존 summary 보호 (summary_source가 'llm'/'manual'이면 덮어쓰지 않음) |

### life-coach (코칭)

| 파일 | 변경 |
|------|------|
| `SKILL.md` | Step 3에 이전 코칭 참조 + 저장 절차 추가, Step 3a에 session_content 기반 enrichment |
| `references/coaching-prompts.md` | 태스크 점검, follow-up 체인 점검 섹션 추가 |
| `scripts/daily_coach.py` | activities→sessions 테이블 전환, behavioral_signals→signals 전환, coaching_entries/task_suggestions/followup_chains 쿼리 추가, follow_up 해소 로직 followup_chains 기반으로 변경, session_content JOIN으로 user_messages 등 접근 |
| `scripts/weekly_coach.py` | activities→sessions 전환, behavioral_signals→signals 전환, coaching_entries 주간 집계, followup_chains blocked resolution 전환 |
| `scripts/daily_report.py` | 날짜 기반 파일명 (`/tmp/daily_report_<DATE>.html`), `--output` 플래그 |
| `scripts/weekly_report.py` | 날짜 기반 파일명, `--output` 플래그 |
| `scripts/_helpers.py` | dedup_sessions() 실제 호출되도록 연결, sessions 테이블 기준으로 수정 |

## 구 테이블 전환 전략

**이번 전환은 CC-only cutover이다.** Codex 데이터는 전환 기간 동안 코칭/리포트에서 제외됨을 명시적으로 수용한다.

- `_migrate()`에서 구 테이블(activities, behavioral_signals)을 DROP하지 않음
- 새 코드는 sessions/signals만 참조
- 구 테이블은 자연스럽게 orphan이 됨 (새 데이터가 안 들어감)
- Codex logger 호환: `activity_writer.py`에 `record_activities()` thin wrapper 유지. 내부적으로 activities 테이블에 기록 (Codex는 아직 구 스키마 사용)
- **Codex 데이터 가시성**: 전환 기간 동안 daily_coach/weekly_coach는 sessions만 읽으므로 Codex 세션은 리포트에 안 나옴. 이전에도 Codex 세션은 전체의 10-20%였고, 핵심 코칭 대상은 CC 세션이므로 수용 가능. Codex 전환은 CC 파이프라인 안정화 후 별도 작업.

### 추가 전환 대상 파일

spec 변경 파일 외에 activities를 직접 참조하는 파일:

| 파일 | 현재 참조 | 전환 방법 |
|------|-----------|-----------|
| `server.py` (MCP) | `FROM activities` | `FROM sessions`로 변경 |
| `sync_calendar.py` | `upsert_activity()` | `upsert_session()`으로 변경 (source='calendar') |
| `backfill_tags.py` | `FROM activities` | `FROM sessions`로 변경 (1회성 스크립트) |

## 비변경 사항

- 건강 테이블 (health_exercises, health_symptoms, health_check_ins, health_meals, health_pt_homework) — 변경 없음
- 재무 테이블 (finance_*) — 변경 없음
- 식재료 테이블 (pantry_items) — 변경 없음
- Codex logger — 이번 범위에서 제외. CC-only cutover. `record_activities()` wrapper로 호환 유지.
