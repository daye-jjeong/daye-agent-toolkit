#!/bin/bash
# wd — worktree dashboard
# Warp 탭에서 실행하여 모든 worktree 상태를 실시간 모니터링
#
# Usage:
#   wd          # 5초 간격 자동 새로고침
#   wd --once   # 한번만 출력

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKTREE_SH="$SCRIPT_DIR/../scripts/worktree.sh"

if [ ! -x "$WORKTREE_SH" ]; then
  echo "ERROR: worktree.sh not found at $WORKTREE_SH" >&2
  exit 1
fi

if [ "${1:-}" = "--once" ]; then
  "$WORKTREE_SH" list
  exit 0
fi

# Live dashboard with watch (fallback to loop if watch not available)
if command -v watch &>/dev/null; then
  watch -n 5 -t "'$WORKTREE_SH' list"
else
  while true; do
    clear
    echo "worktree dashboard  (refresh: 5s, Ctrl+C to exit)"
    echo ""
    "$WORKTREE_SH" list
    sleep 5
  done
fi
