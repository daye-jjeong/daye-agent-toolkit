---
name: vault-memory
description: Obsidian vault 기반 메모리 관리 — 기록, 압축, 보존, 정책 동기화
---

# Vault Memory Plugin

> Version: 0.2.0 | Status: Active | Updated: 2026-02-11

밍밍 공유 볼트(`memory/`) 기반 메모리 관리 플러그인.
Claude Code와 OpenClaw 양쪽에서 동일한 세션 기록, 컨텍스트 복원, 장기 기억 관리를 수행한다.

## 기록 규칙

**파일별 뭘 기록하는지**: [recording-rules.md](recording-rules.md)
**기록 포맷 규격**: `memory/format.md`

## 서브커맨드

### Core Memory

| 커맨드 | 파일 | 설명 |
|--------|------|------|
| `vault-memory:compress` | [compress.md](compress.md) | 세션 종료 전 구조화 저장 |
| `vault-memory:resume` | [resume.md](resume.md) | 이전 세션 컨텍스트 복원 |
| `vault-memory:preserve` | [preserve.md](preserve.md) | MEMORY.md 영구 저장 |
| `vault-memory:sync-agents` | [sync-agents.md](sync-agents.md) | 세션 결정 → AGENTS.md 반영 |

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
| [recording-rules.md](recording-rules.md) | 파일별 기록 대상/트리거/금지 규칙 |

## 공유 경로

| 용도 | 경로 |
|------|------|
| 기록 규칙 | [recording-rules.md](recording-rules.md) |
| 기록 포맷 | `memory/format.md` |
| 시스템 정책 | `~/clawd/AGENTS.md` |
| 장기 기억 | `memory/MEMORY.md` |
| 세션 로그 | `memory/YYYY-MM-DD.md` (flat) |
| 목표 | `memory/goals/{daily,weekly,monthly}/` |
| 설계 문서 | `memory/docs/` |
| 정책 상세 | `memory/policy/` |
| 산출물/리서치 | `memory/reports/` |
| 런타임 상태 | `memory/state/*.json` |
| 인박스 | `memory/+inbox/` |

## 기록 흐름

```
세션 중 결정 발생
    │
    ├─ 일회성? ──────── → 세션 로그 (compress)
    ├─ 반복 규칙? ────── → AGENTS.md (sync-agents)
    ├─ 개인 정보/선호? ── → MEMORY.md (preserve)
    └─ 산출물? ─────── → reports/ 또는 docs/
```

## 자동 기록

- **SessionEnd hook**: `.jsonl` 파싱 → `memory/YYYY-MM-DD.md`에 세션 마커 append
- **vault-session-save cron**: 30분마다 메인 세션 대화 자동 기록
- **compress**: 세션 마커를 AI 분석으로 보강 + 정책성 결정 감지 시 `sync-agents` 제안
- **compress → preserve 연계**: 장기 보관 가치 발견 시 `preserve` 제안
