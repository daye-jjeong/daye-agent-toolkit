#!/bin/bash
# worktree.sh — Gate 0.5 worktree lifecycle manager
# Usage:
#   worktree.sh create <name> [description]
#   worktree.sh list
#   worktree.sh merge <name> [--dry-run]
#   worktree.sh clean <name>
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
WT_BASE="$REPO_ROOT/.claude/worktrees"

cmd_create() {
  local name="$1"
  local desc="${2:-}"
  local wt_path="$WT_BASE/$name"
  local branch="wt/$name"

  if [ -d "$wt_path" ]; then
    echo "ERROR: worktree '$name' already exists at $wt_path" >&2
    exit 1
  fi

  local base_branch
  base_branch=$(git -C "$REPO_ROOT" branch --show-current)
  local base_sha
  base_sha=$(git -C "$REPO_ROOT" rev-parse --short HEAD)

  mkdir -p "$WT_BASE"
  git -C "$REPO_ROOT" worktree add -b "$branch" "$wt_path" HEAD

  # Write session metadata
  cat > "$wt_path/.session-meta.json" <<METAEOF
{
  "name": "$name",
  "description": "$desc",
  "created": "$(date -u +%Y-%m-%dT%H:%M:%S%z)",
  "base_branch": "$base_branch",
  "base_sha": "$base_sha"
}
METAEOF

  echo "✓ worktree created: $name"
  echo "  path:   $wt_path"
  echo "  branch: $branch (from $base_branch @ $base_sha)"
  [ -n "$desc" ] && echo "  desc:   $desc"
}

case "${1:-help}" in
  create) shift; cmd_create "$@" ;;
  list)   shift; echo "not implemented yet" ;;
  merge)  shift; echo "not implemented yet" ;;
  clean)  shift; echo "not implemented yet" ;;
  *)
    echo "Usage: worktree.sh {create|list|merge|clean} ..."
    exit 1
    ;;
esac
