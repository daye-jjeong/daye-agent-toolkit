---
name: work-digest
description: 일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Work Digest Skill

**Version:** 1.0.0 | **Updated:** 2026-02-27 | **Status:** Experimental

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
│   ├── session_logger.py      # CC 세션 종료 시 로그 기록
│   ├── parse_work_log.py      # work-log → 구조화 JSON
│   └── daily_digest.py        # JSON → 요약 + 텔레그램 전송
├── work-log/
│   ├── YYYY-MM-DD.jsonl       # 일별 세션 로그 (자동 생성)
│   └── state/
│       └── last_digest.json   # 마지막 다이제스트 상태
└── references/
    └── prompt-template.md     # LLM 프롬프트 템플릿
```

## Workflow

### Pipeline 1 — Session Logger (CC Hook)

```
CC 세션 종료 → session_logger.py → work-log/YYYY-MM-DD.jsonl
```

각 세션의 메타데이터를 JSONL로 기록:
- 시작/종료 시각, 레포, 주요 파일, 커밋, 요약

### Pipeline 2 — Daily Digest (Cron)

```
work-log/YYYY-MM-DD.jsonl → parse_work_log.py → /tmp/work_digest.json
                           → daily_digest.py  → 텔레그램 전송
```

1. `parse_work_log.py`: 당일 JSONL 파싱 → 구조화 JSON
2. `daily_digest.py`: JSON + LLM 프롬프트 → 요약 생성 → 텔레그램 전송

## 자동화

| Cron | Script | 설명 |
|------|--------|------|
| `0 21 * * *` | `parse_work_log.py \| daily_digest.py` | 매일 21시 다이제스트 생성 + 전송 |

## Scripts

| Script | Tier | Purpose | Key Args |
|--------|------|---------|----------|
| `session_logger.py` | 1 (0 tokens) | CC 세션 로그 기록 | `--repo`, `--session-id` |
| `parse_work_log.py` | 1 (0 tokens) | JSONL → 구조화 JSON | `--date`, `--output` |
| `daily_digest.py` | 2 (LLM) | 요약 생성 + 텔레그램 전송 | `--input`, `--goals` |

## Input / Output

### Input

| File | Purpose |
|------|---------|
| `work-log/YYYY-MM-DD.jsonl` | 당일 세션 로그 |
| `{baseDir}/references/prompt-template.md` | LLM 프롬프트 템플릿 |

### Output — 텔레그램 메시지

4개 섹션: 시간 요약, 레포별 작업, 목표 대비 진행, 패턴 피드백.
텔레그램 4096자 제한 준수.

**프롬프트 상세**: `{baseDir}/references/prompt-template.md` 참고

## Token Usage

- Session Logger + Parse: ~0 tokens (no LLM)
- Daily Digest: ~300-500 tokens (요약 + 피드백)
- Total: ~300-500 tokens/day

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Skill Skeleton | Complete | SKILL.md, .claude-skill, references |
| 2. session_logger.py | Pending | CC hook 연동 |
| 3. parse_work_log.py | Pending | JSONL 파서 |
| 4. daily_digest.py | Pending | LLM 요약 + 텔레그램 |
| 5. Cron Deployment | Pending | OpenClaw cron 등록 |
