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
│   ├── session_logger.py    # CC 세션 종료 시 LLM 요약 + SQLite 직접 기록 + 알림
│   ├── active_session_scanner.py  # 열린 CC 세션 탐색 + SQLite 기록
│   └── notify.sh            # permission/idle/error 알림 (stop 제외)
└── references/
    └── prompt-template.md
```

## Workflow

### Pipeline 1 — Session Logger (CC Hook: SessionEnd/PreCompact)

```
CC 세션 종료 (SessionEnd/PreCompact hook)
  → transcript에서 user/assistant 대화 추출
  → 날짜별 분할 (parse_transcript_by_date)
  → SQLite에 직접 기록 (activity_writer.record_activities)
  → SessionEnd: claude sonnet으로 [태그] + 요약 생성 → SQLite 업데이트
  → 텔레그램으로 세션 요약 알림 전송
```

태그 종류: 코딩, 디버깅, 리서치, 리뷰, ops, 설정, 문서, 기타

### Pipeline 2 — Active Session Scanner

```
daily_coach.py 실행 시 (또는 수동)
  → ~/.claude/sessions/*.json에서 열린 세션 탐색
  → 각 세션의 transcript를 날짜별로 분할
  → SQLite에 직접 기록 (요약 없이, topic만)
```

### Pipeline 3 — Daily/Weekly Coach (life-coach 스킬)

일일/주간 코칭은 `life-coach` 스킬이 담당. work-digest는 데이터 수집만.

## Telegram 설정

`telegram.conf`에서 모든 스크립트가 공통 참조:
- `BOT_TOKEN`, `CHAT_ID`: 필수
- `THREAD_SESSION`, `THREAD_DAILY`, `THREAD_WEEKLY`: Group Topics 분리 (선택)

## 피드백 루프

```
세션 → 요약 → SQLite → daily-coach → work-context.md
                                              ↓
다음 세션 시작 ← memory/work-context.md ←────┘
```

각 프로젝트의 `~/.claude/projects/{project}/memory/work-context.md`에 기록.
글로벌 규칙 `work-context-loop.md`가 세션 시작 시 참조를 안내.

## Scripts

| Script | Tier | Purpose |
|--------|------|---------|
| `session_logger.py` | 2 (LLM) | 세션 요약 + 태깅 + SQLite 기록 + 텔레그램 |
| `active_session_scanner.py` | 1 (0 tokens) | 열린 세션 탐색 + SQLite 기록 |
| `notify.sh` | 1 (0 tokens) | permission/idle/error 알림 |

## Token Usage

- Session Logger (haiku): ~500 tokens/세션
- Daily Digest (haiku): ~300-500 tokens/일
- Weekly Digest (haiku): ~500-800 tokens/주
- claude CLI 미가용 시: 0 tokens (템플릿 fallback)
