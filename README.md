# daye-agent-toolkit

개인 범용 에이전트 툴킷. Claude Code 플러그인 구조로 스킬/훅/규칙을 관리.

## 구조

```
skills/     — standalone 스킬 (mabinogi-mml, mabinogi-equipment-cost, mabinogi-farming)
apps/       — 우리가 만든 프로그램 (background-automator, mabinogi 데이터 플랫폼)
plugins/    — 레거시 CC 플러그인 4개 (life-management, finance, dev-tools, media-fetch)
rules/      — 글로벌 규칙 (~/.claude/rules/에 심링크)
commands/   — 범용 슬래시 커맨드
hooks/      — 세션 훅
mcp/        — MCP 서버 (life-dashboard)
codex/      — Codex CLI 전용
```

`apps/mabinogi/`는 마비노기 데이터 플랫폼 — 수집(automator)·저장(`~/.mabi/`)·분석
(farming, equipment-cost)을 나눈 프로그램 묶음. 계약은 `apps/mabinogi/README.md`.

## Setup

```bash
make install    # 마켓플레이스 등록 + 플러그인 활성화 + 규칙 심링크
make status     # 설치 상태 확인
make clean      # 등록 해제 + 심링크 제거
```

## 방침

- 개인 범용 스킬만 관리 (Cube 업무용은 cube-agent-toolkit)
- 네이밍: 하이픈(`-`) 통일, 언더스코어 금지
