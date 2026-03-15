# Session Logger → SQLite 직접 기록

## 배경

CC와 Codex session_logger가 transcript를 파싱한 뒤 work-log markdown을 중간 단계로 거쳐 SQLite에 기록하고 있다. 이 markdown은 누구도 읽지 않고, sync 스크립트가 다시 파싱해야 하는 불필요한 변환 단계다.

### 현재 파이프라인

```
CC:    transcript → session_logger → work-log.md → sync_cc.py → SQLite
Codex: rollout    → session_logger → work-log.md → sync_codex.py → SQLite
                                                 ↘ (JSONL도 직접 파싱)
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

ParsedData 구조 (CC와 Codex 동일한 출력):
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
1. 무의미한 날짜 슬라이스 skip (files, commands, topic 모두 없으면)
2. 각 날짜별로 `upsert_activity()` 호출
3. summary/behavioral_signals가 있으면 마지막 날짜의 레코드에 적용
4. 관련 날짜의 `update_daily_stats()` 호출
5. behavioral_signals가 있으면 `insert_behavioral_signal()` 호출

dedup은 SQLite의 `ON CONFLICT(source, session_id, date) DO UPDATE`로 처리.
`upsert_activity`의 `COALESCE(excluded.tag, tag)` / `COALESCE(excluded.summary, summary)` 로 scanner가 NULL로 넣은 뒤 SessionEnd가 값을 채울 때 덮어쓰지 않음.

기존 session_logger의 state 파일 기반 dedup 제거.

### 2. CC session_logger.py 변경

**기존:** `scan_and_record()` → `write_session_marker()` → work-log.md
**변경:** `scan_and_record()` → `record_activities()` → SQLite

변경 내용:
- `write_session_marker()`, `build_session_section()`, `build_frontmatter()` 제거
- `scan_and_record()`가 `record_activities()`를 호출하도록 변경
- `main()`의 SessionEnd 분기에서 LLM 요약 후 `record_activities()` 재호출 (summary 포함)
- dedup state 파일 로직 (`load_state`, `save_state`, `already_recorded`, `_cleanup_state`) 제거
- work-log 관련 import/상수 (`WORK_LOG_DIR`, `STATE_FILE`) 제거

### 3. Codex session_logger.py 변경

CC와 동일한 패턴으로 변경:
- `parse_rollout_by_date()` 추가 — rollout JSONL을 날짜별로 분할, ParsedData 구조로 출력
- `write_session_marker()`, `build_session_section()`, `build_frontmatter()` 등 제거
- `record_activities("codex", ...)` 호출
- dedup state 파일 로직 제거
- `compaction` 이벤트: `session_end`와 동일하게 `record_activities()` 호출. compaction 요약(`_build_compaction_summary`)은 유지하되 결과를 SQLite에 직접 기록.

### 4. `parse_rollout_by_date()` — Codex용 날짜 분할 파서

기존 `parse_transcript()` (codex session_logger.py:474)를 날짜별로 분할하는 버전.

입력 포맷 매핑:

| 데이터 | CC transcript | Codex rollout |
|--------|--------------|---------------|
| 유저 메시지 | `type:"user"` → `message.content` | `type:"event_msg"` → `payload.type:"user_message"` |
| 도구 호출 | `assistant` content `tool_use` block | `type:"response_item"` → `function_call` |
| 토큰 | `message.usage.{input,output}_tokens` | `event_msg.token_count.total_token_usage` |
| 파일 변경 | `Edit`/`Write` tool input | `write_file`/`apply_diff`/`create_file` function args |
| 에러 | `tool_result` output | `function_call_output` exit_code≠0 |
| 커밋 | `Bash` command에 `git commit` | `shell`/`execute` command에 `git commit` |

토큰 필드 정규화:
- Codex의 `total_token_usage.total_tokens`는 누적값 → 날짜별 증분으로 변환
- `api_calls`는 `token_count` 이벤트 수로 카운트
- `cache_read`, `cache_create`는 Codex에 없으므로 0

파일 변경 추출:
- `write_file`/`apply_diff`/`create_file` function_call의 arguments에서 `path` 또는 `file_path` 추출

브랜치 감지:
- Codex `session_logger.py`의 기존 `detect_repo()`는 repo만 반환. `detect_repo_and_branch()`로 확장하거나 `record_activities`에 `branch=None` 전달.

출력은 CC의 `parse_transcript_by_date()`와 동일한 `dict[str, ParsedData]`.

### 5. active_session_scanner.py 변경

`scan_and_record()` 변경을 그대로 반영. work-log 기록 대신 SQLite 직접 기록.

### 6. daily_coach.py 변경

sync 호출 제거:

```python
# 현재:
scan_active_sessions()        # CC 열린 세션 → work-log → SQLite
sync_cc_date(conn, date)      # CC work-log → SQLite
sync_codex_date(conn, date)   # Codex JSONL → SQLite
get_today_data(conn, date)    # SQLite → 리포트

# 변경:
scan_active_sessions()        # CC 열린 세션 → SQLite 직접
get_today_data(conn, date)    # SQLite → 리포트 (Codex는 이미 session_logger가 기록)
```

### 7. LLM 요약: 에이전트 직접 수행

cron.json의 daily-coach는 OpenClaw 에이전트가 실행. 에이전트 자체가 LLM이므로 미요약 세션을 직접 요약.

**SKILL.md 워크플로우 (daily-coach):**
1. `python3 daily_coach.py --json` → 당일 데이터 JSON 출력
2. 미요약 세션(tag=NULL)이 있으면, 에이전트가 topic/user_messages를 보고 직접 태그+요약 생성
3. 생성한 요약을 SQLite에 업데이트 (activity_writer의 update 함수 또는 직접 SQL)
4. 전체 데이터로 코칭 리포트 생성
5. 텔레그램 전송

이렇게 하면:
- `claude -p` subprocess 호출 없음 (correction rule 준수)
- OpenClaw에서도 동작
- 열린 세션도 의미 있는 요약이 포함된 리포트

**SessionEnd hook의 LLM 요약은 유지.** hook은 CC 세션 외부에서 실행되므로 correction rule 예외. 세션이 닫히면 즉시 요약이 SQLite에 기록됨.

### 8. cron 정리

**삭제:**
- `shared/life-dashboard-mcp/cron.json` — `sync_cc.py` 호출. session_logger가 직접 쓰므로 불필요. `sync_calendar.py`는 daily-coach 워크플로우에 포함.

**수정:**
- `shared/life-coach/cron.json` — daily-coach 워크플로우에 "미요약 세션 요약" 단계 추가

**유지:**
- news-brief, investment-manager, spending-manager cron — 영향 없음

## 제거 대상

| 파일 | 처리 |
|------|------|
| `shared/life-dashboard-mcp/sync_cc.py` | 삭제 |
| `shared/life-dashboard-mcp/sync_codex.py` | 삭제 |
| `shared/life-dashboard-mcp/_sync_common.py` | `auto_tag()`를 `activity_writer.py`로 이동 후 삭제 |
| `shared/life-dashboard-mcp/cron.json` | 삭제 (`sync_calendar.py`는 daily-coach에 통합) |
| `cc/work-digest/scripts/parse_work_log.py` | 삭제 |
| `cc/work-digest/scripts/daily_digest.py` | 삭제 (daily_coach.py가 대체) |
| `cc/work-digest/scripts/weekly_digest.py` | 삭제 (weekly_coach.py가 대체) |
| `cc/work-digest/work-log/*.md` | 생성 중단 (기존 파일 유지) |
| `codex/work-digest/work-log/*.md` | 생성 중단 (기존 파일 유지) |
| CC session_logger의 markdown 관련 함수 | 제거 |
| Codex session_logger의 markdown 관련 함수 | 제거 |
| 양쪽 session_logger의 state 파일 dedup | 제거 (SQLite upsert 대체) |

## 문서 업데이트

| 파일 | 변경 |
|------|------|
| `shared/life-coach/SKILL.md` | sync_cc/sync_codex 호출 제거, daily-coach 워크플로우에 "미요약 세션 요약" 추가 |
| `cc/work-digest/SKILL.md` | parse_work_log, daily_digest 참조 제거, SQLite 직접 기록 설명 |

## 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `shared/life-dashboard-mcp/activity_writer.py` | 신규: 공유 SQLite 기록 함수 + auto_tag 이동 |
| `cc/work-digest/scripts/session_logger.py` | markdown 제거, record_activities 호출, state 파일 dedup 제거 |
| `cc/work-digest/scripts/active_session_scanner.py` | scan_and_record 변경 반영 |
| `codex/work-digest/scripts/session_logger.py` | parse_rollout_by_date + record_activities, markdown 제거 |
| `shared/life-coach/scripts/daily_coach.py` | sync 호출 제거 |
| `shared/life-coach/SKILL.md` | 워크플로우 업데이트 |
| `shared/life-coach/cron.json` | daily-coach instructions 업데이트 |
| `cc/work-digest/SKILL.md` | 파이프라인 설명 업데이트 |
| `shared/life-dashboard-mcp/sync_cc.py` | 삭제 |
| `shared/life-dashboard-mcp/sync_codex.py` | 삭제 |
| `shared/life-dashboard-mcp/_sync_common.py` | 삭제 (auto_tag → activity_writer로 이동) |
| `shared/life-dashboard-mcp/cron.json` | 삭제 |
| `cc/work-digest/scripts/parse_work_log.py` | 삭제 |
| `cc/work-digest/scripts/daily_digest.py` | 삭제 |
| `cc/work-digest/scripts/weekly_digest.py` | 삭제 |
