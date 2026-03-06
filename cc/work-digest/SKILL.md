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
│   ├── parse_work_log.py    # work-log .md → 구조화 JSON
│   ├── daily_digest.py      # 일일 다이제스트 + 레포별 context 갱신
│   ├── weekly_digest.py     # 주간 리포트 + reflect 질문
│   └── notify.sh            # permission/idle/error 알림 (stop 제외)
├── work-log/
│   ├── YYYY-MM-DD.md        # 일별 세션 로그 (자동 생성, git ignored)
│   └── state/
└── references/
    └── prompt-template.md
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

### Pipeline 2 — Daily Digest (Cron 21:00)

```
parse_work_log.py | daily_digest.py
  → 태그 비율 + 레포별 요약 다이제스트 → 텔레그램
  → 레포별 work-context.md → 프로젝트 auto memory
```

### Pipeline 3 — Weekly Digest (Cron 일요일 21:00)

```
weekly_digest.py --date today
  → 일별 활동 + 태그 분석 + 레포 순위 → 텔레그램
  → 🔮 reflect 질문 (패턴 기반)
  → 레포별 주간 work-context.md → 프로젝트 auto memory
```

## 자동화

| Cron | Script | 설명 |
|------|--------|------|
| `0 21 * * *` | `parse_work_log.py \| daily_digest.py` | 매일 21시 다이제스트 |
| `0 21 * * 0` | `weekly_digest.py` | 매주 일요일 21시 주간 리포트 |

## Telegram 설정

`telegram.conf`에서 모든 스크립트가 공통 참조:
- `BOT_TOKEN`, `CHAT_ID`: 필수
- `THREAD_SESSION`, `THREAD_DAILY`, `THREAD_WEEKLY`: Group Topics 분리 (선택)

## 피드백 루프

```
세션 → 요약 → work-log → 다이제스트 → work-context.md
                                              ↓
다음 세션 시작 ← memory/work-context.md ←────┘
```

각 프로젝트의 `~/.claude/projects/{project}/memory/work-context.md`에 기록.
글로벌 규칙 `work-context-loop.md`가 세션 시작 시 참조를 안내.

## Scripts

| Script | Tier | Purpose |
|--------|------|---------|
| `session_logger.py` | 2 (LLM) | 세션 요약 + 태깅 + 로그 + 텔레그램 |
| `parse_work_log.py` | 1 (0 tokens) | .md → 구조화 JSON |
| `daily_digest.py` | 2 (LLM) | 일일 다이제스트 + context 갱신 |
| `weekly_digest.py` | 2 (LLM) | 주간 리포트 + reflect |
| `notify.sh` | 1 (0 tokens) | permission/idle/error 알림 |

## Token Usage

- Session Logger (haiku): ~500 tokens/세션
- Daily Digest (haiku): ~300-500 tokens/일
- Weekly Digest (haiku): ~500-800 tokens/주
- claude CLI 미가용 시: 0 tokens (템플릿 fallback)
