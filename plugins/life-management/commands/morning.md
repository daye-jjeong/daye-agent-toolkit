---
description: 아침 액션 — 우선순위 + 캐파 인터뷰 + WIP/슬롯 잡기
allowed-tools: Bash, Read
---

# /morning

매일 아침 1회 호출. life-coach skill의 **morning 액션** 진입점.

## 절차

1. `python3 plugins/life-management/skills/life-coach/scripts/todo_morning.py --date <오늘>` → 우선순위 JSON
2. 사용자에게 우선순위 제시 + 캐파 인터뷰 (life-coach SKILL.md §인터뷰 가이드라인 참조)
3. 사용자 답변을 wrapper로 저장:
   ```bash
   python3 plugins/life-management/skills/life-coach/scripts/checkin_save.py morning \
     --date <오늘> \
     (--available-hours N | --skip-available) \
     (--energy low|mid|high | --skip-energy) \
     (--blockers TEXT | --skip-blockers) \
     [--morning-intent TEXT] [--wip-ids 13,20]
   ```
4. WIP 슬롯 잡기:
   ```bash
   python3 plugins/life-management/skills/life-coach/scripts/schedule_upsert.py \
     --todo-id N --date <오늘> [--planned-min M | --start HH:MM --end HH:MM]
   ```
5. `python3 plugins/life-management/skills/life-coach/scripts/capacity.py --start <오늘> --end <내일>` → overbook/conflict 보고

## 룰

- 모든 read/write는 wrapper 경유. db.py 직접 호출 금지.
- 캐파 답이 모호하면 명확해질 때까지 재질문. "스킵" 명시일 때만 `--skip-*`.
- WIP limit 2 (todo_crud.py가 강제)
