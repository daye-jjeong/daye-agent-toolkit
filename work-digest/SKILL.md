---
name: work-digest
description: 일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Work Digest Skill

**Version:** 1.0.0 | **Updated:** 2026-02-27 | **Status:** Active

Claude Code 세션 로그를 자동 기록하고, 매일 저녁 하루의 작업을 요약하여 텔레그램으로 전송하는 하이브리드 스킬.
목표 대비 갭 분석 + 작업 패턴 피드백 포함.

## Trigger

- 크론 `21:00` 자동 실행
- 수동 호출 가능

## File Structure

```
work-digest/
├── SKILL.md
├── .claude-skill
├── scripts/
│   ├── session_logger.py      # CC 세션 종료 시 로그 기록 (훅)
│   ├── parse_work_log.py      # work-log .md → 구조화 JSON
│   └── daily_digest.py        # JSON → LLM 요약 + 텔레그램 전송
├── work-log/
│   ├── YYYY-MM-DD.md          # 일별 세션 로그 (자동 생성, git ignored)
│   └── state/
│       └── session_logger_state.json
└── references/
    └── prompt-template.md     # LLM 프롬프트 템플릿
```

## Workflow

### Pipeline 1 — Session Logger (CC Hook)

```
CC 세션 종료 → session_logger.py (stdin JSON) → work-log/YYYY-MM-DD.md
```

각 세션의 메타데이터를 마크다운으로 기록:
- 시각, 레포, 수정 파일, 실행 명령, 에러, 주제

### Pipeline 2 — Daily Digest (Cron)

```
parse_work_log.py --date today | daily_digest.py → 텔레그램 전송
```

1. `parse_work_log.py`: 당일 .md 파싱 → 구조화 JSON (stdout)
2. `daily_digest.py`: JSON → `claude -p --model haiku` 분석 → 텔레그램 전송
   - claude CLI 미사용 시 템플릿 기반 fallback

## 자동화

| Cron | Script | 설명 |
|------|--------|------|
| `0 21 * * *` | `parse_work_log.py \| daily_digest.py` | 매일 21시 다이제스트 생성 + 전송 |

## Scripts

| Script | Tier | Purpose | Args |
|--------|------|---------|------|
| `session_logger.py` | 1 (0 tokens) | CC 세션 로그 기록 | stdin JSON (CC 훅) |
| `parse_work_log.py` | 1 (0 tokens) | .md → 구조화 JSON | `--date YYYY-MM-DD` |
| `daily_digest.py` | 2 (LLM) | 요약 + 텔레그램 전송 | `--dry-run`, `--no-llm` |

## Input / Output

### Input

| Source | Purpose |
|--------|---------|
| `work-log/YYYY-MM-DD.md` | 당일 세션 로그 |
| goal-planner daily YAML | 목표 대비 갭 분석 (optional) |
| `{baseDir}/references/prompt-template.md` | LLM 프롬프트 템플릿 |

### Output — 텔레그램 메시지

4개 섹션: 시간 요약, 레포별 작업, 목표 대비 진행, 패턴 피드백.
텔레그램 4096자 제한 준수.

**프롬프트 상세**: `{baseDir}/references/prompt-template.md` 참고

## Token Usage

- Session Logger + Parse: ~0 tokens (no LLM)
- Daily Digest (haiku): ~300-500 tokens/day
- claude CLI 미가용 시: 0 tokens (템플릿 fallback)
