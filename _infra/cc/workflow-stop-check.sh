#!/bin/bash
# Stop hook: 구현 작업 세션에서만 워크플로우 보고 강제
# worktree 안에서 작업 중일 때만 block, 그 외는 통과

INPUT="$(cat 2>/dev/null || echo '{}')"

# 무한 루프 방지: 이미 한 번 block 당한 후면 통과
STOP_ACTIVE="$(echo "$INPUT" | grep -o '"stop_hook_active":[a-z]*' | cut -d: -f2 || true)"
[ "$STOP_ACTIVE" = "true" ] && exit 0

# worktree 안에 있는지 확인 (구현 작업 = worktree 사용)
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

TOPLEVEL="$(git rev-parse --show-toplevel 2>/dev/null || true)"
# .claude/worktrees/ 경로 안에 있으면 worktree 작업 중
if [[ "$TOPLEVEL" != *"/.claude/worktrees/"* ]]; then
  exit 0
fi

cat <<'HOOKJSON'
{
  "decision": "block",
  "reason": "워크플로우 보고 체크 (worktree 작업 감지):\n1. 이번에 뭘 했는지 한 줄 요약\n2. M/L 작업이면: simplify + pr-review 돌렸는지\n3. 다음에 뭘 해야 하는지\n\n보고 후 다시 멈춰라."
}
HOOKJSON
