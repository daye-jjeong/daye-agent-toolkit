# Calendar Sync Design

## Design

캘린더 이벤트를 life-dashboard DB에 수집하여 코칭 리포트에 통합한다.

### 데이터 소스

macOS EventKit (Swift) → Google Calendar + Apple Calendar 동시 접근.

| 캘린더 | tag | 성격 |
|--------|-----|------|
| `건강` | `운동` | 수영, 필라테스 등 |
| `daye@ronik.io` | `업무미팅` | 회사 캘린더 |
| `개인` | `개인` | 개인 일정 |
| `업무` | `업무` | 업무 일정 |
| `학습` | `학습` | 학습 일정 |

나머지 캘린더 제외. allDay 이벤트 제외.

### 아키텍처

```
Swift cal_events.swift (EventKit)
  → stdout: pipe-delimited events
  → Python sync_calendar.py 파싱
  → activities upsert (source='calendar')
  → update_daily_stats() 전체 source 집계
```

### 컴포넌트

1. `life-dashboard-mcp/scripts/cal_events.swift` — 날짜 범위 이벤트 출력
2. `life-dashboard-mcp/sync_calendar.py` — Swift 실행 + DB upsert
3. `db.py` — update_daily_stats() source 필터 제거
4. `daily_coach.py`, `weekly_coach.py` — source='cc' 필터 제거
5. cron — sync_calendar.py 추가

### session_id 생성

`cal_{date}_{hash(title+start)}` — 같은 이벤트 재수집 시 upsert로 중복 방지.
