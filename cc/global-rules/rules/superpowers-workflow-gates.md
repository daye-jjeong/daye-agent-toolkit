# Superpowers Workflow (Lightweight)

토큰 효율 우선. 멀티 세션 환경 전제.

---

## 세션 시작: 진행중 작업 감지

새 세션이 시작되면 **가장 먼저** 진행중 작업이 있는지 확인한다:

1. `git worktree list`로 기존 worktree 확인
2. worktree 안에 미완료 plan 파일(`docs/plans/`)이 있으면 사용자에게 질문:
   > "진행중인 작업 `<name>`이 있습니다. 이어서 할까요, 새 작업을 시작할까요?"
3. 이어하기 → 세션 핸드오프 절차 (아래 참조)
4. 새 작업 → 정상 워크플로우 시작

---

## 전제: 항상 Worktree

사용자는 Warp 탭 여러 개로 같은 레포에 동시 작업한다.
**모든 구현 작업은 worktree에서 시작한다.** 규모 무관.

- 세션 시작 시 worktree 생성 (아래 우선순위)
- 이미 worktree 안이면 skip
- 유일한 예외: read-only 탐색/리서치

### Worktree 생성 방법 (우선순위)
1. 프로젝트에 `worktree.sh`가 있으면 → `worktree.sh create <name> "desc"`
2. 없으면 → `git worktree add .claude/worktrees/<name> -b <name>`

### Worktree merge 방법 (우선순위)
1. 프로젝트에 `worktree.sh`가 있으면 → `worktree.sh merge <name>`
2. 없으면 → 아래 merge 절차 참조

### Merge 절차 (공통)
1. **먼저 rebase:** `git rebase main` — 다른 worktree가 먼저 merge한 변경사항 반영
2. 충돌 발생 시 → 사용자에게 알리고 수동 해결 안내 (자동 해결 시도하지 않음)
3. rebase 성공 시 → dry-run으로 확인 → 사용자 OK → merge
4. worktree 정리: `git worktree remove <path> && git branch -d <name>`

---

## 규모 판단

| 규모 | 기본 기준 | 적용 워크플로우 |
|------|-----------|-----------------|
| **S** | 1-2 파일, 단순 수정 | worktree → 직접 코딩 → 테스트 → merge |
| **M** | 3-5 파일 | worktree → brainstorming → (plan) → 구현 → 검증 → 리뷰 → merge |
| **L** | 6+ 파일 | M + plan 필수 + Ralph Loop 평가 |

**복잡도 보정:** 파일 수가 적어도 다음에 해당하면 상위 티어 적용:
- 코어 로직/아키텍처 변경 → M 이상
- 새로운 패턴/인프라 도입 → M 이상
- 불확실성이 높은 작업 (원인 불명 버그 등) → M 이상
- 반대로, 단순 rename/이동이 여러 파일이면 하위 티어 적용 가능

---

## S: 직접 코딩

worktree 생성 후 바로 작업:
- 단일 파일 버그/타입 수정
- 설정 변경
- 사용자가 구체적 지시를 내린 경우
- 디버깅 (`systematic-debugging` 사용)

**완료 전 최소 게이트:**
- 테스트가 있는 프로젝트 → 관련 테스트 실행, 통과 확인 후 merge
- 테스트가 없는 프로젝트 → 변경 영향 범위 확인 후 merge

---

## M: 경량 파이프라인

### 1. Brainstorming
- `superpowers:brainstorming` 스킬 실행
- 디자인 합의 후, 합의된 내용을 plan 파일 상단 `## Design` 섹션에 기록
  - plan을 안 쓰는 경우에도 `docs/plans/<name>.md`에 디자인만 기록
  - compact/핸드오프 시 디자인 의도가 보존됨

### 2. Plan (선택)
- 태스크 3개 이상이면 `superpowers:writing-plans`로 plan 파일 생성
- 2개 이하면 plan 없이 바로 구현
- 신규 파일 경로만 codebase에서 확인

### 3. 메인 세션이 직접 구현
- **테스트 가능한 코드:** `superpowers:test-driven-development` 따라 RED → GREEN → REFACTOR
- **테스트 불가한 코드** (CSS, 설정, 인프라, 프로토타입): 구현 후 수동 검증 가능한 확인 방법 제시
- plan이 있으면 각 태스크 완료 시 plan 파일에 체크
- **서브에이전트 없음** — 메인 세션이 전부 수행

### 4. Context 관리
- **태스크 경계에서 커밋** → 코드는 git에 저장됨
- **context 부족 시 `/compact`** → plan 파일 다시 읽고 이어서 진행
- **한 태스크에서 5개+ 파일을 새로 읽어야 할 때** → 해당 태스크만 서브에이전트에 위임 (context 보호)

### 5. 자기 검증 (리뷰 전 필수)
- `superpowers:verification-before-completion` 스킬 실행
- **Design 섹션 대비 확인** — brainstorming에서 합의한 설계가 구현에 반영되었는지
- plan이 있으면 **모든 항목 하나씩 대조** — 체크 안 된 항목은 구현
- plan이 없으면 `git diff` 보면서 원래 요구사항 대비 누락 확인
- 테스트 전부 실행, 통과 확인
- **"다 했다"고 판단한 후에만** 리뷰로 넘어감

### 6. 완료 리뷰
- `git diff` 전체를 `superpowers:code-reviewer` 서브에이전트 1개에 전달
- plan이 있으면 plan 대비 누락 체크 포함
- Critical/Important 이슈 수정 후 커밋

### 7. Simplify
- 리뷰 이슈 수정 후 `simplify` 스킬 실행
- 3개 병렬 에이전트(Code Reuse, Code Quality, Efficiency)가 diff를 분석하고 직접 수정
- 수정사항이 있으면 커밋

### 8. Merge
- simplify 완료 후, 사용자에게 merge 제안
- 사용자가 OK하면 merge 절차 실행 (rebase → dry-run → merge)
- 사용자가 요청하기 전에 자동 merge하지 않음

---

## L: 확장 파이프라인

M과 동일한 구조. 다음만 다름:

- **Plan 필수** (M은 선택)
- **Ralph Loop 평가:** 각 태스크 실행 전, 자동검증 조건 + 반복패턴 + 20분+ 예상 → 3개 충족시 `/ralph-loop` 제안 (M에서도 조건 충족 시 제안 가능)

---

## 세션 핸드오프 (토큰 부족 → 새 세션)

토큰이 부족해서 새 Warp 탭에서 새 세션을 시작하는 경우:

### 이전 세션이 해야 할 것
- 현재까지 작업을 **커밋** (WIP 커밋도 OK)
- plan 파일에 **진행 상태 업데이트** (완료 항목 체크, 현재 진행중 항목 표시)

### 새 세션이 해야 할 것
- 세션 시작 시 자동 감지 (위의 "세션 시작: 진행중 작업 감지" 참조)
- 사용자가 이어하기 선택 시:
  1. 해당 worktree로 이동
  2. plan 파일 읽기 → 어디까지 했는지 파악
  3. `git log --oneline -5`로 최근 커밋 확인
  4. 미완료 태스크부터 이어서 진행

---

## 공통 규칙

- **Process 스킬 우선:** brainstorming/debugging → implementation 스킬
- **compact 후:** plan 파일 다시 읽고 현재 워크플로우 단계를 재확인
- **면제 사항:** S 규모 작업에는 brainstorming/plan 불필요

---

## Quick Reference

```
[세션 시작] git worktree list → 진행중 작업 있으면 이어하기 제안

[S] worktree → 직접 코딩 → 테스트 실행 → merge

[M] worktree → brainstorming → (plan) → 메인 구현 (TDD or 수동검증)
    → 자기 검증 → 완료 리뷰 (1 서브에이전트) → simplify → rebase → merge

[L] worktree → brainstorming → plan → 메인 구현 (+ Ralph 평가)
    → 자기 검증 → 완료 리뷰 → simplify → rebase → merge

[핸드오프] 이전: WIP 커밋 + plan 업데이트 → 새 세션: 자동 감지 → 이어서
```
