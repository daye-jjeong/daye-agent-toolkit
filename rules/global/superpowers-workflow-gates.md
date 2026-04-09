# Superpowers Workflow

## 세션 시작
`git worktree list` → 진행 중 worktree + 미완료 plan 있으면 이어하기 제안.

## Worktree (모든 구현 작업)
- 모든 구현은 worktree에서. read-only 탐색만 예외
- `superpowers:using-git-worktrees` 사용. 브랜치명: `fix/xxx`, `feat/xxx`. Agent 도구 `isolation: "worktree"` 금지
- **편집 전 게이트**: `git branch --show-current`이 master/main이면 수정 거부, worktree부터 만들어라
- worktree 생성 후 `npm ci`(또는 lockfile 명령)
- 삭제 시 메인 레포로 `cd` 먼저, `worktree remove + branch -d + push`는 한 체인

### 합리화 거부
"작은 수정/빨리 테스트/이미 진행 중/merge 후 추가/조사 중 수정 필요" — 전부 거부. 규모 무관, 수정 전 worktree 생성.

## 파이프라인
1. `superpowers:brainstorming` → 디자인 합의
2. `superpowers:writing-plans` → plan 생성
3. (L: 6+ 파일) `codex-cli` adversarial 모드로 plan 교차 리뷰
4. worktree 생성
5. 구현 (TDD, 태스크 경계 커밋)
6. `superpowers:verification-before-completion`
7. `/simplify` → `pr-review-toolkit:review-pr` 순차 반복 (병렬 금지). 수렴 전 머지 옵션 금지
8. 머지 게이트
9. `claude-md-management:revise-claude-md`

## 머지 게이트
1. simplify + pr-review 수렴
2. `git log HEAD..master --oneline`로 divergence 확인. 새 커밋 있으면 rebase 먼저
3. 변경 요약 (파일/내용/효과) + 사용자 승인 필수

## 커밋
- worktree에서 자유롭게: 태스크 1개 완료, simplify/review 수렴 후, 핸드오프, 사용자 요청 시. 루프 중간엔 묻지 마라
- 머지 전 `git rebase -i`로 정리: `fix:` squash, dist 리빌드는 마지막 커밋에 포함

## 핸드오프
- 이전 세션: WIP 커밋 + plan 진행 상태 업데이트
- 새 세션: worktree 감지 → plan 읽기 → `git log -5` → 이어서
- compact 직후: `~/.claude/compact-state.json` 있으면 plan_path 열고 current_task 위치부터. 24h+ stale이면 삭제만
