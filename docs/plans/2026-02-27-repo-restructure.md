# daye-agent-toolkit Repo Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize flat skill directories into categorized subdirectories (shared/, cc/, openclaw/) with infra isolation, replace setup.sh with Makefile, and update all configs.

**Architecture:** Move 25 skill directories into 3 category dirs using `git mv` to preserve history. Infrastructure files move to `_infra/`. Makefile replaces setup.sh with individual targets for CC and OpenClaw setup. OpenClaw extraDirs config updated to point to new paths.

**Tech Stack:** bash, make, python3 (stdlib only), git

---

### Task 1: Create target directory structure

**Files:**
- Create: `shared/` (directory)
- Create: `cc/` (directory)
- Create: `openclaw/` (directory)
- Create: `_infra/scripts/` (directory)
- Create: `_infra/cc/` (directory)
- Create: `_infra/docs/plans/` (directory)

**Step 1: Create all target directories**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit
mkdir -p shared cc openclaw _infra/scripts _infra/cc _infra/docs/plans
```

**Step 2: Verify directories exist**

```bash
ls -d shared cc openclaw _infra _infra/scripts _infra/cc _infra/docs/plans
```

Expected: all 7 paths listed without error.

**Step 3: Commit**

```bash
git add shared/.gitkeep cc/.gitkeep openclaw/.gitkeep _infra/.gitkeep
# Note: git doesn't track empty dirs, but git mv in next tasks will create them
```

No commit yet — empty dirs aren't tracked. Proceed to Task 2.

---

### Task 2: Move shared skills (CC + OpenClaw)

**Files:**
- Move: `banksalad-import/` → `shared/banksalad-import/`
- Move: `health-coach/` → `shared/health-coach/`
- Move: `health-tracker/` → `shared/health-tracker/`
- Move: `investment-report/` → `shared/investment-report/`
- Move: `investment-research/` → `shared/investment-research/`
- Move: `meal-tracker/` → `shared/meal-tracker/`
- Move: `news-brief/` → `shared/news-brief/`
- Move: `pantry-manager/` → `shared/pantry-manager/`
- Move: `saju-manse/` → `shared/saju-manse/`

**Step 1: Move all 9 shared skills**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit
git mv banksalad-import shared/
git mv health-coach shared/
git mv health-tracker shared/
git mv investment-report shared/
git mv investment-research shared/
git mv meal-tracker shared/
git mv news-brief shared/
git mv pantry-manager shared/
git mv saju-manse shared/
```

**Step 2: Verify moves**

```bash
ls shared/
```

Expected: 9 directories listed.

```bash
ls shared/news-brief/SKILL.md shared/saju-manse/SKILL.md
```

Expected: both files exist.

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: move shared skills to shared/"
```

---

### Task 3: Move Claude Code-only skills

**Files:**
- Move: `correction-memory/` → `cc/correction-memory/`
- Move: `mermaid-diagrams/` → `cc/mermaid-diagrams/`
- Move: `professional-communication/` → `cc/professional-communication/`
- Move: `reddit-fetch/` → `cc/reddit-fetch/`
- Move: `skill-forge/` → `cc/skill-forge/`
- Move: `work-digest/` → `cc/work-digest/`
- Move: `youtube-fetch/` → `cc/youtube-fetch/`

**Step 1: Move all 7 CC-only skills**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit
git mv correction-memory cc/
git mv mermaid-diagrams cc/
git mv professional-communication cc/
git mv reddit-fetch cc/
git mv skill-forge cc/
git mv work-digest cc/
git mv youtube-fetch cc/
```

**Step 2: Verify moves**

```bash
ls cc/
```

Expected: 7 directories listed.

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: move CC-only skills to cc/"
```

---

### Task 4: Move OpenClaw-only skills

**Files:**
- Move: `check-integrations/` → `openclaw/check-integrations/`
- Move: `elon-thinking/` → `openclaw/elon-thinking/`
- Move: `notion/` → `openclaw/notion/`
- Move: `prompt-guard/` → `openclaw/prompt-guard/`
- Move: `quant-swing/` → `openclaw/quant-swing/`

Note: CLAUDE.md listed 9 OpenClaw skills but only 5 exist. Missing (already deleted):
model-health-orchestrator, openclaw-docs, orchestrator, proactive-agent.

**Step 1: Move all 5 OpenClaw-only skills**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit
git mv check-integrations openclaw/
git mv elon-thinking openclaw/
git mv notion openclaw/
git mv prompt-guard openclaw/
git mv quant-swing openclaw/
```

**Step 2: Verify moves**

```bash
ls openclaw/
```

Expected: 5 directories listed.

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: move OpenClaw-only skills to openclaw/"
```

---

### Task 5: Move infrastructure files

**Files:**
- Move: `_cc/setup_env.py` → `_infra/scripts/setup_env.py`
- Move: `_cc/statusline.sh` → `_infra/cc/statusline.sh`
- Move: `scripts/sync.py` → `_infra/scripts/sync.py`
- Move: `docs/plans/*` → `_infra/docs/plans/`
- Remove: empty `_cc/`, `scripts/`, `docs/` directories

**Step 1: Move infra files**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit
git mv _cc/setup_env.py _infra/scripts/setup_env.py
git mv _cc/statusline.sh _infra/cc/statusline.sh
git mv scripts/sync.py _infra/scripts/sync.py
git mv docs/plans/* _infra/docs/plans/
```

**Step 2: Remove empty directories**

```bash
rmdir _cc scripts docs/plans docs 2>/dev/null; true
```

**Step 3: Verify**

```bash
ls _infra/scripts/
# Expected: setup_env.py  sync.py
ls _infra/cc/
# Expected: statusline.sh
ls _infra/docs/plans/
# Expected: all plan .md files
```

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: move infrastructure files to _infra/"
```

---

### Task 6: Update skills.json

**Files:**
- Modify: `skills.json`

**Step 1: Rewrite skills.json**

The new structure eliminates the need for manual skill lists — Makefile will glob directories. skills.json keeps only marketplace/plugin config and category metadata.

```json
{
  "$comment": "daye-agent-toolkit 매니페스트. Makefile이 이 파일과 디렉토리 구조로 환경을 구성합니다.",
  "categories": {
    "shared": "CC + OpenClaw 양쪽에서 사용하는 스킬",
    "cc": "Claude Code 전용 스킬",
    "openclaw": "OpenClaw 전용 스킬"
  },
  "marketplaces": [
    {
      "name": "claude-plugins-official",
      "source": "github",
      "repo": "anthropics/claude-plugins-official"
    }
  ],
  "plugins": [
    { "marketplace": "claude-plugins-official", "name": "superpowers" }
  ]
}
```

**Step 2: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open('skills.json')); print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add skills.json
git commit -m "refactor: simplify skills.json — directory-based discovery"
```

---

### Task 7: Create Makefile

**Files:**
- Create: `Makefile`

**Step 1: Write Makefile**

```makefile
# daye-agent-toolkit Makefile
# Usage:
#   make install-cc     # Claude Code: symlink shared/ + cc/ skills
#   make install-oc     # OpenClaw: update extraDirs config
#   make clean          # Remove CC symlinks
#   make sync           # Git sync (OpenClaw PC)
#   make status         # Show installation status
#   make init           # Interactive env setup

REPO_DIR := $(shell pwd)
SKILLS_DIR := $(HOME)/.claude/skills

# Discover skills from directory structure
SHARED_SKILLS := $(notdir $(wildcard shared/*/SKILL.md))
CC_SKILLS := $(notdir $(wildcard cc/*/SKILL.md))
OC_SKILLS := $(notdir $(wildcard openclaw/*/SKILL.md))

# Fix: wildcard returns SKILL.md, we want parent dir names
SHARED_DIRS := $(patsubst %/SKILL.md,%,$(wildcard shared/*/SKILL.md))
CC_DIRS := $(patsubst %/SKILL.md,%,$(wildcard cc/*/SKILL.md))
OC_DIRS := $(patsubst %/SKILL.md,%,$(wildcard openclaw/*/SKILL.md))

.PHONY: install-cc install-oc clean sync status init help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install-cc: ## Install skills for Claude Code (symlink)
	@echo "=== Claude Code skill install ==="
	@mkdir -p $(SKILLS_DIR)
	@for skill_path in $(SHARED_DIRS) $(CC_DIRS); do \
		name=$$(basename $$skill_path); \
		dest="$(SKILLS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; fi; \
		ln -s "$(REPO_DIR)/$$skill_path" "$$dest"; \
		echo "  ✓ $$name → $$skill_path"; \
	done
	@echo ""
	@echo "Done. $(words $(SHARED_DIRS)) shared + $(words $(CC_DIRS)) cc = $$(( $(words $(SHARED_DIRS)) + $(words $(CC_DIRS)) )) skills installed."

install-oc: ## Configure OpenClaw extraDirs
	@echo "=== OpenClaw config update ==="
	@python3 -c "\
import json, os; \
config_path = os.path.expanduser('~/.openclaw/openclaw.json'); \
config = json.load(open(config_path)) if os.path.exists(config_path) else {}; \
skills = config.setdefault('skills', {}); \
load = skills.setdefault('load', {}); \
repo = '$(REPO_DIR)'; \
new_dirs = [os.path.expanduser('~/.openclaw/core-skills'), repo + '/shared', repo + '/openclaw']; \
load['extraDirs'] = new_dirs; \
json.dump(config, open(config_path, 'w'), indent=2, ensure_ascii=False); \
print('✓ extraDirs updated:'); \
[print(f'  {d}') for d in new_dirs]; \
"

clean: ## Remove CC symlinks created by install-cc
	@echo "=== Removing CC symlinks ==="
	@for skill_path in $(SHARED_DIRS) $(CC_DIRS); do \
		name=$$(basename $$skill_path); \
		dest="$(SKILLS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then \
			rm "$$dest"; \
			echo "  ✓ removed $$name"; \
		fi; \
	done
	@echo "Done."

sync: ## Git sync for OpenClaw PC (push + pull)
	@python3 _infra/scripts/sync.py $(ARGS)

status: ## Show current installation status
	@echo "=== Skill Categories ==="
	@echo "  shared:  $(words $(SHARED_DIRS)) skills"
	@echo "  cc:      $(words $(CC_DIRS)) skills"
	@echo "  openclaw: $(words $(OC_DIRS)) skills"
	@echo ""
	@echo "=== CC Symlinks ==="
	@for skill_path in $(SHARED_DIRS) $(CC_DIRS); do \
		name=$$(basename $$skill_path); \
		dest="$(SKILLS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  ✓ $$name"; \
		elif [ -d "$$dest" ]; then echo "  ⚠ $$name (dir, not symlink)"; \
		else echo "  ✗ $$name (not installed)"; \
		fi; \
	done
	@echo ""
	@echo "=== OpenClaw extraDirs ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('~/.openclaw/openclaw.json'); \
c = json.load(open(p)) if os.path.exists(p) else {}; \
dirs = c.get('skills', {}).get('load', {}).get('extraDirs', []); \
[print(f'  {d}') for d in dirs] if dirs else print('  (not configured)'); \
" 2>/dev/null || echo "  (openclaw.json not found)"

init: ## Interactive environment setup
	@python3 _infra/scripts/setup_env.py
```

**Step 2: Verify Makefile syntax**

```bash
make help
```

Expected: formatted list of available targets.

**Step 3: Verify install-cc target (dry run check)**

```bash
make status
```

Expected: lists skills by category with install status.

**Step 4: Commit**

```bash
git add Makefile
git commit -m "feat: add Makefile replacing setup.sh"
```

---

### Task 8: Update sync.py paths

**Files:**
- Modify: `_infra/scripts/sync.py:176-179`

**Step 1: Update skill counting logic in cmd_status()**

The `cmd_status()` function filters directories by name. With the new structure, skills are in `shared/`, `cc/`, `openclaw/` subdirs.

Replace the skill counting logic (around line 176):

```python
# Old:
skills = [d.name for d in REPO_ROOT.iterdir()
          if d.is_dir() and not d.name.startswith(".")
          and d.name not in ("docs", "scripts")]

# New:
categories = ["shared", "cc", "openclaw"]
skills = []
for cat in categories:
    cat_dir = REPO_ROOT / cat
    if cat_dir.is_dir():
        skills.extend(
            f"{cat}/{d.name}" for d in cat_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )
print(f"\n  Skills ({len(skills)}):")
for cat in categories:
    cat_skills = [s.split("/")[1] for s in skills if s.startswith(cat + "/")]
    if cat_skills:
        print(f"    {cat} ({len(cat_skills)}): {', '.join(sorted(cat_skills))}")
```

**Step 2: Update docstring paths**

Replace references to `python scripts/sync.py` with `python _infra/scripts/sync.py` or `make sync` in the docstring.

**Step 3: Commit**

```bash
git add _infra/scripts/sync.py
git commit -m "fix: update sync.py for new directory structure"
```

---

### Task 9: Remove old setup.sh

**Files:**
- Remove: `setup.sh`

**Step 1: Remove setup.sh**

```bash
git rm setup.sh
```

**Step 2: Commit**

```bash
git commit -m "chore: remove setup.sh (replaced by Makefile)"
```

---

### Task 10: Update .gitignore

**Files:**
- Modify: `.gitignore`

**Step 1: Add new entries**

```
.DS_Store
*.swp
*.swo
*~
.claude/settings.local.json
__pycache__/
.claude/worktrees/
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .claude/worktrees/ to .gitignore"
```

---

### Task 11: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Rewrite CLAUDE.md**

Update to reflect new directory structure:
- Replace flat skill tables with categorized tables referencing `shared/`, `cc/`, `openclaw/`
- Update setup instructions (`./setup.sh` → `make install-cc`)
- Update sync instructions (`scripts/sync.py` → `make sync`)
- Update "새 스킬 추가 절차" to reference category directories
- Update `scripts/ 규칙` to reference `_infra/scripts/`
- Remove references to `local_skills` in skills.json

Key sections to update:
- 접근 방식 table
- 스킬 분류 section (3 category tables → directory-based)
- skills.json 매니페스트 section
- 새 스킬 추가 절차
- 동기화 section
- scripts/ 규칙

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for new directory structure"
```

---

### Task 12: Update .claude-plugin/marketplace.json (if needed)

**Files:**
- Check: `.claude-plugin/marketplace.json`

**Step 1: Verify marketplace.json**

The marketplace.json has no path references to skills — it's just metadata. No changes needed.

**Step 2: Skip commit — no changes.**

---

### Task 13: Run make install-cc and verify

**Step 1: Clean old symlinks**

```bash
make clean
```

**Step 2: Also remove dead symlinks from other sources**

```bash
# Check for broken symlinks in ~/.claude/skills/
find ~/.claude/skills/ -maxdepth 1 -type l ! -exec test -e {} \; -print
```

Remove any broken ones manually.

**Step 3: Install new symlinks**

```bash
make install-cc
```

Expected: 16 skills installed (9 shared + 7 cc).

**Step 4: Verify symlinks**

```bash
make status
```

Expected: all 16 skills show ✓.

**Step 5: Verify a skill is accessible**

```bash
ls -la ~/.claude/skills/news-brief
# Expected: symlink → /Users/dayejeong/git_workplace/daye-agent-toolkit/shared/news-brief
ls ~/.claude/skills/news-brief/SKILL.md
# Expected: file exists
```

---

### Task 14: Update OpenClaw config and verify

**Step 1: Update OpenClaw extraDirs**

```bash
make install-oc
```

Expected output:
```
✓ extraDirs updated:
  ~/.openclaw/core-skills
  /Users/dayejeong/git_workplace/daye-agent-toolkit/shared
  /Users/dayejeong/git_workplace/daye-agent-toolkit/openclaw
```

**Step 2: Verify config**

```bash
python3 -c "
import json
c = json.load(open('$HOME/.openclaw/openclaw.json'))
dirs = c['skills']['load']['extraDirs']
for d in dirs:
    print(d)
"
```

Expected: 3 directories listed with new paths.

**Step 3: Verify OpenClaw symlink still works**

```bash
ls -la ~/.openclaw/daye-agent-toolkit
# Expected: symlink → /Users/dayejeong/git_workplace/daye-agent-toolkit
ls ~/.openclaw/daye-agent-toolkit/shared/news-brief/SKILL.md
# Expected: file exists
```

---

## Task Dependency Graph

```
Task 1 (dirs) → Task 2 (shared) → Task 3 (cc) → Task 4 (openclaw) → Task 5 (infra)
                                                                          ↓
Task 6 (skills.json) ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
Task 7 (Makefile) ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
Task 8 (sync.py) ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
Task 9 (rm setup.sh) ← Task 7
Task 10 (.gitignore) — independent
Task 11 (CLAUDE.md) ← Task 6, Task 7
Task 12 (marketplace) — independent
Task 13 (verify CC) ← Task 7
Task 14 (verify OC) ← Task 7
```

Tasks 2-4 are sequential (same directory operations).
Tasks 6-8, 10, 12 can run in parallel after Task 5.
Tasks 9, 11 depend on Task 7.
Tasks 13-14 are final verification.
