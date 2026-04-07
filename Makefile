# daye-agent-toolkit Makefile
# Usage:
#   make install       # 스킬 + 규칙 심링크
#   make clean         # 심링크 제거
#   make status        # 설치 상태 확인

REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SKILLS_DIR := $(HOME)/.claude/skills
RULES_DIR := $(HOME)/.claude/rules

# Discover skills from plugin structure (parent dir names of SKILL.md)
SKILL_DIRS := $(patsubst %/SKILL.md,%,$(wildcard plugins/*/skills/*/SKILL.md))

.PHONY: install clean status help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: _symlink-skills _symlink-rules ## Install skills + rules
	@echo ""
	@echo "Done. $(words $(SKILL_DIRS)) skills + $$(find rules -name '*.md' | wc -l | tr -d ' ') rules installed."
	@echo "Run 'make status' to verify."

_symlink-skills:
	@echo "=== Symlink skills ==="
	@mkdir -p $(SKILLS_DIR)
	@for skill_path in $(SKILL_DIRS); do \
		name=$$(basename $$skill_path); \
		dest="$(SKILLS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; \
		elif [ -e "$$dest" ]; then echo "  ⚠ SKIPPED $$name (exists, not symlink)"; continue; \
		fi; \
		ln -s "$(REPO_DIR)/$$skill_path" "$$dest"; \
		echo "  ✓ $$name"; \
	done

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

clean: ## Remove skills + rules symlinks
	@echo "=== Remove skill symlinks ==="
	@for skill_path in $(SKILL_DIRS); do \
		name=$$(basename $$skill_path); \
		dest="$(SKILLS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; echo "  ✓ removed $$name"; fi; \
	done
	@echo ""
	@echo "=== Remove rules symlinks ==="
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; echo "  ✓ removed $$name"; fi; \
	done

status: ## Show installation status
	@echo "=== Skills ($(words $(SKILL_DIRS))) ==="
	@for skill_path in $(SKILL_DIRS); do \
		name=$$(basename $$skill_path); \
		dest="$(SKILLS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  ✓ $$name"; \
		else echo "  ✗ $$name (not installed)"; fi; \
	done
	@echo ""
	@echo "=== Rules ==="
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  ✓ $$name"; \
		else echo "  ✗ $$name (not installed)"; fi; \
	done
