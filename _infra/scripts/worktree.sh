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

cmd_list() {
  local wt_dirs=()
  if [ -d "$WT_BASE" ]; then
    for d in "$WT_BASE"/*/; do
      [ -d "$d" ] && wt_dirs+=("$d")
    done
  fi

  if [ ${#wt_dirs[@]} -eq 0 ]; then
    echo "No active worktrees."
    return
  fi

  printf "%-16s %-14s %6s %10s  %-8s  %s\n" "Name" "Branch" "Files" "+/-" "Status" "Description"
  printf "%-16s %-14s %6s %10s  %-8s  %s\n" "────────────────" "──────────────" "──────" "──────────" "────────" "───────────"

  local total_add=0 total_del=0 active=0 count=0

  for wt_path in "${wt_dirs[@]}"; do
    local name branch stat files=0 add=0 del=0 status desc
    name=$(basename "$wt_path")
    branch=$(git -C "$wt_path" branch --show-current 2>/dev/null || echo "?")
    stat=$(git -C "$wt_path" diff --stat HEAD 2>/dev/null | tail -1)

    if [ -n "$stat" ]; then
      files=$(echo "$stat" | grep -oE '[0-9]+ file' | grep -oE '[0-9]+' || echo 0)
      add=$(echo "$stat" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo 0)
      del=$(echo "$stat" | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo 0)
    fi

    status="○ clean"
    if [ "${files:-0}" -gt 0 ] 2>/dev/null; then
      status="● active"
      active=$((active + 1))
    fi

    desc=""
    if [ -f "$wt_path/.session-meta.json" ]; then
      desc=$(jq -r '.description // ""' "$wt_path/.session-meta.json" 2>/dev/null)
    fi

    printf "%-16s %-14s %6s %+5d/-%d  %-8s  %s\n" \
      "$name" "$branch" "${files:-0}" "${add:-0}" "${del:-0}" "$status" "$desc"

    total_add=$((total_add + ${add:-0}))
    total_del=$((total_del + ${del:-0}))
    count=$((count + 1))
  done

  echo ""
  echo "Active: $active/$count  |  Total: +$total_add/-$total_del"
}

case "${1:-help}" in
  create) shift; cmd_create "$@" ;;
  list)   shift; cmd_list "$@" ;;
  merge)  shift; echo "not implemented yet" ;;
  clean)  shift; echo "not implemented yet" ;;
  *)
    echo "Usage: worktree.sh {create|list|merge|clean} ..."
    exit 1
    ;;
esac
