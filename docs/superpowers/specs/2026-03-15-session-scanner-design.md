# CC 세션 스캐너 + 날짜 분할 로깅

## 배경

Opus 1M 컨텍스트 도입으로 compaction이 거의 일어나지 않게 되면서, 기존 session logging 시스템의 두 전제가 깨졌다:

1. **세션이 짧고 자주 닫힘** → 실제로는 며칠 열어둠 → SessionEnd hook 미발동
2. **긴 세션은 compact가 자주 일어남** → 1M 컨텍스트로 compact 거의 없음 → PreCompact hook 미발동

결과: 대부분의 CC 세션이 로깅되지 않아 daily coaching report가 불완전.

### 현상 (2026-03-14 사례)

- CC 세션 6개 중 1개만 기록됨 (나머지 5개는 열린 상태)
- daily report에 CC 34분만 잡힘, 실제 작업량은 훨씬 많음
- 다일간 세션은 시작 날짜에만 기록돼 양쪽 날짜에서 누락 가능

## 설계

### 접근: session_logger.py 리팩토링 + scanner 추가

날짜 분할 로직을 코어 함수로 추출하고, hook과 cron scanner 양쪽에서 재사용.

```
session_logger.py (refactored)
  ├── scan_and_record()  ← 코어: transcript 파싱 + 날짜 분할 + work-log 기록
  ├── main()             ← hook 진입점 (SessionEnd/PreCompact)
  └── LLM 요약/행동추출  (SessionEnd only)

active_session_scanner.py (신규)
  └── 열린 세션 탐색 → 각각 scan_and_record() 호출

daily_coach.py (수정)
  └── 실행 시 scanner → sync → 일괄 요약 → 리포트
```

### 1. 코어: `scan_and_record()`

#### 날짜 분할

transcript JSONL의 각 엔트리 timestamp를 KST 기준으로 날짜 분류.

```python
scan_and_record(session_id, transcript_path, cwd, force=False)
  1. parse_transcript_by_date(transcript_path)
     → { "2026-03-14": ParsedData, "2026-03-15": ParsedData }
  2. 날짜별로 stats 계산 (duration, files, commands, errors, tokens)
  3. 날짜별로 work-log에 기록
```

`ParsedData`는 기존 `parse_transcript()` 반환값과 동일한 구조 (files, commands, errors, topic, duration_min, tokens 등).

#### Dedup

- 키: `session_id:date` (기존 `session_id:event`에서 변경)
- `force=False` (cron/PreCompact): 이미 기록된 날짜는 skip
- `force=True` (SessionEnd): 기존 기록을 덮어씀 (요약 포함)

#### work-log 기록

- 기존: append-only
- 변경: `## 세션 HH:MM (sid_short, repo)` 헤더로 섹션 식별, 같은 session_id 섹션이 있으면 교체
- 교체 실패 시 append fallback (기존 호환)
- 파일 락: 기존 `fcntl.flock()` 유지

### 2. Hook 진입점

#### SessionEnd

```
1. scan_and_record(force=True) → 날짜별 work-log 기록
2. LLM 요약 + 행동 추출 (세션 전체 대상, 1회)
3. 요약을 마지막 활동 날짜의 work-log 섹션에 업데이트
4. 텔레그램 전송
```

#### PreCompact

```
1. scan_and_record(force=False) → 미기록 날짜만 추가
```

LLM 요약 없이 마커만 (기존과 동일).

### 3. Active Session Scanner

#### `active_session_scanner.py`

```python
scan_active_sessions()
  1. ~/.claude/sessions/*.json 읽기 → { pid, sessionId, cwd, startedAt }
  2. transcript 경로 탐색:
     - cwd → project hash 변환:
       a. 경로의 / → -, _ → -, 선행 - 추가
       b. worktree cwd인 경우: git rev-parse --git-common-dir로 원본 레포 경로 획득 → 원본 경로로 hash 재시도
       c. 위 모두 실패 시: ~/.claude/projects/ 전체에서 {sessionId}.jsonl 검색 (find fallback)
     - ~/.claude/projects/{hash}/{sessionId}.jsonl
  3. 각 세션에 대해 scan_and_record(force=False)
  4. 죽은 세션(ps -p 실패): transcript 기록은 하되 sessions 파일은 건드리지 않음
```

#### 호출 시점

독립 cron이 아닌 daily_coach.py에서 직접 호출:

```python
# daily_coach.py main() — 순차 실행 (각 단계 완료 후 다음 진행)
scan_active_sessions()     # 1) 열린 세션 work-log에 기록 (완료 필수)
run_sync()                 # 2) work-log → SQLite (scanner 완료 후)
data = get_today_data()    # 3) 리포트 생성
```

cron 변경 불필요: daily_coach.py 내부에서 scanner를 직접 호출하므로 기존 cron 설정 유지.

### 4. 미요약 세션 처리

#### correction rule 준수

`.claude/rules/correction-20260307-2030-no-subprocess-llm.md`에 의해 스킬 스크립트(daily_coach.py 포함)에서 LLM subprocess 호출 금지. 예외는 hook 스크립트(`session_logger.py`)만.

#### 해결: on-demand 패턴

cron(`daily_coach.py`)은 **데이터만 기록**하고, LLM 요약은 하지 않는다:

1. scanner가 raw data를 work-log에 기록 (topic, files, commands — 요약 없음)
2. sync → SQLite에 tag=NULL, summary=NULL인 레코드 생성
3. daily_coach.py의 template report는 미요약 세션을 topic으로 표시
4. `--json` 출력에 미요약 세션 포함 → CC/OpenClaw LLM 세션이 on-demand로 요약 생성

SessionEnd hook이 발동하면 그 시점에 LLM 요약이 붙고 SQLite 업데이트.

#### template report에서의 표시

미요약 세션은 topic(첫 유저 메시지)을 summary 대신 사용:

```
- 14:13 [?] ChatGPT 주간 한도 소진 원인을 ...   ← 미요약 (topic)
- 00:58 [리뷰] OpenClaw 스킬 호환성 확인        ← 요약 완료
```

### 5. sync_cc.py 변경

날짜 분할로 같은 session_id가 여러 날짜 파일에 나타남:

- upsert 키: `(session_id, date)` 복합키
- 같은 키 레코드가 있으면 UPDATE (요약 추가 등)

### 6. SQLite 스키마 변경

현재 스키마: `CREATE UNIQUE INDEX idx_activities_session ON activities(source, session_id);`

변경:
1. `date` 컬럼 추가 (TEXT, 'YYYY-MM-DD')
2. unique index를 `(source, session_id, date)`로 변경
3. 기존 데이터 마이그레이션

```sql
-- 1. date 컬럼 추가
ALTER TABLE activities ADD COLUMN date TEXT;

-- 2. 기존 레코드 backfill (start_at에서 파생)
UPDATE activities SET date = date(start_at) WHERE date IS NULL;

-- 3. 기존 unique index 교체
DROP INDEX IF EXISTS idx_activities_session;
CREATE UNIQUE INDEX idx_activities_session ON activities(source, session_id, date);
```

마이그레이션은 `sync_cc.py` / `db.py` 초기화 시 자동 실행 (ALTER TABLE은 idempotent하지 않으므로 컬럼 존재 여부 확인 후 실행).

### 7. 에러 처리

| 케이스 | 처리 |
|--------|------|
| 죽은 세션 (pid dead) | transcript 기록, sessions 파일은 CC에 맡김 |
| transcript 없음/비어있음 | skip, stderr 로그 |
| timestamp 없는 엔트리 | 직전 timestamped 엔트리의 날짜에 귀속, 없으면 startedAt |
| work-log 섹션 교체 실패 | append fallback |
| 동시 실행 (hook + scanner) | fcntl.flock() — work-log 파일 + state 파일 양쪽에 적용 |
| state 파일 크기 | recorded 리스트 100개 제한 + 7일 TTL 정리 |

## 범위 외

- **Codex 세션**: 별도 파이프라인으로 이미 정상 동작. 변경 없음.
- **Codex work-digest**: 변경 없음.
- **daily_coach.py 리포트 포맷**: 변경 없음 (데이터 소스만 개선).

## 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `cc/work-digest/scripts/session_logger.py` | 코어 리팩토링: scan_and_record, 날짜 분할, dedup 변경, work-log 섹션 교체 |
| `cc/work-digest/scripts/active_session_scanner.py` | 신규: 열린 세션 탐색 + scan_and_record 호출 |
| `shared/life-coach/scripts/daily_coach.py` | scanner + sync + 일괄 요약 호출 추가 |
| `shared/life-dashboard-mcp/sync_cc.py` | (session_id, date) 복합키 upsert |
| `shared/life-dashboard-mcp/db.py` | upsert_activity ON CONFLICT 절 변경 + 마이그레이션 함수 |
| `shared/life-dashboard-mcp/schema.sql` | activities date 컬럼 추가 + unique index 변경 |
