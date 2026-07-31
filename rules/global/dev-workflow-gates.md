# Worktree 게이트

모든 구현은 worktree에서. read-only 탐색만 예외. `EnterWorktree` 도구로 만든다(이름은 도구가 정한다).

- **편집 전 게이트**: `git branch --show-current`가 main/master면 수정 거부, worktree부터
- `EnterWorktree`는 origin/<default> 기준 분기 → 로컬 main이 앞설 수 있다. 머지 전 `git rebase main` 필수
- 생성 후 의존성 설치(프로젝트에 맞게) → `code --add <worktree-절대경로>`로 LSP 진단 정상화. 삭제 시 메인 레포로 `cd` 먼저
- 합리화("작은 수정/빨리 테스트/조사 중 수정") 전부 거부. 규모 무관
- **메인 레포 클린 게이트**: 메인 체크아웃은 항상 `git status` clean. 코드·문서·plan 종류 무관. 메인에서 무심코 만든 파일은 즉시 worktree로 `mv`

## 머지

변경 요약 + 사용자 명시 승인. 머지 전 `git log HEAD..main`으로 divergence 확인.
