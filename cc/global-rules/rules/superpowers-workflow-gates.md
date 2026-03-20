# Superpowers Workflow

## 세션 시작

1. `git worktree list` → 진행중 worktree + 미완료 plan 있으면 이어하기 제안
2. 새 작업이면 규모 판단 후 워크플로우 진행

## 항상 Worktree

모든 구현 작업은 worktree에서 시작. 규모 무관. 예외: read-only 탐색.

**생성 방법**: Agent 도구의 `isolation: "worktree"` 사용. `.worktrees/`에 자동 생성되며 cwd도 전환된다. `superpowers:using-git-worktrees` 스킬이나 수동 `git worktree add`는 사용하지 마라.

## 규모 판단

작업 시작 전 반드시 규모를 판단하고 사용자에게 알려라.

| 규모 | 기준 | 워크플로우 |
|------|------|-----------|
| **S** | 1-2 파일, 단순 수정 | worktree → 코딩 → 테스트 → simplify + pr-review → 사용자 승인 → 머지 |
| **M** | 3-5 파일, 또는 불확실성 높음 | 아래 M 파이프라인 |
| **L** | 6+ 파일 | M + codex plan 리뷰 |

단순 rename/이동은 파일 수 많아도 하위 티어 적용 가능.

## M 파이프라인

1. `superpowers:brainstorming` → 디자인 합의 + spec 작성 (스킬 내장 체크리스트 따름)
2. `superpowers:writing-plans` → plan 생성 + plan review loop (스킬 내장 subagent)
3. 구현 (TDD, 태스크 경계에서 커밋)
4. `superpowers:verification-before-completion` → 자기검증
5. `/simplify` → `pr-review-toolkit:review-pr` → 수렴까지 반복
6. **사용자 머지 승인** → 명시적 확인 후 진행
7. `superpowers:finishing-a-development-branch` → 완료 처리

## L 추가 사항

2번과 3번 사이에: `codex-cli` exec 모드로 plan 교차 리뷰. 구현 착수 전 완료할 것.

## 머지 게이트

**모든 규모에서 머지 전 필수:**
1. `/simplify` + `pr-review-toolkit:review-pr` 실행 (S 포함)
2. **변경 요약 작성** — 사용자에게 다음을 보여줌:
   - 변경된 파일 목록 (`git diff main...HEAD --stat`)
   - 뭘 바꿨는지 (기능/수정/삭제 요약 1-3줄)
   - 어떤 효과가 있는지 (동작 변화, 삭제된 기능, 새 의존성 등)
3. 사용자에게 머지 승인 요청 — 승인 없이 머지하지 마라

Why: 리뷰 없이 머지하면 cross-file 불일치, 불필요한 코드가 그대로 반영된다. 변경 요약 없이 승인 요청하면 사용자가 뭘 승인하는지 모른다.

## 보고 규칙

작업 중 항상 **현재 위치 + 다음 행동**을 함께 보고하라.

- ❌ "커밋할까요?"
- ✅ "태스크 2/4 완료, 테스트 통과. 커밋하고 태스크 3 진행할게."

## 커밋 시점

1. plan 태스크 1개 완료 + 테스트 통과 시
2. simplify/pr-review 수렴 후
3. 세션 종료/핸드오프 시 (WIP 커밋)
4. 사용자가 명시적으로 요청 시

파일 수정 직후, 루프 중간에는 커밋을 묻지 마라.

## 핸드오프

이전 세션: WIP 커밋 + plan 진행 상태 업데이트
새 세션: worktree 감지 → plan 읽기 → `git log -5` → 이어서 진행

## 공통

- Process 스킬(brainstorming/debugging) 먼저, 그 다음 implementation 스킬
- compact 후 plan 다시 읽고 현재 단계 재확인
- S는 brainstorming/plan 면제
