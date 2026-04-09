# Superpowers Workflow

## 세션 시작
`git worktree list` → 진행 중 worktree + 미완료 plan 있으면 이어하기 제안.

## Worktree
모든 구현은 worktree에서. read-only 탐색만 예외.
- `superpowers:using-git-worktrees` 사용. 브랜치명: `fix/xxx`, `feat/xxx`. Agent `isolation: "worktree"` 금지
- **편집 전 게이트**: `git branch --show-current`이 master/main이면 수정 거부, worktree부터
- worktree 생성 후 `npm ci`. 삭제 시 메인 레포로 `cd` 먼저
- 합리화("작은 수정/빨리 테스트/조사 중 수정") 전부 거부. 규모 무관

## 파이프라인
1. `superpowers:brainstorming` → design
2. (L: 6+파일) `/codex:adversarial-review` + `codex-cli` 프롬프트 → design 검증
3. `superpowers:writing-plans` → plan
4. worktree → 5. 구현(TDD, 태스크 경계 커밋) → 6. `superpowers:verification-before-completion`
7. `/simplify` → `pr-review-toolkit:review-pr` 순차 반복(병렬 금지, 수렴 전 머지 금지)
8. 머지 게이트 → 9. `claude-md-management:revise-claude-md`
- 학습 루프: 리뷰에서 수정 2개+ 시 반복 패턴을 `patterns.md`에 기록

## 구현 위임
- **Claude subagent** (`superpowers:subagent-driven-development`): 기본. implementer는 `model: "sonnet"` 우선
- **Codex** (`codex:rescue`): 디버깅 난항, 세컨드 오피니언. adversarial은 `/codex:adversarial-review`

## 머지 게이트
simplify+review 수렴 → `git log HEAD..master` divergence 확인(rebase) → 변경 요약 + 사용자 승인

## Subagent 모델
- implementer: `model: "sonnet"` (1-2파일 단순), `model: "opus"` (multi-file/복잡)
- spec reviewer: `model: "sonnet"` / code quality reviewer: `model: "opus"`
- BLOCKED 재dispatch: `model: "opus"`

## 커밋
worktree에서 자유롭게. 머지 전 `git rebase -i`로 정리: `fix:` squash, dist는 마지막 커밋에.

## 핸드오프
이전 세션: WIP 커밋 + plan 업데이트. 새 세션: worktree 감지 → plan → `git log -5` → 이어서.
