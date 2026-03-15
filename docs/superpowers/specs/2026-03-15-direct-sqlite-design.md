# Session Logger → SQLite 직접 기록

## 배경

CC와 Codex session_logger가 transcript를 파싱한 뒤 work-log markdown을 중간 단계로 거쳐 SQLite에 기록하고 있다. 이 markdown은 누구도 읽지 않고, sync 스크립트가 다시 파싱해야 하는 불필요한 변환 단계다.

### 현재 파이프라인

```
CC:    transcript → session_logger → work-log.md → sync_cc.py → SQLite
Codex: rollout    → session_logger → work-log.md → sync_codex.py → SQLite
```

### 목표 파이프라인

```
CC:    transcript → session_logger → SQLite
Codex: rollout    → session_logger → SQLite
```

양쪽이 동일한 구조로 처리되고, 동일한 SQLite 스키마에 기록된다.

## 설계

### 1. 공유 코어: `activity_writer.py`

**위치:** `shared/life-dashboard-mcp/activity_writer.py` (신규)

CC와 Codex session_logger가 공유하는 SQLite 기록 함수.

```python
def record_activities(source, session_id, by_date, repo, branch,
                      summary=None, behavioral_signals=None):
    """날짜별 분할 데이터를 SQLite에 직접 기록.

    by_date: {"2026-03-14": ParsedData, ...}
    summary: {"tag": "코딩", "text": "..."} — 마지막 날짜에 적용
    behavioral_signals: {"decisions": [...], ...} — 마지막 날짜에 적용
    """
```

ParsedData 구조 (CC와 Codex 동일):
```python
{
    "files": list[str],
    "commands": list[str],
    "errors": list[str],
    "topic": str,
    "duration_min": int | None,
    "start_kst": datetime | None,
    "end_time": str | None,
    "has_commits": bool,
    "tokens": {
        "input": int, "output": int,
        "cache_read": int, "cache_create": int,
        "api_calls": int,
    },
}
```

`record_activities`가 하는 일:
1. 각 날짜별로 `upsert_activity()` 호출
2. summary/behavioral_signals가 있으면 마지막 날짜의 레코드에 적용
3. `update_daily_stats()` 호출
4. behavioral_signals가 있으면 `insert_behavioral_signal()` 호출

dedup은 SQLite의 `ON CONFLICT(source, session_id, date) DO UPDATE`로 처리. 기존 session_logger의 state 파일 기반 dedup 대체.

### 2. CC session_logger.py 변경

**기존:** `scan_and_record()` → `write_session_marker()` → work-log.md
**변경:** `scan_and_record()` → `record_activities()` → SQLite

변경 내용:
- `write_session_marker()`, `build_session_section()`, `build_frontmatter()` 제거
- `scan_and_record()`가 `record_activities()`를 호출하도록 변경
- `main()`의 SessionEnd 분기에서 LLM 요약 후 `record_activities()` 재호출 (summary 포함)
- dedup state 파일 로직 제거 (SQLite upsert가 대체)
- work-log 관련 import/상수 제거

### 3. Codex session_logger.py 변경

CC와 동일한 패턴으로 변경:
- `parse_rollout_by_date()` 추가 — rollout JSONL을 날짜별로 분할, ParsedData 구조로 출력
- `write_session_marker()`, `build_session_section()` 등 제거
- `record_activities("codex", ...)` 호출
- dedup state 파일 로직 제거

### 4. `parse_rollout_by_date()` — Codex용 날짜 분할 파서

기존 `parse_transcript()` (codex session_logger.py:474)를 날짜별로 분할하는 버전으로 교체.

입력 포맷 매핑:

| 데이터 | CC transcript | Codex rollout |
|--------|--------------|---------------|
| 유저 메시지 | `type:"user"` → `message.content` | `type:"event_msg"` → `payload.type:"user_message"` |
| 도구 호출 | `assistant` content `tool_use` block | `type:"response_item"` → `function_call` |
| 토큰 | `message.usage` | `event_msg` → `token_count` |
| 파일 변경 | `Edit`/`Write` tool | `write_file`/`apply_diff` function |
| 에러 | `tool_result` output | `function_call_output` exit_code≠0 |

출력은 CC의 `parse_transcript_by_date()`와 동일한 `dict[str, ParsedData]`.

### 5. active_session_scanner.py 변경

현재: `scan_and_record()` → work-log.md
변경: `scan_and_record()` → `record_activities()` → SQLite

session_logger.py의 `scan_and_record()` 변경을 그대로 반영.

### 6. daily_coach.py 변경

sync 호출 제거:

```python
# 현재:
scan_active_sessions()        # CC 열린 세션 → work-log
sync_cc_date(conn, date)      # CC work-log → SQLite
sync_codex_date(conn, date)   # Codex JSONL → SQLite
get_today_data(conn, date)    # SQLite → 리포트

# 변경:
scan_active_sessions()        # CC 열린 세션 → SQLite 직접
get_today_data(conn, date)    # SQLite → 리포트
```

### 7. LLM 요약 타이밍

- **SessionEnd / 세션 종료:** LLM 요약 생성 → `record_activities(summary=..., signals=...)` 으로 SQLite 업데이트
- **열린 세션 (scanner):** 요약 없이 topic만. correction rule 준수 (스크립트에서 LLM subprocess 금지)
- **daily_coach template report:** 요약 없는 레코드는 topic으로 표시 (`[?] topic...`)

## 제거 대상

| 파일 | 처리 |
|------|------|
| `shared/life-dashboard-mcp/sync_cc.py` | 삭제 |
| `shared/life-dashboard-mcp/sync_codex.py` | 삭제 |
| `cc/work-digest/scripts/parse_work_log.py` | 삭제 |
| `cc/work-digest/work-log/*.md` | 생성 중단 (기존 파일 유지) |
| `codex/work-digest/work-log/*.md` | 생성 중단 (기존 파일 유지) |
| CC session_logger의 markdown 관련 함수 | 제거 |
| Codex session_logger의 markdown 관련 함수 | 제거 |
| 양쪽 session_logger의 state 파일 dedup | 제거 (SQLite upsert 대체) |

## 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `shared/life-dashboard-mcp/activity_writer.py` | 신규: 공유 SQLite 기록 함수 |
| `cc/work-digest/scripts/session_logger.py` | markdown 제거, record_activities 호출 |
| `cc/work-digest/scripts/active_session_scanner.py` | scan_and_record 변경 반영 |
| `codex/work-digest/scripts/session_logger.py` | parse_rollout_by_date + record_activities |
| `shared/life-coach/scripts/daily_coach.py` | sync 호출 제거 |
| `shared/life-dashboard-mcp/sync_cc.py` | 삭제 |
| `shared/life-dashboard-mcp/sync_codex.py` | 삭제 |
| `cc/work-digest/scripts/parse_work_log.py` | 삭제 |
