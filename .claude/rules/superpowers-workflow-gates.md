# Superpowers Workflow — 프로젝트 오버라이드

글로벌 규칙(`~/.claude/rules/superpowers-workflow-gates.md`)을 따르되,
이 프로젝트에서는 다음을 오버라이드한다.

## Worktree 명령어

이 레포에는 전용 스크립트가 있다. 글로벌의 `git worktree` 대신 이것을 사용:

- **생성:** `"$CLAUDE_PROJECT_DIR"/_infra/scripts/worktree.sh create <name> "desc"`
- **목록:** `"$CLAUDE_PROJECT_DIR"/_infra/scripts/worktree.sh list`
- **병합:** `"$CLAUDE_PROJECT_DIR"/_infra/scripts/worktree.sh merge <name>`
- **대시보드:** 별도 Warp 탭에서 `wd` 실행 (`_infra/cc/wd.sh`)
