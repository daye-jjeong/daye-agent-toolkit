# Life Coach — Design Document

**Date:** 2026-03-07 | **Status:** Approved

## Problem

CC, OpenClaw, Claude Desktop을 매일 사용하지만 활동 데이터가 분산되어 있어서:
- 하루에 뭘 얼마나 했는지 통합 파악 불가
- 과작업/운동 부족 등 생활 패턴 인식 부재
- 반복 작업의 자동화 기회 놓침
- 업무 방향성에 대한 피드백 없음

## Design

### Architecture: 데이터 허브 MCP + 코치 스킬 (분리형)

```
[데이터 소스]                    [life-dashboard-mcp]        [life-coach 스킬]
CC work-log/*.md ──────┐
OpenClaw gateway.log ──┼──→  수집 + 정규화 + SQLite  ──→  분석 + 코칭 + 알림
Google Calendar ───────┤          ↑                        (CC/OpenClaw 스킬)
iCloud CalDAV ─────────┘     cron sync                      ↓
                                                       텔레그램 / 세션 내
```

### Component 1: life-dashboard-mcp

Python MCP 서버. 모든 데이터를 SQLite에 정규화하여 저장.

**데이터 소스:**
- CC work-log/*.md — parse_work_log.py 로직 재활용
- OpenClaw gateway.log + agents/*/sessions/
- Google Calendar API (회사, 읽기 전용)
- iCloud CalDAV (개인, 읽기)

**SQLite 스키마:**
- `activities` — 정규화된 활동 (source, start_at, end_at, duration_min, tags, repo, summary)
- `calendar_events` — 양쪽 캘린더 일정 (source, title, start, end, calendar_name)
- `daily_stats` — 일별 집계 캐시 (work_hours, session_count, tag_breakdown, repos)
- `coach_state` — 코칭 상태 (escalation_level, streak_data, goals)

**MCP Tools:**
- `sync_now` — 즉시 데이터 동기화
- `get_today_summary` — 오늘 활동 요약 (작업시간, 세션, 태그, 레포)
- `get_weekly_summary` — 주간 집계
- `get_work_hours(date)` — 특정일 작업시간 통계
- `get_calendar_events(date_range)` — 캘린더 일정
- `get_patterns(days)` — N일간 행동 패턴 (시간대, 태그 비율, 연속일)
- `get_coach_state` / `update_coach_state` — 에스컬레이션 레벨 등

**Sync (cron 5분 또는 hourly):**
- CC work-log: 파일 mtime 비교 → 변경분만 파싱
- OpenClaw: gateway.log tail + agent session 파일
- Calendar: Google API + iCloud CalDAV fetch

### Component 2: life-coach 스킬

shared/ 디렉토리에 배치 (CC + OpenClaw 양쪽).

**파일 구조:**
```
shared/life-coach/
├── SKILL.md
├── .claude-skill
├── scripts/
│   ├── daily_coach.py      # 일일 코칭 리포트 → 텔레그램
│   ├── weekly_coach.py     # 주간 코칭 → 텔레그램
│   └── alert.py            # 실시간 경고 (8h+ 과작업 등)
└── references/
    ├── coaching-prompts.md  # LLM 코칭 프롬프트
    └── escalation.md       # 에스컬레이션 룰
```

**실행 방식:**
- `/coach` — 온디맨드 (CC/OpenClaw 세션 내)
- cron 21:00 — daily_coach.py → 텔레그램
- cron 일요일 21:00 — weekly_coach.py → 텔레그램
- cron 매시 — alert.py (8h+ 감지 시 텔레그램 push)

**코칭 톤 에스컬레이션:**
```
Level 0 (기본 B+C): "오늘 12시간 작업. 운동 없었다. 내일은 어떻게 할까?"
Level 1 (3일 연속 10h+, B): "3일 연속 10시간 넘김. 번아웃 위험. 내일 6시간 제한 제안."
Level 2 (7일 연속 or 미개선, A): "7일 연속 과작업. 내일 오후 7시 이후 작업 금지."
```

에스컬레이션 레벨은 coach_state에 저장. 개선되면 자동 하향.

**일일 리포트 구성:**
1. 오늘의 정리 — 작업 시간, 레포별 요약, 태그 비율
2. 코칭 — 패턴 기반 제안 (과작업, 수면, 집중도)
3. 자동화 제안 — 반복 명령/작업 감지
4. 내일 캘린더 — 예정된 일정 미리보기
5. 건강 넛지 — 운동, 휴식 알림

### Component 3: work-digest 보강 (P1에서 같이 수정)

session_logger.py 2가지 수정:

**1) 세션 종료 시간 추가:**
- transcript의 마지막 timestamp를 `end_time`으로 기록
- work-log 헤더에 `## 세션 00:03~00:40` 형식으로 변경

**2) 요약 태그 품질 개선:**
- `[기타]` 비율을 줄이기 위해 프롬프트 수정
- 태그를 세분화하거나, "기타"일 때 보조 태그 추가

### work-digest와의 관계

| | work-digest (유지) | life-coach (신규) |
|---|---|---|
| 역할 | CC 세션 로그 기록 + 작업 요약 | 통합 행동 분석 + 코칭 + 넛지 |
| 데이터 | CC 세션만 | CC + OpenClaw + Calendar |
| 출력 | "오늘 뭘 했다" (팩트) | "이렇게 바꿔라" (제안) |
| 텔레그램 | 세션/다이제스트 스레드 | 코칭 전용 스레드 |

work-digest는 그대로 유지. life-dashboard-mcp가 work-digest의 work-log/*.md를 읽는 구조.

## 저장소 마이그레이션 경로

Phase 1: SQLite (로컬, ~/life-dashboard/data.db)
Future: 필요 시 Supabase로 교체 — MCP 내부만 변경, 스킬/도구 인터페이스 불변

## Phases

| Phase | 범위 | 규모 |
|-------|------|------|
| P1 | MCP 기본 (SQLite + CC 데이터 sync) + work-digest 보강 + 일일 코칭 | M |
| P2 | OpenClaw 로그 + 캘린더(Google + iCloud) 연동 + 주간 코칭 | M |
| P3 | 실시간 경고 (8h+ push) + 에스컬레이션 로직 + 자동화 제안 | S-M |
| P4 | /coach 온디맨드 + 패턴 분석 고도화 | M |

## Decisions

- MCP 서버 언어: Python (stdlib + sqlite3, 외부 패키지 최소화)
- Calendar 접근: Google API (OAuth, dy-jarvis 크레덴셜 재활용), iCloud (CalDAV, tsdav or python caldav)
- LLM 코칭: claude CLI + haiku (work-digest와 동일 패턴)
- 텔레그램: work-digest telegram.conf 공유
- MCP 배포: CC .mcp.json + OpenClaw config에 등록
