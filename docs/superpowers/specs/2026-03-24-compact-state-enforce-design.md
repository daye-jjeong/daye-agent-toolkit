# Pre-Compact 상태 보존 훅 + 규칙→훅 전환 제안 시스템

> 생성: 2026-03-24

## 배경

Citadel(github.com/SethGammon/Citadel) 분석에서 도출한 두 가지 개선점:

1. **compact 후 컨텍스트 손실** — 규칙으로 "plan 다시 읽기"를 명시했지만, 어떤 plan을 읽어야 하는지, 몇 번째 태스크인지 정보가 사라짐
2. **규칙 위반 반복** — correction-memory에 같은 유형의 교정이 쌓이지만, 마크다운 규칙은 LLM이 무시할 수 있음. 훅으로 강제하면 무시 불가

## 파트 1: Pre-Compact 상태 보존 훅

### 목표

compact 직전에 세션 진행 상태를 JSON으로 저장하여, compact 후 즉시 복구 가능하게 한다.

### 저장 정보

```json
{
  "saved_at": "2026-03-24T14:30:00",
  "plan_path": "docs/superpowers/plans/2026-03-24-pre-compact-hook.md",
  "current_task": "3/7",
  "worktree_path": "/Users/dayejeong/git_workplace/.worktrees/feat/pre-compact-hook",
  "branch": "feat/pre-compact-hook"
}
```

| 필드 | 수집 방법 |
|------|-----------|
| `saved_at` | `date -u +%Y-%m-%dT%H:%M:%S` |
| `plan_path` | (1) worktree 루트 `docs/superpowers/plans/` 최신 `.md` → (2) 없으면 main 레포 루트 동일 경로 탐색 → (3) 둘 다 없으면 `null` |
| `current_task` | plan 파일 내 체크박스 카운트 (`[x]`/`[ ]`/`~~strike~~`). 파싱 실패 시 `null` |
| `worktree_path` | `git rev-parse --show-toplevel` |
| `branch` | `git branch --show-current` |

### 저장 위치

`~/.claude/compact-state.json` (홈 디렉토리 고정 경로). worktree에는 `.claude/` 디렉토리가 없을 수 있으므로 고정 경로가 안전하다.

### 복원 방식

**훅이 아닌 규칙으로 처리.** `superpowers-workflow-gates.md`에 명령형 지시 추가:

> compact 직후: `~/.claude/compact-state.json` 파일을 Read하라. 존재하면 plan_path를 열고 current_task부터 이어서 진행. 읽은 후 파일을 삭제하라.

SessionStart 훅은 만들지 않는다. 이유: compact는 세션 중간에 발생하므로 SessionStart 시점과 맞지 않음. 규칙은 `~/.claude/rules/`에 심링크되어 시스템 프롬프트에 항상 존재하므로 compact 후에도 보인다.

### stale 상태 처리

복원 후 파일을 삭제한다. 이전 세션의 잔존 파일이 새 세션을 오염시키지 않도록. 추가로, `saved_at`가 24시간 이상 경과한 파일은 stale로 간주하고 복원 없이 삭제한다.

### 기존 PreCompact 훅과의 관계

`session_logger.py`(DB 백업)와 병렬 등록. 같은 이벤트에 훅 여러 개 가능. 서로 독립적.

## 파트 2: 규칙→훅 전환 제안 시스템

### 목표

correction-memory에 반복 쌓이는 교정 패턴을 감지하여, 훅으로 강제할 수 있는 후보를 제안한다. 설치는 사용자 승인 후에만.

### 트리거 A: correction-protocol 규칙 추가

`cc/correction-memory/rules/correction-protocol.md`에 한 줄 추가:

> 같은 토픽의 Layer 2 register에 엔트리 3개 이상이면, "이 패턴은 훅으로 강제하는 게 효과적일 수 있다"고 사용자에게 제안하라.

카운트 기준: Layer 2 `corrections/{topic}.md` 파일 내 `- [YYYY-MM-DD]` 엔트리 수.

### 트리거 B: `/enforce` 온디맨드 스킬

`cc/enforce/SKILL.md` 신규 생성. 실행 시:

1. **수집** — Layer 1 (`~/.claude/rules/correction-*.md`) + Layer 2 (`corrections/*.md`) + Layer 3 (`corrections/log/*.md`) 전체 스캔
2. **감지** — 같은 토픽 3회+ 반복 패턴 식별
3. **분류** — 위반 유형별 훅 매핑:

| 위반 유형 | 훅 이벤트 | 예시 |
|-----------|-----------|------|
| 특정 파일 수정 금지 | PreToolUse (Edit/Write) | `.env` 직접 수정 |
| 코드 패턴 사용 금지 | PostToolUse | `console.log` 잔존 |
| 절차 누락 | Stop | 테스트 미실행 |
| 명령어 사용 금지 | PreToolUse (Bash) | `git push --force` |

4. **제안** — 각 후보별: 교정 이력 요약 + 훅 코드 초안 (bash) + settings.json 등록 명령어
5. **설치** — 사용자 승인 시 LLM이 직접 `~/.claude/settings.json`을 Edit 도구로 수정. 훅 스크립트를 `_infra/cc/`에 Write한 뒤 settings.json의 hooks 배열에 등록

### `/enforce` 스킬은 코드를 생성하지 않는다

훅 코드 초안은 **LLM이 교정 내용을 읽고 직접 작성**한다. 별도 코드 생성 스크립트 없음. SKILL.md가 프레임워크를 제공하고, LLM이 실행 주체. (스킬 스크립트에서 LLM subprocess 호출 금지 규칙 준수)

## 변경 파일 목록

| 파일 | 변경 | 신규/수정 |
|------|------|-----------|
| `_infra/cc/save-compact-state.sh` | 상태 수집 + JSON 저장 | 신규 |
| `~/.claude/settings.json` | PreCompact 훅 등록 추가 | 수정 |
| `cc/global-rules/rules/superpowers-workflow-gates.md` | compact 후 상태 파일 읽기 규칙 추가 | 수정 |
| `cc/correction-memory/rules/correction-protocol.md` | 3회 반복 시 훅 전환 제안 문구 추가 | 수정 |
| `cc/enforce/SKILL.md` | 규칙→훅 전환 스킬 | 신규 |
| `cc/enforce/.claude-skill` | 스킬 메타데이터 | 신규 |
| `CLAUDE.md` | 스킬 목록 테이블에 enforce 추가 | 수정 |

## 엣지케이스 처리

| 케이스 | 처리 |
|--------|------|
| plan 파일 없음 (ad-hoc 세션) | `plan_path`, `current_task` = null. worktree/branch만 저장 |
| plan 여러 개 | worktree → main 순 탐색, 최신 수정 시간 기준 1개 |
| 체크박스 파싱 실패 | `current_task` = null, graceful fallback |
| compact-state.json 잔존 | 복원 후 삭제. 규칙에 명시 |
| correction 반복 카운트 모호 | Layer 2 파일 내 `- [YYYY-MM-DD]` 엔트리 수 기준 |
