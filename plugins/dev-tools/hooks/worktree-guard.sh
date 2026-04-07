#!/bin/bash
# PreToolUse hook: Edit/Write 시 master/main 브랜치에서 직접 수정 차단
# 모든 git 레포에서 동작. git 레포가 아니면 통과.

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"

# Edit, Write, MultiEdit만 체크
case "$TOOL_NAME" in
  Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

# git 레포가 아니면 통과
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  exit 0
fi

BRANCH=$(git branch --show-current 2>/dev/null)

# main/master 브랜치에서 코드 수정 차단
case "$BRANCH" in
  main|master)
    echo "🛑 main/master 브랜치에서 코드 수정 금지. worktree를 생성하세요."
    echo ""
    echo "git worktree add ../wt-<feature> -b feat/<feature>"
    exit 2
    ;;
esac

exit 0
