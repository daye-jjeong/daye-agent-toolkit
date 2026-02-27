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

cmd_merge() {
  local name="$1"
  local dry_run=false
  [ "${2:-}" = "--dry-run" ] && dry_run=true

  local wt_path="$WT_BASE/$name"
  local branch="wt/$name"

  if [ ! -d "$wt_path" ]; then
    echo "ERROR: worktree '$name' not found" >&2
    exit 1
  fi

  # Read base branch from metadata
  local base_branch="main"
  if [ -f "$wt_path/.session-meta.json" ]; then
    base_branch=$(jq -r '.base_branch // "main"' "$wt_path/.session-meta.json" 2>/dev/null)
  fi

  # Check for uncommitted changes in worktree
  if ! git -C "$wt_path" diff --quiet HEAD 2>/dev/null; then
    echo "ERROR: worktree '$name' has uncommitted changes. Commit or stash first." >&2
    echo "  path: $wt_path"
    exit 1
  fi

  # Dry run: show what would be merged
  if $dry_run; then
    echo "=== Dry run: merge $branch → $base_branch ==="
    git -C "$REPO_ROOT" log --oneline "$base_branch..$branch" 2>/dev/null
    echo ""
    git -C "$REPO_ROOT" diff --stat "$base_branch...$branch" 2>/dev/null
    return
  fi

  # Create backup tag
  local tag="backup/wt-${name}-$(date +%Y%m%d-%H%M%S)"
  git -C "$REPO_ROOT" tag "$tag" "$branch"
  echo "✓ backup tag: $tag"

  # Merge
  local current_branch
  current_branch=$(git -C "$REPO_ROOT" branch --show-current)

  if [ "$current_branch" != "$base_branch" ]; then
    git -C "$REPO_ROOT" checkout "$base_branch"
  fi

  if git -C "$REPO_ROOT" merge --no-ff "$branch" -m "merge: $name (from worktree)"; then
    echo "✓ merged $branch → $base_branch"

    # Cleanup (--force needed because .session-meta.json is untracked)
    git -C "$REPO_ROOT" worktree remove --force "$wt_path"
    git -C "$REPO_ROOT" branch -d "$branch"
    echo "✓ cleaned up worktree and branch"
  else
    echo "ERROR: merge conflict. Resolve manually:" >&2
    echo "  git merge --abort   # to cancel" >&2
    echo "  # or resolve conflicts, then: git commit" >&2
    echo "  # backup tag: $tag" >&2
    exit 1
  fi
}

cmd_clean() {
  local name="$1"
  local wt_path="$WT_BASE/$name"
  local branch="wt/$name"

  if [ ! -d "$wt_path" ]; then
    echo "ERROR: worktree '$name' not found" >&2
    exit 1
  fi

  git -C "$REPO_ROOT" worktree remove --force "$wt_path"
  echo "✓ removed worktree: $wt_path"

  if git -C "$REPO_ROOT" branch -D "$branch" 2>/dev/null; then
    echo "✓ deleted branch: $branch"
  fi
}

case "${1:-help}" in
  create) shift; cmd_create "$@" ;;
  list)   shift; cmd_list "$@" ;;
  merge)  shift; cmd_merge "$@" ;;
  clean)  shift; cmd_clean "$@" ;;
  *)
    echo "Usage: worktree.sh {create|list|merge|clean} ..."
    exit 1
    ;;
esac
