# Superpowers Workflow

멀티 세션 환경 전제. 상세 절차는 각 스킬 참조.

## 세션 시작

1. `git worktree list` → 진행중 worktree + 미완료 plan 있으면 이어하기 제안
2. 새 작업이면 아래 워크플로우 진행

## 항상 Worktree

모든 구현 작업은 worktree에서 시작. 규모 무관. 예외: read-only 탐색.

생성 우선순위: gitflow 스킬 → `worktree.sh` → `git worktree add`
완료 우선순위: gitflow 스킬 → `worktree.sh merge` → `finishing-a-development-branch` 스킬

## 규모 판단 → 워크플로우

| 규모 | 기준 | 워크플로우 |
|------|------|-----------|
| **S** | 1-2 파일, 단순 수정 | worktree → 코딩 → 테스트 → 완료 |
| **M** | 3-5 파일, 또는 코어/아키텍처/불확실성 높음 | worktree → brainstorming → plan → Codex 리뷰 → TDD 구현 → 자기검증 → [자동] simplify + pr-review → 완료 |
| **L** | 6+ 파일 | M + Ralph Loop 평가 |

단순 rename/이동은 파일 수 많아도 하위 티어 적용 가능.

## M 파이프라인 요약

1. `superpowers:brainstorming` → 디자인 합의 → plan `## Design`에 기록
2. `superpowers:writing-plans` → plan 생성
3. `codex-cli` exec 모드로 plan 리뷰 (타당한 피드백만 반영)
4. 메인 세션이 직접 구현 (TDD or 수동검증). 태스크 경계에서 커밋
5. `superpowers:verification-before-completion` → 자기검증
6. [자동] `/simplify` → `/pr-review-toolkit:review-pr` → 수렴 확인 → 완료 알림
7. 사용자 OK 후 완료 (자동 완료 금지)

## 핸드오프

이전 세션: WIP 커밋 + plan 진행 상태 업데이트
새 세션: worktree 감지 → plan 읽기 → `git log -5` → 이어서 진행

## 공통

- Process 스킬(brainstorming/debugging) 먼저, 그 다음 implementation 스킬
- compact 후 plan 다시 읽고 현재 단계 재확인
- S는 brainstorming/plan 면제
