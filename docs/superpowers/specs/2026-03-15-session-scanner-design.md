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
     - cwd → project hash (경로의 /를 -로, 선행 - 추가)
     - ~/.claude/projects/{hash}/{sessionId}.jsonl
     - 탐색 실패 시 find fallback
  3. 각 세션에 대해 scan_and_record(force=False)
  4. 죽은 세션(ps -p 실패): transcript 기록은 하되 sessions 파일은 건드리지 않음
```

#### 호출 시점

독립 cron이 아닌 daily_coach.py에서 직접 호출:

```python
# daily_coach.py main()
scan_active_sessions()     # 1) 열린 세션 work-log에 기록
run_sync()                 # 2) work-log → SQLite
summarize_unsummarized()   # 3) 요약 없는 세션 일괄 요약
data = get_today_data()    # 4) 리포트 생성
```

### 4. 일괄 요약: `summarize_unsummarized()`

daily_coach.py에 추가. SQLite sync 후 요약 없는 활동 레코드를 찾아 일괄 요약.

```python
summarize_unsummarized(conn, date_str)
  1. SELECT from activities WHERE date(start_at) = date_str AND (tag IS NULL OR summary IS NULL)
  2. 각 레코드의 transcript에서 해당 날짜 분량만 추출
     → extract_conversation_for_date(transcript_path, date_str)
  3. sonnet 호출 → 태그 + 요약 생성 (session_logger의 summarize_session 재사용)
  4. SQLite UPDATE
```

SessionEnd에서 이미 요약된 세션은 skip.

비용: 하루 미기록 5세션 기준, sonnet 요약 5회 ≈ 40K input tokens ≈ $0.12/일.

### 5. sync_cc.py 변경

날짜 분할로 같은 session_id가 여러 날짜 파일에 나타남:

- upsert 키: `(session_id, date)` 복합키
- 같은 키 레코드가 있으면 UPDATE (요약 추가 등)

### 6. SQLite 스키마 변경

```sql
-- activities 테이블에 date 컬럼 추가 (없는 경우)
-- unique index를 (session_id, date)로 변경
CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_session_date
  ON activities(session_id, date);
```

기존 session_id-only index가 있으면 DROP 후 재생성.

### 7. 에러 처리

| 케이스 | 처리 |
|--------|------|
| 죽은 세션 (pid dead) | transcript 기록, sessions 파일은 CC에 맡김 |
| transcript 없음/비어있음 | skip, stderr 로그 |
| timestamp 없는 엔트리 | 직전 timestamped 엔트리의 날짜에 귀속, 없으면 startedAt |
| work-log 섹션 교체 실패 | append fallback |
| 동시 실행 (hook + scanner) | fcntl.flock() 파일 락 |

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
| `shared/life-dashboard-mcp/schema.sql` | activities unique index 변경 |
