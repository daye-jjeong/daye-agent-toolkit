#!/bin/bash
# PreCompact hook: compact로 유실되는 세션 진행 상태를 ~/.claude/compact-state.json에 저장
# session_logger.py와 병렬 등록. 서로 독립적.
# best-effort collector — 실패해도 compact를 막지 않는다.

set -u

STATE_FILE="$HOME/.claude/compact-state.json"
mkdir -p "$(dirname "$STATE_FILE")"

TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
BRANCH=$(git branch --show-current 2>/dev/null || echo "")

# plan 파일 탐색: worktree 루트 → main 레포 루트 (없으면 빈 문자열)
find_plan() {
  local search_dir="$1"
  local plans_dir="$search_dir/docs/superpowers/plans"
  if [ -d "$plans_dir" ]; then
    local found
    found=$(ls -t "$plans_dir"/*.md 2>/dev/null | head -1)
    if [ -n "$found" ]; then
      echo "$found"
      return 0
    fi
  fi
  return 0
}

PLAN_PATH=""
# (1) worktree 루트
if [ -n "$TOPLEVEL" ]; then
  PLAN_PATH=$(find_plan "$TOPLEVEL")
fi
# (2) main 레포 루트 (worktree의 commondir)
if [ -z "$PLAN_PATH" ] && [ -n "$TOPLEVEL" ]; then
  MAIN_ROOT=$(git -C "$TOPLEVEL" rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's|/.git$||' || echo "")
  if [ -n "$MAIN_ROOT" ] && [ "$MAIN_ROOT" != "$TOPLEVEL" ] && [[ "$MAIN_ROOT" == /* ]]; then
    PLAN_PATH=$(find_plan "$MAIN_ROOT")
  fi
fi

# current_task: plan 파일 내 완료/전체 체크박스 비율 (예: "3/5")
CURRENT_TASK="null"
if [ -n "$PLAN_PATH" ]; then
  DONE=$({ grep -iE '^\s*- \[x\]' "$PLAN_PATH" 2>/dev/null || true; } | wc -l | tr -d '[:space:]')
  TODO=$({ grep -E '^\s*- \[ \]' "$PLAN_PATH" 2>/dev/null || true; } | wc -l | tr -d '[:space:]')
  TOTAL=$((DONE + TODO))
  if [ "$TOTAL" -gt 0 ]; then
    CURRENT_TASK="\"$DONE/$TOTAL\""
  fi
fi

# JSON 출력 — 경로의 ", \ 등 특수문자를 이스케이프
json_str() { [ -n "${1:-}" ] && printf '"%s"' "$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')" || echo "null"; }

SAVED_AT=$(date -u +%Y-%m-%dT%H:%M:%S)

cat > "$STATE_FILE" <<EOF
{
  "saved_at": "$SAVED_AT",
  "plan_path": $(json_str "$PLAN_PATH"),
  "current_task": $CURRENT_TASK,
  "worktree_path": $(json_str "$TOPLEVEL"),
  "branch": $(json_str "$BRANCH")
}
EOF

exit 0
