# daye-agent-toolkit Makefile
# Usage:
#   make install-cc     # Claude Code: symlink shared/ + cc/ skills
#   make clean          # Remove CC symlinks
#   make sync           # Git sync (OpenClaw PC)
#   make status         # Show installation status
#   make init           # Interactive env setup

REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SKILLS_DIR := $(HOME)/.claude/skills
RULES_DIR := $(HOME)/.claude/rules

# Discover skills from directory structure (parent dir names of SKILL.md)
SHARED_DIRS := $(patsubst %/SKILL.md,%,$(wildcard shared/*/SKILL.md))
CC_DIRS := $(patsubst %/SKILL.md,%,$(wildcard cc/*/SKILL.md))
OC_DIRS := $(patsubst %/SKILL.md,%,$(wildcard openclaw/*/SKILL.md))
ALL_CC_DIRS := $(SHARED_DIRS) $(CC_DIRS)

.PHONY: install-cc clean sync status init help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install-cc: ## Install skills for Claude Code (symlink shared/ + cc/)
	@echo "=== Claude Code skill install ==="
	@mkdir -p $(SKILLS_DIR)
	@for skill_path in $(ALL_CC_DIRS); do \
		name=$$(basename $$skill_path); \
		dest="$(SKILLS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; \
		elif [ -e "$$dest" ]; then echo "  ⚠ SKIPPED $$name ($$dest exists and is not a symlink)"; continue; \
		fi; \
		ln -s "$(REPO_DIR)/$$skill_path" "$$dest"; \
		echo "  ✓ $$name → $$skill_path"; \
	done
	@echo ""
	@echo "=== Rules symlink ==="
	@mkdir -p $(RULES_DIR)
	@seen=""; \
	for rule_file in $$(find shared/*/rules cc/*/rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		case " $$seen " in \
			*" $$name "*) echo "  ⚠ CONFLICT $$name — duplicate basename, skipped ($$rule_file)"; continue ;; \
		esac; \
		seen="$$seen $$name"; \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; \
		elif [ -e "$$dest" ]; then echo "  ⚠ SKIPPED $$name (exists, not symlink)"; continue; \
		fi; \
		ln -s "$(REPO_DIR)/$$rule_file" "$$dest"; \
		echo "  ✓ $$name → $$rule_file"; \
	done
	@echo ""
	@echo "Done. $(words $(SHARED_DIRS)) shared + $(words $(CC_DIRS)) cc-only = $(words $(ALL_CC_DIRS)) skills installed."
	@echo ""
	@echo "Dashboard:"
	@echo "  alias wd='$(REPO_DIR)/_infra/cc/wd.sh'"
	@echo "  (add to ~/.zshrc for persistent access)"

clean: ## Remove CC symlinks created by install-cc
	@echo "=== Removing CC symlinks ==="
	@for skill_path in $(ALL_CC_DIRS); do \
		name=$$(basename $$skill_path); \
		dest="$(SKILLS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then \
			rm "$$dest"; \
			echo "  ✓ removed $$name"; \
		fi; \
	done
	@echo ""
	@echo "=== Removing rules symlinks ==="
	@for rule_file in $$(find shared/*/rules cc/*/rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then \
			rm "$$dest"; \
			echo "  ✓ removed rule $$name"; \
		fi; \
	done
	@echo "Done."

sync: ## Git sync for OpenClaw PC (push/pull)
	@python3 _infra/scripts/sync.py $(ARGS)

status: ## Show current installation status
	@echo "=== Skill Categories ==="
	@echo "  shared:   $(words $(SHARED_DIRS)) skills"
	@echo "  cc:       $(words $(CC_DIRS)) skills"
	@echo "  openclaw: $(words $(OC_DIRS)) skills"
	@echo "  total:    $$(( $(words $(SHARED_DIRS)) + $(words $(CC_DIRS)) + $(words $(OC_DIRS)) )) skills"
	@echo ""
	@echo "=== CC Symlinks ==="
	@for skill_path in $(ALL_CC_DIRS); do \
		name=$$(basename $$skill_path); \
		dest="$(SKILLS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  ✓ $$name"; \
		elif [ -d "$$dest" ]; then echo "  ⚠ $$name (dir, not symlink)"; \
		else echo "  ✗ $$name (not installed)"; \
		fi; \
	done
	@echo ""
	@echo "=== Rules ==="
	@for rule_file in $$(find shared/*/rules cc/*/rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  ✓ $$name"; \
		else echo "  ✗ $$name (not installed)"; \
		fi; \
	done
	@echo ""
	@echo "=== OpenClaw extraDirs ==="
	@python3 -c "import json,os;p=os.path.expanduser('~/.openclaw/openclaw.json');c=json.load(open(p)) if os.path.exists(p) else {};dirs=c.get('skills',{}).get('load',{}).get('extraDirs',[]);[print(f'  {d}') for d in dirs] if dirs else print('  (not configured)')" 2>/dev/null || echo "  (openclaw.json not found)"

init: ## Interactive environment setup
	@python3 _infra/scripts/setup_env.py
