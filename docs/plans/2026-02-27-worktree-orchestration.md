# Worktree Orchestration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Gate 0.5에 worktree 자동화를 통합하여, 멀티 세션(Warp 8개+) 워크플로우에서 사용자가 `claude`만 실행하면 worktree 생명주기가 자동 관리되게 한다.

**Architecture:** `_infra/scripts/worktree.sh`가 create/list/merge/clean을 담당하고, Claude는 Gate 0.5 절차에 따라 이를 호출한다. `_infra/cc/wd.sh`는 사용자가 Warp 탭에서 직접 실행하는 대시보드. 기존 인프라(session_logger, notify, digest)는 변경 없음.

**Tech Stack:** Bash, Git, jq

**Design doc:** `docs/plans/2026-02-27-worktree-orchestration-design.md`

---

### Task 1: worktree.sh — create 서브커맨드

**Files:**
- Create: `_infra/scripts/worktree.sh`

**Step 1: 스크립트 골격 + create 구현**

```bash
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
  list)   shift; cmd_list "$@" ;;
  merge)  shift; cmd_merge "$@" ;;
  clean)  shift; cmd_clean "$@" ;;
  *)
    echo "Usage: worktree.sh {create|list|merge|clean} ..."
    exit 1
    ;;
esac
```

**Step 2: 실행 권한 부여 + 테스트**

Run: `chmod +x _infra/scripts/worktree.sh && _infra/scripts/worktree.sh create test-task "테스트용"`
Expected: worktree 생성 성공, `.claude/worktrees/test-task/` 존재, `.session-meta.json` 존재

**Step 3: 테스트 worktree 정리**

Run: `git worktree remove .claude/worktrees/test-task && git branch -D wt/test-task`

**Step 4: Commit**

```bash
git add _infra/scripts/worktree.sh
git commit -m "feat: add worktree.sh with create subcommand"
```

---

### Task 2: worktree.sh — list 서브커맨드

**Files:**
- Modify: `_infra/scripts/worktree.sh`

**Step 1: cmd_list 함수 구현**

`cmd_create` 함수 뒤에 추가:

```bash
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

  # Header
  printf "%-16s %-14s %6s %10s  %-8s  %s\n" "Name" "Branch" "Files" "+/-" "Status" "Description"
  printf "%-16s %-14s %6s %10s  %-8s  %s\n" "────────────────" "──────────────" "──────" "──────────" "────────" "───────────"

  local total_add=0 total_del=0 active=0 count=0

  for wt_path in "${wt_dirs[@]}"; do
    local name
    name=$(basename "$wt_path")
    local branch
    branch=$(git -C "$wt_path" branch --show-current 2>/dev/null || echo "?")
    local stat
    stat=$(git -C "$wt_path" diff --stat HEAD 2>/dev/null | tail -1)
    local files=0 add=0 del=0
    if [ -n "$stat" ]; then
      files=$(echo "$stat" | grep -oE '[0-9]+ file' | grep -oE '[0-9]+' || echo 0)
      add=$(echo "$stat" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo 0)
      del=$(echo "$stat" | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo 0)
    fi

    local status="○ clean"
    if [ "$files" -gt 0 ] 2>/dev/null; then
      status="● active"
      active=$((active + 1))
    fi

    local desc=""
    if [ -f "$wt_path/.session-meta.json" ]; then
      desc=$(jq -r '.description // ""' "$wt_path/.session-meta.json" 2>/dev/null)
    fi

    printf "%-16s %-14s %6s %+5d/-%d  %-8s  %s\n" \
      "$name" "$branch" "$files" "${add:-0}" "${del:-0}" "$status" "$desc"

    total_add=$((total_add + ${add:-0}))
    total_del=$((total_del + ${del:-0}))
    count=$((count + 1))
  done

  echo ""
  echo "Active: $active/$count  |  Total: +$total_add/-$total_del"
}
```

**Step 2: 테스트**

Run: `_infra/scripts/worktree.sh create list-test "리스트 테스트" && _infra/scripts/worktree.sh list`
Expected: 테이블 형태로 `list-test` 워크트리 표시

**Step 3: 테스트 worktree 정리 + Commit**

```bash
git worktree remove .claude/worktrees/list-test && git branch -D wt/list-test
git add _infra/scripts/worktree.sh
git commit -m "feat: add list subcommand to worktree.sh"
```

---

### Task 3: worktree.sh — merge 서브커맨드

**Files:**
- Modify: `_infra/scripts/worktree.sh`

**Step 1: cmd_merge 함수 구현**

`cmd_list` 함수 뒤에 추가:

```bash
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

    # Cleanup
    git -C "$REPO_ROOT" worktree remove "$wt_path"
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
```

**Step 2: 테스트 (dry-run)**

Run:
```bash
_infra/scripts/worktree.sh create merge-test "머지 테스트"
echo "test" > .claude/worktrees/merge-test/test-file.txt
git -C .claude/worktrees/merge-test add test-file.txt
git -C .claude/worktrees/merge-test commit -m "test: merge test file"
_infra/scripts/worktree.sh merge merge-test --dry-run
```
Expected: dry-run 결과로 커밋 1개와 파일 1개 표시

**Step 3: 실제 merge 테스트**

Run: `_infra/scripts/worktree.sh merge merge-test`
Expected: backup tag 생성, merge 성공, worktree + branch 정리 완료

**Step 4: 테스트 파일 되돌리기 + Commit**

```bash
git revert HEAD --no-edit   # merge commit 되돌리기
git tag -d $(git tag -l 'backup/wt-merge-test-*')
git add _infra/scripts/worktree.sh
git commit -m "feat: add merge subcommand to worktree.sh"
```

---

### Task 4: worktree.sh — clean 서브커맨드

**Files:**
- Modify: `_infra/scripts/worktree.sh`

**Step 1: cmd_clean 함수 구현**

`cmd_merge` 함수 뒤에 추가:

```bash
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
```

**Step 2: 테스트**

Run:
```bash
_infra/scripts/worktree.sh create clean-test "정리 테스트"
_infra/scripts/worktree.sh clean clean-test
```
Expected: worktree + branch 삭제 성공

**Step 3: Commit**

```bash
git add _infra/scripts/worktree.sh
git commit -m "feat: add clean subcommand to worktree.sh"
```

---

### Task 5: wd.sh — 대시보드

**Files:**
- Create: `_infra/cc/wd.sh`

**Step 1: wd.sh 구현**

```bash
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
  watch -n 5 -t "$WORKTREE_SH list"
else
  while true; do
    clear
    echo "worktree dashboard  (refresh: 5s, Ctrl+C to exit)"
    echo ""
    "$WORKTREE_SH" list
    sleep 5
  done
fi
```

**Step 2: 실행 권한 + 테스트**

Run: `chmod +x _infra/cc/wd.sh && _infra/cc/wd.sh --once`
Expected: "No active worktrees." 또는 현재 worktree 테이블 출력

**Step 3: Commit**

```bash
git add _infra/cc/wd.sh
git commit -m "feat: add wd.sh dashboard for worktree monitoring"
```

---

### Task 6: Gate 0.5 규칙 강화

**Files:**
- Modify: `.claude/rules/superpowers-workflow-gates.md`

**Step 1: Gate 0.5 섹션 교체**

현재 Gate 0.5 (line 48-69)를 아래로 교체:

```markdown
## Gate 0.5: Worktree Isolation for Concurrent Sessions

Implementation 작업시 worktree로 격리한다. Claude가 직접 worktree를 생성/관리한다.

### Opening (작업 시작시)

**The rule:**
- Implementation 작업을 시작하면 `worktree.sh create <name> "description"`을 실행한다
- `<name>`은 태스크를 2-3단어로 요약 (예: `feat-auth`, `fix-login-bug`, `refactor-api`)
- 생성된 worktree 경로로 이동하여 작업한다
- 이미 worktree 안에 있으면 이 단계를 건너뛴다

**Script:** `"$CLAUDE_PROJECT_DIR"/_infra/scripts/worktree.sh create <name> "description"`

**When worktree is REQUIRED:**
- Any implementation task (code changes + commits)
- 사용자가 멀티 세션을 돌리는 것으로 알려진 경우

**When worktree is OPTIONAL:**
- Read-only exploration / research
- Single quick fix the user wants on current branch

### Closing (작업 완료시, Gate 3 이후)

Gate 3(Fresh-Eyes Review)를 통과한 뒤:
1. `worktree.sh merge <name> --dry-run`으로 사전 확인
2. 사용자에게 merge 확인 요청
3. 승인시 `worktree.sh merge <name>` 실행
4. conflict 발생시 사용자에게 수동 해결 안내

**Script:** `"$CLAUDE_PROJECT_DIR"/_infra/scripts/worktree.sh merge <name>`

### Dashboard

사용자가 별도 Warp 탭에서 `wd`를 실행하여 모든 worktree 상태를 모니터링할 수 있다.
스크립트 위치: `_infra/cc/wd.sh`
설치 후 `PATH`에 추가하거나 alias 설정: `alias wd='path/to/_infra/cc/wd.sh'`
```

**Step 2: Gate 1 섹션에 태스크별 Ralph Loop 제안 추가**

Gate 1(Prefer Subagent-Driven Development) 섹션 끝에 다음을 추가:

```markdown
### 태스크별 Ralph Loop 제안

subagent-driven-development 실행 중, 각 태스크 실행 직전에 다음 3가지를 평가한다:

1. ✅ 자동 검증 가능한 완료 조건이 있는가? (테스트 통과, lint 0 에러, 빌드 성공, 커버리지 수치 등)
2. ✅ 반복 개선 패턴인가? (구현 → 테스트 → 수정 사이클)
3. ✅ 20분+ 소요 예상인가?

**3개 모두 충족시 제안:**
```
💡 Task N "[태스크명]"은 [완료 조건]이 명확합니다.
   Ralph Loop(/ralph-loop)로 전환하면 자율 반복으로 효율적일 수 있습니다.
   전환할까요?
```

**규칙:**
- 제안만 하고 강제하지 않는다
- 사용자 승인시 → 해당 태스크만 /ralph-loop으로 실행
- 사용자 거부시 → 일반 subagent로 진행
- 조건 미충족시 → 제안 없이 subagent 진행
- Ralph 완료 후 다음 태스크부터 다시 subagent-driven으로 복귀
```

**Step 3: Gate 4a 테이블에 closing 추가**

Gate 4a의 transition 테이블(line 168-177)에 추가:

```markdown
| All tasks complete → Finishing branch | Gate 3 (Fresh-Eyes Final Review) |
| Fresh-Eyes Review passed → Merge worktree | Gate 0.5 Closing (Merge & Clean) |
```

**Step 3: Quick Reference 업데이트**

Quick Reference(line 196-217)를 업데이트:

```
[Task received]
    ↓
══ GATE 0: Brainstorming first? (building/creating/modifying) ══
    ↓
══ GATE 0.5 OPENING: Worktree Isolation (worktree.sh create) ══
    ↓
brainstorming
    ↓
writing-plans
    ↓
══ GATE 2: Plan Review (3-Example Rule) ══
    ↓
subagent-driven-development (Gate 1)
  ├─ Task 1 → 💡 Ralph 평가 → subagent or ralph-loop → ✓
  ├─ Task 2 → 💡 Ralph 평가 → subagent or ralph-loop → ✓
  └─ Task N → 💡 Ralph 평가 → subagent or ralph-loop → ✓
    ↓
══ GATE 3: Fresh-Eyes Final Review (full diff) ══
    ↓
══ GATE 0.5 CLOSING: Merge & Clean (worktree.sh merge) ══
```

**Step 4: Commit**

```bash
git add .claude/rules/superpowers-workflow-gates.md
git commit -m "feat: enhance Gate 0.5 with worktree automation + Ralph Loop suggestion"
```

---

### Task 7: Makefile에 wd 설치 안내 추가

**Files:**
- Modify: `Makefile`

**Step 1: install-cc 타겟에 wd 안내 추가**

install-cc 타겟의 마지막 echo 블록 뒤에 추가:

```makefile
	@echo ""
	@echo "Dashboard:"
	@echo "  alias wd='$(REPO_DIR)/_infra/cc/wd.sh'"
	@echo "  (add to ~/.zshrc for persistent access)"
```

**Step 2: Commit**

```bash
git add Makefile
git commit -m "feat: add wd alias guidance to make install-cc"
```
