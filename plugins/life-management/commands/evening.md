---
description: 저녁 액션 — 계획 vs 실제 + actual 매칭 + reflection
allowed-tools: Bash, Read
---

# /evening

매일 저녁 1회. life-coach **evening 액션** 진입점.

## 절차

1. `python3 plugins/life-management/skills/life-coach/scripts/todo_evening.py --date <오늘>` → 계획 vs 실제 + loose match JSON
2. 매칭된 task 후보 제시 → 사용자 confirm:
   ```bash
   python3 plugins/life-management/skills/life-coach/scripts/schedule_actual_link.py \
     --schedule-id N --task-id M --date <오늘> --todo-id K
   ```
   - wrapper가 task에서 date/duration/summary/repo 자동 조회
   - identity 재검증 + UNIQUE 4-tuple 검증
3. 매칭 거부/스킵이면 새 schedule 생성 후 매칭:
   ```bash
   schedule_upsert.py ... && schedule_actual_link.py ...
   ```
4. reflection 저장:
   ```bash
   python3 plugins/life-management/skills/life-coach/scripts/checkin_save.py evening \
     --date <오늘> --evening-reflection TEXT
   ```

## 룰

- actual 매칭은 schedule_id 명시 confirmation 후에만
- task duration은 wrapper가 task table에서 직접 읽음 (에이전트 입력 X)
