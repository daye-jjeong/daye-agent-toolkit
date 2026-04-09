# CC 플러그인 마이그레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OpenClaw을 완전히 제거하고, `cc/` + `shared/` 이원 구조를 도메인별 4개 CC 플러그인으로 재편한다.

**Architecture:** 레포 최상위에 `plugins/` 디렉토리를 만들고, 각 플러그인(`life-management`, `finance`, `dev-tools`, `media-fetch`)에 `.claude-plugin/plugin.json` + `skills/`를 배치한다. 규칙은 `rules/`로 분리, MCP 서버는 `mcp/`로 분리, 훅은 `dev-tools/hooks/`에 포함한다. 로컬 마켓플레이스로 등록하여 CC가 자동 발견한다.

**Tech Stack:** Claude Code Plugin format, Makefile, shell scripts, python3 (stdlib only)

**Spec:** `docs/superpowers/specs/2026-04-07-cc-plugin-migration-design.md`

---

### Task 1: 기존 심링크 정리 + marketplace.json 업데이트

기존 `make clean`으로 심링크를 제거하고, `.claude-plugin/marketplace.json`을 새 구조에 맞게 업데이트한다.

**Files:**
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: 기존 CC 심링크 제거**

```bash
make clean
```

Expected: `~/.claude/skills/`와 `~/.claude/rules/`의 심링크가 제거됨.

- [ ] **Step 2: marketplace.json 업데이트**

`.claude-plugin/marketplace.json`을 수정하여 4개 플러그인을 선언:

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "daye-agent-toolkit",
  "version": "2.0.0",
  "description": "Daye's personal agent toolkit - CC plugins for life management, finance, dev tools, media",
  "owner": {
    "name": "Daye Jeong"
  },
  "plugins": [
    {
      "name": "life-management",
      "description": "건강/생활/코칭 관련 스킬 모음 — health-tracker, life-coach, pantry-manager, saju-manse",
      "source": "./plugins/life-management",
      "category": "lifestyle"
    },
    {
      "name": "finance",
      "description": "금융/소비 관련 스킬 모음 — spending-manager, investment-manager, banksalad-import",
      "source": "./plugins/finance",
      "category": "finance"
    },
    {
      "name": "dev-tools",
      "description": "개발 워크플로우 스킬 + 훅 — codex-cli, gemini-cli, correction-memory, enforce, work-digest, self-profile, dashboard-content-design",
      "source": "./plugins/dev-tools",
      "category": "development"
    },
    {
      "name": "media-fetch",
      "description": "외부 콘텐츠 수집 — reddit-fetch, youtube-fetch, news-brief",
      "source": "./plugins/media-fetch",
      "category": "media"
    }
  ]
}
```

- [ ] **Step 3: 검증**

```bash
python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); assert len(d['plugins'])==4; print('OK:', [p['name'] for p in d['plugins']])"
```

Expected: `OK: ['life-management', 'finance', 'dev-tools', 'media-fetch']`

- [ ] **Step 4: 커밋**

```bash
git add .claude-plugin/marketplace.json
git commit -m "chore: marketplace.json에 4개 플러그인 선언"
```

---

### Task 2: 플러그인 골격 생성

4개 플러그인의 디렉토리 구조와 `plugin.json`을 생성한다.

**Files:**
- Create: `plugins/life-management/.claude-plugin/plugin.json`
- Create: `plugins/finance/.claude-plugin/plugin.json`
- Create: `plugins/dev-tools/.claude-plugin/plugin.json`
- Create: `plugins/media-fetch/.claude-plugin/plugin.json`

- [ ] **Step 1: 디렉토리 생성**

```bash
mkdir -p plugins/life-management/{.claude-plugin,skills}
mkdir -p plugins/finance/{.claude-plugin,skills}
mkdir -p plugins/dev-tools/{.claude-plugin,skills,hooks}
mkdir -p plugins/media-fetch/{.claude-plugin,skills}
```

- [ ] **Step 2: plugin.json 생성 — life-management**

`plugins/life-management/.claude-plugin/plugin.json`:
```json
{
  "name": "life-management",
  "version": "1.0.0",
  "description": "건강/생활/코칭 관련 스킬 모음 — health-tracker, life-coach, pantry-manager, saju-manse"
}
```

- [ ] **Step 3: plugin.json 생성 — finance**

`plugins/finance/.claude-plugin/plugin.json`:
```json
{
  "name": "finance",
  "version": "1.0.0",
  "description": "금융/소비 관련 스킬 모음 — spending-manager, investment-manager, banksalad-import"
}
```

- [ ] **Step 4: plugin.json 생성 — dev-tools**

`plugins/dev-tools/.claude-plugin/plugin.json`:
```json
{
  "name": "dev-tools",
  "version": "1.0.0",
  "description": "개발 워크플로우 스킬 + 훅 — codex-cli, gemini-cli, correction-memory, enforce, work-digest, self-profile, dashboard-content-design"
}
```

- [ ] **Step 5: plugin.json 생성 — media-fetch**

`plugins/media-fetch/.claude-plugin/plugin.json`:
```json
{
  "name": "media-fetch",
  "version": "1.0.0",
  "description": "외부 콘텐츠 수집 — reddit-fetch, youtube-fetch, news-brief"
}
```

- [ ] **Step 6: 구조 검증**

```bash
find plugins -name 'plugin.json' | sort
```

Expected:
```
plugins/dev-tools/.claude-plugin/plugin.json
plugins/finance/.claude-plugin/plugin.json
plugins/life-management/.claude-plugin/plugin.json
plugins/media-fetch/.claude-plugin/plugin.json
```

- [ ] **Step 7: 커밋**

```bash
git add plugins/
git commit -m "chore: 4개 플러그인 골격 생성 (plugin.json + 빈 skills/)"
```

---

### Task 3: life-management 스킬 이동

`shared/`에서 life-management 플러그인으로 4개 스킬을 이동한다.

**Files:**
- Move: `shared/health-tracker/` → `plugins/life-management/skills/health-tracker/`
- Move: `shared/life-coach/` → `plugins/life-management/skills/life-coach/`
- Move: `shared/pantry-manager/` → `plugins/life-management/skills/pantry-manager/`
- Move: `shared/saju-manse/` → `plugins/life-management/skills/saju-manse/`

- [ ] **Step 1: git mv로 스킬 이동**

```bash
git mv shared/health-tracker plugins/life-management/skills/health-tracker
git mv shared/life-coach plugins/life-management/skills/life-coach
git mv shared/pantry-manager plugins/life-management/skills/pantry-manager
git mv shared/saju-manse plugins/life-management/skills/saju-manse
```

- [ ] **Step 2: .claude-skill 파일 삭제**

```bash
find plugins/life-management -name '.claude-skill' -delete
```

- [ ] **Step 3: SKILL.md에서 OpenClaw 메타데이터 제거**

각 SKILL.md의 frontmatter에서 `metadata:` 라인을 제거한다. 해당 스킬:
- `health-tracker/SKILL.md` — `metadata: {"openclaw":{"requires":{"bins":["python3"]}}}` 제거
- `life-coach/SKILL.md` — `metadata: {"openclaw":{"requires":{"bins":["python3"]}}}` 제거
- 본문에서 "CC/OpenClaw" → "CC", "OpenClaw" 관련 언급 제거

`pantry-manager`, `saju-manse`도 `metadata:` 라인이 있으면 제거.

- [ ] **Step 4: 검증**

```bash
find plugins/life-management/skills -name 'SKILL.md' | sort
```

Expected:
```
plugins/life-management/skills/health-tracker/SKILL.md
plugins/life-management/skills/life-coach/SKILL.md
plugins/life-management/skills/pantry-manager/SKILL.md
plugins/life-management/skills/saju-manse/SKILL.md
```

```bash
grep -r 'openclaw' plugins/life-management/ || echo "No openclaw references"
```

Expected: `No openclaw references`

- [ ] **Step 5: 커밋**

```bash
git add -A plugins/life-management/ shared/
git commit -m "feat: life-management 플러그인으로 4개 스킬 이동"
```

---

### Task 4: finance 스킬 이동

**Files:**
- Move: `shared/spending-manager/` → `plugins/finance/skills/spending-manager/`
- Move: `shared/investment-manager/` → `plugins/finance/skills/investment-manager/`
- Move: `shared/banksalad-import/` → `plugins/finance/skills/banksalad-import/`

- [ ] **Step 1: git mv로 스킬 이동**

```bash
git mv shared/spending-manager plugins/finance/skills/spending-manager
git mv shared/investment-manager plugins/finance/skills/investment-manager
git mv shared/banksalad-import plugins/finance/skills/banksalad-import
```

- [ ] **Step 2: .claude-skill 삭제 + OpenClaw 메타데이터 제거**

```bash
find plugins/finance -name '.claude-skill' -delete
```

각 SKILL.md의 frontmatter에서 `metadata:` 라인 제거.

- [ ] **Step 3: 검증**

```bash
find plugins/finance/skills -name 'SKILL.md' | sort
grep -r 'openclaw' plugins/finance/ || echo "No openclaw references"
```

Expected: 3개 SKILL.md, openclaw 참조 없음.

- [ ] **Step 4: 커밋**

```bash
git add -A plugins/finance/ shared/
git commit -m "feat: finance 플러그인으로 3개 스킬 이동"
```

---

### Task 5: dev-tools 스킬 이동

**Files:**
- Move: `shared/codex-cli/` → `plugins/dev-tools/skills/codex-cli/`
- Move: `shared/gemini-cli/` → `plugins/dev-tools/skills/gemini-cli/`
- Move: `cc/correction-memory/` → `plugins/dev-tools/skills/correction-memory/`
- Move: `cc/enforce/` → `plugins/dev-tools/skills/enforce/`
- Move: `cc/work-digest/` → `plugins/dev-tools/skills/work-digest/`
- Move: `shared/self-profile/` → `plugins/dev-tools/skills/self-profile/`
- Move: `cc/dashboard-content-design/` → `plugins/dev-tools/skills/dashboard-content-design/`
- Move: `shared/stop-slop-kr/` → `plugins/dev-tools/skills/stop-slop-kr/` (퇴고 모드 포함, rules/는 Task 8에서 분리)

- [ ] **Step 1: git mv로 스킬 이동**

```bash
git mv shared/codex-cli plugins/dev-tools/skills/codex-cli
git mv shared/gemini-cli plugins/dev-tools/skills/gemini-cli
git mv cc/correction-memory plugins/dev-tools/skills/correction-memory
git mv cc/enforce plugins/dev-tools/skills/enforce
git mv cc/work-digest plugins/dev-tools/skills/work-digest
git mv shared/self-profile plugins/dev-tools/skills/self-profile
git mv cc/dashboard-content-design plugins/dev-tools/skills/dashboard-content-design
git mv shared/stop-slop-kr plugins/dev-tools/skills/stop-slop-kr
```

- [ ] **Step 2: .claude-skill 삭제 + OpenClaw 메타데이터 제거**

```bash
find plugins/dev-tools/skills -name '.claude-skill' -delete
```

각 SKILL.md의 frontmatter에서 `metadata:` 라인 제거. correction-memory의 `rules/` 디렉토리는 Task 8에서 별도 처리. stop-slop-kr의 `rules/`도 Task 8에서 분리.

- [ ] **Step 3: 검증**

```bash
find plugins/dev-tools/skills -name 'SKILL.md' | sort
grep -r 'openclaw' plugins/dev-tools/ || echo "No openclaw references"
```

Expected: 8개 SKILL.md, openclaw 참조 없음.

- [ ] **Step 4: 커밋**

```bash
git add -A plugins/dev-tools/skills/ shared/ cc/
git commit -m "feat: dev-tools 플러그인으로 8개 스킬 이동 (stop-slop-kr 퇴고 모드 포함)"
```

---

### Task 6: media-fetch 스킬 이동

**Files:**
- Move: `cc/reddit-fetch/` → `plugins/media-fetch/skills/reddit-fetch/`
- Move: `cc/youtube-fetch/` → `plugins/media-fetch/skills/youtube-fetch/`
- Move: `shared/news-brief/` → `plugins/media-fetch/skills/news-brief/`

- [ ] **Step 1: git mv로 스킬 이동**

```bash
git mv cc/reddit-fetch plugins/media-fetch/skills/reddit-fetch
git mv cc/youtube-fetch plugins/media-fetch/skills/youtube-fetch
git mv shared/news-brief plugins/media-fetch/skills/news-brief
```

- [ ] **Step 2: .claude-skill 삭제 + OpenClaw 메타데이터 제거**

```bash
find plugins/media-fetch -name '.claude-skill' -delete
```

각 SKILL.md의 frontmatter에서 `metadata:` 라인 제거.

- [ ] **Step 3: news-brief venv 정리**

`news-brief/venv/`는 git에 포함되어 있으면 제거. `.gitignore`에 추가.

```bash
ls plugins/media-fetch/skills/news-brief/venv/ 2>/dev/null && echo "venv exists - remove from git"
```

venv가 있으면:
```bash
git rm -r --cached plugins/media-fetch/skills/news-brief/venv/
echo "venv/" >> plugins/media-fetch/skills/news-brief/.gitignore
```

- [ ] **Step 4: 검증**

```bash
find plugins/media-fetch/skills -name 'SKILL.md' | sort
grep -r 'openclaw' plugins/media-fetch/ || echo "No openclaw references"
```

Expected: 3개 SKILL.md, openclaw 참조 없음.

- [ ] **Step 5: 커밋**

```bash
git add -A plugins/media-fetch/ shared/ cc/
git commit -m "feat: media-fetch 플러그인으로 3개 스킬 이동"
```

---

### Task 7: 훅 이동 + hooks.json 생성

`_infra/cc/`의 훅 스크립트를 `plugins/dev-tools/hooks/`로 이동하고, `hooks.json`을 생성하여 CC가 자동 등록하도록 한다. 글로벌 `settings.json`의 절대 경로 훅은 제거한다.

**Files:**
- Move: `_infra/cc/merge-gate.sh` → `plugins/dev-tools/hooks/merge-gate.sh`
- Move: `_infra/cc/worktree-guard.sh` → `plugins/dev-tools/hooks/worktree-guard.sh`
- Move: `_infra/cc/save-compact-state.sh` → `plugins/dev-tools/hooks/save-compact-state.sh`
- Create: `plugins/dev-tools/hooks/hooks.json`
- Modify: `~/.claude/settings.json` (hooks 섹션 제거)

- [ ] **Step 1: git mv로 훅 이동**

```bash
git mv _infra/cc/merge-gate.sh plugins/dev-tools/hooks/merge-gate.sh
git mv _infra/cc/worktree-guard.sh plugins/dev-tools/hooks/worktree-guard.sh
git mv _infra/cc/save-compact-state.sh plugins/dev-tools/hooks/save-compact-state.sh
```

남는 `_infra/cc/statusline.sh`는 확인 후 처리:
```bash
ls _infra/cc/
```

statusline.sh가 남아있으면 dev-tools/hooks/로 함께 이동.

- [ ] **Step 2: hooks.json 생성**

`plugins/dev-tools/hooks/hooks.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/worktree-guard.sh"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/merge-gate.sh"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/work-digest/scripts/session_logger.py"
          },
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/save-compact-state.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/work-digest/scripts/session_logger.py"
          }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/skills/work-digest/scripts/notify.sh permission"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 3: 글로벌 settings.json에서 기존 훅 제거**

`~/.claude/settings.json`의 `hooks` 섹션에서 `daye-agent-toolkit` 절대 경로를 사용하는 훅을 모두 제거한다. 플러그인 `hooks.json`이 대체한다.

```bash
python3 -c "
import json, os
p = os.path.expanduser('~/.claude/settings.json')
d = json.load(open(p))
if 'hooks' in d:
    del d['hooks']
    json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False)
    print('✓ hooks section removed from global settings.json')
else:
    print('no hooks to remove')
"
```

**주의:** 프로젝트 레벨 훅(`.claude/settings.json`의 `plan-review-gate.sh`)은 건드리지 않는다.

- [ ] **Step 4: 검증**

```bash
ls plugins/dev-tools/hooks/
python3 -c "import json; d=json.load(open('plugins/dev-tools/hooks/hooks.json')); print('Hook events:', list(d['hooks'].keys()))"
```

Expected: 파일 목록 + `Hook events: ['PreToolUse', 'PreCompact', 'SessionEnd', 'Notification']`

- [ ] **Step 5: 커밋**

```bash
git add -A plugins/dev-tools/hooks/ _infra/
git commit -m "chore: 훅을 dev-tools/hooks/로 이동 + hooks.json 선언"
```

---

### Task 8: 규칙 이동

3곳에 흩어진 규칙을 `rules/` 최상위로 모은다.

**Files:**
- Move: `cc/global-rules/rules/*.md` → `rules/global/`
- Move: `cc/correction-memory/rules/*.md` → `rules/correction/`  
  (주의: correction-memory 스킬 자체는 Task 5에서 이미 dev-tools로 이동. 여기서는 rules/ 서브디렉토리만 처리)
- Move: `shared/stop-slop-kr/rules/*.md` → `rules/tone/`

- [ ] **Step 1: rules 디렉토리 생성**

```bash
mkdir -p rules/{global,correction,tone}
```

- [ ] **Step 2: global rules 이동**

```bash
git mv cc/global-rules/rules/before-starting.md rules/global/
git mv cc/global-rules/rules/completion-and-commits.md rules/global/
git mv cc/global-rules/rules/long-running-backoff.md rules/global/
git mv cc/global-rules/rules/memory-lifecycle.md rules/global/
git mv cc/global-rules/rules/minimal-scope.md rules/global/
git mv cc/global-rules/rules/review-learning-loop.md rules/global/
git mv cc/global-rules/rules/review-multipass.md rules/global/
git mv cc/global-rules/rules/session-split.md rules/global/
git mv cc/global-rules/rules/superpowers-workflow-gates.md rules/global/
git mv cc/global-rules/rules/tdd-on-new-functions.md rules/global/
```

- [ ] **Step 3: correction rules 이동**

correction-memory의 rules/ 서브디렉토리는 Task 5에서 스킬과 함께 dev-tools로 이동했을 수 있다. 실제 위치 확인 후 이동:

```bash
# Task 5에서 이동된 경우
find plugins/dev-tools/skills/correction-memory -name '*.md' -path '*/rules/*'
```

있으면:
```bash
git mv plugins/dev-tools/skills/correction-memory/rules/correction-protocol.md rules/correction/
rmdir plugins/dev-tools/skills/correction-memory/rules/ 2>/dev/null
```

- [ ] **Step 4: tone rules 이동**

stop-slop-kr 스킬 본체는 Task 5에서 dev-tools로 이동 완료. rules/ 서브디렉토리만 분리:

```bash
# Task 5에서 이동된 위치에서
find plugins/dev-tools/skills/stop-slop-kr -name '*.md' -path '*/rules/*'
```

있으면:
```bash
git mv plugins/dev-tools/skills/stop-slop-kr/rules/tone-kr.md rules/tone/
rmdir plugins/dev-tools/skills/stop-slop-kr/rules/ 2>/dev/null
```

- [ ] **Step 5: 검증**

```bash
find rules -name '*.md' | sort
```

Expected: `rules/global/` 10개 + `rules/correction/` 1개 + `rules/tone/` 1개 = 12개.

- [ ] **Step 6: 커밋**

```bash
git add -A rules/ cc/ shared/ plugins/
git commit -m "chore: 규칙을 rules/ 최상위로 통합"
```

---

### Task 9: MCP 서버 분리

`shared/life-dashboard-mcp/`를 `mcp/life-dashboard/`로 이동한다.

**Files:**
- Move: `shared/life-dashboard-mcp/` → `mcp/life-dashboard/`

- [ ] **Step 1: git mv로 이동**

```bash
mkdir -p mcp
git mv shared/life-dashboard-mcp mcp/life-dashboard
```

- [ ] **Step 2: .claude-skill 삭제**

```bash
rm -f mcp/life-dashboard/.claude-skill
```

- [ ] **Step 3: SKILL.md 업데이트**

MCP 서버이므로 SKILL.md의 역할이 달라진다. frontmatter에서 `metadata:` 제거. 본문에서 OpenClaw 참조 제거.

- [ ] **Step 4: 다른 스킬의 경로 참조 업데이트**

life-coach, work-digest 등의 SKILL.md와 scripts에서 `life-dashboard-mcp` 경로를 참조하는 부분을 확인하고 업데이트:

```bash
grep -r 'life-dashboard-mcp' plugins/ --include='*.py' --include='*.md' --include='*.sh'
```

`{baseDir}/../../shared/life-dashboard-mcp` 같은 상대 경로를 새 경로로 업데이트한다. 패턴:
- work-digest scripts: `{baseDir}/../../shared/life-dashboard-mcp` → `{baseDir}/../../../mcp/life-dashboard`
- life-coach scripts: `{baseDir}/../../shared/life-dashboard-mcp` → `{baseDir}/../../../mcp/life-dashboard`

**주의:** 상대 경로가 복잡해진다. 각 스킬의 `{baseDir}` 기준으로 정확한 경로를 계산할 것. 경로가 너무 깊으면 절대 경로나 환경변수(`$TOOLKIT_DIR/mcp/life-dashboard`)를 고려.

- [ ] **Step 5: 검증**

```bash
ls mcp/life-dashboard/
grep -r 'shared/life-dashboard-mcp' plugins/ || echo "No stale references"
```

Expected: 파일 목록 확인 + stale 참조 없음.

- [ ] **Step 6: 커밋**

```bash
git add -A mcp/ shared/ plugins/
git commit -m "chore: life-dashboard MCP를 mcp/로 분리 + 경로 참조 업데이트"
```

---

### Task 10: Makefile 재작성

기존 Makefile을 플러그인 등록 + rules 심링크 중심으로 재작성한다.

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Makefile 재작성**

```makefile
# daye-agent-toolkit Makefile
# Usage:
#   make install       # 플러그인 등록 + rules 심링크 + MCP 등록
#   make clean         # 등록 해제 + 심링크 제거
#   make status        # 설치 상태 확인

REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RULES_DIR := $(HOME)/.claude/rules
SETTINGS := $(HOME)/.claude/settings.json
MARKETPLACE_NAME := daye-agent-toolkit
PLUGINS := life-management finance dev-tools media-fetch

.PHONY: install clean status help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: _register-marketplace _enable-plugins _symlink-rules ## Install plugins + rules
	@echo ""
	@echo "Done. Run 'make status' to verify."

_register-marketplace:
	@echo "=== Register local marketplace ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)) if os.path.exists(p) else {}; \
m = d.setdefault('extraKnownMarketplaces', {}); \
m['$(MARKETPLACE_NAME)'] = {'source': {'source': 'directory', 'path': '$(REPO_DIR)'}}; print('  path: $(REPO_DIR)'); \
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False); \
print('  ✓ $(MARKETPLACE_NAME) registered')"

_enable-plugins:
	@echo "=== Enable plugins ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)); \
ep = d.setdefault('enabledPlugins', {}); \
plugins = '$(PLUGINS)'.split(); \
for name in plugins: \
    key = f'{name}@$(MARKETPLACE_NAME)'; \
    ep[key] = True; \
    print(f'  ✓ {key}'); \
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False)"

_symlink-rules:
	@echo "=== Symlink rules ==="
	@mkdir -p $(RULES_DIR)
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; \
		elif [ -e "$$dest" ]; then echo "  ⚠ SKIPPED $$name (exists, not symlink)"; continue; \
		fi; \
		ln -s "$(REPO_DIR)/$$rule_file" "$$dest"; \
		echo "  ✓ $$name"; \
	done

clean: ## Remove plugins + rules
	@echo "=== Disable plugins ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)) if os.path.exists(p) else {}; \
ep = d.get('enabledPlugins', {}); \
plugins = '$(PLUGINS)'.split(); \
for name in plugins: \
    key = f'{name}@$(MARKETPLACE_NAME)'; \
    if key in ep: del ep[key]; print(f'  ✓ removed {key}'); \
m = d.get('extraKnownMarketplaces', {}); \
if '$(MARKETPLACE_NAME)' in m: del m['$(MARKETPLACE_NAME)']; print('  ✓ marketplace removed'); \
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False)"
	@echo ""
	@echo "=== Remove rules symlinks ==="
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; echo "  ✓ removed $$name"; fi; \
	done
	@echo ""
	@echo "Note: Plugin hooks are auto-deregistered when plugins are disabled."

status: ## Show installation status
	@echo "=== Marketplace ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)) if os.path.exists(p) else {}; \
m = d.get('extraKnownMarketplaces', {}); \
print('  ✓ registered' if '$(MARKETPLACE_NAME)' in m else '  ✗ not registered')"
	@echo ""
	@echo "=== Plugins ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)) if os.path.exists(p) else {}; \
ep = d.get('enabledPlugins', {}); \
plugins = '$(PLUGINS)'.split(); \
[print(f'  ✓ {n}' if ep.get(f'{n}@$(MARKETPLACE_NAME)') else f'  ✗ {n}') for n in plugins]"
	@echo ""
	@echo "=== Rules ==="
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  ✓ $$name"; \
		else echo "  ✗ $$name (not installed)"; fi; \
	done
```

- [ ] **Step 2: 검증**

```bash
make help
```

Expected: `install`, `clean`, `status` 타겟 표시.

- [ ] **Step 3: 커밋**

```bash
git add Makefile
git commit -m "chore: Makefile을 플러그인 등록 + rules 심링크로 재작성"
```

---

### Task 11: 레거시 삭제

이동 완료된 `cc/`, `shared/`, `_infra/`, `skills.json`을 삭제한다.

**Files:**
- Delete: `cc/` (남은 파일 확인 후)
- Delete: `shared/` (남은 파일 확인 후)
- Delete: `_infra/`
- Delete: `skills.json`

- [ ] **Step 1: 남은 파일 확인**

```bash
echo "=== cc/ ===" && ls -la cc/ 2>/dev/null
echo "=== shared/ ===" && ls -la shared/ 2>/dev/null
echo "=== _infra/ ===" && ls -la _infra/ 2>/dev/null
```

`cc/global-rules/`에 rules/ 외 파일이 있을 수 있다 (`hookify/` 디렉토리). 확인 후 처리:
- `cc/global-rules/hookify/` — 이미 hookify 플러그인으로 관리되므로 삭제
- `shared/stop-slop-kr/` — Task 5에서 dev-tools로 이동 완료. 빈 디렉토리만 남아있으면 삭제
- `shared/.claude/settings.local.json` — 더 이상 필요 없으므로 삭제

- [ ] **Step 2: 레거시 삭제**

```bash
git rm -r cc/
git rm -r shared/
git rm -r _infra/
git rm skills.json
```

- [ ] **Step 3: 검증**

```bash
ls -d cc shared _infra 2>&1 | grep -c "No such file"
```

Expected: 3 (모두 삭제됨)

```bash
find plugins -name 'SKILL.md' | wc -l
```

Expected: 18 (4+3+8+3 스킬)

- [ ] **Step 4: 커밋**

```bash
git add -A
git commit -m "chore: cc/, shared/, _infra/, skills.json 레거시 삭제"
```

---

### Task 12: CLAUDE.md 업데이트

새 디렉토리 구조와 워크플로우를 반영한다.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: CLAUDE.md 재작성**

핵심 변경점:
- 접근 방식: OpenClaw 행 삭제, CC 플러그인 전용으로
- 디렉토리 구조: `cc/`, `shared/` → `plugins/`, `rules/`, `mcp/`, `codex/`
- 스킬 분류: 플러그인별 테이블로 변경
- 설치: `make install-cc` → `make install`
- skills.json: 삭제됨 → marketplace.json으로 대체
- 스킬 포맷: `.claude-skill` 제거, `plugins/{plugin}/skills/{name}/SKILL.md`
- 규칙 시스템: `rules/` 최상위로 통합, 심링크 방식 동일
- 새 스킬 추가 절차: 플러그인 안에 스킬 디렉토리 생성

"OpenClaw", "openclaw", "shared/"에 대한 모든 참조를 제거/수정한다.

- [ ] **Step 2: 검증**

```bash
grep -i 'openclaw' CLAUDE.md || echo "No openclaw references"
grep 'shared/' CLAUDE.md || echo "No shared/ references"
grep 'install-cc' CLAUDE.md || echo "No install-cc references"
```

Expected: 모두 참조 없음.

- [ ] **Step 3: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md를 CC 플러그인 구조로 업데이트"
```

---

### Task 13: 설치 및 동작 검증

`make install`을 실행하고, CC에서 스킬이 정상 인식되는지 확인한다.

**Files:** (없음 — 검증만)

- [ ] **Step 1: make install 실행**

```bash
make install
```

Expected: marketplace 등록, 4개 플러그인 활성화, 12개 규칙 심링크 완료.

- [ ] **Step 2: make status 확인**

```bash
make status
```

Expected: 모든 항목 ✓.

- [ ] **Step 3: settings.json 확인**

```bash
python3 -c "
import json, os
d = json.load(open(os.path.expanduser('~/.claude/settings.json')))
m = d.get('extraKnownMarketplaces', {})
print('Marketplace:', 'daye-agent-toolkit' in m)
ep = d.get('enabledPlugins', {})
for p in ['life-management', 'finance', 'dev-tools', 'media-fetch']:
    key = f'{p}@daye-agent-toolkit'
    print(f'  {p}:', ep.get(key, False))
"
```

Expected: 모두 True.

- [ ] **Step 4: rules 심링크 확인**

```bash
ls -la ~/.claude/rules/ | grep -c "daye-agent-toolkit"
```

Expected: 12 (규칙 파일 수).

- [ ] **Step 5: SKILL.md 내 {baseDir} 경로가 유효한지 스팟 체크**

life-coach의 scripts 경로가 플러그인 구조에서 정상 작동하는지 확인:

```bash
# life-coach의 baseDir = plugins/life-management/skills/life-coach
ls plugins/life-management/skills/life-coach/scripts/daily_coach.py
```

Expected: 파일 존재.

- [ ] **Step 6: 최종 디렉토리 구조 확인**

```bash
find . -maxdepth 1 -type d | sort | grep -v '.git'
```

Expected: `.claude`, `codex`, `docs`, `mcp`, `plugins`, `rules` (+ 숨김 디렉토리)

- [ ] **Step 7: 커밋 (필요 시)**

검증 중 발견된 문제를 수정했으면 커밋.

```bash
git status
```

변경사항 있으면:
```bash
git add -A
git commit -m "fix: 설치 검증 중 발견된 문제 수정"
```
