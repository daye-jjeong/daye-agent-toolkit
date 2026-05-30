# Superpowers Workflow

## 세션 시작
`git worktree list` → 진행 중 worktree + 미완료 plan 있으면 이어하기 제안.

## Worktree
모든 구현은 worktree에서. read-only 탐색만 예외.
- `superpowers:using-git-worktrees` 사용. 브랜치명: `fix/xxx`, `feat/xxx`. Agent `isolation: "worktree"` 금지
- `EnterWorktree`는 origin/<default> 기준 분기 → 로컬 main이 앞설 수 있음. 머지 전 `git rebase main` 필수
- **편집 전 게이트**: `git branch --show-current`이 master/main이면 수정 거부, worktree부터
- worktree 생성 후 `npm ci` → `code --add <worktree-absolute-path>` (LSP 진단 정상화). 삭제 시 메인 레포로 `cd` 먼저
- 합리화("작은 수정/빨리 테스트/조사 중 수정") 전부 거부. 규모 무관
- **메인 레포 클린 게이트**: 메인 레포(`dev`/`main` 체크아웃)는 항상 `git status` clean을 유지한다. 코드·문서·plan/design/correction 룰 — 종류 무관 어떤 unstaged/untracked도 두지 마라. 두 허용 패턴:
  - (a) **선-worktree**: 주제·범위 윤곽 잡힌 시점에 worktree 먼저 → 그 안에서 작성
  - (b) **후-이동**: 메인에서 무심코 작성한 경우 즉시 worktree 만들고 `mv`로 이동
  어긋나면 `git pull`이 origin과 충돌, husky가 commit/push 차단, stash 공유 사고로 번짐. 산출물 누적 → cleanup PR 부채

## 파이프라인
1. `superpowers:brainstorming` → design
2. (L: 6+파일) `/codex:adversarial-review` + `codex-cli` 프롬프트 → design 검증
3. `superpowers:writing-plans` → plan
4. worktree → 5. 구현(TDD, 태스크 경계 커밋) → 6. `superpowers:verification-before-completion`
7. `/simplify` → `pr-review-toolkit:review-pr` 순차 반복(병렬 금지, 수렴 전 머지 금지)
8. 머지 게이트 → 9. `claude-md-management:revise-claude-md`
- 학습 루프: 리뷰에서 수정 2개+ 시 반복 패턴을 `patterns.md`에 기록

## 구현 위임
- **Claude subagent 순차** (`superpowers:subagent-driven-development`): 태스크 순차 의존·소수·검토 필요. 기본. implementer는 `model: "sonnet"` 우선
- **Claude dynamic workflow 병렬** (Workflow 도구): 태스크 독립·대량·기계적, 또는 광범위 감사/대형 마이그레이션
- **Codex** (`codex:rescue`): 디버깅 난항, 세컨드 오피니언. adversarial은 `/codex:adversarial-review`

### Dynamic workflow 자동 사용
- (a) 독립·대량·기계적 또는 (b) 광범위 감사/대형 마이그레이션이면 `workflow` 키워드 없이도 Claude가 판단해 사용
- 실행 전 한 줄 통보(무엇을 왜). 비용 큰 run은 짧게 확인
- 부적합엔 안 씀: 설계·계획·리뷰(병렬 금지), 소규모(1-3파일), 디버깅 초기. ultracode 상시 안 켬

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
