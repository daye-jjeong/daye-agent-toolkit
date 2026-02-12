---
name: vault-memory
description: Obsidian vault 기반 메모리 + 태스크 관리 — 기록, 압축, 보존, 정책 동기화, 프로젝트 추적
---

# Vault Memory Plugin

> Version: 0.3.0 | Status: Active | Updated: 2026-02-11

밍밍 공유 볼트(`memory/`) 기반 메모리 + 프로젝트 태스크 관리 플러그인.
Claude Code와 OpenClaw 양쪽에서 동일한 세션 기록, 컨텍스트 복원, 태스크 공유를 수행한다.

## 기록 규칙

**파일별 뭘 기록하는지**: [recording-rules.md](recording-rules.md)
**기록 포맷 규격**: `memory/format.md`
**태스크 템플릿**: `memory/.obsidian/templates/task-template.md`

## 서브커맨드

### Core Memory

| 커맨드 | 파일 | 설명 |
|--------|------|------|
| `vault-memory:compress` | [compress.md](compress.md) | 세션 종료 전 구조화 저장 + 태스크 자동 감지 |
| `vault-memory:resume` | [resume.md](resume.md) | 활성 태스크 + 세션 컨텍스트 복원 |
| `vault-memory:preserve` | [preserve.md](preserve.md) | MEMORY.md 영구 저장 |
| `vault-memory:sync-agents` | [sync-agents.md](sync-agents.md) | 세션 결정 → AGENTS.md 반영 |

### Project Tasks

| 커맨드 | 파일 | 설명 |
|--------|------|------|
| `vault-memory:task-create` | [task-create.md](task-create.md) | 태스크 생성 (description 필수) |
| `vault-memory:task-update` | [task-update.md](task-update.md) | 태스크 수정 (status, progress, enrich) |
| `vault-memory:task-brief` | [task-brief.md](task-brief.md) | 프로젝트/태스크 현황 브리핑 |

### Goals

| 커맨드 | 파일 | 설명 |
|--------|------|------|
| `vault-memory:goal-create` | [goal-create.md](goal-create.md) | 목표 YAML 생성 (monthly/weekly/daily) |
| `vault-memory:goal-update` | [goal-update.md](goal-update.md) | 목표 진행률/회고/상태 업데이트 |
| `vault-memory:goal-brief` | [goal-brief.md](goal-brief.md) | 목표 현황 브리핑 + 태스크 크로스 참조 |

### Daily Operations

| 커맨드 | 파일 | 설명 |
|--------|------|------|
| `vault-memory:daily-note` | [daily-note.md](daily-note.md) | 일간 계획 생성 |
| `vault-memory:meeting-note` | [meeting-note.md](meeting-note.md) | 미팅 노트 구조화 |
| `vault-memory:inbox-process` | [inbox-process.md](inbox-process.md) | +inbox/ 정리 |
| `vault-memory:weekly-review` | [weekly-review.md](weekly-review.md) | 주간 회고 |

### Reference

| 파일 | 설명 |
|------|------|
| [recording-rules.md](recording-rules.md) | 파일별 기록 대상/트리거/플랫폼별 규칙 |

## 공유 경로

| 용도 | 경로 |
|------|------|
| 기록 규칙 | [recording-rules.md](recording-rules.md) |
| 기록 포맷 | `memory/format.md` |
| 시스템 정책 | `~/clawd/AGENTS.md` |
| 장기 기억 | `memory/MEMORY.md` |
| 세션 로그 | `memory/YYYY-MM-DD.md` (flat) |
| 프로젝트/태스크 | `memory/projects/{type}/{name}/` |
| 태스크 템플릿 | `memory/projects/config/task-template.yml` |
| 목표 | `memory/goals/{daily,weekly,monthly}/` |
| 설계 문서 | `memory/docs/` |
| 정책 상세 | `memory/policy/` |
| 산출물/리서치 | `memory/reports/` |
| 런타임 상태 | `memory/state/*.json` |
| 인박스 | `memory/+inbox/` |

## 기록 흐름

```
세션 중 작업 발생
    │
    ├─ 새 태스크? ────── → t-*.md (task-create, description 필수)
    ├─ 프로젝트 작업? ── → t-*.md (task-update) + 세션 로그 (compress)
    ├─ 목표 수립? ────── → goals/*.yml (goal-create, goal-planner가 내용 결정)
    ├─ 일회성 결정? ──── → 세션 로그 (compress)
    ├─ 반복 규칙? ────── → AGENTS.md (sync-agents)
    ├─ 개인 정보/선호? ── → MEMORY.md (preserve)
    └─ 산출물? ─────── → reports/ 또는 docs/
```

## 크로스 플랫폼 태스크 공유

```
Claude Code                    memory/projects/          OpenClaw
    │                              │                        │
    ├── task-update ──────→ t-*.md ←──────── task-update ──┤
    ├── compress ─────────→ YYYY-MM-DD.md ←── compress ─────┤
    └── resume ←──────────── 활성 태스크 ──────→ resume ─────┘
```

- **t-*.md** 개별 파일이 양쪽의 공유 태스크 단위
- **## 진행 로그**로 누가 뭘 했는지 추적
- **## 코드 변경**으로 코드 연결 (repo, branch, PR)
- **핸드오프**: 진행 로그에 `[HANDOFF → 플랫폼]` 메모

## 스크립트

| 파일 | 용도 | 티어 |
|------|------|------|
| `scripts/compound_review.py` | 야간 자동 세션 리뷰 — 세션 로그 파싱 → MEMORY.md/AGENTS.md 반영 | Tier 2 |

### 자동화

| 스케줄 | 스크립트 | 설명 |
|--------|---------|------|
| `30 22 * * *` | `compound_review.py` | 야간 compound review (매일 22:30) |

## 자동 기록

- **SessionEnd hook** (Claude Code): `.jsonl` 파싱 → `memory/YYYY-MM-DD.md`에 세션 마커 append
- **vault-session-save cron** (OpenClaw): 30분마다 세션 대화 자동 기록
- **compress → task-update 연계**: 프로젝트 작업 감지 시 t-*.md 업데이트 제안
- **compress → sync-agents 연계**: 정책성 결정 감지 시 AGENTS.md 반영 제안
- **compress → preserve 연계**: 장기 보관 가치 발견 시 MEMORY.md 저장 제안
- **알림**: 태스크 상태 변경 시 텔레그램 알림 (recording-rules.md 참조)
