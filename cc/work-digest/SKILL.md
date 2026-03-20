---
name: work-digest
description: 일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Work Digest Skill

**Version:** 2.0.0 | **Updated:** 2026-03-06 | **Status:** Active

Claude Code 세션 로그를 자동 기록하고, LLM 요약 + 작업 유형 태깅으로 일일/주간 다이제스트를 생성한다.
텔레그램 알림 + 프로젝트별 작업 컨텍스트 피드백 루프 포함.

## File Structure

```
work-digest/
├── SKILL.md
├── .claude-skill
├── telegram.conf            # Telegram 설정 (단일 소스)
├── scripts/
│   ├── session_logger.py    # CC 세션 종료 시 LLM 요약 + 로그 + 알림
│   ├── active_session_scanner.py  # 열린 세션 스캔 + DB 기록
│   ├── parse_work_log.py    # work-log .md → 구조화 JSON (sync용)
│   └── notify.sh            # permission/idle/error 알림 (stop 제외)
├── work-log/
│   └── YYYY-MM-DD.md        # 일별 세션 로그 (자동 생성, git ignored)
└── references/
    └── topic-creation-guide.md
```

## Workflow

### Pipeline 1 — Session Logger (CC Hook: SessionEnd/PreCompact)

```
CC 세션 종료
  → transcript에서 user/assistant 대화 추출
  → claude haiku로 [태그] + 2-3줄 요약 생성
  → work-log/YYYY-MM-DD.md에 기록
  → 텔레그램으로 세션 요약 알림 전송
```

태그 종류: 코딩, 디버깅, 리서치, 리뷰, ops, 설정, 문서, 기타

일일/주간 다이제스트는 `life-coach` 스킬로 이관됨 (`daily_coach.py`, `weekly_coach.py`).

## Telegram 설정

`telegram.conf`에서 모든 스크립트가 공통 참조:
- `BOT_TOKEN`, `CHAT_ID`: 필수
- `THREAD_SESSION`, `THREAD_DAILY`, `THREAD_WEEKLY`: Group Topics 분리 (선택)

## Scripts

| Script | Purpose |
|--------|---------|
| `session_logger.py` | CC hook — 세션 종료 시 SQLite 기록 + LLM 요약 + 텔레그램 |
| `active_session_scanner.py` | 열린 세션 스캔 + DB 기록 |
| `parse_work_log.py` | work-log .md → JSON (sync용) |
| `notify.sh` | permission/idle/error 알림 |
