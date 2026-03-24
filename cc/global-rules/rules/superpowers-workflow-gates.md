# Superpowers Workflow

## 세션 시작

1. `git worktree list` → 진행중 worktree + 미완료 plan 있으면 이어하기 제안
2. orphan worktree 감지: `git merge-base --is-ancestor <commit> HEAD`로 머지 완료된 worktree 삭제 제안
3. 새 작업이면 규모 판단 후 워크플로우 진행

## Worktree

모든 구현 작업은 worktree에서 시작. 규모 무관. 예외: read-only 탐색.

`superpowers:using-git-worktrees` 스킬로 생성. 기능명 기반 브랜치(`fix/xxx`, `feat/xxx`). Agent 도구의 `isolation: "worktree"`는 사용하지 마라 — 랜덤 ID 이름이라 식별 불가.

## 규모별 파이프라인

작업 시작 전 반드시 규모를 판단하고 사용자에게 알려라. 단순 rename/이동은 파일 수 많아도 하위 티어 적용 가능.

### S/M 공통 파이프라인

1. `superpowers:brainstorming` → 디자인 합의 + spec 작성
2. `superpowers:writing-plans` → plan 생성 (스킬 내장 리뷰어가 자동 검증)
3. worktree 생성
4. 구현 (TDD, 태스크 경계에서 커밋)
5. `superpowers:verification-before-completion`
6. `/simplify` → `pr-review-toolkit:review-pr` → 수렴까지 반복
   ⚠ subagent-driven-development, executing-plans 등 스킬 흐름이 이 단계를 건너뛰고 finishing으로 안내할 수 있음 — 스킬 무관하게 이 순서를 지켜라
7. 머지 게이트

### L (6+ 파일)

S/M과 동일 + 2번과 3번 사이에 `codex-cli` exec 모드로 plan 교차 리뷰.

## 머지 게이트

모든 규모에서 머지 전 필수:

1. **divergence 체크** — `git log HEAD..master --oneline`으로 확인. master에 새 커밋 있으면 rebase 먼저.
2. **변경 요약** — 파일 목록 + 뭘 바꿨는지 + 효과
3. **사용자 승인** — 승인 없이 머지하지 마라

## 커밋 전략

### worktree에서 (자유롭게)
1. plan 태스크 1개 완료 + 테스트 통과 시
2. simplify/pr-review 수렴 후
3. 세션 종료/핸드오프 시 (WIP 커밋)
4. 사용자가 명시적으로 요청 시

파일 수정 직후, 루프 중간에는 커밋을 묻지 마라.

### 머지 전 정리 (rebase -i)
머지 게이트 진입 전 `git rebase -i`로 커밋 히스토리를 정리한다:
- `fix:` 수정 커밋 → 관련 `feat:`/`refactor:` 커밋에 squash
- `build: rebuild dist` → 마지막 커밋에 포함
- 논리 단위별 커밋은 유지 (AI 리뷰어가 각 커밋의 의도를 파악할 수 있도록)

dist 리빌드를 별도 커밋으로 만들지 마라.

## 보고

작업 중 항상 **현재 위치 + 다음 행동**을 함께 보고하라.

- ❌ "커밋할까요?"
- ✅ "태스크 2/4 완료, 테스트 통과. 커밋하고 태스크 3 진행할게."

## 디버깅 루프 탈출

같은 접근법으로 3회 이상 실패하면 해당 접근을 버리고 재시작하라. 같은 에러를 다른 방법으로 고치는 것도 "같은 접근"이다. 재시작 시:
1. 현재까지의 시도와 실패 원인을 정리
2. `git stash` 또는 `git checkout -- .`로 변경 초기화
3. 다른 접근법으로 처음부터 시작

## 핸드오프

이전 세션: WIP 커밋 + plan 진행 상태 업데이트
새 세션: worktree 감지 → plan 읽기 → `git log -5` → 이어서 진행

## 기타

- Process 스킬(brainstorming/debugging) 먼저, 그 다음 implementation 스킬
- compact 직후: `~/.claude/compact-state.json`을 Read하라. 존재하면 plan_path의 plan을 열고 current_task 위치부터 이어서 진행하라. 읽은 후 파일을 삭제하라. `saved_at`가 24시간 이상 경과했으면 stale — 복원 없이 삭제만 하라. 파일이 없으면 무시.
