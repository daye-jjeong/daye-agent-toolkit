# Pre-Compact 상태 보존 훅 + /enforce 스킬 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** compact 후 세션 상태 자동 복구 + correction 반복 패턴을 훅으로 전환하는 제안 시스템 구축

**Architecture:** (1) PreCompact bash 훅이 plan/worktree 정보를 JSON으로 저장 → 규칙이 compact 후 복원 지시 (2) correction-protocol 규칙에 훅 전환 제안 트리거 추가 + /enforce 온디맨드 스킬로 전체 스캔

**Tech Stack:** bash (stdlib only), markdown

**Spec:** `docs/superpowers/specs/2026-03-24-compact-state-enforce-design.md`

---

## File Structure

| 파일 | 역할 | 신규/수정 |
|------|------|-----------|
| `_infra/cc/save-compact-state.sh` | PreCompact 훅: plan/worktree 상태를 JSON 저장 | 신규 |
| `cc/global-rules/rules/superpowers-workflow-gates.md` | compact 후 상태 파일 읽기 규칙 | 수정 (line 82) |
| `~/.claude/settings.json` | PreCompact 훅 등록 | 수정 (line 59-68) |
| `cc/correction-memory/rules/correction-protocol.md` | 3회 반복 시 훅 전환 제안 | 수정 (line 23 뒤) |
| `cc/enforce/SKILL.md` | /enforce 스킬 본문 | 신규 |
| `cc/enforce/.claude-skill` | 스킬 메타데이터 | 신규 |
| `CLAUDE.md` | 스킬 목록 테이블에 enforce 추가 | 수정 |

---

### Task 1: save-compact-state.sh 작성

**Files:**
- Create: `_infra/cc/save-compact-state.sh`

- [ ] **Step 1: 스크립트 작성**

```bash
#!/bin/bash
# PreCompact hook: 세션 진행 상태를 ~/.claude/compact-state.json에 저장
# session_logger.py와 병렬 등록. 서로 독립적.

set -euo pipefail

STATE_FILE="$HOME/.claude/compact-state.json"
TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
BRANCH=$(git branch --show-current 2>/dev/null || echo "")

# plan 파일 탐색: (1) worktree 루트 → (2) main 레포 루트 → (3) null
find_plan() {
  local search_dir="$1"
  local plans_dir="$search_dir/docs/superpowers/plans"
  if [ -d "$plans_dir" ]; then
    # 최신 수정 시간 기준 1개
    local found
    found=$(ls -t "$plans_dir"/*.md 2>/dev/null | head -1)
    if [ -n "$found" ]; then
      echo "$found"
      return
    fi
  fi
}

PLAN_PATH=""
# (1) worktree 루트
if [ -n "$TOPLEVEL" ]; then
  PLAN_PATH=$(find_plan "$TOPLEVEL")
fi
# (2) main 레포 루트 (worktree의 commondir)
if [ -z "$PLAN_PATH" ] && [ -n "$TOPLEVEL" ]; then
  MAIN_ROOT=$(git -C "$TOPLEVEL" rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's|/.git$||')
  if [ -n "$MAIN_ROOT" ] && [ "$MAIN_ROOT" != "$TOPLEVEL" ]; then
    PLAN_PATH=$(find_plan "$MAIN_ROOT")
  fi
fi

# current_task: plan 파일 내 체크박스 카운트
CURRENT_TASK="null"
if [ -n "$PLAN_PATH" ]; then
  DONE=$(grep -cE '^\s*- \[x\]|^\s*- \[X\]|^\s*~~.*- \[' "$PLAN_PATH" 2>/dev/null || echo 0)
  TODO=$(grep -E '^\s*- \[ \]' "$PLAN_PATH" 2>/dev/null | grep -cvE '^\s*~~' || echo 0)
  TOTAL=$((DONE + TODO))
  if [ "$TOTAL" -gt 0 ]; then
    CURRENT_TASK="\"$DONE/$TOTAL\""
  fi
fi

# JSON 출력
SAVED_AT=$(date -u +%Y-%m-%dT%H:%M:%S)

# plan_path는 절대경로로 저장 (worktree/main 간 경로가 다를 수 있으므로)
PLAN_JSON="null"
if [ -n "$PLAN_PATH" ]; then
  PLAN_JSON="\"$PLAN_PATH\""
fi

WORKTREE_JSON="null"
if [ -n "$TOPLEVEL" ]; then
  WORKTREE_JSON="\"$TOPLEVEL\""
fi

BRANCH_JSON="null"
if [ -n "$BRANCH" ]; then
  BRANCH_JSON="\"$BRANCH\""
fi

cat > "$STATE_FILE" <<EOF
{
  "saved_at": "$SAVED_AT",
  "plan_path": $PLAN_JSON,
  "current_task": $CURRENT_TASK,
  "worktree_path": $WORKTREE_JSON,
  "branch": $BRANCH_JSON
}
EOF

exit 0
```

- [ ] **Step 2: 실행 권한 부여**

Run: `chmod +x _infra/cc/save-compact-state.sh`

- [ ] **Step 3: 수동 테스트 — 정상 케이스**

Run: `bash _infra/cc/save-compact-state.sh && cat ~/.claude/compact-state.json`
Expected: JSON 출력에 saved_at, plan_path, worktree_path, branch 포함

- [ ] **Step 4: 수동 테스트 — plan 없는 디렉토리**

Run: `cd /tmp && bash /Users/dayejeong/git_workplace/daye-agent-toolkit/_infra/cc/save-compact-state.sh && cat ~/.claude/compact-state.json`
Expected: plan_path, current_task가 null

- [ ] **Step 5: 커밋**

```bash
git add _infra/cc/save-compact-state.sh
git commit -m "feat: add pre-compact state preservation hook"
```

---

### Task 2: settings.json에 PreCompact 훅 등록

**Files:**
- Modify: `~/.claude/settings.json:59-68`

- [ ] **Step 1: 기존 PreCompact 배열에 새 훅 추가**

현재 PreCompact 구조:
```json
"PreCompact": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python3 /Users/dayejeong/git_workplace/daye-agent-toolkit/cc/work-digest/scripts/session_logger.py"
      }
    ]
  }
]
```

변경 후 (하나의 hooks 배열에 두 커맨드 병합):
```json
"PreCompact": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python3 /Users/dayejeong/git_workplace/daye-agent-toolkit/cc/work-digest/scripts/session_logger.py"
      },
      {
        "type": "command",
        "command": "/Users/dayejeong/git_workplace/daye-agent-toolkit/_infra/cc/save-compact-state.sh"
      }
    ]
  }
]
```

- [ ] **Step 2: JSON 유효성 검증**

Run: `python3 -c "import json; json.load(open('$HOME/.claude/settings.json')); print('valid')"`
Expected: `valid`

- [ ] **Step 3: 커밋 (settings.json은 git 밖이므로 스킵)**

settings.json은 `~/.claude/`에 있어 git-tracked가 아님. 커밋 불필요.

---

### Task 3: superpowers-workflow-gates.md에 compact 복원 규칙 추가

**Files:**
- Modify: `cc/global-rules/rules/superpowers-workflow-gates.md:82`

- [ ] **Step 1: 기존 compact 규칙을 구체적 행동 지시로 교체**

현재 (line 82):
```
- compact 후 plan 다시 읽고 현재 단계 재확인
```

변경 후:
```
- compact 직후: `~/.claude/compact-state.json`을 Read하라. 존재하면 plan_path의 plan을 열고 current_task 위치부터 이어서 진행하라. 읽은 후 파일을 삭제하라. `saved_at`가 24시간 이상 경과했으면 stale — 복원 없이 삭제만 하라. 파일이 없으면 무시.
```

- [ ] **Step 2: 커밋**

```bash
git add cc/global-rules/rules/superpowers-workflow-gates.md
git commit -m "feat: add concrete compact state recovery rule"
```

---

### Task 4: correction-protocol.md에 훅 전환 제안 트리거 추가

**Files:**
- Modify: `cc/correction-memory/rules/correction-protocol.md:23` (보고 항목 뒤)

- [ ] **Step 1: 저장 절차 5번 뒤에 6번 항목 추가**

현재 (line 23):
```
5. **보고** — `Correction saved: Rule: "..." | Topic: ... | Scope: ...`
```

변경 후:
```
5. **보고** — `Correction saved: Rule: "..." | Topic: ... | Scope: ...`
6. **훅 전환 제안** — 같은 토픽의 Layer 2 register(`corrections/{topic}.md`)에 `- [YYYY-MM-DD]` 엔트리가 3개 이상이면, 사용자에게 제안: "이 토픽({topic})에서 교정이 {N}회 반복됨. `/enforce`로 훅 전환을 검토하시겠습니까?"
```

- [ ] **Step 2: 커밋**

```bash
git add cc/correction-memory/rules/correction-protocol.md
git commit -m "feat: add hook enforcement suggestion trigger to correction protocol"
```

---

### Task 5: /enforce 스킬 생성

**Files:**
- Create: `cc/enforce/SKILL.md`
- Create: `cc/enforce/.claude-skill`

- [ ] **Step 1: .claude-skill 메타데이터 작성**

```json
{
  "name": "enforce",
  "version": "1.0.0",
  "description": "반복 교정을 훅으로 전환 — correction 로그 스캔 + 훅 후보 제안",
  "entrypoint": "SKILL.md"
}
```

- [ ] **Step 2: SKILL.md 작성**

```markdown
---
name: enforce
description: 반복 교정 패턴을 훅으로 전환 제안. correction 로그를 스캔하여 3회+ 반복 위반을 감지하고, 훅 코드 초안 + settings.json 등록 방법을 제시한다. "enforce", "훅으로 전환", "규칙 강제", "반복 교정 확인" 등의 요청에 사용.
---

# Enforce — 반복 교정 → 훅 전환

correction-memory 로그를 스캔하여 반복되는 위반 패턴을 찾고, 훅으로 자동 강제할 수 있는 후보를 제안한다.

## 실행 절차

### 1. 수집

다음 3개 소스를 모두 스캔:

- **Layer 1 (Rules):** `~/.claude/rules/correction-*.md` — 프로젝트별 `.claude/rules/correction-*.md`도 포함
- **Layer 2 (Register):** auto memory `corrections/*.md` (토픽별 교정 이력)
- **Layer 3 (Log):** auto memory `corrections/log/*.md` (날짜별 타임라인)

### 2. 감지

토픽별로 Layer 2 엔트리 수를 카운트한다. `- [YYYY-MM-DD]` 형식 라인 1개 = 1회.

**훅 전환 후보 기준:** 같은 토픽 3회 이상.

### 3. 분류

각 후보를 위반 유형별로 분류하고 적합한 훅 이벤트를 매핑:

| 위반 유형 | 훅 이벤트 | 매처 | 예시 |
|-----------|-----------|------|------|
| 특정 파일 수정 금지 | PreToolUse | Edit\|Write | `.env` 직접 수정 |
| 코드 패턴 사용 금지 | PostToolUse | — | `console.log` 잔존, transition-all |
| 절차 누락 (테스트/검증) | Stop | — | 테스트 미실행, tsc 미실행 |
| 명령어 사용 금지 | PreToolUse | Bash | `git push --force` |
| 분류 불가 | — | — | 규칙으로 유지 (훅 부적합) |

**분류 불가한 경우:** 모든 교정이 훅으로 전환 가능한 것은 아니다. "코드 스타일 선호", "설명 방식" 등 주관적 교정은 규칙으로 유지하고 훅 후보에서 제외.

### 4. 제안

각 훅 후보에 대해 다음을 출력:

```
## 후보 N: {토픽} ({위반횟수}회)

### 교정 이력
- [날짜] {교정 내용 요약}
- ...

### 제안 훅
- 이벤트: {PreToolUse|PostToolUse|Stop}
- 매처: {패턴}
- 동작: {차단|경고}

### 훅 코드 초안
\`\`\`bash
#!/bin/bash
# {설명}
{코드}
\`\`\`

### 설치 방법
1. 파일 저장: `_infra/cc/{slug}.sh`
2. `chmod +x _infra/cc/{slug}.sh`
3. `~/.claude/settings.json`의 `hooks.{이벤트}` 배열에 추가
```

### 5. 설치

**사용자 승인 후에만 진행.** 승인 시:
1. 훅 스크립트를 `_infra/cc/`에 Write
2. `chmod +x` 실행
3. `~/.claude/settings.json`의 해당 이벤트 hooks 배열에 Edit으로 등록
4. 해당 교정의 Layer 1 rule 파일에 "훅으로 전환됨" 메모 추가

## 주의사항

- 훅 코드는 LLM이 직접 작성한다. 별도 코드 생성 스크립트 없음.
- 훅은 bash, stdlib만 사용. 외부 패키지 금지.
- 기존 훅 패턴 참고: `_infra/cc/worktree-guard.sh`, `_infra/cc/merge-gate.sh`
- 차단 훅은 `exit 2`, 통과는 `exit 0`.
```

- [ ] **Step 3: 커밋**

```bash
git add cc/enforce/SKILL.md cc/enforce/.claude-skill
git commit -m "feat: add /enforce skill for correction-to-hook conversion"
```

---

### Task 6: CLAUDE.md 스킬 목록 업데이트

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: cc/ 디렉토리 스킬 테이블에 enforce 추가**

현재 테이블 (5개):
```
| correction-memory | 스킬 | 교정 기억 — 실수 반복 방지 3계층 메모리 |
| global-rules | 규칙 | 글로벌 규칙 묶음 — 세션 자동 로드 (SKILL.md 없음) |
| reddit-fetch | 스킬 | Reddit 포스트/댓글 조회 + 검색 |
| work-digest | 스킬 | 일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림 |
| youtube-fetch | 스킬 | YouTube 메타데이터 + 자막 추출 |
```

추가 (correction-memory와 global-rules 사이, 알파벳순):
```
| enforce | 스킬 | 반복 교정 → 훅 전환 제안 — correction 로그 스캔 + 훅 코드 초안 |
```

헤더의 카운트도 `(4개 스킬 + 1개 규칙묶음)` → `(5개 스킬 + 1개 규칙묶음)` 수정.

- [ ] **Step 2: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: add enforce skill to CLAUDE.md skill list"
```

---

### Task 7: make install-cc 동작 확인

**Files:** 없음 (검증만)

- [ ] **Step 1: make install-cc 실행**

Run: `make install-cc`
Expected: enforce 스킬이 `~/.claude/skills/enforce`에 심링크됨

- [ ] **Step 2: 심링크 확인**

Run: `ls -la ~/.claude/skills/ | grep enforce`
Expected: `enforce -> /Users/dayejeong/git_workplace/daye-agent-toolkit/cc/enforce`

- [ ] **Step 3: 전체 설정 검증**

Run: `python3 -c "import json; json.load(open('$HOME/.claude/settings.json')); print('settings.json valid')"` && `cat ~/.claude/compact-state.json 2>/dev/null || echo "no state file (expected)"`

