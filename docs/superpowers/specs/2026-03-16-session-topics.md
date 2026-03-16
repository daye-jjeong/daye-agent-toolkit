# Session Topics — 세션 내 작업 단위 분해

## 목적

하나의 CC 세션에서 여러 작업을 수행했을 때, 작업 단위(토픽)별로 분리 기록하여
리포트와 집계에서 개별 작업이 축소되지 않고 명확히 표시되도록 한다.

## 배경

pipeline-redesign(2026-03-16)으로 데이터 무결성은 확보했지만,
요약 단위가 세션 단위(1 session = 1 summary = 1 tag)로 고정되어 있어
복합 작업 세션의 내용이 함축된다.

### 현재 문제

| 문제 | 원인 | 영향 |
|------|------|------|
| 3가지 작업을 해도 요약 1줄 | summarize_session() 프롬프트가 "2-3줄, 태그 하나" 강제 | 리포트에서 작업 누락 |
| tag_breakdown이 부정확 | 세션당 태그 1개 → 복합 작업의 비중이 큰 것만 반영 | 주간 집계 왜곡 |
| _build_work_items()가 "best" 세션만 표시 | 같은 tag 그룹에서 가장 긴 세션 1개만 | 나머지 세션 요약 미표시 |

### pipeline-redesign과의 관계

pipeline-redesign은 **데이터 무결성**(Layer 1/2 분리, 원본 보존)을 해결했다.
이번 작업은 **데이터 표현 단위**(세션 → 토픽)를 해결한다. 구조적 결함이 아니라 범위 확장.

## 아키텍처

### 데이터 모델

```
sessions (세션 = 측정 단위)
├── duration_min, token_total, start_at, end_at
├── status, has_commits, has_tests
├── summary, tag  ← 대표값 캐시 (가벼운 소비자용)
├── session_content (원본 데이터, 1:1)
└── session_topics (작업 단위, 1:N)  ← NEW
    ├── topic_order, tag, summary, repo
    └── duration_estimate_min
```

**소비 규칙:**
- 작업 내용 표시 (리포트, 코칭) → session_topics 기준
- tag_breakdown 집계 → session_topics 기준 (토픽 없으면 sessions.tag 폴백)
- 시간/토큰 통계 → **deduplicated sessions 기준** (토픽 행을 합산하면 중복 카운트됨)
- session_topics가 없는 세션 → sessions.summary/tag 폴백

**데이터 흐름 분리:**
`get_today_data()`는 두 스트림을 반환:
- `sessions`: deduplicated 세션 목록 (시간/토큰/커밋 통계용)
- `topics`: session_topics JOIN 결과 (작업 내용 표시용, 부모 session의 source/status/has_commits 포함)
토큰/시간 합산은 sessions에서만 수행. topics에서 token_total을 합산하면 안 된다.

### 스키마

```sql
CREATE TABLE IF NOT EXISTS session_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    topic_order INTEGER NOT NULL DEFAULT 0,
    tag TEXT,
    summary TEXT NOT NULL,
    repo TEXT,
    duration_estimate_min INTEGER,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, session_id, date, topic_order),
    FOREIGN KEY (source, session_id, date)
        REFERENCES sessions(source, session_id, date)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_topics_date ON session_topics(date);
CREATE INDEX IF NOT EXISTS idx_session_topics_tag ON session_topics(tag);
CREATE INDEX IF NOT EXISTS idx_session_topics_fk ON session_topics(source, session_id, date);
```

sessions.summary/tag는 유지. session_topics 생성 시 대표값(첫 번째 또는 최장 토픽)으로 캐시 업데이트.

**마이그레이션**: `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`로 기존 DB에서 안전하게 추가. `_migrate()` 변경 불필요.

## 파이프라인

### 전체 흐름

```
세션 종료
  → Layer 1: sessions + session_content 저장 (변경 없음)
  → Layer 2 경로 A (best-effort):
      코드 신호(repo/branch 전환) 기반 1차 토픽 분해
      + LLM(sonnet subprocess) 각 청크 요약
      → session_topics INSERT
      → sessions.summary/tag 캐시 UPDATE
      실패 시: session_topics 없음, pending 유지

코칭 시점 (21:00 cron → /coach 온디맨드)
  → Step 3a: session_topics 점검/교정
      session_content 원본 기반으로 토픽 분해 검증
      → session_topics DELETE WHERE (source, session_id, date) + 재INSERT (전체 교체)
  → Step 3d: 교정된 토픽으로 코칭 생성
  → 리포트 생성 (교정 완료 상태)
```

### 토픽 분해 품질 보장

#### 1. 토픽 경계 판단 기준

LLM 판단에만 의존하지 않고, 코드 감지 가능한 신호를 1차로 사용:

| 신호 | 신뢰도 | 감지 방법 |
|------|--------|-----------|
| repo 전환 | 높음 | files_changed, commands에서 경로 변화 |
| branch 전환 | 높음 | commands에서 git checkout/worktree 감지 |
| 사용자 방향 전환 | 중간 | user_messages에서 "이제 X 하자" 패턴 |
| files_changed 군집 불연속 | 중간 | 파일 경로의 공통 prefix 변화 |

경로 A(SessionEnd): 코드 신호만으로 분리. LLM은 각 청크의 요약만 담당.
경로 B(Step 3a): 코드 신호 + LLM 판단 합산. 최종 교정.

#### 2. 출력 형식 — JSON 강제

자유 텍스트가 아니라 JSON 배열:

```json
[
  {"tag": "설계", "summary": "pipeline spec 작성 — 3계층 분리 아키텍처", "repo": "daye-agent-toolkit", "date": "2026-03-16"},
  {"tag": "코딩", "summary": "sessions 테이블 + CRUD 구현", "repo": "daye-agent-toolkit", "date": "2026-03-16"}
]
```

멀티데이 세션의 경우 `date` 필드로 어느 date-slice에 귀속되는지 지정. 토픽 분해는 date-slice별로 수행하므로, 자정을 넘긴 세션은 각 날짜의 session_content를 기준으로 별도 분해.

#### 3. 검증 로직

session_topics INSERT 전 코드에서 검증:
- 토픽 0개 → reject (pending 유지)
- summary 빈 값 → reject
- tag가 유효 목록 밖 → auto_tag 폴백
- 토픽 수 > 10 → 과분할 경고, 상위 10개만

#### 4. duration_estimate_min 산출

정확한 시간 추적은 불가 (토픽 간 전환 시점이 명확하지 않음). 추정 방법:
- 코드 신호(repo/branch 전환) 기반 분리 시: 전환 시점 사이의 시간 차이
- LLM 분해 시: sessions.duration_min을 토픽 수로 균등 분배 (대략적)
- Step 3a에서 LLM이 대화 흐름을 보고 보정 가능

#### 5. 경로 A ↔ B 충돌 해소

Step 3a(경로 B)는 해당 세션의 session_topics를 **전체 교체**한다:
`DELETE FROM session_topics WHERE source=? AND session_id=? AND date=?` → 새로 INSERT.

이유: 경로 A가 만든 토픽 3개를 경로 B가 2개로 교정할 수 있으므로, 부분 UPDATE보다 전체 교체가 안전.

#### 6. 두 번의 품질 기회

1. SessionEnd(경로 A): best-effort 1차 생성. 실패해도 원본은 안전.
2. 코칭 Step 3a(경로 B): session_content 원본 기반 교정. **리포트는 이 시점 이후에 생성.**

## 변경 파일 목록

### life-dashboard-mcp (DB)

| 파일 | 변경 |
|------|------|
| `schema.sql` | session_topics 테이블 추가 |
| `db.py` | upsert_session_topics(), get_session_topics() 추가 |
| `activity_writer.py` | update-topics CLI 추가 (Step 3a용). record_sessions() 시그니처 변경: `summary: dict` → `topics: list[dict]` 수용. session_topics INSERT + sessions.summary 캐시 |

### work-digest (수집)

| 파일 | 변경 |
|------|------|
| `session_logger.py` | summarize_session() → 토픽 배열 리턴. 코드 기반 토픽 경계 감지 함수 추가. session_topics INSERT + sessions.summary 캐시 |
| `active_session_scanner.py` | 기존 session_topics 보호 (덮어쓰지 않음) |

### life-coach (소비)

| 파일 | 변경 |
|------|------|
| `SKILL.md` Step 3a | 토픽 분해 기준 + update-topics CLI 사용법 추가 |
| `daily_coach.py` | get_today_data()에서 sessions(dedup) + session_topics 두 스트림 반환. dedup_sessions()는 sessions 스트림에만 적용 (topics는 dedup 대상 아님) |
| `db.py` `update_daily_stats()` | tag_breakdown을 session_topics 기준으로 집계 (토픽 없으면 sessions.tag 폴백) |
| `daily_report.py` | _build_work_items() 토픽별 표시 (입력: topic dicts with tag, summary, repo, duration_estimate_min + 부모 session의 has_commits, status, source). _build_repos_detail() 토픽 기준 그룹핑 |
| `timeline_html.py` | 토픽별 타임라인 바 표시. dedup_sessions() 제거 또는 토픽 스트림용 별도 처리 |
| `_helpers.py` | dedup_sessions()가 session_id prefix 기반 → 토픽 스트림에서는 호출하지 않도록 분리 |

### 변경 없음

| 파일 | 이유 |
|------|------|
| 텔레그램 알림 | sessions.summary 캐시 사용 |
| work-context.md | sessions.summary 캐시 사용 |
| weekly_coach.py, weekly_report.py | 1차 범위 밖. session_topics 추가 후 별도 작업 |
| backfill_tags.py | 1회성 스크립트, 무시 |

## 비변경 사항

- sessions, session_content 스키마 변경 없음
- Layer 1 수집 로직 변경 없음
- 건강/재무/식재료 테이블 변경 없음
- weekly_* 파일은 이번 범위에서 제외 (session_topics 안정화 후 별도)
- 기존 데이터 backfill 없음. 신규 세션부터 session_topics 생성. 기존 세션은 sessions.summary/tag 폴백으로 동작.

## 후속 작업 (이번 범위 밖)

- weekly_coach.py, weekly_report.py의 session_topics 적용
- weekly_coach.py가 daily_stats.tag_breakdown을 읽는 부분 — update_daily_stats()가 토픽 기준으로 바뀌면 자동 반영
