---
description: 캐파 누적 조회 — markdown 표 + 4종 flag
allowed-tools: Bash, Read
---

# /capacity

캐파 데이터 누적 조회. 기본 최근 7일.

## 실행

```bash
python3 plugins/life-management/skills/life-coach/scripts/capacity.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

## 출력

markdown 표:

| 날짜 | 가용 | 계획 | 실측 | 잔여 | 에너지 | 블로커 | 상태 |

상태 종류:
- `OK` — 정상
- `⚠ planned_overbook` — `sum(planned_min) > available_min`
- `⚠ actual_overrun` — `sum(actual) > available_min`
- `⚠ time_conflicts(N)` — schedule 시간대 겹침
- `⚠ missing_budget` — schedule 있는데 캐파 답 안 함 (`available_status='unknown'`만 해당, `'skipped'`는 `ℹ`로 별도 표시)
- `ℹ skipped` — 캐파 명시 스킵
