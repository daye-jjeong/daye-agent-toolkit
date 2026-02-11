---
name: vault-memory
description: Obsidian vault 기반 메모리 관리 — 일일/주간 노트, 압축, 보존
---

# Vault Memory Plugin

> Version: 0.1.0 | Status: Active | Updated: 2026-02-11

밍밍 공유 볼트(`memory/`) 기반 메모리 관리 플러그인.
Claude Code와 OpenClaw 양쪽에서 동일한 세션 기록, 컨텍스트 복원, 장기 기억 관리를 수행한다.

## 기록 규격

**반드시 먼저 읽을 것**: `memory/format.md`
모든 볼트 쓰기 작업은 format.md 규격을 따른다.

## 서브커맨드

### Core Memory

| 커맨드 | 파일 | 설명 |
|--------|------|------|
| `vault-memory:compress` | [compress.md](compress.md) | 세션 종료 전 구조화 저장 |
| `vault-memory:resume` | [resume.md](resume.md) | 이전 세션 컨텍스트 복원 |
| `vault-memory:preserve` | [preserve.md](preserve.md) | MEMORY.md 영구 저장 |

### Daily Operations

| 커맨드 | 파일 | 설명 |
|--------|------|------|
| `vault-memory:daily-note` | [daily-note.md](daily-note.md) | 일간 계획 생성 |
| `vault-memory:meeting-note` | [meeting-note.md](meeting-note.md) | 미팅 노트 구조화 |
| `vault-memory:inbox-process` | [inbox-process.md](inbox-process.md) | +inbox/ 정리 |
| `vault-memory:weekly-review` | [weekly-review.md](weekly-review.md) | 주간 회고 |

## 공유 경로

| 용도 | 경로 |
|------|------|
| 기록 규격 | `memory/format.md` |
| 세션 로그 | `memory/YYYY-MM-DD.md` (flat) |
| 장기 기억 | `memory/MEMORY.md` |
| 런타임 상태 | `memory/state/*.json` |
| 인박스 | `memory/+inbox/` |
| 일간 목표 | `memory/goals/daily/` |
| 주간 목표 | `memory/goals/weekly/` |
| 월간 목표 | `memory/goals/monthly/` |

## 사용법

**Claude Code**: `/vault-memory:compress` 등 슬래시 커맨드로 호출
**OpenClaw**: 이 SKILL.md 읽은 후 해당 서브커맨드의 .md 파일을 읽고 따라갈 것

## 자동 기록

Claude Code는 `SessionEnd` hook으로 `.jsonl` 트랜스크립트를 자동 파싱하여
기본 세션 마커(수정 파일, 명령어, 에러)를 `memory/YYYY-MM-DD.md`에 append한다.
`/vault-memory:compress`는 이 마커를 AI 분석으로 보강(enrich)한다.
