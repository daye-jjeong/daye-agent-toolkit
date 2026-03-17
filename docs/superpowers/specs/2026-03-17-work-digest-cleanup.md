# Work-Digest 정리 + "정리해줘" 스킬 완성

## 목적

session-topics 구현 과정에서 쌓인 실패 코드를 정리하고,
"정리해줘" 기능을 work-digest 스킬의 일부로 완성한다.

## 변경 요약

### 1. extract 스크립트 이동

`shared/life-dashboard-mcp/scripts/` → `cc/work-digest/scripts/`

- extract_session.py
- extract_day.py

이유: extract는 .jsonl 파싱이지 DB CRUD가 아님. work-digest(수집+정리)에 속함.

### 2. work-digest SKILL.md — "정리해줘" 절차 추가

```
"정리해줘" 실행 흐름:

1. extract_day.py 실행 → segments (결정적)
2. LLM이 각 segment에 대해:
   - session_topics: tag, summary, status, follow_up (segment 1:1)
   - signals: decisions, mistakes, patterns (같은 분석에서 동시 추출)
3. 검증: segment 수 = topic 수, 시간 일치, tag↔메시지 대조
4. update-topics CLI로 DB 저장
```

### 3. life-coach SKILL.md — 역할 변경

- Step 3a: "정리해줘" 직접 수행 → work-digest 위임
- 코칭 시 session_topics 없으면: work-digest의 "정리해줘"를 먼저 실행
- life-coach 역할: 리포트 생성 + 코칭 분석

### 4. extract_day.py 개선

- 메시지 cap: 10개 → 20개로 증가
- 열린 세션 지원: sessions 테이블에 없어도 .jsonl 직접 탐색

### 5. signals 생성

"정리해줘"에서 토픽과 동시에 signals 저장.
기존 signals 테이블(session_id 기반) 사용 — 새 테이블 추가 안 함.

### 6. 실패 코드 정리

session_logger.py에서 삭제:
- summarize_session()
- _parse_topics_response()
- _parse_summary_response() 유지 (다른 곳에서 사용 가능성)
- _compute_topic_segments()
- _compute_work_unit_time_ranges()
- _extract_work_unit()
- file_timeline 수집 로직
- activity_segments 계산 로직
- main()에서 LLM subprocess 호출 부분

activity_writer.py에서 삭제:
- record_sessions()의 topic_segments/proto-topic 분기
- 단, update-topics CLI는 유지

active_session_scanner.py에서 삭제:
- projects 디렉토리 스캔 (proto-topic용이었음)
- proto-topic 생성 보호 로직

### 7. scanner cwd 하드코딩 개선

`known_prefix = "-Users-dayejeong-"` → 환경 변수 또는 `Path.home()` 기반으로 동적 생성

## 변경 파일 목록

| 파일 | 변경 |
|------|------|
| `cc/work-digest/SKILL.md` | "정리해줘" 절차 추가 |
| `cc/work-digest/scripts/extract_session.py` | 이동 (from life-dashboard-mcp) |
| `cc/work-digest/scripts/extract_day.py` | 이동 + 메시지 cap 증가 + 열린 세션 지원 |
| `cc/work-digest/scripts/session_logger.py` | 실패 코드 삭제 |
| `cc/work-digest/scripts/active_session_scanner.py` | proto-topic 코드 삭제, cwd 개선 |
| `shared/life-dashboard-mcp/activity_writer.py` | topic_segments 분기 삭제 |
| `shared/life-coach/SKILL.md` | Step 3a를 work-digest 위임으로 변경 |
